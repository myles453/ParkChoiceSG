"""Verify the shipped model with real HDB, OneMap and DB data; stop both servers."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx

ROOT=Path(__file__).resolve().parents[2]
PIPELINE=ROOT/'backend'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        return sock.getsockname()[1]


def wait_ready(url,process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError('Local service stopped before becoming ready')
        try:
            response=httpx.get(url+'/health',timeout=1)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            time.sleep(.25)
    raise RuntimeError('Local service startup timed out')


def main():
    processes=[]
    try:
        model_port,api_port=free_port(),free_port()
        model_url=f'http://127.0.0.1:{model_port}'
        api_url=f'http://127.0.0.1:{api_port}'
        for cwd,module,port in ((ROOT/'ml','service.main:app',model_port),(PIPELINE,'app:app',api_port)):
            environment={**os.environ,'PARKCHOICE_MODEL_URL':model_url}
            process=subprocess.Popen([sys.executable,'-m','uvicorn',module,'--host','127.0.0.1',
                '--port',str(port),'--no-access-log','--log-level','error'],cwd=cwd,env=environment,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            processes.append(process)
            health=wait_ready(model_url if port==model_port else api_url,process)
            if port==model_port:
                assert health['artifacts_loaded'], 'Model files failed to load'
                model_health=health
            else:
                assert health['prediction_configured'] and health['prediction_output']=='probability'
        # Public locations: western Singapore to Jurong East. No driver's history.
        response=httpx.post(api_url+'/recommend',json={
            'origin':{'latitude':1.3483,'longitude':103.6831},
            'destination':{'latitude':1.3331,'longitude':103.7420},
            'duration_minutes':120,'candidate_limit':3,'radius_meters':1500},timeout=100)
        response.raise_for_status()
        result=response.json()
        private=PIPELINE/'data/workflow-validation'
        private.mkdir(parents=True,exist_ok=True)
        (private/'latest-model.json').write_text(json.dumps(result),encoding='utf-8')
        assert result['ranking_basis']=='arrival_free_probability'
        assert any(r['prediction']['status']=='ok' for r in result['candidates']), 'No valid live model forecast'
        for row in result['candidates']:
            prediction=row['prediction']
            if prediction['status']=='ok':
                assert prediction['available_lots'] is None
                assert 0 <= prediction['p_free'] <= 1
            if row['ranking_eligible']:
                assert row['scoring']['raw_factors']['p_free']==prediction['p_free']
                assert row['price']['status']=='quoted'
        short_response=httpx.post(api_url+'/recommend',json={
            'origin':{'latitude':1.3197,'longitude':103.8421},
            'destination':{'latitude':1.2932,'longitude':103.8520},
            'duration_minutes':60,'candidate_limit':3,'radius_meters':1500},timeout=100)
        short_response.raise_for_status()
        short=short_response.json()
        (private/'latest-short-trip.json').write_text(json.dumps(short),encoding='utf-8')
        assert short['ranked']==[] and short['fallback_ranked'], 'Expected an explicit current-reading fallback'
        assert short['top_recommendation'] is None
        report={'checked_at':datetime.now(timezone.utc).isoformat(),'upstream_commit':'d05c1f8',
            'model':{k:v for k,v in model_health.items() if k!='error'},
            'status':result['status'],'ranking_basis':result['ranking_basis'],
            'policy':result['scoring_policy'],'ranked':result['ranked'],
            'candidates':[{'agency':r['agency'],'carpark_id':r['carpark_id'],
                'price_cents':r['price']['amount_cents'],'driving_seconds':r['driving']['duration_seconds'],
                'walking_meters':r['walking']['distance_meters'],'prediction':r['prediction'],
                'ranking_exclusions':r['ranking_exclusions']} for r in result['candidates']],
            'short_trip':{'status':short['status'],'ranked':short['ranked'],
                          'fallback_ranked':short['fallback_ranked'],'notice':short['fallback_notice']},
            'claim':'Integration check only; future outcomes have not been observed yet.'}
        target=Path(__file__).with_name('results')/'model-integration.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
        print(json.dumps(report,indent=2,allow_nan=False))
    finally:
        for process in reversed(processes):
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        message=str(exc) if isinstance(exc,AssertionError) else 'private details withheld'
        raise SystemExit(f'Model integration failed ({type(exc).__name__}): {message}') from None
