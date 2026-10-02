# Periodic training-data collection

The model teammate owns running collection. `collect_periodic.py` starts immediately and repeats on a **five-minute start interval** by default. Change the interval with `--interval-minutes`. This is the team's initial setting, not a guarantee of a provider's update frequency.

## Setup on the teammate's machine

Use Python 3.12 and run from `ParkChoiceSG/data-pipeline`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create a private `.env` using the blank `.env.example`. Obtain `DATABASE_URL`, `LTA_ACCOUNT_KEY` and `URA_ACCESS_KEY` privately. The collector needs a trusted database credential with ingestion/write permissions; a read-only training credential cannot run database collection. Do not commit the filled `.env` or put keys in command arguments. All required tables are already applied to the team project; this script creates no schema.

## Commands

All three providers, every five minutes, until stopped:

```powershell
.\.venv\Scripts\python.exe collect_periodic.py
```

Set another frequency, for example ten minutes:

```powershell
.\.venv\Scripts\python.exe collect_periodic.py --interval-minutes 10
```

HDB only, useful for the initial source-timestamped model:

```powershell
.\.venv\Scripts\python.exe collect_periodic.py --providers hdb --interval-minutes 5
```

One cycle to verify configuration before leaving it running:

```powershell
.\.venv\Scripts\python.exe collect_periodic.py --cycles 1
```

Use `--cycles N` for a bounded number of cycles, `--provider-timeout-seconds 180` to change the per-provider timeout, and `--archive-only` to keep local cleaned captures without database writes. Intervals/timeouts must be finite positive numbers. Change settings by stopping and restarting with the new arguments.

Keep the terminal open, computer awake and network connected. Stop with **Ctrl+C**. This is a foreground script, not an installed Windows service, scheduled task or cloud job. Sleep/offline periods leave genuine data gaps; restarting does not manufacture missed observations. Assign one collection machine for the team. The local lock prevents a second periodic collector in the same workspace, not collectors on other machines or independent one-shot scripts.

## What happens each cycle

- HDB, LTA and URA run sequentially through their existing cleaners and PostgreSQL loaders. Each gets its own real capture timestamp. The script does not pretend they were simultaneous or align them to a fabricated clock grid.
- If a provider fails or exceeds its timeout, the others are still attempted. The next cycle retries at the configured cadence. Existing HTTP retry/backoff and quality rules remain in the provider collectors.
- Cycles do not overlap. If work exceeds the interval, expired start slots are skipped; delayed cycles are not replayed in a burst. With a five-minute interval, a cycle taking six minutes will resume at the next available scheduled start (ten minutes from the previous scheduled start).
- Existing HDB observation deduplication, conflict quarantine and LTA/URA timestamp semantics remain unchanged. Missing readings are not replaced with zero.
- This training collector does **not** download URA's full pricing/detail dataset every five minutes. Use `collect_live.py` separately for the normal daily pricing refresh, when needed. HDB's reference dataset is still fetched each HDB cycle; monitor collection duration and API errors, and adjust the interval if needed.

## Outputs and monitoring

Raw archives, cleaned CSVs and per-capture manifests remain under `data/<run-id>/`. Session logs are under:

`data/collection/<session-id>/`

`events.jsonl` records interval, providers, start/end events, failures, timeouts and skipped slots. Each `cycle-00001-hdb.log` (or LTA/URA equivalent) contains that provider's collection result and archive location. Successful result events include the run ID and accepted/rejected counts. Check these logs to establish actual cadence and temporal coverage.

Successful finite runs exit with code 0; finite runs with any failed/timed-out provider attempt exit with code 1; Ctrl+C exits with code 130. Timeout or interruption may leave a partial local capture; only confirmed completed loads count as successful. A provider transaction commits all its writes or rolls them back. A run that committed immediately before an interruption may still exist in the database, so inspect its manifest rather than assuming it was lost. OS process termination releases the collector lock; do not delete the persistent lock file to force a second instance.

The script does not export training pairs automatically. After sufficient collection, use:

```powershell
.\.venv\Scripts\python.exe export_training.py --output data/model-handover/hdb-arrival-pairs.csv --horizons 15 30 60
```

Inspect the accompanying manifest for usable pair counts. A few successful cycles demonstrate operation, not model readiness. Agree coverage, chronological evaluation periods and confidence criteria before training. See `MODEL-TRAINING-HANDOVER.md` for the prediction target, fields and leakage rules.

## Verification on 2 October

85 tests passed, including skipped-slot scheduling, provider failure/timeout isolation, archive-only mode and cross-process lock exclusion/release. A finite live cycle was started from outside the pipeline directory with the default five-minute interval. It loaded HDB (2,425 accepted observations), LTA (2,606) and URA (154); all three run IDs were verified in PostgreSQL. The cycle took approximately two minutes and stopped after one cycle. No continuous collector was left running.
