# Parking data ingestion pilot

Nestor's Lab 3 scope: collect and clean parking data and prepare PostgreSQL hosted by Supabase for model training. Voice assistance is deferred.

## Start here

**2 October update:** the private Session pooler connection is working. `collect_live.py` now imports URA prices automatically when its last compiled capture is over one day old. Availability, metadata and the refreshed URA tariff schedules load in one transaction for that provider. Older schedules are retained with an end time; unresolved windows block quotes. HDB policy and separately reviewed commercial-carpark prices are not supplied by the LTA availability API and are not automatically reapproved by this refresh.

See [PRICING-WORKFLOW-2026-10-02.md](PRICING-WORKFLOW-2026-10-02.md) for the successful live imports, measured quote coverage and remaining limits. HDB tariff flags are now checked against their original captured baseline before quoting.

Normal database workflow, from this directory:

```powershell
.\.venv\Scripts\python.exe collect_live.py
.\.venv\Scripts\python.exe check_comparison_readiness.py --arrival-in-minutes 30 --duration-minutes 60
```

`--include-rates` forces a fresh URA tariff capture; `--availability-only` explicitly skips it. Archive-only collection includes URA details by default. The readiness check is read-only and reports actual quote failures as well as successful prices; it does not claim an arrival prediction or a final ranking.

For the model teammate's periodic availability collection, use:

```powershell
.\.venv\Scripts\python.exe collect_periodic.py
```

The default interval is **five minutes**. Change it using `--interval-minutes 10`, select providers with `--providers hdb`, or verify one cycle with `--cycles 1`. It runs until Ctrl+C, logs provider failures, and skips missed slots without overlapping cycles. Setup, required ingestion credentials and monitoring are in [PERIODIC-COLLECTION.md](PERIODIC-COLLECTION.md). This availability loop keeps the pricing refresh separate.

**30 September update:** schemas through `schema_v8.sql`, cleaned three-provider data, pricing storage and the request-specific calculator are applied and verified in Supabase. See [PRICING-READINESS-2026-09-30.md](PRICING-READINESS-2026-09-30.md) for current pricing coverage: 2,122 HDB, 657 partial URA and 12 partial operator calculators. See [DATA-READINESS-2026-09-30.md](DATA-READINESS-2026-09-30.md) for availability/model data. Numerical tables explicitly dated 28 September below are historical.

