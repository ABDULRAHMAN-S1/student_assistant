import 'package:flutter/material.dart';

class Course {
  const Course({
    required this.titleAr,
    required this.titleEn,
    required this.semesterAr,
    required this.semesterEn,
    required this.icon,
    required this.color,
    required this.progress,
  });

  final String titleAr;
  final String titleEn;
  final String semesterAr;
  final String semesterEn;
  final IconData icon;
  final Color color;
  final double progress;

  Course copyWith({
    String? titleAr,
    String? titleEn,
    String? semesterAr,
    String? semesterEn,
    IconData? icon,
    Color? color,
    double? progress,
  }) {
    return Course(
      titleAr: titleAr ?? this.titleAr,
      titleEn: titleEn ?? this.titleEn,
      semesterAr: semesterAr ?? this.semesterAr,
      semesterEn: semesterEn ?? this.semesterEn,
      icon: icon ?? this.icon,
      color: color ?? this.color,
      progress: progress ?? this.progress,
    );
  }
}
