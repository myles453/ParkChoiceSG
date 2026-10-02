"""Read-only smoke test of live data, pricing coverage and a sample stay."""
import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os

from provider_puller import load_local_env
from comparison import compare_carparks
from collect_live import rates_due


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--arrival-in-minutes', type=int, default=30)
    parser.add_argument('--duration-minutes', type=int, default=60)
    args = parser.parse_args()
    load_local_env()
    import psycopg
    arrival = (datetime.now(timezone.utc) + timedelta(minutes=args.arrival_in_minutes)).replace(second=0, microsecond=0)
    try:
        with psycopg.connect(os.environ['DATABASE_URL'], sslmode='require',
                             connect_timeout=15, prepare_threshold=None) as connection:
            connection.read_only = True
            due = rates_due(connection)
            rows = compare_carparks(connection, arrival, args.duration_minutes)
            with connection.cursor() as cursor:
                cursor.execute("""SELECT agency,review_status,count(*)
                    FROM parking_data.rate_schedules WHERE valid_until IS NULL
                    GROUP BY agency,review_status ORDER BY agency,review_status""")
                schedules = cursor.fetchall()
        print(json.dumps({'checked_at':datetime.now(timezone.utc).isoformat(),
            'arrival_at':arrival.isoformat(),'duration_minutes':args.duration_minutes,
            'ura_rate_refresh_due':due,'open_schedules':schedules,
            'by_agency':{agency:{
                'carparks':sum(r['agency']==agency for r in rows),
                'quote_statuses':dict(Counter(r['price']['status'] for r in rows if r['agency']==agency)),
                'availability_statuses':dict(Counter(r['availability_status'] for r in rows if r['agency']==agency)),
                'strict_price_comparison_eligible':sum(r['price_comparison_eligible'] for r in rows if r['agency']==agency)
            } for agency in sorted({r['agency'] for r in rows})}}, indent=2))
    except Exception as exc:
        raise SystemExit(f"Readiness check failed ({type(exc).__name__}); connection details withheld.") from None


if __name__ == '__main__':
    main()
