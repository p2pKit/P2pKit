#!/usr/bin/env python3
"""New producer-parent offline models, NOT native/hosted/cache qualification.

Only historical fixture setup is reused. Entry/recipient/initializer/staging and
reservation are explicitly modeled CLOSED returns, never replayed executions.
The original reservation function object is retained, but its code is replaced
inside this isolated test process with a documented upstream model dispatcher.
Production exposes no such hook. This tests the successor's original-call/claim
bindings, not the authenticity or execution of those modeled predecessors.

The new parent/window/owner and tiny ordinary-UID POSIX files execute. Native
children, service queries, host/toolchain admission and command source assembly
are models; no subprocess, network, Java, Gradle, SDK, provider or download runs.
Actual synthetic canonical files pass through the unchanged record validator.
Neither those files nor these passes are original producer/stop/runtime evidence.
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import signal
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


H = load("producer_parent_reservation_setup", Path(__file__).with_name("hosted-cache-bootstrap-custody-test.py"))
C, B, F, O, NS = H.C, H.B, H.F, H.O, H.NS
ORIGINAL_MAKE_REQUEST = C.producer.make_request
OUTER = uuid.UUID("02658411-20ba-4c44-83dc-e3148cbaf1e9")


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


def _upstream_model_bridge(transition, *, initialize, stage, reserve):
    # Executed with the candidate module's globals after the test-only __code__
    # substitution. No candidate code/caller accepts this dispatcher in reality.
    return _producer_test_upstream(transition, initialize=initialize, stage=stage, reserve=reserve)


class ProducerParentModels(unittest.TestCase):
    def setUp(self):
        self.h = H.ReservationModels()
        self.addCleanup(self.h.doCleanups)
        self.h.setUp()
        self.f, self.stack = self.h.f, self.h.f.stack
        # Fresh original registry roots per method; never replace positive roots
        # with dictionaries that the captured original-call closure did not see.
        self.s = load("producer_parent_fresh_controller", ROOT / "scripts/run-hosted-cache-bootstrap.py")
        s = self.s
        self.stack.enter_context(patch.object(s, "ROOT", self.f.root))
        for module, name in ((s.query, "QUARANTINE"), (s.diagnostics, "_QUARANTINE")):
            self.stack.enter_context(patch.object(module, name, []))
        self.stack.enter_context(patch.object(s.producer, "make_request", ORIGINAL_MAKE_REQUEST))
        for module, name in ((C, "reserve_configuration"), (s, "_stage_after_initialization"),
                (s, "_initialize_claimed"), (s, "readmit_closed_entry")):
            self.stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_PREDECESSOR_REPLAY")))
        self.calls, self.old_parents, self.events, self.scopes = [], [], [], []
        self.parent = self.sequence = None
        self.on_read = self.on_admit = self.on_spawn = self.on_poll = self.on_drain = lambda *_args: None
        self.on_describe = lambda value: value
        self.poll_value, self.survivors = 0, []
        self.stdout_bytes, self.stderr_bytes = b"MODEL CONFIGURATION STDOUT\n", b"MODEL STDERR\n"
        self.callback = lambda: None
        self.upstream_error = None
        self.actual_admit = s._ProducerParent.admit
        self.stack.enter_context(patch.object(s._ProducerParent, "read_originals", lambda p: self.model_read(p)))
        self.stack.enter_context(patch.object(s._ProducerParent, "host", lambda p: self.model_host(p)))
        self.stack.enter_context(patch.object(s._ProducerParent, "admit", lambda p: self.model_admit(p)))
        self.stack.enter_context(patch.object(s.producer_command, "command_request", side_effect=self.model_descriptor))
        self.stack.enter_context(patch.object(s.processes, "make_scope", side_effect=self.model_scope))
        self.stack.enter_context(patch.object(s.time, "sleep", side_effect=lambda _seconds: None))
        self.stack.enter_context(patch.object(s.uuid, "uuid4", return_value=OUTER))
        original = s._recipient_after_entry
        self.assertEqual(original.__code__.co_freevars, ())
        self.stack.enter_context(patch.object(original, "__code__", _upstream_model_bridge.__code__))
        self.stack.enter_context(patch.object(s, "_producer_test_upstream", self.model_upstream, create=True))
        self.attempt = s._EntryAttempt(object(), ())
        self.attempt.state, self.attempt.admitted = "COMPLETE", self.f.admitted
        self.entry = s.NewEntryTransition(b"MODELED_ENTRY_NOT_EXECUTED", self.attempt, 1, 2, 3)
        self.attempt.result = self.entry
        self.addCleanup(self.close_tiny_test_pins)

    @staticmethod
    def poison(*_args, **_kwargs):
        raise AssertionError("NO_METHOD_ON_CLOSED_PREDECESSOR")

    def register(self, parent, registry, key, record):
        s = self.s
        registry[key] = record
        control = s._ParentControl(parent, registry, key, record)
        s._register_parent_control(control)
        s._PARENT_CONTROLS[id(parent)] = control

    def model_upstream(self, transition, *, initialize, stage, reserve):
        s, f = self.s, self.f
        self.calls.append((transition, initialize, stage, reserve))
        self.assertIs(transition, self.entry)
        self.assertEqual((initialize, stage, reserve), (True, True, True))
        self.assertTrue(all(type(x) is bool for x in (initialize, stage, reserve)))
        self.assertEqual(s._producer_frame(self.parent).state, "RESERVING")
        if self.upstream_error is not None:
            raise self.upstream_error
        s.require(id(transition) not in s._RECIPIENT_ATTEMPTS, "MODEL_ORIGINAL_RECIPIENT_ALREADY_CLAIMED")
        s._ENTRY_ATTEMPTS[id(self.attempt.transition)] = (self.attempt.transition, self.attempt, self.attempt.originals, None)
        recipient = s._RecipientParent(transition, ())
        recipient.state = "HANDED_OFF"
        recipient.records["start.json"] = O.encoded({"invocation": "c" * 32})
        self.register(recipient, s._RECIPIENT_ATTEMPTS, id(transition),
                      (transition, recipient, recipient.originals, None, True, True, True))
        initializer = s._InitializerParent(transition, ())
        initializer.state = "COMPLETE"
        initializer.records["start.json"] = O.encoded({"invocation": "d" * 32})
        initializer.result = s.InitializationPrefix(f.originals.initializer_closed_raw,
            b"MODELED_INITIALIZER_PENDING", (), f.originals.initializer_checked_ns)
        self.register(initializer, s._INITIALIZER_ATTEMPTS, id(recipient),
                      (transition, initializer, initializer.originals, None, object(), None))
        sequence = s._StagingSequence(initializer, initializer.result)
        row = (initializer, initializer.result, sequence)
        s._STAGING_ATTEMPTS[id(initializer)] = row
        s._claim_staging_sequence(sequence, s._STAGING_ATTEMPTS, row)
        registries = (s._ENTRY_ATTEMPTS, s._RECIPIENT_ATTEMPTS, s._INITIALIZER_ATTEMPTS, s._PARENT_CONTROLS,
            self.attempt, s._entry_attempt_record(self.attempt), s._parent_originals(initializer), s._parent_originals(recipient))
        graph = s._StagingClosedGraph.capture(initializer, initializer.result, registries)
        paths = (f.original, f.original.with_name(f.original.name + "-adoption"),
                 f.original.with_name(f.original.name + "-entry"), f.session)
        s._update_staging_sequence(sequence, graph=graph, originals=f.originals, original_pin=B._capture(f.originals),
            paths=paths, callbacks=(lambda: self.callback(),), registries=registries,
            plan=("dependency-stage", "empty-seed", "custody-prepare"), state="RUNNING")
        sequence.originals, sequence.state = f.originals, "RUNNING"
        previous = initializer.result
        for name in ("dependency-stage", "empty-seed", "custody-prepare"):
            previous = self.model_closed_phase(sequence, previous, name)
        s._update_staging_sequence(sequence, state="COMPLETE", result=previous)
        sequence.state, sequence.result = "COMPLETE", previous
        self.sequence, self.recipient, self.initializer = sequence, recipient, initializer
        self.f.ns, self.f.local = 1103 * NS, 502.0
        return previous

    def model_reservation_leaf(self, staged):
        f, h = self.f, self.h
        inputs = C._Inputs(f.originals, B._capture(f.originals), staged, C._capture_staged(staged))
        directory = f.session / "configuration-custody"
        directory.mkdir(mode=0o700)
        (directory / "retained").mkdir(mode=0o700)
        stage = F.record(staged.stage_leaf.raw)
        request = {"schema": 1, "scope": C.REQUEST_SCOPE, "binding": inputs.binding(),
            "predecessors": inputs.predecessors(), "inputs": stage["inputs"], "bootstrapInputs": stage["bootstrapInputs"],
            "custodyInputs": {name: F.digest((f.root / name).read_bytes()) for name in C.CUSTODY_INPUTS},
            "fileBindings": {name: stage["fileBindings"][name] for name in ("initializer-context", "canonical-context", "properties")},
            "directory": str(directory), "directories": {"custody": f.identity(directory), "retained": f.identity(directory / "retained")},
            "owner": {"job": f.canonical["id"], "productInvocation": H.RESERVED.hex, "sameHomeStopInvocation": H.RESERVED.hex},
            "evidenceDirectory": str(f.state / "evidence" / H.RESERVED.hex), "evidenceDirectoryOwnership": "NOT_CREATED_HERE",
            "purpose": C.producer.PURPOSE, "kind": "gradle", "requestedArgv": list(O.bootstrap.COMMAND),
            "producerScope": O.bootstrap.PRODUCER_SCOPE, "ancestorDomainChain": "NOT_SYNTHESIZED_OR_ADMITTED",
            "loader": "NOT_INSTALLED_BY_CONFIGURATION_RESERVATION", "sourceAdmission": "NOT_ATTESTED_HERE",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        request_raw = F.encoded(request)
        f.write(directory / "request.json", request_raw)
        binding = F._info_binding(F._info((directory / "request.json").stat()))
        value = {"schema": 1, "scope": C.SCOPE, "binding": inputs.binding(), "predecessors": inputs.predecessors(),
            "status": "RESERVED_CONFIGURATION_ONLY", "completed": True, "leafHandleClose": "KNOWN",
            "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False, "requestSha256": F.digest(request_raw),
            "requestBinding": binding, "window": h.leaf_window("custody-prepare", 1102 * NS, staged.raw, staged.checked_ns)}
        leaf = C.ReservationEvidence(F.encoded(value), request_raw, 1102 * NS + 20000, 501.0, 501.1)
        return leaf, self.s._CustodyRequestPin(str(directory), tuple(f.identity(directory)),
            tuple(f.identity(directory / "retained")), F.encoded(binding))

    def model_closed_phase(self, sequence, previous, name):
        s, f, supplied = self.s, self.f, self.h.staged
        staged = request_pin = None
        if name == "dependency-stage":
            leaf, raw = supplied.stage_leaf, supplied.stage_raw
            checked, local = F.record(supplied.raw)["predecessorCheckedNs"], 500.15
            result = s._StagingPhaseReturn(raw, leaf, checked, local)
            pin = (previous.raw, previous.checked_ns, f.originals.initializer_checked_local)
        elif name == "empty-seed":
            leaf, raw, checked, local = supplied.seed_leaf, supplied.raw, supplied.checked_ns, supplied.checked_local
            result = s.StagingPrefix(raw, previous.raw, previous.leaf, leaf, checked, local)
            pin = (previous.raw, previous.checked_ns, previous.checked_local)
        else:
            staged = C.StagedEvidence(previous.raw, previous.stage_raw, previous.stage_leaf, previous.seed_leaf,
                                      previous.checked_ns, previous.checked_local)
            leaf, request_pin = self.model_reservation_leaf(staged)
            raw = self.h.parent_record(leaf, previous.raw, previous.checked_ns)
            checked, local = leaf.checked_ns + 20000, 501.2
            result = s.ConfigurationCustodyPrefix(raw, previous, leaf, checked, local)
            pin = (previous.raw, previous.checked_ns, previous.checked_local)
        parent = s._StagingPhaseParent(sequence, name, previous)
        s._register_staging_phase(parent, pin, None, staged=staged)
        window_data = F.record(leaf.raw)["window"]
        first = O.clocks.Reading(f.clock, window_data["firstNs"])
        phase = B.PhaseStart(first, leaf.local_started)
        limits = s._StagingLimits(B._clock(first.clock), first.nanoseconds, window_data["softEndNs"],
            window_data["hardEndNs"], leaf.local_started, leaf.local_started + (90 if name == "empty-seed" else 120),
            leaf.local_started + 120)
        window, callback = s._StagingWindow(parent), self.poison
        s._update_staging_frame(parent, first=first, phase_start=phase, phase_pin=B._capture_phase(phase),
            limits=limits, window=window, callback=callback, last=checked, local_last=local)
        owner = s._StagingFileOwner(limits.local_hard, window, first=first, cancelled=callback)
        owner.closed = True  # Supplied CLOSED model, never an observed predecessor close.
        for method in ("end", "close", "close_one", "read", "acquire"):
            setattr(owner, method, self.poison)
        for method in ("now", "deadline"):
            object.__setattr__(window, method, self.poison)
        leaf_pin = (leaf.raw, leaf.request_raw, leaf.checked_ns, leaf.local_started, leaf.checked_local) if staged else B._capture_evidence(leaf)
        s._update_staging_frame(parent, owner=owner,
            owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end), state="COMPLETE",
            close_roster=(), leaf=leaf, leaf_pin=leaf_pin, result=result, request_pin=request_pin)
        parent.first, parent.phase_start, parent.window, parent.callback = first, phase, window, callback
        parent.owner, parent.state, parent.leaf, parent.result = owner, "COMPLETE", leaf, result
        self.old_parents.append(parent)
        return result

    def claim(self):
        self.parent = self.s._claim_producer(self.entry)
        return self.parent

    def reserve_model(self):
        p = self.claim()
        self.s._invoke_producer_reservation(p)
        self.s._capture_producer_predecessor(p)
        return p

    def live_model(self):
        """Supply a RUNNING start for unit controls, not the actual run's start."""
        s, p = self.s, self.reserve_model()
        first = O.clocks.Reading(self.f.clock, self.f.ns)
        ends = tuple(first.nanoseconds + seconds * NS for seconds in (600, 825, 870, 900))
        locals_ = tuple(self.f.local + seconds for seconds in (600, 825, 870, 900))
        limits = s._ProducerLimits(B._clock(self.f.clock), first.nanoseconds, self.f.local, ends, locals_)
        window, callback = s._ProducerWindow(p), p.cancel
        s._update_producer(p, first=first, last=first.nanoseconds, local_last=self.f.local, limits=limits, window=window,
            phases=(s._ProducerPhase("WORK", first.nanoseconds, self.f.local, ends[0], locals_[0]),))
        owner = s._ProducerOwner(locals_[3], window, first=first, cancelled=callback)
        s._update_producer(p, owner=owner, owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end, callback),
                           state="RUNNING")
        p.owner, p.window, p.state = owner, window, "RUNNING"
        p.check()
        return p

    def run_parent(self):
        s, original = self.s, self.s._claim_producer
        def capture(transition):
            self.parent = original(transition)
            return self.parent
        with patch.object(s, "_claim_producer", side_effect=capture):
            return s.configure_after_entry(self.entry)

    def frame(self):
        return self.s._producer_frame(self.parent)

    def model_host(self, parent):
        parent.live().end()
        self.events.append("modeled-host")
        return {"PATH": "/MODEL-NO-EXECUTABLES", "LANG": "C", "LC_ALL": "C"}

    def model_read(self, parent):
        parent.live().end()
        self.events.append("modeled-old-original-read")
        self.on_read(parent)
        parent.live().end()

    def model_admit(self, parent):
        parent.live().end()
        self.events.append("modeled-query-return")
        self.on_admit(parent)
        # The later original-result graph pins the CLOSED query supplier too.
        # Reuse the real admission parent's existing modeled supplier, rather
        # than inventing a query tuple or omitting it from production's graph.
        with patch.object(self.s.query, "NativeGitQueries", self.modeled_query_supplier()), \
                patch.object(self.s.bootstrap, "admit", return_value=self.f.admitted):
            self.actual_admit(parent)
        parent.live().end()

    def model_descriptor(self, admission, canonical, *, invocation, ancestor_invocations):
        request = ORIGINAL_MAKE_REQUEST(admission, canonical, invocation=invocation, ancestor_invocations=ancestor_invocations)
        return O.encoded({"requestBytes": O.encoded(request).decode("ascii"), "canonicalContextSha256": O.digest(canonical),
            "state": str(self.f.state), "argv": ["/MODEL-NEVER-EXECUTED/python", "-I", "-B", "-S", "MODEL_CONFIG_ONLY"]})

    def synthetic_canonical_files(self, pid):
        request = O.parse(O.parse(self.frame().descriptor)["requestBytes"].encode("ascii"))
        start = {name: request[name] for name in ("id", "purpose", "kind", "requestedArgv", "cwd", "wrapper", "host", "jobId",
                 "gradleHome", "ancestorInvocationIds", "evidenceDirectory")}
        start.update(schema=1, startedUtc="2026-09-18T00:00:00+00:00", controllerPid=pid, sourceBefore=None,
            sourceAfter=None, productExitCode=None, stopExitCode=None, finalExitCode=125, sourceUnchanged=False,
            ownedSurvivors=[], errors=[])
        def launch(argv, child_pid):
            return {"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv, "created": True,
                    "cwd": request["cwd"], "pid": child_pid, "shell": False, "executable": argv[0]}
        native = {"backend": "linux-proc-pidfd", "scope": "controlled-marker-inheriting-descendants", "job": request["jobId"],
            "invocation": request["id"], "startedIdentities": [], "discoveryErrors": [], "discoveryReconciliations": [],
            "launches": [launch(request["executedArgv"], pid + 1), launch(request["stopArgv"], pid + 2)]}
        receipt = {**start, "executedArgv": request["executedArgv"], "executedArgvSemantics": C.producer.SEMANTICS,
            "productLaunchIndex": 0, "productPid": pid + 1, "productStartedUtc": "2026-09-18T00:00:01+00:00",
            "productEndedUtc": "2026-09-18T00:00:02+00:00", "stopArgv": request["stopArgv"], "stopLaunchIndex": 1,
            "stopStartedUtc": "2026-09-18T00:00:02+00:00", "stopEndedUtc": "2026-09-18T00:00:03+00:00",
            "sourceBefore": self.f.canonical["source"], "sourceAfter": self.f.canonical["source"], "sourceUnchanged": True,
            "productExitCode": 0, "stopExitCode": 0, "finalExitCode": 0, "ownership": native, "reports": [],
            "endedUtc": "2026-09-18T00:00:04+00:00", "durationSeconds": 4.0}
        path = self.f.state / "evidence" / request["id"]
        path.mkdir(mode=0o700)
        self.f.write(self.f.state / "gradle.lock", b"MODELED CANONICAL LOCK; NO GRADLE RAN")
        for name, value in (("start", start), ("receipt", receipt)):
            self.f.write(path / (name + ".json"), (json.dumps(value, indent=2, sort_keys=True) + "\n").encode())

    def model_scope(self, job, invocation, state, home):
        test = self
        class Child:
            pid, stdout, stderr = os.getpid() + 100000, None, None
            def poll(self):
                test.events.append("modeled-poll")
                test.on_poll(self)
                return test.poll_value
        class Scope:
            name = "linux-proc-pidfd"
            baseline = {(101, 99)}
            closed = False
            launches = ()
            child = Child()
            def __init__(self):
                self.job, self.invocation, self.state, self.home = job, invocation, state, home
                self.close_count, self.drains = 0, []
            def _identity(self, pid):
                return {"pid": pid, "startTicks": 100, "live": True}
            def spawn(self, argv, cwd, env, *, stdout, stderr):
                test.events.append("modeled-spawn")
                self.argv, self.cwd, self.env = tuple(argv), cwd, dict(env)
                self.launches = ({"api": "subprocess.Popen", "requestedArgv": list(argv), "resolvedArgv": list(argv),
                    "created": True, "cwd": cwd, "pid": self.child.pid, "shell": False,
                    "executable": argv[0], "outputMode": "caller-owned-files"},)
                os.write(stdout.fileno(), test.stdout_bytes)
                os.write(stderr.fileno(), test.stderr_bytes)
                test.synthetic_canonical_files(self.child.pid)
                test.on_spawn(self)
                return self.child
            def description(self):
                value = {"backend": self.name, "scope": "controlled-marker-inheriting-descendants", "job": self.job,
                    "invocation": self.invocation, "launches": list(self.launches), "discoveryErrors": [],
                    "discoveryReconciliations": [], "startedIdentities": ([{"pid": self.child.pid, "startTicks": 200}]
                    if self.launches else [])}
                return test.on_describe(value)
            def discover(self):
                test.events.append("modeled-discover")
                return test.survivors
            def drain(self, *, grace, kill_wait, deadline):
                frame = test.frame()
                test.assertTrue(frame.local_last < deadline <= frame.phases[-1].local_end)
                self.drains.append((grace, kill_wait, deadline))
                test.events.append("modeled-drain")
                test.on_drain(self)
                return []
            def close(self):
                self.close_count += 1
                self.closed = True
                test.events.append("modeled-scope-close")
        scope = Scope()
        self.scopes.append(scope)
        return scope

    def close_tiny_test_pins(self):
        # Fixture-owned cleanup only. Never clear UNKNOWN in production or claim
        # those failed owners retired. These are tiny files, not native workers.
        if self.parent is not None:
            for pin in reversed(self.s._producer_frame(self.parent).resources):
                value = pin.value
                if isinstance(value, (F.PosixFile, F._PosixDirectory, self.s.query._PosixSink, self.s.query._PosixDirectory)):
                    if not value.closed:
                        try:
                            value.close()
                        except BaseException:
                            pass

    def failed(self, reason=None, *, kind=Exception):
        with (self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)) as caught:
            self.run_parent()
        self.assertEqual(self.frame().state, "FAILED")
        self.assertIsNone(self.frame().result)
        self.assertIs(self.frame().original, caught.exception)
        return caught.exception

    def test_whole_parent_uses_modeled_closed_prefix_but_real_new_owner_files_and_record_reader(self):
        value = self.run_parent()
        s, frame, record = self.s, self.frame(), O.parse(value.raw)
        self.assertIs(type(value), s.ConfigurationPrefix)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(tuple(p.name for p in self.old_parents), ("dependency-stage", "empty-seed", "custody-prepare"))
        self.assertTrue(all(frame.owner is not p.owner and frame.window is not p.window for p in self.old_parents))
        self.assertTrue(frame.owner.closed and all(row.attempted and row.closed for row in frame.resources))
        self.assertEqual(frame.handlers, frame.restored)
        self.assertTrue(frame.native.work_accepted and frame.native.retired)
        self.assertEqual((len(self.scopes), self.scopes[0].close_count), (1, 1))
        self.assertEqual(record["canonicalFourLogReportCollection"], "NOT_PERFORMED")
        self.assertEqual(record["dependencyPopulation"], "NOT_ATTESTED")
        self.assertEqual(record["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(record["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(record["exportSaveAuthority"], False)
        self.assertIs(record["nextPhaseAuthority"], False)
        self.assertFalse(frame.cancellation_attempted)
        self.assertEqual(tuple((self.h.directory / "retained").iterdir()), ())
        s._producer_predecessor_checked(self.parent)

    def test_original_result_pins_native_path_type_and_refuses_closed_path_mutations(self):
        self.run_parent()
        s, frame = self.s, self.frame()
        pin = s._producer_original_result(self.parent)
        directory = next(row[1] for row in frame.handles if row[0] == "initializer")
        self.assertTrue(directory.closed)
        self.assertIs(type(directory.path), type(self.f.session))
        self.assertIs(next(row[2] for row in frame.handles if row[0] == "initializer"), directory.path)
        self.assertTrue(all(type(row[2]) is type(row[1].path) and row[2] == row[1].path for row in frame.handles))
        # The real grammar supplies a PurePath; equal path values must not make
        # a later type replacement become the original native witness.
        pure = PurePosixPath(directory.path)
        self.assertEqual(pure, directory.path)
        self.assertIsNot(type(pure), type(directory.path))
        mutations = (("path", pure), ("path", directory.path.with_name("changed-model-path")),
                     ("identity", (directory.identity[0], directory.identity[1] + 1)))
        for field, value in mutations:
            with self.subTest(field=field, value_type=type(value).__name__), \
                    patch.object(directory, field, value), \
                    self.assertRaisesRegex(O.OriginError, "^BOOTSTRAP_STAGING_CLOSED_PATH_CHANGED$"):
                s._producer_original_result(self.parent)
        self.assertIs(s._producer_original_result(self.parent), pin)

    def test_original_claim_precedes_fixed_tuple7_intent_without_extending_initializer_tuple6(self):
        p = self.reserve_model()
        self.assertEqual(list(inspect.signature(self.s.configure_after_entry).parameters), ["transition"])
        recipient = self.s._RECIPIENT_ATTEMPTS[id(self.entry)]
        initializer = self.s._INITIALIZER_ATTEMPTS[id(self.recipient)]
        self.assertEqual((len(recipient), len(initializer)), (7, 6))
        self.assertEqual(recipient[4:], (True, True, True))
        self.assertIs(self.frame().reservation, self.sequence.result)
        with self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
            self.s.configure_after_entry(self.entry)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(p.state, "RESERVED")

    def test_prefix_or_constructor_cannot_supply_a_claim(self):
        s = self.s
        with self.assertRaisesRegex(O.OriginError, "NOT_CLAIMED"):
            s._ProducerParent(self.entry).check()
        for value in (object(), b"MODELED_PREFIX", replace(self.entry)._attempt):
            with self.subTest(kind=type(value).__name__), self.assertRaisesRegex(O.OriginError, "TRANSITION_KIND"):
                s.configure_after_entry(value)
        self.assertEqual(self.calls, [])

    def test_upstream_falsey_failure_consumes_claim_and_is_not_retried(self):
        self.upstream_error = FalseyFailure("MODELED_UPSTREAM_FAILURE")
        self.assertIs(self.failed(kind=FalseyFailure), self.upstream_error)
        with self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
            self.s.configure_after_entry(self.entry)
        self.assertEqual(len(self.calls), 1)
        self.assertIsNone(self.frame().owner)

    def test_copied_original_root_is_not_an_adoptable_registry(self):
        with patch.object(self.s, "_RECIPIENT_ATTEMPTS", dict(self.s._RECIPIENT_ATTEMPTS)), \
                self.assertRaisesRegex(O.OriginError, "ORIGINAL_CALL_CHANGED"):
            self.s.configure_after_entry(self.entry)
        self.assertEqual(self.calls, [])

    def test_replaced_original_callable_is_refused_before_invocation(self):
        with patch.object(self.s, "_recipient_after_entry", self.poison), \
                self.assertRaisesRegex(O.OriginError, "ORIGINAL_CALL_CHANGED"):
            self.s.configure_after_entry(self.entry)
        self.assertEqual(self.calls, [])

    def test_sequence_publication_and_all_three_closed_frames_are_pinned(self):
        self.reserve_model()
        self.sequence.__dict__ = dict(self.sequence.__dict__)
        with self.assertRaisesRegex(O.OriginError, "SEQUENCE_CHANGED"):
            self.parent.check()
        self.assertEqual(len(self.old_parents), 3)

    def test_equal_replacement_of_closed_private_phase_frame_is_refused(self):
        self.reserve_model()
        self.s._update_staging_frame(self.old_parents[0], state="COMPLETE")
        with self.assertRaisesRegex(O.OriginError, "PREDECESSOR_NOT_CLOSED"):
            self.parent.check()

    def test_predecessor_owner_never_reopened_even_on_new_parent_failure(self):
        first = FalseyFailure("MODELED_CURRENT_READ_FAILURE")
        self.on_read = lambda _p: (_ for _ in ()).throw(first)
        self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertTrue(all(p.state == "COMPLETE" and p.owner.closed for p in self.old_parents))
        self.assertTrue(self.frame().owner.closed)
        self.assertEqual(self.scopes, [])

    def test_actual_start_before_predecessor_raw_refuses_without_owner(self):
        p = self.reserve_model()
        self.f.ns = self.old_parents[-1].result.checked_ns - 2000
        with self.assertRaisesRegex(O.OriginError, "PREDECESSOR_CLOCK"):
            self.s._run_configuration_producer(p)
        self.assertIsNone(self.frame().owner)

    def test_actual_start_before_predecessor_local_refuses_without_owner(self):
        p = self.reserve_model()
        self.f.local = self.old_parents[-1].result.checked_local - .1
        with self.assertRaisesRegex(O.OriginError, "PREDECESSOR_CLOCK"):
            self.s._run_configuration_producer(p)
        self.assertIsNone(self.frame().owner)

    def test_actual_start_caps_remain_first600_825_870_900_inside_original_proposal(self):
        self.run_parent()
        frame = self.frame()
        proposal = self.f.proposal
        self.assertEqual(frame.limits.ends, tuple(min(frame.limits.first + seconds * NS,
            proposal["phaseFencesNs"][name], proposal["proposedJobEndNs"]) for name, seconds in
            zip(("producer-work", "producer-return", "producer-final", "producer-read"), (600, 825, 870, 900))))
        self.assertEqual(tuple(p.name for p in frame.phases), ("WORK", "RETURN", "FINAL", "READ"))
        for phase, seconds in zip(frame.phases[1:], (225, 45, 30)):
            self.assertLessEqual(phase.end, phase.started + seconds * NS)
            self.assertLessEqual(phase.local_end, phase.local_started + seconds)

    def test_return_and_final_shorten_from_actual_start_not_refreshed_global_allowances(self):
        p = self.live_model()
        self.f.ns += 10 * NS
        p.window.advance("RETURN")
        returned = self.frame().phases[-1]
        self.assertEqual(returned.end, returned.started + 225 * NS)
        self.f.ns += NS
        p.window.advance("FINAL")
        final = self.frame().phases[-1]
        self.assertEqual(final.end, final.started + 45 * NS)
        self.assertLess(final.end, self.frame().limits.ends[2])

    def test_work_equality_and_backward_raw_fail_before_new_file(self):
        p = self.live_model()
        end = self.frame().limits.ends[0]
        self.f.ns = end - 1000
        with self.assertRaisesRegex(O.OriginError, "PHASE_EXPIRED"):
            p.window.now()
        self.assertEqual(self.frame().last, end)
        self.f.ns = end - 2000
        with self.assertRaises(Exception):
            p.window.now()
        self.assertFalse(self.frame().resources)

    def test_local_highwater_survives_valid_raw_then_invalid_post_observation(self):
        p = self.live_model()
        before = self.frame().last
        with patch.object(self.s.time, "monotonic", side_effect=(self.f.local, float("nan"))), self.assertRaises(Exception):
            p.window.sample()
        self.assertGreater(self.frame().last, before)

    def test_return_start_failure_consumed_and_cannot_retry_same_phase(self):
        p = self.live_model()
        first = FalseyFailure("MODELED_RETURN_START")
        with patch.object(O.clocks, "observe", side_effect=first), self.assertRaises(FalseyFailure):
            p.window.advance("RETURN")
        self.assertIs(self.frame().original, first)
        self.assertEqual((self.frame().phases[-1].name, self.frame().phases[-1].end), ("RETURN", 0))
        with self.assertRaisesRegex(O.OriginError, "PHASE_REENTRY"):
            p.window.advance("RETURN")

    def test_generic_return_acquire_write_and_final_mode_have_no_escape_hatch(self):
        p = self.live_model()
        p.window.advance("RETURN")
        calls = []
        with self.assertRaises(Exception):
            p.owner.acquire("writer", lambda: calls.append("forbidden"))
        with self.assertRaisesRegex(O.OriginError, "NO_FINAL_ACQUISITION"):
            p.owner.open(self.f.session, final=True)
        self.assertEqual(calls, [])

    def test_first_returned_resource_is_registered_before_fallible_post_allocation_clock(self):
        p = self.live_model()
        class Tiny:
            count = 0
            def close(self):
                self.count += 1
        tiny = Tiny()
        def factory():
            self.f.ns = self.frame().limits.ends[0]
            return tiny
        with self.assertRaisesRegex(O.OriginError, "PHASE_EXPIRED"):
            p.owner.acquire("reader", factory)
        self.assertIs(self.frame().resources[-1].value, tiny)
        self.s._close_producer(p)
        self.assertEqual(tiny.count, 1)
        self.assertTrue(self.frame().resources[-1].closed)

    def test_prelaunch_nonempty_home_refuses_without_native_launch(self):
        self.on_read = lambda _p: self.f.write(self.f.home / "unexpected.txt", b"MODEL")
        self.failed("DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assertEqual(self.scopes, [])
        self.assertEqual((self.f.home / "unexpected.txt").read_bytes(), b"MODEL")

    def test_postlaunch_legitimate_home_additions_do_not_replay_properties_only_oracle(self):
        def warm(_scope):
            (self.f.home / "caches").mkdir(mode=0o700)
            self.f.write(self.f.home / "caches/model-data", b"MODEL NOT A QUALIFIED DEPENDENCY")
        self.on_spawn = warm
        value = self.run_parent()
        self.assertEqual(O.parse(value.raw)["dependencyPopulation"], "NOT_ATTESTED")
        self.assertFalse(tuple(self.f.restore.iterdir()))

    def test_postlaunch_properties_replacement_refuses_even_with_exit_zero(self):
        def change(_scope):
            path = self.f.home / "gradle.properties"
            raw = path.read_bytes()
            path.rename(self.f.base / "old-properties")
            self.f.write(path, raw)
        self.on_spawn = change
        self.failed("ORIGINAL_FILE_REPLACED")
        self.assertEqual(self.frame().native.exit_code, 0)
        self.assertTrue(self.frame().native.retired)

    def test_original_canonical_controller_must_equal_actual_modeled_outer_child_pid(self):
        def change(_scope):
            path = self.f.state / "evidence" / H.RESERVED.hex / "receipt.json"
            value = O.parse(path.read_bytes())
            value["controllerPid"] += 1
            self.f.write(path, O.encoded(value))
        self.on_spawn = change
        self.failed("CANONICAL_CONTROLLER_CHANGED")

    def test_reported_stop_failure_cannot_be_hidden_by_outer_zero(self):
        def change(_scope):
            path = self.f.state / "evidence" / H.RESERVED.hex / "receipt.json"
            value = O.parse(path.read_bytes())
            value["stopExitCode"] = 1
            self.f.write(path, O.encoded(value))
        self.on_spawn = change
        self.failed("CANONICAL_FAILED", kind=C.producer.ProducerError)

    def test_outer_readback_streams_positive_65536_byte_chunks_and_true_eof(self):
        self.stdout_bytes, self.stderr_bytes = b"x" * (2 * 65536 + 1), b""
        reads, original = [], F.PosixFile.read
        def read(reader, size):
            if reader.path.name in ("stdout.log", "stderr.log"):
                reads.append((reader.path.name, size))
            return original(reader, size)
        with patch.object(F.PosixFile, "read", read):
            result = self.run_parent()
        self.assertEqual([size for name, size in reads if name == "stdout.log"], [65536, 65536, 1, 1])
        self.assertEqual([size for name, size in reads if name == "stderr.log"], [1])
        captures = O.parse(result.raw)["outerCaptures"]
        self.assertEqual(captures["stdout"]["sha256"], O.digest(self.stdout_bytes))
        self.assertEqual(captures["stderr"]["bytes"], 0)

    def test_capture_shrink_is_latched_before_exit_zero_can_be_accepted(self):
        def shrink(_child):
            capture = self.frame().captures[0]
            os.ftruncate(capture.stream.fileno(), 0)
        self.on_poll = shrink
        self.failed("CAPTURE_SHRANK_OR_OVERFLOWED")
        self.assertFalse(self.frame().native.work_accepted)
        self.assertTrue(self.frame().native.retired)

    def test_capture_policy_constants_cannot_be_widened(self):
        self.reserve_model()
        with patch.object(self.s, "PRODUCER_STREAM_BYTES", 67174401), \
                self.assertRaisesRegex(O.OriginError, "CAPTURE_POLICY_CHANGED"):
            self.parent.check()

    def test_original_poll_failure_requests_one_same_file_cancellation_without_new_stop(self):
        first = FalseyFailure("MODELED_POLL_FAILURE")
        def once(_child):
            self.on_poll = lambda _value: None
            raise first
        self.on_poll = once
        self.assertIs(self.failed(kind=FalseyFailure), first)
        frame = self.frame()
        path = self.f.state / "cancellations" / (H.RESERVED.hex + ".json")
        raw = path.read_bytes()
        self.assertLessEqual(len(raw), 512)
        self.assertEqual(set(O.parse(raw)), {"schema", "id", "jobId", "requestedUtc"})
        self.assertEqual(O.parse(raw)["id"], H.RESERVED.hex)
        self.assertEqual(O.parse(raw)["jobId"], self.f.canonical["id"])
        self.assertEqual(raw, frame.cancellation_raw)
        self.assertEqual(tuple(row[0] for row in frame.cancellation_stamps), ("attempted", "readback-returned"))
        self.assertTrue(all(self.parent.resource(name).attempted and self.parent.resource(name).closed for name in
                            ("cancellation-writer", "cancellation-reader")))
        self.assertEqual(self.events.count("modeled-spawn"), 1)
        self.assertFalse(frame.native.work_accepted)
        self.assertEqual(frame.native.exit_code, 0)

    def test_partial_spawn_without_returned_child_never_invents_cancellation_target(self):
        first = FalseyFailure("MODELED_PARTIAL_SPAWN")
        self.on_spawn = lambda _scope: (_ for _ in ()).throw(first)
        self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertTrue(self.frame().native.launch_attempted)
        self.assertIsNone(self.frame().native.child)
        self.assertFalse(self.frame().cancellation_attempted)
        self.assertFalse(tuple((self.f.state / "cancellations").iterdir()))
        self.assertEqual(self.scopes[0].close_count, 1)

    def test_existing_cancellation_file_is_not_adopted_or_overwritten(self):
        first = FalseyFailure("MODELED_POLL_FAILURE")
        path = self.f.state / "cancellations" / (H.RESERVED.hex + ".json")
        def once(_child):
            self.on_poll = lambda _value: None
            self.f.write(path, b"MODELED PREEXISTING FILE")
            raise first
        self.on_poll = once
        self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertEqual(path.read_bytes(), b"MODELED PREEXISTING FILE")
        self.assertTrue(self.frame().cancellation_attempted)
        self.assertIsNone(self.parent.resource("cancellation-writer"))
        self.assertIsNone(self.parent.resource("cancellation-reader"))

    def test_replaced_cancellation_directory_cannot_redirect_known_original_request(self):
        first = FalseyFailure("MODELED_POLL_FAILURE")
        def once(_child):
            self.on_poll = lambda _value: None
            (self.f.state / "cancellations").rename(self.f.state / "old-cancellations")
            (self.f.state / "cancellations").mkdir(mode=0o700)
            raise first
        self.on_poll = once
        self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertFalse(tuple((self.f.state / "cancellations").iterdir()))
        self.assertFalse(tuple((self.f.state / "old-cancellations").iterdir()))
        self.assertEqual(self.scopes[0].close_count, 1)

    def test_work_expiry_cannot_become_success_after_late_zero_in_return(self):
        def late(_child):
            self.on_poll = lambda _value: None
            self.f.ns = self.frame().limits.ends[0]
        self.on_poll = late
        self.failed("PHASE_EXPIRED")
        self.assertEqual(self.frame().native.exit_code, 0)
        self.assertFalse(self.frame().native.work_accepted)
        self.assertTrue(self.frame().native.retired)

    def test_short_cancellation_write_keeps_first_failure_and_never_retries_or_reads_back(self):
        first, original, writes = FalseyFailure("MODELED_POLL_FAILURE"), F.PosixFile.write, []
        def once(_child):
            self.on_poll = lambda _value: None
            raise first
        def short(writer, raw):
            if writer.path.name == H.RESERVED.hex + ".json":
                writes.append(len(raw))
                original(writer, raw[:-1])
                return len(raw) - 1
            return original(writer, raw)
        self.on_poll = once
        with patch.object(F.PosixFile, "write", short):
            self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertEqual(len(writes), 1)
        self.assertIsNone(self.parent.resource("cancellation-reader"))
        self.assertEqual(self.scopes[0].close_count, 1)

    def test_alias_rejection_cannot_redirect_known_native_close(self):
        first = FalseyFailure("MODELED_ALIAS")
        alias = SimpleNamespace(close=lambda: self.fail("FOREIGN_CLOSE"))
        def once(_child):
            self.on_poll = lambda _value: None
            self.parent.owner = alias
            raise first
        self.on_poll = once
        self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertIsNot(self.frame().owner, alias)
        self.assertEqual(self.scopes[0].close_count, 1)

    def test_foreign_resource_row_latches_unknown_without_closing_replacement(self):
        p = self.live_model()
        class Tiny:
            count = 0
            def close(self):
                self.count += 1
        original, foreign = Tiny(), Tiny()
        p.owner.acquire("reader", lambda: original)
        p.owner.resources[0]["owner"] = foreign
        with self.assertRaisesRegex(O.OriginError, "ROSTER_CHANGED"):
            p.check()
        self.assertTrue(self.frame().unknown)
        p.owner.resources[0]["owner"] = original
        with self.assertRaises(Exception):
            p.owner.acquire("reader", lambda: self.fail("NO_NEW_ACQUISITION"))
        self.assertTrue(self.frame().foreign)
        self.assertEqual((original.count, foreign.count), (0, 0))

    def test_work_deadline_retains_initial_local_sample_before_any_following_observation(self):
        p = self.live_model()
        baseline, raised = self.f.local, self.f.local + 10
        with patch.object(self.s.time, "monotonic", side_effect=[raised] + [baseline] * 30), \
                self.assertRaisesRegex(O.OriginError, "LOCAL_BACKWARDS"):
            p.window.deadline(45)
        self.assertGreaterEqual(self.frame().local_last, raised)

    def test_cleanup_deadline_retains_initial_local_sample_before_any_following_observation(self):
        p = self.live_model()
        p.window.advance("RETURN")
        baseline, raised = self.f.local, self.f.local + 10
        with patch.object(self.s.time, "monotonic", side_effect=[raised] + [baseline] * 30), \
                self.assertRaisesRegex(O.OriginError, "LOCAL_BACKWARDS"):
            p.window.cleanup_deadline(45)
        self.assertGreaterEqual(self.frame().local_last, raised)

    def test_read_start_clock_failure_is_consumed_before_its_first_supplier(self):
        p = self.live_model()
        p.window.advance("RETURN")
        p.window.advance("FINAL")
        first = FalseyFailure("MODELED_READ_START_CLOCK")
        # This single phase-once control models already-closed writers only;
        # whole-parent controls above use actual new writer closure/readback.
        with patch.object(p, "writers_closed", return_value=None), \
                patch.object(O.clocks, "observe", side_effect=first), self.assertRaises(FalseyFailure):
            p.window.advance("READ")
        self.assertEqual(self.frame().phases[-1].name, "READ")
        self.assertEqual(self.frame().phases[-1].end, 0)
        self.assertIs(self.frame().original, first)
        with self.assertRaisesRegex(O.OriginError, "PHASE_REENTRY"):
            p.window.advance("READ")

    def test_missing_return_start_clock_cannot_recover_a_positive_final_drain_allowance(self):
        first, advance = FalseyFailure("MODELED_RETURN_START_CLOCK"), self.s._ProducerWindow.advance
        def failed_return(window, name):
            if name == "RETURN":
                with patch.object(O.clocks, "observe", side_effect=first):
                    return advance(window, name)
            return advance(window, name)
        with patch.object(self.s._ProducerWindow, "advance", failed_return):
            self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertEqual(self.scopes[0].drains, [])
        self.assertFalse(self.frame().native.drain_attempted)
        self.assertEqual(self.scopes[0].close_count, 1)
        self.assertFalse(self.frame().result)

    def test_original_drain_local_end_rejects_late_empty_result_with_timely_raw(self):
        def late(scope):
            self.f.local = scope.drains[-1][2]
        self.on_drain = late
        self.failed()
        self.assertFalse(self.frame().native.retired)
        self.assertTrue(self.frame().unknown)
        self.assertEqual(self.scopes[0].close_count, 1)
        self.assertFalse(any(capture.readback is not None for capture in self.frame().captures))

    def test_original_drain_raw_end_rejects_late_empty_result_with_timely_local(self):
        self.on_drain = lambda _scope: setattr(self.f, "ns", self.frame().phases[-1].end)
        self.failed("PHASE_EXPIRED")
        self.assertFalse(self.frame().native.retired)
        self.assertTrue(self.frame().unknown)
        self.assertEqual(self.scopes[0].close_count, 1)

    def test_late_scope_close_preserves_actual_once_close_but_not_retirement(self):
        close = self.s._ProducerParent.close_resource
        def late(parent, pin):
            result = close(parent, pin)
            if pin.label == "native-scope":
                self.f.local = self.scopes[0].drains[-1][2]
            return result
        with patch.object(self.s._ProducerParent, "close_resource", late):
            self.failed()
        self.assertEqual(self.scopes[0].close_count, 1)
        self.assertTrue(self.parent.resource("native-scope").closed)
        self.assertFalse(self.frame().native.retired)
        self.assertTrue(self.frame().unknown)

    def saved_end_crossing(self, *, after_close):
        s = self.s
        cleanup, close, observe = s._ProducerWindow.cleanup_deadline, s._ProducerParent.close_resource, O.clocks.observe
        state = {"converting": False, "shortened": False, "armed": False, "crossed": False}
        def reading():
            if state["converting"] and not state["shortened"]:
                # Real converter, modeled one-second RAW observation cost.
                self.f.local += 1
                self.f.ns += NS
                state["shortened"] = True
            if state["armed"]:
                state.update(armed=False, crossed=True)
                self.f.local = state["end"]
            return observe()
        def converted(window, maximum):
            state["converting"] = True
            try:
                end = cleanup(window, maximum)
            finally:
                state["converting"] = False
            state["end"] = end
            self.assertLess(end, self.frame().phases[-1].local_end)
            return end
        def closed(parent, pin):
            result = close(parent, pin)
            if after_close and pin.label == "native-scope" and not state["crossed"]:
                state["armed"] = True
            return result
        if not after_close:
            self.on_drain = lambda _scope: state.update(armed=True)
        failure = None
        with patch.object(s._ProducerWindow, "cleanup_deadline", converted), \
                patch.object(s._ProducerParent, "close_resource", closed), \
                patch.object(O.clocks, "observe", side_effect=reading):
            try:
                self.run_parent()
            except BaseException as error:
                failure = error
        self.assertTrue(state["shortened"] and state["crossed"])
        self.assertFalse(self.frame().native.retired)
        self.assertTrue(self.frame().unknown)
        self.assertEqual(self.scopes[0].close_count, 1)
        self.assertFalse(any(capture.readback is not None for capture in self.frame().captures))
        self.assertIsInstance(failure, s.posix.EvidenceError)
        self.assertIs(self.frame().original, failure)
        self.assertEqual(self.frame().state, "FAILED")

    def test_postdrain_raw_sample_cannot_cross_saved_local_end_inside_broader_phase(self):
        self.saved_end_crossing(after_close=False)

    def test_postclose_raw_sample_cannot_cross_saved_local_end_inside_broader_phase(self):
        self.saved_end_crossing(after_close=True)

    def test_same_byte_canonical_replacement_after_first_read_cannot_supply_original_custody(self):
        reread, replaced = self.s._ProducerParent.reread, []
        def swap(parent):
            if not replaced:
                path = self.f.state / "evidence" / H.RESERVED.hex / "start.json"
                raw = path.read_bytes()
                path.rename(self.f.base / "old-canonical-start")
                self.f.write(path, raw)
                replaced.append(True)
            return reread(parent)
        with patch.object(self.s._ProducerParent, "reread", swap):
            self.failed("ORIGINAL_FILE_REPLACED")
        self.assertEqual(replaced, [True])

    def test_same_byte_outer_stream_replacement_after_close_is_rejected(self):
        read, replaced = self.s._ProducerParent.read_capture, []
        def swap(parent, capture):
            if not replaced:
                path = parent.handles["phase"].path / (capture.name + ".log")
                raw = path.read_bytes()
                path.rename(self.f.base / "old-outer-stream")
                self.f.write(path, raw)
                replaced.append(True)
            return read(parent, capture)
        with patch.object(self.s._ProducerParent, "read_capture", swap):
            self.failed("CLOSED_CAPTURE_REPLACED")
        self.assertEqual(replaced, [True])

    def modeled_query_supplier(self, *, late=False, failure=None):
        test = self
        class Queries:
            unknown, closed = False, False
            def __init__(self, root, path, *, check_cancel, owner_deadlines):
                test.assertEqual(root, test.f.root)
                test.assertEqual(test.frame().phases[-1].name, "WORK")
                self.path, self.cancel, self.deadlines = path, check_cancel, owner_deadlines
                path.mkdir(mode=0o700)
                test.events.append("modeled-query-created")
            def native_host_matches_actions(self):
                self.cancel()
            def retain_admission(self, admitted):
                test.assertIs(admitted, test.f.admitted)
                for name, raw in (("admission.json", admitted.record), ("original-event.json", admitted.original_event),
                        ("original-policy.json", admitted.original_policy), ("recipient-public.asc", admitted.public_key)):
                    test.f.write(self.path / name, raw)
            def _finalize(self, original):
                test.assertIsNone(original)
                self.closed = True
                test.events.append("modeled-query-finalized")
                test.f.write(self.path / "session-result.json", O.encoded({"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
                    "job": "f" * 32, "queries": [], "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN",
                    "firstError": None, "errors": [], "readbacks": []}))
                if late:
                    test.f.ns = test.frame().query[4]
                if failure is not None:
                    raise failure
        return Queries

    def test_actual_admission_parent_retains_modeled_query_finalizer_return_inside_work(self):
        with patch.object(self.s._ProducerParent, "admit", self.actual_admit), \
                patch.object(self.s.query, "NativeGitQueries", self.modeled_query_supplier()), \
                patch.object(self.s.bootstrap, "admit", return_value=self.f.admitted):
            self.run_parent()
        frame = self.frame()
        self.assertTrue(frame.query_attempted and frame.query_returned[0])
        self.assertLess(frame.query_returned[1], frame.limits.ends[0])
        self.assertIn("admission/session-result.json", self.parent.records)
        self.assertIn("admission-return", self.parent.records)
        self.assertEqual(self.events.count("modeled-query-created"), 1)
        self.assertEqual(self.events.count("modeled-query-finalized"), 1)

    def test_query_finalizer_late_return_cannot_become_admission_or_native_launch(self):
        with patch.object(self.s._ProducerParent, "admit", self.actual_admit), \
                patch.object(self.s.query, "NativeGitQueries", self.modeled_query_supplier(late=True)), \
                patch.object(self.s.bootstrap, "admit", return_value=self.f.admitted):
            self.failed("PHASE_EXPIRED")
        self.assertTrue(self.frame().query_returned[0])
        self.assertIsNone(self.frame().query_returned[1])
        self.assertNotIn("admission-return", self.parent.records)
        self.assertEqual(self.scopes, [])

    def test_query_finalizer_falsey_failure_is_preserved_without_native_launch(self):
        first = FalseyFailure("MODELED_QUERY_FINALIZER")
        with patch.object(self.s._ProducerParent, "admit", self.actual_admit), \
                patch.object(self.s.query, "NativeGitQueries", self.modeled_query_supplier(failure=first)), \
                patch.object(self.s.bootstrap, "admit", return_value=self.f.admitted):
            self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertFalse(self.frame().query_returned[0])
        self.assertEqual(self.scopes, [])

    def reader_model(self):
        """Actual new view over explicitly modeled, never-executed old history.

        The two dispatch regressions below execute the unchanged helper entries
        through their real next record guard. They do NOT replay preparation,
        supply a complete original history or execute read_originals end to end.
        """
        first = O.clocks.Reading(self.f.clock, 1000 * NS)
        past = O.Fence(O.prelude(first), minimum=first.nanoseconds, cancelled=self.poison)
        past.now = past.deadline = self.poison
        self.attempt.transition = SimpleNamespace(_fence=past, _limits=(None,) * 8 + (first,))
        parent = self.live_model()
        return self.s._ProducerOriginalReader(parent), past, first

    def test_exact_producer_reader_reaches_unchanged_prepared_handoff_guard(self):
        reader, _past, _first = self.reader_model()
        with patch.object(self.s, "handoff_record", wraps=self.s.handoff_record) as parse_handoff, \
                self.assertRaisesRegex(O.OriginError, "^BOOTSTRAP_ORIGINAL_HANDOFF$"):
            self.s._read_prepared(reader, None, b"{}", b"{}")
        parse_handoff.assert_called_once_with(b"{}", self.f.clock)
        self.assertEqual(self.frame().resources, ())
        self.assertIsNone(self.frame().original)

    def test_exact_producer_reader_reaches_unchanged_chain_record_guard(self):
        reader, _past, _first = self.reader_model()
        before = self.f.ns
        with self.assertRaisesRegex(O.OriginError, "^BOOTSTRAP_ORIGINAL_PHASE_FILES$"):
            self.s._read_chain(reader, None, b"{}", self.f.admitted, {}, {}, {}, final=False)
        self.assertEqual(self.f.ns, before)
        self.assertEqual(self.frame().resources, ())

    def test_reader_dispatch_still_rejects_foreign_and_subclass_before_callbacks(self):
        reader, _past, _first = self.reader_model()
        class ForeignReader(self.s._ProducerOriginalReader):
            pass
        foreign = (object(), SimpleNamespace(first=reader.first, checked=self.poison), ForeignReader(self.parent))
        for value in foreign:
            with self.subTest(kind=type(value).__name__), \
                    patch.object(self.s._ProducerOriginalReader, "checked", self.poison):
                with self.assertRaisesRegex(O.OriginError, "^BOOTSTRAP_ADOPTION_READER$"):
                    self.s._read_prepared(value, None, b"{}", b"{}")
                with self.assertRaisesRegex(O.OriginError, "^BOOTSTRAP_ORIGINAL_READER_KIND$"):
                    self.s._read_chain(value, None, b"{}", self.f.admitted, {}, {}, {}, final=False)
        self.assertEqual(self.frame().resources, ())

    def test_reader_dispatch_checks_original_view_bindings_before_record_access(self):
        reader, _past, _first = self.reader_model()
        for name, replacement in (("owner", object()), ("current", object()), ("first", replace(reader.first))):
            original = getattr(reader, name)
            object.__setattr__(reader, name, replacement)
            try:
                with self.subTest(field=name), patch.object(self.s, "handoff_record", self.poison):
                    with self.assertRaisesRegex(O.OriginError, "^BOOTSTRAP_PRODUCER_READER_CHANGED$"):
                        self.s._read_prepared(reader, None, b"{}", b"{}")
                    with self.assertRaisesRegex(O.OriginError, "^BOOTSTRAP_PRODUCER_READER_CHANGED$"):
                        self.s._read_chain(reader, None, b"{}", self.f.admitted, {}, {}, {}, final=False)
            finally:
                object.__setattr__(reader, name, original)
        self.assertIs(reader.checked(), reader)
        self.assertEqual(self.frame().resources, ())

    def test_new_reader_keeps_historical_first_without_observing_closed_prelude(self):
        reader, past, first = self.reader_model()
        original = (past.raw, past.first, past.work, past.final, past.last)
        self.assertIs(reader.owner, self.parent.owner)
        self.assertIs(reader.current, self.parent.window)
        self.assertIs(reader.first, first)
        self.assertIsNot(reader.first, self.parent.owner.first)
        self.assertFalse(hasattr(reader.past, "last"))
        self.f.ns = 1200 * NS  # Historical120 expired; current WORK600 remains live.
        observed = reader.observe(final=False, minimum=self.frame().last)
        self.assertEqual(observed, self.frame().last)
        self.assertGreater(observed, past.final)
        self.assertEqual((past.raw, past.first, past.work, past.final, past.last), original)
        self.assertEqual(self.frame().resources, ())

    def foreign_call(self, calls):
        def forbidden(name):
            def operation(*_args, **_kwargs):
                calls.append(name)
                raise O.OriginError("MODELED_FOREIGN_CALL_MUST_NOT_RUN")
            return operation
        return SimpleNamespace(**{name: forbidden(name) for name in
            ("check", "cleanup_bindings", "live", "cancel", "error")})

    def refused_window_alias(self, operation):
        parent = self.live_model()
        window, calls = parent.window, []
        object.__setattr__(window, "call", self.foreign_call(calls))
        try:
            with self.assertRaises(O.OriginError):
                operation(window)
            self.assertEqual(calls, [], "A rejected publication must not dispatch a foreign method")
        finally:
            object.__setattr__(window, "call", parent)
        self.assertIs(self.s._producer_window_frame(window).call, parent)

    def test_window_strict_entry_refuses_call_alias_before_foreign_method(self):
        self.refused_window_alias(lambda window: window.sample())

    def test_window_cleanup_entry_refuses_call_alias_before_foreign_method(self):
        self.refused_window_alias(lambda window: window.sample(cleanup=True))

    def test_window_deadline_entry_refuses_call_alias_before_foreign_method(self):
        self.refused_window_alias(lambda window: window.deadline(45))

    def test_original_owner_close_fence_does_not_dispatch_window_call_alias(self):
        parent = self.live_model()
        window, owner, calls = parent.window, parent.owner, []
        object.__setattr__(window, "call", self.foreign_call(calls))
        try:
            owner.close_fence()
            self.assertEqual(calls, [])
            self.assertIsInstance(self.frame().original, O.OriginError)
            self.assertIs(self.frame().owner, owner)
        finally:
            object.__setattr__(window, "call", parent)

    def other_claimed_parent(self):
        # A second original intent, not an admitted/running predecessor or a
        # replacement dictionary. No upstream operation is invoked for it.
        attempt = self.s._EntryAttempt(object(), ())
        transition = self.s.NewEntryTransition(b"SECOND_MODELED_INTENT", attempt, 1, 2, 3)
        return self.s._claim_producer(transition)

    def window_supplier_alias(self, *, raw=False, deadline=False):
        parent = self.live_model()
        window, other = parent.window, self.other_claimed_parent()
        other_before = self.s._producer_frame(other)
        raised_local, raised_raw = self.f.local + 10, self.f.ns + 10 * NS
        def supply():
            object.__setattr__(window, "call", other)
            return O.clocks.Reading(self.f.clock, raised_raw) if raw else raised_local
        error = None
        module, name = (O.clocks, "observe") if raw else (self.s.time, "monotonic")
        try:
            with patch.object(module, name, side_effect=supply):
                try:
                    window.deadline(45) if deadline else window._raw_local(strict=False)
                except BaseException as caught:
                    error = caught
            original = self.s._producer_frame(parent)
            self.assertGreaterEqual(original.last if raw else original.local_last,
                                    raised_raw if raw else raised_local)
            self.assertIs(self.s._producer_frame(other), other_before,
                          "Original returned samples cannot update a second claimed call")
            self.assertIsInstance(error, O.OriginError)
        finally:
            object.__setattr__(window, "call", parent)

    def test_local_supplier_alias_keeps_original_sample_without_writing_second_call(self):
        self.window_supplier_alias()

    def test_deadline_local_supplier_alias_keeps_original_sample_without_writing_second_call(self):
        self.window_supplier_alias(deadline=True)

    def test_raw_supplier_alias_keeps_original_sample_without_writing_second_call(self):
        self.window_supplier_alias(raw=True)

    def test_window_call_alias_preserves_first_failure_and_original_native_close(self):
        first, calls = FalseyFailure("MODELED_WINDOW_ALIAS"), []
        def once(_child):
            self.on_poll = lambda _value: None
            object.__setattr__(self.parent.window, "call", self.foreign_call(calls))
            raise first
        self.on_poll = once
        self.assertIs(self.failed(kind=FalseyFailure), first)
        self.assertEqual(calls, [])
        self.assertEqual(self.scopes[0].close_count, 1)
        self.assertIsNone(self.frame().result)

    def test_reader_constructor_refuses_foreign_parent_before_callback(self):
        self.reader_model()
        calls = []
        with self.assertRaises(O.OriginError):
            self.s._ProducerOriginalReader(self.foreign_call(calls))
        self.assertEqual(calls, [])

    def test_reader_constructor_refuses_subclass_parent_before_callback(self):
        self.reader_model()
        calls = []
        class ForeignParent(self.s._ProducerParent):
            def check(self):
                calls.append("subclass-check")
                raise O.OriginError("MODELED_SUBCLASS_MUST_NOT_RUN")
        with self.assertRaises(O.OriginError):
            self.s._ProducerOriginalReader(ForeignParent(self.entry))
        self.assertEqual(calls, [])

    def test_reader_published_call_refuses_foreign_parent_before_callback(self):
        reader, _past, _first = self.reader_model()
        calls = []
        object.__setattr__(reader, "call", self.foreign_call(calls))
        with self.assertRaises(O.OriginError):
            reader.checked()
        self.assertEqual(calls, [])

    def test_reader_published_call_refuses_other_claimed_parent_before_callback(self):
        reader, _past, _first = self.reader_model()
        other, calls = self.other_claimed_parent(), []
        def forbidden():
            calls.append("other-check")
            raise O.OriginError("MODELED_OTHER_CLAIM_MUST_NOT_RUN")
        object.__setattr__(reader, "call", other)
        with patch.object(other, "check", side_effect=forbidden), self.assertRaises(O.OriginError):
            reader.checked()
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
