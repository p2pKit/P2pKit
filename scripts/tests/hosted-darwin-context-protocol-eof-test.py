#!/usr/bin/env python3
"""Four offline required-frame EOF controls, not native/protocol qualification.

Current reader, validators, foreground catch/abort and main execute against
memory-only channel/process/native/filesystem endpoints. No prior suite or
reconstructed source executes. No payload/private original is acquired.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-protocol-eof-test.py
"""
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
    "test_01_actual_read_frame_positive_and_eof_boundaries",
    "test_02_actual_run_cases_annotates_before_abort_and_reraises",
    "test_03_finite_formatter_and_actual_main_preserve_failure",
    "test_04_exact_inverse_and_legacy_raw_hunk_containment",
)
PREIMAGE = "e92c291407c4b1f6f000a675c07190b34c340cd6b17648e5d73fd8a610e9acac"
BINDING = "a" * 64
CANARY = "SYNTHETIC_PROTOCOL_EOF_CANARY"
PRIMARY = "P2PKIT_CONTEXT_FAILURE|START|STATUS_MISSING|NONE"
PREFIX = "P2PKIT_CONTEXT_PROTOCOL_EOF|"
EVIDENCE = Path("/synthetic/protocol-eof/evidence")
ABSENT = object()
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
        raise AssertionError("OFFLINE_PROTOCOL_EOF_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_PROTOCOL_EOF_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_protocol_eof_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
clock_spec = importlib.util.spec_from_file_location("darwin_context_clock_inverse", INVERSE)
CLOCK = importlib.util.module_from_spec(clock_spec)
clock_spec.loader.exec_module(CLOCK)


def frame_bytes(serial):
    value = dict(schema=1, serial=serial, kind=KINDS[serial - 1], binding=BINDING, payload={"synthetic": CANARY})
    raw = M.encoded(value)
    return value, raw, struct.pack("!I", len(raw))


def held_state(case):
    return dict(case=case, directory=EVIDENCE / "held", channel=None, listener=None, admin=None,
                producer=None, service=None, prepareSent=False, socket=None)


class ProtocolEOF(unittest.TestCase):
    @contextlib.contextmanager
    def _channel(self, replies, *, idle_first=False, pump_error=None, select_error=None):
        state = types.SimpleNamespace(order=[], requests=[], position=0, selections=0)

        class Channel:
            def recvmsg(channel, size, space):
                state.order.append("recv")
                state.requests.append(size)
                self.assertEqual(space, socket.CMSG_SPACE(16))
                self.assertLess(state.position, len(replies), "NO_EXTRA_SYNTHETIC_RECV")
                reply = replies[state.position]
                state.position += 1
                if isinstance(reply, BaseException):
                    raise reply
                result = reply if type(reply) is tuple else (reply, [], 0, None)
                self.assertLessEqual(len(result[0]), size)
                return result

        channel = state.channel = Channel()

        def clock():
            state.order.append("clock")
            return M.NS

        def pump():
            state.order.append("pump")
            if pump_error is not None:
                raise pump_error

        def select(read, write, exceptional, timeout):
            state.order.append("select")
            self.assertEqual((read, write, exceptional, timeout), ([channel], [], [], 0.05))
            state.selections += 1
            if select_error is not None:
                raise select_error
            return ([] if idle_first and state.selections == 1 else [channel]), [], []

        state.pump = pump
        with patch.object(M, "shared_raw_ns", side_effect=clock), patch.object(M.select, "select", side_effect=select):
            yield state

    def _eof(self, serial, phase, progress):
        """Generate the actual require exception, without replacing require."""
        _value, raw, header = frame_bytes(serial)
        chunks = [] if phase == "HEADER" else [header]
        if progress == "PARTIAL":
            chunks.append((header if phase == "HEADER" else raw)[:2])
        chunks.extend((b"", b"UNREACHED"))
        trace = []
        with self._channel(chunks) as state:
            try:
                M.read_frame(state.channel, serial, BINDING, trace, 40 * M.NS, pump=state.pump)
            except M.ExperimentError as error:
                original = error
                codes, traceback = [], error.__traceback__
                while traceback is not None:
                    codes.append(traceback.tb_frame.f_code)
                    traceback = traceback.tb_next
                self.assertIs(codes[-1], M.require.__code__)
                self.assertEqual(codes[-2].co_name, "exact")
                self.assertEqual(codes.count(M.read_frame.__code__), 1)
                self.assertIsNone(error.__context__)  # No replacement/wrapping of the original guard error.
            else:
                self.fail("REQUIRED_FRAME_EOF_DID_NOT_REFUSE")
            expected = [4]
            if phase == "HEADER" and progress == "PARTIAL":
                expected.append(2)
            if phase == "BODY":
                expected.append(len(raw))
                if progress == "PARTIAL":
                    expected.append(len(raw) - 2)
            self.assertEqual(state.requests, expected)
            self.assertEqual(state.position, len(chunks) - 1)
            self.assertEqual(state.order, ["pump", "clock", "select", "recv"] * len(expected))
        self.assertEqual(trace, [])
        self.assertEqual(original.args, ("START/STATUS_MISSING/NONE",))
        self.assertEqual(original.protocol_eof, (serial, phase, progress))
        self.assertIs(getattr(original, "protocol_eof_case", ABSENT), ABSENT)
        self.assertEqual(M.public_error(original), PRIMARY)
        self.assertEqual(M.public_protocol_eof(original), PREFIX + "UNKNOWN|F" + str(serial) + "|" + phase + "|" + progress)
        return original

    @contextlib.contextmanager
    def _foreground(self, error, current):
        """Inject held failure at fake Popen; actual run_cases and abort execute."""
        state = types.SimpleNamespace(order=[], clock_cases=[], writes=[])
        context = state.context = M.Context.__new__(M.Context)
        context.finished = context.export_called = context.sentinel_closed = False
        context.abort_end = context.result = context.sentinel = context.sentinel_pipes = None
        context.current, context.case_results = current, []
        context.evidence, context.environment = EVIDENCE, {"PATH": "/usr/bin:/bin", "LANG": "C"}
        context.step_end, context.job_end, context.policy_end = 720 * M.NS, 1440 * M.NS, 1440 * M.NS
        context.native = types.SimpleNamespace(closed=False, watched={}, events={}, attach_attempts=[], signals=[])

        def clock():
            state.order.append("clock")
            state.clock_cases.append(getattr(error, "protocol_eof_case", ABSENT))
            return M.NS

        def mkdir(path, mode=0o777, parents=False, exist_ok=False):
            self.assertEqual((path, mode, parents, exist_ok), (EVIDENCE / "sentinel", 0o700, False, False))
            state.order.append("mkdir")

        def popen(argv, **kwargs):
            self.assertEqual(argv, ["/bin/cat"])
            self.assertEqual(kwargs, dict(stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                          close_fds=True, env=context.environment))
            state.order.append("popen")
            raise error

        def poll():
            state.order.append("native-poll")

        def close_native():
            state.order.append("native-close")
            context.native.closed = True

        def close_output():
            state.order.append("output-close")

        def write_new(path, raw):
            state.order.append("write")
            state.writes.append((path, raw))

        context.native.poll, context.native.close = poll, close_native
        context.output = types.SimpleNamespace(close=Mock(side_effect=close_output))
        with patch.object(M, "shared_raw_ns", side_effect=clock), \
                patch.object(M.Path, "mkdir", autospec=True, side_effect=mkdir), \
                patch.object(M.subprocess, "Popen", side_effect=popen), \
                patch.object(M, "write_new", side_effect=write_new), patch.object(M, "_UNCLOSED_COMMANDS", []):
            yield state

    def test_01_actual_read_frame_positive_and_eof_boundaries(self):
        for serial in range(1, 9):
            value, raw, header = frame_bytes(serial)
            chunks = [header[:1], header[1:3], header[3:], raw[:1], raw[1:7], raw[7:]]
            with self.subTest(serial=serial), self._channel(chunks, idle_first=True) as state:
                trace = []
                self.assertEqual(M.read_frame(state.channel, serial, BINDING, trace, 40 * M.NS, pump=state.pump), value)
                self.assertEqual(state.requests, [4, 3, 1, len(raw), len(raw) - 1, len(raw) - 7])
                self.assertEqual(state.order, ["pump", "clock", "select"] +
                                 ["pump", "clock", "select", "recv"] * 6 + ["clock"])
                self.assertEqual(trace, [dict(serial=serial, direction=DIRECTIONS[serial - 1], kind=KINDS[serial - 1],
                                             sha256=hashlib.sha256(raw).hexdigest())])
        for serial in (1, 4, 8):
            for phase in ("HEADER", "BODY"):
                for progress in ("EMPTY", "PARTIAL"):
                    with self.subTest(serial=serial, phase=phase, progress=progress):
                        self._eof(serial, phase, progress)

        # The new catch encloses only the existing empty-part require, not the
        # preceding pump/select/recv/ancillary or subsequent frame validators.
        for endpoint in ("pump", "select", "recv"):
            error = M.ExperimentError("START", "STATUS_MISSING")
            options = {endpoint + "_error": error} if endpoint != "recv" else {}
            with self._channel([error] if endpoint == "recv" else [], **options) as state:
                trace = []
                with self.assertRaises(M.ExperimentError) as raised:
                    M.read_frame(state.channel, 1, BINDING, trace, 40 * M.NS, pump=state.pump)
                self.assertIs(raised.exception, error)
                self.assertIs(getattr(error, "protocol_eof", ABSENT), ABSENT)
                self.assertIsNone(M.public_protocol_eof(error))
                self.assertEqual(trace, [])
                self.assertEqual(state.position, 1 if endpoint == "recv" else 0)
        value, raw, _header = frame_bytes(1)
        wrong = M.encoded(dict(value, binding="b" * 64))
        for replies, expected in (
            ([(b"", [], 1, None)], ("START", "REFUSED")),
            ([(b"", [(-1, -1, b"synthetic")], 0, None)], ("START", "REFUSED")),
            ([PermissionError(errno.EACCES, CANARY)], ("START", "PERMISSION_DENIED")),
            ([struct.pack("!I", 0)], ("START", "BOUND")),
            ([struct.pack("!I", M.FRAME_BYTES + 1)], ("START", "BOUND")),
            ([struct.pack("!I", len(raw) + 1), raw + b" "], ("START", "REFUSED")),
            ([struct.pack("!I", len(wrong)), wrong], ("START", "IDENTITY_CHANGED")),
        ):
            with self._channel(replies) as state:
                trace = []
                with self.assertRaises(M.ExperimentError) as raised:
                    M.read_frame(state.channel, 1, BINDING, trace, 40 * M.NS, pump=state.pump)
                self.assertEqual((raised.exception.stage, raised.exception.reason), expected)
                self.assertIs(getattr(raised.exception, "protocol_eof", ABSENT), ABSENT)
                self.assertIsNone(M.public_protocol_eof(raised.exception))
                self.assertEqual((trace, state.position), ([], len(replies)))

    def test_02_actual_run_cases_annotates_before_abort_and_reraises(self):
        class StringSubclass(str):
            pass

        class MappingSubclass(dict):
            def get(self, *_args):
                raise AssertionError("UNTRUSTED_CURRENT_GET")

        missing = held_state("N1")
        del missing["case"]
        cases = [(held_state(case), case) for case in ("N1", "N2", "N3", "N4")]
        cases.extend((held_state(case), "UNKNOWN") for case in (None, True, 1, CANARY, StringSubclass("N1")))
        cases.extend(((None, "UNKNOWN"), (missing, "UNKNOWN"), (MappingSubclass(held_state("N2")), "UNKNOWN")))
        for current, case in cases:
            error = self._eof(4, "BODY", "PARTIAL")
            with self._foreground(error, current) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.run_cases(state.context)
                self.assertIs(raised.exception, error)
                self.assertEqual(error.protocol_eof_case, case)
                self.assertEqual(error.protocol_eof, (4, "BODY", "PARTIAL"))
                self.assertEqual(error.args, ("START/STATUS_MISSING/NONE",))
                # The third clock read is the original abort limit, before any
                # cleanup. It must already observe the held case annotation.
                self.assertEqual(state.clock_cases, [ABSENT, ABSENT, case])
                self.assertEqual(state.order, ["clock", "mkdir", "clock", "popen", "clock"] +
                                 ([] if current is None else ["native-poll"]) + ["native-close", "output-close", "write"])
                context = state.context
                self.assertEqual(context.abort_end, 121 * M.NS)
                self.assertFalse(context.finished or context.export_called)
                self.assertIsNone(context.result)
                self.assertEqual(context.case_results, [])
                self.assertEqual(len(state.writes), 1)
                path, raw = state.writes[0]
                self.assertEqual(path, EVIDENCE / "aborted-no-export.json")
                self.assertEqual(M.parsed(raw), dict(schema=1, scope=M.SCOPE, qualification="REFUSED", exportAllowed=False,
                    cleanupErrors=[], adminLifetimeUnknown=False, abortEndNs=121 * M.NS, registrationAttempts=[], signalReturns=[]))

        class ErrorSubclass(M.ExperimentError):
            pass

        errors = [M.ExperimentError("START", "STATUS_MISSING"), M.ExperimentError("START", "REFUSED"),
                  M.ExperimentError("CHILD_WAIT", "STATUS_MISSING"), ErrorSubclass("START", "STATUS_MISSING")]
        for error in errors[1:]:
            error.protocol_eof = (1, "HEADER", "EMPTY")
        for fields in (None, (), (1, "HEADER"), (1, "HEADER", "EMPTY", 0), [1, "HEADER", "EMPTY"]):
            error = M.ExperimentError("START", "STATUS_MISSING")
            error.protocol_eof = fields
            errors.append(error)
        for error in errors:
            with self._foreground(error, held_state("N3")) as state:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.run_cases(state.context)
                self.assertIs(raised.exception, error)
                self.assertIs(getattr(error, "protocol_eof_case", ABSENT), ABSENT)
                self.assertEqual(state.clock_cases, [ABSENT, ABSENT, ABSENT])
                self.assertEqual(state.context.abort_end, 121 * M.NS)
                self.assertEqual(len(state.writes), 1)

    def test_03_finite_formatter_and_actual_main_preserve_failure(self):
        class Hostile:
            def forbidden(self, *_args):
                raise AssertionError("UNTRUSTED_PROTOCOL_DIAGNOSTIC_OPERATION")
            __str__ = __repr__ = __bool__ = __len__ = __hash__ = __eq__ = __int__ = forbidden

        class StringSubclass(str):
            pass

        class IntegerSubclass(int):
            pass

        class TupleSubclass(tuple):
            pass

        class ErrorSubclass(M.ExperimentError):
            pass

        for case in ("N1", "N2", "N3", "N4"):
            for serial in range(1, 9):
                for phase in ("HEADER", "BODY"):
                    for progress in ("EMPTY", "PARTIAL"):
                        error = M.ExperimentError("START", "STATUS_MISSING")
                        error.protocol_eof, error.protocol_eof_case = (serial, phase, progress), case
                        self.assertEqual(M.public_protocol_eof(error), PREFIX + "|".join((case, "F" + str(serial), phase, progress)))
                        self.assertEqual(M.public_error(error), PRIMARY)
        invalid = (None, True, False, -1, 0, 9, 1.0, [], {}, b"HEADER", CANARY + "\n::error::" + CANARY, Hostile())
        valid = ("N1", 4, "BODY", "PARTIAL")
        subclasses = (StringSubclass("N1"), IntegerSubclass(4), StringSubclass("BODY"), StringSubclass("PARTIAL"))
        for index in range(4):
            for bad in (*invalid, subclasses[index]):
                fields = list(valid)
                fields[index] = bad
                error = M.ExperimentError("START", "STATUS_MISSING")
                error.protocol_eof_case, error.protocol_eof = fields[0], tuple(fields[1:])
                expected = ["N1", "F4", "BODY", "PARTIAL"]
                expected[index] = "UNKNOWN"
                public = M.public_protocol_eof(error)
                self.assertEqual(public, PREFIX + "|".join(expected))
                self.assertLessEqual(len(public), 96)
                self.assertNotIn(CANARY, public)
                self.assertNotIn("\n", public)
        for fields in (None, (), (1,), (1, "HEADER"), (1, "HEADER", "EMPTY", 0), [1, "HEADER", "EMPTY"],
                       TupleSubclass((1, "HEADER", "EMPTY")), Hostile()):
            error = M.ExperimentError("START", "STATUS_MISSING")
            error.protocol_eof = fields
            self.assertIsNone(M.public_protocol_eof(error))
        self.assertIsNone(M.public_protocol_eof(M.ExperimentError("START", "STATUS_MISSING")))
        for attribute in ("stage", "reason"):
            for bad in (*invalid, StringSubclass("START" if attribute == "stage" else "STATUS_MISSING")):
                error = M.ExperimentError("START", "STATUS_MISSING")
                error.protocol_eof = (1, "HEADER", "EMPTY")
                setattr(error, attribute, bad)
                self.assertIsNone(M.public_protocol_eof(error))
        for error in (M.ExperimentError("CHILD_WAIT", "STATUS_MISSING"), M.ExperimentError("START", "REFUSED"),
                      ErrorSubclass("START", "STATUS_MISSING"), RuntimeError(CANARY), SystemExit(CANARY), Hostile()):
            error.protocol_eof = (1, "HEADER", "EMPTY")
            self.assertIsNone(M.public_protocol_eof(error))

        annotated = self._eof(8, "BODY", "PARTIAL")
        plain = M.ExperimentError("START", "STATUS_MISSING")
        unrelated = M.ExperimentError("START", "REFUSED")
        unrelated.protocol_eof = (8, "BODY", "PARTIAL")
        for error, expected in (
            (annotated, PRIMARY + "\n" + PREFIX + "N3|F8|BODY|PARTIAL\n"),
            (plain, PRIMARY + "\n"),
            (unrelated, "P2PKIT_CONTEXT_FAILURE|START|REFUSED|NONE\n"),
        ):
            output = io.StringIO()
            with self._foreground(error, held_state("N3")) as state, \
                    patch.object(M, "prepare", return_value=state.context) as prepare, \
                    patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", "experiment"]), patch.object(M.os, "umask") as umask, \
                    contextlib.redirect_stdout(output):
                # Only preparation's acquisition boundary supplies held data;
                # actual main/experiment/run_cases/abort_suite all execute.
                self.assertEqual(M.main(), 2)
                prepare.assert_called_once_with()
                umask.assert_called_once_with(0o077)
                self.assertEqual(state.context.output.close.call_count, 2)  # Abort and original experiment finally.
                self.assertFalse(state.context.finished or state.context.export_called)
                self.assertIsNone(state.context.result)
                self.assertEqual([path.name for path, _raw in state.writes], ["aborted-no-export.json"])
            self.assertEqual(output.getvalue(), expected)
            self.assertNotIn(CANARY, output.getvalue())

    def test_04_exact_inverse_and_legacy_raw_hunk_containment(self):
        source = SOURCE.read_text(encoding="utf-8")
        hashes = (
            "e92c291407c4b1f6f000a675c07190b34c340cd6b17648e5d73fd8a610e9acac",
            "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf",
            "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b",
            "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d",
        )
        self.assertEqual(CLOCK.PROTOCOL_EOF_BASE_RUNTIME_SHA256, PREIMAGE)
        self.assertEqual((CLOCK.PROTOCOL_EOF_BASE_RUNTIME_SHA256, CLOCK.PLIST_NAME_BASE_RUNTIME_SHA256,
                          CLOCK.ADMIN_RETURN_BASE_RUNTIME_SHA256, CLOCK.BASE_RUNTIME_SHA256), hashes)
        self.assertEqual((CLOCK.BASE_WORKFLOW_SHA256, CLOCK.BASE_EXPERIMENT_TEST_SHA256), (
            "c88c6e69c00c0a150e0eacefbfb54e7611ec9511112dbd02c303f8ad19d7aa40",
            "484c4ebdd20bf5500ad9ba340f552cc15088e0c02e74759805cf693cfe290768",
        ))
        restores = (CLOCK.restore_protocol_eof_runtime, CLOCK.restore_plist_name_runtime,
                    CLOCK.restore_admin_return_runtime, CLOCK.restore_runtime)
        for restore, expected in zip(restores, hashes):
            self.assertEqual(hashlib.sha256(restore(source).encode("utf-8")).hexdigest(), expected)
        self.assertEqual((len(CLOCK.PROTOCOL_EOF_PATCH), len(CLOCK.PLIST_NAME_PATCH), len(CLOCK.ADMIN_RETURN_PATCH)), (7, 3, 8))
        # Legacy controls require these contiguous strings in CURRENT RAW source,
        # not only after reconstructing a preimage. No earlier suite is loaded.
        for before, after in (*CLOCK.PLIST_NAME_PATCH, *CLOCK.ADMIN_RETURN_PATCH):
            self.assertEqual(source.count(after), 1)
            for changed in (source.replace(after, before, 1), source + after):
                with self.assertRaises(AssertionError):
                    CLOCK.restore_runtime(changed)
        for before, after in CLOCK.PROTOCOL_EOF_PATCH:
            self.assertEqual(source.count(after), 1)
            for changed in (source.replace(after, before, 1), source + after,
                            source.replace(after, after + "# SYNTHETIC_MUTATION\n", 1)):
                self.assertNotEqual(changed, source)
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(changed)
        for bad in (None, b"", "", CLOCK.restore_protocol_eof_runtime(source), source + "\n# UNRELATED_MUTATION\n"):
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(bad)
        for patches in (CLOCK.PROTOCOL_EOF_PATCH[:-1], CLOCK.PROTOCOL_EOF_PATCH + CLOCK.PROTOCOL_EOF_PATCH[:1]):
            with patch.object(CLOCK, "PROTOCOL_EOF_PATCH", patches), self.assertRaises(AssertionError):
                CLOCK.restore_protocol_eof_runtime(source)
        for before, after in (
            ("type(error) is not ExperimentError", "not isinstance(error, ExperimentError)"),
            ('require(part, "START", "STATUS_MISSING")', 'require(True, "START", "STATUS_MISSING")'),
            ("len(data) == 0", "len(data) <= 1"),
            ('current.get("case")', '"N4"'),
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


if __name__ == "__main__":
    if tuple(unittest.defaultTestLoader.getTestCaseNames(ProtocolEOF)) != METHODS:
        raise SystemExit("FIXED_FOUR_PROTOCOL_EOF_METHODS_REQUIRED")
    suite = unittest.TestSuite(ProtocolEOF(name) for name in METHODS)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
