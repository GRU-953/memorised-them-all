# THEME_Z_PLAN.md — the road to graph schema v3 (the next major)

**Status:** kickoff (S28). This is the implementation plan for the roadmap's reserved
**Theme-Z** marquee (`ROADMAP_V3.md`) — the *next* major after v3.x. It accumulates on
`develop` as additive bricks until the cohesive, breaking schema bump ships as one major.

**Why a separate plan:** v3.0.0 already delivered the owner-approved "living memory +
interchange" set (and `store.SCHEMA_VERSION` is at **2**: `documents[].sha256`). Theme-Z is
the *graph* schema evolution; it bumps `SCHEMA_VERSION` to **3** only when the breaking set
lands together (recall/render rewrite), per ADR-010 — not brick by brick.

## Load-bearing contracts (must hold for every brick) — from ROADMAP_V3 [C1]–[C6]
- **[C1] Determinism.** Fresh digest → byte-identical `graph.json`/`bm25_index.json`/
  `memory.md`. Any direction/score must be stored canonically (deterministic), or carved out
  and `stats.mode`-stamped.
- **[C2] Atomic writes** via the single `mta/core/_io.py` writer.
- **[C5] Migration.** A real schema bump ships: a registered `_MIGRATIONS[2]` step, a frozen
  v2→v3 fixture + idempotence test, atomic multi-file commit (sentinel), backup-abort-on-fail,
  and `mode=migrated` marking. Migrated ≠ fresh (excluded from byte-identity; recall-parity vs
  the pre-migration store).
- Token-free · 100% local · model-free — unchanged.

## Bricks (ordered; each a `wp-<id>` branch → PR into `develop`, NOT released alone)

### ✅ WP-120 — rule-based typed/directional relations (DONE, additive — S28)
Verb-cue engine (`extract._typed_relation`, `_REL_CUES`) promotes a cued entity pair to a
directed typed relation; `graph.build_graph` records `(type, from, to)` on the edge;
`digest._edge_doc` serialises a deterministic, additive `edges[].relations:[{type,from,to}]`.
Backbone/weights/communities unchanged (precision gate: non-cued edges byte-identical). No
schema bump (additive). Tests: `tests/test_typed_relations.py`. **English-only.**

### WP-123 — fact salience + confidence (+ provenance codepoint-offset spans)
Add a deterministic numeric `salience` and `confidence ∈ [0,1]` per fact, and a
`span:{doc, start, end}` over the digest-time `.md` (store the converter-fingerprint; mark
stale on mismatch). Additive to `nodes[].facts[]`. Pairs with WP-134.

### WP-121 (sub-types half) — entity sub-types in the schema
Per-script `_SCRIPT_BLOCKS` resolution work is the v2.9 half; the **schema** half here adds a
closed `subtype` enum to nodes (gated on the 4 proofs in ROADMAP_V3 WP-121).

### WP-134 — provenance pointers over text (consumes WP-123 spans)
Recall cites `doc + codepoint-offset`; pointer-only stays token-free.

### WP-122 (pin) — community-algorithm pin ([C1])
Make NetworkX Louvain the deterministic default regardless of `leidenalg` presence
(canonical node ordering; `_from_sets` numbers communities by `min(sorted(member_ids))`);
Leiden strictly opt-in (`MTA_COMMUNITY_ALGO=leiden`). **Breaking** (changes partitions) →
part of the major.

### WP — recall/render v2 + export-format v2
Recall/render consume the new fields (still token-free, per-payload byte-capped). Ship
`docs/export-format/v2/` (new fields optional; v1 down-projection through v3.1, warn, remove
≥ v3.2); bundle carries `format_version`; v2 schema CI-enforces `confidence ∈ [0,1]`, salience
numeric, relation direction/type closed enum, offsets non-negative & bounded.

### The schema bump (closes the major)
When the above are in, bump `store.SCHEMA_VERSION` → **3** in one commit with the full [C5]
migration machinery + the breaking recall/render switch, and cut the major.

## Out of scope (per ROADMAP_V3 "won't-do")
Any LLM/embedding in the default path; Bengali verb analysis (WP-120 is English-only);
spreadsheet aggregation/charting; blanket cross-script normalization.
