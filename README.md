# Student Assistant App

Flutter mobile app for students, connected to the Taibah University regulations RAG backend.

## Main Features

- AI chat for university regulation questions in Arabic and English
- Per-message translation for AI replies
- Local chat history
- Suggested starter questions
- Full regulation reference view
- Simple regulation search page
- Student-facing pages for home, courses, events, and reviews

## Project Structure

```text
student_assistant/
├─ lib/
│  ├─ main.dart
│  ├─ home_page.dart
│  ├─ welcome_screen.dart
│  ├─ login_page.dart
│  ├─ create_account_screen.dart
│  ├─ forgot_password_screen.dart
│  ├─ courses_page.dart
│  ├─ events_page.dart
│  ├─ reviews_page.dart
│  ├─ custom_dialog.dart
│  ├─ custom_toast.dart
│  └─ services/
│     ├─ ai_api.dart
│     ├─ ai_chat_page.dart
│     ├─ ai_chat_storage.dart
│     ├─ ai_message_translation.dart
│     └─ regulation_search_page.dart
├─ assets/
├─ taibah-rag-backend/
└─ pubspec.yaml
```

## Run The Flutter App

```bash
flutter pub get
flutter run
```

To connect the app to a specific backend host:

```bash
flutter run --dart-define=AI_CHAT_API_BASE_URL=http://YOUR_HOST:8000
```

Default behavior:

- Web: `http://localhost:8000`
- Android emulator: `http://10.0.2.2:8000`
- Other platforms: `http://127.0.0.1:8000`

## Main AI Runtime Flow

- `lib/services/ai_chat_page.dart`
  UI for chat, history, suggestions, references, feedback, and translation
- `lib/services/ai_api.dart`
  Backend API client for chat, search, and feedback
- `lib/services/ai_chat_storage.dart`
  Local Hive-based chat history persistence
- `lib/services/ai_message_translation.dart`
  Lightweight per-message translation helper

## Backend

The backend lives in:

```text
taibah-rag-backend/
```

See `taibah-rag-backend/README.md` for API endpoints, backend startup, and data pipeline details.
