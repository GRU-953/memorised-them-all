"""Persistence — the graph is the source of truth; vectors power recall.

Per project we keep:
  graph.json       canonical nodes, edges, communities, layered summaries, stats
  vectors.npz      L2-normalised embedding matrix for recall units
  vectors.json     parallel metadata for each row (kind, text, provenance)

JSON is human-readable and diff-friendly; the vector store is compact binary.
Everything lives under ``MTA_HOME/projects/<project>`` so memories are reusable
and never collide.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

try:
    import numpy as np
    _HAVE_NUMPY = True
except Exception:  # noqa: BLE001 — numpy is optional (WP-181a): the recall path is meta-only,
    np = None      # so a numpy-free core still digests (no vectors.npz) and recalls (sidecar).
    _HAVE_NUMPY = False

from .config import Config


# Single shared crash-safe writer ([C2]); re-exported under the legacy name so
# store/render callers are unchanged.
from ._io import atomic_write_text as _atomic_write_text  # noqa: E402


def save_graph(cfg: Config, graph_doc: dict) -> None:
    cfg.ensure_dirs()
    # If the existing store is a NEWER, incompatible schema than this build, back
    # it up before overwriting so a version downgrade can't silently destroy it.
    if cfg.graph_path.exists():
        raw = ""
        try:
            raw = cfg.graph_path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        if raw.strip():
            try:
                existing = json.loads(raw)
                if isinstance(existing, dict) and int(existing.get("version", 1)) > SCHEMA_VERSION:
                    _backup_store(cfg, f"pre-overwrite-v{int(existing.get('version', 1))}")
            except (json.JSONDecodeError, TypeError, ValueError):
                # Present but unparseable (torn/half-written, or a "cleaner" corrupted it):
                # back it up before overwriting so a once-valid memory is never silently lost.
                _backup_store(cfg, "pre-overwrite-corrupt")
    _atomic_write_text(cfg.graph_path, json.dumps(graph_doc, indent=2, ensure_ascii=False))


# Bump when the on-disk graph schema changes incompatibly.
SCHEMA_VERSION = 1

# Registry of forward migrations: from_version -> fn(doc) -> doc that upgrades a
# store from `from_version` to the next version. Empty today (only v1 exists); a
# future incompatible schema bump registers its step here. Migrations are pure.
_MIGRATIONS: dict = {}


def migrate_doc(doc: dict) -> dict:
    """Forward-migrate a store doc toward SCHEMA_VERSION using the registry.

    Pure (writes nothing) → safe to call under a shared read lock. If no step
    exists for a gap, the doc is returned as-is (still readable).
    """
    try:
        v = int(doc.get("version", 1))
    except (TypeError, ValueError):
        return doc
    steps = 0
    while v < SCHEMA_VERSION and v in _MIGRATIONS and steps < 100:
        doc = _MIGRATIONS[v](doc)
        try:
            v = int(doc.get("version", v + 1))
        except (TypeError, ValueError):
            break
        steps += 1
    return doc


def _backup_store(cfg: Config, reason: str) -> Path | None:
    """Copy the on-disk store into project_dir/backups/<ts>-<reason>/ so an
    incompatible overwrite (e.g. a version downgrade) can never lose data.
    Best-effort; never raises into the caller.
    """
    import time
    try:
        dest = cfg.project_dir / "backups" / f"{time.strftime('%Y%m%d-%H%M%S')}-{reason}"
        dest.mkdir(parents=True, exist_ok=True)
        for src in (cfg.graph_path, cfg.vectors_path,
                    cfg.vectors_path.with_suffix(".json"), cfg.bm25_index_path,
                    cfg.memory_md):
            if src.exists():
                shutil.copy2(src, dest / src.name)
        print(f"[mta] backed up existing memory to {dest}", file=sys.stderr)
        return dest
    except OSError:
        return None


def load_graph(cfg: Config) -> dict | None:
    if not cfg.graph_path.exists() or _too_big(cfg.graph_path, cfg):
        return None
    try:
        doc = json.loads(cfg.graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(doc, dict):
        return None
    try:
        v = int(doc.get("version", 1))
    except (TypeError, ValueError):
        return None  # corrupt / non-numeric version → don't trust the file
    if v < SCHEMA_VERSION:
        # Forward-migrate older stores IN MEMORY so old memories stay
        # read-recallable after an upgrade (disk is rewritten at the next digest).
        doc = migrate_doc(doc)
    # A *newer* store than this build understands is no longer dropped (that
    # previously surfaced as "no memory" and let a digest overwrite it). Return it
    # best-effort so recall still works; save_graph() backs it up before any
    # overwrite, so a version downgrade can't silently destroy it (R6 / LIFE-03).
    return doc


def save_vectors(cfg: Config, matrix, meta: list[dict]) -> None:
    cfg.ensure_dirs()
    # The embedding matrix (vectors.npz) is a numpy-only legacy artifact — write it FIRST
    # (atomic; the same order as before, so numpy-present stores are byte-unchanged) when
    # numpy is available and we actually have an ndarray. With numpy absent it is simply
    # skipped: recall never reads the matrix (R-15), so a numpy-free core still works.
    if _HAVE_NUMPY and matrix is not None and isinstance(matrix, np.ndarray):
        tmp = cfg.vectors_path.with_name(cfg.vectors_path.name + ".tmp")
        try:
            with open(tmp, "wb") as f:
                np.savez_compressed(f, matrix=matrix.astype(np.float32))
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, cfg.vectors_path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    # The meta sidecar (vectors.json) is ALWAYS written, numpy-free: recall ranks from it
    # and (WP-181a) gates on it, so it is the real presence signal for the recall store.
    _atomic_write_text(cfg.vectors_path.with_suffix(".json"),
                       json.dumps(meta, ensure_ascii=False))


def clear_vectors(cfg: Config) -> None:
    """Remove the recall vector store (matrix + sidecar).

    Called when a digest yields no recall units, so stale vectors from a previous
    digest can't linger and make ``recall`` (which would mis-key off old refs) and
    ``memory_overview`` disagree. Best-effort and idempotent."""
    for path in (cfg.vectors_path, cfg.vectors_path.with_suffix(".json"),
                 cfg.bm25_index_path):
        try:
            path.unlink()
        except OSError:
            pass


def _too_big(path: Path, cfg: Config) -> bool:
    """True if a JSON store on the recall path exceeds the file-size cap (``MTA_MAX_FILE_MB``,
    default 200 MB; 0 disables). These files are user-editable / copied between machines, so a
    hostile or accidental multi-GB ``bm25_index.json``/``vectors.json``/``graph.json`` would
    OOM the reader — refuse to load it (→ ``no_memory``) rather than ``json.loads`` it blindly.
    Legitimate stores are far under the cap, so this never trips in normal use."""
    cap = getattr(cfg, "max_file_mb", 0) or 0
    if cap <= 0:
        return False
    try:
        return path.stat().st_size > cap * 1024 * 1024
    except OSError:
        return False


def load_meta(cfg: Config) -> list[dict] | None:
    """Load ONLY the recall-unit metadata (``vectors.json``) — never the ``vectors.npz``
    matrix (R-15). BM25 recall ranks from text/labels in the meta, so materialising the
    embedding matrix every query was pure waste.

    Gates on the **sidecar alone** (WP-181a): a numpy-free core writes no ``vectors.npz``,
    so a bare ``vectors.json`` is now a *valid* store, not a torn one — the sidecar (plus
    ``graph.json``, which a digest writes last) is the presence signal. The sidecar must
    parse to a NON-EMPTY list; an empty/garbage/oversized sidecar reads as no_memory (a
    real digest calls ``clear_vectors`` when there are no units, so an empty sidecar only
    arises from a torn/hand-edited store). The matrix body is never read or decompressed,
    so a malicious/pickled ``.npz`` can't even be touched on the recall path."""
    meta_path = cfg.vectors_path.with_suffix(".json")
    if not meta_path.exists():
        return None
    if _too_big(meta_path, cfg):
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    # A non-list, or an EMPTY list, is treated as no memory: a real digest never persists
    # an empty sidecar (it calls clear_vectors when there are no units), so an empty/wrong
    # meta only arises from a torn or hand-edited store — recall should decline, not "ok"
    # with zero hits.
    return meta if isinstance(meta, list) and meta else None


