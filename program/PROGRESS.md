# PROGRESS — program state machine

**Single source of truth for cross-session work.** If code and this file disagree, code wins — reconcile here and note it in SESSION_LOG.

**Working branch:** `develop` (holds `program/` state). **Releasable:** `main`. **Feature branches:** `wp-<id>-<slug>` → PR into `develop`. See DECISIONS ADR-001.
**Status legend:** TODO · IN-PROGRESS · BLOCKED · IN-REVIEW · DONE. **Scope tag:** `v1` (ship first) · `v1.x+` (designed now, delivered later) — ADR-002.

---

## ▶ RESUME HERE
**WP-14 DONE — merged to `develop`** (PR #7, squash `a5851ab`); CI fully green (run 26803940371, all 9 jobs incl. **both Windows cells** = the `msvcrt` lock path). **🎉 Both Criticals now closed (PKG-03 + LIFE-01).** DEP-08 + PIPE-03 closed; LIFE-02 improved (residual narrow atexit-vs-busy race deferred).
**Next: WP-15 — compatibility, versioning & data migration (R6)** on a fresh branch off `develop`. Closes **LIFE-03 (High)**: the store is version-stamped but has no migration/backup/rollback — a newer-than-supported store is silently treated as "no memory". In `mta/core/store.py`, on a version mismatch **back up + migrate** (older stores stay at least read-recallable) instead of returning None; add a migration registry + tests with vN-1 fixtures; document SemVer + deprecation policy. Target acceptance **A7**. Then WP-11 (R2) → WP-12 (R3) → WP-30/32/31 → WP-40/41 → WP-50-52. Deferred Low: PIPE-04, DOC-21, PKG-06, PKG-04; LIFE-02 residual.

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
| WP-15 | Compatibility / versioning / **data migration** (R6) | 2 | v1 | TODO | — | — | closes LIFE-03(High) |
| WP-11 | Auto-configuration: profiles, persist, GPU/LM-Studio (R2) | 2 | v1 | TODO | — | — | closes DEP-05/06/07 |
| WP-12 | Dependency scan + guided install + `mta doctor` (R3) | 2 | v1 | TODO | — | — | closes DEP-04/10 |
| WP-30 | Offline recall reliability + classical quality | 4 | v1 | TODO | — | — | closes DOC-01(High), RECALL-02/03, PIPE-05/06 |
| WP-32 | Security hardening completion + SECURITY.md | 4 | v1 | TODO | — | — | closes SEC-01(High)/02/03/10/11 |
| WP-31 | Eval harness + reference corpus + golden metrics | 4 | v1 | TODO | — | — | supplies A10/A11; closes DOC-18/19 |
| WP-40 | Release train + supply-chain + publish manifest | 5 | v1 core / v1.x+ rest | TODO | — | — | closes CI-02..09/11, SEC-05/06/07 |
| WP-41 | First synchronized v1 release | 5 | v1 | TODO | — | — | after Phase-2 green + WP-40 |
| WP-50 | Sandbox/container harness | 6 | v1 | BLOCKED | — | — | needs Docker (R-01) |
| WP-51 | E2E test-matrix run | 6 | v1 | TODO | — | — | after WP-50 |
| WP-52 | Fix-and-retest loop → TEST_REPORT.md | 6 | v1 | TODO | — | — | after WP-51 |
| WP-90 | Convergence review & note | 6 | v1 | TODO | — | — | final |
| WP-20…24 | Phase-3 interop (HTTP transport, schema exports, REST, backends, recipes) | 3 | v1.x+ | TODO | — | — | designed in plan; built post-v1 |

## Artifacts
`AUDIT.md` · `IMPROVEMENT_PLAN.md` · `ACCEPTANCE.md` · `RISKS.md` · `DECISIONS.md` · `SESSION_LOG.md` · `/CHANGELOG.md` · (later: `PUBLISH_MANIFEST.md`, `TEST_REPORT.md`, `SECURITY.md`)
