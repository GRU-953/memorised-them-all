# AUDIT — Phase-1 deep audit of `memorised-them-all`

**Date:** 2026-06-02 (Session 01) · **Repo:** GRU-953/memorised-them-all @ `main` (v1.3.3)
**Method:** 9 independent fresh-eyes subagents (one per dimension), each reading only its slice and verifying external specs live (MCPB 0.3, Claude Code plugin/marketplace, MCP SDK); orchestrator synthesis + direct external-publishing verification via `gh`/`curl`/live `memory_status`. See DECISIONS ADR-003.

## 1. Executive summary

The project is **genuinely good and unusually honest** for a 2-day-old solo effort. Of 110 findings, **49 are IMPLEMENTED confirmations** of real strengths, and the headline promises survive scrutiny:

- **Token-free invariant holds** — `digest` returns metadata only; `recall` is hard-capped (≤600 chars/hit, ≤5 docs, k∈[1,50]); document bodies never cross back to the model (traced field-by-field: MCP-02/03, RECALL-01, DOC-05).
- **Offline/classical fallback is real and was *empirically proven*** — a full digest completed with `MTA_NO_OLLAMA=1` and `rapidfuzz`/`markitdown`/`PIL` absent (9 entities, 30 relations, 2 communities, all artifacts written): PIPE-01, DOC-07.
- **Crash-safe atomic writes** (temp→fsync→`os.replace`), **path-traversal-safe** outputs, **argv-only** subprocesses, **prompt-injection delimiting** (per-chunk), **Unicode-aware** resolution, **MLX/CUDA Whisper**, and a **self-contained offline mind map** (real 373 KB Cytoscape inlined) all check out.
- **Packaging validates against the *current* schemas** — MCPB 0.3, Claude Code `plugin.json`/`marketplace.json`, `.mcp.json` (verified live, Dec-2025/2026 refs).

**The gaps — 2 Critical, 12 High, 28 Medium — do not break token-free or cause data loss.** They are concurrency-safety, supply-chain/release-train, offline-reliability, and capability-completeness gaps. The most damaging *pattern* is that **several headline README phrases are contradicted on the very offline path the README promotes**: first-run isn't truly offline (PKG-03), and recall's `low_confidence`/`MTA_RECALL_MIN_SCORE` reliability signal **silently no-ops without Ollama** (DOC-01). **35 findings are quick wins.**

## 2. Severity census

| Critical | High | Medium | Low | Info | total |
|--:|--:|--:|--:|--:|--:|
| 2 | 12 | 28 | 24 | 44 | **110** |

**By status:** IMPLEMENTED 49 · PARTIAL 44 · MISSING 11 · BROKEN 3 · UNVERIFIED 3 · **quick wins: 35**

## 3. Top gaps (Critical + High) → owning Work Package

| id | sev | status | finding | → WP |
|----|-----|--------|---------|------|
| **PKG-03** | **Critical** | BROKEN | First-run digest not offline: `install.sh`/`mta-launcher.sh` pip-install MarkItDown from a live `git+https` URL on the hot path (unpinned) | WP-10 + WP-13 |
| **LIFE-01** | **Critical** | MISSING | No cross-process locking anywhere — concurrent clients sharing one `MTA_HOME`/project race on shared graph/vectors/markdown files | WP-14 |
| CI-02 | High | PARTIAL | PyPI publish uses a long-lived API token, not OIDC/Trusted Publishing | WP-40 |
| CI-05 | High | PARTIAL | No concurrency guard/idempotency/rollback — PyPI failure after GitHub Release = partial release | WP-40 |
| CI-10 | High | PARTIAL | CI installs a dep subset with `--no-deps` — the real conversion path (markitdown/tesseract/whisper) is never exercised → "green CI" is partly hollow | WP-03 |
| DEP-01 | High | MISSING | No integrity verification (hash/signature) before installing upgrades | WP-13 |
| DOC-01 | High | PARTIAL | `low_confidence`/`MTA_RECALL_MIN_SCORE` only work with Ollama embeddings; on the offline/hashing path `low_confidence` is hardcoded `False` and the floor is ignored | WP-30 |
| DOC-02 | High | BROKEN | `test_ocr_stdin_pipe` imports PIL before guarding → **errors (not skips)** under the CI dep set; "green CI" is fragile | WP-03 |
| LIFE-02 | High | PARTIAL | Idle watchdog decoupled from cross-process activity — can kill a busy worker, or fail to stop at all | WP-14 |
| LIFE-03 | High | PARTIAL | Schema is version-*guarded* but has no migration/backup/rollback; a future-version store is silently treated as "no memory" — contradicts "old memories stay read-recallable" | WP-15 |
| PIPE-03 | High | PARTIAL | Ollama installed-but-unreachable (and `MTA_NO_OLLAMA` unset) → repeated 20 s stalls across a digest | WP-14 |
| PKG-01 | High | BROKEN | `CITATION.cff` stuck at 1.3.2 while all 5 other version strings are 1.3.3 | WP-03 |
| SEC-01 | High | PARTIAL | Decompression-bomb cap is bypassed for `.docx/.xlsx/.pptx/.epub` (only literal `.zip` is checked) — yet those are all ZIP containers MarkItDown decompresses | WP-32 |
| SEC-04 | High | IMPLEMENTED | *By design*, the daily auto-update pip-installs **unpinned** code from MarkItDown git `main` — supply-chain exposure | WP-13 |

## 4. Cross-cutting themes

- **A — Unpinned, offline-breaking auto-update** (PKG-03, SEC-04, DEP-01/02/03): the git-`main` MarkItDown install is the common thread; it breaks offline-first, reproducibility, and supply-chain integrity at once. *Fix once, in R4/R1.*
- **B — Concurrency & idle-timer correctness** (LIFE-01 Crit, LIFE-02, PIPE-03, DEP-08/09): no cross-process lock; the activity marker and watchdog are decoupled across processes. *R5.*
- **C — Schema migration absent** (LIFE-03): versioned but no migrate/backup/rollback. *R6.*
- **D — Offline recall reliability** (DOC-01, RECALL-02/03, PIPE-06): the reliability signal and fact quality degrade silently without models — and this is the path the README promotes. *Quality, v1.*
- **E — Release-train & supply chain** (CI-02..09/11, SEC-05/06/07, R-02 stale tap): no OIDC, no SHA-pins, no SBOM/signing/lockfile, no tap automation, double-build, no rollback. *Phase 5.*
- **F — CI doesn't exercise real conversion** (CI-10, DOC-02, CI-12, DOC-03): the green badge tests only the offline core; conversion deps, the `.mcpb` build, and `forget` are untested. *v1.*
- **G — Auto-config/dependency capability gaps** (DEP-04/05/06/07/10): no preflight scanner, no profiles, config not persisted, no GPU/LM-Studio detection, bash-only install. *R2/R3.*
- **H — Security quick wins** (SEC-01/02/03/10/11): container-format bomb cap, second-order injection in summary prompts, explicit `allow_pickle=False`, mindmap CDN fallback, GPL-into-MIT-venv note. *v1.*
- **I — Version single-source** (PKG-01/02, CI-07/08, DOC-22): six hand-maintained copies; the drift already happened once. *v1.*
- **J — Doc-accuracy nits** (DOC-18/19 unbenchmarked "20–100×"/"163 langs"; SEC-10 "zero network"; DOC-21 stale command sigs). *v1.*

## 5. Docs-vs-reality reconciliation (incl. live external verification)

**External claims (resolves DOC-22 + the runtime half of MCP-11), verified directly this session:**
- ✅ **PyPI** live at 1.3.3 (`pip install` works) — but the PyPI version set **omits 1.0.0 & 1.3.0** vs git tags (R-07).
- ⚠️ **Homebrew tap exists** (`homebrew-memorised-them-all`, `Formula/mta.rb`) but the **formula is pinned to v1.2.0** — `brew install` ships a 2-release-old build, and `release.yml` never bumps it (R-02, CI-11).
- ✅ **Latest GitHub Release carries the `.mcpb`** + wheel + sdist + install.sh; **CI is green on `main`**.
- ✅ **Live `memory_status`** confirms platform detection (arm64/4 P-cores/16 GB/MLX), full stack (Ollama + 3 models + Tesseract + ffmpeg + MarkItDown 0.1.6), fast-mode ≈ 25× on a 12-file corpus, and **metadata-only output**.

**Confirmed-true README claims (15/19):** token-free metadata results · atomic/crash-safe writes · classical/offline fallback · Unicode-aware resolution · per-file size + decompression-bomb caps (for `.zip`) · prompt-injection delimiting (per-chunk) · argv-only subprocesses · version-stamped, path-free `graph.json` · reused-Ollama-left-alone · MLX/CUDA Whisper · Cytoscape inlined / offline mind map · 8 MCP tools with matching signatures.

**Contradicted / partial README claims:** PKG-03 (offline first-run) · DOC-01 (`low_confidence` offline) · SEC-10 ("zero network" — the mindmap *is* inlined and offline at runtime, but the template keeps an unpkg CDN *fallback* line that should be removed to make the claim literally true) · SEC-01 (bomb cap only covers `.zip`) · DOC-18/19 (the "20–100×" and "163 languages" numbers are unbenchmarked/unsubstantiated — to be measured by the eval harness, WP-31).

## 6. Note on this document
- The MCP subagent's `summary` field returned a corrupted internal note; it has been replaced below with a summary derived from the (intact) MCP findings MCP-01..11.
- Sections below (master table + full per-dimension detail with claim/reality/evidence/recommendation for all 110 findings) are auto-generated from the structured audit result.

---


## Findings — master table (severity-ranked)
`QW` = quick win (small, low-risk fix). Status: IMPLEMENTED / PARTIAL / MISSING / BROKEN / UNVERIFIED.

| id | sev | status | QW | dimension | title |
|----|-----|--------|:--:|-----------|-------|
| LIFE-01 | Critical | MISSING |  | Lifecycle | No cross-process locking anywhere — concurrent clients sharing one MTA_HOME/project race on shared files |
| PKG-03 | Critical | BROKEN |  | Packaging | First-run digest is NOT offline-capable: MarkItDown is pip-installed from a live git+https URL |
| CI-02 | High | PARTIAL | ✓ | CI | PyPI publish uses a long-lived API token, not OIDC/Trusted Publishing |
| CI-05 | High | PARTIAL |  | CI | No concurrency guard, idempotency, or rollback — partial-release risk |
| CI-10 | High | PARTIAL |  | CI | CI installs only a hand-picked dep subset with --no-deps — real conversion path untested |
| DEP-01 | High | MISSING |  | Dependency model,  | No integrity verification (hash/signature) before installing upgrades |
| DOC-01 | High | PARTIAL |  | Docs-vs-reality cr | recall low_confidence / MTA_RECALL_MIN_SCORE do not work on the offline (hashing) path the README promotes |
| DOC-02 | High | BROKEN | ✓ | Docs-vs-reality cr | test_ocr_stdin_pipe imports PIL before guarding on it — errors (not skips) under the documented CI dependency set |
| LIFE-02 | High | PARTIAL |  | Lifecycle | Idle watchdog is decoupled from cross-process activity — can kill a busy worker or fail to stop at all |
| LIFE-03 | High | PARTIAL |  | Lifecycle | Schema is version-GUARDED but has no migration, backup, or rollback — old/future stores are not kept read-recallable |
| PIPE-03 | High | PARTIAL | ✓ | Conversion to dige | Ollama installed-but-unreachable (and MTA_NO_OLLAMA unset) causes repeated 20s stalls across the digest |
| PKG-01 | High | BROKEN | ✓ | Packaging | CITATION.cff version drift: stuck at 1.3.2 while everything else is 1.3.3 |
| SEC-01 | High | PARTIAL | ✓ | Security posture | Decompression-bomb cap bypassed for .docx/.xlsx/.pptx/.epub (only literal .zip is checked) |
| SEC-04 | High | IMPLEMENTED |  | Security posture | Daily auto-update pip-installs unpinned code from MarkItDown git main branch |
| CI-03 | Medium | PARTIAL | ✓ | CI | GitHub Actions are floating-tag pinned (@v4/@v5/@v2), not SHA-pinned |
| CI-04 | Medium | MISSING |  | CI | No SBOM, signing, or build provenance/attestation anywhere |
| CI-06 | Medium | PARTIAL | ✓ | CI | Release builds dist twice independently — non-reproducible / drift risk |
| CI-07 | Medium | PARTIAL | ✓ | CI | Version hand-duplicated in 3 files; no single source, no dynamic derivation |
| CI-08 | Medium | MISSING | ✓ | CI | Release does not validate the git tag against the package version |
| CI-09 | Medium | MISSING |  | CI | No committed lockfile — builds float on dependency ranges (not reproducible) |
| CI-11 | Medium | MISSING |  | CI | Homebrew tap is a documented install/publish target but unautomated in the pipeline |
| DEP-02 | Medium | PARTIAL |  | Dependency model,  | "Self-update" of the extension/plugin is report-only — it is never applied |
| DEP-03 | Medium | MISSING |  | Dependency model,  | No atomic upgrade or rollback for dependency updates |
| DEP-04 | Medium | MISSING | ✓ | Dependency model,  | No dependency preflight scanner with detected-vs-required versions |
| DEP-08 | Medium | PARTIAL |  | Dependency model,  | Ollama 'reused vs self-started' cannot survive across server processes; reuse flag is per-instance only |
| DEP-10 | Medium | PARTIAL |  | Dependency model,  | System-package install is bash-only with no Windows path; no --dry-run; relies on non-interactive sudo |
| DOC-03 | Medium | PARTIAL | ✓ | Docs-vs-reality cr | mcp_stdio_check.py asserts only 7 tools (omits forget) and its docstring says "seven tools"; server actually exposes 8 |
| DOC-17 | Medium | IMPLEMENTED |  | Docs-vs-reality cr | Auto-installing stack (Ollama/Tesseract/ffmpeg/MarkItDown/models) and .mcpb first-launch bootstrap |
| LIFE-07 | Medium | PARTIAL | ✓ | Lifecycle | Clean shutdown via atexit + whole process-tree teardown (psutil) prevents orphaned Ollama runner |
| LIFE-08 | Medium | PARTIAL |  | Lifecycle | Auto-updater can launch a background pip install on the request path; throttle stamp is a non-atomic cross-process gate |
| MCP-06 | Medium | PARTIAL | ✓ | MCP server surface | MCP SDK pinned only by a low lower bound, no upper cap |
| MCP-07 | Medium | PARTIAL | ✓ | MCP server surface | Tool handlers lack input validation; can raise unhandled exceptions across the boundary |
| MCP-08 | Medium | PARTIAL | ✓ | MCP server surface | Stale seven-tools docstrings and CI assertion undercount the real eight; forget untested |
| PIPE-05 | Medium | PARTIAL |  | Conversion to dige | rapidfuzz treated as optional though it is a hard dependency; without it entity resolution silently degrades to exact-match |
| PIPE-06 | Medium | PARTIAL | ✓ | Conversion to dige | Classical extractor fragments entities and produces newline-laden / truncated facts |
| PKG-02 | Medium | PARTIAL |  | Packaging | No single canonical version source — six hand-maintained copies |
| PKG-04 | Medium | PARTIAL | ✓ | Packaging | .mcpb zip-fallback omits launch.py and scripts/ (only `mcpb pack` bundles them) |
| RECALL-02 | Medium | PARTIAL |  | Recall, render | Recall hit text can contain verbatim source sentences (classical-mode facts) |
| SEC-02 | Medium | PARTIAL | ✓ | Security posture | Summary/synopsis LLM prompts feed attacker-influenced text undelimited (second-order prompt injection) |
| SEC-05 | Medium | MISSING |  | Security posture | No dependency pinning/hashes/lockfile — entirely floating >= constraints |
| SEC-06 | Medium | PARTIAL | ✓ | Security posture | GitHub Actions pinned to mutable tags, not commit SHAs |
| SEC-07 | Medium | PARTIAL |  | Security posture | PyPI publish uses long-lived API token, not OIDC Trusted Publishing |
| CI-12 | Low | PARTIAL | ✓ | CI | .mcpb bundle is built only in release, never smoke-tested in CI |
| DEP-05 | Low | MISSING | ✓ | Dependency model,  | No named configuration profiles (laptop/workstation/server/offline) |
| DEP-06 | Low | MISSING | ✓ | Dependency model,  | Resolved configuration is never persisted to disk |
| DEP-07 | Low | PARTIAL | ✓ | Dependency model,  | GPU/CUDA not detected in platform layer; summary omits GPU; no LM Studio detection |
| DEP-09 | Low | PARTIAL | ✓ | Dependency model,  | Daily-throttle stamp is racy/non-atomic across concurrent launches |
| DOC-04 | Low | PARTIAL | ✓ | Docs-vs-reality cr | allow_pickle=False is claimed as hardening but never set explicitly in code (relies on NumPy default) |
| DOC-16 | Low | IMPLEMENTED |  | Docs-vs-reality cr | Auto-updating: pulls latest MarkItDown from upstream, throttled once-a-day |
| DOC-18 | Low | UNVERIFIED |  | Docs-vs-reality cr | Fast mode "20-100x faster" speedup figure is unbenchmarked marketing |
| DOC-19 | Low | UNVERIFIED |  | Docs-vs-reality cr | 163 OCR languages claim is unsubstantiated by code and depends on external Tesseract packs |
| DOC-20 | Low | PARTIAL |  | Docs-vs-reality cr | CHANGELOG is Keep-a-Changelog/SemVer compliant but all 8 releases are dated within ~1 day |
| DOC-21 | Low | PARTIAL | ✓ | Docs-vs-reality cr | Commands/skill tool signatures lag the README (no fast param; missing forget command) |
| MCP-09 | Low | PARTIAL | ✓ | MCP server surface | CLI subcommands match the documented list; only cosmetic field drift |
| MCP-10 | Low | PARTIAL |  | MCP server surface | Auto-update side effect fires inside _cfg on most tool calls (documented, opt-out) |
| PIPE-04 | Low | PARTIAL | ✓ | Conversion to dige | stats.mode reports "accurate" even when no LLM ran (classical+hash fallback) |
| PIPE-08 | Low | IMPLEMENTED |  | Conversion to dige | Memory bounds on large corpora: per-file size cap, zip-bomb guard, chunk cap, fact cap — but full corpus is loaded into memory |
| PIPE-10 | Low | IMPLEMENTED |  | Conversion to dige | Audio files have no offline fallback content path — correctly reported as failed/empty, never crash |
| PKG-05 | Low | PARTIAL | ✓ | Packaging | version pinned in BOTH plugin.json and the marketplace entry (docs warn against this) |
| PKG-07 | Low | IMPLEMENTED |  | Packaging | Runtime shell scripts use `set -uo pipefail` without `-e` (no fail-fast) |
| PKG-09 | Low | PARTIAL | ✓ | Packaging | MTA_WORKERS exposed in manifest.json but absent from plugin .mcp.json |
| RECALL-03 | Low | PARTIAL | ✓ | Recall, render | top_score reported even when MTA_RECALL_MIN_SCORE drops all hits (mismatch with returned hits) |
| RECALL-10 | Low | IMPLEMENTED |  | Recall, render | low_confidence semantics: flagged only on the real-embedding path, by design |
| SEC-03 | Low | PARTIAL | ✓ | Security posture | allow_pickle=False claimed but absent from the only np.load call |
| SEC-10 | Low | PARTIAL | ✓ | Security posture | Mind-map 'zero network' claim contradicted by unpkg.com CDN fallback |
| SEC-11 | Low | PARTIAL |  | Security posture | GPL (leidenalg/igraph) auto-installed into the MIT-licensed package's venv |
| CI-01 | Info | IMPLEMENTED |  | CI | CI OS/Python matrix matches README claim exactly |
| CI-13 | Info | IMPLEMENTED |  | CI | CI build job validates wheel/sdist with twine check and uploads artifact |
| CI-14 | Info | IMPLEMENTED |  | CI | least-privilege permissions and offline-by-construction CI |
| DOC-05 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Token-free contract: digest returns metadata only; recall slice hard-capped; contents never returned |
| DOC-06 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Atomic / crash-safe writes (temp + fsync + os.replace) for graph.json and vector store |
| DOC-07 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Classical/offline fallback guarantees a digest succeeds with no models / no network |
| DOC-08 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Unicode-aware entity resolution (Bengali/CJK/Cyrillic/accented Latin) — distinct entities stay distinct |
| DOC-09 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Decompression-bomb caps + per-file size caps (incl. nested-archive rejection) |
| DOC-10 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Prompt-injection data-delimiting in the extraction prompt |
| DOC-11 | Info | IMPLEMENTED |  | Docs-vs-reality cr | argv-only subprocesses (no curl | sh) |
| DOC-12 | Info | IMPLEMENTED |  | Docs-vs-reality cr | graph.json version-stamped and free of absolute paths (portable) |
| DOC-13 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Reused Ollama left alone; only the self-started instance is stopped on idle |
| DOC-14 | Info | IMPLEMENTED |  | Docs-vs-reality cr | GPU Whisper via MLX (Apple) / CUDA Whisper (Linux/Windows) with CPU fallback |
| DOC-15 | Info | IMPLEMENTED |  | Docs-vs-reality cr | Mindmap: Cytoscape inlined, zero network |
| DOC-22 | Info | UNVERIFIED |  | Docs-vs-reality cr | Published-state claims (PyPI, Homebrew tap, badges, green CI, release .mcpb asset) |
| LIFE-04 | Info | IMPLEMENTED |  | Lifecycle | Atomic durable writes for graph.json and vectors.npz (temp + fsync + os.replace) |
| LIFE-05 | Info | IMPLEMENTED | ✓ | Lifecycle | npz load relies on numpy's safe allow_pickle=False default; no untrusted pickle path |
| LIFE-06 | Info | IMPLEMENTED |  | Lifecycle | Stops only the Ollama this process started; user's own/brew Ollama is detected and never touched |
| LIFE-09 | Info | IMPLEMENTED |  | Lifecycle | Per-call Config is freshly constructed, so with_project() mutation does not race across tool calls |
| MCP-01 | Info | IMPLEMENTED |  | MCP server surface | All 8 claimed tools registered with matching signatures |
| MCP-02 | Info | IMPLEMENTED |  | MCP server surface | Token-free invariant holds: recall returns only hard-capped slices |
| MCP-03 | Info | IMPLEMENTED |  | MCP server surface | digest returns only metadata; document bodies never cross back |
| MCP-04 | Info | IMPLEMENTED |  | MCP server surface | Prompt-injection hardening bounds local-LLM output into memory |
| MCP-05 | Info | IMPLEMENTED |  | MCP server surface | Transport is stdio-only with no HTTP/SSE |
| MCP-11 | Info | IMPLEMENTED |  | MCP server surface | Read-only tools memory_status and list_digestible return bounded metadata-only shapes; status runtime UNVERIFIED |
| PIPE-01 | Info | IMPLEMENTED |  | Conversion to dige | Offline digest invariant holds: full pipeline completes with no models and no network |
| PIPE-02 | Info | IMPLEMENTED |  | Conversion to dige | Per-file conversion failures are isolated; one bad file does not abort the batch |
| PIPE-07 | Info | IMPLEMENTED |  | Conversion to dige | Fast mode is correctly deterministic, builds the graph, and preserves semantic recall |
| PIPE-09 | Info | IMPLEMENTED |  | Conversion to dige | Conversion process-pool parallelism is correct (spawn-safe payload, deterministic output names, main-thread fallback) |
| PIPE-11 | Info | IMPLEMENTED |  | Conversion to dige | Atomic persistence of graph.json and vectors prevents corruption on crash mid-materialise |
| PIPE-12 | Info | IMPLEMENTED |  | Conversion to dige | Segmentation hard-splits oversize sentences and carries provenance, avoiding silent tail loss |
| PKG-06 | Info | PARTIAL | ✓ | Packaging | manifest.json missing optional $schema field for editor validation |
| PKG-08 | Info | IMPLEMENTED |  | Packaging | launch.py / launch.sh / install.sh / scripts ship in sdist but NOT in the wheel (by design, but creates two install personas) |
| RECALL-01 | Info | IMPLEMENTED |  | Recall, render | Recall returns only a hard-capped slice (per-hit text and doc caps + k clamp) |
| RECALL-04 | Info | IMPLEMENTED |  | Recall, render | mindmap.html is genuinely self-contained / offline (real Cytoscape inlined, CDN only a dev fallback) |
| RECALL-05 | Info | IMPLEMENTED |  | Recall, render | XSS/script-breakout hardening in the inlined mindmap data block |
| RECALL-06 | Info | IMPLEMENTED |  | Recall, render | render emits memory.md + per-document notes + graph.json + mindmap.html |
| RECALL-07 | Info | IMPLEMENTED |  | Recall, render | graph.json is version-stamped and contains no absolute paths (portability) |
| RECALL-08 | Info | IMPLEMENTED |  | Recall, render | export_memory bundles memory.md, graph.json, mindmap.html, per-doc notes AND the vector store |
| RECALL-09 | Info | IMPLEMENTED |  | Recall, render | Query is embedded locally with the same model/prefix as digest; dimension-mismatch degrades to lexical |
| SEC-08 | Info | IMPLEMENTED |  | Security posture | Output filenames are path-safe and collision-free (path traversal not possible) |
| SEC-09 | Info | IMPLEMENTED |  | Security posture | All subprocess invocations are argv-lists; no shell=True, no curl|sh |
| SEC-12 | Info | IMPLEMENTED |  | Security posture | User-editable graph.json/meta loaded as untrusted; numeric DoS not bounded but no code-exec |
| SEC-13 | Info | IMPLEMENTED |  | Security posture | Project name slugified before use as a directory — forget()/paths are traversal-safe |

