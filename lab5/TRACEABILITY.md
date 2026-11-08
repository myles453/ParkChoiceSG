# Final requirement traceability

| Requirement | Source | Executable evidence | Status |
|---|---|---|---|
| UC-01 recommendation/modes | Backend recommendation, scoring, comparison, pricing; Flutter search/API | Backend workflow, controller, ranking, pricing and fallback suites; Flutter search/response suites | Connected with documented model/price/route limits |
| UC-02 information | Result cards and API payload | Flutter search/response suites | Cards implemented; full separate detail screen deferred |
| UC-03 navigation; UC-19 map | Map screen, navigation handoff, device location | Flutter location/navigation and map-stability suites | Connected; external app handles guidance |
| UC-05 sign-in | Operator auth, API, login screen, app session | Backend operator-auth and Flutter operator-login suites | Credential check/app gate; no admin server session |
| UC-10 collection | Collectors, cleaners and export | Backend collector/provider/metadata/export/refresh suites | Separate collection process |
| UC-11 appearance | Theme controller and Preferences | Flutter widget/lifecycle suites | Theme persists; other controls local |
| UC-12, UC-14-18 | Preferences, session manager and tracker | Flutter lifecycle/stress suites | Partial behavior only; not durable-feature acceptance |
| UC-04, UC-13; server admin operations | Requirements inventory | No complete backend acceptance claim | Deferred or sample-only |

Original black-box partitions, boundaries and basis paths are retained in
`../lab4/TEST-CASES-AND-RESULTS.md` and its testing PDF. Current execution results
are in `TESTING.md`. Mock-based tests do not establish live provider health,
physical-device acceptance or model probability accuracy.
