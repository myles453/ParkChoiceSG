# Use Case Specification: UC-01 - Request Carpark Recommendation

| Field | Details |
|---|---|
| Use Case ID | UC-01 |
| Use Case Name | Request Carpark Recommendation |
| Created By | Nestor |
| Date Created | 30 August 2026 |
| Last Updated By | Nestor |
| Date Last Updated | 30 August 2026 |
| Actor | Anonymous Driver; Parking Data Provider; Destination, Map and Routing Provider |
| Description | The driver requests ranked carpark recommendations near a destination. ParkChoiceSG applies one fixed Best Overall scoring model using current parking availability, estimated parking cost, and walking distance, then explains why each result is recommended. |
| Preconditions | 1. ParkChoiceSG is running.<br>2. The driver can access the carpark recommendation interface. |
| Postconditions | 1. On success, the driver receives an explained, time-labelled list of up to five recommendations.<br>2. On failure, the driver receives a clear message that no reliable recommendation can be produced.<br>3. No account or profile is created. |
| Priority | Must Have |
| Frequency of Use | High - normally once per parking search or journey. |

## Flow of Events

1. The driver opens the carpark recommendation function.
2. The driver enters a destination and intended parking duration, then submits the request.
3. ParkChoiceSG validates the inputs and resolves the destination to a location.
4. ParkChoiceSG identifies supported nearby carparks and obtains their latest reported availability, published parking rates, and walking-route measurements to the destination.
5. ParkChoiceSG verifies that each candidate has sufficiently current and comparable evidence. It labels every retained availability value as "Current reported availability" and shows its source timestamp.
6. ParkChoiceSG estimates the parking cost for the entered duration, calculates each candidate's fixed Best Overall score using current availability, estimated cost, and walking distance, and ranks the candidates.
7. ParkChoiceSG presents the highest-ranked carpark as the Best Overall recommendation, followed by up to four alternatives. Each result shows its raw factor values, timestamp, relevant warnings, and a concise explanation of its ranking.

## Alternative Flows

### UC-01.AC.1 - Invalid destination or duration

1. At Step 3, ParkChoiceSG identifies an invalid or unsupported input.
2. ParkChoiceSG explains which input must be corrected.
3. The use case resumes at Step 2.

### UC-01.AC.2 - Destination cannot be resolved

1. At Step 3, the destination provider cannot resolve the entered destination unambiguously.
2. ParkChoiceSG asks the driver to refine the destination or select a suggested match.
3. The use case resumes at Step 2 or Step 3 after the driver responds.

### UC-01.AC.3 - Some external data is unavailable

1. At Step 4, one provider or part of its data is unavailable.
2. ParkChoiceSG continues only with carparks that still have the current availability, verified rate information, and walking-route measurement required for the fixed comparison.
3. ParkChoiceSG displays a warning that some carparks could not be assessed because data was unavailable.
4. The use case resumes at Step 5.

### UC-01.AC.4 - A carpark has missing, stale, or incomparable evidence

1. At Step 5, ParkChoiceSG detects that a carpark lacks the minimum evidence required for a fair comparison.
2. ParkChoiceSG excludes that carpark instead of inventing or silently substituting a value.
3. The use case resumes at Step 5 with the remaining candidates.

### UC-01.AC.5 - Fewer than five suitable carparks are available

1. At Step 7, fewer than five carparks satisfy the evidence and eligibility rules.
2. ParkChoiceSG displays every suitable result and states that no additional comparable carparks were found.

### UC-01.AC.6 - No suitable carpark can be recommended

1. At Step 5, no candidate has enough current and comparable evidence for the fixed scoring model.
2. ParkChoiceSG explains why a reliable ranking cannot be produced and suggests changing the destination or duration, or retrying later.
3. The use case ends without a recommendation.

### UC-01.AC.7 - Driver selects a result

1. After Step 7, the driver selects a recommended carpark.
2. ParkChoiceSG starts UC-02 for the selected carpark.

## Exception Flows

### UC-01.EX.1 - All required data sources are unavailable

1. ParkChoiceSG cannot obtain enough current evidence to produce a responsible recommendation.
2. ParkChoiceSG informs the driver that recommendations are temporarily unavailable and invites the driver to retry later.
3. The use case ends without a recommendation.

### UC-01.EX.2 - Unexpected system error

1. ParkChoiceSG records the error without exposing credentials or sensitive technical details.
2. ParkChoiceSG informs the driver that the request could not be completed and provides a retry option.
3. The use case ends.

## Includes

None.

## Special Requirements

- When every required external dependency responds within one second, at least 95% of recommendation requests should be displayed within three seconds.
- Every availability value must be labelled "Current reported availability" and accompanied by its source timestamp.
- Every ranked result must show the availability, estimated cost, and walking distance used in its fixed Best Overall score, together with a concise reason for its position.
- Missing or stale factor data must not be replaced with an invented value or presented as current.
- Partial provider failure must be visible to the driver.
- The core recommendation flow must not require an account, profile, origin, or device-location permission.
- API credentials and provider tokens must not be embedded in the client application or exposed in user-facing errors.
- A first-time driver should be able to submit a search using three required actions: enter a destination, enter a duration, and request recommendations.

## Assumptions

- The driver is searching for an ordinary passenger-car parking space.
- The driver uses ParkChoiceSG only while stationary or through a passenger.
- Parking availability and rate data come from authorised sources and may change after retrieval.
- Estimated cost is based on verified published rate information and the entered duration; it is not a payment quotation or guarantee.
- Current availability does not guarantee that a lot will remain available when the driver arrives.
- Turn-by-turn navigation is handed off to an external navigation service.
- The scoring weights, normalisation rules, and tie-breaker are defined consistently in the project's scoring requirements and tests.

## Notes and Issues

None.
