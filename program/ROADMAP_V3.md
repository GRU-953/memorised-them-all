# ROADMAP_V3.md — the road to v3.0.0

**Status:** planning artifact (S26), **hardened after Round 1 of a 10-lens adversarial review** (invariant-integrity ·
feasibility · semver/sequencing · novice-UX · security/privacy · KPI/measurability · scope/overlap · Bengali/i18n ·
directive-traceability · migration/back-compat). Source of truth for the v2.7 → v3.0.0 arc. Mints WPs into
`PROGRESS.md`; nothing here is built until a WP is taken on a `wp-<id>-<slug>` branch → PR into `develop`.
Baseline: **v2.6.2 SHIPPED** on all channels (PyPI · GitHub Release · `.mcpb` · Homebrew · GHCR multi-arch), cross-AI
`mta setup`, 8 MCP tools, 100% local / token-free / deterministic / model-free.

---

## Load-bearing invariants
Token-free (tiny **per-payload-capped** results; document contents never returned to the model) · 100% local / no
telemetry · deterministic byte-identical output · **model-free by default** · dependency-free classical/offline
fallback · atomic crash-safe writes. **Anything that risks one is opt-in with a graceful fallback** — flagged ⚠️.

## Cross-cutting engineering contracts (every WP must honor; referenced as [C1]…[C6])
These were added because Round-1 review found WPs that *assumed* an invariant held without binding it.

- **[C1] Determinism contract.** "Byte-identical" means: a **fresh** digest of a corpus yields identical
  `graph.json`/`vectors.*`/`bm25_index.json`/`memory.md` across runs, OSes, and `PYTHONHASHSEED` (the existing
  SHA-256 gate). **Known live gap to close:** community detection defaults to `community_algo="auto"`, which runs
  Leiden *if `leidenalg`+`igraph` are installed* else NetworkX Louvain else greedy — i.e. **the default partition is
  environment-dependent today** (different optional deps → different `graph.json`). WP-122 MUST pin a single default
  algorithm (NetworkX Louvain, fixed seed, canonical node ordering) with Leiden strictly opt-in
  (`MTA_COMMUNITY_ALGO=leiden`) and **excluded** from the determinism gate. A CI test digests a fixture **with and
  without `leidenalg` installed** and asserts byte-identical `graph.json`. OCR (WP-112) and hybrid embeddings (WP-131)
  are float/hardware-sensitive and are likewise **carved out** of the byte-identity gate (the deterministic BM25/graph
  floor still applies); a store records its `mode` so deterministic vs augmented builds are distinguishable.
- **[C2] Atomic-write contract.** One shared crash-safe writer (`newline=""` + fsync + `os.replace`). WP-100 promotes
  `_atomic_write_text` from `store.py` into a shared `mta/core/_io.py` so `convert.py` and `store.py` use **one**
  writer (no copy-paste divergence). CI: a meta-test greps `mta/` for raw `open(..., "w")` outside the helper and
  fails; crash-injection tests (kill between temp-write and rename) assert the prior content survives.
- **[C3] No-egress contract.** Digest, recall, the WP-125 viewer, and every **default** install path make **zero**
  outbound calls except the documented, disableable update check (`MTA_AUTO_UPDATE=off`). The only *new* permitted
  egress is the WP-131 embedding-model download — one-time, consented, hash-verified, never on a digest/recall hot
  path. A CI no-egress test (extending the model-free/no-network checks) enforces this.
- **[C4] Supply-chain contract.** Every dependency **extra** (`[ocr]`/`[pdf]`/`[office]`/`[hybrid]`/`[graph]`/`[all]`)
  and every install channel (winget/Scoop/Choco/…) is **hash-pinned to the signed release**, enumerated in the
  CycloneDX SBOM, installed in the CI matrix to keep pins live, and reported by `mta doctor`. New OS package-manager
  manifests are **auto-bumped from the canonical signed artifacts** (like the Homebrew tap, ADR-006), never
  hand-edited, with a post-publish reinstall+cosign-verify smoke. Embedding models (WP-131) are **safetensors-only
  (no pickle)**, pinned by content hash, fetched over TLS from a declared source recorded in the SBOM.
