#!/usr/bin/env python3
"""Zero-dependency test runner (this env has no pytest).

Discovers every `test_*` function in tests/test_*.py, runs it, and reports.
Usage: python3 run_tests.py
"""
import importlib.util
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def load(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    passed = failed = 0
    failures = []
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        mod = load(path)
        for name in sorted(vars(mod)):
            if not name.startswith("test_"):
                continue
            fn = getattr(mod, name)
            if not callable(fn):
                continue
            try:
                fn()
                passed += 1
                print(f"  ok   {path.name}::{name}")
            except Exception:
                failed += 1
                failures.append((f"{path.name}::{name}", traceback.format_exc()))
                print(f"  FAIL {path.name}::{name}")
    print(f"\n{passed} passed, {failed} failed")
    for name, tb in failures:
        print(f"\n===== {name} =====\n{tb}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
