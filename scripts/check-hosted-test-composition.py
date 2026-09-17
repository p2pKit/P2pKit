#!/usr/bin/env python3
"""Static tripwires for the unchanged reviewed ordinary execution composition.

The former direct YAML commands now live in the custody controller. Bind the
actual parsed supplier programs, not comments or echoed command strings. These
independent expectations are reviewed inputs: a supplier edit needs its own
acceptance/review and an explicit tripwire update. They do not prove execution,
cache qualification, native behavior, or a passing held workflow.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path


# Baseline 59b91c738da2801cc4d5008acd54dfd728a2e18d: approved B1/B2/C source,
# not an execution at that commit. Whole programs also bind dispatch/call order
# and prevent an unchanged helper being shadowed by a later assignment.
EXPECTED = {
    "scripts/run-hosted-test-custody.py": "52664a6b44f3d44632a7ec223d3e2c77dbf3de7879bfa4747a7374c434d3f42c",
    "scripts/hosted_full_supplements.py": "9f5c6a0f410c00ee7531664e95dab233c0febc6740dd6a8b1005e3fc3a64310c",
    "scripts/hosted_primary_abi.py": "ff168e70c31bc23b1c6e545a32d0c4217f9a212f7244a2c34571eee09f761553",
    "scripts/run-platform-tests.py": "1a3e6f093abe3a79bfbc2d3f426f26e71db77c6f72034effeb2e296dc833c271",
    "scripts/run-audit-command.py": "70216745a371d41101a0c4f6d27ca1d73b5f3d82c3e7ea4fc70009fb44f51cc5",
    "scripts/hosted_dependency_seed_files.py": "4424910906cad71f98937dcb172f3991a9a3c61ac0e27506b54965b7b66a6849",
}
LIMIT = 1024 * 1024


def structure(value):
    """Stable AST fields across admitted Python 3.9/3.12; no source execution.

    Python 3.12 adds an empty type_params field to ordinary functions/classes.
    Nonempty type parameters remain part of the structure. Locations, comments
    and docstrings are not executable call/command/retention policy.
    """
    if isinstance(value, ast.AST):
        result = {"node": type(value).__name__}
        for name, item in ast.iter_fields(value):
            if name == "type_params" and item == []:
                continue
            if name == "body" and isinstance(value, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if item and isinstance(item[0], ast.Expr) and isinstance(item[0].value, ast.Constant) and isinstance(item[0].value.value, str):
                    item = item[1:]
            result[name] = structure(item)
        return result
    if isinstance(value, list):
        return [structure(item) for item in value]
    if isinstance(value, bytes):
        return {"bytesHex": value.hex()}
    if value is Ellipsis:
        return {"ellipsis": True}
    return value


def source_digest(raw, path):
    if type(raw) is not bytes or not 0 < len(raw) <= LIMIT:
        raise ValueError("ordinary composition input is missing/oversized: " + path)
    tree = ast.parse(raw.decode("utf-8"), filename=path)
    encoded = json.dumps(structure(tree), sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def check_sources(sources):
    if set(sources) != set(EXPECTED):
        raise ValueError("ordinary composition input roster differs")
    for path, expected in EXPECTED.items():
        if source_digest(sources[path], path) != expected:
            raise ValueError("ordinary executable composition changed: " + path)


def read_sources(root):
    result = {}
    for name in EXPECTED:
        path = root / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= LIMIT:
            raise ValueError("ordinary composition input is missing/oversized: " + name)
        with path.open("rb") as stream:
            result[name] = stream.read(LIMIT + 1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        check_sources(read_sources(args.root))
    except (OSError, ValueError, SyntaxError, RecursionError) as error:
        parser.exit(1, "FATAL: " + str(error) + "\n")
    print("RESULT: PASS — ordinary command/ABI/supplement/retention source tripwires; no runtime/cache claim")


if __name__ == "__main__":
    main()
