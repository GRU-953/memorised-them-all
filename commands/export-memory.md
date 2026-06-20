---
description: Export the generated memory as portable Markdown files
argument-hint: <destination-folder>
---

Export the project's memory as portable Markdown files.

Destination: `$ARGUMENTS`

Steps:
1. If no destination was given, ask where to export (default: the current directory).
2. Call `export_memory` with the destination (and `project` if named).
3. It copies `memory.md`, the per-document `memory/` notes, `graph.json`, and the recall
   index (`vectors.npz`/`.json`) to the destination. Confirm what was written.
