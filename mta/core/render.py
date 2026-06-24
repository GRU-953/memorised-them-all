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


def write_graph_exports(doc: dict, dest_path: Path) -> list[str]:
    """Write deterministic interop exports of the knowledge graph (v3, WP-125): GraphML
    (Gephi / yEd / Cytoscape) + ``entities.csv`` / ``relations.csv``. Built over a SORTED
    node/edge order, so two exports of the same memory are identical. These are
    developer/interchange artifacts (not the core store), so they aren't on the [C1]
    byte-identity *gate*, but they are deterministic for a fixed networkx + csv. List
    attributes (docs / edge labels) are flattened to ``"; "``-joined strings because GraphML
    only accepts primitive attribute values."""
    import csv
    import io

    import networkx as nx

    written: list[str] = []
    nodes = sorted(doc.get("nodes", []), key=lambda n: str(n.get("id", "")))
    edges = sorted(doc.get("edges", []),
                   key=lambda e: (str(e.get("source", "")), str(e.get("target", ""))))

    g = nx.Graph()
    for n in nodes:
        nid = str(n.get("id", ""))
        if not nid:
            continue
        g.add_node(nid, label=str(n.get("label", "")), type=str(n.get("type", "")),
                   count=int(n.get("count", 0) or 0), community=int(n.get("community", 0) or 0),
                   docs="; ".join(str(d) for d in (n.get("docs") or [])))
    for e in edges:
        s, t = str(e.get("source", "")), str(e.get("target", ""))
        if g.has_node(s) and g.has_node(t):
            g.add_edge(s, t, weight=int(e.get("weight", 1) or 1),
                       labels="; ".join(str(x) for x in (e.get("labels") or [])))

    # GraphML: generate to a string, then commit through the crash-safe atomic writer.
    _atomic_write_text(dest_path / "graph.graphml",
                       "".join(nx.generate_graphml(g, encoding="utf-8", prettyprint=True)))
    written.append("graph.graphml")

    def _csv(rows: list[list], header: list[str]) -> str:
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")   # fixed terminator → OS-independent bytes
        w.writerow(header)
        w.writerows(rows)
        return buf.getvalue()

    _atomic_write_text(dest_path / "entities.csv", _csv(
        [[n.get("id", ""), n.get("label", ""), n.get("type", ""), n.get("count", 0),
          n.get("community", 0), "; ".join(str(d) for d in (n.get("docs") or []))]
         for n in nodes],
        ["id", "label", "type", "count", "community", "docs"]))
    written.append("entities.csv")

    _atomic_write_text(dest_path / "relations.csv", _csv(
        [[e.get("source", ""), e.get("target", ""), e.get("weight", 1),
          "; ".join(str(x) for x in (e.get("labels") or []))] for e in edges],
        ["source", "target", "weight", "labels"]))
    written.append("relations.csv")
    return written


def export_bundle(cfg: Config, dest: str) -> dict:
    import json

    dest_path = Path(dest).expanduser()
    copied = []
    try:
        dest_path.mkdir(parents=True, exist_ok=True)
        # Include the vector store so recall works from the exported bundle, not
        # just human browsing + graph reload. (The incremental manifest is deliberately
        # excluded — it holds absolute machine-local source paths.)
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
    # v3: deterministic GraphML + CSV interop exports alongside the portable bundle.
    try:
        doc = json.loads(cfg.graph_path.read_text(encoding="utf-8")) \
            if cfg.graph_path.exists() else None
        if isinstance(doc, dict) and doc.get("nodes"):
            copied += write_graph_exports(doc, dest_path)
    except (OSError, ValueError, ImportError):
        pass    # interop exports are best-effort; the portable bundle already succeeded
    return {"status": "ok", "dest": str(dest_path), "copied": copied}
