#!/usr/bin/env python3
"""Capture the device adoption screenshots.

A shim over capture.py with --manifest adoption preselected. These shots are
separate because the adoption queue has to be staged by hand: power on an
unadopted device, leave it un-approved, then run this.

    uv run --group screenshots scripts/screenshots/capture_adoption.py --checklist
    uv run --group screenshots scripts/screenshots/capture_adoption.py

Every capture.py flag still works and is passed straight through.
"""

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import capture  # noqa: E402


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    return capture.main(["--manifest", "adoption", *argv])


if __name__ == "__main__":
    raise SystemExit(main())
