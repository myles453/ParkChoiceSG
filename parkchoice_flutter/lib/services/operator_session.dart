import 'package:flutter/foundation.dart';

/// Operator sign-in state for this app run only.
///
/// Drivers never sign in. The backend checks the single operator credential
/// held in server configuration, and the app keeps nothing on disk, so the
/// operator signs in again after every restart.
class OperatorSession extends ValueNotifier<bool> {
  OperatorSession._() : super(false);

  static final OperatorSession instance = OperatorSession._();

  bool get signedIn => value;

  void signIn() => value = true;

  void signOut() => value = false;
}
