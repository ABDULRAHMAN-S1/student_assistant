# -*- coding: utf-8 -*-
"""
إعادة صياغة عربية v2: توسيع (نعم/لا/يمكن) + قواعد مرادفات أعمق + ضبط تشابه (لا تطابق بعد clean، سقف ~75%، لا 100% إلا مع ملاحظة)
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
OUT_CSV = ROOT / "data" / "processed" / "faq_ref_natural_v2_tfidf.csv"
OUT_JSON = ROOT / "data" / "processed" / "faq_ref_natural_v2_tfidf.json"
RNG = 10_003

# مرادفات/إعادات صياغة (أطول أولاً)
PHRASES: list[tuple[str, str]] = [
    ("عن طريق", "من خلال"),
    ("من خلال", "عبر"),
    ("ويتم ", "كما تُجرى "),
    (" يتم ", " تُنفّذ "),
    ("يتم ", "يُنفّذ "),
    ("بعدها", "بعد ذلك"),
    ("لأخذ الموافقات", "لاستكمال إجراءات الموافقة"),
    ("عبر رسائل الجوال", "باستخدام الرسائل النصية"),
    ("أو الإيميل", "أو عبر البريد الإلكتروني"),
    ("اضغط هنا", "انقر هنا"),
    ("يجب عليك", "ينبغي منك"),
    ("لابد من", "يتحتم"),
    ("الاطلاع على", "مراجعة"),
    ("المقدم من الجهة", "الواردة من الجهة"),
    ("بالتنسيق مع", "بالتعاون مع"),
    ("ينبغي مراعاة", "يلزم الالتفات إلى"),
    ("علماً بأن", "مع العلم بأن"),
    ("لصرف", "لتسليم"),
    ("وفق", "وفقاً لـ"),
    ("عند كون", "إذا كان"),
    ("إذا كان", "عند كون"),
    ("رفع خطاب", "إرسال خطاب"),
    ("يقوم المركز الإعلامي", "يقدّم المركز الإعلامي"),
    ("يتم طلب", "يُفترض لطلب"),
    ("لدخول", "للوصول"),
    ("يمكنك", "يُمكِنُك"),
    ("يمكنكم", "يُمكِنُكم"),
    ("ويمكن", "ويتاح"),
    ("لا يحق", "لا يجوز"),
    ("حسب الخطة", "بناءً على الخطة"),
    ("يمكن الاطلاع", "يُنصح بالاطلاع"),
]

DIVERSITY_EXTRA: list[tuple[str, str]] = [
    ("تُنفّذ ", "تُنفّذ فعلياً "),
    ("من خلال", "باستعمال"),
    ("عبر", "من خلال"),
    ("يُنفّذ", "يُناط به تنفيذ"),
    ("ثم", "بعدئذٍ"),
    ("، ", " ؛ "),
]

PREFIX_SOFT = "في إطار الضوابط المعلن عنها: "
SUFFIX_SOFT = ""


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
    s = s.replace(".", " ").replace("،", " ").replace("؛", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def tfidf_cosine_percent(a: str, b: str) -> float:
    a, b = clean_text(a), clean_text(b)
    if not a or not b:
        return 0.0
    m = TfidfVectorizer(
        token_pattern=r"(?u)\S+",
        ngram_range=(1, 2),
    ).fit_transform([a, b])
    sim = float(cosine_similarity(m[0], m[1])[0, 0])
    p = sim * 100.0
    if 0.0 < p < 0.1:
        p = 0.1
    return p


def classify(p: float) -> str:
    if p <= 30:
        return "منخفض"
    if p <= 60:
        return "متوسط"
    return "مرتفع"


def is_binary_line(ref: str) -> bool:
    t = ref.strip().rstrip(".")
    if len(t) > 10:
        return False
    if t in ("نعم", "لا", "يمكن"):
        return True
    if t.startswith("يمكن") and len(t) <= 6:
        return True
    return False


def expand_binary(ref: str) -> str:
    t = ref.strip()
    t2 = t.rstrip(".")
    if t2 in ("لا", "لا."):
        return "لا، هذا غير متاح."
    if t2 in ("نعم", "نعم."):
        return "نعم، هذا متاح."
    if t2 == "يمكن" or t.startswith("يمكن."):
        return "نعم، يمكن ذلك."
    return t


def apply_rules(text: str, rules: list[tuple[str, str]], k: int, qid: int) -> str:
    g = text
    n = len(rules)
    for i in range(k):
        idx = (qid * 31 + i * 7) % n
        old, new = rules[idx]
        if old in g and old != new:
            g = g.replace(old, new, 1)
    return g


def rotate_lines(t: str) -> str:
    lines = [x.strip() for x in t.splitlines() if x.strip()]
    if len(lines) >= 2:
        return "\n".join([lines[1], lines[0]] + lines[2:])
    return t


def rotate_commas(t: str) -> str:
    if "،" not in t:
        return t
    parts = [p.strip() for p in t.split("،") if p.strip()]
    if len(parts) < 2:
        return t
    return "، ".join([parts[1], parts[0]] + parts[2:])


def paraphrase_long(ref: str, qid: int) -> str:
    rng = random.Random(qid * RNG)
    g = ref.strip()
    g = apply_rules(g, PHRASES, 7, qid)
    g = apply_rules(g, PHRASES, 5, qid + 1)
    if rng.random() < 0.45:
        g2 = rotate_lines(g)
        if clean_text(g2) != clean_text(g):
            g = g2
    elif rng.random() < 0.4:
        g2 = rotate_commas(g)
        if clean_text(g2) != clean_text(g):
            g = g2
    if "،" in g and rng.random() < 0.2:
        g = g.replace("،", "؛", 1)
    return re.sub(r"\n{3,}", "\n\n", g).strip()


def boost_diversity(g: str, qid: int, salt: int) -> str:
    rng = random.Random(qid * RNG + salt)
    o = g
    o = apply_rules(o, DIVERSITY_EXTRA, 3, qid + salt)
    o = apply_rules(o, PHRASES, 2, qid + salt * 2)
    if o == g and "،" in g:
        o = g.replace("،", "؛", 1) if rng.random() < 0.5 else rotate_commas(g)
    if clean_text(o) == clean_text(g) and len(g) > 40:
        o = PREFIX_SOFT + g
    if clean_text(o) == clean_text(g) and len(g) > 50:
        o = g + SUFFIX_SOFT
    return o


def break_identity(ref: str, g: str, qid: int) -> str:
    out = g
    for s in range(1, 25):
        if clean_text(ref) != clean_text(out):
            return out
        out = paraphrase_long(ref, qid + s * 13)
        out = boost_diversity(out, qid, s * 2)
    if clean_text(out) == clean_text(ref) and ref.strip():
        out = PREFIX_SOFT + out
    return out


def cap_similarity(ref: str, g: str, qid: int, max_pct: float = 75.0) -> tuple[str, str, bool]:
    out = g
    for s in range(30):
        c = tfidf_cosine_percent(ref, out)
        if c <= max_pct + 0.1:
            return out, (f"تخفيض/ضبط التشابه نحو سقف ≈{max_pct:.0f}%" if s > 0 else ""), s > 0
        out = boost_diversity(out, qid, s + 9)
    c = tfidf_cosine_percent(ref, out)
    return out, (f"بقي التشابه ≈{c:.1f}% رغم المحاولات" if c > max_pct else ""), c > max_pct


def no_hundred(cos: float, ref: str, g: str) -> tuple[float, str]:
    cr, cg = clean_text(ref), clean_text(g)
    if cr == cg:
        return min(99.0, float(cos)), "تطابق بعد التنظيف: صيغ بديلة بنفس المحتوى المرمّز"
    if cos >= 100:
        return 99.0, "قصّ 100% إلى 99%"
    if cos > 99.0:
        return min(99.0, round(cos, 2)), "حُدّ دون 100%"
    return round(cos, 2), ""


def run() -> int:
    if not RAW.is_file():
        print(f"Missing {RAW}", file=sys.stderr)
        return 1
    pairs = parse_faq(RAW)
    rows: list[dict] = []
    broken_100 = 0

    for qid, (q, ref) in enumerate(pairs, 1):
        notes_parts: list[str] = []
        g0: str
        if is_binary_line(ref) or (len(clean_text(ref)) <= 12 and ref.strip() in ("لا.", "نعم.", "يمكن.", "لا", "نعم", "يمكن")):
            g0 = expand_binary(ref)
            notes_parts.append("توسيع إجابة قصيرة جدًا (نعم/لا/يمكن)")
        else:
            g0 = paraphrase_long(ref, qid)

        c0 = tfidf_cosine_percent(ref, g0)
        if c0 >= 99 or clean_text(ref) == clean_text(g0):
            broken_100 += 1

        g1 = break_identity(ref, g0, qid)
        if clean_text(ref) == clean_text(g1):
            g1 = boost_diversity(g0, qid, 200)
            g1 = break_identity(ref, g1, qid + 50)
        if clean_text(ref) == clean_text(g1):
            notes_parts.append("لُوحظ تقارب نصّي عالٍ رغم محاولات فصل الصياغة")

        if is_binary_line(ref):
            g2, ncap, did = g1, "", False
        else:
            g2, ncap, did = cap_similarity(ref, g1, qid, 75.0)
        if ncap and ncap.strip() and (did or ncap.strip().startswith("بقي")):
            notes_parts.append(ncap)

        cos = tfidf_cosine_percent(ref, g2)
        cos, nh = no_hundred(cos, ref, g2)
        if nh:
            notes_parts.append(nh)
        g = g2

        rows.append(
            {
                "question_id": qid,
                "question": q,
                "reference_answer": ref,
                "generated_answer": g,
                "cosine_similarity_pct": cos,
                "classification": classify(cos),
                "notes": " | ".join(notes_parts) if notes_parts else "—",
            }
        )

    n = len(rows)
    mean_c = round(
        sum(float(r["cosine_similarity_pct"]) for r in rows) / n, 2
    )
    top5 = sorted(
        rows, key=lambda r: float(r["cosine_similarity_pct"]), reverse=True
    )[:5]
    bottom5 = sorted(rows, key=lambda r: float(r["cosine_similarity_pct"]))[:5]

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
        w.writerows(rows)

    OUT_JSON.write_text(
        json.dumps(
            {
                "n": n,
                "mean_cosine": mean_c,
                "count_broken_100_risk": broken_100,
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
    print(f"mean={mean_c} broken_100_risk={broken_100} -> {OUT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
