"""OneMap REST token renewal, cached in memory using the provider's expiry."""
from dataclasses import dataclass, field
import json
from threading import Lock
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class TokenError(Exception):
    """Only a safe status code is exposed; no provider body or credentials."""


@dataclass
class OneMapTokens:
    email: str = field(repr=False)
    password: str = field(repr=False)
    _token: str = field(default='',repr=False)
    _expires: float = field(default=0,repr=False)
    _lock: Lock = field(default_factory=Lock,repr=False)

    def get(self, *, rejected_token: str | None = None) -> str:
        """Renew before expiry or once after a rejected token; serialize renewal."""
        with self._lock:
            if self._token and time.time() < self._expires-60 and self._token != rejected_token:
                return self._token
            request = Request('https://www.onemap.gov.sg/api/auth/post/getToken',
                data=json.dumps({'email':self.email,'password':self.password}).encode('utf-8'),
                headers={'Content-Type':'application/json','Accept':'application/json'},method='POST')
            try:
                with urlopen(request,timeout=8) as response:
                    payload=json.loads(response.read())
                token=payload['access_token']
                expiry=int(payload['expiry_timestamp'])
                if not isinstance(token,str) or not token or any(c.isspace() for c in token) or expiry <= time.time()+60:
                    raise ValueError('Invalid token response')
            except HTTPError as exc:
                raise TokenError('authentication_failed' if exc.code in (400,401,403,404) else
                                 'quota_exceeded' if exc.code==429 else 'provider_unavailable') from None
            except (URLError, TimeoutError, OSError):
                raise TokenError('provider_unavailable') from None
            except (ValueError, TypeError, KeyError, UnicodeError):
                raise TokenError('invalid_auth_response') from None
            self._token,self._expires=token,expiry
            return token
