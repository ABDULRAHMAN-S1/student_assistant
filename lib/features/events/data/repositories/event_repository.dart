import '../../domain/models/event_item.dart';

abstract class EventRepository {
  List<EventItem> getEvents();

  List<EventItem> addEvent(EventItem event);

  List<EventItem> toggleReminder(EventItem event);
}
