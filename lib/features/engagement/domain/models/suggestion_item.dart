class SuggestionItem {
  const SuggestionItem({
    required this.id,
    required this.contentType,
    required this.title,
    required this.body,
    required this.createdAt,
    this.startsAt,
    this.endsAt,
    this.linkUrl,
    this.tags = const [],
    this.matchReasons = const [],
  });

  final String id;
  final String contentType;
  final String title;
  final String body;
  final DateTime? createdAt;
  final DateTime? startsAt;
  final DateTime? endsAt;
  final String? linkUrl;
  final List<String> tags;
  final List<String> matchReasons;
}
