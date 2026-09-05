import 'package:flutter/material.dart';

import '../constants.dart';

class AppSpacing {
  AppSpacing._();

  static const double page = 20;
  static const double section = 28;
  static const double card = 16;
  static const double compact = 12;
}

class AppSurface extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final Color? color;
  final BorderRadius borderRadius;
  final Border? border;
  final List<BoxShadow>? boxShadow;

  const AppSurface({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(AppSpacing.card),
    this.margin,
    this.color,
    this.borderRadius = const BorderRadius.all(Radius.circular(AppRadii.card)),
    this.border,
    this.boxShadow,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: margin,
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? context.appColors.surface,
        borderRadius: borderRadius,
        border: border ?? Border.all(color: context.appColors.line),
        boxShadow: boxShadow,
      ),
      child: child,
    );
  }
}

class AppPageHeader extends StatelessWidget {
  final String title;
  final String subtitle;
  final Widget? trailing;

  const AppPageHeader({
    super.key,
    required this.title,
    required this.subtitle,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(title, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 5),
              Text(subtitle, style: Theme.of(context).textTheme.bodyMedium),
            ],
          ),
        ),
        const SizedBox(width: 16),
        trailing ?? const AppProfileBadge(),
      ],
    );
  }
}

class AppProfileBadge extends StatelessWidget {
  const AppProfileBadge({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 42,
      height: 42,
      decoration: BoxDecoration(
        color: context.appColors.surface,
        shape: BoxShape.circle,
        border: Border.all(color: context.appColors.line),
      ),
      child: Icon(
        Icons.person_outline_rounded,
        color: context.appColors.secondaryText,
        size: 21,
      ),
    );
  }
}

class AppBrandMark extends StatelessWidget {
  final bool showWordmark;

  const AppBrandMark({super.key, this.showWordmark = true});

  @override
  Widget build(BuildContext context) {
    final mark = Container(
      width: 48,
      height: 48,
      decoration: BoxDecoration(
        color: context.appColors.brand,
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      child: Icon(
        Icons.local_parking_rounded,
        color: context.appColors.onBrand,
        size: 27,
      ),
    );

    if (!showWordmark) return mark;

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        mark,
        const SizedBox(height: 14),
        Text(
          'ParkChoiceSG',
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            color: context.appColors.ink,
            fontSize: 22,
            fontWeight: FontWeight.w600,
            letterSpacing: -0.7,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          'Smart parking, less circling',
          style: Theme.of(context).textTheme.labelSmall?.copyWith(
            color: context.appColors.tertiaryText,
            letterSpacing: 0.1,
            fontWeight: FontWeight.w400,
            fontSize: 12,
          ),
        ),
      ],
    );
  }
}

class AppSectionTitle extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget? trailing;

  const AppSectionTitle({
    super.key,
    required this.title,
    this.subtitle,
    this.trailing,
  });

  @override
  Widget build(BuildContext context) {
    final titleBlock = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(title, style: Theme.of(context).textTheme.titleLarge),
        if (subtitle != null) ...[
          const SizedBox(height: 5),
          Text(subtitle!, style: Theme.of(context).textTheme.bodySmall),
        ],
      ],
    );

    if (trailing == null) return titleBlock;

    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Expanded(child: titleBlock),
        const SizedBox(width: 12),
        trailing!,
      ],
    );
  }
}

class AppTextField extends StatelessWidget {
  final TextEditingController? controller;
  final String? label;
  final String hint;
  final IconData? prefixIcon;
  final Widget? suffixIcon;
  final bool obscureText;
  final TextInputType? keyboardType;
  final int maxLines;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onChanged;

