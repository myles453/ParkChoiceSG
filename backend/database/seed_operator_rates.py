"""Produce idempotent SQL from explicitly reviewed operator facts and LTA guides.

Guide entries are stored as evidence only: LTA says they may exclude GST and may
change without notice. Never infer a price from an availability-feed agency.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'data-pipeline'))
from import_ura_rates import sql, sql_json

AT = '2026-09-30T13:27:00+00:00'
IDS = {
 '1':'Suntec City','2':'Marina Square','3':'Raffles City','4':'Esplanade',
 '5':'Millenia Singapore','6':'Singapore Flyer','7':'Orchard Point','8':'The Heeren',
 '9':'Plaza Singapura','10':'The Cathay','11':'Cineleisure','12':'Hilton Orchard',
 '13':'Ngee Ann City','14':'Wisma Atria','15':'Wheelock Place','16':'VivoCity P3',
 '17':'Sentosa','18':'Tang Plaza','20':'Far East Plaza','21':'Centrepoint',
 '22':'Concorde Hotel','23':'ION Orchard','24':'313@Somerset','26':'Resorts World',
 '27':'Orchard Central','43':'Westgate','50':'VivoCity P2','52':'Orchard Gateway',
 '53':'IMM Building','55':'Paragon','56':'National Gallery','57':'The Atrium@Orchard',
 '58':'Bt Panjang Plaza','59':'CQ @ Clarke Quay','61':'Bugis+','62':'Lot One',
 '63':'Tampines Mall','64':'Junction 8','65':'Bedok Mall','66':'Funan Mall'
}
# Explicit aliases reviewed against the LTA development name. Sentosa is an
# aggregate with several carparks, so its location-specific guides remain unmapped.
ALIASES = {
 '1':'Suntec City','2':'Marina Square','3':'Raffles City Shopping Centre','4':'The Esplanade',
 '5':'Millenia Singapore (Basement Car Park)','6':'Singapore Flyer','8':'The Heeren',
 '9':'Plaza Singapura','10':'The Cathay','11':'Cathay Cineleisure Orchard',
 '12':'Hilton Singapore Orchard','13':'Ngee Ann City','14':'Wisma Atria',
 '15':'Wheelock Place','16':'Vivocity','18':'Tang Plaza','20':'Far East Plaza',
 '21':'The Centrepoint','22':'Concorde Hotel','23':'ION Orchard','24':'313@Somerset',
 '26':'Resorts World Sentosa (RWS)','27':'Orchard Central','43':'Westgate',
 '50':'Vivocity','52':'orchardgateway','53':'IMM Building','55':'Paragon Shopping Centre',
 '56':'National Gallery','57':'The Atrium @ Orchard','58':'Bukit Panjang Plaza',
 '59':'Clarke Quay','61':'Bugis+','62':'Lot One','63':'Tampines Mall','64':'Junction 8',
 '65':'Bedok Mall','66':'Funan'
}
BASE = 'https://www.capitaland.com/sg/malls/'


def band(day, start, end, amount, unit=None, *, tiers=None, priority=100,
         weekdays=None, eve=None, kind=None, **extra):
    calc = {**extra}
    if tiers:
        calc['tiers'] = tiers
    if weekdays is not None:
        calc['weekdays'] = weekdays
    if eve is not None:
        calc['ph_eve'] = eve
    if start == end:
        calc['full_day'] = True
    calc['billing'] = 'round_up_unit'
    return {'day_type':day,'start_time':start,'end_time':end,
            'rule_kind':kind or ('per_unit' if unit else 'flat'),
            'amount_cents':amount,'unit_minutes':unit,'priority':priority,
            'review_status':'verified','calculation':calc,
            'description':'Published general motor-car tariff (GST included)'}


def first(minutes, cents):
    return [{'duration_minutes':minutes,'unit_minutes':minutes,'amount_cents':cents}]


def ordinary(first_cents, subsequent, evening, *, weekend_cents=None, weekend_minutes=120):
    rules = []
    for day in ('weekday','saturday','sunday','public_holiday'):
        initial = first(60,first_cents) if day=='weekday' or weekend_cents is None else first(weekend_minutes,weekend_cents)
        rules += [band(day,'00:00','18:00',subsequent,15,tiers=initial),
                  band(day,'18:00','00:00',evening)]
    return rules


def reviewed_catalog():
    entries = []
    def add(code, slug, rules, **config):
        entries.append({'carpark_id':code,'source_url':BASE+slug+'/en/concierge.html',
                        'grace_minutes':10,'rules':rules,'config':config,
                        'note':'Official operator rates and motor-car grace reviewed; crossings between tariff bands remain unquoted.'})
    add('65','bedokmall',ordinary(155,40,260))
    add('43','westgate',ordinary(160,55,325))
    add('62','lotone',ordinary(135,45,265,weekend_cents=265))
    add('64','junction8',ordinary(135,45,265,weekend_cents=265))
    for code,slug,initial,sub,se,weekend in (
        ('9','plazasingapura',195,55,325,325), ('66','funan',240,65,330,260)):
        rules = [band('weekday','00:00','18:00',sub,15,tiers=first(60,initial)),
                 band('all','18:00','00:00',se)]
        for day in ('saturday','sunday','public_holiday'):
            rules += [band(day,'00:00','03:00',sub,15),
                      band(day,'03:00','18:00',sub,15,tiers=first(120,weekend),priority=300 if day=='public_holiday' else 100)]
        # Operator explicitly places Eve of PH in the weekday tariff category.
        rules += [band('all','00:00','18:00',sub,15,tiers=first(60,initial),eve=True,priority=200)]
        add(code,slug,rules)
    rules = [band('weekday','08:00','18:00',65,15,tiers=first(60,260)),
             band('weekday','18:00','08:00',325)]
    for day in ('saturday','sunday','public_holiday'):
        rules.append(band(day,'08:00','08:00',65,15,tiers=first(120,260)))
    add('3','rafflescity',rules)
    rules = [band('weekday','00:00','18:00',55,15,tiers=first(60,220)),
             band('weekday','18:00','00:00',330,weekdays=[0,1,2,3]),
             band('weekday','18:00','00:00',55,15,tiers=first(120,330),weekdays=[4]),
             band('all','18:00','00:00',55,15,tiers=first(120,330),eve=True,priority=200)]
    for day in ('saturday','sunday','public_holiday'):
        rules.append(band(day,'00:00','00:00',55,15,tiers=first(120,330),priority=300 if day=='public_holiday' else 100))
    add('61','bugisplus',rules)
    rules = [band('weekday','07:00','07:00',55,15,tiers=first(60,160)),
             band('saturday','07:00','07:00',55,15,tiers=first(60,160)),
             band('sunday','07:00','07:00',300),
             band('public_holiday','07:00','07:00',300,priority=300),
             band('all','07:00','07:00',55,15,tiers=first(60,160),eve=True,priority=200)]
    add('59','clarkequay',rules)
    tiers = first(60,0)+first(60,120)
    rules = [band('weekday','00:00','00:00',40,15,tiers=tiers,
                  first_entry_required=True,repeat_entry_tiers=first(60,120))]
    for day in ('saturday','sunday','public_holiday'):
        rules.append(band(day,'00:00','00:00',40,15,tiers=first(60,120),
                          first_entry_required=True,repeat_entry_tiers=first(60,120)))
    add('53','imm',rules,first_entry_required=True)
    # Main table says 2 hours; FAQ says 1 hour. Keep the disputed band blocked.
    rules = [band('weekday','00:00','18:00',45,15,tiers=first(60,135)),
             band('all','18:00','00:00',265)]
    for day in ('saturday','sunday','public_holiday'):
        rules.append(band(day,'00:00','03:00',45,15))
        blocked = band(day,'03:00','18:00',45,15)
        blocked.update(review_status='pending_review',description='Conflict: main table first 2 hours; FAQ first hour')
        blocked['calculation']['blocks_quote'] = True
        rules.append(blocked)
    add('63','tampinesmall',rules,source_conflict='Weekend 03:00-18:00 first-duration conflict')
    entries.append({'carpark_id':'4','source_url':'https://www.esplanade.com/visit/visitor-guide/getting-here-and-around',
                    'grace_minutes':0,'rules':[band('all','00:00','00:00',230,60)],
                    'config':{'continuous_full_day':True},
                    'note':'Official daily $2.30/hour or part thereof, GST included and explicitly no grace period.'})
    return entries


def generate(guide_manifest: Path, sql_path: Path, catalog_path: Path):
    captures = json.loads(guide_manifest.read_text(encoding='utf-8'))
    rows = {}
    for capture in captures:
        if capture['status'] != 'captured':
            raise ValueError('incomplete guide capture')
        for row in capture['tables']:
            if len(row)==5:
                rows.setdefault(row[0],(capture,row))
    output = ['BEGIN;']
    evidence_rows = []
    for code,name in IDS.items():
        alias = ALIASES.get(code)
        match = rows.get(alias)
        if match:
            capture,row = match
            facts = {'development':name,'guide_name':alias,'weekday_day':row[1],
                     'weekday_evening':row[2],'saturday':row[3],'sunday_ph':row[4],
                     'gst_status':'not_confirmed','grace_minutes':None}
            values = ['guide-20260930-'+code,'LTA',code,'lta_guide',capture['url'],
                      capture['retrieved_at'],capture['sha256'],facts,'requires_review',
                      'LTA guide may exclude GST; operator billing/grace and tariff-boundary semantics need confirmation.']
        else:
            facts = {'development':name,'reason':'aggregate_carpark_identity' if code=='17' else 'no_exact_guide_match'}
            values = ['missing-20260930-'+code,'LTA',code,'unresolved',None,AT,None,
                      facts,'no_source','No confirmed carpark-specific numeric tariff; never copy a nearby or similarly named tariff.']
        evidence_rows.append(values)
    entries = reviewed_catalog()
    for entry in entries:
        evidence_rows.append(['operator-20260930-'+entry['carpark_id'],'LTA',entry['carpark_id'],
            'operator_page',entry['source_url'],AT,None,
            {'grace_minutes':entry['grace_minutes'],'rules':entry['rules']},'verified_facts',entry['note']])
    output.append('INSERT INTO parking_data.tariff_source_evidence '
                  '(capture_key,agency,carpark_id,source_kind,source_url,captured_at,content_sha256,'
                  'published_facts,review_status,review_note) VALUES\n'+',\n'.join(
                  '('+','.join(sql_json(x) if isinstance(x,dict) else sql(x) for x in row)+')'
                  for row in evidence_rows)+'\nON CONFLICT DO NOTHING;')
    for entry in entries:
        key = 'operator-20260930-'+entry['carpark_id']
        config = {'agency':'LTA','parking_system':'operator_eps','no_cross_window':True,**entry['config']}
        values = ['LTA',entry['carpark_id'],'operator_published',entry['source_url'],AT,
                  'rule_specific',entry['grace_minutes'],'verified','ParkChoiceSG source review',AT,
                  entry['note'],key,'window_rules_v1',config,'partial']
        output.append('INSERT INTO parking_data.rate_schedules '
            '(agency,carpark_id,source,source_url,valid_from,billing_method,grace_minutes,review_status,'
            'reviewed_by,reviewed_at,review_note,seed_key,calculator_key,calculator_config,coverage_scope) VALUES ('+
            ','.join(sql_json(x) if isinstance(x,dict) else sql(x) for x in values)+') ON CONFLICT DO NOTHING;')
        for index,rule in enumerate(entry['rules']):
            values = [rule['day_type'],rule['start_time'],rule['end_time'],rule['rule_kind'],
                      rule['amount_cents'],rule['unit_minutes'],rule['description'],rule['priority'],
                      str(index),rule['review_status'],rule['calculation']]
            output.append('INSERT INTO parking_data.rate_schedule_rules '
                '(schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,description,'
                'priority,rule_key,review_status,calculation) SELECT schedule_id,'+
                ','.join(sql_json(x) if isinstance(x,dict) else sql(x) for x in values)+
                ' FROM parking_data.rate_schedules WHERE seed_key='+sql(key)+' ON CONFLICT DO NOTHING;')
    output.append('COMMIT;')
    sql_path.write_text('\n'.join(output)+'\n',encoding='utf-8')
    catalog_path.write_text(json.dumps({'checked_at':AT,'operator_tariffs':entries,
                                     'all_lta_evidence':evidence_rows},indent=2,ensure_ascii=False),encoding='utf-8')
    return {'lta_carparks':len(IDS),'guide_matches':sum(ALIASES.get(c) in rows for c in IDS),
            'operator_calculators':len(entries),'evidence_rows':len(evidence_rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('guide_manifest',type=Path)
    parser.add_argument('--output',type=Path,default=Path('seed_operator_rates.sql'))
    parser.add_argument('--catalog',type=Path,default=Path('operator_tariffs_reviewed.json'))
    args = parser.parse_args()
    print(json.dumps(generate(args.guide_manifest,args.output,args.catalog)))


if __name__=='__main__':
    main()
