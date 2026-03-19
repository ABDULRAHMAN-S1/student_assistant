import '../features/ai_assistant/data/local/chat_history_store.dart';

class AiChatStorage {
  static const ChatHistoryStore _store = ChatHistoryStore();

  static Future<List<Map<String, dynamic>>> loadHistory({
    required bool isArabic,
  }) {
    return _store.loadHistory(isArabic: isArabic);
  }

  static Future<void> saveHistory({
    required bool isArabic,
    required List<Map<String, dynamic>> messages,
  }) {
    return _store.saveHistory(isArabic: isArabic, messages: messages);
  }

  static Future<void> clearHistory({required bool isArabic}) {
    return _store.clearHistory(isArabic: isArabic);
  }
}
