#!/usr/bin/env python3
"""New parent + leaf offline controls; NOT native/initializer/provider evidence.

The new same-call staging parents, historical-original readers, real POSIX
Owner/files and both unchanged leaves execute. Preparation/service/query/clock
boundaries are models. The recipient and canonical initializer predecessors
are explicitly MODELED closed typed graphs with tiny files: neither native
recipient/initialize() nor generated argv is executed. Two nonfunctional JDK
fixtures are only inspected. No inherited historical test method is selected.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
import importlib.util
import inspect
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("bootstrap_staging_parent_original_fixtures",
    Path(__file__).with_name("hosted-cache-bootstrap-readmission-test.py"))
R = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = R
spec.loader.exec_module(R)
S, O, B = R.S, R.O, R.S.staging


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class IntentProbe(RuntimeError):
    pass


class ParentModels(R.ReadmissionModels):
    def setUp(self):
        super().setUp()
        # Executable source stays in the root-owned read-only export. The
        # actual public-source reader requires its data root to belong to this
        # ordinary UID, just like a hosted checkout. Keep that root outside the
        # modeled RUNNER_TEMP, copy only the closed binding roster, and use tiny
        # synthetic dependency metadata. No copied script/argv is executed.
        source = ROOT
        source_temp = tempfile.TemporaryDirectory(prefix="bootstrap-staging-source-model-")
        self.addCleanup(source_temp.cleanup)
        self.source = Path(source_temp.name)
        components = "".join('<component group="org.fixture" name="' + name + '" version="1.0">' +
            '<artifact name="' + name + '.jar"><sha256 value="' + B.files.digest(name.encode()) +
            '"/></artifact></component>' for name in ("First", "Second"))
        metadata = ('<?xml version="1.0" encoding="UTF-8"?><verification-metadata xmlns="' +
            B.files.authority.NAMESPACE + '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" ' +
            'xsi:schemaLocation="' + B.files.authority.SCHEMA_LOCATION +
            '"><configuration><verify-metadata>true</verify-metadata>' +
            '<verify-signatures>false</verify-signatures></configuration><components>' + components +
            '</components></verification-metadata>').encode()
        for name in sorted(set((*B.files.INPUTS, *B.BOOTSTRAP_INPUTS))):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            path.write_bytes(metadata if name == B.files.INPUTS[0] else (source / name).read_bytes())
            path.chmod(0o644)
        for module in (sys.modules[__name__], R, R.C, R.C.E, R.C.E.H, R.C.E.H.M, S, B, S.canonical):
            self.stack.enter_context(patch.object(module, "ROOT", self.source))
        os.environ["GITHUB_WORKSPACE"] = str(self.source)
        for name in ("_RECIPIENT_ATTEMPTS", "_INITIALIZER_ATTEMPTS", "_PARENT_CONTROLS", "_STAGING_ATTEMPTS"):
            self.stack.enter_context(patch.object(S, name, {}))
        for module, name in ((S, "QUARANTINE"), (S.query, "QUARANTINE"), (S.diagnostics, "_QUARANTINE")):
            self.stack.enter_context(patch.object(module, name, []))
        self.local_override = None
        self.stack.enter_context(patch.object(S.time, "monotonic", side_effect=lambda:
            self.nanoseconds / O.NS if self.local_override is None else self.local_override))
        self.query_events, self.read_events, self.modeled_owners = [], [], []
        self.query_before = self.query_after = lambda parent: None
        self.after_original_read = lambda parent: None
        self.init = self.recipient = self.current = None
        for name in ("JAVA_HOME", "P2PKIT_AUDIT_JDK21"):
            home = self.base / name
            (home / "bin").mkdir(parents=True, mode=0o700)
            for binary in ("java", "javac"):
                path = home / "bin" / binary
                path.write_bytes(b"MODEL_ONLY_NEVER_EXECUTE\n")
                path.chmod(0o700)
            os.environ[name] = str(home)
        self.addCleanup(self.close_fixture_pins)

    def reset_models(self):
        # close_fixture_pins owns only this test's real tiny descriptors. Never
        # let the historical fixture dispatch a deliberately substituted row.
        S.QUARANTINE.clear()

    def close_fixture_pins(self):
        # Fixture-owned POSIX pins only. Never reclassifies a production UNKNOWN.
        owners = list(self.modeled_owners)
        for row in S._STAGING_ATTEMPTS.values():
            sequence = row[2]
            for parent in S._staging_sequence_frame(sequence).phases:
                frame = S._staging_frame(parent)
                for pin in reversed(frame.resources):
                    resource = pin[2]
                    if isinstance(resource, (B.files.PosixFile, B.files._PosixDirectory, S.query._PosixDirectory)):
                        if not resource.closed:
                            try:
                                resource.close()
                            except BaseException:
                                pass
                for supplier, _pair, _work, _final in frame.queries:
                    if hasattr(supplier, "owner"):
                        owners.append(supplier.owner)
        for owner in owners:
            for row in reversed(owner.resources):
                resource = row["owner"]
                if hasattr(resource, "closed") and not resource.closed:
                    try:
                        resource.close()
                    except BaseException:
                        pass

    @staticmethod
    def identity(path):
        info = path.stat()
        return [info.st_dev, info.st_ino]

    def model_window(self, kind, call, first, *, initializer):
        """Typed data model only; not an executed recipient/initializer window."""
        window = object.__new__(kind)
        proposal = O.parse(call.transition._attempt.transition.proposal_raw)
        names = ("canonical-init", "canonical-init-final", "canonical-init-read") if initializer else (
            "recipient-validation", "recipient-final", "recipient-read")
        seconds = (120, 165, 195) if initializer else (240, 285, 315)
        work, native, end = (min(first.nanoseconds + count * O.NS, proposal["phaseFencesNs"][name])
                            for name, count in zip(names, seconds))
        final_start, read_start = first.nanoseconds + O.NS, first.nanoseconds + 2 * O.NS
        values = dict(call=call, clock=first.clock, first=first.nanoseconds, work=work, native_end=native,
            prefix_end=end, work_local=work / O.NS, native_local=native / O.NS, local_end=end / O.NS,
            last=first.nanoseconds + 3 * O.NS, local_last=first.nanoseconds / O.NS + 3,
            phase="READ", final_started=final_start, final_local_start=final_start / O.NS,
            final=min(native, final_start + 45 * O.NS), final_local=min(native, final_start + 45 * O.NS) / O.NS,
            read_started=read_start, read_local_start=read_start / O.NS, read_attempted=True,
            read_end=min(end, read_start + 30 * O.NS), read_local=min(end, read_start + 30 * O.NS) / O.NS)
        for key, value in values.items():
            object.__setattr__(window, key, value)
        return window

    def model_parent(self, kind, transition, pins, path, *, initializer):
        """Real tiny file Owner closes; claimed native execution is NOT run."""
        call = kind(transition, pins)
        first = O.clocks.Reading(self.clock, self.nanoseconds)
        call.first, call.local_start, call.callback = first, self.nanoseconds / O.NS, lambda: None
        window = self.model_window(S._InitializerWindow if initializer else S._RecipientParentWindow,
                                   call, first, initializer=initializer)
        owner = S.Owner(window.local_end)  # File fixture only, not the modeled native window.
        self.modeled_owners.append(owner)
        call.handles["session"] = owner.new(path)
        names = ("canonical-init", "control-home", "temporary") if initializer else S.RECIPIENT_DIRECTORIES
        for name in names:
            call.handles[name] = owner.child(call.handles["session"], name, create=True)
        call.identities = {name: self.identity(directory.path) for name, directory in call.handles.items()}
        call.owner, call.window = owner, window
        return call

    def model_file(self, call, key, directory, name, value, maximum=S.LIMIT):
        raw = value if type(value) is bytes else O.encoded(value)
        call.owner.write(directory, name, raw)
        call.records[key] = raw
        call._model_files.append((key, directory, directory.path, tuple(directory.identity), name, maximum, raw))
        return raw

    def finish_model_parent(self, call, *, initialize, stage, handoff=None, inputs=None):
        owner, window = call.owner, call.window
        # Close REAL fixture files before supplying a MODEL of the old parent.
        owner.close()
        owner.fence, owner.first, owner.cancelled = window, call.first, call.callback
        owner.early_last = call.first.nanoseconds
        bound = S._RecipientParentBindings(owner, window, call.first, call.callback, call.local_start, owner.local_end,
            owner.admissions, owner.resources, owner.errors, window_state=[window.phase_state()],
            observations=[window.last, window.local_last], files=list(call._model_files),
            close_roster=[tuple((row, row["label"], row["owner"]) for row in owner.resources)])
        bound.seen.extend(S._RecipientResource(row, row["label"], row["owner"], True, True) for row in owner.resources)
        call.bindings, call.errors = bound, owner.errors
        call.native_retired = call.captures_retired = call.child_accepted = True
        if type(call) is S._RecipientParent:
            call.state = "HANDED_OFF"
            registry, key = S._RECIPIENT_ATTEMPTS, id(call.transition)
            record = (call.transition, call, call.originals, bound, initialize, stage)
            control = S._ParentControl(call, registry, key, record)
        else:
            call.state = "COMPLETE"
            bound.initialization.append(inputs)
            inputs_pin = (inputs, (inputs.request_raw, inputs.interpreter, inputs.environment, inputs.homes, inputs.policy,
                                  inputs.toolchains, inputs.toolchains.originals))
            registry, key = S._INITIALIZER_ATTEMPTS, id(handoff.recipient)
            record = (call.transition, call, call.originals, bound, handoff, inputs_pin)
            control = S._ParentControl(call, registry, key, record, handoff_pin=handoff.pin())
        registry[key] = record
        S._register_parent_control(control)
        S._PARENT_CONTROLS[id(call)] = control
        self.nanoseconds = window.last + 1000

    def modeled_initializer(self, transition, *, stage=True):
        pins = (*S._recipient_predecessor_pins(transition), S._RecipientPredecessorGraph.capture(transition))
        path = self.current.path.with_name(self.current.path.name + "-productive")
        recipient = self.model_parent(S._RecipientParent, transition, pins, path, initializer=False)
        recipient._model_files = []
        self.model_file(recipient, "context", recipient.handles["session"], "recipient-context.json",
                        {"scope": "MODELED_RECIPIENT_PREDECESSOR_NOT_EXECUTED", "job": "d" * 32})
        recipient.pending_raw = recipient.owner.write(recipient.handles["session"], "recipient-prefix-pending.json",
                                                      {"scope": "MODELED_RECIPIENT_PENDING_NOT_EXECUTED"})
        self.finish_model_parent(recipient, initialize=True, stage=stage)
        raw = O.encoded({"scope": "MODELED_RECIPIENT_CLOSED_NOT_EXECUTED"})
        handoff = S._InitializerPredecessor.capture(recipient, raw, recipient.window.last)
        self.recipient = recipient
        path = path / "initializer"
        call = self.model_parent(S._InitializerParent, transition, pins, path, initializer=True)
        call._model_files = []
        toolchains = S.initialization.installed_toolchains()
        request = S.canonical.init_request(state=str(path / "state"),
            expected_commit=O.parse(transition._attempt.admitted.record)["source"]["commit"], role="linux-x64")
        environment = S.recipient_environment(path)
        environment.update(toolchains.environment())
        homes = toolchains.homes()
        inputs = S._InitializationInputs(request, S.canonical._interpreter(), toolchains,
            tuple(sorted(environment.items())), homes, S.initialization.properties(homes))
        context = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PARENT_CONTEXT_V1", "job": "b" * 32,
            "previousSha256": O.digest(handoff.raw), "requestSha256": O.digest(request),
            "admissionSha256": O.digest(transition._attempt.admitted.record), "clock": O.clock_value(self.clock),
            "directories": dict(call.identities), "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        self.model_file(call, "context", call.handles["session"], "initializer-context.json", context)
        self.model_file(call, "request.json", call.handles["canonical-init"], "request.json", request)
        self.model_file(call, "recipient-closed.json", call.handles["session"], "recipient-closed.json", handoff.raw)
        for name in ("state", "gradle-home", "evidence", "cancellations"):
            parent = call.handles["session"] if name == "state" else call.handles["state:state"]
            directory = call.owner.child(parent, name, create=True)
            call.handles["state:" + name] = directory
            call.identities["state:" + name] = self.identity(directory.path)
        source = {**O.parse(transition._attempt.admitted.record)["source"], "status": "", "diffSha256": O.digest(b"")}
        canonical = {"schema": 1, "root": str(ROOT), "expectedCommit": source["commit"], "tree": source["tree"],
            "source": source, "host": "linux-x64", "gradleHome": str(path / "state/gradle-home"),
            "createdUtc": "2026-09-18T00:00:00+00:00", "id": "a" * 32,
            "gradlePropertiesSha256": O.digest(inputs.policy), "javaHomes": list(homes), "preexistingOutputPaths": []}
        canonical_raw = (json.dumps(canonical, sort_keys=True, indent=2) + "\n").encode()
        self.model_file(call, "canonical-context.json", call.handles["state:state"], "context.json", canonical_raw)
        self.model_file(call, "gradle.properties", call.handles["state:gradle-home"], "gradle.properties", inputs.policy, 16384)
        call.pending_raw = call.owner.write(call.handles["session"], "initializer-prefix-pending.json",
                                          {"scope": "MODELED_INITIALIZER_PENDING_NOT_EXECUTED"})
        window = call.window
        closed = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PREFIX_CLOSED_NO_EXECUTION_V1",
            "recipientClosedSha256": O.digest(handoff.raw), "pendingSha256": O.digest(call.pending_raw),
            "window": {"clock": O.clock_value(self.clock), "firstNs": window.first, "workEndNs": window.work,
                "nativeEndNs": window.native_end, "prefixEndNs": window.prefix_end, "finalStartedNs": window.final_started,
                "finalEndNs": window.final, "readStartedNs": window.read_started, "readEndNs": window.read_end,
                "budgetAcceptance": "NOT_ADMITTED"}, "closedNs": window.last, "resourceCount": len(call.owner.resources),
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "childReturn": "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        call.result = S.InitializationPrefix(O.encoded(closed), call.pending_raw, tuple(sorted(call.records.items())), window.last)
        self.finish_model_parent(call, initialize=True, stage=stage, handoff=handoff, inputs=inputs)
        self.init = call
        return call

    @contextmanager
    def prepared(self, *, stage=True):
        with self.ready() as call:
            call.new = S.readmit_closed_entry(call.closed)
            self.current = call
            initial = self.modeled_initializer(call.new, stage=stage)
            supplier_kind = S.query.NativeGitQueries
            original_finalize = supplier_kind._finalize
            original_read = S._StagingPhaseParent.read_originals
            case = self
            def finalize(supplier, error):
                phase = supplier.directory.path.parent.name
                if phase.endswith("-parent"):
                    parent = case.phase(phase.removesuffix("-parent"))
                    case.query_events.append((parent.name, supplier))
                    case.query_before(parent)
                result = original_finalize(supplier, error)
                if phase.endswith("-parent"):
                    case.query_after(parent)
                return result
            def read(parent):
                result = original_read(parent)
                case.read_events.append(parent.name)
                case.after_original_read(parent)
                return result
            with patch.object(supplier_kind, "_finalize", finalize), \
                    patch.object(S._StagingPhaseParent, "read_originals", read), \
                    patch.object(S.processes, "make_scope", side_effect=AssertionError("NO_NEW_NATIVE_PRODUCER")), \
                    patch.object(O.http.client, "HTTPSConnection", side_effect=AssertionError("NO_SECOND_SERVICE_HTTP")), \
                    patch.object(S.posix, "_gpg", side_effect=AssertionError("NO_GPG")), \
                    patch.object(B.cache, "export_snapshot", side_effect=AssertionError("NO_EXPORT")), \
                    patch.object(B.cache, "save_set", side_effect=AssertionError("NO_SAVE")), \
                    patch.object(B.files, "_copy_allowlisted", side_effect=AssertionError("NO_DEPENDENCY_COPY")):
                yield initial

    def sequence(self):
        return S._STAGING_ATTEMPTS[id(self.init)][2]

    def phase(self, name):
        return next(parent for parent in S._staging_sequence_frame(self.sequence()).phases if parent.name == name)

    def run_parent(self):
        return S._stage_after_initialization(self.init, self.init.result)

    def assert_predecessors_closed(self):
        for parent in (self.recipient, self.init):
            self.assertTrue(parent.owner.closed)
            self.assertIsNone(parent.original)
            self.assertIsNone(parent.owner.original)
            self.assertFalse(parent.owner.unknown)
            self.assertEqual(parent.owner.errors, [])
        self.assertEqual(self.recipient.state, "HANDED_OFF")
        self.assertEqual(self.init.state, "COMPLETE")
        self.unchanged_old(self.current)

    def refused(self, reason=None, kind=Exception):
        assertion = self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)
        with assertion as caught:
            self.run_parent()
        sequence = self.sequence()
        self.assertEqual(sequence.state, "FAILED")
        self.assertIsNone(sequence.result)
        self.assertIs(sequence.original, caught.exception)
        self.assertIn(sequence.failure_custody, ("UNAVAILABLE", "INCOMPLETE"))
        self.assert_predecessors_closed()
        return caught.exception

    def test_actual_new_parents_and_leaves_close_distinct_owners_with_complete_original_reads(self):
        with self.prepared():
            initial_result = self.init.result
            result = self.run_parent()
            self.assertIs(type(result), S.StagingPrefix)
            self.assertIs(self.init.result, initial_result)
            stage, seed = self.sequence().phases
            self.assertIsNot(stage.owner, seed.owner)
            self.assertIsNot(stage.owner, self.init.owner)
            for parent in (stage, seed):
                frame = S._staging_frame(parent)
                self.assertEqual(parent.state, "COMPLETE")
                self.assertTrue(parent.owner.closed)
                self.assertIsNone(parent.owner.original)
                self.assertFalse(parent.owner.unknown)
                self.assertTrue(all(pin[3] and pin[4] for pin in frame.resources))
                self.assertEqual(frame.handlers, frame.restored)
                self.assertEqual(self.read_events.count(parent.name), 4)
                self.assertEqual(len(frame.queries), 1)
                supplier, pair, work, final = frame.queries[0]
                self.assertTrue(supplier.owner.closed)
                self.assertLessEqual(pair[0], pair[1])
                self.assertLessEqual(pair[1], frame.limits.local_soft)
                self.assertLessEqual(work, final)
                self.assertLessEqual(final, frame.limits.soft)
                value = O.parse(parent.result.raw)
                self.assertFalse(value["nextPhaseAuthority"])
                self.assertFalse(value["exportSaveAuthority"])
                self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
                self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
                self.assertGreater(parent.result.checked_ns, parent.leaf.checked_ns)
            self.assertGreaterEqual(S._staging_frame(seed).limits.first, stage.result.checked_ns)
            self.assertGreaterEqual(S._staging_frame(seed).limits.local_start, stage.result.checked_local)
            seed_value = B.files.record(result.seed_leaf.raw)
            self.assertTrue(seed_value["completed"])
            self.assertEqual(seed_value["counts"], {name: 0 for name in B.COUNTERS})
            self.assertTrue(seed_value["misses"])
            self.assertTrue(all(row["reason"] == "ABSENT" for row in seed_value["misses"]))
            home = self.init.handles["state:gradle-home"].path
            self.assertEqual({p.name for p in home.iterdir()}, {"gradle.properties"})
            container = B.files.stage_path(self.init.handles["session"].path, "desktop", "linux-x64")
            self.assertEqual({p.name for p in container.iterdir()}, {"restore-home", "staging.json"})
            self.assertEqual(list((container / "restore-home").iterdir()), [])
            self.assert_predecessors_closed()

    def test_initializer_only_intent_cannot_be_retrofitted_from_its_exact_return(self):
        with self.prepared(stage=False), patch.object(O.clocks, "observe", side_effect=AssertionError("NO_NEW_CLOCK")):
            self.refused("INTENT_NOT_ORIGINAL")
            self.assertEqual(self.sequence().phases, ())

    def test_copied_initializer_result_is_not_a_handoff_and_consumes_the_attempt(self):
        with self.prepared():
            with self.assertRaisesRegex(O.OriginError, "NOT_ORIGINAL_INITIALIZER_RETURN"):
                S._stage_after_initialization(self.init, replace(self.init.result))
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_RETRY_CLOCK")), \
                    self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
                self.run_parent()
            self.assertEqual(self.sequence().phases, ())

    def test_completed_sequence_cannot_be_replayed(self):
        with self.prepared():
            self.run_parent()
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_RETRY_CLOCK")), \
                    self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
                self.run_parent()

    def test_failed_query_consumes_sequence_without_second_supplier_or_service_call(self):
        with self.prepared():
            failure = FalseyFailure("FIRST_QUERY_FAILURE")
            self.query_after = lambda parent: (_ for _ in ()).throw(failure)
            self.assertIs(self.refused("FIRST_QUERY_FAILURE"), failure)
            self.assertEqual(len(self.query_events), 1)
            with self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
                self.run_parent()
            self.assertEqual(len(self.sequence().phases), 1)

    def test_stage_query_finalizer_return_at_soft_equality_is_not_success(self):
        with self.prepared():
            def late(parent):
                self.nanoseconds = S._staging_frame(parent).limits.soft
            self.query_after = late
            self.refused("ORIGINAL_PHASE_EXPIRED")
            self.assertIsNone(self.phase("dependency-stage").leaf)

    def test_seed_query_finalizer_must_fit_soft90_not_hard120(self):
        with self.prepared():
            def late(parent):
                if parent.name == "empty-seed":
                    frame = S._staging_frame(parent)
                    self.assertLess(frame.limits.soft, frame.limits.hard)
                    self.nanoseconds = frame.limits.soft
            self.query_after = late
            self.refused("ORIGINAL_PHASE_EXPIRED")
            self.assertEqual(self.phase("dependency-stage").state, "COMPLETE")
            self.assertIsNone(self.phase("empty-seed").leaf)

    def test_seed_new_file_at_soft90_refuses_even_with_final_true(self):
        with self.prepared():
            acquired = []
            def at_seed(parent):
                if parent.name == "empty-seed":
                    self.nanoseconds = S._staging_frame(parent).limits.soft
                    parent.owner.acquire("writer", lambda: acquired.append(True), final=True)
            self.query_after = at_seed
            self.refused("ORIGINAL_PHASE_EXPIRED")
            self.assertEqual(acquired, [])

    def test_first_stage_raw_precedes_actual_initializer_return_is_refused(self):
        with self.prepared():
            self.nanoseconds = self.init.result.checked_ns - 2000
            self.refused("PREDECESSOR_CLOCK")
            self.assertIsNone(self.phase("dependency-stage").owner)

    def test_first_stage_local_precedes_actual_initializer_return_is_refused(self):
        with self.prepared():
            self.local_override = self.init.window.local_last - .001
            self.refused("PREDECESSOR_CLOCK")
            self.assertIsNone(self.phase("dependency-stage").owner)

    def test_seed_first_follows_parent_return_not_earlier_stage_leaf(self):
        with self.prepared():
            original = S._run_staging_phase
            def run(sequence, previous, name):
                if name == "empty-seed":
                    self.nanoseconds = previous.leaf.checked_ns
                    self.assertLess(self.nanoseconds + 1000, previous.checked_ns)
                return original(sequence, previous, name)
            with patch.object(S, "_run_staging_phase", run):
                self.refused("PREDECESSOR_CLOCK")
            self.assertEqual(self.phase("dependency-stage").state, "COMPLETE")
            self.assertIsNone(self.phase("empty-seed").owner)

    def test_complete_initializer_inputs_are_typed_pins_not_an_opaque_object(self):
        with self.prepared():
            def change(parent):
                inputs = S._parent_originals(self.init)[4][5][0]
                object.__setattr__(inputs.toolchains, "originals", (*inputs.toolchains.originals, ("CHANGED",)))
            self.query_after = change
            self.refused("CLOSED_GRAPH_CHANGED")
            self.assertIsNone(self.phase("dependency-stage").leaf)

    def test_original_initialization_bytes_are_reread_after_query(self):
        with self.prepared():
            path = self.init.handles["state:state"].path / "context.json"
            self.query_after = lambda parent: path.write_bytes(path.read_bytes() + b" ")
            self.refused("PREDECESSOR_FILE_CHANGED")
            self.assertIsNone(self.phase("dependency-stage").leaf)

    def test_original_service_bytes_are_reread_after_query(self):
        with self.prepared():
            path = self.current.path / "service/jobs.json"
            self.query_after = lambda parent: path.write_bytes(path.read_bytes() + b" ")
            self.refused()
            self.assertIsNone(self.phase("dependency-stage").leaf)

    def test_existing_stage_container_is_never_adopted(self):
        with self.prepared():
            path = B.files.stage_path(self.init.handles["session"].path, "desktop", "linux-x64")
            path.mkdir(mode=0o700)
            before = self.identity(path)
            self.refused(kind=FileExistsError)
            self.assertEqual(self.identity(path), before)
            self.assertEqual(list(path.iterdir()), [])

    def test_closed_old_owners_and_windows_are_never_called_again(self):
        with self.prepared():
            owners = (self.current.owner, self.current.new._attempt.owner, self.recipient.owner, self.init.owner)
            original_end, original_close = S.Owner.end, S.Owner.close
            def end(owner, *args, **kwargs):
                self.assertFalse(any(owner is old for old in owners), "NO_OLD_END")
                return original_end(owner, *args, **kwargs)
            def close(owner):
                self.assertFalse(any(owner is old for old in owners), "NO_OLD_CLOSE")
                return original_close(owner)
            with patch.object(S.Owner, "end", end), patch.object(S.Owner, "close", close), \
                    patch.object(S._RecipientParentWindow, "now", side_effect=AssertionError("NO_OLD_WINDOW_NOW")):
                self.run_parent()
            self.assert_predecessors_closed()

    def test_public_owner_alias_rejection_still_closes_original_owner(self):
        with self.prepared():
            fake = object()
            self.query_after = lambda parent: setattr(parent, "owner", fake)
            self.refused("PARENT_CHANGED")
            parent = self.phase("dependency-stage")
            frame = S._staging_frame(parent)
            self.assertIs(parent.owner, fake)
            self.assertTrue(frame.owner.closed)
            self.assertFalse(frame.owner.unknown)
            self.assertTrue(all(pin[3] and pin[4] for pin in frame.resources))
            self.assertEqual(frame.handlers, frame.restored)

    def test_public_registry_alias_rejection_does_not_redirect_cleanup(self):
        with self.prepared():
            original_registry = S._STAGING_ATTEMPTS
            self.query_after = lambda parent: setattr(S, "_STAGING_ATTEMPTS", {})
            try:
                with self.assertRaisesRegex(O.OriginError, "SEQUENCE_CHANGED"):
                    self.run_parent()
                sequence = original_registry[id(self.init)][2]
                frame = S._staging_frame(S._staging_sequence_frame(sequence).phases[0])
                self.assertTrue(frame.owner.closed)
                self.assertFalse(frame.owner.unknown)
                self.assertEqual(frame.handlers, frame.restored)
            finally:
                S._STAGING_ATTEMPTS = original_registry
            self.assert_predecessors_closed()

    def original_registry_replacement(self, name):
        with self.prepared():
            original = getattr(S, name)
            self.query_after = lambda parent: setattr(S, name, dict(original))
            try:
                self.refused("REGISTRY_CHANGED")
                frame = S._staging_frame(self.phase("dependency-stage"))
                self.assertTrue(frame.owner.closed)
                self.assertFalse(frame.owner.unknown)
                self.assertTrue(all(pin[3] and pin[4] for pin in frame.resources))
            finally:
                setattr(S, name, original)

    def test_equal_recipient_registry_alias_is_not_the_original(self):
        self.original_registry_replacement("_RECIPIENT_ATTEMPTS")

    def test_equal_initializer_registry_alias_is_not_the_original(self):
        self.original_registry_replacement("_INITIALIZER_ATTEMPTS")

    def test_equal_parent_control_registry_alias_is_not_the_original(self):
        self.original_registry_replacement("_PARENT_CONTROLS")

    def test_final_seed_raw_return_cannot_replace_the_original_entry_registry(self):
        with self.prepared():
            original, encode, observe = S._ENTRY_ATTEMPTS, O.encoded, O.clocks.observe
            armed, changed = [], []
            def encoded(value):
                raw = encode(value)
                if type(value) is dict and value.get("scope") == "BOOTSTRAP_STAGING_PARENT_CLOSED_NO_EXECUTION_V1" and \
                        value.get("phase") == "empty-seed":
                    armed.append(True)
                return raw
            def clock():
                value = observe()
                if armed and not changed:
                    S._ENTRY_ATTEMPTS = dict(original)
                    changed.append(True)
                return value
            try:
                with patch.object(O, "encoded", encoded), patch.object(O.clocks, "observe", clock):
                    self.refused("REGISTRY_CHANGED")
                self.assertEqual(changed, [True])
                self.assertTrue(S._staging_frame(self.phase("empty-seed")).owner.closed)
            finally:
                S._ENTRY_ATTEMPTS = original

    def close_supplier_mutation(self, *, replace_fence):
        with self.prepared():
            first, redirected, originals = FalseyFailure("FIRST_BEFORE_CLOSE_MUTATION"), [], []
            class WrongResource:
                def close(self):
                    redirected.append("close")
                def now(self, **kwargs):
                    redirected.append("now")
                    return 0
                def deadline(self, *args, **kwargs):
                    redirected.append("deadline")
                    return 1e12
            def inject(parent):
                frame = S._staging_frame(parent)
                live = [pin for pin in frame.resources if not pin[3]]
                self.assertGreaterEqual(len(live), 2)
                trigger, victim = live[-1], live[0]
                originals.extend((trigger, victim))
                close = trigger[2].close
                def mutate():
                    close()
                    if replace_fence:
                        frame.owner.fence = WrongResource()
                    else:
                        victim[0]["owner"] = WrongResource()
                self.stack.enter_context(patch.object(trigger[2], "close", mutate))
                raise first
            self.query_after = inject
            self.assertIs(self.refused("FIRST_BEFORE_CLOSE_MUTATION"), first)
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertEqual(redirected, [])
            self.assertTrue(frame.owner.unknown)
            self.assertTrue(frame.unknown)
            self.assertFalse(originals[1][2].closed)
            self.assertTrue(any(pin[2] is originals[1][2] for pin in frame.resources))
            self.assertEqual(frame.handlers, frame.restored)

    def test_resource_close_cannot_redirect_the_following_cleanup_fence(self):
        self.close_supplier_mutation(replace_fence=True)

    def test_resource_close_cannot_redirect_a_still_pending_resource_row(self):
        self.close_supplier_mutation(replace_fence=False)

    def test_live_owner_end_checks_original_fence_before_dispatch(self):
        with self.prepared():
            redirected = []
            class WrongFence:
                def deadline(self, *args, **kwargs):
                    redirected.append(True)
                    return 1e12
                def now(self, **kwargs):
                    redirected.append(True)
                    return 0
            def replace_fence(parent):
                parent.owner.fence = WrongFence()
                parent.owner.end()
            self.query_after = replace_fence
            self.refused("OWNER_CHANGED")
            self.assertEqual(redirected, [])

    def test_public_attempted_closed_flags_cannot_attest_an_actual_unclosed_resource(self):
        with self.prepared():
            first, forged = FalseyFailure("FIRST_BEFORE_FORGED_CLOSE_FLAGS"), []
            def forge(parent):
                pin = next(pin for pin in S._staging_frame(parent).resources if not pin[3])
                self.assertFalse(pin[2].closed)
                forged.append(pin)
                pin[0].update(attempted=True, closed=True)
                raise first
            self.query_after = forge
            self.assertIs(self.refused("FIRST_BEFORE_FORGED_CLOSE_FLAGS"), first)
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertTrue(frame.unknown)
            self.assertTrue(frame.owner.unknown)
            self.assertFalse(forged[0][2].closed)
            self.assertTrue(any(pin[2] is forged[0][2] and not pin[4] for pin in frame.resources))

    def test_unregistered_public_resource_row_is_retained_without_close_authority(self):
        with self.prepared():
            first, extra = FalseyFailure("FIRST_BEFORE_UNREGISTERED_ROW"), []
            def add_row(parent):
                resource = S.query._PosixDirectory(parent.handles["phase"].path)
                self.addCleanup(lambda: None if resource.closed else resource.close())
                extra.append(resource)
                parent.owner.resources.append({"label": "directory", "owner": resource,
                                               "attempted": False, "closed": False})
                raise first
            self.query_after = add_row
            self.assertIs(self.refused("FIRST_BEFORE_UNREGISTERED_ROW"), first)
            parent = self.phase("dependency-stage")
            frame = S._staging_frame(parent)
            self.assertTrue(frame.unknown)
            self.assertTrue(frame.owner.unknown)
            self.assertFalse(extra[0].closed)
            self.assertTrue(any(pin[2] is extra[0] for pin in frame.foreign_resources))
            self.assertFalse(any(pin[2] is extra[0] for pin in frame.resources))
            # Removing the public extra cannot turn its retained unknown status
            # into a new close obligation or a passing roster.
            frame.owner.resources.pop()
            with self.assertRaisesRegex(O.OriginError, "ROSTER_CHANGED"):
                parent.roster()
            self.assertFalse(extra[0].closed)

    def test_actual_acquisition_is_registered_before_a_fallible_post_return_clock(self):
        with self.prepared():
            first = FalseyFailure("FIRST_AFTER_ACTUAL_ACQUISITION")
            returned, checked = [], []
            original_clock = O.clocks.checked_now
            def clock(*args, **kwargs):
                if returned and not checked:
                    checked.append(True)
                    frame = S._staging_frame(self.phase("dependency-stage"))
                    self.assertEqual(sum(pin[2] is returned[0] for pin in frame.resources), 1)
                    self.assertFalse(returned[0].closed)
                    raise first
                return original_clock(*args, **kwargs)
            def acquire(parent):
                def factory():
                    resource = S.query._PosixDirectory(parent.handles["phase"].path)
                    self.addCleanup(lambda: None if resource.closed else resource.close())
                    returned.append(resource)
                    return resource
                parent.owner.acquire("directory", factory)
            self.query_after = acquire
            with patch.object(O.clocks, "checked_now", clock):
                self.assertIs(self.refused("FIRST_AFTER_ACTUAL_ACQUISITION"), first)
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertEqual(checked, [True])
            self.assertFalse(frame.unknown)
            self.assertFalse(frame.owner.unknown)
            self.assertTrue(returned[0].closed)
            self.assertTrue(any(pin[2] is returned[0] and pin[3] and pin[4] for pin in frame.resources))

    def test_duplicate_factory_return_keeps_only_its_existing_close_obligation(self):
        with self.prepared():
            original_pins, closes = [], []
            def duplicate(parent):
                frame = S._staging_frame(parent)
                original_pins.extend(frame.resources)
                pin = next(pin for pin in frame.resources if not pin[3])
                close = pin[2].close
                def counted_close():
                    closes.append(True)
                    close()
                self.stack.enter_context(patch.object(pin[2], "close", counted_close))
                parent.owner.acquire("directory", lambda: pin[2])
            self.query_after = duplicate
            self.refused("DUPLICATE_OWNER")
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertEqual(len(frame.resources), len(original_pins))
            self.assertTrue(all(pin[:3] == old[:3] for pin, old in zip(frame.resources, original_pins)))
            self.assertFalse(frame.unknown)
            self.assertFalse(frame.owner.unknown)
            self.assertEqual(closes, [True])
            self.assertTrue(all(pin[3] and pin[4] for pin in frame.resources))

    def test_public_alias_after_large_leaf_roster_still_closes_known_originals(self):
        with self.prepared():
            def replace_alias(parent):
                if self.read_events.count(parent.name) == 4:
                    self.assertGreater(len(S._staging_frame(parent).resources), 64)
                    parent.owner = object()
            self.after_original_read = replace_alias
            self.refused("PARENT_CHANGED")
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertTrue(frame.owner.closed)
            self.assertFalse(frame.owner.unknown)
            self.assertLess(len(frame.owner.errors), 64)
            self.assertTrue(all(pin[3] and pin[4] for pin in frame.resources))

    def test_corrupted_actual_error_container_cannot_erase_first_failure(self):
        with self.prepared():
            first = FalseyFailure("FIRST_BEFORE_BAD_ERROR_CONTAINER")
            def replace_errors(parent):
                parent.owner.errors = None
                raise first
            self.query_after = replace_errors
            self.assertIs(self.refused("FIRST_BEFORE_BAD_ERROR_CONTAINER"), first)
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertTrue(frame.unknown)
            self.assertIs(frame.original, first)

    def test_mutated_actual_owner_fence_is_quarantined_not_invoked_on_close(self):
        with self.prepared():
            class WrongFence:
                def now(self, **kwargs):
                    raise AssertionError("NO_REDIRECTED_CLEANUP")
            self.query_after = lambda parent: setattr(parent.owner, "fence", WrongFence())
            self.refused("OWNER_CHANGED")
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertTrue(frame.unknown)
            self.assertFalse(frame.owner.closed)
            self.assertIn(frame.owner, S.QUARANTINE)

    def test_removed_resource_row_is_retained_as_unknown_not_a_clean_close(self):
        with self.prepared():
            removed = []
            def remove(parent):
                removed.append(parent.owner.resources.pop())
            self.query_after = remove
            self.refused("ROSTER_CHANGED")
            frame = S._staging_frame(self.phase("dependency-stage"))
            self.assertTrue(frame.unknown)
            self.assertTrue(any(pin[0] is removed[0] and pin[2] is removed[0]["owner"] for pin in frame.resources))
            self.assertIsNone(frame.result)

    def test_falsey_first_error_survives_handler_restore_failure(self):
        with self.prepared():
            first, later = FalseyFailure("FIRST_FALSEY"), RuntimeError("LATER_RESTORE")
            self.query_after = lambda parent: (_ for _ in ()).throw(first)
            real_signal = S.signal.signal
            def handler(number, value):
                if value is None and S._STAGING_ATTEMPTS:
                    raise later
                return real_signal(number, value)
            with patch.object(S.signal, "signal", handler):
                self.assertIs(self.refused("FIRST_FALSEY"), first)
            self.assertIs(S._staging_frame(self.phase("dependency-stage")).original, first)

    def test_final_seed_raw_return_at_local_hard_retains_raw_and_refuses_success(self):
        with self.prepared():
            encode, observe = O.encoded, O.clocks.observe
            armed, returned = [], []
            def encoded(value):
                raw = encode(value)
                if type(value) is dict and value.get("scope") == "BOOTSTRAP_STAGING_PARENT_CLOSED_NO_EXECUTION_V1" and \
                        value.get("phase") == "empty-seed":
                    armed.append(True)
                return raw
            def raw_observation():
                value = observe()
                if armed:
                    self.local_override = S._staging_frame(self.phase("empty-seed")).limits.local_hard
                    returned.append(value.nanoseconds)
                return value
            with patch.object(O, "encoded", encoded), patch.object(O.clocks, "observe", raw_observation):
                self.refused("ORIGINAL_PHASE_EXPIRED")
            frame = S._staging_frame(self.phase("empty-seed"))
            self.assertEqual(frame.last, returned[-1])
            self.assertEqual(frame.local_last, frame.limits.local_hard)
            self.assertTrue(frame.owner.closed)
            self.assertEqual(self.phase("dependency-stage").state, "COMPLETE")

    def test_final_serialization_failure_does_not_promote_closed_resources(self):
        with self.prepared():
            original = O.encoded
            first = FalseyFailure("FINAL_SERIALIZATION")
            def encoded(value):
                if type(value) is dict and value.get("scope") == "BOOTSTRAP_STAGING_PARENT_CLOSED_NO_EXECUTION_V1":
                    raise first
                return original(value)
            with patch.object(O, "encoded", encoded):
                self.assertIs(self.refused("FINAL_SERIALIZATION"), first)
            self.assertTrue(S._staging_frame(self.phase("dependency-stage")).owner.closed)

    def test_new_reader_kind_is_exact_and_has_no_public_command(self):
        self.assertFalse(issubclass(S._StagingPhaseParent, S._RecipientParent))
        for function in (S._read_chain, S._read_prepared):
            self.assertIn("_StagingOriginalReader", inspect.getsource(function))
        self.assertNotIn("stage_after_entry", inspect.getsource(S.main))
        self.assertEqual(list(inspect.signature(S.stage_after_entry).parameters), ["transition"])
        for initialize, stage in ((False, True), (True, 1), (1, False), (True, None)):
            with self.subTest(initialize=initialize, stage=stage), self.assertRaisesRegex(O.OriginError, "RECIPIENT_INTENT"):
                S._recipient_after_entry(object(), initialize=initialize, stage=stage)

    def original_intent_probe(self, operation, expected):
        with self.ready() as call:
            transition = S.readmit_closed_entry(call.closed)
            with patch.object(S.Owner, "__init__", side_effect=IntentProbe("STOP_BEFORE_RECIPIENT_OWNER")), \
                    self.assertRaisesRegex(IntentProbe, "STOP_BEFORE_RECIPIENT_OWNER"):
                operation(transition)
            registered = S._RECIPIENT_ATTEMPTS[id(transition)]
            self.assertEqual(len(registered), 6)
            self.assertEqual(registered[4:], expected)
            self.assertIs(type(registered[4]), bool)
            self.assertIs(type(registered[5]), bool)
            self.assertEqual(S._INITIALIZER_ATTEMPTS, {})
            self.assertEqual(S._STAGING_ATTEMPTS, {})

    def test_recipient_only_original_shared_claim_keeps_both_intents_false(self):
        self.original_intent_probe(S.run_recipient_after_entry, (False, False))

    def test_initialize_only_original_shared_claim_keeps_stage_intent_false(self):
        self.original_intent_probe(S.initialize_after_entry, (True, False))

    def test_staging_original_shared_claim_selects_initialization_before_any_owner(self):
        self.original_intent_probe(S.stage_after_entry, (True, True))


def load_tests(_loader, _tests, _pattern):
    return unittest.TestSuite(ParentModels(name) for name in ParentModels.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
