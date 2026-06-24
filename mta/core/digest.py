"""The digestion orchestrator — convert → segment → embed → extract → resolve →
graph → communities → layered summaries → materialise.

Returns **only metadata** (counts, paths, stats): document text never crosses
back into the conversation, which is what makes a whole-folder digest cost
~0 Claude tokens. Heavy steps run locally and parallelise across performance
cores. Summaries are a deterministic fact-join — fully model-free, so two digests
of the same corpus produce byte-identical output.
"""
from __future__ import annotations

import glob as _glob
import hashlib
import json
import multiprocessing as _mp
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from . import graph as graphmod
from . import locks, render, store
from .config import Config
from .convert import _DATA_EXTS, _TEXT_EXTS, SUPPORTED_EXTS, convert_file

# Extensions whose conversion is pure-Python (``_native_text`` + linear Bengali regex
# substitutions, size-capped): they can never hang in an un-interruptible C parser, so they
# do NOT need the killable per-file subprocess — converting them inline skips the ~100 ms
# spawn each and is the dominant cost on large text/data corpora.
_INLINE_CONVERT_EXTS = _TEXT_EXTS | _DATA_EXTS
from .embed import Embedder
from .extract import Extraction, extract_chunk
from .platform import worker_count
from .resolve import resolve_entities
from .segment import segment_file

import re as _re
# A "numeric-ish" token: digits with currency/percent/separators/parens (table cells).
_NUMERICISH = _re.compile(r"[-+(]?[\d][\d.,%/:()\-]*\)?")
# A long hex token (colour profile / XMP / base16 dump from design files), not prose.
_HEXISH = _re.compile(r"(?i)[0-9A-F]{12,}")


# ---- input expansion --------------------------------------------------
def _walk_files(root: Path):
    """Yield files under ``root`` robustly: os.walk with ``followlinks=False`` (so a
    symlink cycle can't loop) and an ``onerror`` that skips unreadable dirs — so one
    pathological entry (symlink loop, permission error) can never crash a folder digest."""
    import os
    for dirpath, _dirnames, filenames in os.walk(str(root), followlinks=False,
                                                 onerror=lambda _e: None):
        for name in filenames:
            yield Path(dirpath) / name


