"""Check the new probability score; this cannot establish optimal user preferences."""
from collections import Counter
import json
from pathlib import Path
import random
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scoring import PROBABILITY_POLICY_VERSION, WEIGHTS, score_candidate


def score(row,weights=None):
    return score_candidate(**row,weights=weights)['score']


def main():
    rng=random.Random(20261017)
    violations=Counter()
    for _ in range(20000):
        row={'cost_cents':rng.randint(0,20000),'duration_minutes':rng.choice([30,60,120,240]),
             'walking_meters':rng.uniform(0,5000),'driving_seconds':rng.uniform(900,5400),
             'available_lots':None,'p_free':rng.random()}
        base=score(row)
        if not 0<=base<=100: violations['bounds']+=1
        for field in ('cost_cents','walking_meters','driving_seconds'):
            if score({**row,field:row[field]+1}) > base+1e-10:
                violations[field+'_monotonicity']+=1
        if score({**row,'p_free':min(1,row['p_free']+.01)}) < base:
            violations['probability_monotonicity']+=1
        better={**row,'cost_cents':max(0,row['cost_cents']-1),
                'walking_meters':max(0,row['walking_meters']-1),'p_free':min(1,row['p_free']+.01)}
        if score(better)<=base: violations['dominance']+=1
    reference={'duration_minutes':60,'driving_seconds':1200,'available_lots':None}
    scenarios={
        'equal_routes_different_probability':{
            '90_percent':{**reference,'cost_cents':240,'walking_meters':500,'p_free':.90},
            '99_percent':{**reference,'cost_cents':240,'walking_meters':500,'p_free':.99}},
        'cheaper_vs_higher_probability':{
            'cheap_90_percent':{**reference,'cost_cents':120,'walking_meters':500,'p_free':.90},
            'costly_99_percent':{**reference,'cost_cents':240,'walking_meters':500,'p_free':.99}},
        'near_threshold_probability_noise':{
            'near_91_percent':{**reference,'cost_cents':240,'walking_meters':400,'p_free':.91},
            'far_99_percent':{**reference,'cost_cents':240,'walking_meters':500,'p_free':.99}}}
    results={}
    for name,rows in scenarios.items():
        wins,noise=Counter(),Counter()
        for _ in range(5000):
            raw={k:v*rng.uniform(.8,1.2) for k,v in WEIGHTS.items()}
            weights={k:v/sum(raw.values()) for k,v in raw.items()}
            wins[max(rows,key=lambda key:score(rows[key],weights))]+=1
            noisy={k:{**v,'p_free':min(1,max(0,v['p_free']+rng.uniform(-.03,.03)))}
                   for k,v in rows.items()}
            eligible={k:v for k,v in noisy.items() if v['p_free']>=.9}
            noise[max(eligible,key=lambda key:score(eligible[key])) if eligible else 'none']+=1
        results[name]={'scores':{k:score(v) for k,v in rows.items()},
                       'weight_variation_wins':dict(wins),'probability_noise_wins':dict(noise)}
    report={'seed':20261017,'policy':PROBABILITY_POLICY_VERSION,'random_cases':20000,
            'property_comparisons':120000,'violations':dict(violations),'scenarios':results,
            'weight_trials':15000,'probability_noise_trials':15000,
            'claim':'Mathematical and sensitivity checks only, not model accuracy or optimal weights.'}
    target=Path(__file__).with_name('results')/'probability-scoring.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    if violations: raise SystemExit(1)


if __name__=='__main__':
    main()
