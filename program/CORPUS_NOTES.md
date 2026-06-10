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
