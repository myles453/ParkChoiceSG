# Use Case Specification: UC-02 - Inspect Carpark Information

| Field | Details |
|---|---|
| Use Case ID | UC-02 |
| Use Case Name | Inspect Carpark Information |
| Created By | Nestor |
| Date Created | 30 August 2026 |
| Last Updated By | Nestor |
| Date Last Updated | 30 August 2026 |
| Actor | Anonymous Driver |
| Description | The driver selects a recommended carpark and inspects the information and evidence used to assess it. |
| Preconditions | 1. UC-01 has produced at least one carpark recommendation. |
| Postconditions | 1. The selected carpark's information is displayed.<br>2. The recommendation results remain unchanged.<br>3. No account or profile is created. |
| Priority | Must Have |
| Frequency of Use | High - normally after a recommendation request. |

## Flow of Events

1. The driver selects a carpark from the recommendation results.
2. ParkChoiceSG opens the information view for the selected carpark.
3. ParkChoiceSG displays the carpark's name, address, current reported availability and timestamp, estimated cost for the entered duration, and walking distance to the destination.
4. ParkChoiceSG displays the carpark's Best Overall ranking explanation and any relevant data warnings.
5. ParkChoiceSG provides an option to open external navigation to the carpark.

## Alternative Flows

### UC-02.AC.1 - Selected carpark information is no longer available

1. At Step 2, ParkChoiceSG cannot retrieve the selected result from the active recommendation.
2. ParkChoiceSG explains that the information is no longer available.
3. ParkChoiceSG returns the driver to the current recommendation results.

### UC-02.AC.2 - Some displayed information is no longer current

1. At Step 3, ParkChoiceSG detects that previously retrieved information no longer satisfies the freshness rule.
2. ParkChoiceSG marks the affected information as unavailable or outdated rather than presenting it as current.
3. ParkChoiceSG advises the driver to refresh the recommendation before relying on the result.
4. The use case resumes at Step 4 with the remaining information.

### UC-02.AC.3 - Driver requests navigation

1. After Step 5, the driver selects the external-navigation option.
2. ParkChoiceSG starts UC-03.

## Exception Flows

### UC-02.EX.1 - Unexpected system error

1. ParkChoiceSG records the error without exposing sensitive technical details.
2. ParkChoiceSG informs the driver that the carpark information could not be displayed.
3. ParkChoiceSG provides an option to return to the recommendation results.
4. The use case ends.

## Includes

None.

## Special Requirements

- Information displayed in UC-02 must use the same values, units, labels, and timestamps as the corresponding UC-01 result.
- Availability must be labelled "Current reported availability" and must not be represented as a guaranteed parking space.
- The ranking explanation must identify the availability, estimated cost, and walking distance considered by the fixed Best Overall score.
- When the information is already available from the recommendation result, the information view should appear within one second for at least 95% of selections on a supported device.
- Inspecting a carpark must not require an account, profile, origin, or device-location permission.

## Assumptions

- The selected carpark belongs to the active recommendation result set.
- Estimated cost and walking distance retain the parking duration and destination used in UC-01.
- Parking information may change after it is retrieved.

## Notes and Issues

None.
