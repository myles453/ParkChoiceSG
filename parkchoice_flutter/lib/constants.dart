import 'package:flutter/material.dart';

/// Semantic colors shared by every ParkChoiceSG screen.
///
/// Widgets resolve this extension from [Theme] so every surface, label, status,
/// and map treatment has an intentional light and dark appearance.
@immutable
class AppColors extends ThemeExtension<AppColors> {
  const AppColors({
    required this.canvas,
    required this.surface,
    required this.surfaceMuted,
    required this.surfaceSubtle,
    required this.ink,
    required this.inkStrong,
    required this.secondaryText,
    required this.tertiaryText,
    required this.line,
    required this.primary,
    required this.primaryDark,
    required this.teal,
    required this.success,
    required this.successSoft,
    required this.warning,
    required this.warningSoft,
    required this.danger,
    required this.dangerSoft,
    required this.infoSoft,
    required this.brand,
    required this.onBrand,
    required this.snackBar,
    required this.onSnackBar,
    required this.mapBackground,
    required this.mapWater,
    required this.mapRoad,
    required this.mapRoadEdge,
    required this.mapBlock,
  });

  final Color canvas;
  final Color surface;
  final Color surfaceMuted;
  final Color surfaceSubtle;
  final Color ink;
  final Color inkStrong;
  final Color secondaryText;
  final Color tertiaryText;
  final Color line;
  final Color primary;
  final Color primaryDark;
  final Color teal;
  final Color success;
  final Color successSoft;
  final Color warning;
  final Color warningSoft;
  final Color danger;
  final Color dangerSoft;
  final Color infoSoft;
  final Color brand;
  final Color onBrand;
  final Color snackBar;
  final Color onSnackBar;
  final Color mapBackground;
  final Color mapWater;
  final Color mapRoad;
  final Color mapRoadEdge;
  final Color mapBlock;

  static const light = AppColors(
    canvas: Color(0xFFF5F6F3),
    surface: Colors.white,
    surfaceMuted: Color(0xFFF0F2EF),
    surfaceSubtle: Color(0xFFE6EAE5),
    ink: Color(0xFF1C2822),
    inkStrong: Color(0xFF202B25),
    secondaryText: Color(0xFF536159),
    tertiaryText: Color(0xFF606E63),
    line: Color(0xFFD9DFD8),
    primary: Color(0xFF285C48),
    primaryDark: Color(0xFF204B3B),
    teal: Color(0xFF3C6552),
    success: Color(0xFF326348),
    successSoft: Color(0xFFEDF4ED),
    warning: Color(0xFF88591D),
    warningSoft: Color(0xFFFAF2E5),
    danger: Color(0xFFA53E36),
    dangerSoft: Color(0xFFFAEEEB),
    infoSoft: Color(0xFFEAF1EB),
    brand: Color(0xFF285C48),
    onBrand: Colors.white,
    snackBar: Color(0xFF202B25),
    onSnackBar: Colors.white,
    mapBackground: Color(0xFFECEEE8),
    mapWater: Color(0xFFD9E6E7),
    mapRoad: Colors.white,
    mapRoadEdge: Color(0xFFCDD4CB),
    mapBlock: Color(0xFFDDE5D6),
  );

  static const dark = AppColors(
    canvas: Color(0xFF131715),
    surface: Color(0xFF1C211E),
    surfaceMuted: Color(0xFF252C27),
    surfaceSubtle: Color(0xFF303A33),
    ink: Color(0xFFE9EEE7),
    inkStrong: Color(0xFFF0F3ED),
    secondaryText: Color(0xFFB1BDB2),
    tertiaryText: Color(0xFF95A296),
    line: Color(0xFF38433A),
    primary: Color(0xFFA3C9AE),
    primaryDark: Color(0xFFB7D7BF),
    teal: Color(0xFFA1BFA9),
    success: Color(0xFFA6C9AA),
    successSoft: Color(0xFF26372A),
    warning: Color(0xFFE0BC82),
    warningSoft: Color(0xFF393022),
    danger: Color(0xFFEAA69C),
    dangerSoft: Color(0xFF3C2926),
    infoSoft: Color(0xFF293A2E),
    brand: Color(0xFFA3C9AE),
    onBrand: Color(0xFF17291D),
    snackBar: Color(0xFFE5ECE2),
    onSnackBar: Color(0xFF1C2822),
    mapBackground: Color(0xFF222A24),
    mapWater: Color(0xFF263B3D),
    mapRoad: Color(0xFF3C453D),
    mapRoadEdge: Color(0xFF4B574D),
    mapBlock: Color(0xFF2C3A2B),
  );

  static AppColors of(BuildContext context) {
    return Theme.of(context).extension<AppColors>() ?? light;
  }

