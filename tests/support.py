"""Test support helpers."""

from __future__ import annotations

from importlib import util
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str) -> ModuleType:
    """Load an integration module by file path without importing Home Assistant."""
    spec = util.spec_from_file_location(name, ROOT / relative_path)
    assert spec is not None
    assert spec.loader is not None
    module = util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
