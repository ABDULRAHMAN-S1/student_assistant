class NotificationCategoryPreference {
  const NotificationCategoryPreference({
    required this.category,
    required this.enablePush,
    required this.enableInApp,
    required this.muted,
  });

  final String category;
  final bool enablePush;
  final bool enableInApp;
  final bool muted;

  NotificationCategoryPreference copyWith({
    String? category,
    bool? enablePush,
    bool? enableInApp,
    bool? muted,
  }) {
    return NotificationCategoryPreference(
      category: category ?? this.category,
      enablePush: enablePush ?? this.enablePush,
      enableInApp: enableInApp ?? this.enableInApp,
      muted: muted ?? this.muted,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category,
      'enable_push': enablePush,
      'enable_in_app': enableInApp,
      'muted': muted,
    };
  }

  factory NotificationCategoryPreference.fromJson(Map<String, dynamic> json) {
    return NotificationCategoryPreference(
      category: (json['category'] ?? '').toString(),
      enablePush: json['enable_push'] != false,
      enableInApp: json['enable_in_app'] != false,
      muted: json['muted'] == true,
    );
  }
}

class NotificationPreferences {
  const NotificationPreferences({
    required this.enablePush,
    required this.enableInApp,
    required this.categories,
    this.updatedAt,
  });

  final bool enablePush;
  final bool enableInApp;
  final List<NotificationCategoryPreference> categories;
  final DateTime? updatedAt;

  NotificationPreferences copyWith({
    bool? enablePush,
    bool? enableInApp,
    List<NotificationCategoryPreference>? categories,
    DateTime? updatedAt,
  }) {
    return NotificationPreferences(
      enablePush: enablePush ?? this.enablePush,
      enableInApp: enableInApp ?? this.enableInApp,
      categories: categories ?? this.categories,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'enable_push': enablePush,
      'enable_in_app': enableInApp,
      'categories': categories.map((item) => item.toJson()).toList(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  factory NotificationPreferences.fromJson(Map<String, dynamic> json) {
    final categoriesRaw = json['categories'];
    return NotificationPreferences(
      enablePush: json['enable_push'] != false,
      enableInApp: json['enable_in_app'] != false,
      categories: categoriesRaw is List
          ? categoriesRaw
                .whereType<Map>()
                .map(
                  (item) => NotificationCategoryPreference.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .toList(growable: false)
          : const <NotificationCategoryPreference>[],
      updatedAt: _parseDateTime(json['updated_at']),
    );
  }

  static const empty = NotificationPreferences(
    enablePush: true,
    enableInApp: true,
    categories: <NotificationCategoryPreference>[],
  );
}

DateTime? _parseDateTime(Object? value) {
  final text = value?.toString().trim() ?? '';
  if (text.isEmpty) {
    return null;
  }
  return DateTime.tryParse(text);
}
