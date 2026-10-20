"""Lab 4 basis path tests for pricing.window_at and pricing._tier_price.

Flow graphs, cyclomatic complexity and path lists are in LAB4-TESTING.md.
Each case is (id, path description, inputs, expected).
"""
from datetime import date, datetime, time
from fractions import Fraction
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pricing import SINGAPORE, _tier_price, window_at

MON, TUE, SAT = date(2026,10,19), date(2026,10,20), date(2026,10,24)


def at(day, hour, minute=0):
    return datetime.combine(day,time(hour,minute),SINGAPORE)


def rule(start, end, day_type='all', **calculation):
    return {'start_time':start,'end_time':end,'day_type':day_type,'calculation':calculation}


DAY = rule('07:00','17:00','weekday')
NIGHT = rule('19:00','07:00')

WINDOW_CASES=[
    ('WA-P1','1-2F-4-5-6F-8F-9F-10F-11F-12 (baseline: weekday rule, Monday 10:00)',
     (DAY,at(MON,10),{}),(at(MON,7),at(MON,17))),
    ('WA-P2','1-2T-3 (equal open and close, not full day)',
     (rule('07:00','07:00'),at(MON,10),{}),None),
    ('WA-P3','1-2F-4-5-6T-7-8F-9F-10F-11F-12 (overnight window, Monday 20:00)',
     (NIGHT,at(MON,20),{}),(at(MON,19),at(TUE,7))),
    ('WA-P4','1-2F-4-5-6F-8T-4-5-6F-8T-4-13 (outside window on both anchor days)',
     (DAY,at(MON,18),{}),None),
    ('WA-P5','1-2F-4-5-6F-8F-9T-4-5-6F-8T-4-13 (day type mismatch, Saturday)',
     (DAY,at(SAT,10),{}),None),
    ('WA-P6','1-2F-4-5-6F-8F-9F-10T-4-5-6F-8T-4-13 (weekday filter excludes Saturday)',
     (rule('07:00','17:00',weekdays=[0,1,2,3,4]),at(SAT,10),{}),None),
    ('WA-P7','1-2F-4-5-6F-8F-9F-10F-11T-4-5-6F-8T-4-13 (holiday-eve rule, no holiday tomorrow)',
     (rule('07:00','17:00',ph_eve=True),at(MON,10),{}),None),
    ('WA-P8','1-2F-4-5-6T-7-8T-4-5-6T-7-8F-9F-10F-11F-12 (overnight window anchored on previous day)',
     (NIGHT,at(TUE,2),{}),(at(MON,19),at(TUE,7))),
    # Extra condition case: node 2 false because full_day is set, not because
    # the times differ. Then node 6 is true with equal times (24-hour window).
    ('WA-C1','1-2F-4-5-6T-7-8F-9F-10F-11F-12 (24-hour window, full_day set)',
     (rule('07:00','07:00',full_day=True),at(MON,10),{}),(at(MON,7),at(TUE,7))),
]

BASE_RULE={'unit_minutes':30,'amount_cents':50}
ONE_TIER=[{'duration_minutes':60,'unit_minutes':60,'amount_cents':120}]


def tier_rule(**calculation):
    return {**BASE_RULE,'calculation':calculation}


TIER_CASES=[
    ('TP-P1','1-2F-9-10-11T-12-10-13T-14-15 (baseline: one tier then per-unit remainder)',
     (tier_rule(tiers=ONE_TIER),90,None),Fraction(170)),
    ('TP-P2','1-2T-3T-4 (first entry required but unknown)',
     (tier_rule(tiers=ONE_TIER,first_entry_required=True),90,None),None),
    ('TP-P3','1-2T-3F-5F-9-10-11T-12-10-13T-14-15 (first entry confirmed)',
     (tier_rule(tiers=ONE_TIER,first_entry_required=True),90,True),Fraction(170)),
    ('TP-P4','1-2T-3F-5T-6-7T-8 (repeat entry, no repeat tiers published)',
     (tier_rule(tiers=ONE_TIER,first_entry_required=True),90,False),None),
    ('TP-P5','1-2T-3F-5T-6-7F-9-10-11T-12-10-13T-14-15 (repeat entry uses repeat tiers)',
     (tier_rule(tiers=ONE_TIER,first_entry_required=True,
                repeat_entry_tiers=[{'duration_minutes':60,'unit_minutes':60,'amount_cents':200}]),90,False),
     Fraction(250)),
    ('TP-P6','1-2F-9-10-13T-14-15 (no tiers; 45 min rounds up to two 30-min units)',
     (tier_rule(),45,None),Fraction(100)),
    ('TP-P7','1-2F-9-10-11T-12-10-11F-10-13F-15 (second tier gets zero minutes)',
     (tier_rule(tiers=ONE_TIER+[{'duration_minutes':60,'unit_minutes':30,'amount_cents':80}]),60,None),
     Fraction(120)),
    ('TP-P8','1-2F-9-10-11T-12-10-13F-15 (stay fits inside the only tier)',
     (tier_rule(tiers=ONE_TIER),60,None),Fraction(120)),
]


class WindowAtBasisPathTests(unittest.TestCase):
    def test_paths(self):
        for cid,_,args,expected in WINDOW_CASES:
            with self.subTest(cid):
                self.assertEqual(window_at(*args),expected)


class TierPriceBasisPathTests(unittest.TestCase):
    def test_paths(self):
        for cid,_,args,expected in TIER_CASES:
            with self.subTest(cid):
                self.assertEqual(_tier_price(*args),expected)


if __name__=='__main__':
    unittest.main()
