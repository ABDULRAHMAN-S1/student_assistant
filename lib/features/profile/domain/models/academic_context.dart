class AcademicContext {
  const AcademicContext({
    required this.specialization,
    this.academicLevel,
    this.interests = const [],
    this.currentSemester,
    this.enrolledCourseIds = const [],
  });

  final String specialization;
  final String? academicLevel;
  final List<String> interests;
  final String? currentSemester;
  final List<String> enrolledCourseIds;

  AcademicContext copyWith({
    String? specialization,
    Object? academicLevel = _unset,
    List<String>? interests,
    Object? currentSemester = _unset,
    List<String>? enrolledCourseIds,
  }) {
    return AcademicContext(
      specialization: specialization ?? this.specialization,
      academicLevel: identical(academicLevel, _unset)
          ? this.academicLevel
          : academicLevel as String?,
      interests: interests ?? this.interests,
      currentSemester: identical(currentSemester, _unset)
          ? this.currentSemester
          : currentSemester as String?,
      enrolledCourseIds: enrolledCourseIds ?? this.enrolledCourseIds,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'specialization': specialization,
      'academicLevel': academicLevel,
      'interests': interests,
      'currentSemester': currentSemester,
      'enrolledCourseIds': enrolledCourseIds,
    };
  }

  factory AcademicContext.fromJson(Map<String, dynamic> json) {
    return AcademicContext(
      specialization: (json['specialization'] ?? '').toString(),
      academicLevel: (json['academicLevel'] ?? '').toString().trim().isEmpty
          ? null
          : json['academicLevel'].toString(),
      interests:
          (json['interests'] as List?)
              ?.map((item) => item.toString())
              .toList(growable: false) ??
          const [],
      currentSemester: (json['currentSemester'] ?? '').toString().trim().isEmpty
          ? null
          : json['currentSemester'].toString(),
      enrolledCourseIds:
          (json['enrolledCourseIds'] as List?)
              ?.map((item) => item.toString())
              .toList(growable: false) ??
          const [],
    );
  }

  static const Object _unset = Object();
}
