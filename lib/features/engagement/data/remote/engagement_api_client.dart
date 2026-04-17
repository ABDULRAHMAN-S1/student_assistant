import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../../../../app/api_base_url.dart';
import '../../../../app/app_settings_store.dart';
import '../../../auth/data/remote/auth_api_client.dart';
import '../../../auth/domain/models/auth_session.dart';
import '../../domain/models/engagement_feed.dart';
import '../../domain/models/student_engagement_profile.dart';
import '../repositories/engagement_repository.dart';
import 'map_feed_response.dart';

enum EngagementApiErrorKind {
  unknown,
  network,
  timeout,
  invalidResponse,
  unauthorized,
  authenticationRequired,
  sessionExpired,
  validation,
  server,
}

class EngagementApiException implements Exception {
  const EngagementApiException(
    this.message, {
    this.kind = EngagementApiErrorKind.unknown,
    this.statusCode,
  });

  final String message;
  final EngagementApiErrorKind kind;
  final int? statusCode;

  @override
  String toString() => message;
}

class EngagementApiClient implements EngagementRepository {
  const EngagementApiClient();

  @override
  Future<int> generateNotifications({int limit = 20}) async {
    final payload = await _authorizedRequest(
      'POST',
      '/engagement/notifications/generate',
      query: {'limit': limit.toString()},
    );
    if (payload is! Map<String, dynamic>) {
      return 0;
    }
    return (payload['generated_count'] as num?)?.toInt() ?? 0;
  }

  @override
  Future<EngagementFeed> getFeed({
    bool includeRead = false,
    int limit = 20,
  }) async {
    final payload = await _authorizedRequest(
      'GET',
      '/engagement/feed',
      query: {
        'include_read': includeRead ? 'true' : 'false',
        'limit': limit.toString(),
      },
    );
    if (payload is! Map<String, dynamic>) {
      throw const EngagementApiException(
        'Invalid engagement feed response.',
        kind: EngagementApiErrorKind.invalidResponse,
      );
    }
    return mapFeedResponse(payload);
  }

  @override
  Future<void> markNotificationRead(String notificationId) async {
    await _authorizedRequest(
      'PATCH',
      '/engagement/notifications/$notificationId/read',
    );
  }

  @override
  Future<StudentEngagementProfile> getProfile() async {
    final payload = await _authorizedRequest('GET', '/engagement/profile');
    if (payload is! Map<String, dynamic>) {
      throw const EngagementApiException(
        'Invalid profile response.',
        kind: EngagementApiErrorKind.invalidResponse,
      );
    }
    final profile = payload['profile'];
    if (profile is! Map<String, dynamic>) {
      throw const EngagementApiException(
        'Invalid profile response.',
        kind: EngagementApiErrorKind.invalidResponse,
      );
    }
    return mapEngagementProfile(profile);
  }

  @override
  Future<StudentEngagementProfile> updateProfile({
    required String major,
    required String academicLevel,
    required String track,
    required List<String> interests,
  }) async {
    final payload = await _authorizedRequest(
      'PUT',
      '/engagement/profile',
      body: {
        'major': major,
        'academic_level': academicLevel,
        'track': track,
        'interests': interests,
      },
    );
    if (payload is! Map<String, dynamic>) {
      throw const EngagementApiException(
        'Invalid profile update response.',
        kind: EngagementApiErrorKind.invalidResponse,
      );
    }
    final profile = payload['profile'];
    if (profile is! Map<String, dynamic>) {
      throw const EngagementApiException(
        'Invalid profile update response.',
        kind: EngagementApiErrorKind.invalidResponse,
      );
    }
    return mapEngagementProfile(profile);
  }

  Future<dynamic> _authorizedRequest(
    String method,
    String path, {
    Map<String, Object?>? body,
    Map<String, String>? query,
  }) async {
    var session = await _prepareSession();
    var response = await _sendRequest(
      method,
      path,
      body: body,
      query: query,
      session: session,
    );

    if (response.statusCode == 401 && !session.isRefreshExpired) {
      session = await _refreshSession(session);
      response = await _sendRequest(
        method,
        path,
        body: body,
        query: query,
        session: session,
      );
    }

    if (response.statusCode == 401) {
      await _clearStoredSession();
      throw const EngagementApiException(
        'Session expired. Please sign in again.',
        kind: EngagementApiErrorKind.sessionExpired,
        statusCode: 401,
      );
    }

    final payload = _decodePayload(response);
    if (response.statusCode != 200) {
      throw EngagementApiException(
        _extractErrorMessage(payload, response.statusCode),
        kind: _errorKindForStatusCode(response.statusCode),
        statusCode: response.statusCode,
      );
    }
    return payload;
  }

