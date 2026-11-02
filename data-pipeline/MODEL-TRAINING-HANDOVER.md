# Model teammate's scope and handover

## Responsibilities and target

Predict **available car lots at arrival at each candidate carpark**. Driving ETA determines the forecast horizon; parking duration determines cost separately. Destination ETA alone is not ETA at every carpark.

The model teammate owns operating/monitoring periodic collection, features/cohort/horizons, training, evaluation, confidence and inference code. Nestor maintains the collectors, cleaning/database contract and export tooling. Agree sampling interval, coverage, label tolerance, split boundaries and fallback rules together. Voice assistance is deferred.

Start with [PERIODIC-COLLECTION.md](PERIODIC-COLLECTION.md). The initial interval is five minutes. The database contains pilot captures; continuous history and validation coverage still need to be measured. A large row count does not establish training readiness.

## Data and export

Read [SCHEMA.md](SCHEMA.md) and [DATA-CONTRACT.md](DATA-CONTRACT.md). Use `parking_data.model_car_observations`, not the latest-reading view or an unfiltered provider union. Identity is `(agency, carpark_id)`. HDB provides source timestamps and synchronized capacity; LTA/URA provide retrieval proxies. LTA's HDB/URA copies are excluded from the model view. Provider readings are API evidence, not independently verified physical ground truth.

Work from `data-pipeline`. A private read-only credential is sufficient for training exports; operating collection needs ingestion/write permission. Raw captures, `.env` and exports are not supplied by Git.

```powershell
.\.venv\Scripts\python.exe export_training.py --output data/model-handover/hdb-arrival-pairs.csv --horizons 15 30 60
```

Opt in to separately labelled retrieval series using `--include-retrieval-series`. `--tolerance-minutes` sets label tolerance (default five). `--split-at <aware-ISO-time>` sets a chronological train/validation boundary. `--archives data` reads verified capture folders instead of PostgreSQL; it needs the actual archives, not just a CSV. Inspect the companion manifest for pairs/conflicts/proxy inclusion. Its readiness flag does not become true based on counts alone.

## Features, labels and validation

Features include latest known availability, synchronized HDB capacity/free ratio, actual observation age, 5/15-minute lags with timestamps, previous-hour sample count, horizon, Singapore arrival weekday, 15-minute slot and weekend flag. Weekday is ISO 1=Monday through 7=Sunday; slots are 0–95. Missing lags remain missing.

The target is **`label_available`**, from the first later reading at/after arrival within tolerance. Inspect `label_offset_seconds`; the measurement may not be at the exact requested instant. `label_kind` separates source readings and retrieval proxies. Never use label values/timestamps/offsets/run IDs or other future information as features. Run IDs are audit metadata.

1. Benchmark against persistence: arrival availability equals the latest known available count.
2. Use chronological train/validation/test periods and purge targets crossing boundaries. Fit scaling, encoding, imputation and feature selection on training only. The exporter does not create a three-way split or automatically purge all cross-validation folds.
3. Report MAE in lots by horizon, carpark and source, plus sample counts, coverage and baseline error. Examine errors near full carparks. Do not randomly split adjacent time-series rows, fill gaps with zero or interpolate using future readings.
4. Define/calibrate confidence on held-out reliability. High/Medium/Low needs documented measured criteria; freshness/sample count alone is insufficient.
5. For live validation, save each forecast before its outcome arrives: issue time, target arrival, history cutoff, identity, prediction, version and baseline. Match outcomes using a declared tolerance and retain missing outcomes. LTA/URA validation is against future retrieved readings, not confirmed physical counts at the exact target instant.

## Backend interface to agree

Inputs: identity, issue time, candidate arrival/horizon and history known by issue time. Outputs: predicted available lots, issue/target times, model version, history cutoff, recent sample count, calibrated confidence/interval, and status/fallback reason. Counts must be finite/nonnegative; a capacity upper bound is valid only with trustworthy capacity.

For insufficient history, stale input, an unseen carpark or unsupported horizon, return an explicit fallback/unavailable status. A latest-reading fallback remains labelled current availability. The backend then combines a valid forecast with candidate-specific price/routes under agreed scoring rules.