- **[C5] Migration contract** (binds Theme Z). Schema-v2 migration is **atomic at the store level** (stage all of
  `graph.json`+`vectors.*`+`bm25_index.json`, swap via rename behind a `.migrating` sentinel that `load_graph`
  honors; a crash leaves the v1 store fully intact), performed **once, eagerly, on first v3 load**, with the
  pre-migration store copied to `backups/<ts>-pre-migrate-v1/` **before any write** (a *failed* pre-migrate/downgrade
  backup **aborts** the overwrite — not best-effort). `digest.py` must stamp `version = store.SCHEMA_VERSION` (not the
  current hardcoded literal `1`); a lint fails CI on any literal `"version": N` in producers, and a CI check asserts
  `_MIGRATIONS` forms a contiguous `1→2→…→SCHEMA_VERSION` chain. **Migrated ≠ fresh:** v1 stores lack the source
  context v2 needs (typed relations, char-offsets, salience), so migration **up-casts existing fields only**
  (confidence defaulted, offsets `null`, relations untyped) and is documented "**lossy-forward — re-digest to populate
  v2-native fields**"; `memory_overview` surfaces a "migrated — re-digest for full v2 fidelity" flag. Every
  `_MIGRATIONS` step ships a **frozen real v1→v2 fixture test** (load → migrate → assert: all v1 nodes/edges/facts
  survive with stable IDs; validates against `docs/export-format/v2/graph.schema.json`; recall parity on a fixed query
  set) plus an **idempotence** test (`migrate(migrate(x))==migrate(x)`). The existing `test_migration.py` monkeypatched
  step is *not* sufficient.
- **[C6] Measurement contract.** A KPI is either a **CI gate** (machine-independent, stable, fail-closed) or a
  **benchmark** (reported on named hardware, non-blocking) — never a wall-clock CI gate (GitHub runners vary 2–10×).
  **Prerequisite (WP-202a, lands first in v2.7):** wire `eval/run_eval.py` into `ci.yml` (it is **not** today), commit
  the real **EN+BN eval corpus** (today's `eval/corpus` is 4 English files / 0 Bengali — incl. Unicode + Bijoy-legacy
  Bengali tied to WP-194) and a **conversion-fidelity fixture set** (PDF/DOCX/XLSX/HTML/image + golden Markdown), and
  freeze v2.6.2 reference numbers into `eval/baseline.json`. Until that lands, the roadmap says "test-enforced where a
  test exists; eval/bench are pinned **manual** harnesses" — it must not claim "CI-enforced."

## What makes 3.0.0 a *major*
Three things ride the major (each is a compatibility break that no minor should hide):
1. **Graph schema v2** (typed/temporal/confident facts, salience, provenance offsets, sub-types) — auto-migrated per [C5].
2. **Community-algorithm pinning** (closing [C1]) changes existing `graph.json` partitions → an output break; it
   regenerates byte-identically on re-digest under the major.
3. **Default-dependency slim-down** (WP-181b: OCR/PDF/Office/numpy leave the *default* install). Removing a
   default-on capability (OCR is default-on today) is backward-incompatible (**ADR-010**). v2.7 only *adds* the extras
   + `[all]` + a deprecation notice; the actual removal-from-core lands with the major.

## Effort / Risk legend
Each WP carries **Effort {S,M,L}** and **Risk {Lo,Md,Hi}** (Risk = invariant-jeopardy + uncertainty). Release budget
rule of thumb: **≤ 3 L-items per minor.**

---

## Themes & Work Packages

### Theme A — Quality & hardening
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-100 | Atomic `convert.py` `.md` write (close **R-19**) via shared `_io.py` [C2] | S/Lo | torn `.md` on crash today (`convert.py:548`) |
| WP-101 | Per-script Brahmic normalization (close **R-16**) — see WP-121 (NOT a blanket rule) | S/Md | fix `_NORM_RE` whitelist **and** `_norm` combining-filter together, per-block |
| WP-102 | Length-aware fuzzy threshold (mitigate **R-17**) | S/Lo | scale 88-ratio by token length (করিম/করিমা) |
| WP-103 | CI/coverage truthing: publish coverage %, **add Py 3.13** (3.14 when wheels land, **R-06**), arm64 smoke, **Docker clean-image matrix** (**R-01**) that runs the [C1] cross-env determinism assertion | M/Lo | matrix changes **additive only** this train; any version *drop* → major |
| WP-104 | Reproducible lockfile **with hashes** (close **CI-09**); extras hash-pinned [C4] | S/Lo | |
| WP-105 | Test depth: community-detection determinism [C1], recall/low-confidence sensitivity, **property tests** for per-payload byte-cap & atomic writes [C2], large/degenerate-graph fuzzing | M/Md | |

