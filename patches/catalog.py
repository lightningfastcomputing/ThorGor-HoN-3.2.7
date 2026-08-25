from __future__ import annotations

import json
from pathlib import Path

from thorgor.paths import PATCH_CATALOG
from .models import PatchManifest


class PatchCatalog:
    def __init__(self, root: Path = PATCH_CATALOG) -> None:
        self.root = root

    def all(self) -> tuple[PatchManifest, ...]:
        manifests = [
            PatchManifest.from_dict(json.loads(path.read_text(encoding="utf-8")), path)
            for path in sorted(self.root.glob("*.json"))
        ]
        ids = [manifest.patch_id for manifest in manifests]
        if len(ids) != len(set(ids)):
            raise ValueError("patch catalog contains duplicate ids")
        return tuple(manifests)

    def get(self, patch_id: str) -> PatchManifest:
        for manifest in self.all():
            if manifest.patch_id == patch_id:
                return manifest
        raise KeyError(f"unknown patch: {patch_id}")

