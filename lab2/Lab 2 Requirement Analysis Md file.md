# Lab 2: Requirements Analysis — ParkChoiceSG

**Course:** SC2006 Software Engineering
**Project:** ParkChoiceSG
**Deliverable Directory:** `/lab2`
**Document Version:** 2.0
**Date:** September 2026

---

## 1. Executive Summary & Lab Objectives

The objective of Lab 2 is to transform the system requirements into a structured **Analysis Model** following the methodologies described in Bruegge (Chapter 5) and Fox (Chapter 5 / Dialog Maps). This deliverable covers:
1. **Refined Use Case Model**: Use case diagram and formal specifications for driver and operator flows.
2. **Conceptual Object Model**: Stereotyped entity classes, attributes, and associations.
3. **Boundary-Control-Entity (BCE) Architecture**: Structural breakdown of UI components, control logic, and domain entities.
4. **Dynamic Model**: Dialog map (UI state machine) representing user journeys and administrative workflows.
5. **Technology Stack Evaluation**: AI recommendation analysis and technical evaluation for system middleware.

---

## 2. Refined Use Case Model

### 2.1 Actors
* **Anonymous Driver (Primary)**: Motorist searching for parking recommendations, inspecting candidate details, and launching turn-by-turn navigation.
* **System Operator / Administrator (Primary)**: Authenticated technical administrator who monitors external API health, moderates error reports, and manages manual carpark overrides.
* **Parking Data Provider (Secondary)**: External public services (LTA DataMall, Data.gov.sg, URA) providing lot vacancy feeds and rate schedules.
* **Destination, Map and Routing Provider (Secondary)**: External spatial services (Google Maps API, OneMap) providing geocoding, autocomplete, and walking/driving route measurements.
* **Device Operating System (Secondary)**: Platform subsystem handling application URL schemes and intents to launch native external routing applications.

---

### 2.2 Use Case Diagram

```
+---------------------------------------------------------------------------------------------------------+
|                                              ParkChoiceSG                                               |
|                                                                                                         |
|   +---------------------------------------+                                                             |
|   | (UC-01: Request Recommendation) <-----+---------------------------------------------------------+   |
|   +---------------------------------------+                                                         |   |
|         ^                                                                                           |   |
|         | <<include>> (result selected)                                                              |   |
|   +-----+---------------------------------+                                                         |   |
|   | (UC-02: Inspect Carpark Info) <-------+-----------------------------------------------------+   |   |
|   +---------------------------------------+                                                     |   |   |
|         ^                                                                                       |   |   |
|         | <<include>> (navigation requested)                                                     |   |   |
|   +-----+---------------------------------+                                                         |   |
|   | (UC-03: Open External Navigation) <---+-------------------------------------------------+   |   |   |
|   +---------------------------------------+                                                 |   |   |   |
|                                                                                             |   |   |   |
|   +---------------------------------------+                                                 |   |   |   |
|   | (UC-04: Submit Error Report)          |                                                 |   |   |   |
|   +---------------------------------------+                                                 |   |   |   |
|                                                                                             |   |   |   |
| - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - | - | - | - |
|                                                                                             |   |   |   |
|   +---------------------------------------+                                                 |   |   |   |
|   | (UC-05: Authenticate Operator) <------+                                                 |   |   |   |
|   +---------------------------------------+                                                 |   |   |   |
|         ^                   ^         ^                                                     |   |   |   |
|         | <<include>>       |         | <<include>>                                          |   |   |   |
|   +-----+-------------+     |   +-----+------------------------------------+                |   |   |   |
|   | (UC-06: Manage    |     |   | (UC-08: View API Health & Freshness) <---+            |   |   |   |
|   |  Error Reports)   |     |   +------------------------------------------+            |   |   |   |
|   +-------------------+     |         ^                                                 |   |   |   |
|                             |         | <<extend>> (on stale source detected)           |   |   |   |
|                             |   +-----+------------------------------------+            |   |   |   |
|   +-------------------+     |   | (UC-09: Trigger Manual Data Refresh)     |            |   |   |   |
|   | (UC-07: Apply     |-----+   +------------------------------------------+            |   |   |   |
|   | Carpark Override) | <<extend>>                                                     |   |   |   |
|   +-------------------+                                                                 |   |   |   |
+-----------------------------------------------------------------------------------------|---|---|---+
      ^                           ^                                                      ^   ^   ^
      |                           |                                                      |   |   |
[Anonymous Driver]         [System Operator]                                              |   |   [Device OS]
                                                                                            |   |
                                                                    [Parking Data Provider]     [Map / Routing Provider]
```

