import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:path_provider/path_provider.dart';

class LocalEncryptionKeyProvider {
  LocalEncryptionKeyProvider._();

  static const String _storageFileName = 'student_assistant_hive_key.txt';
  static const String _secureStorageKeyName = 'student_assistant_hive_key_v1';
  static final LocalEncryptionKeyProvider instance =
      LocalEncryptionKeyProvider._();

  static Uint8List? _testOverride;
  List<int>? _cachedKey;
  final FlutterSecureStorage _secureStorage = const FlutterSecureStorage();

  static void setTestKey(Uint8List? key) {
    _testOverride = key;
  }

  Future<List<int>> getKey() async {
    if (_testOverride != null) {
      return _testOverride!;
    }

    if (_cachedKey != null) {
      return _cachedKey!;
    }

    final stored = await _readFromSecureStorage();
    if (stored != null && stored.length == 32) {
      _cachedKey = stored;
      await _attemptRemoveLegacyFileKey();
      return stored;
    }

    final keyFile = await _resolveKeyFile();
    if (await keyFile.exists()) {
      final existing = (await keyFile.readAsString()).trim();
      if (existing.isNotEmpty) {
        final decoded = base64Decode(existing);
        if (decoded.length == 32) {
          await _writeToSecureStorage(decoded);
          await _attemptRemoveLegacyFileKey();
          _cachedKey = decoded;
          return decoded;
        }
      }
    }

    final generated = _generateKey();
    final storedInSecureStorage = await _writeToSecureStorage(generated);
    if (!storedInSecureStorage) {
      // Fallback only when platform secure storage is unavailable.
      await keyFile.parent.create(recursive: true);
      await keyFile.writeAsString(base64Encode(generated), flush: true);
    }
    _cachedKey = generated;
    return generated;
  }

  Future<List<int>?> _readFromSecureStorage() async {
    try {
      final value = await _secureStorage.read(key: _secureStorageKeyName);
      if (value == null || value.trim().isEmpty) {
        return null;
      }
      return base64Decode(value.trim());
    } catch (_) {
      return null;
    }
  }

  Future<bool> _writeToSecureStorage(List<int> keyBytes) async {
    try {
      await _secureStorage.write(
        key: _secureStorageKeyName,
        value: base64Encode(keyBytes),
      );
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<void> _attemptRemoveLegacyFileKey() async {
    try {
      final file = await _resolveKeyFile();
      if (await file.exists()) {
        await file.delete();
      }
    } catch (_) {
      // Best-effort cleanup only.
    }
  }

  Future<File> _resolveKeyFile() async {
    final appSupportDirectory = await getApplicationSupportDirectory();
    return File(
      '${appSupportDirectory.path}${Platform.pathSeparator}$_storageFileName',
    );
  }

  List<int> _generateKey() {
    final random = Random.secure();
    return List<int>.generate(32, (_) => random.nextInt(256), growable: false);
  }
}
