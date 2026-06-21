# release-manifest.md — prepared, NOT executed

Channels discovered from repo evidence (`.github/workflows/release.yml`, `docker.yml`,
`server.json`, `.claude-plugin/marketplace.json`, `manifest.json`, tag history). **Nothing is
published autonomously.** All publishing is the owner's tag-push from an authenticated clone;
this sandbox blocks tag pushes (HTTP 403) by design.

## Version (single source of truth)
- **Source of truth:** `mta/__init__.py` → **2.6.0** (gated in lockstep across manifest.json,
  server.json, plugin.json, marketplace.json, CITATION.cff by `scripts/check_versions.py`).
- **Latest published (all channels):** **v2.4.2**. **v2.5.0** is merged to `main` (untagged);
  **v2.6.0** is PR #75 (unmerged).
- **Proposed next:** **v2.6.0** — semver **minor** over 2.4.2 (additive features: cross-AI
  auto-config + perf + supply-chain; no breaking API/schema change). Verified **does not exist**
  on any channel (tags end at v2.4.2). Recommendation: after merging #75 → `develop` → ff `main`,
  tag **v2.6.0** (it supersedes the untagged 2.5.0 content); optionally tag **v2.5.0** first from
  `main` if a discrete 2.5.0 release is wanted. **Proposed, not applied.**

## Channels

| Channel | Evidence | Current published | Publish command (owner) | Rollback / yank |
|---|---|---|---|---|
| **PyPI** | `release.yml` `pypi` job (OIDC trusted publishing) | 2.4.2 | `git push origin v2.6.0` → train builds once → `pypa/gh-action-pypi-publish` (`skip-existing`) | `pip` cannot delete; **`twine yank memorised-them-all==2.6.0`** (or PyPI UI → Yank). Yank hides from resolution but keeps pinned installs working; cannot reuse the version number. |
| **GitHub Release** | `release.yml` `github_release` job | 2.4.2 | same tag push (runs after PyPI succeeds — halt-on-partial) | Delete the release + tag in the GitHub UI / `gh release delete v2.6.0`; assets (`*.whl/*.tar.gz/.mcpb/sbom/.sigstore.json`) go with it. |
| **`.mcpb` (Claude Desktop)** | built in `build`, attached to the Release | 2.4.2 | (attached by the Release job) | Remove from the Release; users keep the locally-installed bundle until they update. |
| **Homebrew tap** | `release.yml` `homebrew` job → `GRU-953/homebrew-memorised-them-all` | 2.4.2 | same tag push (gated on `HOMEBREW_TAP_TOKEN`; skips cleanly if unset) | Revert the `Formula/mta.rb` bump commit in the tap repo (`git revert`), or re-point `url`/`sha256`/`version` to the prior release. |
| **Docker / GHCR** | `docker.yml` (tag-triggered, multi-arch amd64+arm64) | 2.4.2 | same tag push → pushes `:2.6.0` + `:latest` | `:latest` is mutable — re-tag it to the prior digest, or delete the `:2.6.0` package version in GHCR. Pinned digests stay valid. |
| **MCP registry** | `server.json` (`io.github.gru-953/...`) | manual, owner-only | `mcp-publisher login github && mcp-publisher publish` (interactive GitHub-namespace login) | Re-publish the prior version's `server.json` (idempotent per version). |
| **Claude plugin marketplace** | `.claude-plugin/marketplace.json` | tracks the repo | (consumed live from the repo via `/plugin marketplace add`) | Revert `marketplace.json`/`plugin.json` version on the default branch. |

**Supply chain:** every Action SHA-pinned; CycloneDX SBOM + cosign **keyless single-file
`*.sigstore.json`** bundle per artifact (verify with the pinned-identity command in
`PUBLISH_MANIFEST.md`); PyPI-first **halt-on-partial** (a failed PyPI step ships nothing
downstream); `skip-existing` makes re-runs idempotent; tag==version gate (`check_versions.py`).

## Release notes (draft — from history since v2.4.2)
**v2.6.0** — see `CHANGELOG.md` [2.6.0] + [2.5.0]:
- Cross-AI one-command auto-config (`mta setup`): Claude, Gemini, Cursor, VS Code, Windsurf,
  OpenAI Codex; Grok via discovery; ChatGPT/xAI documented remote path.
- Recall ~8.8× faster (cached BM25 index) + meta-only load; entity resolution de-O(n²)'d with a
  documented `MTA_RESOLVE_MAX_NAMES` cap; convert ~138× faster on text/data corpora (inline path).
- Supply chain: cosign single-file Sigstore bundle. Windows `mta setup` hardening; recall-path
  size-gating; 0600 config backups. Versioned cross-AI export spec (`docs/export-format/v1`).

## CI matrix — tested | untested (honest)
CI (`ci.yml`) runs on each cell below. The host I verified on is **Linux x86_64** (full offline
suite + coverage + benchmark). Per-arch status:

| OS \ arch | x86_64 | arm64 |
|---|---|---|
| **Linux** | ✅ tested (CI `ubuntu-latest` + local host) | ⬜ untested (no `ubuntu-*-arm` runner configured) |
| **macOS** | ⬜ untested (no `macos-13`/x86 runner configured) | ✅ tested (CI `macos-latest` = arm64) |
| **Windows** | ✅ tested (CI `windows-latest`) | ⬜ untested (no Windows-arm64 runner) |

GHCR images are built multi-arch (amd64+arm64) but the **arm64 image is not runtime-smoke-tested**
in CI. Closing the untested cells = adding `ubuntu-24.04-arm` / `macos-13` matrix entries
(follow-up; not changed here to avoid altering green CI I can't re-verify for new cells).