### Theme B — Conversion: files → Markdown (stability · accuracy · performance · efficiency)
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-110 | **Stability**: per-file isolation hardening, adaptive timeouts, partial-result salvage, never-abort-batch, malformed/huge-file fuzzing | M/Lo | |
| WP-111a | **Tractable fidelity**: clean Markdown tables from CSV/XLSX (owns the **table data model**), HTML/EPUB boilerplate strip, list/structure preservation, image alt/caption | M/Md | golden-diff tests on the conversion fixture set |
| WP-111b | **Best-effort PDF** reading-order/column/heading recovery — explicitly best-effort, bounded to pdfplumber/pdfminer (wire the already-declared but unused `pdfplumber`) | L/Md | PDF-column cases tracked, **not** pass/fail gates |
| WP-112a | **OCR engine quality**: DPI/deskew/preprocessing (deterministic); default `-l eng+ben` multi-lang (autodetect **advisory only**, never single-pass exclusive); **confidence floor** drops garbage | M/Md | OCR stays **opt-in**, carved out of determinism [C1]; moved to **v2.8** beside WP-111 |
| WP-113 | **Performance/efficiency**: consume WP-140's manifest to skip unchanged conversions; streaming for large files; worker tuning; bounded RAM. **Cache key = content-hash ⊕ converter-fingerprint** (mta+MarkItDown+OCR/LibreOffice version + bangla-map revision + relevant cfg) so a hit is byte-identical to a fresh convert; miss/garbage → re-convert | M/Md | depends on WP-140 |
| WP-114 | Format coverage + granular extras (OCR/PDF/Office → opt-in extras, see Theme I) | S/Lo | |

### Theme C — Data mapping & graphing
| WP | Item | E/R | Target | Notes |
|----|------|-----|--------|-------|
| WP-120 | **Rule-based** verb-mediated **typed & directional** relations (model-free): English verb→relation lexicon + SVO over existing sentence splits; `DiGraph` + edge `type`; **falls back to undirected `co_occurs`** when no pattern matches | L/Hi | 3.0 | **English-only** in v3.0 (no Bengali verb analysis exists); **precision-gated** — a typed edge must not reduce community/recall quality vs the co-occurrence baseline |
| WP-121 | **Entity resolution & typing**: sub-types; **per-script `_SCRIPT_BLOCKS` table** (Bengali/Devanagari/Tamil/Telugu/…) fixing both `_norm` steps; Tamil/Telugu **opt-in**; gazetteer expansion; embedding-collision hardening. **Never reuse `_rearrange` (Bijoy-specific) for other scripts.** | L/Hi | 2.9/3.0 | per-script **minimal-pair over-merge gate** (काली≠कुल, கடல்≠கடா); generalization may only **reduce** merges, never increase |
| WP-122 | **Community quality + determinism pinning [C1]**: pin NetworkX Louvain (seed, canonical ordering) as the deterministic default, Leiden opt-in & gate-excluded; multi-entity + TF-IDF labels; optional hierarchical communities | M/Hi | 2.9 | partition byte-identical regardless of optional graph libs |
| WP-123 | **Fact salience + confidence** (close **R-1**) — *produces* the values; **provenance char-offset spans** (codepoints over the digest-time `.md`, stored with the converter-fingerprint, stale-marked on mismatch) | L/Md | 3.0 | schema v2; pairs with WP-134 (consumer) |
| WP-124 | Graph hygiene & metrics: dedup/junk filtering, centrality + theme-size in `memory_overview` | M/Lo | 2.9 | |
| WP-125 | **Exports**: GraphML/GEXF/CSV (deterministic) | S/Lo | 2.9 | split from the viewer |
| WP-126 | **Opt-in zero-network static HTML viewer** [C3]: vendored inline JS/CSS (no CDN/font), **CSP `default-src 'none'`**, all labels/facts **HTML-escaped** (XSS test asserts a payload in a label is inert), CI asserts **zero off-origin URLs** + no wall-clock/abs-path → deterministic | L/Md | 2.10 | consumes the canonical partition (WP-122) |

