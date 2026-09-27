#!/usr/bin/env python3
"""Fixed initial-custody stream and finite upload/AFTER pending-file owners.

This source remains dormant until its connected caller and genuine native/
hosted qualification exist. No key, token, network operation or restored B/K
capability is permitted. A pending record cannot attest its enclosing Step.
All stdout bytes belong to the original private Node pipe, never Actions logs.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import errno
import hashlib
import io
import math
import os
from pathlib import Path
import signal
import stat
import sys
import time
from types import MappingProxyType

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import hosted_initial_recipient_productive_tail as K
import hosted_initial_artifact_productive_delivery as D

C, N, native, O, Q, TD, Z = K.C, K.N, K.native, K.O, K.Q, K.TD, D.Z
NS = O.NS
_ATTEMPTS, _CLOCKS, _PIPES = {}, {}, {}
_ENTRY = C.B.EntryLatch(_ATTEMPTS)
_QUARANTINE = []
_INPUT_NAMES = (TD.HASH_ENV, TD.OUTCOME_ENV, TD.SEAL_OUTCOME_ENV, TD.DEADLINE_HASH_ENV, TD.DEADLINE_BASE64_ENV)


def require(value, code):
    D.require(value, "NATIVE_" + code)


def _environment():
    O.public_provider.credential_free()
    require(not any(name in os.environ for name in K.CREDENTIAL_NAMES), "CREDENTIAL_BOUNDARY")
    actual = dict(os.environ)
    return actual, TD.deadline_environment(actual)


@dataclass(eq=False, repr=False)
class _ClockAnchor:
    clock: object
    binding: tuple
    graph: object
    latch: object
    attempts: object
    entry: object
    last: int
    local_last: float
    failure: object = None
    busy: bool = False
    owner: object = None
    content: object = None
    returns: tuple = ()
    tightening: object = None


class _Clock:
    """File-only clock; finite modes cannot restart the original allowance."""
    __slots__ = ("_binding",)

    def __init__(self, first, local, boot, cancelled, environment, seed, entry,
            *, first_graph, latch, attempts, mode="stream"):
        require(type(self) is _Clock and id(self) not in _CLOCKS and callable(cancelled), "CLOCK_ONCE")
        N._check_history(first_graph)
        O.clocks.validate_reading(first)
        C.local_value(local)
        deadline = K.RD.deadline(TD.encoded(seed, K.CD.PUBLIC_LIMIT))
        seal, expected, original_boot = deadline["uploadStartByNs"], O.wire.clock_identity(deadline["clock"]), deadline["originalBootDigest"]
        require(first.clock == expected and boot == original_boot, "CLOCK_BOOT_OR_DOMAIN")
        require(type(mode) is str and mode in ("stream", "finish", "after"), "CLOCK_FIXED_MODE")
        if mode == "stream":
            start, work, close = D.upload_caps(seed, first.nanoseconds)
            require(start == seal, "CLOCK_ORIGINAL_START")
            maximum = 60
        elif mode == "finish":
            # Only the inherited absolute uploadEnd is available before I.
            # There is deliberately NO finish-FIRST+60 allowance. Before any
            # file owner, tighten_finish binds the actual stream R/F caps.
            start, work, close = seal, deadline["uploadEndNs"], deadline["uploadEndNs"]
            require(first.nanoseconds < close, "FINISH_ORIGINAL_UPLOAD_END")
            maximum = 900  # Existing native ceiling, clipped by original end.
        else:
            start, close = D.after_caps(seed, first.nanoseconds)
            work, maximum = close, 15
        local_work = O.wire._directed_deadline(local, maximum, work, first.nanoseconds)
        local_close = O.wire._directed_deadline(local, maximum, close, first.nanoseconds)
        self._binding = (first, local, boot, cancelled, environment, seed, entry,
            (start, work, close, local_work, local_close), mode)
        _CLOCKS[id(self)] = _ClockAnchor(self, self._binding,
            (first_graph, N._history_graph(environment, seed)), latch, attempts, entry,
            first.nanoseconds, local)
        self.current()

    def _anchor(self):
        anchor = _CLOCKS.get(id(self))
        require(type(self) is _Clock and type(anchor) is _ClockAnchor and anchor.clock is self,
            "ORIGINAL_CLOCK")
        return anchor

    def fail(self, error):
        anchor = self._anchor()
        if anchor.failure is None:
            # The original latch is independent of both mutable aliases and
            # callback-facing bindings. Restoring either cannot clear failure.
            anchor.failure = anchor.latch.fail(error)
        return anchor.failure

    def _checked_anchor(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            require(self._binding is anchor.binding and _ENTRY is anchor.latch and
                _ATTEMPTS is anchor.attempts and anchor.binding[6] is anchor.entry, "CLOCK_BINDING")
            for graph in (*anchor.graph, *anchor.returns):
                N._check_history(graph)
            if anchor.tightening is not None:
                require(anchor.binding[8] == "finish", "FINITE_TIGHTENING_MODE")
                N._check_history(anchor.tightening[3])
            anchor.latch.check(anchor.attempts, anchor.entry)
            require(dict(os.environ) == anchor.binding[4], "ENVIRONMENT_CHANGED")
            require(not native.QUARANTINE and not Q.QUARANTINE and not C.C.QUARANTINE and
                not C._PRIMARY_QUARANTINE and not native.diagnostics._QUARANTINE, "UNKNOWN_NATIVE_OWNER")
            if anchor.owner is not None:
                owner, original = anchor.owner
                require(owner._anchor() is original and owner.owner.fence is self and
                    owner.owner.first is anchor.binding[0], "ORIGINAL_FILE_OWNER")
                owner.structural()
                require(owner.failure is None and not owner.owner.unknown, "FILE_OWNER_FAILED")
            if anchor.content is not None:
                graph, policy_start, policy_end, match_start, match_end = anchor.content
                N._check_history(graph)
                now = int(time.time())
                require(policy_start <= now < policy_end and match_start <= now < match_end,
                    "ORIGINAL_POLICY_OR_AUTHORIZATION_EXPIRED")
            return anchor
        except BaseException as error:
            raise self.fail(error)

    def current(self):
        # Detached scalar diagnostics, not a view of the original authority.
        # Callers cannot replace a graph, erase failure or adopt a new latch
        # through a returned status object. Internal users retain _anchor().
        anchor = self._checked_anchor()
        caps = self._caps(anchor)
        return MappingProxyType({"first": anchor.binding[0].nanoseconds, "last": anchor.last,
            "localLast": anchor.local_last, "work": caps[1], "final": caps[2],
            "busy": anchor.busy, "ownerAttached": anchor.owner is not None,
            "contentBound": anchor.content is not None, "retainedReturns": len(anchor.returns)})

    reading = property(lambda self: self._checked_anchor().binding[0])
    clock = property(lambda self: self.reading.clock)
    first = property(lambda self: self.reading.nanoseconds)
    seed = property(lambda self: self._checked_anchor().binding[5])
    mode = property(lambda self: self._checked_anchor().binding[8])
    work = property(lambda self: self._caps(self._checked_anchor())[1])
    final = property(lambda self: self._caps(self._checked_anchor())[2])
    local_end = property(lambda self: self._caps(self._checked_anchor())[4])

    @staticmethod
    def _caps(anchor):
        return anchor.binding[7] if anchor.tightening is None else anchor.tightening[2]

    def tighten_finish(self, ready_raw, final_raw):
        anchor = self._begin()
        try:
            require(anchor.binding[8] == "finish" and anchor.tightening is None and
                anchor.owner is None and anchor.content is None, "FINISH_TIGHTEN_ONCE_BEFORE_FILES")
            original, final = D.stream_ready(ready_raw), D.stream_closed(final_raw, ready_raw)
            graph = N._history_graph(ready_raw, final_raw, original, final)
            require(D.O.encoded(original["deadline"]) == D.O.encoded(anchor.binding[5]) and
                D.decimal(final["closedNs"]) <= anchor.binding[0].nanoseconds <
                D.decimal(original["workEndNs"]) < D.decimal(original["closeEndNs"]) <= anchor.binding[7][2],
                "FINISH_ORIGINAL_STREAM_CAPS")
            work, close = D.decimal(original["workEndNs"]), D.decimal(original["closeEndNs"])
            first, local = anchor.binding[0].nanoseconds, anchor.binding[1]
            caps = (anchor.binding[7][0], work, close,
                min(anchor.binding[7][3], O.wire._directed_deadline(local, 900, work, first)),
                min(anchor.binding[7][4], O.wire._directed_deadline(local, 900, close, first)))
            anchor.tightening = (ready_raw, final_raw, caps, graph)
            self.current()
            self._observe(anchor, False, 0, None)
        except BaseException as error:
            raise self.fail(error)
        finally:
            anchor.busy = False

    def _begin(self):
        anchor = self._anchor()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            self.current()
            require(not anchor.busy, "CLOCK_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self.fail(error)

    def _observe(self, anchor, final, minimum, limit):
        require(type(final) is bool, "FINAL_TYPE")
        caps = self._caps(anchor)
        end = caps[2 if final else 1]
        if limit is not None:
            end = min(end, D.integer(limit))
        frontier = max(anchor.last, D.integer(minimum))
        for index in range(2):
            local = C.local_value(time.monotonic())
            require(anchor.local_last <= local < caps[4 if final else 3], "LOCAL_EXPIRED_OR_BACKWARDS")
            anchor.local_last = local
            self.current()
            observed = O.clocks.checked_now(anchor.binding[0].clock, minimum_ns=frontier)
            anchor.last = frontier = O.integer(observed, frontier)
            self.current()
            require(frontier < end and anchor.busy and anchor.failure is None, "RAW_EXPIRED_OR_CHANGED")
            boot = K.continuity.boot_digest(anchor.binding[0].clock.role)
            self.current()
            require(boot == anchor.binding[2], "BOOT_CHANGED")
            if index == 0:
                anchor.binding[3]()
                self.current()
                require(anchor.last == frontier and anchor.local_last == local and
                    anchor.failure is None and anchor.busy, "CALLBACK_CHANGED")
        local = C.local_value(time.monotonic())
        require(anchor.local_last <= local < caps[4 if final else 3], "LOCAL_RETURN_EXPIRED")
        anchor.local_last = local
        self.current()
        require(anchor.last == frontier and anchor.failure is None and anchor.busy, "CLOCK_RETURN_CHANGED")
        return frontier

    def now(self, *, final=False, minimum=0, limit=None):
        anchor = self._begin()
        try:
            return self._observe(anchor, final, minimum, limit)
        except BaseException as error:
            raise self.fail(error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        anchor = self._begin()
        try:
            require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 900,
                "OPERATION_MAXIMUM")
            local = C.local_value(time.monotonic())
            observed = self._observe(anchor, final, 0, limit)
            caps = self._caps(anchor)
            end = caps[2 if final else 1]
            if limit is not None:
                end = min(end, D.integer(limit))
            result = min(caps[4 if final else 3],
                O.wire._directed_deadline(local, maximum, end, observed))
            self.current()
            return result
        except BaseException as error:
            raise self.fail(error)
        finally:
            anchor.busy = False

    def attach(self, owner):
        anchor = self._anchor()
        try:
            require(anchor.owner is None and type(owner) is C._PrimaryOwner and
                (anchor.binding[8] != "finish" or anchor.tightening is not None), "ATTACH_NEW_OWNER")
            anchor.owner = (owner, owner._anchor())  # Retain before any owner callback.
            self.current()
            require(owner.owner.fence is self and owner.owner.first is anchor.binding[0] and not owner.rows,
                "ATTACH_EMPTY_ORIGINAL_OWNER")
        except BaseException as error:
            raise self.fail(error)

    def bind_content(self, raws, parsed, observations):
        anchor = self._anchor()
        try:
            graph = N._history_graph(raws, parsed, observations)  # Before another callback.
            require(anchor.content is None, "BIND_INPUTS_ONCE")
            policy, match = parsed[4], parsed[5]
            anchor.content = (graph, policy["notBefore"], policy["expiresAt"],
                match["notBefore"], match["expiresAt"])
            self.current()
        except BaseException as error:
            raise self.fail(error)

    def retain(self, *returned):
        anchor = self._anchor()
        try:
            graph = N._history_graph(*returned)  # First return, not a later equal snapshot.
            anchor.returns = (*anchor.returns, graph)
            self.current()
        except BaseException as error:
            raise self.fail(error)


def _pipe_identity(stream, number):
    require(type(stream) is io.TextIOWrapper and not stream.closed and stream.fileno() == number,
        "ORIGINAL_STDIO_WRAPPER")
    buffer = stream.buffer
    require(type(buffer) in (io.BufferedReader, io.BufferedWriter, io.FileIO) and
        not buffer.closed and buffer.fileno() == number, "ORIGINAL_STDIO_BUFFER")
    raw = buffer if type(buffer) is io.FileIO else buffer.raw
    require(type(raw) is io.FileIO and not raw.closed and raw.fileno() == number, "ORIGINAL_STDIO_RAW")
    info = os.fstat(number)
    require(stat.S_ISFIFO(info.st_mode), "ORIGINAL_PIPE_ONLY")
    handle = None
    if os.name == "nt":
        import msvcrt
        handle = msvcrt.get_osfhandle(number)
        require(type(handle) is int and handle not in (-1, 0), "ORIGINAL_WINDOWS_PIPE")
    return stream, buffer, raw, number, (info.st_dev, info.st_ino, info.st_mode), handle


class _Pipes:
    """Retain the three original standard handles, without blocking pipe calls.

    Python3.12+ supports nonblocking anonymous pipes on Windows. Unsupported
    hosts refuse; no thread that could outlive its owner or SIGTERM-as-close
    fallback is introduced. No child/process/network is created here.
    """
    __slots__ = ()

    def __init__(self, clock, *, mode="stream"):
        require(type(self) is _Pipes and id(self) not in _PIPES, "PIPE_OWNER_ONCE")
        require(type(mode) is str and mode in ("stream", "finish", "after") and clock.mode == mode,
            "PIPE_FIXED_MODE")
        # Registration only. Caller assignment must complete BEFORE configure
        # can fail. Indexed originals survive even an incomplete pin operation.
        originals = (sys.stdin, sys.stdout, sys.stderr)
        state = {"owner": self, "clock": clock, "originals": originals, "pins": (None, None, None),
            "closed": set(), "attempted": set(), "unknown": set(), "failure": None, "eof": False,
            "configuring": False, "configured": False, "close_started": False, "closing": False,
            "mode": mode, "input_started": False, "input_done": False, "output_phase": "NEW"}
        _PIPES[id(self)] = state

    def configure(self):
        state = self._anchor()
        try:
            require(not state["configured"] and not state["configuring"] and state["failure"] is None,
                "PIPE_CONFIGURE_ONCE")
            state["configuring"] = True
            state["clock"].current()
            for number, stream in enumerate(state["originals"]):
                pin = _pipe_identity(stream, number)
                state["pins"] = (*state["pins"][:number], pin, *state["pins"][number + 1:])
            require(len({id(value) for pin in state["pins"] for value in pin[:3]}) >= 6, "PIPE_WRAPPER_ALIAS")
            for number in (0, 1):
                require(_pipe_identity(state["originals"][number], number) == state["pins"][number],
                    "CONFIGURE_ORIGINAL_PIPE")
                os.set_blocking(number, False)
                require(os.get_blocking(number) is False, "NONBLOCKING_PIPE_REQUIRED")
            state["configured"] = True
            self._checked_anchor()
        except BaseException as error:
            raise self._remember(state, error)
        finally:
            state["configuring"] = False

    def _anchor(self):
        state = _PIPES.get(id(self))
        require(type(self) is _Pipes and type(state) is dict and state["owner"] is self, "PIPE_ORIGINAL_OWNER")
        return state

    @staticmethod
    def _snapshot(state):
        # No live mappings, sets, clock, exceptions or wrappers escape. The
        # IDs are diagnostics only; all operations use the retained originals.
        return MappingProxyType({"clock": id(state["clock"]),
            "originals": tuple(id(value) for value in state["originals"]),
            "pins": tuple(None if pin is None else
                (tuple(id(value) for value in pin[:3]), pin[3], tuple(pin[4]), pin[5]) for pin in state["pins"]),
            "closed": frozenset(state["closed"]), "attempted": frozenset(state["attempted"]),
            "unknown": frozenset(state["unknown"]), "failure": state["failure"] is not None,
            "eof": state["eof"], "configured": state["configured"], "configuring": state["configuring"],
            "close_started": state["close_started"], "closing": state["closing"], "mode": state["mode"],
            "input_started": state["input_started"], "input_done": state["input_done"],
            "output_phase": state["output_phase"]})

    def state(self):
        return self._snapshot(self._anchor())

    def _remember(self, state, error):
        # Save to the original pipe first, then poison the independently
        # retained ORIGINAL U clock/latch. A swallowed late pipe error cannot
        # leave stream()/main() eligible for a successful return.
        if state["failure"] is None:
            state["failure"] = error
        state["failure"] = state["clock"].fail(state["failure"])
        return state["failure"]

    def _checked_anchor(self):
        state = self._anchor()
        if state["failure"] is not None:
            raise state["failure"]
        try:
            require(state["configured"] and not state["closing"] and all(original is visible
                for original, visible in zip(state["originals"], (sys.stdin, sys.stdout, sys.stderr))) and
                type(state["pins"]) is tuple and len(state["pins"]) == 3, "PIPE_FAILED_OR_REPLACED")
            state["clock"].current()
            require(state["clock"].mode == state["mode"], "PIPE_ORIGINAL_MODE")
            for expected, pin in enumerate(state["pins"]):
                stream, buffer, raw, number, metadata, handle = pin
                require(number == expected and stream is state["originals"][number], "PIPE_ORIGINAL_SLOT")
                if number in state["closed"]:
                    require(stream.closed and buffer.closed and raw.closed, "PIPE_REOPENED")
                else:
                    require(_pipe_identity(stream, number) == pin and
                        (number == 2 or os.get_blocking(number) is False), "PIPE_CHANGED")
            state["clock"].current()
            if state["failure"] is not None:
                raise state["failure"]
            return state
        except BaseException as error:
            raise self._remember(state, error)

    def current(self):
        return self._snapshot(self._checked_anchor())

    def pause(self):
        state = self._anchor()
        try:
            self._checked_anchor()
            require(not state["close_started"] and (not state["eof"] or
                state["mode"] != "stream" and state["input_done"] and state["output_phase"] == "FINAL_WRITING"),
                "PIPE_WAIT_STATE")
            deadline = state["clock"].deadline(0.005)
            remaining = deadline - time.monotonic()
            require(remaining > 0, "PIPE_WAIT_EXPIRED")
            time.sleep(remaining)  # Never a fresh allowance: clipped by original RAW/LOCAL.
            state["clock"].now()
            self._checked_anchor()
        except BaseException as error:
            raise self._remember(state, error)

    def demand(self, *, eof=False):
        state = self._anchor()
        try:
            self._checked_anchor()
            require(type(eof) is bool and not state["eof"] and not state["close_started"] and
                0 not in state["closed"] and (state["mode"] == "stream" or
                    eof and state["input_started"] and not state["input_done"]), "DEMAND_STATE")
            while True:
                state["clock"].now()
                self._checked_anchor()
                try:
                    raw = os.read(0, 1)
                except BlockingIOError:
                    self.pause()
                    continue
                state["clock"].now()
                require(type(raw) is bytes and raw == (b"" if eof else b"N"), "EXACT_NEXT_OR_CANCELLATION")
                if eof:
                    state["eof"] = True
                self._checked_anchor()
                return
        except BaseException as error:
            raise self._remember(state, error)

    def frame(self, kind, raw):
        state = self._anchor()
        try:
            self._checked_anchor()
            require(not state["close_started"] and 1 not in state["closed"], "FRAME_STATE")
            if state["mode"] == "stream":
                require(not state["eof"], "FRAME_STATE")
            elif kind == b"R":
                require(state["mode"] == "after" and not state["eof"] and not state["input_started"] and
                    state["output_phase"] == "NEW", "FINITE_READY_ORDER")
                state["output_phase"] = "READY_WRITING"
            else:
                require(kind == b"F" and state["eof"] and state["input_done"] and
                    state["output_phase"] == ("NEW" if state["mode"] == "finish" else "READY"), "FINITE_FINAL_ORDER")
                state["output_phase"] = "FINAL_WRITING"
            require(type(kind) is bytes and kind in (b"R", b"D", b"F") and type(raw) is bytes and
                0 < len(raw) <= (Z.CHUNK_BYTES if kind == b"D" else D.LIMIT), "FRAME_BOUND")
            packet, offset = kind + len(raw).to_bytes(4, "big") + raw, 0
            while offset < len(packet):
                state["clock"].now()
                self._checked_anchor()
                try:
                    written = os.write(1, memoryview(packet)[offset:])
                except BlockingIOError:
                    self.pause()
                    continue
                require(type(written) is int and 0 < written <= len(packet) - offset, "PIPE_SHORT_WRITE")
                offset += written
                state["clock"].now()
                self._checked_anchor()
            if state["mode"] != "stream":
                state["output_phase"] = "READY" if kind == b"R" else "FINAL"
        except BaseException as error:
            raise self._remember(state, error)

    def control(self):
        """One complete bounded I, then original EOF; no N or trailing byte."""
        state = self._anchor()
        try:
            self._checked_anchor()
            require(state["mode"] in ("finish", "after") and not state["input_started"] and
                not state["eof"] and not state["close_started"] and state["output_phase"] ==
                ("NEW" if state["mode"] == "finish" else "READY"), "FINITE_INPUT_ONCE")
            state["input_started"] = True

            def read_exact(count):
                # Header is validated before allocation/read of its payload.
                require(type(count) is int and 0 < count <= D.INPUT_BYTES, "FINITE_READ_BOUND")
                parts, total = [], 0
                while total < count:
                    state["clock"].now()
                    self._checked_anchor()
                    wanted = min(65536, count - total)
                    try:
                        raw = os.read(0, wanted)
                    except BlockingIOError:
                        self.pause()
                        continue
                    require(type(raw) is bytes and 0 < len(raw) <= wanted, "FINITE_TRUNCATED_INPUT")
                    parts.append(raw)
                    total += len(raw)
                    state["clock"].now()
                    self._checked_anchor()
                return b"".join(parts)

            header = read_exact(5)
            size = int.from_bytes(header[1:], "big")
            require(header[:1] == b"I" and 0 < size <= D.INPUT_BYTES, "FINITE_INPUT_HEADER")
            raw = read_exact(size)
            self.demand(eof=True)
            state["input_done"] = True
            self._checked_anchor()
            return raw
        except BaseException as error:
            raise self._remember(state, error)

    def close(self, failure=None):
        state, entered = self._anchor(), False
        try:
            if failure is not None:
                self._remember(state, failure)
            require(not state["closing"] and not state["close_started"], "PIPE_CLOSE_RETRY")
            state["close_started"], state["closing"], entered = True, True, True
            # Cleanup deliberately does not require a live clock. All handles,
            # pins and attempts come from the SAME locally retained authority.
            for number in (0, 1, 2):
                if number in state["attempted"] or number in state["unknown"]:
                    continue
                try:
                    pin = state["pins"][number]
                    require(pin is not None and pin[0] is state["originals"][number] and
                        _pipe_identity(pin[0], number) == pin, "CLOSE_ORIGINAL_PIPE")
                    state["attempted"].add(number)  # Once, before the actual original close.
                    pin[0].close()
                    require(all(value.closed for value in pin[:3]), "PIPE_CLOSE_RETURN")
                    try:
                        os.fstat(number)
                    except OSError as error:
                        require(error.errno == errno.EBADF, "PIPE_CLOSE_DESCRIPTOR_ERROR")
                    else:
                        require(False, "PIPE_DESCRIPTOR_STILL_OPEN")
                    state["closed"].add(number)
                except BaseException as error:
                    state["unknown"].add(number)
                    self._remember(state, error)
            if state["failure"] is not None:
                raise state["failure"]
            require(state["eof"] and state["closed"] == {0, 1, 2} and (state["mode"] == "stream" or
                state["input_done"] and state["output_phase"] == "FINAL"), "ORIGINAL_PIPE_CLOSE_REQUIRED")
        except BaseException as error:
            raise self._remember(state, error)
        finally:
            if entered:
                state["closing"] = False
                if len(state["closed"]) != 3 and not any(value is self for value in _QUARANTINE):
                    _QUARANTINE.append(self)


def _input_read(owner, private, name, maximum):
    require(name in D.INPUT_LIMITS and maximum == D.INPUT_LIMITS[name], "FIXED_INPUT_ROSTER")
    if name.startswith("returned/"):
        path = K._source_path(name)
        directory = C._private(owner, path.parent)
        leaf = path.name
    else:
        directory, leaf = private, name
    directory_native = K._directory_native(directory)
    file = K._open_file(owner, directory, leaf, maximum)
    stamp = K._native_info(file.reader.initial_info) if os.name == "nt" else K.CD.native(
        ("posix", *native.posix._stamp(os.fstat(file.reader.fileno()))), directory=False)
    raw = K._stream(file, retain=True, close=True)
    K._file_current(file, closed=True)
    require(K._directory_native(directory) == directory_native, "INPUT_ORIGINAL_DIRECTORY_METADATA")
    if directory is not private:
        owner.close_one(directory)
    return raw, file.raw, stamp, directory_native


def _inputs(owner, clock, kind):
    paths = K._paths()  # Fixed original custody location, no event/source read.
    root = C._private(owner, paths["root"])
    private = C._private(owner, paths["tail-returned"])
    output = C._private(owner, paths["root"] / "upload-output")
    K._names(owner, private, K.PRIVATE_CLOSED_NAMES)
    K._names(owner, output, Z.MEMBERS)
    raws, observations = {}, ()
    for name, maximum in D.INPUT_LIMITS.items():
        raw, metadata, stamp, directory_native = _input_read(owner, private, name, maximum)
        raws[name] = raw
        observations = (*observations, (name, metadata, raw, stamp, directory_native))
    index = TD.canonical(raws["source-index.json"])
    for name, metadata, raw, stamp, directory_native in observations:
        if name.startswith("returned/"):
            rows = [row for row in index["files"] if row["relative"] == name]
            require(len(rows) == 1 and list(stamp) == rows[0]["native"] and list(directory_native) ==
                rows[0]["directoryNative"], "ORIGINAL_R_FILE_METADATA_BINDING")
    parsed = D.retained_inputs(raws, environment=dict(os.environ), kind=kind, seed=clock.seed,
        before_sha256=os.environ[TD.HASH_ENV], now=int(time.time()))
    clock.bind_content(raws, parsed, observations)
    pending, carrier, context, _observed, policy, match = parsed
    # Retain K's complete native context grammar, including exact fixed paths,
    # original directory identities and the original inherited parent context.
    caps = tuple(context["caps"][name] for name, _flag in K.CAP_FIELDS)
    require(K._context(raws["context.json"], clock.seed, caps, clock.clock) == context and
        context["inheritedContext"] == Q._inherited_context() and
        tuple(root.identity) == tuple(context["directories"]["root"]) and
        tuple(private.identity) == tuple(context["directories"]["tail-returned"]) and
        tuple(output.identity) == TD.identity(carrier["carrier"]["identity"], clock.clock.role), "ORIGINAL_DIRECTORIES")
    require(len({tuple(value.identity) for value in (root, private, output)}) == 3 and
        pending["times"]["pendingPreparedNs"] <= clock.first, "INPUT_TIME_OR_DIRECTORY_ALIAS")
    manifests = []
    for index in (1, 3):
        file = K._open_file(owner, output, Z.MEMBERS[index], Z.MANIFEST_BYTES)
        require(file.raw == O.encoded(carrier["files"][index]["readback"]["metadata"]), "MANIFEST_POST_CLOSE_METADATA")
        manifests.append(K._stream(file, pending["members"][index]["sha256"], retain=True, close=True))
        K._file_current(file, closed=True)
    D.manifests(pending, *manifests, policy=policy, match=match)
    clock.current()
    return root, private, output, raws, tuple(observations), parsed


def _member(owner, output, pending, carrier, index):
    """One real reader per member, consumed only after Node's original demand."""
    require(type(index) is int and 0 <= index < 4, "LITERAL_MEMBER_INDEX")
    declared = pending["members"][index]
    maximum = Z.MANIFEST_BYTES if index in (1, 3) else TD.MAX_ZIP_BYTES
    file = K._open_file(owner, output, Z.MEMBERS[index], maximum)
    require(file.count == declared["bytes"] and
        file.raw == O.encoded(carrier["files"][index]["readback"]["metadata"]), "MEMBER_POST_CLOSE_METADATA")
    total, digest = 0, hashlib.sha256()
    try:
        K._file_current(file)
        require(file.reader.seek(0) == 0, "MEMBER_INITIAL_POSITION")
        while total < file.count:
            owner.guard()
            raw = file.reader.read(min(Z.CHUNK_BYTES, file.count - total))
            require(type(raw) is bytes and 0 < len(raw) <= min(Z.CHUNK_BYTES, file.count - total), "MEMBER_SHORT_READ")
            total += len(raw)
            digest.update(raw)
            owner.guard()
            yield raw
        owner.guard()
        tail = file.reader.read(1)
        require(type(tail) is bytes and tail == b"" and total == declared["bytes"] and
            digest.hexdigest() == declared["sha256"], "MEMBER_EOF_SIZE_HASH")
        K._file_current(file)
        owner.guard()
    except BaseException as error:
        raise owner.remember(error)
    finally:
        if not owner.owner.unknown:
            owner.close_one(file.reader)
        if owner.failure is not None:
            raise owner.failure
    K._file_current(file, closed=True)


