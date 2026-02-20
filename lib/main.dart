import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:hive_flutter/hive_flutter.dart';

import 'home_page.dart';
import 'welcome_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Hive.initFlutter();
  await Hive.openBox('settings');
  runApp(const StudentAssistantApp());
}

class StudentAssistantApp extends StatefulWidget {
  const StudentAssistantApp({super.key});

  @override
  State<StudentAssistantApp> createState() => _StudentAssistantAppState();
}

class _StudentAssistantAppState extends State<StudentAssistantApp> {
  late final Box _box;
  Locale _locale = const Locale('ar');

  @override
  void initState() {
    super.initState();
    _box = Hive.box('settings');
    final savedLang = _box.get('language', defaultValue: 'ar');
    _locale = Locale(savedLang);
  }

  bool get _hasSeenWelcome => _box.get('hasSeenWelcome', defaultValue: false);
  bool get _isLoggedIn => _box.get('isLoggedIn', defaultValue: false);

  void _toggleLanguage() {
    final newLang = _locale.languageCode == 'ar' ? 'en' : 'ar';
    _box.put('language', newLang);
    setState(() => _locale = Locale(newLang));
  }

  void _onWelcomeDone({bool asGuest = false}) {
    _box.put('hasSeenWelcome', true);
    _box.put('isLoggedIn', !asGuest);
    setState(() {});
  }

  void _onLoginSuccess() {
    _box.put('isLoggedIn', true);
    setState(() {});
  }

  void _logout() {
    _box.put('isLoggedIn', false);
    _box.put('hasSeenWelcome', false);
    setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final isArabic = _locale.languageCode == 'ar';

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Student Assistant',
      locale: _locale,
      supportedLocales: const [Locale('ar'), Locale('en')],
      localizationsDelegates: const [
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF4F46E5)),
      ),
      builder: (context, child) => Directionality(
        textDirection: isArabic ? TextDirection.rtl : TextDirection.ltr,
        child: child!,
      ),
      home: !_hasSeenWelcome
          ? WelcomeScreen(
              isArabic: isArabic,
              onToggleLanguage: _toggleLanguage,
              onDone: ({bool asGuest = false}) =>
                  _onWelcomeDone(asGuest: asGuest),
            )
          : HomePage(
              isArabic: isArabic,
              onToggleLanguage: _toggleLanguage,
              isGuest: !_isLoggedIn,
              onLoginSuccess: _onLoginSuccess,
              onLogout: _logout,
            ),
    );
  }
}
