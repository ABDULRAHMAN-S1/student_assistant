import 'package:hive_flutter/hive_flutter.dart';

import '../../../../app/local_encryption_key_provider.dart';
import '../../domain/models/academic_context.dart';
import '../../domain/models/student_profile.dart';

class ProfileStore {
  ProfileStore._(this._box);

  factory ProfileStore.fromBox(Box box) {
    return ProfileStore._(box);
  }

  static const String boxName = 'student_profile';
  static const String profileKey = 'current_profile';
  static const String academicContextKey = 'academic_context';

  final Box _box;

  static Future<ProfileStore> open() async {
    if (!Hive.isBoxOpen(boxName)) {
      await _openEncryptedBox(boxName);
    }
    return ProfileStore._(Hive.box(boxName));
  }

  static Future<void> _openEncryptedBox(String name) async {
    final encryptionKey = await LocalEncryptionKeyProvider.instance.getKey();
    try {
      await Hive.openBox(name, encryptionCipher: HiveAesCipher(encryptionKey));
    } catch (error) {
      if (_isFileLockError(error)) {
        rethrow;
      }
      await Hive.deleteBoxFromDisk(name);
      await Hive.openBox(name, encryptionCipher: HiveAesCipher(encryptionKey));
    }
  }

  static bool _isFileLockError(Object error) {
    final message = error.toString().toLowerCase();
    return message.contains('lock failed') ||
        message.contains('being used by another process') ||
        message.contains('cannot delete file');
  }

  Future<StudentProfile?> readProfile() async {
    final raw = _box.get(profileKey);
    if (raw is! Map) {
      return null;
    }
    return StudentProfile.fromJson(Map<String, dynamic>.from(raw));
  }

  Future<AcademicContext?> readAcademicContext() async {
    final raw = _box.get(academicContextKey);
    if (raw is! Map) {
      return null;
    }
    return AcademicContext.fromJson(Map<String, dynamic>.from(raw));
  }

  Future<void> writeProfile(StudentProfile profile) {
    return _box.put(profileKey, profile.toJson());
  }

  Future<void> writeAcademicContext(AcademicContext context) {
    return _box.put(academicContextKey, context.toJson());
  }

  Future<void> clear() async {
    await _box.delete(profileKey);
    await _box.delete(academicContextKey);
  }
}
