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
