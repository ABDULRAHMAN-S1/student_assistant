import 'package:flutter_test/flutter_test.dart';
import 'package:student_assistant/features/engagement/data/repositories/engagement_repository.dart';
import 'package:student_assistant/features/engagement/domain/models/engagement_feed.dart';
import 'package:student_assistant/features/engagement/domain/models/engagement_feed_page.dart';
import 'package:student_assistant/features/engagement/domain/models/notification_category_preference_update.dart';
import 'package:student_assistant/features/engagement/domain/models/notification_item.dart';
import 'package:student_assistant/features/engagement/domain/models/notification_preferences.dart';
import 'package:student_assistant/features/engagement/domain/models/notification_read_result.dart';
import 'package:student_assistant/features/engagement/domain/models/student_engagement_profile.dart';
import 'package:student_assistant/features/engagement/presentation/controllers/engagement_feed_controller.dart';

class _FakeRepository implements EngagementRepository {
  _FakeRepository({
    required this.initialFeed,
    this.nextFeed,
    this.readResult,
  });

  final EngagementFeed initialFeed;
  final EngagementFeed? nextFeed;
  final NotificationReadResult? readResult;

  int feedCalls = 0;
  String? lastCursor;

  @override
  Future<int> generateNotifications({int limit = 20}) async => 0;

  @override
  Future<EngagementFeed?> getCachedFeed({required String userId}) async {
    return initialFeed;
  }

  @override
  Future<EngagementFeed> getFeed({
    bool includeRead = false,
    int limit = 20,
    String? cursor,
  }) async {
    feedCalls += 1;
    lastCursor = cursor;
    if (cursor != null && nextFeed != null) {
      return nextFeed!;
    }
    return initialFeed;
  }

  @override
  Future<NotificationReadResult> markNotificationRead(String notificationId) async {
    return readResult ??
        NotificationReadResult(
          notification: initialFeed.notifications.first.copyWith(isRead: true),
          unreadCount: 0,
          status: 'ok',
        );
  }

  @override
  Future<NotificationPreferences> getNotificationPreferences() async =>
      NotificationPreferences.empty;

  @override
  Future<NotificationPreferences> updateNotificationPreferences({
    bool? enablePush,
    bool? enableInApp,
    List<NotificationCategoryPreferenceUpdate> categories = const [],
  }) async {
    return NotificationPreferences(
      enablePush: enablePush ?? true,
      enableInApp: enableInApp ?? true,
      categories: categories
          .map(
            (item) => NotificationCategoryPreference(
              category: item.category,
              enablePush: item.enablePush ?? true,
              enableInApp: item.enableInApp ?? true,
              muted: item.muted ?? false,
            ),
          )
          .toList(growable: false),
    );
  }

  @override
  Future<Never> registerDeviceToken({
    required String token,
    required String platform,
    String deviceName = '',
    String appVersion = '',
    String locale = '',
  }) {
    throw UnimplementedError();
  }

  @override
  Future<void> deleteDeviceToken(String deviceTokenId) async {}

  @override
  Future<void> clearCachedFeed(String userId) async {}

  @override
  Future<StudentEngagementProfile> getProfile() async =>
      StudentEngagementProfile.empty;

  @override
  Future<StudentEngagementProfile> updateProfile({
    required String major,
    required String academicLevel,
    required String track,
    required List<String> interests,
  }) async {
    return StudentEngagementProfile(
      major: major,
      academicLevel: academicLevel,
      track: track,
      interests: interests,
    );
  }
}

NotificationItem _notification(String id, {bool isRead = false}) {
  return NotificationItem(
    id: id,
    category: 'live_event',
    title: 'Notification $id',
    message: 'Body $id',
    isRead: isRead,
    priority: 5,
    createdAt: DateTime.parse('2026-04-17T10:00:00Z'),
    metadata: const NotificationMetadata(),
  );
}

void main() {
  test('loadInitial loads first page', () async {
    final repository = _FakeRepository(
      initialFeed: EngagementFeed(
        notifications: [_notification('1')],
        suggestions: const [],
        unreadCount: 1,
        page: const EngagementFeedPage(hasMore: true, nextCursor: 'cursor-1'),
      ),
    );
    final controller = EngagementFeedController(repository: repository);

    await controller.loadInitial();

    expect(controller.data?.notifications.length, 1);
    expect(controller.unreadCount, 1);
    expect(repository.feedCalls, 1);
  });

  test('loadMore merges next page and preserves cursor', () async {
    final repository = _FakeRepository(
      initialFeed: EngagementFeed(
        notifications: [_notification('1')],
        suggestions: const [],
        unreadCount: 2,
        page: const EngagementFeedPage(hasMore: true, nextCursor: 'cursor-1'),
      ),
      nextFeed: EngagementFeed(
        notifications: [_notification('2')],
        suggestions: const [],
        unreadCount: 2,
        page: const EngagementFeedPage(hasMore: false),
      ),
    );
    final controller = EngagementFeedController(repository: repository);

    await controller.loadInitial();
    await controller.loadMore();

    expect(repository.lastCursor, 'cursor-1');
    expect(controller.data?.notifications.map((item) => item.id), ['1', '2']);
    expect(controller.data?.page.hasMore, false);
  });

  test('markAsRead updates item instead of removing it', () async {
    final repository = _FakeRepository(
      initialFeed: EngagementFeed(
        notifications: [_notification('1')],
        suggestions: const [],
        unreadCount: 1,
      ),
      readResult: NotificationReadResult(
        notification: _notification('1', isRead: true),
        unreadCount: 0,
        status: 'ok',
      ),
    );
    final controller = EngagementFeedController(repository: repository);

    await controller.loadInitial();
    await controller.markAsRead('1');

    expect(controller.data?.notifications.length, 1);
    expect(controller.data?.notifications.first.isRead, true);
    expect(controller.unreadCount, 0);
  });
}
