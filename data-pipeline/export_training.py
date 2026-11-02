"""Create arrival-horizon regression pairs with features known at decision time.

Default HDB source-timestamped observations only. --include-retrieval-series
opts in to separate URA-direct and LTA-agency series; their labels measure a
retrieval-time proxy, not confirmed provider freshness. No cross-feed pooling,
current metadata joins, interpolation, missing-count zeroes or random splitting.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import defaultdict
import csv
from datetime import datetime, timedelta, timezone
import json
from itertools import groupby
import os
from pathlib import Path

from metadata_cleaner import read_run
from provider_puller import load_local_env, normalize_pages
from puller import normalize, timestamp, SGT


def primary_observations(directory):
    observations = []
    for folder in sorted(directory.iterdir()):
        if not (folder / "manifest.json").exists():
            continue
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("status") not in {"collected", "loaded"} or manifest.get("query_time"):
            continue
        manifest, artifacts = read_run(folder)
        if manifest.get("provider"):
            feed = "lta_datamall" if manifest["provider"] == "lta" else "ura_direct"
            pages = [(p["value"] if feed == "lta_datamall" else p["Result"], timestamp(t or manifest["retrieved_at"]))
                     for n,p,t in artifacts if n.startswith("lta-") or n.startswith("ura-availability")]
            rows, _ = normalize_pages(pages,feed)
            for r in rows:
                if r["lot_type"] == "C" and ((feed=="lta_datamall" and r["agency"]=="LTA") or feed=="ura_direct"):
                    observations.append({"agency":r["agency"],"carpark_id":r["carpark_id"],"feed":feed,
                        "observed_at":r["retrieved_at"],"known_at":r["retrieved_at"],"timestamp_kind":"retrieval",
                        "lots_available":r["lots_available"],"total_lots":None,"run_id":manifest["run_id"]})
        else:
            refs = {r["car_park_no"].strip().upper() for n,p,_ in artifacts if n.startswith("reference-") for r in p["result"]["records"]}
            payload = next(p for n,p,_ in artifacts if n=="availability.json.gz")
            rows,_ = normalize(payload,timestamp(manifest["retrieved_at"]),refs)
            for r in rows:
                if r["lot_type"]=="C" and r["training_eligible"]:
                    observations.append({"agency":"HDB","carpark_id":r["carpark_id"],"feed":"hdb_direct",
                        "observed_at":r["source_updated_at"],"known_at":r["retrieved_at"],"timestamp_kind":"source_update",
                        "lots_available":r["lots_available"],"total_lots":r["total_lots"],"run_id":manifest["run_id"]})
    return observations


def prepare_observations(rows, include_retrieval=False):
    series, duplicates, conflicts = {}, 0, set()
    for raw in rows:
        if raw["timestamp_kind"] == "retrieval" and not include_retrieval:
            continue
        row = dict(raw)
        for field in ("observed_at","known_at"):
            value = row[field]
            row[field] = timestamp(value) if isinstance(value,str) else value
            if row[field].tzinfo is None:
                raise ValueError("training_timestamp_must_be_aware")
        # A source-clock reading ahead of collection is retained in raw data,
        # but is not suitable for a strictly causal feature/label export.
        if row["observed_at"] > row["known_at"]:
            continue
        key=(row["agency"],row["carpark_id"],row["feed"],row["timestamp_kind"],row["observed_at"])
        if key in series:
            duplicates += 1
            if (row["lots_available"],row["total_lots"]) != (series[key]["lots_available"],series[key]["total_lots"]):
                conflicts.add(key)
            elif row["known_at"]<series[key]["known_at"]:
                series[key]=row
        else:
            series[key]=row
    clean=defaultdict(list)
    for key,row in series.items():
        if key not in conflicts:
            clean[key[:4]].append(row)
    for group in clean.values():
        group.sort(key=lambda r:(r["known_at"],r["observed_at"]))
    return clean,{"duplicates_collapsed":duplicates,"conflicting_source_instants":len(conflicts),
                  "accepted_observations":sum(len(g) for g in clean.values())}


def make_pairs(rows,horizons=(15,30,60),tolerance_minutes=5,include_retrieval=False,split_at=None):
    if not horizons or any(isinstance(h,bool) or not isinstance(h,int) or h<=0 for h in horizons):
        raise ValueError("horizons must be positive whole minutes")
    if not isinstance(tolerance_minutes,int) or tolerance_minutes<0:
        raise ValueError("tolerance must be nonnegative whole minutes")
    if split_at is not None and split_at.tzinfo is None:
        raise ValueError("split_at must be aware")
    groups,audit=prepare_observations(rows,include_retrieval)
    pairs=[]
    for identity,group in groups.items():
        labels=sorted(group,key=lambda r:r["observed_at"])
        label_times=[r["observed_at"] for r in labels]
        history=[]
        for decision,anchors in groupby(group,key=lambda r:r["known_at"]):
            history.extend(anchors)
            # Only a one-hour history is used for these features. Bound memory
            # and avoid scanning weeks of old readings for every sample.
            history=[r for r in history if r["observed_at"]>=decision-timedelta(minutes=60)]
            usable=[r for r in history if r["observed_at"]<=decision]
            if not usable:
                continue
            # Most recently observed reading *known* by this decision; late
            # delivery of an older reading must not replace newer evidence.
            current=max(usable,key=lambda r:r["observed_at"])
            if decision-current["observed_at"]>timedelta(minutes=15):
                continue
            ordered=sorted(usable,key=lambda r:r["observed_at"])
            times=[r["observed_at"] for r in ordered]
            for horizon in sorted(set(horizons)):
                target=decision+timedelta(minutes=horizon)
                pos=bisect_left(label_times,target)
                if pos==len(labels):
                    continue
                label=labels[pos]
                if label["observed_at"]>target+timedelta(minutes=tolerance_minutes):
                    continue
                if split_at and decision<split_at<=label["observed_at"]:
                    # Purge training examples whose targets cross the split.
                    continue
                local=target.astimezone(SGT)
                result={"agency":identity[0],"carpark_id":identity[1],"feed":identity[2],
                    "timestamp_kind":identity[3],"decision_at":decision.isoformat(),"arrival_at":target.isoformat(),
                    "horizon_minutes":horizon,"arrival_weekday":local.isoweekday(),
                    "arrival_slot_15min":(local.hour*60+local.minute)//15,"arrival_is_weekend":local.weekday()>=5,
                    "current_available":current["lots_available"],"current_total_lots":current["total_lots"],
                    "current_free_ratio":current["lots_available"]/current["total_lots"] if current["total_lots"] else None,
                    "current_observed_at":current["observed_at"].isoformat(),"current_known_at":current["known_at"].isoformat(),
                    "current_age_seconds":(decision-current["observed_at"]).total_seconds(),
                    "samples_previous_60min":sum(r["observed_at"]>=decision-timedelta(minutes=60) for r in ordered),
                    "label_available":label["lots_available"],"label_observed_at":label["observed_at"].isoformat(),
                    "label_known_at":label["known_at"].isoformat(),
                    "label_offset_seconds":(label["observed_at"]-target).total_seconds(),
                    "label_kind":"source_reading" if identity[3]=="source_update" else "retrieval_proxy",
                    "feature_run_id":str(current["run_id"]),"label_run_id":str(label["run_id"]),
                    "split":"train" if split_at and decision<split_at else "validation" if split_at else "unsplit"}
                for minutes in (5,15):
                    index=bisect_right(times,decision-timedelta(minutes=minutes))-1
                    lag=ordered[index] if index>=0 else None
                    if lag and decision-timedelta(minutes=minutes)-lag["observed_at"]>timedelta(minutes=15):
                        lag=None
                    result[f"available_lag_{minutes}min"]=lag["lots_available"] if lag else None
                    result[f"lag_{minutes}min_observed_at"]=lag["observed_at"].isoformat() if lag else None
                pairs.append(result)
    audit.update(pairs=len(pairs),horizons_minutes=list(horizons),label_tolerance_minutes=tolerance_minutes,
                 retrieval_series_included=include_retrieval,
                 training_ready=False,note="Readiness requires the model owner's coverage and validation criteria, not just a valid export.")
    return pairs,audit


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archives",type=Path,help="Read verified local runs instead of PostgreSQL")
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--horizons",type=int,nargs="+",default=[15,30,60])
    parser.add_argument("--tolerance-minutes",type=int,default=5)
    parser.add_argument("--include-retrieval-series",action="store_true")
    parser.add_argument("--split-at",help="Aware ISO time for chronological train/validation split")
    args=parser.parse_args()
    if args.archives:
        rows=primary_observations(args.archives)
    else:
        import psycopg
        from psycopg.rows import dict_row
        load_local_env()
        if not os.environ.get("DATABASE_URL"):
            parser.error("DATABASE_URL is not set; alternatively use --archives data")
        try:
            with psycopg.connect(os.environ["DATABASE_URL"],prepare_threshold=None,connect_timeout=15,row_factory=dict_row) as connection:
                rows=connection.execute("SELECT * FROM parking_data.model_car_observations ORDER BY agency,carpark_id,known_at").fetchall()
        except Exception as exc:
            raise SystemExit(f"Training export failed ({type(exc).__name__}); check schema/configuration.") from None
    pairs,audit=make_pairs(rows,args.horizons,args.tolerance_minutes,args.include_retrieval_series,
                           timestamp(args.split_at) if args.split_at else None)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("w",newline="",encoding="utf-8") as stream:
        if pairs:
            writer=csv.DictWriter(stream,list(pairs[0]))
            writer.writeheader()
            writer.writerows(pairs)
    args.output.with_suffix(".manifest.json").write_text(json.dumps(audit,indent=2),encoding="utf-8")
    print(json.dumps(audit,indent=2))


if __name__=="__main__":
    main()