Use Python 3.12 for the tested environment. A local `.venv` has already been created in this directory. Install the pinned dependencies in `requirements.txt` when setting up elsewhere. From this directory:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest -q
.\.venv\Scripts\python.exe collect_live.py --archive-only --include-rates
.\.venv\Scripts\python.exe export_training.py --archives data --output data/training-arrival.csv
```

The collectors now write `metadata.json`/`metadata.csv` alongside raw archives and cleaned observations. `metadata_cleaner.py <run-directory>` can reprocess a verified archive. `prepare_import.py <run-directory> <new-output-directory>` creates numbered SQL batches for an MCP/SQL-editor import; apply every file in order and confirm `import_status=complete`. The direct `--load` route remains preferable for automated collection because each provider loads in one transaction. MCP login does not supply `DATABASE_URL` to Python.

`export_training.py` can read the private `model_car_observations` view using `DATABASE_URL`, or read checksum-verified local archives. Default HDB only; use `--include-retrieval-series` explicitly for the separate URA/LTA proxy series. Use `--horizons 15 30 60` and an aware `--split-at` to set horizons and a chronological validation boundary. The sparse pilot currently has **zero valid arrival-horizon pairs**. Do not train on rows created by filling those gaps.

Supabase hosts a PostgreSQL database. You do not need a separate PostgreSQL server for this setup. The Python collector is a separate program that retrieves and cleans data, then optionally writes it to that database.

The HDB pilot works locally without keys. Run from this directory:

```powershell
python -m unittest -v
python puller.py
python puller.py --at "2026-09-27T12:00:00+08:00"
```

Each run creates an ignored `data/<run-id>/` folder containing:

- Original responses compressed as `*.json.gz`, preserved before observation cleaning.
- `observations.csv`: accepted observations, including quality flags.
- `training-cars.csv`: only car (`C`) observations passing the pilot's quality rules.
- `rejected.json`: structurally invalid records and their reasons.
- `manifest.json`: actual retrieval time, historical query time, source checksums and counts.

One response is a snapshot, not a training time series. Concatenated files must be deduplicated by source, carpark ID, lot type and source update time. PostgreSQL enforces that key. Never count repeated retrieval of an unchanged source observation as independent samples.

## Carpark comparison

Apply all schema files through `schema_v8.sql`, then use `comparison.py` with an arrival time and duration. It returns location, capacity evidence, latest car-lot reading with timestamp provenance, and a price status. It uses versioned HDB, URA and operator schedules through `pricing.py`, including supported time-band changes, tiers, free windows and caps. Unconfirmed cases remain unpriced. `price_comparison_eligible` is a data-readiness indicator. Arrival-time `recommendation_eligible` remains false until prediction and route estimates are integrated. See [DATA-CONTRACT.md](DATA-CONTRACT.md) for the exact rules and limitations. Stored snapshots expire after 15 minutes and need ongoing collection.

```powershell
python comparison.py --arrival "2026-10-01T10:00:00+08:00" --duration-minutes 60 --show-unready --limit 20
```

The command reads `DATABASE_URL` from the process or ignored local `.env`. Keep it server-side. For the pilot it can use the same connection as the collector; provision separate least-privilege read and write roles before deploying. The Flutter app must call a backend that uses a private read connection; it cannot query `parking_data` directly.

To load one **live** availability cycle from all three sources, configure `DATABASE_URL` and the two provider keys in the trusted backend environment (or the ignored local `.env` file), then run `python collect_live.py`. It stops on the first failed source and leaves each collector's manifest for inspection. Use `collect_periodic.py` for continuous training-data collection with isolated provider failures. The HDB collector currently fetches its reference dataset every cycle; inspect durations/API errors and adjust the pilot interval as needed.

## LTA and URA collection

`provider_puller.py` handles the other two feeds. LTA requires an `LTA_ACCOUNT_KEY`; URA requires a `URA_ACCESS_KEY` and issues a daily token that the script requests automatically. The token response is never written to disk. Put issued keys in the local `.env` file beside the script (it is ignored by Git), using `LTA_ACCOUNT_KEY=your_key` and `URA_ACCESS_KEY=your_key`. Do not put spaces around `=`. Then run:

For `CarParkAvailabilityv2`, use the regular LTA **AccountKey** as the `AccountKey` header. The current LTA API guide does not mention an "SD Account Key" for this endpoint; keep that other key separate until its purpose is confirmed from its issuing instructions.

```powershell
python provider_puller.py --provider lta
python provider_puller.py --provider ura --include-rates
```

An existing process environment variable takes precedence over `.env`; open a new terminal or remove an old `$env:LTA_ACCOUNT_KEY` value before retesting with the file. First run without `--load` and inspect the output. The LTA collector uses the base endpoint for page one and `$skip=500` onward, matching the guide. Two earlier attempts using `$skip=0` on page one received HTTP 400; the corrected authenticated run succeeded. This supports the pagination fix, though no server-side error explanation was provided.

To load a successful run into Supabase, also set the server-side `DATABASE_URL` and add `--load`. Keep keys and the database URL out of Git and chat. The command archives raw availability responses, writes cleaned `observations.csv`, quarantines invalid rows in `rejected.json`, and records counts/checksums in `manifest.json`. `--include-rates` archives URA's full details/rates response. The separate `import_ura_rates.py` verifies that archive and prepares parsed rate rows and draft schedules for import; drafts are **not** yet approved for cost calculation. See [DATA-CONTRACT.md](DATA-CONTRACT.md).

The private `parking_data.provider_availability_snapshots` table is created in Supabase. It holds **2,606 LTA-feed and 154 direct URA rows** from one authenticated run of each provider. It stores retrieval time, available lots, feed and agency separately. Neither documented feed supplies the HDB-style per-carpark update timestamp or a trustworthy total lot count in its availability response; the cleaner leaves these unknown instead of inventing them. LTA's feed contains records attributed to HDB and URA as well as LTA, so `feed = lta_datamall` and `agency` must both be retained. Do not combine overlapping counts as independent observations. The existing `training_car_observations` view remains HDB-only until the model owner agrees on a cross-feed matching and timestamp policy.

The authenticated LTA run `a0d74132-e8bc-4339-bf82-3ee64bfbc23d` fetched six pages: 2,414 HDB-agency, 40 LTA-agency and 152 URA-agency rows. Of these, 1,995, 40 and 88 respectively are car (`C`) rows. Two HDB-agency records used undocumented lot type `S` and were quarantined. All six raw response checksums were verified before the 2,606 accepted rows were imported through the project-scoped Supabase MCP connection.

The authenticated direct URA run `dfacf511-32da-4b11-8210-095d71b46b49` used the AccessKey to request its daily Token automatically, then fetched availability and `Car_Park_Details`. Both raw response checksums were verified. All 154 availability rows were accepted and imported as `feed = ura_direct`; they cover 89 car (`C`), 58 motorcycle (`M`) and 7 heavy-vehicle (`H`) rows. The 3,960 details/rate rows and their 11,880 day-specific interpretations are staged in the private schema, with original JSON retained. Direct URA and LTA's URA-agency subset overlap: all 88 LTA URA car-lot IDs occurred in direct URA, which had one additional car-lot ID (`B0098`). This is a one-run coverage comparison, not a guarantee for future snapshots.

### Does LTA replace the direct HDB feed?

No for model training. Near-simultaneous local snapshots on 28 September (HDB retrieved at 11:59:07 UTC; LTA at 11:59:13 UTC) matched on exact HDB carpark ID and lot type. Direct HDB had 2,005 car-lot (`C`) rows; LTA's HDB-agency subset had 1,995. All 1,995 LTA rows matched direct HDB IDs. The ten direct-HDB-only car-lot IDs were `ACE`, `HE17`, `HG55`, `L7`, `L8`, `L9`, `NHC`, `TH5`, `TM57`, and `TWRM`. All ten also lacked HDB reference metadata and are excluded from the current strict training view. This establishes strong overlap for the currently referenced carparks in this sample, but not permanent full coverage.

Of the 1,995 shared car-lot IDs, 1,428 had the same available count and 567 differed by 1 to 12 lots. This is a comparison of two live requests roughly five seconds apart, not a synchronized ground-truth test; differences alone do not prove either feed wrong. The raw LTA records contain `Agency`, `Area`, `AvailableLots`, `CarParkID`, `Development`, `Location`, and `LotType` only. They have no per-carpark source update timestamp or total capacity, while the direct HDB response has both and supports historical query times. Keep direct HDB as the primary HDB prediction source; use LTA for its 40 LTA-agency car-lot records, its URA-agency coverage, and as a separate fallback/cross-check rather than double-counting its HDB subset.

### Parking pricing is a separate data stream

The LTA `CarParkAvailabilityv2` response has no rate field. The HDB availability response and HDB carpark reference dataset also have no numeric tariff field. Availability source selection therefore cannot settle cost estimates. Rate plans need a separate, versioned source and a calculator that applies the rule in force at the intended arrival time over the requested parking duration.

| Agency in availability feed | Rate source to verify | Current status |
|---|---|---|
| HDB | [Official HDB short-term parking charges](https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges), including central-area, peak-period, night and cap rules; HDB reference flags help identify parking facilities | 2,122 per-carpark calculators seeded, including reviewed peak/night/cap/boundary rules. Calendar, rounding and payment exceptions remain guarded. |
| URA | [URA `Car_Park_Details` API](https://eservice.ura.gov.sg/maps/api/) with `ppCode`, weekday/Saturday/Sunday/holiday rates, time windows and vehicle category | Authenticated retrieval succeeded: 3,960 detail rows staged. All 88 LTA URA car-lot IDs have matching `Car` rate codes; 88 of 89 direct URA car-lot IDs do. 657 partial calculators approved; paired standard night caps supported. Missing/zero rules, other long-period rows and day caps remain guarded. |
| LTA-agency mall/development carparks | Verified published tariffs for each carpark/operator | 12 operator calculators, five additional numeric operator fact sets, and guide/unresolved records covering all 40 identities. Guide-only facts are not approved prices. |

The current Lab 2 UC-01 excludes a carpark from a fair ranked comparison when it lacks a valid rate. Until rate coverage is verified, some LTA-only candidates may be available for inspection but not eligible for cost-based recommendations under that requirement. Changing this fallback policy would require updating the use case and scoring rules together.

LTA and URA access have both been obtained. URA's token is generated by the collector from the configured AccessKey; there is no need to paste the daily Token into `.env`. Inspect each run's manifest and rejected rows before enabling unattended polling.

## Source checks on 28 September 2026

| Source | Observed result | Purpose / limitation |
|---|---|---|
| HDB availability via data.gov.sg | HTTP 200 without credentials; first probe returned 2,017 carparks | Best initial availability source. Counts change between calls. Lot types and per-carpark update times must be handled separately. |
| HDB historical availability | HTTP 200 for requested 27 September noon; response timestamp 11:59:36 +08:00, 2,019 carparks | Backfill is possible for this tested time. This does not establish complete historical coverage. Validate every requested time. |
| HDB carpark reference data | HTTP 200, 2,272 reference records | Codes, address, coordinates, structure and parking-policy fields. Reference coverage differs from live feed coverage. |
| LTA CarParkAvailabilityv2 | Authenticated request succeeded: six pages, 2,606 accepted records | Contains HDB, LTA and URA agency records; feed provenance must be retained. Earlier unauthenticated request returned HTTP 404. |
| URA availability | Authenticated request succeeded: 154 accepted records, 0 rejected | AccessKey plus daily Token required. Earlier unauthenticated HTTP 200 responses were not valid data responses. |
| URA rates/details | Authenticated request succeeded: 3,960 raw records and 11,880 parsed day entries staged | Every active URA carpark with a rate code has a long-period rule. Resolve cap/alternative-charge semantics before quoting. |

Endpoints used:

```text
https://api.data.gov.sg/v1/transport/carpark-availability
https://api.data.gov.sg/v1/transport/carpark-availability?date_time=2026-09-27T12%3A00%3A00
https://data.gov.sg/api/action/datastore_search?resource_id=d_23f946fa557947f93a8043bbef41dd09&limit=1000&offset=0
https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2
https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=Car_Park_Availability
https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=Car_Park_Details
https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1
```

HDB metadata is paginated. The LTA adapter follows DataMall's documented 500-row pages using `$skip`. LTA can repeat HDB/URA observations, so adapters preserve feed and agency provenance and require verified identity mappings; never sum overlapping feed counts or join by name alone. LTA's documented motorcycle code is Y, while URA uses M. This pilot preserves source codes and exports only C from HDB for the current car model.

## Create Supabase: the steps Nestor must do

1. Sign in at https://supabase.com/dashboard and create/select your organisation.
2. Create a project named `parkchoicesg`. Select Singapore if available (otherwise the nearest appropriate region). Choose a plan after reviewing its current storage/compute limits.
3. Generate a database password and save it in your password manager. Do not paste it into chat or commit it.
4. Once the project is ready, open SQL Editor, run `schema.sql`, `schema_v2.sql`, `schema_v3.sql`, then `schema_v4.sql` through `schema_v8.sql` in order. They create only the private `parking_data` schema and its objects; they do not replace public tables.
5. Open **Connect** and copy the **Session pooler** connection string if your collector uses an IPv4-only connection. Use the exact dashboard host/user; do not guess them. Add `sslmode=require` at minimum; `verify-full` with the project certificate additionally verifies server identity.
6. Supply the connection string as `DATABASE_URL` in the collector environment. Percent-encode reserved characters in the password. The HDB `puller.py` reads the process environment; `provider_puller.py` also reads the ignored local `.env` file.
7. Install the optional loader dependency in a local virtual environment and test one small load:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# Set DATABASE_URL privately in your terminal/IDE environment first.
.\.venv\Scripts\python.exe puller.py --load
```

