"""Reproducible offline evaluation harness (WP-31).

Digests the committed reference corpus (``eval/corpus``) with **no models**
(hashing embeddings + classical extraction), runs the golden queries through
``recall``, and reports retrieval recall@k + per-stage timing. Exits non-zero if
recall@k is below the floor in ``eval/golden.json`` — so CI gates retrieval
quality and catches regressions. No network, no copyrighted material.

Run:  python eval/run_eval.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CORPUS = HERE / "corpus"
GOLDEN = json.loads((HERE / "golden.json").read_text(encoding="utf-8"))


def run(home: Path) -> dict:
    """Digest the corpus offline and score the golden queries. Returns metrics."""
    os.environ["MTA_HOME"] = str(home)
    os.environ.setdefault("MTA_NO_OLLAMA", "1")
    os.environ["MTA_EXTRACT"] = "classical"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from mta.core.config import load
    from mta.core.digest import digest
    from mta.core.recall import recall

    cfg = load().with_project("eval")
    t0 = time.time()
    dres = digest(cfg, [str(CORPUS)])
    digest_s = round(time.time() - t0, 2)

    k = int(GOLDEN.get("k", 8))
    queries = GOLDEN["queries"]
    found_n = 0
    per_query = []
    by_suite_found: dict[str, int] = {}
    by_suite_total: dict[str, int] = {}
    rt0 = time.time()
    for q in queries:
        out = recall(cfg, q["query"], k=k)
        blob = " ".join((h.get("label", "") + " " + h.get("text", ""))
                        for h in out.get("hits", [])).lower()
        found = any(exp.lower() in blob for exp in q["expect_any"])
        found_n += int(found)
        suite = q.get("suite", "en")
        by_suite_total[suite] = by_suite_total.get(suite, 0) + 1
        by_suite_found[suite] = by_suite_found.get(suite, 0) + int(found)
        per_query.append({"suite": suite, "query": q["query"], "found": found,
                          "low_confidence": out.get("low_confidence")})
    recall_at_k = round(found_n / len(queries), 3) if queries else 0.0
    recall_by_suite = {s: round(by_suite_found[s] / by_suite_total[s], 3)
                       for s in sorted(by_suite_total)}
    recall_s = round(time.time() - rt0, 2)

    # Fast-mode timing (deterministic, no LLM) for the speedup figure.
    cfg_fast = load().with_project("eval_fast")
    ft0 = time.time()
    digest(cfg_fast, [str(CORPUS)], fast=True)
    fast_s = round(time.time() - ft0, 2)

    return {
        "corpus_files": dres["stats"]["files"],
        "converted": dres["stats"]["converted"],
        "entities": dres["stats"]["entities"],
        "relations": dres["stats"]["relations"],
        "embed_mode": dres["stats"]["embed_mode"],
        "queries": len(queries),
        "k": k,
        "recall_at_k": recall_at_k,
        "recall_by_suite": recall_by_suite,
        "timing_s": {"digest": digest_s, "recall_total": recall_s, "fast_digest": fast_s},
        "per_query": per_query,
    }


def main() -> int:
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        m = run(Path(d))
    print(json.dumps(m, indent=2, ensure_ascii=False))
    ok = True
    # Overall floor (back-compat).
    overall_floor = float(GOLDEN.get("recall_at_k_floor", 0.0))
    if m["recall_at_k"] < overall_floor:
        print(f"FAIL: overall recall@{m['k']} = {m['recall_at_k']} < floor {overall_floor}", file=sys.stderr)
        ok = False
    # Per-suite floors (WP-202a) — a Bengali regression can't hide behind English recall.
    for suite, floor in GOLDEN.get("floors", {}).items():
        got = m["recall_by_suite"].get(suite)
        if got is None:
            print(f"FAIL: suite '{suite}' has a floor but no queries ran", file=sys.stderr)
            ok = False
        elif got < float(floor):
            print(f"FAIL: {suite} recall@{m['k']} = {got} < floor {floor}", file=sys.stderr)
            ok = False
    if not ok:
        return 1
    print(f"OK: recall@{m['k']} overall={m['recall_at_k']} by_suite={m['recall_by_suite']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
