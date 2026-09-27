#!/usr/bin/env python3
"""Retain real ordinary hosted identity through native-owned private Git queries.

Admission only: no Gradle, GPG, package, upload, bootstrap policy or publication.
This command is not an ordinary full/desktop build controller or a required gate.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hosted_test_query
import hosted_test_identity


def initial_ordinary_admission(profile, root):
    """Distinct source-only worker check; never an ordinary Admission adapter.

    The fixed pre-tool provider Action already acquires its own actual current.
    Do not insert this optional standalone inspection before that Action merely
    to duplicate source acquisition. Returned hashes cannot be adopted as a live
    current by another interpreter or substituted for the provider/run entries.
    """
    import hosted_initial_ordinary_adapter as initial
    import hosted_full_job_budget as budget
    cancelled, handlers, original, session = [], {}, None, None
    try:
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        def check():
            hosted_test_identity.require(not cancelled, "INITIAL_ADMISSION_CANCELLED")
        hosted_test_identity.require(root == initial.ROOT and root.is_absolute(), "INITIAL_ADMISSION_FIXED_ROOT")
        first = budget.current_reading(profile)
        session = initial.acquire_first(cancelled=check, original_work_end_ns=first.nanoseconds + 75 * budget.NS,
                                       original_final_end_ns=first.nanoseconds + 120 * budget.NS)
        value = hosted_test_identity.parse(session.identity.record, 4 * 1024 * 1024)
        hosted_test_identity.require(value["profile"] == profile and
            initial.identity.cache_cohort(session.identity.record) == (profile, first.clock.role),
            "INITIAL_ADMISSION_PROFILE_CHANGED")
        current = session.claim("worker")
        result = {"schema": 1, "scope": "INITIAL_ORDINARY_SOURCE_INSPECTION_ONLY",
            "identitySha256": initial.digest(session.identity.record), "currentSha256": initial.digest(current),
            "ordinaryAdmission": "NOT_CREATED", "providerAcceptance": "NOT_PERFORMED", "enclosingStep": "NOT_OBSERVED"}
        session.check()
    except BaseException as error:
        original = error
        if session is not None:
            session.fail(error)
    finally:
        for number, handler in handlers.items():
            try:
                signal.signal(number, handler)
            except BaseException as error:
                original = original or error
    if original is not None:
        raise original
    session.check()
    sys.stdout.write(hosted_test_identity.encoded(result).decode("ascii"))
    sys.stdout.flush()
    session.check()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("full", "desktop"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence-directory", type=Path)
    parser.add_argument("--initial-ordinary", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.initial_ordinary:
            hosted_test_identity.require(args.evidence_directory is None, "INITIAL_ADMISSION_FIXED_EVIDENCE_ONLY")
            initial_ordinary_admission(args.profile, args.root)
            return 0
        hosted_test_identity.require(args.evidence_directory is not None, "ORDINARY_ADMISSION_EVIDENCE_REQUIRED")
        admitted = hosted_test_query.admit_hosted(args.profile, args.root, args.evidence_directory)
        if args.profile == "desktop":
            required = hosted_test_identity.sample_packaging_required(admitted)
            # Only a fixed boolean is public. Step success is also required by
            # every workflow consumer; a partial append cannot grant packaging.
            target = Path(os.environ["GITHUB_OUTPUT"])
            hosted_test_identity.require(target.is_absolute() and target == target.resolve(strict=True),
                                         "IDENTITY_OUTPUT_PATH")
            with target.open("a", encoding="ascii") as stream:
                stream.write("sample_packaging_required=" + str(required).lower() + "\n")
                stream.flush()
                os.fsync(stream.fileno())
    except BaseException:
        print("Ordinary hosted admission HOLD; preserve private records; no products started", file=sys.stderr)
        return 125
    print("Ordinary hosted identity retained; no crypto validation, tests, export or upload performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
