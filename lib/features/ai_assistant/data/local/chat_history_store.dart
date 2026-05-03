import 'package:hive/hive.dart';

import '../../../../app/app_hive.dart';

class ChatHistoryStore {
  const ChatHistoryStore();

  static const String _boxName = 'ai_chat_history';

  Future<Box> _openBox() async {
    if (Hive.isBoxOpen(_boxName)) {
      return Hive.box(_boxName);
    }
    try {
      return await AppHive.openBox(_boxName);
    } catch (error) {
      if (AppHive.isFileLockError(error)) {
        rethrow;
      }
      await Hive.deleteBoxFromDisk(_boxName);
      return AppHive.openBox(_boxName);
    }
  }

  String _historyKey(bool isArabic) =>
      isArabic ? 'arabic_history' : 'english_history';

  Future<List<Map<String, dynamic>>> loadHistory({
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

  Future<void> saveHistory({
    required bool isArabic,
    required List<Map<String, dynamic>> messages,
  }) async {
    final box = await _openBox();
    await box.put(_historyKey(isArabic), messages);
  }

  Future<void> clearHistory({required bool isArabic}) async {
    final box = await _openBox();
    await box.delete(_historyKey(isArabic));
  }
}
