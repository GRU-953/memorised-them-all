# Changelog

All notable changes to **Memorised them All** are documented here. This project
adheres to [Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/).

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

[1.0.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.0.0
