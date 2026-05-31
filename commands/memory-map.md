---
description: Open the interactive offline knowledge-graph mind map
---

Open the offline interactive mind map for the project's memory.

Steps:
1. Call `open_mindmap` (pass `project` if the user named one).
2. If it returns a path, share it and run the `open_with` command so it opens in the
   browser. The mind map is fully offline (Cytoscape.js inlined — no network).
3. If `status` is `no_memory`, suggest running `/memorise` first.
