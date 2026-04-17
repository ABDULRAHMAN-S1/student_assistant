import '../../domain/models/engagement_feed.dart';
import '../../domain/models/notification_category_preference_update.dart';
import '../../domain/models/notification_device_token.dart';
import '../../domain/models/notification_preferences.dart';
import '../../domain/models/notification_read_result.dart';
import '../../domain/models/student_engagement_profile.dart';

abstract class EngagementRepository {
  Future<EngagementFeed?> getCachedFeed({required String userId});

  Future<int> generateNotifications({int limit = 20});

  Future<EngagementFeed> getFeed({
    bool includeRead = false,
    int limit = 20,
    String? cursor,
  });

  Future<NotificationReadResult> markNotificationRead(String notificationId);

  Future<NotificationPreferences> getNotificationPreferences();

  Future<NotificationPreferences> updateNotificationPreferences({
    bool? enablePush,
    bool? enableInApp,
    List<NotificationCategoryPreferenceUpdate> categories = const [],
  });

  Future<NotificationDeviceToken> registerDeviceToken({
    required String token,
    required String platform,
    String deviceName = '',
    String appVersion = '',
    String locale = '',
  });

  Future<void> deleteDeviceToken(String deviceTokenId);

  Future<StudentEngagementProfile> getProfile();

  Future<StudentEngagementProfile> updateProfile({
    required String major,
    required String academicLevel,
    required String track,
    required List<String> interests,
  });

  Future<void> clearCachedFeed(String userId);
}
