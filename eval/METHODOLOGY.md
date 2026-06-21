# Evaluation & benchmark methodology (pinned)

So cycle-over-cycle deltas are comparable, both harnesses are fixed and offline.

## KG-extraction quality — `eval/run_eval.py`
Digests the committed `eval/corpus/*.md` and scores extracted entities/relations against the
gold set in `eval/golden.json`. Deterministic (model-free engine). Run before/after any change
that touches extraction/resolution and attach the score.

## Performance — `eval/bench.py`
Deterministic, offline (`MTA_AUTO_UPDATE=off`, no network), reports the **min** and median of
`--repeat` runs per phase:
- **Corpus (typical):** `eval/corpus/*.md`.
- **Large dimension:** the corpus replicated `--scale` times; each replica gets a *unique*
  marker entity/relation appended so it does not content-hash-dedup away — this makes the
  digest phase genuinely stress extraction + resolution + community detection, not just
  conversion.
- **Malformed/adversarial dimension:** NOT timed here — exercised by the security suite
  (`tests/test_archive_bomb.py`, `test_security.py`, `test_stress_guardrails.py`) which asserts
  zip-bomb / Zip-Slip / decompression / oversize bounds.
- **Phases:** `convert` (files→Markdown), `digest` (Markdown→graph+BM25 index), `recall`
  (one query), `overview`.

Pinned command for cross-cycle comparison:
```
python eval/bench.py --scale 25 --repeat 3 --json bench_<cycle>.json
```

## Offline verification
The whole test + benchmark run is executed under a network namespace with no external route
(loopback only), e.g. on Linux:
```
unshare -rn sh -c 'ip link set lo up; .venv/bin/python -m pytest tests/ -q'
unshare -rn sh -c 'ip link set lo up; .venv/bin/python eval/bench.py --scale 25 --repeat 3'
```
Any runtime network fetch of models/weights/binaries must FAIL — the engine is model-free and
must complete with no network.

## Cycle-0 baseline (this branch, Python 3.12, network-disabled)
- Tests: **265 passed / 3 skipped**, network DISABLED (offline contract verified).
- Coverage: **79%** (`coverage run --source=mta -m pytest`; 3556 stmts / 733 missed).
- Dependency audit: **0 known vulnerabilities** (`pip-audit`).
- Benchmark (`--scale 25 --repeat 3`, 100 files / 200 chunks): convert **12.03 s** (min),
  digest **12.45 s** (min), recall **0.0011 s**, overview ~0.0003 s; KG = 14 entities /
  25 relations / 2 communities.
