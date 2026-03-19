class RecommendationItem {
  const RecommendationItem({
    required this.id,
    required this.type,
    required this.title,
    required this.description,
    required this.reason,
    this.specializationSignals = const [],
    this.interestSignals = const [],
    this.academicLevelSignals = const [],
    this.enrolledCourseSignals = const [],
  });

  static const String courseType = 'course';
  static const String eventType = 'event';

  final String id;
  final String type;
  final String title;
  final String description;
  final String reason;
  final List<String> specializationSignals;
  final List<String> interestSignals;
  final List<String> academicLevelSignals;
  final List<String> enrolledCourseSignals;
}
