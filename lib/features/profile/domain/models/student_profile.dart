import 'academic_context.dart';

class StudentProfile {
  const StudentProfile({
    required this.id,
    required this.fullName,
    required this.email,
    required this.phoneNumber,
    required this.preferredLanguageCode,
    required this.createdAt,
    required this.updatedAt,
    required this.academicContext,
  });

  final String id;
  final String fullName;
  final String email;
  final String phoneNumber;
  final String preferredLanguageCode;
  final DateTime createdAt;
  final DateTime updatedAt;
  final AcademicContext academicContext;

  StudentProfile copyWith({
    String? id,
    String? fullName,
    String? email,
    String? phoneNumber,
    String? preferredLanguageCode,
    DateTime? createdAt,
    DateTime? updatedAt,
    AcademicContext? academicContext,
  }) {
    return StudentProfile(
      id: id ?? this.id,
      fullName: fullName ?? this.fullName,
      email: email ?? this.email,
      phoneNumber: phoneNumber ?? this.phoneNumber,
      preferredLanguageCode:
          preferredLanguageCode ?? this.preferredLanguageCode,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
      academicContext: academicContext ?? this.academicContext,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'fullName': fullName,
      'email': email,
      'phoneNumber': phoneNumber,
      'preferredLanguageCode': preferredLanguageCode,
      'createdAt': createdAt.toIso8601String(),
      'updatedAt': updatedAt.toIso8601String(),
      'academicContext': academicContext.toJson(),
    };
  }

  factory StudentProfile.fromJson(Map<String, dynamic> json) {
    return StudentProfile(
      id: (json['id'] ?? '').toString(),
      fullName: (json['fullName'] ?? '').toString(),
      email: (json['email'] ?? '').toString(),
      phoneNumber: (json['phoneNumber'] ?? '').toString(),
      preferredLanguageCode: (json['preferredLanguageCode'] ?? 'ar').toString(),
      createdAt:
          DateTime.tryParse((json['createdAt'] ?? '').toString()) ??
          DateTime.now(),
      updatedAt:
          DateTime.tryParse((json['updatedAt'] ?? '').toString()) ??
          DateTime.now(),
      academicContext: json['academicContext'] is Map
          ? AcademicContext.fromJson(
              Map<String, dynamic>.from(json['academicContext'] as Map),
            )
          : const AcademicContext(specialization: ''),
    );
  }
}
