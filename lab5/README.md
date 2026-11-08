# Final models and submission material

Open [ParkChoiceSG-Final-SRS-Models.pdf](output/pdf/ParkChoiceSG-Final-SRS-Models.pdf)
for material to insert into the final SRS/design documentation:

- All 19 use-case descriptions with implemented/partial/deferred status.
- Three use-case views, five key-class views and the selected persistent data model.
- Architecture, UC-01/UC-05 request sequences, four dialog maps and the collection
  lifecycle: 17 diagram views in total.
- Scoring formulas, evidence definitions and implementation/test traceability.

The PDF uses searchable text and vector diagrams. Individual SVG/PNG exports and
PlantUML semantic sources are in [diagrams/](diagrams/). Fixed connector layouts
are implemented in `layouts.py`; automatic PlantUML layouts need not be
pixel-identical to the published SVG/PNG exports.

[Editable descriptions](models/USE-CASE-DESCRIPTIONS.json) and the
[manifest/page index](models/MANIFEST.json) accompany the PDF. This material
supports the assembled SRS rather than replacing its complete requirements text.

See [TESTING.md](TESTING.md) for executable commands/results and
[TRACEABILITY.md](TRACEABILITY.md) for source/test mapping. Earlier test and
exercise records retain their dated evidence boundaries under `../lab4/`.

## Rebuild

Authoring requires Python with `reportlab`, `svglib`, `pymupdf`, Java and PlantUML:

```powershell
python lab5/build_srs_models.py --plantuml-jar PATH_TO_PLANTUML_JAR
```

Fonts use Windows Arial. Checked-in SVG/PNG/PDF files can be read on other systems
without running the authoring script. Runtime dependencies are separate.

## Remaining team submission items

- Insert these models into the assembled SRS and link the final document.
- Add the actual accessible 5-7 minute video link and any meeting minutes kept.
- Complete individual peer reviews using the separate course instructions.

Source/tests and this documentation do not establish that those separately
supplied items have already been uploaded.
