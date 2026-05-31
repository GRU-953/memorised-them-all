"""Apple M-series first platform tuning.

Sizes the process pool to the number of *performance* cores, pins each worker's
native math libraries to a single thread (avoiding oversubscription on the
unified-memory Apple GPU/CPU), reports unified-memory headroom, and detects
whether GPU-accelerated Whisper via Apple MLX is available. Everything degrades
cleanly to portable defaults on non-Apple hardware so CI on Linux still works.
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


@functools.lru_cache(maxsize=1)
def performance_cores() -> int:
    """Performance cores on Apple silicon (perflevel0); logical CPUs elsewhere."""
    if is_apple_silicon():
        p = _sysctl_int("hw.perflevel0.physicalcpu")
        if p:
            return p
    return os.cpu_count() or 4


@functools.lru_cache(maxsize=1)
def memory_gb() -> float:
    if is_apple_silicon():
        b = _sysctl_int("hw.memsize")
        if b:
            return round(b / (1024 ** 3), 1)
    try:  # portable fallback
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
                     / (1024 ** 3), 1)
    except (ValueError, OSError):
        return 8.0


def worker_count(requested: int = 0) -> int:
    """Resolve the pool size.

    On Apple silicon we cap to performance cores and further clamp by unified
    memory (each markitdown/Office worker can transiently hold a few hundred MB),
    so a 16 GB Mac doesn't thrash.
    """
    if requested and requested > 0:
        return max(1, requested)
    cores = performance_cores()
    mem_cap = max(2, int(memory_gb() // 2))  # ~2 GB headroom per worker
    return max(1, min(cores, mem_cap, 8))


def pin_native_threads() -> None:
    """Pin BLAS/OpenMP to one thread. Call in each worker before heavy imports."""
    for var in _THREAD_VARS:
        os.environ.setdefault(var, "1")


@functools.lru_cache(maxsize=1)
def mlx_available() -> bool:
    """GPU-accelerated Whisper via Apple MLX (arm64 macOS only)."""
    if not is_apple_silicon():
        return False
    try:
        import importlib.util
        return importlib.util.find_spec("mlx_whisper") is not None
    except Exception:
        return False


def summary() -> dict:
    return {
        "apple_silicon": is_apple_silicon(),
        "machine": platform.machine(),
        "performance_cores": performance_cores(),
        "memory_gb": memory_gb(),
        "workers": worker_count(),
        "mlx_whisper": mlx_available(),
    }
