# Decisions (lightweight ADRs)

Each entry: decision · why · alternatives weighed. Includes deliberately-declined ideas. Newest at the bottom.

---

## ADR-001 — Branching model & where program state lives
**Decided (S01):** `main` stays always-releasable; `develop` is the long-lived integration branch and **holds the `program/` cross-session state**; code Work Packages run on short-lived `wp-<id>-<slug>` feature branches that PR into `develop`; `develop` → `main` for releases (tag-triggered).
**Why:** matches the program's "main stays releasable" rule and standard gitflow. Keeping `program/` on `develop` means every resuming session pulls **one** working branch (`develop`) and finds current state, while `main` and the published artifacts stay free of internal scaffolding.
**Program-state docs** are committed directly to `develop` (they are meta, not product code, and need no code-review gate). The **plan gate** is satisfied by owner review of the *presented* artifacts, not by a PR merge.
**Alternatives:** (a) program/ on `main` — pollutes releases/sdist; (b) a PR for every doc edit — friction with no review value. Both declined.

## ADR-002 — v1 scope: Claude-first + core channels (owner-confirmed, spec §1a)
**Decided (S01):** v1 hardens & ships the **Claude** surfaces (Desktop `.mcpb` + Code plugin) plus the **core channels** (PyPI, Homebrew, GitHub Release) to a fully functioning, tested, published state. **Phase 3 (Gemini / ChatGPT / Ollama / LM Studio / Grok) and the extra publishing channels (containers / registries / store listings beyond core) are designed-for-now but delivered in v1.x+ increments.**
**Why:** owner-confirmed; avoids blocking a shippable v1 on cross-AI breadth. Architecture must stay portable (single canonical engine; clean transport/schema/backend seams) so later clients drop in without a rewrite.
**Implication:** every WP is tagged `v1` or `v1.x+`; the v1 set is ordered first; the release train ships core channels in v1 and is extended later. Revisit at the plan gate.

## ADR-003 — Audit method: parallel fresh-eyes subagents (spec §5)
**Decided (S01):** Phase-1 audit run as **9 independent, dimension-scoped subagents** (a background workflow), each reading only its slice + verifying external specs live, returning structured cited findings; the orchestrator synthesizes into `AUDIT.md`. External-publishing facts (PyPI/Homebrew/CI/releases) verified directly by the orchestrator via `gh`/`curl`, not by agents.
**Why:** the spec requires independent / fresh-eyes review to counter self-confirmation bias; fan-out also covers the surface faster. Owner opted into multi-agent workflows.

## ADR-004 — Auto-update default = offline-first (owner choice, S01 Q1)
**Decided:** default to the **PyPI-pinned MarkItDown** (already a dependency) so first-run works fully offline and reproducibly; the "pull latest from MarkItDown git `main`" behavior becomes an **explicit, integrity-verified opt-in** (`mta update` / `MTA_AUTO_UPDATE=upstream`), pinned to a commit/tag and hash/signature-checked before applying.
**Why:** fixes the Critical **PKG-03** and **SEC-04** — restores the "100% local / works offline" headline and removes the unpinned supply-chain path. README wording on "auto-updating / pulls latest" will be corrected. **Drives WP-10 + WP-13.**

## ADR-005 — Dependency policy = stdlib-first, small vetted deps allowed (S01 Q2)
**Decided:** prefer the standard library (e.g. cross-process locking via `fcntl`/`msvcrt`); a few small, well-maintained, permissively-licensed deps (e.g. `filelock`, `platformdirs`) are acceptable **when they clearly reduce risk**, each justified here. **No heavy/model dependencies in v1** (rerank etc. → v1.x+). Honors the §10 "prefer stdlib, justify new deps" constraint.

## ADR-006 — Release hardening = full (S01 Q3)
**Decided (target for WP-40):** **OIDC/Trusted Publishing** to PyPI (no long-lived token), **automated Homebrew-tap bump** via cross-repo token/deploy key, **SBOM + sigstore/cosign signing + provenance** per artifact, **SHA-pinned** Actions, committed **lockfile**, **idempotent halt-and-rollback** (no partial releases), tag==version gate, post-publish re-install smoke.
**Owner-action items (flagged for WP-40, not blocking earlier WPs):** (1) configure a PyPI Trusted Publisher for this repo+workflow; (2) provide the release workflow cross-repo write to `homebrew-memorised-them-all` (fine-grained PAT or deploy key, referenced by secret name only).

## ADR-007 — Branch flow = full gitflow, push authorized (S01 Q4)
**Decided:** durable authorization to **push `develop` + `wp-*` feature branches and open PRs into `develop`**; **never push `main` directly**; releases via tag (`develop`→`main` for a release). Reversible (branches can be deleted). Confirms ADR-001 operationally.

## ADR-008 — Encryption-at-rest default = opt-in (assumption; owner may override)
**Decided (assumption, not separately asked):** memory store stays **unencrypted by default** to protect simplest-install + the copy-to-another-machine portability promise; an **opt-in passphrase** + secure-delete `forget` is a **v1.x+** roadmap item. Flag for owner correction if encryption-by-default is desired.
