"""Single operator credential for the console. The backend stores no driver accounts.

OPERATOR_USERNAME and OPERATOR_PASSWORD_HASH live in server-side configuration.
Generate the hash with: python operator_auth.py
"""
from getpass import getpass
import hashlib
import hmac
import os
import secrets
from typing import Mapping

SCHEME = 'pbkdf2_sha256'
ITERATIONS = 600_000


def hash_password(password: str, salt: str | None = None, iterations: int = ITERATIONS) -> str:
    """Return 'pbkdf2_sha256$iterations$salt_hex$digest_hex' for the configuration file."""
    if not password:
        raise ValueError('Password must not be empty')
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), iterations).hex()
    return f'{SCHEME}${iterations}${salt}${digest}'


def verify_operator(username: str, password: str, env: Mapping[str, str] = os.environ) -> bool:
    """Compare in constant time. Raises ValueError when the server has no valid credential."""
    expected_user = env.get('OPERATOR_USERNAME', '').strip()
    stored = env.get('OPERATOR_PASSWORD_HASH', '').strip()
    if not expected_user or not stored:
        raise ValueError('Operator login is not configured')
    try:
        scheme, iterations, salt, digest = stored.split('$')
        iterations = int(iterations)
        bytes.fromhex(salt)
    except ValueError:
        raise ValueError('OPERATOR_PASSWORD_HASH is malformed') from None
    if scheme != SCHEME or iterations < 1:
        raise ValueError('OPERATOR_PASSWORD_HASH is malformed')
    candidate = hash_password(password, salt, iterations).rsplit('$', 1)[1] if password else ''
    user_ok = hmac.compare_digest(username.encode(), expected_user.encode())
    password_ok = hmac.compare_digest(candidate.encode(), digest.encode())
    return user_ok and password_ok


if __name__ == '__main__':
    print(hash_password(getpass('Operator password: ')))
