import 'package:flutter/material.dart';

import 'app_settings_store.dart';

class AppSessionController extends ChangeNotifier {
  AppSessionController({required AppSettingsStore settingsStore})
    : _settingsStore = settingsStore;

  final AppSettingsStore _settingsStore;

  Locale _locale = const Locale('ar');
  bool _hasSeenWelcome = false;
  bool _isLoggedIn = false;

  Locale get locale => _locale;
  bool get isArabic => _locale.languageCode == 'ar';
  bool get hasSeenWelcome => _hasSeenWelcome;
  bool get isLoggedIn => _isLoggedIn;
  bool get isGuest => !_isLoggedIn;

  void initialize() {
    _locale = Locale(_settingsStore.readLanguageCode());
    _hasSeenWelcome = _settingsStore.readHasSeenWelcome();
    _isLoggedIn = _settingsStore.readIsLoggedIn();
  }

  Future<void> toggleLanguage() async {
    final newLanguageCode = _locale.languageCode == 'ar' ? 'en' : 'ar';
    _locale = Locale(newLanguageCode);
    await _settingsStore.writeLanguageCode(newLanguageCode);
    notifyListeners();
  }

  Future<void> completeWelcome({bool asGuest = false}) async {
    _hasSeenWelcome = true;
    _isLoggedIn = !asGuest;
    await _settingsStore.writeHasSeenWelcome(true);
    await _settingsStore.writeIsLoggedIn(!asGuest);
    notifyListeners();
  }

  Future<void> markLoggedIn() async {
    _isLoggedIn = true;
    await _settingsStore.writeIsLoggedIn(true);
    notifyListeners();
  }

  Future<void> logout() async {
    _isLoggedIn = false;
    _hasSeenWelcome = false;
    await _settingsStore.writeIsLoggedIn(false);
    await _settingsStore.writeHasSeenWelcome(false);
    notifyListeners();
  }
}
