import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'api_base_url.dart';

enum BackendConnectionStatus { unknown, checking, online, offline }

typedef BackendProbe = Future<bool> Function();

class BackendStatusSnapshot {
  const BackendStatusSnapshot({required this.status, this.lastCheckedAt});

  final BackendConnectionStatus status;
  final DateTime? lastCheckedAt;

  bool get isOnline => status == BackendConnectionStatus.online;
  bool get isChecking => status == BackendConnectionStatus.checking;
  bool get isOffline => status == BackendConnectionStatus.offline;
}

class BackendStatusController extends ChangeNotifier {
  BackendStatusController({
    BackendProbe? probe,
    Duration pollInterval = const Duration(seconds: 15),
  }) : _probe = probe ?? _defaultProbe,
       _pollInterval = pollInterval;

  static final BackendStatusController instance = BackendStatusController();

  final BackendProbe _probe;
  final Duration _pollInterval;

  BackendStatusSnapshot _snapshot = const BackendStatusSnapshot(
    status: BackendConnectionStatus.unknown,
  );
  Timer? _pollTimer;
  Future<void>? _inFlightRefresh;

  BackendStatusSnapshot get snapshot => _snapshot;

  void ensureStarted() {
    if (_pollTimer != null) {
      return;
    }

    _pollTimer = Timer.periodic(_pollInterval, (_) {
      unawaited(refresh(showCheckingState: false));
    });

    if (_snapshot.status == BackendConnectionStatus.unknown) {
      unawaited(refresh());
    }
  }

  Future<void> refresh({bool showCheckingState = true}) {
    return _inFlightRefresh ??=
        _performRefresh(showCheckingState: showCheckingState).whenComplete(() {
          _inFlightRefresh = null;
        });
  }

  Future<void> _performRefresh({required bool showCheckingState}) async {
    if (showCheckingState && !_snapshot.isChecking) {
      _setSnapshot(
        BackendStatusSnapshot(
          status: BackendConnectionStatus.checking,
          lastCheckedAt: _snapshot.lastCheckedAt,
        ),
      );
    }

    final checkedAt = DateTime.now();
    try {
      final reachable = await _probe();
      _setSnapshot(
        BackendStatusSnapshot(
          status: reachable
              ? BackendConnectionStatus.online
              : BackendConnectionStatus.offline,
          lastCheckedAt: checkedAt,
        ),
      );
    } catch (_) {
      _setSnapshot(
        BackendStatusSnapshot(
          status: BackendConnectionStatus.offline,
          lastCheckedAt: checkedAt,
        ),
      );
    }
  }

  void _setSnapshot(BackendStatusSnapshot nextSnapshot) {
    final previous = _snapshot;
    final changed =
        previous.status != nextSnapshot.status ||
        previous.lastCheckedAt != nextSnapshot.lastCheckedAt;
    _snapshot = nextSnapshot;
    if (changed) {
      notifyListeners();
    }
  }

  static Future<bool> _defaultProbe() async {
    // Must work before login; use a public endpoint and require a successful response.
    final uri = buildApiUri('/public/health');
    final response = await http.get(uri).timeout(const Duration(seconds: 3));
    return response.statusCode >= 200 && response.statusCode < 300;
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }
}
