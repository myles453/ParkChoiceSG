import 'package:flutter/material.dart';

import '../services/parking_api.dart';
import '../services/device_location.dart';
import '../services/navigation_handoff.dart';
import '../widgets/bottom_nav_bar.dart';
import 'operator_login_screen.dart';
import 'parking_session_tracker_screen.dart';
import 'preferences_screen.dart';
import 'carpark_map_screen.dart';

/// Home screen: pick a destination and stay length, then see ranked carparks.
///
/// [api], [locate] and [launchNavigation] are injectable so tests run offline.
class CarparkSearchScreen extends StatefulWidget {
  final ParkingApi? api;
  final Future<Map<String, dynamic>> Function()? locate;
  final Future<bool> Function(Uri)? launchNavigation;
  const CarparkSearchScreen({
    super.key,
    this.api,
    this.locate,
    this.launchNavigation,
  });

  @override
  State<CarparkSearchScreen> createState() => _CarparkSearchScreenState();
}

class _CarparkSearchScreenState extends State<CarparkSearchScreen> {
  final _originText = TextEditingController();
  final _destinationText = TextEditingController();
  late final ParkingApi _api;
  Map<String, dynamic>? _origin;
  Map<String, dynamic>? _destination;
  Map<String, dynamic>? _result;
  int _duration = 60;
  bool _busy = false;
  String? _message;

  @override
  void initState() {
    super.initState();
    _api = widget.api ?? ParkingApi();
  }

  @override
  void dispose() {
    _originText.dispose();
    _destinationText.dispose();
    if (widget.api == null) _api.close();
    super.dispose();
  }

