# Session Log — "Memorised them All" hardening program

Append-only. One entry per session; never edit past entries. Newest at the bottom. End every entry with the single exact next step.

---

## Session 01 — 2026-06-02 — Bootstrap + Audit + Plan (WP-00 / WP-01 / WP-02)

**Session id:** S01  **Branch:** `develop`  **Mode:** planning only (plan gate active — no implementation)

**Goal:** Stand up the `program/` cross-session state (WP-00); run the Phase-1 deep audit (WP-01); produce the improvement plan, risk register, and acceptance criteria (WP-02). Present severity-ranked gaps + proposed acceptance criteria, then **stop for owner approval**.

**Reality check (verify, don't trust):**
- Repo cloned fresh into the working dir. `gh` authenticated as owner **`GRU-953`** (scopes: repo, workflow, gist, read:org) → push access available.
- Toolchain: git 2.54, gh 2.93, python **3.14.5**, pip 26.1, brew 5.1, node 24.16, npx 11.13. **Missing: Docker, uv.**
- Repo is brand new (created 2026-05-31), at **v1.3.3**, 7 release tags. Side branches `v1.3-gaps` & `copilot/analyze-test-coverage` are **stale snapshots behind main** — no new analysis to fold in.
- External publishing verified directly: **PyPI live** (1.3.3; PyPI set missing 1.0.0 & 1.3.0 vs git tags); **Homebrew tap exists but formula is stale at v1.2.0**; latest GitHub Release carries `.mcpb` + wheel + sdist + install.sh; **CI green on main**.
- Live read-only probe (`memory_status`, running 1.3.3 server): platform detection works (arm64 / 4 P-cores / 16 GB / MLX); Ollama + 3 default models + Tesseract + ffmpeg + MarkItDown 0.1.6 all present; **fast mode ~25× faster** (7 s vs 179–194 s on a 12-file corpus); results are token-free metadata only.
- `pyproject.toml`: version **hardcoded** (not single-sourced); deps **lower-bounded only** (no upper pins/lockfile); sdist ships `launch.py`/`scripts/` (side-branch fix already in main) but the **wheel does not**.
- `release.yml`: publishes only GitHub Release + (conditional) PyPI via **long-lived token**; **no** tap bump, container, MCP-registry, signing, SBOM; **floating action versions**; double-builds artifacts.

**Work done:**
- WP-00: created `program/` (DECISIONS, RISKS, SESSION_LOG, PROGRESS); branching model = ADR-001; created `develop`.
- WP-01: ran 9-dimension parallel fresh-eyes audit workflow (run `wf_46e5814a-631`; 903K agent-tokens, 267 tool calls) → synthesized `AUDIT.md` (110 findings: **2 Critical, 12 High, 28 Med, 24 Low, 44 Info**; 49 IMPLEMENTED confirmations; 35 quick wins). Criticals: PKG-03 (offline first-run broken) + LIFE-01 (no cross-process lock). Fixed a corrupted MCP summary field from the subagent.
- WP-02: wrote `IMPROVEMENT_PLAN.md` (v1 critical path WP-03 → WP-10/13 → WP-14 → WP-15, plus WP-11/12/30/31/32/40/41/50-52/90; v1.x+ backlog for Phase-3 interop + roadmap), `ACCEPTANCE.md` (A1–A12, CI-gated; A2/A4/A5/A7/A8/A9 currently FAIL), expanded `RISKS.md` (R-08…R-12).

**Decisions:** DECISIONS.md ADR-001..008. Plan-gate choices recorded (owner, S01): offline-first auto-update (Q1), stdlib-first deps (Q2), full release hardening incl. OIDC + tap automation (Q3), full gitflow + push authorized (Q4); encryption-at-rest opt-in by default (assumption, ADR-008). `develop` pushed to origin.
**Blockers:** Docker not installed (Phase-6 container matrix, R-01); WP-40 needs owner to configure PyPI Trusted Publisher + cross-repo tap token (ADR-006). **Explicit plan/acceptance approval still required before executing implementation WPs.**
**Test/CI:** main green (not re-run locally this session).

**EXACT NEXT STEP:** Await owner approval at the **plan gate** (4 open questions: Q1 auto-update default direction, Q2 new-dependency policy, Q3 release credentials/OIDC + tap automation, Q4 push authorization + encryption default). **On approval**, claim **WP-03** on branch `wp-03-ci-fidelity`: make CI install full runtime deps and run a real offline convert→digest→recall, fix `test_ocr_stdin_pipe` (guard PIL), assert all 8 tools (`mcp_stdio_check`), and single-source the version (`mta/__init__.py` via hatch `dynamic` + `scripts/check_versions.py` CI gate + bump `CITATION.cff`). Then WP-10/WP-13 (offline-correct bootstrap + integrity-verified auto-update). **Do NOT start implementation before approval.**

---

## Session 02 — 2026-06-02 — Implementation: WP-03 (CI fidelity + version single-source)

**Session id:** S02  **Branch:** `wp-03-ci-fidelity` → **PR #5** into `develop`  **Mode:** implementation (plan approved)

**Goal:** Close WP-03 — make CI honest, single-source the version, harden the MCP boundary.

**Done (all six exit criteria + quick wins):**
- (a) CI **conversion-e2e** lane: full deps + Tesseract; converts real pdf/docx/xlsx/csv/html (committed `tests/fixtures/` + `tests/test_conversion_e2e.py`). [CI-10]
- (b) `test_ocr_stdin_pipe` skips cleanly without Pillow. [DOC-02]
- (c) `mcp_stdio_check` asserts all 8 tools incl. `forget`. [DOC-03/MCP-08]
- (d) Single version source: `mta/__init__.py` canonical + hatch `dynamic`; `scripts/check_versions.py` CI gate + tag==version in `release.yml`; `CITATION.cff` 1.3.2→1.3.3; marketplace dual-pin removed. [PKG-01/02, CI-07/08, PKG-05]
- (e) `.mcpb` build + content smoke in CI (mcpb packer validates the manifest). [CI-12]
- (f) `digest`/`recall`/`export_memory` input validation → structured error. [MCP-07]
- Also: `.mcp.json` `MTA_WORKERS` parity (PKG-09); CI now runs on `develop` + its PRs.

**Local verification:** 31 tests pass (offline + real-conversion); stdio→8 tools; isolated build (hatchling<1.27)→1.3.3 wheel+sdist, `twine check` PASSED; `build_mcpb.sh` real packer → 50-file validated bundle; `check_versions.py` green.

**Deferred within WP-03 (Low, follow-up):** PIPE-04 (`stats.mode` label when no LLM ran), DOC-21 (command `.md` signatures), PKG-06 (manifest `$schema`).

**Test/CI:** ✅ **CI fully green** — run 26781819576 (6-cell matrix + `build`/`.mcpb`-smoke + `version-check` + `conversion-e2e`). The *first* run (26781633221) caught a real workflow bug: the conversion-e2e lane installed core deps only, so `pytest` was missing (exit 127 `command not found`) — fixed by installing `.[dev]`. PR #5 squash-merged to `develop` (`4548d02`); `wp-03-ci-fidelity` deleted.

**EXACT NEXT STEP:** WP-03 DONE + merged (`4548d02`). Begin **WP-10 + WP-13** together (theme A, ADR-004) on a fresh branch off `develop`: make a first-run digest fully offline (default PyPI-pinned MarkItDown; integrity-verified opt-in for the git-upstream pull) — closes **Critical PKG-03** + SEC-04 + DEP-01; target acceptance **A2** (offline first-run) + **A8** (integrity).

---

## Session 03 — 2026-06-02 — Implementation: WP-10 + WP-13 (offline-first install + safe auto-update)

**Session id:** S03  **Branch:** `wp-10-offline-install` → **PR #6** (merged, squash `fd2d1d2`)  **Mode:** implementation

**Goal:** Close the Critical **PKG-03** and the auto-update gaps (SEC-04, DEP-01, DEP-03, DEP-09) — theme A.

**Done:**
- **Offline-first (PKG-03):** removed the unconditional `git+https` MarkItDown pull from the install hot path (`install.sh`, `scripts/mta-launcher.sh`); the pinned PyPI build (in `requirements.txt`) is the offline-correct default. A first-ever digest no longer needs network beyond the one-time pip install.
- **Opt-in pinned upstream (SEC-04):** `MTA_MARKITDOWN_UPSTREAM=on` / `MTA_AUTO_UPDATE=upstream` pulls upstream MarkItDown **pinned to a resolved commit SHA**; unresolvable → PyPI fallback (never an unpinned moving branch). New `config.markitdown_upstream`.
- **Safe updates (DEP-01/03/09):** `updater.py` rewritten — import-smoke after upgrade + **rollback** to the prior version on failure; **atomic** throttle stamp; richer `run_check` result. PyPI installs are pip hash-verified.
- Docs corrected (README feature bullet + config table — no longer claims "pulls latest upstream" by default); CHANGELOG.
- Tests: `tests/test_updater.py` (8 tests). **39 tests pass** locally; CI run 26796840053 fully green (all 9 jobs); `bash -n` clean.

**Decisions:** ADR-009 — self-update (DEP-02) stays **report-only** for v1 (Desktop/Code host `.mcpb`/plugin updates; pip users get a notice).
**Deferred:** "no-update-during-digest" coordination → WP-14 (needs the lock); PKG-04 (`.mcpb` zip-fallback parity, Low); PIPE-04, DOC-21, PKG-06 (Low quick-wins).
**Risks:** R-08 → **Mitigated**.

**EXACT NEXT STEP:** Begin **WP-14 — lifecycle + cross-process concurrency** (closes **Critical LIFE-01**) on a fresh branch off `develop`: add cross-process single-writer/multi-reader locking (stdlib `fcntl`/`msvcrt`, or `filelock` per ADR-005) around a project's graph/vectors/markdown writes in `mta/core/store.py` / `digest.py` / `lifecycle.py`; fix the idle-watchdog cross-process coupling (LIFE-02) and the Ollama-installed-but-unreachable fast-fail (PIPE-03); fold in the deferred updater↔digest coordination. Target acceptance A5 (4-way concurrent digest → no corruption) + A6 (idle stop within tolerance; user's Ollama untouched).

---

## Session 04 — 2026-06-02 — Implementation: WP-14 (cross-process concurrency + lifecycle)

