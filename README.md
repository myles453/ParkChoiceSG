# ParkChoiceSG

Singapore parking recommendations using supported stay prices, routed travel and
walking distances, and the probability of a free HDB car lot at arrival.

## Submission index

| Material | Location |
|---|---|
| Final descriptions and design diagrams | [Final SRS models PDF](lab5/output/pdf/ParkChoiceSG-Final-SRS-Models.pdf) |
| Editable diagrams and image exports | [PlantUML, SVG and PNG](lab5/diagrams/) |
| Model/document inventory | [Lab 5 package](lab5/README.md) |
| Final test commands and results | [Submission verification](lab5/TESTING.md) |
| Requirements-to-code/test mapping | [Traceability](lab5/TRACEABILITY.md) |
| Detailed black-box/basis-path evidence | [Lab 4 testing report](lab4/output/pdf/Testing-Report.pdf) |
| Setup and runtime | [Backend](backend/README.md), [Android](parkchoice_flutter/ANDROID-TESTING.md), [backup setup](parkchoice_flutter/BACKUP-LAPTOP.md) |
| Data schema and collection | [Schema](data-pipeline/SCHEMA.md), [collection](data-pipeline/README.md) |
| Model source and evaluation | [HDB model](ml/README.md), [evaluation](ml/reports/evaluation.md) |
| Design rationale | [Project decisions](PROJECT-DECISIONS.md) |

The final models PDF supports the team's assembled SRS. The assembled SRS and
actual 5-7 minute demo-video link must be supplied by the team. Individual peer
reviews use the course's private submission process.

## Application source

| Directory | Responsibility |
|---|---|
| [`backend/`](backend/README.md) | FastAPI, coordination, pricing, ranking and backend tests. |
| [`parkchoice_flutter/`](parkchoice_flutter/README.md) | Active Flutter application and widget/service tests. |
| [`data-pipeline/`](data-pipeline/README.md) | HDB/LTA/URA collection, cleaning, provenance and exports. |
| [`ml/`](ml/README.md) | HDB training/inference source, committed artifacts and tests. |
| [`ml_lta_ura/`](ml_lta_ura/README.md) | Experimental models; excluded from app probability ranking. |
| [`lab5/`](lab5/README.md) | Final model exports, editable sources and submission verification. |

Use Python 3.12 for the backend/model. Run inference on port 8001 and the
recommendation API on port 8000. Follow the backend instructions to create private
configuration from blank examples. Flutter uses
`--dart-define=PARKING_API_URL=http://127.0.0.1:8000` for the documented USB-forwarded
Android setup. Provider/database credentials remain server-side and excluded from Git.

Drivers are anonymous. Search includes three scoring modes, foreground location,
OneMap markers and external navigation. Operator credential checking is connected;
console administration, durable saved-data/session features and full erasure remain
partial or deferred as identified in the final inventory.

Earlier `lab1/`, `lab2/`, `lab 3/` and `lab4/` material preserves prior deliverables
and experiments. The older Flutter copy and dated ZIP/APK snapshots are not the
active application or final source baseline.
