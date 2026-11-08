import 'package:flutter/material.dart';

import '../constants.dart';
import '../services/app_theme_controller.dart';
import '../widgets/app_ui.dart';
import '../widgets/bottom_nav_bar.dart';
import 'operator_login_screen.dart';
import 'carpark_search_screen.dart';
import 'parking_session_tracker_screen.dart';

/// Preference controls and in-memory saved destinations; appearance persists locally.
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
  bool _isNavigating = false;

  VehicleType _selectedVehicle = VehicleType.car;
  double _maxWalkingDistance = 400;

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
                title: 'Ranking mode',
                subtitle: 'Choose a mode for each search.',
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
                          isSelected ? FontWeight.w600 : FontWeight.w500,
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

  Future<void> _showAddLocationModal() async {
    if (!mounted ||
        _isNavigating ||
        ModalRoute.of(context)?.isCurrent != true) {
      return;
    }
    var label = '';
    var address = '';
    var isClosing = false;

    final shouldSave = await showModalBottomSheet<bool>(
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
          child: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildSheetHeader(
                  ctx,
                  'Add custom location',
                  onClose: () {
                    if (isClosing || ModalRoute.of(ctx)?.isCurrent != true) {
                      return;
                    }
                    isClosing = true;
                    FocusScope.of(ctx).unfocus();
                    Navigator.pop(ctx);
                  },
                ),
                const SizedBox(height: 5),
                Text(
                  'Save a place you visit often for faster searches.',
                  style: Theme.of(ctx).textTheme.bodyMedium,
                ),
                const SizedBox(height: 18),
                AppTextField(
                  label: 'Location label',
                  hint: 'e.g. Gym, Parents',
                  prefixIcon: Icons.bookmark_outline_rounded,
                  textInputAction: TextInputAction.next,
                  onChanged: (value) => label = value,
                ),
                const SizedBox(height: 14),
                AppTextField(
                  label: 'Address or landmark',
                  hint: 'Enter an address',
                  prefixIcon: Icons.place_outlined,
                  textInputAction: TextInputAction.done,
                  onChanged: (value) => address = value,
                ),
                const SizedBox(height: 22),
                SizedBox(
                  width: double.infinity,
                  height: 50,
                  child: ElevatedButton(
                    onPressed: () {
                      if (isClosing || ModalRoute.of(ctx)?.isCurrent != true) {
                        return;
                      }
                      isClosing = true;
                      FocusScope.of(ctx).unfocus();
                      final canSave =
                          label.trim().isNotEmpty && address.trim().isNotEmpty;
                      Navigator.pop(ctx, canSave);
                    },
                    child: const Text('Save location'),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );

    if (!mounted || shouldSave != true) return;
    setState(() {
      _savedDestinations.add(
        _SavedDestinationModel(
          label: label.trim(),
          address: address.trim(),
          icon: Icons.place_outlined,
          isCustom: true,
        ),
      );
    });
  }

  Widget _buildSheetHeader(
    BuildContext sheetContext,
    String title, {
    VoidCallback? onClose,
  }) {
    return Row(
      children: [
        Expanded(
          child: Text(
            title,
            style: Theme.of(sheetContext).textTheme.titleLarge,
          ),
        ),
        IconButton(
          tooltip: 'Close',
          icon: const Icon(Icons.close_rounded),
          onPressed:
              onClose ??
              () {
                FocusScope.of(sheetContext).unfocus();
                Navigator.pop(sheetContext);
              },
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
                                    color: Colors.black.withValues(alpha: 0.07),
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
                              isSelected ? FontWeight.w600 : FontWeight.w500,
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
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            spacing: 12,
            runSpacing: 8,
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
          Wrap(
            alignment: WrapAlignment.spaceBetween,
            spacing: 12,
            runSpacing: 8,
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
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('Best overall, Prioritise cheaper, or Prioritise closer.'),
          const SizedBox(height: 8),
          const Text(
            'Select your mode on the search screen before finding carparks. Closer means a shorter walk to your destination.',
          ),
          const SizedBox(height: 12),
          OutlinedButton(
            onPressed: () => _onNavTap(0),
            child: const Text('Choose on search screen'),
          ),
        ],
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
              Expanded(
                child: Text(
                  'DATA MANAGEMENT',
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: context.appColors.danger,
                    letterSpacing: 0.8,
                  ),
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

  Future<void> _showEraseDataConfirmation() async {
    if (!mounted ||
        _isNavigating ||
        ModalRoute.of(context)?.isCurrent != true) {
      return;
    }
    var isClosing = false;
    final shouldErase = await showDialog<bool>(
      context: context,
      builder:
          (ctx) => AlertDialog(
            title: Row(
              children: [
                Icon(
                  Icons.warning_amber_rounded,
                  color: ctx.appColors.danger,
                  size: 24,
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    'Erase all local data?',
                    style: Theme.of(ctx).textTheme.titleLarge,
                  ),
                ),
              ],
            ),
            content: Text(
              'This will permanently delete your saved destinations, vehicle profile, walking tolerance settings, search history, and local preferences.',
              style: Theme.of(ctx).textTheme.bodyMedium,
            ),
            actions: [
              TextButton(
                onPressed: () {
                  if (isClosing || ModalRoute.of(ctx)?.isCurrent != true) {
                    return;
                  }
                  isClosing = true;
                  Navigator.pop(ctx, false);
                },
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                onPressed: () {
                  if (isClosing || ModalRoute.of(ctx)?.isCurrent != true) {
                    return;
                  }
                  isClosing = true;
                  Navigator.pop(ctx, true);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: ctx.appColors.danger,
                ),
                child: const Text('Erase data'),
              ),
            ],
          ),
    );

    if (!mounted || shouldErase != true) return;
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
  }

  void _onNavTap(int index) {
    if (_isNavigating ||
        index == _selectedNavIndex ||
        ModalRoute.of(context)?.isCurrent != true) {
      return;
    }
    final Widget destination;
    switch (index) {
      case 0:
        destination = const CarparkSearchScreen();
        break;
      case 1:
        destination = const ParkingSessionTrackerScreen();
        break;
      case 3:
        destination = operatorEntryScreen();
        break;
      default:
        return;
    }
    _isNavigating = true;
    FocusManager.instance.primaryFocus?.unfocus();
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
