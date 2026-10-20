"""Request-time OneMap REST search/routing. No database writes or raw archives.

Credentials stay in a server-side environment. OneMap's documented drive API
does not accept a departure-time/traffic-model parameter: its duration must not
be presented as a verified live-traffic ETA.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import json
from math import isfinite
import os
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode

from pipeline_support import load_local_env
from pipeline_support import get_json
from onemap_auth import OneMapTokens, TokenError

ROOT = 'https://www.onemap.gov.sg/api'
_tokens: OneMapTokens | None = None


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float

    def __post_init__(self):
        for name, value, bound in [('latitude', self.latitude, 90), ('longitude', self.longitude, 180)]:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or abs(value) > bound:
                raise ValueError(f'{name} must be a finite WGS84 decimal degree value')

    def query_value(self):
        return f'{self.latitude},{self.longitude}'


@dataclass(frozen=True)
class RouteEstimate:
    status: str
    mode: str
    requested_at: datetime
    retrieved_at: datetime
    distance_meters: float | None = None
    duration_seconds: float | None = None
    estimated_arrival_at: datetime | None = None
    provider: str = 'onemap'
    traffic_basis: str = 'not_confirmed'
    departure_assumption: str = 'request_time'


class RoutingProvider(Protocol):
    """Backend routing dependency; implementations can be replaced or mocked."""

    def route(self, start: Coordinate, end: Coordinate, mode: str) -> RouteEstimate: ...


@dataclass(frozen=True)
class SearchMatch:
    name: str
    address: str
    postal: str | None
    coordinate: Coordinate


@dataclass(frozen=True)
class SearchResult:
    status: str
    matches: tuple[SearchMatch, ...] = ()
    rejected_count: int = 0
    provider: str = 'onemap'


def _nonnegative_number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError('Invalid route measurement')
    result = float(value)
    if not isfinite(result) or result < 0:
        raise ValueError('Invalid route measurement')
    return result


@dataclass
class OneMapClient:
    access_token: str = field(repr=False)
    timeout_seconds: float = 8
    tokens: OneMapTokens | None = field(default=None,repr=False)

    def __post_init__(self):
        if not isinstance(self.access_token, str) or not self.access_token.strip():
            raise ValueError('ONEMAP_ACCESS_TOKEN is empty; fill the private .env')
        self.access_token = self.access_token.strip()
        if any(char.isspace() for char in self.access_token):
            raise ValueError('Save only the access token, without a header prefix or line breaks')
        if isinstance(self.timeout_seconds, bool) or not isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be positive and finite')

    @classmethod
    def from_env(cls):
        global _tokens
        load_local_env()
        email,password=os.environ.get('ONEMAP_EMAIL',''),os.environ.get('ONEMAP_PASSWORD','')
        if bool(email) != bool(password):
            raise ValueError('Automatic renewal needs both ONEMAP_EMAIL and ONEMAP_PASSWORD')
        if email and password:
            if _tokens is None or (_tokens.email,_tokens.password)!=(email,password):
                _tokens=OneMapTokens(email,password)
            # The actual token is obtained at request time, so safe status codes
            # can be returned if the authentication service is unavailable.
            return cls('managed-token',tokens=_tokens)
        return cls(os.environ.get('ONEMAP_ACCESS_TOKEN', ''))

    def _request(self, endpoint, params):
        try:
            if self.tokens:
                self.access_token=self.tokens.get()
        except TokenError as exc:
            return str(exc),None,datetime.now(timezone.utc)
        status,payload,received=self._request_once(endpoint,params)
        if status=='authentication_failed' and self.tokens:
            try:
                self.access_token=self.tokens.get(rejected_token=self.access_token)
            except TokenError as exc:
                return str(exc),None,datetime.now(timezone.utc)
            return self._request_once(endpoint,params)
        return status,payload,received

    def _request_once(self, endpoint, params):
        try:
            payload, _, received = get_json(ROOT + endpoint + '?' + urlencode(params),
                                             {'Authorization': self.access_token},
                                             timeout=self.timeout_seconds, attempts=1)
        except HTTPError as exc:
            status = {400:'invalid_request', 401:'authentication_failed', 403:'access_denied',
                      404:'not_found', 429:'quota_exceeded'}.get(exc.code, 'provider_unavailable')
            return status, None, datetime.now(timezone.utc)
        except (URLError, TimeoutError, OSError):
            return 'provider_unavailable', None, datetime.now(timezone.utc)
        except (ValueError, UnicodeError):
            return 'invalid_response', None, datetime.now(timezone.utc)
        if not isinstance(payload, dict):
            return 'invalid_response', None, received
        # Some provider errors use HTTP 200 and may even include search results.
        # Never treat those results as successfully authenticated data.
        if payload.get('error'):
            error = str(payload['error']).lower()
            status = 'authentication_failed' if any(word in error for word in ('token', 'authenticat')) else 'provider_error'
            return status, None, received
        return 'ok', payload, received

    def route(self, start: Coordinate, end: Coordinate, mode: str) -> RouteEstimate:
        """Return route measurements; failed routes retain null distance/time."""
        if not isinstance(start, Coordinate) or not isinstance(end, Coordinate):
            raise ValueError('start and end must be Coordinate values')
        if mode not in {'drive', 'walk'}:
            raise ValueError('mode must be drive or walk')
        requested = datetime.now(timezone.utc)
        status, payload, received = self._request('/public/routingsvc/route',
            {'start':start.query_value(), 'end':end.query_value(), 'routeType':mode})
        if status != 'ok':
            return RouteEstimate('no_route' if status == 'not_found' else status, mode, requested, received)
        if type(payload.get('status')) is not int:
            return RouteEstimate('invalid_response', mode, requested, received)
        if payload['status'] != 0:
            return RouteEstimate('no_route', mode, requested, received)
        try:
            summary = payload['route_summary']
            distance = _nonnegative_number(summary['total_distance'])
            duration = _nonnegative_number(summary['total_time'])
            if distance > 0 and duration == 0:
                raise ValueError('Nonzero route distance needs positive duration')
            arrival = requested + timedelta(seconds=duration) if mode == 'drive' else None
        except (KeyError, TypeError, ValueError, OverflowError):
            return RouteEstimate('invalid_response', mode, requested, received)
        return RouteEstimate('ok', mode, requested, received, distance, duration, arrival)

    def search(self, query: str) -> SearchResult:
        """Return first-page address choices; caller/user selects the destination."""
        if not isinstance(query, str) or not query.strip() or len(query) > 200:
            raise ValueError('Search query must contain 1-200 characters')
        status, payload, _ = self._request('/common/elastic/search',
            {'searchVal':query.strip(), 'returnGeom':'Y', 'getAddrDetails':'Y', 'pageNum':1})
        if status != 'ok':
            return SearchResult(status)
        rows = payload.get('results')
        if not isinstance(rows, list):
            return SearchResult('invalid_response')
        matches, rejected = [], 0
        for row in rows:
            try:
                if isinstance(row['LATITUDE'], bool) or isinstance(row['LONGITUDE'], bool):
                    raise ValueError('Invalid destination coordinate')
                coordinate = Coordinate(float(row['LATITUDE']), float(row['LONGITUDE']))
                name, address = row['SEARCHVAL'], row['ADDRESS']
                if not isinstance(name, str) or not name or not isinstance(address, str) or not address:
                    raise ValueError('Missing destination label')
                postal = row.get('POSTAL')
                if postal is not None and not isinstance(postal, str):
                    raise ValueError('Invalid postal code')
                matches.append(SearchMatch(name, address, postal, coordinate))
            except (KeyError, TypeError, ValueError, OverflowError):
                rejected += 1
        result_status = 'ok' if matches else ('invalid_response' if rejected else 'no_results')
        return SearchResult(result_status, tuple(matches), rejected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check', help='Check search, driving and walking using public sample locations')
    search = commands.add_parser('search', help='Search for destination choices')
    search.add_argument('--query', required=True)
    route = commands.add_parser('route', help='Get one route between WGS84 coordinates')
    route.add_argument('--start', nargs=2, type=float, required=True, metavar=('LAT','LNG'))
    route.add_argument('--end', nargs=2, type=float, required=True, metavar=('LAT','LNG'))
    route.add_argument('--mode', choices=('drive','walk'), required=True)
    args = parser.parse_args()
    try:
        client = OneMapClient.from_env()
        if args.command == 'search':
            result = client.search(args.query)
            output, success = asdict(result), result.status in {'ok', 'no_results'}
        elif args.command == 'route':
            result = client.route(Coordinate(*args.start), Coordinate(*args.end), args.mode)
            output, success = asdict(result), result.status == 'ok'
        else:
            found = client.search('City Hall MRT')
            output = {'search':asdict(found)}
            success = found.status == 'ok'
            if success:
                # Fixed public sample points, not a driver's personal location.
                start, end = Coordinate(1.2932, 103.8520), Coordinate(1.2868, 103.8545)
                driving = client.route(start, end, 'drive')
                output['driving'] = asdict(driving)
                success = driving.status == 'ok'
                if driving.status not in {'authentication_failed', 'access_denied', 'quota_exceeded'}:
                    walking = client.route(start, end, 'walk')
                    output['walking'] = asdict(walking)
                    success = success and walking.status == 'ok'
        print(json.dumps(output, default=lambda value: value.isoformat(), indent=2, allow_nan=False))
        if not success:
            raise SystemExit(1)
    except ValueError:
        raise SystemExit('OneMap setup/input is invalid. Check the token field and documented inputs; private details withheld.') from None
    except Exception as exc:
        raise SystemExit(f'OneMap check failed ({type(exc).__name__}); credentials and response contents withheld.') from None


if __name__ == '__main__':
    main()
