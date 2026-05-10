enum NotificationRouteType {
  course,
  event,
  review,
  chat,
  search,
  externalUrl,
  engagement,
}

extension NotificationRouteTypeX on NotificationRouteType {
  static NotificationRouteType? fromString(String? raw) {
    switch ((raw ?? '').trim().toLowerCase()) {
      case 'course':
        return NotificationRouteType.course;
      case 'event':
        return NotificationRouteType.event;
      case 'review':
        return NotificationRouteType.review;
      case 'chat':
        return NotificationRouteType.chat;
      case 'search':
        return NotificationRouteType.search;
      case 'external_url':
        return NotificationRouteType.externalUrl;
      case 'engagement':
        return NotificationRouteType.engagement;
    }
    return null;
  }

  String get wireValue {
    switch (this) {
      case NotificationRouteType.course:
        return 'course';
      case NotificationRouteType.event:
        return 'event';
      case NotificationRouteType.review:
        return 'review';
      case NotificationRouteType.chat:
        return 'chat';
      case NotificationRouteType.search:
        return 'search';
      case NotificationRouteType.externalUrl:
        return 'external_url';
      case NotificationRouteType.engagement:
        return 'engagement';
    }
  }
}

class NotificationRoute {
  const NotificationRoute({
    required this.type,
    this.payload = const <String, dynamic>{},
  });

  final NotificationRouteType type;
  final Map<String, dynamic> payload;

  NotificationRoute copyWith({
    NotificationRouteType? type,
    Map<String, dynamic>? payload,
  }) {
    return NotificationRoute(
      type: type ?? this.type,
      payload: payload ?? this.payload,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'type': type.wireValue,
      'payload': payload,
    };
  }

  factory NotificationRoute.fromJson(Map<String, dynamic> json) {
    return NotificationRoute(
      type: NotificationRouteTypeX.fromString(json['type']?.toString()) ??
          NotificationRouteType.engagement,
      payload: json['payload'] is Map
          ? Map<String, dynamic>.from(json['payload'] as Map)
          : const <String, dynamic>{},
    );
  }

  String displayLabel({required bool isArabic}) {
    switch (type) {
      case NotificationRouteType.course:
        return isArabic ? 'الانتقال إلى الدورات' : 'Open courses';
      case NotificationRouteType.event:
        return isArabic ? 'الانتقال إلى الفعاليات' : 'Open events';
      case NotificationRouteType.review:
        return isArabic ? 'الانتقال إلى الآراء' : 'Open reviews';
      case NotificationRouteType.chat:
        return isArabic ? 'فتح الدردشة' : 'Open AI chat';
      case NotificationRouteType.search:
        return isArabic ? 'فتح البحث' : 'Open search';
      case NotificationRouteType.externalUrl:
        return isArabic ? 'فتح الرابط' : 'Open link';
      case NotificationRouteType.engagement:
        return isArabic ? 'فتح الإشعارات' : 'Open notifications';
    }
  }
}
