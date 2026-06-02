---
description: Delete a project's local memory (Memorised them All) — irreversible
argument-hint: [project]
---

Delete a project's local memory using the `forget` tool.

Project: `$ARGUMENTS`

Steps:
1. Confirm which `project` to delete (default is `default`). This is **irreversible** —
   it removes the graph, converted Markdown, vectors, and mind map for that project.
2. Call `forget` with the project name.
3. Report the result (`status`, `project`). If `status` is `not_found`, tell the user
   there was no such project.
