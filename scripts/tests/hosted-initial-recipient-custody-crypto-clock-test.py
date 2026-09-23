#!/usr/bin/env python3
"""NEW custody crypto binding controls; authored, not executed evidence.

The maintained child guard, immutable cap constructor, exact metadata/native
owners and registry checks are real source. RAW/LOCAL/boot/host launch inputs
are explicit supplied observations, never recovered provider identity. Counter
resources model metadata closure; no native process or old owner is restored.
Only the new bind_crypto/attachment seam is exercised, not the accepted clock
suite. No accepted test module is imported or discovered. No execution grant,
native fit, trusted recipient, Step success or delivery is established here.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes  # Finish stdlib initialization before rejecting native loads.
import hashlib
import importlib.util
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
        raise RuntimeError("OFFLINE_CRYPTO_CLOCK_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("new_custody_crypto_clock_controls",
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


class Resource:
    """Supplied counter-only metadata resource, not a native handle."""
    def __init__(self):
        self.closed, self.calls, self.error = False, 0, None

    def close(self):
        self.calls += 1
        if self.error is not None:
            raise self.error
        if self.closed:
            raise AssertionError("SUPPLIED_METADATA_DOUBLE_CLOSE")
        self.closed = True


class Clock:
    def __init__(self, role="linux-x64"):
        self.identity = D.O.clocks.ClockIdentity(role, D.O.clocks.DOMAINS[role], NS)
        self.raw, self.local, self.boot = 1100 * NS, 100.0, BOOT
        self.hook, self.reads, self.cancel_calls = lambda: None, [], 0

    def reading(self):
        return D.O.clocks.Reading(self.identity, self.raw)

    def checked(self, expected, *, minimum_ns=0):
        if expected is not self.identity or self.raw < minimum_ns:
            raise AssertionError("SUPPLIED_CRYPTO_CLOCK_FRONTIER")
        self.reads.append((expected, minimum_ns, self.raw))
        return self.raw

    def advance(self, seconds):
        self.raw, self.local = 1100 * NS + seconds * NS, 100.0 + seconds

    def cancelled(self):
        self.cancel_calls += 1
        self.hook()


class Harness:
    """Fresh actual source registries with explicitly supplied clock inputs."""
    def __init__(self, kind="gate"):
        self.kind, self.clock, self.stack = kind, Clock(), ExitStack()
        self.metadata = self.operative = None

    def __enter__(self):
        try:
            self.stack.enter_context(patch.dict(D.os.environ, {}, clear=True))
            self.stack.enter_context(patch.object(D.time, "monotonic", lambda: self.clock.local))
            self.stack.enter_context(patch.object(D.O.clocks, "checked_now", self.clock.checked))
            self.stack.enter_context(patch.object(D.C, "boot_digest", lambda _role: self.clock.boot))
            for name in ("_WINDOWS", "_CUSTODY_CHILD_CLOCKS", "_CUSTODY_OWNERS", "_PRIMARY_OWNERS"):
                self.stack.enter_context(patch.object(D, name, {}))
            self.stack.enter_context(patch.object(D, "_PRIMARY_QUARANTINE", []))
            self.stack.enter_context(patch.object(D.native, "QUARANTINE", []))
            self.parent_first = self.clock.reading()
            self.parent = D.Window(self.parent_first, self.clock.local, BOOT,
                D.schedule(self.kind, 1000 * NS, self.clock.raw), self.clock.cancelled)
            self.clock.advance(10)
            self.started = self.clock.raw
            self.clock.advance(11)
            self.first, self.first_local = self.clock.reading(), self.clock.local
            self.guard = D._CustodyChildClock(self.first, self.first_local, BOOT, self.clock.cancelled)
            raw_owner = D.native.Owner(self.guard.deadline(45), self.guard,
                first=self.first, cancelled=self.clock.cancelled)
            self.metadata = D._PrimaryOwner(raw_owner)
            self.guard.attach_metadata(self.metadata)
            self.resource = self.metadata.acquire("directory", Resource)
            self.frame()
            return self
        except BaseException:
            self.stack.close()
            raise

    def __exit__(self, *args):
        # No retry of UNKNOWN resources or repair of altered ledgers. The
        # counter resource has no device handle; its original refusal remains.
        return self.stack.__exit__(*args)

    def close_metadata(self):
        self.clock.advance(12)
        self.close_raw = self.metadata.finish()
        return self.close_raw

    def bind(self):
        return self.guard.bind_crypto(self.context_raw, self.context, self.start_raw,
            self.start, self.expected, self.event, self.inherited)

    def recode(self):
        self.context_raw = wire(self.context)
        self.start["contextSha256"] = sha(self.context_raw)
        self.start["argv"] = D._custody_crypto_command(sha(self.context_raw))
        self.start_raw = wire(self.start)

    def frame(self):
        self.event = wire({"scope": "SUPPLIED_CRYPTO_CLOCK_EVENT_NOT_HOSTED_EXECUTION"})
        self.observed = {"kind": self.kind, "role": self.clock.identity.role, "firstUseAt": 12345,
            "source": {"commit": "1" * 40, "tree": "2" * 40}}
        self.roots = {"P": Path("/SUPPLIED/primary")}
        self.custody = Path("/SUPPLIED/primary-custody")
        self.stack.enter_context(patch.object(D, "_paths", self.paths))
        self.stack.enter_context(patch.object(D.N, "host_context", self.host_context))
        match_type = D.A.gate.GateEligibility if self.kind == "gate" else D.A.stages.BootstrapMatch
        self.expected = match_type(wire({"scope": "SUPPLIED_TYPED_MATCH_BOUNDARY", "firstUseAt": 12345,
            "source": self.observed["source"]}))
        hashes = {name: sha(("SUPPLIED:" + name).encode("ascii")) for name in D._CRYPTO_INPUT_LIMITS}
        hashes["original-match.json"] = hashes["fresh-match.json"] = sha(self.expected.record)
        hashes["event.json"] = sha(self.event)
        self.context = {"schema": 1, "scope": D._CRYPTO_CONTEXT_SCOPE, "kind": self.kind,
            "root": str(ROOT), "session": str(self.custody / "returned"), "job": "b" * 32,
            "observed": self.observed, "window": json.loads(D._custody_authority_window(self.parent)),
            "primary": {"step": "initial-originals" if self.kind == "gate" else "canonical-initialization",
                "outcome": "success", "resultSha256": "3" * 64, "handoffSha256": "4" * 64,
                "inventorySha256": "5" * 64},
            "authority": {"returnSha256": hashes["authority-return.json"],
                "matchSha256": hashes["fresh-match.json"], "copySha256": hashes["authority-map.json"]},
            "filesSha256": hashes, "directories": {name: ([17, 100 + number] if name != "export-output" else None)
                for number, name in enumerate(D._CRYPTO_DIRECTORIES)},
            "inheritedContext": {}, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        path, invocation = self.custody / "returned", "c" * 32
        environment = D.native.processes.ownership_environment({}, self.context["job"], invocation,
            str(path), str(path / "control-home"), allow_new_context=True)
        self.inherited = {name: environment[name] for name in D.Q._CONTEXT}
        work = min(self.parent.work, self.started + 210 * NS)
        self.start = {"schema": 1, "scope": D._CRYPTO_START_SCOPE, "contextSha256": "0" * 64,
            "argv": [], "cwd": str(ROOT), "role": self.clock.identity.role, "job": self.context["job"],
            "invocation": invocation, "state": str(path), "home": str(path / "control-home"),
            "inheritedContext": dict(self.inherited), "startedNs": self.started, "workEndNs": work,
            "finalEndNs": min(self.parent.final, work + 45 * NS), "exitCode": None,
            "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"}
        self.recode()

    def paths(self, kind):
        if kind != self.kind:
            raise AssertionError("SUPPLIED_CRYPTO_CLOCK_KIND")
        return self.roots, Path("/SUPPLIED/primary-handoff"), self.custody

    def host_context(self, first_use):
        if first_use != 12345:
            raise AssertionError("SUPPLIED_CRYPTO_CLOCK_FIRST_USE")
        return self.observed, self.roots["P"], self.event


class CryptoClockTests(unittest.TestCase):
    def test_crypto_bind_uses_original_first_local_frontier_and_parent_work(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), Harness(kind) as rig:
                metadata_cap = rig.guard._anchor().cap
                rig.close_metadata()
                before = rig.guard.last
                with patch.object(D.native._RecipientWindow, "now",
                        side_effect=AssertionError("UNCHANGED_CAP_OBSERVER_MUST_NOT_RUN")), \
                        patch.object(D.native._RecipientWindow, "deadline",
                        side_effect=AssertionError("UNCHANGED_CAP_DEADLINE_MUST_NOT_RUN")):
                    rig.bind()
                anchor = rig.guard._anchor()
                expected_end = min(rig.first.nanoseconds + 210 * NS, rig.start["workEndNs"])
                self.assertEqual((rig.guard.work, rig.guard.final), (expected_end, expected_end))
                self.assertEqual(anchor.phase, "OPERATIVE")
                self.assertIs(anchor.binding[0], rig.first)
                self.assertEqual(anchor.binding[1], rig.first_local)
                self.assertEqual(anchor.binding[2], BOOT)
                self.assertIs(anchor.frame[-3], metadata_cap)
                self.assertIs(anchor.metadata, rig.metadata)
                self.assertTrue(rig.metadata.finished)
                self.assertTrue(rig.metadata.owner.closed)
                self.assertTrue(all(attempted and closed for _, _, _, attempted, closed in rig.metadata.rows))
                self.assertEqual(rig.resource.calls, 1)
                self.assertGreaterEqual(rig.guard.last, before)
                self.assertEqual(rig.guard.last, rig.clock.raw)
                self.assertLessEqual(rig.guard.local_end, rig.first_local + 210)
                self.assertLessEqual(rig.guard.local_end,
                    rig.first_local + (expected_end - rig.first.nanoseconds) / NS)
                self.assertLess(rig.guard.local_end, rig.clock.local + 210)
                operative = D._CustodyOwner(rig.guard.local_end, rig.guard,
                    first=rig.first, cancelled=rig.clock.cancelled)
                rig.guard.attach_operative(operative)
                self.assertIs(anchor.operative, operative)
                self.assertIs(operative.fence, rig.guard)
                self.assertIs(operative.first, rig.first)
                rig.guard.now()
                operative.freeze()
                operative.close()
                operative.known()

    def test_crypto_binding_rejects_authority_scope_bad_start_and_second_transition(self):
        mutations = (
            ("context-scope", lambda r: r.context.__setitem__("scope", D.native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE)),
            ("context-extra-field", lambda r: r.context.__setitem__("renewal", 210)),
            ("context-boot", lambda r: r.context["window"].__setitem__("originalBootDigest", "f" * 64)),
            ("context-primary-not-success", lambda r: r.context["primary"].__setitem__("outcome", "failure")),
            ("context-directory-alias", lambda r: r.context["directories"].__setitem__(
                "temporary", list(r.context["directories"]["control-home"]))),
            ("context-output-not-absent", lambda r: r.context["directories"].__setitem__("export-output", [17, 199])),
            ("start-authority-scope", lambda r: r.start.__setitem__("scope", D.native.PHASE_SCOPE)),
            ("start-authority45", lambda r: r.start.__setitem__("workEndNs", r.started + 45 * NS)),
            ("start-final-widened", lambda r: r.start.__setitem__("finalEndNs", r.start["finalEndNs"] + 1)),
            ("start-child-before-parent", lambda r: r.start.__setitem__("startedNs", r.first.nanoseconds + 1)),
            ("start-job", lambda r: r.start.__setitem__("job", "d" * 32)),
            ("start-role", lambda r: r.start.__setitem__("role", "windows-x64")),
            ("start-arbitrary-command", lambda r: r.start["argv"].__setitem__(5, "help")),
            ("start-transported-minimum", lambda r: r.start.__setitem__("launchMinimumNs", r.first.nanoseconds)),
            ("start-domain", lambda r: r.start["inheritedContext"].__setitem__(next(iter(r.inherited)), "SUBSTITUTED")),
            ("actual-domain", lambda r: r.inherited.__setitem__(next(iter(r.inherited)), "SUBSTITUTED")),
            ("expected-type", lambda r: setattr(r, "expected", SimpleNamespace(record=r.expected.record))),
        )
        for label, change in mutations:
            with self.subTest(refused=label), Harness() as rig:
                rig.close_metadata()
                change(rig)
                if label.startswith("context-"):
                    rig.recode()
                else:
                    rig.start_raw = wire(rig.start)
                with self.assertRaises(Exception) as caught:
                    rig.bind()
                self.assertNotIsInstance(caught.exception, (AttributeError, NameError, TypeError))
                anchor = rig.guard._anchor()
                self.assertIs(anchor.failure, caught.exception)
                self.assertNotEqual(anchor.phase, "OPERATIVE")
                self.assertIsNone(anchor.operative)
                for binder in (rig.guard.bind_crypto, rig.guard.bind):
                    with self.assertRaises(Exception) as replay:
                        binder(rig.context_raw, rig.context, rig.start_raw, rig.start,
                            rig.expected, rig.event, rig.inherited)
                    self.assertIs(replay.exception, caught.exception)
        with Harness() as rig:
            rig.close_metadata()
            rig.bind()
            with self.assertRaisesRegex(Exception, "CHILD_CLOCK_BIND_ONCE") as second:
                rig.bind()
            with self.assertRaises(Exception) as other:
                rig.guard.bind(None, None, None, None, None, None, None)
            self.assertIs(other.exception, second.exception)
        with Harness() as rig:
            # Supplied already-validated authority CLOCK frame only. This one
            # setup bind establishes the opposite prior phase; it is not an
            # authority caller/HTTP execution or an accepted-suite replay.
            rig.close_metadata()
            context = json.loads(rig.context_raw)
            context["expectedMatch"] = json.loads(rig.expected.record)
            start = json.loads(rig.start_raw)
            start["workEndNs"] = min(rig.parent.work, rig.started + 45 * NS)
            start["finalEndNs"] = min(rig.parent.final, start["workEndNs"] + 45 * NS)
            rig.guard.bind(wire(context), context, wire(start), start, rig.expected, rig.event, rig.inherited)
            with self.assertRaisesRegex(Exception, "CHILD_CLOCK_BIND_ONCE"):
                rig.bind()

    def test_crypto_bind_refuses_open_failed_unknown_or_replaced_metadata(self):
        for failure_kind in ("open", "failed-close", "unknown", "equal-owner-dictionary"):
            with self.subTest(metadata=failure_kind), Harness() as rig:
                original_owner = rig.metadata.owner
                original_dictionary = original_owner.__dict__
                original_first = rig.first
                falsey = FalseyFailure("SUPPLIED_METADATA_FALSEY_CLOSE_FAILURE")
                if failure_kind == "failed-close":
                    rig.resource.error = falsey
                    with self.assertRaises(FalseyFailure) as closed:
                        rig.close_metadata()
                    self.assertIs(closed.exception, falsey)
                    self.assertIs(rig.metadata.failure, falsey)
                    self.assertIs(original_owner.original, falsey)
                elif failure_kind != "open":
                    rig.close_metadata()
                    if failure_kind == "unknown":
                        original_owner.unknown = True  # Explicit malformed closed-owner negative.
                    else:
                        original_owner.__dict__ = dict(original_dictionary)
                with self.assertRaisesRegex(Exception,
                        "CHILD_METADATA_CLOSE_UNKNOWN|COPY_ORIGINAL_OWNER_BINDING") as caught:
                    # The actual metadata refusal must precede even reading these
                    # invalid frame inputs. No validator stub turns them positive.
                    rig.guard.bind_crypto(None, None, None, None, None, None, None)
                failure = rig.guard._anchor().failure
                self.assertIs(caught.exception, failure)
                self.assertIsNone(rig.guard._anchor().operative)
                self.assertNotEqual(rig.guard._anchor().phase, "OPERATIVE")
                self.assertIs(rig.guard._anchor().binding[0], original_first)
                self.assertEqual(D._CUSTODY_OWNERS, {})
                for binder in (rig.guard.bind_crypto, rig.guard.bind):
                    with self.assertRaises(Exception) as replay:
                        binder(None, None, None, None, None, None, None)
                    self.assertIs(replay.exception, failure)
                if failure_kind == "failed-close":
                    self.assertIs(rig.metadata.failure, falsey)
                    self.assertIs(original_owner.original, falsey)
                    self.assertEqual(rig.resource.calls, 1)
                if failure_kind == "equal-owner-dictionary":
                    self.assertIsNot(original_owner.__dict__, original_dictionary)

    def test_crypto_binding_callbacks_cannot_replace_frame_caps_or_frontier(self):
        with Harness() as rig:
            rig.close_metadata()
            original_domain = D.native.processes.ownership_environment
            fired = []
            def change_frame_during_original_domain(*args, **kwargs):
                result = original_domain(*args, **kwargs)
                if not fired:
                    fired.append(rig.start["workEndNs"])
                    # The fixed formula was already checked at this boundary.
                    # Do not permit its same-dict mutation to become a new cap.
                    rig.start["workEndNs"] = rig.first.nanoseconds + 210 * NS
                return result
            with patch.object(D.native.processes, "ownership_environment", change_frame_during_original_domain):
                with self.assertRaises(Exception) as caught:
                    rig.bind()
            self.assertEqual(fired, [rig.parent.work])
            self.assertIs(rig.guard._anchor().failure, caught.exception)
            self.assertIsNone(rig.guard._anchor().operative)
            self.assertNotEqual(rig.guard._anchor().phase, "OPERATIVE")
            with self.assertRaises(Exception) as replay:
                rig.bind()
            self.assertIs(replay.exception, caught.exception)

        for label, change in (
                ("equal-context-window", lambda r, a: r.context.__setitem__("window", dict(r.context["window"]))),
                ("operative-cap", lambda r, a: a.cap.__dict__.__setitem__("work", a.cap.work + 1)),
                ("retained-metadata-cap", lambda r, a: a.frame[-3].__dict__.__setitem__("last", 0)),
                ("clock-frontier", lambda r, a: setattr(a, "last", a.last - 1)),
                ("original-binding", lambda r, a: setattr(r.guard, "_binding", tuple(list(a.binding))))):
            with self.subTest(callback=label), Harness() as rig:
                rig.close_metadata()
                before = rig.guard.last
                fired = []
                def mutate():
                    anchor = rig.guard._anchor()
                    if anchor.phase == "OPERATIVE" and not fired:
                        fired.append(anchor.last)
                        change(rig, anchor)
                rig.clock.hook = mutate
                with self.assertRaises(Exception) as caught:
                    rig.bind()
                self.assertEqual(len(fired), 1)
                self.assertGreaterEqual(fired[0], before)
                self.assertIs(rig.guard._anchor().failure, caught.exception)
                self.assertIsNone(rig.guard._anchor().operative)
                with self.assertRaises(Exception) as replay:
                    rig.bind()
                self.assertIs(replay.exception, caught.exception)
        for label in ("foreign-first", "foreign-fence", "changed-owner-dictionary"):
            with self.subTest(attachment=label), Harness() as rig:
                rig.close_metadata()
                rig.bind()
                operative = D._CustodyOwner(rig.guard.local_end, rig.guard,
                    first=rig.first, cancelled=rig.clock.cancelled)
                if label == "foreign-first":
                    operative.first = D.O.clocks.Reading(rig.first.clock, rig.first.nanoseconds)
                elif label == "foreign-fence":
                    operative.fence = rig.parent
                else:
                    operative.__dict__ = dict(operative.__dict__)
                with self.assertRaises(Exception) as caught:
                    rig.guard.attach_operative(operative)
                self.assertIsNone(rig.guard._anchor().operative)
                self.assertIs(rig.guard._anchor().failure, caught.exception)
                with self.assertRaises(Exception) as replay:
                    rig.guard.attach_operative(operative)
                self.assertIs(replay.exception, caught.exception)


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
