"""Verify and stage an archived URA Car_Park_Details response.

Creates SQL batches for the private Supabase schema. Parsed fields are evidence,
not approved price quotes. Never reads or writes URA credentials or tokens.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path
import re


CODE = re.compile(r"[A-Z0-9]+\Z")
MONEY = re.compile(r"\$(\d+)(?:\.(\d{1,2}))?\Z")
MINUTES = re.compile(r"(\d+)\s*mins?\Z", re.IGNORECASE)
TIME = re.compile(r"(0?[1-9]|1[0-2])\.(\d{2})\s+(AM|PM)\Z", re.IGNORECASE)
DAY_FIELDS = {
    "weekday": ("weekdayRate", "weekdayMin"),
    "saturday": ("satdayRate", "satdayMin"),
    "sunday_ph": ("sunPHRate", "sunPHMin"),
}
VEHICLES = {"Car", "Motorcycle", "Heavy Vehicle"}


def sql(value):
    """Literal for an offline SQL import file with standard_conforming_strings on."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, int):
        return str(value)
    if "\x00" in str(value):
        raise ValueError("NUL in provider data")
    return "'" + str(value).replace("'", "''") + "'"


def sql_json(value):
    return sql(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) + "::jsonb"


def sql_array(values):
    return "ARRAY[" + ",".join(sql(v) for v in values) + "]::text[]"


def parse_time(value):
    match = TIME.fullmatch(str(value).strip())
    if not match or int(match[2]) > 59:
        return None
    hour = int(match[1]) % 12 + (12 if match[3].upper() == "PM" else 0)
    return f"{hour:02d}:{int(match[2]):02d}:00"


def parse_day(rate, minutes):
    rate, minutes = str(rate or "").strip(), str(minutes or "").strip()
    if not rate and not minutes:
        return None, None, "missing"
    money, unit = MONEY.fullmatch(rate), MINUTES.fullmatch(minutes)
    if money is None or unit is None:
        return None, None, "invalid"
    cents = 100 * int(money[1]) + int((money[2] or "0").ljust(2, "0"))
    length = int(unit[1])
    if cents == 0 and length == 0:
        return cents, length, "zero_zero_review"
    if length == 0:
        return cents, length, "invalid"
    if length > 60:
        return cents, length, "long_period_review"
    return cents, length, "per_unit"


