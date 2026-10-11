"""Make the lane62 suite independent of the directory pytest is started from.

The tests read the lane's own evidence/ and docs/ trees with relative paths, so
the session chdirs to the lane root (the parent of tests/) before collection.
The same conftest puts lane62/src on sys.path, so `python3 -m pytest lane62/tests`
works from the repository root as well as from inside lane62/.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

LANE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LANE / "src"))


def pytest_configure(config):
    os.chdir(LANE)