---

### 2.3 Detailed Use Case Specifications

#### UC-01: Request Carpark Recommendation
* **Use Case ID:** UC-01
* **Use Case Name:** Request Carpark Recommendation
* **Created By:** Nestor
* **Last Updated By:** Nestor
* **Date Created:** 30 August 2026
* **Date Last Updated:** 30 August 2026
* **Actor:** Anonymous Driver; Parking Data Provider; Destination, Map and Routing Provider
* **Description:** The driver requests ranked carpark recommendations near a destination. ParkChoiceSG applies one fixed Best Overall scoring model using current parking availability, estimated parking cost, and walking distance, then explains why each result is recommended.
* **Preconditions:**
  1. ParkChoiceSG is running.
  2. The driver can access the carpark recommendation interface.
* **Postconditions:**
  1. On success, the driver receives an explained, time-labelled list of up to five recommendations.
  2. On failure, the driver receives a clear message that no reliable recommendation can be produced.
  3. No account or profile is created.
* **Priority:** Must Have
* **Frequency of Use:** High - normally once per parking search or journey.
* **Flow of Events:**
  1. The driver opens the carpark recommendation function.
  2. The driver enters a destination and intended parking duration, then submits the request.
  3. ParkChoiceSG validates the inputs and resolves the destination to a location.
  4. ParkChoiceSG identifies supported nearby carparks and obtains their latest reported availability, published parking rates, and walking-route measurements to the destination.
  5. ParkChoiceSG verifies that each candidate has sufficiently current and comparable evidence. It labels every retained availability value as "Current reported availability" and shows its source timestamp.
  6. ParkChoiceSG estimates the parking cost for the entered duration, calculates each candidate's fixed Best Overall score using current availability, estimated cost, and walking distance, and ranks the candidates.
  7. ParkChoiceSG presents the highest-ranked carpark as the Best Overall recommendation, followed by up to four alternatives. Each result shows its raw factor values, timestamp, relevant warnings, and a concise explanation of its ranking.
* **Alternative Flows:**
  * **UC-01.AC.1 - Invalid destination or duration:**
    1. At Step 3, ParkChoiceSG identifies an invalid or unsupported input.
    2. ParkChoiceSG explains which input must be corrected.
    3. The use case resumes at Step 2.
  * **UC-01.AC.2 - Destination cannot be resolved:**
    1. At Step 3, the destination provider cannot resolve the entered destination unambiguously.
    2. ParkChoiceSG asks the driver to refine the destination or select a suggested match.
    3. The use case resumes at Step 2 or Step 3 after the driver responds.
  * **UC-01.AC.3 - Some external data is unavailable:**
    1. At Step 4, one provider or part of its data is unavailable.
    2. ParkChoiceSG continues only with carparks that still have the current availability, verified rate information, and walking-route measurement required for the fixed comparison.
    3. ParkChoiceSG displays a warning that some carparks could not be assessed because data was unavailable.
    4. The use case resumes at Step 5.
  * **UC-01.AC.4 - A carpark has missing, stale, or incomparable evidence:**
    1. At Step 5, ParkChoiceSG detects that a carpark lacks the minimum evidence required for a fair comparison.
    2. ParkChoiceSG excludes that carpark instead of inventing or silently substituting a value.
    3. The use case resumes at Step 5 with the remaining candidates.
  * **UC-01.AC.5 - Fewer than five suitable carparks are available:**
    1. At Step 7, fewer than five carparks satisfy the evidence and eligibility rules.
    2. ParkChoiceSG displays every suitable result and states that no additional comparable carparks were found.
  * **UC-01.AC.6 - No suitable carpark can be recommended:**
    1. At Step 5, no candidate has enough current and comparable evidence for the fixed scoring model.
    2. ParkChoiceSG explains why a reliable ranking cannot be produced and suggests changing the destination or duration, or retrying later.
    3. The use case ends without a recommendation.
  * **UC-01.AC.7 - Driver selects a result:**
    1. After Step 7, the driver selects a recommended carpark.
    2. ParkChoiceSG starts UC-02 for the selected carpark.
