# TEST_REPORT — Phase-6 end-to-end

**Date:** 2026-06-02 · **Env:** macOS / Apple-silicon (arm64), Python 3.12.13,
**clean wheel install** (`pip install dist/*.whl` into a fresh venv — the real user
install, not editable), **live Ollama** (qwen2.5:7b + nomic-embed-text + moondream),
Tesseract + ffmpeg present. CI counterpart: `.github/workflows/e2e.yml` runs the
offline suite on the `develop`→`main` release PR + on demand.

## Results

### Offline CLI E2E — `tests/test_e2e_cli.py` (MTA_E2E=1) — **5/5 PASS**
- `mta status` / `mta doctor --dry-run` — stack + detected-vs-required dependency report.
- Full lifecycle: `digest` (5 real formats — pdf/docx/xlsx/csv/html) → `overview` →
  `recall` → `export` → `mindmap` → `forget`. `converted=5`, `mode="classical"`
  (honest offline label), token-free (no raw document text in results), recall hits
  ≤600 chars, mindmap offline (Cytoscape inlined; no CDN / external `<script src=`).
- `--fast` CLI → `mode="fast"`.
- Off-topic recall offline → `low_confidence=true` (declinable with no models).
- Constrained: a zip-bomb `.docx` is skipped; the digest never crashes.

### Accurate-mode E2E — live Ollama (MTA_E2E_OLLAMA=1) — **PASS (142 s)**
Full pipeline through the real local LLM: `digest` (accurate) → `mode="accurate"`,
`embed_mode="ollama"`, `entities>0`; `recall` returns real-embedding hits with
`low_confidence`/`top_score`. The host's Ollama was **reused and left running**.

### Measured performance (5 fixtures, same machine)
- accurate digest **137.3 s** vs fast digest **1.4 s** → **≈98× faster**.
- Earlier 12-file probe: ≈186 s vs ≈7 s → ≈26×.
- ⇒ fast mode is **≈25–100×** faster depending on corpus/model — the headline
  speedup is now **benchmarked** (README updated to the measured range).

## Invariants verified end-to-end
token-free (metadata/slice only) · offline/classical fallback (full digest with
`MTA_NO_OLLAMA=1`) · atomic store (no `.tmp` left; torn-pair guard) · mindmap
zero-network · decompression-bomb cap · reused-Ollama-left-untouched.

## Deferred to a future pass (v1.x+ / not CI-feasible here)
- Clean **container** matrix installing from each *published* channel
  (PyPI / Homebrew / `.mcpb`-in-Claude-Desktop) — pending the live release (WP-41)
  and Docker (R-01).
- Cross-client over **HTTP / REST** (Phase-3 transports are v1.x+).
- Broad **multilingual scanned-PDF / audio** fidelity at scale (the offline OCR path
  is unit-tested; large-corpus fidelity is a v1.x+ eval-harness expansion).
- Idle-shutdown timing tolerance + multi-client **soak** under sustained real load
  (locking + lifecycle are unit-tested in `test_concurrency`).
