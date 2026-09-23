#!/usr/bin/env python3
"""NEW fixed crypto parent/entry controls; authored, never qualification.

The maintained custody launcher/owner/Window and fixed dispatcher are used with
explicit supplied scope, capture, child, host and clock boundaries. No native
process, signal registration, GPG, network, Git or old test suite is run. In-
memory signal/capture suppliers exercise native.guarded's unchanged late checks;
files/ACKs remain distinct from actual supplied child and parent return events.
These models cannot establish genuine native ownership, measured210/45 fit,
current acquisition, custody Step success, owner approval or delivered evidence.
"""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr
import ctypes  # Initialize stdlib before the native-load refusal hook.
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_CRYPTO_NATIVE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("new_custody_crypto_native_controls",
    ROOT / "scripts/run-hosted-initial-recipient-custody.py")
D = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = D
_spec.loader.exec_module(D)
NS, BOOT = 1_000_000_000, "a" * 64


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class SignalModel:
    """Pure signal-list producer; never installs an operating-system handler."""
    SIGINT, SIGTERM = 2, 15

    def __init__(self):
        self.original = {2: object(), 15: object()}
        self.handlers, self.calls, self.installed = dict(self.original), [], {}

    def getsignal(self, number):
        return self.handlers[number]

    def signal(self, number, handler):
        self.calls.append((number, handler))
        self.handlers[number] = handler
        if callable(handler):
            self.installed[number] = handler

    def cancel(self):
        self.handlers[self.SIGTERM](self.SIGTERM, None)

    def pending_cancel(self):
        # Explicit pending-list mutation model, not a claim an OS handler
        # remains registered after native.guarded restored original handlers.
        self.installed[self.SIGTERM](self.SIGTERM, None)


class Sink(io.BytesIO):
    def __init__(self):
        super().__init__()
        self.on_write, self.on_flush = lambda: None, lambda: None

    def write(self, raw):
        count = super().write(raw)
        self.on_write()
        return count

    def flush(self):
        self.on_flush()


class EntryClock:
    def __init__(self):
        self.calls, self.raw, self.hook = [], 1115 * NS, lambda: None

    def now(self, *, final=False, limit=None):
        self.calls.append((final, limit))
        self.hook()
        if self.raw >= limit:
            raise RuntimeError("SUPPLIED_ENTRY_EXPIRED")
        return self.raw


