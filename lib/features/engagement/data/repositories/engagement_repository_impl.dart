import '../../domain/models/engagement_feed.dart';
import '../../domain/models/notification_device_token.dart';
import '../../domain/models/notification_preferences.dart';
import '../../domain/models/notification_read_result.dart';
import '../../domain/models/student_engagement_profile.dart';
import '../../domain/models/notification_category_preference_update.dart';
import '../local/engagement_feed_cache.dart';
import '../remote/engagement_api_client.dart';
import 'engagement_repository.dart';

class EngagementRepositoryImpl implements EngagementRepository {
  EngagementRepositoryImpl({
    EngagementApiClient remote = const EngagementApiClient(),
    EngagementFeedCache? cache,
  }) : _remote = remote,
       _cacheFuture = cache == null
           ? EngagementFeedCache.open()
           : Future<EngagementFeedCache>.value(cache);

  final EngagementApiClient _remote;
  final Future<EngagementFeedCache> _cacheFuture;

  Future<EngagementFeedCache> get _cache async => _cacheFuture;

  Future<String?> currentUserId() {
    return _remote.currentUserId();
  }

  @override
  Future<EngagementFeed?> getCachedFeed({required String userId}) async {
    return (await _cache).readFeed(userId);
  }

  @override
  Future<int> generateNotifications({int limit = 20}) {
    return _remote.generateNotifications(limit: limit);
  }

  @override
  Future<EngagementFeed> getFeed({
    bool includeRead = false,
    int limit = 20,
    String? cursor,
  }) async {
    final feed = await _remote.getFeed(
      includeRead: includeRead,
      limit: limit,
      cursor: cursor,
    );
    final userId = await _remote.currentUserId();
    if (userId != null && userId.isNotEmpty) {
      await (await _cache).writeFeed(userId, feed);
    }
    return feed;
  }

  @override
  Future<NotificationReadResult> markNotificationRead(String notificationId) async {
    final result = await _remote.markNotificationRead(notificationId);
    final userId = await _remote.currentUserId();
    if (userId != null && userId.isNotEmpty) {
      final cache = await _cache;
      final cached = await cache.readFeed(userId);
      if (cached != null) {
        final updatedNotifications = cached.notifications
            .map(
              (item) => item.id == notificationId ? result.notification : item,
            )
            .toList(growable: false);
        await cache.writeFeed(
          userId,
          cached.copyWith(
            notifications: updatedNotifications,
            unreadCount: result.unreadCount,
          ),
        );
      }
    }
    return result;
  }

  @override
  Future<StudentEngagementProfile> getProfile() {
    return _remote.getProfile();
  }

  @override
  Future<StudentEngagementProfile> updateProfile({
    required String major,
    required String academicLevel,
    required String track,
    required List<String> interests,
  }) {
    return _remote.updateProfile(
      major: major,
      academicLevel: academicLevel,
      track: track,
      interests: interests,
    );
  }

  @override
  Future<NotificationPreferences> getNotificationPreferences() {
    return _remote.getNotificationPreferences();
  }

  @override
  Future<NotificationPreferences> updateNotificationPreferences({
    bool? enablePush,
    bool? enableInApp,
    List<NotificationCategoryPreferenceUpdate> categories = const [],
  }) async {
    final updated = await _remote.updateNotificationPreferences(
      enablePush: enablePush,
      enableInApp: enableInApp,
      categories: categories,
    );
    final userId = await _remote.currentUserId();
    if (userId != null && userId.isNotEmpty) {
      await (await _cache).writePreferences(userId, updated);
    }
    return updated;
  }

  @override
  Future<NotificationDeviceToken> registerDeviceToken({
    required String token,
    required String platform,
    String deviceName = '',
    String appVersion = '',
    String locale = '',
  }) {
    return _remote.registerDeviceToken(
      token: token,
      platform: platform,
      deviceName: deviceName,
      appVersion: appVersion,
      locale: locale,
    );
  }

  @override
  Future<void> deleteDeviceToken(String tokenId) {
    return _remote.deleteDeviceToken(tokenId);
  }

  @override
  Future<void> clearCachedFeed(String userId) async {
    await (await _cache).clearUser(userId);
  }
}
