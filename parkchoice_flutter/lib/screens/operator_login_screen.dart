import 'package:flutter/material.dart';

import '../constants.dart';
import '../services/operator_session.dart';
import '../services/parking_api.dart';
import '../widgets/app_ui.dart';
import '../widgets/bottom_nav_bar.dart';
import 'admin_panel_screen.dart';
import 'carpark_search_screen.dart';
import 'parking_session_tracker_screen.dart';
import 'preferences_screen.dart';

/// The admin tab's entry point: the panel when signed in, otherwise sign-in.
Widget operatorEntryScreen() =>
    OperatorSession.instance.signedIn
        ? const AdminPanelScreen()
        : const OperatorLoginScreen();

/// Sign-in for the single operator account. Drivers use the app without one.
class OperatorLoginScreen extends StatefulWidget {
  final ParkingApi? api;

  const OperatorLoginScreen({super.key, this.api});

  @override
  State<OperatorLoginScreen> createState() => _OperatorLoginScreenState();
}

class _OperatorLoginScreenState extends State<OperatorLoginScreen> {
  static const _navIndex = 3;
  final _usernameController = TextEditingController();
  final _passwordController = TextEditingController();
  late final ParkingApi _api = widget.api ?? ParkingApi();
  bool _obscurePassword = true;
  bool _submitting = false;
  bool _isNavigating = false;
  String? _error;

  Future<void> _signIn() async {
    if (!mounted || _submitting || _isNavigating) return;
    final username = _usernameController.text.trim();
    final password = _passwordController.text;
    if (username.isEmpty || password.isEmpty) {
      setState(() => _error = 'Enter the operator username and password.');
      return;
    }
    FocusManager.instance.primaryFocus?.unfocus();
    setState(() {
      _submitting = true;
      _error = null;
    });
    try {
      final ok = await _api.operatorLogin(
        username: username,
        password: password,
      );
      if (!mounted || _isNavigating) return;
      if (!ok) {
        setState(() => _error = 'Incorrect operator username or password.');
        return;
      }
      OperatorSession.instance.signIn();
      _replaceWith(const AdminPanelScreen());
    } catch (_) {
      if (mounted && !_isNavigating) {
        setState(
          () => _error = 'Operator sign-in is unavailable. Please try again.',
        );
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _replaceWith(Widget destination) {
    if (!mounted || _isNavigating) return;
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

  void _onNavTap(int index) {
    if (index == _navIndex) return;
    final Widget? destination = switch (index) {
      0 => const CarparkSearchScreen(),
      1 => const ParkingSessionTrackerScreen(),
      2 => const PreferencesScreen(),
      _ => null,
    };
    if (destination != null) _replaceWith(destination);
  }

  @override
  void dispose() {
    _usernameController.dispose();
    _passwordController.dispose();
    if (widget.api == null) _api.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      bottomNavigationBar: ParkChoiceBottomNav(
        selectedIndex: _navIndex,
        onDestinationSelected: _onNavTap,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 460),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const AppBrandMark(),
                  const SizedBox(height: 46),
                  Text(
                    'Operator sign-in',
                    style: Theme.of(context).textTheme.headlineSmall,
                  ),
                  const SizedBox(height: 7),
                  Text(
                    'The admin panel is for the ParkChoiceSG operator. '
                    'Drivers do not need an account.',
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                  const SizedBox(height: 28),
                  AppTextField(
                    key: const Key('operator-username'),
                    controller: _usernameController,
                    label: 'Username',
                    hint: 'Operator username',
                    prefixIcon: Icons.person_outline_rounded,
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 18),
                  AppTextField(
                    key: const Key('operator-password'),
                    controller: _passwordController,
                    label: 'Password',
                    hint: 'Operator password',
                    prefixIcon: Icons.lock_outline_rounded,
                    obscureText: _obscurePassword,
                    textInputAction: TextInputAction.done,
                    suffixIcon: IconButton(
                      tooltip:
                          _obscurePassword ? 'Show password' : 'Hide password',
                      icon: Icon(
                        _obscurePassword
                            ? Icons.visibility_outlined
                            : Icons.visibility_off_outlined,
                        color: context.appColors.secondaryText,
                        size: 20,
                      ),
                      onPressed:
                          () => setState(
                            () => _obscurePassword = !_obscurePassword,
                          ),
                    ),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 14),
                    Text(
                      _error!,
                      style: TextStyle(color: context.appColors.danger),
                    ),
                  ],
                  const SizedBox(height: 22),
                  SizedBox(
                    height: 52,
                    child: ElevatedButton(
                      onPressed: _submitting ? null : _signIn,
                      child:
                          _submitting
                              ? const SizedBox(
                                width: 20,
                                height: 20,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                ),
                              )
                              : const Text('Sign in'),
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
}
