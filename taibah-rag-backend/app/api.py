from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from app.chat import answer_question
    from app.retrieve import CHUNKS_PATH, VECTORDB_DIR, search
except ImportError:
    from chat import answer_question  # type: ignore
    from retrieve import CHUNKS_PATH, VECTORDB_DIR, search  # type: ignore


BUILD_INFO_PATH = VECTORDB_DIR / "build_info.json"
FEEDBACK_DIR = Path(__file__).resolve().parent.parent / "data" / "feedback"
FEEDBACK_PATH = FEEDBACK_DIR / "feedback.jsonl"


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
    question: str = Field(..., min_length=1, description="Question in Arabic or English.")
    top_k: int = Field(4, ge=1, le=10, description="Number of chunks to retrieve.")


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query in Arabic or English.")
    top_k: int = Field(5, ge=1, le=10, description="Number of search results to return.")


class FeedbackRequest(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)
    helpful: bool = Field(..., description="Whether the user found the answer helpful.")
    language: str = Field("", description="Detected language on the client.")
    sources: list[dict[str, object]] = Field(default_factory=list)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "processed_chunks_ready": CHUNKS_PATH.exists(),
        "vectordb_ready": BUILD_INFO_PATH.exists(),
    }


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    try:
        return answer_question(request.question, top_k=request.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc


@app.post("/ask")
def ask(request: ChatRequest) -> dict[str, object]:
    return chat(request)


@app.post("/search")
def regulation_search(request: SearchRequest) -> dict[str, object]:
    try:
        matches = search(request.query, top_k=request.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    results = [
        {
            "id": item["id"],
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
        "query": request.query,
        "results": results,
    }


@app.post("/feedback")
def feedback(request: FeedbackRequest) -> dict[str, object]:
    try:
        FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)
        with FEEDBACK_PATH.open("a", encoding="utf-8") as file:
            file.write(
                json.dumps(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "question": request.question,
                        "answer": request.answer,
                        "helpful": request.helpful,
                        "language": request.language,
                        "sources": request.sources,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}") from exc

    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False)