  const AppTextField({
    super.key,
    this.controller,
    this.label,
    required this.hint,
    this.prefixIcon,
    this.suffixIcon,
    this.obscureText = false,
    this.keyboardType,
    this.maxLines = 1,
    this.textInputAction,
    this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (label != null) ...[
          Text(
            label!,
            style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: context.appColors.inkStrong,
              fontWeight: FontWeight.w500,
              letterSpacing: 0,
            ),
          ),
          const SizedBox(height: 8),
        ],
        TextField(
          controller: controller,
          obscureText: obscureText,
          keyboardType: keyboardType,
          maxLines: maxLines,
          textInputAction: textInputAction,
          onChanged: onChanged,
          style: Theme.of(context).textTheme.bodyLarge?.copyWith(
            color: context.appColors.inkStrong,
            fontWeight: FontWeight.w400,
          ),
          decoration: InputDecoration(
            hintText: hint,
            prefixIcon:
                prefixIcon == null
                    ? null
                    : Icon(
                      prefixIcon,
                      color: context.appColors.secondaryText,
                      size: 21,
                    ),
            suffixIcon: suffixIcon,
          ),
        ),
      ],
    );
  }
}

class AppStatusPill extends StatelessWidget {
  final String label;
  final Color color;
  final Color? backgroundColor;
  final IconData? icon;

  const AppStatusPill({
    super.key,
    required this.label,
    required this.color,
    this.backgroundColor,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
      decoration: BoxDecoration(
        color: backgroundColor ?? color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(AppRadii.small),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, color: color, size: 14),
            const SizedBox(width: 5),
          ],
          Text(
            label,
            style: Theme.of(context).textTheme.labelSmall?.copyWith(
              color: color,
              fontWeight: FontWeight.w600,
              letterSpacing: 0,
            ),
          ),
        ],
      ),
    );
  }
}

class AppIconTile extends StatelessWidget {
  final IconData icon;
  final Color? color;
  final Color? backgroundColor;
  final double size;

  const AppIconTile({
    super.key,
    required this.icon,
    this.color,
    this.backgroundColor,
    this.size = 42,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: backgroundColor ?? context.appColors.surfaceMuted,
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      child: Icon(
        icon,
        color: color ?? context.appColors.secondaryText,
        size: size * 0.46,
      ),
    );
  }
}

class AppMetric extends StatelessWidget {
  final String label;
  final String value;
  final String? subtitle;
  final Color? valueColor;
  final IconData? icon;

  const AppMetric({
    super.key,
    required this.label,
    required this.value,
    this.subtitle,
    this.valueColor,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: context.appColors.surfaceMuted,
        borderRadius: BorderRadius.circular(AppRadii.control),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              if (icon != null) ...[
                Icon(icon, color: context.appColors.secondaryText, size: 14),
                const SizedBox(width: 5),
              ],
              Expanded(
                child: Text(
                  label,
                  style: Theme.of(context).textTheme.labelSmall?.copyWith(
                    color: context.appColors.secondaryText,
                    fontWeight: FontWeight.w500,
                    letterSpacing: 0.25,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            value,
            style: Theme.of(context).textTheme.titleLarge?.copyWith(
              color: valueColor ?? context.appColors.ink,
              fontSize: 24,
              fontWeight: FontWeight.w500,
              letterSpacing: -0.6,
              fontFeatures: const [FontFeature.tabularFigures()],
            ),
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 3),
            Text(subtitle!, style: Theme.of(context).textTheme.bodySmall),
          ],
        ],
      ),
    );
  }
}

void showAppSnackBar(
  BuildContext context,
  String message, {
  Color? backgroundColor,
  Color? foregroundColor,
  IconData? icon,
}) {
  ScaffoldMessenger.of(context)
    ..hideCurrentSnackBar()
    ..showSnackBar(
      SnackBar(
        backgroundColor: backgroundColor ?? context.appColors.snackBar,
        behavior: SnackBarBehavior.floating,
        margin: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadii.control),
        ),
        content: Row(
          children: [
            if (icon != null) ...[
              Icon(
                icon,
                color: foregroundColor ?? context.appColors.onSnackBar,
                size: 19,
              ),
              const SizedBox(width: 10),
            ],
            Expanded(
              child: Text(
                message,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: foregroundColor ?? context.appColors.onSnackBar,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
          ],
        ),
      ),
    );
}
