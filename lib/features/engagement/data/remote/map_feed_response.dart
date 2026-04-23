import '../../domain/models/engagement_feed.dart';
import '../../domain/models/engagement_feed_page.dart';
import '../../domain/models/notification_device_token.dart';
import '../../domain/models/notification_item.dart';
import '../../domain/models/notification_preferences.dart';
import '../../domain/models/notification_read_result.dart';
import '../../domain/models/notification_route.dart';
import '../../domain/models/student_engagement_profile.dart';
import '../../domain/models/suggestion_item.dart';

EngagementFeed mapFeedResponse(Map<String, dynamic> payload) {
  final notificationsRaw = payload['notifications'];
  final suggestionsRaw = payload['suggestions'];
  final notifications = notificationsRaw is List
      ? notificationsRaw
            .whereType<Map<String, dynamic>>()
            .map(_mapNotification)
            .toList(growable: false)
      : const <NotificationItem>[];
  final suggestions = suggestionsRaw is List
      ? suggestionsRaw
            .whereType<Map<String, dynamic>>()
            .map(_mapSuggestion)
            .toList(growable: false)
      : const <SuggestionItem>[];

  final unreadCount =
      (payload['unread_count'] as num?)?.toInt() ??
      notifications.where((item) => !item.isRead).length;
  final generatedCount = (payload['generated_count'] as num?)?.toInt() ?? 0;
  final pageRaw = payload['page'];
  final page = pageRaw is Map<String, dynamic>
      ? EngagementFeedPage(
          hasMore: pageRaw['has_more'] == true,
          nextCursor: _asStringOrNull(pageRaw['next_cursor']),
        )
      : const EngagementFeedPage();

  return EngagementFeed(
    notifications: notifications,
    suggestions: suggestions,
    unreadCount: unreadCount,
    generatedCount: generatedCount,
    page: page,
  );
}

StudentEngagementProfile mapEngagementProfile(Map<String, dynamic> json) {
  return StudentEngagementProfile(
    major: (json['major'] ?? '').toString(),
    academicLevel: (json['academic_level'] ?? '').toString(),
    track: (json['track'] ?? '').toString(),
    interests: _stringList(json['interests']),
    updatedAt: _asDateTime(json['updated_at']),
  );
}

NotificationItem _mapNotification(Map<String, dynamic> json) {
  final metadataRaw = json['metadata'];
  final metadata = metadataRaw is Map<String, dynamic>
      ? NotificationMetadata(
          contentType: _asStringOrNull(metadataRaw['content_type']),
          matchReasons: _stringList(metadataRaw['match_reasons']),
          linkUrl: _asStringOrNull(metadataRaw['link_url']),
          route: _mapNotificationRoute(metadataRaw['route']),
        )
      : null;

  return NotificationItem(
    id: (json['id'] ?? '').toString(),
    category: (json['category'] ?? '').toString(),
    title: (json['title'] ?? '').toString(),
    message: (json['message'] ?? '').toString(),
    isRead: json['is_read'] == true,
    priority: (json['priority'] as num?)?.toInt() ?? 0,
    createdAt: _asDateTime(json['created_at']),
    readAt: _asDateTime(json['read_at']),
    metadata: metadata,
  );
}

NotificationReadResult mapNotificationReadResult(Map<String, dynamic> json) {
  final notificationRaw = json['notification'];
  return NotificationReadResult(
    notification: notificationRaw is Map<String, dynamic>
        ? _mapNotification(notificationRaw)
        : null,
    unreadCount: (json['unread_count'] as num?)?.toInt() ?? 0,
    status: (json['status'] ?? 'ok').toString(),
  );
}

NotificationReadResult mapNotificationReadResponse(
  Map<String, dynamic> payload,
) {
  return mapNotificationReadResult(payload);
}

NotificationPreferences mapNotificationPreferences(Map<String, dynamic> json) {
  final categoriesRaw = json['categories'];
  return NotificationPreferences(
    enablePush: json['enable_push'] != false,
    enableInApp: json['enable_in_app'] != false,
    updatedAt: _asDateTime(json['updated_at']),
    categories: categoriesRaw is List
        ? categoriesRaw
              .whereType<Map<String, dynamic>>()
              .map(NotificationCategoryPreference.fromJson)
              .toList(growable: false)
        : const <NotificationCategoryPreference>[],
  );
}

NotificationDeviceToken mapNotificationDeviceToken(Map<String, dynamic> json) {
  return NotificationDeviceToken(
    id: (json['id'] ?? '').toString(),
    platform: (json['platform'] ?? '').toString(),
    deviceName: (json['device_name'] ?? '').toString(),
    appVersion: (json['app_version'] ?? '').toString(),
    locale: (json['locale'] ?? '').toString(),
    isActive: json['is_active'] != false,
    lastRegisteredAt: _asDateTime(json['last_registered_at']),
    lastSeenAt: _asDateTime(json['last_seen_at']),
  );
}

NotificationRoute? _mapNotificationRoute(Object? raw) {
  if (raw is! Map<String, dynamic>) {
    return null;
  }
  final type = _asStringOrNull(raw['type']);
  if (type == null) {
    return null;
  }
  final payload = raw['payload'];
  return NotificationRoute(
    type:
        NotificationRouteTypeX.tryParse(type) ??
        NotificationRouteType.engagement,
    payload: payload is Map<String, dynamic>
        ? Map<String, dynamic>.from(payload)
        : const <String, dynamic>{},
  );
}

SuggestionItem _mapSuggestion(Map<String, dynamic> json) {
  return SuggestionItem(
    id: (json['id'] ?? '').toString(),
    contentType: (json['content_type'] ?? '').toString(),
    title: (json['title'] ?? '').toString(),
    body:
        _asStringOrNull(json['body']) ??
        _asStringOrNull(json['body_preview']) ??
        '',
    createdAt:
        _asDateTime(json['created_at']) ?? _asDateTime(json['starts_at']),
    startsAt: _asDateTime(json['starts_at']),
    endsAt: _asDateTime(json['ends_at']),
    linkUrl: _asStringOrNull(json['link_url']),
    tags: _stringList(json['tags']),
    matchReasons: _stringList(json['match_reasons']),
  );
}

DateTime? _asDateTime(Object? value) {
  final text = _asStringOrNull(value);
  if (text == null || text.isEmpty) {
    return null;
  }
  return DateTime.tryParse(text);
}

String? _asStringOrNull(Object? value) {
  if (value == null) {
    return null;
  }
  final text = value.toString().trim();
  return text.isEmpty ? null : text;
}

List<String> _stringList(Object? value) {
  if (value is! List) {
    return const <String>[];
  }
  return value
      .map((item) => item.toString().trim())
      .where((item) => item.isNotEmpty)
      .toList(growable: false);
}
