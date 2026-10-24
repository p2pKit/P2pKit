#!/usr/bin/env python3
"""Controlled first-show keyboard experiment; never a qualification/failure override.

The explicit OFF/ON condition changes Simulator's Connect Hardware Keyboard preference in
an otherwise idle disposable hosted job, before creating/booting a fresh owned
device. CFPreferences readback is a preference observation, not proof that a
hardware keyboard was attached. The original two UI methods decide their own
result. App-side UIKit telemetry distinguishes focus and keyboard presentation.
"""
from __future__ import annotations

import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import sys
import tempfile
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audit_processes
import ci_evidence

RUNTIME = "com.apple.CoreSimulator.SimRuntime.iOS-26-5"
DEVICE_TYPE = "com.apple.CoreSimulator.SimDeviceType.iPhone-17"
SUBSYSTEM = "dev.p2pkit.sample.keyboard-cause-probe"
MODE_ENV = "P2PKIT_KEYBOARD_CAUSE_MODE"
BUILD_ENV = "P2PKIT_KEYBOARD_CAUSE_BUILD"
ISOLATED_ENV = "P2PKIT_KEYBOARD_CAUSE_ISOLATED_HOST"
MAX_EVENTS_BYTES = 512 * 1024
# Cold CoreSimulator setup only, not any XCTest keyboard/input deadline.
# Runner.run still clamps this ceiling to the original outer work end.
COLD_BOOT_SECONDS = 600
FINALIZATION_SECONDS = 120
UUID = re.compile(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}")


class ProbeError(RuntimeError):
    """Closed diagnostic code; never include arbitrary command output."""


def require(condition, code):
    if not condition:
        raise ProbeError(code)


