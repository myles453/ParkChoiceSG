import 'dart:convert';

import 'package:http/http.dart' as http;

/// The app calls our backend; provider keys and database credentials stay there.
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
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<List<Map<String, dynamic>>> destinations(String query) async {
    final result = await _post('/destinations', {'query': query});
    return (result['matches'] as List).cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> recommend({
    required Map<String, dynamic> origin,
    required Map<String, dynamic> destination,
    required int durationMinutes,
  }) => _post('/recommend', {
    'origin': origin,
    'destination': destination,
    'duration_minutes': durationMinutes,
    'candidate_limit': 3,
    'radius_meters': 1500,
  });

  void close() => _client.close();
}
