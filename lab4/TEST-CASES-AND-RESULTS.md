# Test cases and testing results

26 October 2026. Current local review build, not a submission-ready claim.

88 documented cases passed; backend regression: 151 unittest methods; model tests: 108; Flutter tests: 44. Android arm64 debug APK built. Physical-device checks remain pending.


## 3. Recommendation control cases

| ID | Input / change | Expected | Actual / result |
| --- | --- | --- | --- |
| CTL-01 | valid forecast fixture | ('ok', 3, 0) | ('ok', 3, 0) / PASS |
| CTL-02 | {'pending': True} | ('ok', 3, 0) | ('ok', 3, 0) / PASS |
| CTL-03 | {'empty': True} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-04 | {'route_error': 'drive'} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-05 | {'route_error': 'walk'} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-06 | {'price': 'tariff_unverified'} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-07 | {'history_age': 16} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-08 | {'probability': 0.899999} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-09 | {'probability': 0.9} | ('ok', 3, 0) | ('ok', 3, 0) / PASS |
| CTL-10 | {'probability': 0.900001} | ('ok', 3, 0) | ('ok', 3, 0) / PASS |
| CTL-11 | {'audit_error': True} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-12 | {'prediction_status': 'unsupported_horizon_15_to_90_minutes'} | ('current_reading_fallback', 0, 3) | ('current_reading_fallback', 0, 3) / PASS |
| CTL-13 | {'prediction_status': 'unsupported_horizon_15_to_90_minutes', 'current_status': 'stale'} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-14 | {'current_count': 0} | ('ok', 3, 0) | ('ok', 3, 0) / PASS |
| CTL-15 | {'wrong_identity': True} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |
| CTL-16 | {'prediction_status': 'unknown_carpark', 'timestamp_kind': 'retrieval'} | ('no_eligible_candidates', 0, 0) | ('no_eligible_candidates', 0, 0) / PASS |


## 4. Request boundary values

| ID | Input / change | Expected | Actual / result |
| --- | --- | --- | --- |
| REQ-01 | duration_minutes=0; other fields nominal | ValueError | ValueError / PASS |
| REQ-02 | duration_minutes=1; other fields nominal | accepted | accepted / PASS |
| REQ-03 | duration_minutes=2; other fields nominal | accepted | accepted / PASS |
| REQ-04 | duration_minutes=1439; other fields nominal | accepted | accepted / PASS |
| REQ-05 | duration_minutes=1440; other fields nominal | accepted | accepted / PASS |
| REQ-06 | duration_minutes=1441; other fields nominal | ValueError | ValueError / PASS |
| REQ-07 | candidate_limit=0; other fields nominal | ValueError | ValueError / PASS |
| REQ-08 | candidate_limit=1; other fields nominal | accepted | accepted / PASS |
| REQ-09 | candidate_limit=2; other fields nominal | accepted | accepted / PASS |
| REQ-10 | candidate_limit=4; other fields nominal | accepted | accepted / PASS |
| REQ-11 | candidate_limit=5; other fields nominal | accepted | accepted / PASS |
| REQ-12 | candidate_limit=6; other fields nominal | ValueError | ValueError / PASS |
| REQ-13 | radius_meters=99; other fields nominal | ValueError | ValueError / PASS |
| REQ-14 | radius_meters=100; other fields nominal | accepted | accepted / PASS |
| REQ-15 | radius_meters=101; other fields nominal | accepted | accepted / PASS |
| REQ-16 | radius_meters=2999; other fields nominal | accepted | accepted / PASS |
| REQ-17 | radius_meters=3000; other fields nominal | accepted | accepted / PASS |
| REQ-18 | radius_meters=3001; other fields nominal | ValueError | ValueError / PASS |


## 5. Supporting scoring equivalence classes

