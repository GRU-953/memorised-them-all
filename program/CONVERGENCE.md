# Convergence note — v2.6.0 recall + resolve performance pass (S24)

**Status: CONVERGED. No open Critical/High.** Closed deferred backlog R-13/R-14/R-15 (perf)
with NO behaviour change: recall ranking is byte-identical (cached vs on-the-fly) and resolve
merges equal the true full O(n²) scan on realistic corpora (parity-tested). No new dependency.

- **R-13 + R-15 (recall):** a deterministic pre-tokenised `bm25_index.json` is built once at
  digest time; recall ranks from it via a meta-only load (never the `vectors.npz` matrix).
  **~8.8× faster @8k units** (118→13.5 ms/query), identical hits. Additive (no SCHEMA bump),
  back-compat: old stores / torn / absent / corrupt cache all fall back to on-the-fly safely.
- **R-14 (resolve):** `(script, prefix-2 + suffix-2 per token)` blocking → candidate pairs are
  **6.6% of O(n²)** at 3k names; dense n×n cosine replaced by per-candidate dot product; the
  silent 1500 cap is now documented/configurable `MTA_RESOLVE_MAX_NAMES` (default 5000). `_norm`
  untouched → WP-90 Bengali distinctness preserved.

Convergence criteria — ALL met:
- **(a) Two clean rounds.** Up-front: 3 expert design/cross-check agents. Round 1 (adversarial
  diff review) → **1 High** (the prefix-only block key dropped fuzzy merges where the matching
  token differed at its LEADING char — MacDonald/McDonald; the parity test compared blocking-vs-
  blocking and couldn't catch it) + 1 Low (cache gate didn't check inner tokens are str) → **both
  fixed**: added a per-token SUFFIX block key + a TRUE full-scan parity test (`_block=False`).
  Round 2 = **independent fresh-verification** (own adversarial fuzz corpus, ran the suite + all
  gates first-hand) → **NO Critical/High**; one Low (the "reproduces the full scan" wording over-
  claims for the *embedding* pass, where blocking safely skips spurious hash-collision merges —
  the over-split/safe direction) → docstring + test comment tightened. Monotonic (1H+Low → 0).
- **(b) Numeric gates / no regression.** **261 pass / 3 skip** (+11 over v2.5.0); determinism
  byte-identical incl. the new `bm25_index.json` (independently SHA-256-verified across two homes);
  recall cache-equivalence + corrupt-cache fallback verified; resolve blocked==full-scan on a
  realistic corpus + a 40-trial fuzzer (only benign over-split divergences); `check_versions` OK
  @2.6.0; wheel+sdist `twine check` PASSED.
- **(c) No open Critical/High.** Invariants re-verified intact: token-free, no network on
  recall/resolve, crash-safe atomic writes (new file via `_atomic_write_text`), dependency-free
  (no pyproject/requirements change), back-compat. RISKS R-13/14/15 marked Resolved.

**Disposition:** MINOR **v2.6.0** (perf only; no tool/schema change). Awaiting CI confirmation +
the owner tag-push publish gate. _Prior v2.5.0 note below._

---

# Convergence note — v2.5.0 cross-AI multi-client auto-config (S23)

**Status: CONVERGED. No open Critical/High.** New feature (`mta setup` + `mta/core/clients.py`):
one command auto-registers the local stdio server into every detected MCP client (Claude
Desktop/Code, Gemini CLI, Cursor, VS Code, Windsurf, OpenAI Codex; Grok via Claude/.mcp.json
auto-discovery). ChatGPT app + xAI API are remote-MCP-only → documented HTTP path, not auto-config.