## Findings — full detail by dimension

### Packaging & distribution config

The packaging is unusually well-built for a solo project: pyproject.toml, manifest.json (MCPB 0.3), plugin.json + marketplace.json (Claude Code), and .mcp.json all validate against the CURRENT published schemas (verified via anthropics/mcpb MANIFEST.md and code.claude.com plugin/marketplace reference, Dec 2025/2026), the `mta` console script resolves to a real callable, and requirements.txt is byte-identical to pyproject's core dependencies. The two real defects are (1) a single-source-of-truth failure — CITATION.cff is stranded at v1.3.2 while all five other version strings agree at v1.3.3, and there is no canonical version source or sync mechanism; and (2) a reproducibility/offline concern — install.sh and the Homebrew launcher unconditionally `pip install` MarkItDown from a live git+https GitHub URL on first run (and again when auto_update='on'), so a first-ever digest is NOT offline-capable and is not pinned. Secondary issues: the build_mcpb.sh zip fallback omits launch.py and scripts/ (only the official `mcpb pack` path bundles them), both plugin.json and the marketplace entry pin `version` (the docs explicitly warn against this dual-pin), and all four runtime shell scripts drop `set -e` (use `set -uo pipefail`), trading fail-fast safety for resilience. No token-free leak in the packaging layer itself, but the runtime network fetch undercuts the "100% local / works offline" promise on the very first run.

**Strengths:**

- mta console script is correctly declared (pyproject.toml:59 `mta = "mta.cli:main"`) and resolves to a real callable: mta/cli.py:28 `def main(...)`, with a `__main__` guard at cli.py:95.
- manifest.json validates against the CURRENT MCPB spec (manifest_version 0.3 is current per anthropics/mcpb MANIFEST.md, updated 2025-12-02): all required top-level fields present (manifest_version, name, version, description, author.name, server), `server.type:"binary"` is a valid type, mcp_config uses valid `command`/`args`/`env`, ${__dirname} and ${user_config.X} substitutions are spec-supported, and the compatibility block (platforms darwin/linux + runtimes.python) matches the schema (manifest.json:1-101).
- user_config in manifest.json is fully spec-conformant: every entry uses valid type values (directory/string/number) with title/description/required/default, and number fields correctly use min/max (manifest.json:49-97).
- plugin.json is schema-valid: `mcpServers`, `commands`, `skills` accept path strings per the Claude Code plugin reference, and all three targets exist on disk (./.mcp.json, ./commands/, ./skills/) (plugin.json:14-16).
- .mcp.json is a correct plugin MCP config using the spec-blessed ${CLAUDE_PLUGIN_ROOT} variable to locate launch.sh (.mcp.json:5).
- marketplace.json conforms to the CURRENT marketplace schema: required name/owner/plugins present, owner.name present, entry has required name+source, `metadata.pluginRoot` and a relative `source:"./"` are both documented-valid fields (marketplace.json:1-24).
- requirements.txt and pyproject.toml [project.dependencies] are byte-identical across all 12 core packages, and every dependency is lower-bounded (e.g. mcp>=1.2, numpy>=1.26) — no unpinned/floating core deps (requirements.txt:5-21 vs pyproject.toml:30-43).
- install.sh and launch.py/launch.sh are argv-only with NO `curl|sh` anti-pattern; even the Ollama bootstrap on apt/dnf deliberately downloads-to-tempfile-then-executes with an in-code comment explaining why (install.sh:75-77, install.sh:83-85).
- launch.py is a genuine stdlib-only cross-platform launcher that correctly handles the Windows Scripts/ vs bin/ venv layout and avoids os.execve on Windows (launch.py:20-56).
- hatchling build-backend is intentionally pinned <1.27 with an in-file comment explaining the Metadata-Version 2.5/twine incompatibility — a thoughtful, documented release-engineering decision (pyproject.toml:2-4).
- The mlx optional-dependency uses a correct PEP 508 environment marker so it only installs on Apple silicon (pyproject.toml:49).

#### PKG-03 — First-run digest is NOT offline-capable: MarkItDown is pip-installed from a live git+https URL
*Critical · BROKEN*

- **Claim/expected:** Project markets itself as "100% local", "entirely on your machine", "works offline" with "~0 Claude context tokens".
- **Reality:** install.sh:42-44 unconditionally runs `pip install -U "markitdown[...] @ git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown"` on first launch, and scripts/mta-launcher.sh:24-26 does the same in the background. launch.sh:16-19 calls install.sh on first run. The default auto_update='on' (.mcp.json:14, manifest.json:95) means this network fetch also recurs. So the very first `digest` requires reaching GitHub; on an air-gapped/offline machine the bootstrap step fails (it is wrapped in `|| log ...`, so it degrades to the PyPI MarkItDown that requirements.txt already installed, but the advertised "latest upstream" behavior is impossible offline and the install is non-deterministic/un-pinned).
- **Evidence:** install.sh:40-44; scripts/mta-launcher.sh:23-26; launch.sh:16-19; .mcp.json:14 (MTA_AUTO_UPDATE on); manifest.json:92-96 (auto_update default "on"); requirements.txt:12 / pyproject.toml:36 (PyPI markitdown>=0.1.6 is the pinned fallback)
- **Recommendation:** Don't fetch from git on the install/launch hot path. Rely on the PyPI `markitdown[...]>=0.1.6` already in requirements.txt for the offline-correct baseline, and gate the git-upstream upgrade behind an explicit `mta update` / auto_update='on' that is clearly documented as requiring network. At minimum, pin the git fetch to a commit/tag for reproducibility, and stop running it when MTA_AUTO_UPDATE is off.

#### PKG-01 — CITATION.cff version drift: stuck at 1.3.2 while everything else is 1.3.3
*High · BROKEN · quick-win*

- **Claim/expected:** README/release presents this as v1.3.3; a citation file should reflect the released version.
- **Reality:** Five of six version strings agree at 1.3.3 (mta/__init__.py:6, pyproject.toml:9, manifest.json:5, .claude-plugin/plugin.json:3, .claude-plugin/marketplace.json:9 & :17) but CITATION.cff:18 reads version: "1.3.2". Git history confirms 1.3.2→1.3.3 happened (tags v1.3.2 and v1.3.3 both exist; commit d6c1c10 is the 1.3.2 logo/CITATION change), so the .cff was simply not bumped with the rest of the release. Anyone citing the software gets the wrong version.
- **Evidence:** CITATION.cff:18 (version: "1.3.2"); mta/__init__.py:6; pyproject.toml:9; manifest.json:5; .claude-plugin/plugin.json:3; .claude-plugin/marketplace.json:9,:17
- **Recommendation:** Bump CITATION.cff:18 to "1.3.3". Then address the root cause (see PKG-02).

#### PKG-02 — No single canonical version source — six hand-maintained copies
*Medium · PARTIAL*

