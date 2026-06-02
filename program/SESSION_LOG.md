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
