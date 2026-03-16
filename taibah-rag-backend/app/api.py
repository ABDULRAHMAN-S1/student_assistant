from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    from app.chat import answer_question
    from app.retrieve import CHUNKS_PATH, VECTORDB_DIR
except ImportError:
    from chat import answer_question  # type: ignore
    from retrieve import CHUNKS_PATH, VECTORDB_DIR  # type: ignore


BUILD_INFO_PATH = VECTORDB_DIR / "build_info.json"


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.api:app", host="0.0.0.0", port=8000, reload=False)
