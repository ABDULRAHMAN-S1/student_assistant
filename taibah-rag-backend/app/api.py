from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

try:
    from app.chat import answer_question
    from app.retrieve import (
        BUILD_INFO_PATH,
        CHUNKS_PATH,
        get_chunk_records,
        get_collection,
        get_processed_chunks_state,
        get_vector_build_info,
        search,
    )
except ImportError:
    from chat import answer_question  # type: ignore
    from retrieve import (  # type: ignore
        BUILD_INFO_PATH,
        CHUNKS_PATH,
        get_chunk_records,
        get_collection,
        get_processed_chunks_state,
        get_vector_build_info,
        search,
    )


FEEDBACK_DIR = Path(__file__).resolve().parent.parent / "data" / "feedback"
FEEDBACK_PATH = FEEDBACK_DIR / "feedback.jsonl"
MAX_QUESTION_LENGTH = 500
MAX_SEARCH_QUERY_LENGTH = 500
MAX_ANSWER_LENGTH = 4000
MAX_LANGUAGE_LENGTH = 16
MAX_FEEDBACK_SOURCES = 10
RATE_LIMIT_RULES = {
    "/chat": (20, 60),
    "/search": (40, 60),
    "/feedback": (30, 60),
}


logger = logging.getLogger(__name__)
_rate_limit_lock = threading.Lock()
_rate_limit_state: dict[tuple[str, str], list[float]] = {}


app = FastAPI(
    title="Taibah Regulations RAG API",
    description="Minimal Arabic-first RAG backend for university regulations.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description="Question in Arabic or English.",
    )
    top_k: int = Field(4, ge=1, le=10, description="Number of chunks to retrieve.")


class SearchRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=MAX_SEARCH_QUERY_LENGTH,
        description="Search query in Arabic or English.",
    )
    top_k: int = Field(5, ge=1, le=10, description="Number of search results to return.")


class FeedbackRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=MAX_QUESTION_LENGTH)
    answer: str = Field(..., min_length=1, max_length=MAX_ANSWER_LENGTH)
    helpful: bool = Field(..., description="Whether the user found the answer helpful.")
    language: str = Field("", max_length=MAX_LANGUAGE_LENGTH, description="Detected language on the client.")
    sources: list[dict[str, object]] = Field(default_factory=list, max_length=MAX_FEEDBACK_SOURCES)


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: object | None = None,
) -> JSONResponse:
    payload: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
        },
        "detail": message,
    }
    if details is not None:
        payload["error"] = {
            **payload["error"],
            "details": details,
        }
    return JSONResponse(status_code=status_code, content=payload)


def raise_api_error(*, status_code: int, code: str, message: str) -> None:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message})


