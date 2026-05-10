import 'dart:convert';
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

    final helperScript = File(
      '${tempDir.path}${Platform.pathSeparator}hold_lock.dart',
    );
    await helperScript.writeAsString('''
import 'dart:io';

Future<void> main(List<String> args) async {
  final path = args.first;
  final file = File(path);
  final handle = await file.open(mode: FileMode.append);
  await handle.lock(FileLock.exclusive);
  stdout.writeln('locked');
  await Future<void>.delayed(const Duration(seconds: 10));
  await handle.unlock();
  await handle.close();
}
''');

    final process = await Process.start('dart', [
      helperScript.path,
      lockFile.path,
    ]);
    addTearDown(() async {
      process.kill();
      await process.exitCode.timeout(
        const Duration(seconds: 2),
        onTimeout: () => 0,
      );
    });

    final ready = await process.stdout
        .transform(SystemEncoding().decoder)
        .transform(const LineSplitter())
        .first;
    expect(ready, 'locked');

    await expectLater(
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