def encode(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def admit(environment, mode):
    require(mode in ("hardware-off", "hardware-on"), "UNSUPPORTED_CONDITION")
    require(environment.get(ISOLATED_ENV) == "1", "ISOLATED_HOST_NOT_EXPLICIT")
    require(ci_evidence._hosted_darwin_context(environment), "HOSTED_DARWIN_CONTEXT_REQUIRED")
    require(environment.get("SIM_RUNTIME", RUNTIME) == RUNTIME, "REVIEWED_RUNTIME_REQUIRED")
    require(not any(environment.get(k) for k in (BUILD_ENV, "SIM_UDID", "IOS_RUN_DIR")),
            "BORROWED_OR_NESTED_FIXTURE_REFUSED")
    deadline = environment.get("P2PKIT_CI_COMMAND_DEADLINE_NS", "")
    require(re.fullmatch(r"[0-9]{1,20}", deadline) is not None, "OUTER_DEADLINE_REQUIRED")
    require(int(deadline) / 1e9 > time.monotonic() + 120, "OUTER_DEADLINE_EXHAUSTED")


class CoreFoundationPreference:
    """One exact current-user/any-host key; no whole preference-file writes."""
    def __init__(self):
        self.cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        pointer = ctypes.c_void_p
        signatures = {
            "CFStringCreateWithCString": ([pointer, ctypes.c_char_p, ctypes.c_uint32], pointer),
            "CFPreferencesCopyValue": ([pointer] * 4, pointer),
            "CFPreferencesCopyAppValue": ([pointer] * 2, pointer),
            "CFPreferencesSetValue": ([pointer] * 5, None),
            "CFPreferencesSynchronize": ([pointer] * 3, ctypes.c_ubyte),
            "CFGetTypeID": ([pointer], ctypes.c_ulong),
            "CFBooleanGetTypeID": ([], ctypes.c_ulong),
            "CFBooleanGetValue": ([pointer], ctypes.c_ubyte),
            "CFRelease": ([pointer], None),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.cf, name)
            function.argtypes, function.restype = arguments, result
        self.key = self.cf.CFStringCreateWithCString(None, b"ConnectHardwareKeyboard", 0x08000100)
        self.domain = self.cf.CFStringCreateWithCString(None, b"com.apple.iphonesimulator", 0x08000100)
        require(self.key and self.domain, "PREFERENCE_KEY_ALLOCATION")
        self.user = pointer.in_dll(self.cf, "kCFPreferencesCurrentUser").value
        self.host = pointer.in_dll(self.cf, "kCFPreferencesAnyHost").value
        self.booleans = {True: pointer.in_dll(self.cf, "kCFBooleanTrue").value,
                         False: pointer.in_dll(self.cf, "kCFBooleanFalse").value}

    def _boolean(self, value):
        if not value:
            return None
        try:
            require(self.cf.CFGetTypeID(value) == self.cf.CFBooleanGetTypeID(),
                    "UNSUPPORTED_ORIGINAL_PREFERENCE_TYPE")
            return bool(self.cf.CFBooleanGetValue(value))
        finally:
            self.cf.CFRelease(value)

    def explicit(self):
        self.synchronize()
        return self._boolean(self.cf.CFPreferencesCopyValue(self.key, self.domain, self.user, self.host))

    def effective(self):
        self.synchronize()
        return self._boolean(self.cf.CFPreferencesCopyAppValue(self.key, self.domain))

    def synchronize(self):
        require(self.cf.CFPreferencesSynchronize(self.domain, self.user, self.host), "PREFERENCE_SYNCHRONIZE")

    def write(self, value):
        require(value is None or type(value) is bool, "INVALID_PREFERENCE_WRITE")
        self.cf.CFPreferencesSetValue(self.key, None if value is None else self.booleans[value],
                                     self.domain, self.user, self.host)
        self.synchronize()

    def close(self):
        for value in (self.key, self.domain):
            self.cf.CFRelease(value)


class PreferenceTransaction:
    def __init__(self, backend, requested):
        require(type(requested) is bool, "INVALID_PREFERENCE_CONDITION")
        self.backend, self.requested = backend, requested
        self.original = backend.explicit()
        self.original_effective = backend.effective()
        require(all(value is None or type(value) is bool for value in (self.original, self.original_effective)),
                "UNSUPPORTED_ORIGINAL_PREFERENCE_TYPE")
        self.attempted = False
        self.readback = None
        self.restored = False
        self.observations = []

    def apply(self):
        self.attempted = True  # A failed synchronization still requires restoration.
        self.backend.write(self.requested)
        self.observe("APPLIED_BEFORE_DEVICE_CREATION")

    def observe(self, phase):
        self.readback = self.backend.effective()
        explicit = self.backend.explicit()
        self.observations.append(dict(phase=phase, explicitValue=explicit, effectiveValue=self.readback))
        require(explicit is self.requested and self.readback is self.requested,
                "PREFERENCE_READBACK_MISMATCH")

    def restore(self):
        if not self.attempted:
            return
        # Do not overwrite an unrelated intervening preference change.
        current = self.backend.explicit()
        require(current is self.requested or current is self.original, "PREFERENCE_CHANGED_DURING_PROBE")
        if current is not self.original:
            self.backend.write(self.original)
        self.restored = (self.backend.explicit() is self.original and
                         self.backend.effective() is self.original_effective)
        require(self.restored, "PREFERENCE_RESTORE_MISMATCH")

    def summary(self):
        return dict(scope="CURRENT_USER_ANY_HOST_SINGLE_KEY", domain="com.apple.iphonesimulator",
                    key="ConnectHardwareKeyboard", originalExplicitValue=self.original,
                    originalEffectiveValue=self.original_effective, requestedValue=self.requested,
                    effectivePreferenceReadback=self.readback, restorationVerified=self.restored,
                    observations=self.observations,
                    hardwareConnectionIndependentlyAttested=False)


class Runner:
    """Reuse the existing inner native owner, captures, and original outer end."""
    def __init__(self, root, environment, cancelled):
        self.root, self.cancelled = root, cancelled
        self.environment = dict(environment)
        self.end = int(environment["P2PKIT_CI_COMMAND_DEADLINE_NS"]) / 1e9
        token = uuid.uuid4().hex
        self.environment = audit_processes.local_ownership_environment(self.environment, token)
        self.scope = ci_evidence.local_command_scope(environment.get(audit_processes.JOB_ENV, token),
            token, str(root), environment.get("GRADLE_USER_HOME", str(root / "gradle-home")), environment)
        self.commands = []
        self.captures = []
        self.cleanup_known = False
        self.finalization_end = None

    def begin_finalization(self):
        # One shared cleanup allowance, never a new window for each operation.
        require(self.finalization_end is None, "FINALIZATION_ALREADY_STARTED")
        self.finalization_end = min(self.end, time.monotonic() + FINALIZATION_SECONDS)

    def deadline(self):
        return self.finalization_end if self.finalization_end is not None else self.end - FINALIZATION_SECONDS

    def check(self, end, streams=()):
        require(self.finalization_end is not None or not self.cancelled(), "CANCELLED")
        require(time.monotonic() < end, "COMMAND_DEADLINE")
        checked = streams if self.finalization_end is not None else self.captures
        require(not any(stream.error for stream in checked), "CAPTURE_FAILED")

    def _capture(self, name, argv, limit, environment=None):
        child = self.scope.spawn(list(argv), str(ROOT), environment or self.environment)
        streams = []
        for suffix, pipe in (("stdout", child.stdout), ("stderr", child.stderr)):
            stream = ci_evidence.Capture(pipe, self.root / (name + "." + suffix), limit)
            streams.append(stream)
            self.captures.append(stream)
            stream.thread.start()
        return child, streams

    def run(self, name, argv, seconds=120, *, limit=1024 * 1024, forward=False, environment=None):
        begin = time.monotonic()
        end = min(begin + seconds, self.deadline())
        require(end > begin, "OUTER_DEADLINE_EXHAUSTED")
        row = dict(name=name, exitCode=None, capturesClosed=False, completedWithinDeadline=False, forward=forward)
        self.commands.append(row)
        next_discovery = begin
        try:
            self.check(end)
            child, streams = self._capture(name, argv, limit, environment)
            while True:
                self.check(end, streams)  # Native gate/spawn time belongs to this same end.
                row["exitCode"] = child.poll()
                self.check(end, streams)  # A fast or late exit cannot bypass the end.
                if row["exitCode"] is not None:
                    break
                if time.monotonic() >= next_discovery:
                    self.scope.discover()
                    next_discovery = time.monotonic() + 1
                    self.check(end, streams)
                time.sleep(min(.05, max(0, end - time.monotonic())))
            capture_end = min(end, time.monotonic() + 5)
            for stream in streams:
                while stream.thread.is_alive() and time.monotonic() < capture_end:
                    stream.thread.join(timeout=max(0, min(.05, capture_end - time.monotonic())))
                    self.check(end, streams)
            row["capturesClosed"] = all(not stream.thread.is_alive() and stream.eof and stream.closed and
                                         not stream.error for stream in streams)
            require(row["capturesClosed"], "CAPTURE_NOT_CLOSED")
            raw = [stream.path.read_bytes() for stream in streams]
            self.check(end, streams)
            row["completedWithinDeadline"] = True
            return row["exitCode"], raw[0], raw[1]
        finally:
            row["elapsedSeconds"] = round(time.monotonic() - begin, 6)

    def checked(self, name, argv, seconds=120, **kwargs):
        code, out, _ = self.run(name, argv, seconds, **kwargs)
        require(code == 0, "TOOL_FAILED_" + name.upper().replace("-", "_"))
        return out

    def start_simulator(self, executable, device):
        self.check(self.deadline())
        child, _ = self._capture("simulator-application",
                                 [str(executable), "-CurrentDeviceUDID", device], 1024 * 1024)
        code = child.poll()
        self.commands.append(dict(name="simulator-application", pid=child.pid, background=True, exitCodeAtStart=code))
        self.check(self.deadline())
        require(code is None, "SIMULATOR_APPLICATION_EXITED")

    def drain(self):
        end = min(self.deadline(), time.monotonic() + 30)
        self.cleanup_known = False
        live = self.scope.drain(grace=10, kill_wait=10, deadline=end)
        self.cleanup_known = not live and not self.scope.discovery_errors
        require(self.cleanup_known, "NATIVE_RETIREMENT_UNKNOWN")

    def close(self):
        errors = []
        # spawn can register a leader then raise. Keep its original streams even
        # when no Capture was returned; scope.close clears the leader registry.
        pipes = [pipe for child in self.scope.leaders for pipe in (child.stdout, child.stderr) if pipe is not None]
        try:
            self.drain()
        except BaseException as error:
            record_error(errors, error)
        finally:
            try:
                self.scope.close()
            except BaseException as error:
                self.cleanup_known = False
                record_error(errors, error)
            for stream in self.captures:
                if stream.thread.ident is not None:
                    stream.thread.join(timeout=max(0, self.deadline() - time.monotonic()))
            captured = {id(stream.pipe) for stream in self.captures if stream.thread.ident is not None}
            for pipe in pipes:
                if id(pipe) not in captured:
                    try:
                        pipe.close()
                    except BaseException as error:
                        self.cleanup_known = False
                        record_error(errors, error)
            if not all(not s.thread.is_alive() and s.eof and s.closed and not s.error for s in self.captures):
                errors.append("FINAL_CAPTURE_NOT_CLOSED")
        return errors

    def retain_captures(self, destination):
        destination.mkdir(mode=0o700)
        rows = []
        forwarded = {row["name"] for row in self.commands if row.get("forward")}
        for stream in self.captures:
            row = dict(name=stream.path.name, eof=stream.eof, closed=stream.closed, error=stream.error, retained=False)
            rows.append(row)
            # A closed partial sink is evidence of a capture failure, not EOF.
            # Never read from an active writer or pretend it is a complete log.
            if stream.thread.is_alive() or not stream.closed or not stream.path.is_file():
                continue
            raw = stream.path.read_bytes()
            require(len(raw) <= stream.limit, "CAPTURE_BOUND_CHANGED")
            ci_evidence.write_private(destination / stream.path.name, raw)
            row.update(retained=True, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            if stream.path.stem in forwarded:
                output = sys.stdout.buffer if stream.path.suffix == ".stdout" else sys.stderr.buffer
                output.write(raw)
                output.flush()
        return rows


def devices(raw):
    value = json.loads(raw)
    require(type(value) is dict and type(value.get("devices")) is dict, "INVALID_DEVICE_INVENTORY")
    rows = []
    for runtime, group in value["devices"].items():
        require(type(runtime) is str and type(group) is list, "INVALID_DEVICE_INVENTORY")
        for item in group:
            require(type(item) is dict and type(item.get("udid")) is str and UUID.fullmatch(item["udid"]),
                    "INVALID_DEVICE_INVENTORY")
            rows.append({**item, "runtime": runtime})
    require(len({row["udid"].upper() for row in rows}) == len(rows), "DUPLICATE_DEVICE_ID")
    return rows


def created_device(candidate, name, before, after):
    require(UUID.fullmatch(candidate) is not None, "INVALID_CREATED_DEVICE_ID")
    require(candidate.upper() not in {row["udid"].upper() for row in before}, "CREATED_DEVICE_WAS_PREEXISTING")
    matching = [row for row in after if row["udid"].upper() == candidate.upper()]
    require(len(matching) == 1 and matching[0].get("name") == name and
            matching[0].get("runtime") == RUNTIME and matching[0].get("deviceTypeIdentifier") == DEVICE_TYPE and
            matching[0].get("isAvailable") is True and matching[0].get("state") == "Shutdown",
            "CREATED_DEVICE_BINDING_MISMATCH")
    return candidate  # Only this positive fresh-fixture binding grants cleanup authority.


def retain_xcresult(private, report_dir):
    bundle = private / "ios-run/DerivedData/Logs/Test/swift-keyboard-readiness.xcresult"
    require(bundle.is_dir() and not bundle.is_symlink(), "ORIGINAL_XCRESULT_UNAVAILABLE")
    count = total = 0
    def walk_error(error):
        raise error
    for parent, dirs, files in os.walk(bundle, followlinks=False, onerror=walk_error):
        for name in (*dirs, *files):
            info = (Path(parent) / name).lstat()
            require(stat.S_ISDIR(info.st_mode) or (stat.S_ISREG(info.st_mode) and info.st_nlink == 1),
                    "UNSUPPORTED_XCRESULT_ENTRY")
            count += 1
            total += info.st_size if stat.S_ISREG(info.st_mode) else 0
            require(count <= 4096 and total <= 128 * 1024 * 1024, "XCRESULT_BOUND_EXCEEDED")
    require(total > 0, "ORIGINAL_XCRESULT_EMPTY")
    # Existing strict private report collector; select only the original result,
    # never all DerivedData, build products, or the SwiftPM scratch directory.
    ci_evidence.collect_reports(private, [bundle.relative_to(private).as_posix() + "/**/*"],
                                report_dir / "original-xcresult")
    return dict(entries=count, bytes=total, retained=True)


def record_error(errors, error):
    code = str(error) if type(error) is ProbeError else type(error).__name__
    errors.append(code)


def run_probe(mode, environment, *, cancelled=lambda: False):
    admit(environment, mode)
    report_dir = ROOT / "build/reports/keyboard-cause-probe"
    report_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    # Never place DerivedData or SwiftPM scratch beneath the report glob.
    private = Path(tempfile.mkdtemp(prefix="keyboard-cause-execution-", dir=ROOT / "build"))
    runner = preference = backend = None
    device = name = None
    ui_code = None
    errors = []
    removed = shutdown = False
    events_info = xcresult_info = None
    captures_info = []
    lock_fd = None
    list_devices = ["/usr/bin/xcrun", "simctl", "list", "--json", "devices"]
    try:
        # Never unlink this shared lock inode; contenders must lock the same file.
        lock = Path(tempfile.gettempdir()) / ("p2pkit-keyboard-cause-" + str(os.getuid()) + ".guard")
        lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        info = os.fstat(lock_fd)
        require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.getuid() and
                stat.S_IMODE(info.st_mode) == 0o600, "INVALID_GLOBAL_PROBE_GUARD")
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        runner = Runner(private, environment, cancelled)
        inventory = devices(runner.checked("initial-devices", list_devices))
        require(all(row.get("state") == "Shutdown" for row in inventory), "OTHER_SIMULATOR_NOT_SHUTDOWN")
        code, _, _ = runner.run("ambient-simulator-refusal", ["/usr/bin/pgrep", "-x", "Simulator"], 30)
        require(code == 1, "AMBIENT_SIMULATOR_APPLICATION")
        selected = json.loads(runner.checked("runtime-inventory", ["/usr/bin/xcrun", "simctl", "list", "--json", "runtimes"]))
        require(sum(row.get("identifier") == RUNTIME and row.get("isAvailable") is True
                    for row in selected.get("runtimes", [])) == 1, "REVIEWED_RUNTIME_UNAVAILABLE")
        runner.checked("record-controls", ["/usr/bin/xcrun", "swift", "test", "--package-path",
            str(ROOT / "samples/iosApp/KeyboardCauseProbeControls"), "--scratch-path", str(private / "swift-controls")],
            180, forward=True)
        backend = CoreFoundationPreference()
        preference = PreferenceTransaction(backend, mode == "hardware-on")
        preference.apply()
        name = "p2pkit-keyboard-cause-" + uuid.uuid4().hex
        raw = runner.checked("create-device", ["/usr/bin/xcrun", "simctl", "create", name, DEVICE_TYPE, RUNTIME])
        candidate = raw.decode("ascii").strip()
        require(UUID.fullmatch(candidate) is not None, "INVALID_CREATED_DEVICE_ID")
        require(candidate.upper() not in {row["udid"].upper() for row in inventory}, "CREATED_DEVICE_WAS_PREEXISTING")
        created = devices(runner.checked("created-device-readback", list_devices))
        device = created_device(candidate, name, inventory, created)
        runner.checked("boot-owned-device", ["/usr/bin/xcrun", "simctl", "bootstatus", device, "-b"], COLD_BOOT_SECONDS)
        developer = Path(runner.checked("developer-directory", ["/usr/bin/xcode-select", "-p"], 30).decode().strip())
        simulator = developer / "Applications/Simulator.app/Contents/MacOS/Simulator"
        require(developer.is_absolute() and simulator.is_file(), "SIMULATOR_EXECUTABLE_UNAVAILABLE")
        runner.start_simulator(simulator, device)
        preference.observe("SIMULATOR_STARTED_BEFORE_UI")
        child_env = dict(runner.environment)
        child_env.pop(MODE_ENV, None)
        child_env.update({BUILD_ENV: "1", "SIM_NAME": name, "SIM_UDID": device, "SIM_RUNTIME": RUNTIME,
                          "IOS_RUN_DIR": str(private / "ios-run")})
        ui_code, _, _ = runner.run("original-ui-tests",
            [environment.get("P2PKIT_BASH", "/bin/bash"), "scripts/run-ios-ui-tests.sh", "run-keyboard-readiness"],
            2700, limit=16 * 1024 * 1024, forward=True, environment=child_env)
    except BaseException as error:
        record_error(errors, error)
    finally:
        if runner:
            runner.begin_finalization()
            ui_row = next((row for row in runner.commands if row["name"] == "original-ui-tests"), None)
            # A post-exit capture/telemetry failure must not erase the observed
            # original UI exit code, but still makes this experiment fail125.
            if ui_code is None and ui_row:
                ui_code = ui_row.get("exitCode")
            if errors:
                try:
                    runner.drain()
                except BaseException as error:
                    record_error(errors, error)
            if device:
                if ui_row:
                    try:
                        preference.observe("AFTER_ORIGINAL_UI")
                    except BaseException as error:
                        record_error(errors, error)
                    try:
                        raw = runner.checked("keyboard-events", ["/usr/bin/xcrun", "simctl", "spawn", device,
                            "log", "show", "--style", "ndjson", "--info", "--last", "1h", "--predicate",
                            'subsystem == "' + SUBSYSTEM + '"'], 30, limit=MAX_EVENTS_BYTES)
                        ci_evidence.write_private(report_dir / "events.ndjson", raw)
                        events_info = dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                        require(b"KEYBOARD_CAUSE_EVENT" in raw and b"event=armed" in raw,
                                "APP_TELEMETRY_NOT_OBSERVED")
                    except BaseException as error:
                        record_error(errors, error)
                # Retire our Simulator application before it can react to the
                # device deletion. No delegated platform service is name-killed.
                try:
                    runner.drain()
                except BaseException as error:
                    record_error(errors, error)
                try:
                    current = devices(runner.checked("owned-finalization-state", list_devices, 30))
                    matching = [row for row in current if row["udid"].upper() == device.upper()]
                    require(len(matching) == 1 and matching[0].get("name") == name and
                            matching[0].get("runtime") == RUNTIME and matching[0].get("deviceTypeIdentifier") == DEVICE_TYPE,
                            "OWNED_DEVICE_BINDING_CHANGED")
                    if matching[0].get("state") != "Shutdown":
                        code, _, _ = runner.run("shutdown-owned-device", ["/usr/bin/xcrun", "simctl", "shutdown", device], 45)
                        if code != 0:
                            errors.append("TOOL_FAILED_SHUTDOWN_OWNED_DEVICE")
                        current = devices(runner.checked("shutdown-readback", list_devices, 30))
                    shutdown = any(row["udid"].upper() == device.upper() and row.get("state") == "Shutdown" for row in current)
                    require(shutdown, "OWNED_SHUTDOWN_NOT_OBSERVED")
                    code, _, _ = runner.run("delete-owned-device", ["/usr/bin/xcrun", "simctl", "delete", device], 30)
                    if code != 0:
                        errors.append("TOOL_FAILED_DELETE_OWNED_DEVICE")
                    current = devices(runner.checked("deletion-readback", list_devices, 30))
                    removed = all(row["udid"].upper() != device.upper() for row in current)
                    require(removed, "OWNED_DELETION_NOT_OBSERVED")
                except BaseException as error:
                    record_error(errors, error)
            try:
                errors.extend(runner.close())
            except BaseException as error:
                record_error(errors, error)
        if preference:
            try:
                preference.restore()
            except BaseException as error:
                record_error(errors, error)
        if backend:
            try:
                backend.close()
            except BaseException as error:
                record_error(errors, error)
        if lock_fd is not None:
            try:
                os.close(lock_fd)
            except BaseException as error:
                record_error(errors, error)
    if runner:
        try:
            captures_info = runner.retain_captures(report_dir / "captures")
        except BaseException as error:
            record_error(errors, error)
        if ui_row and runner.cleanup_known:
            try:
                xcresult_info = retain_xcresult(private, report_dir)
            except BaseException as error:
                record_error(errors, error)
        if time.monotonic() >= runner.end:
            errors.append("OUTER_DEADLINE_EXHAUSTED")
    summary = dict(schema=1, scope="CONTROLLED_KEYBOARD_FIRST_SHOW_EXPERIMENT_NOT_QUALIFICATION",
        condition=mode, runtime=RUNTIME, deviceType=DEVICE_TYPE, ownedDevice=device,
        originalUiExitCode=ui_code, preference=preference.summary() if preference else None,
        nativeRetirementKnown=runner.cleanup_known if runner else False,
        ownedShutdownObserved=shutdown, ownedDeletionObserved=removed,
        events=events_info, originalXcresult=xcresult_info, captures=captures_info,
        commands=runner.commands if runner else [], errors=errors,
        underlyingHistoricalCauseEstablished=False)
    ci_evidence.write_private(report_dir / "summary.json", encode(summary))
    print("KEYBOARD_CAUSE_PROBE_SUMMARY_JSON:" + json.dumps(summary, sort_keys=True, separators=(",", ":")), flush=True)
    # An intentionally failing ON condition remains an original failure artifact.
    # Neither telemetry nor successful cleanup substitutes for the original result.
    return ui_code if ui_code is not None and not errors else 125


def main():
    os.umask(0o077)
    require(len(sys.argv) == 2, "ONE_CLOSED_CONDITION_REQUIRED")
    cancelled = [False]
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: cancelled.__setitem__(0, True))
    return run_probe(sys.argv[1], os.environ, cancelled=lambda: cancelled[0])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ProbeError as error:
        print("Keyboard cause probe refused: " + str(error), file=sys.stderr)
        raise SystemExit(125)
