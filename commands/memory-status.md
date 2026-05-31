---
description: Check the local stack (Ollama, models, Tesseract, MarkItDown) and projects
---

Report the health of the local Memorised them All stack.

Steps:
1. Call `memory_status`.
2. Summarise for the user: whether Ollama is running and which models are present,
   whether Tesseract/ffmpeg are installed, the MarkItDown version, Apple-silicon tuning
   (performance cores, MLX Whisper), auto-update state, idle timeout, and existing
   projects with their stats.
3. If something needed is missing (e.g. a model not pulled), tell the user the exact
   command to fix it (e.g. `ollama pull qwen2.5:7b`).
