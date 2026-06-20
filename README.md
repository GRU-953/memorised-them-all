<div align="center">

<img src="https://raw.githubusercontent.com/GRU-953/memorised-them-all/main/docs/social-preview.png" alt="Memorised them All — give Claude a private, local memory of your files" width="100%">

<h1>Memorised them All</h1>

<h3>Give Claude a private memory of your files — without paying for it in tokens.</h3>

<p>Point it at a folder of PDFs, Word/Excel files, or whole archives. It reads and remembers them <b>entirely on your own computer</b> — no AI models to install, no copy-pasting, no uploads, no API keys, no surprise token bills. Then just <i>ask Claude</i> about them later.</p>

[![PyPI](https://img.shields.io/pypi/v/memorised-them-all?color=ec4899&label=pip%20install)](https://pypi.org/project/memorised-them-all/)
[![Release](https://img.shields.io/github/v/release/GRU-953/memorised-them-all?color=6366f1&label=release)](https://github.com/GRU-953/memorised-them-all/releases/latest)
[![CI](https://github.com/GRU-953/memorised-them-all/actions/workflows/ci.yml/badge.svg)](https://github.com/GRU-953/memorised-them-all/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://pypi.org/project/memorised-them-all/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![100% local](https://img.shields.io/badge/100%25-local%20%26%20private-10b981)](#-is-my-data-private)
[![Model-free](https://img.shields.io/badge/AI%20models-none%20needed-10b981)](#-why-no-ai-model)
[![Claude tokens](https://img.shields.io/badge/Claude%20tokens-~0-10b981)](#-why-is-it-token-free)

<sub><b>v2.5</b> · works with Claude · Gemini · Cursor · VS Code · Codex · 100% local · deterministic · model-free · token-free · <a href="CHANGELOG.md">what's new →</a></sub>

<p>
<a href="#-what-is-this"><b>What is this?</b></a> ·
<a href="#-why-its-different">Why it's different</a> ·
<a href="#-get-started"><b>Get started</b></a> ·
<a href="#-your-first-memory">First memory</a> ·
<a href="#-what-can-i-use-it-for">Use cases</a> ·
<a href="#-english--bengali">Bengali</a> ·
<a href="#-questions--troubleshooting">FAQ</a> ·
<a href="#-for-power-users">Advanced</a>
</p>

</div>

---

## 🧠 What is this?

Imagine you could hand Claude a **filing cabinet** of your documents and say *"remember all of this."* Later you just ask questions, and Claude answers from what it remembers — telling you which document each fact came from.

That's **Memorised them All**. It's a small add-on (an [MCP server](https://modelcontextprotocol.io)) for **Claude Desktop** and **Claude Code** that:

1. **Reads your files** — PDFs, Word/Excel/PowerPoint (including *old* `.doc`/`.ppt`/`.xls`), web pages, CSVs, EPUBs, even zip/rar archives (unpacked safely) — and converts them to clean text **on your computer**.
2. **Builds a memory** — a searchable map of the people, topics, and facts inside them (a "knowledge graph"), plus a tidy synopsis and per-document notes.
3. **Lets you ask** — Claude recalls just the relevant, **cited** snippets when you ask, instead of you pasting whole files into the chat.

> **The one-line idea:** Claude tokens cost money; your computer's effort is free. So all the heavy lifting happens locally, and Claude only ever receives a tiny answer. Memorising a 500-page folder costs **roughly zero** chat tokens.

### 💬 See it in action

Once it's installed, you just talk to Claude normally:

```
You:    Memorise everything in ~/Documents/contracts.
Claude: ✅ Digested 38 files → 421 facts across 7 themes. (took ~30s, all local)

You:    Which contracts mention an auto-renewal clause, and when do they renew?
Claude: Three do — the Globex MSA (renews 1 Jan, 60-day notice), … [cites each source]

You:    What changed between the 2023 and 2024 progress reports?
Claude: Three headline shifts — … [cites each source document]
```

Nothing left your machine. Claude never saw the 38 files — only the small, cited answers. Behind the scenes, recall uses a fast on-device keyword search (BM25) to pick the few most relevant snippets, and **declines** when your question isn't actually covered.

---

## 🌟 Why it's different

<table>
<tr>
<td width="25%"><b>🔒 100% local & private</b><br><sub>Your files are read, converted, and remembered on your own machine. No telemetry, no uploads, no accounts, no API keys. <a href="#-is-my-data-private">More →</a></sub></td>
<td width="25%"><b>⚙️ Deterministic & model-free</b><br><sub>No LLM, no Ollama, no GPU, no embedding model. Pure rules — so a digest <i>always</i> finishes and the same folder always gives byte-identical memory. <a href="#-why-no-ai-model">More →</a></sub></td>
<td width="25%"><b>🪙 Token-free</b><br><sub>Your documents' contents are never sent to Claude. Building <i>and</i> recalling cost ≈0 context tokens. <a href="#-why-is-it-token-free">More →</a></sub></td>
<td width="25%"><b>🛡️ Robust & multilingual</b><br><sub>Per-file timeouts, crash-safe writes, safely-unpacked archives, and full legacy + Unicode <b>Bengali</b> support. <a href="#-built-to-be-reliable">More →</a></sub></td>
</tr>
</table>

---

## 🚀 Get started

You need **Python 3.10 or newer** (most Macs and Linux PCs already have it; Windows users can get it from [python.org](https://www.python.org/downloads/) — tick *"Add to PATH"*). There are **no AI models to download** — pick the row that matches how you use Claude:

| How you use Claude | Do this | Best for |
| --- | --- | --- |
| **Claude Desktop** (no terminal) | Download **`memorised-them-all.mcpb`** from the [latest release](https://github.com/GRU-953/memorised-them-all/releases/latest) and **double-click** → **Install**. | The easiest path. |
| **Claude Code** | `/plugin marketplace add GRU-953/memorised-them-all` then `/plugin install memorised-them-all` | Coding in the terminal. |
| **pip** (any setup) | `pip install memorised-them-all` then `mta setup` | Auto-configures **every AI client** found on your machine (Claude, Gemini, Cursor, VS Code, Windsurf, Codex). |
| **Homebrew** | `brew install GRU-953/memorised-them-all/mta` | macOS / Linux CLI users. |
| **Docker / GHCR** | `docker run … ghcr.io/gru-953/memorised-them-all:latest` ([details](#run-it-in-docker)) | Servers & containers. |
| **MCP registry** | published as `io.github.gru-953/memorised-them-all` ([`server.json`](server.json)) | MCP-aware clients. |

All paths give you the same thing. To add it to Claude by hand, it just runs `mta serve`:

```json
{
  "mcpServers": {
    "memorised-them-all": { "command": "mta", "args": ["serve"] }
  }
}
```

> **Do I need to install AI models?** **No.** The engine is deterministic (plain rules + maths), so it works the moment it's installed — the same on every computer, fully offline. To check your setup, run `mta doctor`.

### 🤝 Works with more than Claude

It's an [MCP](https://modelcontextprotocol.io) server, so the same local, token-free memory plugs into any AI client that speaks MCP. One command finds and configures **every client installed on your machine** — idempotently, with a backup of each file it touches:

```bash
mta setup            # auto-configure all detected clients
mta setup --dry-run  # just show what would change
```

| AI client | How it connects | Auto-configured by `mta setup`? |
| --- | --- | --- |
| **Claude** Desktop & Code | local (stdio) | ✅ |
| **Gemini** CLI | local (stdio) → `~/.gemini/settings.json` | ✅ |
| **Cursor** | local (stdio) → `~/.cursor/mcp.json` | ✅ |
| **VS Code** (Copilot agent) | local (stdio) → user `mcp.json` | ✅ |
| **Windsurf** | local (stdio) → `~/.codeium/windsurf/mcp_config.json` | ✅ |
| **OpenAI Codex** (ChatGPT's coding agent) | local (stdio) → `~/.codex/config.toml` | ✅ |
| **Grok** (Build CLI) | auto-discovers the Claude / `.mcp.json` config | ✅ (via Claude) |
| **ChatGPT** app · **xAI** API | remote MCP only (HTTPS) | run `mta serve --http`; see `mta recipes` |

The **ChatGPT app** and the **xAI API** accept only *remote* MCP endpoints, so they can't point at a local process — start the built-in secure HTTP server (`mta serve --http`) and paste the URL into their UI. `mta recipes` prints ready-to-use setup for every surface (stdio, HTTP-MCP, REST, OpenAI/Gemini function schemas).

---

## 📁 Your first memory

1. **Tell Claude what to remember** — point it at a folder, a file, or a pattern:
   > *"Memorise everything in ~/Documents/research."*

   (Behind the scenes Claude calls the `digest` tool. The first run may take a little longer while it sets things up.)

2. **Ask away** — in plain language:
   > *"What do my documents say about the Q3 budget?"*
   > *"Summarise everything about Project Apollo."*
   > *"Who is mentioned most often, and in which files?"*

3. **See the big picture, or take it with you:**
   > *"Give me an overview of what's in this memory."* (the `memory_overview` tool — synopsis + main themes)
   > *"Export the memory to ~/notes as Markdown."* (the `export_memory` tool — portable notes you can keep or share)

4. **Keep it tidy** — separate memories per topic with **projects**:
   > *"Memorise ~/work/clientA into a project called clientA."*
   > *"Using the clientA project, what were the agreed deliverables?"*
   > *"Forget the clientA project."* (deletes just that memory)

Your memory lives in a folder on your computer (`~/.memorised-them-all` by default) and persists between chats. Re-running *"memorise"* updates it.

---

## 🎯 What can I use it for?

- **📚 Research & study** — digest a pile of papers or a textbook, then ask for explanations, comparisons, and citations.
- **📑 Contracts & policies** — load all your agreements and ask *"which ones auto-renew?"* or *"what are the termination clauses?"*
- **🗂️ Personal knowledge base** — point it at years of notes, receipts, or manuals and actually *find* things.
- **🖼️ Scanned documents & images** — switch on OCR and it reads text from photos and scans so they become searchable.
- **🇧🇩 Legacy Bengali archives** — digitise old Bijoy/SutonnyMJ documents that show up as gibberish elsewhere, and actually search them (see [below](#-english--bengali)).
- **🔒 Sensitive material** — legal, medical, financial, or confidential files that must **never leave your machine**.

---

## 🪙 Why is it token-free?

When you normally share a document with Claude, the whole thing is sent into the conversation — and you pay (in tokens) for every word, every time. A few big PDFs can blow your whole context window.

Memorised them All flips that around:

- **Converting, reading, and summarising** your files happens **on your computer**.
- Claude only ever receives a **tiny result** — a count, a short summary, or a few relevant snippets (capped small).
- So memorising a giant folder, and asking about it again and again, stays **near-zero context tokens**.

It's the difference between mailing someone an entire library versus asking a librarian a question.

---

## 🔒 Is my data private?

**Yes — that's the whole point.** By default:

- ✅ **100% local.** Your files are read, converted, and remembered on your own machine. Their contents are **never** sent to Claude's servers, to us, or to anyone.
- ✅ **No telemetry, no tracking, no accounts, no API keys.**
- ✅ **Works fully offline.** Disconnect the internet and it still memorises and answers.
- ✅ **PII-aware.** Personal data such as phone numbers and survey/roster rows is deterministically dropped or redacted from summaries and recall, so sensitive details don't surface — even locally.
- ✅ **Open source (MIT).** You (or anyone) can read exactly what it does.

The only times anything touches the network are clearly optional and on *your* command: installing/updating software, an occasional check for a new version (turn off with `MTA_AUTO_UPDATE=off`), or *if you explicitly choose* to point it at a remote backend. With the defaults, **your documents stay with you.** See [SECURITY.md](SECURITY.md) for the full threat model.

---

## 🇧🇩 English & Bengali

A lot of Bengali documents were typed years ago with the **Bijoy** keyboard in **SutonnyMJ** (and 110+ other ANSI fonts). Opened as plain text, they come out as gibberish — so they're effectively unsearchable. **Memorised them All upgrades them to standard Unicode Bengali automatically**, so digest and recall work on real words instead of mojibake. (Modern Unicode Bengali — and every other language — already works out of the box.)

Four mechanisms, all deterministic and on-device:

- **Font-aware Office conversion** (`.docx`/`.pptx`/`.xlsx`) — only runs whose font is a Bijoy-family font are converted, so **mixed English + Bengali** documents come out clean (the English is left exactly as-is).
- **Line-wise PDF-text recovery** — Bengali pages inside a PDF whose text layer is Bijoy-encoded are recovered line by line, while English/already-correct lines are left untouched.
- **Vetted reorder-artifact repair** *(new in v2.4)* — some PDF fonts mis-encode a vowel sign, leaving common words stored mis-spelled (so a correct-Bengali search never matched them). A repair vetted by a Bengali-expert panel against the whole corpus recovers ~5,700 word-forms (গ্রুপ, শুরু, পুরুষ, গুরুত্ব …) while provably leaving correct words like নিম্ন untouched. It runs during extraction, so an existing memory is fixed by a simple rebuild — no re-conversion.
- **Auto re-OCR** — Bengali PDFs with a broken embedded font are re-read with OCR (Tesseract `eng+ben`).

Recall is Bengali-aware too (the search tokenizer keeps Bengali words whole). Built on a faithful pure-Python port of the [**Mukti**](https://github.com/anindash15-arch/Mukti) converter — no extra dependency, on by default (`MTA_BANGLA_LEGACY=off` to disable).

---

## 🛡️ Built to be reliable

It's been hardened through repeated, deliberate stress-testing and an expert-panel audit, so it stays calm on real, messy folders:

- **It always finishes.** A broken, enormous, or stuck file can't freeze the job — every file has a time limit and is skipped if it jams, so the rest still go through.
- **One bad file won't sink the batch.** Unreadable files, looping shortcuts, and odd or over-long filenames are skipped, never fatal.
- **Your memory is crash-safe.** If the computer is interrupted mid-write, your memory isn't corrupted or lost — writes are atomic, and anything that looks damaged is backed up before it's touched.
- **It's the same every time.** The engine is deterministic — memorising the same folder twice produces the identical memory, on any machine.
- **It reads awkward files.** Windows "Unicode" (UTF-16) text, archives (zip/tar/gz natively, rar/7z when an extractor is installed — unpacked safely, duplicates detected), and legacy Bengali fonts are handled; media, fonts, and junk files are skipped cleanly.
- **It can't be tricked into reading elsewhere.** A shortcut planted in a folder that points *outside* that folder is ignored — a digest only ever reads what you pointed it at, and archives are unpacked behind Zip-Slip, decompression-bomb, and depth guards.

---

## ❓ Questions & troubleshooting

<details>
<summary><b>Is it really free?</b></summary>

Yes — the software is free and open-source (MIT), and it runs on your own computer, so there are no per-use fees or token charges. The only "cost" is a little of your computer's time and disk space.
</details>

<details>
<summary><b>Claude says it doesn't have the tool / it's not showing up.</b></summary>

Make sure the extension/plugin is installed **and enabled**, then fully **restart Claude Desktop** (or your Claude Code session). To confirm the engine itself works, run `mta status` in a terminal — it should print your setup. Still stuck? Run `mta doctor`.
</details>

<details>
<summary><b>The first "memorise" was slow.</b></summary>

The first run sets things up. Later runs are much faster, and re-memorising only processes what changed. There's no AI model to download or load — the engine is deterministic and starts instantly.
</details>

<details>
<summary><b>What files can it read?</b></summary>

PDFs, Word/Excel/PowerPoint (including legacy binary `.doc`/`.ppt`/`.xls` when LibreOffice is installed), plain text/Markdown, HTML, CSV/JSON/XML, RTF, EPUB — plus **archives** (`.zip`/`.tar`/`.gz` natively; `.rar`/`.7z` when an extractor like `unar` is installed), which are unpacked safely and read. Beyond those, **any other text-based file is digested too** (source code, `.log`, `.tex`, …). Photos, video, audio, fonts, and junk files are skipped by default (scanned images can be OCR'd by setting `MTA_SKIP_MEDIA=off` if Tesseract is installed). Ask Claude to *"list what's digestible in this folder"* to see.
</details>

<details>
<summary><b>What languages does it understand?</b></summary>

Text in any language works (it's Unicode throughout), and Bengali gets special legacy-font handling (see [English & Bengali](#-english--bengali)). For **scanned documents and images**, OCR runs **English + Bangla by default** (`eng+ben`); set `MTA_OCR_LANG` to other [Tesseract codes](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html) (e.g. `eng+hin+ara`). Any language pack you don't have installed is dropped automatically, so it never errors.
</details>

<details>
<summary><b>How does it pick which snippets to show? Why are the answers cited?</b></summary>

Recall ranks the stored facts and themes against your question with **BM25**, a fast, classic keyword-relevance method that runs entirely on your machine (no AI model). It returns only the top few, each tagged with its source document — so answers are grounded and citable. If nothing relevant matches, recall flags **low confidence** so Claude can say *"I don't have that"* instead of guessing.
</details>

<details>
<summary><b>How do I delete a memory?</b></summary>

Tell Claude *"forget the clientA project"* (it asks you to name the project, on purpose). It deletes that project's memory from your disk — irreversibly.
</details>

<details>
<summary><b>Does it need an internet connection?</b></summary>

No. It's built to work completely offline. Internet is only used for optional, opt-in things like installing updates.
</details>

<details>
<summary><b>Does it use AI? Why are the summaries so plain?</b></summary>

No — and that's deliberate. Version 2 is **fully deterministic**: it extracts people, places, organisations, and facts with carefully-tuned rules (plain Python + maths), not an AI model. That means it **always works** (nothing to install, nothing to break, nothing to run out of memory), it's **fast**, and memorising the same folder twice gives the **identical** result. The trade-off is that summaries read more like structured notes than flowing prose — but every fact is grounded in your documents, and Claude (which IS the AI) does the smart reasoning at question time using the recalled facts.

*Coming from v1?* The optional local models (Ollama), the HTML mind-map, and audio transcription were all removed in v2. Old memories still load — re-memorise once (`reset: true`) to rebuild them with the deterministic engine.
</details>

---

## 🧰 The eight tools Claude gets

Once installed, Claude can use these eight tools on your behalf (you just talk normally — Claude picks the right one):

| Tool | What it does for you |
| --- | --- |
| **digest** | Reads files/folders and builds (or updates) the memory. |
| **convert** | Just converts files to clean Markdown (no memory) — handy for exporting or fixing legacy Bengali. |
| **recall** | Answers a question from memory with a few relevant, cited snippets. |
| **memory_overview** | Gives the big picture — a synopsis and the main themes. |
| **list_digestible** | Shows which files in a folder it can read. |
| **export_memory** | Saves the memory as portable Markdown notes you can keep or share. |
| **memory_status** | Reports your local setup — deterministic engine, OCR/MarkItDown availability, platform, and existing projects. |
| **forget** | Deletes a project's memory (you name it explicitly). |

Every tool returns only small results — **never your documents' contents**.

---

## 🛠️ For power users

You don't need any of this to use the app — but it's here if you want it.

<details>
<summary><b>Command line (no Claude needed)</b></summary>

The same engine ships as an `mta` command:

```bash
mta digest ~/Documents/research        # build/update memory (deterministic, model-free)
mta recall "what about the Q3 budget?" # query it (BM25 recall, cited slices)
mta overview                            # synopsis + themes
mta convert ~/docs --out ~/md_out       # just convert to Markdown (incl. legacy Bengali)
mta export ./notes                      # export portable Markdown
mta status                              # local stack health   ·   mta doctor  (fix deps)
mta setup                               # auto-configure every detected AI client (--dry-run to preview)
mta setup-claude                        # Claude-only variant (Desktop + Code)
```
</details>

<details>
<summary><b>Use it from other AI apps (Gemini, Cursor, VS Code, Codex, OpenAI, plain HTTP)</b></summary>

`mta setup` auto-registers the local server into every MCP client it finds (Claude, Gemini CLI, Cursor, VS Code, Windsurf, OpenAI Codex). For clients that take only *remote* MCP (the ChatGPT app, the xAI API) — or any other integration — the same eight tools are served beyond stdio:

```bash
mta setup            # auto-configure every detected stdio MCP client (--dry-run to preview)
mta serve --http     # MCP over HTTP (loopback + an auto-generated bearer token)
mta serve --rest     # plain JSON:  POST http://127.0.0.1:8765/tools/<name>
mta export-schema    # tool schemas as OpenAI / Gemini / OpenAPI 3.1 (no drift)
mta recipes          # copy-paste connection snippets for every client
```

Both HTTP modes are loopback-only by default and require a bearer token (with a DNS-rebinding guard). For the ChatGPT app or xAI API, start `mta serve --http` and paste the URL into their connector UI. See `mta recipes` for ready-to-paste setup for every surface.
</details>

<details>
<summary><b>Run it in Docker</b><a id="run-it-in-docker"></a></summary>

A multi-arch image (`amd64` + `arm64`) is published to GHCR:

```bash
docker run -d --name mta -p 127.0.0.1:8765:8765 -v mta-data:/data \
  ghcr.io/gru-953/memorised-them-all:latest
docker logs mta     # copy the printed bearer token + the `claude mcp add …` line
```

It serves the tools over MCP HTTP and keeps memory in the `/data` volume. Mount documents read-only (`-v /path/to/docs:/docs:ro`) and digest the in-container path.
</details>

<details>
<summary><b>Configuration</b></summary>

Everything has sensible defaults. Common knobs (set as environment variables):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MTA_HOME` | `~/.memorised-them-all` | where memory is stored |
| `MTA_SKIP_MEDIA` | `on` | skip photos/video/audio (set `off` to OCR images with Tesseract) |
| `MTA_SKIP_FONTS` / `MTA_SKIP_GDRIVE` / `MTA_SKIP_JUNK` | `on` | skip font files / Google-Drive pointer stubs / `.tmp`,`.DS_Store` junk |
| `MTA_ARCHIVE_RECURSIVE` | `on` | unpack zip/tar/gz (+ rar/7z via `unar`/`7z`) recursively, with bomb + path-traversal guards |
| `MTA_ARCHIVE_DEPTH` / `MTA_ARCHIVE_ENTRIES` | `8` / `100000` | nesting depth / member-count caps for archives |
| `MTA_OCR_LANG` | `eng+ben` | OCR languages (Tesseract codes; missing packs dropped automatically) |
| `MTA_BANGLA_LEGACY` | `on` | auto-convert legacy Bengali (Bijoy/SutonnyMJ) to Unicode |
| `MTA_CONVERT_TIMEOUT` | `120` | per-file conversion timeout (seconds); a file that hangs the parser is skipped, never stalls the batch. `0` disables |
| `MTA_MAX_FILE_MB` | `200` | per-file size cap (also drives the archive budgets) |
| `MTA_MAX_CHUNKS` | `1500` | cap on passages kept per memory (raise for very large corpora) |
| `MTA_OCR` | `auto` | OCR mode for PDFs/images: `auto`, `off`, `force`, `hybrid` |
| `MTA_RECALL_K` | `8` | default number of recall hits returned |
| `MTA_RECALL_MIN_SCORE` | `0` (off) | absolute BM25-score floor for recall hits (unbounded ≥0, **not** a 0–1 cosine) |
| `MTA_MEMORY_GB` | auto | override detected RAM (for containers/VMs that misreport it) |
| `MTA_WORKERS` / `MTA_EXTRACT_WORKERS` | auto | conversion / extraction workers (RAM/CPU-sized; 1 on small machines) |
| `MTA_AUTO_UPDATE` | `on` | daily MarkItDown update check (`off` to disable; `upstream` to track the latest upstream MarkItDown commit) |
| `MTA_HTTP_*` | off | options for the opt-in HTTP/REST servers |

</details>

<details>
<summary><b>Why no AI model? (v2 design)</b><a id="-why-no-ai-model"></a></summary>

Earlier versions could optionally use local AI models (via Ollama) for extraction and search, plus an HTML mind-map and audio transcription. **Version 2 removed all of them on purpose.** The deterministic engine:

- **always works** — nothing to download, install, crash, or run out of memory; the same on a 4 GB laptop and a 64 GB workstation;
- **is reproducible** — the same folder always produces the identical memory (great for auditing);
- **is fast** — no model loading, no GPU, instant startup;
- **stays private & token-free** — nothing ever leaves your machine, and Claude still only receives tiny slices.

The trade-off: extraction and search are rule- and keyword-based rather than semantic. In practice Claude compensates at question time — it reasons over the recalled facts. If you used v1.x with models: your old memories still load; re-memorise once (`reset: true`) to rebuild them with the deterministic engine.
</details>

<details>
<summary><b>Legacy Bengali (Bijoy / SutonnyMJ) → Unicode, and the <code>convert</code> command</b></summary>

Read as plain text, Bijoy/SutonnyMJ documents come out as mojibake. Memorised them All upgrades them to standard **Unicode Bengali automatically** during conversion, so digest and recall (BM25) work on real text instead of garbage. The full story is in [English & Bengali](#-english--bengali); briefly:

- **Font-aware for Office files** (`.docx`/`.pptx`/`.xlsx`): only Bijoy-family-font runs are converted, so mixed English + Bengali documents come out clean.
- **PDF-text recovery + a vetted reorder repair (v2.4)** for Bengali PDFs, and **auto re-OCR** for broken-font PDFs.
- A faithful pure-Python port of the [**Mukti**](https://github.com/anindash15-arch/Mukti) converter — no new dependency, fully local, on by default (`MTA_BANGLA_LEGACY=off` to disable).

**Convert a folder to Markdown** (with the legacy upgrade) without building memory:

```bash
mta convert ~/docs                 # writes ~/docs/markdown_converted/*.md
mta convert ~/docs --out ~/md_out  # …or choose the output folder
```

`digest` runs the very same conversion as its first step, so converting to Markdown is the default everywhere — reach for `convert` only when you want the `.md` files themselves.
</details>

<details>
<summary><b>How it works under the hood</b></summary>

`convert` (files → Markdown, locally; archives unpacked safely; duplicates deduped) → `extract` (entities, relations, facts — rule-based, deterministic) → `graph` (build + detect communities/themes) → `summarise` (layered: per-theme + a global synopsis, fact-joined) → `materialise` (memory.md + per-doc notes). At question time, `recall` ranks the stored facts/themes against your query with **BM25 lexical search** (model-free, Bengali-aware) and returns the closest, capped, cited snippets — with a low-confidence guard for off-topic questions. No models, no network — a digest **always** succeeds and is byte-for-byte reproducible. See [`CHANGELOG.md`](CHANGELOG.md) and [`SECURITY.md`](SECURITY.md) for details.
</details>

---

## 💻 Platforms

macOS, Linux, and Windows · Python 3.10–3.12 · tested on all three in CI on every change.

## 🙏 Credits & license

Built on the shoulders of [MarkItDown](https://github.com/microsoft/markitdown), [NetworkX](https://networkx.org), and the [Model Context Protocol](https://modelcontextprotocol.io); legacy-Bengali conversion is a pure-Python port of [Mukti](https://github.com/anindash15-arch/Mukti). Optional community-detection extras (`python-igraph`, `leidenalg`) are GPL-licensed and **not** installed by the MIT core. See [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

**MIT licensed** · made by [GRU-953](https://github.com/GRU-953). Issues and contributions welcome — start with [`SECURITY.md`](SECURITY.md) for the security model.

<div align="center">
<sub>100% local · deterministic · token-free · free &amp; open-source · your files never leave your machine.</sub>
</div>
