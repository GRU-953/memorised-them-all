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
def memory_gb() -> float:
    """Total RAM in GB — portable (Apple sysctl → psutil → POSIX sysconf → 8)."""
    if is_apple_silicon():
        b = _sysctl_int("hw.memsize")
        if b:
            return round(b / (1024 ** 3), 1)
    ps = _psutil()
    if ps:
        try:
            return round(ps.virtual_memory().total / (1024 ** 3), 1)
        except Exception:
            pass
    try:  # POSIX fallback (no Windows)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
                     / (1024 ** 3), 1)
    except (ValueError, OSError, AttributeError):
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


@functools.lru_cache(maxsize=1)
def detect_gpu() -> str:
    """Best available local accelerator: 'mlx' (Apple), 'cuda', 'rocm', or 'none'.

    Cached — hardware doesn't change within a run.
    """
    if mlx_available():
        return "mlx"
    import shutil
    if shutil.which("nvidia-smi"):
        try:
            r = subprocess.run(["nvidia-smi", "-L"], capture_output=True,
                               text=True, timeout=3)
            if r.returncode == 0 and "GPU" in r.stdout:
                return "cuda"
        except (OSError, subprocess.SubprocessError):
            pass
    if shutil.which("rocminfo"):
        return "rocm"
    return "none"


def lm_studio_running(host: str = "http://127.0.0.1:1234") -> bool:
    """Detect a local LM Studio (OpenAI-compatible) server. Best-effort, ~1s; NOT
    cached (it's runtime service state). Used only for status/doctor reporting."""
    import urllib.error
    import urllib.request
    try:
        with urllib.request.urlopen(f"{host.rstrip('/')}/v1/models", timeout=1.0) as r:
            return r.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


_PATH_HEALED = False


def bootstrap_path() -> None:
    """Prepend common Homebrew/system bin dirs to PATH (idempotent).

    Host apps like Claude Desktop launch the server with a very sparse PATH, so
    ``tesseract``/``ffmpeg``/``ollama`` may not resolve. This makes them findable
    without changing the user's shell config.
    """
    global _PATH_HEALED
    if _PATH_HEALED:
        return
    if os.name == "nt":  # Windows: common install locations for the CLI tools
        extra = [
            os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama"),
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
        "mlx_whisper": mlx_available(),
        "gpu": detect_gpu(),
        "lm_studio": lm_studio_running(),
    }
