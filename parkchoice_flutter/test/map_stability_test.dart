import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:parkchoicesg_2/screens/carpark_map_screen.dart';

class TestTiles extends TileProvider {
  final bool fail;
  TestTiles({this.fail = false});
  @override
  ImageProvider getImage(
    TileCoordinates coordinates,
    TileLayer options,
  ) => MemoryImage(
    fail
        ? Uint8List(0)
        : base64Decode(
          'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABpfZFQAAAAABJRU5ErkJggg==',
        ),
  );
}

void main() {
  const place = {
    'coordinate': {'latitude': 1.3, 'longitude': 103.8},
  };
  testWidgets(
    'missing required coordinates display a recoverable map message',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkMapScreen(
            origin: const {},
            destination: place,
            carparks: const [],
            tileProvider: TestTiles(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        find.textContaining('Map coordinates are unavailable'),
        findsOneWidget,
      );
    },
  );
  testWidgets(
    'coincident points and invalid carpark coordinates do not crash the map',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkMapScreen(
            origin: place,
            destination: place,
            carparks: const [
              {
                'latitude': 999,
                'longitude': 103.8,
                'display_name': 'Invalid point',
              },
            ],
            tileProvider: TestTiles(),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(
        tester.widget<MarkerLayer>(find.byType(MarkerLayer)).markers,
        hasLength(2),
      );
    },
  );
  testWidgets('failed tiles can be followed by leaving and reopening the map', (
    tester,
  ) async {
    for (var i = 0; i < 4; i++) {
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkMapScreen(
            key: ValueKey(i),
            origin: place,
            destination: place,
            carparks: const [],
            tileProvider: TestTiles(fail: true),
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Map tiles are unavailable'), findsOneWidget);
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pumpAndSettle();
    }
  });
  testWidgets(
    'a failed attribution link reports an error instead of an unhandled future',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkMapScreen(
            origin: place,
            destination: place,
            carparks: const [],
            tileProvider: TestTiles(),
            launchWebsite:
                (_) async => throw Exception('Test browser unavailable'),
          ),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('OneMap'));
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.textContaining('Could not open the website'), findsOneWidget);
    },
  );
}
