"""Materialise human-facing memory: memory.md, per-document notes, mind map.

All outputs are plain files on disk. ``memory.md`` is the compact, layered digest
Claude reads (synopsis → themes → key facts → index); per-document notes make the
memory exportable and browseable; ``mindmap.html`` is a fully offline interactive
graph (Cytoscape.js inlined from the bundled asset, no network, no CDN).
"""
from __future__ import annotations

import html
import json
import shutil
from collections import defaultdict
from pathlib import Path

from .config import Config
from .store import _atomic_write_text   # temp → fsync → os.replace (crash-safe)


def _asset(*parts: str) -> Path:
    """Locate a bundled asset in both the dev repo and the installed wheel.

    Dev layout: <repo>/templates|assets/...   (templates next to the mta package)
    Wheel layout: <site-packages>/mta/templates|assets/...   (force-included)
    """
    here = Path(__file__).resolve()
    candidates = [
        here.parents[1] / Path(*parts),   # mta/<parts>  (installed wheel)
        here.parents[2] / Path(*parts),   # <repo>/<parts>  (dev checkout)
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]


_TEMPLATE = _asset("templates", "mindmap.html.j2")
_CYTOSCAPE = _asset("assets", "cytoscape.min.js")


def write_memory_md(cfg: Config, doc: dict) -> Path:
    s = doc.get("stats", {})
    lines = [
        f"# Memory — {doc['project']}", "",
        f"> Generated locally by **Memorised them All**. "
        f"{s.get('files', 0)} files · {s.get('entities', 0)} entities · "
        f"{s.get('relations', 0)} relations · {s.get('communities', 0)} themes · "
        f"embeddings: {s.get('embed_mode', 'n/a')}.", "",
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
        name = Path(d["name"]).name
        stem = name
        ents = sorted(by_doc_entities.get(_doc_key(d), set()))
        facts = by_doc_facts.get(_doc_key(d), [])
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
        _atomic_write_text(cfg.memory_dir / (stem + ".md"), "\n".join(out))
        count += 1
    return count


def _doc_key(d: dict) -> str:
    # Facts/docs are keyed by the markdown stem produced in convert/segment.
    out = d.get("output")
    if out:
        n = Path(out).name
        return n[:-3] if n.endswith(".md") else n
    return Path(d.get("name", "")).name


def write_mindmap(cfg: Config, doc: dict) -> Path:
    palette = ["#6366f1", "#ec4899", "#f59e0b", "#10b981", "#3b82f6", "#ef4444",
               "#8b5cf6", "#14b8a6", "#f97316", "#84cc16"]
    cy_nodes = [{"data": {"id": n["id"], "label": n["label"],
                          "comm": n.get("community", 0),
                          "color": palette[n.get("community", 0) % len(palette)],
                          "size": 18 + min(40, n.get("count", 1) * 4)}}
                for n in doc["nodes"]]
    cy_edges = [{"data": {"source": e["source"], "target": e["target"],
                          "weight": e.get("weight", 1)}} for e in doc["edges"]]
    data = {"elements": {"nodes": cy_nodes, "edges": cy_edges},
            "synopsis": doc.get("synopsis", ""),
            "communities": [{"id": c["id"], "label": c["label"],
                             "summary": c.get("summary", "")} for c in doc["communities"]],
            "project": doc["project"]}

    # Escape "</" so an entity label containing "</script>" can't break out of
    # the inline <script> data block (still valid JSON/JS).
    data_js = json.dumps(data).replace("</", "<\\/")
    cyto = _CYTOSCAPE.read_text(encoding="utf-8") if _CYTOSCAPE.exists() else ""
    if not cyto:
        # The bundled Cytoscape asset is missing from this build — render a static,
        # strictly-offline notice rather than fetching it from a CDN. The mind map
        # makes ZERO network requests (SEC-10). The asset is force-included in both
        # the wheel and the .mcpb, so this path should never trigger in practice.
        _atomic_write_text(
            cfg.mindmap_html,
            "<!doctype html><meta charset=utf-8><title>"
            + html.escape(doc["project"]) + " — mind map</title>"
            "<body style='font-family:sans-serif;background:#0b1020;color:#e7ecf5;padding:24px'>"
            "<h1>" + html.escape(doc["project"]) + " — memory</h1>"
            "<p>The offline mind-map renderer asset is missing from this build; "
            "reinstall the package to restore it. (No network fallback is used.)</p>"
            "<p>" + html.escape(doc.get("synopsis", "")) + "</p></body>")
        return cfg.mindmap_html
    cyto_tag = f"<script>{cyto}</script>"
    if _TEMPLATE.exists():
        tpl = _TEMPLATE.read_text(encoding="utf-8")
        out_html = (tpl.replace("/*__CYTOSCAPE__*/", cyto_tag)
                    .replace("/*__DATA__*/", data_js))
    else:
        out_html = _fallback_html(data, cyto_tag, data_js)
    _atomic_write_text(cfg.mindmap_html, out_html)
    return cfg.mindmap_html


def _fallback_html(data: dict, cyto_tag: str, data_js: str | None = None) -> str:
    data_js = data_js if data_js is not None else json.dumps(data).replace("</", "<\\/")
    return ("<!doctype html><meta charset=utf-8><title>"
            + html.escape(data["project"]) + " — mind map</title>"
            + cyto_tag
            + "<div id=cy style='position:fixed;inset:0'></div><script>"
            + "var D=" + data_js + ";cytoscape({container:"
            + "document.getElementById('cy'),elements:D.elements,layout:{name:'cose'},"
            + "style:[{selector:'node',style:{'background-color':'data(color)',"
            + "'label':'data(label)','width':'data(size)','height':'data(size)',"
            + "'font-size':8}},{selector:'edge',style:{'opacity':0.3}}]});</script>")


def export_bundle(cfg: Config, dest: str) -> dict:
    dest_path = Path(dest).expanduser()
    copied = []
    try:
        dest_path.mkdir(parents=True, exist_ok=True)
        # Include the vector store so semantic recall works from the exported
        # bundle, not just human browsing + graph reload.
        for src in (cfg.memory_md, cfg.graph_path, cfg.mindmap_html,
                    cfg.vectors_path, cfg.vectors_path.with_suffix(".json")):
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
