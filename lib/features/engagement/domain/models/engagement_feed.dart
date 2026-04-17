import 'notification_item.dart';
import 'suggestion_item.dart';

class EngagementFeed {
  const EngagementFeed({
    required this.notifications,
    required this.suggestions,
    this.unreadCount = 0,
    this.generatedCount = 0,
  });

  final List<NotificationItem> notifications;
  final List<SuggestionItem> suggestions;
  final int unreadCount;
  final int generatedCount;

  EngagementFeed copyWith({
    List<NotificationItem>? notifications,
    List<SuggestionItem>? suggestions,
    int? unreadCount,
    int? generatedCount,
  }) {
    return EngagementFeed(
      notifications: notifications ?? this.notifications,
      suggestions: suggestions ?? this.suggestions,
      unreadCount: unreadCount ?? this.unreadCount,
      generatedCount: generatedCount ?? this.generatedCount,
    );
  }
}
