from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def package_root() -> Path:
    """The builds/quality-gate directory holding the real config/."""
    return PACKAGE_ROOT


@pytest.fixture
def config_root(tmp_path: Path) -> Path:
    """A throwaway package root whose config/ holds a copy of the real gate.toml only."""
    (tmp_path / "config" / "facts").mkdir(parents=True)
    (tmp_path / "config" / "gate.toml").write_bytes(
        (PACKAGE_ROOT / "config" / "gate.toml").read_bytes()
    )
    return tmp_path
