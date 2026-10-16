#!/usr/bin/env python3
"""New-entry offline controls; NOT hosted/native/provider or job admission.

Tiny ordinary-UID POSIX files are real. All hosted, query/process/service and
clock boundaries are explicit models. Existing fixture helpers are reused,
but no inherited test method is selected. No build/download/key/cache action.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import copy
from dataclasses import FrozenInstanceError, replace
import importlib.util
import inspect
import os
from pathlib import Path
import shutil
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("bootstrap_new_entry_close_models",
    Path(__file__).with_name("hosted-cache-bootstrap-close-test.py"))
C = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = C
spec.loader.exec_module(C)
S, O = C.S, C.O


class ReadmissionModels(C.CloseModels):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(S, "_ENTRY_ATTEMPTS", {}))

    @contextmanager
    def ready(self, *, late=True, final_failure=None):
        with self.live() as call:
            call.closed = self.close(call)
            call.old_last = call.fence.last
            call.old_limits = S._entry_close_limits(call.owner, call.fence)
            if late:
                # Advance, never rewind: the old75 AND old120 have elapsed.
                self.nanoseconds = call.fence.final + 2 * O.NS
            with self.actual_readmission_wrapper(final_failure=final_failure) as (calls, admitted):
                call.new_calls, call.new_admitted = calls, admitted
                yield call

    def attempt(self, call):
        row = S._ENTRY_ATTEMPTS[id(call.closed)]
        self.assertIs(row[0], call.closed)
        return row[1]

    def unchanged_old(self, call):
        self.assertEqual(call.fence.last, call.old_last)
        self.assertEqual(S._entry_close_limits(call.owner, call.fence), call.old_limits)
        self.assertIs(call.owner.entry_close_original, call.closed)
        self.assertTrue(call.owner.closed)
        self.assertFalse(call.owner.unknown)

    def no_retry(self, call):
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_RETRY_CLOCK")), \
                patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_RETRY_OWNER")), \
                self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
            S.readmit_closed_entry(call.closed)

    def reject_host(self, name, value, reason):
        with self.ready() as call, patch.dict(os.environ, {name: value}), \
                self.assertRaisesRegex(O.OriginError, reason):
            try:
                S.readmit_closed_entry(call.closed)
            finally:
                attempt = self.attempt(call)
                self.assertTrue(attempt.owner.closed)
                self.assertEqual(attempt.resources, ())
                self.assertEqual(call.new_calls, [])
                self.assertEqual(attempt.failure_custody, "UNAVAILABLE")
                self.unchanged_old(call)

    def change_during_admission(self, relative):
        with self.ready() as call:
            original = S.admit
            def admit(*args, **kwargs):
                result = original(*args, **kwargs)
                file = call.path / relative
                file.write_bytes(file.read_bytes() + b" ")
                return result
            with patch.object(S, "admit", side_effect=admit), self.assertRaises(ValueError):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIsNone(attempt.result)
            self.assertIsNotNone(attempt.admitted)
            self.assertEqual(attempt.failure_custody, "PRIVATE_PROVISIONAL_ONLY")
            self.assertTrue(attempt.owner.closed)
            self.unchanged_old(call)

    def test_late_fresh_readmission_closes_only_new_resources_without_execution_authority(self):
        with self.ready() as call:
            before = {str(p): p.read_bytes() for base in (call.path, call.target.path)
                      for p in base.rglob("*") if p.is_file()}
            original, closed = S.Owner.close, []
            def close(owner):
                if type(owner.fence) is S._NewEntryWindow:
                    closed.append(owner)
                return original(owner)
            with patch.object(S.Owner, "close", close), \
                    patch.object(call.owner, "close", side_effect=AssertionError("NO_OLD_CLOSE")), \
                    patch.object(call.fence, "now", side_effect=AssertionError("NO_OLD_CLOCK")):
                result = S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertEqual(closed, [attempt.owner])
            self.assertIsNot(attempt.owner, call.owner)
            self.assertIs(attempt.admitted, call.new_admitted)
            self.assertIsNot(attempt.admitted, call.entry.admitted)
            self.assertEqual(call.new_calls, ["construct", "native-model", "identity-model", "retain", "finalize"])
            self.assertEqual((len(self.requests), len(self.scopes)), (2, 1))
            value = S.check_new_entry_transition(result)
            self.assertEqual(value["scope"], "BOOTSTRAP_NEW_ENTRY_READMISSION_CLOSED_NO_EXECUTION_V1")
            self.assertEqual(value["newOwnerRetirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
            self.assertEqual(value["productiveOwner"], "NOT_CREATED")
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
            self.assertIs(value["exportSaveAuthority"], False)
            self.assertGreater(attempt.window.first, call.fence.final)
            self.assertEqual(attempt.window.final - attempt.window.first, 120 * O.NS)
            self.assertEqual(attempt.window.work - attempt.window.first, 75 * O.NS)
            self.assertEqual(attempt.window.final - attempt.window.work, 45 * O.NS)
            self.assertLessEqual(attempt.local_end, attempt.local_start + 120)
            self.assertEqual(attempt.owner.resources, [row for row, _, _ in attempt.resources])
            self.assertTrue(all(row["attempted"] and row["closed"] for row in attempt.owner.resources))
            self.assertEqual(before, {name: Path(name).read_bytes() for name in before})
            self.unchanged_old(call)

    def test_pending_file_has_no_postclose_claim_and_exact_result_is_registered(self):
        with self.ready() as call:
            result = S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            pending = O.parse(attempt.pending_raw)
            file = attempt.target.path / "new-entry-pending.json"
            self.assertEqual(file.read_bytes(), attempt.pending_raw)
            self.assertEqual(file.stat().st_mode & 0o777, 0o600)
            self.assertEqual(pending["newOwnerRetirement"], "PENDING_CLOSE")
            self.assertNotIn("resourceCount", pending)
            self.assertNotIn("closedNs", pending)
            self.assertEqual(pending["originalAdopterFirstNs"], call.first.nanoseconds)
            self.assertEqual(pending["previousCheckedNs"], call.closed._checked_ns)
            self.assertEqual(pending["proposalSha256"], O.digest(call.closed.proposal_raw))
            self.assertFalse((attempt.target.path / "new-entry-result.json").exists())
            self.assertGreater(result._checked_ns, result._closed_ns)
            self.assertEqual(result._checked_ns, attempt.window.last)
            self.assertIs(attempt.result, result)
            self.assertEqual(repr(result), "NewEntryTransition()")
            with self.assertRaises(FrozenInstanceError):
                result.raw = b"{}"

    def test_closed_return_validation_reads_no_file_clock_or_owner_and_rejects_copies(self):
        with self.ready() as call:
            result = S.readmit_closed_entry(call.closed)
            expected = O.parse(result.raw)
            with ExitStack() as guards:
                for target, name in ((O.clocks, "observe"), (S.time, "monotonic"), (Path, "read_bytes"),
                                     (S.Owner, "__init__"), (S.Owner, "acquire"), (S.Owner, "read")):
                    guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_VALIDATOR_IO")))
                self.assertEqual(S.check_new_entry_transition(result), expected)
                self.assertEqual(S.check_new_entry_transition(result), expected)
                for copied in (copy.copy(result), replace(result), SimpleNamespace(raw=result.raw)):
                    with self.assertRaisesRegex(O.OriginError, "NOT_CURRENT_RETURN"):
                        S.check_new_entry_transition(copied)

    def test_successful_entry_cannot_be_claimed_again(self):
        with self.ready() as call:
            S.readmit_closed_entry(call.closed)
            self.no_retry(call)

    def test_foreign_closed_copies_do_not_claim_or_touch_the_original(self):
        with self.ready() as call:
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_FOREIGN_CLOCK")), \
                    patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_FOREIGN_OWNER")):
                for copied in (copy.copy(call.closed), replace(call.closed), SimpleNamespace(raw=call.closed.raw)):
                    with self.assertRaisesRegex(O.OriginError, "NOT_CURRENT_RETURN"):
                        S.readmit_closed_entry(copied)
            self.assertEqual(S._ENTRY_ATTEMPTS, {})
            S.readmit_closed_entry(call.closed)

    def test_original_adopter_first_requires_identity_not_value_equality(self):
        with self.ready() as call:
            original = call.owner.first
            call.owner.first = replace(original)
            try:
                with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_NEW_CLOCK")), \
                        self.assertRaisesRegex(O.OriginError, "ORIGINAL_FIRST"):
                    S.readmit_closed_entry(call.closed)
                self.assertEqual(S._ENTRY_ATTEMPTS, {})
            finally:
                call.owner.first = original

    def test_first_clock_failure_preserves_once_claim_and_exception_without_allocating(self):
        with self.ready() as call:
            failure = O.clocks.ClockError("SYNTHETIC_FIRST_CLOCK")
            with patch.object(O.clocks, "observe", side_effect=failure), \
                    patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_OWNER_AFTER_CLOCK_FAILURE")), \
                    self.assertRaises(O.clocks.ClockError) as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIs(caught.exception, failure)
            self.assertIs(attempt.original, failure)
            self.assertEqual(attempt.state, "FAILED")
            self.assertIsNone(attempt.owner)
            self.assertEqual(attempt.failure_custody, "UNAVAILABLE")
            self.no_retry(call)
            self.unchanged_old(call)

    def test_backward_fresh_first_is_retained_and_cannot_recover_with_a_later_clock(self):
        with self.ready() as call:
            first = O.clocks.Reading(self.clock, call.closed._checked_ns - 1)
            with patch.object(O.clocks, "observe", return_value=first), \
                    self.assertRaisesRegex(O.OriginError, "FIRST_CLOCK"):
                S.readmit_closed_entry(call.closed)
            self.assertIs(self.attempt(call).first, first)
            self.assertIsNone(self.attempt(call).owner)
            self.no_retry(call)

    def test_fresh_first_cannot_change_the_complete_clock_identity(self):
        with self.ready() as call:
            clock = O.clocks.ClockIdentity("windows-x64", O.clocks.WINDOWS_DOMAIN, 10_000_001)
            first = O.clocks.Reading(clock, self.nanoseconds)
            with patch.object(O.clocks, "observe", return_value=first), \
                    self.assertRaisesRegex(O.OriginError, "FIRST_CLOCK"):
                S.readmit_closed_entry(call.closed)
            self.assertIs(self.attempt(call).first, first)
            self.assertIsNone(self.attempt(call).owner)

    def test_old_first_object_is_not_a_fresh_observation(self):
        with self.ready() as call:
            with patch.object(O.clocks, "observe", return_value=call.first), \
                    self.assertRaisesRegex(O.OriginError, "FIRST_CLOCK"):
                S.readmit_closed_entry(call.closed)
            self.assertIs(self.attempt(call).first, call.first)
            self.assertIsNone(self.attempt(call).owner)

    def test_first_plus_120_overflow_refuses_instead_of_clamping_to_a_proposal(self):
        with self.ready() as call:
            first = O.clocks.Reading(self.clock, O.clocks.UINT64 - 30 * O.NS)
            with patch.object(O.clocks, "observe", return_value=first), self.assertRaisesRegex(O.OriginError, "INTEGER"):
                S.readmit_closed_entry(call.closed)
            self.assertIs(self.attempt(call).first, first)
            self.assertIsNone(self.attempt(call).window)

    def test_exact_45_remaining_has_no_new_work_interval(self):
        with self.ready() as call:
            phase = O.parse(call.closed.proposal_raw)["phaseFencesNs"]["productive-entry"]
            first = O.clocks.Reading(self.clock, phase - 45 * O.NS)
            with patch.object(O.clocks, "observe", return_value=first), \
                    self.assertRaisesRegex(O.OriginError, "NO_WORK_INTERVAL"):
                S.readmit_closed_entry(call.closed)
            self.assertIsNone(self.attempt(call).owner)

    def test_shortened_phase_caps_the_actual_query_pair_without_extra_45_or_wait(self):
        with self.ready() as call:
            phase = O.parse(call.closed.proposal_raw)["phaseFencesNs"]["productive-entry"]
            self.nanoseconds = phase - 60 * O.NS
            original, pairs = S.query.NativeGitQueries, []
            def supplier(*args, **kwargs):
                pairs.append(kwargs["owner_deadlines"])
                return original(*args, **kwargs)
            with patch.object(S.query, "NativeGitQueries", side_effect=supplier):
                result = S.readmit_closed_entry(call.closed)
            attempt = result._attempt
            self.assertEqual(attempt.window.final, phase)
            self.assertEqual(attempt.window.work, phase - 45 * O.NS)
            self.assertLess(attempt.window.work - attempt.window.first, 15 * O.NS)
            self.assertEqual(len(pairs), 1)
            self.assertLessEqual(pairs[0][0], attempt.window.work / O.NS)
            self.assertLessEqual(pairs[0][1], attempt.window.final / O.NS)
            self.assertLessEqual(attempt.local_end, phase / O.NS)

    def test_reentry_from_first_clock_is_rejected_with_lock_released(self):
        with self.ready() as call:
            entered = []
            def observe():
                if not entered:
                    entered.append(True)
                    acquired = S._ENTRY_CLAIM_LOCK.acquire(blocking=False)
                    self.assertTrue(acquired)
                    if acquired:
                        S._ENTRY_CLAIM_LOCK.release()
                    self.no_retry(call)
                return self.observe()
            with patch.object(O.clocks, "observe", side_effect=observe):
                S.readmit_closed_entry(call.closed)
            self.assertEqual(entered, [True])

    def test_concurrent_claims_retain_exactly_one_strong_attempt_without_suppliers(self):
        with self.ready() as call:
            barrier, results, errors = threading.Barrier(2), [], []
            def claim():
                try:
                    barrier.wait(timeout=5)
                    results.append(S._claim_closed_entry(call.closed))
                except BaseException as error:
                    errors.append(error)
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_CLAIM_CLOCK")), \
                    patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_CLAIM_OWNER")):
                workers = [threading.Thread(target=claim, daemon=True) for _ in range(2)]
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(timeout=5)
                self.assertFalse(any(worker.is_alive() for worker in workers))
            self.assertEqual((len(results), len(errors)), (1, 1))
            self.assertIsInstance(errors[0], O.OriginError)
            self.assertIn("ALREADY_CLAIMED", str(errors[0]))
            self.assertIs(self.attempt(call), results[0])

    def test_returned_first_handle_is_captured_before_local_clock_failure_and_closed_once(self):
        with self.ready() as call:
            failure, seen = OSError("SYNTHETIC_POST_RETURN_LOCAL_CLOCK"), []
            def local():
                registered = S._ENTRY_ATTEMPTS.get(id(call.closed))
                attempt = registered[1] if registered else None
                owner = S._new_entry_owner(attempt) if attempt is not None else None
                if owner is not None and owner.resources and not seen:
                    seen.append(owner.resources[0]["owner"])
                    self.assertIs(attempt.resources[0][2], seen[0])
                    raise failure
                return self.nanoseconds / O.NS
            with patch.object(S.time, "monotonic", side_effect=local), self.assertRaises(OSError) as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(seen), 1)
            self.assertEqual(len(attempt.resources), 1)
            self.assertTrue(attempt.resources[0][0]["closed"])
            self.assertFalse(attempt.owner.unknown)
            self.assertIsNone(attempt.target)

    def test_returned_first_handle_crossing_final_keeps_raw_highwater_and_known_cleanup(self):
        with self.ready() as call:
            original, returned = S.query._PosixDirectory, []
            def directory(path):
                value = original(path)
                returned.append(value)
                self.nanoseconds = self.attempt(call).window.final
                return value
            with patch.object(S.query, "_PosixDirectory", side_effect=directory), \
                    self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertEqual(len(returned), 1)
            self.assertIs(attempt.resources[0][2], returned[0])
            self.assertGreaterEqual(attempt.window.last, attempt.window.final)
            self.assertTrue(attempt.resources[0][0]["closed"])
            self.assertFalse(attempt.owner.unknown)
            self.assertEqual(attempt.failure_custody, "UNAVAILABLE")

    def test_ambiguous_first_allocation_is_unknown_and_never_allocates_failure_custody(self):
        with self.ready() as call:
            failure = OSError("SYNTHETIC_UNRETURNED_HANDLE")
            with patch.object(S.query, "_PosixDirectory", side_effect=failure), self.assertRaises(OSError) as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIs(caught.exception, failure)
            self.assertTrue(attempt.owner.unknown)
            self.assertTrue(any(owner is attempt.owner for owner in S.QUARANTINE))
            self.assertEqual(attempt.resources, ())
            self.assertIsNone(attempt.target)
            self.assertEqual(attempt.failure_custody, "UNAVAILABLE")

    def test_work_expiry_precedes_host_metadata_and_reserves_only_original_cleanup(self):
        with self.ready() as call:
            original = S._new_entry_read_originals
            def read(attempt):
                self.nanoseconds = attempt.window.work
                with patch.object(S, "host_inputs", side_effect=AssertionError("NO_EXPIRED_HOST_IO")):
                    return original(attempt)
            with patch.object(S, "_new_entry_read_originals", side_effect=read), \
                    self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertGreaterEqual(attempt.window.last, attempt.window.work)
            self.assertLess(attempt.window.last, attempt.window.final)
            self.assertEqual(attempt.failure_custody, "PRIVATE_PROVISIONAL_ONLY")
            self.assertTrue(attempt.owner.closed)
            self.assertFalse(attempt.owner.unknown)
            self.no_retry(call)

    def test_failed_prepare_outcome_cannot_authorize_an_entry(self):
        self.reject_host(S.PREPARE_OUTCOME_ENV, "failure", "PREPARE_ORIGINAL_OUTCOME")

    def test_changed_prepare_hash_cannot_authorize_an_entry(self):
        self.reject_host(S.PREPARE_HASH_ENV, "0" * 64, "PREPARE_ORIGINAL_HASH_CHANGED")

    def test_acquisition_token_is_not_inherited_by_new_readmission(self):
        self.reject_host(O.wire.TOKEN_ENV, "SYNTHETIC_FORBIDDEN", "TOKEN_FORBIDDEN")

    def test_actual_host_drift_is_not_accepted_from_matching_old_records(self):
        self.reject_host("GITHUB_JOB", "desktop", "ACTUAL_HOSTED_CALLER")

    def test_ambient_execution_override_is_refused_before_file_ownership(self):
        self.reject_host("JAVA_TOOL_OPTIONS", "SYNTHETIC_FORBIDDEN", "AMBIENT_EXECUTION_OVERRIDE")

    def test_new_reader_uses_original_history_first_but_only_current_registered_owner(self):
        with self.ready() as call:
            original, views = S._new_entry_read_originals, []
            def read(attempt):
                with patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_READER_FACTORY_OWNER")):
                    reader = S._NewEntryOriginalReader(attempt)
                    self.assertIs(reader.owner, attempt.owner)
                    self.assertIs(reader.current, attempt.window)
                    self.assertIs(reader.first, call.first)
                    self.assertIsNot(reader.first, attempt.owner.first)
                    self.assertEqual(reader.past.raw, call.fence.raw)
                    self.assertIs(reader.checked(), reader)
                    views.append(reader)
                    with self.assertRaisesRegex(O.OriginError, "NOT_CLAIMED"):
                        S._NewEntryOriginalReader(copy.copy(attempt))
                return original(attempt)
            with patch.object(S, "_new_entry_read_originals", side_effect=read):
                result = S.readmit_closed_entry(call.closed)
            self.assertEqual(len(views), 3)
            with self.assertRaisesRegex(O.OriginError, "NOT_LIVE"):
                views[0].checked()
            with self.assertRaisesRegex(O.OriginError, "NOT_LIVE"):
                S._NewEntryOriginalReader(result._attempt)

    def test_fresh_actual_return_after_old75_is_not_relabeled_as_historical_admission(self):
        with self.ready() as call:
            result = S.readmit_closed_entry(call.closed)
            attempt = result._attempt
            self.assertGreater(attempt.returned["returnedNs"], call.fence.work)
            self.assertIn("returnSha256", S._new_entry_return_content(attempt))
            with self.assertRaises(O.OriginError):
                S.admission_content(attempt.admitted, attempt.admission_originals[1],
                                    attempt.admission_originals[2], call.fence)
            self.assertLess(O.parse(call.entry.return_original)["returnedNs"], call.fence.work)

    def test_copied_current_admission_cannot_replace_actual_supplier_return(self):
        with self.ready() as call:
            original = S.admit
            def admit(owner, fence, directory, **kwargs):
                result = original(owner, fence, directory, **kwargs)
                row = owner.admissions[str(directory)]
                owner.admissions[str(directory)] = (replace(row[0]), *row[1:])
                return result
            with patch.object(S, "admit", side_effect=admit), \
                    self.assertRaisesRegex(O.OriginError, "NOT_CURRENT_ADMISSION"):
                S.readmit_closed_entry(call.closed)
            self.assertIsNone(self.attempt(call).result)

    def test_equal_replaced_current_registry_tuple_is_not_the_retained_original(self):
        with self.ready() as call:
            original = S._new_entry_read_admission
            def read(attempt):
                key = str(attempt.target.path / "admission")
                attempt.owner.admissions[key] = tuple(list(attempt.admission_originals))
                return original(attempt)
            with patch.object(S, "_new_entry_read_admission", side_effect=read), \
                    self.assertRaisesRegex(O.OriginError, "NOT_CURRENT_ADMISSION"):
                S.readmit_closed_entry(call.closed)
            self.assertIsNone(self.attempt(call).result)

    def test_failed_native_supplier_return_cannot_use_its_provisional_session_file(self):
        failure = OSError("SYNTHETIC_QUERY_FINAL_RETURN")
        with self.ready(final_failure=failure) as call:
            with self.assertRaises(OSError) as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIs(caught.exception, failure)
            self.assertIsNone(attempt.admitted)
            self.assertEqual(attempt.owner.admissions, {})
            self.assertTrue((attempt.target.path / "admission/session-result.json").is_file())
            self.assertIsNone(attempt.result)

    def test_current_return_at_work_boundary_cannot_be_coherently_declared_success(self):
        with self.ready() as call:
            original = S.admit
            def admit(owner, fence, directory, **kwargs):
                admitted, returned = original(owner, fence, directory, **kwargs)
                returned = {**returned, "returnedNs": fence.work}
                row = owner.admissions[str(directory)]
                owner.admissions[str(directory)] = (admitted, row[1], O.encoded(returned))
                return admitted, returned
            with patch.object(S, "admit", side_effect=admit), \
                    self.assertRaisesRegex(O.OriginError, "ADMISSION_RETURN"):
                S.readmit_closed_entry(call.closed)
            self.assertIsNone(self.attempt(call).pending_raw)

    def test_original_jobs_byte_change_is_refused_before_fresh_native_admission(self):
        with self.ready() as call:
            file = call.path / "service/jobs.json"
            file.write_bytes(file.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                S.readmit_closed_entry(call.closed)
            self.assertEqual(call.new_calls, [])
            self.assertIsNone(self.attempt(call).result)

    def test_context_change_during_actual_readmission_is_found_by_reread(self):
        self.change_during_admission("context.json")

    def test_handoff_change_during_actual_readmission_is_found_by_reread(self):
        self.change_during_admission("prepare-handoff.json")

    def test_service_change_during_actual_readmission_is_found_by_reread(self):
        self.change_during_admission("service/attempt.json")

    def test_replaced_original_directory_has_no_native_identity_authority(self):
        with self.ready() as call:
            saved = call.path.with_name(call.path.name + "-saved-fixture")
            call.path.rename(saved)
            shutil.copytree(saved, call.path)
            with self.assertRaisesRegex(O.OriginError, "DIRECTORY_CHANGED"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIsNone(attempt.target)
            self.assertEqual(call.new_calls, [])

    def test_existing_new_episode_is_not_overwritten_or_retried(self):
        with self.ready() as call:
            target = call.path.with_name(call.path.name + "-entry")
            target.mkdir(mode=0o700)
            retained = target / "retained"
            retained.write_bytes(b"SYNTHETIC_DO_NOT_REPLACE")
            with self.assertRaises(FileExistsError):
                S.readmit_closed_entry(call.closed)
            self.assertEqual(retained.read_bytes(), b"SYNTHETIC_DO_NOT_REPLACE")
            self.assertTrue(self.attempt(call).owner.unknown)
            self.no_retry(call)

    def test_old_adoption_change_after_pending_retention_is_not_rehabilitated(self):
        with self.ready() as call:
            original = S.Owner.write
            def write(owner, directory, name, *args, **kwargs):
                raw = original(owner, directory, name, *args, **kwargs)
                if name == "new-entry-pending.json":
                    file = call.target.path / "entry-context.json"
                    file.write_bytes(file.read_bytes() + b" ")
                return raw
            with patch.object(S.Owner, "write", write), self.assertRaisesRegex(O.OriginError, "ADOPTION_CHANGED"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIsNotNone(attempt.pending_raw)
            self.assertIsNone(attempt.result)

    def test_first_retention_error_survives_secondary_failure_and_closes_known_resources(self):
        with self.ready() as call:
            original = S.Owner.write
            first, second = OSError("SYNTHETIC_PENDING_FAILURE"), OSError("SYNTHETIC_FAILURE_CUSTODY")
            def write(owner, directory, name, *args, **kwargs):
                if name == "new-entry-pending.json":
                    raise first
                if name == "new-entry-failure.json":
                    raise second
                return original(owner, directory, name, *args, **kwargs)
            with patch.object(S.Owner, "write", write), self.assertRaises(OSError) as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIs(caught.exception, first)
            self.assertIs(attempt.owner.original, first)
            self.assertEqual(attempt.failure_custody, "INCOMPLETE")
            self.assertTrue(attempt.owner.closed)
            self.assertFalse(attempt.owner.unknown)
            self.assertEqual([row["stage"] for row in attempt.errors],
                             ["new-entry-readmission", "new-entry-failure-retention"])

    def test_original_cancellation_signal_keeps_failure_and_bounded_private_custody(self):
        with self.ready() as call:
            original, count = S._new_entry_read_originals, []
            def read(attempt):
                count.append(True)
                if len(count) == 2:
                    self.cancelled.append(15)
                return original(attempt)
            with patch.object(S, "_new_entry_read_originals", side_effect=read), \
                    self.assertRaisesRegex(KeyboardInterrupt, "ORIGIN_CANCELLED") as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIs(attempt.original, caught.exception)
            self.assertEqual(attempt.failure_custody, "PRIVATE_PROVISIONAL_ONLY")
            self.assertFalse(attempt.owner.unknown)
            self.unchanged_old(call)

    def test_postclose_cancellation_has_no_failure_reacquisition_or_new_owner(self):
        with self.ready() as call:
            original, closed = S.Owner.close, []
            def close(owner):
                original(owner)
                if type(owner.fence) is S._NewEntryWindow:
                    closed.append(owner)
                    self.cancelled.append(15)
            with patch.object(S.Owner, "close", close), self.assertRaises(KeyboardInterrupt):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertEqual(closed, [attempt.owner])
            self.assertIsNotNone(attempt.pending_raw)
            self.assertIsNone(attempt.failure_raw)
            self.assertEqual(attempt.failure_custody, "UNAVAILABLE")
            self.assertFalse(attempt.owner.unknown)
            self.assertFalse((attempt.target.path / "new-entry-failure.json").exists())

    def test_postclose_raw_expiry_is_retained_without_another_close_or_retention_owner(self):
        with self.ready() as call:
            local, original, closed = self.nanoseconds / O.NS, S.Owner.close, []
            def close(owner):
                original(owner)
                if type(owner.fence) is S._NewEntryWindow:
                    closed.append(owner)
                    self.nanoseconds = owner.fence.final
            with patch.object(S.time, "monotonic", return_value=local), patch.object(S.Owner, "close", close), \
                    self.assertRaisesRegex(O.OriginError, "FENCE_EXPIRED"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertEqual(closed, [attempt.owner])
            self.assertGreaterEqual(attempt.window.last, attempt.window.final)
            self.assertIsNone(attempt.failure_raw)
            self.assertIsNone(attempt.result)

    def test_postclose_row_uncertainty_quarantines_original_snapshot_without_second_close(self):
        with self.ready() as call:
            original, closed = S.Owner.close, []
            def close(owner):
                original(owner)
                if type(owner.fence) is S._NewEntryWindow:
                    closed.append(owner)
                    owner.resources[0]["closed"] = False
            with patch.object(S.Owner, "close", close), self.assertRaisesRegex(O.OriginError, "NEW_ENTRY_ROSTER"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertEqual(closed, [attempt.owner])
            self.assertTrue(attempt.owner.unknown)
            self.assertTrue(any(owner is attempt.owner for owner in S.QUARANTINE))
            self.assertGreater(len(attempt.snapshot[1]), 3)
            self.assertIsNone(attempt.result)

    def test_preclose_list_replacement_cannot_erase_previously_observed_handles(self):
        with self.ready() as call:
            original = S._new_entry_read_originals
            def read(attempt):
                owner = attempt.owner
                saved = owner.resources
                self.addCleanup(setattr, owner, "resources", saved)  # Tiny-fixture teardown only, never production recovery.
                owner.resources = []
                return original(attempt)
            with patch.object(S, "_new_entry_read_originals", side_effect=read), \
                    self.assertRaisesRegex(O.OriginError, "NEW_ENTRY_ROSTER"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertTrue(attempt.owner.unknown)
            self.assertEqual(len(attempt.resources), 3)
            self.assertTrue(any(resource is attempt.private for _, _, resource in attempt.resources))
            self.assertTrue(any(resource is attempt.target for _, _, resource in attempt.resources))
            self.assertTrue(any(owner is attempt.owner for owner in S.QUARANTINE))

    def test_changed_attempt_owner_never_redirects_cleanup_to_an_equal_copy(self):
        with self.ready() as call:
            original, owners = S._new_entry_read_originals, []
            def read(attempt):
                owners.append(attempt.owner)
                attempt.owner = copy.copy(attempt.owner)
                return original(attempt)
            with patch.object(S, "_new_entry_read_originals", side_effect=read), \
                    self.assertRaisesRegex(O.OriginError, "OWNER_CHANGED"):
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertEqual(len(owners), 1)
            self.assertTrue(owners[0].closed)
            self.assertFalse(attempt.owner.closed)
            self.assertIs(S._new_entry_owner(attempt), owners[0])
            self.assertTrue(all(row["closed"] for row in owners[0].resources))

    def rebound_after_first_return(self, replace_transition):
        with self.ready() as call:
            original, returned, closed = S.query._PosixDirectory, [], []
            close = S.Owner.close
            def directory(path):
                resource = original(path)
                returned.append(resource)
                self.attempt(call).transition = replace_transition(call.closed)
                return resource
            def finish(owner):
                if type(owner.fence) is S._NewEntryWindow:
                    closed.append(owner)
                return close(owner)
            with patch.object(S.query, "_PosixDirectory", side_effect=directory), \
                    patch.object(S.Owner, "close", finish), \
                    self.assertRaisesRegex(O.OriginError, "NOT_CLAIMED") as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertEqual(attempt.state, "FAILED")
            self.assertIs(caught.exception, attempt.original)
            self.assertIs(caught.exception, attempt.owner.original)
            self.assertEqual(closed, [attempt.owner])
            self.assertTrue(attempt.owner.closed)
            self.assertFalse(attempt.owner.unknown)
            self.assertEqual(len(returned), 1)
            self.assertIs(attempt.resources[0][2], returned[0])
            self.assertTrue(attempt.resources[0][0]["attempted"])
            self.assertTrue(attempt.resources[0][0]["closed"])
            self.assertIsNone(attempt.result)
            self.assertEqual(attempt.failure_custody, "UNAVAILABLE")
            self.assertFalse(any(owner is attempt.owner for owner in S.QUARANTINE))
            self.no_retry(call)
            self.unchanged_old(call)

    def test_copied_transition_after_handle_return_cannot_skip_close_or_replace_first_error(self):
        self.rebound_after_first_return(copy.copy)

    def test_missing_transition_after_handle_return_cannot_discard_actual_owner(self):
        self.rebound_after_first_return(lambda _transition: None)

    def test_rebound_transition_before_acquisition_preserves_original_error_and_closes_empty_owner(self):
        with self.ready() as call:
            first = OSError("SYNTHETIC_REBOUND_BEFORE_ACQUISITION")
            def host(attempt):
                attempt.transition = None
                raise first
            with patch.object(S, "_new_entry_host", side_effect=host), self.assertRaises(OSError) as caught:
                S.readmit_closed_entry(call.closed)
            attempt = self.attempt(call)
            self.assertIs(caught.exception, first)
            self.assertIs(attempt.original, first)
            self.assertIs(attempt.owner.original, first)
            self.assertEqual(attempt.state, "FAILED")
            self.assertTrue(attempt.owner.closed)
            self.assertFalse(attempt.owner.unknown)
            self.assertEqual(attempt.resources, ())
            self.assertIsNone(attempt.result)
            self.no_retry(call)

    def test_new_entry_never_invokes_producer_export_save_or_http_acquisition(self):
        with self.ready() as call, ExitStack() as guards:
            for target, name in ((C.cache, "export_snapshot"), (C.cache, "save_set"),
                                 (S, "phase"), (O, "acquire"), (S.processes, "make_scope")):
                guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_PRODUCTIVE_ACTION")))
            S.readmit_closed_entry(call.closed)
            self.assertEqual((len(self.requests), len(self.scopes)), (2, 1))

    def test_new_entry_surface_has_no_caller_owner_clock_budget_path_or_callback(self):
        self.assertEqual(list(inspect.signature(S.readmit_closed_entry).parameters), ["transition"])
        self.assertEqual(list(inspect.signature(S._NewEntryOriginalReader).parameters), ["attempt"])
        source = inspect.getsource(S.main)
        self.assertNotIn("readmit_closed_entry", source)
        self.assertFalse((ROOT / ".github/workflows/dependency-cache-bootstrap.yml").exists())


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite(ReadmissionModels(name) for name in sorted(ReadmissionModels.__dict__)
                              if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
