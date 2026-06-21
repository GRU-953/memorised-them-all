# ROADMAP_V3.md — the road to v3.0.0

**Status:** planning artifact (S26), **hardened through 3 rounds of a multi-lens adversarial review + a Round-4 edit
pass** (R1: 10 lenses → ~5 Critical; R2: 7 lenses → 4 Critical; R3: 6 lenses → **0 Critical**, all-resolved per the
convergence auditor). Source of truth for the v2.7 → v3.0.0 arc. Mints WPs into `PROGRESS.md`; nothing is built until a WP is taken on a `wp-<id>-<slug>` branch → PR into
`develop`. Baseline: **v2.6.2 SHIPPED** on all channels (PyPI · GitHub Release · `.mcpb` · Homebrew · GHCR multi-arch),
cross-AI `mta setup`, 8 MCP tools, 100% local / token-free / deterministic / model-free.

---

## Load-bearing invariants
Token-free (tiny **per-payload-capped** results; document contents never returned to the model) · 100% local / no
telemetry · deterministic byte-identical output · **model-free by default** · dependency-free classical/offline
fallback · atomic crash-safe writes. **Anything that risks one is opt-in with a graceful fallback** — flagged ⚠️.

## Cross-cutting engineering contracts ([C1]…[C6]) — every WP must honor; cite the ones it touches
Added/expanded because review found WPs that *assumed* an invariant without binding it.

- **[C1] Determinism contract.** "Byte-identical" = a **fresh** digest yields identical `graph.json`/`bm25_index.json`/
  `memory.md` across runs, OSes, and `PYTHONHASHSEED`. The existing gate (`test_v2_invariants.py`) only proves
  **same-machine run-to-run** stability — it does **not** cover environment axes. **Known live gaps that v3.0 closes
  (interim accepted, RISKS R-20):** the partition depends on which *optional* packages are installed —
  **(i) community algo** (`community_algo="auto"` → Leiden if `leidenalg`+`igraph` else NetworkX Louvain else greedy);
  **(ii) numpy** (the `resolve.py` embedding-confirm pass fires merges at ratio≥60 that the fuzzy≥88 pass would not, so
  numpy-absent changes the entity partition); **(iii) rapidfuzz** (absent → exact-match-only resolution). The CI
  determinism assertion (in the WP-103 clean-image lane) digests a fixture across a **matrix** of
  {leidenalg, igraph-only, numpy, rapidfuzz} presence × two `PYTHONHASHSEED` values × OS, asserting byte-identical
  `graph.json`+`bm25_index.json`+`memory.md`. To make that pass: **WP-181a** reimplements the embedding-confirm dot
  product in **pure Python** (it is md5-bucketed, trivially numpy-free) so numpy-present == numpy-absent **byte-for-byte**;
  **WP-122/Theme Z** pins NetworkX Louvain (fixed seed **+ canonical node ordering**, and `_from_sets` numbers
  communities by `min(sorted(member_ids))`) as the single deterministic default, with Leiden opt-in
  (`MTA_COMMUNITY_ALGO=leiden`) and the **also-seeded/removed greedy fallback** both **excluded** from the gate;
  **WP-183** must prove its pure-Python rapidfuzz fallback byte-identical to rapidfuzz on the gate corpus (else
  rapidfuzz stays a hard dep). `vectors.*` is **carved out** of the byte-identity gate (it exists only in numpy builds).
  OCR (WP-112a), PDF reading-order (WP-111b), and hybrid embeddings (WP-131) are float/heuristic and likewise carved
  out; a store stamps `stats.mode` so augmented/limited builds are distinguishable.
- **[C2] Atomic-write contract.** One shared crash-safe writer (`newline=""` + fsync + `os.replace`). WP-100 promotes
  `_atomic_write_text` from `store.py` into a shared `mta/core/_io.py` so `convert.py` (`convert.py:548` is a raw
  `write_text` today — R-19) and `store.py` use **one** writer. CI: a meta-test greps `mta/` for raw `open(...,"w")`/
  `write_text` outside the helper; crash-injection tests assert prior content survives.
- **[C3] No-egress contract.** Digest, recall, the WP-126 viewer, and every **default** install path make **zero**
  outbound calls except the documented, disableable update check (`MTA_AUTO_UPDATE=off`). The only *new* permitted
  egress is the WP-131 embedding-model download — one-time, consented, hash-verified, off the digest/recall hot path.
  A CI no-egress test enforces this.
- **[C4] Supply-chain contract.** Every dependency **extra** and install channel is **hash-pinned to the signed
  release**, in the CycloneDX SBOM, installed in the CI matrix to keep pins live, and reported by `mta doctor`. New OS
  package-manager manifests (winget/Scoop/Choco) are **auto-bumped from the canonical signed artifacts** (like the
  Homebrew tap, ADR-006), never hand-edited, with a post-publish reinstall+cosign-verify smoke. Embedding models
  (WP-131) are **safetensors-only (no pickle)**, content-hash-pinned, TLS-fetched from a declared SBOM-recorded source.
