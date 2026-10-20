-- Apply after schema_v6.sql. Rate evidence and request-specific calculators.
BEGIN;

ALTER TABLE parking_data.rate_schedules
    ADD COLUMN IF NOT EXISTS seed_key text,
    ADD COLUMN IF NOT EXISTS calculator_key text,
    ADD COLUMN IF NOT EXISTS calculator_config jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS coverage_scope text NOT NULL DEFAULT 'unreviewed'
        CHECK (coverage_scope IN ('unreviewed', 'partial', 'published_windows'));
CREATE UNIQUE INDEX IF NOT EXISTS rate_schedules_seed_key_idx
    ON parking_data.rate_schedules (seed_key) WHERE seed_key IS NOT NULL;
ALTER TABLE parking_data.rate_schedule_rules
    ADD COLUMN IF NOT EXISTS rule_key text,
    ADD COLUMN IF NOT EXISTS review_status text NOT NULL DEFAULT 'pending_review'
        CHECK (review_status IN ('pending_review', 'verified', 'rejected')),
    ADD COLUMN IF NOT EXISTS calculation jsonb NOT NULL DEFAULT '{}'::jsonb;
CREATE UNIQUE INDEX IF NOT EXISTS rate_schedule_rules_key_idx
    ON parking_data.rate_schedule_rules (schedule_id, rule_key)
    WHERE rule_key IS NOT NULL;
ALTER TABLE parking_data.rate_schedule_rules DROP CONSTRAINT IF EXISTS rate_schedule_rules_day_type_check;
ALTER TABLE parking_data.rate_schedule_rules ADD CONSTRAINT rate_schedule_rules_day_type_check
    CHECK (day_type IN ('weekday','saturday','sunday','public_holiday','sunday_ph','all'));

-- Public source facts, including guide-only tariffs that must NOT be quoted.
-- Monetary schedules use integer cents; raw evidence is deliberately separate.
CREATE TABLE IF NOT EXISTS parking_data.tariff_source_evidence (
    evidence_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    capture_key text NOT NULL UNIQUE,
    agency text NOT NULL,
    carpark_id text NOT NULL,
    source_kind text NOT NULL CHECK (source_kind IN
        ('operator_page', 'lta_guide', 'hdb_policy', 'ura_api', 'unresolved')),
    source_url text,
    captured_at timestamptz NOT NULL,
    content_sha256 text CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
    published_facts jsonb NOT NULL,
    review_status text NOT NULL CHECK (review_status IN
        ('verified_facts', 'requires_review', 'no_source')),
    review_note text NOT NULL,
    FOREIGN KEY (agency, carpark_id)
        REFERENCES parking_data.carpark_identities (agency, carpark_id)
);
CREATE INDEX IF NOT EXISTS tariff_source_evidence_identity_idx
    ON parking_data.tariff_source_evidence (agency, carpark_id, captured_at DESC);
ALTER TABLE parking_data.tariff_source_evidence ENABLE ROW LEVEL SECURITY;

-- Protect these restricted-purpose bays even if the reference later changes.
CREATE TABLE IF NOT EXISTS parking_data.hdb_loading_bay_tariffs (
    carpark_id text PRIMARY KEY,
    agency text NOT NULL DEFAULT 'HDB' CHECK (agency = 'HDB'),
    grace_minutes integer NOT NULL CHECK (grace_minutes >= 0),
    first_30_minutes_cents integer NOT NULL CHECK (first_30_minutes_cents >= 0),
    subsequent_30_minutes_cents integer NOT NULL CHECK (subsequent_30_minutes_cents >= 0),
    source_url text NOT NULL,
    checked_at timestamptz NOT NULL,
    FOREIGN KEY (agency, carpark_id)
        REFERENCES parking_data.carpark_identities (agency, carpark_id)
);
ALTER TABLE parking_data.hdb_loading_bay_tariffs ENABLE ROW LEVEL SECURITY;
INSERT INTO parking_data.hdb_loading_bay_tariffs
    (carpark_id, grace_minutes, first_30_minutes_cents,
     subsequent_30_minutes_cents, source_url, checked_at)
SELECT code, CASE WHEN code = 'BRBL' THEN 10 ELSE 15 END, 200, 400,
       'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges',
       now()
FROM unnest(ARRAY['GSML','BRBL','JCML','T55','GEML','KAML','J57L','J60L','TPL','EPL','BL8L','W4L']) code
ON CONFLICT DO NOTHING;

-- This view reports storage coverage, NOT whether an arbitrary stay is priced.
CREATE OR REPLACE VIEW parking_data.carpark_pricing_coverage
WITH (security_invoker = true) AS
SELECT c.agency, c.carpark_id, c.display_name,
       s.schedule_id, s.calculator_key, s.coverage_scope, s.source_url,
       s.valid_from, s.valid_until, s.reviewed_at,
       CASE WHEN lb.carpark_id IS NOT NULL THEN 'loading_bay_not_general_parking'
            WHEN c.agency = 'HDB' AND h.short_term_parking = 'NO'
                THEN 'no_short_term_parking'
            WHEN s.schedule_id IS NOT NULL THEN 'calculator_available_with_guards'
            WHEN e.source_kind = 'lta_guide' THEN 'guide_only_requires_operator_confirmation'
            WHEN e.evidence_id IS NOT NULL THEN 'published_evidence_requires_review'
            ELSE 'rate_source_missing' END AS pricing_storage_status,
       e.source_kind AS latest_evidence_kind, e.review_note AS evidence_note
FROM parking_data.carpark_identities c
LEFT JOIN parking_data.hdb_loading_bay_tariffs lb
  ON c.agency = lb.agency AND c.carpark_id = lb.carpark_id
LEFT JOIN parking_data.hdb_tariff_classification h
  ON c.agency = 'HDB' AND c.carpark_id = h.carpark_id
LEFT JOIN LATERAL (
    SELECT rs.* FROM parking_data.rate_schedules rs
    WHERE rs.agency = c.agency AND rs.carpark_id = c.carpark_id
      AND rs.review_status = 'verified' AND rs.calculator_key IS NOT NULL
      AND rs.valid_from <= now() AND (rs.valid_until IS NULL OR rs.valid_until > now())
    ORDER BY rs.valid_from DESC LIMIT 1
) s ON true
LEFT JOIN LATERAL (
    SELECT es.* FROM parking_data.tariff_source_evidence es
    WHERE es.agency = c.agency AND es.carpark_id = c.carpark_id
    ORDER BY CASE es.source_kind WHEN 'operator_page' THEN 0 ELSE 1 END,
             es.captured_at DESC LIMIT 1
) e ON true;

REVOKE ALL ON ALL TABLES IN SCHEMA parking_data FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA parking_data FROM PUBLIC, anon, authenticated;
COMMIT;
