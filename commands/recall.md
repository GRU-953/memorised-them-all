---
description: Recall from local graph memory — returns a tiny, citable slice (token-free)
argument-hint: <question>
---

Answer the user's question **from local memory** using the `recall` tool.

Question: `$ARGUMENTS`

Steps:
1. Call `recall` with the question (and `project` if the user named one).
2. It embeds the query locally and returns a **small** relevant slice — theme summaries
   and entity cards with their source documents. It never returns whole documents.
3. Answer the user's question grounded in those hits, citing the source document names
   where provided. If `status` is `no_memory`, suggest running `/memorise` first.
4. If the result has `low_confidence: true` (or no hits clear the relevance floor),
   tell the user the memory doesn't contain a confident answer rather than guessing.
