import 'package:flutter/foundation.dart';

const String _configuredBaseUrl = String.fromEnvironment(
  'AI_CHAT_API_BASE_URL',
);

String resolveApiBaseUrl() {
  final configured = _configuredBaseUrl.trim();
  final baseUrl = configured.isNotEmpty
      ? configured
      : kIsWeb
      ? 'http://localhost:8000'
      : defaultTargetPlatform == TargetPlatform.android
      ? 'http://10.0.2.2:8000'
      : 'http://127.0.0.1:8000';

  final normalized = baseUrl.replaceFirst(RegExp(r'/$'), '');
  final uri = Uri.parse(normalized);
  if (kReleaseMode && uri.scheme.toLowerCase() != 'https') {
    throw StateError(
      'Release builds require an HTTPS API base URL. Configure AI_CHAT_API_BASE_URL with an https:// origin.',
    );
  }
  return normalized;
}

Uri buildApiUri(String path) {
  final normalizedPath = path.startsWith('/') ? path : '/$path';
  return Uri.parse('${resolveApiBaseUrl()}$normalizedPath');
}
