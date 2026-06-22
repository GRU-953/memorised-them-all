"""Entity resolution — collapse surface variants into canonical nodes.

Two mentions refer to the same entity when their names are fuzzily similar
(``rapidfuzz`` token-set ratio, with a normalised-string fast path) *or* their
name embeddings are highly cosine-similar. A union-find groups the matches; the
most frequent surface form becomes the canonical label and the rest become
aliases. Falls back to exact normalised-string matching if ``rapidfuzz`` is
absent.
"""
from __future__ import annotations

import os
import re
import unicodedata
from collections import Counter, defaultdict

from .embed import Embedder

# All Brahmic combining marks live in U+0900–U+0DFF (Devanagari · Bengali · Gurmukhi ·
# Gujarati · Oriya · Tamil · Telugu · Kannada · Malayalam · Sinhala). They are category
# Mc/Mn and are NOT matched by \w, so a bare [^\w] squeeze DELETES every vowel-sign/halant,
# collapsing distinct words to consonant skeletons and force-merging unrelated entities —
# Bengali ভোলা & ভালো → "ভ ল"; Devanagari काली & कुल → "क ल"; Tamil கடல் & கடா → "க ட".
# WP-101 (R-16): keep the *whole* Brahmic range, not just the Bengali block (U+0980–U+09FF),
# so the matra-preservation that protected Bengali now protects every Indic script. Keeping
# MORE marks only ever PRESERVES MORE DISTINCTIONS → fewer merges (the safe over-split
# direction; can never introduce an over-merge). The per-script tightening + minimal-pair
# proofs are WP-121.
_BRAHMIC_LO, _BRAHMIC_HI = "ऀ", "෿"


def _is_brahmic(c: str) -> bool:
    return _BRAHMIC_LO <= c <= _BRAHMIC_HI


_NORM_RE = re.compile(r"[^\wऀ-෿]+", re.UNICODE)

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


def _eff_threshold(a: str, b: str, base: int) -> int:
    """WP-102 (R-17): short names need near-identity. A one-character difference in a
    4-char name (করিম / করিমা — `token_set_ratio` ≈ 89) is a *different entity*, not a typo,
    yet it clears the default 88 and force-merges. Scale the required ratio up as the
    shorter normalised name gets shorter. Monotone, deterministic, and it only ever RAISES
    the bar → fewer merges (the safe over-split direction); long-name typo merges (where
    fuzzy matching earns its keep) are unaffected."""
    shorter = min(len(a), len(b))
    if shorter <= 4:
        return max(base, 95)
    if shorter <= 6:
        return max(base, 91)
    return base


def _norm(name: str) -> str:
    # Fold Latin accents (José → jose) + compatibility forms (ﬁ→fi, ＡＢＣ→abc) but PRESERVE
    # *Brahmic* combining marks (halant/nukta/matras) — stripping them merged নিম্ন-class words
    # and (WP-101/R-16) काली/कुल-class words. Matras are also kept by _NORM_RE above; re-compose
    # NFC so the canonical form matches stored labels.
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not (unicodedata.combining(c) and not _is_brahmic(c)))
    s = unicodedata.normalize("NFC", s)
    return _NORM_RE.sub(" ", s).lower().strip()


def _script(s: str) -> str:
    """Coarse script tag of the first significant char of a normalised name. Bengali
    (U+0980–U+09FF) and ASCII alnum are split out; everything else is keyed by codepoint
    block so e.g. Cyrillic/CJK never co-bucket with Latin. Used only for blocking."""
    for c in s:
        if c == " ":
            continue
        if "ঀ" <= c <= "৿":
            return "bn"
        if c.isascii() and c.isalnum():
            return "la"
        return f"u{ord(c) >> 8}"
    return ""


