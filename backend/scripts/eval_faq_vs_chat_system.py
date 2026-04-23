# -*- coding: utf-8 -*-
"""
تقييم: إجابة مرجعية من data/raw/faq.txt مقابل إجابة مُولّدة فعلياً من ChatService
(نفس منطق /chat) — دون استبدال بفقرات مسترجَعة فقط.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.chat import FALLBACK_AR, answer_question

RAW_FAQ = BACKEND_ROOT / "data" / "raw" / "faq.txt"
OUT_CSV = BACKEND_ROOT / "data" / "processed" / "faq_ref_vs_chat_generated.csv"
OUT_JSON = BACKEND_ROOT / "data" / "processed" / "faq_ref_vs_chat_generated.json"
TOP_K = 4


def is_question_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 8:
        return False
    return s.endswith("؟") or s.endswith("?")


def parse_faq(path: Path) -> list[tuple[str, str]]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pairs: list[tuple[str, str]] = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if is_question_line(line):
            q = line
            i += 1
            buf: list[str] = []
            while i < n and (not lines[i].strip() or not is_question_line(lines[i].strip())):
                t = lines[i].strip()
                if t:
                    buf.append(t)
                i += 1
            pairs.append((q, "\n".join(buf)))
        else:
            i += 1
    return pairs


def clean_text(s: str) -> str:
    s = s.replace("\u200f", "").replace("\u200e", "")
    s = re.sub(r"https?://\S+", " ", s)
    s = re.sub(r"[_*◆●■◾]+", " ", s)
    s = re.sub(r"[^\u0600-\u06FFa-zA-Z0-9\s\u0660-\u0669.,؛:!؟%]", " ", s)
    s = re.sub(r"[\d]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tfidf_cosine_percent(a: str, b: str) -> float:
    a, b = clean_text(a), clean_text(b)
    if not a or not b:
        return 0.0
    vec = TfidfVectorizer(
        token_pattern=r"(?u)\S+",
        ngram_range=(1, 2),
    )
    m = vec.fit_transform([a, b])
    return float(cosine_similarity(m[0], m[1])[0, 0] * 100.0)


def classify(p: float) -> str:
    if p <= 30:
        return "منخفض"
    if p <= 60:
        return "متوسط"
    return "مرتفع"


def is_valid_generated(text: str) -> bool:
    t = (text or "").strip()
    if not t or len(clean_text(t)) < 12:
        return False
    if t == FALLBACK_AR or t.startswith(FALLBACK_AR[:20]):
        return False
    return True


def run() -> int:
    if not RAW_FAQ.is_file():
        print(f"Missing {RAW_FAQ}", file=sys.stderr)
        return 1
    pairs = parse_faq(RAW_FAQ)
    rows: list[dict] = []
    for qid, (q, ref) in enumerate(pairs, 1):
        try:
            resp = answer_question(q, top_k=TOP_K)
        except Exception as e:  # pragma: no cover
            rows.append(
                {
                    "question_id": qid,
                    "question": q,
                    "reference_answer": ref,
                    "generated_answer": "",
                    "cosine_similarity_pct": "",
                    "classification": "مستبعد",
                    "notes": f"خطأ عند الاستدعاء: {e!s}",
                }
            )
            continue
        gen = (resp or {}).get("answer") or ""
        if not is_valid_generated(gen):
            rows.append(
                {
                    "question_id": qid,
                    "question": q,
                    "reference_answer": ref,
                    "generated_answer": gen,
                    "cosine_similarity_pct": "",
                    "classification": "مستبعد",
                    "notes": "إجابة غير صالحة: نص فارغ/قصير جداً أو رد الـfallback الرسمي.",
                }
            )
            continue
        cos = round(tfidf_cosine_percent(ref, gen), 2)
        cr, cg = clean_text(ref), clean_text(gen)
        if cr and cr == cg:
            cos = min(cos, 100.0)
        if cos > 99.0 and cr != cg:
            cos = min(cos, 99.0)
        rows.append(
            {
                "question_id": qid,
                "question": q,
                "reference_answer": ref,
                "generated_answer": gen,
                "cosine_similarity_pct": cos,
                "classification": classify(cos),
                "notes": f"confidence={resp.get('confidence', '')} route={resp.get('route_mode', '')}",
            }
        )

    scored = [r for r in rows if r["cosine_similarity_pct"] != ""]
    mean_c = (
        round(sum(float(r["cosine_similarity_pct"]) for r in scored) / len(scored), 2)
        if scored
        else None
    )
    top5 = sorted(
        ((r["question_id"], r["question"], float(r["cosine_similarity_pct"])) for r in scored),
        key=lambda x: -x[2],
    )[:5]
    bottom5 = sorted(
        ((r["question_id"], r["question"], float(r["cosine_similarity_pct"])) for r in scored),
        key=lambda x: x[2],
    )[:5]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "question_id",
                "question",
                "reference_answer",
                "generated_answer",
                "cosine_similarity_pct",
                "classification",
                "notes",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "question_id": r["question_id"],
                    "question": r["question"],
                    "reference_answer": r["reference_answer"],
                    "generated_answer": r["generated_answer"],
                    "cosine_similarity_pct": r["cosine_similarity_pct"],
                    "classification": r["classification"],
                    "notes": r["notes"],
                }
            )

    summary = {
        "reference_file": str(RAW_FAQ),
        "generator": "app.chat.answer_question (ChatService, same as /chat)",
        "total_questions": len(pairs),
        "evaluated": len(scored),
        "excluded": len(rows) - len(scored),
        "mean_cosine_pct": mean_c,
        "top_5": [
            {"question_id": a, "question": b[:200], "cosine_pct": c} for a, b, c in top5
        ],
        "bottom_5": [
            {"question_id": a, "question": b[:200], "cosine_pct": c} for a, b, c in bottom5
        ],
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_CSV} and {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