def _expand(paths: list[str], *, all_types: bool = True,
            cfg: Config | None = None) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()

    def add(p: Path, *, explicit: bool = False, root: Path | None = None):
        try:
            rp = str(p.resolve())
            if rp in seen or not p.is_file():
                return
        except (OSError, RuntimeError, ValueError):
            return  # broken/looping symlink or unresolvable path → skip, never crash the batch
        # Out-of-tree symlink policy: a symlink found during a FOLDER walk whose target
        # resolves OUTSIDE the digested root is skipped — a symlink planted in a folder
        # must not trick the digest into reading arbitrary host files (e.g. ~/.ssh/…).
        # Explicitly-named paths (and glob hits) are always honored — the user chose them.
        if not explicit and root is not None:
            try:
                if p.is_symlink():
                    Path(rp).relative_to(root.resolve())
            except (ValueError, OSError):
                return
        known = p.suffix.lower() in SUPPORTED_EXTS
        if not explicit and not known:
            # Unknown extension: include it (so convert_file's text-fallback can digest
            # it, or skip binaries) only when digesting all file types, and never if it's
            # hidden relative to the walked root (.git, .DS_Store, dotfiles, …).
            if not all_types:
                return
            try:
                rel = p.relative_to(root).parts if root else (p.name,)
            except ValueError:
                rel = (p.name,)
            if any(part.startswith(".") for part in rel):
                return
        seen.add(rp)
        files.append(p)

    for raw in paths:
        if any(ch in raw for ch in "*?[") and not Path(raw).exists():
            for hit in _glob.glob(raw, recursive=True):
                add(Path(hit))
            continue
        p = Path(raw).expanduser()
        if p.is_dir():
            for child in sorted(_walk_files(p)):
                add(child, root=p)
        else:
            add(p, explicit=True)   # an explicitly-named file is always digested

    # Recursive archive expansion (v2): each archive is expanded (bounded, traversal-
    # safe — see archive.py) into cfg.unpack_dir and REPLACED by its extracted members;
    # an archive that can't be expanded (no rar/7z tool, corrupt, budget breach) stays
    # in the list so convert_file reports an honest 'skipped'. Nested archives are
    # handled inside expand_archive (depth-capped), so this loop terminates.
    if cfg is not None and getattr(cfg, "archive_recursive", False):
        from . import archive as _archive
        i = 0
        while i < len(files):
            f = files[i]
            if _archive.kind(f) is None:
                i += 1
                continue
            dest = _archive.expand_archive(f, cfg)
            if dest is None:
                i += 1                                  # kept → honest skipped at convert
                continue
            files.pop(i)
            for child in sorted(_walk_files(dest)):
                add(child, root=dest)                   # appended at the end; re-checked

    # Content-hash dedup (v2): byte-identical inputs (duplicate archives, already-
    # extracted archive twins) are digested ONCE. First occurrence in the (stable)
    # collection order wins, so the result is deterministic.
    if cfg is not None:
        by_hash: set[str] = set()
        unique: list[Path] = []
        for f in files:
            try:
                h = hashlib.sha256()
                with open(f, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                        h.update(chunk)
                d = h.hexdigest()
            except OSError:
                unique.append(f)                        # unreadable → let convert report it
                continue
            if d in by_hash:
                continue
            by_hash.add(d)
            unique.append(f)
        files = unique
    return files


# ---- conversion worker (top-level so it pickles under spawn) ----------
def _convert_worker(payload):
    path_str, out_dir_str, cfg, out_name = payload
    from .platform import bootstrap_path, pin_native_threads
    pin_native_threads()
    bootstrap_path()  # spawned children don't inherit a library embedder's healed PATH
    return convert_file(Path(path_str), Path(out_dir_str), cfg, out_name=out_name).as_dict()


def _convert_timeout(src: str, cfg: Config) -> int:
    """Per-file budget: a base + size-scaled headroom for hang-prone container formats,
    capped. 0 → disabled (no isolation)."""
    base = getattr(cfg, "convert_timeout", 0)
    if not base or base <= 0:
        return 0
    try:
        mb = os.path.getsize(src) / 1048576
    except OSError:
        mb = 0
    per_mb = 4 if os.path.splitext(src)[1].lower() in {
        ".pptx", ".docx", ".xlsx", ".xls", ".doc", ".ppt", ".pps", ".dot", ".xlt", ".pdf", ".epub", ".zip"} else 1
    cap = getattr(cfg, "convert_timeout_max", 900) or 10 ** 9
    return int(min(base + per_mb * mb, cap))


def _convert_worker_pipe(payload, conn):
    """Run one conversion and send its result dict over a pipe (timeout-isolated path)."""
    try:
        conn.send(_convert_worker(payload))
    except BaseException as exc:  # noqa: BLE001 — report, don't die silently
        try:
            conn.send({"source": payload[0], "status": "failed",
                       "method": f"worker-error:{type(exc).__name__}", "output": None})
        except Exception:
            pass
    finally:
        conn.close()


def _convert_isolated(payload, cfg: Config) -> dict:
    """Convert ONE file in its own spawned subprocess with a hard timeout, hard-killing it
    if it hangs (a parser stuck in a C extension can't be interrupted otherwise) — so one
    pathological file can never stall the whole batch. Cross-platform (spawn + terminate/kill).

    Fast path: a pure-Python text/data file (``_native_text`` + linear, size-capped Bengali
    regex) cannot hang in a C parser, so it is converted INLINE — skipping the ~100 ms
    subprocess spawn that otherwise dominates large text corpora. The subprocess+timeout is
    still used for every format that can hang (PDF/Office/image/unknown-content-sniffed)."""
    src = payload[0]
    if Path(src).suffix.lower() in _INLINE_CONVERT_EXTS:
        return convert_file(Path(src), Path(payload[1]), cfg, out_name=payload[3]).as_dict()
    timeout = _convert_timeout(src, cfg)
    ctx = _mp.get_context("spawn")
    parent, child = ctx.Pipe(duplex=False)
    proc = ctx.Process(target=_convert_worker_pipe, args=(payload, child), daemon=True)
    proc.start()
    child.close()
    res = None
    try:
        if parent.poll(timeout if timeout > 0 else None):
            try:
                res = parent.recv()
            except EOFError:
                res = None
    finally:
        parent.close()
    if res is None:  # timed out / died mid-send → hard-kill + mark failed (keep the batch alive)
        proc.terminate()
        proc.join(3)
        if proc.is_alive():
            proc.kill()
            proc.join()
        return {"source": src, "status": "failed", "method": "timeout",
                "error": f">{timeout}s", "output": None}
    proc.join(2)
    if proc.is_alive():
        proc.terminate()
    return res


def _assign_output_names(files: list[Path], *, reserved: set[str] | None = None,
                         fixed: dict[str, str] | None = None) -> dict[str, str]:
    """Assign a unique output filename per source path (race-free, in the main
    process). Distinct files with the same basename in different directories
    (e.g. many README.md) would otherwise overwrite each other and silently lose
    data. The first (sorted) keeps the clean name; collisions get a short,
    deterministic path-hash suffix.

    Incremental digest (v3) passes two extra maps so names stay STABLE across runs:
    ``fixed`` pins a path to the name a prior manifest already gave it (an updated file
    overwrites its own .md), and ``reserved`` seeds the taken-set with names that must not
    be reused (existing .md from other folders / unchanged files) so a newly-converted
    file can never clobber an unrelated existing output.
    """
    import hashlib
    taken: set[str] = {n.lower() for n in (reserved or set())}
    assigned: dict[str, str] = dict(fixed or {})
    taken.update(v.lower() for v in assigned.values())
    for f in files:  # files are already sorted upstream → deterministic
        if str(f) in assigned:           # pinned by `fixed` (incremental) → keep it
            continue
        h = hashlib.sha1(str(f).encode("utf-8")).hexdigest()[:8]
        base = f.name + ".md"
        # Clamp well under NAME_MAX (255) / Windows MAX_PATH so a very long source name can't
        # raise an uncaught OSError and abort the whole batch; case-fold the collision check
        # so two outputs can't silently overwrite on a case-insensitive FS (macOS/Windows).
        if base.lower() in taken or len(base.encode("utf-8", "ignore")) > 200:
            base = f"{f.name[:80]}.{h}.md"
        taken.add(base.lower())
        assigned[str(f)] = base
    return assigned


def _sha256_file(path: Path) -> str | None:
    """Streaming sha256 of a file's bytes, or None if unreadable. Cheap relative to
    conversion (no parsing/OCR), so re-hashing to detect changes is a clear net win."""
    import hashlib
    try:
        h = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _plan_conversions(files: list[Path], prior: dict, cfg: Config,
                      input_paths: list[str]) -> dict:
    """Plan an incremental digest: decide which files to (re)convert, which prior converted
    outputs to reuse unchanged, and which to prune because their source was deleted from a
    digested directory. Pure planning (deletes nothing) — the caller acts on the result.

    A file is **reused** (conversion skipped) when its bytes hash to the same value the
    manifest recorded AND its .md still exists. Everything else is converted. A prior entry
    whose source path no longer exists AND sat under one of THIS call's directory roots is
    **removed** (its .md pruned); prior entries from other folders are **preserved**. With an
    empty ``prior`` (full digest / incremental off) every file is converted and nothing is
    pruned — so the same code path serves both, and always (re)builds the manifest.
    """
    cur_rp: dict[str, Path] = {}      # resolved source path -> Path (this call's inputs)
    hashes: dict[str, str] = {}       # str(path) -> sha256
    for f in files:
        try:
            rp = str(f.resolve())
        except (OSError, RuntimeError, ValueError):
            rp = str(f)
        cur_rp[rp] = f
        h = _sha256_file(f)
        if h is not None:
            hashes[str(f)] = h
    cur_rp_set = set(cur_rp)

    roots: list[Path] = []            # directory roots of THIS call (prune only within them)
    for raw in input_paths:
        try:
            p = Path(raw).expanduser()
            if p.is_dir():
                roots.append(p.resolve())
        except (OSError, RuntimeError, ValueError):
            continue

    def _under_roots(rp: str) -> bool:
        for root in roots:
            try:
                Path(rp).relative_to(root)
                return True
            except (ValueError, OSError):
                continue
        return False

    preserved: dict[str, dict] = {}
    removed_outputs: list[str] = []
    removed = 0
    for rp, entry in prior.items():
        if rp in cur_rp_set or not isinstance(entry, dict):
            continue
        try:
            still = Path(rp).exists()
        except (OSError, ValueError):
            still = False
        if (not still) and _under_roots(rp):
            removed += 1                              # source deleted from a digested folder
            if entry.get("out"):
                removed_outputs.append(entry["out"])
        else:
            preserved[rp] = entry                     # other folder / still present → keep

    fixed = {str(cur_rp[rp]): prior[rp]["out"]
             for rp in cur_rp_set
             if isinstance(prior.get(rp), dict) and prior[rp].get("out")}
    reserved = {e["out"] for e in preserved.values() if e.get("out")}
    names = _assign_output_names(files, reserved=reserved, fixed=fixed)

    to_convert: list[Path] = []
    reused = 0
    reused_paths: set[str] = set()
    for rp, f in cur_rp.items():
        h = hashes.get(str(f))
        prior_e = prior.get(rp)
        md_ok = (cfg.markdown_dir / names[str(f)]).exists()
        if (h is not None and isinstance(prior_e, dict)
                and prior_e.get("sha256") == h and md_ok):
            reused += 1
            reused_paths.add(rp)
        else:
            to_convert.append(f)

    return {"to_convert": to_convert, "names": names, "hashes": hashes,
            "reused": reused, "reused_paths": reused_paths, "preserved": preserved,
            "removed_outputs": removed_outputs, "removed": removed, "prior": prior}


def _convert_all(files: list[Path], cfg: Config,
                 out_dir: Path | None = None,
                 names: dict[str, str] | None = None) -> list[dict]:
    out_dir = out_dir or cfg.markdown_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    # Incremental digest precomputes stable names over the FULL current corpus and passes
    # them in (so an updated file overwrites its own .md and a new one never clobbers an
    # unrelated existing output); the standalone `convert` path assigns fresh names.
    names = names if names is not None else _assign_output_names(files)
    n = worker_count(cfg.workers)
    payloads = [(str(f), str(out_dir), cfg, names[str(f)]) for f in files]

    # Per-file-timeout path (default): each file converts in its OWN killable subprocess,
    # so one file that drives a parser into an infinite loop can't stall the whole batch.
    # Up to n run concurrently (threads owning one child each). MTA_CONVERT_TIMEOUT=0 → legacy.
    if getattr(cfg, "convert_timeout", 0) and cfg.convert_timeout > 0:
        if n <= 1 or len(payloads) <= 1:
            return [_convert_isolated(p, cfg) for p in payloads]
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=n) as tp:
            return list(tp.map(lambda p: _convert_isolated(p, cfg), payloads))

    # Legacy path (timeout disabled): parallel pool with a main-thread retry on a worker
    # crash; a broken pool degrades to fully sequential. (No protection against a hang.)
    if n > 1 and len(files) > 1:
        from concurrent.futures import as_completed
        try:
            results = []
            with ProcessPoolExecutor(max_workers=n) as ex:
                futs = {ex.submit(_convert_worker, p): p for p in payloads}
                for fut in as_completed(futs):
                    try:
                        results.append(fut.result())
                    except Exception:  # noqa: BLE001 — isolate one bad file
                        bad = Path(futs[fut][0])
                        results.append(convert_file(bad, out_dir, cfg,
                                                    out_name=futs[fut][3]).as_dict())
            return results
        except Exception:  # noqa: BLE001 — pool construction / BrokenProcessPool
            pass
    return [convert_file(f, out_dir, cfg, out_name=names[str(f)]).as_dict()
            for f in files]


