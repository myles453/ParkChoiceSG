"""Offline workflow checks. Run from backend; no API credentials used."""
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import app
from onemap_adapter import Coordinate, RouteEstimate
from prediction import PendingPredictor, Prediction, PredictionRequest, valid_prediction
from recommendation import TripRequest, quote_arrivals, recommend, straight_distance
from scoring import rank_candidates, score_candidate

NOW = datetime.now(timezone.utc)
POINT = Coordinate(1.2932,103.852)


@contextmanager
def fake_connection():
    yield MagicMock()


def candidates():
    return [{'agency':'HDB','carpark_id':code,'display_name':code,'address':'Test fixture',
             'latitude':1.293,'longitude':103.853,'shortlist_distance_meters':i*100}
            for i,code in enumerate(('A','B','C'),1)]


def quote_rows(rows,request,*,status='fresh_source_update',count=20):
    return {(r['agency'],r['carpark_id']):{
        'price':{'status':'quoted','amount_cents':120},'lots_available':count,
        'total_lots':100,'availability_status':status,'availability_timestamp':NOW,
        'timestamp_kind':'source_update','availability_feed':'hdb_direct',
        'capacity_consistency':'consistent'} for r in rows if r['driving']['status']=='ok'}


class Router:
    def route(self,start,end,mode):
        return RouteEstimate('ok',mode,NOW,NOW,500,600,NOW+timedelta(seconds=600) if mode=='drive' else None)


class TrainedFixture:
    """Synthetic contract fixture, not a trained model."""
    ready = True

    def predict(self,request):
        return Prediction('ok',request.agency,request.carpark_id,request.issued_at,request.arrival_at,
                          12,'medium','test-fixture',request.issued_at,20)


