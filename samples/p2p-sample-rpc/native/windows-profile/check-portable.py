#!/usr/bin/env python3
"""Create-only offline C/JNI controls; no Windows emulation, DLL load, installation or application action."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New private directory outside this checkout")
    parser.add_argument("--clang", required=True, type=Path, help="Existing trusted absolute Apple Clang path")
    parser.add_argument("--jdk", required=True, type=Path, help="Existing trusted JDK17 home; no download")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    repository = source.parents[3]
    if sys.platform != "darwin":
        parser.error("This maintained command is the Mac portable check, not Windows qualification")
    if not args.output.is_absolute() or repository in args.output.resolve().parents:
        parser.error("Use a new absolute output directory outside the checkout")
    if not args.clang.is_absolute() or not args.clang.is_file() or not args.jdk.is_absolute():
        parser.error("Existing absolute tool paths required")
    os.umask(0o077)
    args.output.mkdir(mode=0o700)
    inputs = sorted(source.glob("*.c")) + sorted(source.glob("*.h")) + sorted((source / "tests").glob("*.c"))
    inputs += [Path(__file__).resolve()]
    def hashes():
        return {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    before = hashes()
    executable = args.output / "profile-policy-test"
    commands = [
        [str(args.clang), "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic",
         "-fsanitize=address,undefined", "-fno-omit-frame-pointer", str(source / "profile_policy.c"),
         str(source / "tests/profile_policy_test.c"), "-o", str(executable)],
        [str(args.clang), "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-fsyntax-only",
         "-I" + str(args.jdk / "include"), "-I" + str(args.jdk / "include/darwin"), str(source / "profile_jni.c")],
        [str(executable)],
    ]
    results = []
    for index, command in enumerate(commands):
        with (args.output / f"{index}-stdout.log").open("xb") as stdout:
            with (args.output / f"{index}-stderr.log").open("xb") as stderr:
                try:
                    completed = subprocess.run(command, stdout=stdout, stderr=stderr, timeout=120, check=False)
                    outcome = {"command": command, "exitCode": completed.returncode, "timedOut": False}
                except subprocess.TimeoutExpired:
                    outcome = {"command": command, "exitCode": None, "timedOut": True}
        results.append(outcome)
        if outcome["exitCode"] != 0:
            break
    receipt = {"scope": "MAC_PORTABLE_C_AND_JNI_SYNTAX_NOT_WINDOWS_RUNTIME", "sourceHashes": before,
               "sourceUnchanged": before == hashes(), "results": results,
               "passed": len(results) == 3 and all(r["exitCode"] == 0 for r in results) and before == hashes()}
    with (args.output / "result.json").open("x") as target:
        json.dump(receipt, target, indent=2)
        target.write("\n")
    print(json.dumps({"passed": receipt["passed"], "evidence": str(args.output / "result.json")}))
    return 0 if receipt["passed"] and receipt["sourceUnchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
