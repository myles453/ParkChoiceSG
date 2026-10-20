import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import 'package:url_launcher/url_launcher.dart';

/// Public OneMap tiles; coordinates come from the selected search and results.
class CarparkMapScreen extends StatefulWidget {
  final Map<String, dynamic> origin;
  final Map<String, dynamic> destination;
  final List<Map<String, dynamic>> carparks;
  final TileProvider? tileProvider;
  const CarparkMapScreen({
    super.key,
    required this.origin,
    required this.destination,
    required this.carparks,
    this.tileProvider,
  });

  @override
  State<CarparkMapScreen> createState() => _CarparkMapScreenState();
}

class _CarparkMapScreenState extends State<CarparkMapScreen> {
  bool _tileError = false;

  LatLng point(Map value) => LatLng(
    (value['latitude'] as num).toDouble(),
    (value['longitude'] as num).toDouble(),
  );

  Marker marker(LatLng point, Color color, String label, IconData icon) =>
      Marker(
        point: point,
        width: 44,
        height: 44,
        child: Tooltip(
          message: label,
          child: IconButton(
            icon: Icon(icon, color: color, size: 32),
            onPressed:
                () => ScaffoldMessenger.of(
                  context,
                ).showSnackBar(SnackBar(content: Text(label))),
          ),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final start = point(widget.origin['coordinate'] as Map);
    final end = point(widget.destination['coordinate'] as Map);
    final validCarparks =
        widget.carparks
            .where((r) => r['latitude'] is num && r['longitude'] is num)
            .toList();
    final points = [start, end, ...validCarparks.map(point)];
    return Scaffold(
      appBar: AppBar(title: const Text('Carparks on OneMap')),
      body: Column(
        children: [
          if (_tileError)
            const Padding(
              padding: EdgeInsets.all(8),
              child: Text(
                'Map tiles are unavailable. Return to the list to compare carparks.',
              ),
            ),
          const Padding(
            padding: EdgeInsets.all(8),
            child: Text('Blue: start · Red: destination · Green: carpark'),
          ),
          Expanded(
            child: FlutterMap(
              options: MapOptions(
                initialCameraFit: CameraFit.bounds(
                  bounds: LatLngBounds.fromPoints(points),
                  padding: const EdgeInsets.all(48),
                  maxZoom: 16,
                ),
                minZoom: 11,
                maxZoom: 19,
                cameraConstraint: CameraConstraint.contain(
                  bounds: LatLngBounds(
                    const LatLng(1.144, 103.535),
                    const LatLng(1.494, 104.502),
                  ),
                ),
              ),
              children: [
                TileLayer(
                  urlTemplate:
                      'https://www.onemap.gov.sg/maps/tiles/Default/{z}/{x}/{y}.png',
                  userAgentPackageName: 'sg.parkchoicesg.student',
                  tileProvider: widget.tileProvider,
                  errorTileCallback: (_, _, _) {
                    if (mounted && !_tileError) {
                      setState(() => _tileError = true);
                    }
                  },
                ),
                MarkerLayer(
                  markers: [
                    marker(
                      start,
                      Colors.blue,
                      'Starting location',
                      Icons.trip_origin,
                    ),
                    marker(end, Colors.red, 'Destination', Icons.location_on),
                    ...validCarparks.map(
                      (r) => marker(
                        point(r),
                        Colors.green,
                        r['display_name'].toString(),
                        Icons.local_parking,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          // Keep the provider's logo, links and attribution visible.
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Image.network(
                'https://www.onemap.gov.sg/web-assets/images/logo/om_logo.png',
                height: 20,
                width: 20,
                errorBuilder: (_, _, _) => const SizedBox(width: 20),
              ),
              TextButton(
                onPressed:
                    () => launchUrl(Uri.parse('https://www.onemap.gov.sg/')),
                child: const Text('OneMap'),
              ),
              const Text('© contributors |'),
              TextButton(
                onPressed:
                    () => launchUrl(Uri.parse('https://www.sla.gov.sg/')),
                child: const Text('Singapore Land Authority'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
