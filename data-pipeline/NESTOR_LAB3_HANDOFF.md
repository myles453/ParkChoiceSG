# ParkChoiceSG Lab 3 handoff — data pipeline and carpark comparisons

Last updated: 2 October 2026. This is a working handoff for a new chat, not a submission document. Read the current files and database before relying on the figures below; database counts and availability freshness change with each collection.

## Periodic collection handoff

The model teammate will operate data collection. `collect_periodic.py` starts immediately and repeats every five minutes by default; `--interval-minutes` changes the interval, `--providers` selects feeds and `--cycles` limits the run. It uses existing loaders, isolates provider failures/timeouts, records session/capture logs and prevents a second periodic instance in the same workspace. Missed slots are skipped; no overlapping cycles or fake backfills. It runs in the foreground until Ctrl+C, with no installed automation. The full URA pricing dataset is not pulled in this training loop. See `PERIODIC-COLLECTION.md` and `MODEL-TRAINING-HANDOVER.md`. The suite now has 85 passing tests.

## Direct collection and automated URA pricing — 2 October

The private `DATABASE_URL` Session pooler connection now works. Supabase MCP CLI login succeeded, but MCP tools were not exposed to this session; direct psycopg access works independently. Never print the connection string or `.env` contents.

`collect_live.py` automatically requests URA details when the last runtime-compiled capture is more than one day old. `refresh_pricing.py` imports checksum-verified raw rows, compiles known per-unit windows and paired night caps, explicitly blocks unknown windows, and supersedes old URA schedules in the same transaction as that provider's availability load. Same-capture replay is idempotent; unseen older captures are refused. HDB/operator policy reviews are not automatically extended. `check_comparison_readiness.py` provides a read-only live quote/availability audit. The suite now has 79 passing tests.

See `PRICING-WORKFLOW-2026-10-02.md` for final verification. Both URA rate imports succeeded, including the batched loader. HDB, LTA and URA availability was refreshed again at 19:11–19:13 Singapore time. Original HDB reference baselines were attached to all 2,122 schedules using `attach_hdb_reference_baseline.py`; comparison refuses changed flags. Do not rerun dated seed files to refresh review dates. No schema changes were made in this continuation.

Latest HDB and LTA collections have been loaded directly. HDB's four tariff-relevant reference flags have no changes from the September 30 seed snapshot. Pricing availability still differs from recommendation eligibility: recent LTA/URA retrievals are labelled honestly, and the strict comparison flag still requires a source-update timestamp. Routes and arrival predictions are separate integrations. Earlier dated observations below are historical; the absent-connection and untested-loader statements no longer apply.

## Latest pricing continuation — read first

Schemas through v8 and the pricing seeds are applied in Supabase. See `PRICING-READINESS-2026-09-30.md`: 2,122 HDB, 657 partial URA and 12 partial operator calculators; five additional operator fact sets, 38 LTA guide matches and two unresolved LTA identities. All 40 LTA identities have an evidence/unresolved record. These are not universally quoteable prices.

`comparison.py` now delegates to `pricing.quote_schedule`, loading versioned rates/rules rather than the old daytime-only HDB helper. Supported HDB peak/night/cap/boundary cases are implemented. Calendar/rounding/payment exceptions, ambiguous URA rows, operator band crossings and Tampines Mall's disputed weekend first duration remain guarded. Keep numeric source facts distinct from calculator approval. IMM needs first-entry status. Stored availability is stale; arrival-time recommendations remain false until routes and prediction are integrated.

New files include `schema_v7.sql`, `schema_v8.sql`, `pricing.py`, `test_pricing.py`, HDB/URA/operator seed files, public tariff capture/generator scripts and reviewed/pending operator JSON catalogues. 70 tests pass. Live schema queries and database-backed sample day/night calculations succeeded; seed replay left counts unchanged. All 19 tables have RLS and no client access. `DATABASE_URL` is still absent, so a direct Python PostgreSQL connection remains untested. Existing provider keys stay private in `.env`.

Working directory remains `C:\Users\Nestor\OneDrive - Nanyang Technological University\Documents\CS Y2S1\SC2006\SWE project\ParkChoiceSG\data-pipeline`; use `.venv\Scripts\python.exe`. Raw archives, source page hashes and live database verification fixtures/reports are ignored under `data/`. Read the pricing report's refresh instructions before changing dates or replaying the dated seeds for a new capture. Do not commit/push unless requested.

## Earlier availability continuation — superseded for pricing

Supabase MCP was re-authenticated and is available again. Schemas through `schema_v6.sql` are now applied remotely. A fresh HDB/LTA/URA capture at 30 September 20:01 SGT was cleaned and imported. See `DATA-READINESS-2026-09-30.md` for measured results; this section supersedes older counts/readiness claims below.

The work directory is `C:\Users\Nestor\OneDrive - Nanyang Technological University\Documents\CS Y2S1\SC2006\SWE project\ParkChoiceSG\data-pipeline`. Its tested Python executable is `.venv\Scripts\python.exe` (Python 3.12). Runtime dependencies are pinned in `requirements.txt`; `.venv`, `.env` and raw `data` remain ignored. No Git commit or push was made. The database schema/loads **were** applied.

