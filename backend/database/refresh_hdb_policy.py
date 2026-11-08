"""Version HDB tariffs after reviewing fresh official policy-page captures.

This is a maintenance command, not API startup. It keeps past schedules/rules,
requires matching policy lists, and compiles current facility flags. It does not
extend an old review date or change expiry thresholds. Captures are produced by
reading the official rendered HDB pages and reviewing their contents.
"""
from __future__ import annotations

import argparse
from datetime import datetime, time, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'data-pipeline'))
from provider_puller import load_local_env

DAYS=('weekday','saturday','sunday','public_holiday')
URL='https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'


def rule(key,day,start,end,kind,cents,unit=None,priority=100,config=None):
    return dict(rule_key=key,day_type=day,start_time=str(start),end_time=str(end),
                rule_kind=kind,amount_cents=cents,unit_minutes=unit,priority=priority,
                review_status='verified',calculation=config or {},description=key)


def compile_rules(h,windows):
    """Same supported HDB policy semantics as the calculator's reviewed baseline."""
    result=[]
    end='19:00' if h['short_term_parking']=='7AM-7PM' else '22:30'
    peak=h['peak_profile']!='none'
    for day in DAYS:
        result.append(rule('base-'+day,day,'07:00',end,'per_unit',60,30))
        if h['central_area'] and day in ('weekday','saturday'):
            result.append(rule('central-'+day,day,'07:00','17:00','per_unit',120,30,120))
        if day in ('sunday','public_holiday') and h['sunday_ph_free_from'] is not None:
            result.append(rule('free-'+day,day,h['sunday_ph_free_from'],end,'free',0,None,300))
        if h['night_parking']=='YES':
            result.append(rule('night-'+day,day,'22:30','07:00','per_unit',60,30))
            if not peak:
                result.append(rule('night-cap-'+day,day,'22:30','07:00','cap',500,
                                   config={'cap_group':'night'}))
        if not peak:
            result.append(rule('day-cap-'+day,day,'07:00','07:00' if h['night_parking']=='YES' else '22:30',
                               'cap',2000 if h['central_area'] else 1200,
                               config={'cap_group':'parking_day','full_day':h['night_parking']=='YES',
                                       'payment_methods':['eps','parking_sg']}))
    for w in windows:
        if w['peak_profile']!=h['peak_profile']:continue
        day,start,end=w['day_type'],w['start_time'],w['end_time']
        result.append(rule('peak-'+day,day,start,end,'per_unit',80,30,200))
        if h['central_area'] and day in ('weekday','saturday') and start<time(17):
            result.append(rule('central-peak-'+day,day,start,min(end,time(17)),'per_unit',140,30,220))
    assert len({r['rule_key'] for r in result})==len(result)
    return result


