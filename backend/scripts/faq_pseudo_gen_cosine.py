# -*- coding: utf-8 -*-
"""
Pipeline: read backend/data/raw/faq.txt, extract Q/A pairs, build pseudo-ref + generated
(ملخص/شطر أول من إجابة الـraw) vs (شطر لاحق/متوسط بلا تداخل كبير) أو (إعادة صياغة بترجمة
عكسية إذا ضُبط FAQ_USE_BT=1), ثم Cosine(TF-IDF) بين الإجابتين. لا يمثّل gold reference بشرياً.
"""

from __future__ import annotations

import csv
import json
import os
import re
import sys
import time
from pathlib import Path

# TF-IDF + cosine
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError as e:  # pragma: no cover
    print("Install scikit-learn: pip install scikit-learn", file=sys.stderr)
    raise e

try:
    from deep_translator import GoogleTranslator
except ImportError:  # pragma: no cover
    GoogleTranslator = None


ROOT = Path(__file__).resolve().parents[1]
RAW_FAQ = ROOT / "data" / "raw" / "faq.txt"
OUT_CSV = ROOT / "data" / "processed" / "faq_pseudo_gen_tfidf_cosine.csv"
OUT_JSON = ROOT / "data" / "processed" / "faq_pseudo_gen_tfidf_cosine.json"


def is_question_line(line: str) -> bool:
    s = line.strip()
    if len(s) < 8:
        return False
    return s.endswith("؟") or s.endswith("?")


def parse_faq_lines(lines: list[str]) -> list[tuple[str, str]]:
    """سطر يبدأ/ينتهي بسؤال: حتى سطر السؤال التالي = الجواب."""
    pairs: list[tuple[str, str]] = []
    i = 0
    n = len(lines)
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


def first_chunk_for_pseudo(answered: str, max_chars: int = 450) -> str:
    t = clean_text(answered)
    if not t:
        return ""
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars]
    for sep in ("،", ".", "؛", " "):
        idx = cut.rfind(sep)
        if idx > 80:
            return cut[: idx + 1].strip()
    return cut.strip()


