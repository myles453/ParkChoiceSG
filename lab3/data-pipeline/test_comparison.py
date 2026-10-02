import unittest
from datetime import date, datetime, timedelta, timezone

from comparison import PriceQuote, compare_carparks, quote_hdb
from unittest.mock import MagicMock, patch


POLICY_AT = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)
RATES = {
    "outside_standard": {"amount_cents": 60, "unit_minutes": 30, "rule_kind": "per_unit"},
    "central_mon_sat_07_17": {"amount_cents": 120, "unit_minutes": 30, "rule_kind": "per_unit"},
    "central_other_hours": {"amount_cents": 60, "unit_minutes": 30, "rule_kind": "per_unit"},
}
HOLIDAYS = {date(2026, 12, 25): "gazetted", date(2026, 11, 9): "observed"}


def carpark(**changes):
    value = {
        "agency": "HDB", "reference_flags_recognized": True,
        "reference_retrieved_at": POLICY_AT,
        "parking_system": "ELECTRONIC PARKING", "short_term_parking": "WHOLE DAY",
        "peak_profile": "none", "central_area": False, "sunday_ph_free_from": None,
    }
    value.update(changes)
    return value


def quote(when, minutes, *, policy_at=POLICY_AT, **changes):
    return quote_hdb(carpark(reference_retrieved_at=policy_at, **changes),
                     when, minutes, RATES, policy_at, HOLIDAYS, {2026},
                     checked_at=when.astimezone(timezone.utc) - timedelta(minutes=5))


