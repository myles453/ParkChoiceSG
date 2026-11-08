# ParkChoiceSG Flutter application

The active client opens anonymous driver search. Selected origin, destination,
stay duration and ranking mode are submitted to the FastAPI backend. Results
display supported stay prices, routed travel/walking measurements, source times
and arrival probability or a separately labelled current-reading fallback.

## Connected features

- Manual place selection and foreground device location.
- Best overall, Prioritise cheaper and Prioritise closer.
- Result cards, attributed OneMap marker maps and external navigation.
- Persisted Light/Dark/System appearance.
- Separate operator credential check and process-local console entry gate.

Tracker, saved labels, vehicle/walking controls and console actions retain their
partial/sample behavior. Durable history/favourites, scheduled reminders, complete
erasure and server-side administrative writes are not implemented. The final
use-case statuses are in [the models PDF](../lab5/output/pdf/ParkChoiceSG-Final-SRS-Models.pdf).

## Run and test

Start the model on port 8001 and backend on port 8000 using
[backend setup](../backend/README.md). From this directory:

```powershell
flutter pub get
flutter run --dart-define=PARKING_API_URL=http://127.0.0.1:8000
flutter analyze --no-pub
flutter test --no-pub --timeout 120s
flutter build apk --debug --target-platform android-arm64 --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

For an Android phone using that loopback URL, forward port 8000 with USB debugging
as described in [ANDROID-TESTING.md](ANDROID-TESTING.md). A network deployment
requires its reachable API URL. Only `PARKING_API_URL` is client configuration;
provider/database credentials stay server-side.

The app uses bundled Public Sans fonts, shared themes in `lib/constants.dart`
and `lib/main.dart`, and reusable components in `lib/widgets/app_ui.dart`.
Font licences are retained under `assets/fonts/public_sans/`. Generated builds,
local SDK paths and IDE/cache files are excluded from version control.
