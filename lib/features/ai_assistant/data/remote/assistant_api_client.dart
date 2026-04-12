import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../../../../app/api_base_url.dart';
import '../../../../app/app_settings_store.dart';
import '../../../auth/data/remote/auth_api_client.dart';
import '../../../auth/domain/models/auth_session.dart';
import '../../domain/models/assistant_reply.dart';
import '../../domain/models/regulation_source.dart';

enum AssistantApiErrorKind {
  unknown,
  network,
  timeout,
  rateLimited,
  invalidResponse,
  unauthorized,
  authenticationRequired,
  sessionExpired,
  translationUnavailable,
  validation,
  server,
}

class AssistantApiException implements Exception {
  const AssistantApiException(
    this.message, {
    this.kind = AssistantApiErrorKind.unknown,
    this.statusCode,
  });

  final String message;
  final AssistantApiErrorKind kind;
  final int? statusCode;

  @override
  String toString() => message;
}

class AssistantApiClient {
  const AssistantApiClient();

  static Future<AuthSession>? _inFlightRefresh;

  Future<AssistantReply> ask(String message) async {
    final response = await _postAuthorized(
      '/chat',
      body: {'question': message},
    );

    if (response is! Map<String, dynamic>) {
      throw const FormatException('Invalid server response.');
    }

    return AssistantReply.fromJson(response);
  }

  Future<List<RegulationSource>> searchRegulations(
    String query, {
    int topK = 6,
  }) async {
    final response = await _postAuthorized(
      '/search',
      body: {'query': query, 'top_k': topK},
    );

    if (response is! Map<String, dynamic>) {
      throw const FormatException('Invalid server response.');
    }

    return RegulationSource.listFromJson(response['results']);
  }

  Future<void> sendFeedback({
    required String question,
    required String answer,
    required bool helpful,
    required String language,
    required List<RegulationSource> sources,
    String reason = '',
    String routeMode = '',
  }) async {
    await _postAuthorized(
      '/feedback',
      body: {
        'question': question,
        'answer': answer,
        'helpful': helpful,
        'language': language,
        'sources': sources.map((item) => item.toJson()).toList(growable: false),
        'reason': reason,
        'route_mode': routeMode,
      },
    );
  }

  Future<Map<String, dynamic>> translateMessage(String text) async {
    final response = await _postAuthorized('/translate', body: {'text': text});
    if (response is! Map<String, dynamic>) {
      throw const FormatException('Invalid translation response.');
    }
    return response;
  }

  Future<dynamic> _postAuthorized(
    String path, {
    required Map<String, Object?> body,
  }) async {
    var session = await _prepareSession();
    var response = await _sendRequest(path, body: body, session: session);

    if (response.statusCode == 401 && !session.isRefreshExpired) {
      session = await _refreshSession(session);
      response = await _sendRequest(path, body: body, session: session);
    }

    if (response.statusCode == 401) {
      await _clearStoredSession();
      throw const AssistantApiException(
        'Session expired. Please sign in again.',
        kind: AssistantApiErrorKind.sessionExpired,
        statusCode: 401,
      );
    }

    final payload = _decodePayload(response);
    if (response.statusCode != 200) {
      throw AssistantApiException(
        _extractErrorMessage(payload, response.statusCode),
        kind: _errorKindForStatusCode(response.statusCode, payload),
        statusCode: response.statusCode,
      );
    }

    return payload;
  }

