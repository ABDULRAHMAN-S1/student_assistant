import 'package:flutter/material.dart';

import 'app/backend_status_banner.dart';
import 'courses_page.dart';
import 'custom_dialog.dart';
import 'custom_toast.dart';
import 'events_page.dart';
import 'features/admin/presentation/admin_panel_page.dart';
import 'features/auth/domain/models/auth_session.dart';
import 'features/courses/data/demo/demo_course_repository.dart';
import 'features/courses/data/repositories/course_repository.dart';
import 'features/engagement/data/repositories/engagement_repository.dart';
import 'features/engagement/data/repositories/engagement_repository_impl.dart';
import 'features/engagement/domain/models/notification_item.dart';
import 'features/engagement/domain/models/suggestion_item.dart';
import 'features/engagement/presentation/controllers/engagement_feed_controller.dart';
import 'features/engagement/presentation/services/notification_navigation_service.dart';
import 'features/engagement/presentation/services/push_notification_service.dart';
import 'features/engagement/presentation/widgets/engagement_feed_section.dart';
import 'features/events/data/demo/demo_event_repository.dart';
import 'features/events/data/repositories/event_repository.dart';
import 'features/profile/data/demo/demo_profile_repository.dart';
import 'features/profile/data/local/profile_store.dart';
import 'features/profile/presentation/pages/profile_page.dart';
import 'features/recommendations/data/services/recommendation_engine.dart';
import 'features/recommendations/domain/models/recommendation_item.dart';
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
  final AuthSession? authSession;
  final VoidCallback? onToggleLanguage;
  final bool isGuest;
  final Future<void> Function(AuthSession session)? onLoginSuccess;
  final VoidCallback? onLogout;
  final Future<void> Function()? onSessionExpired;

  const HomePage({
    super.key,
    required this.isArabic,
    this.authSession,
    this.onToggleLanguage,
    this.isGuest = false,
    this.onLoginSuccess,
    this.onLogout,
    this.onSessionExpired,
  });

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  static const Set<int> _protectedPageIndices = {1, 2, 4};

  late bool _isArabic;
  final CourseRepository _courseRepository = DemoCourseRepository();
  final EventRepository _eventRepository = DemoEventRepository();
  final RecommendationEngine _recommendationEngine =
      const RecommendationEngine();
  int currentIndex = 0;
  int _profileRefreshSeed = 0;
  int? _pendingProtectedPageIndex;
  bool _isHandlingSessionExpiry = false;
  late Future<List<RecommendationItem>> _recommendationsFuture;
  EngagementFeedController? _engagementController;
  late final EngagementRepository _engagementRepository;

  bool get _isAdmin => widget.authSession?.isAdmin == true;

  @override
  void initState() {
    super.initState();
    _isArabic = widget.isArabic;
    _engagementRepository = EngagementRepositoryImpl();
    _recommendationsFuture = _loadRecommendations();
    _setupEngagementController();
  }

  @override
  void dispose() {
    _engagementController?.dispose();
    super.dispose();
  }

  @override
  void didUpdateWidget(covariant HomePage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.isArabic != widget.isArabic) {
      _isArabic = widget.isArabic;
      _recommendationsFuture = _loadRecommendations();
    }
    if (oldWidget.isGuest != widget.isGuest) {
      _recommendationsFuture = _loadRecommendations();
      if (widget.isGuest && _protectedPageIndices.contains(currentIndex)) {
        currentIndex = 0;
      }
    }
    if (oldWidget.isGuest != widget.isGuest ||
        oldWidget.authSession?.userId != widget.authSession?.userId) {
      _setupEngagementController();
    }
  }

  void _setupEngagementController() {
    _engagementController?.dispose();
    if (widget.isGuest || widget.authSession == null) {
      _engagementController = null;
      PushNotificationService.instance.unregisterCurrentDevice(
        repository: _engagementRepository,
      );
      return;
    }
    final controller = EngagementFeedController(
      repository: _engagementRepository,
    );
    _engagementController = controller;
    controller.addListener(() {
      if (controller.sessionExpiredMessage != null) {
        controller.clearSessionExpiredFlag();
        _handleSessionExpired();
      }
      if (mounted) {
        setState(() {});
      }
    });
    controller.loadInitial();
    PushNotificationService.instance.registerForSession(
      repository: _engagementRepository,
      session: widget.authSession,
      context: context,
      isArabic: _isArabic,
    );
  }

  Future<List<RecommendationItem>> _loadRecommendations() async {
    final profileStore = await ProfileStore.open();
    final profileRepository = DemoProfileRepository(profileStore: profileStore);
    final profile = await profileRepository.loadProfile();

    if (profile == null) {
      return const [];
    }

    return _recommendationEngine.generate(
      profile: profile,
      courses: _courseRepository.getCourses(),
      events: _eventRepository.getEvents(),
      maxResults: 4,
      isArabic: _isArabic,
    );
  }

  void _toggleLanguage() {
    setState(() {
      _isArabic = !_isArabic;
      _recommendationsFuture = _loadRecommendations();
    });
    widget.onToggleLanguage?.call();
  }

  Future<void> _openLoginPage({int? targetPageIndex}) async {
    final resolvedTargetIndex = targetPageIndex ?? _pendingProtectedPageIndex;
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => LoginPage(
          isArabic: _isArabic,
          onLoginSuccess: (session) async {
            await widget.onLoginSuccess?.call(session);
            if (!mounted) return;
            setState(() {
              _recommendationsFuture = _loadRecommendations();
              _pendingProtectedPageIndex = null;
              if (resolvedTargetIndex != null) {
                currentIndex = resolvedTargetIndex;
              }
            });
            _setupEngagementController();
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
  }

  void _showLoginDialog(String featureName, {int? targetPageIndex}) {
    _pendingProtectedPageIndex = targetPageIndex;
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
        _openLoginPage(targetPageIndex: targetPageIndex);
      },
    );
  }

  Future<void> _handleSessionExpired() async {
    if (_isHandlingSessionExpiry) {
      return;
    }

    _isHandlingSessionExpiry = true;
    final resumePageIndex = _protectedPageIndices.contains(currentIndex)
        ? currentIndex
        : null;
    _pendingProtectedPageIndex = resumePageIndex;

    try {
      await widget.onSessionExpired?.call();
      if (!mounted) return;

      setState(() {
        currentIndex = 0;
        _recommendationsFuture = _loadRecommendations();
      });

      CustomDialog.show(
        context: context,
        title: _isArabic ? 'انتهت الجلسة' : 'Session Ended',
        message: _isArabic
            ? 'انتهت جلستك أو لم تعد صالحة. سجل الدخول مرة أخرى للمتابعة.'
            : 'Your session has expired or is no longer valid. Sign in again to continue.',
        icon: Icons.lock_clock_outlined,
        color: const Color(0xFF764BA2),
        primaryButtonText: _isArabic ? 'تسجيل الدخول' : 'Sign in',
        secondaryButtonText: _isArabic ? 'لاحقاً' : 'Later',
        onPrimaryPressed: () {
          _openLoginPage(targetPageIndex: resumePageIndex);
        },
      );
    } finally {
      _isHandlingSessionExpiry = false;
    }
  }

  Future<void> _openProfilePage() async {
    final updated = await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => ProfilePage(isArabic: _isArabic)),
    );

    if (updated != true || !mounted) return;

    setState(() {
      _recommendationsFuture = _loadRecommendations();
      _profileRefreshSeed++;
    });
    await _engagementController?.refresh();
  }

  void _openNotificationsInbox() {
    if (widget.isGuest || _engagementController == null) {
      _showLoginDialog(_isArabic ? 'الإشعارات' : 'Notifications');
      return;
    }
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return SafeArea(
          top: false,
          child: Container(
            constraints: BoxConstraints(
              maxHeight: MediaQuery.of(context).size.height * 0.88,
            ),
            decoration: const BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(16, 18, 16, 24),
              child: EngagementFeedSection(
                controller: _engagementController!,
                isArabic: _isArabic,
                onMarkAsRead: _markEngagementNotificationAsRead,
                onOpenNotification: _openNotification,
                onOpenSuggestion: _openSuggestionDetails,
                onOpenProfile: () {
                  Navigator.of(sheetContext).pop();
                  _openProfilePage();
                },
              ),
            ),
          ),
        );
      },
    );
  }

  Future<void> _markEngagementNotificationAsRead(String notificationId) async {
    final controller = _engagementController;
    if (controller == null) {
      return;
    }
    try {
      await controller.markAsRead(notificationId);
      if (!mounted) {
        return;
      }
      CustomToast.show(
        context: context,
        message: _isArabic
            ? 'تم تعليم التنبيه كمقروء'
            : 'Notification marked as read',
        icon: Icons.done,
        color: Colors.green,
      );
    } catch (_) {
      if (!mounted) {
        return;
      }
      CustomToast.show(
        context: context,
        message: _isArabic
            ? 'تعذر تحديث حالة التنبيه'
            : 'Could not update notification',
        icon: Icons.error_outline,
        color: AppColors.destructive,
      );
    }
  }

  Future<void> _openNotification(NotificationItem item) async {
    await NotificationNavigationService.instance.openNotification(
      context: context,
      item: item,
      isArabic: _isArabic,
      onSessionExpired: _handleSessionExpired,
      onOpenInbox: _openNotificationsInbox,
    );
  }

  void _openSuggestionDetails(SuggestionItem item) {
    final details = item.linkUrl?.trim().isNotEmpty == true
        ? item.linkUrl!.trim()
        : item.body;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.transparent,
      isScrollControlled: true,
      builder: (sheetContext) {
        return SafeArea(
          top: false,
          child: Container(
            decoration: const BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 18, 20, 22),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    item.title,
                    style: const TextStyle(
                      fontSize: 17,
                      fontWeight: FontWeight.w900,
                      color: AppColors.primaryText,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    item.body,
                    style: const TextStyle(
                      fontSize: 13.5,
                      color: AppColors.mutedText,
                      height: 1.45,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppColors.background,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: AppColors.border),
                    ),
                    child: Text(
                      details,
                      style: const TextStyle(
                        fontSize: 12.5,
                        color: AppColors.primaryText,
                        height: 1.4,
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      onPressed: () => Navigator.of(sheetContext).pop(),
                      icon: const Icon(Icons.close),
                      label: Text(_isArabic ? 'إغلاق' : 'Close'),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  void _navigateTo(int index, String featureName) {
    if (_protectedPageIndices.contains(index) && widget.isGuest) {
      _showLoginDialog(featureName, targetPageIndex: index);
      return;
    }

    setState(() => currentIndex = index);
  }

  List<Widget> _buildPages() {
    return [
      _homeContent(),
      AIChatPage(
        isArabic: _isArabic,
        profileRefreshToken: _profileRefreshSeed,
        onSessionExpired: _handleSessionExpired,
      ),
      CoursesPage(isArabic: _isArabic),
      EventsPage(isArabic: _isArabic),
      ReviewsPage(isArabic: _isArabic),
    ];
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

        BackendStatusBanner(isArabic: _isArabic),
        const SizedBox(height: 14),

        if (_isAdmin) _buildAdminAccessBanner(),
        if (_isAdmin) const SizedBox(height: 14),

        TaibahWelcomeCard(isArabic: _isArabic),
        const SizedBox(height: 14),
        _buildRecommendationsSection(),
        if (!widget.isGuest && _engagementController != null) ...[
          const SizedBox(height: 12),
          EngagementFeedSection(
            controller: _engagementController!,
            isArabic: _isArabic,
            onMarkAsRead: _markEngagementNotificationAsRead,
            onOpenNotification: _openNotification,
            onOpenSuggestion: _openSuggestionDetails,
            onOpenProfile: _openProfilePage,
          ),
        ],
        const SizedBox(height: 12),

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

  Widget _buildRecommendationsSection() {
    return FutureBuilder<List<RecommendationItem>>(
      future: _recommendationsFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return _buildRecommendationSectionContainer(
            child: const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Center(child: CircularProgressIndicator(strokeWidth: 2.2)),
            ),
          );
        }

        final recommendations = snapshot.data ?? const <RecommendationItem>[];
        if (recommendations.isEmpty) {
          return _buildRecommendationSectionContainer(
            child: _buildRecommendationEmptyState(),
          );
        }

        return _buildRecommendationSectionContainer(
          child: Column(
            children: recommendations
                .map((item) => _buildRecommendationCard(item))
                .toList(growable: false),
          ),
        );
      },
    );
  }

  Widget _buildRecommendationSectionContainer({required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.card,
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
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: AppColors.gradBlue.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: const Icon(
                  Icons.auto_awesome_outlined,
                  color: AppColors.gradBlue,
                  size: 22,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _isArabic ? 'توصيات مخصصة لك' : 'Recommended for You',
                      style: const TextStyle(
                        fontSize: 18.5,
                        fontWeight: FontWeight.w900,
                        color: AppColors.primaryText,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      _isArabic
                          ? 'اقتراحات مبنية على بياناتك الأكاديمية الحالية'
                          : 'Suggestions based on your current academic context',
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.mutedText,
                        height: 1.45,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          child,
        ],
      ),
    );
  }

  Widget _buildAdminAccessBanner() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF4FF),
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: const Color(0xFFD7E7FF)),
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
                  color: const Color(0xFF2563EB).withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.admin_panel_settings_outlined,
                  color: Color(0xFF1D4ED8),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _isArabic ? 'وصول إداري مفعل' : 'Admin access enabled',
                      style: const TextStyle(
                        fontWeight: FontWeight.w800,
                        color: Color(0xFF1D4ED8),
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _isArabic
                          ? 'هذا الحساب يملك صلاحيات admin في النظام.'
                          : 'This account currently has admin privileges in the system.',
                      style: const TextStyle(
                        color: Color(0xFF1E3A8A),
                        fontSize: 12.5,
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: _openAdminPanel,
            icon: const Icon(Icons.settings_outlined),
            label: Text(_isArabic ? 'لوحة الإدارة' : 'Admin Panel'),
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF1D4ED8),
              side: const BorderSide(color: Color(0xFFBFDBFE)),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(14),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _openAdminPanel() async {
    final authSession = widget.authSession;
    if (authSession == null) {
      return;
    }

    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => AdminPanelPage(
          isArabic: _isArabic,
          authSession: authSession,
          onSessionUpdated: widget.onLoginSuccess,
        ),
      ),
    );
  }

  Widget _buildRecommendationEmptyState() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            _isArabic ? 'لا توجد توصيات متاحة الآن' : 'No recommendations yet',
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w800,
              color: AppColors.primaryText,
            ),
          ),
          const SizedBox(height: 6),
          Text(
            _isArabic
                ? 'أكمل بياناتك الأكاديمية أولًا حتى نعرض لك اقتراحات مناسبة.'
                : 'Complete your academic profile first to see personalized suggestions.',
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.mutedText,
              height: 1.45,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRecommendationCard(RecommendationItem item) {
    final isCourse = item.type == RecommendationItem.courseType;
    final color = isCourse ? AppColors.cardGreen : AppColors.cardPink;
    final typeLabel = _recommendationTypeLabel(item);

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.16)),
        boxShadow: const [
          BoxShadow(
            color: Color(0x0A000000),
            blurRadius: 8,
            offset: Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(16),
          onTap: () => _openRecommendation(item),
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10,
                        vertical: 6,
                      ),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            isCourse
                                ? Icons.menu_book_outlined
                                : Icons.calendar_month_outlined,
                            color: color,
                            size: 15,
                          ),
                          const SizedBox(width: 6),
                          Text(
                            typeLabel,
                            style: TextStyle(
                              color: color,
                              fontSize: 12,
                              fontWeight: FontWeight.w800,
                            ),
                          ),
                        ],
                      ),
                    ),
                    const Spacer(),
                    Icon(Icons.arrow_forward_ios, size: 14, color: color),
                  ],
                ),
                const SizedBox(height: 10),
                Text(
                  item.title,
                  style: const TextStyle(
                    fontSize: 16.5,
                    fontWeight: FontWeight.w900,
                    color: AppColors.primaryText,
                    height: 1.35,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  item.description,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.mutedText,
                    height: 1.45,
                  ),
                ),
                const SizedBox(height: 12),
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.75),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: color.withValues(alpha: 0.12)),
                  ),
                  child: Text(
                    item.reason,
                    style: const TextStyle(
                      fontSize: 12.8,
                      color: AppColors.primaryText,
                      height: 1.5,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _recommendationTypeLabel(RecommendationItem item) {
    final isCourse = item.type == RecommendationItem.courseType;
    return _isArabic
        ? (isCourse ? 'مقرر' : 'فعالية')
        : (isCourse ? 'Course' : 'Event');
  }

  String _recommendationDestinationLabel(RecommendationItem item) {
    final isCourse = item.type == RecommendationItem.courseType;
    return _isArabic
        ? (isCourse ? 'عرض المقررات' : 'عرض الفعاليات')
        : (isCourse ? 'Open courses' : 'Open events');
  }

  List<MapEntry<String, List<String>>> _recommendationSignals(
    RecommendationItem item,
  ) {
    return [
      MapEntry(
        _isArabic ? 'التخصص' : 'Specialization',
        item.specializationSignals,
      ),
      MapEntry(_isArabic ? 'الاهتمامات' : 'Interests', item.interestSignals),
      MapEntry(
        _isArabic ? 'المستوى الأكاديمي' : 'Academic level',
        item.academicLevelSignals,
      ),
      MapEntry(
        _isArabic ? 'المقررات المسجلة' : 'Enrolled courses',
        item.enrolledCourseSignals,
      ),
    ].where((entry) => entry.value.isNotEmpty).toList(growable: false);
  }

  Widget _buildRecommendationSignalSection(
    String label,
    List<String> values,
    Color color,
  ) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w800,
              color: AppColors.primaryText,
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: values
                .map(
                  (value) => Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 10,
                      vertical: 7,
                    ),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.08),
                      borderRadius: BorderRadius.circular(999),
                      border: Border.all(color: color.withValues(alpha: 0.18)),
                    ),
                    child: Text(
                      value,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: color,
                      ),
                    ),
                  ),
                )
                .toList(growable: false),
          ),
        ],
      ),
    );
  }

  void _openRecommendationDestination(RecommendationItem item) {
    if (item.type == RecommendationItem.courseType) {
      _navigateTo(2, _isArabic ? 'الدورات' : 'Courses');
      return;
    }
    setState(() => currentIndex = 3);
  }

  Future<void> _openRecommendation(RecommendationItem item) async {
    final isCourse = item.type == RecommendationItem.courseType;
    final color = isCourse ? AppColors.cardGreen : AppColors.cardPink;
    final signalGroups = _recommendationSignals(item);

    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetContext) {
        return SafeArea(
          top: false,
          child: Container(
            decoration: const BoxDecoration(
              color: AppColors.card,
              borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
            ),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 24),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Center(
                      child: Container(
                        width: 42,
                        height: 4,
                        decoration: BoxDecoration(
                          color: AppColors.border,
                          borderRadius: BorderRadius.circular(999),
                        ),
                      ),
                    ),
                    const SizedBox(height: 18),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 8,
                      ),
                      decoration: BoxDecoration(
                        color: color.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(999),
                      ),
                      child: Text(
                        _recommendationTypeLabel(item),
                        style: TextStyle(
                          color: color,
                          fontSize: 12,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                    const SizedBox(height: 14),
                    Text(
                      item.title,
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w900,
                        color: AppColors.primaryText,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      item.description,
                      style: const TextStyle(
                        fontSize: 13.5,
                        color: AppColors.mutedText,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: 18),
                    Text(
                      _isArabic ? 'سبب التوصية' : 'Why this was recommended',
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w900,
                        color: AppColors.primaryText,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(14),
                      decoration: BoxDecoration(
                        color: AppColors.background,
                        borderRadius: BorderRadius.circular(16),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Text(
                        item.reason,
                        style: const TextStyle(
                          fontSize: 13,
                          color: AppColors.primaryText,
                          height: 1.55,
                        ),
                      ),
                    ),
                    if (signalGroups.isNotEmpty) ...[
                      const SizedBox(height: 18),
                      Text(
                        _isArabic
                            ? 'الإشارات المؤثرة من ملفك الأكاديمي'
                            : 'Profile signals that contributed',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w900,
                          color: AppColors.primaryText,
                        ),
                      ),
                      ...signalGroups.map(
                        (entry) => _buildRecommendationSignalSection(
                          entry.key,
                          entry.value,
                          color,
                        ),
                      ),
                    ],
                    const SizedBox(height: 22),
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: () {
                          Navigator.of(sheetContext).pop();
                          if (!mounted) return;
                          _openRecommendationDestination(item);
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: color,
                          foregroundColor: Colors.white,
                          elevation: 0,
                          padding: const EdgeInsets.symmetric(vertical: 14),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(16),
                          ),
                        ),
                        child: Text(
                          _recommendationDestinationLabel(item),
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      },
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
        notifCount: _engagementController?.unreadCount ?? 0,
        accentColor: accent,
        onLogin: () {
          if (widget.isGuest) {
            _showLoginDialog(_isArabic ? 'حسابك' : 'Your Account');
            return;
          }
          _openProfilePage();
        },
        onLanguage: _toggleLanguage,
        onNotifications: _openNotificationsInbox,
        onLogout: widget.onLogout,
      ),
      body: IndexedStack(index: currentIndex, children: _buildPages()),
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
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isArabic
                      ? 'مرحبًا بطلاب جامعة طيبة'
                      : 'Welcome Taibah Students',
                  textAlign: TextAlign.left,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18.5,
                    fontWeight: FontWeight.w900,
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  isArabic
                      ? 'اختر خدمتك التعليمية الخاصة بك'
                      : 'Choose your educational service',
                  textAlign: TextAlign.left,
                  style: const TextStyle(
                    color: Color(0xEFFFFFFF),
                    fontSize: 13.5,
                    fontWeight: FontWeight.w700,
                    height: 1.45,
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

class FeatureCard extends StatefulWidget {
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
  State<FeatureCard> createState() => _FeatureCardState();
}

class _FeatureCardState extends State<FeatureCard> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressed = true),
      onTapUp: (_) => setState(() => _isPressed = false),
      onTapCancel: () => setState(() => _isPressed = false),
      onTap: widget.onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        curve: Curves.easeInOut,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: _isPressed
              ? widget.color.withValues(alpha: 0.1)
              : AppColors.card,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(
            color: _isPressed ? widget.color : AppColors.border,
            width: _isPressed ? 2 : 1,
          ),
          boxShadow: [
            BoxShadow(
              color: _isPressed
                  ? widget.color.withValues(alpha: 0.3)
                  : const Color(0x0F000000),
              blurRadius: _isPressed ? 15 : 7,
              offset: Offset(0, _isPressed ? 8 : 4),
            ),
          ],
        ),
        child: Transform.scale(
          scale: _isPressed ? 0.98 : 1.0,
          child: Row(
            children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 150),
                width: 54,
                height: 54,
                decoration: BoxDecoration(
                  color: widget.color,
                  borderRadius: BorderRadius.circular(16),
                  boxShadow: _isPressed
                      ? [
                          BoxShadow(
                            color: widget.color.withValues(alpha: 0.5),
                            blurRadius: 10,
                            offset: const Offset(0, 4),
                          ),
                        ]
                      : null,
                ),
                child: Icon(widget.icon, color: Colors.white, size: 26),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.title,
                      textAlign: TextAlign.left,
                      style: const TextStyle(
                        fontSize: 18.5,
                        fontWeight: FontWeight.w900,
                        height: 1.3,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Text(
                      widget.actionText,
                      textAlign: TextAlign.left,
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w900,
                        color: widget.color,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      widget.description,
                      textAlign: TextAlign.left,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.mutedText,
                        height: 1.45,
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
  final Color accentColor;

  const _TopBar({
    required this.isArabic,
    required this.isGuest,
    required this.notifCount,
    required this.onLogin,
    required this.onLanguage,
    required this.onNotifications,
    this.onLogout,
    required this.accentColor,
  });

  @override
  Size get preferredSize => const Size.fromHeight(70);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: AppColors.card,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      titleSpacing: 0,
      automaticallyImplyLeading: false,
      flexibleSpace: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          // ✅ FORCE LTR: Icon left, Text right (like Courses page)
          child: Directionality(
            textDirection: TextDirection.ltr,
            child: Row(
              children: [
                // LEFT: Icons
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
                      onTap: onLogin,
                      color: accentColor,
                    ),
                  ],
                ),

                const Spacer(),

                // RIGHT: Logo + Text (next to each other)
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // Logo
                    Container(
                      width: 38,
                      height: 38,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: LinearGradient(
                          colors: [
                            accentColor,
                            accentColor.withValues(alpha: 0.8),
                          ],
                        ),
                      ),
                      child: const Icon(
                        Icons.school,
                        color: Colors.white,
                        size: 20,
                      ),
                    ),
                    const SizedBox(width: 8),
                    // Text next to logo
                    Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
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
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w600,
                              color: accentColor,
                            ),
                          ),
                      ],
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
    int count = 0,
    Color? color,
  }) {
    final useAccent = color != null;
    return InkWell(
      onTap: onTap,
      customBorder: const CircleBorder(),
      child: Container(
        width: 38,
        height: 38,
        decoration: useAccent
            ? BoxDecoration(
                shape: BoxShape.circle,
                gradient: LinearGradient(
                  colors: [color, color.withValues(alpha: 0.8)],
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
                      color: useAccent ? Colors.white : AppColors.primaryText,
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
                  color: useAccent ? Colors.white : AppColors.primaryText,
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
