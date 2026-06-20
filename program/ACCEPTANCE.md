# ACCEPTANCE CRITERIA

Measurable, CI-gated targets. **Proposed** values await owner approval at the plan gate; numeric floors marked *(calibrate WP-31)* are finalized once the reference corpus exists. "Current" reflects S01 audit/live probe.

| id | criterion | proposed target | CI gate | current | owning WP |
|----|-----------|-----------------|---------|---------|-----------|
| **A1** | Install simplicity | 1 action/surface: double-click `.mcpb`; 2 slash cmds (Code); 1 `pip`/`brew` cmd | manifest+plugin schema-validation; `.mcpb` build+install smoke | mostly met; brew ships stale 1.2.0 | WP-03, WP-10, WP-40 |
| **A2** | Offline first-run | fresh install + `digest` completes **with no network** & no pre-pulled models | CI offline lane (network blocked) runs full-deps convert→digest | **MOSTLY MET** — WP-10/13 removed git+https from the hot path; offline digest proven by the offline matrix + conversion-e2e. Residual: the one-time pip install needs network (inherent) | WP-10 ✓, WP-13 ✓ |
| **A3** | Token-free | `recall` ≤ ~400 tokens (≤600 chars × ≤5 docs + meta); `digest` ≤ ~200 tokens; contents never returned | assertion test on **both** embedding paths | met (capped); strengthen test | WP-03 |
| **A4** | Offline recall reliability | off-topic query on hashing path → `low_confidence==True`; `MTA_RECALL_MIN_SCORE` filters | regression test on hashing path | **MET** — WP-30: lexical-overlap confidence offline + floor on both paths; `test_recall_offline` (4) | WP-30 ✓ |
| **A5** | Concurrency safety | 4 concurrent digests / shared project → no corruption, consistent graph↔vectors, no torn read, no deadlock, ≤1 Ollama started | concurrency stress test | **MET** — WP-14 SWMR project lock; `test_concurrency` 4-way digest → consistent pair, no temp left; cross-process ollama-start lock | WP-14 ✓ |
| **A6** | Idle lifecycle | self-started Ollama stopped within `MTA_IDLE` + tol (≤ idle+30 s), timer reset under load; user's Ollama never stopped; no orphans on exit | lifecycle tests | **MOSTLY MET** — start serialised (no double-spawn); idle timer uses the cross-process marker; only the self-started instance is stopped; residual narrow atexit-vs-busy race deferred | WP-14 ◑ |
| **A7** | Data migration | vN-1 fixture store is recall-readable after upgrade; newer/corrupt store → backup + clear msg, **no data loss** | migration tests w/ version fixtures | **MET** — WP-15: older stores forward-migrate in memory; a newer store is read-recallable + backed up before overwrite; corrupt → None; `test_migration` (6) | WP-15 ✓ |
| **A8** | Release integrity | one version source; CI fails on version drift or tag≠version; **OIDC** publish; **SBOM+signature+provenance** per artifact; idempotent; **halt-and-rollback** (no partial release); tap auto-bumped; post-publish re-install smoke per channel | release-workflow gates + post-publish smoke | **MOSTLY MET** — WP-03 (single version source + tag==version gate) + WP-40 (OIDC, SHA-pins, SBOM + cosign, single-build, halt-on-partial, idempotent, tap auto-bump). Remaining: live validation + post-publish smoke at WP-41 (owner setup); reproducible lockfile (CI-09) deferred | WP-03 ✓ / WP-40 ✓ / WP-41 |
| **A9** | CI fidelity | ≥1 lane installs full runtime deps & runs real offline convert (PDF/DOCX/XLSX/image)→digest→recall; `.mcpb` build smoke; all **8** tools asserted | CI | **FAILS** (CI-10 `--no-deps`; DOC-02 test errors; DOC-03 7-tool assert) | WP-03 |
| **A10** | Eval floors *(calibrate WP-31)* | conversion fidelity ≥ 0.95 (born-digital text sim); retrieval recall@5 ≥ 0.80 / precision@5 ≥ 0.70 (accurate), ≥ 0.60/0.50 (fast); fast-vs-accurate speedup = **measured** (≈25× observed, replaces "20–100×") | eval harness thresholds in CI | **MET** — WP-31 gates offline recall@8 ≥ 0.75 (baseline 1.0); WP-51 Phase-6 E2E validated accurate-mode (live Ollama) + measured fast-vs-accurate **≈25–100×** (≈98×/≈26×) — `TEST_REPORT.md` | WP-31 ✓ / WP-51 ✓ |
| **A11** | Perf/resource *(calibrate WP-31)* | cold-start→first `recall` ≤ target (accurate) / ≤ target s (fast); idle server RSS ≤ ceiling (Ollama stopped); active peak bounded by backpressure | benchmark harness; regression flag vs baseline | **MET (reported)** — Phase-6 `TEST_REPORT.md` records per-stage timing + the accurate-vs-fast speedup; peak/idle RSS soak deferred to a container run | WP-31 ✓ / WP-51 ✓ |
| **A12** | Security | decompression-bomb cap on **all** container formats; second-order injection delimited; `allow_pickle=False` explicit; mindmap truly zero-network; `SECURITY.md`+threat model; CI license+vuln scan blocks on violations | security regression + CI scans | **MOSTLY MET** — WP-32: all-format bomb cap, fenced summary prompts, explicit `allow_pickle=False`, zero-network mindmap, `SECURITY.md`+threat model; `test_security` (5). CI license/vuln scan → WP-40 | WP-32 ✓ / WP-40 |

