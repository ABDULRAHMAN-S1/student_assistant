import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app/backend_status_banner.dart';
import '../app/backend_status_controller.dart';
import '../features/ai_assistant/data/local/chat_history_store.dart';
import '../features/ai_assistant/data/remote/assistant_api_client.dart';
import '../features/ai_assistant/data/repositories/assistant_repository.dart';
import '../features/ai_assistant/data/services/message_translation_service.dart';
import '../features/ai_assistant/domain/models/chat_message.dart';
import '../features/ai_assistant/domain/models/regulation_source.dart';
import '../features/ai_assistant/presentation/assistant_error_messages.dart';
import '../features/courses/data/demo/demo_course_repository.dart';
import '../features/events/data/demo/demo_event_repository.dart';
import '../features/profile/data/demo/demo_profile_repository.dart';
import '../features/profile/data/local/profile_store.dart';
import '../features/profile/domain/models/academic_context.dart';
import '../features/profile/domain/models/student_profile.dart';
import '../features/recommendations/data/services/recommendation_engine.dart';
import '../features/recommendations/domain/models/recommendation_item.dart';
import 'regulation_search_page.dart';

class AIChatPage extends StatefulWidget {
  final bool isArabic;
  final int profileRefreshToken;
  final Future<void> Function()? onSessionExpired;

  const AIChatPage({
    super.key,
    required this.isArabic,
    this.profileRefreshToken = 0,
    this.onSessionExpired,
  });

  @override
  State<AIChatPage> createState() => _AIChatPageState();
}

