"""Import a verified URA capture and compile supported motor-car tariff windows.

Called inside the availability loader's transaction. Unknown provider semantics
become explicit blocking windows; old prices cannot survive a newer missing rate.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from import_ura_rates import DAY_FIELDS, parse_day, parse_time, prepare, read_verified_details


def compile_ura(manifest, details):
    grouped = defaultdict(list)
    for number, raw in enumerate(details):
        if raw.get('vehCat') == 'Car':
            grouped[str(raw['ppCode']).strip().upper()].append((number, raw))
    if not grouped:
        raise ValueError('URA capture has no motor-car tariff records')
    plans = []
    for code, records in sorted(grouped.items()):
        systems = {str(r.get('parkingSystem', '')).strip() for _, r in records}
        system = next(iter(systems)) if len(systems) == 1 else None
        rules = []
        for number, raw in records:
            start, end = parse_time(raw.get('startTime')), parse_time(raw.get('endTime'))
            clock_ok = start is not None and end is not None and start != end
            for day, (amount_field, minutes_field) in DAY_FIELDS.items():
                amount, unit, interpretation = parse_day(raw.get(amount_field), raw.get(minutes_field))
                known = clock_ok and system in {'B', 'C'} and interpretation == 'per_unit'
                rule = dict(day_type=day, start_time=start or '00:00:00', end_time=end or '00:00:00',
                            rule_kind='per_unit' if known else 'free', amount_cents=amount if known else 0,
                            unit_minutes=unit if known else None, source_row_number=number,
                            source_day_type=day, review_status='verified' if known else 'pending_review',
                            description='URA per-unit window' if known else 'Unresolved URA tariff window',
                            calculation={} if known else {'blocks_quote':True,'full_day':not clock_ok})
                # Corroborated standard night ceiling, never an extra per-unit fee.
                paired = any(parse_time(other.get('startTime')) == start
                             and parse_time(other.get('endTime')) == end
                             and parse_day(other.get(amount_field),other.get(minutes_field)) == (60,30,'per_unit')
                             for _, other in records)
                if (system in {'B','C'} and start == '22:30:00' and end == '07:00:00'
                        and amount == 500 and unit == 510 and paired):
                    rule.update(rule_kind='cap',amount_cents=500,unit_minutes=None,review_status='verified',
                                description='URA standard paired night cap',calculation={'cap_group':'night'})
                rules.append(rule)
        verified = any(r['rule_kind'] == 'per_unit' and r['review_status'] == 'verified' for r in rules)
        plans.append(dict(carpark_id=code, parking_system=system, rules=rules,
                          review_status='verified' if verified else 'pending_review',
                          grace_minutes=15 if system == 'B' else 0,
                          calculator_config={'agency':'URA','parking_system':system,
                              'day_cap_unconfirmed':True,'maximum_uncapped_day_cents':1200,
                              'compiler_version':'ura_windows_v1',
                              'billing_source':'https://www.police.gov.sg/-/media/SPF/Knowledge-Hub/Traffic/BT-ENG-24126.pdf'}))
    return plans


def without_transaction_wrapper(script):
    """Strip only our generator's fixed outer statements, never provider text."""
    prefix = 'SET standard_conforming_strings = on;\n'
    if script.startswith(prefix):
        script = script[len(prefix):]
    if script.startswith('BEGIN;\n'):
        script = script[len('BEGIN;\n'):]
    if script.endswith('COMMIT;\n'):
        script = script[:-len('COMMIT;\n')]
    return script


