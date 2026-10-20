"""Coordinate a small carpark search using existing DB, route and price modules.

The service uses plain functions. The collector still runs separately; a driver
search never polls all availability sources or writes driver information.
"""
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
import os

from comparison import CandidateStay, compare_stay_options
from onemap_adapter import Coordinate, RoutingProvider
from prediction import AvailabilityPredictor, PendingPredictor, PredictionRequest, record_forecast, valid_prediction
from scoring import POLICY_VERSION, PROBABILITY_POLICY_VERSION, rank_candidates, score_candidate


@dataclass(frozen=True)
class TripRequest:
    origin: Coordinate
    destination: Coordinate
    duration_minutes: int
    candidate_limit: int = 3
    radius_meters: int = 1500
    payment_method: str = 'parking_sg'

    def __post_init__(self):
        if not isinstance(self.origin, Coordinate) or not isinstance(self.destination, Coordinate):
            raise ValueError('origin and destination must be coordinates')
        for name, lower, upper in [('duration_minutes',1,1440),('candidate_limit',1,5),('radius_meters',100,3000)]:
            if type(getattr(self,name)) is not int or not lower <= getattr(self,name) <= upper:
                raise ValueError(f'{name} must be an integer between {lower} and {upper}')
        if self.payment_method not in {'parking_sg','paper_coupon'}:
            raise ValueError('Unsupported payment method')


@contextmanager
def read_connection():
    """Short read-only DB transaction. Never hold it open during routing calls."""
    import psycopg
    if not os.environ.get('DATABASE_URL'):
        raise RuntimeError('Database configuration is missing')
    with psycopg.connect(os.environ['DATABASE_URL'], sslmode='require',
                         connect_timeout=10, prepare_threshold=None) as connection:
        connection.read_only = True
        connection.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '10s'")
        yield connection


def straight_distance(start: Coordinate, end: Coordinate) -> float:
    """Haversine metres for shortlisting only, never labelled walking distance."""
    lat1, lat2 = radians(start.latitude), radians(end.latitude)
    a = sin((lat2-lat1)/2)**2 + cos(lat1)*cos(lat2)*sin(radians(end.longitude-start.longitude)/2)**2
    return 2*6371000*asin(sqrt(min(1,max(0,a))))


def shortlist(connection, request: TripRequest, *, current_baseline: bool = True,
              supported_agencies: tuple[str, ...] | None = None) -> list[dict]:
    """Prefer nearby general carparks with a reviewed calculator, not assumed prices."""
    from psycopg.rows import dict_row
    dlat = request.radius_meters / 111000
    dlng = request.radius_meters / (111000 * max(0.01, cos(radians(request.destination.latitude))))
    baseline_filter = (" AND i.availability_status='fresh_source_update' AND i.lots_available > 0"
                       if current_baseline else '')
    with connection.cursor(row_factory=dict_row) as cursor:
        agency_filter = ' AND i.agency = ANY(%s)' if supported_agencies else ''
        parameters = [request.destination.latitude-dlat, request.destination.latitude+dlat,
                      request.destination.longitude-dlng, request.destination.longitude+dlng]
        if supported_agencies:
            parameters.append(list(supported_agencies))
        cursor.execute("""SELECT i.agency,i.carpark_id,i.display_name,i.address,i.latitude,i.longitude
          FROM parking_data.carpark_candidate_inputs i
          WHERE i.location_status='single_point'
            AND i.latitude BETWEEN %s AND %s AND i.longitude BETWEEN %s AND %s
            AND (i.agency <> 'HDB' OR i.short_term_parking IS DISTINCT FROM 'NO')
            AND NOT EXISTS (SELECT 1 FROM parking_data.hdb_loading_bay_tariffs b
                            WHERE i.agency='HDB' AND b.carpark_id=i.carpark_id)
            AND EXISTS (SELECT 1 FROM parking_data.rate_schedules s
                        WHERE s.agency=i.agency AND s.carpark_id=i.carpark_id
                          AND s.review_status='verified' AND s.calculator_key='window_rules_v1'
                          AND s.valid_from <= now() AND (s.valid_until IS NULL OR s.valid_until > now()))"""
                       + baseline_filter + agency_filter, parameters)
        rows = cursor.fetchall()
    candidates = []
    for row in rows:
        distance = straight_distance(Coordinate(row['latitude'],row['longitude']), request.destination)
        if distance <= request.radius_meters:
            candidates.append({**row,'shortlist_distance_meters':distance})
    candidates.sort(key=lambda r:(r['shortlist_distance_meters'],r['agency'],r['carpark_id']))
    return candidates[:request.candidate_limit]


