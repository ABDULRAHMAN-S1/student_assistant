import 'dart:convert';

import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../../courses_page.dart';
import '../../../../events_page.dart';
import '../../../../reviews_page.dart';
import '../../../../services/ai_chat_page.dart';
import '../../../../services/regulation_search_page.dart';
import '../../domain/models/notification_item.dart';
import '../../domain/models/notification_route.dart';

class NotificationNavigationService {
  NotificationNavigationService._();

  static final NotificationNavigationService instance =
      NotificationNavigationService._();

  Future<void> openNotification({
    required BuildContext context,
    required NotificationItem item,
    required bool isArabic,
    Future<void> Function()? onSessionExpired,
    VoidCallback? onOpenInbox,
  }) async {
    final route = item.metadata?.route;
    if (route == null) {
      onOpenInbox?.call();
      return;
    }
    await handleRoute(
      context,
      route,
      isArabic: isArabic,
      onSessionExpired: onSessionExpired,
      onOpenInbox: onOpenInbox,
    );
  }

  Future<void> handleRemoteMessage(
    RemoteMessage message, {
    BuildContext? context,
    bool isArabic = false,
    Future<void> Function()? onSessionExpired,
    VoidCallback? onOpenInbox,
  }) async {
    final type = message.data['route_type']?.toString();
    if (type == null || type.isEmpty || context == null) {
      return;
    }
    final routeType = NotificationRouteTypeX.tryParse(type);
    if (routeType == null) {
      return;
    }
    final payloadText = message.data['route_payload']?.toString().trim() ?? '{}';
    Map<String, dynamic> payload = const <String, dynamic>{};
    try {
      final decoded = jsonDecode(payloadText);
      if (decoded is Map) {
        payload = Map<String, dynamic>.from(decoded);
      }
    } catch (_) {
      payload = const <String, dynamic>{};
    }
    await handleRoute(
      context,
      NotificationRoute(type: routeType, payload: payload),
      isArabic: isArabic,
      onSessionExpired: onSessionExpired,
      onOpenInbox: onOpenInbox,
    );
  }

  Future<void> handleRoute(
    BuildContext context,
    NotificationRoute route, {
    required bool isArabic,
    Future<void> Function()? onSessionExpired,
    VoidCallback? onOpenInbox,
  }) async {
    switch (route.type) {
      case NotificationRouteType.course:
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => CoursesPage(isArabic: isArabic)),
        );
        return;
      case NotificationRouteType.event:
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => EventsPage(isArabic: isArabic)),
        );
        return;
      case NotificationRouteType.review:
        await Navigator.of(context).push(
          MaterialPageRoute(builder: (_) => ReviewsPage(isArabic: isArabic)),
        );
        return;
      case NotificationRouteType.chat:
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) =>
                AIChatPage(isArabic: isArabic, onSessionExpired: onSessionExpired),
          ),
        );
        return;
      case NotificationRouteType.search:
        await Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => RegulationSearchPage(
              isArabic: isArabic,
              initialQuery: (route.payload['query'] ?? '').toString(),
            ),
          ),
        );
        return;
      case NotificationRouteType.externalUrl:
        final url = (route.payload['url'] ?? '').toString().trim();
        if (url.isEmpty) {
          onOpenInbox?.call();
          return;
        }
        final uri = Uri.tryParse(url);
        if (uri != null) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
        return;
      case NotificationRouteType.engagement:
        onOpenInbox?.call();
        return;
    }
  }
}
