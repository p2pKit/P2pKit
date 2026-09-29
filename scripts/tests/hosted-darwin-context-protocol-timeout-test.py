#!/usr/bin/env python3
"""Four offline timeout-site controls, not a timeout fix or native admission.

Current guards, framing, case wrapper, foreground abort and main execute against
bounded memory endpoints. Reconstructed preimages are text/AST evidence only;
no old suite, native process, socket, private original or output file is used.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-protocol-timeout-test.py
"""
import ast
import contextlib
import ctypes  # Preload the standard module before the no-native audit fence.
import errno
import hashlib
import importlib.util
import io
from pathlib import Path
import socket
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
    "test_01_actual_left_send_read_and_entry_boundaries",
    "test_02_forward_guard_case_wrapper_and_original_abort",
    "test_03_finite_formatter_and_actual_main_preserve_failure",
    "test_04_exact_inverse_raw_hunks_and_guard_mutations",
)
PREIMAGE = "17b7105e3dab4dcf865d8fda633f988b9ad78d1b286e0ecbb215da8d2828da47"
BINDING = "a" * 64
CANARY = "SYNTHETIC_PROTOCOL_TIMEOUT_CANARY"
PRIMARY = "P2PKIT_CONTEXT_FAILURE|START|TIMEOUT|NONE"
PREFIX = "P2PKIT_CONTEXT_TIMEOUT_SITE|"
EVIDENCE = Path("/synthetic/protocol-timeout/evidence")
ABSENT = object()
SITES = ("NATIVE_ENTRY", "CASE_ENTRY", "SEND_PRE", "SEND_SELECT", "SEND_RETURN", "READ_WAIT", "READ_RETURN", "FORWARD_TIME")
KINDS = ("HELLO", "PREPARE", "CHILD_READY", "CHILD_READY", "START", "START", "RESULT", "CHILD_RESULT_AND_EXIT_READY")
DIRECTIONS = ("D>F", "F>D", "P>D", "D>F", "F>D", "D>P", "P>D", "D>F")


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid", "os.chmod",
        "os.mkdir", "os.rmdir", "os.remove", "os.rename", "os.link", "os.symlink", "os.truncate",
    }:
        raise AssertionError("OFFLINE_PROTOCOL_TIMEOUT_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_PROTOCOL_TIMEOUT_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_protocol_timeout_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
clock_spec = importlib.util.spec_from_file_location("darwin_context_clock_inverse", INVERSE)
CLOCK = importlib.util.module_from_spec(clock_spec)
clock_spec.loader.exec_module(CLOCK)


class Hostile:
    def forbidden(self, *_args, **_kwargs):
        raise AssertionError("UNTRUSTED_TIMEOUT_DIAGNOSTIC_OPERATION")
    __str__ = __repr__ = __bool__ = __len__ = __hash__ = __eq__ = __int__ = __index__ = forbidden


class StringSubclass(str):
    pass


class IntegerSubclass(int):
    pass


class TupleSubclass(tuple):
    pass


class ErrorSubclass(M.ExperimentError):
    pass


def frame_bytes(serial):
    value = dict(schema=1, serial=serial, kind=KINDS[serial - 1], binding=BINDING, payload={"synthetic": CANARY})
    raw = M.encoded(value)
    return value, raw, struct.pack("!I", len(raw))


def final_fixture():
    """Synthetic coherent N4 final data; not a native observation or receipt."""
    class Prepared(dict):
        def __getitem__(self, key):
            self.reads.append(key)
            return super().__getitem__(key)

    prepared = Prepared(binding=BINDING, caseEndNs=40 * M.NS)
    prepared.reads = []
    start = {"synthetic": CANARY}
    probe = dict(stage="NO_NETWORK", result="NO_NETWORK", errno="NONE", sent=0,
                 socketCreated=False, closed=False, closeError="NONE")
    observation = dict(startedMonotonicNs=5 * M.NS, socketFd=None, sendStartedMonotonicNs=None,
                       sendFinishedMonotonicNs=None, sendReturn=None, closeStartedMonotonicNs=None,
                       closeReturnedMonotonicNs=None, closedFd=None, finishedMonotonicNs=6 * M.NS)
    frames = {serial: M.frame_value(serial, BINDING, {"synthetic": CANARY}) for serial in range(1, 8)}
    frames[5] = M.frame_value(5, BINDING, start)
    frames[6] = M.frame_value(6, BINDING, start)
    frames[7] = M.frame_value(7, BINDING, dict(case="N4", probe=probe, observation=observation))
    prefix = [M.frame_record(frames[serial]) for serial in range(1, 8)]
    payload = dict(case="N4", producerCode=0, producerStreams=[], serviceStreams=[], resultFrame=frames[7],
                   tracePrefix=prefix, producerControlEof=True, producerWait=True, nativeClosed=True,
                   capturesClosed=True, signalReturns=[],
                   startForward=dict(startedMonotonicNs=2 * M.NS, returnedMonotonicNs=3 * M.NS))
    final = M.frame_record(M.frame_value(8, BINDING, payload))
    observed = [M.frame_record(frames[serial]) for serial in (1, 2, 4, 5)] + [final]
    return types.SimpleNamespace(payload=payload, prepared=prepared, observed=observed, ready=frames[3],
                                 start=start, probe=probe, observation=observation, trace=[*prefix, final])


class ProtocolTimeout(unittest.TestCase):
    def _caught(self, operation, expected=("START", "TIMEOUT", "NONE")):
        try:
            operation()
        except M.ExperimentError as error:
            original = error
            codes, trace = [], error.__traceback__
            while trace is not None:
                codes.append(trace.tb_frame.f_code)
                trace = trace.tb_next
            self.assertIs(codes[-1], M.require.__code__)
            self.assertIsNone(error.__context__)
        else:
            self.fail("ORIGINAL_GUARD_DID_NOT_REFUSE")
        self.assertEqual((original.stage, original.reason, original.errno_name), expected)
        return original, codes

    @contextlib.contextmanager
    def _wire(self, replies=(), *, times=(), sizes=(), idle=(), pump_error=None, select_error=None, send_error=None):
        state = types.SimpleNamespace(order=[], requests=[], pending=[], sent=bytearray(), position=0,
                                      clock_count=0, selections=0, send_count=0)

        class Channel:
            def recvmsg(channel, size, space):
                state.order.append("recv")
                state.requests.append(size)
                self.assertEqual(space, socket.CMSG_SPACE(16))
                self.assertLess(state.position, len(replies), "NO_EXTRA_MEMORY_RECV")
                reply = replies[state.position]
                state.position += 1
                if isinstance(reply, BaseException):
                    raise reply
                result = reply if type(reply) is tuple else (reply, [], 0, None)
                self.assertLessEqual(len(result[0]), size)
                return result

            def send(channel, pending):
                state.order.append("send")
                state.pending.append(bytes(pending))
                if send_error is not None:
                    raise send_error
                self.assertLess(state.send_count, len(sizes), "NO_EXTRA_MEMORY_SEND")
                count = sizes[state.send_count]
                state.send_count += 1
                self.assertLessEqual(count, len(pending))
                state.sent.extend(pending[:count])
                return count

        state.channel = Channel()

        def clock():
            state.order.append("clock")
            self.assertLess(state.clock_count, len(times), "NO_EXTRA_CLOCK_READ")
            value = times[state.clock_count]
            state.clock_count += 1
            return value

        def pump():
            state.order.append("pump")
            if pump_error is not None:
                raise pump_error

        def select(read, write, exceptional, timeout):
            state.order.append("select")
            self.assertEqual(exceptional, [])
            self.assertTrue((read == [state.channel] and write == []) or (read == [] and write == [state.channel]))
            self.assertGreater(timeout, 0)
            self.assertLessEqual(timeout, 0.05)
            state.selections += 1
            if select_error is not None:
                raise select_error
            ready = [] if state.selections in idle else [state.channel]
            return (ready, [], []) if read else ([], ready, [])

        state.pump = pump
        with patch.object(M, "shared_raw_ns", side_effect=clock), patch.object(M.select, "select", side_effect=select):
            yield state

    @contextlib.contextmanager
    def _foreground(self, times, *, error=ABSENT, at_popen=False):
        """Real run_cases/abort; only clock, sentinel and storage endpoints are models.

        With no injected error, real perform_case reaches its entry guard.
        Injected case errors separately exercise the real once-only wrapper.
        """
        state = types.SimpleNamespace(order=[], clock_cases=[], writes=[], gates=[], failure=None, ticks=0)
        if error is not ABSENT:
            state.failure = error
        context = state.context = M.Context.__new__(M.Context)
        context.finished = context.export_called = context.sentinel_closed = False
        context.abort_end = context.result = context.sentinel = context.sentinel_pipes = context.current = None
        context.case_results = []
        context.evidence, context.environment = EVIDENCE, {"PATH": "/usr/bin:/bin", "LANG": "C"}
        context.step_end, context.job_end, context.policy_end = 720 * M.NS, 1440 * M.NS, 1440 * M.NS
        context.foreground = dict(uniqueId=22)
        context.account = dict(uid=501, euid=501, gid=20, egid=20, groups=[20])
        context.native = types.SimpleNamespace(closed=False, watched={}, events={}, attach_attempts=[], signals=[])
        sentinel_identity = dict(pid=222, parentPid=111, parentUniqueId=22, uid=501, realUid=501, gid=20, realGid=20)
        stdin = types.SimpleNamespace(closed=False)
        process = types.SimpleNamespace(pid=222, stdin=stdin)
        pipes = types.SimpleNamespace(closed=False)
        original_gate = M.timeout_left

        def clock():
            state.order.append("clock")
            self.assertLess(state.ticks, len(times), "NO_EXTRA_FOREGROUND_CLOCK")
            state.clock_cases.append(getattr(state.failure, "timeout_case", ABSENT))
            value = times[state.ticks]
            state.ticks += 1
            return value

        def gate(*args):
            state.gates.append(args)
            try:
                return original_gate(*args)
            except BaseException as failure:
                state.failure = failure
                raise

        def mkdir(path, mode=0o777, parents=False, exist_ok=False):
            self.assertEqual((path, mode, parents, exist_ok), (EVIDENCE / "sentinel", 0o700, False, False))
            state.order.append("mkdir")

        def popen(argv, **kwargs):
            self.assertEqual(argv, ["/bin/cat"])
            self.assertEqual(kwargs, dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          close_fds=True, env=context.environment))
            state.order.append("popen")
            if at_popen:
                raise error
            return process

        def pipe_endpoint(actual):
            self.assertIs(actual, process)
            state.order.append("pipes")
            return pipes

        def identity(pid):
            self.assertEqual(pid, 222)
            state.order.append("native-identity")
            return sentinel_identity

        def perform(actual, case, native_end):
            self.assertIs(actual, context)
            self.assertEqual((case, native_end), ("N1", 181 * M.NS))
            state.order.append("case")
            raise error

        def close_stdin():
            state.order.append("stdin-close")
            stdin.closed = True

        def finish(end_ns, directory):
            self.assertEqual((end_ns, directory), (context.abort_end, EVIDENCE / "sentinel"))
            state.order.append("sentinel-finish")
            pipes.closed = True
            return 0, []

        def close_native():
            state.order.append("native-close")
            context.native.closed = True

        def close_output():
            state.order.append("output-close")

        def write_new(path, raw):
            state.order.append("write")
            state.writes.append((path, raw))

        stdin.close, pipes.finish = close_stdin, finish
        context.native.identity, context.native.close = identity, close_native
        context.output = types.SimpleNamespace(close=Mock(side_effect=close_output))
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(M, "shared_raw_ns", side_effect=clock))
            stack.enter_context(patch.object(M, "timeout_left", side_effect=gate))
            stack.enter_context(patch.object(M.Path, "mkdir", autospec=True, side_effect=mkdir))
            state.popen = stack.enter_context(patch.object(M.subprocess, "Popen", side_effect=popen))
            stack.enter_context(patch.object(M, "ProbePipes", side_effect=pipe_endpoint))
            stack.enter_context(patch.object(M.os, "getpid", return_value=111))
            stack.enter_context(patch.object(M, "write_new", side_effect=write_new))
            stack.enter_context(patch.object(M, "_UNCLOSED_COMMANDS", []))
            state.export = stack.enter_context(patch.object(M, "finish_export", side_effect=AssertionError("NO_EXPORT")))
            if error is not ABSENT and not at_popen:
                state.perform = stack.enter_context(patch.object(M, "perform_case", side_effect=perform))
            yield state

    def _no_export(self, state, abort_end):
        context = state.context
        self.assertEqual(context.abort_end, abort_end)
        self.assertFalse(context.finished or context.export_called)
        self.assertIsNone(context.result)
        self.assertEqual(context.case_results, [])
        state.export.assert_not_called()
        self.assertEqual(len(state.writes), 1)
        path, raw = state.writes[0]
        self.assertEqual(path, EVIDENCE / "aborted-no-export.json")
        self.assertEqual(M.parsed(raw), dict(schema=1, scope=M.SCOPE, qualification="REFUSED", exportAllowed=False,
            cleanupErrors=[], adminLifetimeUnknown=False, abortEndNs=abort_end, registrationAttempts=[], signalReturns=[]))

    def test_01_actual_left_send_read_and_entry_boundaries(self):
        end = 40 * M.NS
        original_left = M.left
        returned = []

        def observe_left(deadline, stage):
            result = original_left(deadline, stage)
            returned.append(result)
            return result

        with patch.object(M, "shared_raw_ns", return_value=M.NS) as clock, \
                patch.object(M, "left", side_effect=observe_left) as left:
            result = M.timeout_left(end, "READ_WAIT", 1, "HEADER")
            self.assertEqual(result, 39.0)
            self.assertIs(result, returned[0])
            left.assert_called_once_with(end, "START")
            clock.assert_called_once_with()
        for index, invalid in enumerate((None, True, 1.0, "40", IntegerSubclass(end), Hostile())):
            with self.subTest(invalid_end=index), patch.object(M, "shared_raw_ns") as clock:
                error, codes = self._caught(lambda: M.timeout_left(invalid, "CASE_ENTRY"))
                clock.assert_not_called()
                self.assertEqual(error.timeout_site, ("CASE_ENTRY", None, None))
                self.assertEqual(codes.count(M.left.__code__), 1)
                self.assertEqual(codes.count(M.timeout_left.__code__), 1)
        for deadline in (-1, 0, M.NS - 1, M.NS):
            with patch.object(M, "shared_raw_ns", return_value=M.NS) as clock:
                error, _codes = self._caught(lambda: M.timeout_left(deadline, "NATIVE_ENTRY"))
                clock.assert_called_once_with()
                self.assertEqual(error.timeout_site, ("NATIVE_ENTRY", None, None))
        with patch.object(M, "shared_raw_ns", return_value=M.NS) as clock:
            self.assertEqual(M.timeout_left(M.NS + 1, "CASE_ENTRY"), 1 / M.NS)
            clock.assert_called_once_with()

        unrelated = [M.ExperimentError("START", "REFUSED"), M.ExperimentError("CLOSE", "TIMEOUT"),
                     M.ExperimentError("START", "TIMEOUT", "ETIMEDOUT"), ErrorSubclass("START", "TIMEOUT"),
                     RuntimeError(CANARY), SystemExit(CANARY)]
        for attribute, good in (("stage", "START"), ("reason", "TIMEOUT"), ("errno_name", "NONE")):
            for invalid in (Hostile(), StringSubclass(good)):
                error = M.ExperimentError("START", "TIMEOUT")
                setattr(error, attribute, invalid)
                unrelated.append(error)
        for error in unrelated:
            with patch.object(M, "left", side_effect=error) as left, patch.object(M, "shared_raw_ns") as clock:
                with self.assertRaises(BaseException) as raised:
                    M.timeout_left(end, "SEND_PRE", 2, "FRAME")
                self.assertIs(raised.exception, error)
                self.assertIs(getattr(error, "timeout_site", ABSENT), ABSENT)
                left.assert_called_once_with(end, "START")
                clock.assert_not_called()

        for serial in range(1, 9):
            value, raw, header = frame_bytes(serial)
            wire = header + raw
            row = dict(serial=serial, direction=DIRECTIONS[serial - 1], kind=KINDS[serial - 1],
                       sha256=hashlib.sha256(raw).hexdigest())
            with self.subTest(send=serial), self._wire(times=(M.NS,) * 9, sizes=(2, 3, len(wire) - 5), idle=(1,)) as state:
                trace = []
                self.assertEqual(M.send_frame(state.channel, serial, BINDING, value["payload"], trace, end), value)
                self.assertEqual(bytes(state.sent), wire)
                self.assertEqual(state.pending, [wire, wire[2:], wire[5:]])
                self.assertEqual(state.order, ["clock", "clock", "select"] +
                                 ["clock", "clock", "select", "send"] * 3 + ["clock"])
                self.assertEqual((state.clock_count, trace), (9, [row]))
            chunks = (header[:1], header[1:3], header[3:], raw[:1], raw[1:7], raw[7:])
            with self.subTest(read=serial), self._wire(chunks, times=(M.NS,) * 8, idle=(1,)) as state:
                trace = []
                self.assertEqual(M.read_frame(state.channel, serial, BINDING, trace, end, state.pump), value)
                self.assertEqual(state.requests, [4, 3, 1, len(raw), len(raw) - 1, len(raw) - 7])
                self.assertEqual(state.order, ["pump", "clock", "select"] +
                                 ["pump", "clock", "select", "recv"] * 6 + ["clock"])
                self.assertEqual((state.clock_count, trace), (8, [row]))

        for serial in (2, 5):
            value, raw, header = frame_bytes(serial)
            wire = header + raw
            for site, times, sizes, order, sent in (
                ("SEND_PRE", (end,), (), ["clock"], 0),
                ("SEND_SELECT", (M.NS, end), (), ["clock", "clock"], 0),
                ("SEND_RETURN", (M.NS, M.NS, end), (len(wire),), ["clock", "clock", "select", "send", "clock"], len(wire)),
                ("SEND_PRE", (M.NS, M.NS, end), (2,), ["clock", "clock", "select", "send", "clock"], 2),
                ("SEND_SELECT", (M.NS, M.NS, M.NS, end), (2,), ["clock", "clock", "select", "send", "clock", "clock"], 2),
            ):
                with self.subTest(serial=serial, site=site, sent=sent), self._wire(times=times, sizes=sizes) as state:
                    trace = []
                    error, codes = self._caught(lambda: M.send_frame(state.channel, serial, BINDING, value["payload"], trace, end))
                    self.assertEqual(error.timeout_site, (site, serial, "FRAME"))
                    self.assertEqual((state.order, bytes(state.sent), trace), (order, wire[:sent], []))
                    self.assertEqual(codes.count(M.timeout_left.__code__), 1)
                    self.assertEqual(codes.count(M.left.__code__), 1)
                    self.assertEqual(M.public_error(error), PRIMARY)

        for serial in (1, 4, 8):
            _value, raw, header = frame_bytes(serial)
            loop = ["pump", "clock", "select", "recv"]
            for phase, replies, times, idle, order in (
                ("HEADER", (), (end,), (), ["pump", "clock"]),
                ("HEADER", (header[:2],), (M.NS, end), (), loop + ["pump", "clock"]),
                ("HEADER", (), (M.NS, end), (1,), ["pump", "clock", "select", "pump", "clock"]),
                ("BODY", (header,), (M.NS, end), (), loop + ["pump", "clock"]),
                ("BODY", (header, raw[:2]), (M.NS, M.NS, end), (), loop * 2 + ["pump", "clock"]),
                ("BODY", (header,), (M.NS, M.NS, end), (2,), loop + ["pump", "clock", "select", "pump", "clock"]),
            ):
                with self.subTest(serial=serial, phase=phase, reads=len(replies), idle=idle), \
                        self._wire(replies, times=times, idle=idle) as state:
                    trace = []
                    error, _codes = self._caught(lambda: M.read_frame(state.channel, serial, BINDING, trace, end, state.pump))
                    self.assertEqual(error.timeout_site, ("READ_WAIT", serial, phase))
                    self.assertEqual((state.order, state.position, trace), (order, len(replies), []))
                    self.assertIs(getattr(error, "protocol_eof", ABSENT), ABSENT)
            with self._wire((header, raw), times=(M.NS, M.NS, end)) as state:
                original_validate = M.validate_frame

                def validate(*args):
                    state.order.append("validate")
                    return original_validate(*args)

                trace = []
                with patch.object(M, "validate_frame", side_effect=validate) as observed:
                    error, _codes = self._caught(lambda: M.read_frame(state.channel, serial, BINDING, trace, end, state.pump))
                    observed.assert_called_once()
                self.assertEqual(error.timeout_site, ("READ_RETURN", serial, "FRAME"))
                self.assertEqual(state.order, loop * 2 + ["validate", "clock"])
                self.assertEqual((state.position, trace), (2, []))

            for phase in ("HEADER", "BODY"):
                for partial in (False, True):
                    replies = [] if phase == "HEADER" else [header]
                    if partial:
                        replies.append((header if phase == "HEADER" else raw)[:2])
                    replies.append(b"")
                    with self._wire(replies, times=(M.NS,) * len(replies)) as state:
                        trace = []
                        error, _codes = self._caught(lambda: M.read_frame(state.channel, serial, BINDING, trace, end, state.pump),
                                                    ("START", "STATUS_MISSING", "NONE"))
                        self.assertEqual(error.protocol_eof, (serial, phase, "PARTIAL" if partial else "EMPTY"))
                        self.assertIs(getattr(error, "timeout_site", ABSENT), ABSENT)
                        self.assertIsNone(M.public_timeout_site(error))
                        self.assertEqual(trace, [])

        for endpoint in ("pump", "select", "recv", "send", "send-select"):
            error = M.ExperimentError("START", "TIMEOUT")
            options = {endpoint + "_error": error} if endpoint in ("pump", "select", "send") else {}
            if endpoint == "send-select":
                options["select_error"] = error
            times = () if endpoint == "pump" else (M.NS,) * (2 if endpoint.startswith("send") else 1)
            with self._wire((error,) if endpoint == "recv" else (), times=times, **options) as state:
                trace = []
                with self.assertRaises(M.ExperimentError) as raised:
                    if endpoint.startswith("send"):
                        M.send_frame(state.channel, 2, BINDING, {}, trace, end)
                    else:
                        M.read_frame(state.channel, 1, BINDING, trace, end, state.pump)
                self.assertIs(raised.exception, error)
                self.assertIs(getattr(error, "timeout_site", ABSENT), ABSENT)
                self.assertIsNone(M.public_timeout_site(error))
                self.assertEqual(trace, [])

        value, raw, _header = frame_bytes(1)
        wrong = M.encoded(dict(value, binding="b" * 64))
        for replies, expected in (
            ([(b"", [], 1, None)], ("START", "REFUSED", "NONE")),
            ([(b"", [(-1, -1, b"synthetic")], 0, None)], ("START", "REFUSED", "NONE")),
            ([PermissionError(errno.EACCES, CANARY)], ("START", "PERMISSION_DENIED", "EACCES")),
            ([struct.pack("!I", 0)], ("START", "BOUND", "NONE")),
            ([struct.pack("!I", M.FRAME_BYTES + 1)], ("START", "BOUND", "NONE")),
            ([struct.pack("!I", len(raw) + 1), raw + b" "], ("START", "REFUSED", "NONE")),
            ([struct.pack("!I", len(wrong)), wrong], ("START", "IDENTITY_CHANGED", "NONE")),
        ):
            with self._wire(replies, times=(M.NS,) * len(replies)) as state:
                trace = []
                with self.assertRaises(M.ExperimentError) as raised:
                    M.read_frame(state.channel, 1, BINDING, trace, end)
                self.assertEqual((raised.exception.stage, raised.exception.reason, raised.exception.errno_name), expected)
                self.assertIs(getattr(raised.exception, "timeout_site", ABSENT), ABSENT)
                self.assertEqual(trace, [])
        with self._wire(times=(M.NS, M.NS), sizes=(0,)) as state:
            error, _codes = self._caught(lambda: M.send_frame(state.channel, 2, BINDING, {}, [], end),
                                        ("START", "RETURN_FAILED", "NONE"))
            self.assertIs(getattr(error, "timeout_site", ABSENT), ABSENT)

        # Positive real case entry stops at the first memory-only mkdir. Failure
        # real case entry stops before it; no later case machinery is substituted.
        for index, case in enumerate(M.CASES):
            context = M.Context.__new__(M.Context)
            context.case_results, context.abort_end, context.current = [None] * index, None, None
            context.step_end = context.job_end = context.policy_end = 720 * M.NS
            context.evidence = EVIDENCE
            stop = M.ExperimentError("PREPARE", "REFUSED")
            with patch.object(M, "shared_raw_ns", side_effect=(M.NS, M.NS)) as clock, \
                    patch.object(M.Path, "mkdir", autospec=True, side_effect=stop) as mkdir, \
                    patch.object(M, "timeout_left", wraps=M.timeout_left) as gate:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.perform_case(context, case, 30 * M.NS)
                self.assertIs(raised.exception, stop)
                gate.assert_called_once_with(30 * M.NS, "CASE_ENTRY")
                mkdir.assert_called_once_with(EVIDENCE / case, mode=0o700)
                self.assertEqual(clock.call_count, 2)
            with patch.object(M, "shared_raw_ns", side_effect=(M.NS, M.NS)) as clock, \
                    patch.object(M.Path, "mkdir", autospec=True) as mkdir:
                error, _codes = self._caught(lambda: M.perform_case(context, case, M.NS))
                self.assertEqual(error.timeout_site, ("CASE_ENTRY", None, None))
                mkdir.assert_not_called()
                self.assertEqual(clock.call_count, 2)
                self.assertIsNone(context.current)

        stop = M.ExperimentError("IDENTITY", "REFUSED")
        with self._foreground((M.NS,) * 3, error=stop, at_popen=True) as state:
            with self.assertRaises(M.ExperimentError) as raised:
                M.run_cases(state.context)
            self.assertIs(raised.exception, stop)
            self.assertIs(getattr(stop, "timeout_site", ABSENT), ABSENT)
            self.assertEqual(state.gates, [(181 * M.NS, "NATIVE_ENTRY")])
            state.popen.assert_called_once()
            self._no_export(state, 121 * M.NS)
        with self._foreground((M.NS, 181 * M.NS, 182 * M.NS)) as state:
            error, _codes = self._caught(lambda: M.run_cases(state.context))
            self.assertEqual(error.timeout_site, ("NATIVE_ENTRY", None, None))
            self.assertIs(getattr(error, "timeout_case", ABSENT), ABSENT)
            self.assertEqual(state.order, ["clock", "mkdir", "clock", "clock", "native-close", "output-close", "write"])
            state.popen.assert_not_called()
            self._no_export(state, 302 * M.NS)

    def test_02_forward_guard_case_wrapper_and_original_abort(self):
        def validate(fixture):
            return M.validate_final_frame(fixture.payload, "N4", fixture.prepared, fixture.observed, fixture.ready, fixture.start)

        for started, returned in ((2 * M.NS, 3 * M.NS), (2 * M.NS, 2 * M.NS), (1, 40 * M.NS - 1)):
            fixture = final_fixture()
            fixture.payload["startForward"] = dict(startedMonotonicNs=started, returnedMonotonicNs=returned)
            fixture.observed[-1] = M.frame_record(M.frame_value(8, BINDING, fixture.payload))
            fixture.trace[-1] = fixture.observed[-1]
            with patch.object(M, "shared_raw_ns", side_effect=AssertionError("NO_FORWARD_CLOCK")) as clock:
                probe, trace = validate(fixture)
                self.assertIs(probe, fixture.probe)
                self.assertEqual(trace, fixture.trace)
                self.assertEqual(fixture.prepared.reads, ["binding", "caseEndNs", "binding", "caseEndNs"])
                clock.assert_not_called()

        class MappingSubclass(dict):
            def forbidden(self, *_args):
                raise AssertionError("UNTRUSTED_FORWARD_MAPPING_OPERATION")
            __iter__ = __getitem__ = values = forbidden

        # Direct data faults exercise each independent clause of the ORIGINAL
        # compound guard. None is presented as a measured elapsed timeout.
        good = dict(startedMonotonicNs=2 * M.NS, returnedMonotonicNs=3 * M.NS)
        invalid = (
            (None, False), ([], False), (Hostile(), False), (MappingSubclass(good), False),
            ({}, False), ({"startedMonotonicNs": 2 * M.NS}, False), (dict(good, extra=1), False),
            (dict(good, startedMonotonicNs=True), False), (dict(good, returnedMonotonicNs=3.0), False),
            (dict(good, startedMonotonicNs=IntegerSubclass(2 * M.NS)), False),
            (dict(good, returnedMonotonicNs=Hostile()), False),
            (dict(good, startedMonotonicNs=0), False), (dict(good, returnedMonotonicNs=0), False),
            (dict(good, startedMonotonicNs=-1), False), (dict(good, startedMonotonicNs=4 * M.NS), False),
            (dict(good, returnedMonotonicNs=40 * M.NS), True), (dict(good, returnedMonotonicNs=41 * M.NS), True),
        )
        for index, (forward, reached_end) in enumerate(invalid):
            fixture = final_fixture()
            fixture.payload["startForward"] = forward
            with self.subTest(forward_clause=index), patch.object(M, "shared_raw_ns") as clock:
                error, codes = self._caught(lambda: validate(fixture))
                self.assertEqual(error.timeout_site, ("FORWARD_TIME", 8, "FRAME"))
                self.assertIs(getattr(error, "timeout_case", ABSENT), ABSENT)
                self.assertEqual(codes.count(M.validate_final_frame.__code__), 1)
                self.assertEqual(fixture.prepared.reads, ["binding"] + (["caseEndNs"] if reached_end else []))
                self.assertEqual(M.public_error(error), PRIMARY)
                clock.assert_not_called()

        for fault, expected in (
            ("initial", ("CHILD_WAIT", "RESOURCE_UNKNOWN", "NONE")),
            ("trace", ("START", "REFUSED", "NONE")),
            ("prefix", ("START", "IDENTITY_CHANGED", "NONE")),
            ("after", ("CLOSE", "REFUSED", "NONE")),
            ("probe-time", ("NATIVE_SEND", "TIMEOUT", "NONE")),
        ):
            fixture = final_fixture()
            if fault == "initial":
                fixture.payload["producerControlEof"] = False
            elif fault == "trace":
                fixture.payload["tracePrefix"] = None
            elif fault == "prefix":
                fixture.payload["tracePrefix"][0] = dict(fixture.payload["tracePrefix"][0], sha256="b" * 64)
            elif fault == "after":
                fixture.payload["signalReturns"] = None
            else:
                fixture.observation["finishedMonotonicNs"] = 40 * M.NS
                fixture.payload["tracePrefix"][-1] = M.frame_record(fixture.payload["resultFrame"])
                fixture.observed[-1] = M.frame_record(M.frame_value(8, BINDING, fixture.payload))
            with patch.object(M, "shared_raw_ns") as clock:
                error, _codes = self._caught(lambda: validate(fixture), expected)
                self.assertIs(getattr(error, "timeout_site", ABSENT), ABSENT)
                clock.assert_not_called()

        context, end, result = Hostile(), Hostile(), object()
        with patch.object(M, "perform_case", return_value=result) as perform, patch.object(M, "shared_raw_ns") as clock:
            self.assertIs(M.perform_case_with_timeout(context, "N2", end), result)
            perform.assert_called_once()
            for actual, original in zip(perform.call_args.args, (context, "N2", end)):
                self.assertIs(actual, original)
            clock.assert_not_called()

        cases = [(case, case) for case in M.CASES]
        cases.extend((case, "UNKNOWN") for case in (None, True, 1, CANARY, StringSubclass("N1"), Hostile()))
        for index, (case, expected) in enumerate(cases):
            with patch.object(M, "shared_raw_ns", return_value=M.NS):
                error, _codes = self._caught(lambda: M.timeout_left(M.NS, "CASE_ENTRY"))
            before = dict(error.__dict__)
            with self.subTest(held_case=index), patch.object(M, "perform_case", side_effect=error) as perform, \
                    patch.object(M, "shared_raw_ns") as clock:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.perform_case_with_timeout(context, case, end)
                self.assertIs(raised.exception, error)
                perform.assert_called_once()
                for actual, original in zip(perform.call_args.args, (context, case, end)):
                    self.assertIs(actual, original)
                self.assertEqual(error.__dict__, {**before, "timeout_case": expected})
                self.assertEqual(error.args, ("START/TIMEOUT/NONE",))
                clock.assert_not_called()

        errors = [M.ExperimentError("START", "TIMEOUT"), M.ExperimentError("START", "REFUSED"),
                  M.ExperimentError("CLOSE", "TIMEOUT"), M.ExperimentError("START", "TIMEOUT", "ETIMEDOUT"),
                  ErrorSubclass("START", "TIMEOUT"), RuntimeError(CANARY), SystemExit(CANARY)]
        for error in errors[1:]:
            error.timeout_site = ("READ_WAIT", 4, "BODY")
        for fields in (None, (), ("CASE_ENTRY",), ("CASE_ENTRY", None), ("CASE_ENTRY", None, None, 0),
                       ["CASE_ENTRY", None, None], TupleSubclass(("CASE_ENTRY", None, None)), Hostile()):
            error = M.ExperimentError("START", "TIMEOUT")
            error.timeout_site = fields
            errors.append(error)
        for attribute, good in (("stage", "START"), ("reason", "TIMEOUT"), ("errno_name", "NONE")):
            for bad in (StringSubclass(good), Hostile()):
                error = M.ExperimentError("START", "TIMEOUT")
                error.timeout_site = ("CASE_ENTRY", None, None)
                setattr(error, attribute, bad)
                errors.append(error)
        for error in errors:
            fields = getattr(error, "timeout_site", ABSENT)
            with patch.object(M, "perform_case", side_effect=error) as perform, patch.object(M, "shared_raw_ns") as clock:
                with self.assertRaises(BaseException) as raised:
                    M.perform_case_with_timeout(context, "N3", end)
                self.assertIs(raised.exception, error)
                self.assertIs(getattr(error, "timeout_site", ABSENT), fields)
                self.assertIs(getattr(error, "timeout_case", ABSENT), ABSENT)
                perform.assert_called_once()
                clock.assert_not_called()

        # The fourth original clock is the case-entry refusal. The fifth is
        # abort_suite's original nonrenewable limit and already sees the case.
        times = (M.NS, M.NS, M.NS, 41 * M.NS, 42 * M.NS, 42 * M.NS)
        with self._foreground(times) as state:
            error, codes = self._caught(lambda: M.run_cases(state.context))
            self.assertEqual(error.timeout_site, ("CASE_ENTRY", None, None))
            self.assertEqual(error.timeout_case, "N1")
            self.assertEqual(codes.count(M.perform_case.__code__), 1)
            self.assertEqual(codes.count(M.perform_case_with_timeout.__code__), 1)
            self.assertEqual(codes.count(M.run_cases.__code__), 1)
            self.assertEqual(state.gates, [(181 * M.NS, "NATIVE_ENTRY"), (41 * M.NS, "CASE_ENTRY")])
            self.assertEqual(state.clock_cases, [ABSENT] * 4 + ["N1", "N1"])
            self.assertEqual(state.order, ["clock", "mkdir", "clock", "popen", "pipes", "native-identity", "clock", "clock",
                                          "clock", "stdin-close", "sentinel-finish", "clock", "native-close", "output-close", "write"])
            self.assertTrue(state.context.sentinel_closed and state.context.native.closed)
            self._no_export(state, 162 * M.NS)

        _value, _raw, header = frame_bytes(4)
        with self._wire((header,), times=(M.NS, 40 * M.NS)) as wire:
            error, _codes = self._caught(lambda: M.read_frame(wire.channel, 4, BINDING, [], 40 * M.NS))
        with self._foreground((M.NS,) * 4, error=error) as state:
            with self.assertRaises(M.ExperimentError) as raised:
                M.run_cases(state.context)
            self.assertIs(raised.exception, error)
            state.perform.assert_called_once_with(state.context, "N1", 181 * M.NS)
            self.assertEqual((error.timeout_site, error.timeout_case), (("READ_WAIT", 4, "BODY"), "N1"))
            self.assertEqual(state.clock_cases, [ABSENT, ABSENT, "N1", "N1"])
            self._no_export(state, 121 * M.NS)
        plain = M.ExperimentError("START", "TIMEOUT")
        with self._foreground((M.NS,) * 4, error=plain) as state:
            with self.assertRaises(M.ExperimentError) as raised:
                M.run_cases(state.context)
            self.assertIs(raised.exception, plain)
            self.assertIs(getattr(plain, "timeout_case", ABSENT), ABSENT)
            self.assertEqual(state.clock_cases, [ABSENT] * 4)
            self._no_export(state, 121 * M.NS)

    def test_03_finite_formatter_and_actual_main_preserve_failure(self):
        for case in (*M.CASES, None):
            for site in SITES:
                for serial in (None, *range(1, 9)):
                    for phase in (None, "HEADER", "BODY", "FRAME"):
                        error = M.ExperimentError("START", "TIMEOUT")
                        error.timeout_site, error.timeout_case = (site, serial, phase), case
                        expected = (case if case is not None else "UNKNOWN", site,
                                    "NONE" if serial is None else "F" + str(serial), "NONE" if phase is None else phase)
                        public = M.public_timeout_site(error)
                        self.assertEqual(public, PREFIX + "|".join(expected))
                        self.assertLessEqual(len(public), 96)
                        self.assertEqual(M.public_error(error), PRIMARY)

        invalid = (None, True, False, -1, 0, 9, 1.0, [], {}, b"FRAME", "NONE",
                   CANARY + "\n::error::" + CANARY, Hostile())
        valid = ("N1", "READ_WAIT", 4, "BODY")
        subclasses = (StringSubclass("N1"), StringSubclass("READ_WAIT"), IntegerSubclass(4), StringSubclass("BODY"))
        for index in range(4):
            for bad in (*invalid, subclasses[index]):
                fields = list(valid)
                fields[index] = bad
                error = M.ExperimentError("START", "TIMEOUT")
                error.timeout_case, error.timeout_site = fields[0], tuple(fields[1:])
                expected = ["N1", "READ_WAIT", "F4", "BODY"]
                expected[index] = "NONE" if bad is None and index in (2, 3) else "UNKNOWN"
                public = M.public_timeout_site(error)
                self.assertEqual(public, PREFIX + "|".join(expected))
                self.assertLessEqual(len(public), 96)
                self.assertNotIn(CANARY, public)
                self.assertNotIn("\n", public)
        self.assertIsNone(M.public_timeout_site(M.ExperimentError("START", "TIMEOUT")))
        for fields in (None, (), ("CASE_ENTRY",), ("CASE_ENTRY", None), ("CASE_ENTRY", None, None, 0),
                       ["CASE_ENTRY", None, None], TupleSubclass(("CASE_ENTRY", None, None)), Hostile()):
            error = M.ExperimentError("START", "TIMEOUT")
            error.timeout_site = fields
            self.assertIsNone(M.public_timeout_site(error))
        for attribute, good in (("stage", "START"), ("reason", "TIMEOUT"), ("errno_name", "NONE")):
            for bad in (*invalid, StringSubclass(good)):
                # NONE is the one legitimate errno in this otherwise-bad set.
                if attribute == "errno_name" and type(bad) is str and bad == "NONE":
                    continue
                error = M.ExperimentError("START", "TIMEOUT")
                error.timeout_site = ("CASE_ENTRY", None, None)
                setattr(error, attribute, bad)
                self.assertIsNone(M.public_timeout_site(error))
        for error in (M.ExperimentError("CLOSE", "TIMEOUT"), M.ExperimentError("START", "REFUSED"),
                      M.ExperimentError("START", "TIMEOUT", "ETIMEDOUT"), ErrorSubclass("START", "TIMEOUT"),
                      RuntimeError(CANARY), SystemExit(CANARY), Hostile()):
            error.timeout_site = ("READ_WAIT", 8, "BODY")
            self.assertIsNone(M.public_timeout_site(error))

        _value, _raw, header = frame_bytes(8)
        with self._wire((header,), times=(M.NS, 40 * M.NS)) as state:
            annotated, _codes = self._caught(lambda: M.read_frame(state.channel, 8, BINDING, [], 40 * M.NS))
        annotated.private_context = CANARY + "\n::error::" + CANARY
        with self._wire((b"",), times=(M.NS,)) as state:
            eof, _codes = self._caught(lambda: M.read_frame(state.channel, 4, BINDING, [], 40 * M.NS),
                                      ("START", "STATUS_MISSING", "NONE"))
        plain = M.ExperimentError("START", "TIMEOUT")
        other_errno = M.ExperimentError("START", "TIMEOUT", "ETIMEDOUT")
        unrelated = M.ExperimentError("START", "REFUSED")
        for error in (other_errno, unrelated):
            error.timeout_site = ("READ_WAIT", 8, "BODY")
        cases = (
            ((M.NS, 181 * M.NS, 182 * M.NS), {}, PRIMARY + "\n" + PREFIX + "UNKNOWN|NATIVE_ENTRY|NONE|NONE\n", 302 * M.NS),
            ((M.NS, M.NS, M.NS, 41 * M.NS, 42 * M.NS, 42 * M.NS), {},
             PRIMARY + "\n" + PREFIX + "N1|CASE_ENTRY|NONE|NONE\n", 162 * M.NS),
            ((M.NS,) * 4, {"error": annotated}, PRIMARY + "\n" + PREFIX + "N1|READ_WAIT|F8|BODY\n", 121 * M.NS),
            ((M.NS,) * 4, {"error": plain}, PRIMARY + "\n", 121 * M.NS),
            ((M.NS,) * 4, {"error": other_errno}, "P2PKIT_CONTEXT_FAILURE|START|TIMEOUT|ETIMEDOUT\n", 121 * M.NS),
            ((M.NS,) * 4, {"error": unrelated}, "P2PKIT_CONTEXT_FAILURE|START|REFUSED|NONE\n", 121 * M.NS),
            ((M.NS,) * 4, {"error": eof}, "P2PKIT_CONTEXT_FAILURE|START|STATUS_MISSING|NONE\n"
             "P2PKIT_CONTEXT_PROTOCOL_EOF|UNKNOWN|F4|HEADER|EMPTY\n", 121 * M.NS),
            ((M.NS,) * 3, {"error": RuntimeError(CANARY), "at_popen": True},
             "P2PKIT_CONTEXT_FAILURE|IDENTITY|REFUSED|UNKNOWN\n", 121 * M.NS),
        )
        for index, (times, options, expected, abort_end) in enumerate(cases):
            output = io.StringIO()
            with self.subTest(main_case=index), self._foreground(times, **options) as state, \
                    patch.object(M, "prepare", return_value=state.context) as prepare, \
                    patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]), \
                    patch.object(M.os, "umask") as umask, contextlib.redirect_stdout(output):
                self.assertEqual(M.main(), 2)
                prepare.assert_called_once_with()
                umask.assert_called_once_with(0o077)
                self.assertEqual(state.context.output.close.call_count, 2)  # Original abort plus experiment finally.
                self._no_export(state, abort_end)
            self.assertEqual(output.getvalue(), expected)
            self.assertIn(len(output.getvalue().splitlines()), (1, 2))
            self.assertNotIn(CANARY, output.getvalue())

    def test_04_exact_inverse_raw_hunks_and_guard_mutations(self):
        source = SOURCE.read_text(encoding="utf-8")
        hashes = (
            PREIMAGE,
            "e92c291407c4b1f6f000a675c07190b34c340cd6b17648e5d73fd8a610e9acac",
            "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf",
            "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b",
            "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d",
        )
        self.assertEqual((CLOCK.PROTOCOL_TIMEOUT_BASE_RUNTIME_SHA256, CLOCK.PROTOCOL_EOF_BASE_RUNTIME_SHA256,
                          CLOCK.PLIST_NAME_BASE_RUNTIME_SHA256, CLOCK.ADMIN_RETURN_BASE_RUNTIME_SHA256,
                          CLOCK.BASE_RUNTIME_SHA256), hashes)
        self.assertEqual((CLOCK.BASE_WORKFLOW_SHA256, CLOCK.BASE_EXPERIMENT_TEST_SHA256), (
            "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40",
            "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768",
        ))
        restores = (CLOCK.restore_protocol_timeout_runtime, CLOCK.restore_protocol_eof_runtime,
                    CLOCK.restore_plist_name_runtime, CLOCK.restore_admin_return_runtime, CLOCK.restore_runtime)
        for restore, expected in zip(restores, hashes):
            self.assertEqual(hashlib.sha256(restore(source).encode("utf-8")).hexdigest(), expected)
        for restore in restores[1:]:
            with patch.object(CLOCK, "restore_protocol_timeout_runtime", wraps=restores[0]) as newest:
                restore(source)
                newest.assert_called_once_with(source)
        self.assertEqual((len(CLOCK.PROTOCOL_TIMEOUT_PATCH), len(CLOCK.PROTOCOL_EOF_PATCH),
                          len(CLOCK.PLIST_NAME_PATCH), len(CLOCK.ADMIN_RETURN_PATCH)), (13, 7, 3, 8))

        # Current RAW containment remains load-bearing for every old suite.
        for before, after in (*CLOCK.PROTOCOL_EOF_PATCH, *CLOCK.PLIST_NAME_PATCH, *CLOCK.ADMIN_RETURN_PATCH):
            self.assertEqual(source.count(after), 1)
            for changed in (source.replace(after, before, 1), source + after):
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(changed)
        for before, after in CLOCK.PROTOCOL_TIMEOUT_PATCH:
            self.assertEqual(source.count(after), 1)
            for changed in (source.replace(after, before, 1), source + after,
                            source.replace(after, after + "# SYNTHETIC_PARTIAL_DELTA\n", 1)):
                self.assertNotEqual(changed, source)
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(changed)
        preimage = restores[0](source)
        for bad in (None, b"", "", StringSubclass(source), preimage, restores[1](source), source + "\n# UNRELATED_MUTATION\n"):
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(bad)
        for patches in (CLOCK.PROTOCOL_TIMEOUT_PATCH[:-1], CLOCK.PROTOCOL_TIMEOUT_PATCH + CLOCK.PROTOCOL_TIMEOUT_PATCH[:1]):
            with patch.object(CLOCK, "PROTOCOL_TIMEOUT_PATCH", patches):
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(source)
        for before, after in (
            ("type(error) is not ExperimentError", "not isinstance(error, ExperimentError)"),
            ('type(error.errno_name) is str and error.stage == "START"', 'error.stage == "START"'),
            ('return left(end_ns, "START")', 'return left(end_ns + NS, "START")'),
            ('require(type(end_ns) is int, stage, "TIMEOUT")', 'require(True, stage, "TIMEOUT")'),
            ('require(remaining > 0, stage, "TIMEOUT")', 'require(remaining >= 0, stage, "TIMEOUT")'),
            ('error.timeout_site = (site, serial, phase)', 'error.timeout_site = (site, 8, "FRAME")'),
            ('forward["returnedMonotonicNs"] < prepared["caseEndNs"]', 'forward["returnedMonotonicNs"] <= prepared["caseEndNs"]'),
            ('return perform_case(context, case, native_end)', 'return None'),
            ('error.timeout_case = case if type(case) is str and case in CASES else "UNKNOWN"', 'error.timeout_case = "N4"'),
            ('            perform_case_with_timeout(context, case, native_end)', '            perform_case(context, case, native_end)'),
            ('require(part, "START", "STATUS_MISSING")', 'require(True, "START", "STATUS_MISSING")'),
            ("len(trace) < 8", "len(trace) < 9"),
            ("self.calls < 96", "self.calls < 97"),
            ("CASE_SECONDS = 120, 180, 40", "CASE_SECONDS = 120, 180, 41"),
            ("(end_ns - shared_raw_ns())", "(end_ns - time.monotonic_ns())"),
        ):
            changed = source.replace(before, after, 1)
            self.assertNotEqual(changed, source)
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(changed)

        tree = ast.parse(source, feature_version=(3, 9))
        clocks, sites = {}, {}

        def inspect(node, owners=()):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                owners += (node.name,)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "shared_raw_ns":
                    self.assertFalse(node.args or node.keywords)
                    name = ".".join(owners)
                    clocks[name] = clocks.get(name, 0) + 1
                if isinstance(node.func, ast.Name) and node.func.id == "timeout_left":
                    self.assertFalse(node.keywords)
                    self.assertIn(len(node.args), (2, 4))
                    self.assertIsInstance(node.args[1], ast.Constant)
                    sites.setdefault(".".join(owners), []).append(node.args[1].value)
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "time":
                    self.assertNotIn(node.func.attr, {"monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns"})
            for child in ast.iter_child_nodes(node):
                inspect(child, owners)

        inspect(tree)
        self.assertEqual(clocks, {"left": 1, "capture_fixed": 1, "Darwin.watch": 3, "Darwin.signal": 2,
            "native_probe": 7, "Admin._run": 2, "service": 2, "Context.__init__": 1, "Context.limit": 1,
            "prepare": 2, "perform_case": 4, "close_sentinel": 1, "run_cases": 1, "finish_export": 2, "upload_guard": 3})
        self.assertEqual(sites, {"send_frame": ["SEND_PRE", "SEND_SELECT", "SEND_RETURN"],
            "read_frame.exact": ["READ_WAIT"], "read_frame": ["READ_RETURN"],
            "perform_case": ["CASE_ENTRY"], "run_cases": ["NATIVE_ENTRY"]})
        for name in ("perform_case", "perform_case_with_timeout"):
            self.assertEqual(sum(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name
                                 for node in ast.walk(tree)), 1)

        # AST comparison is inert: never compile/import/execute a preimage.
        before_tree = ast.parse(preimage, feature_version=(3, 9))
        current_functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        before_functions = {node.name: node for node in before_tree.body if isinstance(node, ast.FunctionDef)}
        self.assertEqual(ast.dump(current_functions["left"]), ast.dump(before_functions["left"]))

        def forward_predicate(function):
            values = [node.args[0] for node in ast.walk(function) if isinstance(node, ast.Call) and
                      isinstance(node.func, ast.Name) and node.func.id == "require" and len(node.args) >= 3 and
                      isinstance(node.args[1], ast.Constant) and node.args[1].value == "START" and
                      isinstance(node.args[2], ast.Constant) and node.args[2].value == "TIMEOUT"]
            self.assertEqual(len(values), 1)
            return ast.dump(values[0])

        self.assertEqual(forward_predicate(current_functions["validate_final_frame"]),
                         forward_predicate(before_functions["validate_final_frame"]))
        self.assertEqual((M.JOB_SECONDS, M.STEP_SECONDS, M.PREPARE_SECONDS, M.NATIVE_SECONDS, M.CASE_SECONDS,
                          M.ABORT_SECONDS, M.FREEZE_SECONDS, M.EXPORT_SECONDS, M.UPLOAD_SECONDS, M.ADMIN_SECONDS),
                         (1440, 720, 120, 180, 40, 120, 60, 120, 420, 10))
        for relative, expected in (
            ("scripts/tests/hosted-darwin-context-protocol-eof-test.py", "b214695509227ab5acea119c87c1beb7adf4f2faffcff41fe3ba8b00d0dcc6d2"),
            (".github/workflows/darwin-native-context-experiment.yml", "46dd83658e256ed4c14ebe376addaac7f73b4cd40552b13853515d9c1f5d5933"),
            (".github/test-evidence-recipient.json", "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"),
            ("AGENTS.md", "3ca3ef11f49ba90152754fb9d884ed353a5bc549b0ab648e182d889d4283d84b"),
            ("CLAUDE.md", "0fd0e8bdd297e16caabc40e87411c377f674769a40b73a35f43818bf9f97a71d"),
        ):
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)


if __name__ == "__main__":
    if tuple(unittest.defaultTestLoader.getTestCaseNames(ProtocolTimeout)) != METHODS:
        raise SystemExit("FIXED_FOUR_PROTOCOL_TIMEOUT_METHODS_REQUIRED")
    suite = unittest.TestSuite(ProtocolTimeout(name) for name in METHODS)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
