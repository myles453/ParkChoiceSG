import 'package:flutter/material.dart';

import '../constants.dart';
import '../services/app_theme_controller.dart';
import '../widgets/app_ui.dart';
import '../widgets/bottom_nav_bar.dart';
import 'admin_panel_screen.dart';
import 'carpark_search_screen.dart';
import 'parking_session_tracker_screen.dart';

class PreferencesScreen extends StatefulWidget {
  const PreferencesScreen({super.key});

  @override
  State<PreferencesScreen> createState() => _PreferencesScreenState();
}

enum VehicleType { car, suvVan, lorry }

class _SavedDestinationModel {
  final String label;
  final String address;
  final IconData icon;
  final bool isCustom;

  const _SavedDestinationModel({
    required this.label,
    required this.address,
    required this.icon,
    this.isCustom = false,
  });
}

class _PreferencesScreenState extends State<PreferencesScreen> {
  static const int _selectedNavIndex = 2;

  VehicleType _selectedVehicle = VehicleType.car;
  double _maxWalkingDistance = 400;

  final List<String> _rankingCriteria = [
    'Cost',
    'Walking Distance',
    'Driving Time',
    'Availability Confidence',
  ];

  final Map<VehicleType, double> _clearanceByVehicle = const {
    VehicleType.car: 1.9,
    VehicleType.suvVan: 2.1,
    VehicleType.lorry: 3.5,
  };

  final List<_SavedDestinationModel> _savedDestinations = [
    const _SavedDestinationModel(
      label: 'Home',
      address: '82 Craig Road, Block B, Singapore',
      icon: Icons.home_outlined,
    ),
    const _SavedDestinationModel(
      label: 'Work',
      address: 'One Raffles Quay, Level 44, Singapore',
      icon: Icons.work_outline,
    ),
  ];

