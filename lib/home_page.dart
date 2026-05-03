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
  static const background = Color(0xFFF6F8FC);
  static const card = Color(0xFFFFFFFF);
  static const primaryText = Color(0xFF111827);
  static const mutedText = Color(0xFF64748B);
  static const border = Color(0xFFE2E8F0);
  static const destructive = Color(0xFFE11D48);
  static const gradBlue = Color(0xFF2563EB);
  static const gradPurple = Color(0xFF6D28D9);
  static const cardPurple = Color(0xFF7C3AED);
  static const cardOrange = Color(0xFFF59E0B);
  static const cardGreen = Color(0xFF10B981);
  static const cardPink = Color(0xFFDB2777);
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
      _homeDashboardContent(),
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

  Widget _homeDashboardContent() {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 14, 16, 150),
      children: [
        if (widget.isGuest) _buildGuestBanner(),
        if (widget.isGuest) const SizedBox(height: 14),
        if (_isAdmin) _buildAdminAccessBanner(),
        if (_isAdmin) const SizedBox(height: 14),
        TaibahWelcomeCard(isArabic: _isArabic),
        const SizedBox(height: 16),
        _buildQuickServicesSection(),
        const SizedBox(height: 22),
        _buildSmartSuggestionsSection(),
        const SizedBox(height: 22),
        _buildLiveContentSection(),
      ],
    );
  }

  Widget _buildSectionTitle({
    required String title,
    String? actionText,
    VoidCallback? onAction,
    IconData? icon,
  }) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          if (icon != null) ...[
            Icon(icon, color: AppColors.gradPurple, size: 22),
            const SizedBox(width: 8),
          ],
          Expanded(
            child: Text(
              title,
              style: const TextStyle(
                color: AppColors.primaryText,
                fontSize: 21,
                fontWeight: FontWeight.w900,
                height: 1.25,
              ),
            ),
          ),
          if (actionText != null && onAction != null)
            TextButton.icon(
              onPressed: onAction,
              icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 15),
              label: Text(
                actionText,
                style: const TextStyle(fontWeight: FontWeight.w900),
              ),
              style: TextButton.styleFrom(
                foregroundColor: AppColors.gradPurple,
                padding: const EdgeInsets.symmetric(horizontal: 4),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildQuickServicesSection() {
    final services = [
      _QuickServiceItem(
        icon: Icons.menu_book_rounded,
        color: AppColors.gradBlue,
        background: const Color(0xFFEFF6FF),
        title: _isArabic ? 'الدورات' : 'Courses',
        subtitle: _isArabic ? 'دوراتك المسجلة' : 'Your registered courses',
        onTap: () => _navigateTo(2, _isArabic ? 'الدورات' : 'Courses'),
      ),
      _QuickServiceItem(
        icon: Icons.assignment_turned_in_rounded,
        color: AppColors.cardPurple,
        background: const Color(0xFFF5F3FF),
        title: _isArabic ? 'تسجيل المواد' : 'Course Registration',
        subtitle: _isArabic ? 'تسجيل وحذف المقررات' : 'Add and drop courses',
        onTap: () =>
            _navigateTo(2, _isArabic ? 'تسجيل المواد' : 'Course Registration'),
      ),
      _QuickServiceItem(
        icon: Icons.smart_toy_rounded,
        color: AppColors.cardOrange,
        background: const Color(0xFFFFF7ED),
        title: _isArabic ? 'المساعد الذكي' : 'Smart Assistant',
        subtitle: _isArabic ? 'اسأل واستفسر' : 'Ask and explore',
        onTap: () =>
            _navigateTo(1, _isArabic ? 'المساعد الذكي' : 'Smart Assistant'),
      ),
      _QuickServiceItem(
        icon: Icons.calendar_month_rounded,
        color: const Color(0xFF20C997),
        background: const Color(0xFFECFDF5),
        title: _isArabic ? 'الفعاليات' : 'Events',
        subtitle: _isArabic ? 'المعارض والورش' : 'Workshops and fairs',
        onTap: () => setState(() => currentIndex = 3),
      ),
    ];

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle(
          title: _isArabic ? 'الخدمات السريعة' : 'Quick Services',
          actionText: _isArabic ? 'عرض الكل' : 'View all',
          onAction: () => _navigateTo(2, _isArabic ? 'الخدمات' : 'Services'),
        ),
        LayoutBuilder(
          builder: (context, constraints) {
            final textScale = MediaQuery.textScalerOf(context).scale(1);
            final useSingleColumn = constraints.maxWidth < 330;
            final itemHeight = useSingleColumn
                ? (textScale > 1.2 ? 120.0 : 104.0)
                : (textScale > 1.2 ? 134.0 : 112.0);

            return GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              itemCount: services.length,
              gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: useSingleColumn ? 1 : 2,
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                mainAxisExtent: itemHeight,
              ),
              itemBuilder: (context, index) =>
                  _QuickServiceCard(item: services[index]),
            );
          },
        ),
      ],
    );
  }

  Widget _buildSmartSuggestionsSection() {
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    final suggestionHeight = textScale > 1.2 ? 178.0 : 152.0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle(
          title: _isArabic ? 'اقتراحات ذكية لك' : 'Smart Suggestions',
          icon: Icons.auto_awesome_rounded,
        ),
        FutureBuilder<List<RecommendationItem>>(
          future: _recommendationsFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return SizedBox(
                height: suggestionHeight,
                child: const Center(
                  child: CircularProgressIndicator(strokeWidth: 2.2),
                ),
              );
            }

            final recommendations =
                snapshot.data ?? const <RecommendationItem>[];
            if (recommendations.isEmpty) {
              return SizedBox(
                height: suggestionHeight,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  clipBehavior: Clip.none,
                  children: [
                    _ReminderSuggestionCard(
                      isArabic: _isArabic,
                      onTap: () => _navigateTo(
                        2,
                        _isArabic ? 'تسجيل المواد' : 'Course Registration',
                      ),
                    ),
                    const SizedBox(width: 12),
                    _ProfileSuggestionCard(
                      isArabic: _isArabic,
                      onTap: widget.isGuest
                          ? () => _showLoginDialog(
                              _isArabic ? 'ملفك الأكاديمي' : 'Your profile',
                            )
                          : _openProfilePage,
                    ),
                  ],
                ),
              );
            }

            return SizedBox(
              height: suggestionHeight,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                clipBehavior: Clip.none,
                itemCount: recommendations.length,
                separatorBuilder: (_, _) => const SizedBox(width: 12),
                itemBuilder: (context, index) => _SmartSuggestionCard(
                  item: recommendations[index],
                  isArabic: _isArabic,
                  onTap: () => _openRecommendation(recommendations[index]),
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  Widget _buildLiveContentSection() {
    final controller = _engagementController;
    if (controller == null) {
      return _buildLiveContentBody();
    }

    return AnimatedBuilder(
      animation: controller,
      builder: (context, _) => _buildLiveContentBody(),
    );
  }

  Widget _buildLiveContentBody() {
    final feed = _engagementController?.data;
    final notification = feed?.notifications.isNotEmpty == true
        ? feed!.notifications.first
        : null;
    final suggestion = feed?.suggestions.isNotEmpty == true
        ? feed!.suggestions.first
        : null;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _buildSectionTitle(
          title: _isArabic ? 'المحتوى الحي' : 'Live Content',
          actionText: _isArabic ? 'عرض الكل' : 'View all',
          onAction: _openNotificationsInbox,
        ),
        if (_engagementController?.isLoading == true)
          const SizedBox(
            height: 116,
            child: Center(child: CircularProgressIndicator(strokeWidth: 2.2)),
          )
        else if (notification != null)
          _LiveContentCard(
            icon: Icons.campaign_rounded,
            color: AppColors.cardPurple,
            title: notification.title,
            body: notification.message,
            footer: _isArabic ? 'تنبيه جديد' : 'New alert',
            onTap: () => _openNotification(notification),
          )
        else if (suggestion != null)
          _LiveContentCard(
            icon: Icons.school_rounded,
            color: AppColors.gradBlue,
            title: suggestion.title,
            body: suggestion.body,
            footer: _isArabic ? 'اقتراح مناسب لك' : 'Matched suggestion',
            onTap: () => _openSuggestionDetails(suggestion),
          )
        else
          _LiveContentCard(
            icon: Icons.campaign_rounded,
            color: AppColors.cardPurple,
            title: _isArabic ? 'إعلان من الجامعة' : 'University Announcement',
            body: _isArabic
                ? 'فتح التقديم على المنح الدراسية للعام 2024'
                : 'Scholarship applications are now open for 2024',
            footer: _isArabic ? '20 مايو 2024' : 'May 20, 2024',
            onTap: _openNotificationsInbox,
          ),
      ],
    );
  }

  // ignore: unused_element
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

