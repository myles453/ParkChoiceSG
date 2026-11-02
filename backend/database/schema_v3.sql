-- Apply after schema_v2.sql. Source-backed tariff facts and draft rules.
-- This does not verify a price schedule or enable application price quotes.
BEGIN;

ALTER TABLE parking_data.rate_schedule_rules
    ADD COLUMN IF NOT EXISTS priority integer NOT NULL DEFAULT 100,
    ADD COLUMN IF NOT EXISTS source_run_id uuid,
    ADD COLUMN IF NOT EXISTS source_row_number integer,
    ADD COLUMN IF NOT EXISTS source_day_type text;

ALTER TABLE parking_data.rate_schedule_rules
    DROP CONSTRAINT IF EXISTS rate_schedule_rules_day_type_check;
ALTER TABLE parking_data.rate_schedule_rules
    ADD CONSTRAINT rate_schedule_rules_day_type_check
    CHECK (day_type IN ('weekday', 'saturday', 'sunday', 'public_holiday', 'sunday_ph'));

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'parking_data.rate_schedule_rules'::regclass
          AND conname = 'rate_schedule_rules_source_pair_check'
    ) THEN
        ALTER TABLE parking_data.rate_schedule_rules
            ADD CONSTRAINT rate_schedule_rules_source_pair_check
            CHECK ((source_run_id IS NULL AND source_row_number IS NULL AND source_day_type IS NULL)
                OR (source_run_id IS NOT NULL AND source_row_number IS NOT NULL
                    AND source_day_type IS NOT NULL));
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'parking_data.rate_schedule_rules'::regclass
          AND conname = 'rate_schedule_rules_ura_source_fkey'
    ) THEN
        ALTER TABLE parking_data.rate_schedule_rules
            ADD CONSTRAINT rate_schedule_rules_ura_source_fkey
            FOREIGN KEY (source_run_id, source_row_number, source_day_type)
            REFERENCES parking_data.ura_rate_day_rules (run_id, row_number, day_type);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS rate_schedules_source_capture_idx
    ON parking_data.rate_schedules (source, source_run_id, agency, carpark_id)
    WHERE source_run_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS rate_schedule_rules_ura_source_idx
    ON parking_data.rate_schedule_rules
       (schedule_id, source_run_id, source_row_number, source_day_type)
    WHERE source_run_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS rate_schedule_rules_ura_fk_idx
    ON parking_data.rate_schedule_rules (source_run_id, source_row_number, source_day_type)
    WHERE source_run_id IS NOT NULL;

-- Typed HDB policy constants. They are source facts, not per-carpark quotes.
-- The page does not establish a historical effective date; policy_version is
-- the date this version was captured and reviewed for the pilot.
CREATE TABLE IF NOT EXISTS parking_data.hdb_tariff_policy_rules (
    policy_version text NOT NULL,
    rule_code text NOT NULL,
    amount_cents integer NOT NULL CHECK (amount_cents >= 0),
    unit_minutes integer CHECK (unit_minutes > 0),
    rule_kind text NOT NULL CHECK (rule_kind IN ('per_unit', 'cap', 'free')),
    applicability text NOT NULL,
    source_url text NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (policy_version, rule_code),
    CHECK ((rule_kind = 'per_unit' AND unit_minutes IS NOT NULL)
        OR (rule_kind <> 'per_unit' AND unit_minutes IS NULL))
);
ALTER TABLE parking_data.hdb_tariff_policy_rules ENABLE ROW LEVEL SECURITY;

-- Only exceptions named in HDB's official lists are stored. All other HDB
-- references are outside the listed central and peak exception cohorts for
-- this captured policy version, subject to refresh if HDB changes its lists.
CREATE TABLE IF NOT EXISTS parking_data.hdb_tariff_exceptions (
    policy_version text NOT NULL,
    carpark_id text NOT NULL,
    agency text NOT NULL DEFAULT 'HDB' CHECK (agency = 'HDB'),
    central_area boolean NOT NULL DEFAULT false,
    peak_profile text NOT NULL DEFAULT 'none'
        CHECK (peak_profile IN ('none', 'acb_cy', 'se_mon_sat', 'se_daily',
                               'mp_daily', 'hougang_weekend')),
    source_url text NOT NULL,
    captured_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (policy_version, carpark_id),
    FOREIGN KEY (agency, carpark_id)
        REFERENCES parking_data.carpark_identities (agency, carpark_id)
);
CREATE INDEX IF NOT EXISTS hdb_tariff_exceptions_identity_idx
    ON parking_data.hdb_tariff_exceptions (agency, carpark_id);
