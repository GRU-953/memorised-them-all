# ACCEPTANCE CRITERIA

Measurable, CI-gated targets. **Proposed** values await owner approval at the plan gate; numeric floors marked *(calibrate WP-31)* are finalized once the reference corpus exists. "Current" reflects S01 audit/live probe.

| id | criterion | proposed target | CI gate | current | owning WP |
|----|-----------|-----------------|---------|---------|-----------|
| **A1** | Install simplicity | 1 action/surface: double-click `.mcpb`; 2 slash cmds (Code); 1 `pip`/`brew` cmd | manifest+plugin schema-validation; `.mcpb` build+install smoke | mostly met; brew ships stale 1.2.0 | WP-03, WP-10, WP-40 |
| **A2** | Offline first-run | fresh install + `digest` completes **with no network** & no pre-pulled models | CI offline lane (network blocked) runs full-deps convert→digest | **FAILS** (PKG-03: git+https on hot path) | WP-10, WP-13 |
| **A3** | Token-free | `recall` ≤ ~400 tokens (≤600 chars × ≤5 docs + meta); `digest` ≤ ~200 tokens; contents never returned | assertion test on **both** embedding paths | met (capped); strengthen test | WP-03 |
| **A4** | Offline recall reliability | off-topic query on hashing path → `low_confidence==True`; `MTA_RECALL_MIN_SCORE` filters | regression test on hashing path | **FAILS** (DOC-01: hardcoded `False` offline) | WP-30 |
| **A5** | Concurrency safety | 4 concurrent digests / shared project → no corruption, consistent graph↔vectors, no torn read, no deadlock, ≤1 Ollama started | concurrency stress test | **FAILS** (LIFE-01: no cross-process lock) | WP-14 |
| **A6** | Idle lifecycle | self-started Ollama stopped within `MTA_IDLE` + tol (≤ idle+30 s), timer reset under load; user's Ollama never stopped; no orphans on exit | lifecycle tests | partial (LIFE-02 watchdog bug); ownership-correct | WP-14 |
| **A7** | Data migration | vN-1 fixture store is recall-readable after upgrade; newer/corrupt store → backup + clear msg, **no data loss** | migration tests w/ version fixtures | **FAILS** (LIFE-03: no migration; future store → "no memory") | WP-15 |
| **A8** | Release integrity | one version source; CI fails on version drift or tag≠version; **OIDC** publish; **SBOM+signature+provenance** per artifact; idempotent; **halt-and-rollback** (no partial release); tap auto-bumped; post-publish re-install smoke per channel | release-workflow gates + post-publish smoke | **FAILS** (CI-02/05/06/08/09/11, R-02) | WP-03, WP-40 |
| **A9** | CI fidelity | ≥1 lane installs full runtime deps & runs real offline convert (PDF/DOCX/XLSX/image)→digest→recall; `.mcpb` build smoke; all **8** tools asserted | CI | **FAILS** (CI-10 `--no-deps`; DOC-02 test errors; DOC-03 7-tool assert) | WP-03 |
| **A10** | Eval floors *(calibrate WP-31)* | conversion fidelity ≥ 0.95 (born-digital text sim); retrieval recall@5 ≥ 0.80 / precision@5 ≥ 0.70 (accurate), ≥ 0.60/0.50 (fast); fast-vs-accurate speedup = **measured** (≈25× observed, replaces "20–100×") | eval harness thresholds in CI | unmeasured (DOC-18/19) | WP-31 |
| **A11** | Perf/resource *(calibrate WP-31)* | cold-start→first `recall` ≤ target (accurate) / ≤ target s (fast); idle server RSS ≤ ceiling (Ollama stopped); active peak bounded by backpressure | benchmark harness; regression flag vs baseline | partial bounds (PIPE-08 loads full corpus) | WP-31, WP-14 |
| **A12** | Security | decompression-bomb cap on **all** container formats; second-order injection delimited; `allow_pickle=False` explicit; mindmap truly zero-network; `SECURITY.md`+threat model; CI license+vuln scan blocks on violations | security regression + CI scans | partial (SEC-01/02/10) | WP-32, WP-40 |

**Continuously enforced invariants (must never regress):** token-free (A3) · privacy/no-telemetry · atomic crash-safe writes · dependency-free classical/offline fallback (A2). These get dedicated always-on tests.
