# Lab 1 Use-Case Artifacts

## Submission Files

- [Rendered use-case diagram](use-case-diagram.svg)
- [Combined use-case descriptions](use-case-descriptions.pdf)

These are the files intended for direct review and submission as the initial use-case model.

## Editable Sources

- [UC-01: Request Carpark Recommendation](UC-01-request-carpark-recommendation.md)
- [UC-02: Inspect Carpark Information](UC-02-inspect-carpark-information.md)
- [UC-03: Open External Navigation](UC-03-open-external-navigation.md)
- [PlantUML diagram source](use-case-model.puml)
- [Combined browser-readable descriptions](use-case-descriptions.html)

The three descriptions cover the initial driver journey from requesting a recommendation to inspecting a result and optionally opening external navigation. UC-01 uses current availability only, one fixed Best Overall score, and up to five results. Prediction and user-selectable ranking presets are possible future enhancements rather than part of the initial model.

## Regenerating the Combined Descriptions

From the repository root, run:

```powershell
.\scripts\generate-use-case-submission.ps1 -Force
```

The generator mirrors the supplied course-template fields and exports the HTML source to PDF. The rendered diagram must be regenerated separately after changing the PlantUML source.
