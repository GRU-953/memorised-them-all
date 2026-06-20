"""Recursive, bounded, traversal-safe archive expansion (v2).

Archives (zip / tar / tar.gz / tgz / tar.bz2 / tar.xz / single-stream gz/bz2/xz, plus
best-effort rar/7z via an external ``unar``/``7z`` binary) are expanded so their
contents get digested like ordinary files. OOXML/EPUB (.docx/.xlsx/.pptx/.epub) are
**never** expanded — dispatch is by file NAME, not by zip magic, so Office documents
always stay on the MarkItDown path.

Security controls (load-bearing — see SECURITY.md):
- **Path traversal (Zip-Slip):** every member name is validated — no absolute paths,
  no drive letters, no ``..`` components; the resolved target must stay inside the
  destination. Tar members that are symlinks/hardlinks/devices/FIFOs are skipped.
  ``extractall`` is never used.
- **Bombs:** a per-member size cap (``max_file_mb``), a CUMULATIVE uncompressed
  budget across the whole nested tree, an entry-count cap (``archive_max_entries``),
  and a recursion depth cap (``archive_max_depth``, so zip-quines terminate). Actual
  copied bytes are counted (declared sizes can lie) — the stream is hard-stopped.
- **All-or-nothing on budget breach:** if the cumulative budget or entry cap is hit,
  the whole expansion is rolled back (the scratch dir is removed) and the archive is
  reported, not silently half-ingested. An oversize single member is skipped alone.
- External rar/7z output is post-sanitised: symlinks are removed and the same budget
  is enforced; if no tool is available the archive is skipped cleanly (the
  dependency-free invariant holds).

Everything is deterministic: members are processed in archive order, nested
expansion is depth-first, and the scratch layout is derived from the archive's
content hash (``<stem>-<sha8>``).
"""
from __future__ import annotations

import bz2
import gzip
import hashlib
import lzma
import os
import shutil
import subprocess
import tarfile
import time
import zipfile
from pathlib import Path

from .config import Config

_TAR_SUFFIXES = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz")
_STREAM_OPENERS = {".gz": gzip.open, ".bz2": bz2.open, ".xz": lzma.open}
_EXTERNAL_SUFFIXES = (".rar", ".7z")
# Extension-level set for SUPPORTED_EXTS / list_digestible (compound .tar.* resolve
# to their last suffix here; kind() below does the precise name-based dispatch).
ARCHIVE_EXTS = {".zip", ".tar", ".tgz", ".tbz2", ".txz", ".gz", ".bz2", ".xz",
                ".rar", ".7z"}

_CHUNK = 1024 * 1024
_EXTERNAL_TIMEOUT = 600  # seconds for an external unar/7z extraction


def kind(path: Path) -> str | None:
    """The archive family for ``path`` by NAME (never by magic — Office files that
    are zip containers must not match), or None if it isn't an archive."""
    n = path.name.lower()
    if n.endswith((".docx", ".xlsx", ".pptx", ".epub")):  # belt-and-braces
        return None
    if n.endswith(".zip"):
        return "zip"
    if any(n.endswith(s) for s in _TAR_SUFFIXES):
        return "tar"
    if n.endswith(".rar"):
        return "rar"
    if n.endswith(".7z"):
        return "7z"
    if n.endswith((".gz", ".bz2", ".xz")):  # single-stream (tar.* matched above)
        return "stream"
    return None


class _Budget:
    """Cumulative limits shared across one archive's whole nested tree."""

    def __init__(self, cfg: Config):
        cap_mb = getattr(cfg, "max_file_mb", 200) or 0
        self.member_cap = (cap_mb * 1024 * 1024) if cap_mb > 0 else 512 * 1024 * 1024
        # Cumulative uncompressed budget: 4× the single-file cap (same factor the
        # zip-bomb guard has used since SEC-01), with a sane floor.
        self.total_cap = max(self.member_cap * 4, 1024 * 1024 * 1024)
        self.entries_cap = max(1, getattr(cfg, "archive_max_entries", 100000))
        self.depth_cap = max(1, getattr(cfg, "archive_max_depth", 8))
        self.bytes = 0
        self.entries = 0

    def admit_entry(self) -> bool:
        self.entries += 1
        return self.entries <= self.entries_cap

    def admit_bytes(self, n: int) -> bool:
        self.bytes += n
        return self.bytes <= self.total_cap


class _BudgetExceeded(Exception):
    """Cumulative budget/entry cap breached → roll back the whole expansion."""


