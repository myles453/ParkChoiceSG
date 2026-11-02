"""Read-only matching of issued model forecasts to later provider observations."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline_support import load_local_env
from recommendation import read_connection


def evaluate(events,connection,tolerance_minutes=5):
    if not events:
        return {'forecasts':0,'matched':0,'pending':0,'unmatched':0,'groups':{},'results':[]}
    if len({e['forecast_id'] for e in events}) != len(events):
        raise ValueError('Duplicate forecast IDs must be reconciled before evaluation')
    from psycopg.rows import dict_row
    with connection.cursor(row_factory=dict_row) as cursor:
        cursor.execute("""SELECT f.forecast_id,m.observed_at,m.known_at,m.lots_available,m.timestamp_kind
          FROM jsonb_to_recordset(%s::jsonb) AS f(forecast_id text,agency text,carpark_id text,
                        arrival_at timestamptz,recorded_at timestamptz)
          LEFT JOIN LATERAL (
            SELECT observed_at,known_at,lots_available,timestamp_kind
            FROM parking_data.model_car_observations o
            WHERE o.agency=f.agency AND o.carpark_id=f.carpark_id
              AND o.observed_at >= f.arrival_at
              AND o.observed_at <= f.arrival_at+(%s * interval '1 minute')
              AND o.known_at > f.recorded_at AND o.observed_at <= o.known_at
            ORDER BY o.observed_at,o.known_at LIMIT 1
          ) m ON true""",(json.dumps(events),tolerance_minutes))
        outcomes={r['forecast_id']:r for r in cursor.fetchall()}
    now=datetime.now(timezone.utc)
    rows,groups=[],{}
    for event in events:
        target=datetime.fromisoformat(event['arrival_at'])
        outcome=outcomes[event['forecast_id']]
        row={'forecast_id':event['forecast_id'],'agency':event['agency'],
             'carpark_id':event['carpark_id'],'model_version':event['model_version']}
        if outcome['observed_at'] is None:
            row['status']='pending' if (now-target).total_seconds() <= tolerance_minutes*60 else 'unmatched'
        else:
            kind='source_reading' if outcome['timestamp_kind']=='source_update' else 'retrieval_proxy'
            probability = event.get('p_free') is not None
            metric = 'brier' if probability else 'mae_lots'
            actual_free = int(outcome['lots_available'] >= 1)
            error = ((event['p_free']-actual_free)**2 if probability
                     else abs(event['available_lots']-outcome['lots_available']))
            row.update(status='matched',label_kind=kind,actual_lots=outcome['lots_available'],
                       label_offset_seconds=(outcome['observed_at']-target).total_seconds())
            row['brier' if probability else 'absolute_error_lots'] = error
            if probability:
                row['actual_free'] = actual_free
            baseline=event.get('baseline') or {}
            stamp=baseline.get('timestamp')
            if (baseline.get('timestamp_kind')=='source_update' and baseline.get('status')=='fresh_source_update'
                    and isinstance(baseline.get('available_lots'),(int,float)) and stamp
                    and datetime.fromisoformat(stamp)<=datetime.fromisoformat(event['issued_at'])):
                baseline_error = ((int(baseline['available_lots'] >= 1)-actual_free)**2 if probability
                                  else abs(baseline['available_lots']-outcome['lots_available']))
                row['baseline_brier' if probability else 'baseline_absolute_error_lots'] = baseline_error
            horizon=round((target-datetime.fromisoformat(event['issued_at'])).total_seconds()/60)
            key=f"{event['agency']}/{kind}/{event['model_version']}/{horizon}min"
            key += f"/{event.get('mode') or 'count'}/{metric}"
            group=groups.setdefault(key,{'count':0,'model_error_sum':0,'baseline_count':0,
                                        'baseline_error_sum':0,'paired_model_error_sum':0,'metric':metric})
            group['count']+=1
            group['model_error_sum']+=error
            baseline_key = 'baseline_brier' if probability else 'baseline_absolute_error_lots'
            if baseline_key in row:
                group['baseline_count']+=1
                group['baseline_error_sum']+=row[baseline_key]
                group['paired_model_error_sum']+=error
        rows.append(row)
    for g in groups.values():
        metric = g['metric']
        g[metric]=g.pop('model_error_sum')/g['count']
        g['baseline_'+metric]=(g['baseline_error_sum']/g['baseline_count']) if g['baseline_count'] else None
        g['paired_model_'+metric]=(g['paired_model_error_sum']/g['baseline_count']) if g['baseline_count'] else None
        g.pop('baseline_error_sum')
        g.pop('paired_model_error_sum')
    return {'forecasts':len(rows),'matched':sum(r['status']=='matched' for r in rows),
            'pending':sum(r['status']=='pending' for r in rows),'unmatched':sum(r['status']=='unmatched' for r in rows),
            'groups':groups,'results':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forecasts',type=Path,default=Path('data/forecasts/issued.jsonl'))
    parser.add_argument('--output',type=Path,default=Path('data/forecasts/evaluation.json'))
    args=parser.parse_args()
    if not args.forecasts.exists():
        raise SystemExit('No issued forecasts yet. Connect the trained adapter before evaluating forecast accuracy.')
    events=[json.loads(line) for line in args.forecasts.read_text(encoding='utf-8').splitlines() if line.strip()]
    load_local_env()
    with read_connection() as connection:
        report=evaluate(events,connection)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,default=str,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        raise SystemExit(f'Forecast matching failed ({type(exc).__name__}); private details withheld.') from None
