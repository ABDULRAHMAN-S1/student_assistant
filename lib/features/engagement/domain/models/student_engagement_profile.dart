class StudentEngagementProfile {
  const StudentEngagementProfile({
    required this.major,
    required this.academicLevel,
    required this.track,
    required this.interests,
    this.updatedAt,
  });

  final String major;
  final String academicLevel;
  final String track;
  final List<String> interests;
  final DateTime? updatedAt;

  StudentEngagementProfile copyWith({
    String? major,
    String? academicLevel,
    String? track,
    List<String>? interests,
    DateTime? updatedAt,
  }) {
    return StudentEngagementProfile(
      major: major ?? this.major,
      academicLevel: academicLevel ?? this.academicLevel,
      track: track ?? this.track,
      interests: interests ?? this.interests,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  static const empty = StudentEngagementProfile(
    major: '',
    academicLevel: '',
    track: '',
    interests: <String>[],
  );
}