* **Exceptions:**
  * **UC-01.EX.1 - All required data sources are unavailable:**
    1. ParkChoiceSG cannot obtain enough current evidence to produce a responsible recommendation.
    2. ParkChoiceSG informs the driver that recommendations are temporarily unavailable and invites the driver to retry later.
    3. The use case ends without a recommendation.
  * **UC-01.EX.2 - Unexpected system error:**
    1. ParkChoiceSG records the error without exposing credentials or sensitive technical details.
    2. ParkChoiceSG informs the driver that the request could not be completed and provides a retry option.
    3. The use case ends.
* **Special Requirements:**
  1. When every required external dependency responds within one second, at least 95% of recommendation requests should be displayed within three seconds.
  2. Every availability value must be labelled "Current reported availability" and accompanied by its source timestamp.
  3. Every ranked result must show the availability, estimated cost, and walking distance used in its fixed Best Overall score, together with a concise reason for its position.
  4. Missing or stale factor data must not be replaced with an invented value or presented as current.
  5. Partial provider failure must be visible to the driver.
  6. The core recommendation flow must not require an account, profile, origin, or device-location permission.
  7. API credentials and provider tokens must not be embedded in the client application or exposed in user-facing errors.
  8. A first-time driver should be able to submit a search using three required actions: enter a destination, enter a duration, and request recommendations.
* **Assumptions:**
  1. The driver is searching for an ordinary passenger-car parking space.
  2. The driver uses ParkChoiceSG only while stationary or through a passenger.
  3. Parking availability and rate data come from authorised sources and may change after retrieval.
  4. Estimated cost is based on verified published rate information and the entered duration; it is not a payment quotation or guarantee.
  5. Current availability does not guarantee that a lot will remain available when the driver arrives.
  6. Turn-by-turn navigation is handed off to an external navigation service.
  7. The scoring weights, normalisation rules, and tie-breaker are defined consistently in the project's scoring requirements and tests.

---

#### UC-02: Inspect Carpark Information
* **Use Case ID:** UC-02
* **Use Case Name:** Inspect Carpark Information
* **Created By:** Nestor
* **Last Updated By:** Nestor
* **Date Created:** 30 August 2026
* **Date Last Updated:** 30 August 2026
* **Actor:** Anonymous Driver
* **Description:** The driver selects a recommended carpark and inspects the information and evidence used to assess it.
* **Preconditions:**
  1. UC-01 has produced at least one carpark recommendation.
* **Postconditions:**
  1. The selected carpark's information is displayed.
  2. The recommendation results remain unchanged.
  3. No account or profile is created.
* **Priority:** Must Have
* **Frequency of Use:** High - normally after a recommendation request.
* **Flow of Events:**
  1. The driver selects a carpark from the recommendation results.
  2. ParkChoiceSG opens the information view for the selected carpark.
  3. ParkChoiceSG displays the carpark's name, address, current reported availability and timestamp, estimated cost for the entered duration, and walking distance to the destination.
  4. ParkChoiceSG displays the carpark's Best Overall ranking explanation and any relevant data warnings.
  5. ParkChoiceSG provides an option to open external navigation to the carpark.
