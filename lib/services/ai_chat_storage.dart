import 'package:hive/hive.dart';

class AiChatStorage {
  static const String _boxName = 'ai_chat_history';

  static Future<Box> _openBox() async {
    if (Hive.isBoxOpen(_boxName)) {
      return Hive.box(_boxName);
    }
    return Hive.openBox(_boxName);
  }

  static String _historyKey(bool isArabic) =>
      isArabic ? 'arabic_history' : 'english_history';

  static Future<List<Map<String, dynamic>>> loadHistory({
    required bool isArabic,
  }) async {
    final box = await _openBox();
    final raw = box.get(_historyKey(isArabic), defaultValue: const []);
    if (raw is! List) {
      return const [];
    }

    return raw
        .whereType<Map>()
        .map((item) => Map<String, dynamic>.from(item))
        .toList(growable: false);
  }

  static Future<void> saveHistory({
    required bool isArabic,
    required List<Map<String, dynamic>> messages,
  }) async {
    final box = await _openBox();
    await box.put(_historyKey(isArabic), messages);
  }

  static Future<void> clearHistory({required bool isArabic}) async {
    final box = await _openBox();
    await box.delete(_historyKey(isArabic));
  }
}
