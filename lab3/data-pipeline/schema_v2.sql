-- Apply after schema.sql. Private, provenance-preserving comparison layer.
-- Existing raw observations remain untouched. No tariff is approved by this migration.
BEGIN;

CREATE TABLE IF NOT EXISTS parking_data.carpark_identities (
    agency text NOT NULL CHECK (agency IN ('HDB', 'LTA', 'URA')),
    carpark_id text NOT NULL CHECK (carpark_id ~ '^[A-Z0-9]+$'),
    display_name text,
    address text,
    name_source text,
    metadata_retrieved_at timestamptz,
    PRIMARY KEY (agency, carpark_id)
);

-- A source code is linked only when its agency and code have been verified.
-- The initial exact-code links never merge different agencies or fuzzy names.
CREATE TABLE IF NOT EXISTS parking_data.source_carpark_codes (
    feed text NOT NULL CHECK (feed IN ('hdb_direct', 'lta_datamall', 'ura_direct')),
    source_agency text NOT NULL CHECK (source_agency IN ('HDB', 'LTA', 'URA')),
    source_code text NOT NULL CHECK (source_code ~ '^[A-Z0-9]+$'),
    agency text NOT NULL,
    carpark_id text NOT NULL,
    match_method text NOT NULL CHECK (match_method IN ('exact_agency_code', 'manual_verified')),
    verified_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (feed, source_agency, source_code),
    FOREIGN KEY (agency, carpark_id)
        REFERENCES parking_data.carpark_identities (agency, carpark_id),
    CHECK (match_method <> 'exact_agency_code'
        OR (source_agency = agency AND source_code = carpark_id))
);
CREATE INDEX IF NOT EXISTS source_carpark_codes_identity_idx
    ON parking_data.source_carpark_codes (agency, carpark_id);

-- One immutable source row per response position. Keep the original JSON and
-- parsed fields side by side so parsing decisions can be audited or revised.
CREATE TABLE IF NOT EXISTS parking_data.ura_rate_rows (
    run_id uuid NOT NULL REFERENCES parking_data.ingestion_runs (run_id),
    row_number integer NOT NULL CHECK (row_number >= 0),
    pp_code text NOT NULL CHECK (pp_code ~ '^[A-Z0-9]+$'),
    pp_name text NOT NULL,
    vehicle_category text NOT NULL CHECK (vehicle_category IN ('Car', 'Motorcycle', 'Heavy Vehicle')),
    parking_system text,
    park_capacity integer CHECK (park_capacity >= 0),
    start_time time,
    end_time time,
    parse_flags text[] NOT NULL DEFAULT '{}',
    raw jsonb NOT NULL,
    PRIMARY KEY (run_id, row_number)
);
CREATE INDEX IF NOT EXISTS ura_rate_rows_code_category_idx
    ON parking_data.ura_rate_rows (pp_code, vehicle_category, run_id);