  Future<void> _chooseLocation(bool startingPoint) async {
    final controller = startingPoint ? _originText : _destinationText;
    if (controller.text.trim().isEmpty) {
      setState(() => _message = 'Enter a place name or postal code first.');
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
      _result = null;
    });
    try {
      final matches = await _api.destinations(controller.text.trim());
      if (!mounted) return;
      if (matches.isEmpty) {
        setState(
          () =>
              _message =
                  'No matching locations. Try another name or postal code.',
        );
        return;
      }
      setState(() => _busy = false);
      final selected = await showModalBottomSheet<Map<String, dynamic>>(
        context: context,
        showDragHandle: true,
        builder:
            (context) => SafeArea(
              child: SizedBox(
                height: 400,
                child: ListView.builder(
                  itemCount: matches.length,
                  itemBuilder:
                      (context, index) => ListTile(
                        title: Text(matches[index]['name'] as String),
                        subtitle: Text(matches[index]['address'] as String),
                        onTap: () => Navigator.pop(context, matches[index]),
                      ),
                ),
              ),
            ),
      );
      if (!mounted || selected == null) return;
      setState(() {
        if (startingPoint) {
          _origin = selected;
        } else {
          _destination = selected;
        }
        controller.text = selected['name'] as String;
      });
    } catch (_) {
      if (mounted) {
        setState(
          () =>
              _message =
                  'Location search is unavailable. Check your connection and try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _findParking() async {
    if (_origin == null || _destination == null) {
      setState(
        () =>
            _message =
                'Search and select both your starting location and destination.',
      );
      return;
    }
    final locatedAt = DateTime.tryParse(
      _origin!['located_at']?.toString() ?? '',
    );
    if (locatedAt != null &&
        DateTime.now().difference(locatedAt) > const Duration(minutes: 2)) {
      setState(
        () =>
            _message = 'Refresh your current location before searching again.',
      );
      return;
    }
    setState(() {
      _busy = true;
      _message = null;
      _result = null;
    });
    try {
      final result = await _api.recommend(
        origin: Map<String, dynamic>.from(_origin!['coordinate'] as Map),
        destination: Map<String, dynamic>.from(
          _destination!['coordinate'] as Map,
        ),
        durationMinutes: _duration,
      );
      if (mounted) setState(() => _result = result);
    } catch (_) {
      if (mounted) {
        setState(
          () =>
              _message =
                  'Parking comparison is unavailable. Please try again shortly.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _useCurrentLocation() async {
    setState(() {
      _busy = true;
      _message = null;
      _result = null;
      _origin = null;
    });
    try {
      final location = await (widget.locate ?? currentDeviceLocation)();
      if (!mounted) return;
      setState(() {
        _origin = location;
        _originText.text = 'Current location';
      });
    } catch (error) {
      if (mounted) {
        setState(
          () =>
              _message =
                  error is StateError
                      ? error.message.toString()
                      : 'Could not get your location. Choose a starting place instead.',
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _openNavigation(Map<String, dynamic> row) async {
    try {
      final uri = carparkNavigationUrl(
        row['latitude'] as num,
        row['longitude'] as num,
      );
      final opened = await (widget.launchNavigation ?? openExternalNavigation)(
        uri,
      );
      if (opened || !mounted) return;
    } catch (_) {
      if (!mounted) return;
    }
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Could not open navigation. Please try again.'),
        ),
      );
    }
  }

  Widget _locationField(bool origin) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: TextField(
      controller: origin ? _originText : _destinationText,
      enabled: !_busy,
      decoration: InputDecoration(
        labelText: origin ? 'Starting location' : 'Destination',
        hintText: 'Place name or postal code',
        border: const OutlineInputBorder(),
        suffixIcon: IconButton(
          tooltip: origin ? 'Search starting location' : 'Search destination',
          onPressed: _busy ? null : () => _chooseLocation(origin),
          icon: const Icon(Icons.search),
        ),
      ),
      onSubmitted: (_) => _chooseLocation(origin),
      onChanged:
          (_) => setState(() {
            if (origin) {
              _origin = null;
            } else {
              _destination = null;
            }
            _result = null;
          }),
    ),
  );

  Widget _carparkCard(Map<String, dynamic> row, int? rank) {
    final price = row['price'] as Map;
    final driving = row['driving'] as Map;
    final walking = row['walking'] as Map;
    final current = row['current_availability'] as Map?;
    final prediction = row['prediction'] as Map;
    final probability = prediction['p_free'] as num?;
    final predictionUnavailable = switch (prediction['status']) {
      'unsupported_horizon_15_to_90_minutes' =>
        'Arrival predictions are supported for trips of 15–90 minutes.',
      'historical_profile_not_enabled' =>
        'Recent readings are unavailable. Historical profiles are not used for ranking.',
      'model_service_unavailable' =>
        'Arrival prediction service is unavailable.',
      _ => 'Arrival prediction pending or unavailable',
    };
    final cents = price['amount_cents'] as num?;
    final minCents = price['amount_min_cents'] as num?;
    final maxCents = price['amount_max_cents'] as num?;
    final hasCostRange =
        minCents != null && maxCents != null && minCents != maxCents;
    final drivingSeconds = driving['duration_seconds'] as num?;
    final walkingMeters = walking['distance_meters'] as num?;
    final stamp =
        DateTime.tryParse(current?['timestamp']?.toString() ?? '')?.toLocal();
    final timeText =
        stamp == null
            ? ''
            : '${stamp.hour.toString().padLeft(2, '0')}:${stamp.minute.toString().padLeft(2, '0')}';
    final exclusions = row['ranking_exclusions'] as List;
    final canNavigate = row['latitude'] is num && row['longitude'] is num;
    final availabilityLabel = switch (current?['status']) {
      'fresh_source_update' => 'Current reported availability',
      'recent_retrieval_only' => 'Latest retrieved availability',
      'stale' => 'Last reported availability (stale)',
      _ => 'Published availability',
    };
    return Card(
      margin: const EdgeInsets.only(top: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${rank == null ? '' : '#$rank  '}${row['display_name']}',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            if (canNavigate)
              TextButton.icon(
                onPressed: () => _openNavigation(row),
                icon: const Icon(Icons.navigation_outlined),
                label: const Text('Navigate to carpark'),
              ),
            if (row['address'] != null) Text(row['address'].toString()),
            const SizedBox(height: 8),
            Text(
              cents == null
                  ? 'Cost estimate unavailable'
                  : hasCostRange
                  ? '\$${(minCents / 100).toStringAsFixed(2)}–\$${(maxCents / 100).toStringAsFixed(2)} for $_duration min'
                  : '\$${(cents / 100).toStringAsFixed(2)} for $_duration min',
            ),
            if (hasCostRange)
              const Text(
                'Ranking uses the higher neighbouring-minute estimate.',
              ),
            Text(
              drivingSeconds == null
                  ? 'Driving route unavailable'
                  : '${(drivingSeconds / 60).ceil()} min drive',
            ),
            Text(
              walkingMeters == null
                  ? 'Walking route unavailable'
                  : '${walkingMeters.round()} m walk to destination',
            ),
            Text(
              '$availabilityLabel: ${current?['available_lots'] ?? 'unavailable'}',
            ),
            if (stamp != null)
              Text(
                '${current?['timestamp_kind'] == 'source_update' ? 'Updated' : 'Retrieved'} $timeText',
              ),
            Text(
              prediction['status'] == 'ok'
                  ? probability != null
                      ? '${(probability * 100).toStringAsFixed(1)}% chance of at least one free lot at arrival (${prediction['confidence']} band)'
                      : 'Predicted at arrival: ${prediction['available_lots']} lots (${prediction['confidence']} confidence)'
                  : predictionUnavailable,
            ),
            if (exclusions.isNotEmpty)
              const Text(
                'Not included in the arrival-forecast ranking: a required route, price or forecast is unavailable or unsuitable.',
              ),
          ],
        ),
      ),
    );
  }

  List<Widget> _results() {
    if (_result == null) return [];
    final ranked = (_result!['ranked'] as List).cast<Map<String, dynamic>>();
    final fallback =
        ((_result!['fallback_ranked'] as List?) ?? [])
            .cast<Map<String, dynamic>>();
    final showingFallback = ranked.isEmpty && fallback.isNotEmpty;
    final ranks = {
      for (final r in showingFallback ? fallback : ranked)
        '${r['agency']}/${r['carpark_id']}': r['rank'] as int,
    };
    final rows =
        (_result!['candidates'] as List).cast<Map<String, dynamic>>().toList()
          ..sort(
            (a, b) => (ranks['${a['agency']}/${a['carpark_id']}'] ?? 999)
                .compareTo(ranks['${b['agency']}/${b['carpark_id']}'] ?? 999),
          );
    return [
      const SizedBox(height: 20),
      Text(
        showingFallback
            ? 'Current-reading options'
            : ranked.isEmpty
            ? 'No comparable carparks found'
            : 'Parking comparison',
        style: Theme.of(context).textTheme.titleLarge,
      ),
      Text(
        showingFallback
            ? _result!['fallback_notice'].toString()
            : _result!['ranking_basis'] == 'current_availability_baseline'
            ? 'Ranked using current reported availability. Arrival predictions are not ready yet.'
            : _result!['ranking_basis'] == 'arrival_free_probability'
            ? 'Ranked using the chance of a free lot at arrival. HDB carparks only.'
            : 'Ranked using predicted availability at arrival.',
      ),
      const Text(
        'The ranking weights are being evaluated. Route times and charges are estimates.',
      ),
      if (rows.isNotEmpty)
        OutlinedButton.icon(
          onPressed:
              () => Navigator.push(
                context,
                MaterialPageRoute<void>(
                  builder:
                      (_) => CarparkMapScreen(
                        origin: _origin!,
                        destination: _destination!,
                        carparks: rows,
                      ),
                ),
              ),
          icon: const Icon(Icons.map_outlined),
          label: const Text('View map'),
        ),
      if (rows.isEmpty)
        const Text(
          'Try another destination. Nearby carparks may lack supported prices or fresh availability.',
        ),
      ...rows.map(
        (row) =>
            _carparkCard(row, ranks['${row['agency']}/${row['carpark_id']}']),
      ),
    ];
  }

  void _navigate(int index) {
    final Widget? page = switch (index) {
      1 => const ParkingSessionTrackerScreen(),
      2 => const PreferencesScreen(),
      3 => operatorEntryScreen(),
      _ => null,
    };
    if (page != null) {
      Navigator.pushReplacement(
        context,
        PageRouteBuilder<void>(
          pageBuilder: (_, animation, secondaryAnimation) => page,
          transitionDuration: Duration.zero,
          reverseTransitionDuration: Duration.zero,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Find parking')),
    bottomNavigationBar: ParkChoiceBottomNav(
      selectedIndex: 0,
      onDestinationSelected: _navigate,
    ),
    body: SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Padding(
              padding: EdgeInsets.only(bottom: 16),
              child: Text('Plan your parking before you start driving.'),
            ),
            _locationField(true),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: _busy ? null : _useCurrentLocation,
                icon: const Icon(Icons.my_location),
                label: const Text('Use current location'),
              ),
            ),
            if (_origin?['accuracy_meters'] is num)
              Text(
                'Location accuracy: about ${(_origin!['accuracy_meters'] as num).round()} m',
              ),
            _locationField(false),
            DropdownButtonFormField<int>(
              initialValue: _duration,
              decoration: const InputDecoration(
                labelText: 'Parking duration',
                border: OutlineInputBorder(),
              ),
              items:
                  [30, 60, 90, 120, 180, 240]
                      .map(
                        (n) => DropdownMenuItem(
                          value: n,
                          child: Text('$n minutes'),
                        ),
                      )
                      .toList(),
              onChanged:
                  _busy
                      ? null
                      : (n) => setState(() {
                        _duration = n!;
                        _result = null;
                      }),
            ),
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _busy ? null : _findParking,
              child: const Text('Find carparks'),
            ),
            if (_busy)
              const Padding(
                padding: EdgeInsets.all(16),
                child: Center(child: CircularProgressIndicator()),
              ),
            if (_message != null)
              Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Text(_message!),
              ),
            ..._results(),
          ],
        ),
      ),
    ),
  );
}
