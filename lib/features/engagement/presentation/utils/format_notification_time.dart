import 'package:intl/intl.dart';

String formatRelativeNotificationTime(
  DateTime? value, {
  required bool isArabic,
  DateTime? now,
}) {
  if (value == null) {
    return isArabic ? 'الآن' : 'Just now';
  }

  final reference = (now ?? DateTime.now()).toUtc();
  final target = value.toUtc();
  final difference = reference.difference(target);

  if (difference.inSeconds < 45) {
    return isArabic ? 'الآن' : 'Just now';
  }
  if (difference.inMinutes < 60) {
    final minutes = difference.inMinutes;
    return isArabic ? 'منذ $minutes دقيقة' : '$minutes min ago';
  }
  if (difference.inHours < 24) {
    final hours = difference.inHours;
    return isArabic ? 'منذ $hours ساعة' : '$hours hr ago';
  }
  if (difference.inDays == 1) {
    return isArabic ? 'أمس' : 'Yesterday';
  }
  if (difference.inDays < 7) {
    final days = difference.inDays;
    return isArabic ? 'منذ $days أيام' : '$days days ago';
  }

  return formatExactNotificationTime(value, isArabic: isArabic);
}

String formatExactNotificationTime(DateTime? value, {required bool isArabic}) {
  if (value == null) {
    return isArabic ? 'غير معروف' : 'Unknown';
  }
  final locale = isArabic ? 'ar' : 'en';
  return DateFormat('yMMMd, h:mm a', locale).format(value.toLocal());
}
