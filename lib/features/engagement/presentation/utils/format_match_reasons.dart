const Map<String, String> _arabicReasonMap = {
  'major_match': 'مناسب لتخصصك',
  'level_match': 'مناسب لمستواك',
  'interest_match': 'مرتبط باهتماماتك',
  'track_match': 'يناسب مسارك',
};

const Map<String, String> _englishReasonMap = {
  'major_match': 'Matches your major',
  'level_match': 'Matches your level',
  'interest_match': 'Related to your interests',
  'track_match': 'Fits your track',
};

List<String> formatMatchReasons(
  List<String> reasons, {
  required bool isArabic,
}) {
  final dictionary = isArabic ? _arabicReasonMap : _englishReasonMap;
  return reasons
      .map((reason) => dictionary[reason.trim()] ?? reason.trim())
      .where((reason) => reason.isNotEmpty)
      .toList(growable: false);
}