8. In SQL Editor, check:

```sql
select count(*) from parking_data.carparks;
select count(*) from parking_data.availability_observations;
select * from parking_data.training_car_observations limit 20;
```

All eight schema files are applied to the team project. Initial three-provider data and pricing seeds were loaded through the project-scoped Supabase MCP. `comparison.py` uses the approved versioned calculators; storage coverage is not a promise that an arbitrary stay can be quoted. The private direct database connection and Python loaders are now tested. Provision scoped ingestion and read-only roles before unattended/team use; keep the private schema inaccessible to client keys.

### Cloud pilot import, 28 September 2026

The HDB MCP import used the locally archived runs `c10d3765-c5c8-4f48-bf78-b200600f0025` (live) and `70945156-0436-42d6-8115-b0a6ef49a1ed` (27 September noon request). Original response checksums were verified before import. Current Supabase counts after the additional LTA and direct URA imports:

| Object | Rows |
|---|---:|
| `ingestion_runs` | 4 |
| `carparks` | 2,272 |
| `availability_observations` | 4,836 |
| `provider_availability_snapshots` | 2,760 |
| `training_car_observations` view | 3,497 |
| `carpark_identities` | 3,079 |
| `source_carpark_codes` | 5,163 |
| `ura_rate_rows` | 3,960 |
| `ura_rate_day_rules` | 11,880 |
| HDB published policy facts | 10 |
| HDB central/peak exceptions | 26 |
| HDB peak time windows | 16 |
| 2026 public-holiday dates (including observed Mondays) | 14 |
| URA draft `rate_schedules` | 658 |
| source-linked URA draft `rate_schedule_rules` | 3,444 |
| verified `rate_schedules` | 0 |

