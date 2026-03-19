import '../features/ai_assistant/data/services/message_translation_service.dart';

class AiMessageTranslationResult {
  const AiMessageTranslationResult({
    required this.translatedText,
    required this.targetLanguageCode,
  });

  final String translatedText;
  final String targetLanguageCode;

  factory AiMessageTranslationResult.fromResult(
    MessageTranslationResult result,
  ) {
    return AiMessageTranslationResult(
      translatedText: result.translatedText,
      targetLanguageCode: result.targetLanguageCode,
    );
  }
}

class AiMessageTranslation {
  static const MessageTranslationService _service = MessageTranslationService();

  static bool containsArabic(String text) => _service.containsArabic(text);

  static Future<AiMessageTranslationResult> translate(String text) async {
    final result = await _service.translate(text);
    return AiMessageTranslationResult.fromResult(result);
  }
}