def stream(kind, cancelled):
    latch, attempts = _ENTRY, _ATTEMPTS
    entry = latch.begin(attempts)
    clock = owner = pipes = zipper = None
    failure = None
    try:
        local = C.local_value(time.monotonic())
        first = O.clocks.observe()
        first_graph = N._history_graph(first)
        boot = K.continuity.boot_digest(first.clock.role)
        N._check_history(first_graph)
        environment, seed = _environment()
        N._check_history(first_graph)
        clock = _Clock(first, local, boot, cancelled, environment, seed, entry,
            first_graph=first_graph, latch=latch, attempts=attempts)
        pipes = _Pipes(clock)
        pipes.configure()
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=first, cancelled=cancelled))
        clock.attach(owner)
        root, private, output, raws, observations, parsed = _inputs(owner, clock, kind)
        pending, carrier, context, _observed, policy, match = parsed
        ready_raw = D.ready(pending, context, policy=policy, match=match, first_raw=first.nanoseconds,
            before_sha256=os.environ[TD.HASH_ENV], carrier_sha256=D.sha(raws[TD.PRIVATE_CARRIER_CLOSE]), now=int(time.time()))
        zipper = Z.stored_zip(pending["members"], lambda index: _member(owner, output, pending, carrier, index))
        pipes.frame(b"R", ready_raw)  # No payload supplier or next(zipper) before original N.
        while True:
            pipes.demand()
            try:
                raw = next(zipper)
            except StopIteration as returned:
                zip_result = returned.value
                clock.retain(zip_result)
                break
            pipes.frame(b"D", raw)
        # The last N authorizes final completion, not extra payload. Retained
        # small K originals are reread with full metadata equality before close.
        for name, metadata, expected, stamp, directory_native in observations:
            raw, current, native_stamp, parent_stamp = _input_read(owner, private, name, D.INPUT_LIMITS[name])
            require(raw == expected and current == metadata and native_stamp == stamp and parent_stamp == directory_native,
                "K_INPUT_READBACK_CHANGED")
        K._names(owner, private, K.PRIVATE_CLOSED_NAMES)
        K._names(owner, output, Z.MEMBERS)
        root.verify()
        owner.guard()
        close_raw = owner.finish()
        K._closed_files(owner)
        closed_ns = clock.now()
        final_raw = D.stream_final(before_sha256=os.environ[TD.HASH_ENV], ready_raw=ready_raw,
            zip_result=zip_result, close_raw=close_raw, closed_ns=closed_ns)
        clock.current()
        pipes.frame(b"F", final_raw)
        pipes.demand(eof=True)
        clock.now()
        pipes.close()
        clock.now()
        latch.complete(attempts, entry, final_raw)
        latch.returned(attempts, entry, final_raw)
        return clock
    except BaseException as error:
        failure = latch.fail(error)
        raise failure
    finally:
        if failure is not None:
            if zipper is not None:
                try:
                    zipper.close()
                except BaseException:
                    pass  # Preserve the first failure, no success/Finalize.
            if owner is not None and not owner.finished:
                owner.remember(failure)
                try:
                    owner.finish()
                except BaseException:
                    pass
            if pipes is not None:
                try:
                    pipes.close(failure)
                except BaseException:
                    pass


