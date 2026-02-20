import 'package:flutter/material.dart';

class ReviewsPage extends StatefulWidget {
  final bool isArabic;

  const ReviewsPage({super.key, required this.isArabic});

  @override
  State<ReviewsPage> createState() => _ReviewsPageState();
}

class _ReviewsPageState extends State<ReviewsPage> {
  final Color _primaryCyan = const Color(0xFF26C6DA);
  final Color _secondaryBlue = const Color(0xFF4DD0E1);
  final Color _accentPurple = const Color(0xFF00ACC1);

  final List<Map<String, dynamic>> _reviews = [
    {
      'nameAr': 'أحمد محمد',
      'nameEn': 'Ahmed Mohammed',
      'rating': 5,
      'commentAr': 'تطبيق رائع! ساعدني كثير في تنظيم وقتي الدراسي',
      'commentEn': 'Amazing app! Helped me a lot with organizing my study time',
      'date': '2 days ago',
      'avatar': 'A',
    },
    {
      'nameAr': 'سارة علي',
      'nameEn': 'Sara Ali',
      'rating': 4,
      'commentAr': 'واجهة جميلة وسهلة الاستخدام. أنصح به بشدة',
      'commentEn': 'Beautiful and easy to use interface. Highly recommended',
      'date': '1 week ago',
      'avatar': 'S',
    },
    {
      'nameAr': 'خالد عبدالله',
      'nameEn': 'Khalid Abdullah',
      'rating': 5,
      'commentAr': 'المساعد الذكي ممتاز جداً في الإجابة على أسئلتي',
      'commentEn': 'The AI assistant is excellent at answering my questions',
      'date': '2 weeks ago',
      'avatar': 'K',
    },
  ];

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
        onPressed: () {},
        backgroundColor: _primaryCyan,
        icon: const Icon(Icons.rate_review),
        label: Text(widget.isArabic ? 'أضف تقييم' : 'Add Review'),
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
                    const Text(
                      '4.8',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      widget.isArabic ? '(١٢٤ تقييم)' : '(124 reviews)',
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

  Widget _buildReviewCard(Map<String, dynamic> review) {
    final name = widget.isArabic ? review['nameAr'] : review['nameEn'];
    final comment = widget.isArabic ? review['commentAr'] : review['commentEn'];

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 15,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                CircleAvatar(
                  radius: 24,
                  backgroundColor: _primaryCyan,
                  child: Text(
                    review['avatar'],
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
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          ...List.generate(5, (index) {
                            return Icon(
                              index < review['rating']
                                  ? Icons.star
                                  : Icons.star_border,
                              color: Colors.amber,
                              size: 16,
                            );
                          }),
                          const SizedBox(width: 8),
                          Text(
                            review['date'],
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
                fontSize: 14,
                color: Colors.grey[700],
                height: 1.5,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
