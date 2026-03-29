import '../../../courses/domain/models/course.dart';
import '../../../events/domain/models/event_item.dart';
import '../../../profile/domain/models/student_profile.dart';
import '../../domain/models/recommendation_item.dart';

class RecommendationEngine {
  const RecommendationEngine();

  List<RecommendationItem> generate({
    required StudentProfile profile,
    required List<Course> courses,
    required List<EventItem> events,
    int maxResults = 6,
    bool? isArabic,
  }) {
    final useArabic =
        isArabic ?? profile.preferredLanguageCode.toLowerCase().startsWith('ar');
    final specializationRaw = profile.academicContext.specialization.trim();
    final specialization = _normalize(specializationRaw);
    final academicLevelRaw =
        (profile.academicContext.academicLevel ?? '').trim();
    final academicLevel = _normalize(academicLevelRaw);
    final interestValues = profile.academicContext.interests
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toList(growable: false);
    final enrolledCourseValues = profile.academicContext.enrolledCourseIds
        .map((value) => value.trim())
        .where((value) => value.isNotEmpty)
        .toList(growable: false);

    final ranked = <_ScoredRecommendation>[];

    for (final course in courses) {
      final courseText = _normalize(
        '${course.titleAr} ${course.titleEn} ${course.semesterAr} ${course.semesterEn}',
      );
      final reasons = <String>[];
      final specializationSignals = <String>[];
      final interestSignals = <String>[];
      final academicLevelSignals = <String>[];
      final enrolledCourseSignals = <String>[];
      var score = 0;

      if (_matchesContext(courseText, specialization)) {
        score += 3;
        if (specializationRaw.isNotEmpty) {
          specializationSignals.add(specializationRaw);
        }
        reasons.add(
          useArabic
              ? 'يتوافق مع تخصصك${specializationRaw.isNotEmpty ? ' ($specializationRaw)' : ''}.'
              : 'It matches your specialization${specializationRaw.isNotEmpty ? ' ($specializationRaw)' : ''}.',
        );
      }

      final matchedInterests = _matchingValues(courseText, interestValues);
      if (matchedInterests.isNotEmpty) {
        score += 2;
        interestSignals.addAll(matchedInterests);
        reasons.add(
          useArabic
              ? 'يرتبط باهتماماتك (${matchedInterests.join('، ')}).'
              : 'It matches your interests (${matchedInterests.join(', ')}).',
        );
      }

      final matchedCourses = _matchingValues(courseText, enrolledCourseValues);
      if (matchedCourses.isNotEmpty) {
        score += 2;
        enrolledCourseSignals.addAll(matchedCourses);
        reasons.add(
          useArabic
              ? 'يشبه مقررات موجودة في سياقك الأكاديمي (${matchedCourses.join('، ')}).'
              : 'It is similar to a course already in your academic context (${matchedCourses.join(', ')}).',
        );
      }

      if (_supportsAcademicLevel(courseText, academicLevel)) {
        score += 1;
        if (academicLevelRaw.isNotEmpty) {
          academicLevelSignals.add(academicLevelRaw);
        }
        reasons.add(
          useArabic
              ? 'يناسب مستواك الأكاديمي الحالي${academicLevelRaw.isNotEmpty ? ' ($academicLevelRaw)' : ''}.'
              : 'It fits your current academic level${academicLevelRaw.isNotEmpty ? ' ($academicLevelRaw)' : ''}.',
        );
      }

      if (score <= 0) {
        continue;
      }

      ranked.add(
        _ScoredRecommendation(
          score: score,
          item: RecommendationItem(
            id: 'course_${_slug(course.titleEn.isNotEmpty ? course.titleEn : course.titleAr)}',
            type: RecommendationItem.courseType,
            title: _localizedValue(
              arabic: course.titleAr,
              english: course.titleEn,
              isArabic: useArabic,
            ),
            description: _localizedValue(
              arabic: course.semesterAr,
              english: course.semesterEn,
              isArabic: useArabic,
            ),
            reason: _buildReason(reasons),
            specializationSignals: _dedupeValues(specializationSignals),
            interestSignals: _dedupeValues(interestSignals),
            academicLevelSignals: _dedupeValues(academicLevelSignals),
            enrolledCourseSignals: _dedupeValues(enrolledCourseSignals),
          ),
        ),
      );
    }

    for (final event in events) {
      final eventText = _normalize(
        '${event.titleAr} ${event.titleEn} ${event.type} ${event.dateAr} ${event.dateEn}',
      );
      final reasons = <String>[];
      final specializationSignals = <String>[];
      final interestSignals = <String>[];
      final academicLevelSignals = <String>[];
      final enrolledCourseSignals = <String>[];
      var score = 0;

      if (_matchesContext(eventText, specialization)) {
        score += 2;
        if (specializationRaw.isNotEmpty) {
          specializationSignals.add(specializationRaw);
        }
        reasons.add(
          useArabic
              ? 'له صلة بتخصصك${specializationRaw.isNotEmpty ? ' ($specializationRaw)' : ''}.'
              : 'It is relevant to your specialization${specializationRaw.isNotEmpty ? ' ($specializationRaw)' : ''}.',
        );
      }

      final matchedInterests = _matchingValues(eventText, interestValues);
      if (matchedInterests.isNotEmpty) {
        score += 2;
        interestSignals.addAll(matchedInterests);
        reasons.add(
          useArabic
              ? 'يرتبط باهتماماتك (${matchedInterests.join('، ')}).'
              : 'It matches your interests (${matchedInterests.join(', ')}).',
        );
      }

      final matchedCourses = _matchingValues(eventText, enrolledCourseValues);
      if (matchedCourses.isNotEmpty) {
        score += 2;
        enrolledCourseSignals.addAll(matchedCourses);
        reasons.add(
          useArabic
              ? 'يكمل مقررات موجودة في سياقك الأكاديمي (${matchedCourses.join('، ')}).'
              : 'It complements a course already in your academic context (${matchedCourses.join(', ')}).',
        );
      }

      if (_eventFitsAcademicLevel(event.type, academicLevel)) {
        score += 1;
        if (academicLevelRaw.isNotEmpty) {
          academicLevelSignals.add(academicLevelRaw);
        }
        reasons.add(
          useArabic
              ? 'مفيد لمستواك الأكاديمي الحالي${academicLevelRaw.isNotEmpty ? ' ($academicLevelRaw)' : ''}.'
              : 'It is useful for your current academic level${academicLevelRaw.isNotEmpty ? ' ($academicLevelRaw)' : ''}.',
        );
      }

      if (score <= 0) {
        continue;
      }

      final localizedDate = _localizedValue(
        arabic: event.dateAr,
        english: event.dateEn,
        isArabic: useArabic,
      );

      ranked.add(
        _ScoredRecommendation(
          score: score,
          item: RecommendationItem(
            id: 'event_${_slug(event.titleEn.isNotEmpty ? event.titleEn : event.titleAr)}',
            type: RecommendationItem.eventType,
            title: _localizedValue(
              arabic: event.titleAr,
              english: event.titleEn,
              isArabic: useArabic,
            ),
            description: localizedDate.isEmpty
                ? event.time
                : '$localizedDate • ${event.time}',
            reason: _buildReason(reasons),
            specializationSignals: _dedupeValues(specializationSignals),
            interestSignals: _dedupeValues(interestSignals),
            academicLevelSignals: _dedupeValues(academicLevelSignals),
            enrolledCourseSignals: _dedupeValues(enrolledCourseSignals),
          ),
        ),
      );
    }

    ranked.sort((a, b) => b.score.compareTo(a.score));
    return ranked
        .take(maxResults)
        .map((entry) => entry.item)
        .toList(growable: false);
  }

