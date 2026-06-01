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
