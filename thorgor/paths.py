from __future__ import annotations

import sys
from pathlib import Path


def package_root() -> Path:
    """Return the portable package directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


PACKAGE_ROOT = package_root()
SOURCE_ROOT = PACKAGE_ROOT.parent
RUNTIME = PACKAGE_ROOT / "runtime"

# A copied `thorgor` directory is self-contained. During development the same
# bundled runtime is used, ensuring portable and repository launches exercise
# exactly the same files.
ROOT = RUNTIME if RUNTIME.is_dir() else SOURCE_ROOT
WORK = ROOT / "work"
DOCS = SOURCE_ROOT / "docs"
PACKAGED_CATALOG = PACKAGE_ROOT / "patches" / "catalog_data"
PATCH_CATALOG = PACKAGED_CATALOG if PACKAGED_CATALOG.is_dir() else SOURCE_ROOT / "patches" / "catalog"
