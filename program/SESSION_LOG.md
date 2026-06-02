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