  bool _matchesContext(String haystack, String contextValue) {
    if (contextValue.isEmpty) {
      return false;
    }

    if (haystack.contains(contextValue)) {
      return true;
    }

    final contextTokens = contextValue
        .split(' ')
        .where((token) => token.length >= 3);
    return contextTokens.any(haystack.contains);
  }

  List<String> _matchingValues(String haystack, List<String> candidates) {
    final matches = <String>[];
    final seen = <String>{};
    for (final candidate in candidates) {
      final normalizedCandidate = _normalize(candidate);
      if (normalizedCandidate.isEmpty) {
        continue;
      }
      if (_matchesContext(haystack, normalizedCandidate) &&
          seen.add(normalizedCandidate)) {
        matches.add(candidate);
      }
    }
    return matches;
  }

  bool _supportsAcademicLevel(String haystack, String academicLevel) {
    if (academicLevel.isEmpty) {
      return false;
    }

    if (academicLevel.contains('بكالوريوس') ||
        academicLevel.contains('bachelor')) {
      return haystack.contains('program') ||
          haystack.contains('math') ||
          haystack.contains('physics') ||
          haystack.contains('برمجة') ||
          haystack.contains('رياضيات') ||
          haystack.contains('فيزياء');
    }

    if (academicLevel.contains('ماجستير') ||
        academicLevel.contains('master') ||
        academicLevel.contains('دكتوراه') ||
        academicLevel.contains('phd')) {
      return haystack.contains('advanced') ||
          haystack.contains('research') ||
          haystack.contains('متقدمة') ||
          haystack.contains('بحث');
    }

    return haystack.contains('english') || haystack.contains('اللغة');
  }

  bool _eventFitsAcademicLevel(String eventType, String academicLevel) {
    if (academicLevel.isEmpty) {
      return false;
    }

    if (academicLevel.contains('بكالوريوس') ||
        academicLevel.contains('bachelor')) {
      return eventType == 'exam' || eventType == 'workshop';
    }

    if (academicLevel.contains('ماجستير') ||
        academicLevel.contains('master') ||
        academicLevel.contains('دكتوراه') ||
        academicLevel.contains('phd')) {
      return eventType == 'workshop' || eventType == 'event';
    }

    return eventType == 'event';
  }

  String _buildReason(List<String> reasons) {
    final deduped = <String>[];
    final seen = <String>{};
    for (final reason in reasons) {
      if (seen.add(reason)) {
        deduped.add(reason);
      }
    }
    return deduped.join(' ');
  }

  String _localizedValue({
    required String arabic,
    required String english,
    required bool isArabic,
  }) {
    if (isArabic) {
      return arabic.trim().isNotEmpty ? arabic.trim() : english.trim();
    }
    return english.trim().isNotEmpty ? english.trim() : arabic.trim();
  }

  String _normalize(String value) {
    return value.trim().toLowerCase();
  }

  List<String> _dedupeValues(List<String> values) {
    final deduped = <String>[];
    final seen = <String>{};
    for (final value in values) {
      final normalized = _normalize(value);
      if (normalized.isEmpty || !seen.add(normalized)) {
        continue;
      }
      deduped.add(value.trim());
    }
    return deduped;
  }

  String _slug(String value) {
    return _normalize(
      value,
    ).replaceAll(RegExp(r'[^a-z0-9\u0600-\u06FF]+'), '_');
  }
}

class _ScoredRecommendation {
  const _ScoredRecommendation({required this.score, required this.item});

  final int score;
  final RecommendationItem item;
}