def quote_arrivals(connection, candidates: list[dict], request: TripRequest) -> dict:
    """Keep second-precision ETA and disclose neighbouring-minute price estimates.

    The calculator uses whole minutes. Price both neighbouring minute starts,
    and expose that approximation even when their supported prices agree.
    This is not an assertion about exact-second operator billing.
    """
    routed = [r for r in candidates if r['driving']['status']=='ok']
    if not routed:
        return {}
    floors, ceilings = [], []
    for row in routed:
        arrival = row['arrival_at']
        floor = arrival.replace(second=0,microsecond=0)
        ceiling = floor if floor == arrival else floor+timedelta(minutes=1)
        floors.append(CandidateStay(row['agency'],row['carpark_id'],floor,request.duration_minutes,request.payment_method))
        ceilings.append(CandidateStay(row['agency'],row['carpark_id'],ceiling,request.duration_minutes,request.payment_method))
    options = compare_stay_options(connection,floors+ceilings)
    lower,upper=options[:len(routed)],options[len(routed):]
    results = {}
    for row,lo,hi in zip(routed,lower,upper):
        price = dict(lo['price'])
        lo_price, hi_price = lo['price'], hi['price']
        if lo_price['status']=='quoted' and (hi_price['status']!='quoted'
                or (lo_price['payment_method'],lo_price['schedule_id']) !=
                   (hi_price['payment_method'],hi_price['schedule_id'])):
            price = {'status':'arrival_precision_ambiguous','amount_cents':None,
                     'note':'Neighbouring minute arrivals do not give the same supported price.'}
        elif lo_price['status']!='quoted' and hi_price['status']=='quoted':
            price = {'status':'arrival_precision_ambiguous','amount_cents':None,
                     'note':'A sub-minute arrival difference changes quote eligibility.'}
        elif lo_price['status']=='quoted' and hi_price['status']=='quoted':
            # Crossing a tariff time boundary may change one minute's charge.
            # Retain both supported estimates; score the higher one explicitly.
            price=dict(hi_price if hi_price['amount_cents']>lo_price['amount_cents'] else lo_price)
            price['amount_min_cents']=min(lo_price['amount_cents'],hi_price['amount_cents'])
            price['amount_max_cents']=max(lo_price['amount_cents'],hi_price['amount_cents'])
            price['amount_cents']=price['amount_max_cents']
            price['estimate_basis']='higher_neighbouring_minute_quote'
        price['time_approximation'] = {'policy':'neighbouring_minute_estimates',
              'actual_arrival_at':row['arrival_at'], 'earlier_start':lo['quote_arrival_at'],
              'later_start':hi['quote_arrival_at'], 'exact_second_billing_supported':False}
        results[(row['agency'],row['carpark_id'])] = {**lo,'price':price}
    return results


