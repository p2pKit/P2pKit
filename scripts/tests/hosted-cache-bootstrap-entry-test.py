#!/usr/bin/env python3
"""Offline read-only bootstrap entry controls, never execution admission.

The existing fixture models native/query/clock/HTTP boundaries and uses only
tiny actual ordinary-UID POSIX files. Inherited cases are not counted again.
No product, canonical initializer, provider, cache or dependency execution.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import copy
from dataclasses import replace
import importlib.util
import io
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("bootstrap_entry_handoff_models",
    Path(__file__).with_name("hosted-cache-bootstrap-handoff-test.py"))
H = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = H
spec.loader.exec_module(H)
S, O = H.S, H.O
ACTUAL_ADMIT = S.admit


class EntryModels(H.HandoffModels):
    @contextmanager
    def actual_readmission_wrapper(self, *, final_failure=None):
        """Real admit() wrapper, explicit modeled native/identity supplier."""
        calls, case = [], self
        returned_admission = replace(self.admitted)
        class Supplier:
            unknown = False
            def __init__(self, root, directory, *, check_cancel, owner_deadlines):
                case.assertEqual(root, ROOT)
                case.assertNotIn(O.wire.TOKEN_ENV, os.environ)
                case.assertLessEqual(owner_deadlines[0], owner_deadlines[1])
                self.check = check_cancel
                self.owner = S.Owner(owner_deadlines[1])
                self.directory = self.owner.new(directory)
                calls.append("construct")
            def native_host_matches_actions(self):
                self.check()
                calls.append("native-model")
            def retain_admission(self, admitted):
                case.assertIs(admitted, returned_admission)
                calls.append("retain")
                for name, raw in (("admission.json", admitted.record), ("original-event.json", admitted.original_event),
                                  ("original-policy.json", admitted.original_policy), ("recipient-public.asc", admitted.public_key)):
                    self.owner.write(self.directory, name, raw)
            def _finalize(self, error):
                case.assertIsNone(error)
                calls.append("finalize")
                self.owner.write(self.directory, "session-result.json", {"schema": 1, "scope": "ORDINARY_GIT_QUERIES_ONLY",
                    "job": "b" * 32, "queries": [], "result": "READY_FOR_CALLER_SEAL", "retirement": "KNOWN",
                    "firstError": None, "errors": [], "readbacks": []})
                self.owner.close()
                if final_failure:
                    raise final_failure
        def identity(root, *, query_runner, expected):
            self.assertEqual(root, ROOT)
            self.assertIs(type(query_runner), Supplier)
            self.assertEqual(expected, returned_admission)
            calls.append("identity-model")
            return returned_admission
        with patch.object(S, "admit", side_effect=ACTUAL_ADMIT), \
                patch.object(S.query, "NativeGitQueries", Supplier), patch.object(S.bootstrap, "admit", side_effect=identity):
            yield calls, returned_admission

    @contextmanager
    def entry_call(self, *, before=None, after=None):
        original, calls = S.execution_entry, []
        def enter(owner, target, private, handoff_raw, context_raw, admitted, previous, fence):
            call = SimpleNamespace(owner=owner, target=target, private=private, handoff_raw=handoff_raw,
                context_raw=context_raw, admitted=admitted, before=previous, fence=fence)
            calls.append(call)
            if before:
                before(call)
            call.entry = original(call.owner, call.target, call.private, call.handoff_raw, call.context_raw,
                call.admitted, call.before, call.fence)
            if after:
                after(call)
            return call.entry
        with patch.object(S, "execution_entry", side_effect=enter):
            yield calls

    def failed_adoption(self, ack, exception, reason=None, *, cancelled=None):
        output = io.BytesIO()
        assertion = self.assertRaises(exception) if reason is None else self.assertRaisesRegex(exception, reason)
        with self.adopter(ack), patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)), assertion as caught:
            S.guarded(S.adopt_originals if cancelled is None else lambda _: S.adopt_originals(cancelled))
        self.assertEqual(output.getvalue(), b"")
        return caught.exception

    def reject_generated_record(self, change):
        """Model a bad internal record construction, not caller provenance.

        Actual owner/entry identities remain intact. These controls exercise
        the closed context/window checks, independently of copy rejection.
        """
        path, _, ack, _ = self.prepare_handoff()
        original, changed = O.encoded, []
        def encode(value):
            if type(value) is dict and value.get("scope") == S.ENTRY_SCOPE:
                value = copy.deepcopy(value)
                change(value)
                changed.append(True)
            return original(value)
        with patch.object(O, "encoded", side_effect=encode):
            self.failed_adoption(ack, ValueError)
        self.assertTrue(changed)
        self.assertFalse((path.with_name(path.name + "-adoption") / "adoption-result.json").exists())

    def test_entry_is_consumed_by_the_adoption_receipt_with_no_product_authority(self):
        path, _, ack, _ = self.prepare_handoff()
        original_files = {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
        with self.adopter(ack), self.entry_call() as calls:
            raw, public = self.public_adoption()
        self.assertEqual(len(calls), 1)
        call = calls[0]
        target = path.with_name(path.name + "-adoption")
        entry_raw = (target / "entry-context.json").read_bytes()
        entry = O.parse(entry_raw)
        receipt_raw = (target / "adoption-result.json").read_bytes()
        receipt = O.parse(receipt_raw)
        self.assertIs(call.owner.entry_original, call.entry)
        self.assertEqual(call.entry.raw, entry_raw)
        self.assertEqual(entry["scope"], "BOOTSTRAP_READ_ONLY_EXECUTION_ENTRY_V1")
        self.assertEqual(entry["profile"], "cache-bootstrap")
        self.assertEqual(entry["cacheCohort"], {"profile": "desktop", "role": "linux-x64"})
        self.assertEqual(entry["selection"], "desktop-linux-x64")
        self.assertEqual(entry["source"], O.parse(self.admitted.record)["source"])
        self.assertEqual(entry["github"], O.parse(self.admitted.record)["github"])
        self.assertEqual(entry["sessionIdentity"], [target.stat().st_dev, target.stat().st_ino])
        self.assertEqual(entry["preparation"]["handoffSha256"], ack["handoffSha256"])
        self.assertEqual(entry["prelude"], O.parse((path / "prelude.json").read_bytes()))
        self.assertEqual(receipt["schema"], 2)
        self.assertEqual(receipt["scope"], "BOOTSTRAP_READ_ONLY_ADOPTION_PENDING_RETURN_V2")
        self.assertEqual(receipt["entryContextSha256"], O.digest(entry_raw))
        self.assertEqual(receipt["originals"], entry["preparation"])
        self.assertEqual(receipt["readmission"], entry["readmission"])
        self.assertEqual(public["adoptionSha256"], O.digest(receipt_raw))
        for value in (entry, receipt, public):
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
            self.assertIs(value["exportSaveAuthority"], False)
        self.assertEqual(entry["retirement"], "PENDING_OWNER_CLOSE")
        self.assertTrue(call.owner.closed)
        self.assertFalse(call.owner.unknown)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in call.owner.resources))
        self.assertEqual(original_files, {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()})
        self.assertEqual((len(self.requests), len(self.scopes), len(self.admissions)), (2, 1, 3))
        self.assertEqual(set(public), {"scope", "adoptionSha256", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"})
        for private in (str(path), H.M.TOKEN, H.M.RUNNER, "entryContext", "preparation", "clock", "startedNs"):
            self.assertNotIn(private.encode(), raw)

    def test_window_preserves_first_metadata_readmission_and_original_prelude(self):
        path, _, ack, _ = self.prepare_handoff()
        observations = []
        def after(call):
            value = S.check_execution_entry(call.owner, call.target, call.entry, call.fence, retained=True)
            observations.append((value, call.owner.first, call.owner.early_last, call.owner.local_end, call.fence.last))
        with self.adopter(ack), self.entry_call(after=after):
            S.adopt_originals([])
        value, first, metadata, local_end, highwater = observations[0]
        window, prelude = value["window"], O.parse((path / "prelude.json").read_bytes())
        self.assertEqual(window["scope"], "BOOTSTRAP_ORIGINAL_PRELUDE_ENTRY_WINDOW_V1")
        self.assertEqual(window["clock"], O.clock_value(first.clock))
        self.assertEqual(window["adopterFirstNs"], first.nanoseconds)
        self.assertEqual(window["metadataLastNs"], metadata)
        self.assertGreater(metadata, first.nanoseconds)
        self.assertLess(metadata, window["readmissionReturnedNs"])
        self.assertLessEqual(window["readmissionReturnedNs"], window["startedNs"])
        self.assertLess(window["startedNs"], highwater)
        self.assertEqual(window["workEndNs"], prelude["firstNs"] + 75 * O.NS)
        self.assertEqual(window["finalEndNs"], prelude["firstNs"] + 120 * O.NS)
        self.assertLessEqual(local_end, first.nanoseconds / O.NS + 45)
        self.assertEqual(window["localCeiling"], "ORIGINAL_ADOPTER_IO45_ONLY_CAN_SHORTEN")

    def test_entry_uses_actual_outer_admit_return_not_only_the_fixture_registry(self):
        _, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack), self.actual_readmission_wrapper() as (calls, admitted), self.entry_call() as entries:
            S.adopt_originals([])
        self.assertEqual(calls, ["construct", "native-model", "identity-model", "retain", "finalize"])
        entry = entries[0].entry
        self.assertIs(entry.admitted, admitted)
        self.assertIsNot(entry.admitted, self.admitted)
        self.assertEqual(entry.admitted, self.admitted)
        self.assertIs(entries[0].owner.admissions[str(entries[0].target.path / "admission")][0], entry.admitted)
        self.assertEqual((len(self.requests), len(self.scopes)), (2, 1))

    def test_provisional_ready_session_cannot_replace_the_actual_failed_admit_return(self):
        path, _, ack, _ = self.prepare_handoff()
        failure = OSError("SYNTHETIC_READMISSION_FINAL_RETURN")
        with self.actual_readmission_wrapper(final_failure=failure), self.entry_call() as entries:
            error = self.failed_adoption(ack, OSError)
        self.assertIs(error, failure)
        self.assertEqual(entries, [])
        target = path.with_name(path.name + "-adoption")
        self.assertEqual(O.parse((target / "admission/session-result.json").read_bytes())["result"], "READY_FOR_CALLER_SEAL")
        self.assertFalse((target / "entry-context.json").exists())

    def test_equal_but_not_returned_admission_is_refused_at_entry(self):
        _, _, ack, _ = self.prepare_handoff()
        def before(call):
            copied = replace(call.admitted)
            self.assertEqual(copied, call.admitted)
            self.assertIsNot(copied, call.admitted)
            call.admitted = copied
        with self.entry_call(before=before):
            self.failed_adoption(ack, O.OriginError, "ADMISSION_NOT_CURRENT_RETURN")

    def test_missing_readmission_registry_cannot_be_repopulated_from_valid_files(self):
        _, _, ack, _ = self.prepare_handoff()
        def before(call): call.owner.admissions.clear()
        with self.entry_call(before=before):
            self.failed_adoption(ack, O.OriginError, "ADMISSION_NOT_CURRENT_RETURN")

    def test_copied_entry_is_not_this_owners_original_entry(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            copied = replace(call.entry)
            self.assertEqual(copied, call.entry)
            call.entry = copied
        with self.entry_call(after=after):
            self.failed_adoption(ack, O.OriginError, "ENTRY_NOT_CURRENT_RETURN")

    def test_copied_owner_cannot_adopt_the_original_entry_and_registry(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            with self.assertRaisesRegex(O.OriginError, "ENTRY_NOT_CURRENT_RETURN"):
                S.check_execution_entry(copy.copy(call.owner), call.target, call.entry, call.fence, retained=True)
        with self.adopter(ack), self.entry_call(after=after):
            S.adopt_originals([])

    def test_copied_fence_cannot_refresh_the_original_entry(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            with self.assertRaisesRegex(O.OriginError, "ENTRY_NOT_CURRENT_RETURN"):
                S.check_execution_entry(call.owner, call.target, call.entry, copy.copy(call.fence), retained=True)
        with self.adopter(ack), self.entry_call(after=after):
            S.adopt_originals([])

    def test_entry_is_not_usable_after_its_owning_call_closes(self):
        _, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack), self.entry_call() as calls:
            S.adopt_originals([])
        call = calls[0]
        with self.assertRaises(O.OriginError):
            S.check_execution_entry(call.owner, call.target, call.entry, call.fence, retained=True)

    def reject_unregistered_directory(self, name):
        _, _, ack, _ = self.prepare_handoff()
        opened = []
        def before(call):
            directory = S.query._PosixDirectory(getattr(call, name).path)
            opened.append(directory)
            setattr(call, name, directory)
        try:
            with self.entry_call(before=before):
                self.failed_adoption(ack, O.OriginError, "ENTRY_DIRECTORY_NOT_OWNED")
        finally:
            for directory in opened:
                directory.close()

    def test_equal_path_unregistered_target_cannot_escape_owner_close(self):
        self.reject_unregistered_directory("target")

    def test_equal_path_unregistered_preparation_handle_is_refused(self):
        self.reject_unregistered_directory("private")

    def test_another_owners_target_handle_is_not_this_owners_entry_directory(self):
        _, _, ack, _ = self.prepare_handoff()
        foreign = []
        def before(call):
            other = S.Owner(call.owner.local_end, call.fence, first=call.owner.first)
            foreign.append(other)
            call.target = other.open(call.target.path)
        try:
            with self.entry_call(before=before):
                self.failed_adoption(ack, O.OriginError, "ENTRY_DIRECTORY_NOT_OWNED")
        finally:
            for owner in foreign:
                owner.close()

    def test_checker_rejects_same_path_handle_not_the_factorys_owned_object(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            duplicate = S.query._PosixDirectory(call.target.path)
            try:
                with self.assertRaisesRegex(O.OriginError, "ENTRY_DIRECTORY_NOT_OWNED"):
                    S.check_execution_entry(call.owner, duplicate, call.entry, call.fence, retained=True)
            finally:
                duplicate.close()
        with self.adopter(ack), self.entry_call(after=after):
            S.adopt_originals([])

    def test_checker_refuses_a_resource_already_marked_for_retirement_before_io(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            for directory in (call.target, call.private):
                row = next(row for row in call.owner.resources if row["owner"] is directory)
                # Model the owner's prior retirement attempt; no new native
                # resource is acquired and this is not native drain evidence.
                row["attempted"] = True
                try:
                    with self.assertRaisesRegex(O.OriginError, "ENTRY_DIRECTORY_NOT_OWNED"), \
                            patch.object(call.owner, "read", side_effect=AssertionError("NO_RETIRED_DIRECTORY_IO")):
                        S.check_execution_entry(call.owner, call.target, call.entry, call.fence, retained=True)
                finally:
                    row["attempted"] = False
        with self.adopter(ack), self.entry_call(after=after):
            S.adopt_originals([])

    def change_preparation_at_retention(self, retained_name, changed_name):
        path, _, ack, _ = self.prepare_handoff()
        original, changed = S.Owner.write, []
        def write(owner, directory, name, *args, **kwargs):
            raw = original(owner, directory, name, *args, **kwargs)
            if name == retained_name:
                file = path / changed_name
                file.write_bytes(file.read_bytes() + b" ")
                changed.append(True)
            return raw
        with patch.object(S.Owner, "write", write):
            self.failed_adoption(ack, ValueError)
        self.assertEqual(changed, [True])
        target = path.with_name(path.name + "-adoption")
        self.assertTrue((target / "entry-context.json").is_file())
        self.assertTrue((target / "adoption-failure.json").is_file())
        self.assertEqual((target / "adoption-result.json").exists(), retained_name == "adoption-result.json")

    def test_original_jobs_change_during_entry_retention_cannot_escape_consuming_check(self):
        self.change_preparation_at_retention("entry-context.json", "service/jobs.json")

    def test_original_jobs_change_during_result_retention_cannot_escape_final_check(self):
        self.change_preparation_at_retention("adoption-result.json", "service/jobs.json")

    def test_original_handoff_reserialization_after_entry_is_not_the_original(self):
        self.change_preparation_at_retention("entry-context.json", "prepare-handoff.json")

    def test_original_context_reserialization_after_result_is_not_the_original(self):
        self.change_preparation_at_retention("adoption-result.json", "context.json")

    def test_replaced_preparation_directory_after_entry_is_not_the_original_identity(self):
        path, _, ack, _ = self.prepare_handoff()
        def after(call):
            directory, saved = path / "service", self.base / "synthetic-original-service"
            directory.rename(saved)
            shutil.copytree(saved, directory)
        with self.entry_call(after=after):
            self.failed_adoption(ack, O.OriginError, "ADOPTION_DIRECTORIES_CHANGED")

    def test_fictional_preparation_mapping_is_not_a_rederived_original_chain(self):
        self.reject_generated_record(lambda value: value["preparation"].update(handoffSha256="f" * 64))

    def test_ordinary_full_execution_profile_cannot_replace_bootstrap_identity(self):
        self.reject_generated_record(lambda value: value.update(profile="full"))

    def test_full_cache_cohort_cannot_replace_the_admitted_desktop_cohort(self):
        self.reject_generated_record(lambda value: value.update(cacheCohort={"profile": "full", "role": "macos-arm64"}))

    def test_different_selection_cannot_be_supplied_with_the_original_cohort(self):
        self.reject_generated_record(lambda value: value.update(selection="desktop-macos-arm64"))

    def test_different_source_cannot_be_bound_to_the_returned_admission(self):
        self.reject_generated_record(lambda value: value["source"].update(commit="f" * 40))

    def test_different_run_attempt_cannot_reuse_the_original_admission(self):
        self.reject_generated_record(lambda value: value["github"].update(runAttempt="2"))

    def test_a_caller_selected_clock_domain_is_not_a_duration_conversion(self):
        self.reject_generated_record(lambda value: value["window"]["clock"].update(domain="process-monotonic-ns"))

    def test_extra_full_abi_authority_is_not_an_entry_field(self):
        self.reject_generated_record(lambda value: value.update(primaryAbiAccounting={"productiveCutoffRawNs": 9999999999999}))

    def test_requested_duration_cannot_extend_the_closed_entry_window(self):
        self.reject_generated_record(lambda value: value["window"].update(durationSeconds=5400))

    def test_work_fence_cannot_be_replaced_by_the_cleanup_fence(self):
        self.reject_generated_record(lambda value: value["window"].update(workEndNs=value["window"]["finalEndNs"]))

    def test_original_first_observation_cannot_be_replaced_by_readmission_time(self):
        self.reject_generated_record(lambda value: value["window"].update(adopterFirstNs=value["window"]["readmissionReturnedNs"]))

    def test_preserved_metadata_highwater_cannot_be_discarded(self):
        self.reject_generated_record(lambda value: value["window"].update(metadataLastNs=value["window"]["adopterFirstNs"]))

    def test_readmission_return_highwater_cannot_be_discarded(self):
        self.reject_generated_record(lambda value: value["window"].update(readmissionReturnedNs=value["window"]["metadataLastNs"]))

    def test_entry_retention_is_exclusive_and_preserves_preexisting_bytes(self):
        path, _, ack, _ = self.prepare_handoff()
        sentinel = b"SYNTHETIC_PREEXISTING_ENTRY_NOT_A_RECEIPT"
        def before(call):
            file = call.target.path / "entry-context.json"
            file.write_bytes(sentinel)
            file.chmod(0o600)
        with self.entry_call(before=before):
            self.failed_adoption(ack, FileExistsError)
        self.assertEqual((path.with_name(path.name + "-adoption") / "entry-context.json").read_bytes(), sentinel)

    def test_entry_cannot_be_created_twice_with_the_same_owner_and_originals(self):
        _, _, ack, _ = self.prepare_handoff()
        original = S.execution_entry
        def after(call):
            with self.assertRaisesRegex(O.OriginError, "ENTRY_OWNER"):
                original(call.owner, call.target, call.private, call.handoff_raw, call.context_raw,
                    call.admitted, call.before, call.fence)
        with self.adopter(ack), self.entry_call(after=after):
            S.adopt_originals([])

    def test_reserialized_entry_bytes_are_not_the_retained_original(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            file = call.target.path / "entry-context.json"
            file.write_bytes(file.read_bytes() + b" ")
        with self.entry_call(after=after):
            self.failed_adoption(ack, O.OriginError, "ENTRY_ORIGINAL_CHANGED")

    def test_reserialized_readmission_session_cannot_validate_an_entry(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            file = call.target.path / "admission/session-result.json"
            file.write_bytes(file.read_bytes() + b" ")
        with self.entry_call(after=after):
            self.failed_adoption(ack, O.OriginError, "ORIGINAL_ADMISSION_RETURN_CHANGED")

    def test_reserialized_readmission_return_cannot_validate_an_entry(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call):
            file = call.target.path / "admission-return.json"
            file.write_bytes(file.read_bytes() + b" ")
        with self.entry_call(after=after):
            self.failed_adoption(ack, O.OriginError, "ORIGINAL_ADMISSION_RETURN_CHANGED")

    def test_clock_recovery_after_entry_does_not_hide_a_backward_first_check(self):
        _, _, ack, _ = self.prepare_handoff()
        def after(call): self.nanoseconds = call.fence.last - 2000
        with self.entry_call(after=after):
            self.failed_adoption(ack, O.clocks.ClockError)

    def late_entry_retention(self, cutoff, *, near_work=False):
        path, _, ack, _ = self.prepare_handoff()
        if near_work:
            self.nanoseconds = O.parse((path / "prelude.json").read_bytes())["workEndNs"] - 10 * O.NS
        original = S.Owner.write
        def write(owner, directory, name, *args, **kwargs):
            raw = original(owner, directory, name, *args, **kwargs)
            if name == "entry-context.json":
                self.nanoseconds = cutoff(owner)
                self.assertLess(self.nanoseconds, owner.fence.final)
            return raw
        with patch.object(S.Owner, "write", write):
            self.failed_adoption(ack, O.OriginError if near_work else S.posix.EvidenceError)
        target = path.with_name(path.name + "-adoption")
        self.assertTrue((target / "entry-context.json").is_file())
        self.assertFalse((target / "adoption-result.json").exists())

    def test_entry_cannot_renew_the_original_adopter_local_45_seconds(self):
        self.late_entry_retention(lambda owner: int(owner.local_end * O.NS) + 1)

    def test_late_entry_work_cannot_consume_remaining_120_second_finalization(self):
        self.late_entry_retention(lambda owner: owner.fence.work, near_work=True)

    def test_entry_cancellation_keeps_provisional_files_but_no_success(self):
        path, _, ack, _ = self.prepare_handoff()
        cancelled = []
        def after(call): cancelled.append(S.signal.SIGTERM)
        with self.entry_call(after=after):
            self.failed_adoption(ack, KeyboardInterrupt, cancelled=cancelled)
        target = path.with_name(path.name + "-adoption")
        self.assertTrue((target / "entry-context.json").is_file())
        self.assertTrue((target / "adoption-failure.json").is_file())
        self.assertFalse((target / "adoption-result.json").exists())

    def test_unknown_entry_close_cannot_be_rehabilitated_by_retained_files(self):
        path, _, ack, _ = self.prepare_handoff()
        failure, original, marked = OSError("SYNTHETIC_ENTRY_CLOSE_UNKNOWN"), S.Owner.close_one, []
        def close_one(owner, resource):
            original(owner, resource)
            row = next(row for row in owner.resources if row["owner"] is resource)
            if owner.entry_original is not None and row["label"] == "writer" and not marked:
                # The tiny actual file is closed; native uncertainty is modeled.
                marked.append(owner)
                owner.error("synthetic-entry-close", failure, unknown=True)
        with patch.object(S.Owner, "close_one", close_one):
            error = self.failed_adoption(ack, OSError)
        self.assertIs(error, failure)
        self.assertEqual(S.QUARANTINE, marked)
        self.assertTrue((path.with_name(path.name + "-adoption") / "entry-context.json").is_file())
        self.assertFalse((path.with_name(path.name + "-adoption") / "adoption-result.json").exists())

    def test_entry_is_not_a_producer_cache_provider_or_seed_execution_caller(self):
        import hosted_cache_bootstrap_producer as producer
        import hosted_dependency_cache as cache
        import hosted_dependency_seed_files as files
        _, _, ack, _ = self.prepare_handoff()
        guards = []
        with ExitStack() as stack:
            for module, name in ((producer, "make_request"), (producer, "observe_canonical"), (files, "seed_home"),
                                 (cache, "export_snapshot"), (cache, "save_set"), (cache, "provider_observation")):
                guards.append(stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_EXECUTION"))))
            with self.adopter(ack):
                S.adopt_originals([])
        for guard in guards:
            guard.assert_not_called()
        with self.assertRaisesRegex(files.SeedError, "SEED_BOOTSTRAP_EXECUTION_NOT_CONNECTED"):
            files.require_connected_execution(self.admitted.record)
        self.assertEqual((len(self.requests), len(self.scopes), len(self.admissions)), (2, 1, 3))


def load_tests(loader, _standard, _pattern):
    return unittest.TestSuite(EntryModels(name) for name in sorted(EntryModels.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
