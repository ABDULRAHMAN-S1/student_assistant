import 'package:flutter/material.dart';

import '../../domain/models/suggestion_item.dart';
import '../utils/format_match_reasons.dart';

class SuggestionCard extends StatelessWidget {
  const SuggestionCard({
    super.key,
    required this.item,
    required this.isArabic,
    required this.onOpen,
  });

  final SuggestionItem item;
  final bool isArabic;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final reasons = formatMatchReasons(item.matchReasons, isArabic: isArabic);
    final typeText = _typeLabel(item.contentType);
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFFFFF),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0x1A000000)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
                decoration: BoxDecoration(
                  color: const Color(0xFFF0ECFF),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Text(
                  typeText,
                  style: const TextStyle(
                    fontSize: 11.5,
                    color: Color(0xFF6D28D9),
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              const Spacer(),
              if (item.startsAt != null)
                Text(
                  _formatDate(item.startsAt!),
                  style: const TextStyle(
                    fontSize: 11.5,
                    color: Color(0xFF717182),
                    fontWeight: FontWeight.w600,
                  ),
                ),
            ],
          ),
          const SizedBox(height: 10),
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
            item.body,
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
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(
              onPressed: onOpen,
              icon: const Icon(Icons.open_in_new, size: 16),
              label: Text(isArabic ? 'فتح التفاصيل' : 'Open details'),
            ),
          ),
        ],
      ),
    );
  }

  String _typeLabel(String value) {
    const arabicMap = {
      'event': 'فعالية',
      'academic_tip': 'نصيحة أكاديمية',
      'opportunity': 'فرصة',
      'deadline': 'موعد مهم',
    };
    const englishMap = {
      'event': 'Event',
      'academic_tip': 'Academic Tip',
      'opportunity': 'Opportunity',
      'deadline': 'Deadline',
    };
    final key = value.trim().toLowerCase();
    if (isArabic) {
      return arabicMap[key] ?? value;
    }
    return englishMap[key] ?? value;
  }

  String _formatDate(DateTime date) {
    return '${date.year}/${date.month.toString().padLeft(2, '0')}/${date.day.toString().padLeft(2, '0')}';
  }
}
