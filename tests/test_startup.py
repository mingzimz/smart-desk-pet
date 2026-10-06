import os
from pathlib import Path
import subprocess
import sys


def test_actual_entry_point_starts_saves_and_unlocks(tmp_path):
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ, PYTHONPATH=str(root / "src"), QT_QPA_PLATFORM="offscreen")
    script = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox
from smart_desktop_pet.app import main
from smart_desktop_pet.controller import PetController
QMessageBox.critical = lambda parent, title, message: print(message, file=sys.stderr, flush=True)
QMessageBox.information = lambda parent, title, message: print(message, file=sys.stderr, flush=True)
original_start = PetController.start
def short_start(self):
    original_start(self, tray=False)
    QTimer.singleShot(150, self.quit)
PetController.start = short_start
raise SystemExit(main(['--data-dir', sys.argv[1], '--demo']))
"""
    try:
        result = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            env=environment,
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError((exc.stderr or b"startup timed out").decode(errors="replace")) from exc
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    assert (tmp_path / "config.json").exists()
    assert (tmp_path / "memory.json").exists()
    assert (tmp_path / "app.log").exists()
    assert not (tmp_path / "app.lock").exists()
