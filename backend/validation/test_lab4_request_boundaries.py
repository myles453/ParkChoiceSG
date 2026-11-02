"""Boundary values for the validated request accepted by RecommendationController."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recommendation import TripRequest
import test_workflow as fixtures

REQUEST_CASES = []
for field, lower, upper in [('duration_minutes', 1, 1440),
                            ('candidate_limit', 1, 5), ('radius_meters', 100, 3000)]:
    for value in (lower-1, lower, lower+1, upper-1, upper, upper+1):
        REQUEST_CASES.append((f'REQ-{len(REQUEST_CASES)+1:02d}', field, value, lower <= value <= upper))


class RequestBoundaryTests(unittest.TestCase):
    def test_bounds(self):
        for cid, field, value, accepted in REQUEST_CASES:
            with self.subTest(case=cid, field=field, value=value):
                values = {'origin': fixtures.POINT, 'destination': fixtures.POINT, 'duration_minutes': 60}
                values[field] = value
                if accepted:
                    self.assertEqual(getattr(TripRequest(**values), field), value)
                else:
                    with self.assertRaises(ValueError):
                        TripRequest(**values)


if __name__ == '__main__':
    unittest.main()
