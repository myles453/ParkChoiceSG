# Prospective short-trip pilot — 17 October 2026

The supplied HDB classifier was loaded unchanged. Before outcomes arrived, we
issued 576 forecasts at 5, 10 and 15 minutes across 192 sampled carparks: 60
currently full, 42 near full (free/capacity below 10%), 60 other free and 30 with
stale readings using profile mode. The sample was stratified with seed 20261017;
it is not population weighted. Warm-up/history and prediction used only readings
available at issue. No training or calibration used the outcomes.

The bounded study polled the live feed once per minute. A label had to have a
genuine HDB source timestamp at or after target, within five minutes, and no
later than its retrieval/knowledge time. We retained missing labels as unmatched.
There were 297 matches and 279 unmatched forecasts; coverage is a material limit.

| Horizon | Matched short-mode forecasts | Model Brier | Persistence Brier |
|---|---:|---:|---:|
| 5 minutes | 137 | 0.05599 | 0.08759 |
| 10 minutes | 112 | 0.07464 | 0.08929 |
| 15 minutes | 7 | 0.04782 | 0.14286 |

These are pooled matched subsets of the convenience sample, not general model
accuracy estimates. The 15-minute row has too few matches to interpret. Profile
mode is reported separately in [the complete results](results/short-trip-pilot.json)
and does not have a fresh-current persistence baseline.

Performance was mixed across groups. For example, the 5-minute near-full group
had model Brier 0.07248 versus persistence 0.06452, while the 5-minute initially
full group improved from 0.18868 to 0.09951. Carparks and horizons are correlated;
this is one issuance/time window and no statistical generalization is claimed.

**Decision:** keep sub-15-minute predictions and historical-profile ranking gated.
Provide an explicitly current-reading fallback where supported, then collect more
issuances across day types, demand levels and clock hours before changing policy.
The pilot does not establish traffic-aware ETA accuracy or a calibrated uncertainty
interval. Brier evaluates the probability of at least one lot, not future lot-count MAE.

The raw issued forecasts/outcomes remain in the ignored
`data-pipeline/data/short-trip-pilot/` directory. The script is reproducible but
another run makes new real forecasts and waits for later observations; results
will differ. It does not write to the shared database or start periodic collection.
