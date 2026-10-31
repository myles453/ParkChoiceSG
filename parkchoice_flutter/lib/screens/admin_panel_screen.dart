import 'package:flutter/material.dart';

import '../constants.dart';
import '../services/operator_session.dart';
import '../widgets/app_ui.dart';
import '../widgets/bottom_nav_bar.dart';
import 'carpark_search_screen.dart';
import 'parking_session_tracker_screen.dart';
import 'preferences_screen.dart';

/// Operator console: alerts, data source health and carpark overrides.
///
/// Reached only after operator sign-in. Panel data is a prototype.
class AdminPanelScreen extends StatefulWidget {
  const AdminPanelScreen({super.key});

  @override
  State<AdminPanelScreen> createState() => _AdminPanelScreenState();
}

enum AlertStatus { newAlert, inProgress, resolved }

class _AdminAlertModel {
  final String id;
  final String description;
  final AlertStatus status;

  const _AdminAlertModel({
    required this.id,
    required this.description,
    required this.status,
  });
}

class _DataSourceModel {
  final String providerName;
  final String apiEndpoint;
  final bool isHealthy;
  final String uptime;
  final String requestVolume;
  final String failureCount;
  final String cacheAge;

  const _DataSourceModel({
    required this.providerName,
    required this.apiEndpoint,
    required this.isHealthy,
    required this.uptime,
    required this.requestVolume,
    required this.failureCount,
    required this.cacheAge,
  });
}

class _CarparkOverrideModel {
  final String carparkId;
  final String carparkName;
  final String overrideStatus;
  final String reason;
  final String appliedBy;

  const _CarparkOverrideModel({
    required this.carparkId,
    required this.carparkName,
    required this.overrideStatus,
    required this.reason,
    required this.appliedBy,
  });
}

class _AdminPanelScreenState extends State<AdminPanelScreen> {
  static const int _selectedNavIndex = 3;
  bool _isNavigating = false;
  final TextEditingController _carparkSearchController =
      TextEditingController();

  List<_AdminAlertModel> _alerts = const [
    _AdminAlertModel(
      id: 'R-8821',
      description: 'Barrier failure at Sector G exit gate',
      status: AlertStatus.newAlert,
    ),
    _AdminAlertModel(
      id: 'R-8819',
      description: 'API ingestion delay for Somerset Mall sensors',
      status: AlertStatus.inProgress,
    ),
    _AdminAlertModel(
      id: 'R-8814',
      description: 'Manual lot count discrepancy at Suntec Plaza',
      status: AlertStatus.resolved,
    ),
  ];

  final List<_DataSourceModel> _dataSources = [
    const _DataSourceModel(
      providerName: 'LTA DataMall API',
      apiEndpoint: 'datamall2.mytransport.sg/ltaodataservice',
      isHealthy: true,
      uptime: '99.9%',
      requestVolume: '4,280 req/min',
      failureCount: '0 (0.0%)',
      cacheAge: '14s ago',
    ),
    const _DataSourceModel(
      providerName: 'Data.gov.sg / HDB API',
      apiEndpoint: 'api-open.data.gov.sg/v1/transport/carpark',
      isHealthy: true,
      uptime: '99.7%',
      requestVolume: '3,120 req/min',
      failureCount: '2 (0.06%)',
      cacheAge: '28s ago',
    ),
    const _DataSourceModel(
      providerName: 'URA Parking API',
      apiEndpoint: 'www.ura.gov.sg/uraServices/carpark',
      isHealthy: false,
      uptime: '94.5%',
      requestVolume: '1,450 req/min',
      failureCount: '18 (1.2%)',
      cacheAge: '52s ago (Stale)',
    ),
    const _DataSourceModel(
      providerName: 'OneMap & Navigation Services',
      apiEndpoint: 'developers.onemap.sg/commonapi',
      isHealthy: true,
      uptime: '99.9%',
      requestVolume: '890 req/min',
      failureCount: '0 (0.0%)',
      cacheAge: 'Live direct',
    ),
  ];

  final List<_CarparkOverrideModel> _activeOverrides = [
    const _CarparkOverrideModel(
      carparkId: 'CP-0104',
      carparkName: 'Orchard Central Terminal',
      overrideStatus: 'CLOSED (Maintenance)',
      reason: 'Exit barrier sensor failure & tarmac repair',
      appliedBy: 'Op-Admin #42  ·  2h ago',
    ),
    const _CarparkOverrideModel(
      carparkId: 'CP-0211',
      carparkName: 'Suntec Plaza Level B2',
      overrideStatus: 'FULL (Force Cap)',
      reason: 'VIP event reserved zone',
      appliedBy: 'Op-Admin #12  ·  4h ago',
    ),
  ];

