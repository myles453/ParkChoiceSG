"""Reuse collector HTTP/config helpers; keep the API's private config beside the API."""
from pathlib import Path
import sys

PIPELINE = Path(__file__).resolve().parent.parent / 'data-pipeline'
if str(PIPELINE) not in sys.path:
    sys.path.append(str(PIPELINE))

from puller import get_json  # noqa: E402, F401
from provider_puller import load_local_env as _load_env  # noqa: E402


def load_local_env(path: Path | None = None):
    """Do not accidentally read the collector's separate .env file."""
    _load_env(path if path is not None else Path(__file__).with_name('.env'))