ALTER TABLE parking_data.hdb_tariff_exceptions ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS parking_data.hdb_peak_windows (
    policy_version text NOT NULL,
    peak_profile text NOT NULL CHECK (peak_profile IN
        ('acb_cy', 'se_mon_sat', 'se_daily', 'mp_daily', 'hougang_weekend')),
    day_type text NOT NULL CHECK (day_type IN
        ('weekday', 'saturday', 'sunday', 'public_holiday')),
    start_time time NOT NULL,
    end_time time NOT NULL CHECK (end_time > start_time),
    source_url text NOT NULL,
    PRIMARY KEY (policy_version, peak_profile, day_type, start_time)
);
ALTER TABLE parking_data.hdb_peak_windows ENABLE ROW LEVEL SECURITY;

-- An absent date is only "not a holiday" for a year whose calendar has been
-- loaded. Observed days remain distinguishable from gazetted holiday dates.
ALTER TABLE parking_data.sg_public_holidays
    ADD COLUMN IF NOT EXISTS holiday_kind text NOT NULL DEFAULT 'gazetted'
        CHECK (holiday_kind IN ('gazetted', 'observed'));
CREATE TABLE IF NOT EXISTS parking_data.sg_holiday_year_coverage (
    calendar_year integer PRIMARY KEY CHECK (calendar_year BETWEEN 2000 AND 2100),
    source_url text NOT NULL,
    checked_at timestamptz NOT NULL,
    note text NOT NULL
);
ALTER TABLE parking_data.sg_holiday_year_coverage ENABLE ROW LEVEL SECURITY;

INSERT INTO parking_data.hdb_tariff_policy_rules
    (policy_version, rule_code, amount_cents, unit_minutes, rule_kind,
     applicability, source_url) VALUES