**Session id:** S04  **Branch:** `wp-14-concurrency-lifecycle` → **PR #7** (merged, squash `a5851ab`)  **Mode:** implementation

**Goal:** Close the remaining **Critical LIFE-01** (no cross-process locking) + PIPE-03 + DEP-08; improve LIFE-02.

**Done:**
- **New `mta/core/locks.py`** — single-writer/multi-reader project locking (`flock` POSIX / `msvcrt` Windows); lockfiles under `state/locks/` so `forget`/reset can't delete a held lock; `flock` auto-releases on process death (no stale locks). **Exclusive** around `digest` (`_digest_locked`), `reset`, `delete_project`; **shared** around `recall`/`overview` → no torn `graph.json`↔`vectors.npz` pair, no interleaved digests (LIFE-01).
- **lifecycle:** cross-process `ollama-start` lock (no double-spawn; A5/DEP-08) with re-check inside; **PIPE-03** 60 s cooldown after a failed start (no repeated ~20 s stalls when Ollama is installed-but-unreachable).
- **tests/test_concurrency.py (7)** — lock exclusion/sharing/exclusion, lock-outside-project-dir, **4-way concurrent digest → consistent pair, no temp left (A5)**, `forget` serialisation, PIPE-03 cooldown. CI matrix now runs them on all 3 OSes (fcntl + msvcrt).
- CHANGELOG.

**Local:** 44 passed, 1 skipped. CI run 26803940371 fully green (all 9 jobs, incl. both Windows cells).
**Risks:** R-09 → **Mitigated**.
**Deferred:** LIFE-02 residual — a narrow "owner process exits mid-use of a *shared* Ollama" race (the cross-process activity marker + start-lock cover the common cases; full refcounted ownership deferred). Plus PIPE-04, DOC-21, PKG-06, PKG-04 (Low).

**🎉 Milestone:** **both Criticals (PKG-03, LIFE-01) are now closed.** Phase-2 R4 (WP-13) + R5 (WP-14) done.

**EXACT NEXT STEP:** Begin **WP-15 — compatibility, versioning & data migration (R6)** on a fresh branch off `develop`: in `mta/core/store.py`, when a store's `version` ≠ `SCHEMA_VERSION`, **back it up and migrate** (forward-migrate older stores; keep them at least read-recallable) instead of returning None for a newer store; add a migration registry + tests with vN-1 fixtures; document SemVer + deprecation policy. Target acceptance **A7**.

---

## Session 05 — 2026-06-02 — Implementation: WP-15 (R6 schema versioning & migration)

**Session id:** S05  **Branch:** `wp-15-schema-migration` → **PR #8** (merged, squash `90cfffd`)  **Mode:** implementation

**Goal:** Close **LIFE-03** — versioned store with migration + backup so old memories stay read-recallable and a downgrade can't lose data.

**Done (`mta/core/store.py`):**
- `load_graph`: a **newer-than-supported** store is no longer returned as `None` (which surfaced as "no memory" and let a digest overwrite it) — returned best-effort so recall/overview still work. **Older** stores **forward-migrate in memory** via a `_MIGRATIONS` registry (pure → safe under the shared read lock). Corrupt/non-numeric version still → `None`.
- `save_graph`: **backs up** an incompatible (newer) on-disk store under `projects/<name>/backups/<ts>-…/` before overwriting → a version downgrade can't silently destroy memory.
- `tests/test_migration.py` (6) — run on all 3 OSes in the matrix. README versioning/migration note; CHANGELOG.

**Local:** offline suites green (smoke + concurrency + migration). CI run 26806762333 fully green (9 jobs).
**Risks:** R-12 → **Mitigated**. **Acceptance A7 → met.**

**Milestone:** Phase-2 **R4 (WP-13) + R5 (WP-14) + R6 (WP-15)** complete; both Criticals closed. Phase-2 remaining: **R2 (WP-11), R3 (WP-12)**; R1 (WP-10) done.

**EXACT NEXT STEP:** Begin **WP-11 — auto-configuration (R2)** on a fresh branch off `develop`: in `mta/core/config.py` + `platform.py` + `server.py`, add **named profiles** (laptop/workstation/server/offline via `MTA_PROFILE`), **persist** the resolved config to `state/config.json` (and reload it), and **detect + surface GPU/CUDA + LM Studio** in `memory_status` / `platform.summary()`. Tests for profile resolution + persistence + detection. (Closes DEP-05/06/07.)

---

## Session 06 — 2026-06-02 — Implementation: WP-11 (auto-configuration, R2)

**Session id:** S06  **Branch:** `wp-11-auto-config` → **PR #9** (merged, squash `81bf1c0`)  **Mode:** implementation

**Goal:** Close DEP-05/06/07 — named profiles, persisted resolved config, GPU/LM-Studio detection.

**Done:**
- **config.py:** `PROFILES` (laptop/workstation/server/offline) seeded as `MTA_*` defaults with **env > profile > built-in** precedence; seeded keys are captured into the resolved `Config` then removed (no process-env leak). New `no_ollama` + `profile_name` fields. `persist_config()` writes resolved knobs to `state/config.json` (atomic).
- **platform.py:** `detect_gpu()` (mlx/cuda/rocm/none, cached) + `lm_studio_running()` probe; both in `summary()`.
- **lifecycle.py:** `_disabled()` consults `cfg.no_ollama` (offline profile truly disables Ollama) + the env var. (grep confirms lifecycle is the only runtime `MTA_NO_OLLAMA` reader.)
- **server.py:** `memory_status` / `mta status` report `profile`, `gpu`, `lm_studio`, `config_file`.
- `tests/test_autoconfig.py` (7) on all 3 OSes; README `MTA_PROFILE` row; CHANGELOG (Added).

**Local:** 48 offline tests pass. CI run 26808085813 fully green (9 jobs).

**Milestone:** Phase-2 **R1, R2, R4, R5, R6 done** — only **R3 (WP-12)** remains to complete Phase 2.

**EXACT NEXT STEP:** Begin **WP-12 — dependency scan + guided install/upgrade + `mta doctor` (R3)** on a fresh branch off `develop`: add a preflight scanner reporting present-&-current / outdated / missing with **detected-vs-required versions** (Python deps via `importlib.metadata` vs the pyproject requirements; system bins ollama/tesseract/ffmpeg via PATH + `--version`); a guided, **argv-only, idempotent** install/upgrade per platform (pip; brew/apt/dnf/pacman; winget/choco/scoop) with **`--dry-run`** + graceful no-admin remediation; surface via a new **`mta doctor`** subcommand + `memory_status`. Tests with monkeypatched probes (detected-vs-required, dry-run). (Closes DEP-04/10; completes Phase 2.)

---

## Session 07 — 2026-06-02 — Implementation: WP-12 (dep-scan + `mta doctor`, R3) — Phase 2 complete

**Session id:** S07  **Branch:** `wp-12-doctor` → **PR #10** (merged, squash `66ca5d6`)  **Mode:** implementation

**Goal:** Close DEP-04/10 — dependency preflight scanner + `mta doctor` — completing Phase 2 (R1–R6).