CREATE TABLE IF NOT EXISTS parking_data.ura_rate_day_rules (
    run_id uuid NOT NULL,
    row_number integer NOT NULL,
    day_type text NOT NULL CHECK (day_type IN ('weekday', 'saturday', 'sunday_ph')),
    amount_cents integer CHECK (amount_cents >= 0),
    unit_minutes integer CHECK (unit_minutes >= 0),
    interpretation text NOT NULL CHECK (interpretation IN
        ('per_unit', 'zero_zero_review', 'long_period_review', 'missing', 'invalid')),
    PRIMARY KEY (run_id, row_number, day_type),
    FOREIGN KEY (run_id, row_number)
        REFERENCES parking_data.ura_rate_rows (run_id, row_number)
);
-- Verified pricing is separate from raw provider rules. No application quote
-- should use an unverified schedule or infer a price for an unmatched code.
CREATE TABLE IF NOT EXISTS parking_data.rate_schedules (
    schedule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agency text NOT NULL,
    carpark_id text NOT NULL,
    source text NOT NULL CHECK (source IN ('ura_details', 'hdb_policy', 'operator_published', 'operator_override')),
    source_run_id uuid REFERENCES parking_data.ingestion_runs (run_id),
    source_url text,
    valid_from timestamptz NOT NULL,
    valid_until timestamptz,
    billing_method text CHECK (billing_method IN ('per_minute', 'round_up_unit', 'rule_specific')),
    grace_minutes integer CHECK (grace_minutes >= 0),
    review_status text NOT NULL DEFAULT 'pending_review'
        CHECK (review_status IN ('pending_review', 'verified', 'rejected', 'superseded')),
    reviewed_by text,
    reviewed_at timestamptz,
    review_note text,
    FOREIGN KEY (agency, carpark_id)
        REFERENCES parking_data.carpark_identities (agency, carpark_id),
    CHECK (valid_until IS NULL OR valid_until > valid_from),
    CHECK (review_status <> 'verified' OR
           (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL
            AND billing_method IS NOT NULL AND grace_minutes IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS rate_schedules_identity_idx
    ON parking_data.rate_schedules (agency, carpark_id, valid_from DESC);
CREATE INDEX IF NOT EXISTS rate_schedules_source_run_idx
    ON parking_data.rate_schedules (source_run_id) WHERE source_run_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS rate_schedules_one_current_verified_idx
    ON parking_data.rate_schedules (agency, carpark_id)
    WHERE review_status = 'verified' AND valid_until IS NULL;

CREATE TABLE IF NOT EXISTS parking_data.rate_schedule_rules (
    rule_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    schedule_id bigint NOT NULL REFERENCES parking_data.rate_schedules (schedule_id),
    day_type text NOT NULL CHECK (day_type IN ('weekday', 'saturday', 'sunday_ph')),
    start_time time NOT NULL,
    end_time time NOT NULL,
    rule_kind text NOT NULL CHECK (rule_kind IN ('per_unit', 'free', 'flat', 'cap')),
    amount_cents integer NOT NULL CHECK (amount_cents >= 0),
    unit_minutes integer CHECK (unit_minutes > 0),
    description text,
    CHECK ((rule_kind = 'per_unit' AND unit_minutes IS NOT NULL)
        OR (rule_kind <> 'per_unit' AND unit_minutes IS NULL))
);
CREATE INDEX IF NOT EXISTS rate_schedule_rules_schedule_idx
    ON parking_data.rate_schedule_rules (schedule_id, day_type);

CREATE TABLE IF NOT EXISTS parking_data.sg_public_holidays (
    holiday_date date PRIMARY KEY,
    holiday_name text NOT NULL,
    source_url text NOT NULL,
    verified_at timestamptz NOT NULL
);

-- Seed exact identities from existing data. URA rate-only identities are added
-- by the rate importer after it validates the archived response.
INSERT INTO parking_data.carpark_identities (agency, carpark_id, display_name, address, name_source, metadata_retrieved_at)
SELECT 'HDB', carpark_id, address, address, 'hdb_reference', reference_retrieved_at
FROM parking_data.carparks WHERE source = 'hdb'
ON CONFLICT (agency, carpark_id) DO UPDATE
SET display_name = EXCLUDED.display_name,
    address = EXCLUDED.address,
    name_source = EXCLUDED.name_source,
    metadata_retrieved_at = EXCLUDED.metadata_retrieved_at
WHERE parking_data.carpark_identities.metadata_retrieved_at IS NULL
   OR parking_data.carpark_identities.metadata_retrieved_at < EXCLUDED.metadata_retrieved_at;

INSERT INTO parking_data.carpark_identities (agency, carpark_id)
SELECT DISTINCT 'HDB', carpark_id FROM parking_data.availability_observations WHERE source = 'hdb'
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.carpark_identities (agency, carpark_id)
SELECT DISTINCT agency, carpark_id FROM parking_data.provider_availability_snapshots
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.source_carpark_codes
    (feed, source_agency, source_code, agency, carpark_id, match_method)
SELECT DISTINCT 'hdb_direct', 'HDB', carpark_id, 'HDB', carpark_id, 'exact_agency_code'
FROM parking_data.carpark_identities WHERE agency = 'HDB'
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.source_carpark_codes
    (feed, source_agency, source_code, agency, carpark_id, match_method)
SELECT DISTINCT feed, agency, carpark_id, agency, carpark_id, 'exact_agency_code'
FROM parking_data.provider_availability_snapshots
ON CONFLICT DO NOTHING;

-- LTA's Development label is the best available name for its own carparks.
UPDATE parking_data.carpark_identities c
SET display_name = p.development,
    name_source = 'lta_datamall',
    metadata_retrieved_at = p.retrieved_at
FROM (
    SELECT DISTINCT ON (carpark_id) carpark_id,
           NULLIF(btrim(attributes->>'Development'), '') AS development,
           retrieved_at
    FROM parking_data.provider_availability_snapshots
    WHERE agency = 'LTA' AND lot_type = 'C'
    ORDER BY carpark_id, retrieved_at DESC
) p
WHERE c.agency = 'LTA' AND c.carpark_id = p.carpark_id
  AND p.development IS NOT NULL
  AND (c.metadata_retrieved_at IS NULL OR c.metadata_retrieved_at < p.retrieved_at);

CREATE OR REPLACE VIEW parking_data.hdb_parking_policy_flags
WITH (security_invoker = true) AS
SELECT carpark_id,
       reference_data->>'type_of_parking_system' AS parking_system,
       reference_data->>'short_term_parking' AS short_term_parking,
       reference_data->>'free_parking' AS free_parking,
       reference_data->>'night_parking' AS night_parking,
       reference_retrieved_at
FROM parking_data.carparks WHERE source = 'hdb';

-- Live evidence only: historical backfill is excluded. Provider retrieval time
-- is explicitly marked as a proxy, not a provider's source-update timestamp.
CREATE OR REPLACE VIEW parking_data.car_availability_evidence
WITH (security_invoker = true) AS
SELECT m.agency, m.carpark_id, 'hdb_direct'::text AS feed,
       a.lots_available, a.total_lots, a.source_updated_at AS evidence_at,
       a.first_retrieved_at AS retrieved_at, 'source_update'::text AS timestamp_kind,
       a.quality_flags, a.run_id
FROM parking_data.availability_observations a
JOIN parking_data.ingestion_runs r ON r.run_id = a.run_id AND r.query_time IS NULL
JOIN parking_data.source_carpark_codes m
  ON m.feed = 'hdb_direct' AND m.source_agency = 'HDB' AND m.source_code = a.carpark_id
WHERE a.source = 'hdb' AND a.lot_type = 'C'
UNION ALL
SELECT m.agency, m.carpark_id, p.feed, p.lots_available, NULL::integer,
       p.retrieved_at, p.retrieved_at, 'retrieval'::text, ARRAY[]::text[], p.run_id
FROM parking_data.provider_availability_snapshots p
JOIN parking_data.source_carpark_codes m
  ON m.feed = p.feed AND m.source_agency = p.agency AND m.source_code = p.carpark_id
WHERE p.lot_type = 'C';

CREATE OR REPLACE VIEW parking_data.car_latest_availability
WITH (security_invoker = true) AS
WITH latest_per_feed AS (
    SELECT e.*,
           row_number() OVER (PARTITION BY agency, carpark_id, feed
                              ORDER BY evidence_at DESC, retrieved_at DESC) AS feed_rank
    FROM parking_data.car_availability_evidence e
), ranked AS (
    SELECT e.*,
           (e.evidence_at >= now() - interval '15 minutes'
            AND e.evidence_at <= now() + interval '2 minutes'
            AND NOT (e.quality_flags && ARRAY['stale_source', 'zero_capacity', 'unmatched_reference'])) AS is_fresh,
           row_number() OVER (PARTITION BY agency, carpark_id ORDER BY
               CASE WHEN e.evidence_at >= now() - interval '15 minutes'
                          AND e.evidence_at <= now() + interval '2 minutes'
                          AND NOT (e.quality_flags && ARRAY['stale_source', 'zero_capacity', 'unmatched_reference'])
                    THEN 0 ELSE 1 END,
               CASE WHEN e.evidence_at >= now() - interval '15 minutes'
                          AND e.evidence_at <= now() + interval '2 minutes'
                          AND NOT (e.quality_flags && ARRAY['stale_source', 'zero_capacity', 'unmatched_reference'])
                    THEN CASE WHEN e.agency = 'HDB' AND e.feed = 'hdb_direct' THEN 0
                              WHEN e.agency = 'URA' AND e.feed = 'ura_direct' THEN 0 ELSE 1 END
                    ELSE 0 END,
               e.evidence_at DESC, e.retrieved_at DESC) AS choice_rank
    FROM latest_per_feed e WHERE feed_rank = 1
)
SELECT agency, carpark_id, feed, lots_available, total_lots, evidence_at,
       retrieved_at, timestamp_kind, quality_flags, is_fresh, run_id
FROM ranked WHERE choice_rank = 1;

CREATE OR REPLACE VIEW parking_data.carpark_comparison_readiness
WITH (security_invoker = true) AS
SELECT c.agency, c.carpark_id, c.display_name, c.address,
       a.feed AS availability_feed, a.lots_available, a.total_lots,
       a.evidence_at, a.timestamp_kind, coalesce(a.is_fresh, false) AS availability_fresh,
       CASE WHEN s.schedule_id IS NOT NULL THEN 'verified_schedule'
            WHEN c.agency = 'HDB' THEN 'hdb_policy_not_mapped'
            WHEN c.agency = 'URA' AND EXISTS
                (SELECT 1 FROM parking_data.ura_rate_rows u
                 WHERE u.pp_code = c.carpark_id AND u.vehicle_category = 'Car')
                THEN 'ura_rate_requires_review'
            ELSE 'no_verified_rate' END AS pricing_status,
       s.schedule_id AS verified_schedule_id,
       (coalesce(a.is_fresh, false) AND s.schedule_id IS NOT NULL) AS comparison_ready
FROM parking_data.carpark_identities c
LEFT JOIN parking_data.car_latest_availability a
  ON a.agency = c.agency AND a.carpark_id = c.carpark_id
LEFT JOIN LATERAL (
    SELECT schedule_id FROM parking_data.rate_schedules rs
    WHERE rs.agency = c.agency AND rs.carpark_id = c.carpark_id
      AND rs.review_status = 'verified'
      AND rs.valid_from <= now() AND (rs.valid_until IS NULL OR rs.valid_until > now())
      AND EXISTS (SELECT 1 FROM parking_data.rate_schedule_rules rr
                  WHERE rr.schedule_id = rs.schedule_id)
    ORDER BY valid_from DESC LIMIT 1
) s ON true;

ALTER TABLE parking_data.carpark_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.source_carpark_codes ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.ura_rate_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.ura_rate_day_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.rate_schedules ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.rate_schedule_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE parking_data.sg_public_holidays ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON ALL TABLES IN SCHEMA parking_data FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA parking_data FROM PUBLIC, anon, authenticated;
COMMIT;
