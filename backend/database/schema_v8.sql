-- Apply after schema_v7.sql. Keep coverage labels consistent with approved calculators.
BEGIN;
CREATE INDEX IF NOT EXISTS hdb_loading_bay_tariffs_identity_idx
    ON parking_data.hdb_loading_bay_tariffs (agency, carpark_id);

CREATE OR REPLACE VIEW parking_data.carpark_comparison_inputs
WITH (security_invoker = true) AS
SELECT c.agency, c.carpark_id, c.display_name, c.address,
       a.feed AS availability_feed, a.lots_available, a.total_lots,
       a.evidence_at, a.retrieved_at, a.timestamp_kind,
       a.quality_flags,
       CASE WHEN a.carpark_id IS NULL THEN 'missing'
            WHEN NOT a.is_fresh THEN 'stale'
            WHEN a.timestamp_kind = 'source_update' THEN 'fresh_source_update'
            ELSE 'recent_retrieval_only' END AS availability_status,
       h.parking_system, h.short_term_parking, h.free_parking,
       h.night_parking, h.central_area, h.peak_profile,
       h.sunday_ph_free_from, h.reference_flags_recognized,
       h.reference_retrieved_at, h.policy_version,
       s.schedule_id AS verified_schedule_id,
       CASE WHEN lb.carpark_id IS NOT NULL THEN 'loading_bay_not_general_parking'
            WHEN c.agency = 'HDB' AND h.carpark_id IS NULL
                  THEN 'hdb_reference_missing'
            WHEN c.agency = 'HDB' AND h.short_term_parking = 'NO'
                  THEN 'no_short_term_parking'
            WHEN c.agency = 'HDB' AND NOT h.reference_flags_recognized
                  THEN 'hdb_reference_requires_review'
            WHEN s.schedule_id IS NOT NULL THEN 'verified_schedule_candidate'
            WHEN c.agency = 'HDB' AND h.peak_profile <> 'none'
                  THEN 'hdb_peak_tariff_unreviewed'
            WHEN c.agency = 'HDB' THEN 'hdb_daytime_candidate'
            WHEN c.agency = 'URA' AND EXISTS
                (SELECT 1 FROM parking_data.ura_rate_rows ur
                 WHERE ur.pp_code = c.carpark_id AND ur.vehicle_category = 'Car')
                THEN 'ura_requires_rate_review'
            ELSE 'no_verified_tariff' END AS pricing_evidence_status
FROM parking_data.carpark_identities c
LEFT JOIN parking_data.hdb_loading_bay_tariffs lb
  ON c.agency = lb.agency AND c.carpark_id = lb.carpark_id
LEFT JOIN parking_data.car_latest_availability a
  ON a.agency = c.agency AND a.carpark_id = c.carpark_id
LEFT JOIN parking_data.hdb_tariff_classification h
  ON c.agency = 'HDB' AND h.carpark_id = c.carpark_id
LEFT JOIN LATERAL (
    SELECT rs.schedule_id
    FROM parking_data.rate_schedules rs
    WHERE rs.agency = c.agency AND rs.carpark_id = c.carpark_id
      AND rs.review_status = 'verified' AND rs.calculator_key IS NOT NULL
      AND rs.valid_from <= now()
      AND (rs.valid_until IS NULL OR rs.valid_until > now())
      AND EXISTS (SELECT 1 FROM parking_data.rate_schedule_rules rr
                  WHERE rr.schedule_id = rs.schedule_id)
    ORDER BY rs.valid_from DESC LIMIT 1
) s ON true;

REVOKE ALL ON parking_data.carpark_comparison_inputs FROM PUBLIC, anon, authenticated;
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
            WHEN e.source_kind = 'unresolved' THEN 'rate_source_missing_or_identity_ambiguous'
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


REVOKE ALL ON parking_data.carpark_pricing_coverage FROM PUBLIC, anon, authenticated;
COMMIT;