**Done:**
- **`mta/core/deps.py`:** `scan()` reports Python deps **detected-vs-required** (parsed from the package's `Requires-Dist` via `importlib.metadata` — single-sourced; extras skipped) + ollama/tesseract/ffmpeg binaries (present/version). `remediation()` builds argv-only, idempotent commands per platform (pip; brew/apt/dnf/pacman/winget). `doctor(fix, dry_run)`: `--fix` runs ONLY the safe pip upgrades; system-tool installs are *suggested*, never auto-sudo; `--dry-run` previews.
- **cli.py:** new `mta doctor [--fix] [--dry-run]`. **server.py:** `memory_status` reports a `dependencies` summary.
- `tests/test_doctor.py` (6) on all 3 OSes; README CLI + CHANGELOG (Added). `mta doctor --dry-run` smoke verified.

**Local:** 54 offline tests pass. CI run 26809008286 fully green (9 jobs).

**🎉 Milestone: Phase 2 (R1–R6) COMPLETE.** All core requirements implemented; both Criticals + the R4/R5/R6 Highs closed.

**EXACT NEXT STEP:** Begin **WP-30 — offline recall reliability + classical-extraction quality** on a fresh branch off `develop`. Closes **DOC-01 (High)**: in `mta/core/recall.py`, compute a calibrated **lexical-overlap confidence** + apply a (scaled) floor on the **hashing/offline** path so `low_confidence`/`MTA_RECALL_MIN_SCORE` work without Ollama (today `low_confidence` is hardcoded `False` offline); fix `top_score` to reflect the returned hits (RECALL-03); address the verbatim-classical-fact nuance (RECALL-02). Tests: an off-topic query offline → `low_confidence True`. Target acceptance **A4**.

---

## Session 08 — 2026-06-02 — Implementation: WP-30 (offline recall reliability, DOC-01)

**Session id:** S08  **Branch:** `wp-30-offline-recall` → **PR #11** (merged, squash `84e8c6c`)  **Mode:** implementation

**Goal:** Close **DOC-01 (High)** — `low_confidence`/`MTA_RECALL_MIN_SCORE` work on the offline/hashing path + fix `top_score` (RECALL-03).

**Done (`mta/core/recall.py`):**
- The `MTA_RECALL_MIN_SCORE` floor is applied on **both** embedding paths (was real-embeddings-only → silently ignored offline).
- `low_confidence`: real embeddings keep cosine<0.5; the hashing/offline path now uses **lexical overlap** between the query and the top hit (`_lexical_overlap`) — an off-topic query with no shared content words is flagged low-confidence with **no model at all**.
- `top_score` reflects the **returned** hits (0.0 when the floor empties them); added `raw_top_score` (pre-floor best) — RECALL-03.
- `tests/test_recall_offline.py` (4) on all 3 OSes; CHANGELOG.

**Local:** 58 offline tests pass. CI run 26810293268 fully green (9 jobs).
**Risks:** R-10 → **Mitigated**. **Acceptance A4 → met.**

**Status:** No Critical/High remains except **SEC-01** (WP-32) and release-train **CI-02/05** (WP-40).
**Deferred (Med):** RECALL-02 (verbatim-fact nuance — bounded by the 600-char cap), PIPE-05 (rapidfuzz hard-dep), PIPE-06 (classical-extractor quality).

**EXACT NEXT STEP:** Begin **WP-32 — security hardening completion + `SECURITY.md`** on a fresh branch off `develop`: extend the decompression-bomb/size cap in `mta/core/convert.py` to ALL ZIP-container formats (.docx/.xlsx/.pptx/.epub — SEC-01); delimit attacker-influenced text in the summary/synopsis prompts in `digest.py` (SEC-02); set `allow_pickle=False` explicitly on the `np.load` in `store.py` (SEC-03/DOC-04/LIFE-05); remove the unpkg CDN fallback in `templates/mindmap.html.j2`/`render.py` (SEC-10 → literally zero-network); note GPL optional libs (SEC-11); write `SECURITY.md` + threat model. Tests: bomb cap rejects an oversized .docx; allow_pickle explicit; mindmap has no external URL. Target acceptance **A12**.

---

## Session 09 — 2026-06-02 — Implementation: WP-32 (security hardening + SECURITY.md)

**Session id:** S09  **Branch:** `wp-32-security` → **PR #12** (merged, squash `6c52714`)  **Mode:** implementation

**Goal:** Close **SEC-01 (High)** + SEC-02/03/10/11; write `SECURITY.md` + threat model (A12).

**Done:**
- **SEC-01:** the decompression-bomb/size bounds check runs for **all** MarkItDown inputs, not just `.zip` — so `.docx`/`.xlsx`/`.pptx`/`.epub` bombs are rejected (`convert.py`; `_zip_within_bounds` already no-ops on non-zip inputs).
- **SEC-02:** the theme + synopsis summariser prompts fence document-derived text as data (`<<<DATA>>>…<<<END>>>`), matching the per-chunk extractor (`digest.py`).
- **SEC-03:** `np.load(..., allow_pickle=False)` made explicit on the vector store (`store.py`).
- **SEC-10:** removed the mind map's unpkg CDN fallback → zero network; missing asset → static offline notice (`render.py`).
- **SEC-11:** documented the GPL `graph` extra (`pyproject.toml`).
- Added **`SECURITY.md`** (reporting + threat model). `tests/test_security.py` (5) on all 3 OSes; CHANGELOG (Security).

**Local:** 62 offline tests pass. CI run 26814539065 fully green (9 jobs). **Acceptance A12 → mostly met** (CI license/vuln scan deferred to WP-40).

**Status:** the only open High findings are the release-train ones (**CI-02/05 → WP-40**).

**EXACT NEXT STEP:** Begin **WP-31 — eval harness + reference corpus + golden metrics** on a fresh branch off `develop`: add `eval/` with a small committed multi-format corpus + golden expected metrics (conversion fidelity, retrieval precision/recall, fast-vs-accurate speedup, cold-start + peak/idle memory); a `make eval`/script that reports + CI-gates thresholds; replace the unbenchmarked "20–100×"/"163 languages" claims (DOC-18/19) with measured numbers. Target acceptance **A10/A11**.

---

## Session 10 — 2026-06-02 — Implementation: WP-31 (eval harness + golden metrics)

**Session id:** S10  **Branch:** `wp-31-eval` → **PR #13** (merged, squash `24aef47`)  **Mode:** implementation

**Done:**
- **`eval/`** — committed reference corpus (4 synthetic Markdown docs; no copyrighted material) + `golden.json` (8 queries, expected entities) + `run_eval.py`. Digests offline (hashing + classical), scores **recall@k**, reports per-stage timing.
- **CI gate** — `tests/test_eval.py` (all 3 OSes) fails if `recall@8 < 0.75` (measured **baseline 1.0**; floor set below baseline = regression gate).
- **DOC-18/19** — replaced "20–100×" with "≈10–30× on a typical 7B setup; scales with corpus size" and "163 languages" with "100+ via Tesseract packs" across README features/config/FAQ + a Quality-section note on the eval harness.

**Local:** 64 offline tests pass; `python eval/run_eval.py` exits 0. CI run 26816096593 fully green (9 jobs). **Acceptance:** A10 partially met (offline recall gated; accurate P/R + conversion fidelity → Phase-6); A11 timing reported.

**Status:** every Phase-1 Critical/High is closed/mitigated **except the release-train ones (CI-02/05)** → WP-40.

**EXACT NEXT STEP:** Begin **WP-40 — release train + supply-chain hardening** on a fresh branch off `develop`. Rewrite `.github/workflows/release.yml`: **one** build job → publish to all targets; **OIDC** trusted publishing to PyPI (`pypa/gh-action-pypi-publish`, `permissions: id-token: write`); **SHA-pin** every action; **SBOM** (e.g. anchore/syft) + **cosign keyless** signatures per artifact; idempotent + **halt-on-partial** (no partial releases); **auto-bump the Homebrew tap** (job gated on a `HOMEBREW_TAP_TOKEN` secret); commit a lockfile; keep the tag==version gate. Write `program/PUBLISH_MANIFEST.md` (channel → secret names → verification) + a release checklist. Degrade gracefully when a publisher/secret is absent. **Owner-action items (ADR-006) are required only for WP-41 (the actual publish).**

---

## Session 11 — 2026-06-02 — Implementation: WP-40 (hardened release train + supply chain)

**Session id:** S11  **Branch:** `wp-40-release-train` → **PR #14** (merged, squash `abca304`)  **Mode:** implementation

**Done:**
- Rewrote `.github/workflows/release.yml`: **one** build job (wheel + sdist + `.mcpb` + SBOM, signed) → `pypi` (**OIDC Trusted Publishing**, no token) → `github_release` → `homebrew` (auto-bump the tap, gated on `HOMEBREW_TAP_TOKEN`). **Every Action SHA-pinned**; **CycloneDX SBOM** (anchore/sbom-action) + **cosign keyless** `.sig`/`.pem` per artifact; PyPI first ⇒ a failure halts before a partial release; `skip-existing` ⇒ idempotent; tag==version gate; least-privilege per-job perms; concurrency guard.
- SHA-pinned all `ci.yml` actions too (resolved each tag→commit via `gh api`).
- Added `program/PUBLISH_MANIFEST.md` (channels → auth → verify; owner setup; release checklist).

**Local:** both workflows YAML-valid; **no floating action tags** remain. CI run 26816551772 fully green (9 jobs) — so the **SHA-pinned `ci.yml` is validated on all 3 OSes**. `release.yml` is tag-only ⇒ structure-validated here, live at WP-41.

**Closes:** CI-02/03/04/05/06/11, SEC-06/07. **R-02/R-03 mitigated.** Deferred: CI-09 (reproducible lockfile).

**🎉 Status: every Phase-1 Critical/High is now closed or mitigated.**

**EXACT NEXT STEP (⛔ OWNER-GATED): WP-41 — first synchronized release.** Do NOT tag a live release until the owner has (1) configured the **PyPI Trusted Publisher** (repo `GRU-953/memorised-them-all`, workflow `release.yml`) and (2) added the **`HOMEBREW_TAP_TOKEN`** repo secret. Then: PR `develop`→`main`, merge, move CHANGELOG *Unreleased*→the version, `git tag vX.Y.Z && git push --tags`, watch `build→pypi→github_release→homebrew`, run the post-publish smoke in `PUBLISH_MANIFEST.md`. **In parallel, WP-50-52 (Phase-6 sandbox E2E) can start once Docker is available (R-01), or run in CI.**

---

## Session 12 — 2026-06-02 — Implementation: WP-33 (quick-win sweep)

**Session id:** S12  **Branch:** `wp-33-quickwins` → **PR #15** (merged, squash `d511a0d`)  **Mode:** implementation (owner chose the autonomous sweep)

**Done:**
- **PIPE-04** — `digest` stats report `mode: "classical"` when no LLM ran (offline / Ollama unavailable), instead of mislabelling `"accurate"`; asserted in the offline e2e test.
- **DOC-21** — `/memorise` documents `fast`; new **`/forget`** command (`commands/forget.md`); `SKILL.md` tool list now includes `forget` + `fast`.
- **PKG-04** — `.mcpbignore` excludes dev/internal dirs (`program/`, `eval/`, `scripts/`, `commands/`, `skills/`, `.mcp.json`, `launch.py`, …); the zip fallback packs "everything minus `.mcpbignore`" to match `mcpb pack`. Verified: `.mcpb` is 310 KB / 32 entries, `manifest.json`+`launch.sh`+`mta/` present, all dev dirs excluded.

**Resolved by not forcing:** PKG-06 **N/A** (MCPB has no canonical hosted `$schema` URL — verified upstream); CI-09 **deferred** (a `--generate-hashes` lock = 81 pkgs with pip-install warnings → a clean reproducible lock is a deliberate v1.x+ task); RECALL-02 + LIFE-02-residual **accepted-as-noted** (bounded 600-char cap; narrow atexit race) — no code change.

**Local:** 64 offline tests pass. CI run 26817270903 fully green (9 jobs).

**EXACT NEXT STEP:** All autonomous build work is complete. The remaining v1 items are gated/large: **WP-41** (first live release — needs owner PyPI Trusted Publisher + `HOMEBREW_TAP_TOKEN`, then PR develop→main + tag); **WP-50-52** (Phase-6 E2E — needs Docker (R-01) or a CI container matrix → `TEST_REPORT.md`); **WP-90** (fresh-eyes convergence review). Pick up whichever the owner unblocks first.

---

## Session 13 — 2026-06-02 — Pre-release fresh-eyes review + fixes (WP-34)

**Session id:** S13  **Branch:** `wp-34-review-fixes` → **PR #16** (merged, squash `a46a414`)  **Mode:** independent review (Section 5) + fixes

**Did:** Ran a 4-reviewer adversarial workflow (`wf_9100244e-45f`) over all `develop` deltas vs acceptance + invariants → **21 findings (3 High, 5 Med, 8 Low, 5 Info)**. Reviewers confirmed the lock design, migration safety, offline-first, token-free caps, SEC-01, and release ordering are sound. Fixed in WP-34:
- **H** torn vector store → `load_vectors` length guard + recall index clamp (degrades to `no_memory`, no IndexError).
- **H** `config.load()` profile race → `_LOAD_LOCK` serialises the env seed/restore (no `no_ollama` leak under concurrency).
- **H** DOC-01 hole → `_lexical` fallback returns the full `low_confidence`/`top_score`/`synopsis` contract.
- **M** synopsis capped (recall+overview); updater rollback re-verified + `pip-update` cross-process lock; release `.mcpb` content-verified.
- **L** `list_digestible` TOCTOU guard; lock degraded-mode warning; `.mcpb` nested `__pycache__` excluded.
- Disposition + deferrals recorded in **`program/REVIEW.md`**.

`tests/test_review_fixes.py` (8) on 3 OSes; updated the WP-13 rollback test to re-verify semantics. **Local: 79 passed, 1 skipped. CI run 26818417542 fully green.**

**🎉 ALL autonomous build + review work is COMPLETE.** No Critical/High open; the design is independently validated. `develop` = 25 commits ahead of `main`, all CI-green.

**EXACT NEXT STEP (owner-gated / Docker):** The program is paused for owner action. (1) **WP-41** — set up the PyPI Trusted Publisher + `HOMEBREW_TAP_TOKEN`, then PR `develop`→`main` + tag to ship v1. (2) **WP-50-52** — Phase-6 E2E (local Docker, R-01, or a CI container matrix) → `TEST_REPORT.md`. (3) **WP-90** — write the convergence note once both land. A fresh session resumes from this RESUME-HERE pointer.

---

## Session 14 — 2026-06-02 — Phase-6 E2E (WP-50-52) + release-prep (WP-41) + convergence (WP-90) — UNATTENDED

**Session id:** S14  **Mode:** unattended (owner authorised proceeding without confirmation)

**Done:**
- **WP-50-52 (Phase-6 E2E):** `tests/test_e2e_cli.py` drives the clean-wheel-installed `mta` CLI end-to-end; `.github/workflows/e2e.yml` gates it on the release PR. Local run (clean wheel + live Ollama): offline **5/5 pass**; **accurate-mode pass (142 s)**; measured fast-vs-accurate **≈98×** (5 files) / ≈26× (12 files). Merged via **PR #17**. `program/TEST_REPORT.md`. README fast-mode claim corrected to the **benchmarked ≈25–100×** (WP-31 had under-sold it).
- **WP-41 (release-prep):** bumped to **1.4.0** (all 5 version strings; `check_versions` green), cut CHANGELOG `[Unreleased]→[1.4.0]`. Opened the **`develop`→`main` release PR** (full CI + the `e2e.yml` Phase-6 gate).
- **WP-90 (convergence):** `program/CONVERGENCE.md` — **converged for the code scope** (no Crit/High; acceptance green in CI + Phase-6; last review only marginal/declined items).

**Acceptance:** A10/A11 now MET (Phase-6 measured); A8 mostly-met (the live publish is owner-gated).

**🏁 v1 hardening COMPLETE & CONVERGED (code).** 14 WPs, PRs #5–#17, all CI-green on the 3-OS matrix; `develop` = v1.4.0.

**EXACT NEXT STEP (owner-only — to PUBLISH):** merge the `develop`→`main` PR (ready/green), configure the PyPI **Trusted Publisher** + add `HOMEBREW_TAP_TOKEN` (`PUBLISH_MANIFEST.md`), then `git tag v1.4.0 && git push --tags` → the train ships PyPI + GitHub Release (+`.mcpb`) + bumps the tap. The agent cannot configure PyPI (no account access). v1.x+ backlog: Phase-3 interop (WP-20–24) + extra channels + deferred Low/Med.

---

## Session 15 — 2026-06-02 — 🚢 v1.4.0 RELEASED (WP-41 complete)

**Mode:** unattended. Owner completed the two gated actions (PyPI Trusted Publisher + `HOMEBREW_TAP_TOKEN` secret).

**Done:** Verified the secret is set + `main` at v1.4.0 (CI green); tagged **`v1.4.0`** on `d5ff2d9` and pushed → **Release run 26835623380, all 4 jobs green** (`build → pypi → github_release → homebrew`). **Post-publish smoke ✓:**
- **PyPI** — `latest 1.4.0`; fresh-venv `pip install memorised-them-all==1.4.0` imports, reports 1.4.0.
- **GitHub Release `v1.4.0`** — wheel + sdist + `.mcpb` + `sbom.cyclonedx.json` + a cosign `.sig`/`.pem` for every artifact.
- **Homebrew tap** — `Formula/mta.rb` auto-bumped: `url …/v1.4.0.tar.gz`, new `sha256`, `version "1.4.0"`. (R-02 **Resolved**.)

**🎉 v1 PROGRAM OBJECTIVE COMPLETE** — audit → 14 WPs → independent review → Phase-6 E2E → signed, SBOM'd, multi-channel v1.4.0 release. No Critical/High open.

**⚠ Action for the owner:** **rotate `HOMEBREW_TAP_TOKEN`** — a fine-grained PAT was pasted in chat (compromised); replace the secret with a fresh token before the next release.

**EXACT NEXT STEP:** None required for v1. When desired, start the **v1.x+ backlog** (Phase-3 cross-AI interop WP-20–24; extra publishing channels; deferred Low/Med per `REVIEW.md`) — a fresh session resumes from PROGRESS ▶ RESUME HERE.

---

## Session 16 — 2026-06-03 — v1.x+ Phase-3 interop begins (WP-20 + WP-21); concurrency incident

**Mode:** unattended ("Resume & Continue"). Began the v1.x+ backlog (post-ship by ADR-002), starting Phase-3 cross-AI interop.

**⚠ Concurrency incident (resolved).** Partway into starting WP-21, a **second unattended session** was found writing **WP-20** (HTTP transport) into *this same checkout* — same working tree + git HEAD. Detected via the reflog (`develop → wp-20-http-transport → wp-21-schema-exports`, no commits) and a live `git status` delta (transport.py/test_transport.py/server.py/… appearing mid-turn). Halted all mutations (a shared HEAD makes any git op a race), backed WP-21 up outside git, and surfaced it to the user, who chose **"I drive solo."** A background watcher confirmed the other session went quiet (~72 s stable), then I consolidated as sole driver — no work lost on either side. **Lesson recorded in PROGRESS:** run ONE unattended session per working tree, or isolate with `git worktree`.

**WP-20 — secure Streamable HTTP transport (merged #19, `9e1029a`).** Preserved the concurrent session's work onto `wp-20-http-transport` (explicit paths, never `git add -A`), reviewed it (loopback-only default + non-loopback refusal; mandatory bearer w/ constant-time compare in a pure-ASGI gate; SDK DNS-rebind protection; atomic `0600` token; **no new top-level dep** — starlette/uvicorn ship with mcp, verified), ran it green locally (84 passed; 8-tool stdio check intact after the `build_server()` refactor), PR → full 3-OS CI green → squash-merged. Adds `mta serve --http`, `server.build_server()`, `client_config()` (WP-24 seam).

**WP-21 — cross-AI schema exports (merged #20, `fa86ec3`).** Rebuilt cleanly on top of merged develop. `mta export-schema [--format openai|gemini|openapi|all] [--out DIR]` → new `mta/interop/schemas.py`, **derived from the live FastMCP registry** (a test asserts names/descriptions == the server, so no drift). Gemini normalised to its OpenAPI-3.0 subset (nullable `anyOf` collapsed, JSON-Schema-only keys stripped, no-arg tools omit `parameters`); OpenAPI **3.1** doc (`POST /tools/{name}`) seeds WP-22. Pure/offline/token-free; dispatched before any config load. 10 tests in the offline lane; full lane **94 passed, 1 skipped**; PR → 3-OS CI green → squash-merged.

**State:** `main` = v1.4.0; `develop` ahead by CLAUDE.md + WP-20 + WP-21. No Critical/High open.

**EXACT NEXT STEP:** **WP-22** — local REST gateway exposing the eight tools over the WP-21 OpenAPI-3.1 surface, reusing WP-20's bearer-auth/loopback transport seam. Branch `wp-22-rest-gateway` → PR into `develop`.

---

## Session 16 (cont.) — 2026-06-03 — 🎉 Phase-3 interop COMPLETE (WP-22, 23, 24); v1.5.0 staged

Continued unattended ("resume and continue all remaining WPs"). Sole driver (the S16 concurrent session stayed stopped — verified clean each WP). Finished the Phase-3 arc:

**WP-22 — local REST gateway (merged #21, `2cf269b`).** `mta serve --rest` serves the eight tools as plain JSON (`POST /tools/{name}`) — the exact OpenAPI 3.1 surface WP-21 describes — for non-MCP clients. New `mta/interop/rest.py`; reuses WP-20's bearer-auth + loopback + a `Host`-allowlist middleware (DNS-rebind); `/openapi.json` (live) + unauth `/healthz`; blocking calls in a threadpool. Also hardened `schemas._raw_tools` to prefer the **sync** registry (loop-safe; no coroutine leak). 18 tests; full lane 111 passed.

**WP-23 — pluggable inference backends (merged #22, `07e6d96`).** `MTA_BACKEND` routes text generation + embeddings to Ollama (default, **byte-identical**) or an OpenAI-compatible `/v1` server (lmstudio/llamacpp/vllm/openai) at `MTA_BACKEND_URL`. New `mta/core/backends.py` centralises dispatch; `embed`/`digest`/`extract` delegate with **no signature changes**; classical/hashing offline fallback unchanged (a digest still succeeds with no backend). Vision/transcription stay on Ollama. Loopback default; non-local URL warned once. `memory_status` reports the backend. 14 tests (OpenAI mocked) + a real-socket smoke verified locally; full lane 125 passed.

**WP-24 — per-client recipes + conformance (merged #23, `12ba7ac`).** `mta recipes [--format text|json]` prints copy-paste setup for every surface (Claude Code stdio/HTTP, Claude Desktop, REST curl, OpenAI/Gemini). New `mta/interop/recipes.py`. `tests/test_conformance.py` asserts stdio-MCP `tools/list` == schema catalogue == OpenAI/Gemini/OpenAPI exports == REST registry == the same 8 tools. Full lane 130 passed.

**v1.5.0 staged (release-prep).** Bumped all 5 version strings 1.4.0→1.5.0 (`check_versions.py` green) + cut CHANGELOG `[1.5.0]`. `develop` is the release candidate; `main` still v1.4.0. No Critical/High open. 5 PRs (#19–#23) all green on the 3-OS matrix.

**EXACT NEXT STEP (owner-gated release):** **rotate `HOMEBREW_TAP_TOKEN`** (the S14-exposed PAT) → then merge `develop`→`main` (PR) + `git tag v1.5.0 && git push --tags` → the train publishes PyPI + GitHub Release (+`.mcpb`) + bumps the tap → run the post-publish smoke. Everything is staged; tagging is the owner's call. (Optional after: extra channels + deferred Low/Med per `REVIEW.md`.)

---

## Session 16 (cont. 2) — 2026-06-03 — v1.x+ backlog cleared, 🚢 v1.5.0 SHIPPED, README rewritten

Continued unattended ("continue all remaining tasks … then plan, test, update, publish; then redevelop the README"). Sole driver throughout.

**Backlog WPs (each PR → full 3-OS CI green → squash-merged):**
- **WP-60 supply-chain (#25):** committed `constraints.txt` lockfile (CI-09) + a non-blocking `supply-chain` CI job (`pip-audit` + license report); **release tag-gate** — publish jobs run only on a real tag (`workflow_dispatch` = build/sign dry-run); Homebrew job `continue-on-error` so a bad tap token can't fail a release.
- **WP-61 Docker/GHCR (#26):** multi-stage `Dockerfile` (slim, non-root, tesseract+ffmpeg, `/data` volume, `/healthz` HEALTHCHECK, serves MCP HTTP) + `docker.yml` (PR build-validate + tag → multi-arch `linux/amd64,arm64` push to `ghcr.io/gru-953/memorised-them-all` via `GITHUB_TOKEN`; SHA-pinned). The CI docker job built + smoke-tested the image.
- **WP-62 robustness (#27):** `store.clear_vectors` + digest persists vectors *before* graph and clears them when a digest yields no units (recall/overview can't disagree via a stale matrix); `rapidfuzz` now degrades **loudly** (PIPE-05).
- **WP-63 MCP registry (#28):** `server.json` (root) for the official registry, version-gated by `check_versions.py`; owner submits once via `mcp-publisher`.

**🚢 v1.5.0 RELEASED.** Validated the develop→main release PR (#24; all checks + Phase-6 `e2e-offline` green), merged it (`main` `6c2846a`), tagged **`v1.5.0`** → release run **26844874577 all 4 jobs green**. **Post-publish smoke ✓:** PyPI `1.5.0` (fresh-venv `pip install` → import + CLI ✓), GitHub Release `v1.5.0` (wheel+sdist+`.mcpb`+SBOM+cosign), Homebrew tap → 1.5.0 (the existing tap token was still valid), GHCR multi-arch image building via `docker.yml`. `main` = `develop` = v1.5.0.

**README rewritten from scratch** for novices (plain-language "what is this / why / 60-second quick start / example questions"), with the advanced surfaces (Docker, HTTP/REST, backends, CLI) moved lower. On `develop`; surfaces on the GitHub homepage at the next merge to `main`.

**Owner follow-ups (one-time, not blocking):** rotate `HOMEBREW_TAP_TOKEN`; `mcp-publisher publish` the registry manifest.

**EXACT NEXT STEP:** None required — v1.5.0 is shipped and the v1.x+ backlog is cleared. Optional: cut a small **v1.5.1** (or ride the next feature release) so the rewritten README + any deferred Low/Med (`REVIEW.md`) reach `main`/PyPI; otherwise the program objective is met.

---

## Session 16 (cont. 3) — 2026-06-03 — 🚢 v1.5.1 SHIPPED (novice README is now the public face)

Cut **v1.5.1** to surface the rewritten README. Bumped all 7 version strings 1.5.0→1.5.1 (`check_versions` green) + CHANGELOG `[1.5.1]` (docs-only); `twine check` passed on the new long-description. Release PR #29 (develop→main) — all 21 checks green incl. `e2e-offline` — merged (`main` `c33fa65`), tagged **`v1.5.1`** → release run **26855067617 all 4 jobs green**. **Verified:** PyPI **1.5.1** live and **the new novice README is the PyPI `text/markdown` long-description** (opens with "Give Claude a private memory…"); GitHub Release v1.5.1 (13 signed assets); Homebrew tap 1.5.1; GHCR image. `develop` fast-forwarded to `main` — **`main` = `develop` = v1.5.1**.

**🎉 PROGRAM OBJECTIVE FULLY MET.** Every requested task is done: v1 hardened + published (v1.4.0); v1.x+ Phase-3 interop (WP-20–24) + backlog (WP-60–63) delivered + published (v1.5.0); README rewritten from scratch for novices + published (v1.5.1). No Critical/High open across the whole program.

**Owner follow-ups (one-time, none blocking):** rotate `HOMEBREW_TAP_TOKEN`; `mcp-publisher publish` the registry `server.json`; optionally make the GHCR package public.

**EXACT NEXT STEP:** None. The program objective is met; any further work (deferred Low/Med in `REVIEW.md`, directory listings) is optional and resumes from PROGRESS ▶ RESUME HERE.

---

## Session 16 (cont. 4) — 2026-06-03 — last deferred fix (PIPE-06) → 🚢 v1.5.2; backlog EXHAUSTED

Worked the last clearly-worthwhile deferred item. **WP-64 / PIPE-06 (#30):** the classical (offline) extractor now strips a leading determiner ("The Nordic Grid Authority" → merges with "Nordic Grid Authority"), collapses internal whitespace in facts (no mid-fact newlines), and splits sentences abbreviation-aware (an honorific like "Dr." no longer truncates a fact). `tests/test_classical_extraction.py`; offline suite green, no regression; LLM path untouched.

**🚢 v1.5.2 SHIPPED.** Bumped 7 strings 1.5.1→1.5.2, release PR #31 (21/21 checks green), merged (`main` `6aadebb`), tagged **`v1.5.2`** → run **26856061693 all 4 jobs green**. Verified: PyPI 1.5.2, GitHub Release v1.5.2 (13 signed assets), tap 1.5.2, GHCR. `develop` fast-forwarded → **`main` = `develop` = v1.5.2**.

**The worthwhile backlog is now EXHAUSTED.** Remaining `REVIEW.md` items are *deliberately* not done, with rationale: full graph+vectors **write-transaction** (a torn store is already safe via the load guard → durability nicety not worth a risky store-layout + migration change; its own focused effort if ever wanted); **RECALL-02** (classical facts = provenance-tagged verbatim sentences, the designed recall) + **LIFE-02** residual (mitigated WP-14) — accepted/documented. Owner-only/external: token rotation, `mcp-publisher` submit, GHCR-public, directory listings; winget/scoop N/A for a pip tool.

**EXACT NEXT STEP:** None — program complete (v1.4.0 hardened → v1.5.0 interop+backlog → v1.5.1 README → v1.5.2 PIPE-06), all published & verified. A future session would only pick up the deliberately-deferred items above, none required.

---

## Session 17 — 2026-06-06 — user-reported `${HOME}` digest bug → WP-65/65b → 🚢 v1.6.0 + v1.6.1; local install + ⚠ machine instability

User reported the memory plugin's `${HOME}` bug blocking digests (`config_file: null`) + asked to also default to English+Bangla, all file types, MLX, Ollama-by-default, and write the Claude setup at install; then test/improve/README.

**Diagnosis (live `memory_status`):** Ollama + 3 models, MLX (`gpu: mlx`), Tesseract/ffmpeg all already present (so MLX + Ollama defaults were already satisfied). The bug: the `.mcpb` manifest passes `MTA_HOME=${HOME}/…` and Claude Desktop didn't expand it → the engine wrote to a literal `${HOME}` dir → `config_file` null → digest failed.

**WP-65 (v1.6.0, merged #32):** `config._resolve_home` expands `$VAR`/`${VAR}`/`~` with a safe fallback (the fix); OCR default `eng+ben` with graceful drop of missing Tesseract packs; convert-level plain-text fallback for unknown extensions; new `mta setup-claude` (registers the server in Claude Desktop/Code config, idempotent + backup) run automatically by `install.sh` (+ Bangla pack on dnf/pacman). 16 tests. **Windows CI caught a POSIX-only test assumption** (`Path.home()` uses `USERPROFILE`) — fixed the test, re-green.
**WP-65b (v1.6.1, merged #34):** the v1.6.0 fallback was unreachable in folder digests (`_expand` filtered by `SUPPORTED_EXTS`); `_expand` now includes unknown extensions in folder/glob walks (`MTA_DIGEST_ALL` default on; hidden + binaries skipped), always digests explicit files. +4 tests.

**Verified end-to-end on the published packages:** literal `${HOME}` → `config_file` populated + digest ok + recall hits; folder digest picks up `code.pyx`; Bangla text digested; stdio handshake = 8 tools.

**⚠ Machine instability (not a plugin bug):** twice during the session, files on the *user's machine* vanished — first the repo's `.git` (recovered by re-attaching to origin via `git init` + fetch + reset; **no work lost**, all was pushed), then the **entire Homebrew `mta` install** (bin + Cellar + tap). Root cause unknown (cleanup utility / Time Machine / disk). **Mitigation:** moved the user's install to a self-contained venv `~/.mta-app/venv` (1.6.1) and pointed Claude Desktop + Claude Code configs at it via `setup-claude` (backups saved). Flagged for the user to investigate + to remove the now-redundant broken `.mcpb`.

**EXACT NEXT STEP:** None required — v1.6.1 shipped + verified; the user's `${HOME}` digest bug is fixed and their install/config rebuilt on a venv. User actions (not blocking): investigate the file-deletion cause; remove the old `.mcpb` extension; restart Claude. Released code carries the fix for the `.mcpb` path too (rebuild/reinstall the `.mcpb` from v1.6.1 if they prefer the extension).

---

## Session 18 — 2026-06-06 — live MCP verification → Ollama repair + MLX → WP-66 → 🚢 v1.6.2

Continuation of S17. Goal: verify the user's install through Claude's *actual* MCP connection and close every remaining gap in their "${HOME} fix + eng+ben + all-types + MLX + Ollama-by-default + Claude auto-config" ask.

**Live MCP verification (the server Claude is connected to, not just the CLI):** `memory_status` → healthy, `config_file` non-null (the `${HOME}` fix confirmed through Claude). A live `digest` into an isolated `mta-selftest` project → `files 3/3` (English `memo.txt` + unknown-ext `code.pyx` + Bangla `bangla.txt`), `mode: accurate`, `embed_mode: ollama`, token-free; `recall` → coherent LLM synopsis with hits from all three files incl. Bangla entities. Cleaned up (`forget mta-selftest`) so the user's store stays pristine.

**⚠ 3rd file-deletion victim — Ollama (root cause of an accurate-mode regression).** An accurate digest silently fell back to `classical`/`hash` despite Ollama "running". Root cause (in-process repro): `/api/embeddings` + `/api/generate` returned **HTTP 500 "llama-server binary not found"** — the `ollama` launcher survived (so `/api/tags`/`is_up()` worked + models listed) but the inference runner was deleted from the Homebrew Cellar. A clean `brew reinstall ollama` (→0.30.5) was *still* missing `llama-server` (libexec only had the launcher + an `mlx_metal_v3` symlink). **Fix:** installed the self-contained cask **`ollama-app`** (`/Applications/Ollama.app`, bundles `llama-server`), symlinked `/opt/homebrew/bin/ollama` → the app binary (so MTA's on-demand auto-start uses the working one), launched it. Inference verified: `embed 1×768` + qwen2.5 generate + the live accurate digest above. **MTA was behaving correctly the whole time** — it tried Ollama first (as required) and fell back per the offline invariant; the defect was the corrupted local Ollama.

**MLX gap closed:** base PyPI install omits the heavy Apple-only extra → `mlx_whisper: false`. Installed `memorised-them-all[mlx]`; a fresh process now reports `gpu: mlx`, `mlx_whisper: True` (Apple-GPU for both the LLM via Ollama/Metal and audio via MLX-Whisper).

**WP-66 (v1.6.2, PR #36→develop, #37→main, tag v1.6.2 run 27038666401, 4/4 green):** while re-asserting the Claude config, the Desktop `mcpServers` entry kept vanishing — `setup-claude`'s `_merge_into` used a non-atomic `write_text` + `setdefault` (no-op on a non-dict `mcpServers`), so a **running Claude Desktop** (which watches+reconciles its config) reverted the write. Fixed: stage to a temp file + `os.replace` (atomic) and coerce a non-dict `mcpServers` to a dict. Also aligned the plugin/marketplace `.mcp.json` to `MTA_OCR_LANG=eng+ben` + `MTA_DIGEST_ALL=on`. +1 test (21 pass). Upgraded the user's venv → **1.6.2[mlx]**; confirmed the atomic write makes the Desktop entry stick. Removed the stale broken `.mcpb` (registry + folder, recoverable) and downloaded the fixed v1.6.1/1.6.2 `.mcpb` to `~/Downloads` as a one-click Desktop fallback; wrote `~/.mta-app/SETUP_NOTES.md` (recovery reference).

**EXACT NEXT STEP:** None required — every requested item is implemented, shipped (v1.6.2), and verified through Claude's own MCP connection. `main`=`develop`=v1.6.2; no Critical/High. **User actions (not blocking):** fully quit (⌘Q) + reopen Claude Desktop to load the server (if the raw `mcpServers` entry doesn't survive a Desktop restart, double-click `~/Downloads/memorised-them-all.mcpb` instead — Desktop persists those natively); **investigate what keeps deleting files** (`.git`, brew `mta`, Ollama runner — cleaner/optimizer/antivirus, aggressive sync, or disk faults → Disk Utility → First Aid).

---

## Session 19 — 2026-06-06 — model question → WP-67 → 🚢 v1.6.3 (lighter/multilingual model alternatives)

User asked whether `gemma4:e2b-it-qat` is a better fit and to add it + similar options to the plugin. **Researched the real Ollama landscape (WebFetch/WebSearch):** there is no `gemma4` — Gemma **3n** provides the `e2b-it` ("effective-2B") models (`gemma3n:e2b-it-q4_K_M` 5.6GB) and Gemma **3** provides the QAT models (`gemma3:{1b,4b,12b,27b}-it-qat`; `gemma3:4b-it-qat` = 4GB). Honest verdict: for extraction *quality* `qwen2.5:7b` still leads, but `gemma3:4b-it-qat` is an excellent lighter + strongly-multilingual (140+ langs incl. Bangla) alternative — added as **opt-in**, defaults unchanged.

**WP-67 (v1.6.3, docs/manifest only — no code change):** new README "Choosing a model" section + enriched `manifest.json` `extract_model`/`embed_model`/`vision_model` descriptions with verified-real tags — extraction (`gemma3:4b-it-qat`, `gemma3n:e2b-it-q4_K_M`, `gemma3:1b-it-qat`, `qwen2.5:3b`), embeddings (**`bge-m3`** 100+ langs — best for Bangla recall; `mxbai-embed-large`), vision (`llama3.2-vision`, `qwen2.5vl`, `granite3.2-vision`); added the model env vars to the config table; documented the embed-dimension caveat (re-digest with reset after changing embed model). PR #38→develop, #39→main, tag v1.6.3 (run 27068301458, 4/4 green: build/pypi/github_release/homebrew). Venv upgraded → 1.6.3[mlx] (still backend ollama, gpu mlx, mlx_whisper True).

**EXACT NEXT STEP:** None required — `main`=`develop`=v1.6.3, no Critical/High. The model alternatives are documented + selectable via `MTA_EXTRACT_MODEL`/`MTA_EMBED_MODEL`/`MTA_VISION_MODEL` (or the Desktop extension settings); for a Bangla-tuned stack use `gemma3:4b-it-qat` + `bge-m3` and re-digest with reset. User-machine file-deletion investigation still outstanding (S17–S18).

---

## Session 20 — 2026-06-07 — research ≤16 GB optimum models (agents, repeated) → WP-68 → 🚢 v1.7.0

User: "using only the latest online sources (e.g. ollama.com/search) look again repetitively for the latest+optimum solutions for ≤16 GB machines, update the plugin as many times as needed using agents, then thoroughly/critically test, fix, improve, publish everywhere, and update the README + project details."

**Research (agents, live sources only — 2 rounds):**
- Round 1: three parallel general-purpose agents (extraction / embeddings / vision), each forced to verify exact tags + sizes on live Ollama pages. Findings: extraction `qwen3:4b-instruct` (2.5 GB) > qwen2.5:7b for 16 GB; embed `qwen3-embedding:0.6b` (0.64 GB, 1024-d, MMTEB ≈64) > nomic; vision `qwen3-vl:4b-instruct` (3.3 GB, 32-lang OCR) > moondream; whisper `small`. The extraction agent caught the fetch-summarizer HALLUCINATING models (qwen3.5/gemma4) and discarded them.
- Round 2: an independent verifier agent confirmed every tag against the AUTHORITATIVE `registry.ollama.ai/v2/.../manifests/<tag>` API (what `ollama pull` uses). Critical corrections: `qwen3:4b-instruct-2507` 404s (use `qwen3:4b-instruct`); **bare `qwen3:4b` and `qwen3-vl:4b` are THINKING builds** → pin the `-instruct` tags for clean JSON/captions. Also: `gemma4` and `qwen3.5` are now REAL (released since Round 1) — documented as experimental, not defaulted.

**WP-68 (v1.7.0):** changed config.py defaults + install.sh pull list + manifest.json + .mcp.json + README "Choosing a model" to the new stack; added a qwen3-embedding query-instruction prefix (improve); kept old defaults as documented alternatives; refreshed the GitHub repo description (multilingual + ≤16 GB). All overridable.

**Critically tested on the user's 16 GB Mac BEFORE publishing:** pulled the 3 models; working-tree (1.7.0) digest with new defaults → mode accurate, extract qwen3:4b-instruct + embed qwen3-embedding:0.6b, 3/3 files, 9 entities; English recall 0.688; **Bangla→Bangla recall 0.751** (the multilingual win). Migration safety: digest at 768-d then recall with the 1024-d model → graceful `mode: lexical` fallback (status ok, 4 hits, NO crash); re-digest restores vector recall. 166 offline tests pass; full matrix CI green (#40); release CI green (#41, e2e-offline incl.).

**Published:** tag v1.7.0 (run 27069875217) → PyPI + GitHub Release + Homebrew + GHCR. Venv upgraded to 1.7.0.

**EXACT NEXT STEP:** None required — `main`=`develop`=v1.7.0, no Critical/High. The ≤16 GB optimum stack is the default + live-verified; escalate to qwen3:8b on bigger machines, or try the experimental qwen3.5:4b / gemma4:e2b-it-qat. User-machine file-deletion investigation still outstanding (S17–S18).

---

## Session 21 — 2026-06-07 — real FY 25-26 corpus → WP-69 → 🚢 v1.8.0 (legacy Bengali + convert + LLM hardening)

User: test/fix/improve the plugin + all skills (esp. LLM functionalities) on the **FY 25-26** corpus (2 GB, 711 files: 265 docx / 163 xlsx / 139 pdf / 82 pptx, heavy **SutonnyMJ** legacy Bengali) repetitively to convergence; make **convert-all-to-Markdown a default feature**; build a **legacy Bengali (SutonnyMJ) → Unicode** converter from the **Mukti** folder and integrate it; headless, best options.

**Mukti port (the keystone):** Mukti (anindash15-arch/Mukti, MIT) is a JS Office add-in. Ported its bijoy-to-unicode pipeline to pure-Python `mta/core/bangla_legacy.py` (pre-map → longest-first main map → 2-pass Unicode rearrange → post-map + detection). Node was available at PORT TIME only — used it to dump the mapping tables (`_bangla_maps.py`, ASCII-safe) + the rearrange classification sets faithfully; the shipped feature is dependency-free. **Validated 21/21 identical to the Mukti JS oracle.**

**Font-aware integration (the key correctness insight):** real docs are MIXED (English in Calibri/Arial + Bengali in SutonnyMJ), and a pure-ASCII Bijoy word (`Avwg`→আমি) is indistinguishable from English by characters — so a whole-doc density gate is wrong. Confirmed the docx tag legacy runs with `w:rFonts w:ascii="SutonnyMJ"` (247 runs in one file) → built a **font-aware Office delegacifier** (`.docx`/`.pptx`/`.xlsx`): converts only Bijoy-family-font runs (114 names from Mukti's registry; Boishakhi/Proshika/Lekhoni skipped — different maps), retags to a Unicode font, repackages, then MarkItDown converts the Unicode copy. Plain text uses a conservative density heuristic that excludes the U+2013–2122 punctuation block so English (em-dash/©/smart-quotes) is never touched. Wired into `convert.py` `_try_markitdown` + a plain-text net (default-on, `MTA_BANGLA_LEGACY`). Verified on a real docx: **7273 Bengali chars, 0 residual mojibake, English untouched** (`eª¨vK`→`ব্র্যাক`).

**convert feature:** `digest` already converts to Markdown internally; surfaced it as a first-class **`mta convert <paths> [--out DIR]`** CLI + MCP **`convert()`** tool (writes `markdown_converted/` beside input; legacy Bengali upgraded in the process). Now **9 tools** — updated server registration, REST registry, schema/conformance/transport tests, recipes (count now derived from the catalogue so surfaces can't drift), manifest + SKILL.

**LLM hardening (found by digesting real Bengali):** qwen3:4b leaked `<tool_call>` special tokens into extracted entities/facts (**26 in graph.json**) → added `_scrub` stripping `<tool_call>`/ChatML/`<think>` from every extracted string (**→ 0**). Also `num_predict` 700→1024 (headroom vs truncated-JSON→silent classical fallback) + `<think>`-block stripping in the JSON parser (defensive for thinking-capable qwen3 via non-`format:json` backends).

**Convergence loop:** real-corpus digests surfaced (a) the `<tool_call>` leak, (b) a degraded-Ollama classical/hash fallback + 55-min wall-clock (fixed by an Ollama restart → accurate mode/real embeddings), (c) the 9-tool surface drift (conformance caught it). Drove the offline suite 6-failures→**175 passing**; +9 tests (`test_bangla_legacy.py`). Note: digesting via a `python - <<heredoc` crashes the multiprocessing **spawn** workers (re-imports `<stdin>`) — harness artifact only; the real `mta` CLI/MCP server are unaffected (and `_convert_all` degrades to sequential on a broken pool). Local LLM extraction on dense docs is inherently slow (~40s/chunk) — use `--fast` for bulk.

**Published:** PR #42→develop, #43→main, tag v1.8.0 → PyPI + GitHub + Homebrew + GHCR. Venv upgraded.

**EXACT NEXT STEP:** None required — `main`=`develop`=v1.8.0, no Critical/High. Legacy-Bengali conversion + the `convert` feature are default-on and validated on the real corpus. For the user's 2 GB FY 25-26 corpus, bulk-digest with `--fast` (classical) or digest subsets; the per-doc LLM path is correct but slow on 16 GB. User-machine file-deletion investigation (S17–S18) still outstanding.

---

## Session 22 — 2026-06-08 — 6-expert guardrail brainstorm → WP-70 → 🚢 v1.9.0 (4 GB/no-GPU default + guardrails)

User: continue; then think deeply + brainstorm stability/accuracy guardrails across ALL platforms using **as many expert agents as possible**, prioritising our test roadblocks; **configure the plugin for a 4 GB no-GPU machine as the default** (users opt up); headless, novice-friendly, simple summaries each turn.

**Expert brainstorm (6 parallel agents, each given our real roadblocks):** resource/memory sizing · Ollama runtime reliability · conversion robustness · cross-platform correctness · LLM output safety · novice UX. Strongly-convergent, code-level findings (full reports in the session transcript). Top consensus: (a) the 16 GB-tuned default OOMs/thrashes small boxes — need RAM/GPU-adaptive tiers; (b) silent degradation (Ollama "up" via /api/tags but inference 500s, or thrash→classical/hash) is never surfaced — add an inference probe + honest "degraded" reporting; (c) MarkItDown can hang one file and stall the batch — need a cross-platform per-file timeout; (d) special-token scrub was only on entities/facts, not summaries/synopsis; (e) several atomic-write/spawn/Windows gaps.

**Implemented (v1.9.0, WP-70) — the highest-value cohesive set:**
- **NEW DEFAULT profile `micro`** (safe on 4 GB/no-GPU): `extract_mode=classical` (no heavy LLM → can't OOM/thrash) + `qwen3-embedding:0.6b` (hash fallback) + vision off + 1 worker + tiny whisper. A digest always COMPLETES on any machine. `config.py` `DEFAULT_PROFILE="micro"`; `load()` defaults to it.
- **`MTA_PROFILE=auto`** → `platform.detect_tier()` (RAM-gated: <6 micro / 6-12 small / 12-24 standard=qwen3 stack / ≥24 large=qwen3:8b). Env / explicit profile overrides (env > profile > built-in). `.mcpb` manifest: new "Performance profile" dropdown (default `auto`) + model defaults blanked so the profile drives them (`_env` already treats "" as unset); `.mcp.json` → `MTA_PROFILE=auto`.
- **`worker_count`**: clamp to 1 conversion worker on <6 GB (was `max(2,…)` → OOM risk on 4 GB).
- **LLM safety:** `_llm_summarise` now `_scrub`s its output (covers community summaries + synopsis → memory.md/recall/mindmap); broadened `_SPECIAL_TOK` (gemma `<start_of_turn>`/`<end_of_turn>`, pipe tokens).
- +8 tests (tiers, micro default, env-override precedence, detect_tier buckets, worker floor, summary scrub); 181 offline pass; full CI green. PR #44→develop, #45→main, tag v1.9.0 → all channels.

**Tracked follow-ups from the review (not yet done):** cross-platform per-file conversion timeout (batch-hang guard; chip already filed); honest degraded-mode reporting in `memory_status`/`recall`/`doctor` (the silent classical/hash fallback — high novice value); richer classical extractor (now the default path on 4 GB: sentence-scoped relations, entity gating, grounding filter); atomic `render.py` writes (memory.md/mindmap.html); unique-temp-name in `setup.py`; CI test of the spawn/parallel path + 4 GB worker clamp; `bootstrap_path()` in spawned workers.

**EXACT NEXT STEP:** None required — `main`=`develop`=v1.9.0, no Critical/High. Default is now 4 GB/no-GPU-safe; bigger machines opt up via `MTA_PROFILE=auto`. The user's own venv/Claude config should be set to `MTA_PROFILE=auto` (their 16 GB → standard). The follow-up guardrails above are the next worthwhile work if desired.

---

## Session 23 — 2026-06-08 — 6-agent stress-test sweep → WP-71 → 🚢 v1.10.0 (no batch hangs, crash-safety, classical-path LLM safety)

User: continue the loop — think deeply + brainstorm guardrails with **as many expert agents as possible**, **further stress-test the plugin as many ways as possible**, prioritise our test experiences/roadblocks, run in loops **until convergence**; headless, novice-friendly, simple summaries each turn.

**Stress sweep (6 parallel agents, each told to actively BREAK the plugin and to use temp `MTA_HOME` — never the user's real memory):** conversion chaos (zip bombs, hung/giant/0-byte/encoding-broken files, deep nesting) · runtime degradation (Ollama up-but-500, thrash, mid-stream death) · concurrency & crash safety (parallel digests, kill-mid-write, torn stores) · cross-platform/paths (symlink loops, long/Unicode/reserved names, case-fold) · LLM adversarial (prompt-injection, special-token smuggling, hallucinated entities) · resource limits (4 GB OOM, container RAM misreport). **All headline findings empirically reproduced** (reports in transcript). Top P0/HIGH cluster, in priority of our actual roadblocks:

**Implemented (v1.10.0, WP-71 — branch `wp-71-stress-hardening`):**
- **#1 roadblock — infinite batch hang → per-file timeout.** One MarkItDown/PDF parser hanging used to stall the whole digest with no end (we hit this live in earlier sessions). Each conversion now runs in its **own killable `spawn` subprocess** with a size-scaled deadline (`MTA_CONVERT_TIMEOUT`, default 120 s, ×4/MB for Office/PDF/zip, capped `MTA_CONVERT_TIMEOUT_MAX`=900 s). On timeout → `terminate()`→`kill()`, that file is marked `failed/method=timeout`, **the batch always finishes.** `_convert_all` uses the isolated path when the timeout is on, ThreadPool-fans across files; legacy ProcessPool retained when disabled. (`digest.py`: `_convert_timeout`, `_convert_worker_pipe`, `_convert_isolated`.)
- **Conversion robustness:** `_expand` walks via `os.walk(followlinks=False, onerror=…)` and `resolve()`-dedups → **survives symlink loops / unreadable dirs** (was an infinite/oserror crash); `_assign_output_names` **bounds names** (>200 B → hash-suffixed, <NAME_MAX) and **case-folds** the taken-set (macOS/Windows case-insensitive FS no longer silently overwrites `Read.md`/`read.md`).
- **Crash / corruption safety:** all `render.py` writes (memory.md, per-doc notes, both mindmap paths) routed through `_atomic_write_text` (temp→fsync→os.replace); `save_graph` backs up a **present-but-unparseable** graph.json before overwrite (`pre-overwrite-corrupt`); `load_vectors` catches `Exception` (incl. `zipfile.BadZipFile` from a truncated `vectors.npz`) → **reads as no_memory instead of crashing recall**; `setup.py` `_merge_into` uses a unique `mkstemp` temp.
- **LLM safety on the DEFAULT (classical) path** — the v1.9.0 scrub only covered the LLM path, but `micro`/4 GB **defaults to classical**: `_classical` now `_scrub`s every emitted string + `_defang_fence`s, and the **summary/synopsis fallback** (`_community_summary`, `_synopsis`) is scrubbed+defanged too. `_scrub` hardened — case-insensitive, fullwidth pipe `｜` (DeepSeek), idempotent up to 5 passes (kills nested-reassembly `<tool_<tool_call>call>`). Added `_valid_entity` (reject URLs/numbers/sentences/over-long), `_norm_type` (whitelist), and **grounding** (`_grounded` drops LLM entities whose normalized form isn't in the source chunk → no hallucinated nodes). Relations now **sentence-scoped** (was an O(n²) chunk-wide clique); facts prefer entity-bearing sentences.
- **Resource:** `MTA_MEMORY_GB` override for misreporting containers; clamp negative `MTA_MAX_FILE_MB`→0; `bootstrap_path()`+`pin_native_threads()` inside spawned workers.
- **Tests:** +10 in `tests/test_stress_guardrails.py` (scrub idempotency/nesting/case/fullwidth, fence defang, entity validation, classical scope+scrub, symlink-loop expand, timeout scaling+disable, isolated-path digest completes, output-name bounding+case-fold, corrupt-npz→none, corrupt-graph-backed-up). Added to CI offline lane. **191 offline pass, 1 skipped.**

**Published:** PR #46→develop (squash), #47→main, tag **v1.10.0** → release train (build/pypi/github_release/homebrew) + GHCR. Full matrix green **including `conversion-e2e`** (exercises the real isolated-subprocess timeout path) and Windows (spawn+kill kill-path). Venv upgraded to 1.10.0[mlx]. `main`=`develop`=v1.10.0.

**Convergence note:** Round 1 of the stress loop shipped. The remaining findings are LOWER severity (no new crash/hang/corruption class) and form the **next loop iteration**: honest **degraded-mode reporting** (memory_status inference-probe + digest fail-fast preflight + top-level `degraded` flag + recall `memory_mode` — surface the silent classical/hash fallback to novices); `_loads_json_object` truncated-JSON brace-salvage; UTF-16/BOM decode in `convert`; cgroup `memory.max` auto-detect in `memory_gb`; linear `_rearrange`; explicit out-of-tree-symlink policy; 0-byte → "empty" (not "unsupported").

**EXACT NEXT STEP:** None required to ship — `main`=`develop`=v1.10.0, no Critical/High, venv on 1.10.0. The user must **fully quit Claude Desktop (⌘Q) and reopen** to load v1.10.0. Next worthwhile work = **stress loop Round 2**: implement honest degraded-mode reporting first (highest novice value), then the rest of the backlog above; re-run a stress fan-out to verify convergence.

---

## Session 24 — 2026-06-08 — stress loop Round 2 → WP-72 → 🚢 v1.11.0 (honest degraded-mode reporting)

Continued the until-convergence loop after shipping v1.10.0 (Round 1) earlier this session. Picked the **#1 tracked follow-up** — and a roadblock the owner personally hit 3× (S17/S18/S21): Ollama's launcher stays reachable (`/api/tags` 200) while its inference runner (`llama-server`) is broken or the model isn't pulled, so every generate/embed 500s and a digest **silently** degrades to classical/hashing extraction with no signal (once a 55-minute run that had quietly fallen back). `is_up()` only probed `/api/tags`, so `memory_status` showed green and the user was misled.

**Implemented (v1.11.0, WP-72 — branch `wp-72-degraded-honesty`):**
- **`backends.inference_ok(cfg, ollama)`** — a real 1-token `/api/generate` probe (not just reachability). Returns `True` (works) / `False` (definitive break — 500/404/refused) / `None` (inconclusive: paid OpenAI-compatible backend → don't bill it; launcher unreachable → may be idle-stopped & startable; slow cold model-load → timeout). The False/None split is the crux of "no false alarms".
- **`memory_status`** — new `ollama_inference` (`ok|degraded|down|disabled|unknown`), top-level `degraded` bool, plain-English `health` line. Probe uses a snappy 8 s timeout; OpenAI backend → `unknown` (not a misleading "start Ollama").
- **`digest`** — top-level `degraded` (+ `degraded_reason`) when higher-accuracy mode was expected (`not fast and extract_mode != classical`) but `stats.mode` came back `classical`; a **preflight probe** prints a heads-up at the START of a digest (not after a long silent run). `no_input` early-return carries `degraded:False` for shape consistency.
- **`recall`** — `memory_mode` (`accurate|classical|fast`) on both the cosine and lexical paths, so basic-mode answers are transparent.

**Adversarial review BEFORE merge (1 expert agent on the diff)** — caught a real **cry-wolf bug (A1)**: `inference_ok` returned `False` for BOTH "broken runner" and "idle-stopped", but Ollama auto-stops after 5 min idle → the preflight would warn "basic mode" right before the real extraction's `ensure_running()` restarts it and runs accurately (false alarm on the routine happy path; tests missed it because they all used `MTA_NO_OLLAMA=1`). **Fixed:** unreachable/idle → `None` (not broken); cold-load timeout → `None` (socket.timeout / URLError-timeout split) → `memory_status` shows `unknown`, not a false `degraded`; OpenAI backend → `unknown`; preflight warns only on a *definitive* break (`is False`). Also softened `degraded_reason` (covers embed-only fallback) + added the `no_input` degraded key. +3 regression tests for the fix (9 total in `test_degraded_mode.py`). Reviewer's convergence verdict: **converged** for a novice on ≤16 GB (the default `micro`/`offline` profiles set `extract=classical` → `expected_llm=False` → they correctly never see a degraded warning/flag and get the reassuring "no action needed" `health` line); confirmed no existing dict-key test contracts broken.

**Published:** PR #48→develop (squash), #49→main (merge-commit), tag **v1.11.0** → release train (build/pypi/github_release/homebrew) + GHCR. Full matrix green incl. `conversion-e2e`. Venv upgraded to 1.11.0[mlx] + verified the installed wheel. `main`=`develop`=v1.11.0. Offline suite **202 pass / 1 skip**.

**Round-3 backlog (next loop, all LOWER severity — no new crash/hang/corruption class):** 0-byte file → "empty" (not "unsupported"); UTF-16/BOM decode in convert; truncated-JSON brace-salvage in `_loads_json_object`; cgroup `memory.max` auto-detect in `memory_gb`; linear `_rearrange`; explicit out-of-tree-symlink policy. Reviewer's novice-on-16 GB ranking: 0-byte > UTF-16/BOM > JSON-salvage > cgroup/perf.

**EXACT NEXT STEP:** None required to ship — `main`=`develop`=v1.11.0, no Critical/High, venv on 1.11.0, reviewer says converged. The user must **fully quit Claude Desktop (⌘Q) and reopen** to load v1.11.0. Next worthwhile work = **stress loop Round 3** (the lower-severity backlog above), starting with 0-byte→"empty" and UTF-16/BOM decode; re-run a stress fan-out afterward to confirm convergence holds.

---

## Session 25 — 2026-06-08 — stress loop Round 3 → WP-73 → 🚢 v1.12.0 (lower-severity backlog cleanup)

User: "do round 3 and the remaining." Implemented all six tracked lower-severity follow-ups from the stress sweep (none a new crash/hang/corruption class), each with a regression test in `tests/test_backlog_round3.py`:
1. **0-byte → `empty`**: `convert_file` returns `status="empty"/method="empty-file"` for any 0-byte file before extension routing (was `unsupported`/`failed`).
2. **BOM/UTF-16 decode**: new `convert._decode_text_bytes` (BOM table, UTF-32 before UTF-16, strips the kept U+FEFF) used by `_native_text` AND `_try_unknown_text`. Windows "Unicode" `.txt`/`.csv` no longer mojibake; an unknown-ext UTF-16 file's interleaved NULs no longer misflag it binary (BOM detected → decode; non-BOM keeps the NUL/printable binary heuristic).
3. **Truncated-JSON salvage**: `extract._salvage_json_object` cuts at the last complete nested object, drops a dangling comma, re-balances brackets/braces (string/escape-aware) → recovers entities/relations/facts from a cut-off reply instead of dropping the whole chunk to classical. Reached ONLY on `JSONDecodeError`; returns None (unchanged) if still unparseable, so it can only recover.
4. **cgroup-aware `memory_gb`**: split into `_host_memory_gb()` + `_cgroup_mem_limit_gb()` (reads cgroup v2 `memory.max` then v1 `memory.limit_in_bytes`; ignores `max`/2^63-sentinel/absurd); `memory_gb = min(host, limit)`. So auto-tiering inside a memory-capped Docker/K8s/CI container picks a safe profile.
5. **Out-of-tree symlink policy**: in `_expand.add`, a FOLDER-walk symlink whose `resolve()` escapes the digested root (`relative_to(root.resolve())` raises) is skipped — can't be tricked into reading `~/.ssh/…`. Explicit paths + globs still honoured; existing symlink-loop test still green.

**Adversarial review before merge (1 expert agent)** — verdict: no blockers, but it correctly flagged that a **6th attempted item (line-wise `_rearrange` perf opt) was NOT byte-identical**: the Pass-1 kar/nukta+halant rule is gated on POSITION (`i < len-1`), not character class, so whole-string processing legitimately drags a kar across a `\n` that per-line processing leaves — ~0.17% of multi-line Bijoy diverges from the Mukti reference. Since the converter is oracle-matched and the owner already converted the full FY 25-26 corpus with it, **fidelity wins → REVERTED the `_rearrange` change** (restored whole-string; added a NOTE for the next person; removed the tautological test that couldn't fail). Also fixed 2 real nits: (N1) explicit-endian utf-16/32 codecs keep a leading U+FEFF → `lstrip("﻿")` so it can't prepend a zero-width char to the first heading/entity; (N2) the refactor left the public `memory_gb()` un-cached → restored `@functools.lru_cache(maxsize=1)` (tests `cache_clear()` around monkeypatched assertions). Other 5 fixes confirmed clean; no existing status/method/JSON test contract broken.

**Published:** PR #50→develop (squash), #51→main (merge-commit), tag **v1.12.0** → release train (build/pypi/github_release/homebrew) + GHCR. Full matrix green incl. conversion-e2e. Venv→1.12.0[mlx] + verified the installed wheel. `main`=`develop`=v1.12.0. Offline suite **211 pass / 1 skip**.

**Convergence:** reviewer's verdict across all three rounds (v1.10.0 hangs/crash/corruption · v1.11.0 degraded-honesty · v1.12.0 this) = **converged for a novice on ≤16 GB; no Critical/High open**. The stress backlog is now essentially empty — the only deferred item is a semantics-preserving `_rearrange` linearization (perf-only, never bites real newline-bearing docs, not worth the fidelity risk).

**EXACT NEXT STEP:** None required to ship — `main`=`develop`=v1.12.0, venv on 1.12.0, all 3 stress rounds converged. The user must **fully quit Claude Desktop (⌘Q) and reopen** to load v1.12.0 (gets Rounds 1+2+3 in one bundle). No further loop work outstanding; future sessions are net-new features only (e.g. Phase-3 interop WP-20–24 already done; nothing pending). The recurring user-machine file-deletion root cause remains the owner's to investigate (cleaner/AV/sync/disk) — unrelated to the plugin.
