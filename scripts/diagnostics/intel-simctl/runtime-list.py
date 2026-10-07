#!/usr/bin/env python3
"""One unchanged runtime-list command plus read-only owned-child metadata; not qualification."""
from __future__ import annotations

import ctypes
from datetime import datetime, timezone
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import queue
import re
import signal
import stat
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("platform_gate", ROOT / "scripts/run-platform-tests.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)

SCOPE = "INTEL_SIMCTL_RUNTIME_METADATA_DIAGNOSTIC_V1"
MARKER = "P2PKIT_SIMCTL_RUNTIME_METADATA_V1 "
PHASES = ("simulator-macos-version", "simulator-xcode-version", "simulator-first-launch", "simulator-runtimes")
TARGET_MILLISECONDS = (100, 10000, 45000, 90000)
FRAME_SECONDS, BASELINE_SECONDS, JOIN_SECONDS = 1.0, 1.0, 0.25
PID_LIMIT, BASELINE_CHILD_LIMIT, JSON_LIMIT = 4096, 64, 64 * 1024
IMAGES = {"UNKNOWN", "XCRUN", "SIMCTL", "OTHER"}
REASONS = {"NONE", "API_UNAVAILABLE", "ABI_INVALID", "CENSUS_INVALID", "CENSUS_LIMIT", "IDENTITY_DENIED",
           "IDENTITY_INVALID", "IDENTITY_UNAVAILABLE", "BASELINE_FAILED", "BASELINE_UNFINISHED",
           "CONTROLLER_CHANGED", "NO_CANDIDATE", "AMBIGUOUS", "REPLACED", "EXEC_CHANGED", "LATE",
           "WORK_LIMIT", "STOPPED", "OBSERVER_UNFINISHED", "OBSERVER_FAILED"}
IDENTITY_FIELDS = {"pid", "uid", "parentPid", "parentUniqueId", "parentPidVersion", "group", "uniqueId",
                   "pidVersion", "startSeconds", "startMicroseconds", "status"}
INPUTS = ("scripts/diagnostics/intel-simctl/runtime-list.py", "scripts/run-platform-tests.py",
          "scripts/audit_processes.py", "scripts/hosted_full_simulator.py", ".github/workflows/ios-x64-tests.yml")


def require(value, reason):
    if not value:
        raise ValueError(reason)


def encoded(value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
    require(len(raw) <= JSON_LIMIT, "JSON_LIMIT")
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, "INTEGER")


def exact_keys(value, fields):
    require(type(value) is dict and set(value) == set(fields), "KEYS")


def validate_identity(value):
    exact_keys(value, IDENTITY_FIELDS)
    for name in ("pid", "parentPid", "group"):
        integer(value[name], 1, 2**31 - 1)
    integer(value["uid"], 0, 2**32 - 1)
    for name in ("uniqueId", "parentUniqueId"):
        integer(value[name], 1, 2**64 - 1)
    for name in ("pidVersion", "parentPidVersion"):
        integer(value[name], 0, 2**31 - 1)
    integer(value["startSeconds"], 1, 2**63 // 1000000)
    integer(value["startMicroseconds"], 0, 999999)
    integer(value["status"], 1, 5)
    return value


def lifetime(value):
    return (value["pid"], value["uniqueId"], value["startSeconds"], value["startMicroseconds"])


def stable(before, after):
    return all(before[name] == after[name] for name in IDENTITY_FIELDS - {"status"})


def eligible(value, controller, armed_epoch_us, baseline):
    return (value["uid"] == controller["uid"] and value["parentPid"] == controller["pid"] and
            value["parentUniqueId"] == controller["uniqueId"] and
            value["parentPidVersion"] == controller["pidVersion"] and value["group"] == value["pid"] and
            value["status"] != 5 and lifetime(value) not in baseline and
            value["startSeconds"] * 1000000 + value["startMicroseconds"] >= armed_epoch_us)


def choose_child(rows, controller, armed_epoch_us, baseline, latched):
    choices = [row for row in rows if eligible(row, controller, armed_epoch_us, baseline)]
    if len(choices) != 1:
        return None, "NO_CANDIDATE" if not choices else "AMBIGUOUS", len(choices)
    if latched is not None and lifetime(choices[0]) != latched:
        return None, "REPLACED", 1
    return choices[0], "NONE", 1


def closed_image(comm, name):
    # Called only after the atomic identity response passes the owned-child filter.
    # Neither field, nor any path/argv/environment, is retained in an observation.
    if comm == b"xcrun" and name == b"xcrun":
        return "XCRUN"
    if comm == b"simctl" and name == b"simctl":
        return "SIMCTL"
    return "OTHER"


def unknown_frame(index, reason, observed=-1, error=0, count=0):
    return {"index": index, "targetMilliseconds": TARGET_MILLISECONDS[index], "observedMilliseconds": observed,
            "outcome": "UNKNOWN", "reason": reason, "errno": error, "candidateCount": count,
            "image": "UNKNOWN", "status": 0, "identity": None, "recheck": None}


def validate_observations(value):
    exact_keys(value, {"schema", "scope", "qualification", "armedEpochMicroseconds", "observerStarted",
                       "observerFinished", "baseline", "frames"})
    integer(value["schema"], 1, 1)
    require(value["scope"] == SCOPE and value["qualification"] is False, "SCOPE")
    if value["armedEpochMicroseconds"] is not None:
        integer(value["armedEpochMicroseconds"], 1, 2**63 - 1)
    for name in ("observerStarted", "observerFinished"):
        require(type(value[name]) is bool, "BOOLEAN")
    require(not value["observerFinished"] or value["observerStarted"], "OBSERVER_STATE")
    base = value["baseline"]
    exact_keys(base, {"reason", "errno", "controller", "children"})
    require(base["reason"] in REASONS, "REASON")
    integer(base["errno"], 0, 4095)
    require(type(base["children"]) is list and len(base["children"]) <= BASELINE_CHILD_LIMIT, "BASELINE")
    baseline = []
    for row in base["children"]:
        require(type(row) is list and len(row) == 4, "BASELINE_ROW")
        for item in row:
            integer(item, 0, 2**64 - 1)
        baseline.append(tuple(row))
    require(len(set(baseline)) == len(baseline), "BASELINE_DUPLICATE")
    if base["reason"] == "NONE":
        validate_identity(base["controller"])
        require(base["controller"]["status"] != 5 and base["errno"] == 0, "CONTROLLER")
    else:
        require(base["controller"] is None and not baseline, "FAILED_BASELINE")
    require(type(value["frames"]) is list and len(value["frames"]) == 4, "FRAMES")
    latched = None
    for index, frame in enumerate(value["frames"]):
        exact_keys(frame, unknown_frame(index, "STOPPED"))
        integer(frame["index"], index, index)
        integer(frame["targetMilliseconds"], TARGET_MILLISECONDS[index], TARGET_MILLISECONDS[index])
        integer(frame["observedMilliseconds"], -1, 900000)
        integer(frame["errno"], 0, 4095)
        integer(frame["candidateCount"], 0, PID_LIMIT)
        require(frame["reason"] in REASONS and frame["image"] in IMAGES, "FRAME_ENUM")
        if frame["outcome"] == "OBSERVED":
            require(value["armedEpochMicroseconds"] is not None and base["reason"] == "NONE" and
                    frame["reason"] == "NONE" and frame["errno"] == 0 and
                    frame["candidateCount"] == 1 and frame["image"] != "UNKNOWN", "OBSERVED")
            require(TARGET_MILLISECONDS[index] <= frame["observedMilliseconds"] <=
                    TARGET_MILLISECONDS[index] + int(FRAME_SECONDS * 1000), "FRAME_TIME")
            before, after = validate_identity(frame["identity"]), validate_identity(frame["recheck"])
            require(stable(before, after) and eligible(before, base["controller"], value["armedEpochMicroseconds"], baseline)
                    and eligible(after, base["controller"], value["armedEpochMicroseconds"], baseline), "OWNED_RECHECK")
            require(latched is None or lifetime(after) == latched, "LIFETIME_CHANGED")
            latched = lifetime(after)
            integer(frame["status"], 1, 4)
            require(frame["status"] == after["status"], "STATUS")
        else:
            require(frame["outcome"] == "UNKNOWN" and frame["reason"] != "NONE" and frame["image"] == "UNKNOWN"
                    and type(frame["status"]) is int and frame["status"] == 0 and frame["identity"] is None
                    and frame["recheck"] is None, "UNKNOWN")
    return value


def project_observations(value):
    validate_observations(value)
    return {"observerStarted": value["observerStarted"], "observerFinished": value["observerFinished"],
            "baselineReason": value["baseline"]["reason"], "baselineErrno": value["baseline"]["errno"],
            "frames": [{key: frame[key] for key in ("index", "targetMilliseconds", "observedMilliseconds",
                        "outcome", "reason", "errno", "image", "status")} for frame in value["frames"]]}


class ObservationFailure(Exception):
    def __init__(self, reason, error=0):
        self.reason = reason if reason in REASONS else "OBSERVER_FAILED"
        self.error = error if type(error) is int and 0 <= error <= 4095 else 0
        super().__init__(self.reason)


class ReadOnlyProcesses:
    """libproc reads only. Do not instantiate DarwinScope or acquire signaling/task rights."""
    def __init__(self):
        self.types = GATE.audit_processes
        if tuple(ctypes.sizeof(kind) for kind in (self.types.DarwinBsdInfo, self.types.DarwinUniqueInfo,
                                                  self.types.DarwinIdentity)) != (136, 56, 192):
            raise ObservationFailure("ABI_INVALID")
        try:
            self.proc = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
            self.proc.proc_pidinfo.argtypes = [self.types.I32, self.types.I32, self.types.U64,
                                               self.types.PTR, self.types.I32]
            self.proc.proc_pidinfo.restype = self.types.I32
            self.proc.proc_listallpids.argtypes = [self.types.PTR, self.types.I32]
            self.proc.proc_listallpids.restype = self.types.I32
        except (OSError, AttributeError):
            raise ObservationFailure("API_UNAVAILABLE") from None

    def identity(self, pid, permitted=None):
        raw = self.types.DarwinIdentity()
        ctypes.set_errno(0)
        got = self.proc.proc_pidinfo(pid, 18, 1, ctypes.byref(raw), ctypes.sizeof(raw))
        if got == 0:
            code = ctypes.get_errno()
            if code in (errno.ESRCH, errno.ENOENT):
                return None, "UNKNOWN"
            raise ObservationFailure("IDENTITY_DENIED" if code in (errno.EACCES, errno.EPERM)
                                     else "IDENTITY_UNAVAILABLE", code)
        if got != ctypes.sizeof(raw) or raw.bsd.pid != pid:
            raise ObservationFailure("ABI_INVALID")
        row = {"pid": raw.bsd.pid, "uid": raw.bsd.uid, "parentPid": raw.bsd.ppid, "group": raw.bsd.pgid,
               "uniqueId": raw.unique.uniqueid, "parentUniqueId": raw.unique.parentuniqueid,
               "pidVersion": raw.unique.pidversion, "parentPidVersion": raw.unique.parentpidversion,
               "startSeconds": raw.bsd.startsec, "startMicroseconds": raw.bsd.startusec, "status": raw.bsd.status}
        # Unrelated kernel/launchd identities may contain zero fields; discard them
        # before full candidate validation, without reading either name field.
        if row["uid"] != os.geteuid() or (pid != os.getpid() and row["parentPid"] != os.getpid()):
            return None, "UNKNOWN"
        try:
            validate_identity(row)
        except ValueError:
            raise ObservationFailure("IDENTITY_INVALID") from None
        image = closed_image(bytes(raw.bsd.comm), bytes(raw.bsd.name)) if permitted is not None and permitted(row) else "UNKNOWN"
        return row, image

    def census(self, deadline):
        count = self.proc.proc_listallpids(None, 0)
        if not 0 < count <= PID_LIMIT:
            raise ObservationFailure("CENSUS_LIMIT")
        capacity = min(count + 128, PID_LIMIT)
        data = (self.types.I32 * capacity)()
        got = self.proc.proc_listallpids(data, ctypes.sizeof(data))
        if not 0 < got < capacity:
            raise ObservationFailure("CENSUS_INVALID")
        raw_pids = [int(data[index]) for index in range(got)]
        # PID0 is the kernel, not a candidate; match the maintained Darwin census.
        pids = [pid for pid in raw_pids if pid > 0]
        if any(pid < 0 for pid in raw_pids) or len(set(pids)) != len(pids):
            raise ObservationFailure("CENSUS_INVALID")
        rows = []
        for pid in pids:
            if time.monotonic() >= deadline:
                raise ObservationFailure("WORK_LIMIT")
            row, _image = self.identity(pid)
            if row is not None:
                rows.append(row)
        return rows


class Observer:
    """At most one baseline and four frames; immutable publications and no file writes."""
    def __init__(self):
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.armed = threading.Event()
        self.frames = queue.Queue(maxsize=4)
        self.baseline = None
        self.arm_data = None
        self.started = False
        self.thread = threading.Thread(target=self._work, name="owned-runtime-metadata", daemon=True)

    def start_and_arm(self):
        self.thread.start()
        self.started = True
        accepted = self.ready.wait(BASELINE_SECONDS)
        # Different clocks: process birth is epoch microseconds; scheduling is monotonic.
        self.arm_data = (time.time_ns() // 1000, time.monotonic(), accepted)
        self.armed.set()

    def _work(self):
        if self.stop.is_set():
            self.ready.set()
            return
        native, controller, baseline = None, None, []
        reason, error = "NONE", 0
        try:
            deadline = time.monotonic() + BASELINE_SECONDS
            native = ReadOnlyProcesses()
            controller, _image = native.identity(os.getpid())
            if controller is None or controller["status"] == 5:
                raise ObservationFailure("CONTROLLER_CHANGED")
            rows = native.census(deadline)
            baseline = [lifetime(row) for row in rows if row["parentPid"] == controller["pid"]]
            if len(baseline) > BASELINE_CHILD_LIMIT or time.monotonic() >= deadline:
                raise ObservationFailure("BASELINE_FAILED")
        except ObservationFailure as failure:
            reason, error = failure.reason, failure.error
        except Exception:
            reason = "OBSERVER_FAILED"
        if reason != "NONE":
            controller, baseline = None, []
        self.baseline = encoded({"reason": reason, "errno": error, "controller": controller, "children": baseline})
        self.ready.set()
        if not self.armed.wait(BASELINE_SECONDS) or self.stop.is_set():
            return
        epoch_us, began, accepted = self.arm_data
        latched = None
        for index, target in enumerate(TARGET_MILLISECONDS):
            if self.stop.wait(max(0.0, began + target / 1000 - time.monotonic())):
                return
            elapsed = int((time.monotonic() - began) * 1000)
            if not accepted:
                frame = unknown_frame(index, "BASELINE_UNFINISHED", elapsed)
            elif reason != "NONE":
                frame = unknown_frame(index, "BASELINE_FAILED", elapsed, error)
            else:
                frame, latched = self._frame(native, controller, baseline, epoch_us, began, index, latched)
            if self.stop.is_set():
                return
            self.frames.put_nowait(encoded(frame))

    def _frame(self, native, controller, baseline, epoch_us, began, index, latched):
        target = TARGET_MILLISECONDS[index]
        deadline = began + target / 1000 + FRAME_SECONDS
        observed = int((time.monotonic() - began) * 1000)
        try:
            if time.monotonic() >= deadline:
                raise ObservationFailure("LATE")
            current, _ = native.identity(controller["pid"])
            if current is None or not stable(controller, current) or current["status"] == 5:
                raise ObservationFailure("CONTROLLER_CHANGED")
            rows = native.census(deadline)
            if time.monotonic() >= deadline:
                raise ObservationFailure("WORK_LIMIT")
            child, reason, count = choose_child(rows, controller, epoch_us, baseline, latched)
            if child is None:
                return unknown_frame(index, reason, observed, count=count), latched
            owned = lifetime(child)
            # Latch before rechecking: an unstable/vanished candidate cannot be replaced later.
            latched = owned
            def permitted(row):
                return eligible(row, controller, epoch_us, baseline) and lifetime(row) == owned
            before, image = native.identity(child["pid"], permitted)
            after, next_image = native.identity(child["pid"], permitted)
            final_controller, _ = native.identity(controller["pid"])
            if final_controller is None or not stable(controller, final_controller) or final_controller["status"] == 5:
                raise ObservationFailure("CONTROLLER_CHANGED")
            if before is None or after is None or not permitted(before) or not permitted(after):
                raise ObservationFailure("REPLACED")
            if not stable(before, after) or image != next_image:
                raise ObservationFailure("EXEC_CHANGED")
            if time.monotonic() >= deadline:
                raise ObservationFailure("WORK_LIMIT")
            return {"index": index, "targetMilliseconds": target, "observedMilliseconds": observed,
                    "outcome": "OBSERVED", "reason": "NONE", "errno": 0, "candidateCount": 1,
                    "image": image, "status": after["status"], "identity": before, "recheck": after}, latched
        except ObservationFailure as failure:
            return unknown_frame(index, failure.reason, observed, failure.error), latched
        except Exception:
            return unknown_frame(index, "OBSERVER_FAILED", observed), latched

    def finish(self):
        self.stop.set()
        # start() can be interrupted after the native thread exists but before
        # returning. Its retained Thread handle, not the assignment alone, matters.
        started = self.started or self.thread.ident is not None
        if started:
            self.thread.join(JOIN_SECONDS)
        finished = started and not self.thread.is_alive()
        epoch_us, _began, accepted = self.arm_data or (None, None, False)
        base = json.loads(self.baseline) if accepted and self.baseline is not None else {
            "reason": "BASELINE_UNFINISHED", "errno": 0, "controller": None, "children": []}
        completed = {}
        for _ in range(4):
            try:
                frame = json.loads(self.frames.get_nowait())
            except queue.Empty:
                break
            completed[frame["index"]] = frame
        frames = [completed.get(i, unknown_frame(i, "STOPPED" if finished else "OBSERVER_UNFINISHED")) for i in range(4)]
        result = {"schema": 1, "scope": SCOPE, "qualification": False, "armedEpochMicroseconds": epoch_us,
                  "observerStarted": started, "observerFinished": finished, "baseline": base, "frames": frames}
        validate_observations(result)
        return result


def capture_runtime(directory, publications):
    """Observer failures never suppress/retry the command or replace its primary exception."""
    observer, setup_failed = None, False
    try:
        try:
            observer = Observer()
            observer.start_and_arm()
        except Exception:
            setup_failed = True
            if observer is not None:
                observer.stop.set()
        # An interrupt is not an observer failure: finally stops it and propagates
        # the interrupt without forcing a new command. Ordinary errors do not block it.
        return GATE._intel_capture_phase(directory, PHASES[-1], list(GATE.simulator.COMMANDS[PHASES[-1]]))
    finally:
        primary = sys.exc_info()[1]
        observation_error = None
        try:
            if observer is not None:
                observer.stop.set()
            result = None if observer is None else observer.finish()
        except BaseException as failure:
            observation_error = failure
            result = None
        if result is None or setup_failed:
            # Never synthesize an arming time when construction/arming did not finish.
            armed = None if observer is None else observer.arm_data
            started = observer is not None and (observer.started or observer.thread.ident is not None)
            result = {"schema": 1, "scope": SCOPE, "qualification": False,
                "armedEpochMicroseconds": None if armed is None else armed[0],
                "observerStarted": started, "observerFinished": False,
                "baseline": {"reason": "OBSERVER_FAILED", "errno": 0, "controller": None, "children": []},
                "frames": [unknown_frame(i, "OBSERVER_FAILED") for i in range(4)]}
        publications.append(encoded(result))
        if primary is None and observation_error is not None and not isinstance(observation_error, Exception):
            raise observation_error


def read_file(path, limit, allow_empty=False):
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        meta = os.fstat(stream.fileno())
        require(stat.S_ISREG(meta.st_mode) and meta.st_uid == os.geteuid() and
                (0 if allow_empty else 1) <= meta.st_size <= limit, "FILE")
        raw = stream.read(limit + 1)
        require(len(raw) == meta.st_size, "FILE_CHANGED")
    return raw


def phase_originals(evidence, label, row):
    raw = read_file(evidence / label / "result.json", JSON_LIMIT)
    require(raw == encoded(row), "RESULT_CHANGED")
    streams, hashes = {}, {"result.json": digest(raw)}
    for name, limit in (("stdout", GATE.INTEL_STDOUT_LIMIT), ("stderr", GATE.INTEL_STDERR_LIMIT)):
        value = read_file(evidence / label / (name + ".bin"), limit, True)
        require(len(value) == row[name + "Bytes"] and digest(value) == row[name + "Sha256"], "STREAM_CHANGED")
        streams[name], hashes[name + ".bin"] = value, digest(value)
    return streams, hashes


def run():
    began = time.monotonic()
    end = began + 900
    os.umask(0o077)
    require(GATE.ROOT == ROOT and GATE.platform.system() == "Darwin" and
            GATE.architecture(GATE.platform.machine()) == "x64", "HOST")
    names = (*GATE.INTEL_GITHUB.values(), "GITHUB_WORKSPACE", "DEVELOPER_DIR", "GITHUB_EVENT_NAME",
             "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_ARCH", "ImageOS", "ImageVersion", "P2PKIT_DIAGNOSTIC_MODE")
    context = {name: os.environ.get(name) for name in names}
    require(all(type(v) is str and 0 < len(v) <= 4096 for v in context.values()) and
            context["GITHUB_ACTIONS"] == "true" and context["RUNNER_ENVIRONMENT"] == "github-hosted" and
            context["RUNNER_OS"] == "macOS" and context["RUNNER_ARCH"] == "X64" and
            context["GITHUB_REPOSITORY"] == "p2pKit/P2pKit" and context["GITHUB_JOB"] == "ios-x64" and
            context["GITHUB_EVENT_NAME"] == "workflow_dispatch" and context["P2PKIT_DIAGNOSTIC_MODE"] == "runtime-metadata" and
            context["GITHUB_REF"] == "refs/heads/work/foundation-native-frontier-20261007-CC4DEkbv" and
            context["DEVELOPER_DIR"] == "/Applications/Xcode_26.3.app/Contents/Developer" and
            Path(context["GITHUB_WORKSPACE"]).resolve() == ROOT and
            all(re.fullmatch(r"[1-9][0-9]*", context[k]) for k in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT")), "CONTEXT")
    source = GATE.source_state()
    GATE._intel_source(source)
    require(source["commit"] == context["GITHUB_SHA"], "SOURCE_SHA")
    require(GATE.ordinary_simulator_binding("ios-x64", "x64", source) is None, "ORDINARY_CONTEXT")
    inputs = {name: {"bytes": len(raw), "sha256": digest(raw)} for name in INPUTS
              for raw in [read_file(ROOT / name, 1024 * 1024)]}
    for rel in ("build", "build/reports", "build/reports/intel-simctl"):
        path = ROOT / rel
        path.mkdir(mode=0o700, exist_ok=True)
        require(path.resolve(strict=True) == path and path.stat().st_uid == os.geteuid(), "DIRECTORY")
    token = uuid.uuid4().hex
    evidence = ROOT / "build/reports/intel-simctl" / token
    evidence.mkdir(mode=0o700, exist_ok=False)
    GATE._intel_write(evidence / "source.json", encoded({"source": source, "context": context, "token": token,
                                                        "inputs": inputs, "qualification": False}))
    publications, phases, errors = [], {}, []
    runtime_validated = False
    started = datetime.now(timezone.utc).isoformat()
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt()
    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    label = PHASES[0]
    try:
        for label in PHASES:
            require(time.monotonic() + 140 + BASELINE_SECONDS + JOIN_SECONDS <= end, "CONTROLLER_WINDOW")
            row = capture_runtime(evidence, publications) if label == PHASES[-1] else \
                GATE._intel_capture_phase(evidence, label, list(GATE.simulator.COMMANDS[label]))
            streams, phases[label] = phase_originals(evidence, label, row)
            require(row["exitCode"] == 0 and row["timedOut"] is False and
                    row["outputLimitExceeded"] is False and row["ownedGroupDrained"] is True, "COMMAND_FAILED")
            GATE.simulator.original(label, "macos-x64", streams["stdout"])
            if label == PHASES[-1]:
                runtime_validated = True
    except KeyboardInterrupt:
        errors.append(label + ":INTERRUPTED")
    except Exception:
        errors.append(label + ":FAILED")
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            observation_hash = None
            if publications:
                require(len(publications) == 1, "PUBLICATIONS")
                observations = validate_observations(json.loads(publications[0]))
                GATE._intel_write(evidence / "observations.json", publications[0])
                observation_hash = digest(publications[0])
            else:
                observations = None
            try:
                require(GATE.source_state() == source and context == {name: os.environ.get(name) for name in names}, "CONTEXT_CHANGED")
                require(all({"bytes": len(raw), "sha256": digest(raw)} == inputs[name] for name in INPUTS
                            for raw in [read_file(ROOT / name, 1024 * 1024)]), "INPUT_CHANGED")
            except Exception:
                errors.append("SOURCE_OR_CONTEXT_CHANGED")
            result = {"schema": 1, "scope": SCOPE, "qualification": False, "gradleLaunched": False,
                      "simulatorBootAttempted": False, "source": source, "context": context, "token": token,
                      "startedUtc": started, "finishedUtc": datetime.now(timezone.utc).isoformat(),
                      "runtimeValidated": runtime_validated, "phases": phases,
                      "observationsSha256": observation_hash, "errors": errors}
            GATE._intel_write(evidence / "summary.json", encoded(result))
            safe = {"schema": 1, "scope": SCOPE, "qualification": False, "sourceSha": source["commit"],
                    "runId": context["GITHUB_RUN_ID"], "attempt": context["GITHUB_RUN_ATTEMPT"],
                    "runtimeValidated": runtime_validated, "errors": errors,
                    "observations": None if observations is None else project_observations(observations)}
            print(MARKER + encoded(safe).decode("ascii").rstrip("\n"), flush=True)
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    return 0 if runtime_validated and not errors else 1


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception:
        print("P2PKIT_SIMCTL_RUNTIME_METADATA_DIAGNOSTIC_FAILED", flush=True)
        sys.exit(1)
