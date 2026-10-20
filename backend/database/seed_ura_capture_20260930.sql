-- Both locally archived payloads passed manifest checksum validation and their
-- complete Result arrays compared equal before this import was prepared.
-- Preserve a separate capture/version with the real new retrieval timestamp.
BEGIN;
DO $$ BEGIN
 IF (SELECT count(*) FROM parking_data.ura_rate_rows
     WHERE run_id='dfacf511-32da-4b11-8210-095d71b46b49')<>3960 THEN
   RAISE EXCEPTION 'Expected complete previous URA capture (3960 rows)';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM parking_data.ingestion_runs
     WHERE run_id='2291635e-3d69-4d4b-aa50-6a233535e45b') THEN
   RAISE EXCEPTION 'Latest URA capture ingestion run is missing';
 END IF;
END $$;
INSERT INTO parking_data.ura_rate_rows
 (run_id,row_number,pp_code,pp_name,vehicle_category,parking_system,park_capacity,
  start_time,end_time,parse_flags,raw)
SELECT '2291635e-3d69-4d4b-aa50-6a233535e45b',row_number,pp_code,pp_name,vehicle_category,
 parking_system,park_capacity,start_time,end_time,parse_flags,raw
FROM parking_data.ura_rate_rows WHERE run_id='dfacf511-32da-4b11-8210-095d71b46b49'
ON CONFLICT DO NOTHING;
INSERT INTO parking_data.ura_rate_day_rules
 (run_id,row_number,day_type,amount_cents,unit_minutes,interpretation)
SELECT '2291635e-3d69-4d4b-aa50-6a233535e45b',row_number,day_type,amount_cents,unit_minutes,interpretation
FROM parking_data.ura_rate_day_rules WHERE run_id='dfacf511-32da-4b11-8210-095d71b46b49'
ON CONFLICT DO NOTHING;
COMMIT;
