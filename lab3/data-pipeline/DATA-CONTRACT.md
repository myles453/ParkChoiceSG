# Lab 3 parking data contract

The database separates **identity**, **availability evidence**, and **pricing evidence**. A shared carpark code is only a match within the same agency. An LTA record whose agency is URA is another observation of a URA carpark, not another carpark or extra parking capacity.

Apply `schema.sql`, then `schema_v2.sql` through `schema_v8.sql` in numerical order. All eight are applied to the team Supabase project. The schema is private; the app must access it through a backend with narrowly scoped credentials, not a client-side Supabase key.

| Object | Purpose |
|---|---|
| `carpark_identities` | One canonical `(agency, carpark_id)` and the best available display name. HDB reference addresses and LTA development names are retained with provenance. |
| `source_carpark_codes` | Audited mapping from `(feed, source_agency, source_code)` to the canonical identity. Initial links require exact agency and code; no fuzzy name merge. |
| `availability_observations` | HDB rows with source-provided update time and total capacity. Historical backfill stays distinct from live collection. |
| `provider_availability_snapshots` | LTA and direct URA readings, retaining both feed and agency. These feeds do not supply per-carpark source update time or reliable total capacity. |
| `car_availability_evidence` | Car-lot (`C`) readings in a common shape. `timestamp_kind` identifies source update versus retrieval time. Historical HDB queries are excluded. |
| `car_latest_availability` | One preferred reading per canonical carpark. A fresh HDB direct reading outranks LTA's HDB copy; direct URA outranks LTA's URA copy. Freshness is 15 minutes, with a 2-minute future-clock allowance. `is_fresh=false` must not be presented as live availability. A fresh retrieval timestamp from LTA/URA does **not** prove the provider's underlying reading is fresh. |
| `hdb_parking_policy_flags` | HDB reference flags such as short-term, free and night parking, still in the source's original vocabulary. These flags are not a tariff. |
| `ura_rate_rows` | All verified-archive URA detail rows, with original JSON, vehicle category, time window and parse flags. |
| `ura_rate_day_rules` | Three day-specific interpretations per URA row, with exact cents and duration fields. `per_unit` means syntax parsed, **not** price approved. Zero/zero, long-period and missing rules stay explicitly flagged. |
| `rate_schedules` and `rate_schedule_rules` | Versioned tariffs with review state, calculator configuration, day/time bands, billing, grace, tiers, caps and source links. Current approved calculators cover 2,122 HDB, 657 partial URA and 12 partial operator schedules. A verified schedule may still contain blocked windows. |
| `ura_rate_draft_audit` | Counts copied, ambiguous and missing URA entries per draft, so review cannot overlook an overnight or free-period row. |
| `hdb_tariff_policy_rules` | Ten typed rates and caps from HDB's published short-term parking policy. These are policy facts, not computed per-carpark prices. |
| `hdb_tariff_exceptions` and `hdb_peak_windows` | The 26 HDB carparks named in the official central-area or peak-charge lists, plus the published peak time windows. |
| `hdb_tariff_classification` | Combines those official exceptions with HDB reference flags for payment system, short-term hours, night parking and Sunday/public-holiday free parking. All 2,272 current reference rows use recognized flag values. |
| `sg_public_holidays` and `sg_holiday_year_coverage` | MOM's 2026 dates are loaded: 11 gazetted holidays and three observed Mondays, kept as distinct kinds. Other years are not covered. Parking treatment of observed Mondays still needs provider confirmation. |
| `carpark_comparison_readiness` | Shows availability and pricing evidence status by carpark. `comparison_ready` is a coarse legacy indicator combining retrieval freshness and a schedule, not request-specific eligibility or confirmed source freshness. A request-specific quote must also check arrival date and full parking duration. |
| `carpark_comparison_inputs` | One row per canonical carpark with the preferred car-lot reading, its timestamp kind and freshness status, HDB policy classification, and verified-rate indicator. It is an input to the request-specific quote calculator, not a price or recommendation by itself. |
| `carpark_metadata_evidence` | Versioned car metadata with source/capture time, WGS84 location points converted from SVY21 where needed, location quality, URA published capacity, HDB facility type and gantry height. Repeated URA tariff rows never add to capacity. Conflicting fields are withheld. |
| `carpark_latest_metadata` | Latest capture per agency, code and metadata source. A newer invalid field does not silently revert to an older valid value from that source. |
| `carpark_candidate_inputs` | Extends comparison inputs with location, independent capacity evidence and capacity mismatch flags. HDB capacity remains available even when the selected availability feed is LTA. A historical or URA metadata capacity is evidence, not a synchronized occupancy denominator. |
| `hdb_observation_conflicts` | Quarantines different counts reported for an already-stored HDB source instant. The conflicting instant is excluded from the new model and live-evidence views. |
| `model_car_observations` | Prospective car-lot series: HDB direct source-time observations, URA direct retrieval snapshots, and LTA-feed LTA-agency snapshots. Excludes LTA copies of HDB/URA and historical-only HDB queries. `known_at` records when input evidence first became available to the collector. |