def load_ura_pricing(cursor, run_directory: Path):
    """Caller owns the transaction; a failed import rolls back availability too."""
    from psycopg.types.json import Jsonb

    manifest, details = read_verified_details(run_directory)
    plans = compile_ura(manifest, details)
    run_id, captured_at = manifest['run_id'], manifest['retrieved_at']
    # Serialize full URA pricing imports and protect against concurrent collectors.
    cursor.execute("SELECT pg_advisory_xact_lock(72631, 3)")
    cursor.execute("""SELECT count(*),count(*) FILTER (
        WHERE calculator_config->>'compiler_version'='ura_windows_v1')
        FROM parking_data.rate_schedules WHERE source_run_id=%s""", (run_id,))
    existing, compiled = cursor.fetchone()
    if existing:
        if existing == compiled == len(plans):
            return {'capture_run_id':run_id,'carparks':existing,'already_loaded':True}
        raise ValueError('Capture already has incompatible schedules; manual review required')
    cursor.execute("""SELECT max(valid_from) FROM parking_data.rate_schedules
                      WHERE source='ura_details'""")
    newest = cursor.fetchone()[0]
    instant = datetime.fromisoformat(captured_at)
    if newest is not None and newest > instant:
        raise ValueError('Refusing an out-of-order URA tariff capture')
    with TemporaryDirectory(prefix='parkchoice-rates-') as temporary:
        output = Path(temporary) / 'batches'
        prepare(run_directory, output)
        cursor.execute('SET LOCAL standard_conforming_strings = on')
        # Draft generation remains available for manual review; the runtime uses
        # the compiler above, including explicit blocks absent from old drafts.
        for path in sorted(output.glob('*.sql')):
            if path.name != '20-drafts.sql':
                cursor.execute(without_transaction_wrapper(path.read_text(encoding='utf-8')))
    cursor.execute("""UPDATE parking_data.rate_schedules SET valid_until=%s,review_status='superseded'
                      WHERE source='ura_details' AND valid_until IS NULL AND valid_from < %s""",
                   (captured_at,captured_at))
    # Batch statements to avoid thousands of individual network round trips.
    cursor.executemany("""INSERT INTO parking_data.rate_schedules
            (agency,carpark_id,source,source_run_id,source_url,valid_from,billing_method,
             grace_minutes,review_status,reviewed_by,reviewed_at,review_note,seed_key,
             calculator_key,calculator_config,coverage_scope)
            VALUES ('URA',%s,'ura_details',%s,'https://eservice.ura.gov.sg/maps/api/',%s,
              'rule_specific',%s,%s,'ParkChoiceSG reviewed compiler ura_windows_v1',%s,%s,%s,%s,%s,'partial')
            RETURNING schedule_id""",
            [(plan['carpark_id'],run_id,captured_at,plan['grace_minutes'],plan['review_status'],captured_at,
             'Automatically validated documented per-unit fields and standard paired night cap. Other windows block quotes.',
             f"ura-runtime-{run_id}-{plan['carpark_id']}",
             'window_rules_v1' if plan['review_status']=='verified' else None,
             Jsonb(plan['calculator_config'])) for plan in plans], returning=True)
    rule_values = []
    for plan in plans:
        schedule_id = cursor.fetchone()[0]
        rule_values.extend(
            (schedule_id,r['day_type'],r['start_time'],r['end_time'],r['rule_kind'],r['amount_cents'],
             r['unit_minutes'],r['description'],run_id,r['source_row_number'],r['source_day_type'],
             r['review_status'],Jsonb(r['calculation']),f"{r['source_row_number']}-{r['day_type']}")
            for r in plan['rules'])
        cursor.nextset()
    cursor.executemany("""INSERT INTO parking_data.rate_schedule_rules
             (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
              description,source_run_id,source_row_number,source_day_type,review_status,calculation,rule_key)
             VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
             rule_values)
    cursor.executemany("""INSERT INTO parking_data.tariff_source_evidence
            (capture_key,agency,carpark_id,source_kind,source_url,captured_at,published_facts,review_status,review_note)
            VALUES (%s,'URA',%s,'ura_api','https://eservice.ura.gov.sg/maps/api/',%s,%s,'verified_facts',%s)
            ON CONFLICT DO NOTHING""",[(f"ura-{run_id}-{plan['carpark_id']}",plan['carpark_id'],captured_at,
              Jsonb({'run_id':run_id,'compiler_version':'ura_windows_v1','rule_count':len(plan['rules'])}),
              'Source capture imported atomically with availability; partial calculator with explicit blocked windows.')
              for plan in plans])
    return {'capture_run_id':run_id,'carparks':len(plans),
            'approved_partial':sum(p['review_status']=='verified' for p in plans),
            'blocked_windows':sum(r['review_status']!='verified' for p in plans for r in p['rules'])}
