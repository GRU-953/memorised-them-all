"""Knowledge-graph assembly + community detection.

Canonical entities become weighted nodes; resolved relations become weighted
edges. Communities (themes) are detected with **Leiden** (``leidenalg`` + igraph)
when available — it gives the most stable partitions — and degrade to NetworkX
**Louvain** and then greedy modularity. Communities are what make the memory
*layered*: each one is summarised locally into an L1 theme.
"""
from __future__ import annotations

import re
from collections import defaultdict

import networkx as nx

from .resolve import cid_for

_MAX_FACTS_PER_NODE = 25


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
            # De-dup: two surface forms of one canonical entity in the same chunk
            # must not double-count facts or co-occurrence edges.
            if cid and cid in g and cid not in present:
                present.append(cid)
                g.nodes[cid]["docs"].add(chunk.doc)
        # Attach facts to the entities they actually mention (word-boundary match,
        # so "Cat" does not capture "Category"). A fact mentioning several present
        # entities is shared by all of them; one mentioning none falls back to the
        # most salient present entity (deterministic).
        for fact in ex.facts:
            fl = fact.lower()
            holders = []
            for cid in present:
                lbl = g.nodes[cid]["label"].lower()
                # Boundary match via lookarounds (not \b) so labels that begin or
                # end with punctuation still match — e.g. "Inc.", "C++". Falls back
                # to substring containment for scripts without word separators
                # (e.g. CJK), where word boundaries don't fire.
                if re.search(rf"(?<!\w){re.escape(lbl)}(?!\w)", fl) or (
                        not re.search(r"[a-z0-9]", lbl) and lbl in fl):
                    holders.append(cid)
            if not holders and present:
                holders = [present[0]]
            rec = {"text": fact, "doc": chunk.doc, "heading": chunk.heading_path}
            for cid in holders:
                facts = g.nodes[cid]["facts"]
                # Dedupe identical fact text per node and cap the count — keeps
                # graph.json bounded (facts were duplicating heavily otherwise).
                if len(facts) >= _MAX_FACTS_PER_NODE:
                    continue
                if any(f["text"] == fact for f in facts):
                    continue
                facts.append(rec)
        # Explicit relations.
        for rel in ex.relations:
            s = cid_for(rel.get("source", ""), alias_to_cid)
            t = cid_for(rel.get("target", ""), alias_to_cid)
            if s and t and s != t and s in g and t in g:
                rtype = rel.get("relation", "related_to")
                _bump_edge(g, s, t, rtype)
                # WP-120 (Theme-Z): record the DIRECTION + type of a verb-typed relation on
                # the (still undirected) edge. Purely additive annotation — weights and the
                # co-occurrence backbone are untouched, so community detection is unchanged.
                if rtype not in ("related_to", "co_occurs"):
                    g[s][t].setdefault("rels", set()).add((rtype, s, t))
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
    # Rank members within a community by salience; node id is a stable final
    # tiebreaker so labels/ordering don't flip between near-tied entities.
    for comm, nodes in members.items():
        nodes.sort(key=lambda n: (g.degree(n, weight="weight"),
                                  g.nodes[n].get("count", 0), n), reverse=True)
    return members
