import 'package:flutter/material.dart';

import '../../domain/models/notification_item.dart';
import '../utils/format_match_reasons.dart';

class NotificationCard extends StatelessWidget {
  const NotificationCard({
    super.key,
    required this.item,
    required this.isArabic,
    required this.onMarkAsRead,
    this.marking = false,
  });

  final NotificationItem item;
  final bool isArabic;
  final bool marking;
  final VoidCallback onMarkAsRead;

  @override
  Widget build(BuildContext context) {
    final reasons = formatMatchReasons(
      item.metadata?.matchReasons ?? const <String>[],
      isArabic: isArabic,
    );
    final link = item.metadata?.linkUrl;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFF9FAFF),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x1A000000)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            item.title,
            style: const TextStyle(
              fontSize: 14.5,
              fontWeight: FontWeight.w800,
              color: Color(0xFF030213),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            item.message,
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xFF717182),
              height: 1.4,
            ),
          ),
          if (reasons.isNotEmpty) ...[
            const SizedBox(height: 10),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: reasons
                  .map(
                    (reason) => Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 8,
                        vertical: 5,
                      ),
                      decoration: BoxDecoration(
                        color: const Color(0xFFE6EEFF),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        reason,
                        style: const TextStyle(
                          fontSize: 11.5,
                          color: Color(0xFF1D4ED8),
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ),
                  )
                  .toList(growable: false),
            ),
          ],
          const SizedBox(height: 12),
          Row(
            children: [
              if (link != null && link.isNotEmpty)
                Expanded(
                  child: Text(
                    link,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      color: Color(0xFF2563EB),
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                )
              else
                const Spacer(),
              const SizedBox(width: 10),
              ElevatedButton.icon(
                onPressed: marking ? null : onMarkAsRead,
                icon: marking
                    ? const SizedBox(
                        width: 14,
                        height: 14,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                          color: Colors.white,
                        ),
                      )
                    : const Icon(Icons.done, size: 16),
                label: Text(isArabic ? 'تمت القراءة' : 'Mark as read'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF2F6CFF),
                  foregroundColor: Colors.white,
                  elevation: 0,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 10,
                  ),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
