import 'package:flutter/material.dart';

import '../constants.dart';
import '../services/parking_session_manager.dart';
import '../widgets/app_ui.dart';
import '../widgets/bottom_nav_bar.dart';
import 'admin_panel_screen.dart';
import 'parking_session_tracker_screen.dart';
import 'preferences_screen.dart';

class CarparkSearchScreen extends StatefulWidget {
  const CarparkSearchScreen({super.key});

  @override
  State<CarparkSearchScreen> createState() => _CarparkSearchScreenState();
}

class _CarparkModel {
  final String name;
  final String driveTime;
  final String pricePerHour;
  final int spotsLeft;
  final int spotsTotal;
  final int rank;
  final String walkTime;
  final String confidenceLevel;
  final String confidenceText;

  const _CarparkModel({
    required this.name,
    required this.driveTime,
    required this.pricePerHour,
    required this.spotsLeft,
    required this.spotsTotal,
    required this.rank,
    required this.walkTime,
    required this.confidenceLevel,
    required this.confidenceText,
  });
}

class _CarparkSearchScreenState extends State<CarparkSearchScreen>
    with SingleTickerProviderStateMixin {
  final _searchController = TextEditingController(
    text: 'Orchard Road Mall District, SG',
  );

  String _stayDuration = '2 Hours stay';
  String _eta = 'ETA: 10:15 AM';
  String _sortBy = 'Sort: Best Match';
  String _filterFeature = 'Filter: All Carparks';
  static const int _selectedNavIndex = 0;
  bool _isMapView = false;
  late AnimationController _livePulseController;

  final List<_CarparkModel> _carparks = const [
    _CarparkModel(
      name: 'Orchard Central Terminal',
      driveTime: '12 min drive',
      pricePerHour: r'$4.50/hr',
      spotsLeft: 48,
      spotsTotal: 320,
      rank: 1,
      walkTime: '5 min walk',
      confidenceLevel: 'High',
      confidenceText: 'High confidence',
    ),
    _CarparkModel(
      name: 'Suntec Plaza Level B2',
      driveTime: '8 min drive',
      pricePerHour: r'$5.00/hr',
      spotsLeft: 12,
      spotsTotal: 450,
      rank: 2,
      walkTime: '6 min walk',
      confidenceLevel: 'Medium',
      confidenceText: 'Med confidence',
    ),
    _CarparkModel(
      name: 'Somerset Underground',
      driveTime: '15 min drive',
      pricePerHour: r'$3.80/hr',
      spotsLeft: 142,
      spotsTotal: 200,
      rank: 3,
      walkTime: '8 min walk',
      confidenceLevel: 'High',
      confidenceText: 'High confidence',
    ),
    _CarparkModel(
      name: 'Marina Square Basement',
      driveTime: '10 min drive',
      pricePerHour: r'$4.00/hr',
      spotsLeft: 85,
      spotsTotal: 500,
      rank: 4,
      walkTime: '7 min walk',
      confidenceLevel: 'High',
      confidenceText: 'High confidence',
    ),
    _CarparkModel(
      name: 'Ngee Ann City Tower B',
      driveTime: '14 min drive',
      pricePerHour: r'$5.50/hr',
      spotsLeft: 5,
      spotsTotal: 280,
      rank: 5,
      walkTime: '4 min walk',
      confidenceLevel: 'Low',
      confidenceText: 'Low confidence',
    ),
  ];

  @override
  void initState() {
    super.initState();
    _livePulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _livePulseController.dispose();
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            AppSpacing.page,
            20,
            AppSpacing.page,
            24,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AppPageHeader(
                title: 'Find parking',
                subtitle: 'A calmer way to reach your destination.',
              ),
              const SizedBox(height: 22),
              _buildSearchField(),
              const SizedBox(height: 14),
              _buildFilterRow(),
              const SizedBox(height: 28),
              _buildRecommendationsHeader(),
              const SizedBox(height: 16),
              if (_isMapView)
                _buildMapViewPlaceholder()
              else
                ..._carparks.map(
                  (cp) => Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: _buildCarparkCard(cp),
                  ),
                ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _buildBottomNavBar(),
    );
  }

  Widget _buildSearchField() {
    return Container(
      decoration: BoxDecoration(
        color: context.appColors.surface,
        borderRadius: BorderRadius.circular(AppRadii.control),
        border: Border.all(color: context.appColors.line),
        boxShadow: [
          BoxShadow(
            color: context.appColors.ink.withValues(alpha: 0.035),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: TextField(
        controller: _searchController,
        textInputAction: TextInputAction.search,
        style: Theme.of(context).textTheme.bodyLarge,
        decoration: InputDecoration(
          hintText: 'Where are you going?',
          prefixIcon: Icon(
            Icons.search_rounded,
            color: context.appColors.primary,
            size: 22,
          ),
          suffixIcon: IconButton(
            tooltip: 'Clear destination',
            icon: Icon(
              Icons.cancel_outlined,
              color: context.appColors.tertiaryText,
              size: 20,
            ),
            onPressed: () => setState(_searchController.clear),
          ),
          filled: false,
          border: InputBorder.none,
          enabledBorder: InputBorder.none,
          focusedBorder: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(vertical: 16),
        ),
      ),
    );
  }

  Widget _buildFilterRow() {
    return LayoutBuilder(
      builder: (context, constraints) {
        final width = (constraints.maxWidth - 8) / 2;
        return Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            SizedBox(
              width: width,
              child: _buildFilterPill(
                icon: Icons.schedule_rounded,
                label: _stayDuration,
                onTap: _showStayDurationPicker,
              ),
            ),
            SizedBox(
              width: width,
              child: _buildFilterPill(
                icon: Icons.near_me_outlined,
                label: _eta,
                onTap: _showEtaPicker,
              ),
            ),
            SizedBox(
              width: width,
              child: _buildFilterPill(
                icon: Icons.swap_vert_rounded,
                label: _sortBy,
                onTap: _showSortByPicker,
              ),
            ),
            SizedBox(
              width: width,
              child: _buildFilterPill(
                icon: Icons.tune_rounded,
                label: _filterFeature,
                onTap: _showFeatureFilterPicker,
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildFilterPill({
    required IconData icon,
    required String label,
    required VoidCallback onTap,
  }) {
    return Material(
      color: context.appColors.surface,
      borderRadius: BorderRadius.circular(AppRadii.control),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppRadii.control),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppRadii.control),
            border: Border.all(color: context.appColors.line),
          ),
          child: Row(
            children: [
              Icon(icon, color: context.appColors.primary, size: 17),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  label,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                    color: context.appColors.inkStrong,
                  ),
                ),
              ),
              Icon(
                Icons.keyboard_arrow_down_rounded,
                color: context.appColors.tertiaryText,
                size: 18,
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showStayDurationPicker() {
    _showOptionsPickerModal(
      title: 'Stay duration',
      currentSelection: _stayDuration,
      options: const [
        '30 Mins stay',
        '1 Hour stay',
        '2 Hours stay',
        '3 Hours stay',
        '4 Hours stay',
        'Half Day stay',
        'Full Day stay',
      ],
      onSelected: (value) => setState(() => _stayDuration = value),
    );
  }

  void _showEtaPicker() {
    _showOptionsPickerModal(
      title: 'Estimated arrival',
      currentSelection: _eta,
      options: const [
        'Arriving Now',
        'ETA: In 15 Mins',
        'ETA: In 30 Mins',
        'ETA: 10:15 AM',
        'ETA: 11:30 AM',
        'ETA: 2:00 PM',
        'ETA: 5:30 PM',
      ],
      onSelected: (value) => setState(() => _eta = value),
    );
  }

  void _showSortByPicker() {
    _showOptionsPickerModal(
      title: 'Sort recommendations by',
      currentSelection: _sortBy,
      options: const [
        'Sort: Best Match',
        'Sort: Lowest Price',
        'Sort: Shortest Walk',
        'Sort: Nearest Drive',
        'Sort: High Confidence',
      ],
      onSelected: (value) => setState(() => _sortBy = value),
    );
  }

  void _showFeatureFilterPicker() {
    _showOptionsPickerModal(
      title: 'Filter carpark features',
      currentSelection: _filterFeature,
      options: const [
        'Filter: All Carparks',
        'Filter: EV Charging',
        'Filter: Covered Only',
        'Filter: Height >= 1.9m',
        'Filter: Season Parking',
      ],
      onSelected: (value) => setState(() => _filterFeature = value),
    );
  }

  void _showOptionsPickerModal({
    required String title,
    required String currentSelection,
    required List<String> options,
    required ValueChanged<String> onSelected,
  }) {
    showModalBottomSheet(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (ctx) {
        return ConstrainedBox(
          constraints: BoxConstraints(
            maxHeight: MediaQuery.of(ctx).size.height * 0.78,
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: Theme.of(context).textTheme.titleLarge,
                      ),
                    ),
                    IconButton(
                      tooltip: 'Close',
                      icon: const Icon(Icons.close_rounded),
                      onPressed: () => Navigator.pop(ctx),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: options.length,
                    separatorBuilder:
                        (context, index) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final option = options[index];
                      final isSelected = option == currentSelection;
                      return Material(
                        color:
                            isSelected
                                ? context.appColors.infoSoft
                                : context.appColors.surfaceMuted,
                        borderRadius: BorderRadius.circular(AppRadii.control),
                        child: InkWell(
                          borderRadius: BorderRadius.circular(AppRadii.control),
                          onTap: () {
                            onSelected(option);
                            Navigator.pop(ctx);
                          },
                          child: Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 16,
                              vertical: 14,
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    option,
                                    style: Theme.of(
                                      context,
                                    ).textTheme.bodyLarge?.copyWith(
                                      color:
                                          isSelected
                                              ? context.appColors.primaryDark
                                              : context.appColors.inkStrong,
                                      fontWeight:
                                          isSelected
                                              ? FontWeight.w700
                                              : FontWeight.w500,
                                    ),
                                  ),
                                ),
                                if (isSelected)
                                  Icon(
                                    Icons.check_circle_rounded,
                                    color: context.appColors.primary,
                                    size: 20,
                                  ),
                              ],
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildRecommendationsHeader() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              child: Text(
                'Top recommendations',
                style: Theme.of(context).textTheme.titleLarge,
              ),
            ),
            _buildViewToggle(),
          ],
        ),
        const SizedBox(height: 9),
        Row(
          children: [
            FadeTransition(
              opacity: Tween<double>(begin: 0.35, end: 1).animate(
                CurvedAnimation(
                  parent: _livePulseController,
                  curve: Curves.easeInOut,
                ),
              ),
              child: Icon(
                Icons.circle,
                color: context.appColors.success,
                size: 9,
              ),
            ),
            const SizedBox(width: 7),
            Text(
              'Live traffic',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: context.appColors.success,
                fontWeight: FontWeight.w700,
              ),
            ),
            const SizedBox(width: 8),
            Icon(
              Icons.update_rounded,
              color: context.appColors.tertiaryText,
              size: 14,
            ),
            const SizedBox(width: 4),
            Text(
              'Updated 45s ago',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildViewToggle() {
    return Container(
      padding: const EdgeInsets.all(3),
      decoration: BoxDecoration(
        color: context.appColors.surfaceMuted,
        borderRadius: BorderRadius.circular(11),
        border: Border.all(color: context.appColors.line),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildSegmentedOption(
            icon: Icons.format_list_bulleted_rounded,
            label: 'List',
            isSelected: !_isMapView,
            onTap: () => setState(() => _isMapView = false),
          ),
          _buildSegmentedOption(
            icon: Icons.map_outlined,
            label: 'Map',
            isSelected: _isMapView,
            onTap: () => setState(() => _isMapView = true),
          ),
        ],
      ),
    );
  }

  Widget _buildSegmentedOption({
    required IconData icon,
    required String label,
    required bool isSelected,
    required VoidCallback onTap,
  }) {
    return Material(
      color: isSelected ? context.appColors.surface : Colors.transparent,
      borderRadius: BorderRadius.circular(8),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 7),
          child: Row(
            children: [
              Icon(
                icon,
                size: 14,
                color:
                    isSelected
                        ? context.appColors.primary
                        : context.appColors.secondaryText,
              ),
              const SizedBox(width: 5),
              Text(
                label,
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color:
                      isSelected
                          ? context.appColors.primaryDark
                          : context.appColors.secondaryText,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCarparkCard(_CarparkModel cp) {
    final availabilityRatio = cp.spotsLeft / cp.spotsTotal;
    final availabilityColor =
        availabilityRatio < 0.08
            ? context.appColors.warning
            : context.appColors.success;
    final confidenceColor =
        cp.confidenceLevel == 'High'
            ? context.appColors.success
            : cp.confidenceLevel == 'Medium'
            ? context.appColors.warning
            : context.appColors.danger;

    return AppSurface(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 29,
                height: 29,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  color: context.appColors.infoSoft,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  cp.rank.toString(),
                  style: Theme.of(context).textTheme.labelLarge?.copyWith(
                    color: context.appColors.primaryDark,
                  ),
                ),
              ),
              const SizedBox(width: 11),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      cp.name,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 5),
                    Wrap(
                      spacing: 4,
                      runSpacing: 4,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Icon(
                          Icons.directions_car_filled_outlined,
                          color: context.appColors.secondaryText,
                          size: 15,
                        ),
                        Text(
                          cp.driveTime,
                          style: Theme.of(context).textTheme.bodySmall,
                        ),
                        Text(
                          '\u2022',
                          style: TextStyle(
                            color: context.appColors.tertiaryText,
                          ),
                        ),
                        Text(
                          cp.pricePerHour,
                          style: Theme.of(
                            context,
                          ).textTheme.bodySmall?.copyWith(
                            color: context.appColors.success,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10),
              AppStatusPill(
                label: '${cp.spotsLeft} left',
                color: availabilityColor,
                backgroundColor: availabilityColor.withValues(alpha: 0.1),
                icon: Icons.local_parking_rounded,
              ),
            ],
          ),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: availabilityRatio.clamp(0.02, 1.0).toDouble(),
              minHeight: 5,
              backgroundColor: context.appColors.surfaceSubtle,
              valueColor: AlwaysStoppedAnimation<Color>(availabilityColor),
            ),
          ),
          const SizedBox(height: 11),
          Row(
            children: [
              Icon(
                Icons.directions_walk_outlined,
                color: context.appColors.secondaryText,
                size: 16,
              ),
              const SizedBox(width: 5),
              Text(cp.walkTime, style: Theme.of(context).textTheme.bodySmall),
              const Spacer(),
              AppStatusPill(
                label: cp.confidenceText,
                color: confidenceColor,
                icon: Icons.insights_outlined,
              ),
            ],
          ),
          const SizedBox(height: 9),
          Text(
            'Updated 45s ago',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: context.appColors.tertiaryText,
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 15),
          Row(
            children: [
              Expanded(
                flex: 5,
                child: SizedBox(
                  height: 46,
                  child: ElevatedButton.icon(
                    onPressed: () => _onParkHere(cp),
                    icon: const Icon(Icons.local_parking_rounded, size: 18),
                    label: const Text('Park Here'),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 4,
                child: SizedBox(
                  height: 46,
                  child: OutlinedButton.icon(
                    onPressed:
                        () => showAppSnackBar(
                          context,
                          'Directions to ${cp.name} are ready.',
                          icon: Icons.navigation_outlined,
                        ),
                    icon: const Icon(Icons.navigation_outlined, size: 17),
                    label: const Text('Go To'),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildMapViewPlaceholder() {
    return SizedBox(
      height: 500,
      child: AppSurface(
        padding: EdgeInsets.zero,
        borderRadius: BorderRadius.circular(AppRadii.card),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(AppRadii.card),
          child: Stack(
            children: [
              Positioned.fill(
                child: CustomPaint(painter: _MockMapPainter(context.appColors)),
              ),
              Positioned(
                top: 24,
                left: 18,
                child: _buildMapPin(
                  'Orchard Central',
                  r'$4.50/hr',
                  '48 left',
                  context.appColors.primary,
                ),
              ),
              Positioned(
                top: 125,
                right: 15,
                child: _buildMapPin(
                  'Suntec Plaza',
                  r'$5.00/hr',
                  '12 left',
                  context.appColors.warning,
                ),
              ),
              Positioned(
                bottom: 92,
                left: 16,
                child: _buildMapPin(
                  'Somerset Underground',
                  r'$3.80/hr',
                  '142 left',
                  context.appColors.success,
                ),
              ),
              Positioned(
                bottom: 155,
                right: 20,
                child: _buildMapPin(
                  'Marina Square',
                  r'$4.00/hr',
                  '85 left',
                  context.appColors.primary,
                ),
              ),
              Positioned(
                top: 230,
                left: 68,
                child: _buildMapPin(
                  'Ngee Ann City',
                  r'$5.50/hr',
                  '5 left',
                  context.appColors.danger,
                ),
              ),
              Positioned(
                top: 14,
                right: 14,
                child: AppStatusPill(
                  label: 'Updated 45s ago',
                  color: context.appColors.inkStrong,
                  backgroundColor: context.appColors.surface.withValues(
                    alpha: 0.92,
                  ),
                  icon: Icons.update_rounded,
                ),
              ),
              Positioned(
                bottom: 16,
                left: 16,
                child: AppStatusPill(
                  label: 'Approximate map view',
                  color: context.appColors.secondaryText,
                  backgroundColor: context.appColors.surface,
                  icon: Icons.map_outlined,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMapPin(
    String title,
    String price,
    String info,
    Color accentColor,
  ) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
      decoration: BoxDecoration(
        color: context.appColors.surface.withValues(alpha: 0.96),
        borderRadius: BorderRadius.circular(13),
        border: Border.all(color: accentColor.withValues(alpha: 0.5)),
        boxShadow: [
          BoxShadow(
            color: context.appColors.ink.withValues(alpha: 0.12),
            blurRadius: 12,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.location_on_rounded, color: accentColor, size: 19),
          const SizedBox(width: 6),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                title,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                  color: context.appColors.inkStrong,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                '$price • $info',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: context.appColors.secondaryText,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _onParkHere(_CarparkModel cp) {
    if (ParkingSessionManager.instance.hasActiveSession) {
      showAppSnackBar(
        context,
        'A parking session is already ongoing.',
        backgroundColor: context.appColors.danger,
        icon: Icons.warning_amber_rounded,
      );
      return;
    }

    ParkingSessionManager.instance.startSession(
      carparkName: cp.name,
      location: 'Zone A, Lot 145',
      hourlyRate: _parsePricePerHour(cp.pricePerHour),
    );
    Navigator.pushReplacement(
      context,
      PageRouteBuilder(
        pageBuilder:
            (context, animation1, animation2) =>
                const ParkingSessionTrackerScreen(),
        transitionDuration: Duration.zero,
        reverseTransitionDuration: Duration.zero,
      ),
    );
  }

  double _parsePricePerHour(String priceStr) {
    final clean = priceStr.replaceAll(RegExp(r'[^0-9.]'), '');
    return double.tryParse(clean) ?? 0.0;
  }

  void _onNavTap(int index) {
    if (index == _selectedNavIndex) return;
    final Widget destination;
    switch (index) {
      case 1:
        destination = const ParkingSessionTrackerScreen();
        break;
      case 2:
        destination = const PreferencesScreen();
        break;
      case 3:
        destination = const AdminPanelScreen();
        break;
      default:
        return;
    }
    Navigator.pushReplacement(
      context,
      PageRouteBuilder(
        pageBuilder: (context, animation1, animation2) => destination,
        transitionDuration: Duration.zero,
        reverseTransitionDuration: Duration.zero,
      ),
    );
  }

  Widget _buildBottomNavBar() {
    return ParkChoiceBottomNav(
      selectedIndex: _selectedNavIndex,
      onDestinationSelected: _onNavTap,
    );
  }
}

class _MockMapPainter extends CustomPainter {
  const _MockMapPainter(this.colors);

  final AppColors colors;

  @override
  void paint(Canvas canvas, Size size) {
    final background = Paint()..color = colors.mapBackground;
    canvas.drawRect(Offset.zero & size, background);

    final water = Paint()..color = colors.mapWater;
    final waterPath =
        Path()
          ..moveTo(size.width * 0.74, 0)
          ..quadraticBezierTo(
            size.width * 0.58,
            size.height * 0.2,
            size.width * 0.82,
            size.height * 0.39,
          )
          ..quadraticBezierTo(
            size.width * 0.96,
            size.height * 0.54,
            size.width * 0.78,
            size.height,
          )
          ..lineTo(size.width, size.height)
          ..lineTo(size.width, 0)
          ..close();
    canvas.drawPath(waterPath, water);

    final minorRoad =
        Paint()
          ..color = colors.mapRoad.withValues(alpha: 0.92)
          ..strokeWidth = 10
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round;
    final majorRoad =
        Paint()
          ..color = colors.mapRoadEdge
          ..strokeWidth = 17
          ..style = PaintingStyle.stroke
          ..strokeCap = StrokeCap.round;

    final roads = [
      Path()
        ..moveTo(-20, size.height * 0.2)
        ..cubicTo(
          size.width * 0.3,
          size.height * 0.28,
          size.width * 0.55,
          size.height * 0.08,
          size.width + 20,
          size.height * 0.16,
        ),
      Path()
        ..moveTo(-10, size.height * 0.73)
        ..cubicTo(
          size.width * 0.27,
          size.height * 0.6,
          size.width * 0.56,
          size.height * 0.8,
          size.width + 10,
          size.height * 0.58,
        ),
      Path()
        ..moveTo(size.width * 0.18, -10)
        ..cubicTo(
          size.width * 0.34,
          size.height * 0.3,
          size.width * 0.15,
          size.height * 0.7,
          size.width * 0.28,
          size.height + 10,
        ),
      Path()
        ..moveTo(size.width * 0.57, -10)
        ..cubicTo(
          size.width * 0.44,
          size.height * 0.28,
          size.width * 0.72,
          size.height * 0.61,
          size.width * 0.54,
          size.height + 10,
        ),
    ];

    for (final road in roads) {
      canvas.drawPath(road, majorRoad);
      canvas.drawPath(road, minorRoad);
    }

    final blockPaint = Paint()..color = colors.mapBlock;
    for (var row = 0; row < 4; row++) {
      for (var column = 0; column < 3; column++) {
        final rect = Rect.fromLTWH(
          22 + column * size.width * 0.22,
          52 + row * size.height * 0.16,
          size.width * 0.13,
          size.height * 0.08,
        );
        canvas.drawRRect(
          RRect.fromRectAndRadius(rect, const Radius.circular(4)),
          blockPaint,
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _MockMapPainter oldDelegate) {
    return oldDelegate.colors != colors;
  }
}
