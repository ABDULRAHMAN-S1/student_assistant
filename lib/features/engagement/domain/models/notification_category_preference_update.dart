class NotificationCategoryPreferenceUpdate {
  const NotificationCategoryPreferenceUpdate({
    required this.category,
    this.enablePush,
    this.enableInApp,
    this.muted,
  });

  final String category;
  final bool? enablePush;
  final bool? enableInApp;
  final bool? muted;

  Map<String, dynamic> toJson() {
    return {
      'category': category,
      if (enablePush != null) 'enable_push': enablePush,
      if (enableInApp != null) 'enable_in_app': enableInApp,
      if (muted != null) 'muted': muted,
    };
  }
}