('2026-09-28-observed', 'outside_standard', 60, 30, 'per_unit',
 'Motor car, outside Central Area, ordinary hours',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'central_mon_sat_07_17', 120, 30, 'per_unit',
 'Motor car, Central Area, Monday-Saturday 07:00-17:00, non-peak',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'central_other_hours', 60, 30, 'per_unit',
 'Motor car, Central Area, other hours, non-peak',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'outside_peak', 80, 30, 'per_unit',
 'Motor car, outside Central Area, listed peak-hour carparks during their published peak windows',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'central_day_peak', 140, 30, 'per_unit',
 'Motor car, Central Area, Monday-Saturday 07:00-17:00 during published peak windows',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'central_other_peak', 80, 30, 'per_unit',
 'Motor car, Central Area, other hours during published peak windows',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'night_cap', 500, NULL, 'cap',
 'Motor car, night parking scheme, 22:30-07:00; not for peak-hour carparks',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'outside_day_cap', 1200, NULL, 'cap',
 'Motor car, non-Central Area, applicable day/whole-day window; not for peak-hour carparks',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'central_day_cap', 2000, NULL, 'cap',
 'Motor car, Central Area, applicable day/whole-day window; not for peak-hour carparks',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'),
('2026-09-28-observed', 'sun_ph_free', 0, NULL, 'free',
 'Motor car, only where HDB reference flags Sunday/public-holiday free parking; usually 07:00-22:30, with some 13:00 starts',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/free-parking-scheme-on-sundays-and-public-holidays')
ON CONFLICT (policy_version, rule_code) DO NOTHING;

INSERT INTO parking_data.hdb_tariff_exceptions
    (policy_version, carpark_id, central_area, peak_profile, source_url)
SELECT '2026-09-28-observed', v.carpark_id, v.central_area, v.peak_profile,
       'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'
FROM (VALUES
    ('ACB', true, 'acb_cy'), ('BBB', true, 'none'), ('BRB1', true, 'none'),
    ('CY', true, 'acb_cy'), ('DUXM', true, 'none'), ('HLM', true, 'none'),
    ('KAB', true, 'none'), ('KAM', true, 'none'), ('KAS', true, 'none'),
    ('PRM', true, 'none'), ('SLS', true, 'none'), ('SR1', true, 'none'),
    ('SR2', true, 'none'), ('TPM', true, 'none'), ('UCS', true, 'none'),
    ('WCB', true, 'none'),
    ('SE21', false, 'se_mon_sat'), ('SE22', false, 'se_mon_sat'),
    ('SE24', false, 'se_daily'),
    ('MP14', false, 'mp_daily'), ('MP15', false, 'mp_daily'),
    ('MP16', false, 'mp_daily'),
    ('HG9', false, 'hougang_weekend'), ('HG9T', false, 'hougang_weekend'),
    ('HG15', false, 'hougang_weekend'), ('HG16', false, 'hougang_weekend')
) AS v(carpark_id, central_area, peak_profile)
JOIN parking_data.carpark_identities c
  ON c.agency = 'HDB' AND c.carpark_id = v.carpark_id
ON CONFLICT (policy_version, carpark_id) DO NOTHING;

INSERT INTO parking_data.hdb_peak_windows
    (policy_version, peak_profile, day_type, start_time, end_time, source_url)
SELECT '2026-09-28-observed', v.peak_profile, v.day_type,
       v.start_time::time, v.end_time::time,
       'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges'
FROM (VALUES
    ('acb_cy', 'weekday', '10:00', '18:00'),
    ('acb_cy', 'saturday', '08:00', '19:00'),
    ('acb_cy', 'sunday', '08:00', '19:00'),
    ('se_mon_sat', 'weekday', '10:00', '22:00'),
    ('se_mon_sat', 'saturday', '10:00', '22:00'),
    ('se_daily', 'weekday', '10:00', '22:00'),
    ('se_daily', 'saturday', '10:00', '22:00'),
    ('se_daily', 'sunday', '10:00', '22:00'),
    ('se_daily', 'public_holiday', '10:00', '22:00'),
    ('mp_daily', 'weekday', '08:00', '20:00'),
    ('mp_daily', 'saturday', '08:00', '20:00'),
    ('mp_daily', 'sunday', '08:00', '20:00'),
    ('mp_daily', 'public_holiday', '08:00', '20:00'),
    ('hougang_weekend', 'weekday', '11:00', '20:00'),
    ('hougang_weekend', 'saturday', '09:00', '20:00'),
    ('hougang_weekend', 'sunday', '09:00', '20:00')
) AS v(peak_profile, day_type, start_time, end_time)
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.sg_public_holidays
    (holiday_date, holiday_name, source_url, verified_at, holiday_kind)
SELECT v.holiday_date::date, v.holiday_name,
       'https://www.mom.gov.sg/newsroom/press-releases/2025/0616-public-holidays-for-2026',
       now(), v.holiday_kind
FROM (VALUES
    ('2026-01-01', 'New Year''s Day', 'gazetted'),
    ('2026-02-17', 'Chinese New Year (first day)', 'gazetted'),
    ('2026-02-18', 'Chinese New Year (second day)', 'gazetted'),
    ('2026-03-21', 'Hari Raya Puasa', 'gazetted'),
    ('2026-04-03', 'Good Friday', 'gazetted'),
    ('2026-05-01', 'Labour Day', 'gazetted'),
    ('2026-05-27', 'Hari Raya Haji', 'gazetted'),
    ('2026-05-31', 'Vesak Day', 'gazetted'),
    ('2026-06-01', 'Vesak Day observed', 'observed'),
    ('2026-08-09', 'National Day', 'gazetted'),
    ('2026-08-10', 'National Day observed', 'observed'),
    ('2026-11-08', 'Deepavali', 'gazetted'),
    ('2026-11-09', 'Deepavali observed', 'observed'),
    ('2026-12-25', 'Christmas Day', 'gazetted')
) AS v(holiday_date, holiday_name, holiday_kind)
ON CONFLICT (holiday_date) DO NOTHING;

INSERT INTO parking_data.sg_holiday_year_coverage
    (calendar_year, source_url, checked_at, note)
VALUES (2026,
        'https://www.mom.gov.sg/newsroom/press-releases/2025/0616-public-holidays-for-2026',
        now(),
        '11 gazetted dates plus three Monday observed days. Parking treatment of observed days requires separate HDB/URA confirmation.')
ON CONFLICT (calendar_year) DO NOTHING;

CREATE OR REPLACE VIEW parking_data.hdb_tariff_classification
WITH (security_invoker = true) AS
SELECT h.carpark_id, h.parking_system, h.short_term_parking,
       h.free_parking, h.night_parking,
       coalesce(e.central_area, false) AS central_area,
       coalesce(e.peak_profile, 'none') AS peak_profile,
       CASE h.free_parking
           WHEN 'SUN & PH FR 7AM-10.30PM' THEN time '07:00'
           WHEN 'SUN & PH FR 1PM-10.30PM' THEN time '13:00'
           ELSE NULL END AS sunday_ph_free_from,
       (h.parking_system IN ('ELECTRONIC PARKING', 'COUPON PARKING')
        AND h.short_term_parking IN ('WHOLE DAY', '7AM-10.30PM', '7AM-7PM', 'NO')
        AND h.free_parking IN ('NO', 'SUN & PH FR 7AM-10.30PM',
                               'SUN & PH FR 1PM-10.30PM')
        AND h.night_parking IN ('YES', 'NO')) AS reference_flags_recognized,
       h.reference_retrieved_at,
       '2026-09-28-observed'::text AS policy_version
FROM parking_data.hdb_parking_policy_flags h
LEFT JOIN parking_data.hdb_tariff_exceptions e
  ON e.policy_version = '2026-09-28-observed' AND e.carpark_id = h.carpark_id;

-- Draft URA schedules use retrieval time only as the first captured policy
-- version. They make no claim about historical effective dates. Only plain
-- per-unit rows are copied; free-looking and long-period rows remain in raw
-- staging for explicit interpretation during review.
INSERT INTO parking_data.rate_schedules
    (agency, carpark_id, source, source_run_id, source_url, valid_from,
     review_status, review_note)
SELECT 'URA', r.pp_code, 'ura_details', r.run_id,
       'https://eservice.ura.gov.sg/maps/api/', ir.retrieved_at,
       'pending_review',
       'Draft from captured URA data. Per-unit entries only; free/zero and long-period entries require interpretation. Billing method, grace period, time-window coverage and effective date require review.'
FROM parking_data.ura_rate_rows r
JOIN parking_data.ingestion_runs ir ON ir.run_id = r.run_id
WHERE r.vehicle_category = 'Car'
GROUP BY r.run_id, r.pp_code, ir.retrieved_at
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.rate_schedule_rules
    (schedule_id, day_type, start_time, end_time, rule_kind,
     amount_cents, unit_minutes, description, priority,
     source_run_id, source_row_number, source_day_type)
SELECT s.schedule_id, d.day_type, r.start_time, r.end_time,
       'per_unit', d.amount_cents, d.unit_minutes,
       'Unverified URA per-unit rule; see linked source row', 100,
       d.run_id, d.row_number, d.day_type
FROM parking_data.ura_rate_rows r
JOIN parking_data.ura_rate_day_rules d
  ON d.run_id = r.run_id AND d.row_number = r.row_number
JOIN parking_data.rate_schedules s
  ON s.source = 'ura_details' AND s.source_run_id = r.run_id
 AND s.agency = 'URA' AND s.carpark_id = r.pp_code
WHERE r.vehicle_category = 'Car' AND d.interpretation = 'per_unit'
  AND r.start_time IS NOT NULL AND r.end_time IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW parking_data.ura_rate_draft_audit
WITH (security_invoker = true) AS
SELECT s.schedule_id, s.carpark_id, s.source_run_id,
       count(*) FILTER (WHERE d.interpretation = 'per_unit') AS parsed_per_unit,
       count(*) FILTER (WHERE d.interpretation = 'zero_zero_review') AS zero_zero_review,
       count(*) FILTER (WHERE d.interpretation = 'long_period_review') AS long_period_review,
       count(*) FILTER (WHERE d.interpretation = 'missing') AS missing,
       count(*) FILTER (WHERE d.interpretation = 'invalid') AS invalid,
       count(DISTINCT rr.rule_id) AS draft_rules
FROM parking_data.rate_schedules s
JOIN parking_data.ura_rate_rows r
  ON r.run_id = s.source_run_id AND r.pp_code = s.carpark_id
 AND r.vehicle_category = 'Car'
JOIN parking_data.ura_rate_day_rules d
  ON d.run_id = r.run_id AND d.row_number = r.row_number
LEFT JOIN parking_data.rate_schedule_rules rr
  ON rr.schedule_id = s.schedule_id AND rr.source_run_id = d.run_id
 AND rr.source_row_number = d.row_number AND rr.source_day_type = d.day_type
WHERE s.source = 'ura_details'
GROUP BY s.schedule_id, s.carpark_id, s.source_run_id;

REVOKE ALL ON ALL TABLES IN SCHEMA parking_data FROM PUBLIC, anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA parking_data FROM PUBLIC, anon, authenticated;
COMMIT;
