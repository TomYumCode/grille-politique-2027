"""Service de notifications (notifications/, Cloudflare Worker) : ses tests JavaScript, avec Node si présent."""

import shutil
import subprocess
from pathlib import Path

import pytest

DOSSIER = Path(__file__).resolve().parent.parent / "notifications"
NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node absent")
def test_service_de_notifications():
    fichiers = sorted(str(p) for p in (DOSSIER / "test").glob("*.test.mjs"))
    r = subprocess.run([NODE, "--test", *fichiers], capture_output=True, text=True, cwd=DOSSIER)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