| ID | Input / change | Expected | Actual / result |
| --- | --- | --- | --- |
| EC-01 | nominal | 50.0 (best_overall_v1_provisional) | 50.0 (best_overall_v1_provisional) / PASS |
| EC-02 | available_lots=None, p_free=0.5, weights={'cost': 0.25, 'walking': 0.25, 'availability': 0.25, 'driving': 0.25} | 50.0 (best_overall_probability_v2_provisional) | 50.0 (best_overall_probability_v2_provisional) / PASS |
| EC-03 | cost_cents=-400 | ValueError | ValueError / PASS |
| EC-04 | cost_cents=400.0 | ValueError | ValueError / PASS |
| EC-05 | duration_minutes=-60 | ValueError | ValueError / PASS |
| EC-06 | duration_minutes=60.5 | ValueError | ValueError / PASS |
| EC-07 | walking_meters=-500 | ValueError | ValueError / PASS |
| EC-08 | walking_meters=inf | ValueError | ValueError / PASS |
| EC-09 | walking_meters='500' | ValueError | ValueError / PASS |
| EC-10 | driving_seconds=-900 | ValueError | ValueError / PASS |
| EC-11 | driving_seconds=nan | ValueError | ValueError / PASS |
| EC-12 | available_lots=-5 | ValueError | ValueError / PASS |
| EC-13 | available_lots=None | ValueError | ValueError / PASS |
| EC-14 | p_free=0.5 | ValueError | ValueError / PASS |
| EC-15 | available_lots=None, p_free=-0.5 | ValueError | ValueError / PASS |
| EC-16 | available_lots=None, p_free=1.5 | ValueError | ValueError / PASS |
| EC-17 | available_lots=None, p_free=nan | ValueError | ValueError / PASS |
| EC-18 | weights={'cost': 0.5, 'walking': 0.3, 'availability': 0.2} | ValueError | ValueError / PASS |
| EC-19 | weights={'cost': 0.5, 'walking': 0.5, 'availability': 0.0, 'driving': 0.0} | ValueError | ValueError / PASS |
| EC-20 | weights={'cost': 0.5, 'walking': 0.5, 'availability': 0.5, 'driving': 0.5} | ValueError | ValueError / PASS |


## 6. Supporting scoring boundary values

| ID | Input / change | Expected | Actual / result |
| --- | --- | --- | --- |
| BV-01 | cost_cents=-1 | ValueError | ValueError / PASS |
| BV-02 | cost_cents=0 | 70.0 | 70.0 / PASS |
| BV-03 | cost_cents=1 | 69.9002 | 69.9002 / PASS |
| BV-04 | duration_minutes=0 | ValueError | ValueError / PASS |
| BV-05 | duration_minutes=1 | 30.6557 | 30.6557 / PASS |
| BV-06 | walking_meters=-0.001 | ValueError | ValueError / PASS |
| BV-07 | walking_meters=0 | 65.0 | 65.0 / PASS |
| BV-08 | driving_seconds=-0.001 | ValueError | ValueError / PASS |
| BV-09 | driving_seconds=0 | 55.0 | 55.0 / PASS |
| BV-10 | available_lots=-0.001 | ValueError | ValueError / PASS |
| BV-11 | available_lots=0 | 40.0 | 40.0 / PASS |
| BV-12 | available_lots=None, p_free=-0.001 | ValueError | ValueError / PASS |
| BV-13 | available_lots=None, p_free=0 | 40.0 | 40.0 / PASS |
| BV-14 | available_lots=None, p_free=1 | 60.0 | 60.0 / PASS |
| BV-15 | available_lots=None, p_free=1.001 | ValueError | ValueError / PASS |
| BV-16 | weights={'cost': 0.1, 'walking': 0.2, 'availability': 0.3, 'driving': 0.4} | 50.0 | 50.0 / PASS |
| BV-17 | weights={'cost': 0.1, 'walking': 0.2, 'availability': 0.3, 'driving': 0.400001} | ValueError | ValueError / PASS |


## window_at basis paths

N=14; E=20; V(G)=8; independent basis rank=8.

