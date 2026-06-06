<div align="center">

<img src="https://raw.githubusercontent.com/GRU-953/memorised-them-all/main/docs/social-preview.png" alt="Memorised them All — give Claude a private, local memory of your files" width="100%">

<h1>Memorised them All</h1>

<h3>Give Claude a private memory of your files — without paying for it in tokens.</h3>

<p>Point it at a folder of PDFs, Word/Excel files, images, or audio. It reads and remembers them <b>entirely on your own computer</b>, so you can just <i>ask Claude</i> about them later — no copy-pasting, no uploads, no API keys, no surprise token bills.</p>

[![PyPI](https://img.shields.io/pypi/v/memorised-them-all?color=ec4899&label=pip%20install)](https://pypi.org/project/memorised-them-all/)
[![Release](https://img.shields.io/github/v/release/GRU-953/memorised-them-all?color=6366f1&label=release)](https://github.com/GRU-953/memorised-them-all/releases/latest)
[![CI](https://github.com/GRU-953/memorised-them-all/actions/workflows/ci.yml/badge.svg)](https://github.com/GRU-953/memorised-them-all/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://pypi.org/project/memorised-them-all/)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)
[![100% local](https://img.shields.io/badge/100%25-local%20%26%20private-10b981)](#-is-my-data-private)
[![Claude tokens](https://img.shields.io/badge/Claude%20tokens-~0-10b981)](#-why-is-it-free-of-token-cost)

<p>
<a href="#-what-is-this"><b>What is this?</b></a> ·
<a href="#-get-started-in-about-a-minute"><b>Get started</b></a> ·
<a href="#-your-first-memory">First memory</a> ·
<a href="#-what-can-i-use-it-for">Use cases</a> ·
<a href="#-questions--troubleshooting">FAQ</a> ·
<a href="#-for-power-users">Advanced</a>
</p>

</div>

---

## 🧠 What is this?

Imagine you could hand Claude a **filing cabinet** of your documents and say *"remember all of this."* Later you just ask questions, and Claude answers from what it remembers — citing which document each fact came from.

That's **Memorised them All**. It's a small add-on (an [MCP server](https://modelcontextprotocol.io)) for **Claude Desktop** and **Claude Code** that:

1. **Reads your files** — PDFs, Word/Excel/PowerPoint, web pages, images (with OCR), even audio — and converts them to clean text **on your computer**.
2. **Builds a memory** — a searchable map of the people, topics, and facts inside them (a "knowledge graph"), plus a tidy summary and an interactive **mind map**.
3. **Lets you ask** — Claude recalls just the relevant bits when you ask, instead of you pasting whole files into the chat.

> **The one-line idea:** Claude tokens cost money; your computer's effort is free. So all the heavy lifting happens locally, and Claude only ever receives a tiny answer. Memorising a 500-page folder costs **roughly zero** chat tokens.

### 💬 See it in action

Once it's installed, you just talk to Claude normally:

```
You:    Memorise everything in ~/Documents/contracts.
Claude: ✅ Digested 38 files → 421 facts across 7 themes. (took ~30s, all local)

You:    Which contracts mention an auto-renewal clause, and when do they renew?
Claude: Three do — the Globex MSA (renews 1 Jan, 60-day notice), … [cites each source]

You:    Open the mind map.
Claude: Here's your interactive map: /…/mindmap.html
```

Nothing left your machine. Claude never saw the 38 files — only the small answers.

---

## 🚀 Get started in about a minute

You need **Python 3.10 or newer** (most Macs and Linux PCs already have it; Windows users can install it from [python.org](https://www.python.org/downloads/) — tick *"Add to PATH"*). Everything else installs automatically the first time you use it.

Pick whichever matches how you use Claude:

### ▶ Claude Desktop (easiest — no terminal)

1. Download **`memorised-them-all.mcpb`** from the [**latest release**](https://github.com/GRU-953/memorised-them-all/releases/latest).
2. **Double-click it.** Claude Desktop opens and offers to install the extension — click **Install**.
3. Done. Start a chat and say *"Memorise my Documents folder."*

### ▶ Claude Code

```bash
claude
# then, inside Claude Code:
/plugin marketplace add GRU-953/memorised-them-all
/plugin install memorised-them-all
```

### ▶ Any other setup (pip)

```bash
pip install memorised-them-all
```

Then register it with Claude — easiest is to let it configure itself:

```bash
mta setup-claude     # writes the MCP server into Claude Desktop (and Claude Code) config
```

(The `install.sh` installer runs this for you automatically.) Or add it by hand — it just runs `mta serve`:

```json
{
  "mcpServers": {
    "memorised-them-all": { "command": "mta", "args": ["serve"] }
  }
}
```

> 💡 Prefer Homebrew or Docker? `brew install GRU-953/memorised-them-all/mta`, or see [Run it in Docker](#run-it-in-docker). All paths give you the same thing.

### Do I need to install AI models?

**No — it works the moment it's installed.** Out of the box it uses fast, built-in techniques (no downloads, fully offline).

For **sharper** summaries and search, it can optionally use a **free local AI model** via [Ollama](https://ollama.com) (still 100% on your machine). If Ollama is present it's used automatically; if not, you're never blocked. To check what you have and get one-line setup tips, run:

```bash
mta doctor
```

---

## 📁 Your first memory

1. **Tell Claude what to remember** — point it at a folder, a file, or a pattern:
   > *"Memorise everything in ~/Documents/research."*

   (Behind the scenes Claude calls the `digest` tool. The first run may take a little longer while it sets things up.)

2. **Ask away** — in plain language:
   > *"What do my documents say about the Q3 budget?"*
   > *"Summarise everything about Project Apollo."*
   > *"Who is mentioned most often, and in which files?"*

3. **Explore visually** *(optional)*:
   > *"Open the mind map."* — an interactive, offline map of how everything connects.

4. **Keep it tidy** — separate memories per topic with **projects**:
   > *"Memorise ~/work/clientA into a project called clientA."*
   > *"Using the clientA project, what were the agreed deliverables?"*

Your memory lives in a folder on your computer (`~/.memorised-them-all` by default) and persists between chats. Re-running *"memorise"* updates it.

---

## 🎯 What can I use it for?

- **📚 Research & study** — digest a pile of papers or a textbook, then ask for explanations, comparisons, and citations.
- **📑 Contracts & policies** — load all your agreements and ask "which ones auto-renew?" or "what are the termination clauses?"
- **🗂️ Personal knowledge base** — point it at years of notes, receipts, or manuals and actually *find* things.
- **🎧 Meetings & lectures** — drop in audio recordings; it transcribes locally and remembers the content.
- **🖼️ Scanned documents & images** — it reads text from photos and scans (OCR) so they become searchable.
- **🔒 Sensitive material** — legal, medical, financial, or confidential files that must **never leave your machine**.

---

## ✨ Why is it free of token cost?

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
- ✅ **Open source (MIT).** You (or anyone) can read exactly what it does.

The only times anything touches the network are clearly optional and on *your* command: installing/updating software, an occasional check for a new version (turn off with `MTA_AUTO_UPDATE=off`), or *if you explicitly choose* to point it at a remote AI backend. With the defaults, **your documents stay with you.** See [SECURITY.md](SECURITY.md) for the full threat model.

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

The first run sets things up (and, if you have Ollama, may load a model). Later runs are much faster, and re-memorising only processes what changed. Add `fast` ("memorise … in fast mode") to skip the AI step entirely for a quick, fully-deterministic pass.
</details>

<details>
<summary><b>What files can it read?</b></summary>

PDFs, Word/Excel/PowerPoint, plain text/Markdown, HTML, CSV/JSON/XML, RTF, EPUB, common images (via OCR), and audio (transcribed locally). Beyond those, **any other text-based file is digested too** (source code, `.log`, `.ini`, `.tex`, …); only genuine binaries are skipped — so a whole folder gets captured. Ask Claude to *"list what's digestible in this folder"* to see.
</details>

<details>
<summary><b>What languages does it understand?</b></summary>

Text in any language works (it's Unicode throughout). For **scanned documents and images**, OCR runs **English + Bangla by default** (`eng+ben`); set `MTA_OCR_LANG` to other [Tesseract codes](https://tesseract-ocr.github.io/tessdoc/Data-Files-in-different-versions.html) (e.g. `eng+hin+ara`). Any language pack you don't have installed is dropped automatically, so it never errors.
</details>

<details>
<summary><b>How do I delete a memory?</b></summary>

Tell Claude *"forget the clientA project"* (it asks you to name the project, on purpose). It deletes that project's memory from your disk — irreversibly.
</details>

<details>
<summary><b>Does it need an internet connection?</b></summary>

No. It's built to work completely offline. Internet is only used for optional, opt-in things like installing updates.
</details>

---

## 🧰 The tools Claude gets

Once installed, Claude can use these eight tools on your behalf (you just talk normally — Claude picks the right one):

| Tool | What it does for you |
| --- | --- |
| **digest** | Reads files/folders and builds (or updates) the memory. |
| **recall** | Answers a question from memory with a few relevant, cited snippets. |
| **memory_overview** | Gives the big picture — a synopsis and the main themes. |
| **list_digestible** | Shows which files in a folder it can read. |
| **open_mindmap** | Opens the interactive, offline mind map. |
| **export_memory** | Saves the memory as portable Markdown notes you can keep or share. |
| **memory_status** | Reports your local setup (models, tools, projects). |
| **forget** | Deletes a project's memory (you name it explicitly). |

Every tool returns only small results — never your documents' contents.

---

## 🛠️ For power users

You don't need any of this to use the app — but it's here if you want it.

<details>
<summary><b>Command line (no Claude needed)</b></summary>

The same engine ships as an `mta` command:

```bash
mta digest ~/Documents/research        # build/update memory (--fast to skip the LLM)
mta recall "what about the Q3 budget?" # query it
mta overview                            # synopsis + themes
mta status                              # local stack health   ·   mta doctor  (fix deps)
mta export ./notes                      # export portable Markdown
mta mindmap --open                      # open the mind map
```
</details>

<details>
<summary><b>Use it from other AI apps (OpenAI, Gemini, plain HTTP)</b></summary>

The same eight tools can be served beyond Claude:

```bash
mta serve --http     # MCP over HTTP (loopback + an auto-generated bearer token)
mta serve --rest     # plain JSON:  POST http://127.0.0.1:8765/tools/<name>
mta export-schema    # tool schemas as OpenAI / Gemini / OpenAPI 3.1 (no drift)
mta recipes          # copy-paste connection snippets for every client
```

Both HTTP modes are loopback-only by default and require a bearer token. See `mta recipes` for ready-to-paste setup.
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
<summary><b>Use a different (or remote) AI model</b></summary>

By default the optional AI step runs on local **Ollama**. To use another local server (LM Studio, llama.cpp, vLLM, …) set `MTA_BACKEND`:

```bash
MTA_BACKEND=lmstudio mta digest ~/docs          # OpenAI-compatible server on :1234
MTA_BACKEND=openai MTA_BACKEND_URL=http://127.0.0.1:8080/v1 mta digest ~/docs
```

Set `MTA_EXTRACT_MODEL` / `MTA_EMBED_MODEL` to that server's model names. Pointing it at a **non-local** URL sends content off your machine — that's your explicit choice (you'll get a one-time warning).
</details>

<details>
<summary><b>Configuration</b></summary>

Everything has sensible defaults. Common knobs (set as environment variables):

| Variable | Default | Meaning |
| --- | --- | --- |
| `MTA_HOME` | `~/.memorised-them-all` | where memory is stored |
| `MTA_OCR_LANG` | `eng+ben` | OCR languages (Tesseract codes; missing packs dropped automatically) |
| `MTA_EXTRACT_MODEL` | `qwen2.5:7b` | extraction LLM — lighter/multilingual options under "Choosing a model" below |
| `MTA_EMBED_MODEL` | `nomic-embed-text` | embedding model — use `bge-m3` for Bangla/multilingual recall |
| `MTA_VISION_MODEL` | `moondream` | image-caption model |
| `MTA_NO_OLLAMA` | unset | force fully-offline mode (no AI model) |
| `MTA_AUTO_UPDATE` | `on` | daily update check (`off` to disable) |
| `MTA_PROFILE` | unset | tuning preset: `laptop` · `workstation` · `server` · `offline` |
| `MTA_BACKEND` / `MTA_BACKEND_URL` | `auto` | use another local model server (see above) |
| `MTA_HTTP_*` | off | options for the opt-in HTTP/REST servers |

</details>

<details>
<summary><b>Choosing a local model (lighter / multilingual alternatives)</b><a id="choosing-a-model"></a></summary>

Every model is configurable. The defaults are tuned for quality on a ~16 GB machine; the alternatives below are lighter and/or more multilingual (helpful for Bangla). All tags are real Ollama library models — `ollama pull <model>` first, or just set the variable and let the on-demand pull handle it.

**Extraction LLM — `MTA_EXTRACT_MODEL`** (entity/relation/fact extraction + summaries):

| Model | Size | Best for |
| --- | --- | --- |
| `qwen2.5:7b` *(default)* | ~4.7 GB | Best extraction quality + JSON structure |
| `gemma3:4b-it-qat` | 4.0 GB | **Lighter + strongly multilingual** (140+ languages incl. Bangla); quantization-aware-trained ≈ BF16 quality |
| `gemma3n:e2b-it-q4_K_M` | 5.6 GB | On-device-efficient (fast, ~2 B effective compute), multilingual |
| `gemma3:1b-it-qat` | 1.0 GB | Minimal-RAM / fastest; basic extraction |
| `qwen2.5:3b` | ~1.9 GB | Light English-centric alternative |

> Note: there is **no `gemma4` / `gemma4:e2b-it-qat`** on Ollama. Gemma **3n** provides the `e2b-it` ("effective-2B") models; Gemma **3** provides the `*-it-qat` (QAT) models. For Bangla-heavy use, `gemma3:4b-it-qat` is the sweet spot — it stays near full-precision quality at 4 GB while covering 140+ languages.

**Embeddings — `MTA_EMBED_MODEL`** (entity resolution + recall):

| Model | Size | Best for |
| --- | --- | --- |
| `nomic-embed-text` *(default)* | ~0.3 GB | Fast, English-centric |
| `bge-m3` | 1.2 GB | **Bangla / mixed-language recall** (100+ languages, 8 K context) |
| `mxbai-embed-large` | ~0.7 GB | Higher-quality English (1024-dim) |

> Switching the embedding model changes the vector dimension, so **re-digest the project with `reset: true`** after changing it.

**Vision — `MTA_VISION_MODEL`** (captions images OCR can't read):

| Model | Size | Best for |
| --- | --- | --- |
| `moondream` *(default)* | ~1.7 GB | Tiny, fast |
| `llama3.2-vision` | ~7.8 GB | Much stronger; text-in-image / diagrams; multilingual |
| `qwen2.5vl` · `granite3.2-vision` | ~6 GB | Strong document / figure understanding |

Example — a lighter, Bangla-tuned stack (set these in the Claude Desktop extension's settings, or as env vars):

```bash
MTA_EXTRACT_MODEL=gemma3:4b-it-qat MTA_EMBED_MODEL=bge-m3 mta digest ~/docs --reset
```

</details>

<details>
<summary><b>How it works under the hood</b></summary>

`convert` (files → Markdown, locally) → `extract` (entities, relations, facts) → `graph` (build + detect communities/themes) → `summarise` (layered: per-theme + a global synopsis) → `embed` (vectors for search) → `materialise` (memory.md, per-doc notes, mind map). `recall` embeds your question and returns the closest, capped, cited snippets. With no AI model available it falls back to fast classical techniques, so a digest **always** succeeds. See [`CHANGELOG.md`](CHANGELOG.md) and [`SECURITY.md`](SECURITY.md) for details.
</details>

---

## 💻 Platforms

macOS (Apple-silicon optimised), Linux, and Windows · Python 3.10–3.12 · tested on all three in CI.

## 🙏 Credits & license

Built on the shoulders of [MarkItDown](https://github.com/microsoft/markitdown), [Ollama](https://ollama.com), [NetworkX](https://networkx.org), and the [Model Context Protocol](https://modelcontextprotocol.io). Optional community-detection extras (`python-igraph`, `leidenalg`) are GPL-licensed and **not** installed by the MIT core. See [ACKNOWLEDGEMENTS.md](ACKNOWLEDGEMENTS.md).

**MIT licensed** · made by [GRU-953](https://github.com/GRU-953). Issues and contributions welcome — start with [`SECURITY.md`](SECURITY.md) for the security model.

<div align="center">
<sub>100% local · token-free · free &amp; open-source · your files never leave your machine.</sub>
</div>