def _safe_member_path(name: str, dest: Path) -> Path | None:
    """Resolve a member name to a path inside ``dest``; None if it tries to escape."""
    if not name:
        return None
    # Normalise separators; reject absolute paths, drive letters, and parent refs.
    norm = name.replace("\\", "/")
    if norm.startswith("/") or (len(norm) > 1 and norm[1] == ":"):
        return None
    parts = [p for p in norm.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        return None
    target = dest.joinpath(*parts)
    try:
        target.resolve().relative_to(dest.resolve())
    except (ValueError, OSError):
        return None
    return target


def _copy_capped(src_fh, target: Path, declared: int, budget: _Budget) -> bool:
    """Stream-copy with hard caps. Returns False (member skipped) when the member
    alone exceeds the per-member cap; raises _BudgetExceeded on cumulative breach."""
    if declared > budget.member_cap:
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    copied = 0
    with open(target, "wb") as out:
        while True:
            chunk = src_fh.read(_CHUNK)
            if not chunk:
                break
            copied += len(chunk)
            if copied > budget.member_cap:          # declared size lied
                out.close()
                target.unlink(missing_ok=True)
                return False
            if not budget.admit_bytes(len(chunk)):
                out.close()
                target.unlink(missing_ok=True)
                raise _BudgetExceeded()
            out.write(chunk)
    return True


def _expand_zip(path: Path, dest: Path, budget: _Budget) -> None:
    with zipfile.ZipFile(path) as z:
        # Ratio guard up front (declared sizes; the stream caps below still bind).
        infos = z.infolist()
        total = sum(i.file_size for i in infos)
        comp = sum(i.compress_size for i in infos) or 1
        if total / comp > 200:
            raise _BudgetExceeded()
        for info in infos:
            if info.is_dir():
                continue
            if not budget.admit_entry():
                raise _BudgetExceeded()
            target = _safe_member_path(info.filename, dest)
            if target is None:
                continue                              # traversal attempt → skip member
            with z.open(info) as fh:
                _copy_capped(fh, target, info.file_size, budget)


def _expand_tar(path: Path, dest: Path, budget: _Budget) -> None:
    with tarfile.open(path) as t:                     # transparent gz/bz2/xz
        for member in t:
            if member.isdir():
                continue
            if not member.isreg():
                continue  # symlink/hardlink/device/FIFO → never extracted
            if not budget.admit_entry():
                raise _BudgetExceeded()
            target = _safe_member_path(member.name, dest)
            if target is None:
                continue
            fh = t.extractfile(member)
            if fh is None:
                continue
            with fh:
                _copy_capped(fh, target, member.size, budget)


def _expand_stream(path: Path, dest: Path, budget: _Budget) -> None:
    """Single-stream .gz/.bz2/.xz → one inner file named by stripping the suffix."""
    opener = _STREAM_OPENERS.get(path.suffix.lower())
    if opener is None:
        return
    inner = path.name[: -len(path.suffix)] or (path.name + ".out")
    target = _safe_member_path(inner, dest)
    if target is None:
        return
    if not budget.admit_entry():
        raise _BudgetExceeded()
    with opener(path, "rb") as fh:
        # No declared size for streams — the copy caps bind.
        _copy_capped(fh, target, 0, budget)


def _external_tool() -> list[str] | None:
    """argv prefix for the first available rar/7z extractor, or None."""
    if shutil.which("unar"):
        return ["unar", "-quiet", "-force-overwrite", "-output-directory"]
    for bin_ in ("7z", "7za", "7zz"):
        if shutil.which(bin_):
            return [bin_]
    return None


def _dir_size(path: Path) -> int:
    """Bytes of regular files under ``path`` (symlinks excluded)."""
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            p = Path(root) / name
            try:
                if not p.is_symlink():
                    total += p.stat().st_size
            except OSError:
                pass
    return total


def _run_extract_capped(argv: list[str], dest: Path, total_cap: int, timeout: int) -> int:
    """Run an external extractor, ABORTING if the extracted tree exceeds ``total_cap`` —
    the native zip/tar paths stream-cap *during* copy, but unar/7z write to disk before any
    post-walk could see them, so a rar/7z decompression bomb could fill the disk with only
    the wall-clock timeout as a bound. We poll ``dest`` size while it runs and kill + roll
    back on breach. Returns the process return code; raises ``_BudgetExceeded`` on a byte
    breach, ``OSError`` on timeout."""
    proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + timeout
    try:
        while True:
            try:
                rc = proc.wait(timeout=0.4)
            except subprocess.TimeoutExpired:
                rc = None
            if _dir_size(dest) > total_cap:
                raise _BudgetExceeded()
            if rc is not None:
                return rc
            if time.monotonic() > deadline:
                raise OSError("extractor timeout")
    finally:
        if proc.poll() is None:
            proc.kill()
            try:
                proc.wait(timeout=5)
            except (OSError, subprocess.SubprocessError):
                pass


def _expand_external(path: Path, dest: Path, budget: _Budget) -> bool:
    """rar/7z via unar or 7z. Bounded by ``total_cap`` DURING extraction (not just a post
    walk), then post-sanitised against the same budget. Returns False when no tool is
    available (caller reports a clean skip); raises ``_BudgetExceeded`` on a bomb so the
    whole expansion rolls back all-or-nothing."""
    tool = _external_tool()
    if tool is None:
        return False
    dest.mkdir(parents=True, exist_ok=True)
    if tool[0] == "unar":
        argv = tool + [str(dest), str(path)]
    else:
        argv = tool + ["x", "-y", f"-o{dest}", str(path)]
    try:
        rc = _run_extract_capped(argv, dest, budget.total_cap, _EXTERNAL_TIMEOUT)
        if rc != 0:
            raise OSError(f"extractor rc={rc}")
    except _BudgetExceeded:
        shutil.rmtree(dest, ignore_errors=True)
        raise                                    # bomb → all-or-nothing rollback (caller)
    except (OSError, subprocess.SubprocessError):
        shutil.rmtree(dest, ignore_errors=True)
        return False
    # Post-sanitise: drop symlinks, enforce entry + byte budgets on what landed.
    for root, dirnames, filenames in os.walk(dest, followlinks=False):
        for name in list(dirnames):
            p = Path(root) / name
            if p.is_symlink():
                p.unlink(missing_ok=True)
                dirnames.remove(name)
        for name in filenames:
            p = Path(root) / name
            if p.is_symlink():
                p.unlink(missing_ok=True)
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size > budget.member_cap:
                p.unlink(missing_ok=True)             # oversize member → skipped alone
                continue
            if not budget.admit_entry() or not budget.admit_bytes(size):
                raise _BudgetExceeded()
    return True


def _expand_into(path: Path, dest: Path, cfg: Config, budget: _Budget, depth: int) -> bool:
    """Expand one archive into ``dest`` (depth-first nested expansion). Returns False
    when this archive could not be expanded (no tool / corrupt)."""
    k = kind(path)
    if k is None or depth > budget.depth_cap:
        return False
    try:
        if k == "zip":
            _expand_zip(path, dest, budget)
        elif k == "tar":
            _expand_tar(path, dest, budget)
        elif k == "stream":
            _expand_stream(path, dest, budget)
        else:  # rar / 7z
            if not _expand_external(path, dest, budget):
                return False
    except _BudgetExceeded:
        raise
    except Exception:  # noqa: BLE001 — corrupt/torn archive must never crash a digest
        return False
    # Depth-first nested expansion: expand archives that landed inside dest, then
    # delete the nested archive file so the digest never double-processes it.
    if depth < budget.depth_cap:
        nested = [p for p in sorted(dest.rglob("*"))
                  if p.is_file() and not p.is_symlink() and kind(p) is not None]
        for arch in nested:
            sub = arch.parent / (arch.name + ".unpacked")
            if _expand_into(arch, sub, cfg, budget, depth + 1):
                arch.unlink(missing_ok=True)
    return True


def expand_archive(path: Path, cfg: Config) -> Path | None:
    """Expand ``path`` (recursively) into ``cfg.unpack_dir/<stem>-<sha8>/``.

    Returns the scratch directory containing the extracted tree, or None when the
    archive wasn't expanded (no rar/7z tool, corrupt, or a bomb/entry/depth budget
    breach — in which case everything extracted so far is rolled back)."""
    if kind(path) is None:
        return None
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(_CHUNK), b""):
                h.update(chunk)
        digest8 = h.hexdigest()[:8]
    except OSError:
        return None
    dest = cfg.unpack_dir / f"{path.stem[:60]}-{digest8}"
    shutil.rmtree(dest, ignore_errors=True)           # always a fresh, deterministic tree
    dest.mkdir(parents=True, exist_ok=True)
    budget = _Budget(cfg)
    try:
        ok = _expand_into(path, dest, cfg, budget, depth=1)
    except _BudgetExceeded:
        shutil.rmtree(dest, ignore_errors=True)       # all-or-nothing on budget breach
        return None
    if not ok:
        shutil.rmtree(dest, ignore_errors=True)
        return None
    return dest


def cleanup_unpacked(cfg: Config) -> None:
    """Remove the archive scratch tree (call after a digest/convert batch)."""
    shutil.rmtree(cfg.unpack_dir, ignore_errors=True)
