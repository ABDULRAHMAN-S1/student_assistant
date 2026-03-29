import '../data/remote/auth_api_client.dart';

String localizeAuthError(
  AuthApiException error, {
  required bool isArabic,
  required bool isRegistration,
}) {
  switch (error.kind) {
    case AuthApiErrorKind.network:
      return isArabic
          ? 'تعذر الوصول إلى الخادم. تأكد من تشغيل الـ backend ثم حاول مرة أخرى.'
          : 'Could not reach the server. Make sure the backend is running, then try again.';
    case AuthApiErrorKind.timeout:
      return isArabic
          ? 'انتهت مهلة الاتصال بالخادم. حاول مرة أخرى بعد قليل.'
          : 'The server took too long to respond. Please try again shortly.';
    case AuthApiErrorKind.invalidResponse:
      return isArabic
          ? 'رد الخادم غير صالح حالياً. تحقق من إعدادات الخادم.'
          : 'The server returned an invalid response. Check the backend configuration.';
    case AuthApiErrorKind.conflict:
      return isRegistration
          ? (isArabic
                ? 'هذا البريد مستخدم بالفعل. جرّب تسجيل الدخول أو استخدم بريداً آخر.'
                : 'This email is already in use. Try signing in or use a different email.')
          : error.message;
    case AuthApiErrorKind.unauthorized:
      return isRegistration
          ? error.message
          : (isArabic
                ? 'بيانات الدخول غير صحيحة. تحقق من البريد وكلمة المرور.'
                : 'Incorrect credentials. Check your email and password.');
    case AuthApiErrorKind.validation:
      return error.message;
    case AuthApiErrorKind.server:
      return isArabic
          ? 'الخادم واجه مشكلة داخلية. حاول مرة أخرى بعد قليل.'
          : 'The server hit an internal error. Please try again shortly.';
    case AuthApiErrorKind.unknown:
      return error.message;
  }
}

String localizeUnexpectedAuthError({
  required bool isArabic,
  required bool isRegistration,
}) {
  if (isRegistration) {
    return isArabic
        ? 'تعذر إنشاء الحساب حالياً.'
        : 'Could not create the account right now.';
  }
  return isArabic
      ? 'تعذر تسجيل الدخول حالياً.'
      : 'Could not sign in right now.';
}
