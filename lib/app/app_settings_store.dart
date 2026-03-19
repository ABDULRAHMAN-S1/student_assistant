import 'package:hive_flutter/hive_flutter.dart';

class AppSettingsStore {
  AppSettingsStore._(this._box);

  factory AppSettingsStore.fromBox(Box box) {
    return AppSettingsStore._(box);
  }

  static const String boxName = 'settings';
  static const String languageKey = 'language';
  static const String hasSeenWelcomeKey = 'hasSeenWelcome';
  static const String isLoggedInKey = 'isLoggedIn';

  final Box _box;

  static Future<AppSettingsStore> open() async {
    if (!Hive.isBoxOpen(boxName)) {
      await Hive.openBox(boxName);
    }
    return AppSettingsStore._(Hive.box(boxName));
  }

  static Future<void> ensureInitialized() async {
    await Hive.initFlutter();
    await open();
  }

  String readLanguageCode() {
    return (_box.get(languageKey, defaultValue: 'ar') ?? 'ar').toString();
  }

  bool readHasSeenWelcome() {
    return _box.get(hasSeenWelcomeKey, defaultValue: false) == true;
  }

  bool readIsLoggedIn() {
    return _box.get(isLoggedInKey, defaultValue: false) == true;
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
}