class WorkflowTests(unittest.TestCase):
    def run_workflow(self,router=None,predictor=None,quotes=quote_rows):
        with patch('recommendation.read_connection',fake_connection), \
             patch('recommendation.shortlist',return_value=candidates()), \
             patch('recommendation.record_forecast'), \
             patch('recommendation.quote_arrivals',side_effect=lambda c,r,q:quotes(r,q)):
            return recommend(TripRequest(POINT,POINT,60),router or Router(),predictor)

    def test_pending_model_is_only_a_labelled_current_reading_baseline(self):
        result=self.run_workflow()
        self.assertEqual(result['ranking_basis'],'current_availability_baseline')
        self.assertEqual(result['prediction_status'],'prediction_pending')
        self.assertEqual(len(result['ranked']),3)
        self.assertTrue(all(r['prediction']['available_lots'] is None for r in result['candidates']))
        self.assertTrue(result['policy_is_provisional'])

    def test_real_adapter_contract_enables_prediction_basis(self):
        result=self.run_workflow(predictor=TrainedFixture())
        self.assertEqual(result['ranking_basis'],'predicted_availability')
        self.assertTrue(all(r['scoring']['raw_factors']['available_lots']==12 for r in result['candidates']))

    def test_model_failure_never_silently_mixes_current_counts_into_forecast_scores(self):
        class PartialModel(TrainedFixture):
            def predict(self,r):
                if r.carpark_id=='B':
                    raise RuntimeError('test-only provider failure')
                return super().predict(r)
        result=self.run_workflow(predictor=PartialModel())
        self.assertEqual([r['carpark_id'] for r in result['ranked']],['A','C'])
        self.assertIn('prediction_unavailable',result['candidates'][1]['ranking_exclusions'])

    def test_full_or_stale_baseline_data_never_enters_ranking(self):
        for options in [{'count':0},{'status':'stale'},{'status':'recent_retrieval_only'}]:
            with self.subTest(options=options):
                result=self.run_workflow(quotes=lambda r,q:quote_rows(r,q,**options))
                self.assertEqual(result['ranked'],[])
                self.assertIsNone(result['top_recommendation'])

    def test_unpriced_candidate_is_excluded_without_zero_substitution(self):
        def quotes(rows,q):
            result=quote_rows(rows,q)
            result[('HDB','B')]['price']={'status':'tariff_unverified','amount_cents':None}
            return result
        result=self.run_workflow(quotes=quotes)
        self.assertEqual([r['carpark_id'] for r in result['ranked']],['A','C'])
        self.assertIsNone(result['candidates'][1]['scoring'])

    def test_route_failure_is_per_candidate(self):
        class FailedRouter(Router):
            calls=0
            def route(self,start,end,mode):
                self.calls+=1
                if self.calls==3:
                    return RouteEstimate('no_route',mode,NOW,NOW)
                return super().route(start,end,mode)
        result=self.run_workflow(router=FailedRouter())
        self.assertEqual([r['carpark_id'] for r in result['ranked']],['A','C'])
        self.assertIn('driving_no_route',result['candidates'][1]['ranking_exclusions'])

    def test_common_departure_makes_etas_independent_of_call_order(self):
        result=self.run_workflow()
        for row in result['candidates']:
            self.assertEqual(row['arrival_at']-result['departure_at'],timedelta(seconds=600))

    def test_capacity_bound_and_invalid_model_identity_are_rejected(self):
        class InvalidModel(TrainedFixture):
            def predict(self,r):
                p=super().predict(r)
                return replace(p,available_lots=101) if r.carpark_id=='A' else replace(p,carpark_id='WRONG')
        result=self.run_workflow(predictor=InvalidModel())
        self.assertEqual(result['ranked'],[])

    def test_low_confidence_forecasts_are_visible_but_excluded(self):
        class LowModel(TrainedFixture):
            def predict(self,r):
                return replace(super().predict(r),confidence='low')
        result=self.run_workflow(predictor=LowModel())
        self.assertEqual(result['ranked'],[])
        self.assertTrue(all('low_model_confidence' in r['ranking_exclusions'] for r in result['candidates']))

    def test_valid_future_forecast_can_select_a_currently_full_carpark(self):
        result=self.run_workflow(predictor=TrainedFixture(),quotes=lambda r,q:quote_rows(r,q,count=0))
        self.assertEqual(len(result['ranked']),3)

    def test_minute_rounding_keeps_both_estimates_and_scores_the_higher_one(self):
        rows=[{**candidates()[0],'arrival_at':NOW.replace(second=30,microsecond=0),
               'driving':{'status':'ok'}}]
        base={'agency':'HDB','carpark_id':'A','quote_arrival_at':NOW.replace(second=0,microsecond=0),
              'price':{'status':'quoted','amount_cents':120,'payment_method':'eps','schedule_id':1}}
        upper={**base,'price':{**base['price'],'amount_cents':122}}
        with patch('recommendation.compare_stay_options',return_value=[base,upper]):
            result=quote_arrivals(MagicMock(),rows,TripRequest(POINT,POINT,60))
        price=result[('HDB','A')]['price']
        self.assertEqual(price['status'],'quoted')
        self.assertEqual((price['amount_min_cents'],price['amount_max_cents'],price['amount_cents']),(120,122,122))
        unsupported={**upper,'price':{'status':'tariff_unverified','amount_cents':None}}
        with patch('recommendation.compare_stay_options',return_value=[base,unsupported]):
            result=quote_arrivals(MagicMock(),rows,TripRequest(POINT,POINT,60))
        self.assertIsNone(result[('HDB','A')]['price']['amount_cents'])

    def test_invalid_trip_never_starts_work(self):
        for kwargs in [{'duration_minutes':True},{'duration_minutes':0},{'duration_minutes':1441},
                       {'candidate_limit':6},{'radius_meters':5000}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):
                TripRequest(**{'origin':POINT,'destination':POINT,'duration_minutes':60,**kwargs})

    def test_haversine_is_shortlist_distance_only(self):
        self.assertEqual(straight_distance(POINT,POINT),0)
        self.assertAlmostEqual(straight_distance(POINT,Coordinate(1.2942,103.852)),111.19,delta=0.1)


class PredictionContractTests(unittest.TestCase):
    def test_forecasts_are_saved_before_outcomes_without_personal_locations(self):
        import json
        from tempfile import TemporaryDirectory
        from prediction import record_forecast
        request=PredictionRequest('HDB','A',datetime.now(timezone.utc),datetime.now(timezone.utc)+timedelta(minutes=15))
        with TemporaryDirectory() as folder:
            path=Path(folder)/'issued.jsonl'
            record_forecast(TrainedFixture().predict(request),None,path)
            event=json.loads(path.read_text())
            self.assertNotIn('origin',event)
            self.assertNotIn('destination',event)
            self.assertLess(datetime.fromisoformat(event['recorded_at']),request.arrival_at)
            self.assertEqual(event['model_version'],'test-fixture')
    def test_stale_future_nan_wrong_identity_and_uncalibrated_shape_rejected(self):
        request=PredictionRequest('HDB','A',NOW,NOW+timedelta(minutes=15))
        good=TrainedFixture().predict(request)
        self.assertTrue(valid_prediction(good,request))
        for p in [replace(good,history_cutoff=NOW+timedelta(seconds=1)),
                  replace(good,history_cutoff=NOW-timedelta(minutes=16)),
                  replace(good,available_lots=float('nan')),replace(good,available_lots=True),
                  replace(good,confidence=None),replace(good,model_version=''),
                  replace(good,sample_count=0),replace(good,arrival_at=NOW),
                  replace(good,agency='URA')]:
            with self.subTest(prediction=p):
                self.assertFalse(valid_prediction(p,request))


