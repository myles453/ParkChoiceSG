"""Attach immutable source flags to HDB seeds using their original verified archive.

Does not change rates, review dates or validity. Only schedules whose stored
reference capture exactly matches this archive receive a baseline.
"""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
from provider_puller import load_local_env


def verified_flags(root):
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    flags = {}
    pages = [r for r in manifest['raw'] if Path(r.get('file') or r['path']).name.startswith('reference-')]
    if not pages:
        raise ValueError('No reference pages in archive')
    for item in pages:
        path = root/Path(item.get('file') or item['path']).name
        raw = gzip.decompress(path.read_bytes())
        if hashlib.sha256(raw).hexdigest() != item['sha256']:
            raise ValueError('Reference checksum mismatch')
        for row in json.loads(raw)['result']['records']:
            flags[row['car_park_no'].strip().upper()] = {
                'parking_system':row.get('type_of_parking_system'),
                'short_term_parking':row.get('short_term_parking'),
                'free_parking':row.get('free_parking'),
                'night_parking':row.get('night_parking')}
    if len(flags) != manifest['reference_count']:
        raise ValueError('Reference count mismatch')
    return manifest,flags


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('original_seed_archive',type=Path)
    args = parser.parse_args()
    manifest,flags = verified_flags(args.original_seed_archive)
    load_local_env()
    import psycopg
    from psycopg.types.json import Jsonb
    try:
        with psycopg.connect(os.environ['DATABASE_URL'],sslmode='require',
                             connect_timeout=15,prepare_threshold=None) as connection:
            with connection.cursor() as cursor:
                cursor.executemany("""UPDATE parking_data.rate_schedules
                    SET calculator_config=calculator_config || jsonb_build_object('reference_flags',%s::jsonb)
                    WHERE agency='HDB' AND source='hdb_policy' AND carpark_id=%s
                      AND (calculator_config->>'reference_retrieved_at')::timestamptz=%s::timestamptz
                      AND NOT calculator_config ? 'reference_flags'""",
                    [(Jsonb(value),code,manifest['reference_retrieved_at']) for code,value in flags.items()])
                print(json.dumps({'baselines_attached':cursor.rowcount,'source_run_id':manifest['run_id']}))
    except Exception as exc:
        raise SystemExit(f'Baseline attachment failed ({type(exc).__name__}); connection details withheld.') from None


if __name__ == '__main__':
    main()
