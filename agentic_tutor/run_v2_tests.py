#!/usr/bin/env python3
"""Zero-dependency test runner for the isolated tutor_v2 backend."""
from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def _load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    passed = failed = 0
    failures: list[tuple[str, str]] = []
    for path in sorted((ROOT / "tests_v2").glob("test_*.py")):
        module = _load(path)
        for name in sorted(vars(module)):
            candidate = getattr(module, name)
            if name.startswith("test_") and callable(candidate):
                try:
                    candidate()
                    passed += 1
                    print(f"  ok   {path.name}::{name}")
                except Exception:
                    failed += 1
                    failures.append((f"{path.name}::{name}", traceback.format_exc()))
                    print(f"  FAIL {path.name}::{name}")
    print(f"\n{passed} passed, {failed} failed")
    for name, trace in failures:
        print(f"\n===== {name} =====\n{trace}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
