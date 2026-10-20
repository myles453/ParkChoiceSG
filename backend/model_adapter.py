"""Use the teammate's existing HDB inference service, without retraining it."""
from datetime import datetime, timedelta, timezone
import os

import httpx

from prediction import PendingPredictor, Prediction, PredictionRequest, valid_prediction
from pipeline_support import load_local_env


class HdbModelClient:
    """HTTP client for the ml/service HDB model. Failures become statuses, not errors."""
    ready = True  # configured, not a claim that the remote process is healthy
    supported_agencies = ('HDB',)
    output_kind = 'probability'

    def __init__(self, url: str, client=None):
        self.url = url.rstrip('/')
        self.client = client or httpx

    def current_readings(self, carpark_ids: list[str]) -> dict:
        """Fetch public current counts once per search; do not depend on DB collection cadence."""
        if not carpark_ids: return {}
        try:
            response=self.client.post(self.url+'/current',json={'carpark_ids':carpark_ids},timeout=10)
            response.raise_for_status()
            rows=response.json()
            if not isinstance(rows,list): return {}
            results={}
            duplicates=set()
            now=datetime.now(timezone.utc)
            for row in rows:
                cid=row.get('carpark_id')
                if cid not in carpark_ids: continue
                if cid in results: duplicates.add(cid)
                available,total=row.get('available_lots'),row.get('total_lots')
                stamp=datetime.fromisoformat(row['timestamp'])
                if (type(available) is not int or type(total) is not int
                        or total<=0 or not 0<=available<=total or stamp.utcoffset() is None
                        or row.get('timestamp_kind')!='source_update'): continue
                fresh=timedelta(0)<=now-stamp<=timedelta(minutes=15)
                results[cid]={'available_lots':available,'total_lots':total,'timestamp':stamp,
                    'status':'fresh_source_update' if fresh else 'stale',
                    'timestamp_kind':'source_update','feed':'hdb_live_service'}
            return {cid:row for cid,row in results.items() if cid not in duplicates}
        except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError):
            return {}

    def predict(self, request: PredictionRequest) -> Prediction:
        def unavailable(status):
            return Prediction(status, request.agency, request.carpark_id,
                              request.issued_at, request.arrival_at)

        if request.agency != 'HDB':
            return unavailable('unsupported_agency')
        horizon = (request.arrival_at-request.issued_at).total_seconds()/60
        # Training used 15/30/45/60/90-minute targets. Avoid claiming validation
        # for <15-minute trips or the separate historical-profile fallback.
        if not 15 <= horizon <= 90:
            return unavailable('unsupported_horizon_15_to_90_minutes')
        try:
            response = self.client.post(self.url+'/predict', json={
                'carpark_ids':[request.carpark_id], 'arrival_at':request.arrival_at.isoformat()
            }, timeout=10)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, list) or len(payload) != 1:
                return unavailable('invalid_model_response')
            row = payload[0]
            if row.get('carpark_id') != request.carpark_id:
                return unavailable('invalid_model_response')
            if row.get('status') != 'ok':
                status = row.get('status')
                return unavailable(status if status in {'unknown_carpark','insufficient_history',
                    'live_feed_unavailable','model_error'} else 'model_unavailable')
            if row.get('mode') != 'short':
                return unavailable('historical_profile_not_enabled')
            p = row.get('p_free')
            # Use the calibrated bands in the shipped HDB model card. Fail closed
            # on changed/inconsistent metadata rather than inventing confidence.
            band = 'high' if type(p) in (float,int) and p >= .99 else (
                'medium' if type(p) in (float,int) and p >= .90 else 'low')
            if str(row.get('confidence')).lower() != band:
                return unavailable('invalid_model_response')
            result = Prediction('ok', request.agency, row['carpark_id'],
                datetime.fromisoformat(row['issue_at']), datetime.fromisoformat(row['arrival_at']),
                confidence=band, model_version=row.get('model_version'),
                history_cutoff=datetime.fromisoformat(row['current_observed_at']),
                p_free=p, mode=row['mode'], fallback_reason=row.get('fallback_reason'))
            return result if valid_prediction(result,request) else unavailable('invalid_model_response')
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            return unavailable('model_service_unavailable')


def configured_predictor():
    """Use the model service when PARKCHOICE_MODEL_URL is set, otherwise no forecasts."""
    load_local_env()
    url = os.environ.get('PARKCHOICE_MODEL_URL','').strip()
    return HdbModelClient(url) if url else PendingPredictor()
