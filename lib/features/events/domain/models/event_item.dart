import 'package:flutter/material.dart';

class EventItem {
  const EventItem({
    required this.titleAr,
    required this.titleEn,
    required this.dateAr,
    required this.dateEn,
    required this.time,
    required this.type,
    required this.color,
    required this.reminderEnabled,
  });

  final String titleAr;
  final String titleEn;
  final String dateAr;
  final String dateEn;
  final String time;
  final String type;
  final Color color;
  final bool reminderEnabled;

  EventItem copyWith({
    String? titleAr,
    String? titleEn,
    String? dateAr,
    String? dateEn,
    String? time,
    String? type,
    Color? color,
    bool? reminderEnabled,
  }) {
    return EventItem(
      titleAr: titleAr ?? this.titleAr,
      titleEn: titleEn ?? this.titleEn,
      dateAr: dateAr ?? this.dateAr,
      dateEn: dateEn ?? this.dateEn,
      time: time ?? this.time,
      type: type ?? this.type,
      color: color ?? this.color,
      reminderEnabled: reminderEnabled ?? this.reminderEnabled,
    );
  }
}
