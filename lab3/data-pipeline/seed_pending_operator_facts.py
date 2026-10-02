"""Store reviewed numeric source facts without authorising an incomplete calculator."""
import argparse
import json
from pathlib import Path
from import_ura_rates import sql, sql_json


def generate(manifest_path, output):
    manifest = {x['url']: x for x in json.loads(manifest_path.read_text(encoding='utf-8'))}
    facts = json.loads(Path(__file__).with_name('operator_tariffs_pending.json').read_text(encoding='utf-8'))
    statements = ['BEGIN;']
    for item in facts:
        capture = manifest[item['source_url']]
        if capture['status'] != 'captured':
            raise ValueError('Cannot seed facts from a failed source capture')
        key = 'operator-pending-' + capture['retrieved_at'][:10] + '-' + item['carpark_id']
        values = [key,'LTA',item['carpark_id'],'operator_page',item['source_url'],capture['retrieved_at'],
                  capture['sha256'],item,'requires_review',item['review_note']]
        statements.append('INSERT INTO parking_data.tariff_source_evidence '
            '(capture_key,agency,carpark_id,source_kind,source_url,captured_at,content_sha256,'
            'published_facts,review_status,review_note) VALUES (' +
            ','.join(sql_json(v) if isinstance(v,dict) else sql(v) for v in values) + ') ON CONFLICT DO NOTHING;')
    statements.append('COMMIT;')
    output.write_text('\n'.join(statements)+'\n',encoding='utf-8')
    return {'operator_fact_rows':len(facts),'new_calculators':0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest',type=Path)
    parser.add_argument('output',type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.manifest,args.output)))
