---
name: memorise
description: Digest a folder of documents into local, token-free knowledge-graph memory and recall from it. Use when the user wants to "memorise", "digest", "ingest", or "remember" files/attachments/a folder, build a knowledge graph from documents, or ask questions grounded in their own documents without paying tokens to read them. Triggers on "memorise these files", "digest my documents", "build memory from this folder", "remember this PDF", "what do my docs say about X".
---

# Memorise them All

Turn any pile of documents into **local, token-free** graph memory for Claude, and
recall from it cheaply. All conversion and digestion runs on the user's machine
(MarkItDown, plus optional Tesseract OCR) — fully deterministic and model-free, no
LLM/Ollama/GPU. Claude only ever issues a small tool call and gets back compact
metadata or a tiny relevant slice — never whole documents.

## When to use
- The user wants to ingest/digest/memorise files, attachments, or a whole folder.
- The user asks a question that should be answered from their own documents.
- The user wants a knowledge graph of their documents.

## How it works (the pipeline)
1. **Convert** — every attachment → Markdown locally (PDF/Office/HTML via MarkItDown,
   incl. legacy binary `.doc/.ppt/.xls` via optional LibreOffice; scanned images via
   optional Tesseract OCR; archives unpacked safely). Legacy Bengali typed in
   Bijoy/SutonnyMJ ANSI fonts is auto-upgraded to Unicode (font-aware, so mixed
   English+Bengali documents convert cleanly).
2. **Segment → Extract** — structure-aware chunks; rule-based, deterministic extraction
   of entities, relations, and atomic facts (no LLM/model).
3. **Graph + themes** — a knowledge graph with community-detected themes.
4. **Layered memory** — a global synopsis, per-theme summaries, per-document notes,
   and `graph.json`. Recall ranks with model-free BM25 (Bengali-aware) and returns a
   tiny cited slice, declining off-topic queries.

## Tools
- `digest(paths, project?, reset?)` — build/refresh memory (`reset: true` rebuilds from scratch). Returns metadata only.
- `convert(paths, out_dir?, project?)` — convert files/dirs/globs to Markdown locally (legacy Bengali/SutonnyMJ → Unicode); writes `.md` files to `out_dir` (default `markdown_converted/` beside the input). Token-free. Use when the user just wants Markdown, not a digest.
- `recall(query, project?, k?)` — return a small, citable slice of memory.
- `memory_overview(project?)` — synopsis + themes.
- `export_memory(dest, project?)` — export portable Markdown files.
- `list_digestible(directory)` — list convertible files (paths/sizes only).
- `forget(project?)` — delete a project's memory (graph, converted Markdown, summaries/notes). Irreversible.
- `memory_status()` — local stack health.

## Rules
- **Never** read the converted documents back into the conversation — that defeats the
  token-free design. Trust the metadata and recall slices.
- Always cite source document names from recall hits when answering.
- If a project has no memory yet, run `digest` first.
- Use a `project` name to keep separate, reusable memories per body of work.
