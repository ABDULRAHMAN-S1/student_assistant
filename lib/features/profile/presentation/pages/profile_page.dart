import 'package:flutter/material.dart';

import '../../../engagement/data/remote/engagement_api_client.dart';
import '../../../engagement/data/repositories/engagement_repository.dart';
import '../../../engagement/data/repositories/engagement_repository_impl.dart';
import '../../../engagement/domain/models/notification_category_preference_update.dart';
import '../../../engagement/domain/models/notification_preferences.dart';
import '../../data/demo/demo_profile_repository.dart';
import '../../data/local/profile_store.dart';
import '../../domain/models/academic_context.dart';
import '../../domain/models/student_profile.dart';

class ProfilePage extends StatefulWidget {
  const ProfilePage({super.key, required this.isArabic});

  final bool isArabic;

  @override
  State<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends State<ProfilePage> {
  final _formKey = GlobalKey<FormState>();
  final _fullNameController = TextEditingController();
  final _emailController = TextEditingController();
  final _phoneController = TextEditingController();
  final _specializationController = TextEditingController();
  final _trackController = TextEditingController();
  final _currentSemesterController = TextEditingController();
  final _courseIdController = TextEditingController();
  final EngagementRepository _engagementRepository = EngagementRepositoryImpl();

  bool _isLoading = true;
  bool _isSaving = false;
  bool _isSavingPreferences = false;
  StudentProfile? _loadedProfile;
  String? _selectedAcademicLevel;
  final Set<String> _selectedInterests = <String>{};
  final List<String> _enrolledCourseIds = <String>[];
  NotificationPreferences _notificationPreferences =
      const NotificationPreferences();

  static const Color _backgroundColor = Color(0xFFFBF4FC);
  static const Color _cardColor = Colors.white;
  static const Color _primaryPurple = Color(0xFF7B2CFF);
  static const Color _primaryBlue = Color(0xFF2F6CFF);
  static const Color _borderColor = Color(0x1A000000);
  static const Color _mutedText = Color(0xFF717182);
  static const Color _primaryText = Color(0xFF030213);

  static const List<_ProfileOption> _academicLevels = [
    _ProfileOption(
      value: 'High School',
      arabic: 'المرحلة الثانوية',
      english: 'High School',
    ),
    _ProfileOption(
      value: 'Bachelor',
      arabic: 'البكالوريوس',
      english: 'Bachelor',
    ),
    _ProfileOption(value: 'Master', arabic: 'الماجستير', english: 'Master'),
    _ProfileOption(value: 'PhD', arabic: 'الدكتوراه', english: 'PhD'),
  ];

  static const List<_ProfileOption> _interestOptions = [
    _ProfileOption(
      value: 'Engineering',
      arabic: 'الهندسة',
      english: 'Engineering',
    ),
    _ProfileOption(
      value: 'Digital Marketing',
      arabic: 'التسويق الرقمي',
      english: 'Digital Marketing',
    ),
    _ProfileOption(
      value: 'Business Administration',
      arabic: 'إدارة الأعمال',
      english: 'Business Administration',
    ),
    _ProfileOption(
      value: 'Graphic Design',
      arabic: 'تصميم الجرافيك',
      english: 'Graphic Design',
    ),
    _ProfileOption(
      value: 'Artificial Intelligence',
      arabic: 'الذكاء الاصطناعي',
      english: 'Artificial Intelligence',
    ),
    _ProfileOption(
      value: 'Programming',
      arabic: 'البرمجة',
      english: 'Programming',
    ),
    _ProfileOption(value: 'Music', arabic: 'الموسيقى', english: 'Music'),
    _ProfileOption(value: 'Sports', arabic: 'الرياضة', english: 'Sports'),
    _ProfileOption(value: 'Languages', arabic: 'اللغات', english: 'Languages'),
    _ProfileOption(value: 'Arts', arabic: 'الفنون', english: 'Arts'),
    _ProfileOption(value: 'Science', arabic: 'العلوم', english: 'Science'),
    _ProfileOption(value: 'Medicine', arabic: 'الطب', english: 'Medicine'),
  ];

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  @override
  void dispose() {
    _fullNameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _specializationController.dispose();
    _trackController.dispose();
    _currentSemesterController.dispose();
    _courseIdController.dispose();
    super.dispose();
  }

  Future<void> _loadProfile() async {
    final profileStore = await ProfileStore.open();
    final repository = DemoProfileRepository(profileStore: profileStore);
    final profile = await repository.loadProfile();

    if (!mounted) return;

    _loadedProfile = profile;
    _fullNameController.text = profile?.fullName ?? '';
    _emailController.text = profile?.email ?? '';
    _phoneController.text = profile?.phoneNumber ?? '';
    _specializationController.text =
        profile?.academicContext.specialization ?? '';
    _trackController.text = '';
    _currentSemesterController.text =
        profile?.academicContext.currentSemester ?? '';
    _selectedAcademicLevel = _normalizeAcademicLevel(
      profile?.academicContext.academicLevel,
    );
    _selectedInterests
      ..clear()
      ..addAll(
        (profile?.academicContext.interests ?? const <String>[])
            .map(_normalizeInterest)
            .where((value) => value.isNotEmpty),
      );
    _enrolledCourseIds
      ..clear()
      ..addAll(
        (profile?.academicContext.enrolledCourseIds ?? const <String>[])
            .map(_normalizeCourseId)
            .where((value) => value.isNotEmpty),
      );

    try {
      final remoteProfile = await _engagementRepository.getProfile();
      if (!mounted) return;
      _specializationController.text = remoteProfile.major;
      _trackController.text = remoteProfile.track;
      _selectedAcademicLevel = _normalizeAcademicLevel(
        remoteProfile.academicLevel,
      );
      _selectedInterests
        ..clear()
        ..addAll(
          remoteProfile.interests
              .map(_normalizeInterest)
              .where((value) => value.isNotEmpty),
        );
      _notificationPreferences = await _engagementRepository
          .getNotificationPreferences();
    } catch (_) {
      // Keep local profile behavior even when backend profile sync fails.
    }

    setState(() {
      _isLoading = false;
    });
  }

  String _t(String arabic, String english) =>
      widget.isArabic ? arabic : english;

  String _normalizeAcademicLevel(String? rawValue) {
    if (rawValue == null || rawValue.trim().isEmpty) {
      return '';
    }

    final normalized = rawValue.trim().toLowerCase();
    for (final option in _academicLevels) {
      final candidates = {
        option.value.toLowerCase(),
        option.arabic.toLowerCase(),
        option.english.toLowerCase(),
      };
      if (candidates.contains(normalized)) {
        return option.value;
      }
    }
    return rawValue.trim();
  }

  String _normalizeInterest(String rawValue) {
    final normalized = rawValue.trim().toLowerCase();
    for (final option in _interestOptions) {
      final candidates = {
        option.value.toLowerCase(),
        option.arabic.toLowerCase(),
        option.english.toLowerCase(),
      };
      if (candidates.contains(normalized)) {
        return option.value;
      }
    }
    return rawValue.trim();
  }

  String _normalizeCourseId(String rawValue) {
    return rawValue.trim().toLowerCase();
  }

  List<DropdownMenuItem<String>> _academicLevelItems() {
    final items = _academicLevels
        .map(
          (option) => DropdownMenuItem<String>(
            value: option.value,
            child: Text(option.label(widget.isArabic)),
          ),
        )
        .toList(growable: true);

    if (_selectedAcademicLevel != null &&
        _selectedAcademicLevel!.isNotEmpty &&
        !_academicLevels.any(
          (option) => option.value == _selectedAcademicLevel,
        )) {
      items.add(
        DropdownMenuItem<String>(
          value: _selectedAcademicLevel,
          child: Text(_selectedAcademicLevel!),
        ),
      );
    }

    return items;
  }

  String _interestLabel(String value) {
    for (final option in _interestOptions) {
      if (option.value == value) {
        return option.label(widget.isArabic);
      }
    }
    return value;
  }

  InputDecoration _inputDecoration(String hintText, {Widget? suffixIcon}) {
    return InputDecoration(
      hintText: hintText,
      hintStyle: const TextStyle(color: _mutedText, fontSize: 14),
      filled: true,
      fillColor: const Color(0xFFF8F9FA),
      suffixIcon: suffixIcon,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: _borderColor),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: _borderColor),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(14),
        borderSide: const BorderSide(color: _primaryPurple, width: 1.6),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    );
  }

  Widget _buildSectionCard({
    required String title,
    required IconData icon,
    required List<Widget> children,
  }) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: _cardColor,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: _borderColor),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0F000000),
            blurRadius: 7,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: _primaryBlue.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: _primaryBlue),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 17.5,
                    fontWeight: FontWeight.w800,
                    color: _primaryText,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 18),
          ...children,
        ],
      ),
    );
  }

  Widget _buildFieldLabel(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 9),
      child: Text(
        text,
        style: const TextStyle(
          fontSize: 13.5,
          fontWeight: FontWeight.w700,
          color: _primaryText,
        ),
      ),
    );
  }

  Widget _buildTextField({
    required TextEditingController controller,
    required String label,
    required String hint,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
    bool forceLtr = false,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildFieldLabel(label),
        TextFormField(
          controller: controller,
          keyboardType: keyboardType,
          validator: validator,
          style: const TextStyle(fontSize: 14.5, height: 1.45),
          textAlign: widget.isArabic && !forceLtr
              ? TextAlign.right
              : TextAlign.left,
          textDirection: forceLtr
              ? TextDirection.ltr
              : (widget.isArabic ? TextDirection.rtl : TextDirection.ltr),
          decoration: _inputDecoration(hint),
        ),
      ],
    );
  }

  void _addCourseIdsFromInput() {
    final raw = _courseIdController.text.trim();
    if (raw.isEmpty) return;

    final values = raw
        .split(RegExp(r'[,;\n]'))
        .map(_normalizeCourseId)
        .where((value) => value.isNotEmpty)
        .toList(growable: false);

    setState(() {
      for (final value in values) {
        if (!_enrolledCourseIds.contains(value)) {
          _enrolledCourseIds.add(value);
        }
      }
      _courseIdController.clear();
    });
  }

  Future<void> _setNotificationPreferences({
    bool? enablePush,
    bool? enableInApp,
    List<NotificationCategoryPreferenceUpdate> categories = const [],
  }) async {
    setState(() {
      _isSavingPreferences = true;
    });
    try {
      final updated = await _engagementRepository.updateNotificationPreferences(
        enablePush: enablePush,
        enableInApp: enableInApp,
        categories: categories,
      );
      if (!mounted) return;
      setState(() {
        _notificationPreferences = updated;
      });
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _t(
              'تعذر تحديث تفضيلات الإشعارات.',
              'Could not update notification preferences.',
            ),
          ),
        ),
      );
    } finally {
      if (mounted) {
        setState(() {
          _isSavingPreferences = false;
        });
      }
    }
  }

  bool _categoryPushEnabled(String category) {
    NotificationCategoryPreference? match;
    for (final item in _notificationPreferences.categories) {
      if (item.category == category) {
        match = item;
        break;
      }
    }
    return match?.enablePush ?? _notificationPreferences.enablePush;
  }

  bool _categoryInAppEnabled(String category) {
    NotificationCategoryPreference? match;
    for (final item in _notificationPreferences.categories) {
      if (item.category == category) {
        match = item;
        break;
      }
    }
    return match?.enableInApp ?? _notificationPreferences.enableInApp;
  }

  Widget _buildPreferenceSwitch({
    required String titleAr,
    required String titleEn,
    required String subtitleAr,
    required String subtitleEn,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    return SwitchListTile.adaptive(
      contentPadding: EdgeInsets.zero,
      value: value,
      onChanged: _isSavingPreferences ? null : onChanged,
      title: Text(
        _t(titleAr, titleEn),
        style: const TextStyle(
          color: _primaryText,
          fontWeight: FontWeight.w700,
        ),
      ),
      subtitle: Text(
        _t(subtitleAr, subtitleEn),
        style: const TextStyle(color: _mutedText, height: 1.35),
      ),
    );
  }

  StudentProfile _buildUpdatedProfile() {
    final now = DateTime.now();
    final existing = _loadedProfile;

    return StudentProfile(
      id: existing?.id.isNotEmpty == true
          ? existing!.id
          : (_emailController.text.trim().isNotEmpty
                ? _emailController.text.trim().toLowerCase()
                : 'local-${now.millisecondsSinceEpoch}'),
      fullName: _fullNameController.text.trim(),
      email: _emailController.text.trim(),
      phoneNumber: _phoneController.text.trim(),
      preferredLanguageCode: widget.isArabic ? 'ar' : 'en',
      createdAt: existing?.createdAt ?? now,
      updatedAt: now,
      academicContext: AcademicContext(
        specialization: _specializationController.text.trim(),
        academicLevel: _selectedAcademicLevel?.trim().isEmpty ?? true
            ? null
            : _selectedAcademicLevel,
        interests: _selectedInterests.toList(growable: false),
        currentSemester: _currentSemesterController.text.trim().isEmpty
            ? null
            : _currentSemesterController.text.trim(),
        enrolledCourseIds: _enrolledCourseIds.toList(growable: false),
      ),
    );
  }

  Future<void> _saveProfile() async {
    if (_courseIdController.text.trim().isNotEmpty) {
      _addCourseIdsFromInput();
    }
    if (!_formKey.currentState!.validate()) return;

    setState(() {
      _isSaving = true;
    });

    try {
      final profileStore = await ProfileStore.open();
      final repository = DemoProfileRepository(profileStore: profileStore);
      final updatedProfile = _buildUpdatedProfile();
      await repository.saveProfile(updatedProfile);
      var remoteSyncFailed = false;
      try {
        await _engagementRepository.updateProfile(
          major: _specializationController.text.trim(),
          academicLevel: (_selectedAcademicLevel ?? '').trim(),
          track: _trackController.text.trim(),
          interests: _selectedInterests.toList(growable: false),
        );
      } on EngagementApiException {
        remoteSyncFailed = true;
      }

      if (!mounted) return;
      setState(() {
        _loadedProfile = updatedProfile;
        _isSaving = false;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            remoteSyncFailed
                ? _t(
                    'تم حفظ الملف محليًا، وتعذر مزامنته مع الخادم.',
                    'Profile saved locally, but server sync failed.',
                  )
                : _t(
                    'تم حفظ الملف الأكاديمي ومزامنته.',
                    'Profile saved and synced successfully.',
                  ),
          ),
        ),
      );
      Navigator.of(context).pop(true);
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _isSaving = false;
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _t(
              'تعذر حفظ البيانات الآن.',
              'Could not save the profile right now.',
            ),
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _backgroundColor,
      appBar: AppBar(
        backgroundColor: _cardColor,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        title: Text(
          _t('الملف الأكاديمي', 'Academic Profile'),
          style: const TextStyle(
            color: _primaryText,
            fontWeight: FontWeight.w800,
          ),
        ),
        iconTheme: const IconThemeData(color: _primaryText),
        actions: [
          TextButton(
            onPressed: _isLoading || _isSaving ? null : _saveProfile,
            child: _isSaving
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : Text(
                    _t('حفظ', 'Save'),
                    style: const TextStyle(
                      color: _primaryPurple,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : Form(
              key: _formKey,
              child: ListView(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(
                        colors: [Color(0xFF2F6CFF), Color(0xFF7B2CFF)],
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                      ),
                      borderRadius: BorderRadius.circular(22),
                    ),
                    child: Row(
                      children: [
                        Container(
                          width: 54,
                          height: 54,
                          decoration: BoxDecoration(
                            color: Colors.white.withValues(alpha: 0.18),
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(
                            Icons.person_outline,
                            color: Colors.white,
                            size: 28,
                          ),
                        ),
                        const SizedBox(width: 14),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                _loadedProfile?.fullName.trim().isNotEmpty ==
                                        true
                                    ? _loadedProfile!.fullName
                                    : _t('ملف الطالب', 'Student Profile'),
                                style: const TextStyle(
                                  color: Colors.white,
                                  fontSize: 18,
                                  fontWeight: FontWeight.w800,
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                _t(
                                  'راجع بياناتك الأكاديمية وعدّلها محليًا عند الحاجة.',
                                  'Review and update your academic details locally.',
                                ),
                                style: TextStyle(
                                  color: Colors.white.withValues(alpha: 0.9),
                                  height: 1.4,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  _buildSectionCard(
                    title: _t('البيانات الشخصية', 'Personal Details'),
                    icon: Icons.badge_outlined,
                    children: [
                      _buildTextField(
                        controller: _fullNameController,
                        label: _t('الاسم الكامل', 'Full name'),
                        hint: _t('اكتب اسمك الكامل', 'Enter your full name'),
                        validator: (value) {
                          if ((value ?? '').trim().isEmpty) {
                            return _t('الاسم مطلوب', 'Name is required');
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 14),
                      _buildTextField(
                        controller: _emailController,
                        label: _t('البريد الإلكتروني', 'Email'),
                        hint: _t(
                          'student@taibahu.edu.sa',
                          'student@taibahu.edu.sa',
                        ),
                        keyboardType: TextInputType.emailAddress,
                        forceLtr: true,
                        validator: (value) {
                          final trimmed = (value ?? '').trim();
                          if (trimmed.isEmpty) {
                            return _t(
                              'البريد الإلكتروني مطلوب',
                              'Email is required',
                            );
                          }
                          if (!trimmed.contains('@')) {
                            return _t(
                              'أدخل بريدًا صحيحًا',
                              'Enter a valid email',
                            );
                          }
                          return null;
                        },
                      ),
                      const SizedBox(height: 14),
                      _buildTextField(
                        controller: _phoneController,
                        label: _t('رقم الجوال', 'Phone number'),
                        hint: _t('05XXXXXXXX', '05XXXXXXXX'),
                        keyboardType: TextInputType.phone,
                        forceLtr: true,
                      ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _buildSectionCard(
                    title: _t('السياق الأكاديمي', 'Academic Context'),
                    icon: Icons.school_outlined,
                    children: [
                      _buildTextField(
                        controller: _specializationController,
                        label: _t('التخصص', 'Specialization'),
                        hint: _t(
                          'مثل: علوم الحاسب',
                          'Example: Computer Science',
                        ),
                      ),
                      const SizedBox(height: 14),
                      _buildTextField(
                        controller: _trackController,
                        label: _t('المسار', 'Track'),
                        hint: _t(
                          'مثل: مسار البرمجيات',
                          'Example: Software Track',
                        ),
                      ),
                      const SizedBox(height: 14),
                      _buildFieldLabel(
                        _t('المستوى الأكاديمي', 'Academic level'),
                      ),
                      DropdownButtonFormField<String>(
                        initialValue: _selectedAcademicLevel?.isEmpty ?? true
                            ? null
                            : _selectedAcademicLevel,
                        items: _academicLevelItems(),
                        onChanged: (value) {
                          setState(() {
                            _selectedAcademicLevel = value;
                          });
                        },
                        decoration: _inputDecoration(
                          _t('اختر المستوى الأكاديمي', 'Select academic level'),
                        ),
                      ),
                      const SizedBox(height: 14),
                      _buildTextField(
                        controller: _currentSemesterController,
                        label: _t('الفصل الحالي', 'Current semester'),
                        hint: _t('مثل: الفصل الأول 1447', 'Example: Fall 2026'),
                      ),
                      const SizedBox(height: 14),
                      _buildFieldLabel(_t('الاهتمامات', 'Interests')),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _interestOptions
                            .map((option) {
                              final selected = _selectedInterests.contains(
                                option.value,
                              );
                              return ChoiceChip(
                                label: Text(option.label(widget.isArabic)),
                                selected: selected,
                                onSelected: (_) {
                                  setState(() {
                                    if (selected) {
                                      _selectedInterests.remove(option.value);
                                    } else {
                                      _selectedInterests.add(option.value);
                                    }
                                  });
                                },
                              );
                            })
                            .toList(growable: false),
                      ),
                      if (_selectedInterests.isNotEmpty) ...[
                        const SizedBox(height: 12),
                        Text(
                          _t('الاهتمامات المحددة', 'Selected interests'),
                          style: const TextStyle(
                            fontSize: 12,
                            color: _mutedText,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _selectedInterests
                              .map(
                                (interest) => Chip(
                                  label: Text(_interestLabel(interest)),
                                  onDeleted: () {
                                    setState(() {
                                      _selectedInterests.remove(interest);
                                    });
                                  },
                                ),
                              )
                              .toList(growable: false),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 16),
                  _buildSectionCard(
                    title: _t('المقررات الحالية', 'Current Courses'),
                    icon: Icons.menu_book_outlined,
                    children: [
                      _buildFieldLabel(
                        _t(
                          'المقررات أو المعرفات المسجلة',
                          'Enrolled course ids',
                        ),
                      ),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _courseIdController,
                              textDirection: TextDirection.ltr,
                              decoration: _inputDecoration(
                                _t(
                                  'مثل: programming أو cs101',
                                  'Example: programming or cs101',
                                ),
                              ),
                              onSubmitted: (_) => _addCourseIdsFromInput(),
                            ),
                          ),
                          const SizedBox(width: 10),
                          ElevatedButton(
                            onPressed: _addCourseIdsFromInput,
                            style: ElevatedButton.styleFrom(
                              backgroundColor: _primaryPurple,
                              foregroundColor: Colors.white,
                              padding: const EdgeInsets.symmetric(
                                horizontal: 16,
                                vertical: 14,
                              ),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(14),
                              ),
                            ),
                            child: Text(_t('إضافة', 'Add')),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      if (_enrolledCourseIds.isEmpty)
                        Text(
                          _t(
                            'لم تتم إضافة مقررات بعد.',
                            'No enrolled course ids added yet.',
                          ),
                          style: const TextStyle(
                            color: _mutedText,
                            height: 1.4,
                          ),
                        )
                      else
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: _enrolledCourseIds
                              .map(
                                (courseId) => Chip(
                                  label: Text(courseId),
                                  onDeleted: () {
                                    setState(() {
                                      _enrolledCourseIds.remove(courseId);
                                    });
                                  },
                                ),
                              )
                              .toList(growable: false),
                        ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _buildSectionCard(
                    title: _t('تفضيلات الإشعارات', 'Notification Preferences'),
                    icon: Icons.notifications_outlined,
                    children: [
                      if (_isSavingPreferences)
                        const LinearProgressIndicator(minHeight: 2),
                      _buildPreferenceSwitch(
                        titleAr: 'الإشعارات الفورية',
                        titleEn: 'Push notifications',
                        subtitleAr:
                            'استلام إشعارات الدفع عندما يكون التطبيق في الخلفية أو مغلقًا.',
                        subtitleEn:
                            'Receive push notifications when the app is in background or closed.',
                        value: _notificationPreferences.enablePush,
                        onChanged: (value) {
                          _setNotificationPreferences(enablePush: value);
                        },
                      ),
                      _buildPreferenceSwitch(
                        titleAr: 'الإشعارات داخل التطبيق',
                        titleEn: 'In-app notifications',
                        subtitleAr:
                            'إظهار الإشعارات داخل قائمة التنبيهات داخل التطبيق.',
                        subtitleEn:
                            'Show notifications inside the in-app notification inbox.',
                        value: _notificationPreferences.enableInApp,
                        onChanged: (value) {
                          _setNotificationPreferences(enableInApp: value);
                        },
                      ),
                      const Divider(height: 24),
                      _buildPreferenceSwitch(
                        titleAr: 'تنبيهات الفعاليات',
                        titleEn: 'Event alerts',
                        subtitleAr: 'الإشعارات المرتبطة بالفعاليات والأنشطة.',
                        subtitleEn:
                            'Notifications related to events and activities.',
                        value: _categoryPushEnabled('live_event'),
                        onChanged: (value) {
                          _setNotificationPreferences(
                            categories: [
                              NotificationCategoryPreferenceUpdate(
                                category: 'live_event',
                                enablePush: value,
                                enableInApp: _categoryInAppEnabled(
                                  'live_event',
                                ),
                              ),
                            ],
                          );
                        },
                      ),
                      _buildPreferenceSwitch(
                        titleAr: 'تنبيهات الفرص والمواعيد',
                        titleEn: 'Opportunity and deadline alerts',
                        subtitleAr:
                            'الإشعارات المرتبطة بالفرص والمواعيد الأكاديمية.',
                        subtitleEn:
                            'Notifications for opportunities and academic deadlines.',
                        value: _categoryPushEnabled('live_opportunity'),
                        onChanged: (value) {
                          _setNotificationPreferences(
                            categories: [
                              NotificationCategoryPreferenceUpdate(
                                category: 'live_opportunity',
                                enablePush: value,
                                enableInApp: _categoryInAppEnabled(
                                  'live_opportunity',
                                ),
                              ),
                              NotificationCategoryPreferenceUpdate(
                                category: 'live_deadline',
                                enablePush: value,
                                enableInApp: _categoryInAppEnabled(
                                  'live_deadline',
                                ),
                              ),
                            ],
                          );
                        },
                      ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  SizedBox(
                    height: 52,
                    child: ElevatedButton(
                      onPressed: _isSaving ? null : _saveProfile,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _primaryPurple,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(16),
                        ),
                      ),
                      child: _isSaving
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.white,
                              ),
                            )
                          : Text(
                              _t('حفظ التغييرات', 'Save changes'),
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                    ),
                  ),
                ],
              ),
            ),
    );
  }
}

class _ProfileOption {
  const _ProfileOption({
    required this.value,
    required this.arabic,
    required this.english,
  });

  final String value;
  final String arabic;
  final String english;

  String label(bool isArabic) => isArabic ? arabic : english;
}
