from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .catalog import PatchCatalog
from .engine import apply_patch
from .installer import install_supported_patches, verify_supported_install


def run(args) -> int:
    catalog = PatchCatalog()
    if args.action in ("install", "verify"):
        if not args.hon_home:
            raise SystemExit(f"{args.action} requires --hon-home PATH")
        operation = install_supported_patches if args.action == "install" else verify_supported_install
        for message in operation(Path(args.hon_home)):
            print(message)
        return 0
    if args.action == "list":
        for patch in catalog.all():
            migration = "declarative" if patch.operations else "stable-builder"
            print(f"{patch.patch_id:<48} {patch.binary:<10} {migration}")
        return 0
    if not args.patch_id:
        raise SystemExit("patch id is required")
    manifest = catalog.get(args.patch_id)
    if args.action == "show":
        payload = asdict(manifest)
        payload["manifest_path"] = str(manifest.manifest_path)
        payload["builder"] = str(manifest.builder) if manifest.builder else None
        print(json.dumps(payload, indent=2, default=lambda value: value.hex() if isinstance(value, bytes) else str(value)))
        return 0
    if not args.source or not args.target:
        raise SystemExit("apply requires SOURCE and TARGET")
    print(apply_patch(manifest, Path(args.source), Path(args.target)))
    return 0
