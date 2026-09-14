import 'package:flutter/foundation.dart';

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

class ParkingSessionManager extends ValueNotifier<ParkingSession?> {
  static final ParkingSessionManager instance =
      ParkingSessionManager._internal();

  ParkingSessionManager._internal() : super(null);

  bool get hasActiveSession => value != null;

  ParkingSession? get currentSession => value;

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

  void endSession() {
    value = null;
  }
}
