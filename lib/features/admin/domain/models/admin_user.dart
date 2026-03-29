class AdminUser {
  const AdminUser({
    required this.id,
    required this.email,
    required this.fullName,
    required this.role,
  });

  final String id;
  final String email;
  final String fullName;
  final String role;

  factory AdminUser.fromJson(Map<String, dynamic> json) {
    return AdminUser(
      id: (json['id'] ?? '').toString(),
      email: (json['email'] ?? '').toString(),
      fullName: (json['full_name'] ?? '').toString(),
      role: (json['role'] ?? 'student').toString(),
    );
  }

  AdminUser copyWith({String? role}) {
    return AdminUser(
      id: id,
      email: email,
      fullName: fullName,
      role: role ?? this.role,
    );
  }
}
