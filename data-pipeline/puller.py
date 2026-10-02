"""HDB ingestion pilot: preserve raw responses, validate observations, optionally load Postgres.

Run `python puller.py --help`. No credentials are needed for local collection.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import uuid

SGT = timezone(timedelta(hours=8))
UTC = timezone.utc
LIVE_URL = "https://api.data.gov.sg/v1/transport/carpark-availability"
REFERENCE_URL = "https://data.gov.sg/api/action/datastore_search"
RESOURCE = "d_23f946fa557947f93a8043bbef41dd09"
FIELDS = ["source", "carpark_id", "lot_type", "source_updated_at", "retrieved_at",
          "lots_available", "total_lots", "quality_flags", "training_eligible"]


def timestamp(value: str) -> datetime:
    """HDB's timezone-less update_datetime is interpreted as Singapore local time."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("missing_timestamp")
    result = datetime.fromisoformat(value)
    return (result.replace(tzinfo=SGT) if result.tzinfo is None else result).astimezone(UTC)


def count(value) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"\d+", str(value)):
        raise ValueError("invalid_count")
    return int(value)


def get_json(url: str, headers: dict[str, str] | None = None) -> tuple[dict, bytes, datetime]:
    """Bounded retries; never treat HTTP success as proof of a valid payload."""
    for attempt in range(3):
        try:
            request_headers = {"Accept": "application/json",
                               "User-Agent": "ParkChoiceSG-Lab3-data-pipeline"}
            request_headers.update(headers or {})
            with urlopen(Request(url, headers=request_headers), timeout=30) as response:
                raw = response.read()
            return json.loads(raw), raw, datetime.now(UTC)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            retry_after = exc.headers.get("Retry-After", "")
            delay = min(int(retry_after), 30) if retry_after.isdigit() else 2 ** (attempt + 1)
            time.sleep(delay)
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("request_failed")


def archive(directory: Path, name: str, raw: bytes) -> dict:
    path = directory / (name + ".json.gz")
    with gzip.open(path, "wb") as output:
        output.write(raw)
    return {"path": str(path.resolve()), "file": path.name, "sha256": hashlib.sha256(raw).hexdigest()}


def normalize(payload: dict, retrieved_at: datetime, reference_ids: set[str],
              target_time: datetime | None = None, stale_minutes: int = 15):
    """Keep source observations separate by carpark/lot type/time. Quarantine bad rows.

    Repeated identical source observations are not new independent training samples.
    Conflicting duplicates inside a response are excluded rather than arbitrarily chosen.
    """
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ValueError("missing_items")
    rows, rejected, seen, conflicts = [], [], {}, set()
    comparison_time = target_time or retrieved_at
    for item in items:
        parks = item.get("carpark_data")
        if not isinstance(parks, list) or not parks:
            raise ValueError("missing_carpark_data")
        for park in parks:
            try:
                code = park["carpark_number"].strip().upper()
                if not re.fullmatch(r"[A-Z0-9]+", code):
                    raise ValueError("invalid_carpark_id")
                observed = timestamp(park["update_datetime"])
                if observed > comparison_time + timedelta(minutes=2):
                    raise ValueError("future_source_timestamp")
                lots = park["carpark_info"]
                if not isinstance(lots, list) or not lots:
                    raise ValueError("missing_lot_records")
            except (KeyError, TypeError, AttributeError, ValueError) as exc:
                rejected.append({"reason": str(exc), "record": park})
                continue
            for lot in lots:
                try:
                    available, total = count(lot["lots_available"]), count(lot["total_lots"])
                    kind = lot["lot_type"].strip().upper()
                    # Preserve provider codes. HDB live data uses Y as well as C/H;
                    # do not apply URA's M vocabulary to another provider silently.
                    if kind not in {"C", "M", "H", "Y"}:
                        raise ValueError("unknown_lot_type")
                    if available > total:
                        raise ValueError("available_exceeds_total")
                    flags = []
                    if code not in reference_ids:
                        flags.append("unmatched_reference")
                    if total == 0:
                        flags.append("zero_capacity")
                    if comparison_time - observed > timedelta(minutes=stale_minutes):
                        flags.append("stale_source")
                    row = dict(zip(FIELDS, ["hdb", code, kind, observed.isoformat(),
                               retrieved_at.isoformat(), available, total, flags, not flags]))
                    key = (code, kind, row["source_updated_at"])
                    if key in seen:
                        old = seen[key]
                        if (old["lots_available"], old["total_lots"]) != (available, total):
                            conflicts.add(key)
                            rejected.append({"reason": "conflicting_duplicate", "record": park})
                    else:
                        rows.append(row)
                        seen[key] = row
                except (KeyError, TypeError, AttributeError, ValueError) as exc:
                    rejected.append({"reason": str(exc), "record": {"carpark_number": code, "lot": lot}})
    rows = [r for r in rows if (r["carpark_id"], r["lot_type"], r["source_updated_at"]) not in conflicts]
    return rows, rejected


