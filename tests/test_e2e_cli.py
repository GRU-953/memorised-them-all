"""Phase-6 end-to-end tests — drive the INSTALLED `mta` CLI (clean wheel install),
not the editable package, so they exercise the shipped artifact + entry point.

Gated on MTA_E2E=1 (runs in the e2e workflow / locally), so the unit matrix skips it.
The offline lifecycle runs everywhere; the accurate-mode test additionally needs a
live Ollama and is gated on MTA_E2E_OLLAMA=1.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

if os.environ.get("MTA_E2E") != "1":
    pytest.skip("e2e CLI suite — set MTA_E2E=1 (runs in the e2e workflow)",
                allow_module_level=True)

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures"
MTA = shutil.which("mta") or "mta"


def _run(args, offline=True, timeout=600):
    env = {**os.environ, "MTA_AUTO_UPDATE": "off"}
    if offline:
        env["MTA_NO_OLLAMA"] = "1"
    else:
        env.pop("MTA_NO_OLLAMA", None)
    return subprocess.run([MTA, *args], capture_output=True, text=True,
                          env=env, timeout=timeout)


def _json(args, **kw):
    r = _run(args, **kw)
    assert r.returncode == 0, f"`mta {' '.join(args)}` failed:\n{r.stderr[-1200:]}"
    return json.loads(r.stdout)


def test_status_and_doctor():
    s = _json(["status"])
    assert s["status"] == "ok" and "platform" in s and "dependencies" in s
    d = _json(["doctor", "--dry-run"])
    assert d["status"] == "ok" and "scan" in d and "remediation" in d


def test_full_cli_lifecycle_offline(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    res = _json(["--project", "e2e", "digest", str(FIXTURES)])
    assert res["status"] == "ok" and res["stats"]["converted"] >= 5, res["stats"]
    assert res["stats"]["mode"] == "classical"            # offline → honest label
    assert "Lena Marsh" not in json.dumps(res)            # token-free: no raw doc text
    assert _json(["--project", "e2e", "overview"])["status"] == "ok"
    rc = _json(["--project", "e2e", "recall", "Who leads Project Aurora?"])
    assert rc["status"] == "ok" and all(len(h["text"]) <= 600 for h in rc["hits"])
    exp = _json(["--project", "e2e", "export", str(tmp_path / "out")])
    assert exp["status"] == "ok"
    mm = _json(["--project", "e2e", "mindmap"])
    assert mm["status"] == "ok" and Path(mm["path"]).exists()
    html = Path(mm["path"]).read_text(encoding="utf-8")
    assert "cytoscape" in html.lower() and "unpkg" not in html and "<script src=" not in html
    assert _json(["--project", "e2e", "forget"])["status"] == "ok"
    assert not (tmp_path / "projects" / "e2e").exists()


def test_fast_mode_cli(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    res = _json(["--project", "f", "digest", str(FIXTURES), "--fast"])
    assert res["status"] == "ok" and res["stats"]["mode"] == "fast"


def test_offline_recall_declines_offtopic(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    _json(["--project", "ot", "digest", str(FIXTURES)])
    rc = _json(["--project", "ot", "recall", "xylophone zebra quantum chromodynamics"])
    assert rc["low_confidence"] is True                   # offline declinable (DOC-01)


def test_constrained_zip_bomb_no_crash(tmp_path):
    os.environ["MTA_HOME"] = str(tmp_path)
    z = tmp_path / "bomb.docx"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", "a" * (8 * 1024 * 1024))
    res = _json(["--project", "bomb", "digest", str(z)])
    assert res["status"] in ("ok", "no_input")            # bomb skipped, never crashes
    assert res.get("stats", {}).get("converted", 0) == 0


@pytest.mark.skipif(os.environ.get("MTA_E2E_OLLAMA") != "1",
                    reason="accurate-mode E2E needs a live Ollama (set MTA_E2E_OLLAMA=1)")
def test_accurate_mode_e2e(tmp_path):
    """Full pipeline through the real local LLM: digest (accurate) → recall with
    real embeddings. Uses the host's already-running Ollama (left untouched)."""
    os.environ["MTA_HOME"] = str(tmp_path)
    res = _json(["--project", "acc", "digest", str(FIXTURES)], offline=False, timeout=1200)
    assert res["status"] == "ok"
    assert res["stats"]["mode"] == "accurate"
    assert res["stats"]["embed_mode"] == "ollama"
    assert res["stats"]["entities"] > 0
    rc = _json(["--project", "acc", "recall", "Who leads Project Aurora?"], offline=False)
    assert rc["status"] == "ok" and "low_confidence" in rc and "top_score" in rc
