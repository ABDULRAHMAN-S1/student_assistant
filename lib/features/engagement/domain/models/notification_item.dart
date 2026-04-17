class NotificationMetadata {
  const NotificationMetadata({
    this.contentType,
    this.matchReasons = const [],
    this.linkUrl,
  });

  final String? contentType;
  final List<String> matchReasons;
  final String? linkUrl;
}

class NotificationItem {
  const NotificationItem({
    required this.id,
    required this.category,
    required this.title,
    required this.message,
    required this.isRead,
    required this.priority,
    required this.createdAt,
    this.metadata,
  });

  final String id;
  final String category;
  final String title;
  final String message;
  final bool isRead;
  final int priority;
  final DateTime? createdAt;
  final NotificationMetadata? metadata;

  NotificationItem copyWith({
    String? id,
    String? category,
    String? title,
    String? message,
    bool? isRead,
    int? priority,
    DateTime? createdAt,
    NotificationMetadata? metadata,
  }) {
    return NotificationItem(
      id: id ?? this.id,
      category: category ?? this.category,
      title: title ?? this.title,
      message: message ?? this.message,
      isRead: isRead ?? this.isRead,
      priority: priority ?? this.priority,
      createdAt: createdAt ?? this.createdAt,
      metadata: metadata ?? this.metadata,
    );
  }
}
