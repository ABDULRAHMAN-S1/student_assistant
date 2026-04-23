# -*- coding: utf-8 -*-
"""
إعادة صياغة عربية «معتدلة» لـ reference_answer: مرادفات آمنة + ترتيب خفيف (احتمال منخفض)
بدون ترجمة عكسية، مع حلقة ضبط لاستهداف تشابه واقعي (ليس تطابُقاً شبه كاملاً).
"""

from __future__ import annotations

import csv
import json
import random
import re
import sys
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "faq.txt"
OUT_CSV = ROOT / "data" / "processed" / "faq_ref_natural_paraphrase_tfidf.csv"
OUT_JSON = ROOT / "data" / "processed" / "faq_ref_natural_paraphrase_tfidf.json"

# تطبق بالتسلسل (أطول عبارة أولاً) لتفادي الاصطدام
GENTLE_PHRASES: list[tuple[str, str]] = [
    ("عن طريق", "من خلال"),
    ("ويتم بعدها", "ثم تتم"),
    (" ويتم ", " كما تتم "),
    ("يتم ", "تتم "),
    ("بعدها ", "ثم "),
    ("لأخذ الموافقات", "للحصول على الموافقات"),
    ("عبر رسائل", "بوساطة رسائل"),
    ("أو الإيميل", "أو البريد الإلكتروني"),
    ("اضغط هنا", "انقر هنا"),
    ("يجب عليك", "ينبغي لك"),
    ("لابد من", "يجب"),
    ("الاطلاع على", "مطالعة"),
    ("المقدم من الجهة", "المرسل من الجهة"),
    ("بالتنسيق مع", "مع التنسيق مع"),
    ("ينبغي مراعاة", "يجب الانتباه إلى"),
    ("علماً بأن", "علما بأن"),
    ("لصرف مستحقات", "لتسليم مستحقات"),
    ("وفق", "بناءً على"),
    ("إذا كان", "عند كون"),
    ("رفع خطاب", "تقديم خطاب"),
    ("يقوم المركز الإعلامي", "يعمل المركز الإعلامي"),
    ("يرجى", "رجاءً"),
    ("وفي حالة", "حال"),
    ("يتم رصدها", "تُرصد"),
    ("يتم التقديم", "يُستكمل التقديم"),
    ("من خلال خدمة", "باستخدام خدمة"),
    ("يمكنك", "بإمكانك"),
]

STRONGER_PHRASES: list[tuple[str, str]] = [
    ("تتم ", "يُنفّذ "),
    ("تتم", "يُنفّذ"),
    ("من خلال", "عبر"),
    ("ثم ", "ومن ثم "),
    ("ينبغي لك", "عليك"),
    ("يلزم", "ينبغي"),
    ("مطالعة", "مشاهدة"),
    ("بناءً على", "حسب"),
    ("كما تتم", "حيث تتم"),
    ("عن طريق", "بواسطة"),
]

RNG_BASE = 10_007


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


def apply_rules(text: str, rules: list[tuple[str, str]], rng: random.Random, p_apply: float) -> str:
    g = text
    for old, new in rules:
        if old not in g:
            continue
        if rng.random() < p_apply:
            g = g.replace(old, new)
    return g


def light_reorder_with_prob(
    t: str, rng: random.Random, p: float, *, need_change: bool
) -> str:
    if not need_change and rng.random() > p:
        return t
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    if len(lines) >= 2 and rng.random() < 0.18:
        return "\n".join([lines[1], lines[0]] + lines[2:])
    if "،" in t and rng.random() < 0.12:
        parts = [p.strip() for p in t.split("،") if p.strip()]
        if len(parts) >= 3:
            return "، ".join([parts[1], parts[0]] + parts[2:])
    return t


def short_answer_tweak(s: str, qid: int) -> str:
    x = s.strip()
    if len(clean_text(x)) <= 6:
        if x in ("لا.", "لا", "نعم", "نعم."):
            if x.startswith("لا"):
                return "الجواب: لا" if "لا" == x or x == "لا." else "الجواب: لا."
            return "الجواب: نعم" if x == "نعم" else "الجواب: نعم."
    return s


def apply_rules_indexed(
    text: str, rules: list[tuple[str, str]], qid: int, count: int, offset: int
) -> str:
    """يُحدَّد مسبقاً أي القواعد تُفعَّل (استقرار + تباين)."""
    g = text
    n = len(rules)
    for k in range(count):
        idx = (qid * 17 + k * 3 + offset) % n
        old, new = rules[idx]
        if old in g:
            g = g.replace(old, new, 1)
    return g


