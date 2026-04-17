"""Retrieval and answer quality benchmark for the student assistant RAG system.

Measures four key metrics across any number of saved configuration runs, enabling
an apples-to-apples comparison between:
  - baseline  : current bi-encoder only (no reranking)
  - reranker  : bi-encoder + cross-encoder reranker (ENABLE_RERANKING=true)
  - e5        : intfloat/multilingual-e5-large bi-encoder (after rebuild)
  - e5-reranker: e5 bi-encoder + cross-encoder reranker

Usage
-----
  # 1. Run evaluation against the current active configuration
  python -m app.eval_benchmark run --name baseline

  # 2. Enable reranking, then run again
  #    (set ENABLE_RERANKING=true in environment)
  python -m app.eval_benchmark run --name reranker

  # 3. After rebuilding with e5 model:
  #    EMBEDDING_MODEL=intfloat/multilingual-e5-large python -m app.embed_store --rebuild
  #    python -m app.eval_benchmark run --name e5

  # 4. e5 + reranker:
  #    python -m app.eval_benchmark run --name e5-reranker

  # 5. Compare all saved results:
  python -m app.eval_benchmark compare

  # 6. Compare specific result files:
  python -m app.eval_benchmark compare data/eval/results/baseline.json data/eval/results/reranker.json

Metrics
-------
  hit@1, hit@2, hit@4   Fraction of questions where the expected source doc
                        appears in the top-1 / top-2 / top-4 results.
  mrr                   Mean Reciprocal Rank (rank of first expected source hit).
  keyword_coverage      Fraction of reference_keywords found in the answer text.
  fallback_rate         Fraction of answers that returned the "not found" fallback.
  confidence_high/med/low  Distribution of the three confidence levels.
  avg_latency_ms        Average wall-clock time per question in milliseconds.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EVAL_DIR = DATA_DIR / "eval"
RESULTS_DIR = EVAL_DIR / "results"
DEFAULT_QUESTIONS_PATH = EVAL_DIR / "eval_questions.jsonl"
TOP_K = 4
FALLBACK_AR = "لم أجد إجابة صريحة في المصادر الجامعية المعتمدة."
FALLBACK_EN = "I could not find an explicit answer in the available university-approved sources."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


def load_questions(path: Path) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                questions.append(json.loads(line))
    return questions


def normalize_text(text: str) -> str:
    """Light normalisation for keyword matching (strip diacritics, collapse spaces)."""
    text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]", "", text)
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"[ىة]", "ه", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def keyword_hit(keyword: str, text: str) -> bool:
    """True if the normalised keyword appears anywhere in the normalised text."""
    return normalize_text(keyword) in normalize_text(text)


def source_hit(result_item: dict[str, Any], doc_keywords: list[str]) -> bool:
    """True if any expected doc keyword is found in the source's searchable metadata."""
    if not doc_keywords:
        return False
    metadata = result_item.get("metadata", {})
    haystack = " ".join(
        str(v)
        for v in (
            metadata.get("document_title", ""),
            metadata.get("section", ""),
            metadata.get("article", ""),
            result_item.get("content", ""),
        )
        if v
    )
    return any(keyword_hit(kw, haystack) for kw in doc_keywords)


def reciprocal_rank(results: list[dict[str, Any]], doc_keywords: list[str]) -> float:
    """Return 1/rank of the first result matching expected_doc_keywords, or 0."""
    for rank, item in enumerate(results, start=1):
        if source_hit(item, doc_keywords):
            return 1.0 / rank
    return 0.0


def hits_at_k(results: list[dict[str, Any]], doc_keywords: list[str], k: int) -> bool:
    return any(source_hit(item, doc_keywords) for item in results[:k])


def keyword_coverage(reference_keywords: list[str], answer: str) -> float:
    """Fraction of reference_keywords found in the answer text."""
    if not reference_keywords:
        return 1.0
    hits = sum(1 for kw in reference_keywords if keyword_hit(kw, answer))
    return hits / len(reference_keywords)


def is_fallback(answer: str) -> bool:
    norm = normalize_text(answer)
    return normalize_text(FALLBACK_AR) in norm or normalize_text(FALLBACK_EN) in norm


# ---------------------------------------------------------------------------
# Core evaluation
# ---------------------------------------------------------------------------