`comparison.py` now loads approved schedules and delegates to `pricing.quote_schedule`. It returns exact SGD cents, payment assumption, source, schedule ID and a breakdown for a supplied aware, minute-precision arrival and positive whole-minute stay. Supported HDB cases include central/peak changes, Sunday/gazetted-holiday free boundaries, night and eligible parking-day caps. Partial URA and operator tariffs support reviewed windows, tiers and caps. See [PRICING-READINESS-2026-09-30.md](PRICING-READINESS-2026-09-30.md) for measured coverage, examples, source evidence and remaining guards.

From 2 October, normal `collect_live.py` runs refresh URA tariff storage daily. `refresh_pricing.py` checks the archived payload checksum, imports source rows, compiles supported Car windows, and supersedes the prior URA capture atomically with that provider's availability load. Missing/zero/ambiguous windows block a quote, never imply free parking. A standard night cap requires a matching per-unit night window. Replaying the same runtime capture is idempotent; an older unseen capture cannot replace newer tariffs. Daily automatic validation applies to known API semantics, not to previously unknown rules or general policy changes. HDB policy and commercial operator evidence retain their separate review-expiry checks.

`tariff_source_evidence` stores guide/operator/API facts separately from quote approval. `hdb_loading_bay_tariffs` preserves 12 special loading-bay tariffs while excluding those bays from ordinary parking recommendations. `carpark_pricing_coverage` distinguishes approved calculators, reviewable facts, guide-only evidence, missing sources and parking exclusions; it never returns a request price.

The calculator supports near-term arrivals within 24 hours and stays up to 24 hours, checks tariff validity across the whole stay, and refuses stale review/source/reference captures. HDB/operator review and HDB reference age are limited to 30 days; URA review and source capture age to two days. Only the 2026 calendar is loaded. Observed holidays, fractional-cent rounding, some peak PH interpretations, paper-coupon boundaries/caps, ambiguous URA windows and operator band crossings remain guarded. IMM needs the vehicle's first-entry status. Unknown rules are never interpreted as zero price or free parking. The older daytime-only `quote_hdb` helper is retained for compatibility and is not the production comparison calculator.

Example from a trusted backend with a private `DATABASE_URL`; replace the arrival with a near-term time when running later:

```powershell
python comparison.py --arrival "2026-10-01T10:00:00+08:00" --duration-minutes 60 --first-entry unknown --show-unready --limit 20
```

`price_comparison_eligible` still requires positive availability, a fresh source-update timestamp, a quoted supported stay, a single usable location and no available-count/capacity mismatch. A recent LTA/URA retrieval alone does not prove source freshness. `recommendation_eligible` stays false until arrival prediction and candidate-specific driving/walking routes are integrated. Stored observations are stale until the next live collection. Cross-agency pricing coverage remains partial; show explicit unavailable-price reasons where allowed by the product use case.

Useful read-only checks:

