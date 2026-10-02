-- HDB policy reviewed in the official rendered page on 30 September 2026.
-- Captured versions are immutable. Quotes still validate request-specific guards.
BEGIN;
INSERT INTO parking_data.rate_schedules
 (agency,carpark_id,source,source_url,valid_from,billing_method,grace_minutes,
  review_status,reviewed_by,reviewed_at,review_note,seed_key,calculator_key,
  calculator_config,coverage_scope)
SELECT 'HDB',h.carpark_id,'hdb_policy',
 'https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges',
 timestamptz '2026-09-30 13:27:00+00','rule_specific',
 CASE WHEN h.parking_system='ELECTRONIC PARKING' THEN 15 ELSE 0 END,
 'verified','ParkChoiceSG source review',timestamptz '2026-09-30 13:27:00+00',
 'General motor-car tariff, HDB reference flags and listed central/peak exceptions. Caps excluded for peak carparks. Observed holidays, ambiguous peak PH treatment and fractional-cent billing remain guarded. Restricted-purpose loading bays excluded.',
 'hdb-20260930-'||h.carpark_id,'window_rules_v1',
 jsonb_build_object('agency','HDB','parking_system',h.parking_system,
   'reference_flags',jsonb_build_object('parking_system',h.parking_system,
      'short_term_parking',h.short_term_parking,'free_parking',h.free_parking,'night_parking',h.night_parking),
   'reference_retrieved_at',h.reference_retrieved_at,'peak_profile',h.peak_profile,
   'ph_peak_unconfirmed',h.peak_profile IN ('acb_cy','se_mon_sat','hougang_weekend'),
   'paper_day_cap_unconfirmed',true,'overnight_anchor_day',true),
 'published_windows'
FROM parking_data.hdb_tariff_classification h
WHERE h.reference_flags_recognized AND h.short_term_parking<>'NO'
 AND NOT EXISTS (SELECT 1 FROM parking_data.hdb_loading_bay_tariffs lb WHERE lb.carpark_id=h.carpark_id)
ON CONFLICT DO NOTHING;

-- One non-overlapping base rate per applicable day/time window. Higher priority
-- central/peak/free rules explicitly replace it; caps are separate constraints.
INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,d.day_type,time '07:00',
 CASE WHEN h.short_term_parking='7AM-7PM' THEN time '19:00' ELSE time '22:30' END,
 'per_unit',60,30,'Standard daytime motor-car rate',100,'base-'||d.day_type,'verified','{}'
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
CROSS JOIN (VALUES ('weekday'),('saturday'),('sunday'),('public_holiday')) d(day_type)
WHERE s.seed_key='hdb-20260930-'||h.carpark_id
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,d.day_type,time '07:00',time '17:00','per_unit',120,30,
 'Central Area Monday-Saturday daytime rate',120,'central-'||d.day_type,'verified','{}'
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
CROSS JOIN (VALUES ('weekday'),('saturday')) d(day_type)
WHERE s.seed_key='hdb-20260930-'||h.carpark_id AND h.central_area
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,w.day_type,w.start_time,w.end_time,'per_unit',
 80,30,
 'Peak-period rate (caps do not apply)',200,'peak-'||w.day_type,'verified','{}'
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
JOIN parking_data.hdb_peak_windows w ON w.policy_version=h.policy_version AND w.peak_profile=h.peak_profile
WHERE s.seed_key='hdb-20260930-'||h.carpark_id
ON CONFLICT DO NOTHING;

-- Central peak price changes at 17:00 as the ordinary Central Area price does.
INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,w.day_type,w.start_time,least(w.end_time,time '17:00'),'per_unit',140,30,
 'Central Area Monday-Saturday peak daytime rate',220,'central-peak-'||w.day_type,'verified','{}'
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
JOIN parking_data.hdb_peak_windows w ON w.policy_version=h.policy_version AND w.peak_profile=h.peak_profile
WHERE s.seed_key='hdb-20260930-'||h.carpark_id AND h.central_area
 AND w.day_type IN ('weekday','saturday') AND w.start_time<time '17:00'
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,d.day_type,h.sunday_ph_free_from,
 CASE WHEN h.short_term_parking='7AM-7PM' THEN time '19:00' ELSE time '22:30' END,'free',0,NULL,
 'Published Sunday/PH free parking in general car lots',300,'free-'||d.day_type,'verified','{}'
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
CROSS JOIN (VALUES ('sunday'),('public_holiday')) d(day_type)
WHERE s.seed_key='hdb-20260930-'||h.carpark_id AND h.sunday_ph_free_from IS NOT NULL
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,d.day_type,time '22:30',time '07:00','per_unit',60,30,
 'Night Parking Scheme half-hour rate',100,'night-'||d.day_type,'verified','{}'
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
CROSS JOIN (VALUES ('weekday'),('saturday'),('sunday'),('public_holiday')) d(day_type)
WHERE s.seed_key='hdb-20260930-'||h.carpark_id AND h.night_parking='YES'
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,d.day_type,time '22:30',time '07:00','cap',500,NULL,
 'Night cap, only for non-peak carparks with NPS',100,'night-cap-'||d.day_type,'verified',
 '{"cap_group":"night"}'::jsonb
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
CROSS JOIN (VALUES ('weekday'),('saturday'),('sunday'),('public_holiday')) d(day_type)
WHERE s.seed_key='hdb-20260930-'||h.carpark_id AND h.night_parking='YES' AND h.peak_profile='none'
ON CONFLICT DO NOTHING;

INSERT INTO parking_data.rate_schedule_rules
 (schedule_id,day_type,start_time,end_time,rule_kind,amount_cents,unit_minutes,
  description,priority,rule_key,review_status,calculation)
SELECT s.schedule_id,d.day_type,time '07:00',
 CASE WHEN h.night_parking='YES' THEN time '07:00' ELSE time '22:30' END,
 'cap',CASE WHEN h.central_area THEN 2000 ELSE 1200 END,NULL,
 '07:00 parking-day cap (not a rolling 24-hour cap)',100,'day-cap-'||d.day_type,'verified',
 jsonb_build_object('cap_group','parking_day','full_day',h.night_parking='YES',
   'payment_methods',jsonb_build_array('eps','parking_sg'))
FROM parking_data.rate_schedules s
JOIN parking_data.hdb_tariff_classification h ON s.agency='HDB' AND s.carpark_id=h.carpark_id
CROSS JOIN (VALUES ('weekday'),('saturday'),('sunday'),('public_holiday')) d(day_type)
WHERE s.seed_key='hdb-20260930-'||h.carpark_id AND h.peak_profile='none'
ON CONFLICT DO NOTHING;
COMMIT;
