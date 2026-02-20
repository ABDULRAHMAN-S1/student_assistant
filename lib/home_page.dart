import 'package:flutter/material.dart';

import 'courses_page.dart';
import 'custom_dialog.dart';
import 'custom_toast.dart';
import 'events_page.dart';
import 'login_page.dart';
import 'reviews_page.dart';
import 'services/ai_chat_page.dart';

class AppColors {
  static const background = Color(0xFFFBF4FC);
  static const card = Color(0xFFFFFFFF);
  static const primaryText = Color(0xFF030213);
  static const mutedText = Color(0xFF717182);
  static const border = Color(0x1A000000);
  static const destructive = Color(0xFFD4183D);
  static const gradBlue = Color(0xFF2F6CFF);
  static const gradPurple = Color(0xFF7B2CFF);
  static const cardPurple = Color(0xFF7B2CFF);
  static const cardOrange = Color(0xFFFF8A00);
  static const cardGreen = Color(0xFF00B35A);
  static const cardPink = Color(0xFFE4008D);
}

class HomePage extends StatefulWidget {
  final bool isArabic;
  final VoidCallback? onToggleLanguage;
  final bool isGuest;
  final VoidCallback? onLoginSuccess;
  final VoidCallback? onLogout;

  const HomePage({
    super.key,
    required this.isArabic,
    this.onToggleLanguage,
    this.isGuest = false,
    this.onLoginSuccess,
    this.onLogout,
  });

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  late bool _isArabic;
  int currentIndex = 0;

  @override
  void initState() {
    super.initState();
    _isArabic = widget.isArabic;
  }

  void _toggleLanguage() {
    setState(() => _isArabic = !_isArabic);
    widget.onToggleLanguage?.call();
  }

