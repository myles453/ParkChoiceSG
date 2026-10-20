import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:parkchoicesg_2/screens/admin_panel_screen.dart';
import 'package:parkchoicesg_2/screens/operator_login_screen.dart';
import 'package:parkchoicesg_2/services/operator_session.dart';
import 'package:parkchoicesg_2/services/parking_api.dart';

ParkingApi _api(int status) => ParkingApi(
  baseUrl: 'http://test',
  client: MockClient((request) async {
    expect(request.url.path, '/operator/login');
    final body = jsonDecode(request.body) as Map<String, dynamic>;
    expect(body.keys, containsAll(['username', 'password']));
    return http.Response(jsonEncode({'status': 'x'}), status);
  }),
);

Future<void> _submit(WidgetTester tester, ParkingApi api) async {
  tester.view.physicalSize = const Size(430, 932);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  await tester.pumpWidget(MaterialApp(home: OperatorLoginScreen(api: api)));
  await tester.enterText(
    find.descendant(
      of: find.byKey(const Key('operator-username')),
      matching: find.byType(TextField),
    ),
    'operator',
  );
  await tester.enterText(
    find.descendant(
      of: find.byKey(const Key('operator-password')),
      matching: find.byType(TextField),
    ),
    'secret',
  );
  await tester.tap(find.text('Sign in'));
  await tester.pumpAndSettle();
}

void main() {
  setUp(OperatorSession.instance.signOut);

  test('admin tab opens sign-in until the operator signs in', () {
    expect(operatorEntryScreen(), isA<OperatorLoginScreen>());
    OperatorSession.instance.signIn();
    expect(operatorEntryScreen(), isA<AdminPanelScreen>());
  });

  testWidgets('wrong credentials stay on sign-in with an error', (
    tester,
  ) async {
    await _submit(tester, _api(401));
    expect(find.text('Incorrect operator username or password.'), findsOne);
    expect(OperatorSession.instance.signedIn, isFalse);
  });

  testWidgets('unconfigured backend reports sign-in unavailable', (
    tester,
  ) async {
    await _submit(tester, _api(503));
    expect(
      find.text('Operator sign-in is unavailable. Please try again.'),
      findsOne,
    );
    expect(OperatorSession.instance.signedIn, isFalse);
  });

  testWidgets('correct credentials open the admin panel', (tester) async {
    await _submit(tester, _api(200));
    expect(OperatorSession.instance.signedIn, isTrue);
    expect(find.text('Admin panel'), findsOne);
  });
}
