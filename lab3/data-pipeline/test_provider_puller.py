import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from provider_puller import LTA_URL, collect_lta, collect_ura, load_local_env, normalize_pages, require_list

NOW = datetime(2026, 9, 28, 6, 0, tzinfo=timezone.utc)


class ProviderCleaningTests(unittest.TestCase):
    def test_lta_agency_and_unknown_timestamp_stay_explicit(self):
        pages = [([{"Agency": "LTA", "CarParkID": "1", "LotType": "C",
                    "AvailableLots": "352", "Development": "Suntec City"}], NOW)]
        rows, rejected = normalize_pages(pages, "lta_datamall")
        self.assertEqual(rejected, [])
        self.assertEqual((rows[0]["feed"], rows[0]["agency"]), ("lta_datamall", "LTA"))
        self.assertEqual(rows[0]["retrieved_at"], NOW.isoformat())
        self.assertIsNone(rows[0]["source_updated_at"])
        self.assertIsNone(rows[0]["total_lots"])

    def test_ura_zero_and_motorcycle_code(self):
        pages = [([{"carparkNo": "N0006", "lotType": "M", "lotsAvailable": "0"}], NOW)]
        rows, rejected = normalize_pages(pages, "ura_direct")
        self.assertEqual(rejected, [])
        self.assertEqual((rows[0]["agency"], rows[0]["lot_type"], rows[0]["lots_available"]),
                         ("URA", "M", 0))

    def test_lta_repeated_agency_is_not_a_distinct_feed(self):
        records = [{"Agency": "HDB", "CarParkID": "KB7", "LotType": "C",
                    "AvailableLots": 18}]
        rows, _ = normalize_pages([(records, NOW)], "lta_datamall")
        self.assertEqual(rows[0]["agency"], "HDB")
        self.assertEqual(rows[0]["feed"], "lta_datamall")

    def test_invalid_and_conflicting_records_quarantined(self):
        records = [{"Agency": "LTA", "CarParkID": "1", "LotType": "C", "AvailableLots": "2"},
                   {"Agency": "LTA", "CarParkID": "1", "LotType": "C", "AvailableLots": "3"},
                   {"Agency": "LTA", "CarParkID": "2", "LotType": "C", "AvailableLots": "-1"}]
        rows, rejected = normalize_pages([(records, NOW)], "lta_datamall")
        self.assertEqual(rows, [])
        self.assertEqual(len(rejected), 2)

    def test_ura_error_envelope_not_data(self):
        with self.assertRaises(ValueError):
            require_list({"Status": "Error", "Message": "Invalid input."}, "Result")

    def test_lta_fetches_second_page(self):
        first = ({"value": [{"CarParkID": str(i)} for i in range(500)]}, b"first", NOW)
        second = ({"value": [{"CarParkID": "500"}]}, b"second", NOW)
        with patch.dict("os.environ", {"LTA_ACCOUNT_KEY": "test-key"}), \
             patch("provider_puller.get_json", side_effect=[first, second]) as get, \
             patch("provider_puller.archive", return_value={"sha256": "test"}):
            pages, artifacts = collect_lta(Path("unused"))
        self.assertEqual([len(records) for records, _ in pages], [500, 1])
        self.assertEqual(len(artifacts), 2)
        self.assertEqual(get.call_args_list[0].args[0], LTA_URL)
        self.assertIn("$skip=500", get.call_args_list[1].args[0])

    def test_env_file_loads_key_without_overriding_existing_environment(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text("LTA_ACCOUNT_KEY=file-key\nURA_ACCESS_KEY='ura-key'\n", encoding="utf-8")
            with patch.dict("os.environ", {"LTA_ACCOUNT_KEY": "existing-key"}, clear=True):
                load_local_env(path)
                import os
                self.assertEqual(os.environ["LTA_ACCOUNT_KEY"], "existing-key")
                self.assertEqual(os.environ["URA_ACCESS_KEY"], "ura-key")

    def test_lta_exact_full_page_accepts_empty_terminating_page(self):
        with patch.dict("os.environ", {"LTA_ACCOUNT_KEY": "test-key"}), \
             patch("provider_puller.get_json", side_effect=[
                 ({"value": [{}]*500}, b"first", NOW), ({"value": []}, b"last", NOW)]), \
             patch("provider_puller.archive", return_value={"sha256": "test"}):
            pages, artifacts = collect_lta(Path("unused"))
        self.assertEqual(len(pages), 1)
        self.assertEqual(len(artifacts), 2)

    def test_ura_token_response_is_not_archived(self):
        replies = [({"Status": "Success", "Result": "private-token"}, b"secret", NOW),
                   ({"Status": "Success", "Result": [{"carparkNo": "A0004"}]}, b"availability", NOW),
                   ({"Status": "Success", "Result": [{"ppCode": "A0004"}]}, b"rates", NOW)]
        with patch.dict("os.environ", {"URA_ACCESS_KEY": "test-key"}), \
             patch("provider_puller.get_json", side_effect=replies) as get, \
             patch("provider_puller.archive", return_value={"sha256": "test"}) as save:
            pages, artifacts, rate_count = collect_ura(Path("unused"), include_rates=True)
        self.assertEqual((len(pages), len(artifacts), rate_count), (1, 2, 1))
        self.assertEqual(save.call_args_list[0].args[2], b"availability")
        self.assertEqual(save.call_args_list[1].args[2], b"rates")
        self.assertEqual(get.call_args_list[1].args[1]["Token"], "private-token")


if __name__ == "__main__":
    unittest.main()
