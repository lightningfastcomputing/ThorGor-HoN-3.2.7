"""Temporary adapters around frozen v77 entry points.

These imports are deliberately centralized. As code moves into the package,
the corresponding adapter can disappear without changing callers.
"""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache
from pathlib import Path

from .paths import ROOT


@lru_cache(maxsize=None)
def load_legacy(name: str, relative_path: str):
    path = ROOT / Path(relative_path)
    spec = importlib.util.spec_from_file_location(f"thorgor._compat.{name}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load ThorGor compatibility module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

