# ParkChoiceSG backend

This is the working recommendation backend. Develop here rather than in an academic
submission directory. The active app is `../parkchoice_flutter/`, the existing HDB
inference service is `../ml/`, and the shared collection scripts are `../data-pipeline/`.

## Setup and run

Use Python 3.12. From the repository root:

```powershell
py -3.12 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\.venv\Scripts\python.exe -m pip install -r ml/requirements-inference.txt
Copy-Item -LiteralPath backend/.env.example -Destination backend/.env
```

Fill `backend/.env` privately with the existing database connection and OneMap
configuration. Do not overwrite an existing `.env` when upgrading. Keep the collector's
separate write-capable configuration in `data-pipeline/.env`. This backend only needs
read access to the private `parking_data` schema. No credentials belong in Flutter.

Run these in separate terminals, from the repository root:

```powershell
# Terminal 1: existing trained HDB model, no retraining.
.\backend\.venv\Scripts\python.exe -m uvicorn service.main:app --app-dir ml --host 127.0.0.1 --port 8001 --no-access-log

# Terminal 2: recommendation API.
.\backend\.venv\Scripts\python.exe -m uvicorn app:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log

# Terminal 3: Flutter web.
cd parkchoice_flutter
flutter pub get
flutter run -d chrome --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

`PARKCHOICE_MODEL_URL=http://127.0.0.1:8001` enables the probability adapter. Leaving it
blank explicitly selects the current-reading baseline. A configured but unavailable
forecast may produce a separately labelled current-only list; it never silently fills
the forecast ranking. Open `http://127.0.0.1:8000/docs` for request schemas.

## Code map

| File/folder | Responsibility |
|---|---|
| `app.py` | Validate requests and expose `/health`, `/destinations`, `/recommend`. |
| `recommendation.py` | Shortlist, route, quote, predict, check eligibility and rank. |
| `comparison.py`, `pricing.py` | Read versioned tariffs and calculate supported stay prices. |
| `onemap_adapter.py`, `onemap_auth.py` | Place search, driving/walking routes and REST token renewal. |
| `model_adapter.py`, `prediction.py` | Validate the supplied model contract and record issued forecasts. |
| `scoring.py` | Explainable provisional four-factor score. |
| `operator_auth.py` | Single operator console login from `OPERATOR_USERNAME` and `OPERATOR_PASSWORD_HASH`. |
| `pipeline_support.py` | Reuse collector helpers without duplicating ingestion; load `backend/.env`. |
| `database/` | Existing SQL schema history and dated pricing seeds; not startup scripts. |
| `validation/` | Offline tests, optional live checks and documented validation results. |

## Scope and limits

The integrated model predicts **P(at least one free car lot at arrival)** for HDB, not a
future lot count. Ranked forecasts require short-mode horizons of 15-90 minutes,
recent source data and probability at least 0.90. The original held-out horizons were
15/30/45/60/90; intermediate horizons have not each been independently validated.
Sub-15-minute and historical-profile forecasting remain disabled in app ranking.

Costs use approved supported tariff windows, not guessed missing rates. Neighbouring
minute estimates are retained as a range and the higher supported amount is scored.
Weights remain provisional: cost 40%, walking 30%, availability 20%, driving 10%.
The default shortlist is three nearby candidates, not a global optimum.

Search, current-location input, OneMap markers and external navigation are connected.
The admin tab requires operator sign-in through `POST /operator/login`. Generate the
password hash with `python backend/operator_auth.py`. Operator actions on the panel,
reporting and durable session/favourites/preferences
storage are not complete. Local HTTP service setup is not a production deployment.
No schema changes, seed replay, data collection or retraining happens when starting the API.

## Verification

From the repository root:

```powershell
.\backend\.venv\Scripts\python.exe -m unittest discover -s backend/validation -p "test_*.py" -q
.\backend\.venv\Scripts\python.exe backend/validation/validate_scoring.py
.\backend\.venv\Scripts\python.exe backend/validation/validate_probability_scoring.py
```

For the model unit tests, install `pytest` in the same environment, then run
`python -m pytest ml/tests ml/service/tests/test_service.py -q` from the root.
Lab 4 black box and basis path cases, with their results tables, are in
`validation/LAB4-TESTING.md`. Refresh the tables with `python backend/validation/lab4_report.py`.

Raw-data parity checks need the model owner's ignored datasets; the command above
intentionally selects tests that do not require those archives.

Live checks are opt-in and call real providers: `validation/run_model_workflow.py`
uses the configured database and OneMap plus temporary local API/model processes.
`validation/prospective_pilot.py` is a separate bounded capture study; do not run it as a
routine unit test. The database collector is separately operated by the model teammate.

See [the runbook](BACKEND-RUNBOOK.md), [architecture](ARCHITECTURE.md),
[model integration](MODEL-INTEGRATION.md), [database schema](../data-pipeline/SCHEMA.md)
and [collection instructions](../data-pipeline/README.md).
