import 'package:hive_flutter/hive_flutter.dart';
import 'package:path_provider/path_provider.dart';

import '../features/auth/domain/models/auth_session.dart';
import 'local_encryption_key_provider.dart';

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
  static const String notificationDeviceTokenIdKey = 'notificationDeviceTokenId';

  final Box _box;

  static Future<AppSettingsStore> open() async {
    if (!Hive.isBoxOpen(boxName)) {
      await _openEncryptedBox(boxName);
    }
    return AppSettingsStore._(Hive.box(boxName));
  }

  static Future<void> ensureInitialized() async {
    final appSupportDirectory = await getApplicationSupportDirectory();
    await appSupportDirectory.create(recursive: true);
    Hive.init(appSupportDirectory.path);
    await LocalEncryptionKeyProvider.instance.getKey();
    await open();
  }

  static Future<void> _openEncryptedBox(String name) async {
    final encryptionKey = await LocalEncryptionKeyProvider.instance.getKey();
    try {
      await Hive.openBox(name, encryptionCipher: HiveAesCipher(encryptionKey));
    } catch (error) {
      if (_isFileLockError(error)) {
        rethrow;
      }
      // Do NOT wipe user data on ambiguous open failures.
      // Only wipe when corruption is strongly indicated.
      if (_looksLikeCorruptionError(error)) {
        await Hive.deleteBoxFromDisk(name);
        await Hive.openBox(name, encryptionCipher: HiveAesCipher(encryptionKey));
        return;
      }
      rethrow;
    }
  }

  static bool _isFileLockError(Object error) {
    final message = error.toString().toLowerCase();
    return message.contains('lock failed') ||
        message.contains('being used by another process') ||
        message.contains('cannot delete file');
  }

  static bool _looksLikeCorruptionError(Object error) {
    final message = error.toString().toLowerCase();
    // Hive can report "wrong key or corrupted box". Treat "wrong key" as NOT confirmed corruption.
    if (message.contains('wrong key')) return false;
    return message.contains('corrupt') ||
        message.contains('crc') ||
        message.contains('invalid header') ||
        message.contains('cannot be decoded') ||
        message.contains('bad state');
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
