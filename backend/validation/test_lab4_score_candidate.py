"""Lab 4 black box tests for scoring.score_candidate.

Equivalence classes (EC) and boundary values (BV) are listed in LAB4-TESTING.md.
Each case is (id, kwargs, expected), where expected is a score rounded to
4 decimal places, a (score, policy_version) pair, or 'ValueError'.
"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scoring import POLICY_VERSION, PROBABILITY_POLICY_VERSION, score_candidate

# Nominal input: every penalty is exactly 0.5, so the score is 50.
NOMINAL={'cost_cents':400,'duration_minutes':60,'walking_meters':500,
         'driving_seconds':900,'available_lots':1}
EQUAL_WEIGHTS={'cost':0.25,'walking':0.25,'availability':0.25,'driving':0.25}
ERROR='ValueError'


def case(**changes):
    return {**NOMINAL,**changes}


EC_CASES=[
    ('EC-01','Valid lots mode, default weights (V1-V5, V7)',case(),(50.0,POLICY_VERSION)),
    ('EC-02','Valid probability mode, custom weights (V6, V8)',
     case(available_lots=None,p_free=0.5,weights=EQUAL_WEIGHTS),(50.0,PROBABILITY_POLICY_VERSION)),
    ('EC-03','I1 cost negative',case(cost_cents=-400),ERROR),
    ('EC-04','I2 cost not an integer',case(cost_cents=400.0),ERROR),
    ('EC-05','I3 duration not positive',case(duration_minutes=-60),ERROR),
    ('EC-06','I4 duration not an integer',case(duration_minutes=60.5),ERROR),
    ('EC-07','I5 walking negative',case(walking_meters=-500),ERROR),
    ('EC-08','I6 walking not finite',case(walking_meters=float('inf')),ERROR),
    ('EC-09','I7 walking not a number',case(walking_meters='500'),ERROR),
    ('EC-10','I8 driving negative',case(driving_seconds=-900),ERROR),
    ('EC-11','I9 driving not finite',case(driving_seconds=float('nan')),ERROR),
    ('EC-12','I10 lots negative',case(available_lots=-5),ERROR),
    ('EC-13','I11 no availability input',case(available_lots=None),ERROR),
    ('EC-14','I12 both lots and probability',case(p_free=0.5),ERROR),
    ('EC-15','I13 probability below 0',case(available_lots=None,p_free=-0.5),ERROR),
    ('EC-16','I14 probability above 1',case(available_lots=None,p_free=1.5),ERROR),
    ('EC-17','I15 probability NaN',case(available_lots=None,p_free=float('nan')),ERROR),
    ('EC-18','I16 weight key missing',
     case(weights={'cost':0.5,'walking':0.3,'availability':0.2}),ERROR),
    ('EC-19','I17 weight not positive',
     case(weights={'cost':0.5,'walking':0.5,'availability':0.0,'driving':0.0}),ERROR),
    ('EC-20','I18 weights do not sum to 1',
     case(weights={'cost':0.5,'walking':0.5,'availability':0.5,'driving':0.5}),ERROR),
]

BV_CASES=[
    ('BV-01','cost just below 0',case(cost_cents=-1),ERROR),
    ('BV-02','cost at 0',case(cost_cents=0),70.0),
    ('BV-03','cost just above 0',case(cost_cents=1),69.9002),
    ('BV-04','duration at 0',case(duration_minutes=0),ERROR),
    ('BV-05','duration at 1',case(duration_minutes=1),30.6557),
    ('BV-06','walking just below 0',case(walking_meters=-0.001),ERROR),
    ('BV-07','walking at 0',case(walking_meters=0),65.0),
    ('BV-08','driving just below 0',case(driving_seconds=-0.001),ERROR),
    ('BV-09','driving at 0',case(driving_seconds=0),55.0),
    ('BV-10','lots just below 0',case(available_lots=-0.001),ERROR),
    ('BV-11','lots at 0',case(available_lots=0),40.0),
    ('BV-12','probability just below 0',case(available_lots=None,p_free=-0.001),ERROR),
    ('BV-13','probability at 0',case(available_lots=None,p_free=0),40.0),
    ('BV-14','probability at 1',case(available_lots=None,p_free=1),60.0),
    ('BV-15','probability just above 1',case(available_lots=None,p_free=1.001),ERROR),
    ('BV-16','weights sum exactly 1',
     case(weights={'cost':0.1,'walking':0.2,'availability':0.3,'driving':0.4}),50.0),
    ('BV-17','weights sum just above 1',
     case(weights={'cost':0.1,'walking':0.2,'availability':0.3,'driving':0.400001}),ERROR),
]


def actual(kwargs):
    """Run one case and return a value comparable with its expected output."""
    try:
        result=score_candidate(**kwargs)
    except ValueError:
        return ERROR
    return round(result['score'],4),result['policy_version']


def matches(expected, got):
    if expected==ERROR or got==ERROR:
        return expected==got
    if isinstance(expected,tuple):
        return expected==got
    return expected==got[0]


class ScoreCandidateBlackBoxTests(unittest.TestCase):
    def test_equivalence_classes(self):
        for cid,_,kwargs,expected in EC_CASES:
            with self.subTest(cid):
                self.assertTrue(matches(expected,actual(kwargs)),(expected,actual(kwargs)))

    def test_boundary_values(self):
        for cid,_,kwargs,expected in BV_CASES:
            with self.subTest(cid):
                self.assertTrue(matches(expected,actual(kwargs)),(expected,actual(kwargs)))


if __name__=='__main__':
    unittest.main()
