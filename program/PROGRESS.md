# PROGRESS — program state machine

**Single source of truth for cross-session work.** If code and this file disagree, code wins — reconcile here and note it in SESSION_LOG.

**Working branch:** `develop` (holds `program/` state). **Releasable:** `main`. **Feature branches:** `wp-<id>-<slug>` → PR into `develop`. See DECISIONS ADR-001.
**Status legend:** TODO · IN-PROGRESS · BLOCKED · IN-REVIEW · DONE. **Scope tag:** `v1` (ship first) · `v1.x+` (designed now, delivered later) — ADR-002.

---

## ▶ RESUME HERE
**v1.4.0 SHIPPED (all core channels: PyPI + GitHub Release + `.mcpb` + Homebrew tap); v1.x+ Phase-3 interop now UNDERWAY on `develop`.** `main` = v1.4.0; `develop` is ahead by CLAUDE.md + WP-20 + WP-21.
**DONE this session (S16):** **WP-20** secure Streamable HTTP transport — `mta serve --http`, loopback-only + mandatory bearer + DNS-rebind, no new top-level dep (merged #19, `9e1029a`) · **WP-21** cross-AI schema exports — `mta export-schema` → OpenAI/Gemini/OpenAPI 3.1, derived from the live registry so they can't drift (merged #20, `fa86ec3`). Both green on the full 3-OS matrix.
**▶ Next = WP-22** local REST gateway over the OpenAPI-3.1 surface (reuses WP-20's bearer/loopback transport seam + WP-21's `to_openapi()`), then **WP-23** pluggable backends, **WP-24** per-client recipes + conformance. Also available: extra publishing channels + deferred Low/Med (`REVIEW.md`: graph+vectors write-transaction, CI-09 lockfile, PIPE-05/06, LIFE-02). When Phase-3 (or a useful subset) lands → cut **v1.5.0** (tag from `main`; the train publishes all channels).
**⚠ Before the next release:** rotate `HOMEBREW_TAP_TOKEN` — a fine-grained PAT was exposed in chat during the S14 release.
**⚠ Concurrency (S16):** two unattended sessions briefly shared this one checkout (a 2nd was writing WP-20 while this did WP-21); resolved by sole-driver consolidation. **Run ONE unattended session per working tree**, or give each its own `git worktree`.

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
| WP-34 | Pre-release fresh-eyes review + fixes | 6 | v1 | **DONE** | merged #16 → develop (a46a414) | 06-02 | 21 findings; 3 High + Med/Low fixed; `program/REVIEW.md` |
| WP-40 | Release train + supply-chain + publish manifest | 5 | v1 core / v1.x+ rest | **DONE** | merged #14 → develop (abca304) | 06-02 | CI-02/03/04/05/06/11, SEC-06/07 closed; CI-09 lockfile deferred |
| WP-41 | First synchronized v1 release | 5 | v1 | **DONE 🚢** | v1.4.0 tag (run 26835623380) | 06-02 | PUBLISHED: PyPI + GitHub Release + .mcpb + Homebrew tap; smoke ✓ |
| WP-50 | Sandbox/E2E harness | 6 | v1 | **DONE** | merged #17 → develop | 06-02 | clean-wheel CLI E2E + e2e.yml; container matrix deferred (R-01) |
| WP-51 | E2E test-matrix run | 6 | v1 | **DONE** | merged #17 | 06-02 | offline 5/5 + accurate-mode pass (live Ollama) |
| WP-52 | Fix-and-retest loop → TEST_REPORT.md | 6 | v1 | **DONE** | merged #17 | 06-02 | `program/TEST_REPORT.md` |
| WP-90 | Convergence review & note | 6 | v1 | **DONE** | develop | 06-02 | `program/CONVERGENCE.md` — converged (code) |
| WP-20 | Phase-3: secure Streamable HTTP transport (stdio + HTTP) | 3 | v1.x+ | **DONE** | merged #19 → develop (9e1029a) | 06-03 | `serve --http`; loopback+bearer+DNS-rebind; no new dep |
| WP-21 | Phase-3: cross-AI schema exports (OpenAI/Gemini/OpenAPI 3.1) | 3 | v1.x+ | **DONE** | merged #20 → develop (fa86ec3) | 06-03 | `export-schema`; derived from live registry (no drift) |
| WP-22 | Phase-3: local REST gateway over the OpenAPI-3.1 surface | 3 | v1.x+ | **TODO ▶ NEXT** | — | — | reuse WP-20 transport/auth + WP-21 `to_openapi()` |
| WP-23 | Phase-3: pluggable backends (Ollama/LM Studio/llama.cpp/OpenAI-compat) | 3 | v1.x+ | TODO | — | — | backend seam |
| WP-24 | Phase-3: per-client recipes + conformance tests | 3 | v1.x+ | TODO | — | — | `client_config()` seam exists (WP-20) |

## Artifacts
`AUDIT.md` · `IMPROVEMENT_PLAN.md` · `ACCEPTANCE.md` · `RISKS.md` · `DECISIONS.md` · `SESSION_LOG.md` · `/CHANGELOG.md` · (later: `PUBLISH_MANIFEST.md`, `TEST_REPORT.md`, `SECURITY.md`)
