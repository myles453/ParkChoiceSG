import 'package:flutter/foundation.dart';

/// One active stay. Cost accrues per second at [hourlyRate] dollars per hour.
class ParkingSession {
  final String carparkName;
  final String location;
  final double hourlyRate;
  final DateTime startTime;

  ParkingSession({
    required this.carparkName,
    required this.location,
    required this.hourlyRate,
    required this.startTime,
  });

  Duration get duration => DateTime.now().difference(startTime);

  double get runningCost {
    final seconds = duration.inSeconds;
    return (seconds / 3600.0) * hourlyRate;
  }
}

/// Holds at most one active session in memory and notifies listeners on change.
class ParkingSessionManager extends ValueNotifier<ParkingSession?> {
  static final ParkingSessionManager instance =
      ParkingSessionManager._internal();

  ParkingSessionManager._internal() : super(null);

  bool get hasActiveSession => value != null;

  ParkingSession? get currentSession => value;

  /// Starts a session now. Returns false when one is already active.
  bool startSession({
    required String carparkName,
    required String location,
    required double hourlyRate,
  }) {
    if (hasActiveSession) {
      return false;
    }
    value = ParkingSession(
      carparkName: carparkName,
      location: location,
      hourlyRate: hourlyRate,
      startTime: DateTime.now(),
    );
    return true;
  }

  /// Ends the active session, if any.
  void endSession() {
    value = null;
  }
}
