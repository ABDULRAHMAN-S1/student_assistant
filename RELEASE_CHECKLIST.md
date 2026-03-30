# Release Checklist

## Backend

- Copy `backend/.env.example` to your deployment secret store and replace every placeholder.
- Set `APP_ENV=production`.
- Set a strong `JWT_SECRET`.
- Set `CORS_ORIGINS` to the exact HTTPS origins that should access the API.
- Keep `REQUIRE_HTTPS=true` behind your reverse proxy or load balancer.
- Set `ENABLE_API_DOCS=false` unless you intentionally want public docs.
- Configure `REDIS_URL` when deploying more than one backend instance.
- Keep `ENABLE_TRANSLATION=false` unless the provider is approved by your privacy policy.
- Persist `APP_DB_PATH` on durable storage, or replace SQLite with a managed production database before scaling write traffic.

## Backend launch

- Install backend dependencies with `pip install -r backend/requirements.txt`.
- Start the API with a process manager, for example `uvicorn app.api:app --host 0.0.0.0 --port 8000` from the `backend` directory.
- Terminate TLS at the edge and forward `X-Forwarded-Proto` correctly.
- Verify `/auth/register`, `/auth/login`, `/chat`, `/search`, `/feedback`, and `/translate` from a deployed client origin.

## Flutter release builds

- Use an HTTPS API origin for release builds.
- Pass the API base URL with `--dart-define=AI_CHAT_API_BASE_URL=https://api.example.com`.
- Verify login, token refresh, chat, search, translation fallback behavior, and feedback submission against production.
- Keep the secure-storage backed Hive key path intact; do not replace it with plaintext storage for release builds.
- Test Android, iOS, and web separately because they use different local defaults in development.

## Smoke verification

- Register a fresh account.
- Sign in with that account.
- Send an authenticated chat request.
- Submit feedback on a response.
- Confirm rate limiting, CORS, and HTTPS behavior from the deployed frontend.