  String _vehicleLabel(VehicleType type) {
    switch (type) {
      case VehicleType.car:
        return 'Car';
      case VehicleType.suvVan:
        return 'SUV / Van';
      case VehicleType.lorry:
        return 'Lorry';
    }
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
            30,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const AppPageHeader(
                title: 'Preferences',
                subtitle: 'Make every recommendation feel more like yours.',
              ),
              const SizedBox(height: AppSpacing.section),
              const AppSectionTitle(
                title: 'Appearance',
                subtitle: 'Choose how ParkChoiceSG looks on this device.',
              ),
              const SizedBox(height: 13),
              _buildAppearanceCard(),
              const SizedBox(height: AppSpacing.section),
              const AppSectionTitle(
                title: 'Saved destinations',
                subtitle: 'Keep your regular places close at hand.',
              ),
              const SizedBox(height: 13),
              ..._savedDestinations.map(
                (destination) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _buildDestinationTile(destination),
                ),
              ),
              _buildAddLocationButton(),
              const SizedBox(height: AppSpacing.section),
              const AppSectionTitle(
                title: 'Vehicle profile',
                subtitle: 'We will avoid carparks your vehicle cannot enter.',
              ),
              const SizedBox(height: 13),
              _buildVehicleClearanceCard(),
              const SizedBox(height: AppSpacing.section),
              const AppSectionTitle(
                title: 'Walking tolerance',
                subtitle: 'Set the furthest walk you are comfortable with.',
              ),
              const SizedBox(height: 13),
              _buildWalkingDistanceCard(),
              const SizedBox(height: AppSpacing.section),
              const AppSectionTitle(
                title: 'Ranking priority',
                subtitle: 'Drag items to set recommendation priorities.',
              ),
              const SizedBox(height: 13),
              _buildRankingPriorityCard(),
              const SizedBox(height: 30),
              _buildEraseDataCard(),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _buildBottomNavBar(),
    );
  }

  Widget _buildAppearanceCard() {
    final selectedMode = AppThemeController.instance.themeMode;
    final description = switch (selectedMode) {
      ThemeMode.system => 'ParkChoiceSG follows your device appearance.',
      ThemeMode.light => 'Light appearance stays on until you change it.',
      ThemeMode.dark => 'Dark appearance stays on until you change it.',
    };

    return AppSurface(
      padding: const EdgeInsets.all(14),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: context.appColors.surfaceMuted,
              borderRadius: BorderRadius.circular(AppRadii.control),
            ),
            child: Row(
              children: [
                _buildAppearanceOption(
                  mode: ThemeMode.system,
                  icon: Icons.brightness_auto_outlined,
                  label: 'System',
                  selectedMode: selectedMode,
                ),
                _buildAppearanceOption(
                  mode: ThemeMode.light,
                  icon: Icons.light_mode_outlined,
                  label: 'Light',
                  selectedMode: selectedMode,
                ),
                _buildAppearanceOption(
                  mode: ThemeMode.dark,
                  icon: Icons.dark_mode_outlined,
                  label: 'Dark',
                  selectedMode: selectedMode,
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Icon(
                Icons.info_outline_rounded,
                size: 16,
                color: context.appColors.tertiaryText,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  description,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildAppearanceOption({
    required ThemeMode mode,
    required IconData icon,
    required String label,
    required ThemeMode selectedMode,
  }) {
    final isSelected = mode == selectedMode;
    return Expanded(
      child: Semantics(
        button: true,
        selected: isSelected,
        label: '$label appearance',
        child: Material(
          color: Colors.transparent,
          child: InkWell(
            key: ValueKey('appearance-${mode.name}'),
            onTap: () => AppThemeController.instance.setThemeMode(mode),
            borderRadius: BorderRadius.circular(AppRadii.small),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              curve: Curves.easeOut,
              padding: const EdgeInsets.symmetric(vertical: 11, horizontal: 5),
              decoration: BoxDecoration(
                color:
                    isSelected ? context.appColors.surface : Colors.transparent,
                borderRadius: BorderRadius.circular(AppRadii.small),
                border: Border.all(
                  color:
                      isSelected ? context.appColors.line : Colors.transparent,
                ),
                boxShadow:
                    isSelected
                        ? [
                          BoxShadow(
                            color: Colors.black.withValues(
                              alpha:
                                  Theme.of(context).brightness ==
                                          Brightness.dark
                                      ? 0.24
                                      : 0.07,
                            ),
                            blurRadius: 8,
                            offset: const Offset(0, 2),
                          ),
                        ]
                        : null,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    icon,
                    size: 19,
                    color:
                        isSelected
                            ? context.appColors.primary
                            : context.appColors.secondaryText,
                  ),
                  const SizedBox(height: 5),
                  Text(
                    label,
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                      color:
                          isSelected
                              ? context.appColors.primaryDark
                              : context.appColors.secondaryText,
                      fontWeight:
                          isSelected ? FontWeight.w800 : FontWeight.w600,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildDestinationTile(_SavedDestinationModel destination) {
    return AppSurface(
      padding: const EdgeInsets.fromLTRB(14, 13, 8, 13),
      borderRadius: BorderRadius.circular(AppRadii.control),
      child: Row(
        children: [
          AppIconTile(
            icon: destination.icon,
            color: context.appColors.primary,
            backgroundColor: context.appColors.infoSoft,
            size: 42,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  destination.label,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 3),
                Text(
                  destination.address,
                  style: Theme.of(context).textTheme.bodySmall,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          IconButton(
            tooltip: destination.isCustom ? 'Delete location' : 'Edit location',
            icon: Icon(
              destination.isCustom
                  ? Icons.delete_outline_rounded
                  : Icons.edit_outlined,
              color:
                  destination.isCustom
                      ? context.appColors.danger
                      : context.appColors.secondaryText,
              size: 20,
            ),
            onPressed:
                destination.isCustom
                    ? () {
                      setState(() {
                        _savedDestinations.remove(destination);
                      });
                    }
                    : null,
          ),
        ],
      ),
    );
  }

  Widget _buildAddLocationButton() {
    return SizedBox(
      width: double.infinity,
      height: 48,
      child: OutlinedButton.icon(
        onPressed: _showAddLocationModal,
        icon: const Icon(Icons.add_location_alt_outlined, size: 19),
        label: const Text('Add new location'),
      ),
    );
  }

  void _showAddLocationModal() {
    final labelController = TextEditingController();
    final addressController = TextEditingController();

    showModalBottomSheet(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (ctx) {
        return Padding(
          padding: EdgeInsets.fromLTRB(
            20,
            4,
            20,
            MediaQuery.of(ctx).viewInsets.bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildSheetHeader(ctx, 'Add custom location'),
              const SizedBox(height: 5),
              Text(
                'Save a place you visit often for faster searches.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 18),
              AppTextField(
                controller: labelController,
                label: 'Location label',
                hint: 'e.g. Gym, Parents',
                prefixIcon: Icons.bookmark_outline_rounded,
                textInputAction: TextInputAction.next,
              ),
              const SizedBox(height: 14),
              AppTextField(
                controller: addressController,
                label: 'Address or landmark',
                hint: 'Enter an address',
                prefixIcon: Icons.place_outlined,
                textInputAction: TextInputAction.done,
              ),
              const SizedBox(height: 22),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: ElevatedButton(
                  onPressed: () {
                    final label = labelController.text.trim();
                    final address = addressController.text.trim();
                    if (label.isNotEmpty && address.isNotEmpty) {
                      setState(() {
                        _savedDestinations.add(
                          _SavedDestinationModel(
                            label: label,
                            address: address,
                            icon: Icons.place_outlined,
                            isCustom: true,
                          ),
                        );
                      });
                    }
                    Navigator.pop(ctx);
                  },
                  child: const Text('Save location'),
                ),
              ),
            ],
          ),
        );
      },
    ).whenComplete(() {
      labelController.dispose();
      addressController.dispose();
    });
  }

  Widget _buildSheetHeader(BuildContext sheetContext, String title) {
    return Row(
      children: [
        Expanded(
          child: Text(title, style: Theme.of(context).textTheme.titleLarge),
        ),
        IconButton(
          tooltip: 'Close',
          icon: const Icon(Icons.close_rounded),
          onPressed: () => Navigator.pop(sheetContext),
        ),
      ],
    );
  }

  Widget _buildVehicleClearanceCard() {
    final clearance = _clearanceByVehicle[_selectedVehicle]!;

    return AppSurface(
      padding: const EdgeInsets.all(15),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'ACTIVE VEHICLE TYPE',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: context.appColors.secondaryText,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(height: 10),
          _buildVehicleSegmentedControl(),
          const SizedBox(height: 14),
          _buildClearanceNotice(clearance),
        ],
      ),
    );
  }

  Widget _buildVehicleSegmentedControl() {
    return Container(
      padding: const EdgeInsets.all(4),
      decoration: BoxDecoration(
        color: context.appColors.surfaceMuted,
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      child: Row(
        children:
            VehicleType.values.map((type) {
              final isSelected = type == _selectedVehicle;
              return Expanded(
                child: Material(
                  color:
                      isSelected
                          ? context.appColors.surface
                          : Colors.transparent,
                  borderRadius: BorderRadius.circular(AppRadii.small),
                  child: InkWell(
                    onTap: () => setState(() => _selectedVehicle = type),
                    borderRadius: BorderRadius.circular(AppRadii.small),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 180),
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      alignment: Alignment.center,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(AppRadii.small),
                        boxShadow:
                            isSelected
                                ? [
                                  BoxShadow(
                                    color: context.appColors.ink.withValues(
                                      alpha: 0.07,
                                    ),
                                    blurRadius: 5,
                                    offset: const Offset(0, 2),
                                  ),
                                ]
                                : null,
                      ),
                      child: Text(
                        _vehicleLabel(type),
                        style: Theme.of(
                          context,
                        ).textTheme.labelMedium?.copyWith(
                          color:
                              isSelected
                                  ? context.appColors.primaryDark
                                  : context.appColors.secondaryText,
                          fontWeight:
                              isSelected ? FontWeight.w800 : FontWeight.w600,
                        ),
                      ),
                    ),
                  ),
                ),
              );
            }).toList(),
      ),
    );
  }

  Widget _buildClearanceNotice(double clearance) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: context.appColors.infoSoft,
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AppIconTile(
            icon: Icons.height_rounded,
            color: context.appColors.primary,
            backgroundColor: context.appColors.surface,
            size: 34,
          ),
          const SizedBox(width: 11),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Assumed clearance: ${clearance.toStringAsFixed(1)}m',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(
                    color: context.appColors.inkStrong,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  'Carparks below this height will be excluded automatically.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWalkingDistanceCard() {
    return AppSurface(
      padding: const EdgeInsets.fromLTRB(15, 15, 15, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                'MAX WALKING DISTANCE',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: context.appColors.secondaryText,
                  letterSpacing: 0.8,
                ),
              ),
              AppStatusPill(
                label: '${_maxWalkingDistance.toInt()} m',
                color: context.appColors.primaryDark,
                backgroundColor: context.appColors.infoSoft,
              ),
            ],
          ),
          Slider(
            value: _maxWalkingDistance,
            min: 100,
            max: 1000,
            divisions: 18,
            label: '${_maxWalkingDistance.toInt()}m',
            onChanged: (value) {
              setState(() {
                _maxWalkingDistance = value;
              });
            },
          ),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                '100m  Strict',
                style: TextStyle(
                  color: context.appColors.tertiaryText,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
              Text(
                '1000m  Flexible',
                style: TextStyle(
                  color: context.appColors.tertiaryText,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 9),
          Text(
            'Recommendations further than this distance from your destination will be filtered out.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Widget _buildRankingPriorityCard() {
    return AppSurface(
      padding: const EdgeInsets.all(12),
      child: ReorderableListView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        itemCount: _rankingCriteria.length,
        onReorderItem: (oldIndex, newIndex) {
          setState(() {
            final item = _rankingCriteria.removeAt(oldIndex);
            _rankingCriteria.insert(newIndex, item);
          });
        },
        itemBuilder: (context, index) {
          final item = _rankingCriteria[index];
          return Container(
            key: ValueKey(item),
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
            decoration: BoxDecoration(
              color: context.appColors.surfaceMuted,
              borderRadius: BorderRadius.circular(AppRadii.control),
            ),
            child: Row(
              children: [
                Container(
                  width: 30,
                  height: 30,
                  alignment: Alignment.center,
                  decoration: BoxDecoration(
                    color: context.appColors.infoSoft,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Text(
                    (index + 1).toString(),
                    style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: context.appColors.primaryDark,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    item,
                    style: Theme.of(
                      context,
                    ).textTheme.titleMedium?.copyWith(fontSize: 14),
                  ),
                ),
                Icon(
                  Icons.drag_indicator_rounded,
                  color: context.appColors.tertiaryText,
                  size: 21,
                ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildEraseDataCard() {
    return AppSurface(
      color: context.appColors.dangerSoft,
      border: Border.all(
        color: context.appColors.danger.withValues(alpha: 0.18),
      ),
      padding: const EdgeInsets.all(15),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                Icons.shield_outlined,
                color: context.appColors.danger,
                size: 17,
              ),
              const SizedBox(width: 7),
              Text(
                'DATA MANAGEMENT',
                style: Theme.of(context).textTheme.labelSmall?.copyWith(
                  color: context.appColors.danger,
                  letterSpacing: 0.8,
                ),
              ),
            ],
          ),
          const SizedBox(height: 7),
          Text(
            'Delete locally stored preferences, search history, and saved locations.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            height: 46,
            child: OutlinedButton.icon(
              onPressed: _showEraseDataConfirmation,
              icon: const Icon(Icons.delete_forever_outlined, size: 18),
              label: const Text('Erase all local data'),
              style: OutlinedButton.styleFrom(
                foregroundColor: context.appColors.danger,
                side: BorderSide(
                  color: context.appColors.danger.withValues(alpha: 0.35),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _showEraseDataConfirmation() {
    showDialog(
      context: context,
      builder:
          (ctx) => AlertDialog(
            title: Row(
              children: [
                Icon(
                  Icons.warning_amber_rounded,
                  color: context.appColors.danger,
                  size: 24,
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    'Erase all local data?',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
              ],
            ),
            content: Text(
              'This will permanently delete your saved destinations, vehicle profile, walking tolerance settings, search history, and local preferences.',
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx);
                  setState(() {
                    _maxWalkingDistance = 400;
                    _selectedVehicle = VehicleType.car;
                  });
                  showAppSnackBar(
                    context,
                    'All local preferences and data have been erased.',
                    backgroundColor: context.appColors.danger,
                    icon: Icons.delete_sweep_outlined,
                  );
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: context.appColors.danger,
                ),
                child: const Text('Erase data'),
              ),
            ],
          ),
    );
  }

  void _onNavTap(int index) {
    if (index == _selectedNavIndex) return;
    final Widget destination;
    switch (index) {
      case 0:
        destination = const CarparkSearchScreen();
        break;
      case 1:
        destination = const ParkingSessionTrackerScreen();
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
