# IMPROVEMENT PLAN — R1–R6 · interop · roadmap

Dependency-ordered. Each WP lists the audit findings it **closes**, entry/exit criteria, primary files, the tests that prove it, and impact/effort. Scope tags per ADR-002: **`v1`** (ship first) · **`v1.x+`** (designed now, delivered later). Acceptance IDs (A1…A12) are defined in `ACCEPTANCE.md`.

> **Plan-gate status:** awaiting owner approval. No implementation WP starts until this plan + `ACCEPTANCE.md` are approved.

## v1 dependency order (the critical path)

```
WP-03 (CI fidelity + version single-source + quick-win hygiene)
   └─► WP-10 (R1 install + OFFLINE-correct bootstrap)  ─┐   [closes Critical PKG-03]
   └─► WP-13 (R4 safe auto-update, integrity+rollback) ─┘   [theme A — fix once]
        └─► WP-14 (R5 lifecycle + cross-process locking)     [closes Critical LIFE-01]
             └─► WP-15 (R6 versioning + data migration)      [closes LIFE-03]
WP-11 (R2 auto-config)  ─►  WP-12 (R3 dep scan + `mta doctor`)
WP-30 (offline recall reliability)   [closes DOC-01]   ┐
WP-32 (security completion + SECURITY.md)              ├─ parallelizable after WP-03
WP-31 (eval harness + golden corpus → ACCEPTANCE nums) ┘
WP-40 (release train + supply-chain)  ◄ needs WP-03 + WP-10/13
   └─► WP-41 (first synchronized v1 release) ◄ needs Phase-2 green
WP-50 ► WP-51 ► WP-52 (Phase-6 sandbox E2E → TEST_REPORT) ◄ needs Docker (R-01)
WP-90 (convergence review & note)
```

---

## v1 Work Packages

### WP-03 — CI fidelity, single version source & quick-win hygiene · `v1`
**Closes:** CI-10, DOC-02, DOC-03/MCP-08, PKG-01, PKG-02/CI-07, CI-08, CI-12, PKG-05/06/09, MCP-07, PIPE-04, DOC-21 (+ assorted doc/test quick wins).
**Why first:** the green badge today doesn't exercise conversion and one test *errors* under the CI dep set — so CI can't be trusted to gate anything else. Single-sourcing the version unblocks the release train.
**Exit:** (a) a CI lane installs **full** runtime deps and runs a real offline conversion (PDF/DOCX/XLSX/image)→digest→recall; (b) `test_ocr_stdin_pipe` skips cleanly without pillow; (c) `mcp_stdio_check` asserts all **8** tools incl. `forget`; (d) one canonical version source (`mta/__init__.py` via hatch `dynamic`), a `scripts/check_versions.py` CI gate failing on any drift among the 6 strings, and a tag==version gate; (e) `.mcpb` build smoke-tested in CI; (f) handlers validate inputs (no unhandled exception across the MCP boundary). **Gates A9, part of A3/A8.**
**Files:** `.github/workflows/ci.yml`, `tests/`, `pyproject.toml`, `mta/__init__.py`, all 6 version files, `scripts/`, `mta/server.py`.
**Impact:** High · **Effort:** M.

### WP-10 — Install simplicity + offline-correct bootstrap (R1) · `v1`
**Closes:** **PKG-03 (Critical)**, PKG-04, DOC-17; hardens A1/A2.
**Change:** make the **PyPI-pinned MarkItDown the default, offline-correct baseline** (already a dep); move the `git+https` upstream pull behind an explicit, documented, network-gated `mta update`/opt-in (see WP-13). Zero-config first-run prints a clear success/failure summary. `.mcpb` zip-fallback includes `launch.py`+`scripts/`. Keep + CI-validate `.mcpb`/plugin manifests (already spec-valid).
**Exit:** a fresh install with **no network** completes `digest` (A2); one obvious action per surface (A1). **Decision needed:** auto-update default direction (see open questions Q1).
**Files:** `install.sh`, `scripts/mta-launcher.sh`, `launch.sh/py`, `mta/core/updater.py`, `scripts/build_mcpb.sh`, README.
**Impact:** Critical · **Effort:** M.

### WP-13 — Safe auto-update: integrity + atomic + rollback (R4) · `v1`
**Closes:** **DEP-01 (High)**, SEC-04 (High), DEP-02, DEP-03, DEP-09/LIFE-08; theme A.
**Change:** pin the upstream source (commit/tag) **and verify integrity (hash/signature) before applying**; make updates atomic with rollback; never run on the request path or break a running digest; either *apply* the self-update or clearly document it as report-only; atomic daily-throttle stamp; honor offline/`off`.
**Exit:** simulated update applies + rolls back cleanly; offline opt-out verified; no unpinned/unverified install path remains. **Gates A8 (integrity).**
**Files:** `mta/core/updater.py`, `lifecycle.py`, `config.py`. **Impact:** High · **Effort:** M.

