import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:parkchoicesg_2/screens/carpark_search_screen.dart';
import 'package:parkchoicesg_2/screens/login_screen.dart';
import 'package:parkchoicesg_2/screens/register_screen.dart';

import 'constants.dart';
import 'services/app_theme_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppThemeController.instance.load();
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    final themeController = AppThemeController.instance;
    return AnimatedBuilder(
      animation: themeController,
      builder: (context, _) {
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: _buildTheme(AppColors.light, Brightness.light),
          darkTheme: _buildTheme(AppColors.dark, Brightness.dark),
          themeMode: themeController.themeMode,
          initialRoute: '/register',
          routes: {
            '/login': (context) => const LoginScreen(),
            '/register': (context) => const RegisterScreen(),
            '/home': (context) => const CarparkSearchScreen(),
          },
        );
      },
    );
  }
}

ThemeData _buildTheme(AppColors colors, Brightness brightness) {
  final isDark = brightness == Brightness.dark;
  final colorScheme = ColorScheme.fromSeed(
    seedColor: colors.primary,
    brightness: brightness,
  ).copyWith(
    primary: colors.primary,
    onPrimary: colors.onBrand,
    secondary: colors.teal,
    onSecondary: isDark ? const Color(0xFF06221F) : Colors.white,
    surface: colors.surface,
    onSurface: colors.inkStrong,
    error: colors.danger,
    onError: isDark ? const Color(0xFF2B080D) : Colors.white,
    outline: colors.line,
    outlineVariant: colors.line,
    surfaceContainerHighest: colors.surfaceMuted,
  );

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: colorScheme,
    extensions: <ThemeExtension<dynamic>>[colors],
    scaffoldBackgroundColor: colors.canvas,
    canvasColor: colors.canvas,
    dividerColor: colors.line,
    splashColor: colors.primary.withValues(alpha: isDark ? 0.14 : 0.09),
    highlightColor: colors.primary.withValues(alpha: 0.06),
    textTheme: TextTheme(
      headlineSmall: TextStyle(
        color: colors.ink,
        fontSize: 28,
        fontWeight: FontWeight.w800,
        letterSpacing: -0.8,
      ),
      titleLarge: TextStyle(
        color: colors.inkStrong,
        fontSize: 18,
        fontWeight: FontWeight.w700,
        letterSpacing: -0.2,
      ),
      titleMedium: TextStyle(
        color: colors.inkStrong,
        fontSize: 15,
        fontWeight: FontWeight.w700,
      ),
      bodyLarge: TextStyle(color: colors.inkStrong, fontSize: 15, height: 1.35),
      bodyMedium: TextStyle(
        color: colors.secondaryText,
        fontSize: 14,
        height: 1.35,
      ),
      bodySmall: TextStyle(
        color: colors.secondaryText,
        fontSize: 12,
        height: 1.35,
      ),
      labelLarge: TextStyle(
        color: colors.inkStrong,
        fontSize: 14,
        fontWeight: FontWeight.w700,
        letterSpacing: 0.1,
      ),
      labelMedium: TextStyle(
        color: colors.inkStrong,
        fontSize: 12,
        fontWeight: FontWeight.w700,
      ),
      labelSmall: TextStyle(
        color: colors.secondaryText,
        fontSize: 11,
        fontWeight: FontWeight.w700,
      ),
    ),
    iconTheme: IconThemeData(color: colors.secondaryText),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: colors.surfaceMuted,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
      hintStyle: TextStyle(color: colors.tertiaryText, fontSize: 14),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadii.control),
        borderSide: BorderSide(color: colors.line),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadii.control),
        borderSide: BorderSide(color: colors.line),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(AppRadii.control),
        borderSide: BorderSide(color: colors.primary, width: 1.5),
      ),
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: colors.primary,
        foregroundColor: colors.onBrand,
        disabledBackgroundColor: colors.surfaceSubtle,
        disabledForegroundColor: colors.tertiaryText,
        elevation: 0,
        minimumSize: const Size.fromHeight(52),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadii.control),
        ),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: colors.primary,
        minimumSize: const Size.fromHeight(48),
        side: BorderSide(color: colors.line),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadii.control),
        ),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: colors.primary),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: colors.surface,
      indicatorColor: colors.infoSoft,
      surfaceTintColor: Colors.transparent,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          color:
              states.contains(WidgetState.selected)
                  ? colors.primaryDark
                  : colors.secondaryText,
          fontSize: 11,
          fontWeight: FontWeight.w700,
        ),
      ),
      iconTheme: WidgetStateProperty.resolveWith(
        (states) => IconThemeData(
          color:
              states.contains(WidgetState.selected)
                  ? colors.primary
                  : colors.secondaryText,
          size: 22,
        ),
      ),
    ),
    sliderTheme: SliderThemeData(
      activeTrackColor: colors.primary,
      inactiveTrackColor: colors.surfaceSubtle,
      thumbColor: colors.primary,
      overlayColor: colors.primary.withValues(alpha: 0.12),
      valueIndicatorColor: colors.snackBar,
      valueIndicatorTextStyle: TextStyle(color: colors.onSnackBar),
      trackHeight: 4,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: colors.surface,
      surfaceTintColor: Colors.transparent,
      modalBarrierColor: Colors.black.withValues(alpha: 0.58),
      showDragHandle: true,
      dragHandleColor: colors.tertiaryText,
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: colors.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadii.card),
      ),
    ),
    dividerTheme: DividerThemeData(color: colors.line, thickness: 1),
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {
        TargetPlatform.android: CupertinoPageTransitionsBuilder(),
        TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
      },
    ),
  );
}