def read_captures(directory,now):
    pages={}
    for name in ['hdb-charges','hdb-electronic-parking','hdb-free-parking','hdb-coupon-parking']:
        path=directory/(name+'.json');p=json.loads(path.read_text(encoding='utf-8'))
        at=datetime.fromisoformat(p['retrieved_at'].replace('Z','+00:00'))
        if not p['url'].startswith('https://www.hdb.gov.sg/') or not timedelta(0)<=now-at<timedelta(days=1):
            raise ValueError('Review requires fresh captures from the official HDB site')
        p['sha256']=hashlib.sha256(path.read_bytes()).hexdigest();pages[name]=p
    charges=pages['hdb-charges'];body=' '.join(charges['text'].split())
    for fact in ['$0.60 per half-hour','$1.20 per half-hour','$0.80 per half-hour','$1.40 per half-hour',
                 '$5 per night','10:30pm to 7:00am','$12 in non-Central Areas','$20 in Central Areas',
                 'caps do not apply to car parks with peak hour parking charges']:
        if fact not in body:raise ValueError('HDB tariff facts changed; review the compiler before applying')
    eps=pages['hdb-electronic-parking']['text']
    if 'per-minute basis' not in eps or '15-minute grace period' not in eps:
        raise ValueError('EPS billing/grace needs a new review')
    free=pages['hdb-free-parking']['text']
    if '7.00am to 10.30pm on Sundays and Public Holidays' not in free:
        raise ValueError('Free parking scheme needs a new review')
    coupon=pages['hdb-coupon-parking']['text']
    if 'Parking.sg caps' not in coupon or 'caps do not apply to car parks with peak hour parking charges' not in coupon:
        raise ValueError('Coupon/Parking.sg caps need a new review')
    return pages


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures',type=Path)
    parser.add_argument('--env',type=Path,default=ROOT/'backend/.env')
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();load_local_env(args.env)
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    now=datetime.now(timezone.utc);pages=read_captures(args.captures,now)
    version=now.strftime('hdb-review-%Y%m%dT%H%M%SZ')
    with psycopg.connect(os.environ['DATABASE_URL'],sslmode='require',connect_timeout=15,
                         prepare_threshold=None,row_factory=dict_row) as conn:
        with conn.cursor() as c:
            c.execute("SET LOCAL statement_timeout='120s'")
            c.execute('SELECT pg_advisory_xact_lock(72631,4)')
            c.execute('SELECT * FROM parking_data.hdb_tariff_exceptions WHERE policy_version=%s',('2026-09-28-observed',))
            exceptions=c.fetchall()
            central={r['carpark_id'] for r in exceptions if r['central_area']}
            peak={r['carpark_id'] for r in exceptions if r['peak_profile']!='none'}
            tables=pages['hdb-charges']['tables']
            assert {r[0] for r in tables[1][1:]}==central,'Central list changed'
            assert {r[0] for r in tables[5][1:]}==peak,'Peak list changed'
            c.execute('SELECT * FROM parking_data.hdb_loading_bay_tariffs');bays=c.fetchall()
            listed={r[0].replace('BRBL1','BRBL') for r in tables[7][1:]}
            assert listed=={r['carpark_id'] for r in bays},'Loading-bay list changed'
            bay_text=' '.join(' '.join(row) for row in tables[6])
            assert all(f in bay_text for f in ['Free - first 15 minutes','$2 - first half hour',
                                              '$4 - subsequent half hour']),'Loading-bay rates changed'
            assert all(b['first_30_minutes_cents']==200 and b['subsequent_30_minutes_cents']==400
                       and b['grace_minutes']==(10 if b['carpark_id']=='BRBL' else 15)
                       for b in bays),'Stored loading-bay facts need review'
            c.execute('SELECT * FROM parking_data.hdb_peak_windows WHERE policy_version=%s',('2026-09-28-observed',))
            windows=c.fetchall()
            # Compare the complete current published peak-window wording to the
            # reviewed cohort assignment, not just its carpark IDs.
            periods={'acb_cy':'Weekdays, 10:00am to 6:00pm; Weekends, 8:00am to 7:00pm',
                     'se_mon_sat':'Monday to Saturday, 10:00am to 10:00pm','se_daily':'Daily, 10:00am to 10:00pm',
                     'mp_daily':'Daily, 8:00am to 8:00pm',
                     'hougang_weekend':'Weekdays, 11:00am to 8:00pm Weekends, 9:00am to 8:00pm'}
            profiles={r['carpark_id']:r['peak_profile'] for r in exceptions}
            for row in tables[5][1:]:
                assert ' '.join(row[2].split())==periods[profiles[row[0]]],'Peak hours changed'
            c.execute("""SELECT * FROM parking_data.hdb_tariff_classification h
                WHERE reference_flags_recognized AND short_term_parking<>'NO'
                  AND reference_retrieved_at > now()-interval '1 day'
                  AND NOT EXISTS (SELECT 1 FROM parking_data.hdb_loading_bay_tariffs b WHERE b.carpark_id=h.carpark_id)
                ORDER BY carpark_id""")
            facilities=c.fetchall();assert len(facilities)>1900,'Unexpected HDB reference coverage'
            plans=[(h,compile_rules(h,windows)) for h in facilities]
            c.execute("SELECT * FROM parking_data.rate_schedules WHERE agency='HDB' AND source='hdb_policy' AND valid_until IS NULL")
            old=c.fetchall()
            backup=args.captures/'hdb-schedules-before.json.gz'
            if not backup.exists():backup.write_bytes(gzip.compress(json.dumps(old,default=str).encode()))
            report={'checked_at':now.isoformat(),'version':version,'carparks':len(plans),
                    'rules':sum(len(r) for _,r in plans),'previous_open_schedules':len(old),
                    'source_hashes':{k:p['sha256'] for k,p in pages.items()},'applied':args.apply}
            if not args.apply:
                conn.rollback();print(json.dumps(report));return
            note='Fresh official HDB charges, EPS, coupon and free-parking pages reviewed. Central/peak/loading-bay lists and peak windows match the existing classification. Unknown/observed-holiday guards remain.'
            c.execute("""UPDATE parking_data.rate_schedules SET valid_until=%s,review_status='superseded'
                         WHERE agency='HDB' AND source='hdb_policy' AND valid_until IS NULL""",(now,))
            values=[]
            for h,rules in plans:
                flags={k:h[k] for k in ['parking_system','short_term_parking','free_parking','night_parking']}
                config={'agency':'HDB','parking_system':h['parking_system'],'reference_flags':flags,
                        'reference_retrieved_at':h['reference_retrieved_at'].isoformat(),'peak_profile':h['peak_profile'],
                        'ph_peak_unconfirmed':h['peak_profile'] in ['acb_cy','se_mon_sat','hougang_weekend'],
                        'paper_day_cap_unconfirmed':True,'overnight_anchor_day':True,'policy_review_capture':version,
                        'source_hashes':report['source_hashes']}
                values.append((h['carpark_id'],URL,now,15 if h['parking_system']=='ELECTRONIC PARKING' else 0,
                               now,note,version+'-'+h['carpark_id'],Jsonb(config)))
            c.executemany("""INSERT INTO parking_data.rate_schedules
                (agency,carpark_id,source,source_url,valid_from,billing_method,grace_minutes,review_status,
                 reviewed_by,reviewed_at,review_note,seed_key,calculator_key,calculator_config,coverage_scope)
                VALUES ('HDB',%s,'hdb_policy',%s,%s,'rule_specific',%s,'verified','ParkChoiceSG official source review',
                        %s,%s,%s,'window_rules_v1',%s,'published_windows') RETURNING schedule_id""",values,returning=True)
            rule_values=[]
            for h,rules in plans:
                sid=c.fetchone()['schedule_id']
                rule_values.extend((sid,r['day_type'],r['start_time'],r['end_time'],r['rule_kind'],r['amount_cents'],
                                    r['unit_minutes'],r['description'],r['priority'],r['rule_key'],Jsonb(r['calculation']))
                                   for r in rules)
                c.nextset()
            c.executemany("""INSERT INTO parking_data.rate_schedule_rules
                (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
                 description,priority,rule_key,review_status,calculation)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'verified',%s)""",rule_values)
            facts={'review_capture':version,'source_hashes':report['source_hashes'],
                   'base_cents_per_30min':60,'central_day_cents_per_30min':120,
                   'peak_cents_per_30min':80,'central_peak_cents_per_30min':140,
                   'night_cap_cents':500,'outside_day_cap_cents':1200,'central_day_cap_cents':2000}
            c.executemany("""INSERT INTO parking_data.tariff_source_evidence
                (capture_key,agency,carpark_id,source_kind,source_url,captured_at,content_sha256,
                 published_facts,review_status,review_note)
                VALUES (%s,'HDB',%s,'hdb_policy',%s,%s,%s,%s,'verified_facts',%s)""",
                [(version+'-'+h['carpark_id'],h['carpark_id'],URL,now,pages['hdb-charges']['sha256'],Jsonb(facts),note)
                 for h,_ in plans])
            c.execute('UPDATE parking_data.hdb_loading_bay_tariffs SET checked_at=%s',(now,))
            c.execute("SELECT count(*) AS n FROM parking_data.rate_schedules WHERE seed_key LIKE %s",(version+'-%',))
            assert c.fetchone()['n']==len(plans)
        conn.commit()
    (args.captures/'hdb-refresh-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    try:main()
    except Exception as exc:
        if isinstance(exc,(ValueError,AssertionError)):raise SystemExit(str(exc)) from None
        raise SystemExit(f'HDB refresh failed ({type(exc).__name__}); private connection details withheld.') from None
