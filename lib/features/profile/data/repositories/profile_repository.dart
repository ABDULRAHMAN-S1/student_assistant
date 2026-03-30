import '../../domain/models/academic_context.dart';
import '../../domain/models/student_profile.dart';

abstract class ProfileRepository {
  Future<StudentProfile?> loadProfile();

  Future<AcademicContext?> loadAcademicContext();

  Future<void> saveProfile(StudentProfile profile);

  Future<void> saveAcademicContext(AcademicContext context);

  Future<void> clearProfile();
}
