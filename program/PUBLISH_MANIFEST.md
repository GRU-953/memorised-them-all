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
| **GitHub Release** | `softprops/action-gh-release` | `GITHUB_TOKEN` (contents: write) | release carries wheel + sdist + `.mcpb` + SBOM + a `*.sigstore.json` cosign bundle per artifact |
| **`.mcpb` (Claude Desktop)** | built in `build`, attached to the Release | — | double-click → Settings ▸ Extensions |
| **Homebrew tap** | `homebrew` job bumps `homebrew-memorised-them-all/Formula/mta.rb` | secret `HOMEBREW_TAP_TOKEN` (skips if unset; `continue-on-error`) | `brew install GRU-953/memorised-them-all/mta` |
| **Docker (GHCR)** | `docker.yml` builds multi-arch (amd64+arm64), pushes `:<v>` + `:latest` on tag | `GITHUB_TOKEN` (packages: write) — **no extra secret** | `docker run ghcr.io/gru-953/memorised-them-all:<v> mta --help` |

**Supply chain:** every Action is **SHA-pinned**; a **CycloneDX SBOM** and **cosign
keyless** single-file `*.sigstore.json` bundles (cosign v3 default; the legacy `.sig`/`.pem`
two-file form is deprecated in v3 / removed in v4) are produced per artifact; the build runs once
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
   download the `.mcpb` + its `.sigstore.json` and verify the keyless bundle (cosign v3):
   ```bash
   cosign verify-blob memorised-them-all.mcpb \
     --bundle memorised-them-all.mcpb.sigstore.json \
     --certificate-identity-regexp '^https://github.com/GRU-953/memorised-them-all/\.github/workflows/release\.yml@refs/tags/v.+$' \
     --certificate-oidc-issuer 'https://token.actions.githubusercontent.com'
   ```

## MCP registry (server.json — owner submits once)
`server.json` (repo root, version-gated by `scripts/check_versions.py`) is ready for the
official **MCP registry**. The release train does **not** auto-submit it (the registry
needs an interactive GitHub-namespace login). After a release, the owner runs once:
`mcp-publisher login github` then `mcp-publisher publish` from the repo root (the
`io.github.gru-953/...` namespace is validated against the GitHub owner). Updates are
idempotent per version.

## Done since v1.5.0
- **CI-09 lockfile** → `constraints.txt` + a non-blocking `supply-chain` CI job (pip-audit + licenses).
- **Docker/GHCR** multi-arch image (`docker.yml` → `ghcr.io/gru-953/memorised-them-all`).

## Deferred (v1.x+ / follow-up)
- Directories (Smithery / mcp.so / PulseMCP / Glama) + the Claude marketplace listing.
- **winget / Chocolatey / Scoop / Snap / Flatpak / AUR** — a poor fit for a pip/MCP tool
  (they expect standalone installers/binaries, not a Python package); revisit only if a
  frozen single-file build is produced. An `npx` wrapper.
- A **post-publish re-install smoke** job per channel.
