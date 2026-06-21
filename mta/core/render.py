"""Materialise human-facing memory: memory.md and per-document notes.

All outputs are plain files on disk. ``memory.md`` is the compact, layered digest
Claude reads (synopsis → themes → key facts → index); per-document notes make the
memory exportable and browseable.
"""
from __future__ import annotations

import shutil
from collections import defaultdict
from pathlib import Path

from .config import Config
from .store import _atomic_write_text   # temp → fsync → os.replace (crash-safe)


def write_memory_md(cfg: Config, doc: dict) -> Path:
    s = doc.get("stats", {})
    lines = [
        f"# Memory — {doc['project']}", "",
        f"> Generated locally by **Memorised them All**. "
        f"{s.get('files', 0)} files · {s.get('entities', 0)} entities · "
        f"{s.get('relations', 0)} relations · {s.get('communities', 0)} themes · "
        f"recall: BM25 lexical.", "",
        "## Overview", "", doc.get("synopsis", "").strip() or "_(empty)_", "",
        "## Themes", "",
    ]
    nodes = {n["id"]: n for n in doc["nodes"]}
    for c in doc["communities"]:
        member_labels = [nodes[m]["label"] for m in c["members"][:8] if m in nodes]
        lines.append(f"### {c['label']}")
        if c.get("summary"):
            lines.append(c["summary"])
        if member_labels:
            lines.append("")
            lines.append("**Entities:** " + ", ".join(member_labels))
        lines.append("")

    # Key facts (top entities by salience).
    top = sorted(doc["nodes"], key=lambda n: n.get("count", 0), reverse=True)[:25]
    lines += ["## Key facts", ""]
    for n in top:
        facts = n.get("facts", [])
        if not facts:
            continue
        lines.append(f"- **{n['label']}** — {facts[0]['text']}"
                     + (f" _(source: {facts[0]['doc']})_" if facts[0].get("doc") else ""))
    lines += ["", "## Documents", ""]
    for d in doc.get("documents", []):
        if d.get("status") == "ok":
            lines.append(f"- `{Path(d['name']).name}` — {d.get('chars', 0)} chars "
                         f"(via {d.get('method', '?')})")
    lines.append("")
    _atomic_write_text(cfg.memory_md, "\n".join(lines))
    return cfg.memory_md


def write_doc_memories(cfg: Config, doc: dict, _g=None) -> int:
    """One memory note per source document, grouping its entities and facts."""
    cfg.memory_dir.mkdir(parents=True, exist_ok=True)
    by_doc_facts: dict[str, list[dict]] = defaultdict(list)
    by_doc_entities: dict[str, set] = defaultdict(set)
    for n in doc["nodes"]:
        for d in n.get("docs", []):
            by_doc_entities[d].add(n["label"])
        for f in n.get("facts", []):
            if f.get("doc"):
                by_doc_facts[f["doc"]].append({"entity": n["label"], **f})

    count = 0
    for d in doc.get("documents", []):
        if d.get("status") != "ok":
            continue
        name = Path(d["name"]).name        # human-readable title for the note heading
        key = _doc_key(d)                  # collision-free, length-clamped output stem
        ents = sorted(by_doc_entities.get(key, set()))
        facts = by_doc_facts.get(key, [])
        out = [f"# {name}", "",
               f"_Converted via {d.get('method', '?')} · {d.get('chars', 0)} chars._", ""]
        if ents:
            out += ["## Entities", "", ", ".join(ents), ""]
        if facts:
            out += ["## Facts", ""]
            seen = set()
            for f in facts:
                t = f["text"]
                if t in seen:
                    continue
                seen.add(t)
                out.append(f"- {t}")
            out.append("")
        _atomic_write_text(cfg.memory_dir / (key + ".md"), "\n".join(out))
        count += 1
    return count


def _doc_key(d: dict) -> str:
    # Facts/docs are keyed by the markdown stem produced in convert/segment.
    out = d.get("output")
    if out:
        n = Path(out).name
        return n[:-3] if n.endswith(".md") else n
    return Path(d.get("name", "")).name


def export_bundle(cfg: Config, dest: str) -> dict:
    dest_path = Path(dest).expanduser()
    copied = []
    try:
        dest_path.mkdir(parents=True, exist_ok=True)
        # Include the vector store so recall works from the exported bundle, not
        # just human browsing + graph reload.
        for src in (cfg.memory_md, cfg.graph_path,
                    cfg.vectors_path, cfg.vectors_path.with_suffix(".json"),
                    cfg.bm25_index_path):
            if src.exists():
                shutil.copy2(src, dest_path / src.name)
                copied.append(src.name)
        if cfg.memory_dir.exists():
            target = dest_path / "memory"
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(cfg.memory_dir, target)
            copied.append("memory/")
    except OSError as e:  # unwritable dest, file-as-parent, etc. — return a status
        return {"status": "error", "dest": str(dest_path), "error": str(e),
                "copied": copied}
    if not copied:
        return {"status": "no_memory", "dest": str(dest_path)}
    return {"status": "ok", "dest": str(dest_path), "copied": copied}
