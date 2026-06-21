# ROADMAP_V3.md — the road to v3.0.0

**Status:** planning artifact (S26). Source of truth for the v2.7 → v3.0.0 arc. Mints WPs into
`PROGRESS.md`; nothing here is built until a WP is taken on a `wp-<id>-<slug>` branch → PR into
`develop`. Baseline: **v2.6.2 SHIPPED** on all channels (PyPI · GitHub Release · `.mcpb` · Homebrew ·
GHCR multi-arch), cross-AI `mta setup`, 8 MCP tools, 100% local / token-free / deterministic /
model-free.

## Load-bearing invariants (every item is checked against these — CI enforces)
Token-free (tiny tool results; document contents never returned to the model) · 100% local / no
telemetry · deterministic byte-identical output · **model-free by default** · dependency-free
classical/offline fallback · atomic crash-safe writes. **Anything that risks one is opt-in with a
graceful fallback** — flagged ⚠️.

## What makes 3.0.0 a *major*
Semver-major = a breaking change. The only compatibility break that doesn't violate an invariant is
the **on-disk / exported graph schema** — and the code already waits for it: `store.py` has an empty
`_MIGRATIONS = {}` registry ("a future incompatible schema bump registers its step here"). So:
- **v2.7 → v2.9 (minors):** additive quality + features; ship continuously.
- **v3.0.0 (major):** **graph schema v2** (typed/temporal/confident facts, salience, provenance
  offsets, entity sub-types) — auto-migrated via `_MIGRATIONS`, plus the recall/render upgrades that
  exploit it.

---

## Themes & Work Packages

### Theme A — Quality & hardening
| WP | Item | Why | Invariant |
|----|------|-----|-----------|
| WP-100 | Atomic `convert.py` `.md` write (close **R-19**) | torn `.md` on crash; all else is atomic | reuse `_atomic_write_text` |
| WP-101 | Generalize skeleton-merge to all Brahmic blocks (close **R-16**) | Devanagari/Tamil still skeleton-merge; only Bengali guarded | deterministic |
| WP-102 | Length-aware fuzzy threshold (mitigate **R-17**) | 88-ratio collapses short names (করিম/করিমা) | deterministic |
| WP-103 | CI/coverage truthing: publish coverage %, add Py 3.13 (3.14 when wheels land, **R-06**), arm64 runtime smoke, Docker clean-image matrix (**R-01**) | honest matrix | — |
| WP-104 | Reproducible lockfile w/ hashes (close **CI-09**) | bit-identical builds | supply-chain |
| WP-105 | Test depth: community-detection determinism, recall/low-confidence sensitivity, property tests for byte-caps & atomic writes, large/degenerate-graph fuzzing | thin areas | — |

### Theme B — Conversion: files → Markdown (stability · accuracy · performance · efficiency)
The convert pipeline (`convert.py`, MarkItDown, OCR, `archive.py`, `bangla_legacy.py`).
| WP | Item | Why / target |
|----|------|--------------|
| WP-110 | **Conversion stability**: harden per-file isolation, adaptive timeouts, partial-result salvage, never-abort-batch guarantee, malformed/huge-file fuzzing | one bad file never stalls or aborts a batch |
| WP-111 | **Conversion accuracy/fidelity**: clean Markdown tables from CSV/XLSX; PDF layout/column/heading fidelity; HTML/EPUB cleanup; image alt/caption extraction; preserve lists & structure | fidelity diff-tests on a fixed corpus, no regressions |
| WP-112 | **OCR quality**: DPI/preprocessing/deskew, auto language detection, mixed-script pages; broken-font Bengali re-OCR improvements (ties Theme K) | higher recall on scanned docs |
| WP-113 | **Conversion performance/efficiency**: extend the inline fast-path to more types; **content-hash conversion cache** (skip unchanged → ties incremental); streaming for large files; parallel-worker tuning; bounded peak RAM | throughput baseline tracked in `eval/bench.py` |
| WP-114 | **Format coverage + granular extras**: more input types; OCR/PDF/Office become opt-in extras (ties Theme J) | tiny core, full power on demand |

