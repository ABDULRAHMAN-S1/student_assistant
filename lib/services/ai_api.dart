import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class AiApi {
  static String _baseUrl() {
    // ✅ Flutter Web على نفس الجهاز: localhost أفضل من 127
    if (kIsWeb) return 'http://localhost:8000';

    // Android Emulator
    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }

    // Windows / macOS / Linux / iOS (لو شغلتهم محليًا)
    return 'http://127.0.0.1:8000';
  }

  static Future<String> ask(String question) async {
    final url = Uri.parse('${_baseUrl()}/chat');

    final res = await http
        .post(
          url,
          headers: const {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: jsonEncode({'question': question}),
        )
        .timeout(const Duration(seconds: 25));

    if (res.statusCode != 200) {
      throw Exception('Server ${res.statusCode}: ${res.body}');
    }

    final data = jsonDecode(res.body);

    // ✅ دعم لو السيرفر رجّع error
    if (data is Map && data['error'] != null) {
      // نخلي التطبيق يعرض الرد + يعرف أن فيه تحذير
      final reply = (data['reply'] ?? '').toString();
      final err = data['error'].toString();
      return reply.isEmpty ? 'خطأ: $err' : '$reply\n\n(تنبيه: $err)';
    }

    return (data['reply'] ?? '').toString();
  }
}
