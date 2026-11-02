"""Generated replacement class for the isolated Lab 4 reconstruction exercise.

Inserted into the prepared module, which supplies the imports and helper functions.
This file is evidence of the experiment, not an additional production controller.
"""


class RecommendationController:
    def __init__(self, router, predictor=None):
        self.router = router
        self.predictor = predictor if predictor is not None else PendingPredictor()

    def recommend(self, request):
        predictor = self.predictor
        configured = getattr(predictor, 'ready', False) is True
        probability_mode = configured and getattr(predictor, 'output_kind', None) == 'probability'
        basis = ('arrival_free_probability' if probability_mode else 'predicted_availability') if configured else 'current_availability_baseline'
        started = datetime.now(timezone.utc)
        with read_connection() as connection:
            candidates = shortlist(connection, request, current_baseline=not configured,
                                   supported_agencies=getattr(predictor, 'supported_agencies', None))
        for candidate in candidates:
            point = Coordinate(candidate['latitude'], candidate['longitude'])
            candidate['driving'] = asdict(self.router.route(request.origin, point, 'drive'))
            candidate['walking'] = asdict(self.router.route(point, request.destination, 'walk'))
        departure = datetime.now(timezone.utc)
        for candidate in candidates:
            driving = candidate['driving']
            arrival = departure + timedelta(seconds=driving['duration_seconds']) if driving['status'] == 'ok' else None
            candidate['arrival_at'] = arrival
            driving.update(estimated_arrival_at=arrival,
                           departure_assumption='common_departure_after_route_collection')
        with read_connection() as connection:
            quotes = quote_arrivals(connection, candidates, request)
        live = predictor.current_readings([c['carpark_id'] for c in candidates]) if (
            probability_mode and hasattr(predictor, 'current_readings')) else {}

        for candidate in candidates:
            exclusions = [mode+'_'+candidate[mode]['status'] for mode in ('driving', 'walking')
                          if candidate[mode]['status'] != 'ok']
            quote = quotes.get((candidate['agency'], candidate['carpark_id']))
            candidate['price'] = quote['price'] if quote else {'status': 'driving_route_required', 'amount_cents': None}
            current = None if not quote else {
                'available_lots': quote['lots_available'], 'total_lots': quote['total_lots'],
                'status': quote['availability_status'], 'timestamp': quote['availability_timestamp'],
                'timestamp_kind': quote['timestamp_kind'], 'feed': quote['availability_feed'],
            }
            if candidate['agency'] == 'HDB' and candidate['carpark_id'] in live:
                current = live[candidate['carpark_id']]
            candidate['current_availability'] = current
            if candidate['price']['status'] != 'quoted':
                exclusions.append('price_'+candidate['price']['status'])
            if quote and quote['capacity_consistency'] == 'available_exceeds_capacity':
                exclusions.append('available_exceeds_capacity')
            count = probability = None
            if candidate['arrival_at'] is None:
                candidate['prediction'] = {'status': 'driving_route_required'}
            else:
                model_request = PredictionRequest(candidate['agency'], candidate['carpark_id'],
                                                  datetime.now(timezone.utc), candidate['arrival_at'])
                try:
                    forecast = predictor.predict(model_request)
                    if forecast.status == 'ok' and (not valid_prediction(forecast, model_request)
                            or (probability_mode and forecast.p_free is None)):
                        forecast = None
                except Exception:
                    forecast = None
                candidate['prediction'] = asdict(forecast) if forecast is not None else {'status': 'invalid_prediction'}
                if configured:
                    if forecast is not None and valid_prediction(forecast, model_request):
                        count, probability = forecast.available_lots, forecast.p_free
                        try:
                            record_forecast(forecast, current)
                        except (OSError, ValueError):
                            exclusions.append('forecast_audit_unavailable_or_target_passed')
                        if not probability_mode and forecast.confidence == 'low':
                            exclusions.append('low_model_confidence')
                        capacity = quote['total_lots'] if quote else None
                        if capacity is not None and count is not None and count > capacity:
                            exclusions.append('prediction_exceeds_capacity')
                    else:
                        exclusions.append('prediction_unavailable')
            if not configured and quote:
                if quote['availability_status'] == 'fresh_source_update':
                    count = quote['lots_available']
                else:
                    exclusions.append('availability_'+quote['availability_status'])
            if probability is not None:
                if probability < .90:
                    exclusions.append('arrival_probability_below_0_90')
            elif count is None:
                exclusions.append('arrival_probability_missing' if probability_mode else 'available_count_missing')
            elif count <= 0:
                exclusions.append('no_available_lots_for_ranking')
            candidate.update(ranking_basis=basis, ranking_exclusions=list(dict.fromkeys(exclusions)),
                             ranking_eligible=not exclusions)
            candidate['scoring'] = None if exclusions else score_candidate(
                candidate['price']['amount_cents'], request.duration_minutes,
                candidate['walking']['distance_meters'], candidate['driving']['duration_seconds'],
                count, p_free=probability, ranking_mode=request.ranking_mode)

        ranked = rank_candidates(candidates, request.ranking_mode)
        fallback = current_fallback(candidates, request) if probability_mode and not ranked else []
        return {
            'status': 'ok' if ranked else 'current_reading_fallback' if fallback else 'no_eligible_candidates',
            'prediction_status': ('connected' if any(c['prediction']['status'] == 'ok' for c in candidates)
                                  else 'configured_no_valid_forecast') if configured else 'prediction_pending',
            'ranking_basis': basis, 'ranking_mode': request.ranking_mode,
            'ranking_mode_label': MODE_LABELS[request.ranking_mode],
            'scoring_policy': policy_version(request.ranking_mode, probability=probability_mode),
            'scoring_weights': mode_weights(request.ranking_mode),
            'fallback_scoring_policy': policy_version(request.ranking_mode) if fallback else None,
            'policy_is_provisional': True, 'started_at': started, 'departure_at': departure,
            'generated_at': datetime.now(timezone.utc), 'duration_minutes': request.duration_minutes,
            'candidates': candidates, 'ranked': ranked, 'top_recommendation': ranked[0] if ranked else None,
            'fallback_ranked': fallback, 'fallback_basis': 'current_availability_baseline' if fallback else None,
            'fallback_notice': ('No usable arrival forecast. These options use current reported lots; '
                                'availability may change before arrival.') if fallback else None,
        }
