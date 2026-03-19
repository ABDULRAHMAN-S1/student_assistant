class RegulationSource {
  const RegulationSource({
    required this.id,
    required this.docType,
    required this.documentTitle,
    required this.section,
    required this.article,
    required this.title,
    required this.content,
    required this.contentPreview,
    required this.score,
  });

  final String id;
  final String docType;
  final String documentTitle;
  final String section;
  final String article;
  final String title;
  final String content;
  final String contentPreview;
  final double? score;

  static const String _regulationType = 'regulation';
  static const String _policyType = 'policy';
  static const String _guideType = 'guide';
  static const String _faqType = 'faq';
  static const Set<String> _decorativeSectionTitles = {
    'والله ولي التوفيق',
    'المحتويات',
    'فهرس',
    'contents',
    'table of contents',
    'index',
  };

  factory RegulationSource.fromJson(Map<String, dynamic> json) {
    final rawScore = json['score'];
    return RegulationSource(
      id: (json['id'] ?? '').toString().trim(),
      docType: _normalizeDocType(json['doc_type']),
      documentTitle: (json['document_title'] ?? '').toString().trim(),
      section: (json['section'] ?? '').toString().trim(),
      article: (json['article'] ?? '').toString().trim(),
      title: (json['title'] ?? '').toString().trim(),
      content: (json['content'] ?? '').toString().trim(),
      contentPreview: (json['content_preview'] ?? '').toString().trim(),
      score: rawScore is num ? rawScore.toDouble() : null,
    );
  }

  static List<RegulationSource> listFromJson(dynamic rawList) {
    if (rawList is! List) {
      return const [];
    }

    return rawList
        .whereType<Map>()
        .map(
          (item) => RegulationSource.fromJson(Map<String, dynamic>.from(item)),
        )
        .toList(growable: false);
  }

  bool get hasReference =>
      documentTitle.isNotEmpty || section.isNotEmpty || article.isNotEmpty;

  static String _normalizeDocType(dynamic value) {
    final normalized = (value ?? '').toString().trim().toLowerCase();
    switch (normalized) {
      case _policyType:
        return _policyType;
      case _guideType:
        return _guideType;
      case _faqType:
        return _faqType;
      case _regulationType:
      default:
        return _regulationType;
    }
  }

  String sourceTypeLabel({required bool isArabic}) {
    switch (docType) {
      case _policyType:
        return isArabic ? 'سياسة' : 'Policy';
      case _guideType:
        return isArabic ? 'دليل' : 'Guide';
      case _faqType:
        return isArabic ? 'أسئلة شائعة' : 'FAQ';
      case _regulationType:
      default:
        return isArabic ? 'لائحة' : 'Regulation';
    }
  }

  String sourceTypeTag({required bool isArabic}) {
    return '[${sourceTypeLabel(isArabic: isArabic)}]';
  }

  static bool _isDecorativeSectionTitle(String value) {
    final normalized = value.trim().toLowerCase();
    return normalized.isNotEmpty &&
        _decorativeSectionTitles.contains(normalized);
  }

  static String _cleanDisplaySection(String value) {
    final parts = <String>[];
    final seen = <String>{};
    for (final rawPart in value.split('>')) {
      final part = rawPart.trim();
      final normalized = part.toLowerCase();
      if (part.isEmpty ||
          seen.contains(normalized) ||
          _isDecorativeSectionTitle(part)) {
        continue;
      }
      seen.add(normalized);
      parts.add(part);
    }
    return parts.join(' > ');
  }

  String get cleanedSection => _cleanDisplaySection(section);

  String get primaryDisplayTitle {
    if (documentTitle.isNotEmpty) return documentTitle;
    if (article.isNotEmpty) return article;
    if (cleanedSection.isNotEmpty) return cleanedSection;
    return title;
  }

  String get secondaryDisplayArticle {
    if (article.isEmpty || article == primaryDisplayTitle) {
      return '';
    }
    return article;
  }

  String get secondaryDisplaySection {
    if (cleanedSection.isEmpty || cleanedSection == primaryDisplayTitle) {
      return '';
    }
    return cleanedSection;
  }

  String toDisplayString({bool isArabic = true}) {
    final parts = <String>[
      sourceTypeTag(isArabic: isArabic),
      if (primaryDisplayTitle.isNotEmpty) primaryDisplayTitle,
      if (secondaryDisplayArticle.isNotEmpty) secondaryDisplayArticle,
      if (secondaryDisplaySection.isNotEmpty) secondaryDisplaySection,
    ];

    return parts.join(' | ');
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'doc_type': docType,
      'document_title': documentTitle,
      'section': section,
      'article': article,
      'title': title,
      'content': content,
      'content_preview': contentPreview,
      'score': score,
    };
  }
}