class _QuickServiceItem {
  const _QuickServiceItem({
    required this.icon,
    required this.color,
    required this.background,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final Color background;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
}

class _QuickServiceCard extends StatelessWidget {
  const _QuickServiceCard({required this.item});

  final _QuickServiceItem item;

  @override
  Widget build(BuildContext context) {
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    final compact = MediaQuery.sizeOf(context).width < 360 || textScale > 1.15;
    final iconBoxSize = compact ? 46.0 : 54.0;
    final iconSize = compact ? 26.0 : 30.0;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: item.onTap,
        borderRadius: BorderRadius.circular(18),
        child: Ink(
          decoration: BoxDecoration(
            color: item.background,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: item.color.withValues(alpha: 0.12)),
            boxShadow: const [
              BoxShadow(
                color: Color(0x08000000),
                blurRadius: 12,
                offset: Offset(0, 6),
              ),
            ],
          ),
          child: Padding(
            padding: EdgeInsets.all(compact ? 12 : 14),
            child: Row(
              children: [
                Container(
                  width: iconBoxSize,
                  height: iconBoxSize,
                  decoration: BoxDecoration(
                    color: item.color.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(compact ? 14 : 16),
                  ),
                  child: Icon(item.icon, color: item.color, size: iconSize),
                ),
                SizedBox(width: compact ? 10 : 12),
                Expanded(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        item.title,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppColors.primaryText,
                          fontSize: compact ? 15 : 16,
                          fontWeight: FontWeight.w900,
                          height: 1.25,
                        ),
                      ),
                      SizedBox(height: compact ? 5 : 6),
                      Text(
                        item.subtitle,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: AppColors.mutedText,
                          fontSize: compact ? 12 : 12.5,
                          fontWeight: FontWeight.w700,
                          height: 1.35,
                        ),
                      ),
                    ],
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

class _ReminderSuggestionCard extends StatelessWidget {
  const _ReminderSuggestionCard({required this.isArabic, required this.onTap});

  final bool isArabic;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 268,
      child: _GradientSuggestionShell(
        color: AppColors.destructive,
        background: const Color(0xFFFFF1F5),
        icon: Icons.timer_rounded,
        title: isArabic ? 'تنبيه تسجيل' : 'Registration Alert',
        subtitle: isArabic
            ? 'بقي 4 أيام على تسجيل المقررات'
            : '4 days left for course registration',
        caption: isArabic ? 'لا تفوت الفرصة' : 'Do not miss it',
        actionText: isArabic ? 'اذهب للتسجيل' : 'Register now',
        onTap: onTap,
      ),
    );
  }
}

class _ProfileSuggestionCard extends StatelessWidget {
  const _ProfileSuggestionCard({required this.isArabic, required this.onTap});

  final bool isArabic;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: 206,
      child: _GradientSuggestionShell(
        color: AppColors.gradBlue,
        background: const Color(0xFFF2F7FF),
        icon: Icons.school_rounded,
        title: isArabic ? 'ملفك الأكاديمي' : 'Academic Profile',
        subtitle: isArabic ? 'حدّث بياناتك' : 'Update your data',
        caption: isArabic ? 'اقتراحات أدق' : 'Better matches',
        actionText: isArabic ? 'عرض الملف' : 'Open profile',
        onTap: onTap,
      ),
    );
  }
}

