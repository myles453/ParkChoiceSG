# Training data and time semantics

The application uses the HDB classifier in `../ml/` to estimate the probability
of at least one free car lot at arrival. Its training workflow backfills HDB
history into files. The PostgreSQL export described here is an additional
collection/export path; it is not the exclusive source of the shipped model.

## Collection and export

Run collection as a separate process using [PERIODIC-COLLECTION.md](PERIODIC-COLLECTION.md).
The default start interval is five minutes. Use a write-capable server credential
for collection and a read-only credential for exports. Configuration, raw
captures and exported datasets are excluded from Git.

Read [SCHEMA.md](SCHEMA.md) and [DATA-CONTRACT.md](DATA-CONTRACT.md). The
`parking_data.model_car_observations` view separates source-timestamped HDB
observations from LTA/URA retrieval proxies and excludes duplicate LTA copies of
HDB/URA series. Identity is `(agency, carpark_id)`.

```powershell
.\.venv\Scripts\python.exe export_training.py --output data/training-export/hdb-arrival-pairs.csv --horizons 15 30 60
```

The generic exporter produces an arrival count target, `label_available`; a
binary free-lot target can be derived as `label_available > 0`. This export is
distinct from the deployed classifier's response field, `p_free`.

`--tolerance-minutes` controls the permitted distance between the requested target
and its later source reading; the default is five minutes. Inspect the companion
manifest for coverage, missing labels, conflicts and proxy inclusion. Opt in to
separately labelled retrieval series with `--include-retrieval-series`.

## Validation rules

- Features must be known by issue time. Keep observation and first-seen times;
  exclude future labels, label offsets and ingestion IDs from model features.
- Split chronologically and remove targets crossing split boundaries. Fit
  transformations on training data only. Missing lags remain missing.
- Compare count forecasts with persistence using MAE. For binary probabilities,
  compare with the current-state baseline using Brier score and calibration,
  with results by horizon, coverage and starting occupancy.
- Record issued predictions before outcomes arrive, including model version,
  issue/target times, history cutoff and baseline. Keep unmatched outcomes and
  disclose timestamp tolerance.
- A provider reading is feed evidence rather than independent physical ground
  truth. LTA/URA retrieval proxies do not establish the time a count was measured.

The backend's active inference contract, supported horizons, confidence bands and
fallback rules are documented in [MODEL-INTEGRATION.md](../backend/MODEL-INTEGRATION.md).
