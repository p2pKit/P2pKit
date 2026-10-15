#!/usr/bin/env python3
"""Real Mac development-JDK21 JNI registrar controls; NOT Windows/installed/bootstrap qualification."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time


def digest(path):
    result = hashlib.sha256()
    with path.open("rb") as value:
        for block in iter(lambda: value.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="New private absolute directory outside checkout")
    parser.add_argument("--clang", required=True, type=Path, help="Existing trusted absolute Apple Clang")
    parser.add_argument("--sdk", required=True, type=Path, help="Existing trusted absolute macOS SDK")
    parser.add_argument("--jdk", required=True, type=Path, help="Existing trusted absolute development JDK21 home")
    parser.add_argument("--classes", required=True, type=Path, help="This checkout's existing Gradle JVM main classes")
    args = parser.parse_args()
    source = Path(__file__).resolve().parent
    repository = source.parents[3]
    expected_classes = repository / "samples/p2p-sample-rpc/build/classes/kotlin/jvm/main"
    if sys.platform != "darwin":
        parser.error("Mac development-JVM component control only; no Windows execution scope")
    for name in ("output", "clang", "sdk", "jdk", "classes"):
        if not getattr(args, name).is_absolute():
            parser.error(f"--{name} must be absolute")
    if args.output.resolve().is_relative_to(repository) or args.output.exists():
        parser.error("Output must be new and outside checkout")
    if args.classes.resolve() != expected_classes.resolve():
        parser.error("Classes must be this checkout's actual existing Gradle JVM main output")
    jvm = args.jdk / "lib/server/libjvm.dylib"
    required = [args.clang, args.jdk / "release", jvm, args.jdk / "include/jni.h",
                args.jdk / "include/darwin/jni_md.h", args.sdk / "SDKSettings.json"]
    names = ("WindowsProfileCustodyCalls", "WindowsProfileCustodyJni")
    package = Path("dev/p2pkit/sample/rpc/profile")
    class_inputs = [args.classes / package / (name + ".class") for name in names]
    if not all(path.is_file() for path in required + class_inputs):
        parser.error("Missing selected tool/SDK/runtime or actual compiled classes; no download/build fallback")
    if not any(line.startswith('JAVA_VERSION="21.') for line in (args.jdk / "release").read_text().splitlines()):
        parser.error("Existing JDK21 required, not JDK17 fallback")
    for path in class_inputs:
        header = path.read_bytes()[:8]
        if header != b"\xca\xfe\xba\xbe\x00\x00\x00\x3d":
            parser.error("Actual custody classes must retain Java17 non-preview bytecode")

    os.umask(0o077)
    args.output.mkdir(mode=0o700)
    copied_classes = args.output / "actual-gradle-classes"
    (copied_classes / package).mkdir(parents=True)
    empty_classes = args.output / "empty-classes"
    empty_classes.mkdir()
    temporary = args.output / "tmp"
    temporary.mkdir()
    c_inputs = [source / "profile_policy.c", source / "profile_jni.c", source / "profile_jni_registration.c",
                source / "tests/jvm/deny_storage.c", source / "tests/jvm/registration_jvm_test.c"]
    inputs = c_inputs + [source / name for name in ("profile_policy.h", "profile_win32.h", "profile_jni_registration.h")]
    inputs += [Path(__file__).resolve()] + required + class_inputs
    inputs += [repository / "samples/p2p-sample-rpc/src/jvmMain/kotlin" / package / (name + ".kt") for name in names]
    # Bind the selected development image's available include/lib bytes, not an installed authority.
    inputs += [path for base in (args.jdk / "lib", args.jdk / "include") for path in base.rglob("*") if path.is_file()]
    inputs = sorted(set(inputs))
    before = {str(path): digest(path) for path in inputs}
    for path in class_inputs:
        target = copied_classes / package / path.name
        shutil.copyfile(path, target)
        if digest(target) != before[str(path)]:
            raise RuntimeError("Actual class bytes changed while copying")
    environment = {"PATH": "/usr/bin:/bin", "HOME": str(args.output), "TMPDIR": str(temporary),
                   "LANG": "C", "LC_ALL": "C", "SDKROOT": str(args.sdk)}
    executable = args.output / "registration-jvm-test"
    command = [str(args.clang), "-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-isysroot", str(args.sdk),
               "-I" + str(args.jdk / "include"), "-I" + str(args.jdk / "include/darwin")]
    commands = [command + [str(path) for path in c_inputs] + ["-o", str(executable)]]
    modes = ("success", "pending", "address", "missing-class")
    commands += [[str(executable), str(jvm), str(empty_classes if mode == "missing-class" else copied_classes), mode]
                 for mode in modes]
    results = []
    for index, command in enumerate(commands):
        start = time.monotonic()
        with (args.output / f"{index}-stdout.log").open("xb") as stdout:
            with (args.output / f"{index}-stderr.log").open("xb") as stderr:
                try:
                    completed = subprocess.run(command, cwd=args.output, env=environment, stdin=subprocess.DEVNULL,
                                               stdout=stdout, stderr=stderr, timeout=60, check=False)
                    outcome = {"command": command, "exitCode": completed.returncode, "timedOut": False}
                except subprocess.TimeoutExpired:
                    outcome = {"command": command, "exitCode": None, "timedOut": True}
        outcome["elapsedSeconds"] = round(time.monotonic() - start, 3)
        # -Xcheck:jni warnings are failures, including those the JVM writes to stdout.
        logs = [(args.output / f"{index}-{stream}.log").read_bytes() for stream in ("stdout", "stderr")]
        expected = b"" if index == 0 else (
            f"PASS real-development-JDK21-registration {modes[index - 1]}; no Windows storage or loader\n".encode()
        )
        outcome["cleanOutput"] = logs == [expected, b""]
        results.append(outcome)
        if outcome["exitCode"] != 0 or not outcome["cleanOutput"]:
            break
    after = {str(path): digest(path) for path in inputs}
    unchanged = before == after
    receipt = {
        "scope": "REAL_MAC_DEVELOPMENT_JDK21_JNI_REGISTRATION_NOT_WINDOWS_STORAGE_OR_INSTALLED_RUNTIME",
        "inputs": before, "inputsUnchanged": unchanged, "environment": environment,
        "classBinding": "Copied actual existing Gradle outputs; source hashes are observations, not a rebuild receipt",
        "toolBinding": "Selected image/input hashes, not full compiler dependency provenance or production authority",
        "processScope": "Bounded same-user test child; not Foundation whole-invocation supervisor acceptance",
        "results": results,
        "passed": unchanged and len(results) == len(commands) and
                  all(result["exitCode"] == 0 and result["cleanOutput"] for result in results),
    }
    if executable.is_file():
        receipt["executableSha256"] = digest(executable)
    with (args.output / "result.json").open("x") as target:
        json.dump(receipt, target, indent=2)
        target.write("\n")
    print(json.dumps({"passed": receipt["passed"], "evidence": str(args.output / "result.json")}))
    return 0 if receipt["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
