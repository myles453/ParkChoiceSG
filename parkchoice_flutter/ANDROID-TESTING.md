# Test on an Android phone over USB

Use this folder, `parkchoice_flutter/`, rather than the older Flutter copies.

## Connect and run

1. Enable Developer options and USB debugging on the phone. Connect a USB data
   cable, unlock the phone and accept the computer's debugging prompt.
2. Start the model and recommendation API using
   [the backend setup](../backend/README.md). Keep both terminals running.
   `/health` on ports 8000 and 8001 should respond; model health should report
   `artifacts_loaded: true`.
3. From this folder, run the following in PowerShell. If there is more than one
   Android device, add `-s DEVICE_ID` after `adb.exe` and replace `DEVICE_ID` below.

```powershell
$adbPath = "$env:LOCALAPPDATA/Android/Sdk/platform-tools/adb.exe"
& $adbPath devices -l
& $adbPath reverse tcp:8000 tcp:8000
flutter run -d DEVICE_ID --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

USB forwarding makes the phone's port 8000 reach the computer's backend. The
backend can stay bound to `127.0.0.1`; no firewall change is needed. Keep the cable
connected and rerun the reverse command after reconnecting. The phone still needs
internet access for map tiles and external navigation. The computer needs internet
for OneMap, the database and the HDB model feed. No provider or database secrets
belong on the phone.

To install an already built debug APK instead of attaching Flutter:

```powershell
& $adbPath install -r build/app/outputs/flutter-apk/app-debug.apk
& $adbPath shell am start -n com.example.parkchoicesg_2/.MainActivity
```

The APK must have been built with the same `PARKING_API_URL` above. These instructions
use the debug build, which permits local HTTP. Release deployment needs HTTPS.

## End-to-end checks

| Check | Expected behaviour |
|---|---|
| Launch | Opens parking search without login or registration. |
| Use current location | Android asks for foreground location permission; after allowing it, the starting point reads Current location and shows accuracy. Turn on device location first. |
| Deny permission | Shows an explanation and allows a manually selected starting place. |
| Search destination | Enter a Singapore place/postal code, tap its search icon and select a returned place. |
| Find carparks | Uses the selected origin/destination and duration; shows supported prices, route information and availability evidence. |
| Ranking modes | Best overall, Prioritise cheaper and Prioritise closer are accepted. Changing mode clears the previous results; search again to apply it. |
| View map | OneMap tiles appear with start, destination and carpark markers. |
| Navigate | Opens external directions for the selected carpark. |
| Old device fix | After two minutes, refresh current location before searching again. |
| Provider does not return a fix | Android tries its native provider after the first attempt times out. Within 30 seconds the form either has a location or shows a retry/manual-input message; it must not remain locked. |

The model ranks supported HDB forecasts for arrival horizons of 15-90 minutes.
A short trip can legitimately show a labelled current-reading fallback instead.
The model loads artifacts at startup but also needs recent source history; artifact
health alone does not establish that an eligible forecast exists. No eligible
carparks is a possible result, not a reason to display fabricated recommendations.

Tracker, admin actions and some saved-preference flows remain prototypes. This
checklist covers the connected search, comparison, map and navigation workflow.
