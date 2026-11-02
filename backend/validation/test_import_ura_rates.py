from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'data-pipeline'))

import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from import_ura_rates import parse_day, parse_time, prepare, read_verified_details, sql


class RateParsingTests(unittest.TestCase):
    def test_per_unit_rate_is_exact_cents(self):
        self.assertEqual(parse_day("$0.65", "30 mins"), (65, 30, "per_unit"))
        self.assertEqual(parse_day("$0.01", "3 mins"), (1, 3, "per_unit"))

    def test_free_and_long_period_rows_require_review(self):
        self.assertEqual(parse_day("$0.00", "0 mins"), (0, 0, "zero_zero_review"))
        self.assertEqual(parse_day("$5.00", "510 mins"), (500, 510, "long_period_review"))

    def test_missing_or_invalid_rates_are_not_prices(self):
        self.assertEqual(parse_day("", ""), (None, None, "missing"))
        self.assertEqual(parse_day("$1.20", "0 mins"), (120, 0, "invalid"))
        self.assertEqual(parse_day("$1.20", "n/a"), (None, None, "invalid"))

    def test_time_and_sql_escaping(self):
        self.assertEqual(parse_time("12.00 AM"), "00:00:00")
        self.assertEqual(parse_time("10.30 PM"), "22:30:00")
        self.assertIsNone(parse_time("13.00 PM"))
        self.assertEqual(sql("O'Brien"), "'O''Brien'")
        with self.assertRaises(ValueError):
            sql("bad\x00input")

    def test_archive_checksum_is_checked_before_import(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = json.dumps({"Status": "Success", "Result": []}).encode()
            (root / "ura-details-rates.json.gz").write_bytes(gzip.compress(raw))
            manifest = {
                "run_id": "00000000-0000-0000-0000-000000000001",
                "provider": "ura", "status": "collected", "rate_records": 0,
                "raw": [{"path": str(root / "ura-details-rates.json.gz"),
                         "sha256": hashlib.sha256(raw).hexdigest()}],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(read_verified_details(root)[1], [])
            manifest["raw"][0]["sha256"] = "0" * 64
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "checksum"):
                read_verified_details(root)

    def test_draft_batch_is_generated_once_from_verified_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            run = root / "run"
            run.mkdir()
            record = {
                "ppCode": "A0004", "ppName": "ALIWAL ST", "vehCat": "Car",
                "parkingSystem": "C", "parkCapacity": 69,
                "startTime": "08.30 AM", "endTime": "05.00 PM",
                "weekdayRate": "$0.60", "weekdayMin": "30 mins",
                "satdayRate": "$0.60", "satdayMin": "30 mins",
                "sunPHRate": "$0.00", "sunPHMin": "0 mins",
            }
            raw = json.dumps({"Status": "Success", "Result": [record]}).encode()
            artifact = run / "ura-details-rates.json.gz"
            artifact.write_bytes(gzip.compress(raw))
            manifest = {
                "run_id": "00000000-0000-0000-0000-000000000001",
                "provider": "ura", "status": "collected", "rate_records": 1,
                "retrieved_at": "2026-09-28T12:00:00+00:00",
                "raw": [{"path": str(artifact), "sha256": hashlib.sha256(raw).hexdigest()}],
            }
            (run / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            output = root / "sql"
            result = prepare(run, output)
            self.assertEqual(result["rate_rows"], 1)
            self.assertEqual(result["interpretation_counts"]["zero_zero_review"], 1)
            self.assertIn("INSERT INTO parking_data.rate_schedules",
                          (output / "20-drafts.sql").read_text(encoding="utf-8"))
            with self.assertRaisesRegex(ValueError, "empty"):
                prepare(run, output)


if __name__ == "__main__":
    unittest.main()