class Entry:
    """Actual fixed main+guarded, two supplied children and in-memory outputs."""
    def __init__(self, operation):
        self.operation, self.stack = operation, ExitStack()
        self.signal, self.sink, self.fence = SignalModel(), Sink(), EntryClock()
        self.calls, self.callback = [], lambda: None
        self.hash, self.minimum = "b" * 64, 1111 * NS
        self.argv = [str(ROOT / "scripts/run-hosted-initial-recipient-custody.py"), operation,
            "--context-sha256", self.hash, "--minimum-ns", str(self.minimum)]
        self.flags = SimpleNamespace(isolated=1, no_site=1)
        self.stderr = io.StringIO()
        self.leaf_closed = 1114 * NS
        self.value = None

    def __enter__(self):
        self.stack.enter_context(patch.dict(D.os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(D.native, "signal", self.signal))
        self.stack.enter_context(patch.object(D.native, "sys", SimpleNamespace(
            stdout=SimpleNamespace(buffer=self.sink), executable=sys.executable)))
        self.dispatch_sys = SimpleNamespace(argv=self.argv, flags=self.flags, dont_write_bytecode=True,
            executable=sys.executable, stderr=self.stderr, stdout=SimpleNamespace(buffer=self.sink))
        self.stack.enter_context(patch.object(D, "sys", self.dispatch_sys))
        self.stack.enter_context(patch.object(sys, "argv", self.argv))
        self.stack.enter_context(redirect_stderr(self.stderr))
        self.stack.enter_context(patch.object(D, "custody_authority_child", self.authority))
        self.stack.enter_context(patch.object(D, "custody_crypto_child", self.crypto))
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def child(self, operation, context_hash, minimum, cancelled):
        if not callable(cancelled):
            raise AssertionError("SUPPLIED_CHILD_REQUIRES_SIGNAL_CALLABLE_NOT_LIST")
        self.calls.append((operation, context_hash, minimum, cancelled))
        self.callback()
        cancelled()  # The real fixed adapter must consult the actual signal list.
        scope = (D.native.INITIAL_CUSTODY_AUTHORITY_ACK_SCOPE if operation == "_authority"
            else D._CRYPTO_ACK_SCOPE)
        self.value = {"schema": 1, "scope": scope, "invocation": "c" * 32,
            "terminalSha256": "d" * 64, "closedNs": self.leaf_closed}
        return self.value, self.fence, 1200 * NS

    def authority(self, context_hash, minimum, cancelled):
        return self.child("_authority", context_hash, minimum, cancelled)

    def crypto(self, context_hash, minimum, cancelled):
        return self.child("_crypto", context_hash, minimum, cancelled)

    def run(self):
        try:
            return D.main()
        except SystemExit as error:
            return error.code


class PhaseClock:
    def __init__(self):
        self.identity = D.O.clocks.ClockIdentity("linux-x64", D.O.clocks.DOMAINS["linux-x64"], NS)
        self.raw, self.local, self.hook = 1100 * NS, 100.0, lambda: None

    def reading(self):
        return D.O.clocks.Reading(self.identity, self.raw)

    def checked(self, expected, *, minimum_ns=0):
        if expected is not self.identity or self.raw < minimum_ns:
            raise AssertionError("SUPPLIED_NATIVE_ORIGINAL_CLOCK")
        return self.raw

    def advance(self, seconds):
        self.raw, self.local = 1100 * NS + seconds * NS, 100.0 + seconds

    def cancelled(self):
        self.hook()


class Phase:
    """Actual new phase hooks and owner, not a supplied native launch return."""
    def __init__(self, kind="worker"):
        self.kind, self.clock, self.stack = kind, PhaseClock(), ExitStack()

    def __enter__(self):
        self.stack.enter_context(patch.dict(D.os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(D.time, "monotonic", lambda: self.clock.local))
        self.stack.enter_context(patch.object(D.O.clocks, "checked_now", self.clock.checked))
        self.stack.enter_context(patch.object(D.C, "boot_digest", lambda _role: BOOT))
        for name in ("_WINDOWS", "_CUSTODY_OWNERS"):
            self.stack.enter_context(patch.object(D, name, {}))
        self.stack.enter_context(patch.object(D.native, "QUARANTINE", []))
        self.first = self.clock.reading()
        self.window = D.Window(self.first, self.clock.local, BOOT,
            D.schedule(self.kind, 1000 * NS, self.clock.raw), self.clock.cancelled)
        self.clock.advance(5)
        self.local_ceiling = self.window.deadline(255, final=True)
        self.owner = D._CustodyOwner(self.local_ceiling, self.window,
            first=self.first, cancelled=self.clock.cancelled)
        self.context = wire({"scope": D._CRYPTO_CONTEXT_SCOPE,
            "window": json.loads(D._custody_authority_window(self.window))})
        self.clock.advance(10)
        self.started = self.window.now()
        self.work = min(self.window.work, self.started + 210 * NS)
        self.final = min(self.window.final, self.work + 45 * NS)
        return self

    def __exit__(self, *args):
        return self.stack.__exit__(*args)

    def enter(self):
        self.owner.enter_crypto_phase(self.context, self.started, self.work, self.final)


class Stream:
    """Supplied native-file boundary; data lives only in Python memory."""
    def __init__(self, rig, directory, name, maximum, deadline):
        self.rig, self.directory, self.name = rig, directory, name
        self.maximum, self.deadline, self.raw = maximum, deadline, b""
        self.closed, self.close_calls, self.sync_calls = False, 0, 0
        self.close_error = self.sync_error = None

    def write(self, raw):
        if self.closed or len(self.raw) + len(raw) > self.maximum:
            raise AssertionError("SUPPLIED_CAPTURE_WRITE_STATE")
        self.raw += raw
        return len(raw)

    def sync(self):
        self.sync_calls += 1
        if self.sync_error is not None:
            raise self.sync_error
        self.verify()

    def verify(self):
        if self.closed or len(self.raw) > self.maximum:
            raise AssertionError("SUPPLIED_CAPTURE_VERIFY_STATE")
        return SimpleNamespace(size=len(self.raw))

    def observe_live_output(self):
        return self.verify()

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        if self.closed:
            raise AssertionError("SUPPLIED_CAPTURE_CLOSE_RETRY")
        self.closed = True


class Directory:
    def __init__(self, rig, path, identity, files):
        self.rig, self.path, self.identity, self.files = rig, path, identity, files
        self.closed, self.close_calls = False, 0

    def verify(self):
        if self.closed:
            raise AssertionError("SUPPLIED_DIRECTORY_CLOSED")

    def create_file(self, name, *, max_bytes, deadline):
        self.verify()
        if name in self.files:
            raise AssertionError("SUPPLIED_EXCLUSIVE_FILE_REUSE")
        stream = Stream(self.rig, self, name, max_bytes, deadline)
        self.files[name] = stream
        self.rig.allocations.append((name, stream))
        return stream

    def read_bytes(self, name, *, max_bytes, deadline):
        self.verify()
        self.rig.read_calls.append((self.path, name, deadline))
        value = self.files[name]
        if isinstance(value, Stream):
            if not value.closed:
                raise AssertionError("SUPPLIED_READ_BEFORE_CAPTURE_CLOSE")
            value = value.raw
        if type(value) is not bytes or len(value) > max_bytes or self.rig.clock.local >= deadline:
            raise AssertionError("SUPPLIED_READ_BOUND")
        self.rig.read_hook(name)
        return value

    def close(self):
        self.close_calls += 1
        if self.closed:
            raise AssertionError("SUPPLIED_DIRECTORY_CLOSE_RETRY")
        self.closed = True


class Child:
    def __init__(self, rig):
        self.rig, self.pid, self.stdout, self.stderr = rig, rig.scope.leader["pid"], None, None
        self.poll_calls = 0

    def poll(self):
        self.poll_calls += 1
        self.rig.poll_hook()
        return self.rig.exit_code


class Scope:
    def __init__(self, rig, job, invocation, state, home):
        self.rig, self.job, self.invocation, self.state, self.home = rig, job, invocation, state, home
        self.name, self.baseline = D.native.BACKENDS["linux-x64"], {(8000, 4000)}
        self.close_calls, self.spawn_calls, self.identity_calls = 0, 0, 0
        self.closed, self.drain_calls, self.launch = False, [], None
        self.leader = {"pid": os.getpid() + 100000, "startTicks": 5000}

    def _identity(self, pid):
        self.identity_calls += 1
        return {"pid": pid, "startTicks": 4000 + int(self.rig.preparer_changes and self.identity_calls > 1),
            "live": True}

    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        self.spawn_calls += 1
        if self.spawn_calls != 1:
            raise AssertionError("SUPPLIED_NATIVE_SPAWN_RETRY")
        self.launch = {"created": True, "requestedArgv": list(argv), "resolvedArgv": list(argv),
            "cwd": cwd, "pid": self.leader["pid"], "api": "subprocess.Popen", "shell": False,
            "executable": argv[0], "outputMode": "caller-owned-files"}
        self.rig.environment = dict(environment)
        self.rig.argv = list(argv)
        self.rig.child = Child(self.rig)
        if self.rig.valid_child_bytes:
            self.rig.prepare_child_transport()
        stdout.raw, stderr.raw = self.rig.ack_raw, self.rig.stderr_raw
        self.rig.private.files["crypto-child-result.json"] = self.rig.child_raw
        self.rig.spawn_hook()
        return self.rig.child

    def description(self):
        return {"backend": self.name, "job": self.job, "invocation": self.invocation,
            "scope": "controlled-marker-inheriting-descendants", "discoveryErrors": list(self.rig.discovery_errors),
            "launches": [] if self.launch is None else [dict(self.launch)],
            "startedIdentities": [] if self.launch is None else [dict(self.leader)],
            "discoveryReconciliations": []}

    def discover(self):
        return list(self.rig.descendants)

    def drain(self, *, grace, kill_wait, deadline):
        self.drain_calls.append((grace, kill_wait, deadline))
        if self.rig.drain_error is not None:
            raise self.rig.drain_error
        if self.rig.clock.local >= deadline:
            raise RuntimeError("SUPPLIED_ORIGINAL_DRAIN_CEILING_EXPIRED")
        return list(self.rig.survivors)

    def close(self):
        self.close_calls += 1
        if self.rig.scope_close_error is not None:
            raise self.rig.scope_close_error
        if self.closed:
            raise AssertionError("SUPPLIED_SCOPE_CLOSE_RETRY")
        self.closed = True


class Native(Phase):
    """Actual fixed launcher, modeled native resources and immutable I/O bytes."""
    def __init__(self, kind="worker"):
        super().__init__(kind)
        self.allocations, self.read_calls, self.make_calls = [], [], []
        self.scope = self.child = None
        self.exit_code, self.descendants, self.survivors = 0, [], []
        self.scope_close_error = self.drain_error = None
        self.preparer_changes = False
        self.discovery_errors = []
        self.valid_child_bytes = False
        self.poll_hook = self.spawn_hook = lambda: None
        self.read_hook = lambda _name: None
        self.check_hook, self.check_calls = lambda: None, 0
        self.ack_raw = wire({"schema": 1, "scope": "SUPPLIED_ACK_BYTES_NOT_A_VALIDATED_CHILD_RETURN"})
        self.child_raw = wire({"schema": 1, "scope": "SUPPLIED_CHILD_BYTES_NOT_A_VALIDATED_CHILD_RETURN"})
        self.stderr_raw = b""

    def __enter__(self):
        super().__enter__()
        self.stack.enter_context(patch.object(D, "_CRYPTO_NATIVE_RETURNS", {}))
        self.custody = Path("/SUPPLIED/primary-custody")
        self.path = self.custody / "returned"
        self.stores = {self.path: ((17, 201), {}), self.path / "crypto-service": ((17, 202), {})}
        self.stack.enter_context(patch.object(D.Q, "_PosixDirectory", self.directory))
        self.stack.enter_context(patch.object(D.Q, "_inherited_context", lambda: {}))
        self.stack.enter_context(patch.object(D, "_paths", self.paths))
        self.stack.enter_context(patch.object(D.native.processes, "make_scope", self.make_scope))
        self.stack.enter_context(patch.object(D.native, "phase",
            side_effect=AssertionError("ORDINARY_AUTHORITY_PHASE_MUST_NOT_RUN_FOR_CRYPTO")))
        self.private = self.owner.open(self.path)
        value = json.loads(self.context)
        value.update(kind=self.kind, job="b" * 32, inheritedContext={},
            directories={"returned": [17, 201], "crypto-service": [17, 202]},
            observed={"source": {"commit": "1" * 40, "tree": "2" * 40}},
            primary={"step": "initial-originals" if self.kind == "gate" else "canonical-initialization",
                "outcome": "success", "resultSha256": "3" * 64, "handoffSha256": "4" * 64,
                "inventorySha256": "5" * 64},
            authority={"returnSha256": "6" * 64, "matchSha256": "7" * 64, "copySha256": "8" * 64})
        self.context = wire(value)
        return self

    def prepare_child_transport(self):
        """SUPPLIED child outcome bytes, NOT execution of the real crypto child.

Only tests of the actual parent native return/byte authenticator use this
explicit boundary. The separately authored child controls test real closure;
this helper does not create a registry entry or reconstruct any live object.
"""
        context = json.loads(self.context)
        start_raw = self.stores[self.path / "crypto-service"][1]["start.json"].raw
        start = json.loads(start_raw)
        copied = {"mapSha256": "9" * 64, "memberCount": 7, "totalBytes": 99,
            "origins": {origin: str(number) * 64 for number, origin in enumerate(D.ORIGINS, 1)}}
        recipient = {"fingerprint": "A" * 40, "encryptionFingerprint": "B" * 40,
            "keySha256": "c" * 64, "expiresAt": 123456}
        self.manifest_raw = wire({"schema": 4, "scope": D.E.SCOPE, "kind": self.kind,
            "source": context["observed"]["source"], "primary": context["primary"], "copy": copied,
            "recipient": recipient, "initialRecipient": {"matchSha256": context["authority"]["matchSha256"],
                "freshReturnSha256": context["authority"]["returnSha256"]},
            "productiveAuthority": False, "cacheAuthority": False, "exportSaveAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED"})
        self.child_raw = wire({"schema": 1, "scope": D._CRYPTO_CHILD_SCOPE,
            "contextSha256": sha(self.context), "startSha256": sha(start_raw), "invocation": start["invocation"],
            "clock": D.O.clock_value(self.clock.identity), "bootDigest": BOOT,
            "launchMinimumNs": int(self.argv[-1]), "beganNs": self.clock.raw,
            "metadataLastNs": self.clock.raw, "metadataCloseSha256": "d" * 64,
            "validationStartedNs": self.clock.raw, "validationReturnedNs": self.clock.raw,
            "exportedNs": self.clock.raw, "recipientReturnSha256": "e" * 64, "recipient": recipient,
            "copy": copied, "freezeMetadataSha256": "f" * 64,
            "sourceMetadataSha256": {origin: str(number) * 64 for number, origin in enumerate(D.ORIGINS, 1)},
            "manifest": {"bytes": len(self.manifest_raw), "sha256": sha(self.manifest_raw),
                "base64": base64.b64encode(self.manifest_raw).decode("ascii")},
            "retirement": "PENDING_CHILD_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        self.ack_raw = wire({"schema": 1, "scope": D._CRYPTO_ACK_SCOPE, "invocation": start["invocation"],
            "terminalSha256": sha(self.child_raw), "clock": D.O.clock_value(self.clock.identity),
            "closedNs": self.clock.raw, "ownerCloseSha256": "a" * 64,
            "fileResourceCount": 1, "operativeResourceCount": 1})

    def paths(self, kind):
        if kind != self.kind:
            raise AssertionError("SUPPLIED_NATIVE_FIXED_KIND")
        return {"P": Path("/SUPPLIED/primary")}, Path("/SUPPLIED/primary-handoff"), self.custody

    def directory(self, path):
        identity, files = self.stores[path]
        return Directory(self, path, identity, files)

    def make_scope(self, job, invocation, state, home):
        self.make_calls.append((job, invocation, state, home))
        self.scope = Scope(self, job, invocation, state, home)
        self.allocations.append(("native-scope", self.scope))
        return self.scope

    def check(self):
        self.check_calls += 1
        self.check_hook()

    def run(self):
        return D._custody_crypto_native(self.owner, self.private, self.context, self.window, self.check)


class CryptoNativeTests(unittest.TestCase):
    def test_crypto_parent_uses_fixed_token_free_argv_and_original_210_45_caps(self):
        for kind in ("gate", "worker"):
            with self.subTest(launcher=kind), Native(kind) as rig:
                original_local = rig.owner.local_end
                original_window = rig.window._view().binding
                returned = rig.run()
                self.assertIs(type(returned), D._CryptoNativeReturn)
                self.assertIs(returned.context, rig.context)
                self.assertIs(returned.child, rig.child_raw)
                self.assertEqual(returned.phase, (rig.started, rig.work, rig.final))
                original, graph = D._CRYPTO_NATIVE_RETURNS[id(returned)]
                self.assertIs(original[0], returned)
                self.assertIs(original[1], rig.owner)
                self.assertIs(original[2], rig.window)
                self.assertIs(original[3], rig.owner.__dict__)
                self.assertIs(original[4], rig.owner._anchor())
                self.assertIs(original[5], rig.scope)
                self.assertIs(original[8], rig.child)
                self.assertIs(original[10], returned.records)
                self.assertIs(original[11], returned.child)
                self.assertIs(original[12], returned.phase)
                self.assertIs(original[13], returned.__dict__)
                self.assertTrue(graph)
                self.assertIs(rig.owner.phase_originals, returned)
                self.assertEqual(rig.owner.local_end, original_local)
                self.assertIs(rig.window._view().binding, original_window)
                self.assertFalse(rig.owner._anchor().phase_active)
                self.assertIsNone(rig.owner.work_limit)
                self.assertIsNone(rig.owner.final_limit)
                records = dict(returned.records)
                self.assertEqual(set(records), {"start.json", "baseline.json", "native-start.json",
                    "stdout.log", "stderr.log", "result.json"})
                start, row = (json.loads(records[name]) for name in ("start.json", "result.json"))
                self.assertEqual(start["scope"], D._CRYPTO_START_SCOPE)
                self.assertEqual(start["argv"], D._custody_crypto_command(sha(rig.context)))
                self.assertEqual(rig.argv, D._custody_crypto_command(sha(rig.context), rig.started))
                self.assertEqual(rig.argv[1:4], ["-I", "-B", "-S"])
                self.assertEqual((start["startedNs"], start["workEndNs"], start["finalEndNs"]), returned.phase)
                self.assertIsNone(start["exitCode"])
                self.assertFalse(start["launchAttempted"])
                self.assertFalse(start["scopeAttempted"])
                self.assertEqual(start["retirement"], "UNKNOWN")
                self.assertEqual(row["launchArgv"], rig.argv)
                self.assertEqual(row["exitCode"], 0)
                self.assertEqual(row["retirement"], "KNOWN")
                self.assertTrue(row["scopeCloseAttempted"] and row["scopeClosed"])
                self.assertEqual(row["survivors"], [])
                self.assertTrue(all(value is True for item in row["captureOutcomes"].values() for value in item.values()))
                self.assertEqual(rig.scope.spawn_calls, 1)
                self.assertEqual(rig.scope.close_calls, 1)
                self.assertTrue(rig.scope.closed)
                self.assertEqual(len(rig.make_calls), 1)
                self.assertEqual(rig.scope.drain_calls[0][2], original[9])
                self.assertLessEqual(original[9], original_local)
                self.assertLessEqual(original[9], rig.clock.local + (rig.final - rig.clock.raw) / NS)
                self.assertEqual((original[6].deadline, original[7].deadline), (original[9], original[9]))
                self.assertEqual((original[6].maximum, original[7].maximum),
                    (D.native.ACK_LIMIT, D.native.STDERR_LIMIT))
                self.assertTrue(original[6].closed and original[7].closed)
                self.assertEqual((original[6].close_calls, original[7].close_calls), (1, 1))
                self.assertTrue(all(name not in rig.environment for name in D._CREDENTIAL_NAMES))
                self.assertEqual(rig.environment["HOME"], str(rig.path / "control-home"))
                self.assertEqual(rig.environment["TMPDIR"], str(rig.path / "temporary"))
                self.assertEqual({name: rig.environment[name] for name in D.Q._CONTEXT}, start["inheritedContext"])
                domain = D.native.processes.ownership_domains(
                    rig.environment[D.native.processes.CHAIN_ENV], rig.environment[D.native.processes.DOMAINS_ENV])[-1]
                self.assertEqual(domain, {"id": start["invocation"], "job": start["job"],
                    "state": str(rig.path), "home": str(rig.path / "control-home")})
                # Native transport bytes alone have NOT authenticated a child
                # manifest. This positive stops at the actual modeled launch leaf.
                self.assertIsNone(rig.owner._anchor().failure)
                self.assertFalse(rig.owner.closed)
                rig.owner.freeze()
                rig.owner.close()
                rig.owner.known()
                self.assertEqual(rig.owner.local_end, original_local)

        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), Phase(kind) as rig:
                original = rig.owner.local_end
                binding = rig.window._view().binding
                rig.enter()
                self.assertEqual((rig.owner.work_limit, rig.owner.final_limit), (rig.work, rig.final))
                self.assertEqual(rig.owner._anchor().phase,
                    (rig.started, rig.work, rig.final, (None, None)))
                self.assertIs(rig.owner.first, rig.first)
                self.assertIs(rig.owner.fence, rig.window)
                rig.owner.leave_crypto_phase(rig.started, rig.work, rig.final)
                self.assertIsNone(rig.owner.work_limit)
                self.assertIsNone(rig.owner.final_limit)
                self.assertEqual(rig.owner.local_end, original)
                self.assertIs(rig.window._view().binding, binding)
                self.assertFalse(rig.owner._anchor().phase_active)
                rig.owner.freeze()
                rig.owner.close()
                rig.owner.known()
                self.assertEqual(rig.owner.local_end, original)
            with self.subTest(kind=kind, refused="second-phase"), Phase(kind) as rig:
                rig.enter()
                rig.owner.leave_crypto_phase(rig.started, rig.work, rig.final)
                with self.assertRaisesRegex(Exception, "CRYPTO_OWNER_ORIGINAL_PHASE"):
                    rig.enter()
            with self.subTest(kind=kind, refused="authority45-substitution"), Phase(kind) as rig:
                wrong_work = min(rig.window.work, rig.started + 45 * NS)
                with self.assertRaisesRegex(Exception, "CRYPTO_OWNER_ORIGINAL_PHASE"):
                    rig.owner.enter_crypto_phase(rig.context, rig.started, wrong_work,
                        min(rig.window.final, wrong_work + 45 * NS))
                self.assertIsNone(rig.owner._anchor().phase)

        for operation in ("_authority", "_crypto"):
            with self.subTest(route=operation), Entry(operation) as rig:
                command = (D.native.initial_custody_authority_command if operation == "_authority"
                    else D._custody_crypto_command)(rig.hash, rig.minimum)
                self.assertEqual(command[1:4], ["-I", "-B", "-S"])
                self.assertEqual(command[4:], rig.argv)
                self.assertEqual(rig.run(), 0)
                self.assertEqual([call[:3] for call in rig.calls], [(operation, rig.hash, rig.minimum)])
                self.assertTrue(callable(rig.calls[0][3]))
                self.assertEqual(rig.signal.handlers, rig.signal.original)
                self.assertEqual(rig.fence.calls, [(True, 1200 * NS), (True, 1200 * NS)])
                emitted = json.loads(rig.sink.getvalue())
                if operation == "_crypto":
                    self.assertEqual(emitted["closedNs"], rig.leaf_closed)
                    self.assertNotEqual(emitted["scope"], D.native.INITIAL_CUSTODY_AUTHORITY_ACK_SCOPE)
                else:
                    self.assertEqual(emitted["closedNs"], rig.fence.raw)
            with self.subTest(route=operation, refused="cancelled-list"), Entry(operation) as rig:
                rig.callback = rig.signal.cancel
                self.assertNotEqual(rig.run(), 0)
                self.assertEqual(len(rig.calls), 1)
                self.assertEqual(rig.sink.getvalue(), b"")
                self.assertEqual(rig.signal.handlers, rig.signal.original)
            with self.subTest(route=operation, refused="late-flush-expiry"), Entry(operation) as rig:
                rig.sink.on_flush = lambda: setattr(rig.fence, "raw", 1200 * NS)
                self.assertNotEqual(rig.run(), 0)
                self.assertTrue(rig.sink.getvalue())  # Emitted bytes are still provisional.
                self.assertEqual(len(rig.fence.calls), 2)
            with self.subTest(route=operation, refused="post-flush-cancellation"), Entry(operation) as rig:
                rig.sink.on_flush = rig.signal.pending_cancel
                self.assertNotEqual(rig.run(), 0)
                self.assertTrue(rig.sink.getvalue())

        for label, change in (
                ("hash-uppercase", lambda r: r.argv.__setitem__(3, "B" * 64)),
                ("hash-short", lambda r: r.argv.__setitem__(3, "b" * 63)),
                ("hash-extra", lambda r: r.argv.__setitem__(3, "b" * 65)),
                ("minimum-negative", lambda r: r.argv.__setitem__(5, "-1")),
                ("minimum-sign", lambda r: r.argv.__setitem__(5, "+1")),
                ("minimum-leading-zero", lambda r: r.argv.__setitem__(5, "01")),
                ("minimum-float", lambda r: r.argv.__setitem__(5, "1.0")),
                ("minimum-overflow", lambda r: r.argv.__setitem__(5, str(1 << 64))),
                ("outward-custody", lambda r: r.argv.__setitem__(1, "custody")),
                ("outward-seal", lambda r: r.argv.__setitem__(1, "seal")),
                ("outward-upload", lambda r: r.argv.__setitem__(1, "upload")),
                ("unknown-route", lambda r: r.argv.__setitem__(1, "_service")),
                ("extra-path", lambda r: r.argv.extend(("--path", "/SUPPLIED/foreign"))),
                ("not-isolated", lambda r: setattr(r.flags, "isolated", 0)),
                ("site-enabled", lambda r: setattr(r.flags, "no_site", 0)),
                ("bytecode-enabled", lambda r: setattr(r.dispatch_sys, "dont_write_bytecode", False))):
            with self.subTest(refused=label), Entry("_crypto") as rig:
                change(rig)
                self.assertNotEqual(rig.run(), 0)
                self.assertEqual(rig.calls, [])
                self.assertEqual(rig.sink.getvalue(), b"")

    def test_crypto_parent_retains_returned_allocations_before_late_failure(self):
        for label in ("stdout.log", "stderr.log", "native-scope"):
            for unknown in (False, True):
                with self.subTest(returned=label, unknown_close=unknown), Native() as rig:
                    first = FalseyFailure("SUPPLIED_POST_REGISTRATION_FALSEY_FAILURE")
                    later = RuntimeError("SUPPLIED_ACTUAL_RESOURCE_CLOSE_FAILURE")
                    fired, retained = [], []
                    original_local = rig.owner.local_end
                    def after_allocation():
                        if fired or not rig.allocations or rig.allocations[-1][0] != label:
                            return
                        resource = rig.allocations[-1][1]
                        rows = [item for item in rig.owner._anchor().rows if item[2] is resource]
                        if not rows:
                            return
                        # Failure is after the actual supplier returned AND the
                        # source owner registered the exact row, not in a factory.
                        fired.append(True)
                        retained.append((resource, rows[0][0]))
                        if unknown:
                            if label == "native-scope":
                                rig.scope_close_error = later
                            else:
                                resource.close_error = later
                        raise first
                    rig.clock.hook = after_allocation
                    with self.assertRaises(FalseyFailure) as caught:
                        rig.run()
                    self.assertIs(caught.exception, first)
                    self.assertIs(rig.owner._anchor().failure, first)
                    self.assertIs(rig.window._anchor().failure, first)
                    self.assertEqual(fired, [True])
                    self.assertEqual(len([item for item in rig.allocations if item[0] == label]), 1)
                    resource, row = retained[0]
                    saved = next(item for item in rig.owner._anchor().rows if item[2] is resource)
                    self.assertIs(saved[0], row)
                    self.assertIs(row["owner"], resource)
                    self.assertIs(saved[2], resource)
                    self.assertTrue(saved[3])
                    self.assertIs(saved[4], not unknown)
                    self.assertEqual(resource.close_calls, 1)
                    self.assertIsNone(rig.owner._anchor().pending)
                    self.assertIsNone(rig.child)
                    self.assertIsNone(rig.owner.phase_originals)
                    self.assertEqual(D._CRYPTO_NATIVE_RETURNS, {})
                    self.assertEqual(rig.owner.local_end, original_local)
                    self.assertFalse(any(name in rig.stores[rig.path / "crypto-service"][1]
                        for name in ("native-start.json", "result.json")))
                    if rig.scope is not None:
                        self.assertEqual(rig.scope.spawn_calls, 0)
                        self.assertEqual(len(rig.scope.drain_calls), 1)
                        self.assertLessEqual(rig.scope.drain_calls[0][2], original_local)
                    if unknown:
                        self.assertTrue(rig.owner._anchor().unknown)
                        self.assertTrue(any(owner is rig.owner for owner in D.native.QUARANTINE))
                        with self.assertRaises(FalseyFailure) as closed:
                            rig.owner.close()
                        self.assertIs(closed.exception, first)
                    else:
                        self.assertFalse(rig.owner._anchor().unknown)
                        rig.owner.close()
                        self.assertTrue(all(a and c for _r, _l, _v, a, c in rig.owner._anchor().rows))
                    self.assertEqual(resource.close_calls, 1)  # No repaired or retried close.

    def test_crypto_parent_refuses_child_ack_files_without_actual_native_success(self):
        for kind in ("gate", "worker"):
            with self.subTest(authenticated_transport=kind), Native(kind) as rig:
                rig.valid_child_bytes = True
                returned = rig.run()
                start, row, child, ack, manifest = D._checked_crypto_native(returned, rig.owner, rig.window)
                self.assertEqual(manifest, rig.manifest_raw)
                self.assertEqual(ack["terminalSha256"], sha(returned.child))
                self.assertEqual(child["contextSha256"], sha(rig.context))
                self.assertEqual(row["launchMinimumNs"], rig.started)
                self.assertEqual(start["workEndNs"], rig.work)
                self.assertFalse(rig.owner.closed)  # This is not the outer parent-close/READ grant.
                rig.owner.freeze()
                rig.owner.close()
                rig.owner.known()
                self.assertEqual(D._checked_crypto_native(returned, rig.owner, rig.window)[4], manifest)

        for label in ("nonzero-child", "boolean-exit", "descendant", "changed-preparer", "survivor",
                "scope-close", "stdout-close", "stdout-sync", "stdout-read", "stderr-bytes", "discovery-error"):
            with self.subTest(native_refused=label), Native() as rig:
                rig.valid_child_bytes = True
                supplied = RuntimeError("SUPPLIED_NATIVE_FAILURE_" + label)
                if label == "nonzero-child":
                    rig.exit_code = 7
                elif label == "boolean-exit":
                    rig.exit_code = False
                elif label == "descendant":
                    rig.descendants = [{"pid": 9002, "startTicks": 5001}]
                elif label == "changed-preparer":
                    rig.preparer_changes = True
                elif label == "survivor":
                    rig.survivors = [{"pid": 9001, "startTicks": 5000}]
                elif label == "scope-close":
                    rig.scope_close_error = supplied
                elif label in ("stdout-close", "stdout-sync"):
                    def fail_capture():
                        out = next(value for name, value in rig.allocations if name == "stdout.log")
                        setattr(out, "close_error" if label == "stdout-close" else "sync_error", supplied)
                    rig.spawn_hook = fail_capture
                elif label == "stdout-read":
                    def fail_read(name):
                        if name == "stdout.log":
                            raise supplied
                    rig.read_hook = fail_read
                elif label == "stderr-bytes":
                    rig.stderr_raw = b"SUPPLIED_NONEMPTY_STDERR"
                else:
                    rig.discovery_errors = ["SUPPLIED_DISCOVERY_IDENTITY_FAILURE"]
                with self.assertRaises(Exception) as caught:
                    rig.run()
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                self.assertEqual(rig.scope.spawn_calls, 1)
                self.assertIsNone(rig.owner.phase_originals)
                self.assertEqual(D._CRYPTO_NATIVE_RETURNS, {})
                # Even byte-consistent-looking capture/child files cannot mint
                # the private actual-return registry after native failure.
                clone = D._CryptoNativeReturn(rig.context, (), rig.child_raw, (rig.started, rig.work, rig.final))
                with self.assertRaisesRegex(Exception, "CRYPTO_NOT_ORIGINAL_NATIVE_RETURN"):
                    D._checked_crypto_native(clone, rig.owner, rig.window)

        for label in ("opaque-ack", "wrong-ack-scope", "wrong-ack-digest", "manifest-encoding", "late-child-close"):
            with self.subTest(child_bytes_refused=label), Native() as rig:
                rig.valid_child_bytes = label != "opaque-ack"
                def corrupt_transport():
                    if label == "opaque-ack":
                        return
                    out = next(value for name, value in rig.allocations if name == "stdout.log")
                    ack, child = json.loads(out.raw), json.loads(rig.child_raw)
                    if label == "wrong-ack-scope":
                        ack["scope"] = D.native.INITIAL_CUSTODY_AUTHORITY_ACK_SCOPE
                    elif label == "wrong-ack-digest":
                        ack["terminalSha256"] = "0" * 64
                    elif label == "late-child-close":
                        ack["closedNs"] = rig.work
                    else:
                        child["manifest"]["base64"] = "!not-base64!"
                        rig.child_raw = wire(child)
                        rig.private.files["crypto-child-result.json"] = rig.child_raw
                        ack["terminalSha256"] = sha(rig.child_raw)
                    out.raw = wire(ack)
                rig.spawn_hook = corrupt_transport
                returned = rig.run()  # Actual supplied native success is necessary, not sufficient.
                self.assertIn(id(returned), D._CRYPTO_NATIVE_RETURNS)
                with self.assertRaises(Exception) as caught:
                    D._checked_crypto_native(returned, rig.owner, rig.window)
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                rig.owner.freeze()
                rig.owner.close()

        for label in ("equal-object", "equal-record-tuple", "equal-object-dictionary", "changed-resource-row"):
            with self.subTest(return_refused=label), Native() as rig:
                rig.valid_child_bytes = True
                returned = rig.run()
                if label == "equal-object":
                    candidate = D._CryptoNativeReturn(returned.context, returned.records, returned.child, returned.phase)
                else:
                    candidate = returned
                    if label == "equal-record-tuple":
                        object.__setattr__(returned, "records", tuple(list(returned.records)))
                    elif label == "equal-object-dictionary":
                        object.__setattr__(returned, "__dict__", dict(returned.__dict__))
                    else:
                        actual = next(row for row in rig.owner.resources if row["label"] == "stdout")
                        actual["closed"] = False
                with self.assertRaises(Exception) as caught:
                    D._checked_crypto_native(candidate, rig.owner, rig.window)
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))

    def test_crypto_parent_failed_work_cleanup_uses_only_original_capture_ceiling(self):
        for kind in ("gate", "worker"):
            for failure_kind in ("original-work-expired", "falsey-primary", "falsey-and-drain", "falsey-and-close"):
                with self.subTest(kind=kind, failure=failure_kind), Native(kind) as rig:
                    primary = FalseyFailure("SUPPLIED_POLL_FALSEY_PRIMARY")
                    secondary = RuntimeError("SUPPLIED_SECONDARY_NATIVE_RETIREMENT_FAILURE")
                    original_local = rig.owner.local_end
                    original_binding = rig.window._view().binding
                    def poll_failure():
                        if failure_kind == "original-work-expired":
                            rig.clock.raw = rig.work
                            # The independent original LOCAL cleanup ceiling is
                            # still live; do not renew it from the failed RAW.
                        else:
                            if failure_kind == "falsey-and-drain":
                                rig.drain_error = secondary
                            elif failure_kind == "falsey-and-close":
                                rig.scope_close_error = secondary
                            raise primary
                    rig.poll_hook = poll_failure
                    with self.assertRaises(Exception) as caught:
                        rig.run()
                    self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                    self.assertIs(rig.owner._anchor().failure, caught.exception)
                    if failure_kind == "original-work-expired":
                        self.assertIn("WINDOW_RAW_EXPIRED", str(caught.exception))
                        self.assertIs(rig.window._anchor().failure, caught.exception)
                        self.assertEqual(rig.window._anchor().last, rig.work)
                    else:
                        self.assertIs(caught.exception, primary)
                    self.assertEqual(rig.owner.local_end, original_local)
                    self.assertIs(rig.window._view().binding, original_binding)
                    out = next(resource for label, resource in rig.allocations if label == "stdout.log")
                    self.assertEqual(len(rig.scope.drain_calls), 1)
                    grace, kill_wait, deadline = rig.scope.drain_calls[0]
                    self.assertEqual(deadline, out.deadline)
                    self.assertLessEqual(deadline, original_local)
                    self.assertLessEqual(grace + kill_wait, max(0, deadline - rig.clock.local))
                    self.assertLessEqual(grace, 5)
                    self.assertLessEqual(kill_wait, 5)
                    self.assertEqual(rig.scope.spawn_calls, 1)
                    self.assertEqual(rig.child.poll_calls, 1)
                    self.assertTrue(rig.owner._anchor().unknown)  # A launched child failed to return success.
                    self.assertIsNone(rig.owner.phase_originals)
                    self.assertEqual(D._CRYPTO_NATIVE_RETURNS, {})
                    self.assertNotIn("result.json", rig.stores[rig.path / "crypto-service"][1])
                    # No false final/native success or newly invented birth.
                    self.assertEqual(len([name for name, _ in rig.allocations if name == "native-start.json"]), 1)
                    self.assertEqual(rig.scope.close_calls, 0 if failure_kind == "falsey-and-drain" else 1)
                    before = rig.scope.close_calls
                    with self.assertRaises(Exception) as closed:
                        rig.owner.close()
                    self.assertIs(closed.exception, caught.exception)
                    self.assertEqual(rig.scope.close_calls, before)


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
