"""WP-183 — the pure-Python fuzzy fallback is decision-equivalent to rapidfuzz, so a
core without the compiled rapidfuzz wheel (Termux/iOS, with the numpy-free WP-181a)
resolves entities identically and produces a byte-identical graph.

Two checks:
  * unit — `_fuzz.token_set_ratio` agrees with `rapidfuzz.fuzz.token_set_ratio` to ~1e-9
    and gives the SAME >=threshold decision (60/88/91/95) across corpus + random pairs;
  * integration — a subprocess with `rapidfuzz` import forced to fail digests the eval
    corpus and yields a `graph.json` byte-identical (same sha256) to the rapidfuzz build.

Offline; no network, no models.
"""
from __future__ import annotations

import json
import os
import random
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

from mta.core import _fuzz


def test_pyfuzz_matches_rapidfuzz_decisions():
    rf = pytest.importorskip("rapidfuzz")          # present in CI; compare against it
    tsr = rf.fuzz.token_set_ratio
    words = ["helios", "helios energy", "nordic grid authority", "nga", "project aurora",
             "project  aurora", "dr lena marsh", "lena marsh", "macdonald", "mcdonald",
             "theresa", "teresa", "reykjavik", "bergen", "korim", "korima", "jose", "cafe",
             "international atomic agency", "international atomic agencyy"]
    pairs = [(a, b) for i, a in enumerate(words) for b in words[i + 1:]]
    rng = random.Random(7)
    alpha = "abcdefghijklmnop "
    for _ in range(3000):
        a = "".join(rng.choice(alpha) for _ in range(rng.randint(2, 18))).strip()
        b = "".join(rng.choice(alpha) for _ in range(rng.randint(2, 18))).strip()
        pairs.append((a, b))
    for a, b in pairs:
        r = tsr(a, b)
        p = _fuzz.token_set_ratio(a, b)
        assert abs(r - p) < 1e-6, (a, b, r, p)
        for th in (60, 88, 91, 95):
            assert (r >= th) == (p >= th), (a, b, r, p, th)


_PROBE = textwrap.dedent(
    """
    import sys, json, hashlib
    from mta.core import resolve
    from mta.core.config import load
    from mta.core.digest import digest
    cfg = load().with_project("ff")
    digest(cfg, ["eval/corpus"])
    gp = cfg.graph_path
    print("RESULT " + json.dumps({
        "fuzz_impl": resolve._FUZZ_IMPL,
        "graph_sha": hashlib.sha256(gp.read_bytes()).hexdigest() if gp.exists() else None,
    }))
    """
)


def _run(home: Path, block_rapidfuzz: bool) -> dict:
    env = dict(os.environ)
    env.update(MTA_HOME=str(home), MTA_EXTRACT="classical",
               MTA_AUTO_UPDATE="off", MTA_NO_OLLAMA="1")
    if block_rapidfuzz:
        blocker = home.parent / "rf_blocker" / "rapidfuzz"
        blocker.mkdir(parents=True, exist_ok=True)
        # A fake `rapidfuzz` package whose import raises == "rapidfuzz not installed".
        (blocker / "__init__.py").write_text(
            'raise ImportError("WP-183 test: rapidfuzz is blocked")\n', encoding="utf-8")
        env["PYTHONPATH"] = str(blocker.parent) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-c", _PROBE], cwd=str(REPO),
                          env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"subprocess failed (block={block_rapidfuzz}):\n{proc.stderr}"
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT "))
    return json.loads(line[len("RESULT "):])


def test_graph_is_byte_identical_without_rapidfuzz(tmp_path):
    with_rf = _run(tmp_path / "home_rf", block_rapidfuzz=False)
    no_rf = _run(tmp_path / "home_norf", block_rapidfuzz=True)
    assert with_rf["fuzz_impl"] == "rapidfuzz"
    assert no_rf["fuzz_impl"] == "python", "the rapidfuzz block did not take effect"
    assert with_rf["graph_sha"] and no_rf["graph_sha"]
    assert with_rf["graph_sha"] == no_rf["graph_sha"], (
        "graph.json diverged between the rapidfuzz and pure-Python-fuzz builds")


def test_zero_compiled_deps_core_is_byte_identical(tmp_path):
    """Capstone: with BOTH compiled deps (numpy + rapidfuzz) blocked, a digest still
    completes and the graph is byte-identical to the full-deps build (WP-181a + WP-183)."""
    full = _run(tmp_path / "home_full", block_rapidfuzz=False)
    # Block numpy AND rapidfuzz on PYTHONPATH.
    home = tmp_path / "home_pure"
    bdir = tmp_path / "pure_blocker"
    (bdir / "rapidfuzz").mkdir(parents=True, exist_ok=True)
    (bdir / "rapidfuzz" / "__init__.py").write_text('raise ImportError("blocked")\n', encoding="utf-8")
    (bdir / "numpy.py").write_text('raise ImportError("blocked")\n', encoding="utf-8")
    env = dict(os.environ)
    env.update(MTA_HOME=str(home), MTA_EXTRACT="classical", MTA_AUTO_UPDATE="off", MTA_NO_OLLAMA="1")
    env["PYTHONPATH"] = str(bdir) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-c", _PROBE], cwd=str(REPO),
                          env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"zero-compiled-dep digest failed:\n{proc.stderr}"
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT "))
    pure = json.loads(line[len("RESULT "):])
    assert pure["fuzz_impl"] == "python"
    assert pure["graph_sha"] == full["graph_sha"], (
        "graph.json diverged with numpy+rapidfuzz both absent")
