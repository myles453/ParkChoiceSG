# Trained model integration â€” 17 October 2026

## Workflow completion update

Current-location input, an attributed OneMap map and external navigation are now
connected and verified in Flutter web using a simulated public location. The
new separate current-reading fallback handles unsupported short trips without
inventing a forecast or mixing counts into probability scores. The inference
service shares validated cached source readings through `/current`.

A bounded prospective study issued 576 forecasts and matched 297 later source
observations. Findings were mixed and coverage incomplete; short/profile forecast
ranking remains gated. See [the pilot](validation/SHORT-TRIP-PILOT.md).

Price estimates may now display a range when two supported neighbouring-minute
quotes differ under the same schedule/payment; scoring uses the higher estimate.
An unsupported neighbour or mismatched schedule still withholds the cost.
The original integration record below is retained as history where noted.

Fetched upstream main at `d05c1f8`. Imported the new `ml/`, `ml_lta_ura/` and
published `data-pipeline/` directories without merging over unrelated local work.
This integration is published under the permanent `backend/`, `ml/` and
`parkchoice_flutter/` working directories. Academic submission artifacts remain separate.

## Model artifacts

| Component | Meaning | Application use now |
|---|---|---|
| `ml/models/short_horizon.joblib` plus statistics/calibrator | HDB classifier for **P(at least one free car lot on arrival)**. It does not predict a lot count. | Connected through the existing `ml/service` HTTP endpoint. |
| `ml/models/profile.parquet` | Historical probability by HDB carpark, day type and 15-minute slot. The service can use it for later arrivals or stale/missing live readings. | Explicitly excluded from ranking in this integration, pending separate fallback evaluation. |
| `ml_lta_ura/models/variant_a.joblib` | Retrieval-time model trained on HDB-style data and evaluated experimentally on real URA/LTA captures. | Retained locally, not connected to the HDB inference service. URA needs its own inference/history adapter and broader validation. |
| `variant_b.joblib` | Adds a trailing-count feature needing substantial live history. | Not selected. Variant A is selected for application inference. |

The URA transfer evaluation covers normal **weekdays** only. The LTA report has
only 60 normal "not free" rows from three carparks and calls that verdict
provisional; its README recommends showing current readings. We must not describe
LTA forecasting as established. The HDB probability ranking does not silently
mix those agencies or current-count fallbacks into its scores.

## What changed

- `model_adapter.py` calls the supplied `/predict` service. No duplicate feature
  builder, training routine or replacement model was added to the app backend.
- The backend keeps exact canonical HDB identity, arrival and the service's
  actual issue time. It rejects invalid probabilities, stale history, changed
  identity/target, failed model status and profile fallback.
- Current integration supports request horizons **15â€“90 minutes**. The supplied
  held-out report evaluates discrete horizons 15/30/45/60/90. Intermediate
  horizons can be inferred but have not been independently evaluated here.
  Trips below 15 minutes require validation before enabling; they return an
  explicit unavailable status, rather than a made-up forecast.
- `p_free` is stored separately; `available_lots` remains null for classifier
  forecasts. The service supplies no per-forecast sample count, so none is invented.
- The app shows current reported lots separately from the percentage chance of
  finding at least one free lot. High/Medium/Low are **probability bands**, not
  uncertainty intervals or guarantees.
- Ranking requires probability at least **0.90**, using the current model card
  and README. High starts at 0.99; Medium starts at 0.90.
- The provisional score retains 40% cost / 30% walking / 20% availability / 10%
  driving. Probability mode uses availability penalty **`1 - p_free`**, not the
  previous count penalty `1/(1+lots)`. Its distinct version is
  `best_overall_probability_v2_provisional`.
- Issued probabilities are logged before arrival with model/history timestamps.
  The matcher uses **Brier score** against `actual_lots >= 1`, and compares the
  current-reading persistence baseline on the same matched subset. Count MAE is
  retained only for the older count-predictor interface. Source-time and
  retrieval-time outcome groups remain separate.
- Small Windows compatibility fixes allow the training module to import without
  Unix `resource`, and permit asyncio's internal loopback socket in service tests.
  The trained artifacts and learned parameters are unchanged.

## Verification and limits

The committed HDB artifacts loaded and produced real forecasts using the live
HDB feed. A localhost HTTP integration check combined OneMap routes, supported
database tariff quotes, the real classifier and ranking for a public trip to
Jurong East. The first check ranked J57 (S$2.40 for 120 minutes, 1,261 seconds
drive, 438 metres walk, `p_free` about 0.99983); J56's probability about 0.05686
was excluded. Results change with time; see the latest machine-readable
[integration result](validation/results/model-integration.json).

The model's own offline tests passed locally: 107 tests covering the dataset,
training helpers and inference service. Our workflow/auth/model integration
suite passed 34 checks. The raw-data parity tests require the model training workflow's ignored
`ml/data` files and **were not run**; reported held-out accuracy was read from
the recorded model evaluation report, not independently reproduced. Windows LTA/URA collection
uses the existing cross-platform pipeline; the experimental `ml_lta_ura/collect.py`
still imports Unix `fcntl` and is not the Windows collection entry point.

A separate probability-score study checked 20,000 generated cases (120,000
property comparisons) without mathematical violations, plus 15,000 weight
perturbations and 15,000 probability perturbations. It exposes a real policy
trade-off: a 91% nearby option and a 99% farther option can swap rank under small
weight changes. Values near the 90% eligibility threshold can enter/leave the
ranking under modest forecast error. These are sensitivity findings, not proof
of optimal weights or new model accuracy. See
[probability score results](validation/results/probability-scoring.json).

Two details to resolve with the model owner:

1. `ml/reports/evaluation.md` still describes a **0.5** free threshold, whereas
   the current artifact card/README use **0.9**. Probability/Brier results are not
   affected by a classification threshold, but threshold-specific counts and
   claims need regenerating or clearly labelling as historical.
2. Validate sub-15-minute trips, profile fallback, forecast coverage and ranking
   outcomes on later real observations. URA needs an inference adapter and
   representative weekend evidence; LTA needs more negative outcomes.

## Run it

Use the two local services and configuration described in
[BACKEND-RUNBOOK.md](BACKEND-RUNBOOK.md). Configure the private `.env` with
`PARKCHOICE_MODEL_URL=http://127.0.0.1:8001`; start the model service before using
recommendations. No service is left running by the verification script.

From the repository root, repeat the real integration check with:

```powershell
.\backend\.venv\Scripts\python.exe backend/validation/run_model_workflow.py
```

This starts and stops temporary localhost services, makes bounded real API calls,
reads the existing database, and records genuine forecasts locally. It does not
start periodic collection or retrain the model. Later outcome matching depends
on the separate collector continuing to save observations to the database.
