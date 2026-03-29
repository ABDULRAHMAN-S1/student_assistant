import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'dart:typed_data';

import 'package:path_provider/path_provider.dart';

class LocalEncryptionKeyProvider {
  LocalEncryptionKeyProvider._();

  static const String _storageFileName = 'student_assistant_hive_key.txt';
  static final LocalEncryptionKeyProvider instance =
      LocalEncryptionKeyProvider._();

  static Uint8List? _testOverride;
  List<int>? _cachedKey;

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

    final keyFile = await _resolveKeyFile();
    if (await keyFile.exists()) {
      final existing = (await keyFile.readAsString()).trim();
      if (existing.isNotEmpty) {
        final decoded = base64Decode(existing);
        if (decoded.length == 32) {
          _cachedKey = decoded;
          return decoded;
        }
      }
    }

    final generated = _generateKey();
    await keyFile.parent.create(recursive: true);
    await keyFile.writeAsString(base64Encode(generated), flush: true);
    _cachedKey = generated;
    return generated;
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