### Theme C — Data mapping & graphing
The knowledge-graph build (`extract.py`, `resolve.py`, `graph.py`, `render.py`).
| WP | Item | Why | Target version |
|----|------|-----|----------------|
| WP-120 | **Relation extraction v2**: verb-mediated, **typed & directional** relations (beyond co-occurrence) | richer, more accurate graph | needs schema v2 → **3.0** |
| WP-121 | **Entity resolution & typing**: sub-types, Brahmic generalize (with WP-101), length-aware fuzzy (WP-102), gazetteer expansion, embedding-collision hardening | fewer mis-merges, better typing | 2.9 / 3.0 |
| WP-122 | **Community quality**: multi-entity + TF-IDF labels (less noise), optional hierarchical communities, fixed-seed determinism | readable themes | 2.9 |
| WP-123 | **Fact salience + confidence ranking** (close **R-1**) + **provenance char-offset spans** (ties I-3) | best facts surfaced; exact citations | needs schema v2 → **3.0** |
| WP-124 | **Graph hygiene & metrics**: dedup/junk filtering, centrality + theme-size surfaced in `memory_overview` | cleaner, more informative | 2.9 |
| WP-125 | **Graph exports + opt-in zero-network static HTML viewer**: GraphML / GEXF / CSV + a deterministic offline viewer (brings visualization back *without* re-breaking determinism — export artifact, not a live feature) | external tools + human browse | 2.9 |

### Theme D — Retrieval (IR) quality & token frugality
| WP | Item | Why | Invariant |
|----|------|-----|-----------|
| WP-130 | Recall query filters (by document / entity type / theme) | precise recall | additive args |
| WP-131 | ⚠️ **Opt-in hybrid retrieval** (BM25 + optional local embeddings + lexical gate) | higher recall | default stays pure-BM25, model-free, zero-compiled-dep |
| WP-132 | Layout/table-aware chunking (ties WP-111) | tables/forms stop becoming noise | deterministic |
| WP-133 | **Token frugality**: adaptive recall payloads, `MTA_RECALL_BUDGET` byte cap, deduped/compressed synopsis | already token-free → make it frugal | median recall ≤ ~1.5 KB, overview ≤ ~2 KB |
| WP-134 | **Provenance pointers over text** (schema v2): cite by `doc + offset` so the model fetches only if needed | fewer tokens still | 3.0 |

### Theme E — Lifecycle & large-corpus UX
| WP | Item | Invariant |
|----|------|-----------|
| WP-140 | Incremental / `mta watch` mode (content-hash manifest sidecar) | watch opt-in; request model stays default |
| WP-141 | Snapshot / rollback of a memory (versioned store dirs) | builds on backup-before-overwrite |
| WP-142 | `forget --secure` best-effort secure delete | additive |
| WP-143 | ⚠️ Encryption-at-rest, opt-in passphrase (ADR-008) | default unencrypted preserves portability |
| WP-144 | Multi-project recall / federation | additive |

### Theme F — Cross-AI breadth + novice how-to guides
| WP | Item | Notes |
|----|------|-------|
| WP-150 | Add **Ollama & LM Studio** to `mta setup` | both speak MCP; same idempotent writer pattern |
| WP-151 | Next tier: Jan, Cherry Studio, AnythingLLM, Continue, Zed, Msty + generic `mta setup --client <name>` | "etc." covered |
| WP-152 | `mta setup` one-click: detect → configure → **verify** (round-trip a tool call) → "✅ working in …"; zero copy-paste | first-run friendliness |
| WP-153 | `mta doctor`: plain-English diagnosis (no stack traces) | novice self-service |
| WP-154 | **Per-platform beginner guides** `docs/guides/<client>.md` + a "Start here — pick your AI" picker | strictly non-technical: needs · 3-step setup w/ screenshots/GIF · first memory · how to ask · troubleshooting · uninstall |

