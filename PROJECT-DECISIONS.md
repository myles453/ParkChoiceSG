# Design rationale

## Arrival-based comparison

Current free-lot readings can change during travel. Each candidate receives its
own arrival target from a routed driving duration. The HDB classifier estimates
the probability of at least one free car lot at that target. Current readings
remain visible evidence; a separately labelled current-only fallback is used
when permitted rather than being presented as a forecast.

The enabled integration accepts HDB short-mode horizons of 15-90 minutes with
coherent source times, model metadata and probability at least 0.90. Experimental
LTA/URA models and historical-profile forecasts are excluded from app probability
ranking. Prediction does not reserve a space or guarantee physical availability.

## Shortlisting and routes

PostgreSQL filters canonical location/facility/tariff evidence using a destination
bounding box. Python applies Haversine distance and selects the nearest three
within 1.5 km by default. OneMap supplies driving and walking routes for those
candidates. Straight-line distance is not displayed as routed walking distance.
Rejected candidates are not automatically replaced, so this is a bounded
comparison rather than a global optimum.

## Supported prices

The pricing engine calculates a whole stay using versioned, reviewed integer-cent
rules: day/time windows, billing increments, grace, tiers and supported caps.
Unknown prices remain unavailable. HDB/commercial reviews expire after 30 days;
URA tariff evidence expires after two days. Arrival times are checked at both
neighbouring whole minutes, and the higher supported amount is scored while the
range and approximation remain explicit.

## Three scoring modes

Default cost/walk/availability/drive weights are 40/30/20/10. Cheaper uses
65/15/15/5; Closer uses 15/65/15/5. Closer prioritises walking from carpark to
destination. All modes retain the same eligibility gates. Fixed reference scales
make units comparable and expose weighted penalties in the response. These are
explainable project-policy defaults, not experimentally optimal preferences.

## Process and data boundaries

Flutter handles interaction, foreground GPS, OneMap tiles and external navigation.
FastAPI coordinates adapters and short database read stages. Private credentials
remain server-side. The inference service loads committed artifacts and maintains
recent HDB history. A separate collector archives and ingests provider data;
search does not start collection or retrain the model.

Canonical identity is `(agency, carpark_id)`. Observation and retrieval times are
distinct. LTA copies of HDB/URA series are not independent observations. The
shipped HDB model uses a historical backfill/file training path; the PostgreSQL
export is an additional interface rather than its exclusive training source.

## Testability and scope

Routing and prediction Protocols allow controlled test doubles. Tests cover input
validation, error statuses, audit failure, price boundaries and ranking/fallback
gates. Flutter tests exercise duplicate navigation, late completions, invalid
responses, GPS failures and repeated screen/modal sequences. Model probability
quality is evaluated separately through chronological splits, persistence
baselines, calibration and coverage.

Drivers have no accounts. Operator credentials are checked server-side, but the
app's in-memory flag is not a server authorization system. Console sample actions
do not persist reports or operational overrides. Only appearance persists in the
current preference controller. Sessions, history, saved labels and erasure retain
the partial behavior documented in the final models PDF.

Voice control, payments, reservations, durable driver profiles and public-service
deployment are outside the connected application baseline.
