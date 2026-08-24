"""Declarative binary patch catalog and application engine."""

from .catalog import PatchCatalog
from .engine import apply_patch

__all__ = ["PatchCatalog", "apply_patch"]

