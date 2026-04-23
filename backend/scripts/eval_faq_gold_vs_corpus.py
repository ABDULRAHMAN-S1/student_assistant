# -*- coding: utf-8 -*-
"""
مقارنة إجابات faq.txt (المرجع الرسمي) بمقاطع مسترجَعة من بقية ملفات data/raw
لأن الملفات الأخرى ليست بصيغة (سؤال/جواب) مثل faq. لكل سؤال مرجعي نختار
الفقرة الأكثر تشابهاً لِلسّؤال (TF-IDF + Cosine)، ثم نحسب التشابه بين
إجابة faq وذلك المقطع.
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
RAW = ROOT / "data" / "raw"
REF_FILE = "faq.txt"
OUT_CSV = ROOT / "data" / "processed" / "faq_gold_vs_corpus_tfidf.csv"
OUT_JSON = ROOT / "data" / "processed" / "faq_gold_vs_corpus_tfidf.json"

# سؤال-مقطع: عتبة دنيا (اقتراب معجمي) لاعتبار المقتطع «مرشّحاً» للمقارنة. أقل منها = استبعاد
MIN_Q_CH_SIM = 0.05
MIN_CHARS_CHUNK = 45


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


def split_chunks(text: str) -> list[str]:
    """تقسيم إلى فقرات/مقاطع بحد أدنى طول."""
    parts = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for p in parts:
        p = p.strip()
        if len(p) < MIN_CHARS_CHUNK:
            continue
        if len(p) > 5000:
            for sub in re.split(r"(?<=[.;؛\n])", p):
                sub = sub.strip()
                if len(sub) >= MIN_CHARS_CHUNK:
                    out.append(sub[:5000])
        else:
            out.append(p)
    return out


def load_corpus_excluding_faq() -> list[tuple[str, str, str]]:
    """قائمة (مسار_نسبي، فقرة، نص_منقّح)."""
    rows: list[tuple[str, str, str]] = []
    for f in sorted(RAW.glob("*.txt")):
        name = f.name
        if name == REF_FILE:
            continue
        try:
            body = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ch in split_chunks(body):
            c = clean_text(ch)
            if len(c) < 25:
                continue
            rows.append((name, ch.strip(), c))
    return rows


def classify(p: float) -> str:
    if p <= 30:
        return "منخفض"
    if p <= 60:
        return "متوسط"
    return "مرتفع"


def run() -> int:
    ref_path = RAW / REF_FILE
    if not ref_path.is_file():
        print(f"Missing {ref_path}", file=sys.stderr)
        return 1

    pairs = parse_faq(ref_path)
    if not pairs:
        print("No FAQ pairs", file=sys.stderr)
        return 1

    corpus = load_corpus_excluding_faq()
    if not corpus:
        print("No non-faq corpus", file=sys.stderr)
        return 1

    chunk_raw = [c[1] for c in corpus]
    chunk_cln = [c[2] for c in corpus]
    chunk_file = [c[0] for c in corpus]

    questions = [clean_text(q) for q, _ in pairs]
    ref_ans = [clean_text(a) for _, a in pairs]

    fit_docs = chunk_cln + questions + [a for a in ref_ans if a]
    vec = TfidfVectorizer(
        token_pattern=r"(?u)\S+",
        ngram_range=(1, 2),
        min_df=1,
    )
    vec.fit(fit_docs)
    M_c = vec.transform(chunk_cln)
    M_q = vec.transform(questions)
    M_a = vec.transform(ref_ans)
    # تشابه سؤال–مقطع
    sim_qc = cosine_similarity(M_q, M_c)
    # تشابه إجابة مرجعية–نفس المقطع (نفس الـvocab)
    sim_ac = cosine_similarity(M_a, M_c)

    out_rows: list[dict] = []
    n_total = len(pairs)
    n_eval = 0
    n_skip = 0

    for i0, (q_raw, a_raw) in enumerate(pairs):
        qid = i0 + 1
        j = int(sim_qc[i0].argmax())
        q_ch_sim = float(sim_qc[i0, j])
        ra_sim = float(sim_ac[i0, j])

        if q_ch_sim < MIN_Q_CH_SIM:
            n_skip += 1
            out_rows.append(
                {
                    "question_id": qid,
                    "question": q_raw,
                    "reference_answer": a_raw,
                    "generated_answer": "",
                    "q_chunk_sim": round(q_ch_sim * 100, 2),
                    "cosine_similarity_pct": "",
                    "classification": "مستبعد",
                    "notes": f"تشابه السؤال مع أي مقطع في بقية المدونة {q_ch_sim*100:.2f}% < عتبة {MIN_Q_CH_SIM*100}%.",
                }
            )
            continue

        # لا نمنح 100% إلا إن كان التنظيف يساوي
        c_raw = chunk_raw[j]
        cp = clean_text(a_raw)
        cg = clean_text(c_raw)
        if cp and cp == cg:
            final_pct = 100.0
        else:
            final_pct = round(ra_sim * 100, 2)
            if final_pct > 99.5 and ra_sim < 0.999:
                final_pct = min(final_pct, 99.0)

        n_eval += 1
        out_rows.append(
            {
                "question_id": qid,
                "question": q_raw,
                "reference_answer": a_raw,
                "generated_answer": c_raw,
                "q_chunk_sim": round(q_ch_sim * 100, 2),
                "cosine_similarity_pct": final_pct,
                "classification": classify(final_pct),
                "notes": f"مقتطع من: {chunk_file[j]} (تقريب تطابق سؤال–مقطع: {q_ch_sim*100:.2f}%)",
            }
        )

    mean_cos = None
    scored = [r for r in out_rows if r["cosine_similarity_pct"] != ""]
    if scored:
        mean_cos = round(
            sum(float(r["cosine_similarity_pct"]) for r in scored) / len(scored), 2
        )
    top5 = sorted(
        (
            (r["question_id"], r["question"], float(r["cosine_similarity_pct"]))
            for r in scored
        ),
        key=lambda x: x[2],
        reverse=True,
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
                "q_chunk_match_pct",
                "cosine_similarity_pct",
                "classification",
                "notes",
            ],
        )
        w.writeheader()
        for r in out_rows:
            w.writerow(
                {
                    "question_id": r["question_id"],
                    "question": r["question"],
                    "reference_answer": r["reference_answer"],
                    "generated_answer": r["generated_answer"],
                    "q_chunk_match_pct": r.get("q_chunk_sim", ""),
                    "cosine_similarity_pct": r["cosine_similarity_pct"],
                    "classification": r["classification"],
                    "notes": r["notes"],
                }
            )

    summary = {
        "reference_gold_file": str(ref_path),
        "comparison_source_files": sorted(
            {n for n in chunk_file}
        ),
        "total_reference_questions": n_total,
        "evaluated_count": n_eval,
        "excluded_count": n_skip,
        "mean_cosine_pct": mean_cos,
        "top_5": [
            {"question_id": a, "question": b[:200], "cosine_pct": c} for a, b, c in top5
        ],
        "bottom_5": [
            {"question_id": a, "question": b[:200], "cosine_pct": c} for a, b, c in bottom5
        ],
        "methodology": (
            "بقية الملفات ليست FAQ؛ تُمثّل «الإجابة المراد تقييمها» بأقرب فقرة من تلك المدونة "
            f"لِلسّؤال (عتبة min تشابه سؤال-مقطع: {MIN_Q_CH_SIM*100}%)."
        ),
    }
    OUT_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {OUT_CSV}\nWrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
