"""Apply the 2 November 2026 manual review of archived operator/MOM pages.

Run without --apply first. This records a reviewed import, not an automatic
scraper that grants approval to whatever a website happens to return.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'data-pipeline'), str(ROOT / 'backend')]
from provider_puller import load_local_env
from seed_operator_rates import reviewed_catalog, band
from pricing import quote_schedule, SINGAPORE


def reviewed_entries():
    entries = reviewed_catalog()
    for entry in entries:
        code = entry['carpark_id']
        if code == '62':
            # Main table gives subsequent-only midnight charges, FAQ gives an
            # initial two-hour block. Both are on the current published page.
            for day in ('saturday', 'sunday', 'public_holiday'):
                r = band(day, '00:00', '03:00', 0, kind='free', blocks_quote=True)
                r.update(review_status='pending_review', description='Lot One midnight main-table/FAQ conflict')
                entry['rules'].append(r)
            entry['note'] += ' Weekend/PH 00:00-03:00 is blocked: main table and FAQ disagree.'
        if code == '59':
            entry['rules'].append(band('weekday', '12:00', '14:00', 0, kind='free',
                                       weekdays=[0, 1, 2, 3, 4], eve=False, priority=400))
            # Main table extends evening free parking to December; FAQ still
            # ends it in June. Do not pick one of those contradictory dates.
            r = band('weekday', '18:00', '21:00', 0, kind='free',
                     weekdays=[0, 1, 2, 3], eve=False, blocks_quote=True)
            r.update(review_status='pending_review', description='CQ evening promotion expiry conflict: June/December 2026')
            entry['rules'].append(r)
            entry['note'] += ' Weekday lunch free parking is supported; Mon-Thu evening promotion expiry remains disputed.'
        if code == '63':
            r = band('all', '00:00', '18:00', 0, kind='free', eve=True, blocks_quote=True)
            r.update(review_status='pending_review', description='Tampines Mall PH-eve daytime table/FAQ category conflict')
            entry['rules'].append(r)
            entry['note'] += ' PH-eve daytime is also blocked while the main-table/FAQ categories differ.'
    return entries


def verify_quotes(entries, now):
    """Exercise monetary examples and the newly identified ambiguous windows."""
    by_id = {e['carpark_id']: e for e in entries}
    cases = [
        ('65', '2026-11-03T10:00', 60, None, 'quoted', 155),
        ('43', '2026-11-03T10:00', 75, None, 'quoted', 215),
        ('62', '2026-11-14T10:00', 120, None, 'quoted', 265),
        ('62', '2026-11-14T01:00', 60, None, 'rate_window_unreviewed', None),
        ('64', '2026-11-14T01:00', 120, None, 'quoted', 265),
        ('9', '2026-11-03T10:00', 75, None, 'quoted', 250),
        ('66', '2026-11-14T10:00', 120, None, 'quoted', 260),
        ('3', '2026-11-03T10:00', 75, None, 'quoted', 325),
        ('61', '2026-11-06T19:00', 135, None, 'quoted', 385),
        ('59', '2026-11-03T12:00', 60, None, 'quoted', 0),
        ('59', '2026-11-03T10:00', 60, None, 'quoted', 160),
        ('59', '2026-11-03T18:30', 60, None, 'rate_window_unreviewed', None),
        ('59', '2026-11-06T18:30', 60, None, 'quoted', 160),
        ('59', '2026-11-03T13:30', 60, None, 'operator_boundary_unreviewed', None),
        ('53', '2026-11-03T10:00', 120, None, 'first_entry_unknown', None),
        ('53', '2026-11-03T10:00', 120, True, 'quoted', 120),
        ('53', '2026-11-03T10:00', 120, False, 'quoted', 280),
        ('63', '2026-11-07T10:00', 60, None, 'rate_window_unreviewed', None),
        ('63', '2026-11-03T10:00', 60, None, 'quoted', 135),
        ('4', '2026-11-03T10:00', 61, None, 'quoted', 460),
        ('4', '2026-11-03T23:30', 60, None, 'quoted', 230),
        ('65', '2026-11-03T10:00', 10, None, 'quoted', 0),
        ('66', '2026-11-07T10:00', 60, None, 'quoted', 240),
        ('9', '2026-11-07T10:00', 60, None, 'quoted', 195),
        ('63', '2026-11-07T01:00', 60, None, 'rate_window_unreviewed', None),
        ('59', '2026-11-08T12:00', 60, None, 'quoted', 300),
        ('65', '2026-11-09T10:00', 60, None, 'observed_holiday_unreviewed', None),
    ]
    for code, at, duration, first, status, cents in cases:
        entry = by_id[code]
        arrival = datetime.fromisoformat(at).replace(tzinfo=SINGAPORE)
        schedule = dict(review_status='verified', calculator_key='window_rules_v1',
                        valid_from=now, reviewed_at=now, grace_minutes=entry['grace_minutes'],
                        calculator_config={'agency':'LTA', 'parking_system':'operator_eps',
                                           'no_cross_window':True, **entry['config']})
        holidays = {date(2026,11,8):'gazetted', date(2026,11,9):'observed'}
        result = quote_schedule(schedule, entry['rules'], arrival, duration, holidays, {2026},
                                checked_at=arrival, first_entry=first)
        assert (result.status, result.amount_cents) == (status, cents), (code, at, result)
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('captures', type=Path)
    parser.add_argument('--env', type=Path, default=ROOT/'backend/.env')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    load_local_env(args.env)
    now = datetime.now(timezone.utc)
    if now.astimezone(SINGAPORE).date() != date(2026, 11, 2):
        raise ValueError('This dated manual review must not be replayed as a future approval.')
    manifest = json.loads((args.captures/'manifest.json').read_text(encoding='utf-8'))
    sources = {p['url']:p for p in manifest if p['status']=='captured'}
    entries = reviewed_entries()
    for p in sources.values():
        captured = datetime.fromisoformat(p['retrieved_at'])
        assert timedelta(0) <= now-captured < timedelta(days=1), 'Capture is no longer fresh'
        raw = gzip.decompress((args.captures/p['file']).read_bytes())
        assert hashlib.sha256(raw).hexdigest() == p['sha256'], 'Source capture checksum mismatch'
    assert all(e['source_url'] in sources for e in entries)
    tests = verify_quotes(entries, now)
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb
    version = now.strftime('operator-review-%Y%m%dT%H%M%SZ')
    mom_url = 'https://www.mom.gov.sg/newsroom/press-releases/2025/0616-public-holidays-for-2026'
    expected = {'2026-01-01','2026-02-17','2026-02-18','2026-03-21','2026-04-03',
                '2026-05-01','2026-05-27','2026-05-31','2026-06-01','2026-08-09',
                '2026-08-10','2026-11-08','2026-11-09','2026-12-25'}
    observed = {'2026-06-01','2026-08-10','2026-11-09'}
    assert mom_url in sources
    with psycopg.connect(os.environ['DATABASE_URL'], sslmode='require', connect_timeout=15,
                         prepare_threshold=None, row_factory=dict_row) as conn:
        with conn.cursor() as c:
            c.execute("SET LOCAL statement_timeout='120s'")
            c.execute('SELECT pg_advisory_xact_lock(72631,4)')
            c.execute("SELECT * FROM parking_data.sg_public_holidays WHERE extract(year from holiday_date)=2026")
            holidays = c.fetchall()
            assert {str(r['holiday_date']) for r in holidays} == expected
            assert {str(r['holiday_date']) for r in holidays if r['holiday_kind']=='observed'} == observed
            c.execute("SELECT * FROM parking_data.rate_schedules WHERE agency='LTA' AND source='operator_published' AND valid_until IS NULL")
            old = c.fetchall()
            assert len(old)==12 and {r['carpark_id'] for r in old}=={e['carpark_id'] for e in entries}
            backup = args.captures/'operator-schedules-before.json.gz'
            if not backup.exists():
                backup.write_bytes(gzip.compress(json.dumps(old,default=str).encode()))
            report = {'version':version, 'checked_at':now.isoformat(), 'schedules':len(entries),
                      'monetary_checks':tests, 'holiday_rows':len(holidays), 'applied':args.apply,
                      'partial_schedules':['62','59','63']}
            if not args.apply:
                conn.rollback(); print(json.dumps(report)); return
            c.execute("""UPDATE parking_data.rate_schedules SET valid_until=%s,review_status='superseded'
                         WHERE agency='LTA' AND source='operator_published' AND valid_until IS NULL""",(now,))
            for e in entries:
                source = sources[e['source_url']]
                partial = any(r['review_status']!='verified' for r in e['rules'])
                config = {'agency':'LTA','parking_system':'operator_eps','no_cross_window':True,
                          **e['config'],'review_capture_sha256':source['sha256']}
                c.execute("""INSERT INTO parking_data.rate_schedules
                    (agency,carpark_id,source,source_url,valid_from,billing_method,grace_minutes,
                     review_status,reviewed_by,reviewed_at,review_note,seed_key,calculator_key,calculator_config,coverage_scope)
                    VALUES ('LTA',%s,'operator_published',%s,%s,'rule_specific',%s,'verified',
                            'ParkChoiceSG official source review',%s,%s,%s,'window_rules_v1',%s,%s)
                    RETURNING schedule_id""",(e['carpark_id'],e['source_url'],now,e['grace_minutes'],now,
                    e['note'],version+'-'+e['carpark_id'],Jsonb(config),'partial' if partial else 'published_windows'))
                sid = c.fetchone()['schedule_id']
                c.executemany("""INSERT INTO parking_data.rate_schedule_rules
                    (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
                     description,priority,rule_key,review_status,calculation)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    [(sid,r['day_type'],r['start_time'],r['end_time'],r['rule_kind'],r['amount_cents'],
                      r['unit_minutes'],r['description'],r['priority'],f'rule-{i}',r['review_status'],Jsonb(r['calculation']))
                     for i,r in enumerate(e['rules'])])
                c.execute("""INSERT INTO parking_data.tariff_source_evidence
                    (capture_key,agency,carpark_id,source_kind,source_url,captured_at,content_sha256,
                     published_facts,review_status,review_note)
                    VALUES (%s,'LTA',%s,'operator_page',%s,%s,%s,%s,'verified_facts',%s)""",
                    (version+'-'+e['carpark_id'],e['carpark_id'],e['source_url'],source['retrieved_at'],
                     source['sha256'],Jsonb({'rules':e['rules'],'grace_minutes':e['grace_minutes'],
                                            'uncertain_windows_blocked':partial}),e['note']))
            c.execute("UPDATE parking_data.sg_public_holidays SET verified_at=%s WHERE extract(year from holiday_date)=2026",(now,))
            c.execute("""UPDATE parking_data.sg_holiday_year_coverage SET checked_at=%s,note=%s
                         WHERE calendar_year=2026""",(now,
                         'MOM 2026 calendar rechecked; 11 gazetted dates and 3 observed dates match. '+
                         'Observed-day parking treatment remains guarded. Capture SHA256: '+sources[mom_url]['sha256']))
        conn.commit()
    (args.captures/'operator-refresh-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        if isinstance(exc,(ValueError,AssertionError)):
            raise SystemExit(str(exc)) from None
        raise SystemExit(f'Operator refresh failed ({type(exc).__name__}); private details withheld.') from None