### Theme D — Retrieval (IR) quality & token frugality
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-130 | Recall query filters (by document / entity type / theme) | S/Lo | additive args |
| WP-131 | ⚠️ **Opt-in hybrid retrieval** (BM25 + optional local embeddings + lexical gate) | L/Hi | default pure-BM25; enabling `[hybrid]` **never** auto-downloads (model user-provided/pre-pulled, else clear error → BM25 fallback) [C3]; model **safetensors-only, hash-pinned** [C4]; hybrid scores **only re-rank**, never bypass the off-topic gate; hybrid output **excluded** from byte-identity [C1] |
| WP-132 | Layout/table-aware **chunk-boundary** logic — consumes WP-111a's table model; **never re-segments a table mid-row** (owns boundaries only, not the table representation) | M/Md | co-located with WP-111a (v2.8) |
| WP-133 | **Token frugality**: `MTA_RECALL_BUDGET` = a **hard total-payload UTF-8 byte cap** at the tool boundary (today only per-field caps exist), applied **deterministically** — cap each field, then drop **whole trailing hits in fixed rank order** until under budget (never resize a field by neighbours/k); deduped/compressed synopsis | M/Md | schema-v1-achievable; **reconcile the number with shipped caps** (k=5 worst-case ≈ 8 KB today) — set the budget, then prove median ≤ it |
| WP-134 | **Provenance pointers over text** (schema v2): cite by `doc + codepoint-offset` (consumes WP-123 spans); pointer-only stays token-free | M/Md | 3.0; further frugality beyond WP-133 |

### Theme E — Lifecycle & large-corpus UX
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-140 | Incremental / `mta watch` mode — **owns the single content-hash manifest** (sidecar + invalidation contract); WP-113 consumes it | M/Md | watch opt-in; request model default |
| WP-141 | Snapshot / rollback — each snapshot dir records `schema_version`; **restore routes through `load_graph`/`migrate_doc`** and refuses-with-backup if newer [C5]; document the relationship to `_backup_store` | M/Md | |
| WP-142 | `forget --secure` — **documented as best-effort only**: overwrite cannot erase on SSD/flash/CoW/synced/snapshotted stores; the real guarantee is **crypto-erase via WP-143**; also targets `state/http_token`, `_unpacked/` scratch, snapshots | S/Md | tie to WP-143 |
| WP-143 | ⚠️ **Encryption-at-rest** (ADR-008) — **threat model: defends a stolen/cloud-synced `MTA_HOME` at rest; NOT a running process / memory / swap**; encrypts the **whole content corpus** (`markdown/`, `memory/`, `graph.json`, `vectors.*`), not just the graph; vetted KDF (argon2id/scrypt, stated params), AEAD; passphrase never persisted; **encryption wraps before the atomic temp** (no plaintext temp); migration/backup operate on decrypted plaintext (passphrase required, else **decline** — never "corrupt→backup"); determinism defined on **plaintext** (nonce-based ciphertext is not reproducible); encrypted stores excluded from the human-readable/diff-friendly guarantee | L/Hi | v2.10 |
| WP-144 | Multi-project recall / federation | M/Lo | additive |

### Theme F — Cross-AI breadth + novice how-to guides
**Currently supported (v2.6.x), each gets a WP-154 novice guide:** Claude (Desktop/Code), **Gemini**, **Grok**
(auto-discover), Cursor, VS Code, Windsurf, **Codex**.
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-150 | Add **Ollama & LM Studio** to `mta setup` | M/Lo | both speak MCP |
| WP-151 | Next tier: Jan, Cherry Studio, AnythingLLM, Continue, Zed, Msty + generic `mta setup --client <name>` | M/Lo | |
| WP-152 | `mta setup` one-click: detect → configure → **verify** (round-trip a tool call) → "✅ working in …"; **on verify failure auto-print the WP-153 doctor diagnosis** | M/Md | |
| WP-153 | `mta doctor`: plain-English diagnosis (no stack traces) **+ a failure-symptom catalogue keyed on what the user sees in their AI app** (works even before `mta` is callable; the `.mcpb` no-terminal user is routed to `memory_status` inside the AI) | M/Md | |
| WP-154 | **Per-platform guides** `docs/guides/<client>.md` for **every supported client** (≥ Claude, Gemini, ChatGPT, Grok, Ollama, LM Studio, Cursor, VS Code, Windsurf, Codex) + a **single canonical "Start here — pick your AI" picker** (README/USER_GUIDE link *into* it). Required sections incl. **"How to point it at your files"** (copy-a-folder-path per OS; `~`/OneDrive/iCloud gotchas). **CI link-check: every client `mta setup` supports has a live guide**, and the picker lists only clients with one | L/Md | matrix is **client × OS** |
| WP-155 | **ChatGPT support + guide** | M/Md | ChatGPT = MCP via **Codex** (restate existing target) + **remote-MCP / custom-GPT Actions** against `mta serve --http` (ties WP-160); ships `docs/guides/chatgpt.md` |