def _upload_carrier(environment):
    require(environment.get(D.UPLOAD_OUTCOME_ENV) == "success", "ORIGINAL_UPLOAD_STEP_RETURN")
    return {"directoryIdentitySha256": D.digest(environment.get(D.UPLOAD_DIRECTORY_ENV)),
        "fileMetadataSha256": D.digest(environment.get(D.UPLOAD_METADATA_ENV)),
        "fileOwnerCloseSha256": D.digest(environment.get(D.UPLOAD_CLOSE_ENV))}


def _returned_directory(owner, clock, root, *, create):
    require(type(create) is bool, "RETURNED_DIRECTORY_MODE")
    expected = (*K._root_names(upload=True), *(("upload-returned",) if not create else ()))
    K._names(owner, root, expected)
    path = root.path / "upload-returned"
    if create:
        end = owner.guard()
        directory = owner.acquire("directory", lambda: root.create_directory("upload-returned", deadline=end))
    else:
        directory = C._private(owner, path)
    require(type(directory) is (native.windows.PrivateDirectory if os.name == "nt" else Q._PosixDirectory),
        "RETURNED_DIRECTORY_TYPE")
    identity = native.directory_identity(list(directory.identity), clock.clock.role)
    identity_raw = O.encoded(identity)  # Actual identity only; no mutable directory timestamps.
    clock.retain(path, directory.path, identity, identity_raw)
    require(directory.path == path and tuple(directory.identity) == tuple(identity) and
        tuple(directory.identity) != tuple(root.identity), "RETURNED_ORIGINAL_DIRECTORY")
    directory.verify()
    K._names(owner, directory, () if create else (D.UPLOAD_FILE,))
    owner.guard()
    return directory, identity_raw


