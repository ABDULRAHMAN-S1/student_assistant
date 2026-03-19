class StudentReview {
  const StudentReview({
    required this.nameAr,
    required this.nameEn,
    required this.rating,
    required this.commentAr,
    required this.commentEn,
    required this.dateAr,
    required this.dateEn,
    required this.avatar,
  });

  final String nameAr;
  final String nameEn;
  final int rating;
  final String commentAr;
  final String commentEn;
  final String dateAr;
  final String dateEn;
  final String avatar;

  StudentReview copyWith({
    String? nameAr,
    String? nameEn,
    int? rating,
    String? commentAr,
    String? commentEn,
    String? dateAr,
    String? dateEn,
    String? avatar,
  }) {
    return StudentReview(
      nameAr: nameAr ?? this.nameAr,
      nameEn: nameEn ?? this.nameEn,
      rating: rating ?? this.rating,
      commentAr: commentAr ?? this.commentAr,
      commentEn: commentEn ?? this.commentEn,
      dateAr: dateAr ?? this.dateAr,
      dateEn: dateEn ?? this.dateEn,
      avatar: avatar ?? this.avatar,
    );
  }
}