def evaluate_question(
    q: dict[str, Any],
    search_fn: Any,
    answer_fn: Any,
    top_k: int = TOP_K,
) -> dict[str, Any]:
    question = q["question"]
    doc_keywords: list[str] = q.get("expected_doc_keywords", [])
    ref_keywords: list[str] = q.get("reference_keywords", [])
    # skip_retrieval=true marks questions where the source data is genuinely absent
    # from the corpus. Retrieval metrics (Hit@K, MRR) are excluded for these questions
    # so they do not penalise embedding quality for a data-coverage problem.
    skip_retrieval: bool = bool(q.get("skip_retrieval", False))

    # Retrieval evaluation
    t0 = time.perf_counter()
    search_results = search_fn(question, top_k=top_k)
    retrieval_ms = (time.perf_counter() - t0) * 1000

    # Answer evaluation
    t1 = time.perf_counter()
    answer_result = answer_fn(question, top_k=top_k)
    answer_ms = (time.perf_counter() - t1) * 1000

    answer_text: str = answer_result.get("answer", "")
    confidence: str = answer_result.get("confidence", "medium")

    # Retrieval metrics — only for questions where source is known to exist
    if skip_retrieval:
        rr, h1, h2, h4 = None, None, None, None
    else:
        rr = reciprocal_rank(search_results, doc_keywords)
        h1 = hits_at_k(search_results, doc_keywords, 1)
        h2 = hits_at_k(search_results, doc_keywords, 2)
        h4 = hits_at_k(search_results, doc_keywords, top_k)

    kw_cov = keyword_coverage(ref_keywords, answer_text)
    fallback = is_fallback(answer_text)

    # Top retrieved source info for inspection
    top_source = {}
    if search_results:
        top_meta = search_results[0].get("metadata", {})
        top_source = {
            "score": round(float(search_results[0].get("score", 0)), 4),
            "document_title": top_meta.get("document_title", ""),
            "article": top_meta.get("article", ""),
            "section": top_meta.get("section", ""),
        }

    return {
        "id": q["id"],
        "question": question,
        "category": q.get("category", ""),
        "difficulty": q.get("difficulty", ""),
        "skip_retrieval": skip_retrieval,
        "coverage_note": q.get("coverage_note", ""),
        # Retrieval metrics (None = not evaluated)
        "rr": rr,
        "hit_at_1": h1,
        "hit_at_2": h2,
        "hit_at_4": h4,
        "top_source": top_source,
        # Answer metrics (always evaluated)
        "keyword_coverage": round(kw_cov, 3),
        "is_fallback": fallback,
        "confidence": confidence,
        # Latency
        "retrieval_ms": round(retrieval_ms, 1),
        "answer_ms": round(answer_ms, 1),
        "total_ms": round(retrieval_ms + answer_ms, 1),
        # Raw answer for manual review
        "answer_preview": answer_text[:200].replace("\n", " "),
    }