class _SmartSuggestionCard extends StatelessWidget {
  const _SmartSuggestionCard({
    required this.item,
    required this.isArabic,
    required this.onTap,
  });

  final RecommendationItem item;
  final bool isArabic;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isCourse = item.type == RecommendationItem.courseType;
    final color = isCourse ? AppColors.gradBlue : AppColors.cardPink;

    return SizedBox(
      width: 240,
      child: _GradientSuggestionShell(
        color: color,
        background: isCourse
            ? const Color(0xFFF2F7FF)
            : const Color(0xFFFFF1FA),
        icon: isCourse ? Icons.school_rounded : Icons.event_available_rounded,
        title: item.title,
        subtitle: item.description,
        caption: item.reason,
        actionText: isArabic
            ? (isCourse ? 'عرض الدورة' : 'عرض الفعالية')
            : (isCourse ? 'View course' : 'View event'),
        onTap: onTap,
      ),
    );
  }
}

class _GradientSuggestionShell extends StatelessWidget {
  const _GradientSuggestionShell({
    required this.color,
    required this.background,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.caption,
    required this.actionText,
    required this.onTap,
  });

  final Color color;
  final Color background;
  final IconData icon;
  final String title;
  final String subtitle;
  final String caption;
  final String actionText;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Ink(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: background,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: color.withValues(alpha: 0.13)),
            boxShadow: const [
              BoxShadow(
                color: Color(0x08000000),
                blurRadius: 12,
                offset: Offset(0, 6),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                width: 58,
                height: 58,
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.8),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: color, size: 30),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: color,
                        fontSize: 17,
                        fontWeight: FontWeight.w900,
                        height: 1.25,
                      ),
                    ),
                    const SizedBox(height: 7),
                    Text(
                      subtitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.primaryText,
                        fontSize: 14,
                        fontWeight: FontWeight.w800,
                        height: 1.35,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      caption,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.mutedText,
                        fontSize: 12.5,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const Spacer(),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: Text(
                        actionText,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: color,
                          fontSize: 13.5,
                          fontWeight: FontWeight.w900,
                        ),
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

class _LiveContentCard extends StatelessWidget {
  const _LiveContentCard({
    required this.icon,
    required this.color,
    required this.title,
    required this.body,
    required this.footer,
    required this.onTap,
  });

  final IconData icon;
  final Color color;
  final String title;
  final String body;
  final String footer;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(18),
        child: Ink(
          padding: const EdgeInsets.all(18),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: AppColors.border),
            boxShadow: const [
              BoxShadow(
                color: Color(0x0F000000),
                blurRadius: 10,
                offset: Offset(0, 5),
              ),
            ],
          ),
          child: Row(
            children: [
              Container(
                width: 64,
                height: 64,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.08),
                  shape: BoxShape.circle,
                ),
                child: Icon(icon, color: color, size: 34),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.primaryText,
                        fontSize: 17,
                        fontWeight: FontWeight.w900,
                        height: 1.25,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      body,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        color: AppColors.mutedText,
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        height: 1.45,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Text(
                      footer,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: color,
                        fontSize: 13.5,
                        fontWeight: FontWeight.w900,
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

class TaibahWelcomeCard extends StatelessWidget {
  final bool isArabic;
  const TaibahWelcomeCard({super.key, required this.isArabic});

  @override
  Widget build(BuildContext context) {
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    final compact = MediaQuery.sizeOf(context).width < 360 || textScale > 1.2;
    final logoSize = compact ? 52.0 : 60.0;

    return Container(
      padding: EdgeInsets.all(compact ? 14 : 16),
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
            width: logoSize,
            height: logoSize,
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(compact ? 14 : 16),
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
              borderRadius: BorderRadius.circular(compact ? 12 : 14),
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
          SizedBox(width: compact ? 12 : 16),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  isArabic
                      ? 'مرحبًا بطلاب جامعة طيبة'
                      : 'Welcome Taibah Students',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.left,
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: compact ? 17 : 18.5,
                    fontWeight: FontWeight.w900,
                    height: 1.3,
                  ),
                ),
                SizedBox(height: compact ? 5 : 6),
                Text(
                  isArabic
                      ? 'اختر خدمتك التعليمية الخاصة بك'
                      : 'Choose your educational service',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.left,
                  style: TextStyle(
                    color: const Color(0xEFFFFFFF),
                    fontSize: compact ? 12.8 : 13.5,
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
  Size get preferredSize => const Size.fromHeight(71);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      backgroundColor: AppColors.card,
      surfaceTintColor: Colors.transparent,
      elevation: 0,
      shadowColor: Colors.black.withValues(alpha: 0.08),
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
      bottom: const PreferredSize(
        preferredSize: Size.fromHeight(1),
        child: Divider(height: 1, thickness: 1, color: AppColors.border),
      ),
    );
  }

  Widget _buildIconButton({
    required IconData icon,
    required VoidCallback onTap,
    int count = 0,
    Color? color,
  }) {
    return _ReactiveCircleButton(
      icon: icon,
      onTap: onTap,
      count: count,
      accent: color,
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

class _ReactiveCircleButton extends StatefulWidget {
  const _ReactiveCircleButton({
    required this.icon,
    required this.onTap,
    this.count = 0,
    this.accent,
  });

  final IconData icon;
  final VoidCallback onTap;
  final int count;
  final Color? accent;

  @override
  State<_ReactiveCircleButton> createState() => _ReactiveCircleButtonState();
}

class _ReactiveCircleButtonState extends State<_ReactiveCircleButton> {
  bool _hovered = false;
  bool _pressed = false;

  void _setHovered(bool value) {
    if (_hovered == value) return;
    setState(() {
      _hovered = value;
      if (!value) {
        _pressed = false;
      }
    });
  }

  void _setPressed(bool value) {
    if (_pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    final hasAccent = widget.accent != null;
    final accent = widget.accent ?? AppColors.gradBlue;
    final active = _hovered || _pressed;
    final scale = _pressed ? 0.92 : (_hovered ? 1.06 : 1.0);

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => _setHovered(true),
      onExit: (_) => _setHovered(false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => _setPressed(true),
        onTapUp: (_) => _setPressed(false),
        onTapCancel: () => _setPressed(false),
        onTap: widget.onTap,
        child: Semantics(
          button: true,
          child: AnimatedScale(
            scale: scale,
            duration: const Duration(milliseconds: 120),
            curve: Curves.easeOut,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 160),
              curve: Curves.easeOut,
              width: 40,
              height: 40,
              decoration: hasAccent
                  ? BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        colors: [
                          accent,
                          Color.lerp(accent, AppColors.gradPurple, 0.24)!,
                        ],
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: accent.withValues(alpha: active ? 0.28 : 0.16),
                          blurRadius: active ? 16 : 10,
                          offset: Offset(0, active ? 7 : 4),
                        ),
                      ],
                    )
                  : BoxDecoration(
                      shape: BoxShape.circle,
                      color: active
                          ? accent.withValues(alpha: _pressed ? 0.16 : 0.10)
                          : AppColors.card,
                      border: Border.all(
                        color: active
                            ? accent.withValues(alpha: 0.34)
                            : AppColors.border,
                      ),
                      boxShadow: active
                          ? [
                              BoxShadow(
                                color: accent.withValues(alpha: 0.12),
                                blurRadius: 12,
                                offset: const Offset(0, 5),
                              ),
                            ]
                          : null,
                    ),
              child: Stack(
                children: [
                  Center(
                    child: Icon(
                      widget.icon,
                      color: hasAccent
                          ? Colors.white
                          : (active ? accent : AppColors.primaryText),
                      size: 20,
                    ),
                  ),
                  if (widget.count > 0)
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
              ),
            ),
          ),
        ),
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
    final width = MediaQuery.sizeOf(context).width;
    final textScale = MediaQuery.textScalerOf(context).scale(1);
    final compact = width < 380 || textScale > 1.15;

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
        padding: EdgeInsets.fromLTRB(
          compact ? 10 : 14,
          10,
          compact ? 10 : 14,
          12,
        ),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: compact ? 6 : 10,
            vertical: compact ? 10 : 12,
          ),
          decoration: BoxDecoration(
            color: AppColors.card,
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: AppColors.border),
            boxShadow: const [
              BoxShadow(
                color: Color(0x140F172A),
                blurRadius: 18,
                offset: Offset(0, 8),
              ),
            ],
          ),
          child: Row(
            children: List.generate(5, (i) {
              final selected = currentIndex == i;
              return Expanded(
                child: Padding(
                  padding: EdgeInsets.symmetric(horizontal: compact ? 1 : 2),
                  child: _BottomNavItemButton(
                    icon: icons[i],
                    label: labels[i],
                    selected: selected,
                    accent: accent,
                    compact: compact,
                    onTap: () => onChange(i),
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

class _BottomNavItemButton extends StatefulWidget {
  const _BottomNavItemButton({
    required this.icon,
    required this.label,
    required this.selected,
    required this.accent,
    required this.compact,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final Color accent;
  final bool compact;
  final VoidCallback onTap;

  @override
  State<_BottomNavItemButton> createState() => _BottomNavItemButtonState();
}

class _BottomNavItemButtonState extends State<_BottomNavItemButton> {
  bool _hovered = false;
  bool _pressed = false;

  void _setHovered(bool value) {
    if (_hovered == value) return;
    setState(() {
      _hovered = value;
      if (!value) {
        _pressed = false;
      }
    });
  }

  void _setPressed(bool value) {
    if (_pressed == value) return;
    setState(() => _pressed = value);
  }

  @override
  Widget build(BuildContext context) {
    final active = widget.selected || _hovered || _pressed;
    final selected = widget.selected;
    final scale = _pressed ? 0.96 : (_hovered ? 1.04 : 1.0);
    final foreground = selected
        ? Colors.white
        : active
        ? widget.accent
        : AppColors.mutedText;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => _setHovered(true),
      onExit: (_) => _setHovered(false),
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => _setPressed(true),
        onTapUp: (_) => _setPressed(false),
        onTapCancel: () => _setPressed(false),
        onTap: widget.onTap,
        child: Semantics(
          button: true,
          selected: selected,
          child: AnimatedScale(
            scale: scale,
            duration: const Duration(milliseconds: 120),
            curve: Curves.easeOut,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 170),
              curve: Curves.easeOut,
              padding: EdgeInsets.symmetric(
                horizontal: widget.compact ? 6 : 10,
                vertical: widget.compact ? 9 : 10,
              ),
              decoration: BoxDecoration(
                color: selected
                    ? widget.accent
                    : active
                    ? widget.accent.withValues(alpha: 0.10)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: selected
                      ? widget.accent.withValues(alpha: 0.18)
                      : active
                      ? widget.accent.withValues(alpha: 0.22)
                      : Colors.transparent,
                ),
                boxShadow: selected || _hovered
                    ? [
                        BoxShadow(
                          color: widget.accent.withValues(
                            alpha: selected ? 0.20 : 0.10,
                          ),
                          blurRadius: selected ? 14 : 10,
                          offset: Offset(0, selected ? 6 : 4),
                        ),
                      ]
                    : null,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    widget.icon,
                    size: widget.compact ? 23 : 25,
                    color: foreground,
                  ),
                  SizedBox(height: widget.compact ? 5 : 6),
                  Text(
                    widget.label,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: widget.compact ? 10.8 : 12,
                      fontWeight: FontWeight.w900,
                      color: foreground,
                      height: 1.1,
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
}
