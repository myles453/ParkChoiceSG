-- Apply after schema_v4.sql. Private metadata and model input evidence.
-- No tariff is auto-approved and no prediction is fabricated.
BEGIN;

CREATE TABLE IF NOT EXISTS parking_data.carpark_metadata_evidence (
    run_id uuid NOT NULL REFERENCES parking_data.ingestion_runs(run_id),
    source text NOT NULL CHECK (source IN ('hdb_reference','lta_datamall','ura_direct','ura_details')),
    agency text NOT NULL,
    carpark_id text NOT NULL,
    captured_at timestamptz NOT NULL,
    display_name text,
    address text,
    source_crs text CHECK (source_crs IN ('EPSG:3414','EPSG:4326')),
    location_points jsonb NOT NULL CHECK (jsonb_typeof(location_points) = 'array'),
    location_status text NOT NULL CHECK (location_status IN ('single_point','multiple_points','missing','invalid','conflicting')),
    latitude double precision CHECK (latitude BETWEEN 1.15 AND 1.50),
    longitude double precision CHECK (longitude BETWEEN 103.55 AND 104.15),
    car_capacity integer CHECK (car_capacity > 0),
    capacity_status text NOT NULL CHECK (capacity_status IN ('not_published','published_metadata','conflicting_or_invalid','zero_capacity_review')),
    carpark_type text,
    gantry_height_m numeric(5,2) CHECK (gantry_height_m > 0 AND gantry_height_m <= 10),
    quality_flags text[] NOT NULL DEFAULT '{}',
    source_row_count integer NOT NULL CHECK (source_row_count > 0),
    cleaner_version text NOT NULL,
    PRIMARY KEY (run_id,source,agency,carpark_id),
    FOREIGN KEY (agency,carpark_id) REFERENCES parking_data.carpark_identities(agency,carpark_id),
    CHECK ((source='hdb_reference' AND agency='HDB') OR source='lta_datamall'
           OR (source IN ('ura_direct','ura_details') AND agency='URA')),
    CHECK ((location_status='single_point' AND latitude IS NOT NULL AND longitude IS NOT NULL
            AND jsonb_array_length(location_points)=1)
        OR (location_status='multiple_points' AND latitude IS NULL AND longitude IS NULL
            AND jsonb_array_length(location_points)>1)
        OR (location_status IN ('missing','invalid','conflicting') AND latitude IS NULL
            AND longitude IS NULL AND jsonb_array_length(location_points)=0)),
    CHECK ((capacity_status='published_metadata' AND car_capacity IS NOT NULL AND source='ura_details')
        OR (capacity_status<>'published_metadata' AND car_capacity IS NULL))
);
CREATE INDEX IF NOT EXISTS metadata_identity_source_time_idx
    ON parking_data.carpark_metadata_evidence(agency,carpark_id,source,captured_at DESC);

-- A historical row inserted first must not prevent a later *live* retrieval
-- of that same source observation from becoming usable live evidence.
ALTER TABLE parking_data.availability_observations
    ADD COLUMN IF NOT EXISTS first_live_retrieved_at timestamptz,
    ADD COLUMN IF NOT EXISTS live_run_id uuid REFERENCES parking_data.ingestion_runs(run_id);
CREATE INDEX IF NOT EXISTS availability_live_run_idx
    ON parking_data.availability_observations(live_run_id) WHERE live_run_id IS NOT NULL;
UPDATE parking_data.availability_observations a
SET first_live_retrieved_at = a.first_retrieved_at, live_run_id = a.run_id
FROM parking_data.ingestion_runs r
WHERE r.run_id=a.run_id AND r.query_time IS NULL AND a.live_run_id IS NULL;

CREATE TABLE IF NOT EXISTS parking_data.hdb_observation_conflicts (
    run_id uuid NOT NULL REFERENCES parking_data.ingestion_runs(run_id),
    source text NOT NULL,
    carpark_id text NOT NULL,
    lot_type text NOT NULL,
    source_updated_at timestamptz NOT NULL,
    retrieved_at timestamptz NOT NULL,
    lots_available integer NOT NULL CHECK (lots_available>=0),
    total_lots integer NOT NULL CHECK (total_lots>=lots_available),
    PRIMARY KEY (run_id,source,carpark_id,lot_type,source_updated_at)
);
CREATE INDEX IF NOT EXISTS hdb_conflicts_observation_idx
    ON parking_data.hdb_observation_conflicts(source,carpark_id,lot_type,source_updated_at);

-- Replace only the HDB branch, preserving downstream columns and views.
CREATE OR REPLACE VIEW parking_data.car_availability_evidence WITH (security_invoker=true) AS
SELECT m.agency,m.carpark_id,'hdb_direct'::text AS feed,a.lots_available,a.total_lots,
       a.source_updated_at AS evidence_at,a.first_live_retrieved_at AS retrieved_at,
       'source_update'::text AS timestamp_kind,a.quality_flags,a.live_run_id AS run_id
FROM parking_data.availability_observations a
JOIN parking_data.source_carpark_codes m ON m.feed='hdb_direct' AND m.source_agency='HDB'
    AND m.source_code=a.carpark_id
WHERE a.source='hdb' AND a.lot_type='C' AND a.live_run_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM parking_data.hdb_observation_conflicts x
      WHERE (x.source,x.carpark_id,x.lot_type,x.source_updated_at)=
            (a.source,a.carpark_id,a.lot_type,a.source_updated_at))
