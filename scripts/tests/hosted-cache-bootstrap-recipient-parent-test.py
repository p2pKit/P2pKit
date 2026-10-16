#!/usr/bin/env python3
"""Recipient PARENT offline controls, not native/GPG/hosted qualification.

Tiny ordinary-UID POSIX originals and capture descriptors are real. Native
processes, Git/host/service suppliers and clocks are explicit models. The
accepted child and guard execute in-process under that modeled environment;
no native child, GPG, network, build, download or provider action can run.
Existing fixture builders are reused, never their historical test methods.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import copy
from dataclasses import FrozenInstanceError, replace
import importlib.util
import inspect
import os
from pathlib import Path
import signal
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bootstrap_recipient_parent_readmission_models",
    Path(__file__).with_name("hosted-cache-bootstrap-readmission-test.py"))
R = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = R
spec.loader.exec_module(R)
S, O, F = R.S, R.O, R.C.E.H.M

# Valid packet/armor FRAMING only, emphatically not a usable cryptographic key.
# The validator is modeled; real packet framing/readback still runs in parent.
PACKET = b"\xc6\x01x"
ARMOR = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nxgF4\n-----END PGP PUBLIC KEY BLOCK-----\n"


class StopProbe(OSError):
    pass


class FalseyFailure(OSError):
    def __bool__(self):
        return False


class ParentModels(R.ReadmissionModels):
    def setUp(self):
        with patch.object(F.M, "KEY", ARMOR):
            super().setUp()
        self.stack.enter_context(patch.object(S, "_RECIPIENT_ATTEMPTS", {}))
        self.stack.enter_context(patch.object(S.query, "QUARANTINE", []))
        self.stack.enter_context(patch.object(S.diagnostics, "_QUARANTINE", []))
        for module, name in ((S.posix, "_gpg"), (S.diagnostics, "_gpg"), (S.diagnostics, "validate_recipient")):
            self.stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_REAL_GPG")))
        self.stack.enter_context(patch.object(S.posix, "validate_recipient", side_effect=self.validate_recipient))
        self.parent_scopes, self.parent_events, self.parent_child_errors, self.validations = [], [], [], []
        self.parent_before_child = self.parent_after_child = self.parent_after_drain = lambda: None
        self.parent_scope_created = self.parent_scope_close = self.parent_before_poll = lambda: None
        self.parent_birth = self.parent_terminal = lambda value: None
        self.parent_ack = lambda raw: raw
        self.parent_exit, self.parent_survivors, self.parent_descendants = None, [], []
        self.parent_validator_error = None
        self.parent_baseline = set()

    def reset_models(self):
        # Test teardown ONLY: these scopes never owned a process. Close leftover
        # tiny real files through independent pins after assertions, not as a
        # production recovery or qualification of an UNKNOWN outcome.
        seen = set()
        for row in S._RECIPIENT_ATTEMPTS.values():
            bound = row[3]
            if bound is not None:
                for pin in reversed(bound.seen):
                    resource = pin.resource
                    if pin.label != "native-scope" and id(resource) not in seen:
                        seen.add(id(resource))
                        resource.close()
        S.QUARANTINE.clear()

    @staticmethod
    def put(path, raw):
        path.write_bytes(raw)
        path.chmod(0o600)

    @contextmanager
    def prepared(self):
        with self.ready() as call:
            call.new = S.readmit_closed_entry(call.closed)
            call.entry_window = call.new._attempt.window
            call.entry_last = call.entry_window.last
            call.entry_limits = (call.entry_window.first, call.entry_window.work, call.entry_window.final,
                                 call.new._attempt.owner.local_end)
            self.current = call
            self.session = call.path.with_name(call.path.name + "-productive")
            self.phase = self.session / "recipient-validation"
            original_read, original_close = S.Owner.read, S.Owner.close_one

            def read(owner, directory, name, *args, **kwargs):
                if type(owner.fence) is S._RecipientParentWindow and directory.path == self.phase:
                    self.parent_events.append("read:" + name)
                    if name in ("stdout.log", "stderr.log", "child-result.json"):
                        self.assertTrue(self.parent_scopes[-1].closed)
                        for label in ("native-scope", "stdout", "stderr"):
                            row = next(row for row in owner.resources if row["label"] == label)
                            self.assertTrue(row["closed"])
                return original_read(owner, directory, name, *args, **kwargs)

            def close(owner, resource):
                if type(owner.fence) is S._RecipientParentWindow:
                    row = next(row for row in owner.resources if row["owner"] is resource)
                    if row["label"] in ("native-scope", "stdout", "stderr") and not row["attempted"]:
                        self.parent_events.append("close:" + row["label"])
                return original_close(owner, resource)

            with patch.object(S.processes, "make_scope", side_effect=self.recipient_scope), \
                    patch.object(S.Owner, "read", read), patch.object(S.Owner, "close_one", close):
                yield call

    def parent(self, call=None):
        call = self.current if call is None else call
        row = S._RECIPIENT_ATTEMPTS[id(call.new)]
        self.assertIs(row[0], call.new)
        return row[1]

    def unchanged_predecessors(self, call):
        self.unchanged_old(call)
        self.assertEqual(call.entry_window.last, call.entry_last)
        self.assertEqual((call.entry_window.first, call.entry_window.work, call.entry_window.final,
                          call.new._attempt.owner.local_end), call.entry_limits)
        self.assertTrue(call.new._attempt.owner.closed)
        self.assertFalse(call.new._attempt.owner.unknown)

    def no_retry_parent(self, call):
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_RETRY_CLOCK")), \
                patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_RETRY_OWNER")), \
                self.assertRaisesRegex(O.OriginError, "RECIPIENT_ALREADY_CLAIMED"):
            S.run_recipient_after_entry(call.new)

    def closed_parent(self):
        parent = self.parent()
        owner = parent.actual_owner()
        self.assertTrue(owner.closed)
        self.assertFalse(owner.unknown)
        self.assertFalse(parent.unknown)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))

    def failed(self, kind=Exception, reason=None):
        assertion = self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)
        with assertion as caught:
            S.run_recipient_after_entry(self.current.new)
        self.assertIsNone(self.parent().result)
        self.assertEqual(self.parent().state, "FAILED")
        self.unchanged_predecessors(self.current)
        return caught.exception

    def validate_recipient(self, key, fingerprint, work):
        self.assertEqual(key, self.session / "recipient-admission/recipient-public.asc")
        self.assertEqual(key.read_bytes(), ARMOR)
        self.assertEqual(work, self.session / "crypto")
        self.assertEqual(fingerprint, self.admitted.fingerprint)
        start = O.parse((self.phase / "start.json").read_bytes())
        self.assertEqual(S.query._inherited_context(), start["inheritedContext"])
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        self.assertNotIn("GITHUB_TOKEN", os.environ)
        self.validations.append((key, fingerprint, work))
        (work / "gnupg").mkdir(mode=0o700)
        (work / "tmp").mkdir(mode=0o700)
        self.put(work / "recipient.asc", ARMOR)
        self.put(work / "recipient.gpg", PACKET)
        if self.parent_validator_error is not None:
            raise self.parent_validator_error
        return S.posix.Recipient(work, work / "gnupg", Path(sys.executable), fingerprint.upper(),
            "AB" * 20, self.admitted.expires_at + 1000, self.admitted.key_sha256, S.posix._identity(work))

    def recipient_scope(self, job, invocation, state, home):
        case = self
        self.assertEqual(Path(state), self.session)
        self.assertEqual(Path(home), self.session / "control-home")
        self.parent_events.append("construct")

        class Scope:
            name = "linux-proc-pidfd"

            def __init__(self):
                self.launches, self.closed, self.descriptions = [], False, 0
                self.baseline = case.parent_baseline
                self.close_count = 0

            def _identity(self, pid):
                return {"pid": pid, "startTicks": 9021, "live": True}

            def spawn(self, argv, cwd, env, *, stdout, stderr):
                case.parent_events.append("spawn")
                case.assertEqual(argv[:-2], S.recipient_command(O.digest((case.session / "recipient-context.json").read_bytes())))
                case.assertEqual(argv[-2], "--minimum-ns")
                case.assertEqual(cwd, str(ROOT))
                case.assertNotIn(O.wire.TOKEN_ENV, env)
                case.assertNotIn("GITHUB_TOKEN", env)
                self.launches = [{"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv,
                    "cwd": cwd, "shell": False, "created": True, "executable": argv[0], "pid": 54321,
                    "outputMode": "caller-owned-files"}]
                case.parent_before_child()

                def write(raw):
                    captured = case.parent_ack(raw)
                    case.assertEqual(os.write(stdout.fileno(), captured), len(captured))
                    return len(raw)

                output = SimpleNamespace(buffer=SimpleNamespace(write=write, flush=stdout.sync))
                code = 0
                try:
                    with patch.dict(os.environ, env, clear=True), patch.object(S.sys, "stdout", output):
                        S.guarded(lambda cancelled: S.recipient_child(argv[-3], int(argv[-1]), cancelled))
                except BaseException as error:
                    case.parent_child_errors.append(error)
                    os.write(stderr.fileno(), b"SYNTHETIC_CHILD_FAILURE\n")
                    code = 125
                case.parent_after_child()

                def poll():
                    case.parent_events.append("poll")
                    case.parent_before_poll()
                    return code if case.parent_exit is None else case.parent_exit

                return SimpleNamespace(pid=54321, stdout=None, stderr=None, poll=poll)

            def description(self):
                value = {"backend": self.name, "scope": "controlled-marker-inheriting-descendants",
                    "job": job, "invocation": invocation, "launches": self.launches,
                    "startedIdentities": ([{"pid": 54321, "startTicks": 5678, "uid": os.getuid(), "live": False}]
                        if self.launches else []), "discoveryErrors": [], "discoveryReconciliations": []}
                (case.parent_birth if self.descriptions == 0 else case.parent_terminal)(value)
                self.descriptions += 1
                return value

            def discover(self):
                return case.parent_descendants

            def drain(self, *, grace, kill_wait, deadline):
                self.drain_deadline = deadline
                window = case.parent().window
                case.assertTrue(window.local_last < deadline <= window.final_local)
                case.parent_events.append("drain")
                case.assertTrue(0 <= grace <= 5 and 0 <= kill_wait <= 5)
                case.parent_after_drain()
                return case.parent_survivors

            def close(self):
                self.close_count += 1
                case.parent_events.append("scope-close")
                self.closed = True
                case.parent_scope_close()

        scope = Scope()
        self.parent_scopes.append(scope)
        self.parent_scope_created()
        return scope

    def test_actual_parent_runs_child_and_reads_only_after_native_and_capture_close(self):
        with self.prepared() as call:
            before = {str(path): path.read_bytes() for base in (call.path, call.target.path, call.new._attempt.target.path)
                      for path in base.rglob("*") if path.is_file()}
            with patch.object(call.owner, "close", side_effect=AssertionError("NO_OLD_CLOSE")), \
                    patch.object(call.fence, "now", side_effect=AssertionError("NO_OLD_CLOCK")), \
                    patch.object(call.new._attempt.owner, "close", side_effect=AssertionError("NO_ENTRY_CLOSE")), \
                    patch.object(type(call.entry_window), "now", side_effect=AssertionError("NO_ENTRY_CLOCK")):
                result = S.run_recipient_after_entry(call.new)
            self.assertFalse(self.parent_child_errors, self.parent_child_errors)
            self.assertEqual(len(self.validations), 1)
            self.assertEqual(len(self.parent_scopes), 1)
            self.assertEqual(self.parent_scopes[0].close_count, 1)
            self.assertEqual(call.new_calls.count("finalize"), 2)  # New entry and actual child wrapper, modeled query.
            events = self.parent_events
            for earlier, later in (("spawn", "poll"), ("poll", "drain"), ("drain", "scope-close"),
                    ("scope-close", "close:stdout"), ("close:stdout", "close:stderr"),
                    ("close:stderr", "read:stdout.log")):
                self.assertLess(events.index(earlier), events.index(later))
            self.closed_parent()
            self.unchanged_predecessors(call)
            self.assertEqual(before, {name: Path(name).read_bytes() for name in before})
            self.assertEqual((len(self.requests), len(self.scopes)), (2, 1))
            self.assertIs(result, self.parent().result)
            self.no_retry_parent(call)

    def test_private_prefix_is_evidence_not_live_recipient_or_execution_authority(self):
        with self.prepared() as call:
            result = S.run_recipient_after_entry(call.new)
            value, pending = O.parse(result.raw), O.parse(result.pending_raw)
            self.assertEqual(value["scope"], S.RECIPIENT_PREFIX_SCOPE)
            self.assertEqual(value["pendingSha256"], O.digest(result.pending_raw))
            self.assertEqual(value["parentResourceClose"], "KNOWN_RESOURCE_CLOSE_ONLY")
            self.assertIs(value["nextPhaseAuthority"], False)
            self.assertEqual(pending["parentResourceClose"], "PENDING_CLOSE")
            self.assertNotIn("closedNs", pending)
            self.assertEqual(value["window"], pending["window"])
            self.assertGreater(result.checked_ns, value["closedNs"])
            self.assertEqual(result.checked_ns, self.parent().window.last)
            for item in (value, pending):
                self.assertEqual(item["budgetAcceptance"], "NOT_ADMITTED")
                self.assertEqual(item["testAcceptance"], "NOT_PERFORMED")
                self.assertIs(item["exportSaveAuthority"], False)
            self.assertEqual((self.session / "recipient-prefix-pending.json").read_bytes(), result.pending_raw)
            self.assertFalse((self.session / "recipient-prefix-result.json").exists())
            self.assertEqual(repr(result), "RecipientPrefix()")
            with self.assertRaises(FrozenInstanceError):
                result.raw = b"{}"
            self.assertEqual((self.phase / "child-result.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(dict(result.originals)["crypto/recipient.gpg"], PACKET)
            self.assertEqual(pending["originalsSha256"], {name: O.digest(raw) for name, raw in result.originals})

    def test_foreign_copies_refuse_before_claim_clock_or_owner(self):
        with self.prepared() as call:
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_FOREIGN_CLOCK")), \
                    patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_FOREIGN_OWNER")):
                for foreign in (copy.copy(call.new), replace(call.new), SimpleNamespace(raw=call.new.raw)):
                    with self.assertRaisesRegex(O.OriginError, "NOT_CURRENT_RETURN"):
                        S.run_recipient_after_entry(foreign)
            self.assertEqual(S._RECIPIENT_ATTEMPTS, {})
            S.run_recipient_after_entry(call.new)

    def test_first_clock_failure_keeps_claim_and_first_exception_without_owner(self):
        with self.prepared() as call:
            failure = O.clocks.ClockError("SYNTHETIC_FIRST_CLOCK")
            with patch.object(O.clocks, "observe", side_effect=failure), \
                    patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_OWNER")):
                self.assertIs(self.failed(O.clocks.ClockError), failure)
            self.assertIsNone(self.parent().actual_owner())
            self.no_retry_parent(call)

    def test_backward_first_cannot_recover_with_a_later_clock(self):
        with self.prepared() as call:
            first = O.clocks.Reading(self.clock, call.new._checked_ns - 1)
            with patch.object(O.clocks, "observe", return_value=first):
                self.failed(O.OriginError, "FIRST_CLOCK")
            self.assertIs(self.parent().first, first)
            self.assertIsNone(self.parent().actual_owner())
            self.no_retry_parent(call)

    def test_complete_clock_identity_cannot_change(self):
        with self.prepared():
            changed = O.clocks.ClockIdentity("windows-x64", O.clocks.WINDOWS_DOMAIN, 10_000_001)
            with patch.object(O.clocks, "observe", return_value=O.clocks.Reading(changed, self.nanoseconds)):
                self.failed(O.OriginError, "FIRST_CLOCK")
            self.assertIsNone(self.parent().actual_owner())

    def test_closed_graph_validation_is_non_acquiring_without_replaying_full_parser(self):
        with self.prepared() as call:
            S.check_new_entry_transition(call.new)
            with ExitStack() as guards:
                for target, name in ((O.clocks, "observe"), (S.time, "monotonic"), (Path, "read_bytes"),
                        (S.Owner, "__init__"), (S.Owner, "acquire"), (S.Owner, "read"), (S.Owner, "close")):
                    guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_PIN_SUPPLIER")))
                graph = S._RecipientPredecessorGraph.capture(call.new)
                with patch.object(S, "check_new_entry_transition", side_effect=AssertionError("NO_PARSER_REPLAY")):
                    for _ in range(3):
                        graph.checked(call.new)
            self.assertTrue(any(value is call.closed._owner for value, _, _, _ in graph.nodes))
            self.assertTrue(any(value is call.new._attempt.owner for value, _, _, _ in graph.nodes))
            self.assertIs(graph.registry, S._ENTRY_ATTEMPTS)
            self.assertIs(graph.registered, S._ENTRY_ATTEMPTS[id(call.closed)])
            self.unchanged_predecessors(call)

    def test_nested_typed_predecessor_changes_match_complete_validator_refusals(self):
        with self.prepared() as call:
            new, old, attempt = call.new, call.closed, call.new._attempt
            graph = S._RecipientPredecessorGraph.capture(new)
            changes = (
                (new, "raw", new.raw + b" "), (new, "_checked_ns", new._checked_ns + 1),
                (new, "_preclose_ns", True), (old, "raw", old.raw + b" "),
                (old, "pending_raw", old.pending_raw + b" "), (old, "proposal_raw", old.proposal_raw + b" "),
                (old, "responses", ()), (old, "_checked_ns", old._checked_ns + 1),
                (old._fence, "last", old._fence.last + 1), (old._fence, "work", old._fence.work + 1),
                (old._fence.clock, "ticks_per_second", old._fence.clock.ticks_per_second + 1),
                (old._fence.clock, "domain", "SYNTHETIC_DIFFERENT_DOMAIN"),
                (old._owner, "closed", False), (old._owner, "unknown", True),
                (old._owner, "cancelled", lambda: None), (old._owner, "entry_close_original", copy.copy(old)),
                (old._entry, "context_original", old._entry.context_original + b" "),
                (old._entry, "handoff_original", old._entry.handoff_original + b" "),
                (old._entry, "admitted", replace(old._entry.admitted)),
                (attempt, "state", "FAILED"), (attempt, "transition", copy.copy(old)),
                (attempt, "owner", copy.copy(attempt.owner)), (attempt, "window", copy.copy(attempt.window)),
                (attempt, "first", replace(attempt.first)), (attempt, "bindings", tuple(list(attempt.bindings))),
                (attempt, "originals", tuple(list(attempt.originals))),
                (attempt, "admission_originals", tuple(list(attempt.admission_originals))),
                (attempt.window, "last", attempt.window.last + 1),
                (attempt.window, "final", attempt.window.final + 1),
                (attempt.owner, "phase_originals", object()), (attempt.owner, "unknown", True),
                (attempt.admitted, "record", attempt.admitted.record + b" "),
                (attempt.admitted, "public_key", b"NOT_A_KEY"),
                (old._entry._private, "path", old._entry._private.path.with_name("changed-original")),
                (old._entry._target, "path", old._entry._target.path.with_name("changed-adoption")),
            )
            for target, name, changed in changes:
                with self.subTest(kind=type(target).__name__, field=name):
                    original = getattr(target, name)
                    object.__setattr__(target, name, changed)
                    try:
                        with self.assertRaises(Exception):
                            S.check_new_entry_transition(new)
                        with self.assertRaises(O.OriginError):
                            graph.checked(new)
                    finally:
                        object.__setattr__(target, name, original)
                    S.check_new_entry_transition(new)
                    graph.checked(new)

    def test_container_and_actual_registry_mutations_match_complete_validator_refusals(self):
        with self.prepared() as call:
            new, attempt = call.new, call.new._attempt
            graph = S._RecipientPredecessorGraph.capture(new)
            for owner in (call.owner, attempt.owner):
                for name, value in (("label", "changed"), ("owner", object()), ("attempted", 1), ("closed", False)):
                    row, original = owner.resources[0], owner.resources[0][name]
                    original_resources = attempt.resources
                    with self.subTest(owner=owner is attempt.owner, field=name):
                        row[name] = value
                        try:
                            with self.assertRaises(O.OriginError):
                                graph.checked(new)
                            with self.assertRaises(Exception):
                                S.check_new_entry_transition(new)
                        finally:
                            row[name] = original
                            # Test-fixture reset only: the legacy full checker
                            # deliberately retains suspicious replacement pins.
                            # Do not contaminate the next independent mutation
                            # or claim that production may erase that history.
                            attempt.resources = original_resources
                        S.check_new_entry_transition(new)
                        graph.checked(new)
            key, original = id(call.closed), S._ENTRY_ATTEMPTS[id(call.closed)]
            for duplicate in (False, True):
                with self.subTest(duplicate=duplicate):
                    if duplicate:
                        S._ENTRY_ATTEMPTS["duplicate"] = original
                    else:
                        del S._ENTRY_ATTEMPTS[key]
                    try:
                        with self.assertRaises(Exception):
                            S.check_new_entry_transition(new)
                        with self.assertRaises(O.OriginError):
                            graph.checked(new)
                    finally:
                        if duplicate:
                            del S._ENTRY_ATTEMPTS["duplicate"]
                        else:
                            S._ENTRY_ATTEMPTS[key] = original
                    S.check_new_entry_transition(new)
                    graph.checked(new)

    def test_graph_refuses_changed_preparation_bytes_even_when_full_parser_values_match(self):
        with self.prepared() as call:
            attempt = call.new._attempt
            graph = S._RecipientPredecessorGraph.capture(call.new)
            expected = S.check_new_entry_transition(call.new)
            original = attempt.preparation
            attempt.preparation += b" "
            try:
                # The legacy content validator parses this nested record; the
                # parent has always additionally pinned its ORIGINAL bytes.
                self.assertEqual(S.check_new_entry_transition(call.new), expected)
                with self.assertRaisesRegex(O.OriginError, "PREDECESSOR_CHANGED"):
                    graph.checked(call.new)
            finally:
                attempt.preparation = original
            graph.checked(call.new)

    def test_exact_graph_also_refuses_equal_container_replacement_and_moved_registry(self):
        with self.prepared() as call:
            attempt = call.new._attempt
            graph = S._RecipientPredecessorGraph.capture(call.new)
            # Stricter immutable-edge checks, not claims that all value-equal
            # replacement containers were refused by the legacy full parser.
            for target, name in ((attempt, "returned"), (attempt.owner, "resources"), (call.owner, "admissions")):
                original = getattr(target, name)
                with self.subTest(field=name), patch.object(target, name, copy.copy(original)), \
                        self.assertRaises(O.OriginError):
                    graph.checked(call.new)
                graph.checked(call.new)
            original = S._ENTRY_ATTEMPTS.pop(id(call.closed))
            S._ENTRY_ATTEMPTS["moved"] = original
            try:
                with self.assertRaises(O.OriginError):
                    graph.checked(call.new)
            finally:
                del S._ENTRY_ATTEMPTS["moved"]
                S._ENTRY_ATTEMPTS[id(call.closed)] = original
            with patch.object(S, "_ENTRY_ATTEMPTS", dict(S._ENTRY_ATTEMPTS)), self.assertRaises(O.OriginError):
                graph.checked(call.new)
            graph.checked(call.new)

    def test_closed_predecessor_change_at_first_clock_refuses_before_new_ownership(self):
        with self.prepared() as call:
            original_observe, first = O.clocks.observe, call.new._attempt.owner.closed
            def observe():
                result = original_observe()
                call.new._attempt.owner.closed = False
                return result
            try:
                with patch.object(O.clocks, "observe", observe), \
                        patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_CHANGED_PREDECESSOR_OWNER")), \
                        self.assertRaisesRegex(O.OriginError, "PREDECESSOR_CHANGED"):
                    S.run_recipient_after_entry(call.new)
                self.assertIsNone(self.parent().actual_owner())
                self.assertIsNone(self.parent().result)
            finally:
                call.new._attempt.owner.closed = first
            self.unchanged_predecessors(call)

    def test_closed_predecessor_change_at_factory_return_preserves_actual_new_resource(self):
        with self.prepared() as call:
            factory, returned, first = S.query._PosixDirectory, [], call.closed._fence.last
            def open_directory(path):
                resource = factory(path)
                returned.append(resource)
                call.closed._fence.last += 1
                return resource
            try:
                with patch.object(S.query, "_PosixDirectory", open_directory), \
                        self.assertRaisesRegex(O.OriginError, "PREDECESSOR_CHANGED"):
                    S.run_recipient_after_entry(call.new)
                self.assertEqual(len(returned), 1)
                self.assertTrue(self.parent().actual_owner().closed)
                self.assertTrue(any(pin.resource is returned[0] and pin.attempted and pin.closed
                                    for pin in self.parent().bindings.seen))
                self.assertIsNone(self.parent().result)
            finally:
                call.closed._fence.last = first
            self.unchanged_predecessors(call)

    def test_reentry_is_rejected_while_original_scope_factory_is_running(self):
        with self.prepared() as call:
            self.parent_scope_created = lambda: self.no_retry_parent(call)
            S.run_recipient_after_entry(call.new)
            self.assertEqual(len(self.parent_scopes), 1)

    def test_concurrent_claim_has_only_one_clock_and_no_losing_owner(self):
        with self.prepared() as call:
            entered, release, errors = threading.Event(), threading.Event(), []
            failure = StopProbe("SYNTHETIC_CLAIM_STOP")
            def observe():
                entered.set()
                self.assertTrue(release.wait(2))
                raise failure
            def first():
                try:
                    S.run_recipient_after_entry(call.new)
                except BaseException as error:
                    errors.append(error)
            with patch.object(O.clocks, "observe", side_effect=observe) as readings:
                worker = threading.Thread(target=first)
                worker.start()
                try:
                    self.assertTrue(entered.wait(2))
                    with self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
                        S.run_recipient_after_entry(call.new)
                finally:
                    release.set()
                    worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(readings.call_count, 1)
            self.assertEqual(errors, [failure])
            self.assertIsNone(self.parent().actual_owner())

    def probe(self, operation, kind=Exception, reason=None):
        with self.prepared():
            with patch.object(S._RecipientParent, "launch", operation):
                error = self.failed(kind, reason)
            self.assertFalse(self.parent_scopes)
            return error

    def test_work_raw240_equality_expires_without_native_launch(self):
        def probe(parent):
            self.nanoseconds = parent.window.work
            parent.window.now()
        self.probe(probe, O.OriginError, "PARENT_EXPIRED")
        self.closed_parent()

    def test_independent_local_work240_cannot_use_prefix315(self):
        def probe(parent):
            self.assertLess(parent.window.work_local, parent.window.local_end)
            with patch.object(S.time, "monotonic", return_value=parent.window.work_local):
                parent.window.now()
        self.probe(probe, O.OriginError, "LOCAL_EXPIRED")

    def test_independent_local_clock_cannot_go_backwards(self):
        def probe(parent):
            with patch.object(S.time, "monotonic", return_value=parent.window.local_last - 1):
                parent.window.now()
        self.probe(probe, O.OriginError, "LOCAL_CLOCK")

    def test_static_window_change_refuses_before_clock_or_native(self):
        def probe(parent):
            object.__setattr__(parent.window, "work", parent.window.work + O.NS)
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_CHANGED_WINDOW_CLOCK")):
                parent.window.now()
        self.probe(probe, O.OriginError, "WINDOW_CHANGED")

    def test_cumulative_recipient_fences_only_shorten_original_caps(self):
        with self.prepared() as call:
            proposal = O.parse(call.closed.proposal_raw)
            self.nanoseconds = proposal["phaseFencesNs"]["recipient-validation"] - 30 * O.NS
            S.run_recipient_after_entry(call.new)
            window = self.parent().window
            self.assertEqual(window.work, proposal["phaseFencesNs"]["recipient-validation"])
            self.assertEqual(window.native_end, proposal["phaseFencesNs"]["recipient-final"])
            self.assertEqual(window.prefix_end, proposal["phaseFencesNs"]["recipient-read"])
            self.assertLess(window.work - window.first, 30 * O.NS)
            self.assertLessEqual(window.prefix_end, proposal["proposedJobEndNs"])

    def test_original_job_expiry_is_not_a_new5400_allowance(self):
        with self.prepared() as call:
            self.nanoseconds = O.parse(call.closed.proposal_raw)["proposedJobEndNs"]
            self.failed(O.OriginError, "NO_INTERVAL")
            self.assertIsNone(self.parent().actual_owner())
            self.assertFalse(self.parent_scopes)

    def test_early_native_final45_does_not_inherit_all_first285(self):
        with self.prepared() as call:
            S.run_recipient_after_entry(call.new)
            window = self.parent().window
            self.assertLess(window.final, window.native_end)
            self.assertEqual(window.final, window.final_started + 45 * O.NS)
            self.assertLessEqual(window.final_local, window.final_local_start + 45)
            self.assertLessEqual(window.final_local, window.native_local)
            self.assertEqual(window.read_end, window.read_started + 30 * O.NS)

    def test_actual_final45_equality_after_drain_is_failure_not_read_admission(self):
        with self.prepared():
            self.parent_after_drain = lambda: setattr(self, "nanoseconds", self.parent().window.final)
            self.failed(O.OriginError, "PARENT_EXPIRED")
            self.assertTrue(self.parent_scopes[0].closed)
            self.assertTrue(self.parent().unknown)
            self.assertFalse(self.parent().native_retired)
            self.assertNotIn("read:stdout.log", self.parent_events)

    def test_local_drain_return_equality_is_not_retirement_even_with_timely_raw(self):
        with self.prepared():
            def late():
                self.stack.enter_context(patch.object(S.time, "monotonic",
                    return_value=self.parent_scopes[0].drain_deadline))
            self.parent_after_drain = late
            self.failed(Exception)
            self.assertFalse(self.parent().native_retired)
            self.assertTrue(self.parent().unknown)
            self.assertEqual(self.parent_scopes[0].close_count, 1)
            self.assertNotIn("read:stdout.log", self.parent_events)

    def test_local_scope_close_equality_keeps_close_but_refuses_retirement(self):
        with self.prepared():
            def late():
                self.stack.enter_context(patch.object(S.time, "monotonic",
                    return_value=self.parent_scopes[0].drain_deadline))
            self.parent_scope_close = late
            self.failed(Exception)
            self.assertFalse(self.parent().native_retired)
            self.assertTrue(self.parent().row["scopeClosed"])
            self.assertEqual(self.parent_scopes[0].close_count, 1)
            self.assertNotIn("read:stdout.log", self.parent_events)

    def test_missing_final_start_skips_drain_preserves_first_error_and_known_close(self):
        first = FalseyFailure("MODELED_MISSING_FINAL_START")
        with self.prepared(), patch.object(S._RecipientParentWindow, "begin_final", side_effect=first):
            self.assertIs(self.failed(FalseyFailure), first)
            self.assertNotIn("drain", self.parent_events)
            self.assertEqual(self.parent_scopes[0].close_count, 1)
            self.assertFalse(self.parent().native_retired)
            self.assertTrue(self.parent().unknown)

    def test_delayed_final_start_cannot_renew_first285(self):
        def probe(parent):
            self.nanoseconds = parent.window.first + 260 * O.NS
            parent.window.begin_final()
            self.assertEqual(parent.window.final, parent.window.native_end)
            self.assertLess(parent.window.final, parent.window.final_started + 45 * O.NS)
            self.nanoseconds = parent.window.native_end
            parent.window.now(final=True)
        self.probe(probe, O.OriginError, "PARENT_EXPIRED")

    def test_local_final_also_stays_inside_first285(self):
        def probe(parent):
            with patch.object(S.time, "monotonic", return_value=parent.local_start + 260):
                parent.window.begin_final()
                self.assertEqual(parent.window.final_local, parent.window.native_local)
                with patch.object(S.time, "monotonic", return_value=parent.window.native_local):
                    parent.window.now(final=True)
        self.probe(probe, O.OriginError, "LOCAL_EXPIRED")

    def test_failed_final_start_is_once_only_and_no_replacement45(self):
        failure = O.clocks.ClockError("SYNTHETIC_FINAL_CLOCK")
        def probe(parent):
            with patch.object(O.clocks, "observe", side_effect=failure), self.assertRaises(O.clocks.ClockError):
                parent.window.begin_final()
            self.assertIsNone(parent.window.final_started)
            self.assertEqual(parent.window.final, 0)
            with self.assertRaisesRegex(O.OriginError, "FINAL_REENTRY"):
                parent.window.begin_final()
            raise failure
        self.assertIs(self.probe(probe, O.clocks.ClockError), failure)

    def test_read30_equality_refuses_and_no_postexpiry_pending_file(self):
        with self.prepared():
            original = S._RecipientParent.reread_files
            def reread(parent):
                self.nanoseconds = parent.window.read_end
                return original(parent)
            with patch.object(S._RecipientParent, "reread_files", reread):
                self.failed(O.OriginError, "PARENT_EXPIRED")
            self.assertFalse((self.session / "recipient-prefix-pending.json").exists())
            self.assertTrue(self.parent().unknown)

    def test_local_read30_refuses_even_with_unexpired_raw(self):
        with self.prepared():
            original = S._RecipientParent.reread_files
            def reread(parent):
                with patch.object(S.time, "monotonic", return_value=parent.window.read_local):
                    return original(parent)
            with patch.object(S._RecipientParent, "reread_files", reread):
                self.failed(O.OriginError, "LOCAL_EXPIRED")

    def test_returned_scope_survives_postreturn_clock_failure_without_invented_birth(self):
        with self.prepared():
            failure, original = O.clocks.ClockError("SYNTHETIC_AFTER_SCOPE_RETURN"), O.clocks.observe
            armed = [False]
            self.parent_scope_created = lambda: armed.__setitem__(0, True)
            def observe():
                if armed[0]:
                    armed[0] = False
                    raise failure
                return original()
            with patch.object(O.clocks, "observe", side_effect=observe):
                self.assertIs(self.failed(O.clocks.ClockError), failure)
            parent = self.parent()
            self.assertNotIn("preparerIdentity", parent.row)
            self.assertNotIn("leader", parent.row)
            self.assertFalse(parent.row["launchAttempted"])
            self.assertTrue(parent.native_retired)
            self.assertTrue(parent.captures_retired)
            self.assertEqual(self.parent_scopes[0].close_count, 1)
            self.closed_parent()

    def test_scope_constructor_failure_keeps_unknown_and_no_capture_read(self):
        with self.prepared():
            failure = OSError("SYNTHETIC_SCOPE_CONSTRUCTOR")
            with patch.object(S.processes, "make_scope", side_effect=failure):
                self.assertIs(self.failed(OSError), failure)
            self.assertTrue(self.parent().unknown)
            self.assertNotIn("read:stdout.log", self.parent_events)
            self.assertFalse(self.validations)

    def test_first_falsey_native_exception_survives_failed_scope_close(self):
        with self.prepared():
            failure = FalseyFailure("SYNTHETIC_FALSEY_FIRST")
            def begin():
                raise failure
            def close():
                raise OSError("SYNTHETIC_SECOND_CLOSE")
            self.parent_before_child, self.parent_scope_close = begin, close
            self.assertIs(self.failed(FalseyFailure), failure)
            self.assertIs(self.parent().original, failure)
            self.assertTrue(self.parent().unknown)
            self.assertEqual(self.parent_scopes[0].close_count, 1)

    def test_nonzero_child_is_unknown_despite_known_outer_drain(self):
        with self.prepared():
            self.parent_exit = 125
            self.failed(O.OriginError, "CHILD_FAILED")
            self.assertTrue((self.phase / "child-result.json").is_file())
            self.assertTrue(self.parent().native_retired)
            self.assertTrue(self.parent().unknown)
            self.assertNotIn("read:stdout.log", self.parent_events)

    def test_failed_supplier_is_not_rehabilitated_by_outer_close(self):
        with self.prepared():
            self.parent_validator_error = OSError("SYNTHETIC_VALIDATOR_FAILURE")
            self.failed(O.OriginError, "CHILD_FAILED")
            self.assertEqual(self.parent_child_errors, [self.parent_validator_error])
            self.assertTrue(self.parent().unknown)
            self.assertEqual((self.session / "crypto/recipient.gpg").read_bytes(), PACKET)
            self.assertFalse((self.session / "recipient-prefix-failure.json").exists())

    def test_missing_ack_is_unknown_after_successful_outer_retirement(self):
        with self.prepared():
            self.parent_ack = lambda raw: b""
            self.failed()
            self.assertTrue(self.parent().native_retired)
            self.assertTrue(self.parent().captures_retired)
            self.assertTrue(self.parent().unknown)
            self.assertTrue((self.phase / "child-result.json").exists())

    def test_late_ack_clock_cannot_be_promoted_by_matching_digest(self):
        with self.prepared():
            def changed(raw):
                value = O.parse(raw)
                value["closedNs"] = self.parent().window.work
                return O.encoded(value)
            self.parent_ack = changed
            self.failed(O.OriginError, "CHILD_CHRONOLOGY")
            self.assertTrue(self.parent().unknown)

    def test_native_birth_and_terminal_launches_must_match(self):
        with self.prepared():
            self.parent_terminal = lambda value: value["launches"][0].update(extra="SYNTHETIC_DRIFT")
            self.failed(O.OriginError, "NATIVE_BIRTH_CHANGED")
            self.assertTrue(self.parent().unknown)

    def test_unretired_descendant_or_drain_is_not_known(self):
        with self.prepared():
            self.parent_survivors = [{"pid": 54321, "startTicks": 5678}]
            self.failed(O.OriginError, "DRAIN_UNKNOWN")
            self.assertTrue(self.parent().unknown)
            self.assertNotIn("read:stdout.log", self.parent_events)

    def test_baseline_cannot_already_contain_launched_leader(self):
        with self.prepared():
            self.parent_baseline = {(54321, 5678)}
            self.failed(O.OriginError, "PREEXISTING_LEADER")
            self.assertTrue(self.parent().unknown)

    def test_capture_close_failure_stops_readback_and_keeps_actual_sink(self):
        with self.prepared():
            failure, original = OSError("SYNTHETIC_CAPTURE_CLOSE"), S.query._PosixSink.close
            def close(stream):
                if stream.path == self.phase / "stdout.log":
                    raise failure
                return original(stream)
            with patch.object(S.query._PosixSink, "close", close):
                self.assertIs(self.failed(OSError), failure)
            parent = self.parent()
            self.assertTrue(parent.unknown)
            self.assertIsNotNone(parent.resource("stdout"))
            self.assertNotIn("read:stdout.log", self.parent_events)

    def test_rebound_owner_never_redirects_actual_resource_cleanup(self):
        with self.prepared():
            original = S._RecipientParent.private_inputs
            actual, foreign = [], SimpleNamespace(close=lambda: self.fail("NO_FOREIGN_CLOSE"))
            def inputs(parent):
                original(parent)
                actual.append(parent.actual_owner())
                parent.owner = foreign
            with patch.object(S._RecipientParent, "private_inputs", inputs):
                self.failed(O.OriginError, "OWNER_CHANGED")
            self.assertEqual(len(actual), 1)
            self.assertTrue(actual[0].closed)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in actual[0].resources))

    def test_rejected_call_aliases_do_not_saturate_large_known_resource_cleanup(self):
        with self.prepared() as call:
            closes, failures, saved = [], [], []
            foreign = SimpleNamespace(close=lambda: self.fail("NO_FOREIGN_CLOSE"))
            def operation(parent):
                owner, window = parent.actual_owner(), parent.window
                for number in range(80):
                    resource = SimpleNamespace(close=lambda number=number: closes.append(number))
                    owner.acquire("directory", lambda resource=resource: resource)
                bound = S._RECIPIENT_ATTEMPTS[id(call.new)][3]
                saved.append((owner, window, window.limits(), bound))
                # Rejected execution aliases are NEVER restored by production.
                # The actual registered owner/frame/roster remain untouched.
                parent.transition, parent.originals, parent.bindings = copy.copy(call.new), (), None
                parent.owner, parent.window, parent.first, parent.callback = foreign, None, None, None
                parent.local_start, parent.errors = 1e30, []
                try:
                    parent.check()
                except BaseException as error:
                    failures.append(error)
                    raise
            with patch.object(S._RecipientParent, "launch", operation):
                error = self.failed(O.OriginError, "CLAIM_CHANGED")
            owner, window, limits, bound = saved[0]
            parent = self.parent()
            self.assertIs(error, failures[0])
            self.assertIs(owner.original, error)
            self.assertEqual(sorted(closes), list(range(80)))
            self.assertTrue(owner.closed)
            self.assertFalse(owner.unknown or parent.unknown)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))
            self.assertLess(len(owner.errors), 16)  # Not the unchanged64-entry saturation policy.
            self.assertIs(S._RECIPIENT_ATTEMPTS[id(call.new)][3], bound)
            self.assertEqual(window.limits(cleanup=True), limits)
            self.assertEqual(window.phase, "FINAL")
            self.assertEqual(window.final, min(window.native_end, window.final_started + 45 * O.NS))
            self.assertIs(parent.owner, foreign)
            self.assertIsNone(parent.window)
            self.assertIsNone(parent.bindings)
            self.assertEqual(parent.errors, [])
            self.assertFalse(self.parent_scopes)
            self.assertFalse((self.session / "recipient-prefix-failure.json").exists())

    def test_final_deadline_rejects_alias_before_clock_and_factory(self):
        factories = []
        def operation(parent):
            owner = parent.actual_owner()
            parent.owner = SimpleNamespace(close=lambda: self.fail("NO_FOREIGN_CLOSE"))
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_REJECTED_ALIAS_CLOCK")), \
                    patch.object(S.time, "monotonic", side_effect=AssertionError("NO_REJECTED_ALIAS_LOCAL")):
                owner.acquire("directory", lambda: factories.append("FORBIDDEN"), final=True)
        self.probe(operation, O.OriginError, "OWNER_CHANGED")
        self.assertEqual(factories, [])
        self.closed_parent()

    def test_final_deadline_rejects_alias_changed_during_raw_supplier_before_factory(self):
        factories, readings = [], []
        def operation(parent):
            owner, observe = parent.actual_owner(), O.clocks.observe
            foreign = SimpleNamespace(close=lambda: self.fail("NO_FOREIGN_CLOSE"))
            def changed():
                reading = observe()
                readings.append(reading)
                parent.owner = foreign
                return reading
            with patch.object(O.clocks, "observe", side_effect=changed):
                owner.acquire("directory", lambda: factories.append("FORBIDDEN"), final=True)
        self.probe(operation, O.OriginError, "OWNER_CHANGED")
        self.assertEqual(len(readings), 1)
        self.assertEqual(factories, [])
        self.closed_parent()

    def test_final_observation_is_nonacquiring_even_after_execution_alias_rejection(self):
        failure = StopProbe("SYNTHETIC_OBSERVATION_ONLY")
        def operation(parent):
            window = parent.window
            parent.owner = SimpleNamespace(close=lambda: self.fail("NO_FOREIGN_CLOSE"))
            with ExitStack() as guards:
                for target, name in ((S.Owner, "acquire"), (S.Owner, "read"), (S.Owner, "write"),
                                     (parent, "cancel")):
                    guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_FINAL_IO_OR_CALLBACK")))
                window.begin_final()
                before = window.last
                self.assertGreater(window.now(final=True), before)
                self.assertLessEqual(window.cleanup_deadline(45), window.final_local)
                for strict in (parent.live, window.record, lambda: window.deadline(45, final=True)):
                    with self.assertRaisesRegex(O.OriginError, "OWNER_CHANGED"):
                        strict()
            raise failure
        self.assertIs(self.probe(operation, StopProbe), failure)
        self.closed_parent()

    def test_cleanup_observation_still_rejects_changed_actual_owner_frame(self):
        def operation(parent):
            parent.actual_owner().local_end += 1
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_CHANGED_BOUND_CLOCK")):
                parent.window.now(final=True)
        self.probe(operation, O.OriginError, "OWNER_CHANGED")
        self.assertIsNone(self.parent().result)
        self.assertFalse((self.session / "recipient-prefix-failure.json").exists())

    def test_cleanup_observation_still_rejects_changed_actual_highwater(self):
        def operation(parent):
            object.__setattr__(parent.window, "last", parent.window.last + 1)
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_CHANGED_HIGHWATER_CLOCK")):
                parent.window.now(final=True)
        self.probe(operation, O.OriginError, "WINDOW_CHANGED")
        self.assertIsNone(self.parent().result)
        self.assertFalse((self.session / "recipient-prefix-failure.json").exists())

    def test_failed_cleanup_start_after_alias_rejection_stays_consumed_and_expired(self):
        failure = O.clocks.ClockError("SYNTHETIC_CLEANUP_FIRST_CLOCK")
        def operation(parent):
            window = parent.window
            parent.owner = SimpleNamespace(close=lambda: self.fail("NO_FOREIGN_CLOSE"))
            with patch.object(O.clocks, "observe", side_effect=failure), self.assertRaises(O.clocks.ClockError) as caught:
                window.begin_final()
            self.assertIs(caught.exception, failure)
            self.assertEqual((window.phase, window.final_started, window.final_local_start,
                              window.final, window.final_local), ("FINAL", None, None, 0, 0.0))
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_RENEWAL_CLOCK")), \
                    self.assertRaisesRegex(O.OriginError, "FINAL_REENTRY"):
                window.begin_final()
            with self.assertRaisesRegex(O.OriginError, "PARENT_EXPIRED"):
                window.cleanup_deadline(45)
            self.assertEqual((window.final, window.final_local), (0, 0.0))
            raise failure
        self.assertIs(self.probe(operation, O.clocks.ClockError), failure)

    def read_cleanup_expiry(self, *, local):
        with self.prepared():
            saved = []
            def reread(parent):
                window = parent.window
                self.assertEqual(window.phase, "READ")
                parent.owner = SimpleNamespace(close=lambda: self.fail("NO_FOREIGN_CLOSE"))
                state = window.phase_state()
                with self.assertRaisesRegex(O.OriginError, "FINAL_REENTRY"):
                    window.begin_final()
                self.assertEqual(window.phase_state(), state)
                saved.append(state)
                if local:
                    with patch.object(S.time, "monotonic", return_value=window.read_local):
                        window.cleanup_deadline(45)
                else:
                    self.nanoseconds = window.read_end
                    window.cleanup_deadline(45)
            with patch.object(S._RecipientParent, "reread_files", reread):
                self.failed(O.OriginError, "LOCAL_EXPIRED" if local else "PARENT_EXPIRED")
            self.assertEqual(len(saved), 1)
            self.assertEqual(self.parent().window.phase_state(), saved[0])
            self.assertFalse((self.session / "recipient-prefix-failure.json").exists())
            self.assertFalse((self.session / "recipient-prefix-pending.json").exists())

    def test_read_cleanup_after_alias_rejection_keeps_existing_raw30_without_new45(self):
        self.read_cleanup_expiry(local=False)

    def test_read_cleanup_after_alias_rejection_keeps_existing_local30_without_new45(self):
        self.read_cleanup_expiry(local=True)

    def test_rebound_transition_cannot_erase_original_scope_reference(self):
        with self.prepared() as call:
            self.parent_scope_created = lambda: setattr(self.parent(), "transition", copy.copy(call.new))
            self.failed(O.OriginError, "CLAIM_CHANGED")
            parent = self.parent()
            self.assertIs(parent.resource("native-scope"), self.parent_scopes[0])
            self.assertEqual(self.parent_scopes[0].close_count, 1)
            self.assertIs(S._RECIPIENT_ATTEMPTS[id(call.new)][0], call.new)

    def test_late_removed_row_is_unknown_even_when_first_error_already_exists(self):
        with self.prepared():
            failure, original = FalseyFailure("SYNTHETIC_FIRST_CLOSE"), S.Owner.close
            retained = []
            def close(owner):
                original(owner)
                if type(owner.fence) is S._RecipientParentWindow:
                    retained.append(owner.resources.pop())
                    raise failure
            with patch.object(S.Owner, "close", close):
                self.assertIs(self.failed(FalseyFailure), failure)
            parent = self.parent()
            self.assertTrue(parent.unknown)
            self.assertIs(parent.original, failure)
            self.assertTrue(any(pin.row is retained[0] for pin in parent.bindings.seen))
            self.assertIn(parent.actual_owner(), S.QUARANTINE)

    def test_postclose_flag_regression_is_unknown_without_another_close(self):
        with self.prepared():
            original, closed = S.Owner.close, []
            def close(owner):
                original(owner)
                if type(owner.fence) is S._RecipientParentWindow:
                    closed.append(owner)
                    owner.resources[0]["closed"] = False
            with patch.object(S.Owner, "close", close):
                self.failed(O.OriginError, "ROSTER")
            self.assertEqual(len(closed), 1)
            self.assertTrue(self.parent().unknown)

    def test_handler_restore_failure_is_not_success_or_postclose_file_acquisition(self):
        with self.prepared():
            failure, handlers = OSError("SYNTHETIC_HANDLER_RESTORE"), {}
            def get(number):
                return handlers.setdefault(number, object())
            def set_handler(number, handler):
                if handler is handlers.get(number) and self.parent().actual_owner().closed:
                    raise failure
            with patch.object(S.signal, "getsignal", side_effect=get), patch.object(S.signal, "signal", side_effect=set_handler):
                self.assertIs(self.failed(OSError), failure)
            self.closed_parent()
            self.assertTrue((self.session / "recipient-prefix-pending.json").exists())
            self.assertFalse((self.session / "recipient-prefix-failure.json").exists())

    def final_callback(self, effect, reason):
        """Run the late callback INSIDE the last now(), after prefix encoding."""
        with self.prepared():
            original_encode, original_cancel = O.encoded, S._RecipientParent.cancel
            encoded, callbacks = [], []
            def encode(value):
                raw = original_encode(value)
                if type(value) is dict and value.get("scope") == S.RECIPIENT_PREFIX_SCOPE:
                    encoded.append(raw)
                return raw
            def cancel(parent):
                original_cancel(parent)
                if encoded:
                    callbacks.append(parent)
                    if len(callbacks) == 2:
                        self.assertTrue(parent.actual_owner().closed)
                        effect(parent)
            with patch.object(O, "encoded", encode), patch.object(S._RecipientParent, "cancel", cancel):
                self.failed(O.OriginError, reason)
            self.assertEqual(len(encoded), 1)
            self.assertEqual(len(callbacks), 2)
            self.assertTrue((self.session / "recipient-prefix-pending.json").exists())
            self.assertFalse((self.session / "recipient-prefix-failure.json").exists())

    def test_final_callback_cannot_consume_remaining_raw_read30(self):
        self.final_callback(lambda parent: setattr(self, "nanoseconds", parent.window.read_end), "PARENT_EXPIRED")
        self.closed_parent()

    def test_final_callback_cannot_consume_remaining_local_read30(self):
        def expire(parent):
            self.stack.enter_context(patch.object(S.time, "monotonic", return_value=parent.window.read_local))
        self.final_callback(expire, "LOCAL_EXPIRED")
        self.closed_parent()

    def test_success_shaped_late_row_is_not_learned_after_actual_close(self):
        with self.prepared():
            original, closes, resource_closes = S.Owner.close, [], []
            # No actual resource: assert no production close before the fixture's
            # independent test-only teardown visits retained synthetic pins.
            resource = SimpleNamespace(close=lambda: resource_closes.append("model-only"))
            added = {"label": "directory", "owner": resource, "attempted": True, "closed": True}
            def close(owner):
                original(owner)
                if type(owner.fence) is S._RecipientParentWindow:
                    closes.append(owner)
                    owner.resources.append(added)
            with patch.object(S.Owner, "close", close):
                self.failed(O.OriginError, "CLOSE_ROSTER")
            self.assertEqual(len(closes), 1)
            self.assertTrue(self.parent().unknown)
            self.assertTrue(any(pin.row is added and pin.resource is resource for pin in self.parent().bindings.seen))
            self.assertIn(closes[0], S.QUARANTINE)
            self.assertEqual(resource_closes, [])

    def test_handler_restore_cannot_append_a_success_shaped_closed_resource(self):
        with self.prepared():
            handlers, injected, resource_closes = {}, [], []
            resource = SimpleNamespace(close=lambda: resource_closes.append("model-only"))
            def get(number):
                return handlers.setdefault(number, object())
            def set_handler(number, handler):
                parent = self.parent()
                if handler is handlers.get(number) and parent.actual_owner().closed and not injected:
                    row = {"label": "writer", "owner": resource, "attempted": True, "closed": True}
                    injected.append(row)
                    parent.actual_owner().resources.append(row)
            with patch.object(S.signal, "getsignal", side_effect=get), patch.object(S.signal, "signal", side_effect=set_handler):
                self.failed(O.OriginError, "CLOSE_ROSTER")
            self.assertEqual(len(injected), 1)
            self.assertTrue(self.parent().unknown)
            self.assertTrue(any(pin.resource is resource for pin in self.parent().bindings.seen))
            self.assertEqual(resource_closes, [])

    def quarantine_on_final_callback(self, quarantine):
        sentinel = object()
        self.final_callback(lambda _parent: quarantine.append(sentinel), "PRIOR_UNKNOWN")
        self.assertIn(sentinel, quarantine)
        self.assertTrue(self.parent().unknown)
        self.assertIn(self.parent().actual_owner(), S.QUARANTINE)

    def test_final_callback_caller_quarantine_stays_unknown(self):
        self.quarantine_on_final_callback(S.QUARANTINE)

    def test_final_callback_query_quarantine_stays_unknown(self):
        self.quarantine_on_final_callback(S.query.QUARANTINE)

    def test_final_callback_windows_quarantine_stays_unknown(self):
        self.quarantine_on_final_callback(S.diagnostics._QUARANTINE)

    def test_cancellation_after_child_does_not_get_a_successful_prefix(self):
        with self.prepared():
            self.parent_after_child = lambda: self.parent().cancelled.append(signal.SIGTERM)
            self.failed(KeyboardInterrupt)
            self.assertTrue(self.parent_scopes[0].closed)
            self.assertTrue(self.parent().unknown)

    def test_no_canonical_cache_provider_http_or_public_caller(self):
        with self.prepared() as call, ExitStack() as guards:
            import hosted_dependency_cache as cache
            import hosted_dependency_seed_files as seed
            for target, name in ((cache, "export_snapshot"), (cache, "save_set"), (cache, "make_plan"),
                    (seed, "seed_home"), (S, "phase"), (O, "acquire")):
                guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_FOLLOWON_ACTION")))
            S.run_recipient_after_entry(call.new)
            self.assertEqual(list(inspect.signature(S.run_recipient_after_entry).parameters), ["transition"])
            self.assertNotIn("run_recipient_after_entry", inspect.getsource(S.main))
            self.assertNotIn("run_recipient_after_entry", inspect.getsource(S.adopt_originals))
            self.assertFalse((ROOT / ".github/workflows/dependency-cache-bootstrap.yml").exists())


def original_change(relative, *, after_pending=False):
    def test(self):
        with self.prepared():
            def mutate():
                path = self.session / relative
                raw = path.read_bytes()
                self.put(path, raw + b" ")
            if after_pending:
                original = S.Owner.write
                def write(owner, directory, name, *args, **kwargs):
                    raw = original(owner, directory, name, *args, **kwargs)
                    if type(owner.fence) is S._RecipientParentWindow and name == "recipient-prefix-pending.json":
                        mutate()
                    return raw
                with patch.object(S.Owner, "write", write):
                    self.failed()
            else:
                self.parent_scope_close = mutate
                self.failed()
            self.assertFalse(self.parent().result)
            self.assertTrue(self.parent_scopes[0].closed)
    return test


for label, relative in (("baseline", "recipient-validation/baseline.json"),
        ("native_birth", "recipient-validation/native-start.json"), ("start", "recipient-validation/start.json"),
        ("context", "recipient-context.json"), ("proposal", "allocation.json"),
        ("terminal", "recipient-validation/child-result.json"), ("ack", "recipient-validation/stdout.log"),
        ("query_session", "recipient-admission/session-result.json"),
        ("query_return", "recipient-validation/admission-return.json"), ("key_armor", "crypto/recipient.asc"),
        ("key_packets", "crypto/recipient.gpg")):
    setattr(ParentModels, "test_original_" + label + "_cannot_change_after_native_close", original_change(relative))
    setattr(ParentModels, "test_original_" + label + "_is_reread_after_prefix_retention", original_change(relative, after_pending=True))


def load_tests(_loader, _tests, _pattern):
    return unittest.TestSuite(ParentModels(name) for name in sorted(ParentModels.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
