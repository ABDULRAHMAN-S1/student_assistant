import '../../domain/models/course.dart';

abstract class CourseRepository {
  List<Course> getCourses();

  List<Course> addCourse(Course course);

  List<Course> markCourseCompleted(Course course);
}
