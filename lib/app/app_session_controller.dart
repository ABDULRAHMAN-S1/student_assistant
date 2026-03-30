import 'package:flutter/material.dart';

import '../features/auth/domain/models/auth_session.dart';
import 'app_settings_store.dart';

class AppSessionController extends ChangeNotifier {
  AppSessionController({required AppSettingsStore settingsStore})
    : _settingsStore = settingsStore;

  final AppSettingsStore _settingsStore;

  Locale _locale = const Locale('ar');
  bool _hasSeenWelcome = false;
  AuthSession? _authSession;

  Locale get locale => _locale;
  bool get isArabic => _locale.languageCode == 'ar';
  bool get hasSeenWelcome => _hasSeenWelcome;
  bool get isLoggedIn => _authSession?.isAuthenticated == true;
  bool get isGuest => !isLoggedIn;
  AuthSession? get authSession => _authSession;

  void initialize() {
    _locale = Locale(_settingsStore.readLanguageCode());
    _hasSeenWelcome = _settingsStore.readHasSeenWelcome();
    _authSession = _settingsStore.readAuthSession();
  }

  Future<void> toggleLanguage() async {
    final newLanguageCode = _locale.languageCode == 'ar' ? 'en' : 'ar';
    _locale = Locale(newLanguageCode);
    await _settingsStore.writeLanguageCode(newLanguageCode);
    notifyListeners();
  }

  Future<void> completeWelcome({
    bool asGuest = false,
    AuthSession? session,
  }) async {
    _hasSeenWelcome = true;
    _authSession = asGuest ? null : session;
    await _settingsStore.writeHasSeenWelcome(true);
    if (asGuest || session == null) {
      await _settingsStore.clearAuthSession();
    } else {
      await _settingsStore.writeAuthSession(session);
    }
    notifyListeners();
  }

  Future<void> markLoggedIn(AuthSession session) async {
    _authSession = session;
    await _settingsStore.writeAuthSession(session);
    notifyListeners();
  }

  Future<void> updateSession(AuthSession session) async {
    _authSession = session;
    await _settingsStore.writeAuthSession(session);
    notifyListeners();
  }

  Future<void> expireSession() async {
    await _clearSession(resetWelcome: false);
  }

  Future<void> logout() async {
    await _clearSession(resetWelcome: true);
  }

  Future<void> _clearSession({required bool resetWelcome}) async {
    _authSession = null;
    if (resetWelcome) {
      _hasSeenWelcome = false;
    }
    await _settingsStore.clearAuthSession();
    if (resetWelcome) {
      await _settingsStore.writeHasSeenWelcome(false);
    }
    notifyListeners();
  }
}