def convert_to_markdown(cfg: Config, paths: list[str], out_dir: str | None = None) -> dict:
    """Convert files/dirs/globs to Markdown locally and write the .md files to ``out_dir``
    (default: a ``markdown_converted/`` folder beside the input). Legacy Bengali
    (Bijoy/SutonnyMJ ANSI fonts) is auto-upgraded to Unicode during conversion.

    Token-free: returns only counts + output paths, never document text. This is the
    standalone "convert everything to Markdown" feature; ``digest`` runs the very same
    conversion as its first stage, so conversion-to-Markdown is the default everywhere.
    """
    import os
    cfg.ensure_dirs()
    files = _expand(paths, all_types=cfg.digest_all, cfg=cfg)
    if not files:
        return {"status": "no_input", "paths": paths,
                "message": "No convertible files found."}
    if out_dir:
        outd = Path(os.path.expanduser(os.path.expandvars(str(out_dir))))
    else:
        first = Path(os.path.expanduser(os.path.expandvars(paths[0])))
        outd = (first if first.is_dir() else first.parent) / "markdown_converted"
    results = _convert_all(files, cfg, out_dir=outd)
    from .archive import cleanup_unpacked
    cleanup_unpacked(cfg)            # extracted-archive scratch; converted .md persists
    ok = [r for r in results if r.get("status") == "ok"]
    bn = sum(1 for r in ok if "bn-unicode" in (r.get("method") or ""))
    return {
        "status": "ok", "out_dir": str(outd),
        "stats": {
            "files": len(files), "converted": len(ok),
            "bangla_unicode_converted": bn,
            "skipped": sum(1 for r in results if r.get("status") in ("skipped", "unsupported")),
            "failed": sum(1 for r in results if r.get("status") in ("failed", "empty")),
        },
        "outputs": [r.get("output") for r in ok if r.get("output")][:100],
    }