class HdbComparisonTests(unittest.TestCase):
    def test_changed_hdb_night_policy_cannot_use_old_price(self):
        row={'agency':'HDB','carpark_id':'A1','night_parking':'NO',
             'display_name':'Example','address':'Example','lots_available':20,'total_lots':100,
             'availability_feed':'hdb_direct','availability_status':'fresh_source_update',
             'evidence_at':POLICY_AT,'timestamp_kind':'source_update','location_points':[],
             'latitude':1.3,'longitude':103.8,'location_status':'single_point',
             'location_source':'hdb_reference','capacity_evidence':100,
             'capacity_source':'availability_snapshot','capacity_evidence_at':POLICY_AT,
             'capacity_consistency':'consistent'}
        schedule={'agency':'HDB','carpark_id':'A1','schedule_id':1,'rules':[],
                  'calculator_config':{'reference_flags':{'night_parking':'YES'}}}
        connection=MagicMock()
        cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect=[[row],[schedule],[],[],[],[]]
        with patch('comparison.quote_schedule') as calculator:
            result=compare_carparks(connection,POLICY_AT,60)[0]
            calculator.assert_not_called()
        self.assertEqual(result['price']['status'],'hdb_reference_changed')
        self.assertFalse(result['price_comparison_eligible'])

    def test_comparison_readiness_does_not_claim_arrival_prediction(self):
        base={"agency":"HDB","carpark_id":"A1","display_name":"Example","address":"Example",
              "lots_available":20,"total_lots":100,"availability_feed":"hdb_direct",
              "availability_status":"fresh_source_update","evidence_at":POLICY_AT,
              "timestamp_kind":"source_update","location_points":[{"latitude":1.3,"longitude":103.8}],
              "latitude":1.3,"longitude":103.8,"location_status":"single_point","location_source":"hdb_reference",
              "capacity_evidence":100,"capacity_source":"availability_snapshot","capacity_evidence_at":POLICY_AT,
              "capacity_consistency":"consistent"}
        for changes,expected in [({},True),({"location_status":"multiple_points"},False),
                                 ({"capacity_consistency":"available_exceeds_capacity"},False),
                                 ({"availability_status":"stale"},False)]:
            with self.subTest(changes=changes):
                connection=MagicMock()
                cursor=connection.cursor.return_value.__enter__.return_value
                cursor.fetchall.side_effect=[[{**base,**changes}],[{"agency":"HDB","carpark_id":"A1","schedule_id":1,"rules":[]}],[],[],[],[]]
                with patch("comparison.quote_schedule",return_value=PriceQuote("quoted",120)):
                    result=compare_carparks(connection,POLICY_AT,60)[0]
                self.assertEqual(result["price_comparison_eligible"],expected)
                self.assertFalse(result["recommendation_eligible"])
                self.assertEqual(result["capacity_evidence"],100)

    def test_eps_grace_and_full_duration_charge(self):
        at = datetime.fromisoformat("2026-09-29T10:00:00+08:00")
        self.assertEqual(quote(at, 15).amount_cents, 0)
        self.assertEqual(quote(at, 16).amount_cents, 32)

    def test_coupon_payment_method_changes_quote(self):
        at = datetime.fromisoformat("2026-09-29T10:00:00+08:00")
        coupon = carpark(parking_system="COUPON PARKING")
        parking_sg = quote_hdb(coupon, at, 20, RATES, POLICY_AT, HOLIDAYS,
                               {2026}, checked_at=POLICY_AT + timedelta(days=1))
        paper = quote_hdb(coupon, at, 20, RATES, POLICY_AT, HOLIDAYS,
                          {2026}, payment_method="paper_coupon",
                          checked_at=POLICY_AT + timedelta(days=1))
        self.assertEqual((parking_sg.amount_cents, paper.amount_cents), (40, 60))

    def test_central_day_and_boundary(self):
        at = datetime.fromisoformat("2026-09-29T16:00:00+08:00")
        self.assertEqual(quote(at, 30, central_area=True).amount_cents, 120)
        self.assertEqual(quote(at, 90, central_area=True).status, "rate_boundary_unreviewed")

    def test_sunday_and_holiday_free_window(self):
        free = {"sunday_ph_free_from": datetime.strptime("13:00", "%H:%M").time()}
        sunday = datetime.fromisoformat("2026-10-04T13:00:00+08:00")
        holiday = datetime.fromisoformat("2026-12-25T13:00:00+08:00")
        self.assertEqual(quote(sunday, 60, **free).amount_cents, 0)
        self.assertEqual(quote(holiday, 60, policy_at=datetime(2026, 12, 24, tzinfo=timezone.utc),
                               **free).amount_cents, 0)
        self.assertEqual(quote(sunday - timedelta(minutes=30), 60, **free).status,
                         "free_boundary_unreviewed")

    def test_unsupported_cases_fail_closed(self):
        daytime = datetime.fromisoformat("2026-09-29T10:00:00+08:00")
        self.assertEqual(quote(daytime, 30, peak_profile="acb_cy").status,
                         "peak_tariff_unreviewed")
        self.assertEqual(quote(daytime, 30, short_term_parking="NO").status,
                         "no_short_term_parking")
        self.assertEqual(quote(daytime, 300).status, "unsupported_duration")
        observed = datetime.fromisoformat("2026-11-09T10:00:00+08:00")
        self.assertEqual(quote(observed, 30,
                               policy_at=datetime(2026, 11, 8, tzinfo=timezone.utc)).status,
                         "observed_holiday_unreviewed")
        night = datetime.fromisoformat("2026-09-29T22:00:00+08:00")
        self.assertEqual(quote(night, 60).status, "outside_short_term_hours")

    def test_stale_policy_or_reference_cannot_quote(self):
        at = datetime.fromisoformat("2026-09-29T10:00:00+08:00")
        stale = quote_hdb(carpark(), POLICY_AT + timedelta(days=31), 30,
                          RATES, POLICY_AT, HOLIDAYS, {2026},
                          checked_at=POLICY_AT + timedelta(days=31) - timedelta(minutes=5))
        self.assertEqual(stale.status, "policy_stale")
        far_future = quote_hdb(carpark(), at + timedelta(days=3), 30,
                               RATES, POLICY_AT, HOLIDAYS, {2026},
                               checked_at=at.astimezone(timezone.utc))
        self.assertEqual(far_future.status, "arrival_out_of_range")


if __name__ == "__main__":
    unittest.main()
