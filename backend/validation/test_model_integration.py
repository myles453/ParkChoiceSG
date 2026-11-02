"""Model/API integration checks, including probability units and failure handling."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock

import httpx

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_adapter import HdbModelClient
from prediction import PredictionRequest, valid_prediction
from scoring import score_candidate
import test_workflow as workflow


class ModelIntegrationTests(unittest.TestCase):
    def setUp(self):
        now=datetime.now(timezone.utc)
        self.request=PredictionRequest('HDB','ACB',now,now+timedelta(minutes=30))
        self.payload={'carpark_id':'ACB','issue_at':now.isoformat(),
            'arrival_at':self.request.arrival_at.isoformat(), 'status':'ok','mode':'short',
            'p_free':.96,'confidence':'Medium','model_version':'short-horizon-lgbm-20261007',
            'current_observed_at':(now-timedelta(minutes=2)).isoformat()}

    def client(self, payload=None, status=200):
        def respond(request):
            return httpx.Response(status,json=[self.payload if payload is None else payload])
        self.addCleanupClient=httpx.Client(transport=httpx.MockTransport(respond))
        self.addCleanup(self.addCleanupClient.close)
        return HdbModelClient('http://model.local',self.addCleanupClient)

    def test_probability_is_never_treated_as_a_lot_count(self):
        prediction=self.client().predict(self.request)
        self.assertTrue(valid_prediction(prediction,self.request))
        self.assertEqual(prediction.p_free,.96)
        self.assertIsNone(prediction.available_lots)
        self.assertIsNone(prediction.sample_count)  # service supplies no per-forecast sample count
        score=score_candidate(240,60,500,1200,None,p_free=prediction.p_free)
        self.assertAlmostEqual(score['penalties']['availability'],.04)

    def test_inconsistent_or_stale_responses_are_rejected(self):
        for changes in [{'carpark_id':'WRONG'},{'p_free':96},{'p_free':True},
                        {'p_free':.5,'confidence':'High'},
                        {'current_observed_at':(self.request.issued_at-timedelta(minutes=16)).isoformat()},
                        {'issue_at':(self.request.issued_at-timedelta(seconds=1)).isoformat()},
                        {'arrival_at':(self.request.arrival_at+timedelta(seconds=1)).isoformat()}]:
            with self.subTest(changes=changes):
                self.assertNotEqual(self.client({**self.payload,**changes}).predict(self.request).status,'ok')

    def test_profile_and_unvalidated_horizons_are_explicit(self):
        self.assertEqual(self.client({**self.payload,'mode':'profile'}).predict(self.request).status,
                         'historical_profile_not_enabled')
        for minutes in (0,5,14,91):
            request=replace(self.request,arrival_at=self.request.issued_at+timedelta(minutes=minutes))
            self.assertEqual(self.client().predict(request).status,'unsupported_horizon_15_to_90_minutes')
        self.assertEqual(self.client().predict(replace(self.request,agency='URA')).status,'unsupported_agency')

    def test_outage_is_sanitized(self):
        self.assertEqual(self.client(status=503).predict(self.request).status,'model_service_unavailable')

    def test_probability_score_is_bounded_monotonic_and_rejects_mixed_units(self):
        previous=-1
        for p in (0,.1,.5,.9,.99,1):
            score=score_candidate(240,60,500,1200,None,p_free=p)['score']
            self.assertTrue(0 <= score <= 100)
            self.assertGreater(score,previous)
            previous=score
        with self.assertRaises(ValueError):
            score_candidate(240,60,500,1200,20,p_free=.9)

    def test_real_probability_contract_reaches_ranking_without_count_substitution(self):
        class Model:
            ready=True
            output_kind='probability'
        # Use a direct typed fixture because the workflow router's trip is 10 min;
        # the HTTP adapter's 15-minute lower bound is checked separately above.
        from prediction import Prediction
        def predict(request):
            return Prediction('ok',request.agency,request.carpark_id,request.issued_at,request.arrival_at,
                confidence='medium',model_version='fixture',history_cutoff=request.issued_at,
                p_free=.96,mode='short')
        model=Model()
        model.predict=predict
        result=workflow.WorkflowTests().run_workflow(predictor=model,
            quotes=lambda r,q:workflow.quote_rows(r,q,count=0))
        self.assertEqual(result['ranking_basis'],'arrival_free_probability')
        self.assertEqual(len(result['ranked']),3)
        for row in result['candidates']:
            self.assertEqual(row['scoring']['raw_factors']['p_free'],.96)
            self.assertIsNone(row['scoring']['raw_factors']['available_lots'])

    def test_probability_audit_is_evaluated_with_brier_not_count_mae(self):
        from match_forecasts import evaluate
        issued=self.request.issued_at-timedelta(minutes=40)
        target=issued+timedelta(minutes=30)
        event={'forecast_id':'probability','agency':'HDB','carpark_id':'ACB',
               'issued_at':issued.isoformat(),'recorded_at':issued.isoformat(),
               'arrival_at':target.isoformat(),'model_version':'fixture','p_free':.9,'mode':'short',
               'available_lots':None,'baseline':{'available_lots':0,'timestamp':issued.isoformat(),
                   'timestamp_kind':'source_update','status':'fresh_source_update'}}
        connection=MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchall.return_value=[{
            'forecast_id':'probability','observed_at':target,'known_at':target+timedelta(seconds=30),
            'lots_available':2,'timestamp_kind':'source_update'}]
        report=evaluate([event],connection)
        group=next(iter(report['groups'].values()))
        self.assertAlmostEqual(group['brier'],.01)
        self.assertEqual(group['baseline_brier'],1)
        self.assertNotIn('mae_lots',group)


if __name__=='__main__':
    unittest.main()