# ---- local summarisation (deterministic, model-free) -----------------
def _community_summary(label_facts: list[str], names: list[str], cfg: Config) -> str:
    from .extract import _defang_fence, _is_tabular_or_pii, _redact_pii, _scrub
    # Sanitise document-derived text: scrub control tokens + neutralise the fence
    # delimiters so a fact can't forge <<<END>>> to escape a data region. This is now
    # only cheap hygiene on classical/converted text (no LLM), but it still defends
    # memory.md / recall against control tokens embedded in documents.
    def _san(x: str) -> str:
        return _defang_fence(_scrub(str(x)))
    # Defence-in-depth: even though facts are already PII-filtered at extraction time, drop
    # any tabular/roster fact here too and redact stray digit-runs, so beneficiary names +
    # phone numbers can never reach a persisted theme summary / recall unit.
    facts = [_redact_pii(_san(f)) for f in label_facts[:12] if not _is_tabular_or_pii(str(f))]
    names = [_san(n) for n in names]
    # Deterministic fact-join — the only summary path.
    head = ", ".join(names[:5])
    body = " ".join(facts[:3])
    return (f"Theme around {head}. {body}").strip()


# ---- main entry -------------------------------------------------------
def digest(cfg: Config, paths: list[str], reset: bool = False,
           fast: bool = False) -> dict:
    # ``fast`` is accepted for MCP-client compatibility but is now a no-op: v2 always
    # uses the single deterministic, model-free path.
    cfg.ensure_dirs()
    # Single-writer per project: serialise concurrent digests / reset / forget so
    # two callers can't interleave into a torn graph<->vectors pair (LIFE-01).
    with locks.write_lock(cfg):
        return _digest_locked(cfg, paths, reset)


