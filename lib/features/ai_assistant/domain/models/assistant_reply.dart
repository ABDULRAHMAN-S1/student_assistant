import 'regulation_source.dart';

class AssistantReply {
  const AssistantReply({required this.answer, required this.sources});

  final String answer;
  final List<RegulationSource> sources;

  factory AssistantReply.fromJson(Map<String, dynamic> json) {
    return AssistantReply(
      answer: (json['answer'] ?? json['reply'] ?? '').toString().trim(),
      sources: RegulationSource.listFromJson(json['sources']),
    );
  }
}
