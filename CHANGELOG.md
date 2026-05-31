# Changelog

All notable changes to **Memorised them All** are documented here. This project
adheres to [Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/).

## [1.2.0] — 2026-06-01

Fast mode + a multi-agent evaluation/hardening pass (accuracy, reliability,
token-safety, reusability, cross-platform) and security review.

### Added
- **Fast mode** (`MTA_FAST=on`, `mta digest --fast`, `fast=true` tool arg): skips
  the LLM (classical extraction + deterministic summaries, keeps the embedding
  model) for a fully **deterministic**, ~100× faster digest. The default path
  stays on the LLM for maximum accuracy.
- **Cross-platform support beyond Apple silicon**: psutil-based physical-core and
  memory detection (correct pool sizing on Intel/Linux/Windows), platform-aware
  PATH healing, portable mind-map opener, `psutil` process-tree teardown for the
  idle-stop, CUDA Whisper on Linux/Windows GPUs, Linux package-manager install
  paths (apt/dnf/pacman), broadened platform metadata, and a CI matrix across
  Ubuntu/macOS/Windows × Python 3.10/3.12.
- **Per-file size cap** (`MTA_MAX_FILE_MB`, default 200) — oversize files are
  skipped before being read into memory (bounds OOM/decompression-bomb risk).

### Fixed / Hardened (from agent reviews)
- **Token-safety**: `recall(k=…)` is hard-clamped (≤50) so a caller can't pull the
  whole graph's text into context; LLM fact strings are length-capped.
- **Accuracy**: facts attach to entities by **word boundary** (no "Cat" inside
  "Category"; CJK-aware), de-duplicated per chunk; stable community tiebreak.
- **Reliability**: per-file isolation for the conversion process pool and
  per-chunk isolation for threaded extraction (one failure or a mid-run model
  death no longer aborts/redoes the whole digest); PDF OCR handle leak fixed;
  updater throttle stamped before work to avoid concurrent pip races.
- **Reusability**: `graph.json` stores basenames (no absolute-path leakage —
  portable across machines); exports now include the vector store so recall works
  from a copied bundle; `load_graph` rejects an incompatible future schema.

## [1.1.0] — 2026-06-01

### Added
- **Accumulative digestion**: digesting another folder into the same project now
  *extends* the memory (rebuilt from the full converted corpus on disk) instead
  of replacing it. `reset=True` clears the project first.
- **Scanned-PDF OCR**: image-only PDFs are rasterised with pypdfium2 and OCR'd
  page-by-page (previously a no-op).
- **Parallel extraction**: knowledge extraction runs across a memory-aware thread
  pool (`MTA_EXTRACT_WORKERS`, default auto: 1–3 by RAM) — the LLM calls are
  I/O-bound, but too much concurrency thrashes a unified-memory Mac running a 7B
  model, so the default scales with available memory.
- **Workload guards**: identical chunks are de-duplicated, degenerate low-
  information passages are skipped, and a reported cap (`MTA_MAX_CHUNKS`, default
  1500) prevents pathological corpora from hanging — all surfaced in stats, never
  silent.
- **PATH self-heal**: the server/CLI prepend common Homebrew/system bin dirs so
  `tesseract`/`ffmpeg`/`ollama` resolve under a host app's sparse PATH (Claude
  Desktop).

### Fixed
- **Entity resolution no longer over-merges**: short proper nouns embed almost
  identically with nomic-embed-text (e.g. two unrelated organisations can score
  cosine ≈ 1.0), which previously collapsed distinct entities into a single node.
  Embeddings now only *confirm* a merge that also shares tokens (fuzzy floor), and
  the cosine threshold was raised. Distinct entities stay distinct.
- **Better recall ranking**: prefix-aware embedding models (nomic) now receive
  their `search_document:` / `search_query:` task prefixes, sharpening retrieval.
- **Honest idle timeout**: the on-demand Ollama idle-stop floor was lowered from
  30 s to 5 s so small `MTA_IDLE` values are respected (default remains 300 s).
- **OCR robustness**: image OCR now pipes PNG bytes to `tesseract stdin stdout`
  (PSM 1 auto-orientation) instead of using temp files, which failed under
  sandboxed/sparse environments and silently fell through to vision captioning.
- **No silent content loss**: an over-long unpunctuated passage is hard-split into
  chunk-sized windows, so the extractor's input cap no longer drops the tail.

## [1.0.1] — 2026-06-01

### Fixed
- **Homebrew / CLI launcher**: run the pure-Python package directly from the
  source tree via `PYTHONPATH` instead of building it at first run. This avoids a
  failure when a packager strips `README.md` from the install tree (Homebrew),
  and makes the plugin launcher resilient to a missing editable install.

## [1.0.0] — 2026-06-01

The first public release.

### Added
- **Local, token-free digestion pipeline** (the *MnemoGraph* engine): convert →
  segment → embed → extract → resolve → graph → community detection → layered
  summaries → materialise. Document contents never return to Claude.
- **Universal local conversion** via Microsoft MarkItDown (latest, auto-updated),
  Tesseract OCR, on-device Whisper (Apple-MLX accelerated, faster-whisper
  fallback), and a local Ollama vision model.
- **Layered knowledge graph**: global synopsis (L0), community/theme summaries
  (L1), and provenance-tracked atomic facts (L2). Leiden community detection with
  Louvain/greedy fallbacks.
- **Outputs**: `graph.json`, compact `memory.md`, per-document Markdown notes,
  an offline interactive `mindmap.html` (Cytoscape inlined), and a vector store.
- **Token-free recall** returning a small, citable slice — never whole documents.
- **Seven MCP tools**: `digest`, `recall`, `memory_overview`, `export_memory`,
  `list_digestible`, `memory_status`, `open_mindmap`.
- **`mta` CLI** with `digest`, `recall`, `overview`, `export`, `status`,
  `mindmap`, `update`, `serve`.
- **Auto-install** (idempotent `install.sh`) of Homebrew apps, the Python venv,
  and local models; **auto-update** of MarkItDown and dependencies (throttled
  daily, opt-out).
- **On-demand lifecycle**: starts Ollama on first use, stops the instance it
  started after 5 minutes idle; a user's own Ollama is reused and left untouched.
- **Apple-silicon tuning**: performance-core parallelism, native-thread pinning,
  GPU Whisper via MLX, unified-memory-aware concurrency.
- **Offline mode**: a dependency-free classical extractor and hashing embeddings
  keep the pipeline working with no models and no network.
- **Distribution**: Claude Desktop `.mcpb`, Claude Code plugin/marketplace, PyPI
  package, and a Homebrew tap; CI and tagged releases with assets.

[1.2.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.2.0
[1.1.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.1.0
[1.0.1]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.0.1
[1.0.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.0.0
