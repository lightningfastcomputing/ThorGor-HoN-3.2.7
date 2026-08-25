"""Package shim for the flattened ThorGor source tree.

The repository root now owns the package modules directly.  Exposing a package
search path here preserves the stable ``python -m thorgor`` entry point and
existing absolute imports without requiring the checkout directory itself to
be named ``thorgor``.
"""
from __future__ import annotations

import sys
import importlib.util
from pathlib import Path


__path__ = [str(Path(__file__).resolve().parent)]

if __name__ == "__main__":
    sys.modules.setdefault("thorgor", sys.modules[__name__])
    cli_path = Path(__file__).resolve().with_name("__main__.py")
    spec = importlib.util.spec_from_file_location("_thorgor_cli", cli_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load ThorGor CLI from {cli_path}")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)

    raise SystemExit(cli.main())
