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
          body: jsonEncode({'question': message}),
        )
        .timeout(const Duration(seconds: 25));

    final dynamic payload = response.body.isEmpty
        ? null
        : jsonDecode(utf8.decode(response.bodyBytes));

    if (response.statusCode != 200) {
      throw Exception(_extractErrorMessage(payload, response.statusCode));
    }

    if (payload is! Map<String, dynamic>) {
      throw const FormatException('Invalid server response.');
    }

    return AiChatResponse.fromJson(payload);
  }

  static Future<AiSearchResponse> searchRegulations(
    String query, {
    int topK = 6,
  }) async {
    final url = Uri.parse('${_baseUrl()}/search');

    final response = await http
        .post(
          url,
          headers: const {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: jsonEncode({'query': query, 'top_k': topK}),
        )
        .timeout(const Duration(seconds: 25));

    final dynamic payload = response.body.isEmpty
        ? null
        : jsonDecode(utf8.decode(response.bodyBytes));

    if (response.statusCode != 200) {
      throw Exception(_extractErrorMessage(payload, response.statusCode));
    }

    if (payload is! Map<String, dynamic>) {
      throw const FormatException('Invalid server response.');
    }

    return AiSearchResponse.fromJson(payload);
  }

  static Future<void> sendFeedback({
    required String question,
    required String answer,
    required bool helpful,
    required String language,
    required List<AiSourceReference> sources,
  }) async {
    final url = Uri.parse('${_baseUrl()}/feedback');

    final response = await http
        .post(
          url,
          headers: const {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
          },
          body: jsonEncode({
            'question': question,
            'answer': answer,
            'helpful': helpful,
            'language': language,
            'sources': sources
                .map((item) => item.toJson())
                .toList(growable: false),
          }),
        )
        .timeout(const Duration(seconds: 25));

    if (response.statusCode != 200) {
      final dynamic payload = response.body.isEmpty
          ? null
          : jsonDecode(utf8.decode(response.bodyBytes));
      throw Exception(_extractErrorMessage(payload, response.statusCode));
    }
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

class AiSearchResponse {
  const AiSearchResponse({required this.results});

  final List<AiSourceReference> results;

  factory AiSearchResponse.fromJson(Map<String, dynamic> json) {
    final rawResults = json['results'];
    return AiSearchResponse(
      results: rawResults is List
          ? rawResults
                .whereType<Map>()
                .map(
                  (item) => AiSourceReference.fromJson(
                    Map<String, dynamic>.from(item),
                  ),
                )
                .toList(growable: false)
          : const [],
    );
  }
}

class AiSourceReference {
  const AiSourceReference({
    required this.id,
    required this.documentTitle,
    required this.section,
    required this.article,
    required this.title,
    required this.content,
    required this.contentPreview,
    required this.score,
  });

  final String id;
  final String documentTitle;
  final String section;
  final String article;
  final String title;
  final String content;
  final String contentPreview;
  final double? score;

  factory AiSourceReference.fromJson(Map<String, dynamic> json) {
    final rawScore = json['score'];
    return AiSourceReference(
      id: (json['id'] ?? '').toString().trim(),
      documentTitle: (json['document_title'] ?? '').toString().trim(),
      section: (json['section'] ?? '').toString().trim(),
      article: (json['article'] ?? '').toString().trim(),
      title: (json['title'] ?? '').toString().trim(),
      content: (json['content'] ?? '').toString().trim(),
      contentPreview: (json['content_preview'] ?? '').toString().trim(),
      score: rawScore is num ? rawScore.toDouble() : null,
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

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'document_title': documentTitle,
      'section': section,
      'article': article,
      'title': title,
      'content': content,
      'content_preview': contentPreview,
      'score': score,
    };
  }
}
