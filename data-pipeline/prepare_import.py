"""Prepare repeatable SQL batches from checksum-verified provider archives.

For MCP/SQL-editor import when DATABASE_URL is unavailable. Apply schema_v5
first, then every numbered file in order. Replaying a batch is safe. A run is
marked import_status=complete only by the last batch; do not stop mid-import.
The normal --load collectors use one database transaction instead.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from import_ura_rates import sql, sql_array, sql_json
from metadata_cleaner import metadata_from_run, read_run
from provider_puller import normalize_pages
from puller import normalize, timestamp


def insert(table, columns, rows, suffix="ON CONFLICT DO NOTHING", arrays=(), jsons=()):
    values = []
    for row in rows:
        values.append("(" + ",".join(sql_array(v) if i in arrays else sql_json(v) if i in jsons else sql(v)
                                     for i, v in enumerate(row)) + ")")
    return f"INSERT INTO parking_data.{table} ({columns}) VALUES\n" + ",\n".join(values) + "\n" + suffix + ";\n"


def prepare(directory, output, batch_size=250):
    manifest, artifacts = read_run(directory)
    _, metadata, _ = metadata_from_run(directory)
    output.mkdir(parents=True, exist_ok=False)
    queries = []
    def emit(table, columns, rows, suffix="ON CONFLICT DO NOTHING", arrays=(), jsons=()):
        for start in range(0, len(rows), batch_size):
            queries.append(insert(table, columns, rows[start:start+batch_size], suffix, arrays, jsons))

    loading = {**manifest, "import_status": "loading"}
    emit("ingestion_runs", "run_id,retrieved_at,query_time,manifest",
         [(manifest["run_id"], manifest["retrieved_at"], manifest.get("query_time"), loading)], jsons=(3,))
    references, pages, payload = [], [], None
    for name, data, captured in artifacts:
        if name.startswith("reference-"):
            references.extend(data["result"]["records"])
        elif name == "availability.json.gz":
            payload = data
        elif name.startswith("lta-"):
            pages.append((data["value"], timestamp(captured or manifest["retrieved_at"])))
        elif name.startswith("ura-availability"):
            pages.append((data["Result"], timestamp(captured or manifest["retrieved_at"])))
    if manifest.get("provider"):
        feed = "lta_datamall" if manifest["provider"] == "lta" else "ura_direct"
        rows, rejected = normalize_pages(pages, feed)
    else:
        feed = "hdb_direct"
        rows, rejected = normalize(payload, timestamp(manifest["retrieved_at"]),
                                   {r["car_park_no"].strip().upper() for r in references},
                                   timestamp(manifest["query_time"]) if manifest.get("query_time") else None)
    identities = {(r["agency"], r["carpark_id"]) for r in metadata}
    identities.update((r.get("agency", "HDB"), r["carpark_id"]) for r in rows)
    emit("carpark_identities", "agency,carpark_id", sorted(identities))
    authoritative_names = [(r["agency"], r["carpark_id"],r["display_name"],r["address"],r["source"],r["captured_at"])
        for r in metadata if r["display_name"] and
        (r["source"] in {"hdb_reference","ura_details"} or r["agency"]=="LTA")]
    emit("carpark_identities", "agency,carpark_id,display_name,address,name_source,metadata_retrieved_at", authoritative_names,
         """ON CONFLICT (agency,carpark_id) DO UPDATE SET
         display_name=EXCLUDED.display_name,address=coalesce(EXCLUDED.address,carpark_identities.address),
         name_source=EXCLUDED.name_source,metadata_retrieved_at=EXCLUDED.metadata_retrieved_at
         WHERE carpark_identities.metadata_retrieved_at IS NULL
            OR carpark_identities.metadata_retrieved_at<EXCLUDED.metadata_retrieved_at""")
    emit("source_carpark_codes", "feed,source_agency,source_code,agency,carpark_id,match_method",
         [(feed,a,c,a,c,"exact_agency_code") for a,c in sorted(identities)])
    emit("carparks", "source,carpark_id,address,reference_data,reference_retrieved_at",
         [("hdb",r["car_park_no"].strip().upper(),r.get("address"),r,manifest["reference_retrieved_at"]) for r in references],
         """ON CONFLICT (source,carpark_id) DO UPDATE SET address=EXCLUDED.address,
         reference_data=EXCLUDED.reference_data,reference_retrieved_at=EXCLUDED.reference_retrieved_at
         WHERE carparks.reference_retrieved_at<=EXCLUDED.reference_retrieved_at""", jsons=(3,))
    if feed == "hdb_direct":
        for start in range(0,len(rows),batch_size):
            batch = rows[start:start+batch_size]
            incoming = "VALUES\n"+",\n".join("("+",".join(sql(v) for v in (
                r["source"],r["carpark_id"],r["lot_type"],r["source_updated_at"],r["retrieved_at"],
                r["lots_available"],r["total_lots"]))+")" for r in batch)
            queries.append(f"""WITH incoming(source,carpark_id,lot_type,updated,retrieved,available,total) AS ({incoming})
            INSERT INTO parking_data.hdb_observation_conflicts
            (run_id,source,carpark_id,lot_type,source_updated_at,retrieved_at,lots_available,total_lots)
            SELECT {sql(manifest['run_id'])}::uuid,i.source,i.carpark_id,i.lot_type,
                   i.updated::timestamptz,i.retrieved::timestamptz,i.available,i.total
            FROM incoming i JOIN parking_data.availability_observations a ON
                (a.source,a.carpark_id,a.lot_type,a.source_updated_at)=
                (i.source,i.carpark_id,i.lot_type,i.updated::timestamptz)
            WHERE (a.lots_available,a.total_lots)<>(i.available,i.total) ON CONFLICT DO NOTHING;\n""")
            queries.append(insert("availability_observations",
                "source,carpark_id,lot_type,source_updated_at,first_retrieved_at,lots_available,total_lots,quality_flags,training_eligible,run_id,first_live_retrieved_at,live_run_id",
                [(r["source"],r["carpark_id"],r["lot_type"],r["source_updated_at"],r["retrieved_at"],
                  r["lots_available"],r["total_lots"],r["quality_flags"],r["training_eligible"],manifest["run_id"],
                  r["retrieved_at"] if not manifest.get("query_time") else None,
                  manifest["run_id"] if not manifest.get("query_time") else None) for r in batch],
                """ON CONFLICT (source,carpark_id,lot_type,source_updated_at) DO UPDATE SET
                 first_live_retrieved_at=EXCLUDED.first_live_retrieved_at,live_run_id=EXCLUDED.live_run_id
                 WHERE EXCLUDED.live_run_id IS NOT NULL AND
                   (availability_observations.first_live_retrieved_at IS NULL OR
                    EXCLUDED.first_live_retrieved_at<availability_observations.first_live_retrieved_at)
                 AND (availability_observations.lots_available,availability_observations.total_lots)=
                     (EXCLUDED.lots_available,EXCLUDED.total_lots)""", arrays=(7,)))
    else:
        emit("provider_availability_snapshots", "run_id,feed,agency,carpark_id,lot_type,retrieved_at,lots_available,attributes",
             [(manifest["run_id"],r["feed"],r["agency"],r["carpark_id"],r["lot_type"],r["retrieved_at"],r["lots_available"],r["attributes"]) for r in rows], jsons=(7,))
    columns = ["run_id","source","agency","carpark_id","captured_at","display_name","address","source_crs",
               "location_points","location_status","latitude","longitude","car_capacity","capacity_status",
               "carpark_type","gantry_height_m","quality_flags","source_row_count","cleaner_version"]
    emit("carpark_metadata_evidence", ",".join(columns), [tuple(r[c] for c in columns) for r in metadata],arrays=(16,),jsons=(8,))
    # Do not turn floating coordinate literals into quoted strings containing
    # locale commas: sql() emits dot-decimal Python strings cast by PostgreSQL.
    queries.append(f"UPDATE parking_data.ingestion_runs SET manifest=manifest || '{{\"import_status\":\"complete\"}}'::jsonb WHERE run_id={sql(manifest['run_id'])}::uuid;\n")
    for index, query in enumerate(queries):
        (output/f"{index:03d}.sql").write_text("BEGIN;\nSET standard_conforming_strings=on;\n"+query+"COMMIT;\n",encoding="utf-8")
    return {"run_id":manifest["run_id"],"batches":len(queries),"observations":len(rows),"metadata":len(metadata),"rejected":len(rejected)}


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory",type=Path)
    parser.add_argument("output_directory",type=Path)
    args=parser.parse_args()
    print(json.dumps(prepare(args.run_directory,args.output_directory),indent=2))