Convergence criteria — ALL met:
- **(a) Two consecutive clean review rounds.** Up-front: 3 expert agents (2 web-research verifying
  every vendor's MCP config format against current docs + 1 senior design/review). Round 1 = an
  adversarial review of the new module → **1 High** (`_merge_into` clobbered a valid-JSON-but-non-object
  config) + 1 Med (parser-less TOML single-quoted-key idempotency) + 1 Low (`--only` empty widened) →
  **all fixed with regression tests**. Round 2 = an **independent fresh-eyes** reviewer (no part in
  authoring/round-1) re-ran the suite + all gates → **VERDICT: NO Critical/High — converged**; only a
  narrow **Low** (parser-less TOML duplicate-detection of non-canonical headers, backup-protected),
  which was then **also fixed** (regex tolerates whitespace/comments/all key quotings). Monotonic
  (1H+Med+Low → 0); no reopened findings.
- **(b) Numeric gates / no regression.** 234 baseline → **250 pass / 3 skip** (+16 net new tests in
  `tests/test_clients.py`); `check_versions` OK @2.5.0 across all 7 surfaces; `python -m build` +
  `twine check` PASSED (sdist+wheel); `clients.py` ships in the wheel; `.mcpb` still bundles
  `launch.py` (+win32 override). Live `mta setup --dry-run`/`recipes` + end-to-end digest/recall smoke-OK.
- **(c) No open Critical/High.** Invariants independently re-verified intact: token-free, **no network on
  the setup path** (the `setup`/`setup-claude` CLI branches return before any engine/updater wiring),
  atomic crash-safe writes, dependency-free (TOML works on the 3.10 floor with no `tomllib`), never
  clobbers an existing config (JSONC + non-object-JSON both left untouched), idempotent, cross-platform.
  Published docs (README/CHANGELOG/recipes) verified to match the code (no over/under-claim). Residual =
  the Med/Low perf deferrals R-13…R-19 (unchanged, not looped on).

**Disposition:** MINOR **v2.5.0** (additive feature; no tool/schema change). Awaiting publish HUMAN GATE
(owner-gated tag push → release train). _Prior v2.4.2 note below._

---

# Convergence note — v2.4.2 review-driven hardening (S22)

**Status: CONVERGED. No open Critical/High.** A maximal 9-agent re-audit of shipped v2.4.1
found **1 Critical + 4 High** (token-free `label` byte-leak; char-vs-byte caps; `resolve._norm`
Bengali over-merge; rar/7z disk-fill; Windows `.mcpb` can't start). All fixed in WP-89…95
(+ Med bundle WP-93/94), each with a regression test.

Convergence criteria — ALL met:
- **(a) Two consecutive clean review rounds.** Round 1 = initial audit (found 1C+4H → fixed).
  Round 2 = 5-lens re-review of the diff → **0 new Critical/High**. Round 3 = an **independent
  fresh verification agent** (no part in authoring/reviewing) re-ran the suite + all gates →
  **VERDICT: SHIP, 0 Critical/High**. Monotonic progress (1C+4H → 0); no reopened findings.
- **(b) Numeric gates met, no regression.** Token-free worst-case Bengali: recall **394 KB→86 KB**,
  overview **157 KB→18 KB** (per-field byte caps enforced); determinism **byte-identical** across
  hash-seed (SHA-256 reproduced); resolve keeps distinct Bengali distinct; rar/7z bomb bounded
  (aborts+rolls back); export has zero absolute paths; `.mcpb` `mcpb validate` passes.
- **(c) No open Critical/High.** Residuals are Med/Low, recorded as accepted/deferred in
  `RISKS.md` R-13…R-19 (perf-index cache, resolve O(n²), non-Bengali Indic, cosign-bundle
  migration, etc.) — not looped on.

**Validation:** full suite **235 pass / 2 skip** (full-deps venv) incl. conversion-e2e; offline
lane 232/2; `check_versions` OK at 2.4.2; wheel/sdist `twine check` PASSED. Released as PATCH
**v2.4.2** (bug/security only, no tool/schema change). _Prior v1 note below._

---

# Convergence note — v1 hardening program (WP-90)

**Status: CONVERGED for the build/code scope.** Against the program's convergence
criteria (Section 5):

**(a) No Critical/High findings remain.** The Phase-1 audit's **2 Critical + 12 High**
are closed/mitigated, and the independent fresh-eyes pre-release review's **3 High** are
fixed (`AUDIT.md`, `REVIEW.md`).

**(b) Acceptance criteria pass in CI + Phase-6 (runnable scope).** A2/A3/A4/A5/A7/A12 met
and CI-gated; A9 met; A8 mostly-met (release train hardened — the live PyPI publish is
owner-gated); A10/A11 measured in `TEST_REPORT.md` (offline E2E 5/5; accurate-mode pass
via live Ollama; fast mode **≈25–100× benchmarked**). Everything on green CI across the
Ubuntu/macOS/Windows × 3.10/3.12 matrix.

**(c) The last review pass produced only marginal / deliberately-declined items**, logged
in `REVIEW.md` (full graph+vectors write-transaction, recall lock-hold, non-atomic derived
outputs, `workflow_dispatch` tag gate) plus the deferred Low/Med (CI-09 lockfile, PIPE-05/06,
LIFE-02 residual) and the v1.x+ scope. None clear the bar for v1.

## Delivered
**14 work packages, 13 feature PRs (#5–#17)**, every one CI-green. Both Criticals + all
Highs closed; Phase-2 **R1–R6** complete; offline-recall reliability; security hardening +
`SECURITY.md`; CI-gated eval harness; hardened **OIDC + SBOM + cosign** release train;
Phase-6 E2E. `develop` is **v1.4.0**, ready to release; `main` stayed releasable throughout.

## Remaining — owner-gated (NOT a code convergence blocker)
- **WP-41 publish:** configure a PyPI **Trusted Publisher** + add `HOMEBREW_TAP_TOKEN`
  (`PUBLISH_MANIFEST.md`), then `git tag v1.4.0 && git push --tags` — the train publishes
  PyPI + the GitHub Release (+`.mcpb`) and bumps the Homebrew tap.
- **v1.x+:** Phase-3 cross-AI interop (HTTP/REST transports, schema exports, REST gateway,
  pluggable backends), extra publishing channels (containers/registries/store listings),
  and the deferred Low/Med items above.

## Deliberately declined (rationale)
- **PKG-06** manifest `$schema` — MCPB has no canonical hosted schema URL (verified upstream).
- **Encryption-at-rest on by default** — hurts simplest-install + portability; opt-in is the
  v1.x+ plan (ADR-008).
- **Heavy rerank/model deps in v1** — conflict with the "simplest install" invariant (ADR-005).
