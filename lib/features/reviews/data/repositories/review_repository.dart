import '../../domain/models/student_review.dart';

abstract class ReviewRepository {
  List<StudentReview> getReviews();

  List<StudentReview> addReview(StudentReview review);
}
