#!/usr/bin/env python3
"""Source-bound API35 Compose/Activity witnesses, NOT physical or API37 LAN acceptance.

Run under ci_evidence.py: it owns and retires all marker-inheriting descendants and
retains encrypted output. This controller uses only a fresh AVD/private adb server;
it never discovers or operates on personal devices. A harness pass still needs
independent screenshot/Parcel review and separately committed mutation controls.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "dev.p2pkit.sample.android"
IMAGE = "system-images;android-35;google_apis;x86_64"
CASES = {
    "317": (PACKAGE + ".runtime.UiAcceptanceInstrumentation", "diagnosticEventAppearsWithoutInput", 180),
    "324": (PACKAGE + ".runtime.CredentialUiInstrumentation", "productionCredentialRestorationAndLifecycle", 240),
}
LIMIT = 64 * 1024 * 1024
PASS = "HARNESS_PASS_PENDING_REVIEW"


def need(condition, message):
    if not condition:
        raise ValueError(message)


def decode_json(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, "Duplicate JSON key")
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique)


def instrumentation_result(raw, case, token):
    """Exit zero/crashes/partial or duplicate bundles never earn a harness pass."""
    fields, pending, frames, codes = {}, {}, [], []
    for line in raw.decode("utf-8", errors="strict").splitlines():
        if line.startswith(("INSTRUMENTATION_STATUS: ", "INSTRUMENTATION_RESULT: ")):
            prefix, field = line.split(": ", 1)
            key, separator, value = field.partition("=")
            target = pending if prefix == "INSTRUMENTATION_STATUS" else fields
            need(separator and key and key not in target, "Invalid or duplicate instrumentation field")
            target[key] = value
        elif line.startswith("INSTRUMENTATION_STATUS_CODE: "):
            frames.append((line.split(": ", 1)[1], pending))
            pending = {}
        elif line.startswith("INSTRUMENTATION_CODE: "):
            codes.append(line.split(": ", 1)[1])
        elif line.startswith("INSTRUMENTATION_"):
            raise ValueError("Unexpected instrumentation error")
    required = {"p2pkitToken": token, "p2pkitCompleted": "1", "p2pkitOutcome": PASS,
                "p2pkitEvidence": f"no_backup/ui-{case}-{token}", "class": CASES[case][0],
                "test": CASES[case][1], "numtests": "1", "current": "1"}
    if case == "317":
        required["p2pkitCleanup"] = "RETIRED_OWNED_OBSERVERS"
    need(codes == ["-1"] and not pending and len(frames) == 1 and frames[0][0] == "0",
         "Incomplete or failed instrumentation")
    need(all(fields.get(key) == value and frames[0][1].get(key) == value for key, value in required.items()),
         "Wrong instrumentation identity or outcome")
    need(fields == frames[0][1] and not any("Failure" in key or key == "p2pkitRetention" for key in fields),
         "Inconsistent or failed final evidence")
    return fields


def evidence_members(raw):
    """Read only bounded synthetic files; never extract links or traversal members."""
    need(0 < len(raw) <= 128 * 1024 * 1024, "Evidence archive size")
    files, total = {}, 0
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
        for entry in archive:
            name = entry.name[2:] if entry.name.startswith("./") else entry.name
            if entry.isdir() and name in ("", "."):
                continue
            path = PurePosixPath(name)
            need(entry.isfile() and not path.is_absolute() and ".." not in path.parts and
                 len(path.parts) == 1 and name not in files and re.fullmatch(r"[a-zA-Z0-9_.-]+", name),
                 "Unsafe or duplicate evidence member")
            need(0 <= entry.size <= 16 * 1024 * 1024 and len(files) < 256, "Evidence member limit")
            total += entry.size
            need(total <= 128 * 1024 * 1024, "Expanded evidence limit")
            with archive.extractfile(entry) as stream:
                files[name] = stream.read(entry.size + 1)
            need(len(files[name]) == entry.size, "Truncated evidence")
    need("result.json" in files, "Missing result")
    return files


def validate_report(raw, case, token, source, tree):
    report = decode_json(raw)
    need(report.get("case") == case and report.get("sourceCommit") == source and
         report.get("declaredSourceTree") == tree and report.get("api") == 35 and
         report.get("targetSdk") == 37 and report.get("outcome") == PASS, "Wrong retained result")
    # The credential runner's directory/final bundle bind the token; it does not
    # duplicate it in JSON. #317 additionally records it in the JSON report.
    if case == "317":
        need(report.get("token") == token and not report.get("cleanupFailures") and
             report.get("independentVisualAndMutationReview") == "REQUIRED_NOT_PERFORMED_BY_RUNNER",
             "Diagnostic cleanup or review declaration")
    else:
        cleanup = report.get("cleanup")
        need(isinstance(cleanup, list) and cleanup and
             all(item.get("outcome") == "RETIRED" for item in cleanup) and
             report.get("lifecycleViolation") is False, "Credential cleanup or lifecycle failure")
    return report


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def emulator_port():
    # No kill/adoption on collision: the fresh emulator's launch must succeed.
    for port in range(5554, 5682, 2):
        try:
            with socket.socket() as first, socket.socket() as second:
                first.bind(("127.0.0.1", port))
                second.bind(("127.0.0.1", port + 1))
                return port
        except OSError:
            continue
    raise ValueError("No unused emulator console pair")


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=("317", "324", "both"), default="both")
    args = parser.parse_args(argv)
    need(sys.platform == "linux" and os.access("/dev/kvm", os.R_OK | os.W_OK), "Readable/writable Linux KVM required")
    need(re.fullmatch(r"[0-9a-f]{32}", os.environ.get("P2PKIT_AUDIT_JOB_ID", "")) and
         os.environ.get("P2PKIT_CI_COMMAND_DEADLINE_NS"), "Run inside ci_evidence.py ownership scope")
    sdk = Path(os.environ.get("ANDROID_HOME") or os.environ["ANDROID_SDK_ROOT"]).resolve()
    report = ROOT / "build/reports/android-ui"
    need(not report.exists(), "Fresh UI report directory required")
    report.mkdir(parents=True, mode=0o700)
    env = dict(os.environ)
    deadline = int(env["P2PKIT_CI_COMMAND_DEADLINE_NS"]) / 1_000_000_000
    counter = 0

    def run(command, *, timeout=30, check=True, input_bytes=None):
        nonlocal counter
        counter += 1
        left = deadline - time.monotonic()
        need(left > 0, "Outer deadline reached")
        log = report / f"command-{counter:03d}.log"
        error_log = report / f"command-{counter:03d}.stderr"
        with log.open("xb") as out, error_log.open("xb") as err:
            with subprocess.Popen([str(item) for item in command], cwd=ROOT, env=env,
                                  stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                                  stdout=out, stderr=err) as process:
                if input_bytes is not None:
                    process.stdin.write(input_bytes)
                    process.stdin.close()
                end = time.monotonic() + min(timeout, left)
                try:
                    while process.poll() is None:
                        need(time.monotonic() < end, "Bounded command timed out")
                        need(log.stat().st_size + error_log.stat().st_size <= LIMIT, "Command output limit")
                        time.sleep(0.1)
                except BaseException:
                    process.kill()  # This exact owned leader; outer native scope retires descendants.
                    process.wait(timeout=10)
                    raise
        need(log.stat().st_size + error_log.stat().st_size <= LIMIT, "Command output limit")
        need(not check or process.returncode == 0, f"Command {counter} failed; inspect encrypted capture")
        return process.returncode, log.read_bytes()

    def git(*arguments):
        return run(["git", *arguments])[1].decode().strip()

    need(not git("status", "--porcelain", "--untracked-files=normal"), "Clean committed source required")
    source, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    write_json(report / "source.json", {"commit": source, "tree": tree, "case": args.case,
               "scope": "API35 rendered UI only; not physical, API37 permissions or mutation acceptance"})
    run([ROOT / "gradlew", ":p2p-sample-android:clean", ":p2p-sample-android:assembleDebug",
         ":p2p-sample-android:assembleDebugAndroidTest", "--no-daemon", "--max-workers=2", "--console=plain"], timeout=2400)
    sample = ROOT / "samples/p2p-sample-android/build"
    app_apk = sample / "outputs/apk/debug/p2p-sample-android-debug.apk"
    test_apk = sample / "outputs/apk/androidTest/debug/p2p-sample-android-debug-androidTest.apk"
    spec = importlib.util.spec_from_file_location("android_art", ROOT / "scripts/run-android-art-smoke.py")
    art = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(art)
    apks = {}
    for label, apk in (("app", app_apk), ("test", test_apk)):
        need(apk.is_file() and 0 < apk.stat().st_size <= 256 * 1024 * 1024, "Missing or oversized APK")
        manifest = run([sdk / "cmdline-tools/latest/bin/apkanalyzer", "manifest", "print", apk])[1]
        (report / f"{label}-manifest.xml").write_bytes(manifest)
        if label == "test":
            art.verify_test_apk_manifest(manifest)
        else:
            xml = art.xml(manifest)
            ns = "{http://schemas.android.com/apk/res/android}"
            need(xml.get("package") == PACKAGE and xml.find("uses-sdk").get(ns + "targetSdkVersion") == "37",
                 "Wrong application package or target")
        apks[label] = {"sha256": hashlib.sha256(apk.read_bytes()).hexdigest(), "bytes": apk.stat().st_size}
    write_json(report / "apks.json", apks)
    for label, relative in (("ndk", "ndk/29.0.14206865/source.properties"),
                            ("emulator", "emulator/source.properties"),
                            ("system-image", "system-images/android-35/google_apis/x86_64/source.properties")):
        (report / f"{label}-source.properties").write_bytes((sdk / relative).read_bytes())
    need(not git("status", "--porcelain", "--untracked-files=normal") and git("rev-parse", "HEAD") == source,
         "Source changed during build")
    # Keep tooling state separate from Gradle's HOME and the host's adb keys/AVDs.
    private = Path(tempfile.mkdtemp(prefix="android-ui-", dir=os.environ.get("RUNNER_TEMP")))
    for name in ("home", "android", "avd"):
        (private / name).mkdir(mode=0o700)
    env.update(HOME=str(private / "home"), ANDROID_USER_HOME=str(private / "android"),
               ANDROID_EMULATOR_HOME=str(private / "android"), ANDROID_AVD_HOME=str(private / "avd"))
    server_port, console_port = free_port(), emulator_port()
    env.update(ANDROID_ADB_SERVER_PORT=str(server_port), ADB_SERVER_SOCKET=f"tcp:127.0.0.1:{server_port}")
    serial = f"emulator-{console_port}"
    adb = [sdk / "platform-tools/adb", "-P", str(server_port)]
    device = [*adb, "-s", serial]
    emulator = None
    avd = "p2pkit-ui-" + uuid.uuid4().hex
    results, cleanup = {}, []
    try:
        run([sdk / "cmdline-tools/latest/bin/avdmanager", "create", "avd", "--name", avd,
             "--package", IMAGE, "--path", private / "avd" / avd], timeout=90, input_bytes=b"no\n")
        config = private / "avd" / avd / "config.ini"
        with config.open("a") as output:
            output.write("\nhw.lcd.width=1600\nhw.lcd.height=2560\nhw.lcd.density=200\nhw.keyboard=yes\n")
        run([*adb, "start-server"])
        with (report / "emulator.log").open("xb") as emulog:
            emulator = subprocess.Popen([str(sdk / "emulator/emulator"), "-avd", avd, "-port", str(console_port),
                "-accel", "on", "-gpu", "swiftshader", "-memory", "2048", "-cores", "2", "-no-window",
                "-skin", "1600x2560", "-dpi-device", "200", "-no-audio", "-no-boot-anim", "-no-snapshot", "-no-metrics"],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=emulog, stderr=emulog)
            boot_end = time.monotonic() + 180
            while True:
                need(emulator.poll() is None, "Owned emulator exited before admission")
                need(time.monotonic() < boot_end, "Emulator boot deadline")
                code, boot = run([*device, "shell", "getprop", "sys.boot_completed"], timeout=15, check=False)
                if code == 0 and boot.strip() == b"1":
                    break
                time.sleep(2)
            need(run([*device, "emu", "avd", "name"])[1].decode().splitlines()[0] == avd,
                 "Serial is not the invocation-owned AVD")
            need(run([*device, "shell", "getprop", "ro.build.version.sdk"])[1].strip() == b"35", "API35 required")
            runtime = run([*device, "shell", "getprop"])[1]
            (report / "runtime-properties.txt").write_bytes(runtime)
            run([*device, "shell", "input", "keyevent", "82"])
            for case in CASES if args.case == "both" else (args.case,):
                case_dir = report / case
                case_dir.mkdir(mode=0o700)
                # Sequential cases get a genuinely fresh install, not pm clear/restore.
                if results:
                    run([*device, "uninstall", PACKAGE + ".test"])
                    run([*device, "uninstall", PACKAGE])
                run([*device, "install", "--no-streaming", app_apk], timeout=90)
                run([*device, "install", "--no-streaming", test_apk], timeout=90)
                token = uuid.uuid4().hex
                write_json(case_dir / "request.json", {"case": case, "token": token, "sourceCommit": source,
                           "sourceTree": tree, "runner": CASES[case][0]})
                code, output = run([*device, "shell", "am", "instrument", "-w", "-r", "-e", "case", case,
                    "-e", "token", token, "-e", "sourceCommit", source, "-e", "sourceTree", tree,
                    PACKAGE + ".test/" + CASES[case][0]], timeout=CASES[case][2], check=False)
                (case_dir / "instrumentation.txt").write_bytes(output)
                # Pull only our synthetic case directory, even on instrumentation failure.
                archive_code, raw = run([*device, "exec-out", "run-as", PACKAGE, "tar", "-C",
                    f"no_backup/ui-{case}-{token}", "-cf", "-", "."], timeout=30, check=False)
                if archive_code == 0:
                    for name, value in evidence_members(raw).items():
                        (case_dir / name).write_bytes(value)
                need(code == 0 and archive_code == 0, "Instrumentation or evidence capture failed")
                instrumentation_result(output, case, token)
                validate_report((case_dir / "result.json").read_bytes(), case, token, source, tree)
                results[case] = PASS
    finally:
        if emulator is not None:
            if emulator.poll() is None:
                emulator.terminate()
                try:
                    emulator.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    emulator.kill()
                    emulator.wait(timeout=10)
            cleanup.append("owned emulator leader exited; outer native scope verifies descendants")
        run([*adb, "kill-server"], check=True)
        cleanup.append("private adb server stop requested; outer native scope verifies exit")
        write_json(report / "controller-result.json", {"cases": results, "cleanup": cleanup,
                   "review": "REQUIRED: original screenshots/Parcel/lifecycle and immutable mutation controls",
                   "notQualified": ["physical phones", "API29/OEM", "API37 LAN permission revocation"]})
        # The outer evidence scope establishes complete retirement before deleting
        # its private state. Do not delete live daemon/tool state speculatively.
    need(not git("status", "--porcelain", "--untracked-files=normal") and git("rev-parse", "HEAD") == source,
         "Source changed during runtime")
    print("UI harness completed; independent original-evidence and mutation review remains required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
