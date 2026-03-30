import 'package:flutter/material.dart';

import '../../../../app/backend_status_banner.dart';
import '../../auth/domain/models/auth_session.dart';
import '../data/remote/admin_api_client.dart';
import '../domain/models/admin_user.dart';

class AdminPanelPage extends StatefulWidget {
  const AdminPanelPage({
    super.key,
    required this.isArabic,
    required this.authSession,
    this.onSessionUpdated,
  });

  final bool isArabic;
  final AuthSession authSession;
  final Future<void> Function(AuthSession session)? onSessionUpdated;

  @override
  State<AdminPanelPage> createState() => _AdminPanelPageState();
}

class _AdminPanelPageState extends State<AdminPanelPage> {
  static const List<String> _roles = ['student', 'admin'];

  final AdminApiClient _apiClient = const AdminApiClient();
  List<AdminUser> _users = const [];
  bool _isLoading = true;
  String? _errorMessage;
  String? _updatingUserId;

  bool get _isArabic => widget.isArabic;

  @override
  void initState() {
    super.initState();
    _refreshUsers();
  }

  Future<void> _refreshUsers() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    try {
      final users = await _apiClient.listUsers();
      if (!mounted) return;
      setState(() {
        _users = users;
        _isLoading = false;
      });
    } on AdminApiException catch (error) {
      if (!mounted) return;
      setState(() {
        _errorMessage = error.message;
        _isLoading = false;
      });
    }
  }

  Future<void> _changeUserRole(AdminUser user, String role) async {
    if (_updatingUserId != null || role == user.role) {
      return;
    }

    setState(() {
      _updatingUserId = user.id;
    });

    try {
      final updatedUser = await _apiClient.updateUserRole(
        userId: user.id,
        role: role,
      );
      if (!mounted) return;

      setState(() {
        _users = _users
            .map((item) => item.id == updatedUser.id ? updatedUser : item)
            .toList(growable: false);
      });

      if (updatedUser.id == widget.authSession.userId) {
        final updatedSession = AuthSession(
          accessToken: widget.authSession.accessToken,
          refreshToken: widget.authSession.refreshToken,
          accessExpiresAt: widget.authSession.accessExpiresAt,
          refreshExpiresAt: widget.authSession.refreshExpiresAt,
          userId: widget.authSession.userId,
          userEmail: widget.authSession.userEmail,
          userFullName: widget.authSession.userFullName,
          role: updatedUser.role,
        );
        await widget.onSessionUpdated?.call(updatedSession);
        if (!mounted) return;
        if (updatedUser.role != 'admin') {
          Navigator.of(context).pop();
          return;
        }
      }

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            _isArabic ? 'تم تحديث الدور بنجاح' : 'Role updated successfully',
          ),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } on AdminApiException catch (error) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(error.message),
          behavior: SnackBarBehavior.floating,
        ),
      );
    } finally {
      if (!mounted) return;
      setState(() {
        _updatingUserId = null;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_isArabic ? 'لوحة الإدارة' : 'Admin Panel'),
        actions: [
          IconButton(
            onPressed: _isLoading ? null : _refreshUsers,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
            child: BackendStatusBanner(isArabic: _isArabic),
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 14),
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: _refreshUsers,
                child: Text(_isArabic ? 'إعادة المحاولة' : 'Retry'),
              ),
            ],
          ),
        ),
      );
    }

    if (_users.isEmpty) {
      return Center(
        child: Text(_isArabic ? 'لا يوجد مستخدمون' : 'No users found'),
      );
    }

    return ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: _users.length,
      separatorBuilder: (_, _) => const SizedBox(height: 12),
      itemBuilder: (context, index) => _buildUserCard(_users[index]),
    );
  }

  Widget _buildUserCard(AdminUser user) {
    final isUpdating = _updatingUserId == user.id;

    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              user.fullName,
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            Text(user.email, style: const TextStyle(color: Colors.black54)),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: Text(
                    _isArabic ? 'الدور' : 'Role',
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
                if (isUpdating)
                  const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                else
                  DropdownButton<String>(
                    value: user.role,
                    onChanged: (value) {
                      if (value == null) {
                        return;
                      }
                      _changeUserRole(user, value);
                    },
                    items: _roles
                        .map(
                          (role) => DropdownMenuItem<String>(
                            value: role,
                            child: Text(role),
                          ),
                        )
                        .toList(growable: false),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
