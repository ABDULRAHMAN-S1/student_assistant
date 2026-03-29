import 'package:hive/hive.dart';

import '../../../../app/local_encryption_key_provider.dart';

class ChatHistoryStore {
  const ChatHistoryStore();

  static const String _boxName = 'ai_chat_history';

  Future<Box> _openBox() async {
    if (Hive.isBoxOpen(_boxName)) {
      return Hive.box(_boxName);
    }
    final encryptionKey = await LocalEncryptionKeyProvider.instance.getKey();
    try {
      return await Hive.openBox(
        _boxName,
        encryptionCipher: HiveAesCipher(encryptionKey),
      );
    } catch (error) {
      if (_isFileLockError(error)) {
        rethrow;
      }
      await Hive.deleteBoxFromDisk(_boxName);
      return Hive.openBox(
        _boxName,
        encryptionCipher: HiveAesCipher(encryptionKey),
      );
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

  bool _isFileLockError(Object error) {
    final message = error.toString().toLowerCase();
    return message.contains('lock failed') ||
        message.contains('being used by another process') ||
        message.contains('cannot delete file');
  }
}