### Theme G — Mobile: Android & iOS (staged, feasibility-first)
| WP | Item | Feasibility |
|----|------|-------------|
| WP-160 | **Remote-MCP from phones**: connect mobile AI apps to a self-hosted `mta serve --http` server (home PC/NAS/own cloud), with QR-code URL+token pairing + a novice phone guide | ready now — polish + docs |
| WP-161 | **Android on-device via Termux**: one-line slim-core install (needs Theme J) | achievable after slimming |
| WP-162 | **iOS via a-Shell / remote**: documented path (true on-device iOS Python is sandbox-limited) | partial; remote reliable |
| WP-163 | *(stretch, likely post-3.0)* native companion app (BeeWare/Briefcase or thin Swift/Kotlin shell over the HTTP API) for browse/recall | research, not committed |

Privacy note: "100% local" = user-controlled, no third-party cloud/telemetry. A self-hosted server
(WP-160) honors that even when the phone is a thin client; WP-161 is the purist on-device case.

### Theme H — Frictionless installation + README/USER GUIDE overhaul (novice-first)
| WP | Item | Target |
|----|------|--------|
| WP-170 | **One-command install per platform**: `pipx`, Homebrew, `.mcpb` double-click (Claude Desktop), winget/Scoop/Choco, `install.sh`, Termux one-liner; prerequisite check + friendly guidance if Python is missing | install ≤ 2 actions/surface |
| WP-171 | **README overhaul (novice-first)**: pick-your-AI → install → **first memory in 3 steps**, screenshots/GIFs, FAQ, troubleshooting | non-technical readable |
| WP-172 | **USER_GUIDE.md** + the per-platform guides (with WP-154) | comprehensive, friendly |
| WP-173 | **Reduce prerequisites**: OCR/LibreOffice optional, slim core (ties Theme J), offline-first first-run | fewer moving parts |
| WP-KPI | **Time-to-first-memory < 5 min** for a non-technical user, on each platform | acceptance gate |

