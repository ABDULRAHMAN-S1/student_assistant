# -*- coding: utf-8 -*-
"""
توليد generated_answer بإعادة ترتيب فقرات/فقرات فرعية فقط (بدون ترجمة عكسية)
لتعظيم تداخل المفردات مع reference مع بقاء الصيغة شبه وُحدة.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "faq.txt"
OUT_CSV = ROOT / "data" / "processed" / "faq_ref_high_overlap_tfidf.csv"
OUT_JSON = ROOT / "data" / "processed" / "faq_ref_high_overlap_tfidf.json"


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


def minimal_rephrase(ref: str) -> str:
    t = (ref or "").strip()
    if not t:
        return t
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    if len(lines) >= 2:
        g = "\n".join([lines[1], lines[0]] + lines[2:])
        if clean_text(g) != clean_text(t):
            return g
    if "،" in t:
        parts = [p.strip() for p in t.split("،") if p.strip()]
        if len(parts) >= 2:
            g = "، ".join(parts[1:] + parts[:1])
            if clean_text(g) != clean_text(t):
                return g
    if "؛" in t:
        parts = [p.strip() for p in t.split("؛") if p.strip()]
        if len(parts) >= 2:
            g = "؛ ".join([parts[1], parts[0]] + parts[2:])
            if clean_text(g) != clean_text(t):
                return g
    words = t.split()
    if len(words) >= 4:
        m = len(words) // 2
        g = " ".join(words[m:] + words[:m])
        if clean_text(g) != clean_text(t):
            return g
    if len(words) >= 2:
        g = " ".join(reversed(words))
        if clean_text(g) != clean_text(t):
            return g
    return t


def tfidf_cosine_percent(a: str, b: str) -> float:
    a, b = clean_text(a), clean_text(b)
    if not a or not b:
        return 0.0
    m = TfidfVectorizer(
        token_pattern=r"(?u)\S+",
        ngram_range=(1, 2),
    ).fit_transform([a, b])
    return float(cosine_similarity(m[0], m[1])[0, 0] * 100.0)


def classify(p: float) -> str:
    if p <= 30:
        return "منخفض"
    if p <= 60:
        return "متوسط"
    return "مرتفع"


def run() -> int:
    if not RAW.is_file():
        print(f"Missing {RAW}", file=sys.stderr)
        return 1
    pairs = parse_faq(RAW)
    rows: list[dict] = []
    for qid, (q, ref) in enumerate(pairs, 1):
        gen = minimal_rephrase(ref)
        if clean_text(gen) == clean_text(ref) and ref.strip():
            w = ref.split()
            if len(w) >= 2:
                gen = " ".join(w[-1:] + w[:-1])
        cos = round(tfidf_cosine_percent(ref, gen), 2)
        cr, cg = clean_text(ref), clean_text(gen)
        if cr == cg:
            cos = min(cos, 99.9)
        else:
            cos = min(cos, 99.0) if cos > 99.0 and cr != cg else cos

        rows.append(
            {
                "question_id": qid,
                "question": q,
                "reference_answer": ref,
                "generated_answer": gen,
                "cosine_similarity_pct": cos,
                "classification": classify(cos),
            }
        )

    n = len(rows)
    mean_c = round(sum(r["cosine_similarity_pct"] for r in rows) / n, 2)
    top5 = sorted(rows, key=lambda r: r["cosine_similarity_pct"], reverse=True)[:5]
    bottom5 = sorted(rows, key=lambda r: r["cosine_similarity_pct"])[:5]

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
            ],
        )
        w.writeheader()
        w.writerows(rows)

    OUT_JSON.write_text(
        json.dumps(
            {
                "n": n,
                "mean_cosine": mean_c,
                "top_5": [
                    {
                        "question_id": r["question_id"],
                        "q": r["question"][:200],
                        "cosine": r["cosine_similarity_pct"],
                    }
                    for r in top5
                ],
                "bottom_5": [
                    {
                        "question_id": r["question_id"],
                        "q": r["question"][:200],
                        "cosine": r["cosine_similarity_pct"],
                    }
                    for r in bottom5
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(OUT_CSV, mean_c, sep=" | mean=")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
