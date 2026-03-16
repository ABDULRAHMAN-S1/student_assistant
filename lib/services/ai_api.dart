import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

class AiApi {
  static const String _configuredBaseUrl = String.fromEnvironment(
    'AI_CHAT_API_BASE_URL',
  );

  static String _baseUrl() {
    final configured = _configuredBaseUrl.trim();
    if (configured.isNotEmpty) {
      return configured.replaceFirst(RegExp(r'/$'), '');
    }

    if (kIsWeb) {
      return 'http://localhost:8000';
    }

    if (defaultTargetPlatform == TargetPlatform.android) {
      return 'http://10.0.2.2:8000';
    }

    return 'http://127.0.0.1:8000';
  }

  static Future<AiChatResponse> ask(String message) async {
    final url = Uri.parse('${_baseUrl()}/chat');

    final response = await http
        .post(
          url,
          headers: const {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: jsonEncode({'message': message, 'question': message}),
        )
        .timeout(const Duration(seconds: 25));

    final dynamic payload = response.body.isEmpty
        ? null
        : jsonDecode(response.body);

    if (response.statusCode != 200) {
      throw Exception(_extractErrorMessage(payload, response.statusCode));
    }

    if (payload is! Map<String, dynamic>) {
      throw const FormatException('Invalid server response.');
    }

    return AiChatResponse.fromJson(payload);
  }

  static String _extractErrorMessage(dynamic payload, int statusCode) {
    if (payload is Map<String, dynamic>) {
      final detail = payload['detail'];
      if (detail != null && detail.toString().trim().isNotEmpty) {
        return detail.toString();
      }

      final error = payload['error'];
      if (error != null && error.toString().trim().isNotEmpty) {
        return error.toString();
      }
    }

    return 'Server $statusCode';
  }
}

class AiChatResponse {
  const AiChatResponse({required this.answer, required this.sources});

  final String answer;
  final List<AiSourceReference> sources;

  factory AiChatResponse.fromJson(Map<String, dynamic> json) {
    final rawSources = json['sources'];

    return AiChatResponse(
      answer: (json['answer'] ?? json['reply'] ?? '').toString().trim(),
      sources: rawSources is List
          ? rawSources
                .whereType<Map>()
                .map(
                  (item) => AiSourceReference.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .where((item) => item.hasReference)
                .toList(growable: false)
          : const [],
    );
  }
}

class AiSourceReference {
  const AiSourceReference({
    required this.documentTitle,
    required this.section,
    required this.article,
  });

  final String documentTitle;
  final String section;
  final String article;

  factory AiSourceReference.fromJson(Map<String, dynamic> json) {
    return AiSourceReference(
      documentTitle: (json['document_title'] ?? '').toString().trim(),
      section: (json['section'] ?? '').toString().trim(),
      article: (json['article'] ?? '').toString().trim(),
    );
  }

  bool get hasReference =>
      documentTitle.isNotEmpty || section.isNotEmpty || article.isNotEmpty;

  String toDisplayString() {
    final parts = <String>[
      if (article.isNotEmpty) article,
      if (section.isNotEmpty) section,
      if (documentTitle.isNotEmpty) documentTitle,
    ];

    return parts.join(' | ');
  }
}
