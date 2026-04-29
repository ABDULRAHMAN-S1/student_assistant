import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../../../../app/app_settings_store.dart';
import '../../../auth/domain/models/auth_session.dart';
import '../../data/repositories/engagement_repository.dart';
import '../../domain/models/notification_route.dart';
import 'notification_navigation_service.dart';

Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  try {
    await Firebase.initializeApp();
  } catch (_) {
    // Firebase may be unconfigured in local/dev environments.
  }
}

class PushNotificationService {
  PushNotificationService._();

  static final PushNotificationService instance = PushNotificationService._();

  final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;
  String? _registeredToken;
  String? _registeredDeviceTokenId;
  EngagementRepository? _repository;
  BuildContext? _context;
  bool _isArabic = false;
  String _localeCode = 'en';
  StreamSubscription<String>? _tokenRefreshSubscription;
  StreamSubscription<RemoteMessage>? _foregroundSubscription;
  StreamSubscription<RemoteMessage>? _tapSubscription;

  Future<void> initialize() async {
    if (_initialized) {
      return;
    }
    try {
      await Firebase.initializeApp();
    } catch (_) {
      return;
    }

    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);

    const androidSettings = AndroidInitializationSettings(
      '@mipmap/ic_launcher',
    );
    const initSettings = InitializationSettings(android: androidSettings);
    await _localNotifications.initialize(
      settings: initSettings,
      onDidReceiveNotificationResponse: (response) {
        final route = _routeFromPayload(response.payload);
        if (route != null && _context != null) {
          final context = _context!;
          unawaited(
            NotificationNavigationService.instance.handleRoute(
              context,
              route,
              isArabic: _isArabic,
            ),
          );
        }
      },
    );

