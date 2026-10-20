"""Current options stay separate from forecasts and require genuine fresh source time."""
from datetime import datetime, timedelta, timezone
import unittest
from pathlib import Path
import sys
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_adapter import HdbModelClient
from prediction import Prediction
import test_workflow as workflow


class CurrentFallbackTests(unittest.TestCase):
    def model(self,status='unsupported_horizon_15_to_90_minutes'):
        class Model:
            ready=True
            output_kind='probability'
            def predict(self,request):
                return Prediction(status,request.agency,request.carpark_id,
                                  request.issued_at,request.arrival_at)
        return Model()

    def test_short_trip_uses_a_separately_labelled_current_list(self):
        result=workflow.WorkflowTests().run_workflow(predictor=self.model())
        self.assertEqual(result['ranked'],[])
        self.assertEqual(len(result['fallback_ranked']),3)
        self.assertEqual(result['status'],'current_reading_fallback')
        self.assertIsNone(result['top_recommendation'])
        self.assertTrue(all(r['scoring'] is None for r in result['candidates']))
        self.assertIn('may change',result['fallback_notice'])

    def test_fallback_rejects_stale_proxy_full_and_unpriced_candidates(self):
        for options in ({'count':0},{'status':'stale'},{'status':'recent_retrieval_only'}):
            with self.subTest(options=options):
                result=workflow.WorkflowTests().run_workflow(predictor=self.model(),
                    quotes=lambda r,q:workflow.quote_rows(r,q,**options))
                self.assertEqual(result['fallback_ranked'],[])
        def quotes(rows,request):
            values=workflow.quote_rows(rows,request)
            for row in values.values(): row['price']={'status':'unknown','amount_cents':None}
            return values
        result=workflow.WorkflowTests().run_workflow(predictor=self.model(),quotes=quotes)
        self.assertEqual(result['fallback_ranked'],[])

    def test_known_low_probability_never_turns_into_positive_current_fallback(self):
        from dataclasses import replace
        class Low(workflow.TrainedFixture):
            output_kind='probability'
            def predict(self,request):
                return replace(super().predict(request),available_lots=None,p_free=.1,
                               confidence='low',mode='short')
        result=workflow.WorkflowTests().run_workflow(predictor=Low())
        self.assertEqual(result['ranked'],[])
        self.assertEqual(result['fallback_ranked'],[])

    def test_live_counts_replace_stale_db_counts_without_database_writes(self):
        model=self.model()
        now=datetime.now(timezone.utc)
        model.current_readings=lambda ids:{cid:{'available_lots':20,'total_lots':100,
            'status':'fresh_source_update','timestamp':now,'timestamp_kind':'source_update',
            'feed':'hdb_live_service'} for cid in ids}
        result=workflow.WorkflowTests().run_workflow(predictor=model,
            quotes=lambda r,q:workflow.quote_rows(r,q,status='stale'))
        self.assertEqual(len(result['fallback_ranked']),3)

    def test_current_adapter_rejects_clock_ahead_and_invalid_counts(self):
        now=datetime.now(timezone.utc)
        rows=[{'carpark_id':'A','available_lots':10,'total_lots':100,
               'timestamp':(now-timedelta(minutes=2)).isoformat(),'timestamp_kind':'source_update'},
              {'carpark_id':'B','available_lots':110,'total_lots':100,
               'timestamp':now.isoformat(),'timestamp_kind':'source_update'},
              {'carpark_id':'C','available_lots':10,'total_lots':100,
               'timestamp':(now+timedelta(minutes=1)).isoformat(),'timestamp_kind':'source_update'}]
        with httpx.Client(transport=httpx.MockTransport(lambda r:httpx.Response(200,json=rows))) as client:
            values=HdbModelClient('http://model.local',client).current_readings(['A','B','C'])
        self.assertEqual(values['A']['status'],'fresh_source_update')
        self.assertNotIn('B',values)
        self.assertEqual(values['C']['status'],'stale')


if __name__=='__main__': unittest.main()
