<div align="center">

<img src="assets/icon.png" alt="Memorised them All" width="128" height="128">

# Memorised them All

### Convert any attachment to Markdown and digest it into **token-free knowledge-graph memory** for Claude — 100% locally.

[![CI](https://github.com/GRU-953/memorised-them-all/actions/workflows/ci.yml/badge.svg)](https://github.com/GRU-953/memorised-them-all/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/GRU-953/memorised-them-all?color=6366f1)](https://github.com/GRU-953/memorised-them-all/releases)
[![PyPI](https://img.shields.io/pypi/v/memorised-them-all?color=ec4899)](https://pypi.org/project/memorised-them-all/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Apple silicon](https://img.shields.io/badge/Apple%20silicon-optimised-black?logo=apple)](#apple-silicon-first)
[![Token cost](https://img.shields.io/badge/Claude%20tokens-~0-10b981)](#why-its-token-free)

**by [GRU-953](https://github.com/GRU-953)** · Claude Desktop + Claude Code · free & open-source · runs entirely on your machine

</div>

---

> **The idea.** Claude tokens are expensive; your Mac's compute is free. So every
> heavy step — converting documents, extracting knowledge, building the graph,
> embedding, summarising — runs **locally**. Claude only ever issues a tiny tool
> call and gets back compact metadata or a small, relevant slice — **never whole
> documents**. Digesting a 500-page folder costs roughly **zero context tokens**.

Point it at a folder. It converts every attachment to Markdown, then digests it
into a layered knowledge graph — a global synopsis, per-theme summaries,
per-document notes, an exportable Markdown bundle, and an offline interactive
mind map — and lets Claude recall from it for next to nothing.

## Contents

[Why it's token-free](#why-its-token-free) ·
[What you get](#what-you-get) ·
[How it works](#how-it-works) ·
[Install](#install) ·
[Use it](#use-it) ·
[Tools](#mcp-tools) ·
[Configuration](#configuration) ·
[Apple silicon](#apple-silicon-first) ·
[Privacy](#privacy) ·
[FAQ](#faq) ·
[Modes & performance](#modes--performance) ·
[Platform support](#platform-support) ·
[Generated files & reuse](#generated-files--reuse) ·
[Quality & testing](#quality--testing) ·
[Security](#security--threat-model) ·
[Acknowledgements](#acknowledgements)

## Why it's token-free

Most "chat with your docs" tools stream document text into the model — you pay
tokens to ingest *and* to recall. Memorised them All never does that:

| Step | Where it runs | Tokens to Claude |
| --- | --- | --- |
| Convert PDF/Office/image/audio → Markdown | your Mac (MarkItDown, Tesseract, Whisper, Ollama) | 0 |
| Extract entities · relations · facts | your Mac (local LLM, classical fallback) | 0 |
| Embed · resolve · build graph · summarise themes | your Mac (Ollama + NetworkX) | 0 |
| **`digest` tool result** | — | only counts & paths |
| **`recall` tool result** | — | a small, relevant slice (not documents) |

## What you get

- 📄 **Universal local conversion** — PDF, Word, Excel, PowerPoint, HTML, EPub,
  Outlook `.msg`, CSV/JSON/XML, images (OCR + vision captioning), audio
  (on-device transcription) → clean Markdown.
- 🕸️ **A layered knowledge graph** — entities, typed relations and atomic facts,
  grouped into **communities (themes)** with local summaries. Three memory
  layers: global synopsis → theme summaries → provenance-tracked facts.
- 📝 **Exportable Markdown memory** — `memory.md`, one note per source document,
  and `graph.json` — copy them anywhere.
- 🧭 **Offline interactive mind map** — a single self-contained `mindmap.html`
  (Cytoscape inlined, no network) you can open in any browser.
- 🔁 **Reusable, named projects** — keep separate memories per body of work.
- ⚙️ **Auto-installing & auto-updating** — pulls the latest MarkItDown from
  upstream and keeps dependencies current. Starts the model server on demand and
  **stops it after 5 minutes idle**.

## How it works

```
attachments ─► CONVERT ─► SEGMENT ─► EMBED ─► EXTRACT ─► RESOLVE ─► GRAPH + COMMUNITIES ─► MATERIALISE
  pdf/docx/   MarkItDown  structure  nomic-   local LLM  canonical  NetworkX +             graph.json
  xlsx/img/   +Tesseract  +semantic  embed-   triples +  entities   Leiden / Louvain        memory.md
  audio/...   +Whisper    chunking   text     facts      (embed +   community summaries     memory/<doc>.md
              +Ollama                          (+class-   fuzzy)     (local LLM)             mindmap.html
               vision                           ical                                         vectors store
                                                fallback)
                                                                              │
   recall("…")  ◄── embed query locally ──  return ONLY a small relevant slice (themes + facts + provenance)
```

Everything between *attachments* and *recall* happens on your machine. The local
LLM step has a **dependency-free classical fallback**, so a digest always
succeeds — even offline, even before any model is downloaded — and gets sharper
once the models are present.

## Install

> **Requirements:** macOS (Apple silicon recommended), Linux, or Windows ·
> Python ≥ 3.10 · [Homebrew](https://brew.sh) on macOS/Linux (the installer uses
> apt/dnf/pacman if Homebrew is absent on Linux). The installer fetches everything
> else for you. See [Platform support](#platform-support) for details.

### Claude Desktop (one click)

1. Download `memorised-them-all.mcpb` from the
   [latest release](https://github.com/GRU-953/memorised-them-all/releases/latest).
2. Double-click it (or **Settings → Extensions → Install**).
3. On first launch it bootstraps the local stack automatically.

### Claude Code (CLI)

```bash
/plugin marketplace add GRU-953/memorised-them-all
/plugin install memorised-them-all
```

### As a plain CLI / from PyPI

```bash
pip install memorised-them-all      # installs the `mta` command
mta status                          # check the local stack
mta digest ~/Documents/research     # build memory from a folder
```

### From source / Homebrew

```bash
git clone https://github.com/GRU-953/memorised-them-all
cd memorised-them-all && ./install.sh        # idempotent: brew apps + venv + models

# or via the tap
brew install GRU-953/memorised-them-all/mta
```

The installer adds (only what's missing): **Ollama**, **Tesseract** (+ all OCR
languages), **ffmpeg**, a Python virtualenv with the **latest MarkItDown** from
upstream, and the local models `qwen2.5:7b`, `nomic-embed-text`, `moondream`
(~6–8 GB, configurable — pulled in the background).

## Use it

**In Claude** (Desktop or Code), just ask:

> "Memorise everything in `~/Documents/grant-proposals`."
> "What did my documents say about the Aurora timeline?"
> "Open the mind map." · "Export the memory to `~/Desktop/aurora-memory`."

Or use the slash commands: `/memorise`, `/recall`, `/memory-map`,
`/memory-status`, `/export-memory`.

**From the terminal:**

```bash
mta digest ~/Documents/research --project aurora
mta digest ~/Documents/big-corpus --project aurora --fast   # deterministic, ~100× faster
mta recall "who leads the project and who are the partners?" --project aurora
mta overview --project aurora
mta mindmap --project aurora --open
mta export ~/Desktop/aurora-memory --project aurora
mta forget --project aurora    # delete this project's memory
mta update                     # pull the latest MarkItDown + dependencies
```

## MCP tools

| Tool | What it does | Returns |
| --- | --- | --- |
| `digest(paths, project?, reset?, fast?)` | convert + digest files/dirs/globs (**accumulates** into the project; `reset=true` starts fresh; `fast=true` skips the LLM) | counts, paths, graph stats |
| `recall(query, project?, k?)` | answer from memory | a small, citable slice |
| `memory_overview(project?)` | synopsis + themes | compact overview |
| `export_memory(dest, project?)` | export portable Markdown | files written |
| `list_digestible(directory)` | list convertible files | paths + sizes |
| `memory_status()` | local stack health | versions, models, projects |
| `open_mindmap(project?)` | offline mind map | file path |
| `forget(project?)` | delete a project's memory (irreversible) | status |

Every result is metadata or a small slice — **document contents never return to
the conversation**.

## Configuration

All optional; sensible defaults. Set via environment (CLI) or the extension
settings (Desktop).

| Variable | Default | Meaning |
| --- | --- | --- |
| `MTA_HOME` | `~/.memorised-them-all` | where memories are stored |
| `MTA_EXTRACT_MODEL` | `qwen2.5:7b` | local LLM for extraction & summaries |
| `MTA_EMBED_MODEL` | `nomic-embed-text` | local embedding model |
| `MTA_VISION_MODEL` | `moondream` | image captioning |
| `MTA_OCR_LANG` | `eng` | Tesseract languages, e.g. `eng+ben` |
| `MTA_WHISPER_MODEL` | `base` | on-device transcription model |
| `MTA_IDLE` | `300` | seconds of idle before Ollama is stopped |
| `MTA_WORKERS` | `0` (auto) | parallel conversion workers |
| `MTA_EXTRACT_WORKERS` | `0` (auto) | parallel extraction workers (memory-aware: 1–3 by RAM) |
| `MTA_MAX_CHUNKS` | `1500` | safety cap on chunks per digest (truncation is reported) |
| `MTA_MAX_FILE_MB` | `200` | skip files larger than this before reading (0 disables) |
| `MTA_COMMUNITY_ALGO` | `auto` | `leiden` · `louvain` · `greedy` |
| `MTA_AUTO_UPDATE` | `on` | auto-update MarkItDown & dependencies |
| `MTA_FAST` | `off` | fast mode — skip the LLM (classical extraction, deterministic, keeps embeddings) |
| `MTA_NO_OLLAMA` | unset | hard offline switch (classical + hashing) |

> **Accuracy vs speed.** The default path uses the local LLM for the highest
> extraction accuracy. **Fast mode** (`MTA_FAST=on`, `mta digest --fast`, or the
> `fast=true` tool arg) skips the LLM for a fully **deterministic**, ~100× faster
> digest that still builds the graph and keeps semantic recall — ideal for large
> or frequently-updated corpora.

## Apple silicon first

- Conversion fans out across **performance cores** (`hw.perflevel0.physicalcpu`),
  with each worker's native math libraries pinned to one thread to avoid
  oversubscription on the unified-memory architecture.
- **GPU-accelerated Whisper** via Apple **MLX** (`mlx-whisper`), with a
  `faster-whisper` CPU fallback.
- Worker count is **unified-memory-aware** so it won't thrash a 16 GB Mac.

It runs on Intel Macs and Linux too — those paths simply use portable defaults.

## Privacy

100% local. No cloud APIs, no telemetry, no API keys. Your documents, the graph,
the embeddings, and the memory files never leave your machine. The only network
access is (a) downloading open-source dependencies/models on install and
(b) the once-a-day dependency update check (disable with `MTA_AUTO_UPDATE=off`).

## FAQ

**Does it really cost no tokens?** Conversion and digestion cost **zero** Claude
tokens. `recall` returns a small slice (a handful of summaries/facts), so answers
are cheap — far cheaper than pasting documents into the chat.

**What if I have no GPU / no models / I'm offline?** It still works. The classical
extractor and hashing embeddings keep the pipeline running; quality improves once
Ollama and the models are available.

**Is my existing Ollama affected?** No. If Ollama is already running, it's reused
and left alone. Only an instance *this tool* starts is stopped on idle.

**Where are my files?** Under `MTA_HOME/projects/<project>/` — `graph.json`,
`memory.md`, `memory/`, `mindmap.html`. `export_memory` copies them anywhere.

## Modes & performance

Two digest modes — the default favours **accuracy & consistency**, fast mode favours **speed & determinism**:

| | Default (accurate) | Fast (`--fast` / `MTA_FAST=on`) |
| --- | --- | --- |
| Extraction | local LLM (qwen2.5) | classical (deterministic) |
| Theme summaries | local LLM | deterministic fact-join |
| Embeddings / recall | local (nomic) | local (nomic) |
| Reproducible | per-model | **byte-identical across runs** |
| Relative speed | baseline | **~100× faster** |
| Best for | highest fidelity | large or frequently-refreshed corpora |

Both are **token-free** and **fully local**. Digestion is incremental — pointing `digest` at another folder *extends* the same project; `reset=true` starts fresh. Degenerate/repetitive content is de-duplicated and a reported `MTA_MAX_CHUNKS` cap keeps even pathological inputs bounded.

## Platform support

Apple M-series is the primary, most-optimised target. Other platforms are supported with portable fallbacks:

| Platform | Status | Notes |
| --- | --- | --- |
| macOS (Apple silicon) | ✅ optimised | performance-core pool, MLX GPU Whisper, unified-memory-aware |
| macOS (Intel) | ✅ supported | physical-core sizing via psutil, CPU Whisper |
| Linux | ✅ supported | apt/dnf/pacman install paths, CUDA Whisper if a GPU is present |
| Windows | 🧪 experimental | `pip install memorised-them-all` then `mta serve` (or `python launch.py` from a clone). The one-click `.mcpb` bundle is macOS/Linux only (its launcher is bash); on Windows use pip. |

CI runs the offline test suite across **Ubuntu, macOS, and Windows** on Python 3.10 & 3.12.

## Generated files & reuse

Each project under `MTA_HOME/projects/<name>/` is self-contained and portable:

| File | What it is |
| --- | --- |
| `graph.json` | source of truth — nodes, edges, communities, layered summaries, stats (`version`-stamped; stores basenames, no absolute paths) |
| `memory.md` | compact, layered digest for reading / pasting |
| `memory/<doc>.md` | one note per source document |
| `mindmap.html` | offline interactive graph (Cytoscape inlined) |
| `vectors.npz` + `vectors.json` | local embeddings for recall |

A memory built once can be **copied to another machine** and reused read-only — recall and the mind map work with no rebuild. `export_memory` bundles all of the above (including the vector store) into a folder you choose.

## Quality & testing

This project is exercised hard: a multi-format corpus (Office, PDF, scanned PDF, OCR images, audio), **14 regression tests** (determinism, token-safety, fact attribution, accumulation, OCR, lifecycle, cross-platform), green CI on three OSes, and a multi-agent review pass covering accuracy, reliability, token-safety, reusability, cross-platform, and security. The token-free guarantee is enforced (recall slices are hard-capped) and the digest never returns document contents to the model.

## Security & threat model

Memorised them All processes files you point it at — including, potentially,
untrusted documents. It is hardened accordingly:

- **No shell injection / no `curl | sh`**: all subprocesses use argv lists; the
  optional installer downloads to a temp file before executing.
- **Path-safe outputs**: converted filenames are sanitised; same-named files in
  different folders get unique names (no silent overwrite); exports write only
  the memory artifacts to the destination you choose.
- **Bounded inputs**: per-file size cap (`MTA_MAX_FILE_MB`), a reported chunk cap,
  and a decompression-bomb guard for archives (size, ratio, and nested-archive
  rejection).
- **Prompt-injection aware**: extracted document text is wrapped as *data* in the
  local-LLM prompt. Note that theme/synopsis summaries are model output over your
  documents — treat them as you would any generated text. Recall results are
  hard-capped in size so a verbose or adversarial summary cannot bloat context.
- **No deserialization risk**: JSON only; `numpy` loads with `allow_pickle=False`.
- **Local-only egress**: the only network calls are localhost Ollama, dependency
  installs, and a throttled once-a-day GitHub update check (opt out with
  `MTA_AUTO_UPDATE=off`).

Manage projects with `mta forget --project <name>` (or the `forget` tool) to
delete a memory; the `.mcpb` one-click bundle targets macOS/Linux (Windows uses
`pip install` + `mta serve`).

## Acknowledgements

Built on the shoulders of excellent open-source work — see
[ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md). In particular:
[Microsoft MarkItDown](https://github.com/microsoft/markitdown),
[Ollama](https://github.com/ollama/ollama),
[Tesseract](https://github.com/tesseract-ocr/tesseract),
[OpenAI Whisper](https://github.com/openai/whisper) /
[faster-whisper](https://github.com/SYSTRAN/faster-whisper) /
[Apple MLX](https://github.com/ml-explore/mlx-examples),
[NetworkX](https://github.com/networkx/networkx),
[Leiden / igraph](https://github.com/vtraag/leidenalg), and
[Cytoscape.js](https://github.com/cytoscape/cytoscape.js). Design inspiration from
[graphify](https://github.com/safishamsi/graphify) and the author's own
[markitdown-mcp](https://github.com/GRU-953/markitdown-mcp) and
[mnemo-mcp](https://github.com/GRU-953/mnemo-mcp).

## License

[MIT](LICENSE) © 2026 Aninda Sundar Howlader ([GRU-953](https://github.com/GRU-953)).
