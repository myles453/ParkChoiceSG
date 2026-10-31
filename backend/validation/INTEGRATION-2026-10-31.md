# Integration verification — 31 October 2026

The working changes were reconciled on top of upstream main
`a19e9ccf9fae0170eb934013b505d39c41bfde71` (operator password configuration fix).
Upstream operator login, documentation and tests are preserved. Drivers remain
anonymous; the operator console remains a separately gated prototype.

## Reconciled changes

- Retain `OPERATOR_USERNAME` and `OPERATOR_PASSWORD_HASH` in the shared private
  environment loader. Its overlap with local code was formatting only. The
  backend regression verifies both fields load from a private configuration file.
- Keep the three ranking modes consistent between the Flutter request and backend
  request/controller/scoring code, including the labelled current-reading fallback.
- Preserve the frontend map/input snapshots, duplicate-action guards, response
  validation, GPS timeout handling and small-screen/dialog fixes.
- Extend the operator screen with the same request/navigation guard: rapid sign-in
  taps start one request, and success after leaving the screen does not establish
  a new operator session. Both new cases fail against the upstream screen and
  pass with the guard. Keyboard focus is released before replacing the screen.
- Preserve the upstream working-directory README, adding current frontend review,
  Lab 4 review and project-rationale entry points. Historical Lab 2/3 working
  drafts were not reintroduced over the published directory cleanup.
- Treat PDF, archive, image and model artifacts as binary files so Windows line
  conversion does not change their bytes.

## Checks on the combined tree

| Check | Result |
|---|---|
| Backend `unittest` discovery | 151 tests passed |
| Flutter suite | 46 tests passed |
| Flutter static analysis | No issues |
| Android arm64 debug APK | Built successfully |
| Publication scan | No private environment files or configured secret values in staged sources or ZIP contents |
| PDF/source-ZIP Git blobs | Staged bytes match the local artifacts |
| Main entry-point Markdown links | No missing local targets |

Reproduce from the repository root with the configured Python environment:

```powershell
python -m unittest discover -s backend/validation -p 'test_*.py' -q
cd parkchoice_flutter
flutter pub get
flutter analyze --no-pub
flutter test --no-pub --timeout 120s
flutter build apk --debug --no-pub --target-platform android-arm64 --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

The Lab 4 PDFs, evidence and source ZIP remain dated 26 October review snapshots.
The current source tree includes the later sign-in guards. APKs and build
directories are local artifacts and are not committed. This integration uses
offline fixtures; it does not establish current provider/feed health, model
accuracy or physical-device acceptance, and does not change the database.
