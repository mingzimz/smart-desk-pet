"""Source checkout entry point; installed builds use smart-desktop-pet."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from smart_desktop_pet.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