### Theme G — Mobile: Android & iOS (staged, feasibility-first)
| WP | Item | E/R | Feasibility / gates |
|----|------|-----|---------------------|
| WP-160 | **Remote-MCP from phones** to a self-hosted `mta serve --http` | M/Hi | **TLS-mandatory** when bound non-loopback; QR encodes a **short-lived single-use pairing token** exchanged for a **per-device** bearer (so the QR artifact is worthless after pairing; supports rotation/revocation); **refuse to emit a remote QR for a cleartext `http://` endpoint**; `--allow-remote` requires **interactive double-confirm**; **never bind `0.0.0.0` implicitly**; default novice recipe = loopback + SSH/Tailscale tunnel or reverse-proxy, **not** raw port exposure; HTTP tool responses are byte-cap-identical to stdio (conformance test) [C3] |
| WP-161 | **Android on-device via Termux** | M/Hi | **HARD PREREQUISITE GATE:** WP-181a (numpy-free core) + WP-183 land AND `pip install memorised-them-all` (core, no extras) succeeds on stock **Termux aarch64 with zero compiler/`pkg` steps**, proven on a real device/CI, **before this WP starts**. One-liner installs the **pure-Python core only**; OCR/PDF/Office are `pkg install`-then-`pip install …[ocr]`, explicitly **not** in the one-liner (no Bionic wheels for pypdfium2/numpy/pillow) |
| WP-162 | **iOS = remote-MCP only** (WP-160) as the supported path | S/Md | a-Shell on-device documented **experimental, text/CSV/MD-only, no OCR/PDF/Office/subprocess**, only after WP-181; **excluded** from the time-to-first-memory gate |
| WP-163 | *(research, post-3.0, NOT on any release line)* native companion | — | **163a (lower risk):** thin Swift/Kotlin shell over the WP-160 HTTP API (no Python on device) — preferred. **163b (high risk):** BeeWare/Briefcase Python-on-device (painful for compiled deps) |

### Theme H — Frictionless installation + README/USER GUIDE overhaul (novice-first)
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-170 | **One-command install per surface**: pipx, Homebrew, `.mcpb` double-click, winget/Scoop/Choco, `install.sh`, Termux one-liner; enumerate the **no-terminal vs one-command** story **per client** and fill gaps (GUI installer where a client has no double-click path); README matrix labels each row | L/Md | channels obey [C4] |
| WP-171 | **README overhaul (novice-first)**: pick-your-AI → install → **first memory in 3 steps**, screenshots/GIFs, FAQ incl. the top pre-install failures (**no Python**, **SmartScreen block**, **"command not found: mta"/PATH**) | M/Md | |
| WP-172 | **USER_GUIDE.md** (separate deliverable) + the per-platform guides (with WP-154) | M/Md | |
| WP-173 | **Reduce prerequisites**: OCR/LibreOffice optional, slim core (Theme I), offline-first first-run | M/Md | |
| WP-174 | **Python-free / Python-bundled install** | L/Hi | the `.mcpb` and ≥1 desktop GUI installer per OS either **bundle a Python runtime** (PyInstaller/shiv/embeddable) or auto-install it via the platform PM **non-interactively**, so a non-technical user **never installs Python**. Until then, `pip install` is **not** the headline novice row |
| WP-175 | **Windows novice hardening** | M/Hi | **Authenticode-sign** the Windows installer/`.exe` (extends cosign/SBOM to a code-signing cert) to clear **SmartScreen**; screenshot-driven "Windows protected your PC → More info → Run anyway (why it's safe)"; verify PATH so `mta` resolves, fallback `py -m mta` |
| WP-176 | **Lifecycle: clean update & uninstall** | M/Md | ship **`mta uninstall`** that **reverses `mta setup`** (removes the server block from every client config it added, restoring the backups setup made), optionally removes `~/.memorised-them-all`, prints the one manual step (`pip/brew uninstall` / delete `.mcpb`); per-surface **update** story. Acceptance: after uninstall, no client config references the server |
| WP-177 | **Accessibility & localization of the novice surface** | M/Md | every screenshot/GIF has alt text + (GIFs) captions; guides pass heading-structure/screen-reader check; **Bengali (bn) translation of the Start-Here picker + 3-step quickstart**; `mta setup`/`doctor` strings localisable (en+bn first) — the headline differentiator is Bengali docs, so Bengali users are first-class |

