import 'package:hive_flutter/hive_flutter.dart';

import '../../../../app/local_encryption_key_provider.dart';
import '../../domain/models/engagement_feed.dart';
import '../../domain/models/engagement_feed_page.dart';
import '../../domain/models/notification_item.dart';
import '../../domain/models/notification_preferences.dart';
import '../../domain/models/notification_route.dart';
import '../../domain/models/suggestion_item.dart';

class EngagementFeedCache {
  const EngagementFeedCache();

  static const String boxName = 'engagement_feed';
  static const String _feedPrefix = 'feed:';
  static const String _preferencesPrefix = 'preferences:';

  static Future<Box> _openBox() async {
    if (!Hive.isBoxOpen(boxName)) {
      await _openEncryptedBox(boxName);
    }
    return Hive.box(boxName);
  }

  static Future<EngagementFeedCache> open() async {
    await _openBox();
    return const EngagementFeedCache();
  }

  static Future<void> ensureInitialized() async {
    await _openBox();
  }

  static Future<void> _openEncryptedBox(String name) async {
    final encryptionKey = await LocalEncryptionKeyProvider.instance.getKey();
    try {
      await Hive.openBox(name, encryptionCipher: HiveAesCipher(encryptionKey));
    } catch (error) {
      final message = error.toString().toLowerCase();
      if (message.contains('lock failed') ||
          message.contains('being used by another process') ||
          message.contains('cannot delete file')) {
        rethrow;
      }
      await Hive.deleteBoxFromDisk(name);
      await Hive.openBox(name, encryptionCipher: HiveAesCipher(encryptionKey));
    }
  }

  Future<EngagementFeed?> readFeed(String userId) async {
    final box = await _openBox();
    final raw = box.get('$_feedPrefix$userId');
    if (raw is! Map) {
      return null;
    }
    return _decodeFeed(Map<String, dynamic>.from(raw));
  }

  Future<void> writeFeed(String userId, EngagementFeed feed) {
    return _openBox()
        .then((box) => box.put('$_feedPrefix$userId', _encodeFeed(feed)));
  }

  Future<NotificationPreferences?> readPreferences(String userId) async {
    final box = await _openBox();
    final raw = box.get('$_preferencesPrefix$userId');
    if (raw is! Map) {
      return null;
    }
    return _decodePreferences(Map<String, dynamic>.from(raw));
  }

  Future<void> writePreferences(
    String userId,
    NotificationPreferences preferences,
  ) {
    return _openBox().then(
      (box) => box.put(
        '$_preferencesPrefix$userId',
        _encodePreferences(preferences),
      ),
    );
  }

  Future<void> clearUser(String userId) async {
    final box = await _openBox();
    await box.delete('$_feedPrefix$userId');
    await box.delete('$_preferencesPrefix$userId');
  }

  Map<String, dynamic> _encodeFeed(EngagementFeed feed) {
    return {
      'notifications': feed.notifications.map(_encodeNotification).toList(),
      'suggestions': feed.suggestions.map(_encodeSuggestion).toList(),
      'unreadCount': feed.unreadCount,
      'generatedCount': feed.generatedCount,
      'page': {
        'hasMore': feed.page.hasMore,
        'nextCursor': feed.page.nextCursor,
      },
      'cachedAt': feed.cachedAt?.toIso8601String(),
    };
  }

  EngagementFeed _decodeFeed(Map<String, dynamic> raw) {
    final notificationsRaw = raw['notifications'];
    final suggestionsRaw = raw['suggestions'];
    return EngagementFeed(
      notifications: notificationsRaw is List
          ? notificationsRaw
                .whereType<Map>()
                .map((item) => _decodeNotification(Map<String, dynamic>.from(item)))
                .toList(growable: false)
          : const [],
      suggestions: suggestionsRaw is List
          ? suggestionsRaw
                .whereType<Map>()
                .map((item) => _decodeSuggestion(Map<String, dynamic>.from(item)))
                .toList(growable: false)
          : const [],
      unreadCount: (raw['unreadCount'] as num?)?.toInt() ?? 0,
      generatedCount: (raw['generatedCount'] as num?)?.toInt() ?? 0,
      page: EngagementFeedPage(
        hasMore: raw['page'] is Map
            ? Map<String, dynamic>.from(raw['page'] as Map)['hasMore'] == true
            : false,
        nextCursor: raw['page'] is Map
            ? (Map<String, dynamic>.from(raw['page'] as Map)['nextCursor']
                  ?.toString())
            : null,
      ),
      cachedAt: _asDateTime(raw['cachedAt']),
    );
  }

