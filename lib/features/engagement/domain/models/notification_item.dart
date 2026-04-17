import 'notification_route.dart';

class NotificationMetadata {
  const NotificationMetadata({
    this.contentType,
    this.matchReasons = const [],
    this.linkUrl,
    this.route,
  });

  final String? contentType;
  final List<String> matchReasons;
  final String? linkUrl;
  final NotificationRoute? route;

  NotificationMetadata copyWith({
    String? contentType,
    List<String>? matchReasons,
    String? linkUrl,
    NotificationRoute? route,
  }) {
    return NotificationMetadata(
      contentType: contentType ?? this.contentType,
      matchReasons: matchReasons ?? this.matchReasons,
      linkUrl: linkUrl ?? this.linkUrl,
      route: route ?? this.route,
    );
  }
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
    this.readAt,
    this.metadata,
  });

  final String id;
  final String category;
  final String title;
  final String message;
  final bool isRead;
  final int priority;
  final DateTime? createdAt;
  final DateTime? readAt;
  final NotificationMetadata? metadata;

  NotificationItem copyWith({
    String? id,
    String? category,
    String? title,
    String? message,
    bool? isRead,
    int? priority,
    DateTime? createdAt,
    DateTime? readAt,
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
      readAt: readAt ?? this.readAt,
      metadata: metadata ?? this.metadata,
    );
  }
}
