import 'package:flutter/material.dart';

import '../../domain/models/suggestion_item.dart';
import '../controllers/engagement_feed_controller.dart';
import 'feed_empty_state.dart';
import 'feed_error_state.dart';
import 'notification_card.dart';
import 'suggestion_card.dart';

class EngagementFeedSection extends StatelessWidget {
  const EngagementFeedSection({
    super.key,
    required this.controller,
    required this.isArabic,
    required this.onMarkAsRead,
    required this.onOpenSuggestion,
    required this.onOpenProfile,
  });

  final EngagementFeedController controller;
  final bool isArabic;
  final Future<void> Function(String notificationId) onMarkAsRead;
  final void Function(SuggestionItem item) onOpenSuggestion;
  final VoidCallback onOpenProfile;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) {
        return Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: const Color(0xFFFFFFFF),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0x1A000000)),
            boxShadow: const [
              BoxShadow(
                color: Color(0x0F000000),
                blurRadius: 7,
                offset: Offset(0, 4),
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildHeader(context),
              const SizedBox(height: 12),
              if (controller.isLoading) _buildSkeleton(),
              if (!controller.isLoading && controller.errorMessage != null)
                FeedErrorState(
                  message: controller.errorMessage!,
                  isArabic: isArabic,
                  onRetry: controller.refresh,
                ),
              if (!controller.isLoading &&
                  controller.errorMessage == null &&
                  (controller.data?.notifications.isEmpty ?? true) &&
                  (controller.data?.suggestions.isEmpty ?? true))
                FeedEmptyState(isArabic: isArabic),
              if (!controller.isLoading &&
                  controller.errorMessage == null &&
                  controller.data != null &&
                  ((controller.data!.notifications.isNotEmpty) ||
                      (controller.data!.suggestions.isNotEmpty)))
                _buildLoadedState(context),
            ],
          ),
        );
      },
    );
  }

  Widget _buildHeader(BuildContext context) {
    return Row(
      children: [
        Container(
          width: 44,
          height: 44,
          decoration: BoxDecoration(
            color: const Color(0xFF2F6CFF).withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(14),
          ),
          child: const Icon(
            Icons.notifications_active_outlined,
            color: Color(0xFF2F6CFF),
            size: 22,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                isArabic ? 'المحتوى الحي والتنبيهات' : 'Engagement Feed',
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w900,
                  color: Color(0xFF030213),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                isArabic
                    ? 'تنبيهات موجهة واقتراحات حسب ملفك الدراسي'
                    : 'Personalized alerts and suggestions for your profile',
                style: const TextStyle(
                  fontSize: 13,
                  color: Color(0xFF717182),
                  height: 1.45,
                ),
              ),
            ],
          ),
        ),
        IconButton(
          onPressed: controller.isRefreshing ? null : controller.refresh,
          icon: controller.isRefreshing
              ? const SizedBox(
                  width: 18,
                  height: 18,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Icon(Icons.refresh),
        ),
      ],
    );
  }

  Widget _buildSkeleton() {
    return Column(
      children: List.generate(
        3,
        (index) => Container(
          height: 86,
          margin: const EdgeInsets.only(bottom: 10),
          decoration: BoxDecoration(
            color: const Color(0xFFF3F4F6),
            borderRadius: BorderRadius.circular(14),
          ),
        ),
      ),
    );
  }

  Widget _buildLoadedState(BuildContext context) {
    final feed = controller.data!;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (feed.notifications.isNotEmpty) ...[
          Text(
            isArabic ? 'التنبيهات' : 'Notifications',
            style: const TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w800,
              color: Color(0xFF030213),
            ),
          ),
          const SizedBox(height: 10),
          ...feed.notifications.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: NotificationCard(
                item: item,
                isArabic: isArabic,
                marking: controller.isMarkingRead,
                onMarkAsRead: () => onMarkAsRead(item.id),
              ),
            ),
          ),
          const SizedBox(height: 4),
        ],
        if (feed.suggestions.isNotEmpty) ...[
          Text(
            isArabic ? 'مقترحات لك' : 'Suggestions for You',
            style: const TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w800,
              color: Color(0xFF030213),
            ),
          ),
          const SizedBox(height: 10),
          ...feed.suggestions.map(
            (item) => Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: SuggestionCard(
                item: item,
                isArabic: isArabic,
                onOpen: () => onOpenSuggestion(item),
              ),
            ),
          ),
        ],
        const SizedBox(height: 4),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: onOpenProfile,
            icon: const Icon(Icons.person_outline),
            label: Text(
              isArabic
                  ? 'تحديث الملف التخصيصي'
                  : 'Update personalization profile',
            ),
          ),
        ),
      ],
    );
  }
}
