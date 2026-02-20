import 'package:flutter/material.dart';

import "create_account_screen.dart";

class LoginPage extends StatefulWidget {
  final bool isArabic;
  final VoidCallback? onLoginSuccess;

  const LoginPage({super.key, required this.isArabic, this.onLoginSuccess});

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  bool _hide = true;
  bool _remember = true;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isAr = widget.isArabic;

    return Directionality(
      textDirection: isAr ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        extendBodyBehindAppBar: true,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          title: Text(isAr ? 'تسجيل الدخول' : 'Login'),
          centerTitle: true,
        ),
        body: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topRight,
              end: Alignment.bottomLeft,
              colors: [Color(0xFFF6F7FF), Color(0xFFF1F5FF), Color(0xFFFFF5FA)],
            ),
          ),
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 90, 16, 24),
              child: Container(
                constraints: const BoxConstraints(maxWidth: 460),
                padding: const EdgeInsets.all(18),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.78),
                  borderRadius: BorderRadius.circular(24),
                  border: Border.all(
                    color: Colors.white.withValues(alpha: 0.85),
                  ),
                  boxShadow: [
                    BoxShadow(
                      blurRadius: 26,
                      offset: const Offset(0, 14),
                      color: Colors.black.withValues(alpha: 0.10),
                    ),
                  ],
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 64,
                      height: 64,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: const LinearGradient(
                          colors: [Color(0xFF4F46E5), Color(0xFF9333EA)],
                        ),
                        boxShadow: [
                          BoxShadow(
                            blurRadius: 18,
                            offset: const Offset(0, 12),
                            color: Colors.black.withValues(alpha: 0.12),
                          ),
                        ],
                      ),
                      child: const Icon(
                        Icons.school_rounded,
                        color: Colors.white,
                        size: 30,
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      isAr ? 'أهلاً بك 👋' : 'Welcome 👋',
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      isAr
                          ? 'سجّل دخولك للاستفادة من المزايا'
                          : 'Sign in to unlock features',
                      style: const TextStyle(
                        fontSize: 12,
                        color: Colors.black54,
                      ),
                      textAlign: TextAlign.center,
                    ),
                    const SizedBox(height: 18),

                    _SoftTextField(
                      controller: _email,
                      label: isAr ? 'البريد الجامعي' : 'Email',
                      icon: Icons.email_rounded,
                      keyboardType: TextInputType.emailAddress,
                    ),
                    const SizedBox(height: 12),
                    _SoftTextField(
                      controller: _password,
                      label: isAr ? 'كلمة المرور' : 'Password',
                      icon: Icons.lock_rounded,
                      obscureText: _hide,
                      suffix: IconButton(
                        onPressed: () => setState(() => _hide = !_hide),
                        icon: Icon(
                          _hide
                              ? Icons.visibility_rounded
                              : Icons.visibility_off_rounded,
                        ),
                      ),
                    ),

                    const SizedBox(height: 10),

                    Row(
                      children: [
                        Expanded(
                          child: Row(
                            children: [
                              Switch(
                                value: _remember,
                                onChanged: (v) => setState(() => _remember = v),
                              ),
                              Text(
                                isAr ? 'تذكرني' : 'Remember me',
                                style: const TextStyle(
                                  fontSize: 12,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                            ],
                          ),
                        ),
                        TextButton(
                          onPressed: () {},
                          child: Text(
                            isAr ? 'نسيت كلمة المرور؟' : 'Forgot password?',
                          ),
                        ),
                      ],
                    ),

                    const SizedBox(height: 6),

                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: ElevatedButton(
                        onPressed: () {
                          widget.onLoginSuccess?.call();

                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(isAr ? 'تم (ديمو)' : 'Done (demo)'),
                              behavior: SnackBarBehavior.floating,
                            ),
                          );
                        },
                        style: ElevatedButton.styleFrom(
                          elevation: 0,
                          backgroundColor: Colors.transparent,
                          shadowColor: Colors.transparent,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(18),
                          ),
                        ),
                        child: Ink(
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(18),
                            gradient: const LinearGradient(
                              colors: [Color(0xFF4F46E5), Color(0xFF9333EA)],
                            ),
                          ),
                          child: Container(
                            alignment: Alignment.center,
                            child: Text(
                              isAr ? 'تسجيل الدخول' : 'Login',
                              style: const TextStyle(
                                color: Colors.white,
                                fontWeight: FontWeight.w900,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),

                    const SizedBox(height: 14),

                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          isAr ? 'ما عندك حساب؟ ' : "Don't have an account? ",
                          style: const TextStyle(color: Colors.black54),
                        ),
                        TextButton(
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (context) => CreateAccountScreen(
                                  isArabic: isAr,
                                  onRegisterSuccess: widget.onLoginSuccess,
                                ),
                              ),
                            );
                          },
                          child: Text(
                            isAr ? 'إنشاء حساب' : 'Sign up',
                            style: const TextStyle(fontWeight: FontWeight.w900),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _SoftTextField extends StatelessWidget {
  final TextEditingController controller;
  final String label;
  final IconData icon;
  final TextInputType? keyboardType;
  final bool obscureText;
  final Widget? suffix;

  const _SoftTextField({
    required this.controller,
    required this.label,
    required this.icon,
    this.keyboardType,
    this.obscureText = false,
    this.suffix,
  });

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      obscureText: obscureText,
      decoration: InputDecoration(
        labelText: label,
        prefixIcon: Icon(icon),
        suffixIcon: suffix,
        filled: true,
        fillColor: Colors.white.withValues(alpha: 0.85),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(16)),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: Colors.black.withValues(alpha: 0.08)),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: Color(0xFF4F46E5), width: 1.6),
        ),
      ),
    );
  }
}
