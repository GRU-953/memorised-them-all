# Risk Register

Likelihood × Impact, with mitigation + status. Updated whenever risks change. (Initial set from S01 bootstrap; audit-derived risks appended after WP-01.)

| id | risk | likelihood | impact | mitigation | status |
|----|------|-----------|--------|------------|--------|
| R-01 | Docker **not installed** on the dev machine → Phase-6 container / clean-image install matrix cannot run locally | High | Med | Install Docker Desktop, or use `venv` + a UTM/VM sandbox for clean-env tests; run the container matrix in CI instead | Open |
| R-02 | Homebrew tap formula **stale at v1.2.0** (latest is 1.3.3) → `brew install` delivers a 2-release-old build | **Confirmed** | High | Automate tap-formula bump in the release train (WP-40); backfill at next release | **Resolved** — tap auto-bumped to v1.4.0 at the v1.4.0 release (run 26835623380) |
| R-03 | Release pipeline lacks **OIDC/trusted-publishing, signing, SBOM, hash-pinned actions**; double-builds artifacts | **Confirmed** | High | Harden `release.yml` in WP-40 (Phase 5); single build → publish | **Mitigated** (WP-40, abca304; lockfile CI-09 deferred) |
| R-04 | Very new project, single maintainer, **rapid churn** (7 tags in ~2 days) → regression risk | High | Med | Acceptance criteria + CI gates + eval harness | Open |
| R-05 | PyPI / general web flaky from dev machine (python `urllib` failed once; `curl` ok) | Med | Low | Prefer `curl`/`gh`; retry network steps; treat as transient | Monitoring |
| R-06 | Dev machine Python is **3.14**, CI tests 3.10/3.12 → local repro may diverge from CI | Med | Med | Use pinned `venv`s (3.10/3.12) for local repro; add 3.14 to matrix only once deps support it | Open |
| R-07 | PyPI version set ≠ git tags (PyPI missing **1.0.0 & 1.3.0**) → version-provenance confusion | **Confirmed** | Low | Single version source + release checklist (WP-15 / WP-40) | Open |
| R-08 | Auto-update pip-installs **unpinned** MarkItDown from git `main` on the hot path → breaks offline-first + reproducibility + supply-chain at once (PKG-03/SEC-04/DEP-01) | **Confirmed** | High | PyPI-pinned default + commit-pinned opt-in upstream + import-smoke/rollback (WP-10/13) | **Mitigated** (fd2d1d2) |
| R-09 | **No cross-process locking** → concurrent clients on one `MTA_HOME`/project corrupt shared graph/vectors (LIFE-01) | **Confirmed** | High | Cross-process single-writer/multi-reader lock (WP-14) | **Mitigated** (a5851ab) |
| R-10 | Offline recall reliability signal no-ops (`low_confidence` hardcoded `False` on hashing path) → Claude can't decline off-topic offline (DOC-01) | **Confirmed** | Med-High | Calibrated lexical confidence on offline path (WP-30) | **Mitigated** (84e8c6c) |
| R-11 | **CI doesn't exercise real conversion** (`--no-deps` subset) and one test errors under CI deps → regressions slip past a green badge (CI-10/DOC-02) | **Confirmed** | High | Full-deps conversion lane + fix test guards (WP-03) | Open |
| R-12 | Schema versioned but **no migration/backup/rollback**; a newer store is silently treated as "no memory" (LIFE-03) | **Confirmed** | Med | Atomic migrate + backup + read-recall of old stores (WP-15) | **Mitigated** (90cfffd) |

### v2.4.2 convergence — accepted / deferred (Med/Low, NOT release blockers)
| id | item (source) | sev | rationale / disposition |
|----|---------------|-----|--------------------------|
| R-13 | Recall BM25 re-tokenizes the full recall-unit corpus + recomputes idf **every query**; recall-unit count uncapped (`recall._bm25_rank`, `digest._recall_units`) — perf cliff (~0.8s @50k units) | Med | **Deferred** to a focused WP: persist/cache a tokenised index at digest time (determinism-sensitive). Workaround: corpus bounded by `MTA_MAX_CHUNKS`; interactive recall fine at typical sizes. Not a regression. |
| R-14 | Entity resolution is O(n²) fuzzy+cosine up to a hard 1500-name cap that doubles as an unannounced quality cliff (`resolve.py`) | Med | **Deferred**: length/first-char bucketing + documented configurable cap. Bounded today; not a regression. |
| R-15 | Recall loads the full unused `vectors.npz` matrix into RAM per query (BM25 never reads it) (`recall.py` via `load_vectors`) | Med | **Deferred** with R-13: add a meta-only loader. Safe perf win, no correctness impact. |
| R-16 | `resolve._norm` still skeleton-merges **non-Bengali Indic** (Devanagari/Tamil); only the Bengali block is preserved | Low | **Accepted**: tool scope is English + Bengali; pre-existing (WP-90 did not regress it). Trivially generalisable later (keep all Brahmic blocks). |
| R-17 | Fuzzy merge can still collapse near-duplicate short Bengali names at the 88 ratio (e.g. করিম/করিমা) (`resolve.py` fuzz_threshold) | Low | **Accepted**: inherent fuzzy-threshold tradeoff; WP-90 *improved* separation (skeleton-100 → 88.9). Not introduced this round. |
| R-18 | cosign signs in the legacy `.sig/.pem` two-file form (deprecated in cosign v3 Oct-2025, removed in v4) (`release.yml`) | Med | **Deferred** to a dedicated supply-chain WP: migrate to the single-file `*.sigstore.json` bundle **before** any cosign-v4 bump. Works on the SHA-pinned v3 installer today. |
| R-19 | Converted `.md` write (`convert.py`) is non-atomic (plain `write_text`, unlike graph/memory) — a crash mid-write can leave a torn `.md` | Low | **Accepted**: blast radius contained — re-digest re-converts from the immutable source; readers use `errors="replace"`. Pre-existing. |
