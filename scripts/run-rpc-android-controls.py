#!/usr/bin/env python3
"""Explicit supplemental API24 software-emulator RPC controls, never the maintained ART gate.

Requires a successful source-bound APK producer and an admitted native executor.
Uses an already installed SDK, a NEW 2-GiB-data AVD and a private loopback adb server. Does
not download tools, alter KVM/HVF permissions, grant app permissions, or start RPC
traffic. API37 permission, real-LAN interoperability and phone capacity stay separate.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import time
import uuid

CONTROL_NAMES = (
    "keystore-round-trip-nonexportable", "namespaces-and-128-pin-bound",
    "tamper-fails-closed-without-erasing-approval", "authenticated-purpose-isolation",
    "real-rpc-client-identity-persistence-not-sent-and-close", "phone-input-fails-closed",
    "actual-foreground-debug-activity-and-destruction",
    "mobile-private-files-atomic-publication-and-negative-admission",
    "mobile-actual-self-process-cpu-rss-and-thread-counters",
    "missing-key-never-recreates-or-clears-existing-trust",
)
PACKAGE = "dev.p2pkit.sample.android"
SCOPE = "SUPPLEMENTAL_CONTROLS_NO_NETWORK_OR_CAPACITY_CLAIM"
LIMIT = 32 * 1024 * 1024
SHELL_SCOPE = "ACTUAL_ANDROID_SHELL_V2_FILES_NOT_PHYSICAL_USB_OR_RPC"
SHELL_COMMANDS = (
    "control-shell-features", "control-shell-prepare", "control-shell-read-inbox",
    "control-shell-missing", "control-shell-reprepare", "control-shell-read-unchanged",
    "control-shell-stop", "control-shell-restop", "control-shell-read-stop",
)


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def configure_avd(text, image):
    # Size only this new supplemental fixture's userdata, not the system image
    # or a maintained ART gate. Pixel 2's 10-GiB default is unnecessary for the
    # two APKs and ten non-network controls. This is not storage qualification.
    for key in ("image.sysdir.1", "disk.dataPartition.size"):
        need(len(re.findall(r"(?m)^" + re.escape(key) + r"=.*$", text)) == 1,
             "Missing/ambiguous AVD property: " + key)
    text = re.sub(r"(?m)^image.sysdir.1=.*$", lambda _: "image.sysdir.1=" + str(image) + "/", text)
    return re.sub(r"(?m)^disk.dataPartition.size=.*$", "disk.dataPartition.size=2G", text)


def assess_instrumentation(raw, token):
    need(len(raw) <= 262144, "Oversized instrumentation result")
    pairs = re.findall(r"^INSTRUMENTATION_RESULT: ([A-Za-z0-9]+)=(.*)$", raw, re.M)
    need(len(pairs) == len({key for key, _ in pairs}), "Duplicate instrumentation result field")
    fields = dict(pairs)
    terminals = [line for line in raw.splitlines() if line.startswith("INSTRUMENTATION_CODE:")]
    need(terminals == ["INSTRUMENTATION_CODE: -1"] and "INSTRUMENTATION_FAILED" not in raw,
         "Instrumentation did not finish successfully")
    expected = dict(rpcToken=token, rpcApi="24", rpcAbi="x86_64", rpcVm="Dalvik", rpcScope=SCOPE,
                    rpcOutcome="PASS", rpcCleanup="PASS", rpcCompleted=str(len(CONTROL_NAMES)))
    expected.update({f"rpcControl{index}": name for index, name in enumerate(CONTROL_NAMES, 1)})
    need(fields == expected, "Incomplete, wrong-device, mismatched-token or failed RPC controls")
    return fields


def module(root, name, filename):
    spec = importlib.util.spec_from_file_location(name, root / "scripts" / filename)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def control_shell_checks(invoke, usb, run_label):
    """The exact mobile shell grammar, on our own disposable AVD/package, not a USB-device substitute."""
    need(re.fullmatch(r"[a-z0-9-]{1,64}", run_label), "Invalid fresh shell-control run label")
    completed = []
    def command(label, argv, data=None, expected=0, output=b""):
        need(label == SHELL_COMMANDS[len(completed)], "Unexpected shell control order")
        code, raw = invoke(label, argv, data)
        need(type(code) is int and (code in (1, 2) if expected == "refused" else code == expected) and
             type(raw) is bytes and len(raw) <= 16384, "Android shell control exit/type mismatch: " + label)
        if output is not None:
            need(raw == output, "Android shell control output mismatch: " + label)
        completed.append(label)
        return raw
    features = command("control-shell-features", ["features"], output=None)
    need(usb.android_shell_v2_supported(features), "Actual Android shell-v2 support is required")
    data = b"schema=1\nvalue=non-executable;fixture\n"
    command("control-shell-prepare", usb.android_shell(run_label, "prepare"), data=data)
    command("control-shell-read-inbox", usb.android_shell(run_label, "read", "inbox.txt"), output=data)
    command("control-shell-missing", usb.android_shell(run_label, "read", "ready.txt"), expected=44)
    command("control-shell-reprepare", usb.android_shell(run_label, "prepare"),
            data=b"schema=2\n", expected="refused")
    command("control-shell-read-unchanged", usb.android_shell(run_label, "read", "inbox.txt"), output=data)
    stop = b"action=stop\n"
    command("control-shell-stop", usb.android_shell(run_label, "stop"), data=stop)
    command("control-shell-restop", usb.android_shell(run_label, "stop"),
            data=b"action=changed\n", expected="refused")
    command("control-shell-read-stop", usb.android_shell(run_label, "read", "stop.txt"), output=stop)
    need(tuple(completed) == SHELL_COMMANDS, "Incomplete Android shell controls")
    return dict(scope=SHELL_SCOPE, completed=list(completed), passed=True)


def stat_dereference_probe():
    """Read-only tool observation: 0=supported, 69=explicit unknown -L, 70=unexplained failure.

    No failure here substitutes for any original shell/file control. The
    descriptor is a new /dev/null handle, never an application data record.
    """
    script = '''set -eu
export LC_ALL=C
exec 3< /dev/null
code=0
reply=$(stat -Lc %f /proc/self/fd/5 5<&3 2>&1) || code=$?
test "${#reply}" -le 16384 || exit 70
if test "$code" -eq 0; then
    case "$reply" in ''|*[!a-fA-F0-9]*) exit 70;; *) exit 0;; esac
fi
test "$code" -eq 1 || exit 70
# Android 7 toybox help_exit emits usage before the terminal error; args.c
# reports the complete unconsumed option suffix (Lc). Do not mistake that
# known format for an unexplained failure, or accept arbitrary error tails.
case "$reply" in
    "stat: Unknown option 'L'"|"stat: Unknown option L"|"stat: Unknown option Lc") exit 69;;
    "usage: stat [-f] [-c FORMAT] FILE..."*"
stat: Unknown option Lc") exit 69;;
    *) exit 70;;
esac
'''
    return ['shell', '-T', '-e', 'none', 'run-as ' + PACKAGE + ' sh -c ' + shlex.quote(script)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-authorized-software-emulator", action="store_true")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--sdk", type=Path, required=True)
    parser.add_argument("--producer-receipt", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    args = parser.parse_args()
    need(args.owner_authorized_software_emulator and os.environ.get("P2PKIT_AUDIT_OWNERSHIP_CHAIN"),
         "Explicit owner authorization and admitted native ownership required")
    os.umask(0o077)
    sys.dont_write_bytecode = True
    root, sdk = args.root.resolve(strict=True), args.sdk.resolve(strict=True)
    sys.path.insert(0, str(root / "scripts"))
    audit = module(root, "rpc_art_audit", "run-audit-command.py")
    checker = module(root, "rpc_art_checker", "check-audit-receipt.py")
    art = module(root, "rpc_art_manifest", "run-android-art-smoke.py")
    state, context = audit.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    need(root == Path(context["root"]) and context["source"]["status"] == "", "Wrong/dirty source candidate")
    producer = audit.read_json(args.producer_receipt)
    checker.validate(producer, 0, producer["purpose"], root, root / "gradlew", producer["requestedArgv"])
    need(producer["sourceBefore"] == producer["sourceAfter"] == context["source"] and
         producer["sourceUnchanged"] and not producer["errors"] and not producer["ownedSurvivors"] and
         not producer["ownership"]["discoveryErrors"] and producer["stopExitCode"] == 0,
         "APK producer did not finalize unchanged and successfully")
    need({":p2p-sample-android:assembleDebug", ":p2p-sample-android:assembleDebugAndroidTest"}.issubset(
        producer["requestedArgv"]), "Both real APK producer tasks are required")
    work = args.directory
    need(work.is_absolute() and work.parent == state / "work" and
         re.fullmatch(r"[a-z0-9-]{1,64}", work.name), "Only a new directly owned work directory is allowed")
    audit.reject_symlinks(work.parent)
    work.mkdir(mode=0o700)
    app = root / "samples/p2p-sample-android/build/outputs/apk/debug/p2p-sample-android-debug.apk"
    test = root / "samples/p2p-sample-android/build/outputs/apk/androidTest/debug/p2p-sample-android-debug-androidTest.apk"
    for path in (sdk, app, test):
        audit.reject_symlinks(path)
        need(path.exists(), "Required existing SDK/APK is missing")
    result = dict(schema=1, scope=SCOPE, status="FAIL", source=context["source"],
                  producerReceiptSha256=digest(args.producer_receipt), scriptSha256=digest(Path(__file__)),
                  appSha256=digest(app), testApkSha256=digest(test), booted=False,
                  controlsPassed=False, capacityQualified=False, acceleration="off", api=24, cores=1,
                  commands=[], errors=[], startedUtc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    env = dict(os.environ)
    env.pop("ANDROID_SDK_ROOT", None)
    for name in ("home", "android-user", "avd", "tmp", "cache"):
        (work / name).mkdir(mode=0o700)
    env.update(HOME=str(work / "home"), ANDROID_HOME=str(sdk), ANDROID_USER_HOME=str(work / "android-user"),
               ANDROID_EMULATOR_HOME=str(work / "android-user"), ANDROID_AVD_HOME=str(work / "avd"),
               TMPDIR=str(work / "tmp"), XDG_CACHE_HOME=str(work / "cache"))
    counter = 0

    def run(label, argv, timeout=40, stdin=None, check=True):
        nonlocal counter
        counter += 1
        stem = f"{counter:03d}-{label}"
        row = dict(label=label, argv=list(map(str, argv)), timeoutSeconds=timeout)
        result["commands"].append(row)
        started = time.monotonic()
        try:
            with (work / (stem + ".stdout")).open("xb") as out, (work / (stem + ".stderr")).open("xb") as err:
                child = subprocess.Popen(row["argv"], env=env, stdin=subprocess.PIPE if stdin else subprocess.DEVNULL,
                                         stdout=out, stderr=err)
                if stdin:
                    child.stdin.write(stdin)
                    child.stdin.close()
                deadline = time.monotonic() + timeout
                while child.poll() is None:
                    need(time.monotonic() < deadline, "Command deadline: " + label)
                    need(out.tell() <= LIMIT and err.tell() <= LIMIT, "Command log bound: " + label)
                    time.sleep(.2)
                row["exitCode"] = child.returncode
        finally:
            # Observation only: the same native owner still drains a timed-out
            # child. No deadline, retry, cleanup or process-ownership change.
            row["elapsedMillis"] = round((time.monotonic() - started) * 1000)
        need(not check or child.returncode == 0, "Command failed: " + label)
        data = work / (stem + ".stdout")
        need(data.stat().st_size <= LIMIT, "Final command log exceeds bound")
        return data.read_bytes()

    server = emulator = None
    logs = []
    port = serial = avd = None

    def adb(label, *argv, timeout=40, check=True):
        need(server is not None and server.poll() is None, "Private adb exited")
        return run(label, [sdk / "platform-tools/adb", "-P", str(port), "-s", serial, *argv], timeout, check=check)

    try:
        # Inspect the produced binary manifest, not only its source declaration.
        # Reuse the maintained gate's exact inventory without selecting/replacing
        # its separate API37 permission test or accepting an extra runner.
        result["instrumentationRunners"] = art.verify_test_apk_manifest(run("test-apk-manifest",
            [sdk / "cmdline-tools/latest/bin/apkanalyzer", "manifest", "print", test], timeout=90))
        image = sdk / "system-images/android-24/default/x86_64"
        result["imageProperties"] = (image / "source.properties").read_text()
        result["emulatorProperties"] = (sdk / "emulator/source.properties").read_text()
        run("acceleration-observation", [sdk / "emulator/emulator", "-accel-check"], 30, check=False)
        avd = "rpc-phone-" + uuid.uuid4().hex[:16]
        run("avd-create", [sdk / "cmdline-tools/latest/bin/avdmanager", "--verbose", "create", "avd", "--name", avd,
                           "--package", "system-images;android-24;default;x86_64", "--device", "pixel_2",
                           "--path", work / "avd" / (avd + ".avd")], 90, stdin=b"no\n")
        config = work / "avd" / (avd + ".avd") / "config.ini"
        text = configure_avd(config.read_text(), image)
        config.write_text(text)
        result["avdConfig"] = text
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        emulator_port = 5580
        for number in (emulator_port, emulator_port + 1):
            with socket.socket() as probe:
                probe.bind(("127.0.0.1", number))
        serial = "emulator-" + str(emulator_port)
        env.update(ANDROID_ADB_SERVER_PORT=str(port), ADB_SERVER_SOCKET="tcp:127.0.0.1:" + str(port))
        log = (work / "adb-server.log").open("xb")
        logs.append(log)
        server = subprocess.Popen([str(sdk / "platform-tools/adb"), "-L", "tcp:" + str(port), "nodaemon", "server"],
                                  env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 20
        while True:
            need(server.poll() is None, "Private adb failed before readiness")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=.5):
                    break
            except OSError:
                need(time.monotonic() < deadline, "Private adb readiness deadline")
                time.sleep(.1)
        need(not [line for line in adb("initial-devices", "devices").decode().splitlines() if "\t" in line],
             "Private adb must initially have no devices")
        argv = [str(sdk / "emulator/emulator"), "-avd", avd, "-port", str(emulator_port), "-accel", "off",
                "-memory", "1536", "-cores", "1", "-gpu", "swiftshader", "-no-window", "-skin", "480x800",
                "-no-audio", "-no-boot-anim", "-no-snapshot", "-no-metrics", "-show-kernel"]
        result["emulatorArgv"] = argv
        result["bootBoundSeconds"] = 600
        log = (work / "emulator.log").open("xb")
        logs.append(log)
        emulator = subprocess.Popen(argv, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        started = time.monotonic()
        while True:
            need(emulator.poll() is None, "Emulator exited before boot")
            need(time.monotonic() - started < 600, "Software emulator boot deadline")
            need((work / "emulator.log").stat().st_size <= LIMIT, "Emulator log exceeded bound")
            if adb("boot-state", "shell", "getprop", "sys.boot_completed", check=False).strip() == b"1":
                break
            time.sleep(3)
        need(adb("avd-name", "emu", "avd", "name").decode().splitlines()[0] == avd, "Wrong AVD")
        need(adb("qemu", "shell", "getprop", "ro.kernel.qemu").strip() == b"1", "Not an emulator")
        need(adb("sdk", "shell", "getprop", "ro.build.version.sdk").strip() == b"24", "Wrong API")
        result["booted"] = True
        result["bootSeconds"] = round(time.monotonic() - started, 3)
        result["buildFingerprint"] = adb("image-fingerprint", "shell", "getprop", "ro.build.fingerprint").decode().strip()
        adb("app-install", "install", str(app), timeout=120)
        adb("test-install", "install", str(test), timeout=120)
        token = uuid.uuid4().hex
        raw = adb("rpc-controls", "shell", "am", "instrument", "-w", "-r", "-e", "token", token,
                  "-e", "scope", "supplemental-api24-rpc-controls",
                  PACKAGE + ".test/dev.p2pkit.sample.android.rpclab.RpcLabRuntimeInstrumentation", timeout=120).decode()
        result["instrumentation"] = assess_instrumentation(raw, token)
        result["controlsPassed"] = True
        # Observe the historical CLI mismatch directly without exporting its
        # free-form stderr. The fixed metadata replacement still has to pass
        # every original check and full source-bound shell command below.
        run("stat-dereference-observation", [sdk / "platform-tools/adb", "-P", str(port), "-s", serial,
            *stat_dereference_probe()], timeout=40, check=False)
        need(result["commands"][-1]["exitCode"] in (0, 69), "Unexplained Android stat dereference observation")
        # Reuse only the new AVD and its already tested app. Do not admit an
        # emulator through AndroidUsb's physical-device or wired-identity checks.
        # These exact shell-v2/create-only commands are an additional integration
        # check, not a replacement for any of the ten app/native controls.
        usb = module(root, "rpc_supplemental_mobile_shell", "rpc_mobile_usb.py")
        def shell(label, argv, data):
            need(server is not None and server.poll() is None, "Private adb exited")
            raw = run(label, [sdk / "platform-tools/adb", "-P", str(port), "-s", serial, *argv],
                      timeout=40, stdin=data, check=False)
            result["commands"][-1]["shellFailureStage"] = usb.android_shell_failure_stage(
                (work / f"{counter:03d}-{label}.stderr").read_bytes())
            return result["commands"][-1]["exitCode"], raw
        result["shellControlChecks"] = control_shell_checks(shell, usb, "shell-" + uuid.uuid4().hex)
        result["shellControlSha256"] = digest(root / "scripts/rpc_mobile_usb.py")
        adb("test-uninstall", "uninstall", PACKAGE + ".test")
        adb("app-uninstall", "uninstall", PACKAGE)
        result["status"] = "PASS"
    except Exception as error:
        result["errors"].append(type(error).__name__ + ": " + str(error))
        last = result["commands"][-1] if result["commands"] else {}
        if last.get("exitCode") not in (None, 0) and last.get("shellFailureStage") is not None:
            result["errors"].append("Android shell stage: " + last["shellFailureStage"])
        if server is not None and server.poll() is None and emulator is not None and emulator.poll() is None:
            try:
                adb("owned-guest-failure-log", "logcat", "-d", "-t", "300", timeout=20, check=False)
            except Exception as diagnostic:
                result["errors"].append("Diagnostic failure: " + type(diagnostic).__name__)
    finally:
        if emulator is not None and emulator.poll() is None:
            try:
                name = adb("cleanup-avd-name", "emu", "avd", "name", timeout=10, check=False).decode().splitlines()
                need(name and name[0] == avd, "AVD ownership unavailable; native executor must drain")
                adb("owned-emulator-stop", "emu", "kill", timeout=20)
                emulator.wait(timeout=30)
            except Exception as error:
                result["errors"].append("Emulator cleanup: " + type(error).__name__)
        if server is not None and server.poll() is None:
            try:
                run("private-adb-stop", [sdk / "platform-tools/adb", "-P", str(port), "kill-server"], 20)
                server.wait(timeout=15)
            except Exception as error:
                result["errors"].append("Private adb cleanup: " + type(error).__name__)
        for log in logs:
            log.close()
        result["naturalCleanup"] = ((server is None or server.poll() is not None) and
                                    (emulator is None or emulator.poll() is not None))
        if result["errors"] or not result["naturalCleanup"]:
            result["status"] = "FAIL"
        result["endedUtc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with (work / "result.json").open("x") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print(json.dumps({key: result[key] for key in ("status", "booted", "controlsPassed", "naturalCleanup")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
