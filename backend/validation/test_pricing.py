from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest
from datetime import date, datetime, timedelta

from pricing import quote_schedule
from database.seed_operator_rates import reviewed_catalog

AT = datetime.fromisoformat('2026-09-30T10:00:00+08:00')
HOLIDAYS = {date(2026,12,25):'gazetted',date(2026,11,9):'observed'}


def schedule(**changes):
    return {'schedule_id':1,'review_status':'verified','calculator_key':'window_rules_v1',
            'valid_from':AT-timedelta(days=1),'reviewed_at':AT,
            'grace_minutes':15,'source_url':'https://example.test/rates',
            'calculator_config':{'agency':'HDB','parking_system':'ELECTRONIC PARKING'},**changes}


def rule(start='07:00',end='22:30',amount=60,unit=30,kind='per_unit',day='all',**calc):
    return {'day_type':day,'start_time':start,'end_time':end,
            'rule_kind':kind,'amount_cents':amount,'unit_minutes':unit,
            'review_status':'verified','priority':100,'calculation':calc}


def quote(s,r,at=AT,duration=60,holidays=HOLIDAYS,**options):
    return quote_schedule(s,r,at,duration,holidays,{2026},checked_at=at,**options)


def operator(code):
    entry = next(e for e in reviewed_catalog() if e['carpark_id']==code)
    s = schedule(grace_minutes=entry['grace_minutes'],valid_from=datetime.fromisoformat('2026-09-30T13:27:00+00:00'),
                 reviewed_at=datetime.fromisoformat('2026-09-30T13:27:00+00:00'),
                 calculator_config={'agency':'LTA','parking_system':'operator_eps','no_cross_window':True,**entry['config']})
    return s,entry['rules']


