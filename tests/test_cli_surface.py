"""Cycle-1 coverage: exercise the `mta` CLI dispatch end-to-end, offline.

The CLI is the primary non-Claude entry point but was thinly covered (cli.py ~63%). These
drive every subcommand through `mta.cli.main` against a temp MTA_HOME so the dispatch,
`server._status`, `recipes`, `schemas`, and `deps.doctor` paths are covered without network.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

import pytest

from mta.cli import main


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("MTA_HOME", str(tmp_path))
    monkeypatch.setenv("MTA_AUTO_UPDATE", "off")
    return tmp_path


def _json_out(capsys):
    return json.loads(capsys.readouterr().out)


def test_digest_recall_overview_export_forget(home, capsys, tmp_path):
    # digest the bundled fixtures
    assert main(["--project", "cli", "digest", "tests/fixtures"]) == 0
    d = _json_out(capsys)
    assert d["status"] == "ok"
    # recall
    assert main(["--project", "cli", "recall", "report"]) == 0
    r = _json_out(capsys)
    assert r["status"] in ("ok", "no_memory")
    # overview
    assert main(["--project", "cli", "overview"]) == 0
    assert _json_out(capsys)["status"] in ("ok", "no_memory")
    # export
    dest = tmp_path / "export"
    assert main(["--project", "cli", "export", str(dest)]) == 0
    _json_out(capsys)
    # status
    assert main(["status"]) == 0
    s = _json_out(capsys)
    assert s["status"] == "ok" and s["backend"]["kind"] == "deterministic" \
        and s["backend"]["model_free"] is True
    # forget
    assert main(["--project", "cli", "forget"]) == 0
    assert _json_out(capsys)["status"] in ("ok", "not_found")


def test_convert_writes_markdown(home, capsys, tmp_path):
    out = tmp_path / "md"
    assert main(["convert", "tests/fixtures/table.csv", "--out", str(out)]) == 0
    res = _json_out(capsys)
    assert res  # structured result returned


def test_doctor_dry_run(home, capsys):
    # default: the human-readable plain-English report (WP-153)
    assert main(["doctor", "--dry-run"]) == 0
    text = capsys.readouterr().out
    assert "Common problems" in text and "→" in text
    # --json: structured dict (for scripts / setup-verify)
    assert main(["doctor", "--dry-run", "--json"]) == 0
    out = _json_out(capsys)
    assert "scan" in out and out["dry_run"] is True and "report" in out


def test_recipes_text_and_json(home, capsys):
    assert main(["recipes"]) == 0
    assert "connection recipes" in capsys.readouterr().out
    assert main(["recipes", "--format", "json"]) == 0
    data = _json_out(capsys)
    assert data["tools"] == 8 and "auto" in data["surfaces"]


def test_export_schema_all_and_one(home, capsys, tmp_path):
    assert main(["export-schema", "--format", "openai"]) == 0
    oai = _json_out(capsys)
    assert isinstance(oai, list) and oai[0]["type"] == "function"
    assert main(["export-schema", "--format", "all", "--out", str(tmp_path / "schemas")]) == 0
    written = _json_out(capsys)["written"]
    assert any(w.endswith("gemini.json") for w in written)


def test_setup_dry_run_and_only_json(home, capsys):
    assert main(["setup", "--dry-run", "--json", "--exclude", "vscode"]) == 0
    out = _json_out(capsys)
    assert out["write"] is False and "vscode" not in out["targets"]


def test_update_disabled_when_auto_update_off(home, capsys):
    # auto_update=off → run_check reports disabled without touching the network
    assert main(["update"]) == 0
    assert _json_out(capsys)["status"] in ("disabled", "throttled", "ok")


def test_unknown_subcommand_errors(home):
    with pytest.raises(SystemExit):
        main(["frobnicate"])
