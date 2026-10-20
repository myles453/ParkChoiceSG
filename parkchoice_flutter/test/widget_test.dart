import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:parkchoicesg_2/constants.dart';
import 'package:parkchoicesg_2/main.dart';
import 'package:parkchoicesg_2/services/app_theme_controller.dart';
import 'package:parkchoicesg_2/services/operator_session.dart';
import 'package:parkchoicesg_2/services/parking_session_manager.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
    AppThemeController.instance.setThemeModeForTesting(ThemeMode.light);
    ParkingSessionManager.instance.endSession();
    OperatorSession.instance.signOut();
  });

  tearDown(() {
    AppThemeController.instance.setThemeModeForTesting(ThemeMode.system);
    ParkingSessionManager.instance.endSession();
  });

  testWidgets('driver starts at anonymous parking search', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const MyApp());

    expect(find.text('Find parking'), findsOneWidget);
    expect(find.text('Create Account'), findsNothing);
    expect(find.text('Find carparks'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
    expect(tester.takeException(), isNull);
  });

  testWidgets('appearance control switches the complete app theme', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(430, 932);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MyApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    await tester.tap(find.text('Preferences'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(find.text('Appearance'), findsOneWidget);
    expect(find.byKey(const ValueKey('appearance-dark')), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('appearance-dark')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    final darkContext = tester.element(find.byType(Scaffold).first);
    expect(Theme.of(darkContext).brightness, Brightness.dark);
    expect(darkContext.appColors.canvas, AppColors.dark.canvas);
    expect(
      find.text('Dark appearance stays on until you change it.'),
      findsOneWidget,
    );

    await tester.tap(find.byKey(const ValueKey('appearance-light')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));

    expect(
      Theme.of(tester.element(find.byType(Scaffold).first)).brightness,
      Brightness.light,
    );
    expect(tester.takeException(), isNull);
  });

  testWidgets('primary navigation reaches every main feature', (
    WidgetTester tester,
  ) async {
    tester.view.physicalSize = const Size(430, 932);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(const MyApp());
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Find parking'), findsOneWidget);

    await tester.tap(find.text('Tracker'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Active session'), findsOneWidget);

    await tester.tap(find.text('Admin'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Operator sign-in'), findsOneWidget);
    expect(find.text('Admin panel'), findsNothing);

    await tester.tap(find.text('Search'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 500));
    expect(find.text('Find parking'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