New files: `metadata_cleaner.py`, `prepare_import.py`, `export_training.py`, `schema_v5.sql`, `schema_v6.sql`, two new test files and the readiness report. Existing collectors now write cleaned metadata; `collect_live.py --archive-only --include-rates` works without `DATABASE_URL`. `prepare_import.py` creates replayable SQL batches for MCP imports; direct collector `--load` still loads a provider in one transaction. The Python automated path requires `DATABASE_URL`, which is still absent locally. MCP OAuth does not configure that connection string.

Use `carpark_candidate_inputs` for comparison, with WGS84 locations/provenance and independent capacity evidence. `model_car_observations` supplies primary HDB/URA/LTA-agency series; LTA's HDB/URA copies are excluded from training. HDB historical-first/live-later provenance and cross-run conflicts are handled. `export_training.py` produces causal arrival-horizon pairs, retrieval proxies only on explicit opt-in, and chronological split purging. Current sparse archives produce **zero 15/30/60-minute pairs**, so training is not ready just because the schema exists. There are 47 passing local tests, plus successful rolled-back live PostgreSQL checks.

Location coverage: HDB 2,272, LTA 40, URA 657 usable sets; URA has 22 multi-point carparks. Keep all points and never claim they are verified entrances. URA `B0098` has missing geometry/Car rate, `C0010` has invalid Car-details geometry, and `M0088`, `S0106`, `W0029` have available-count/detail-capacity mismatches. Capacity ratios must not use those metadata denominators. LTA capacity remains unknown.

Still needed: regular collection and temporal coverage criteria; daily reference caching before frequent unattended pulls; reviewed URA quote rules and separately sourced LTA operator tariffs; remaining HDB price cases; routing estimates to each carpark and walking route to destination; trained model with calibrated confidence and prospectively logged evaluations; agreed ranking weights/normalization. The fresh URA rate payload is identical to the previously staged payload, so duplicate unchanged draft schedules were not imported. `comparison.py` now reports `price_comparison_eligible`; arrival-time `recommendation_eligible` remains false while predictions/routes are absent.

## Project direction and Nestor's scope

ParkChoiceSG recommends Singapore carparks using estimated parking cost, location/travel time, and availability. The team plans to predict **available car lots at the driver's estimated arrival time** rather than presenting a current reading as an arrival-time forecast. Predictions should be logged before their target time and later compared with the observed availability. Voice assistance is deferred.

Nestor's current scope is the data pullers, cleaning rules, Supabase PostgreSQL data model, and reliable availability/pricing inputs for carpark comparison. The model teammate will train the predictor after a usable time series has been collected.

Repository: `C:\Users\Nestor\OneDrive - Nanyang Technological University\Documents\CS Y2S1\SC2006\SWE project\ParkChoiceSG`. Work here: `data-pipeline/`. The package is published on `main` under the top-level `data-pipeline/` folder. The Lab 3 package is versioned independently of the unrelated local Lab 2 edits. Inspect `git status` and do not reset, overwrite, or commit unrelated work. Credentials, raw captures and exported training CSVs remain ignored.

## What exists

Read these in order:

1. `README.md` — collector setup, commands, existing data and limitations.
2. `DATA-CONTRACT.md` — identity, timestamp, price and comparison semantics.
3. `schema.sql`, `schema_v2.sql`, `schema_v3.sql`, `schema_v4.sql` — applied in that order to the team Supabase project's private `parking_data` schema. Do not rerun them blindly; inspect the live schema first.
4. `puller.py` — direct HDB availability and carpark reference collection; HDB also supports a historical query.
5. `provider_puller.py` — authenticated LTA and URA availability collection. The URA daily token is requested automatically and is not archived.
6. `import_ura_rates.py` — verifies an archived URA details response and prepares typed, source-linked draft tariff rows.
7. `comparison.py` — request-specific, conservative HDB daytime price estimates and comparison output.
8. `collect_live.py` — one live HDB → LTA → URA collection/load cycle. It stops on the first failure and leaves manifests for inspection.

The private schema has canonical `(agency, carpark_id)` identities and exact, same-agency source-code mappings. HDB observations preserve the provider's update time and total capacity. LTA and URA snapshots preserve retrieval time but do not pretend to have an HDB-style source update time or capacity. `car_latest_availability` chooses one reading per canonical carpark without summing overlapping feeds. `carpark_comparison_inputs` exposes availability status and price evidence for the backend. The Flutter client must use a backend; do not expose the private schema or database password in the app.

## Last verified state and limits

As checked on 28 September, the Supabase project held 3,079 canonical identities, 4,836 HDB availability rows, 2,760 LTA/URA provider rows, and 3,497 strict HDB car-training observations across 1,871 carparks. Each carpark had at most two training observations, so the dataset could support loader/baseline development but **not a reliable trained arrival-time model**. Requery these counts; they may have changed.

