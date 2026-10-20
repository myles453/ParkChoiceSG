import 'package:url_launcher/url_launcher.dart';

/// Google Maps URL handoff uses no paid routing API or embedded Google map.
Uri carparkNavigationUrl(num latitude, num longitude) {
  if (!latitude.isFinite ||
      !longitude.isFinite ||
      latitude < -90 ||
      latitude > 90 ||
      longitude < -180 ||
      longitude > 180) {
    throw ArgumentError('Invalid navigation destination');
  }
  return Uri.https('www.google.com', '/maps/dir/', {
    'api': '1',
    'destination': '$latitude,$longitude',
    'travelmode': 'driving',
    'dir_action': 'navigate',
  });
}

Future<bool> openExternalNavigation(Uri uri) =>
    launchUrl(uri, mode: LaunchMode.externalApplication);