| ID | Path | Input | Expected / actual |
| --- | --- | --- | --- |
| WA-P1 | 1-2F-4-5-6F-8F-9F-10F-11F-12 | weekday 07:00-17:00; at Mon 10:00 | Mon 07:00 to Mon 17:00 / Mon 07:00 to Mon 17:00 |
| WA-P2 | 1-2T-3 | all 07:00-07:00; at Mon 10:00 | None / None |
| WA-P3 | 1-2F-4-5-6T-7-8F-9F-10F-11F-12 | all 19:00-07:00; at Mon 20:00 | Mon 19:00 to Tue 07:00 / Mon 19:00 to Tue 07:00 |
| WA-P4 | 1-2F-4-5-6F-8T-4-5-6F-8T-4-13 | weekday 07:00-17:00; at Mon 18:00 | None / None |
| WA-P5 | 1-2F-4-5-6F-8F-9T-4-5-6F-8T-4-13 | weekday 07:00-17:00; at Sat 10:00 | None / None |
| WA-P6 | 1-2F-4-5-6F-8F-9F-10T-4-5-6F-8T-4-13 | all 07:00-17:00, {'weekdays': [0, 1, 2, 3, 4]}; at Sat 10:00 | None / None |
| WA-P7 | 1-2F-4-5-6F-8F-9F-10F-11T-4-5-6F-8T-4-13 | all 07:00-17:00, {'ph_eve': True}; at Mon 10:00 | None / None |
| WA-P8 | 1-2F-4-5-6T-7-8T-4-5-6T-7-8F-9F-10F-11F-12 | all 19:00-07:00; at Tue 02:00 | Mon 19:00 to Tue 07:00 / Mon 19:00 to Tue 07:00 |
| WA-C1 | 1-2F-4-5-6T-7-8F-9F-10F-11F-12 | all 07:00-07:00, {'full_day': True}; at Mon 10:00 | Mon 07:00 to Tue 07:00 / Mon 07:00 to Tue 07:00 |


## _tier_price basis paths

N=16; E=22; V(G)=8; independent basis rank=8.

| ID | Path | Input | Expected / actual |
| --- | --- | --- | --- |
| TP-P1 | 1-2F-9-10-11T-12-10-13T-14-15 | tiers [60m@120c/60m]; 90 min; first_entry=None | 170 / 170 |
| TP-P2 | 1-2T-3T-4 | tiers [60m@120c/60m]; first entry required; 90 min; first_entry=None | None / None |
| TP-P3 | 1-2T-3F-5F-9-10-11T-12-10-13T-14-15 | tiers [60m@120c/60m]; first entry required; 90 min; first_entry=True | 170 / 170 |
| TP-P4 | 1-2T-3F-5T-6-7T-8 | tiers [60m@120c/60m]; first entry required; 90 min; first_entry=False | None / None |
| TP-P5 | 1-2T-3F-5T-6-7F-9-10-11T-12-10-13T-14-15 | tiers [60m@120c/60m]; first entry required; repeat tier 60m@200c/60m; 90 min; first_entry=False | 250 / 250 |
| TP-P6 | 1-2F-9-10-13T-14-15 | tiers []; 45 min; first_entry=None | 100 / 100 |
| TP-P7 | 1-2F-9-10-11T-12-10-11F-10-13F-15 | tiers [60m@120c/60m, 60m@80c/30m]; 60 min; first_entry=None | 120 / 120 |
| TP-P8 | 1-2F-9-10-11T-12-10-13F-15 | tiers [60m@120c/60m]; 60 min; first_entry=None | 120 / 120 |


## Android acceptance record

| ID | Action | Expected | Actual status |
| --- | --- | --- | --- |
| AND-01 | Install the supplied arm64 debug APK on the actual demo phone. | Launches anonymous Search. | Pending on device |
| AND-02 | Use USB reverse port 8000; issue a real search. | Phone reaches the laptop backend. | Pending on device |
| AND-03 | Grant foreground location; then test denial/manual origin. | Fresh fix or recoverable manual-input path. | Pending on device |
| AND-04 | Search a rehearsed 15-90-minute arrival scenario. | Real routed prices and eligible arrival probabilities, or an honest unavailable state. | Pending on device |
| AND-05 | Re-search with each ranking mode. | Mode sent; old results cleared; policy shown consistently. | Pending on device |
| AND-06 | Open map, launch navigation and return to the app. | Attributed tiles/markers and correct carpark handoff; no crash. | Pending on device |
| AND-07 | Run a short trip and inspect current-only fallback. | Fallback is separately labelled; no fabricated forecast. | Pending on device |
| AND-08 | Rotate, open keyboard, background/foreground, switch tabs repeatedly. | No crash/overflow; transient resets understood. | Pending on device |
| AND-09 | Disconnect/reconnect USB and rerun reverse; retry a request. | Recoverable service error and successful retry. | Pending on device |
| AND-10 | If showing Admin, test wrong/right configured operator credentials. | Credential check works; console data/actions identified as prototypes. | Pending on device |


Reproduce: `python lab4/collect_evidence.py`. Source hashes and exact rows: `evidence/test-results.json`.
