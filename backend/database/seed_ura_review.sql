-- Review captured URA motor-car windows using the API's documented units.
-- An approved schedule may be partial: zero/zero and missing data are NOT free.
BEGIN;
-- Retain older captures as history, rather than activating two current versions.
UPDATE parking_data.rate_schedules old
SET review_status='superseded',valid_until=newer.valid_from
FROM parking_data.rate_schedules newer
WHERE old.source='ura_details' AND newer.source='ura_details'
 AND old.carpark_id=newer.carpark_id AND old.agency=newer.agency
 AND old.valid_from<newer.valid_from AND old.valid_until IS NULL
 AND old.review_status IN ('pending_review','verified');
UPDATE parking_data.rate_schedules s
SET billing_method='rule_specific',
    grace_minutes=CASE WHEN x.system='B' THEN 15 ELSE 0 END,
    review_status='verified',reviewed_by='ParkChoiceSG source review',
    reviewed_at=timestamptz '2026-09-30 13:27:00+00',
    calculator_key='window_rules_v1',coverage_scope='partial',
    calculator_config=jsonb_build_object('agency','URA','parking_system',x.system,
      'day_cap_unconfirmed',true,'maximum_uncapped_day_cents',1200,
      'billing_source','https://www.police.gov.sg/-/media/SPF/Knowledge-Hub/Traffic/BT-ENG-24126.pdf',
      'payment_source','https://www.ura.gov.sg/car-parks/short-term-parking/parkingsg-mobile-application/'),
    review_note='Partial motor-car calculator. API per-unit windows only; EPS/Parking.sg per-minute billing. Missing/zero-zero windows block quotes. Standard paired $5/510-minute night rows are caps; other long-period rows remain unreviewed. No inferred day caps, parking permission or historical effective dates.'
FROM (
 SELECT run_id,pp_code,min(parking_system) AS system
 FROM parking_data.ura_rate_rows WHERE vehicle_category='Car'
 GROUP BY run_id,pp_code
 HAVING count(DISTINCT parking_system)=1 AND min(parking_system) IN ('B','C')
) x
WHERE s.source='ura_details' AND s.source_run_id=x.run_id AND s.carpark_id=x.pp_code
 AND s.review_status='pending_review' AND s.valid_until IS NULL
 AND EXISTS (SELECT 1 FROM parking_data.rate_schedule_rules rr WHERE rr.schedule_id=s.schedule_id);

UPDATE parking_data.rate_schedule_rules rr
SET review_status='verified',
    description='Reviewed URA per-unit window; see source row and schedule guards'
FROM parking_data.rate_schedules s
WHERE s.schedule_id=rr.schedule_id AND s.calculator_key='window_rules_v1'
 AND s.source='ura_details' AND rr.rule_kind='per_unit'
 AND rr.start_time<>rr.end_time;

-- 510 minutes exactly covers 22:30-07:00. The $5 night ceiling is independently
-- published by URA; require a matching 60c/30-minute row in the same capture.
INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,source_run_id,source_row_number,source_day_type,review_status,calculation)
SELECT s.schedule_id,d.day_type,r.start_time,r.end_time,'cap',500,NULL,
 'Standard $5 night cap, corroborated by URA coupon policy; no inferred day cap',
 d.run_id,d.row_number,d.day_type,'verified','{"cap_group":"night"}'::jsonb
FROM parking_data.ura_rate_rows r
JOIN parking_data.ura_rate_day_rules d USING(run_id,row_number)
JOIN parking_data.rate_schedules s ON s.source='ura_details' AND s.source_run_id=r.run_id AND s.carpark_id=r.pp_code
WHERE r.vehicle_category='Car' AND r.start_time=time '22:30' AND r.end_time=time '07:00'
 AND d.amount_cents=500 AND d.unit_minutes=510
 AND EXISTS (SELECT 1 FROM parking_data.rate_schedule_rules rr
   WHERE rr.schedule_id=s.schedule_id AND rr.day_type=d.day_type
    AND rr.start_time=r.start_time AND rr.end_time=r.end_time
    AND rr.rule_kind='per_unit' AND rr.amount_cents=60 AND rr.unit_minutes=30)
ON CONFLICT DO NOTHING;

-- Store other syntactically valid numeric rows without promoting their meaning.
-- Zero/zero, missing and unfamiliar long rows are separately carried in raw
-- staging and checked by the calculator's loaded block windows.
INSERT INTO parking_data.tariff_source_evidence
 (capture_key,agency,carpark_id,source_kind,source_url,captured_at,
  published_facts,review_status,review_note)
SELECT 'ura-'||r.run_id||'-'||r.pp_code,'URA',r.pp_code,'ura_api',
 'https://eservice.ura.gov.sg/maps/api/',ir.retrieved_at,
 jsonb_build_object('run_id',r.run_id,'vehicle_category','Car','raw_row_count',count(*)),
 'verified_facts','Numeric API facts retained; approved quote coverage is partial, not every time window.'
FROM parking_data.ura_rate_rows r JOIN parking_data.ingestion_runs ir USING(run_id)
WHERE r.vehicle_category='Car'
GROUP BY r.run_id,r.pp_code,ir.retrieved_at
ON CONFLICT DO NOTHING;
COMMIT;
