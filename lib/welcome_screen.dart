import 'package:flutter/material.dart';

import 'create_account_screen.dart';
import 'login_page.dart';

class WelcomeScreen extends StatefulWidget {
  final bool isArabic;
  final VoidCallback onToggleLanguage;
  final void Function({bool asGuest}) onDone;

  const WelcomeScreen({
    super.key,
    required this.isArabic,
    required this.onToggleLanguage,
    required this.onDone,
  });

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> {
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [Color(0xFF667EEA), Color(0xFF764BA2), Color(0xFFF093FB)],
            stops: [0.0, 0.5, 1.0],
          ),
        ),
        child: SafeArea(
          child: Column(
            children: [
              Align(
                alignment: widget.isArabic
                    ? Alignment.topLeft
                    : Alignment.topRight,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: _buildLanguageButton(),
                ),
              ),
              const Spacer(),
              Container(
                margin: const EdgeInsets.symmetric(horizontal: 32),
                constraints: BoxConstraints(
                  maxHeight: MediaQuery.of(context).size.height * 0.7,
                ),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(24),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.15),
                      blurRadius: 30,
                      offset: const Offset(0, 10),
                    ),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(32),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          widget.isArabic
                              ? 'مساعد الطلاب'
                              : 'Student Assistant',
                          style: const TextStyle(
                            fontSize: 32,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF764BA2),
                          ),
                        ),
                        const SizedBox(height: 30),
                        Icon(
                          Icons.school,
                          size: 60,
                          color: Colors.purple.withValues(alpha: 0.3),
                        ),
                        const SizedBox(height: 30),
                        _buildButton(
                          text: widget.isArabic ? 'زائر' : 'Guest',
                          icon: Icons.person_outline,
                          colors: const [Color(0xFF667EEA), Color(0xFF764BA2)],
                          onPressed: () => widget.onDone(asGuest: true),
                        ),
                        const SizedBox(height: 12),
                        _buildButton(
                          text: widget.isArabic ? 'تسجيل دخول' : 'Login',
                          icon: Icons.login,
                          colors: const [Color(0xFF764BA2), Color(0xFF9B59B6)],
                          onPressed: () {
                            // ✅ USE PUSH (keeps Welcome in stack)
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) => LoginPage(
                                  isArabic: widget.isArabic,
                                  onLoginSuccess: () =>
                                      widget.onDone(asGuest: false),
                                  onToggleLanguage: widget.onToggleLanguage,
                                  onDone: widget.onDone,
                                ),
                              ),
                            );
                          },
                        ),
                        const SizedBox(height: 12),
                        _buildButton(
                          text: widget.isArabic ? 'تسجيل' : 'Register',
                          icon: Icons.person_add_outlined,
                          colors: const [Color(0xFF00B4DB), Color(0xFF0083B0)],
                          onPressed: () {
                            // ✅ USE PUSH (keeps Welcome in stack)
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) => CreateAccountScreen(
                                  isArabic: widget.isArabic,
                                  onRegisterSuccess: () =>
                                      widget.onDone(asGuest: false),
                                  onToggleLanguage: widget.onToggleLanguage,
                                  onDone: widget.onDone,
                                ),
                              ),
                            );
                          },
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 40),
              Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [_buildDot(true), _buildDot(false), _buildDot(false)],
              ),
              const Spacer(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDot(bool active) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      margin: const EdgeInsets.symmetric(horizontal: 4),
      width: active ? 24 : 8,
      height: 8,
      decoration: BoxDecoration(
        color: active
            ? const Color(0xFF00B4DB)
            : Colors.white.withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(4),
      ),
    );
  }

  Widget _buildButton({
    required String text,
    required IconData icon,
    required List<Color> colors,
    required VoidCallback onPressed,
  }) {
    return Container(
      width: double.infinity,
      height: 50,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: colors,
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
        ),
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(
            color: colors[0].withValues(alpha: 0.4),
            blurRadius: 12,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: onPressed,
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, color: Colors.white, size: 20),
              const SizedBox(width: 8),
              Text(
                text,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 16,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildLanguageButton() {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.1),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: widget.onToggleLanguage,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.translate, size: 18, color: Color(0xFF667EEA)),
                const SizedBox(width: 6),
                Text(
                  widget.isArabic ? 'English' : 'العربية',
                  style: const TextStyle(
                    color: Color(0xFF667EEA),
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}