def compute_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(results)
    if n == 0:
        return {}

    # Separate retrieval-evaluatable questions from skip_retrieval ones
    retrieval_results = [r for r in results if not r.get("skip_retrieval")]
    skipped_results = [r for r in results if r.get("skip_retrieval")]
    nr = len(retrieval_results)

    def pct_of(values: list, total: int) -> float:
        return round(sum(1 for v in values if v) / total * 100, 1) if total else 0.0

    def avg(values: list) -> float:
        return round(sum(values) / len(values), 4) if values else 0.0

    summary = {
        "n": n,
        "n_retrieval_evaluated": nr,
        "n_coverage_gap": len(skipped_results),
        # Retrieval metrics — computed only over retrieval-evaluatable questions
        "hit_at_1_pct": pct_of([r["hit_at_1"] for r in retrieval_results], nr),
        "hit_at_2_pct": pct_of([r["hit_at_2"] for r in retrieval_results], nr),
        "hit_at_4_pct": pct_of([r["hit_at_4"] for r in retrieval_results], nr),
        "mrr": avg([r["rr"] for r in retrieval_results]),
        # Answer metrics — computed over ALL questions
        "keyword_coverage_avg": avg([r["keyword_coverage"] for r in results]),
        "fallback_rate_pct": pct_of([r["is_fallback"] for r in results], n),
        "confidence_high_pct": pct_of([r["confidence"] == "high" for r in results], n),
        "confidence_med_pct": pct_of([r["confidence"] == "medium" for r in results], n),
        "confidence_low_pct": pct_of([r["confidence"] == "low" for r in results], n),
        "avg_total_ms": avg([r["total_ms"] for r in results]),
        # Per-category and difficulty breakdowns
        "by_category": {},
        "by_difficulty": {},
        # Coverage gaps for inspection
        "coverage_gaps": [
            {"id": r["id"], "question": r["question"], "note": r.get("coverage_note", "")}
            for r in skipped_results
        ],
    }

    # Category breakdown — retrieval metrics use only non-skipped items per category
    categories: dict[str, list] = {}
    for r in results:
        categories.setdefault(r["category"], []).append(r)
    for cat, cat_results in sorted(categories.items()):
        cn = len(cat_results)
        cat_retrieval = [r for r in cat_results if not r.get("skip_retrieval")]
        crn = len(cat_retrieval)
        summary["by_category"][cat] = {
            "n": cn,
            "n_retrieval": crn,
            "hit_at_4_pct": pct_of([r["hit_at_4"] for r in cat_retrieval], crn) if crn else "—",
            "mrr": avg([r["rr"] for r in cat_retrieval]) if crn else 0.0,
            "keyword_coverage": round(avg([r["keyword_coverage"] for r in cat_results]), 3),
            "coverage_gap": cn > crn,
        }

    # Difficulty breakdown
    difficulties: dict[str, list] = {}
    for r in results:
        difficulties.setdefault(r["difficulty"], []).append(r)
    for diff, diff_results in sorted(difficulties.items()):
        diff_retrieval = [r for r in diff_results if not r.get("skip_retrieval")]
        drn = len(diff_retrieval)
        summary["by_difficulty"][diff] = {
            "n": len(diff_results),
            "n_retrieval": drn,
            "hit_at_4_pct": pct_of([r["hit_at_4"] for r in diff_retrieval], drn) if drn else "—",
            "mrr": avg([r["rr"] for r in diff_retrieval]) if drn else 0.0,
        }

    return summary


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

BAR_WIDTH = 20


def bar(pct: float) -> str:
    filled = round(pct / 100 * BAR_WIDTH)
    return "█" * filled + "░" * (BAR_WIDTH - filled)


def print_summary(name: str, summary: dict[str, Any]) -> None:
    n = summary["n"]
    nr = summary.get("n_retrieval_evaluated", n)
    ng = summary.get("n_coverage_gap", 0)
    gap_note = f"  [{ng} coverage-gap questions excluded from retrieval metrics]" if ng else ""
    print(f"\n{'─' * 64}")
    print(f"  Config: {name}  ({n} questions, {nr} retrieval-evaluated{', ' + str(ng) + ' skipped' if ng else ''})")
    print(f"{'─' * 64}")
    print(f"  Hit@1    {bar(summary['hit_at_1_pct'])} {summary['hit_at_1_pct']:5.1f}%  (n={nr})")
    print(f"  Hit@2    {bar(summary['hit_at_2_pct'])} {summary['hit_at_2_pct']:5.1f}%  (n={nr})")
    print(f"  Hit@4    {bar(summary['hit_at_4_pct'])} {summary['hit_at_4_pct']:5.1f}%  (n={nr})")
    print(f"  MRR      {bar(summary['mrr'] * 100)} {summary['mrr']:.4f}")
    print(f"  Kw.Cov   {bar(summary['keyword_coverage_avg'] * 100)} {summary['keyword_coverage_avg']:.3f}  (n={n})")
    print(f"  Fallback {bar(summary['fallback_rate_pct'])} {summary['fallback_rate_pct']:5.1f}%")
    print(
        f"  Confidence: high={summary['confidence_high_pct']:.0f}%  "
        f"med={summary['confidence_med_pct']:.0f}%  "
        f"low={summary['confidence_low_pct']:.0f}%"
    )
    print(f"  Avg latency: {summary['avg_total_ms']:.0f} ms/question")
    if gap_note:
        print(gap_note)

    if summary.get("by_difficulty"):
        print()
        print("  By difficulty:")
        for diff, stats in sorted(summary["by_difficulty"].items()):
            h4 = stats["hit_at_4_pct"]
            h4_str = f"{h4:5.1f}%" if isinstance(h4, float) else f"{'—':>6}"
            print(f"    {diff:8s}  Hit@4={h4_str}  MRR={stats['mrr']:.3f}  n={stats['n']} ({stats['n_retrieval']} eval)")

    if summary.get("by_category"):
        print()
        print("  By category:")
        for cat, stats in sorted(summary["by_category"].items()):
            h4 = stats["hit_at_4_pct"]
            h4_str = f"{h4:5.1f}%" if isinstance(h4, float) else f"{'—':>6}"
            gap_marker = " ⚠ data gap" if stats.get("coverage_gap") else ""
            print(f"    {cat:22s}  Hit@4={h4_str}  MRR={stats['mrr']:.3f}  n={stats['n']}{gap_marker}")


