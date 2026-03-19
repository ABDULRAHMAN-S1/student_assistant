import '../features/ai_assistant/data/repositories/assistant_repository.dart';
import '../features/ai_assistant/domain/models/assistant_reply.dart';
import '../features/ai_assistant/domain/models/regulation_source.dart';

class AiApi {
  static const AssistantRepository _repository = AssistantRepository();

  static Future<AiChatResponse> ask(String message) async {
    final reply = await _repository.ask(message);
    return AiChatResponse.fromReply(reply);
  }

  static Future<AiSearchResponse> searchRegulations(
    String query, {
    int topK = 6,
  }) async {
    final results = await _repository.searchRegulations(query, topK: topK);
    return AiSearchResponse(
      results: results
          .map(AiSourceReference.fromSource)
          .toList(growable: false),
    );
  }

  static Future<void> sendFeedback({
    required String question,
    required String answer,
    required bool helpful,
    required String language,
    required List<AiSourceReference> sources,
  }) {
    return _repository.sendFeedback(
      question: question,
      answer: answer,
      helpful: helpful,
      language: language,
      sources: sources
          .map((source) => source.toSource())
          .toList(growable: false),
    );
  }
}

class AiChatResponse {
  const AiChatResponse({required this.answer, required this.sources});

  final String answer;
  final List<AiSourceReference> sources;

  factory AiChatResponse.fromJson(Map<String, dynamic> json) {
    return AiChatResponse.fromReply(AssistantReply.fromJson(json));
  }

  factory AiChatResponse.fromReply(AssistantReply reply) {
    return AiChatResponse(
      answer: reply.answer,
      sources: reply.sources
          .map(AiSourceReference.fromSource)
          .toList(growable: false),
    );
  }
}

class AiSearchResponse {
  const AiSearchResponse({required this.results});

  final List<AiSourceReference> results;

  factory AiSearchResponse.fromJson(Map<String, dynamic> json) {
    return AiSearchResponse(
      results: RegulationSource.listFromJson(
        json['results'],
      ).map(AiSourceReference.fromSource).toList(growable: false),
    );
  }
}

class AiSourceReference {
  const AiSourceReference({
    required this.id,
    required this.docType,
    required this.documentTitle,
    required this.section,
    required this.article,
    required this.title,
    required this.content,
    required this.contentPreview,
    required this.score,
  });

  final String id;
  final String docType;
  final String documentTitle;
  final String section;
  final String article;
  final String title;
  final String content;
  final String contentPreview;
  final double? score;

  factory AiSourceReference.fromJson(Map<String, dynamic> json) {
    return AiSourceReference.fromSource(RegulationSource.fromJson(json));
  }

  factory AiSourceReference.fromSource(RegulationSource source) {
    return AiSourceReference(
      id: source.id,
      docType: source.docType,
      documentTitle: source.documentTitle,
      section: source.section,
      article: source.article,
      title: source.title,
      content: source.content,
      contentPreview: source.contentPreview,
      score: source.score,
    );
  }

  bool get hasReference =>
      documentTitle.isNotEmpty || section.isNotEmpty || article.isNotEmpty;

  String toDisplayString({bool isArabic = true}) {
    return toSource().toDisplayString(isArabic: isArabic);
  }

  Map<String, dynamic> toJson() {
    return toSource().toJson();
  }

  RegulationSource toSource() {
    return RegulationSource(
      id: id,
      docType: docType,
      documentTitle: documentTitle,
      section: section,
      article: article,
      title: title,
      content: content,
      contentPreview: contentPreview,
      score: score,
    );
  }
}
