"""Pipeline-local pytest config (does not replace backend/tests/conftest.py)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow `import backend...` before co-1 adds backend/__init__.py + root conftest.
_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def synthetic_dataset(tmp_path: Path) -> Path:
    from backend.tests.fixtures.synthetic_tree import build_synthetic_dataset

    return build_synthetic_dataset(tmp_path / "raw")
