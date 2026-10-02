# Data readiness — 30 September 2026

The live collectors worked for HDB, LTA and URA. Schemas v5/v6 and the cleaned records below were applied and verified in Supabase project `tskfbkuwplgrpwyxhudz`. This is a data readiness report, not a claim that arrival-time prediction or full price comparison is implemented.

## Captures loaded

| Source | Retrieval time (Singapore) | Accepted availability rows | Rejected rows | Run ID |
|---|---|---:|---:|---|
| HDB direct | 30 Sep 20:01:40 | 2,425 | 3 | `62d633ae-a115-4282-9c54-f97d05ab9f28` |
| LTA DataMall | 30 Sep 20:01:41 | 2,606 | 2 | `6c917c26-0f08-4949-a3ed-ce0562e3446f` |
| URA direct | 30 Sep 20:01:41 | 154 | 0 | `2291635e-3d69-4d4b-aa50-6a233535e45b` |

HDB's capture has 1,683 car-lot rows meeting its strict training flags, before the export's additional causal-clock check. Across all accepted lot types, 407 rows were flagged stale, 12 unmatched to reference metadata, and two zero-capacity (flags can overlap). Rejects include undocumented `S` lot types and one `Y` record whose available count exceeds its total. Preserve vehicle types; only `C` is used for this car model.

LTA contains 2,414 HDB-agency, 40 LTA-agency and 152 URA-agency records. Those agency counts are not three independent carpark inventories. URA contains 89 car-lot, 58 motorcycle and seven heavy-vehicle readings.

## Clean metadata and shared candidate inputs

The database has 3,081 canonical identities and 5,142 metadata evidence records. Counts refer to identities in all staging data; some have only motorcycle/heavy-vehicle references or no live car reading.

| Agency | Identities | Usable car-location sets | Capacity evidence | Availability > capacity |
|---|---:|---:|---:|---:|
| HDB | 2,284 | 2,272 | 2,003 | 0 |
| LTA | 40 | 40 | 0 | 0 |
| URA | 757 | 657 | 655 | 3 |

HDB capacity is from a timestamped car-lot availability snapshot; it remains separate evidence when LTA is selected as a fallback. URA capacity is from Car details and is not assumed synchronized with its current count. LTA publishes no capacity in this feed. Unknown values remain NULL.

- SVY21 coordinates are converted using EPSG:3414 → EPSG:4326, with explicit axis order and Singapore bounds. All 1,995 shared HDB positions and 88 shared URA positions agree with LTA to within one metre after rounding in this capture.
- URA has 22 carparks with multiple location points. All points are preserved; no centroid or first point is labelled an entrance.
- `B0098` lacks a usable direct location and matching Car tariff. `C0010` has no usable Car-details location. The 100 URA identities without a usable car-location set also include IDs represented only by other vehicle categories.
- URA `J0099`, `S0109`, `T0107` publish zero Car capacity; the usable capacity field is withheld.
- URA `M0088` (47 available / 28 detail capacity), `S0106` (59 / 34), `W0029` (64 / 58) are flagged. These could reflect differing lot populations; the cleaner does not claim their counts are necessarily false. Do not calculate occupancy from that denominator.

Use `parking_data.carpark_candidate_inputs` for backend comparison inputs. It retains agency, code, availability feed/count, source-versus-retrieval timestamp, quality/freshness, location points and provenance, capacity provenance/consistency, HDB policy flags/facilities, and pricing evidence status. A stale reading or unknown field does not become a default zero.

## Training handoff

The new `model_car_observations` view contains 3,445 HDB source-time rows across 1,873 codes, 80 LTA-agency retrieval rows across 40 codes, and 178 URA-direct retrieval rows across 89 codes. One HDB source instant is ahead of its recorded collection time and is excluded by the causal exporter. These are currently sparse pilot snapshots, not sufficient temporal coverage.

`export_training.py` emits 15/30/60-minute supervised pairs using only features known at the decision time and a later target reading within five minutes of arrival. It currently emits **zero pairs** from the verified local pilot archives: gaps are too large. Features cover current count, synchronized HDB capacity/free ratio, actual observation age, 5/15-minute lags, last-hour sample count, arrival weekday/15-minute slot/weekend flag, and horizon. LTA/URA require explicit opt-in and retain `retrieval_proxy` labels. Do not merge overlapping feeds, fill missing periods with zeroes, or use today's metadata as a past feature.

Next: collect regularly (a five-minute pilot interval can be evaluated against observed provider cadence), measure coverage/gaps, choose a chronological train/validation split with target purging, and agree model-owner minimum history/error/confidence criteria. No collection schedule is installed. Python automation still needs a private `DATABASE_URL`; MCP authentication enables interactive database work only.

## Pricing update and formulation still needed

Subsequent pricing work applied schemas v7/v8 and populated approved versioned calculators for 2,122 HDB, 657 partial URA and 12 operator carparks. The newer URA rate capture is now separately staged; older schedules are retained as superseded versions. Guide/operator evidence is stored for review. See [PRICING-READINESS-2026-09-30.md](PRICING-READINESS-2026-09-30.md) for current counts, supported cases and gaps. The availability/model figures in this report are unchanged; 70 tests now pass across the pipeline and calculator.

Driving/walking route measurements are not in these feeds. The backend needs origin/destination/departure, a driving ETA **to each candidate carpark**, walking route to destination, and stay duration. The model must return predicted count at that carpark ETA, model version/history cutoff/sample count and calibrated confidence. The team must settle scoring weights, normalization and missing-data policy. `comparison.py` reports `price_comparison_eligible`; it keeps arrival-time `recommendation_eligible=false` while model/routes are absent.

## Verification

- 47 local tests passed, including coordinate axes, geometry retention, duplicate capacity, checksum tampering, future-label leakage, late observations, gaps, clock-ahead readings, chronological split purging, and comparison readiness without an invented arrival forecast.
- All schema SQL and 128 prepared import batches parsed; all 46 merged cloud import batches succeeded and all three run imports were marked complete.
- A rolled-back PostgreSQL fixture confirmed historical-first HDB rows can later acquire live provenance and that cross-run conflicting source instants leave both model and live evidence views.
- `anon` and `authenticated` have no schema usage or table reads. All private tables have RLS enabled and views use invoker security. Supabase reports informational no-policy notices for this deliberate backend-only schema, plus two unused-index notices; no warning/error advisory was returned.
- The loaded 20:01 readings aged past the 15-minute window during verification. They remain labelled stale; this demonstrates why regular collection is required.

Provider field references: [URA API](https://eservice.ura.gov.sg/maps/api/), [HDB reference dataset](https://data.gov.sg/datasets/d_23f946fa557947f93a8043bbef41dd09/view), [LTA API guide](https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf).