def _block_keys(norm: str, script: str) -> set[str]:
    """Overlapping blocking keys: per distinct token, BOTH its first-2 and last-2 chars
    (script-tagged). A *fuzzy-string* merge (token_set_ratio ≥ threshold) needs a shared
    near-identical token; a single edit changes a token's leading OR trailing chars but not
    both (for the realistic OCR/transliteration typos this ingests), so a near-identical
    token pair shares at least one of {prefix-2, suffix-2} and co-buckets — blocking
    reproduces the full-scan fuzzy merges (parity-tested on a realistic corpus incl.
    leading-edit pairs).

    Blocking is always a SAFE REFINEMENT of the full O(n²) scan: it only ever drops
    comparisons, and the merge predicate is unchanged, so it can never introduce an
    over-merge. The one case where it legitimately diverges is the *embedding* pass — the
    hash embedder can give cosine 1.0 to two unrelated single-token names that collide in
    256 dims; the full scan would then merge them if token_set_ratio ≥ 60, whereas blocking
    skips the (spurious, hash-collision) merge. That divergence is over-SPLIT (the safe
    direction) and avoids a bad merge, so it is accepted. Cross-script pairs (ratio≈0) are
    never merged today, so skipping them changes nothing."""
    toks = norm.split()
    if not toks:
        return {f"{script}:"}
    keys: set[str] = set()
    for t in toks:
        keys.add(f"{script}:p{t[:2]}")   # prefix block
        keys.add(f"{script}:s{t[-2:]}")  # suffix block — catches leading-char edits
    return keys


def _resolve_cap_from_env() -> int:
    """Fallback cap when ``resolve_entities`` is called without a Config (mirrors
    ``Config.resolve_max_names`` / MTA_RESOLVE_MAX_NAMES; 0 or negative = unbounded)."""
    try:
        return int(str(os.environ.get("MTA_RESOLVE_MAX_NAMES", "5000")).strip())
    except (TypeError, ValueError):
        return 5000


def _candidate_pairs(norms: list[str], block: bool = True) -> list[tuple[int, int]]:
    """All (i<j) pairs that share at least one blocking key — the only pairs that can
    pass the fuzzy/embedding thresholds. Deterministic (sorted keys + sorted output).
    ``block=False`` returns the full O(n²) pair set (the unblocked reference used to
    prove parity, and a safety escape hatch)."""
    n = len(norms)
    if not block:
        return [(i, j) for i in range(n) for j in range(i + 1, n)]
    scripts = [_script(nm) for nm in norms]
    buckets: dict[str, list[int]] = defaultdict(list)
    for i in range(n):
        for key in _block_keys(norms[i], scripts[i]):
            buckets[key].append(i)            # appended in ascending i
    seen: set[tuple[int, int]] = set()
    for key in sorted(buckets):
        idxs = buckets[key]
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)):
                seen.add((idxs[a], idxs[b]))  # i<j by construction
    return sorted(seen)


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
                     cos_threshold: float = 0.92,
                     resolve_cap: int | None = None,
                     _block: bool = True) -> dict:
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

    # R-14: only compare plausibly-matching pairs (shared blocking key) instead of the
    # full O(n²) scan. The cap now bounds the unique-name set entering the pairwise
    # passes — above it, exact-norm + acronym (both O(n)) still run; only fuzzy/embedding
    # are skipped (a documented, configurable degradation, not a silent 1500 cliff).
    cap = resolve_cap if resolve_cap is not None else _resolve_cap_from_env()
    do_pairwise = _HAVE_FUZZ and n >= 2 and (cap <= 0 or n <= cap)
    candidate_pairs = _candidate_pairs(norms, block=_block) if do_pairwise else []

    # Fuzzy string match over candidate pairs only (per-pair guards unchanged).
    if do_pairwise:
        for i, j in candidate_pairs:
            if uf.find(i) == uf.find(j):
                continue
            if abs(len(norms[i]) - len(norms[j])) > 12:
                continue
            if _numbered_siblings(norms[i], norms[j]):
                continue
            if fuzz.token_set_ratio(norms[i], norms[j]) >= _eff_threshold(norms[i], norms[j], fuzz_threshold):
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
    if do_pairwise:
        mat = embedder.embed(names)
        for i, j in candidate_pairs:        # same blocked candidates; no dense n×n matrix
            if uf.find(i) == uf.find(j):
                continue
            if float(mat[i] @ mat[j]) < cos_threshold:   # L2-normalised rows → dot = cosine
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
