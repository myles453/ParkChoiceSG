import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:parkchoicesg_2/services/device_location.dart';

class SlowLocationProvider extends GeolocatorPlatform {
  final bool bothProvidersFail;
  final List<LocationSettings?> requests = [];
  SlowLocationProvider({this.bothProvidersFail = false});

  @override
  Future<bool> isLocationServiceEnabled() async => true;

  @override
  Future<LocationPermission> checkPermission() async =>
      LocationPermission.whileInUse;

  @override
  Future<Position> getCurrentPosition({
    LocationSettings? locationSettings,
  }) async {
    requests.add(locationSettings);
    if (requests.length == 1 || bothProvidersFail) {
      throw TimeoutException('No device fix');
    }
    return Position(
      latitude: 1.3,
      longitude: 103.8,
      timestamp: DateTime.now(),
      accuracy: 25,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late GeolocatorPlatform original;
  setUp(() {
    original = GeolocatorPlatform.instance;
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
  });
  tearDown(() {
    GeolocatorPlatform.instance = original;
    debugDefaultTargetPlatformOverride = null;
  });

  test(
    'Android tries its native provider after a fused provider timeout',
    () async {
      final provider = SlowLocationProvider();
      GeolocatorPlatform.instance = provider;
      final location = await currentDeviceLocation();
      expect(provider.requests, hasLength(2));
      expect(provider.requests.last, isA<AndroidSettings>());
      expect(
        (provider.requests.last as AndroidSettings).forceLocationManager,
        isTrue,
      );
      expect(location['coordinate'], {'latitude': 1.3, 'longitude': 103.8});
      expect(location['accuracy_meters'], 25);
    },
  );

  test(
    'failure of both providers returns an error without inventing a fix',
    () async {
      final provider = SlowLocationProvider(bothProvidersFail: true);
      GeolocatorPlatform.instance = provider;
      await expectLater(
        currentDeviceLocation(),
        throwsA(isA<TimeoutException>()),
      );
      expect(provider.requests, hasLength(2));
    },
  );
}