```sql
SELECT agency, carpark_id, display_name, availability_feed, lots_available,
       evidence_at, timestamp_kind, availability_fresh, pricing_status
FROM parking_data.carpark_comparison_readiness
WHERE agency = 'URA' AND carpark_id = 'S0049';

SELECT r.pp_code, r.vehicle_category, r.start_time, r.end_time,
       d.day_type, d.amount_cents, d.unit_minutes, d.interpretation
FROM parking_data.ura_rate_rows r
JOIN parking_data.ura_rate_day_rules d USING (run_id, row_number)
WHERE r.pp_code = 'S0049' AND r.vehicle_category = 'Car'
ORDER BY r.row_number, d.day_type;

SELECT feed, agency, count(*)
FROM parking_data.provider_availability_snapshots
GROUP BY feed, agency ORDER BY feed, agency;

SELECT * FROM parking_data.ura_rate_draft_audit
WHERE carpark_id = 'S0049';

SELECT * FROM parking_data.hdb_tariff_classification
WHERE carpark_id = 'ACB';
```

For a new URA run, archive with `python provider_puller.py --provider ura --include-rates`, then verify and prepare its rate import with `python import_ura_rates.py <run-directory> <empty-output-directory>`. The output SQL is for the private schema and must be run in filename order: identities, numbered rate batches, then `20-drafts.sql`. The parser never requests, stores or prints the daily URA token. Re-running the SQL for the same run ID is idempotent.

Use `model_car_observations` with `export_training.py` for the current prediction workflow. The older `training_car_observations` is a legacy HDB staging view, including historical queries; it is not a prospective validation export. LTA/URA retrieval time is not an observed source update time, and overlapping feeds must not be counted as independent ground truth.

## Prediction export and request-specific inputs

`export_training.py` defaults to HDB only. Opt in with `--include-retrieval-series` for URA direct and LTA-agency series. Each stays a separate series with `label_kind=retrieval_proxy`; do not report the proxy as confirmed source freshness or pool identical codes from different agencies.

Features include latest available count, synchronized HDB capacity/free ratio where present, actual observation age, 5/15-minute lags with timestamps, samples in the last hour, prediction horizon, and Singapore arrival weekday/15-minute slot/weekend flag. `decision_at` is the actual collection time, not an earlier source update time. Only inputs already known by that decision enter a feature row. Labels use the first later reading at or after the target arrival, within a declared tolerance (default five minutes). Long gaps produce no label. Clock-ahead source readings are excluded. No interpolation or zero filling is performed. `--split-at` creates a chronological split and purges training targets that cross it. The manifest does not claim training readiness based on row count alone.

The provider dataset cannot supply every scoring input. These must be produced per request:

| Field | Producer and rule |
|---|---|
| Driver origin, resolved destination, departure time, stay duration | App/backend request. Stay duration is necessary for cost; handle Singapore time explicitly. |
| Driving seconds and arrival instant **at each candidate carpark** | Routing adapter. `arrival_at = departure_at + driving_seconds`. Destination ETA alone is not the ETA at every carpark. Retain route request time/status. |
| Walking distance/time from carpark to destination | Walking-route adapter. Do not call straight-line distance a walking route. |
| Estimated cost in SGD cents | Reviewed cost engine over the full stay starting at that candidate's arrival time; return payment assumption and quote status. |
| Predicted available lots at arrival | Teammate's model, with model version, forecast issue/target times, history cutoff, sample count and calibrated confidence. Never invent confidence from collection freshness. |
| Ranking and explanation | Backend using agreed weights, normalization, missing-factor policy and deterministic tie-breaks. Keep raw factors and excluded-candidate reasons. |

Retain all URA geometry points. A single published point is a carpark location, not proof of an entrance. Multiple points require a deliberate route-point choice; their mean or first element is not automatically an entrance. `B0098` currently has no usable location and no matching Car tariff. LTA-agency capacity is not published in its feed and remains NULL. Three current URA records have availability greater than detail capacity; use counts without a metadata-based occupancy ratio until the discrepancy is resolved.

Sources: [URA API reference](https://eservice.ura.gov.sg/maps/api/), [HDB short-term parking charges](https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges), [HDB electronic parking](https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/electronic-parking).
