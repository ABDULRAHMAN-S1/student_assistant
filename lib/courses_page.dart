import 'package:flutter/material.dart';

import 'features/courses/data/demo/demo_course_repository.dart';
import 'features/courses/data/repositories/course_repository.dart';
import 'features/courses/domain/models/course.dart';

class CoursesPage extends StatefulWidget {
  final bool isArabic;

  const CoursesPage({super.key, required this.isArabic});

  @override
  State<CoursesPage> createState() => _CoursesPageState();
}

class _CoursesPageState extends State<CoursesPage> {
  final Color _primaryCyan = const Color(0xFF00B35A);
  final Color _secondaryBlue = const Color(0xFF00C853);
  final Color _accentPurple = const Color(0xFF009624);
  final CourseRepository _courseRepository = DemoCourseRepository();

  List<Course> _courses = const [];

  @override
  void initState() {
    super.initState();
    _courses = _courseRepository.getCourses();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      body: Column(
        children: [
          _buildHeader(),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _courses.length,
              itemBuilder: (context, index) {
                return _buildCourseCard(_courses[index], index);
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddCourseDialog,
        backgroundColor: _primaryCyan,
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 50, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_primaryCyan, _secondaryBlue, _accentPurple],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(30),
          bottomRight: Radius.circular(30),
        ),
        boxShadow: [
          BoxShadow(
            color: _primaryCyan.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                widget.isArabic ? 'موادي الدراسية' : 'My Courses',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.school, color: Colors.white, size: 24),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            widget.isArabic
                ? 'تابع تقدمك في دراستك'
                : 'Track your learning progress',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.8),
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCourseCard(Course course, int index) {
    final title = widget.isArabic ? course.titleAr : course.titleEn;
    final semester = widget.isArabic ? course.semesterAr : course.semesterEn;
    final progressPercent = (course.progress * 100).toInt();

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () => _showCourseDetails(course),
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(12),
                      decoration: BoxDecoration(
                        color: course.color.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(15),
                      ),
                      child: Icon(course.icon, color: course.color, size: 28),
                    ),
                    const SizedBox(width: 16),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: const TextStyle(
                              fontSize: 17.5,
                              fontWeight: FontWeight.w800,
                              height: 1.35,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Text(
                            semester,
                            style: TextStyle(
                              fontSize: 14,
                              color: Colors.grey[600],
                              height: 1.4,
                            ),
                          ),
                        ],
                      ),
                    ),
                    PopupMenuButton<String>(
                      onSelected: (value) {
                        if (value == 'details') {
                          _showCourseDetails(course);
                        } else if (value == 'complete') {
                          setState(() {
                            _courses = _courseRepository.markCourseCompleted(
                              _courses[index],
                            );
                          });
                          _showMessage(
                            widget.isArabic
                                ? 'تم تحديث تقدم المقرر إلى 100%'
                                : 'Course progress updated to 100%',
                          );
                        }
                      },
                      itemBuilder: (context) => [
                        PopupMenuItem<String>(
                          value: 'details',
                          child: Text(
                            widget.isArabic ? 'عرض التفاصيل' : 'View details',
                          ),
                        ),
                        PopupMenuItem<String>(
                          value: 'complete',
                          child: Text(
                            widget.isArabic ? 'تحديد كمكتمل' : 'Mark completed',
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(10),
                        child: LinearProgressIndicator(
                          value: course.progress,
                          backgroundColor: Colors.grey[200],
                          valueColor: AlwaysStoppedAnimation<Color>(
                            course.color,
                          ),
                          minHeight: 8,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Text(
                      '$progressPercent%',
                      style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.bold,
                        color: course.color,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Text(
                  widget.isArabic
                      ? 'تم إنجاز $progressPercent% من المنهج'
                      : '$progressPercent% of curriculum completed',
                  style: TextStyle(
                    fontSize: 12.5,
                    color: Colors.grey[500],
                    height: 1.4,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showCourseDetails(Course course) {
    final title = widget.isArabic ? course.titleAr : course.titleEn;
    final semester = widget.isArabic ? course.semesterAr : course.semesterEn;
    final progressPercent = (course.progress * 100).toInt();

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 42,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Row(
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: course.color.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Icon(course.icon, color: course.color, size: 28),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Text(
                      title,
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              _buildInfoRow(widget.isArabic ? 'الفصل' : 'Semester', semester),
              _buildInfoRow(
                widget.isArabic ? 'نسبة الإنجاز' : 'Progress',
                '$progressPercent%',
              ),
              _buildInfoRow(
                widget.isArabic ? 'الحالة' : 'Status',
                progressPercent >= 100
                    ? (widget.isArabic ? 'مكتمل' : 'Completed')
                    : (widget.isArabic ? 'قيد الدراسة' : 'In progress'),
              ),
              const SizedBox(height: 12),
              Text(
                widget.isArabic
                    ? 'يمكنك متابعة تقدمك في هذا المقرر من نفس الصفحة.'
                    : 'You can keep tracking your progress for this course from this page.',
                style: TextStyle(
                  fontSize: 14,
                  height: 1.5,
                  color: Colors.grey[700],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _showAddCourseDialog() async {
    final titleController = TextEditingController();
    final semesterController = TextEditingController();

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return AlertDialog(
          title: Text(widget.isArabic ? 'إضافة مقرر' : 'Add Course'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: titleController,
                decoration: InputDecoration(
                  labelText: widget.isArabic ? 'اسم المقرر' : 'Course name',
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: semesterController,
                decoration: InputDecoration(
                  labelText: widget.isArabic ? 'الفصل الدراسي' : 'Semester',
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(dialogContext).pop(),
              child: Text(widget.isArabic ? 'إلغاء' : 'Cancel'),
            ),
            FilledButton(
              onPressed: () {
                final title = titleController.text.trim();
                final semester = semesterController.text.trim();

                if (title.isEmpty) {
                  _showMessage(
                    widget.isArabic
                        ? 'يرجى إدخال اسم المقرر'
                        : 'Please enter a course name',
                  );
                  return;
                }

                setState(() {
                  _courses = _courseRepository.addCourse(
                    Course(
                      titleAr: title,
                      titleEn: title,
                      semesterAr: semester.isEmpty
                          ? 'الفصل الدراسي الحالي'
                          : semester,
                      semesterEn: semester.isEmpty
                          ? 'Current Semester'
                          : semester,
                      icon: Icons.menu_book,
                      color: _primaryCyan,
                      progress: 0.0,
                    ),
                  );
                });

                Navigator.of(dialogContext).pop();
                _showMessage(
                  widget.isArabic
                      ? 'تمت إضافة المقرر بنجاح'
                      : 'Course added successfully',
                );
              },
              child: Text(widget.isArabic ? 'إضافة' : 'Add'),
            ),
          ],
        );
      },
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$label: ', style: const TextStyle(fontWeight: FontWeight.bold)),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}
