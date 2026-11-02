# Use Case Specification: UC-03 - Open External Navigation

| Field | Details |
|---|---|
| Use Case ID | UC-03 |
| Use Case Name | Open External Navigation |
| Created By | Nestor |
| Date Created | 30 August 2026 |
| Last Updated By | Nestor |
| Date Last Updated | 30 August 2026 |
| Actor | Anonymous Driver; Destination, Map and Routing Provider; Device Operating System |
| Description | The driver requests directions to a selected carpark, and ParkChoiceSG hands the carpark destination to an external navigation service. |
| Preconditions | 1. UC-02 is displaying a selected carpark. |
| Postconditions | 1. On success, an external navigation service opens with the selected carpark as its destination.<br>2. On failure, the driver remains in ParkChoiceSG and receives a clear alternative. |
| Priority | Must Have |
| Frequency of Use | Medium - when a driver decides to travel to a recommended carpark. |

## Flow of Events

1. The driver selects the option to navigate to the displayed carpark.
2. ParkChoiceSG obtains the selected carpark's verified name and destination coordinates.
3. ParkChoiceSG sends the destination to a supported external navigation service through the device operating system.
4. The external navigation service opens and displays a route to the selected carpark.
5. ParkChoiceSG completes the handoff without providing turn-by-turn navigation itself.

## Alternative Flows

### UC-03.AC.1 - More than one navigation service is available

1. At Step 3, the device operating system asks the driver to select a supported navigation service.
2. The driver selects a service.
3. The use case resumes at Step 4.

### UC-03.AC.2 - No supported navigation application is available

1. At Step 3, the device cannot open a supported navigation application.
2. ParkChoiceSG keeps the carpark information visible and provides the carpark name, address, and coordinates for manual use.
3. The use case ends without opening navigation.

### UC-03.AC.3 - External navigation service cannot calculate a route

1. At Step 4, the external navigation service cannot produce a route.
2. The external service informs the driver according to its own failure behaviour.
3. ParkChoiceSG remains responsible only for having supplied the correct selected destination.
4. The use case ends.

## Exception Flows

### UC-03.EX.1 - Selected destination is invalid or unavailable

1. At Step 2, ParkChoiceSG detects missing or invalid destination coordinates.
2. ParkChoiceSG does not launch the external navigation service.
3. ParkChoiceSG explains that navigation cannot be opened for this carpark and keeps its information visible.
4. The use case ends.

### UC-03.EX.2 - Unexpected handoff error

1. ParkChoiceSG records the error without exposing sensitive technical details.
2. ParkChoiceSG informs the driver that navigation could not be opened and keeps the carpark information visible.
3. The use case ends.

## Includes

None.

## Special Requirements

- ParkChoiceSG must send only the selected carpark's name and destination coordinates required for the handoff.
- ParkChoiceSG must not require or collect the driver's origin or device location for the handoff. The external navigation service manages any origin or location permission under its own controls.
- The external application launch should begin within two seconds for at least 95% of requests on a supported device, excluding time spent inside the external service.
- A handoff failure must not close the carpark information view or remove the selected result.
- ParkChoiceSG must clearly indicate that navigation is provided by an external service.

## Assumptions

- The device operating system supports external application links or intents.
- At least one suitable external navigation service may be installed or accessible through a web browser.
- ParkChoiceSG does not control route availability, traffic information, navigation accuracy, or permissions requested by the external service.

## Notes and Issues

None.
