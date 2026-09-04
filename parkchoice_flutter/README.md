# ParkChoiceSG Flutter UI

This folder contains the standalone Flutter UI prototype for ParkChoiceSG. It is kept outside the Lab 2 deliverables so the product interface can evolve independently.

## Included flows

- Account registration and sign-in
- Carpark search with list and map views
- Parking session tracking, reminders, and extensions
- Saved destinations and vehicle preferences
- Persisted System, Light, and Dark appearance modes
- Admin alerts, data-source health, and carpark overrides

## Run locally

```powershell
flutter pub get
flutter run
```

Select an Android emulator or another connected Flutter device when prompted.

## Validate

```powershell
flutter analyze
flutter test
flutter build apk --debug
```

Generated build outputs, local SDK paths, IDE metadata, and caches are intentionally excluded from version control.