def _digest_locked(cfg: Config, paths: list[str], reset: bool) -> dict:
    t0 = time.time()

    if reset:
        _reset_project(cfg)
        cfg.ensure_dirs()

    files = _expand(paths, all_types=cfg.digest_all, cfg=cfg)
    if not files:
        return {"status": "no_input", "project": cfg.project,
                "message": "No convertible files found.", "paths": paths}

    # Incremental plan (v3): re-convert only changed/new files, reuse unchanged .md, and
    # prune the converted output of sources deleted from the digested folders. With an empty
    # prior (full digest, reset, or MTA_INCREMENTAL=off) every file is converted — the same
    # code path — and the manifest is rebuilt either way so the NEXT digest can be
    # incremental. The rebuilt memory is byte-identical to a full digest of the same final
    # corpus (conversion is deterministic), so this only changes WHICH files get converted.
    prior = store.load_manifest(cfg) if (cfg.incremental and not reset) else {}
    plan = _plan_conversions(files, prior, cfg, paths)
    for out in plan["removed_outputs"]:
        try:
            (cfg.markdown_dir / out).unlink()
        except OSError:
            pass
    conv = _convert_all(plan["to_convert"], cfg, names=plan["names"])

    # Assemble the next manifest: preserved (other folders) ∪ reused (this run) ∪ freshly
    # converted files that produced a .md. Skipped/failed files are left OUT so they are
    # re-evaluated next run (a media skip is instant; a transient failure gets retried).
    manifest = dict(plan["preserved"])
    for rp in plan["reused_paths"]:
        if isinstance(prior.get(rp), dict):
            manifest[rp] = prior[rp]
    res_by_src = {c.get("source"): c for c in conv}
    added = updated = 0
    for f in plan["to_convert"]:
        c = res_by_src.get(str(f))
        if not c or c.get("status") != "ok":
            continue
        h = plan["hashes"].get(str(f))
        if h is None:
            continue
        try:
            rp = str(f.resolve())
        except (OSError, RuntimeError, ValueError):
            rp = str(f)
        manifest[rp] = {"sha256": h, "out": plan["names"][str(f)],
                        "method": c.get("method", "")}
        if rp in prior:
            updated += 1
        else:
            added += 1
    store.save_manifest(cfg, manifest)

    # Rebuild the graph from the FULL markdown corpus on disk (accumulative; reset=True
    # cleared it first). The rebuild is shared with merge_memory, which rebuilds from a
    # merged corpus with no conversion step.
    result = _rebuild_from_markdown(cfg, t0, files_count=len(files), conv=conv,
                                    manifest=manifest)
    result["incremental"] = {
        "enabled": bool(cfg.incremental and not reset),
        "added": added, "updated": updated,
        "unchanged": plan["reused"], "removed": plan["removed"],
        "converted": sum(1 for c in conv if c.get("status") == "ok"),
    }
    from .archive import cleanup_unpacked
    cleanup_unpacked(cfg)            # extracted-archive scratch; the markdown persists
    return result


