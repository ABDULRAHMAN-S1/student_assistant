import 'package:flutter/material.dart';

import 'features/reviews/data/demo/demo_review_repository.dart';
import 'features/reviews/data/repositories/review_repository.dart';
import 'features/reviews/domain/models/student_review.dart';

class ReviewsPage extends StatefulWidget {
  final bool isArabic;

  const ReviewsPage({super.key, required this.isArabic});

  @override
  State<ReviewsPage> createState() => _ReviewsPageState();
}

class _ReviewsPageState extends State<ReviewsPage> {
  final Color _primaryCyan = const Color(0xFFFF8A00);
  final Color _secondaryBlue = const Color(0xFFFFA726);
  final Color _accentPurple = const Color(0xFFE65100);
  final ReviewRepository _reviewRepository = DemoReviewRepository();

  List<StudentReview> _reviews = const [];

  @override
  void initState() {
    super.initState();
    _reviews = _reviewRepository.getReviews();
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
              itemCount: _reviews.length,
              itemBuilder: (context, index) {
                return _buildReviewCard(_reviews[index]);
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showAddReviewDialog,
        backgroundColor: _primaryCyan,
        icon: const Icon(Icons.rate_review),
        label: Text(widget.isArabic ? 'أضف تقييم' : 'Add Review'),
      ),
    );
  }

  Widget _buildHeader() {
    final average = _averageRating;
    final count = _reviews.length;
    final countLabel = widget.isArabic ? 'تقييم' : 'reviews';

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
                widget.isArabic ? 'التقييمات' : 'Reviews',
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
                child: const Icon(Icons.star, color: Colors.white, size: 24),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 16,
                  vertical: 8,
                ),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.star, color: Colors.amber, size: 20),
                    const SizedBox(width: 8),
                    Text(
                      average.toStringAsFixed(1),
                      style: const TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      widget.isArabic
                          ? '($count $countLabel)'
                          : '($count $countLabel)',
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.8),
                        fontSize: 14,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildReviewCard(StudentReview review) {
    final name = widget.isArabic ? review.nameAr : review.nameEn;
    final comment = widget.isArabic ? review.commentAr : review.commentEn;
    final date = widget.isArabic ? review.dateAr : review.dateEn;

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
          onTap: () => _showReviewDetails(review),
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    CircleAvatar(
                      radius: 24,
                      backgroundColor: _primaryCyan,
                      child: Text(
                        review.avatar,
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            name,
                            style: const TextStyle(
                              fontSize: 16.5,
                              fontWeight: FontWeight.w800,
                              height: 1.35,
                            ),
                          ),
                          const SizedBox(height: 4),
                          Row(
                            children: [
                              ...List.generate(5, (index) {
                                return Icon(
                                  index < review.rating
                                      ? Icons.star
                                      : Icons.star_border,
                                  color: Colors.amber,
                                  size: 16,
                                );
                              }),
                              const SizedBox(width: 8),
                              Text(
                                date,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: Colors.grey[500],
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text(
                  comment,
                  style: TextStyle(
                    fontSize: 14.2,
                    color: Colors.grey[700],
                    height: 1.58,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Future<void> _showAddReviewDialog() async {
    final nameController = TextEditingController();
    final commentController = TextEditingController();
    int selectedRating = 5;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text(widget.isArabic ? 'إضافة تقييم' : 'Add Review'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: nameController,
                      decoration: InputDecoration(
                        labelText: widget.isArabic ? 'الاسم' : 'Name',
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: commentController,
                      maxLines: 3,
                      decoration: InputDecoration(
                        labelText: widget.isArabic ? 'التعليق' : 'Comment',
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<int>(
                      initialValue: selectedRating,
                      decoration: InputDecoration(
                        labelText: widget.isArabic ? 'التقييم' : 'Rating',
                      ),
                      items: List.generate(5, (index) => index + 1)
                          .map(
                            (rating) => DropdownMenuItem<int>(
                              value: rating,
                              child: Text(
                                widget.isArabic
                                    ? '$rating نجوم'
                                    : '$rating stars',
                              ),
                            ),
                          )
                          .toList(),
                      onChanged: (value) {
                        if (value == null) {
                          return;
                        }
                        setDialogState(() {
                          selectedRating = value;
                        });
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  child: Text(widget.isArabic ? 'إلغاء' : 'Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    final name = nameController.text.trim();
                    final comment = commentController.text.trim();

                    if (name.isEmpty || comment.isEmpty) {
                      _showMessage(
                        widget.isArabic
                            ? 'يرجى إدخال الاسم والتعليق'
                            : 'Please enter your name and comment',
                      );
                      return;
                    }

                    setState(() {
                      final avatar = name.isNotEmpty
                          ? name.substring(0, 1).toUpperCase()
                          : 'S';

                      _reviews = _reviewRepository.addReview(
                        StudentReview(
                          nameAr: name,
                          nameEn: name,
                          rating: selectedRating,
                          commentAr: comment,
                          commentEn: comment,
                          dateAr: 'الآن',
                          dateEn: 'Just now',
                          avatar: avatar,
                        ),
                      );
                    });

                    Navigator.of(dialogContext).pop();
                    _showMessage(
                      widget.isArabic
                          ? 'تمت إضافة التقييم بنجاح'
                          : 'Review added successfully',
                    );
                  },
                  child: Text(widget.isArabic ? 'إضافة' : 'Add'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showReviewDetails(StudentReview review) {
    final name = widget.isArabic ? review.nameAr : review.nameEn;
    final comment = widget.isArabic ? review.commentAr : review.commentEn;
    final date = widget.isArabic ? review.dateAr : review.dateEn;

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
                  CircleAvatar(
                    radius: 24,
                    backgroundColor: _primaryCyan,
                    child: Text(
                      review.avatar,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      name,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  ...List.generate(5, (index) {
                    return Icon(
                      index < review.rating ? Icons.star : Icons.star_border,
                      color: Colors.amber,
                      size: 18,
                    );
                  }),
                  const SizedBox(width: 8),
                  Text(date, style: TextStyle(color: Colors.grey[600])),
                ],
              ),
              const SizedBox(height: 16),
              Text(
                comment,
                style: TextStyle(
                  fontSize: 14,
                  height: 1.6,
                  color: Colors.grey[700],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  double get _averageRating {
    if (_reviews.isEmpty) {
      return 0;
    }

    final total = _reviews.fold<int>(0, (sum, review) => sum + review.rating);
    return total / _reviews.length;
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}
