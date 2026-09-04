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
    canvas: Color(0xFFF5F7FB),
    surface: Colors.white,
    surfaceMuted: Color(0xFFF0F4F8),
    surfaceSubtle: Color(0xFFEAF0F6),
    ink: Color(0xFF102A43),
    inkStrong: Color(0xFF172B4D),
    secondaryText: Color(0xFF52667A),
    tertiaryText: Color(0xFF8293A6),
    line: Color(0xFFDCE5EE),
    primary: Color(0xFF2563EB),
    primaryDark: Color(0xFF1D4ED8),
    teal: Color(0xFF0F766E),
    success: Color(0xFF16805B),
    successSoft: Color(0xFFE8F6F0),
    warning: Color(0xFFB7791F),
    warningSoft: Color(0xFFFFF6E5),
    danger: Color(0xFFB42318),
    dangerSoft: Color(0xFFFFEFED),
    infoSoft: Color(0xFFEAF1FF),
    brand: Color(0xFF102A43),
    onBrand: Colors.white,
    snackBar: Color(0xFF102A43),
    onSnackBar: Colors.white,
    mapBackground: Color(0xFFEAF1F5),
    mapWater: Color(0xFFDDECF2),
    mapRoad: Colors.white,
    mapRoadEdge: Color(0xFFC8D7E0),
    mapBlock: Color(0xFFDCE7E5),
  );

  static const dark = AppColors(
    canvas: Color(0xFF09111F),
    surface: Color(0xFF111C2C),
    surfaceMuted: Color(0xFF182638),
    surfaceSubtle: Color(0xFF223247),
    ink: Color(0xFFEAF1F8),
    inkStrong: Color(0xFFF5F8FC),
    secondaryText: Color(0xFFB0C0D0),
    tertiaryText: Color(0xFF8295A9),
    line: Color(0xFF2A3B50),
    primary: Color(0xFF72A7FF),
    primaryDark: Color(0xFFA8C8FF),
    teal: Color(0xFF5EEAD4),
    success: Color(0xFF5DD6A1),
    successSoft: Color(0xFF102D27),
    warning: Color(0xFFF2C35B),
    warningSoft: Color(0xFF342A16),
    danger: Color(0xFFFF8A8A),
    dangerSoft: Color(0xFF351B22),
    infoSoft: Color(0xFF162C4D),
    brand: Color(0xFF72A7FF),
    onBrand: Color(0xFF071426),
    snackBar: Color(0xFFE5EDF7),
    onSnackBar: Color(0xFF101A29),
    mapBackground: Color(0xFF152232),
    mapWater: Color(0xFF123043),
    mapRoad: Color(0xFF2A3B4E),
    mapRoadEdge: Color(0xFF34495F),
    mapBlock: Color(0xFF20372F),
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

  static const double card = 20;
  static const double control = 14;
  static const double small = 10;
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
