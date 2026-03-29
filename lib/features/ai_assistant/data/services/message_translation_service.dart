import '../remote/assistant_api_client.dart';

class MessageTranslationResult {
  const MessageTranslationResult({
    required this.translatedText,
    required this.targetLanguageCode,
  });

  final String translatedText;
  final String targetLanguageCode;
}

class MessageTranslationService {
  const MessageTranslationService({AssistantApiClient? apiClient})
    : _apiClient = apiClient ?? const AssistantApiClient();

  static final RegExp _arabicPattern = RegExp(r'[\u0600-\u06FF]');
  final AssistantApiClient _apiClient;

  bool containsArabic(String text) => _arabicPattern.hasMatch(text);

  Future<MessageTranslationResult> translate(String text) async {
    final cleaned = text.trim();
    if (cleaned.isEmpty) {
      return const MessageTranslationResult(
        translatedText: '',
        targetLanguageCode: 'en',
      );
    }

    final payload = await _apiClient.translateMessage(cleaned);
    final translatedText = (payload['translated_text'] ?? '').toString().trim();
    final targetLanguageCode = (payload['target_language_code'] ?? '')
        .toString()
        .trim();

    if (translatedText.isEmpty || targetLanguageCode.isEmpty) {
      throw const FormatException('Invalid translation response');
    }

    return MessageTranslationResult(
      translatedText: translatedText,
      targetLanguageCode: targetLanguageCode,
    );
  }
}
