-- Run once in the Supabase SQL editor (or psql). This is a private ingestion schema.
-- Do not add parking_data to the Data API exposed schemas or grant anon/authenticated access.
BEGIN;
CREATE SCHEMA IF NOT EXISTS parking_data;
REVOKE ALL ON SCHEMA parking_data FROM PUBLIC;

CREATE TABLE IF NOT EXISTS parking_data.ingestion_runs (
    run_id uuid PRIMARY KEY,
    retrieved_at timestamptz NOT NULL,
    query_time timestamptz,
    manifest jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS parking_data.carparks (
    source text NOT NULL,
    carpark_id text NOT NULL,
    address text,
    reference_data jsonb NOT NULL,
    reference_retrieved_at timestamptz NOT NULL,
    PRIMARY KEY (source, carpark_id)
);
CREATE TABLE IF NOT EXISTS parking_data.availability_observations (
    source text NOT NULL,
    carpark_id text NOT NULL,
    lot_type text NOT NULL CHECK (lot_type IN ('C','M','H','Y')),
    source_updated_at timestamptz NOT NULL,
    first_retrieved_at timestamptz NOT NULL,
    lots_available integer NOT NULL CHECK (lots_available >= 0),
    total_lots integer NOT NULL CHECK (total_lots >= 0 AND lots_available <= total_lots),
    quality_flags text[] NOT NULL DEFAULT '{}',
    training_eligible boolean NOT NULL,
    run_id uuid NOT NULL REFERENCES parking_data.ingestion_runs(run_id),
    PRIMARY KEY (source, carpark_id, lot_type, source_updated_at)
    -- Unmatched IDs intentionally retained with a quality flag, not discarded by a FK.
);
CREATE INDEX IF NOT EXISTS availability_by_time
    ON parking_data.availability_observations(source_updated_at);
CREATE INDEX IF NOT EXISTS availability_by_run
    ON parking_data.availability_observations(run_id);

-- LTA/URA feeds do not publish the per-carpark update time or total lot count.
-- Each polling run is a separate retrieval-time snapshot, not an HDB observation.
CREATE TABLE IF NOT EXISTS parking_data.provider_availability_snapshots (
    run_id uuid NOT NULL REFERENCES parking_data.ingestion_runs(run_id),
    feed text NOT NULL CHECK (feed IN ('lta_datamall', 'ura_direct')),
    agency text NOT NULL CHECK (agency IN ('HDB', 'LTA', 'URA')),
    carpark_id text NOT NULL,
    lot_type text NOT NULL CHECK (lot_type IN ('C', 'M', 'H', 'Y')),
    retrieved_at timestamptz NOT NULL,
    lots_available integer NOT NULL CHECK (lots_available >= 0),
    attributes jsonb NOT NULL,
    PRIMARY KEY (run_id, agency, carpark_id, lot_type),
    CHECK (feed <> 'ura_direct' OR agency = 'URA'),
    CHECK ((feed = 'ura_direct' AND lot_type IN ('C', 'M', 'H'))
        OR (feed = 'lta_datamall' AND lot_type IN ('C', 'H', 'Y')))
);
CREATE INDEX IF NOT EXISTS provider_snapshots_by_time
    ON parking_data.provider_availability_snapshots(retrieved_at);
ALTER TABLE parking_data.provider_availability_snapshots ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE VIEW parking_data.training_car_observations AS
SELECT source, carpark_id, source_updated_at, first_retrieved_at,
       lots_available, total_lots,
       source_updated_at AT TIME ZONE 'Asia/Singapore' AS observed_at_singapore,
       EXTRACT(ISODOW FROM source_updated_at AT TIME ZONE 'Asia/Singapore')::integer AS weekday,
       EXTRACT(HOUR FROM source_updated_at AT TIME ZONE 'Asia/Singapore')::integer AS hour,
       EXTRACT(MINUTE FROM source_updated_at AT TIME ZONE 'Asia/Singapore')::integer AS minute
FROM parking_data.availability_observations
WHERE lot_type = 'C' AND training_eligible;

REVOKE ALL ON ALL TABLES IN SCHEMA parking_data FROM PUBLIC;
COMMIT;