class _AIChatPageState extends State<AIChatPage> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  final AssistantRepository _assistantRepository = const AssistantRepository();
  final ChatHistoryStore _chatHistoryStore = const ChatHistoryStore();
  final MessageTranslationService _messageTranslationService =
      const MessageTranslationService();
  final DemoCourseRepository _courseRepository = DemoCourseRepository();
  final DemoEventRepository _eventRepository = DemoEventRepository();
  final RecommendationEngine _recommendationEngine =
      const RecommendationEngine();
  bool _isTyping = false;
  bool _isLoadingHistory = true;
  late bool _activeHistoryIsArabic;
  List<String> _personalizedSuggestedQuestions = const [];

  final Color _primaryCyan = const Color(0xFF5421D9);
  final Color _secondaryBlue = const Color(0xFF6D0FE0);
  final Color _accentPurple = const Color(0xFF3F2ABF);

  List<String> get _suggestedQuestions => widget.isArabic
      ? const [
          'ما عقوبة الغش في الاختبار؟',
          'هل يسمح بتصوير المحاضرات؟',
          'ما شروط السكن الجامعي؟',
          'ماذا يحدث إذا غبت عن الاختبار النهائي؟',
        ]
      : const [
          'What happens if a student misses a final exam?',
          'Can I withdraw from a course?',
          'Is smoking allowed on campus?',
          'What are the housing conditions?',
        ];

  static const List<String> _arabicReferenceLabels = [
    'المصدر المعتمد:',
    'المرجع:',
  ];
  static const List<String> _englishReferenceLabels = [
    'Official source:',
    'Source:',
  ];

  @override
  void initState() {
    super.initState();
    _activeHistoryIsArabic = widget.isArabic;
    _initializeChat();
    _loadStudentAwareSuggestions();
  }

  @override
  void didUpdateWidget(covariant AIChatPage oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.isArabic != widget.isArabic) {
      _syncActiveHistoryBucket();
    }
    if (oldWidget.isArabic != widget.isArabic ||
        oldWidget.profileRefreshToken != widget.profileRefreshToken) {
      _loadStudentAwareSuggestions();
    }
  }

  Future<void> _syncActiveHistoryBucket() async {
    final nextHistoryIsArabic = widget.isArabic;
    if (_activeHistoryIsArabic == nextHistoryIsArabic) {
      return;
    }

    if (!_isLoadingHistory) {
      await _persistHistory();
    }

    setState(() {
      _activeHistoryIsArabic = nextHistoryIsArabic;
    });

    if (_isLoadingHistory) {
      return;
    }

    await _initializeChat();
  }

  Future<void> _initializeChat() async {
    final storedHistory = await _chatHistoryStore.loadHistory(
      isArabic: _activeHistoryIsArabic,
    );
    if (!mounted) return;

    setState(() {
      _messages.clear();
      if (storedHistory.isEmpty) {
        _messages.add(
          ChatMessage(
            text: widget.isArabic
                ? 'مرحباً! 👋 أنا مساعدك الذكي. كيف يمكنني مساعدتك اليوم؟'
                : 'Hello! 👋 I\'m your AI assistant. How can I help you today?',
            isUser: false,
            timestamp: DateTime.now(),
            canFeedback: false,
          ),
        );
      } else {
        _messages.addAll(storedHistory.map(ChatMessage.fromMap));
      }
      _isLoadingHistory = false;
    });

    await _persistHistory();
    _scrollToBottom();
  }

  Future<void> _loadStudentAwareSuggestions() async {
    final profileStore = await ProfileStore.open();
    final profileRepository = DemoProfileRepository(profileStore: profileStore);
    final profile = await profileRepository.loadProfile();

    if (!mounted) return;

    if (profile == null) {
      setState(() {
        _personalizedSuggestedQuestions = const [];
      });
      return;
    }

    final recommendations = _recommendationEngine.generate(
      profile: profile,
      courses: _courseRepository.getCourses(),
      events: _eventRepository.getEvents(),
      maxResults: 4,
      isArabic: widget.isArabic,
    );
    final prompts = _buildStudentAwarePrompts(profile, recommendations);

    if (!mounted) return;
    setState(() {
      _personalizedSuggestedQuestions = prompts;
    });
  }

  List<String> _buildStudentAwarePrompts(
    StudentProfile profile,
    List<RecommendationItem> recommendations,
  ) {
    final prompts = <String>[];
    final seen = <String>{};

    void addPrompt(String value) {
      if (value.trim().isEmpty) return;
      if (seen.add(value)) {
        prompts.add(value);
      }
    }

    final academicContext = profile.academicContext;
    final profileSignals = _buildProfileSignalsText(profile, recommendations);
    final hasAcademicLoadContext =
        academicContext.specialization.trim().isNotEmpty ||
        (academicContext.academicLevel?.trim().isNotEmpty ?? false) ||
        (academicContext.currentSemester?.trim().isNotEmpty ?? false) ||
        academicContext.interests.isNotEmpty ||
        academicContext.enrolledCourseIds.isNotEmpty;

    final hasCourseRecommendation = recommendations.any(
      (item) => item.type == RecommendationItem.courseType,
    );
    final hasExamRecommendation = recommendations.any(_isExamRecommendation);
    final hasWorkshopRecommendation = recommendations.any(
      _isWorkshopRecommendation,
    );
    final isTechnicalProfile = _matchesAny(profileSignals, const [
      'computer',
      'computing',
      'software',
      'programming',
      'artificial intelligence',
      'information systems',
      'cyber',
      'data',
      'علوم الحاسب',
      'حاسب',
      'حاسوب',
      'برمجة',
      'الذكاء الاصطناعي',
      'تقنية',
      'نظم المعلومات',
      'أمن سيبراني',
      'software engineering',
      'programming workshop',
    ]);
    final isHealthProfile = _matchesAny(profileSignals, const [
      'medicine',
      'medical',
      'health',
      'pharmacy',
      'pharmd',
      'nursing',
      'clinical',
      'lab',
      'طب',
      'صيدلة',
      'تمريض',
      'صحي',
      'سريري',
      'إكلينيكي',
      'مختبر',
      'تدريب ميداني',
      'practical training',
    ]);
    final hasTrainingContext = _matchesAny(profileSignals, const [
      'training',
      'internship',
      'clinical',
      'practical',
      'lab',
      'امتياز',
      'تدريب',
      'إكلينيكي',
      'عملي',
      'ميداني',
      'مختبر',
    ]);
    final hasGeneralEducationContext = _matchesAny(profileSignals, const [
      'general education',
      'elective',
      'general course',
      'المقررات العامة',
      'المقررات الاختيارية',
      'اختياري',
      'اختيارية',
      'عام',
    ]);
    final hasGradingContext = _matchesAny(profileSignals, const [
      'gpa',
      'grade',
      'grading',
      'dn',
      'ic',
      'wp',
      'wf',
      'np',
      'المعدل',
      'التقديرات',
      'التقدير',
      'dn',
      'ic',
    ]);
    final isSeniorProfile = _isSeniorProfile(academicContext, profileSignals);
    final isJuniorProfile = _isJuniorProfile(academicContext, profileSignals);

    if (widget.isArabic) {
      if (isTechnicalProfile) {
        addPrompt('هل يسمح بتصوير المحاضرات أو المواد التعليمية بدون إذن؟');
        addPrompt('ما عقوبة الغش أو الاعتداء على الحقوق الفكرية؟');
      }
      if (isHealthProfile || hasTrainingContext) {
        addPrompt('ما الحد الأدنى للحضور في الدروس العملية أو التدريب؟');
        addPrompt('ماذا يحدث إذا غاب الطالب عن الاختبار النهائي بعذر؟');
      }
      if (isSeniorProfile) {
        addPrompt('ما متطلبات التخرج في البرنامج؟');
        addPrompt('ما شروط الحصول على مرتبة الشرف؟');
      }
      if (isJuniorProfile) {
        addPrompt('متى يطبق الإنذار الأكاديمي؟');
        addPrompt('كيف يحسب المعدل الفصلي والتراكمي؟');
      }
      if (hasGeneralEducationContext) {
        addPrompt('ما سياسة المقررات العامة والاختيارية؟');
      }
      if (hasGradingContext || isHealthProfile || isJuniorProfile) {
        addPrompt('ما معنى DN وبقية رموز التقديرات؟');
      }
      if (hasAcademicLoadContext || hasCourseRecommendation) {
        addPrompt('ما الحد الأعلى والحد الأدنى للعبء الدراسي؟');
        addPrompt('هل أستطيع الانسحاب من مقرر؟');
      }
      if (hasExamRecommendation) {
        addPrompt('ماذا يحدث إذا غاب الطالب عن الاختبار النهائي؟');
        addPrompt('ما عقوبة الغش في الاختبار؟');
      }
      if (hasWorkshopRecommendation || hasCourseRecommendation) {
        addPrompt('هل يسمح بتسجيل أو تصوير المحاضرات بدون إذن؟');
      }
      if (prompts.isEmpty) {
        addPrompt('هل أستطيع الانسحاب من مقرر؟');
        addPrompt('ماذا يحدث إذا غاب الطالب عن الاختبار النهائي؟');
        addPrompt('ما نظام التقديرات؟');
        addPrompt('هل يسمح بتصوير المحاضرات بدون إذن؟');
      }
    } else {
      if (isTechnicalProfile) {
        addPrompt(
          'Is recording lectures or course materials allowed without permission?',
        );
        addPrompt(
          'What is the penalty for cheating or violating intellectual property?',
        );
      }
      if (isHealthProfile || hasTrainingContext) {
        addPrompt(
          'What is the minimum attendance required for practical training?',
        );
        addPrompt(
          'What happens if a student misses a final exam with an excuse?',
        );
      }
      if (isSeniorProfile) {
        addPrompt('What are the graduation requirements for the program?');
        addPrompt('What are the requirements for graduating with honors?');
      }
      if (isJuniorProfile) {
        addPrompt('When is an academic warning applied?');
        addPrompt('How are the semester and cumulative GPA calculated?');
      }
      if (hasGeneralEducationContext) {
        addPrompt('What is the General Education and Elective Courses Policy?');
      }
      if (hasGradingContext || isHealthProfile || isJuniorProfile) {
        addPrompt('What do DN and other grading codes mean?');
      }
      if (hasAcademicLoadContext || hasCourseRecommendation) {
        addPrompt('What are the minimum and maximum academic load limits?');
        addPrompt('Can I withdraw from a course?');
      }
      if (hasExamRecommendation) {
        addPrompt('What happens if a student misses a final exam?');
        addPrompt('What is the penalty for cheating in an exam?');
      }
      if (hasWorkshopRecommendation || hasCourseRecommendation) {
        addPrompt('Is recording lectures allowed without permission?');
      }
      if (prompts.isEmpty) {
        addPrompt('Can I withdraw from a course?');
        addPrompt('What happens if a student misses a final exam?');
        addPrompt('What is the grading system?');
        addPrompt('Is recording lectures allowed without permission?');
      }
    }

    return prompts.take(4).toList(growable: false);
  }

  String _buildProfileSignalsText(
    StudentProfile profile,
    List<RecommendationItem> recommendations,
  ) {
    final academicContext = profile.academicContext;
    final parts = <String>[
      profile.fullName,
      academicContext.specialization,
      academicContext.academicLevel ?? '',
      academicContext.currentSemester ?? '',
      ...academicContext.interests,
      ...academicContext.enrolledCourseIds,
      ...recommendations.map(
        (item) => '${item.title} ${item.description} ${item.reason}',
      ),
    ];
    return parts.join(' ').toLowerCase();
  }

  bool _matchesAny(String text, List<String> keywords) {
    return keywords.any((keyword) => text.contains(keyword.toLowerCase()));
  }

  int? _parseSemesterNumber(String? rawValue) {
    if (rawValue == null || rawValue.trim().isEmpty) {
      return null;
    }

    const arabicDigits = {
      '٠': '0',
      '١': '1',
      '٢': '2',
      '٣': '3',
      '٤': '4',
      '٥': '5',
      '٦': '6',
      '٧': '7',
      '٨': '8',
      '٩': '9',
    };

    final normalizedDigits = rawValue
        .split('')
        .map((char) => arabicDigits[char] ?? char)
        .join();
    final match = RegExp(r'\d+').firstMatch(normalizedDigits);
    if (match == null) {
      return null;
    }

    return int.tryParse(match.group(0)!);
  }

  bool _isSeniorProfile(AcademicContext context, String signals) {
    final semester = _parseSemesterNumber(context.currentSemester);
    if (semester != null && semester >= 7) {
      return true;
    }

    return _matchesAny(signals, const [
      'senior',
      'final year',
      'graduation',
      'graduate',
      'الخريج',
      'التخرج',
      'سنة التخرج',
      'المستوى الثامن',
      'المستوى السابع',
    ]);
  }

  bool _isJuniorProfile(AcademicContext context, String signals) {
    final semester = _parseSemesterNumber(context.currentSemester);
    if (semester != null && semester > 0 && semester <= 4) {
      return true;
    }

    return _matchesAny(signals, const [
      'freshman',
      'sophomore',
      'first year',
      'second year',
      'المستوى الأول',
      'المستوى الثاني',
      'المستوى الثالث',
      'المستوى الرابع',
      'مستجد',
    ]);
  }

  bool _isExamRecommendation(RecommendationItem item) {
    final haystack = '${item.title} ${item.description} ${item.reason}'
        .toLowerCase();
    return haystack.contains('exam') ||
        haystack.contains('midterm') ||
        haystack.contains('final') ||
        haystack.contains('deadline') ||
        haystack.contains('اختبار') ||
        haystack.contains('امتحان') ||
        haystack.contains('نهائي');
  }

  bool _isWorkshopRecommendation(RecommendationItem item) {
    final haystack = '${item.title} ${item.description} ${item.reason}'
        .toLowerCase();
    return haystack.contains('workshop') ||
        haystack.contains('lecture') ||
        haystack.contains('course') ||
        haystack.contains('programming') ||
        haystack.contains('ورشة') ||
        haystack.contains('محاضرة') ||
        haystack.contains('مقرر') ||
        haystack.contains('برمجة');
  }

  String _studentAwareHintText() {
    return widget.isArabic
        ? 'أسئلة مبنية على ملفك الأكاديمي وتوصياتك الحالية.'
        : 'Questions based on your academic context and current recommendations.';
  }

  Future<void>? _activePersist;
  bool _persistAgain = false;

  Future<void> _persistHistory() async {
    if (_activePersist != null) {
      _persistAgain = true;
      await _activePersist;
      return;
    }

    Future<void> doWrite() async {
      do {
        _persistAgain = false;
        await _chatHistoryStore.saveHistory(
          isArabic: _activeHistoryIsArabic,
          messages: _messages.map((message) => message.toMap()).toList(),
        );
      } while (_persistAgain);
    }

    _activePersist = doWrite();
    try {
      await _activePersist;
    } finally {
      _activePersist = null;
    }
  }

  bool _isSameLogicalMessage(ChatMessage left, ChatMessage right) {
    return left.timestamp == right.timestamp &&
        left.isUser == right.isUser &&
        left.text == right.text;
  }

  int _resolveMessageIndex(ChatMessage message, {int? preferredIndex}) {
    if (preferredIndex != null &&
        preferredIndex >= 0 &&
        preferredIndex < _messages.length &&
        _isSameLogicalMessage(_messages[preferredIndex], message)) {
      return preferredIndex;
    }

    return _messages.indexWhere(
      (candidate) => _isSameLogicalMessage(candidate, message),
    );
  }

  bool get _showSuggestedQuestions =>
      !_isLoadingHistory &&
      !_isTyping &&
      _messages.where((message) => message.isUser).isEmpty;

  void _addBotMessage(
    String text, {
    List<RegulationSource> sources = const [],
    bool canFeedback = false,
    bool canTranslate = false,
    String routeMode = '',
  }) {
    setState(() {
      _messages.add(
        ChatMessage(
          text: text,
          isUser: false,
          timestamp: DateTime.now(),
          sources: sources,
          canFeedback: canFeedback,
          canTranslate: canTranslate,
          routeMode: routeMode,
        ),
      );
    });
    _persistHistory();
    _scrollToBottom();
  }

  bool _isSessionError(AssistantApiException error) {
    return error.kind == AssistantApiErrorKind.authenticationRequired ||
        error.kind == AssistantApiErrorKind.sessionExpired ||
        error.kind == AssistantApiErrorKind.unauthorized;
  }

  bool _shouldRefreshBackendIndicator(AssistantApiException error) {
    return error.kind == AssistantApiErrorKind.network ||
        error.kind == AssistantApiErrorKind.timeout ||
        error.kind == AssistantApiErrorKind.invalidResponse;
  }

  bool get _isBackendOffline =>
      BackendStatusController.instance.snapshot.isOffline;

  String get _backendUnavailableMessage => widget.isArabic
      ? 'الخادم غير متاح حالياً. شغّل الـ backend المحلي ثم حدّث الحالة من الشريط العلوي.'
      : 'The backend is currently unavailable. Start the local backend, then refresh the status from the header.';

  void _showBackendUnavailableSnackBar() {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(_backendUnavailableMessage)));
  }

  bool _ensureBackendAvailable() {
    if (!_isBackendOffline) {
      return true;
    }
    _showBackendUnavailableSnackBar();
    return false;
  }

  Future<void> _sendMessage({String? presetText}) async {
    if (_isTyping) return;

    final text = (presetText ?? _messageController.text).trim();
    if (text.isEmpty) return;
    if (!_ensureBackendAvailable()) return;

    setState(() {
      _messages.add(
        ChatMessage(text: text, isUser: true, timestamp: DateTime.now()),
      );
      _isTyping = true;
    });

    _messageController.clear();
    await _persistHistory();
    _scrollToBottom();

    try {
      final response = await _assistantRepository.ask(text);
      if (!mounted) return;

      setState(() => _isTyping = false);
      _addBotMessage(
        response.answer.isEmpty
            ? (widget.isArabic
                  ? "ما قدرت أطلع جواب."
                  : "I couldn't generate an answer.")
            : response.answer,
        sources: response.sources,
        canFeedback: response.sources.isNotEmpty,
        canTranslate: true,
        routeMode: response.routeMode,
      );
    } on AssistantApiException catch (error) {
      if (!mounted) return;

      setState(() => _isTyping = false);
      if (_isSessionError(error)) {
        await widget.onSessionExpired?.call();
        return;
      }
      if (_shouldRefreshBackendIndicator(error)) {
        BackendStatusController.instance.refresh(showCheckingState: false);
      }

      _addBotMessage(
        localizeAssistantError(
          error,
          isArabic: widget.isArabic,
          action: AssistantRequestAction.chat,
        ),
      );
    } catch (_) {
      if (!mounted) return;

      setState(() => _isTyping = false);
      _addBotMessage(
        localizeUnexpectedAssistantError(
          isArabic: widget.isArabic,
          action: AssistantRequestAction.chat,
        ),
      );
    }
  }

  Future<void> _clearHistory() async {
    final shouldClear = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(widget.isArabic ? 'مسح المحادثة' : 'Clear Chat'),
        content: Text(
          widget.isArabic
              ? 'هل تريد حذف سجل المحادثة الحالي؟'
              : 'Do you want to delete the current chat history?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: Text(widget.isArabic ? 'إلغاء' : 'Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: Text(widget.isArabic ? 'مسح' : 'Clear'),
          ),
        ],
      ),
    );

    if (shouldClear != true || !mounted) return;

    final historyBucketToClear = _activeHistoryIsArabic;
    await _chatHistoryStore.clearHistory(isArabic: historyBucketToClear);
    setState(() {
      _activeHistoryIsArabic = widget.isArabic;
      _messages
        ..clear()
        ..add(
          ChatMessage(
            text: widget.isArabic
                ? 'مرحباً! 👋 أنا مساعدك الذكي. كيف يمكنني مساعدتك اليوم؟'
                : 'Hello! 👋 I\'m your AI assistant. How can I help you today?',
            isUser: false,
            timestamp: DateTime.now(),
            canFeedback: false,
          ),
        );
    });
    await _persistHistory();
  }

  Future<void> _openSearchPage() async {
    await Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => RegulationSearchPage(
          isArabic: widget.isArabic,
          onSessionExpired: widget.onSessionExpired,
        ),
      ),
    );
  }

  int _referenceSplitIndex(String text) {
    final indices = <int>[
      ..._arabicReferenceLabels.map(text.indexOf).where((index) => index >= 0),
      ..._englishReferenceLabels.map(text.indexOf).where((index) => index >= 0),
    ];

    if (indices.isEmpty) {
      return -1;
    }
    indices.sort();
    return indices.first;
  }

  String _messageBodyText(ChatMessage message) {
    final text = message.text.trim();
    final splitIndex = _referenceSplitIndex(text);

    if (splitIndex < 0) {
      return text;
    }
    return text.substring(0, splitIndex).trim();
  }

  String? _inlineReferenceText(ChatMessage message) {
    final text = message.text.trim();
    final splitIndex = _referenceSplitIndex(text);

    if (splitIndex < 0) {
      return null;
    }

    final referenceText = text.substring(splitIndex).trim();
    return referenceText.isEmpty ? null : referenceText;
  }

  String _referenceHeading(RegulationSource source) {
    if (source.primaryDisplayTitle.isNotEmpty) {
      return source.primaryDisplayTitle;
    }
    return source.sourceTypeLabel(isArabic: widget.isArabic);
  }

  String _normalizeReferenceKeyPart(String value) {
    return value.trim().toLowerCase().replaceAll(RegExp(r'\s+'), ' ');
  }

  List<RegulationSource> _dedupeSources(List<RegulationSource> sources) {
    final grouped = <String, RegulationSource>{};

    for (final source in sources) {
      final snippet = source.content.isNotEmpty
          ? source.content
          : source.contentPreview;
      final key = [
        _normalizeReferenceKeyPart(source.docType),
        _normalizeReferenceKeyPart(source.documentTitle),
        _normalizeReferenceKeyPart(source.article),
        _normalizeReferenceKeyPart(source.cleanedSection),
      ].join('|');

      final existing = grouped[key];
      if (existing == null) {
        grouped[key] = source;
        continue;
      }

      final existingSnippet = existing.content.isNotEmpty
          ? existing.content
          : existing.contentPreview;
      if (snippet.length > existingSnippet.length) {
        grouped[key] = source;
      }
    }

    return grouped.values.toList(growable: false);
  }

  String _mixedScriptSafeText(String text) {
    return text.replaceAllMapped(
      RegExp(r'\b[A-Za-z]{1,4}\b'),
      (match) => '\u2066${match.group(0)}\u2069',
    );
  }

  Widget _buildMixedScriptText(
    String text, {
    required TextStyle style,
    TextAlign? textAlign,
    int? maxLines,
    TextOverflow? overflow,
  }) {
    return Text(
      _mixedScriptSafeText(text),
      textDirection: widget.isArabic ? TextDirection.rtl : TextDirection.ltr,
      textAlign:
          textAlign ?? (widget.isArabic ? TextAlign.right : TextAlign.left),
      maxLines: maxLines,
      overflow: overflow,
      style: style,
    );
  }

  bool _isListLikeMessage(String text) {
    final trimmed = text.trimLeft();
    return trimmed.contains('\n- ') || trimmed.startsWith('- ');
  }

  bool _isShortAnswerText(String text) {
    final normalized = text.trim();
    if (normalized.isEmpty || _isListLikeMessage(normalized)) {
      return false;
    }
    return normalized.length <= 90 && !normalized.contains('\n');
  }

  Widget _buildMessageTextContent(String text, {required bool isUser}) {
    final baseStyle = _messageBodyStyle(isUser);
    final emphasisStyle = baseStyle.copyWith(
      fontSize: isUser ? baseStyle.fontSize : 15.6,
      fontWeight: FontWeight.w600,
      height: widget.isArabic ? 1.72 : 1.54,
    );

    if (_isListLikeMessage(text)) {
      final lines = text
          .split('\n')
          .map((line) => line.trim())
          .where((line) => line.isNotEmpty)
          .toList(growable: false);
      final intro = lines.where((line) => !line.startsWith('- ')).join(' ');
      final bullets = lines
          .where((line) => line.startsWith('- '))
          .map((line) => line.substring(2).trim())
          .where((line) => line.isNotEmpty)
          .toList(growable: false);

      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (intro.isNotEmpty) _buildMixedScriptText(intro, style: baseStyle),
          if (intro.isNotEmpty && bullets.isNotEmpty) const SizedBox(height: 8),
          ...bullets.map(
            (bullet) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 7),
                    child: Container(
                      width: 5,
                      height: 5,
                      decoration: BoxDecoration(
                        color: isUser ? Colors.white : _primaryCyan,
                        shape: BoxShape.circle,
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _buildMixedScriptText(bullet, style: baseStyle),
                  ),
                ],
              ),
            ),
          ),
        ],
      );
    }

    return _buildMixedScriptText(
      text,
      style: _isShortAnswerText(text) ? emphasisStyle : baseStyle,
    );
  }

  String _compactReferenceLine(RegulationSource source) {
    final heading = _referenceHeading(source);
    final parts = <String>[
      source.sourceTypeTag(isArabic: widget.isArabic),
      heading,
      if (source.secondaryDisplayArticle.isNotEmpty)
        '• ${source.secondaryDisplayArticle}',
      if (source.secondaryDisplaySection.isNotEmpty)
        '• ${source.secondaryDisplaySection}',
    ];
    return parts.join(' ');
  }

  String _referenceFieldLabel(String arabic, String english) {
    return widget.isArabic ? arabic : english;
  }

  Widget _buildReferenceField({
    required String label,
    required String value,
    Color? valueColor,
    FontWeight valueWeight = FontWeight.w600,
  }) {
    if (value.trim().isEmpty) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: TextStyle(
              color: Colors.grey[600],
              fontSize: 12.5,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 4),
          _buildMixedScriptText(
            value,
            style: TextStyle(
              color: valueColor ?? Colors.black87,
              fontSize: 14,
              fontWeight: valueWeight,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  TextStyle _messageBodyStyle(bool isUser) {
    return TextStyle(
      color: isUser ? Colors.white : Colors.black87,
      fontSize: 15.2,
      fontWeight: FontWeight.w500,
      height: widget.isArabic ? 1.62 : 1.48,
    );
  }

  Widget? _buildReferenceSummaryBlock(
    ChatMessage message,
    String? inlineReferenceText,
  ) {
    if (message.isUser) {
      return null;
    }

    final label = widget.isArabic ? 'المصدر المعتمد' : 'Official source';
    final inlineLines = inlineReferenceText == null
        ? const <String>[]
        : inlineReferenceText
              .split('\n')
              .map((line) => line.trim())
              .where((line) => line.isNotEmpty)
              .toList(growable: true);
    if (inlineLines.isNotEmpty &&
        (_arabicReferenceLabels.contains(inlineLines.first) ||
            _englishReferenceLabels.contains(inlineLines.first))) {
      inlineLines.removeAt(0);
    }

    final dedupedSources = _dedupeSources(message.sources);

    final lines = message.sources.isNotEmpty
        ? dedupedSources
              .map(_compactReferenceLine)
              .take(3)
              .toList(growable: false)
        : inlineLines;

    if (lines.isEmpty) {
      return null;
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 12),
      decoration: BoxDecoration(
        color: const Color(0xFFF7F8FC),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.grey.shade300),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Icon(
                Icons.description_outlined,
                size: 15,
                color: Colors.grey.shade700,
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  label,
                  style: TextStyle(
                    color: Colors.grey.shade800,
                    fontSize: 12.4,
                    fontWeight: FontWeight.w800,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          ...lines.map(
            (line) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: _buildMixedScriptText(
                line,
                style: TextStyle(
                  color: Colors.black87,
                  fontSize: 12.6,
                  height: widget.isArabic ? 1.5 : 1.4,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageActionButton({
    required String label,
    required IconData icon,
    required VoidCallback? onPressed,
    Color? foregroundColor,
  }) {
    final resolvedColor = foregroundColor ?? Colors.grey.shade700;
    return TextButton.icon(
      onPressed: onPressed,
      icon: Icon(icon, size: 15, color: resolvedColor),
      label: Text(label),
      style: TextButton.styleFrom(
        foregroundColor: resolvedColor,
        backgroundColor: resolvedColor.withValues(alpha: 0.08),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        minimumSize: Size.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        visualDensity: const VisualDensity(horizontal: -2, vertical: -2),
        textStyle: const TextStyle(fontSize: 12.0, fontWeight: FontWeight.w700),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  String _questionForMessage(ChatMessage message) {
    final messageIndex = _messages.indexOf(message);
    if (messageIndex <= 0) {
      return '';
    }

    for (int index = messageIndex - 1; index >= 0; index--) {
      final candidate = _messages[index];
      if (candidate.isUser) {
        return candidate.text;
      }
    }
    return '';
  }

  Future<String?> _showFeedbackReasonSheet() {
    final reasons = widget.isArabic
        ? ['الإجابة غير دقيقة', 'لم تجب على سؤالي', 'الإجابة غير واضحة']
        : ['Inaccurate answer', "Didn't answer my question", 'Unclear answer'];

    return showModalBottomSheet<String>(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: Text(
                    widget.isArabic ? 'ما السبب؟' : 'What went wrong?',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                for (final reason in reasons)
                  ListTile(
                    dense: true,
                    title: Text(reason),
                    onTap: () => Navigator.pop(context, reason),
                  ),
                const Divider(height: 1),
                ListTile(
                  dense: true,
                  title: Text(
                    widget.isArabic ? 'تخطي' : 'Skip',
                    style: TextStyle(color: Colors.grey.shade600),
                  ),
                  onTap: () => Navigator.pop(context, ''),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _submitFeedback(ChatMessage message, bool helpful) async {
    if (!message.canFeedback) return;

    final messageIndex = _resolveMessageIndex(message);
    if (messageIndex < 0) return;
    if (!_ensureBackendAvailable()) return;

    String reason = '';
    if (!helpful) {
      final selected = await _showFeedbackReasonSheet();
      if (!mounted) return;
      if (selected == null) return; // dismissed without choosing
      reason = selected;
    }

    final previousHelpful = message.helpful;
    final question = _questionForMessage(message);

    setState(() {
      _messages[messageIndex] = message.copyWith(helpful: helpful);
    });
    await _persistHistory();

    try {
      await _assistantRepository.sendFeedback(
        question: question,
        answer: message.text,
        helpful: helpful,
        language: widget.isArabic ? 'ar' : 'en',
        sources: message.sources,
        reason: reason,
        routeMode: message.routeMode,
      );
      if (!helpful && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              widget.isArabic
                  ? 'شكراً، ملاحظتك تساعدنا على التحسين'
                  : 'Thanks, your feedback helps us improve',
            ),
            duration: const Duration(seconds: 2),
          ),
        );
      }
    } on AssistantApiException catch (error) {
      if (!mounted) return;

      final currentMessageIndex = _resolveMessageIndex(
        message,
        preferredIndex: messageIndex,
      );
      if (currentMessageIndex < 0) return;

      setState(() {
        _messages[currentMessageIndex] = message.copyWith(
          helpful: previousHelpful,
        );
      });
      await _persistHistory();

      if (_isSessionError(error)) {
        await widget.onSessionExpired?.call();
        return;
      }
      if (_shouldRefreshBackendIndicator(error)) {
        BackendStatusController.instance.refresh(showCheckingState: false);
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            localizeAssistantError(
              error,
              isArabic: widget.isArabic,
              action: AssistantRequestAction.feedback,
            ),
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;

      final currentMessageIndex = _resolveMessageIndex(
        message,
        preferredIndex: messageIndex,
      );
      if (currentMessageIndex < 0) return;

      setState(() {
        _messages[currentMessageIndex] = message.copyWith(
          helpful: previousHelpful,
        );
      });
      await _persistHistory();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            localizeUnexpectedAssistantError(
              isArabic: widget.isArabic,
              action: AssistantRequestAction.feedback,
            ),
          ),
        ),
      );
    }
  }

  String _translateButtonLabel(ChatMessage message) {
    if (message.isTranslating) {
      return widget.isArabic ? 'جاري الترجمة...' : 'Translating...';
    }
    if (message.translatedText != null && message.isShowingTranslation) {
      return widget.isArabic ? 'إظهار الأصل' : 'Show original';
    }
    return widget.isArabic ? 'ترجمة' : 'Translate';
  }

  Future<void> _toggleMessageTranslation(ChatMessage message) async {
    if (message.isUser) return;

    final messageIndex = _resolveMessageIndex(message);
    if (messageIndex < 0) return;

    if (message.translatedText != null) {
      setState(() {
        _messages[messageIndex] = message.copyWith(
          isShowingTranslation: !message.isShowingTranslation,
        );
      });
      await _persistHistory();
      return;
    }

    if (!_ensureBackendAvailable()) return;

    setState(() {
      _messages[messageIndex] = message.copyWith(isTranslating: true);
    });

    try {
      final result = await _messageTranslationService.translate(
        _messageBodyText(message),
      );
      if (!mounted) return;

      final currentMessageIndex = _resolveMessageIndex(
        message,
        preferredIndex: messageIndex,
      );
      if (currentMessageIndex < 0) return;

      setState(() {
        _messages[currentMessageIndex] = message.copyWith(
          translatedText: result.translatedText,
          isShowingTranslation: true,
          isTranslating: false,
        );
      });
      await _persistHistory();
    } on AssistantApiException catch (error) {
      if (!mounted) return;

      final currentMessageIndex = _resolveMessageIndex(
        message,
        preferredIndex: messageIndex,
      );
      if (currentMessageIndex < 0) return;

      setState(() {
        _messages[currentMessageIndex] = message.copyWith(isTranslating: false);
      });

      if (_isSessionError(error)) {
        await widget.onSessionExpired?.call();
        return;
      }
      if (_shouldRefreshBackendIndicator(error)) {
        BackendStatusController.instance.refresh(showCheckingState: false);
      }

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            localizeAssistantError(
              error,
              isArabic: widget.isArabic,
              action: AssistantRequestAction.translate,
            ),
          ),
        ),
      );
    } catch (_) {
      if (!mounted) return;

      final currentMessageIndex = _resolveMessageIndex(
        message,
        preferredIndex: messageIndex,
      );
      if (currentMessageIndex < 0) return;

      setState(() {
        _messages[currentMessageIndex] = message.copyWith(isTranslating: false);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            localizeUnexpectedAssistantError(
              isArabic: widget.isArabic,
              action: AssistantRequestAction.translate,
            ),
          ),
        ),
      );
    }
  }

  void _showReferenceView(ChatMessage message) {
    if (message.sources.isEmpty) return;

    final visibleSources = _dedupeSources(message.sources);

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) => SafeArea(
        top: false,
        child: Container(
          decoration: const BoxDecoration(
            color: Color(0xFFF8F9FC),
            borderRadius: BorderRadius.vertical(top: Radius.circular(28)),
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 20),
            child: SingleChildScrollView(
              child: Column(
                children: [
                  Center(
                    child: Container(
                      width: 42,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: 14),
                      decoration: BoxDecoration(
                        color: Colors.grey.shade300,
                        borderRadius: BorderRadius.circular(999),
                      ),
                    ),
                  ),
                  ...visibleSources.asMap().entries.map((entry) {
                    final index = entry.key;
                    final source = entry.value;
                    final heading = _referenceHeading(source);
                    final snippet = source.content.isNotEmpty
                        ? source.content
                        : source.contentPreview;
                    return Padding(
                      padding: EdgeInsets.only(
                        bottom: index == visibleSources.length - 1 ? 0 : 14,
                      ),
                      child: Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(18),
                          border: Border.all(color: Colors.grey.shade300),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x12000000),
                              blurRadius: 10,
                              offset: Offset(0, 5),
                            ),
                          ],
                        ),
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
                                    color: _primaryCyan.withValues(alpha: 0.10),
                                    borderRadius: BorderRadius.circular(999),
                                  ),
                                  child: Text(
                                    source.sourceTypeTag(
                                      isArabic: widget.isArabic,
                                    ),
                                    style: TextStyle(
                                      color: _primaryCyan,
                                      fontWeight: FontWeight.w800,
                                      fontSize: 12.5,
                                    ),
                                  ),
                                ),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: _buildMixedScriptText(
                                    heading,
                                    style: const TextStyle(
                                      fontSize: 15.5,
                                      fontWeight: FontWeight.w800,
                                      color: Colors.black87,
                                      height: 1.4,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                            const SizedBox(height: 14),
                            _buildReferenceField(
                              label: _referenceFieldLabel(
                                'العنوان أو المادة',
                                'Article or title',
                              ),
                              value: source.secondaryDisplayArticle.isNotEmpty
                                  ? source.secondaryDisplayArticle
                                  : heading,
                              valueWeight: FontWeight.w800,
                            ),
                            _buildReferenceField(
                              label: _referenceFieldLabel(
                                'المستند المعتمد',
                                'Official document',
                              ),
                              value: source.documentTitle.isNotEmpty
                                  ? source.documentTitle
                                  : heading,
                            ),
                            _buildReferenceField(
                              label: _referenceFieldLabel('القسم', 'Section'),
                              value: source.secondaryDisplaySection,
                            ),
                            const SizedBox(height: 12),
                            Container(
                              width: double.infinity,
                              padding: const EdgeInsets.all(14),
                              decoration: BoxDecoration(
                                color: const Color(0xFFF7F8FC),
                                borderRadius: BorderRadius.circular(14),
                                border: Border.all(color: Colors.grey.shade300),
                              ),
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    _referenceFieldLabel(
                                      'النص المستند إليه',
                                      'Supporting excerpt',
                                    ),
                                    style: TextStyle(
                                      color: Colors.grey.shade700,
                                      fontSize: 12.5,
                                      fontWeight: FontWeight.w700,
                                    ),
                                  ),
                                  const SizedBox(height: 8),
                                  _buildMixedScriptText(
                                    snippet,
                                    style: const TextStyle(
                                      height: 1.6,
                                      fontSize: 14,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  }),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (!mounted || !_scrollController.hasClients) {
        return;
      }

      if (_scrollController.position.hasPixels) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      body: Column(
        children: [
          _buildHeader(),
          Expanded(
            child: _isLoadingHistory
                ? const Center(child: CircularProgressIndicator())
                : _messages.isEmpty
                ? _buildEmptyState()
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.fromLTRB(16, 18, 16, 18),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      return _buildMessageBubble(_messages[index]);
                    },
                  ),
          ),
          if (_showSuggestedQuestions &&
              _personalizedSuggestedQuestions.isNotEmpty)
            _buildStudentAwareSuggestions(),
          if (_showSuggestedQuestions) _buildSuggestedQuestions(),
          if (_isTyping) _buildTypingIndicator(),
          _buildInputArea(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 50, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_primaryCyan, _secondaryBlue, _accentPurple],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(30),
          bottomRight: Radius.circular(30),
        ),
        boxShadow: [
          BoxShadow(
            color: _primaryCyan.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.smart_toy_rounded,
              color: Colors.white,
              size: 28,
            ),
          ),
          const SizedBox(width: 15),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'AI Assistant',
                  style: TextStyle(
                    color: Colors.white,
                    fontSize: 22,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 6),
                BackendStatusBanner(
                  isArabic: widget.isArabic,
                  compact: true,
                  forDarkBackground: true,
                ),
              ],
            ),
          ),
          AnimatedBuilder(
            animation: BackendStatusController.instance,
            builder: (context, _) {
              final isBackendOffline =
                  BackendStatusController.instance.snapshot.isOffline;

              return PopupMenuButton<String>(
                icon: const Icon(Icons.more_vert, color: Colors.white),
                onSelected: (value) {
                  if (value == 'search') {
                    _openSearchPage();
                  } else if (value == 'clear') {
                    _clearHistory();
                  }
                },
                itemBuilder: (context) => [
                  PopupMenuItem<String>(
                    value: 'search',
                    enabled: !isBackendOffline,
                    child: Text(
                      widget.isArabic
                          ? 'البحث في المصادر الرسمية'
                          : 'Search official sources',
                    ),
                  ),
                  PopupMenuItem<String>(
                    value: 'clear',
                    child: Text(
                      widget.isArabic ? 'مسح المحادثة' : 'Clear chat history',
                    ),
                  ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestedQuestions() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      child: Wrap(
        spacing: 10,
        runSpacing: 10,
        children: _suggestedQuestions
            .map(
              (question) => _buildSuggestionChip(
                question: question,
                icon: Icons.bolt_outlined,
              ),
            )
            .toList(growable: false),
      ),
    );
  }

  Widget _buildStudentAwareSuggestions() {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: Colors.grey.shade200),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: _primaryCyan.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(
                  Icons.auto_awesome_outlined,
                  color: _primaryCyan,
                  size: 20,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.isArabic ? 'مقترح لك' : 'Suggested for You',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      _studentAwareHintText(),
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[600],
                        height: 1.4,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: _personalizedSuggestedQuestions
                .map(
                  (question) => _buildSuggestionChip(
                    question: question,
                    icon: Icons.auto_awesome,
                  ),
                )
                .toList(growable: false),
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestionChip({
    required String question,
    required IconData icon,
  }) {
    return AnimatedBuilder(
      animation: BackendStatusController.instance,
      builder: (context, _) {
        final isBackendOffline =
            BackendStatusController.instance.snapshot.isOffline;

        return ActionChip(
          avatar: Icon(icon, size: 16, color: _primaryCyan),
          side: BorderSide(color: _primaryCyan.withValues(alpha: 0.18)),
          backgroundColor: _primaryCyan.withValues(alpha: 0.06),
          labelStyle: TextStyle(
            color: Colors.black87,
            fontSize: 12.8,
            fontWeight: FontWeight.w600,
            height: widget.isArabic ? 1.45 : 1.3,
          ),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
          materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          onPressed: isBackendOffline
              ? null
              : () => _sendMessage(presetText: question),
          label: Text(question),
        );
      },
    );
  }

  Widget _buildEmptyState() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.chat_bubble_outline,
            size: 80,
            color: _primaryCyan.withValues(alpha: 0.3),
          ),
          const SizedBox(height: 20),
          Text(
            widget.isArabic ? 'ابدأ المحادثة مع AI' : 'Start chatting with AI',
            style: TextStyle(
              fontSize: 20,
              color: Colors.grey[600],
              fontWeight: FontWeight.w500,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            widget.isArabic
                ? 'اسألني أي شيء عن دراستك! 📚'
                : 'Ask me anything about your studies! 📚',
            style: TextStyle(fontSize: 16, color: Colors.grey[400]),
          ),
        ],
      ),
    );
  }

  Widget _buildMessageBubble(ChatMessage message) {
    final isUser = message.isUser;
    final inlineReferenceText = _inlineReferenceText(message);
    final referenceSummary = _buildReferenceSummaryBlock(
      message,
      inlineReferenceText,
    );
    final visibleText =
        message.isShowingTranslation && message.translatedText != null
        ? message.translatedText!
        : _messageBodyText(message);
    final hasFooterActions =
        !isUser &&
        (message.sources.isNotEmpty ||
            message.canTranslate ||
            message.canFeedback);

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.78,
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (!isUser) ...[
              CircleAvatar(
                radius: 16,
                backgroundColor: _primaryCyan,
                child: const Icon(
                  Icons.smart_toy,
                  size: 18,
                  color: Colors.white,
                ),
              ),
              const SizedBox(width: 8),
            ],
            Flexible(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onLongPressStart: (details) =>
                    _showMessageCopyMenu(details, visibleText),
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 14,
                  ),
                  decoration: BoxDecoration(
                    gradient: isUser
                        ? LinearGradient(
                            colors: [_primaryCyan, _accentPurple],
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                          )
                        : null,
                    color: isUser ? null : Colors.white,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(22),
                      topRight: const Radius.circular(22),
                      bottomLeft: Radius.circular(isUser ? 22 : 6),
                      bottomRight: Radius.circular(isUser ? 6 : 22),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: (isUser ? _primaryCyan : Colors.grey).withValues(
                          alpha: isUser ? 0.22 : 0.16,
                        ),
                        blurRadius: 12,
                        offset: const Offset(0, 5),
                      ),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      _buildMessageTextContent(visibleText, isUser: isUser),
                      if (referenceSummary != null) ...[
                        const SizedBox(height: 10),
                        referenceSummary,
                      ],
                      if (!isUser) ...[
                        const SizedBox(height: 6),
                        Align(
                          alignment: AlignmentDirectional.centerEnd,
                          child: Material(
                            color: Colors.transparent,
                            child: InkWell(
                              borderRadius: BorderRadius.circular(14),
                              onTap: () => _copyMessageText(visibleText),
                              child: Padding(
                                padding: const EdgeInsets.all(4),
                                child: Icon(
                                  Icons.content_copy_rounded,
                                  size: 16,
                                  color: Colors.grey.shade600,
                                ),
                              ),
                            ),
                          ),
                        ),
                      ],
                      if (hasFooterActions) ...[
                        const SizedBox(height: 8),
                        AnimatedBuilder(
                          animation: BackendStatusController.instance,
                          builder: (context, _) {
                            final isBackendOffline = BackendStatusController
                                .instance
                                .snapshot
                                .isOffline;

                            return Wrap(
                              spacing: 6,
                              runSpacing: 6,
                              children: [
                                if (message.canTranslate)
                                  _buildMessageActionButton(
                                    label: _translateButtonLabel(message),
                                    icon: Icons.translate_outlined,
                                    onPressed:
                                        message.isTranslating ||
                                            (isBackendOffline &&
                                                message.translatedText == null)
                                        ? null
                                        : () => _toggleMessageTranslation(
                                            message,
                                          ),
                                  ),
                                if (message.canFeedback)
                                  _buildMessageActionButton(
                                    label: widget.isArabic ? 'مفيد' : 'Helpful',
                                    icon: Icons.thumb_up_alt_outlined,
                                    foregroundColor: message.helpful == true
                                        ? Colors.green.shade700
                                        : null,
                                    onPressed: isBackendOffline
                                        ? null
                                        : () => _submitFeedback(message, true),
                                  ),
                                if (message.canFeedback)
                                  _buildMessageActionButton(
                                    label: widget.isArabic
                                        ? 'غير مفيد'
                                        : 'Not helpful',
                                    icon: Icons.thumb_down_alt_outlined,
                                    foregroundColor: message.helpful == false
                                        ? Colors.red.shade700
                                        : null,
                                    onPressed: isBackendOffline
                                        ? null
                                        : () => _submitFeedback(message, false),
                                  ),
                                if (message.sources.isNotEmpty)
                                  _buildMessageActionButton(
                                    label: widget.isArabic
                                        ? 'عرض المرجع الكامل'
                                        : 'View full source',
                                    icon: Icons.menu_book_outlined,
                                    onPressed: () =>
                                        _showReferenceView(message),
                                  ),
                              ],
                            );
                          },
                        ),
                      ],
                    ],
                  ),
                ),
              ),
            ),
            if (isUser) ...[
              const SizedBox(width: 8),
              CircleAvatar(
                radius: 16,
                backgroundColor: Colors.grey[300],
                child: const Icon(Icons.person, size: 18, color: Colors.white),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _copyMessageText(String messageText) async {
    final text = messageText.trim();
    if (text.isEmpty) {
      return;
    }

    await Clipboard.setData(ClipboardData(text: text));
    if (!mounted) {
      return;
    }

    final messenger = ScaffoldMessenger.of(context);
    messenger
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('تم النسخ'),
          behavior: SnackBarBehavior.floating,
        ),
      );
  }

  Future<void> _showMessageCopyMenu(
    LongPressStartDetails details,
    String messageText,
  ) async {
    final selected = await showMenu<String>(
      context: context,
      position: RelativeRect.fromLTRB(
        details.globalPosition.dx,
        details.globalPosition.dy,
        details.globalPosition.dx,
        details.globalPosition.dy,
      ),
      items: [
        PopupMenuItem<String>(
          value: 'copy',
          child: Text(widget.isArabic ? 'نسخ' : 'Copy'),
        ),
      ],
    );

    if (selected == 'copy') {
      await _copyMessageText(messageText);
    }
  }

  Widget _buildTypingIndicator() {
    return Container(
      margin: const EdgeInsets.only(left: 20, bottom: 10),
      child: Row(
        children: [
          CircleAvatar(
            radius: 16,
            backgroundColor: _primaryCyan,
            child: const Icon(Icons.smart_toy, size: 18, color: Colors.white),
          ),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(20),
              boxShadow: [
                BoxShadow(
                  color: Colors.grey.withValues(alpha: 0.2),
                  blurRadius: 8,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [_AnimatedTypingDots(color: _primaryCyan)],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputArea() {
    return AnimatedBuilder(
      animation: BackendStatusController.instance,
      builder: (context, _) {
        final isBackendOffline =
            BackendStatusController.instance.snapshot.isOffline;
        final canSend = !_isTyping && !isBackendOffline;

        return Container(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 16),
          decoration: BoxDecoration(
            color: Colors.white,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.05),
                blurRadius: 20,
                offset: const Offset(0, -5),
              ),
            ],
          ),
          child: SafeArea(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Row(
                  children: [
                    IconButton(
                      icon: Icon(Icons.attach_file, color: _primaryCyan),
                      onPressed: () {},
                    ),
                    Expanded(
                      child: Container(
                        decoration: BoxDecoration(
                          color: const Color(0xFFF7F8FC),
                          borderRadius: BorderRadius.circular(25),
                          border: Border.all(color: Colors.grey.shade300),
                        ),
                        child: TextField(
                          controller: _messageController,
                          textAlign: widget.isArabic
                              ? TextAlign.right
                              : TextAlign.left,
                          decoration: InputDecoration(
                            hintText: widget.isArabic
                                ? 'اكتب رسالتك هنا...'
                                : 'Type your message...',
                            hintStyle: TextStyle(color: Colors.grey[400]),
                            border: InputBorder.none,
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 20,
                              vertical: 15,
                            ),
                          ),
                          onSubmitted: canSend ? (_) => _sendMessage() : null,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    GestureDetector(
                      onTap: canSend ? _sendMessage : null,
                      child: Opacity(
                        opacity: canSend ? 1.0 : 0.45,
                        child: Container(
                          padding: const EdgeInsets.all(12),
                          decoration: BoxDecoration(
                            gradient: LinearGradient(
                              colors: isBackendOffline
                                  ? const [Color(0xFFCBD5E1), Color(0xFF94A3B8)]
                                  : [_primaryCyan, _accentPurple],
                            ),
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color:
                                    (isBackendOffline
                                            ? Colors.grey
                                            : _primaryCyan)
                                        .withValues(alpha: 0.32),
                                blurRadius: 10,
                                offset: const Offset(0, 4),
                              ),
                            ],
                          ),
                          child: const Icon(
                            Icons.send,
                            color: Colors.white,
                            size: 20,
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                if (isBackendOffline) ...[
                  const SizedBox(height: 10),
                  Text(
                    _backendUnavailableMessage,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      color: Color(0xFF7F1D1D),
                      fontSize: 12.5,
                      fontWeight: FontWeight.w600,
                      height: 1.4,
                    ),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}

class _AnimatedTypingDots extends StatefulWidget {
  final Color color;

  const _AnimatedTypingDots({required this.color});

  @override
  State<_AnimatedTypingDots> createState() => _AnimatedTypingDotsState();
}

class _AnimatedTypingDotsState extends State<_AnimatedTypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  double _waveValue(int index) {
    var progress = _controller.value - (index * 0.18);
    while (progress < 0) {
      progress += 1;
    }
    progress = progress % 1;

    if (progress <= 0.5) {
      return Curves.easeOut.transform(progress / 0.5);
    }
    return Curves.easeIn.transform((1 - progress) / 0.5);
  }

  Widget _buildDot(int index) {
    final wave = _waveValue(index);
    return Transform.translate(
      offset: Offset(0, -4 * wave),
      child: Opacity(
        opacity: 0.4 + (wave * 0.6),
        child: Transform.scale(
          scale: 0.8 + (wave * 0.35),
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 2),
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: widget.color,
              borderRadius: BorderRadius.circular(4),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) => Row(
        mainAxisSize: MainAxisSize.min,
        children: List.generate(3, _buildDot),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
