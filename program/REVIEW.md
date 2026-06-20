# Review round — v2.4.1 maximal re-audit (S22, this session)

A fresh **9-agent maximal fan-out** (lenses A–I: correctness, security, token-free,
cross-platform, performance, reliability, packaging, docs, Bengali) re-audited `develop`
@ v2.4.1 (read-only) vs the invariants + severity rubric. Baseline was green first
(215 pass / 2 skip core lane; `check_versions` OK; byte-identical determinism + crash-safety
independently re-confirmed by lens F via SHA-256). **Consolidated: Critical=1 · High=4 ·
Med≈12 · Low≈12** (after orchestrator triage; several reviewers' "Critical/High" perf items
were rubric-downgraded to Med = "perf concern with a workaround").

## BLOCKING — Critical/High (must close before convergence) → WPs

| sev | id | finding (file:line) | smallest-safe-fix | WP |
|-----|----|--------------------|--------------------|----|
| **Critical** | TF-1 | `recall._hit`/`overview` never length-clamp the `label` field (recall.py:33,186); the Bengali entity path bypasses the 80-char Latin `_valid_entity` gate → **measured 394 KB recall(k=50) + 157 KB overview** on a Bengali corpus. **Token-free invariant violated.** | byte-clamp `label` (+ all hit/theme string fields) | WP-89 |
| **High** | TF-2 | recall "byte caps" are **character** slices (`[:600]`/`[:1200]`) → 3× over budget for 3-byte Bengali chars; "hard-capped in bytes" is false (recall.py:24,28,34,148,184) | cap on `len(s.encode())`, not `len(s)`; add a byte-size CI test | WP-89 |
| **High** | RES-1 | `resolve._norm` NFKD-decomposes + strips combining marks → reduces Bengali to consonant skeletons → **force-merges distinct entities** (ভোলা[Bhola]≡ভালো[good]; ঢাকা[Dhaka]≡ঢাকি) corrupting the entity graph on the flagship Bengali corpus (resolve.py:37-41); **no `test_resolve*` exists** | strip combining marks for **Latin diacritics only** (preserve Indic/Bengali); + resolve regression test | WP-90 |
| **High** | WIN-1 | `.mcpb` runs `bash launch.sh`; the Windows-capable `launch.py` is excluded by `.mcpbignore:13` yet manifest advertises `win32` → desktop bundle **cannot start on Windows** (manifest.json server.mcp_config) | DECISION (see PROGRESS ▶): make-it-work (ship launch.py + platform override) vs honest-claim (drop win32 from .mcpb, keep pip path) | WP-91 |
| **High** | SEC-1 | rar/7z external path (`unar`/`7z`) fully extracts to disk before any size/entry budget — only a 600s timeout bounds it → **disk-fill DoS**; SECURITY.md claims "same budget enforced" (archive.py:222-250) | pre-extraction size check (`unar -l`/`7z l`) + reconcile SECURITY.md | WP-92 |

## Med backlog — fix cheap/high-value ones this release (WP-93), defer perf refactors

**Bundle into v2.4.2 (cheap, safe, honesty/correctness):**
- render.py:76,92 — per-doc note keyed off source **basename** not the collision-free `d["output"]` → same-basename note silently overwritten; AND unclamped note name → uncaught `OSError` can abort an otherwise-successful digest *after* graph commit. Fix: reuse `d["output"]` + length-clamp.
- convert.py:26,33 + server.py:108 — `_AUDIO_EXTS` still in `SUPPORTED_EXTS` → `list_digestible` over-promises audio that `digest` always skips. Remove from SUPPORTED set (keep in media-skip).
- config.py:104-107 — `recall_min_score` doc says "cosine 0–1" but applied on the BM25 scale → mis-tuning. Reword.
- recall.py:62-74 — `_OVERLAP_STOP` includes contentful words ("data","report","information") → forces `low_confidence=True` on legit hits. Drop those / fall back when filtered set empty.
- Docs: commands/recall.md:13 "embeds the query" → BM25; commands/export-memory.md:14 duplicate `graph.json`; README config table missing live vars (`MTA_RECALL_MIN_SCORE`,`MTA_RECALL_K`,`MTA_OCR`,…) + `MTA_AUTO_UPDATE=upstream` value.
- De-stale internal text: Dockerfile:4-6 (`MTA_BACKEND*`/remote-model + "audio"/ffmpeg — none exist), ci.yml:23,62 + e2e.yml:18 dead env (`MTA_NO_OLLAMA`,`MTA_EXTRACT`), and stale LLM/embedding/audio comments in recall.py:21-28/26-28, extract.py:289-290, digest.py:399,573; `embed_mode:"hash"` string in memory.md; dead `_lexical` path.
- recall.py:127,131 — every recall loads the full unused `vectors.npz` matrix into RAM (BM25 never reads it). Drop the matrix load on the recall path (meta-only). Safe perf win.

