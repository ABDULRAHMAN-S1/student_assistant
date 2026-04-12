import '../data/remote/assistant_api_client.dart';

enum AssistantRequestAction { chat, search, feedback, translate }

String localizeAssistantError(
  AssistantApiException error, {
  required bool isArabic,
  required AssistantRequestAction action,
}) {
  switch (error.kind) {
    case AssistantApiErrorKind.network:
      return _networkMessage(isArabic: isArabic, action: action);
    case AssistantApiErrorKind.timeout:
      return _timeoutMessage(isArabic: isArabic, action: action);
    case AssistantApiErrorKind.rateLimited:
      return isArabic
          ? 'تم إرسال طلبات كثيرة خلال وقت قصير. انتظر قليلاً ثم حاول مرة أخرى.'
          : 'Too many requests were sent in a short time. Please wait a moment and try again.';
    case AssistantApiErrorKind.invalidResponse:
      return isArabic
          ? 'رد الخادم غير صالح حالياً. حاول مرة أخرى بعد قليل.'
          : 'The server returned an invalid response. Please try again shortly.';
    case AssistantApiErrorKind.unauthorized:
    case AssistantApiErrorKind.authenticationRequired:
    case AssistantApiErrorKind.sessionExpired:
      return isArabic
          ? 'انتهت الجلسة. سجل الدخول مرة أخرى للمتابعة.'
          : 'Your session has expired. Sign in again to continue.';
    case AssistantApiErrorKind.translationUnavailable:
      return isArabic
          ? 'خدمة الترجمة غير متاحة حالياً.'
          : 'Translation is not available right now.';
    case AssistantApiErrorKind.validation:
      return error.message;
    case AssistantApiErrorKind.server:
      return _serverMessage(isArabic: isArabic, action: action);
    case AssistantApiErrorKind.unknown:
      return localizeUnexpectedAssistantError(
        isArabic: isArabic,
        action: action,
      );
  }
}

String localizeUnexpectedAssistantError({
  required bool isArabic,
  required AssistantRequestAction action,
}) {
  switch (action) {
    case AssistantRequestAction.chat:
      return isArabic
          ? 'تعذر الاتصال بالمساعد الآن. حاول مرة أخرى.'
          : 'Could not reach the assistant right now. Please try again.';
    case AssistantRequestAction.search:
      return isArabic
          ? 'تعذر تنفيذ البحث الآن.'
          : 'Could not complete the search right now.';
    case AssistantRequestAction.feedback:
      return isArabic
          ? 'تعذر إرسال التقييم الآن.'
          : 'Could not send feedback right now.';
    case AssistantRequestAction.translate:
      return isArabic
          ? 'تعذر ترجمة هذه الرسالة الآن.'
          : 'Could not translate this message right now.';
  }
}

String _networkMessage({
  required bool isArabic,
  required AssistantRequestAction action,
}) {
  switch (action) {
    case AssistantRequestAction.chat:
      return isArabic
          ? 'تعذر الوصول إلى الخادم الآن. تأكد من تشغيل الـ backend ثم حاول مرة أخرى.'
          : 'Could not reach the server. Make sure the backend is running, then try again.';
    case AssistantRequestAction.search:
      return isArabic
          ? 'تعذر الوصول إلى خدمة البحث في المصادر الرسمية.'
          : 'Could not reach the official source search service.';
    case AssistantRequestAction.feedback:
      return isArabic
          ? 'تعذر الوصول إلى الخادم لإرسال التقييم.'
          : 'Could not reach the server to submit feedback.';
    case AssistantRequestAction.translate:
      return isArabic
          ? 'تعذر الوصول إلى خدمة الترجمة حالياً.'
          : 'Could not reach the translation service right now.';
  }
}

String _timeoutMessage({
  required bool isArabic,
  required AssistantRequestAction action,
}) {
  switch (action) {
    case AssistantRequestAction.chat:
      return isArabic
          ? 'استغرقت إجابة المساعد وقتاً أطول من المتوقع. حاول مرة أخرى.'
          : 'The assistant took too long to respond. Please try again.';
    case AssistantRequestAction.search:
      return isArabic
          ? 'استغرق البحث وقتاً أطول من المتوقع. حاول مرة أخرى.'
          : 'The search request took too long. Please try again.';
    case AssistantRequestAction.feedback:
      return isArabic
          ? 'استغرق إرسال التقييم وقتاً أطول من المتوقع.'
          : 'Submitting feedback took too long. Please try again.';
    case AssistantRequestAction.translate:
      return isArabic
          ? 'استغرقت الترجمة وقتاً أطول من المتوقع. حاول مرة أخرى.'
          : 'Translation took too long. Please try again.';
  }
}

String _serverMessage({
  required bool isArabic,
  required AssistantRequestAction action,
}) {
  switch (action) {
    case AssistantRequestAction.chat:
      return isArabic
          ? 'الخادم واجه مشكلة أثناء تجهيز الرد. حاول مرة أخرى بعد قليل.'
          : 'The server hit an error while preparing the answer. Please try again shortly.';
    case AssistantRequestAction.search:
      return isArabic
          ? 'الخادم واجه مشكلة أثناء تنفيذ البحث.'
          : 'The server hit an error while running the search.';
    case AssistantRequestAction.feedback:
      return isArabic
          ? 'الخادم واجه مشكلة أثناء حفظ التقييم.'
          : 'The server hit an error while saving the feedback.';
    case AssistantRequestAction.translate:
      return isArabic
          ? 'الخادم واجه مشكلة أثناء ترجمة الرسالة.'
          : 'The server hit an error while translating the message.';
  }
}
