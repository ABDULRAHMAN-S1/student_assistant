import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import 'login_page.dart';

class CreateAccountScreen extends StatefulWidget {
  final bool isArabic;
  final VoidCallback? onRegisterSuccess;
  final VoidCallback? onToggleLanguage;
  final void Function({bool asGuest})? onDone;

  const CreateAccountScreen({
    super.key,
    this.isArabic = true,
    this.onRegisterSuccess,
    this.onToggleLanguage,
    this.onDone,
  });

  @override
  State<CreateAccountScreen> createState() => _CreateAccountScreenState();
}

class _CreateAccountScreenState extends State<CreateAccountScreen> {
  final _formKey = GlobalKey<FormState>();
  final _nameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _specializationController = TextEditingController();

  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  bool _agreedToTerms = false;
  String? _selectedAcademicLevel;
  final Set<String> _selectedInterests = {};

  static const Color _primaryPurple = Color(0xFF7C3AED);
  static const Color _lightPurple = Color(0xFFB829F7);
  static const Color _darkPurple = Color(0xFF4F46E5);
  static const Color _borderColor = Color(0xFFE2E8F0);
  static const Color _hintColor = Color(0xFF94A3B8);
  static const Color _labelColor = Color(0xFF1E293B);
  static const Color _backgroundColor = Color(0xFFF8F9FA);
  static const Color _inputFillColor = Color(0xFFF1F5F9);

  final List<String> _academicLevels = const [
    'المرحلة الثانوية',
    'البكالوريوس',
    'الماجستير',
    'الدكتوراه',
  ];

