"""Source-backed motor-car tariff calculation (Singapore local time, exact cents).

Schedules may cover only part of a day. Missing or ambiguous evidence prevents a
quote; a zero/zero provider value is never silently treated as free parking.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from fractions import Fraction
from math import ceil
from typing import Any, Mapping

SINGAPORE = timezone(timedelta(hours=8), "SGT")


@dataclass(frozen=True)
class PriceQuote:
    status: str
    amount_cents: int | None = None
    payment_method: str | None = None
    source_url: str | None = None
    note: str | None = None
    schedule_id: int | None = None
    breakdown: tuple = ()


def unavailable(status, note):
    return PriceQuote(status=status, note=note)


def _aware(value, name):
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _clock(value):
    return time.fromisoformat(value) if isinstance(value, str) else value


def day_type(day, holidays):
    if day in holidays:
        return "public_holiday"
    if day.weekday() == 6:
        return "sunday"
    if day.weekday() == 5:
        return "saturday"
    return "weekday"


def window_at(rule, instant, holidays):
    """Return a concrete [start,end) interval; day type belongs to its anchor day."""
    config = rule.get("calculation") or {}
    opening, closing = _clock(rule["start_time"]), _clock(rule["end_time"])
    if opening == closing and not config.get("full_day"):
        return None
    for day in (instant.date(), instant.date() - timedelta(days=1)):
        start = datetime.combine(day, opening, SINGAPORE)
        end = datetime.combine(day, closing, SINGAPORE)
        if closing <= opening:
            end += timedelta(days=1)
        if not start <= instant < end:
            continue
        kind = day_type(day, holidays)
        if rule["day_type"] not in {kind, "all"} and not (
                rule["day_type"] == "sunday_ph" and kind in {"sunday", "public_holiday"}):
            continue
        weekdays = config.get("weekdays")
        if weekdays is not None and day.weekday() not in weekdays:
            continue
        eve = day + timedelta(days=1) in holidays
        if config.get("ph_eve") is not None and config["ph_eve"] != eve:
            continue
        return start, end
    return None


def _signature(rule):
    config = rule.get("calculation") or {}
    import json
    return (rule["rule_kind"], rule["amount_cents"], rule.get("unit_minutes"),
            json.dumps(config, sort_keys=True))


def _tier_price(rule, minutes, first_entry):
    config = rule.get("calculation") or {}
    tiers = config.get("tiers", [])
    if config.get("first_entry_required"):
        if first_entry is None:
            return None
        if not first_entry:
            tiers = config.get("repeat_entry_tiers")
            if tiers is None:
                return None
    amount, remaining = 0, minutes
    for tier in tiers:
        used = min(remaining, tier["duration_minutes"])
        if used:
            amount += ceil(Fraction(used, tier["unit_minutes"])) * tier["amount_cents"]
            remaining -= used
    if remaining:
        amount += ceil(Fraction(remaining, rule["unit_minutes"])) * rule["amount_cents"]
    return Fraction(amount)


def quote_schedule(schedule: Mapping[str, Any], rules: list[dict], arrival_at: datetime,
                   duration_minutes: int, holidays: Mapping[date, str], covered_years: set[int],
                   *, payment_method="parking_sg", first_entry: bool | None = None,
                   checked_at: datetime | None = None) -> PriceQuote:
    arrival_at = _aware(arrival_at, "arrival_at")
    checked_at = _aware(checked_at or datetime.now(timezone.utc), "checked_at")
    if arrival_at.second or arrival_at.microsecond:
        raise ValueError("arrival_at must have minute precision")
    if type(duration_minutes) is not int or duration_minutes <= 0:
        raise ValueError("duration_minutes must be a positive integer")
    if payment_method not in {"parking_sg", "paper_coupon"}:
        raise ValueError("payment_method must be parking_sg or paper_coupon")
    if first_entry is not None and type(first_entry) is not bool:
        raise ValueError("first_entry must be true, false or unknown")
    if duration_minutes > 1440:
        return unavailable("unsupported_duration", "This calculator supports stays up to 24 hours.")
    if not checked_at - timedelta(minutes=15) <= arrival_at <= checked_at + timedelta(hours=24):
        return unavailable("arrival_out_of_range", "Use a near-term arrival with current published tariffs.")
    if schedule.get("review_status") != "verified" or schedule.get("calculator_key") != "window_rules_v1":
        return unavailable("tariff_unverified", "This schedule has no approved calculator.")
    start = arrival_at.astimezone(SINGAPORE)
    end = start + timedelta(minutes=duration_minutes)
    valid_from = _aware(schedule["valid_from"], "valid_from")
    valid_until = schedule.get("valid_until")
    if start < valid_from or (valid_until and end > _aware(valid_until, "valid_until")):
        return unavailable("schedule_out_of_range", "The tariff version does not cover the whole stay.")
    config = schedule.get("calculator_config") or {}
    age_limit = timedelta(days=2 if config.get("agency") == "URA" else 30)
    reviewed = _aware(schedule["reviewed_at"], "reviewed_at")
    if reviewed > checked_at + timedelta(minutes=2) or checked_at - reviewed > age_limit:
        return unavailable("policy_stale", "Refresh/review the published tariff before quoting.")
    if config.get("agency") == "URA" and schedule.get("source_captured_at"):
        captured = _aware(schedule["source_captured_at"], "source_captured_at")
        if captured > checked_at + timedelta(minutes=2) or checked_at - captured > timedelta(days=2):
            return unavailable("rate_capture_stale", "Fetch the latest daily URA tariff capture.")
    if config.get("reference_retrieved_at"):
        reference = _aware(config["reference_retrieved_at"], "reference_retrieved_at")
        if reference > checked_at + timedelta(minutes=2) or checked_at - reference > timedelta(days=30):
            return unavailable("reference_stale", "Refresh the HDB facility flags.")
    system = config.get("parking_system")
    method = "eps" if system in {"B", "ELECTRONIC PARKING", "operator_eps"} else payment_method
    if method == "eps" and payment_method == "paper_coupon":
        return unavailable("payment_method_invalid", "Paper coupons do not apply to an EPS carpark.")
    minutes = [start + timedelta(minutes=i) for i in range(duration_minutes)]
    if any(t.year not in covered_years for t in minutes):
        return unavailable("holiday_calendar_missing", "Load the public-holiday calendar for every year in the stay.")
    if any(holidays.get(t.date()) == "observed" for t in minutes):
        return unavailable("observed_holiday_unreviewed", "Tariff treatment of observed holidays remains unconfirmed.")
    if config.get("ph_peak_unconfirmed") and any(t.date() in holidays for t in minutes):
        return unavailable("peak_holiday_unreviewed", "HDB's weekday/weekend peak table does not specify PH treatment.")
    selected, caps = [], defaultdict(list)
    for i, instant in enumerate(minutes):
        choices = []
        for rule in rules:
            interval = window_at(rule, instant, holidays)
            if interval is None:
                continue
            calc = rule.get("calculation") or {}
            if rule.get("review_status") != "verified":
                if calc.get("blocks_quote"):
                    return unavailable("rate_window_unreviewed", "The stay enters a missing or ambiguous provider tariff window.")
                continue
            if rule["rule_kind"] == "cap":
                if not calc.get("payment_methods") or method in calc["payment_methods"]:
                    caps[(calc.get("cap_group", "cap"), *interval, rule["amount_cents"])].append(i)
                continue
            choices.append((rule, interval))
        if not choices:
            return unavailable("rate_window_missing", "No approved tariff/short-term permission covers part of this stay.")
        priority = max(r.get("priority", 100) for r, _ in choices)
        winners = [(r, w) for r, w in choices if r.get("priority", 100) == priority]
        if len({_signature(r) for r, _ in winners}) > 1:
            return unavailable("rate_conflict", "Conflicting equal-priority tariffs require review.")
        chosen, interval = winners[0]
        # A Saturday-to-Sunday transition may affect an overnight URA tariff;
        # the API does not specify which date controls it. Avoid guessing.
        if config.get("agency") == "URA" and instant.date() != interval[0].date():
            if day_type(instant.date(), holidays) != day_type(interval[0].date(), holidays):
                return unavailable("overnight_day_type_unreviewed", "Confirm URA's day-category treatment across midnight.")
        selected.append((chosen, interval))
    grace = schedule.get("grace_minutes")
    if grace is None:
        return unavailable("grace_policy_unpublished", "The operator's grace policy is not published in this capture.")
    if duration_minutes <= grace and method == "eps":
        return PriceQuote("quoted", 0, method, schedule.get("source_url"),
                          "Exit within the published grace period; no deductible free minutes after it.",
                          schedule.get("schedule_id"))
    bands = {(_signature(r), *w) for r, w in selected}
    if config.get("no_cross_window") and len(bands) > 1:
        # Esplanade's one continuous hourly tariff does not reset at midnight.
        if not (config.get("continuous_full_day") and len({_signature(r) for r, _ in selected}) == 1):
            return unavailable("operator_boundary_unreviewed", "Confirm charging across the operator's tariff/day boundary.")
    if method == "paper_coupon" and len({_signature(r) for r, _ in selected}) > 1:
        return unavailable("paper_boundary_unreviewed", "Confirm paper-coupon coverage across different tariff bands.")
    charges = [Fraction(0)] * duration_minutes
    groups = defaultdict(list)
    for i, (rule, interval) in enumerate(selected):
        groups[(_signature(rule), *interval)].append(i)
    if config.get("continuous_full_day"):
        groups = {("continuous",): list(range(duration_minutes))}
    details = []
    for indices in groups.values():
        rule = selected[indices[0]][0]
        kind = rule["rule_kind"]
        if kind == "free":
            total = Fraction(0)
        elif kind == "flat":
            total = Fraction(rule["amount_cents"])
        elif kind == "per_unit":
            calc = rule.get("calculation") or {}
            billing = calc.get("billing") or ("round_up_unit" if method == "paper_coupon" else "per_minute")
            if calc.get("tiers"):
                total = _tier_price(rule, len(indices), first_entry)
                if total is None:
                    return unavailable("first_entry_unknown", "This tariff needs the vehicle's first-entry status for the day.")
            elif billing == "round_up_unit":
                total = Fraction(ceil(Fraction(len(indices), rule["unit_minutes"])) * rule["amount_cents"])
            elif billing == "per_minute":
                total = Fraction(len(indices) * rule["amount_cents"], rule["unit_minutes"])
            else:
                return unavailable("billing_unreviewed", "Unsupported billing convention.")
        else:
            return unavailable("rule_kind_unreviewed", "Unsupported tariff rule kind.")
        for i in indices:
            charges[i] = total / len(indices)
        details.append({"description": rule.get("description"), "minutes": len(indices),
                        "before_caps_cents": str(total)})
    # Apply nested night caps before the larger parking-day cap. Exact fractions
    # retain cents accurately; no floating-point or guessed fractional-cent rule.
    for (group, lower, upper, ceiling), indices in sorted(caps.items(), key=lambda item: item[0][2]-item[0][1]):
        subtotal = sum(charges[i] for i in indices)
        if subtotal > ceiling:
            for i in indices:
                charges[i] *= Fraction(ceiling) / subtotal
            details.append({"cap": group, "amount_cents": ceiling,
                            "window_start": lower.isoformat(), "window_end": upper.isoformat()})
    total = sum(charges)
    if config.get("day_cap_unconfirmed"):
        day_charge = sum(charges[i] for i, t in enumerate(minutes) if time(7) <= t.time() < time(22, 30))
        if day_charge >= config.get("maximum_uncapped_day_cents", 1200):
            return unavailable("day_cap_unreviewed", "Confirm this URA carpark's whole-day cap before quoting a long stay.")
    if method == "paper_coupon" and config.get("paper_day_cap_unconfirmed"):
        day_charge = sum(charges[i] for i, t in enumerate(minutes) if time(7) <= t.time() < time(22, 30))
        if day_charge >= 1200:
            return unavailable("paper_day_cap_unreviewed", "Confirm paper-coupon whole-day charging before quoting.")
    if total.denominator != 1:
        return unavailable("rounding_unreviewed", "The amount contains a fractional cent; provider rounding needs confirmation.")
    return PriceQuote("quoted", int(total), method, schedule.get("source_url"),
                      "Estimate for general motor-car parking at the stated arrival and duration; discounts excluded.",
                      schedule.get("schedule_id"), tuple(details))
