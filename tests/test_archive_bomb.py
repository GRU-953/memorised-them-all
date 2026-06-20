"""WP-92 — rar/7z external extraction is bounded DURING extraction (SEC-1).

unar/7z write to disk before any post-walk could see them, so a rar/7z decompression bomb
could fill the disk with only the 600s wall-clock timeout as a bound (the native zip/tar
paths stream-cap during copy). `_run_extract_capped` now polls the extracted tree and kills
the extractor + rolls back the moment it crosses the cumulative byte budget.

Tested with a synthetic flooding subprocess so it runs on the CI matrix without a real
rar/7z tool installed.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

os.environ.setdefault("MTA_AUTO_UPDATE", "off")

from mta.core import archive

_FLOOD = (
    "import sys, os, time\n"
    "d = sys.argv[1]\n"
    "blk = b'x' * (1024 * 1024)\n"
    "with open(os.path.join(d, 'bomb.bin'), 'wb') as f:\n"
    "    for _ in range(400):\n"
    "        f.write(blk); f.flush(); time.sleep(0.01)\n"
)
_SMALL = (
    "import sys, os\n"
    "open(os.path.join(sys.argv[1], 'ok.txt'), 'w').write('hello' * 100)\n"
)
_HANG = "import time\ntime.sleep(30)\n"


def test_capped_extract_aborts_a_disk_bomb(tmp_path):
    dest = tmp_path / "out"
    dest.mkdir()
    argv = [sys.executable, "-c", _FLOOD, str(dest)]
    with pytest.raises(archive._BudgetExceeded):
        archive._run_extract_capped(argv, dest, total_cap=8 * 1024 * 1024, timeout=30)
    # the flooding child must have been killed well before writing its full 400 MB
    assert archive._dir_size(dest) < 80 * 1024 * 1024


def test_capped_extract_completes_under_budget(tmp_path):
    dest = tmp_path / "out2"
    dest.mkdir()
    argv = [sys.executable, "-c", _SMALL, str(dest)]
    rc = archive._run_extract_capped(argv, dest, total_cap=10 * 1024 * 1024, timeout=30)
    assert rc == 0
    assert (dest / "ok.txt").exists()


def test_capped_extract_enforces_timeout(tmp_path):
    dest = tmp_path / "out3"
    dest.mkdir()
    argv = [sys.executable, "-c", _HANG, str(dest)]
    with pytest.raises(OSError):
        archive._run_extract_capped(argv, dest, total_cap=10 * 1024 * 1024, timeout=1)
    # the hung child is killed by the finally-block (no orphan)
    # (a poll after kill should not raise)