* **Alternative Flows:**
  * **UC-02.AC.1 - Selected carpark information is no longer available:**
    1. At Step 2, ParkChoiceSG cannot retrieve the selected result from the active recommendation.
    2. ParkChoiceSG explains that the information is no longer available.
    3. ParkChoiceSG returns the driver to the current recommendation results.
  * **UC-02.AC.2 - Some displayed information is no longer current:**
    1. At Step 3, ParkChoiceSG detects that previously retrieved information no longer satisfies the freshness rule.
    2. ParkChoiceSG marks the affected information as unavailable or outdated rather than presenting it as current.
    3. ParkChoiceSG advises the driver to refresh the recommendation before relying on the result.
    4. The use case resumes at Step 4 with the remaining information.
  * **UC-02.AC.3 - Driver requests navigation:**
    1. After Step 5, the driver selects the external-navigation option.
    2. ParkChoiceSG starts UC-03.
* **Exceptions:**
  * **UC-02.EX.1 - Unexpected system error:**
    1. ParkChoiceSG records the error without exposing sensitive technical details.
    2. ParkChoiceSG informs the driver that the carpark information could not be displayed.
    3. ParkChoiceSG provides an option to return to the recommendation results.
    4. The use case ends.
* **Special Requirements:**
  1. Information displayed in UC-02 must use the same values, units, labels, and timestamps as the corresponding UC-01 result.
  2. Availability must be labelled "Current reported availability" and must not be represented as a guaranteed parking space.
  3. The ranking explanation must identify the availability, estimated cost, and walking distance considered by the fixed Best Overall score.
  4. When the information is already available from the recommendation result, the information view should appear within one second for at least 95% of selections on a supported device.
  5. Inspecting a carpark must not require an account, profile, origin, or device-location permission.
* **Assumptions:**
  1. The selected carpark belongs to the active recommendation result set.
  2. Estimated cost and walking distance retain the parking duration and destination used in UC-01.
  3. Parking information may change after it is retrieved.

---

#### UC-03: Open External Navigation
* **Use Case ID:** UC-03
* **Use Case Name:** Open External Navigation
* **Created By:** Nestor
* **Last Updated By:** Nestor
* **Date Created:** 30 August 2026
* **Date Last Updated:** 30 August 2026
* **Actor:** Anonymous Driver; Destination, Map and Routing Provider; Device Operating System
* **Description:** The driver requests directions to a selected carpark, and ParkChoiceSG hands the carpark destination to an external navigation service.
* **Preconditions:**
  1. UC-02 is displaying a selected carpark.
* **Postconditions:**
  1. On success, an external navigation service opens with the selected carpark as its destination.
  2. On failure, the driver remains in ParkChoiceSG and receives a clear alternative.
* **Priority:** Must Have
* **Frequency of Use:** Medium - when a driver decides to travel to a recommended carpark.
* **Flow of Events:**
  1. The driver selects the option to navigate to the displayed carpark.
  2. ParkChoiceSG obtains the selected carpark's verified name and destination coordinates.
  3. ParkChoiceSG sends the destination to a supported external navigation service through the device operating system.
  4. The external navigation service opens and displays a route to the selected carpark.
  5. ParkChoiceSG completes the handoff without providing turn-by-turn navigation itself.
* **Alternative Flows:**
  * **UC-03.AC.1 - More than one navigation service is available:**
    1. At Step 3, the device operating system asks the driver to select a supported navigation service.
    2. The driver selects a service.
    3. The use case resumes at Step 4.
  * **UC-03.AC.2 - No supported navigation application is available:**
    1. At Step 3, the device cannot open a supported navigation application.
    2. ParkChoiceSG keeps the carpark information visible and provides the carpark name, address, and coordinates for manual use.
    3. The use case ends without opening navigation.
  * **UC-03.AC.3 - External navigation service cannot calculate a route:**
    1. At Step 4, the external navigation service cannot produce a route.
    2. The external service informs the driver according to its own failure behaviour.
    3. ParkChoiceSG remains responsible only for having supplied the correct selected destination.
    4. The use case ends.
