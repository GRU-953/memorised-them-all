"""Structure-aware + semantic chunking with provenance.

Markdown is split first on heading boundaries (so a chunk never straddles two
sections), then long sections are packed into ~``chunk_chars``-sized windows at
sentence boundaries. Every chunk carries its provenance: the source document and
the heading path it came from, which later flows into the graph and into recall
results so Claude can always cite where a fact came from.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_SENT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass
class Chunk:
    id: str
    doc: str                      # source document name
    heading_path: str             # "Section > Subsection"
    text: str
    index: int


def _sentences(block: str) -> list[str]:
    block = block.strip()
    if not block:
        return []
    parts = _SENT_RE.split(block)
    return [p.strip() for p in parts if p.strip()]


def _split_oversize(s: str, limit: int) -> list[str]:
    """Hard-split a single overly long sentence on whitespace near the limit.

    Without this, an unpunctuated blob becomes one giant chunk and the extractor's
    input cap silently drops the tail. Splitting keeps all content addressable.
    """
    if len(s) <= limit:
        return [s]
    out, i, n = [], 0, len(s)
    while i < n:
        end = min(i + limit, n)
        if end < n:
            brk = s.rfind(" ", i + limit // 2, end)
            if brk > i:
                end = brk
        out.append(s[i:end].strip())
        i = end
    return [p for p in out if p]


def _pack(sentences: list[str], limit: int) -> list[str]:
    out, cur = [], ""
    for raw in sentences:
        for s in _split_oversize(raw, limit):
            if cur and len(cur) + len(s) + 1 > limit:
                out.append(cur)
                cur = s
            else:
                cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def segment_markdown(text: str, doc: str, chunk_chars: int = 1200) -> list[Chunk]:
    text = _COMMENT_RE.sub("", text or "")
    lines = text.splitlines()
    chunks: list[Chunk] = []
    heading_stack: list[tuple[int, str]] = []
    buf: list[str] = []
    idx = 0

    def heading_path() -> str:
        return " > ".join(h for _, h in heading_stack) or doc

    def flush():
        nonlocal idx, buf
        body = "\n".join(buf).strip()
        buf = []
        if not body:
            return
        for piece in _pack(_sentences(body) or [body], chunk_chars):
            if len(piece) < 8:
                continue
            chunks.append(Chunk(
                id=f"{doc}#{idx}", doc=doc, heading_path=heading_path(),
                text=piece, index=idx))
            idx += 1

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
        else:
            buf.append(line)
    flush()
    return chunks


def segment_file(md_path: Path, chunk_chars: int = 1200) -> list[Chunk]:
    doc = Path(md_path).name
    if doc.endswith(".md"):
        doc = doc[:-3]
    text = Path(md_path).read_text(encoding="utf-8", errors="replace")
    return segment_markdown(text, doc, chunk_chars)