- **[C5] Migration contract** (binds Theme Z). **This machinery does not exist yet — it is NEW code, not a wiring
  tweak.** Today `load_graph` migrates **in memory only** (no disk write; disk is rewritten at the next digest),
  `_MIGRATIONS={}`, `_backup_store` is **best-effort and its return is ignored**, and `digest.py` hardcodes
  `"version": 1`. v3.0 must add: (a) **physical in-place migration runs only under the exclusive write lock, via an
  explicit `mta migrate` command** — **NOT** `digest` (digest rebuilds the graph from the `markdown/` corpus and writes
  a **fresh** v2 store that *supersedes* any v1 `graph.json`; it is not a migration and is never tagged
  `mode=migrated-v1`). **Read paths (`recall`/`overview`, shared lock) migrate in-memory only and never write** (closing
  the shared-lock race). (b) **Atomic multi-file commit**:
  write a `.migrating` sentinel first; stage `graph.json`+`vectors.*`+`bm25_index.json`; swap; clear the sentinel last.
  `load_graph` checks the sentinel — its own incomplete write → roll back to the pre-migrate backup; a **newer** build's
  sentinel → decline-to-overwrite + back up (R6). (c) **Backup-before-write that ABORTS on failure** for the
  pre-migrate/downgrade cases (`save_graph`/migrator must check `_backup_store`'s return and raise if `None`) —
  best-effort is allowed only for the already-corrupt case. (d) **Schema-version single-source:** `digest.py` stamps
  `version = store.SCHEMA_VERSION`; a lint fails CI on a literal graph-schema `"version": N` in producers (the
  **independent bm25-index `version`** is carved out, and a schema bump **invalidates/rewrites** a stale bm25 index so
  recall is never ranked off a mismatched cache); a CI check asserts `_MIGRATIONS` is a contiguous `1→2→…→
  SCHEMA_VERSION` chain. (e) **Lossy-forward & not-fresh-equal:** v1 stores lack v2 source context (typed relations,
  char-offsets, salience) → migration up-casts existing fields only (confidence defaulted, offsets `null`, relations
  untyped) and is documented "**re-digest to populate v2-native fields**"; `memory_overview` shows a "migrated" flag and
  the store stamps `mode=migrated-v1`. **Migrated ≠ fresh:** a migrated store is **excluded** from any fresh-digest
  byte-identity comparison; the migration **recall-parity** gate compares the migrated store to the **pre-migration v1
  store's own recall** (same hit identities/order up to v1-derivable fields), **never** to a fresh v2 digest. Each
  `_MIGRATIONS` step ships a **frozen real v1→v2 fixture test** + an **idempotence** test; the monkeypatched
  `test_migration.py` step is insufficient. Crash-injection tests (kill after sentinel / mid-swap) assert v1 survives.
- **[C6] Measurement contract.** A KPI is either a **CI gate** (machine-independent, stable, fail-closed) or a
  **benchmark** (named hardware, non-blocking) — never a wall-clock CI gate. **Correction (Round 2):** the EN recall@k
  floor (0.75) **is already CI-gated today** via `tests/test_eval.py` (run by `pytest tests/`). So **WP-202a's real job
  is narrower:** commit the missing **Bengali corpus** (`eval/corpus` is 4 English files / 0 Bengali — incl. Unicode +
  Bijoy-legacy tied to WP-194), the **conversion-fidelity fixture set** (PDF/DOCX/XLSX/HTML/image + golden Markdown),
  and `eval/baseline.json` with frozen v2.6.2 numbers, then split the **BN-accuracy and conversion-fidelity** assertions
  into their own fail-closed gates. Only those two are "not yet CI-enforced"; do not over-claim the rest.

## What makes 3.0.0 a *major* (each is a break no minor may hide — ADR-010)
1. **Graph schema v2** (typed/temporal/confident facts, salience, provenance offsets, sub-types) — auto-migrated [C5].
2. **Community-algorithm pinning** ([C1]) — changes existing `graph.json` partitions; regenerates byte-identically on
   re-digest under the major. (The *quality* label work, WP-122, is non-breaking and lands in v2.9; the **default-algo
   pin itself** lands here.)
3. **Default-dependency slim-down** (WP-181b: OCR/PDF/Office/numpy leave the *default* install — ADR-010). v2.7 only
   *adds* extras + `[all]` + a deprecation notice (genuinely additive); removal-from-core is here.

## Effort / Risk legend  — **Effort {S,M,L}**, **Risk {Lo,Md,Hi}** (Risk = invariant-jeopardy + uncertainty). **≤ 3 L-items per minor.**

---

## Themes & Work Packages

### Theme A — Quality & hardening
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-100 | Atomic `.md` write (close **R-19**) via shared `_io.py` [C2] | S/Lo | |
| WP-101 | Per-script Brahmic normalization (close **R-16**) — folded into WP-121 (NOT a blanket rule) | S/Md | |
| WP-102 | Length-aware fuzzy threshold (mitigate **R-17**) | S/Lo | |
| WP-103 | CI/coverage truthing: coverage %, **Py 3.13** (3.14 when wheels land, R-06), arm64 smoke, **Docker clean-image matrix (R-01)** running the **[C1] cross-env determinism matrix** | M/Md | matrix changes **additive only**; version *drop* → major |
| WP-104 | Reproducible lockfile **with hashes** (CI-09); extras hash-pinned [C4] | S/Lo | |
| WP-105 | Test depth: [C1] determinism matrix, recall/low-confidence sensitivity, **property tests** for the per-payload byte-cap (token-free invariant / WP-133) & atomic writes [C2], large/degenerate-graph fuzzing | **M/Md** | **→ v2.7.0** |

### Theme B — Conversion: files → Markdown (stability · accuracy · performance · efficiency)
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-110 | **Stability**: per-file isolation, adaptive timeouts, partial-result salvage, never-abort-batch, malformed/huge-file fuzzing | M/Lo | |
| WP-111a | **Tractable fidelity**: CSV/XLSX → clean Markdown tables (**owns the table data model**), HTML/EPUB strip, list/structure, image alt/caption | M/Md | golden-diff on the conversion fixtures |
| WP-111b | **Best-effort PDF** reading-order/column/heading (wire the declared-but-unused `pdfplumber`) | L/Md | pdfplumber/pdfminer **hash-pinned [C4]**, **fixed extractor precedence** MarkItDown→pdfplumber→OCR (byte-identical per pinned toolchain), output **carved out of [C1]** only if the version can vary; PDF-column cases **non-gating** |
| WP-112a | **OCR engine quality**: DPI/deskew/preprocessing; default `-l eng+ben` multi-lang (**autodetect advisory only**, never single-pass exclusive); **confidence floor** drops garbage | M/Md | OCR **opt-in**, carved out of [C1]; **→ v2.8 beside WP-111a** |
| WP-113 | **Performance/efficiency**: consume **WP-140's** manifest to skip unchanged conversions; streaming; bounded RAM. **Cache key = content-hash ⊕ converter-fingerprint** (mta+MarkItDown+OCR/LibreOffice version + bangla-map revision + cfg) → a hit is byte-identical to a fresh convert; miss/garbage → re-convert | M/Md | depends on WP-140 |
| WP-114 | Format coverage — **merged into WP-180** (granular extras); tracked there | — | (was dangling; folded) |

### Theme C — Data mapping & graphing
**Scope note (directive #10):** "data mapping" = the WP-111a **table model surfaced through recall** + WP-125
**CSV/GraphML/GEXF exports** + **numeric-fact recall** (WP-130 type filter) + the new **WP-127 table/numeric recall
view**. Spreadsheet **aggregation/charting is explicitly OUT of scope** — routed to the host model / exports (keeps
model-free + token-free).
| WP | Item | E/R | Target | Notes |
|----|------|-----|--------|-------|
| WP-120 | **Rule-based** verb-mediated **typed relations**, model-free | L/Hi | 3.0 | **English-only** (no Bengali verb analysis); stored as **edge attributes (`type`,`direction`) on the existing UNDIRECTED backbone** — community detection still runs on the undirected projection (canonical ordering [C1]) so partitions/recall order are unchanged when only labels are added; **fallback `co_occurs`** when no pattern matches; **precision gate = CI comparison** (typed ON vs OFF: recall@k (WP-202a) + community count ≥ co-occurrence baseline). **`direction` is a determinism axis [C1]:** an undirected edge serializes endpoints in insertion order, so `direction` MUST be stored relative to the **canonical `sorted((u,v))`** orientation (not the serialized order) and the serialized `source`/`target` canonicalized — added to the determinism gate |
| WP-121 | **Entity resolution & typing**: **per-script `_SCRIPT_BLOCKS` table** fixing **both** `_norm`'s combining-mark filter (today whitelists only U+0980–U+09FF → every other Brahmic matra is stripped → skeleton over-merge) **and** `_NORM_RE`; **never reuse `_rearrange` (Bijoy-specific)** | L/Hi | **resolution/normalization → 2.9; entity sub-types (schema) → 3.0** | per-script opt-in gated on **4 proofs**: (1) `_norm` preserves that script's marks, (2) **no-skeleton test** (distinct words don't normalize equal), (3) **minimal-pair over-merge gate** (काली≠कुल, கடல்≠கடா), (4) `_block_keys` prefix/suffix-edit parity re-proven on a real corpus for that script; until all 4 pass, the script stays byte-for-byte unhandled (safe over-split); generalization may only **reduce** merges |
| WP-122 | **Community quality** (v2.9, non-breaking): multi-entity + TF-IDF labels, optional hierarchical communities, determinism **property tests within fixed env**. The **default-algo pin itself is a v3.0 break** (see "major" #2 + [C1]) | M/Md | 2.9 (quality) / **3.0 (pin)** | |
| WP-123 | **Fact salience + confidence** (close **R-1**, *produces* values) + **provenance codepoint-offset spans** (over the digest-time `.md`, stored with the converter-fingerprint, stale-marked) [C5][C1] | L/Md | 3.0 | pairs with WP-134 (consumer) |
| WP-124 | Graph hygiene & metrics: dedup/junk filtering, centrality + theme-size in `memory_overview` | M/Lo | 2.9 | |
| WP-125 | **Exports**: GraphML/GEXF/CSV (deterministic) | S/Lo | 2.9 | |
| WP-126 | **Opt-in zero-network static HTML viewer** [C3]: **single self-contained `.html` with the partition data inlined** as an escaped `<script type="application/json">` island (no runtime `fetch` → `default-src 'none'` holds & `file://` works); **CSP `default-src 'none'`**; **all fields that reach the DOM HTML-escaped** (labels/aliases/themes **and** any WP-134 snippet/doc ref) — XSS test asserts a payload is inert; **doc refs = basenames only** (CI asserts zero absolute paths); no wall-clock → deterministic; CI asserts **zero off-origin URLs** | L/Md | 2.10 | consumes the canonical partition (WP-122) |
| WP-127 | **Table / numeric-fact recall view** (directive #10 "data mapping"): recall a digested table's cells + numeric facts as a small cited slice (token-free) | M/Md | 2.9 | aggregation stays host-model's job |

### Theme D — Retrieval (IR) quality & token frugality
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-130 | Recall query filters (by document / entity type / theme) | S/Lo | additive args |
| WP-131 | ⚠️ **Opt-in hybrid retrieval** | L/Hi | default pure-BM25; `[hybrid]` **never auto-downloads** (model user-provided/pre-pulled, else error → BM25 fallback) [C3]; model **safetensors-only, hash-pinned** [C4]; hybrid scores **only re-rank**, never bypass the off-topic gate; **excluded from byte-identity** [C1] |
| WP-132 | Layout/table-aware **chunk-boundary** logic — consumes WP-111a's table model; **never re-segments a table mid-row** (owns boundaries only) | M/Md | co-located with WP-111a (v2.8) |
| WP-133 | **Token frugality**: **`MTA_RECALL_BUDGET` default = 16384 bytes** (hard total-payload UTF-8 cap at the tool boundary; covers `k=8` worst-case ≈14 KB at current per-field caps), applied **deterministically** — cap each field, then drop **whole trailing hits in fixed rank order** until under budget (never resize a field by neighbours/k); deduped/compressed synopsis | M/Md | **instrument:** CI asserts `len(json.dumps(recall).encode()) ≤ MTA_RECALL_BUDGET` for every golden query **and median ≤ 4096**; per-field caps unchanged |
| WP-134 | **Provenance pointers over text** (schema v2): cite by `doc + codepoint-offset` (consumes WP-123 spans); pointer-only stays token-free [C5] | M/Md | 3.0 |

### Theme E — Lifecycle & large-corpus UX
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-140 | Incremental / `mta watch` mode — **owns the single content-hash manifest**; WP-113 consumes it | M/Md | watch opt-in |
| WP-141 | Snapshot / rollback — each snapshot records `schema_version`; **restore routes through `load_graph`/`migrate_doc`**, refuses-with-backup if newer [C5] | M/Md | document relationship to `_backup_store` |
| WP-142 | `forget --secure` — **best-effort only** (overwrite can't erase on SSD/flash/CoW/synced/snapshotted; real guarantee = crypto-erase via WP-143); targets **all of `state/`** incl. `http_token` **and the WP-160 per-device store**, `_unpacked/`, snapshots | S/Md | tie to WP-143 |
| WP-143 | ⚠️ **Encryption-at-rest** (ADR-008) — threat model: **stolen/cloud-synced `MTA_HOME` at rest; NOT a running process/memory/swap**; encrypts the **whole content corpus** (`markdown/`,`memory/`,`graph.json`,`vectors.*`) **+ `state/` secrets** (else documented gap); KDF argon2id/scrypt (stated params); passphrase never persisted; **wraps before the atomic temp**; migration/backup need the passphrase (else **decline**, not corrupt→backup); determinism on **plaintext**. **Recall × encryption:** the automated hot path needs a non-interactive **key source** — `MTA_PASSPHRASE` env or an OS keychain held for the **server-process lifetime**; "never persisted" = **never written to disk** (may live in process memory/keychain for the session); the `.mcpb`/no-terminal path documents "encryption requires a key source" | L/Hi | v2.10 |
| WP-144 | Multi-project recall / federation | M/Lo | additive |

### Theme F — Cross-AI breadth + novice how-to guides
**Currently supported (v2.6.x), each gets a WP-154 guide:** Claude (Desktop/Code), **Gemini**, **Grok** (auto-discover),
Cursor, VS Code, Windsurf, **Codex**.
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-150 | Add **Ollama & LM Studio** to `mta setup` | M/Lo | both speak MCP |
| WP-151 | Next tier: Jan, Cherry Studio, AnythingLLM, Continue, Zed, Msty + generic `--client <name>` | M/Lo | |
| WP-152 | `mta setup` one-click: **detect → configure → verify (round-trip a tool call) → "✅ working"**; on verify-fail **auto-print WP-153 doctor** | M/Md | |
| WP-153 | `mta doctor`: plain-English diagnosis + **failure-symptom catalogue keyed on what the user sees** (works pre-`mta`; `.mcpb` no-terminal user routed to `memory_status` in-AI); detect **installed-but-not-on-PATH** + print the one-line fix | M/Md | |
| WP-154 | **Per-platform guides** `docs/guides/<client>.md` for **every supported client** + a single canonical **"Start here" picker** that is **detection-first** (`mta setup` auto-scans & reports), has an **"I have no AI app yet → install one"** branch, and a **"browser ChatGPT/Gemini won't work — use X"** disambiguation; required section **"How to point it at your files"** (copy-a-path per OS; `~`/OneDrive/iCloud). **CI link-check: every supported client has a live guide** | L/Md | client × OS |
| WP-155 | **ChatGPT support + guide** = Codex-MCP (restate) + **remote-MCP/custom-GPT Actions** against `mta serve --http` (ties WP-160); ships `docs/guides/chatgpt.md` | M/Md | |

### Theme G — Mobile: Android & iOS (staged, feasibility-first)
| WP | Item | E/R | Feasibility / gates |
|----|------|-----|---------------------|
| WP-160 | **Remote-MCP from phones** to a self-hosted `mta serve --http` | L/Hi | **NEW server state required** (today `transport.py` ships **one shared `state/http_token`**): add a **per-device token store** (`state/http_devices.json`, 0600, bearer+label+issued-at) + `mta serve --revoke <device>`/`mta devices`; BearerAuth checks membership. QR carries a **≥128-bit (`token_urlsafe(32)`) short-lived (≤120 s) single-use pairing token** redeemed once at `/pair` (atomic compare-and-set under the store lock → no TOCTOU double-redeem) for a fresh per-device bearer — the QR holds **no reusable secret**; `/pair` is the only unauthenticated mutating endpoint, so it has a **per-window attempt cap / lockout**. **Revocation is live:** BearerAuth re-reads the on-disk device store **per request** so `--revoke` takes effect immediately (not restart-only). **TLS enforcement is explicit (the server can't detect a proxy):** a non-loopback bind is **refused** unless either native `--tls-cert/--tls-key` are provided **or** an explicit `--behind-tls-proxy` attestation flag is set (trust-on-assertion, documented); **refuse a remote QR for a cleartext `http://` endpoint**; **`--allow-remote` requires a real `y/N` tty confirm AND `--i-understand-remote-exposure`** (today `MTA_HTTP_ALLOW_REMOTE=on` enables it silently — close that, incl. the env path); **never bind `0.0.0.0` implicitly**; default novice recipe = loopback + SSH/Tailscale tunnel. HTTP tool responses byte-cap-identical to stdio (conformance test) [C3] |
| WP-161 | **Android on-device via Termux** | M/Hi | **HARD PREREQ GATE (before WP starts):** WP-181a (numpy-free core, **byte-identical** per [C1]) + WP-183 land AND `pip install memorised-them-all` (core, no extras) succeeds on **stock Termux aarch64, zero compiler/`pkg` steps**, proven on real device/CI. One-liner = **pure-Python core only**; OCR/PDF/Office = `pkg install`+`pip install …[ocr]`, explicitly not in the one-liner |
| WP-162 | **iOS = remote-MCP only** (WP-160) | S/Md | a-Shell on-device documented **experimental, text/CSV/MD-only, no OCR/PDF/Office/subprocess**, only after WP-181a; **excluded** from the time-to-first-memory gate |
| WP-163 | *(research, post-3.0, NOT on any release line)* | — | **163a** thin Swift/Kotlin shell over the WP-160 HTTP API (no Python on device) — preferred; **163b** BeeWare/Briefcase on-device (high risk) |

### Theme H — Frictionless installation + README/USER GUIDE overhaul (novice-first)
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-170 | **One-command install per surface** (pipx, Homebrew, `.mcpb` double-click, winget/Scoop/Choco, `install.sh`, Termux); enumerate **no-terminal vs one-command per client**; **every console-script surface verifies `mta` is invocable post-install** (PATH probe + exact fallback `export PATH=…`/`py -m mta`) | L/Md | channels obey [C4] |
| WP-171 | **README overhaul (novice-first)**: pick-your-AI → install → **first memory in 3 steps**, screenshots/GIFs, FAQ incl. **no Python**, **SmartScreen/Gatekeeper block**, **"command not found: mta"/PATH** | M/Md | |
| WP-172 | **USER_GUIDE.md** (separate) + per-platform guides (with WP-154) | M/Md | |
| WP-173 | **Reduce prerequisites**: OCR/LibreOffice optional, slim core (Theme I), offline-first first-run | M/Md | |
| WP-174 | **Python-free / Python-bundled install** | L/Hi | `.mcpb` + ≥1 desktop GUI installer per OS **bundle a Python runtime** (PyInstaller/shiv/embeddable) or auto-install it non-interactively → user **never installs Python**. **Bundled-runtime invariant:** when frozen (`sys.frozen`), every `mta setup` config block is **`[sys.executable, "serve"]`** — **not** `-m mta.server` (a one-file freeze has no `-m` module-run) and **never** a bare `python`/`mta`; the frozen branch **short-circuits `which("mta")`** in `_mta_command()` (so a system-installed `mta` can't shadow the bundle). CI conformance test launches an emitted config with **no system Python present** and asserts the block contains **no `-m` and no bare `mta`/`python`**; WP-176 uninstall removes that same block |
| WP-175 | **Desktop install hardening (Windows + macOS)** | M/Hi | **Windows:** Authenticode-sign the installer/`.exe` to clear **SmartScreen**; PATH verified; fallback `py -m mta`. **macOS:** **notarize** the GUI installer/`.app`/`.pkg` (Developer ID + `notarytool` + **staple**, hardened runtime), extending cosign/SBOM [C4] to an Apple Developer ID; screenshot-driven Gatekeeper recovery; Homebrew formula is notarization-exempt but the `.dmg`/GUI path is not |
| WP-176 | **Lifecycle: clean update & uninstall** | M/Md | **`mta uninstall`** reverses `mta setup` (removes the server block from every client config it wrote, restoring backups), optionally removes `~/.memorised-them-all`, prints the one manual step; per-surface update story. Acceptance: after uninstall, no client config references the server |
| WP-177 | **Accessibility & localization** | M/Md | screenshots/GIFs carry alt text + captions; guides pass heading/screen-reader check; **Bengali (bn) translation of the picker + 3-step quickstart**; localize (en+bn) the **user-facing failure/empty-state strings a novice hits first** (digest "no files found", recall "no memory yet", `.mcpb` `memory_status` guidance) — **tool payloads stay structured/locale-neutral** (no token regression) |

### Theme I — Dependency reduction (unblocks mobile + easy installs)
Today's core (**11 deps** per `pyproject` `[project].dependencies`): `mcp, numpy, networkx, rapidfuzz, psutil,
markitdown[…], pdfplumber, pillow, pytesseract, pypdfium2, striprtf`. Goal per ADR-005 + **ADR-010**: tiny default,
heavy stuff opt-in. **`mcp` is the required MCP transport — exempt from the "pure-Python" rule, but counts toward the
budget.**
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-180 | **Add** extras `[ocr]`/`[pdf]`/`[office]`/`[all]` (v2.7 = **additive**; core still pulls them) + **deprecation notice** from `mta doctor`/first-run; removal-from-core is **v3.0** (ADR-010). Folds old WP-114. | M/Md | extras hash-pinned+SBOM'd+CI-installed [C4] |
| WP-181a | **Code: de-numpy the core, merge-decision-identical** [C1] — reimplement the `resolve.py` embedding-confirm in **pure Python** (md5-bucketed) so the **merge *decision*** (ratio≥60 **+** cosine≥0.92 boolean) is reproduced exactly → the resulting partition is **byte-identical**; the dot-product float itself is **not** persisted/compared (`vectors.*` carved out) — confirmed safe in practice (achievable cosines near 0.92 are spaced ~1e-3 apart ≫ ~1e-7 float error, so the boundary isn't straddled on a fixed corpus). **Split the meta sidecar (`vectors.json`) write OUT of `save_vectors`** into a numpy-free writer the digest **always** calls, and **repoint recall off the `.npz` existence gate** (today `load_meta`/`load_vectors` gate on `vectors_path.exists()` AND `store.py:21 import numpy` is **module-level** → numpy-absent is an **ImportError on `import store`**, not a graceful `no_memory`; guard it). **Acceptance: gate the with/without-numpy partition against the frozen v2.6.2 baseline** (`eval/baseline.json`, WP-202a), not merely numpy-present==absent; **else numpy stays a hard core dep** (same hedge as WP-183) and the change rides v3.0 | **M/Md** | **v2.7**; precedes WP-181b; additive only because merge-decision-identical |
| WP-181b | **Packaging: move numpy to `[hybrid]`** — numpy **leaves the default install in v3.0** (ADR-010); the `[hybrid]` extra ships earlier with WP-131 (v2.10) [C4] | S/Md | **v3.0** |
| WP-182 | *(spike-only / Open Decisions — NOT in a committed release)* stdlib community detection | S/Hi | networkx is **already pure-Python** (not on the mobile path); any reimpl **can't byte-match** networkx → output break that must ride v3.0. Default value: low |
| WP-183 | Harden the **pure-Python `rapidfuzz` fallback**, **proven byte-identical to rapidfuzz on the gate corpus** [C1] (else rapidfuzz stays a hard dep) → core with **zero compiled deps** | M/Md | enables Termux/iOS core |
| — | **KPI (gate):** `tests/test_dep_budget.py` parses `[project].dependencies`; asserts **≤ 6 total (≤ 5 excluding `mcp`)**, each pure-Python **except an explicit allowlist `{mcp, psutil}`** (`psutil` is compiled C but a **soft/optional import** via `platform.py`, so it never blocks a pure-Python core install). Baseline recorded = **11**; v3.0 survivors = `{mcp, networkx, rapidfuzz, psutil, striprtf}` = 5 | — | exact integers |

### Theme J — Bijoy & Unicode Bangla
| WP | Item | E/R | Notes |
|----|------|-----|-------|
| WP-190 | Corpus-driven Bijoy/SutonnyMJ map refinement (WP-87b) | M/Md | |
| WP-191 | **NEW context-gated reorder rules only** | M/Hi | The four **S30-rejected** rules (`ম্ন→ু`,`েস্ন→্লে`,`ে্য→্য`,`ণরে→ণের`) **stay rejected** — their LHS are substrings of valid words (নিম্ন/করে স্নান/প্রত্যেক/চরণরে) so **no local context** distinguishes them (needs a dictionary, out of scope) and they can never pass the zero-change clean gate. Scope = NEW orthographically-impossible artifacts (like shipped `রম্ন→রু`); gate = **dual corpus** (clean-Bengali **zero-change** + pipeline-**manufactured** artifacts fixed) + **frozen counterexample invariant** + net-fix-ratio denominator 0 |
| WP-192 | Better Bijoy PDF recovery (line-wise `recover_mixed`; mixed EN+BN) — folds the broken-font re-OCR clause (removed from WP-112a) | M/Md | |
| WP-193-fix | **(S, do first)** remove `"boishakhi"` from `_BIJOY_FONTS` (`bangla_legacy.py:332`) so it stays **byte-for-byte** (today it's force-converted through the **wrong SutonnyMJ map**, contradicting the line-325 comment) — correctness bug | S/Md | regression-test a Boishakhi run is unchanged |
| WP-193-route | **(M, follow-on)** introduce a **map registry** (today `_bangla_maps.py` ships **one** map and `convert_bijoy_to_unicode` is hardwired to it); route font→map-id; **a font with no registered map is never coerced**; each new encoding (Boishakhi/Bangla-Word) needs its **own oracle-tested golden fixture** before its fonts are added | M/Md | |
| WP-194 | **Forward-conversion golden-vector regression** (Bijoy bytes → expected Unicode, frozen) + **idempotence as a TESTED property** | S/Md | round-trip is ill-posed (map is **many-to-one**); idempotence is **non-trivial** (MAIN maps ASCII letters/digits → Bengali, so a 2nd pass over mixed EN+BN re-fires) → either prove on the pinned fixtures or scope idempotence to the `delegacify`/`recover_mixed` entry points (which gate on font/density) and document bare `convert_bijoy_to_unicode` is **not** idempotent on residual-ASCII; **pin the oracle commit hash** in CI; oracle = **fidelity to Mukti**, NOT linguistic correctness (correctness → WP-191 gates) |

### Theme K — Perf / stability / accuracy / efficiency (these are **acceptance gates**, not WPs)
| Gate | Measures | Type |
|------|----------|------|
| **Digest efficiency** | re-digest unchanged — **gate** on the proxy "second digest converts **0** changed files" (WP-140 cache-hit count); ≥2× wall-clock = **benchmark** (named hardware) | gate + benchmark |
| **Recall latency** | "p95 < 150 ms @ 50k recall-units" = **benchmark on named hardware**, **lands with WP-201, not before** (today's linear cached scan is ~0.5–0.6 s @ 50k per R-13). CI **gate** = op-count proxy that **also lands with WP-201, not before** — the current `_bm25_rank_tokenized` is a **linear scan over every unit**, so its iteration counter is **∝ corpus size** and would *fail* this assertion; the proxy is only satisfiable once WP-201's **term→postings inverted index** scopes scoring to the query terms' postings. The proxy: instrument the inverted-index scorer with an iteration counter, replicate the corpus 1× vs 10× with a **fixed query**, and assert the counter is **constant** (∝ query terms, not corpus size). Define "unit" = entity cards + theme summaries | benchmark + proxy gate (both **with WP-201**) |
| **Accuracy** | EN recall@k floor **already CI-gated** (`test_eval.py`); **WP-202a** adds the **BN** + **conversion-fidelity** gates; run jointly with the byte-budget gate so neither is gamed | gate |
| **Stability** | grep no raw `open(...,"w")`/`write_text` outside `_io` [C2] + crash-injection tests | gate |
| **Efficiency** | peak RSS via `psutil` at `--scale`, per cycle (benchmark; runner variance ⇒ non-blocking) | benchmark |

**WP-201** *(M/Md, v2.9)* = build the term→postings **inverted index** at digest time. **Parity:** sum each doc's
per-term BM25 contributions in a **canonical (sorted) query-term order** so the indexed score is **bit-identical** to
the linear scorer → top-k **set AND ordering are then exactly identical** (with the documented `(-score, unit index)`
tie-break); WAND/block-max pruning keeps the safe-up-to-k property (a pruned doc cannot enter top-k). (Without the
canonical-order summation, float re-association can flip a ≤1-ULP near-tie and reorder it — so the canonical sum is
required, not optional.) The already-shipped pre-tokenised `bm25_index.json` cache is **not** this deliverable.
**WP-202a** *(S/Md, v2.7)* = the [C6] eval-corpus + BN/conversion gates + baseline freeze (sequenced **first**).

### Theme Z — 🚀 v3.0.0 marquee: Graph schema v2
Per **[C5]**. Typed & directional relation attributes (WP-120) · temporal & numeric facts (PII-safe) · fact confidence
+ salience (WP-123) · entity sub-types (WP-121) · provenance codepoint-offset spans (WP-123 produce / WP-134 cite) ·
**community-algorithm pin** ([C1]) · **default-dependency slim-down** (WP-181b, ADR-010) · recall/render rewritten —
still token-free, per-payload byte-capped. **Export-format v1→v2 deprecation:** ship `docs/export-format/v2/` (new
fields optional); `mta export` emits v2 by default but supports **`--format v1`** (down-projecting) **through v3.1**,
warning thereafter, removed **no earlier than v3.2**; v1 `graph.schema.json` stays published; bundle carries a
`format_version`; v2 schema CI-enforces confidence ∈ [0,1], salience numeric, relation direction/type closed enum,
offsets non-negative & bounded, plus the existing edge→node referential-integrity check.

---

## Release train
| Release | Marquee | Headline WPs (L-items ≤3) |
|--------|---------|----------------------------|
| **v2.7.0** | Slim core (additive) + easy install | WP-180 (additive), **WP-181a**, WP-183, WP-170(L), WP-173, **WP-174(L)**, WP-175, WP-176, WP-100/101/102, WP-103/104, **WP-105**, **WP-202a** |
| **v2.7.x / v2.8.0** | Cross-AI guides + conversion accuracy | WP-150/151/152/153, **WP-154(L)**, WP-155, WP-171/172, WP-177; WP-110, WP-111a, **WP-111b(L)**, WP-112a, WP-113, WP-132, WP-140, WP-130 |
| **v2.8.x** | Mobile | **WP-160(L)**, WP-161 (gated), WP-162, WP-141, WP-142, WP-144 |
| **v2.9.0** | Bengali + graph quality + frugality | WP-190/191/192/193-fix/193-route/194, **WP-121(L)**, WP-122 (quality), WP-124/125/127, WP-133, WP-130, WP-201 |
| **v2.10.0** | Opt-in power features *(at the L-budget ceiling — 3 L-items)* | ⚠️ **WP-131(L)**, ⚠️ **WP-143(L)**, **WP-126(L)** |
| **v3.0.0** | Graph schema v2 (Theme Z) *(at the L-budget ceiling — 3 L-items)* | **WP-120(L)**, **WP-123(L)**, WP-134, WP-181b, **WP-122 pin (community-algo)**, **WP-121 sub-types(L, budget-counted here; the v2.9 resolution half is counted in v2.9)**, recall/render v2, migration [C5] |

*(Gated on schema v2, not a version number — extra minors are legitimate so no release is overloaded.)*

## Global acceptance gates (measurable per [C6])
- Invariants preserved; **[C1] cross-env determinism matrix** green in the clean-image lane; **[C3] no-egress** green.
- **WP-202a landed** before any BN-accuracy/conversion-fidelity gate is cited (EN recall@k is already gated).
- **Frugality**: `MTA_RECALL_BUDGET=16384` enforced (max ≤ budget, median ≤ 4096 on the golden set).
- **Dep budget**: ≤ 6 total / ≤ 5 excluding `mcp`, all pure-Python except `mcp` (`test_dep_budget.py`).
- **Conversion**: success ≥ committed baseline + golden-diff fidelity ≥ floor (PDF columns non-gating).
- **Accuracy**: recall@k ≥ floor on EN **and** BN, ratcheting, run with the byte-budget gate.
- **Migration** [C5]: frozen v1→v2 fixture migrates losslessly-forward, validates against v2 schema, recall-parity vs the **pre-migration v1 store**; idempotent; atomic; crash-injection-tested.
- **Manual acceptance (not CI)**: time-to-first-memory on a **fresh OS account, no Python, only the download link**, per (OS × no-terminal/one-command), in `ACCEPTANCE.md`; **GUI installer launches with no SmartScreen/Gatekeeper block** (per OS). CI proxy = **install ≤ 2 actions/surface** where an "action" = one user shell command **or** one GUI click (OS security prompts excluded, tracked under WP-175); a CI test parses the machine-readable install-recipe blocks and asserts ≤ 2. **The blocks do not exist yet — WP-170 owns producing them as a committed, schema-defined source-of-truth** (one block/surface; each `action` typed `shell`|`gui`, security-prompt steps flagged `excluded`) that this CI test parses; today's README install table is free-form prose and is **not** parseable, so the proxy is **un-runnable until WP-170 lands the structured recipes** (no instrument before then). Termux gated on WP-161 prereq; on-device iOS excluded.

## Explicitly out of scope / won't-do
- ❌ Any LLM/embedding/summarizer in the **default** path. An `ask`/`summarize` tool stays the host model's job.
- ❌ Always-on network, telemetry, or returning document contents to the model.
- ❌ Mandatory heavy/compiled deps; `_rearrange` linearization; full LIFE-02 refcounting.
- ❌ Blanket cross-script normalization; blanket Bijoy reorder `replace`; the 4 S30-rejected reorder rules.
- ❌ Spreadsheet aggregation/charting (host-model + exports instead).

## Open decisions for the owner
- **ADR-008** encryption opt-in by default. **ADR-010** (now recorded): dependency deprecate-then-remove.
- **Community-algo pin** ([C1]) = NetworkX Louvain default, Leiden opt-in; pin lands v3.0. Confirm.
- **Paid signing identities** (Round 2): Windows **Authenticode cert** (WP-175) + **Apple Developer ID** (WP-175 macOS) are owner prerequisites with cost.
- **WP-182** spike-only; **WP-163** research-only; **WP-131** pure-BM25 stays default.
- **Interim cross-env nondeterminism** (RISKS R-20, to be added): until v3.0 pins the algo/numpy axes, two installs with
  different optional deps can produce different `graph.json`; accepted interim, gate enforced same-environment.

---

## Adversarial review log
- **Round 1 (S26)** — 10 lenses; ~5 Critical / ~14 High / ~20 Med-Low; all Critical/High folded (contracts [C1]–[C6],
  Effort/Risk tags, v2.10 split, WP-155/174/175/176/177/202a/181a-b, ADR-010, reframed gates).
- **Round 2 (S26)** — 7 fresh lenses (incl. convergence + internal-consistency auditors) re-attacked the revision.
  Findings folded into **this Round-3 revision**: macOS notarization (Critical → WP-175 renamed) · numpy-absent
  recall-death + graph divergence (Critical → WP-181a byte-identical pure-Python fix + [C1] numpy/rapidfuzz axes) ·
  migration machinery unbuilt + best-effort backup (Critical → [C5] rewritten: write-lock, sentinel, abort-on-failed-
  backup, in-memory-read-only) · WP-201 "byte-identical index" impossible (Critical → top-k result+order parity) ·
  dep baseline 10→11 + `mcp` carve-out · WP-133 committed `16384`/median-`4096` + instrument · "run_eval already CI-
  gated" correction → WP-202a scoped to BN+conversion · latency proxy named (corpus 1×/10× iteration-count) ·
  "install ≤2 actions" defined + parser · WP-181b → v3.0 only · WP-105/WP-114 scheduled (114 folded into 180) ·
  WP-121 split 2.9-resolution/3.0-subtypes + per-script `_norm` proof · WP-123/134 cite [C5] · WP-122 algo-pin → v3.0
  (quality stays 2.9) · WP-160 per-device tokens/revocation/atomic-pairing/real-confirm · WP-126 inline-data + escape-
  all-fields + basename paths · WP-154 detect-first/"no app yet"/"browser won't work" · PATH fix all-surfaces ·
  WP-177 localize error/empty-state strings · directive-#10 "data mapping" scope + **WP-127** · WP-120 undirected-
  backbone + CI precision gate · WP-191 the 4 rejected rules stay rejected (NEW rules only) · WP-193 split fix/route +
  map-registry-doesn't-exist · WP-194 idempotence is tested-not-assumed + pinned oracle.
- **Round 3 (S26)** — 6 fresh lenses (convergence + internal-consistency + determinism/migration + measurability +
  security/semver + feasibility/Bengali/novice). **Convergence auditor verified all 22 Round-2 items FULLY RESOLVED;
  0 Critical this round.** ~14 High, all *roadmap-text precision* (no direction change), folded into **this Round-4
  revision**: WP-181a reworded "merge-decision-identical" (not "byte-identical dot product"; the achievable-cosine
  spacing makes it safe in practice — verified numerically) + split the `vectors.json` sidecar writer out of
  `save_vectors` + module-level numpy import is an ImportError + gate against the v2.6.2 baseline / else numpy stays
  core · [C5](a) dropped `digest` as a migration trigger (digest writes a fresh v2 store, only `mta migrate` up-casts
  in place) · WP-120 `direction` is a determinism axis → canonical `sorted((u,v))` orientation · WP-201 parity =
  canonical-order summation → bit-identical score → exact ordering (not "ordering may differ") · WP-160 explicit TLS
  enforcement (`--tls-cert/key` or `--behind-tls-proxy`) + `/pair` ≥128-bit token + brute-force cap + **live**
  per-request revocation · WP-143 names the recall key source (`MTA_PASSPHRASE`/keychain; "never persisted" = never
  on disk) · WP-174 frozen entry = `[sys.executable, "serve"]` (not `-m`) short-circuiting `which("mta")` · `[C-token]`
  dangling citation fixed · WP-121/122 v3.0-row L-tag + pin labels · `psutil` allowlisted (soft import) in the dep gate.
- **Round 4 (S26)** — the above edits. **Next: a confirmation round** (convergence + determinism/migration + security
  lenses); declare **CONVERGED** when it yields no new Critical/High (the trend is 5 → 4 → 0 Criticals).
