# Backend

Authenticated backend for the Student Assistant regulations chatbot.

This backend serves the Flutter client and answers from the processed regulations data in:

- `data/processed/taibah_regulations.jsonl`
- `data/vectordb/`

## Official Python Version

- Official backend runtime: `Python 3.13.x`
- Official Windows virtual environment path: `backend\venv`
- Create the backend environment with `py -3.13 -m venv venv`

## Runtime Flow

- `app/api.py` -> FastAPI endpoints
- `app/chat.py` -> answer orchestration and formatting
- `app/chat_fallbacks.py` -> domain-specific fallback context retrieval
- `app/retrieve.py` -> retrieval and filtering

## Delivery Structure

```text
backend/
├─ app/
│  ├─ api.py
│  ├─ chat.py
│  ├─ retrieve.py
│  ├─ chroma_telemetry.py
│  ├─ prepare_data.py
│  ├─ improve_chunks.py
│  ├─ embed_store.py
│  └─ __init__.py
├─ data/
│  ├─ raw/
│  ├─ processed/
│  │  ├─ taibah_regulations.jsonl
│  │  └─ manifest.json
│  └─ vectordb/
├─ requirements.txt
└─ README.md
```

## Run The Backend

The official Windows team workflow uses `Python 3.13.x` and a repo-local virtual environment at `backend\venv`.

From the backend folder:

```bash
cd backend
py -3.13 -m venv venv
venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If you already created `backend\venv`, only activation is required before running backend commands:

```bash
cd backend
venv\Scripts\activate
```

Create deployment configuration from the provided template before production:

```bash
copy .env.example .env
```

Start the API on Windows in the safest way:

```bash
python start_backend_windows.py
```

This launcher keeps `stdout` and `stderr` attached to real log files under `data/logs/`, which avoids fragile detached-console behavior on Windows during lazy model loading.

The included launcher scripts assume `backend\venv` was created with `py -3.13 -m venv venv`:

```bash
.\run_api.ps1
```

If you want to run it manually in an active terminal, this still works:

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

## Authentication

Public auth endpoints:

- `POST /auth/register`
- `POST /auth/login`
- `POST /auth/refresh`

All operational endpoints require `Authorization: Bearer <access_token>`.

## Health Check

```bash
GET /health
```

This endpoint is authenticated.

Expected response:

```json
{
  "status": "ok",
  "ready": true,
  "version": "2.0.0",
  "user": "student@example.com"
}
```

## Chat API

```bash
POST /chat
```

Headers:

```text
Authorization: Bearer <access_token>
```

Request:

```json
{
  "question": "هل أستطيع الانسحاب من مقرر؟",
  "top_k": 4
}
```

## Search API

```bash
POST /search
```

Request:

```json
{
  "query": "السكن الجامعي",
  "top_k": 5
}
```

Response:

```json
{
  "query": "السكن الجامعي",
  "results": [
    {
      "id": "taibah_student_housing_rules_ar-0001",
      "document_title": "القواعد المنظمة للإسكان الطلابي بجامعة طيبة",
      "section": "الباب الأول: التعريفات والأهداف",
      "article": "",
      "title": "الباب الأول: التعريفات والأهداف",
      "score": 0.91,
      "content": "...",
      "content_preview": "..."
    }
  ]
}
```

## Feedback API

```bash
POST /feedback
```

Request:

```json
{
  "question": "هل يسمح بتصوير المحاضرات؟",
  "answer": "لا، لا يسمح بتسجيل أو تصوير المحاضرات...",
  "helpful": true,
  "language": "ar",
  "sources": []
}
```

Response:

```json
{
  "status": "ok"
}
```

Example chat response:

```json
{
  "question": "هل أستطيع الانسحاب من مقرر؟",
  "language": "ar",
  "answer": "نعم، يجوز للطالب الانسحاب من مقرر دراسي...",
  "sources": [
    {
      "id": "taibah_academic_regulations_ar.txt-0069",
      "source": "taibah_academic_regulations_ar.txt.txt",
      "document_title": "لائحة الدراسة والاختبارات للمرحلة الجامعية",
      "section": "الفصل الثالث: أنظمة الدراسة > القواعد التنفيذية للمادة الخامسة عشرة",
      "article": "المادة السابعة عشرة:",
      "title": "المادة السابعة عشرة:",
      "score": 0.9721,
      "content_preview": "الفصل الثالث: أنظمة الدراسة..."
    }
  ]
}
```

## Flutter Integration

The Flutter app reads:

- `answer` as the assistant message
- `sources` as optional references under the message
- authenticated responses using stored access and refresh tokens

Flutter release builds must use HTTPS and pass a backend URL through:

```bash
--dart-define=AI_CHAT_API_BASE_URL=http://YOUR_HOST:8000
```

If no URL is provided, the app uses its built-in local development defaults.

## Production Notes

- Configure a strong `JWT_SECRET`.
- Restrict `CORS_ORIGINS` to exact client origins.
- Keep `ENABLE_TRANSLATION=false` unless privacy review explicitly allows an external provider.
- Configure `REDIS_URL` for distributed rate limiting if you deploy more than one instance.
- See `../RELEASE_CHECKLIST.md` for deployment verification steps.

## Optional Maintenance

Only if you update the regulations text later:

1. Put UTF-8 `.txt` files in `data/raw/`
2. Rebuild processed data:

```bash
python -m app.prepare_data
python -m app.improve_chunks
python -m app.embed_store --rebuild
```
