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
import tempfile
from pathlib import Path

import numpy as np

from .config import Config


def _atomic_write_text(path: Path, text: str) -> None:
    """Write text durably: temp file in the same dir → fsync → os.replace.

    Guarantees a reader never sees a half-written file, and an interrupt
    (crash/power loss) leaves the *previous* valid file intact rather than a
    truncated one. utf-8 explicit (Windows defaults to cp1252).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_graph(cfg: Config, graph_doc: dict) -> None:
    cfg.ensure_dirs()
    _atomic_write_text(cfg.graph_path, json.dumps(graph_doc, indent=2, ensure_ascii=False))


# Bump when the on-disk graph schema changes incompatibly.
SCHEMA_VERSION = 1


def load_graph(cfg: Config) -> dict | None:
    if not cfg.graph_path.exists():
        return None
    try:
        doc = json.loads(cfg.graph_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    # Refuse to mis-read a future, incompatible schema rather than silently
    # returning garbage; older/equal versions load fine. graph.json is user-
    # editable, so coerce the version defensively (a non-numeric value won't crash).
    if isinstance(doc, dict):
        try:
            if int(doc.get("version", 1)) > SCHEMA_VERSION:
                return None
        except (TypeError, ValueError):
            return None
    return doc


def save_vectors(cfg: Config, matrix: np.ndarray, meta: list[dict]) -> None:
    cfg.ensure_dirs()
    # Atomic: write the .npz to a temp handle (so np doesn't append .npz to a
    # temp name), then os.replace; write the sidecar JSON atomically too.
    tmp = cfg.vectors_path.with_name(cfg.vectors_path.name + ".tmp")
    with open(tmp, "wb") as f:
        np.savez_compressed(f, matrix=matrix.astype(np.float32))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, cfg.vectors_path)
    _atomic_write_text(cfg.vectors_path.with_suffix(".json"),
                       json.dumps(meta, ensure_ascii=False))


def load_vectors(cfg: Config) -> tuple[np.ndarray, list[dict]] | None:
    meta_path = cfg.vectors_path.with_suffix(".json")
    if not cfg.vectors_path.exists() or not meta_path.exists():
        return None
    try:
        with np.load(cfg.vectors_path) as data:
            matrix = data["matrix"]
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return matrix, meta
    except (OSError, ValueError, KeyError, json.JSONDecodeError):
        return None


def delete_project(cfg: Config) -> dict:
    """Delete a project's entire memory (graph, markdown, vectors, mind map)."""
    import shutil
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