### WP-14 — Lifecycle + cross-process concurrency (R5) · `v1`
**Closes:** **LIFE-01 (Critical)**, LIFE-02 (High), PIPE-03 (High), LIFE-07, DEP-08.
**Change:** add **cross-process locking** (stdlib `fcntl`/`msvcrt`, or `filelock` if approved — see Q2): single-writer/multi-reader on a project, no torn reads, no double-started server, no deadlock. Fix the idle watchdog so the activity marker and the stopping process are coupled (don't kill a busy worker; do stop when truly idle). Fast-fail when Ollama is installed-but-unreachable (no 20 s stalls). Generalize lazy-start/idle-stop to managed deps; keep the "only stop what we started / never the user's Ollama" guarantee.
**Exit:** 4-way concurrent digest on one project → no corruption, ≤1 Ollama (A5); idle stop within tolerance, user's Ollama untouched, no orphans (A6).
**Files:** `mta/core/lifecycle.py`, `store.py`, `server.py`, `digest.py`. **Impact:** Critical · **Effort:** L.

### WP-15 — Compatibility, versioning & data migration (R6) · `v1`
**Closes:** **LIFE-03 (High)**, PKG-01 (durable), DOC-20.
**Change:** treat `graph.json`/vector store as a **versioned schema** with automatic, atomic, **backup+rollback migration**; older stores stay at least **read-recallable**; a newer-than-supported store is backed up with a clear message (never silently "no memory"). Formalize SemVer + deprecation policy; preserve public CLI/tool contracts across minors; one version source (from WP-03).
**Exit:** vN-1 fixture store recalls read-only after upgrade; newer store handled safely (A7).
**Files:** `mta/core/store.py`, `digest.py`, `CHANGELOG.md`, docs. **Impact:** High · **Effort:** M.

### WP-11 — Auto-configuration (R2) · `v1`
**Closes:** DEP-05, DEP-06, DEP-07, PKG-09.
**Change:** persist resolved config; **named profiles** (laptop/workstation/server/offline); surface GPU/CUDA + LM Studio detection in `summary()`; documented overrides; manifest/.mcp.json config parity.
**Exit:** profile selection + persisted config verified; `memory_status` reports GPU + detected services.
**Files:** `mta/core/config.py`, `platform.py`, `server.py`, manifests. **Impact:** Med · **Effort:** M.

### WP-12 — Dependency scan + guided install/upgrade + `mta doctor` (R3) · `v1`
**Closes:** DEP-04, DEP-10.
**Change:** preflight scanner reporting **present/outdated/missing with detected-vs-required versions**; guided install/upgrade via the correct per-platform manager (pip/brew/apt/dnf/pacman/winget/choco/scoop), argv-only, idempotent, `--dry-run`, graceful no-admin remediation; surface via `mta doctor`/`memory_status`.
**Exit:** `mta doctor` reports an accurate matrix and offers a safe, idempotent fix.
**Files:** new `mta/core/deps.py`(?), `cli.py`, `platform.py`, `server.py`. **Impact:** Med · **Effort:** L.

### WP-30 — Offline recall reliability & classical-extraction quality · `v1`
**Closes:** **DOC-01 (High)**, RECALL-02, RECALL-03, PIPE-05, PIPE-06.
**Change:** make `low_confidence` + `MTA_RECALL_MIN_SCORE` work on the **hashing/offline path** (calibrated lexical-overlap confidence); fix `top_score` vs returned-hits consistency; treat `rapidfuzz` as the hard dep it is (or truly optional with a clear degrade notice); improve classical entity/fact quality (fragmentation, newline-laden facts); tighten the "contents never return" wording vs verbatim classical facts.
**Exit:** off-topic query offline → `low_confidence==True` and floor filters (A4).
**Files:** `mta/core/recall.py`, `extract.py`, `resolve.py`, `embed.py`. **Impact:** High · **Effort:** M.

### WP-32 — Security hardening completion + `SECURITY.md` · `v1`
**Closes:** **SEC-01 (High)**, SEC-02, SEC-03/DOC-04/LIFE-05, SEC-10, SEC-11.
**Change:** extend the decompression-bomb/size cap to **all** container formats (docx/xlsx/pptx/epub); delimit attacker-influenced text in **summary/synopsis** prompts (second-order injection); set `allow_pickle=False` explicitly; remove the mindmap unpkg CDN fallback so "zero network" is literally true; document/segregate GPL optional libs; write `SECURITY.md` + threat model.
**Exit:** bomb test passes for every container format; security regression tests green. **Gates A12.**
**Files:** `mta/core/convert.py`, `digest.py`, `store.py`, `render.py`, `templates/mindmap.html.j2`, `SECURITY.md`. **Impact:** High · **Effort:** M.

### WP-31 — Eval harness + reference corpus + golden metrics · `v1`
**Closes:** DOC-18, DOC-19 (substantiate/replace claims); supplies the numbers behind A10/A11.
**Change:** committed (or pinned-fetch, no copyrighted material) multi-format multilingual corpus + golden expected metrics; measure conversion fidelity, retrieval P/R/F1, fast-vs-accurate speedup, cold-start, peak/idle memory; CI-gated thresholds; replace marketing numbers with measured ones.
**Exit:** `make eval` produces a stable report; CI fails on regression vs ACCEPTANCE floors.
**Files:** `eval/`, `tests/`, CI. **Impact:** High · **Effort:** L.

### WP-40 — Release train + supply-chain hardening + publish manifest · `v1` (core channels) / `v1.x+` (rest)
**Closes:** CI-02/SEC-07, CI-03/SEC-06, CI-04, CI-05, CI-06, CI-09/SEC-05, CI-11 (+R-02 tap), CI-08, MCP-06.
**Change (v1 core):** **single build → publish**; **OIDC trusted publishing** to PyPI; **SHA-pin** all Actions; committed **lockfile**/reproducible build; **SBOM + sigstore/cosign signature + provenance** per artifact; **idempotent + halt-and-rollback** (no partial release); **automate the Homebrew tap bump**; tag==version gate; CI license + vuln scans that block; post-publish re-install smoke per channel; **publish manifest** (channel → secret names → verification). **v1.x+:** Docker/GHCR multi-arch, MCP registry + directories, Claude marketplace listing, winget/choco/scoop/snap/flatpak/AUR, npx wrapper.
**Exit:** dry-run release to test indices passes all gates (A8). **Decision needed:** Q3 (credentials/OIDC/tap automation).
**Files:** `.github/workflows/release.yml`, `scripts/`, tap repo, `program/PUBLISH_MANIFEST.md`. **Impact:** High · **Effort:** L.

### WP-41 — First synchronized v1 release · `v1`
**Entry:** Phase-2 acceptance green + WP-40 dry-run green. **Exit:** one tag publishes PyPI+Homebrew+GitHub Release(+.mcpb) in lockstep, all verified; README badges/state accurate. **Impact:** High · **Effort:** S.

### WP-50 / WP-51 / WP-52 — Phase-6 sandbox E2E → `TEST_REPORT.md` · `v1`
**Entry:** Docker available (R-01). **Scope:** clean-image install per channel (incl. missing/outdated tools), auto-config profiles, full tool/CLI functionality on a multilingual corpus (incl. Bengali/CJK), invariants (token-free, atomic, offline), lifecycle, cross-client (stdio/HTTP/REST — HTTP/REST are v1.x+), auto-update apply+rollback, perf/eval, security (malformed/bomb/injection), constrained/negative. **Exit:** `program/TEST_REPORT.md` green; fix-and-retest loop. **Impact:** High · **Effort:** L.

### WP-90 — Convergence review & note · `v1`
Fresh-eyes pass; confirm no Critical/High remain, all acceptance gates pass, last pass yields only declined marginal items; write the convergence note. **Impact:** High · **Effort:** S.

---

## v1.x+ backlog (designed now, delivered later — ADR-002)

- **Phase 3 interop:** WP-20 dual MCP transport (stdio + **secure** Streamable HTTP), WP-21 schema exports (OpenAI/Gemini/**OpenAPI 3.1**), WP-22 local REST gateway, WP-23 pluggable backends (Ollama/LM Studio/llama.cpp/OpenAI-compatible), WP-24 per-client recipes + conformance tests. *Architect the transport/schema/backend seams cleanly in v1 so these drop in without a rewrite.*
- **Phase 4 roadmap (prioritized):** incremental/watch mode + content-hash dedup; hybrid retrieval (BM25 + dense + optional local rerank); layout/table-aware chunking; daemon/service mode; encryption-at-rest (opt-in passphrase) + secure delete in `forget`; observability (structured logs/`--verbose`/metrics); accessible mind map (keyboard/screen-reader/high-contrast) + GraphML/GEXF export; import/merge/diff of memories; expanded multilingual OCR/resolution; optional off-by-default local web UI.
- **Phase 5 extra channels:** containers/registries/store listings (see WP-40 v1.x+).

## Deliberately declined / deferred (logged in DECISIONS as they're taken)
- **Heavy rerank models / large new deps in v1** — conflict with "simplest install"; deferred to v1.x+ hybrid retrieval.
- **Encryption-at-rest ON by default** — would complicate first-run + portability; propose **opt-in** (Q4).
- **Adding Python 3.14 to the CI matrix now** — wait until all conversion deps publish 3.14 wheels (R-06).