  Map<String, dynamic> _encodeNotification(NotificationItem item) {
    return {
      'id': item.id,
      'category': item.category,
      'title': item.title,
      'message': item.message,
      'isRead': item.isRead,
      'priority': item.priority,
      'createdAt': item.createdAt?.toIso8601String(),
      'readAt': item.readAt?.toIso8601String(),
      'metadata': item.metadata == null
          ? null
          : {
              'contentType': item.metadata!.contentType,
              'matchReasons': item.metadata!.matchReasons,
              'linkUrl': item.metadata!.linkUrl,
              'route': item.metadata!.route == null
                  ? null
                  : {
                      'type': item.metadata!.route!.type.name,
                      'payload': item.metadata!.route!.payload,
                    },
            },
    };
  }

  NotificationItem _decodeNotification(Map<String, dynamic> raw) {
    final metadataRaw = raw['metadata'];
    return NotificationItem(
      id: (raw['id'] ?? '').toString(),
      category: (raw['category'] ?? '').toString(),
      title: (raw['title'] ?? '').toString(),
      message: (raw['message'] ?? '').toString(),
      isRead: raw['isRead'] == true,
      priority: (raw['priority'] as num?)?.toInt() ?? 0,
      createdAt: _asDateTime(raw['createdAt']),
      readAt: _asDateTime(raw['readAt']),
      metadata: metadataRaw is Map
          ? NotificationMetadata(
              contentType: metadataRaw['contentType']?.toString(),
              matchReasons: _stringList(metadataRaw['matchReasons']),
              linkUrl: metadataRaw['linkUrl']?.toString(),
              route: _decodeRoute(
                metadataRaw['route'] is Map
                    ? Map<String, dynamic>.from(metadataRaw['route'] as Map)
                    : null,
              ),
            )
          : null,
    );
  }

  Map<String, dynamic> _encodeSuggestion(SuggestionItem item) {
    return {
      'id': item.id,
      'contentType': item.contentType,
      'title': item.title,
      'body': item.body,
      'createdAt': item.createdAt?.toIso8601String(),
      'startsAt': item.startsAt?.toIso8601String(),
      'endsAt': item.endsAt?.toIso8601String(),
      'linkUrl': item.linkUrl,
      'tags': item.tags,
      'matchReasons': item.matchReasons,
    };
  }

  SuggestionItem _decodeSuggestion(Map<String, dynamic> raw) {
    return SuggestionItem(
      id: (raw['id'] ?? '').toString(),
      contentType: (raw['contentType'] ?? '').toString(),
      title: (raw['title'] ?? '').toString(),
      body: (raw['body'] ?? '').toString(),
      createdAt: _asDateTime(raw['createdAt']),
      startsAt: _asDateTime(raw['startsAt']),
      endsAt: _asDateTime(raw['endsAt']),
      linkUrl: raw['linkUrl']?.toString(),
      tags: _stringList(raw['tags']),
      matchReasons: _stringList(raw['matchReasons']),
    );
  }

  Map<String, dynamic> _encodePreferences(NotificationPreferences preferences) {
    return {
      'enablePush': preferences.enablePush,
      'enableInApp': preferences.enableInApp,
      'updatedAt': preferences.updatedAt?.toIso8601String(),
      'categories': preferences.categories
          .map(
            (item) => {
              'category': item.category,
              'enablePush': item.enablePush,
              'enableInApp': item.enableInApp,
              'muted': item.muted,
            },
          )
          .toList(),
    };
  }

  NotificationPreferences _decodePreferences(Map<String, dynamic> raw) {
    final categoriesRaw = raw['categories'];
    return NotificationPreferences(
      enablePush: raw['enablePush'] != false,
      enableInApp: raw['enableInApp'] != false,
      updatedAt: _asDateTime(raw['updatedAt']),
      categories: categoriesRaw is List
          ? categoriesRaw
                .whereType<Map>()
                .map(
                  (item) => NotificationCategoryPreference(
                    category: (item['category'] ?? '').toString(),
                    enablePush: item['enablePush'] != false,
                    enableInApp: item['enableInApp'] != false,
                    muted: item['muted'] == true,
                  ),
                )
                .toList(growable: false)
          : const [],
    );
  }

  NotificationRoute? _decodeRoute(Map<String, dynamic>? raw) {
    if (raw == null) {
      return null;
    }
    final type = NotificationRouteTypeX.fromString(raw['type']?.toString());
    if (type == null) {
      return null;
    }
    return NotificationRoute(
      type: type,
      payload: raw['payload'] is Map
          ? Map<String, dynamic>.from(raw['payload'] as Map)
          : const <String, dynamic>{},
    );
  }

  DateTime? _asDateTime(Object? value) {
    final text = value?.toString().trim();
    if (text == null || text.isEmpty) {
      return null;
    }
    return DateTime.tryParse(text);
  }

  List<String> _stringList(Object? value) {
    if (value is! List) {
      return const [];
    }
    return value.map((item) => item.toString()).toList(growable: false);
  }
}
