# ParkChoiceSG machine learning component

Predicts whether **at least 1 car lot will be free** at an HDB carpark when the driver arrives.
Two modes: a short-horizon LightGBM classifier (arrival within 90 minutes) and a lookup profile
(later arrivals). Everything below is run from the `ml/` directory.

## Setup

```bash
cd ml
python3.12 -m venv .venv            # the project venv is Python 3.12
.venv/bin/pip install -r requirements.txt
```

`data/` is git-ignored and is produced by the commands below. `models/` holds the trained model and is committed.

## 1. Backfill raw HDB snapshots

One availability snapshot per 5-minute Singapore timestamp, saved unmodified to
`data/raw/hdb/YYYY-MM-DD/HHMM.json.gz`. Resumable: finished files are skipped.

```bash
.venv/bin/python backfill_hdb.py --start 2026-10-06T00:00 --end 2026-10-07T23:55
.venv/bin/python backfill_hdb.py --start 2026-07-15T00:00 --end 2026-10-05T23:55
# 00:00 is always empty at the source, so also fetch 00:01 of each day
.venv/bin/python backfill_hdb.py --start 2026-07-15T00:01 --end 2026-10-07T00:01 --step-minutes 1440
```

Future timestamps are never requested (the API would return the current snapshot under the wrong time).

## 2. Build the dataset

```bash
.venv/bin/python build_dataset.py                        # both stages
.venv/bin/python build_dataset.py --stage observations   # stage 1: data/observations.parquet
.venv/bin/python build_dataset.py --stage pairs          # stage 2: data/pairs.parquet
```

Splits (Singapore dates): train 2026-07-15 to 09-15, validation 09-16 to 09-26, test 09-27 to 10-07.
Features only use readings known at decision time (`first_seen_at` and `observed_at` both at or before it).

## 3. Train and evaluate

```bash
.venv/bin/python train.py        # writes models/ (about 90 s, about 4.5 GB peak memory)
.venv/bin/python evaluate.py     # test split only: reports/evaluation.md, data/test_predictions.parquet
.venv/bin/python -m pytest tests service -v
```

## 4. Run the service

```bash
PARKCHOICE_ARTIFACT_DIR=models .venv/bin/uvicorn service.main:app
```

At start-up it logs `history warm-up finished: 5 of 5 calls succeeded` (it asks the feed for snapshots
15, 30, 45, 60 and 75 minutes ago to fill the lag history), then `background poll: N carparks fetched`
once every 60 seconds. `GET /health` reports whether the artefacts loaded.

### Example request and response (real, 2026-10-07)

```bash
curl -s localhost:8000/predict -H 'content-type: application/json' \
  -d '{"carpark_ids": ["GHCL"], "arrival_at": "2026-10-07T08:04:25Z"}'
```

```json
[{
  "carpark_id": "GHCL",
  "issue_at": "2026-10-07T07:44:25.257105Z",
  "arrival_at": "2026-10-07T08:04:25.235809Z",
  "horizon_minutes": 20.0,
  "mode": "short",
  "p_free": 0.9592330896678722,
  "free": true,
  "confidence": "Medium",
  "current_available": 3,
  "current_observed_at": "2026-10-07T07:42:54Z",
  "current_reading_stale": false,
  "model_version": "short-horizon-lgbm-20261007",
  "status": "ok",
  "fallback_reason": null
}]
```

(The response was returned for a request sent at 07:44:25Z with `arrival_at` 20 minutes later; the request shown is
rounded to the second.) `arrival_at` must carry a timezone and
must not be in the past. Up to 200 carparks per request.

### Fields

| Field | Meaning |
|---|---|
| `mode` | `short`: classifier on the live reading and recent history (arrival within 90 minutes). `profile`: historical share of readings with a free lot for this carpark, day type and 15-minute slot. |
| `p_free` | Probability that at least 1 lot is free on arrival. Null only when `status` is not `ok`. |
| `free` | `p_free >= free_threshold`. `free_threshold` is 0.9 (`models/model_card.json`). |
| `confidence` | Band of `p_free`, below. |
| `current_available` | Lots free in the latest live reading. **Null when that reading is older than 15 minutes** (and when the carpark has no reading). |
| `current_observed_at` | When the latest live reading was measured. Kept even when the reading is stale. |
| `current_reading_stale` | `true` when the latest reading is older than 15 minutes (`current_available` is then null), `false` for a fresh reading, null when the carpark has no live reading. |
| `fallback_reason` | Why the service did not use the plain short model, when it did not. |

### Statuses

| Status | Meaning |
|---|---|
| `ok` | `p_free` is present. In `profile` mode with a short horizon, `fallback_reason` says why the short model was not used (for example `current_reading_older_than_15_min`, in which case `current_available` is null and `current_reading_stale` is true). |
| `insufficient_history` | No profile cell for this carpark, day type and slot, so no probability (`p_free` null). Includes the 9 carparks with no data. |
| `unknown_carpark` | Not in the live feed and not in the profile. No probability. |
| `live_feed_unavailable` | The live feed failed. The profile probability is returned if a cell exists (mode `profile`), otherwise `p_free` is null. |
| `model_error` | The short model failed at request time. The profile probability is returned if a cell exists, otherwise null. Never reported as `ok`. |

An `ok` result never has a null `p_free`.

### Confidence bands

Lower bounds on `p_free` from `model_card.json`: **High** is `p_free >= 0.99`, **Medium** is
`0.90 <= p_free < 0.99`, **Low** is `p_free < 0.90`. On the test split (short model) the observed share of
rows with a free lot was 0.9996 in High, 0.9434 in Medium and 0.368 in Low. With `free_threshold` 0.9,
`free` is true exactly for High and Medium. Low means a free lot is not expected; it is the band where
the model is least certain.

## Known limits

- **HDB carparks only.** Other carpark types are not in the data.
- **Readings arrive late.** A reading is first seen a median of 115 seconds after it was measured (90th percentile 600 s).
- **9 carparks have no data** (no training rows and no usable profile): H1GL, HE17, HG1G, HG55, NHC, TM57, U67, W527, WGL
  (`reports/uncovered_carparks.csv`). They get `insufficient_history` for profile-mode arrivals, and for short
  arrivals whenever the live reading is older than 15 minutes (a short-mode answer is possible if their live reading is fresh). Carparks that stopped updating months ago return
  `current_available` null and `current_reading_stale` true, with their old `current_observed_at`.
- **Profile mode only covers patterns seen between 2026-07-15 and 2026-09-26.** Anything outside those
  weeks (public holidays other than 9 and 10 August, other seasons, events) is not represented. Public holidays
  are only known for 2026.
- **Short mode needs a reading at most 15 minutes old.** Otherwise the service falls back to the profile.
- **Calibration drifts a little on new data.** Test reliability in the lowest bins is off by up to 1 to 3 points.
- **History is in process memory.** After a restart, lag features fill only as far as the warm-up succeeds, and
  each uvicorn worker has its own history.
- Lags can still be missing for carparks that update rarely; the model handles missing values but is less accurate then.
- Model skill is mostly "stay as you are": see `reports/agent-e.md` for the split between rows whose state
  changes before arrival and rows whose state does not.

## Application integration


For the connected app, use port **8001** for this inference service and port **8000**
for the recommendation API. Follow [the working backend setup](../backend/README.md),
which uses `ml/requirements-inference.txt` for the verified runtime dependencies.
The commands below also document the standalone training workflow.
