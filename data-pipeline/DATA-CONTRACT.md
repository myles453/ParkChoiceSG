# Collection and training data contract

## Identity and timestamps

A carpark is **`(agency, carpark_id)`**. Retain `feed` separately. An LTA record tagged HDB/URA is another observation of that agency's carpark, not extra capacity. Only car lot type `C` enters the car model; staging retains other valid vehicle types.

HDB supplies source-update time and capacity. Its timezone-less timestamps are interpreted as Singapore time and stored as aware instants. Repeated collection of an unchanged source instant is not another independent sample.

LTA/URA availability supplies no per-carpark source-update time or synchronized capacity. Their observation time is a **retrieval proxy**, and capacity remains NULL. Retrieval time proves when a value was received, not when it was measured.

`known_at` records when this collector knew an observation. Features must respect that cutoff. Convert to `Asia/Singapore` for weekday/time-of-day features. Historical-only HDB queries are excluded from the prospective model view; later live provenance is retained without moving knowledge into the past.

The live freshness policy is 15 minutes, with a two-minute future-clock allowance. These are project settings, not provider guarantees. The stricter causal exporter excludes observations whose source clocks are ahead of collection time.

## Cleaning and gaps

| Case | Behaviour |
|---|---|
| Zero available with positive capacity | Valid full-carpark reading. |
| Missing/noninteger/negative counts | Reject rather than guess. |
| HDB availability exceeds its synchronized capacity | Reject/quarantine; never clamp. |
| Stale HDB data, zero capacity, unmatched reference | Preserve audit flags where applicable; exclude from strict training. |
| Identical HDB source/code/lot/time duplicate | Deduplicate. |
| Different counts for the same HDB source instant | Quarantine in `hdb_observation_conflicts`; exclude that instant from model/live views. |
| Missing reading/carpark | Preserve the gap; never replace with zero or assume closure. |
| URA availability exceeds details capacity | Flag mismatch; do not use that metadata denominator for occupancy. |
| Unknown capacity | NULL; do not invent a factual capacity. |

Raw responses and checksums are preserved before cleaning. Each provider's load commits atomically; other providers may succeed independently in the periodic runner.

## Metadata and model series

Convert SVY21 EPSG:3414 to WGS84 with explicit axes and Singapore-bound checks. Preserve all URA points; a point/centroid is not automatically a verified entrance. Repeated URA tariff rows do not add to capacity. Current metadata must not become a historical feature unless it was known at that decision time.

Use `parking_data.model_car_observations`: HDB direct source-time rows, URA direct retrieval snapshots, and LTA-feed LTA-agency snapshots. LTA copies of HDB/URA are excluded. HDB is the default export; other sources require `--include-retrieval-series` and retain `retrieval_proxy` labels.

Features contain only evidence known by `decision_at`. Labels use the first reading at or after target arrival within the configured tolerance, default five minutes. Longer gaps yield no pair. There is no interpolation. `--split-at` creates a chronological train/validation split and purges targets crossing it; the model owner must define the later test period and other readiness criteria.

## Pricing boundary

The existing database stores HDB policy, operator evidence and versioned rates separately from availability. `collect_live.py` refreshes URA details daily. Known per-unit windows and corroborated night caps can be compiled; unknown/zero/ambiguous windows block affected prices rather than imply free parking. Old schedules are preserved. Availability collection does not renew HDB/operator policy reviews.

This package contains collection/export tooling. Cost calculation and final scoring are separate backend work. Each candidate needs its own driving ETA, parking duration, walking route and a validated availability forecast/confidence. Missing evidence must remain explicit.
