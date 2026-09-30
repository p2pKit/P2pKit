#!/usr/bin/env python3
"""Four offline startup-diagnostic controls; no native cause or custody claim.

Only current service/READY/capsule/abort/main functions execute, against bounded
memory endpoints under a no-process/network/write audit fence. Historical
preimages are text/AST assertions only, never compiled, imported or executed.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-startup-diagnostic-test.py
"""
import ast
import contextlib
import copy
import ctypes  # Preload the standard module before the no-native audit fence.
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
INVERSE = ROOT / "scripts/tests/hosted_darwin_context_clock_inverse.py"
METHODS = (
    "test_01_actual_service_sites_ready_and_unwind",
    "test_02_finite_capsule_buffer_and_hostile_inputs",
    "test_03_actual_abort_main_terminal_gate_and_primary",
    "test_04_exact_inverse_legacy_hunks_and_guard_mutations",
)
PREIMAGE = "fac1691819a7a201851fa4c6062f2f9d272d6ab7635c4b613746a88f58e50754"
BINDING = "a" * 64
CANARY = "SYNTHETIC_STARTUP_PRIVATE_CANARY"
PARENT = Path("/synthetic/startup-operation")
EVIDENCE = PARENT / "evidence"
PRIMARY = "P2PKIT_CONTEXT_FAILURE|START|STATUS_MISSING|NONE"
RECORD_PREFIX = b"P2PKIT_CONTEXT_STARTUP_RECORD|"
SERVICE_PREFIX = "P2PKIT_CONTEXT_SERVICE_FAILURE|"
REPORTED_PREFIX = "P2PKIT_CONTEXT_SERVICE_REPORTED_P_FAILURE|"
SITES = (
    "PREPARE_READ", "PREPARE_VALIDATE", "CHILD_CHANNEL", "CHILD_ENVIRONMENT", "CHILD_SPAWN",
    "CHILD_IDENTITY", "CHILD_PIPES", "CHILD_READY_READ", "CHILD_READY_VALIDATE", "CHILD_RECHECK",
    "CHILD_READY_FORWARD",
)
READY = ("READY_SHAPE", "READY_ACCOUNT", "READY_PARENT", "READY_PRODUCER", "READY_BINDINGS")
ABSENT = object()


