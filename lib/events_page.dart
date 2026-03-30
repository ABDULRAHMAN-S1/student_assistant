import 'package:flutter/material.dart';

import 'features/events/data/demo/demo_event_repository.dart';
import 'features/events/data/repositories/event_repository.dart';
import 'features/events/domain/models/event_item.dart';

class EventsPage extends StatefulWidget {
  final bool isArabic;

  const EventsPage({super.key, required this.isArabic});

  @override
  State<EventsPage> createState() => _EventsPageState();
}

class _EventsPageState extends State<EventsPage> {
  final Color _primaryCyan = const Color(0xFFE4008D);
  final Color _secondaryBlue = const Color(0xFFFF1493);
  final Color _accentPurple = const Color(0xFFC2185B);
  final EventRepository _eventRepository = DemoEventRepository();

  List<EventItem> _events = const [];

  @override
  void initState() {
    super.initState();
    _events = _eventRepository.getEvents();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      body: Column(
        children: [
          _buildHeader(),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _events.length,
              itemBuilder: (context, index) {
                return _buildEventCard(_events[index], index);
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: _showAddEventDialog,
        backgroundColor: _primaryCyan,
        child: const Icon(Icons.add),
      ),
    );
  }

  Widget _buildHeader() {
    return Container(
      padding: const EdgeInsets.fromLTRB(20, 50, 20, 20),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [_primaryCyan, _secondaryBlue, _accentPurple],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: const BorderRadius.only(
          bottomLeft: Radius.circular(30),
          bottomRight: Radius.circular(30),
        ),
        boxShadow: [
          BoxShadow(
            color: _primaryCyan.withValues(alpha: 0.3),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                widget.isArabic ? 'الأحداث والمواعيد' : 'Events & Schedule',
                style: const TextStyle(
                  color: Colors.white,
                  fontSize: 26,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.event, color: Colors.white, size: 24),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            widget.isArabic
                ? 'لا تفوت أي موعد مهم'
                : 'Never miss an important date',
            style: TextStyle(
              color: Colors.white.withValues(alpha: 0.8),
              fontSize: 14,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildEventCard(EventItem event, int index) {
    final title = widget.isArabic ? event.titleAr : event.titleEn;
    final date = widget.isArabic ? event.dateAr : event.dateEn;
    final typeLabel = _getTypeLabel(event.type);
    final reminderEnabled = event.reminderEnabled;

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(20),
          onTap: () => _showEventDetails(event),
          child: IntrinsicHeight(
            child: Row(
              children: [
                Container(
                  width: 6,
                  decoration: BoxDecoration(
                    color: event.color,
                    borderRadius: widget.isArabic
                        ? const BorderRadius.only(
                            topRight: Radius.circular(20),
                            bottomRight: Radius.circular(20),
                          )
                        : const BorderRadius.only(
                            topLeft: Radius.circular(20),
                            bottomLeft: Radius.circular(20),
                          ),
                  ),
                ),
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(18),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 10,
                                vertical: 4,
                              ),
                              decoration: BoxDecoration(
                                color: event.color.withValues(alpha: 0.1),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: Text(
                                typeLabel,
                                style: TextStyle(
                                  color: event.color,
                                  fontSize: 12,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                            IconButton(
                              icon: Icon(
                                reminderEnabled
                                    ? Icons.notifications_active
                                    : Icons.notifications_outlined,
                                color: reminderEnabled ? event.color : null,
                              ),
                              onPressed: () => _toggleReminder(index),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          title,
                          style: const TextStyle(
                            fontSize: 17.5,
                            fontWeight: FontWeight.w800,
                            height: 1.35,
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Icon(
                              Icons.calendar_today,
                              size: 16,
                              color: Colors.grey[600],
                            ),
                            const SizedBox(width: 6),
                            Text(
                              date,
                              style: TextStyle(
                                color: Colors.grey[600],
                                fontSize: 14,
                                height: 1.4,
                              ),
                            ),
                            const SizedBox(width: 16),
                            Icon(
                              Icons.access_time,
                              size: 16,
                              color: Colors.grey[600],
                            ),
                            const SizedBox(width: 6),
                            Text(
                              event.time,
                              style: TextStyle(
                                color: Colors.grey[600],
                                fontSize: 14,
                                height: 1.4,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _toggleReminder(int index) {
    setState(() {
      _events = _eventRepository.toggleReminder(_events[index]);
    });

    _showMessage(
      (widget.isArabic
          ? _events[index].reminderEnabled
                ? 'تم تفعيل التذكير'
                : 'تم إيقاف التذكير'
          : _events[index].reminderEnabled
          ? 'Reminder enabled'
          : 'Reminder disabled'),
    );
  }

  void _showEventDetails(EventItem event) {
    final title = widget.isArabic ? event.titleAr : event.titleEn;
    final date = widget.isArabic ? event.dateAr : event.dateEn;

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) {
        return Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Center(
                child: Container(
                  width: 42,
                  height: 4,
                  decoration: BoxDecoration(
                    color: Colors.grey[300],
                    borderRadius: BorderRadius.circular(999),
                  ),
                ),
              ),
              const SizedBox(height: 20),
              Text(
                title,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              _buildInfoRow(
                widget.isArabic ? 'النوع' : 'Type',
                _getTypeLabel(event.type),
              ),
              _buildInfoRow(widget.isArabic ? 'التاريخ' : 'Date', date),
              _buildInfoRow(widget.isArabic ? 'الوقت' : 'Time', event.time),
              _buildInfoRow(
                widget.isArabic ? 'التذكير' : 'Reminder',
                event.reminderEnabled
                    ? (widget.isArabic ? 'مفعل' : 'Enabled')
                    : (widget.isArabic ? 'غير مفعل' : 'Disabled'),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _showAddEventDialog() async {
    final titleController = TextEditingController();
    final dateController = TextEditingController();
    final timeController = TextEditingController();
    String selectedType = 'event';

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              title: Text(widget.isArabic ? 'إضافة موعد' : 'Add Event'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    TextField(
                      controller: titleController,
                      decoration: InputDecoration(
                        labelText: widget.isArabic ? 'العنوان' : 'Title',
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: dateController,
                      decoration: InputDecoration(
                        labelText: widget.isArabic ? 'التاريخ' : 'Date',
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: timeController,
                      decoration: InputDecoration(
                        labelText: widget.isArabic ? 'الوقت' : 'Time',
                      ),
                    ),
                    const SizedBox(height: 12),
                    DropdownButtonFormField<String>(
                      initialValue: selectedType,
                      decoration: InputDecoration(
                        labelText: widget.isArabic ? 'النوع' : 'Type',
                      ),
                      items: ['exam', 'workshop', 'deadline', 'event']
                          .map(
                            (type) => DropdownMenuItem<String>(
                              value: type,
                              child: Text(_getTypeLabel(type)),
                            ),
                          )
                          .toList(),
                      onChanged: (value) {
                        if (value == null) {
                          return;
                        }
                        setDialogState(() {
                          selectedType = value;
                        });
                      },
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  child: Text(widget.isArabic ? 'إلغاء' : 'Cancel'),
                ),
                FilledButton(
                  onPressed: () {
                    final title = titleController.text.trim();
                    final date = dateController.text.trim();
                    final time = timeController.text.trim();

                    if (title.isEmpty || date.isEmpty || time.isEmpty) {
                      _showMessage(
                        widget.isArabic
                            ? 'يرجى تعبئة جميع الحقول'
                            : 'Please fill in all fields',
                      );
                      return;
                    }

                    setState(() {
                      _events = _eventRepository.addEvent(
                        EventItem(
                          titleAr: title,
                          titleEn: title,
                          dateAr: date,
                          dateEn: date,
                          time: time,
                          type: selectedType,
                          color: _getTypeColor(selectedType),
                          reminderEnabled: false,
                        ),
                      );
                    });

                    Navigator.of(dialogContext).pop();
                    _showMessage(
                      widget.isArabic
                          ? 'تمت إضافة الموعد بنجاح'
                          : 'Event added successfully',
                    );
                  },
                  child: Text(widget.isArabic ? 'إضافة' : 'Add'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$label: ', style: const TextStyle(fontWeight: FontWeight.bold)),
          Expanded(child: Text(value)),
        ],
      ),
    );
  }

  Color _getTypeColor(String type) {
    switch (type) {
      case 'exam':
        return Colors.red;
      case 'workshop':
        return Colors.green;
      case 'deadline':
        return Colors.orange;
      case 'event':
      default:
        return Colors.purple;
    }
  }

  String _getTypeLabel(String type) {
    if (widget.isArabic) {
      switch (type) {
        case 'exam':
          return 'امتحان';
        case 'workshop':
          return 'ورشة';
        case 'deadline':
          return 'موعد نهائي';
        case 'event':
          return 'فعالية';
        default:
          return 'أخرى';
      }
    }

    switch (type) {
      case 'exam':
        return 'Exam';
      case 'workshop':
        return 'Workshop';
      case 'deadline':
        return 'Deadline';
      case 'event':
        return 'Event';
      default:
        return 'Other';
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }
}
