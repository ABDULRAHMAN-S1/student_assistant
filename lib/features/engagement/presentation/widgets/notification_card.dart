import 'package:flutter/material.dart';

import '../../domain/models/notification_item.dart';
import '../utils/format_match_reasons.dart';
import '../utils/format_notification_time.dart';

class NotificationCard extends StatelessWidget {
  const NotificationCard({
    super.key,
    required this.item,
    required this.isArabic,
    required this.onMarkAsRead,
    required this.onOpen,
    this.marking = false,
  });

  final NotificationItem item;
  final bool isArabic;
  final bool marking;
  final VoidCallback onMarkAsRead;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final reasons = formatMatchReasons(
      item.metadata?.matchReasons ?? const <String>[],
      isArabic: isArabic,
    );
    final routeLabel = item.metadata?.route?.displayLabel(isArabic: isArabic);
    final relativeTime = formatRelativeNotificationTime(
      item.createdAt,
      isArabic: isArabic,
    );
    final exactTime = formatExactNotificationTime(
      item.createdAt,
      isArabic: isArabic,
    );
    final background = item.isRead
        ? const Color(0xFFF8FAFC)
        : const Color(0xFFF2F7FF);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        borderRadius: BorderRadius.circular(14),
        onTap: onOpen,
        child: Ink(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: background,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: item.isRead
                  ? const Color(0x1A000000)
                  : const Color(0x332F6CFF),
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  if (!item.isRead)
                    Container(
                      width: 10,
                      height: 10,
                      margin: const EdgeInsetsDirectional.only(end: 8),
                      decoration: const BoxDecoration(
                        color: Color(0xFF2F6CFF),
                        shape: BoxShape.circle,
                      ),
                    ),
                  Expanded(
                    child: Text(
                      item.title,
                      style: const TextStyle(
                        fontSize: 14.5,
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF030213),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    relativeTime,
                    style: const TextStyle(
                      fontSize: 11.5,
                      color: Color(0xFF64748B),
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ],
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
              const SizedBox(height: 8),
              Text(
                exactTime,
                style: const TextStyle(
                  fontSize: 11.5,
                  color: Color(0xFF94A3B8),
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
              if (routeLabel != null && routeLabel.isNotEmpty) ...[
                const SizedBox(height: 10),
                Text(
                  routeLabel,
                  style: const TextStyle(
                    color: Color(0xFF2563EB),
                    fontSize: 12.5,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
              const SizedBox(height: 12),
              Row(
                children: [
                  TextButton.icon(
                    onPressed: onOpen,
                    icon: const Icon(Icons.open_in_new_rounded, size: 16),
                    label: Text(isArabic ? 'فتح' : 'Open'),
                  ),
                  const Spacer(),
                  ElevatedButton.icon(
                    onPressed: marking || item.isRead ? null : onMarkAsRead,
                    icon: marking
                        ? const SizedBox(
                            width: 14,
                            height: 14,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Icon(
                            item.isRead ? Icons.done_all : Icons.done,
                            size: 16,
                          ),
                    label: Text(
                      item.isRead
                          ? (isArabic ? 'مقروء' : 'Read')
                          : (isArabic ? 'تمت القراءة' : 'Mark as read'),
                    ),
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
        ),
      ),
    );
  }
}