def read_verified_details(run_directory: Path):
    manifest = json.loads((run_directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("provider") != "ura" or manifest.get("status") not in {"collected", "loaded"}:
        raise ValueError("not a successful URA run")
    artifacts = {Path(entry["path"]).name: entry for entry in manifest["raw"]}
    filename = "ura-details-rates.json.gz"
    if filename not in artifacts:
        raise ValueError("URA rate artifact missing")
    raw = gzip.decompress((run_directory / filename).read_bytes())
    if hashlib.sha256(raw).hexdigest() != artifacts[filename]["sha256"]:
        raise ValueError("URA rate artifact checksum mismatch")
    payload = json.loads(raw)
    if payload.get("Status") != "Success" or not isinstance(payload.get("Result"), list):
        raise ValueError("URA rate payload failed")
    if len(payload["Result"]) != manifest.get("rate_records"):
        raise ValueError("URA rate count differs from manifest")
    return manifest, payload["Result"]


def prepare(run_directory: Path, output: Path, batch_size: int = 250):
    manifest, details = read_verified_details(run_directory)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError("output directory must be empty to avoid stale SQL batches")
    run_id = manifest["run_id"]
    retrieved_at = manifest["retrieved_at"]
    identities = {}
    rows = []
    day_rules = []
    counts = {}
    for row_number, raw in enumerate(details):
        code = str(raw.get("ppCode", "")).strip().upper()
        category = str(raw.get("vehCat", "")).strip()
        if not CODE.fullmatch(code) or category not in VEHICLES:
            raise ValueError(f"unrecognized code or vehicle category at row {row_number}")
        name = str(raw.get("ppName", "")).strip()
        if not name:
            raise ValueError(f"missing name at row {row_number}")
        identities.setdefault(code, name)
        start, end = parse_time(raw.get("startTime")), parse_time(raw.get("endTime"))
        flags = []
        if start is None or end is None:
            flags.append("invalid_time")
        elif start == end:
            flags.append("equal_start_end_review")
        capacity = raw.get("parkCapacity")
        if isinstance(capacity, bool) or not str(capacity).isdigit():
            capacity = None
            flags.append("invalid_capacity")
        else:
            capacity = int(capacity)
        for day, (rate_key, minute_key) in DAY_FIELDS.items():
            cents, minutes, interpretation = parse_day(raw.get(rate_key), raw.get(minute_key))
            day_rules.append((run_id, row_number, day, cents, minutes, interpretation))
            counts[interpretation] = counts.get(interpretation, 0) + 1
            if interpretation != "per_unit":
                flags.append(day + "_" + interpretation)
        rows.append((run_id, row_number, code, name, category,
                     str(raw.get("parkingSystem", "")).strip() or None,
                     capacity, start, end, flags, raw))

    names = [("URA", code, name, "ura_details", retrieved_at) for code, name in identities.items()]
    statement = """SET standard_conforming_strings = on;
INSERT INTO parking_data.carpark_identities
  (agency, carpark_id, display_name, name_source, metadata_retrieved_at) VALUES
""" + ",\n".join("(" + ",".join(sql(x) for x in item) + ")" for item in names) + """
ON CONFLICT (agency, carpark_id) DO UPDATE
SET display_name = EXCLUDED.display_name,
    name_source = EXCLUDED.name_source,
    metadata_retrieved_at = EXCLUDED.metadata_retrieved_at
WHERE parking_data.carpark_identities.metadata_retrieved_at IS NULL
   OR parking_data.carpark_identities.metadata_retrieved_at < EXCLUDED.metadata_retrieved_at;
INSERT INTO parking_data.source_carpark_codes
  (feed, source_agency, source_code, agency, carpark_id, match_method)
SELECT 'ura_direct', 'URA', carpark_id, 'URA', carpark_id, 'exact_agency_code'
FROM parking_data.carpark_identities WHERE agency = 'URA'
ON CONFLICT DO NOTHING;
"""
    (output / "00-identities.sql").write_text(statement, encoding="utf-8")

    for start_index in range(0, len(rows), batch_size):
        subset = rows[start_index:start_index + batch_size]
        subset_days = day_rules[start_index * 3:(start_index + len(subset)) * 3]
        row_values = []
        for run, number, code, name, category, system, capacity, start, end, flags, raw in subset:
            row_values.append("(" + ",".join([
                sql(run), sql(number), sql(code), sql(name), sql(category), sql(system),
                sql(capacity), sql(start) + "::time" if start else "NULL",
                sql(end) + "::time" if end else "NULL", sql_array(flags), sql_json(raw),
            ]) + ")")
        day_values = ["(" + ",".join(sql(x) for x in item) + ")" for item in subset_days]
        batch = """SET standard_conforming_strings = on;
BEGIN;
INSERT INTO parking_data.ura_rate_rows
  (run_id, row_number, pp_code, pp_name, vehicle_category, parking_system,
   park_capacity, start_time, end_time, parse_flags, raw) VALUES
""" + ",\n".join(row_values) + """
ON CONFLICT (run_id, row_number) DO NOTHING;
INSERT INTO parking_data.ura_rate_day_rules
  (run_id, row_number, day_type, amount_cents, unit_minutes, interpretation) VALUES
""" + ",\n".join(day_values) + """
ON CONFLICT (run_id, row_number, day_type) DO NOTHING;
COMMIT;
"""
        (output / f"10-rates-{start_index // batch_size:03d}.sql").write_text(batch, encoding="utf-8")
    drafts = """BEGIN;
INSERT INTO parking_data.rate_schedules
    (agency, carpark_id, source, source_run_id, source_url, valid_from,
     review_status, review_note)
SELECT 'URA', r.pp_code, 'ura_details', r.run_id,
       'https://eservice.ura.gov.sg/maps/api/', ir.retrieved_at,
       'pending_review',
       'Draft from captured URA data. Per-unit entries only; free/zero and long-period entries require interpretation. Billing method, grace period, time-window coverage and effective date require review.'
FROM parking_data.ura_rate_rows r
JOIN parking_data.ingestion_runs ir ON ir.run_id = r.run_id
WHERE r.vehicle_category = 'Car' AND r.run_id = """ + sql(run_id) + """::uuid
GROUP BY r.run_id, r.pp_code, ir.retrieved_at
ON CONFLICT DO NOTHING;
INSERT INTO parking_data.rate_schedule_rules
    (schedule_id, day_type, start_time, end_time, rule_kind,
     amount_cents, unit_minutes, description, priority,
     source_run_id, source_row_number, source_day_type)
SELECT s.schedule_id, d.day_type, r.start_time, r.end_time,
       'per_unit', d.amount_cents, d.unit_minutes,
       'Unverified URA per-unit rule; see linked source row', 100,
       d.run_id, d.row_number, d.day_type
FROM parking_data.ura_rate_rows r
JOIN parking_data.ura_rate_day_rules d
  ON d.run_id = r.run_id AND d.row_number = r.row_number
JOIN parking_data.rate_schedules s
  ON s.source = 'ura_details' AND s.source_run_id = r.run_id
 AND s.agency = 'URA' AND s.carpark_id = r.pp_code
WHERE r.vehicle_category = 'Car' AND d.interpretation = 'per_unit'
  AND r.start_time IS NOT NULL AND r.end_time IS NOT NULL
  AND r.run_id = """ + sql(run_id) + """::uuid
ON CONFLICT DO NOTHING;
COMMIT;
"""
    (output / "20-drafts.sql").write_text(drafts, encoding="utf-8")
    return {"rate_rows": len(rows), "day_rules": len(day_rules),
            "ura_codes": len(identities), "interpretation_counts": counts,
            "batches": (len(rows) + batch_size - 1) // batch_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    parser.add_argument("output_directory", type=Path)
    parser.add_argument("--batch-size", type=int, default=250)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 500:
        parser.error("batch size must be 1-500")
    print(json.dumps(prepare(args.run_directory, args.output_directory, args.batch_size), indent=2))


if __name__ == "__main__":
    main()
