# Requirements to code and tests

| Use case | Implementation | Test evidence | Status |
| --- | --- | --- | --- |
| UC-01 recommendation | RecommendationController; TripRequest; pricing/model/scoring adapters | CTL-01..16; REQ-01..18; scoring EC/BV; mode tests | Implemented search, with documented cohort limits |
| UC-02 inspect carpark | Search result cards; price/source/forecast payload | Flutter parking_search_test and parking_api_response_test | Implemented result inspection; full planned detail flow remains partial |
| UC-03 navigation; UC-19 map | carpark_map_screen; navigation_handoff; device_location | Flutter map_stability, location_and_navigation, device_location tests; AND-03/06 | Automated fixtures passed; physical handoff pending |
| UC-05 operator sign-in | operator_auth; /operator/login; OperatorLoginScreen / OperatorSession | test_operator_auth; operator_login_test | Credential check and UI gate implemented; not a server session/authorization system |
| UC-10 collection | data-pipeline collectors and cleaning/export contracts | Collector, provider, metadata, refresh and export regression modules | Implemented separately; teammate operates collection |
| UC-11 preferences / UC-12 saved places | PreferencesScreen; theme controller | Flutter lifecycle/stress/theme tests | Theme persists; other controls retain prototype scope |
| UC-14..17 parking tracker/history | ParkingSessionManager and tracker UI | Flutter lifecycle/stress tests | In-memory/prototype behavior; not durable session history |
| UC-04/06/07/08/09/13/18 remaining scope | Planned reports, admin operations, favourites and full erasure | Do not infer real backend coverage from prototype UI tests | Not complete; keep visible in the implementation-gap record |
