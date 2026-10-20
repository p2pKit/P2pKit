#!/usr/bin/env python3
"""API37 actual deny/grant/pinned-duplex/revoke witness; independent profile review remains required."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import selectors
import socket
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("android_ui_owner", ROOT / "scripts/run-android-ui-validation.py")
owner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(owner)
need = owner.need
PACKAGE = owner.PACKAGE
RUNNER = PACKAGE + ".runtime.LanPermissionRuntimeInstrumentation"
PERMISSION = "android.permission.ACCESS_LOCAL_NETWORK"
PEER_REPLY_PREFIX = "send jvm-"


def live_lines(raw):
    # CLI state lines contain UTF-8 arrows. Neither decoding a partial codepoint
    # nor counting an unterminated receive line is valid stream admission.
    complete = raw[:raw.rfind(b"\n") + 1]
    return [line.lstrip("> ").strip() for line in complete.decode("utf-8", errors="strict").splitlines()]


def final_peer_lines(raw):
    need(raw.endswith(b"\n") or raw.endswith(b"\n> "), "Unterminated final peer output")
    raw.decode("utf-8", errors="strict")  # EOF is strict; only the literal prompt tail is exempt.
    return live_lines(raw)


def parse_output(raw):
    result, pending, frames, codes = {}, {}, [], []
    for line in raw.decode("utf-8", errors="strict").splitlines():
        if line.startswith(("INSTRUMENTATION_STATUS: ", "INSTRUMENTATION_RESULT: ")):
            prefix, field = line.split(": ", 1)
            key, separator, value = field.partition("=")
            target = pending if prefix == "INSTRUMENTATION_STATUS" else result
            need(separator and key and key not in target, "Invalid or duplicate permission instrumentation field")
            target[key] = value
        elif line.startswith("INSTRUMENTATION_STATUS_CODE: "):
            frames.append((line.split(": ", 1)[1], pending))
            pending = {}
        elif line.startswith("INSTRUMENTATION_CODE: "):
            codes.append(line.split(": ", 1)[1])
    return result, frames, codes, pending


def terminal(raw, token, mode):
    need(raw.endswith(b"\n"), "Truncated permission terminal")
    result, frames, codes, pending = parse_output(raw)
    test = "deniedReentryAfterPermissionDrivenExit" if mode == "revoked-reentry" else (
        "permissionRecreationPinnedTcpAndRevocation")
    need(codes == ["-1"] and not pending and frames and frames[-1][0] == "0", "No completed permission terminal")
    need(frames[-1][1].get("class") == RUNNER and frames[-1][1].get("test") == test and
         all(frame.get("p2pkitToken") == token for _, frame in frames), "Wrong permission test identity")
    expected = {"p2pkitToken": token, "p2pkitCompleted": "1", "p2pkitOutcome": "PASS", "p2pkitCleanup": "PASS",
                "p2pkitManager": "PASS", "p2pkitRawPregrant": "DENIED"}
    if mode == "revoked-reentry":
        expected.update(p2pkitReentry="DENIED_AFTER_ATTRIBUTABLE_PERMISSION_KILL",
                        p2pkitSameInstanceRevocation="OS_PERMISSION_KILL_NOT_SAME_INSTANCE")
    else:
        expected.update(p2pkitReentry="DENIED_SAME_MANAGER_AND_PROCESS", p2pkitSameInstanceRevocation="PASS",
                        p2pkitRawRoute="DENIED_THEN_ADMITTED", p2pkitTraffic="PASS", p2pkitRecreation="PASS",
                        p2pkitRequestSettled="true", p2pkitSentBytes="40", p2pkitReceivedBytes="36")
    need(all(result.get(key) == value and frames[-1][1].get(key) == value for key, value in expected.items()),
         "Wrong permission terminal scope")
    need(not any("Failure" in key for key in result), "Permission test retained a failure")
    return result


def ready_checkpoint(raw, token):
    # os.read is byte-stream delivery, not line framing. A partial field/UTF-8
    # suffix is neither malformed evidence nor an authoritative handoff yet.
    complete = raw[:raw.rfind(b"\n") + 1]
    _, frames, _, _ = parse_output(complete)
    ready = [value for code, value in frames if code == "2" and
             value.get("p2pkitPhase") == "awaiting-host-os-revocation"]
    if not ready:
        return None
    need(len(ready) == 1, "Duplicate live revocation handoff")
    record = ready[0]
    expected = {"p2pkitToken": token, "class": RUNNER, "test": "permissionRecreationPinnedTcpAndRevocation",
                "p2pkitTraffic": "PASS", "p2pkitRawRoute": "DENIED_THEN_ADMITTED", "p2pkitManager": "PASS",
                "p2pkitRecreation": "PASS", "p2pkitRequestSettled": "true", "p2pkitSentBytes": "40",
                "p2pkitReceivedBytes": "36", "p2pkitSameInstanceRevocation": "NOT_EXECUTED"}
    need(all(record.get(key) == value for key, value in expected.items()), "Unqualified revocation handoff")
    return record


def record_binding(record, token, source, tree):
    need(record.get("token") == token and record.get("sourceCommit") == source and
         record.get("sourceTree") == tree and record.get("sdk") == 37 and record.get("targetSdk") == 37,
         "Wrong retained API37 source/runtime binding")


def completed_instrumentation_output(raw):
    """Classify only a complete drained stream, not runner entry or root cause."""
    return ("INSTRUMENTATION_OUTPUT_PRESENT" if any(line.startswith("INSTRUMENTATION_")
            for line in raw.decode("utf-8", errors="strict").splitlines()) else "NO_INSTRUMENTATION_OUTPUT")


RETAINED_RECORDS = ("profile-revocation.json", "before-revocation.json", "profile-revoked-reentry.json",
                    "revoked-reentry.json")


def store_retained_record(raw, evidence, name):
    # exec-out does not guarantee the remote cat exit status. A missing-file
    # message stays in the private command capture, never a purported JSON record.
    need(name in RETAINED_RECORDS and 0 < len(raw) <= 16_384, "API37 record identity/size")
    record = owner.decode_json(raw)
    need(isinstance(record, dict), "API37 record must be an object")
    (evidence / name).write_bytes(raw)
    return record


def attempt_failure_capture(capture):
    receipt = {"status": "ATTEMPTED"}
    try:
        capture()
    except BaseException as error:
        receipt["failureType"] = type(error).__name__
    return receipt


def reject_graphics_feature_error(raw):
    text = raw.decode("utf-8", errors="strict")
    need(not re.search(r"(?im)(?:unknown|invalid|unsupported|unrecognized)[^\r\n]*(?:feature|GLDirectMem)|"
                       r"(?:feature|GLDirectMem)[^\r\n]*(?:unknown|invalid|unsupported|unrecognized)", text),
         "Emulator rejected the requested graphics feature")


def graphics_options(help_output, defaults):
    """Supplier capability preflight, not proof of effective guest DMA support."""
    need(0 < len(help_output) <= 131_072 and 0 < len(defaults) <= 131_072, "Graphics preflight size")
    reject_graphics_feature_error(help_output)
    help_text = help_output.decode("utf-8", errors="strict").lower()
    need("feature" in help_text and any(word in help_text for word in ("enabl", "disabl", "overrid")),
         "Actual emulator feature-option help unavailable")
    values = {}
    for line in defaults.decode("utf-8", errors="strict").splitlines():
        key, separator, value = line.partition("=")
        key = key.strip()
        if key in ("GLDirectMem", "HasSharedSlotsHostMemoryAllocator"):
            need(separator and key not in values and value.strip() in ("on", "off"),
                 "Ambiguous supplier graphics feature declaration")
            values[key] = value.strip()
    # Supplier defaults identify recognized features, not their effective runtime
    # values. Never demand a particular default or override shared-slot behavior.
    need(set(values) == {"GLDirectMem", "HasSharedSlotsHostMemoryAllocator"},
         "Required supplier graphics feature declarations unavailable")
    return ("-feature", "GLDirectMem")


class Campaign:
    API = 37
    IMAGE = "system-images;android-37.0;google_apis;x86_64"
    LABEL = "android-permission"
    SCOPE = "API37 ordinary target UID, real P2pKit controlled guest10.0.2.2 traffic and OS revocation; not physical"
    BUILD_TASKS = (":p2p-sample-desktop:installDist",)
    REVIEW = "REQUIRED: actual loaded permission module, mandatory flag/cache/compat, route and original runtime evidence"
    NOT_QUALIFIED = ["physical phones/OEM behavior", "legacy target36 and Android16 opt-in", "unreviewed profile semantics"]

    @staticmethod
    def prepare_emulator(*, run, sdk, report):
        # API37-only: no user-provided feature selector or backend fallback. This
        # documented positive option requests the mapper's required DMA path;
        # it does not alter Android permission/module flags or the API35 UI lane.
        help_output = run([sdk / "emulator/emulator", "-help-feature"], timeout=15)[1]
        defaults_path = sdk / "emulator/lib/advancedFeatures.ini"
        need(defaults_path.is_file() and 0 < defaults_path.stat().st_size <= 131_072,
             "Actual supplier feature defaults unavailable")
        defaults = defaults_path.read_bytes()
        (report / "emulator-feature-help.txt").write_bytes(help_output)
        (report / "emulator-feature-defaults.ini").write_bytes(defaults)
        options = graphics_options(help_output, defaults)
        with (sdk / "emulator/emulator").open("rb") as binary:
            frontend_hash = hashlib.file_digest(binary, "sha256").hexdigest()
        owner.write_json(report / "emulator-graphics-request.json", {
            "options": list(options), "scope": "API37 graphics only; not permission or profile acceptance",
            "emulatorFrontendSha256": frontend_hash,
            "helpSha256": hashlib.sha256(help_output).hexdigest(),
            "supplierDefaultsSha256": hashlib.sha256(defaults).hexdigest(),
            "effectiveGuestDmaSupport": "NOT_ESTABLISHED_BY_PREFLIGHT",
        })
        return options

    @staticmethod
    def validate_emulator_boot(raw):
        # A warning that an option is unknown must fail even if launch exits zero
        # or the guest otherwise boots. No alternate option/backend is attempted.
        need(0 < len(raw) <= owner.LIMIT, "Bounded emulator startup log required")
        reject_graphics_feature_error(raw)

    @staticmethod
    def run(*, run, device, report, env, private, source, tree, apks, app_apk, test_apk, capture_failure):
        token = uuid.uuid4().hex
        evidence = report / "372"
        evidence.mkdir(mode=0o700)
        for package, apk, label in ((PACKAGE, app_apk, "app"), (PACKAGE + ".test", test_apk, "test")):
            # Owned fresh AVD: no reinstall, grant flags, data clear or permissions shell identity.
            run([*device, "install", "--no-streaming", apk], timeout=90)
            path = run([*device, "shell", "pm", "path", package])[1].decode().strip()
            need(re.fullmatch(r"package:/data/app/[^\r\n]+/base\.apk", path), "Ambiguous installed package")
            digest = run([*device, "shell", "sha256sum", path.removeprefix("package:")])[1].decode().split()[0]
            need(digest == apks[label]["sha256"], "Installed source APK differs from built bytes")

        def metadata(label):
            commands = {
                "package": ["dumpsys", "package", PACKAGE],
                "active-modules": ["dumpsys", "apexservice"],
                "compat": ["dumpsys", "platform_compat"],
                "aconfig": ["cmd", "aconfig", "list"],
                "permission-controller-packages": ["pm", "list", "packages", "-f", "permissioncontroller"],
            }
            status = {}
            for name, command in commands.items():
                code, raw = run([*device, "shell", *command], check=False)
                (evidence / f"{label}-{name}.txt").write_bytes(raw)
                status[name] = {"exitCode": code, "bytes": len(raw)}
            owner.write_json(evidence / f"{label}-metadata.json", status)
            # Source/runtime evidence is retained even if a public shell observer is
            # unavailable. Such a profile remains an explicit independent-review hold.
            need(status["package"]["exitCode"] == 0 and status["package"]["bytes"] > 0,
                 "Package grant/install readback unavailable")

        metadata("fresh")
        selector = selectors.DefaultSelector()
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        listener.setblocking(False)
        selector.register(listener, selectors.EVENT_READ, ("listener", None))
        control_port = listener.getsockname()[1]
        processes, buffers, streams, clients = {}, {}, {}, {}
        raw_accepts = raw_challenges = raw_empty = 0
        received = responded = revoked = False
        outcome, original_error = {}, None
        instrumentation_output, failure_capture = {}, None
        overall_end = time.monotonic() + 240

        def spawn(label, command):
            process = subprocess.Popen([str(arg) for arg in command], cwd=ROOT, env=env, stdin=subprocess.PIPE,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            processes[label] = process
            buffers[label] = bytearray()
            streams[label] = (evidence / f"{label}.log").open("xb", buffering=0)
            os.set_blocking(process.stdout.fileno(), False)
            selector.register(process.stdout, selectors.EVENT_READ, ("stream", label))
            return process

        def text(label):
            return bytes(buffers[label]).decode("utf-8", errors="strict")

        def lines(label):
            return live_lines(bytes(buffers[label]))

        def send(process, command):
            need(process.poll() is None, "Peer exited before command")
            process.stdin.write((command + "\n").encode())
            process.stdin.flush()

        def pump():
            nonlocal raw_accepts, raw_challenges, raw_empty
            need(time.monotonic() < overall_end, "API37 campaign deadline")
            for key, _ in selector.select(0.1):
                kind, label = key.data
                if kind == "listener":
                    client, _ = listener.accept()
                    client.setblocking(False)
                    raw_accepts += 1
                    need(raw_accepts <= 3, "Unexpected raw connections")
                    clients[client] = bytearray()
                    selector.register(client, selectors.EVENT_READ, ("client", None))
                elif kind == "client":
                    client = key.fileobj
                    part = client.recv(128)
                    clients[client].extend(part)
                    data = bytes(clients[client])
                    need(len(data) <= 33, "Raw probe input bound")
                    if not part or data.endswith(b"\n"):
                        selector.unregister(client)
                        if data:
                            need(data == (token + "\n").encode(), "Wrong source-run raw nonce")
                            client.settimeout(2)
                            client.sendall(("ack-" + token + "\n").encode())
                            raw_challenges += 1
                        else:
                            raw_empty += 1
                        client.close()
                        del clients[client]
                else:
                    part = os.read(key.fileobj.fileno(), 65536)
                    if not part:
                        selector.unregister(key.fileobj)
                    else:
                        buffers[label].extend(part)
                        need(len(buffers[label]) <= 8 * 1024 * 1024, "API37 process output bound")
                        streams[label].write(part)

        def until(predicate, seconds, message):
            end = time.monotonic() + seconds
            while not predicate():
                need(time.monotonic() < end, message)
                pump()

        def drained(label):
            return not any(key.data == ("stream", label) for key in selector.get_map().values())

        def retained(name, required=True):
            code, raw = run([*device, "exec-out", "run-as", PACKAGE, "cat", f"no_backup/lan-372-{token}/{name}"],
                            timeout=15, check=False)
            if code != 0:
                need(not required, "Required private API37 record missing")
                return None
            return store_retained_record(raw, evidence, name)

        try:
            code, graphics = run([*device, "shell", "dumpsys", "SurfaceFlinger"], timeout=10, check=False)
            need(len(graphics) <= 2 * 1024 * 1024, "SurfaceFlinger observation size")
            (evidence / "fresh-surfaceflinger.txt").write_bytes(graphics)
            owner.write_json(evidence / "fresh-graphics-observation.json", {
                "exitCode": code, "bytes": len(graphics),
                "scope": "Actual graphics service observation, not internal DMA or permission proof",
            })
            need(code == 0 and graphics, "Fresh graphics service unavailable")
            distribution = ROOT / "samples/p2p-sample-desktop/build/install/p2p-sample-desktop/lib"
            java = Path(env["JAVA_HOME"]) / "bin/java"
            peer = spawn("peer", [java, "-Xmx384m", "-XX:ActiveProcessorCount=2",
                "-Duser.home=" + str(private / "home"), "-Djava.io.tmpdir=" + str(private),
                "-cp", str(distribution / "*"), "dev.p2pkit.sample.desktop.MainKt", "API37 controlled peer",
                "p2pkit-art-" + token, "trace=off", "test=ART-372", "session=" + token, "role=both",
                "evidence=" + str(private / "peer-export"), "log=" + str(evidence / "peer-events.jsonl")])
            until(lambda: "Ready. Type 'help' for commands." in lines("peer"), 30, "P2pKit peer not ready")
            send(peer, "mesh off")
            send(peer, "info")
            until(lambda: "auto-mesh off" in lines("peer") and
                  any(re.fullmatch(r"manual port\s+[0-9]+", line) for line in lines("peer")) and
                  any(re.fullmatch(r"fingerprint\s+p2f1-[a-z2-7]{52}", line) for line in lines("peer")),
                  10, "Peer endpoint/fingerprint missing")
            pins = [line.split()[-1] for line in lines("peer") if re.fullmatch(r"fingerprint\s+p2f1-[a-z2-7]{52}", line)]
            ports = [int(line.split()[-1]) for line in lines("peer") if re.fullmatch(r"manual port\s+[0-9]+", line)]
            need(len(pins) == len(ports) == 1 and 1024 <= ports[0] <= 65535 and ports[0] != control_port,
                 "Ambiguous peer endpoint")
            arguments = {"token": token, "host": "10.0.2.2", "controlPort": str(control_port),
                         "cliPort": str(ports[0]), "fingerprint": pins[0], "sourceCommit": source, "sourceTree": tree}
            owner.write_json(evidence / "request.json", {**arguments, "topology": Campaign.SCOPE})

            def instrument(mode):
                command = [*device, "shell", "am", "instrument", "-w", "-r"]
                for key, value in {**arguments, "mode": mode}.items():
                    command += ["-e", key, value]
                return spawn(mode, command + [PACKAGE + ".test/" + RUNNER])

            original = instrument("revocation")
            while original.poll() is None:
                pump()
                received = any(re.fullmatch(r"incoming from anon-[0-9a-f]{16}: <text 40B>", line)
                               for line in lines("peer"))
                if received and not responded and "INSTRUMENTATION_STATUS: p2pkitPhase=message-sent" in lines("revocation"):
                    send(peer, PEER_REPLY_PREFIX + token)
                    responded = True
                handoff = ready_checkpoint(bytes(buffers["revocation"]), token)
                if handoff is not None and not revoked:
                    need(responded and raw_accepts == raw_challenges == 1 and raw_empty == 0,
                         "Missing enforced ordinary-route duplex before revocation")
                    before = retained("before-revocation.json")
                    record_binding(before, token, source, tree)
                    need(before.get("traffic") == "AUTHENTICATED_DUPLEX_COMPLETED" and
                         before.get("peerFingerprint") == pins[0], "Wrong pre-revocation witness")
                    # Actual OS permission operation, not grant adoption/shell network
                    # identity/force-stop. The OS may kill the target process here.
                    run([*device, "shell", "pm", "revoke", PACKAGE, PERMISSION], timeout=15)
                    revoked = True
            original.wait(timeout=5)
            until(lambda: drained("revocation"), 3, "Original instrumentation EOF missing")
            instrumentation_output["revocation"] = completed_instrumentation_output(bytes(buffers["revocation"]))
            need(instrumentation_output["revocation"] != "NO_INSTRUMENTATION_OUTPUT", "NO_INSTRUMENTATION_OUTPUT")
            need(revoked and responded, "No completed traffic-to-live-revocation handoff")
            profile = retained("profile-revocation.json")
            record_binding(profile, token, source, tree)
            need(profile.get("falseDefaultValue") is True and profile.get("trueDefaultValue") is True,
                 "Mandatory target37 flag readback not true")
            metadata("revoked")
            raw = bytes(buffers["revocation"])
            try:
                result = terminal(raw, token, "revocation")
                need(original.returncode == 0, "Successful survivor terminal but adb command failed")
                outcome["revocation"] = "SAME_MANAGER_AND_PROCESS_DENIED"
            except ValueError:
                # A missing terminal is NOT success. A new ordinary app process
                # must independently attribute the old PID to OS permission change.
                reentry = instrument("revoked-reentry")
                until(lambda: reentry.poll() is not None, 100, "Denied OS-kill reentry deadline")
                reentry.wait(timeout=5)
                until(lambda: drained("revoked-reentry"), 3, "Reentry instrumentation EOF missing")
                instrumentation_output["revoked-reentry"] = completed_instrumentation_output(bytes(buffers["revoked-reentry"]))
                need(instrumentation_output["revoked-reentry"] != "NO_INSTRUMENTATION_OUTPUT", "NO_INSTRUMENTATION_OUTPUT")
                need(reentry.returncode == 0, "Reentry adb command failed")
                result = terminal(bytes(buffers["revoked-reentry"]), token, "revoked-reentry")
                record = retained("revoked-reentry.json")
                record_binding(record, token, source, tree)
                need(record.get("reason") == "REASON_PERMISSION_CHANGE" and
                     record.get("defaultManagerDenied") is True and record.get("rawSocketDenied") is True and
                     record.get("sampleStartDenied") is True, "No attributable OS-kill denied-reentry proof")
                outcome["revocation"] = "OS_PERMISSION_KILL_AND_UNCHANGED_INSTALL_DENIED_REENTRY"
            outcome["terminal"] = result
            metadata("reentered")
        except BaseException as error:
            original_error = error
            # Source-owned original emulator/AVD binding, never an acceptance retry.
            failure_capture = attempt_failure_capture(capture_failure)
            raise
        finally:
            cleanup_errors, forced = [], []

            def clean(label, action):
                try:
                    action()
                except BaseException as error:
                    cleanup_errors.append({"step": label, "errorType": type(error).__name__})

            # Every retirement attempt runs even if retention or graceful quit fails.
            for name in RETAINED_RECORDS:
                clean("retain-" + name, lambda name=name: retained(name, required=False))
            peer = processes.get("peer")

            def retire_peer():
                if peer is not None and peer.poll() is None:
                    send(peer, "quit")
                    until(lambda: peer.poll() is not None, 15, "Peer cleanup deadline")
                    peer.wait(timeout=5)
                    until(lambda: drained("peer"), 3, "Peer EOF missing")

            clean("graceful-peer-retirement", retire_peer)
            for label, process in processes.items():
                def retire(process=process, label=label):
                    if process.poll() is None:
                        forced.append(label)
                        process.kill()  # Exact original leader; outer owner retires descendants.
                        process.wait(timeout=10)
                clean("leader-" + label, retire)
                for name in ("stdin", "stdout"):
                    stream = getattr(process, name)
                    if stream is not None:
                        clean(label + "-" + name, stream.close)
            for label, stream in streams.items():
                clean("capture-" + label, stream.close)
            for client in clients:
                clean("raw-client", client.close)
            clean("selector", selector.close)
            clean("raw-listener", listener.close)
            owner.write_json(evidence / "host-result.json", {"outcome": outcome, "rawAccepts": raw_accepts,
                "rawChallenges": raw_challenges, "rawEmptyConnections": raw_empty, "cleanupErrors": cleanup_errors,
                "forcedLeaders": forced, "review": Campaign.REVIEW,
                "instrumentationOutput": instrumentation_output, "failureCapture": failure_capture,
                "sameManagerClaimed": outcome.get("revocation") == "SAME_MANAGER_AND_PROCESS_DENIED"})
            if original_error is None:
                need(not cleanup_errors and not forced, "API37 campaign cleanup failed")
        # Admit the complete, drained peer transcript, not just an early send snapshot.
        spec = importlib.util.spec_from_file_location("android_art", ROOT / "scripts/run-android-art-smoke.py")
        art = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(art)
        alias = re.findall(r"incoming from (anon-[0-9a-f]{16}): <text 40B>", text("peer"))
        host = art.runtime_host_result(final_peer_lines(bytes(buffers["peer"])), alias[0] if len(alias) == 1 else None,
            {"controlAccepts": raw_accepts, "controlChallenges": raw_challenges, "controlEmptyConnections": raw_empty},
            True, len(clients))
        need(peer.returncode == 0 and host["status"] == "PASS", "Final P2pKit peer or raw-route control failed")
        return {"372": "HARNESS_PASS_PENDING_PROFILE_REVIEW"}


def main(argv=None):
    # No user-supplied API/host/route/permission/mode/timeout selectors.
    import argparse
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    return owner.main([], campaign=Campaign())


if __name__ == "__main__":
    raise SystemExit(main())
