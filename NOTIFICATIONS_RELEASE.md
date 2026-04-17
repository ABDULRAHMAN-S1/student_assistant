# Notification System Release Guide

## What was implemented

The engagement feed was upgraded into a production-oriented notification system across Flutter and FastAPI.

Implemented in code:

- paginated notification feed with stable cursor ordering
- cache-first notification loading with Hive-backed local cache
- explicit read/unread state with unread counter updates
- notification preferences persisted per user
- device-token registration and cleanup APIs
- Firebase Cloud Messaging delivery support on the backend
- Flutter push lifecycle handling for:
  - foreground messages
  - background taps
  - terminated launch taps
- typed notification deep-link routing
- Arabic and English timestamp formatting

## Backend environment requirements

Set these environment variables in backend deployment:

- `NOTIFICATIONS_PUSH_ENABLED=true`
- `FCM_PROJECT_ID=<your-firebase-project-id>`
- `FCM_SERVICE_ACCOUNT_JSON=<service-account-json>`

Alternative:

- `FCM_SERVICE_ACCOUNT_FILE=<path-to-service-account.json>`

Notes:

- push delivery is skipped safely when Firebase credentials are not configured
- in-app feed behavior still works without Firebase

## Flutter Firebase requirements

These files must be provided externally for the target Firebase project:

- `android/app/google-services.json`
- `ios/Runner/GoogleService-Info.plist`

If your team uses FlutterFire CLI, also generate:

- `lib/firebase_options.dart`

The current code is resilient when Firebase is not configured:

- the app still boots
- the engagement feed still works
- push registration silently no-ops
- local/in-app notifications and routing from the feed still work

## Token lifecycle

Implemented token behavior:

- token is requested after login/session initialization
- token refresh re-registers with the backend
- backend device-token id is persisted locally
- logout/session removal attempts backend-side token deletion
- stale previous device-token ids are cleaned up during token replacement

## Preferences behavior

Preferences are stored server-side and exposed through authenticated APIs.

Supported behavior:

- global `enable_push`
- global `enable_in_app`
- per-category overrides
- muted category behavior

Enforcement:

- backend skips push when push is disabled for the user/category
- backend skips in-app notification creation when in-app is disabled for the user/category

## Deep-link contract

Notification routes are passed in notification metadata using:

```json
{
  "type": "course | event | review | chat | search | external_url | engagement",
  "payload": {}
}
```

Current route handling:

- `course` -> Courses page
- `event` -> Events page
- `review` -> Reviews page
- `chat` -> AI chat page
- `search` -> Regulation search page, optionally seeded with `payload.query`
- `external_url` -> external browser via `url_launcher`
- `engagement` -> notifications inbox/feed

Invalid or missing route payload behavior:

- invalid route type -> ignored safely
- malformed payload JSON -> ignored safely
- empty external URL -> falls back to inbox open if available

## Fallback behavior when Firebase config is missing

If Firebase app files or credentials are missing:

- Flutter initialization catches Firebase setup failures
- push permission/token calls fail safely
- backend delivery returns a non-crashing "not configured" failure state
- feed, cache, read/unread, preferences, timestamps, and in-app routing continue to work

## Practical QA checklist

### Feed load
- log in
- open home page
- verify notifications/feed renders without crash
- verify unread badge appears if unread items exist

### Cache-first load
- open the app once while online
- kill the app
- reopen with backend unavailable
- verify cached feed appears read-only without crash

### Refresh
- pull/refresh feed
- verify unread count and list reconcile with backend state

### Pagination
- load first page
- trigger load more
- verify next page appends
- verify no duplicates after multiple loads

### Mark as read
- mark an unread item as read
- verify item remains visible and changes style
- verify unread badge/count decreases

### Preferences
- open profile page notification settings
- toggle push and in-app settings
- reopen page and verify server state persists

### Push
- with Firebase configured, log in on a device
- verify device token is registered on the backend
- send a notification
- verify:
  - foreground handling
  - background tap handling
  - terminated launch handling

### Tap routing
- tap a notification card from the feed
- verify matching screen opens
- test invalid route payload and confirm no crash

### Login / logout token lifecycle
- log in and confirm token registration
- log out and confirm cleanup request is attempted
- log back in and confirm registration works again

### Timestamps
- verify Arabic timestamps render in Arabic style
- verify English timestamps render in English style
- verify exact time text is visible on cards
