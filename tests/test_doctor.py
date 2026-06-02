"""WP-12 — dependency scanner + `mta doctor` (R3). Offline; monkeypatched probes."""
from __future__ import annotations

import os
import sys

os.environ.setdefault("MTA_NO_OLLAMA", "1")
os.environ.setdefault("MTA_AUTO_UPDATE", "off")


def test_vtuple_compare():
    from mta.core.deps import _vtuple
    assert _vtuple("1.26.4") >= _vtuple("1.26")
    assert _vtuple("0.1.6") >= _vtuple("0.1.6")
    assert _vtuple("0.1.5") < _vtuple("0.1.6")
    assert _vtuple("2.0") > _vtuple("1.99.99")


def test_parse_req():
    from mta.core.deps import _parse_req
    assert _parse_req("numpy>=1.26") == ("numpy", "1.26", False)
    name, ver, opt = _parse_req("markitdown[pdf,docx]>=0.1.6")
    assert name == "markitdown" and ver == "0.1.6" and opt is False
    name, _ver, opt = _parse_req("pytest>=8.0; extra == 'dev'")
    assert name == "pytest" and opt is True


def test_scan_statuses(monkeypatch):
    from mta.core import deps
    monkeypatch.setattr(deps._md, "requires", lambda pkg: [
        "numpy>=1.26", "rapidfuzz>=3.6", "ghostpkg>=1.0", "pytest>=8.0; extra == 'dev'"])
    versions = {"numpy": "1.26.4", "rapidfuzz": "3.0.0", "ghostpkg": None}
    monkeypatch.setattr(deps, "_installed_version", lambda n: versions.get(n))
    monkeypatch.setattr(deps.shutil, "which",
                        lambda b: "/usr/bin/" + b if b == "ffmpeg" else None)
    r = deps.scan(probe_bin_versions=False)
    by = {d["name"]: d["status"] for d in r["python"]}
    assert by == {"numpy": "ok", "rapidfuzz": "outdated", "ghostpkg": "missing"}  # dev extra skipped
    binp = {b["name"]: b["present"] for b in r["binaries"]}
    assert binp == {"ollama": False, "tesseract": False, "ffmpeg": True}
    assert r["all_ok"] is False


def test_remediation_pip_for_python():
    from mta.core import deps
    result = {"python": [{"name": "rapidfuzz", "status": "outdated"},
                         {"name": "numpy", "status": "ok"}],
              "binaries": [{"name": n, "present": True} for n in ("ollama", "tesseract", "ffmpeg")]}
    pip = [c for c in deps.remediation(result) if c["for"] == "python"]
    assert pip and pip[0]["argv"][:4] == [sys.executable, "-m", "pip", "install"]
    assert "rapidfuzz" in pip[0]["argv"] and "numpy" not in pip[0]["argv"]
    assert pip[0]["auto"] is True


def test_doctor_dry_run_applies_nothing(monkeypatch):
    from mta.core import deps
    monkeypatch.setattr(deps, "scan", lambda cfg=None: {
        "python": [{"name": "x", "status": "missing"}], "binaries": [],
        "summary": {"ok": 0, "outdated": 0, "missing": 1}, "all_ok": False})
    ran = []
    monkeypatch.setattr(deps, "_run", lambda argv: ran.append(argv) or True)
    out = deps.doctor(fix=True, dry_run=True)
    assert out["applied"] == [] and ran == []          # dry-run runs nothing


def test_doctor_fix_runs_pip_only(monkeypatch):
    from mta.core import deps
    monkeypatch.setattr(deps, "scan", lambda cfg=None: {
        "python": [{"name": "x", "status": "outdated"}],
        "binaries": [{"name": "ollama", "present": False}],
        "summary": {"ok": 0, "outdated": 1, "missing": 1}, "all_ok": False})
    monkeypatch.setattr(deps.shutil, "which", lambda b: "/usr/bin/brew" if b == "brew" else None)
    ran = []
    monkeypatch.setattr(deps, "_run", lambda argv: ran.append(argv) or True)
    out = deps.doctor(fix=True)
    assert len(ran) == 1 and ran[0][:3] == [sys.executable, "-m", "pip"]   # pip only
    assert any(c["for"] == "system" and not c["auto"] for c in out["remediation"])  # brew suggested, not run
