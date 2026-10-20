# ParkChoiceSG

Singapore parking recommendations using source-backed stay prices, routed travel and
walking distances, and an HDB model predicting the chance of a free lot at arrival.

## Working directories

| Directory | Purpose |
|---|---|
| [`backend/`](backend/README.md) | Active FastAPI recommendation API, pricing, ranking, database references and validation. |
| [`parkchoice_flutter/`](parkchoice_flutter/README.md) | Active Flutter app connected to the API. |
| [`data-pipeline/`](data-pipeline/README.md) | Shared HDB/LTA/URA collection, cleaning and training export. |
| [`ml/`](ml/README.md) | Supplied HDB model, training code and inference service. |
| [`ml_lta_ura/`](ml_lta_ura/README.md) | Separate experimental retrieval-time models; not enabled in app ranking. |

Start with [backend setup and run commands](backend/README.md). The normal local
workflow runs the model on port 8001, the recommendation API on 8000, and Flutter
with `PARKING_API_URL=http://127.0.0.1:8000`. Provider/database credentials are
private server-side configuration; blank examples are included.

Develop in these working directories. `lab1/`, `lab2/` and the older `lab 3/` copy
are academic/history folders, not the active application source. This change does
not publish the separate local submission PDF/ZIP package.

The working search includes device location, OneMap markers, supported tariff
comparisons, explainable ranking and external navigation. Administration, reporting
and durable local-data screens remain partly prototypes. The probability model and
provisional ranking policy have documented scope and validation limits in `backend/`.
