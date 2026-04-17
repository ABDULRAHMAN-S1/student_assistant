class EngagementFeedPage {
  const EngagementFeedPage({
    this.hasMore = false,
    this.nextCursor,
  });

  final bool hasMore;
  final String? nextCursor;

  EngagementFeedPage copyWith({
    bool? hasMore,
    String? nextCursor,
  }) {
    return EngagementFeedPage(
      hasMore: hasMore ?? this.hasMore,
      nextCursor: nextCursor ?? this.nextCursor,
    );
  }
}