**Defer to backlog (RISKS) — bigger/perf, "workaround exists", NOT blocking:**
- recall BM25 re-tokenizes the full recall-unit corpus + recomputes idf every query (perf cliff at large corpus); recall-unit count uncapped (digest.py:518). Fix = persist/cache a tokenized index at digest time — own focused WP (determinism-sensitive).
- resolve O(n²) fuzzy+cosine up to a hard 1500-name cap that doubles as an unannounced quality cliff (resolve.py:113-160). Fix = length/first-char bucketing.
- Cross-OS determinism: text-mode writers without `newline=""` emit `\r\n` on Windows (convert.py:543, store/render `_atomic_write_text`) → converted .md + persisted graph differ byte-for-byte across OS (the determinism test is same-OS so it's uncaught). Add `newline=""`. *(Promote to WP-93 if cheap — it's a 1-line-each fix and touches the determinism invariant across machines.)*
- platform.py:81 Windows-without-psutil mis-tier (caught, returns 8.0); digest.py:265 legacy pool uses default mp context (fork vs spawn); accumulate re-segments whole corpus each run.

**Accepted / Low (RISKS or no-op):** stale-comment cosmetics already listed; `MAX_FILE_MB=0` erodes the absolute bomb bound (opt-in only); gz oversized-stream returns empty dir vs None (cosmetic); `memory_status.projects` unbounded count (slugged ≤120); cosign `.sig/.pem` two-file form deprecated in cosign v3, removed in v4 (forward-looking supply-chain — own WP before a cosign v4 bump).

## Verified-clean this round (independently re-confirmed, no finding)
Determinism **byte-identical** across hash-seed/density/parallelism (SHA-256, lens F) · atomic temp+fsync+`os.replace`, backup-before-overwrite, torn-store→`no_memory` recovery · Zip-Slip/tar-symlink/bomb-cap/entry-cap/depth-cap/out-of-tree-symlink all rejected (lens B reproduced) · `allow_pickle=False`; no `shell=True`/`os.system`/`pickle`/`extractall` anywhere · HTTP transport deny-by-default + constant-time bearer · version single-sourced & gated across all 7 surfaces · all CI Actions SHA-pinned; OIDC/SBOM/tag==version/halt-on-partial intact · every **published** surface (README/manifest/glama/server.json/CITATION/plugin) tells a consistent model-free story · Bengali: oracle-faithful Bijoy→Unicode, ONLY the vetted রম্ন→রু rule active (3 dangerous rules absent, নিম্ন preserved), NFC-consistent halant tokenization (recall path).

---

# Pre-release review (S13) — findings & disposition

Independent **fresh-eyes** review (4 adversarial reviewers, workflow run
`wf_9100244e-45f`) of every `develop` change vs the acceptance criteria + invariants,
before the WP-41 release (Section 5). **21 findings: 3 High · 5 Medium · 8 Low · 5 Info.**

The reviewers **confirmed sound:** the cross-process lock design (lock files under
`state/locks/`; advisory flock; correct read/write split; no AB/BA deadlock), migration
safety (newer store read-recallable + backed up before overwrite; `allow_pickle=False`),
offline-first + opt-in/pinned upstream, the token-free hit caps, SEC-01's bomb cap, and
the release pipeline's halt-on-partial ordering + once-only build. The gaps were
edge-cases/robustness — fixed below.

## Fixed in WP-34 (PR #16)
| sev | finding | fix |
|-----|---------|-----|
| **High** | Torn vector store (`vectors.npz` rows ≠ `vectors.json` meta) → recall `IndexError` / mis-attribution | `load_vectors` length guard + recall index clamp |
| **High** | `config.load()` profile race on global `os.environ` → `no_ollama` could leak `False` under concurrent load | serialise the seed/restore window with `_LOAD_LOCK` |
| **High** | DOC-01 incomplete: the `_lexical` (dim-mismatch) fallback dropped `low_confidence`/`top_score` | `_lexical` now returns the full relevance contract |
| Med | `synopsis` returned uncapped (token-free) | cap in `recall` + `overview` (`_MAX_SYNOPSIS`) |
| Med | MarkItDown rollback reported success without re-verifying the import | `rolled_back` only if the restored version imports |
| Med | no lock around the auto-update pip install into a shared venv | `named_lock("pip-update")` around `update_markitdown` |
| Med | release `.mcpb` "verify" was content-blind (`test -f`) | zip-content assert in `release.yml` |
| Low | `list_digestible` could crash on a `stat()` TOCTOU | try/except → structured error |
| Low | lock degraded-mode (timeout → proceed unlocked) was silent | stderr warning in `locks.named_lock` |
| Low | zip-fallback `.mcpb` leaked nested `__pycache__` | extra `-x` globs in `build_mcpb.sh` |

## Deferred (logged, non-blocking — Low/Info or larger, revisit in v1.x+)
- **Full graph+vectors WRITE transaction** (single atomic unit). The read-side guard already
  makes a torn store *safe* (→ `no_memory`); a combined artifact is a deliberate v1.x+ change.
- Empty-units digest can leave `graph.json` present + vectors absent (recall `no_memory` vs
  overview `ok`) — a minor inconsistency, not corruption.
- `recall` holds the shared lock across the embedding round-trip (perf under heavy concurrent
  recall) — acceptable; revisit if it bites.
- Derived outputs (`memory.md`, per-doc notes, `mindmap.html`) written non-atomically — they're
  regenerated each digest; low value to harden.
- `workflow_dispatch` bypasses the tag==version gate (manual-dispatch only path).
- `_lexical` score is an integer overlap (different scale from cosine) — documented in the result.
- CI **license/vuln scan** (A12 remainder) — folded into the WP-40 supply-chain follow-up.
