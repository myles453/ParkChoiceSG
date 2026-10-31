"""Explainable provisional score: lower penalties mean a better candidate.

Weights/scales are project policy, not empirically learned driver preferences.
Fixed scales avoid changing two carparks' relative order when a third is added.
"""
from math import isfinite

MODE_WEIGHTS = {
    'best_overall': {'cost':0.40, 'walking':0.30, 'availability':0.20, 'driving':0.10},
    'cheaper': {'cost':0.65, 'walking':0.15, 'availability':0.15, 'driving':0.05},
    'closer': {'cost':0.15, 'walking':0.65, 'availability':0.15, 'driving':0.05},
}
MODE_LABELS = {'best_overall':'Best overall', 'cheaper':'Prioritise cheaper',
               'closer':'Prioritise closer'}
WEIGHTS = dict(MODE_WEIGHTS['best_overall'])
POLICY_VERSION = 'best_overall_v1_provisional'
PROBABILITY_POLICY_VERSION = 'best_overall_probability_v2_provisional'


def mode_weights(ranking_mode: str) -> dict[str, float]:
    if not isinstance(ranking_mode,str) or ranking_mode not in MODE_WEIGHTS:
        raise ValueError('Unsupported ranking mode')
    return dict(MODE_WEIGHTS[ranking_mode])


def policy_version(ranking_mode: str, *, probability: bool = False) -> str:
    mode_weights(ranking_mode)
    return ranking_mode + ('_probability_v2_provisional' if probability else '_v1_provisional')


def score_candidate(cost_cents: int, duration_minutes: int, walking_meters: float,
                    driving_seconds: float, available_lots: float | None,
                    weights: dict[str, float] | None = None, *, p_free: float | None = None,
                    ranking_mode: str = 'best_overall') -> dict:
    """Return 0..100, higher is better, plus every raw and weighted factor.

    Reference scales: S$4 per requested parking hour, 500 m walking and 15 min
    driving. x/(x+reference) grows smoothly, so extreme costs do not flatten into
    the same score. Availability uses 1/(lots+1): extra lots matter most near full.
    It is a preference penalty, never a probability of finding a space.
    When a classifier supplies p_free instead, use 1-p_free and leave lots null.
    """
    if type(cost_cents) is not int or cost_cents < 0 or type(duration_minutes) is not int or duration_minutes <= 0:
        raise ValueError('Cost must be nonnegative integer cents and duration positive integer minutes')
    if p_free is not None and (available_lots is not None or type(p_free) not in (int,float)
                              or not isfinite(p_free) or not 0 <= p_free <= 1):
        raise ValueError('Supply either lots or a probability within [0,1]')
    for value in (walking_meters, driving_seconds, available_lots if p_free is None else p_free):
        if isinstance(value, bool) or not isinstance(value, (int,float)) or not isfinite(value) or value < 0:
            raise ValueError('Score inputs must be finite nonnegative numbers')
    selected_weights = mode_weights(ranking_mode)
    weights = dict(selected_weights if weights is None else weights)
    if set(weights) != set(WEIGHTS) or any(isinstance(w,bool) or not isinstance(w,(int,float))
            or not isfinite(w) or w <= 0 for w in weights.values()) or abs(sum(weights.values())-1) > 1e-9:
        raise ValueError('All four weights must be positive and sum to one')
    cost_reference = 400 * duration_minutes / 60
    penalties = {'cost':cost_cents/(cost_cents+cost_reference),
                 'walking':walking_meters/(walking_meters+500),
                 'availability':1-p_free if p_free is not None else 1/(1+available_lots),
                 'driving':driving_seconds/(driving_seconds+900)}
    contributions = {key:weights[key]*penalties[key] for key in weights}
    return {'score':100*(1-sum(contributions.values())),
            'policy_version':policy_version(ranking_mode,probability=p_free is not None),
            'ranking_mode':ranking_mode,
            'reference_scales':{'cost_cents_for_requested_stay':cost_reference,
                                'walking_meters':500,'driving_seconds':900},
            'weights':weights, 'penalties':penalties, 'weighted_penalties':contributions,
            'raw_factors':{'cost_cents':cost_cents,'duration_minutes':duration_minutes,
                          'walking_meters':walking_meters,'driving_seconds':driving_seconds,
                          'available_lots':available_lots, 'p_free':p_free}}


def rank_candidates(candidates: list[dict], ranking_mode: str = 'best_overall') -> list[dict]:
    """Rank eligible rows only; canonical identity gives a stable final tie-break."""
    mode_weights(ranking_mode)
    eligible = [r for r in candidates if r.get('ranking_eligible') and r.get('scoring')]
    def order(row):
        cost,walk=row['price']['amount_cents'],row['walking']['distance_meters']
        priority=(walk,cost) if ranking_mode=='closer' else (cost,walk)
        return (-row['scoring']['score'],*priority,row['driving']['duration_seconds'],
                row['agency'],row['carpark_id'])
    ordered = sorted(eligible,key=order)
    return [{'rank':i, 'agency':r['agency'], 'carpark_id':r['carpark_id'],
             'score':r['scoring']['score']} for i,r in enumerate(ordered,1)]
