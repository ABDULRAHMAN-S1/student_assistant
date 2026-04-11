import 'regulation_source.dart';

class AssistantReply {
  const AssistantReply({
    required this.answer,
    required this.sources,
    this.routeMode = '',
  });

  final String answer;
  final List<RegulationSource> sources;
  final String routeMode;

  factory AssistantReply.fromJson(Map<String, dynamic> json) {
    return AssistantReply(
      answer: (json['answer'] ?? json['reply'] ?? '').toString().trim(),
      sources: RegulationSource.listFromJson(json['sources']),
      routeMode: (json['route_mode'] ?? '').toString(),
    );
  }
}
