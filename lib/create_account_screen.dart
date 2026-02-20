import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';

import 'login_page.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Create Account',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF00BCD4)),
        useMaterial3: true,
      ),
      home: const CreateAccountScreen(isArabic: false),
    );
  }
}

class CreateAccountScreen extends StatefulWidget {
  final bool isArabic;
  final VoidCallback? onRegisterSuccess;

  const CreateAccountScreen({
    super.key,
    required this.isArabic,
    this.onRegisterSuccess,
  });

  @override
  State<CreateAccountScreen> createState() => _CreateAccountScreenState();
}

class _CreateAccountScreenState extends State<CreateAccountScreen> {
  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _passwordController = TextEditingController();
  final _confirmPasswordController = TextEditingController();
  final _specializationController = TextEditingController();

  bool _obscurePassword = true;
  bool _obscureConfirmPassword = true;
  bool _agreeToTerms = false;
  String? _selectedAcademicLevel;
  final Set<String> _selectedInterests = {};

  late final List<String> _academicLevels;
  late final List<String> _interests;

  static const Color _primaryCyan = Color(0xFF00BCD4);
  static const Color _darkTeal = Color(0xFF00838F);
  static const Color _lightCyan = Color(0xFFB2EBF2);
  static const Color _inputBorderColor = Color(0xFF80DEEA);
  static const Color _inputFillColor = Color(0xFFF0F4F5);
  static const Color _labelColor = Color(0xFF263238);
  static const Color _hintColor = Color(0xFF9E9E9E);
  static const Color _gradientStart = Color(0xFF4DD0E1);
  static const Color _gradientEnd = Color(0xFF0288D1);

  @override
  void initState() {
    super.initState();
    if (widget.isArabic) {
      _academicLevels = [
        'ثانوية عامة',
        'بكالوريوس',
        'ماجستير',
        'دكتوراه',
        'دبلوم',
        'أخرى',
      ];
      _interests = [
        'البرمجة',
        'الذكاء الاصطناعي',
        'تصميم الجرافيك',
        'إدارة الأعمال',
        'التسويق الرقمي',
        'الهندسة',
        'الطب',
        'العلوم',
        'الفنون',
        'اللغات',
        'الرياضة',
        'الموسيقى',
      ];
    } else {
      _academicLevels = [
        'High School',
        'Bachelor\'s Degree',
        'Master\'s Degree',
        'PhD',
        'Diploma',
        'Other',
      ];
      _interests = [
        'Programming',
        'Artificial Intelligence',
        'Graphic Design',
        'Business Management',
        'Digital Marketing',
        'Engineering',
        'Medicine',
        'Science',
        'Arts',
        'Languages',
        'Sports',
        'Music',
      ];
    }
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _passwordController.dispose();
    _confirmPasswordController.dispose();
    _specializationController.dispose();
    super.dispose();
  }

