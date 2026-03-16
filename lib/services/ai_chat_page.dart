import 'package:flutter/material.dart';

import 'ai_api.dart';
import 'ai_chat_storage.dart';
import 'ai_message_translation.dart';
import 'regulation_search_page.dart';

class AIChatPage extends StatefulWidget {
  final bool isArabic;

  const AIChatPage({super.key, required this.isArabic});

  @override
  State<AIChatPage> createState() => _AIChatPageState();
}

class _AIChatPageState extends State<AIChatPage> {
  final TextEditingController _messageController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<ChatMessage> _messages = [];
  bool _isTyping = false;
  bool _isLoadingHistory = true;

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

  static const String _arabicReferenceLabel = 'المرجع:';
  static const String _englishReferenceLabel = 'Source:';

  @override
  void initState() {
    super.initState();
    _initializeChat();
  }

  Future<void> _initializeChat() async {
    final storedHistory = await AiChatStorage.loadHistory(
      isArabic: widget.isArabic,
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

  Future<void> _persistHistory() async {
    await AiChatStorage.saveHistory(
      isArabic: widget.isArabic,
      messages: _messages.map((message) => message.toMap()).toList(),
    );
  }

  bool get _showSuggestedQuestions =>
      !_isLoadingHistory &&
      !_isTyping &&
      _messages.where((message) => message.isUser).isEmpty;

  void _addBotMessage(
    String text, {
    List<AiSourceReference> sources = const [],
    bool canFeedback = false,
    bool canTranslate = false,
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
        ),
      );
    });
    _persistHistory();
    _scrollToBottom();
  }

  Future<void> _sendMessage({String? presetText}) async {
    if (_isTyping) return;

    final text = (presetText ?? _messageController.text).trim();
    if (text.isEmpty) return;

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
      final response = await AiApi.ask(text);
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
      );
    } catch (e) {
      if (!mounted) return;

      setState(() => _isTyping = false);
      _addBotMessage(
        widget.isArabic
            ? "صار خطأ في الاتصال: ${e.toString()}"
            : "Connection error: ${e.toString()}",
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

    await AiChatStorage.clearHistory(isArabic: widget.isArabic);
    setState(() {
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
        builder: (_) => RegulationSearchPage(isArabic: widget.isArabic),
      ),
    );
  }

  String _messageBodyText(ChatMessage message) {
    final text = message.text.trim();
    final arabicIndex = text.indexOf(_arabicReferenceLabel);
    final englishIndex = text.indexOf(_englishReferenceLabel);

    int splitIndex = -1;
    if (arabicIndex >= 0 && englishIndex >= 0) {
      splitIndex = arabicIndex < englishIndex ? arabicIndex : englishIndex;
    } else if (arabicIndex >= 0) {
      splitIndex = arabicIndex;
    } else if (englishIndex >= 0) {
      splitIndex = englishIndex;
    }

    if (splitIndex < 0) {
      return text;
    }
    return text.substring(0, splitIndex).trim();
  }

  String? _inlineReferenceText(ChatMessage message) {
    final text = message.text.trim();
    final arabicIndex = text.indexOf(_arabicReferenceLabel);
    final englishIndex = text.indexOf(_englishReferenceLabel);

    int splitIndex = -1;
    if (arabicIndex >= 0 && englishIndex >= 0) {
      splitIndex = arabicIndex < englishIndex ? arabicIndex : englishIndex;
    } else if (arabicIndex >= 0) {
      splitIndex = arabicIndex;
    } else if (englishIndex >= 0) {
      splitIndex = englishIndex;
    }

    if (splitIndex < 0) {
      return null;
    }

    final referenceText = text.substring(splitIndex).trim();
    return referenceText.isEmpty ? null : referenceText;
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

  Future<void> _submitFeedback(ChatMessage message, bool helpful) async {
    if (!message.canFeedback) return;

    final messageIndex = _messages.indexOf(message);
    if (messageIndex < 0) return;

    setState(() {
      _messages[messageIndex] = message.copyWith(helpful: helpful);
    });
    await _persistHistory();

    try {
      await AiApi.sendFeedback(
        question: _questionForMessage(message),
        answer: message.text,
        helpful: helpful,
        language: widget.isArabic ? 'ar' : 'en',
        sources: message.sources,
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.isArabic
                ? 'تعذر إرسال التقييم الآن.'
                : 'Could not send feedback right now.',
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

    final messageIndex = _messages.indexOf(message);
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

    setState(() {
      _messages[messageIndex] = message.copyWith(isTranslating: true);
    });

    try {
      final result = await AiMessageTranslation.translate(_messageBodyText(message));
      if (!mounted) return;

      setState(() {
        _messages[messageIndex] = message.copyWith(
          translatedText: result.translatedText,
          isShowingTranslation: true,
          isTranslating: false,
        );
      });
      await _persistHistory();
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _messages[messageIndex] = message.copyWith(isTranslating: false);
      });
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            widget.isArabic
                ? 'تعذر ترجمة هذه الرسالة الآن.'
                : 'Could not translate this message right now.',
          ),
        ),
      );
    }
  }

  void _showReferenceView(ChatMessage message) {
    if (message.sources.isEmpty) return;

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: ListView.separated(
            shrinkWrap: true,
            itemCount: message.sources.length,
            separatorBuilder: (_, _) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final source = message.sources[index];
              return Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: Colors.grey[50],
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.grey[300]!),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (source.article.isNotEmpty)
                      Text(
                        source.article,
                        style: const TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                        ),
                      ),
                    if (source.section.isNotEmpty) ...[
                      const SizedBox(height: 6),
                      Text(
                        source.section,
                        style: TextStyle(color: Colors.grey[700]),
                      ),
                    ],
                    if (source.documentTitle.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        source.documentTitle,
                        style: TextStyle(color: Colors.grey[600]),
                      ),
                    ],
                    const SizedBox(height: 10),
                    Text(
                      source.content.isNotEmpty
                          ? source.content
                          : source.contentPreview,
                      style: const TextStyle(height: 1.5),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  void _scrollToBottom() {
    Future.delayed(const Duration(milliseconds: 100), () {
      if (_scrollController.hasClients) {
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
                    padding: const EdgeInsets.all(16),
                    itemCount: _messages.length,
                    itemBuilder: (context, index) {
                      return _buildMessageBubble(_messages[index]);
                    },
                  ),
          ),
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
                Text(
                  widget.isArabic
                      ? 'متصل • جاهز للمساعدة'
                      : 'Online • Ready to help',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.8),
                    fontSize: 14,
                  ),
                ),
              ],
            ),
          ),
          PopupMenuButton<String>(
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
                child: Text(
                  widget.isArabic ? 'البحث في اللوائح' : 'Search regulations',
                ),
              ),
              PopupMenuItem<String>(
                value: 'clear',
                child: Text(
                  widget.isArabic ? 'مسح المحادثة' : 'Clear chat history',
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSuggestedQuestions() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
      child: Wrap(
        spacing: 8,
        runSpacing: 8,
        children: _suggestedQuestions
            .map(
              (question) => ActionChip(
                label: Text(question),
                onPressed: () => _sendMessage(presetText: question),
              ),
            )
            .toList(growable: false),
      ),
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
    final sourceText = _buildSourceText(message);
    final inlineReferenceText = _inlineReferenceText(message);
    final visibleText =
        message.isShowingTranslation && message.translatedText != null
        ? message.translatedText!
        : _messageBodyText(message);

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        constraints: BoxConstraints(
          maxWidth: MediaQuery.of(context).size.width * 0.75,
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
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 12,
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
                    topLeft: const Radius.circular(20),
                    topRight: const Radius.circular(20),
                    bottomLeft: Radius.circular(isUser ? 20 : 4),
                    bottomRight: Radius.circular(isUser ? 4 : 20),
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: (isUser ? _primaryCyan : Colors.grey).withValues(
                        alpha: 0.2,
                      ),
                      blurRadius: 8,
                      offset: const Offset(0, 3),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      visibleText,
                      style: TextStyle(
                        color: isUser ? Colors.white : Colors.black87,
                        fontSize: 15,
                        height: 1.4,
                      ),
                    ),
                    if (sourceText != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        sourceText,
                        style: TextStyle(
                          color: isUser ? Colors.white70 : Colors.black54,
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ],
                    if (sourceText == null && inlineReferenceText != null) ...[
                      const SizedBox(height: 8),
                      Text(
                        inlineReferenceText,
                        style: TextStyle(
                          color: isUser ? Colors.white70 : Colors.black54,
                          fontSize: 12,
                          height: 1.4,
                        ),
                      ),
                    ],
                    if (!isUser &&
                        (message.sources.isNotEmpty ||
                            message.canFeedback ||
                            message.canTranslate)) ...[
                      const SizedBox(height: 8),
                      Wrap(
                        spacing: 4,
                        runSpacing: 4,
                        children: [
                          if (message.canTranslate)
                            TextButton(
                              onPressed: message.isTranslating
                                  ? null
                                  : () => _toggleMessageTranslation(message),
                              child: Text(_translateButtonLabel(message)),
                            ),
                          if (message.sources.isNotEmpty)
                            TextButton(
                              onPressed: () => _showReferenceView(message),
                              child: Text(
                                widget.isArabic
                                    ? 'عرض المرجع الكامل'
                                    : 'View full reference',
                              ),
                            ),
                          if (message.canFeedback)
                            IconButton(
                              icon: Icon(
                                Icons.thumb_up_alt_outlined,
                                color: message.helpful == true
                                    ? _primaryCyan
                                    : Colors.grey[600],
                              ),
                              onPressed: () => _submitFeedback(message, true),
                              tooltip: widget.isArabic ? 'مفيد' : 'Helpful',
                            ),
                          if (message.canFeedback)
                            IconButton(
                              icon: Icon(
                                Icons.thumb_down_alt_outlined,
                                color: message.helpful == false
                                    ? Colors.redAccent
                                    : Colors.grey[600],
                              ),
                              onPressed: () => _submitFeedback(message, false),
                              tooltip: widget.isArabic
                                  ? 'غير مفيد'
                                  : 'Not helpful',
                            ),
                        ],
                      ),
                    ],
                  ],
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

  String? _buildSourceText(ChatMessage message) {
    if (message.isUser || message.sources.isEmpty) {
      return null;
    }

    final label = widget.isArabic ? 'المرجع: ' : 'Source: ';
    return '$label${message.sources.map((source) => source.toDisplayString()).take(2).join('\n')}';
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
    return Container(
      padding: const EdgeInsets.all(16),
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
        child: Row(
          children: [
            IconButton(
              icon: Icon(Icons.attach_file, color: _primaryCyan),
              onPressed: () {},
            ),
            Expanded(
              child: Container(
                decoration: BoxDecoration(
                  color: Colors.grey[100],
                  borderRadius: BorderRadius.circular(25),
                  border: Border.all(color: Colors.grey[300]!),
                ),
                child: TextField(
                  controller: _messageController,
                  textAlign: widget.isArabic ? TextAlign.right : TextAlign.left,
                  decoration: InputDecoration(
                    hintText: widget.isArabic
                        ? 'اكتب رسالتك هنا...'
                        : 'Type your message...',
                    hintStyle: TextStyle(color: Colors.grey[400]),
                    border: InputBorder.none,
                    contentPadding: const EdgeInsets.symmetric(
                      horizontal: 20,
                      vertical: 14,
                    ),
                  ),
                  onSubmitted: (_) => _sendMessage(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            GestureDetector(
              onTap: _isTyping ? null : _sendMessage,
              child: Opacity(
                opacity: _isTyping ? 0.6 : 1.0,
                child: Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      colors: [_primaryCyan, _accentPurple],
                    ),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: _primaryCyan.withValues(alpha: 0.4),
                        blurRadius: 10,
                        offset: const Offset(0, 4),
                      ),
                    ],
                  ),
                  child: const Icon(Icons.send, color: Colors.white, size: 20),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _messageController.dispose();
    _scrollController.dispose();
    super.dispose();
  }
}

class ChatMessage {
  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<AiSourceReference> sources;
  final bool canFeedback;
  final bool canTranslate;
  final bool? helpful;
  final String? translatedText;
  final bool isShowingTranslation;
  final bool isTranslating;

  ChatMessage({
    required this.text,
    required this.isUser,
    required this.timestamp,
    this.sources = const [],
    this.canFeedback = false,
    this.canTranslate = false,
    this.helpful,
    this.translatedText,
    this.isShowingTranslation = false,
    this.isTranslating = false,
  });

  static const Object _unset = Object();

  ChatMessage copyWith({
    String? text,
    bool? isUser,
    DateTime? timestamp,
    List<AiSourceReference>? sources,
    bool? canFeedback,
    bool? canTranslate,
    Object? helpful = _unset,
    Object? translatedText = _unset,
    bool? isShowingTranslation,
    bool? isTranslating,
  }) {
    return ChatMessage(
      text: text ?? this.text,
      isUser: isUser ?? this.isUser,
      timestamp: timestamp ?? this.timestamp,
      sources: sources ?? this.sources,
      canFeedback: canFeedback ?? this.canFeedback,
      canTranslate: canTranslate ?? this.canTranslate,
      helpful: identical(helpful, _unset) ? this.helpful : helpful as bool?,
      translatedText: identical(translatedText, _unset)
          ? this.translatedText
          : translatedText as String?,
      isShowingTranslation: isShowingTranslation ?? this.isShowingTranslation,
      isTranslating: isTranslating ?? this.isTranslating,
    );
  }

  Map<String, dynamic> toMap() {
    return {
      'text': text,
      'isUser': isUser,
      'timestamp': timestamp.toIso8601String(),
      'sources': sources
          .map((source) => source.toJson())
          .toList(growable: false),
      'canFeedback': canFeedback,
      'canTranslate': canTranslate,
      'helpful': helpful,
      'translatedText': translatedText,
      'isShowingTranslation': isShowingTranslation,
      'isTranslating': isTranslating,
    };
  }

  factory ChatMessage.fromMap(Map<String, dynamic> map) {
    final rawSources = map['sources'];
    return ChatMessage(
      text: (map['text'] ?? '').toString(),
      isUser: map['isUser'] == true,
      timestamp:
          DateTime.tryParse((map['timestamp'] ?? '').toString()) ??
          DateTime.now(),
      sources: rawSources is List
          ? rawSources
                .whereType<Map>()
                .map(
                  (item) => AiSourceReference.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .toList(growable: false)
          : const [],
      canFeedback: map['canFeedback'] == true,
      canTranslate: map['canTranslate'] == true,
      helpful: map['helpful'] is bool ? map['helpful'] as bool : null,
      translatedText: (map['translatedText'] ?? '').toString().trim().isEmpty
          ? null
          : (map['translatedText'] ?? '').toString(),
      isShowingTranslation: map['isShowingTranslation'] == true,
      isTranslating: false,
    );
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
