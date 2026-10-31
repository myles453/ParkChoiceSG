# Lab 4 review package

The working code was reconciled with upstream main on 31 October; see
[integration verification](../backend/validation/INTEGRATION-2026-10-31.md).
The PDFs, evidence and source ZIP below are dated 26 October review snapshots.
Use the repository's current working directories for the latest implementation.

Prepared 26 October 2026 from upstream main `790ac78`, reconciled with the newer
local ranking/frontend work. Application code stays in the permanent working
directories; this folder contains submission evidence and review documents.

| File | Purpose |
|---|---|
| [Testing report](output/pdf/Testing-Report.pdf) | Partitions, boundaries, actual results and verified basis-path graphs. |
| [Android demo script](output/pdf/Android-Demo-Script.pdf) | Live sequence, phone setup/recovery and recording plan. |
| [Coding-agent reflections](output/pdf/Coding-Agent-Reflections.pdf) | Two executed experiments, iterations, outcomes and limits. |
| [Source snapshot](submission/ParkChoiceSG-Lab4-Source.zip) | Curated source/model/assets; no private config, captures or generated builds. |
| Local Android arm64 debug APK (not tracked; build using [Android setup](../parkchoice_flutter/ANDROID-TESTING.md)) | Phone prototype built for API URL http://127.0.0.1:8000 with USB reverse. |
| [Traceability](TRACEABILITY.md) | Use cases to implementation and actual test coverage. |
| [Completion checklist](CHECKLIST.md) | Remaining phone checks, video, attribution and team review. |

Editable reports are the Markdown files in this folder. Machine-readable rows,
source hashes and experiment records are under `evidence/`; diagram sources and
PNG/SVG exports are under `diagrams/`. `tmp/` is ignored experiment scratch space.

Reproduce offline evidence using the backend Python environment:

```powershell
python lab4/collect_evidence.py
```

Regenerate PDFs with `python lab4/prepare_deliverables.py` in an environment with
reportlab, Pillow, pypdf and PyMuPDF, plus Java and the local PlantUML jar configured in
that script. Use the installed PDF authoring workflow before regeneration.

This is a review package, not a claim that all planned features or device checks
are complete. Operator sign-in checks credentials and gates a prototype console;
admin actions are not authenticated server operations. The actual Android device
acceptance and five-minute video remain pending. Author names are intentionally
omitted for now, as requested. No GitHub push is performed by this generator.