def print_comparison_table(runs: list[dict[str, Any]]) -> None:
    """Print a side-by-side comparison table of multiple evaluation runs."""
    if not runs:
        print("No runs to compare.")
        return

    names = [r["name"] for r in runs]
    summaries = [r["summary"] for r in runs]

    col_w = max(14, max(len(n) for n in names) + 2)
    header = f"{'Metric':<22}" + "".join(f"{n:>{col_w}}" for n in names)
    sep = "─" * len(header)

    metrics = [
        ("Hit@1 (%)", "hit_at_1_pct", ".1f"),
        ("Hit@2 (%)", "hit_at_2_pct", ".1f"),
        ("Hit@4 (%)", "hit_at_4_pct", ".1f"),
        ("MRR", "mrr", ".4f"),
        ("Keyword Coverage", "keyword_coverage_avg", ".3f"),
        ("Fallback Rate (%)", "fallback_rate_pct", ".1f"),
        ("Confidence High (%)", "confidence_high_pct", ".1f"),
        ("Confidence Low (%)", "confidence_low_pct", ".1f"),
        ("Avg Latency (ms)", "avg_total_ms", ".0f"),
    ]

    print(f"\n{'═' * len(header)}")
    print("  BENCHMARK COMPARISON")
    print(f"{'═' * len(header)}")
    print(header)
    print(sep)

    for label, key, fmt in metrics:
        row = f"{label:<22}"
        values = [s.get(key, 0) for s in summaries]
        best = max(values) if key not in ("fallback_rate_pct", "confidence_low_pct", "avg_total_ms") else min(values)
        for val in values:
            cell = format(val, fmt)
            marker = " ★" if val == best and len(runs) > 1 else "  "
            row += f"{cell + marker:>{col_w}}"
        print(row)

    print(sep)
    print("  ★ = best value for this metric\n")


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> None:
    """Run the benchmark against the currently active configuration."""
    try:
        from app.retrieve import search  # noqa: PLC0415
        from app.chat import answer_question  # noqa: PLC0415
    except ImportError:
        from retrieve import search  # type: ignore
        from chat import answer_question  # type: ignore

    questions_path = Path(args.questions)
    if not questions_path.exists():
        print(f"ERROR: Questions file not found: {questions_path}", file=sys.stderr)
        sys.exit(1)

    questions = load_questions(questions_path)
    if args.limit:
        questions = questions[: args.limit]

    config_name = args.name
    top_k = args.top_k

    print(f"\n🔍 Running benchmark: config='{config_name}'  questions={len(questions)}  top_k={top_k}")
    print(f"   Questions: {questions_path}")

    import os as _os
    env_info = {
        "EMBEDDING_MODEL": _os.getenv("EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"),
        "ENABLE_RERANKING": _os.getenv("ENABLE_RERANKING", "false"),
        "RERANKING_MODEL": _os.getenv("RERANKING_MODEL", "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"),
    }
    print(f"   Env: {env_info}")

    results: list[dict[str, Any]] = []
    failed: list[str] = []

    for i, q in enumerate(questions, start=1):
        try:
            result = evaluate_question(q, search, answer_question, top_k=top_k)
            results.append(result)
            if result["skip_retrieval"]:
                status = "~"  # skipped for retrieval, answer quality still measured
            else:
                status = "✓" if result["hit_at_4"] else "✗"
            conf = result["confidence"][0].upper()
            kw = f"{result['keyword_coverage']:.0%}"
            print(f"  [{i:3d}/{len(questions)}] {status} {conf} kw={kw:4s}  {q['id']}  {q['question'][:60]}")
        except Exception as exc:
            failed.append(q["id"])
            print(f"  [{i:3d}/{len(questions)}] ERROR {q['id']}: {exc}", file=sys.stderr)

    summary = compute_summary(results)
    print_summary(config_name, summary)

    # Persist results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"{config_name}_{timestamp}.json"
    # Also write/overwrite the canonical name file for easy comparison
    canonical_path = RESULTS_DIR / f"{config_name}.json"

    payload = {
        "name": config_name,
        "timestamp": timestamp,
        "questions_path": str(questions_path),
        "top_k": top_k,
        "env": env_info,
        "summary": summary,
        "results": results,
        "failed": failed,
    }

    for path in (out_path, canonical_path):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n✅ Results saved to: {out_path}")
    print(f"   Canonical:         {canonical_path}")
    if failed:
        print(f"   ⚠️  {len(failed)} questions failed: {failed}")