The comparison view identified 2,110 HDB carparks as possible standard daytime tariff candidates before arrival/duration checks. `comparison.py` can quote ordinary HDB daytime stays of up to four hours when all its conditions pass: supported short-term hours, current policy/reference capture, covered holiday calendar, one rate band, and an explicit payment method (Parking.sg is the coupon-carpark default). It accounts for EPS's 15-minute grace period and Sunday/gazetted-holiday free windows. It returns a reason instead of a number for peak tariffs, overnight/cap cases, ambiguous boundaries, observed holidays, and other unsupported cases. Arrival must be within the next 24 hours. This is a limited estimate, not a complete tariff engine.

URA has 3,960 raw rate rows and 658 **draft** car schedules; no URA schedule was verified. In particular, overlapping night per-unit and `$5 / 510 mins` rows need interpretation, and `$0.00 / 0 mins` must not automatically mean unlimited free parking. The LTA availability feed contains no prices. Do not claim complete cross-agency cost comparison until these rates are reviewed and calculated. The old `carpark_comparison_readiness` view checks for verified schedules and can remain false even where the new HDB request-specific calculator could quote; use `carpark_comparison_inputs` plus `comparison.py` for this pilot.

At the last database check on 28 September, **zero** availability readings met the 15-minute freshness rule. A retrieval-recent LTA/URA reading still does not prove the underlying source is fresh. `comparison.py` marks recommendations eligible only when a positive, source-timestamped HDB reading is fresh **and** a price can be quoted. Current availability must never be labelled as predicted availability at arrival.

The ignored `.env` currently contains `LTA_ACCOUNT_KEY` and `URA_ACCESS_KEY`; it does **not** contain `DATABASE_URL`. Do not print or paste secret values. The Python `--load` path and `comparison.py` database connection have not yet been exercised against the live project. The SQL schemas and view were applied and queried through a project-scoped Supabase MCP connection in the previous chat.

On 30 September, `python -m unittest discover -q` in `data-pipeline/` passed **31 tests**. This verifies parser/calculator behavior, not live provider access or a direct PostgreSQL connection.

## Working directions for the next chat

1. **Start with an audit.** Read this handoff, `README.md`, `DATA-CONTRACT.md`, and `git status`. Check whether the Supabase MCP connection is available and query the live schema/counts/freshness. Treat the dated figures above as historical checkpoints.
2. **Finish the database connection test.** Have Nestor put the Supabase **Session pooler** connection string into the ignored `.env` as `DATABASE_URL` or a trusted process environment variable; never request that the password be pasted into chat. The collector needs write access. Before deployment, create separate least-privilege read and ingestion roles.
3. **Run a single live cycle** from `data-pipeline/` with `python collect_live.py` once the connection is configured. Inspect each new `data/<run-id>/manifest.json` and rejected rows. Verify that the new HDB, LTA and URA timestamps/row counts appeared in `parking_data` and that no duplicate capacity or source-time labels were invented. The script currently reloads HDB reference metadata each run; add a daily cache before frequent scheduling.
4. **Test the comparison path** with a near-term Singapore arrival and duration: `python comparison.py --arrival "<ISO-8601 time with +08:00>" --duration-minutes 60 --show-unready --limit 20`. Check a standard HDB case, a peak/unsupported case, a URA case, and an LTA case. Verify that stale/unpriced candidates remain labelled rather than silently entering recommendations.
5. **Finish remaining price gaps.** Read the current pricing readiness report first. Standard HDB peak/night/cap/boundary logic and partial URA/operator calculators now exist. Confirm unresolved calendars, fractional rounding, paper rules, URA long-period/zero rows and pending mall tariffs; retain sources, dates and per-request guards.
6. **Prepare sustained collection/model handoff.** Set a justified polling interval and provider-limit policy, cache reference data, monitor failures and storage, and define retention. Keep HDB historical backfill separate from genuinely live observations. Export only eligible car rows for training. The model teammate should use chronological splits, a current-reading baseline, saved forecast/target pairs, and bounded matching to later observed outcomes.
7. **Keep changes scoped.** Run `python -m unittest discover -q` after edits, check the affected SQL against the live schema and Supabase security/performance advisors, and update the data contract when assumptions change. Do not push or commit unless requested.

Useful read-only SQL after reconnecting:

```sql
SELECT agency, availability_status, pricing_evidence_status, count(*)
FROM parking_data.carpark_comparison_inputs
GROUP BY 1, 2, 3 ORDER BY 1, 2, 3;

SELECT source, count(*), max(first_retrieved_at) AS latest_retrieval
FROM parking_data.availability_observations GROUP BY source;

SELECT feed, agency, count(*), max(retrieved_at) AS latest_retrieval
FROM parking_data.provider_availability_snapshots
GROUP BY feed, agency ORDER BY feed, agency;

SELECT count(*) AS training_rows, count(DISTINCT carpark_id) AS carparks
FROM parking_data.training_car_observations;

SELECT review_status, count(*) FROM parking_data.rate_schedules
GROUP BY review_status;
```

Suggested first message in the new chat: **“Continue ParkChoiceSG Lab 3 from `data-pipeline/NESTOR_LAB3_HANDOFF.md`. Follow its working directions. First audit the repo and live Supabase state, then finish the safe comparison/collection work without changing unrelated Lab 2 files.”**
