import 'package:hive_flutter/hive_flutter.dart';

import '../features/auth/domain/models/auth_session.dart';
import 'app_hive.dart';

class AppSettingsStore {
  AppSettingsStore._(this._box);

  factory AppSettingsStore.fromBox(Box box) {
    return AppSettingsStore._(box);
  }

  static const String boxName = 'settings';
  static const String languageKey = 'language';
  static const String hasSeenWelcomeKey = 'hasSeenWelcome';
  static const String isLoggedInKey = 'isLoggedIn';
  static const String authSessionKey = 'authSession';
  static const String notificationDeviceTokenIdKey =
      'notificationDeviceTokenId';

  final Box _box;

  static Future<AppSettingsStore> open() async {
    if (!Hive.isBoxOpen(boxName)) {
      await AppHive.openBox(boxName);
    }
    return AppSettingsStore._(Hive.box(boxName));
  }

  static Future<void> ensureInitialized() async {
    await AppHive.ensureInitialized();
    await open();
  }

  String readLanguageCode() {
    return (_box.get(languageKey, defaultValue: 'ar') ?? 'ar').toString();
  }

  bool readHasSeenWelcome() {
    return _box.get(hasSeenWelcomeKey, defaultValue: false) == true;
  }

  bool readIsLoggedIn() {
    final session = readAuthSession();
    if (session == null) {
      return _box.get(isLoggedInKey, defaultValue: false) == true;
    }
    return session.isAuthenticated;
  }

  AuthSession? readAuthSession() {
    final raw = _box.get(authSessionKey);
    if (raw is! Map) {
      return null;
    }
    final session = AuthSession.fromMap(Map<String, dynamic>.from(raw));
    return session.isAuthenticated ? session : null;
  }

  String? readNotificationDeviceTokenId() {
    final raw = _box.get(notificationDeviceTokenIdKey);
    final value = raw?.toString().trim() ?? '';
    return value.isEmpty ? null : value;
  }

  Future<void> writeLanguageCode(String languageCode) {
    return _box.put(languageKey, languageCode);
  }

  Future<void> writeHasSeenWelcome(bool value) {
    return _box.put(hasSeenWelcomeKey, value);
  }

  Future<void> writeIsLoggedIn(bool value) {
    return _box.put(isLoggedInKey, value);
  }

  Future<void> writeAuthSession(AuthSession session) async {
    await _box.put(authSessionKey, session.toMap());
    await writeIsLoggedIn(true);
  }

  Future<void> writeNotificationDeviceTokenId(String? value) async {
    final cleaned = value?.trim() ?? '';
    if (cleaned.isEmpty) {
      await _box.delete(notificationDeviceTokenIdKey);
      return;
    }
    await _box.put(notificationDeviceTokenIdKey, cleaned);
  }

  Future<void> clearAuthSession() async {
    await _box.delete(authSessionKey);
    await writeIsLoggedIn(false);
  }
}
