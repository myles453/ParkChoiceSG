from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from datetime import date, datetime, timedelta, timezone

from comparison import CandidateStay, PriceQuote, compare_candidate_stays, compare_carparks, quote_hdb
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
        schedule={'agency':'HDB','carpark_id':'A1','schedule_id':1,'rules':[], 'valid_from':POLICY_AT,
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
                cursor.fetchall.side_effect=[[{**base,**changes}],[{"agency":"HDB","carpark_id":"A1","schedule_id":1,"rules":[],"valid_from":POLICY_AT}],[],[],[],[]]
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


class CandidateComparisonTests(unittest.TestCase):
    AT = datetime.fromisoformat('2026-10-02T16:40:00+08:00')

    def row(self, agency='HDB', code='BBB', **changes):
        return {"agency":agency,"carpark_id":code,"display_name":"Example","address":"Example",
                "lots_available":20,"total_lots":100,"availability_feed":"hdb_direct",
                "availability_status":"fresh_source_update","evidence_at":self.AT,
                "timestamp_kind":"source_update","location_points":[{"latitude":1.3,"longitude":103.8}],
                "latitude":1.3,"longitude":103.8,"location_status":"single_point","location_source":"hdb_reference",
                "capacity_evidence":100,"capacity_source":"availability_snapshot","capacity_evidence_at":self.AT,
                "capacity_consistency":"consistent", **changes}

    def schedule(self, agency='HDB', code='BBB', ident=1, **changes):
        base = {'day_type':'all','start_time':'07:00','end_time':'22:30',
                'rule_kind':'per_unit','amount_cents':60,'unit_minutes':30,
                'review_status':'verified','priority':100,'calculation':{}}
        return {'agency':agency,'carpark_id':code,'schedule_id':ident,
                'valid_from':self.AT-timedelta(days=1),'valid_until':None,'reviewed_at':self.AT,
                'review_status':'verified','calculator_key':'window_rules_v1','grace_minutes':15,
                'calculator_config':{'agency':agency,'parking_system':'ELECTRONIC PARKING'},
                'rules':[base,{**base,'end_time':'17:00','amount_cents':120,'priority':120}], **changes}

    def run_batch(self, stays, rows, schedules, blockers=None):
        connection=MagicMock()
        cursor=connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.side_effect=[rows,schedules,[],[{'calendar_year':2026}],[],blockers or []]
        with patch('comparison.datetime') as clock:
            clock.now.return_value=self.AT
            result=compare_candidate_stays(connection,stays)
        self.assertEqual(cursor.execute.call_count,6)
        return result,cursor

    def test_actual_tariff_boundary_uses_each_candidates_arrival(self):
        first=self.AT.replace(minute=50)
        second=self.AT.replace(hour=17,minute=10)
        # Request order is intentionally different from DB order.
        requests=[CandidateStay('HDB','A1',second,30),CandidateStay('HDB','BBB',first,30)]
        results,cursor=self.run_batch(requests,[self.row(),self.row(code='A1')],
                                    [self.schedule(),self.schedule(code='A1',ident=2)])
        self.assertEqual([r['carpark_id'] for r in results],['A1','BBB'])
        self.assertEqual([r['price']['amount_cents'] for r in results],[60,80])
        self.assertEqual(results[1]['parking_end_at'],first+timedelta(minutes=30))
        self.assertTrue(all(r['price_comparison_eligible'] for r in results))
        self.assertTrue(all(not r['recommendation_eligible'] for r in results))
        # Exact agency/code pairs are bound as arrays, not interpolated SQL.
        self.assertEqual(cursor.execute.call_args_list[0].args[1],(['HDB','HDB'],['A1','BBB']))

    def test_schedule_version_is_selected_for_each_arrival_and_full_stay(self):
        boundary=self.AT.replace(hour=17,minute=0)
        old=self.schedule(valid_until=boundary)
        future=self.schedule(ident=2,valid_from=boundary)
        results,_=self.run_batch([CandidateStay('HDB','BBB',boundary,30)],
                                [self.row()],[future,old])
        self.assertEqual(results[0]['price']['schedule_id'],2)
        results,_=self.run_batch([CandidateStay('HDB','BBB',boundary-timedelta(minutes=10),30)],
                                [self.row()],[future,old])
        self.assertEqual(results[0]['price']['status'],'schedule_out_of_range')

    def test_same_code_in_different_agencies_does_not_merge(self):
        hdb=self.schedule()
        lta=self.schedule(agency='LTA',ident=2,grace_minutes=0)
        lta['rules']=[{**lta['rules'][0],'amount_cents':300}]
        at=self.AT.replace(hour=17,minute=10)
        results,_=self.run_batch([CandidateStay('LTA','BBB',at,30),CandidateStay('HDB','BBB',at,30)],
                                [self.row(),self.row('LTA')],[hdb,lta])
        self.assertEqual([r['price']['amount_cents'] for r in results],[300,60])

    def test_first_entry_status_is_per_carpark(self):
        schedules=[self.schedule('LTA',code,ident,grace_minutes=0)
                   for ident,code in enumerate(('53','65'),start=1)]
        for s in schedules:
            s['rules']=[{**s['rules'][0],'calculation':{'first_entry_required':True,
                          'tiers':[{'duration_minutes':120,'unit_minutes':120,'amount_cents':0}],
                          'repeat_entry_tiers':[]}}]
        at=self.AT.replace(hour=17,minute=10)
        results,_=self.run_batch([CandidateStay('LTA','53',at,30,first_entry=True),
                                 CandidateStay('LTA','65',at,30,first_entry=False)],
                                [self.row('LTA','53'),self.row('LTA','65')],schedules)
        self.assertEqual([r['price']['amount_cents'] for r in results],[0,60])

    def test_missing_price_stale_reading_and_ambiguous_location_are_explained(self):
        results,_=self.run_batch([CandidateStay('URA','B0098',self.AT,60)],
                                [self.row('URA','B0098',availability_status='stale',
                                          location_status='multiple_points')],[])
        self.assertIsNone(results[0]['price']['amount_cents'])
        self.assertEqual(results[0]['price_comparison_exclusions'],
                         ['availability_stale','price_tariff_unverified','location_multiple_points'])

    def test_unreviewed_ura_window_blocks_instead_of_becoming_free(self):
        s=self.schedule('URA','S0049',grace_minutes=0)
        blocker={'schedule_id':1,'day_type':'weekday','start_time':None,'end_time':None}
        results,_=self.run_batch([CandidateStay('URA','S0049',self.AT,30)],
                                [self.row('URA','S0049')],[s],[blocker])
        self.assertEqual(results[0]['price']['status'],'rate_window_unreviewed')
        self.assertIsNone(results[0]['price']['amount_cents'])
        self.assertEqual(len(s['rules']),2)  # Adding a blocker must not mutate cached inputs.

    def test_unknown_identity_is_not_silently_omitted(self):
        connection=MagicMock()
        connection.cursor.return_value.__enter__.return_value.fetchall.side_effect=[[],[],[],[],[],[]]
        with self.assertRaisesRegex(ValueError,'Unknown canonical carpark'):
            compare_candidate_stays(connection,[CandidateStay('HDB','UNKNOWN',self.AT,30)])

    def test_duplicate_empty_and_invalid_requests_do_not_query_database(self):
        connection=MagicMock()
        request=CandidateStay('HDB','BBB',self.AT,30)
        self.assertEqual(compare_candidate_stays(connection,[]),[])
        with self.assertRaises(ValueError):
            compare_candidate_stays(connection,[request,request])
        with self.assertRaises(ValueError):
            compare_candidate_stays(connection,[{}])
        for arrival, duration in [(self.AT.replace(tzinfo=None),30),(self.AT.replace(second=1),30),
                                   (self.AT,0),(self.AT,True)]:
            with self.subTest(arrival=arrival,duration=duration),self.assertRaises(ValueError):
                compare_carparks(connection,arrival,duration)
        connection.cursor.assert_not_called()


if __name__ == "__main__":
    unittest.main()