  void _showLoginDialog(String featureName) {
    CustomDialog.show(
      context: context,
      title: _isArabic ? '🔒 تسجيل مطلوب' : '🔒 Login Required',
      message: _isArabic
          ? 'يجب تسجيل الدخول أولاً للوصول إلى $featureName'
          : 'Please login first to access $featureName',
      icon: Icons.lock_outline,
      color: const Color(0xFF764BA2),
      primaryButtonText: _isArabic ? 'تسجيل الدخول' : 'Login',
      secondaryButtonText: _isArabic ? 'لاحقاً' : 'Later',
      onPrimaryPressed: () {
        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => LoginPage(
              isArabic: _isArabic,
              onLoginSuccess: () {
                widget.onLoginSuccess?.call();
                Navigator.pop(context);
                CustomToast.show(
                  context: context,
                  message: _isArabic
                      ? '✅ تم تسجيل الدخول بنجاح!'
                      : '✅ Login successful!',
                  icon: Icons.check_circle,
                  color: Colors.green,
                );
              },
            ),
          ),
        );
      },
    );
  }

  void _toast(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  void _navigateTo(int index, String featureName) {
    final protectedPages = [1, 2, 4];

    if (protectedPages.contains(index) && widget.isGuest) {
      _showLoginDialog(featureName);
      return;
    }

    setState(() => currentIndex = index);
  }

  Widget _getPage(int index) {
    switch (index) {
      case 1:
        return AIChatPage(isArabic: _isArabic);
      case 2:
        return CoursesPage(isArabic: _isArabic);
      case 3:
        return EventsPage(isArabic: _isArabic);
      case 4:
        return ReviewsPage(isArabic: _isArabic);
      default:
        return _homeContent();
    }
  }

  Color _pageColor(int index) {
    switch (index) {
      case 1:
        return AppColors.cardPurple;
      case 2:
        return AppColors.cardGreen;
      case 3:
        return AppColors.cardPink;
      case 4:
        return AppColors.cardOrange;
      default:
        return AppColors.gradPurple;
    }
  }

  Widget _homeContent() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 160),
      children: [
        if (widget.isGuest) _buildGuestBanner(),
        if (widget.isGuest) const SizedBox(height: 14),

        TaibahWelcomeCard(isArabic: _isArabic),
        const SizedBox(height: 14),

        FeatureCard(
          icon: Icons.chat_bubble_outline,
          color: AppColors.cardPurple,
          title: _isArabic ? 'دردشة الذكاء الاصطناعي' : 'AI Chat',
          actionText: _isArabic ? 'ابدأ الآن' : 'Start now',
          description: _isArabic
              ? 'احصل على مساعدة فورية في دراستك من الذكاء الاصطناعي'
              : 'Get instant help with your studies from AI',
          onTap: () =>
              _navigateTo(1, _isArabic ? 'الذكاء الاصطناعي' : 'AI Chat'),
        ),
        const SizedBox(height: 12),

        FeatureCard(
          icon: Icons.star_border,
          color: AppColors.cardOrange,
          title: _isArabic ? 'آراء الطلاب' : 'Student Reviews',
          actionText: _isArabic ? 'اكتشف الآن' : 'Discover now',
          description: _isArabic
              ? 'شاهد تجارب وآراء الطلاب الآخرين'
              : 'See experiences and opinions of other students',
          onTap: () => _navigateTo(4, _isArabic ? 'آراء الطلاب' : 'Reviews'),
        ),
        const SizedBox(height: 12),

        FeatureCard(
          icon: Icons.bookmark_border,
          color: AppColors.cardGreen,
          title: _isArabic ? 'الدورات المحفوظة' : 'Saved Courses',
          actionText: _isArabic ? 'تصفح الدورات' : 'Browse courses',
          description: _isArabic
              ? 'الوصول إلى مواردك التعليمية في أي وقت'
              : 'Access your learning resources anytime',
          onTap: () => _navigateTo(2, _isArabic ? 'الدورات' : 'Courses'),
        ),
        const SizedBox(height: 12),

        FeatureCard(
          icon: Icons.calendar_month_outlined,
          color: AppColors.cardPink,
          title: _isArabic ? 'الفعاليات' : 'Events',
          actionText: _isArabic ? 'شاهد الفعاليات' : 'View events',
          description: _isArabic
              ? 'اكتشف الأنشطة التعليمية القادمة'
              : 'Discover upcoming educational activities',
          onTap: () => setState(() => currentIndex = 3),
        ),
      ],
    );
  }

  Widget _buildGuestBanner() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.orange.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Colors.orange.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(
              color: Colors.orange.withValues(alpha: 0.2),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.info_outline,
              color: Colors.orange,
              size: 20,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  _isArabic ? 'وضع الزائر' : 'Guest Mode',
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: Colors.orange,
                    fontSize: 14,
                  ),
                ),
                Text(
                  _isArabic
                      ? 'بعض الميزات محدودة. سجل دخول للوصول الكامل.'
                      : 'Some features are limited. Login for full access.',
                  style: TextStyle(
                    color: Colors.orange.withValues(alpha: 0.8),
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
          TextButton(
            onPressed: () =>
                _showLoginDialog(_isArabic ? 'جميع الميزات' : 'All features'),
            style: TextButton.styleFrom(
              foregroundColor: Colors.orange,
              padding: const EdgeInsets.symmetric(horizontal: 12),
            ),
            child: Text(
              _isArabic ? 'سجل دخول' : 'Login',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final accent = _pageColor(currentIndex);

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: _TopBar(
        isArabic: _isArabic,
        isGuest: widget.isGuest,
        notifCount: 3,
        onLogin: () => _showLoginDialog(_isArabic ? 'حسابك' : 'Your Account'),
        onLanguage: _toggleLanguage,
        onNotifications: () =>
            _toast(_isArabic ? 'الإشعارات' : 'Notifications'),
        onLogout: widget.onLogout,
      ),
      body: _getPage(currentIndex),
      bottomNavigationBar: _BottomBar(
        isArabic: _isArabic,
        isGuest: widget.isGuest,
        currentIndex: currentIndex,
        accent: accent,
        onChange: (i) {
          final labels = _isArabic
              ? ['الرئيسية', 'الذكاء', 'الدورات', 'الفعاليات', 'آراء']
              : ['Home', 'AI', 'Courses', 'Events', 'Reviews'];

          if (i == 0 || i == 3) {
            setState(() => currentIndex = i);
          } else {
            _navigateTo(i, labels[i]);
          }
        },
      ),
    );
  }
}

class TaibahWelcomeCard extends StatelessWidget {
  final bool isArabic;
  const TaibahWelcomeCard({super.key, required this.isArabic});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          colors: [AppColors.gradBlue, AppColors.gradPurple],
          begin: Alignment.centerLeft,
          end: Alignment.centerRight,
        ),
        boxShadow: const [
          BoxShadow(
            color: Color(0x22000000),
            blurRadius: 14,
            offset: Offset(0, 8),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: Colors.white.withValues(alpha: 0.3),
                width: 2,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.1),
                  blurRadius: 8,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: ClipRRect(
              borderRadius: BorderRadius.circular(14),
              child: Image.asset(
                'assets/taibah_logo.png',
                fit: BoxFit.contain,
                errorBuilder: (context, error, stackTrace) {
                  return const Icon(
                    Icons.school,
                    color: AppColors.gradPurple,
                    size: 32,
                  );
                },
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(
                  isArabic
                      ? 'مرحبًا بطلاب جامعة طيبة'
                      : 'Welcome Taibah Students',
                  textAlign: TextAlign.right,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  isArabic
                      ? 'اختر خدمتك التعليمية الخاصة بك'
                      : 'Choose your educational service',
                  textAlign: TextAlign.right,
                  style: const TextStyle(
                    color: Color(0xEFFFFFFF),
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class FeatureCard extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String title;
  final String actionText;
  final String description;
  final VoidCallback onTap;

  const FeatureCard({
    super.key,
    required this.icon,
    required this.color,
    required this.title,
    required this.actionText,
    required this.description,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: AppColors.card,
      borderRadius: BorderRadius.circular(18),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppColors.border),
            boxShadow: const [
              BoxShadow(
                color: Color(0x0F000000),
                blurRadius: 7,
                offset: Offset(0, 4),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                width: 54,
                height: 54,
                decoration: BoxDecoration(
                  color: color,
                  borderRadius: BorderRadius.circular(16),
                ),
                child: Icon(icon, color: Colors.white, size: 26),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      title,
                      textAlign: TextAlign.right,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w900,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      actionText,
                      textAlign: TextAlign.right,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w900,
                        color: color,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      description,
                      textAlign: TextAlign.right,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.mutedText,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _TopBar extends StatelessWidget implements PreferredSizeWidget {
  final bool isArabic;
  final bool isGuest;
  final int notifCount;
  final VoidCallback onLogin;
  final VoidCallback onLanguage;
  final VoidCallback onNotifications;
  final VoidCallback? onLogout;

  const _TopBar({
    required this.isArabic,
    required this.isGuest,
    required this.notifCount,
    required this.onLogin,
    required this.onLanguage,
    required this.onNotifications,
    this.onLogout,
  });

  @override
  Size get preferredSize => const Size.fromHeight(70);

  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: isArabic ? TextDirection.rtl : TextDirection.ltr,
      child: AppBar(
        backgroundColor: AppColors.card,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        titleSpacing: 0,
        automaticallyImplyLeading: false,
        flexibleSpace: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8),
            child: Row(
              children: [
                // Icons side
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (!isGuest) ...[
                      _buildIconButton(
                        icon: Icons.logout,
                        onTap: () => _showLogoutDialog(context),
                      ),
                      const SizedBox(width: 6),
                    ],
                    _buildIconButton(
                      icon: Icons.notifications_none,
                      count: notifCount,
                      onTap: onNotifications,
                    ),
                    const SizedBox(width: 6),
                    _buildIconButton(
                      icon: Icons.translate_rounded,
                      onTap: onLanguage,
                    ),
                    const SizedBox(width: 6),
                    _buildIconButton(
                      icon: Icons.person_outline,
                      isGradient: true,
                      onTap: onLogin,
                    ),
                  ],
                ),

                const Spacer(),

                // Title side
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text(
                          isArabic ? 'مساعدة الطلاب' : 'Student Assistant',
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w900,
                            color: AppColors.primaryText,
                          ),
                        ),
                        const SizedBox(height: 1),
                        if (isGuest)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 4,
                              vertical: 1,
                            ),
                            decoration: BoxDecoration(
                              color: Colors.orange.withValues(alpha: 0.2),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text(
                              'زائر',
                              style: TextStyle(
                                fontSize: 9,
                                color: Colors.orange,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          )
                        else
                          Text(
                            isArabic
                                ? 'منصتك التعليمية الذكية'
                                : 'Your Smart Learning Platform',
                            style: const TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: AppColors.mutedText,
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(width: 8),
                    Container(
                      width: 38,
                      height: 38,
                      decoration: const BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: [AppColors.gradBlue, AppColors.gradPurple],
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                        ),
                      ),
                      child: const Icon(
                        Icons.school,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildIconButton({
    required IconData icon,
    required VoidCallback onTap,
    bool isGradient = false,
    int count = 0,
  }) {
    return InkWell(
      onTap: onTap,
      customBorder: const CircleBorder(),
      child: Container(
        width: 38,
        height: 38,
        decoration: isGradient
            ? const BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  colors: [AppColors.gradBlue, AppColors.gradPurple],
                ),
              )
            : BoxDecoration(
                shape: BoxShape.circle,
                color: AppColors.card,
                border: Border.all(color: AppColors.border),
              ),
        child: count > 0
            ? Stack(
                children: [
                  Center(
                    child: Icon(
                      icon,
                      color: isGradient ? Colors.white : AppColors.primaryText,
                      size: 20,
                    ),
                  ),
                  Positioned(
                    top: 6,
                    right: 6,
                    child: Container(
                      width: 8,
                      height: 8,
                      decoration: const BoxDecoration(
                        color: AppColors.destructive,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                ],
              )
            : Center(
                child: Icon(
                  icon,
                  color: isGradient ? Colors.white : AppColors.primaryText,
                  size: 20,
                ),
              ),
      ),
    );
  }

  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(isArabic ? 'تسجيل خروج' : 'Logout'),
        content: Text(
          isArabic ? 'هل تريد تسجيل الخروج؟' : 'Do you want to logout?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text(isArabic ? 'إلغاء' : 'Cancel'),
          ),
          TextButton(
            onPressed: () {
              Navigator.pop(context);
              onLogout?.call();
            },
            child: Text(
              isArabic ? 'خروج' : 'Logout',
              style: const TextStyle(color: Colors.red),
            ),
          ),
        ],
      ),
    );
  }
}

class _BottomBar extends StatelessWidget {
  final bool isArabic;
  final bool isGuest;
  final int currentIndex;
  final ValueChanged<int> onChange;
  final Color accent;

  const _BottomBar({
    required this.isArabic,
    required this.isGuest,
    required this.currentIndex,
    required this.onChange,
    required this.accent,
  });

  @override
  Widget build(BuildContext context) {
    final labels = isArabic
        ? ['الرئيسية', 'AI', 'الدورات', 'الفعاليات', 'آراء']
        : ['Home', 'AI', 'Courses', 'Events', 'Reviews'];

    final icons = [
      Icons.home_outlined,
      Icons.chat_bubble_outline,
      Icons.menu_book_outlined,
      Icons.calendar_month_outlined,
      Icons.star_border,
    ];

    return SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(14, 10, 14, 12),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AppColors.border),
            boxShadow: const [
              BoxShadow(
                color: Color(0x0A000000),
                blurRadius: 12,
                offset: Offset(0, 6),
              ),
            ],
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: List.generate(5, (i) {
              final selected = currentIndex == i;
              return InkWell(
                onTap: () => onChange(i),
                borderRadius: BorderRadius.circular(18),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 12,
                  ),
                  decoration: BoxDecoration(
                    color: selected ? accent : Colors.transparent,
                    borderRadius: BorderRadius.circular(18),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        icons[i],
                        size: 26,
                        color: selected ? Colors.white : AppColors.mutedText,
                      ),
                      const SizedBox(height: 7),
                      Text(
                        labels[i],
                        style: TextStyle(
                          fontSize: 12.5,
                          fontWeight: FontWeight.w900,
                          color: selected ? Colors.white : AppColors.mutedText,
                        ),
                      ),
                    ],
                  ),
                ),
              );
            }),
          ),
        ),
      ),
    );
  }
}
