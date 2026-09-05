import 'package:flutter/foundation.dart';
import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:parkchoicesg_2/screens/carpark_search_screen.dart';
import 'package:parkchoicesg_2/screens/login_screen.dart';
import 'package:parkchoicesg_2/screens/register_screen.dart';

import 'constants.dart';
import 'services/app_theme_controller.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  LicenseRegistry.addLicense(() async* {
    final license = await rootBundle.loadString(
      'assets/fonts/public_sans/LICENSE.md',
    );
    yield LicenseEntryWithLineBreaks(['Public Sans'], license);
  });
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
  const fontFamily = 'Public Sans';
  const buttonText = TextStyle(
    fontFamily: fontFamily,
    fontSize: 14,
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
  );
  final colorScheme = ColorScheme.fromSeed(
    seedColor: colors.primary,
    brightness: brightness,
  ).copyWith(
    primary: colors.primary,
    onPrimary: colors.onBrand,
    primaryContainer: colors.infoSoft,
    onPrimaryContainer: colors.primaryDark,
    secondary: colors.teal,
    onSecondary: colors.onBrand,
    secondaryContainer: colors.infoSoft,
    onSecondaryContainer: colors.primaryDark,
    tertiary: colors.teal,
    onTertiary: colors.onBrand,
    tertiaryContainer: colors.surfaceMuted,
    onTertiaryContainer: colors.inkStrong,
    surface: colors.surface,
    onSurface: colors.inkStrong,
    onSurfaceVariant: colors.secondaryText,
    error: colors.danger,
    onError: colors.onBrand,
    errorContainer: colors.dangerSoft,
    onErrorContainer: colors.danger,
    outline: colors.tertiaryText,
    outlineVariant: colors.line,
    surfaceDim: colors.canvas,
    surfaceBright: colors.surface,
    surfaceContainerLowest: colors.canvas,
    surfaceContainerLow: colors.surface,
    surfaceContainer: colors.surface,
    surfaceContainerHigh: colors.surfaceMuted,
    surfaceContainerHighest: colors.surfaceSubtle,
    inverseSurface: colors.snackBar,
    onInverseSurface: colors.onSnackBar,
    inversePrimary: isDark ? AppColors.light.primary : AppColors.dark.primary,
    surfaceTint: Colors.transparent,
  );

  return ThemeData(
    useMaterial3: true,
    brightness: brightness,
    fontFamily: fontFamily,
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
        fontWeight: FontWeight.w600,
        letterSpacing: -0.9,
        height: 1.2,
      ),
      titleLarge: TextStyle(
        color: colors.inkStrong,
        fontSize: 17,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.35,
        height: 1.3,
      ),
      titleMedium: TextStyle(
        color: colors.inkStrong,
        fontSize: 15,
        fontWeight: FontWeight.w600,
        letterSpacing: -0.2,
        height: 1.35,
      ),
      bodyLarge: TextStyle(color: colors.inkStrong, fontSize: 15, height: 1.45),
      bodyMedium: TextStyle(
        color: colors.secondaryText,
        fontSize: 14,
        height: 1.45,
      ),
      bodySmall: TextStyle(
        color: colors.secondaryText,
        fontSize: 12,
        height: 1.45,
      ),
      labelLarge: TextStyle(
        color: colors.inkStrong,
        fontSize: 14,
        fontWeight: FontWeight.w600,
        letterSpacing: 0,
      ),
      labelMedium: TextStyle(
        color: colors.inkStrong,
        fontSize: 12,
        fontWeight: FontWeight.w500,
        letterSpacing: 0,
      ),
      labelSmall: TextStyle(
        color: colors.secondaryText,
        fontSize: 11,
        fontWeight: FontWeight.w500,
        letterSpacing: 0.1,
      ),
    ).apply(fontFamily: fontFamily),
    iconTheme: IconThemeData(color: colors.secondaryText),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: colors.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 15),
      hintStyle: TextStyle(
        fontFamily: fontFamily,
        color: colors.tertiaryText,
        fontSize: 14,
        fontWeight: FontWeight.w400,
      ),
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
        textStyle: buttonText,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        surfaceTintColor: Colors.transparent,
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: colors.inkStrong,
        minimumSize: const Size.fromHeight(48),
        side: BorderSide(color: colors.line),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadii.control),
        ),
        textStyle: buttonText,
        padding: const EdgeInsets.symmetric(horizontal: 16),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: colors.primary,
        textStyle: buttonText,
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: colors.surface,
      indicatorColor: colors.infoSoft,
      indicatorShape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      surfaceTintColor: Colors.transparent,
      labelTextStyle: WidgetStateProperty.resolveWith(
        (states) => TextStyle(
          fontFamily: fontFamily,
          color:
              states.contains(WidgetState.selected)
                  ? colors.primaryDark
                  : colors.secondaryText,
          fontSize: 11,
          fontWeight:
              states.contains(WidgetState.selected)
                  ? FontWeight.w600
                  : FontWeight.w500,
          letterSpacing: 0,
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
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: colors.primary,
      selectionColor: colors.primary.withValues(alpha: 0.2),
      selectionHandleColor: colors.primary,
    ),
    chipTheme: ChipThemeData(
      backgroundColor: colors.surfaceMuted,
      selectedColor: colors.infoSoft,
      checkmarkColor: colors.primary,
      side: BorderSide(color: colors.line),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      labelStyle: buttonText.copyWith(fontSize: 12, color: colors.inkStrong),
      elevation: 0,
      pressElevation: 0,
    ),
    sliderTheme: SliderThemeData(
      activeTrackColor: colors.primary,
      inactiveTrackColor: colors.surfaceSubtle,
      thumbColor: colors.primary,
      overlayColor: colors.primary.withValues(alpha: 0.12),
      valueIndicatorColor: colors.snackBar,
      valueIndicatorTextStyle: buttonText.copyWith(color: colors.onSnackBar),
      trackHeight: 4,
    ),
    bottomSheetTheme: BottomSheetThemeData(
      backgroundColor: colors.surface,
      surfaceTintColor: Colors.transparent,
      modalBarrierColor: Colors.black.withValues(alpha: isDark ? 0.64 : 0.4),
      showDragHandle: true,
      dragHandleColor: colors.tertiaryText,
      dragHandleSize: const Size(32, 4),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
    ),
    dialogTheme: DialogThemeData(
      backgroundColor: colors.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadii.card),
      ),
    ),
    dividerTheme: DividerThemeData(color: colors.line, thickness: 1),
    tooltipTheme: TooltipThemeData(
      decoration: BoxDecoration(
        color: colors.snackBar,
        borderRadius: BorderRadius.circular(AppRadii.small),
      ),
      textStyle: buttonText.copyWith(fontSize: 12, color: colors.onSnackBar),
    ),
    pageTransitionsTheme: const PageTransitionsTheme(
      builders: {
        TargetPlatform.android: CupertinoPageTransitionsBuilder(),
        TargetPlatform.iOS: CupertinoPageTransitionsBuilder(),
      },
    ),
  );
}
