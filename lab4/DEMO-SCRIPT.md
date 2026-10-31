# Android demo script

26 October 2026

## Preflight
| Check | Action |
| --- | --- |
| Device | Use the actual Android demo phone. Unlock it, enable USB debugging and confirm adb lists it as device, not unauthorized. |
| Services | Start the model on laptop port 8001 and API on 8000. Inspect model artifact health and run a genuine eligible search; health alone is insufficient. |
| USB | Run adb -s DEVICE_ID reverse tcp:8000 tcp:8000. The APK targets phone loopback port 8000; reconnecting USB may require reverse again. |
| Network | Laptop needs database/OneMap/HDB access. Phone needs internet for OneMap tiles and external navigation. Keep the USB cable connected. |
| Freshness | Rehearse and check metadata, tariff review dates and current source readings. Refresh/review through the normal owner workflow if necessary; do not disable guards for the demo. |
| Scenario | Choose a real current 15-90-minute arrival example and a short-trip example. Live availability and winners may change. Keep a second rehearsed destination. |
| Privacy | Use public sample places in recordings. Keep .env files, passwords and keys off screen; entering operator credentials should be obscured. |
| Backup | Record and review the five-minute screen video before the presentation. The script is prepared; the actual video has not been recorded by this task. |

## 15-minute live sequence
| Time | Segment | Actions | Role |
| --- | --- | --- | --- |
| 00:00-01:00 | Problem and users | Explain that the driver arrives later than the latest reading. Introduce anonymous driver search and the separate operator area. | Driver presenter |
| 01:00-02:00 | Android input | Show the actual device and one foreground GPS fix if available. For a repeatable forecast scenario, manually select NTU as the origin and Jurong East MRT as destination. | Driver presenter |
| 02:00-05:00 | Real recommendation | Select a stay duration and Best overall. Explain driving ETA to each carpark, forecast probability of at least one lot, current source timestamp, supported total-stay cost and walking route. Read actual values; do not quote fixed expected counts. | Driver presenter |
| 05:00-06:00 | Preference trade-off | Re-search using Prioritise cheaper and Prioritise closer. Explain that weights change while eligibility rules do not. A different winner is not guaranteed with every live shortlist. | Driver presenter |
| 06:00-07:00 | Map and navigation | Show OneMap attribution and start/destination/carpark markers. Open external navigation for one carpark, then return. No physical driving is needed. | Driver presenter |
| 07:00-08:30 | Short-trip fallback | Use a rehearsed short route such as Novena to City Hall. Explain the disabled sub-15-minute forecasting cohort and the separate current-reading list if fresh usable evidence exists. | Driver presenter |
| 08:30-09:30 | Recovery and scope | Show a rehearsed recoverable input/provider error. If time permits, show theme persistence or tracker UI, clearly labelling non-durable/prototype behavior. Do not present mock operator data as live monitoring. | Driver presenter |
| 09:30-11:30 | Traceability | Trace UC-01 through RecommendationController, pricing helpers, model adapter and the CTL/REQ tests. Show one overnight tariff flow graph and its actual expected/observed table. | Technical presenter |
| 11:30-13:00 | Engineering evidence | Summarize automated tests, independent basis paths, unsupported-price handling and prediction/current separation. Distinguish interface/regression checks from model accuracy and on-phone evidence. | Technical presenter |
| 13:00-14:30 | Architecture and extension | Explain Flutter -> API -> DB/OneMap/model; collection is separate. Mention canonical IDs, observation/knowledge time, prospective forecast auditing and private server credentials. | Technical presenter |
| 14:30-15:00 | Close | State implemented search benefits and remaining scope. Leave the app on a useful result screen. Keep the pre-recorded video available for network failure. | Driver presenter |

## Five-minute video plan
| Time | Capture |
| --- | --- |
| 00:00-00:30 | Problem, actual phone and anonymous search. |
| 00:30-01:15 | Select real origin/destination and duration. |
| 01:15-02:30 | Show a real forecast recommendation; explain ETA, probability, supported price and walking distance. |
| 02:30-03:15 | Re-search with a different ranking mode; show actual trade-offs. |
| 03:15-04:00 | Open map and external navigation; return safely. |
| 04:00-04:40 | Show short-trip current fallback or an honest unavailable state. |
| 04:40-05:00 | State the tested scope and close on the result screen. |

Actual device acceptance and video recording remain pending. Use the supplied phone checklist; do not infer phone success from a build.
