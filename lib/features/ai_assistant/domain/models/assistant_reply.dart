import 'assistant_coverage.dart';
import 'regulation_source.dart';

class AssistantReply {
  const AssistantReply({
    required this.answer,
    required this.sources,
    this.routeMode = '',
    this.coverage,
  });

  final String answer;
  final List<RegulationSource> sources;
  final String routeMode;
  final AssistantCoverage? coverage;
  bool get hasCoverageGap => coverage?.hasGap == true;

  factory AssistantReply.fromJson(Map<String, dynamic> json) {
    return AssistantReply(
      answer: (json['answer'] ?? json['reply'] ?? '').toString().trim(),
      sources: RegulationSource.listFromJson(json['sources']),
      routeMode: (json['route_mode'] ?? '').toString(),
      coverage: AssistantCoverage.fromJsonNullable(json['coverage']),
    );
  }
}
