# ParkChoiceSG model-training handover

Updated 2 October 2026. Owner handoff: Nestor (collection/database) to the model-training teammate.

## What the model predicts

Predict the number of available **car lots at arrival at a specific carpark**. Example: issue a forecast at 14:00 for carpark `(HDB, A1)` at 14:20, then compare it with a later provider reading near 14:20. Price and travel-time scoring are backend responsibilities; parking duration determines cost, while driving ETA determines the forecast horizon.

Each candidate needs its own arrival time from routing to that carpark. ETA at the destination is not necessarily ETA at each candidate carpark. The model must handle the horizon explicitly and reject/fall back for horizons outside its validated range.

## Current readiness: pipeline available, time series still sparse

The three-provider collectors, private Supabase PostgreSQL schema and causal training exporter work. The model teammate now owns running periodic collection. `collect_periodic.py` repeats every five minutes by default, with a configurable interval, provider failure isolation, logs and protection against overlapping cycles. It runs in the foreground; no service or operating-system schedule is installed. See `PERIODIC-COLLECTION.md` for setup and monitoring. `collect_live.py` remains the single-cycle collection/pricing command.

The current raw model view contains:

| Primary series | Observations | Carpark codes | Distinct collection instants | Timestamp semantics |
|---|---:|---:|---:|---|
| HDB direct | 7,021 | 1,930 | 4 | Provider source-update time |
| LTA feed, LTA agency only | 160 | 40 | 4 | Retrieval time |
| URA direct | 445 | 89 | 5 | Retrieval time |

The exporter excludes three HDB observations whose source clocks are ahead of their collection times, leaving 7,018 causal HDB observations, or 7,623 including retrieval series. **Both exports currently produce zero valid 15/30/60-minute feature-label pairs**, using a five-minute label tolerance. Large gaps between collections are the reason; thousands of carparks sampled a few times do not make a continuous time series.

The teammate can build preprocessing, baselines, training and evaluation now, but cannot claim a trained/validated arrival predictor from these exports. First agree a collection interval and cohort, then accumulate coverage across daily peaks, weekdays and weekends. A five-minute interval is a proposed pilot setting, subject to provider limits and measured update cadence. Minimum history and acceptable error must be agreed and measured, not inferred from row count.

## Data access and files

Use `parking_data.model_car_observations` for the prepared primary series. Do not train from the latest-reading view, tariff tables, or an unfiltered union of all feeds.

Start with the exported `data/model-handover/model-observations.csv` and `observation-summary.json`. This snapshot has 7,626 rows, including the three clock-ahead rows that the training exporter excludes. It is suitable for inspecting fields and developing the workflow, not evidence of training readiness. Run it through the same causal/quality rules before modelling. Empty arrival-pair CSVs and their `.manifest.json` files document the current zero-pair result.

These files live under ignored `data/` and will not accompany a normal Git push. Share them separately. The pipeline source and handover documents are versioned under `data-pipeline/`; pull the latest `main` branch. Do not send `.env` or the owner database connection string. For live access, arrange a separate read-only database credential privately; a frontend Supabase publishable key cannot read this private schema. Operating the collector requires a separate credential with ingestion/write permissions, as explained in `PERIODIC-COLLECTION.md`.

Local working directory:

`C:\Users\Nestor\OneDrive - Nanyang Technological University\Documents\CS Y2S1\SC2006\SWE project\ParkChoiceSG\data-pipeline`

The teammate should use the equivalent directory in their own checkout. On a fresh machine, create a Python 3.12 environment and install the pinned `requirements.txt`.

### Observation fields

| Field | Meaning / modelling rule |
|---|---|
| `agency`, `carpark_id` | Joint carpark identity. Never merge codes across agencies. |
| `feed` | Which provider feed produced the series. Retain it for provenance and separate evaluation. |
| `lots_available` | Available car-lot count. Zero is valid; a missing reading is not zero. |
| `total_lots` | Synchronized HDB capacity where supplied. LTA/URA series leave it NULL; do not invent an occupancy ratio. |
| `observed_at` | HDB's source-update instant, or a retrieval proxy for LTA/URA. |
| `known_at` | When the collector first knew that observation. This controls whether it can be a feature for a decision. |
| `timestamp_kind` | `source_update` or `retrieval`; the latter does not prove underlying provider freshness. |
| `run_id` | Audit link to the original capture. Keep for debugging, not as a numeric predictive feature. |

Timestamps are timezone-aware; use `Asia/Singapore` for weekday/time-slot features. Do not interpret UTC hour as Singapore hour.

The model view uses HDB direct, URA direct, and LTA's LTA-agency readings. LTA also republishes HDB/URA readings; those copies are excluded so they do not become independent training samples. Provider counts are observed API readings, not physical measurements verified by us.

