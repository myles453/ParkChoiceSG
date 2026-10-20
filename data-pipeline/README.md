# ParkChoiceSG data collection

Collect and clean HDB, LTA and URA parking data into the team's existing Supabase PostgreSQL database. The model teammate owns operating collection and training an arrival-time availability predictor. Voice assistance is deferred.

## Read first

- [SCHEMA.md](SCHEMA.md): tables, row meanings, important fields, views and a dated row-count snapshot.
- [DATA-CONTRACT.md](DATA-CONTRACT.md): identity, timestamps, cleaning and deduplication.
- [PERIODIC-COLLECTION.md](PERIODIC-COLLECTION.md): frequency, logs, failures and stopping/restarting.
- [MODEL-TRAINING-HANDOVER.md](MODEL-TRAINING-HANDOVER.md): prediction target, export, evaluation and responsibilities.

## Setup and start

Use Python 3.12. From the repository's `data-pipeline` folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a private `.env` from the blank `.env.example`. Obtain these values privately:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection with ingestion/write permissions for the existing team database. |
| `LTA_ACCOUNT_KEY` | LTA DataMall API access. |
| `URA_ACCESS_KEY` | URA access; the collector obtains its daily token automatically. |

A frontend Supabase publishable key cannot access this private schema. Read-only training credentials cannot operate collection. Keep secrets out of Git and command arguments. Process environment variables take precedence over `.env`.

Verify one cycle, then start continuous collection:

```powershell
.\.venv\Scripts\python.exe collect_periodic.py --cycles 1
.\.venv\Scripts\python.exe collect_periodic.py
```

The initial interval is **five minutes**. Change frequency or select HDB only:

```powershell
.\.venv\Scripts\python.exe collect_periodic.py --interval-minutes 10
.\.venv\Scripts\python.exe collect_periodic.py --providers hdb --interval-minutes 5
```

Keep the terminal open, machine awake and network connected. **Ctrl+C stops collection.** Providers run sequentially; failures are logged and others are still attempted. Cycles do not overlap; missed slots are skipped. Assign one collection machine for the team. This is a foreground script, not an installed service/scheduler.

The training loop avoids repeatedly downloading URA's full rates dataset. For one collection cycle with the daily URA detail/rate refresh, use `collect_live.py`; unlike the periodic runner, it stops on the first provider failure. Each provider's database load is transactional. `--archive-only` saves local captures without database writes.

## Outputs and export

`data/<run-id>/` contains original compressed responses, checksums, manifests, cleaned observations, rejected rows and metadata. `data/collection/<session-id>/` holds session events and provider logs. Data, credentials, the local environment and Python caches are ignored by Git.

After sufficient regular collection:

```powershell
.\.venv\Scripts\python.exe export_training.py --output data/model-handover/hdb-arrival-pairs.csv --horizons 15 30 60
```

This defaults to HDB. `--include-retrieval-series` opts in to separate LTA/URA proxies. Inspect the export manifest for usable pairs and coverage; row count alone does not prove readiness. No interpolation or missing-count zero filling is performed.

## Runtime files

| File | Purpose |
|---|---|
| `collect_periodic.py` | Configurable loop, provider timeouts/failure isolation, lock and session logs. |
| `collect_live.py` | Single cycle and daily URA detail/rate refresh. |
| `puller.py` | HDB capture, cleaning, archiving and load. |
| `provider_puller.py` | LTA/URA capture, private configuration, cleaning, archiving and load. |
| `metadata_cleaner.py` | Coordinate conversion, metadata provenance and load. |
| `refresh_pricing.py` | Atomic import/versioning of supported URA tariff windows. |
| `import_ura_rates.py` | URA archive verification/parsing used by the rate loader. |
| `export_training.py` | Causal forecast-horizon feature/label export. |

The database schema and policies are already applied. This folder is an operational handover for that database: no SQL setup or dated seeds need to be run. Tests and one-off audit/seeding tools are excluded. Collection does not train a model or generate a final carpark ranking.

## Application integration

The active request-time API now lives in [../backend/](../backend/README.md).
It reuses parsing/HTTP helpers from this folder but reads its own `backend/.env`.
Collection still reads `data-pipeline/.env`; starting the API does not start collection.
The shipped HDB model is a probability classifier, described in
[the current model integration](../backend/MODEL-INTEGRATION.md). Older count-target
handover notes describe the generic export contract, not the shipped model output.
