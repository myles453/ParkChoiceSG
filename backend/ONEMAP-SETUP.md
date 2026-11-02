# OneMap destination search and routing

The local backend adapter is `onemap_adapter.py`. It uses Python's standard
library and the existing private environment loader. It does not need a Google
key, write to PostgreSQL, join the periodic collector or save raw responses.

## Local setup

Put the OneMap **REST access token** in the ignored `.env` beside the scripts:

```dotenv
ONEMAP_ACCESS_TOKEN=
```

Paste only the token value after `=`, not the whole JSON response or an
`Authorization`/`Bearer` header. Keep existing provider/database settings.
The loader now accepts this additional field; existing process environment
values still take precedence. An expired token must be replaced privately.

The standard REST authentication response includes `expiry_timestamp`. Use that
expiry rather than assuming the token lasts indefinitely. For automatic renewal,
set both `ONEMAP_EMAIL` and `ONEMAP_PASSWORD` in the server's private `.env`.
`OneMapTokens` obtains a token via HTTPS and caches it in memory until 60 seconds
before expiry. A rejected token triggers one renewal/retry, not an infinite loop.
The replacement is not printed or written into `.env`. With both credentials
blank, manual-token mode remains available. OneMap's MCP flow is separate; this is the REST
search/routing adapter. See [REST authentication](https://www.onemap.gov.sg/apidocs/authentication).

From the local `backend` directory:

```powershell
.\.venv\Scripts\python.exe onemap_adapter.py check
```

The check searches for City Hall MRT and tries driving and walking between two
fixed public sample points. It prints normalized results with no token and exits
nonzero on failure. It does not use device GPS or write an archive.

Individual calls:

```powershell
.\.venv\Scripts\python.exe onemap_adapter.py search --query "City Hall MRT"
.\.venv\Scripts\python.exe onemap_adapter.py route --start 1.2932 103.8520 --end 1.2868 103.8545 --mode drive
.\.venv\Scripts\python.exe onemap_adapter.py route --start 1.2932 103.8520 --end 1.2868 103.8545 --mode walk
```

## Interface and fields

`RoutingProvider` is a typed interface for interchangeable/mock routing providers.
`OneMapClient` implements `route(start: Coordinate, end: Coordinate, mode: str)`
and also provides `search(query: str)`. `Coordinate` uses WGS84 decimal degrees in
**latitude, longitude** order, not SVY21 easting/northing.

| Result | Meaning |
|---|---|
| Search `matches` | First-page destination choices with label, address, postal code where supplied and coordinates. The app/user chooses; the adapter does not silently select the first match. |
| Route `status` | `ok`, or an explicit failure such as `authentication_failed`, `access_denied`, `no_route`, `quota_exceeded`, `provider_unavailable` or `invalid_response`. |
| `distance_meters` | Routed distance; null on failure, never a straight-line substitute. |
| `duration_seconds` | Provider-estimated route duration, retaining seconds for forecast horizons. |
| `requested_at`, `retrieved_at` | UTC instants recording when the call began and its response was received. |
| Driving `estimated_arrival_at` | `requested_at + duration_seconds`, assuming departure at request time. No allowance for parking search or delay before starting. |
| `traffic_basis` | `not_confirmed`. The documented drive/walk REST request exposes no departure-time or traffic-model parameter. Do not label this live-traffic ETA. |

HTTP success alone is not enough: provider error envelopes, missing/invalid
measurements and non-success route statuses are checked. Missing data is not
converted to zero. HTTP retries reuse the collector's bounded network helper.
Error bodies, credentials and raw route responses are not logged or archived.
The CLI's normalized results are intended for a local check; the app backend
should avoid adding personal driver coordinates/searches to ordinary logs.

API reference: [OneMap routing](https://www.onemap.gov.sg/apidocs/routing),
[destination search](https://www.onemap.gov.sg/apidocs/search).

## Connected workflow

1. Let the driver select a destination from search results and provide an origin
   through an agreed GPS/manual flow.
2. Shortlist nearby canonical carparks from our existing cleaned coordinates.
   Select route points deliberately for multi-point locations; published points
   are not verified entrances.
3. For each shortlisted carpark, route **origin to carpark** in driving mode and
   **carpark to destination** in walking mode. A failed route keeps that candidate
   explicitly unavailable for the affected factor.
4. Give the driving arrival estimate to the model as its forecast target. Keep
   model confidence separate from routing uncertainty and refresh estimates when
   the departure/location changes.
5. Price the stay with the same candidate-specific arrival using the comparison
   interface. The current cost engine requires minute precision, so document the
   chosen approximation before connecting exact-second ETAs. Preserve the actual
   ETA for prediction. See `COMPARISON-INTEGRATION.md`.
6. Return cost, predicted/current availability, driving time, walking distance
   and their statuses for the provisional scoring policy. See the separate
   validation record under `validation/SCORING-VALIDATION.md`.

The local HTTP endpoint, candidate orchestration and root Flutter search screen
now implement this flow. The trained predictor is pending, and no public
deployment has been made. See `../BACKEND-RUNBOOK.md`. Do not poll routes for all
stored carparks as part of the availability-training collection loop.

## Verified live on 15 October 2026

The private configured token passed a real check: City Hall MRT search returned
10 valid first-page matches. The fixed sample points returned a driving route of
2,190 metres / 274 seconds and a walking route of 1,044 metres / 753 seconds.
These are dated sample route results, not measured journey times or guarantees
about live traffic. No credentials, raw API archives or database rows were added
to the repository by that check.

Automatic REST authentication was also verified live after private credentials
were supplied: destination search and driving succeeded, and the next request
reused the cached token. Offline checks verified expiry/renewal, concurrent cache
reuse and bounded authentication retry.

A live renewal-path check then forced only the local cache expiry, obtained a
replacement from the real authentication endpoint, and verified driving/walking
with it. Two authentication calls covered initial login and renewal; the next
request reused the cached replacement. No token values were printed or archived.
