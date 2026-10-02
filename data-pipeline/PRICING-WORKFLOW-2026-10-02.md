# Verified collection and pricing workflow — 2 October 2026

The private Supabase Session pooler connection works. All three direct Python loaders have completed successfully. No new tables or public permissions were needed for this continuation.

From `ParkChoiceSG/data-pipeline`, run:

```powershell
.\.venv\Scripts\python.exe collect_live.py
.\.venv\Scripts\python.exe check_comparison_readiness.py --arrival-in-minutes 30 --duration-minutes 60
```

Normal collection refreshes URA tariff data when the last runtime-compiled capture is more than one day old. `--include-rates` forces a refresh; `--availability-only` explicitly skips it. Each provider's load is atomic. A failure in the URA pricing import rolls back that provider's availability and metadata load too; earlier successful providers remain committed.

URA source checksums are validated before parsing. Supported motor-car per-unit windows and corroborated standard night caps become calculator rules. Missing, zero/zero, ambiguous and unsupported windows block affected quotes. New captures close earlier versions; replaying an already imported runtime capture adds no schedules. Older unseen captures cannot replace newer pricing. Tariff capture time is when the provider response was retrieved, not a claimed provider publication/effective date.

HDB schedules now retain the original tariff-relevant reference flags from the checksum-verified September 30 seed archive. Changed flags block the old price. Unchanged refreshed flags can satisfy reference freshness, while the independent policy-review expiry remains unchanged. The latest reference matched all 2,122 schedule baselines.

## Live verification

Latest availability captures:

| Provider | Run ID | Retrieved at (Singapore) | Accepted observations |
|---|---|---|---:|
| HDB | `5e3be12e-e779-4100-a773-9a5ba7763d56` | 2 Oct, 19:11:29 | 2,425 |
| LTA | `171894e7-7f4c-4152-8f75-1d20e1105167` | 2 Oct, 19:12:29 | 2,606 |
| URA | `8615d5bc-ef19-466b-9aa8-9d3a309a4855` | 2 Oct, 19:13:04 | 154 |

HDB's latest archive includes 1,751 usable car observations under the strict training rules. These figures are snapshots, not sufficient history for training.

Latest compiled URA tariff capture: `3869a21b-e5fe-4b23-990a-7ec131224a8f`. It loaded 658 schedules: 657 partially supported and one pending review. The prior runtime capture is superseded. A database replay check confirmed no new schedules, no inverted validity intervals, no duplicate open URA schedules and no daily refresh currently due.

At 19:14:32 Singapore time, quotes for arrival at 19:44 and a 60-minute stay gave:

| Agency | Stored supported calculators | Quotes for this stay | Principal unavailable cases |
|---|---:|---:|---|
| HDB | 2,122 | 2,073 | 42 outside supported parking hours; 7 fractional-cent results; other identities lack short-term parking/reference or are loading bays |
| URA | 657 partial | 430 | 227 unresolved time windows; 100 identities without an approved calculator |
| LTA commercial | 12 partial | 11 | 28 without approved operator prices; IMM needs first-entry status |

There were 1,420 candidates under the existing strict price-comparison policy. This policy requires a fresh source-update timestamp; recent LTA/URA retrievals remain labelled `recent_retrieval_only` and are not accepted by that flag. A product decision on using retrieval proxies must be explicit. Price calculation itself is available independently of that flag.

79 unit tests pass. Live imports verified both the original and batched loader; all 19 private tables have RLS and neither client role has SELECT access. The `.env` remains excluded from Git.

## Remaining limits

This fixes automatic URA tariff storage and the direct collection path. It does not provide universal pricing coverage. HDB policy and commercial operator prices need separate source reviews; an availability response does not supply those prices. Observed-holiday interpretation, fractional-cent billing, some long-stay caps, conflicting operator tariffs and unknown windows remain guarded. The calculator does not silently substitute zero cost.

To rank carparks at arrival, the backend must supply each candidate's actual route-derived ETA, the requested parking duration, walking route, prediction and model confidence. Pass that candidate's ETA to the calculator; a common ETA used for this smoke test is not a substitute for candidate-specific routes. Arrival recommendations remain disabled until those integrations exist. Regular collection and sufficient chronological history are still required for model training.
