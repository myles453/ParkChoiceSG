import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parkchoicesg_2/models/ranking_mode.dart';
import 'package:parkchoicesg_2/screens/carpark_search_screen.dart';
import 'package:parkchoicesg_2/services/parking_api.dart';

void main() {
  for (final selected in RankingMode.values) {
    testWidgets(
      '${selected.label} is sent to the backend and clears old results',
      (tester) async {
        tester.view.physicalSize = const Size(430, 1000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        final requests = <String>[];
        final api = ParkingApi(
          client: MockClient((request) async {
            final body = jsonDecode(request.body) as Map<String, dynamic>;
            if (request.url.path == '/destinations') {
              return http.Response(
                jsonEncode({
                  'matches': [
                    {
                      'name': 'Selected ${body['query']}',
                      'address': 'Public fixture',
                      'coordinate': {'latitude': 1.3, 'longitude': 103.8},
                    },
                  ],
                }),
                200,
              );
            }
            requests.add(body['ranking_mode'] as String);
            return http.Response(
              jsonEncode({
                'ranking_mode': body['ranking_mode'],
                'ranking_basis': 'arrival_free_probability',
                'ranked': [
                  {'agency': 'HDB', 'carpark_id': 'A', 'rank': 1},
                ],
                'fallback_ranked': [],
                'candidates': [
                  {
                    'agency': 'HDB',
                    'carpark_id': 'A',
                    'display_name': 'Policy result',
                    'price': {'amount_cents': 240},
                    'driving': {'duration_seconds': 1200},
                    'walking': {'distance_meters': 250},
                    'current_availability': {'available_lots': 20},
                    'prediction': {
                      'status': 'ok',
                      'p_free': .96,
                      'confidence': 'medium',
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
          MaterialApp(home: CarparkSearchScreen(api: api)),
        );
        expect(find.text(RankingMode.bestOverall.description), findsOneWidget);

        for (var i = 0; i < 2; i++) {
          await tester.enterText(
            find.byType(TextField).at(i),
            i == 0 ? 'Origin' : 'Destination',
          );
          await tester.tap(
            find.byTooltip(
              i == 0 ? 'Search starting location' : 'Search destination',
            ),
          );
          await tester.pumpAndSettle();
          await tester.tap(
            find.text(i == 0 ? 'Selected Origin' : 'Selected Destination'),
          );
          await tester.pumpAndSettle();
        }
        final selector = find.byKey(const Key('ranking-mode-selector'));
        if (selected != RankingMode.bestOverall) {
          await tester.ensureVisible(selector);
          await tester.tap(selector);
          await tester.pumpAndSettle();
          await tester.tap(find.text(selected.label).last);
          await tester.pumpAndSettle();
        }
        expect(find.text(selected.description), findsOneWidget);
        await tester.ensureVisible(find.text('Find carparks'));
        await tester.tap(find.text('Find carparks'));
        await tester.pumpAndSettle();
        expect(requests, [selected.apiValue]);
        expect(find.text('Ranking mode: ${selected.label}'), findsOneWidget);
        expect(find.text('#1  Policy result'), findsOneWidget);

        final other =
            selected == RankingMode.closer
                ? RankingMode.bestOverall
                : RankingMode.closer;
        await tester.ensureVisible(selector);
        await tester.tap(selector);
        await tester.pumpAndSettle();
        await tester.tap(find.text(other.label).last);
        await tester.pumpAndSettle();
        expect(find.text('#1  Policy result'), findsNothing);
        expect(find.text('Ranking mode: ${selected.label}'), findsNothing);
        expect(requests.length, 1);
        expect(tester.takeException(), isNull);
      },
    );
  }
}
