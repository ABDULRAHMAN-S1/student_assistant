class AuthSession {
  const AuthSession({
    required this.accessToken,
    required this.refreshToken,
    required this.accessExpiresAt,
    required this.refreshExpiresAt,
    required this.userId,
    required this.userEmail,
    required this.userFullName,
    required this.role,
  });

  final String accessToken;
  final String refreshToken;
  final DateTime accessExpiresAt;
  final DateTime refreshExpiresAt;
  final String userId;
  final String userEmail;
  final String userFullName;
  final String role;

  bool get isAccessExpired => DateTime.now().isAfter(accessExpiresAt);
  bool get isRefreshExpired => DateTime.now().isAfter(refreshExpiresAt);
  bool get isAuthenticated =>
      accessToken.isNotEmpty && refreshToken.isNotEmpty && !isRefreshExpired;
  bool get isAdmin => role == 'admin';

  Map<String, dynamic> toMap() {
    return {
      'accessToken': accessToken,
      'refreshToken': refreshToken,
      'accessExpiresAt': accessExpiresAt.toIso8601String(),
      'refreshExpiresAt': refreshExpiresAt.toIso8601String(),
      'userId': userId,
      'userEmail': userEmail,
      'userFullName': userFullName,
      'role': role,
    };
  }

  factory AuthSession.fromMap(Map<String, dynamic> map) {
    return AuthSession(
      accessToken: (map['accessToken'] ?? '').toString(),
      refreshToken: (map['refreshToken'] ?? '').toString(),
      accessExpiresAt:
          DateTime.tryParse((map['accessExpiresAt'] ?? '').toString()) ??
          DateTime.fromMillisecondsSinceEpoch(0),
      refreshExpiresAt:
          DateTime.tryParse((map['refreshExpiresAt'] ?? '').toString()) ??
          DateTime.fromMillisecondsSinceEpoch(0),
      userId: (map['userId'] ?? '').toString(),
      userEmail: (map['userEmail'] ?? '').toString(),
      userFullName: (map['userFullName'] ?? '').toString(),
      role: (map['role'] ?? 'student').toString(),
    );
  }

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    final user = json['user'] is Map<String, dynamic>
        ? json['user'] as Map<String, dynamic>
        : const <String, dynamic>{};

    return AuthSession(
      accessToken: (json['access_token'] ?? '').toString(),
      refreshToken: (json['refresh_token'] ?? '').toString(),
      accessExpiresAt: DateTime.fromMillisecondsSinceEpoch(
        ((json['access_expires_at'] ?? 0) as num).toInt() * 1000,
      ),
      refreshExpiresAt: DateTime.fromMillisecondsSinceEpoch(
        ((json['refresh_expires_at'] ?? 0) as num).toInt() * 1000,
      ),
      userId: (user['id'] ?? '').toString(),
      userEmail: (user['email'] ?? '').toString(),
      userFullName: (user['full_name'] ?? '').toString(),
      role: (user['role'] ?? 'student').toString(),
    );
  }
}
