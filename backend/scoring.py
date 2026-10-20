"""Explainable provisional score: lower penalties mean a better candidate.

Weights/scales are project policy, not empirically learned driver preferences.
Fixed scales avoid changing two carparks' relative order when a third is added.
"""
from math import isfinite

WEIGHTS = {'cost':0.40, 'walking':0.30, 'availability':0.20, 'driving':0.10}
POLICY_VERSION = 'best_overall_v1_provisional'
PROBABILITY_POLICY_VERSION = 'best_overall_probability_v2_provisional'


def score_candidate(cost_cents: int, duration_minutes: int, walking_meters: float,
                    driving_seconds: float, available_lots: float | None,
                    weights: dict[str, float] | None = None, *, p_free: float | None = None) -> dict:
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
    weights = dict(WEIGHTS if weights is None else weights)
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
            'policy_version':PROBABILITY_POLICY_VERSION if p_free is not None else POLICY_VERSION,
            'reference_scales':{'cost_cents_for_requested_stay':cost_reference,
                                'walking_meters':500,'driving_seconds':900},
            'weights':weights, 'penalties':penalties, 'weighted_penalties':contributions,
            'raw_factors':{'cost_cents':cost_cents,'duration_minutes':duration_minutes,
                          'walking_meters':walking_meters,'driving_seconds':driving_seconds,
                          'available_lots':available_lots, 'p_free':p_free}}


def rank_candidates(candidates: list[dict]) -> list[dict]:
    """Rank eligible rows only; canonical identity gives a stable final tie-break."""
    eligible = [r for r in candidates if r.get('ranking_eligible') and r.get('scoring')]
    ordered = sorted(eligible, key=lambda r:(-r['scoring']['score'], r['price']['amount_cents'],
                    r['walking']['distance_meters'], r['driving']['duration_seconds'],
                    r['agency'], r['carpark_id']))
    return [{'rank':i, 'agency':r['agency'], 'carpark_id':r['carpark_id'],
             'score':r['scoring']['score']} for i,r in enumerate(ordered,1)]
