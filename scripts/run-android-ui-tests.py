#!/usr/bin/env python3
"""One owned native Mac guest for the explicit #317/#324 UI components.

This is an execution/retention adapter, not a runtime or visual approval. Use
only inside the maintained immutable command executor, after the operator's
shared host/Actions lease, ordinary native SDK-tool admission and resource check.
The fixed1800s product budget requires the exact documented2100s outer launch;
start.json does NOT contain a timeout field. No caller-supplied device, command,
profile, source, token, trusted flag or timeout can select another execution.

Official emulator/image archive authority, APK authority, content verification,
Darwin ownership and final wrapper stop remain their existing separate controls.
#372 permission/compat/LAN acceptance and physical-device work are not performed.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import os
from pathlib import Path
import re
import selectors
import shlex
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import android_ui_controller as core
import android_archive_admission as archives

need, Rejected = core.need, core.Rejected
MIB, GIB = 1024 ** 2, 1024 ** 3
TOTAL_SECONDS, FINAL_SECONDS, OUTER_SECONDS = 1800, 420, 2100
BOOT_SECONDS, ART_SECONDS, THREAD_SECONDS = 180, 20, 3
FREE_DISK, FREE_INACTIVE_MEMORY = 5 * GIB, 4 * GIB
BACKGROUND_LIMIT, TOOL_BYTES, TOOL_ENTRIES = 8 * MIB, GIB, 2048
SELECTIONS = {"317": ("317",), "324": ("324",), "317+324": ("317", "324")}
DISPLAY = (1600, 2560, 200)
IMAGE_FINGERPRINT = "google/generic_system_google/generic:17/CP21.260330.012/15545953:user/dev-keys"


def problem(error):
    # Private reports may name generated paths, but never serialize arbitrary
    # guest bytes, environment values, screenshots or synthetic credentials here.
    return type(error).__name__ + (": " + str(error) if isinstance(error, Rejected) else "")


def directory(runner, path):
    runner.reject_symlinks(path)
    path.mkdir(mode=0o700)
    return path


class Budget:
    """One monotonic episode, not a renewed timeout for each stage/case."""
    def __init__(self, path):
        self.started = time.monotonic()
        self.deadline = self.started + TOTAL_SECONDS
        self.body_deadline = self.deadline - FINAL_SECONDS
        self.path, self.next_disk = path, 0.0
        self.cancelled = []
        self.finalizing = False

    def __call__(self):
        now = time.monotonic()
        need(now < self.deadline, "Whole Android UI episode deadline")
        if not self.finalizing:
            need(not self.cancelled, "Android UI episode cancelled")
            need(now < self.body_deadline, "Android UI body reserve exhausted")
        if now >= self.next_disk:
            need(shutil.disk_usage(self.path).free >= FREE_DISK, "Android UI disk reserve exhausted")
            self.next_disk = now + 1

    def room(self, seconds):
        self()
        end = self.deadline if self.finalizing else self.body_deadline
        need(time.monotonic() + seconds <= end, "Insufficient remaining fixed episode budget")


def properties(raw):
    need(type(raw) is bytes and 0 < len(raw) <= MIB and b"\0" not in raw, "Invalid SDK/AVD properties")
    result = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "!")):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*=([^\r\n\\]*)", line)
        need(match and match[1] not in result, "Unsupported/duplicate SDK or AVD property")
        result[match[1]] = match[2].strip()
    need(result, "Empty SDK/AVD properties")
    return result


def process_rows(raw):
    """Exact toybox ps numeric-column profile; no query failure means absence."""
    need(type(raw) is bytes and 0 < len(raw) <= MIB and raw.endswith(b"\n"), "Incomplete process inventory")
    lines = raw.decode("ascii").splitlines()
    need(lines and lines[0].split() == ["PID", "UID", "NAME"] and 1 < len(lines) <= 8193,
         "Unsupported/empty process inventory profile")
    rows = {}
    for line in lines[1:]:
        match = re.fullmatch(r"\s*([0-9]{1,10})\s+([0-9]{1,10})\s+([^\s\x00-\x1f]+)\s*", line)
        need(match and 0 < int(match[1]) < 2 ** 31 and int(match[1]) not in rows,
             "Ambiguous process inventory row")
        rows[int(match[1])] = {"uid": int(match[2]), "name": match[3]}
    need(any(row["uid"] == 0 for row in rows.values()) and any(row["uid"] == 2000 for row in rows.values()),
         "Process inventory lacks expected system/shell witnesses")
    return rows


def proc_stat(raw, pid):
    need(type(raw) is bytes and len(raw) <= 8192 and raw.endswith(b"\n"), "Incomplete proc stat")
    text = raw.decode("ascii").strip()
    end = text.rfind(") ")
    need(text.startswith(str(pid) + " (") and end > len(str(pid)) + 2, "Wrong proc stat PID/profile")
    fields = text[end + 2:].split()
    need(len(fields) == 50 and fields[0] in ("R", "S", "D", "Z", "T", "t", "X", "I") and
         all(re.fullmatch(r"-?[0-9]{1,20}", value) for value in fields[1:]), "Unsupported proc stat fields")
    need(int(fields[19]) > 0, "Missing kernel process start ticks")
    return {"pid": pid, "comm": text[len(str(pid)) + 2:end], "state": fields[0],
            "parentPid": int(fields[1]), "startTicks": int(fields[19])}


def proc_uid(raw, uid):
    need(type(raw) is bytes and raw.endswith(b"\n") and b"\0" not in raw and len(raw) <= 64 * 1024,
         "Incomplete proc status")
    values = re.findall(rb"(?m)^Uid:\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s+([0-9]+)\s*$", raw)
    need(len(values) == 1 and [int(value) for value in values[0]] == [uid] * 4, "Wrong actual ART credentials")
    return uid


def activity_records(raw):
    """Admit the actual dumpsys command's bounded complete stream and records.

    Task base intents/recents are not running ActivityRecords. Every textual
    ActivityRecord must match the known profile, even when it belongs to a system
    app. A new Android format is HOLD, never an empty accepted Activity set.
    """
    need(type(raw) is bytes and raw.endswith(b"\n") and len(raw) <= core.STREAM_LIMIT,
         "Incomplete Activity inventory")
    text = raw.decode("utf-8")
    need(text.startswith("ACTIVITY MANAGER ACTIVITIES (dumpsys activity activities)\n") and
         re.search(r"(?m)^Display #[0-9]+ \(activities from top to bottom\):$", text) and
         not re.search(r"(?i)permission denial|can't find service|exception|unknown command", text),
         "Unsupported Activity inventory profile")
    pattern = r"ActivityRecord\{[0-9a-f]+ u([0-9]+) ([A-Za-z0-9_.]+)/([A-Za-z0-9_.$]+) t([0-9]+)(?: f)?\}"
    matches = list(re.finditer(pattern, text))
    need(matches and len(matches) == text.count("ActivityRecord"), "Unsupported/empty ActivityRecord serialization")
    return [{"user": int(match[1]), "package": match[2], "component": match[3], "task": int(match[4])}
            for match in matches]


def vm_available(raw):
    text = raw.decode("ascii")
    page = re.findall(r"(?m)^Mach Virtual Memory Statistics: \(page size of ([0-9]+) bytes\)$", text)
    need(len(page) == 1 and int(page[0]) in (4096, 16384), "Unsupported native vm_stat header")
    counts = []
    for label in ("Pages free", "Pages inactive"):
        found = re.findall(r"(?m)^" + label + r":\s+([0-9]+)\.\s*$", text)
        need(len(found) == 1, "Unsupported native vm_stat page counter")
        counts.append(int(found[0]))
    return sum(counts) * int(page[0])  # Not a Linux MemAvailable or allocation guarantee.


def selected_cases(value):
    need(value in SELECTIONS, "Only the fixed UI selections317,324,317+324 are admitted")
    return SELECTIONS[value]


def admit_request(runner, state, owner, args):
    """Bind the live owner to this exact product request, not an arbitrary shell.

    The outer deadline is deliberately NOT certified here: maintained start and
    receipt records have no timeout field. Review the root's original2100s leaf
    launch separately; never infer a timeout from this provisional product result.
    """
    request = runner.read_json(state / "evidence" / owner / "start.json")["requestedArgv"]
    tail = ["--cases", args.cases]
    for name in ("build", "inspection", "archive"):
        tail += ["--" + name + "-receipt", str(getattr(args, name + "_receipt")),
                 "--" + name + "-purpose", getattr(args, name + "_purpose")]
    need(type(request) is list and len(request) == 5 + len(tail) and
         request[0] in ("python3", "/usr/bin/python3", sys.executable) and
         request[1:4] == ["-I", "-B", "-S"] and
         request[4] in ("scripts/run-android-ui-tests.py", str(ROOT / "scripts/run-android-ui-tests.py")) and
         request[5:] == tail, "Active owner did not request the exact isolated Android UI command")
    return {"requestedArgv": request, "requiredOuterSeconds": OUTER_SECONDS,
            "outerTimeoutAuthority": "REQUIRES_ROOT_ORIGINAL_LAUNCH_NOT_RECORDED_IN_RECEIPT"}


def listener_identity(raw, pid, port):
    need(type(raw) is bytes and len(raw) <= 8192 and raw.endswith(b"\n"), "Incomplete owned-listener observation")
    lines = raw.decode("ascii").splitlines()
    need(len(lines) == 3 and lines[0] == "p" + str(pid) and re.fullmatch(r"f[0-9]+", lines[1]) and
         lines[2] == f"n127.0.0.1:{port}", "Listener does not belong to the exact foreground process handle")
    return {"pid": pid, "descriptor": int(lines[1][1:]), "address": "127.0.0.1", "port": port}


def private_environment(original, fixture, sdk):
    for key in ("ADB_SERVER_SOCKET", "ANDROID_ADB_SERVER_PORT", "ANDROID_SERIAL", "ADB_VENDOR_KEYS", "ADB_TRACE",
                "ANDROID_AVD_HOME", "ANDROID_EMULATOR_HOME", "ANDROID_SDK_ROOT", "QEMU_AUDIO_DRV",
                "ANDROID_EMULATOR_USE_SYSTEM_LIBS", "ANDROID_EMULATOR_FORCE_32BIT", "QT_PLUGIN_PATH",
                "QML2_IMPORT_PATH", "DYLD_INSERT_LIBRARIES", "DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH",
                "ANDROID_SDK_HOME", "ANDROID_PREFS_ROOT", "ANDROID_LOG_TAGS", "ANDROID_ADB_LOG_PATH",
                "ANDROID_ADB_SERVER_ADDRESS", "ANDROID_EMULATOR_LAUNCHER_DIR", "QT_QPA_PLATFORM_PLUGIN_PATH"):
        need(not original.get(key), "Resolve conflicting ambient Android/native override: " + key)
    result = dict(original)
    result.update(ANDROID_HOME=str(sdk), ANDROID_USER_HOME=str(fixture / "android-user"),
                  ANDROID_EMULATOR_HOME=str(fixture / "emulator-home"), ANDROID_AVD_HOME=str(fixture / "avd"),
                  HOME=str(fixture / "home"), TMPDIR=str(fixture / "tmp"),
                  XDG_CACHE_HOME=str(fixture / "xdg-cache"))
    return result


class OwnedProcess:
    """Foreground handle and two bounded original pipes; never signals a PID.

    The maintained outer Darwin domain is the only fallback drain. A prefix,
    exited handle or closed local pipe is not reported as native pipe EOF.
    """
    def __init__(self, runner, evidence, label, argv, environment, budget):
        self.runner, self.path, self.budget = runner, evidence, budget
        self.handle = None
        self.thread = None
        self.abort_pump = threading.Event()
        self.record = {"label": label, "argv": list(argv), "startedUtc": runner.utc(), "pid": None,
                       "exitCode": None, "stdoutEof": False, "stderrEof": False,
                       "bytes": {"stdout": 0, "stderr": 0}, "errors": [], "retention": "PARTIAL"}
        self.outputs = {}
        self.argv, self.environment = argv, environment
        self.start_attempted = False

    def start(self):
        # The adapter assigns this object BEFORE attempting native construction,
        # so a failure after Popen still has an exact finalizable handle.
        need(not self.start_attempted, "Foreground start was already attempted")
        self.start_attempted = True
        try:
            for name in ("stdout", "stderr"):
                path = self.path / (self.record["label"] + "." + name)
                self.outputs[name] = self.runner.new_file(path)
                self.record[name] = str(path)
            self.handle = subprocess.Popen(self.argv, cwd=ROOT, env=self.environment, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True, bufsize=0)
            self.record["pid"] = self.handle.pid
            self.thread = threading.Thread(target=self._pump, name="android-ui-" + self.record["label"], daemon=True)
            self.thread.start()
        except BaseException as error:
            self.record["errors"].append(problem(error))
            self.record["exitCode"] = None if self.handle is None else self.handle.poll()
            if self.thread is None or not self.thread.is_alive():
                streams = list(self.outputs.values())
                if self.handle is not None:
                    streams += [self.handle.stdout, self.handle.stderr]
                for stream in streams:
                    try:
                        stream.close()
                    except BaseException as secondary:
                        self.record["errors"].append(problem(secondary))
            try:
                self.runner.write_new_json(self.path / (self.record["label"] + "-failed-start.json"), self.record)
            except BaseException as secondary:
                self.record["errors"].append("Failed-start retention: " + problem(secondary))
            raise

    def _pump(self):
        selector = None
        try:
            selector = selectors.DefaultSelector()
            for name, pipe in (("stdout", self.handle.stdout), ("stderr", self.handle.stderr)):
                os.set_blocking(pipe.fileno(), False)
                selector.register(pipe, selectors.EVENT_READ, name)
            while selector.get_map():
                need(not self.abort_pump.is_set() and time.monotonic() < self.budget.deadline,
                     "Owned background pipe did not reach EOF within the episode")
                for key, _ in selector.select(0.1):
                    name = key.data
                    block = os.read(key.fileobj.fileno(), core.COPY_CHUNK)
                    if not block:
                        self.record[name + "Eof"] = True
                        selector.unregister(key.fileobj)
                        continue
                    self.outputs[name].write(block)
                    self.outputs[name].flush()
                    self.record["bytes"][name] += len(block)
                    need(self.record["bytes"][name] <= BACKGROUND_LIMIT, "Owned background original exceeds bound")
            self.record["retention"] = "COMPLETE_STREAMS"
        except BaseException as error:
            self.record["errors"].append(problem(error))
        finally:
            for pipe in (self.handle.stdout, self.handle.stderr):
                try:
                    pipe.close()
                except BaseException as error:
                    self.record["errors"].append(problem(error))
            if selector is not None:
                try:
                    selector.close()
                except BaseException as error:
                    self.record["errors"].append(problem(error))
            for stream in self.outputs.values():
                try:
                    stream.flush()
                    os.fsync(stream.fileno())
                    stream.close()
                except BaseException as error:
                    self.record["errors"].append(problem(error))

    def healthy(self):
        need(self.handle is not None and self.handle.poll() is None and not self.record["errors"],
             "Owned foreground process exited or its original capture failed")

    def finish(self):
        if self.thread is not None and self.thread.is_alive():
            self.thread.join(THREAD_SECONDS)
            if self.thread.is_alive():
                self.abort_pump.set()
                self.thread.join(THREAD_SECONDS)
        self.record["pumpRetired"] = self.thread is None or not self.thread.is_alive()
        self.record["exitCode"] = None if self.handle is None else self.handle.poll()
        self.record["endedUtc"] = self.runner.utc()
        self.runner.write_new_json(self.path / (self.record["label"] + "-final.json"), self.record)
        need(self.record["pumpRetired"] and self.record["exitCode"] == 0 and
             self.record["stdoutEof"] and self.record["stderrEof"] and not self.record["errors"],
             "Owned foreground process/streams did not retire completely")
        return self.record


class Guest(core.PrivateAdb):
    def __init__(self, commands, sdk, port, serial, server, emulator, case, token, budget):
        super().__init__(commands, sdk, port, serial, server, emulator, case, token)
        self.budget = budget
        self.phase_deadline = None

    @contextmanager
    def phase(self, seconds):
        """Cap a whole multi-command phase; do not renew its time per query."""
        self.budget.room(seconds)
        with self.until(time.monotonic() + seconds):
            yield

    @contextmanager
    def until(self, deadline):
        """Use an already established absolute deadline without renewing it."""
        previous = self.phase_deadline
        self.phase_deadline = deadline if previous is None else min(previous, deadline)
        try:
            need(time.monotonic() < self.phase_deadline, "Guest phase has no time remaining")
            yield
            need(time.monotonic() < self.phase_deadline, "Whole guest phase exceeded its deadline")
        finally:
            self.phase_deadline = previous

    def adb(self, label, arguments, seconds=40, limit=core.STREAM_LIMIT, destination=None):
        if self.phase_deadline is not None:
            seconds = min(seconds, self.phase_deadline - time.monotonic())
        need(seconds > 0, "Guest phase has no command time remaining")
        self.budget.room(seconds)
        need(self.emulator is not None and self.emulator.poll() is None, "Owned emulator handle is not live")
        result = super().adb(label, arguments, seconds, limit, destination)
        self.budget()
        need(self.phase_deadline is None or time.monotonic() < self.phase_deadline,
             "Guest command exceeded its whole-phase deadline")
        return result


class InstrumentWorker:
    def __init__(self, guest, case, token, source):
        self.done = threading.Event()
        self.record = None
        self.error = None
        self.deadline = None
        self.guest, self.case, self.token, self.source = guest, case, token, source
        self.thread = threading.Thread(target=self._run, name="android-ui-instrumentation", daemon=True)

    def _run(self):
        try:
            self.record = core.instrument(self.guest, self.case, self.token, self.source)
        except BaseException as error:
            self.error = problem(error)
        finally:
            self.done.set()

    def start(self):
        self.deadline = time.monotonic() + core.CASES[self.case][1] + THREAD_SECONDS
        self.thread.start()

    def finish(self):
        # The actual command retains its unchanged180s/240s cap. Allow only the
        # remaining original command interval plus3s for its Python final record,
        # never a fresh instrumentation timeout after cleanup starts.
        need(self.deadline is not None, "Instrumentation worker was never started")
        while self.thread.is_alive() and time.monotonic() < self.deadline:
            self.guest.budget()
            self.thread.join(min(0.1, max(0, self.deadline - time.monotonic())))
        need(not self.thread.is_alive() and self.done.is_set(), "Instrumentation worker is unresolved")
        need(self.error is None and self.record is not None, "Instrumentation command failed or is incomplete")
        return core.completed(self.record)


class Adapter:
    def __init__(self, runner, processes, state, context, owner, args):
        self.runner, self.processes, self.state, self.context, self.owner, self.args = (
            runner, processes, state, context, owner, args)
        self.evidence = directory(runner, state / "evidence" / owner / "android-ui")
        self.budget = Budget(state)
        self.artifacts = core.load_tool("verify-android-acceptance-artifacts.py")
        self.verifier = core.load_tool("verify-android-ui-evidence.py")
        self.environment = dict(os.environ)
        self.commands = core.Commands(runner, directory(runner, self.evidence / "commands"), ROOT, self.environment)
        self.server = self.emulator = self.guest = None
        self.device_admitted = False
        self.port = self.serial = self.fixture = self.sdk = None
        self.bundle = None
        self.case_results = []
        self.tools = {}
        self.result = {"schema": 1, "source": context["source"], "ownerId": owner,
                       "jobId": context["id"], "host": context["host"], "status": "INCOMPLETE",
                       "scope": "owned emulated production UI only; no372, physical or release acceptance",
                       "sharedExecutionLease": "OPERATOR_REQUIRED_NOT_CERTIFIED_BY_ADAPTER",
                       "sdkToolAuthenticity": "ORDINARY_OPERATOR_ADMISSION_REQUIRED_SEPARATELY",
                       "nativeRuntimeAndVisualReview": "REQUIRED_SEPARATELY",
                       "boundsSeconds": {"episode": TOTAL_SECONDS, "finalReserve": FINAL_SECONDS,
                                         "documentedOuter": OUTER_SECONDS, "boot": BOOT_SECONDS,
                                         "317": 180, "324": 240, "collection": 120, "artRetirement": ART_SECONDS},
                       "cases": self.case_results, "errors": []}

    def write(self, path, value):
        self.runner.write_new_json(path, value)

    def raw(self, label, argv, seconds=40, limit=core.STREAM_LIMIT):
        self.budget.room(seconds)
        return core.command_bytes(self.commands.run(label, argv, seconds, limit), limit)

    def resources(self, label):
        self.budget()
        pressure = self.raw("memory-pressure", ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"], 10, 64)
        pages = self.raw("memory-pages", ["/usr/bin/vm_stat"], 10, 64 * 1024)
        observation = {"freeDiskBytes": shutil.disk_usage(self.state).free,
                       "pressure": pressure.decode("ascii").strip(), "freePlusInactivePageBytes": vm_available(pages)}
        self.write(self.evidence / ("resources-" + label + ".json"), observation)
        need(observation["pressure"] == "1" and observation["freeDiskBytes"] >= FREE_DISK and
             observation["freePlusInactivePageBytes"] >= FREE_INACTIVE_MEMORY,
             "Native single-guest disk/RAM admission failed")

    def tool_inventory(self):
        rows, total, seen = {}, 0, set()
        for relative in ("platform-tools", "cmdline-tools/latest"):
            pending = [self.sdk / relative]
            while pending:
                self.budget()
                path = pending.pop()
                self.runner.reject_symlinks(path)
                info = path.lstat()
                key = (info.st_dev, info.st_ino)
                need(info.st_uid == os.getuid() and not info.st_mode & 0o022 and key not in seen,
                     "Foreign/writable/aliased SDK tool input")
                seen.add(key)
                need(len(seen) <= TOOL_ENTRIES, "SDK tool inventory exceeds bound")
                name = path.relative_to(self.sdk).as_posix()
                if stat.S_ISDIR(info.st_mode):
                    children = []
                    for child in path.iterdir():
                        self.budget()
                        children.append(child)
                        need(len(children) + len(pending) + len(rows) + 1 <= TOOL_ENTRIES,
                             "SDK tool namespace bound")
                    rows[name] = {"kind": "directory", "mode": info.st_mode, "names": sorted(p.name for p in children)}
                    pending.extend(sorted(children))
                else:
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "SDK tool input is not a regular file")
                    binding = archives.file_binding(path, core.APK_LIMIT, self.budget)[0]
                    total += binding["bytes"]
                    need(total <= TOOL_BYTES, "SDK tool byte inventory exceeds bound")
                    rows[name] = {"kind": "file", "mode": info.st_mode, **binding}
        return rows

    def prepare(self):
        self.resources("initial")
        checker = core.load_tool("check-audit-receipt.py")
        self.bundle = core.intake(self.runner, checker, self.artifacts, core.load_tool("run-android-art-smoke.py"),
                                 self.state, self.context, ROOT, self.args)
        self.result["apkAuthority"] = self.bundle["bindings"]
        archive_evidence = directory(self.runner, self.evidence / "archive-recheck")
        archive_result = {"status": "INCOMPLETE"}
        try:
            archives.admit_retained(self.runner, checker, self.artifacts, self.state, self.context, self.owner,
                                    self.environment, self.args.archive_receipt, self.args.archive_purpose,
                                    self.budget, archive_evidence, archive_result)
        finally:
            self.write(archive_evidence / "result.json", archive_result)
        self.sdk = archives.selected_sdk(self.environment, ROOT, self.budget)
        self.tools = self.tool_inventory()
        self.write(self.evidence / "sdk-tool-identities.json", self.tools)
        for name in ("platform-tools/adb", "cmdline-tools/latest/bin/avdmanager"):
            need(name in self.tools and self.tools[name]["kind"] == "file" and self.tools[name]["mode"] & 0o111,
                 "Missing executable from selected physical SDK tools")
        adb_properties = properties(self.artifacts.fingerprint(self.sdk / "platform-tools/source.properties", MIB, True)[1])
        revision = adb_properties.get("Pkg.Revision", "")
        need(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", revision), "Unsupported platform-tools version metadata")
        self.fixture = core.new_fixture(self.runner, self.state)
        for name in ("android-user", "emulator-home", "avd", "home", "tmp", "xdg-cache"):
            directory(self.runner, self.fixture / name)
        self.environment = private_environment(self.environment, self.fixture, self.sdk)
        self.commands.environment = dict(self.environment)
        raw = self.raw("adb-version", [str(self.sdk / "platform-tools/adb"), "version"], 10, 64 * 1024)
        text = raw.decode("utf-8")
        need(text.startswith("Android Debug Bridge version 1.0.41\n") and
             len(re.findall(r"(?m)^Version ([^\r\n]+)$", text)) == 1 and
             re.findall(r"(?m)^Version ([^\r\n]+)$", text)[0].startswith(revision + "-") and
             re.findall(r"(?m)^Installed as ([^\r\n]+)$", text) == [str(self.sdk / "platform-tools/adb")] and
             len(re.findall(r"(?m)^Running on Darwin [^\r\n]+$", text)) == 1,
             "Unsupported actual native adb version profile")
        version = self.raw("emulator-version", [str(self.sdk / "emulator/emulator"), "-version"], 10, 64 * 1024)
        need(len(re.findall(rb"(?m)^Android emulator version 36\.6\.11(?:\.0)? \(build_id 15507667\)[^\r\n]*$", version)) == 1,
             "Actual emulator does not match the fixed archive profile")
        self.create_avd()

    def listener(self, process, port, label, *, starting=False, seconds=10):
        process.healthy()
        self.budget.room(seconds)
        record = self.commands.run(label, ["/usr/sbin/lsof", "-nP", "-a", "-p", str(process.handle.pid),
            "-iTCP@127.0.0.1:" + str(port), "-sTCP:LISTEN", "-Fpfn"], seconds, 8192)
        process.healthy()
        if starting and record["exitCode"] == 1:
            need(record["stdoutEof"] and record["stderrEof"] and not record["errors"] and
                 record["retention"] == "COMPLETE_STREAMS" and
                 archives.file_binding(Path(record["stdout"]), 8192, self.budget, True)[1] == b"" and
                 archives.file_binding(Path(record["stderr"]), 8192, self.budget, True)[1] == b"",
                 "Failed/unsupported foreground-listener observation")
            return None  # Only a startup retry, never an ownership/absence pass.
        return listener_identity(core.command_bytes(record, 8192), process.handle.pid, port)

    def create_avd(self):
        self.avd_name = "p2pkit-ui-" + self.owner
        avd = self.fixture / "avd" / (self.avd_name + ".avd")
        need(not os.path.lexists(avd), "AVD path already exists")
        self.raw("avd-create", [str(self.sdk / "cmdline-tools/latest/bin/avdmanager"), "create", "avd",
                 "--name", self.avd_name, "--package", archives.IMAGE_PACKAGE, "--device", "pixel_2",
                 "--path", str(avd)], 90)
        config = avd / "config.ini"
        original, raw = self.artifacts.fingerprint(config, MIB, True)
        data = properties(raw)
        self.write(self.evidence / "avd-generated-config.json", {"path": str(config), **original, "properties": data})
        need(data.get("abi.type") == "arm64-v8a" and data.get("hw.cpu.arch") == "arm64" and
             data.get("image.sysdir.1", "").rstrip("/") in (archives.IMAGE_PATH, str(self.sdk / archives.IMAGE_PATH)),
             "AVD manager selected another image or architecture")
        # Only the newly generated owned config is updated, before first boot.
        # Command-line flags also disable snapshots/cameras/audio/metrics.
        data.update({"hw.lcd.width": str(DISPLAY[0]), "hw.lcd.height": str(DISPLAY[1]),
                     "hw.lcd.density": str(DISPLAY[2]), "hw.initialOrientation": "portrait",
                     "hw.ramSize": "2048", "hw.cpu.ncore": "2", "hw.gpu.enabled": "yes", "hw.gpu.mode": "host",
                     "disk.dataPartition.size": "3G", "hw.sdCard": "no", "fastboot.forceColdBoot": "yes",
                     "fastboot.forceFastBoot": "no", "fastboot.forceChosenSnapshotBoot": "no"})
        temporary = avd / "config.ui-new"
        with self.runner.new_file(temporary) as stream:
            stream.write("".join(key + "=" + value + "\n" for key, value in sorted(data.items())).encode())
            stream.flush()
            os.fsync(stream.fileno())
        need(self.artifacts.fingerprint(config, MIB)[0] == original, "Owned AVD config changed before replacement")
        os.replace(temporary, config)
        ini = properties(self.artifacts.fingerprint(self.fixture / "avd" / (self.avd_name + ".ini"), MIB, True)[1])
        need(ini.get("path") == str(avd), "AVD index does not name this invocation's directory")
        self.write(self.evidence / "avd-configured.json", {"name": self.avd_name, "index": ini,
                   "config": self.artifacts.fingerprint(config, MIB)[0], "properties": data,
                   "scope": "pre-boot owned viewport selection; not runtime/frame qualification"})

    def boot(self):
        self.resources("before-boot")
        # Reserve once, then fail if either endpoint is busy at launch. No port
        # scanning, existing-server adoption, retry or default adb server exists.
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            self.port = reservation.getsockname()[1]
        console = 5580
        for port in (console, console + 1):
            with socket.socket() as reservation:
                reservation.bind(("127.0.0.1", port))
        self.serial = "emulator-" + str(console)
        self.environment.update(ANDROID_ADB_SERVER_PORT=str(self.port), ADB_SERVER_SOCKET=f"tcp:127.0.0.1:{self.port}")
        self.commands.environment = dict(self.environment)
        background = directory(self.runner, self.evidence / "foreground-processes")
        self.server = OwnedProcess(self.runner, background, "adb-server",
            [str(self.sdk / "platform-tools/adb"), "-L", f"tcp:127.0.0.1:{self.port}", "nodaemon", "server"],
            self.environment, self.budget)
        self.server.start()
        # Do not let a client auto-start a server or address a racing unrelated
        # listener. First bind the listener to this actual still-live handle.
        deadline = time.monotonic() + 10
        while True:
            self.budget()
            self.server.healthy()
            remaining = deadline - time.monotonic()
            need(remaining > 0, "Owned adb foreground listener startup deadline")
            observed = self.listener(self.server, self.port, "adb-owned-listener", starting=True, seconds=remaining)
            need(time.monotonic() < deadline, "Owned adb foreground listener startup deadline")
            if observed is not None:
                break
            need(time.monotonic() < deadline, "Owned adb foreground listener startup deadline")
            time.sleep(0.05)
        empty = self.raw("private-empty-server", [str(self.sdk / "platform-tools/adb"), "-P", str(self.port), "devices"], 10)
        self.server.healthy()
        core.require_empty_server(empty)
        argv = [str(self.sdk / "emulator/emulator"), "-avd", self.avd_name, "-port", str(console),
                "-accel", "on", "-memory", "2048", "-cores", "2", "-gpu", "host", "-no-window",
                "-skin", f"{DISPLAY[0]}x{DISPLAY[1]}", "-dpi-device", str(DISPLAY[2]), "-no-audio",
                "-camera-back", "none", "-camera-front", "none", "-no-boot-anim", "-no-snapshot", "-no-metrics"]
        self.emulator = OwnedProcess(self.runner, background, "emulator", argv, self.environment, self.budget)
        self.emulator.start()
        # This initial token has no case execution or output authority.
        self.guest = Guest(self.commands, self.sdk, self.port, self.serial, self.server.handle,
                           self.emulator.handle, "317", uuid.uuid4().hex, self.budget)
        with self.guest.phase(BOOT_SECONDS):
            while True:
                self.budget()
                self.server.healthy()
                self.emulator.healthy()
                record = self.guest.adb("boot-state", ["shell", "getprop", "sys.boot_completed"], seconds=10, limit=1024)
                # An offline/no-device failure is only a retained startup
                # observation, never accepted as absence or a boot success.
                if record["exitCode"] == 0:
                    if core.command_bytes(record, 1024).strip() == b"1":
                        break
                else:
                    need(record["stdoutEof"] and record["stderrEof"] and not record["errors"], "Incomplete boot query")
                time.sleep(0.25)
        self.listener(self.server, self.port, "adb-owned-listener-after-boot")
        self.listener(self.emulator, console, "emulator-owned-console")
        devices = self.raw("private-single-device", [str(self.sdk / "platform-tools/adb"), "-P", str(self.port), "devices"], 10)
        need(devices in (("List of devices attached\n" + self.serial + "\tdevice\n").encode(),
                        ("List of devices attached\n" + self.serial + "\tdevice\n\n").encode()),
             "Private server contains an unexpected/offline device")
        avd_name = core.command_bytes(self.guest.adb("actual-avd-name", ["emu", "avd", "name"], seconds=10), 1024)
        need(avd_name == (self.avd_name + "\nOK\n").encode(), "Unsupported/wrong actual AVD identity")
        self.device_admitted = True
        values = {}
        expected = {"ro.build.version.sdk": "37", "ro.build.version.sdk_full": "37.0",
                    "ro.build.version.codename": "REL", "ro.build.version.preview_sdk": "0",
                    "ro.product.cpu.abi": "arm64-v8a", "ro.kernel.qemu": "1",
                    "ro.system.build.fingerprint": IMAGE_FINGERPRINT}
        for name in (*expected, "ro.build.fingerprint", "ro.build.version.security_patch"):
            raw = core.command_bytes(self.guest.adb("guest-property", ["shell", "getprop", name], seconds=10, limit=2048), 2048)
            need(raw.endswith(b"\n") and raw.count(b"\n") == 1 and raw.strip(), "Unsupported guest property result")
            values[name] = raw.decode("ascii").strip()
        need(all(values[key] == value for key, value in expected.items()), "Actual guest differs from selected image profile")
        page = core.command_bytes(self.guest.adb("guest-page-size", ["shell", "getconf", "PAGESIZE"], seconds=10), 64)
        need(page.strip() == b"16384", "Selected image did not run the declared16KiB page size")
        core.completed(self.guest.adb("wake-owned-guest", ["shell", "input", "keyevent", "KEYCODE_WAKEUP"], seconds=10))
        core.completed(self.guest.adb("dismiss-empty-keyguard", ["shell", "wm", "dismiss-keyguard"], seconds=10))
        size = core.command_bytes(self.guest.adb("physical-size", ["shell", "wm", "size"], seconds=10), 1024)
        density = core.command_bytes(self.guest.adb("physical-density", ["shell", "wm", "density"], seconds=10), 1024)
        need(size.strip() == b"Physical size: 1600x2560" and density.strip() == b"Physical density: 200",
             "Actual viewport has an override or differs from the pre-boot profile")
        self.write(self.evidence / "guest-profile.json", {"properties": values, "pageSizeBytes": 16384,
                   "viewport": list(DISPLAY), "requestedGpu": "host", "avdName": self.avd_name, "serial": self.serial,
                   "rendering": "ACTUAL_HARNESS_FRAME_AND_PIXEL_REVIEW_STILL_REQUIRED", "compat372": "NOT_QUALIFIED"})

    def packages(self, guest):
        return core.package_uids(core.command_bytes(guest.adb("package-inventory",
            ["shell", "pm", "list", "packages", "--user", "0", "-U"], seconds=10), MIB))

    def installed_uids(self, guest, installed):
        actual = self.packages(guest)
        for package, row in installed.items():
            need(actual.get(package) == row["uid"] and list(actual.values()).count(row["uid"]) == 1,
                 "Installed target ownership changed")

    def install(self, guest, evidence):
        packages = self.packages(guest)
        need(not any(package in packages for package in core.PACKAGES), "UI install is not fresh")
        for role in ("app", "test"):
            item = self.bundle["map"]["components"][role]["apk"]
            self.artifacts.verified_file(ROOT, item["path"], item, core.APK_LIMIT)
            raw = core.command_bytes(guest.adb(role + "-install", ["install", "--user", "0", str(self.bundle["apks"][role])],
                                              seconds=120), core.STREAM_LIMIT)
            need(raw.decode("utf-8").splitlines() in (["Performing Streamed Install", "Success"], ["Success"]),
                 "Unsupported/failed fresh APK installation result")
        installed = core.installed_pair(guest, self.artifacts, ROOT, self.bundle, evidence)
        self.write(evidence / "installed-pair.json", installed)
        return installed

    def inventory(self, guest):
        raw = core.command_bytes(guest.adb("art-process-inventory",
            ["shell", "/system/bin/toybox", "ps", "-A", "-o", "PID,UID,NAME"], seconds=10, limit=MIB), MIB)
        return process_rows(raw)

    def observe_art(self, guest, installed, previous):
        rows = self.inventory(guest)
        uid = installed[core.PACKAGE]["uid"]
        members = [pid for pid, row in rows.items() if row["uid"] in {value["uid"] for value in installed.values()}]
        if not members:
            return None
        need(len(members) == 1 and rows[members[0]]["uid"] == uid, "Unexpected process in the newly installed UI UIDs")
        pid = members[0]
        captured = {}
        for name in ("stat", "status", "cmdline"):
            remote = shlex.join(["run-as", core.PACKAGE, "/system/bin/toybox", "cat", f"/proc/{pid}/{name}"])
            captured[name] = core.command_bytes(guest.adb("art-" + name, ["exec-out", remote], seconds=10, limit=64 * 1024),
                                                64 * 1024)
        identity = proc_stat(captured["stat"], pid)
        proc_uid(captured["status"], uid)
        need(captured["cmdline"].endswith(b"\0") and captured["cmdline"].rstrip(b"\0") == core.PACKAGE.encode(),
             "Live ART argv is not the exact target")
        remote = shlex.join(["run-as", core.PACKAGE, "/system/bin/toybox", "cat", f"/proc/{pid}/stat"])
        after = proc_stat(core.command_bytes(guest.adb("art-stat-after", ["exec-out", remote], seconds=10,
                                                      limit=64 * 1024), 64 * 1024), pid)
        need(all(after[key] == identity[key] for key in ("pid", "comm", "parentPid", "startTicks")),
             "ART identity changed during credential/argv observation")
        identity.update(uid=uid, package=core.PACKAGE)
        if previous is not None:
            need(all(identity[key] == previous[key] for key in ("pid", "uid", "startTicks", "package")),
                 "UI process identity changed while instrumentation was live")
        return identity

    def retire_art(self, guest, installed, identity):
        with guest.phase(ART_SECONDS):
            return self._retire_art(guest, installed, identity)

    def _retire_art(self, guest, installed, identity):
        self.installed_uids(guest, installed)
        before = self.inventory(guest)
        uids = {row["uid"] for row in installed.values()}
        if identity is not None and identity["pid"] in before:
            current = self.observe_art(guest, installed, identity)
            need(current is not None, "ART identity vanished ambiguously before retirement")
        # These packages were absent before our unchanged installs in this owned
        # guest. force-stop is the explicit teardown, not a harness success rescue.
        for package in core.PACKAGES:
            core.completed(guest.adb("stop-owned-package", ["shell", "am", "force-stop", "--user", "0", package], seconds=10))
        snapshots = []
        while len(snapshots) < 2:
            rows = self.inventory(guest)
            records = activity_records(core.command_bytes(guest.adb("activity-retirement",
                ["shell", "dumpsys", "activity", "activities"], seconds=10), core.STREAM_LIMIT))
            need(not any(row["uid"] in uids for row in rows.values()), "Owned ART process still exists")
            need(not any(row["package"] in core.PACKAGES for row in records), "Owned ActivityRecord still exists")
            snapshots.append({"processRows": len(rows), "ownedUidMembers": [], "activityRecords": records})
            if len(snapshots) < 2:
                time.sleep(0.25)
        self.installed_uids(guest, installed)
        return {"status": "RETIRED", "identityBefore": identity, "snapshots": snapshots,
                "mechanism": "explicit force-stop of this fresh install; not natural ART-exit qualification"}

    def run_case(self, case):
        token = uuid.uuid4().hex
        evidence = directory(self.runner, self.evidence / ("case-" + case + "-" + token))
        # Installed APKs and collector originals are descendants of this exact
        # command root. A separate /commands root would reject their destinations.
        commands = core.Commands(self.runner, evidence, ROOT, self.environment)
        guest = Guest(commands, self.sdk, self.port, self.serial, self.server.handle, self.emulator.handle,
                      case, token, self.budget)
        row = {"case": case, "token": token, "status": "INCOMPLETE", "errors": [], "evidence": str(evidence),
               "instrumentation": None, "artRetirement": "UNKNOWN", "content": None}
        self.case_results.append(row)
        installed = worker = identity = None
        observations = []
        final_collection = None
        try:
            self.resources("before-" + case)
            installed = self.install(guest, evidence)
            instrumentation = core.Commands(self.runner, directory(self.runner, evidence / "instrumentation"),
                                             ROOT, self.environment)
            instrument_guest = Guest(instrumentation, self.sdk, self.port, self.serial, self.server.handle,
                                     self.emulator.handle, case, token, self.budget)
            self.budget.room(core.CASES[case][1])
            worker = InstrumentWorker(instrument_guest, case, token, self.context["source"])
            worker.start()
            # A worker blocked before its done event must not keep the observer
            # alive until the much longer episode deadline. Every observer adb
            # command and event wait shares the original180/240s +3s boundary.
            with guest.until(worker.deadline):
                while not worker.done.is_set():
                    need(time.monotonic() < worker.deadline, "Instrumentation worker observation deadline")
                    self.budget()
                    self.server.healthy()
                    self.emulator.healthy()
                    observed = self.observe_art(guest, installed, identity)
                    if observed is not None:
                        identity = observed
                        observations.append({"observedUtc": self.runner.utc(), **observed})
                    remaining = worker.deadline - time.monotonic()
                    need(remaining > 0, "Instrumentation worker observation deadline")
                    worker.done.wait(min(0.25 if identity is None else 1.0, remaining))
                row["instrumentation"] = worker.finish()
            need(identity is not None, "No supported live target ART identity was observed")
            terminal = self.verifier.parse_terminal(core.command_bytes(row["instrumentation"], core.STREAM_LIMIT), case, token)
            need(terminal["p2pkitOutcome"] == self.verifier.POSITIVE, "Named UI harness reported failure")
        except BaseException as error:
            row["errors"].append(problem(error))
        finally:
            old = self.budget.finalizing
            self.budget.finalizing = True
            retirement = {}

            def collect(phase):
                need(installed is not None, "No admitted fresh installed target for collection")
                self.budget.room(core.COLLECTION_SECONDS)
                return core.Collector(self.runner, guest, self.verifier, evidence, case, token,
                                      installed[core.PACKAGE]["uid"], phase).collect()

            def retire():
                need(installed is not None, "No admitted installed target for retirement")
                retirement.update(self.retire_art(guest, installed, identity))
                row["artRetirement"] = retirement
                return retirement

            def finish_instrument():
                need(worker is not None, "Instrumentation was not started")
                record = worker.finish()
                if row["instrumentation"] is None:
                    row["instrumentation"] = record
                return record

            def final_capture():
                nonlocal final_collection
                need(retirement.get("status") == "RETIRED", "No exact ART/Activity retirement for stable final capture")
                final_collection = collect("after-retirement")
                return final_collection

            actions = [("partial-originals", lambda: collect("before-retirement-partial")),
                       ("exact-art-retirement", retire), ("instrumentation-worker", finish_instrument),
                       ("stable-final-originals", final_capture),
                       ("guest-logcat", lambda: core.completed(guest.adb("case-logcat",
                            ["logcat", "-d", "-v", "threadtime"], seconds=20, limit=core.STREAM_LIMIT)))]
            row["finally"] = core.attempt_all(self.runner, evidence, actions)
            self.budget.finalizing = old
            self.write(evidence / "live-art-observations.json", observations)
            for action in row["finally"]:
                if action["status"] != "RETURNED":
                    row["errors"].append("Finally failed: " + action["step"])
            try:
                need(final_collection is not None and row["instrumentation"] is not None,
                     "Missing final originals/terminal instrumentation stream")
                retained = Path(final_collection["retainedRoot"])
                report = self.runner.read_json(retained / "result.json")
                need(identity is not None and report.get("pid") == identity["pid"] and
                     type(report.get("processStartElapsedMillis")) is int and report["processStartElapsedMillis"] > 0,
                     "Retained report differs from observed live target process")
                if case == "317":
                    need(report.get("uid") == identity["uid"], "Retained report differs from actual installed UID")
                row["processBinding"] = {"observedKernelIdentity": identity,
                    "reportedProcessStartElapsedMillis": report["processStartElapsedMillis"],
                    "clockMeaning": "kernel start ticks and Java elapsed-start milliseconds are not equated"}
                row["content"] = core.retain_content_result(self.runner, self.verifier, evidence, retained,
                    Path(row["instrumentation"]["stdout"]), case, token, self.context["source"])
                need(row["content"]["contentStatus"] == "CONSISTENT", "UI original content did not pass its passive checks")
            except BaseException as error:
                row["errors"].append(problem(error))
            row["commandSettlement"] = commands.settlement()
            if any(item["exitCode"] is None for item in row["commandSettlement"]):
                row["errors"].append("Case command child remains unresolved")
            if worker is not None:
                row["instrumentationWorkerOutcome"] = {"error": worker.error, "record": worker.record}
                row["instrumentationCommandSettlement"] = worker.guest.commands.settlement()
                row["instrumentationWorkerRetired"] = not worker.thread.is_alive()
                if not row["instrumentationWorkerRetired"] or any(item["exitCode"] is None for item in
                                                                 row["instrumentationCommandSettlement"]):
                    row["errors"].append("Instrumentation child/worker remains unresolved")
            if not row["errors"]:
                row["status"] = "CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW"
            self.write(evidence / "result.json", row)
        need(not row["errors"], "UI case failed; stop before another case/installation")
        return guest, installed, row

    def between_cases(self, guest, installed, row):
        need(row["status"] == "CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW" and
             row["artRetirement"]["status"] == "RETIRED" and row["content"]["contentStatus"] == "CONSISTENT",
             "No successful retained/retired first case for shared-guest reuse")
        self.installed_uids(guest, installed)
        for package in core.PACKAGES:
            raw = core.command_bytes(guest.adb("between-case-uninstall", ["uninstall", package], seconds=40), 1024)
            need(raw.strip() == b"Success", "Owned between-case uninstall did not complete")
        remaining = self.packages(guest)
        need(not any(package in remaining for package in core.PACKAGES), "Packages remain between UI cases")
        need(not any(value["uid"] in {item["uid"] for item in installed.values()} for value in self.inventory(guest).values()),
             "Previous install's process survives uninstall")
        self.write(self.evidence / "between-case-freshness.json", {"previousCase": row["case"],
                   "retainedResult": str(Path(row["evidence"]) / "result.json"),
                   "packagesAbsent": list(core.PACKAGES), "nextInstall": "MUST_REINSTALL_AND_READ_BACK_SAME_APKS"})

    def stop_emulator(self):
        need(self.device_admitted and self.guest is not None and self.emulator is not None,
             "No admitted owned emulator command channel; outer Darwin drain must retire its exact handle")
        self.listener(self.emulator, 5580, "emulator-owned-console-before-stop")
        return core.completed(self.guest.adb("stop-owned-emulator", ["emu", "kill"], seconds=10))

    def stop_server(self):
        need(self.server is not None and self.port is not None, "No owned foreground server")
        self.server.healthy()
        self.listener(self.server, self.port, "adb-owned-listener-before-stop")
        return core.completed(self.commands.run("stop-private-server",
            [str(self.sdk / "platform-tools/adb"), "-P", str(self.port), "kill-server"], 10))

    def run(self):
        handlers = {}
        try:
            for number in (signal.SIGINT, signal.SIGTERM):
                handlers[number] = signal.getsignal(number)
                signal.signal(number, lambda signum, _frame: self.budget.cancelled.append(signum))
            self.prepare()
            self.boot()
            cases = selected_cases(self.args.cases)
            for index, case in enumerate(cases):
                guest, installed, row = self.run_case(case)
                if index + 1 < len(cases):
                    self.between_cases(guest, installed, row)
            need(self.tool_inventory() == self.tools, "Shared SDK tools changed during UI execution")
            self.resources("after-cases")
        except BaseException as error:
            self.result["errors"].append(problem(error))
        finally:
            self.budget.finalizing = True
            actions = []
            if self.emulator is not None:
                actions.append(("emulator-shutdown", self.stop_emulator))
            if self.server is not None:
                actions.append(("adb-server-shutdown", self.stop_server))
            if self.emulator is not None or self.server is not None:
                # stop_handles always attempts both. Missing/failed handles remain
                # explicit errors, never a reason to skip the other wait.
                handles = type("OwnedHandles", (), {"emulator": None if self.emulator is None else self.emulator.handle,
                                                    "server": None if self.server is None else self.server.handle})()
                actions.append(("foreground-handle-waits", lambda: core.stop_handles(handles)))
            if self.emulator is not None:
                actions.append(("emulator-original-streams", self.emulator.finish))
            if self.server is not None:
                actions.append(("server-original-streams", self.server.finish))
            self.result["finally"] = core.attempt_all(self.runner, self.evidence, actions)
            for row in self.result["finally"]:
                if row["status"] != "RETURNED" or (row["step"] == "foreground-handle-waits" and
                        any("error" in value for value in row.get("observation", {}).values())):
                    self.result["errors"].append("Finally failed: " + row["step"])
            self.result["commandSettlement"] = self.commands.settlement()
            if any(item["exitCode"] is None for item in self.result["commandSettlement"]):
                self.result["errors"].append("Ordinary command child remains unresolved")
            self.result["cancelledSignals"] = self.budget.cancelled
            try:
                self.result["sourceAfter"] = self.runner.source_snapshot(ROOT)
                need(self.result["sourceAfter"] == self.context["source"], "Source changed during UI episode")
                need(len(self.case_results) == len(selected_cases(self.args.cases)) and
                     all(row["status"] == "CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW" for row in self.case_results),
                     "UI selection did not complete every case")
                self.budget()
            except BaseException as error:
                self.result["errors"].append(problem(error))
            self.result["elapsedSeconds"] = time.monotonic() - self.budget.started
            for number, handler in handlers.items():
                signal.signal(number, handler)
            # Budget checks intentionally ignore cancellation during cleanup.
            # Decide success only after every observation and handler restore:
            # no later signal can enter our append-only cancellation handler.
            # Restored normal dispositions propagate rather than being swallowed.
            self.result["cancelledSignals"] = list(self.budget.cancelled)
            if self.result["cancelledSignals"]:
                self.result["errors"].append("Android UI episode cancelled before result commit")
            if not self.result["errors"]:
                self.result["status"] = "CAPTURED_PENDING_OUTER_RECEIPT_AND_REVIEW"
            self.write(self.evidence / "result.json", self.result)
        return 0 if not self.result["errors"] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True, choices=tuple(SELECTIONS))
    for name in ("build", "inspection", "archive"):
        parser.add_argument("--" + name + "-receipt", required=True, type=Path)
        parser.add_argument("--" + name + "-purpose", required=True)
    args = parser.parse_args()
    need(os.getuid() != 0, "Use an ordinary native Mac user, not root")
    runner = core.load_tool("run-audit-command.py")
    processes = core.load_tool("audit_processes.py")
    state, context = runner.context_at(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    owner = core.admit_outer(runner, processes, state, context, ROOT, os.environ)
    request = admit_request(runner, state, owner, args)
    lock = runner.LeafLock(state)
    try:
        lock.acquire()
        adapter = Adapter(runner, processes, state, context, owner, args)
        adapter.result["ownerRequest"] = request
        code = adapter.run()
        path = adapter.evidence / "result.json"
        binding = adapter.artifacts.fingerprint(path, runner.MAX_JSON_BYTES)[0]
        sys.stdout.buffer.write(runner.json_bytes({"path": str(path), **binding}))
        return code
    finally:
        # Release before the maintained outer finalizer's SAME-HOME wrapper stop.
        # No fixture/output/cache deletion is safe before that terminal receipt.
        lock.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (Exception, KeyboardInterrupt) as error:
        print("Android UI HOLD: " + problem(error), file=sys.stderr)
        raise SystemExit(1)
