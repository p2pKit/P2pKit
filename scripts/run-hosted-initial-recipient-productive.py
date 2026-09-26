#!/usr/bin/env python3
"""Fixed initial-recipient productive/native-child routes; activation stays held."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hosted_initial_recipient_productive as P


def main():
    try:
        P.require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and
            os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            os.environ.get("GITHUB_REPOSITORY") == P.I.REPOSITORY, "ACTUAL_HOSTED_CALLER")
        parser = argparse.ArgumentParser(description=__doc__)
        commands = parser.add_subparsers(dest="operation", required=True)
        commands.add_parser("produce")
        for name in ("prepare-save", "after-save", "prepare-probe", "after-probe"):
            commands.add_parser(name)
        flags = ("context-sha256", "minimum-ns", "site", "parent-first-ns", "parent-work-end-ns", "use-first-ns",
            "use-work-end-ns", "use-final-end-ns", "original-boot-digest", "phase-start-ns", "phase-work-end-ns",
            "phase-final-end-ns", "clock-role", "clock-domain", "clock-ticks-per-second")
        for name in ("_private-use", "_public-use"):
            command = commands.add_parser(name)
            for flag in flags:
                command.add_argument("--" + flag, required=True)
        args = parser.parse_args()
        if args.operation == "produce":
            P.B.guarded(lambda signals: P.productive(lambda: P.B.cancellation(signals)))
        elif args.operation in ("prepare-save", "after-save", "prepare-probe", "after-probe"):
            P.B.guarded(lambda signals: P.step(args.operation, lambda: P.B.cancellation(signals)))
        else:
            def integer(name):
                value = getattr(args, name)
                P.require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value), "CHILD_INTEGER")
                return P.O.integer(int(value))
            value = {"site": args.site, "parentFirstNs": integer("parent_first_ns"),
                "parentWorkEndNs": integer("parent_work_end_ns"), "firstNs": integer("use_first_ns"),
                "workEndNs": integer("use_work_end_ns"), "nativeFinalEndNs": integer("use_final_end_ns"),
                "originalBootDigest": args.original_boot_digest}
            caps = tuple(integer(name) for name in ("phase_start_ns", "phase_work_end_ns", "phase_final_end_ns"))
            clock = P.O.clocks.ClockIdentity(args.clock_role, args.clock_domain, integer("clock_ticks_per_second"))
            P.O.clocks.validate_identity(clock)
            scope = P.U.PRIVATE_CONTEXT if args.operation == "_private-use" else P.U.PUBLIC_CONTEXT
            P.B.guarded(lambda signals: P.service_child(scope, args.context_sha256, integer("minimum_ns"),
                value, caps, clock, lambda: P.B.cancellation(signals)))
        return 0
    except BaseException:
        print("INITIAL_PRODUCTIVE_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
