"""WP-181a — the core digests + recalls with numpy ABSENT, byte-identically.

numpy is a heavy compiled wheel that doesn't install cleanly on Termux/iOS, so the
slim/mobile core must work without it. This proves it *in CI* (where numpy IS installed)
by spawning a subprocess whose `import numpy` is forced to fail (a fake `numpy` module on
PYTHONPATH that raises ImportError — exactly simulating "numpy not installed").

Asserts:
  * the package imports and a full digest + recall complete with numpy unavailable;
  * recall still finds the answer (it reads the meta sidecar, never the matrix);
  * the numpy-free store writes NO `vectors.npz` but DOES write the `vectors.json`
    sidecar + `bm25_index.json`;
  * the resolved `graph.json` is **byte-identical** (same sha256) to the numpy build —
    i.e. the pure-Python embedding reproduces the exact merge decision (WP-181a / [C1]).

Fully offline (classical extraction + hashing embeddings); no network, no models.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Runs in a subprocess: digest the committed eval corpus, recall one query, and report a
# JSON summary (numpy availability, recall hit, graph sha256, which store files exist).
_PROBE = textwrap.dedent(
    """
    import sys, json, hashlib
    try:
        import numpy  # noqa: F401
        numpy_ok = True
    except Exception:
        numpy_ok = False
    from mta.core.config import load
    from mta.core.digest import digest
    from mta.core.recall import recall
    cfg = load().with_project("nf")
    digest(cfg, ["eval/corpus"])
    out = recall(cfg, "Where is the Nordic Grid Authority based?", k=8)
    blob = " ".join((h.get("label", "") + " " + h.get("text", "")) for h in out.get("hits", [])).lower()
    hit = ("oslo" in blob) or ("nordic grid authority" in blob)
    gp = cfg.graph_path
    vp = cfg.vectors_path
    print("RESULT " + json.dumps({
        "numpy_ok": numpy_ok,
        "hit": hit,
        "graph_sha": hashlib.sha256(gp.read_bytes()).hexdigest() if gp.exists() else None,
        "has_npz": vp.exists(),
        "has_sidecar": vp.with_suffix(".json").exists(),
        "has_bm25": cfg.bm25_index_path.exists(),
    }))
    """
)


def _run(home: Path, block_numpy: bool) -> dict:
    env = dict(os.environ)
    env.update(MTA_HOME=str(home), MTA_EXTRACT="classical",
               MTA_AUTO_UPDATE="off", MTA_NO_OLLAMA="1")
    if block_numpy:
        blocker = home.parent / "numpy_blocker"
        blocker.mkdir(parents=True, exist_ok=True)
        # A fake top-level `numpy` that raises on import == "numpy not installed".
        (blocker / "numpy.py").write_text(
            'raise ImportError("WP-181a test: numpy is blocked")\n', encoding="utf-8")
        env["PYTHONPATH"] = str(blocker) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run([sys.executable, "-c", _PROBE], cwd=str(REPO),
                          env=env, capture_output=True, text=True)
    assert proc.returncode == 0, f"subprocess failed (block_numpy={block_numpy}):\n{proc.stderr}"
    line = next(ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT "))
    return json.loads(line[len("RESULT "):])


def test_digest_and_recall_work_without_numpy(tmp_path):
    r = _run(tmp_path / "home_nonumpy", block_numpy=True)
    assert r["numpy_ok"] is False, "the numpy block did not take effect"
    assert r["hit"] is True, "recall failed to find the answer without numpy"
    assert r["has_sidecar"] and r["has_bm25"], "numpy-free digest must write the sidecar + BM25 index"
    assert r["has_npz"] is False, "numpy-free store must NOT write vectors.npz"


def test_graph_is_byte_identical_with_and_without_numpy(tmp_path):
    with_np = _run(tmp_path / "home_np", block_numpy=False)
    no_np = _run(tmp_path / "home_nonp", block_numpy=True)
    assert with_np["numpy_ok"] is True and no_np["numpy_ok"] is False
    assert with_np["graph_sha"] and no_np["graph_sha"]
    # The pure-Python embedding reproduces the EXACT merge decision → identical graph.
    assert with_np["graph_sha"] == no_np["graph_sha"], (
        "graph.json diverged between the numpy and numpy-free builds")
    assert with_np["has_npz"] is True and no_np["has_npz"] is False
