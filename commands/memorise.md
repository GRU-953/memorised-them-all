---
description: Digest files/folders into local, token-free graph memory (Memorised them All)
argument-hint: <path-or-folder-or-glob> [more paths…]
---

Digest the path(s) the user provided into **local, token-free** graph memory using
the **Memorised them All** engine.

Paths: `$ARGUMENTS`

Steps:
1. If no path was given, ask which file or folder to digest (or offer the current directory).
2. Call the `digest` tool with the path(s). It converts every attachment to Markdown
   locally (MarkItDown + Tesseract OCR + Whisper + Ollama vision), builds a knowledge
   graph with community-detected themes, and writes `memory.md`, per-document notes,
   `graph.json`, and an offline `mindmap.html`.
3. The tool returns **only metadata** (counts, paths, stats) — do not try to read the
   converted documents back into the conversation; that would waste tokens.
4. Report a short summary: files converted, entities, relations, themes, and where the
   outputs were written. Offer `/recall`, `/memory-map`, or `/export-memory` as next steps.

Tip: for a large or frequently-refreshed corpus, pass `fast: true` to `digest` — it
skips the local LLM for a deterministic, much faster digest (still builds the graph
and keeps semantic recall).
