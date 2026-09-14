import 'dart:async';

import 'package:flutter/material.dart';

import '../constants.dart';
import '../services/parking_session_manager.dart';
import '../widgets/app_ui.dart';
import '../widgets/bottom_nav_bar.dart';
import 'admin_panel_screen.dart';
import 'carpark_search_screen.dart';
import 'preferences_screen.dart';

class ParkingSessionTrackerScreen extends StatefulWidget {
  const ParkingSessionTrackerScreen({super.key});

  @override
  State<ParkingSessionTrackerScreen> createState() =>
      _ParkingSessionTrackerScreenState();
}

class _RecentSessionModel {
  final String name;
  final String location;
  final String dateLabel;
  final String cost;
  final String duration;

  const _RecentSessionModel({
    required this.name,
    required this.location,
    required this.dateLabel,
    required this.cost,
    required this.duration,
  });
}

class _MonthlySessionGroup {
  final String monthYear;
  final String totalExpenditure;
  final List<_RecentSessionModel> sessions;

  const _MonthlySessionGroup({
    required this.monthYear,
    required this.totalExpenditure,
    required this.sessions,
  });
}

class _ParkingSessionTrackerScreenState
    extends State<ParkingSessionTrackerScreen>
    with SingleTickerProviderStateMixin {
  static const int _selectedNavIndex = 1;
  bool _isNavigating = false;
  Timer? _timer;
  late AnimationController _livePulseController;

  final List<_MonthlySessionGroup> _monthlyGroups = [
    _MonthlySessionGroup(
      monthYear: 'October 2026',
      totalExpenditure: r'$42.10',
      sessions: const [
        _RecentSessionModel(
          name: 'Suntec Plaza Level B2',
          location: 'Level B2, Lot 08',
          dateLabel: 'Yesterday, 2:15 PM',
          cost: r'$15.00',
          duration: '3h 0m',
        ),
        _RecentSessionModel(
          name: 'Orchard Central Terminal',
          location: 'Level 3, Lot B12',
          dateLabel: '14 Oct, 11:30 AM',
          cost: r'$9.00',
          duration: '2h 0m',
        ),
        _RecentSessionModel(
          name: 'Somerset Underground',
          location: 'Level 1, Lot A04',
          dateLabel: '11 Oct, 09:15 AM',
          cost: r'$5.70',
          duration: '1h 30m',
        ),
        _RecentSessionModel(
          name: 'National Museum Park',
          location: 'Level 2, Lot C09',
          dateLabel: '08 Oct, 03:00 PM',
          cost: r'$12.40',
          duration: '4h 10m',
        ),
      ],
    ),
    _MonthlySessionGroup(
      monthYear: 'September 2026',
      totalExpenditure: r'$28.50',
      sessions: const [
        _RecentSessionModel(
          name: 'Bugis Junction Level 1',
          location: 'Level 1, Lot 42',
          dateLabel: '28 Sep, 04:20 PM',
          cost: r'$14.50',
          duration: '3h 30m',
        ),
        _RecentSessionModel(
          name: 'Marina Bay Sands Lot B',
          location: 'Basement 2, Lot 105',
          dateLabel: '19 Sep, 01:10 PM',
          cost: r'$14.00',
          duration: '2h 45m',
        ),
      ],
    ),
  ];

  @override
  void initState() {
    super.initState();
    ParkingSessionManager.instance.addListener(_onSessionChanged);
    _livePulseController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    )..repeat(reverse: true);
    _startTimerIfNeeded();
  }

  void _startTimerIfNeeded() {
    _timer?.cancel();
    if (ParkingSessionManager.instance.hasActiveSession) {
      _timer = Timer.periodic(const Duration(seconds: 1), (_) {
        if (mounted) setState(() {});
      });
    }
  }

  void _onSessionChanged() {
    _startTimerIfNeeded();
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    ParkingSessionManager.instance.removeListener(_onSessionChanged);
    _livePulseController.dispose();
    _timer?.cancel();
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
                title: 'Active session',
                subtitle: 'Keep an eye on time, cost, and reminders.',
              ),
              const SizedBox(height: 22),
              _buildActiveSessionCard(),
              const SizedBox(height: AppSpacing.section),
              const AppSectionTitle(
                title: 'Session history',
                subtitle: 'A clear record of your recent parking.',
              ),
              const SizedBox(height: 4),
              ..._monthlyGroups.map(
                (group) => Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _buildMonthlyHeader(group),
                    ...group.sessions.map(
                      (session) => Padding(
                        padding: const EdgeInsets.only(bottom: 10),
                        child: _buildRecentSessionTile(session),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _buildBottomNavBar(),
    );
  }

  Widget _buildActiveSessionCard() {
    final session = ParkingSessionManager.instance.currentSession;
    if (session == null) return _buildNoActiveSessionCard();

    final durationString = _formatDuration(session.duration);
    final runningCostString = '\$${session.runningCost.toStringAsFixed(2)}';
    final rateString =
        '\$${(session.hourlyRate / 2).toStringAsFixed(2)} / 30 min';

    return AppSurface(
      padding: const EdgeInsets.all(18),
      border: Border.all(
        color: context.appColors.primary.withValues(alpha: 0.35),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppIconTile(
                icon: Icons.local_parking_rounded,
                color: context.appColors.primary,
                backgroundColor: context.appColors.infoSoft,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      session.carparkName,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 4),
                    Text(
                      session.location,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                ),
              ),
              FadeTransition(
                opacity: Tween<double>(begin: 0.35, end: 1).animate(
                  CurvedAnimation(
                    parent: _livePulseController,
                    curve: Curves.easeInOut,
                  ),
                ),
                child: AppStatusPill(
                  label: 'LIVE',
                  color: context.appColors.success,
                  icon: Icons.circle,
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(
                  child: AppMetric(
                    label: 'Parked duration',
                    value: durationString,
                    valueColor: context.appColors.ink,
                    icon: Icons.schedule_rounded,
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: AppMetric(
                    label: 'Running cost',
                    value: runningCostString,
                    subtitle: rateString,
                    valueColor: context.appColors.primaryDark,
                    icon: Icons.payments_outlined,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
            decoration: BoxDecoration(
              color: context.appColors.successSoft,
              borderRadius: BorderRadius.circular(AppRadii.control),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.notifications_active_outlined,
                  color: context.appColors.success,
                  size: 17,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Reminder alert is active for this session.',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      color: context.appColors.success,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 15),
          Row(
            children: [
              Expanded(
                flex: 3,
                child: SizedBox(
                  height: 47,
                  child: ElevatedButton.icon(
                    onPressed: _onEndSessionPrompt,
                    icon: const Icon(Icons.stop_rounded, size: 18),
                    label: const Text('End Session'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: context.appColors.warning,
                      foregroundColor: context.appColors.onBrand,
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                flex: 2,
                child: SizedBox(
                  height: 47,
                  child: OutlinedButton.icon(
                    onPressed: _showExtendSessionModal,
                    icon: const Icon(Icons.add_alarm_outlined, size: 17),
                    label: const Text('Extend'),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildNoActiveSessionCard() {
    return AppSurface(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 30),
      child: Center(
        child: Column(
          children: [
            AppIconTile(
              icon: Icons.local_parking_rounded,
              color: context.appColors.secondaryText,
              backgroundColor: context.appColors.surfaceMuted,
              size: 52,
            ),
            const SizedBox(height: 13),
            Text(
              'No active sessions',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 5),
            Text(
              'Start a parking session from Search.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _onEndSessionPrompt() async {
    final session = ParkingSessionManager.instance.currentSession;
    if (session == null) return;

    final durationString = _formatDuration(session.duration);
    final finalCostString = r'$' + session.runningCost.toStringAsFixed(2);

    final shouldEnd = await showDialog<bool>(
      context: context,
      builder:
          (ctx) => AlertDialog(
            title: Row(
              children: [
                Icon(
                  Icons.flag_outlined,
                  color: ctx.appColors.warning,
                  size: 24,
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    'End parking session?',
                    style: Theme.of(ctx).textTheme.titleLarge,
                  ),
                ),
              ],
            ),
            content: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'Your final charge will be calculated and this session will be added to your history.',
                  style: Theme.of(ctx).textTheme.bodyMedium,
                ),
                const SizedBox(height: 16),
                AppSurface(
                  color: ctx.appColors.surfaceMuted,
                  padding: const EdgeInsets.all(14),
                  borderRadius: BorderRadius.circular(AppRadii.control),
                  border: null,
                  child: Column(
                    children: [
                      _buildConfirmRow(
                        ctx,
                        'Carpark',
                        session.carparkName,
                        true,
                      ),
                      const SizedBox(height: 9),
                      _buildConfirmRow(ctx, 'Duration', durationString, false),
                      const SizedBox(height: 9),
                      _buildConfirmRow(
                        ctx,
                        'Computed total',
                        finalCostString,
                        true,
                        ctx.appColors.primaryDark,
                      ),
                    ],
                  ),
                ),
              ],
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('Cancel'),
              ),
              ElevatedButton(
                onPressed: () {
                  Navigator.pop(ctx, true);
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: ctx.appColors.warning,
                ),
                child: const Text('Confirm end'),
              ),
            ],
          ),
    );

    if (!mounted || shouldEnd != true) return;
    _confirmAndEndSession();
  }

  Widget _buildConfirmRow(
    BuildContext context,
    String label,
    String value,
    bool isHighlight, [
    Color? valueColor,
  ]) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: Theme.of(context).textTheme.bodySmall),
        const SizedBox(width: 12),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.end,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color:
                  valueColor ??
                  (isHighlight
                      ? context.appColors.inkStrong
                      : context.appColors.secondaryText),
              fontWeight: isHighlight ? FontWeight.w600 : FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }

  void _confirmAndEndSession() {
    final session = ParkingSessionManager.instance.currentSession;
    if (session != null) {
      final endedModel = _RecentSessionModel(
        name: session.carparkName,
        location: session.location,
        dateLabel: 'Just now',
        cost: r'$' + session.runningCost.toStringAsFixed(2),
        duration: _formatDuration(session.duration),
      );
      if (_monthlyGroups.isNotEmpty) {
        final currentGroup = _monthlyGroups[0];
        final updatedList = List<_RecentSessionModel>.from(
          currentGroup.sessions,
        )..insert(0, endedModel);
        _monthlyGroups[0] = _MonthlySessionGroup(
          monthYear: currentGroup.monthYear,
          totalExpenditure: currentGroup.totalExpenditure,
          sessions: updatedList,
        );
      }
    }
    ParkingSessionManager.instance.endSession();
    showAppSnackBar(
      context,
      'Parking session ended and saved to your history.',
      icon: Icons.check_circle_outline_rounded,
    );
  }

  Future<void> _showExtendSessionModal() async {
    String selectedInterval = '+30 min';
    var isClosing = false;
    final appliedInterval = await showModalBottomSheet<String>(
      context: context,
      useSafeArea: true,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return Padding(
              padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Extend session & reminder',
                          style: Theme.of(context).textTheme.titleLarge,
                        ),
                      ),
                      IconButton(
                        tooltip: 'Close',
                        icon: const Icon(Icons.close_rounded),
                        onPressed: () {
                          if (isClosing) return;
                          isClosing = true;
                          FocusScope.of(ctx).unfocus();
                          Navigator.pop(ctx);
                        },
                      ),
                    ],
                  ),
                  Text(
                    'Choose how much extra time you need.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 18),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children:
                        [
                          '+15 min',
                          '+30 min',
                          '+45 min',
                          '+1 hour',
                          '+2 hours',
                        ].map((interval) {
                          final isSelected = selectedInterval == interval;
                          return ChoiceChip(
                            label: Text(interval),
                            selected: isSelected,
                            onSelected: (selected) {
                              if (selected) {
                                setModalState(() {
                                  selectedInterval = interval;
                                });
                              }
                            },
                            selectedColor: context.appColors.infoSoft,
                            backgroundColor: context.appColors.surfaceMuted,
                            side: BorderSide(
                              color:
                                  isSelected
                                      ? context.appColors.primary
                                      : context.appColors.line,
                            ),
                            labelStyle: Theme.of(
                              context,
                            ).textTheme.labelMedium?.copyWith(
                              color:
                                  isSelected
                                      ? context.appColors.primaryDark
                                      : context.appColors.inkStrong,
                            ),
                          );
                        }).toList(),
                  ),
                  const SizedBox(height: 22),
                  SizedBox(
                    width: double.infinity,
                    height: 50,
                    child: ElevatedButton.icon(
                      onPressed: () {
                        if (isClosing) return;
                        isClosing = true;
                        FocusScope.of(ctx).unfocus();
                        Navigator.pop(ctx, selectedInterval);
                      },
                      icon: const Icon(Icons.check_circle_outline_rounded),
                      label: const Text('Apply extension'),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );

    if (!mounted || appliedInterval == null) return;
    showAppSnackBar(
      context,
      'Session extended by $appliedInterval. Reminder alert updated.',
      icon: Icons.notifications_active_outlined,
    );
  }

  Widget _buildMonthlyHeader(_MonthlySessionGroup group) {
    return AppSurface(
      margin: const EdgeInsets.only(top: 18, bottom: 10),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
      color: context.appColors.surfaceMuted,
      borderRadius: BorderRadius.circular(AppRadii.control),
      border: null,
      child: Row(
        children: [
          Icon(
            Icons.calendar_month_outlined,
            color: context.appColors.primary,
            size: 19,
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${group.monthYear}  ·  ${group.sessions.length} sessions',
              style: Theme.of(context).textTheme.titleMedium,
            ),
          ),
          Text(
            group.totalExpenditure,
            style: Theme.of(context).textTheme.titleMedium?.copyWith(
              color: context.appColors.primaryDark,
            ),
          ),
        ],
      ),
    );
  }

  String _formatDuration(Duration duration) {
    final hours = duration.inHours.toString().padLeft(2, '0');
    final minutes = (duration.inMinutes % 60).toString().padLeft(2, '0');
    final seconds = (duration.inSeconds % 60).toString().padLeft(2, '0');
    return '$hours:$minutes:$seconds';
  }

  Widget _buildRecentSessionTile(_RecentSessionModel session) {
    return AppSurface(
      padding: const EdgeInsets.all(14),
      borderRadius: BorderRadius.circular(AppRadii.control),
      child: Row(
        children: [
          AppIconTile(
            icon: Icons.history_rounded,
            color: context.appColors.secondaryText,
            backgroundColor: context.appColors.surfaceMuted,
            size: 42,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  session.name,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 3),
                Text(
                  '${session.location}  ·  ${session.dateLabel}',
                  style: Theme.of(context).textTheme.bodySmall,
                  overflow: TextOverflow.ellipsis,
                ),
              ],
            ),
          ),
          const SizedBox(width: 10),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(
                session.cost,
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                  color: context.appColors.inkStrong,
                ),
              ),
              const SizedBox(height: 3),
              Text(
                session.duration,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ],
      ),
    );
  }

  void _onNavTap(int index) {
    if (_isNavigating || index == _selectedNavIndex) return;
    final Widget destination;
    switch (index) {
      case 0:
        destination = const CarparkSearchScreen();
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
