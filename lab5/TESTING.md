# Submission verification - 8 November 2026

Checks were executed from the isolated `submission/lab5-final` checkout, based on
upstream `3d37040`, with the final source and documentation cleanup applied.

| Check | Result |
|---|---|
| Backend unittest discovery | 151 passed |
| Model dataset/training unit tests and inference service contract tests | 108 passed |
| Flutter widget/service/stress tests | 46 passed |
| Flutter static analysis | No issues found |
| Android arm64 debug build | Passed; version code 20261108; loopback API URL for documented USB forwarding |
| Python comment/docstring cleanup | AST comparison confirmed unchanged executable code in model_adapter.py, prediction.py and service/artifacts.py |
| Final models PDF | 42 pages, 19 use cases, 17 diagrams; searchable text/vector figures; rendered layout reviewed |

## Reproduce

Use Python 3.12 with `backend/requirements.txt`, `ml/requirements-inference.txt`
and the training/test dependencies in `ml/requirements.txt`. Install `pytest` for
the model suites. From the repository root:

```powershell
python -m unittest discover -s backend/validation -p 'test_*.py' -q
python -m pytest ml/tests ml/service/tests/test_service.py -q
cd parkchoice_flutter
flutter pub get
flutter analyze --no-pub
flutter test --no-pub --timeout 120s
flutter build apk --debug --no-pub --target-platform android-arm64 --build-number=20261108 --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

The selected model suites use controlled data/artifacts and do not require the
ignored raw archive. Separate parity suites require their documented datasets
and were not included in this submission run. No production credentials or live
provider calls are needed for these automated suites.

Map tile failure tests intentionally exercise invalid-image responses; image
decoder diagnostics in their output are expected fixture behavior. Framework
deprecation warnings do not change the successful test outcomes.

The Android source uses the previously verified Gradle 9.3.1 / Android Gradle
Plugin 9.1.0 / Kotlin 2.4.0 toolchain. Generated APKs, private configuration, local
SDK paths, datasets and caches are excluded from Git.

These checks establish the tested source/build behavior. They do not repeat a
physical-phone acceptance test, live prediction evaluation or production-provider
health check. Earlier live and model-evaluation evidence retains its original
date, cohort and method under backend validation and `ml/reports/`.
