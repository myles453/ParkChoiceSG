# Ranking proposal and validation record

15 October 2026. Policy: `best_overall_v1_provisional`.

**17 October update:** this document preserves the original count-baseline
study. The integrated HDB classifier uses a separate probability policy with
availability penalty `1-p_free`. See [model integration](../MODEL-INTEGRATION.md)
and [its separate score study](results/probability-scoring.json); the old
count-sensitivity results must not be represented as probability-model validation.

This study verifies the proposed score's behaviour, failure handling and limited
real-API integration. It does **not** demonstrate optimal driver preferences,
trained-model accuracy or physically verified vacant lots. The weights remain a
proposed default to review with the team, even though the prototype can run them.

## Formula and rationale

For a common requested stay, let C be estimated total charge in SGD cents, H be
duration in hours, W be routed walking metres, D be routed driving seconds and A
be available lots under the request's declared basis.

```
cost penalty         = C / (C + 400 × H)
walking penalty      = W / (W + 500)
driving penalty      = D / (D + 900)
availability penalty = 1 / (1 + A)

score = 100 × [1 − (0.40 × cost penalty
                 + 0.30 × walking penalty
                 + 0.20 × availability penalty
                 + 0.10 × driving penalty)]
```

Higher scores are preferable. Cost and walking receive the largest shares because
they are direct trip trade-offs; availability matters most near full; driving
time is included with a smaller share because the route estimate is uncertain
and the candidate pool is already geographically bounded. This is a reasoned
policy proposal, not a regression fit to driver choices.

Reference points are S$4 per parking hour, 500 metres walking and 15 minutes
driving. At a reference point its penalty is 0.5. Stay cost is still displayed as
a total; the hourly reference is only a normalization scale. A per-entry tariff
is not presented as an hourly billing rule. The saturation is smooth: expensive
or long routes continue to get worse instead of all being clipped at a maximum.

Availability uses diminishing returns: increasing one lot to two matters more
than increasing 100 to 101. This avoids letting a very large carpark automatically
win because it publishes a large count. It is **not** a probability of success or
a calibrated risk measure. If the trained model later supplies reliable vacancy
probabilities or intervals, a revised policy may use them after validation.

Fixed scales avoid candidate-set min/max normalization: adding an unrelated
carpark cannot change two existing scores. Tie-breaks are score descending,
charge ascending, walking distance ascending, driving duration ascending, then
canonical agency/code. Full precision is used for ordering; displayed rounding
does not create artificial ties.

## Eligibility comes before the score

No positive score can rescue a missing required factor. The workflow excludes
failed driving/walking routes, unquoted or ambiguous prices, available/capacity
inconsistency and nonpositive availability for the declared basis.

Pending model mode uses fresh source-timestamped current counts only, with an
explicit `current_availability_baseline` label. It does not promote LTA/URA
retrieval times into source-update times. With a ready model, the whole request
switches to prediction basis. Invalid identity/target/time/value fields, a history
cutoff over 15 minutes old, insufficient metadata and low confidence are rejected
or excluded. A failed forecast is not replaced by a current count in the same
ranking. A currently full carpark is not excluded solely for being full in
prediction mode; its valid future forecast decides availability eligibility.

These gates deliberately reduce coverage. They cannot certify that a high/medium
confidence label was statistically calibrated; the model owner must provide that
evidence. The 15-minute input age and low-confidence exclusion are proposed
operating policies to revisit against measured forecast coverage/error.

## Mathematical and synthetic checks

`validate_scoring.py` uses seed 20261015 and writes
`results/scoring-validation.json`. In the checked domain, it ran:

| Check | Extent | Result |
|---|---:|---|
| Random bounded input cases | 20,000 | Scores stayed within 0–100. |
| Bounds, each-factor monotonicity, dominance and candidate-set independence | 140,000 property comparisons | No violations. |
| Invalid negative, boolean, missing, NaN or infinite fields | 8 cases | All rejected. |
| Relative weight perturbations, independently within ±20%, then renormalized | 25,000 scenario trials | See sensitivity findings below. |
| Lot-count perturbations, independently within ±3 lots | 5,000 scenario trials | Shows dependence on forecast error near full. |
| Reference-scale perturbations within ±20% | 25,000 scenario trials | Default scenario winner stayed stable in these examples. |

Cost sampling spans 0–20,000 cents; stay durations are 15, 30, 60, 120, 240 and
1,440 minutes; walking spans 0–5,000 metres; driving spans 0–7,200 seconds; available
lots span 0–1,000. These broad synthetic ranges test score behaviour, not the live
shortlist limits. At zero lots, the pure function remains defined but the workflow
excludes that candidate before ranking.

The monotonic direction also follows analytically: for positive reference r,
the derivative of x/(x+r) is r/(x+r)² > 0; the derivative of 1/(1+A) is negative.
Thus worse cost/walk/drive cannot improve a score, and more available lots cannot
reduce it. This says nothing about whether the chosen weights represent drivers.

## What sensitivity exposed

