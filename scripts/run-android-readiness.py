#!/usr/bin/env python3
"""Opt-in real ART 128/256 raw-I/O probe; not authenticated RPC or physical/mobile capacity qualification."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("android_owner", ROOT / "scripts/run-android-ui-validation.py")
owner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(owner)
need = owner.need
PACKAGE = "dev.p2pkit.transport.lan.test"
RUNNER = "dev.p2pkit.transport.lan.LanReadinessInstrumentation"
SCOPE = "RAW_ANDROID_IO_NOT_AUTHENTICATED_RPC_OR_PHYSICAL_QUALIFICATION"


def verify_installed_apk(device, installed, source_apk, report, run):
    """Hash actual installed bytes, without a guest hash utility or the adb sync STAT protocol."""
    need(re.fullmatch(r"package:/data/app/(?:[-A-Za-z0-9_.~+=]+/)+base\.apk", installed) and
         all(part not in (".", "..") for part in installed.removeprefix("package:").split("/")),
         "Ambiguous installed APK")
    # A new private destination prevents adb from accidentally reusing an earlier observation.
    # Do not retain a second APK in the evidence bundle; preserve its bound digest instead.
    with tempfile.TemporaryDirectory(prefix="installed-apk-", dir=report) as directory:
        pulled = Path(directory) / "base.apk"
        path = installed.removeprefix("package:")
        # Preserve the OS observation too: API24's adb sync pull reported ENOENT for pm's path.
        # exec-out streams exact binary bytes through the public shell API, without text conversion
        # or dependency on an older device's file-transfer metadata protocol. A failed cat still fails.
        run([*device, "shell", "ls", "-ldn", str(Path(path).parent), path], check=False)
        run([*device, "exec-out", "cat", path], timeout=90, stdout_file=pulled)
        need(pulled.is_file() and not pulled.is_symlink() and
             pulled.stat().st_size == source_apk.stat().st_size, "Incomplete installed APK observation")
        actual = hashlib.sha256(pulled.read_bytes()).hexdigest()
        need(actual == hashlib.sha256(source_apk.read_bytes()).hexdigest(),
             "Installed bytes differ from the source-built APK")
        return actual


def result(raw):
    fields, codes = {}, []
    for line in raw.decode("utf-8").splitlines():
        if line.startswith("INSTRUMENTATION_RESULT: "):
            key, value = line.removeprefix("INSTRUMENTATION_RESULT: ").split("=", 1)
            need(key not in fields, "Duplicate instrumentation field")
            fields[key] = value
        elif line.startswith("INSTRUMENTATION_CODE: "):
            codes.append(line.removeprefix("INSTRUMENTATION_CODE: "))
    need(raw.endswith(b"\n") and codes == ["-1"] and fields.get("outcome") == "PASS" and
         fields.get("completed") == "4" and fields.get("scope") == SCOPE and
         not any(key.startswith("failure") for key in fields), "Incomplete/failed Android I/O probe")
    measures = json.loads(fields["measurements"])
    need(len(measures) == 4 and {(m["backend"], m["clients"]) for m in measures} ==
         {(backend, clients) for backend in ("nio-selector", "native-os-poll") for clients in (128, 256)},
         "Wrong Android backend/capacity inventory")
    for m in measures:
        need(m["responses"] == m["clients"] * 300 and m["bytesPerResponse"] == 1024 and
             m["readinessThreads"] == (2 if m["backend"] == "native-os-poll" else 1) and
             m["threadsIdle"] - m["threadsBefore"] < 80 and
             m["idleWallNs"] >= 5_000_000_000 and m["activeWallNs"] > 0,
             "Incomplete Android workload/resource evidence")
    return measures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", type=int, choices=(24, 35), required=True)
    args = parser.parse_args()
    need(sys.platform == "linux" and os.access("/dev/kvm", os.R_OK | os.W_OK), "Actual readable/writable KVM required")
    need(re.fullmatch(r"[0-9a-f]{32}", os.environ.get("P2PKIT_AUDIT_JOB_ID", "")) and
         os.environ.get("P2PKIT_CI_COMMAND_DEADLINE_NS"), "Use the maintained ci_evidence.py supervisor")
    sdk = Path(os.environ["ANDROID_HOME"]).resolve()
    image = f"system-images;android-{args.api};google_apis;x86_64"
    report = ROOT / f"build/reports/android-readiness-{args.api}"
    report.mkdir(parents=True, mode=0o700, exist_ok=False)
    env = dict(os.environ)
    counter = 0
    deadline = int(env["P2PKIT_CI_COMMAND_DEADLINE_NS"]) / 1_000_000_000

    def run(command, *, timeout=30, check=True, input_bytes=None, stdout_file=None):
        nonlocal counter
        counter += 1
        log = report / f"command-{counter:03d}.log"
        end = min(deadline, time.monotonic() + timeout)
        with contextlib.ExitStack() as files:
            capture = files.enter_context(log.open("xb"))
            output = capture if stdout_file is None else files.enter_context(stdout_file.open("xb"))
            process = subprocess.Popen([str(item) for item in command], cwd=ROOT, env=env,
                                       stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                                       stdout=output, stderr=capture)
            try:
                if input_bytes is not None:
                    process.stdin.write(input_bytes)
                    process.stdin.close()
                while process.poll() is None:
                    need(time.monotonic() < end and log.stat().st_size <= 16 * 1024 * 1024 and
                         (stdout_file is None or stdout_file.stat().st_size <= 16 * 1024 * 1024),
                         f"Bounded command {counter} failed to settle")
                    time.sleep(0.1)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=10)  # Outer native scope also owns and observes descendants.
        need(not check or process.returncode == 0, f"Command {counter} failed; inspect original private evidence")
        return process.returncode, log.read_bytes()

    def git(*args):
        return run(["git", *args])[1].decode().strip()

    source, tree = git("rev-parse", "HEAD"), git("rev-parse", "HEAD^{tree}")
    need(not git("status", "--porcelain=v1"), "Clean exact source required")
    run([ROOT / "gradlew", ":p2p-transport-lan:assembleAndroidDeviceTest",
         "-Pp2pkit.lan.readinessDeviceTest=true", "--dependency-verification=strict",
         "--no-daemon", "--max-workers=2", "--console=plain"], timeout=1800)
    apks = list((ROOT / "library/p2p-transport-lan/build/outputs/apk").rglob("*.apk"))
    need(len(apks) == 1, "Exactly one source-built device-test APK required")
    apk = apks[0]
    raw = run([sdk / "cmdline-tools/latest/bin/apkanalyzer", "manifest", "print", apk])[1]
    (report / "manifest.xml").write_bytes(raw)
    manifest = ET.fromstring(raw)
    ns = "{http://schemas.android.com/apk/res/android}"
    instrumentation = manifest.find("instrumentation")
    need(manifest.get("package") == PACKAGE and instrumentation is not None and
         instrumentation.get(ns + "name") == RUNNER and instrumentation.get(ns + "targetPackage") == PACKAGE,
         "Wrong instrumentation package/runner")
    digest = hashlib.sha256(apk.read_bytes()).hexdigest()
    private = Path(tempfile.mkdtemp(prefix="android-readiness-", dir=os.environ.get("RUNNER_TEMP")))
    for name in ("home", "android", "avd"):
        (private / name).mkdir(mode=0o700)
    env.update(HOME=str(private / "home"), ANDROID_USER_HOME=str(private / "android"),
               ANDROID_EMULATOR_HOME=str(private / "android"), ANDROID_AVD_HOME=str(private / "avd"))
    server_port, console_port = owner.free_port(), owner.emulator_port()
    env.update(ANDROID_ADB_SERVER_PORT=str(server_port), ADB_SERVER_SOCKET=f"tcp:127.0.0.1:{server_port}")
    adb = [sdk / "platform-tools/adb", "-P", str(server_port)]
    device = [*adb, "-s", f"emulator-{console_port}"]
    avd = "p2pkit-readiness-" + uuid.uuid4().hex
    emulator = None
    measures = None
    try:
        run([sdk / "cmdline-tools/latest/bin/avdmanager", "create", "avd", "--name", avd,
             "--package", image, "--path", private / "avd" / avd], timeout=90, input_bytes=b"no\n")
        config = private / "avd" / avd / "config.ini"
        config.write_text(owner.configure_new_avd_userdata(config.read_text()))
        run([*adb, "start-server"])
        with (report / "emulator.log").open("xb") as capture:
            emulator = subprocess.Popen([str(sdk / "emulator/emulator"), "-avd", avd, "-port", str(console_port),
                "-accel", "on", "-gpu", "swiftshader", "-memory", "2048", "-cores", "2", "-no-window",
                "-no-audio", "-no-boot-anim", "-no-snapshot", "-no-metrics"],
                cwd=ROOT, env=env, stdin=subprocess.DEVNULL, stdout=capture, stderr=capture)
            owner.admit_android_guest(run, device, emulator, avd, args.api, report)
            run([*device, "install", "--no-streaming", apk], timeout=90)
            installed = run([*device, "shell", "pm", "path", PACKAGE])[1].decode().strip()
            need(verify_installed_apk(device, installed, apk, report, run) == digest,
                 "Source-built APK changed during installed-byte observation")
            raw = run([*device, "shell", "am", "instrument", "-w", "-r", PACKAGE + "/" + RUNNER], timeout=390)[1]
            (report / "instrumentation.txt").write_bytes(raw)
            measures = result(raw)
    finally:
        if emulator is not None and emulator.poll() is None:
            emulator.terminate()
            try:
                emulator.wait(timeout=20)
            except subprocess.TimeoutExpired:
                emulator.kill()
                emulator.wait(timeout=10)
        run([*adb, "kill-server"])
    need(not git("status", "--porcelain=v1") and git("rev-parse", "HEAD") == source, "Source changed")
    owner.write_json(report / "result.json", dict(source=source, tree=tree, apkSha256=digest, api=args.api,
                     scope=SCOPE, measurements=measures, emulatorExit=emulator.returncode,
                     cleanup="Original leader exit observed; outer native scope must verify descendants"))
    print(f"ANDROID_RAW_IO_COMPLETE api={args.api}; inspect actual measurements; no RPC/mobile-capacity credit")


if __name__ == "__main__":
    main()