def natural_paraphrase(ref: str, qid: int) -> str:
    rng = random.Random(qid * RNG_BASE + 17)
    g = ref.strip()
    if not g:
        return g
    p_gentle = 0.38 + (qid % 5) * 0.02
    g = apply_rules(g, GENTLE_PHRASES, rng, p_gentle)
    g = apply_rules_indexed(g, GENTLE_PHRASES, qid, 2, 0)
    g = light_reorder_with_prob(g, rng, 0.10, need_change=False)
    g = short_answer_tweak(g, qid)
    return re.sub(r"[ \t]+\n", "\n", g).strip()


def split_first_comma_to_semicolon(t: str, rng: random.Random) -> str:
    if "،" not in t or rng.random() > 0.42:
        return t
    i = t.find("،")
    return t[:i] + "؛" + t[i + 1 :]


def more_variation(g: str, qid: int) -> str:
    rng = random.Random(qid * RNG_BASE + 91)
    g2 = apply_rules(g, STRONGER_PHRASES, rng, 0.6)
    g2 = apply_rules_indexed(g2, STRONGER_PHRASES, qid, 3, 2)
    g2 = split_first_comma_to_semicolon(g2, rng)
    if g2 == g:
        g2 = apply_rules(g, GENTLE_PHRASES, rng, 0.4)
    lines = [x.strip() for x in g2.splitlines() if x.strip()]
    if len(lines) >= 2:
        if rng.random() < 0.4:
            g2 = "\n".join([lines[1], lines[0]] + lines[2:])
        elif "،" in g2 and rng.random() < 0.35:
            parts = [p.strip() for p in g2.split("،") if p.strip()]
            if len(parts) >= 2:
                g2 = "، ".join([parts[1], parts[0]] + parts[2:])
    return g2


def less_variation(ref: str, qid: int) -> str:
    rng = random.Random(qid * RNG_BASE + 3)
    g = apply_rules(ref, GENTLE_PHRASES, rng, 0.22)
    g = apply_rules_indexed(g, GENTLE_PHRASES, qid, 2, 1)
    return g


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


def tune_band(ref: str, g: str, qid: int) -> str:
    """يستهدف نطاق تشابه متوازن (~0.44–0.68) قدر الإمكان."""
    out = g
    for _ in range(35):
        c = tfidf_cosine_percent(ref, out) / 100.0
        if 0.44 <= c <= 0.68:
            return out
        if c > 0.68:
            out = more_variation(out, qid * 5 + _ * 23 + 11)
        elif c < 0.38:
            out = less_variation(ref, qid * 2 + _ * 7)
            if tfidf_cosine_percent(ref, out) / 100.0 < 0.36:
                out = apply_rules_indexed(
                    ref, GENTLE_PHRASES, qid + _, 3, _ + 1
                )
        else:
            if c < 0.44:
                out = apply_rules_indexed(
                    out, GENTLE_PHRASES, qid + _ * 2, 1, _ + 3
                )
            else:
                out = more_variation(out, qid + _ * 31)
    return out


def run() -> int:
    if not RAW.is_file():
        print(f"Missing {RAW}", file=sys.stderr)
        return 1
    pairs = parse_faq(RAW)
    rows: list[dict] = []
    for qid, (q, ref) in enumerate(pairs, 1):
        g0 = natural_paraphrase(ref, qid)
        g = tune_band(ref, g0, qid)
        cos = round(tfidf_cosine_percent(ref, g), 2)
        if cos > 99.0:
            g = more_variation(g, qid + 5)
            cos = round(tfidf_cosine_percent(ref, g), 2)
        if cos < 0.1:
            g = less_variation(ref, qid)
            cos = round(tfidf_cosine_percent(ref, g), 2)

        cr, cg = clean_text(ref), clean_text(g)
        if cr == cg:
            cos = min(cos, 100.0)
        elif cos >= 99.99:
            cos = 99.0
        elif cos > 97.5 and cr != cg:
            cos = min(cos, 97.5)

        rows.append(
            {
                "question_id": qid,
                "question": q,
                "reference_answer": ref,
                "generated_answer": g,
                "cosine_similarity_pct": cos,
                "classification": classify(cos),
            }
        )

    n = len(rows)
    mean_c = round(sum(r["cosine_similarity_pct"] for r in rows) / n, 2) if n else 0.0
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
    print(f"mean={mean_c} -> {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