## Training-pair exporter

From the pipeline directory, with privately configured database access:

```powershell
.\.venv\Scripts\python.exe export_training.py --output data/model-handover/hdb-arrival-pairs.csv --horizons 15 30 60
```

HDB is the default. Opt in to the separate retrieval-proxy series only deliberately:

```powershell
.\.venv\Scripts\python.exe export_training.py --include-retrieval-series --output data/model-handover/all-primary-arrival-pairs.csv --horizons 15 30 60
```

Without database access, checksum-verified local capture folders can be used via `--archives data`. This requires the actual archive folders, not just the observation CSV. The Python dependencies/imported modules must be present from the pipeline checkout.

The exporter builds features only from information known by `decision_at`. It uses the latest usable count, synchronized HDB capacity/free ratio, observation age, 5/15-minute lags, preceding-hour sample count, horizon, and Singapore arrival weekday/15-minute slot/weekend flag. Lags can be missing; their actual observation times are supplied. Arrival weekday uses ISO 1=Monday through 7=Sunday; slot is 0–95. No current metadata is retroactively joined into historical features.

The target is `label_available`. It is the first reading at or after `arrival_at`, within the declared tolerance (default five minutes). Inspect `label_offset_seconds`; this is not guaranteed to be a reading at the exact requested second. Labels outside tolerance produce no pair. LTA/URA targets are labelled `retrieval_proxy` and must be reported separately from HDB `source_reading` labels.

Do not give the model `label_available`, `label_observed_at`, `label_known_at`, `label_offset_seconds`, `label_run_id` or other future information as features. Run IDs are audit metadata. `decision_at` and feature provenance should support reproducibility.

## Evaluation requirements

1. Start with the persistence baseline: predict arrival availability equals the latest known available count. The trained model must demonstrate improvement over this baseline on held-out data.
2. Split chronologically. Use `--split-at <aware-ISO-time>` for the exporter’s train/validation split and target purging. Set the boundary after sufficient history exists; it is not preselected. Reserve a later independent test period as well. The exporter does not automatically create a three-way split or guarantee all cross-validation folds are purged.
3. Fit scaling, encoding, imputation and feature selection on training data only. Never randomly split adjacent time-series rows, fill observation gaps with zero, or interpolate using future readings. Evaluate capacity/location changes with appropriate historical provenance.
4. Report MAE in lots by horizon, carpark and source, alongside sample counts, time coverage and the baseline's MAE. Also examine false predictions of availability near full carparks. Overall averages can hide a poor result on the carparks that matter.
5. Define and validate confidence. High/Medium/Low must correspond to measured held-out reliability, calibrated intervals or agreed error thresholds. Source freshness and training sample count alone are not confidence calibration.
6. For prospective validation, save each forecast before its outcome arrives. Record issue time, target arrival, input/history cutoff, identity, prediction, model version and baseline. Match the later provider outcome with a declared tolerance and retain missing outcomes. LTA/URA comparison validates future retrieved readings, not proven physical lot counts at the exact target instant.

## Proposed model/backend interface to agree

Inputs: `(agency, carpark_id)`, forecast issue time, candidate arrival time/horizon, and the feature history available by issue time. Agree required inputs, missing-feature behaviour and supported horizons together.

Outputs: `(agency, carpark_id)`, `issued_at`, `target_arrival_at`, `predicted_available_lots`, `model_version`, `history_cutoff`, relevant recent `sample_count`, confidence value/label with its documented definition, and `status`/fallback reason. If an uncertainty interval is available, return it. Counts must be finite and nonnegative; only enforce a capacity upper bound when the applicable capacity is trustworthy.

For insufficient history, stale inputs, an unseen carpark or unsupported horizon, return an explicit fallback/unavailable status. A current-reading fallback must remain labelled current availability; it must not be presented as a successful model forecast. Price calculation and the final ranking can then use the returned status deliberately.

## Decisions for the two owners

- Nestor: collector implementation, provider cleaning, observation storage and export tooling.
- Model teammate: operating/monitoring periodic collection, feature choices, supported cohort/horizons, training, evaluation, confidence and saved model/inference code.
- Together: sampling interval, minimum temporal coverage, train/validation/test boundaries, label tolerance, whether to support retrieval proxies initially, fallback rules and the inference interface.

The immediate next step is for the model teammate to configure and start `collect_periodic.py`, inspect successful cycles and agree the initial cohort. The initial interval is five minutes and can be changed with `--interval-minutes`. HDB is a sensible initial dataset because it includes a source-update timestamp and synchronized capacity. URA/LTA can follow with their timestamp limitations explicitly preserved.
