import 'package:flutter/foundation.dart';

import '../../data/repositories/engagement_repository.dart';
import '../../domain/models/engagement_feed.dart';

class EngagementFeedController extends ChangeNotifier {
  EngagementFeedController({required EngagementRepository repository})
    : _repository = repository;

  final EngagementRepository _repository;
  static const Duration _generateThrottleWindow = Duration(seconds: 30);

  EngagementFeed? _data;
  bool _isLoading = true;
  bool _isRefreshing = false;
  bool _isMarkingRead = false;
  String? _errorMessage;
  DateTime? _lastGenerateAt;

  EngagementFeed? get data => _data;
  bool get isLoading => _isLoading;
  bool get isRefreshing => _isRefreshing;
  bool get isMarkingRead => _isMarkingRead;
  String? get errorMessage => _errorMessage;
  int get unreadCount => _data?.unreadCount ?? 0;

  Future<void> loadInitial() async {
    _isLoading = true;
    _errorMessage = null;
    notifyListeners();

    try {
      await _generateThenFetch();
    } catch (error) {
      _errorMessage = error.toString();
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> refresh() async {
    _isRefreshing = true;
    _errorMessage = null;
    notifyListeners();
    try {
      await _generateThenFetch();
    } catch (error) {
      _errorMessage = error.toString();
    } finally {
      _isRefreshing = false;
      notifyListeners();
    }
  }

  Future<void> markAsRead(String notificationId) async {
    if (_isMarkingRead || _data == null) {
      return;
    }

    final currentData = _data!;
    final previousData = currentData;
    final updatedNotifications = currentData.notifications
        .where((item) => item.id != notificationId)
        .toList(growable: false);
    final removedCount =
        currentData.notifications.length - updatedNotifications.length;
    if (removedCount == 0) {
      return;
    }

    _isMarkingRead = true;
    _data = currentData.copyWith(
      notifications: updatedNotifications,
      unreadCount: (currentData.unreadCount - removedCount).clamp(0, 999999),
    );
    notifyListeners();

    try {
      await _repository.markNotificationRead(notificationId);
    } catch (_) {
      _data = previousData;
      rethrow;
    } finally {
      _isMarkingRead = false;
      notifyListeners();
    }
  }

  Future<void> _generateThenFetch() async {
    final now = DateTime.now();
    final shouldGenerate =
        _lastGenerateAt == null ||
        now.difference(_lastGenerateAt!) >= _generateThrottleWindow;
    if (shouldGenerate) {
      _lastGenerateAt = now;
      try {
        await _repository.generateNotifications(limit: 20);
      } catch (_) {
        // Keep feed resilient: generation may fail while old notifications still exist.
      }
    }
    _data = await _repository.getFeed(includeRead: false, limit: 20);
  }
}
