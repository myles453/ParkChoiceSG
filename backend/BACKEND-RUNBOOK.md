# Run the recommendation backend

## Trained HDB model (17 October integration)

Model source and artifacts are in `ml/` and `ml_lta_ura/`.
See [MODEL-INTEGRATION.md](MODEL-INTEGRATION.md) for scope and validation.
The application reuses the supplied HDB inference service on localhost port 8001.
It predicts **P(at least one free lot)**, not a future number of lots.

First create the backend environment and private configuration from the repository root:

```powershell
py -3.12 -m venv backend/.venv
Copy-Item -LiteralPath backend/.env.example -Destination backend/.env
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
```

Fill `backend/.env` privately; the example has no credentials. Do not overwrite an existing
`.env` when upgrading. The collector continues using its own `data-pipeline/.env`.

From the repository root, install the verified inference dependencies, then run
the model service in its own terminal:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r ml/requirements-inference.txt
.\backend\.venv\Scripts\python.exe -m uvicorn service.main:app --app-dir ml --host 127.0.0.1 --port 8001 --no-access-log
```

Set `PARKCHOICE_MODEL_URL=http://127.0.0.1:8001` in the private
`backend/.env`, then start the recommendation backend below in a second
terminal. Leave that setting blank to choose the explicit current-reading
baseline. A configured but unavailable forecast can produce a separately labelled
current-only list; the forecast ranking is never silently filled with current counts. Neither command retrains models
or starts the team's database collector.

## Backend

Use Python 3.12 in `backend`. Create a fresh environment for this checkout.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8000 --no-access-log
```

Open `http://127.0.0.1:8000/docs` for the three endpoints:

| Endpoint | Input and output |
|---|---|
| `GET /health` | Process liveness, `prediction_configured` and output kind. Configuration does not prove model-service or feed health. Check the model service's own `/health` for artifact loading. |
| `POST /destinations` | `{"query":"City Hall MRT"}` Ã¢â€ â€™ choices with address and coordinates. Select the intended place. |
| `POST /recommend` | Selected origin/destination coordinates, duration and bounded shortlist settings Ã¢â€ â€™ routes, cost evidence, current/predicted counts, exclusions and provisional ranking. |

Sample request uses public locations, not a saved driver's location:

```json
{
  "origin": {"latitude":1.3197,"longitude":103.8421},
  "destination": {"latitude":1.2932,"longitude":103.8520},
  "duration_minutes":60,
  "candidate_limit":3,
  "radius_meters":1500
}
```

Private configuration is loaded from `backend/.env`:

- `DATABASE_URL` connects to the existing private Supabase schema.
- `ONEMAP_ACCESS_TOKEN` supports manual-token mode.
- `ONEMAP_EMAIL` and `ONEMAP_PASSWORD` together enable automatic token renewal
  and take precedence over the manual token. The server caches the returned token
  in memory, renews within 60 seconds of its expiry, and retries authentication
  once after a rejected token. It does not write the replacement into `.env`.
- LTA/URA keys are needed for collection, not individual recommendation requests.
- `PARKCHOICE_MODEL_URL` connects the supplied HDB model service when set.

If data or URA rates need refreshing, run one `collect_live.py` cycle from the separate `data-pipeline/` folder using its private collector configuration.
Periodic collection is operated separately. Do not start a
second periodic instance from another machine. HDB/operator policy expiry is
independent of availability refresh; collection does not automatically approve
new commercial tariff facts.

Without a model, `prediction_status=prediction_pending` and
`ranking_basis=current_availability_baseline`. Only fresh source-timestamped
counts enter that baseline. A recent retrieval proxy is not silently promoted
to confirmed source freshness. An empty ranking is a genuine outcome.

## Flutter

The active source for this work is `parkchoice_flutter/` at the repository root.
Both Flutter copies were identical before this integration. The copy under
`lab 3/` is unchanged and should not be used to demonstrate this new workflow.

This prototype was checked with Flutter 3.47.2 / Dart 3.13.2. The Python backend
uses Python 3.12 with the pinned API requirements.

```powershell
flutter pub get
flutter run -d chrome --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

For an Android emulator use `http://10.0.2.2:8000` as `PARKING_API_URL` instead.
The debug Android manifest permits local HTTP; an eventual release should use
the deployed HTTPS endpoint. No database/provider keys belong in Dart defines.

Search and select a starting place, search and select a destination, select the
parking duration and tap **Find carparks**. The screen opens without registration,
shows real API results and uses total stay cost rather than fictitious hourly
rates. Editing a selected place clears its saved coordinates. GPS acquisition,
navigation handoff and OneMap display are now connected: **Use current location**
requests one foreground fix, **View map** displays markers, and **Navigate to
carpark** opens an external directions URL. Refresh device fixes older than two
minutes. Android requests coarse/fine location; web location requires a secure
context (localhost works for local testing). Permission denial leaves place search
available. No background tracking is added. Session actions remain prototype work.
Other screens remain the team's existing prototype work.

