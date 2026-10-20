"""One bounded live forecast study. No retraining, database writes or driver data."""
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'ml'))
from service.artifacts import load_artifacts
from service.engine import Engine
from service.live import LiveFeed


def summarize(events):
    groups=defaultdict(list)
    for event in events:
        groups[f"{event['horizon_minutes']}min/{event['mode']}/{event['stratum']}"].append(event)
    result={}
    for key,rows in groups.items():
        matched=[r for r in rows if r.get('outcome') is not None]
        paired=[r for r in matched if r['baseline_free'] is not None]
        brier=lambda r:(r['p_free']-int(r['outcome']['lots_available']>=1))**2
        result[key]={'issued':len(rows),'matched':len(matched),'unmatched':len(rows)-len(matched),
            'not_free':sum(r['outcome']['lots_available']==0 for r in matched),
            'brier':sum(map(brier,matched))/len(matched) if matched else None,
            'paired_count':len(paired),
            'paired_model_brier':sum(map(brier,paired))/len(paired) if paired else None,
            'persistence_brier':sum((r['baseline_free']-int(r['outcome']['lots_available']>=1))**2
                                    for r in paired)/len(paired) if paired else None,
            'state_changes':sum(r['baseline_free']!=int(r['outcome']['lots_available']>=1) for r in paired)}
    return result


def main():
    directory=ROOT/'backend/data/short-trip-pilot'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory.mkdir(parents=True)
    artifacts=load_artifacts(ROOT/'ml/models')
    feed=LiveFeed()
    feed.warm_up()
    readings=feed.refresh()
    now=datetime.now(timezone.utc)
    strata=defaultdict(list)
    for cid,r in readings.items():
        if r.observed_at>now: continue
        if now-r.observed_at>timedelta(minutes=15):
            if cid in artifacts.profile_carparks: strata['stale_profile'].append(cid)
        elif r.lots_available==0: strata['full'].append(cid)
        elif r.lots_available/r.total_lots<.10: strata['near_full'].append(cid)
        else: strata['other_free'].append(cid)
    rng=random.Random(20261017)
    chosen={}
    for stratum,ids in sorted(strata.items()):
        for cid in rng.sample(sorted(ids),min(len(ids),30 if stratum=='stale_profile' else 60)):
            chosen[cid]=stratum
    engine=Engine(artifacts,feed)
    events=[]
    failures=Counter()
    for horizon in (5,10,15):
        target=datetime.now(timezone.utc)+timedelta(minutes=horizon)
        for prediction in engine.predict(list(chosen),target):
            cid=prediction['carpark_id']
            recorded=datetime.now(timezone.utc)
            if prediction['status']!='ok' or prediction['p_free'] is None:
                failures[prediction['status']]+=1
                continue
            event={**prediction,'horizon_minutes':horizon,'stratum':chosen[cid],
                   'recorded_at':recorded,'baseline_free':None if prediction['current_available'] is None
                       else int(prediction['current_available']>=1),'outcome':None}
            assert recorded<target
            events.append(event)
    if not events: raise RuntimeError('No model forecasts available for the pilot')
    # Freeze issued probabilities before requesting any outcomes.
    (directory/'issued.json').write_text(json.dumps(events,default=str,indent=2),encoding='utf-8')
    print(json.dumps({'status':'issued','forecasts':len(events),'strata':dict(Counter(chosen.values())),
                      'failures':dict(failures),'max_wait_minutes':20}),flush=True)
    deadline=max(e['arrival_at'] for e in events)+timedelta(minutes=5)
    polls,errors=0,0
    while datetime.now(timezone.utc)<=deadline:
        time.sleep(60)
        try:
            later=feed.refresh()
            known=datetime.now(timezone.utc)
            polls+=1
        except Exception:
            errors+=1
            print(json.dumps({'status':'poll_failed','failures':errors}),flush=True)
            continue
        for event in events:
            reading=later.get(event['carpark_id'])
            target=event['arrival_at']
            if (event['outcome'] is None and reading is not None
                    and target<=reading.observed_at<=target+timedelta(minutes=5)
                    and event['recorded_at']<known and reading.observed_at<=known):
                event['outcome']={'observed_at':reading.observed_at,'known_at':known,
                                  'lots_available':reading.lots_available}
        print(json.dumps({'status':'collecting','polls':polls,
              'matched':sum(e['outcome'] is not None for e in events),'issued':len(events)}),flush=True)
        if all(e['outcome'] is not None for e in events): break
    report={'checked_at':datetime.now(timezone.utc),'model_version':artifacts.version,
            'seed':20261017,'groups':summarize(events),'polls':polls,'poll_errors':errors,
            'selection':'Stratified single-issuance convenience sample, not population weighted.',
            'claim':'Prospective pilot at one time only. Insufficient to establish general accuracy or enable new horizons.',
            'decision':'Keep sub-15-minute predictions and historical-profile ranking gated pending broader evidence.'}
    (directory/'outcomes.json').write_text(json.dumps(events,default=str,indent=2),encoding='utf-8')
    target=Path(__file__).with_name('results')/'short-trip-pilot.json'
    target.write_text(json.dumps(report,default=str,indent=2),encoding='utf-8')
    print(json.dumps(report,default=str,indent=2),flush=True)


if __name__=='__main__':
    try: main()
    except Exception as exc:
        raise SystemExit(f'Prospective pilot stopped ({type(exc).__name__}); private details withheld.') from None
