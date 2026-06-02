# PROGRESS — program state machine

**Single source of truth for cross-session work.** If code and this file disagree, code wins — reconcile here and note it in SESSION_LOG.

**Working branch:** `develop` (holds `program/` state). **Releasable:** `main`. **Feature branches:** `wp-<id>-<slug>` → PR into `develop`. See DECISIONS ADR-001.
**Status legend:** TODO · IN-PROGRESS · BLOCKED · IN-REVIEW · DONE. **Scope tag:** `v1` (ship first) · `v1.x+` (designed now, delivered later) — ADR-002.

---

## ▶ RESUME HERE
**WP-33 (quick-win sweep) DONE — merged to `develop`** (PR #15, `d511a0d`); CI green (run 26817270903). Cleared PIPE-04 (honest `mode` label), DOC-21 (`/forget` + `fast` docs + SKILL sync), PKG-04 (lean/consistent `.mcpb`). PKG-06 N/A (MCPB has no `$schema`); CI-09 deferred (clean hashed lock → v1.x+); RECALL-02 + LIFE-02-residual accepted-as-noted.
**🎉 All Phase-1 Critical/High closed or mitigated; all autonomous build work is done — 12 implementation WPs, PRs #5–#15, every one CI-green on the 3-OS matrix.** Remaining v1 is **gated / large:**
- **WP-41 — first synchronized release (⛔ OWNER-GATED):** needs (ADR-006 / `PUBLISH_MANIFEST.md`) a **PyPI Trusted Publisher** + repo secret **`HOMEBREW_TAP_TOKEN`**, then PR `develop`→`main`, move CHANGELOG *Unreleased*→version, `git tag vX.Y.Z && git push --tags`, watch `build→pypi→github_release→homebrew`, run the post-publish smoke.
- **WP-50-52 — Phase-6 E2E:** local **Docker** (R-01) or a CI container matrix → `program/TEST_REPORT.md`.
- **WP-90 — convergence review** (fresh-eyes) once the above land.
Deferred Low/Med (logged, non-blocking): CI-09 lockfile, PIPE-05/06, RECALL-02, LIFE-02 residual.

---

## Work Packages

| id | title | phase | scope | status | branch/PR | updated | next-action |
|----|-------|:-----:|:-----:|--------|-----------|:------:|-------------|
| WP-00 | Program setup (state files, branch conventions) | 0 | v1 | **DONE** | develop | 06-02 | — |
| WP-01 | Deep audit → AUDIT.md | 1 | v1 | **DONE** | develop | 06-02 | — |
| WP-02 | Plan + risks + acceptance (**plan gate**) | 1–2 | v1 | **DONE** | develop | 06-02 | approved (S02) |
| WP-03 | CI fidelity + single version source + quick-win hygiene | 2 | v1 | **DONE** | merged #5 → develop (4548d02) | 06-02 | CI green; deferred PIPE-04/DOC-21/PKG-06 |
| WP-10 | Install simplicity + **offline-correct bootstrap** (R1) | 2 | v1 | **DONE** | merged #6 → develop (fd2d1d2) | 06-02 | PKG-03 closed; PKG-04 (Low) deferred |
| WP-13 | Safe auto-update: integrity+atomic+rollback (R4) | 2 | v1 | **DONE** | merged #6 → develop | 06-02 | SEC-04/DEP-01/03/09 closed; DEP-02 report-only (ADR-009) |
| WP-14 | Lifecycle + **cross-process concurrency** (R5) | 2 | v1 | **DONE** | merged #7 → develop (a5851ab) | 06-02 | LIFE-01/PIPE-03/DEP-08 closed; LIFE-02 improved |
| WP-15 | Compatibility / versioning / **data migration** (R6) | 2 | v1 | **DONE** | merged #8 → develop (90cfffd) | 06-02 | LIFE-03 closed; A7 met |
| WP-11 | Auto-configuration: profiles, persist, GPU/LM-Studio (R2) | 2 | v1 | **DONE** | merged #9 → develop (81bf1c0) | 06-02 | DEP-05/06/07 closed |
| WP-12 | Dependency scan + guided install + `mta doctor` (R3) | 2 | v1 | **DONE** | merged #10 → develop (66ca5d6) | 06-02 | DEP-04/10 closed; **Phase 2 ✅** |
| WP-30 | Offline recall reliability + classical quality | 4 | v1 | **DONE** | merged #11 → develop (84e8c6c) | 06-02 | DOC-01/RECALL-03 closed (A4); RECALL-02/PIPE-05/06 deferred (Med) |
| WP-32 | Security hardening completion + SECURITY.md | 4 | v1 | **DONE** | merged #12 → develop (6c52714) | 06-02 | SEC-01/02/03/10/11 closed (A12) |
| WP-31 | Eval harness + reference corpus + golden metrics | 4 | v1 | **DONE** | merged #13 → develop (24aef47) | 06-02 | recall@8 gated; DOC-18/19 reworded (A10 partial/A11 reported) |
| WP-33 | Quick-win sweep (PIPE-04, DOC-21, PKG-04) | 4 | v1 | **DONE** | merged #15 → develop (d511a0d) | 06-02 | PKG-06 n/a; CI-09 deferred; RECALL-02/LIFE-02 noted |
| WP-40 | Release train + supply-chain + publish manifest | 5 | v1 core / v1.x+ rest | **DONE** | merged #14 → develop (abca304) | 06-02 | CI-02/03/04/05/06/11, SEC-06/07 closed; CI-09 lockfile deferred |
| WP-41 | First synchronized v1 release | 5 | v1 | TODO | — | — | after Phase-2 green + WP-40 |
| WP-50 | Sandbox/container harness | 6 | v1 | BLOCKED | — | — | needs Docker (R-01) |
| WP-51 | E2E test-matrix run | 6 | v1 | TODO | — | — | after WP-50 |
| WP-52 | Fix-and-retest loop → TEST_REPORT.md | 6 | v1 | TODO | — | — | after WP-51 |
| WP-90 | Convergence review & note | 6 | v1 | TODO | — | — | final |
| WP-20…24 | Phase-3 interop (HTTP transport, schema exports, REST, backends, recipes) | 3 | v1.x+ | TODO | — | — | designed in plan; built post-v1 |

## Artifacts
`AUDIT.md` · `IMPROVEMENT_PLAN.md` · `ACCEPTANCE.md` · `RISKS.md` · `DECISIONS.md` · `SESSION_LOG.md` · `/CHANGELOG.md` · (later: `PUBLISH_MANIFEST.md`, `TEST_REPORT.md`, `SECURITY.md`)
