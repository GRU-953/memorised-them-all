# Security Policy

## Supported versions

The latest released minor version receives security fixes (SemVer; see
[CHANGELOG.md](CHANGELOG.md)).

## Reporting a vulnerability

Please report privately via **GitHub Security Advisories** ("Security → Report a
vulnerability") on <https://github.com/GRU-953/memorised-them-all>, or open a
minimal non-sensitive issue. We aim to acknowledge within a few days. Please do
not put exploit details in public issues.

## Security model & posture

**Local-first, no telemetry.** All processing is on-device, with **no AI models at all**
(no LLM, no Ollama, no embedding model, no GPU). The only network use is: (a) downloading
Python dependencies when you install or run `mta doctor` / `mta update`; (b) a throttled
(~daily) GitHub *release check* (disable with `MTA_AUTO_UPDATE=off`); (c) an **opt-in** pull
of the latest upstream MarkItDown (`MTA_MARKITDOWN_UPSTREAM=on`/`MTA_AUTO_UPDATE=upstream`),
pinned to a resolved commit. No analytics; with the defaults, document contents never leave
your machine.

**Token-free boundary.** MCP tools return only metadata or a small slice in which **every
returned field is hard-capped in UTF-8 bytes** (label ≤ 200 B, text ≤ 600 B, ≤ 5 docs,
synopsis ≤ 1200 B); document contents never return to the model.

### Processing untrusted files (threat model)

Attachments are untrusted input. Mitigations:

- **Path traversal** — output filenames are derived from `Path.name` (directory components
  stripped) and de-duplicated with a content hash; project names are slugified before use
  as directory names, so `forget`/writes cannot escape `MTA_HOME`.
- **Decompression bombs** — **every** ZIP-container input (`.zip`, `.docx`, `.xlsx`,
  `.pptx`, `.epub`) is bounds-checked before extraction: rejected on excessive uncompressed
  size, an extreme compression ratio, or a nested archive. Per-file size cap via
  `MTA_MAX_FILE_MB` (default 200). Native archive expansion (zip/tar/gz/bz2/xz) is
  **stream-capped during copy** against a cumulative byte/entry/depth budget, with
  all-or-nothing rollback. Optional **rar/7z** (via `unar`/`7z`) cannot be stream-capped, so
  extraction runs under a **live disk-usage monitor** that kills the extractor and rolls back
  within a fraction of a second of the tree exceeding the same cumulative byte budget (not
  merely a wall-clock timeout) — so a rar/7z bomb cannot run the disk away.
- **Injection hardening** — the engine is fully model-free, but the small recall slice it
  returns is later read by Claude, so control tokens and prompt-fence sequences embedded in
  *source* documents are neutralised during entity/fact extraction **and** the theme/synopsis
  summarisers, and every returned field is byte-capped so a document cannot flood or
  manipulate the model's context.
- **Unsafe deserialization** — all persisted state is JSON; the vector store is loaded with
  `numpy.load(..., allow_pickle=False)`. No `pickle` / `eval` / `exec` / `yaml.load`.
- **Crash safety** — `graph.json` and the vector store are written atomically
  (temp → fsync → `os.replace`); concurrent clients are serialised by a cross-process lock,
  and a store from a newer build is backed up before any overwrite.
- **Subprocesses** — every external command is an argv list (no `shell=True`, no
  `curl | sh`); optional helpers (Tesseract OCR, `unar`/`7z`, LibreOffice) run with fixed
  arguments and bounded, killable timeouts, never an interpolated shell string.

### Remote access (opt-in HTTP transport)

By default the MCP server speaks **stdio** and opens no socket. `mta serve --http`
additionally exposes the tools over MCP **Streamable HTTP**, hardened so the inbound
listener is safe to run:

- **Loopback by default** — binds `127.0.0.1` and *refuses* a non-loopback host unless
  you pass `--allow-remote` (or set `MTA_HTTP_ALLOW_REMOTE=on`), which prints a warning.
  No `0.0.0.0` by accident.
- **Authentication is mandatory** — every request must send `Authorization: Bearer
  <token>`. The token comes from `MTA_HTTP_TOKEN`, or is auto-generated and stored at
  `MTA_HOME/state/http_token` (`0600`). There is no unauthenticated mode; the token is
  compared in constant time and is never returned by any tool or by the `/healthz` probe.
- **DNS-rebinding protection** — the `Host`/`Origin` headers are validated against an
  allowlist (the bound `host:port` plus loopback aliases; extend via
  `MTA_HTTP_ALLOWED_HOSTS` / `MTA_HTTP_ALLOWED_ORIGINS` for a reverse proxy), so a
  malicious web page cannot drive your local server through your browser.
- **No built-in TLS** — loopback traffic doesn't need it. To expose the server beyond
  localhost, terminate TLS at a reverse proxy, treat the bearer token as a password, and
  never place it on an untrusted network.

The optional **REST gateway** (`mta serve --rest` — plain JSON `POST /tools/{name}` for
non-MCP clients) enforces the *same* controls: loopback-only by default with the identical
non-loopback refusal, the **same** mandatory bearer token (shared `state/http_token`), and
a `Host`-header allowlist. Only `GET /healthz` is unauthenticated; `GET /openapi.json` and
every tool call require the token.

### Supply chain

- Releases build from committed sources; the version is single-sourced and CI fails on drift
  (and on a tag that doesn't match the version).
- The default MarkItDown is the **pinned PyPI** build (pip hash-verified). The optional
  upstream pull is pinned to a resolved commit and import-smoke-tested with rollback.
  `mta doctor` reports detected-vs-required dependency versions.
- The optional `graph` extra (`python-igraph`, `leidenalg`) is **GPL-licensed** and is *not*
  installed by the MIT core, which falls back to NetworkX Louvain.
- Releases use **OIDC trusted publishing** to PyPI (no long-lived token), ship a
  **CycloneDX SBOM**, and are **Sigstore/cosign-signed** (a single-file `*.sigstore.json`
  bundle per artifact — signature, Fulcio certificate and Rekor proof in one file);
  every GitHub Action is SHA-pinned.
