import '../../domain/models/engagement_feed.dart';
import '../../domain/models/student_engagement_profile.dart';

abstract class EngagementRepository {
  Future<int> generateNotifications({int limit = 20});

  Future<EngagementFeed> getFeed({bool includeRead = false, int limit = 20});

  Future<void> markNotificationRead(String notificationId);

  Future<StudentEngagementProfile> getProfile();

  Future<StudentEngagementProfile> updateProfile({
    required String major,
    required String academicLevel,
    required String track,
    required List<String> interests,
  });
}
