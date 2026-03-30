import 'regulation_source.dart';

class ChatMessage {
  const ChatMessage({
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

  final String text;
  final bool isUser;
  final DateTime timestamp;
  final List<RegulationSource> sources;
  final bool canFeedback;
  final bool canTranslate;
  final bool? helpful;
  final String? translatedText;
  final bool isShowingTranslation;
  final bool isTranslating;

  static const Object _unset = Object();

  ChatMessage copyWith({
    String? text,
    bool? isUser,
    DateTime? timestamp,
    List<RegulationSource>? sources,
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
    return ChatMessage(
      text: (map['text'] ?? '').toString(),
      isUser: map['isUser'] == true,
      timestamp:
          DateTime.tryParse((map['timestamp'] ?? '').toString()) ??
          DateTime.now(),
      sources: RegulationSource.listFromJson(map['sources']),
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