    _foregroundSubscription = FirebaseMessaging.onMessage.listen((message) {
      _showForegroundNotification(message);
    });
    _tapSubscription = FirebaseMessaging.onMessageOpenedApp.listen((message) {
      final context = _context;
      if (context == null || !context.mounted) {
        return;
      }
      unawaited(
        NotificationNavigationService.instance.handleRemoteMessage(
          message,
          context: context,
          isArabic: _isArabic,
        ),
      );
    });
    _tokenRefreshSubscription = FirebaseMessaging.instance.onTokenRefresh.listen((
      token,
    ) {
      final repository = _repository;
      if (repository == null) {
        return;
      }
      unawaited(
        _syncToken(
          repository: repository,
          localeCode: _localeCode,
          token: token,
        ),
      );
    });
    _initialized = true;
    final settingsStore = await AppSettingsStore.open();
    _registeredDeviceTokenId = settingsStore.readNotificationDeviceTokenId();
  }

  Future<void> requestPermissionIfNeeded() async {
    if (!_initialized) {
      await initialize();
    }
    try {
      await FirebaseMessaging.instance.requestPermission(
        alert: true,
        badge: true,
        sound: true,
        provisional: false,
      );
    } catch (_) {
      // Ignore when Firebase is not configured on this machine.
    }
  }

  Future<void> registerForSession({
    required EngagementRepository repository,
    required AuthSession? session,
    required BuildContext context,
    required bool isArabic,
  }) async {
    _repository = repository;
    _context = context;
    _isArabic = isArabic;
    _localeCode = Localizations.localeOf(context).languageCode;
    if (session == null) {
      await unregisterCurrentDevice(repository: repository);
      return;
    }
    if (!_initialized) {
      await initialize();
    }
    await requestPermissionIfNeeded();
    try {
      final settingsStore = await AppSettingsStore.open();
      _registeredDeviceTokenId ??=
          settingsStore.readNotificationDeviceTokenId();
      final token = await FirebaseMessaging.instance.getToken();
      if (token == null || token.isEmpty || token == _registeredToken) {
        return;
      }
      if (!context.mounted) {
        return;
      }
      final initialMessage = await FirebaseMessaging.instance.getInitialMessage();
      if (initialMessage != null && context.mounted) {
        unawaited(
          NotificationNavigationService.instance.handleRemoteMessage(
            initialMessage,
            context: context,
            isArabic: isArabic,
          ),
        );
      }
      await _syncToken(
        repository: repository,
        localeCode: _localeCode,
        token: token,
      );
    } catch (_) {
      // Keep app startup/login resilient if push is not configured yet.
    }
  }

  Future<void> unregisterCurrentDevice({
    required EngagementRepository repository,
  }) async {
    _repository = repository;
    final existingTokenId = _registeredDeviceTokenId;
    _registeredToken = null;
    _registeredDeviceTokenId = null;
    final settingsStore = await AppSettingsStore.open();
    final persistedTokenId =
        existingTokenId ?? settingsStore.readNotificationDeviceTokenId();
    if (existingTokenId != null && existingTokenId.isNotEmpty) {
      try {
        await repository.deleteDeviceToken(existingTokenId);
      } catch (_) {
        // Avoid blocking logout on token cleanup failures.
      }
    }
    if (persistedTokenId != null &&
        persistedTokenId.isNotEmpty &&
        persistedTokenId != existingTokenId) {
      try {
        await repository.deleteDeviceToken(persistedTokenId);
      } catch (_) {
        // Avoid blocking logout on token cleanup failures.
      }
    }
    await settingsStore.writeNotificationDeviceTokenId(null);
    try {
      await FirebaseMessaging.instance.deleteToken();
    } catch (_) {
      // Ignore when Firebase is not configured.
    }
  }

  Future<void> _syncToken({
    required EngagementRepository repository,
    required String localeCode,
    required String token,
  }) async {
    if (token.isEmpty) {
      return;
    }
    final previousTokenId = _registeredDeviceTokenId;
    final previousToken = _registeredToken;
    if (previousTokenId != null &&
        previousTokenId.isNotEmpty &&
        previousToken != null &&
        previousToken != token) {
      try {
        await repository.deleteDeviceToken(previousTokenId);
      } catch (_) {
        // Try the new registration even if old cleanup fails.
      }
    }
    final deviceToken = await repository.registerDeviceToken(
      token: token,
      platform: Platform.isIOS ? 'ios' : 'android',
      locale: localeCode,
    );
    _registeredToken = token;
    _registeredDeviceTokenId = deviceToken.id;
    final settingsStore = await AppSettingsStore.open();
    await settingsStore.writeNotificationDeviceTokenId(deviceToken.id);
  }

  Future<void> _showForegroundNotification(RemoteMessage message) async {
    final notification = message.notification;
    if (notification == null) {
      return;
    }
    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        'engagement_notifications',
        'Engagement Notifications',
        channelDescription: 'Foreground engagement notifications',
        importance: Importance.max,
        priority: Priority.high,
      ),
    );
    await _localNotifications.show(
      id: notification.hashCode,
      title: notification.title,
      body: notification.body,
      notificationDetails: details,
      payload: _payloadFromData(message.data),
    );
  }

  String? _payloadFromData(Map<String, dynamic> data) {
    final type = data['route_type']?.toString();
    if (type == null || type.isEmpty) {
      return null;
    }
    final payload = data['route_payload'];
    final encodedPayload = payload is String
        ? payload
        : jsonEncode(payload ?? const <String, dynamic>{});
    return jsonEncode({'type': type, 'payload': encodedPayload});
  }

  NotificationRoute? _routeFromPayload(String? payload) {
    if (payload == null || payload.isEmpty) {
      return null;
    }
    try {
      final decoded = jsonDecode(payload);
      if (decoded is! Map<String, dynamic>) {
        return null;
      }
      final routeType = NotificationRouteTypeX.fromString(
        decoded['type']?.toString(),
      );
      if (routeType == null) {
        return null;
      }
      final rawPayload = decoded['payload'];
      final parsedPayload = rawPayload is String
          ? jsonDecode(rawPayload) as Map<String, dynamic>
          : rawPayload is Map
          ? Map<String, dynamic>.from(rawPayload)
          : const <String, dynamic>{};
      return NotificationRoute(type: routeType, payload: parsedPayload);
    } catch (_) {
      return null;
    }
  }

  void dispose() {
    _foregroundSubscription?.cancel();
    _tapSubscription?.cancel();
    _tokenRefreshSubscription?.cancel();
  }
}
