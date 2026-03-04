import 'package:flutter/material.dart';

import 'login_page.dart';

class ForgotPasswordScreen extends StatefulWidget {
  final bool isArabic;
  const ForgotPasswordScreen({super.key, this.isArabic = true});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _codeController = TextEditingController();
  final _newPasswordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();

  bool _isLoading = false;
  bool _codeSent = false;
  bool _obscureNewPassword = true;
  bool _obscureConfirmPassword = true;

  static const Color _primaryPurple = Color(0xFF7C3AED);
  static const Color _lightPurple = Color(0xFFB829F7);
  static const Color _darkPurple = Color(0xFF4F46E5);
  static const Color _borderColor = Color(0xFFE2E8F0);
  static const Color _hintColor = Color(0xFF94A3B8);
  static const Color _labelColor = Color(0xFF1E293B);

  String _getText(String ar, String en) => widget.isArabic ? ar : en;

  @override
  void dispose() {
    _emailController.dispose();
    _codeController.dispose();
    _newPasswordController.dispose();
    _confirmPasswordController.dispose();
    super.dispose();
  }

  Future<void> _sendCode() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    await Future.delayed(const Duration(seconds: 2));
    setState(() {
      _isLoading = false;
      _codeSent = true;
    });
    _showMessage(_getText('تم إرسال الرمز', 'Code sent'));
  }

  Future<void> _resetPassword() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    await Future.delayed(const Duration(seconds: 2));
    setState(() => _isLoading = false);
    _showMessage(_getText('تم التغيير بنجاح', 'Password reset'));
    Future.delayed(const Duration(seconds: 1), () {
      if (mounted) {
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
            builder: (_) => LoginPage(isArabic: widget.isArabic),
          ),
        );
      }
    });
  }

  void _showMessage(String msg) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(msg), backgroundColor: Colors.green));
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: widget.isArabic ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: const Color(0xFFF8F9FA),
        body: SafeArea(
          child: SingleChildScrollView(
            child: Form(
              key: _formKey,
              child: Column(
                children: [
                  _buildHeader(),
                  const SizedBox(height: 32),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: _codeSent ? _buildResetForm() : _buildEmailForm(),
                  ),
                  const SizedBox(height: 24),
                  TextButton(
                    onPressed: () => Navigator.pushReplacement(
                      context,
                      MaterialPageRoute(
                        builder: (_) => LoginPage(isArabic: widget.isArabic),
                      ),
                    ),
                    child: Text(_getText('العودة للتسجيل', 'Back to Login')),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [_lightPurple, _primaryPurple, _darkPurple],
        ),
        borderRadius: BorderRadius.only(
          bottomLeft: Radius.circular(24),
          bottomRight: Radius.circular(24),
        ),
      ),
      child: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            children: [
              Container(
                width: 80,
                height: 80,
                decoration: const BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.lock_reset,
                  size: 40,
                  color: _primaryPurple,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                _getText('نسيت كلمة السر؟', 'Forgot Password?'),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _getText('أدخل بريدك لإعادة التعيين', 'Enter email to reset'),
                style: const TextStyle(color: Colors.white70, fontSize: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildEmailForm() {
    return Column(
      children: [
        _buildTextField(
          controller: _emailController,
          label: _getText('البريد الإلكتروني', 'Email'),
          hint: 'example@email.com',
          keyboardType: TextInputType.emailAddress,
          icon: Icons.email,
          validator: (v) => v!.contains('@')
              ? null
              : _getText('بريد غير صالح', 'Invalid email'),
        ),
        const SizedBox(height: 24),
        _buildButton(_getText('إرسال الرمز', 'Send Code'), _sendCode),
      ],
    );
  }

  Widget _buildResetForm() {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.green.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: Colors.green.withValues(alpha: 0.3)),
          ),
          child: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.green),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  _getText(
                    'تم إرسال الرمز، تحقق من بريدك',
                    'Code sent, check your email',
                  ),
                  style: const TextStyle(color: Colors.green),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),
        _buildTextField(
          controller: _codeController,
          label: _getText('رمز التحقق', 'Code'),
          hint: '123456',
          keyboardType: TextInputType.number,
          icon: Icons.confirmation_num,
        ),
        const SizedBox(height: 16),
        _buildPasswordField(
          controller: _newPasswordController,
          label: _getText('كلمة السر الجديدة', 'New Password'),
          isObscured: _obscureNewPassword,
          onToggle: () =>
              setState(() => _obscureNewPassword = !_obscureNewPassword),
          validator: (v) =>
              v!.length >= 6 ? null : _getText('قصيرة جداً', 'Too short'),
        ),
        const SizedBox(height: 16),
        _buildPasswordField(
          controller: _confirmPasswordController,
          label: _getText('تأكيد كلمة السر', 'Confirm'),
          isObscured: _obscureConfirmPassword,
          onToggle: () => setState(
            () => _obscureConfirmPassword = !_obscureConfirmPassword,
          ),
          validator: (v) => v == _newPasswordController.text
              ? null
              : _getText('غير متطابقة', 'Not matching'),
        ),
        const SizedBox(height: 24),
        _buildButton(
          _getText('تغيير كلمة السر', 'Reset Password'),
          _resetPassword,
        ),
        const SizedBox(height: 16),
        TextButton(
          onPressed: _isLoading ? null : _sendCode,
          child: Text(_getText('إعادة إرسال الرمز', 'Resend Code')),
        ),
      ],
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    required IconData icon,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: _labelColor,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          textDirection: TextDirection.ltr,
          validator: validator,
          decoration: InputDecoration(
            hintText: hint,
            prefixIcon: Icon(icon, color: _primaryPurple),
            filled: true,
            fillColor: const Color(0xFFF1F5F9),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: _borderColor),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: _primaryPurple, width: 2),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildPasswordField({
    required TextEditingController controller,
    required String label,
    required bool isObscured,
    required VoidCallback onToggle,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          label,
          style: const TextStyle(
            color: _labelColor,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          obscureText: isObscured,
          textDirection: TextDirection.ltr,
          validator: validator,
          decoration: InputDecoration(
            hintText: '••••••••',
            prefixIcon: const Icon(Icons.lock, color: _primaryPurple),
            suffixIcon: IconButton(
              icon: Icon(
                isObscured ? Icons.visibility_off : Icons.visibility,
                color: _hintColor,
              ),
              onPressed: onToggle,
            ),
            filled: true,
            fillColor: const Color(0xFFF1F5F9),
            border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
            enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: _borderColor),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12),
              borderSide: const BorderSide(color: _primaryPurple, width: 2),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildButton(String text, VoidCallback onPressed) {
    return Container(
      width: double.infinity,
      height: 56,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [_lightPurple, _primaryPurple, _darkPurple],
        ),
        borderRadius: BorderRadius.circular(12),
      ),
      child: ElevatedButton(
        onPressed: _isLoading ? null : onPressed,
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent,
          shadowColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: _isLoading
            ? const CircularProgressIndicator(color: Colors.white)
            : Text(
                text,
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                ),
              ),
      ),
    );
  }
}