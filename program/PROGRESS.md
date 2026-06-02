# PROGRESS — program state machine

**Single source of truth for cross-session work.** If code and this file disagree, code wins — reconcile here and note it in SESSION_LOG.

**Working branch:** `develop` (holds `program/` state). **Releasable:** `main`. **Feature branches:** `wp-<id>-<slug>` → PR into `develop`. See DECISIONS ADR-001.
**Status legend:** TODO · IN-PROGRESS · BLOCKED · IN-REVIEW · DONE. **Scope tag:** `v1` (ship first) · `v1.x+` (designed now, delivered later) — ADR-002.

---

## ▶ RESUME HERE
**🎉 Phase-3 cross-AI interop COMPLETE (WP-20–24, all merged to `develop`, full 3-OS CI green). `develop` = a staged v1.5.0 release candidate.** `main` = v1.4.0 (published).
**DONE (S16):** **WP-20** secure Streamable HTTP transport (`mta serve --http`; #19 `9e1029a`) · **WP-21** cross-AI schema exports (`mta export-schema` → OpenAI/Gemini/OpenAPI 3.1; #20 `fa86ec3`) · **WP-22** local REST gateway (`mta serve --rest`, `POST /tools/{name}`; #21 `2cf269b`) · **WP-23** pluggable backends (`MTA_BACKEND` → Ollama default or OpenAI-compatible; #22 `07e6d96`) · **WP-24** per-client recipes (`mta recipes`) + cross-surface conformance (#23 `12ba7ac`). All additive + invariant-safe (token-free, local-first, no new dependency). **Version bumped to 1.5.0 + CHANGELOG cut** (all 5 version strings agree; `scripts/check_versions.py` green).
**▶ Next = release v1.5.0 (owner-gated):** ⚠ **first rotate `HOMEBREW_TAP_TOKEN`** (a fine-grained PAT was exposed in chat at S14 — the tap job would fail/partial-release otherwise), then merge `develop`→`main` (PR) and `git tag v1.5.0 && git push --tags` → the train publishes PyPI + GitHub Release (+`.mcpb`) + bumps the tap (`PUBLISH_MANIFEST.md`); run the post-publish smoke. The agent staged everything; tagging is the owner's call.
**Then (optional) v1.x+ remainder:** extra publishing channels (Docker/GHCR, MCP registry, winget/scoop/AUR) + deferred Low/Med (`REVIEW.md`: graph+vectors write-transaction, CI-09 lockfile, PIPE-05/06, LIFE-02).
**⚠ Concurrency (S16):** two unattended sessions briefly shared this one checkout (a 2nd wrote WP-20 while this did WP-21); resolved by sole-driver consolidation. **Run ONE unattended session per working tree**, or give each its own `git worktree`.

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
| WP-22 | Phase-3: local REST gateway over the OpenAPI-3.1 surface | 3 | v1.x+ | **DONE** | merged #21 → develop (2cf269b) | 06-03 | `serve --rest`; bearer+Host-allowlist; threadpool |
| WP-23 | Phase-3: pluggable backends (Ollama/LM Studio/llama.cpp/OpenAI-compat) | 3 | v1.x+ | **DONE** | merged #22 → develop (07e6d96) | 06-03 | `MTA_BACKEND`; Ollama default byte-identical; fallback intact |
| WP-24 | Phase-3: per-client recipes + conformance tests | 3 | v1.x+ | **DONE** | merged #23 → develop (12ba7ac) | 06-03 | `mta recipes`; all surfaces == same 8 tools |

## Artifacts
`AUDIT.md` · `IMPROVEMENT_PLAN.md` · `ACCEPTANCE.md` · `RISKS.md` · `DECISIONS.md` · `SESSION_LOG.md` · `/CHANGELOG.md` · (later: `PUBLISH_MANIFEST.md`, `TEST_REPORT.md`, `SECURITY.md`)
