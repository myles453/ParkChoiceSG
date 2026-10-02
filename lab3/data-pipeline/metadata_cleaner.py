"""Normalize archived carpark metadata without inventing entrances or capacity.

SVY21 easting/northing (EPSG:3414) becomes WGS84 longitude/latitude
(EPSG:4326). All URA geometry points survive. Repeated tariff rows are not
additional lots. A conflicting field is quarantined independently of others.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path, PureWindowsPath

from pyproj import Transformer
from pyproj.exceptions import ProjError

from puller import count, timestamp

TRANSFORMER = Transformer.from_crs(3414, 4326, always_xy=True)
VERSION = "metadata-1"
MAX_METADATA_AGE = timedelta(days=30)


def number(value):
    if isinstance(value, bool):
        raise ValueError("invalid_coordinate")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError("invalid_coordinate")
    return result


def point(first, second, crs):
    if crs == "EPSG:3414":
        longitude, latitude = TRANSFORMER.transform(number(first), number(second), errcheck=True)
    elif crs == "EPSG:4326":
        latitude, longitude = number(first), number(second)
    else:
        raise ValueError("unsupported_crs")
    # Broad Singapore extent, including offshore carparks. Reject wrong axis
    # order, projected metres mistaken for degrees, NaN and sentinel zeroes.
    if not (1.15 <= latitude <= 1.50 and 103.55 <= longitude <= 104.15):
        raise ValueError("coordinate_outside_singapore")
    return {"latitude": round(latitude, 7), "longitude": round(longitude, 7)}


def locations(raw, source):
    flags, points = [], []
    try:
        if source == "hdb_reference":
            candidates = [(raw.get("x_coord"), raw.get("y_coord"))]
            crs = "EPSG:3414"
        elif source == "lta_datamall":
            values = str(raw.get("Location", "")).split()
            if len(values) != 2:
                raise ValueError("location_missing_or_invalid")
            candidates, crs = [values], "EPSG:4326"
        else:
            geometries = raw.get("geometries")
            if not isinstance(geometries, list) or not geometries:
                raise ValueError("location_missing_or_invalid")
            candidates, crs = [], "EPSG:3414"
            for geometry in geometries:
                values = str(geometry.get("coordinates", "")).split(",") if isinstance(geometry, dict) else []
                if len(values) != 2:
                    flags.append("invalid_geometry")
                else:
                    candidates.append(values)
        for values in candidates:
            try:
                cleaned = point(*values, crs)
                if cleaned not in points:
                    points.append(cleaned)
            except (TypeError, ValueError, OverflowError, ProjError):
                flags.append("invalid_geometry")
    except (TypeError, ValueError):
        flags.append("location_missing_or_invalid")
    # Partial geometries cannot safely substitute for the complete source set.
    if flags:
        return [], "invalid", sorted(set(flags)), crs if 'crs' in locals() else None
    if not points:
        return [], "missing", ["location_missing"], crs
    points.sort(key=lambda p: (p["latitude"], p["longitude"]))
    status = "single_point" if len(points) == 1 else "multiple_points"
    return points, status, flags, crs


def clean_metadata(records, source, run_id, captured_at):
    groups, rejected = defaultdict(list), []
    for raw in records:
        try:
            if not isinstance(raw, dict):
                raise ValueError("invalid_metadata_record")
            if source == "hdb_reference":
                agency, code = "HDB", str(raw["car_park_no"]).strip().upper()
            elif source == "lta_datamall":
                agency, code = str(raw["Agency"]).strip().upper(), str(raw["CarParkID"]).strip().upper()
                if raw.get("LotType") != "C":
                    continue
            elif source == "ura_direct":
                agency, code = "URA", str(raw["carparkNo"]).strip().upper()
                if raw.get("lotType") != "C":
                    continue
            elif source == "ura_details":
                agency, code = "URA", str(raw["ppCode"]).strip().upper()
                if raw.get("vehCat") != "Car":
                    continue
            else:
                raise ValueError("unknown_metadata_source")
            if agency not in {"HDB", "URA", "LTA"} or not re.fullmatch(r"[A-Z0-9]+", code):
                raise ValueError("invalid_metadata_identity")
            groups[(agency, code)].append(raw)
        except (KeyError, TypeError, ValueError) as exc:
            rejected.append({"reason": str(exc), "record": raw})
    rows = []
    for (agency, code), group in sorted(groups.items()):
        flags, geometry_sets, crs = [], set(), None
        for raw in group:
            points, status, problems, crs = locations(raw, source)
            flags.extend(problems)
            geometry_sets.add(json.dumps(points, sort_keys=True))
        if len(geometry_sets) != 1:
            points, status = [], "conflicting"
            flags.append("conflicting_locations")
        else:
            points = json.loads(next(iter(geometry_sets)))
            status = "invalid" if flags else ("multiple_points" if len(points) > 1 else "single_point")
        capacity, capacity_status = None, "not_published"
        if source == "ura_details":
            capacities = set()
            for raw in group:
                try:
                    capacities.add(count(raw.get("parkCapacity")))
                except ValueError:
                    flags.append("invalid_capacity")
            if "invalid_capacity" in flags or len(capacities) != 1:
                capacity_status = "conflicting_or_invalid"
                flags.append("capacity_requires_review")
            else:
                capacity = next(iter(capacities))
                capacity_status = "published_metadata" if capacity > 0 else "zero_capacity_review"
                if capacity == 0:
                    capacity = None
                    flags.append("zero_capacity")
        name_key = {"hdb_reference": "address", "lta_datamall": "Development", "ura_details": "ppName"}.get(source)
        names = {str(raw.get(name_key, "")).strip() for raw in group} if name_key else set()
        names.discard("")
        name = next(iter(names)) if len(names) == 1 else None
        if len(names) > 1:
            flags.append("conflicting_names")
        height = None
        raw = group[0]
        if source == "hdb_reference":
            try:
                candidate = number(raw.get("gantry_height"))
                if 0 < candidate <= 10:
                    height = candidate
                elif candidate != 0:
                    flags.append("invalid_gantry_height")
            except (ValueError, TypeError):
                flags.append("invalid_gantry_height")
        rows.append({"run_id": run_id, "source": source, "agency": agency, "carpark_id": code,
                     "captured_at": timestamp(captured_at).isoformat(), "display_name": name,
                     "address": name if source == "hdb_reference" else None,
                     "source_crs": crs, "location_points": points, "location_status": status,
                     "latitude": points[0]["latitude"] if len(points) == 1 else None,
                     "longitude": points[0]["longitude"] if len(points) == 1 else None,
                     "car_capacity": capacity, "capacity_status": capacity_status,
                     "carpark_type": raw.get("car_park_type") if source == "hdb_reference" else None,
                     "gantry_height_m": height,
                     "quality_flags": sorted(set(flags)), "source_row_count": len(group),
                     "cleaner_version": VERSION})
    return rows, rejected


def read_run(directory):
    """Verify compressed-source checksums before re-cleaning; never read .env."""
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") not in {"collected", "loaded"}:
        raise ValueError("not_successful_run")
    artifacts = []
    for item in manifest.get("raw", []):
        name = item.get("file") or PureWindowsPath(item["path"]).name
        if Path(name).name != name:
            raise ValueError("unsafe_archive_path")
        raw = gzip.decompress((directory / name).read_bytes())
        # archive() hashes the original uncompressed response.
        if hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise ValueError("archive_checksum_mismatch")
        artifacts.append((name, json.loads(raw), item.get("retrieved_at")))
    return manifest, artifacts


def metadata_from_run(directory):
    manifest, artifacts = read_run(directory)
    collected, rejected = [], []
    grouped = defaultdict(list)
    captures, approximate = {}, set()
    for name, payload, artifact_time in artifacts:
        if name.startswith("reference-"):
            source, records = "hdb_reference", payload["result"]["records"]
            captured = manifest["reference_retrieved_at"]
        elif name.startswith("lta-"):
            source, records, captured = "lta_datamall", payload["value"], artifact_time or manifest["retrieved_at"]
        elif name.startswith("ura-details"):
            source, records, captured = "ura_details", payload["Result"], artifact_time or manifest["retrieved_at"]
        elif name.startswith("ura-availability"):
            source, records, captured = "ura_direct", payload["Result"], artifact_time or manifest["retrieved_at"]
        else:
            continue
        if source != "hdb_reference" and artifact_time is None:
            approximate.add(source)
        grouped[source].extend(records)
        captures[source] = max(captures.get(source, captured), captured)
    for source, records in grouped.items():
        rows, problems = clean_metadata(records, source, manifest["run_id"], captures[source])
        if source in approximate:
            for row in rows:
                row["quality_flags"].append("capture_time_approximate")
        collected.extend(rows)
        rejected.extend(problems)
    return manifest, collected, rejected


def write_metadata(directory, rows, rejected):
    (directory / "metadata.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    (directory / "metadata-rejected.json").write_text(json.dumps(rejected, indent=2), encoding="utf-8")
    fields = ["agency", "carpark_id", "source", "captured_at", "display_name", "latitude", "longitude",
              "location_status", "car_capacity", "capacity_status", "gantry_height_m", "quality_flags"]
    with (directory / "metadata.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: "|".join(row[k]) if k == "quality_flags" else row[k] for k in fields})


def load_metadata(cursor, rows):
    from psycopg.types.json import Jsonb
    cursor.executemany("""INSERT INTO parking_data.carpark_identities (agency,carpark_id)
        VALUES (%s,%s) ON CONFLICT DO NOTHING""", [(r["agency"], r["carpark_id"]) for r in rows])
    cursor.executemany("""INSERT INTO parking_data.carpark_metadata_evidence
        (run_id,source,agency,carpark_id,captured_at,display_name,address,source_crs,
         location_points,location_status,latitude,longitude,car_capacity,capacity_status,
         carpark_type,gantry_height_m,quality_flags,source_row_count,cleaner_version)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (run_id,source,agency,carpark_id) DO NOTHING""",
        [(r["run_id"], r["source"], r["agency"], r["carpark_id"], r["captured_at"], r["display_name"],
          r["address"], r["source_crs"], Jsonb(r["location_points"]), r["location_status"], r["latitude"],
          r["longitude"], r["car_capacity"], r["capacity_status"], r["carpark_type"], r["gantry_height_m"],
          r["quality_flags"], r["source_row_count"], r["cleaner_version"]) for r in rows])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("--load", action="store_true")
    args = parser.parse_args()
    manifest, rows, rejected = metadata_from_run(args.run_directory)
    write_metadata(args.run_directory, rows, rejected)
    if args.load:
        import os
        import psycopg
        from psycopg.types.json import Jsonb
        from provider_puller import load_local_env
        load_local_env()
        if not os.environ.get("DATABASE_URL"):
            parser.error("DATABASE_URL is not set")
        try:
            with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None, connect_timeout=15) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("""INSERT INTO parking_data.ingestion_runs
                        (run_id,retrieved_at,query_time,manifest) VALUES (%s,%s,%s,%s)
                        ON CONFLICT DO NOTHING""", (manifest["run_id"], manifest["retrieved_at"],
                                                  manifest.get("query_time"), Jsonb(manifest)))
                    load_metadata(cursor, rows)
        except Exception as exc:
            raise SystemExit(f"Metadata load failed ({type(exc).__name__}); check schema/configuration.") from None
    print(json.dumps({"metadata_records": len(rows), "rejected": len(rejected),
                      "multiple_point_carparks": sum(r["location_status"] == "multiple_points" for r in rows),
                      "unusable_locations": sum(r["location_status"] not in {"single_point", "multiple_points"} for r in rows)}, indent=2))


if __name__ == "__main__":
    main()