* **Exceptions:**
  * **UC-03.EX.1 - Selected destination is invalid or unavailable:**
    1. At Step 2, ParkChoiceSG detects missing or invalid destination coordinates.
    2. ParkChoiceSG does not launch the external navigation service.
    3. ParkChoiceSG explains that navigation cannot be opened for this carpark and keeps its information visible.
    4. The use case ends.
  * **UC-03.EX.2 - Unexpected handoff error:**
    1. ParkChoiceSG records the error without exposing sensitive technical details.
    2. ParkChoiceSG informs the driver that navigation could not be opened and keeps the carpark information visible.
    3. The use case ends.
* **Special Requirements:**
  1. ParkChoiceSG must send only the selected carpark's name and destination coordinates required for the handoff.
  2. ParkChoiceSG must not require or collect the driver's origin or device location for the handoff. The external navigation service manages any origin or location permission under its own controls.
  3. The external application launch should begin within two seconds for at least 95% of requests on a supported device, excluding time spent inside the external service.
  4. A handoff failure must not close the carpark information view or remove the selected result.
  5. ParkChoiceSG must clearly indicate that navigation is provided by an external service.
* **Assumptions:**
  1. The device operating system supports external application links or intents.
  2. At least one suitable external navigation service may be installed or accessible through a web browser.
  3. ParkChoiceSG does not control route availability, traffic information, navigation accuracy, or permissions requested by the external service.

---

#### UC-05: Authenticate Operator
* **Use Case ID:** UC-05
* **Actor:** System Operator / Administrator
* **Description:** The operator authenticates via credentials over TLS to unlock the administrative console.
* **Preconditions:** Mobile/web client connects over TLS 1.2+.
* **Postconditions:** An encrypted session bearer token is issued; the administrative console tab is unlocked.
* **Main Flow:**
  1. Operator accesses the administrative login interface.
  2. Operator enters email/username and administrative password.
  3. System validates credentials against secure server-side configuration.
  4. System issues a signed session token and renders the Operator Console.
* **Alternative Flows:**
  * **UC-05.AC.1 (Authentication Failure):** System displays an error message without disclosing which credential field was invalid.

---

#### UC-07: Apply Manual Carpark Override
* **Use Case ID:** UC-07
* **Actor:** System Operator
* **Description:** Operator applies a manual override on a carpark (e.g., temporary closure or rate correction), preventing erroneous data from appearing in search results.
* **Preconditions:** Operator is successfully authenticated under UC-05.
* **Postconditions:** Overrides are persisted with an audit log and protected against daily background dataset refreshes.
* **Main Flow:**
  1. Operator selects a carpark by ID or from an error report ticket.
  2. Operator chooses an override action (e.g., "Mark Temporarily Closed").
  3. Operator provides a mandatory justification remark.
  4. System records the override with timestamp and operator ID.
  5. System excludes the carpark from recommendation algorithms and updates public status badges.
* **Alternative Flows:**
  * **UC-07.AC.1 (Withdraw Override):** Operator releases override; record reverts to source provider values at next refresh.

---

## 3. Conceptual Object Model (Entity Class Diagram)