def _read_pending(owner, clock, directory, name, checksum):
    require(name in (D.UPLOAD_FILE, D.AFTER_FILE), "FIXED_PENDING_FILE")
    file = K._open_file(owner, directory, name, D.LIMIT)
    raw = K._stream(file, checksum, retain=True, close=True)
    clock.retain(raw, file.raw)  # Capture original read return before another callback.
    K._file_current(file, closed=True)
    return raw, file.raw


def _final_inputs(owner, clock, root, private, output, observations, pending, carrier):
    """Small originals/metadata only; never reopen either ciphertext here."""
    for name, metadata, expected, stamp, directory_native in observations:
        raw, current, native_stamp, parent_stamp = _input_read(owner, private, name, D.INPUT_LIMITS[name])
        require(raw == expected and current == metadata and native_stamp == stamp and parent_stamp == directory_native,
            "FINITE_K_READBACK_CHANGED")
    for index in (1, 3):
        file = K._open_file(owner, output, Z.MEMBERS[index], Z.MANIFEST_BYTES)
        require(file.raw == O.encoded(carrier["files"][index]["readback"]["metadata"]),
            "FINITE_MANIFEST_METADATA_CHANGED")
        K._stream(file, pending["members"][index]["sha256"], retain=True, close=True)
        K._file_current(file, closed=True)
    K._names(owner, private, K.PRIVATE_CLOSED_NAMES)
    K._names(owner, output, Z.MEMBERS)
    K._names(owner, root, (*K._root_names(upload=True), "upload-returned"))
    root.verify()
    clock.now()