UNION ALL
SELECT m.agency,m.carpark_id,p.feed,p.lots_available,NULL::integer,
       p.retrieved_at,p.retrieved_at,'retrieval'::text,ARRAY[]::text[],p.run_id
FROM parking_data.provider_availability_snapshots p
JOIN parking_data.source_carpark_codes m ON m.feed=p.feed AND m.source_agency=p.agency
    AND m.source_code=p.carpark_id WHERE p.lot_type='C';

CREATE OR REPLACE VIEW parking_data.carpark_latest_metadata WITH (security_invoker=true) AS
WITH latest AS (
    SELECT e.*, row_number() OVER (PARTITION BY agency,carpark_id,source
        ORDER BY captured_at DESC,run_id DESC) AS source_rank
    FROM parking_data.carpark_metadata_evidence e
)
SELECT * FROM latest WHERE source_rank=1;

-- One authoritative series per agency. LTA copies of HDB/URA stay available
-- for audits/fallback, but are excluded here to avoid training duplication.
-- No present-day reference metadata or tariff is joined into past features.
CREATE OR REPLACE VIEW parking_data.model_car_observations WITH (security_invoker=true) AS
SELECT 'HDB'::text AS agency,a.carpark_id,'hdb_direct'::text AS feed,
       a.source_updated_at AS observed_at,a.first_live_retrieved_at AS known_at,
       'source_update'::text AS timestamp_kind,a.lots_available,a.total_lots,
       a.live_run_id AS run_id
FROM parking_data.availability_observations a
WHERE a.source='hdb' AND a.lot_type='C' AND a.training_eligible AND a.live_run_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM parking_data.hdb_observation_conflicts x
      WHERE (x.source,x.carpark_id,x.lot_type,x.source_updated_at)=
            (a.source,a.carpark_id,a.lot_type,a.source_updated_at))
UNION ALL
SELECT p.agency,p.carpark_id,p.feed,p.retrieved_at,p.retrieved_at,
       'retrieval'::text,p.lots_available,NULL::integer,p.run_id
FROM parking_data.provider_availability_snapshots p
WHERE p.lot_type='C' AND ((p.feed='ura_direct' AND p.agency='URA')
                     OR (p.feed='lta_datamall' AND p.agency='LTA'));

CREATE OR REPLACE VIEW parking_data.carpark_candidate_inputs WITH (security_invoker=true) AS
SELECT i.*,loc.location_points,loc.latitude,loc.longitude,
       loc.source AS location_source,loc.captured_at AS location_captured_at,
       CASE WHEN loc.carpark_id IS NULL THEN 'missing_or_invalid'
            WHEN loc.captured_at < now()-interval '30 days' THEN 'stale'
            ELSE loc.location_status END AS location_status,
       loc.quality_flags AS metadata_quality_flags,
       coalesce(i.total_lots,cap.car_capacity) AS capacity_evidence,
       CASE WHEN i.total_lots IS NOT NULL THEN 'availability_snapshot'
            WHEN cap.car_capacity IS NOT NULL THEN 'ura_details' ELSE 'unknown' END AS capacity_source,
       CASE WHEN i.total_lots IS NOT NULL THEN i.evidence_at ELSE cap.captured_at END AS capacity_evidence_at,
       CASE WHEN coalesce(i.total_lots,cap.car_capacity) IS NULL THEN 'unknown'
            WHEN i.lots_available > coalesce(i.total_lots,cap.car_capacity) THEN 'available_exceeds_capacity'
            ELSE 'consistent' END AS capacity_consistency,
       facilities.carpark_type,facilities.gantry_height_m
FROM parking_data.carpark_comparison_inputs i
LEFT JOIN LATERAL (
    SELECT m.* FROM parking_data.carpark_latest_metadata m
    WHERE m.agency=i.agency AND m.carpark_id=i.carpark_id
      AND m.location_status IN ('single_point','multiple_points')
      AND m.captured_at<=now()+interval '2 minutes'
    ORDER BY CASE WHEN m.captured_at>=now()-interval '30 days' THEN 0 ELSE 1 END,
        CASE m.source WHEN 'hdb_reference' THEN 0 WHEN 'ura_details' THEN 0
                      WHEN 'ura_direct' THEN 1 ELSE 2 END,m.captured_at DESC LIMIT 1
) loc ON true
LEFT JOIN LATERAL (
    SELECT m.* FROM parking_data.carpark_latest_metadata m
    WHERE m.agency=i.agency AND m.carpark_id=i.carpark_id AND m.source='ura_details'
      AND m.capacity_status='published_metadata'
      AND m.captured_at BETWEEN now()-interval '30 days' AND now()+interval '2 minutes'
    LIMIT 1
) cap ON true
LEFT JOIN parking_data.carpark_latest_metadata facilities
    ON facilities.agency=i.agency AND facilities.carpark_id=i.carpark_id AND facilities.source='hdb_reference';

CREATE INDEX IF NOT EXISTS provider_primary_history_idx
    ON parking_data.provider_availability_snapshots(agency,carpark_id,feed,retrieved_at)
    WHERE lot_type='C';

ALTER TABLE parking_data.carpark_metadata_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.hdb_observation_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.carparks ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.availability_observations ENABLE ROW LEVEL SECURITY;
ALTER VIEW parking_data.training_car_observations SET (security_invoker=true);
REVOKE ALL ON SCHEMA parking_data FROM PUBLIC,anon,authenticated;
REVOKE ALL ON ALL TABLES IN SCHEMA parking_data FROM PUBLIC,anon,authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA parking_data FROM PUBLIC,anon,authenticated;
COMMIT;
