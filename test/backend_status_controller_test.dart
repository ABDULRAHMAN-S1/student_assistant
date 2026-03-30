import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:student_assistant/app/backend_status_controller.dart';

void main() {
  test('marks backend online when probe succeeds', () async {
    final controller = BackendStatusController(
      probe: () async => true,
      pollInterval: const Duration(hours: 1),
    );
    addTearDown(controller.dispose);

    await controller.refresh();

    expect(controller.snapshot.status, BackendConnectionStatus.online);
    expect(controller.snapshot.lastCheckedAt, isNotNull);
  });

  test('marks backend offline when probe fails', () async {
    final controller = BackendStatusController(
      probe: () async => false,
      pollInterval: const Duration(hours: 1),
    );
    addTearDown(controller.dispose);

    await controller.refresh();

    expect(controller.snapshot.status, BackendConnectionStatus.offline);
    expect(controller.snapshot.lastCheckedAt, isNotNull);
  });

  test('emits checking state before the probe resolves', () async {
    final completer = Completer<bool>();
    final controller = BackendStatusController(
      probe: () => completer.future,
      pollInterval: const Duration(hours: 1),
    );
    addTearDown(controller.dispose);

    final future = controller.refresh();

    expect(controller.snapshot.status, BackendConnectionStatus.checking);

    completer.complete(true);
    await future;

    expect(controller.snapshot.status, BackendConnectionStatus.online);
  });
}
