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
   locally (MarkItDown, plus optional Tesseract OCR for scanned images), unpacks archives
   safely, then builds a knowledge graph with community-detected themes — fully
   deterministic and model-free (no LLM/Ollama/GPU) — and writes `memory.md`,
   per-document notes, and `graph.json`.
3. The tool returns **only metadata** (counts, paths, stats) — do not try to read the
   converted documents back into the conversation; that would waste tokens.
4. Report a short summary: files converted, entities, relations, themes, and where the
   outputs were written. Offer `/recall` or `/export-memory` as next steps.

Tip: to rebuild a project from scratch (e.g. after upgrading), pass `reset: true` to
`digest`. Otherwise, re-running `digest` on the same folder just updates the memory.
