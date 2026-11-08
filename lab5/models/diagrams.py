"""PlantUML sources for the final implementation views."""

STYLE = '''
skinparam backgroundColor white
skinparam defaultFontName Arial
skinparam defaultFontSize 15
skinparam shadowing false
skinparam roundcorner 10
skinparam linetype ortho
skinparam nodesep 45
skinparam ranksep 45
skinparam ArrowColor #243B4A
skinparam classBackgroundColor #F0F5F7
skinparam classBorderColor #243B4A
skinparam classAttributeIconSize 0
skinparam packageBackgroundColor white
skinparam packageBorderColor #A8BAC4
skinparam stateBackgroundColor #F0F5F7
skinparam stateBorderColor #243B4A
skinparam noteBackgroundColor #FFF6DE
skinparam noteBorderColor #C39A3B
hide empty members
'''

# name, title, source paths, diagram body, explanatory caption
DIAGRAMS = [
('use-cases-core', 'Use-case model: connected application and collection',
 'backend/app.py; recommendation.py; data-pipeline/collect_live.py; Flutter screens', r'''
left to right direction
actor "Anonymous driver" as Driver
actor Operator
actor "Collection operator / scheduler" as Collector
rectangle "ParkChoiceSG - implemented scope" {
 usecase "UC-01\nRequest recommendation" as U1
 usecase "UC-02\nInspect result information" as U2
 usecase "UC-19\nView marker map" as U19
 usecase "UC-03\nOpen external navigation" as U3
 usecase "UC-05\nAuthenticate operator" as U5
 usecase "UC-10\nCollect availability" as U10
 U1 -[hidden]down- U2
 U2 -[hidden]down- U19
 U19 -[hidden]down- U3
 U5 -[hidden]down- U10
}
actor OneMap
actor "External navigation / OS" as Nav
actor "HDB / LTA / URA feeds" as Feeds
Driver -- U1
Driver -- U2
Driver -- U19
Driver -- U3
Operator -- U5
Collector -- U10
U1 -- OneMap
U19 -- OneMap
U3 -- Nav
U10 -- Feeds
note bottom of U1
HDB forecast ranking and separate
current-reading fallback have
different eligibility conditions.
end note
''', 'Associations show external participation. Result inspection/map/navigation require returned candidate data; they do not imply separate backend services. OneMap supplies search, routes and tiles.'),
('use-cases-partial', 'Use-case model: partial and prototype functions',
 'Flutter PreferencesScreen, ParkingSessionTrackerScreen, AdminPanelScreen', r'''
left to right direction
actor "Anonymous driver" as D
actor Operator as O
rectangle "Partial device-side functions" #FFF6DE {
 usecase "UC-11 Preferences\nAppearance persists; other controls local" as P
 usecase "UC-12 Saved locations\nIn-memory sample/edit list" as S
 usecase "UC-14 Start session\nInternal manager; no complete UI entry" as T
 usecase "UC-15 Extend session\nModal feedback only" as E
 usecase "UC-16 End session\nClear active in-memory stay" as X
 usecase "UC-17 Session history\nSample and screen-local entries" as H
 usecase "UC-18 Erase data\nResets two controls only" as R
}
rectangle "Prototype console - no server writes" #FFF6DE {
 usecase "UC-06 Sample alerts" as A
 usecase "UC-07 Local override list" as V
 usecase "UC-08 Sample health fields" as F
 usecase "UC-09 Refresh feedback" as Q
}
D -- P
D -- S
D -- T
D -- E
D -- X
D -- H
D -- R
O -- A
O -- V
O -- F
O -- Q
note bottom of F
Console entry uses UC-05's app gate.
There is no administrative token or
authorized write endpoint.
end note
''', 'These functions remain in the requirements inventory with their precise implementation limits. A local control or sample record does not establish durable persistence or a provider operation.'),
('use-cases-deferred', 'Use-case model: deferred requirements',
 'Requirements inventory and implementation comparison', r'''
left to right direction
actor "Anonymous driver" as D
rectangle "Deferred requirements" #FFF6DE {
 usecase "UC-04\nSubmit error report" as R
 usecase "UC-13\nManage favourites" as F
}
D -- R
D -- F
note right of R
No connected submission form,
report persistence or report ID.
end note
note right of F
No connected favourites list
or durable Favourite repository.
end note
''', 'Other unfinished extensions are identified under their existing partial use cases: durable saved places/history, authenticated operator writes, complete erasure and reminder scheduling. No requirement is silently treated as completed.'),
('class-recommendation', 'Key classes: recommendation coordination',
 'backend/recommendation.py; app.py; scoring.py; parking_api.dart', r'''
top to bottom direction
class ParkingApi <<Flutter adapter>> {
 +destinations(query: String): Future<List>
 +recommend(origin, destination, durationMinutes, rankingMode): Future<Map>
}
class "app module" as App <<FastAPI functions>> {
 +recommendations(body: RecommendationInput): dict
 +destinations(body: SearchInput): dict
}
class RecommendationController <<control>> {
 +router: RoutingProvider
 +predictor: AvailabilityPredictor
 +recommend(request: TripRequest): dict
}
class TripRequest <<frozen dataclass>> {
 +origin: Coordinate
 +destination: Coordinate
 +duration_minutes: int
 +candidate_limit: int = 3
 +radius_meters: int = 1500
 +payment_method: str
 +ranking_mode: str
}
interface RoutingProvider {
 +route(start: Coordinate, end: Coordinate, mode: str): RouteEstimate
}
interface AvailabilityPredictor {
 +ready: bool
 +predict(request: PredictionRequest): Prediction
}
class "recommendation helpers" as Helpers <<module functions>> {
 +shortlist(connection, request): list
 +quote_arrivals(connection, candidates, request): dict
 +current_fallback(candidates, request): list
}
class "scoring module" as Scoring <<functions>> {
 +score_candidate(..., ranking_mode): dict
 +rank_candidates(candidates, ranking_mode): list
}
ParkingApi ..> App : HTTP POST
App ..> RecommendationController : constructs per request
RecommendationController ..> TripRequest : validated input
RecommendationController "1" --> "1" RoutingProvider : router
RecommendationController "1" --> "1" AvailabilityPredictor : predictor
RecommendationController ..> Helpers : calls
RecommendationController ..> Scoring : gates then scores
''', 'Python modules are labelled as functions rather than invented service classes. The controller receives one router and one predictor. TripRequest holds two validated Coordinate values.'),
('class-routing-model', 'Key classes: routing and prediction contracts',
 'backend/onemap_adapter.py; onemap_auth.py; model_adapter.py; prediction.py; ml/service/', r'''
top to bottom direction
interface RoutingProvider {
 +route(start, end, mode): RouteEstimate
}
class OneMapClient <<adapter>> {
 +from_env(): OneMapClient
 +search(query: str): SearchResult
 +route(start, end, mode): RouteEstimate
}
class OneMapTokens {
 +get(): str
}
class Coordinate <<frozen value>> {
 +latitude: float
 +longitude: float
 +query_value(): str
}
class RouteEstimate <<frozen value>> {
 +status, mode: str
 +distance_meters: float?
 +duration_seconds: float?
 +requested_at, retrieved_at: datetime
 +estimated_arrival_at: datetime?
}
interface AvailabilityPredictor {
 +ready: bool
 +predict(request: PredictionRequest): Prediction
}
class HdbModelClient <<HTTP adapter>> {
 +supported_agencies = (HDB,)
 +current_readings(ids: list): dict
 +predict(request): Prediction
}
class PendingPredictor {
 +ready = false
 +predict(request): Prediction
}
class PredictionRequest <<frozen value>> {
 +agency, carpark_id: str
 +issued_at, arrival_at: datetime
}
class Prediction <<frozen value>> {
 +status, agency, carpark_id: str
 +issued_at, arrival_at: datetime
 +p_free: float?
 +confidence, model_version: str?
 +history_cutoff: datetime?
 +mode, fallback_reason: str?
}
RoutingProvider <|.. OneMapClient
OneMapClient --> OneMapTokens : token cache
OneMapClient ..> Coordinate
OneMapClient ..> RouteEstimate : returns
AvailabilityPredictor <|.. HdbModelClient
AvailabilityPredictor <|.. PendingPredictor
HdbModelClient ..> PredictionRequest : validates horizon
HdbModelClient ..> Prediction : normalizes response
PendingPredictor ..> Prediction : unavailable status
''', 'OneMapClient implements the routing Protocol structurally. HdbModelClient accepts only HDB short-mode probability forecasts at 15-90 minute horizons. Service failures and unsupported forecasts become explicit statuses.'),
('class-pricing', 'Key classes and functions: stay pricing',
 'backend/comparison.py; pricing.py; database/rate schedule definitions', r'''
top to bottom direction
class CandidateStay <<frozen dataclass>> {
 +agency, carpark_id: str
 +arrival_at: datetime
 +duration_minutes: int
 +payment_method: str
 +first_entry: bool?
}
class "comparison module" as C <<functions>> {
 +compare_stay_options(connection, stays): list
 +compare_candidate_stays(connection, stays): list
 -_load_context(connection, earliest, latest, identities)
}
class "pricing module" as P <<functions>> {
 +quote_schedule(schedule, rules, arrival, duration, holidays, years): PriceQuote
 +window_at(rule, instant, holidays): interval?
}
class PriceQuote <<frozen dataclass>> {
 +status: str
 +amount_cents: int?
 +payment_method, source_url: str?
 +note: str?
 +schedule_id: int?
 +breakdown: tuple
}
class "rate_schedules" as S <<database record>> {
 +schedule_id: bigint [PK]
 +agency, carpark_id: text [FK]
 +valid_from, valid_until: timestamptz
 +review_status, calculator_key: text
 +reviewed_at: timestamptz
 +calculator_config: jsonb
}
class "rate_schedule_rules" as R <<database record>> {
 +rule_id: bigint [PK]
 +schedule_id: bigint [FK]
 +day_type: text
 +start_time, end_time: time
 +rule_kind: text
 +amount_cents, unit_minutes: int
 +priority, review_status, calculation
}
CandidateStay ..> C : request options
C ..> S : read version
S "1" -- "0..*" R : rules
C ..> P : calls per option
P ..> PriceQuote : returns
note bottom of P
Unknown, stale, unsupported or conflicting rules
produce an unavailable quote, not zero cost.
end note
''', 'Money is stored in integer SGD cents. The calculator applies day/time windows, priority, billing increments, grace, tiers and supported caps. Neighbouring-minute arrival quotes are compared before a cost is eligible for ranking.'),
('class-client-local', 'Key classes: Flutter boundaries and local state',
 'parkchoice_flutter/lib/screens/; services/; models/ranking_mode.dart', r'''
top to bottom direction
class CarparkSearchScreen <<StatefulWidget>>
class _CarparkSearchScreenState <<State>> {
 -_origin, _destination: Map?
 -_duration: int
 -_rankingMode: RankingMode
 -_result: Map?
 -_findParking(): Future<void>
 -_useCurrentLocation(): Future<void>
 -_openMap(...): Future<void>
}
class ParkingApi <<HTTP adapter>>
class CarparkMapScreen <<StatefulWidget>> {
 +origin, destination: Map
 +carparks: List<Map>
}
class PreferencesScreen <<StatefulWidget>>
class AppThemeController <<ChangeNotifier>> {
 +instance: AppThemeController
 +themeMode: ThemeMode
 +load(): Future<void>
 +setThemeMode(mode): Future<void>
}
class ParkingSessionTrackerScreen <<StatefulWidget>>
class ParkingSessionManager <<ValueNotifier>> {
 +instance: ParkingSessionManager
 +currentSession: ParkingSession?
 +startSession(...): bool
 +endSession(): void
}
class ParkingSession {
 +carparkName, location: String
 +hourlyRate: double
 +startTime: DateTime
 +duration: Duration
 +runningCost: double
}
CarparkSearchScreen *-- _CarparkSearchScreenState
_CarparkSearchScreenState --> ParkingApi
_CarparkSearchScreenState ..> CarparkMapScreen : snapshots input
PreferencesScreen --> AppThemeController : persists appearance
ParkingSessionTrackerScreen --> ParkingSessionManager : listens
ParkingSessionManager "1" o-- "0..1" ParkingSession : active stay
note bottom of PreferencesScreen
Saved labels, vehicle and walking controls
remain screen-local prototype state.
end note
note bottom of ParkingSession
Linear hourly-rate display; not the backend tariff engine.
No durable history or complete start-session UI.
end note
''', 'Widget classes own their State objects. The session manager holds at most one in-memory stay. Only appearance uses persistent preference storage; other local-data requirements remain partial or deferred.'),
('class-operator', 'Key classes: operator access',
 'operator_login_screen.dart; operator_session.dart; backend/app.py; operator_auth.py', r'''
top to bottom direction
class OperatorLoginScreen <<StatefulWidget>>
class _OperatorLoginScreenState <<State>> {
 -_submitting, _isNavigating: bool
 -_signIn(): Future<void>
}
class ParkingApi <<HTTP adapter>> {
 +operatorLogin(username, password): Future<bool>
}
class "app module" as A <<FastAPI function>> {
 +operator_login(body: OperatorLoginInput): dict
}
class "operator_auth module" as V <<functions>> {
 +verify_operator(username, password, env): bool
 +hash_password(password, salt?, iterations): str
}
class OperatorSession <<ValueNotifier<bool>>> {
 +instance: OperatorSession
 +signedIn: bool
 +signIn(): void
 +signOut(): void
}
class AdminPanelScreen <<StatefulWidget>>
class "Private environment" as E <<configuration>> {
 OPERATOR_USERNAME
 OPERATOR_PASSWORD_HASH
}
OperatorLoginScreen *-- _OperatorLoginScreenState
_OperatorLoginScreenState --> ParkingApi : submits
ParkingApi ..> A : POST /operator/login
A ..> V : verifies
V ..> E : reads
_OperatorLoginScreenState --> OperatorSession : success if screen active
OperatorSession ..> AdminPanelScreen : app entry gate
note bottom of OperatorSession
Process-local boolean. No server token,
account table or administrative write authorization.
end note
''', 'The configured credential is verified server-side. The successful response enables a client-side console entry gate for the app process. Console sample actions do not imply authenticated backend administration.'),
('data-model', 'Persistent data model: identity, evidence and tariffs',
 'backend/database/schema.sql and schema_v2.sql through schema_v8.sql', r'''
top to bottom direction
entity "carpark_identities" as I {
 * agency: text [PK]
 * carpark_id: text [PK]
 --
 display_name, address: text
}
entity "source_carpark_codes" as C {
 * feed, source_agency, source_code [PK]
 --
 agency, carpark_id [FK]
 match_method, verified_at
}
entity "ingestion_runs" as G {
 * run_id: uuid [PK]
 --
 retrieved_at: timestamptz
 manifest: jsonb
}
entity "carpark_metadata_evidence" as M {
 * run_id, source, agency, carpark_id [PK]
 --
 agency, carpark_id [FK]
 run_id [FK]
 captured_at, location_status
 location_points, latitude, longitude
}
entity "provider_availability_snapshots" as O {
 * run_id, agency, carpark_id, lot_type [PK]
 --
 feed, retrieved_at, lots_available
 attributes: jsonb
}
entity "rate_schedules" as S {
 * schedule_id [PK]
 --
 agency, carpark_id [FK]
 source_run_id [FK, optional]
 source, validity, review, calculator
}
entity "rate_schedule_rules" as R {
 * rule_id [PK]
 --
 schedule_id [FK]
 day/time, amount_cents, calculation
}
entity "tariff_source_evidence" as T {
 * evidence_id [PK]
 --
 agency, carpark_id [FK]
 capture_key, captured_at, content_sha256
 published_facts, review_status
}
I ||--o{ C : source mapping
I ||--o{ M : metadata
G ||--o{ M : capture
G ||--o{ O : provider capture
I ||--o{ S : tariff versions
S ||--o{ R : rules
I ||--o{ T : price provenance
note bottom of O
HDB direct history also uses carparks and
availability_observations. Normalized views
resolve canonical comparison/training inputs.
end note
''', 'This selected physical-data view omits secondary columns and lookup tables. HDB direct history and provider captures remain separate provenance paths. Device preferences, session samples and operator app state are not backend driver-account tables.'),
('architecture', 'System architecture and process boundaries',
 'backend/app.py; recommendation.py; ml/service/; data-pipeline/; Flutter app', r'''
left to right direction
rectangle "Android / Flutter" as Phone {
 component "Search, cards and map\nAnonymous driver" as UI
 component "ParkingApi" as Client
 component "Device GPS / permissions" as GPS
 component "SharedPreferences\nappearance only" as Local
 UI --> Client
 UI --> GPS
 UI --> Local
}
rectangle "Recommendation process :8000" as Backend {
 component "FastAPI\n/destinations /recommend\n/operator/login /health" as API
 component "RecommendationController\nshortlist -> routes -> quotes\n-> forecasts -> gate -> score" as Control
 component "Pricing / comparison\nScoring / forecast audit" as Helpers
 API --> Control
 Control --> Helpers
}
rectangle "Inference process :8001" as Model {
 component "HdbModelClient HTTP boundary\nEngine + calibrated artifacts" as Engine
 component "LiveFeed cache\nrecent HDB history" as Cache
 Engine --> Cache
}
database "Supabase PostgreSQL\nprivate parking_data schema" as DB
component "OneMap\nsearch / drive / walk / tiles" as OM
component "HDB / LTA / URA\npublic source feeds" as Feeds
component "Separate collector\nclean -> archive -> ingest" as Collect
component "External navigation\nGoogle Maps URL / OS" as Nav
Client --> API : HTTP
API --> OM : place search
Control --> OM : drive/walk routes
UI --> OM : map tiles
UI --> Nav : explicit handoff
Control --> DB : short read-only stages
Control --> Engine : /predict and /current
Cache --> Feeds : HDB only
Feeds --> Collect : captures
Collect --> DB : transactional writes
note bottom of Backend
Private keys stay server-side. A search does not
start database collection or retrain the model.
end note
''', 'The inference service polls HDB into its own recent-history cache; the separate database collector maintains stored evidence and exports. Local development uses HTTP and USB port forwarding. Public deployment/authenticated admin operations are outside this baseline.'),
('sequence-recommendation', 'UC-01 request sequence',
 'backend/recommendation.py; comparison.py; model_adapter.py; Flutter ParkingApi', r'''
skinparam linetype polyline
actor Driver
boundary "Search / ParkingApi" as UI
control "FastAPI / Controller" as API
database "PostgreSQL / comparison" as DB
participant OneMap
participant "HdbModelClient / service" as ML
Driver -> UI : choose places, stay and mode
UI -> API : POST /recommend
API -> API : validate TripRequest
API -> DB : read eligible location pool
DB --> API : canonical identities + coordinates
API -> API : Haversine radius; keep nearest 3
note over API,DB : Close read transaction before route calls
loop each shortlisted candidate
 API -> OneMap : drive(origin, carpark); walk(carpark, destination)
 OneMap --> API : duration, distance, measurement times
end
API -> API : common departure + candidate driving duration
API -> DB : quote floor/ceiling arrival and full stay
DB --> API : supported price range or status
API -> ML : /current for HDB shortlist
ML --> API : source-timestamped current evidence
loop each candidate with driving arrival
 API -> ML : /predict(candidate ID, arrival_at)
 ML --> API : p_free, mode, confidence, issue/history time or failure
 API -> API : validate and audit forecast; collect exclusions
end
API -> API : eligibility gates; selected-mode scores; stable rank
alt forecast candidates eligible
 API --> UI : ranked forecasts + evidence + exclusions
else no forecast ranks and current fallback permitted
 API --> UI : separate current-reading list + explicit notice
else no usable candidates
 API --> UI : unavailable status + reasons
end
UI --> Driver : display cards / fallback / retry
''', 'The shortlist is chosen before route/model eligibility checks. A failed candidate is not replaced by an additional search. Probability requests can still be evaluated for a candidate whose quote fails; the final gate prevents it from ranking.'),
('sequence-operator', 'UC-05 operator credential sequence',
 'operator_login_screen.dart; parking_api.dart; operator_session.dart; operator_auth.py', r'''
skinparam linetype polyline
actor Operator
boundary OperatorLoginScreen as UI
participant ParkingApi as HTTP
control "POST /operator/login" as API
participant "verify_operator" as Verify
participant OperatorSession as Session
Operator -> UI : enter username/password; Sign in
UI -> UI : require nonempty input; set submitting
UI -> HTTP : operatorLogin(username, password)
HTTP -> API : POST credentials
API -> Verify : configured username + PBKDF2 hash
Verify --> API : valid / invalid / malformed config
alt valid credential
 API --> HTTP : 200 {status: ok}
 HTTP --> UI : true
 alt login screen still active
  UI -> Session : signIn()
  UI --> Operator : open console
 else screen was left
  UI -> UI : discard late completion
 end
else invalid credential
 API --> HTTP : 401
 HTTP --> UI : false
 UI --> Operator : inline error; retry
else configuration or connection failure
 API --> HTTP : 503 or request fails
 HTTP --> UI : exception
 UI --> Operator : sign-in unavailable
end
note over UI,Session
The flag is in process memory. This flow does not issue
a server token or implement administrative write authorization.
end note
''', 'Invalid schema input may return HTTP 422. Duplicate submissions are blocked and leaving the screen prevents a late response from establishing a new app session.'),
('dialog-driver-input', 'Driver dialog map: input and search lifecycle',
 'carpark_search_screen.dart; device_location.dart', r'''
top to bottom direction
[*] --> Search : Open app
state "Search input" as Search {
 Search : entry / anonymous form
 Search : do / origin, destination, stay, mode
}
state "Place selection sheet" as Places
Places : entry / search OneMap matches
state "Foreground location request" as GPS
GPS : do / permission, service and bounded fix
state "Comparing" as Busy
Busy : do / POST /recommend
state "Input / service error" as Error
Search --> Places : Search origin or destination
Places --> Search : Select valid match / store coordinate
Places --> Search : Cancel
Search --> GPS : Use current location
GPS --> Search : [valid fix] / store origin + age + accuracy
GPS --> Error : [denied, off, timeout or failure]
Search --> Error : Find [missing selection or stale GPS]
Search --> Busy : Find [valid selections]
Busy --> Results : [response validated]
Busy --> Error : [network or response failure]
state "Result handling\nSee results/map dialog" as Results
Results --> Search : Change input or mode / clear old results
Error --> Search : Correct input / retry
note right of Busy
Disable conflicting actions while busy.
Ignore late completion after navigation.
end note
''', 'A foreground device fix is one origin input, not continuous tracking. A fix older than two minutes must be refreshed. Manual place selection remains available after location failure.'),
('dialog-driver-results', 'Driver dialog map: results, fallback and navigation',
 'carpark_search_screen.dart; carpark_map_screen.dart; navigation_handoff.dart', r'''
top to bottom direction
[*] --> Response : Validated response
state Response <<choice>>
state "Ranked forecast cards" as Forecast
Forecast : entry / probability + cost + routes
state "Current-reading cards" as Current
Current : entry / explicit fallback notice + source time
state "Unavailable" as Empty
Empty : entry / reasons and retry
Response --> Forecast : [ranked not empty]
Response --> Current : [fallback_ranked not empty]
Response --> Empty : [no usable ranking]
state "OneMap marker view" as Map
Map : entry / snapshot selected inputs and candidates
Map : do / select marker, external navigation
Forecast --> Map : View map
Current --> Map : View map
Map --> Forecast : Back [forecast screen retained]
Map --> Current : Back [fallback screen retained]
state "External navigation" as Nav
state "Navigation error" as NError
Map --> Nav : Navigate [valid destination and OS opens URL]
Map --> NError : Navigate [invalid coordinate or handoff fails]
NError --> Map : Dismiss / retry
Nav --> Map : Return to app
Forecast --> [*] : Change input/mode / return to Search
Current --> [*] : Change input/mode / return to Search
Empty --> [*] : Retry / return to Search
''', 'Result cards are the current inspection boundary. There is no separate complete detail screen, report form or automatic start-parking transition. The map can display returned candidates, including candidates excluded from ranking.'),
('dialog-local', 'Driver dialog map: preferences and tracker',
 'preferences_screen.dart; parking_session_tracker_screen.dart; local state services', r'''
left to right direction
state "Bottom navigation" as Tabs
state "Preferences" as Pref
Pref : do / choose theme; edit local controls
state "Add saved location" as Add
state "Erase confirmation" as Erase
state "Tracker" as Track
Track : entry / sample history; active session if present
state "End confirmation" as End
state "Extend modal" as Extend
Tabs --> Pref : Preferences tab
Pref --> Tabs : Other tab
Pref --> Add : Add location
Add --> Pref : Save [nonblank label/address] / add local entry
Add --> Pref : Cancel
Pref --> Erase : Erase data
Erase --> Pref : Confirm / reset vehicle and walking controls
Erase --> Pref : Cancel
Tabs --> Track : Tracker tab
Track --> Tabs : Other tab
Track --> End : End [active session]
End --> Track : Confirm / clear stay; add screen-local entry
End --> Track : Cancel
Track --> Extend : Extend [active session]
Extend --> Track : Apply / feedback only
Extend --> Track : Cancel
note bottom of Pref
Appearance persists; saved lists and other
controls are screen-local. No complete erasure.
end note
note bottom of Track
No complete UI start flow, durable history,
notification scheduling or tariff repricing.
end note
''', 'This map includes prototype flows because they remain visible in the app. Their labels state the actual effect of each action; modal feedback is not modelled as durable storage or a completed notification operation.'),
('dialog-operator', 'Operator dialog map: access and prototype console',
 'operator_login_screen.dart; admin_panel_screen.dart; operator_session.dart', r'''
top to bottom direction
[*] --> Gate : Admin tab
state Gate <<choice>>
state "Login form" as Login
state "Signing in" as Busy
state "Login error" as Error
state "Operator console" as Console
Console : entry / sample alerts, health and override list
Gate --> Console : [signedIn in this app process]
Gate --> Login : [not signed in]
Login --> Busy : Submit [fields populated]
Busy --> Console : [200 and login still active] / set app flag
Busy --> Error : [401, 422, 503, timeout or network error]
Error --> Login : Correct / retry
state "Local override modal" as Override
Console --> Override : Add override
Override --> Console : Apply / update local list
Override --> Console : Cancel
Console --> Console : Resolve alert / local status only
Console --> Console : Refresh source / feedback only
Console --> Login : Sign out / clear flag
Busy --> [*] : Leave screen / discard late success
Login --> [*] : Return to driver screen
Console --> [*] : Driver tab
note right of Console
No server report/override/refresh writes.
Restart clears the operator app flag.
end note
''', 'The app gates console entry with a successfully verified credential. Its sample actions remain isolated from the recommendation database and do not constitute administrative authorization.'),
('collection-lifecycle', 'Collection, cleaning and training evidence lifecycle',
 'data-pipeline collectors, metadata cleaner, export_training.py; ml training/service', r'''
top to bottom direction
component "HDB / LTA / URA responses" as Source
artifact "Compressed raw capture\nrun ID + hash + retrieval time" as Raw
component "Validation and canonical mapping\nagency + carpark_id; quality flags" as Clean
database "Historical observations / metadata\nsource and retrieval timestamps" as DB
artifact "Training export\nknown-at features; later labels" as Export
component "Offline training / chronological evaluation" as Train
artifact "Versioned model artifacts\nclassifier + calibration + model card" as Model
component "Inference service\nrecent HDB history" as Service
artifact "Issued forecast audit\nissue / target / history cutoff" as Issued
artifact "Later outcome matching\ncoverage + Brier + calibration" as Eval
Source --> Raw
Raw --> Clean
Clean --> DB : accepted rows; rejected evidence retained
DB --> Export : generic count-target export
Export ..> Train : optional export path
Raw ..> Train : independent HDB backfill/file path
Train --> Model
Model --> Service
Service --> Issued
Issued --> Eval
Source --> Eval : later source readings
note right of Export
The shipped HDB classifier used the independent
backfill/file pipeline. Do not claim that it was
trained exclusively from PostgreSQL exports.
end note
''', 'Recommendation inference does not retrain the classifier. Forecasts are recorded before target time, and later outcomes are matched with a declared tolerance. Provider feed evidence is not independently verified physical occupancy.'),
]
