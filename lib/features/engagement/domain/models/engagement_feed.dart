import 'notification_item.dart';
import 'engagement_feed_page.dart';
import 'suggestion_item.dart';

class EngagementFeed {
  const EngagementFeed({
    required this.notifications,
    required this.suggestions,
    this.page = const EngagementFeedPage(),
    this.unreadCount = 0,
    this.generatedCount = 0,
    this.cachedAt,
  });

  final List<NotificationItem> notifications;
  final List<SuggestionItem> suggestions;
  final EngagementFeedPage page;
  final int unreadCount;
  final int generatedCount;
  final DateTime? cachedAt;

  EngagementFeed copyWith({
    List<NotificationItem>? notifications,
    List<SuggestionItem>? suggestions,
    EngagementFeedPage? page,
    int? unreadCount,
    int? generatedCount,
    DateTime? cachedAt,
  }) {
    return EngagementFeed(
      notifications: notifications ?? this.notifications,
      suggestions: suggestions ?? this.suggestions,
      page: page ?? this.page,
      unreadCount: unreadCount ?? this.unreadCount,
      generatedCount: generatedCount ?? this.generatedCount,
      cachedAt: cachedAt ?? this.cachedAt,
    );
  }

  EngagementFeed mergePage(EngagementFeed nextPage) {
    final mergedNotifications = <NotificationItem>[
      ...notifications,
      ...nextPage.notifications.where(
        (candidate) => !notifications.any((item) => item.id == candidate.id),
      ),
    ];
    return copyWith(
      notifications: List<NotificationItem>.unmodifiable(mergedNotifications),
      suggestions: nextPage.suggestions.isNotEmpty ? nextPage.suggestions : suggestions,
      page: nextPage.page,
      unreadCount: nextPage.unreadCount,
      generatedCount: nextPage.generatedCount,
      cachedAt: nextPage.cachedAt ?? cachedAt,
    );
  }
}
