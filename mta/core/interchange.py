"""Memory interchange (v3): diff · import · merge.

Three project-level operations that make memories portable and composable, all offline,
deterministic, model-free and **token-free** (every result is a small dict — never document
contents):

* ``diff_memory``   — read-only comparison of two project memories (documents added/removed/
  changed by portable content hash, entities/themes only-in-each, stats delta).
* ``import_memory`` — restore a previously-exported bundle into a project (recall-ready
  snapshot; backs up any existing store first).
* ``merge_memory``  — combine several projects' converted corpora into one new project and
  rebuild a single coherent memory (reuses the deterministic digest rebuild).
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import shutil
import time
from pathlib import Path

from . import locks, store
from .config import Config

_MAX_LIST = 50   # cap any echoed name/label list so a diff stays token-free

# Files that make up a portable export bundle (mirrors render.export_bundle). The
# incremental manifest is intentionally absent — it holds machine-local absolute paths.
_BUNDLE_FILES = ("graph.json", "vectors.npz", "vectors.json", "bm25_index.json", "memory.md")


def _project_cfg(cfg: Config, name: str) -> Config:
    """A sibling Config for another project under the same home (paths only)."""
    return dataclasses.replace(cfg).with_project(name)


def _index(doc: dict) -> dict:
    """Index a graph doc for comparison: ok-documents by name → sha256, entity labels (by
    lowercased key → display label), theme labels, and the stats block."""
    docs: dict[str, str | None] = {}
    for d in doc.get("documents", []):
        if d.get("status") != "ok":
            continue
        name = d.get("name") or d.get("output") or ""
        if name:
            docs[name] = d.get("sha256")
    ents: dict[str, str] = {}
    for n in doc.get("nodes", []):
        lbl = str(n.get("label", "")).strip()
        if lbl:
            ents.setdefault(lbl.lower(), lbl)
    themes: dict[str, str] = {}
    for c in doc.get("communities", []):
        lbl = str(c.get("label", "")).strip()
        if lbl:
            themes.setdefault(lbl.lower(), lbl)
    return {"docs": docs, "ents": ents, "themes": themes, "stats": doc.get("stats", {})}


def diff_memory(cfg: Config, other: str, project: str | None = None) -> dict:
    """Compare two project memories (read-only, token-free). Documents match by portable
    content hash (sha256) when both stores carry it — so a renamed-but-identical file isn't
    flagged changed, and a same-name-different-content file is. Lists are capped."""
    a_cfg = _project_cfg(cfg, project or cfg.project)
    b_cfg = _project_cfg(cfg, other)
    if a_cfg.project == b_cfg.project:
        return {"status": "error", "error": "diff needs two different projects"}
    with locks.read_lock(a_cfg):
        a = store.load_graph(a_cfg)
    with locks.read_lock(b_cfg):
        b = store.load_graph(b_cfg)
    if a is None:
        return {"status": "no_memory", "project": a_cfg.project}
    if b is None:
        return {"status": "no_memory", "project": b_cfg.project}
    ai, bi = _index(a), _index(b)

    a_docs, b_docs = set(ai["docs"]), set(bi["docs"])
    common = a_docs & b_docs
    changed = sorted(n for n in common
                     if ai["docs"][n] and bi["docs"][n] and ai["docs"][n] != bi["docs"][n])

    def _cap(keys, display=None):
        keys = sorted(keys)
        names = [display[k] for k in keys] if display else keys
        return {"count": len(keys), "names": names[:_MAX_LIST]}

    a_e, b_e = set(ai["ents"]), set(bi["ents"])
    a_t, b_t = set(ai["themes"]), set(bi["themes"])
    return {
        "status": "ok", "a": a_cfg.project, "b": b_cfg.project,
        "documents": {
            "only_in_a": _cap(a_docs - b_docs),
            "only_in_b": _cap(b_docs - a_docs),
            "changed": {"count": len(changed), "names": changed[:_MAX_LIST]},
            "common": len(common),
        },
        "entities": {
            "a_total": len(a_e), "b_total": len(b_e), "shared": len(a_e & b_e),
            "only_in_a": _cap(a_e - b_e, ai["ents"]),
            "only_in_b": _cap(b_e - a_e, bi["ents"]),
        },
        "themes": {
            "a_total": len(a_t), "b_total": len(b_t),
            "only_in_a": _cap(a_t - b_t, ai["themes"]),
            "only_in_b": _cap(b_t - a_t, bi["themes"]),
        },
        "stats": {"a": ai["stats"], "b": bi["stats"]},
    }


def import_memory(cfg: Config, src: str, project: str | None = None) -> dict:
    """Import a previously-exported bundle directory into a project, making it recall-ready
    on this machine. **Recall-only snapshot:** the raw ``markdown/`` corpus is not part of an
    export bundle, so re-running ``digest`` on this project would rebuild from an empty corpus
    and replace the import — treat an imported project as a snapshot. Any existing store is
    backed up first. Token-free."""
    target = _project_cfg(cfg, project or cfg.project)
    src_path = Path(src).expanduser()
    if not src_path.is_dir():
        return {"status": "error", "error": f"not a directory: {src_path}"}
    gp = src_path / "graph.json"
    if not gp.exists():
        return {"status": "error", "error": "bundle has no graph.json (not an export bundle)"}
    try:
        doc = json.loads(gp.read_text(encoding="utf-8"))
        if not isinstance(doc, dict) or "nodes" not in doc:
            raise ValueError
    except (OSError, ValueError, json.JSONDecodeError):
        return {"status": "error", "error": "bundle graph.json is not a valid memory graph"}

    with locks.write_lock(target):
        target.ensure_dirs()
        if target.graph_path.exists():
            store._backup_store(target, "pre-import")
        imported = []
        for name in _BUNDLE_FILES:
            sp = src_path / name
            if sp.is_file() and not sp.is_symlink():
                shutil.copy2(sp, target.project_dir / name)
                imported.append(name)
        mem = src_path / "memory"
        if mem.is_dir():
            target.memory_dir.mkdir(parents=True, exist_ok=True)
            for f in sorted(mem.glob("*.md")):       # only the note files, never symlinks
                if f.is_file() and not f.is_symlink():
                    shutil.copy2(f, target.memory_dir / f.name)
            imported.append("memory/")
        # an imported snapshot has no source manifest → drop any stale one so a later digest
        # doesn't think files are "unchanged".
        store.clear_manifest(target)
    return {"status": "ok", "project": target.project, "from": str(src_path),
            "imported": imported,
            "note": "recall-ready snapshot; re-digesting this project replaces it"}


def merge_memory(cfg: Config, sources: list[str], into: str) -> dict:
    """Merge the converted corpora of several source projects into a NEW project ``into`` and
    rebuild one coherent memory — deterministic and model-free, exactly as if the sources'
    files had been digested together. Byte-identical source documents are merged once
    (content-hash dedup); same-name/different-content files are kept under distinct names.
    Any existing ``into`` store is backed up and replaced. Token-free."""
    from .digest import _rebuild_from_markdown, _reset_project

    if not isinstance(sources, list) or not sources or not all(
            isinstance(s, str) and s.strip() for s in sources):
        return {"status": "error", "error": "'sources' must be a non-empty list of project names"}
    if not isinstance(into, str) or not into.strip():
        return {"status": "error", "error": "'into' must be a non-empty project name"}

    into_cfg = _project_cfg(cfg, into)
    src_cfgs = [_project_cfg(cfg, s) for s in sources]
    missing = [s.project for s in src_cfgs
               if not (s.markdown_dir.exists() and any(s.markdown_dir.glob("*.md")))]
    if missing:
        return {"status": "error",
                "error": f"source project(s) have no digested corpus: {sorted(set(missing))}"}

    # Gather the union of source markdown BEFORE touching `into` — so merging A,B → A is
    # safe — deduping byte-identical documents and disambiguating name collisions.
    seen_sha: set[str] = set()
    name_sha: dict[str, str] = {}
    gathered: list[tuple[str, bytes]] = []
    for scfg in src_cfgs:
        for md in sorted(scfg.markdown_dir.glob("*.md")):
            try:
                data = md.read_bytes()
            except OSError:
                continue
            sha = hashlib.sha256(data).hexdigest()
            if sha in seen_sha:
                continue                                   # identical doc already merged
            seen_sha.add(sha)
            name = md.name
            if name_sha.get(name, sha) != sha:
                name = f"{md.stem}.{sha[:8]}{md.suffix}"   # same name, different content
            name_sha[name] = sha
            gathered.append((name, data))

    t0 = time.time()
    with locks.write_lock(into_cfg):
        if into_cfg.graph_path.exists():
            store._backup_store(into_cfg, "pre-merge")
        _reset_project(into_cfg)                           # fresh corpus for the merge target
        into_cfg.ensure_dirs()
        for name, data in gathered:
            (into_cfg.markdown_dir / name).write_bytes(data)
        result = _rebuild_from_markdown(into_cfg, t0, files_count=len(gathered))
    result["merge"] = {"into": into_cfg.project,
                       "sources": [s.project for s in src_cfgs],
                       "documents": len(gathered)}
    return result