| Designed situation | Default scores / decision | Perturbation finding |
|---|---|---|
| One option better in every factor | Better 78.75, worse 49.87 | Better won all 5,000 weight trials. |
| Cheap but 1,000 m walk versus costly but 200 m walk | Cheap/far 65.82, middle 64.61, costly/close 64.25 | Cheap/far won 3,883/5,000; costly/close won 1,117. Close trade-offs are preference-sensitive. |
| One space nearby versus 20 spaces with a longer walk | More spaces 72.32, one space 69.70 | More spaces won 4,941/5,000 weight trials, but only 616/1,000 lot-perturbation trials. Near-full forecasts need particular scrutiny. |
| Five spaces nearby versus 200 with a longer walk | Nearby 76.36, large/far 69.71 | Nearby won all tested weight, scale and count perturbations. Large counts did not dominate by themselves. |
| Equal factors | Equal scores | Canonical tie-breaking decides; simulated independent lot noise can change the winner. |

These are constructed trade-offs, not labelled human decisions. We did not tune
the weights merely to force a desired winner in every example. A score gap is not
confidence and must not be presented as a probability that the top choice is best.

## Real API/data checks

The resumed database accepted a new collection cycle:

| Source | Capture (UTC) | Accepted rows | Notes |
|---|---|---:|---|
| HDB | 02:58:34 | 2,425 | 3 rows rejected; source freshness and zero-capacity flags retained. |
| LTA | 02:59:29 | 2,608 | 6 pages; 2 undocumented/invalid rows rejected. |
| URA | 03:00:01 | 154 | 3,960 detail/rate rows captured; 657 partial calculators, unresolved windows still blocked. |

`run_live_workflow.py` then exercised public sample trips. The City Hall trip used
an actual localhost HTTP request; the other two called the same service directly.

| Destination | Outcome | Measured elapsed time |
|---|---|---:|
| City Hall | BBB, WCB, ACB all had routes and supported quotes; provisional order BBB → WCB → ACB. | 10.578 s including local server startup |
| Orchard | No eligible shortlist under the strict source-timestamped current-reading policy. No result was invented. | 5.313 s |
| Jurong East | J57, J4, J1 all had routes and supported quotes; provisional order J57 → J4 → J1. | 9.516 s |

City Hall: BBB quoted 240 cents for 60 minutes, drive 484 s, walk 556 m; WCB 240
cents / 440 s / 954 m; ACB 280 cents / 422 s / 1,279 m. Jurong East: all three
quoted 240 cents for 120 minutes; J57 walked 438 m, J4 721 m and J1 812 m.
For each of the two successful trips, its default top stayed first in all 1,000
tested relative-weight perturbations. This is limited stability evidence for two
specific snapshots, not general optimality or a held-out ranking accuracy score.

The availability readings were provider-reported counts and the model was
pending. The times are not a p95 latency study. The prototype does not meet an
assumed universal three-second target, and no such result is claimed.

## Integration checks and remaining validation

The final checks passed 93 existing Python tests and 27 new workflow/API/token/
forecast tests (120 total), plus four Flutter tests. Flutter static analysis was
clean, the web target built successfully, package dependency checks passed and
the changed/new code scan found no configured credentials. The OneMap renewal
path was also exercised against its real token endpoint by forcing only the
local cache expiry and confirming reuse of the replacement.

The separate workflow/API tests cover unavailable prices, failed routes, full or
stale readings, proxy timestamps, wrong model identity, future/stale history,
over-capacity forecasts, low confidence, common departure times, ambiguous
minute approximations and safe HTTP error output. Authentication tests cover
expiry-based renewal, cache reuse, concurrent renewal and bounded retry.

Flutter tests cover location selection, discarding coordinates after edits,
posting the selected values, total-stay cost rendering, pending-forecast labels,
anonymous entry, navigation and theme switching. Backend and Flutter checks are
kept separate from the application's scoring functions.

Before claiming validated arrival recommendations, the team still needs:

1. A held-out arrival-time model evaluation against persistence, including
   errors and coverage per horizon/carpark/source and behaviour near full.
2. Calibration evidence and agreed thresholds for confidence/fallback policies.
3. A labelled preference set: give target drivers pairs or shortlists with real
   factor values, record their choices and compare this score with alternatives.
   Tune on one subset and evaluate on another; do not call hand-designed scenario
   agreement or API response success “ranking accuracy”.
4. Operate the provided prospective logger/outcome matcher with the real model,
   audit known-at cutoffs and label tolerance, and report missing later readings
   alongside matched errors. The presence of this tooling is not an evaluation.
5. More destinations, peak/weekend periods, route timing/entrance checks and
   supported tariff boundary cases. Published points are not verified entrances;
   OneMap duration is not established as live-traffic-aware.

The candidate pool is a bounded nearby shortlist, not every carpark in Singapore.
The default UI requests three within 1.5 km. Some eligible carparks outside that
pool may be preferable. Universal tariff coverage, exact-second billing,
physical price/vacancy verification and a production deployment are not provided
by this study.
