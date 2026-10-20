import 'package:geolocator/geolocator.dart';

/// One location fix after a user action. No background tracking or persistence.
Future<Map<String, dynamic>> currentDeviceLocation() async {
  if (!await Geolocator.isLocationServiceEnabled()) {
    throw StateError(
      'Location services are off. Choose a starting place instead.',
    );
  }
  var permission = await Geolocator.checkPermission();
  if (permission == LocationPermission.denied) {
    permission = await Geolocator.requestPermission();
  }
  if (permission == LocationPermission.denied ||
      permission == LocationPermission.deniedForever) {
    throw StateError(
      'Location permission was not granted. Choose a starting place instead.',
    );
  }
  final position = await Geolocator.getCurrentPosition(
    locationSettings: const LocationSettings(
      accuracy: LocationAccuracy.high,
      timeLimit: Duration(seconds: 15),
    ),
  );
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