def finite(kind, cancelled, mode):
    """Fixed finish/A, sharing original RAW and LOCAL caps through return."""
    latch, attempts = _ENTRY, _ATTEMPTS
    entry = latch.begin(attempts)
    clock = owner = pipes = None
    failure = None
    try:
        require(type(mode) is str and mode in ("finish", "after"), "FINITE_FIXED_MODE")
        local = C.local_value(time.monotonic())
        first = O.clocks.observe()
        first_graph = N._history_graph(first)
        boot = K.continuity.boot_digest(first.clock.role)
        N._check_history(first_graph)
        environment, seed = _environment()
        N._check_history(first_graph)
        clock = _Clock(first, local, boot, cancelled, environment, seed, entry,
            first_graph=first_graph, latch=latch, attempts=attempts, mode=mode)
        pipes = _Pipes(clock, mode=mode)
        pipes.configure()
        if mode == "finish":
            input_raw = pipes.control()
            clock.retain(input_raw)
            control = D.control_input(input_raw, mode)
            clock.retain(control)
            ready_raw = control[2]
            clock.tighten_finish(ready_raw, control[3])  # Before ANY file owner/path read.
            observed = D.finish_observations(control, now=int(time.time()))
            clock.retain(observed)
        else:
            upload_carrier = _upload_carrier(environment)
            upload_hash = D.digest(environment.get(D.UPLOAD_HASH_ENV))
            clock.retain(upload_carrier, upload_hash)
        owner = C._PrimaryOwner(native.Owner(clock.local_end, clock, first=first, cancelled=cancelled))
        clock.attach(owner)
        root, private, output, raws, observations, parsed = _inputs(owner, clock, kind)
        pending, carrier, context, _observed, policy, match = parsed
        if mode == "finish":
            require(observed[0]["beforeSha256"] == environment[TD.HASH_ENV] and
                observed[0]["carrierCloseSha256"] == D.sha(raws[TD.PRIVATE_CARRIER_CLOSE]),
                "FINISH_ACTUAL_K_HASHES")
        directory, directory_raw = _returned_directory(owner, clock, root, create=mode == "finish")
        if mode == "after":
            require(D.sha(directory_raw) == upload_carrier["directoryIdentitySha256"], "UPLOAD_DIRECTORY_OUTPUT")
            upload_raw, upload_metadata = _read_pending(owner, clock, directory, D.UPLOAD_FILE, upload_hash)
            require(D.sha(upload_metadata) == upload_carrier["fileMetadataSha256"] and
                D.parse_delivery(upload_raw, "finish")["carrierCloseSha256"] == D.sha(raws[TD.PRIVATE_CARRIER_CLOSE]),
                "UPLOAD_ORIGINAL_METADATA_OR_CARRIER")
            ready_raw = D.after_ready(pending, upload_raw, policy=policy, match=match,
                first=first.nanoseconds, before_sha256=environment[TD.HASH_ENV], now=int(time.time()))
            clock.retain(ready_raw)
            pipes.frame(b"R", ready_raw)
            input_raw = pipes.control()
            clock.retain(input_raw)
            control = D.control_input(input_raw, mode)
            clock.retain(control)
        prepared, now = clock.now(), int(time.time())
        if mode == "finish":
            pending_raw = D.upload_pending(pending, context, policy=policy, match=match, control=control,
                observed=observed, finish_first=first.nanoseconds, prepared=prepared, now=now)
            name = D.UPLOAD_FILE
        else:
            pending_raw = D.delivery_pending(pending, context, upload_raw, ready_raw, policy=policy, match=match,
                control=control, carrier=upload_carrier, prepared=prepared, now=now)
            name = D.AFTER_FILE
        clock.retain(pending_raw)
        written = K._write_bytes(owner, directory, name, pending_raw)
        clock.retain(written)  # Original returned readback metadata, before other callbacks.
        file_raw = O.encoded(written["postCloseReadback"])
        _final_inputs(owner, clock, root, private, output, observations, pending, carrier)
        if mode == "after":
            repeated, metadata = _read_pending(owner, clock, directory, D.UPLOAD_FILE, upload_hash)
            require(repeated == upload_raw and metadata == upload_metadata, "UPLOAD_CHANGED_AFTER_OBSERVATIONS")
        actual, metadata = _read_pending(owner, clock, directory, name, D.sha(pending_raw))
        require(actual == pending_raw and metadata == file_raw, "PENDING_ORIGINAL_READBACK")
        D.parse_delivery(actual, mode)
        K._names(owner, directory, (D.UPLOAD_FILE,) if mode == "finish" else (D.UPLOAD_FILE, D.AFTER_FILE))
        require(O.encoded(native.directory_identity(list(directory.identity), clock.clock.role)) == directory_raw,
            "PENDING_DIRECTORY_CHANGED")
        directory.verify()
        owner.guard()
        close_raw = owner.finish()
        clock.retain(close_raw)
        K._closed_files(owner)
        closed = clock.now()
        final_raw = D.finite_result(mode, actual, ready_raw=ready_raw, input_raw=input_raw,
            directory_identity_raw=directory_raw, file_metadata_raw=file_raw,
            file_owner_close_raw=close_raw, closed_ns=closed)
        clock.retain(final_raw)
        pipes.frame(b"F", final_raw)  # Finite modes only: original I+EOF already complete.
        clock.now()
        pipes.close()
        clock.now()
        latch.complete(attempts, entry, final_raw)
        latch.returned(attempts, entry, final_raw)
        return clock
    except BaseException as error:
        failure = latch.fail(error)
        raise failure
    finally:
        if failure is not None:
            if owner is not None and not owner.finished:
                owner.remember(failure)
                try:
                    owner.finish()
                except BaseException:
                    pass
            if pipes is not None:
                try:
                    pipes.close(failure)
                except BaseException:
                    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("operation", choices=("stream", "finish", "after"))
    parser.add_argument("--kind", choices=("worker",), required=True)
    args = parser.parse_args()
    handlers, cancelled, clock, failure = {}, [], None, None
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            "ISOLATED_INTERPRETER_REQUIRED")
        for number in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if hasattr(signal, "SIGBREAK") else [])):
            handlers[number] = signal.getsignal(number)
            signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        cancel = lambda: native.cancellation(cancelled)
        clock = stream(args.kind, cancel) if args.operation == "stream" else finite(args.kind, cancel, args.operation)
    except BaseException as error:
        failure = error
    finally:
        for number, handler in handlers.items():
            try:
                signal.signal(number, handler)
            except BaseException as error:
                if failure is None:
                    failure = error
    if failure is None:
        try:
            native.cancellation(cancelled)
            clock.now()
        except BaseException as error:
            failure = error
    # No traceback, input, raw diagnostic, path, token or private evidence may
    # reach stderr/stdout. The Node caller sees only the original exit status.
    return 0 if failure is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