## Model boundary

`HdbModelClient` now implements the boundary using the model service's `/predict`
endpoint. It restricts the shortlist to HDB, keeps the model's actual issue time,
validates identity, arrival, probability and recent history, and preserves the
service's high/medium/low probability bands. No per-forecast sample count is
invented. Only short-mode forecasts for request horizons 15Ã¢â‚¬â€œ90 minutes enter this
integration. Historical profile fallbacks remain excluded, and probability below
0.90 is visible but not ranked. The shorter and intermediate horizons have not
been independently validated by this integration; original test horizons are
15/30/45/60/90 minutes. Forecast accuracy is not a guarantee of a free bay.

In probability mode, the availability penalty is `1 - p_free`, with the other
three penalties and provisional weights unchanged. The response identifies
`arrival_free_probability` and `best_overall_probability_v2_provisional`.
The client displays a percentage chance and the current lot count separately.

The model service also exposes `POST /current` for its cached HDB source readings.
The backend checks source time and counts rather than depending on the database
collector's cadence for current fallback. Only valid positive source-timestamped
readings no older than 15 minutes enter that list. If no forecast ranks,
`fallback_ranked` may contain current-only options and `fallback_notice` explains
the basis. `ranked` and `top_recommendation` remain forecast-only. A known low
probability, unsupported price, missing route or stale/proxy reading is never
promoted through this fallback.

When the two neighbouring-minute tariff quotes use the same supported schedule
and payment method, the response keeps `amount_min_cents` and `amount_max_cents`,
scores the higher estimate and displays the range if it differs. This is an
explicit minute-precision approximation, not guaranteed exact-second billing.
If either quote is unsupported or its schedule/payment differs, no numeric cost
is used for ranking.

The bounded short-trip study is documented in
[SHORT-TRIP-PILOT.md](validation/SHORT-TRIP-PILOT.md). Its one-time mixed evidence
does not enable sub-15-minute or profile ranking. Repeat the study only when a
new real prospective capture is desired; it runs for up to roughly twenty minutes.

The following count-model contract is retained for a future count predictor and
the existing offline checks; it is not the contract of the shipped classifier.

Implement `AvailabilityPredictor` in `prediction.py` with `ready=True` and a
`predict(PredictionRequest) -> Prediction` method. Assign that adapter to
`app.state.predictor` in the application's startup code in place of
`PendingPredictor`. Keep model loading inside the adapter, once per process.

The count-model request carries exact canonical agency/code, issue time and target arrival.
The adapter owns inference feature construction from the agreed history; the
backend does not guess how the trained model encodes carparks or forecast
horizons. Access only history known by `issued_at`. Return unsupported-horizon,
unseen-carpark or insufficient-history statuses explicitly.

An `ok` prediction must echo identity/issue/target times and supply finite
nonnegative lots, calibrated `high`/`medium`/`low` confidence, model version,
positive sample count and a timezone-aware history cutoff no later than issue
time and within 15 minutes. That freshness rule is project policy to review with
the model owner. Low-confidence values stay visible but are excluded from final
prediction ranking. Do not invent confidence from sample count. The current
count baseline is never substituted into a mixed prediction ranking.

Valid model forecasts are appended before their target time to the ignored
`data/forecasts/issued.jsonl`, with identity, issue/target/history times, version,
confidence, sample count and the available current-reading baseline. No personal
origin or destination is logged. An audit-write failure or target that already
passed excludes the forecast from ranking. Pending placeholders are not logged.

After later observations arrive, run from `backend`:

```powershell
.\.venv\Scripts\python.exe validation/match_forecasts.py
```

The tool matches the first later provider observation within five minutes of the
target, retains pending/unmatched forecasts and separates source-time labels
from retrieval proxies. For probability forecasts it reports Brier score against
`actual_lots >= 1`, with persistence Brier on the paired baseline subset. Count
forecasts retain model MAE, and model/baseline MAE on the same
paired subset where a valid baseline exists. The audit is for the local
single-process prototype; it is not durable shared production storage. Held-out
error/coverage evaluation and confidence calibration still need the model owner.
Matching the interface is not proof that the model is valid.

## Verification

```powershell
# From backend
.\.venv\Scripts\python.exe -m unittest discover -s validation -p "test_*.py" -q
.\.venv\Scripts\python.exe validation/validate_scoring.py
.\.venv\Scripts\python.exe validation/validate_probability_scoring.py
.\.venv\Scripts\python.exe validation/run_model_workflow.py
.\.venv\Scripts\python.exe validation/run_live_workflow.py
```

From the active Flutter folder, run `flutter analyze` and `flutter test`.
The live benchmark starts a temporary localhost API for one HTTP request, stops
it afterward, and checks two more public sample destinations through the service.
Full results stay in ignored `data/workflow-validation`; a shareable summary is
written to `backend/validation/results`. A later run can legitimately differ as
availability, rates, source freshness and routes change.