def _rebuild_from_markdown(cfg: Config, t0: float, *, files_count: int | None = None,
                           conv: list[dict] | None = None,
                           manifest: dict | None = None) -> dict:
    """Build (segment → extract → resolve → graph → communities → summaries → persist →
    materialise) from the project's CURRENT ``markdown/`` corpus — the deterministic core
    shared by ``digest`` (after conversion) and ``merge_memory`` (after copying source
    corpora, no conversion). Returns the token-free result dict (no incremental block)."""
    conv = conv or []
    all_md = sorted(cfg.markdown_dir.glob("*.md"))

    # Segment + extract.
    embedder = Embedder(cfg)
    all_chunks = []
    for md in all_md:
        all_chunks.extend(segment_file(md, cfg.chunk_chars))

    # Dedupe identical chunks, drop degenerate low-information passages (repetitive
    # filler whose boundary-shifted windows defeat exact dedupe), then cap the
    # workload with explicit reporting (never silently truncate).
    unique: dict[str, object] = {}
    skipped_low_value = 0
    for ch in all_chunks:
        if _low_value(ch.text):
            skipped_low_value += 1
            continue
        unique.setdefault(ch.text, ch)
    unique_chunks = list(unique.values())
    truncated = 0
    if len(unique_chunks) > cfg.max_chunks:
        truncated = len(unique_chunks) - cfg.max_chunks
        unique_chunks = unique_chunks[:cfg.max_chunks]

    # Extract across a modest, memory-aware pool. Rule-based extraction is fast and
    # CPU-bound, but on a small machine too many parallel workers still thrash memory,
    # so the default scales with RAM.
    extractions: list[tuple] = []
    mentions: list[dict] = []
    workers = max(1, min(_auto_extract_workers(cfg), len(unique_chunks))) if unique_chunks else 1

    def _safe_extract(c):
        # A mid-run extraction failure must not abort the whole digest after we have
        # already written the converted markdown — degrade that chunk to empty.
        try:
            return (c, extract_chunk(c))
        except Exception:  # noqa: BLE001
            return (c, Extraction())

    if workers > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as tp:
            results = list(tp.map(_safe_extract, unique_chunks))
    else:
        results = [_safe_extract(c) for c in unique_chunks]
    for ch, ex in results:
        extractions.append((ch, ex))
        mentions.extend(ex.entities)

    # Resolve entities → graph → communities.
    resolved = resolve_entities(mentions, embedder, resolve_cap=cfg.resolve_max_names)
    G = graphmod.build_graph(extractions, resolved["alias_to_cid"],
                             resolved["canonical"])
    partition = graphmod.detect_communities(G, cfg.community_algo)
    members = graphmod.community_members(G, partition)

    # Layered summaries (L1 communities, L0 synopsis).
    communities = []
    for comm_id, node_ids in sorted(members.items()):
        names = [G.nodes[n]["label"] for n in node_ids]
        facts = []
        for n in node_ids:
            facts.extend(f["text"] for f in G.nodes[n].get("facts", []))
        summary = _community_summary(facts, names, cfg) if node_ids else ""
        communities.append({
            "id": comm_id,
            "label": names[0] if names else f"Theme {comm_id}",
            "summary": summary,
            "members": node_ids,
            "size": len(node_ids),
        })

    synopsis = _synopsis(communities)

    # Build the persisted graph doc.
    for n in G.nodes():
        G.nodes[n]["docs"] = sorted(G.nodes[n].get("docs", set()))
        G.nodes[n]["community"] = partition.get(n, 0)
    # NOTE: no wall-clock fields ("created"/"seconds") are persisted — graph.json,
    # vectors.npz and memory.md must be BYTE-IDENTICAL for the same corpus (the v2
    # determinism contract). Timing lives only in the transient tool result below;
    # build recency is observable from file mtimes.
    graph_doc = {
        "project": cfg.project,
        # Single-sourced from store.SCHEMA_VERSION (v2 in v3.0.0): adding a literal here is a
        # CI lint failure. v2 = documents[] carry a portable per-document sha256.
        "version": store.SCHEMA_VERSION,
        "synopsis": synopsis,
        "nodes": [{"id": n, **{k: v for k, v in G.nodes[n].items()}} for n in G.nodes()],
        "edges": [_edge_doc(u, v, d) for u, v, d in G.edges(data=True)],
        "communities": communities,
        "documents": _documents(cfg, all_md, conv, manifest),
        "stats": {
            "files": files_count if files_count is not None else len(all_md),
            "converted": len(all_md),
            "chunks": len(all_chunks),
            "unique_chunks": len(unique_chunks),
            "chunks_truncated": truncated,
            "chunks_skipped_low_value": skipped_low_value,
            "entities": G.number_of_nodes(),
            "relations": G.number_of_edges(),
            "communities": len(communities),
            "embed_mode": embedder.mode,
            # v2 is fully deterministic and model-free: extraction, summaries and
            # embeddings all use the on-device classical/hash path. The mode is a
            # constant descriptor (no LLM/accurate/fast distinction remains).
            "mode": "deterministic",
        },
    }
    # WP-123b: best-effort provenance spans — locate each fact in its source .md and stamp
    # codepoint offsets (additive; recall/vectors/bm25 are built from fact TEXT only, so this
    # changes graph.json alone). Deterministic → graph.json stays byte-identical run-to-run.
    _attach_fact_spans(cfg, graph_doc)
    # Recall vectors: one card per entity + one per community summary. Persist these
    # BEFORE the graph so graph.json — the presence signal recall/overview key off —
    # only lands once its matching vectors are in place (shrinks the torn-store window;
    # the load-time length guard covers the rest). When a digest yields no recall units,
    # clear any stale vectors so recall (no_memory) and overview never disagree.
    units, texts = _recall_units(graph_doc)
    matrix = embedder.embed(texts) if texts else None
    if matrix is not None and len(units):
        store.save_vectors(cfg, matrix, units)
        # R-13: persist the deterministic pre-tokenised BM25 index from the SAME units,
        # so recall ranks without re-tokenising the whole corpus on every query.
        store.save_bm25_index(cfg, _build_bm25_index(units))
    else:
        store.clear_vectors(cfg)
    store.save_graph(cfg, graph_doc)

    # Materialise human-facing outputs.
    render.write_memory_md(cfg, graph_doc)
    render.write_doc_memories(cfg, graph_doc, G)

    result = {
        "status": "ok",
        "project": cfg.project,
        # seconds is transient (tool result only) — never persisted, so artifacts
        # stay byte-identical across runs of the same corpus.
        "stats": {**graph_doc["stats"], "seconds": round(time.time() - t0, 1)},
        "outputs": {
            "graph": str(cfg.graph_path),
            "memory_md": str(cfg.memory_md),
            "memory_dir": str(cfg.memory_dir),
        },
        "conversion": _conv_tally(conv),
    }
    return result


def _synopsis(communities: list[dict]) -> str:
    if not communities:
        return "No content digested yet."
    # Deterministic synopsis (model-free): the theme labels joined into one line.
    return ("This memory covers " + str(len(communities)) + " themes: "
            + ", ".join(c["label"] for c in communities[:8]) + ".")


def _build_bm25_index(units: list[dict]) -> dict:
    """Deterministic pre-tokenised BM25 index (R-13): ``docs[i]`` is the token list for
    recall-unit ``i``, produced by the SAME tokeniser recall uses on the fly, so the
    cache can never rank differently. Pure function of the (deterministic) units → the
    JSON is byte-identical across runs/OSes and joins the determinism contract."""
    from .recall import _unit_doc_tokens
    docs = [_unit_doc_tokens(u) for u in units]
    return {"version": 1, "tokenizer": "nfc+bn+len>1+label*2",
            "count": len(docs), "docs": docs}


