from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'data-pipeline'))

import unittest
from datetime import datetime, timezone
from puller import normalize, timestamp

NOW = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)


def payload(available="5", total="10", observed="2026-09-28T14:00:00", kinds=None):
    return {"items": [{"carpark_data": [{"carpark_number": "A1", "update_datetime": observed,
             "carpark_info": kinds or [{"lots_available": available, "total_lots": total, "lot_type": "C"}]}]}]}


class CleaningTests(unittest.TestCase):
    def test_singapore_timestamp(self):
        self.assertEqual(timestamp("2026-09-28T14:00:00"), NOW)

    def test_zero_availability_is_valid(self):
        rows, bad = normalize(payload("0"), NOW, {"A1"})
        self.assertFalse(bad)
        self.assertTrue(rows[0]["training_eligible"])

    def test_invalid_counts_quarantined(self):
        for value in ["-1", "11", "", None, True, "5.5"]:
            with self.subTest(value=value):
                rows, bad = normalize(payload(value), NOW, {"A1"})
                self.assertFalse(rows)
                self.assertEqual(len(bad), 1)

    def test_missing_reference_kept_but_excluded(self):
        rows, _ = normalize(payload(), NOW, set())
        self.assertEqual(rows[0]["quality_flags"], ["unmatched_reference"])
        self.assertFalse(rows[0]["training_eligible"])

    def test_stale_not_relabelled_as_new(self):
        rows, _ = normalize(payload(observed="2026-09-28T13:00:00"), NOW, {"A1"})
        self.assertIn("stale_source", rows[0]["quality_flags"])

    def test_historical_uses_query_time_for_staleness(self):
        old = "2026-09-27T14:00:00"
        rows, _ = normalize(payload(observed=old), NOW, {"A1"}, timestamp(old))
        self.assertTrue(rows[0]["training_eligible"])
        self.assertEqual(rows[0]["retrieved_at"], NOW.isoformat())

    def test_future_rejected(self):
        rows, bad = normalize(payload(observed="2026-09-29T14:00:00"), NOW, {"A1"})
        self.assertFalse(rows)
        self.assertTrue(bad)

    def test_duplicate_and_conflicting_observations(self):
        p = payload()
        p["items"][0]["carpark_data"] += payload()["items"][0]["carpark_data"]
        rows, bad = normalize(p, NOW, {"A1"})
        self.assertEqual(len(rows), 1)
        self.assertFalse(bad)
        p["items"][0]["carpark_data"] += payload("6")["items"][0]["carpark_data"]
        rows, bad = normalize(p, NOW, {"A1"})
        self.assertFalse(rows)
        self.assertTrue(bad)

    def test_lot_types_remain_separate(self):
        lots = [{"lots_available": "3", "total_lots": "10", "lot_type": k} for k in ["C", "Y"]]
        rows, _ = normalize(payload(kinds=lots), NOW, {"A1"})
        self.assertEqual([r["lot_type"] for r in rows], ["C", "Y"])

    def test_unrecognised_type_not_guessed(self):
        rows, bad = normalize(payload(kinds=[{"lot_type": "S", "lots_available": "2", "total_lots": "5"}]), NOW, {"A1"})
        self.assertFalse(rows)
        self.assertEqual(bad[0]["reason"], "unknown_lot_type")

    def test_bad_envelope_fails(self):
        with self.assertRaises(ValueError):
            normalize({"items": []}, NOW, {"A1"})


if __name__ == "__main__":
    unittest.main()
