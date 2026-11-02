import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parkchoicesg_2/services/parking_api.dart';

void main() {
  for (final malformed in [
    {
      'ranked': [],
      'candidates': [
        {'price': null},
      ],
    },
    {
      'ranked': [
        {'rank': 'first'},
      ],
      'candidates': [],
    },
    {'ranked': [], 'candidates': null},
  ]) {
    test(
      'malformed comparison is rejected before a widget can render it: $malformed',
      () async {
        final api = ParkingApi(
          client: MockClient(
            (_) async => http.Response(jsonEncode(malformed), 200),
          ),
        );
        addTearDown(api.close);
        await expectLater(
          api.recommend(
            origin: {'latitude': 1.3, 'longitude': 103.8},
            destination: {'latitude': 1.31, 'longitude': 103.81},
            durationMinutes: 60,
          ),
          throwsFormatException,
        );
      },
    );
  }
  test(
    'invalid place coordinates are rejected before showing a selection sheet',
    () async {
      final api = ParkingApi(
        client: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'matches': [
                {
                  'name': 'A',
                  'address': 'Public fixture',
                  'coordinate': {'latitude': null, 'longitude': 103.8},
                },
              ],
            }),
            200,
          ),
        ),
      );
      addTearDown(api.close);
      await expectLater(api.destinations('A'), throwsFormatException);
    },
  );
  test('an empty but valid comparison remains a normal response', () async {
    final api = ParkingApi(
      client: MockClient(
        (_) async =>
            http.Response(jsonEncode({'ranked': [], 'candidates': []}), 200),
      ),
    );
    addTearDown(api.close);
    expect(
      (await api.recommend(
        origin: {'latitude': 1.3, 'longitude': 103.8},
        destination: {'latitude': 1.31, 'longitude': 103.81},
        durationMinutes: 60,
      ))['candidates'],
      isEmpty,
    );
  });
}
