import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:student_assistant/features/ai_assistant/domain/models/chat_message.dart';
import 'package:student_assistant/features/ai_assistant/domain/models/regulation_source.dart';
import 'package:student_assistant/services/ai_chat_page.dart';

void main() {
  testWidgets('language switch preserves visible chat and moves persistence bucket', (
    WidgetTester tester,
  ) async {
    final tempDir = await Directory.systemTemp.createTemp(
      'student_assistant_ai_chat_',
    );

    Hive.init(tempDir.path);
    final historyBox = await Hive.openBox('ai_chat_history');
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
    await historyBox.put('arabic_history', arabicHistory);

    await tester.pumpWidget(
      const MaterialApp(
        home: AIChatPage(
          key: ValueKey('chat-page'),
          isArabic: true,
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('سؤال تجريبي'), findsOneWidget);
    expect(find.text('إجابة تجريبية'), findsOneWidget);

    await tester.pumpWidget(
      const MaterialApp(
        home: AIChatPage(
          key: ValueKey('chat-page'),
          isArabic: false,
        ),
      ),
    );
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    expect(find.text('سؤال تجريبي'), findsOneWidget);
    expect(find.text('إجابة تجريبية'), findsOneWidget);

    final englishHistory = historyBox.get('english_history') as List?;
    expect(englishHistory, isNotNull);
    expect(englishHistory, hasLength(2));

    await tester.tap(find.byIcon(Icons.more_vert));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Clear chat history'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 300));
    await tester.tap(find.text('Clear'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));

    final updatedEnglishHistory = historyBox.get('english_history') as List?;
    final updatedArabicHistory = historyBox.get('arabic_history') as List?;
    expect(updatedEnglishHistory, isNotNull);
    expect(updatedEnglishHistory, hasLength(1));
    expect(updatedArabicHistory, isNotNull);
    expect(updatedArabicHistory, hasLength(2));

    await historyBox.close();
    await Hive.close();
  });
}