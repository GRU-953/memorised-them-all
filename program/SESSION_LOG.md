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
