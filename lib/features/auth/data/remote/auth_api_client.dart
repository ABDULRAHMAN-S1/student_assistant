import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../../../../app/api_base_url.dart';
import '../../domain/models/auth_session.dart';

enum AuthApiErrorKind {
  unknown,
  network,
  timeout,
  invalidResponse,
  unauthorized,
  conflict,
  validation,
  server,
}

class AuthApiException implements Exception {
  const AuthApiException(
    this.message, {
    this.kind = AuthApiErrorKind.unknown,
    this.statusCode,
  });

  final String message;
  final AuthApiErrorKind kind;
  final int? statusCode;

  @override
  String toString() => message;
}

class AuthApiClient {
  const AuthApiClient();

  Future<AuthSession> login({required String email, required String password}) {
    return _authenticate(
      '/auth/login',
      body: {'email': email, 'password': password},
    );
  }

  Future<AuthSession> register({
    required String email,
    required String password,
    required String fullName,
  }) {
    return _authenticate(
      '/auth/register',
      body: {'email': email, 'password': password, 'full_name': fullName},
    );
  }

  Future<AuthSession> refreshSession(String refreshToken) {
    return _authenticate(
      '/auth/refresh',
      body: {'refresh_token': refreshToken},
    );
  }

  Future<AuthSession> _authenticate(
    String path, {
    required Map<String, Object?> body,
  }) async {
    late final http.Response response;
    try {
      response = await http
          .post(
            buildApiUri(path),
            headers: const {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
            body: jsonEncode(body),
          )
          .timeout(const Duration(seconds: 25));
    } on TimeoutException {
      throw const AuthApiException(
        'Request timed out.',
        kind: AuthApiErrorKind.timeout,
      );
    } on SocketException {
      throw const AuthApiException(
        'Could not connect to the server.',
        kind: AuthApiErrorKind.network,
      );
    } on http.ClientException {
      throw const AuthApiException(
        'Could not connect to the server.',
        kind: AuthApiErrorKind.network,
      );
    }

    dynamic payload;
    if (response.body.isNotEmpty) {
      try {
        payload = jsonDecode(utf8.decode(response.bodyBytes));
      } on FormatException {
        throw const AuthApiException(
          'Invalid authentication response.',
          kind: AuthApiErrorKind.invalidResponse,
        );
      }
    }

    if (response.statusCode != 200) {
      throw AuthApiException(
        _extractErrorMessage(payload, response.statusCode),
        kind: _errorKindForStatusCode(response.statusCode),
        statusCode: response.statusCode,
      );
    }

    if (payload is! Map<String, dynamic>) {
      throw const AuthApiException(
        'Invalid authentication response.',
        kind: AuthApiErrorKind.invalidResponse,
      );
    }

    return AuthSession.fromJson(payload);
  }

  AuthApiErrorKind _errorKindForStatusCode(int statusCode) {
    if (statusCode == 400 || statusCode == 422) {
      return AuthApiErrorKind.validation;
    }
    if (statusCode == 401 || statusCode == 403) {
      return AuthApiErrorKind.unauthorized;
    }
    if (statusCode == 409) {
      return AuthApiErrorKind.conflict;
    }
    if (statusCode >= 500) {
      return AuthApiErrorKind.server;
    }
    return AuthApiErrorKind.unknown;
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

    return 'Authentication failed ($statusCode).';
  }
}