class ApiTests(unittest.TestCase):
    def setUp(self):
        predictor=patch.object(app.state,'predictor',PendingPredictor())
        predictor.start()
        self.addCleanup(predictor.stop)
        self.client=TestClient(app)

    def test_health_does_not_claim_external_services_are_working(self):
        with patch.object(app.state,'predictor',PendingPredictor()):
            self.assertEqual(self.client.get('/health').json(),
                             {'status':'ok','prediction_configured':False,'prediction_output':None})

    def test_local_browser_preflight_is_allowed_without_opening_every_origin(self):
        headers={'Origin':'http://127.0.0.1:7777','Access-Control-Request-Method':'POST',
                 'Access-Control-Request-Headers':'content-type'}
        r=self.client.options('/recommend',headers=headers)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['access-control-allow-origin'],headers['Origin'])
        r=self.client.options('/recommend',headers={**headers,'Origin':'https://unrelated.example'})
        self.assertNotIn('access-control-allow-origin',r.headers)

    def test_invalid_request_returns_fields_without_echoing_location(self):
        body={'origin':{'latitude':999.123456,'longitude':103.8},
              'destination':{'latitude':1.3,'longitude':103.8},'duration_minutes':60}
        r=self.client.post('/recommend',json=body)
        self.assertEqual(r.status_code,422)
        self.assertNotIn('999.123456',r.text)

    def test_database_failure_is_sanitized(self):
        body={'origin':{'latitude':1.3,'longitude':103.8},
              'destination':{'latitude':1.3,'longitude':103.8},'duration_minutes':60}
        with patch('app.OneMapClient.from_env',return_value=Router()), \
             patch('app.recommend',side_effect=RuntimeError('postgresql://private-password')):
            r=self.client.post('/recommend',json=body)
        self.assertEqual(r.status_code,503)
        self.assertNotIn('private-password',r.text)

    def test_api_serializes_real_workflow_shape(self):
        body={'origin':{'latitude':1.3,'longitude':103.8},
              'destination':{'latitude':1.3,'longitude':103.8},'duration_minutes':60}
        with patch('app.OneMapClient.from_env',return_value=Router()), \
             patch('recommendation.read_connection',fake_connection), \
             patch('recommendation.shortlist',return_value=candidates()), \
             patch('recommendation.quote_arrivals',side_effect=lambda c,r,q:quote_rows(r,q)):
            r=self.client.post('/recommend',json=body)
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['ranking_basis'],'current_availability_baseline')
        self.assertEqual(len(r.json()['ranked']),3)


class ForecastMatcherTests(unittest.TestCase):
    def test_matched_pending_and_unmatched_are_kept_and_baselines_are_paired(self):
        from match_forecasts import evaluate
        issued=NOW-timedelta(minutes=20)
        def event(key,target,baseline=None):
            return {'forecast_id':key,'agency':'HDB','carpark_id':'A','issued_at':issued.isoformat(),
                    'recorded_at':issued.isoformat(),'arrival_at':target.isoformat(),
                    'available_lots':6,'model_version':'synthetic-test','baseline':baseline}
        events=[event('matched',NOW-timedelta(minutes=15),
                      {'available_lots':4,'timestamp_kind':'source_update','status':'fresh_source_update',
                       'timestamp':(issued-timedelta(minutes=1)).isoformat()}),
                event('pending',NOW+timedelta(minutes=15)),event('missing',NOW-timedelta(hours=1))]
        connection=MagicMock()
        cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value=[
            {'forecast_id':'matched','observed_at':NOW-timedelta(minutes=15),
             'known_at':NOW-timedelta(minutes=14),'lots_available':7,'timestamp_kind':'source_update'},
            {'forecast_id':'pending','observed_at':None},{'forecast_id':'missing','observed_at':None}]
        result=evaluate(events,connection)
        self.assertEqual((result['matched'],result['pending'],result['unmatched']),(1,1,1))
        g=next(iter(result['groups'].values()))
        self.assertEqual((g['mae_lots'],g['paired_model_mae_lots'],g['baseline_mae_lots']),(1,1,3))
        self.assertNotIn('actual_lots',result['results'][1])

    def test_empty_and_duplicate_forecasts_do_not_produce_false_metrics(self):
        from match_forecasts import evaluate
        connection=MagicMock()
        self.assertEqual(evaluate([],connection)['groups'],{})
        with self.assertRaises(ValueError):
            evaluate([{'forecast_id':'duplicate'},{'forecast_id':'duplicate'}],connection)
        connection.cursor.assert_not_called()


if __name__=='__main__':
    unittest.main()
