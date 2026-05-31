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
from pathlib import Path

import numpy as np

from .config import Config


def save_graph(cfg: Config, graph_doc: dict) -> None:
    cfg.ensure_dirs()
    cfg.graph_path.write_text(json.dumps(graph_doc, indent=2, ensure_ascii=False),
                              encoding="utf-8")


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
    # returning garbage; older/equal versions load fine.
    if isinstance(doc, dict) and doc.get("version", 1) > SCHEMA_VERSION:
        return None
    return doc


def save_vectors(cfg: Config, matrix: np.ndarray, meta: list[dict]) -> None:
    cfg.ensure_dirs()
    np.savez_compressed(cfg.vectors_path, matrix=matrix.astype(np.float32))
    cfg.vectors_path.with_suffix(".json").write_text(
        json.dumps(meta, ensure_ascii=False), encoding="utf-8")


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
