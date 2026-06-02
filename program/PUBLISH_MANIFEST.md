# Publish manifest — Memorised them All

One **tag-triggered** pipeline (`.github/workflows/release.yml`) builds every
artifact **once** and publishes to all channels in lockstep. Re-runnable
(idempotent), and ordered so a failure halts **before** anything partial.

**Order (halt-on-partial):** `build → pypi → github_release → homebrew`.
PyPI is first and required: if it fails, no GitHub Release is created.

## Channels (v1 core)

| Channel | How | Auth | Verify |
|---|---|---|---|
| **PyPI** | `pypa/gh-action-pypi-publish` (OIDC) | OIDC Trusted Publishing — no repo token | `pip install memorised-them-all==<v>` |
| **GitHub Release** | `softprops/action-gh-release` | `GITHUB_TOKEN` (contents: write) | release carries wheel + sdist + `.mcpb` + SBOM + `.sig`/`.pem` |
| **`.mcpb` (Claude Desktop)** | built in `build`, attached to the Release | — | double-click → Settings ▸ Extensions |
| **Homebrew tap** | `homebrew` job bumps `homebrew-memorised-them-all/Formula/mta.rb` | secret `HOMEBREW_TAP_TOKEN` (skips if unset) | `brew install GRU-953/memorised-them-all/mta` |

**Supply chain:** every Action is **SHA-pinned**; a **CycloneDX SBOM** and **cosign
keyless** signatures (`.sig`/`.pem`) are produced per artifact; the build runs once
and publish jobs consume the same artifacts (no double-build); least-privilege
per-job permissions; tag == version gate.

## ⚠ Owner one-time setup (required before the first hardened release — WP-41)
1. **PyPI Trusted Publisher** — on PyPI, project `memorised-them-all` → *Publishing* →
   add a GitHub publisher: owner `GRU-953`, repo `memorised-them-all`, workflow
   `release.yml`. (No token is stored in the repo.)
2. **Homebrew tap token** — create a fine-grained PAT (or deploy key) with
   `contents:write` on `GRU-953/homebrew-memorised-them-all`; add it as the repo
   secret **`HOMEBREW_TAP_TOKEN`**. If absent, the tap bump is **skipped**, not failed.

## Release checklist
1. `develop` green; bump `mta/__init__.py` `__version__`; run `python scripts/check_versions.py`.
2. PR `develop` → `main`; merge when green; update `CHANGELOG.md` (move *Unreleased* → the version).
3. `git tag vX.Y.Z && git push origin vX.Y.Z`.
4. Watch **Release**: `build → pypi → github_release → homebrew`.
5. Post-publish smoke: `pip install memorised-them-all==X.Y.Z`; `brew update && brew upgrade … mta`;
   download the `.mcpb` and `cosign verify-blob` it against its `.pem`/`.sig`.

## Deferred (v1.x+ / follow-up)
- Reproducible-build **lockfile** (CI-09 / SEC-05) — pin build tooling + a hashed deps lock.
- Extra channels (Phase-5 v1.x+): Docker/GHCR multi-arch + devcontainer, the official MCP
  registry + directories (Smithery / mcp.so / PulseMCP / Glama), the Claude marketplace
  listing, winget/Chocolatey/Scoop, Snap/Flatpak/AUR, an `npx` wrapper.
- A **post-publish re-install smoke** job per channel.