def save_bm25_index(cfg: Config, index_doc: dict) -> None:
    """Persist the deterministic, pre-tokenised BM25 index (R-13) next to the vectors.
    Written through the same crash-safe atomic writer (``newline=""`` → byte-identical
    across OSes), so it joins the determinism contract like ``graph.json``."""
    cfg.ensure_dirs()
    _atomic_write_text(cfg.bm25_index_path,
                       json.dumps(index_doc, ensure_ascii=False, indent=2))


def load_bm25_index(cfg: Config) -> dict | None:
    """Load the BM25 index cache, or ``None`` if absent/torn/garbage. Structural
    validation of the per-unit token lists lives at the recall call site, so any
    corrupt cache degrades to the on-the-fly tokeniser rather than crashing recall."""
    if not cfg.bm25_index_path.exists() or _too_big(cfg.bm25_index_path, cfg):
        return None
    try:
        doc = json.loads(cfg.bm25_index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return doc if isinstance(doc, dict) else None


def clear_bm25_index(cfg: Config) -> None:
    """Remove the BM25 index cache (idempotent, best-effort)."""
    try:
        cfg.bm25_index_path.unlink()
    except OSError:
        pass


def load_vectors(cfg: Config):
    """Load the embedding matrix + meta (the legacy numpy path; recall does NOT use this —
    it reads ``load_meta`` only). Returns ``None`` without numpy or without a ``.npz``."""
    if not _HAVE_NUMPY:
        return None
    meta_path = cfg.vectors_path.with_suffix(".json")
    if not cfg.vectors_path.exists() or not meta_path.exists():
        return None
    try:
        # allow_pickle=False explicitly (don't rely on the NumPy default): the
        # vector store is untrusted (user-editable / copied between machines), and
        # a pickled .npz must never be able to execute code on load (SEC-03).
        with np.load(cfg.vectors_path, allow_pickle=False) as data:
            matrix = data["matrix"]
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a corrupt/torn store (incl. zipfile.BadZipFile from a
        return None    # truncated .npz) must read as "no memory", never crash recall (SEC/LIFE).
    # Consistency guard: vectors.npz (matrix rows) and vectors.json (per-row meta)
    # are two separate atomic replaces, so a crash between them can desync row count
    # from meta length. Treat a torn pair as "no memory" rather than letting recall
    # IndexError or mis-attribute a row to the wrong unit.
    if not isinstance(meta, list) or int(matrix.shape[0]) != len(meta):
        return None
    return matrix, meta


def delete_project(cfg: Config) -> dict:
    """Delete a project's entire memory (graph, converted Markdown, summaries, notes).

    Takes the project's exclusive write lock so a `forget` can't race a digest
    (the lock file lives under state/locks/, not the project dir, so it survives
    the rmtree). See locks.py.
    """
    import shutil

    from . import locks
    with locks.write_lock(cfg):
        if not cfg.project_dir.exists():
            return {"status": "not_found", "project": cfg.project}
        shutil.rmtree(cfg.project_dir, ignore_errors=True)
    return {"status": "ok", "project": cfg.project, "deleted": True}


def list_projects(cfg: Config) -> list[dict]:
    out: list[dict] = []
    pdir = cfg.projects_dir
    if not pdir.exists():
        return out
    for child in sorted(pdir.iterdir()):
        if not child.is_dir():
            continue
        gp = child / "graph.json"
        info = {"project": child.name, "has_graph": gp.exists()}
        if gp.exists():
            try:
                doc = json.loads(gp.read_text(encoding="utf-8"))
                info["stats"] = doc.get("stats", {})
            except (json.JSONDecodeError, OSError):
                pass
        out.append(info)
    return out
