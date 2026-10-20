"""Small real-API benchmark using public sample locations, not driver histories.

Runs the real HTTP endpoint once, then two direct service calls. Raw normalized
results stay under ignored data/; the shareable report contains public IDs and
measurements only. This never substitutes mock predictions for a trained model.
"""
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import sys
import time
from urllib.request import Request,urlopen

PIPELINE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PIPELINE))
from onemap_adapter import Coordinate,OneMapClient
from recommendation import TripRequest,recommend
from scoring import WEIGHTS,score_candidate

SAMPLES=[
    ('City Hall',(1.3197,103.8421),(1.2932,103.8520),60),
    ('Orchard',(1.3151,103.7652),(1.3048,103.8318),90),
    ('Jurong East',(1.3483,103.6831),(1.3331,103.7420),120),
]


def http_case(body):
    with socket.socket() as s:
        s.bind(('127.0.0.1',0))
        port=s.getsockname()[1]
    process=subprocess.Popen([sys.executable,'-m','uvicorn','app:app','--host','127.0.0.1',
         '--port',str(port),'--no-access-log','--log-level','warning'],cwd=PIPELINE,
         env={**os.environ,'PARKCHOICE_MODEL_URL':''},
         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    root=f'http://127.0.0.1:{port}'
    try:
        for _ in range(50):
            try:
                with urlopen(root+'/health',timeout=1) as r:
                    assert json.load(r)['status']=='ok'
                break
            except OSError:
                if process.poll() is not None: raise RuntimeError('Local API did not start')
                time.sleep(.1)
        else:
            raise RuntimeError('Local API did not become ready')
        with urlopen(root+'/openapi.json',timeout=3) as r:
            assert set(json.load(r)['paths'])=={'/health','/destinations','/recommend'}
        request=Request(root+'/recommend',data=json.dumps(body).encode(),
                        headers={'Content-Type':'application/json'},method='POST')
        with urlopen(request,timeout=100) as r:
            assert r.status==200
            return json.load(r)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def sensitivity(result):
    rows=[r for r in result['candidates'] if r['ranking_eligible']]
    if not rows: return {}
    wins={r['carpark_id']:0 for r in rows}
    rng=random.Random(20261015)
    for _ in range(1000):
        raw={k:v*rng.uniform(.8,1.2) for k,v in WEIGHTS.items()}
        weights={k:v/sum(raw.values()) for k,v in raw.items()}
        winner=max(rows,key=lambda r:score_candidate(**r['scoring']['raw_factors'],weights=weights)['score'])
        wins[winner['carpark_id']]+=1
    return wins


def main():
    private=PIPELINE/'data/workflow-validation'
    private.mkdir(exist_ok=True)
    report={'checked_at':datetime.now(timezone.utc).isoformat(),'model':'pending',
            'claim':'real routes/current readings/prices; provisional baseline ranking, not forecast validation',
            'samples':[]}
    for index,(name,origin,destination,minutes) in enumerate(SAMPLES):
        start=time.monotonic()
        body={'origin':dict(zip(('latitude','longitude'),origin)),
              'destination':dict(zip(('latitude','longitude'),destination)),
              'duration_minutes':minutes,'candidate_limit':3,'radius_meters':1500}
        if index==0:
            result=http_case(body)
        else:
            result=recommend(TripRequest(Coordinate(*origin),Coordinate(*destination),minutes),OneMapClient.from_env())
        (private/(name.replace(' ','-').lower()+'.json')).write_text(json.dumps(result,default=str,indent=2),encoding='utf-8')
        assert result['prediction_status']=='prediction_pending'
        assert result['ranking_basis']=='current_availability_baseline'
        for row in result['candidates']:
            assert row['prediction'].get('available_lots') is None
            if row['ranking_eligible']:
                assert row['driving']['status']==row['walking']['status']=='ok'
                assert row['price']['status']=='quoted'
                assert row['current_availability']['status']=='fresh_source_update'
        sample={'destination':name,'transport':'HTTP' if index==0 else 'service',
                'elapsed_seconds':round(time.monotonic()-start,3),'status':result['status'],
                'ranked':result['ranked'],'weight_sensitivity_wins_out_of_1000':sensitivity(result),
                'candidates':[{'agency':r['agency'],'carpark_id':r['carpark_id'],
                 'price_status':r['price']['status'],'cost_cents':r['price']['amount_cents'],
                 'driving_seconds':r['driving']['duration_seconds'],'walking_meters':r['walking']['distance_meters'],
                 'current_lots':(r['current_availability'] or {}).get('available_lots'),
                 'current_timestamp':(r['current_availability'] or {}).get('timestamp'),
                 'exclusions':r['ranking_exclusions']} for r in result['candidates']]}
        report['samples'].append(sample)
        print(json.dumps(sample,default=str),flush=True)
    folder=Path(__file__).resolve().parent/'results'
    folder.mkdir(exist_ok=True)
    (folder/'live-workflow.json').write_text(json.dumps(report,default=str,indent=2),encoding='utf-8')


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(f'Live workflow check failed ({type(exc).__name__}); credentials and raw errors withheld.') from None
