import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:parkchoicesg_2/models/ranking_mode.dart';
import 'package:parkchoicesg_2/screens/carpark_map_screen.dart';
import 'package:parkchoicesg_2/screens/carpark_search_screen.dart';
import 'package:parkchoicesg_2/services/parking_api.dart';
import 'package:parkchoicesg_2/widgets/bottom_nav_bar.dart';

Map<String, dynamic> place(String name) => {
  'name': name,
  'address': 'Public test place',
  'coordinate': {'latitude': 1.3, 'longitude': 103.8},
};

class LifecycleApi extends ParkingApi {
  Completer<List<Map<String, dynamic>>>? pendingSearch;
  Completer<Map<String, dynamic>>? pendingComparison;
  int searches = 0;

  @override
  Future<List<Map<String, dynamic>>> destinations(String query) async {
    searches++;
    return pendingSearch == null
        ? [place('Selected $query')]
        : pendingSearch!.future;
  }

  @override
  Future<Map<String, dynamic>> recommend({
    required Map<String, dynamic> origin,
    required Map<String, dynamic> destination,
    required int durationMinutes,
    RankingMode rankingMode = RankingMode.bestOverall,
  }) async =>
      pendingComparison?.future ??
      {
        'ranked': [],
        'candidates': [
          {
            'agency': 'HDB',
            'carpark_id': 'A',
            'display_name': 'Test carpark',
            'latitude': 1.301,
            'longitude': 103.801,
            'price': {'amount_cents': 120},
            'driving': {'duration_seconds': 1200},
            'walking': {'distance_meters': 200},
            'prediction': {'status': 'prediction_pending'},
            'ranking_exclusions': [],
          },
        ],
      };
}

Future<void> selectPlace(WidgetTester tester, int index, String query) async {
  await tester.enterText(find.byType(TextField).at(index), query);
  await tester.tap(
    find.byTooltip(
      index == 0 ? 'Search starting location' : 'Search destination',
    ),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.text('Selected $query'));
  await tester.pumpAndSettle();
}

