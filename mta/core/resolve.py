"""Entity resolution — collapse surface variants into canonical nodes.

Two mentions refer to the same entity when their names are fuzzily similar
(``rapidfuzz`` token-set ratio, with a normalised-string fast path) *or* their
name embeddings are highly cosine-similar. A union-find groups the matches; the
most frequent surface form becomes the canonical label and the rest become
aliases. Falls back to exact normalised-string matching if ``rapidfuzz`` is
absent.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

import numpy as np

from .embed import Embedder, cosine

# Keep any Unicode word character (CJK, Cyrillic, …) AND the Bengali block — Bengali
# vowel signs (matras), halant (্ U+09CD) and nukta (় U+09BC) are category Mc/Mn and are
# NOT matched by \w, so a bare [^\w] squeeze DELETES every matra, collapsing distinct words
# to consonant skeletons (ভোলা[Bhola] & ভালো[good] → "ভ ল"; ঢাকা[Dhaka] & ঢাকি[drum] → "ঢ ক")
# and force-merging unrelated entities. Block range matches recall._TOK (U+0980–U+09FF).
_NORM_RE = re.compile(r"[^\wঀ-৿]+", re.UNICODE)

try:
    from rapidfuzz import fuzz
    _HAVE_FUZZ = True
except Exception:  # noqa: BLE001 - a hard dependency; if it's missing, degrade LOUDLY (PIPE-05)
    import sys as _sys
    _HAVE_FUZZ = False
    _sys.stderr.write(
        "[mta] WARNING: rapidfuzz is not installed — entity resolution falls back to "
        "exact-match only, which over-splits entities that differ only by spacing/case. "
        "rapidfuzz is a required dependency; reinstall it (`pip install rapidfuzz`, or run "
        "`mta doctor`).\n")


def _norm(name: str) -> str:
    # Fold Latin accents (José → jose) + compatibility forms (ﬁ→fi, ＡＢＣ→abc) but PRESERVE
    # Bengali combining marks (halant/nukta) — stripping them merged নিম্ন-class words. Matras
    # are kept by _NORM_RE above; re-compose NFC so the canonical form matches stored labels.
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not (unicodedata.combining(c) and not ("ঀ" <= c <= "৿")))
    s = unicodedata.normalize("NFC", s)
    return _NORM_RE.sub(" ", s).lower().strip()


def _numbered_siblings(a: str, b: str) -> bool:
    """True if two normalised names differ only by a trailing enumerator —
    e.g. "reykjavik 1" vs "reykjavik 2", or "site1" vs "site2". Such pairs are
    distinct entities and must not be fuzzily merged."""
    ta, tb = a.split(), b.split()
    if not ta or len(ta) != len(tb):
        return False
    diff = [k for k in range(len(ta)) if ta[k] != tb[k]]
    if len(diff) != 1:
        return False
    x, y = ta[diff[0]], tb[diff[0]]
    if x.isdigit() and y.isdigit():
        return True
    return x[:-1] == y[:-1] and x[-1:].isdigit() and y[-1:].isdigit()


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def resolve_entities(mentions: list[dict], embedder: Embedder,
                     fuzz_threshold: int = 88,
                     cos_threshold: float = 0.92) -> dict:
    """Group mention dicts ({name,type}) into canonical entities.

    Returns {"canonical": {cid: {label,type,aliases,count}},
             "alias_to_cid": {normalised_name: cid}}.
    """
    if not mentions:
        return {"canonical": {}, "alias_to_cid": {}}

    # Count surface forms; resolve over the unique set for speed.
    freq: Counter[str] = Counter()
    types: dict[str, Counter] = defaultdict(Counter)
    for m in mentions:
        name = (m.get("name") or "").strip()
        if not name:
            continue
        freq[name] += 1
        types[name][m.get("type", "other") or "other"] += 1

    names = list(freq)
    n = len(names)
    uf = _UnionFind(n)
    norms = [_norm(x) for x in names]

    # Exact normalised match.
    by_norm: dict[str, list[int]] = defaultdict(list)
    for i, nm in enumerate(norms):
        by_norm[nm].append(i)
    for key, group in by_norm.items():
        if not key:  # don't merge names that normalise to empty (e.g. punctuation-only)
            continue
        for k in range(1, len(group)):
            uf.union(group[0], group[k])

    # Fuzzy string match (only worthwhile for a manageable set).
    if _HAVE_FUZZ and n <= 1500:
        for i in range(n):
            for j in range(i + 1, n):
                if uf.find(i) == uf.find(j):
                    continue
                if abs(len(norms[i]) - len(norms[j])) > 12:
                    continue
                if _numbered_siblings(norms[i], norms[j]):
                    continue
                if fuzz.token_set_ratio(norms[i], norms[j]) >= fuzz_threshold:
                    uf.union(i, j)

    # Acronym ↔ expansion linking, e.g. "NGA" ↔ "Nordic Grid Authority". An
    # acronym is matched to an expansion only when its letters exactly equal the
    # initials of the expansion's significant words AND the word count matches —
    # precise enough to avoid the over-merge failure mode.
    acro_of: dict[str, list[int]] = defaultdict(list)   # ACRONYM -> indices
    expand_of: dict[str, list[int]] = defaultdict(list)  # INITIALS -> indices
    for i, raw in enumerate(names):
        letters = re.sub(r"[^A-Za-z]", "", raw)
        words = [w for w in re.split(r"\s+", raw.strip()) if w and w[0].isalpha()]
        if len(words) <= 1 and 2 <= len(letters) <= 6 and raw.strip() == raw.strip().upper():
            acro_of[letters.upper()].append(i)
        elif len(words) >= 2:
            expand_of["".join(w[0] for w in words).upper() + f"|{len(words)}"].append(i)
    for acro, idxs in acro_of.items():
        cands = expand_of.get(f"{acro}|{len(acro)}", [])
        # Only link when the expansion is unambiguous — a single candidate. If two
        # distinct entities share initials+word-count, linking either would
        # transitively merge them, so we link none.
        if len(cands) != 1:
            continue
        for i in idxs:
            uf.union(i, cands[0])

    # Embeddings only *confirm* a merge that also shares tokens. Pure-embedding
    # merging is unsafe for short proper nouns — domain-related names (e.g. two
    # different organisations) sit close in embedding space and would otherwise
    # collapse into one entity. Requiring a fuzzy floor prevents that.
    if _HAVE_FUZZ and 2 <= n <= 1500:
        mat = embedder.embed(names)
        sims = cosine(mat, mat)
        rows, cols = np.where(np.triu(sims >= cos_threshold, k=1))
        for i, j in zip(rows.tolist(), cols.tolist()):
            if uf.find(i) == uf.find(j):
                continue
            if fuzz.token_set_ratio(norms[i], norms[j]) >= 60:
                uf.union(i, j)

    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[uf.find(i)].append(i)

    canonical: dict[str, dict] = {}
    alias_to_cid: dict[str, str] = {}
    for cid_num, members in enumerate(clusters.values()):
        member_names = [names[i] for i in members]
        label = max(member_names, key=lambda x: (freq[x], len(x)))
        type_counter: Counter = Counter()
        total = 0
        for mn in member_names:
            total += freq[mn]
            type_counter.update(types[mn])
        cid = f"e{cid_num}"
        canonical[cid] = {
            "label": label,
            "type": (type_counter.most_common(1)[0][0] if type_counter else "other"),
            "aliases": sorted(set(member_names) - {label}),
            "count": total,
        }
        for mn in member_names:
            alias_to_cid[_norm(mn)] = cid
    return {"canonical": canonical, "alias_to_cid": alias_to_cid}


def cid_for(name: str, alias_to_cid: dict) -> str | None:
    return alias_to_cid.get(_norm(name))
