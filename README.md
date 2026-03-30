# Student Assistant App

Flutter app for students, connected to the authenticated regulations backend.

## Main Features

- AI chat for university regulation questions in Arabic and English
- Real login and registration flow
- Per-message translation through the backend
- Encrypted local chat history and settings
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
│  ├─ app/
│  ├─ features/
│  └─ services/
├─ assets/
├─ backend/
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

For release builds, use HTTPS:

```bash
flutter build apk --dart-define=AI_CHAT_API_BASE_URL=https://api.example.com
```

## Main AI Runtime Flow

- `lib/services/ai_chat_page.dart`
  UI for chat, history, suggestions, references, feedback, and translation
- `lib/features/ai_assistant/data/remote/assistant_api_client.dart`
  Authenticated backend API client for chat, search, feedback, and translation
- `lib/features/auth/data/remote/auth_api_client.dart`
  Backend auth client for register, login, and refresh
- `lib/app/app_settings_store.dart`
  Encrypted app settings and persisted auth session state

## Backend

The backend lives in:

```text
backend/
```

The official backend runtime is `Python 3.13.x`.

For the intended full semantic retrieval path on Windows, create the backend environment with:

```bash
cd backend
py -3.13 -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

See `backend/README.md` for the backend API, startup flow, and temporary Python 3.14 transition note.

See `RELEASE_CHECKLIST.md` for backend and Flutter deployment requirements.