def cmd_compare(args: argparse.Namespace) -> None:
    """Load saved result files and print a comparison table."""
    paths: list[Path] = []

    if args.files:
        paths = [Path(f) for f in args.files]
    else:
        # Auto-discover canonical result files in the results directory.
        # Canonical files are named exactly "<config-name>.json" (e.g. baseline.json).
        # Timestamped snapshots follow the pattern "<name>_YYYYMMDD_HHMMSS.json" and
        # are excluded here to avoid loading each config twice.
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        paths = sorted(
            [
                p
                for p in RESULTS_DIR.glob("*.json")
                if re.match(r"^[a-z0-9][a-z0-9\-]*\.json$", p.name)
                and not re.search(r"_\d{8}_\d{6}\.json$", p.name)
            ],
            key=lambda p: p.stat().st_mtime,
        )

    if not paths:
        print("No result files found. Run `python -m app.eval_benchmark run --name <name>` first.")
        return

    runs: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            print(f"WARNING: File not found: {path}", file=sys.stderr)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        runs.append(data)
        print(f"  Loaded: {path.name}  ({data.get('summary', {}).get('n', '?')} questions, {data.get('timestamp', '')})")

    if not runs:
        print("No valid runs loaded.")
        return

    print_comparison_table(runs)

    # Also print per-config summaries
    for run in runs:
        print_summary(run["name"], run["summary"])

    # Highlight questions where configs disagree on hit@4
    if len(runs) >= 2:
        print("\n─── Questions where configs DISAGREE on Hit@4 ───")
        q_map: dict[str, dict[str, bool]] = {}
        for run in runs:
            for r in run.get("results", []):
                q_map.setdefault(r["id"], {})[run["name"]] = r["hit_at_4"]

        disagreements = [
            (qid, hits)
            for qid, hits in q_map.items()
            if len(set(hits.values())) > 1
        ]

        if not disagreements:
            print("  None — all configs agree on every question.")
        else:
            # Show question text from any run
            q_text: dict[str, str] = {}
            for run in runs:
                for r in run.get("results", []):
                    q_text[r["id"]] = r["question"]

            for qid, hits in sorted(disagreements):
                hits_str = "  ".join(f"{name}={'✓' if v else '✗'}" for name, v in hits.items())
                print(f"  {qid}: {hits_str}")
                print(f"    Q: {q_text.get(qid, '')[:80]}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    configure_stdout()
    parser = argparse.ArgumentParser(
        description="Benchmark the student assistant RAG system across configurations.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run subcommand
    run_parser = subparsers.add_parser("run", help="Run benchmark against the current active configuration.")
    run_parser.add_argument(
        "--name",
        required=True,
        help="Label for this configuration (e.g. 'baseline', 'reranker', 'e5', 'e5-reranker').",
    )
    run_parser.add_argument(
        "--questions",
        default=str(DEFAULT_QUESTIONS_PATH),
        help=f"Path to the JSONL question file (default: {DEFAULT_QUESTIONS_PATH}).",
    )
    run_parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K,
        help=f"Number of chunks to retrieve per question (default: {TOP_K}).",
    )
    run_parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Limit number of questions (0 = all).",
    )

    # compare subcommand
    compare_parser = subparsers.add_parser("compare", help="Compare saved evaluation result files.")
    compare_parser.add_argument(
        "files",
        nargs="*",
        help="Result JSON files to compare. If omitted, auto-discovers from results directory.",
    )

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "compare":
        cmd_compare(args)


if __name__ == "__main__":
    main()
