import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:parkchoicesg_2/main.dart';
import 'package:parkchoicesg_2/screens/admin_panel_screen.dart';
import 'package:parkchoicesg_2/screens/preferences_screen.dart';
import 'package:parkchoicesg_2/screens/parking_session_tracker_screen.dart';
import 'package:parkchoicesg_2/services/app_theme_controller.dart';
import 'package:parkchoicesg_2/services/parking_session_manager.dart';

Future<void> frame(WidgetTester tester) async {
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 400));
}

Finder tab(String name) =>
    find.descendant(of: find.byType(NavigationBar), matching: find.text(name));

void main() {
  setUp(() {
    WidgetController.hitTestWarningShouldBeFatal = true;
    SharedPreferences.setMockInitialValues({});
    AppThemeController.instance.setThemeModeForTesting(ThemeMode.light);
    ParkingSessionManager.instance.endSession();
  });
  tearDown(() {
    WidgetController.hitTestWarningShouldBeFatal = false;
    ParkingSessionManager.instance.endSession();
    AppThemeController.instance.setThemeModeForTesting(ThemeMode.system);
  });

  testWidgets(
    'admin override sheets can be repeatedly changed, applied and withdrawn',
    (tester) async {
      tester.view.physicalSize = const Size(430, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(const MaterialApp(home: AdminPanelScreen()));
      for (var i = 0; i < 8; i++) {
        await tester.ensureVisible(find.text('Override'));
        await tester.tap(find.text('Override'));
        await frame(tester);
        await tester.tap(find.byType(DropdownButtonFormField<String>).first);
        await frame(tester);
        await tester.tap(find.text('Marina Square Basement').last);
        await frame(tester);
        await tester.tap(find.byType(DropdownButtonFormField<String>).last);
        await frame(tester);
        await tester.tap(find.text('FORCE OPEN (Override Sensor)').last);
        await frame(tester);
        await tester.enterText(find.byType(TextField).last, 'Test note $i');
        await tester.ensureVisible(find.text('Apply override'));
        await tester.tap(find.text('Apply override'));
        await frame(tester);
        expect(find.text('Test note $i'), findsOneWidget);
        await tester.ensureVisible(find.text('Withdraw').first);
        await tester.tap(find.text('Withdraw').first);
        await frame(tester);
        expect(find.text('Test note $i'), findsNothing);
        expect(tester.takeException(), isNull);
      }
    },
  );

  for (final width in [320.0, 430.0]) {
    testWidgets(
      'active session survives repeated extend/cancel actions at width $width',
      (tester) async {
        tester.view.physicalSize = Size(width, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        ParkingSessionManager.instance.startSession(
          carparkName: 'Test carpark',
          location: 'Public test place',
          hourlyRate: 1.2,
        );
        await tester.pumpWidget(
          const MaterialApp(home: ParkingSessionTrackerScreen()),
        );
        for (var i = 0; i < 8; i++) {
          await tester.ensureVisible(find.text('Extend'));
          await tester.tap(find.text('Extend'));
          await frame(tester);
          await tester.tap(find.text('+1 hour'));
          await frame(tester);
          await tester.tap(find.text('Apply extension'));
          await frame(tester);
          await tester.ensureVisible(find.text('End Session'));
          await tester.tap(find.text('End Session'));
          await frame(tester);
          await tester.tap(find.text('Cancel'));
          await frame(tester);
          expect(ParkingSessionManager.instance.hasActiveSession, isTrue);
          expect(tester.takeException(), isNull);
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await frame(tester);
      },
    );
  }

  for (final width in [320.0, 430.0]) {
    testWidgets(
      '60 reproducible tab transitions with edits and dialogs at width $width',
      (tester) async {
        tester.view.physicalSize = Size(width, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        await tester.pumpWidget(const MyApp());
        final random = Random(26);
        const names = ['Search', 'Tracker', 'Preferences', 'Admin'];
        var currentTab = 'Search';
        for (var i = 0; i < 60; i++) {
          final choices = names.where((name) => name != currentTab).toList();
          final name = choices[random.nextInt(choices.length)];
          currentTab = name;
          await tester.tap(tab(name));
          await frame(tester);
          if (name == 'Search') {
            await tester.enterText(
              find.byType(TextField).first,
              'Test start $i',
            );
            await tester.enterText(find.byType(TextField).last, 'Test end $i');
          } else if (name == 'Preferences') {
            final appearance = find.byKey(
              ValueKey(i.isEven ? 'appearance-dark' : 'appearance-light'),
            );
            await tester.ensureVisible(appearance);
            await tester.tap(appearance);
            await frame(tester);
            await tester.ensureVisible(find.text('Add new location'));
            await tester.tap(find.text('Add new location'));
            await frame(tester);
            await tester.enterText(find.byType(TextField).first, 'Test $i');
            await tester.enterText(
              find.byType(TextField).last,
              'Public test place',
            );
            await tester.tap(find.text('Save location'));
            await frame(tester);
            expect(find.text('Test $i'), findsOneWidget);
          }
          expect(
            tester.takeException(),
            isNull,
            reason: 'iteration $i, $name, width $width',
          );
        }
        await tester.pumpWidget(const SizedBox.shrink());
        await frame(tester);
        expect(tester.takeException(), isNull);
      },
    );
  }

  testWidgets(
    'custom-location sheet fits a small screen with keyboard and large text',
    (tester) async {
      tester.view.physicalSize = const Size(320, 740);
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = 1.5;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpWidget(const MaterialApp(home: PreferencesScreen()));
      await tester.ensureVisible(find.text('Add new location'));
      await tester.tap(find.text('Add new location'));
      await frame(tester);
      tester.view.viewInsets = const FakeViewPadding(bottom: 300);
      addTearDown(tester.view.resetViewInsets);
      await frame(tester);
      expect(tester.takeException(), isNull);
    },
  );

  for (final endingSession in [false, true]) {
    testWidgets(
      'double confirm ${endingSession ? 'end session' : 'erase data'} stays on its screen',
      (tester) async {
        tester.view.physicalSize = const Size(430, 1000);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        if (endingSession) {
          ParkingSessionManager.instance.startSession(
            carparkName: 'Test park',
            location: 'Public location',
            hourlyRate: 1.2,
          );
        }
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
                              builder:
                                  (_) =>
                                      endingSession
                                          ? const ParkingSessionTrackerScreen()
                                          : const PreferencesScreen(),
                            ),
                          ),
                      child: const Text('Open'),
                    ),
                  ),
            ),
          ),
        );
        await tester.tap(find.text('Open'));
        await frame(tester);
        final label = endingSession ? 'End Session' : 'Erase all local data';
        await tester.ensureVisible(find.text(label));
        await tester.tap(find.text(label));
        await frame(tester);
        final button = tester.widget<ElevatedButton>(
          find.widgetWithText(
            ElevatedButton,
            endingSession ? 'Confirm end' : 'Erase data',
          ),
        );
        button.onPressed!();
        button.onPressed!();
        await frame(tester);
        expect(find.text('Open'), findsNothing);
        expect(
          endingSession
              ? find.byType(ParkingSessionTrackerScreen)
              : find.byType(PreferencesScreen),
          findsOneWidget,
        );
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        await frame(tester);
      },
    );
  }
}
