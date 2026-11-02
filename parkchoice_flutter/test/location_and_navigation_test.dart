import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:parkchoicesg_2/screens/carpark_search_screen.dart';
import 'package:parkchoicesg_2/services/navigation_handoff.dart';

void main() {
  testWidgets(
    'a stalled location request unlocks the form and ignores a late fix',
    (tester) async {
      final pending = Completer<Map<String, dynamic>>();
      await tester.pumpWidget(
        MaterialApp(home: CarparkSearchScreen(locate: () => pending.future)),
      );
      await tester.tap(find.text('Use current location'));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      await tester.pump(const Duration(seconds: 31));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(
        find.textContaining('could not get a location fix'),
        findsOneWidget,
      );
      expect(
        tester.widget<TextField>(find.byType(TextField).first).enabled,
        isTrue,
      );

      // A platform callback arriving after the deadline must not change the form.
      pending.complete({
        'coordinate': {'latitude': 1.3, 'longitude': 103.8},
      });
      await tester.pump();
      expect(find.text('Current location'), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'device location is requested only on tap and permission failure keeps manual input',
    (tester) async {
      var requests = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkSearchScreen(
            locate: () async {
              requests++;
              throw StateError(
                'Location permission was not granted. Choose a starting place instead.',
              );
            },
          ),
        ),
      );
      expect(requests, 0);
      await tester.tap(find.text('Use current location'));
      await tester.pumpAndSettle();
      expect(requests, 1);
      expect(
        find.textContaining('Location permission was not granted'),
        findsOneWidget,
      );
      expect(find.byType(TextField), findsNWidgets(2));
    },
  );

  testWidgets(
    'device location keeps coordinates and marks accuracy without automatic searches',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkSearchScreen(
            locate:
                () async => {
                  'name': 'Current location',
                  'coordinate': {'latitude': 1.3, 'longitude': 103.8},
                  'located_at': DateTime.now().toUtc().toIso8601String(),
                  'accuracy_meters': 12.0,
                },
          ),
        ),
      );
      await tester.tap(find.text('Use current location'));
      await tester.pumpAndSettle();
      expect(find.text('Current location'), findsOneWidget);
      expect(find.text('Location accuracy: about 12 m'), findsOneWidget);
      await tester.ensureVisible(find.text('Find carparks'));
      await tester.tap(find.text('Find carparks'));
      await tester.pumpAndSettle();
      expect(
        find.text(
          'Search and select both your starting location and destination.',
        ),
        findsOneWidget,
      );
    },
  );

  test(
    'navigation validates coordinates and uses a destination-only key-free URL',
    () {
      final url = carparkNavigationUrl(1.3, 103.8);
      expect(url.host, 'www.google.com');
      expect(url.queryParameters['destination'], '1.3,103.8');
      expect(url.queryParameters.containsKey('origin'), isFalse);
      expect(url.queryParameters.containsKey('key'), isFalse);
      expect(
        () => carparkNavigationUrl(double.nan, 103.8),
        throwsArgumentError,
      );
    },
  );
}
