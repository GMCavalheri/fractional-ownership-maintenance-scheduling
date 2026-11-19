import tomllib
from pathlib import Path

import pmo.ga
import smallfleet

import fracsched

ROOT = Path(__file__).resolve().parents[1]


def test_version_matches_pyproject() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert fracsched.__version__ == project["version"]


def test_reused_packages_import() -> None:
    # AVR-04's GA and EJD-01's conjugate model are pinned by git tag (pyproject.toml).
    assert hasattr(pmo.ga, "run_ga")
    assert smallfleet.__version__ == "1.0.0"
