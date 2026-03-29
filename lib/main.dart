import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'app/app_instance_guard.dart';
import 'app/app_session_controller.dart';
import 'app/app_settings_store.dart';
import 'features/auth/domain/models/auth_session.dart';
import 'home_page.dart';
import 'welcome_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const StudentAssistantBootstrapApp());
}

class StudentAssistantBootstrapApp extends StatefulWidget {
  const StudentAssistantBootstrapApp({super.key});

  @override
  State<StudentAssistantBootstrapApp> createState() =>
      _StudentAssistantBootstrapAppState();
}

class _StudentAssistantBootstrapAppState
    extends State<StudentAssistantBootstrapApp> {
  late Future<AppSessionController> _bootstrapFuture;

  @override
  void initState() {
    super.initState();
    _bootstrapFuture = _initializeApp();
  }

  Future<AppSessionController> _initializeApp() async {
    await AppInstanceGuard.instance.ensureSingleInstance();
    await AppSettingsStore.ensureInitialized();
    final settingsStore = await AppSettingsStore.open();
    return AppSessionController(settingsStore: settingsStore)..initialize();
  }

  void _retryInitialization() {
    setState(() {
      _bootstrapFuture = _initializeApp();
    });
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<AppSessionController>(
      future: _bootstrapFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const _StartupLoadingApp();
        }

        if (snapshot.hasError || !snapshot.hasData) {
          return _StartupFailureApp(
            error: snapshot.error,
            onRetry: _retryInitialization,
          );
        }

        return StudentAssistantApp(sessionController: snapshot.data!);
      },
    );
  }
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
                  onDone: ({bool asGuest = false, AuthSession? sessionData}) =>
                      session.completeWelcome(
                        asGuest: asGuest,
                        session: sessionData,
                      ),
                )
              : HomePage(
                  isArabic: isArabic,
                  onToggleLanguage: () {
                    session.toggleLanguage();
                  },
                  isGuest: session.isGuest,
                  onLoginSuccess: (sessionData) async {
                    await session.markLoggedIn(sessionData);
                  },
                  onSessionExpired: () async {
                    await session.expireSession();
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

class _StartupLoadingApp extends StatelessWidget {
  const _StartupLoadingApp();

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topCenter,
              end: Alignment.bottomCenter,
              colors: [Color(0xFFF6F7FF), Color(0xFFFFFFFF)],
            ),
          ),
          child: const Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(),
                SizedBox(height: 16),
                Text(
                  'Starting Student Assistant...',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _StartupFailureApp extends StatelessWidget {
  const _StartupFailureApp({required this.error, required this.onRetry});

  final Object? error;
  final VoidCallback onRetry;

  bool _isStorageLockError() {
    final message = (error ?? '').toString().toLowerCase();
    return message.contains('lock failed') ||
        message.contains('being used by another process') ||
        message.contains('cannot delete file');
  }

  bool _isAnotherInstanceError() {
    return error is AppInstanceException &&
        (error as AppInstanceException).alreadyRunning;
  }

  String _headline() {
    if (_isAnotherInstanceError()) {
      return 'Another app window is already open';
    }
    return _isStorageLockError()
        ? 'The app storage is locked'
        : 'Could not start the app';
  }

  String _message() {
    if (_isAnotherInstanceError()) {
      return 'Student Assistant already has a running window on this device. Close the other window first, then try again.';
    }
    if (_isStorageLockError()) {
      return 'Another running copy of Student Assistant is still using the local data files. Close other app windows, then try again.';
    }
    return 'Startup failed before the app could open. Retry first. If the problem continues, inspect the latest local setup changes.';
  }

  @override
  Widget build(BuildContext context) {
    final details = (error ?? '').toString().trim();

    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520),
              child: Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                  side: BorderSide(color: Colors.red.withValues(alpha: 0.15)),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(
                        Icons.error_outline_rounded,
                        color: Colors.redAccent,
                        size: 36,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        _headline(),
                        style: const TextStyle(
                          fontSize: 22,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _message(),
                        style: const TextStyle(fontSize: 15, height: 1.5),
                      ),
                      if (details.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        Container(
                          width: double.infinity,
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF8FAFC),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            details,
                            style: const TextStyle(fontSize: 13),
                          ),
                        ),
                      ],
                      const SizedBox(height: 20),
                      FilledButton.icon(
                        onPressed: onRetry,
                        icon: const Icon(Icons.refresh_rounded),
                        label: const Text('Retry startup'),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
