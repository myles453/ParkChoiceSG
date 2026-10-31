"""Specification-based cases for the recommendation control class.

All external boundaries use fixtures; no live database or provider is contacted.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from onemap_adapter import RouteEstimate
from prediction import PendingPredictor, Prediction
from recommendation import RecommendationController, TripRequest
import test_workflow as fixtures


CASES = [
    ('CTL-01', 'Valid arrival forecast', {}, 'ok', 3, 0),
    ('CTL-02', 'Explicit current baseline', {'pending': True}, 'ok', 3, 0),
    ('CTL-03', 'Empty eligible shortlist', {'empty': True}, 'no_eligible_candidates', 0, 0),
    ('CTL-04', 'Driving route unavailable', {'route_error': 'drive'}, 'no_eligible_candidates', 0, 0),
    ('CTL-05', 'Walking route unavailable', {'route_error': 'walk'}, 'no_eligible_candidates', 0, 0),
    ('CTL-06', 'Price unsupported', {'price': 'tariff_unverified'}, 'no_eligible_candidates', 0, 0),
    ('CTL-07', 'Prediction history too old', {'history_age': 16}, 'no_eligible_candidates', 0, 0),
    ('CTL-08', 'Forecast just below eligibility threshold', {'probability': .899999}, 'no_eligible_candidates', 0, 0),
    ('CTL-09', 'Forecast at eligibility threshold', {'probability': .90}, 'ok', 3, 0),
    ('CTL-10', 'Forecast just above eligibility threshold', {'probability': .900001}, 'ok', 3, 0),
    ('CTL-11', 'Audit write fails', {'audit_error': True}, 'no_eligible_candidates', 0, 0),
    ('CTL-12', 'Unsupported horizon with fresh current evidence',
     {'prediction_status': 'unsupported_horizon_15_to_90_minutes'}, 'current_reading_fallback', 0, 3),
    ('CTL-13', 'Unsupported forecast with stale current evidence',
     {'prediction_status': 'unsupported_horizon_15_to_90_minutes', 'current_status': 'stale'},
     'no_eligible_candidates', 0, 0),
    ('CTL-14', 'Current full reading does not veto a valid future forecast', {'current_count': 0}, 'ok', 3, 0),
    ('CTL-15', 'Wrong prediction identity', {'wrong_identity': True}, 'no_eligible_candidates', 0, 0),
    ('CTL-16', 'Retrieval proxy cannot enter current fallback',
     {'prediction_status': 'unknown_carpark', 'timestamp_kind': 'retrieval'}, 'no_eligible_candidates', 0, 0),
]


class ProbabilityFixture:
    ready = True
    output_kind = 'probability'
    supported_agencies = ('HDB',)

    def __init__(self, options):
        self.options = options

    def predict(self, request):
        opts = self.options
        issued = datetime.now(timezone.utc)
        probability = opts.get('probability', .96)
        band = 'high' if probability >= .99 else 'medium' if probability >= .9 else 'low'
        return Prediction(
            opts.get('prediction_status', 'ok'), request.agency,
            'WRONG' if opts.get('wrong_identity') else request.carpark_id,
            issued, request.arrival_at, confidence=band, model_version='controlled-fixture',
            history_cutoff=issued-timedelta(minutes=opts.get('history_age', 1)),
            p_free=probability, mode='short',
        )


def execute(options):
    class Router(fixtures.Router):
        def route(self, start, end, mode):
            if mode == options.get('route_error'):
                now = datetime.now(timezone.utc)
                return RouteEstimate('no_route', mode, now, now)
            return super().route(start, end, mode)

    request = TripRequest(fixtures.POINT, fixtures.POINT, 60)
    rows = [] if options.get('empty') else fixtures.candidates()

    def quotes(connection, candidates, trip):
        data = fixtures.quote_rows(candidates, trip,
                                   status=options.get('current_status', 'fresh_source_update'),
                                   count=options.get('current_count', 20))
        for row in data.values():
            row['price']['status'] = options.get('price', 'quoted')
            row['timestamp_kind'] = options.get('timestamp_kind', 'source_update')
            row['availability_timestamp'] = datetime.now(timezone.utc)
        return data

    predictor = PendingPredictor() if options.get('pending') else ProbabilityFixture(options)
    with patch('recommendation.read_connection', fixtures.fake_connection), \
         patch('recommendation.shortlist', return_value=rows), \
         patch('recommendation.quote_arrivals', side_effect=quotes), \
         patch('recommendation.record_forecast', side_effect=OSError('fixture') if options.get('audit_error') else None):
        return RecommendationController(Router(), predictor).recommend(request)


class RecommendationControlBlackBoxTests(unittest.TestCase):
    def test_equivalence_classes_and_probability_boundary(self):
        for cid, description, inputs, status, ranked, fallback in CASES:
            with self.subTest(case=cid, description=description):
                result = execute(inputs)
                self.assertEqual((result['status'], len(result['ranked']), len(result['fallback_ranked'])),
                                 (status, ranked, fallback))
                self.assertEqual(result['top_recommendation'] is None, ranked == 0)


if __name__ == '__main__':
    unittest.main()
