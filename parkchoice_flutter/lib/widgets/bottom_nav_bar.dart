import 'package:flutter/material.dart';

import '../constants.dart';

class ParkChoiceBottomNav extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onDestinationSelected;

  const ParkChoiceBottomNav({
    super.key,
    required this.selectedIndex,
    required this.onDestinationSelected,
  });

  @override
  Widget build(BuildContext context) {
    return NavigationBar(
      selectedIndex: selectedIndex,
      onDestinationSelected: onDestinationSelected,
      height: 76,
      backgroundColor: context.appColors.surface,
      elevation: 0,
      indicatorColor: context.appColors.infoSoft,
      labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.search_rounded),
          selectedIcon: Icon(Icons.search_rounded),
          label: 'Search',
        ),
        NavigationDestination(
          icon: Icon(Icons.timer_outlined),
          selectedIcon: Icon(Icons.timer_rounded),
          label: 'Tracker',
        ),
        NavigationDestination(
          icon: Icon(Icons.tune_rounded),
          selectedIcon: Icon(Icons.tune_rounded),
          label: 'Preferences',
        ),
        NavigationDestination(
          icon: Icon(Icons.admin_panel_settings_outlined),
          selectedIcon: Icon(Icons.admin_panel_settings_rounded),
          label: 'Admin',
        ),
      ],
    );
  }
}