Each cleaner accepted 2,423 observations locally. The historical import stored 2,413 new rows because 10 source-time/lot-type keys were already present from the live snapshot. This is intentional deduplication; the two runs are only a connectivity and cleaning pilot, not enough time-series coverage to train or validate a model.

The private schema was checked after the URA import: neither `anon` nor `authenticated` has schema usage or rate/identity-table SELECT permission. The `availability_observations.run_id` index is applied in Supabase and included in `schema.sql`. The security advisor reports informational `RLS enabled, no policy` findings for the new private tables: these intentionally deny client access. The performance advisor reports unused indexes on newly created tables; the rate-schedule foreign-key index finding was fixed.

## Other accounts

- **data.gov.sg:** public requests worked without a key. A key can provide higher limits; follow the current dataset/API guidance before backfilling at scale.
- **LTA DataMall:** request API access at https://datamall.lta.gov.sg/content/datamall/en/request-for-api.html and follow the activation instructions. We need the AccountKey for an authenticated smoke test.
- **URA:** follow the access/account instructions linked from https://eservice.ura.gov.sg/maps/api/. The AccessKey requests a daily Token, which is then used with the AccessKey for data calls. Do not archive token responses in training data.
- **Google Maps:** not required to collect HDB availability history. Routing/ETA integration comes later; the collector does not need drivers' locations.

