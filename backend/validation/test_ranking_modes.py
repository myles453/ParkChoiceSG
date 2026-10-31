"""Three search policies: trade-offs change; eligibility and fallback do not."""
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import random
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app import app
from onemap_adapter import RouteEstimate
from prediction import Prediction
from recommendation import TripRequest, recommend
from scoring import MODE_WEIGHTS, WEIGHTS, mode_weights, policy_version, rank_candidates, score_candidate
import test_workflow as fixtures


COSTS={'A':120,'B':240,'C':600}
WALKS={'A':800,'B':250,'C':50}
WINNERS={'best_overall':'B','cheaper':'A','closer':'C'}


def sample_candidates():
    return [{**row,'longitude':103.81+i*.01} for i,row in enumerate(fixtures.candidates())]


class Router:
    def route(self,start,end,mode):
        now=datetime.now(timezone.utc)
        key=min(sample_candidates(),key=lambda r:abs(r['longitude']-start.longitude))['carpark_id']
        return RouteEstimate('ok',mode,now,now,4000 if mode=='drive' else WALKS[key],1200)


class Model:
    ready=True
    output_kind='probability'

    def __init__(self,fallback=False,low=False):
        self.fallback,self.low=fallback,low

    def predict(self,r):
        if self.fallback:
            return Prediction('unsupported_horizon_15_to_90_minutes',r.agency,r.carpark_id,r.issued_at,r.arrival_at)
        return Prediction('ok',r.agency,r.carpark_id,r.issued_at,r.arrival_at,
            confidence='low' if self.low else 'medium',p_free=.2 if self.low else .96,
            model_version='synthetic-policy-fixture',history_cutoff=r.issued_at,mode='short')


def quotes(connection,rows,request):
    values=fixtures.quote_rows(rows,request)
    for key,row in values.items():row['price']['amount_cents']=COSTS[key[1]]
    return values


class ModeWorkflowTests(unittest.TestCase):
    def run_request(self,mode,*,model=None,quote_loader=quotes):
        with patch('recommendation.read_connection',fixtures.fake_connection), \
             patch('recommendation.shortlist',return_value=sample_candidates()), \
             patch('recommendation.quote_arrivals',side_effect=quote_loader), \
             patch('recommendation.record_forecast'):
            return recommend(TripRequest(fixtures.POINT,fixtures.POINT,60,ranking_mode=mode),Router(),model)

    def test_each_mode_changes_the_winner_without_changing_measurements(self):
        for model in (None,Model()):
            for mode,winner in WINNERS.items():
                with self.subTest(mode=mode,model=model):
                    result=self.run_request(mode,model=model)
                    self.assertEqual(result['ranked'][0]['carpark_id'],winner)
                    self.assertEqual(result['ranking_mode'],mode)
                    self.assertEqual(result['scoring_weights'],MODE_WEIGHTS[mode])
                    for row in result['candidates']:
                        self.assertEqual(row['price']['amount_cents'],COSTS[row['carpark_id']])
                        self.assertEqual(row['walking']['distance_meters'],WALKS[row['carpark_id']])
                        self.assertEqual(row['scoring']['ranking_mode'],mode)

    def test_current_fallback_uses_the_selected_mode_and_keeps_its_basis_separate(self):
        for mode,winner in WINNERS.items():
            result=self.run_request(mode,model=Model(fallback=True))
            self.assertEqual(result['ranked'],[])
            self.assertIsNone(result['top_recommendation'])
            self.assertEqual(result['fallback_ranked'][0]['carpark_id'],winner)
            self.assertEqual(result['fallback_scoring_policy'],policy_version(mode))
            self.assertTrue(all(r['fallback_scoring']['ranking_mode']==mode for r in result['candidates']))

    def test_priority_modes_do_not_bypass_low_forecasts_or_unknown_prices(self):
        def unpriced(*args):
            values=quotes(*args)
            values['HDB','A']['price']={'status':'tariff_unverified','amount_cents':None}
            return values
        for mode in MODE_WEIGHTS:
            low=self.run_request(mode,model=Model(low=True))
            self.assertEqual((low['ranked'],low['fallback_ranked']),([],[]))
            result=self.run_request(mode,model=Model(),quote_loader=unpriced)
            self.assertNotIn('A',[r['carpark_id'] for r in result['ranked']])
            self.assertIn('price_tariff_unverified',result['candidates'][0]['ranking_exclusions'])

    def test_api_default_and_all_modes_reach_the_workflow(self):
        body={'origin':{'latitude':1.3,'longitude':103.8},
              'destination':{'latitude':1.3,'longitude':103.8},'duration_minutes':60}
        with TestClient(app) as client,patch.object(app.state,'predictor',Model()), \
             patch('app.OneMapClient.from_env',return_value=Router()), \
             patch('recommendation.read_connection',fixtures.fake_connection), \
             patch('recommendation.shortlist',side_effect=lambda *a,**k:sample_candidates()), \
             patch('recommendation.quote_arrivals',side_effect=quotes), \
             patch('recommendation.record_forecast'):
            for mode,winner in WINNERS.items():
                response=client.post('/recommend',json={**body,'ranking_mode':mode})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['ranked'][0]['carpark_id'],winner)
                self.assertEqual(response.json()['ranking_mode'],mode)
            self.assertEqual(client.post('/recommend',json=body).json()['ranking_mode'],'best_overall')
            with patch('app.recommend') as work:
                for mode in ('unknown',None,True,[],{}):
                    self.assertEqual(client.post('/recommend',json={**body,'ranking_mode':mode}).status_code,422)
                work.assert_not_called()