def offline(event, args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid", "os.chmod",
        "os.mkdir", "os.rmdir", "os.remove", "os.rename", "os.link", "os.symlink", "os.truncate",
    }:
        raise AssertionError("OFFLINE_STARTUP_FORBIDDEN_OPERATION")
    if event == "open":
        name, mode, flags = args
        if (type(mode) is str and any(value in mode for value in "wax+") or
                type(flags) is int and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND) or
                type(name) is str and name.startswith(str(PARENT))):
            raise AssertionError("OFFLINE_STARTUP_FORBIDDEN_FILE_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_STARTUP_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_startup_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
inverse_spec = importlib.util.spec_from_file_location("darwin_context_startup_inverse", INVERSE)
CLOCK = importlib.util.module_from_spec(inverse_spec)
inverse_spec.loader.exec_module(CLOCK)


class Hostile:
    def forbidden(self, *_args, **_kwargs):
        raise AssertionError("UNTRUSTED_STARTUP_VALUE_OPERATION")
    __str__ = __repr__ = __bool__ = __len__ = __hash__ = __eq__ = __int__ = __index__ = forbidden


class StringSubclass(str):
    pass


class BytesSubclass(bytes):
    pass


class IntegerSubclass(int):
    pass


class ListSubclass(list):
    pass


class DictSubclass(dict):
    pass


class ErrorSubclass(M.ExperimentError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def identity(pid, parent):
    return dict(pid=pid, parentPid=parent, uniqueId=pid * 10, parentUniqueId=parent * 10, pidVersion=1,
                startSeconds=1, startMicroseconds=0, uid=501, realUid=501, gid=20, realGid=20, status=1)


def account():
    return dict(uid=501, euid=501, gid=20, egid=20, groups=[20])


def prepared_fixture(case="N1"):
    interpreter = dict(path=str(PARENT / "python"), sha256="c" * 64, size=1, stat=[1, 2])
    source_raw = b"SYNTHETIC_STARTUP_SOURCE_INPUT\n"
    source = dict(commit="d" * 40, tree="e" * 40, files={M.SCRIPT: hashlib.sha256(source_raw).hexdigest()})
    github = dict(repository=M.REPOSITORY, workflow=M.WORKFLOW, job="context_experiment", runId="123", runAttempt="1",
                  source=source["commit"], sourceTree=source["tree"])
    allocation = dict(schema=2, clockDomain="darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)", source=source["commit"],
                      sourceTree=source["tree"], runId="123", runAttempt="1", startedMonotonicNs=1, startedEpochNs=1)
    foreground, service, producer = identity(101, 1), identity(202, 1), identity(303, 202)
    prepared = dict(schema=1, binding=BINDING, case=case, github=github, allocation=allocation, source=source,
                    account=account(), foreground=foreground, boot="11111111-2222-3333-4444-555555555555",
                    interpreter=interpreter, directoryIdentity=[11, 33], operationIdentity=[11, 22],
                    socketIdentity=[11, 44], caseEndNs=40 * M.NS, stepEndNs=720 * M.NS, jobEndNs=1440 * M.NS)
    ready = M.frame_value(3, BINDING, dict(producer=copy.deepcopy(producer), parent=copy.deepcopy(service),
        account=account(), sigtermDefault=True, sigtermBlocked=False, sourceSha256=source["files"][M.SCRIPT],
        boot=prepared["boot"], interpreter=interpreter["path"]))
    return types.SimpleNamespace(prepared=prepared, ready=ready, service=service, producer=producer,
                                 foreground=foreground, interpreter=interpreter, source_raw=source_raw)


def capsule_fixture(*, case="N1", failure=None, site="CHILD_READY_READ", ready="NONE", producer=True):
    return dict(schema=1, case=case, binding=BINDING, site=site, ready=ready,
                failure=["START", "STATUS_MISSING", "NONE"] if failure is None else failure,
                timeout=None, eof=["F3", "HEADER", "EMPTY"] if failure is None else None,
                producerFailure=["IDENTITY", "IDENTITY_CHANGED", "NONE"] if producer else None)


def capsule_bytes(value):
    primary = ("P2PKIT_CONTEXT_FAILURE|" + "|".join(value["failure"]) + "\n").encode("ascii")
    return primary + RECORD_PREFIX + canonical(value)


def buffered(raw):
    pipes = M.ProbePipes.__new__(M.ProbePipes)
    pipes.data = {"stdout": raw, "stderr": Hostile()}
    pipes.pump = Mock(side_effect=AssertionError("NO_DIAGNOSTIC_PUMP"))
    pipes.finish = Mock(side_effect=AssertionError("NO_DIAGNOSTIC_FINISH"))
    pipes.process = types.SimpleNamespace(poll=Mock(side_effect=AssertionError("NO_DIAGNOSTIC_POLL")),
                                          wait=Mock(side_effect=AssertionError("NO_DIAGNOSTIC_WAIT")))
    return pipes


class StartupDiagnostic(unittest.TestCase):
    def _safe(self, lines):
        self.assertIs(type(lines), tuple)
        self.assertLessEqual(len(lines), 4)
        for line in lines:
            self.assertIs(type(line), str)
            self.assertTrue(line.isascii())
            self.assertLessEqual(len(line), 192)
            self.assertNotIn("\n", line)
            self.assertNotIn(CANARY, line)
            self.assertNotIn(BINDING, line)
            self.assertNotIn(str(PARENT), line)

    def _guard_error(self, operation, ready):
        try:
            operation()
        except M.ExperimentError as error:
            held = error
            codes, trace = [], error.__traceback__
            while trace is not None:
                codes.append(trace.tb_frame.f_code)
                trace = trace.tb_next
            self.assertIs(codes[-1], M.require.__code__)
            self.assertEqual(codes.count(M.validate_ready.__code__), 1)
            self.assertIsNone(error.__context__)
        else:
            self.fail("ORIGINAL_READY_GUARD_DID_NOT_REFUSE")
        self.assertEqual(held.ready_site, ready)
        return held

    @contextlib.contextmanager
    def _service(self, fail=None, *, cleanup_error=None, record_error=False, write_error=False, normal=False):
        """Actual service, frames and READY; only native/IO/process endpoints are models."""
        fixture = prepared_fixture("N2")
        prepared, directory = fixture.prepared, EVIDENCE / "N2"
        state = types.SimpleNamespace(order=[], written=[], write_attempts=[], snapshots=[], selections=0,
                                      pipes=None, failure=M.ExperimentError("IDENTITY", "REFUSED"), fixture=fixture)
        state.failure.args = (CANARY,)
        if fail == "CHILD_READY_READ":
            state.failure = M.ExperimentError("START", "STATUS_MISSING")
            state.failure.protocol_eof = (3, "HEADER", "EMPTY")
        received = copy.deepcopy(prepared)
        if fail == "PREPARE_VALIDATE":
            received["caseEndNs"] += 1
        if fail == "CHILD_READY_VALIDATE":
            fixture.ready["payload"]["producer"]["pidVersion"] += 1
        start = dict(case="N2", account=account(), service=fixture.service, sourceSha256=prepared["source"]["files"][M.SCRIPT],
                     interface=None, deadlineNs=prepared["caseEndNs"])
        probe = dict(stage="NO_NETWORK", result="EXPECTED_FAILURE", errno="NONE", sent=0,
                     socketCreated=False, closed=False, closeError="NONE")
        observation = dict(startedMonotonicNs=M.NS, socketFd=None, sendStartedMonotonicNs=None,
                           sendFinishedMonotonicNs=None, sendReturn=None, closeStartedMonotonicNs=None,
                           closeReturnedMonotonicNs=None, closedFd=None, finishedMonotonicNs=M.NS)

        def packet(serial, payload):
            raw = canonical(M.frame_value(serial, BINDING, payload))
            return struct.pack("!I", len(raw)) + raw

        def stop(site):
            state.order.append(site)
            if fail == site:
                raise state.failure

        class Channel:
            def __init__(channel, role, fd, packets=()):
                channel.role, channel.fd, channel.packets = role, fd, list(packets)
                channel.pending, channel.sent = b"", []

            def fileno(channel):
                return channel.fd

            def settimeout(channel, timeout):
                self.assertEqual((channel.role, timeout), ("F", 39.0))

            def connect(channel, path):
                self.assertEqual((channel.role, path), ("F", str(directory / "control.sock")))

            def setblocking(channel, value):
                self.assertIs(value, False)
                if channel.role == "P":
                    stop("CHILD_SETBLOCKING")

            def close(channel):
                state.order.append("close:" + channel.role)
                if channel.role == "C" and cleanup_error is not None:
                    raise cleanup_error
                channel.fd = -1

            def send(channel, raw):
                raw = bytes(raw)
                self.assertGreaterEqual(len(raw), 4)
                self.assertEqual(struct.unpack("!I", raw[:4])[0], len(raw) - 4)
                value = json.loads(raw[4:].decode("ascii"))
                serial = value["serial"]
                state.order.append("send" + str(serial))
                if (fail == "BEFORE_STARTUP" and serial == 1 or fail == "CHILD_READY_FORWARD" and serial == 4):
                    raise state.failure
                channel.sent.append(value)
                return len(raw)

            def recvmsg(channel, count, space):
                self.assertEqual(space, socket.CMSG_SPACE(16))
                self.assertGreater(count, 0)
                self.assertLessEqual(count, M.FRAME_BYTES)
                if not channel.pending:
                    if not channel.packets:
                        state.order.append("eof:" + channel.role)
                        return b"", [], 0, None
                    serial, raw = channel.packets.pop(0)
                    state.order.append("read" + str(serial))
                    if (fail == "PREPARE_READ" and serial == 2 or fail == "CHILD_READY_READ" and serial == 3 or
                            not normal and serial == 5):
                        raise state.failure
                    channel.pending = raw
                result, channel.pending = channel.pending[:count], channel.pending[count:]
                return result, [], 0, None

        foreground = state.channel = Channel("F", 42, ((2, packet(2, received)), (5, packet(5, start))))
        producer = state.probe_channel = Channel("P", 43, ((3, packet(3, fixture.ready["payload"])),
            (7, packet(7, dict(case="N2", probe=probe, observation=observation)))))
        child = state.child_channel = Channel("C", 44)
        native = state.native = types.SimpleNamespace(closed=False, signals=[])
        captures = state.captures = types.SimpleNamespace(closed=False)
        process = state.process = types.SimpleNamespace(pid=303)

        def native_identity(pid):
            if pid == 303:
                stop("CHILD_IDENTITY")
                return fixture.producer
            self.assertEqual(pid, 202)
            return fixture.service

        def native_same(value):
            if value["pid"] == 303:
                stop("CHILD_RECHECK")
                expected = fixture.producer
            else:
                state.order.append("foreground-recheck")
                expected = fixture.foreground
            return M.same_identity(value, expected)

        def signal_child(value, signum, end):
            self.assertEqual((value, signum, end), (fixture.producer, signal.SIGTERM, prepared["caseEndNs"]))
            state.order.append("cleanup-signal")

        def close_native():
            state.order.append("native-close")
            native.closed = True

        def close_capture():
            state.order.append("capture-close")
            captures.closed = True
            return []

        def process_poll():
            state.order.append("cleanup-poll")
            return None

        native.identity, native.same = native_identity, native_same
        native.peer, native.boot = lambda _channel: fixture.foreground, lambda: prepared["boot"]
        native.signal, native.close = signal_child, close_native
        captures.check, captures.close = lambda: state.order.append("capture-check"), close_capture
        process.poll = process_poll

        def pair(family, kind):
            self.assertEqual((family, kind), (socket.AF_UNIX, socket.SOCK_STREAM))
            stop("CHILD_CHANNEL")
            return producer, child

        original_environment = M.child_environment

        def environment(parent):
            self.assertEqual(parent, directory)
            stop("CHILD_ENVIRONMENT")
            return original_environment(parent)

        def popen(argv, **kwargs):
            state.order.append("CHILD_SPAWN")
            expected_env = original_environment(directory)
            expected_env.update(P2PKIT_CONTEXT_BINDING=BINDING, P2PKIT_CONTEXT_CASE_END_NS=str(prepared["caseEndNs"]),
                                P2PKIT_CONTEXT_CLOCK_SCHEMA="2", P2PKIT_CONTEXT_CLOCK_DOMAIN=M.CLOCK_DOMAIN)
            self.assertEqual(argv, [fixture.interpreter["path"], "-I", "-B", "-S", str(ROOT / M.SCRIPT), "_probe", "44"])
            self.assertEqual(kwargs, dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          close_fds=True, pass_fds=(44,), cwd=ROOT, env=expected_env))
            if fail == "CHILD_SPAWN":
                raise state.failure
            return process

        def pipes_init(pipes, actual):
            self.assertIs(actual, process)
            stop("CHILD_PIPES")
            state.pipes = pipes
            pipes.process, pipes.closed, pipes.active = process, False, []
            pipes.data = {"stdout": bytearray(b"P2PKIT_CONTEXT_FAILURE|IDENTITY|IDENTITY_CHANGED|NONE\n"),
                          "stderr": bytearray(CANARY.encode("ascii"))}

        def pump(pipes):
            self.assertIs(pipes, state.pipes)
            state.order.append("pump")

        def finish(pipes, end, destination):
            self.assertEqual((end, destination), (prepared["caseEndNs"], directory))
            state.order.append("cleanup-finish" if not normal else "finish")
            pipes.closed = True
            pipes.data["stdout"] = bytearray(CANARY.encode("ascii"))  # Must not replace the earlier snapshot.
            return 23, []

        def read_file(path, limit=M.STREAM_BYTES):
            if path == directory / "prepared.json":
                return canonical(prepared)
            self.assertEqual((path, limit), (ROOT / M.SCRIPT, M.EVIDENCE_BYTES))
            return fixture.source_raw

        def private_directory(path, **kwargs):
            self.assertFalse(kwargs)
            self.assertIn(path, (directory, PARENT))
            return [11, 33] if path == directory else [11, 22]

        def select(read, write, exceptional, timeout):
            state.selections += 1
            self.assertLessEqual(state.selections, 64, "BOUNDED_MEMORY_SERVICE_SELECTS")
            self.assertEqual(exceptional, [])
            self.assertTrue((len(read) == 1 and write == []) or (len(write) == 1 and read == []))
            self.assertIn((read or write)[0], (foreground, producer))
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 0.05)
            return read, write, []

        original_record = M.startup_failure_record

        def record(*args):
            state.order.append("snapshot")
            state.snapshots.append(args)
            if record_error:
                raise RuntimeError(CANARY)
            return original_record(*args)

        def write(fd, raw):
            self.assertEqual(fd, 2)
            self.assertIs(type(raw), bytes)
            state.write_attempts.append(raw)
            state.order.append("companion-write" if raw.startswith(RECORD_PREFIX) else "primary-write")
            if write_error and raw.startswith(RECORD_PREFIX):
                raise OSError(CANARY)
            state.written.append(raw)
            return len(raw)

        with contextlib.ExitStack() as stack:
            for owner, name, kwargs in (
                (M, "physical", dict(side_effect=lambda value: Path(value))),
                (M, "private_directory", dict(side_effect=private_directory)),
                (M, "account", dict(side_effect=account)),
                (M, "ServiceCaptures", dict(return_value=captures)),
                (M, "Darwin", dict(return_value=native)),
                (M, "read_file", dict(side_effect=read_file)),
                (M, "checked_interpreter", dict(return_value=fixture.interpreter)),
                (M, "socket_identity", dict(return_value=prepared["socketIdentity"])),
                (M, "shared_raw_ns", dict(return_value=M.NS)),
                (M, "child_environment", dict(side_effect=environment)),
                (M, "startup_failure_record", dict(side_effect=record)),
                (M.socket, "socket", dict(return_value=foreground)),
                (M.socket, "socketpair", dict(side_effect=pair)),
                (M.select, "select", dict(side_effect=select)),
                (M.subprocess, "Popen", dict(side_effect=popen)),
                (M.ProbePipes, "__init__", dict(autospec=True, side_effect=pipes_init)),
                (M.ProbePipes, "pump", dict(autospec=True, side_effect=pump)),
                (M.ProbePipes, "finish", dict(autospec=True, side_effect=finish)),
                (M.os, "getpid", dict(return_value=202)),
                (M.os, "getuid", dict(return_value=501)),
                (M.os, "write", dict(side_effect=write)),
            ):
                stack.enter_context(patch.object(owner, name, **kwargs))
            stack.enter_context(patch.object(M.os, "environ", {}))
            yield state

    def test_01_actual_service_sites_ready_and_unwind(self):
        self.assertEqual(M.STARTUP_SITES, frozenset(SITES))
        self.assertEqual(M.READY_SITES, frozenset(READY))
        for site in (*SITES, "CHILD_SETBLOCKING"):
            with self.subTest(site=site), self._service(site) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.service(EVIDENCE / "N2")
                error = raised.exception
                self.assertEqual(len(state.snapshots), 1)
                args = state.snapshots[0]
                self.assertIs(args[0], error)
                self.assertEqual(args[1:4], ("N2", BINDING, "CHILD_CHANNEL" if site == "CHILD_SETBLOCKING" else site))
                self.assertIs(args[4], state.pipes)
                if site not in ("PREPARE_VALIDATE", "CHILD_READY_VALIDATE"):
                    self.assertIs(error, state.failure)
                self.assertEqual(len(state.written), 2)
                self.assertEqual(state.written[0], (M.public_error(error) + "\n").encode("ascii"))
                self.assertTrue(state.written[1].startswith(RECORD_PREFIX))
                lines = M.parse_startup_record(b"".join(state.written), "N2", BINDING)
                self._safe(lines)
                detail = "READY_PRODUCER" if site == "CHILD_READY_VALIDATE" else "NONE"
                expected = SERVICE_PREFIX + "|".join(("N2", args[3], detail, error.stage, error.reason, error.errno_name))
                self.assertEqual(lines[0], expected)
                self.assertEqual(any(line.startswith(REPORTED_PREFIX) for line in lines), state.pipes is not None)
                if state.pipes is not None:
                    self.assertIn(REPORTED_PREFIX + "N2|IDENTITY|IDENTITY_CHANGED|NONE", lines)
                    self.assertEqual(state.pipes.data["stdout"], bytearray(CANARY.encode("ascii")))
                if "cleanup-poll" in state.order:
                    self.assertLess(state.order.index("snapshot"), state.order.index("cleanup-poll"))
                if "cleanup-finish" in state.order:
                    self.assertLess(state.order.index("snapshot"), state.order.index("cleanup-finish"))
                self.assertLess(state.order.index("primary-write"), state.order.index("companion-write"))
                self.assertLess(state.order.index("companion-write"), state.order.index("native-close"))
                self.assertLess(state.order.index("native-close"), state.order.index("capture-close"))
                self.assertTrue(state.native.closed and state.captures.closed)
                self.assertEqual(state.channel.fileno(), -1)
                self.assertEqual(sum(value["serial"] == 8 for value in state.channel.sent), 0)
                if site in ("CHILD_ENVIRONMENT", "CHILD_SPAWN", "CHILD_IDENTITY", "CHILD_PIPES"):
                    self.assertLess(state.order.index("close:C"), state.order.index("snapshot"))
                    self.assertEqual(state.child_channel.fileno(), -1)
                if site == "CHILD_IDENTITY":
                    self.assertNotIn("cleanup-signal", state.order)  # An unknown P is not adopted.

        # Before F2 and after returned F4, the ordinary failure path has no capsule.
        for site in ("BEFORE_STARTUP", "AFTER_STARTUP"):
            with self.subTest(inactive=site), self._service(site) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.service(EVIDENCE / "N2")
                self.assertIs(raised.exception, state.failure)
                self.assertEqual(state.snapshots, [])
                self.assertEqual(state.written, [(M.public_error(state.failure) + "\n").encode("ascii")])
                self.assertTrue(state.native.closed and state.captures.closed)
        with self._service(normal=True) as state:
            self.assertEqual(M.service(EVIDENCE / "N2"), 23)
            self.assertEqual(state.snapshots, [])
            self.assertEqual(state.written, [])
            self.assertEqual([row["serial"] for row in state.channel.sent], [1, 4, 8])
            self.assertEqual([row["serial"] for row in state.probe_channel.sent], [6])
            self.assertTrue(state.native.closed and state.captures.closed and state.pipes.closed)
            self.assertLess(state.order.index("capture-close"), state.order.index("send8"))

        # Python's original child-copy-finally precedence wins over the earlier
        # environment failure. A successful finally, tested above, preserves it.
        cleanup = M.ExperimentError("CLOSE", "RESOURCE_UNKNOWN")
        with self._service("CHILD_ENVIRONMENT", cleanup_error=cleanup) as state:
            with self.assertRaises(M.ExperimentError) as raised:
                M.service(EVIDENCE / "N2")
            self.assertIs(raised.exception, cleanup)
            self.assertIs(cleanup.__context__, state.failure)
            self.assertIs(state.snapshots[0][0], cleanup)
            self.assertEqual(state.snapshots[0][3], "CHILD_CHANNEL")
            self.assertEqual(state.written[0], b"P2PKIT_CONTEXT_FAILURE|CLOSE|RESOURCE_UNKNOWN|NONE\n")
        for options in ({"record_error": True}, {"write_error": True}):
            with self.subTest(diagnostic_failure=tuple(options)), self._service("CHILD_READY_READ", **options) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.service(EVIDENCE / "N2")
                self.assertIs(raised.exception, state.failure)
                self.assertEqual(state.written, [(PRIMARY + "\n").encode("ascii")])
                self.assertEqual(len(state.snapshots), 1)
                self.assertEqual(sum(raw.startswith(RECORD_PREFIX) for raw in state.write_attempts),
                                 1 if options.get("write_error") else 0)
                self.assertTrue(state.native.closed and state.captures.closed and state.pipes.closed)

        base = prepared_fixture()
        self.assertIs(M.validate_ready(base.ready, base.prepared, base.service, base.producer), base.ready["payload"])
        base.ready["payload"]["producer"]["status"] = 3
        base.ready["payload"]["parent"]["status"] = 4
        self.assertIs(M.validate_ready(base.ready, base.prepared, base.service, base.producer), base.ready["payload"])

        def producer_change(value, key, changed):
            value.producer[key] = changed
            value.ready["payload"]["producer"][key] = changed

        mutations = (
            ("READY_SHAPE", lambda value: value.ready.update(binding="b" * 64)),
            ("READY_SHAPE", lambda value: value.ready["payload"].update(sigtermDefault=False)),
            ("READY_SHAPE", lambda value: value.ready["payload"].update(sigtermBlocked=True)),
            ("READY_SHAPE", lambda value: value.ready["payload"].update(unexpected=CANARY)),
            ("READY_ACCOUNT", lambda value: value.ready["payload"]["account"].update(groups=[20, 21])),
            ("READY_PARENT", lambda value: value.ready["payload"]["parent"].update(pidVersion=2)),
            ("READY_PRODUCER", lambda value: value.ready["payload"]["producer"].update(pidVersion=2)),
            ("READY_ACCOUNT", lambda value: producer_change(value, "realUid", 502)),
            ("READY_BINDINGS", lambda value: producer_change(value, "parentPid", 203)),
            ("READY_BINDINGS", lambda value: producer_change(value, "parentUniqueId", 2030)),
            ("READY_BINDINGS", lambda value: value.ready["payload"].update(sourceSha256="f" * 64)),
            ("READY_BINDINGS", lambda value: value.ready["payload"].update(boot=CANARY)),
            ("READY_BINDINGS", lambda value: value.ready["payload"].update(interpreter=CANARY)),
        )
        for index, (site, change) in enumerate(mutations):
            value = prepared_fixture()
            change(value)
            original = copy.deepcopy(value.__dict__)
            with self.subTest(ready_guard=index):
                error = self._guard_error(lambda: M.validate_ready(value.ready, value.prepared, value.service, value.producer), site)
                self.assertEqual(value.__dict__, original)
                error.private_context = CANARY
                record = M.startup_failure_record(error, "N1", BINDING, "CHILD_READY_VALIDATE", None)
                self.assertTrue(record)
                lines = M.parse_startup_record((M.public_error(error) + "\n").encode("ascii") + record, "N1", BINDING)
                self._safe(lines)
                expected = (SERVICE_PREFIX + "|".join(("N1", "CHILD_READY_VALIDATE", site,
                            error.stage, error.reason, error.errno_name)),)
                if site == "READY_PRODUCER":
                    expected += ("P2PKIT_CONTEXT_SERVICE_READY_PRODUCER|N1|PAIR|EQUALITY|PID_VERSION",)
                self.assertEqual(lines, expected)

    def test_02_finite_capsule_buffer_and_hostile_inputs(self):
        self.assertEqual((M.STARTUP_BYTES, M.STARTUP_PREFIX), (2048, RECORD_PREFIX))
        value = capsule_fixture()
        raw = capsule_bytes(value)
        expected = (
            SERVICE_PREFIX + "N1|CHILD_READY_READ|NONE|START|STATUS_MISSING|NONE",
            "P2PKIT_CONTEXT_SERVICE_PROTOCOL_EOF|N1|F3|HEADER|EMPTY",
            REPORTED_PREFIX + "N1|IDENTITY|IDENTITY_CHANGED|NONE",
        )
        self.assertEqual(M.parse_startup_record(raw, "N1", BINDING), expected)
        self._safe(expected)
        eof = M.ExperimentError("START", "STATUS_MISSING")
        eof.protocol_eof, eof.args = (3, "HEADER", "EMPTY"), (CANARY,)
        pipes = buffered(bytearray(b"P2PKIT_CONTEXT_FAILURE|IDENTITY|IDENTITY_CHANGED|NONE\n"))
        with contextlib.ExitStack() as stack:
            endpoints = [stack.enter_context(patch.object(owner, name, side_effect=AssertionError("NO_CAPSULE_IO")))
                         for owner, name in ((M, "shared_raw_ns"), (M, "read_file"), (M.os, "read"),
                                             (M.os, "open"), (M.os, "write"), (M.subprocess, "Popen"))]
            companion = M.startup_failure_record(eof, "N1", BINDING, "CHILD_READY_READ", pipes)
            self.assertEqual(companion, RECORD_PREFIX + canonical(value))
            self.assertEqual(M.parse_startup_record((PRIMARY + "\n").encode("ascii") + companion, "N1", BINDING), expected)
            for endpoint in endpoints:
                endpoint.assert_not_called()
            for endpoint in (pipes.pump, pipes.finish, pipes.process.poll, pipes.process.wait):
                endpoint.assert_not_called()

        for case in M.CASES:
            for site in SITES:
                error = M.ExperimentError("IDENTITY", "REFUSED")
                error.args = (CANARY,)
                companion = M.startup_failure_record(error, case, BINDING, site, None)
                expected_value = capsule_fixture(case=case, failure=["IDENTITY", "REFUSED", "NONE"], site=site, producer=False)
                self.assertEqual(companion, RECORD_PREFIX + canonical(expected_value))
                self.assertLessEqual(len(companion) + len(M.public_error(error)) + 1, 2048)
                lines = M.parse_startup_record(capsule_bytes(expected_value), case, BINDING)
                self.assertEqual(lines, (SERVICE_PREFIX + "|".join((case, site, "NONE", "IDENTITY", "REFUSED", "NONE")),))
                self._safe(lines)
        for ready in READY:
            error = M.ExperimentError("IDENTITY", "IDENTITY_CHANGED")
            error.ready_site = ready
            companion = M.startup_failure_record(error, "N4", BINDING, "CHILD_READY_VALIDATE", None)
            self.assertTrue(companion)
            self.assertIn(("\"ready\":\"" + ready + "\"").encode("ascii"), companion)
            self.assertEqual(M.startup_failure_record(error, "N4", BINDING, "CHILD_SPAWN", None), b"")
        for case in M.CASES:
            error = M.ExperimentError("START", "TIMEOUT")
            error.timeout_site, error.timeout_case = ("READ_WAIT", 3, "BODY"), case
            companion = M.startup_failure_record(error, case, BINDING, "CHILD_READY_READ", None)
            lines = M.parse_startup_record((M.public_error(error) + "\n").encode("ascii") + companion, case, BINDING)
            self.assertEqual(lines, (SERVICE_PREFIX + case + "|CHILD_READY_READ|NONE|START|TIMEOUT|NONE",
                                    "P2PKIT_CONTEXT_SERVICE_TIMEOUT_SITE|" + case + "|READ_WAIT|F3|BODY"))
            self._safe(lines)
            other = "N2" if case == "N1" else "N1"
            self.assertEqual(M.startup_failure_record(error, other, BINDING, "CHILD_READY_READ", None), b"")
        eof.protocol_eof_case = "N3"
        self.assertEqual(M.startup_failure_record(eof, "N1", BINDING, "CHILD_READY_READ", None), b"")
        del eof.protocol_eof_case

        valid_reports = (
            b"P2PKIT_CONTEXT_FAILURE|PREPARE|REFUSED|UNKNOWN\n",
            b"P2PKIT_CONTEXT_FAILURE|SOURCE|IDENTITY_CHANGED|NONE\nP2PKIT_CONTEXT_SOURCE_SITE|PREPARED_SOURCE|NONE\n",
            b"P2PKIT_CONTEXT_FAILURE|SOURCE|IDENTITY_CHANGED|NONE\nP2PKIT_CONTEXT_SOURCE_SITE|OS_OWNER|USR_BIN\n",
            b"P2PKIT_CONTEXT_FAILURE|START|TIMEOUT|NONE\nP2PKIT_CONTEXT_TIMEOUT_SITE|UNKNOWN|READ_WAIT|F6|HEADER\n",
            b"P2PKIT_CONTEXT_FAILURE|START|STATUS_MISSING|NONE\nP2PKIT_CONTEXT_PROTOCOL_EOF|N1|F6|BODY|PARTIAL\n",
        )
        for raw_report in valid_reports:
            for buffer_type in (bytes, bytearray):
                pipes = buffered(buffer_type(raw_report))
                result = M.startup_failure_record(eof, "N1", BINDING, "CHILD_READY_READ", pipes)
                data = json.loads(result[len(RECORD_PREFIX):].decode("ascii"))
                self.assertEqual(data["producerFailure"], raw_report.decode("ascii").split("\n")[0].split("|")[1:])
                for endpoint in (pipes.pump, pipes.finish, pipes.process.poll, pipes.process.wait):
                    endpoint.assert_not_called()
        primary = valid_reports[0]
        bad_reports = (
            b"", primary[:-1], primary[:15], primary + b"\n", primary + primary,
            primary + CANARY.encode("ascii"), primary + CANARY.encode("ascii") + b"\n",
            primary.replace(b"\n", b"\r\n"), primary + b"\x00\n", primary + b"\xff\n",
            primary.replace(b"PREPARE", CANARY.encode("ascii")), primary.replace(b"REFUSED", b"UNRECOGNIZED"),
            primary.replace(b"UNKNOWN", CANARY.encode("ascii")), b"x" * 2048 + b"\n",
            primary + b"P2PKIT_CONTEXT_SOURCE_SITE|PREPARED_SOURCE|NONE\n",
            valid_reports[1] + valid_reports[1].split(b"\n")[1] + b"\n",
            valid_reports[2].replace(b"USR_BIN", CANARY.encode("ascii")),
            valid_reports[3].replace(b"UNKNOWN|READ_WAIT", b"N2|READ_WAIT"),
            valid_reports[3].replace(b"READ_WAIT", CANARY.encode("ascii")),
            valid_reports[3].replace(b"F6", b"F9"), valid_reports[3].replace(b"HEADER", b"PARTIAL"),
            valid_reports[4].replace(b"PARTIAL", CANARY.encode("ascii")),
            valid_reports[4] + b"P2PKIT_CONTEXT_TIMEOUT_SITE|N1|READ_WAIT|F6|BODY\n",
            primary + b"P2PKIT_CONTEXT_ADMIN_SITE|META_OWNER|PRIVATE_DIRECTORY\n",
            primary + b"P2PKIT_CONTEXT_EXPERIMENT_SUCCESS\n",
            None, [], {}, Hostile(), StringSubclass(primary.decode("ascii")), BytesSubclass(primary),
        )
        for index, raw_report in enumerate(bad_reports):
            with self.subTest(bad_buffer=index):
                pipes = buffered(raw_report)
                result = M.startup_failure_record(eof, "N1", BINDING, "CHILD_READY_READ", pipes)
                self.assertTrue(result, "UNAVAILABLE_P_MUST_NOT_SUPPRESS_D")
                data = json.loads(result[len(RECORD_PREFIX):].decode("ascii"))
                self.assertIsNone(data["producerFailure"])
                lines = M.parse_startup_record((PRIMARY + "\n").encode("ascii") + result, "N1", BINDING)
                self.assertEqual(lines, expected[:2])
                self._safe(lines)
                for endpoint in (pipes.pump, pipes.finish, pipes.process.poll, pipes.process.wait):
                    endpoint.assert_not_called()
        for data in (None, Hostile(), DictSubclass(stdout=primary), {"stderr": Hostile()}, {"stdout": Hostile()}):
            pipes = buffered(primary)
            pipes.data = data
            result = M.startup_failure_record(eof, "N1", BINDING, "CHILD_READY_READ", pipes)
            self.assertTrue(result)
            self.assertIsNone(json.loads(result[len(RECORD_PREFIX):].decode("ascii"))["producerFailure"])

        invalid_values = (None, True, 1, 1.0, [], {}, b"N1", Hostile(), CANARY, StringSubclass("N1"))
        for index, bad in enumerate(invalid_values):
            with self.subTest(bad_capsule_argument=index):
                self.assertEqual(M.startup_failure_record(eof, bad, BINDING, "CHILD_READY_READ", None), b"")
                self.assertEqual(M.startup_failure_record(eof, "N1", bad, "CHILD_READY_READ", None), b"")
                self.assertEqual(M.startup_failure_record(eof, "N1", BINDING, bad, None), b"")
                self.assertEqual(M.parse_startup_record(raw, bad, BINDING), ())
                self.assertEqual(M.parse_startup_record(raw, "N1", bad), ())
        for bad in (None, RuntimeError(CANARY), SystemExit(CANARY), ErrorSubclass("START", "STATUS_MISSING"), Hostile()):
            self.assertEqual(M.startup_failure_record(bad, "N1", BINDING, "CHILD_READY_READ", None), b"")
        for attribute in ("stage", "reason", "errno_name", "ready_site"):
            for bad in (Hostile(), CANARY, StringSubclass("NONE"), [], None):
                error = M.ExperimentError("START", "STATUS_MISSING")
                setattr(error, attribute, bad)
                self.assertEqual(M.startup_failure_record(error, "N1", BINDING, "CHILD_READY_READ", None), b"")

        changes = (
            ("schema", True), ("schema", 2), ("case", "N2"), ("case", CANARY), ("binding", "b" * 64),
            ("binding", CANARY), ("site", CANARY), ("site", None), ("ready", "READY_PRODUCER"),
            ("ready", CANARY), ("failure", ["START", "STATUS_MISSING", CANARY]),
            ("failure", ["START", "STATUS_MISSING"]), ("failure", "START"),
            ("timeout", ["READ_WAIT", "F3", "BODY"]), ("eof", ["F9", "HEADER", "EMPTY"]),
            ("eof", ["F3", "FRAME", "EMPTY"]), ("eof", ["F3", "HEADER", CANARY]), ("eof", []),
            ("producerFailure", ["IDENTITY", "REFUSED", CANARY]), ("producerFailure", []), ("extra", CANARY),
        )
        for index, (key, changed) in enumerate(changes):
            value = capsule_fixture()
            value[key] = changed
            first = PRIMARY
            if type(value["failure"]) is list and all(type(item) is str for item in value["failure"]):
                first = "P2PKIT_CONTEXT_FAILURE|" + "|".join(value["failure"])
            malformed = (first + "\n").encode("ascii") + RECORD_PREFIX + canonical(value)
            with self.subTest(bad_record_field=index):
                self.assertEqual(M.parse_startup_record(malformed, "N1", BINDING), ())
        malformed = (
            raw[:-1], raw + b"\n", raw + raw, raw.replace(b"\n", b"\r\n"), raw + b"\x00",
            raw.replace(RECORD_PREFIX, b"UNRECOGNIZED|", 1), raw.replace(b'"schema":1', b'"schema":1,"schema":1', 1),
            raw.replace(b'"schema":1', b'"schema": 1', 1), raw.replace(b"START|STATUS_MISSING", b"START|REFUSED", 1),
            (PRIMARY + "\n").encode("ascii") + RECORD_PREFIX + json.dumps(capsule_fixture()).encode("ascii") + b"\n",
            b"x" * 2049, b"\xff\n", None, [], {}, Hostile(), bytearray(raw), BytesSubclass(raw),
        )
        for index, bad in enumerate(malformed):
            with self.subTest(malformed_record=index):
                self.assertEqual(M.parse_startup_record(bad, "N1", BINDING), ())

    @contextlib.contextmanager
    def _foreground(self, *, raw=None, mutation=None, file_fault=None, diagnostic_error=False, primary_error=None):
        """Actual run_cases/abort/main and stable read_file, with memory-only owners."""
        raw = capsule_bytes(capsule_fixture()) if raw is None else raw
        state = types.SimpleNamespace(order=[], writes=[], opens=[], reads=[], stats={}, fstats=0, handles=[],
                                      output=io.StringIO(), replace_current=False, raw=raw)
        context = state.context = M.Context.__new__(M.Context)
        context.finished = context.export_called = context.sentinel_closed = False
        context.abort_end = context.result = context.sentinel = context.sentinel_pipes = context.current = None
        context.case_results = []
        context.evidence, context.parent, context.parent_identity = EVIDENCE, PARENT, [11, 22]
        context.environment, context.foreground, context.account = {"PATH": "/usr/bin:/bin", "LANG": "C"}, identity(101, 1), account()
        context.step_end, context.job_end, context.policy_end = 720 * M.NS, 1440 * M.NS, 1440 * M.NS
        service_identity, sentinel_identity = identity(202, 1), identity(404, 101)
        registration = dict(identity=copy.deepcopy(service_identity), startedMonotonicNs=1,
            returnedMonotonicNs=2, recheckedMonotonicNs=3,
            requested=dict(ident=202, filter=M.EVFILT_PROC, flags=M.EV_ADD | M.EV_ENABLE | M.EV_RECEIPT,
                           fflags=M.NOTE_EXIT | M.NOTE_EXITSTATUS),
            receipts=[dict(ident=202, filter=M.EVFILT_PROC, flags=M.EV_ERROR, fflags=0, data=0)])
        event = dict(ident=202, filter=M.EVFILT_PROC, flags=M.EV_EOF,
                     fflags=M.NOTE_EXIT | M.NOTE_EXITSTATUS, data=2 << 8)
        native = context.native = state.native = types.SimpleNamespace(closed=False,
            watched={202: copy.deepcopy(service_identity)}, registrations={202: registration},
            events={202: dict(event=event, status=M.decode_exit_event(event, 202))}, attach_attempts=[registration], signals=[])
        admin = state.admin = types.SimpleNamespace(service=service_identity, retired=False, removed=False, closed=False)
        held = state.held = dict(case="N1", binding=BINDING, directory=EVIDENCE / "N1", directoryIdentity=[11, 33],
            listener=None, channel=None, admin=admin, service=service_identity, producer=None, prepareSent=True, socket=None)
        if primary_error is None:
            primary_error = M.ExperimentError("START", "STATUS_MISSING")
            primary_error.protocol_eof = (4, "HEADER", "EMPTY")
        state.failure = primary_error
        primary_error.private_context = CANARY
        stdin = types.SimpleNamespace(closed=False)
        sentinel = state.sentinel = types.SimpleNamespace(pid=404, stdin=stdin)
        stderr_path = EVIDENCE / "N1" / "service.stderr"

        def clock():
            state.order.append("clock")
            return M.NS

        def mkdir(path, mode=0o777, parents=False, exist_ok=False):
            self.assertEqual((path, mode, parents, exist_ok), (EVIDENCE / "sentinel", 0o700, False, False))
            state.order.append("sentinel-directory")

        def popen(argv, **kwargs):
            self.assertEqual(argv, ["/bin/cat"])
            self.assertEqual(kwargs, dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          close_fds=True, env=context.environment))
            state.order.append("sentinel-create")
            return sentinel

        def pipes_init(pipes, actual):
            self.assertIs(actual, sentinel)
            pipes.closed = False
            state.pipes = pipes

        def native_identity(pid):
            self.assertEqual(pid, 404)
            state.order.append("sentinel-identity")
            return sentinel_identity

        def perform(actual, case, end):
            self.assertIs(actual, context)
            self.assertEqual((case, end), ("N1", 181 * M.NS))
            state.order.append("case-failure")
            context.current = held
            raise primary_error

        def poll():
            state.order.append("original-poll")

        def signal_original(value, signum, end):
            self.assertEqual((value, signum, end), (held["service"], signal.SIGTERM, 121 * M.NS))
            state.order.append("original-signal")

        def wait_original(values, end):
            state.order.append("original-wait")
            self.assertEqual((values, end), ([held["service"]], 121 * M.NS))
            if 202 not in native.events:
                raise M.ExperimentError("SERVICE_WAIT", "STATUS_MISSING")
            return {202: native.events[202]}

        def close_stdin():
            state.order.append("sentinel-stdin-close")
            stdin.closed = True

        def finish(pipes, end, directory):
            self.assertEqual((end, directory), (121 * M.NS, EVIDENCE / "sentinel"))
            self.assertIs(pipes, state.pipes)
            state.order.append("sentinel-finish")
            pipes.closed = True
            return 0, []

        def close_native():
            state.order.append("native-close")
            native.closed = True

        def close_admin():
            state.order.append("admin-close")
            admin.closed = True

        def write_new(path, content):
            state.order.append("aborted-record")
            state.writes.append((path, content))
            if state.replace_current:
                context.current = dict(held)

        def metadata(path):
            state.order.append("lstat")
            state.stats[path] = state.stats.get(path, 0) + 1
            if path == PARENT:
                ino = 23 if file_fault == "parent-changed" and state.stats[path] > 1 else 22
                return types.SimpleNamespace(st_dev=11, st_ino=ino, st_mode=stat.S_IFDIR | 0o700, st_uid=501)
            if path == EVIDENCE / "N1":
                ino = 34 if file_fault == "directory-changed" and state.stats[path] > 1 else 33
                mode = 0o755 if file_fault == "directory-mode" else 0o700
                return types.SimpleNamespace(st_dev=11, st_ino=ino, st_mode=stat.S_IFDIR | mode, st_uid=501)
            self.assertEqual(path, stderr_path)
            return file_stat(changed=file_fault == "path-changed" and state.stats[path] > 1)

        def file_stat(*, changed=False):
            mode = stat.S_IFDIR | 0o600 if file_fault == "not-regular" else stat.S_IFREG | (0o400 if file_fault == "mode" else 0o600)
            return types.SimpleNamespace(st_dev=11, st_ino=45 if changed else 44, st_mode=mode,
                st_uid=502 if file_fault == "owner" else 501, st_gid=20, st_nlink=2 if file_fault == "hardlink" else 1,
                st_size=len(raw), st_mtime_ns=10, st_ctime_ns=10)

        def is_symlink(path):
            state.order.append("no-symlink")
            return file_fault == "symlink" and path == stderr_path

        def open_original(path, flags):
            state.order.append("diagnostic-open")
            state.opens.append((path, flags))
            self.assertEqual((path, flags), (stderr_path, M.os.O_RDONLY | M.os.O_NOFOLLOW))
            self.assertEqual(len(state.opens), 1, "ONE_POST_TERMINAL_FILE_OPEN")
            if file_fault == "open":
                raise OSError(CANARY)
            return 909

        class Handle:
            def __init__(handle):
                handle.closed = False

            def __enter__(handle):
                return handle

            def __exit__(handle, *_args):
                handle.closed = True

            def fileno(handle):
                return 909

            def read(handle, count):
                state.order.append("diagnostic-read")
                state.reads.append(count)
                self.assertEqual(state.reads, [2049], "ONE_BOUNDED_READ_NO_TAIL_POLL")
                if file_fault == "read":
                    raise OSError(CANARY)
                return raw + b"x" if file_fault == "overread" else raw

        def fdopen(fd, mode):
            self.assertEqual((fd, mode), (909, "rb"))
            handle = Handle()
            state.handles.append(handle)
            return handle

        def fstat(fd):
            self.assertEqual(fd, 909)
            state.fstats += 1
            return file_stat(changed=file_fault == "fd-changed" and state.fstats > 1)

        stdin.close, native.close = close_stdin, close_native
        native.identity = Mock(side_effect=native_identity)
        native.poll, native.wait, native.signal = Mock(side_effect=poll), Mock(side_effect=wait_original), Mock(side_effect=signal_original)
        native.same = Mock(side_effect=AssertionError("NO_DIAGNOSTIC_NATIVE_RECHECK"))
        native.token = Mock(side_effect=AssertionError("NO_DIAGNOSTIC_TOKEN"))
        native.watch = Mock(side_effect=AssertionError("NO_DIAGNOSTIC_WATCH"))
        admin.retire, admin.close = Mock(side_effect=AssertionError("UNKNOWN_P_FORBIDS_RETIREMENT")), close_admin
        context.output = types.SimpleNamespace(close=Mock(side_effect=lambda: state.order.append("output-close")))
        if mutation is not None:
            mutation(state)
        with contextlib.ExitStack() as stack:
            for owner, name, kwargs in (
                (M, "shared_raw_ns", dict(side_effect=clock)),
                (M, "prepare", dict(return_value=context)),
                (M, "perform_case", dict(side_effect=perform)),
                (M, "write_new", dict(side_effect=write_new)),
                (M.Path, "mkdir", dict(autospec=True, side_effect=mkdir)),
                (M.Path, "lstat", dict(autospec=True, side_effect=metadata)),
                (M.Path, "is_symlink", dict(autospec=True, side_effect=is_symlink)),
                (M.subprocess, "Popen", dict(side_effect=popen)),
                (M.ProbePipes, "__init__", dict(autospec=True, side_effect=pipes_init)),
                (M.ProbePipes, "finish", dict(autospec=True, side_effect=finish)),
                (M.os, "getpid", dict(return_value=101)),
                (M.os, "getuid", dict(return_value=501)),
                (M.os, "open", dict(side_effect=open_original)),
                (M.os, "fdopen", dict(side_effect=fdopen)),
                (M.os, "fstat", dict(side_effect=fstat)),
                (M.os, "umask", dict(return_value=0o077)),
            ):
                stack.enter_context(patch.object(owner, name, **kwargs))
            state.export = stack.enter_context(patch.object(M, "finish_export", side_effect=AssertionError("NO_ABORT_EXPORT")))
            stack.enter_context(patch.object(M, "_UNCLOSED_COMMANDS", []))
            stack.enter_context(patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]))
            stack.enter_context(contextlib.redirect_stdout(state.output))
            if diagnostic_error:
                stack.enter_context(patch.object(M, "emit_startup_diagnostic", side_effect=RuntimeError(CANARY)))
            yield state

    def _refused(self, state):
        context = state.context
        self.assertFalse(context.finished or context.export_called)
        self.assertIsNone(context.result)
        self.assertEqual(context.case_results, [])
        self.assertEqual(context.abort_end, 121 * M.NS)
        self.assertTrue(context.sentinel_closed and context.native.closed and state.pipes.closed)
        self.assertEqual(context.output.close.call_count, 2)
        state.export.assert_not_called()
        state.admin.retire.assert_not_called()
        self.assertFalse(state.admin.retired or state.admin.removed)
        self.assertIsNone(state.held["producer"])
        self.assertEqual(len(state.writes), 1)
        path, raw = state.writes[0]
        self.assertEqual(path, EVIDENCE / "aborted-no-export.json")
        value = M.parsed(raw, M.EVIDENCE_BYTES)
        self.assertEqual((value["qualification"], value["exportAllowed"], value["adminLifetimeUnknown"]), ("REFUSED", False, False))
        self.assertEqual(value["abortEndNs"], 121 * M.NS)
        self.assertEqual(state.order.count("clock"), 4, "DIAGNOSTIC_MUST_NOT_READ_ANOTHER_CLOCK")
        state.native.identity.assert_called_once_with(404)
        state.native.poll.assert_called_once_with()
        self.assertLessEqual(state.native.wait.call_count, 1)
        self.assertLessEqual(state.native.signal.call_count, 1)
        for endpoint in (state.native.same, state.native.token, state.native.watch):
            endpoint.assert_not_called()
        self.assertTrue(all(handle.closed for handle in state.handles))
        self.assertNotIn(CANARY, state.output.getvalue())
        self.assertNotIn(BINDING, state.output.getvalue())
        return value

    def test_03_actual_abort_main_terminal_gate_and_primary(self):
        summary = (
            SERVICE_PREFIX + "N1|CHILD_READY_READ|NONE|START|STATUS_MISSING|NONE\n"
            "P2PKIT_CONTEXT_SERVICE_PROTOCOL_EOF|N1|F3|HEADER|EMPTY\n"
            + REPORTED_PREFIX + "N1|IDENTITY|IDENTITY_CHANGED|NONE\n"
        )
        primary = PRIMARY + "\nP2PKIT_CONTEXT_PROTOCOL_EOF|N1|F4|HEADER|EMPTY\n"
        with self._foreground() as state:
            original_event = copy.deepcopy(state.native.events)
            self.assertEqual(M.main(), 2)
            value = self._refused(state)
            self.assertEqual(state.output.getvalue(), summary + primary)
            self.assertEqual((len(state.opens), state.reads), (1, [2049]))
            self.assertEqual(value["cleanupErrors"], [])
            self.assertEqual(state.native.events, original_event)
            self.assertLess(state.order.index("original-wait"), state.order.index("native-close"))
            self.assertLess(state.order.index("native-close"), state.order.index("aborted-record"))
            self.assertLess(state.order.index("aborted-record"), state.order.index("diagnostic-open"))
            self.assertLess(state.order.index("diagnostic-open"), state.order.index("diagnostic-read"))

        # These mutations are retained DATA, not manufactured native events.
        # Each must fail before any filesystem observation, not merely before read.
        gates = (
            ("service-absent", lambda state: state.held.update(service=None)),
            ("watch-absent", lambda state: state.native.watched.clear()),
            ("watch-version", lambda state: state.native.watched[202].update(pidVersion=2)),
            ("registration-absent", lambda state: state.native.registrations.clear()),
            ("registration-copy", lambda state: setattr(state.native, "attach_attempts", copy.deepcopy(state.native.attach_attempts))),
            ("registration-version", lambda state: state.native.registrations[202]["identity"].update(pidVersion=2)),
            ("registration-time", lambda state: state.native.registrations[202].update(recheckedMonotonicNs=0)),
            ("registration-time-type", lambda state: state.native.registrations[202].update(startedMonotonicNs=True)),
            ("requested-pid", lambda state: state.native.registrations[202]["requested"].update(ident=203)),
            ("requested-flags", lambda state: state.native.registrations[202]["requested"].update(fflags=M.NOTE_EXIT)),
            ("receipt-count", lambda state: state.native.registrations[202]["receipts"].clear()),
            ("receipt-error", lambda state: state.native.registrations[202]["receipts"][0].update(data=1)),
            ("receipt-flag", lambda state: state.native.registrations[202]["receipts"][0].update(flags=0)),
            ("event-absent", lambda state: state.native.events.clear()),
            ("event-pid", lambda state: state.native.events[202]["event"].update(ident=203)),
            ("event-type", lambda state: state.native.events[202]["event"].update(ident=True)),
            ("event-filter", lambda state: state.native.events[202]["event"].update(filter=0)),
            ("event-error", lambda state: state.native.events[202]["event"].update(flags=M.EV_ERROR)),
            ("event-note", lambda state: state.native.events[202]["event"].update(fflags=M.NOTE_EXIT)),
            ("event-stopped", lambda state: state.native.events[202]["event"].update(data=0x7f)),
            ("status-code", lambda state: state.native.events[202]["status"].update(popenCode=0)),
            ("status-type", lambda state: state.native.events[202]["status"].update(value=True)),
            ("missing-binding", lambda state: state.held.pop("binding")),
            ("directory-shape", lambda state: state.held.update(directoryIdentity=[11, True])),
            ("wrong-directory", lambda state: state.held.update(directory=EVIDENCE / "N2")),
            ("replaced-current", lambda state: setattr(state, "replace_current", True)),
        )
        for name, mutation in gates:
            with self.subTest(gate=name), self._foreground(mutation=mutation) as state:
                self.assertEqual(M.main(), 2)
                self._refused(state)
                self.assertEqual(state.output.getvalue(), primary)
                self.assertEqual((state.opens, state.reads, state.stats), ([], [], {}))
                self.assertNotIn("no-symlink", state.order)

        for fault in ("owner", "hardlink", "mode", "not-regular", "directory-mode", "symlink", "open", "read",
                      "overread", "fd-changed", "path-changed", "directory-changed", "parent-changed"):
            with self.subTest(file_fault=fault), self._foreground(file_fault=fault) as state:
                self.assertEqual(M.main(), 2)
                value = self._refused(state)
                self.assertEqual(state.output.getvalue(), primary)
                self.assertLessEqual(len(state.opens), 1)
                self.assertLessEqual(len(state.reads), 1)
                self.assertEqual(value["cleanupErrors"], [])
        for invalid in (b"", b"x" * 2049, capsule_bytes(capsule_fixture())[:-1],
                        capsule_bytes(capsule_fixture()).replace(BINDING.encode("ascii"), b"b" * 64),
                        capsule_bytes(capsule_fixture()) + CANARY.encode("ascii")):
            with self.subTest(malformed_size=len(invalid)), self._foreground(raw=invalid) as state:
                self.assertEqual(M.main(), 2)
                value = self._refused(state)
                self.assertEqual(state.output.getvalue(), primary)
                self.assertLessEqual(len(state.reads), 1)
                self.assertEqual(value["cleanupErrors"], [])
        with self._foreground(diagnostic_error=True) as state:
            self.assertEqual(M.main(), 2)
            value = self._refused(state)
            self.assertEqual(state.output.getvalue(), primary)
            self.assertEqual(state.opens, [])
            self.assertEqual(value["cleanupErrors"], [])
        different = M.ExperimentError("IDENTITY", "REFUSED", "UNKNOWN")
        with self._foreground(primary_error=different) as state:
            self.assertEqual(M.main(), 2)
            self._refused(state)
            self.assertEqual(state.output.getvalue(), summary + "P2PKIT_CONTEXT_FAILURE|IDENTITY|REFUSED|UNKNOWN\n")

    def test_04_exact_inverse_legacy_hunks_and_guard_mutations(self):
        source = SOURCE.read_text(encoding="utf-8")
        ready_layer = CLOCK.restore_ready_producer_runtime(source)
        self.assertEqual(hashlib.sha256(ready_layer.encode("utf-8")).hexdigest(),
                         "db90735880ff020f027a91c695221963bbebce07a3ee7e7e624622692931c852")
        hashes = (
            PREIMAGE,
            "17b7105e3dab4dcf865d8fda633f988b9ad78d1b286e0ecbb215da8d2828da47",
            "e92c291407c4b1f6f000a675c07190b34c340cd6b17648e5d73fd8a610e9acac",
            "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf",
            "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b",
            "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d",
        )
        self.assertEqual((CLOCK.STARTUP_DIAGNOSTIC_BASE_RUNTIME_SHA256, CLOCK.PROTOCOL_TIMEOUT_BASE_RUNTIME_SHA256,
                          CLOCK.PROTOCOL_EOF_BASE_RUNTIME_SHA256, CLOCK.PLIST_NAME_BASE_RUNTIME_SHA256,
                          CLOCK.ADMIN_RETURN_BASE_RUNTIME_SHA256, CLOCK.BASE_RUNTIME_SHA256), hashes)
        self.assertEqual((CLOCK.BASE_WORKFLOW_SHA256, CLOCK.BASE_EXPERIMENT_TEST_SHA256), (
            "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40",
            "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768",
        ))
        restores = (CLOCK.restore_startup_diagnostic_runtime, CLOCK.restore_protocol_timeout_runtime,
                    CLOCK.restore_protocol_eof_runtime, CLOCK.restore_plist_name_runtime,
                    CLOCK.restore_admin_return_runtime, CLOCK.restore_runtime)
        for restore, expected in zip(restores, hashes):
            self.assertEqual(hashlib.sha256(restore(source).encode("utf-8")).hexdigest(), expected)
        for restore in restores[1:]:
            with patch.object(CLOCK, "restore_startup_diagnostic_runtime", wraps=restores[0]) as newest:
                restore(source)
                newest.assert_called_once_with(source)
        self.assertEqual((len(CLOCK.STARTUP_DIAGNOSTIC_PATCH), len(CLOCK.PROTOCOL_TIMEOUT_PATCH), len(CLOCK.PROTOCOL_EOF_PATCH),
                          len(CLOCK.PLIST_NAME_PATCH), len(CLOCK.ADMIN_RETURN_PATCH)), (10, 13, 7, 3, 8))
        # Historical raw hunks reside in the explicitly hashed prior layer.
        # Bypass only the newest inverse with the supplied text itself, never a
        # saved preimage. Positive acceptance prevents missing-new-hunk failures
        # from masquerading as historical mutation coverage.
        with patch.object(CLOCK, "restore_ready_producer_runtime", side_effect=lambda held: held) as newest:
            for restore, expected in zip(restores, hashes):
                newest.reset_mock()
                self.assertEqual(hashlib.sha256(restore(ready_layer).encode("utf-8")).hexdigest(), expected)
                newest.assert_called_once_with(ready_layer)

        def reject_at_prior_layer(changed):
            self.assertNotEqual(changed, ready_layer)
            with patch.object(CLOCK, "restore_ready_producer_runtime", side_effect=lambda held: held) as newest:
                for restore in restores:
                    newest.reset_mock()
                    with self.assertRaises(AssertionError):
                        restore(changed)
                    newest.assert_called_once_with(changed)

        for before, after in (*CLOCK.STARTUP_DIAGNOSTIC_PATCH, *CLOCK.PROTOCOL_TIMEOUT_PATCH, *CLOCK.PROTOCOL_EOF_PATCH,
                              *CLOCK.PLIST_NAME_PATCH, *CLOCK.ADMIN_RETURN_PATCH):
            self.assertEqual(ready_layer.count(after), 1, "HASHED_PRIOR_RAW_POSTIMAGE_MUST_REMAIN_CONTIGUOUS")
            for changed in (ready_layer.replace(after, before, 1), ready_layer + after):
                reject_at_prior_layer(changed)
        preimage = restores[0](source)
        for bad in (None, b"", "", StringSubclass(source), preimage, source + "\n# UNRELATED_STARTUP_MUTATION\n"):
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(bad)
        for patches in (CLOCK.STARTUP_DIAGNOSTIC_PATCH[:-1], CLOCK.STARTUP_DIAGNOSTIC_PATCH + CLOCK.STARTUP_DIAGNOSTIC_PATCH[:1]):
            with patch.object(CLOCK, "STARTUP_DIAGNOSTIC_PATCH", patches):
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(source)

        # Each mutation is inert source DATA. No alternate runtime is executed.
        mutations = (
            ('require(type(end_ns) is int, stage, "TIMEOUT")', 'require(True, stage, "TIMEOUT")'),
            ('require(remaining > 0, stage, "TIMEOUT")', 'require(remaining >= 0, stage, "TIMEOUT")'),
            ('return left(end_ns, "START")', 'return left(end_ns + NS, "START")'),
            ('(end_ns - shared_raw_ns())', '(end_ns - time.monotonic_ns())'),
            ('CASE_SECONDS = 120, 180, 40', 'CASE_SECONDS = 120, 180, 41'),
            ('ABORT_SECONDS, FREEZE_SECONDS, EXPORT_SECONDS = 120, 60, 120',
             'ABORT_SECONDS, FREEZE_SECONDS, EXPORT_SECONDS = 121, 60, 120'),
            ('JOB_SECONDS, STEP_SECONDS = 1440, 720', 'JOB_SECONDS, STEP_SECONDS = 1441, 721'),
            ('UPLOAD_SECONDS, ADMIN_SECONDS = 420, 10', 'UPLOAD_SECONDS, ADMIN_SECONDS = 421, 11'),
            ('FRAME_BYTES, STREAM_BYTES, EVIDENCE_BYTES, EVIDENCE_MEMBERS = 16384, 65536, 2 * 1024 * 1024, 128',
             'FRAME_BYTES, STREAM_BYTES, EVIDENCE_BYTES, EVIDENCE_MEMBERS = 16385, 65537, 3 * 1024 * 1024, 129'),
            ('len(trace) < 8', 'len(trace) < 9'),
            ('require(part, "START", "STATUS_MISSING")', 'require(True, "START", "STATUS_MISSING")'),
            ('require(not ancillary and flags == 0, stage, "REFUSED")', 'require(True, stage, "REFUSED")'),
            ('value["binding"] == binding', 'value["binding"] != binding'),
            ('IDENTITY_KEYS - {"status"}', 'IDENTITY_KEYS - {"status", "pidVersion"}'),
            ('same_identity(payload["producer"], producer_identity)', 'same_identity(payload["producer"], payload["producer"])'),
            ('identity_account(producer_identity, prepared["account"])', 'validate_account(prepared["account"])'),
            ('producer_identity["parentUniqueId"] == service_identity["uniqueId"]', 'True'),
            ('payload["sourceSha256"] == prepared["source"]["files"][SCRIPT]', 'True'),
            ('payload["interpreter"] == prepared["interpreter"]["path"]', 'True'),
            ('require(received == prepared, "START", "IDENTITY_CHANGED")', 'require(True, "START", "IDENTITY_CHANGED")'),
            ('not any(key in os.environ for key in OWNER_ENV)', 'True'),
            ('P2PKIT_CONTEXT_CLOCK_DOMAIN=CLOCK_DOMAIN', 'P2PKIT_CONTEXT_CLOCK_DOMAIN="UNPINNED"'),
            ('[interpreter["path"], "-I", "-B", "-S", str(ROOT / SCRIPT), "_probe", str(child_fd)]',
             '[interpreter["path"], str(ROOT / SCRIPT), "_probe", str(child_fd)]'),
            ('close_fds=True, pass_fds=(child_fd,), cwd=ROOT, env=environment',
             'close_fds=False, pass_fds=(), cwd=ROOT, env=environment'),
            ('require(channel.fileno() == -1, "CLOSE", "RESOURCE_UNKNOWN")', 'require(True, "CLOSE", "RESOURCE_UNKNOWN")'),
            ('self.calls < 96', 'self.calls < 97'),
            ('context.native.watch(peer)', 'context.native.same(peer)'),
            ('context.native.watch(producer_identity)', 'context.native.same(producer_identity)'),
            ('channel.shutdown(socket.SHUT_WR)', 'channel.shutdown(socket.SHUT_RDWR)'),
            ('native.signal(producer_identity, signal.SIGTERM, end_ns)', 'native.signal(producer_identity, signal.SIGKILL, end_ns)'),
            ('signal.raise_signal(signal.SIGTERM)', 'return 0'),
            ('context.sentinel.poll() is None', 'True'),
            ('state["producer"] is not None or not state["prepareSent"]', 'True'),
            ('context.sentinel_closed and context.sentinel_pipes.closed and context.native.closed', 'True'),
            ('not context.export_called and context.recipient is context.recipient_original', 'True'),
            ('STARTUP_BYTES = 2048', 'STARTUP_BYTES = 65536'),
            ('type(error) is not ExperimentError or type(site) is not str', 'type(site) is not str'),
            ('context.current is not state', 'False'),
            ('not any(item is registration for item in native.attach_attempts)', 'False'),
            ('decoded = decode_exit_event(terminal["event"], pid)', 'decoded = terminal["status"]'),
            ('stat.S_IMODE(before.st_mode) != 0o600', 'False'),
            ('raw = read_file(path, STARTUP_BYTES)', 'raw = read_file(path, STREAM_BYTES)'),
            ('for line in parse_startup_record(raw, case, binding):', 'for line in (raw.decode("ascii"),):'),
            ('type(pipes) is not ProbePipes or type(pipes.data) is not dict', 'False'),
            ('if ordinal <= previous:', 'if ordinal < previous:'),
        )
        for index, (before, after) in enumerate(mutations):
            with self.subTest(guard_mutation=index):
                self.assertIn(before, source)
                changed = source.replace(before, after, 1)
                self.assertNotEqual(source, changed)
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(changed)
                self.assertIn(before, ready_layer)
                reject_at_prior_layer(ready_layer.replace(before, after, 1))

        tree, before_tree = ast.parse(source, feature_version=(3, 9)), ast.parse(preimage, feature_version=(3, 9))
        current = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        original = {node.name: node for node in before_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        changed_functions = {"validate_ready", "service", "perform_case", "abort_suite"}
        for name, function in original.items():
            self.assertIn(name, current)
            if name not in changed_functions:
                self.assertEqual(ast.dump(current[name]), ast.dump(function), name)
        ready_try = current["validate_ready"].body[1]
        self.assertIsInstance(ready_try, ast.Try)
        ready_body = [node for node in ready_try.body if not (isinstance(node, ast.Assign) and
                      len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "ready_site")]
        self.assertEqual(tuple(ast.dump(node) for node in ready_body),
                         tuple(ast.dump(node) for node in original["validate_ready"].body))

        selected = {"require", "validate_frame", "validate_account", "identity_account", "same_identity", "read_frame",
                    "send_frame", "validate_ready", "validate_probe_result", "validate_probe_observation", "wait_eof",
                    "close_socket", "child_environment", "shared_raw_ns", "left", "timeout_left", "decode_exit_event",
                    "validate_case_result", "validate_closure", "validate_final_frame", "close_sentinel", "write_new"}
        native_owners = {"native", "context.native", "socket", "subprocess", "signal"}

        def calls(function):
            result = []
            def visit(node):
                if isinstance(node, ast.Call):
                    func = node.func
                    name = func.id if isinstance(func, ast.Name) else None
                    owner = ast.unparse(func.value) if isinstance(func, ast.Attribute) else None
                    if name in selected or owner in native_owners:
                        result.append(ast.dump(node))
                for child in ast.iter_child_nodes(node):
                    visit(child)
            visit(function)
            return result

        for name in changed_functions:
            self.assertEqual(calls(current[name]), calls(original[name]), "ORIGINAL_ORDERED_GUARDS_AND_OPERATIONS_" + name)
        clocks = {}

        def inspect(node, owners=()):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                owners += (node.name,)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "shared_raw_ns":
                    self.assertFalse(node.args or node.keywords)
                    name = ".".join(owners)
                    clocks[name] = clocks.get(name, 0) + 1
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "time":
                    self.assertNotIn(node.func.attr, {"monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns"})
            for child in ast.iter_child_nodes(node):
                inspect(child, owners)

        inspect(tree)
        self.assertEqual(clocks, {"left": 1, "capture_fixed": 1, "Darwin.watch": 3, "Darwin.signal": 2,
            "native_probe": 7, "Admin._run": 2, "service": 2, "Context.__init__": 1, "Context.limit": 1,
            "prepare": 2, "perform_case": 4, "close_sentinel": 1, "run_cases": 1, "finish_export": 2, "upload_guard": 3})
        self.assertEqual((M.JOB_SECONDS, M.STEP_SECONDS, M.PREPARE_SECONDS, M.NATIVE_SECONDS, M.CASE_SECONDS,
                          M.ABORT_SECONDS, M.FREEZE_SECONDS, M.EXPORT_SECONDS, M.UPLOAD_SECONDS, M.ADMIN_SECONDS),
                         (1440, 720, 120, 180, 40, 120, 60, 120, 420, 10))
        self.assertEqual(len(M.FRAME_ROSTER), 8)
        self.assertEqual(M.CASES, ("N1", "N2", "N3", "N4"))
        for relative, expected in (
            ("scripts/tests/hosted-darwin-context-protocol-timeout-test.py", "7095a048d1a450e007d968abb712d86051ad1623e208c04725c8862e00743eb7"),
            ("scripts/tests/hosted-darwin-context-protocol-eof-test.py", "b214695509227ab5acea119c87c1beb7adf4f2faffcff41fe3ba8b00d0dcc6d2"),
            ("scripts/tests/hosted-darwin-context-admin-return-test.py", "a98e4cc5424116683b7fcaa78d1770909bb17dbc115fb15ff225f2ed6d4218ab"),
            ("scripts/tests/hosted-darwin-context-clock-test.py", "4a3fce92d05457054ae86ccf2a6c5002a9940e37a46fbfe167efb3d6b53c64ea"),
            ("scripts/audit_processes.py", "7ef1beb8a79ce3c8e062100849babee6ffa0ce3421d0f0fc56706c3e0ef7ed13"),
            (".github/workflows/darwin-native-context-experiment.yml", "46dd83658e256ed4c14ebe376addaac7f73b4cd40552b13853515d9c1f5d5933"),
            (".github/test-evidence-recipient.json", "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"),
            ("AGENTS.md", "3ca3ef11f49ba90152754fb9d884ed353a5bc549b0ab648e182d889d4283d84b"),
            ("CLAUDE.md", "0fd0e8bdd297e16caabc40e87411c377f674769a40b73a35f43818bf9f97a71d"),
        ):
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    if tuple(unittest.defaultTestLoader.getTestCaseNames(StartupDiagnostic)) != METHODS:
        raise SystemExit("FIXED_FOUR_STARTUP_DIAGNOSTIC_METHODS_REQUIRED")
    suite = unittest.TestSuite(StartupDiagnostic(name) for name in METHODS)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