## Cleaning contract

| Case | Pilot behaviour |
|---|---|
| Provider timestamp without timezone | Interpret HDB's local timestamp as Singapore time; persist UTC with timezone. |
| Retrieval vs observation | Store both. Historical data retrieved today must not pretend it was available to our collector yesterday. |
| Numeric strings | Parse nonnegative whole counts; reject missing/noninteger values. |
| Zero available lots | Valid full-carpark observation when capacity is positive. |
| Available count greater than total | Quarantine; never silently clamp. |
| Zero capacity | Retain with quality flag, exclude from training view. |
| Stale observation | Flag if older than 15 minutes relative to live retrieval or historical query time. This is a configurable policy to agree with the model owner, not a provider guarantee. |
| Future observation | Reject when over 2 minutes beyond the comparison time. The allowance is an explicit clock-tolerance policy. |
| Unknown lot code | Quarantine for investigation; do not guess car/motorcycle semantics. |
| Duplicate key inside response | Collapse identical values; quarantine conflicting values. |
| Duplicate key already in database | Keep first stored observation; retain later raw capture for audit. Automated cross-run correction reconciliation is not implemented. |
| No matching reference carpark | Preserve row with flag; exclude from strict training view until resolved. |
| Missing carpark in response | Does not mean closed or zero availability. |
| Coordinates | Preserve original reference fields. SVY21 easting/northing are converted explicitly to WGS84, with bounds/axis checks and source provenance. |

