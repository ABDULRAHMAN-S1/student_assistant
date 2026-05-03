import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:path_provider/path_provider.dart';

import 'local_encryption_key_provider.dart';

class AppHive {
  AppHive._();

  static bool _initialized = false;

  static Future<void> ensureInitialized() async {
    if (_initialized) {
      return;
    }

    if (kIsWeb) {
      await Hive.initFlutter();
      _initialized = true;
      return;
    }

    final appSupportDirectory = await getApplicationSupportDirectory();
    await appSupportDirectory.create(recursive: true);
    Hive.init(appSupportDirectory.path);
    _initialized = true;
  }

  static Future<Box> openBox(String name) async {
    if (Hive.isBoxOpen(name)) {
      return Hive.box(name);
    }

    try {
      return await _openPlatformBox(name);
    } catch (error) {
      if (isFileLockError(error)) {
        rethrow;
      }
      if (looksLikeCorruptionError(error)) {
        await Hive.deleteBoxFromDisk(name);
        return _openPlatformBox(name);
      }
      rethrow;
    }
  }

  static Future<Box> _openPlatformBox(String name) async {
    if (kIsWeb) {
      return Hive.openBox(name);
    }

    final encryptionKey = await LocalEncryptionKeyProvider.instance.getKey();
    return Hive.openBox(name, encryptionCipher: HiveAesCipher(encryptionKey));
  }

  static bool isFileLockError(Object error) {
    final message = error.toString().toLowerCase();
    return message.contains('lock failed') ||
        message.contains('being used by another process') ||
        message.contains('cannot delete file');
  }

  static bool looksLikeCorruptionError(Object error) {
    final message = error.toString().toLowerCase();
    if (message.contains('wrong key')) {
      return false;
    }
    return message.contains('corrupt') ||
        message.contains('crc') ||
        message.contains('invalid header') ||
        message.contains('cannot be decoded') ||
        message.contains('bad state');
  }
}
