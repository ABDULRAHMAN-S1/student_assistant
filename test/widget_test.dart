import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:student_assistant/app/app_session_controller.dart';
import 'package:student_assistant/app/app_settings_store.dart';

void main() {
  test('AppSessionController initializes from persisted settings', () async {
    final tempDir = await Directory.systemTemp.createTemp(
      'student_assistant_test_',
    );

    Hive.init(tempDir.path);
    final box = await Hive.openBox(AppSettingsStore.boxName);
    await box.put(AppSettingsStore.languageKey, 'en');
    await box.put(AppSettingsStore.hasSeenWelcomeKey, true);
    final store = AppSettingsStore.fromBox(box);
    final controller = AppSessionController(settingsStore: store)..initialize();

    expect(controller.locale.languageCode, 'en');
    expect(controller.hasSeenWelcome, isTrue);
    expect(controller.isGuest, isTrue);

    await box.close();
    await Hive.close();
    await tempDir.delete(recursive: true);
  });
}
