"""Cross-platform CPU/RAM tuning.

Sizes the process pool to the number of *performance* cores, pins each worker's
native math libraries to a single thread (avoiding oversubscription), and reports
available-memory headroom. Tuned for Apple M-series but degrades cleanly to portable
defaults on Linux/Windows/Intel so CI works everywhere.
"""
from __future__ import annotations

import functools
import os
import platform
import subprocess

# Pinning these to 1 thread per worker is the single biggest win when running a
# process pool on Apple silicon: each worker gets one performance core and the
# BLAS/OpenMP backends don't fight over the others.
_THREAD_VARS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS")


def is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _sysctl_int(key: str) -> int | None:
    try:
        out = subprocess.run(["sysctl", "-n", key], capture_output=True,
                             text=True, timeout=3)
        if out.returncode == 0 and out.stdout.strip():
            return int(out.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _psutil():
    try:
        import psutil
        return psutil
    except Exception:
        return None


@functools.lru_cache(maxsize=1)
def performance_cores() -> int:
    """Best available "real work" core count, portable across OSes.

    Apple silicon → performance cores (perflevel0). Elsewhere → physical cores via
    psutil (avoids oversubscribing hyperthreaded Intel/Linux/Windows boxes), then
    logical CPUs as a last resort.
    """
    if is_apple_silicon():
        p = _sysctl_int("hw.perflevel0.physicalcpu")
        if p:
            return p
    ps = _psutil()
    if ps:
        try:
            phys = ps.cpu_count(logical=False)
            if phys:
                return phys
        except Exception:
            pass
    return os.cpu_count() or 4


@functools.lru_cache(maxsize=1)
def _host_memory_gb() -> float:
    """Host RAM in GB (Apple sysctl → psutil → POSIX sysconf → 8)."""
    if is_apple_silicon():
        b = _sysctl_int("hw.memsize")
        if b:
            return b / (1024 ** 3)
    ps = _psutil()
    if ps:
        try:
            return ps.virtual_memory().total / (1024 ** 3)
        except Exception:  # noqa: BLE001
            pass
    try:  # POSIX fallback (no Windows)
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / (1024 ** 3)
    except (ValueError, OSError, AttributeError):
        return 8.0


def _cgroup_mem_limit_gb() -> float | None:
    """The cgroup memory ceiling in GB, or None if unset/unlimited/non-Linux.

    Reads cgroup v2 (``memory.max``) then v1 (``memory.limit_in_bytes``). Containers
    (Docker / Kubernetes / CI) cap memory here while the HOST total is what sysctl/
    psutil report — without this, auto-tiering can pick a profile that OOMs inside a
    small container on a big host."""
    for path in ("/sys/fs/cgroup/memory.max",
                 "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        try:
            with open(path) as f:
                raw = f.read().strip()
        except OSError:
            continue
        if not raw or raw == "max":
            continue
        try:
            gb = int(raw) / (1024 ** 3)
        except ValueError:
            continue
        if 0.1 < gb < 100000:   # v1 uses a ~2^63 sentinel for "unlimited" — ignore it
            return gb
    return None


@functools.lru_cache(maxsize=1)
def memory_gb() -> float:
    """Total RAM in GB — portable (Apple sysctl → psutil → POSIX sysconf → 8), capped
    by any cgroup limit.

    Honors an ``MTA_MEMORY_GB`` override first (forces a tier on a misreporting sandbox).
    Otherwise takes ``min(host, cgroup-limit)`` so a memory-capped container sizes to a
    safe tier instead of the host's (possibly huge) total."""
    ovr = os.environ.get("MTA_MEMORY_GB", "").strip()
    if ovr:
        try:
            v = float(ovr)
            if v > 0:
                return round(v, 1)
        except ValueError:
            pass
    host = _host_memory_gb()
    lim = _cgroup_mem_limit_gb()
    return round(min(host, lim), 1) if (lim is not None and lim < host) else round(host, 1)


def worker_count(requested: int = 0) -> int:
    """Resolve the conversion pool size.

    Clamps by unified memory (each markitdown/Office worker can transiently hold a
    few hundred MB) so a small box doesn't thrash. A 4 GB-class machine — the new
    default target — runs a SINGLE conversion worker.
    """
    if requested and requested > 0:
        return max(1, requested)
    if memory_gb() < 6:                       # 4 GB-class box → one worker, no OOM
        return 1
    cores = performance_cores()
    mem_cap = max(1, int(memory_gb() // 2))   # ~2 GB headroom per worker
    return max(1, min(cores, mem_cap, 8))



def pin_native_threads() -> None:
    """Pin BLAS/OpenMP to one thread. Call in each worker before heavy imports."""
    for var in _THREAD_VARS:
        os.environ.setdefault(var, "1")



_PATH_HEALED = False


def bootstrap_path() -> None:
    """Prepend common Homebrew/system bin dirs to PATH (idempotent).

    Host apps like Claude Desktop launch the server with a very sparse PATH, so
    ``tesseract``/``ffmpeg`` may not resolve. This makes them findable
    without changing the user's shell config.
    """
    global _PATH_HEALED
    if _PATH_HEALED:
        return
    if os.name == "nt":  # Windows: common install locations for the CLI tools
        extra = [
            os.path.expandvars(r"%ProgramFiles%\Tesseract-OCR"),
            os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin"),
            os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Links"),
            os.path.expanduser(r"~\scoop\shims"),
            os.path.expandvars(r"%ProgramData%\chocolatey\bin"),
        ]
    else:  # macOS / Linux: Homebrew, system, snap, user-local
        extra = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin",
                 "/snap/bin", os.path.expanduser("~/.local/bin")]
    cur = os.environ.get("PATH", "").split(os.pathsep)
    missing = [p for p in extra if p not in cur and os.path.isdir(p)]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing + cur)
    _PATH_HEALED = True


def summary() -> dict:
    return {
        "apple_silicon": is_apple_silicon(),
        "machine": platform.machine(),
        "performance_cores": performance_cores(),
        "memory_gb": memory_gb(),
        "workers": worker_count(),
        "engine": "deterministic",
        "model_free": True,
    }
