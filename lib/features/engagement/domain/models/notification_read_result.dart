import 'notification_item.dart';

class NotificationReadResult {
  const NotificationReadResult({
    required this.notification,
    required this.unreadCount,
    this.status = 'ok',
  });

  final NotificationItem notification;
  final int unreadCount;
  final String status;
}
