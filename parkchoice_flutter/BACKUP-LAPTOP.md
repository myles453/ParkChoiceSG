# Run the Android demo from a backup Windows laptop

The phone calls the laptop backend through USB. Plugging the phone into a second
laptop works only after that laptop is configured and its services are running.
Prepare and rehearse this before the presentation.

## 1. Get the current code and tools

Use the latest `main` from this repository. If your checkout has local changes,
use a separate clone rather than overwriting them.

Install Python 3.12 and Android SDK Platform-Tools (ADB). Android Studio normally
installs the SDK under `%LOCALAPPDATA%\Android\Sdk`; the startup script also checks
`ANDROID_HOME` and `ANDROID_SDK_ROOT` for custom SDK locations.

If the demo phone already has the fresh APK, **Flutter, Gradle and Android build
tools are not needed on the backup laptop**. The backend and model still are.
The checked demo APK is version `1.0.0`, Android version code `20261103`.

## 2. Create the Python environment

In PowerShell, from the repository root:

```powershell
py -3.12 -m venv backend/.venv
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\backend\.venv\Scripts\python.exe -m pip install -r ml/requirements-inference.txt
```

The model artifacts are already under `ml/models/`. No model training or new
database is required. The existing team's database must remain reachable.

## 3. Configure the backup laptop privately

Create `backend/.env` from `backend/.env.example` if it does not already exist:

```powershell
if (-not (Test-Path backend/.env)) {
    Copy-Item backend/.env.example backend/.env
}
```

Fill it privately. It needs:

| Field | Purpose |
| --- | --- |
| `DATABASE_URL` | Access the existing team database's `parking_data` schema. Read-only access is sufficient for recommendations. |
| `ONEMAP_EMAIL` and `ONEMAP_PASSWORD` | Obtain and renew OneMap tokens automatically. A manual token alone expires. |
| `PARKCHOICE_MODEL_URL` | Set to `http://127.0.0.1:8001`, pointing to the model running on this backup laptop. |
| `OPERATOR_USERNAME` and `OPERATOR_PASSWORD_HASH` | Needed if demonstrating Admin sign-in. The hash, not a plain password, belongs in this file. |

Arrange access to these credentials privately with the team; they are not in
GitHub or the APK. An authorized private copy of the existing **backend** `.env`
can retain the same demo operator login. Protect it as a secret. To choose a
different operator login instead, run before starting the services:

```powershell
.\backend\.venv\Scripts\python.exe backend/configure_operator.py
```

The backup laptop does not need LTA/URA collection keys just to run the demo.
Do not start a second periodic training collector; collection is a separate team task.

## 4. Connect the same demo phone

Connect a USB data cable, unlock the phone, enable USB debugging and accept the
new laptop's debugging prompt. Authorization is separate for each laptop.

If the phone already has the current demo app installed:

```powershell
.\scripts\start-android-demo.ps1 -SkipInstall
```

This starts the model and backend, checks live destination search, sets up
`adb reverse tcp:8000 tcp:8000`, and opens the installed app. Keep the laptop
awake and the cable connected. The phone needs internet for map tiles/navigation;
the laptop needs internet for OneMap, the database and the live HDB model feed.

If using a different phone, obtain the fresh APK file from the team and install it:

```powershell
.\scripts\start-android-demo.ps1 -ApkPath 'C:\path\to\ParkChoiceSG-demo.apk'
```

The APK is a generated local artifact, not part of this Git push. The verified
3 November universal APK SHA-256 is:

```text
c8deed2ba449361da272b8b13aa61119092d13c578b36efbaa157702672b6400
```

Check a supplied file with `Get-FileHash -Algorithm SHA256 'C:\path\to\ParkChoiceSG-demo.apk'`.
Do not use the older 26 October APK in `lab4/submission/` for this demo.

If multiple Android devices are connected, add `-DeviceId YOUR_PHONE_SERIAL`.
List devices with the SDK's `platform-tools/adb.exe devices -l`. If PowerShell
blocks the script under its execution policy, run this one process without
changing the machine-wide policy:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\start-android-demo.ps1 -SkipInstall
```

## 5. Rehearse the actual failover

1. Search for and select NTU and Jurong East MRT, choose a 60-minute stay, then
   Find carparks. A passing `/health` response alone does not prove recommendations work.
2. Check the displayed price, route and forecast/current-reading label. Live
   winners change; do not force a result by bypassing eligibility guards.
3. Open the map, open navigation, return, and test operator sign-in if presenting it.
4. Disconnect the phone from the primary laptop, connect it to the backup laptop,
   rerun the startup script with `-SkipInstall`, and repeat the search.

The database and external providers are shared dependencies, so a second laptop
does not cover an internet/provider outage. Keep the team's reviewed backup video
available too. The model may need time to warm its recent HDB history after startup.
See [DEMO-READY.md](DEMO-READY.md) for tested scope and phone checks.
