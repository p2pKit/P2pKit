#!/usr/bin/env python3
"""Fixed productive seal/native-child routes; no standalone BEFORE hydration."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hosted_initial_recipient_productive_receiver as R


class _ClosedParser(argparse.ArgumentParser):
    def error(self, _message):
        # Do not print arbitrary caller strings or rejected environment data.
        raise R.O.OriginError("INITIAL_PRODUCTIVE_RECEIVER_CLI_ARGUMENTS")


def _arguments(argv):
    parser = _ClosedParser(description=__doc__, allow_abbrev=False, add_help=False)
    commands = parser.add_subparsers(dest="operation", required=True, parser_class=_ClosedParser)
    commands.add_parser("seal", allow_abbrev=False, add_help=False)
    flags = ("--context-sha256", "--minimum-ns", *R.RD.AUTHORITY_CAP_FLAGS,
        "--original-boot-digest", "--clock-role", "--clock-domain", "--clock-ticks-per-second")
    for operation in ("_seal-authority", "_before-authority"):
        child = commands.add_parser(operation, allow_abbrev=False, add_help=False)
        for flag in flags:
            child.add_argument(flag, required=True)
    args = parser.parse_args(argv)
    if args.operation == "seal":
        R.require(argv == ["seal"], "CLI_EXACT_SEAL")
        return args.operation, None
    values = [getattr(args, flag[2:].replace("-", "_")) for flag in flags]
    R.require(argv == [args.operation, *(item for pair in zip(flags, values) for item in pair)], "CLI_EXACT_CHILD_ARGV")
    def integer(value):
        R.require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value), "CLI_CANONICAL_INTEGER")
        return R.CD.integer(int(value))
    checksum, minimum = R.CD.sha(values[0]), integer(values[1])
    caps = R.CD.authority_caps(tuple(integer(value) for value in values[2:8]))
    boot = R.CD.sha(values[8])
    clock = R.O.clocks.ClockIdentity(values[9], values[10], integer(values[11]))
    R.O.clocks.validate_identity(clock)
    R.require(caps[3] <= minimum < caps[4], "CLI_LAUNCH_MINIMUM")
    return args.operation, (checksum, minimum, caps, clock, boot)


def main():
    try:
        R.require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and
            os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            os.environ.get("GITHUB_REPOSITORY") == R.P.I.REPOSITORY and
            sys.argv[0] == str(R.SCRIPTS / "run-hosted-initial-recipient-productive-receiver.py"), "CLI_ACTUAL_HOSTED_SOURCE")
        operation, values = _arguments(sys.argv[1:])
        if operation == "seal":
            R.B.guarded(lambda signals: R.seal(lambda: R.B.cancellation(signals)))
        else:
            child = (R.productive_seal_authority_child if operation == "_seal-authority" else
                R.productive_before_authority_child)
            R.B.guarded(lambda signals: child(*values, lambda: R.B.cancellation(signals)))
        return 0
    except BaseException:
        print("INITIAL_PRODUCTIVE_RECEIVER_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