def _normalize_with_map(text: str) -> tuple[str, list[int]]:
    """Lower-case + whitespace-collapsed copy of ``text`` plus a parallel list mapping each
    normalised character back to its ORIGINAL codepoint index. Lets a whitespace-/case-
    tolerant substring match be translated to exact offsets in the source .md (a fact that
    wraps across line breaks in the .md still matches its single-line stored form)."""
    chars: list[str] = []
    pos: list[int] = []
    prev_space = False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space or not chars:       # collapse runs; drop leading whitespace
                continue
            chars.append(" "); pos.append(i); prev_space = True
        else:
            chars.append(ch.lower()); pos.append(i); prev_space = False
    return "".join(chars), pos


def _attach_fact_spans(cfg: Config, graph_doc: dict) -> None:
    """WP-123b (Theme-Z): stamp each locatable fact with a best-effort provenance
    ``span:{doc,start,end}`` — codepoint offsets into the digest-time ``.md``. Pure post-pass
    over ``graph_doc`` (mutates the shared fact recs in place); deterministic. A fact whose
    stored text can't be found verbatim in its .md (e.g. PII-redacted or Bengali-reorder-
    normalised) simply gets no span — honest best-effort, paired with the per-doc ``md_sha``
    fingerprint on ``documents[]`` so a consumer can detect staleness."""
    cache: dict[str, tuple[str, list[int]] | None] = {}

    def _index(doc: str):
        if doc in cache:
            return cache[doc]
        try:
            md = (cfg.markdown_dir / (doc + ".md")).read_text(encoding="utf-8", errors="replace")
            cache[doc] = _normalize_with_map(md)
        except OSError:
            cache[doc] = None
        return cache[doc]

    seen: set[int] = set()
    for node in graph_doc.get("nodes", []):
        for f in node.get("facts", []):
            if id(f) in seen:                 # facts are shared across the entities they name
                continue
            seen.add(id(f))
            doc = f.get("doc")
            if not doc:
                continue
            idx = _index(doc)
            if not idx:
                continue
            norm_md, pos = idx
            nf = _normalize_with_map(f.get("text", ""))[0]
            if len(nf) < 8:                   # too short to locate unambiguously
                continue
            at = norm_md.find(nf)
            if at < 0:
                continue
            f["span"] = {"doc": doc, "start": pos[at], "end": pos[at + len(nf) - 1] + 1}


def _edge_doc(u: str, v: str, d: dict) -> dict:
    """Serialise one graph edge. WP-120 (Theme-Z) adds a deterministic, DIRECTED
    ``relations`` list (typed verb relations as ``{type, from, to}`` by entity id) when the
    edge carries any — purely additive; the undirected backbone (source/target/weight/
    labels) is unchanged, and a co-occurrence-only edge omits the field entirely."""
    edge = {"source": u, "target": v, "weight": d["weight"],
            "labels": sorted(d.get("labels", []))}
    rels = d.get("rels")
    if rels:
        edge["relations"] = [{"type": rt, "from": fr, "to": to}
                             for rt, fr, to in sorted(rels)]
    return edge


def _recall_units(graph_doc: dict) -> tuple[list[dict], list[str]]:
    units, texts = [], []
    nodes = {n["id"]: n for n in graph_doc["nodes"]}
    for c in graph_doc["communities"]:
        if c.get("summary"):
            units.append({"kind": "theme", "ref": c["id"], "label": c["label"],
                          "text": c["summary"]})
            texts.append(f"{c['label']}: {c['summary']}")
    for nid, n in nodes.items():
        facts = "; ".join(f["text"] for f in n.get("facts", [])[:5])
        card = f"{n['label']} ({n.get('type','other')}). {facts}".strip()
        # `type` (v3.1) lets recall filter entity hits by kind (person/org/place/…). It
        # rides the meta sidecar only — not the bm25 tokens or the embedded text — so
        # graph.json / vectors.npz / bm25_index.json stay byte-identical (determinism
        # gate untouched); an old store without it simply can't be type-filtered until
        # the next re-digest.
        units.append({"kind": "entity", "ref": nid, "label": n["label"],
                      "type": n.get("type", "other"),
                      "text": card, "docs": n.get("docs", [])})
        texts.append(card)
    return units, texts


