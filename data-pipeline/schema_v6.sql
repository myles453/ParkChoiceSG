-- Apply after schema_v5.sql. Capacity is separate from feed selection.
-- An LTA fallback must not hide the last HDB source-published capacity.
BEGIN;
CREATE OR REPLACE VIEW parking_data.carpark_candidate_inputs WITH (security_invoker=true) AS
SELECT i.*,loc.location_points,loc.latitude,loc.longitude,
       loc.source AS location_source,loc.captured_at AS location_captured_at,
       CASE WHEN loc.carpark_id IS NULL THEN 'missing_or_invalid'
            WHEN loc.captured_at < now()-interval '30 days' THEN 'stale'
            ELSE loc.location_status END AS location_status,
       loc.quality_flags AS metadata_quality_flags,
       coalesce(i.total_lots,hcap.total_lots,cap.car_capacity) AS capacity_evidence,
       CASE WHEN i.total_lots IS NOT NULL THEN 'availability_snapshot'
            WHEN hcap.total_lots IS NOT NULL THEN 'hdb_previous_snapshot'
            WHEN cap.car_capacity IS NOT NULL THEN 'ura_details' ELSE 'unknown' END AS capacity_source,
       CASE WHEN i.total_lots IS NOT NULL THEN i.evidence_at
            WHEN hcap.total_lots IS NOT NULL THEN hcap.source_updated_at ELSE cap.captured_at END AS capacity_evidence_at,
       CASE WHEN coalesce(i.total_lots,hcap.total_lots,cap.car_capacity) IS NULL THEN 'unknown'
            WHEN i.lots_available > coalesce(i.total_lots,hcap.total_lots,cap.car_capacity) THEN 'available_exceeds_capacity'
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
    SELECT a.total_lots,a.source_updated_at FROM parking_data.availability_observations a
    WHERE i.agency='HDB' AND a.source='hdb' AND a.carpark_id=i.carpark_id AND a.lot_type='C'
      AND a.total_lots>0 AND a.live_run_id IS NOT NULL
      AND a.source_updated_at BETWEEN now()-interval '30 days' AND now()
      AND NOT EXISTS (SELECT 1 FROM parking_data.hdb_observation_conflicts x
          WHERE (x.source,x.carpark_id,x.lot_type,x.source_updated_at)=
                (a.source,a.carpark_id,a.lot_type,a.source_updated_at))
    ORDER BY a.source_updated_at DESC LIMIT 1
) hcap ON true
LEFT JOIN LATERAL (
    SELECT m.* FROM parking_data.carpark_latest_metadata m
    WHERE m.agency=i.agency AND m.carpark_id=i.carpark_id AND m.source='ura_details'
      AND m.capacity_status='published_metadata'
      AND m.captured_at BETWEEN now()-interval '30 days' AND now()+interval '2 minutes'
    LIMIT 1
) cap ON true
LEFT JOIN parking_data.carpark_latest_metadata facilities
    ON facilities.agency=i.agency AND facilities.carpark_id=i.carpark_id AND facilities.source='hdb_reference';

REVOKE ALL ON parking_data.carpark_candidate_inputs FROM PUBLIC,anon,authenticated;
COMMIT;
