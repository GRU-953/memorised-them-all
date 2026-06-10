---
description: Check the local stack (deterministic engine, Tesseract, MarkItDown) and projects
---

Report the health of the local Memorised them All stack.

Steps:
1. Call `memory_status`.
2. Summarise for the user: the deterministic, model-free engine (no AI models needed),
   whether Tesseract OCR and MarkItDown are installed (and their versions), the platform,
   auto-update state, and existing projects with their stats.
3. If something optional is missing (e.g. Tesseract for OCR, or `unar` for rar archives),
   tell the user the exact command to install it, or run `mta doctor` for guided fixes.
