"""Interactively configure the private operator login; never save a plain password.

Run on the laptop with the backend stopped, then restart it with the demo script.
"""
from getpass import getpass
from pathlib import Path
import re

from operator_auth import hash_password


def main():
    path = Path(__file__).with_name('.env')
    if not path.is_file():
        raise SystemExit('Configure backend/.env first; existing provider settings must be preserved.')
    source = path.read_text(encoding='utf-8-sig')
    username = input('Operator username: ').strip()
    if not username or len(username) > 100 or any(c in username for c in '\r\n#\'"'):
        raise SystemExit('Use a nonempty username up to 100 characters without quotes or #.')
    password = getpass('Operator password (at least 8 characters): ')
    if len(password) < 8 or len(password) > 200:
        raise SystemExit('Use a password between 8 and 200 characters.')
    if password != getpass('Confirm password: '):
        raise SystemExit('Passwords do not match; configuration was not changed.')
    if re.search(r'^OPERATOR_PASSWORD_HASH=\S+', source, flags=re.MULTILINE):
        if input('Replace the existing operator credential? Type yes: ').strip() != 'yes':
            raise SystemExit('Configuration was not changed.')
    values = {'OPERATOR_USERNAME': username, 'OPERATOR_PASSWORD_HASH': hash_password(password)}
    for key, value in values.items():
        pattern = re.compile(r'^' + key + r'=.*$', flags=re.MULTILINE)
        if pattern.search(source):
            source = pattern.sub(lambda _: key + '=' + value, source)
        else:
            source = source.rstrip('\r\n') + '\n' + key + '=' + value + '\n'
    path.write_text(source, encoding='utf-8', newline='\n')
    print('Operator username and password hash saved privately. No plain password was saved.')
    print('Restart the backend before testing operator sign-in. Drivers still do not sign in.')


if __name__ == '__main__':
    main()