  @override
  AppColors copyWith({
    Color? canvas,
    Color? surface,
    Color? surfaceMuted,
    Color? surfaceSubtle,
    Color? ink,
    Color? inkStrong,
    Color? secondaryText,
    Color? tertiaryText,
    Color? line,
    Color? primary,
    Color? primaryDark,
    Color? teal,
    Color? success,
    Color? successSoft,
    Color? warning,
    Color? warningSoft,
    Color? danger,
    Color? dangerSoft,
    Color? infoSoft,
    Color? brand,
    Color? onBrand,
    Color? snackBar,
    Color? onSnackBar,
    Color? mapBackground,
    Color? mapWater,
    Color? mapRoad,
    Color? mapRoadEdge,
    Color? mapBlock,
  }) {
    return AppColors(
      canvas: canvas ?? this.canvas,
      surface: surface ?? this.surface,
      surfaceMuted: surfaceMuted ?? this.surfaceMuted,
      surfaceSubtle: surfaceSubtle ?? this.surfaceSubtle,
      ink: ink ?? this.ink,
      inkStrong: inkStrong ?? this.inkStrong,
      secondaryText: secondaryText ?? this.secondaryText,
      tertiaryText: tertiaryText ?? this.tertiaryText,
      line: line ?? this.line,
      primary: primary ?? this.primary,
      primaryDark: primaryDark ?? this.primaryDark,
      teal: teal ?? this.teal,
      success: success ?? this.success,
      successSoft: successSoft ?? this.successSoft,
      warning: warning ?? this.warning,
      warningSoft: warningSoft ?? this.warningSoft,
      danger: danger ?? this.danger,
      dangerSoft: dangerSoft ?? this.dangerSoft,
      infoSoft: infoSoft ?? this.infoSoft,
      brand: brand ?? this.brand,
      onBrand: onBrand ?? this.onBrand,
      snackBar: snackBar ?? this.snackBar,
      onSnackBar: onSnackBar ?? this.onSnackBar,
      mapBackground: mapBackground ?? this.mapBackground,
      mapWater: mapWater ?? this.mapWater,
      mapRoad: mapRoad ?? this.mapRoad,
      mapRoadEdge: mapRoadEdge ?? this.mapRoadEdge,
      mapBlock: mapBlock ?? this.mapBlock,
    );
  }

  @override
  AppColors lerp(covariant AppColors? other, double t) {
    if (other == null) return this;
    return AppColors(
      canvas: Color.lerp(canvas, other.canvas, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceMuted: Color.lerp(surfaceMuted, other.surfaceMuted, t)!,
      surfaceSubtle: Color.lerp(surfaceSubtle, other.surfaceSubtle, t)!,
      ink: Color.lerp(ink, other.ink, t)!,
      inkStrong: Color.lerp(inkStrong, other.inkStrong, t)!,
      secondaryText: Color.lerp(secondaryText, other.secondaryText, t)!,
      tertiaryText: Color.lerp(tertiaryText, other.tertiaryText, t)!,
      line: Color.lerp(line, other.line, t)!,
      primary: Color.lerp(primary, other.primary, t)!,
      primaryDark: Color.lerp(primaryDark, other.primaryDark, t)!,
      teal: Color.lerp(teal, other.teal, t)!,
      success: Color.lerp(success, other.success, t)!,
      successSoft: Color.lerp(successSoft, other.successSoft, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningSoft: Color.lerp(warningSoft, other.warningSoft, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
      dangerSoft: Color.lerp(dangerSoft, other.dangerSoft, t)!,
      infoSoft: Color.lerp(infoSoft, other.infoSoft, t)!,
      brand: Color.lerp(brand, other.brand, t)!,
      onBrand: Color.lerp(onBrand, other.onBrand, t)!,
      snackBar: Color.lerp(snackBar, other.snackBar, t)!,
      onSnackBar: Color.lerp(onSnackBar, other.onSnackBar, t)!,
      mapBackground: Color.lerp(mapBackground, other.mapBackground, t)!,
      mapWater: Color.lerp(mapWater, other.mapWater, t)!,
      mapRoad: Color.lerp(mapRoad, other.mapRoad, t)!,
      mapRoadEdge: Color.lerp(mapRoadEdge, other.mapRoadEdge, t)!,
      mapBlock: Color.lerp(mapBlock, other.mapBlock, t)!,
    );
  }
}

extension AppColorsContext on BuildContext {
  AppColors get appColors => AppColors.of(this);
}

class AppRadii {
  AppRadii._();

  static const double card = 12;
  static const double control = 8;
  static const double small = 6;
  static const double pill = 999;
}

/// Compatibility aliases retained for any untouched prototype code.
class CustomColor {
  CustomColor._();

  static final Color darkGrey = AppColors.light.ink;
  static final Color lightGrey = AppColors.light.surfaceMuted;
  static final Color neroGrey = AppColors.light.canvas;
  static final Color denimBlue = AppColors.light.primary;
}
