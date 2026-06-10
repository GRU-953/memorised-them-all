# UPGP corpus (`/Users/aninda/UPG Files`) — processing notes (Phase 4)

Survey (10-agent scope workflow, Session 27): 2303 files / 2.4 GB; **1714 content files** after exclusions.

## Skip (config-driven, defaults ON for v2)
- Fonts (`.otf/.ttf/.ttc/...`) — 298 files (incl. the bundled SutonnyMJ/Suttony Bijoy font packs).
- Images (`.jpeg/.jpg/.png/.nef/.eps/.indd`) — ~185, Audio (`.mp3`) — 1, Video — none. (Owner: skip photos/videos/audios.)
- Google-Drive pointer stubs (`.gdoc/.gsheet/.gform/.gdrive`) — **62 files, NO local content** (168-byte JSON holding a Drive doc_id + owner email). Cannot be digested offline. **Owner action if wanted:** re-sync/download the real files from Google Drive, then re-digest. Skipped by default.
- Junk: `.tmp` (6), `.DS_Store` (17), `.ini` (2), `__deltest_2/` test folder.

## Must handle in the digest
- **Archives (6 zip + 4 rar):** unarchive recursively (stdlib zip/tar/gz; rar via `unar`/`7z` — install for the run). One zip is **nested inside `For AOP Data 2023.rar`**; several archives have **already-extracted twin folders** on disk (`New WinRAR archive/`, `Jamalpur/`, `Sherpur/`, `For AOP Data 2023/`); two **byte-identical** copies of `All IDP UPG graduation report-2023 (cohort-2022).zip`. → **content-hash dedup** (sha256 of converted-source bytes) so identical content is digested ONCE, not 2–3×.
- **Legacy binary Office** (117 `.doc`, 22 `.ppt`, 21 `.xls`): MarkItDown may not extract these → pre-convert to OOXML via LibreOffice headless (`soffice --headless --convert-to`) during the corpus run if MarkItDown can't, so they flow through the normal pipeline (incl. Bijoy delegacification).
- **Legacy Bangla (SutonnyMJ / Bijoy family):** confirmed present in **~245 OOXML** (195 docx, 34 pptx, 16 xlsx) + likely some `.doc`. Run Bijoy→Unicode normalization BEFORE conversion (font-aware delegacifier already does this for OOXML; legacy `.doc` handled after LibreOffice→docx).
- **No-extension file** `MEAL and Research/.../Rural data (Missining 1)` is actually an `.xlsx` (PK/zip magic). Content-sniff Office/zip magic in the unknown-type path so it's digested as a spreadsheet. ("(Missining 1)" suggests a sibling source file may be absent — completeness caveat.)

## Memory target
One consolidated project **`UPGP`** in the real `MTA_HOME` (`~/.memorised-them-all`), built with the finalised deterministic v2 engine.

---
## Verification findings — first UPGP build (v2.0.1, Session 27)

Built `upgp` (real `~/.memorised-them-all`, `--reset`): **2192 files** after archive-expand+dedup, **1479 converted ok**, 539 skipped (media/fonts/gdrive/junk), **166 failed** (legacy .doc/.ppt/.xls — LibreOffice still downloading), 3 unsupported, 5 empty. 2370 entities, 14061 relations, 43 communities. ~23 min.

**Quality issues found (refinement backlog — WP-80c):**
1. **Severe undersampling.** `max_chunks` default **1500** truncated **~188,698** chunks (corpus produced 279,072; ~66,716 low-value-skipped). Memory built from only ~1500 chunks. → re-digest with a much higher `MTA_MAX_CHUNKS`, BUT first fix #2 or the cap fills with table noise.
2. **Spreadsheet-cell noise dominates entities.** Top entities are beneficiary-survey cell values — `Male`(962), `No`(961), `Husband`(920), `Rural`(794), `Son`, `NaN` — from the 442 xlsx. They crowd out real programme entities (BRAC=103, DIUPG=178, district names, Annual Progress Report=58, PRA). → extractor/segmentation should down-rank or skip degenerate single-token tabular column values; the low-value-chunk filter should catch survey-grid dumps harder.
3. **Bengali quality is mixed, not broken.** Office docx delegacified cleanly (215 `+bn-unicode`). Bengali **PDFs** (`method: markitdown`) extract as *mostly-readable* Unicode with systematic **vowel-sign reorder errors** ("অনলাইয়ন"→should be "অনলাইন") — a Bengali-PDF text-layer artifact, NOT Bijoy-ASCII (so `maybe_convert` correctly no-ops). A subset (image-heavy maps with a broken embedded font, e.g. "ইৎধহপয খড়পধঃরড়হ") is genuinely garbled → would need Tesseract-Bengali OCR (opt-in) to recover. Optional: a Unicode-Bengali reorder-normalisation pass for PDF text.
4. **166 legacy .doc/.ppt/.xls failed** — pending the slow LibreOffice install; do a `--reset` re-digest (or accumulate) once `soffice` is present so they convert via the v2.0.1 fallback.

**Refinement plan (WP-80c, next iteration):** (a) extractor: skip/down-rank single-token tabular column-value entities (Male/No/Husband/Rural/Son/NaN-class) — product fix + test; (b) raise effective coverage (higher MTA_MAX_CHUNKS, or prioritise narrative chunks over survey grids); (c) LibreOffice top-up for the 166 legacy files; (d) optional Bengali-PDF reorder-normalise / OCR for the broken-font subset; (e) re-digest `--reset` once (a)–(c) land → then agent-fanout verification (once the subagent daily limit resets) until convergence.
