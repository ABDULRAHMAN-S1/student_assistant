import 'dart:convert';

import 'package:http/http.dart' as http;

class AiMessageTranslationResult {
  const AiMessageTranslationResult({
    required this.translatedText,
    required this.targetLanguageCode,
  });

  final String translatedText;
  final String targetLanguageCode;
}

class AiMessageTranslation {
  static final RegExp _arabicPattern = RegExp(r'[\u0600-\u06FF]');

  static bool containsArabic(String text) => _arabicPattern.hasMatch(text);

  static Future<AiMessageTranslationResult> translate(String text) async {
    final cleaned = text.trim();
    if (cleaned.isEmpty) {
      return const AiMessageTranslationResult(
        translatedText: '',
        targetLanguageCode: 'en',
      );
    }

    final targetLanguageCode = containsArabic(cleaned) ? 'en' : 'ar';
    final uri = Uri.parse(
      'https://translate.googleapis.com/translate_a/single'
      '?client=gtx&sl=auto&tl=$targetLanguageCode&dt=t&q=${Uri.encodeQueryComponent(cleaned)}',
    );

    final response = await http.get(uri).timeout(const Duration(seconds: 20));
    if (response.statusCode != 200) {
      throw Exception('Translation failed: ${response.statusCode}');
    }

    final dynamic payload = jsonDecode(utf8.decode(response.bodyBytes));
    if (payload is! List || payload.isEmpty || payload.first is! List) {
      throw const FormatException('Invalid translation response');
    }

    final translatedText = (payload.first as List)
        .whereType<List>()
        .map((item) => item.isNotEmpty ? item.first?.toString() ?? '' : '')
        .join()
        .trim();

    if (translatedText.isEmpty) {
      throw const FormatException('Empty translation result');
    }

    return AiMessageTranslationResult(
      translatedText: translatedText,
      targetLanguageCode: targetLanguageCode,
    );
  }
}