  Future<http.Response> _sendRequest(
    String method,
    String path, {
    required AuthSession session,
    Map<String, Object?>? body,
    Map<String, String>? query,
  }) async {
    try {
      final headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ${session.accessToken}',
        if (body != null) 'Content-Type': 'application/json',
      };
      final uri = buildApiUri(path).replace(queryParameters: query);
      switch (method) {
        case 'GET':
          return await http
              .get(uri, headers: headers)
              .timeout(const Duration(seconds: 25));
        case 'POST':
          return await http
              .post(
                uri,
                headers: headers,
                body: jsonEncode(body ?? const <String, Object?>{}),
              )
              .timeout(const Duration(seconds: 25));
        case 'PUT':
          return await http
              .put(
                uri,
                headers: headers,
                body: jsonEncode(body ?? const <String, Object?>{}),
              )
              .timeout(const Duration(seconds: 25));
        case 'PATCH':
          return await http
              .patch(
                uri,
                headers: headers,
                body: jsonEncode(body ?? const <String, Object?>{}),
              )
              .timeout(const Duration(seconds: 25));
        default:
          throw StateError('Unsupported method: $method');
      }
    } on TimeoutException {
      throw const EngagementApiException(
        'Request timed out.',
        kind: EngagementApiErrorKind.timeout,
      );
    } on SocketException {
      throw const EngagementApiException(
        'Could not connect to the server.',
        kind: EngagementApiErrorKind.network,
      );
    } on http.ClientException {
      throw const EngagementApiException(
        'Could not connect to the server.',
        kind: EngagementApiErrorKind.network,
      );
    }
  }

  Future<AuthSession> _prepareSession() async {
    final settingsStore = await AppSettingsStore.open();
    final session = settingsStore.readAuthSession();
    if (session == null) {
      throw const EngagementApiException(
        'Authentication required.',
        kind: EngagementApiErrorKind.authenticationRequired,
      );
    }
    if (!session.isAccessExpired) {
      return session;
    }
    if (session.isRefreshExpired) {
      await settingsStore.clearAuthSession();
      throw const EngagementApiException(
        'Session expired. Please sign in again.',
        kind: EngagementApiErrorKind.sessionExpired,
      );
    }
    return _refreshSession(session);
  }

  Future<AuthSession> _refreshSession(AuthSession session) async {
    try {
      final refreshed = await const AuthApiClient().refreshSession(
        session.refreshToken,
      );
      final settingsStore = await AppSettingsStore.open();
      await settingsStore.writeAuthSession(refreshed);
      return refreshed;
    } on AuthApiException catch (error) {
      if (_isRejectedRefresh(error)) {
        await _clearStoredSession();
        throw const EngagementApiException(
          'Session expired. Please sign in again.',
          kind: EngagementApiErrorKind.sessionExpired,
          statusCode: 401,
        );
      }
      throw EngagementApiException(
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
      // Keep original API failure as primary signal.
    }
  }

  dynamic _decodePayload(http.Response response) {
    if (response.body.isEmpty) {
      return null;
    }
    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const EngagementApiException(
        'Invalid server response.',
        kind: EngagementApiErrorKind.invalidResponse,
      );
    }
  }

  bool _isRejectedRefresh(AuthApiException error) {
    return error.kind == AuthApiErrorKind.unauthorized ||
        error.kind == AuthApiErrorKind.validation;
  }

  EngagementApiErrorKind _mapAuthErrorKind(AuthApiErrorKind kind) {
    switch (kind) {
      case AuthApiErrorKind.network:
        return EngagementApiErrorKind.network;
      case AuthApiErrorKind.timeout:
        return EngagementApiErrorKind.timeout;
      case AuthApiErrorKind.invalidResponse:
        return EngagementApiErrorKind.invalidResponse;
      case AuthApiErrorKind.unauthorized:
        return EngagementApiErrorKind.sessionExpired;
      case AuthApiErrorKind.validation:
        return EngagementApiErrorKind.validation;
      case AuthApiErrorKind.server:
        return EngagementApiErrorKind.server;
      case AuthApiErrorKind.conflict:
      case AuthApiErrorKind.unknown:
        return EngagementApiErrorKind.unknown;
    }
  }

  EngagementApiErrorKind _errorKindForStatusCode(int statusCode) {
    if (statusCode == 400 || statusCode == 422) {
      return EngagementApiErrorKind.validation;
    }
    if (statusCode == 401 || statusCode == 403) {
      return EngagementApiErrorKind.unauthorized;
    }
    if (statusCode >= 500) {
      return EngagementApiErrorKind.server;
    }
    return EngagementApiErrorKind.unknown;
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
      final detail = (payload['detail'] ?? '').toString().trim();
      if (detail.isNotEmpty) {
        return detail;
      }
    }
    return 'Request failed ($statusCode).';
  }
}
