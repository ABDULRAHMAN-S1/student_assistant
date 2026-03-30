import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:student_assistant/app/local_encryption_key_provider.dart';
import 'package:student_assistant/features/ai_assistant/data/local/chat_history_store.dart';
import 'package:student_assistant/features/ai_assistant/domain/models/chat_message.dart';
import 'package:student_assistant/features/ai_assistant/domain/models/regulation_source.dart';

void main() {
  test(
    'chat history store keeps Arabic and English buckets isolated',
    () async {
      final tempDir = await Directory.systemTemp.createTemp(
        'student_assistant_ai_chat_',
      );

      LocalEncryptionKeyProvider.setTestKey(
        Uint8List.fromList(List<int>.generate(32, (index) => index + 1)),
      );
      Hive.init(tempDir.path);

      final store = ChatHistoryStore();
      final arabicHistory = [
        ChatMessage(
          text: 'سؤال تجريبي',
          isUser: true,
          timestamp: DateTime(2026, 3, 19, 10, 0, 0),
        ).toMap(),
        ChatMessage(
          text: 'إجابة تجريبية',
          isUser: false,
          timestamp: DateTime(2026, 3, 19, 10, 0, 1),
          sources: const [
            RegulationSource(
              id: 'src-1',
              docType: 'guide',
              documentTitle: 'دليل الإرشاد للطالب الجامعي',
              section: 'نظام التقديرات',
              article: 'DN',
              title: 'DN',
              content: 'إجابة تجريبية',
              contentPreview: 'إجابة تجريبية',
              score: 0.9,
            ),
          ],
          canFeedback: true,
          canTranslate: true,
        ).toMap(),
      ];

      await store.saveHistory(isArabic: true, messages: arabicHistory);
      await store.saveHistory(
        isArabic: false,
        messages: const [
          {
            'text': 'English question',
            'isUser': true,
            'timestamp': '2026-03-19T10:00:02.000',
            'sources': [],
            'canFeedback': false,
            'canTranslate': false,
            'helpful': null,
            'translatedText': null,
            'isShowingTranslation': false,
            'isTranslating': false,
          },
        ],
      );

      final loadedArabic = await store.loadHistory(isArabic: true);
      final loadedEnglish = await store.loadHistory(isArabic: false);
      expect(loadedArabic, hasLength(2));
      expect(loadedEnglish, hasLength(1));

      await store.clearHistory(isArabic: false);
      final clearedEnglish = await store.loadHistory(isArabic: false);
      final persistedArabic = await store.loadHistory(isArabic: true);
      expect(clearedEnglish, isEmpty);
      expect(persistedArabic, hasLength(2));

      await Hive.close();
      LocalEncryptionKeyProvider.setTestKey(null);
      await tempDir.delete(recursive: true);
    },
  );
}
