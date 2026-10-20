import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parkchoicesg_2/screens/carpark_search_screen.dart';
import 'package:parkchoicesg_2/services/parking_api.dart';

void main() {
  for (final mode in ['pending', 'probability', 'fallback']) {
    final usePrediction = mode == 'probability';
    final useFallback = mode == 'fallback';
    testWidgets('selected locations show real cost and $mode', (tester) async {
      tester.view.physicalSize = const Size(430, 932);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var recommendationCalls = 0;
      Uri? openedNavigation;
      final api = ParkingApi(
        client: MockClient((request) async {
          expect(request.headers['Authorization'], isNull);
          final body = jsonDecode(request.body) as Map<String, dynamic>;
          if (request.url.path == '/destinations') {
            return http.Response(
              jsonEncode({
                'matches': [
                  {
                    'name': 'Selected ${body['query']}',
                    'address': 'Public test location',
                    'coordinate': {'latitude': 1.3, 'longitude': 103.8},
                  },
                ],
              }),
              200,
            );
          }
          recommendationCalls++;
          expect(body['origin'], {'latitude': 1.3, 'longitude': 103.8});
          expect(body['duration_minutes'], 60);
          return http.Response(
            jsonEncode({
              'ranking_basis':
                  usePrediction
                      ? 'arrival_free_probability'
                      : 'current_availability_baseline',
              'ranked':
                  useFallback
                      ? []
                      : [
                        {'agency': 'HDB', 'carpark_id': 'BBB', 'rank': 1},
                      ],
              'fallback_ranked':
                  useFallback
                      ? [
                        {'agency': 'HDB', 'carpark_id': 'BBB', 'rank': 1},
                      ]
                      : [],
              'fallback_notice':
                  'Current readings only; availability may change before arrival.',
              'candidates': [
                {
                  'agency': 'HDB',
                  'carpark_id': 'BBB',
                  'latitude': 1.3,
                  'longitude': 103.8,
                  'display_name': 'Bras Basah',
                  'address': 'Test address',
                  'price': {'amount_cents': 240},
                  'driving': {'duration_seconds': 484},
                  'walking': {'distance_meters': 556},
                  'current_availability': {
                    'available_lots': 111,
                    'status': 'fresh_source_update',
                    'timestamp': '2026-10-15T03:00:00Z',
                    'timestamp_kind': 'source_update',
                  },
                  'prediction':
                      usePrediction
                          ? {
                            'status': 'ok',
                            'p_free': 0.96,
                            'available_lots': null,
                            'confidence': 'medium',
                          }
                          : {
                            'status':
                                useFallback
                                    ? 'unsupported_horizon_15_to_90_minutes'
                                    : 'prediction_pending',
                          },
                  'ranking_exclusions': [],
                },
              ],
            }),
            200,
          );
        }),
      );
      addTearDown(api.close);
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkSearchScreen(
            api: api,
            launchNavigation: (uri) async {
              openedNavigation = uri;
              return true;
            },
          ),
        ),
      );
      expect(find.textContaining('Bras Basah'), findsNothing);

      await tester.enterText(find.byType(TextField).at(0), 'Novena');
      await tester.tap(find.byTooltip('Search starting location'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Selected Novena'));
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextField).at(1), 'City Hall');
      await tester.tap(find.byTooltip('Search destination'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Selected City Hall'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Find carparks'));
      await tester.pumpAndSettle();

      expect(recommendationCalls, 1);
      expect(find.text(r'$2.40 for 60 min'), findsOneWidget);
      expect(find.text('Current reported availability: 111'), findsOneWidget);
      expect(find.textContaining('High confidence'), findsNothing);
      expect(
        find.text(
          usePrediction
              ? '96.0% chance of at least one free lot at arrival (medium band)'
              : useFallback
              ? 'Arrival predictions are supported for trips of 15–90 minutes.'
              : 'Arrival prediction pending or unavailable',
        ),
        findsOneWidget,
      );
      expect(find.textContaining('null lots'), findsNothing);
      if (useFallback) {
        expect(find.text('Current-reading options'), findsOneWidget);
        expect(find.textContaining('availability may change'), findsOneWidget);
      }
      await tester.ensureVisible(find.text('Navigate to carpark'));
      await tester.tap(find.text('Navigate to carpark'));
      await tester.pumpAndSettle();
      expect(openedNavigation?.queryParameters['destination'], '1.3,103.8');
      expect(openedNavigation?.queryParameters['api'], '1');
      expect(openedNavigation?.queryParameters.containsKey('key'), isFalse);

      // Editing a selected destination must discard its old coordinates.
      await tester.enterText(
        find.byType(TextField).at(1),
        'Changed destination',
      );
      await tester.ensureVisible(find.text('Find carparks'));
      await tester.tap(find.text('Find carparks'));
      await tester.pumpAndSettle();
      expect(recommendationCalls, 1);
      expect(
        find.text(
          'Search and select both your starting location and destination.',
        ),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    });
  }
}
