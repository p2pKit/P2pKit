#!/usr/bin/env python3
"""Own tiny reservation controls; no parent/native/configuration execution.

Historical modules supply model setup only: their tests and stage/seed leaves
are never run. Actual ordinary-UID POSIX reads/writes/closure exercise the new
leaf; staged returns, admission, service identity and clocks are synthetic.
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import inspect
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_custody as C


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FIXTURES = load("configuration_custody_model_setup", Path(__file__).with_name("hosted-cache-bootstrap-staging-test.py"))
B, F, O, NS = C.staging, C.files, C.origin, C.staging.NS
RESERVED = uuid.UUID("c398a53f-dfbc-4cda-8e07-57cf5e679a9f")


class ReservationModels(unittest.TestCase):
    def setUp(self):
        # Only setUp/doCleanups are composed. No historical method or stage/seed
        # execution is selected, and these entry points are explicitly poisoned.
        self.f = FIXTURES.LeafModels()
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        f = self.f
        f.stack.enter_context(patch.object(C, "ROOT", f.root))
        for target, name in ((B, "stage_empty"), (B, "observe_empty_seed"), (C.producer, "make_request"),
                             (B.initialization, "installed_toolchains")):
            f.stack.enter_context(patch.object(target, name, side_effect=AssertionError("NO_STAGE_REPLAY_OR_PRODUCER")))
        for name in C.CUSTODY_INPUTS:
            path = f.root / name
            path.write_bytes(("SYNTHETIC NEVER EXECUTED: " + name + "\n").encode())
            path.chmod(0o644)
        f.container.mkdir(mode=0o700)
        f.restore.mkdir(mode=0o700)
        compiled = F.authority.parse_allowlist(FIXTURES.metadata())
        source = {"files": {name: F.digest((f.root / name).read_bytes()) for name in F.INPUTS},
            "allowlistSha256": compiled.authority_sha256, "artifacts": len(compiled.artifacts),
            "components": compiled.component_count, "policy": F.policy()}
        inputs = B._Inputs(f.originals, B._capture(f.originals))
        stage = F.stage_record(f.admitted.record, "desktop", "linux-x64", f.container,
            SimpleNamespace(identity=f.identity(f.container)), SimpleNamespace(identity=f.identity(f.restore)), source)
        staging_raw = F.encoded(stage)
        f.write(f.container / "staging.json", staging_raw)
        bindings = {name: F._info_binding(F._info(path.stat())) for name, path in (
            ("initializer-context", f.session / "initializer-context.json"), ("canonical-context", f.state / "context.json"),
            ("properties", f.home / "gradle.properties"), ("staging", f.container / "staging.json"))}
        plan = B.cache.make_plan(f.admitted.record, staging_raw, compiled, source,
                                 session=f.session, profile="desktop", role="linux-x64", mode="bootstrap")
        intent = F.seed_intent(f.admitted.record, "desktop", "linux-x64", f.container, staging_raw, source)
        stage_first, seed_first = 1100 * NS, 1101 * NS
        stage_value = {"schema": 1, "scope": B.STAGE_SCOPE, "binding": inputs.binding(), "inputs": source,
            "bootstrapInputs": {name: F.digest((f.root / name).read_bytes()) for name in B.BOOTSTRAP_INPUTS},
            "stagingSha256": F.digest(staging_raw), "plan": plan, "seedIntent": intent, "fileBindings": bindings,
            "window": self.leaf_window("dependency-stage", stage_first, f.originals.initializer_closed_raw,
                                        f.originals.initializer_checked_ns),
            "status": B.EMPTY, "completed": True, "leafHandleClose": "KNOWN", "enclosingOwnerRetirement": "NOT_OBSERVED_HERE",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        stage_leaf = B.LeafEvidence(F.encoded(stage_value), staging_raw, stage_first + 20_000, 500.0, 500.1)
        seed_value = {**stage_value, "scope": B.SEED_SCOPE,
            "window": self.leaf_window("empty-seed", seed_first, stage_leaf.raw, stage_leaf.checked_ns),
            "stageEvidenceSha256": F.digest(stage_leaf.raw), "stageReturnBindingSha256": F.digest(F.encoded(
                {"rawSha256": F.digest(stage_leaf.raw), "checkedNs": stage_leaf.checked_ns,
                 "localStarted": stage_leaf.local_started, "localChecked": stage_leaf.checked_local})),
            "counts": {name: 0 for name in B.COUNTERS}, "admitted": [],
            "misses": [{"index": i, "reason": "ABSENT", "rejected": 0} for i in range(len(compiled.artifacts))],
            "sourceIdentity": f.identity(f.restore), "homeIdentity": f.identity(f.home),
            "byteScope": "DEPENDENCY_BYTES_ONLY_METADATA_IO_OCCURRED"}
        seed_leaf = B.LeafEvidence(F.encoded(seed_value), staging_raw, seed_first + 20_000, 500.2, 500.3)
        stage_parent = self.parent_record(stage_leaf, f.originals.initializer_closed_raw, f.originals.initializer_checked_ns)
        seed_parent = self.parent_record(seed_leaf, stage_parent, stage_first + 40_000)
        self.staged = C.StagedEvidence(seed_parent, stage_parent, stage_leaf, seed_leaf, seed_first + 40_000, 500.4)
        f.ns, f.local = 1102 * NS, 501.0
        self.phase = f.phase()
        self.directory = f.session / "configuration-custody"
        self.uuid_call = f.stack.enter_context(patch.object(C.uuid, "uuid4", return_value=RESERVED))

    def leaf_window(self, name, first, previous, previous_ns):
        return {"phase": name, "clock": O.clock_value(self.f.clock), "firstNs": first,
            "hardEndNs": first + 120 * NS, "softEndNs": first + (90 if name == "empty-seed" else 120) * NS,
            "lastNewWorkNs": first + 5000, "finishedNs": first + 10000,
            "predecessorSha256": F.digest(previous), "predecessorCheckedNs": previous_ns,
            "proposalSha256": F.digest(self.f.originals.proposal_raw)}

    @staticmethod
    def parent_record(leaf, previous, checked):
        window = F.record(leaf.raw)["window"]
        return F.encoded({"schema": 1, "scope": C.PARENT_SCOPE, "phase": window["phase"],
            "window": {**{name: window[name] for name in ("phase", "clock", "firstNs", "softEndNs", "hardEndNs")},
                       "budgetAcceptance": "NOT_ADMITTED"}, "pendingSha256": "b" * 64,
            "predecessorSha256": F.digest(previous), "predecessorCheckedNs": checked,
            "leafSha256": F.digest(leaf.raw), "leafCheckedNs": leaf.checked_ns, "closedNs": leaf.checked_ns + 10000,
            "resourceCount": 5, "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "nextPhaseAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})

    def reserve(self, **overrides):
        values = {"parent": self.f.owner, "originals": self.f.originals, "phase": self.phase, "staged": self.staged}
        values.update(overrides)
        return C.reserve_configuration(**values)

    def fail(self, call=None, reason=None, kind=Exception, owner=None):
        with (self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)) as caught:
            (self.reserve if call is None else call)()
        error = caught.exception
        if hasattr(error, "bootstrap_custody_result"):
            self.assertFalse(error.bootstrap_custody_result["completed"])
            self.assertIs(error.bootstrap_custody_result["exportSaveAuthority"], False)
            self.assertIs((self.f.owner if owner is None else owner).original, error)
        return error

    def seed_mutant(self, change):
        value = F.record(self.staged.seed_leaf.raw)
        change(value)
        return replace(self.staged, seed_leaf=replace(self.staged.seed_leaf, raw=F.encoded(value)))

    def parent_mutant(self, name, change):
        value = F.record(getattr(self.staged, name))
        change(value)
        return replace(self.staged, **{name: F.encoded(value)})

    def known(self):
        self.assertIsNone(self.f.owner.original)
        self.assertFalse(self.f.owner.unknown)
        self.assertFalse(self.f.owner.closed)
        self.assertTrue(self.f.owner.resources)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.f.owner.resources))

    def test_reserves_one_id_without_loader_command_or_canonical_evidence_allocation(self):
        before = {str(p): p.read_bytes() for p in self.f.session.parent.rglob("*") if p.is_file()}
        value = self.reserve()
        result, request = F.record(value.raw), F.record(value.request_raw)
        self.assertEqual(result["status"], "RESERVED_CONFIGURATION_ONLY")
        self.assertEqual(result["requestSha256"], F.digest(value.request_raw))
        self.assertEqual((self.directory / "request.json").read_bytes(), value.request_raw)
        self.assertEqual({p.name for p in self.directory.iterdir()}, {"request.json", "retained"})
        self.assertFalse(tuple((self.directory / "retained").iterdir()))
        self.assertEqual(request["owner"], {"job": "a" * 32, "productInvocation": RESERVED.hex,
                                           "sameHomeStopInvocation": RESERVED.hex})
        self.assertEqual(request["requestedArgv"], ["help", "--console=plain", "--no-configure-on-demand"])
        self.assertEqual(request["ancestorDomainChain"], "NOT_SYNTHESIZED_OR_ADMITTED")
        self.assertNotIn("argv", request)
        self.assertEqual(request["evidenceDirectory"], str(self.f.state / "evidence" / RESERVED.hex))
        self.assertFalse(tuple((self.f.state / "evidence").iterdir()))
        self.assertFalse(tuple((self.f.state / "cancellations").iterdir()))
        self.assertEqual({p.name for p in self.f.home.iterdir()}, {"gradle.properties"})
        self.assertFalse(tuple(self.f.restore.iterdir()))
        self.assertEqual({path: Path(path).read_bytes() for path in before}, before)
        self.uuid_call.assert_called_once_with()
        self.known()

    def test_final_parent_not_leaf_is_clock_and_hash_predecessor(self):
        value = self.reserve()
        result = F.record(value.raw)
        self.assertEqual(result["window"]["predecessorSha256"], F.digest(self.staged.raw))
        self.assertEqual(result["window"]["predecessorCheckedNs"], self.staged.checked_ns)
        self.assertEqual(result["predecessors"]["seedParentCheckedLocal"], self.staged.checked_local)
        self.assertGreater(self.staged.checked_ns, self.staged.seed_leaf.checked_ns)
        self.assertLess(result["window"]["finishedNs"], value.checked_ns)
        self.assertEqual(value.local_started, self.phase.local_started)
        self.assertEqual(result["window"]["hardEndNs"], self.phase.first.nanoseconds + 120 * NS)
        self.assertEqual(result["window"]["softEndNs"], result["window"]["hardEndNs"])

    def test_copied_consistent_records_remain_non_authoritative_data(self):
        copied = replace(self.staged, stage_leaf=replace(self.staged.stage_leaf), seed_leaf=replace(self.staged.seed_leaf))
        value = self.reserve(staged=copied)
        for raw in (value.raw, value.request_raw):
            result = F.record(raw)
            self.assertIs(result["nextPhaseAuthority"], False)
            self.assertIs(result["exportSaveAuthority"], False)
            self.assertEqual(result["budgetAcceptance"], "NOT_ADMITTED")
            self.assertEqual(result["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(F.record(value.raw)["enclosingOwnerRetirement"], "NOT_OBSERVED_HERE")
        self.assertEqual(F.record(value.request_raw)["predecessors"]["provenance"], "SUPPLIED_DATA_NOT_AUTHENTICATED_PARENT_RETURNS")

    def test_rejects_stage_only_or_changed_seed_counters_scope_and_source_binding(self):
        changes = (lambda v: v.update(scope=B.STAGE_SCOPE), lambda v: v["counts"].update(outputBytes=1),
            lambda v: v["counts"].update(outputBytes=False), lambda v: v.update(admitted=[{}]),
            lambda v: v.update(misses=[{"index": 0, "reason": "BUDGET_NOT_STARTED", "rejected": 0}]),
            lambda v: v.update(stageReturnBindingSha256="0" * 64),
            lambda v: v.update(stageEvidenceSha256="0" * 64), lambda v: v.update(sourceIdentity=[1, 2]),
            lambda v: v.update(homeIdentity=[1, 2]), lambda v: v.update(completed=1),
            lambda v: v.update(testAcceptance="PASS"), lambda v: v.update(unknown="extra"))
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.fail(lambda: self.reserve(staged=self.seed_mutant(change)))
                self.assertFalse(self.f.owner.resources)
        self.assertFalse(self.directory.exists())

    def test_missing_declared_artifact_cannot_be_a_complete_empty_inventory(self):
        staged = self.seed_mutant(lambda v: v.update(misses=[]))
        parent = F.record(staged.raw)
        # Reach the inventory boundary with a coherently hash-bound synthetic
        # parent, not the earlier original-byte mismatch guard. No source change.
        parent["leafSha256"] = F.digest(staged.seed_leaf.raw)
        staged = replace(staged, raw=F.encoded(parent))
        self.fail(lambda: self.reserve(staged=staged), "SEED_INVENTORY")
        self.assertTrue(self.f.owner.resources)
        self.assertTrue(all(r["attempted"] and r["closed"] for r in self.f.owner.resources))
        self.assertFalse(self.directory.exists())

    def test_seed_leaf_must_reference_stage_leaf_not_stage_parent(self):
        staged = self.seed_mutant(lambda v: v["window"].update(predecessorSha256=F.digest(self.staged.stage_raw)))
        self.fail(lambda: self.reserve(staged=staged), "SEED_CHRONOLOGY")
        self.assertFalse(self.f.owner.resources)

    def test_seed_parent_must_reference_stage_parent_not_stage_leaf(self):
        staged = self.parent_mutant("raw", lambda v: v.update(predecessorSha256=F.digest(self.staged.stage_leaf.raw)))
        self.fail(lambda: self.reserve(staged=staged), "PARENT_BINDING")

    def test_parent_completion_and_original_window_cannot_be_relabelled(self):
        changes = (lambda v: v.update(schema=True), lambda v: v.update(parentResourceClose="PENDING"),
            lambda v: v.update(leafCheckedNs=True), lambda v: v.update(exportSaveAuthority=True),
            lambda v: v.update(predecessorCheckedNs=0), lambda v: v["window"].update(hardEndNs=99999 * NS),
            lambda v: v.update(closedNs=99999 * NS), lambda v: v.update(resourceCount=True),
            lambda v: v.update(extra="field"))
        for change in changes:
            with self.subTest(change=changes.index(change)):
                self.fail(lambda: self.reserve(staged=self.parent_mutant("raw", change)))
                self.assertFalse(self.f.owner.resources)

    def test_start_before_final_parent_raw_is_rejected_even_after_leaf_finished(self):
        phase = replace(self.phase, first=O.clocks.Reading(self.f.clock, self.staged.checked_ns - 1))
        self.fail(lambda: self.reserve(phase=phase), "PREDECESSOR_CLOCK")
        self.assertFalse(self.f.owner.resources)

    def test_start_before_final_parent_local_is_rejected(self):
        self.fail(lambda: self.reserve(phase=replace(self.phase, local_started=self.staged.checked_local - 0.01)),
                  "PREDECESSOR_CLOCK")

    def test_original_custody_cumulative_fence_is_not_renewed(self):
        end = self.f.proposal["phaseFencesNs"]["custody-prepare"]
        phase = replace(self.phase, first=O.clocks.Reading(self.f.clock, end))
        self.fail(lambda: self.reserve(phase=phase), "ORIGINAL_PHASE_EXPIRED")
        self.assertFalse(self.directory.exists())

    def test_existing_empty_custody_is_never_adopted_deleted_or_rerolled(self):
        self.directory.mkdir(mode=0o700)
        identity = self.f.identity(self.directory)
        self.fail(kind=FileExistsError)
        self.assertEqual(self.f.identity(self.directory), identity)
        self.assertFalse(tuple(self.directory.iterdir()))
        self.uuid_call.assert_called_once()

    def test_preexisting_evidence_blocks_reservation_without_touching_it(self):
        occupied = self.f.state / "evidence" / RESERVED.hex
        occupied.mkdir(mode=0o700)
        self.fail(reason="DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assertTrue(occupied.is_dir())
        self.uuid_call.assert_not_called()
        self.assertFalse(self.directory.exists())

    def test_preexisting_cancellation_blocks_reservation_without_touching_it(self):
        occupied = self.f.state / "cancellations" / (RESERVED.hex + ".json")
        self.f.write(occupied, b"SYNTHETIC ORIGINAL CANCELLATION")
        self.fail(reason="DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assertEqual(occupied.read_bytes(), b"SYNTHETIC ORIGINAL CANCELLATION")
        self.uuid_call.assert_not_called()

    def test_loader_or_other_home_member_is_refused_not_removed(self):
        (self.f.home / "init.d").mkdir(mode=0o700)
        self.fail(reason="DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assertTrue((self.f.home / "init.d").is_dir())
        self.assertFalse(self.directory.exists())

    def test_nonempty_restore_is_not_empty_seed_or_cleanup_authority(self):
        self.f.write(self.f.restore / "payload", b"SYNTHETIC NOT A DEPENDENCY")
        self.fail(reason="DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assertEqual((self.f.restore / "payload").read_bytes(), b"SYNTHETIC NOT A DEPENDENCY")

    def test_replaced_state_with_equal_bytes_is_not_original(self):
        self.f.state.rename(self.f.session / "old-state")
        shutil.copytree(self.f.session / "old-state", self.f.state)
        self.fail(reason="INITIALIZER_REPLACED")

    def test_replaced_context_with_equal_bytes_is_not_original(self):
        old = self.f.state / "context.json"
        old.rename(self.f.session / "old-context.json")
        self.f.write(old, self.f.canonical_raw)
        self.fail(reason="FILE_REPLACED")

    def test_hardlinked_context_refuses_without_read_or_unlink(self):
        os.link(self.f.state / "context.json", self.f.session / "context-alias")
        self.fail(reason="IDENTITY_OR_KIND")
        self.assertTrue((self.f.session / "context-alias").exists())

    def test_fifo_context_refuses_nonblockingly_without_deleting_original(self):
        path = self.f.state / "context.json"
        path.rename(self.f.session / "old-context.json")
        os.mkfifo(path, mode=0o600)
        self.fail(reason="IDENTITY_OR_KIND")
        self.assertTrue((self.f.session / "old-context.json").is_file())

    def test_symlink_custody_root_refuses_without_following_it(self):
        target = self.f.base / "foreign"
        target.mkdir(mode=0o700)
        self.directory.symlink_to(target, target_is_directory=True)
        self.fail(kind=FileExistsError)
        self.assertFalse(tuple(target.iterdir()))
        self.assertTrue(self.directory.is_symlink())

    def test_synthetic_source_or_properties_drift_is_refused(self):
        self.f.write(self.f.home / "gradle.properties", self.f.properties + b"SYNTHETIC CHANGE\n")
        self.fail(reason="FILE_REPLACED")
        self.assertFalse(self.directory.exists())

    def test_new_source_supplier_drift_is_refused_without_byte_scope_expansion(self):
        original = C._sources
        calls = []
        def sources(*args):
            result = original(*args)
            calls.append(None)
            if len(calls) == 1:
                (self.f.root / C.CUSTODY_INPUTS[0]).write_bytes(b"SYNTHETIC CHANGED SOURCE")
            return result
        with patch.object(C, "_sources", sources):
            self.fail(reason="SOURCE_INPUT_CHANGED")
        self.assertEqual(len(calls), 2)
        self.assertTrue((self.directory / "request.json").is_file())
        self.assertFalse(tuple(self.f.restore.iterdir()))

    def test_uuid_wrong_type_or_version_refuses_without_retry_or_output(self):
        for value in (SimpleNamespace(hex=RESERVED.hex), uuid.UUID(int=1)):
            with self.subTest(value=type(value).__name__):
                # Each case fails after file reads; allocate a distinct tiny test
                # owner, never rehabilitate an earlier failed production owner.
                owner = FIXTURES.S.Owner(self.f.local + 1000, cancelled=lambda: None)
                with patch.object(C.uuid, "uuid4", return_value=value) as supplier:
                    self.fail(lambda: self.reserve(parent=owner), "INVOCATION_SUPPLIER", owner=owner)
                supplier.assert_called_once()
                self.assertTrue(all(r["attempted"] and r["closed"] for r in owner.resources))
        self.assertFalse(self.directory.exists())

    def test_uuid_collision_with_canonical_job_is_not_rerolled(self):
        canonical = F.record(self.f.canonical_raw)
        canonical["id"] = RESERVED.hex
        raw = F.encoded(canonical)
        self.f.write(self.f.state / "context.json", raw)
        originals = replace(self.f.originals, canonical_raw=raw)
        # Rebind this entirely synthetic predecessor consistently BEFORE entry.
        inputs = B._Inputs(originals, B._capture(originals))
        stage = F.record(self.staged.stage_leaf.raw)
        stage["binding"] = inputs.binding()
        stage["fileBindings"]["canonical-context"] = F._info_binding(F._info((self.f.state / "context.json").stat()))
        stage_leaf = replace(self.staged.stage_leaf, raw=F.encoded(stage))
        seed = F.record(self.staged.seed_leaf.raw)
        seed.update(binding=stage["binding"], fileBindings=stage["fileBindings"], stageEvidenceSha256=F.digest(stage_leaf.raw),
            stageReturnBindingSha256=F.digest(F.encoded({"rawSha256": F.digest(stage_leaf.raw), "checkedNs": stage_leaf.checked_ns,
                "localStarted": stage_leaf.local_started, "localChecked": stage_leaf.checked_local})))
        seed["window"]["predecessorSha256"] = F.digest(stage_leaf.raw)
        seed_leaf = replace(self.staged.seed_leaf, raw=F.encoded(seed))
        stage_parent = self.parent_record(stage_leaf, originals.initializer_closed_raw, originals.initializer_checked_ns)
        seed_parent = self.parent_record(seed_leaf, stage_parent, F.record(self.staged.raw)["predecessorCheckedNs"])
        staged = replace(self.staged, stage_raw=stage_parent, raw=seed_parent, stage_leaf=stage_leaf, seed_leaf=seed_leaf)
        self.fail(lambda: self.reserve(originals=originals, staged=staged), "INVOCATION_COLLISION")
        self.uuid_call.assert_called_once()
        self.assertFalse(self.directory.exists())

    def test_no_caller_id_command_path_ancestry_duration_or_recipient_overrides(self):
        self.assertEqual(tuple(inspect.signature(C.reserve_configuration).parameters), ("parent", "originals", "phase", "staged"))
        for name in ("invocation", "argv", "directory", "ancestor_invocations", "timeout", "recipient"):
            with self.subTest(name=name):
                self.fail(lambda: self.reserve(**{name: "SYNTHETIC FORBIDDEN"}), kind=TypeError)
        self.uuid_call.assert_not_called()
        self.assertFalse(self.f.owner.resources)

    def test_staged_container_mutation_in_uuid_callback_is_not_admitted(self):
        def mutate():
            object.__setattr__(self.staged, "checked_ns", self.staged.checked_ns + 1)
            return RESERVED
        with patch.object(C.uuid, "uuid4", side_effect=mutate):
            self.fail(reason="STAGED_INPUT_CHANGED")
        self.assertFalse(self.directory.exists())

    def test_original_phase_mutation_cannot_widen_the_saved_window(self):
        def mutate():
            object.__setattr__(self.phase, "local_started", self.phase.local_started + 999)
            return RESERVED
        with patch.object(C.uuid, "uuid4", side_effect=mutate):
            self.fail(reason="PHASE_CHANGED")
        self.assertFalse(self.directory.exists())

    def test_cancellation_preserves_the_exact_falsey_first_error(self):
        first = FIXTURES.FalseyFailure("SYNTHETIC FIRST CANCELLATION")
        def cancel():
            raise first
        self.f.callback = cancel
        self.assertIs(self.fail(kind=FIXTURES.FalseyFailure), first)
        self.assertFalse(self.directory.exists())
        self.assertFalse(self.f.owner.resources)

    def test_keyboard_interrupt_is_not_normalized_to_failure_code_or_retried(self):
        first = KeyboardInterrupt()
        with patch.object(C.uuid, "uuid4", side_effect=first) as supplier:
            self.assertIs(self.fail(kind=KeyboardInterrupt), first)
        supplier.assert_called_once()
        self.assertFalse(self.directory.exists())

    def test_short_write_preserves_partial_request_and_known_leaf_closes(self):
        original = F.PosixFile.write
        writes = []
        def write(file, raw):
            if file.path.name == "request.json":
                writes.append(None)
                if len(writes) == 1:
                    return original(file, raw[:5])
                return 0
            return original(file, raw)
        with patch.object(F.PosixFile, "write", write):
            self.fail(reason="SHORT_WRITE")
        self.assertEqual((self.directory / "request.json").stat().st_size, 5)
        self.assertTrue(all(r["attempted"] and r["closed"] for r in self.f.owner.resources))

    def test_sync_failure_is_preserved_after_request_bytes_are_written(self):
        first = RuntimeError("SYNTHETIC SYNC FAILURE")
        original = F.PosixFile.sync
        def sync(file):
            if file.path.name == "request.json":
                raise first
            return original(file)
        with patch.object(F.PosixFile, "sync", sync):
            self.assertIs(self.fail(), first)
        self.assertTrue((self.directory / "request.json").stat().st_size > 0)
        self.assertTrue(all(r["attempted"] and r["closed"] for r in self.f.owner.resources))

    def test_request_readback_replacement_is_not_successful_retention(self):
        original = C._write_request
        def write(*args):
            result = original(*args)
            (self.directory / "request.json").write_bytes(b"SYNTHETIC REPLACEMENT")
            return result
        with patch.object(C, "_write_request", write):
            self.fail(reason="FILE_REPLACED")
        self.assertEqual((self.directory / "request.json").read_bytes(), b"SYNTHETIC REPLACEMENT")

    def test_raw_exact120_expiry_cannot_borrow_final_or_read_reserves(self):
        def late():
            self.f.ns = self.phase.first.nanoseconds + 120 * NS
            return RESERVED
        with patch.object(C.uuid, "uuid4", side_effect=late):
            self.fail(reason="ORIGINAL_PHASE_EXPIRED")
        self.assertFalse(self.directory.exists())

    def test_local_exact120_expiry_cannot_be_hidden_by_early_raw(self):
        def late():
            self.f.local = self.phase.local_started + 120
            return RESERVED
        with patch.object(C.uuid, "uuid4", side_effect=late):
            self.fail(reason="ORIGINAL_PHASE_EXPIRED")
        self.assertFalse(self.directory.exists())

    def test_backwards_raw_supplier_does_not_reset_the_clock(self):
        def backwards():
            self.f.ns = self.phase.first.nanoseconds - NS
            return RESERVED
        with patch.object(C.uuid, "uuid4", side_effect=backwards):
            self.fail(reason="CLOCK_CHANGED_OR_BACKWARDS")

    def test_late_final_serialization_fails_even_after_known_leaf_close(self):
        original = F.encoded
        def encoded(value):
            raw = original(value)
            if type(value) is dict and value.get("scope") == C.SCOPE and value.get("completed") is True:
                self.f.local = self.phase.local_started + 120
            return raw
        with patch.object(F, "encoded", encoded):
            self.fail(reason="ORIGINAL_PHASE_EXPIRED")
        self.assertTrue(all(r["attempted"] and r["closed"] for r in self.f.owner.resources))
        self.assertFalse(self.f.owner.unknown)

    def test_post_acquisition_failure_keeps_returned_handle_for_known_close(self):
        original = self.f.owner.acquire
        first = RuntimeError("SYNTHETIC AFTER FACTORY RETURN")
        def acquire(label, factory):
            resource = original(label, factory)
            if label == "bootstrap-leaf-custody-directory":
                raise first
            return resource
        with patch.object(self.f.owner, "acquire", acquire):
            self.assertIs(self.fail(), first)
        self.assertTrue(self.directory.is_dir())
        self.assertTrue(all(r["attempted"] and r["closed"] for r in self.f.owner.resources))

    def test_unknown_close_cannot_create_more_owners_or_successful_reservation(self):
        original = self.f.owner.close_one
        first = RuntimeError("SYNTHETIC CLOSE UNKNOWN")
        calls = []
        def close(resource):
            if getattr(resource, "path", Path("/")) == self.directory / "request.json":
                calls.append(resource)
                self.f.owner.error("model-close", first, unknown=True)
                raise first
            return original(resource)
        with patch.object(self.f.owner, "close_one", close):
            error = self.fail()
        self.assertIs(error, first)
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.f.owner.unknown)
        self.assertEqual(error.bootstrap_custody_result["status"], "UNKNOWN")
        self.assertTrue(error.bootstrap_custody_resources)

    def test_no_delete_installer_generated_command_or_dependency_transfer(self):
        with patch.object(os, "unlink", side_effect=AssertionError("NO_DELETE")), \
                patch.object(shutil, "rmtree", side_effect=AssertionError("NO_DELETE")):
            value = self.reserve()
        self.assertEqual(F.record(value.raw)["status"], "RESERVED_CONFIGURATION_ONLY")
        self.assertEqual(F.record(value.request_raw)["loader"], "NOT_INSTALLED_BY_CONFIGURATION_RESERVATION")
        self.assertEqual(C.CUSTODY_INPUTS, ("scripts/hosted_cache_bootstrap_custody.py",))
        self.assertEqual(B.allocation.policy()["proposedJobSeconds"], 5400)
        self.assertEqual(B.allocation.policy()["windowsNativeFileSeconds"], 900)


if __name__ == "__main__":
    unittest.main()
