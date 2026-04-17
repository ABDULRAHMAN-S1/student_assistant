import 'package:flutter/material.dart';

class FeedEmptyState extends StatelessWidget {
  const FeedEmptyState({super.key, required this.isArabic});

  final bool isArabic;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFFBF4FC),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0x1A000000)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            isArabic
                ? 'لا توجد تنبيهات أو اقتراحات حاليًا'
                : 'No notifications or suggestions right now',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: Color(0xFF030213),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            isArabic
                ? 'حدّث ملفك التخصيصي لتحصل على محتوى أكثر ملاءمة.'
                : 'Update your profile to receive more relevant content.',
            style: const TextStyle(
              fontSize: 13,
              color: Color(0xFF717182),
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }
}