```
+------------------------------------+           1..* +------------------------------------+
|             Destination            | -------------> |              Carpark               |
+------------------------------------+                +------------------------------------+
| - destinationName: String          |                | - carparkId: String                |
| - coordinates: Coordinates         |                | - name: String                     |
| - parkingDuration: Integer (mins)  |                | - address: String                  |
+------------------------------------+                | - location: Coordinates            |
                                                        | - vehicleClearanceHeight: Float    |
                                                        | - totalLots: Integer               |
                                                        | - paymentModes: List<String>       |
                                                        | - isOverridden: Boolean            |
                                                        | - isClosed: Boolean                |
                                                        +------------------------------------+
                                                          1 |             1 |              1 |
                                                            | 1             | 1..*           | 0..*
                                                            v               v                v
                                          +-------------------+  +-------------------+  +-------------------+
                                          |AvailabilityRecord |  |   RateSchedule    |  |  OperatorOverride |
                                          +-------------------+  +-------------------+  +-------------------+
                                          | - availableLots   |  | - vehicleType     |  | - overrideId      |
                                          | - timestamp       |  | - dayType         |  | - operatorId      |
                                          | - isPublished      |  | - chargePerBlock  |  | - overrideReason  |
                                          +-------------------+  | - blockDuration   |  | - appliedAt       |
                                                                  | - gracePeriod     |  +-------------------+
                                                                  | - isActive        |            ^
                                                                  +-------------------+            | 1..*
                                                                                          +---------+---------+
                                                                                          |   OperatorAccount |
                                                                                          +-------------------+
                                                                                          | - operatorId      |
                                                                                          | - email: String   |
                                                                                          | - passwordHash    |
                                                                                          | - role: String    |
                                                                                          +-------------------+
                                                                                                    | 1
                                                                                                    | 0..*
                                                                                          +---------+---------+
                                                                                          |    ErrorReport    |
                                                                                          +-------------------+
                                                                                          | - reportId        |
                                                                                          | - carparkId       |
                                                                                          | - reportCategory  |
                                                                                          | - description     |
                                                                                          | - status          |
                                                                                          | - submittedAt     |
                                                                                          | - resolutionNote  |
                                                                                          +-------------------+
```

---

## 4. Boundary, Control, and Entity (BCE) Architecture

| Stereotype | Class Name | Responsibility | Collaborators |
| :--- | :--- | :--- | :--- |
| **Boundary** | `SearchHomeScreenUI` | Captures search inputs and duration; displays top 5 ranked recommendation cards. | `RecommendationController` |
| **Boundary** | `CarparkDetailViewUI` | Renders rate table, lot freshness timestamps, physical clearance, and navigation action. | `RecommendationController`, `NavigationController` |
| **Boundary** | `OperatorConsoleUI` | Renders operator login, report moderation queues, override toggles, and API telemetry. | `OperatorAdminController`, `AuthenticationController` |
| **Boundary** | `ReportModalUI` | Captures anonymous data error reports submitted by drivers. | `ReportController` |
| **Boundary** | `LTADataMallAdapter` | Handles 60-second polling payloads from LTA DataMall. | `ExternalDataController` |
| **Boundary** | `NavigationIntentLauncher` | Dispatches native platform intent/URI schemes to launch external navigation apps. | `NavigationController` |
| **Control** | `RecommendationController` | Manages candidate filtering, radius expansion, and scoring pipeline execution. | `Carpark`, `ScoringEngine`, `CostCalculationEngine` |
| **Control** | `ScoringEngine` | Evaluates Best Overall ranking based on availability, cost, and walking distance. | `RecommendationResult` |
| **Control** | `CostCalculationEngine` | Computes charges using published rate schedules, vehicle category, and duration. | `RateSchedule`, `Carpark` |
| **Control** | `OperatorAdminController` | Manages manual overrides, protects overridden records from daily refreshes, and reads telemetry. | `OperatorOverride`, `Carpark`, `APIHealthMonitor` |
| **Control** | `AuthenticationController` | Validates administrative credentials over TLS; issues session bearer tokens. | `OperatorAccount`, `OperatorConsoleUI` |
| **Control** | `ReportController` | Validates and rate-limits anonymous error submissions (max 5 per device/24h). | `ErrorReport`, `OperatorAdminController` |
| **Entity** | `Carpark`, `AvailabilityRecord`, `RateSchedule`, `OperatorOverride`, `ErrorReport`, `OperatorAccount` | Domain entities maintaining persistent properties and relationships. | System Controllers |

---

## 5. Dynamic Model (Dialog Map / UI State Machine)

