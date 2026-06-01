# Risk Register

Likelihood × Impact, with mitigation + status. Updated whenever risks change. (Initial set from S01 bootstrap; audit-derived risks appended after WP-01.)

| id | risk | likelihood | impact | mitigation | status |
|----|------|-----------|--------|------------|--------|
| R-01 | Docker **not installed** on the dev machine → Phase-6 container / clean-image install matrix cannot run locally | High | Med | Install Docker Desktop, or use `venv` + a UTM/VM sandbox for clean-env tests; run the container matrix in CI instead | Open |
| R-02 | Homebrew tap formula **stale at v1.2.0** (latest is 1.3.3) → `brew install` delivers a 2-release-old build | **Confirmed** | High | Automate tap-formula bump in the release train (WP-40); backfill 1.3.3 now | Open |
| R-03 | Release pipeline lacks **OIDC/trusted-publishing, signing, SBOM, hash-pinned actions**; double-builds artifacts | **Confirmed** | High | Harden `release.yml` in WP-40 (Phase 5); single build → publish | Open |
| R-04 | Very new project, single maintainer, **rapid churn** (7 tags in ~2 days) → regression risk | High | Med | Acceptance criteria + CI gates + eval harness | Open |
| R-05 | PyPI / general web flaky from dev machine (python `urllib` failed once; `curl` ok) | Med | Low | Prefer `curl`/`gh`; retry network steps; treat as transient | Monitoring |
| R-06 | Dev machine Python is **3.14**, CI tests 3.10/3.12 → local repro may diverge from CI | Med | Med | Use pinned `venv`s (3.10/3.12) for local repro; add 3.14 to matrix only once deps support it | Open |
| R-07 | PyPI version set ≠ git tags (PyPI missing **1.0.0 & 1.3.0**) → version-provenance confusion | **Confirmed** | Low | Single version source + release checklist (WP-15 / WP-40) | Open |
| R-08 | Auto-update pip-installs **unpinned** MarkItDown from git `main` on the hot path → breaks offline-first + reproducibility + supply-chain at once (PKG-03/SEC-04/DEP-01) | **Confirmed** | High | PyPI-pinned default + integrity-verified opt-in upstream (WP-10/WP-13) | Open |
| R-09 | **No cross-process locking** → concurrent clients on one `MTA_HOME`/project corrupt shared graph/vectors (LIFE-01) | **Confirmed** | High | Cross-process single-writer/multi-reader lock (WP-14) | Open |
| R-10 | Offline recall reliability signal no-ops (`low_confidence` hardcoded `False` on hashing path) → Claude can't decline off-topic offline (DOC-01) | **Confirmed** | Med-High | Calibrated lexical confidence on offline path (WP-30) | Open |
| R-11 | **CI doesn't exercise real conversion** (`--no-deps` subset) and one test errors under CI deps → regressions slip past a green badge (CI-10/DOC-02) | **Confirmed** | High | Full-deps conversion lane + fix test guards (WP-03) | Open |
| R-12 | Schema versioned but **no migration/backup/rollback**; a newer store is silently treated as "no memory" (LIFE-03) | **Confirmed** | Med | Atomic migrate + backup + read-recall of old stores (WP-15) | Open |
