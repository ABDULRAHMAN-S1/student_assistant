import 'package:flutter/material.dart';

class EventsPage extends StatefulWidget {
  final bool isArabic;

  const EventsPage({
    super.key,
    required this.isArabic, // ✅ صح - كان: required widget.isArabic
  });

  @override
  State<EventsPage> createState() => _EventsPageState();
}

class _EventsPageState extends State<EventsPage> {
  final Color _primaryCyan = const Color(0xFF26C6DA);
  final Color _secondaryBlue = const Color(0xFF4DD0E1);
  final Color _accentPurple = const Color(0xFF00ACC1);

  final List<Map<String, dynamic>> _events = [
    {
      'titleAr': 'امتحان منتصف الفصل',
      'titleEn': 'Midterm Exam',
      'dateAr': '١٥ نوفمبر ٢٠٢٤',
      'dateEn': 'Nov 15, 2024',
      'time': '09:00 AM',
      'type': 'exam',
      'color': Colors.red,
    },
    {
      'titleAr': 'ورشة عمل البرمجة',
      'titleEn': 'Programming Workshop',
      'dateAr': '٢٠ نوفمبر ٢٠٢٤',
      'dateEn': 'Nov 20, 2024',
      'time': '02:00 PM',
      'type': 'workshop',
      'color': Colors.green,
    },
    {
      'titleAr': 'موعد تسليم المشروع',
      'titleEn': 'Project Deadline',
      'dateAr': '٢٥ نوفمبر ٢٠٢٤',
      'dateEn': 'Nov 25, 2024',
      'time': '11:59 PM',
      'type': 'deadline',
      'color': Colors.orange,
    },
    {
      'titleAr': 'يوم مفتوح للطلاب',
      'titleEn': 'Student Open Day',
      'dateAr': '٣٠ نوفمبر ٢٠٢٤',
      'dateEn': 'Nov 30, 2024',
      'time': '10:00 AM',
      'type': 'event',
      'color': Colors.purple,
    },
  ];

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
                return _buildEventCard(_events[index]);
              },
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        onPressed: () {},
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

  Widget _buildEventCard(Map<String, dynamic> event) {
    final title = widget.isArabic ? event['titleAr'] : event['titleEn'];
    final date = widget.isArabic ? event['dateAr'] : event['dateEn'];
    final typeLabel = _getTypeLabel(event['type']);

    return Container(
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 15,
            offset: const Offset(0, 5),
          ),
        ],
      ),
      child: IntrinsicHeight(
        child: Row(
          children: [
            Container(
              width: 6,
              decoration: BoxDecoration(
                color: event['color'],
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
                padding: const EdgeInsets.all(16),
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
                            color: event['color'].withValues(alpha: 0.1),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            typeLabel,
                            style: TextStyle(
                              color: event['color'],
                              fontSize: 12,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.notifications_outlined),
                          onPressed: () {},
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
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
                          event['time'],
                          style: TextStyle(
                            color: Colors.grey[600],
                            fontSize: 14,
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
    );
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
    } else {
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
  }
}