def collect_reference(directory: Path):
    records, artifacts, offset, total = [], [], 0, None
    while total is None or offset < total:
        url = REFERENCE_URL + "?" + urlencode({"resource_id": RESOURCE, "limit": 1000, "offset": offset})
        payload, raw, received = get_json(url)
        artifacts.append(archive(directory, f"reference-{offset}", raw))
        if payload.get("success") is not True:
            raise ValueError("reference_api_error")
        result = payload["result"]
        page = result["records"]
        total = int(result["total"])
        if not page:
            raise ValueError("reference_pagination_incomplete")
        records.extend(page)
        offset += len(page)
    ids = [r["car_park_no"].strip().upper() for r in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate_reference_id")
    return records, artifacts, received


def load_postgres(manifest: dict, rows: list[dict], references: list[dict], metadata: list[dict] | None = None):
    """One transaction: all rows commit or none do. Run schema.sql separately first."""
    import psycopg
    from psycopg.types.json import Jsonb
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL is not set")
    with psycopg.connect(db_url, prepare_threshold=None, connect_timeout=15) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO parking_data.ingestion_runs
                (run_id, retrieved_at, query_time, manifest) VALUES (%s,%s,%s,%s)
                ON CONFLICT (run_id) DO NOTHING""",
                (manifest["run_id"], manifest["retrieved_at"], manifest["query_time"], Jsonb(manifest)))
            cursor.executemany("""INSERT INTO parking_data.carparks
                (source, carpark_id, address, reference_data, reference_retrieved_at)
                VALUES ('hdb',%s,%s,%s,%s)
                ON CONFLICT (source,carpark_id) DO UPDATE SET address=EXCLUDED.address,
                reference_data=EXCLUDED.reference_data, reference_retrieved_at=EXCLUDED.reference_retrieved_at
                WHERE EXCLUDED.reference_retrieved_at >= carparks.reference_retrieved_at""",
                [(r["car_park_no"].strip().upper(), r.get("address"), Jsonb(r),
                  manifest["reference_retrieved_at"]) for r in references])
            cursor.executemany("""INSERT INTO parking_data.carpark_identities
                (agency,carpark_id,display_name,address,name_source,metadata_retrieved_at)
                VALUES ('HDB',%s,%s,%s,'hdb_reference',%s)
                ON CONFLICT (agency,carpark_id) DO UPDATE
                SET display_name=EXCLUDED.display_name,address=EXCLUDED.address,
                    name_source=EXCLUDED.name_source,
                    metadata_retrieved_at=EXCLUDED.metadata_retrieved_at
                WHERE carpark_identities.metadata_retrieved_at IS NULL
                   OR carpark_identities.metadata_retrieved_at < EXCLUDED.metadata_retrieved_at""",
                [(r["car_park_no"].strip().upper(), r.get("address"), r.get("address"),
                  manifest["reference_retrieved_at"]) for r in references])
            # Preserve live IDs that have no reference metadata. They remain
            # ineligible for strict model training but can be audited by code.
            cursor.executemany("""INSERT INTO parking_data.carpark_identities (agency,carpark_id)
                VALUES ('HDB',%s) ON CONFLICT DO NOTHING""",
                [(r["carpark_id"],) for r in rows])
            cursor.executemany("""INSERT INTO parking_data.source_carpark_codes
                (feed,source_agency,source_code,agency,carpark_id,match_method)
                VALUES ('hdb_direct','HDB',%s,'HDB',%s,'exact_agency_code')
                ON CONFLICT DO NOTHING""",
                [(r["carpark_id"], r["carpark_id"]) for r in rows])
            cursor.executemany("""INSERT INTO parking_data.hdb_observation_conflicts
                (run_id,source,carpark_id,lot_type,source_updated_at,retrieved_at,lots_available,total_lots)
                SELECT %s,a.source,a.carpark_id,a.lot_type,a.source_updated_at,%s,%s,%s
                FROM parking_data.availability_observations a
                WHERE (a.source,a.carpark_id,a.lot_type,a.source_updated_at)=(%s,%s,%s,%s)
                  AND (a.lots_available,a.total_lots)<>(%s,%s)
                ON CONFLICT DO NOTHING""",
                [(manifest["run_id"], r["retrieved_at"], r["lots_available"], r["total_lots"],
                  r["source"],r["carpark_id"],r["lot_type"],r["source_updated_at"],
                  r["lots_available"],r["total_lots"]) for r in rows])
            cursor.executemany("""INSERT INTO parking_data.availability_observations
                (source,carpark_id,lot_type,source_updated_at,first_retrieved_at,lots_available,
                 total_lots,quality_flags,training_eligible,run_id,first_live_retrieved_at,live_run_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (source,carpark_id,lot_type,source_updated_at) DO UPDATE SET
                  first_live_retrieved_at=EXCLUDED.first_live_retrieved_at,live_run_id=EXCLUDED.live_run_id
                WHERE EXCLUDED.live_run_id IS NOT NULL
                  AND (availability_observations.first_live_retrieved_at IS NULL
                       OR EXCLUDED.first_live_retrieved_at<availability_observations.first_live_retrieved_at)
                  AND (availability_observations.lots_available,availability_observations.total_lots)=
                      (EXCLUDED.lots_available,EXCLUDED.total_lots)""",
                [(r["source"], r["carpark_id"], r["lot_type"], r["source_updated_at"],
                  r["retrieved_at"], r["lots_available"], r["total_lots"], r["quality_flags"],
                  r["training_eligible"], manifest["run_id"],
                  r["retrieved_at"] if manifest["query_time"] is None else None,
                  manifest["run_id"] if manifest["query_time"] is None else None) for r in rows])
            if metadata is not None:
                from metadata_cleaner import load_metadata
                load_metadata(cursor, metadata)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "data")
    parser.add_argument("--at", help="Historical snapshot time, e.g. 2026-09-27T12:00:00+08:00")
    parser.add_argument("--load", action="store_true", help="Also load Postgres using DATABASE_URL")
    args = parser.parse_args()
    if args.load:
        from provider_puller import load_local_env
        load_local_env()
        if not os.environ.get("DATABASE_URL"):
            parser.error("DATABASE_URL is not set")
    target = timestamp(args.at) if args.at else None
    if target and target > datetime.now(UTC):
        parser.error("--at must be in the past")
    run_id = str(uuid.uuid4())
    directory = args.output / run_id
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {"run_id": run_id, "status": "started", "cleaner_version": "hdb-pilot-1",
                "stale_threshold_minutes": 15, "query_time": target.isoformat() if target else None}
    try:
        references, artifacts, ref_time = collect_reference(directory)
        url = LIVE_URL + ("?" + urlencode({"date_time": target.astimezone(SGT).isoformat()}) if target else "")
        payload, raw, received = get_json(url)
        artifacts.append(archive(directory, "availability", raw))
        manifest.update(retrieved_at=received.isoformat(), reference_retrieved_at=ref_time.isoformat(), raw=artifacts)
        rows, rejected = normalize(payload, received, {r["car_park_no"].strip().upper() for r in references}, target)
        (directory / "rejected.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
        with (directory / "observations.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            writer.writerows({**r, "quality_flags": "|".join(r["quality_flags"])} for r in rows)
        with (directory / "training-cars.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, FIELDS)
            writer.writeheader()
            writer.writerows({**r, "quality_flags": ""} for r in rows
                             if r["lot_type"] == "C" and r["training_eligible"])
        flags = {}
        for row in rows:
            for flag in row["quality_flags"]:
                flags[flag] = flags.get(flag, 0) + 1
        manifest.update(status="collected", reference_count=len(references), accepted=len(rows),
                        rejected=len(rejected), quality_flags=flags,
                        trainable_car_rows=sum(r["training_eligible"] and r["lot_type"] == "C" for r in rows))
        from metadata_cleaner import clean_metadata, write_metadata
        metadata, metadata_rejected = clean_metadata(references, "hdb_reference", run_id, ref_time.isoformat())
        write_metadata(directory, metadata, metadata_rejected)
        manifest["metadata_records"] = len(metadata)
        if args.load:
            load_postgres(manifest, rows, references, metadata)
            manifest["status"] = "loaded"
    except Exception as exc:
        # DB exceptions can include connection details. Do not print credentials or raw error text.
        manifest.update(status="failed", error_type=type(exc).__name__)
        raise SystemExit(f"Collection/load failed ({type(exc).__name__}); see local manifest and check configuration.") from None
    finally:
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k != "raw"}, indent=2))
    print(f"Artifacts: {directory.resolve()}")


if __name__ == "__main__":
    main()