def second_chunk_alternative(answered: str, start_min: int = 200) -> str:
    """جزء لاحق/متوسط من نفس الإجابة بحيث لا يتطابق مع الشطر الأول عادةً."""
    t = clean_text(answered)
    if len(t) <= start_min:
        return t[len(t) // 2 :].strip() or t
    return t[start_min:].strip()


def mid_chunk_alternative(answered: str) -> str:
    """نافذة من منتصف النص عبر حدود كلمات لتفادي قص أحرف عربية."""
    t = clean_text(answered)
    toks = t.split()
    if len(toks) < 4:
        return t[len(t) // 2 :].strip() or t
    a = max(1, len(toks) // 4)
    b = min(len(toks), 3 * len(toks) // 4 + 1)
    window = " ".join(toks[a:b])
    if len(window) < 20 and len(toks) >= 2:
        return " ".join(toks[len(toks) // 2 :])
    return window.strip()


def use_backtranslate() -> bool:
    return os.environ.get("FAQ_USE_BT", "").strip() in ("1", "true", "yes")


def back_translate_if_possible(text: str) -> tuple[str, str | None]:
    if not use_backtranslate():
        return text, "skip_BT_local_mode"
    if not text or not GoogleTranslator:
        return text, "no_translator" if not GoogleTranslator else "empty"
    try:
        en = GoogleTranslator(source="ar", target="en").translate(text[:4500])
        time.sleep(0.2)
        ar2 = GoogleTranslator(source="en", target="ar").translate(en[:5000])
        time.sleep(0.2)
        return clean_text(ar2), None
    except Exception as e:  # network / quota
        return text, f"translate_error:{e!s}"


def tfidf_cosine_percent(a: str, b: str) -> float:
    a, b = clean_text(a), clean_text(b)
    if not a or not b:
        return 0.0
    vec = TfidfVectorizer(
        token_pattern=r"(?u)\S+",
        ngram_range=(1, 2),
    )
    m = vec.fit_transform([a, b])
    sim = cosine_similarity(m[0], m[1])[0, 0]
    return float(sim * 100.0)


def classify(p: float) -> str:
    if p <= 30:
        return "منخفض"
    if p <= 60:
        return "متوسط"
    return "مرتفع"


def run() -> int:
    if not RAW_FAQ.is_file():
        print(f"Missing file: {RAW_FAQ}", file=sys.stderr)
        return 1
    text = RAW_FAQ.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    pairs = parse_faq_lines(lines)
    rows: list[dict] = []
    excluded = 0
    for idx, (q, a) in enumerate(pairs, 1):
        a = a.strip()
        if len(clean_text(a)) < 15:
            excluded += 1
            rows.append(
                {
                    "id": idx,
                    "question": q,
                    "pseudo": "",
                    "generated": "",
                    "cosine_pct": None,
                    "classification": "مستبعد",
                    "notes": "إجابة ناقصة جداً",
                }
            )
            continue

        pseudo = first_chunk_for_pseudo(a)
        err: str | None = None
        if use_backtranslate():
            gen, tr_err = back_translate_if_possible(pseudo)
            gen = clean_text(gen)
            if tr_err and "translate_error" in tr_err:
                gen = clean_text(mid_chunk_alternative(a))
                err = f"{tr_err} +mid_fallback"
            elif not gen or len(gen) < 10 or gen == clean_text(pseudo):
                gen = clean_text(second_chunk_alternative(a))
                err = (tr_err or "bt_pseudo_duplicate") + " +second_fallback"
            else:
                err = tr_err
        else:
            gen = clean_text(mid_chunk_alternative(a))
            if not gen or len(gen) < 15 or gen == clean_text(pseudo):
                gen = clean_text(second_chunk_alternative(a))
                err = "local_mode second_chunk"
            else:
                err = "local_mode mid_window"

        if clean_text(pseudo) == clean_text(gen):
            gen = clean_text(second_chunk_alternative(a)) or gen
            err = (err or "") + "+forced_split"

        cos = round(tfidf_cosine_percent(pseudo, gen), 2)
        # لا نمنح 100% عبر نسخ حرفي: بعد التنظيف إن تطابقت
        cp = clean_text(pseudo)
        cg = clean_text(gen)
        if cp == cg and cp:
            cos = min(cos, 99.9)

        rows.append(
            {
                "id": idx,
                "question": q,
                "pseudo": pseudo,
                "generated": gen,
                "cosine_pct": cos,
                "classification": classify(cos) if cos is not None else "",
                "notes": f"pseudo=ملخص/شطر أول من إجابة الـraw؛ generated=إعادة صياغة/شطر مكمّل. {err or ''}".strip(),
            }
        )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "question_id",
                "question",
                "pseudo_reference_answer",
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
                    "question_id": r["id"],
                    "question": r["question"],
                    "pseudo_reference_answer": r["pseudo"] or "",
                    "generated_answer": r["generated"] or "",
                    "cosine_similarity_pct": r["cosine_pct"] if r["cosine_pct"] is not None else "",
                    "classification": r["classification"],
                    "notes": r["notes"],
                }
            )

    scored = [
        (r["id"], r["question"], float(r["cosine_pct"]))
        for r in rows
        if r["cosine_pct"] is not None
    ]
    mean_cos = round(sum(t[2] for t in scored) / len(scored), 2) if scored else None
    top5 = sorted(scored, key=lambda x: x[2], reverse=True)[:5]
    bottom5 = sorted(scored, key=lambda x: x[2])[:5]
    OUT_JSON.write_text(
        json.dumps(
            {
                "source": str(RAW_FAQ),
                "pairs_total": len(pairs),
                "excluded_tiny_answers": excluded,
                "evaluated_count": len(scored),
                "mean_cosine_pct": mean_cos,
                "top_5": [
                    {"question_id": i, "question": q[:120], "cosine_pct": c} for i, q, c in top5
                ],
                "bottom_5": [
                    {"question_id": i, "question": q[:120], "cosine_pct": c} for i, q, c in bottom5
                ],
                "pseudo_reference_note": "Pseudo-reference مولّد آلياً من شطر/ملخص إجابة faq.txt وليس مرجعاً بشرياً معتمداً",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_CSV} and {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
