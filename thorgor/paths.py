from __future__ import annotations

import os
import sys
from pathlib import Path


def package_root() -> Path:
    """Return the portable package directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


PACKAGE_ROOT = package_root()
SOURCE_ROOT = PACKAGE_ROOT.parent
ROOT = Path(os.environ.get("THORGOR_DATA_HOME", PACKAGE_ROOT / "var")).expanduser().resolve()
ROOT.mkdir(parents=True, exist_ok=True)
(ROOT / "chat-server").mkdir(exist_ok=True)
WORK = ROOT / "work"
DOCS = SOURCE_ROOT / "docs"
PACKAGED_CATALOG = PACKAGE_ROOT / "patches" / "catalog_data"
PATCH_CATALOG = PACKAGED_CATALOG
