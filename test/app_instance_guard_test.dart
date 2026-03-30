import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_assistant/app/app_instance_guard.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late Directory tempDir;

  setUp(() async {
    tempDir = await Directory.systemTemp.createTemp(
      'student_assistant_guard_test_',
    );
    AppInstanceGuard.setTestDirectory(tempDir);
    await AppInstanceGuard.instance.release();
  });

  tearDown(() async {
    await AppInstanceGuard.instance.release();
    AppInstanceGuard.setTestDirectory(null);
    if (await tempDir.exists()) {
      await tempDir.delete(recursive: true);
    }
  });

  test('creates the startup lock file when acquiring the guard', () async {
    await AppInstanceGuard.instance.ensureSingleInstance();

    final lockFile = File(
      '${tempDir.path}${Platform.pathSeparator}student_assistant.instance.lock',
    );

    expect(await lockFile.exists(), isTrue);
  });

  test('rejects a second process lock holder', () async {
    final lockFile = File(
      '${tempDir.path}${Platform.pathSeparator}student_assistant.instance.lock',
    );
    await lockFile.parent.create(recursive: true);

    final externalHandle = await lockFile.open(mode: FileMode.append);
    await externalHandle.lock(FileLock.exclusive);
    addTearDown(() async {
      try {
        await externalHandle.unlock();
      } catch (_) {
        // The OS may already release the lock on close.
      }
      await externalHandle.close();
    });

    expect(
      AppInstanceGuard.instance.ensureSingleInstance(),
      throwsA(
        isA<AppInstanceException>().having(
          (error) => error.alreadyRunning,
          'alreadyRunning',
          isTrue,
        ),
      ),
    );
  });
}
