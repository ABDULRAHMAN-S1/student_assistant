import 'package:flutter/foundation.dart';

import '../../data/repositories/engagement_repository_impl.dart';
import '../../data/repositories/engagement_repository.dart';
import '../../domain/models/engagement_feed.dart';

class EngagementFeedController extends ChangeNotifier {
  EngagementFeedController({required EngagementRepository repository})
    : _repository = repository;

  final EngagementRepository _repository;
  static const Duration _generateThrottleWindow = Duration(seconds: 30);
  static const int _pageSize = 20;

  EngagementFeed? _data;
  bool _isLoading = true;
  bool _isRefreshing = false;
  bool _isMarkingRead = false;
  bool _isLoadingMore = false;
  String? _errorMessage;
  DateTime? _lastGenerateAt;
  String? _sessionExpiredMessage;
  final Set<String> _markingNotificationIds = <String>{};

  EngagementFeed? get data => _data;
  bool get isLoading => _isLoading;
  bool get isRefreshing => _isRefreshing;
  bool get isMarkingRead => _isMarkingRead;
  bool get isLoadingMore => _isLoadingMore;
  String? get errorMessage => _errorMessage;
  String? get sessionExpiredMessage => _sessionExpiredMessage;
  int get unreadCount => _data?.unreadCount ?? 0;
  bool get hasMore => _data?.page.hasMore == true;

  Future<void> loadInitial() async {
    _isLoading = true;
    _errorMessage = null;
    _sessionExpiredMessage = null;
    notifyListeners();

    try {
      final cached = await _loadCachedFeed();
      if (cached.notifications.isNotEmpty || cached.suggestions.isNotEmpty) {
        _data = cached;
        notifyListeners();
      }
      await _generateThenFetch(reset: true);
    } catch (error) {
      _captureError(error);
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<void> refresh() async {
    _isRefreshing = true;
    _errorMessage = null;
    _sessionExpiredMessage = null;
    notifyListeners();
    try {
      await _generateThenFetch(reset: true);
    } catch (error) {
      _captureError(error);
    } finally {
      _isRefreshing = false;
      notifyListeners();
    }
  }

  Future<void> loadMore() async {
    final current = _data;
    if (_isLoadingMore || current == null || !current.page.hasMore) {
      return;
    }
    _isLoadingMore = true;
    _errorMessage = null;
    notifyListeners();
    try {
      final nextPage = await _repository.getFeed(
        includeRead: true,
        limit: _pageSize,
        cursor: current.page.nextCursor,
      );
      _data = current.mergePage(nextPage);
    } catch (error) {
      _captureError(error);
    } finally {
      _isLoadingMore = false;
      notifyListeners();
    }
  }

  Future<void> markAsRead(String notificationId) async {
    if (_data == null || _markingNotificationIds.contains(notificationId)) {
      return;
    }

    final currentData = _data!;
    final previousData = currentData;
    final index = currentData.notifications.indexWhere(
      (item) => item.id == notificationId,
    );
    if (index < 0) {
      return;
    }
    final currentItem = currentData.notifications[index];
    if (currentItem.isRead) {
      return;
    }
    final optimistic = currentData.notifications.toList(growable: true);
    optimistic[index] = currentItem.copyWith(
      isRead: true,
      readAt: DateTime.now(),
    );

    _markingNotificationIds.add(notificationId);
    _isMarkingRead = true;
    _data = currentData.copyWith(
      notifications: optimistic,
      unreadCount: (currentData.unreadCount - 1).clamp(0, 999999),
    );
    notifyListeners();

    try {
      final result = await _repository.markNotificationRead(notificationId);
      final refreshed = (_data ?? previousData).notifications
          .map(
            (item) => item.id == result.notification.id ? result.notification : item,
          )
          .toList(growable: false);
      _data = (_data ?? previousData).copyWith(
        notifications: refreshed,
        unreadCount: result.unreadCount,
      );
    } catch (error) {
      _data = previousData;
      _captureError(error);
      rethrow;
    } finally {
      _markingNotificationIds.remove(notificationId);
      _isMarkingRead = _markingNotificationIds.isNotEmpty;
      notifyListeners();
    }
  }

  bool isMarkingNotification(String notificationId) {
    return _markingNotificationIds.contains(notificationId);
  }

  void clearSessionExpiredFlag() {
    _sessionExpiredMessage = null;
  }

  Future<void> _generateThenFetch({required bool reset}) async {
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
    final feed = await _repository.getFeed(
      includeRead: true,
      limit: _pageSize,
      cursor: reset ? null : _data?.page.nextCursor,
    );
    _data = reset || _data == null ? feed : _data!.mergePage(feed);
  }

  Future<EngagementFeed> _loadCachedFeed() async {
    final repository = _repository;
    if (repository is EngagementRepositoryImpl) {
      try {
        final userId = await repository.currentUserId();
        if (userId == null || userId.isEmpty) {
          return const EngagementFeed(
            notifications: [],
            suggestions: [],
          );
        }
        return await repository.getCachedFeed(userId: userId) ??
            const EngagementFeed(
              notifications: [],
              suggestions: [],
            );
      } catch (_) {
        return const EngagementFeed(
          notifications: [],
          suggestions: [],
        );
      }
    }
    return const EngagementFeed(
      notifications: [],
      suggestions: [],
    );
  }

  void _captureError(Object error) {
    final message = error.toString();
    _errorMessage = message;
    if (message.toLowerCase().contains('session expired')) {
      _sessionExpiredMessage = message;
    }
  }
}
