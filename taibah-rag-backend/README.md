# Taibah RAG Backend

Final backend for the Taibah University regulations chatbot.

This backend is already connected to the Flutter AI chat page and is designed to answer from the processed regulations data in:
- `data/processed/taibah_regulations.jsonl`
- `data/vectordb/`

## Final Runtime Flow

- `app/api.py` -> FastAPI endpoints
- `app/chat.py` -> answer generation and relevance gate
- `app/retrieve.py` -> retrieval and filtering

## Delivery Structure

```text
taibah-rag-backend/
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

From the backend folder:

```bash
cd taibah-rag-backend
```

If you are using the included virtual environment on Windows:

```bash
venv\Scripts\activate
```

Install dependencies if needed:

```bash
pip install -r requirements.txt
```

Start the API:

```bash
uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
```

## Health Check

```bash
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "processed_chunks_ready": true,
  "vectordb_ready": true
}
```

## Chat API

```bash
POST /chat
```

Request:

```json
{
  "question": "هل أستطيع الانسحاب من مقرر؟",
  "top_k": 4
}
```

Response:

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

`POST /ask` is kept as an alias for `POST /chat`.

## Flutter Integration

The Flutter AI chat page reads:
- `answer` as the assistant message
- `sources` as optional references under the message

The Flutter app already supports a configurable backend URL through:

```bash
--dart-define=AI_CHAT_API_BASE_URL=http://YOUR_HOST:8000
```

If no URL is provided, the app uses its built-in local defaults.

## Optional Maintenance

Only if you update the regulations text later:

1. Put UTF-8 `.txt` files in `data/raw/`
2. Rebuild processed data:

```bash
python -m app.prepare_data
python -m app.improve_chunks
python -m app.embed_store --rebuild
```