  InputDecoration _buildInputDecoration({required String hintText}) {
    return InputDecoration(
      hintText: hintText,
      hintStyle: const TextStyle(
        color: _hintColor,
        fontSize: 15,
        fontWeight: FontWeight.w400,
      ),
      filled: true,
      fillColor: _inputFillColor,
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(30),
        borderSide: const BorderSide(color: _inputBorderColor, width: 1),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(30),
        borderSide: const BorderSide(color: _inputBorderColor, width: 1),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(30),
        borderSide: const BorderSide(color: _primaryCyan, width: 1.5),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(30),
        borderSide: const BorderSide(color: Colors.red, width: 1),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(30),
        borderSide: const BorderSide(color: Colors.red, width: 1.5),
      ),
    );
  }

  Widget _buildLabel({required IconData icon, required String text}) {
    return Padding(
      padding: EdgeInsets.only(
        bottom: 8,
        left: widget.isArabic ? 0 : 4,
        right: widget.isArabic ? 4 : 0,
      ),
      child: Row(
        textDirection: widget.isArabic ? TextDirection.rtl : TextDirection.ltr,
        children: [
          Icon(icon, size: 22, color: _darkTeal),
          const SizedBox(width: 8),
          Text(
            text,
            style: const TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w600,
              color: _labelColor,
            ),
          ),
        ],
      ),
    );
  }

  void _handleCreateAccount() {
    if (_formKey.currentState!.validate()) {
      if (!_agreeToTerms) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              widget.isArabic
                  ? 'يرجى الموافقة على الشروط والأحكام'
                  : 'Please agree to the Terms and Conditions',
            ),
            backgroundColor: Colors.red,
          ),
        );
        return;
      }

      final formData = {
        'fullName': _fullNameController.text,
        'email': _emailController.text,
        'phone': _phoneController.text,
        'password': _passwordController.text,
        'specialization': _specializationController.text,
        'academicLevel': _selectedAcademicLevel,
        'interests': _selectedInterests.toList(),
      };

      debugPrint('Form Data: $formData');

      widget.onRegisterSuccess?.call();

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.isArabic
                ? 'تم إنشاء الحساب بنجاح!'
                : 'Account created successfully!',
          ),
          backgroundColor: _primaryCyan,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: widget.isArabic ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: Colors.white,
        body: SafeArea(
          child: SingleChildScrollView(
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _buildHeader(),

                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 24),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const SizedBox(height: 28),

                        _buildLabel(
                          icon: Icons.person_outline,
                          text: widget.isArabic ? 'الاسم الكامل' : 'Full Name',
                        ),
                        TextFormField(
                          controller: _fullNameController,
                          decoration: _buildInputDecoration(
                            hintText: widget.isArabic
                                ? 'مثال: محمد أحمد علي'
                                : 'e.g., John Michael Smith',
                          ),
                          keyboardType: TextInputType.name,
                          textCapitalization: TextCapitalization.words,
                          validator: (value) {
                            if (value == null || value.trim().isEmpty) {
                              return widget.isArabic
                                  ? 'يرجى إدخال الاسم الكامل'
                                  : 'Please enter your full name';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        _buildLabel(
                          icon: Icons.mail_outline,
                          text: widget.isArabic
                              ? 'البريد الإلكتروني'
                              : 'Email Address',
                        ),
                        TextFormField(
                          controller: _emailController,
                          decoration: _buildInputDecoration(
                            hintText: widget.isArabic
                                ? 'example@email.com'
                                : 'example@email.com',
                          ),
                          keyboardType: TextInputType.emailAddress,
                          validator: (value) {
                            if (value == null || value.trim().isEmpty) {
                              return widget.isArabic
                                  ? 'يرجى إدخال البريد الإلكتروني'
                                  : 'Please enter your email';
                            }
                            if (!RegExp(
                              r'^[\w-\.]+@([\w-]+\.)+[\w-]{2,4}$',
                            ).hasMatch(value)) {
                              return widget.isArabic
                                  ? 'يرجى إدخال بريد إلكتروني صالح'
                                  : 'Please enter a valid email';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        _buildLabel(
                          icon: Icons.phone_outlined,
                          text: widget.isArabic ? 'رقم الهاتف' : 'Phone Number',
                        ),
                        TextFormField(
                          controller: _phoneController,
                          decoration: _buildInputDecoration(
                            hintText: widget.isArabic
                                ? '+966 5 1234 5678'
                                : '+1 234 567 8900',
                          ),
                          keyboardType: TextInputType.phone,
                          validator: (value) {
                            if (value == null || value.trim().isEmpty) {
                              return widget.isArabic
                                  ? 'يرجى إدخال رقم الهاتف'
                                  : 'Please enter your phone number';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        _buildLabel(
                          icon: Icons.lock_outline,
                          text: widget.isArabic ? 'كلمة المرور' : 'Password',
                        ),
                        TextFormField(
                          controller: _passwordController,
                          obscureText: _obscurePassword,
                          decoration:
                              _buildInputDecoration(
                                hintText: widget.isArabic
                                    ? '••••••••'
                                    : '••••••••',
                              ).copyWith(
                                suffixIcon: IconButton(
                                  icon: Icon(
                                    _obscurePassword
                                        ? Icons.visibility_off_outlined
                                        : Icons.visibility_outlined,
                                    color: _hintColor,
                                    size: 20,
                                  ),
                                  onPressed: () {
                                    setState(() {
                                      _obscurePassword = !_obscurePassword;
                                    });
                                  },
                                ),
                              ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return widget.isArabic
                                  ? 'يرجى إدخال كلمة المرور'
                                  : 'Please enter a password';
                            }
                            if (value.length < 6) {
                              return widget.isArabic
                                  ? 'يجب أن تكون كلمة المرور 6 أحرف على الأقل'
                                  : 'Password must be at least 6 characters';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        _buildLabel(
                          icon: Icons.lock_outline,
                          text: widget.isArabic
                              ? 'تأكيد كلمة المرور'
                              : 'Confirm Password',
                        ),
                        TextFormField(
                          controller: _confirmPasswordController,
                          obscureText: _obscureConfirmPassword,
                          decoration:
                              _buildInputDecoration(
                                hintText: widget.isArabic
                                    ? '••••••••'
                                    : '••••••••',
                              ).copyWith(
                                suffixIcon: IconButton(
                                  icon: Icon(
                                    _obscureConfirmPassword
                                        ? Icons.visibility_off_outlined
                                        : Icons.visibility_outlined,
                                    color: _hintColor,
                                    size: 20,
                                  ),
                                  onPressed: () {
                                    setState(() {
                                      _obscureConfirmPassword =
                                          !_obscureConfirmPassword;
                                    });
                                  },
                                ),
                              ),
                          validator: (value) {
                            if (value == null || value.isEmpty) {
                              return widget.isArabic
                                  ? 'يرجى تأكيد كلمة المرور'
                                  : 'Please confirm your password';
                            }
                            if (value != _passwordController.text) {
                              return widget.isArabic
                                  ? 'كلمات المرور غير متطابقة'
                                  : 'Passwords do not match';
                            }
                            return null;
                          },
                        ),
                        const SizedBox(height: 20),

                        _buildLabel(
                          icon: Icons.menu_book_outlined,
                          text: widget.isArabic ? 'التخصص' : 'Specialization',
                        ),
                        TextFormField(
                          controller: _specializationController,
                          decoration: _buildInputDecoration(
                            hintText: widget.isArabic
                                ? 'مثال: علوم الحاسب'
                                : 'e.g., Computer Science',
                          ),
                          textCapitalization: TextCapitalization.words,
                        ),
                        const SizedBox(height: 20),

                        _buildLabel(
                          icon: Icons.school_outlined,
                          text: widget.isArabic
                              ? 'المستوى الأكاديمي'
                              : 'Academic Level',
                        ),
                        DropdownButtonFormField<String>(
                          initialValue: _selectedAcademicLevel,
                          decoration: _buildInputDecoration(
                            hintText: widget.isArabic
                                ? 'اختر مستواك الأكاديمي'
                                : 'Select your academic level',
                          ),
                          icon: Icon(
                            widget.isArabic
                                ? Icons.keyboard_arrow_left
                                : Icons.keyboard_arrow_down,
                            color: _hintColor,
                          ),
                          items: _academicLevels.map((level) {
                            return DropdownMenuItem<String>(
                              value: level,
                              child: Text(level),
                            );
                          }).toList(),
                          onChanged: (value) {
                            setState(() {
                              _selectedAcademicLevel = value;
                            });
                          },
                        ),
                        const SizedBox(height: 24),

                        _buildLabel(
                          icon: Icons.favorite_outline,
                          text: widget.isArabic ? 'الاهتمامات' : 'Interests',
                        ),
                        _buildInterestsSection(),
                        const SizedBox(height: 24),

                        _buildTermsSection(),
                        const SizedBox(height: 24),

                        _buildCreateAccountButton(),
                        const SizedBox(height: 20),

                        _buildSignInLink(),
                        const SizedBox(height: 32),
                      ],
                    ),
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
      padding: const EdgeInsets.symmetric(vertical: 36),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF4DD0E1), Color(0xFF26C6DA), Color(0xFF00ACC1)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(32),
          bottomRight: Radius.circular(32),
        ),
        boxShadow: [
          BoxShadow(
            color: _primaryCyan.withValues(alpha: .3),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(color: Colors.white, width: 2.5),
            ),
            child: const Icon(
              Icons.person_add_outlined,
              size: 40,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 16),
          Text(
            widget.isArabic ? 'إنشاء حساب جديد' : 'Create New Account',
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: Colors.white,
            ),
          ),
          const SizedBox(height: 8),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 40),
            child: Text(
              widget.isArabic
                  ? 'املأ المعلومات أدناه للانضمام إلى منصتنا'
                  : 'Fill in the information below to join our platform',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 15,
                color: Colors.white70,
                height: 1.4,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInterestsSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _inputBorderColor, width: 1),
      ),
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        children: _interests.map((interest) {
          final isSelected = _selectedInterests.contains(interest);
          return GestureDetector(
            onTap: () {
              setState(() {
                if (isSelected) {
                  _selectedInterests.remove(interest);
                } else {
                  _selectedInterests.add(interest);
                }
              });
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
              decoration: BoxDecoration(
                color: isSelected
                    ? _primaryCyan.withValues(alpha: 0.15)
                    : Colors.white,
                borderRadius: BorderRadius.circular(24),
                border: Border.all(
                  color: isSelected ? _primaryCyan : _inputBorderColor,
                  width: isSelected ? 1.5 : 1,
                ),
              ),
              child: Text(
                interest,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w400,
                  color: isSelected
                      ? _darkTeal
                      : _darkTeal.withValues(alpha: 0.8),
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildTermsSection() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
      decoration: BoxDecoration(
        color: _lightCyan.withValues(alpha: 0.25),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: _inputBorderColor, width: 1),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          SizedBox(
            width: 24,
            height: 24,
            child: Checkbox(
              value: _agreeToTerms,
              onChanged: (value) {
                setState(() {
                  _agreeToTerms = value ?? false;
                });
              },
              activeColor: _primaryCyan,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(4),
              ),
              side: const BorderSide(color: _hintColor, width: 1.5),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: RichText(
              textDirection: widget.isArabic
                  ? TextDirection.rtl
                  : TextDirection.ltr,
              text: TextSpan(
                style: const TextStyle(fontSize: 14, color: _labelColor),
                children: [
                  TextSpan(
                    text: widget.isArabic ? 'أوافق على ' : 'I agree to the ',
                  ),
                  TextSpan(
                    text: widget.isArabic
                        ? 'الشروط والأحكام'
                        : 'Terms and Conditions',
                    style: const TextStyle(
                      color: _primaryCyan,
                      decoration: TextDecoration.underline,
                      fontWeight: FontWeight.w500,
                    ),
                    recognizer: TapGestureRecognizer()
                      ..onTap = () {
                        debugPrint('Terms and Conditions tapped');
                      },
                  ),
                  TextSpan(text: widget.isArabic ? ' و' : ' and '),
                  TextSpan(
                    text: widget.isArabic ? 'سياسة الخصوصية' : 'Privacy Policy',
                    style: const TextStyle(
                      color: _primaryCyan,
                      decoration: TextDecoration.underline,
                      fontWeight: FontWeight.w500,
                    ),
                    recognizer: TapGestureRecognizer()
                      ..onTap = () {
                        debugPrint('Privacy Policy tapped');
                      },
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCreateAccountButton() {
    return Container(
      height: 54,
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [_gradientStart, _gradientEnd],
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
        ),
        borderRadius: BorderRadius.circular(30),
        boxShadow: [
          BoxShadow(
            color: _primaryCyan.withValues(alpha: 0.35),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: ElevatedButton(
        onPressed: _handleCreateAccount,
        style: ElevatedButton.styleFrom(
          backgroundColor: Colors.transparent,
          shadowColor: Colors.transparent,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(30),
          ),
          padding: const EdgeInsets.symmetric(vertical: 14),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(
              Icons.person_add_outlined,
              color: Colors.white,
              size: 22,
            ),
            const SizedBox(width: 10),
            Text(
              widget.isArabic ? 'إنشاء حساب' : 'Create Account',
              style: const TextStyle(
                fontSize: 17,
                fontWeight: FontWeight.w600,
                color: Colors.white,
                letterSpacing: 0.5,
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
        textDirection: widget.isArabic ? TextDirection.rtl : TextDirection.ltr,
        text: TextSpan(
          style: TextStyle(fontSize: 15, color: _darkTeal),
          children: [
            TextSpan(
              text: widget.isArabic
                  ? 'هل لديك حساب بالفعل؟ '
                  : 'Already have an account? ',
            ),
            TextSpan(
              text: widget.isArabic ? 'تسجيل الدخول' : 'Sign In',
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: _primaryCyan,
                decoration: TextDecoration.underline,
              ),
              recognizer: TapGestureRecognizer()
                ..onTap = () {
                  debugPrint('Sign In tapped');
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => LoginPage(isArabic: widget.isArabic),
                    ),
                  );
                },
            ),
          ],
        ),
      ),
    );
  }
}