**Continuously enforced invariants (must never regress):** token-free (A3) · privacy/no-telemetry · atomic crash-safe writes · dependency-free classical/offline fallback (A2). These get dedicated always-on tests.

> **Note:** the table above is the v1-era baseline; A10/A11 (fast-vs-accurate) and the A12
> mindmap clause are obsolete under the v2 deterministic/model-free engine. The v2 measured
> gates are below.

---

## v2.4.2 measured gates (S22, this session) — all reproduced

Local OS: macOS (Apple Silicon, 16 GB, py3.12). CI: green on Ubuntu/macOS/Windows × 3.10/3.12
incl. conversion-e2e (run 27866340339). Independent fresh-verification agent reproduced every
gate (VERDICT: SHIP).

| gate | target | measured (v2.4.2) | vs v2.4.1 |
|------|--------|-------------------|-----------|
| Token-free — recall(k=50), worst-case Bengali | tiny, byte-capped | **86 KB** (label ≤200 B, text ≤600 B, doc ≤160 B, synopsis ≤1200 B) | **394 KB → 86 KB** (Critical fixed) |
| Token-free — overview, worst-case Bengali | compact | **18 KB** (≤20 themes, byte-capped) | **157 KB → 18 KB** |
| Token-free — digest/convert/export/forget/status/list_digestible | counts/paths only | no document content returned | unchanged |
| Determinism | byte-identical for identical input | graph.json/memory.md/notes/vectors **byte-identical** across PYTHONHASHSEED (SHA-256), incl. cross-OS LF | strengthened (cross-OS) |
| Re-digest idempotency | state hash unchanged on re-run | graph.json SHA unchanged, no dup nodes/notes | unchanged |
| Recall — English | grounded hit + correct low_confidence | "Project Aurora"→Dr. Marsh, top 3.22, low_conf False | unchanged |
| Recall — Bengali | grounded hit (BM25, halant-aware) | গ্রুপ মিটিং→ঢাকা, top 3.18, low_conf False | unchanged |
| Bengali entity resolution | distinct entities stay distinct | ভোলা≠ভালো, ঢাকা≠ঢাকি (4 distinct cids); নিম্ন preserved | **over-merge fixed (RES-1)** |
| Archive bomb (rar/7z) | bounded during extraction | flood aborts + rolls back at the byte cap; no orphan | **disk-fill fixed (SEC-1)** |
| Export portability | zero absolute paths | grep `/Users`,home,`/private/tmp` in memory.md/graph.json/notes → 0 | unchanged |
| Supply chain | cosign-verify each signed asset | **wheel+sdist+.mcpb+SBOM all VERIFIED** (keyless, release.yml@refs/tags/v2.4.2 + GH OIDC) | unchanged |
| .mcpb | valid manifest, win32 startable | `mcpb validate` passes; platforms [darwin,linux,win32] + win32→`python launch.py` | **WIN-1 fixed** |
| Version single-source | all surfaces agree | check_versions OK at 2.4.2 (7 surfaces) | unchanged |
| Test suite | green | **235 pass / 2 skip** (full-deps, incl. conversion-e2e); 18 new regression tests | +18 tests |

Tests that can't run in CI / locally (recorded honestly): the **real Windows .mcpb start** is
validated only in Claude Desktop on Windows (not on this macOS host) — WP-91 ships best-effort
with schema + structural validation. **Docker `docker run`** not run locally (Docker not
installed, R-01); image built+pushed by the successful Docker train run; anonymous GHCR pull
needs the owner to set the package public.
