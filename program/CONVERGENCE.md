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
