# Lab 3 data pipeline and model handover

The backend data work lives in `data-pipeline/`; the Flutter project remains in the repository's existing app folders.

- [Model-training handover](MODEL-TRAINING-HANDOVER.md): prediction target, fields, timestamp semantics, training/export limitations and responsibilities.
- [Periodic collection](data-pipeline/PERIODIC-COLLECTION.md): the model teammate's configurable collector, initially every five minutes.
- [Pipeline setup](data-pipeline/README.md): Python dependencies, private configuration and collection/export commands.
- [Data contract](data-pipeline/DATA-CONTRACT.md): canonical identities, source/retrieval timestamps, database views and pricing semantics.
- [Latest pricing verification](data-pipeline/PRICING-WORKFLOW-2026-10-02.md): measured coverage and unresolved tariff cases.

Start from `lab3/data-pipeline` with Python 3.12 and the pinned dependencies. Fill a private `.env` using the blank `.env.example`; credentials must be obtained privately, not from Git. The team Supabase schema is already applied. Schema/seed SQL is included for reproducibility, not an instruction to replay dated seeds into the existing database.

```powershell
.\.venv\Scripts\python.exe collect_periodic.py
```

The collector runs in the foreground until Ctrl+C. Raw captures, exported training CSVs, session logs, the local Python environment and credentials are ignored by Git. Share an agreed data export separately. The sparse pilot is not sufficient training history; regular collection and chronological validation are required.
