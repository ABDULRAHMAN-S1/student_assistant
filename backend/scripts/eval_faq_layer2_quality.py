# -*- coding: utf-8 -*-
"""
طبقة ثانية: صحة/اكتمال/وضوح (0–5) + متوسط = overall_quality
يعتمد على: تضمين متعدد اللغات + نسبة طول + قواعد تناقض خفيفة
(لا يعادل حكماً بشرياً).
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
INP = ROOT / "data" / "processed" / "faq_ref_natural_v2_tfidf.csv"
OUT_CSV = ROOT / "data" / "processed" / "faq_layer2_quality.csv"
OUT_JSON = ROOT / "data" / "processed" / "faq_layer2_quality.json"

# نموذج تضمين خفيف متعدد اللغات
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"


def clean_for_len(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s


def has_hard_conflict(ref: str, gen: str) -> bool:
    r, g = ref.lower() if ref else "", gen.lower() if gen else ""
    r, g = clean_for_len(r), clean_for_len(g)
    if len(r) < 30 and r.strip().rstrip(".") in ("لا", "نعم", "يمكن") and g:
        if r.strip().lstrip()[:2] == "لا" and ("نعم" in g[:25] and "غير" not in g[:30]):
            if "هذا غير" not in g and "غير متاح" not in g:
                return True
    pairs = [("لا يجوز", "يُجوز",), ("لا يحق", "يحق",), ("لا يمكن", "يمكن ")]
    for a, b in pairs:
        if a in r and b in g and a not in g:
            if "لا" not in g[:40]:
                return True
    return False


def score_completeness(ref: str, gen: str) -> float:
    r, g = clean_for_len(ref), clean_for_len(gen)
    if not g:
        return 0.0
    if not r:
        return 3.0
    lr, lg = max(len(r), 1), max(len(g), 1)
    ratio = min(lg / lr, 2.0)
    if len(r) <= 12 and len(g) > len(r) * 1.2:
        return 4.5
    if ratio >= 0.88:
        s = 5.0
    elif ratio >= 0.65:
        s = 4.0
    elif ratio >= 0.4:
        s = 3.0
    elif ratio >= 0.2:
        s = 2.0
    else:
        s = 1.0
    if lg < 10 and lr > 30:
        s = min(s, 2.0)
    return s


def score_clarity(gen: str) -> float:
    g = clean_for_len(gen)
    if not g:
        return 0.0
    lg = len(g)
    if lg < 8:
        return 2.0
    if lg < 20:
        return 3.5
    nlines = g.count("\n")
    if nlines > 0 and 50 < lg < 4000:
        return 4.5
    if 30 <= lg <= 8000:
        return 4.0
    if lg > 12000:
        return 3.0
    return 3.5


def to_note(c: float, o: float, cl: float, confl: bool, low_cov: bool) -> str:
    if confl:
        return "مؤشر تناقض دلالي/إجرائي يلزم مراجعته"
    if c < 2.5 and o < 3.0 and cl >= 3.5:
        return "وضوح مقبول لكن محتوى المرجع غير مُناسَب بما يكفي"
    if low_cov:
        return "نقص تغطية مقارنة بالنص المرجعي (اكتمال)"
    if o >= 4.0:
        return "تقدير إجمالي جيد: اتساق ومعالجة معقولة"
    if o < 2.5:
        return "جودة منخفضة: اضعف في الصحة/الدليل أو الاكتمال"
    return "وضع متوسط: وُجد تباين بين السطحي والمضمون"


def run() -> int:
    if not INP.is_file():
        print(f"Missing {INP}", file=sys.stderr)
        return 1
    from sentence_transformers import SentenceTransformer

    with INP.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("empty csv", file=sys.stderr)
        return 1

    model = SentenceTransformer(MODEL_NAME)
    texts: list[str] = []
    for r in rows:
        texts.append(clean_for_len(r.get("reference_answer", "")))
        texts.append(clean_for_len(r.get("generated_answer", "")))
    emb = model.encode(texts, show_progress_bar=False, convert_to_numpy=True, normalize_embeddings=True)

    out: list[dict] = []
    for idx, r in enumerate(rows):
        i_ref, i_gen = 2 * idx, 2 * idx + 1
        dot = float(np.dot(emb[i_ref], emb[i_gen]))
        ecos_01 = max(0.0, min(1.0, (dot + 1.0) / 2.0))
        c_raw = 0.5 + 4.5 * ecos_01
        if has_hard_conflict(r.get("reference_answer", ""), r.get("generated_answer", "")):
            c_raw = max(0.0, c_raw - 1.5)
        correctness = float(np.clip(np.round(c_raw, 1), 0, 5))

        comp = float(score_completeness(r.get("reference_answer", ""), r.get("generated_answer", "")))
        clar = float(score_clarity(r.get("generated_answer", "")))
        confl = has_hard_conflict(r.get("reference_answer", ""), r.get("generated_answer", ""))
        low_cov = comp < 2.5 and len(clean_for_len(r.get("reference_answer", ""))) > 50

        overall = round((correctness + comp + clar) / 3.0, 2)
        note = to_note(correctness, comp, clar, confl, low_cov)

        try:
            cos_t = float(r.get("cosine_similarity_pct", "0") or 0)
        except ValueError:
            cos_t = 0.0

        out.append(
            {
                "question_id": r.get("question_id", idx + 1),
                "cosine_similarity_pct": round(cos_t, 2),
                "correctness_score": correctness,
                "completeness_score": comp,
                "clarity_score": clar,
                "overall_quality_score": overall,
                "evaluation_note": note,
            }
        )

    n = len(out)
    mean_cos = round(sum(x["cosine_similarity_pct"] for x in out) / n, 2)
    mean_oq = round(sum(x["overall_quality_score"] for x in out) / n, 2)

    high_cos_low_q = sum(
        1 for x in out if x["cosine_similarity_pct"] > 60 and x["overall_quality_score"] < 2.5
    )
    low_cos_high_q = sum(
        1 for x in out if x["cosine_similarity_pct"] < 45 and x["overall_quality_score"] >= 3.5
    )

    issues: list[str] = []
    if mean_oq < 3.0:
        issues.append("متوسط جودة إجمالي دون التوقع حسب الضبط الآلي")
    if high_cos_low_q:
        issues.append("كثرة حالات تشابه سطحي مرتفع مع جودة إجمالية منخفضة (نقص اكتمال/صحة مُلحوظة)")
    if low_cos_high_q:
        issues.append("تداخل: تشابه نصي منخفض لكن تقدير دلالي/شكلي أوفر؛ راجع الاعتماد على Cosine وحدفه")
    lo_comp = sum(1 for r in out if r["completeness_score"] < 2.5)
    if lo_comp > n * 0.2:
        issues.append("نسبة مرتفعة نسبيًا لضعف الاكتمال بمقارنة أطوال النصوص")
    if len(issues) < 3:
        issues.append("اعتماد التضمين لمعنى الصحة يلزم الاستكمال بعينة بشرية للإنتاج")
    if len(issues) < 3:
        issues.append("تكرار بادئات/صيغ قد يرفع الضوضاء دون مضمون إضافي")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "question_id",
                "cosine_similarity_pct",
                "correctness_score",
                "completeness_score",
                "clarity_score",
                "overall_quality_score",
                "evaluation_note",
            ],
        )
        w.writeheader()
        w.writerows(out)

    OUT_JSON.write_text(
        json.dumps(
            {
                "source_rows": str(INP),
                "embedding_model": MODEL_NAME,
                "n": n,
                "mean_cosine_tfidf": mean_cos,
                "mean_overall_quality": mean_oq,
                "count_high_cosine_low_quality": high_cos_low_q,
                "count_low_cosine_high_quality": low_cos_high_q,
                "top_3_system_issues": issues[:3],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(OUT_CSV, mean_cos, mean_oq, file=sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
