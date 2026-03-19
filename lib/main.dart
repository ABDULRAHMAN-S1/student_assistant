import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'app/app_session_controller.dart';
import 'app/app_settings_store.dart';
import 'home_page.dart';
import 'welcome_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppSettingsStore.ensureInitialized();
  final settingsStore = await AppSettingsStore.open();
  final sessionController = AppSessionController(settingsStore: settingsStore)
    ..initialize();
  runApp(StudentAssistantApp(sessionController: sessionController));
}

class StudentAssistantApp extends StatefulWidget {
  const StudentAssistantApp({super.key, required this.sessionController});

  final AppSessionController sessionController;

  @override
  State<StudentAssistantApp> createState() => _StudentAssistantAppState();
}

class _StudentAssistantAppState extends State<StudentAssistantApp> {
  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.sessionController,
      builder: (context, _) {
        final session = widget.sessionController;
        final isArabic = session.isArabic;

        return MaterialApp(
          debugShowCheckedModeBanner: false,
          title: 'Student Assistant',
          locale: session.locale,
          supportedLocales: const [Locale('ar'), Locale('en')],
          localizationsDelegates: const [
            GlobalMaterialLocalizations.delegate,
            GlobalWidgetsLocalizations.delegate,
            GlobalCupertinoLocalizations.delegate,
          ],
          theme: ThemeData(
            useMaterial3: true,
            colorScheme: ColorScheme.fromSeed(
              seedColor: const Color(0xFF4F46E5),
            ),
          ),
          builder: (context, child) => Directionality(
            textDirection: isArabic ? TextDirection.rtl : TextDirection.ltr,
            child: child!,
          ),
          home: !session.hasSeenWelcome
              ? WelcomeScreen(
                  isArabic: isArabic,
                  onToggleLanguage: () {
                    session.toggleLanguage();
                  },
                  onDone: ({bool asGuest = false}) =>
                      session.completeWelcome(asGuest: asGuest),
                )
              : HomePage(
                  isArabic: isArabic,
                  onToggleLanguage: () {
                    session.toggleLanguage();
                  },
                  isGuest: session.isGuest,
                  onLoginSuccess: () {
                    session.markLoggedIn();
                  },
                  onLogout: () {
                    session.logout();
                  },
                ),
        );
      },
    );
  }
}