void main() {
  late LifecycleApi api;
  setUp(() => api = LifecycleApi());
  tearDown(() => api.close());

  for (final fails in [false, true]) {
    testWidgets(
      'leaving search while a lookup is pending, late failure=$fails',
      (tester) async {
        api.pendingSearch = Completer();
        await tester.pumpWidget(
          MaterialApp(home: CarparkSearchScreen(api: api)),
        );
        await tester.enterText(find.byType(TextField).last, 'City Hall');
        await tester.tap(find.byTooltip('Search destination'));
        await tester.pump();
        await tester.tap(find.text('Preferences'));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));
        if (fails) {
          api.pendingSearch!.completeError(
            Exception('Test connection failure'),
          );
        } else {
          api.pendingSearch!.complete([place('Late result')]);
        }
        await tester.pump();
        expect(find.text('Late result'), findsNothing);
        expect(find.byType(CarparkSearchScreen), findsNothing);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets(
    'late comparison after switching tabs does not use disposed inputs',
    (tester) async {
      api.pendingComparison = Completer();
      tester.view.physicalSize = const Size(430, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(MaterialApp(home: CarparkSearchScreen(api: api)));
      await selectPlace(tester, 0, 'Start');
      await selectPlace(tester, 1, 'End');
      await tester.ensureVisible(find.text('Find carparks'));
      await tester.tap(find.text('Find carparks'));
      await tester.pump();
      await tester.tap(find.text('Preferences'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 400));
      api.pendingComparison!.complete({'ranked': [], 'candidates': []});
      await tester.pump();
      expect(find.byType(CarparkSearchScreen), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('rapid tab taps replace the search route only once', (
    tester,
  ) async {
    final observer = ReplacementObserver();
    await tester.pumpWidget(
      MaterialApp(
        navigatorObservers: [observer],
        home: CarparkSearchScreen(api: api),
      ),
    );
    final nav = tester.widget<ParkChoiceBottomNav>(
      find.byType(ParkChoiceBottomNav),
    );
    nav.onDestinationSelected(2);
    nav.onDestinationSelected(1);
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(observer.replacements, 1);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'an expired GPS fix can be refreshed without losing the destination',
    (tester) async {
      tester.view.physicalSize = const Size(430, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var fixes = 0;
      await tester.pumpWidget(
        MaterialApp(
          home: CarparkSearchScreen(
            api: api,
            locate:
                () async => {
                  ...place('Current location'),
                  'accuracy_meters': 15,
                  'located_at':
                      DateTime.now()
                          .subtract(Duration(minutes: fixes++ == 0 ? 3 : 0))
                          .toUtc()
                          .toIso8601String(),
                },
          ),
        ),
      );
      await tester.tap(find.text('Use current location'));
      await tester.pumpAndSettle();
      await selectPlace(tester, 1, 'End');
      await tester.ensureVisible(find.text('Find carparks'));
      await tester.tap(find.text('Find carparks'));
      await tester.pumpAndSettle();
      expect(
        find.textContaining('Refresh your current location'),
        findsOneWidget,
      );
      await tester.ensureVisible(find.text('Use current location'));
      await tester.tap(find.text('Use current location'));
      await tester.pumpAndSettle();
      expect(find.text('Selected End'), findsOneWidget);
      await tester.ensureVisible(find.text('Find carparks'));
      await tester.tap(find.text('Find carparks'));
      await tester.pumpAndSettle();
      expect(find.text('Test carpark'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'double tapping a destination result never pops the search screen',
    (tester) async {
      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder:
                (context) => Scaffold(
                  body: TextButton(
                    onPressed:
                        () => Navigator.push(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) => CarparkSearchScreen(api: api),
                          ),
                        ),
                    child: const Text('Open search'),
                  ),
                ),
          ),
        ),
      );
      await tester.tap(find.text('Open search'));
      await tester.pumpAndSettle();
      await tester.enterText(find.byType(TextField).last, 'City Hall');
      await tester.tap(find.byTooltip('Search destination'));
      await tester.pumpAndSettle();
      final row = tester.widget<ListTile>(
        find.widgetWithText(ListTile, 'Selected City Hall'),
      );
      row.onTap!();
      row.onTap!();
      await tester.pumpAndSettle();
      expect(find.byType(CarparkSearchScreen), findsOneWidget);
      expect(find.text('Selected City Hall'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('overlapping submit events start only one location search', (
    tester,
  ) async {
    api.pendingSearch = Completer();
    await tester.pumpWidget(MaterialApp(home: CarparkSearchScreen(api: api)));
    await tester.enterText(find.byType(TextField).last, 'City Hall');
    final submit =
        tester.widget<TextField>(find.byType(TextField).last).onSubmitted!;
    submit('City Hall');
    submit('City Hall');
    expect(api.searches, 1);
    api.pendingSearch!.complete([place('Selected City Hall')]);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Selected City Hall'));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('map navigation keeps the selections that produced its results', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(430, 1000);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    await tester.pumpWidget(MaterialApp(home: CarparkSearchScreen(api: api)));
    await selectPlace(tester, 0, 'Start');
    await selectPlace(tester, 1, 'End');
    await tester.ensureVisible(find.text('Find carparks'));
    await tester.tap(find.text('Find carparks'));
    await tester.pumpAndSettle();
    final edit =
        tester.widget<TextField>(find.byType(TextField).last).onChanged!;
    await tester.ensureVisible(find.text('View map'));
    await tester.tap(find.text('View map'));
    // An input event can arrive before the pushed route builds its contents.
    edit('Another destination');
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 350));
    expect(tester.takeException(), isNull);
    expect(find.byType(CarparkMapScreen), findsOneWidget);
    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpAndSettle();
  });
}

class ReplacementObserver extends NavigatorObserver {
  int replacements = 0;
  @override
  void didReplace({Route<dynamic>? newRoute, Route<dynamic>? oldRoute}) {
    replacements++;
  }
}