  Future<http.Response> _sendRequest(
    String path, {
    required Map<String, Object?> body,
    required AuthSession session,
  }) async {
    try {
      return await http
          .post(
            buildApiUri(path),
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
              'Authorization': 'Bearer ${session.accessToken}',
            },
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 25));
    } on TimeoutException {
      throw const AssistantApiException(
        'Request timed out.',
        kind: AssistantApiErrorKind.timeout,
      );
    } on SocketException {
      throw const AssistantApiException(
        'Could not connect to the server.',
        kind: AssistantApiErrorKind.network,
      );
    } on http.ClientException {
      throw const AssistantApiException(
        'Could not connect to the server.',
        kind: AssistantApiErrorKind.network,
      );
    }
  }

  Future<AuthSession> _prepareSession() async {
    final settingsStore = await AppSettingsStore.open();
    final session = settingsStore.readAuthSession();
    if (session == null) {
      throw const AssistantApiException(
        'Authentication required.',
        kind: AssistantApiErrorKind.authenticationRequired,
      );
    }
    if (!session.isAccessExpired) {
      return session;
    }
    if (session.isRefreshExpired) {
      await settingsStore.clearAuthSession();
      throw const AssistantApiException(
        'Session expired. Please sign in again.',
        kind: AssistantApiErrorKind.sessionExpired,
      );
    }
    return _refreshSession(session);
  }

  Future<AuthSession> _refreshSession(AuthSession session) async {
    Future<AuthSession> doRefresh() async {
      final refreshed = await const AuthApiClient().refreshSession(
        session.refreshToken,
      );
      final settingsStore = await AppSettingsStore.open();
      await settingsStore.writeAuthSession(refreshed);
      return refreshed;
    }

    try {
      final future = _inFlightRefresh ??= doRefresh().whenComplete(
        () => _inFlightRefresh = null,
      );
      return await future;
    } on AuthApiException catch (error) {
      if (_isRejectedRefresh(error)) {
        await _clearStoredSession();
        throw const AssistantApiException(
          'Session expired. Please sign in again.',
          kind: AssistantApiErrorKind.sessionExpired,
          statusCode: 401,
        );
      }

      throw AssistantApiException(
        error.message,
        kind: _mapAuthErrorKind(error.kind),
        statusCode: error.statusCode,
      );
    }
  }

  Future<void> _clearStoredSession() async {
    try {
      final settingsStore = await AppSettingsStore.open();
      await settingsStore.clearAuthSession();
    } catch (_) {
      // If local settings cannot be opened here, surfacing the original error is enough.
    }
  }

  dynamic _decodePayload(http.Response response) {
    if (response.body.isEmpty) {
      return null;
    }

    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const AssistantApiException(
        'Invalid server response.',
        kind: AssistantApiErrorKind.invalidResponse,
      );
    }
  }

  bool _isRejectedRefresh(AuthApiException error) {
    return error.kind == AuthApiErrorKind.unauthorized ||
        error.kind == AuthApiErrorKind.validation;
  }

  AssistantApiErrorKind _mapAuthErrorKind(AuthApiErrorKind kind) {
    switch (kind) {
      case AuthApiErrorKind.network:
        return AssistantApiErrorKind.network;
      case AuthApiErrorKind.timeout:
        return AssistantApiErrorKind.timeout;
      case AuthApiErrorKind.invalidResponse:
        return AssistantApiErrorKind.invalidResponse;
      case AuthApiErrorKind.unauthorized:
        return AssistantApiErrorKind.sessionExpired;
      case AuthApiErrorKind.validation:
        return AssistantApiErrorKind.validation;
      case AuthApiErrorKind.server:
        return AssistantApiErrorKind.server;
      case AuthApiErrorKind.conflict:
      case AuthApiErrorKind.unknown:
        return AssistantApiErrorKind.unknown;
    }
  }

  AssistantApiErrorKind _errorKindForStatusCode(
    int statusCode,
    dynamic payload,
  ) {
    if (statusCode == 400 || statusCode == 422) {
      return AssistantApiErrorKind.validation;
    }
    if (statusCode == 429) {
      return AssistantApiErrorKind.rateLimited;
    }
    if (statusCode == 401 || statusCode == 403) {
      return AssistantApiErrorKind.unauthorized;
    }
    if (statusCode == 503 &&
        _extractErrorCode(payload) == 'translation_unavailable') {
      return AssistantApiErrorKind.translationUnavailable;
    }
    if (statusCode >= 500) {
      return AssistantApiErrorKind.server;
    }
    return AssistantApiErrorKind.unknown;
  }

  String _extractErrorCode(dynamic payload) {
    if (payload is Map<String, dynamic>) {
      final error = payload['error'];
      if (error is Map<String, dynamic>) {
        return (error['code'] ?? '').toString().trim();
      }
    }
    return '';
  }

  String _extractErrorMessage(dynamic payload, int statusCode) {
    if (payload is Map<String, dynamic>) {
      final error = payload['error'];
      if (error is Map<String, dynamic>) {
        final message = (error['message'] ?? '').toString().trim();
        if (message.isNotEmpty) {
          return message;
        }
      }

      final message = (payload['message'] ?? '').toString().trim();
      if (message.isNotEmpty) {
        return message;
      }

      final detail = payload['detail'];
      if (detail != null && detail.toString().trim().isNotEmpty) {
        return detail.toString();
      }
    }

    return 'Server $statusCode';
  }
}
