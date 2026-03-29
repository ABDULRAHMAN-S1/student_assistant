import 'package:flutter/material.dart';

import '../../domain/models/event_item.dart';
import '../repositories/event_repository.dart';

class DemoEventRepository implements EventRepository {
  DemoEventRepository();

  final List<EventItem> _events = [
    const EventItem(
      titleAr: 'امتحان منتصف الفصل',
      titleEn: 'Midterm Exam',
      dateAr: '١٥ نوفمبر ٢٠٢٤',
      dateEn: 'Nov 15, 2024',
      time: '09:00 AM',
      type: 'exam',
      color: Colors.red,
      reminderEnabled: false,
    ),
    const EventItem(
      titleAr: 'ورشة عمل البرمجة',
      titleEn: 'Programming Workshop',
      dateAr: '٢٠ نوفمبر ٢٠٢٤',
      dateEn: 'Nov 20, 2024',
      time: '02:00 PM',
      type: 'workshop',
      color: Colors.green,
      reminderEnabled: false,
    ),
    const EventItem(
      titleAr: 'موعد تسليم المشروع',
      titleEn: 'Project Deadline',
      dateAr: '٢٥ نوفمبر ٢٠٢٤',
      dateEn: 'Nov 25, 2024',
      time: '11:59 PM',
      type: 'deadline',
      color: Colors.orange,
      reminderEnabled: false,
    ),
    const EventItem(
      titleAr: 'يوم مفتوح للطلاب',
      titleEn: 'Student Open Day',
      dateAr: '٣٠ نوفمبر ٢٠٢٤',
      dateEn: 'Nov 30, 2024',
      time: '10:00 AM',
      type: 'event',
      color: Colors.purple,
      reminderEnabled: false,
    ),
  ];

  @override
  List<EventItem> getEvents() => List.unmodifiable(_events);

  @override
  List<EventItem> addEvent(EventItem event) {
    _events.insert(0, event);
    return getEvents();
  }

  @override
  List<EventItem> toggleReminder(EventItem event) {
    final index = _events.indexOf(event);
    if (index >= 0) {
      final current = _events[index];
      _events[index] = current.copyWith(
        reminderEnabled: !current.reminderEnabled,
      );
    }
    return getEvents();
  }
}
