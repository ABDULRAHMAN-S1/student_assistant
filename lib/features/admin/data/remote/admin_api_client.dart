import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../../../../app/api_base_url.dart';
import '../../../../app/app_settings_store.dart';
import '../../../auth/data/remote/auth_api_client.dart';
import '../../../auth/domain/models/auth_session.dart';
import '../../domain/models/admin_user.dart';

enum AdminApiErrorKind {
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

class AdminApiException implements Exception {
  const AdminApiException(
    this.message, {
    this.kind = AdminApiErrorKind.unknown,
    this.statusCode,
  });

  final String message;
  final AdminApiErrorKind kind;
  final int? statusCode;

  @override
  String toString() => message;
}

class AdminApiClient {
  const AdminApiClient();

  Future<List<AdminUser>> listUsers() async {
    final payload = await _authorizedRequest('GET', '/users');
    if (payload is! Map<String, dynamic>) {
      throw const AdminApiException(
        'Invalid users response.',
        kind: AdminApiErrorKind.invalidResponse,
      );
    }

    final users = payload['users'];
    if (users is! List) {
      throw const AdminApiException(
        'Invalid users response.',
        kind: AdminApiErrorKind.invalidResponse,
      );
    }

    return users
        .whereType<Map<String, dynamic>>()
        .map(AdminUser.fromJson)
        .toList(growable: false);
  }

  Future<AdminUser> updateUserRole({
    required String userId,
    required String role,
  }) async {
    final payload = await _authorizedRequest(
      'PATCH',
      '/users/$userId/role',
      body: {'role': role},
    );
    if (payload is! Map<String, dynamic>) {
      throw const AdminApiException(
        'Invalid role update response.',
        kind: AdminApiErrorKind.invalidResponse,
      );
    }

    final user = payload['user'];
    if (user is! Map<String, dynamic>) {
      throw const AdminApiException(
        'Invalid role update response.',
        kind: AdminApiErrorKind.invalidResponse,
      );
    }

    return AdminUser.fromJson(user);
  }

  Future<dynamic> _authorizedRequest(
    String method,
    String path, {
    Map<String, Object?>? body,
  }) async {
    var session = await _prepareSession();
    var response = await _sendRequest(
      method,
      path,
      body: body,
      session: session,
    );

    if (response.statusCode == 401 && !session.isRefreshExpired) {
      session = await _refreshSession(session);
      response = await _sendRequest(method, path, body: body, session: session);
    }

    if (response.statusCode == 401) {
      await _clearStoredSession();
      throw const AdminApiException(
        'Session expired. Please sign in again.',
        kind: AdminApiErrorKind.sessionExpired,
        statusCode: 401,
      );
    }

    final payload = _decodePayload(response);
    if (response.statusCode != 200) {
      throw AdminApiException(
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
    Map<String, Object?>? body,
    required AuthSession session,
  }) async {
    try {
      final headers = {
        'Accept': 'application/json',
        'Authorization': 'Bearer ${session.accessToken}',
        if (body != null) 'Content-Type': 'application/json',
      };

      switch (method) {
        case 'GET':
          return await http
              .get(buildApiUri(path), headers: headers)
              .timeout(const Duration(seconds: 25));
        case 'PATCH':
          return await http
              .patch(
                buildApiUri(path),
                headers: headers,
                body: jsonEncode(body ?? const <String, Object?>{}),
              )
              .timeout(const Duration(seconds: 25));
        default:
          throw StateError('Unsupported method: $method');
      }
    } on TimeoutException {
      throw const AdminApiException(
        'Request timed out.',
        kind: AdminApiErrorKind.timeout,
      );
    } on SocketException {
      throw const AdminApiException(
        'Could not connect to the server.',
        kind: AdminApiErrorKind.network,
      );
    } on http.ClientException {
      throw const AdminApiException(
        'Could not connect to the server.',
        kind: AdminApiErrorKind.network,
      );
    }
  }

  Future<AuthSession> _prepareSession() async {
    final settingsStore = await AppSettingsStore.open();
    final session = settingsStore.readAuthSession();
    if (session == null) {
      throw const AdminApiException(
        'Authentication required.',
        kind: AdminApiErrorKind.authenticationRequired,
      );
    }
    if (!session.isAccessExpired) {
      return session;
    }
    if (session.isRefreshExpired) {
      await settingsStore.clearAuthSession();
      throw const AdminApiException(
        'Session expired. Please sign in again.',
        kind: AdminApiErrorKind.sessionExpired,
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
        throw const AdminApiException(
          'Session expired. Please sign in again.',
          kind: AdminApiErrorKind.sessionExpired,
          statusCode: 401,
        );
      }

      throw AdminApiException(
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
      // Surface the original error when local settings are not available.
    }
  }

  dynamic _decodePayload(http.Response response) {
    if (response.body.isEmpty) {
      return null;
    }

    try {
      return jsonDecode(utf8.decode(response.bodyBytes));
    } on FormatException {
      throw const AdminApiException(
        'Invalid server response.',
        kind: AdminApiErrorKind.invalidResponse,
      );
    }
  }

  bool _isRejectedRefresh(AuthApiException error) {
    return error.kind == AuthApiErrorKind.unauthorized ||
        error.kind == AuthApiErrorKind.validation;
  }

  AdminApiErrorKind _mapAuthErrorKind(AuthApiErrorKind kind) {
    switch (kind) {
      case AuthApiErrorKind.network:
        return AdminApiErrorKind.network;
      case AuthApiErrorKind.timeout:
        return AdminApiErrorKind.timeout;
      case AuthApiErrorKind.invalidResponse:
        return AdminApiErrorKind.invalidResponse;
      case AuthApiErrorKind.unauthorized:
        return AdminApiErrorKind.sessionExpired;
      case AuthApiErrorKind.validation:
        return AdminApiErrorKind.validation;
      case AuthApiErrorKind.server:
        return AdminApiErrorKind.server;
      case AuthApiErrorKind.conflict:
      case AuthApiErrorKind.unknown:
        return AdminApiErrorKind.unknown;
    }
  }

  AdminApiErrorKind _errorKindForStatusCode(int statusCode) {
    if (statusCode == 400 || statusCode == 422) {
      return AdminApiErrorKind.validation;
    }
    if (statusCode == 401 || statusCode == 403) {
      return AdminApiErrorKind.unauthorized;
    }
    if (statusCode >= 500) {
      return AdminApiErrorKind.server;
    }
    return AdminApiErrorKind.unknown;
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
