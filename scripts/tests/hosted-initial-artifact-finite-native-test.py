#!/usr/bin/env python3
"""NEW finite clock/pipe/caller models only; no real native/hosted resources.

Actual finite entry/control code runs over explicit closed unit-model seams.
AST assertions are source-order evidence only. Neither is native qualification.
No old reader fixture or previously accepted suite is imported or executed.
"""
from __future__ import annotations

import _strptime
import ast
import base64
from contextlib import contextmanager, ExitStack
import ctypes
import errno
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("FINITE_NATIVE_MODEL_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(SCRIPTS), str(SCRIPTS / "tests")]
SOURCE_PATH = SCRIPTS / "run-hosted-initial-recipient-upload.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
if len(SOURCE.encode("utf-8")) > 128 * 1024:
    raise AssertionError("FINITE_SOURCE_BOUND")
TREE = ast.parse(SOURCE, filename=str(SOURCE_PATH))
SPEC = importlib.util.spec_from_file_location("_new_finite_native_controls", SOURCE_PATH)
U = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = U
SPEC.loader.exec_module(U)
import hosted_initial_artifact_finite_fixtures as F

D, NS, NOW = U.D, F.NS, F.NOW


@contextmanager
def clock_model(mode="finish", *, first=None, cancel=lambda: None):
    global GUARDED
    first = (405 if mode == "after" else 345 if mode == "finish" else 340) * NS if first is None else first
    with ExitStack() as stack:
        attempts, environment = {}, {"MODEL_ONLY": "NOT_HOSTED_AUTHORITY"}
        latch = U.K.B.EntryLatch(attempts)
        for name, value in (("_ATTEMPTS", attempts), ("_ENTRY", latch), ("_CLOCKS", {})):
            stack.enter_context(patch.object(U, name, value))
        stack.enter_context(patch.object(U.os, "environ", environment))
        local = stack.enter_context(patch.object(U.time, "monotonic", return_value=100.1))
        utc = stack.enter_context(patch.object(U.time, "time", return_value=float(NOW)))
        raw = stack.enter_context(patch.object(U.O.clocks, "checked_now", return_value=first + NS // 10))
        stack.enter_context(patch.object(U.K.continuity, "boot_digest", return_value="a" * 64))
        entry = latch.begin(attempts)
        identity = U.O.clocks.ClockIdentity("linux-x64", F.seed()["initialSealClockDomain"], NS)
        reading = U.O.clocks.Reading(identity, first)
        previous, GUARDED = GUARDED, True
        try:
            clock = U._Clock(reading, 100.0, "a" * 64, cancel, dict(environment), F.seed(), entry,
                first_graph=U.N._history_graph(reading), latch=latch, attempts=attempts, mode=mode)
            yield SimpleNamespace(clock=clock, latch=latch, attempts=attempts, entry=entry,
                environment=environment, local=local, raw=raw, utc=utc, reading=reading)
        finally:
            GUARDED = previous


class Part:
    def __init__(self):
        self.closed = False


class Pipe(Part):
    def __init__(self, number):
        super().__init__()
        self.number, self.buffer, self.raw = number, Part(), Part()
        self.close_calls, self.close_error = 0, None

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        self.closed = self.buffer.closed = self.raw.closed = True


class PipeOps:
    def __init__(self):
        self.originals = tuple(Pipe(number) for number in range(3))
        self.blocking, self.input, self.read_calls, self.writes, self.write_results = {0: True, 1: True}, [], [], [], []
        self.pin_error = self.false_close = None

    def identity(self, stream, number):
        if number == self.pin_error:
            raise ValueError("MODEL_PIN_FAILURE")
        if stream is not self.originals[number] or stream.closed:
            raise ValueError("MODEL_ORIGINAL_PIPE_CHANGED")
        return stream, stream.buffer, stream.raw, number, (1, number + 1, 123), None

    def read(self, number, count):
        if number != 0 or not self.input:
            raise AssertionError("UNEXPECTED_MODEL_READ")
        self.read_calls.append(count)
        raw = self.input.pop(0)
        if isinstance(raw, BaseException):
            raise raw
        if len(raw) > count:
            self.input.insert(0, raw[count:])
            raw = raw[:count]
        return raw

    def write(self, number, raw):
        if number != 1:
            raise AssertionError("UNEXPECTED_MODEL_WRITE")
        result = self.write_results.pop(0) if self.write_results else len(raw)
        if isinstance(result, BaseException):
            raise result
        if type(result) is int and 0 < result <= len(raw):
            self.writes.append(bytes(raw[:result]))
        return result

    def fstat(self, number):
        if self.originals[number].closed and number != self.false_close:
            raise OSError(errno.EBADF, "MODEL_ORIGINAL_CLOSED")
        return object()


@contextmanager
def pipe_model(mode="finish"):
    with clock_model(mode) as clock, ExitStack() as stack:
        ops = PipeOps()
        for name, value in (("_PIPES", {}), ("_QUARANTINE", [])):
            stack.enter_context(patch.object(U, name, value))
        for name, original in zip(("stdin", "stdout", "stderr"), ops.originals):
            stack.enter_context(patch.object(U.sys, name, original))
        stack.enter_context(patch.object(U, "_pipe_identity", side_effect=ops.identity))
        stack.enter_context(patch.object(U.os, "set_blocking", side_effect=lambda number, value: ops.blocking.update({number: value})))
        stack.enter_context(patch.object(U.os, "get_blocking", side_effect=ops.blocking.__getitem__))
        stack.enter_context(patch.object(U.os, "read", side_effect=ops.read))
        stack.enter_context(patch.object(U.os, "write", side_effect=ops.write))
        stack.enter_context(patch.object(U.os, "fstat", side_effect=ops.fstat))
        stack.enter_context(patch.object(U.time, "sleep", return_value=None))
        pipes = U._Pipes(clock.clock, mode=mode)
        yield pipes, ops, clock


def frame(kind, raw):
    return kind + len(raw).to_bytes(4, "big") + raw


class FiniteClockControls(unittest.TestCase):
    def sticky(self, model, operation):
        with self.assertRaises(ValueError) as failure:
            operation()
        with self.assertRaises(ValueError) as repeated:
            model.latch.check(model.attempts, model.entry)
        self.assertIs(failure.exception, repeated.exception)
        return failure.exception

    def test_finish_has_only_original_upload_end_then_tightens_before_files(self):
        f = F.fixture(D)
        with clock_model() as m:
            self.assertEqual((m.clock.work, m.clock.final), (406 * NS, 406 * NS))
            self.assertGreater(m.clock.final, m.clock.first + 60 * NS)  # Not a manufactured new60s.
            m.clock.tighten_finish(f["ready_raw"], f["final_raw"])
            self.assertEqual((m.clock.work, m.clock.final), (395 * NS, 400 * NS))
            self.assertLessEqual(m.clock.local_end, 155.0)

    def test_finish_refuses_file_owner_attachment_before_original_cap_binding(self):
        with clock_model() as m:
            owner = object.__new__(U.C._PrimaryOwner)  # No owner acquired; first precondition must refuse.
            self.sticky(m, lambda: m.clock.attach(owner))

    def test_finish_never_accepts_first_before_original_stream_close_or_after_work(self):
        f = F.fixture(D)
        for first in (343 * NS, 395 * NS):
            with clock_model(first=first) as m:
                self.sticky(m, lambda: m.clock.tighten_finish(f["ready_raw"], f["final_raw"]))

    def test_finish_tightening_is_once_and_cannot_be_reset(self):
        f = F.fixture(D)
        with clock_model() as m:
            m.clock.tighten_finish(f["ready_raw"], f["final_raw"])
            self.sticky(m, lambda: m.clock.tighten_finish(f["ready_raw"], f["final_raw"]))

    def test_finish_original_ready_graph_is_pinned_not_reparsed_after_mutation(self):
        f = F.fixture(D)
        with clock_model() as m:
            returned, original_ready = [], D.stream_ready
            def capture(raw):
                value = original_ready(raw)
                returned.append(value)
                return value
            with patch.object(D, "stream_ready", side_effect=capture):
                m.clock.tighten_finish(f["ready_raw"], f["final_raw"])
            self.assertGreaterEqual(len(returned), 1)
            original = returned[0]
            self.assertTrue(any(row[0] is original for row in m.clock._anchor().tightening[3]))
            observed = original["observedAt"]
            original["observedAt"] = observed + 1
            failure = self.sticky(m, m.clock.current)
            original["observedAt"] = observed
            with self.assertRaises(ValueError) as again:
                m.clock.current()
            self.assertIs(again.exception, failure)

    def test_after_has_one_original_fifteen_second_cap_through_direct_return(self):
        with clock_model("after") as m:
            self.assertEqual((m.clock.work, m.clock.final), (420 * NS, 420 * NS))
            self.assertLessEqual(m.clock.local_end, 115.0)
            m.local.return_value = 115.0
            self.sticky(m, m.clock.now)

    def test_after_first_at_original_upload_end_is_refused(self):
        with self.assertRaises(ValueError):
            with clock_model("after", first=406 * NS):
                self.fail("AFTER_FIRST_EQUALS_UPLOAD_END")

    def test_each_finite_mode_latches_original_raw_expiry_and_backwards_local_time(self):
        for mode in ("finish", "after"):
            with clock_model(mode) as m:
                m.raw.return_value = m.clock.work
                self.sticky(m, m.clock.now)
            with clock_model(mode) as m:
                m.local.return_value = 99.0
                self.sticky(m, m.clock.now)


class FinitePipeControls(unittest.TestCase):
    def prepare(self, pipes, ops, mode="finish", raw=b'{"model":"I"}\n'):
        pipes.configure()
        if mode == "after":
            pipes.frame(b"R", b'{"model":"R"}\n')
        ops.input = [frame(b"I", raw), b""]
        self.assertEqual(pipes.control(), raw)

    def test_both_finite_modes_require_i_eof_f_and_all_original_closes(self):
        for mode in ("finish", "after"):
            with pipe_model(mode) as (pipes, ops, _clock):
                self.prepare(pipes, ops, mode)
                self.assertTrue(pipes.state()["input_done"])
                pipes.frame(b"F", b'{"model":"F"}\n')
                pipes.close()
                self.assertEqual(pipes.state()["closed"], frozenset((0, 1, 2)))
                self.assertEqual([value.close_calls for value in ops.originals], [1, 1, 1])

    def test_declared_input_overflow_refuses_before_any_payload_read(self):
        with pipe_model() as (pipes, ops, clock):
            pipes.configure()
            ops.input = [b"I" + (D.INPUT_BYTES + 1).to_bytes(4, "big"), b"NOT_READ"]
            with self.assertRaises(ValueError):
                pipes.control()
            self.assertEqual(ops.read_calls, [5])
            self.assertEqual(ops.input, [b"NOT_READ"])
            with self.assertRaises(ValueError):
                clock.clock.now()

    def test_exact_complete_two_mib_frame_is_not_truncated(self):
        with pipe_model() as (pipes, ops, _clock):
            raw = b" " * D.INPUT_BYTES
            self.prepare(pipes, ops, raw=raw)
            self.assertLessEqual(max(ops.read_calls), 65536)
            self.assertEqual(sum(ops.read_calls[:-1]), D.INPUT_BYTES + 5)

    def test_fragmented_input_eagain_and_f_output_backpressure_preserve_original_frames(self):
        with pipe_model() as (pipes, ops, _clock):
            pipes.configure()
            raw = b'{"model":"fragmented"}\n'
            packet = frame(b"I", raw)
            ops.input = [packet[:2], BlockingIOError(), packet[2:5], packet[5:9], packet[9:], b""]
            self.assertEqual(pipes.control(), raw)
            ops.write_results = [BlockingIOError(), 1, 3]
            pipes.frame(b"F", raw)
            self.assertEqual(b"".join(ops.writes), frame(b"F", raw))

    def test_missing_input_eof_trailing_byte_and_wrong_tag_are_sticky_failures(self):
        for incoming in ([b""], [frame(b"I", b"{}\n"), b"N"], [b"D\0\0\0\1", b"x"]):
            with pipe_model() as (pipes, ops, clock):
                pipes.configure()
                ops.input = incoming
                with self.assertRaises(ValueError):
                    pipes.control()
                with self.assertRaises(ValueError):
                    clock.clock.current()

    def test_after_ready_must_precede_input_and_finish_cannot_emit_ready(self):
        with pipe_model("after") as (pipes, ops, _clock):
            pipes.configure()
            with self.assertRaises(ValueError):
                pipes.control()
            self.assertEqual(ops.read_calls, [])
        with pipe_model() as (pipes, _ops, _clock):
            pipes.configure()
            with self.assertRaises(ValueError):
                pipes.frame(b"R", b"{}\n")

    def test_repeated_input_or_final_cannot_become_a_second_successful_return(self):
        for repeated in ("input", "final"):
            with pipe_model() as (pipes, ops, _clock):
                self.prepare(pipes, ops)
                if repeated == "final":
                    pipes.frame(b"F", b"{}\n")
                with self.assertRaises(ValueError):
                    pipes.control() if repeated == "input" else pipes.frame(b"F", b"{}\n")

    def test_finite_close_without_final_or_unknown_descriptor_close_never_succeeds(self):
        with pipe_model() as (pipes, ops, _clock):
            self.prepare(pipes, ops)
            with self.assertRaises(ValueError):
                pipes.close()
        with pipe_model() as (pipes, ops, _clock):
            self.prepare(pipes, ops)
            pipes.frame(b"F", b"{}\n")
            ops.false_close = 1
            with self.assertRaises(ValueError):
                pipes.close()
            self.assertIn(1, pipes.state()["unknown"])
            with self.assertRaises(ValueError):
                pipes.close()
            self.assertEqual(ops.originals[1].close_calls, 1)

    def test_partial_finite_configuration_retains_originals_for_cleanup_not_reopen(self):
        with pipe_model("after") as (pipes, ops, _clock):
            ops.pin_error = 1
            with self.assertRaises(ValueError) as failure:
                pipes.configure()
            with self.assertRaises(ValueError):
                pipes.close(failure.exception)
            self.assertEqual([pipe.close_calls for pipe in ops.originals], [1, 0, 0])
            self.assertEqual(pipes.state()["unknown"], frozenset((1, 2)))

    def test_default_stream_does_not_inherit_finite_f_after_eof_or_control_input(self):
        with pipe_model("stream") as (pipes, ops, _clock):
            pipes.configure()
            ops.input = [b""]
            pipes.demand(eof=True)
            with self.assertRaises(ValueError):
                pipes.frame(b"F", b"{}\n")
        with pipe_model("stream") as (pipes, _ops, _clock):
            pipes.configure()
            with self.assertRaises(ValueError):
                pipes.control()


@contextmanager
def caller_model(mode="finish"):
    """Real finite/clock/pipe/DATA over explicit fake native files and K inputs.

    This executes the new caller, not the old native reader or a file backend.
    No fake record here is used as hosted evidence or passed to a real owner.
    """
    global GUARDED
    with ExitStack() as stack:
        f = F.fixture(D)
        a = F.after(D, f) if mode == "after" else None
        events, attempts, owners = [], {}, []
        latch, ops = U.K.B.EntryLatch(attempts), PipeOps()
        first = U.O.clocks.Reading(U.O.clocks.ClockIdentity("linux-x64",
            F.seed()["initialSealClockDomain"], NS), (405 if a else 345) * NS)
        environment = {U.H.HASH_ENV: f["ready"]["beforeSha256"], U.H.OUTCOME_ENV: "success",
            U.K.B.SEAL_OUTCOME_ENV: "success", **{name: F.seed()[field] for field, name, _flag in U.K.B.SEED_FIELDS}}
        data, metadata = {}, {}
        faults = {"reread": False, "finish": False}
        close_raw = b'{"model":"FINITE_ORIGINAL_OWNER_CLOSE_NOT_AUTHORITY"}\n'

        class Directory:
            def __init__(self, path, identity, names=()):
                self.path, self.identity, self.names = Path(path), identity, list(names)

            def verify(self):
                events.append("directory-verify")

            def create_directory(self, name, *, deadline):
                if name != "upload-returned" or name in self.names or deadline <= 100.1:
                    raise AssertionError("MODEL_DIRECTORY_CREATE")
                self.names.append(name)
                events.append("directory-create")
                return directory

        root = Directory("/model/custody", (1, 1), U.K._custody_names(tail_output=True, upload=True))
        directory = Directory(root.path / "upload-returned", (1, 2))
        private, output = object(), object()

        def metadata_for(name, raw):
            return {"device": 1, "inode": 8 if name == D.UPLOAD_FILE else 9,
                "size": len(raw), "mtime_ns": 1, "ctime_ns": 1}

        if a:
            root.names.append("upload-returned")
            directory.names.append(D.UPLOAD_FILE)
            data[D.UPLOAD_FILE] = a["upload_raw"]
            metadata[D.UPLOAD_FILE] = metadata_for(D.UPLOAD_FILE, a["upload_raw"])
            environment.update({D.UPLOAD_OUTCOME_ENV: "success", D.UPLOAD_HASH_ENV: D.sha(a["upload_raw"]),
                D.UPLOAD_DIRECTORY_ENV: D.sha(F.wire([1, 2])),
                D.UPLOAD_METADATA_ENV: D.sha(F.wire(metadata[D.UPLOAD_FILE])), D.UPLOAD_CLOSE_ENV: "3" * 64})
        control_raw = F.wire(a["control"] if a else f["control"])
        ops.input = [frame(b"I", control_raw), b""]

        class Owner:
            def __init__(self, original):
                self.owner, self.failure, self.finished, self.rows = original, None, False, []
                self.anchor, self.finish_calls = object(), 0
                owners.append(self)
                events.append("owner-created")

            def _anchor(self):
                return self.anchor

            def structural(self):
                return None

            def guard(self):
                if self.finished:
                    raise AssertionError("MODEL_OWNER_ALREADY_CLOSED")
                return self.owner.fence.deadline(900)

            def acquire(self, kind, operation):
                if kind != "directory":
                    raise AssertionError("MODEL_UNPLANNED_ACQUIRE")
                return operation()

            def remember(self, error):
                if self.failure is None:
                    self.failure = error
                return self.failure

            def finish(self):
                self.finish_calls += 1
                if self.finished:
                    raise AssertionError("MODEL_OWNER_CLOSE_RETRY")
                self.finished = True
                events.append("owner-close")
                if faults["finish"]:
                    raise self.remember(ValueError("MODEL_OWNER_CLOSE_UNKNOWN"))
                return close_raw

        def inputs(owner, clock, kind):
            if kind != "worker":
                raise AssertionError("MODEL_FIXED_KIND")
            events.append("K-inputs")
            raws = {U.H.PRIVATE_CARRIER_CLOSE: F.CARRIER_CLOSE}
            parsed = (f["pending"], {}, f["context"], {}, f["policy"], f["match"])
            clock.bind_content(raws, parsed, ())
            return root, private, output, raws, (), parsed

        def write(_owner, target, name, raw):
            if target is not directory or name in data or name not in (D.UPLOAD_FILE, D.AFTER_FILE):
                raise AssertionError("MODEL_EXCLUSIVE_FIXED_WRITE")
            events.append("pending-write-readback")
            data[name], metadata[name] = raw, metadata_for(name, raw)
            directory.names.append(name)
            return {"postCloseReadback": F.copy(metadata[name])}

        def open_file(_owner, target, name, maximum):
            if target is not directory or name not in data or len(data[name]) > maximum:
                raise AssertionError("MODEL_FIXED_PENDING_READ")
            events.append("pending-read-" + name)
            raw = F.wire(metadata[name])
            if faults["reread"] and name == (D.AFTER_FILE if a else D.UPLOAD_FILE):
                raw = F.wire({**metadata[name], "inode": 99})
            return SimpleNamespace(name=name, raw=raw, closed=False)

        def read(file, checksum, *, retain, close):
            if not retain or not close or D.sha(data[file.name]) != checksum:
                raise AssertionError("MODEL_PENDING_HASH_EOF_CLOSE")
            file.closed = True
            return data[file.name]

        def file_current(file, *, closed):
            if not closed or not file.closed:
                raise AssertionError("MODEL_PENDING_NOT_CLOSED")

        def names(_owner, target, expected):
            if target not in (root, directory) or sorted(target.names) != sorted(expected):
                raise AssertionError("MODEL_FIXED_DIRECTORY_ROSTER")

        def pipe_write(number, raw):
            events.append("frame-" + bytes(raw[:1]).decode("ascii"))
            return ops.write(number, raw)

        def original_close(_owner):
            if not owners[0].finished or owners[0].failure is not None:
                raise AssertionError("MODEL_OWNER_NOT_KNOWN_CLOSED")
            events.append("known-file-closes")

        for name, value in (("_ATTEMPTS", attempts), ("_ENTRY", latch), ("_CLOCKS", {}), ("_PIPES", {}), ("_QUARANTINE", [])):
            stack.enter_context(patch.object(U, name, value))
        stack.enter_context(patch.object(U.os, "environ", environment))
        stack.enter_context(patch.object(U.time, "monotonic", return_value=100.1))
        stack.enter_context(patch.object(U.time, "time", return_value=float(NOW)))
        stack.enter_context(patch.object(U.O.clocks, "observe", return_value=first))
        stack.enter_context(patch.object(U.O.clocks, "checked_now", return_value=first.nanoseconds + NS // 10))
        stack.enter_context(patch.object(U.K.continuity, "boot_digest", return_value="a" * 64))
        stack.enter_context(patch.object(U.native, "Owner", side_effect=lambda end, clock, **kwargs:
            SimpleNamespace(fence=clock, first=kwargs["first"], unknown=False)))
        stack.enter_context(patch.object(U.C, "_PrimaryOwner", Owner))
        stack.enter_context(patch.object(U.Q, "_PosixDirectory", Directory))
        stack.enter_context(patch.object(U.C, "_private", side_effect=lambda _owner, path:
            directory if path == directory.path else (_ for _ in ()).throw(AssertionError("MODEL_PRIVATE_PATH"))))
        stack.enter_context(patch.object(U, "_inputs", side_effect=inputs))
        stack.enter_context(patch.object(U, "_final_inputs", side_effect=lambda *_args: events.append("K-final-rereads-model")))
        for name, operation in (("_write_bytes", write), ("_open_file", open_file), ("_stream", read),
                ("_file_current", file_current), ("_names", names), ("_closed_files", original_close)):
            stack.enter_context(patch.object(U.K, name, side_effect=operation))
        for name, original in zip(("stdin", "stdout", "stderr"), ops.originals):
            stack.enter_context(patch.object(U.sys, name, original))
        stack.enter_context(patch.object(U, "_pipe_identity", side_effect=ops.identity))
        stack.enter_context(patch.object(U.os, "set_blocking", side_effect=lambda number, value: ops.blocking.update({number: value})))
        stack.enter_context(patch.object(U.os, "get_blocking", side_effect=ops.blocking.__getitem__))
        stack.enter_context(patch.object(U.os, "read", side_effect=ops.read))
        stack.enter_context(patch.object(U.os, "write", side_effect=pipe_write))
        stack.enter_context(patch.object(U.os, "fstat", side_effect=ops.fstat))
        previous, GUARDED = GUARDED, True
        try:
            yield SimpleNamespace(events=events, attempts=attempts, latch=latch, ops=ops, environment=environment,
                owners=owners, faults=faults, data=data, metadata=metadata, close_raw=close_raw,
                control_raw=control_raw, mode=mode, run=lambda: U.finite("worker", lambda: None, mode))
        finally:
            GUARDED = previous


class FiniteCallerControls(unittest.TestCase):
    def failure(self, model):
        with self.assertRaises(ValueError) as caught:
            model.run()
        with self.assertRaises(ValueError) as retained:
            model.latch.check(model.attempts, model.attempts["entry"])
        self.assertIs(caught.exception, retained.exception)
        return caught.exception

    def test_finish_real_caller_binds_writes_rereads_closes_then_returns_f(self):
        with caller_model() as m:
            clock = m.run()
            self.assertEqual((clock.work, clock.final), (395 * NS, 400 * NS))
            packet = b"".join(m.ops.writes)
            self.assertEqual(packet[:1], b"F")
            value = D.canonical(packet[5:])
            self.assertEqual(int.from_bytes(packet[1:5], "big"), len(packet) - 5)
            self.assertEqual(value["pendingSha256"], D.sha(m.data[D.UPLOAD_FILE]))
            self.assertEqual(value["fileMetadataSha256"], D.sha(F.wire(m.metadata[D.UPLOAD_FILE])))
            self.assertEqual(value["fileOwnerCloseSha256"], D.sha(m.close_raw))
            self.assertEqual(value["inputSha256"], D.sha(m.control_raw))
            ordered = ("owner-created", "K-inputs", "directory-create", "pending-write-readback",
                "K-final-rereads-model", "pending-read-" + D.UPLOAD_FILE, "owner-close", "known-file-closes", "frame-F")
            positions = [m.events.index(name) for name in ordered]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(m.attempts["entry"]["state"], "RETURNED")
            self.assertEqual([pipe.close_calls for pipe in m.ops.originals], [1, 1, 1])
            self.assertEqual(m.owners[0].finish_calls, 1)

    def test_after_real_caller_binds_old_u_carrier_then_emits_r_and_writes_a(self):
        with caller_model("after") as m:
            clock = m.run()
            packet, frames = b"".join(m.ops.writes), []
            while packet:
                size = int.from_bytes(packet[1:5], "big")
                self.assertGreater(size, 0)
                self.assertGreaterEqual(len(packet), 5 + size)
                frames.append((packet[:1], D.canonical(packet[5:5 + size])))
                packet = packet[5 + size:]
            self.assertEqual([tag for tag, _ in frames], [b"R", b"F"])
            self.assertEqual(clock.final, 420 * NS)
            pending = frames[1][1]["pending"]
            self.assertEqual(pending["uploadSha256"], D.sha(m.data[D.UPLOAD_FILE]))
            self.assertEqual(pending["uploadCarrier"]["fileOwnerCloseSha256"], m.environment[D.UPLOAD_CLOSE_ENV])
            self.assertEqual(pending["artifact"]["expiresAt"], "2026-10-09T00:00:30Z")
            self.assertEqual(m.events.count("pending-read-" + D.UPLOAD_FILE), 2)
            self.assertNotIn("directory-create", m.events)
            self.assertLess(m.events.index("frame-R"), m.events.index("pending-write-readback"))
            self.assertLess(m.events.index("known-file-closes"), m.events.index("frame-F"))
            self.assertEqual(m.attempts["entry"]["state"], "RETURNED")
            self.assertEqual([pipe.close_calls for pipe in m.ops.originals], [1, 1, 1])

    def test_finish_actual_k_hash_mismatch_refuses_before_directory_or_writer(self):
        with caller_model() as m:
            m.environment[U.H.HASH_ENV] = "0" * 64
            self.assertIn("FINISH_ACTUAL_K_HASHES", str(self.failure(m)))
            self.assertNotIn("directory-create", m.events)
            self.assertNotIn("pending-write-readback", m.events)
            self.assertNotIn("frame-F", m.events)
            self.assertEqual(m.owners[0].finish_calls, 1)

    def test_after_old_u_directory_and_file_outputs_are_checked_before_observer_or_write(self):
        for name in (D.UPLOAD_DIRECTORY_ENV, D.UPLOAD_METADATA_ENV):
            with caller_model("after") as m:
                m.environment[name] = "0" * 64
                self.failure(m)
                self.assertNotIn("frame-R", m.events)
                self.assertNotIn("pending-write-readback", m.events)
                self.assertNotIn("frame-F", m.events)

    def test_pending_metadata_change_after_write_cannot_become_f_or_success(self):
        for mode in ("finish", "after"):
            with caller_model(mode) as m:
                m.faults["reread"] = True
                self.assertIn("PENDING_ORIGINAL_READBACK", str(self.failure(m)))
                self.assertIn("pending-write-readback", m.events)
                self.assertNotIn("frame-F", m.events)
                self.assertEqual(m.owners[0].finish_calls, 1)

    def test_unknown_owner_close_does_not_emit_f_or_retry_close(self):
        with caller_model() as m:
            m.faults["finish"] = True
            self.assertEqual(str(self.failure(m)), "MODEL_OWNER_CLOSE_UNKNOWN")
            self.assertNotIn("frame-F", m.events)
            self.assertEqual(m.owners[0].finish_calls, 1)

    def test_f_written_before_unknown_pipe_close_is_not_a_successful_caller_return(self):
        with caller_model() as m:
            m.ops.false_close = 1
            self.failure(m)
            self.assertIn("frame-F", m.events)
            self.assertEqual(m.attempts["entry"]["state"], "FAILED")
            self.assertEqual([pipe.close_calls for pipe in m.ops.originals], [1, 1, 1])


def source(name):
    node = next(value for value in TREE.body if isinstance(value, (ast.FunctionDef, ast.ClassDef)) and value.name == name)
    return ast.get_source_segment(SOURCE, node)


class FiniteCallerSourceControls(unittest.TestCase):
    def test_first_graph_and_original_latch_precede_environment_or_path_callbacks(self):
        text = source("finite")
        self.assertLess(text.index("latch, attempts = _ENTRY, _ATTEMPTS"), text.index("latch.begin"))
        self.assertLess(text.index("local = C.local_value"), text.index("first = O.clocks.observe()"))
        self.assertLess(text.index("first_graph = N._history_graph(first)"), text.index("boot = K.continuity.boot_digest"))
        self.assertLess(text.index("N._check_history(first_graph)"), text.index("environment, seed = _environment()"))

    def test_finish_tightens_actual_r_f_before_any_file_owner(self):
        text = source("finite")
        self.assertLess(text.index("clock.tighten_finish(ready_raw, control[3])"), text.index("owner = C._PrimaryOwner"))
        self.assertLess(text.index("clock.retain(control)"), text.index("clock.tighten_finish"))
        self.assertLess(text.index('"FINISH_ACTUAL_K_HASHES"'), text.index("directory, directory_raw = _returned_directory"))
        self.assertIn('observed[0]["beforeSha256"] == environment[H.HASH_ENV]', text)
        self.assertIn('observed[0]["carrierCloseSha256"] == D.sha(raws[H.PRIVATE_CARRIER_CLOSE])', text)

    def test_after_checks_original_u_directory_file_bytes_and_outcome_before_writer(self):
        text = source("finite")
        for operation in ("upload_carrier = _upload_carrier(environment)", '"UPLOAD_DIRECTORY_OUTPUT"',
                '"UPLOAD_ORIGINAL_METADATA_OR_CARRIER"', "input_raw = pipes.control()"):
            self.assertLess(text.index(operation), text.index("written = K._write_bytes"))
        self.assertIn('environment.get(D.UPLOAD_OUTCOME_ENV) == "success"', source("_upload_carrier"))
        self.assertIn('D.digest(environment.get(D.UPLOAD_CLOSE_ENV))', source("_upload_carrier"))

    def test_pending_write_and_independent_readback_precede_actual_owner_close_and_f(self):
        text = source("finite")
        ordered = ("written = K._write_bytes", "clock.retain(written)", "_final_inputs(owner", "actual, metadata = _read_pending",
            "close_raw = owner.finish()", "clock.retain(close_raw)", "K._closed_files(owner)", "final_raw = D.finite_result",
            'pipes.frame(b"F", final_raw)', "pipes.close()", "latch.complete", "latch.returned", "return clock")
        positions = [text.index(part) for part in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn('file_raw = O.encoded(written["postCloseReadback"])', text)

    def test_only_two_fixed_pending_children_and_actual_directory_identity_preimage(self):
        text = source("_returned_directory")
        self.assertIn('root.create_directory("upload-returned", deadline=end)', text)
        self.assertIn("identity_raw = O.encoded(identity)", text)
        self.assertIn("native.directory_identity(list(directory.identity), clock.clock.role)", text)
        self.assertIn("() if create else (D.UPLOAD_FILE,)", text)
        self.assertIn("(D.UPLOAD_FILE, D.AFTER_FILE)", source("finite"))

    def test_final_rereads_are_small_k_originals_and_two_manifests_not_ciphertexts(self):
        text = source("_final_inputs")
        self.assertIn("for name, metadata, expected in observations:", text)
        self.assertIn("for index in (1, 3):", text)
        self.assertIn("file.raw == O.encoded(carrier", text)
        self.assertNotIn("_member(", text)
        self.assertNotIn("stored_zip(", text)
        self.assertNotIn("unlink(", source("finite"))


if __name__ == "__main__":
    unittest.main(failfast=True)