def trim_required_text(value: str, *, field_name: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        raise_api_error(status_code=422, code="validation_error", message=f"{field_name} must not be empty.")
    return trimmed


def client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded_for:
        return forwarded_for
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(request: Request) -> None:
    rule = RATE_LIMIT_RULES.get(request.url.path)
    if not rule:
        return

    limit, window_seconds = rule
    key = (request.url.path, client_ip(request))
    now = time.monotonic()

    with _rate_limit_lock:
        timestamps = [stamp for stamp in _rate_limit_state.get(key, []) if now - stamp < window_seconds]
        if len(timestamps) >= limit:
            raise_api_error(
                status_code=429,
                code="rate_limited",
                message="Too many requests. Please try again shortly.",
            )
        timestamps.append(now)
        _rate_limit_state[key] = timestamps


def readiness_state() -> dict[str, object]:
    processed_chunks_ready = CHUNKS_PATH.exists()
    vectordb_ready = BUILD_INFO_PATH.exists()
    chunk_records_ready = False
    build_info_ready = False
    collection_ready = False
    sync_ready = False
    chunk_count_match = False
    sync_hash_match = False
    collection_count_match = False
    processed_chunk_count = 0
    vector_chunk_count = 0
    collection_count = 0

    processed_state: dict[str, object] | None = None
    build_info: dict[str, object] | None = None

    if processed_chunks_ready:
        try:
            processed_state = get_processed_chunks_state()
            processed_chunk_count = int(processed_state.get("chunk_count", 0))
            chunk_records_ready = processed_chunk_count > 0 and len(get_chunk_records()) == processed_chunk_count
        except Exception:
            chunk_records_ready = False

    if vectordb_ready:
        try:
            build_info = get_vector_build_info()
            vector_chunk_count = int(build_info.get("chunk_count", 0))
            build_info_ready = True
        except Exception:
            build_info_ready = False

    if build_info_ready:
        try:
            collection = get_collection()
            collection_count = int(collection.count())
            collection_ready = True
        except Exception:
            collection_ready = False

    if processed_state and build_info_ready:
        chunk_count_match = vector_chunk_count == processed_chunk_count
        sync_hash_match = str(build_info.get("processed_sync_hash", "")) == str(processed_state.get("sync_hash", ""))
    if processed_state and collection_ready:
        collection_count_match = collection_count == processed_chunk_count

    sync_ready = chunk_count_match and sync_hash_match and collection_count_match

    vectordb_ready = build_info_ready and collection_ready
    ready = processed_chunks_ready and vectordb_ready and chunk_records_ready and sync_ready
    return {
        "status": "ok" if ready else "degraded",
        "ready": ready,
        "processed_chunks_ready": processed_chunks_ready,
        "vectordb_ready": vectordb_ready,
        "chunk_records_ready": chunk_records_ready,
        "build_info_ready": build_info_ready,
        "collection_ready": collection_ready,
        "sync_ready": sync_ready,
        "chunk_count_match": chunk_count_match,
        "sync_hash_match": sync_hash_match,
        "collection_count_match": collection_count_match,
        "processed_chunk_count": processed_chunk_count,
        "vector_chunk_count": vector_chunk_count,
        "collection_count": collection_count,
    }


@app.exception_handler(RequestValidationError)
def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(
        status_code=422,
        code="validation_error",
        message="Request validation failed.",
        details=exc.errors(),
    )


@app.exception_handler(HTTPException)
def handle_http_exception(_: Request, exc: HTTPException) -> JSONResponse:
    detail = exc.detail
    if isinstance(detail, dict):
        code = str(detail.get("code") or "request_error")
        message = str(detail.get("message") or "Request failed.")
        details = detail.get("details")
    else:
        code = "request_error"
        message = str(detail or "Request failed.")
        details = None
    return error_response(status_code=exc.status_code, code=code, message=message, details=details)


@app.exception_handler(Exception)
def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled API error on %s", request.url.path, exc_info=exc)
    return error_response(
        status_code=500,
        code="internal_error",
        message="Internal server error.",
    )


@app.get("/health")
def health() -> dict[str, object]:
    return readiness_state()


@app.post("/chat")
def chat(http_request: Request, request: ChatRequest) -> dict[str, object]:
    enforce_rate_limit(http_request)
    question = trim_required_text(request.question, field_name="question")
    try:
        return answer_question(question, top_k=request.top_k)
    except RuntimeError as exc:
        raise_api_error(status_code=400, code="bad_request", message=str(exc))

@app.post("/search")
def regulation_search(http_request: Request, request: SearchRequest) -> dict[str, object]:
    enforce_rate_limit(http_request)
    query = trim_required_text(request.query, field_name="query")
    try:
        matches = search(query, top_k=request.top_k)
    except RuntimeError as exc:
        raise_api_error(status_code=400, code="bad_request", message=str(exc))

    results = [
        {
            "id": item["id"],
            "doc_type": item["metadata"].get("doc_type"),
            "document_title": item["metadata"].get("document_title"),
            "section": item["metadata"].get("section"),
            "article": item["metadata"].get("article"),
            "title": item["metadata"].get("title"),
            "score": item.get("score"),
            "content": item.get("content", ""),
            "content_preview": item.get("content", "")[:260].strip(),
        }
        for item in matches
    ]
    return {
        "query": query,
        "results": results,
    }


@app.post("/feedback")
def feedback(http_request: Request, request: FeedbackRequest) -> dict[str, object]:
    enforce_rate_limit(http_request)
    question = trim_required_text(request.question, field_name="question")
    answer = trim_required_text(request.answer, field_name="answer")
    language = (request.language or "").strip()
    FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_PATH.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "question": question,
                    "answer": answer,
                    "helpful": request.helpful,
                    "language": language,
                    "sources": request.sources[:MAX_FEEDBACK_SOURCES],
                },
                ensure_ascii=False,
            )
            + "\n"
        )

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False)
