"""Request-specific carpark comparison using the private parking_data schema.

Source-backed, versioned HDB, URA and operator schedules are loaded from the DB.
Unknown windows, stale rates and disputed source facts remain unquoted.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from datetime import date, datetime, time, timedelta, timezone
from math import ceil
from typing import Any, Mapping
from pricing import PriceQuote, quote_schedule
# Singapore uses UTC+08:00. Fixed offset avoids an optional tzdata dependency
# on Windows for the current pilot's 2026 tariff calendar.
SINGAPORE = timezone(timedelta(hours=8), "SGT")
HDB_RATE_URL = (
    "https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/"
    "shortterm-parking-charges"
)
SUPPORTED_POLICY_AGE = timedelta(days=30)
MAX_SUPPORTED_MINUTES = 240
MAX_ARRIVAL_HORIZON = timedelta(hours=24)


def _unavailable(status: str, note: str) -> PriceQuote:
    return PriceQuote(status=status, note=note)


def quote_hdb(
    carpark: Mapping[str, Any],
    arrival_at: datetime,
    duration_minutes: int,
    policy_rates: Mapping[str, Mapping[str, Any]],
    policy_checked_at: datetime,
    holidays: Mapping[date, str],
    covered_years: set[int],
    *,
    payment_method: str = "parking_sg",
    checked_at: datetime | None = None,
) -> PriceQuote:
    """Legacy daytime-only helper retained for compatibility with earlier callers.

    The current comparison path uses pricing.quote_schedule and database schedules.

    Input times are aware instants, duration is whole minutes, and amounts are cents.
    Paper coupon pricing rounds the whole stay up to half-hour units. EPS and
    Parking.sg use per-minute pricing; EPS is free only when the whole stay is
    within its 15-minute grace period.
    """
    if arrival_at.tzinfo is None or arrival_at.utcoffset() is None:
        raise ValueError("arrival_at must be timezone-aware")
    if not isinstance(duration_minutes, int) or isinstance(duration_minutes, bool) or duration_minutes <= 0:
        raise ValueError("duration_minutes must be a positive whole number")
    if arrival_at.second or arrival_at.microsecond:
        raise ValueError("arrival_at must have minute precision")
    if payment_method not in {"parking_sg", "paper_coupon"}:
        raise ValueError("payment_method must be parking_sg or paper_coupon")
    if duration_minutes > MAX_SUPPORTED_MINUTES:
        return _unavailable("unsupported_duration", "Day caps and longer-stay rules are not yet calculated.")
    checked_at = checked_at or datetime.now(timezone.utc)
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("checked_at must be timezone-aware")
    if arrival_at < checked_at - timedelta(minutes=15) or arrival_at > checked_at + MAX_ARRIVAL_HORIZON:
        return _unavailable("arrival_out_of_range", "Quote only near-term arrival times using the current policy.")
    if policy_checked_at.tzinfo is None or policy_checked_at.utcoffset() is None:
        raise ValueError("policy_checked_at must be timezone-aware")
    if policy_checked_at > checked_at + timedelta(minutes=2) or checked_at - policy_checked_at > SUPPORTED_POLICY_AGE:
        return _unavailable("policy_stale", "Recheck the published HDB tariff before quoting.")
    reference_at = carpark.get("reference_retrieved_at")
    if (not isinstance(reference_at, datetime) or reference_at.tzinfo is None
            or reference_at > checked_at + timedelta(minutes=2)
            or checked_at - reference_at > SUPPORTED_POLICY_AGE):
        return _unavailable("reference_stale", "Refresh the HDB carpark policy flags.")
    if carpark.get("agency") != "HDB" or not carpark.get("reference_flags_recognized"):
        return _unavailable("reference_unverified", "Carpark policy flags are missing or unrecognized.")
    if carpark.get("peak_profile") != "none":
        return _unavailable("peak_tariff_unreviewed", "Peak-window and cap behavior needs review.")
    if carpark.get("short_term_parking") == "NO":
        return _unavailable("no_short_term_parking", "HDB reference does not allow short-term parking.")

    start = arrival_at.astimezone(SINGAPORE)
    end = start + timedelta(minutes=duration_minutes)
    if start.date() != end.date():
        return _unavailable("overnight_unreviewed", "Night and cross-day charges are not yet calculated.")
    if start.year not in covered_years:
        return _unavailable("holiday_calendar_missing", "This year's public-holiday calendar is not loaded.")
    holiday_kind = holidays.get(start.date())
    if holiday_kind == "observed":
        return _unavailable("observed_holiday_unreviewed", "Provider treatment of observed Mondays is unconfirmed.")
    is_sunday_ph = start.weekday() == 6 or holiday_kind == "gazetted"

    opening_end = time(19) if carpark.get("short_term_parking") == "7AM-7PM" else time(22, 30)
    if start.time() < time(7) or end.time() > opening_end:
        return _unavailable("outside_short_term_hours", "Stay extends outside the published daytime short-term hours.")
    if carpark.get("short_term_parking") not in {"WHOLE DAY", "7AM-10.30PM", "7AM-7PM"}:
        return _unavailable("short_term_hours_unknown", "Short-term hours are not supported.")

    system = carpark.get("parking_system")
    if system not in {"ELECTRONIC PARKING", "COUPON PARKING"}:
        return _unavailable("payment_system_unknown", "Payment system is not supported.")
    if system == "ELECTRONIC PARKING" and payment_method == "paper_coupon":
        return _unavailable("payment_method_invalid", "Paper coupons do not apply to an EPS carpark.")
    actual_method = "eps" if system == "ELECTRONIC PARKING" else payment_method
    free_from = carpark.get("sunday_ph_free_from")
    if is_sunday_ph and free_from is not None:
        if start.time() < free_from < end.time():
            return _unavailable("free_boundary_unreviewed", "Stay crosses the start of free parking.")
        if start.time() >= free_from:
            return PriceQuote("quoted", 0, actual_method, HDB_RATE_URL, "Sunday/PH free parking; general car lots only.")
    if system == "ELECTRONIC PARKING" and duration_minutes <= 15:
        return PriceQuote("quoted", 0, "eps", HDB_RATE_URL, "EPS grace applies only if exit is within 15 minutes.")

    if carpark.get("central_area") and not is_sunday_ph:
        if start.time() < time(17) < end.time():
            return _unavailable("rate_boundary_unreviewed", "Stay crosses the Central Area 17:00 rate change.")
        rule_code = "central_mon_sat_07_17" if start.time() < time(17) else "central_other_hours"
    elif carpark.get("central_area"):
        rule_code = "central_other_hours"
    else:
        rule_code = "outside_standard"
    rule = policy_rates.get(rule_code)
    if not rule or rule.get("rule_kind") != "per_unit" or rule.get("unit_minutes") != 30:
        return _unavailable("rate_rule_missing", "Published HDB rate rule is missing or changed.")
    amount_per_unit = rule.get("amount_cents")
    if not isinstance(amount_per_unit, int) or amount_per_unit < 0:
        return _unavailable("rate_rule_invalid", "Published HDB rate has no valid amount.")
    if actual_method == "paper_coupon":
        amount = ceil(duration_minutes / 30) * amount_per_unit
    else:
        # Supported standard HDB rates divide exactly into whole cents/minute.
        if amount_per_unit % 30:
            return _unavailable("rounding_unreviewed", "Per-minute rounding for this tariff needs review.")
        amount = duration_minutes * (amount_per_unit // 30)
    return PriceQuote("quoted", amount, actual_method, rule.get("source_url") or HDB_RATE_URL,
                      "Estimate assumes the stated arrival, duration and payment method.")


def compare_carparks(connection: Any, arrival_at: datetime, duration_minutes: int,
                     *, payment_method: str = "parking_sg", first_entry: bool | None = None) -> list[dict[str, Any]]:
    """Return evidence and quote statuses for all canonical carpark identities."""
    from psycopg.rows import dict_row

    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("SELECT * FROM parking_data.carpark_candidate_inputs ORDER BY agency, carpark_id")
        carparks = cursor.fetchall()
        cursor.execute("""SELECT s.*, ir.retrieved_at AS source_captured_at,
                                 coalesce(r.rules,'[]'::jsonb) AS rules
          FROM parking_data.rate_schedules s
          LEFT JOIN parking_data.ingestion_runs ir ON ir.run_id=s.source_run_id
          LEFT JOIN LATERAL (
            SELECT jsonb_agg(to_jsonb(rr)) AS rules
            FROM parking_data.rate_schedule_rules rr WHERE rr.schedule_id=s.schedule_id
          ) r ON true
          WHERE s.review_status='verified' AND s.calculator_key IS NOT NULL
            AND s.valid_from <= %s AND (s.valid_until IS NULL OR s.valid_until > %s)
          ORDER BY s.agency,s.carpark_id,s.valid_from DESC""",(arrival_at,arrival_at))
        schedule_rows = cursor.fetchall()
        cursor.execute("SELECT holiday_date, holiday_kind FROM parking_data.sg_public_holidays")
        holidays = {r["holiday_date"]: r["holiday_kind"] for r in cursor.fetchall()}
        cursor.execute("SELECT calendar_year FROM parking_data.sg_holiday_year_coverage")
        covered_years = {r["calendar_year"] for r in cursor.fetchall()}
        cursor.execute("SELECT carpark_id FROM parking_data.hdb_loading_bay_tariffs")
        loading_bays = {r['carpark_id'] for r in cursor.fetchall()}
        cursor.execute("""SELECT s.schedule_id,r.start_time,r.end_time,d.day_type
          FROM parking_data.rate_schedules s
          JOIN parking_data.ura_rate_rows r ON r.run_id=s.source_run_id AND r.pp_code=s.carpark_id
          JOIN parking_data.ura_rate_day_rules d USING (run_id,row_number)
          WHERE s.review_status='verified' AND s.source='ura_details'
            AND r.vehicle_category='Car' AND d.interpretation<>'per_unit'
            AND NOT EXISTS (SELECT 1 FROM parking_data.rate_schedule_rules rr
              WHERE rr.schedule_id=s.schedule_id AND rr.source_run_id=d.run_id
                AND rr.source_row_number=d.row_number AND rr.source_day_type=d.day_type
                AND rr.review_status='verified')""")
        blocked_windows = cursor.fetchall()
    schedules = {}
    for schedule in schedule_rows:
        schedules.setdefault((schedule['agency'],schedule['carpark_id']),schedule)
    by_id = {s['schedule_id']:s for s in schedules.values()}
    for row in blocked_windows:
        if row['schedule_id'] in by_id:
            unknown_time = row['start_time'] is None or row['end_time'] is None
            by_id[row['schedule_id']]['rules'].append({
                'day_type':row['day_type'],'start_time':row['start_time'] or time(0),
                'end_time':row['end_time'] or time(0),'rule_kind':'free','amount_cents':0,
                'review_status':'pending_review','calculation':{
                    'blocks_quote':True,'full_day':unknown_time or row['start_time']==row['end_time']}})
    checked_at = datetime.now(timezone.utc)
    results = []
    for row in carparks:
        schedule = schedules.get((row['agency'],row['carpark_id']))
        if row['agency']=='HDB' and row['carpark_id'] in loading_bays:
            quote = _unavailable('loading_bay_not_general_parking','Restricted-purpose loading bay; excluded from parking recommendations.')
        elif row['agency']=='HDB' and row.get('short_term_parking')=='NO':
            quote = _unavailable('no_short_term_parking','Short-term parking is not offered.')
        elif schedule:
            config = schedule.get('calculator_config') or {}
            baseline = config.get('reference_flags') if row['agency']=='HDB' else None
            if baseline and any(row.get(field) != value for field,value in baseline.items()):
                quote = _unavailable('hdb_reference_changed',
                    'Parking policy flags changed since this tariff was compiled; review the affected rules.')
            else:
                # Fresh unchanged facility flags do not extend policy review age.
                if baseline:
                    schedule = {**schedule,'calculator_config':{
                        **config,'reference_retrieved_at':row['reference_retrieved_at']}}
                quote = quote_schedule(schedule,schedule['rules'],arrival_at,duration_minutes,
                                       holidays,covered_years,payment_method=payment_method,
                                       first_entry=first_entry,checked_at=checked_at)
        else:
            quote = _unavailable("tariff_unverified", "No approved calculator for this carpark's tariff.")
        # Retrieval-only feeds have no per-carpark source update timestamp.
        # Keep them visible for inspection, but do not imply confirmed freshness.
        ready = (row["availability_status"] == "fresh_source_update"
                 and row["lots_available"] is not None and row["lots_available"] > 0
                 and quote.status == "quoted"
                 and row["location_status"] == "single_point"
                 and row["capacity_consistency"] != "available_exceeds_capacity")
        results.append({"agency": row["agency"], "carpark_id": row["carpark_id"],
                        "display_name": row["display_name"], "address": row["address"],
                        "lots_available": row["lots_available"], "total_lots": row["total_lots"],
                        "availability_feed": row["availability_feed"],
                        "availability_status": row["availability_status"],
                        "availability_timestamp": row["evidence_at"],
                        "timestamp_kind": row["timestamp_kind"],
                        "location_points": row["location_points"],
                        "latitude": row["latitude"], "longitude": row["longitude"],
                        "location_status": row["location_status"],
                        "location_source": row["location_source"],
                        "capacity_evidence": row["capacity_evidence"],
                        "capacity_source": row["capacity_source"],
                        "capacity_evidence_at": row["capacity_evidence_at"],
                        "capacity_consistency": row["capacity_consistency"],
                        "price": asdict(quote), "price_comparison_eligible": ready,
                        "recommendation_eligible": False,
                        "arrival_recommendation_status": "prediction_and_route_estimates_required"})
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect price/availability comparison readiness")
    parser.add_argument("--arrival", required=True, help="ISO 8601 arrival instant with timezone, minute precision")
    parser.add_argument("--duration-minutes", required=True, type=int)
    parser.add_argument("--payment-method", choices=("parking_sg", "paper_coupon"), default="parking_sg")
    parser.add_argument("--first-entry", choices=('yes','no','unknown'), default='unknown',
                        help='Whether the vehicle has already entered the same carpark today')
    parser.add_argument("--show-unready", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    arrival_at = datetime.fromisoformat(args.arrival)
    from provider_puller import load_local_env
    load_local_env()
    if not os.environ.get("DATABASE_URL"):
        parser.error("DATABASE_URL is not set; configure a trusted server-side database connection")
    import psycopg

    with psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None,
                         connect_timeout=15) as connection:
        rows = compare_carparks(connection, arrival_at, args.duration_minutes,
                                payment_method=args.payment_method,
                                first_entry={'yes':True,'no':False,'unknown':None}[args.first_entry])
    shown = rows if args.show_unready else [r for r in rows if r["price_comparison_eligible"]]
    print(json.dumps({"total_carparks": len(rows),
                      "price_comparison_eligible": sum(r["price_comparison_eligible"] for r in rows),
                      "recommendation_eligible": 0,
                      "displayed": shown[:args.limit]}, default=str, indent=2))


if __name__ == "__main__":
    main()
