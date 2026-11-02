# Existing database: schema, tables and rows

Supabase hosts the team's PostgreSQL database. All collection tables/views live in the private **`parking_data`** schema. It already exists and is populated; the teammate needs collection credentials, not a new database or SQL setup. This repository cleanup does not change the live database.

The 19 tables have row-level security enabled, and the frontend `anon`/`authenticated` roles have no table SELECT access. Use trusted ingestion credentials for collection and a separately provided read-only credential for training. Do not put privileged credentials in the app.

## Table inventory

Counts below were read from the live database on **2 October 2026**. They are a snapshot and increase/change with collection. They include staging records, other vehicle types and historical versions; they are not a count of independent carparks, total parking lots or usable training pairs.

| Table | Rows at this check | What one row means |
|---|---:|---|
| `ingestion_runs` | 17 | One capture/import run, with UUID, capture/query time and manifest. |
| `carparks` | 2,272 | One HDB reference carpark with address, original policy/geometry JSON and reference capture time. |
| `carpark_identities` | 3,081 | One canonical `(agency, carpark_id)` with display-name/address provenance; not every identity has live car availability. |
| `source_carpark_codes` | 5,165 | One source-feed/code mapping to a canonical identity. Multiple feed mappings are not extra carparks. |
| `availability_observations` | 14,462 | One HDB source/code/lot-type/source-time observation, with availability, synchronized capacity, quality and live/historical provenance. |
| `provider_availability_snapshots` | 13,954 | One LTA/URA availability entry in a capture, retaining feed, agency, lot type, retrieval time and source attributes. |
| `hdb_observation_conflicts` | 0 | Conflicting counts for an already-stored HDB source instant. These instants are excluded from model/live views. |
| `carpark_metadata_evidence` | 19,999 | One versioned metadata record per capture/source/identity: geometry, capacity/facility evidence and quality. |
| `ura_rate_rows` | 15,840 | One raw URA detail/tariff row from a capture. A carpark may have several rows for vehicle types/time bands. |
| `ura_rate_day_rules` | 47,520 | One weekday/Saturday/Sunday-PH rate interpretation for a raw URA row. Parsing alone is not calculator approval. |
| `rate_schedules` | 4,766 | One version of a carpark tariff schedule, including superseded and pending versions. |
| `rate_schedule_rules` | 57,526 | One time/day rule belonging to a schedule: fee, free window, tier/cap or explicit unresolved-window block. |
| `tariff_source_evidence` | 2,689 | Captured pricing facts/source provenance; evidence approval is separate from whether a stay can be priced. |
| `hdb_tariff_policy_rules` | 10 | One reviewed HDB policy fact/rate/cap. |
| `hdb_tariff_exceptions` | 26 | One named HDB central/peak policy exception. |
| `hdb_peak_windows` | 16 | One day/time window for an HDB peak policy profile. |
| `hdb_loading_bay_tariffs` | 12 | One special loading-bay tariff; these bays are excluded from ordinary parking recommendations. |
| `sg_public_holidays` | 14 | One gazetted/observed holiday date; only the 2026 calendar is currently covered. |
| `sg_holiday_year_coverage` | 1 | One calendar year for which holiday coverage was loaded. |

## Important columns

### Canonical identity and captures

`carpark_identities.agency` and `carpark_id` are text and form the joint identity. `display_name`, `address` and `name_source` describe the best available reference data; `metadata_retrieved_at` records its provenance time.

`source_carpark_codes` retains `feed`, `source_agency`, `source_code`, canonical `agency`/`carpark_id` and `match_method`. The initial mapping uses exact agency/code matches, not fuzzy names.

`ingestion_runs.run_id` is UUID. `retrieved_at` and optional `query_time` are timezone-aware timestamps. `manifest` is JSONB containing capture counts, cleaner details and raw-response checksums/provenance. A historical query time is not the collector's knowledge time.

### HDB observations

