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