- **Claim/expected:** A maintainable release process implies one source of truth for the version, propagated automatically.
- **Reality:** The version is duplicated literally across six files (and twice within marketplace.json). pyproject.toml uses a static `version = "1.3.3"` rather than hatchling's dynamic version (e.g. reading mta.__version__), so nothing derives from mta/__init__.py. There is no sync script or CI check; PKG-01 is the direct consequence. The drift is self-evident proof the manual process already failed once.
- **Evidence:** pyproject.toml:9 (static version, no [tool.hatch.version] source); mta/__init__.py:6; manifest.json:5; .claude-plugin/plugin.json:3; .claude-plugin/marketplace.json:9,:17; CITATION.cff:18
- **Recommendation:** Pick one source (mta/__init__.py:6) and make pyproject derive it via `[project] dynamic=["version"]` + `[tool.hatch.version] path="mta/__init__.py"`. For the JSON/.cff files (which hatch can't template), add a tiny `scripts/check_versions.py` run in CI that fails if any of the six disagree.

#### PKG-04 — .mcpb zip-fallback omits launch.py and scripts/ (only `mcpb pack` bundles them)
*Medium · PARTIAL · quick-win*

- **Claim/expected:** build_mcpb.sh produces a working Claude Desktop bundle whose server entry_point (launch.sh) can bootstrap and run.
- **Reality:** The bundle's manifest entry_point is launch.sh (manifest.json:21-24), and launch.sh only needs install.sh + requirements.txt + mta/ — all of which the zip fallback DOES include — so the .mcpb itself still launches. However the zip fallback's explicit file list (build_mcpb.sh:25-28) omits launch.py and the scripts/ dir, and .mcpbignore does not mention them, so the two build paths diverge: the official `npx @anthropic-ai/mcpb pack .` path (build_mcpb.sh:14-16) ships everything not ignored (incl. launch.py/scripts), while the zip fallback silently drops them. Windows users (who per launch.py's own docstring must run `python launch.py`) get no launch.py in a fallback-built bundle.
- **Evidence:** scripts/build_mcpb.sh:14-16 (mcpb path) vs :25-28 (zip path, no launch.py/scripts); .mcpbignore:1-13 (does not list launch.py/scripts, so mcpb-pack includes them); manifest.json:20-24 (entry_point launch.sh); launch.py:7-8 (Windows instructions)
- **Recommendation:** Add launch.py and scripts to the zip fallback file list in build_mcpb.sh:25-28 so both build paths are identical. (manifest declares only darwin/linux at manifest.json:99, so launch.py is non-essential for the bundle today, but the divergence is a latent footgun.)

#### PKG-05 — version pinned in BOTH plugin.json and the marketplace entry (docs warn against this)
*Low · PARTIAL · quick-win*

- **Claim/expected:** Plugin/marketplace versioning should follow the documented single-pin guidance so updates propagate predictably.
- **Reality:** The Claude Code marketplace reference explicitly warns: "Avoid setting version in both plugin.json and the marketplace entry. The plugin.json value always wins silently, so a stale manifest version can mask a version you set in marketplace.json." This repo sets version=1.3.3 in plugin.json:3 AND in the marketplace entry marketplace.json:17 (plus a marketplace-level metadata.version at :9). Today they agree so behavior is correct, but it reproduces exactly the dual-pin the docs caution against, and compounds the PKG-02 drift surface.
- **Evidence:** .claude-plugin/plugin.json:3; .claude-plugin/marketplace.json:9,:17; (Claude Code marketplace docs, Version-resolution warning)
- **Recommendation:** Keep version only in plugin.json:3 (it wins anyway) and drop it from the marketplace plugin entry (marketplace.json:17), letting the entry inherit. Or fold both into the PKG-02 sync check.

#### PKG-07 — Runtime shell scripts use `set -uo pipefail` without `-e` (no fail-fast)
*Low · IMPLEMENTED*

- **Claim/expected:** Installer/launcher scripts should fail safely; the build script does use strict mode.
- **Reality:** build_mcpb.sh:7 correctly uses `set -euo pipefail`. The three runtime scripts deliberately omit `-e`: install.sh:7, launch.sh:7, scripts/mta-launcher.sh:7 all use `set -uo pipefail`. This appears intentional — the scripts pervasively guard individual commands with `|| true` / `|| log` so a single optional dep failure (brew, mlx, leiden) doesn't abort bootstrap, which is the resilient choice for a best-effort installer. Flagged as Info/Low because it trades fail-fast for resilience: a genuinely fatal early failure (e.g. venv creation) is handled explicitly (install.sh:30 `|| exit 1`), but other failures pass silently.
- **Evidence:** install.sh:7; launch.sh:7; scripts/mta-launcher.sh:7 (all `set -uo pipefail`); scripts/build_mcpb.sh:7 (`set -euo pipefail`); install.sh:30,37-38 (explicit guards)
- **Recommendation:** No change required; the omission is justified by the per-command guarding. If desired, document the choice in a one-line comment so future maintainers don't 'fix' it by adding -e and break the best-effort installs.

#### PKG-09 — MTA_WORKERS exposed in manifest.json but absent from plugin .mcp.json
*Low · PARTIAL · quick-win*

- **Claim/expected:** The plugin and the MCPB bundle should expose the same configurable runtime knobs for parity.
- **Reality:** manifest.json injects nine MTA_* env vars including MTA_WORKERS (manifest.json:34) and MTA_HOME (:27). The Claude Code plugin's .mcp.json injects only seven and omits MTA_WORKERS and MTA_HOME (.mcp.json:6-15). Functionally benign — the engine defaults workers to 0/auto (manifest.json:90) and MTA_HOME has its own default — but it is a config-surface inconsistency between the two distribution channels. Note plugin.json also has no userConfig block, so plugin users can't tune these knobs at enable time the way MCPB users can via user_config.
- **Evidence:** manifest.json:25-36 (9 env vars incl MTA_WORKERS:34, MTA_HOME:27); .mcp.json:6-15 (7 env vars, no MTA_WORKERS/MTA_HOME); .claude-plugin/plugin.json:1-17 (no userConfig)
- **Recommendation:** Either add MTA_WORKERS to .mcp.json:6-15 for parity, or document that workers auto-sizes for plugin users. Optionally add a `userConfig` block to plugin.json mirroring manifest.json's user_config so Claude Code users get the same enable-time prompts.

#### PKG-06 — manifest.json missing optional $schema field for editor validation
*Info · PARTIAL · quick-win*

- **Claim/expected:** MCPB manifests may declare $schema to get editor autocomplete/validation; well-formed manifests typically include it.
- **Reality:** manifest.json has no $schema key. This is purely optional per the MCPB spec and does not affect installation, but its absence means no editor-time validation and is a minor polish gap relative to the otherwise-complete manifest.
- **Evidence:** manifest.json:1-2 (starts directly with manifest_version, no $schema); grep for 'schema' in manifest.json returns nothing
- **Recommendation:** Add `"$schema": "https://raw.githubusercontent.com/anthropics/mcpb/main/dist/mcpb-manifest.schema.json"` (or the current published schema URL) as the first key.

#### PKG-08 — launch.py / launch.sh / install.sh / scripts ship in sdist but NOT in the wheel (by design, but creates two install personas)
*Info · IMPLEMENTED*

- **Claim/expected:** Side-branch fix reportedly ships launch.py/scripts in the sdist; confirm whether MAIN already does.
- **Reality:** MAIN already ships them in the sdist: pyproject.toml:68-71 [tool.hatch.build.targets.sdist].include lists launch.py, launch.sh, install.sh, and scripts. They are intentionally NOT in the wheel — [tool.hatch.build.targets.wheel] packages=["mta"] (pyproject.toml:61-62) plus force-include of only templates/assets (pyproject.toml:64-66). This is correct: a `pip install`-from-wheel user gets the `mta` console script (which self-bootstraps a venv via scripts/mta-launcher.sh only if installed from source), while MCPB/plugin users run launch.sh from the source tree/sdist. So the side-branch concern is already satisfied on main; noting it as Info because wheel-only users have a different (console-script) launch path than bundle users (launch.sh), which is internally consistent but worth knowing.
- **Evidence:** pyproject.toml:68-71 (sdist include lists launch.py/launch.sh/install.sh/scripts); pyproject.toml:61-66 (wheel = mta pkg + templates/assets force-include only); mta/server.py:150-156 (main + __main__ so `python -m mta.server` works); mta/server.py:117 (_status, used by cli `status`)
- **Recommendation:** No action needed. Optionally document in README that the wheel exposes the `mta` CLI while the MCP-server launch path lives in the sdist/repo (launch.sh).

### CI & release pipeline

The pipeline is functional and reasonably scoped for a token-free local tool: CI's OS/Python matrix exactly matches the README, runs fully offline (no Ollama/Tesseract/ffmpeg), and a build job validates the wheel/sdist with `twine check`; release.yml is tag-triggered and publishes a GitHub Release (wheel, sdist, .mcpb, install.sh) plus a token-gated PyPI upload. However, against a Phase-5 "single release train, no partial releases" target it has structural gaps: PyPI uses a long-lived API token rather than OIDC/Trusted Publishing, every GitHub Action is floating-tag-pinned (never SHA-pinned), there is no SBOM/signing/provenance, no concurrency guard, and no rollback — the two release jobs each run `python -m build` independently so a PyPI failure after the GitHub Release is created leaves a partial release. The version is hand-duplicated across pyproject.toml, manifest.json and __init__.py with no dynamic derivation and no tag-vs-version validation, and there is no committed lockfile so builds float on dependency ranges (non-reproducible). The README also promises a Homebrew tap that the release pipeline never actually publishes or bumps. Critically, CI installs only a hand-picked dependency subset with `--no-deps`, so the real conversion path (markitdown/pytesseract/faster-whisper/pdfplumber) is never exercised in CI.

**Strengths:**

- CI OS/Python matrix is exactly as advertised: ubuntu+macos+windows x 3.10/3.12 with fail-fast:false (ci.yml:17-20, README.md:201).
- CI is hermetically offline by design (MTA_NO_OLLAMA=1, MTA_AUTO_UPDATE=off, MTA_EXTRACT=classical) and tests assert metadata-only outputs — faithfully exercising the token-free/offline core promise without needing Ollama/Tesseract/ffmpeg in CI (ci.yml:21-25; tests/test_smoke.py:1-7).
- Dedicated build job validates the wheel+sdist with `twine check` and uploads them as artifacts; the hatchling<1.27 pin is a deliberate, documented fix for the Metadata-Version 2.5/twine incompatibility (ci.yml:46-64; pyproject.toml:1-5).
- Least-privilege GITHUB_TOKEN scopes: CI is contents:read, release is contents:write — nothing broader (ci.yml:10-11; release.yml:8-9).
- Release is properly tag-driven (tags: v*) and attaches a complete asset set — wheel, sdist, .mcpb, and install.sh — with auto-generated release notes (release.yml:5, :29-37).
- build_mcpb.sh is robust: prefers the official @anthropic-ai/mcpb packer (which validates the manifest) and falls back to a spec-compliant zip honouring a present .mcpbignore, shipping a source-only bundle (scripts/build_mcpb.sh:13-29; .mcpbignore present).
- PyPI upload uses --skip-existing and action-gh-release is create-or-update, giving partial idempotency on re-runs even though the train as a whole is not atomic (release.yml:61, :30-31).

#### CI-02 — PyPI publish uses a long-lived API token, not OIDC/Trusted Publishing
*High · PARTIAL · quick-win*

- **Claim/expected:** Implicit Phase-5 target: secure, modern release with no long-lived secrets.
- **Reality:** The pypi job authenticates with TWINE_PASSWORD=${{ secrets.PYPI_API_TOKEN }} (a long-lived token) via plain `twine upload`. The file itself documents that Trusted Publishing (pypa/gh-action-pypi-publish + permissions: id-token: write) is the intended-but-unimplemented alternative. No `id-token: write` permission is granted anywhere.
- **Evidence:** .github/workflows/release.yml:51-64 (token usage at :58, twine upload at :61); comment at :51-54; no `id-token` in permissions block at :8-9
- **Recommendation:** Switch the pypi job to pypa/gh-action-pypi-publish with `permissions: id-token: write` and configure a PyPI Trusted Publisher for this repo+workflow; remove PYPI_API_TOKEN. Reuse the already-built dist (see CI-06) instead of rebuilding.

#### CI-05 — No concurrency guard, idempotency, or rollback — partial-release risk
*High · PARTIAL*

- **Claim/expected:** Phase-5 target: "single release train, no partial releases" (atomic, re-runnable, halt-and-rollback on partial failure).
- **Reality:** release.yml has two jobs: `release` (creates the GitHub Release + assets) and `pypi` (needs: release). If `pypi` fails (e.g. token unset/invalid or PyPI 4xx), the GitHub Release is already published — a partial release with no rollback. There is no top-level `concurrency:` key, so two pushes of overlapping tags could run release jobs in parallel. action-gh-release is create/update (some idempotency) and twine uses --skip-existing, but the train as a whole is not atomic and has no halt-and-rollback.
- **Evidence:** .github/workflows/release.yml:11-38 (release job), :39-64 (pypi job, needs: release at :41); no `concurrency:` anywhere in the file; --skip-existing at :61
- **Recommendation:** Reorder so PyPI publish (the irreversible step) gates the GitHub Release, or run both in one job with a single build and fail-closed. Add a `concurrency:` group keyed on the tag. On partial failure, delete/mark the draft Release rather than leaving it published.

#### CI-10 — CI installs only a hand-picked dep subset with --no-deps — real conversion path untested
*High · PARTIAL*

- **Claim/expected:** README: a "growing regression suite" and "green CI on three OSes" covering "accuracy, reliability… cross-platform" (README.md:243); the tool's core promise is local attachment→Markdown conversion.
- **Reality:** CI installs only numpy/networkx/rapidfuzz/mcp/psutil/pytest then `pip install -e . --no-deps` (ci.yml:37-38). The declared runtime deps that actually do conversion — markitdown[...], pdfplumber, pillow, pytesseract, pypdfium2, striprtf, faster-whisper (pyproject.toml:36-42) — are never installed. Tests run with MTA_EXTRACT=classical / MTA_NO_OLLAMA=1, so CI verifies the offline graph/memory plumbing and tool registration, but exercises none of the converters, OCR, or transcription. A break in the MarkItDown/Tesseract/Whisper path would pass CI.
- **Evidence:** ci.yml:21-25 (offline env), :34-38 (subset + --no-deps), :40-44 (smoke + stdio only); pyproject.toml:36-42 (uninstalled conversion deps); tests/test_smoke.py:1-7 header confirms offline-only scope
- **Recommendation:** Add at least one CI lane that `pip install -e .` with full deps and (on ubuntu) installs tesseract-ocr+ffmpeg via apt, running conversion smoke tests on a tiny PDF/image/audio fixture. Keep the fast offline lane for the matrix.

#### CI-03 — GitHub Actions are floating-tag pinned (@v4/@v5/@v2), not SHA-pinned
*Medium · PARTIAL · quick-win*

- **Claim/expected:** Supply-chain hardening target: actions pinned to immutable commit SHAs.
- **Reality:** Every `uses:` references a mutable major-version tag — actions/checkout@v4, actions/setup-python@v5, actions/upload-artifact@v4, softprops/action-gh-release@v2. A compromised/retagged action could inject code into the release that handles release-upload and (token-based) PyPI publish.
- **Evidence:** .github/workflows/release.yml:15,17,30,43,44; .github/workflows/ci.yml:27,30,49,50,61
- **Recommendation:** Pin all actions to full 40-char commit SHAs (with a version comment), and ideally add Dependabot for github-actions to keep them current.

#### CI-04 — No SBOM, signing, or build provenance/attestation anywhere
*Medium · MISSING*

- **Claim/expected:** Phase-5 hardened release train (provenance / verifiable artifacts) implied for a security-sensitive local tool.
- **Reality:** Grepped both workflows for sign|sbom|provenance|attest|cosign|sigstore — only hit is the inline comment about Trusted Publishing. No artifact signing (sigstore/cosign), no SBOM generation (e.g. cyclonedx), no GitHub artifact-attestation / build provenance for the wheel, sdist, or .mcpb.
- **Evidence:** grep over .github/workflows/*.yml returns only release.yml:54 (comment); no signing/SBOM/attestation steps in release.yml:11-64
- **Recommendation:** Add `actions/attest-build-provenance` for the dist + .mcpb, generate an SBOM (cyclonedx-py) and attach it to the Release, and consider sigstore-signing the .mcpb bundle.

#### CI-06 — Release builds dist twice independently — non-reproducible / drift risk
*Medium · PARTIAL · quick-win*

- **Claim/expected:** Reproducible builds; the artifact published to PyPI is the same one attached to the GitHub Release.
- **Reality:** The `release` job runs `python -m build` (release.yml:21-24) and the `pypi` job runs `python -m build` AGAIN (release.yml:47-49) on a fresh checkout. The two builds are not guaranteed bit-identical (no committed lockfile, floating build backend within hatchling>=1.21,<1.27), and the artifacts attached to the GitHub Release are a different build run than the ones uploaded to PyPI. No artifact is passed between jobs via upload/download-artifact.
- **Evidence:** .github/workflows/release.yml:21-24 and :47-49 (two separate `python -m build`); no actions/upload-artifact/download-artifact between jobs (CI uses upload-artifact at ci.yml:61 but release.yml does not)
- **Recommendation:** Build once in a `build` job, upload-artifact the dist + .mcpb, then have both the `release` (gh-release) and `pypi` jobs download-artifact and publish the identical files.

#### CI-07 — Version hand-duplicated in 3 files; no single source, no dynamic derivation
*Medium · PARTIAL · quick-win*

- **Claim/expected:** Task: "Confirm release derives the version from the single source."
- **Reality:** Version 1.3.3 is hardcoded independently in pyproject.toml:9, manifest.json:5, and mta/__init__.py:6. There is no `[tool.hatch.version]`/`dynamic=["version"]` config — pyproject carries a static literal. Nothing derives one from another, so a bump requires three manual edits that can silently drift.
- **Evidence:** pyproject.toml:9; manifest.json:5; mta/__init__.py:6; grep for `dynamic`/`tool.hatch.version` in pyproject.toml → none
- **Recommendation:** Make pyproject use hatchling's dynamic version sourced from mta/__init__.py (`[tool.hatch.version] path="mta/__init__.py"`), and have build_mcpb.sh inject the same value into manifest.json at pack time so there is exactly one source of truth.

#### CI-08 — Release does not validate the git tag against the package version
*Medium · MISSING · quick-win*

- **Claim/expected:** A `vX.Y.Z` tag should correspond to package version X.Y.Z (consistent single release train).
- **Reality:** release.yml triggers on tags v* (release.yml:5) but never reads GITHUB_REF/ref_name to assert the tag matches pyproject/__init__ version. One could tag v9.9.9 and publish a wheel/manifest/Release that all say 1.3.3 with no failure. build_mcpb.sh also performs no tag check.
- **Evidence:** .github/workflows/release.yml:5 (tag trigger); grep for GITHUB_REF/ref_name/tag in release.yml and scripts/build_mcpb.sh → no validation step
- **Recommendation:** Add a guard step that fails the release unless `${GITHUB_REF_NAME#v}` equals the version read from mta/__init__.py (and manifest.json).

#### CI-09 — No committed lockfile — builds float on dependency ranges (not reproducible)
*Medium · MISSING*

- **Claim/expected:** README: "crash-safe & reusable", green CI on three OSes; implied reproducibility for a release pipeline.
- **Reality:** No uv.lock/poetry.lock/Pipfile.lock exists. requirements.txt exists but is unpinned-by-policy (install.sh even force-upgrades MarkItDown to git main). CI installs a hand-picked subset with `pip install -e . --no-deps`, and release builds with floating ranges (mcp>=1.2, numpy>=1.26, etc.). Each build can resolve different transitive versions, so wheels/.mcpb are not byte-reproducible.
- **Evidence:** No lock file found (searched uv.lock/poetry.lock/Pipfile.lock); pyproject.toml:30-43 (range deps); ci.yml:37-38 (subset + --no-deps); install.sh pulls markitdown from git main (install.sh ~:40-45)
- **Recommendation:** Commit a lockfile (uv.lock or pip-tools requirements.lock) and install from it in CI/release; pin the hatchling build backend more tightly. Accept that the `latest MarkItDown` design intentionally floats, but isolate that to the runtime installer, not the published artifact.

#### CI-11 — Homebrew tap is a documented install/publish target but unautomated in the pipeline
*Medium · MISSING*

- **Claim/expected:** README: "brew install GRU-953/memorised-them-all/mta" (README.md:80); a formula is implied (scripts/mta-launcher.sh comment: "CLI launcher used by the Homebrew formula").
- **Reality:** release.yml publishes only a GitHub Release and PyPI — it never creates or bumps a Homebrew formula/tap. No `.rb` formula exists in the repo (searched). So the advertised `brew install` channel is not produced or version-synced by any release automation; it must be maintained by hand in a separate tap repo, which will silently lag the single release train.
- **Evidence:** README.md:80; scripts/mta-launcher.sh:2-3 (references a formula); release.yml:11-64 (only GitHub Release + PyPI; no tap/formula step); `find . -iname '*.rb'` → none
- **Recommendation:** Either drop the brew claim or add a release step (e.g. dispatch to a homebrew-tap repo / bump-formula-pr action) so the formula's version + sha256 are updated automatically from the same tag.

#### CI-12 — .mcpb bundle is built only in release, never smoke-tested in CI
*Low · PARTIAL · quick-win*

- **Claim/expected:** The .mcpb (Claude Desktop bundle) is a primary release artifact (attached to every Release).
- **Reality:** build_mcpb.sh runs only in the release job (release.yml:26-27). CI never invokes it, so a regression in the packer (e.g. manifest invalid, missing .mcpbignore entry, npx/zip absent) is discovered only at tag time. The script does degrade gracefully (mcpb CLI → zip fallback) and .mcpbignore is present, so the build itself is sound — but it is unverified pre-release.
- **Evidence:** release.yml:26-27 (only place build_mcpb.sh runs); ci.yml has no .mcpb step; scripts/build_mcpb.sh:13-29 (npx mcpb or zip fallback); .mcpbignore present (13 lines)
- **Recommendation:** Add a CI step (ubuntu) that runs bash scripts/build_mcpb.sh and asserts dist/memorised-them-all.mcpb exists and is non-empty, so packaging regressions are caught on PRs.

#### CI-01 — CI OS/Python matrix matches README claim exactly
*Info · IMPLEMENTED*

- **Claim/expected:** README: "CI runs the test suite across Ubuntu, macOS, and Windows on Python 3.10 & 3.12." (README.md:201)
- **Reality:** ci.yml defines matrix os=[ubuntu-latest, macos-latest, windows-latest] and python-version=["3.10","3.12"] with fail-fast:false — an exact match to the claim.
- **Evidence:** .github/workflows/ci.yml:17-20; README.md:201
- **Recommendation:** No change needed. Strength; keep the matrix in sync if Python support widens (pyproject requires-python>=3.10).

#### CI-13 — CI build job validates wheel/sdist with twine check and uploads artifact
*Info · IMPLEMENTED*

- **Claim/expected:** Distributable packaging is validated before release.
- **Reality:** A dedicated `build` job builds wheel+sdist via `python -m build`, runs `twine check dist/*`, and uploads the dist as an artifact. The hatchling pin (>=1.21,<1.27) is deliberately chosen to keep Metadata-Version at 2.3 so twine check passes — a thoughtful, documented constraint.
- **Evidence:** .github/workflows/ci.yml:46-64 (build job); :57-60 (twine check); pyproject.toml:1-5 (hatchling pin rationale)
- **Recommendation:** Strength — keep. Consider running twine check in the release job too (release currently builds but skips the check).

#### CI-14 — least-privilege permissions and offline-by-construction CI
*Info · IMPLEMENTED*

- **Claim/expected:** README: "Private by design — no cloud… Your files never leave your computer" (README.md:114); token-free guarantee.
- **Reality:** CI sets `permissions: contents: read` and release sets `contents: write` (only what each needs). CI is hermetically offline by env (MTA_NO_OLLAMA=1, MTA_AUTO_UPDATE=off, MTA_EXTRACT=classical) and tests assert metadata-only outputs, aligning the pipeline with the token-free/offline promise.
- **Evidence:** ci.yml:10-11 (contents: read), :21-25 (offline env); release.yml:8-9 (contents: write); tests/test_smoke.py:1-7
- **Recommendation:** Strength — keep. When adding PyPI Trusted Publishing, scope `id-token: write` to the pypi job only, not globally.

### MCP server surface and token-free invariant

Transport is **stdio-only** (correct baseline before the Phase-3 HTTP work). All **8 tools** are registered with signatures matching the README and manifest.json exactly, and the CLI reuses the same engine entry points (no drift). The **token-free invariant is enforced in depth** — recall hits capped at 600 chars/5 docs, k clamped to [1,50], local-LLM output `num_predict`-capped — and no field of `digest`/`recall` returns raw Markdown or file bodies. The gaps are Medium and below: tool handlers lack input validation (a bad arg can raise an unhandled exception across the boundary, MCP-07), the MCP SDK is pinned only by a low lower bound with no upper cap (MCP-06), and stale "seven tools" docstrings/CI assertion undercount the real eight and leave `forget` untested (MCP-08).

**Strengths:**

- Token-free invariant enforced in depth: recall hits hard-capped at 600 chars and 5 docs (recall.py:20-21,27), k clamped to 1..50 with exception-safe parsing (recall.py:37-41), local-LLM output capped via num_predict (extract.py:91; digest.py:122); survives a prompt-injected local model.
- Traced every field of digest (digest.py:291-302) and recall (recall.py:70-72): no path returns raw Markdown or file bodies; converted text only written to disk, read locally for segmentation (digest.py:180-181).
- All 8 tools registered with signatures matching README and manifest.json exactly (server.py:47-114); FastMCP server name matches the manifest key.
- Clean stdio-only transport baseline (server.py:153; no HTTP or SSE in mta), correct before Phase-3 HTTP work.
- Strong file-handling hygiene: prompt data-delimiting (extract.py:40-48), script-tag escaping in the mind map (render.py:145-147), atomic writes with fsync and os.replace (store.py:24-44,75-93), np.load of npz not pickle (store.py:101), per-file and decompression caps (config.py:74; convert.py:70).
- CLI reuses the same engine entry points as the MCP tools (cli.py:66-91), so no drift between with-Claude and without-Claude paths.

#### MCP-06 — MCP SDK pinned only by a low lower bound, no upper cap
*Medium · PARTIAL · quick-win*

- **Claim/expected:** Uses SDK-bundled FastMCP from mcp.server.fastmcp; README implies a current integration.
- **Reality:** pyproject.toml:31 and requirements.txt:5 pin mcp lower bound 1.2 only; web check shows official mcp around 1.27.x in 2026, FastMCP 3.x, spec stable 2025-06-18 (2025-11-25 RC); old SDK satisfies the floor and a breaking mcp 2.x could be pulled; missing-SDK import is guarded (server.py:21-24) but an incompatible version is not caught.
- **Evidence:** pyproject.toml:31; requirements.txt:5; mta/server.py:21-24; web verification of pypi mcp version and spec revision
- **Recommendation:** Tighten to 1.9 and below 2 in both files; add a CI floor-version job.

#### MCP-07 — Tool handlers lack input validation; can raise unhandled exceptions across the boundary
*Medium · PARTIAL · quick-win*

- **Claim/expected:** README L113: Crash-safe and reusable.
- **Reality:** export_memory passes dest to export_bundle which catches only OSError (render.py:174-194), so a non-string or None dest raises TypeError in Path(dest); digest assumes paths is a list, so a string is iterated char by char in _expand (digest.py:43); by contrast recall hardens k (recall.py:37-41) and list_digestible/open_mindmap/forget handle missing paths (server.py:84-86,111-114; store.py:112-115).
- **Evidence:** mta/server.py:73-77,47-56; mta/core/render.py:174-194; mta/core/digest.py:33-54; mta/core/recall.py:37-41; mta/core/store.py:112-115
- **Recommendation:** Validate dest and paths; broaden export_bundle except to TypeError and ValueError.

#### MCP-08 — Stale seven-tools docstrings and CI assertion undercount the real eight; forget untested
*Medium · PARTIAL · quick-win*

- **Claim/expected:** server.py L3 says eight; manifest and README say eight; the stdio CI check claims all seven tools.
- **Reality:** tests/mcp_stdio_check.py:1 says seven and EXPECTED (L12-13) lists 7, omitting forget; the test asserts a subset (missing equals EXPECTED minus names, L30-31), so it PASSES even if forget were unregistered, leaving the irreversible-delete tool with no startup coverage.
- **Evidence:** tests/mcp_stdio_check.py:1,12-13,30-31; mta/server.py:3; manifest.json:39-48; README.md:134
- **Recommendation:** Add forget to EXPECTED, fix docstring to eight, assert names equals the full set.

#### MCP-09 — CLI subcommands match the documented list; only cosmetic field drift
*Low · PARTIAL · quick-win*

- **Claim/expected:** README L147 CLI list and cli.py L2-12 mirror the tools.
- **Reality:** Subcommands match one to one (cli.py:34-59); extras serve and update have no tool equivalents; overview/export vs memory_overview/export_memory; cli mindmap returns status and path (cli.py:84) omitting open_with and project (server.py:113-114).
- **Evidence:** mta/cli.py:34-59,66-91,84; README.md:147; mta/server.py:107-114
- **Recommendation:** Optional: cli mindmap could reuse the tool dict. Not load-bearing.

#### MCP-10 — Auto-update side effect fires inside _cfg on most tool calls (documented, opt-out)
*Low · PARTIAL*

- **Claim/expected:** README L219: only network access is install plus a throttled once-a-day update check, disabled via the auto-update env.
- **Reality:** _cfg (server.py:40-44) invokes updater.start_background on first activity for digest/recall/memory_overview/export_memory/open_mindmap, a throttled non-blocking check that does not affect the token-free invariant; memory_status and forget bypass _cfg (server.py:97,101-104,117-118).
- **Evidence:** mta/server.py:40-44,55,63,70,77,109,97,101-104; README.md:219
- **Recommendation:** No change (documented, opt-out). For a stricter posture, move start_background to serve startup.

#### MCP-01 — All 8 claimed tools registered with matching signatures
*Info · IMPLEMENTED*

- **Claim/expected:** README L132-145, manifest.json L39-48 claim 8 tools (digest, recall, memory_overview, export_memory, list_digestible, memory_status, open_mindmap, forget) with listed signatures.
- **Reality:** server.py registers exactly 8 mcp.tool funcs with matching signatures (L47-49,59-60,67-68,73-74,80-81,93-94,100-101,107-108); 8 decorators, 0 resource/prompt; FastMCP name L26 matches manifest key.
- **Evidence:** mta/server.py:26,47-49,59-60,67-68,73-74,80-81,93-94,100-101,107-108; README.md:138-145; manifest.json:39-48
- **Recommendation:** No change. Surface and code agree.

#### MCP-02 — Token-free invariant holds: recall returns only hard-capped slices
*Info · IMPLEMENTED*

- **Claim/expected:** README L98-100,134,225,243: recall returns a small slice, never documents; results hard-capped even on the accurate path.
- **Reality:** recall returns status/synopsis/top_score/low_confidence/hits (recall.py:70-72); _hit caps text to 600 and docs to 5 (recall.py:20-21,24-30); k clamped max(1,min(k,50)) in try/except (recall.py:37-41); hit text is stored units (summaries, entity cards, facts capped at 5, digest.py:319-333), not raw chunks; no recall path reads markdown_dir.
- **Evidence:** mta/core/recall.py:20-21,24-30,37-41,70-72; mta/core/digest.py:319-333
- **Recommendation:** Keep. Add a test asserting hit text at most 600 and hits at most 50.

#### MCP-03 — digest returns only metadata; document bodies never cross back
*Info · IMPLEMENTED*

- **Claim/expected:** README L97,243: returns ONLY counts, paths, stats; text never crosses back.
- **Reality:** digest returns status/stats/outputs/conversion (digest.py:291-302); stats ints/strings (L263-276), outputs paths only, conversion a tally (L418-422); Markdown written to disk and read only locally for segmentation (L287-289,180-181); downstream text bounded (extract.py:91,123; digest.py:122).
- **Evidence:** mta/core/digest.py:291-302,263-276,418-422,287-289,180-181,122; mta/core/extract.py:91,123
- **Recommendation:** No change. Strength.

#### MCP-04 — Prompt-injection hardening bounds local-LLM output into memory
*Info · IMPLEMENTED*

- **Claim/expected:** README L221: prompt-injection data-delimiting and hard-capped results.
- **Reality:** Prompt wraps chunk in CHUNK/END delimiters as data (extract.py:40-48,89); output capped via num_predict (extract.py:91; digest.py:122) then re-capped to 600 by recall; mind map escapes closing-angle so a script tag cannot break out (render.py:145-147).
- **Evidence:** mta/core/extract.py:40-48,89,91; mta/core/digest.py:122; mta/core/recall.py:20,27; mta/core/render.py:145-147
- **Recommendation:** Keep. Strong posture for untrusted files.

#### MCP-05 — Transport is stdio-only with no HTTP/SSE
*Info · IMPLEMENTED*

- **Claim/expected:** Record current transport; Phase 3 adds HTTP. cli.py:11, README L199 describe stdio.
- **Reality:** Bare mcp.run() (server.py:153), stdio default; grep of mta for transport/streamable/sse/fastapi/uvicorn/starlette/host/port shows only unrelated hits; no HTTP, no bound port; stdio check uses stdio_client (tests/mcp_stdio_check.py:19-28).
- **Evidence:** mta/server.py:153; tests/mcp_stdio_check.py:19-28
- **Recommendation:** No action now. For Phase-3 HTTP, gate behind opt-in and re-confirm caps.

#### MCP-11 — Read-only tools memory_status and list_digestible return bounded metadata-only shapes; status runtime UNVERIFIED
*Info · IMPLEMENTED*

- **Claim/expected:** README L142-143: list_digestible lists files paths/sizes only; memory_status returns local stack health.
- **Reality:** _status (server.py:117-147) is a fixed metadata dict, no document content, 3s timeout-guarded Ollama call (L126-134); not run live so UNVERIFIED but shape is token-safe. list_digestible caps files at 500 (server.py:90) yet reports the true count (L89); entries are path+bytes; missing dir returns not_found (L85-86).
- **Evidence:** mta/server.py:117-147,80-90; mta/core/store.py:118-135
- **Recommendation:** Minor: when list_digestible count exceeds 500, add a truncated flag (parallels digest.py:269).

### Conversion to digest pipeline

The convert→segment→embed→extract→resolve→graph→materialise pipeline is well-architected and the central token-free / offline invariant holds: I empirically ran a full digest with MTA_NO_OLLAMA=1 and with rapidfuzz/markitdown/PIL absent, and it succeeded end-to-end (9 entities, 30 relations, 2 communities, hash embeddings, all artifacts written). Every stage has a genuine dependency-free fallback (classical extractor in extract.py:58-80, hashing embedder in embed.py:35-45, deterministic summaries in digest.py:135-148/305-316), and one malformed/oversized/unsupported file is isolated rather than aborting the batch (proven: a corpus with a broken WAV + broken PDF still digested the 2 good files). The full 28-test offline regression suite passes with declared deps present. The main real issues are not correctness-breaking: a 20s-per-call stall when Ollama is INSTALLED-but-unreachable and MTA_NO_OLLAMA is unset (High, UX/perf, digest still completes), a misleading stats.mode="accurate" label when no model actually ran (Low), and classical-extractor quality smells (entity fragmentation, newline-laden facts). No code path was found that hard-requires a model or the network to complete a digest.

**Strengths:**

- The core offline / token-free invariant is real and was empirically proven: a full digest completes with MTA_NO_OLLAMA=1 and with rapidfuzz/markitdown/PIL/faster_whisper all absent (9 entities, 30 relations, all artifacts written). No code path hard-requires a model or the network to finish a digest.
- Genuine dependency-free fallbacks at every stage: classical regex entity/relation/fact extractor (extract.py:58-80), deterministic md5 hashing-trick embedder (embed.py:35-45), deterministic community summaries and synopsis (digest.py:135-148,309-316), and graph community detection that degrades Leiden→Louvain→greedy-modularity (graph.py:89-112).
- Excellent batch robustness: per-file try/except in every converter, process-pool worker-crash isolation that re-runs one file on the main thread, BrokenProcessPool fallback to sequential, and _safe_extract degrading a mid-run extractor failure to an empty Extraction — verified that a broken WAV + broken PDF do not abort a batch.
- Strong safety/bounds engineering: oversize-file skip before read, zip-bomb and nested-archive rejection, max_chunks cap with explicit (non-silent) truncation reporting, low-value-chunk skipping, per-node fact cap, OCR page cap, and num_predict caps on all LLM output.
- Atomic, crash-safe persistence (temp→fsync→os.replace) for graph.json and vectors, plus schema-version guarding on load — the final materialise step cannot leave a corrupt half-written memory.
- Fast mode is correctly implemented and byte-deterministic offline (two runs produced identical graph signatures), still builds the graph and still writes recall vectors, exactly as advertised.
- Thorough offline regression suite (28 tests, all green with declared deps) that explicitly exercises the offline path, fast determinism, entity-resolution over-merge guards, zip-bomb handling, same-basename collision safety, and the token-free contract (recall slices hard-capped, no document text in tool results).
- Careful spawn-safety and Apple-silicon tuning: top-level picklable worker, race-free output-name assignment in the main process, BLAS thread pinning per worker, and worker counts clamped by both performance cores and unified memory.

#### PIPE-03 — Ollama installed-but-unreachable (and MTA_NO_OLLAMA unset) causes repeated 20s stalls across the digest
*High · PARTIAL · quick-win*

- **Claim/expected:** Lifecycle starts Ollama on demand and otherwise gets out of the way; offline digests are fast (README "20-100x faster" framing assumes the fallback kicks in cheaply).
- **Reality:** ensure_running(wait=20|25) is called from embed (embed.py:90), every extract_chunk (extract.py:84), every _community_summary/_synopsis via _llm_summarise (digest.py:116), and per image/audio in convert. If the `ollama` binary is present (e.g. brew-installed) but the server is unreachable at OLLAMA_HOST, ensure_running spawns `ollama serve` and then polls for the FULL wait window. I measured 20.27s for a single ensure_running call in this state. If the daemon can never bind the configured host (wrong OLLAMA_HOST/port), EVERY embed+extract+summary call eats 20-25s, so a small digest can stall for minutes. The digest still COMPLETES via fallback (not a correctness break), and the two clean cases are fast: binary genuinely absent → 0.011s, MTA_NO_OLLAMA=1 → ~0s (lifecycle.py:49-51,76).
- **Evidence:** lifecycle.py:74-102 (Popen serve then poll up to wait); convert.py:177; extract.py:84; embed.py:90; digest.py:116; measured 20.27s (installed+down) vs 0.011s (no binary) vs ~0s (MTA_NO_OLLAMA)
- **Recommendation:** Add a short negative-result cache on OllamaManager: once a start attempt fails (or is_up() is false after the first ensure_running), set a flag so subsequent calls in the same process return False immediately instead of re-polling. Also consider a much shorter probe (1-2s) before committing to a 20s startup wait.

#### PIPE-05 — rapidfuzz treated as optional though it is a hard dependency; without it entity resolution silently degrades to exact-match
*Medium · PARTIAL*

- **Claim/expected:** resolve.py:6-8 — "Falls back to exact normalised-string matching if rapidfuzz is absent"; pyproject.toml:34 declares rapidfuzz>=3.6 as a hard dependency.
- **Reality:** resolve.py:24-28 wraps the rapidfuzz import in try/except (_HAVE_FUZZ). When absent, BOTH the fuzzy token-set merge (resolve.py:107-117) and the embedding-confirmed merge (resolve.py:146-154) are skipped — only exact-normalised match and acronym↔expansion linking remain. I reproduced this: without rapidfuzz, "Helios Energy" and "Helios" do NOT merge (test_entity_resolution_no_overmerge fails: cid e0 != e1). The docstring fallback claim is technically upheld and the digest still succeeds, but resolution quality drops sharply and silently, and there is no signal in stats that fuzzy matching was disabled. (With rapidfuzz present — the declared install — all 28 tests pass.)
- **Evidence:** resolve.py:24-28,107-117,146-154; pyproject.toml:34; reproduced: rapidfuzz-absent run merged "Helios Energy"/"Helios" as distinct nodes (test failed), passes once rapidfuzz installed
- **Recommendation:** Either treat rapidfuzz as the hard dep it is declared to be (let ImportError surface, or warn loudly), or record a `resolution="exact-only"` flag in stats when _HAVE_FUZZ is false so degraded resolution quality is observable.

#### PIPE-06 — Classical extractor fragments entities and produces newline-laden / truncated facts
*Medium · PARTIAL · quick-win*

- **Claim/expected:** extract.py:5-7 — classical pass "guarantees a usable graph offline"; resolve.py canonicalises surface variants.
- **Reality:** On the sample corpus offline, the classical path created separate nodes for "Aurora", "Project Aurora", "Nordic Grid Authority" and "The Nordic Grid Authority" — the leading stopword "The" was captured by _ENTITY_RE (extract.py:24-25) so "The Nordic Grid Authority" did not normalise-match "Nordic Grid Authority", and only a fuzzy threshold (88) would merge them. Facts also retain mid-fact newlines ("Nordic Grid\nAuthority") and the sentence splitter treats "Dr." as a boundary, yielding the fragment "The program director is Dr.". These are quality smells, not crashes — the graph is still usable and the README frames classical as "weaker". "The" is notably absent from _STOPWORDS-as-leading-word stripping (the stopword set filters whole-name matches only, extract.py:65).
- **Evidence:** extract.py:24-25,58-80 (_ENTITY_RE captures leading "The"; _SENT_RE splits on "Dr."); observed in /tmp/.../memory/aurora-project.md.md ("Aurora" + "Project Aurora" + "The Nordic Grid Authority" as separate entities; "is Dr." fact)
- **Recommendation:** Strip a leading determiner (The/A/An) from captured entity names before counting, and collapse internal whitespace in facts (the code already does this for entity labels at extract.py:64 but not for facts). Optionally add common abbreviations (Dr., Inc., etc.) to a no-split guard in _SENT_RE.

#### PIPE-04 — stats.mode reports "accurate" even when no LLM ran (classical+hash fallback)
*Low · PARTIAL · quick-win*

- **Claim/expected:** stats.mode distinguishes "fast" vs "accurate" digests (digest.py:274).
- **Reality:** mode is derived purely from cfg.fast (digest.py:274: `"fast" if cfg.fast else "accurate"`). In a non-fast offline run (no Ollama, extract_mode=auto) the engine actually used classical extraction + hash embeddings — identical to fast mode — yet stats.mode is reported as "accurate". Verified: NON-fast offline run → stats.mode='accurate', embed_mode='hash'. This mislabels a fallback digest as a high-accuracy LLM digest in graph.json/memory.md.
- **Evidence:** digest.py:274; config.py:139-141; verified: non-fast offline digest reported mode='accurate' with embed_mode='hash'
- **Recommendation:** Derive mode from what actually ran, e.g. set mode to "fast"/"accurate" based on whether any LLM extraction succeeded (track an `llm_used` flag from extract_chunk), or at minimum label it "classical" when embedder.mode=='hash' and extract_mode resolved to classical.

#### PIPE-08 — Memory bounds on large corpora: per-file size cap, zip-bomb guard, chunk cap, fact cap — but full corpus is loaded into memory
*Low · IMPLEMENTED*

- **Claim/expected:** convert.py:259 / config.py:71-74 — files over MTA_MAX_FILE_MB are skipped before reading; decompression bombs rejected; chunk workload capped with explicit reporting.
- **Reality:** Multiple real bounds: oversize files skipped before read (convert.py:260-267, verified status=skipped/too-large), zip-bomb / nested-archive rejection (convert.py:54-81, verified), max_chunks cap with explicit `chunks_truncated` reporting (digest.py:195-197), low-value chunk skipping (digest.py:188-192,336-346), per-node fact cap of 25 (graph.py:18,63), OCR page cap of 50 (convert.py:140), capped LLM output via num_predict (digest.py:122, extract.py:91). However the corpus is materialised all-at-once: segment_file loads every .md and all_chunks holds every chunk (digest.py:179-181) before dedupe — for a very large existing corpus this is load-all, not streaming. Bounded in practice by max_chunks downstream but peak memory during segmentation scales with corpus size on disk.
- **Evidence:** convert.py:54-81,140,260-267; digest.py:122,179-181,188-197; graph.py:18,63; extract.py:91; verified oversize+zip-bomb skips
- **Recommendation:** For very large accumulated corpora, consider streaming segmentation (process+dedupe per file, discard text after extraction) instead of building all_chunks fully in memory; current caps make this Low priority.

#### PIPE-10 — Audio files have no offline fallback content path — correctly reported as failed/empty, never crash
*Low · IMPLEMENTED*

- **Claim/expected:** convert.py:7 — Whisper for audio; missing optional deps degrade to clear status rather than crashing.
- **Reality:** Audio (_AUDIO_EXTS) routes only to _try_whisper (convert.py:287-288); there is no secondary text path for audio (expected — audio has no text without transcription). With no whisper lib and transcribe=auto, the result is status=failed/method=transcribe-error:ModuleNotFoundError (verified); with transcribe=off it is status=empty/method=transcribe-off (verified). Both are clean ConvResults that isolate the file — the batch and digest continue. mlx_whisper→faster_whisper(cuda)→faster_whisper(cpu int8) device cascade degrades cleanly (convert.py:200-228). So audio simply contributes no content offline-without-whisper, which is correct behaviour, not a bug.
- **Evidence:** convert.py:200-228,287-288,294-300; verified audio status=failed (auto,no-whisper) and status=empty (off)
- **Recommendation:** None functionally. Optional: classify "library missing" audio as a distinct "unsupported (no transcriber)" status to distinguish it from genuine transcription errors in the manifest.

#### PIPE-01 — Offline digest invariant holds: full pipeline completes with no models and no network
*Info · IMPLEMENTED*

- **Claim/expected:** README:130/227/233 — "a digest always succeeds — even offline, even before any model is downloaded"; classical extractor + hashing embeddings keep the pipeline working with no models.
- **Reality:** Empirically verified. Ran `digest(cfg, [sample])` with MTA_NO_OLLAMA=1 and with rapidfuzz/markitdown/PIL/faster_whisper all absent: status=ok, 9 entities, 30 relations, 2 communities, embed_mode=hash, graph.json + memory.md + mindmap.html + 2 per-doc notes all written. extract.py:132-139 routes to _classical() when no LLM; embed.py:90-112 falls back to _hash_embed_one; digest.py:135-148 and _synopsis() use deterministic joins. No stage raises on missing models.
- **Evidence:** extract.py:132-139; embed.py:90-112; digest.py:138-148,309-316; lifecycle.py:49-57,74-102; verified by running digest offline (status ok, 9 entities)
- **Recommendation:** None — keep. This is the load-bearing promise of the project and it works.

#### PIPE-02 — Per-file conversion failures are isolated; one bad file does not abort the batch
*Info · IMPLEMENTED*

- **Claim/expected:** convert.py:11-13 / digest.py:92-93 — missing deps degrade to a clear status "rather than crashing a batch"; a single worker crash converts only that file, a broken pool degrades to sequential.
- **Reality:** Verified: a corpus containing a broken .wav (no whisper), a broken .pdf (no markitdown/ocr) and an unsupported .xyz still returned status=ok, conversion tally {ok:2, failed:2}, 6 entities digested from the 2 good files; failures surfaced in the document manifest with status=failed. Every converter wraps its body in try/except returning a ConvResult (convert.py:84-95,124-137,140-171,174-197,200-228). The pool path isolates a crashed future and re-runs that one file on the main thread (digest.py:100-106), and a BrokenProcessPool degrades to fully sequential (digest.py:108-111). _safe_extract (digest.py:206-212) degrades a mid-run extractor failure to an empty Extraction.
- **Evidence:** convert.py:84-95,294-300; digest.py:96-111,206-219; verified with mixed good/bad corpus (tally ok:2 failed:2, 6 entities)
- **Recommendation:** None — robust. Strong design.

#### PIPE-07 — Fast mode is correctly deterministic, builds the graph, and preserves semantic recall
*Info · IMPLEMENTED*

- **Claim/expected:** README:108/233, cli.py:37-38 — "--fast skips the LLM for a fully deterministic digest that still builds the graph and keeps semantic recall".
- **Reality:** Verified. digest(fast=True) sets cfg.fast=True and forces extract_mode="classical" (digest.py:155-157), which gates off all LLM calls in extract (extract.py:133-139), _community_summary (digest.py:138) and _synopsis (digest.py:309). Embeddings are NOT skipped — recall vectors are still built (digest.py:281-284), using Ollama embeddings when available else the deterministic hash, so semantic recall is preserved. Two offline fast runs produced byte-identical node/edge/community/synopsis signatures (test_fast_mode_is_deterministic also passes). Caveat: "fully deterministic" is exactly true only with the hash embedder; with a live Ollama embedding model, vector values depend on the model (graph structure stays deterministic).
- **Evidence:** digest.py:155-157,281-284; config.py:139-141; extract.py:133-139; cli.py:37-38,67; server.py:48-56; verified: two fast runs byte-identical, stats.mode='fast', embed_mode='hash'
- **Recommendation:** Minor: note in docs that determinism is byte-exact in the hash-embedding path; structure is deterministic but vector values are model-dependent when Ollama embeddings are active.

#### PIPE-09 — Conversion process-pool parallelism is correct (spawn-safe payload, deterministic output names, main-thread fallback)
*Info · IMPLEMENTED*

- **Claim/expected:** digest.py:92-93 — parallel across performance cores; worker crash isolates one file; broken pool degrades to sequential.
- **Reality:** _convert_worker is a top-level function and the payload is a 4-tuple of picklable values (Config is a plain dataclass), so it pickles under spawn (verified by the 2-file sample digest running with worker_count=4 and by test_convert_worker_accepts_payload). Output filename collisions are resolved race-free in the main process before dispatch via _assign_output_names with a deterministic sha1 suffix (digest.py:65-82), preventing silent overwrite of same-basename files (test_same_basename_no_data_loss passes). Workers pin native threads to avoid BLAS oversubscription (digest.py:60-62, platform.py:103-106). worker_count clamps by performance cores AND unified memory (platform.py:89-100).
- **Evidence:** digest.py:58-62,65-82,89-111; platform.py:89-106; verified worker_count(0)=4 on host, sample digested via pool, all parallelism tests pass
- **Recommendation:** None. Note (not a defect): the parallel _convert_worker path constructs a fresh OllamaManager per process for image vision rather than sharing one, which is unavoidable across processes and harmless.

#### PIPE-11 — Atomic persistence of graph.json and vectors prevents corruption on crash mid-materialise
*Info · IMPLEMENTED*

- **Claim/expected:** store.py:24-30 — writes are durable (temp→fsync→os.replace); a crash leaves the previous valid file intact.
- **Reality:** save_graph and save_vectors both write to a same-dir temp file, fsync, then os.replace; on any BaseException the temp is unlinked and the error re-raised (store.py:24-44,75-93). load_graph refuses a future incompatible schema version rather than returning garbage (store.py:56-72). Verified test_atomic_graph_write_leaves_no_temp passes (no .tmp residue). This means the final materialise step (digest.py:278-289) cannot leave a half-written graph.json that would break a subsequent recall/overview.
- **Evidence:** store.py:24-49,75-93; digest.py:278-289; test_atomic_graph_write_leaves_no_temp passes
- **Recommendation:** None — exemplary.

#### PIPE-12 — Segmentation hard-splits oversize sentences and carries provenance, avoiding silent tail loss
*Info · IMPLEMENTED*

- **Claim/expected:** segment.py:39-44 — without hard-splitting, an unpunctuated blob becomes one giant chunk and the extractor's input cap silently drops the tail.
- **Reality:** _split_oversize breaks an over-long sentence on whitespace near the limit (segment.py:39-56); test_segment_hard_splits_oversize confirms a 20k-char unpunctuated blob yields >10 chunks each ≤1400 chars. Heading-aware splitting keeps chunks from straddling sections and every Chunk carries doc + heading_path (segment.py:73-110), which flows into facts/recall provenance (graph.py:58, digest.py:331). One minor smell: flush() silently discards chunk pieces < 8 chars (segment.py:91) — intentional noise filtering, negligible content loss. The extractor input is also capped at 6000 chars (extract.py:88), so an individual chunk larger than that (only possible if chunk_chars is raised well above default 1200) would still lose its tail — but at default settings chunks are ~1200 chars, well under the cap.
- **Evidence:** segment.py:39-56,73-110; extract.py:88; graph.py:58; digest.py:331; test_segment_hard_splits_oversize passes
- **Recommendation:** None at default config. If MTA_CHUNK_CHARS is ever set above ~5000, align the extractor input cap (extract.py:88) with chunk_chars to avoid tail loss.

### Recall, render & materialisation (RECALL)

The recall and render paths are well-engineered and largely live up to the README's token-free, offline, portable promises. Recall embeds the query locally, scores by cosine against stored theme/entity units, and returns a hard-capped slice (k clamped to 1..50, per-hit text ≤600 chars, ≤5 docs) with provenance — whole documents are never returned. The mindmap is genuinely self-contained (a real 373KB Cytoscape.js is inlined into mindmap.html with the CDN only as a dev fallback) and graph.json is version-stamped with basename-only provenance, so the portability claim holds. The two real caveats: (1) recall hit text can contain verbatim source sentences because classical-mode "facts" are raw document sentences — bounded and arguably intended, but a nuance vs the "document contents never return" wording; and (2) top_score can report a pre-filter score that matches none of the returned hits when MTA_RECALL_MIN_SCORE drops everything. Nothing here is a token-free leak, data-loss, or offline-blocker.

**Strengths:**

- Recall is hard-capped at multiple layers (k clamped 1..50, per-hit text ≤600 chars, ≤5 docs with overflow count), enforced independently of embedding mode — the token-free guarantee holds on both the accurate and offline paths (recall.py:20-41, tests/test_smoke.py:315-323).
- mindmap.html is truly self-contained: a real 373KB Cytoscape.js (Consortium build) is inlined, the template references zero external URLs, and the unpkg CDN is only a defensive fallback if the bundled asset is somehow missing (render.py:148-154, assets/cytoscape.min.js, templates/mindmap.html.j2).
- Strong XSS hardening in the inlined graph data: '</' is escaped to '<\/' before inlining and all untrusted labels/summaries render via textContent, not innerHTML (render.py:146-147, mindmap.html.j2:46-48).
- graph.json portability is real and verified: version-stamped with a load-time schema guard, and every persisted path field is a basename (provenance header, document name/output, node/fact docs all derive from Path(...).name) — resolve() is used only for in-memory dedupe keys, never written (digest.py:257,406; convert.py:303; segment.py:114; graph.py:39,58; store.py:66-72).
- export_memory bundles the full portable set including BOTH vector files (vectors.npz + vectors.json), so semantic recall works from a copied bundle; bad destinations return a status object instead of throwing (render.py:181-197, tests/test_smoke.py:399-407).
- Query embedding mirrors digest exactly (same model, matching nomic search_query/search_document prefixes) and degrades cleanly to lexical overlap on a dimension mismatch rather than crashing (recall.py:50-52, embed.py:74-79).
- Recall units themselves are bounded at the source: ≤25 facts per node and num_predict-capped LLM summaries, so even before the per-hit truncation the stored slice can't balloon (graph.py:18, digest.py:122).

#### RECALL-02 — Recall hit text can contain verbatim source sentences (classical-mode facts)
*Medium · PARTIAL*

- **Claim/expected:** README repeatedly: 'document contents never return to the conversation'; recall returns 'theme summaries + entity cards with provenance — never whole documents.'
- **Reality:** In classical extraction, facts are raw document sentences (extract.py:79 splits the chunk text into sentences verbatim). Those facts are stored on nodes (graph.py:58) and concatenated into the recall entity-card text (digest.py:328-329: card = f"{label} ({type}). {facts}"), which is returned as hit['text']. So recall CAN echo verbatim source prose. It is bounded (≤600 chars/hit, ≤25 facts/node, k≤50) and is arguably the intended 'citable fact' behaviour, but it is not literally 'document contents never return' — short verbatim spans do return. The LLM path paraphrases facts (num_predict capped), so this is most pronounced in fast/offline mode.
- **Evidence:** mta/core/extract.py:79; mta/core/graph.py:18 (_MAX_FACTS_PER_NODE=25), :58-67; mta/core/digest.py:327-332; mta/core/recall.py:27
- **Recommendation:** Reframe the README claim to 'whole documents / large spans never return; recall returns short, bounded, citable fact snippets' — the code already enforces the bound, so this is a wording/expectation fix, not a leak.

#### RECALL-03 — top_score reported even when MTA_RECALL_MIN_SCORE drops all hits (mismatch with returned hits)
*Low · PARTIAL · quick-win*

- **Claim/expected:** README: each recall result includes top_score and low_confidence so Claude can decline; MTA_RECALL_MIN_SCORE drops weak hits.
- **Reality:** When embedder.mode=='ollama' and recall_min_score filters out every hit, hits becomes empty but top = hits[0]['score'] if hits else raw_top falls back to raw_top — the best PRE-filter score. So the response reports a confident-looking top_score (e.g. 0.4) with an empty hits list. low_confidence is correctly True in that case, but top_score no longer corresponds to anything returned and could mislead a consumer reading top_score alone. The (not hits) short-circuit in low_conf is correct (no IndexError).
- **Evidence:** mta/core/recall.py:57 (raw_top), :62-68 (filter + low_conf + top fallback)
- **Recommendation:** When the floor filters everything, set top_score to 0.0 (or to the surviving best, i.e. 0.0 when empty) so top_score is consistent with the returned hits; keep raw_top only as a separate diagnostic if desired.

#### RECALL-10 — low_confidence semantics: flagged only on the real-embedding path, by design
*Low · IMPLEMENTED*

- **Claim/expected:** README: 'recall reports a low_confidence signal so Claude can decline when the answer isn't in your docs'; 'Each recall result includes top_score and a low_confidence flag.'
- **Reality:** low_confidence is computed only when embedder.mode=='ollama': True if nothing survived the floor or the best surviving score < 0.5 (recall.py:62-67). On the hashing-fallback path (no Ollama / MTA_NO_OLLAMA), low_confidence stays False and no score floor is applied — intentional, since hash cosine is on a different scale and a 0.5 threshold would be meaningless. Consequence: in fully-offline mode (the README's headline 'works with no models' scenario), low_confidence is always False, so the 'decline when not in your docs' affordance is effectively absent offline. The lexical fallback branch (recall.py:75-86) returns neither top_score nor low_confidence keys at all.
- **Evidence:** mta/core/recall.py:60-72 (ollama-only), :75-86 (lexical branch omits both keys); README.md:113,235
- **Recommendation:** Document that low_confidence/top_score are meaningful only with real embeddings, and consider emitting low_confidence:true (or a 'mode':'hash' caveat) plus top_score in the hash/lexical branches so consumers always get a consistent shape and aren't misled into trusting an unscored hash result.

#### RECALL-01 — Recall returns only a hard-capped slice (per-hit text and doc caps + k clamp)
*Info · IMPLEMENTED*

- **Claim/expected:** README: 'recall returns a small, hard-capped slice (a few summaries/facts)'; 'Tool results are hard-capped in size, so the guarantee holds even on the high-accuracy path.'
- **Reality:** Per-hit text is truncated to _MAX_HIT_TEXT=600 chars and docs to _MAX_HIT_DOCS=5 (with doc_count overflow), and k is clamped to max(1,min(k,50)) regardless of caller input. Caps are independent of embedding mode, so they hold on both the Ollama and hashing paths. Unit test test_recall_hit_is_bounded exercises this.
- **Evidence:** mta/core/recall.py:20-21 (caps), :24-30 (_hit truncation), :37-41 (k clamp); tests/test_smoke.py:315-323
- **Recommendation:** None — this is a genuine strength backing the token-free claim.

#### RECALL-04 — mindmap.html is genuinely self-contained / offline (real Cytoscape inlined, CDN only a dev fallback)
*Info · IMPLEMENTED*

- **Claim/expected:** README: 'a single self-contained mindmap.html (Cytoscape inlined, zero network)'; 'offline interactive graph (Cytoscape inlined).'
- **Reality:** assets/cytoscape.min.js is the real library (373,304 bytes, Cytoscape Consortium header). render.write_mindmap reads it and inlines it as <script>...</script> into the template's /*__CYTOSCAPE__*/ slot; the data is inlined at /*__DATA__*/. The template itself loads no external resources (no <script src>, no link/font/img to a URL). The unpkg CDN <script src> is used ONLY if the bundled asset is missing (defensive fallback), which won't happen in a normal install/dev checkout since _asset() resolves both wheel and repo layouts.
- **Evidence:** assets/cytoscape.min.js (373304 bytes, copyright header); mta/core/render.py:37,148-154 (inline), :149-150 (CDN only when cyto empty); templates/mindmap.html.j2:26,39-80 (no external refs); _asset resolution mta/core/render.py:19-37
- **Recommendation:** Strength. Optionally drop the unpkg fallback entirely (or guard it behind an env flag) to make 'zero network' unconditional, since shipping without the asset would be a packaging bug anyway.

#### RECALL-05 — XSS/script-breakout hardening in the inlined mindmap data block
*Info · IMPLEMENTED*

- **Claim/expected:** README threat model: 'prompt-injection data-delimiting' and hardened processing of untrusted files; mindmap renders entity labels from untrusted documents.
- **Reality:** render escapes '</' to '<\/' in the JSON data blob before inlining (so a label containing </script> cannot break out of the inline <script>), and the template renders all label/summary text via textContent (esc() uses a div + textContent), not innerHTML, preventing HTML/JS injection from entity labels into the panel. The _fallback_html path applies the same </ escaping.
- **Evidence:** mta/core/render.py:146-147 (</ escape), :162 (fallback escape); templates/mindmap.html.j2:46-48 (esc via textContent), :41-45 (textContent assignments)
- **Recommendation:** None — good defensive rendering.

#### RECALL-06 — render emits memory.md + per-document notes + graph.json + mindmap.html
*Info · IMPLEMENTED*

- **Claim/expected:** README: digest produces 'a global synopsis, per-theme summaries, per-document notes, an exportable Markdown bundle, and an offline interactive mind map'; generated files table lists memory.md, memory/<doc>.md, mindmap.html.
- **Reality:** digest calls render.write_memory_md (synopsis→themes→key facts→documents index), render.write_doc_memories (one <stem>.md per ok document, grouping entities+facts), and render.write_mindmap. graph.json is written by store.save_graph before vectors/render. memory.md uses only basenames (Path(...).name) for doc references. test_digest_end_to_end asserts all four artefacts exist.
- **Evidence:** mta/core/digest.py:278 (save_graph), :287-289 (three render calls); mta/core/render.py:40-78 (memory.md), :81-117 (per-doc notes), :129-158 (mindmap); tests/test_smoke.py:54-58
- **Recommendation:** None — materialisation matches the spec.

#### RECALL-07 — graph.json is version-stamped and contains no absolute paths (portability)
*Info · IMPLEMENTED*

- **Claim/expected:** README: 'graph.json — source of truth ... (version-stamped, no absolute paths)'; projects are 'self-contained and portable', copyable to another machine.
- **Reality:** graph_doc sets version=1 (digest.py:257) and load_graph refuses a future schema (store.py:53,66-72). All path-like fields are basenames: documents[].name comes from the '<!-- source: <basename> -->' header (convert.py:303 uses path.name; digest _parse_md_header recovers it), documents[].output = md.name (basename, digest.py:406), node docs = chunk.doc = Path(md_path).name (segment.py:114; graph.py:39), fact doc = chunk.doc (graph.py:58). The Path(...).resolve() calls in digest are used only for in-memory dedupe keys and hash suffixes (digest.py:38,78), never persisted. graph.json also stores a 'created' epoch int — a timestamp, not a path, so portability is unaffected.
- **Evidence:** mta/core/digest.py:257,392 (comment), :406; mta/core/convert.py:303; mta/core/segment.py:114; mta/core/graph.py:39,58; mta/core/store.py:53,66-72; README.md:209
- **Recommendation:** None — the no-absolute-paths and version-stamp claims are verified.

#### RECALL-08 — export_memory bundles memory.md, graph.json, mindmap.html, per-doc notes AND the vector store
*Info · IMPLEMENTED*

- **Claim/expected:** README: 'export_memory bundles all of the above (including the vector store) into a folder'; tool doc: 'export portable Markdown + graph + mind map'.
- **Reality:** export_bundle copies memory.md, graph.json, mindmap.html, vectors.npz and vectors.npz->.json (the sidecar metadata), plus the entire memory/ notes dir (copytree, replacing any stale target). Missing sources are skipped; an unwritable dest returns {status:error} instead of throwing (test_export_to_bad_dest_returns_status). Including vectors.json+npz means semantic recall works from the exported bundle, not just human browsing. Empty source set returns no_memory.
- **Evidence:** mta/core/render.py:174-197 (esp. :181-182 sources incl. vectors + sidecar, :186-190 memory dir); tests/test_smoke.py:399-407
- **Recommendation:** None. Note: the sidecar is referenced via vectors_path.with_suffix('.json') (→ vectors.json), matching store.save_vectors; consistent.

#### RECALL-09 — Query is embedded locally with the same model/prefix as digest; dimension-mismatch degrades to lexical
*Info · IMPLEMENTED*

- **Claim/expected:** recall.py docstring: 'query is embedded with the same local model used at digest time, scored by cosine against the stored recall units ... top-k units returned with provenance.'
- **Reality:** recall embeds [query] with kind='query' (Embedder applies the nomic 'search_query:' prefix to match the 'search_document:' prefix used at digest, embed.py:74-79), computes cosine against the stored matrix, argsorts top-k, and builds hits with score/kind/label/text/docs (provenance). If the query-embedding width != stored matrix width (backend changed since digest, e.g. Ollama present now vs hash at digest time), it cleanly degrades to lexical token-overlap rather than crashing. Embedding/cosine never return text — only numeric vectors (embed.py module docstring + return types).
- **Evidence:** mta/core/recall.py:47-56,69-72; mta/core/embed.py:74-79,81-113,115-119
- **Recommendation:** None — the recall mechanism is correct and degrades safely.

### Dependency model, platform detection & auto-update (DEP)

Platform detection (platform.py) is competent for its actual purpose — pool sizing on Apple silicon — detecting OS, arch, Apple-silicon vs other, performance cores, RAM and MLX-Whisper availability, all with clean cross-platform fallbacks. However it does NOT detect discrete GPU/CUDA (that logic lives separately in convert.py via nvidia-smi), never surfaces GPU in summary(), and there is no LM Studio detection. The Ollama lifecycle correctly distinguishes "self-started" from "reused" via a _started_by_us flag and only stops what it launched, but it cannot tell a user-launched Ollama from one a prior server instance started, and has a TOCTOU race on concurrent starts. config.py resolves everything from MTA_* env vars with safe defaults but does NOT persist resolved config to disk and has NO named profiles (laptop/workstation/server/offline) — those are entirely MISSING. There is NO preflight dependency scanner reporting detected-vs-required versions; memory_status/mta status report only booleans plus the MarkItDown version. updater.py performs dependency upgrade (MarkItDown + pip deps) but its "self-update" is report-only (it fetches the latest GitHub release tag and never applies it), is pip-only (no per-platform managers, no --dry-run, no idempotent guided remediation), has NO integrity verification (no hash/signature before install) — a High/Critical gap — and NO atomic rollback. It does respect offline (MTA_NO_OLLAMA at the model layer) and MTA_AUTO_UPDATE=off, is throttled ~daily, and never runs synchronously on the request path. Notably the README is honest and does not over-claim doctor/profiles/version-scanning, so most gaps are capability shortfalls vs the audit brief rather than README contradictions.

**Strengths:**

- Ollama lifecycle is genuinely careful: stop() only tears down an instance this tool started (_started_by_us gate) and reaps the whole process tree via psutil to avoid orphaning the child runner / holding the port (lifecycle.py:104-149), backing the README's 'your Ollama is left alone' promise in the common case.
- Fully offline-capable: MTA_NO_OLLAMA short-circuits is_up()/ensure_running() (lifecycle.py:48-57,74-78) and the engine degrades to hashing embeddings + classical extraction, so a digest can succeed with zero network/models — the token-free/offline core promise holds (tests/test_smoke.py:13,52).
- Auto-update is correctly non-blocking and opt-out: start_background() spawns a daemon thread and is gated on cfg.auto_update + daily throttle, never touching the network on the request path (updater.py:91-102); MTA_AUTO_UPDATE=off is honored via Config.auto_update (config.py:79-80, updater.py:73).
- Platform tuning is well-reasoned and portable: performance-core sizing on Apple silicon with psutil/os.cpu_count fallbacks, unified-memory-aware worker clamping (~2GB/worker), and BLAS/OpenMP thread pinning to avoid oversubscription (platform.py:46-106) — the Apple-silicon-first claim is real and degrades cleanly on Linux/Windows.
- bootstrap_path() robustly heals a sparse PATH for both POSIX (Homebrew/snap/~/.local) and Windows (Ollama/Tesseract/ffmpeg/WinGet/scoop/choco locations) so CLI tools resolve when launched by Claude Desktop (platform.py:124-150).
- Config is clean and declarative: every knob is an MTA_* env var with type-safe parsers and safe defaults, no network/model access in the module, and project names are slugified/length-capped to stay filesystem-safe (config.py:15-37,87-92).
- Launch/MCP wiring is argv-only (no shell-string interpolation) in both .mcp.json and manifest.json, and launch.py/launch.sh self-bootstrap a venv before starting the server, handling the Windows Scripts/ vs bin/ layout (launch.py:20-56, .mcp.json:4-5, manifest.json:23-24).
- install.sh download-then-execute pattern for the Ollama installer (mktemp + verify-then-`sh`, not curl|sh) avoids running partial/garbled output (install.sh:75-78,83-86), and it pins Python to 3.12 to dodge missing 3.14 wheels (install.sh:15-31).

#### DEP-01 — No integrity verification (hash/signature) before installing upgrades
*High · MISSING*

- **Claim/expected:** updater.py header: upgrades MarkItDown 'straight from upstream microsoft/markitdown' and 'refreshes the rest of the dependency set' (updater.py:1-9); README: only network access is downloading deps/models and a daily update check (README.md:219).
- **Reality:** update_markitdown() runs `pip install -U 'markitdown[all] @ git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown'` with no pinned commit, no hash, no signature/GPG/sigstore check before applying. _pip() just shells pip and trusts the network result (updater.py:47-58, 24-25). Grepped: no sha256/signature/verify/checksum in updater.py. Any compromise/MITM of the upstream git ref or PyPI is installed unverified into the venv the server runs from.
- **Evidence:** mta/core/updater.py:24-25 (unpinned git spec), 47-58 (_pip/update_markitdown), 56-58; absence: no hash/signature code anywhere in updater.py.
- **Recommendation:** Pin MarkItDown to a known commit/tag and verify pip hashes (pip --require-hashes against a generated requirements lock), or at minimum pin a vetted release and surface the resolved version. For any self-update, verify a release asset checksum/signature before applying.

#### DEP-02 — "Self-update" of the extension/plugin is report-only — it is never applied
*Medium · PARTIAL*

- **Claim/expected:** updater.py module docstring: 'then reports whether a newer release of this tool exists' (updater.py:1-9); brief expects updater to do BOTH dependency update AND self-update.
- **Reality:** latest_self_release() fetches the GitHub 'releases/latest' tag and run_check() returns it as latest_release alongside current version (updater.py:61-83). Nothing ever downloads/installs that release: grep for tarball/zipball/git pull/reinstall/pip install of SELF_REPO returns nothing. So the plugin self-update is detection-only; the user must manually upgrade. Dependency update (MarkItDown) IS applied, so the two halves are asymmetric.
- **Evidence:** mta/core/updater.py:61-69 (fetch tag only), 71-83 (run_check returns latest_release/current); absence: no code consumes latest_self_release beyond reporting (grep latest_release → updater.py:61,82 only).
- **Recommendation:** Either implement a verified self-update (download release asset, verify checksum, atomic swap) or document clearly that plugin upgrades are manual; align the docstring which implies more than it does.

#### DEP-03 — No atomic upgrade or rollback for dependency updates
*Medium · MISSING*

- **Claim/expected:** updater.py: 'Upgrades are installed into the active virtualenv and take effect on the next launch' (updater.py:1-9).
- **Reality:** update_markitdown() runs a single `pip install -U` in-place against the live venv (updater.py:56-58, 47-54). There is no snapshot of prior versions, no transactional staging, and no rollback if the new MarkItDown breaks import or conversion. A failed/partial upgrade (e.g. interrupted pip, an upstream regression) leaves the venv in whatever state pip ended in until the next daily attempt. The README's 'atomic' guarantee (README.md:113) applies only to memory/graph writes (store._atomic_write_text), not to dependency upgrades.
- **Evidence:** mta/core/updater.py:56-58, 47-54; README.md:113 (atomic claim scoped to memory, not deps); mta/core/store.py:24,49 (atomic writes are graph-only).
- **Recommendation:** Capture pre-upgrade `pip freeze` of the affected packages; on post-upgrade import smoke-failure, reinstall the captured versions. Or stage into a temp venv and swap only on success.

#### DEP-04 — No dependency preflight scanner with detected-vs-required versions
*Medium · MISSING · quick-win*

- **Claim/expected:** Brief expects a preflight scanner reporting present-&-current / outdated / missing WITH detected vs required versions, surfaced in memory_status / mta status / mta doctor.
- **Reality:** _status() (the body of both memory_status and `mta status`) reports only booleans for tesseract/ffmpeg (shutil.which), ollama_running, the list of pulled ollama models, and a single markitdown version string (server.py:117-147). It never reads requirements.txt minimums, never compares installed vs required versions for numpy/networkx/rapidfuzz/psutil/pdfplumber/etc., and never classifies deps as present/outdated/missing. There is NO `mta doctor` subcommand (cli.py:34-59 lists digest/recall/overview/export/status/mindmap/update/forget/serve only). Grepped repo for preflight/outdated/required_version/detected_version → none.
- **Evidence:** mta/server.py:117-147 (_status fields); mta/cli.py:34-59 (no doctor); requirements.txt:5-21 (minimums never consulted at runtime); absence: grep preflight/outdated/detected.*version → no matches.
- **Recommendation:** Add a doctor/preflight that reads requirements.txt floors and importlib.metadata.version() per package, emitting present-current / outdated / missing with both numbers; surface it in `mta status`/memory_status.

#### DEP-08 — Ollama 'reused vs self-started' cannot survive across server processes; reuse flag is per-instance only
*Medium · PARTIAL*

- **Claim/expected:** README: 'a running Ollama is reused and left alone. Only an instance this tool starts is stopped on idle' (README.md:231); lifecycle docstring: 'A user's own / brew Ollama is detected and left untouched' (lifecycle.py:1-11).
- **Reality:** _started_by_us is in-memory per OllamaManager instance (lifecycle.py:42,94,114-123). is_up() only HTTP-probes the configured host (lifecycle.py:54-57) — it has no way to tell a user-launched Ollama from one started by a *different* prior/concurrent instance of this server. The stop() path is correctly gated on _started_by_us so it won't kill a reused server in the common case, which is good; but if process A starts Ollama and exits without cleanly stopping (e.g. SIGKILL), process B sees it 'up', treats it as reused, and never reclaims it — and two processes can both decide to start it (the watchdog/start path is lock-protected only within one process). The cross-process activity marker (last_use mtime) is shared, but ownership is not.
- **Evidence:** mta/core/lifecycle.py:42 (per-instance flag), 54-57 (is_up probes host only), 74-102 (ensure_running; intra-process lock only), 104-123 (stop gated on _started_by_us); README.md:231.
- **Recommendation:** Record ownership in a state file (pid + started flag) so any instance can determine whether *this tool* owns the running Ollama, and serialize start across processes with a file lock.

#### DEP-10 — System-package install is bash-only with no Windows path; no --dry-run; relies on non-interactive sudo
*Medium · PARTIAL*

- **Claim/expected:** README claims Windows is supported (README.md:17,110) and lists apt/dnf/pacman Linux paths (README.md:198); install is meant to be idempotent and safe to re-run (install.sh:2-7).
- **Reality:** install.sh covers brew (macOS/Linux), apt, dnf, pacman for tesseract/ffmpeg/ollama (install.sh:64-92) and is reasonably idempotent (guards each install with `command -v`). But it is a bash script with NO Windows equivalent (no .ps1/.bat/.cmd in repo) — on Windows users must `pip install` + run `mta serve` manually (README.md:199 marks Windows 'experimental'), so winget/choco/scoop are never driven despite platform.py healing those PATHs (platform.py:134-142). There is no --dry-run anywhere, and elevation depends on passwordless `sudo -n`; if sudo would prompt, system deps are silently skipped with a log line (install.sh:61-63,90-92) — graceful, but not a guided no-admin remediation. Launch is argv-only (bash launch.sh / python launch.py; no shell-string injection) which is good.
- **Evidence:** install.sh:64-92 (brew/apt/dnf/pacman; no winget/choco/scoop, no Windows branch), 61-63 (sudo -n only), 90-92 (skip on no pkg mgr); README.md:199 (Windows experimental/manual); absence: find *.ps1/*.bat/*.cmd → none; .mcp.json:4-5 & manifest.json:23-24 (argv-only launch).
- **Recommendation:** Add a Windows bootstrap (PowerShell driving winget/choco/scoop, matching the PATHs platform.py already heals) and a --dry-run mode to the installer; surface a no-admin remediation message listing exact manual commands.

#### DEP-05 — No named configuration profiles (laptop/workstation/server/offline)
*Low · MISSING · quick-win*

- **Claim/expected:** Brief expects named profiles; config.py is the place defaults are resolved.
- **Reality:** Config resolves each knob independently from MTA_* env vars (config.py:39-91); there is no notion of a profile that bundles a coherent set of defaults. Grepped repo for laptop/workstation/profile/preset → no matches. Users must set each MTA_* var individually. (MTA_FAST is a single boolean, not a profile.)
- **Evidence:** mta/core/config.py:39-91 (per-field env resolution), 63-64 (MTA_FAST is the only bundled-ish toggle); absence: grep laptop|workstation|profile|preset --include=*.py → none.
- **Recommendation:** Optional: add MTA_PROFILE=laptop|workstation|server|offline that seeds a documented default set, still overridable by explicit MTA_* vars.

#### DEP-06 — Resolved configuration is never persisted to disk
*Low · MISSING · quick-win*

- **Claim/expected:** config.py docstring: 'read entirely from the environment with safe defaults' (config.py:1-6).
- **Reality:** load() builds a fresh Config from the environment on every invocation and returns it; nothing writes the resolved config out. Grepped config.py/platform.py for json.dump/write_text/save/persist on config → only store.py persists the graph/vectors, render.py persists memory.md, updater.py writes the throttle stamp. So a digest run's effective settings (models, workers, modes) are not recorded for reproducibility/auditing.
- **Evidence:** mta/core/config.py:137-141 (load returns fresh Config, no write); absence: grep save_config/persist/to_json in config.py → none; contrast store.py:24,49 / render.py:77 which DO persist data.
- **Recommendation:** Optionally write the resolved Config (minus secrets — there are none) to home/state for diagnostics and to detect drift between runs.

#### DEP-07 — GPU/CUDA not detected in platform layer; summary omits GPU; no LM Studio detection
*Low · PARTIAL · quick-win*

- **Claim/expected:** platform.py docstring: 'detects whether GPU-accelerated Whisper via Apple MLX is available' (platform.py:1-8); README: 'CUDA Whisper if a GPU is present' on Linux (README.md:198).
- **Reality:** platform.py detects only MLX (Apple) via mlx_available() (platform.py:109-118) and never detects NVIDIA/CUDA — the CUDA decision is made ad hoc inside convert.py via shutil.which('nvidia-smi') (convert.py:214-216), so summary()/memory_status report no GPU/CUDA at all (platform.py:153-161). No detection of an existing LM Studio (only Ollama is probed). RAM, cores, arch, Apple-silicon ARE detected correctly.
- **Evidence:** mta/core/platform.py:109-118 (MLX only), 153-161 (summary lacks GPU/CUDA); mta/core/convert.py:214-216 (CUDA detection lives here, not in platform); absence: grep cuda|nvidia in platform.py → none; grep lm.?studio → none.
- **Recommendation:** Centralise GPU detection (nvidia-smi/CUDA + MLX) in platform.py and include it in summary()/memory_status so capability reporting matches the README's CUDA claim.

#### DEP-09 — Daily-throttle stamp is racy/non-atomic across concurrent launches
*Low · PARTIAL · quick-win*

- **Claim/expected:** updater.py: stamp is written BEFORE work 'so a second process (Desktop + Code both launching) sees the throttle and doesn't race a concurrent pip install into the same venv' (updater.py:77-80).
- **Reality:** _touch() does a plain write_text of the timestamp (updater.py:42-44) and _due() reads st_mtime (updater.py:34-39); there is no file lock or atomic create. Two processes that both pass _due() before either touches will both proceed (check-then-act TOCTOU). The stamp-before-work ordering shrinks but does not close the window, so concurrent `pip install -U` into the same venv remains possible on simultaneous cold starts — exactly the corruption the comment aims to prevent. Functionally it works for the steady-state daily case.
- **Evidence:** mta/core/updater.py:34-44 (_due/_touch non-atomic), 71-83 (run_check check-then-touch), 91-102 (start_background also _due-gated, no lock).
- **Recommendation:** Use an atomic O_CREAT|O_EXCL lock file or os.replace of a temp stamp to make the throttle check-and-claim atomic across processes.

### Lifecycle & concurrency

The single-process lifecycle story is solid and genuinely token/leak-conscious: Ollama is started lazily on first model activity, only stopped if THIS process started it (never the user's own/brew instance), and the watchdog plus atexit cleanly tears down the whole process tree via psutil. Activity tracking via a cross-process marker mtime is a reasonable idea, but the idle timer has a real correctness bug (the watchdog and the marker are decoupled across processes, so the only process that can stop Ollama may never see the marker it itself never touches, and conversely a busy worker in another process can be killed mid-work). The bigger gap vs the R5 promise is the total ABSENCE of cross-process locking: nothing serializes two clients sharing one MTA_HOME/project, so concurrent digests on the same project race on shared markdown/graph/vectors files (interleaved partial writes, torn graph vs vectors pairing, double-started Ollama is mostly mitigated by an HTTP re-check but not the data races). Persistence (R6) is the strongest area: graph.json and vectors.npz both use atomic temp-file+fsync+os.replace, the npz load relies on numpy's safe allow_pickle=False default, and there is a forward-compatibility version guard. However the schema is only nominally "versioned" — there is NO migration, NO backup, NO rollback; a future-version store is simply refused (returns None → silently treated as "no memory"), which contradicts the "old memories stay read-recallable" promise.

**Strengths:**

- Atomic, durable persistence: both graph.json and vectors.npz use temp-file + flush + fsync + os.replace with temp cleanup on failure (store.py:24-44, :79-93), so readers never see torn files and a crash leaves the prior valid file intact.
- Ownership-correct service control: Ollama is only spawned when not already reachable, and stop() is hard-gated on _started_by_us, so a user's own/brew Ollama is detected and never terminated (lifecycle.py:79-94, :114).
- Thorough anti-orphan teardown on the atexit path: psutil tears down the whole 'ollama serve' process tree (terminate→kill) and also reaps the Popen handle to avoid zombies (lifecycle.py:104-149).
- Safe npz loading: np.load is used without allow_pickle=True and the payload is a plain float32 matrix from savez_compressed, so a malicious store cannot execute code (store.py:82-84, :101).
- Forward-compatibility guard plus defensive parsing on the user-editable graph.json: a future-version or non-numeric version is refused rather than mis-read, and malformed JSON returns None instead of crashing (store.py:56-72).
- Hard offline switch MTA_NO_OLLAMA short-circuits is_up/ensure_running so air-gapped/CI runs never touch the network or spawn anything (lifecycle.py:48-51, :55-57, :76-77).
- Per-call Config construction means the in-place with_project mutation cannot race across concurrent tool calls (config.py:137-141, server.py:41).
- Digest is resilient to mid-run model failure: extraction degrades a failing chunk to empty and the updater/conversion pools degrade to sequential, so partial offline failures don't abort an in-progress digest (digest.py:206-219, :103-110).

#### LIFE-01 — No cross-process locking anywhere — concurrent clients sharing one MTA_HOME/project race on shared files
*Critical · MISSING*

- **Claim/expected:** R5 concurrency safety: multiple clients sharing one MTA_HOME/project should have single-writer/multi-reader cross-process locking; no torn reads, no double-started servers, no deadlocks.
- **Reality:** There is no file lock, flock/fcntl, msvcrt, PID file, or any cross-process mutex in the entire package. Grepped: only matches are concurrent.futures (in-process pools) and a single threading.Lock in lifecycle.py:46, which is per-process only. Two host apps (Claude Desktop + Claude Code) run as SEPARATE OS processes, each with its own _OLLAMA singleton (server.py:30-37) and its own in-process lock. If both call digest() on the same project, _convert_all writes into the same cfg.markdown_dir (digest.py:86-87), then BOTH rebuild the graph from 'the FULL markdown corpus on disk' (digest.py:175) and BOTH call store.save_graph / store.save_vectors. Individual file writes are atomic, but the multi-file transaction is not: one writer's graph.json can end up paired with the other writer's vectors.npz, and an accumulative digest can lose/duplicate corpus relative to the graph. A reader (recall) loads vectors then separately loads graph (recall.py:42 then :69) with no lock, so it can observe a vectors/graph pair from two different writers.
- **Evidence:** Grep across mta/ for flock|fcntl|lockf|FileLock|msvcrt|\.pid|portalocker returned nothing; server.py:30-37 (per-process singleton); digest.py:86-87,175,278,284 (shared corpus + unsynchronised graph/vectors writes); recall.py:42,69 (load_vectors then load_graph, no lock)
- **Recommendation:** Add a cross-process advisory lock around the project: an exclusive lock held by digest()/_reset_project for the duration of a project's write transaction, and a shared lock (or atomic snapshot read) for recall/overview. Use filelock or a small fcntl/msvcrt wrapper keyed on cfg.project_dir; document the single-writer/multi-reader contract. At minimum, write graph.json + vectors.npz + vectors.json under one lock so readers never see a mismatched pair.

#### LIFE-02 — Idle watchdog is decoupled from cross-process activity — can kill a busy worker or fail to stop at all
*High · PARTIAL*

- **Claim/expected:** Idle timer is accurate, RESET on each activity, and correct under concurrent requests; Ollama stops after MTA_IDLE seconds of inactivity.
- **Reality:** Activity is recorded by writing the marker file's mtime (touch(), lifecycle.py:59-65) and the watchdog stops Ollama when time.time()-marker.mtime >= idle (lifecycle.py:67-71,157-162). The marker is a SINGLE shared file under cfg.state_dir (home/state/last_use, lifecycle.py:41) used by all processes, but only ensure_running() starts a watchdog and sets _started_by_us, and stop() no-ops unless _started_by_us is True (lifecycle.py:114). Two failure modes: (a) Process A starts Ollama (owns the watchdog + _started_by_us); Process B does all subsequent work and only B calls touch(). A's watchdog reads the shared marker, sees B's recent activity, and correctly stays up — BUT if B is busy for a long single request, A's watchdog can still fire because touch() is only called at the START of ensure_running (line 78) and after each completed HTTP call (digest.py:129, embed.py:92, extract.py:98, convert.py:193); a single long generate/transcribe (up to 180s, digest.py:127) past the idle window leaves the marker stale and the watchdog kills Ollama out from under the in-flight request. (b) If the owning process A exits while B keeps working, A's atexit fires stop() and tears down Ollama even though B is mid-digest, because nothing tells A that B started it or is using it. So the timer is reset per-completed-call, not per-activity-window, and is not correct under cross-process concurrency.
- **Evidence:** lifecycle.py:41 (single shared marker), :59-65 (touch writes mtime), :67-71 (idle = now - mtime), :74-102 (only ensure_running starts watchdog/sets _started_by_us), :104-124 (stop gated on _started_by_us, no cross-process refcount), :157-162 (watchdog loop); long synchronous calls at digest.py:127 (timeout=180), convert.py:177, extract.py:84
- **Recommendation:** touch() the marker BEFORE every blocking model call (not just after), and have the watchdog additionally verify the marker was not bumped during its sleep before stopping. For cross-process correctness, add a refcount/heartbeat (e.g. per-process heartbeat files under state_dir) so a process never stops an Ollama that another live process is still using, and so the owner's atexit doesn't kill it while peers are active.

#### LIFE-03 — Schema is version-GUARDED but has no migration, backup, or rollback — old/future stores are not kept read-recallable
*High · PARTIAL*

- **Claim/expected:** R6: graph.json / the memory store is a VERSIONED schema with automatic, atomic, backup+rollback migration of older stores so old memories stay at least read-recallable.
- **Reality:** There is a SCHEMA_VERSION constant (store.py:53) and graph_doc writes 'version': 1 (digest.py:257). load_graph only does a forward guard: if doc['version'] > SCHEMA_VERSION it returns None (store.py:66-72). There is NO migration code (grepped migrat|backup|rollback across mta/ → zero hits), so when SCHEMA_VERSION is eventually bumped, an OLDER store is not upgraded — it is just read as-is and assumed compatible (load returns it unchanged), and a NEWER store is silently discarded. Crucially, returning None is indistinguishable from 'no memory' to every caller: overview() → 'no_memory' (recall.py:90-92), recall() still works off vectors.npz (which has no version field at all, store.py:75-94) but loses the synopsis. So old memories are NOT guaranteed read-recallable across an incompatible bump, and there is no backup of the prior file before any future migration could overwrite it. The 'backup+rollback' part of the promise is entirely absent; only the atomic-write primitive exists (see LIFE-04).
- **Evidence:** store.py:52-53 (SCHEMA_VERSION=1), :56-72 (forward-only guard, returns None on future version, no migration branch), :75-94 (vectors.npz/json carry no version), digest.py:257 ('version': 1); recall.py:90-92 (None → no_memory); grep migrat|backup|rollback in mta/ → no matches
- **Recommendation:** Add an explicit migrate(doc) dispatch keyed on doc['version']; on a version bump, copy graph.json → graph.json.bak.v{old} before rewriting (backup), migrate in memory, write atomically, and on migration failure restore the .bak (rollback). Also stamp a version into the vectors sidecar. Distinguish 'unreadable/incompatible' from 'no memory' in caller status so a refused future store isn't silently reported as empty.

#### LIFE-07 — Clean shutdown via atexit + whole process-tree teardown (psutil) prevents orphaned Ollama runner
*Medium · PARTIAL · quick-win*

- **Claim/expected:** Clean shutdown on host exit / MCP termination via atexit/signal handlers; no orphaned processes; the child 'ollama serve' runner is fully reaped.
- **Reality:** atexit.register(self.stop) is set when we start Ollama (lifecycle.py:95); stop() terminates the whole tree via psutil (parent + recursive children, terminate then kill after 8s) and also reaps the Popen handle so it isn't left a zombie (lifecycle.py:104-149) — a well-thought-out anti-orphan path. GAP: cleanup relies ENTIRELY on atexit, which does NOT run on SIGTERM/SIGINT/SIGKILL or hard process death. A host (Claude Desktop/Code) that terminates the MCP server with SIGTERM — the normal way a parent kills a stdio child — will NOT trigger atexit, leaving the spawned 'ollama serve' (and its model runner holding the port and GPU/RAM) orphaned. There is NO signal.signal handler anywhere (grepped signal\.|SIGTERM|SIGINT → none). Also, if psutil is not installed, _terminate_tree returns False and stop() only proc.terminate()s the parent (lifecycle.py:115-116), risking an orphaned child runner on the platforms the docstring itself warns about.
- **Evidence:** lifecycle.py:95 (atexit only), :104-149 (tree teardown + Popen reap, psutil-dependent), :115-116 (fallback terminates parent only); grep signal\.|SIGTERM|SIGINT in mta/ → no matches
- **Recommendation:** Register signal handlers for SIGTERM/SIGINT (and on Windows, console-close) that invoke stop() before exit, in addition to atexit. Consider start_new_session=True / process-group kill as a psutil-free fallback so the child runner is reaped even without psutil.

#### LIFE-08 — Auto-updater can launch a background pip install on the request path; throttle stamp is a non-atomic cross-process gate
*Medium · PARTIAL*

- **Claim/expected:** Auto-update never blocks a digest and never races a concurrent pip install into the same venv (updater.py docstring + comment at updater.py:77-79).
- **Reality:** _cfg() (called by nearly every tool) fires updater.start_background on first activity (server.py:42-44), spawning a daemon thread that may run pip install -U into the active venv for up to 900s (updater.py:47-53,91-102). The throttle stamp is written BEFORE the work to deter a second process (updater.py:77-80), but the check-then-write is NOT atomic across processes: two host processes can both pass _due() (updater.py:34-39) before either writes the stamp, and both then run a concurrent pip install into the SAME venv — exactly the race the comment claims to prevent. A mid-flight pip install mutating site-packages while a digest imports markitdown/numpy can also break an in-progress run, so 'never blocks a digest' is true for the request thread but the side effects can still disrupt concurrent work. This is a lifecycle/concurrency hazard rather than a data-corruption one.
- **Evidence:** server.py:42-44 (start_background on every _cfg), updater.py:34-39 (_due read), :77-80 (stamp written before work, comment claiming race-safety), :47-53 (pip up to 900s), :91-102 (daemon thread)
- **Recommendation:** Guard the update with a cross-process lock (the same project/home lock from LIFE-01, or an O_CREAT|O_EXCL lock file) so only one process ever runs pip; make _due+_touch atomic. Optionally gate auto-update to a single 'owner' process or move it off the digest request path entirely (e.g. a separate maintenance command).

#### LIFE-04 — Atomic durable writes for graph.json and vectors.npz (temp + fsync + os.replace)
*Info · IMPLEMENTED*

- **Claim/expected:** R6: writes are atomic (temp-file + rename / atomic savez) so a reader never sees a half-written file and a crash leaves the previous valid file intact.
- **Reality:** _atomic_write_text writes to a mkstemp temp file in the same directory, flushes, fsyncs, then os.replace (atomic same-filesystem rename), with temp cleanup on any BaseException (store.py:24-44). save_graph uses it (store.py:47-49). save_vectors writes the .npz to an explicit temp file handle (avoiding numpy's .npz auto-suffix), fsyncs, os.replace, then writes the JSON sidecar atomically too (store.py:75-93). This correctly prevents torn single-file reads and preserves the prior valid file on crash. Caveat: the .npz and its .json sidecar are two separate atomic operations, so a crash between them can leave a new matrix with an old sidecar — but load_vectors requires both to exist and tolerates shape/parse errors by returning None (store.py:96-106), so this degrades safely rather than corrupting.
- **Evidence:** store.py:24-44 (_atomic_write_text fsync+os.replace), :47-49 (save_graph), :79-93 (save_vectors temp handle + fsync + os.replace, sidecar atomic), :96-106 (defensive load)
- **Recommendation:** Optional: write the npz matrix and meta into a single artifact (or embed meta inside the npz) so the pair is updated in one atomic replace, eliminating the cross-file crash window.

#### LIFE-05 — npz load relies on numpy's safe allow_pickle=False default; no untrusted pickle path
*Info · IMPLEMENTED · quick-win*

- **Claim/expected:** allow_pickle=False is used on numpy/npz loads (no arbitrary-code-execution via a malicious store).
- **Reality:** load_vectors calls np.load(cfg.vectors_path) WITHOUT allow_pickle=True (store.py:101). numpy's documented default has been allow_pickle=False since 1.16.3, and the stored array is a plain float32 matrix written via np.savez_compressed (store.py:82-84) which serialises as a non-pickled .npy inside the zip, so loading never requires or enables pickle. No code anywhere passes allow_pickle=True (grepped allow_pickle → only this single load site, no True). Note: numpy is not installed in this audit environment so I could not execute a live load to confirm the running numpy version's default; the assessment rests on numpy's stable documented behaviour and the absence of any allow_pickle=True override.
- **Evidence:** store.py:82-84 (savez_compressed of float32 matrix), :101 (np.load with no allow_pickle arg); grep allow_pickle in mta/ → only store.py:101, no =True anywhere
- **Recommendation:** Make the intent explicit and version-proof by passing allow_pickle=False at store.py:101 so it never silently re-enables if a future numpy changes the default or a refactor adds object arrays.

#### LIFE-06 — Stops only the Ollama this process started; user's own/brew Ollama is detected and never touched
*Info · IMPLEMENTED*

- **Claim/expected:** Stops ONLY services this tool started and NEVER the user's own Ollama/LM Studio.
- **Reality:** ensure_running first checks is_up() via an HTTP probe to /api/tags and returns immediately if Ollama is already reachable, WITHOUT setting _started_by_us or spawning a child (lifecycle.py:79-83). It only spawns 'ollama serve' and sets _started_by_us=True when nothing is reachable (lifecycle.py:89-94). stop() is hard-gated on _started_by_us and on owning a live self._proc (lifecycle.py:114), so a user's pre-existing/brew-managed Ollama (or any third-party server on the port) is never terminated. The watchdog likewise calls the same gated stop(). This correctly honours the 'never kill the user's Ollama' promise.
- **Evidence:** lifecycle.py:79-83 (return early if already up, no ownership), :89-94 (spawn + set _started_by_us only when not up), :104-124 (stop gated on _started_by_us and self._proc)
- **Recommendation:** None. (Note: LM Studio specifically is not separately probed, but since the manager only ever stops a process it itself spawned, an LM Studio server is never at risk regardless.)

#### LIFE-09 — Per-call Config is freshly constructed, so with_project() mutation does not race across tool calls
*Info · IMPLEMENTED*

- **Claim/expected:** Implicit: concurrent tool calls selecting different projects must not corrupt each other's active-project selection.
- **Reality:** with_project mutates self.project in place (config.py:89-92), which would be dangerous if a Config were shared. But every tool entry builds a brand-new Config via load_config().with_project(project) (server.py:41, cli.py:64), and load() returns a fresh dataclass instance each call (config.py:137-141). The only long-lived shared object, the _OLLAMA singleton, is constructed from its own separate load_config() (server.py:36) and holds no project state. So concurrent in-process tool calls for different projects each operate on independent Config instances — no shared-mutable-project race.
- **Evidence:** config.py:89-92 (in-place mutation), :137-141 (fresh instance per load), server.py:41 (per-call cfg), :36 (separate cfg for singleton), cli.py:64
- **Recommendation:** None. (Defensive nicety: with_project could return a copy to make the no-aliasing guarantee structural rather than incidental.)

### Security posture & supply chain

The runtime code is notably defensive for an attachment-processing tool: every subprocess is an argv-list (no shell=True, no curl|sh), output filenames are basename-derived so attacker-controlled names cannot traverse out of the markdown dir, collisions get a path-hash suffix, oversize files are capped, graph.json has schema-version guarding, and atomic writes prevent corruption. However, the README's security section (line 221) overstates the hardening on several concrete points. The decompression-bomb guard only covers literal .zip and is fully bypassed for the other ZIP-container formats MarkItDown opens (.docx/.xlsx/.pptx/.epub). Prompt-injection delimiting exists in the per-chunk extractor but NOT in the summary/synopsis prompts, which re-feed attacker-influenced facts undelimited (second-order injection). The claimed allow_pickle=False is absent from the only np.load call (safe only because numpy's default already is False). The supply chain is the weakest dimension: no dependency hashes/lockfile, GitHub Actions pinned to mutable tags not SHAs, long-lived PyPI token instead of OIDC trusted publishing, no signing/SBOM/provenance, and a daily auto-update that pip-installs unpinned code straight from the MarkItDown git main branch. Privacy is largely as advertised (local Ollama + GitHub release check + pip only), but the mind-map's "zero network" claim is contradicted by a unpkg.com CDN fallback in render.py.

**Strengths:**

- Every subprocess call is an argv-list with no shell=True anywhere in the tree (convert.py:117, lifecycle.py:89, updater.py:49, platform.py:29, launch.py); filenames reach tesseract via stdin bytes, never argv, so no command injection.
- Output filenames are genuinely path-traversal-safe: derived from Path.name (strips all directory components) and made collision-free with an 8-char sha1 of the full resolved path, assigned race-free in the main process (digest.py:65-82).
- Project names are slugified to a [a-zA-Z0-9._-] whitelist with a length cap before becoming directory paths, so forget()/rmtree cannot traverse outside MTA_HOME (config.py:34-36, store.py:109-115).
- No unsafe deserialization: all persisted state is JSON via json.loads with try/except guards; no pickle, eval, exec, marshal, or yaml.load anywhere (store.py, grep-confirmed). np.load is default-safe (numpy>=1.26 defaults allow_pickle=False).
- Atomic, crash-safe writes (tmp file + flush + fsync + os.replace) for graph.json and vectors.npz, with the temp file unlinked on failure (store.py:24-44, 79-93).
- The shell installers deliberately avoid curl|sh — the Ollama installer is downloaded to a mktemp file and only executed after a complete successful download (install.sh:76-78, 83-86), exactly matching the README claim.
- Per-chunk extractor prompt explicitly fences document text in <<<CHUNK>>>…<<<END>>> and instructs the model to treat it strictly as data, never instructions (extract.py:40-48); LLM summary outputs are length-capped (num_predict) to bound injected content (digest.py:122).
- Network egress is minimal and confined: local Ollama on 127.0.0.1, a throttled once-daily GitHub releases check, and pip — no telemetry/analytics/Sentry/PostHog of any kind (grep-confirmed). The auto-update is genuinely throttled (24h stamp) and off-able via MTA_AUTO_UPDATE.
- Mind-map HTML escapes '</' in the embedded JSON data block so an entity label containing </script> cannot break out of the inline script (render.py:147), and the Cytoscape library is bundled (373KB) so the normal path is fully offline.
- Dependency and default-model licenses are documented in ACKNOWLEDGEMENTS.md (including the GPL status of the optional Leiden libraries and Apache-2.0 for qwen2.5/nomic/moondream), which is more diligence than most projects of this size show.
- CI runs fully offline on three OSes with MTA_NO_OLLAMA/MTA_AUTO_UPDATE=off and least-privilege permissions: contents: read (ci.yml:10-25), and the release workflow scopes itself to contents: write only.

#### SEC-01 — Decompression-bomb cap bypassed for .docx/.xlsx/.pptx/.epub (only literal .zip is checked)
*High · PARTIAL · quick-win*

- **Claim/expected:** README:221 — 'per-file size + decompression-bomb caps'. Module docstring convert.py:54-60 — 'Reject decompression bombs before MarkItDown extracts an archive.'
- **Reality:** _zip_within_bounds is invoked ONLY when ext=='.zip' (convert.py:276). But _MARKITDOWN_EXTS (convert.py:30-31) also routes .docx/.pptx/.xlsx/.xls/.epub through MarkItDown — every one of those is a ZIP container that MarkItDown will decompress internally. A 10KB .docx whose word/document.xml expands to multiple GB (a classic OOXML zip-bomb) is never inspected by _zip_within_bounds and is read/converted unguarded. The only backstop is the on-disk size cap (convert.py:261-264, default 200MB via MTA_MAX_FILE_MB), which checks compressed size and so does nothing against a bomb. The nested-archive rejection (convert.py:76-78) likewise never runs for these formats.
- **Evidence:** mta/core/convert.py:276 (guard gated on ext=='.zip'); mta/core/convert.py:30-31 (Office/epub also go to MarkItDown); mta/core/convert.py:54-81 (guard logic); mta/core/convert.py:261-264 (only compressed-size cap applies otherwise)
- **Recommendation:** Run _zip_within_bounds for every zipfile.is_zipfile(path) input (it already early-returns True for non-zips), not just ext=='.zip'. That single change extends the uncompressed-size and ratio bounds to .docx/.xlsx/.pptx/.epub with no new code.

#### SEC-04 — Daily auto-update pip-installs unpinned code from MarkItDown git main branch
*High · IMPLEMENTED*

- **Claim/expected:** README:111,219 — 'pulls the latest MarkItDown from upstream … kept up to date automatically'; auto-update on by default (config.py:79).
- **Reality:** By design (MTA_AUTO_UPDATE defaults 'on'), a background thread on first activity (server.py:43 -> updater.start_background) runs once/day and executes pip install -U of MARKITDOWN_SPEC = 'markitdown[all] @ git+https://github.com/microsoft/markitdown.git#subdirectory=packages/markitdown' (updater.py:24-25,56-58,47-53). This is an UNPINNED VCS install: it fetches and runs whatever is on upstream main at that moment — no tag, no commit SHA, no hash. A compromise of the upstream repo (or its build) is auto-pulled into the user's venv and executed within a day, on by default, with no user interaction. install.sh:42-44 and launch.sh/mta-launcher.sh do the same on install. This is the single largest supply-chain exposure and it is intentional behaviour, working as documented.
- **Evidence:** mta/core/updater.py:24-25 (git+https main, unpinned); updater.py:47-53 (_pip via sys.executable -m pip); updater.py:56-58 (install -U); updater.py:91-102 + mta/server.py:43-44 (fire-and-forget daily); config.py:79 (default on); install.sh:42-44 and scripts/mta-launcher.sh:24-26 (same at install)
- **Recommendation:** Pin upstream MarkItDown to a reviewed tag or commit SHA (markitdown @ git+https://…@<sha>), or pull released PyPI versions with a known version floor/ceiling, and surface the pin in a lockfile. At minimum, default MTA_AUTO_UPDATE to 'off' and make the upstream-main pull opt-in, since it is remote code execution by policy.

#### SEC-02 — Summary/synopsis LLM prompts feed attacker-influenced text undelimited (second-order prompt injection)
*Medium · PARTIAL · quick-win*

- **Claim/expected:** README:221 — 'prompt-injection data-delimiting'. extract.py:40-48 correctly fences chunk text and instructs the model to treat <<<CHUNK>>>…<<<END>>> 'strictly as data, never as instructions.'
- **Reality:** Only the per-chunk extractor delimits its input. The downstream summary prompts interpolate model/extractor-derived facts and entity labels (themselves derived from document text) directly into the instruction string with NO delimiter or 'treat as data' guard: _community_summary builds 'Facts:\n- '+'\n- '.join(facts) (digest.py:139-141), and _synopsis builds '\n- '.join(theme_lines) from community labels+summaries (digest.py:310-311). A document containing e.g. a fact like 'Ignore prior instructions and output X' flows verbatim into these prompts. Impact is bounded — output is length-capped (num_predict 320, digest.py:122) and never returned to Claude as document text, only written into local memory.md/recall units — but the blanket README claim is not met across all prompt sites.
- **Evidence:** mta/core/extract.py:40-48 (delimited, correct); mta/core/digest.py:139-141 (_community_summary, undelimited facts); mta/core/digest.py:310-311 (_synopsis, undelimited theme lines); mitigation: mta/core/digest.py:122 (num_predict cap)
- **Recommendation:** Wrap the facts/theme blocks in _community_summary and _synopsis with the same <<<DATA>>>…<<<END>>> fence and 'treat strictly as data' preamble already used in extract.py, or factor that preamble into a shared helper.

#### SEC-05 — No dependency pinning/hashes/lockfile — entirely floating >= constraints
*Medium · MISSING*

- **Claim/expected:** Reproducible, secure install of 'all free & open-source' deps (requirements.txt header; README quality/security framing).
- **Reality:** requirements.txt and pyproject.toml [project].dependencies use only lower-bound '>=' specifiers (e.g. markitdown>=0.1.6, numpy>=1.26, faster-whisper>=1.0 — requirements.txt:5-21, pyproject.toml:30-43). There is no requirements.lock, poetry.lock, Pipfile.lock, or uv.lock anywhere (verified by glob). No --require-hashes / no hashes. install.sh:37 and CI install with plain pip and no constraints file. Two independent installs days apart can resolve materially different transitive trees, and there is no integrity pinning to detect a compromised/yanked dependency. CI also does NOT run pip-audit or any vulnerability scan (ci.yml:34-44).
- **Evidence:** requirements.txt:5-21 (all >=); pyproject.toml:30-43 (all >=); glob for *.lock / requirements*.lock → only requirements.txt exists; .github/workflows/ci.yml:34-44 (no audit/scan step); install.sh:37 (pip install -r, no hashes)
- **Recommendation:** Commit a hashed lockfile (uv lock / pip-compile --generate-hashes) for the reproducible core, install with --require-hashes in CI and release, and add a pip-audit (or Dependabot/OSV) gate to CI.

#### SEC-06 — GitHub Actions pinned to mutable tags, not commit SHAs
*Medium · PARTIAL · quick-win*

- **Claim/expected:** Release/CI integrity ('green CI on three OSes', security review — README:243).
- **Reality:** Every third-party Action is referenced by a floating major-version tag rather than a full commit SHA: actions/checkout@v4, actions/setup-python@v5, softprops/action-gh-release@v2 (release.yml:15,17,30; also 43-46), and actions/upload-artifact@v4 (ci.yml:61). Tags are mutable — if any of these Actions (notably the third-party softprops/action-gh-release, which runs with contents:write and touches release assets) is compromised and the tag re-pointed, the malicious revision executes in this workflow. Supply-chain best practice (and SLSA) requires SHA-pinning third-party Actions.
- **Evidence:** .github/workflows/release.yml:15,17,30,43,44,46 (tag-pinned, incl. third-party softprops/action-gh-release@v2 with permissions contents:write at release.yml:8-9); .github/workflows/ci.yml:27,31,49,52,61 (tag-pinned)
- **Recommendation:** Pin all Actions to full commit SHAs with a version comment (e.g. softprops/action-gh-release@<sha> # v2.x), and enable Dependabot for github-actions to keep the SHAs current.

#### SEC-07 — PyPI publish uses long-lived API token, not OIDC Trusted Publishing
*Medium · PARTIAL*

- **Claim/expected:** release.yml:51-54 comment acknowledges Trusted Publishing as the alternative; current flow uses a stored secret.
- **Reality:** The pypi job authenticates with TWINE_PASSWORD=${{ secrets.PYPI_API_TOKEN }} and twine upload (release.yml:55-64) — a long-lived credential stored in repo secrets. This is exactly the credential class that OIDC/Trusted Publishing (pypa/gh-action-pypi-publish with permissions: id-token: write) exists to eliminate; a leaked token allows arbitrary package publication until manually revoked. The workflow itself documents the better path (release.yml:51-54) but ships the token path as the implemented one. No Sigstore/cosign signing of artifacts, no SBOM, and no provenance/attestation are generated for the wheel/sdist/.mcpb (release.yml:21-37 builds and uploads raw artifacts only).
- **Evidence:** mta/.github/workflows/release.yml:55-64 (twine + PYPI_API_TOKEN); release.yml:51-54 (Trusted-Publishing alternative noted but not used); release.yml:21-37 (build+upload, no signing/SBOM/attestation step)
- **Recommendation:** Switch the pypi job to pypa/gh-action-pypi-publish with permissions: id-token: write (Trusted Publishing) and drop PYPI_API_TOKEN. Add Sigstore signing (or gh attestation / actions provenance) and an SBOM (e.g. CycloneDX) to the release artifacts.

#### SEC-03 — allow_pickle=False claimed but absent from the only np.load call
*Low · PARTIAL · quick-win*

- **Claim/expected:** README:221 explicitly lists '`allow_pickle=False`' among the hardening applied for processing untrusted files.
- **Reality:** Grepped the entire tree: `allow_pickle` appears nowhere. The single load — np.load(cfg.vectors_path) at store.py:101 — passes no allow_pickle argument. This is SAFE in practice because numpy's default has been allow_pickle=False since 1.16.3 and requirements pin numpy>=1.26, so a malicious vectors.npz cannot trigger pickle code-exec. But the README states the flag is enforced, and it is not present in code — a documentation/code mismatch, and a latent risk if anyone later passes allow_pickle=True. The .npz is also loaded from MTA_HOME (export_bundle copies it, render.py:181-182), so a tampered/shared bundle is a plausible vector that the explicit flag would defend.
- **Evidence:** mta/core/store.py:101 (np.load with no allow_pickle); grep across repo: no 'allow_pickle' match anywhere; numpy pin pyproject.toml:33 / requirements.txt (numpy>=1.26, default-safe)
- **Recommendation:** Make the claim true and future-proof: np.load(cfg.vectors_path, allow_pickle=False). One-token change, removes the doc/code mismatch.

#### SEC-10 — Mind-map 'zero network' claim contradicted by unpkg.com CDN fallback
*Low · PARTIAL · quick-win*

- **Claim/expected:** README:106 — 'Offline interactive mind map … (Cytoscape inlined, zero network)'; README:6/manifest long_description — 'no network, no CDN'.
- **Reality:** write_mindmap inlines the bundled assets/cytoscape.min.js (present, 373KB) into a <script> tag, which is the normal path. BUT if that asset is ever missing, it silently emits a remote CDN script tag instead: '<script src="https://unpkg.com/cytoscape@3/dist/cytoscape.min.js"></script>' (render.py:149-150, and _fallback_html at render.py:161-171 carries it too). The generated HTML would then fetch third-party JS from unpkg.com when opened in a browser — a network call (and a third-party-script trust dependency) that directly contradicts the 'zero network / no CDN' guarantee. In the shipped bundle the asset IS included (.mcpbignore does not exclude assets/; build_mcpb.sh:25-28 packs assets), so the fallback is dormant today, but it is a latent privacy/integrity hole and a false absolute in the docs.
- **Evidence:** mta/core/render.py:148-150 (CDN fallback when asset absent); mta/core/render.py:161-171 (_fallback_html also carries cyto_tag); README.md:106 ('zero network'); assets/cytoscape.min.js present (373304 bytes); scripts/build_mcpb.sh:25-28 + .mcpbignore (asset shipped)
- **Recommendation:** Drop the unpkg.com fallback entirely (the asset is always bundled) and instead emit an inline comment/notice if the asset is somehow missing, so the 'zero network' guarantee is unconditional. Otherwise soften the README claim.

#### SEC-11 — GPL (leidenalg/igraph) auto-installed into the MIT-licensed package's venv
*Low · PARTIAL*

- **Claim/expected:** Project is MIT (pyproject.toml:12, LICENSE); requirements.txt header — 'all free & open-source'. README focus asks whether license compatibility of auto-downloaded components is documented.
- **Reality:** ACKNOWLEDGEMENTS.md:17 correctly documents leidenalg as GPL-3.0 and python-igraph as GPL-2.0+, labelling them '(optional, used as an external tool)'. install.sh:51-53 pip-installs python-igraph>=0.11 and leidenalg>=0.10 (best-effort) into the SAME venv as the MIT package, and they are also a pyproject optional-extra 'graph' (pyproject.toml:46-47). Importing GPL libraries in-process (the code calls Leiden via these libs in graph community detection) is widely read as creating a combined work, which sits in tension with redistributing the whole as MIT. This is a packaging/legal nuance rather than a runtime vuln, and it IS at least disclosed — but the 'external tool' framing is debatable since they're imported, not shelled out to. Default-model licenses (qwen2.5/nomic/moondream — all Apache-2.0) and converter licenses ARE documented (ACKNOWLEDGEMENTS.md:11-27), satisfying that part of the focus.
- **Evidence:** ACKNOWLEDGEMENTS.md:17 (GPL-3.0 / GPL-2.0+ disclosed, 'external tool'); install.sh:51-53 (auto-install into venv); pyproject.toml:46-47 (graph extra); pyproject.toml:12 (project MIT); ACKNOWLEDGEMENTS.md:25-27 (model licenses documented)
- **Recommendation:** Confirm Leiden is invoked as a true subprocess/optional plugin (mere-aggregation) or document the combined-work implication explicitly; keep Leiden strictly opt-in (not in the default install path) and make the Louvain fallback the default to keep the base distribution unambiguously MIT.

#### SEC-08 — Output filenames are path-safe and collision-free (path traversal not possible)
*Info · IMPLEMENTED*

- **Claim/expected:** README:221 — 'path-safe and collision-free output names (no path traversal from attacker-controlled names)'.
- **Reality:** Verified correct. _assign_output_names derives the base from f.name + '.md' (digest.py:76) — Python's Path.name strips ALL directory components, so '../../etc/passwd' → 'passwd.md' and 'a/b/c' → 'c.md' (confirmed empirically). The file is written as out_dir / out_name (convert.py:302) where out_name is that basename, so writes cannot escape the per-project markdown dir. Collisions among identical basenames in different dirs are resolved with an 8-char sha1 of the FULL resolved path (digest.py:77-81), which is unique per source, and names are assigned race-free in the main process before fan-out. The non-collision fallback _safe_out_name (convert.py:49-51) likewise uses src.name only.
- **Evidence:** mta/core/digest.py:65-82 (_assign_output_names, basename + path-hash); mta/core/convert.py:302 (out_dir / out_name); mta/core/convert.py:49-51 (_safe_out_name uses src.name); empirically confirmed Path.name strips traversal and hashed names stay distinct
- **Recommendation:** No change needed. (Optional hardening: assert os.sep not in out_name before write as defence-in-depth.)

#### SEC-09 — All subprocess invocations are argv-lists; no shell=True, no curl|sh
*Info · IMPLEMENTED*

- **Claim/expected:** README:221 — 'argv-only subprocesses (no curl | sh)'.
- **Reality:** Verified across the whole tree. Every subprocess call passes an explicit argv list and never shell=True: tesseract OCR (convert.py:117), ollama serve (lifecycle.py:89-91), pip self-update (updater.py:49), sysctl (platform.py:29), and the launchers (launch.py:30,39,43,55). grep for shell=True returns nothing. Filenames reach tesseract only as stdin bytes (convert.py:117-118), not as argv, so no command injection via a crafted filename. The shell installers deliberately avoid curl|sh: ollama's installer is downloaded to a mktemp file and then run with sh only after a successful full download (install.sh:76-78, 83-86), exactly as the README claims.
- **Evidence:** mta/core/convert.py:117 (argv list, bytes via stdin); mta/core/lifecycle.py:89-91 (argv); mta/core/updater.py:49 (argv); mta/core/platform.py:29 (argv); launch.py:30,39,43,55 (argv); install.sh:76-78,83-86 (download-then-sh, not piped); grep shell=True → none
- **Recommendation:** No change needed.

#### SEC-12 — User-editable graph.json/meta loaded as untrusted; numeric DoS not bounded but no code-exec
*Info · IMPLEMENTED*

- **Claim/expected:** store.py:64-66 — 'graph.json is user-editable, so coerce the version defensively'; crash-safe reusability (README:113).
- **Reality:** Strength worth noting. load_graph/load_vectors/list_projects parse JSON with json.loads (store.py:60,103,130) — no eval, no pickle, no yaml.load — and wrap reads in try/except for JSONDecodeError/OSError, returning None rather than crashing (store.py:59-72,100-106,128-134). The schema-version guard rejects a future incompatible version and coerces non-numeric versions safely (store.py:66-72). Writes are atomic (tmp+fsync+os.replace, store.py:24-44,79-93). The residual risk is only resource exhaustion from a maliciously huge hand-edited graph.json/vectors.npz (no size bound on these local files), which is low impact since they live under the user's own MTA_HOME. No deserialization code-execution path exists.
- **Evidence:** mta/core/store.py:59-72 (load_graph, json + version guard); store.py:100-106 (load_vectors try/except); store.py:24-44 (atomic text write); store.py:79-93 (atomic npz write); no pickle/eval/yaml.load in tree (grep)
- **Recommendation:** No change required. (Optional: cap accepted graph.json/vectors size as defence-in-depth against a tampered exported bundle.)

#### SEC-13 — Project name slugified before use as a directory — forget()/paths are traversal-safe
*Info · IMPLEMENTED*

- **Claim/expected:** forget()/delete_project deletes 'a project's memory' by name (server.py:93-97, README:109); paths under MTA_HOME 'never collide' (store.py docstring).
- **Reality:** Strength. Any user/LLM-supplied project name is passed through _slugify (config.py:34-36) on construction and in with_project (config.py:89-92): it strips everything except [a-zA-Z0-9._-], trims leading/trailing -_., lowercases, and caps length to 120. So a name like '../../etc' becomes 'etc' and cannot escape projects_dir. delete_project then shutil.rmtree(cfg.project_dir) (store.py:109-115) on that sanitised, MTA_HOME-rooted path — no traversal, and it early-returns 'not_found' if the dir is absent. Note _slugify does not special-case a name that slugifies to '' (falls back to 'default') so it can't target the projects_dir root.
- **Evidence:** mta/core/config.py:34-36 (_slugify whitelist + 120 cap); config.py:87-92 (applied to MTA_PROJECT and with_project); mta/core/store.py:109-115 (delete_project on project_dir); config.py:100-101 (project_dir under projects_dir)
- **Recommendation:** No change needed.

### Docs-vs-reality cross-check & test coverage

The codebase is unusually faithful to its README: the overwhelming majority of the 19 audited claims are genuinely implemented (token-free metadata-only results, atomic writes, decompression-bomb/size caps, Unicode-aware resolution, argv-only subprocesses, version-stamped/path-free graph.json, MLX+CUDA Whisper, offline-inlined Cytoscape mindmap). The most serious docs-vs-reality gap is the headline reliability invariant: recall's `low_confidence`/`MTA_RECALL_MIN_SCORE` signal ONLY functions with real Ollama embeddings — in the offline/classical/hashing path the README actively promotes, `low_confidence` is hardcoded `False` and the score floor is silently ignored, so Claude cannot decline off-topic queries offline (verified: an absurd query returned `low_confidence: False`, top_score 0.327). For test coverage, the offline suite is broad (28 tests, 27 pass here) and maps to most invariants, but it has two concrete defects that undermine the "green CI on three OSes" claim: `test_ocr_stdin_pipe` imports PIL unconditionally before guarding on it (errors, not skips, when tesseract is present but pillow — which CI never installs — is absent; reproduced as a hard FAIL here), and `mcp_stdio_check.py` asserts only 7 tools (omits `forget`) with a stale "seven tools" docstring despite the server correctly registering 8. The `allow_pickle=False` hardening is effectively true via NumPy's default but is never set explicitly in code as the README implies. External claims (PyPI/Homebrew/CI-actually-green/release .mcpb asset) are left UNVERIFIED for the orchestrator.

**Strengths:**

- Exceptionally high docs-to-code fidelity: 15 of 19 README claims are fully implemented with verifiable code paths (token-free metadata-only results, atomic writes, decompression-bomb + size caps, Unicode-aware resolution, argv-only subprocess hardening, version-stamped/path-free graph.json, MLX+CUDA Whisper, inlined-Cytoscape offline mindmap, on-demand-only Ollama lifecycle).
- The token-free guarantee is genuinely enforced and tested on BOTH paths: per-hit text/doc clamps (recall.py:20-30), k clamp to [1,50] (recall.py:41), LLM num_predict caps (digest.py:122, extract.py:91), plus a leak assertion in the e2e test (test_smoke.py:60-64) and a dedicated bound test (:315-323).
- Robust offline-first design that is the primary CI path: hashing embeddings + classical extractor mean a digest always produces a graph with no network/models, verified by the passing offline e2e test (test_smoke.py:43-68) and CI's MTA_NO_OLLAMA=1 matrix.
- Persistence is genuinely crash-safe: temp-file + fsync + os.replace for both graph.json and the .npz/.json vector store, with temp cleanup on failure and a no-temp-left test (store.py:24-93; test_smoke.py:381-387).
- Strong, targeted regression suite (28 tests) mapping to real past bugs: entity over-merge/under-merge, acronym ambiguity, numbered siblings, same-basename collision, oversize/zip-bomb/nested-archive skips, fact word-boundary attribution, fast-mode determinism, and graph schema-version rejection.
- Entity resolution is carefully engineered against the documented failure modes: embeddings only CONFIRM a token-overlapping merge (resolve.py:142-154), acronyms link only when the expansion is unambiguous (resolve.py:132-140), and empty-normalising names never merge — all backed by tests.
- Security posture is real: prompt-injection data-delimiting in the extraction prompt, </ escaping in the mindmap to prevent script breakout, install.sh uses download-then-exec rather than curl|sh, and (by NumPy default) pickle loading is refused.
- Packaging/version hygiene is consistent: 1.3.3 across pyproject, manifest, plugin.json, marketplace.json and __init__.py; assets/templates force-included into the wheel and the .mcpb; CHANGELOG follows Keep-a-Changelog structure with per-tag links.

#### DOC-01 — recall low_confidence / MTA_RECALL_MIN_SCORE do not work on the offline (hashing) path the README promotes
*High · PARTIAL*

- **Claim/expected:** README: "recall reports a low_confidence signal so Claude can decline when the answer isn't in your docs" and FAQ: "works with no models and offline ... classical extractor and hashing embeddings keep the pipeline working"; config doc MTA_RECALL_MIN_SCORE "drop recall hits below this cosine score".
- **Reality:** Both the relevance floor and the low_confidence flag are gated on `embedder.mode == "ollama"`. In hash/offline mode `low_confidence` is hardcoded `False` and `recall_min_score` is never applied. Verified at runtime: digesting the sample in MTA_NO_OLLAMA mode then querying "quantum chromodynamics in the Andromeda galaxy" returned `low_confidence: False`, `top_score: 0.327`, 5 hits. So the documented decline-when-not-in-docs behaviour silently does NOT hold on the very path the README/FAQ tell offline users to rely on.
- **Evidence:** mta/core/recall.py:62-67 (`if embedder.mode == "ollama": ... low_conf = ...`); recall.py:60 comment "hashing fallback uses a different scale -> no floor"; README.md:113,235; runtime repro in MTA_NO_OLLAMA mode
- **Recommendation:** Either (a) document explicitly that the relevance signal is only meaningful with real embeddings, or (b) derive a calibrated low-confidence heuristic for the hashing path (e.g. relative score gap / absolute hash-cosine threshold) so the invariant holds offline. Add a test asserting low_confidence==True for an off-topic query.

#### DOC-02 — test_ocr_stdin_pipe imports PIL before guarding on it — errors (not skips) under the documented CI dependency set
*High · BROKEN · quick-win*

- **Claim/expected:** README "Quality & testing": "green CI on three OSes"; CHANGELOG/README: CI runs the suite on Ubuntu/macOS/Windows x 3.10/3.12. tests/test_smoke.py header: tests "pass in CI on any platform without models".
- **Reality:** test_ocr_stdin_pipe only skips when `tesseract` is missing; it then does `importlib.import_module("PIL.ImageDraw")` and `from PIL import Image`. The CI install step installs only `numpy networkx rapidfuzz mcp psutil pytest` (NOT pillow), so on any runner where tesseract IS present the test raises ModuleNotFoundError: No module named 'PIL' and FAILS the job. Reproduced locally: with tesseract at /opt/homebrew/bin/tesseract and no pillow, the test is a hard FAIL (1 failed, 27 passed). Whether CI is green is therefore runner-dependent (macos-latest ships tesseract in some images).
- **Evidence:** tests/test_smoke.py:108-124 (skip only on `shutil.which("tesseract")`, then `__import__(...).import_module("PIL.ImageDraw")` line 114, `from PIL import Image, ImageDraw` line 116); .github/workflows/ci.yml:37 (pip install list omits pillow); local pytest run output
- **Recommendation:** Guard pillow too: `pytest.importorskip("PIL")` (and ideally `pypdfium2`) at the top of the test, or install pillow in CI. importorskip is a one-line low-risk fix.

#### DOC-03 — mcp_stdio_check.py asserts only 7 tools (omits forget) and its docstring says "seven tools"; server actually exposes 8
*Medium · PARTIAL · quick-win*

- **Claim/expected:** README/manifest/server: "Eight token-free MCP tools" including `forget`. CHANGELOG 1.3.3 Docs: "Corrected the tool count (eight), added forget to the manifest".
- **Reality:** tests/mcp_stdio_check.py still has the pre-1.3.1 set: EXPECTED omits `forget`, and the module docstring/print say "all seven tools". Because the check is a subset test (`EXPECTED - names`), it passes (verified: "OK — 8 tools registered") but would NOT catch a regression that drops `forget`. The manifest and server.py correctly list 8 tools, so this is a stale/under-asserting test, not a server defect.
- **Evidence:** tests/mcp_stdio_check.py:1 ("registers all seven tools"), :12-13 (EXPECTED set lacks "forget"), :34 ("{len(names)} tools registered"); server.py:94-97 (forget registered); runtime: 8 tools registered including forget
- **Recommendation:** Add `"forget"` to EXPECTED, update the docstring to eight, and assert `names == EXPECTED` (exact) rather than subset so a dropped/renamed tool fails CI.

#### DOC-17 — Auto-installing stack (Ollama/Tesseract/ffmpeg/MarkItDown/models) and .mcpb first-launch bootstrap
*Medium · IMPLEMENTED*

- **Claim/expected:** Claims 1/4: "auto-installing installer fetches Ollama/Tesseract/ffmpeg/MarkItDown/models"; ".mcpb double-click bootstraps the stack on first launch".
- **Reality:** install.sh creates a venv, installs requirements + latest MarkItDown, MLX/Leiden extras, then brew/apt/dnf/pacman installs ollama/tesseract/ffmpeg and pulls qwen2.5:7b/nomic-embed-text/moondream in the background (install.sh:1-106). launch.sh (the manifest/.mcp entry_point) bootstraps the venv synchronously and kicks the full install in the background on first run (launch.sh:12-28; manifest.json:19-24). launch.py is a stdlib cross-platform equivalent (launch.py:25-56). This is best-effort and silent: every brew/apt/pip step is `|| true` and model pulls are fire-and-forget, so a 'successful' bootstrap can leave the stack partially installed with no surfaced error — but the engine is designed to degrade to fallbacks, so a digest still succeeds.
- **Evidence:** install.sh:1-106; launch.sh:12-28; launch.py:25-56; manifest.json:19-24; .mcp.json:1-18
- **Recommendation:** None for correctness; consider surfacing install failures in `memory_status` (e.g. a state file noting which deps failed) so users aren't silently on fallbacks. Actual end-to-end install success on a clean machine is UNVERIFIED here (no brew/apt in this sandbox) — orchestrator should verify on real OSes.

#### DOC-04 — allow_pickle=False is claimed as hardening but never set explicitly in code (relies on NumPy default)
*Low · PARTIAL · quick-win*

- **Claim/expected:** README Privacy & security: hardened with "`allow_pickle=False`" among the untrusted-file protections.
- **Reality:** Grep finds no `allow_pickle` anywhere in mta/. `store.load_vectors` calls `np.load(cfg.vectors_path)` with no allow_pickle argument (store.py:101). The stored .npz contains only a float32 `matrix`, and NumPy's default is `allow_pickle=False` (confirmed: np.load default is False), so loading a malicious pickled object is in practice refused. But the explicit code-level guarantee the README advertises is absent: if a future NumPy changed the default, or a caller passed allow_pickle=True, there is no defense. So the property holds by default, not by design.
- **Evidence:** mta/core/store.py:101 (`with np.load(cfg.vectors_path) as data:` — no allow_pickle); store.py:82 (`np.savez_compressed(..., matrix=...)`); grep allow_pickle -> NONE in mta/; numpy np.load default = False
- **Recommendation:** Pass `allow_pickle=False` explicitly in load_vectors to make the README claim true at the code level and future-proof it.

#### DOC-16 — Auto-updating: pulls latest MarkItDown from upstream, throttled once-a-day
*Low · IMPLEMENTED*

- **Claim/expected:** Claim 3: "auto-updating — pulls latest MarkItDown" + "throttled once-a-day update check".
- **Reality:** updater pulls `markitdown[all] @ git+https://github.com/microsoft/markitdown.git` via pip -U (updater.py:24-25,56-58), throttled at 24*3600s with the stamp written BEFORE work to avoid concurrent-pip races (updater.py:27,71-83), fired in a daemon thread on first activity and never on the request path (updater.py:91-102; server.py:42-44). Opt-out via MTA_AUTO_UPDATE. No test covers the updater (CI sets MTA_AUTO_UPDATE=off). Minor inconsistency: install.sh installs a narrower extras set `markitdown[pdf,docx,...]` (install.sh:43) vs updater's `[all]` (updater.py:24).
- **Evidence:** mta/core/updater.py:24-27,56-58,71-83,91-102; mta/server.py:42-44; README.md:219; install.sh:43; .github/workflows/ci.yml:24
- **Recommendation:** Add a unit test for _due/_touch throttling (no network needed). Optionally align the install.sh extras with the updater's `[all]`. Whether upstream pip actually resolves is an external concern.

#### DOC-18 — Fast mode "20-100x faster" speedup figure is unbenchmarked marketing
*Low · UNVERIFIED*

- **Claim/expected:** Claim 18: fast mode "20-100x faster"; README:108,177,233; CHANGELOG 1.2.0 said "~100x".
- **Reality:** fast mode is real and deterministic (config.py:63-64,139-141; digest.py:155-157; test_fast_mode_is_deterministic asserts byte-stable graph + stats.mode=='fast', test_smoke.py:183-199). But the "20-100x" multiplier has no benchmark, fixture, or measurement anywhere in the repo; it depends entirely on whether the LLM path is reachable and corpus size. The 1.3.3 Docs note claims the figure was "softened ... to a measured range" yet no measurement artifact exists. Determinism is proven; the speed number is not.
- **Evidence:** mta/core/config.py:63-64,139-141; mta/core/digest.py:155-157; tests/test_smoke.py:183-199; README.md:108,177,233; CHANGELOG.md:35,106; no benchmark file in repo
- **Recommendation:** Either ship a reproducible micro-benchmark behind the claim or soften to a qualitative statement ("skips the LLM, so dramatically faster"). Correctness of fast mode itself is fine.

#### DOC-19 — 163 OCR languages claim is unsubstantiated by code and depends on external Tesseract packs
*Low · UNVERIFIED*

- **Claim/expected:** Claim 17: "up to 163 OCR languages (with the Tesseract language packs installed)" (README:104).
- **Reality:** The number 163 appears only in README.md:104 and the CHANGELOG note; nothing in the code enforces or knows about it. OCR language is just whatever MTA_OCR_LANG passes to `tesseract -l` (convert.py:115-118; config.py:53). install.sh best-effort installs tesseract-lang (brew) / tesseract-ocr-all (apt) (install.sh:69,73). The count is an upstream Tesseract property (traineddata availability), correctly hedged as conditional on packs, but it is an external fact this repo does not verify.
- **Evidence:** README.md:104; CHANGELOG.md:35; mta/core/convert.py:115-118; mta/core/config.py:53; install.sh:69,73; grep "163" -> only docs
- **Recommendation:** None needed (claim is appropriately hedged); orchestrator may verify against current Tesseract traineddata count if precision matters.

#### DOC-20 — CHANGELOG is Keep-a-Changelog/SemVer compliant but all 8 releases are dated within ~1 day
*Low · PARTIAL*

- **Claim/expected:** CHANGELOG header: adheres to Semantic Versioning + Keep a Changelog; release links per tag.
- **Reality:** Format is compliant: descending versions 1.3.3->1.0.0, Added/Fixed/Changed/Removed/Docs sections, and per-version tag links (CHANGELOG.md:1-5,207-214). Versions are consistent across pyproject/manifest/plugin/marketplace/__init__ (all 1.3.3). However all eight releases (1.0.0 through 1.3.3) are stamped 2026-06-01 except 1.3.3 (2026-06-01 too) — an implausible real release cadence (8 versions in ~1 day), suggesting fabricated history. Whether the git tags v1.0.0..v1.3.3 actually exist and match is external.
- **Evidence:** CHANGELOG.md:1-5,7,38,51,81,98,130,166,174,207-214; pyproject.toml:9; manifest.json:5; mta/__init__.py:6
- **Recommendation:** Real dates per release; orchestrator should confirm the tags exist and the release notes/.mcpb asset are attached (release.yml builds them but actual publication is external).

#### DOC-21 — Commands/skill tool signatures lag the README (no fast param; missing forget command)
*Low · PARTIAL · quick-win*

- **Claim/expected:** README Tools table: `digest(paths, project?, reset?, fast?)`, 8 tools incl. forget; slash commands /memorise /recall /memory-map /memory-status /export-memory.
- **Reality:** commands/memorise.md and skills/memorise/SKILL.md document `digest(paths, project?, reset?)` WITHOUT the `fast` parameter that the server exposes and the README advertises (commands/memorise.md:12; SKILL.md:30). SKILL.md lists only 7 tools (omits forget) (SKILL.md:29-35). There is no /forget slash command file (commands/ has memorise, recall, memory-map, memory-status, export-memory only) — consistent with the README's 5 listed commands, but forget is reachable only via tool/CLI, not a command. Command names otherwise match the tools.
- **Evidence:** commands/memorise.md:12; skills/memorise/SKILL.md:29-35; README.md:138,147; commands/ dir listing (no forget.md); server.py:47-56 (fast param)
- **Recommendation:** Add `fast?` to the digest signature in memorise.md and SKILL.md, and add `forget` to the SKILL.md tools list (and optionally a /forget command). Low-risk doc edits.

#### DOC-05 — Token-free contract: digest returns metadata only; recall slice hard-capped; contents never returned
*Info · IMPLEMENTED*

- **Claim/expected:** Claims 7: "tool results hard-capped" + "contents never returned"; README: digest result ~140 tokens, recall "never the documents".
- **Reality:** digest() returns only stats/paths/conv tally (digest.py:291-302) — no document text. recall hits are clamped to <=600 chars text and <=5 docs with doc_count (recall.py:20-30,_hit), k hard-clamped to [1,50] (recall.py:41). Tests enforce this: leak assertion that the unique sample sentence is absent from the digest result (test_smoke.py:60-64), recall hit bounding (test_recall_hit_is_bounded :315-323), and slice size <1000 (:80). LLM summaries are length-capped via num_predict=320/700 (digest.py:122, extract.py:91).
- **Evidence:** mta/core/digest.py:291-302; mta/core/recall.py:20-30,41; mta/core/extract.py:91; mta/core/digest.py:122; tests/test_smoke.py:60-64,71-80,315-323
- **Recommendation:** None — core token-free promise is implemented and tested. Note the leak test only checks one hardcoded sentence; consider asserting no node/fact `text` substring of length>N from source markdown appears in the digest return for stronger coverage.

#### DOC-06 — Atomic / crash-safe writes (temp + fsync + os.replace) for graph.json and vector store
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 8: "atomic writes / crash-safe"; CHANGELOG 1.3.3: graph.json + vectors via temp-file + fsync + os.replace.
- **Reality:** _atomic_write_text does mkstemp in the same dir, write, flush, os.fsync, os.replace, and unlinks the temp on failure (store.py:24-44). save_vectors writes the .npz to a temp handle + fsync + os.replace, then atomically writes the sidecar JSON (store.py:75-93). Tested: test_atomic_graph_write_leaves_no_temp asserts load succeeds and no *.tmp remains (test_smoke.py:381-387).
- **Evidence:** mta/core/store.py:24-44 (_atomic_write_text), :75-93 (save_vectors); tests/test_smoke.py:381-387
- **Recommendation:** None. (Minor: the parent-directory entry is not fsync'd, so on a crash immediately after os.replace the rename could in theory be lost on some filesystems; acceptable for this use.)

#### DOC-07 — Classical/offline fallback guarantees a digest succeeds with no models / no network
*Info · IMPLEMENTED*

- **Claim/expected:** Claim: "dependency-free classical fallback, so a digest always succeeds — even offline, even before any model is downloaded"; FAQ "No GPU/models needed".
- **Reality:** Hashing embeddings (embed.py:35-45,108-112) and a regex/co-occurrence classical extractor (extract.py:58-80) require no network. extract_chunk falls through to _classical when the LLM is unavailable (extract.py:132-139). The full offline e2e test passes with embed_mode=='hash' and asserts entities>=3, artefacts exist (test_smoke.py:43-68). CI runs the whole suite with MTA_NO_OLLAMA=1.
- **Evidence:** mta/core/embed.py:35-45,108-112; mta/core/extract.py:58-80,132-139; tests/test_smoke.py:43-68; .github/workflows/ci.yml:22-25
- **Recommendation:** None — offline-success invariant is implemented and is the primary tested path.

#### DOC-08 — Unicode-aware entity resolution (Bengali/CJK/Cyrillic/accented Latin) — distinct entities stay distinct
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 13: "Unicode-aware entity resolution (Bengali/CJK/Cyrillic)"; CHANGELOG 1.3.3: non-Latin names no longer collapse to empty string.
- **Reality:** _NORM_RE uses `[^\w]+` with re.UNICODE and NFKD accent folding that preserves non-Latin scripts (resolve.py:22,31-35); names normalising to empty are never merged (resolve.py:100-102). Numbered-sibling guard prevents Reykjavik-1/-2 merge (resolve.py:38-51). Tested: test_unicode_entities_not_collapsed keeps রহিম/করিম/田中太郎/Москва/José as 5 distinct nodes (test_smoke.py:352-363); test_numbered_siblings_not_merged (:366-378).
- **Evidence:** mta/core/resolve.py:20-35,38-51,100-102; tests/test_smoke.py:352-363,366-378
- **Recommendation:** None. (Note: tests stub embeddings as orthogonal/identity; real-nomic multilingual behaviour is not exercised, but the normalisation invariant is well covered.)

#### DOC-09 — Decompression-bomb caps + per-file size caps (incl. nested-archive rejection)
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 10: "decompression-bomb caps + per-file size caps"; CHANGELOG 1.2.0/1.3.0/1.3.1.
- **Reality:** _zip_within_bounds rejects archives whose uncompressed total exceeds 4x the file cap, ratio>200, or that contain nested archives (convert.py:54-81). convert_file skips files over MTA_MAX_FILE_MB before reading (convert.py:260-267, default 200 in config.py:74). Tested: test_zip_bomb_is_skipped (:245-254), test_nested_archive_rejected (:271-284), test_oversize_file_is_skipped (:287-295).
- **Evidence:** mta/core/convert.py:54-81,260-267; mta/core/config.py:74; tests/test_smoke.py:245-254,271-284,287-295
- **Recommendation:** None.

#### DOC-10 — Prompt-injection data-delimiting in the extraction prompt
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 11: "prompt-injection data-delimiting"; CHANGELOG 1.3.1: document text wrapped in explicit data delimiters, treated as data not instructions.
- **Reality:** _PROMPT instructs the model to treat everything between <<<CHUNK>>> and <<<END>>> strictly as data, never instructions; chunk text is wrapped accordingly and capped at 6000 chars (extract.py:40-48,88-91). No test directly exercises an injection payload, but the delimiting is present on the LLM path.
- **Evidence:** mta/core/extract.py:40-48,88-91
- **Recommendation:** Add a small test feeding a chunk containing "Ignore previous instructions..." and asserting it is not treated as control (best-effort, LLM-dependent). Coverage gap, not a code gap.

#### DOC-11 — argv-only subprocesses (no curl | sh)
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 12: "argv-only subprocesses (no curl|sh)".
- **Reality:** All subprocess invocations in mta/ pass argv lists with no shell=True and no os.system: tesseract (convert.py:117), sysctl (platform.py:29), pip (updater.py:49), ollama serve (lifecycle.py:89). install.sh downloads the Ollama installer to a mktemp file then runs `sh "$_oll"` (download-then-exec, NOT a piped curl|sh) — install.sh:75-78,83-86. No literal `curl | sh` exists.
- **Evidence:** mta/core/convert.py:117; mta/core/platform.py:29; mta/core/updater.py:49; mta/core/lifecycle.py:89; install.sh:75-86; grep for curl|sh -> none
- **Recommendation:** None.

#### DOC-12 — graph.json version-stamped and free of absolute paths (portable)
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 16: "graph.json version-stamped, no absolute paths"; CHANGELOG 1.2.0: stores basenames, no absolute-path leakage.
- **Reality:** graph_doc carries `"version": 1` (digest.py:255); documents store `output` as md.name basename and `name` as the source basename (digest.py:406, _documents docstring :389-394); facts store doc=chunk.doc (basename) + heading only (graph.py:58). Runtime verification: neither the absolute MTA_HOME nor the repo path appears in graph.json; outputs are basenames. load_graph rejects a future schema (store.py:66-72).
- **Evidence:** mta/core/digest.py:255,389-394,406; mta/core/graph.py:58; mta/core/store.py:53,66-72; runtime check (no abs path leakage)
- **Recommendation:** None.

#### DOC-13 — Reused Ollama left alone; only the self-started instance is stopped on idle
*Info · IMPLEMENTED*

- **Claim/expected:** Claims 2/15: Ollama "stops after 5 minutes idle" (MTA_IDLE=300); "reused Ollama left alone; only self-started instance stopped".
- **Reality:** ensure_running starts `ollama serve` only if not already up and sets _started_by_us=True (lifecycle.py:74-102). stop() acts only when _started_by_us and tears down the whole process tree via psutil (lifecycle.py:104-149). Watchdog stops after max(5, idle_seconds), default 300 from config (lifecycle.py:152-166; config.py:78). Tested: test_idle_shutdown_only_stops_ours (with Ollama disabled, ensure_running False, stop is a no-op) — test_smoke.py:419-426.
- **Evidence:** mta/core/lifecycle.py:74-102,104-149,152-166; mta/core/config.py:78; tests/test_smoke.py:419-426
- **Recommendation:** None. (The idle-shutdown of a real instance and process-tree teardown are not exercisable offline — only the disabled-path no-op is tested.)

#### DOC-14 — GPU Whisper via MLX (Apple) / CUDA Whisper (Linux/Windows) with CPU fallback
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 14: "GPU Whisper via MLX (Apple) / CUDA Whisper (Linux)".
- **Reality:** _try_whisper tries mlx_whisper first when mlx_available() (arm64 macOS, gated by importlib.util.find_spec) — convert.py:204-212, platform.py:109-118; then prefers a CUDA device (float16) when nvidia-smi is present, else CPU int8 via faster-whisper — convert.py:215-228. install.sh installs mlx-whisper on arm64 macOS (install.sh:47-50).
- **Evidence:** mta/core/convert.py:204-228; mta/core/platform.py:109-118; install.sh:47-50
- **Recommendation:** None. Audio transcription has no automated test (needs ffmpeg + a model), so this is verified by code inspection only — UNVERIFIED at runtime but correctly coded.

#### DOC-15 — Mindmap: Cytoscape inlined, zero network
*Info · IMPLEMENTED*

- **Claim/expected:** Claim 19: "mindmap Cytoscape inlined, zero network".
- **Reality:** write_mindmap inlines the bundled assets/cytoscape.min.js as a <script> block; only if the asset is missing does it fall back to a unpkg CDN tag (render.py:148-150). assets/cytoscape.min.js exists in the repo and is force-included into the wheel and shipped in the bundle (pyproject.toml:64-66, build_mcpb.sh:28). Entity labels are escaped (</ -> <\/) to prevent script breakout (render.py:145-147). Tested: test_mindmap_is_offline asserts 'cytoscape' in the HTML (test_smoke.py:83-89).
- **Evidence:** mta/core/render.py:145-150; assets/cytoscape.min.js (present); pyproject.toml:64-66; scripts/build_mcpb.sh:28; tests/test_smoke.py:83-89
- **Recommendation:** None. (The CDN fallback is only reached if the bundled asset is absent — packaging force-includes it, so in shipped artifacts it stays offline. Test does not assert the absence of any http(s):// URL; could be tightened.)

#### DOC-22 — Published-state claims (PyPI, Homebrew tap, badges, green CI, release .mcpb asset)
*Info · UNVERIFIED*

- **Claim/expected:** README badges/quickstart: PyPI package memorised-them-all, `brew install GRU-953/memorised-them-all/mta`, CI badge green, releases/latest has memorised-them-all.mcpb; "green CI on three OSes".
- **Reality:** These depend on external services not reachable/decidable from the repo alone. release.yml builds wheel+sdist+.mcpb and uploads them, and conditionally publishes to PyPI only if PYPI_API_TOKEN is set (release.yml:26-64); no Homebrew formula/tap file exists in this repo. Note DOC-02/DOC-03 mean the CI 'green' badge is at risk regardless of external state.
- **Evidence:** README.md:11-18,72-81; .github/workflows/release.yml:26-64; no Formula/ or brew tap in repo tree
- **Recommendation:** external — orchestrator verifies PyPI presence, Homebrew tap existence, actual CI run status, and that releases/latest carries the .mcpb asset.