  final List<String> _interests = const [
    'الهندسة',
    'التسويق الرقمي',
    'إدارة الأعمال',
    'تصميم الجرافيك',
    'الذكاء الاصطناعي',
    'البرمجة',
    'الموسيقى',
    'الرياضة',
    'اللغات',
    'الفنون',
    'العلوم',
    'الطب',
  ];

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _specializationController.dispose();
    super.dispose();
  }

  // ✅ SIMPLE POP - GOES BACK TO WELCOME
  void _goBack() {
    Navigator.pop(context);
  }

  void _toggleInterest(String interest) {
    setState(() {
      if (_selectedInterests.contains(interest)) {
        _selectedInterests.remove(interest);
      } else {
        _selectedInterests.add(interest);
      }
    });
  }

  void _togglePasswordVisibility() {
    setState(() => _obscurePassword = !_obscurePassword);
  }

  void _toggleConfirmPasswordVisibility() {
    setState(() => _obscureConfirmPassword = !_obscureConfirmPassword);
  }

  void _handleTermsChanged(bool? value) {
    setState(() => _agreedToTerms = value ?? false);
  }

  void _showSuccessDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(_getText('تم بنجاح!', 'Success!')),
        content: Text(
          _getText('تم إنشاء حسابك بنجاح', 'Account created successfully'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(_getText('حسناً', 'OK')),
          ),
        ],
      ),
    );
  }

  void _showErrorSnackBar(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  void _submitForm() {
    if (!_formKey.currentState!.validate()) return;

    if (!_agreedToTerms) {
      _showErrorSnackBar(
        _getText(
          'يرجى الموافقة على الشروط والأحكام',
          'Please agree to Terms and Conditions',
        ),
      );
      return;
    }

    final formData = {
      'fullName': _nameController.text.trim(),
      'email': _emailController.text.trim(),
      'phone': _phoneController.text.trim(),
      'password': _passwordController.text,
      'specialization': _specializationController.text.trim(),
      'academicLevel': _selectedAcademicLevel,
      'interests': _selectedInterests.toList(),
    };

    debugPrint('Form Data: $formData');

    widget.onRegisterSuccess?.call();
    _showSuccessDialog();
  }

  String _getText(String arabic, String english) =>
      widget.isArabic ? arabic : english;

  InputDecoration _buildInputDecoration({
    required String hintText,
    Widget? suffixIcon,
  }) {
    return InputDecoration(
      hintText: hintText,
      hintStyle: const TextStyle(color: _hintColor, fontSize: 14),
      filled: true,
      fillColor: _inputFillColor,
      border: _buildBorder(_borderColor),
      enabledBorder: _buildBorder(_borderColor),
      focusedBorder: _buildBorder(_primaryPurple, width: 2),
      errorBorder: _buildBorder(Colors.red),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      suffixIcon: suffixIcon,
    );
  }

  OutlineInputBorder _buildBorder(Color color, {double width = 1}) {
    return OutlineInputBorder(
      borderRadius: BorderRadius.circular(12),
      borderSide: BorderSide(color: color, width: width),
    );
  }

  Widget _buildLabel(String text, IconData icon) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Text(
          text,
          style: const TextStyle(
            color: _labelColor,
            fontSize: 14,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(width: 8),
        Icon(icon, size: 18, color: _primaryPurple),
      ],
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required IconData icon,
    required String hint,
    TextInputType? keyboardType,
    bool obscureText = false,
    Widget? suffixIcon,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _buildLabel(label, icon),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          obscureText: obscureText,
          textDirection: TextDirection.ltr,
          validator: validator,
          decoration: _buildInputDecoration(
            hintText: hint,
            suffixIcon: suffixIcon,
          ),
        ),
      ],
    );
  }

  Widget _buildPasswordField({
    required TextEditingController controller,
    required String label,
    required bool isObscured,
    required VoidCallback onToggleVisibility,
    String? Function(String?)? validator,
  }) {
    return _buildTextField(
      controller: controller,
      label: label,
      icon: Icons.lock_outlined,
      hint: '••••••••',
      obscureText: isObscured,
      suffixIcon: IconButton(
        icon: Icon(
          isObscured
              ? Icons.visibility_off_outlined
              : Icons.visibility_outlined,
          color: _hintColor,
          size: 20,
        ),
        onPressed: onToggleVisibility,
      ),
      validator: validator,
    );
  }

  Widget _buildHeader() {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
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
              // ✅ BACK BUTTON ADDED HERE
              Row(
                children: [
                  IconButton(
                    icon: Icon(
                      widget.isArabic ? Icons.arrow_forward : Icons.arrow_back,
                      color: Colors.white,
                    ),
                    onPressed: _goBack,
                  ),
                  const Spacer(),
                ],
              ),
              Container(
                width: 80,
                height: 80,
                decoration: BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.1),
                      blurRadius: 10,
                      offset: const Offset(0, 4),
                    ),
                  ],
                ),
                child: const Icon(
                  Icons.person_add_outlined,
                  size: 40,
                  color: _primaryPurple,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                _getText('إنشاء حساب جديد', 'Create Account'),
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                _getText(
                  'املأ البيانات التالية للانضمام إلى منصتنا',
                  'Fill in your details to join our platform',
                ),
                textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.white70, fontSize: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAcademicLevelDropdown() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _buildLabel(
          _getText('المستوى الأكاديمي', 'Academic Level'),
          Icons.school_outlined,
        ),
        const SizedBox(height: 8),
        DropdownButtonFormField<String>(
          initialValue: _selectedAcademicLevel,
          decoration: _buildInputDecoration(
            hintText: _getText(
              'اختر المستوى الأكاديمي',
              'Select academic level',
            ),
          ),
          icon: const Icon(Icons.keyboard_arrow_down, color: _primaryPurple),
          items: _academicLevels.map((level) {
            return DropdownMenuItem(value: level, child: Text(level));
          }).toList(),
          onChanged: (value) => setState(() => _selectedAcademicLevel = value),
        ),
      ],
    );
  }

  Widget _buildInterestsSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _buildLabel(_getText('الاهتمامات', 'Interests'), Icons.favorite_border),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: _borderColor),
          ),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            alignment: WrapAlignment.center,
            children: _interests.map((interest) {
              final isSelected = _selectedInterests.contains(interest);
              return ChoiceChip(
                label: Text(interest),
                selected: isSelected,
                onSelected: (_) => _toggleInterest(interest),
                selectedColor: const Color(0xFFF3E8FF),
                backgroundColor: Colors.white,
                labelStyle: TextStyle(
                  color: isSelected ? _primaryPurple : const Color(0xFF64748B),
                  fontSize: 12,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                ),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(20),
                  side: BorderSide(
                    color: isSelected ? _primaryPurple : _borderColor,
                  ),
                ),
                padding: const EdgeInsets.symmetric(horizontal: 12),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildTermsSection() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: const Color(0xFFF8FAFC),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _borderColor),
      ),
      child: Row(
        children: [
          Checkbox(
            value: _agreedToTerms,
            onChanged: _handleTermsChanged,
            activeColor: _primaryPurple,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(4),
            ),
          ),
          Expanded(
            child: RichText(
              text: TextSpan(
                text: _getText('أوافق على ', 'I agree to '),
                style: const TextStyle(color: _labelColor, fontSize: 14),
                children: [
                  TextSpan(
                    text: _getText('الشروط والأحكام', 'Terms & Conditions'),
                    style: const TextStyle(
                      color: _primaryPurple,
                      fontWeight: FontWeight.bold,
                      decoration: TextDecoration.underline,
                    ),
                    recognizer: TapGestureRecognizer()
                      ..onTap = () => debugPrint('Terms tapped'),
                  ),
                  TextSpan(text: _getText(' و ', ' and ')),
                  TextSpan(
                    text: _getText('سياسة الخصوصية', 'Privacy Policy'),
                    style: const TextStyle(
                      color: _primaryPurple,
                      fontWeight: FontWeight.bold,
                      decoration: TextDecoration.underline,
                    ),
                    recognizer: TapGestureRecognizer()
                      ..onTap = () => debugPrint('Privacy tapped'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSubmitButton() {
    return Container(
      width: double.infinity,
      height: 56,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [_lightPurple, _primaryPurple, _darkPurple],
        ),
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: _primaryPurple.withValues(alpha: 0.3),
            blurRadius: 8,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: ElevatedButton(
        onPressed: _submitForm,
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent,
          shadowColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.person_add, color: Colors.white),
            const SizedBox(width: 8),
            Text(
              _getText('إنشاء الحساب', 'Create Account'),
              style: const TextStyle(
                color: Colors.white,
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSignInLink() {
    return Center(
      child: RichText(
        text: TextSpan(
          text: _getText('لديك حساب بالفعل؟ ', 'Already have an account? '),
          style: const TextStyle(color: Color(0xFF64748B), fontSize: 14),
          children: [
            TextSpan(
              text: _getText('تسجيل الدخول', 'Sign In'),
              style: const TextStyle(
                color: _primaryPurple,
                fontWeight: FontWeight.bold,
                decoration: TextDecoration.underline,
              ),
              recognizer: TapGestureRecognizer()
                ..onTap = () {
                  // ✅ USE PUSH (keeps Register in stack)
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => LoginPage(
                        isArabic: widget.isArabic,
                        onLoginSuccess: widget.onRegisterSuccess,
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
    );
  }

  Widget _buildHelpButton() {
    return Positioned(
      bottom: 20,
      right: 20,
      child: FloatingActionButton(
        onPressed: () {
          showDialog(
            context: context,
            builder: (context) => AlertDialog(
              title: Text(_getText('مساعدة', 'Help')),
              content: Text(
                _getText(
                  'هل تحتاج مساعدة في إنشاء حسابك؟\nتواصل مع فريق الدعم',
                  'Need help creating your account?\nContact our support team',
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: Text(_getText('إغلاق', 'Close')),
                ),
              ],
            ),
          );
        },
        backgroundColor: _labelColor,
        mini: true,
        child: const Icon(Icons.question_mark, color: Colors.white),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: widget.isArabic ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: _backgroundColor,
        body: SafeArea(
          child: Stack(
            children: [
              SingleChildScrollView(
                child: Form(
                  key: _formKey,
                  child: Column(
                    children: [
                      _buildHeader(),
                      const SizedBox(height: 24),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            _buildTextField(
                              controller: _nameController,
                              label: _getText('الاسم الثلاثي', 'Full Name'),
                              icon: Icons.person_outline,
                              hint: _getText(
                                'مثال: محمد أحمد علي',
                                'e.g. John Smith',
                              ),
                              validator: (value) =>
                                  value?.trim().isEmpty == true
                                  ? _getText(
                                      'الرجاء إدخال الاسم',
                                      'Please enter your name',
                                    )
                                  : null,
                            ),
                            const SizedBox(height: 20),
                            _buildTextField(
                              controller: _emailController,
                              label: _getText('البريد الإلكتروني', 'Email'),
                              icon: Icons.email_outlined,
                              hint: 'example@email.com',
                              keyboardType: TextInputType.emailAddress,
                              validator: (value) {
                                if (value?.trim().isEmpty == true) {
                                  return _getText(
                                    'الرجاء إدخال البريد',
                                    'Please enter your email',
                                  );
                                }
                                if (!value!.contains('@')) {
                                  return _getText(
                                    'بريد إلكتروني غير صالح',
                                    'Invalid email',
                                  );
                                }
                                return null;
                              },
                            ),
                            const SizedBox(height: 20),
                            _buildTextField(
                              controller: _phoneController,
                              label: _getText('رقم الجوال', 'Phone Number'),
                              icon: Icons.phone_outlined,
                              hint: _getText('05xxxxxxxx', '+1 234 567 8900'),
                              keyboardType: TextInputType.phone,
                              validator: (value) =>
                                  value?.trim().isEmpty == true
                                  ? _getText(
                                      'الرجاء إدخال رقم الجوال',
                                      'Please enter your phone',
                                    )
                                  : null,
                            ),
                            const SizedBox(height: 20),
                            _buildPasswordField(
                              controller: _passwordController,
                              label: _getText('كلمة السر', 'Password'),
                              isObscured: _obscurePassword,
                              onToggleVisibility: _togglePasswordVisibility,
                              validator: (value) =>
                                  value != null && value.length < 6
                                  ? _getText(
                                      'كلمة السر قصيرة جداً',
                                      'Password too short',
                                    )
                                  : null,
                            ),
                            const SizedBox(height: 20),
                            _buildPasswordField(
                              controller: _confirmPasswordController,
                              label: _getText(
                                'تأكيد كلمة السر',
                                'Confirm Password',
                              ),
                              isObscured: _obscureConfirmPassword,
                              onToggleVisibility:
                                  _toggleConfirmPasswordVisibility,
                              validator: (value) =>
                                  value != _passwordController.text
                                  ? _getText(
                                      'كلمتا السر غير متطابقتين',
                                      'Passwords do not match',
                                    )
                                  : null,
                            ),
                            const SizedBox(height: 20),
                            _buildTextField(
                              controller: _specializationController,
                              label: _getText('التخصص', 'Specialization'),
                              icon: Icons.menu_book_outlined,
                              hint: _getText(
                                'مثال: علوم الحاسب',
                                'e.g. Computer Science',
                              ),
                              validator: (value) =>
                                  value?.trim().isEmpty == true
                                  ? _getText(
                                      'الرجاء إدخال التخصص',
                                      'Please enter specialization',
                                    )
                                  : null,
                            ),
                            const SizedBox(height: 20),
                            _buildAcademicLevelDropdown(),
                            const SizedBox(height: 24),
                            _buildInterestsSection(),
                            const SizedBox(height: 24),
                            _buildTermsSection(),
                            const SizedBox(height: 24),
                            _buildSubmitButton(),
                            const SizedBox(height: 16),
                            _buildSignInLink(),
                            const SizedBox(height: 40),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              _buildHelpButton(),
            ],
          ),
        ),
      ),
    );
  }
}