### Theme I — Dependency reduction (unblocks mobile + easy installs)
Today's core (10 deps): `numpy, networkx, rapidfuzz, psutil, markitdown[…], pdfplumber, pillow, pytesseract,
pypdfium2, striprtf`. Goal: tiny pure-Python default, heavy stuff opt-in (per ADR-005 + **ADR-010**).
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-180 | **Add** extras `[ocr]`/`[pdf]`/`[office]`/`[all]` (v2.7 = **additive**; core still pulls them) + emit a **deprecation notice** from `mta doctor`/first-run; the actual **removal-from-core lands in v3.0** (ADR-010) | M/Md | extras hash-pinned + SBOM'd + CI-installed [C4] |
| WP-181a | **Code: de-numpy the core import graph** — guard `numpy` in `store.py`/`embed.py`/`resolve.py`; `embed` degrades to no-op (hash embedding has no semantic value), `save/load_vectors` skipped (recall already meta-only), resolve embedding-confirm pass skipped; **a digest still completes** (graph + bm25 written) with numpy uninstalled; CI lane imports & digests core-only | M/Md | must land before WP-181b; **`import mta` fails without numpy today** (`store.py:21`) |
| WP-181b | **Packaging: move numpy to `[hybrid]`** (ships with WP-131, v2.10/3.0) | S/Md | gated on WP-181a + ADR-010 |
| WP-182 | *(spike-only / Open Decisions — NOT in a committed release)* investigate stdlib community detection | S/Hi | **networkx is already pure-Python** (not on the mobile critical path); any reimpl **cannot byte-match** networkx's partition → it's an **output break that must ride v3.0**, not a silent dep-drop. Default value: low |
| WP-183 | Harden the **pure-Python `rapidfuzz` fallback** → core works with **zero compiled deps** | M/Md | enables Termux/iOS core |
| — | **KPI** (gate): `tests/test_dep_budget.py` parses `pyproject` `[project].dependencies`, asserts **count ≤ 5** and each is pure-Python (wheel tag `none-any` / pinned allowlist). Baseline recorded = 10 | — | exact integer, no "~" |

### Theme J — Bijoy & Unicode Bangla (deepen the differentiator)
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-190 | Corpus-driven Bijoy/SutonnyMJ map refinement (WP-87b) | M/Md | grow glyph coverage from real word-forms |
| WP-191 | **Context-gated** reorder-artifact repairs (NOT blanket `replace`) | M/Hi | the S30 panel rejected ম্ন→ু / েস্ন→্লে / ে্য→্য / ণরে→ণের on **orthographic-impossibility** grounds, not corpus stats. Gate = **dual corpus**: a clean-Bengali set that must show **zero** changes (any change = fail) **+** an adversarial set of *pipeline-manufactured* artifacts that must be fixed; **frozen counterexample invariant** (`normalize(নিম্ন/সর্বনিম্ন/প্রত্যেক/"করে স্নান"/চরণরে/প্রাণরে) == input`); repairs fire only when flanking context makes the valid reading impossible; net-fix ratio denominator must be 0 |
| WP-192 | Better Bijoy PDF text-layer recovery (line-wise `recover_mixed` thresholds; mixed EN+BN) — folds the "broken-font Bengali re-OCR" clause (removed from WP-112) | M/Md | |
| WP-193 | **Fix the live Boishakhi mis-route FIRST**, then map-keyed routing | M/Md | `"boishakhi"` is in `_BIJOY_FONTS` (bangla_legacy.py:332) so it's force-converted through the **wrong SutonnyMJ map** today, contradicting the line-325 comment that says it's skipped → **remove/gate it (correctness bug)**; routing is **map-keyed**; a font with no shipped map stays **byte-for-byte** (never coerced); each new encoding (Boishakhi, Bangla-Word) needs its **own oracle-tested map fixture** before its fonts are added |
| WP-194 | **Forward-conversion golden-vector regression** (Bijoy bytes → expected Unicode, frozen vectors) + **idempotence** (`convert(convert(x))==convert(x)`), NOT round-trip | S/Md | the Mukti map is **non-bijective** (many-to-one) so round-trip is ill-posed; **pin the oracle commit hash** in CI; the oracle is authoritative for **fidelity to Mukti**, NOT linguistic **correctness** (correctness questions route to WP-191's linguistic gates) |

### Theme K — Performance / stability / accuracy / efficiency (these are **acceptance gates**, not WPs)
Each attaches to the release whose WPs it measures (per [C6]); none is an independent deliverable.
| Gate | Measures | Type |
|------|----------|------|
| **Digest efficiency** | re-digest unchanged corpora — **gate** on the machine-independent proxy "second digest converts **0** changed files" (WP-140 cache-hit count); **benchmark** the ≥2× wall-clock on named hardware | gate + benchmark |
| **Recall latency** | "p95 < 150 ms @ 50k **recall-units**" is a **benchmark on named hardware**, **contingent on WP-201's inverted index** (today's linear cached scan is ~0.5–0.6 s @ 50k per R-13). CI **gate** = a machine-independent op-count proxy (postings ops ∝ query terms, not corpus size). Define "unit" = entity cards + theme summaries, and the corpus size that yields 50k | benchmark + proxy gate |
| **Accuracy** | recall@k ≥ committed floor on the EN+BN corpus (WP-202a), no regression; ratchet floor on green; run **with the byte-budget gate** so neither is gamed by dumping more text | gate |
| **Stability** | grep no raw `open(...,"w")` outside `_io` [C2] + crash-injection tests; zero torn-write paths | gate |
| **Efficiency** | peak RSS via `psutil` at `--scale`, recorded per cycle (benchmark; runner-variance makes a hard RSS gate non-blocking) | benchmark |

*(WP-201 = build the term→postings **inverted index** at digest time, parity-tested byte-identical to the linear scorer; this is the deliverable behind the latency benchmark. WP-200/203/204 are the gates above, not separate WPs.)*

### Theme Z — 🚀 v3.0.0 marquee: Graph schema v2
Per **[C5]**. Typed & directional relations (WP-120) · temporal & numeric facts (PII-safe) · fact confidence +
salience (WP-123) · entity sub-types (WP-121) · provenance codepoint-offset spans (WP-123 produce / WP-134 cite) ·
community-algorithm pinning ([C1]) · default-dependency slim-down (WP-181b, ADR-010) · recall/render rewritten to
exploit them — still token-free, still per-payload byte-capped. **Export-format v1→v2 deprecation:** ship
`docs/export-format/v2/` (new fields optional); `mta export` emits v2 by default but supports **`--format v1`**
(down-projecting) **through v3.1**, warning thereafter, removed **no earlier than v3.2**; v1 `graph.schema.json` stays
published; the bundle carries a `format_version` header; v2 schema CI-enforces confidence ∈ [0,1], salience numeric,
relation direction/type from a closed enum, offsets non-negative & bounded by doc length, plus the existing
edge→node referential-integrity check.

---

## Release train

| Release | Marquee | Headline WPs (L-items capped ≤3) |
|--------|---------|----------------------------------|
| **v2.7.0** | Slim core (additive) + easy install + cross-AI breadth | WP-180 (additive extras + deprecation notice), WP-181a, WP-183, WP-170, WP-173, WP-174, WP-175, WP-176, WP-100/101/102, WP-103/104, **WP-202a (eval corpus + CI wiring + baseline)** |
| **v2.7.x / v2.8.0** | Cross-AI guides + conversion accuracy | WP-150/151/152/153, WP-154, WP-155 (ChatGPT), WP-171/172, WP-177; WP-110, WP-111a/111b, WP-112a, WP-113, WP-132, WP-140; WP-130 |
| **v2.8.x** | Mobile | WP-160, WP-161 (gated), WP-162, WP-141, WP-142, WP-144 |
| **v2.9.0** | Bengali + graph quality + frugality | WP-190/191/192/193/194, WP-121/122/124/125, WP-133, WP-201 (inverted index) |
| **v2.10.0** | Opt-in power features (isolated invariant-risk) | ⚠️ WP-131 (hybrid), ⚠️ WP-143 (encryption), WP-126 (HTML viewer) |
| **v3.0.0** | Graph schema v2 (Theme Z) | WP-120, WP-123, WP-134, WP-181b (default slim-down), community pinning, recall/render v2, migration [C5] |

*(The arc is gated on schema v2, not on a version number — extra minors v2.7.x/v2.8.x/v2.10 are legitimate so no
single release is overloaded.)*

## Global acceptance gates (measurable per [C6])
- All invariants preserved; **cross-env determinism** asserted in the clean-image lane [C1]; **no-egress** test green [C3].
- **Eval harness wired into CI** (WP-202a) before any accuracy/frugality gate is cited; EN+BN + conversion corpora committed; v2.6.2 baseline frozen.
- **Token frugality**: `MTA_RECALL_BUDGET` total-payload cap enforced + median recall/overview ≤ the budget on the golden set (number reconciled with caps).
- **Dep budget**: core deps ≤ **5**, all pure-Python (`test_dep_budget.py`).
- **Conversion**: success ≥ committed baseline + golden-diff fidelity ≥ floor on the conversion fixture set (PDF columns = best-effort, non-gating).
- **Accuracy**: recall@k ≥ floor on EN+BN, ratcheting, run jointly with the byte-budget gate.
- **Migration** [C5]: frozen v1→v2 fixture migrates losslessly-forward, validates against v2 schema, recall-parity; idempotent; atomic.
- **Manual acceptance (not CI)**: time-to-first-memory measured on a **fresh OS account, no Python, only the download link**, per (OS × no-terminal/one-command), recorded in `ACCEPTANCE.md`; CI-able proxy = **install ≤ 2 actions/surface** (scripted command count). Termux gated on WP-161 prereq; on-device iOS excluded.

## Explicitly out of scope / won't-do
- ❌ Any LLM/embedding/summarizer in the **default** path (breaks model-free + determinism). An `ask`/`summarize`
  tool stays the host model's job; we only return citable slices.
- ❌ Always-on network, telemetry, or returning document contents to the model.
- ❌ Mandatory heavy/compiled deps. `_rearrange` linearization (perf-only, fidelity risk) and full LIFE-02
  refcounting (narrow, mitigated) stay deferred.
- ❌ Blanket cross-script normalization or blanket Bijoy reorder `replace` (per the Bengali safety gates).

## Open decisions for the owner
- **ADR-008** encryption-at-rest stays opt-in by default.
- **ADR-010 (NEW — proposed):** *dependency-extra changes follow deprecate-then-remove; removing a default-on
  capability forces a major or a flagged one-minor deprecation window.* (Add to `DECISIONS.md`.)
- **Community-algorithm pinning** ([C1]): pin NetworkX Louvain as the deterministic default (Leiden opt-in). Confirm.
- **WP-182** (stdlib community detection): spike-only; pursue only if it rides the v3 output break — else keep networkx.
- **WP-163** native mobile app: research only (prefer 163a thin shell); confirm before committing engineering.
- **WP-131** hybrid retrieval: pure-BM25 stays the shipping default; embeddings opt-in, safetensors-only, hash-pinned.

---

## Adversarial review log
- **Round 1 (S26)** — 10 expert lenses attacked every WP. Findings: ~5 Critical, ~14 High, ~20 Med/Low. **All
  Critical/High folded into this revision** (community-detection determinism gap [C1]; schema-v2 migration unbound →
  [C5]; eval corpus/CI-wiring nonexistent → [C6]/WP-202a; latency gate contradicted by R-13 → reframed benchmark;
  1.5 KB↔caps inconsistency → WP-133; WP-180/181 breaking-in-a-minor → ADR-010 + WP-181a/b split; ChatGPT/Grok absent →
  WP-155 + Theme F restated; novice Python-install/uninstall/SmartScreen gaps → WP-174/175/176/177; security on
  QR/encryption/embeddings/viewer/channels → [C3]/[C4] + WP clauses; scope overload → v2.10 split + Effort/Risk tags;
  Bengali blanket-rule & Boishakhi mis-route → WP-191/193 gates; WP-182 reframed spike-only; WP-201 latency = inverted
  index). **Next: Round 2** — fresh lenses re-attack this revision; converge when a round yields no new Critical/High.
