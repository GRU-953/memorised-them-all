"""Knowledge-graph assembly + community detection.

Canonical entities become weighted nodes; resolved relations become weighted
edges. Communities (themes) are detected with **Leiden** (``leidenalg`` + igraph)
when available — it gives the most stable partitions — and degrade to NetworkX
**Louvain** and then greedy modularity. Communities are what make the memory
*layered*: each one is summarised locally into an L1 theme.
"""
from __future__ import annotations

from collections import defaultdict

import networkx as nx

from .resolve import cid_for


def build_graph(extractions: list, alias_to_cid: dict, canonical: dict) -> nx.Graph:
    """Assemble an undirected weighted graph from per-chunk extractions.

    Each item of ``extractions`` is (chunk, Extraction).
    """
    g = nx.Graph()
    for cid, meta in canonical.items():
        g.add_node(cid, label=meta["label"], type=meta["type"],
                   count=meta["count"], facts=[], docs=set(), aliases=meta["aliases"])

    for chunk, ex in extractions:
        present: list[str] = []
        for ent in ex.entities:
            cid = cid_for(ent.get("name", ""), alias_to_cid)
            if cid and cid in g:
                present.append(cid)
                g.nodes[cid]["docs"].add(chunk.doc)
        # Attach facts to the entities they mention (provenance preserved).
        for fact in ex.facts:
            holder = None
            for cid in present:
                if g.nodes[cid]["label"].lower() in fact.lower():
                    holder = cid
                    break
            holder = holder or (present[0] if present else None)
            if holder:
                g.nodes[holder]["facts"].append({"text": fact, "doc": chunk.doc,
                                                 "heading": chunk.heading_path})
        # Explicit relations.
        for rel in ex.relations:
            s = cid_for(rel.get("source", ""), alias_to_cid)
            t = cid_for(rel.get("target", ""), alias_to_cid)
            if s and t and s != t and s in g and t in g:
                _bump_edge(g, s, t, rel.get("relation", "related_to"))
        # Co-occurrence backbone within the chunk.
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                _bump_edge(g, present[i], present[j], "co_occurs")
    return g


def _bump_edge(g: nx.Graph, a: str, b: str, label: str) -> None:
    if g.has_edge(a, b):
        g[a][b]["weight"] += 1
        g[a][b]["labels"].add(label)
    else:
        g.add_edge(a, b, weight=1, labels={label})


def detect_communities(g: nx.Graph, algo: str = "auto") -> dict[str, int]:
    """Return {node_id: community_index}. Empty graph → {}."""
    if g.number_of_nodes() == 0:
        return {}
    if g.number_of_edges() == 0:
        return {n: i for i, n in enumerate(g.nodes())}

    order = list(g.nodes())
    if algo in ("auto", "leiden"):
        part = _leiden(g, order)
        if part is not None:
            return part
        if algo == "leiden":
            algo = "louvain"

    if algo in ("auto", "louvain"):
        try:
            comms = nx.community.louvain_communities(g, weight="weight", seed=7)
            return _from_sets(comms)
        except Exception:  # noqa: BLE001
            pass

    comms = nx.community.greedy_modularity_communities(g, weight="weight")
    return _from_sets(comms)


def _leiden(g: nx.Graph, order: list[str]):
    try:
        import igraph as ig
        import leidenalg
    except Exception:  # noqa: BLE001
        return None
    try:
        idx = {n: i for i, n in enumerate(order)}
        edges = [(idx[u], idx[v]) for u, v in g.edges()]
        weights = [g[u][v]["weight"] for u, v in g.edges()]
        ig_g = ig.Graph(n=len(order), edges=edges)
        ig_g.es["weight"] = weights
        part = leidenalg.find_partition(
            ig_g, leidenalg.ModularityVertexPartition, weights="weight", seed=7)
        return {order[i]: m for m, comm in enumerate(part) for i in comm}
    except Exception:  # noqa: BLE001
        return None


def _from_sets(comms) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, comm in enumerate(comms):
        for node in comm:
            out[node] = i
    return out


def community_members(g: nx.Graph, partition: dict[str, int]) -> dict[int, list[str]]:
    members: dict[int, list[str]] = defaultdict(list)
    for node, comm in partition.items():
        members[comm].append(node)
    # Rank members within a community by salience (degree * count).
    for comm, nodes in members.items():
        nodes.sort(key=lambda n: (g.degree(n, weight="weight"),
                                  g.nodes[n].get("count", 0)), reverse=True)
    return members
