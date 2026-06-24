# Export format **v1** — neutral, cross-AI knowledge-graph bundle

`mta export <dir>` (and the `export_memory` MCP tool) write a self-contained, vendor-neutral
bundle. It is **deterministic** (byte-identical for identical input) and **offline**. One spec,
consumed by any assistant.

## Bundle contents
| File | Format | Purpose |
|---|---|---|
| `memory.md` | UTF-8 Markdown | Global synopsis + per-theme summaries — the human/LLM-readable memory. |
| `memory/*.md` | UTF-8 Markdown | Per-document notes (one per source), with provenance headers. |
| `graph.json` | JSON (this schema) | The knowledge-graph **sidecar**: entities (nodes), relations (edges), themes (communities), with **stable IDs**. |
| `vectors.npz` / `vectors.json` | binary + JSON | Recall units (optional; for re-loading recall locally). |
| `bm25_index.json` | JSON | Pre-tokenised recall index (optional; regenerated on digest). |
| `graph.graphml` | GraphML (XML) | Deterministic graph export for Gephi / yEd / Cytoscape (since v3.0). |
| `entities.csv` / `relations.csv` | CSV | Deterministic node/edge tables for spreadsheets (since v3.0). |

Bring a bundle back into a project with `mta import <dir>` (or the `import_memory` tool).

## Knowledge-graph sidecar (`graph.json`)
Validated by [`graph.schema.json`](graph.schema.json) (JSON Schema 2020-12). Contract:
- **`nodes[]`** — entities. `id` is a **stable** string (`e0`, `e1`, …); `label`, `type`, `count`,
  and `facts[]` (`{text, doc, heading}` — `doc` is the provenance source name).
- **`edges[]`** — relations referencing node IDs: `{source, target, weight, labels[]}`. Every
  `source`/`target` MUST be an existing node `id` (referential integrity, enforced in CI).
- **`communities[]`** — themes: `{id, label, summary, members[], size}`; `members` are node IDs.
- **`version`** — on-disk schema version; bumped only on an incompatible change. Migrations and
  backward-compat tests ship with the engine; sharpening extraction must not break older bundles.
  **v2 (since v3.0)** adds an optional, additive `documents[].sha256` — a portable per-document
  content hash that powers cross-machine `diff_memory` / `merge_memory`. It is purely additive
  (the v1 schema permits it via `additionalProperties`), so v1 consumers ignore it safely.

## Token budgets & chunking
`memory.md` is bounded (synopsis + ≤ theme summaries). When a target assistant's context is
smaller than the bundle, **chunk** by feeding `graph.json` first (compact, ~structured) then
per-theme/per-document Markdown on demand; `graph.json` itself is the index. Recall
(`mta recall`) already returns only a tiny cited slice, so the common path needs no chunking.

## Per-assistant consumption

"Consumable" here = **schema-conformance + a sample-ingestion fixture passes** (see
`tests/test_export_format.py`); it is **not** a claim of live per-vendor runtime verification.

| Assistant | Best path | Accepted formats | Approx. limits | Auto-configurable? |
|---|---|---|---|---|
| **Claude** (Desktop/Code) | Native MCP — `mta setup` registers the local server; just ask. No export needed. | live tools | tiny (token-free recall) | **Auto** (`mta setup`) — stable CLI/MCP |
| **Gemini** (CLI / API) | MCP via `mta setup` (CLI); or attach `memory.md` + `graph.json` | Markdown, JSON | per Gemini file limits; chunk via graph index | **Auto** (CLI, `mta setup`) / manual (web upload) |
| **ChatGPT** (Codex / app) | Codex: MCP via `mta setup`. App: attach `memory.md` + `graph.json` (remote MCP for connectors) | Markdown, JSON | per ChatGPT upload limits; chunk via graph index | **Auto** (Codex) / **manual** (app upload) |
| **Grok** (Build CLI / app) | Build CLI auto-discovers the `.mcp.json` config; or attach `memory.md` + `graph.json` | Markdown, JSON | per Grok limits; chunk via graph index | **Auto** (Build CLI, via discovery) / manual (app) |

Detailed per-assistant steps: [`docs/assistants/`](../../assistants/). The neutral bundle is the
same for every assistant; only the *import mechanism* differs.

## Versioning
This directory is `v1`. A future incompatible export change adds `docs/export-format/v2/` with its
own schema; the engine keeps reading older on-disk graphs (migrations) so existing bundles remain
valid.