class ScoreModeTests(unittest.TestCase):
    def test_default_score_is_backwards_compatible_and_profile_copies_are_independent(self):
        args=(240,60,500,1200,None)
        self.assertEqual(score_candidate(*args,p_free=.96),score_candidate(*args,weights=WEIGHTS,p_free=.96))
        self.assertEqual(mode_weights('best_overall'),WEIGHTS)
        copied=mode_weights('cheaper');copied['cost']=0
        self.assertEqual(mode_weights('cheaper')['cost'],.65)
        for mode in (None,[],{},True,'invalid'):
            with self.assertRaises(ValueError):
                TripRequest(fixtures.POINT,fixtures.POINT,60,ranking_mode=mode)

    def test_closer_mode_tie_break_prefers_the_shorter_walk(self):
        rows=[{'agency':'HDB','carpark_id':key,'ranking_eligible':True,'scoring':{'score':80},
               'price':{'amount_cents':cost},'walking':{'distance_meters':walk},
               'driving':{'duration_seconds':1200}}
              for key,cost,walk in [('A',120,800),('B',240,50)]]
        self.assertEqual(rank_candidates(rows,'closer')[0]['carpark_id'],'B')
        self.assertEqual(rank_candidates(rows,'cheaper')[0]['carpark_id'],'A')
        self.assertEqual(rank_candidates(rows[::-1],'closer'),rank_candidates(rows,'closer'))

    def test_all_profiles_are_bounded_and_monotone_for_counts_and_probabilities(self):
        rng=random.Random(20261020)
        for mode in MODE_WEIGHTS:
            self.assertAlmostEqual(sum(mode_weights(mode).values()),1)
            for _ in range(1000):
                for probability in (True,False):
                    row=dict(cost_cents=rng.randint(1,20000),duration_minutes=rng.choice([30,60,120,240]),
                        walking_meters=rng.uniform(1,5000),driving_seconds=rng.uniform(1,5400),
                        available_lots=None if probability else rng.randint(1,500),
                        p_free=rng.random() if probability else None,ranking_mode=mode)
                    base=score_candidate(**row)['score']
                    self.assertTrue(0<=base<=100)
                    for field in ('cost_cents','walking_meters','driving_seconds'):
                        self.assertLessEqual(score_candidate(**{**row,field:row[field]+1})['score'],base)
                    better={'p_free':min(1,row['p_free']+.01)} if probability else {'available_lots':row['available_lots']+1}
                    self.assertGreaterEqual(score_candidate(**{**row,**better})['score'],base)


if __name__=='__main__':unittest.main()
