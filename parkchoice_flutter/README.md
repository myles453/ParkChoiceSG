# ParkChoiceSG Flutter UI

**15 October integration:** the search screen now calls the recommendation backend
using real selected places, routed distances, supported total-stay prices and a
labelled current-availability baseline. Drivers open directly to parking search;
there are no driver accounts, login screens or registration screens.
Other screens remain existing prototype work. See the
[backend runbook](../backend/BACKEND-RUNBOOK.md). Only `PARKING_API_URL` belongs in
Flutter configuration; database/provider secrets stay on the backend.

This folder contains the standalone Flutter UI prototype for ParkChoiceSG. It is kept outside the Lab 2 deliverables so the product interface can evolve independently.

## Included flows

- Anonymous place selection and live backend carpark comparison
- Prototype parking session tracking, reminders, and extensions (not durable storage)
- Prototype saved destinations and vehicle preferences
- Persisted System, Light, and Dark appearance modes
- Prototype admin alerts, data-source health, and carpark overrides

## Visual styling

The app uses bundled Public Sans fonts (400Ã¢â‚¬â€œ700), forest green accents, and
separate light and dark surface palettes. Shared colours and corner radii live
in `lib/constants.dart`, component themes in `lib/main.dart`, and reusable
surfaces and typography treatments in `lib/widgets/app_ui.dart`.
Font source and licences are included in `assets/fonts/public_sans/`.

## Run locally

```powershell
flutter pub get
flutter run
```

Select an Android emulator or another connected Flutter device when prompted.

## Validate

See [the frontend stability review](FRONTEND-VERIFICATION.md) for reproduced
crash cases, regression tests and the remaining phone checks.

```powershell
flutter analyze
flutter test
flutter build apk --debug
```

Generated build outputs, local SDK paths, IDE metadata, and caches are intentionally excluded from version control.
