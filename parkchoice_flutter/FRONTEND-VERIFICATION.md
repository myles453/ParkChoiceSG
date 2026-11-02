# Frontend crash review — 26 October 2026

Scope: the active `parkchoice_flutter/` app. Historical Flutter copies, backend
behaviour, database schema, pricing and ranking formulas were not changed.

## Reproduced defects and fixes

| Trigger | Failure before the fix | Result after the fix |
|---|---|---|
| Open a result map while an input edit clears the destination, before the new route builds | Null-check exception: the map builder read the search screen's mutable destination | The map uses the origin and destination captured with its results. |
| Select a place result twice before its sheet finishes closing | Both taps popped a route, closing the search page as well | Closing is accepted once and only from the active selection sheet. |
| Submit the same place search twice before the next frame | Two requests and potentially competing selection sheets | One place-selection operation is allowed at a time. |
| Confirm erase-data or end-session twice | The second confirmation could pop the underlying screen | Dialog callbacks check closing state and current route. Other sheet entry/close actions use the same route checks. |
| Rapidly switch away from Search | Multiple replacement actions could start from the old page | Navigation is guarded and keyboard focus is released before replacement. Late responses are ignored after navigation/disposal. |
| Receive incomplete comparison data with HTTP 200 | Invalid nested values could pass the request handler and fail later during widget rendering | Required lists/maps and rendered numeric values are checked before screen state is updated. Existing request-error messages handle invalid responses. Unknown prices are not converted to zero. |
| Open a map with missing or invalid coordinates | Cast/range errors in map construction | Missing start/destination coordinates show a recoverable message; invalid carpark markers are skipped. |
| Map tiles fail, or an attribution link cannot open | Error callbacks or failed launches could update an unsafe widget state or leave failure unreported | Tile-error updates wait until after the frame and check mounting; failed website launches show an error. |
| Use a narrow screen, or open the saved-place keyboard with larger text | Preferences and session confirmation layouts overflowed | Labels wrap, the saved-place sheet scrolls, and confirmation values fit the available width. |

## Automated verification

The full Flutter suite passed **40 tests**, including all 15 existing tests.
`flutter analyze` is clean and the Android arm64 debug APK built successfully.
The new checks include:

- 120 reproducible tab transitions across Search, Tracker, Preferences and Admin,
  at widths 320 and 430, with typing, appearance changes and saved-place dialogs.
- Eight admin override create/change/apply/withdraw cycles against prototype state.
- Sixteen session-extension and sixteen end-session/cancel cycles across two widths.
- Duplicate taps/submits, late successful and failed lookups after navigation,
  late comparison responses, and map navigation during input invalidation.
- Expired GPS input followed by refresh, retaining the selected destination.
- Invalid/empty service responses, bad map points, unavailable tiles, reopening
  maps and failed website launches.
- A small-screen saved-place sheet with a keyboard and 150% text scaling.

Tests fail on missed stress-test taps; off-screen controls are scrolled into view.
The request and map tests use controlled fixtures and do not contact providers,
modify the database or change real operator data. Intentional tile failures in
the map test print image-error diagnostics; these are expected test inputs.

Reproduce from this folder:

```powershell
flutter analyze
flutter test --timeout 120s
flutter build apk --debug --target-platform android-arm64 --dart-define=PARKING_API_URL=http://127.0.0.1:8000
```

## Limits and phone verification

These checks verify Flutter interactions and request handling; they are not proof
that every Android OS or device-specific failure is eliminated. No Android phone
was connected during this review. The generated APK still needs an on-phone pass
using [ANDROID-TESTING.md](ANDROID-TESTING.md), including repeated tab changes,
background/foreground transitions, keyboard use, GPS permission and external
navigation. If a native process crash remains, capture its Android logcat output.

The two-minute GPS freshness rule remains intentional. Tabs still replace their
pages, so transient form entries can reset when leaving a tab. Durable preferences,
session reminders and operator actions retain their existing prototype scope;
this review does not implement those unfinished features.
