import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:student_assistant/app/app_session_controller.dart';
import 'package:student_assistant/app/app_settings_store.dart';
import 'package:student_assistant/main.dart';

void main() {
  testWidgets('StudentAssistantApp builds with app session controller', (
    WidgetTester tester,
  ) async {
    final tempDir = await Directory.systemTemp.createTemp(
      'student_assistant_test_',
    );

    Hive.init(tempDir.path);
    final box = await Hive.openBox(AppSettingsStore.boxName);
    final store = AppSettingsStore.fromBox(box);
    final controller = AppSessionController(settingsStore: store)..initialize();

    await tester.pumpWidget(StudentAssistantApp(sessionController: controller));

    expect(find.byType(MaterialApp), findsOneWidget);

    await box.close();
    await tempDir.delete(recursive: true);
  });
}
