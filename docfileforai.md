PROJECT CONTEXT — ParkChoiceSG (NTU SC2006/CE2006/CZ2006 Software Engineering team project)

WHAT WE'RE BUILDING

ParkChoiceSG is a cross-platform mobile app (Flutter) that recommends where to park.

The driver enters a destination, an intended arrival time and an expected parking

duration. The system returns up to five nearby carparks ranked by a weighted score

over four factors: predicted lot availability at the driver's ETA, estimated cost

for the intended stay, driving time under live traffic, and walking distance from

carpark to destination. The top result carries a one-line justification.

THE DIFFERENTIATOR

It does NOT report how many lots are free now — that figure is already stale by the

time the driver arrives. It predicts how many will be free AT ARRIVAL, using our own

accumulated history of availability readings (matched by carpark, day-of-week and

time-of-day bucket), with a stated confidence level (High/Medium/Low) derived from

sample size and variance. This matters because the course brief vetoes proposals that

are "a simple presentation of extracted data" — prediction is what lifts it out of

that category. Treat this as the core of the product in any advice you give.

DATA SOURCES

- LTA DataMall Carpark Availability API — live lot counts, polled every 60 s and

  persisted as the prediction training set. Covers HDB/URA/LTA carparks only; most

  private carparks publish nothing and must be shown as "availability not published".

- data.gov.sg HDB Carpark Information — locations, carpark type, height limits.

- URA / data.gov.sg Carpark Rates — rate schedules by vehicle type, day type and

  time band, including free periods, grace periods and charge caps.

- Google Maps Platform — Distance Matrix (driving time in traffic, walking distance),

  Places (destination autocomplete), map rendering.

ARCHITECTURE

Flutter client + thin backend + minimal operator web console.

The defining property: THE BACKEND HOLDS NO USER DATA. There are no accounts, no

registration, no login, no credential store. All user-scoped data — preferences,

saved locations (Home/Work), favourites, search history, parking sessions — lives in

device-local storage (shared_preferences + sqflite). This is a deliberate

privacy-by-design decision under PDPA data minimisation, taken after we judged an

account system to be over-engineering for this product.

The backend exists for three reasons only: (1) custody of the LTA and Google API keys,

which must never be embedded in the client binary; (2) polling and persisting the

availability history that prediction depends on; (3) caching carpark reference data and

controlling external API quota consumption. Datastore is MySQL.

The one remaining credential is a single operator login for the console, held in

server-side configuration, used to triage anonymous user reports, override carpark

records (e.g. mark closed) and monitor integration health.

FEATURE GROUPS

4.1 Preferences and saved locations   4.5 Carpark information and navigation

4.2 Destination input                 4.6 Parking session tracking (timer, accruing

4.3 External data acquisition             cost, local expiry reminder, history)

4.4 Carpark recommendation (core)     4.7 Favourites and anonymous feedback

                                      4.8 Operator administration

EXPLICITLY OUT OF SCOPE

Bay reservation, in-app payment, gantry/IU integration, season parking, EV charging

bay status, cross-device sync or backup, tourist features, weather features.

(The brief vetoes tourist- and weather-oriented applications.)

KEY RISKS AND OPEN QUESTIONS

- Central assumption: occupancy patterns repeat enough by day-of-week and time-of-day

  for prediction to beat the naive current-reading baseline. Testable against logged

  outcomes; if false, the product's differentiator collapses.

- Availability logging must run from week one or there is no training data by the demo.

- Carpark identifier reconciliation between LTA DataMall and the HDB dataset is an

  unresolved integration risk.

- Undecided: scoring weights, prediction bucket width (15 or 30 min), minimum sample

  threshold, public holiday calendar source, max search radius, travel-time cache

  bucket width.

TARGETS WE'VE COMMITTED TO

Recommendation in under 3 s at p95 on 4G; availability no more than 90 s stale; cost

estimates within ±S$0.50; predictions within ±20% for at least 70% of cases; graceful

degradation to cached data with a visible staleness indicator whenever an external API

fails; three interactions from home screen to recommendation.

COURSE CONTEXT

Ten-week team project, 4–6 members, traversing the full SDLC. Lab 1 (requirements

elicitation) is complete: SRS in the IEEE-style template, use case model with

include/extend/generalisation, data dictionary, UI mockups, traceability matrix.

Lab 2 is requirements analysis (complete use case descriptions, entity class diagram,

boundary and control classes, sequence diagrams, dialog map). Lab 3 is design and

implementation, Lab 4 testing, Lab 5 live demo. Documentation quality and visible

SDLC rigour are graded, not just the working app.

HOW TO HELP

Assume the above is settled unless we say otherwise. Challenge assumptions where you

think we're wrong — particularly the prediction assumption and the no-accounts

decision. Prefer concrete, testable specifics over generalities.