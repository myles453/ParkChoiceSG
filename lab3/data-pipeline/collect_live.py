"""Collect one live HDB, LTA and URA availability cycle into PostgreSQL.

Run this from a trusted backend environment with DATABASE_URL and provider
keys configured. The existing collectors archive raw responses and manifests.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

from provider_puller import load_local_env


BASE = Path(__file__).resolve().parent


def rates_due(connection):
    """Refresh daily; only runtime-compiled captures count as successful imports."""
    with connection.cursor() as cursor:
        cursor.execute("""SELECT NOT EXISTS (
            SELECT 1 FROM parking_data.rate_schedules
            WHERE source='ura_details' AND valid_until IS NULL
              AND calculator_config->>'compiler_version'='ura_windows_v1'
              AND valid_from > now() - interval '1 day')""")
        return cursor.fetchone()[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-only", action="store_true", help="Collect and clean without a database connection")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--include-rates", action="store_true", help="Force a fresh URA tariff capture and import")
    mode.add_argument("--availability-only", action="store_true", help="Explicitly skip the automatic daily URA tariff refresh")
    args = parser.parse_args()
    load_local_env(BASE / ".env")
    needed = ["LTA_ACCOUNT_KEY", "URA_ACCESS_KEY"] + ([] if args.archive_only else ["DATABASE_URL"])
    missing = [name for name in needed
               if not os.environ.get(name)]
    if missing:
        raise SystemExit("Missing configuration: " + ", ".join(missing))
    load = [] if args.archive_only else ["--load"]
    include_rates = args.include_rates
    if not args.availability_only and not include_rates:
        if args.archive_only:
            include_rates = True
        else:
            import psycopg
            try:
                with psycopg.connect(os.environ['DATABASE_URL'], connect_timeout=15,
                                     sslmode='require', prepare_threshold=None) as connection:
                    include_rates = rates_due(connection)
            except Exception as exc:
                raise SystemExit(f"Cannot check pricing freshness ({type(exc).__name__}); configuration remains private.") from None
    rates = ["--include-rates"] if include_rates else []
    for command in (["puller.py", *load],
                    ["provider_puller.py", "--provider", "lta", *load],
                    ["provider_puller.py", "--provider", "ura", *rates, *load]):
        print("Collecting " + " ".join(command), flush=True)
        completed = subprocess.run([sys.executable, *command], cwd=BASE, check=False)
        if completed.returncode:
            raise SystemExit(f"Collection stopped: {command[0]} returned {completed.returncode}. "
                             "Inspect that run's local manifest.")


if __name__ == "__main__":
    main()
