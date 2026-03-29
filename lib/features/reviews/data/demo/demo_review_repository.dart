import '../../domain/models/student_review.dart';
import '../repositories/review_repository.dart';

class DemoReviewRepository implements ReviewRepository {
  DemoReviewRepository();

  final List<StudentReview> _reviews = const [
    StudentReview(
      nameAr: 'أحمد محمد',
      nameEn: 'Ahmed Mohammed',
      rating: 5,
      commentAr: 'تطبيق رائع! ساعدني كثير في تنظيم وقتي الدراسي',
      commentEn: 'Amazing app! Helped me a lot with organizing my study time',
      dateAr: 'منذ يومين',
      dateEn: '2 days ago',
      avatar: 'A',
    ),
    StudentReview(
      nameAr: 'سارة علي',
      nameEn: 'Sara Ali',
      rating: 4,
      commentAr: 'واجهة جميلة وسهلة الاستخدام. أنصح به بشدة',
      commentEn: 'Beautiful and easy to use interface. Highly recommended',
      dateAr: 'منذ أسبوع',
      dateEn: '1 week ago',
      avatar: 'S',
    ),
    StudentReview(
      nameAr: 'خالد عبدالله',
      nameEn: 'Khalid Abdullah',
      rating: 5,
      commentAr: 'المساعد الذكي ممتاز جداً في الإجابة على أسئلتي',
      commentEn: 'The AI assistant is excellent at answering my questions',
      dateAr: 'منذ أسبوعين',
      dateEn: '2 weeks ago',
      avatar: 'K',
    ),
  ].toList();

  @override
  List<StudentReview> getReviews() => List.unmodifiable(_reviews);

  @override
  List<StudentReview> addReview(StudentReview review) {
    _reviews.insert(0, review);
    return getReviews();
  }
}
