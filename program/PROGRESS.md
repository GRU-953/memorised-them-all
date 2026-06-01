# PROGRESS — program state machine

**Single source of truth for cross-session work.** If code and this file disagree, code wins — reconcile here and note it in SESSION_LOG.

**Working branch:** `develop` (holds `program/` state). **Releasable:** `main`. **Feature branches:** `wp-<id>-<slug>` → PR into `develop`. See DECISIONS ADR-001.
**Status legend:** TODO · IN-PROGRESS · BLOCKED · IN-REVIEW · DONE. **Scope tag:** `v1` (ship first) · `v1.x+` (designed now, delivered later) — ADR-002.

---

## ▶ RESUME HERE
**WP-03 DONE — merged to `develop`** (PR #5, squash `4548d02`); CI fully green (run 26781819576: 6-cell matrix + `build`/`.mcpb`-smoke + `version-check` + `conversion-e2e`). Plan + acceptance approved (S01).
**Next: start WP-10 + WP-13 together (theme A, ADR-004)** on a fresh branch off `develop` (e.g. `wp-10-offline-install`): make a first-run digest work **fully offline** — default to the PyPI-pinned MarkItDown, and gate the git-upstream pull behind an **integrity-verified opt-in**. Closes **Critical PKG-03** + SEC-04 + DEP-01; targets acceptance **A2** (offline first-run) + **A8** (integrity). Deferred Low follow-ups from WP-03 (fold into a later quick-win pass): PIPE-04, DOC-21, PKG-06.

---

## Work Packages

| id | title | phase | scope | status | branch/PR | updated | next-action |
|----|-------|:-----:|:-----:|--------|-----------|:------:|-------------|
| WP-00 | Program setup (state files, branch conventions) | 0 | v1 | **DONE** | develop | 06-02 | — |
| WP-01 | Deep audit → AUDIT.md | 1 | v1 | **DONE** | develop | 06-02 | — |
| WP-02 | Plan + risks + acceptance (**plan gate**) | 1–2 | v1 | **DONE** | develop | 06-02 | approved (S02) |
| WP-03 | CI fidelity + single version source + quick-win hygiene | 2 | v1 | **DONE** | merged #5 → develop (4548d02) | 06-02 | CI green; deferred PIPE-04/DOC-21/PKG-06 |
| WP-10 | Install simplicity + **offline-correct bootstrap** (R1) | 2 | v1 | TODO | — | — | closes **PKG-03 (Crit)**, PKG-04 |
| WP-13 | Safe auto-update: integrity+atomic+rollback (R4) | 2 | v1 | TODO | — | — | closes DEP-01(High), SEC-04 |
| WP-14 | Lifecycle + **cross-process concurrency** (R5) | 2 | v1 | TODO | — | — | closes **LIFE-01 (Crit)**, LIFE-02, PIPE-03 |
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
