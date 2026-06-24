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

### ✅ WP-123 — fact salience + confidence (DONE, additive — S30)
`graph.build_graph` now stamps each fact with a deterministic `salience` (int — count of
distinct entities the fact names) and `confidence ∈ [0,1]` (≥0.7 when it explicitly names a
holder, 0.5 for a fallback attachment). Additive to `nodes[].facts[]`; facts are NOT reordered,
so recall meta / bm25 / render are unchanged and `graph.json` stays byte-identical run-to-run.
Tests: `tests/test_fact_salience.py`. Accumulating on `develop` (not released alone).

### ✅ WP-123b — provenance codepoint-offset spans (DONE, additive — S31)
Solved without touching the determinism-critical segment/extract pipeline: a **post-digest
best-effort locator** (`digest._attach_fact_spans` + `_normalize_with_map`) finds each fact in
its source `.md` via a whitespace-/case-tolerant search that maps back to exact codepoint
offsets, stamping `span:{doc,start,end}`. `documents[]` gain an `md_sha` fingerprint of the `.md`
the offsets index into (stale-detection). A fact whose stored text isn't verbatim in the `.md`
(PII-redacted / Bengali-reorder-normalised) gets no span — honest best-effort. Additive,
deterministic; recall/render/meta/bm25 untouched. Tests: `tests/test_provenance_spans.py`.
A future refinement could thread exact sentence offsets through segmentation for 100% coverage.

### ✅ WP-121 (sub-types half) — entity sub-types in the schema (DONE, additive — S32)
`extract._infer_subtype` + `graph.build_graph` stamp graph nodes with an additive, deterministic
closed-enum `subtype` refining the coarse `type` (org → government/financial/education/nonprofit/
company; place → division/district/upazila/city/town/union/village/region/ward, gazetteer-first).
High-precision (no cue ⇒ no field), English-only. Tests: `tests/test_entity_subtypes.py`.
*(The per-script `_SCRIPT_BLOCKS` **resolution/normalization** half stays a separate v2.9-style
item — gated on ROADMAP_V3 WP-121's 4 proofs — not part of this schema brick.)*

### ✅ WP-134 — provenance pointers in recall (DONE, additive — S33)
First **consumer** brick. `recall._node_spans` + `_hit` surface the WP-123b fact spans as a
pointer-only `spans` list (`{doc,start,end}`, capped) on entity hits — derived from
`graph.json` **at query time**, so the stored recall index (`vectors.json`/`bm25_index.json`)
is untouched and old stores work with no re-digest. Pointer-only → token-free; theme hits and
unlocatable facts have no `spans`. Tests: `tests/test_recall_provenance.py`.

### WP-122 (pin) — community-algorithm pin ([C1])  ← NEXT
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