  @override
  void dispose() {
    _carparkSearchController.dispose();
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
            30,
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              AppPageHeader(
                title: 'Admin panel',
                subtitle: 'Monitor platform health and parking operations.',
                trailing: IconButton(
                  key: const Key('operator-sign-out'),
                  tooltip: 'Sign out',
                  icon: const Icon(Icons.logout_rounded),
                  onPressed: _signOut,
                ),
              ),
              const SizedBox(height: AppSpacing.section),
              AppSectionTitle(
                title: 'Active alerts',
                subtitle: '${_alerts.length} operational notices',
                trailing: AppStatusPill(
                  label:
                      '${_alerts.where((alert) => alert.status != AlertStatus.resolved).length} open',
                  color: context.appColors.warning,
                  icon: Icons.warning_amber_rounded,
                ),
              ),
              const SizedBox(height: 13),
              ..._alerts.map(
                (alert) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _buildAlertCard(alert),
                ),
              ),
              const SizedBox(height: 18),
              const AppSectionTitle(
                title: 'Data-source health',
                subtitle: 'Live status of the four connected gateway APIs.',
              ),
              const SizedBox(height: 13),
              ..._dataSources.map(
                (dataSource) => Padding(
                  padding: const EdgeInsets.only(bottom: 10),
                  child: _buildDataSourceCard(dataSource),
                ),
              ),
              const SizedBox(height: 18),
              const AppSectionTitle(
                title: 'Carpark overrides',
                subtitle: 'Apply or withdraw manual status changes.',
              ),
              const SizedBox(height: 13),
              _buildCarparkOverrideSection(),
            ],
          ),
        ),
      ),
      bottomNavigationBar: _buildBottomNavBar(),
    );
  }

  Widget _buildAlertCard(_AdminAlertModel alert) {
    return AppSurface(
      padding: const EdgeInsets.all(15),
      border: Border.all(color: context.appColors.line),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  alert.id,
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              _buildStatusBadge(alert.status),
            ],
          ),
          const SizedBox(height: 10),
          Text(alert.description, style: Theme.of(context).textTheme.bodyLarge),
          if (alert.status != AlertStatus.resolved) ...[
            const SizedBox(height: 13),
            Align(
              alignment: Alignment.centerRight,
              child: SizedBox(
                height: 38,
                child: OutlinedButton.icon(
                  onPressed: () => _markResolved(alert.id),
                  icon: const Icon(Icons.check_rounded, size: 16),
                  label: const Text('Mark resolved'),
                  style: OutlinedButton.styleFrom(
                    minimumSize: Size.zero,
                    padding: const EdgeInsets.symmetric(horizontal: 13),
                    foregroundColor: context.appColors.success,
                    side: BorderSide(
                      color: context.appColors.success.withValues(alpha: 0.3),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }

  Color _alertColor(AlertStatus status) {
    switch (status) {
      case AlertStatus.newAlert:
        return context.appColors.warning;
      case AlertStatus.inProgress:
        return context.appColors.primary;
      case AlertStatus.resolved:
        return context.appColors.success;
    }
  }

  Widget _buildStatusBadge(AlertStatus status) {
    late String label;
    switch (status) {
      case AlertStatus.newAlert:
        label = 'NEW';
        break;
      case AlertStatus.inProgress:
        label = 'IN PROGRESS';
        break;
      case AlertStatus.resolved:
        label = 'RESOLVED';
        break;
    }
    return AppStatusPill(label: label, color: _alertColor(status));
  }

  Widget _buildDataSourceCard(_DataSourceModel dataSource) {
    final statusColor =
        dataSource.isHealthy
            ? context.appColors.success
            : context.appColors.warning;
    return AppSurface(
      padding: const EdgeInsets.all(15),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.only(top: 5),
                child: Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: statusColor,
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: statusColor.withValues(alpha: 0.25),
                        blurRadius: 0,
                        spreadRadius: 3,
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      dataSource.providerName,
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 3),
                    Text(
                      dataSource.apiEndpoint,
                      style: Theme.of(context).textTheme.bodySmall,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Trigger manual fetch',
                icon: const Icon(Icons.refresh_rounded),
                color: context.appColors.primary,
                onPressed: () => _triggerDataFetch(dataSource.providerName),
              ),
            ],
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 13),
            child: Divider(height: 1, color: context.appColors.line),
          ),
          Row(
            children: [
              Expanded(
                child: _buildSourceMetric(
                  'REQUEST VOLUME',
                  dataSource.requestVolume,
                ),
              ),
              Expanded(
                child: _buildSourceMetric(
                  'FAILURES',
                  dataSource.failureCount,
                  isWarning: !dataSource.isHealthy,
                ),
              ),
            ],
          ),
          const SizedBox(height: 13),
          Row(
            children: [
              Expanded(
                child: _buildSourceMetric('CACHE AGE', dataSource.cacheAge),
              ),
              Expanded(
                child: _buildSourceMetric(
                  'UPTIME',
                  dataSource.uptime,
                  color: statusColor,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSourceMetric(
    String label,
    String value, {
    bool isWarning = false,
    Color? color,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: context.appColors.tertiaryText,
            letterSpacing: 0.65,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          value,
          style: Theme.of(context).textTheme.bodyMedium?.copyWith(
            color:
                color ??
                (isWarning ? context.appColors.warning : context.appColors.ink),
            fontWeight: FontWeight.w600,
          ),
        ),
      ],
    );
  }

  void _markResolved(String id) {
    setState(() {
      _alerts =
          _alerts
              .map(
                (alert) =>
                    alert.id == id
                        ? _AdminAlertModel(
                          id: alert.id,
                          description: alert.description,
                          status: AlertStatus.resolved,
                        )
                        : alert,
              )
              .toList();
    });
    showAppSnackBar(
      context,
      'Alert $id marked as resolved.',
      icon: Icons.check_circle_outline_rounded,
    );
  }

  void _triggerDataFetch(String providerName) {
    showAppSnackBar(
      context,
      'Manual fetch triggered for $providerName.',
      icon: Icons.sync_rounded,
    );
  }

  Widget _buildCarparkOverrideSection() {
    return AppSurface(
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _carparkSearchController,
                  style: Theme.of(context).textTheme.bodyMedium,
                  decoration: InputDecoration(
                    hintText: 'Search a carpark',
                    prefixIcon: Icon(
                      Icons.search_rounded,
                      color: context.appColors.secondaryText,
                      size: 20,
                    ),
                    contentPadding: const EdgeInsets.symmetric(vertical: 13),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              SizedBox(
                height: 50,
                child: ElevatedButton(
                  onPressed: _showAddOverrideModal,
                  style: ElevatedButton.styleFrom(
                    minimumSize: Size.zero,
                    padding: const EdgeInsets.symmetric(horizontal: 14),
                  ),
                  child: const Text('Override'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          Text(
            'ACTIVE STATUS OVERRIDES',
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: context.appColors.secondaryText,
              letterSpacing: 0.75,
            ),
          ),
          const SizedBox(height: 10),
          ..._activeOverrides.map(
            (overrideItem) => Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: _buildOverrideItemTile(overrideItem),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildOverrideItemTile(_CarparkOverrideModel overrideItem) {
    return Container(
      padding: const EdgeInsets.all(13),
      decoration: BoxDecoration(
        color: context.appColors.surfaceMuted,
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(
                  overrideItem.carparkName,
                  style: Theme.of(
                    context,
                  ).textTheme.titleMedium?.copyWith(fontSize: 14),
                ),
              ),
              const SizedBox(width: 8),
              AppStatusPill(
                label: 'OVERRIDE',
                color: context.appColors.danger,
                backgroundColor: context.appColors.dangerSoft,
              ),
            ],
          ),
          const SizedBox(height: 7),
          Text(
            overrideItem.overrideStatus,
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: context.appColors.danger,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            overrideItem.reason,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 9),
          Row(
            children: [
              Expanded(
                child: Text(
                  overrideItem.appliedBy,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: context.appColors.tertiaryText,
                    fontWeight: FontWeight.w600,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              TextButton(
                onPressed: () {
                  setState(() {
                    _activeOverrides.remove(overrideItem);
                  });
                  showAppSnackBar(
                    context,
                    'Override withdrawn for ${overrideItem.carparkName}.',
                    icon: Icons.undo_rounded,
                  );
                },
                style: TextButton.styleFrom(
                  minimumSize: Size.zero,
                  padding: const EdgeInsets.only(left: 8),
                ),
                child: const Text('Withdraw'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Future<void> _showAddOverrideModal() async {
    if (!mounted ||
        _isNavigating ||
        ModalRoute.of(context)?.isCurrent != true) {
      return;
    }
    String selectedCarpark = 'Orchard Central Terminal';
    String selectedStatus = 'CLOSED (Maintenance)';
    var reason = '';
    var isClosing = false;

    final shouldApply = await showModalBottomSheet<bool>(
      context: context,
      useSafeArea: true,
      isScrollControlled: true,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
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
                      'Apply carpark override',
                      onClose: () {
                        if (isClosing ||
                            ModalRoute.of(ctx)?.isCurrent != true) {
                          return;
                        }
                        isClosing = true;
                        FocusScope.of(ctx).unfocus();
                        Navigator.pop(ctx);
                      },
                    ),
                    const SizedBox(height: 5),
                    Text(
                      'Changes are shown to operators immediately and kept in the audit trail.',
                      style: Theme.of(context).textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 18),
                    DropdownButtonFormField<String>(
                      initialValue: selectedCarpark,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Carpark',
                        prefixIcon: Icon(Icons.local_parking_outlined),
                      ),
                      items:
                          const [
                                'Orchard Central Terminal',
                                'Suntec Plaza Level B2',
                                'Somerset Underground',
                                'Marina Square Basement',
                                'Ngee Ann City Tower B',
                              ]
                              .map(
                                (carpark) => DropdownMenuItem(
                                  value: carpark,
                                  child: Text(carpark),
                                ),
                              )
                              .toList(),
                      onChanged: (value) {
                        if (value != null) {
                          setModalState(() => selectedCarpark = value);
                        }
                      },
                    ),
                    const SizedBox(height: 14),
                    DropdownButtonFormField<String>(
                      initialValue: selectedStatus,
                      isExpanded: true,
                      decoration: const InputDecoration(
                        labelText: 'Override status',
                        prefixIcon: Icon(Icons.report_problem_outlined),
                      ),
                      items:
                          const [
                                'CLOSED (Maintenance)',
                                'FULL (Force Cap 0 Lots)',
                                'FORCE OPEN (Override Sensor)',
                              ]
                              .map(
                                (status) => DropdownMenuItem(
                                  value: status,
                                  child: Text(status),
                                ),
                              )
                              .toList(),
                      onChanged: (value) {
                        if (value != null) {
                          setModalState(() => selectedStatus = value);
                        }
                      },
                    ),
                    const SizedBox(height: 14),
                    TextField(
                      maxLines: 3,
                      onChanged: (value) => reason = value,
                      decoration: const InputDecoration(
                        labelText: 'Reason for override',
                        hintText: 'Add a short audit note',
                        alignLabelWithHint: true,
                        prefixIcon: Icon(Icons.notes_outlined),
                      ),
                    ),
                    const SizedBox(height: 20),
                    SizedBox(
                      width: double.infinity,
                      height: 50,
                      child: ElevatedButton(
                        onPressed: () {
                          if (isClosing ||
                              ModalRoute.of(ctx)?.isCurrent != true) {
                            return;
                          }
                          isClosing = true;
                          FocusScope.of(ctx).unfocus();
                          Navigator.pop(ctx, true);
                          /*
                                appliedBy: 'Op-Admin #01  ·  Just now',
                          */
                        },
                        child: const Text('Apply override'),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );

    if (!mounted || shouldApply != true) return;
    final trimmedReason = reason.trim();
    setState(() {
      _activeOverrides.insert(
        0,
        _CarparkOverrideModel(
          carparkId: 'CP-${1000 + _activeOverrides.length}',
          carparkName: selectedCarpark,
          overrideStatus: selectedStatus,
          reason:
              trimmedReason.isNotEmpty
                  ? trimmedReason
                  : 'Manual operator override',
          appliedBy: 'Op-Admin #01 - Just now',
        ),
      );
    });
    showAppSnackBar(
      context,
      'Override applied to $selectedCarpark.',
      icon: Icons.check_circle_outline_rounded,
    );
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

  void _signOut() {
    OperatorSession.instance.signOut();
    _onNavTap(0);
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
      case 2:
        destination = const PreferencesScreen();
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
