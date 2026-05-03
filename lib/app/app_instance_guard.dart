import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';

class AppInstanceException implements Exception {
  const AppInstanceException(this.message, {this.alreadyRunning = false});

  final String message;
  final bool alreadyRunning;

  @override
  String toString() => message;
}

class AppInstanceGuard {
  AppInstanceGuard._();

  static const String _lockFileName = 'student_assistant.instance.lock';
  static final AppInstanceGuard instance = AppInstanceGuard._();

  static Directory? _testDirectory;

  RandomAccessFile? _lockHandle;

  static void setTestDirectory(Directory? directory) {
    _testDirectory = directory;
  }

  Future<void> ensureSingleInstance() async {
    if (kIsWeb) {
      return;
    }

    if (_lockHandle != null) {
      return;
    }

    final appSupportDirectory =
        _testDirectory ?? await getApplicationSupportDirectory();
    await appSupportDirectory.create(recursive: true);

    final lockFile = File(
      '${appSupportDirectory.path}${Platform.pathSeparator}$_lockFileName',
    );

    RandomAccessFile? handle;
    try {
      handle = await lockFile.open(mode: FileMode.append);
      await handle.lock(FileLock.exclusive);
      _lockHandle = handle;
    } on FileSystemException catch (error) {
      await handle?.close();
      if (_isAlreadyRunningError(error)) {
        throw const AppInstanceException(
          'Another Student Assistant window is already running.',
          alreadyRunning: true,
        );
      }
      throw AppInstanceException(
        'Could not acquire the app startup lock: ${error.message}',
      );
    }
  }

  Future<void> release() async {
    final handle = _lockHandle;
    _lockHandle = null;

    if (handle == null) {
      return;
    }

    try {
      await handle.unlock();
    } catch (_) {
      // Closing the handle is enough if the OS already released the lock.
    }
    await handle.close();
  }

  bool _isAlreadyRunningError(FileSystemException error) {
    final message = error.toString().toLowerCase();
    return message.contains('lock') ||
        message.contains('being used by another process') ||
        message.contains('used by another process');
  }
}
