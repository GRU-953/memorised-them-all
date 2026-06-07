# Changelog

All notable changes to **Memorised them All** are documented here. This project
adheres to [Semantic Versioning](https://semver.org/) and
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

## [1.9.0] — 2026-06-08

### Changed
- **New default profile `micro` — safe on a 4 GB machine with no GPU.** Out of the box the
  plugin now runs **fully offline** (classical extraction + a tiny `qwen3-embedding:0.6b`
  embedder that falls back to a hashing embedding if even that can't load; vision off; one
  conversion worker), so a digest **always completes and never OOMs/thrashes** on any
  computer. This replaces the previous 16 GB-tuned default that could thrash a small box.
- **One-knob opt-up.** `MTA_PROFILE=auto` sizes the local-AI stack to the machine
  (`<6 GB`→`micro`, 6–12→`small`, 12–24→`standard` = the qwen3 stack, ≥24→`large` = qwen3:8b);
  explicit `MTA_PROFILE=standard/large` or any `MTA_*_MODEL` env var overrides it. The Claude
  Desktop extension gains a **"Performance profile"** dropdown (default `auto`). New
  `platform.detect_tier()`; the conversion worker pool now clamps to **1 worker on <6 GB**.

### Fixed
- **Special-token leak closed on the summary + synopsis path** (the WP-69 fix only covered
  entities/facts). qwen3 `<tool_call>`, ChatML `<|…|>`, `<think>`, and gemma
  `<start_of_turn>`/`<end_of_turn>` tokens are now scrubbed from LLM community summaries and
  the global synopsis too — they feed `memory.md`, recall theme-cards and the mind map.

### Notes
- Informed by a 6-expert guardrail review (resource sizing, Ollama reliability, conversion
  robustness, cross-platform, LLM safety, novice UX). Remaining high-value items — a
  cross-platform per-file conversion timeout, honest "degraded mode" reporting in
  `memory_status`/`recall`, and a richer classical extractor — are tracked as follow-ups.

## [1.8.0] — 2026-06-07

### Added
- **Legacy Bengali → Unicode, built in.** Documents typed in **Bijoy/SutonnyMJ** (and
  110+ other Bijoy-family ANSI fonts) are auto-upgraded to standard Unicode Bengali during
  conversion, so digest/recall/embeddings work on text that used to be mojibake. It is
  **font-aware** for Office files (`.docx`/`.pptx`/`.xlsx`) — only legacy-font runs are
  converted, so *mixed English+Bengali* documents convert cleanly (English untouched);
  plain text uses a conservative density heuristic that never touches ordinary English.
  A faithful pure-Python port of the **Mukti** converter (MIT) — no new dependency, fully
  local. On by default; `MTA_BANGLA_LEGACY=off` disables it. (`mta/core/bangla_legacy.py`.)
- **`convert` — convert-to-Markdown as a first-class feature.** New `mta convert <paths>
  [--out DIR]` CLI command and MCP `convert(paths, out_dir?)` tool convert files/dirs/globs
  to Markdown locally (with the legacy-Bengali upgrade) and write the `.md` files to
  `out_dir` (default: a `markdown_converted/` folder beside the input). Token-free. `digest`
  runs the very same conversion as its first stage, so converting to Markdown is the default
  everywhere. The plugin now exposes **9 tools** (all surfaces kept in lockstep).

### Fixed
- Extraction robustness on dense/real documents: `num_predict` 700 → 1024 (headroom so a
  long entity/fact JSON can't be truncated into a parse failure → silent classical fallback),
  and the JSON parser now strips `<think>…</think>` reasoning blocks (defensive for
  thinking-capable models such as `qwen3:8b` reached through a non-`format:json` backend).

## [1.7.0] — 2026-06-06

### Changed
- **Default local-model stack re-tuned to the optimum for ≤16 GB Apple Silicon** —
  newer-generation and multilingual (incl. Bangla), small enough to be co-resident with
  headroom — based on fresh research verified against the live Ollama registry manifest API:
  - Extraction (`MTA_EXTRACT_MODEL`): `qwen2.5:7b` → **`qwen3:4b-instruct`** (2.5 GB; a
    non-thinking instruct build → clean JSON, 119 languages).
  - Embeddings (`MTA_EMBED_MODEL`): `nomic-embed-text` → **`qwen3-embedding:0.6b`** (0.64 GB,
    1024-d, 100+ languages — far stronger multilingual/Bangla recall, MMTEB ≈ 64).
  - Vision (`MTA_VISION_MODEL`): `moondream` → **`qwen3-vl:4b-instruct`** (3.3 GB; 32-language
    OCR incl. Bangla; reads charts/diagrams).
  - Speech-to-text (`MTA_WHISPER_MODEL`): `base` → **`small`**.
  All previous defaults remain available and documented as alternatives; every model is
  overridable via env vars or the Claude Desktop extension settings.
  **Existing memories are safe:** changing the embedding model changes the vector dimension,
  so `recall` transparently falls back to lexical scoring (it never errors) until you
  re-digest with `reset: true`, which rebuilds vectors at the new dimension.

### Added
- Query-side instruction prefix for `qwen3-embedding` models (their recommended usage),
  improving recall quality.
- Refreshed README "Choosing a model" + extension field descriptions with the verified
  ≤16 GB stack and alternatives — including a warning that bare `qwen3:4b` / `qwen3-vl:4b`
  are *thinking* builds (pin the `-instruct` tags), and that `qwen3.5` / `gemma4` now exist
  as experimental options.

## [1.6.3] — 2026-06-06

### Added
- **Lighter / multilingual local-model alternatives, documented and surfaced.** A new
  "Choosing a model" section in the README plus enriched Claude Desktop extension
  (`manifest.json`) field descriptions recommend opt-in alternatives to the defaults:
  extraction — `gemma3:4b-it-qat` (4 GB, quantization-aware-trained ≈ BF16 quality, 140+
  languages), `gemma3n:e2b-it-q4_K_M` (on-device-efficient), `gemma3:1b-it-qat`;
  embeddings — `bge-m3` (100+ languages, ideal for Bangla/mixed-language recall),
  `mxbai-embed-large`; vision — `llama3.2-vision`, `qwen2.5vl`, `granite3.2-vision`.
  Clarifies that **`gemma4` does not exist** (Gemma 3n = `e2b-it`, Gemma 3 = `*-it-qat`).
  Defaults are unchanged (`qwen2.5:7b` / `nomic-embed-text` / `moondream`); all are already
  selectable via `MTA_EXTRACT_MODEL` / `MTA_EMBED_MODEL` / `MTA_VISION_MODEL` and the
  extension settings. Note: changing the embedding model changes the vector dimension —
  re-digest with `reset: true`.

## [1.6.2] — 2026-06-06

### Fixed
- **`mta setup-claude` now writes the Claude config atomically.** `_merge_into` used a
  plain `write_text`, so a host that watches and reconciles its config (a running Claude
  Desktop) could observe a half-written file or revert the freshly-added `mcpServers`
  entry. The write is now staged to a temp file and committed with a single `os.replace`
  rename. It also **coerces a non-dict `mcpServers`** (e.g. a stray `[]` left by another
  tool) to a dict, so the merge can neither silently no-op nor raise.

### Changed
- **Plugin/marketplace `.mcp.json` defaults aligned to the v1.6.x code defaults** —
  `MTA_OCR_LANG=eng+ben` (was `eng`) and `MTA_DIGEST_ALL=on`, so a plugin-mode install gets
  English + Bangla OCR and all-file-types digesting out of the box.

## [1.6.1] — 2026-06-06

### Fixed
- **Digest *all* file types — for real, in folder digests.** v1.6.0 added a plain-text
  fallback in the converter, but the directory walk (`_expand`) still filtered every path
  by `SUPPORTED_EXTS`, so unknown extensions in a folder never reached it. The walk now
  includes unknown extensions too (digested as text when textual, binaries skipped),
  skipping only hidden files/dirs (`.git`, dotfiles, …); an explicitly-named file is always
  digested. Gated by `MTA_DIGEST_ALL` (default `on`; set `off` for known-types-only).

## [1.6.0] — 2026-06-06

### Fixed
- **`${HOME}` path bug that blocked digesting.** When a launcher (e.g. Claude Desktop's
  MCPB manifest substitution) passed `MTA_HOME` as a literal, unexpanded
  `${HOME}/.memorised-them-all`, the engine tried to write to a bogus directory — so
  `config_file` came back `null` and `digest` failed. `MTA_HOME` is now resolved robustly:
  `$VAR`/`${VAR}` and `~` are expanded, and an unexpandable placeholder or non-absolute
  path falls back to the safe default instead of writing junk.

### Changed
- **English + Bangla OCR by default** (`MTA_OCR_LANG=eng+ben`). OCR now also **drops any
  requested language Tesseract doesn't have installed**, so the new default never errors
  on a machine with only `eng` — it degrades gracefully.
- **Digest all file types.** Unknown extensions are now digested as plain text when the
  content looks textual (source code, `.log`, `.ini`, `.tex`, `.org`, …, including UTF-8
  Bangla); genuine binaries remain a clean `unsupported`. Nothing textual is silently skipped.

### Added
- **`mta setup-claude`** — registers this MCP server in the host's Claude config
  (Claude Desktop `claude_desktop_config.json`, and Claude Code `~/.claude.json` when
  present), idempotently and with a backup. **`install.sh` now runs it automatically**, so
  a fresh install wires itself into Claude with no hand-edited JSON (opt out with
  `MTA_SKIP_CLAUDE_SETUP=1`). The Bangla Tesseract pack is installed on dnf/pacman too
  (macOS/apt already did). MLX (Apple-GPU Whisper) + the default Ollama models
  (`qwen2.5:7b`/`nomic-embed-text`/`moondream`) remain the install defaults.

## [1.5.2] — 2026-06-03

### Fixed
- **Classical (offline) extractor quality (PIPE-06).** The dependency-free extractor now
  strips a leading determiner so "The Nordic Grid Authority" resolves to the same entity
  as "Nordic Grid Authority"; collapses internal whitespace in facts (no more mid-fact
  newlines from table/line breaks); and splits sentences abbreviation-aware, so an
  honorific like "Dr." no longer truncates a fact (`… is Dr.`). Improves the offline path
  the README promotes; no effect on the LLM path.

## [1.5.1] — 2026-06-03

### Changed
- **README rewritten from scratch for newcomers** — leads with a plain-language "what is
  this?", a ~60-second get-started (Claude Desktop `.mcpb` / Claude Code plugin / `pip`),
  example prompts, a privacy section, and an FAQ; the advanced surfaces (Docker, HTTP/REST,
  alternative model backends, CLI, configuration, internals) move into a collapsible
  section. Uses an absolute image URL so it renders on the PyPI project page too.
  Documentation only — no code change from 1.5.0.

## [1.5.0] — 2026-06-03

Phase-3 cross-AI interop — use the same eight local, token-free tools from non-MCP
clients and alternative local model servers. All additive and invariant-safe (still
token-free, 100% local by default, no new top-level dependency).

### Added
- **Secure Streamable HTTP transport** (opt-in; Phase-3 interop). `mta serve --http`
  exposes the same eight token-free tools over MCP Streamable HTTP for non-stdio
  clients, **alongside** the unchanged default stdio transport. Secure by
  construction: binds **loopback (`127.0.0.1`) only** unless `--allow-remote`
  (`MTA_HTTP_ALLOW_REMOTE=on`) is given explicitly; **every request requires a
  bearer token** (auto-generated and persisted `0600`, or set `MTA_HTTP_TOKEN`) —
  there is no unauthenticated mode; the SDK's **DNS-rebinding protection**
  (Host/Origin allowlist) stays on. An unauthenticated `/healthz` liveness probe
  is the only open route and never echoes the token. Knobs: `MTA_HTTP_HOST`,
  `MTA_HTTP_PORT` (default `8765`), `MTA_HTTP_PATH`, `MTA_HTTP_ALLOWED_HOSTS`,
  `MTA_HTTP_ALLOWED_ORIGINS`. Adds **no** new top-level dependency
  (`starlette`/`uvicorn` already ship with `mcp`). The server is now built by a
  `build_server()` factory so each transport owns its own session manager.
- **Cross-AI tool-schema export** (opt-in; Phase-3 interop). `mta export-schema
  [--format openai|gemini|openapi|all] [--out DIR]` emits the eight tools as an OpenAI
  function-calling array, a Gemini `function_declarations` object, and an **OpenAPI 3.1**
  document (`POST /tools/{name}`), so non-MCP clients can drive the same local engine.
  Schemas are derived from the live FastMCP registry (no drift) via the new
  `mta.interop.schemas` module — pure, offline, and token-free.
- **Local REST gateway** (opt-in; Phase-3 interop). `mta serve --rest` serves the eight
  tools as plain JSON over HTTP — `POST /tools/{name}` with an argument body returns the
  tool's token-free result — i.e. the exact OpenAPI 3.1 surface `export-schema` describes,
  with `GET /openapi.json` (live schema) and an unauthenticated `GET /healthz`. Reuses the
  WP-20 hardening: loopback-only by default, the **same** mandatory bearer token, and a
  Host-header allowlist (DNS-rebinding defense). New `mta.interop.rest`; blocking calls run
  in a threadpool. No new top-level dependency.
- **Pluggable inference backends** (Phase-3 interop). `MTA_BACKEND` selects where text
  generation (extraction + summaries) and embeddings run: `auto`/`ollama` (default,
  unchanged) or an **OpenAI-compatible** server (`lmstudio` · `llamacpp` · `vllm` ·
  `openai`) at `MTA_BACKEND_URL` (`/v1/chat/completions` + `/v1/embeddings`), with optional
  `MTA_BACKEND_KEY`. New `mta.core.backends` centralises the dispatch; the Ollama path is
  byte-identical and the classical/hashing offline fallback is unchanged, so a digest still
  succeeds when no backend is reachable. Vision/transcription stay on Ollama. The backend
  defaults to loopback; a non-local URL is the user's explicit opt-in (warned once).
  `memory_status` now reports the active backend. No new top-level dependency.
- **Per-client connection recipes** (Phase-3 interop). `mta recipes [--format text|json]`
  prints ready-to-paste setup for every surface — Claude Code (stdio/HTTP), Claude Desktop
  (`.mcpb`/`mcp.json`), the REST gateway (curl), and OpenAI/Gemini (exported schema + gateway)
  — composed from the transport/REST/schema seams (`mta.interop.recipes`). Backed by a
  **cross-surface conformance test** asserting stdio-MCP `tools/list`, the schema catalogue,
  the OpenAI/Gemini/OpenAPI exports, and the REST registry all expose the *same* eight tools.
- **Docker image (GHCR).** A multi-arch image (`linux/amd64` + `linux/arm64`) at
  `ghcr.io/gru-953/memorised-them-all` — multi-stage, runs as a non-root user, serves the
  tools over MCP Streamable HTTP, persists memory in a `/data` volume, and ships an OCI
  `/healthz` HEALTHCHECK. Built/validated in CI and pushed on release via the built-in
  `GITHUB_TOKEN` (no extra secret). Ollama isn't bundled — use a backend URL or the offline
  fallback.
- **MCP registry manifest.** A version-gated `server.json` (root) describing the PyPI package
  + stdio transport, ready for the official MCP registry (`io.github.gru-953/...` namespace).
  Submitted once by the owner via `mcp-publisher` (see `program/PUBLISH_MANIFEST.md`).

### Security / supply chain
- Committed **dependency lockfile** (`constraints.txt`, CI-09) for reproducible installs
  (`pip install -e ".[dev]" -c constraints.txt`); a non-blocking CI **supply-chain** job runs
  `pip-audit` (CVE scan) + a dependency-license report and verifies the lockfile resolves.
- **Release pipeline hardening:** the publish jobs (PyPI / GitHub Release / Homebrew) now run
  **only on a real tag push** — a manual `workflow_dispatch` builds + signs as a dry-run but
  never publishes (closes the tag-gate bypass). The Homebrew tap bump is now best-effort
  (`continue-on-error`), so a missing/expired tap token can never fail a release after PyPI
  and the GitHub Release have already shipped.

### Fixed
- **Recall-vector store consistency.** A digest now persists recall vectors (or clears them)
  *before* writing `graph.json`, and a digest that yields **no recall units** clears any prior
  vectors via the new `store.clear_vectors` — so a stale matrix (with refs into a previous
  graph) can no longer linger and make `recall` and `memory_overview` disagree.
- **PIPE-05:** `rapidfuzz` is a hard dependency, so a missing install now **warns loudly**
  (entity resolution otherwise silently degraded to exact-match, which over-splits entities).

## [1.4.0] — 2026-06-02

### Added
- **Configuration profiles** — `MTA_PROFILE=laptop|workstation|server|offline`
  applies a bundle of sensible defaults (an explicit `MTA_*` variable always
  wins). The resolved configuration is written to `state/config.json` and surfaced
  by `mta status` / `memory_status`, which now also report the detected
  **GPU/accelerator** (`mlx`/`cuda`/`rocm`/`none`) and whether a local **LM Studio**
  server is running.
- **`mta doctor`** — a dependency preflight: reports each runtime dependency and
  the `ollama`/`tesseract`/`ffmpeg` binaries as present / outdated / missing with
  **detected-vs-required** versions, and proposes argv-only, idempotent remediation
  (`--dry-run` previews; `--fix` applies the safe pip upgrades; system-tool installs
  are suggested per platform, never auto-run with sudo). Summary also in `memory_status`.
- **Evaluation harness** (`eval/`) — a committed reference corpus + golden metrics;
  `python eval/run_eval.py` digests offline and **gates retrieval recall@8 in CI**
  (baseline 1.0, floor 0.75). The unbenchmarked "20–100×" / "163 languages" claims
  are replaced with honest, measured wording.

### Changed
- **Offline-first auto-update** — the baseline MarkItDown is now the **pinned PyPI
  build** (in `requirements.txt`), so a first-ever digest no longer needs a live
  `git+https` fetch from upstream (restores the "100% local / works offline"
  promise on first run). Pulling the latest upstream MarkItDown is now **opt-in**
  (`MTA_MARKITDOWN_UPSTREAM=on`, or `MTA_AUTO_UPDATE=upstream`) and is **pinned to a
  resolved commit** rather than a moving branch. Upgrades are import-smoke-tested
  and **rolled back** to the previous version on failure; the throttle stamp is
  written atomically.
- MCP tools (`digest`, `recall`, `export_memory`) validate their inputs and return
  a small structured error instead of letting an exception cross the MCP boundary
  as a raw traceback (still token-free).
- `digest` stats report `mode: "classical"` when no local LLM ran (offline / Ollama
  unavailable) instead of mislabelling the run `"accurate"` (PIPE-04).
- Slash commands / skill synced with the tools: `/memorise` documents `fast`, a new
  **`/forget`** command, and `SKILL.md` lists `forget` + `fast` (DOC-21).
- Leaner, consistent `.mcpb`: `.mcpbignore` now excludes dev/internal dirs
  (`program/`, `eval/`, `scripts/`, `commands/`, `skills/`, …) and the zip fallback
  packs "everything minus `.mcpbignore`" to match the official `mcpb pack` (PKG-04).

### Fixed
- **Concurrency safety** — concurrent clients sharing one memory home no longer
  race. A digest / `forget` / reset takes an **exclusive** per-project lock and
  recall takes a **shared** lock (cross-process via `flock` / `msvcrt`), so the
  `graph.json` ↔ `vectors.npz` pair can never be torn and two digests on one
  project can't interleave. The on-demand Ollama start is serialised so two apps
  (Desktop + Code) can't both spawn a server. Lock files live under `state/locks/`
  so `forget` can't delete a held lock.
- **Availability** — when Ollama is installed but unreachable, the engine now
  fast-fails after one attempt (short cooldown) instead of stalling ~20 s on every
  model call across a digest.
- **Schema migration** — the on-disk store is a versioned schema: an older store
  is forward-migrated in memory (stays recall-readable after an upgrade), and a
  store written by a *newer* build is backed up under `backups/` before any
  overwrite — so a version downgrade can never silently lose memory.
- **Offline recall reliability** — `low_confidence` and `MTA_RECALL_MIN_SCORE` now
  work on the **offline/hashing** path (they were real-embeddings-only and silently
  no-op'd there): the confidence signal falls back to lexical overlap when no model
  is present, so an off-topic query is flagged low-confidence even fully offline.
  `top_score` now reflects the hits actually returned (with `raw_top_score` for the
  pre-floor best).

### Release & supply chain
- **Hardened, single-source release train** (`release.yml`): builds every artifact
  **once**, then publishes in lockstep `build → pypi → github_release → homebrew`
  (PyPI first, so a failure can't leave a partial release). **OIDC Trusted
  Publishing** to PyPI (no long-lived token); every Action is **SHA-pinned** (CI too);
  a **CycloneDX SBOM** and **cosign keyless signatures** are produced per artifact;
  the **Homebrew tap is auto-bumped** (gated on `HOMEBREW_TAP_TOKEN`, skips cleanly
  if absent); idempotent re-runs; tag == version gate. See `program/PUBLISH_MANIFEST.md`.

### Security
- **Decompression-bomb / size caps now cover all ZIP-container formats**
  (`.docx`/`.xlsx`/`.pptx`/`.epub`), not just literal `.zip` (SEC-01).
- The theme/synopsis summariser prompts fence document-derived text as data —
  second-order prompt-injection hardening, matching the per-chunk extractor (SEC-02).
- The vector store is loaded with `allow_pickle=False` **explicitly** (SEC-03).
- The offline mind map has **no CDN fallback** — it makes zero network requests; a
  missing renderer asset degrades to a static offline notice (SEC-10).
- Added **`SECURITY.md`** (threat model + reporting). The optional GPL `graph` extra
  is documented as not installed by the MIT core (SEC-11).

### Fixed (pre-release review)
- **Torn vector store is no longer fatal** — `load_vectors` rejects a desynced
  `vectors.npz`/`vectors.json` pair (matrix rows ≠ meta length) and recall clamps row
  indices, so a crash mid-write degrades to "no memory" instead of an IndexError.
- **Config profiles are concurrency-safe** — the profile env seed/restore in
  `config.load()` is serialised, so parallel `load()` under `MTA_PROFILE=offline`
  can't leak `no_ollama=False` / `auto_update=True`.
- **Offline recall stays declinable on the lexical path** — the dimension-mismatch
  fallback now also returns `low_confidence` / `top_score` / `synopsis` (DOC-01).
- The **synopsis** echoed by `recall`/`memory_overview` is length-capped (token-free).
- Auto-update **rollback is re-verified** (imports) before reporting success, and the
  pip install is serialised by a cross-process lock; `list_digestible` no longer
  crashes on a stat() race.

### Internal / CI
- **Phase-6 E2E** — a clean-wheel-install CLI suite (`tests/test_e2e_cli.py`) drives the
  installed `mta` binary end-to-end (offline + a real accurate-mode run via Ollama);
  `.github/workflows/e2e.yml` runs it on the release PR. The fast-mode speedup is now
  **benchmarked** (≈25–100×). See `program/TEST_REPORT.md`.
- CI now exercises the **real** conversion path: a new full-deps lane installs the
  package + Tesseract and converts PDF/DOCX/XLSX/CSV/HTML (the offline matrix
  installed no converters, so conversion was previously untested). The `.mcpb`
  bundle is built and smoke-tested in CI (the `mcpb` packer validates the manifest).
- **Single source of truth for the version** (`mta/__init__.py`): `pyproject`
  derives it dynamically, and `scripts/check_versions.py` (run in CI, and as a
  tag==version gate at release) fails on any drift across the manifests.
  (`CITATION.cff` had drifted to 1.3.2.)
- `test_ocr_stdin_pipe` skips cleanly when Pillow is absent (it previously *errored*
  under the CI dependency set); the stdio check now asserts all **8** tools.

## [1.3.3] — 2026-06-01

Fixes from another multi-agent evaluation loop (live accuracy/recall benchmark,
error-handling & leak stress, docs-vs-code audit, i18n/correctness sweep).

### Fixed
- **Atomic persistence** — `graph.json` and the vector store are written via
  temp-file + `fsync` + `os.replace`, so an interrupted digest can no longer
  truncate or desync an existing project's memory.
- **Unicode entity resolution** — normalisation is Unicode-aware; non-Latin
  (Bengali, CJK, Cyrillic) and accented names are no longer collapsed into one
  node (they previously all normalised to the empty string).
- **Numbered siblings** like `Reykjavik-1` / `Reykjavik-2` are no longer fuzzily
  merged into a single entity.
- Robustness: `recall` guards non-finite `k`; `export_memory` returns a status
  instead of raising on an unwritable destination; project-name slugs are
  length-capped; the mind map escapes `</` so an entity label can't break the
  inline script; classical (fast-mode) entity names collapse internal whitespace.

### Added
- **Recall relevance signal** — every `recall` result reports `top_score` and
  `low_confidence`, with an optional absolute floor (`MTA_RECALL_MIN_SCORE`, real
  embeddings only), so an off-topic query no longer feeds confident-looking junk
  to Claude.
- Bengali (`।`) and CJK (`。！？`) sentence terminators recognised in segmentation.

### Docs
- Corrected the tool count (eight), added `forget` to the manifest, made the
  "163 OCR languages" claim conditional on the language packs, and softened the
  fast-mode speedup figure to a measured range.

## [1.3.2] — 2026-06-01

### Changed
- **Redesigned README** — modern hero with a new social banner, SEO-optimised
  keywords and headings, quickstart matrix, use-cases, and a comparison table.
- **New logo / icon** (anti-aliased knowledge-graph mark) and a social-preview
  banner (`docs/social-preview.png`).

### Added
- `CITATION.cff` and expanded repository topics for discoverability.

No code or behaviour changes — packaging refreshes the bundled icon and metadata.

## [1.3.1] — 2026-06-01

Fixes from a further multi-agent evaluation loop (accuracy, token-safety,
reliability, reusability) + Copilot review.

### Fixed
- **Acronym linking no longer over-merges**: an acronym is linked to an expansion
  only when that expansion is unambiguous (a single candidate), so two distinct
  entities sharing initials (e.g. two "WHO"s) are never transitively merged.
- **Token-free guarantee hardened on the accurate path**: local-LLM theme/synopsis
  summaries are now length-capped (`num_predict`), and every recall hit clamps its
  text (≤600 chars) and `docs` list (≤5, with `doc_count`) — a verbose or
  prompt-injected summary can no longer bloat Claude's context.
- **No silent data loss**: same-named files in different folders (e.g. many
  `README.md`) get unique, race-free output names assigned in the main process
  instead of overwriting each other.
- **graph.json bounded**: facts are de-duplicated and capped per node (was
  duplicating heavily), shrinking the artifact and keeping it reusable.

### Added
- **`forget`** tool + `mta forget` CLI command to delete a project's memory.
- **Prompt-injection hardening**: document text is wrapped in explicit data
  delimiters in the extraction prompt (treated as data, never instructions).
- **Decompression-bomb guard** now also rejects archives containing nested
  archives.
- `launch.py`, `launch.sh`, `install.sh`, and `scripts/` are shipped in the sdist.

### Removed
- Dead `lru_cache` import in `embed.py`.

## [1.3.0] — 2026-06-01

Closes the v1.2.0 follow-up gaps.

### Added
- **Acronym ↔ expansion linking** in entity resolution: e.g. "NGA" now resolves
  to "Nordic Grid Authority" (exact initials + matching word count — precise, so
  it doesn't reintroduce over-merging).
- **Decompression-bomb guard**: `.zip` archives are inspected before MarkItDown
  extracts them; archives with an excessive uncompressed size or implausible
  compression ratio are skipped (`zip-too-large`).
- **`launch.py`** — a standard-library, cross-platform launcher/bootstrap
  (handles the Windows `Scripts/` vs POSIX `bin/` venv layout), so Windows MCP
  clients can run `python launch.py` directly.

[Unreleased gaps now addressed: acronym linking, archive bounding, Windows launcher.]

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

[1.3.3]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.3.3
[1.3.2]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.3.2
[1.3.1]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.3.1
[1.3.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.3.0
[1.2.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.2.0
[1.1.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.1.0
[1.0.1]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.0.1
[1.0.0]: https://github.com/GRU-953/memorised-them-all/releases/tag/v1.0.0
