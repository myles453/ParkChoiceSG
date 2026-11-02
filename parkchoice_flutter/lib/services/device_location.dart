import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

/// One location fix after a user action. No background tracking or persistence.
Future<Map<String, dynamic>> currentDeviceLocation() async {
  if (!await Geolocator.isLocationServiceEnabled().timeout(
    const Duration(seconds: 5),
  )) {
    throw StateError(
      'Location services are off. Choose a starting place instead.',
    );
  }
  var permission = await Geolocator.checkPermission().timeout(
    const Duration(seconds: 5),
  );
  if (permission == LocationPermission.denied) {
    permission = await Geolocator.requestPermission();
  }
  if (permission == LocationPermission.denied ||
      permission == LocationPermission.deniedForever) {
    throw StateError(
      'Location permission was not granted. Choose a starting place instead.',
    );
  }
  Position position;
  try {
    position = await Geolocator.getCurrentPosition(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 10),
      ),
    );
  } on TimeoutException {
    if (kIsWeb || defaultTargetPlatform != TargetPlatform.android) rethrow;
    // Some devices stall in the Play Services provider. Try Android's own
    // provider once; both requests remain bounded and require permission.
    position = await Geolocator.getCurrentPosition(
      locationSettings: AndroidSettings(
        forceLocationManager: true,
        accuracy: LocationAccuracy.medium,
        timeLimit: const Duration(seconds: 8),
      ),
    );
  }
  final measuredAt = position.timestamp.toUtc();
  final age = DateTime.now().toUtc().difference(measuredAt);
  if (age > const Duration(minutes: 2) || age < const Duration(seconds: -30)) {
    throw StateError(
      'The device returned an old location. Try again or choose a starting place.',
    );
  }
  if (!position.latitude.isFinite ||
      !position.longitude.isFinite ||
      position.latitude < 1.144 ||
      position.latitude > 1.494 ||
      position.longitude < 103.535 ||
      position.longitude > 104.502) {
    throw StateError(
      'Your location is outside the Singapore map area. Choose a starting place instead.',
    );
  }
  return {
    'name': 'Current location',
    'address': 'Location from your device',
    'coordinate': {
      'latitude': position.latitude,
      'longitude': position.longitude,
    },
    'accuracy_meters': position.accuracy,
    'located_at': measuredAt.toIso8601String(),
  };
}
