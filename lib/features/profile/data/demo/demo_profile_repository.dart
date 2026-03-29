import '../../domain/models/academic_context.dart';
import '../../domain/models/student_profile.dart';
import '../local/profile_store.dart';
import '../repositories/profile_repository.dart';

class DemoProfileRepository implements ProfileRepository {
  DemoProfileRepository({required ProfileStore profileStore})
    : _profileStore = profileStore;

  final ProfileStore _profileStore;

  @override
  Future<StudentProfile?> loadProfile() {
    return _profileStore.readProfile();
  }

  @override
  Future<AcademicContext?> loadAcademicContext() {
    return _profileStore.readAcademicContext();
  }

  @override
  Future<void> saveProfile(StudentProfile profile) async {
    await _profileStore.writeProfile(profile);
    await _profileStore.writeAcademicContext(profile.academicContext);
  }

  @override
  Future<void> saveAcademicContext(AcademicContext context) {
    return _profileStore.writeAcademicContext(context);
  }

  @override
  Future<void> clearProfile() {
    return _profileStore.clear();
  }
}
