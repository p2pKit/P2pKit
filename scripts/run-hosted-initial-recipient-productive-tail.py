#!/usr/bin/env python3
"""Fixed productive R-before/K continuation. Dormant, no acceptance claim."""
from __future__ import annotations

import argparse
import base64
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import hosted_initial_recipient_productive_tail as K


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("before", allow_abbrev=False)
    child = commands.add_parser("_tail-child", allow_abbrev=False)
    child.add_argument("--context-sha256", required=True)
    child.add_argument("--minimum-ns", required=True)
    child.add_argument("--deadline-base64", required=True)
    for name, flag in K.CAP_FIELDS:
        child.add_argument(flag, dest=name, required=True)
    args = parser.parse_args()
    try:
        K.require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            "ISOLATED_INTERPRETER_REQUIRED")
        if args.operation == "before":
            K.native.guarded(lambda signals: K.before_and_tail(lambda: K.native.cancellation(signals)))
        else:
            K.CD.sha(args.context_sha256)
            K.require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "MINIMUM_DECIMAL")
            minimum = K.CD.integer(int(args.minimum_ns))
            encoded = args.deadline_base64
            K.require(type(encoded) is str and 0 < len(encoded) <= 16384, "DEADLINE_ARGV_BOUND")
            raw = base64.b64decode(encoded, validate=True)
            K.require(base64.b64encode(raw).decode("ascii") == encoded, "DEADLINE_CANONICAL_BASE64")
            deadline = K.RD.deadline(raw)
            decimals = tuple(getattr(args, name) for name, _flag in K.CAP_FIELDS)
            K.require(all(re.fullmatch(r"0|[1-9][0-9]{0,19}", value) for value in decimals), "CAP_DECIMALS")
            caps = K.TD.caps(deadline, tuple(int(value) for value in decimals))
            K.require(sys.argv[1:] == K._command(args.context_sha256, deadline, caps, minimum)[5:],
                "EXACT_FIXED_CHILD_ARGUMENTS")
            K.native.guarded(lambda signals: K.tail_child(args.context_sha256, minimum, deadline, caps,
                lambda: K.native.cancellation(signals)))
        return 0
    except BaseException:
        print("INITIAL_RECIPIENT_PRODUCTIVE_TAIL_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