def _low_value(text: str) -> bool:
    """True for degenerate, near-zero-information passages — repetitive filler OR
    numeric/cell data dumps (beneficiary-survey spreadsheet rows), which carry almost
    no narrative knowledge but huge chunk volume.
    """
    words = text.split()
    if len(words) < 40:
        return False
    uniq = len(set(w.lower() for w in words))
    if uniq / len(words) < 0.12:                       # repetitive filler
        return True
    # Beneficiary roster: tabular structure (pipes) together with multiple long digit-runs
    # (phone/NID numbers, Latin or Bengali numerals) — survey-export rows that carry no
    # narrative knowledge but huge volume, and leak PII. Gate on BOTH so a legitimate
    # prose-bearing markdown table (few numbers) survives.
    from .extract import _PII_DIGITS_RE
    digit_runs = len(_PII_DIGITS_RE.findall(text))
    pipes = text.count("|")
    if (pipes >= 4 and digit_runs >= 2) or digit_runs >= 5:
        return True
    # Binary / metadata dump: embedded colour profiles, XMP packets, base16 blobs from
    # design files (.eps/.indd/.ai) leak as long hex tokens or XMP namespace tags — data,
    # not prose.
    if any(t in text for t in ("<xapG:", "<x:xmpmeta", "xmlns:rdf", "<rdf:")):
        return True
    if sum(1 for w in words if len(w) >= 12 and _HEXISH.fullmatch(w)) >= 2:
        return True
    # Data/table dump: a window that is mostly numbers/codes (e.g. a spreadsheet grid)
    # is data, not prose. >55% numeric-ish tokens → skip.
    numeric = sum(1 for w in words if _NUMERICISH.fullmatch(w))
    return numeric / len(words) > 0.55


def _auto_extract_workers(cfg: Config) -> int:
    if cfg.extract_workers > 0:
        return cfg.extract_workers
    from .platform import memory_gb
    gb = memory_gb()
    # Classical regex extraction is cheap (no model); this mainly bounds peak RAM from
    # holding many chunks in flight. Override with MTA_EXTRACT_WORKERS.
    return 1 if gb < 16 else (2 if gb < 48 else 3)


def _reset_project(cfg: Config) -> None:
    """Wipe a project's converted corpus and derived memory (for reset=True)."""
    import shutil
    for path in (cfg.markdown_dir, cfg.memory_dir, cfg.unpack_dir):
        shutil.rmtree(path, ignore_errors=True)
    for f in (cfg.graph_path, cfg.vectors_path,
              cfg.vectors_path.with_suffix(".json"), cfg.bm25_index_path,
              cfg.manifest_path, cfg.memory_md):
        try:
            f.unlink()
        except OSError:
            pass


def _parse_md_header(md: Path) -> tuple[str, str]:
    """Recover (source name, method) from the provenance comment we write."""
    try:
        first = md.read_text(encoding="utf-8", errors="replace").splitlines()[0]
    except (OSError, IndexError):
        first = ""
    src, method = md.name[:-3] if md.name.endswith(".md") else md.name, ""
    if first.startswith("<!-- source:"):
        body = first.strip("<!-> ")
        for part in body.split("·"):
            part = part.strip()
            if part.startswith("source:"):
                src = part[len("source:"):].strip()
            elif part.startswith("method:"):
                method = part[len("method:"):].strip()
    return src, method


def _documents(cfg: Config, all_md: list[Path], conv: list[dict],
               manifest: dict | None = None) -> list[dict]:
    """Document manifest across the FULL corpus, plus this call's non-ok files.

    ``output`` is stored as a basename (not an absolute path) so a copied memory
    bundle stays portable across machines / MTA_HOME locations. ``sha256`` (schema v2) is
    the source file's content hash — portable (not machine-specific) and deterministic, so
    it joins the byte-identity contract and powers cross-machine diff/merge. It is looked up
    from the incremental manifest by output name; absent for a document whose source hash
    is unknown (e.g. a v1 store migrated in place).
    """
    out_to_sha = {e["out"]: e["sha256"]
                  for e in (manifest or {}).values()
                  if isinstance(e, dict) and e.get("out") and e.get("sha256")}
    docs = []
    ok_names: set[str] = set()
    for md in all_md:
        src, method = _parse_md_header(md)
        md_sha = None
        try:
            full = md.read_text(encoding="utf-8", errors="replace")
            body = full.split("-->", 1)[-1].lstrip("\n") if full.startswith("<!-- source:") else full
            chars = len(body)
            # WP-123b: fingerprint of the converted .md the fact spans index into, so a
            # consumer can detect a stale span after a re-conversion. Deterministic.
            md_sha = hashlib.sha1(full.encode("utf-8")).hexdigest()[:12]
        except OSError:
            chars = 0
        ok_names.add(src)
        doc = {"name": src, "output": md.name, "status": "ok",
               "method": method, "chars": chars}
        sha = out_to_sha.get(md.name)
        if sha:
            doc["sha256"] = sha
        if md_sha:
            doc["md_sha"] = md_sha
        docs.append(doc)
    for c in conv:  # surface files that failed/were unsupported this run (no dup)
        if c.get("status") != "ok":
            nm = Path(c.get("source", "")).name
            if nm in ok_names:
                continue
            docs.append({"name": nm, "output": None, "status": c.get("status"),
                         "method": c.get("method", ""), "chars": 0})
    return docs


def _conv_tally(conv: list[dict]) -> dict:
    tally: dict[str, int] = {}
    for c in conv:
        tally[c.get("status", "?")] = tally.get(c.get("status", "?"), 0) + 1
    return tally
