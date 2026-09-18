#!/usr/bin/env python3
"""Tiny offline bootstrap leaf controls; NOT original/native/hosted evidence.

Actual ordinary-UID POSIX file suppliers and bootstrap Owner run on synthetic
files. Admission, service/initializer originals and clocks are models. No real
initializer, native child, Java/Gradle, dependency copier, download or provider.
Historical test modules supply fixtures only; their test classes are not selected.
"""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_staging as B


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


M = load("bootstrap_staging_origin_fixtures", Path(__file__).with_name("hosted-cache-bootstrap-origin-test.py"))
S, O, F, NS = M.S, B.origin, B.files, B.NS


def metadata():
    rows = "".join('<component group="org.fixture" name="' + name + '" version="1.0">' +
        '<artifact name="' + name + '.jar"><sha256 value="' + F.digest(name.encode()) +
        '"/></artifact></component>' for name in ("First", "Second"))
    return ('<?xml version="1.0" encoding="UTF-8"?><verification-metadata xmlns="' + F.authority.NAMESPACE +
        '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="' + F.authority.SCHEMA_LOCATION +
        '"><configuration><verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures>' +
        '</configuration><components>' + rows + '</components></verification-metadata>').encode()


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class LeafModels(unittest.TestCase):
    def setUp(self):
        self.assertEqual(os.name, "posix", "These controls require actual POSIX suppliers")
        self.assertNotEqual(os.getuid(), 0, "Run the tiny fixtures as an ordinary UID")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-bootstrap-staging-model-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir(mode=0o700)
        for name in sorted(set((*F.INPUTS, *B.BOOTSTRAP_INPUTS))):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
            path.write_bytes(metadata() if name == F.INPUTS[0] else
                             ("SYNTHETIC SOURCE BINDING; NEVER EXECUTED: " + name + "\n").encode())
            path.chmod(0o644)
        self.admitted, self.clock, _unused_env = M.model_admission()
        self.responses = {name: M.response(self.admitted, self.clock, name, body, start=(1001 + index) * NS)
            for index, (name, body) in enumerate(M.service_bodies(self.admitted, self.clock).items())}
        self.proposal = B.allocation.derive(self.admitted, self.responses, "e" * 32, self.clock, M.RUNNER)
        self.original = self.base / "p2pkit-cache-originals-123-1-desktop-linux-x64"
        self.session = self.original.with_name(self.original.name + "-productive") / "initializer"
        self.session.mkdir(parents=True, mode=0o700)
        self.session.parent.chmod(0o700)
        for name in ("canonical-init", "control-home", "temporary", "state", "state/gradle-home",
                     "state/evidence", "state/cancellations"):
            (self.session / name).mkdir(mode=0o700)
        self.state, self.home = self.session / "state", self.session / "state/gradle-home"
        self.properties = B.initialization.properties(("/synthetic/jdk17", "/synthetic/jdk21"))
        source = {**O.parse(self.admitted.record)["source"], "status": "", "diffSha256": F.digest(b"")}
        self.canonical = {"schema": 1, "root": str(self.root), "expectedCommit": source["commit"],
            "tree": source["tree"], "source": source, "host": "linux-x64", "gradleHome": str(self.home),
            "createdUtc": "2026-09-18T00:00:00+00:00", "id": "a" * 32,
            "gradlePropertiesSha256": F.digest(self.properties), "javaHomes": ["/synthetic/jdk17", "/synthetic/jdk21"],
            "preexistingOutputPaths": []}
        # Deliberately canonical-initializer style, NOT files.encoded().
        self.canonical_raw = (json.dumps(self.canonical, sort_keys=True, indent=2) + "\n").encode()
        self.context = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PARENT_CONTEXT_V1", "job": "b" * 32,
            "previousSha256": "c" * 64, "requestSha256": "d" * 64, "admissionSha256": F.digest(self.admitted.record),
            "clock": O.clock_value(self.clock), "directories": {name: self.identity(self.session if name == "session"
                else self.session / name) for name in ("session", "canonical-init", "control-home", "temporary")},
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        self.context_raw = O.encoded(self.context)
        self.closed = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PREFIX_CLOSED_NO_EXECUTION_V1",
            "recipientClosedSha256": "c" * 64, "pendingSha256": "f" * 64,
            "window": {"clock": O.clock_value(self.clock), "firstNs": 1003 * NS, "workEndNs": 1123 * NS,
                "nativeEndNs": 1168 * NS, "prefixEndNs": 1198 * NS, "finalStartedNs": 1004 * NS,
                "finalEndNs": 1049 * NS, "readStartedNs": 1005 * NS, "readEndNs": 1035 * NS,
                "budgetAcceptance": "NOT_ADMITTED"}, "closedNs": 1006 * NS, "resourceCount": 17,
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "childReturn": "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        self.write(self.session / "initializer-context.json", self.context_raw)
        self.write(self.state / "context.json", self.canonical_raw)
        self.write(self.home / "gradle.properties", self.properties)
        self.originals = B.Originals(self.admitted, self.responses, "e" * 32, self.clock, M.RUNNER,
            O.encoded(self.proposal), str(self.original), self.context_raw, self.canonical_raw, self.properties,
            {name: self.identity(self.session if name == "session" else self.state if name == "state" else self.state / name)
                for name in B.DIRECTORIES}, O.encoded(self.closed), 1006 * NS + 1, 400.0)
        self.ns, self.local = 1100 * NS, 500.0
        self.callback = lambda: None
        self.stack.enter_context(patch.object(B, "ROOT", self.root))
        self.stack.enter_context(patch.object(O.clocks, "observe", side_effect=self.observe))
        self.stack.enter_context(patch.object(B.time, "monotonic", side_effect=lambda: self.local))
        for target, name in ((subprocess, "Popen"), (subprocess, "run"), (os, "system"),
                (socket, "socket"), (socket, "create_connection"), (S.processes, "make_scope"),
                (S.processes, "host_role"), (S.query, "NativeGitQueries"), (F, "_copy_allowlisted"),
                (B.cache, "export_snapshot"), (B.cache, "save_set"),
                (O.http.client, "HTTPSConnection"), (O.ssl, "create_default_context")):
            self.stack.enter_context(patch.object(target, name, side_effect=AssertionError("NO_NATIVE_NETWORK_OR_DEPENDENCY_WRITER")))
        self.owner = S.Owner(self.local + 1000, cancelled=lambda: self.callback())
        self.addCleanup(self.retire_tiny_fixtures)
        self.container = F.stage_path(self.session, "desktop", "linux-x64")
        self.restore = self.container / "restore-home"

    def retire_tiny_fixtures(self):
        # Test-owned POSIX pins only; no production UNKNOWN rehabilitation.
        for row in reversed(self.owner.resources):
            resource = row["owner"]
            if isinstance(resource, (F.PosixFile, F._PosixDirectory)) and not resource.closed:
                try:
                    resource.close()
                except BaseException:
                    pass

    @staticmethod
    def identity(path):
        info = path.stat()
        return [info.st_dev, info.st_ino]

    @staticmethod
    def write(path, raw):
        path.write_bytes(raw)
        path.chmod(0o600)

    def observe(self):
        self.ns += 1000
        return O.clocks.Reading(self.clock, self.ns)

    def phase(self):
        return B.PhaseStart(O.clocks.Reading(self.clock, self.ns), self.local)

    def stage(self, *, phase=None, originals=None):
        return B.stage_empty(self.owner, self.originals if originals is None else originals,
                             self.phase() if phase is None else phase)

    def seed(self, stage, *, phase=None, originals=None):
        return B.observe_empty_seed(self.owner, self.originals if originals is None else originals,
                                    self.phase() if phase is None else phase, stage)

    def known_leaves(self):
        self.assertIsNone(self.owner.original)
        self.assertFalse(self.owner.unknown)
        self.assertFalse(self.owner.closed)
        self.assertTrue(self.owner.resources)
        self.assertTrue(all(row["attempted"] is True and row["closed"] is True for row in self.owner.resources))

    def unchanged_home(self):
        self.assertEqual({path.name for path in self.home.iterdir()}, {"gradle.properties"})
        self.assertEqual((self.home / "gradle.properties").read_bytes(), self.properties)
        self.assertFalse(tuple(self.restore.iterdir()))

    def failed(self, invoke, reason=None, kind=Exception):
        assertion = self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)
        with assertion as caught:
            invoke()
        error = caught.exception
        if hasattr(error, "bootstrap_leaf_result"):
            self.assertFalse(error.bootstrap_leaf_result["completed"])
            self.assertIs(error.bootstrap_leaf_result["nextPhaseAuthority"], False)
            self.assertIs(error.bootstrap_leaf_result["exportSaveAuthority"], False)
            self.assertIs(self.owner.original, error)
        return error

    def test_stage_exclusively_creates_only_two_container_members_and_keeps_parent_live(self):
        phase = self.phase()
        result = self.stage(phase=phase)
        value = F.record(result.raw)
        self.assertEqual(value["scope"], "BOOTSTRAP_EMPTY_STAGING_LEAF_V1")
        self.assertEqual(value["status"], "KNOWN_EMPTY_OBSERVED")
        self.assertEqual({path.name for path in self.container.iterdir()}, {"restore-home", "staging.json"})
        self.assertEqual((self.container / "staging.json").read_bytes(), result.staging_raw)
        self.assertEqual(value["window"]["hardEndNs"], phase.first.nanoseconds + 120 * NS)
        self.assertEqual(value["window"]["softEndNs"], value["window"]["hardEndNs"])
        self.assertLess(value["window"]["finishedNs"], result.checked_ns)
        self.assertEqual(value["plan"]["mode"], "bootstrap")
        self.assertEqual(value["plan"]["profile"], "desktop")
        self.assertEqual(value["binding"]["admissionSha256"], F.digest(self.admitted.record))
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(value["nextPhaseAuthority"], False)
        self.assertIs(value["exportSaveAuthority"], False)
        self.known_leaves()
        self.unchanged_home()

    def test_seed_is_read_only_complete_absence_not_budget_omission_or_provider_result(self):
        stage = self.stage()
        before = {str(path): (path.read_bytes(), self.identity(path)) for path in self.session.parent.rglob("*") if path.is_file()}
        phase = self.phase()
        result = self.seed(stage, phase=phase)
        value = F.record(result.raw)
        after = {str(path): (path.read_bytes(), self.identity(path)) for path in self.session.parent.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(value["scope"], "BOOTSTRAP_KNOWN_EMPTY_SEED_LEAF_V1")
        self.assertEqual(value["counts"], {key: 0 for key in B.COUNTERS})
        self.assertEqual(value["admitted"], [])
        self.assertEqual(value["misses"], [{"index": 0, "reason": "ABSENT", "rejected": 0},
                                          {"index": 1, "reason": "ABSENT", "rejected": 0}])
        self.assertEqual(value["byteScope"], "DEPENDENCY_BYTES_ONLY_METADATA_IO_OCCURRED")
        self.assertEqual(value["stageEvidenceSha256"], F.digest(stage.raw))
        self.assertEqual(value["window"]["predecessorCheckedNs"], stage.checked_ns)
        self.assertEqual(value["window"]["softEndNs"], phase.first.nanoseconds + 90 * NS)
        self.assertEqual(value["window"]["hardEndNs"], phase.first.nanoseconds + 120 * NS)
        self.assertEqual(value["enclosingOwnerRetirement"], "NOT_OBSERVED_HERE")
        self.known_leaves()
        self.unchanged_home()

    def test_exact_indented_canonical_original_is_bound_without_normalization(self):
        self.assertNotEqual(self.canonical_raw, F.encoded(self.canonical))
        stage = self.stage()
        self.assertEqual(F.record(stage.raw)["binding"]["canonicalContextSha256"], F.digest(self.canonical_raw))
        self.assertEqual((self.state / "context.json").read_bytes(), self.canonical_raw)

    def test_existing_empty_container_is_refused_without_adoption_or_deletion(self):
        self.container.mkdir(mode=0o700)
        original_id = self.identity(self.container)
        self.failed(self.stage, kind=FileExistsError)
        self.assertEqual(self.identity(self.container), original_id)
        self.assertEqual(tuple(self.container.iterdir()), ())
        self.assertFalse((self.container / "restore-home").exists())

    def test_seed_refuses_nonempty_s_even_an_empty_cache_directory(self):
        stage = self.stage()
        (self.restore / "caches").mkdir(mode=0o700)
        self.failed(lambda: self.seed(stage), "DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assertTrue((self.restore / "caches").is_dir())

    def test_seed_refuses_extra_h_member_without_copying_or_deleting_it(self):
        stage = self.stage()
        self.write(self.home / "extra.txt", b"SYNTHETIC EXTRA")
        self.failed(lambda: self.seed(stage), "DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assertEqual((self.home / "extra.txt").read_bytes(), b"SYNTHETIC EXTRA")

    def test_replaced_restore_directory_with_identical_emptiness_is_not_original(self):
        stage = self.stage()
        self.restore.rename(self.container / "old-restore-home")
        self.restore.mkdir(mode=0o700)
        self.failed(lambda: self.seed(stage), "STAGING_ADMISSION_OR_IDENTITY_CHANGED")

    def test_replaced_home_with_identical_properties_is_not_original(self):
        stage = self.stage()
        self.home.rename(self.state / "old-home")
        self.home.mkdir(mode=0o700)
        self.write(self.home / "gradle.properties", self.properties)
        self.failed(lambda: self.seed(stage), "INITIALIZER_REPLACED")

    def test_replaced_state_directory_cannot_rebind_original_home(self):
        self.state.rename(self.session / "old-state")
        shutil.copytree(self.session / "old-state", self.state)
        self.failed(self.stage, "INITIALIZER_REPLACED")

    def test_symlink_restore_alias_is_not_opened(self):
        stage = self.stage()
        self.restore.rename(self.container / "original-restore")
        self.restore.symlink_to(self.container / "original-restore", target_is_directory=True)
        self.failed(lambda: self.seed(stage), kind=OSError)
        self.assertTrue(self.restore.is_symlink())

    def test_replaced_identical_canonical_file_is_not_stage_bound_file(self):
        stage = self.stage()
        path = self.state / "context.json"
        path.rename(self.base / "original-context.json")
        self.write(path, self.canonical_raw)
        self.failed(lambda: self.seed(stage), "FILE_REPLACED")

    def test_changed_original_properties_refuse_before_staging_creation(self):
        self.write(self.home / "gradle.properties", self.properties + b"org.gradle.workers.max=3\n")
        self.failed(self.stage, "ORIGINAL_FILE_CHANGED")
        self.assertFalse(self.container.exists())

    def test_replaced_identical_staging_file_is_not_original(self):
        stage = self.stage()
        path = self.container / "staging.json"
        path.rename(self.base / "original-staging.json")
        self.write(path, stage.staging_raw)
        self.failed(lambda: self.seed(stage), "FILE_REPLACED")

    def test_changed_staging_bytes_do_not_supply_matching_return_custody(self):
        stage = self.stage()
        self.write(self.container / "staging.json", stage.staging_raw + b" ")
        self.failed(lambda: self.seed(stage), "FILE_REPLACED")

    def test_allowlist_change_after_stage_refuses_even_when_s_remains_empty(self):
        stage = self.stage()
        path = self.root / F.INPUTS[0]
        path.write_bytes(metadata().replace(F.digest(b"First").encode(), F.digest(b"Changed").encode()))
        self.failed(lambda: self.seed(stage), "SOURCE_INPUTS_CHANGED")
        self.unchanged_home()

    def test_bootstrap_source_change_after_stage_refuses_separately_from_provider_key(self):
        stage = self.stage()
        path = self.root / B.BOOTSTRAP_INPUTS[0]
        path.write_bytes(b"SYNTHETIC CHANGED BOOTSTRAP SOURCE\n")
        self.failed(lambda: self.seed(stage), "SOURCE_INPUTS_CHANGED")

    def test_ordinary_or_relabelled_admission_cannot_select_bootstrap_leaf(self):
        value = O.parse(self.admitted.record)
        value["profile"] = "desktop"
        changed = replace(self.originals, admitted=replace(self.admitted, record=O.encoded(value)))
        self.failed(lambda: self.stage(originals=changed), "BOOTSTRAP_CACHE_IDENTITY")
        self.assertEqual(self.owner.resources, [])

    def test_wrong_cache_cohort_is_rejected_before_acquisition(self):
        value = O.parse(self.admitted.record)
        value["cacheCohort"]["profile"] = "full"
        changed = replace(self.originals, admitted=replace(self.admitted, record=O.encoded(value)))
        self.failed(lambda: self.stage(originals=changed), "COHORT_OR_EXECUTION_CHANGED")
        self.assertEqual(self.owner.resources, [])

    def test_changed_original_response_encoding_cannot_validate_old_proposal(self):
        changed = replace(self.originals, responses={**self.responses, "jobs": self.responses["jobs"] + b" "})
        self.failed(lambda: self.stage(originals=changed), "PROPOSAL_CHANGED")
        self.assertEqual(self.owner.resources, [])

    def test_changed_proposal_does_not_select_a_new_budget(self):
        proposal = dict(self.proposal, proposedJobEndNs=self.proposal["proposedJobEndNs"] + NS)
        changed = replace(self.originals, proposal_raw=O.encoded(proposal))
        self.failed(lambda: self.stage(originals=changed), "PROPOSAL_CHANGED")
        self.assertEqual(self.owner.resources, [])

    def test_changed_runner_is_not_inferred_from_matching_digest(self):
        self.failed(lambda: self.stage(originals=replace(self.originals, runner_name="SYNTHETIC DIFFERENT")), "SERVICE_RUNNER")
        self.assertEqual(self.owner.resources, [])

    def test_initializer_layout_is_derived_not_an_independent_home_choice(self):
        self.failed(lambda: self.stage(originals=replace(self.originals, original_session=str(self.base / "chosen-home"))),
                    "INITIALIZER_LAYOUT")
        self.assertEqual(self.owner.resources, [])

    def test_initializer_claim_with_no_original_work_interval_is_refused_before_acquisition(self):
        fences = self.proposal["phaseFencesNs"]
        began = fences["canonical-init"] + 1
        window = self.closed["window"]
        window.update(firstNs=began, workEndNs=fences["canonical-init"],
            nativeEndNs=min(began + 165 * NS, fences["canonical-init-final"]),
            prefixEndNs=min(began + 195 * NS, fences["canonical-init-read"]),
            finalStartedNs=began + 1, readStartedNs=began + 2)
        window["finalEndNs"] = min(window["nativeEndNs"], window["finalStartedNs"] + 45 * NS)
        window["readEndNs"] = min(window["prefixEndNs"], window["readStartedNs"] + 30 * NS)
        self.closed["closedNs"] = began + 3
        changed = replace(self.originals, initializer_closed_raw=O.encoded(self.closed), initializer_checked_ns=began + 4)
        self.ns = began + 5
        self.assertLess(window["workEndNs"], window["firstNs"])
        self.failed(lambda: self.stage(originals=changed), "INITIALIZER_CHRONOLOGY")
        self.assertEqual(self.owner.resources, [])
        self.assertFalse(self.container.exists())

    def test_initializer_first_must_not_precede_original_service_response_completion(self):
        service_last = self.proposal["serviceTimeBasis"]["service"]["lastNs"]
        began = service_last - 1
        window = self.closed["window"]
        window.update(firstNs=began, workEndNs=began + 120 * NS, nativeEndNs=began + 165 * NS,
            prefixEndNs=began + 195 * NS, finalStartedNs=service_last, finalEndNs=service_last + 45 * NS,
            readStartedNs=service_last, readEndNs=service_last + 30 * NS)
        self.closed["closedNs"] = service_last
        changed = replace(self.originals, initializer_closed_raw=O.encoded(self.closed),
                          initializer_checked_ns=service_last)
        self.ns = service_last + 1
        self.assertLess(window["firstNs"], service_last)
        self.failed(lambda: self.stage(originals=changed), "INITIALIZER_CHRONOLOGY")
        self.assertEqual(self.owner.resources, [])
        self.assertFalse(self.container.exists())

    def test_mutable_input_change_during_callback_cannot_replace_frozen_originals(self):
        original_jobs = self.responses["jobs"]
        def mutate():
            self.responses["jobs"] = original_jobs + b" "
        self.callback = mutate
        self.failed(self.stage, "CALLER_INPUT_CHANGED")
        self.assertEqual(self.owner.resources, [])

    def test_nominally_frozen_admission_change_during_callback_is_refused(self):
        self.callback = lambda: object.__setattr__(self.admitted, "record", self.admitted.record + b" ")
        self.failed(self.stage, "CALLER_INPUT_CHANGED")
        self.assertEqual(self.owner.resources, [])

    def test_phase_replacement_during_callback_cannot_renew_the_original_first(self):
        phase = self.phase()
        self.callback = lambda: object.__setattr__(phase, "first", O.clocks.Reading(self.clock, self.ns + 100 * NS))
        self.failed(lambda: self.stage(phase=phase), "PHASE_CHANGED")
        self.assertEqual(self.owner.resources, [])

    def test_post_allocation_clock_failure_keeps_and_closes_actual_parent_only_registration(self):
        first = FalseyFailure("SYNTHETIC_POST_ALLOCATION")
        original_factory, original_end = F.private_root, self.owner.end
        allocated, fail = [], []
        def factory(*args, **kwargs):
            value = original_factory(*args, **kwargs)
            allocated.append(value)
            fail.append(True)
            return value
        def end(**kwargs):
            if fail:
                fail.pop()
                raise first
            return original_end(**kwargs)
        with patch.object(F, "private_root", factory), patch.object(self.owner, "end", end):
            error = self.failed(self.stage, kind=FalseyFailure)
        self.assertIs(error, first)
        self.assertIs(self.owner.original, first)
        self.assertEqual(len(allocated), 1)
        self.assertTrue(allocated[0].closed)
        self.assertEqual(len(error.bootstrap_leaf_resources), 1)
        self.assertIs(error.bootstrap_leaf_resources[0][0], allocated[0])
        self.assertTrue(self.owner.resources[0]["closed"])
        self.assertFalse(self.owner.unknown)

    def test_falsey_retained_close_error_is_not_a_successful_leaf(self):
        first = FalseyFailure("SYNTHETIC_RETAINED_CLOSE_CLOCK")
        original = self.owner.close_fence
        injected = []
        def close_fence():
            if not injected:
                injected.append(True)
                self.owner.error("synthetic-close-clock", first)
            original()
        with patch.object(self.owner, "close_fence", close_fence):
            error = self.failed(self.stage, kind=FalseyFailure)
        self.assertIs(error, first)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.owner.resources))
        self.assertFalse(self.owner.unknown)

    def test_unknown_allocation_stops_acquisition_and_does_not_claim_known_cleanup(self):
        first = RuntimeError("SYNTHETIC_ALLOCATION_UNKNOWN")
        with patch.object(F, "private_root", side_effect=first) as supplier:
            error = self.failed(self.stage)
        self.assertIs(error, first)
        self.assertEqual(supplier.call_count, 1)
        self.assertEqual(self.owner.resources, [])
        self.assertTrue(self.owner.unknown)
        self.assertEqual(error.bootstrap_leaf_result["status"], "UNKNOWN")

    def test_unknown_close_cannot_start_any_later_file_acquisition(self):
        original, closures, acquired_after = F.PosixFile.close, [], []
        acquire = self.owner.acquire
        def close(stream):
            original(stream)
            if not closures:
                closures.append(True)
                raise RuntimeError("SYNTHETIC_CLOSE_UNKNOWN")
        def allocate(*args, **kwargs):
            if closures:
                acquired_after.append(args[0])
            return acquire(*args, **kwargs)
        with patch.object(F.PosixFile, "close", close), patch.object(self.owner, "acquire", allocate):
            error = self.failed(self.stage)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(error.bootstrap_leaf_result["status"], "UNKNOWN")
        self.assertEqual(acquired_after, [])
        self.assertFalse(self.owner.closed)

    def test_leaf_does_not_close_preexisting_parent_resource(self):
        class Resource:
            count = 0
            def close(self):
                self.count += 1
        borrowed = self.owner.acquire("existing-parent-resource", Resource)
        stage = self.stage()
        self.assertEqual(borrowed.count, 0)
        self.assertFalse(self.owner.resources[0]["attempted"])
        self.assertFalse(self.owner.closed)
        self.assertTrue(F.record(stage.raw)["completed"])

    def test_factory_return_of_preexisting_parent_resource_is_not_a_leaf_allocation(self):
        borrowed = self.owner.acquire("existing-parent-directory", lambda: F.private_root(self.session))
        row = self.owner.resources[0]
        with patch.object(F, "private_root", return_value=borrowed):
            error = self.failed(self.stage, "BOOTSTRAP_DUPLICATE_OWNER")
        self.assertFalse(borrowed.closed)
        self.assertIs(self.owner.resources[0], row)
        self.assertFalse(row["attempted"])
        self.assertFalse(row["closed"])
        self.assertEqual(error.bootstrap_leaf_resources, ())
        self.assertFalse(self.owner.unknown)
        self.assertFalse(self.owner.closed)

    def test_final_source_verification_error_survives_a_later_directory_close_error(self):
        first = FalseyFailure("SYNTHETIC_SOURCE_FINAL_VERIFY")
        secondary = RuntimeError("SYNTHETIC_SOURCE_CLOSE")
        read, verify, close = B._read, F._PosixDirectory.verify, F._PosixDirectory.close
        armed, raised, closed = [], [], []
        def read_last(*args, **kwargs):
            result = read(*args, **kwargs)
            if args[2] == Path(B.BOOTSTRAP_INPUTS[-1]).name:
                armed.append(True)
            return result
        def verify_final(directory):
            if armed and not raised and directory.path == self.root:
                raised.append(True)
                raise first
            return verify(directory)
        def close_after_error(directory):
            close(directory)
            if raised and not closed:
                closed.append(directory)
                raise secondary
        with patch.object(B, "_read", read_last), patch.object(F._PosixDirectory, "verify", verify_final), \
                patch.object(F._PosixDirectory, "close", close_after_error):
            error = self.failed(self.stage)
        self.assertEqual(len(raised), 1)
        self.assertEqual(len(closed), 1)
        self.assertIs(error, first)
        self.assertIs(self.owner.original, first)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(error.bootstrap_leaf_result["status"], "UNKNOWN")
        self.assertFalse(self.container.exists())

    def test_raw_hard120_includes_validation_and_refuses_before_acquisition(self):
        phase = self.phase()
        self.ns += 120 * NS
        error = self.failed(lambda: self.stage(phase=phase), "ORIGINAL_PHASE_EXPIRED")
        self.assertEqual(self.owner.resources, [])
        self.assertGreaterEqual(error.bootstrap_leaf_result["window"]["finishedNs"], phase.first.nanoseconds + 120 * NS)

    def test_local_hard120_expires_even_when_raw_is_live(self):
        phase = self.phase()
        self.local += 120
        self.failed(lambda: self.stage(phase=phase), "ORIGINAL_PHASE_EXPIRED")
        self.assertEqual(self.owner.resources, [])

    def test_seed_local_new_work90_is_not_renewed_to_another120(self):
        stage = self.stage()
        phase = self.phase()
        old_count = len(self.owner.resources)
        self.local += 90
        self.failed(lambda: self.seed(stage, phase=phase), "ORIGINAL_PHASE_EXPIRED")
        self.assertEqual(len(self.owner.resources), old_count)

    def test_raw_backwards_sample_preserves_the_last_valid_high_water(self):
        phase = self.phase()
        values = iter((phase.first.nanoseconds + 10, phase.first.nanoseconds + 9))
        with patch.object(O.clocks, "observe", side_effect=lambda: O.clocks.Reading(self.clock, next(values))):
            error = self.failed(lambda: self.stage(phase=phase), "RAW_CLOCK_CHANGED_OR_BACKWARDS")
        self.assertEqual(error.bootstrap_leaf_result["window"]["finishedNs"], phase.first.nanoseconds + 10)
        self.assertEqual(self.owner.resources, [])

    def test_local_backwards_sample_is_not_rehabilitated_by_raw_progress(self):
        phase = self.phase()
        values = iter((500.1, 500.05))
        with patch.object(B.time, "monotonic", side_effect=lambda: next(values)):
            self.failed(lambda: self.stage(phase=phase), "LOCAL_BACKWARDS")
        self.assertEqual(self.owner.resources, [])

    def test_original_cumulative_phase_fence_shortens_the_stage120(self):
        fence = self.proposal["phaseFencesNs"]["dependency-stage"]
        self.ns = fence - 10 * NS
        phase = self.phase()
        value = F.record(self.stage(phase=phase).raw)
        self.assertEqual(value["window"]["hardEndNs"], fence)
        self.assertLess(fence, phase.first.nanoseconds + 120 * NS)

    def test_seed_first_must_follow_stage_final_checked_highwater_not_file_write(self):
        stage = self.stage()
        phase = B.PhaseStart(O.clocks.Reading(self.clock, stage.checked_ns - 1), stage.checked_local)
        count = len(self.owner.resources)
        self.failed(lambda: self.seed(stage, phase=phase), "PREDECESSOR_CLOCK")
        self.assertEqual(len(self.owner.resources), count)

    def test_seed_local_first_must_follow_stage_return(self):
        stage = self.stage()
        phase = B.PhaseStart(O.clocks.Reading(self.clock, stage.checked_ns), stage.checked_local - 1)
        count = len(self.owner.resources)
        self.failed(lambda: self.seed(stage, phase=phase), "PREDECESSOR_CLOCK")
        self.assertEqual(len(self.owner.resources), count)

    def test_staging_json_alone_does_not_substitute_for_stage_leaf_return(self):
        stage = self.stage()
        count = len(self.owner.resources)
        self.failed(lambda: self.seed(replace(stage, raw=stage.staging_raw)), "STAGE_EVIDENCE_CHANGED")
        self.assertEqual(len(self.owner.resources), count)

    def test_final_serialization_failure_retains_partial_result_and_closed_handles(self):
        first = FalseyFailure("SYNTHETIC_FINAL_SERIALIZATION")
        encoded = F.encoded
        def encode(value):
            if value.get("scope") == B.STAGE_SCOPE and value.get("completed") is True:
                raise first
            return encoded(value)
        with patch.object(F, "encoded", encode):
            error = self.failed(self.stage, kind=FalseyFailure)
        self.assertIs(error, first)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.owner.resources))
        self.assertFalse(self.owner.unknown)
        self.assertEqual({path.name for path in self.container.iterdir()}, {"restore-home", "staging.json"})

    def test_late_clock_after_final_serialization_cannot_return_completed_evidence(self):
        phase = self.phase()
        encoded = F.encoded
        def encode(value):
            raw = encoded(value)
            if value.get("scope") == B.STAGE_SCOPE and value.get("completed") is True:
                self.ns = phase.first.nanoseconds + 120 * NS
            return raw
        with patch.object(F, "encoded", encode):
            error = self.failed(lambda: self.stage(phase=phase), "ORIGINAL_PHASE_EXPIRED")
        self.assertFalse(error.bootstrap_leaf_result["completed"])
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.owner.resources))

    def test_final_raw_supplier_return_at_local120_cannot_use_its_earlier_local_sample(self):
        phase = self.phase()
        encoded, final_samples, armed = F.encoded, [], []
        def encode(value):
            raw = encoded(value)
            if value.get("scope") == B.STAGE_SCOPE and value.get("completed") is True:
                armed.append(True)
            return raw
        def observe():
            value = self.observe()
            if armed:
                final_samples.append(value)
                if len(final_samples) == 2:
                    self.local = phase.local_started + 120
            return value
        with patch.object(F, "encoded", encode), patch.object(O.clocks, "observe", observe):
            error = self.failed(lambda: self.stage(phase=phase), "ORIGINAL_PHASE_EXPIRED")
        self.assertEqual(len(final_samples), 2)
        self.assertLess(self.ns, phase.first.nanoseconds + 120 * NS)
        self.assertFalse(error.bootstrap_leaf_result["completed"])
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.owner.resources))
        self.assertFalse(self.owner.unknown)

    def test_final_return_construction_failure_keeps_the_original_error(self):
        first = RuntimeError("SYNTHETIC_RETURN_CONSTRUCTION")
        with patch.object(B, "LeafEvidence", side_effect=first):
            error = self.failed(self.stage)
        self.assertIs(error, first)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.owner.resources))


if __name__ == "__main__":
    unittest.main()
