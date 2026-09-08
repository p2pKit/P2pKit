#!/usr/bin/env python3
"""Reject missing/infrastructure-failed audit leaves, including expected-red probes."""

import argparse
import json
from pathlib import Path
import re
import sys


def validate(receipt, status, purpose, cwd, wrapper, arguments):
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    require(type(receipt) is dict and type(receipt.get("schema")) is int and receipt["schema"] == 1,
            "missing or unsupported audit receipt schema")
    require(type(status) is int and status != 125, "audit infrastructure failure is not a policy rejection")
    require(type(receipt.get("id")) is str and bool(receipt["id"]), "missing audit invocation identity")
    require(receipt.get("purpose") == purpose, "receipt belongs to another purpose")
    require(receipt.get("cwd") == str(Path(cwd).resolve()), "receipt working directory differs")
    require(receipt.get("wrapper") == str(Path(wrapper).resolve()), "receipt wrapper differs")
    require(receipt.get("requestedArgv") == arguments, "receipt original argument vector differs")
    for name in ("productExitCode", "finalExitCode"):
        require(type(receipt.get(name)) is int and receipt[name] == status, name + " differs")
    require(type(receipt.get("stopExitCode")) is int and receipt["stopExitCode"] == 0,
            "Gradle stop did not succeed")
    require(receipt.get("sourceUnchanged") is True, "source was not stable")
    require(receipt.get("errors") == [] and type(receipt.get("errors")) is list,
            "audit leaf has finalization errors")
    require(type(receipt.get("ownedSurvivors")) is list and receipt["ownedSurvivors"] == [],
            "owned workers remain or cleanup was not recorded")
    before, after = receipt.get("sourceBefore"), receipt.get("sourceAfter")
    require(type(before) is dict and before == after, "source receipts differ or are absent")
    for name in ("commit", "tree"):
        require(type(before.get(name)) is str and re.fullmatch(r"[0-9a-f]{40}", before[name]),
                "invalid source " + name)
    require(type(before.get("status")) is str, "missing complete source status")
    require(type(before.get("diffSha256")) is str and re.fullmatch(r"[0-9a-f]{64}", before["diffSha256"]),
            "missing source diff binding")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("status", type=int)
    parser.add_argument("--purpose", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--wrapper", required=True)
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.receipt.is_symlink() or not args.receipt.is_file():
            raise ValueError("audit receipt is not a regular owned file")
        with args.receipt.open("rb") as stream:
            raw = stream.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("audit receipt is oversized")
        def pairs(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError("duplicate receipt key")
                result[key] = value
            return result
        receipt = json.loads(raw, object_pairs_hook=pairs)
        arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
        validate(receipt, args.status, args.purpose, args.cwd, args.wrapper, arguments)
    except (OSError, ValueError, TypeError) as error:
        print("FATAL: invalid audit leaf receipt: " + str(error), file=sys.stderr)
        return 125
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