| Column | Type | Meaning |
|---|---|---|
| `source`, `carpark_id`, `lot_type` | text | HDB identity and vehicle/lot category; car model uses `C`. |
| `source_updated_at` | timestamptz | Provider's observation/update time. |
| `first_retrieved_at` | timestamptz | First time this observation was retrieved, including historical requests. |
| `first_live_retrieved_at`, `live_run_id` | timestamptz, UUID | First live-capture provenance when available. |
| `lots_available`, `total_lots` | integer | Available lots and capacity from the same HDB observation. |
| `quality_flags`, `training_eligible` | text array, boolean | Cleaning decisions; the model view applies additional conflict/live filters. |
| `run_id` | UUID | Original run audit link. |

The same source/code/lot-type/source-time key is deduplicated. Conflicting counts are quarantined rather than silently replacing the value.

### LTA/URA snapshots and metadata

`provider_availability_snapshots` contains `run_id` (UUID), `feed`, `agency`, `carpark_id`, `lot_type` (text), `retrieved_at` (timestamptz), `lots_available` (integer) and `attributes` (JSONB). These feeds do not provide per-carpark source-update time or synchronized capacity in their availability payload.

`carpark_metadata_evidence` contains capture/source/identity keys, `captured_at`, display/address fields, `source_crs`, `location_points` (JSONB), location status and latitude/longitude, `car_capacity`, capacity status, facility type, gantry height, quality flags and cleaner version. Source coordinates are preserved through provenance; normalized coordinates use WGS84. URA detail capacity is reference evidence and must not automatically become an occupancy denominator for a separate availability reading.

### Pricing storage

Schedules retain source/capture links, validity interval, review state, billing/grace information and calculator configuration. Rules retain time/day bands, integer SGD cents, unit minutes, rule kind, review state and source-row links. More schedule/rule rows usually mean more versions/windows, not more carparks.

The one-shot collector's daily URA refresh writes into these existing tables; the periodic training loop does not repeatedly fetch full URA tariff details. Missing/ambiguous tariff windows remain explicit. Price calculation, policy review and final ranking are outside this collection handover.

## Views the teammate should use

| View | Purpose |
|---|---|
| **`model_car_observations`** | Primary prospective car-training series; use this for export/training. |
| `car_latest_availability` | Preferred current car reading and freshness; not a training time series. |
| `carpark_latest_metadata` | Latest metadata by source/identity; not automatically historically valid features. |
| `carpark_candidate_inputs` | Canonical comparison inputs with availability, geometry, capacity provenance/consistency and pricing evidence. |
| `hdb_parking_policy_flags`, `hdb_tariff_classification` | HDB reference flags and reviewed exception classification. |
| `carpark_pricing_coverage` | Pricing evidence/calculator coverage, not a request-specific parking price. |

`model_car_observations` has these columns:

| Field | Meaning |
|---|---|
| `agency`, `carpark_id` | Joint identity. |
| `feed` | Primary series feed; LTA copies of HDB/URA are excluded. |
| `observed_at` | HDB source time or LTA/URA retrieval proxy. |
| `known_at` | When this collector knew the observation; controls feature availability. |
| `timestamp_kind` | `source_update` or `retrieval`. |
| `lots_available` | Available car-lot count. |
| `total_lots` | Synchronized HDB capacity where present; otherwise NULL. |
| `run_id` | Audit capture link. |

The older `training_car_observations` view is HDB staging that can include historical queries; use `model_car_observations` for this prospective workflow. The exporter additionally excludes source-clock observations ahead of knowledge time and requires valid future label matches. A view count is not the number of training pairs.

## Read-only checks

```sql
SELECT agency, feed, timestamp_kind, count(*) AS observations,
       count(DISTINCT carpark_id) AS carparks,
       min(known_at) AS first_capture, max(known_at) AS latest_capture
FROM parking_data.model_car_observations
GROUP BY agency, feed, timestamp_kind
ORDER BY agency, feed;

SELECT agency, carpark_id, observed_at, known_at,
       timestamp_kind, lots_available, total_lots
FROM parking_data.model_car_observations
ORDER BY known_at DESC
LIMIT 20;
```

Use the existing project's schema. Table/policy migrations and dated pricing seeds are intentionally not part of this operational collection folder; coordinate database maintenance separately rather than rerunning setup against populated data.
