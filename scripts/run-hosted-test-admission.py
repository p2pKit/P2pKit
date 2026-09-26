#!/usr/bin/env python3
"""Retain real ordinary hosted identity through native-owned private Git queries.

Admission only: no Gradle, GPG, package, upload, bootstrap policy or publication.
This command is not an ordinary full/desktop build controller or a required gate.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hosted_test_query
import hosted_test_identity


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("full", "desktop"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--evidence-directory", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
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