```
+==========================================================================================================+
|                                          DRIVER INTERFACE FLOW                                         |
+==========================================================================================================+
                        +---------------------------+
                        |  1.0 Search Home Screen   |<-----------------------+
                        +---------------------------+                        |
                              |                       ^                          |
                [Submit Valid Search] |                       | [Tap Back / Clear]       |
                              v                       |                          |
                        +---------------------------+                        |
                        | 2.0 Results List Display  |                        |
                        +---------------------------+                        |
                              |                       ^                          |
                [Select Carpark Card] |                       | [Tap Back]               |
                              v                       |                          |
                        +---------------------------+                        |
                        |  3.0 Carpark Detail View  |                        |
                        +---------------------------+                        |
                              |                       |                          |
        [Select "Report Issue"]    |                       | [Select "Navigate"]      |
                              v                       v                          |
                  +---------------------+  +--------------------+               |
                  | 3.1 Report Modal UI |  | 4.0 Ext Navigation |---------------+
                  +---------------------+  +--------------------+
                              |
                              +--------------------------------------------------+

+==========================================================================================================+
|                                      OPERATOR ADMINISTRATION FLOW                                      |
+==========================================================================================================+
                        +---------------------------+
                        | 6.0 Operator Login Screen |
                        +---------------------------+
                              |
                              | [Valid Credentials Over TLS]
                              v
                        +---------------------------+
                        |  7.0 Operator Dashboard   |<-----------------------+
                        +---------------------------+                        |
                              |                       |                          |
                [Select Report Queue] |                       | [Select API Health]      |
                              v                       v                          |
                  +--------------------+  +--------------------+               |
                  | 8.0 Report Action  |  | 9.0 Health & Cache |               |
                  |   & Override Panel |  |   Telemetry View   |               |
                  +--------------------+  +--------------------+               |
                              |                       |                          |
                  | [Submit Override]     | [Trigger Manual Refresh] |
                              v                       v                          |
                  +--------------------+  +--------------------+               |
                  | 8.1 Confirm Update |  | 9.1 Data Refreshed |---------------+
                  +--------------------+  +--------------------+
```

---

## 6. Technology Stack Discussion Report

### 6.1 Uploaded Materials Summary
The system analysis artifacts for **ParkChoiceSG** specify a cross-platform mobile client for Singapore drivers requiring high-frequency public API polling (LTA DataMall, Data.gov.sg, OneMap, Google Maps), anonymous client operations, and an authenticated administrative portal for manual overrides and error queue processing.

### 6.2 Prompt & Response Log

**Prompt Submitted:**
> *"Based on the uploaded design materials and BCE analysis for ParkChoiceSG, recommend a technology stack appropriate for an entry-level software engineering team. We are familiar with Java, React, and modular backend architectures, and require clean separation between public mobile queries and administrative workflows."*

**AI Chat Recommendations:**
1. **Frontend**: **Flutter (Dart)** for cross-platform Android/iOS compilation with native navigation handoff support.
2. **Backend**: **Spring Boot (Java)** or **FastAPI (Python)** to provide REST endpoints, JWT-secured operator routing, and async background polling.
3. **In-Memory Cache**: **Redis** for 60-second LTA lot caching, rate-limit counters, and transient matrix lookups.
4. **Relational Database**: **PostgreSQL** for persistent storage of carpark coordinates, rate schedules, operator audit logs, and error reports.
5. **Mapping / Geocoding**: **OneMap API** for Singapore postal/geocoding resolution and **Google Routes Matrix API** for routing distances.

---

### 6.3 Technical Justification of Selected Middleware: PostgreSQL

> **Selected Technology:** **PostgreSQL (Relational Database Management System)**
>
> **Written Opinion:**
> Integrating **PostgreSQL** provides the ACID compliance necessary to ensure manual operator overrides immediately take precedence and remain protected against scheduled daily data synchronizations. For a student software engineering team, PostgreSQL offers structured schema enforcement and relational integrity across carpark metadata, operator audit records, and user error queues with minimal operational overhead. Its native spatial capabilities (PostGIS) also provide a robust fallback for candidate radius filtering, reducing reliance on chargeable external map services within student tier constraints.
