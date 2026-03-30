import 'package:flutter/material.dart';

import 'backend_status_controller.dart';

class BackendStatusBanner extends StatefulWidget {
  const BackendStatusBanner({
    super.key,
    required this.isArabic,
    this.controller,
    this.compact = false,
    this.forDarkBackground = false,
    this.showRefreshButton = true,
  });

  final bool isArabic;
  final BackendStatusController? controller;
  final bool compact;
  final bool forDarkBackground;
  final bool showRefreshButton;

  @override
  State<BackendStatusBanner> createState() => _BackendStatusBannerState();
}

class _BackendStatusBannerState extends State<BackendStatusBanner> {
  late final BackendStatusController _controller;

  @override
  void initState() {
    super.initState();
    _controller = widget.controller ?? BackendStatusController.instance;
    _controller.ensureStarted();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final visuals = _buildVisuals(
          _controller.snapshot.status,
          isArabic: widget.isArabic,
          forDarkBackground: widget.forDarkBackground,
        );

        if (widget.compact) {
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: visuals.backgroundColor,
              borderRadius: BorderRadius.circular(999),
              border: Border.all(color: visuals.borderColor),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: visuals.accentColor,
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  visuals.title,
                  style: TextStyle(
                    color: visuals.textColor,
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                if (widget.showRefreshButton) ...[
                  const SizedBox(width: 4),
                  InkWell(
                    onTap: () => _controller.refresh(),
                    borderRadius: BorderRadius.circular(999),
                    child: Padding(
                      padding: const EdgeInsets.all(4),
                      child: Icon(
                        Icons.refresh_rounded,
                        size: 15,
                        color: visuals.textColor,
                      ),
                    ),
                  ),
                ],
              ],
            ),
          );
        }

        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: visuals.backgroundColor,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: visuals.borderColor),
          ),
          child: Row(
            children: [
              Container(
                width: 38,
                height: 38,
                decoration: BoxDecoration(
                  color: visuals.accentColor.withValues(alpha: 0.14),
                  shape: BoxShape.circle,
                ),
                child: Icon(visuals.icon, color: visuals.accentColor, size: 20),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      visuals.title,
                      style: TextStyle(
                        color: visuals.textColor,
                        fontSize: 13.5,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      visuals.subtitle,
                      style: TextStyle(
                        color: visuals.textColor.withValues(alpha: 0.82),
                        fontSize: 12.5,
                        height: 1.35,
                      ),
                    ),
                  ],
                ),
              ),
              if (widget.showRefreshButton)
                IconButton(
                  onPressed: () => _controller.refresh(),
                  icon: Icon(Icons.refresh_rounded, color: visuals.textColor),
                  tooltip: widget.isArabic ? 'تحديث الحالة' : 'Refresh status',
                ),
            ],
          ),
        );
      },
    );
  }

  _BackendStatusVisuals _buildVisuals(
    BackendConnectionStatus status, {
    required bool isArabic,
    required bool forDarkBackground,
  }) {
    switch (status) {
      case BackendConnectionStatus.online:
        return _BackendStatusVisuals(
          icon: Icons.cloud_done_rounded,
          title: isArabic ? 'الخادم متصل' : 'Backend online',
          subtitle: isArabic
              ? 'يمكنك استخدام تسجيل الدخول والدردشة الآن.'
              : 'Login and AI chat are ready to use.',
          accentColor: const Color(0xFF16A34A),
          backgroundColor: forDarkBackground
              ? const Color(0x3322C55E)
              : const Color(0xFFEAF9EF),
          borderColor: forDarkBackground
              ? const Color(0x5534D399)
              : const Color(0xFFC7EFD5),
          textColor: forDarkBackground ? Colors.white : const Color(0xFF14532D),
        );
      case BackendConnectionStatus.offline:
        return _BackendStatusVisuals(
          icon: Icons.cloud_off_rounded,
          title: isArabic ? 'الخادم غير متاح' : 'Backend unavailable',
          subtitle: isArabic
              ? 'شغّل الـ backend المحلي أو تحقق من عنوان API ثم حدّث الحالة.'
              : 'Start the local backend or verify the API URL, then refresh.',
          accentColor: const Color(0xFFDC2626),
          backgroundColor: forDarkBackground
              ? const Color(0x33F87171)
              : const Color(0xFFFDECEC),
          borderColor: forDarkBackground
              ? const Color(0x55FCA5A5)
              : const Color(0xFFF6CACA),
          textColor: forDarkBackground ? Colors.white : const Color(0xFF7F1D1D),
        );
      case BackendConnectionStatus.checking:
        return _BackendStatusVisuals(
          icon: Icons.sync_rounded,
          title: isArabic ? 'جارٍ فحص الخادم' : 'Checking backend',
          subtitle: isArabic
              ? 'نتحقق من توفر خدمة الـ backend الآن.'
              : 'Checking backend availability now.',
          accentColor: const Color(0xFF2563EB),
          backgroundColor: forDarkBackground
              ? const Color(0x33FFFFFF)
              : const Color(0xFFEEF4FF),
          borderColor: forDarkBackground
              ? const Color(0x55DBEAFE)
              : const Color(0xFFD7E7FF),
          textColor: forDarkBackground ? Colors.white : const Color(0xFF1D4ED8),
        );
      case BackendConnectionStatus.unknown:
        return _BackendStatusVisuals(
          icon: Icons.cloud_queue_rounded,
          title: isArabic ? 'حالة الخادم غير معروفة' : 'Backend status unknown',
          subtitle: isArabic
              ? 'لم يتم فحص اتصال الخادم بعد.'
              : 'The backend connection has not been checked yet.',
          accentColor: const Color(0xFFF59E0B),
          backgroundColor: forDarkBackground
              ? const Color(0x33FDE68A)
              : const Color(0xFFFFF7E8),
          borderColor: forDarkBackground
              ? const Color(0x55FDE68A)
              : const Color(0xFFFCE3A8),
          textColor: forDarkBackground ? Colors.white : const Color(0xFF92400E),
        );
    }
  }
}

class _BackendStatusVisuals {
  const _BackendStatusVisuals({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.accentColor,
    required this.backgroundColor,
    required this.borderColor,
    required this.textColor,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final Color accentColor;
  final Color backgroundColor;
  final Color borderColor;
  final Color textColor;
}
