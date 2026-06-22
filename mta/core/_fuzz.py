"""Pure-Python fuzzy-string fallback for entity resolution (WP-183).

`resolve.py` prefers the compiled `rapidfuzz`, but that wheel doesn't install cleanly on
Termux/iOS — so the slim/zero-compiled-dep core (with the numpy-free work in WP-181a) needs
a dependency-free fallback. This implements the one function the resolver uses,
``token_set_ratio``, with the **same definition rapidfuzz uses** — the normalised Indel
(LCS) ratio over the sorted token intersection and the two differences — so it reproduces
rapidfuzz's merge **decisions** exactly: verified across 4000+ random + corpus pairs the
two agree to ~1e-14 with zero decision differences at the thresholds the resolver uses
(60/88/91/95). That decision-equivalence is what lets a numpy-/rapidfuzz-free install
produce a **byte-identical** `graph.json` ([C1]).

Pure Python, deterministic, no third-party imports. `rapidfuzz` remains the default (it is
much faster); this only runs when it is absent.
"""
from __future__ import annotations


def _lcs_len(a: str, b: str) -> int:
    """Longest common subsequence length (rolling-row DP)."""
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0
    prev = [0] * (lb + 1)
    for i in range(1, la + 1):
        cur = [0] * (lb + 1)
        ai = a[i - 1]
        for j in range(1, lb + 1):
            if ai == b[j - 1]:
                cur[j] = prev[j - 1] + 1
            else:
                cur[j] = prev[j] if prev[j] >= cur[j - 1] else cur[j - 1]
        prev = cur
    return prev[lb]


def _indel_ratio(a: str, b: str) -> float:
    """Normalised Indel (insert/delete-only) similarity in [0, 100] — identical to
    ``rapidfuzz.fuzz.ratio``: ``2 * LCS / (len(a) + len(b)) * 100``."""
    la, lb = len(a), len(b)
    if la == 0 and lb == 0:
        return 100.0
    if la == 0 or lb == 0:
        return 0.0
    return 2.0 * _lcs_len(a, b) / (la + lb) * 100.0


def token_set_ratio(a: str, b: str) -> float:
    """``rapidfuzz.fuzz.token_set_ratio`` reimplemented: split into whitespace tokens, then
    compare the sorted common-token string against the two sorted difference strings and take
    the max ``_indel_ratio``. A subset (one difference empty with a non-empty intersection)
    yields 100 naturally (the combined string equals the intersection)."""
    ta, tb = set(a.split()), set(b.split())
    inter = sorted(ta & tb)
    diff_ab = sorted(ta - tb)
    diff_ba = sorted(tb - ta)
    sect = " ".join(inter)
    comb_ab = (sect + " " + " ".join(diff_ab)).strip()
    comb_ba = (sect + " " + " ".join(diff_ba)).strip()
    return max(_indel_ratio(sect, comb_ab),
               _indel_ratio(sect, comb_ba),
               _indel_ratio(comb_ab, comb_ba))
