# Database refresh — 2 November 2026

The reported search failure was reproduced against the running backend. All
2,122 previously active HDB policy schedules and 12 commercial schedules had
passed their 30-day review limit. A Jurong East search returned
`no_eligible_candidates`; J57 and J56 had valid predictions but were rejected with
`price_policy_stale`. URA prices also needed a fresh capture under their separate
two-day limit.

## Completed refresh

| Data | Result |
|---|---|
| HDB facility reference | 2,273 current records loaded. One older record absent from the current source remains stored for history. |
| HDB availability | Latest pull accepted 2,425 rows, rejected 3; 1,851 car rows met training-quality checks. Source-stale and unmatched rows retain their quality flags. |
| LTA availability | Latest pull accepted 2,613 rows over 6 pages, rejected 2. Agency split: HDB 2,416; LTA 40; URA 157. |
| URA availability | Latest pull accepted 159 rows, rejected none. |
| HDB tariffs | 2,124 freshly reviewed schedule versions and 35,008 rules inserted from current official policy and current facility flags. |
| URA tariffs | 3,959 source rate rows captured; 658 schedule versions compiled: 657 verified with guarded partial coverage, 1 pending review. |
| Commercial tariffs | 12 new reviewed versions loaded from current official operator pages; ambiguous windows remain blocked. |
| Holiday calendar | All 14 stored 2026 dates matched the published MOM calendar, including the 3 observed dates. Review evidence renewed; observed-day parking treatment remains guarded. |

Latest availability captures occurred around 22:38–22:40 Singapore time. Tariff
reviews/capture occurred around 22:24–22:37. Existing observations, old tariff
versions and raw source captures remain available; no tables were recreated and
no freshness limits were relaxed.

HDB tariff amounts, caps and central/peak cohorts matched the current
[HDB charging page](https://www.hdb.gov.sg/parking/other-parking-matters/shortterm-parking/shortterm-parking-charges).
The EPS, coupon/Parking.sg and free-parking pages were also reviewed. Comparing
the new compiler with stored rules found 2,119 identical existing rule sets.
TH24, TH32 and TH33 now have Sunday/PH free-parking rules reflecting their fresh
reference flags; two additional eligible facilities receive tariffs.

## Ambiguous prices retained as unavailable

- Lot One weekend/PH 00:00–03:00: the main price table and FAQ give different
  initial charging treatment. Those windows now block a quote.
- CQ @ Clarke Quay Mon–Thu 18:00–21:00, excluding PH/eve: the main table ends the
  free-parking promotion in December 2026 while the FAQ ends it in June. This
  window remains unquoted. The undisputed Mon–Fri lunch free-parking window is
  represented explicitly; unsupported crossings into/out of it remain guarded.
- Tampines Mall weekend/PH daytime initial-duration conflict remains blocked;
  PH-eve daytime category ambiguity is also guarded.
- IMM still requires first-entry status for an exact quote. Other missing operator
  tariffs, unresolved URA windows, restricted loading bays and unsupported holiday
  interpretations remain unavailable rather than being treated as free.

## Verification

- All 151 existing backend tests passed.
- 27 additional monetary examples checked ordinary prices, initial-hour tiers,
  grace, lunch free parking, midnight billing, first-entry status, conflict
  blockers, PH-eve rules and observed-holiday guards. The initial 22 checks ran
  before the commercial import; five further holiday checks passed afterward.
- Database reads confirmed **zero stale active verified schedules** and zero
  duplicate open schedules for the same agency/carpark/source.
- Live `POST /recommend` succeeded in `best_overall`, `cheaper` and `closer` modes
  using real OneMap routes, database tariffs and the running HDB model service.
  J57 and J56 each had supported one-hour quotes of 120 cents and ranked results.
  J58 remained excluded because the model does not support that carpark, rather
  than because of its price.
- A one-hour, near-term price audit across all 3,081 canonical identities found no
  `policy_stale`, `rate_capture_stale`, `reference_stale` or `hdb_reference_changed`
  quote results. At the tested late-evening arrival it produced 1,842 HDB, 11 LTA
  and 144 URA quotes. Other results reflect actual coverage/permission limitations;
  these counts are not an assertion of universal price coverage or model coverage.

No Flutter changes or phone-level testing were needed for this database repair.
The prediction model was neither retrained nor replaced.

## Audit evidence and recurrence

Local evidence is under `backend/data/refresh-20261102/` (ignored by Git). It
contains rendered HDB source captures, compressed operator/MOM source pages and
checksums, before-import schedule records, import reports, database/coverage
audits and live ranking-mode results. Provider raw archives and manifests are
under `data-pipeline/data/<run_id>/`.

Final availability run IDs:

- HDB: `8f205be1-e41f-4057-9632-8ea493202a2d`
- LTA: `532a9f12-5fab-4c82-92c1-0a15ef165148`
- URA availability: `38f8f831-10bb-4071-bd07-ce97bad28dc3`
- URA rate capture: `128ece83-7b62-43c7-bb20-de8c79ebb4f5`

Keep the existing periodic availability collection running. Run the price-capable
live collector daily for URA. Review HDB and commercial policy pages again
**before 2 December 2026**; a training-only availability loop does not renew those
policies. This maintenance run performed bounded collection cycles and did not
install a new scheduler or start an indefinite collector.