### Theme I — Dependency reduction (unblocks mobile + easy installs)
Today's core: `numpy, networkx, rapidfuzz, psutil, markitdown[…], pdfplumber, pillow, pytesseract,
pypdfium2, striprtf`. Goal: tiny pure-Python default, heavy stuff opt-in (per ADR-005).
| WP | Item | Effect |
|----|------|--------|
| WP-180 | Move OCR/PDF/Office stack to extras `[ocr]` `[pdf]` `[office]` | core drops the heaviest wheels |
| WP-181 | Make `numpy` optional (BM25 needs none; numpy → `[hybrid]` extra with WP-131) | smaller core |
| WP-182 | Investigate replacing `networkx` with a small stdlib Louvain (keep determinism) | one fewer dep |
| WP-183 | Harden the pure-Python `rapidfuzz` fallback | core works with **zero compiled deps** → trivial Termux/iOS install |
| WP-KPI | `pip install memorised-them-all` core ≤ ~5 deps, all pure-Python; `[all]` for full power | |

### Theme J — Bijoy & Unicode Bangla (deepen the differentiator)
| WP | Item | Notes |
|----|------|-------|
| WP-190 | Corpus-driven Bijoy/SutonnyMJ map refinement (WP-87b) | grow glyph coverage from real word-forms |
| WP-191 | Safely expand vetted reorder-artifact repairs | panel approved only রম্ন→রু and *rejected* 3 risky ones — revisit behind a **held-out correct-Bengali regression corpus** so we expand without corrupting valid text |
| WP-192 | Better Bijoy PDF text-layer recovery (line-wise `recover_mixed` thresholds; mixed EN+BN) | fewer false negatives |
| WP-193 | Detect more legacy encodings (Boishakhi, Bangla-Word, …) → auto-route | broader coverage |
| WP-194 | Round-trip regression vs the Mukti oracle; grow the BN test corpus | determinism preserved (ties WP-105 accuracy gate) |

### Theme K — Performance · stability · accuracy · efficiency (cross-cutting KPIs)
| WP | Item | KPI |
|----|------|-----|
| WP-200 | Digest throughput (incremental WP-140 + conversion cache WP-113 + cheaper segmentation) | ≥2× faster re-digest on unchanged corpora |
| WP-201 | Recall latency (postings/skip structure on the cached BM25 index) | p95 < 150 ms @ 50k units |
| WP-202 | Accuracy gate (WP-111/112/121/132 + schema v2) on a fixed EN+BN eval set | no hit-rate regressions, ratcheting up |
| WP-203 | Stability (WP-100 + crash-injection/property tests + huge/degenerate-store fuzzing) | zero torn-write paths |
| WP-204 | Efficiency (streaming digest, bounded peak RAM per `MTA_MEMORY_GB`) | documented memory ceiling |

### Theme Z — 🚀 v3.0.0 marquee: Graph schema v2
Auto-migrated via `_MIGRATIONS` (old `graph.json` upgrades in place, backed up first; export-format
bumps v1→v2 with a deprecation window):
- typed & directional relations (WP-120) · temporal & numeric facts (PII-safe) · fact confidence +
  salience ranking (WP-123) · entity sub-types (WP-121) · provenance char-offset spans (WP-134) ·
  recall/render rewritten to exploit them — still token-free, still byte-capped.

---

## Release train

| Release | Marquee | Headline WPs |
|--------|---------|--------------|
| **v2.7.0** | Slim core, easy install & cross-AI breadth | WP-180…183 (deps), WP-170…173 + WP-154 (install + novice docs), WP-150/152/153 (Ollama/LM Studio + one-click + doctor), WP-100/101/102 (R-19/16/17), WP-103/104, WP-110 (conversion stability) |
| **v2.8.0** | Mobile + big-corpus lifecycle + conversion accuracy | WP-160/161/162 (mobile), WP-140…142/144 (lifecycle), WP-111/113 (conversion accuracy + cache), WP-130 (filters), WP-200/203 |
| **v2.9.0** | Accuracy, frugality, Bengali & graphing | WP-133 (token frugal), WP-190…194 (Bijoy/Bangla), WP-121/122/124/125 (mapping/graphing + viewer), WP-131 (opt-in hybrid), WP-132 (table-aware), WP-143 (encryption opt-in), WP-112 (OCR), WP-201/202/204 |
| **v3.0.0** | Graph schema v2 — richer, higher-fidelity, lower-token memory | Theme Z + WP-120/123 (typed relations, salience/confidence), WP-134 (provenance offsets), recall/render v2, auto-migration; WP-163 native companion as a stretch |

## Global acceptance gates
- All invariants preserved (CI-enforced; determinism byte-identical maintained).
- Time-to-first-memory **< 5 min** for a non-technical user, per platform.
- Core deps **≤ ~5, all pure-Python**; `[all]` extra for full power.
- Conversion success **≥ baseline**, no fidelity regressions, on the fixed corpus.
- Recall **p95 < 150 ms @ 50k**; median result **≤ ~1.5 KB**.
- EN+BN hit-rate gate: **no regressions**, ratcheting upward.

## Explicitly out of scope / won't-do
- ❌ Any LLM/embedding/summarizer in the **default** path (breaks model-free + determinism). An
  `ask`/`summarize` tool stays the host model's job; we only return citable slices.
- ❌ Always-on network, telemetry, or returning document contents to the model.
- ❌ Mandatory heavy/compiled deps. The `_rearrange` linearization (perf-only, fidelity risk) and
  full LIFE-02 refcounting (narrow, mitigated) stay deferred — low value.

## Open decisions for the owner
- **ADR-008** encryption-at-rest stays opt-in by default (override if encryption-by-default wanted).
- Native mobile app (WP-163): research only — confirm before committing engineering to it.
- Hybrid retrieval (WP-131): keep pure-BM25 as the shipping default; embeddings are an opt-in extra.
