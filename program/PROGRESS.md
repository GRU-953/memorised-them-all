# PROGRESS — program state machine

**Single source of truth for cross-session work.** If code and this file disagree, code wins — reconcile here and note it in SESSION_LOG.

**Working branch:** `develop` (holds `program/` state). **Releasable:** `main`. **Feature branches:** `wp-<id>-<slug>` → PR into `develop`. See DECISIONS ADR-001.
**Status legend:** TODO · IN-PROGRESS · BLOCKED · IN-REVIEW · DONE. **Scope tag:** `v1` (ship first) · `v1.x+` (designed now, delivered later) — ADR-002.

---

## ▶ RESUME HERE
**🚢 v1.5.0 SHIPPED — Phase-3 cross-AI interop *and* the v1.x+ backlog are COMPLETE.** Tag `v1.5.0` published (release run 26844874577, all 4 jobs green) + post-publish-verified: **PyPI** 1.5.0 (OIDC; fresh-venv install ✓), **GitHub Release** `v1.5.0` (wheel + sdist + `.mcpb` + SBOM + cosign `.sig`/`.pem` per artifact), **Homebrew tap** bumped to 1.5.0, **GHCR** multi-arch image. `main` = `develop` = v1.5.0; no Critical/High open.
**Delivered this arc (S16):** Phase-3 — WP-20 HTTP transport (#19) · WP-21 schema exports (#20) · WP-22 REST gateway (#21) · WP-23 pluggable backends (#22) · WP-24 recipes + conformance (#23). Backlog — WP-60 supply-chain + CI-09 lockfile + release tag-gate (#25) · WP-61 Docker/GHCR (#26) · WP-62 vector-store consistency + PIPE-05 (#27) · WP-63 MCP-registry `server.json` (#28). All additive + invariant-safe.
**Owner follow-ups (one-time, NOT blocking):** rotate `HOMEBREW_TAP_TOKEN` (the S14-exposed PAT still worked for 1.5.0 but should be replaced); submit the registry manifest once (`mcp-publisher login github && mcp-publisher publish`).
**▶ Next (optional only):** README was rewritten from scratch for novices (S16) — it surfaces on the GitHub homepage at the next release to `main`. Deferred Low/Med (`REVIEW.md`: full graph+vectors write-transaction *(accepted — a torn store is already safe via the load guard)*, PIPE-06 entity fragmentation, RECALL-02, LIFE-02 residual); directory/marketplace listings; winget/scoop noted N/A for a pip tool (`PUBLISH_MANIFEST.md`).
**⚠ Concurrency (S16):** run ONE unattended session per working tree (or give each its own `git worktree`).

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
| WP-60 | Supply-chain: lockfile (CI-09) + pip-audit/license + release tag-gate | 5 | v1.x+ | **DONE** | merged #25 → develop | 06-03 | `constraints.txt`; dispatch=dry-run; tap best-effort |
| WP-61 | Docker image + GHCR multi-arch publishing | 5 | v1.x+ | **DONE** | merged #26 → develop | 06-03 | `Dockerfile` + `docker.yml`; GITHUB_TOKEN, no secret |
| WP-62 | Robustness: vector-store consistency + rapidfuzz hard-dep (PIPE-05) | 4 | v1.x+ | **DONE** | merged #27 → develop | 06-03 | `store.clear_vectors`; vectors-before-graph |
| WP-63 | MCP registry manifest (`server.json`) | 5 | v1.x+ | **DONE** | merged #28 → develop | 06-03 | version-gated; owner submits via `mcp-publisher` |
| WP-41b | Second synchronized release (v1.5.0) | 5 | v1.x+ | **DONE 🚢** | tag v1.5.0 (run 26844874577) | 06-03 | PyPI + GitHub Release + .mcpb + tap + GHCR; smoke ✓ |

## Artifacts
`AUDIT.md` · `IMPROVEMENT_PLAN.md` · `ACCEPTANCE.md` · `RISKS.md` · `DECISIONS.md` · `SESSION_LOG.md` · `/CHANGELOG.md` · (later: `PUBLISH_MANIFEST.md`, `TEST_REPORT.md`, `SECURITY.md`)
