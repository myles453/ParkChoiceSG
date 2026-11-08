import 'dart:convert';

import 'package:http/http.dart' as http;
import '../models/ranking_mode.dart';

/// HTTP client for the parking backend; credentials remain on the server.
class ParkingApi {
  final http.Client _client;
  final String baseUrl;

  ParkingApi({http.Client? client, String? baseUrl})
    : _client = client ?? http.Client(),
      baseUrl =
          baseUrl ??
          const String.fromEnvironment(
            'PARKING_API_URL',
            defaultValue: 'http://127.0.0.1:8000',
          );

  Future<Map<String, dynamic>> _post(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl$path'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode(body),
        )
        .timeout(const Duration(seconds: 60));
    if (response.statusCode != 200) {
      throw Exception('The parking service is unavailable. Please try again.');
    }
    return _object(jsonDecode(response.body));
  }

  /// Destination matches from OneMap search, for the driver to choose from.
  Future<List<Map<String, dynamic>>> destinations(String query) async {
    final result = await _post('/destinations', {'query': query});
    final matches = _rows(result['matches']);
    for (final place in matches) {
      if (place['name'] is! String ||
          place['address'] is! String ||
          !_coordinate(place['coordinate'])) {
        throw const FormatException('Invalid location response');
      }
    }
    return matches;
  }

  /// Ranked carparks with price, routing, availability and score breakdown.
  Future<Map<String, dynamic>> recommend({
    required Map<String, dynamic> origin,
    required Map<String, dynamic> destination,
    required int durationMinutes,
    RankingMode rankingMode = RankingMode.bestOverall,
  }) async {
    final result = await _post('/recommend', {
      'origin': origin,
      'destination': destination,
      'duration_minutes': durationMinutes,
      'candidate_limit': 3,
      'radius_meters': 1500,
      'ranking_mode': rankingMode.apiValue,
    });
    // Validate before assigning to screen state: build-time cast errors cannot
    // be caught by the screen's request error handler.
    for (final key in ['ranked', 'fallback_ranked']) {
      for (final row in _rows(
        key == 'fallback_ranked' ? result[key] ?? [] : result[key],
      )) {
        if (row['agency'] is! String ||
            row['carpark_id'] is! String ||
            row['rank'] is! int ||
            (row['rank'] as int) < 1) {
          throw const FormatException('Invalid ranking response');
        }
      }
    }
    for (final row in _rows(result['candidates'])) {
      if (row['agency'] is! String ||
          row['carpark_id'] is! String ||
          row['display_name'] is! String ||
          row['ranking_exclusions'] is! List) {
        throw const FormatException('Invalid carpark response');
      }
      final price = _object(row['price']);
      final driving = _object(row['driving']);
      final walking = _object(row['walking']);
      final prediction = _object(row['prediction']);
      for (final value in [
        price['amount_cents'],
        price['amount_min_cents'],
        price['amount_max_cents'],
        driving['duration_seconds'],
        walking['distance_meters'],
        prediction['p_free'],
        prediction['available_lots'],
      ]) {
        if (value != null && (value is! num || !value.isFinite || value < 0)) {
          throw const FormatException('Invalid comparison measurement');
        }
      }
      if (prediction['p_free'] != null && (prediction['p_free'] as num) > 1) {
        throw const FormatException('Invalid arrival probability');
      }
      if (row['current_availability'] != null) {
        _object(row['current_availability']);
      }
    }
    return result;
  }

  static Map<String, dynamic> _object(Object? value) {
    if (value is! Map<String, dynamic>) {
      throw const FormatException('Incomplete parking service response');
    }
    return value;
  }

  static List<Map<String, dynamic>> _rows(Object? value) {
    if (value is! List) {
      throw const FormatException('Incomplete parking service response');
    }
    return value.map(_object).toList();
  }

  static bool _coordinate(Object? value) {
    if (value is! Map) return false;
    final lat = value['latitude'], lng = value['longitude'];
    return lat is num &&
        lng is num &&
        lat.isFinite &&
        lng.isFinite &&
        lat >= -90 &&
        lat <= 90 &&
        lng >= -180 &&
        lng <= 180;
  }

  /// Returns true for a correct operator credential and false for a wrong one.
  /// Throws when the backend is unreachable or has no operator configured.
  Future<bool> operatorLogin({
    required String username,
    required String password,
  }) async {
    final response = await _client
        .post(
          Uri.parse('$baseUrl/operator/login'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'username': username, 'password': password}),
        )
        .timeout(const Duration(seconds: 15));
    if (response.statusCode == 200) return true;
    if (response.statusCode == 401 || response.statusCode == 422) return false;
    throw Exception('Operator sign-in is unavailable. Please try again.');
  }

  void close() => _client.close();
}
