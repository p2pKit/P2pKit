#!/usr/bin/env python3
"""Owner-authorized RPC candidate generation; never publication or capacity evidence.

Run only on the exact feature ref in a disposable GitHub-hosted macOS runner.
Generated checksums/ABI/locks need independent review; a failed full writer's
partial lockfiles are never acceptable. Raw logs and test payloads are not uploaded.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
REF = "refs/heads/work/rpc-lan-20260927-054728-8b1b11da"
LIBRARIES = ("p2p-core", "p2p-transport-lan", "p2p-rpc")
LOCKS = (
    "gradle.lockfile", "settings-gradle.lockfile", "buildscript-gradle.lockfile",
    *(f"library/{name}/gradle.lockfile" for name in (*LIBRARIES,
        "p2p-network-provisioning-android", "p2p-network-provisioning-desktop")),
    *(f"samples/{name}/gradle.lockfile" for name in ("p2p-sample-rpc", "p2p-sample-android",
        "p2p-sample-desktop", "p2p-sample-desktop-ui", "p2p-sample-diagnostics", "sample-kmp-shared")),
)
GENERATED = frozenset((*LOCKS, "gradle/verification-metadata.xml", *(
    f"library/{name}/api/{suffix}" for name in LIBRARIES
    for suffix in (f"{name}.klib.api", f"jvm/{name}.api", f"android/{name}.api"))))
FLAGS = ["--no-daemon", "--no-build-cache", "--no-configuration-cache", "--no-parallel",
         "--max-workers=2", "--no-configure-on-demand", "--rerun-tasks", "--console=plain",
         "--dependency-verification", "strict", "--warning-mode=fail",
         "-Pkotlin.compiler.execution.strategy=in-process"]
MAX_FILE = 16 * 1024 * 1024
MAX_LOG = 256 * 1024 * 1024


class HostedValidationError(RuntimeError):
    """A fixed, payload-free control failure safe to report in Actions logs."""


def require(condition, message):
    if not condition:
        raise HostedValidationError(message)


def git(*args):
    return subprocess.check_output(["git", "--no-replace-objects", *args], cwd=ROOT, timeout=30)


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def read_bounded(path, limit=MAX_FILE):
    require(path.is_file() and not path.is_symlink(), "Expected a regular bounded evidence file")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Evidence file exceeds its byte limit")
    return raw


def paths():
    require(os.environ.get("GITHUB_ACTIONS") == "true" and platform.system() == "Darwin",
            "Execution requires the authorized disposable GitHub macOS host")
    require(os.environ.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and os.environ.get("GITHUB_REF") == REF,
            "Execution is restricted to the RPC feature ref")
    require(ROOT == Path(os.environ["GITHUB_WORKSPACE"]).resolve(), "Unexpected source root")
    require(git("rev-parse", "HEAD").decode().strip() == os.environ["GITHUB_SHA"], "Wrong source commit")
    state = Path(os.environ["RPC_HOSTED_STATE"]).resolve(strict=True)
    require(state.is_relative_to(Path(os.environ["RUNNER_TEMP"]).resolve()), "State is not runner-owned")
    require(not state.is_relative_to(ROOT), "State must not be a project input")
    for variable, child in (("HOME", "home"), ("GRADLE_USER_HOME", "gradle"),
                            ("KONAN_DATA_DIR", "konan"), ("ANDROID_USER_HOME", "android-user"),
                            ("TMPDIR", "tmp")):
        require(Path(os.environ[variable]).resolve(strict=True) == state / child, "Unowned tool home")
    require(all(not os.environ.get(name) for name in ("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS")),
            "Inherited Java launch options are not authorized")
    reports = ROOT / "build/reports/rpc-hosted"
    reports.mkdir(parents=True, exist_ok=True)
    return state, reports


def generator_commands():
    # Do not narrow the lock graph or bypass its root graph-admission guard.
    return [
        ("apple-abi", [*(f":{name}:updateKotlinAbi" for name in LIBRARIES),
                       "--write-verification-metadata", "sha256"], 1800),
        ("complete-lock-writer", ["resolveAndLockAll", "--write-locks",
                                  "--write-verification-metadata", "sha256"], 7200),
    ]


def safe_diagnostics(path):
    """Only compiler/task/dependency diagnostics, never test output/assertion bodies."""
    selected = []
    with path.open("rb") as stream:
        while len(selected) < 160:
            raw = stream.readline(8193)
            if not raw:
                break
            if len(raw) > 8192:
                while raw and not raw.endswith(b"\n"):
                    raw = stream.readline(8193)
                continue
            line = raw.decode("utf-8", errors="replace").rstrip()
            compiler = re.match(r"^[ew]: (?:file:/{1,3})?[^\r\n]+\.(?:kt|kts|java):[0-9]+", line)
            task = re.fullmatch(r"> Task :[A-Za-z0-9:_-]+ (?:FAILED|SKIPPED|NO-SOURCE)", line)
            artifact = re.fullmatch(r"\s*> Could not (?:find|resolve) "
                                    r"[A-Za-z0-9_.-]+:[A-Za-z0-9_.-]+:[A-Za-z0-9_.+-]+\.?", line)
            if compiler or task or artifact or re.fullmatch(r"BUILD (?:FAILED|SUCCESSFUL) in [0-9hms .]+", line):
                selected.append(line.replace(str(ROOT), "<source>"))
    return selected


def test_summary(root):
    result, total, count = [], 0, 0
    for parent in (root / "library", root / "samples"):
        for path in sorted(parent.glob("*/build/test-results/**/TEST-*.xml")):
            count += 1
            require(count <= 5000, "Too many test report files")
            raw = read_bounded(path)
            total += len(raw)
            require(total <= 64 * 1024 * 1024, "Test reports exceed the aggregate byte bound")
            require(b"<!DOCTYPE" not in raw and b"<!ENTITY" not in raw, "Unexpected XML declaration")
            suite = ET.fromstring(raw)
            require(suite.tag == "testsuite", "Unexpected test report root")
            counts = {name: int(suite.attrib.get(name, "0")) for name in ("tests", "failures", "errors", "skipped")}
            require(all(0 <= value <= 100000 for value in counts.values()), "Invalid test counts")
            failures = []
            for case in suite.findall("testcase"):
                if case.find("failure") is not None or case.find("error") is not None:
                    # Do not retain message/trace/system-out/system-err, even for synthetic fixtures.
                    failures.append({key: re.sub(r"[^A-Za-z0-9_.$ ()-]", "?", case.attrib.get(key, ""))[:200]
                                     for key in ("classname", "name")})
            result.append({"path": path.relative_to(root).as_posix(), **counts, "failedCases": failures})
    return result


def collect_candidates(root, generation_complete):
    unexpected = set(git("diff", "--name-only", "HEAD").decode().splitlines()) - GENERATED
    untracked = set(git("ls-files", "--others", "--exclude-standard").decode().splitlines())
    require(not unexpected and not (untracked - GENERATED), "Unexpected source modification during generation")
    if untracked:
        git("add", "--intent-to-add", "--", *sorted(untracked))
    changed = git("diff", "--name-only", "HEAD").decode().splitlines()
    records = []
    for name in changed:
        raw = read_bounded(root / name)
        records.append({"path": name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    complete = generation_complete and all((root / name).is_file() and (root / name).stat().st_size > 0
                                           for name in (*LOCKS, *(f"library/{n}/api/{n}.klib.api" for n in LIBRARIES)))
    patch = git("diff", "--binary", "--no-ext-diff", "--no-textconv", "HEAD", "--", *sorted(GENERATED))
    require(len(patch) <= 32 * 1024 * 1024, "Candidate patch exceeds its byte bound")
    return {"status": "REVIEW_REQUIRED" if complete else "INCOMPLETE_DO_NOT_IMPORT",
            "files": records, "patchSha256": hashlib.sha256(patch).hexdigest(),
            "limitation": "Not reviewed, not committed, not release or physical/capacity qualification."}, patch


def execute(state, label, argv, timeout):
    spec = importlib.util.spec_from_file_location("rpc_platform_runner", ROOT / "scripts/run-platform-tests.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    started = time.monotonic()
    log = state / f"{label}.log"
    process, code, drained = None, 125, False
    try:
        with log.open("xb") as stream:
            process = subprocess.Popen(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            while process.poll() is None:
                if time.monotonic() - started > timeout or log.stat().st_size > MAX_LOG:
                    code = 124
                    break
                time.sleep(0.2)
            else:
                code = process.returncode
    finally:
        drained = helper.terminate_process(process)
    return {"label": label, "command": argv, "exitCode": code if drained else 125,
            "processGroupDrained": drained, "seconds": round(time.monotonic() - started, 3)}


def generate(state, reports):
    require(not git("status", "--porcelain=v1").strip(), "Generation requires a clean exact commit")
    require(platform.machine() == "arm64", "Candidate generation requires Apple Silicon")
    record = {"source": os.environ["GITHUB_SHA"], "tree": git("rev-parse", "HEAD^{tree}").decode().strip(),
              "runId": os.environ["GITHUB_RUN_ID"], "runAttempt": os.environ["GITHUB_RUN_ATTEMPT"],
              "host": platform.machine(), "phase": "candidate-generation", "commands": [],
              "complete": False, "stopExitCode": None}
    require(not (state / "run.json").exists(), "Do not overwrite an earlier invocation")
    write_json(state / "run.json", record)
    versions = {}
    for name, argv in (("macos", ["sw_vers"]), ("xcode", ["xcodebuild", "-version"]),
                       ("iosSdk", ["xcrun", "--sdk", "iphonesimulator", "--show-sdk-version"]),
                       ("java17", [os.environ["JAVA_HOME"] + "/bin/java", "-version"]),
                       ("java21", [os.environ["RPC_JDK21"] + "/bin/java", "-version"])):
        version = subprocess.run(argv, capture_output=True, text=True, timeout=45, check=True)
        versions[name] = (version.stdout + version.stderr).strip()
    require(versions["xcode"].splitlines()[0] == "Xcode 26.5", "Wrong selected Xcode")
    require(re.search(r'version "17\.', versions["java17"]) and
            re.search(r'version "21\.', versions["java21"]), "Wrong Java prerequisites")
    write_json(reports / "toolchain.json", versions)
    flags = [*FLAGS, "-Dorg.gradle.jvmargs=-Xmx2048m -XX:MaxMetaspaceSize=768m "
             "-XX:ActiveProcessorCount=2 -Dfile.encoding=UTF-8 "
             f"-Duser.home={state}/home -Djava.io.tmpdir={state}/tmp"]
    try:
        for label, arguments, timeout in generator_commands():
            print(f"Starting {label}; full output remains private, sanitized diagnostics follow.", flush=True)
            row = execute(state, label, [str(ROOT / "gradlew"), *arguments, *flags], timeout)
            # Source and task arguments are public; replace ephemeral home paths in shared receipts.
            row["command"] = [part.replace(str(state), "<owned-state>").replace(str(ROOT), "<source>")
                              for part in row["command"]]
            record["commands"].append(row)
            write_json(state / "run.json", record)
            print(f"{label}: exit {row['exitCode']}, {row['seconds']} seconds", flush=True)
            print("\n".join(safe_diagnostics(state / f"{label}.log")), flush=True)
            if row["exitCode"] != 0:
                return row["exitCode"]
        record["complete"] = True
        return 0
    finally:
        stop = execute(state, "stop-owned-gradle", [str(ROOT / "gradlew"), "--stop", "--console=plain"], 90)
        record["stopExitCode"] = stop["exitCode"]
        record["complete"] = record["complete"] and stop["exitCode"] == 0
        write_json(state / "run.json", record)
        require(stop["exitCode"] == 0, "Owned Gradle cleanup did not complete")


def collect(state, reports):
    record = json.loads(read_bounded(state / "run.json")) if (state / "run.json").is_file() else {
        "source": os.environ["GITHUB_SHA"], "complete": False, "phase": "SETUP_DID_NOT_COMPLETE"}
    write_json(reports / "run.json", record)
    write_json(reports / "test-summary.json", test_summary(ROOT))
    diagnostic = []
    for path in sorted(state.glob("*.log")):
        diagnostic.extend([path.name, *safe_diagnostics(path)])
    (reports / "diagnostics.txt").write_text("\n".join(diagnostic) + "\n", encoding="utf-8")
    manifest, patch = collect_candidates(ROOT, record.get("complete") is True)
    write_json(reports / "candidate-manifest.json", manifest)
    (reports / "candidate.patch").write_bytes(patch)
    print(manifest["status"], flush=True)
    require(not record.get("complete") or manifest["status"] == "REVIEW_REQUIRED",
            "Successful generation did not supply all mandatory lock/ABI inputs")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("generate", "collect"))
    args = parser.parse_args()
    state, reports = paths()
    if args.operation == "collect":
        collect(state, reports)
        return 0
    def interrupted(signum, frame):
        raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM, interrupted)
    return generate(state, reports)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (Exception, KeyboardInterrupt) as error:
        # Do not expose exception text: dependency/test messages can contain payloads.
        detail = str(error) if isinstance(error, HostedValidationError) else type(error).__name__
        print(f"RPC hosted validation failed: {detail}", file=sys.stderr)
        sys.exit(125)