class TariffTests(unittest.TestCase):
    def test_grace_is_not_subtracted_after_expiry(self):
        self.assertEqual(quote(schedule(),[rule()],duration=15).amount_cents,0)
        self.assertEqual(quote(schedule(),[rule()],duration=16).amount_cents,32)

    def test_central_boundary_is_integrated(self):
        rules=[rule(),{**rule(end='17:00',amount=120),'priority':120}]
        result=quote(schedule(),rules,AT.replace(hour=16,minute=30),60)
        self.assertEqual(result.amount_cents,180)

    def test_free_boundary_is_integrated(self):
        rules=[rule(),{**rule(start='13:00',amount=0,unit=None,kind='free',day='sunday'),'priority':300}]
        sunday=AT.replace(day=4,month=10,hour=12,minute=30)
        result=quote(schedule(reviewed_at=sunday),rules,sunday,60)
        self.assertEqual(result.amount_cents,60)

    def test_night_cap_crosses_midnight(self):
        rules=[rule(start='22:30',end='07:00'),rule(start='22:30',end='07:00',amount=500,unit=None,kind='cap',cap_group='night')]
        night=AT.replace(hour=23)
        self.assertEqual(quote(schedule(),rules,night,360).amount_cents,500)
        self.assertEqual(quote(schedule(),rules,night,60).amount_cents,120)

    def test_nested_day_cap_does_not_add_another_five_dollars(self):
        rules=[rule(),rule(start='22:30',end='07:00'),
               rule(start='22:30',end='07:00',amount=500,unit=None,kind='cap',cap_group='night'),
               rule(start='07:00',end='07:00',amount=1200,unit=None,kind='cap',cap_group='parking_day',full_day=True)]
        self.assertEqual(quote(schedule(),rules,(AT+timedelta(days=1)).replace(hour=7),1440).amount_cents,1200)

    def test_day_cap_resets_at_seven_not_midnight(self):
        rules=[rule(),rule(start='22:30',end='07:00'),
               rule(start='22:30',end='07:00',amount=500,unit=None,kind='cap',cap_group='night'),
               rule(start='07:00',end='07:00',amount=1200,unit=None,kind='cap',cap_group='parking_day',full_day=True)]
        self.assertEqual(quote(schedule(),rules,AT.replace(hour=22,minute=30),600).amount_cents,680)

    def test_no_night_permission_no_quote(self):
        self.assertEqual(quote(schedule(),[rule()],AT.replace(hour=22),60).status,'rate_window_missing')

    def test_equal_clock_without_full_day_is_not_twenty_four_hours(self):
        self.assertEqual(quote(schedule(),[rule(start='07:00',end='07:00')]).status,'rate_window_missing')

    def test_missing_or_zero_zero_not_free(self):
        block={**rule(),'review_status':'pending_review','calculation':{'blocks_quote':True}}
        self.assertEqual(quote(schedule(),[rule(),block]).status,'rate_window_unreviewed')

    def test_ambiguous_rounding_fails_closed(self):
        self.assertEqual(quote(schedule(),[rule(amount=80)],duration=16).status,'rounding_unreviewed')
        self.assertEqual(quote(schedule(),[rule(amount=80)],duration=30).amount_cents,80)

    def test_conflicting_priority_fails_closed(self):
        self.assertEqual(quote(schedule(),[rule(),rule(amount=90)]).status,'rate_conflict')

    def test_paper_and_eps_do_not_share_billing(self):
        coupon=schedule(grace_minutes=0,calculator_config={'agency':'HDB','parking_system':'COUPON PARKING'})
        self.assertEqual(quote(coupon,[rule()],duration=20).amount_cents,40)
        self.assertEqual(quote(coupon,[rule()],duration=20,payment_method='paper_coupon').amount_cents,60)
        self.assertEqual(quote(schedule(),[rule()],payment_method='paper_coupon').status,'payment_method_invalid')

    def test_ura_unknown_long_stay_cap(self):
        ura=schedule(grace_minutes=0,calculator_config={'agency':'URA','parking_system':'C','day_cap_unconfirmed':True})
        self.assertEqual(quote(ura,[rule()],duration=600).status,'day_cap_unreviewed')
        self.assertEqual(quote(ura,[rule()],duration=60).amount_cents,120)

    def test_ura_overnight_category_change_unconfirmed(self):
        ura=schedule(calculator_config={'agency':'URA','parking_system':'B'})
        saturday=AT.replace(month=10,day=3,hour=23)
        self.assertEqual(quote({**ura,'reviewed_at':saturday},[rule(start='22:30',end='07:00',day='saturday')],saturday,120).status,'overnight_day_type_unreviewed')

    def test_stale_captured_ura_data_cannot_be_approved_by_review_only(self):
        ura=schedule(source_captured_at=AT-timedelta(days=3),calculator_config={'agency':'URA','parking_system':'C'})
        self.assertEqual(quote(ura,[rule()]).status,'rate_capture_stale')

    def test_holiday_calendar_and_observed_days_guarded(self):
        observed=AT.replace(month=11,day=9)
        self.assertEqual(quote(schedule(reviewed_at=observed),[rule()],observed).status,'observed_holiday_unreviewed')
        self.assertEqual(quote_schedule(schedule(),[rule()],AT,60,HOLIDAYS,set(),checked_at=AT).status,'holiday_calendar_missing')

    def test_operator_initial_block_and_partial_units(self):
        at=datetime.fromisoformat('2026-10-01T10:00:00+08:00')
        s,r=operator('65')
        self.assertEqual(quote(s,r,at,60).amount_cents,155)
        self.assertEqual(quote(s,r,at,61).amount_cents,195)
        self.assertEqual(quote(s,r,at,120).amount_cents,315)

    def test_operator_flat_charge_is_once_and_grace_not_discount(self):
        at=datetime.fromisoformat('2026-09-30T19:00:00+08:00')+timedelta(days=1)
        s,r=operator('65')
        self.assertEqual(quote(s,r,at,10).amount_cents,0)
        self.assertEqual(quote(s,r,at,11).amount_cents,260)
        self.assertEqual(quote(s,r,at,180).amount_cents,260)

    def test_operator_cross_band_not_guessed(self):
        at=datetime.fromisoformat('2026-10-01T17:30:00+08:00')
        s,r=operator('65')
        self.assertEqual(quote(s,r,at,60).status,'operator_boundary_unreviewed')

    def test_esplanade_hour_does_not_restart_at_midnight(self):
        at=datetime.fromisoformat('2026-09-30T23:45:00+08:00')
        s,r=operator('4')
        self.assertEqual(quote(s,r,at,30).amount_cents,230)
        self.assertEqual(quote(s,r,at,61).amount_cents,460)

    def test_imm_requires_first_entry_knowledge(self):
        at=datetime.fromisoformat('2026-10-01T10:00:00+08:00')
        s,r=operator('53')
        self.assertEqual(quote(s,r,at,60).status,'first_entry_unknown')
        self.assertEqual(quote(s,r,at,60,first_entry=True).amount_cents,0)
        self.assertEqual(quote(s,r,at,60,first_entry=False).amount_cents,120)
        self.assertEqual(quote(s,r,at,121,first_entry=True).amount_cents,160)

    def test_tampines_conflicting_weekend_block_is_not_promoted(self):
        at=datetime.fromisoformat('2026-10-03T10:00:00+08:00')
        s,r=operator('63')
        self.assertEqual(quote(s,r,at,60).status,'rate_window_unreviewed')

    def test_validity_covers_entire_stay(self):
        s=schedule(valid_until=AT+timedelta(minutes=30))
        self.assertEqual(quote(s,[rule()],duration=60).status,'schedule_out_of_range')


if __name__=='__main__':
    unittest.main()