Current reference metadata must not be treated as historically correct capacity/location attributes in a backtest. Capacity in the observation comes from that observation's payload. The training view deliberately does not join today's reference attributes into historical features.

## Model teammate handoff

The data contract is one unique carpark/lot-type/source-time observation. A future training builder should choose an explicit source-time grid, retain gaps, and construct labels at agreed forecast horizons with bounded matching tolerance. Do not join arbitrarily distant future observations to fill missing outcomes.

Use chronological train/validation/test splits. Fit scaling, imputation and feature selection only on training data. Compute lag/rolling features from past observations only. Historical backfill allows retrospective evaluation, but does not prove what the live application knew at that time. Prospective evaluation must save each forecast before its outcome is observed, with model version, target time and baseline.

Agree with the model owner on: pilot carpark cohort, 5/15/30-minute or other horizons, sampling interval, gap tolerance, confidence definition, current-reading baseline, and evaluation metrics. Sample horizons are proposals, not fixed requirements.

## Before running continuously

This is a one-shot local collector, not a deployed service. A first pilot could collect every five minutes for a selected cohort, subject to current API limits and model requirements. The current script fetches full metadata per run; add a daily reference cache before scheduling it frequently.

At 2,000 carparks and five-minute sampling, there can be about 576,000 car observations/day before deduplication. At 50 carparks it is about 14,400/day. Measure real database/index size and current Supabase limits first. Raw responses currently live on local disk; move them to controlled object storage with retention before relying on an unattended deployment. Do not put full raw payloads into every observation row.

Remaining work: sustained collection, deployment/scheduling, reference caching, retention, scoped database roles, model training and route/scoring integration. Pricing gaps are listed in [PRICING-READINESS-2026-09-30.md](PRICING-READINESS-2026-09-30.md); do not infer a tariff for unmatched `B0098`, unsupported operator identities or ambiguous provider windows. Refresh live observations before displaying availability.

## Sources

- HDB availability: https://data.gov.sg/datasets/d_ca933a644e55d34fe21f28b8052fac63/view
- HDB reference: https://data.gov.sg/datasets/d_23f946fa557947f93a8043bbef41dd09/view
- LTA official API guide: https://datamall.lta.gov.sg/content/dam/datamall/datasets/LTA_DataMall_API_User_Guide.pdf
- URA official API reference: https://eservice.ura.gov.sg/maps/api/
- Supabase connections: https://supabase.com/docs/guides/database/connecting-to-postgres