def recommend(request: TripRequest, router: RoutingProvider,
              predictor: AvailabilityPredictor | None = None) -> dict:
    """Build routed/priced candidates and a clearly labelled provisional ranking."""
    predictor = predictor or PendingPredictor()
    use_model = getattr(predictor,'ready',False) is True
    probability_model = use_model and getattr(predictor,'output_kind',None) == 'probability'
    started_at = datetime.now(timezone.utc)
    with read_connection() as connection:
        candidates = shortlist(connection,request,current_baseline=not use_model,
                               supported_agencies=getattr(predictor,'supported_agencies',None))
    for row in candidates:
        point = Coordinate(row['latitude'],row['longitude'])
        row['driving'] = asdict(router.route(request.origin,point,'drive'))
        row['walking'] = asdict(router.route(point,request.destination,'walk'))
    # All candidates assume the same departure after route collection, avoiding
    # different departure instants just because one network call ran first.
    departure_at = datetime.now(timezone.utc)
    for row in candidates:
        row['arrival_at'] = (departure_at+timedelta(seconds=row['driving']['duration_seconds'])
                             if row['driving']['status']=='ok' else None)
        row['driving']['estimated_arrival_at'] = row['arrival_at']
        row['driving']['departure_assumption'] = 'common_departure_after_route_collection'
    with read_connection() as connection:
        quotes = quote_arrivals(connection,candidates,request)
    live_current = (predictor.current_readings([r['carpark_id'] for r in candidates])
                    if probability_model and hasattr(predictor,'current_readings') else {})
    # A trained adapter opts in explicitly. Never mix current counts and future
    # predictions inside the same comparison score.
    basis = ('arrival_free_probability' if probability_model else 'predicted_availability') if use_model else 'current_availability_baseline'
    for row in candidates:
        reasons = []
        for mode in ('driving','walking'):
            if row[mode]['status']!='ok':
                reasons.append(mode+'_'+row[mode]['status'])
        quote = quotes.get((row['agency'],row['carpark_id']))
        row['price'] = quote['price'] if quote else {'status':'driving_route_required','amount_cents':None}
        row['current_availability'] = ({'available_lots':quote['lots_available'],
              'total_lots':quote['total_lots'],'status':quote['availability_status'],
              'timestamp':quote['availability_timestamp'],'timestamp_kind':quote['timestamp_kind'],
              'feed':quote['availability_feed']} if quote else None)
        if row['agency']=='HDB' and row['carpark_id'] in live_current:
            row['current_availability'] = live_current[row['carpark_id']]
        if row['price']['status']!='quoted':
            reasons.append('price_'+row['price']['status'])
        if quote and quote['capacity_consistency']=='available_exceeds_capacity':
            reasons.append('available_exceeds_capacity')
        prediction = None
        available = None
        p_free = None
        if row['arrival_at'] is not None:
            issued = datetime.now(timezone.utc)
            model_request = PredictionRequest(row['agency'],row['carpark_id'],issued,row['arrival_at'])
            try:
                prediction = predictor.predict(model_request)
                if prediction.status=='ok' and (not valid_prediction(prediction,model_request)
                        or (probability_model and prediction.p_free is None)):
                    prediction = None
            except Exception:
                prediction = None
            row['prediction'] = asdict(prediction) if prediction is not None else {'status':'invalid_prediction'}
            if use_model:
                if prediction is not None and valid_prediction(prediction,model_request):
                    available = prediction.available_lots
                    p_free = prediction.p_free
                    try:
                        record_forecast(prediction,row['current_availability'])
                    except (OSError,ValueError):
                        reasons.append('forecast_audit_unavailable_or_target_passed')
                    if prediction.confidence=='low' and not probability_model:
                        reasons.append('low_model_confidence')
                    # Only synchronized HDB capacity can bound this value here.
                    capacity = quote['total_lots'] if quote else None
                    if capacity is not None and available is not None and available > capacity:
                        reasons.append('prediction_exceeds_capacity')
                else:
                    reasons.append('prediction_unavailable')
        else:
            row['prediction'] = {'status':'driving_route_required'}
        if not use_model and quote:
            if quote['availability_status']!='fresh_source_update':
                reasons.append('availability_'+quote['availability_status'])
            else:
                available = quote['lots_available']
        if p_free is not None:
            if p_free < .90:
                reasons.append('arrival_probability_below_0_90')
        elif available is None:
            reasons.append('arrival_probability_missing' if probability_model else 'available_count_missing')
        elif available <= 0:
            reasons.append('no_available_lots_for_ranking')
        row['ranking_basis'] = basis
        row['ranking_exclusions'] = list(dict.fromkeys(reasons))
        row['ranking_eligible'] = not reasons
        row['scoring'] = (score_candidate(row['price']['amount_cents'],request.duration_minutes,
                          row['walking']['distance_meters'],row['driving']['duration_seconds'],available,
                          p_free=p_free)
                          if not reasons else None)
    ranked = rank_candidates(candidates)
    fallback_ranked = current_fallback(candidates,request) if probability_model and not ranked else []
    return {'status':'ok' if ranked else 'current_reading_fallback' if fallback_ranked else 'no_eligible_candidates',
            'prediction_status':('connected' if any(r['prediction']['status']=='ok' for r in candidates)
                                 else 'configured_no_valid_forecast') if use_model else 'prediction_pending',
            'ranking_basis':basis,
            'scoring_policy':PROBABILITY_POLICY_VERSION if probability_model else POLICY_VERSION,
            'policy_is_provisional':True,
            'started_at':started_at, 'departure_at':departure_at, 'generated_at':datetime.now(timezone.utc),
            'duration_minutes':request.duration_minutes, 'candidates':candidates, 'ranked':ranked,
            'top_recommendation':ranked[0] if ranked else None,
            'fallback_ranked':fallback_ranked,
            'fallback_basis':'current_availability_baseline' if fallback_ranked else None,
            'fallback_notice':('No usable arrival forecast. These options use current reported lots; '
                               'availability may change before arrival.') if fallback_ranked else None}


