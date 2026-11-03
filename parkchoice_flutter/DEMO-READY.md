# Android demo preparation - 3 November 2026

Use the root `parkchoice_flutter/`, `backend/` and `ml/` folders. The older Flutter
copies under Lab 2 and Lab 3 are not the active application.

For a teammate's backup laptop, follow [BACKUP-LAPTOP.md](BACKUP-LAPTOP.md).

## What has been checked

- Compared 202 backend, model, pipeline and Flutter files with GitHub `main`
  at `4a18316`. Functional files match. The local Android build retains the
  successfully used Gradle 9.3.1 / AGP 9.1.0 / Kotlin 2.4.0 configuration;
  upstream changes to those three build-tool versions do not add app features.
  The database README also has the local 2 November refresh instructions.
- All 151 backend tests and 46 Flutter tests passed. Flutter analysis found no issues.
- The model service loaded `short-horizon-lgbm-20261007` and warmed its live HDB feed.
- Live searches for NTU, Jurong East MRT and City Hall MRT returned valid results.
- Real recommendations passed in Best overall, Cheaper and Closer modes using
  OneMap routes, database prices and the HDB model. At the check, J57 had a valid
  arrival forecast and a supported one-hour price of 120 cents. This is a dated
  check, not a promise of the same winner or availability during the demo.
- A short Novena-to-City-Hall trip returned the explicitly labelled current-reading
  fallback. Missing forecasts were not presented as predictions.

## Start on this laptop

From the repository root, with a USB debugging-authorized Android phone connected:

```powershell
.\scripts\start-android-demo.ps1
```

The script starts or reuses the model on port 8001 and API on port 8000, checks
live OneMap search, forwards device port 8000 to the laptop, installs the current
debug APK and opens the app. With no phone it starts/checks services and asks you
to connect one. Rerun after reconnecting the cable. With multiple devices:

```powershell
.\scripts\start-android-demo.ps1 -DeviceId YOUR_PHONE_SERIAL
```

Find the serial using Android SDK `adb devices -l`. A device marked `unauthorized`
must be unlocked and its USB debugging prompt accepted. A charging-only cable
will not work. The phone needs internet for map tiles and external navigation;
the laptop needs internet for OneMap, the database and live model history. Keep
the laptop awake and the USB cable connected. No `.env` goes into the APK.

This laptop already has a usable Python environment under
`lab3/data-pipeline/.venv/`; the script prefers `backend/.venv/` if available.
Services started by the script log privately under `backend/data/demo-runtime/`.

## APK to use

Use `build/app/outputs/flutter-apk/app-debug.apk` in this folder, built from the
current source with `PARKING_API_URL=http://127.0.0.1:8000`. The fresh demo build
uses Android version code **20261103**, version name **1.0.0**, and supports
ARM 32-bit, ARM64 and x86-64. Its source/package fingerprint is recorded alongside
the APK as `demo-build.json` after the build completes.

Do not install the older 26 October APK from `lab4/submission/` for this demo.

Rebuild from this folder if source changes:

```powershell
flutter build apk --debug --no-pub --target-platform android-arm,android-arm64,android-x64 --build-number=20261103 --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

## Operator sign-in

The operator username and password hash were configured privately on 3 November.
The backend was restarted; configuration validation and rejection of an invalid
login passed, and live driver search still worked. Successful sign-in with the
chosen password remains a user/device check; the password was not requested or
printed during verification. Driver search works without operator sign-in.

To change the credentials privately on the laptop:

```powershell
python backend/configure_operator.py
```

This prompts for a username and a masked password, writes only the password hash
to the ignored backend `.env`, and preserves other configuration. Restart the
backend after changing operator credentials, then test sign-in yourself. The
Admin panel's sample reports/overrides remain prototype UI, not live operational
monitoring or persisted changes to the source feeds.

## Final checks on the actual phone

These remain pending until the demo phone is connected. Emulator success does
not replace physical-device acceptance.

1. Confirm the installed version code is `20261103`, and the app opens anonymous Search.
2. Manually search and select NTU as the origin and Jurong East MRT as destination.
   Set 60 minutes and Find carparks. Explain actual live results, including exclusions.
3. Try Cheaper and Closer. Eligibility stays the same; a different winner is not guaranteed.
4. Open View map, confirm tiles/markers, then open external navigation and return.
5. Test Use current location, including permission handling. Switch on phone location;
   fall back to manual origin if GPS cannot obtain a fix in the demo venue.
6. Disconnect USB, reconnect, rerun the startup script with `-SkipInstall`, and retry search.
7. If showing Admin, test your configured operator sign-in. Tracker and some saved-data
   flows remain prototype scope; rehearse them before presenting any persistence claim.

If recommendations are empty, inspect the displayed reason. Do not weaken price,
freshness or probability guards just to force a result. Rehearse again shortly
before presenting because live data changes. The existing video/demo plan is in
`../lab4/DEMO-SCRIPT.md`; the actual backup video must be recorded by the team.
