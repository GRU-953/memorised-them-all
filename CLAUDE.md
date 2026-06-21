# CLAUDE.md — Memorised them All

This repo is under a **multi-session hardening/extension program**. Cross-session
state lives in `program/` on the **`develop`** branch — that is the single source of
truth, **not** model memory. Any fresh session resumes from it with zero prior context.

## Resume protocol (every session)
1. `git checkout develop && git pull`.
2. Read **`program/PROGRESS.md`** — the **▶ RESUME HERE** pointer + the WP table — and
   the last 1–2 entries of `program/SESSION_LOG.md`. Skim `DECISIONS.md` / `RISKS.md` /
   `ACCEPTANCE.md` as needed. **Load only the code the next Work Package touches** — do
   not re-read the whole tree.
3. Do the next unblocked WP on a `wp-<id>-<slug>` branch → PR into `develop` with green
   CI. **Never push `main` directly**; release from `main` via a `vX.Y.Z` tag (the
   tag-triggered train publishes all channels — see `program/PUBLISH_MANIFEST.md`).
4. **Wrap up:** leave the repo green + resumable; update `PROGRESS.md` (statuses +
   ▶ RESUME HERE) and append a `SESSION_LOG.md` entry ending with the single exact next step.

## Status
**v2.6.1 SHIPPED** — PyPI + GitHub Release + `.mcpb` + Homebrew tap + GHCR (OIDC trusted-publish,
SBOM, cosign single-file `*.sigstore.json` bundle). Ships v2.5.0 cross-AI `mta setup`
(Claude/Gemini/Cursor/VS Code/Windsurf/Codex; Grok auto-discover) + v2.6.0 recall/resolve perf +
supply-chain. v2.6.1 = the v2.6.0 package with two release-pipeline fixes (SBOM attach + cosign pin).
**S25 docs reframe SHIPPED** (no version bump): README + all 7 metadata surfaces reframed
Claude-only → cross-AI; live on GitHub / Claude-marketplace / Glama (PR #80→main, #81→develop).
**Next = v2.x+ backlog** (optional): a docs-only `v2.6.2` to refresh PyPI's page with the new
cross-AI description; remote-MCP recipe polish; the deferred Low items in `program/RISKS.md`
(R-16/R-17, accepted).

## Invariants (must never regress)
Token-free (tiny tool results; document contents never returned to the model) · 100%
local / no telemetry · dependency-free classical/offline fallback (a digest succeeds
with no models and no network) · atomic, crash-safe writes. CI must stay green on the
Ubuntu/macOS/Windows × 3.10/3.12 matrix.

## Env notes
`gh` is authed as owner `GRU-953`. Docker isn't installed locally (the Phase-6 container
matrix runs in CI / `.github/workflows/e2e.yml`). Tests: `pytest tests/` (the
`conversion-e2e` + `e2e` lanes need the full deps / a wheel install). Single version
source = `mta/__init__.py`; `scripts/check_versions.py` gates drift.
