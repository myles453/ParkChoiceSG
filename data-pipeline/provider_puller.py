"""Collect LTA DataMall or URA snapshots without inventing source timestamps or capacity.

Credentials come from environment variables or an ignored local .env file.
Run `python provider_puller.py --help` for options.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import uuid
from urllib.error import HTTPError

from puller import archive, count, get_json

LTA_URL = "https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2"
URA_ROOT = "https://eservice.ura.gov.sg/uraDataService"
FIELDS = ["feed", "agency", "carpark_id", "lot_type", "retrieved_at",
          "lots_available", "source_updated_at", "total_lots"]


def load_local_env(path: Path | None = None):
    """Read only known keys; process environment takes precedence. Never print values."""
    path = path or Path(__file__).with_name(".env")
    if not path.exists():
        return
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        name, separator, value = stripped.partition("=")
        if not separator:
            raise ValueError(f"Malformed .env line {line_number}")
        name, value = name.strip(), value.strip()
        if name not in {"LTA_ACCOUNT_KEY", "URA_ACCESS_KEY", "DATABASE_URL", "ONEMAP_ACCESS_TOKEN",
                        "ONEMAP_EMAIL", "ONEMAP_PASSWORD", "PARKCHOICE_MODEL_URL"}:
            raise ValueError(f"Unsupported .env name on line {line_number}")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if value:
            os.environ.setdefault(name, value)


def require_list(payload: dict, key: str) -> list:
    values = payload.get(key)
    if not isinstance(values, list) or not values:
        raise ValueError(f"missing_{key.lower()}_records")
    return values


def collect_lta(directory: Path):
    key = os.environ["LTA_ACCOUNT_KEY"]
    pages, artifacts = [], []
    # DataMall documents a 500-row page and the $skip query parameter.
    for offset in range(0, 50_000, 500):
        url = LTA_URL if offset == 0 else f"{LTA_URL}?$skip={offset}"
        payload, raw, received = get_json(url, {"AccountKey": key})
        artifacts.append({**archive(directory, f"lta-{offset}", raw), "retrieved_at": received.isoformat()})
        values = payload.get("value")
        if not isinstance(values, list) or (not values and offset == 0):
            raise ValueError("missing_value_records")
        if not values:
            return pages, artifacts
        pages.append((values, received))
        if len(values) < 500:
            return pages, artifacts
    raise ValueError("lta_pagination_limit")


def collect_ura(directory: Path, include_rates: bool):
    key = os.environ["URA_ACCESS_KEY"]
    token_payload, _, _ = get_json(URA_ROOT + "/insertNewToken/v1", {"AccessKey": key})
    if token_payload.get("Status") != "Success" or not token_payload.get("Result"):
        raise ValueError("ura_token_failed")
    # Never archive or print a token response: Result is a secret.
    headers = {"AccessKey": key, "Token": token_payload["Result"]}
    url = URA_ROOT + "/invokeUraDS/v1?service=Car_Park_Availability"
    payload, raw, received = get_json(url, headers)
    artifacts = [{**archive(directory, "ura-availability", raw), "retrieved_at": received.isoformat()}]
    if payload.get("Status") != "Success":
        raise ValueError("ura_availability_failed")
    records = require_list(payload, "Result")
    rate_count = None
    if include_rates:
        url = URA_ROOT + "/invokeUraDS/v1?service=Car_Park_Details"
        details, raw, details_received = get_json(url, headers)
        artifacts.append({**archive(directory, "ura-details-rates", raw), "retrieved_at": details_received.isoformat()})
        if details.get("Status") != "Success":
            raise ValueError("ura_details_failed")
        rate_count = len(require_list(details, "Result"))
    return [(records, received)], artifacts, rate_count


def normalize_pages(pages: list[tuple[list, datetime]], feed: str):
    """Keep agency + feed provenance. Provider update time and capacity stay unknown."""
    rows, rejected, seen, conflicts = [], [], {}, set()
    if feed not in {"lta_datamall", "ura_direct"}:
        raise ValueError("unknown_feed")
    for records, received in pages:
        for record in records:
            try:
                if not isinstance(record, dict):
                    raise ValueError("invalid_record")
                if feed == "lta_datamall":
                    agency = str(record["Agency"]).strip().upper()
                    code = str(record["CarParkID"]).strip().upper()
                    kind = str(record["LotType"]).strip().upper()
                    available = count(record["AvailableLots"])
                    if agency not in {"HDB", "LTA", "URA"}:
                        raise ValueError("unknown_agency")
                    if kind not in {"C", "H", "Y"}:
                        raise ValueError("unknown_lot_type")
                else:
                    agency = "URA"
                    code = str(record["carparkNo"]).strip().upper()
                    kind = str(record["lotType"]).strip().upper()
                    available = count(record["lotsAvailable"])
                    if kind not in {"C", "M", "H"}:
                        raise ValueError("unknown_lot_type")
                if not re.fullmatch(r"[A-Z0-9]+", code):
                    raise ValueError("invalid_carpark_id")
                row = {"feed": feed, "agency": agency, "carpark_id": code,
                       "lot_type": kind, "retrieved_at": received.astimezone(timezone.utc).isoformat(),
                       "lots_available": available, "source_updated_at": None,
                       "total_lots": None, "attributes": record}
                identity = (agency, code, kind)
                if identity in seen:
                    if seen[identity]["lots_available"] != available:
                        conflicts.add(identity)
                        rejected.append({"reason": "conflicting_duplicate", "record": record})
                else:
                    seen[identity] = row
                    rows.append(row)
            except (KeyError, TypeError, ValueError) as exc:
                rejected.append({"reason": str(exc), "record": record})
    rows = [row for row in rows if (row["agency"], row["carpark_id"], row["lot_type"]) not in conflicts]
    return rows, rejected


def load_postgres(manifest: dict, rows: list[dict], metadata: list[dict] | None = None,
                  rate_directory: Path | None = None):
    import psycopg
    from psycopg.types.json import Jsonb

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")
    with psycopg.connect(db_url, prepare_threshold=None, connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO parking_data.ingestion_runs
                (run_id, retrieved_at, query_time, manifest) VALUES (%s,%s,NULL,%s)
                ON CONFLICT (run_id) DO NOTHING""",
                (manifest["run_id"], manifest["retrieved_at"], Jsonb(manifest)))
            cursor.executemany("""INSERT INTO parking_data.carpark_identities
                (agency,carpark_id,display_name,name_source,metadata_retrieved_at)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (agency,carpark_id) DO UPDATE
                SET display_name=EXCLUDED.display_name,
                    name_source=EXCLUDED.name_source,
                    metadata_retrieved_at=EXCLUDED.metadata_retrieved_at
                WHERE EXCLUDED.display_name IS NOT NULL
                  AND (carpark_identities.metadata_retrieved_at IS NULL
                       OR carpark_identities.metadata_retrieved_at < EXCLUDED.metadata_retrieved_at)""",
                [(r["agency"], r["carpark_id"],
                  (str(r["attributes"].get("Development", "")).strip() or None)
                  if r["agency"] == "LTA" else None,
                  "lta_datamall" if r["agency"] == "LTA" else None,
                  r["retrieved_at"] if r["agency"] == "LTA" else None) for r in rows])
            cursor.executemany("""INSERT INTO parking_data.source_carpark_codes
                (feed,source_agency,source_code,agency,carpark_id,match_method)
                VALUES (%s,%s,%s,%s,%s,'exact_agency_code')
                ON CONFLICT DO NOTHING""",
                [(r["feed"], r["agency"], r["carpark_id"], r["agency"], r["carpark_id"])
                 for r in rows])
            cursor.executemany("""INSERT INTO parking_data.provider_availability_snapshots
                (run_id,feed,agency,carpark_id,lot_type,retrieved_at,lots_available,attributes)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (run_id,agency,carpark_id,lot_type) DO NOTHING""",
                [(manifest["run_id"], r["feed"], r["agency"], r["carpark_id"], r["lot_type"],
                  r["retrieved_at"], r["lots_available"], Jsonb(r["attributes"])) for r in rows])
            if metadata is not None:
                from metadata_cleaner import load_metadata
                load_metadata(cursor, metadata)
            if rate_directory is not None:
                from refresh_pricing import load_ura_pricing
                manifest['pricing_load'] = load_ura_pricing(cursor, rate_directory)
            cursor.execute('UPDATE parking_data.ingestion_runs SET manifest=%s WHERE run_id=%s',
                           (Jsonb({**manifest,'status':'loaded'}),manifest['run_id']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=["lta", "ura"], required=True)
    parser.add_argument("--include-rates", action="store_true", help="Archive URA details/rates too")
    parser.add_argument("--load", action="store_true", help="Load snapshots into Postgres via DATABASE_URL")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "data")
    args = parser.parse_args()
    try:
        load_local_env()
    except ValueError as exc:
        parser.error(str(exc))
    if args.include_rates and args.provider != "ura":
        parser.error("--include-rates applies only to URA")
    needed = "LTA_ACCOUNT_KEY" if args.provider == "lta" else "URA_ACCESS_KEY"
    if not os.environ.get(needed):
        parser.error(f"{needed} is not set; request the provider key first")
    if args.load and not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL is not set")
    directory = args.output / str(uuid.uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"run_id": directory.name, "provider": args.provider, "status": "started"}
    try:
        if args.provider == "lta":
            pages, artifacts = collect_lta(directory)
            rate_count = None
        else:
            pages, artifacts, rate_count = collect_ura(directory, args.include_rates)
        feed = "lta_datamall" if args.provider == "lta" else "ura_direct"
        rows, rejected = normalize_pages(pages, feed)
        if not rows:
            raise ValueError("no_accepted_observations")
        manifest.update(status="collected", retrieved_at=max(t for _, t in pages).isoformat(),
                        pages=len(pages), accepted=len(rows), rejected=len(rejected),
                        by_agency={agency: sum(r["agency"] == agency for r in rows)
                                   for agency in sorted({r["agency"] for r in rows})},
                        rate_records=rate_count, raw=artifacts)
        (directory / "rejected.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
        with (directory / "observations.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            writer.writerows({key: row[key] for key in FIELDS} for row in rows)
        # Persist the collected manifest so the metadata pass can verify raw
        # archive checksums. The final status still records any later failure.
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        from metadata_cleaner import metadata_from_run, write_metadata
        _, metadata, metadata_rejected = metadata_from_run(directory)
        write_metadata(directory, metadata, metadata_rejected)
        manifest["metadata_records"] = len(metadata)
        if args.load:
            load_postgres(manifest, rows, metadata, directory if args.include_rates else None)
            manifest["status"] = "loaded"
    except Exception as exc:
        manifest.update(status="failed", error_type=type(exc).__name__)
        if isinstance(exc, HTTPError):
            manifest["http_status"] = exc.code
        detail = f"HTTP {exc.code}" if isinstance(exc, HTTPError) else type(exc).__name__
        raise SystemExit(f"Provider collection failed ({detail}); see manifest and configuration.") from None
    finally:
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "raw"}, indent=2))
    print(f"Artifacts: {directory.resolve()}")


if __name__ == "__main__":
    main()
