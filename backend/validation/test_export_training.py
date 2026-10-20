from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'data-pipeline'))

from datetime import datetime,timedelta,timezone
import unittest

from export_training import make_pairs,prepare_observations

BASE=datetime(2026,9,30,12,tzinfo=timezone.utc)


def row(minutes,available,known=None,agency="HDB",feed="hdb_direct",kind="source_update"):
    return {"agency":agency,"carpark_id":"A1","feed":feed,"timestamp_kind":kind,
            "observed_at":BASE+timedelta(minutes=minutes),"known_at":BASE+timedelta(minutes=known if known is not None else minutes),
            "lots_available":available,"total_lots":100 if agency=="HDB" else None,"run_id":str(minutes)}


class TrainingTests(unittest.TestCase):
    def test_causal_features_and_future_label(self):
        rows=[row(0,90),row(5,80),row(10,70),row(15,60),row(20,50),row(25,40)]
        pairs,_=make_pairs(rows,[15],tolerance_minutes=0)
        at10=next(p for p in pairs if p["decision_at"]==(BASE+timedelta(minutes=10)).isoformat())
        self.assertEqual(at10["current_available"],70)
        self.assertEqual(at10["available_lag_5min"],80)
        self.assertEqual(at10["label_available"],40)
        self.assertEqual(at10["arrival_slot_15min"],81)  # 20:25 SGT

    def test_late_arrival_not_available_to_earlier_feature(self):
        rows=[row(0,90),row(5,2,known=20),row(10,70),row(15,60),row(25,40),row(35,30)]
        pairs,_=make_pairs(rows,[15],tolerance_minutes=0)
        at10=next(p for p in pairs if p["decision_at"]==(BASE+timedelta(minutes=10)).isoformat())
        self.assertEqual(at10["available_lag_5min"],90)
        at20=next(p for p in pairs if p["decision_at"]==(BASE+timedelta(minutes=20)).isoformat())
        self.assertEqual(at20["current_available"],60)  # late old reading not current

    def test_long_gaps_are_not_filled_with_fake_labels(self):
        pairs,_=make_pairs([row(0,50),row(120,30)],[15],5)
        self.assertEqual(pairs,[])

    def test_one_decision_for_multiple_readings_delivered_together(self):
        pairs,_=make_pairs([row(0,10,known=5),row(5,20),row(20,30)],[15],0)
        self.assertEqual(len(pairs),1)
        self.assertEqual(pairs[0]["current_available"],20)

    def test_clock_ahead_source_is_not_a_causal_feature(self):
        _,audit=prepare_observations([row(5,10,known=4),row(15,5)])
        self.assertEqual(audit["accepted_observations"],1)

    def test_duplicate_source_instants_and_conflicts(self):
        clean,audit=prepare_observations([row(0,10,known=1),row(0,10,known=2),row(15,5)])
        self.assertEqual(audit["accepted_observations"],2)
        self.assertEqual(next(iter(clean.values()))[0]["known_at"],BASE+timedelta(minutes=1))
        clean,audit=prepare_observations([row(0,10),row(0,11),row(15,5)])
        self.assertEqual(audit["conflicting_source_instants"],1)
        self.assertEqual(audit["accepted_observations"],1)

    def test_retrieval_series_requires_opt_in_and_remains_labelled(self):
        rows=[row(0,10,agency="URA",feed="ura_direct",kind="retrieval"),
              row(15,0,agency="URA",feed="ura_direct",kind="retrieval")]
        self.assertEqual(make_pairs(rows,[15])[0],[])
        pairs,_=make_pairs(rows,[15],include_retrieval=True)
        self.assertEqual(pairs[0]["label_kind"],"retrieval_proxy")
        self.assertIsNone(pairs[0]["current_total_lots"])
        self.assertIsNone(pairs[0]["current_free_ratio"])
        self.assertEqual(pairs[0]["label_available"],0)

    def test_split_purges_crossing_training_targets(self):
        rows=[row(m,100-m) for m in range(0,61,5)]
        split=BASE+timedelta(minutes=30)
        pairs,_=make_pairs(rows,[15],split_at=split)
        for p in pairs:
            if p["split"]=="train":
                self.assertLess(datetime.fromisoformat(p["label_observed_at"]),split)
            else:
                self.assertGreaterEqual(datetime.fromisoformat(p["decision_at"]),split)


if __name__=="__main__":
    unittest.main()
