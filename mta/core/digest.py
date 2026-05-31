"""The digestion orchestrator — convert → segment → embed → extract → resolve →
graph → communities → layered summaries → materialise.

Returns **only metadata** (counts, paths, stats): document text never crosses
back into the conversation, which is what makes a whole-folder digest cost
~0 Claude tokens. Heavy steps run locally and parallelise across performance
cores; the LLM-summary step degrades to a deterministic fact-join when no local
model is present.
"""
from __future__ import annotations

import glob as _glob
import json
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import urllib.request

from . import graph as graphmod
from . import render, store
from .config import Config
from .convert import SUPPORTED_EXTS, convert_file
from .embed import Embedder
from .extract import Extraction, extract_chunk
from .lifecycle import OllamaManager
from .platform import worker_count
from .resolve import resolve_entities
from .segment import segment_file


# ---- input expansion --------------------------------------------------
def _expand(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()

    def add(p: Path):
        rp = str(p.resolve())
        if rp not in seen and p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            seen.add(rp)
            files.append(p)

    for raw in paths:
        if any(ch in raw for ch in "*?[")  and not Path(raw).exists():
            for hit in _glob.glob(raw, recursive=True):
                add(Path(hit))
            continue
        p = Path(raw).expanduser()
        if p.is_dir():
            for child in sorted(p.rglob("*")):
                add(child)
        else:
            add(p)
    return files


# ---- conversion worker (top-level so it pickles under spawn) ----------
def _convert_worker(payload):
    path_str, out_dir_str, cfg = payload
    from .platform import pin_native_threads
    pin_native_threads()
    return convert_file(Path(path_str), Path(out_dir_str), cfg).as_dict()


def _convert_all(files: list[Path], cfg: Config, ollama: OllamaManager) -> list[dict]:
    out_dir = cfg.markdown_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    n = worker_count(cfg.workers)
    payloads = [(str(f), str(out_dir), cfg) for f in files]
    # Parallel across performance cores; fall back to sequential on any failure.
    if n > 1 and len(files) > 1:
        try:
            with ProcessPoolExecutor(max_workers=n) as ex:
                return list(ex.map(_convert_worker, payloads))
        except Exception:  # noqa: BLE001
            pass
    return [convert_file(f, out_dir, cfg, ollama).as_dict() for f in files]


# ---- local summarisation ---------------------------------------------
def _llm_summarise(prompt: str, cfg: Config, ollama: OllamaManager) -> str | None:
    if not ollama.ensure_running(wait=20):
        return None
    payload = json.dumps({
        "model": cfg.extract_model, "prompt": prompt, "stream": False,
        "options": {"temperature": 0.1},
    }).encode()
    try:
        req = urllib.request.Request(f"{ollama.host}/api/generate", data=payload,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read())
        ollama.touch()
        return (data.get("response") or "").strip() or None
    except Exception:  # noqa: BLE001
        return None


def _community_summary(label_facts: list[str], names: list[str], cfg: Config,
                       ollama: OllamaManager) -> str:
    facts = label_facts[:12]
    if cfg.extract_mode != "classical":
        prompt = ("Summarise this theme in 2-3 sentences for a memory note. "
                  "Key entities: " + ", ".join(names[:8]) + ". Facts:\n- "
                  + "\n- ".join(facts) + "\nSummary:")
        s = _llm_summarise(prompt, cfg, ollama)
        if s:
            return s
    # Deterministic fallback.
    head = ", ".join(names[:5])
    body = " ".join(facts[:3])
    return (f"Theme around {head}. {body}").strip()


# ---- main entry -------------------------------------------------------
def digest(cfg: Config, paths: list[str], reset: bool = False,
           ollama: OllamaManager | None = None) -> dict:
    cfg.ensure_dirs()
    ollama = ollama or OllamaManager(cfg)
    t0 = time.time()

    files = _expand(paths)
    if not files:
        return {"status": "no_input", "project": cfg.project,
                "message": "No convertible files found.", "paths": paths}

    conv = _convert_all(files, cfg, ollama)
    ok_md = [Path(c["output"]) for c in conv if c.get("status") == "ok" and c.get("output")]

    # Segment + extract.
    embedder = Embedder(cfg, ollama)
    all_chunks = []
    for md in ok_md:
        all_chunks.extend(segment_file(md, cfg.chunk_chars))

    extractions: list[tuple] = []
    mentions: list[dict] = []
    for ch in all_chunks:
        ex = extract_chunk(ch, cfg, ollama)
        extractions.append((ch, ex))
        mentions.extend(ex.entities)

    # Resolve entities → graph → communities.
    resolved = resolve_entities(mentions, embedder)
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
        summary = _community_summary(facts, names, cfg, ollama) if node_ids else ""
        communities.append({
            "id": comm_id,
            "label": names[0] if names else f"Theme {comm_id}",
            "summary": summary,
            "members": node_ids,
            "size": len(node_ids),
        })

    synopsis = _synopsis(communities, cfg, ollama)

    # Build the persisted graph doc.
    for n in G.nodes():
        G.nodes[n]["docs"] = sorted(G.nodes[n].get("docs", set()))
        G.nodes[n]["community"] = partition.get(n, 0)
    graph_doc = {
        "project": cfg.project,
        "version": 1,
        "created": int(t0),
        "synopsis": synopsis,
        "nodes": [{"id": n, **{k: v for k, v in G.nodes[n].items()}} for n in G.nodes()],
        "edges": [{"source": u, "target": v, "weight": d["weight"],
                   "labels": sorted(d.get("labels", []))} for u, v, d in G.edges(data=True)],
        "communities": communities,
        "documents": [{"name": c.get("source"), "output": c.get("output"),
                       "status": c.get("status"), "method": c.get("method", ""),
                       "chars": c.get("chars", 0)} for c in conv],
        "stats": {
            "files": len(files),
            "converted": len(ok_md),
            "chunks": len(all_chunks),
            "entities": G.number_of_nodes(),
            "relations": G.number_of_edges(),
            "communities": len(communities),
            "embed_mode": embedder.mode,
            "seconds": round(time.time() - t0, 1),
        },
    }
    store.save_graph(cfg, graph_doc)

    # Recall vectors: one card per entity + one per community summary.
    units, texts = _recall_units(graph_doc)
    matrix = embedder.embed(texts) if texts else None
    if matrix is not None:
        store.save_vectors(cfg, matrix, units)

    # Materialise human-facing outputs.
    render.write_memory_md(cfg, graph_doc)
    render.write_doc_memories(cfg, graph_doc, G)
    render.write_mindmap(cfg, graph_doc)

    return {
        "status": "ok",
        "project": cfg.project,
        "stats": graph_doc["stats"],
        "outputs": {
            "graph": str(cfg.graph_path),
            "memory_md": str(cfg.memory_md),
            "memory_dir": str(cfg.memory_dir),
            "mindmap": str(cfg.mindmap_html),
        },
        "conversion": _conv_tally(conv),
    }


def _synopsis(communities: list[dict], cfg: Config, ollama: OllamaManager) -> str:
    if not communities:
        return "No content digested yet."
    theme_lines = [f"{c['label']}: {c['summary']}" for c in communities[:10]]
    if cfg.extract_mode != "classical":
        prompt = ("Write a 3-4 sentence overview of this knowledge base from its "
                  "themes:\n- " + "\n- ".join(theme_lines) + "\nOverview:")
        s = _llm_summarise(prompt, cfg, ollama)
        if s:
            return s
    return ("This memory covers " + str(len(communities)) + " themes: "
            + ", ".join(c["label"] for c in communities[:8]) + ".")


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
        units.append({"kind": "entity", "ref": nid, "label": n["label"],
                      "text": card, "docs": n.get("docs", [])})
        texts.append(card)
    return units, texts


def _conv_tally(conv: list[dict]) -> dict:
    tally: dict[str, int] = {}
    for c in conv:
        tally[c.get("status", "?")] = tally.get(c.get("status", "?"), 0) + 1
    return tally
