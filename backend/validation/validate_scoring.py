"""Reproducible scoring behaviour/sensitivity study, separate from app code.

These tests verify mathematical behaviour and designed trade-offs. They do not
establish driver preferences, calibrated forecast accuracy or physical vacancies.
"""
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import random
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scoring import POLICY_VERSION, WEIGHTS, score_candidate

SEED=20261015
SAMPLES=20000
SCENARIOS={
    'clear_dominance':[
        {'name':'better','cost_cents':120,'duration_minutes':60,'walking_meters':200,'driving_seconds':300,'available_lots':20},
        {'name':'worse','cost_cents':400,'duration_minutes':60,'walking_meters':800,'driving_seconds':900,'available_lots':2}],
    'cost_vs_walking':[
        {'name':'cheap_far','cost_cents':120,'duration_minutes':60,'walking_meters':1000,'driving_seconds':600,'available_lots':20},
        {'name':'expensive_close','cost_cents':500,'duration_minutes':60,'walking_meters':200,'driving_seconds':600,'available_lots':20},
        {'name':'middle','cost_cents':240,'duration_minutes':60,'walking_meters':500,'driving_seconds':500,'available_lots':10}],
    'nearly_full_vs_more_spaces':[
        {'name':'near_one_space','cost_cents':120,'duration_minutes':60,'walking_meters':200,'driving_seconds':300,'available_lots':1},
        {'name':'far_twenty_spaces','cost_cents':120,'duration_minutes':60,'walking_meters':500,'driving_seconds':300,'available_lots':20}],
    'large_vs_small_carpark_count_saturation':[
        {'name':'five_spaces_close','cost_cents':120,'duration_minutes':60,'walking_meters':200,'driving_seconds':300,'available_lots':5},
        {'name':'two_hundred_spaces_far','cost_cents':120,'duration_minutes':60,'walking_meters':800,'driving_seconds':300,'available_lots':200}],
    'equal_everything':[
        {'name':'A','cost_cents':120,'duration_minutes':60,'walking_meters':200,'driving_seconds':300,'available_lots':5},
        {'name':'B','cost_cents':120,'duration_minutes':60,'walking_meters':200,'driving_seconds':300,'available_lots':5}],
}


def scored(row,weights=None):
    return score_candidate(**{k:v for k,v in row.items() if k!='name'},weights=weights)['score']


def main():
    rng=random.Random(SEED)
    violations=Counter()
    for _ in range(SAMPLES):
        x={'cost_cents':rng.randint(0,20000),'duration_minutes':rng.choice([15,30,60,120,240,1440]),
           'walking_meters':rng.uniform(0,5000),'driving_seconds':rng.uniform(0,7200),
           'available_lots':rng.uniform(0,1000)}
        base=scored(x)
        if not 0<=base<=100: violations['score_bounds']+=1
        for field in ['cost_cents','walking_meters','driving_seconds']:
            if scored({**x,field:x[field]+1}) > base+1e-10:
                violations[field+'_monotonicity']+=1
        if scored({**x,'available_lots':x['available_lots']+1}) < base-1e-10:
            violations['availability_monotonicity']+=1
        better={**x,'cost_cents':max(0,x['cost_cents']-1),'walking_meters':max(0,x['walking_meters']-1),
                'driving_seconds':max(0,x['driving_seconds']-1),'available_lots':x['available_lots']+1}
        if scored(better) <= base: violations['dominance']+=1
        # Reversing candidate order and adding an extreme third carpark cannot
        # change the two independent scores or their relative order.
        other={**x,'cost_cents':rng.randint(0,20000)}
        pair=[scored(x),scored(other)]
        expanded=[scored(other),scored({**x,'cost_cents':10**9}),scored(x)]
        if pair != [expanded[2],expanded[0]]: violations['candidate_set_independence']+=1
    summaries={}
    for name,rows in SCENARIOS.items():
        wins=Counter()
        for _ in range(5000):
            raw={key:weight*rng.uniform(.8,1.2) for key,weight in WEIGHTS.items()}
            weights={key:value/sum(raw.values()) for key,value in raw.items()}
            winner=max(rows,key=lambda row:scored(row,weights))['name']
            wins[winner]+=1
        forecast_changes=Counter()
        for _ in range(1000):
            perturbed=[{**row,'available_lots':max(0,row['available_lots']+rng.uniform(-3,3))} for row in rows]
            # Full/zero predictions are infeasible, not ordinary scored choices.
            eligible=[row for row in perturbed if row['available_lots']>0]
            forecast_changes[max(eligible,key=scored)['name'] if eligible else 'none']+=1
        scale_wins=Counter()
        for _ in range(5000):
            hourly,walk,drive=400*rng.uniform(.8,1.2),500*rng.uniform(.8,1.2),900*rng.uniform(.8,1.2)
            def changed_scales(row):
                cost_ref=hourly*row['duration_minutes']/60
                return 1-(.4*row['cost_cents']/(row['cost_cents']+cost_ref)
                          +.3*row['walking_meters']/(row['walking_meters']+walk)
                          +.2/(1+row['available_lots'])
                          +.1*row['driving_seconds']/(row['driving_seconds']+drive))
            scale_wins[max(rows,key=changed_scales)['name']]+=1
        baseline=sorted(rows,key=lambda row:-scored(row))
        summaries[name]={'default_scores':[{'name':r['name'],'score':round(scored(r),6)} for r in baseline],
                         'weight_perturbation_wins':dict(wins),
                         'forecast_plus_minus_3_lot_wins':dict(forecast_changes),
                         'reference_scale_perturbation_wins':dict(scale_wins),
                         'interpretation':'designed scenario; no human preference ground truth'}
    # Deliberate invalid inputs must fail, rather than produce a normal score.
    invalid_checked=0
    valid={'cost_cents':120,'duration_minutes':60,'walking_meters':200,'driving_seconds':300,'available_lots':5}
    invalid=[{'cost_cents':-1},{'cost_cents':True},{'duration_minutes':0},
             {'walking_meters':float('nan')},{'driving_seconds':float('inf')},
             {'available_lots':None},{'available_lots':-1},{'available_lots':True}]
    for changes in invalid:
        try:
            scored({**valid,**changes})
            violations['invalid_input_accepted']+=1
        except ValueError:
            invalid_checked+=1
    report={'generated_at':datetime.now(timezone.utc).isoformat(),'seed':SEED,
            'policy_version':POLICY_VERSION,'weights':WEIGHTS,'random_cases':SAMPLES,
            'property_comparisons':SAMPLES*7,'violations':dict(violations),
            'invalid_cases_rejected':invalid_checked,'weight_sensitivity_trials':25000,
            'forecast_sensitivity_trials':5000,'scenarios':summaries,
            'reference_scale_sensitivity_trials':25000,
            'claim':'behavioural validation only; no assertion of optimal weights or model accuracy'}
    folder=Path(__file__).resolve().parent/'results'
    folder.mkdir(exist_ok=True)
    (folder/'scoring-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='scenarios'},indent=2))
    if violations: raise SystemExit(1)


if __name__=='__main__':
    main()
