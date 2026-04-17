class AssistantCoverage {
  const AssistantCoverage({
    required this.category,
    required this.matchedContexts,
    required this.strongContexts,
    required this.hasGap,
  });

  final String category;
  final int matchedContexts;
  final int strongContexts;
  final bool hasGap;

  factory AssistantCoverage.fromJson(Map<String, dynamic> json) {
    final rawMatched = json['matched_contexts'];
    final rawStrong = json['strong_contexts'];
    return AssistantCoverage(
      category: (json['category'] ?? '').toString().trim(),
      matchedContexts: rawMatched is num ? rawMatched.toInt() : 0,
      strongContexts: rawStrong is num ? rawStrong.toInt() : 0,
      hasGap: json['has_gap'] == true,
    );
  }

  static AssistantCoverage? fromJsonNullable(dynamic raw) {
    if (raw is! Map) {
      return null;
    }
    return AssistantCoverage.fromJson(Map<String, dynamic>.from(raw));
  }

  Map<String, dynamic> toJson() {
    return {
      'category': category,
      'matched_contexts': matchedContexts,
      'strong_contexts': strongContexts,
      'has_gap': hasGap,
    };
  }
}
