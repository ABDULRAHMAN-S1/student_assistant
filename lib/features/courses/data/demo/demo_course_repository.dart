import 'package:flutter/material.dart';

import '../../domain/models/course.dart';
import '../repositories/course_repository.dart';

class DemoCourseRepository implements CourseRepository {
  DemoCourseRepository();

  final List<Course> _courses = [
    const Course(
      titleAr: 'الرياضيات المتقدمة',
      titleEn: 'Advanced Mathematics',
      semesterAr: 'الفصل الدراسي الأول',
      semesterEn: 'Fall Semester',
      icon: Icons.calculate,
      color: Colors.blue,
      progress: 0.75,
    ),
    const Course(
      titleAr: 'الفيزياء',
      titleEn: 'Physics',
      semesterAr: 'الفصل الدراسي الأول',
      semesterEn: 'Fall Semester',
      icon: Icons.science,
      color: Colors.orange,
      progress: 0.60,
    ),
    const Course(
      titleAr: 'البرمجة',
      titleEn: 'Programming',
      semesterAr: 'الفصل الدراسي الأول',
      semesterEn: 'Fall Semester',
      icon: Icons.code,
      color: Colors.green,
      progress: 0.90,
    ),
    const Course(
      titleAr: 'اللغة الإنجليزية',
      titleEn: 'English Language',
      semesterAr: 'الفصل الدراسي الأول',
      semesterEn: 'Fall Semester',
      icon: Icons.language,
      color: Colors.purple,
      progress: 0.45,
    ),
  ];

  @override
  List<Course> getCourses() => List.unmodifiable(_courses);

  @override
  List<Course> addCourse(Course course) {
    _courses.insert(0, course);
    return getCourses();
  }

  @override
  List<Course> markCourseCompleted(Course course) {
    final index = _courses.indexOf(course);
    if (index >= 0) {
      _courses[index] = _courses[index].copyWith(progress: 1.0);
    }
    return getCourses();
  }
}
