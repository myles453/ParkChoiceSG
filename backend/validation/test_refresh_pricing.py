from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'data-pipeline'))

import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
from refresh_pricing import compile_ura, without_transaction_wrapper, load_ura_pricing


def record(**changes):
    return dict(ppCode='A0004', vehCat='Car', parkingSystem='B',
                startTime='10.30 PM', endTime='07.00 AM',
                weekdayRate='$0.60', weekdayMin='30 mins',
                satdayRate='$0.60', satdayMin='30 mins',
                sunPHRate='$0.60', sunPHMin='30 mins', **changes)


class RefreshPricingTests(unittest.TestCase):
    def test_changed_price_is_compiled_from_new_capture(self):
        old = compile_ura({}, [record()])[0]
        updated = record()
        updated['weekdayRate'] = '$1.20'
        new = compile_ura({}, [updated])[0]
        self.assertEqual(old['rules'][0]['amount_cents'], 60)
        self.assertEqual(new['rules'][0]['amount_cents'], 120)

    def test_paired_night_cap_is_not_additional_charge(self):
        cap = record()
        cap.update(weekdayRate='$5.00', weekdayMin='510 mins')
        rules = compile_ura({}, [record(), cap])[0]['rules']
        self.assertEqual(rules[3]['rule_kind'], 'cap')
        self.assertEqual(rules[3]['amount_cents'], 500)
        unpaired = compile_ura({}, [cap])[0]['rules'][0]
        self.assertTrue(unpaired['calculation']['blocks_quote'])

    def test_zero_missing_and_unknown_system_never_become_free(self):
        for change in ({'weekdayRate':'$0.00','weekdayMin':'0 mins'},
                       {'weekdayRate':'','weekdayMin':''}, {'parkingSystem':'UNKNOWN'}):
            raw = record()
            raw.update(change)
            rule = compile_ura({}, [raw])[0]['rules'][0]
            self.assertEqual(rule['review_status'], 'pending_review')
            self.assertTrue(rule['calculation']['blocks_quote'])

    def test_invalid_and_equal_clocks_block_whole_day(self):
        for end in ('invalid', '10.30 PM'):
            raw = record()
            raw['endTime'] = end
            rule = compile_ura({}, [raw])[0]['rules'][0]
            self.assertTrue(rule['calculation']['full_day'])

    def test_mixed_parking_systems_block(self):
        other = record()
        other['parkingSystem'] = 'C'
        self.assertEqual(compile_ura({}, [record(), other])[0]['review_status'], 'pending_review')

    def test_transaction_wrapper_preserves_provider_strings(self):
        inner = "SELECT 'COMMIT; BEGIN;';\n"
        script = 'SET standard_conforming_strings = on;\nBEGIN;\n' + inner + 'COMMIT;\n'
        self.assertEqual(without_transaction_wrapper(script), inner)

    def test_same_capture_replay_does_not_write_duplicate_rates(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1, 1)
        manifest = {'run_id':'example', 'retrieved_at':'2026-10-02T00:00:00+00:00'}
        with patch('refresh_pricing.read_verified_details', return_value=(manifest, [record()])):
            self.assertTrue(load_ura_pricing(cursor, Path('.'))['already_loaded'])
        self.assertTrue(all('INSERT' not in call.args[0] for call in cursor.execute.call_args_list))

    def test_old_capture_cannot_replace_new_rates(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(0,0), (datetime.fromisoformat('2026-10-03T00:00:00+00:00'),)]
        manifest = {'run_id':'example', 'retrieved_at':'2026-10-02T00:00:00+00:00'}
        with patch('refresh_pricing.read_verified_details', return_value=(manifest, [record()])):
            with self.assertRaisesRegex(ValueError, 'out-of-order'):
                load_ura_pricing(cursor, Path('.'))
        self.assertTrue(all('UPDATE' not in call.args[0] for call in cursor.execute.call_args_list))


if __name__ == '__main__':
    unittest.main()
