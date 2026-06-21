#!/usr/bin/env python3
"""Pinned performance benchmark — deterministic, offline, comparable across cycles.

Methodology (fixed so deltas are comparable):
  * Corpus = the committed `eval/corpus/*.md` (typical) replicated ``--scale`` times into a
    temp tree (the "large" dimension); malformed/adversarial inputs are covered by the
    security test-suite (`tests/test_archive_bomb.py`, `test_security.py`,
    `test_stress_guardrails.py`), not timed here.
  * Each phase is timed with ``time.perf_counter``; we report the MIN of ``--repeat`` runs
    (min = least noise) plus the median. Engine is deterministic/model-free, so timings are
    the only thing that varies run-to-run.
  * Fully offline: sets MTA_AUTO_UPDATE=off and never touches the network.
  * Phases: convert (files→Markdown), digest (Markdown→graph+index), recall (one query),
    overview. Run identically before/after a change; attach both JSON blobs to the cycle.

Usage:  python eval/bench.py [--scale N] [--repeat K] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "eval" / "corpus"


def _timed(fn, repeat: int):
    samples = []
    out = None
    for _ in range(repeat):
        t0 = time.perf_counter()
        out = fn()
        samples.append(time.perf_counter() - t0)
    return {"min_s": round(min(samples), 4),
            "median_s": round(statistics.median(samples), 4)}, out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=int, default=10, help="replicate the corpus N times")
    ap.add_argument("--repeat", type=int, default=3)
    ap.add_argument("--query", default="grid stability and solar output")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    sys.path.insert(0, str(ROOT))
    from mta.core.config import Config
    from mta.core.digest import digest, convert_to_markdown
    from mta.core import recall as recall_mod

    src = [p for p in sorted(CORPUS.glob("*.md"))]
    if not src:
        print("no corpus", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        docs = tdp / "docs"
        docs.mkdir()
        # Replicate the corpus --scale times for the "large" dimension. Each replica gets a
        # UNIQUE marker entity/relation appended so it does NOT content-hash-dedup away —
        # this is what makes the digest phase genuinely stress extraction + resolution +
        # community detection at scale (not just conversion). Deterministic per (i, file).
        n_files = 0
        for i in range(args.scale):
            for p in src:
                body = p.read_text(encoding="utf-8")
                marker = (f"\n\n## Site Report {i:03d}\n"
                          f"Operator Helios-{i:03d} manages Substation Nyx-{i:03d} "
                          f"with Director Vega-{i:03d}; output rose at Grid-{i:03d}.\n")
                (docs / f"{p.stem}_{i:03d}.md").write_text(body + marker, encoding="utf-8")
                n_files += 1
        home = tdp / "home"
        cfg = Config(home=home).with_project("bench")
        cfg.ensure_dirs()

        conv, _ = _timed(lambda: convert_to_markdown(Config(home=home).with_project("bench"),
                                                     [str(docs)], out_dir=str(tdp / "md")),
                         args.repeat)
        dig, dres = _timed(lambda: digest(Config(home=home).with_project("bench"),
                                          [str(docs)], reset=True), args.repeat)
        rec, _ = _timed(lambda: recall_mod.recall(Config(home=home).with_project("bench"),
                                                  args.query), args.repeat)
        ov, _ = _timed(lambda: recall_mod.overview(Config(home=home).with_project("bench")),
                       args.repeat)

    stats = dres.get("stats", {}) or {}
    report = {
        "corpus_files": n_files, "scale": args.scale, "repeat": args.repeat,
        "digest_status": dres.get("status"),
        "kg": {"entities": stats.get("entities"), "relations": stats.get("relations"),
               "communities": stats.get("communities"), "chunks": stats.get("chunks")},
        "phases_seconds": {"convert": conv, "digest": dig, "recall": rec, "overview": ov},
        "python": sys.version.split()[0],
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.json:
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