def current_fallback(candidates: list[dict], request: TripRequest) -> list[dict]:
    """Separate current-only list when no forecast ranks; never override a known low probability."""
    allowed={'unsupported_horizon_15_to_90_minutes','historical_profile_not_enabled',
             'model_service_unavailable','unknown_carpark','insufficient_history',
             'live_feed_unavailable','model_error'}
    now=datetime.now(timezone.utc)
    options=[]
    for row in candidates:
        current=row['current_availability'] or {}
        stamp=current.get('timestamp')
        if isinstance(stamp,str):
            try: stamp=datetime.fromisoformat(stamp)
            except ValueError: stamp=None
        count=current.get('available_lots')
        fresh=(isinstance(stamp,datetime) and stamp.utcoffset() is not None
               and timedelta(0)<=now-stamp<=timedelta(minutes=15)
               and current.get('timestamp_kind')=='source_update'
               and current.get('status')=='fresh_source_update')
        allowed_row=(row['prediction']['status'] in allowed and fresh
            and type(count) is int and count>0 and row['price']['status']=='quoted'
            and (current.get('total_lots') is None or
                 (type(current['total_lots']) is int and count<=current['total_lots']))
            and all(row[m]['status']=='ok' for m in ('driving','walking')))
        row['fallback_scoring']=(score_candidate(row['price']['amount_cents'],request.duration_minutes,
             row['walking']['distance_meters'],row['driving']['duration_seconds'],count) if allowed_row else None)
        if allowed_row:
            options.append({**row,'ranking_eligible':True,'scoring':row['fallback_scoring']})
    return rank_candidates(options)


def main():
    import argparse
    import json
    from onemap_adapter import OneMapClient
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin',nargs=2,type=float,required=True,metavar=('LAT','LNG'))
    parser.add_argument('--destination',nargs=2,type=float,required=True,metavar=('LAT','LNG'))
    parser.add_argument('--duration-minutes',type=int,required=True)
    parser.add_argument('--candidate-limit',type=int,default=3)
    parser.add_argument('--radius-meters',type=int,default=1500)
    args=parser.parse_args()
    try:
        client=OneMapClient.from_env()
        request=TripRequest(Coordinate(*args.origin),Coordinate(*args.destination),args.duration_minutes,
                            args.candidate_limit,args.radius_meters)
        from model_adapter import configured_predictor
        print(json.dumps(recommend(request,client,configured_predictor()),default=lambda x:x.isoformat(),indent=2,allow_nan=False))
    except ValueError:
        raise SystemExit('Invalid trip or OneMap configuration; private details withheld.') from None
    except Exception as exc:
        raise SystemExit(f'Recommendation failed ({type(exc).__name__}); connection details withheld.') from None


if __name__=='__main__':
    main()
