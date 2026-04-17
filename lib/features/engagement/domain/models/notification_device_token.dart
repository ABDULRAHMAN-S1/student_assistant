class NotificationDeviceToken {
  const NotificationDeviceToken({
    required this.id,
    required this.platform,
    required this.deviceName,
    required this.appVersion,
    required this.locale,
    required this.isActive,
    this.lastRegisteredAt,
    this.lastSeenAt,
  });

  final String id;
  final String platform;
  final String deviceName;
  final String appVersion;
  final String locale;
  final bool isActive;
  final DateTime? lastRegisteredAt;
  final DateTime? lastSeenAt;
}
