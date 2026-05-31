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

> **Requirements:** macOS (Apple silicon recommended) · [Homebrew](https://brew.sh)
> · Python ≥ 3.10. The installer fetches everything else for you.

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
mta recall "who leads the project and who are the partners?" --project aurora
mta overview --project aurora
mta mindmap --project aurora --open
mta export ~/Desktop/aurora-memory --project aurora
mta update            # pull the latest MarkItDown + dependencies
```

## MCP tools

| Tool | What it does | Returns |
| --- | --- | --- |
| `digest(paths, project?, reset?)` | convert + digest files/dirs/globs (**accumulates** into the project; `reset=true` starts fresh) | counts, paths, graph stats |
| `recall(query, project?, k?)` | answer from memory | a small, citable slice |
| `memory_overview(project?)` | synopsis + themes | compact overview |
| `export_memory(dest, project?)` | export portable Markdown | files written |
| `list_digestible(directory)` | list convertible files | paths + sizes |
| `memory_status()` | local stack health | versions, models, projects |
| `open_mindmap(project?)` | offline mind map | file path |

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
| `MTA_COMMUNITY_ALGO` | `auto` | `leiden` · `louvain` · `greedy` |
| `MTA_AUTO_UPDATE` | `on` | auto-update MarkItDown & dependencies |
| `MTA_NO_OLLAMA` | unset | hard offline switch (classical + hashing) |

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
