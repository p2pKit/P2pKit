#!/usr/bin/env python3
"""Offline two-acquisition controls, not hosted/native/provider qualification.

The inherited controls remain separately identifiable. All actual files are
tiny UID65534 POSIX fixtures; process/HTTP/clock boundaries are explicit models.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("initial_readmission_native_fixtures",
    Path(__file__).with_name("hosted-initial-recipient-native-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)
N, S, O, I = F.N, F.S, F.O, F.I


class ReadmissionModels(F.NativeModels):
    def worker(self):
        self.choose("worker", "desktop-linux-x64")
        return N._prepare_and_readmit_worker(self.cancelled)

    def after_claim(self, change):
        claim = N._claim_worker
        def changed(original):
            self.claim = claim(original)
            change(self.claim)
            return self.claim
        self.stack.enter_context(patch.object(N, "_claim_worker", side_effect=changed))

    def refuse_worker(self, code):
        with self.assertRaisesRegex((I.AdmissionError, O.OriginError, O.wire.BudgetError, O.clocks.ClockError), code):
            self.worker()
        self.assertFalse(N._READMISSION_RETURNS)
        self.assertNotIn(O.wire.TOKEN_ENV, F.os.environ)

    def final_boundary(self, boundary, change, code="CHANGED"):
        closed = []
        close = S.Owner.close
        def after_close(owner):
            close(owner)
            if type(owner.fence) is N._ReadmissionWindow and hasattr(owner, "initial_sources"):
                closed.append(owner)
        self.stack.enter_context(patch.object(S.Owner, "close", after_close))
        calls = []
        def changed():
            if closed and not calls:
                calls.append(boundary)
                change(closed[0])
        if boundary == "raw":
            def observe():
                reading = self.fixture.observe()
                changed()
                return reading
            replacement = patch.object(O.clocks, "observe", side_effect=observe)
        elif boundary == "local":
            deadline = S.posix._deadline
            def local(end):
                deadline(end)
                changed()
            replacement = patch.object(S.posix, "_deadline", side_effect=local)
        else:
            self.assertEqual(boundary, "cancel")
            cancellation = S.cancellation
            def cancel(value):
                cancellation(value)
                changed()
            replacement = patch.object(S, "cancellation", side_effect=cancel)
        with replacement:
            self.refuse_worker(code)
        self.assertEqual(calls, [boundary])

    def test_two_acquisitions_keep_first_basis_and_close_distinct_nonproductive_owners(self):
        self.choose("worker", "desktop-linux-x64")
        result = N._prepare_and_readmit_worker(self.cancelled)
        self.assertIs(type(result), N._ReadmissionReturn)
        self.assertEqual(N.check_readmission_return(result), result)
        original = result.claim.original
        value = json.loads(result.raw)
        self.assertEqual(value["scope"], N.READMISSION_SCOPE)
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["workerAdmission"], "NOT_PERFORMED")
        self.assertEqual(value["qualificationAcceptance"], "NOT_ESTABLISHED")
        self.assertFalse(value["exportSaveAuthority"])
        self.assertEqual(value["firstUseAt"], F.F.F.FIRST1)
        self.assertEqual(result.service_time_raw, original.service_time_raw)
        self.assertEqual(result.proposal_raw, original.proposal_raw)
        self.assertEqual(len(self.fixture.requests), 16)
        self.assertEqual(len(self.scopes), 2)
        self.assertTrue(all(scope.closed and scope.close_calls == 1 for scope in self.scopes))
        self.assertEqual(len(self.queries), 6)
        self.assertTrue(all(query.closed and query.finalizations == 1 for query in self.queries))
        self.assertIsNot(result.owner, original._owner)
        self.assertTrue(result.owner.closed and original._owner.closed)
        self.assertEqual(result.path, self.path.with_name(self.path.name + "-entry"))
        self.assertTrue((result.path / "entry-window.json").is_file())
        self.assertFalse((result.path / "prelude.json").exists())
        self.assertNotIn(O.wire.TOKEN_ENV, F.os.environ)
        self.assertFalse(S.QUARANTINE)

    def test_child_reacquires_with_original_expected_match_and_first_use(self):
        acquire = N.acquisition.acquire_bootstrap
        calls = []
        def checked(root, **kwargs):
            calls.append(kwargs["expected"])
            self.assertEqual(kwargs["first_use_at"], F.F.F.FIRST1)
            self.assertNotIn(O.wire.TOKEN_ENV, F.os.environ)
            return acquire(root, **kwargs)
        with patch.object(N.acquisition, "acquire_bootstrap", side_effect=checked):
            result = self.worker()
        self.assertEqual(len(calls), 2)
        self.assertIsNone(calls[0])
        self.assertIs(type(calls[1]), N.acquisition.stages.BootstrapMatch)
        self.assertEqual(calls[1].record, result.claim.binding.match_raw)

    def test_new_dates_request_starts_and_job_step_progress_do_not_rebase_first_proposal(self):
        def changed(_claim):
            self.fixture.service_date += 1
            self.fixture.bodies["jobs"]["jobs"][0]["steps"] = [{"name": "SYNTHETIC progress", "status": "in_progress"}]
        self.after_claim(changed)
        result = self.worker()
        original = result.claim.binding
        captured = N._READMISSION_RETURNS[id(result)].evidence[5]
        self.assertNotEqual(dict(captured[1])["jobs"], dict(original.worker_originals[1])["jobs"])
        self.assertEqual(N._service_job(captured, result.window.clock), result.claim.service_job)
        self.assertEqual(result.proposal_raw, original.proposal_raw)
        self.assertEqual(result.service_time_raw, original.service_time_raw)

    def test_claim_never_reopens_or_observes_old_owner_fence_or_new_prelude(self):
        def changed(claim):
            def forbidden(*_args, **_kwargs):
                self.fail("retired original was observed/reopened or O.Fence was restarted")
            self.stack.enter_context(patch.object(claim.binding.fence, "now", side_effect=forbidden))
            self.stack.enter_context(patch.object(claim.binding.owner, "open", side_effect=forbidden))
            self.stack.enter_context(patch.object(O.Fence, "__init__", side_effect=forbidden))
        self.after_claim(changed)
        result = self.worker()
        self.assertIs(N.check_readmission_return(result), result)
        with self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
            N.original_worker_identity(result.claim.original)
        self.assertEqual(result.claim.binding.last_ns, result.claim.binding.fence.last)

    def test_gate_and_copied_originals_refuse_without_consuming_real_worker(self):
        gate = N._prepare_originals(self.cancelled)
        with self.assertRaisesRegex(I.AdmissionError, "WORKER_IDENTITY_ONLY"):
            N._claim_worker(gate)
        self.assertNotIn(id(gate), N._WORKER_CLAIMS)
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        copied = F.dataclasses.replace(original)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL"):
            N._claim_worker(copied)
        self.assertNotIn(id(original), N._WORKER_CLAIMS)
        self.assertIs(N.original_worker_identity(original), original.identity)

    def test_internal_parent_refuses_gate_before_any_query_or_native_allocation(self):
        with self.assertRaisesRegex(I.AdmissionError, "ENTRY_WORKER_ONLY"):
            N._prepare_and_readmit_worker(self.cancelled)
        self.assertEqual(self.queries, [])
        self.assertEqual(self.scopes, [])
        self.assertNotIn(O.wire.TOKEN_ENV, F.os.environ)

    def test_claim_is_permanent_after_cancelled_validation(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        self.cancelled.append("SYNTHETIC cancellation")
        with self.assertRaises(KeyboardInterrupt):
            N._claim_worker(original)
        self.cancelled.clear()  # A changed model cancellation cannot renew the spent claim.
        with self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
            N._claim_worker(original)
        self.assertFalse(N._WORKER_USES)

    def test_reentrant_claim_cannot_overlap_actual_live_validation(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        check = N._checked_worker_identity
        def checked(value):
            with self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
                N._claim_worker(value)
            return check(value)
        with patch.object(N, "_checked_worker_identity", side_effect=checked):
            claim = N._claim_worker(original)
        self.assertIs(N._WORKER_CLAIMS[id(original)], claim)
        self.assertFalse(N._WORKER_USES)

    def test_concurrent_read_holds_short_reservation_not_registry_lock(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        entered, release = threading.Event(), threading.Event()
        check = N._checked_worker_identity
        values, errors = [], []
        def checked(value):
            entered.set()
            self.assertTrue(release.wait(2), "test coordination timed out")
            return check(value)
        def reader():
            try:
                values.append(N.original_worker_identity(original))
            except BaseException as error:
                errors.append(error)
        with patch.object(N, "_checked_worker_identity", side_effect=checked):
            thread = threading.Thread(target=reader)
            thread.start()
            try:
                self.assertTrue(entered.wait(2), "test reader did not enter")
                with self.assertRaisesRegex(I.AdmissionError, "USE_IN_PROGRESS"):
                    N._claim_worker(original)
                self.assertNotIn(id(original), N._WORKER_CLAIMS)
            finally:
                release.set()
                thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(values, [original.identity])
        self.assertIs(N._claim_worker(original).original, original)

    def test_copied_claim_cannot_start_a_second_enclosure(self):
        result = self.worker()
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_WORKER_CLAIM"):
            N._readmit_worker(F.dataclasses.replace(result.claim), F.TOKEN)
        self.assertEqual(len(self.scopes), 2)

    def test_failed_preallocation_readmission_cannot_restart_original_claim(self):
        self.choose("worker", "desktop-linux-x64")
        original = N._prepare_originals(self.cancelled)
        claim = N._claim_worker(original)
        primary = O.clocks.ClockError("SYNTHETIC_ENTRY_FIRST_CLOCK_FAILURE")
        with patch.object(O.clocks, "observe", side_effect=primary), self.assertRaises(O.clocks.ClockError) as caught:
            N._readmit_worker(claim, F.TOKEN)
        self.assertIs(caught.exception, primary)
        with self.assertRaisesRegex(I.AdmissionError, "ALREADY_ATTEMPTED"):
            N._readmit_worker(claim, F.TOKEN)
        self.assertEqual(len(self.fixture.requests), 8)
        self.assertFalse(N._READMISSION_RETURNS)

    def test_window_arithmetic_clamps_without_wait_or_renewal_and_rejects_equality_overflow(self):
        self.assertEqual(N._entry_limits(1000 * O.NS, 5000 * O.NS, 6000 * O.NS), (1075 * O.NS, 1120 * O.NS))
        self.assertEqual(N._entry_limits(1000 * O.NS, 1080 * O.NS, 6000 * O.NS), (1035 * O.NS, 1080 * O.NS))
        self.assertEqual(N._entry_limits(1000 * O.NS, 6000 * O.NS, 1080 * O.NS), (1035 * O.NS, 1080 * O.NS))
        for first, end in ((1000 * O.NS, 1045 * O.NS), (O.clocks.UINT64, O.clocks.UINT64)):
            with self.assertRaises((I.AdmissionError, O.OriginError)):
                N._entry_limits(first, end, end)

    def test_exclusive_fixed_entry_path_preserves_existing_target_and_consumes_claim(self):
        def occupied(_claim):
            self.occupied = self.path.with_name(self.path.name + "-entry")
            self.occupied.mkdir(mode=0o700)
            (self.occupied / "original").write_bytes(b"SYNTHETIC existing bytes")
        self.after_claim(occupied)
        with self.assertRaises(FileExistsError):
            self.worker()
        self.assertEqual((self.occupied / "original").read_bytes(), b"SYNTHETIC existing bytes")
        self.assertEqual(len(self.fixture.requests), 8)
        with self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
            N._claim_worker(self.claim.original)
        self.assertFalse(N._READMISSION_RETURNS)

    def test_fresh_authority_edit_is_rejected(self):
        self.after_claim(lambda _: self.fixture.bodies["comment"].update(updated_at=F.F.F.utc(F.F.F.FIRST1)))
        self.refuse_worker("SERVICE_CHILD_FAILED")
        self.assertIn("COMMENT_EDITED", str(self.child_errors[-1]))

    def test_fresh_approval_removal_is_rejected(self):
        self.after_claim(lambda _: self.fixture.bodies.update(approvals=[]))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_fresh_environment_recreation_is_rejected(self):
        self.after_claim(lambda _: self.fixture.bodies["environment"].update(id=999))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_fresh_branch_policy_recreation_is_rejected(self):
        self.after_claim(lambda _: self.fixture.bodies["branches"]["branch_policies"][0].update(id=999))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_fresh_main_ref_change_is_rejected(self):
        self.after_claim(lambda _: self.fixture.bodies["main"]["object"].update(sha="b" * 40))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_fresh_source_change_is_rejected_before_second_http_child(self):
        self.after_claim(lambda _: setattr(self.fixture.git, "clean_value", False))
        self.refuse_worker("SOURCE")
        self.assertEqual(len(self.fixture.requests), 8)
        self.assertEqual(len(self.scopes), 1)

    def test_fresh_job_id_change_cannot_replace_selected_original(self):
        def changed(_claim):
            job = self.fixture.bodies["jobs"]["jobs"][0]
            job.update(id=999, url=job["url"].rsplit("/", 1)[0] + "/999")
        self.after_claim(changed)
        self.refuse_worker("ENTRY_JOB_OR_MATCH_CHANGED")
        self.assertEqual(self.child_errors, [])
        self.assertEqual(len(self.fixture.requests), 16)

    def test_fresh_job_start_change_cannot_replace_selected_original(self):
        self.after_claim(lambda _: self.fixture.bodies["jobs"]["jobs"][0].update(started_at=F.F.F.utc(F.F.F.START + 1)))
        self.refuse_worker("ENTRY_JOB_OR_MATCH_CHANGED")
        self.assertEqual(self.child_errors, [])

    def test_fresh_runner_numeric_id_change_cannot_replace_selected_original(self):
        self.after_claim(lambda _: self.fixture.bodies["jobs"]["jobs"][0].update(runner_id=999))
        self.refuse_worker("ENTRY_JOB_OR_MATCH_CHANGED")
        self.assertEqual(self.child_errors, [])

    def test_changed_native_clock_domain_refuses_before_new_owner(self):
        def changed(_claim):
            self.fixture.clock = O.clocks.ClockIdentity("windows-x64", O.clocks.WINDOWS_DOMAIN, O.NS)
        self.after_claim(changed)
        self.refuse_worker("IDENTITY_CHANGED")
        self.assertEqual(len(self.queries), 3)

    def test_new_source_after_query_failure_keeps_primary_and_actual_close(self):
        primary = KeyboardInterrupt("SYNTHETIC_QUERY_CANCELLED")
        def fail(path):
            if path.parent.name.endswith("-entry") and path.name == "source-after":
                raise primary
        self.before_query = fail
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.worker()
        self.assertIs(caught.exception, primary)
        self.assertTrue(all(scope.closed and scope.close_calls == 1 for scope in self.scopes))
        self.assertFalse(N._READMISSION_RETURNS)

    def test_new_directory_return_is_retained_before_postallocation_local_failure(self):
        primary = O.wire.BudgetError("SYNTHETIC_POSTALLOCATION_LOCAL_FAILURE")
        new = N.Q._new_private_directory
        returned, pending = [], []
        def directory(path):
            value = new(path)
            if path.name.endswith("-entry"):
                returned.append(value)
                pending.append(True)
            return value
        def local():
            if pending:
                pending.clear()
                raise primary
            return self.fixture.ns / O.NS
        with patch.object(N.Q, "_new_private_directory", side_effect=directory), \
                patch.object(N.time, "monotonic", side_effect=local), self.assertRaises(O.wire.BudgetError) as caught:
            self.worker()
        self.assertIs(caught.exception, primary)
        self.assertEqual(len(returned), 1)
        states = [x for x in N._ENTRY_WINDOWS.values() if x.owner is not None]
        self.assertEqual(len(states), 1)
        self.assertTrue(any(value is returned[0] and row["closed"] for row, _label, value in states[0].resources))
        self.assertFalse(S.QUARANTINE)
        self.assertFalse(N._READMISSION_RETURNS)

    def test_second_native_unknown_cannot_adopt_capture_or_register_return(self):
        self.after_claim(lambda _: setattr(self, "scope_close_error", RuntimeError("SYNTHETIC_UNKNOWN_CLOSE")))
        with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_UNKNOWN_CLOSE"):
            self.worker()
        self.assertFalse(N._READMISSION_RETURNS)
        self.assertEqual(len(self.scopes), 2)
        self.assertEqual(self.scopes[-1].close_calls, 1)
        self.assertTrue(S.QUARANTINE)

    def test_new_phase_ack_uses_distinct_scope_and_final_guarded_highwater(self):
        result = self.worker()
        child = json.loads((result.path / "service/child-result.json").read_bytes())
        ack = json.loads((result.path / "service/stdout.log").read_bytes())
        self.assertEqual(ack["scope"], S.INITIAL_ENTRY_ACK_SCOPE)
        self.assertGreater(ack["closedNs"], child["completedNs"])
        self.assertEqual(self.scopes[0].launches[0]["requestedArgv"][5], "_service")
        self.assertEqual(self.scopes[1].launches[0]["requestedArgv"][5], "_service-entry")

    def test_old_initial_ack_cannot_substitute_for_readmission_ack(self):
        def changed(_claim):
            def rewrite(raw):
                value = json.loads(raw)
                value["scope"] = S.INITIAL_ACK_SCOPE
                return O.encoded(value)
            self.ack_transform = rewrite
        self.after_claim(changed)
        self.refuse_worker("CHILD_ACK")

    def test_final_raw_callback_cannot_mutate_saved_source_return(self):
        self.final_boundary("raw", lambda owner: object.__setattr__(next(iter(owner.initial_sources.values())), "raw", b"{}\n"))

    def test_final_local_callback_cannot_extend_pinned_local_ceiling(self):
        self.final_boundary("local", lambda owner: setattr(owner, "local_end", owner.local_end + 1))

    def test_final_cancellation_callback_cannot_mutate_original_phase(self):
        self.final_boundary("cancel", lambda owner: object.__setattr__(owner.phase_originals, "context", b"{}\n"))

    def test_cancellation_arriving_at_final_callback_cannot_register_return(self):
        self.final_boundary("cancel", lambda _owner: self.cancelled.append("SYNTHETIC_LATE_CANCEL"), "CANCELLED")

    def test_final_raw_highwater_mutation_is_not_overwritten_by_successful_observation(self):
        self.final_boundary("raw", lambda owner: setattr(owner.fence, "last", owner.fence.last - 1))

    def test_expiry_during_new_owner_close_cannot_register_return(self):
        close = S.Owner.close
        def changed(owner):
            close(owner)
            if type(owner.fence) is N._ReadmissionWindow and hasattr(owner, "initial_sources"):
                self.fixture.ns = owner.fence.final
        with patch.object(S.Owner, "close", changed):
            self.refuse_worker("ENTRY_WINDOW_EXPIRED")

    def test_policy_expiry_during_new_owner_close_cannot_register_return(self):
        close = S.Owner.close
        def changed(owner):
            close(owner)
            if type(owner.fence) is N._ReadmissionWindow and hasattr(owner, "initial_sources"):
                self.stack.enter_context(patch.object(N.time, "time", return_value=F.F.F.END))
        with patch.object(S.Owner, "close", changed):
            self.refuse_worker("RECIPIENT_POLICY_VALIDITY")

    def test_historical_return_checker_is_data_only_and_never_admission_or_renewal(self):
        result = self.worker()
        with patch.object(O.clocks, "observe", side_effect=AssertionError("must not observe")), \
                patch.object(N.time, "time", side_effect=AssertionError("must not revalidate current policy")):
            self.assertIs(N.check_readmission_return(result), result)
            with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_READMISSION_RETURN"):
                N.check_readmission_return(F.dataclasses.replace(result))
        with self.assertRaises(O.OriginError):
            O.admitted_value(result)
        with self.assertRaisesRegex(I.AdmissionError, "RETIRED"):
            result.window.now()

    def test_return_bytes_cannot_be_rewritten_even_coherently(self):
        result = self.worker()
        value = json.loads(result.raw)
        value["budgetAcceptance"] = "SYNTHETIC_GRANT"
        object.__setattr__(result, "raw", O.encoded(value))
        with self.assertRaisesRegex(I.AdmissionError, "RETURN_BYTES_CHANGED"):
            N.check_readmission_return(result)

    def test_private_metadata_token_is_absent_from_all_retained_files(self):
        result = self.worker()
        for directory in (self.path, result.path):
            for path in directory.rglob("*"):
                if path.is_file():
                    self.assertNotIn(F.TOKEN.encode(), path.read_bytes())
        self.assertNotIn(O.wire.TOKEN_ENV, F.os.environ)
        for child in self.child_envs:
            self.assertNotIn("GITHUB_TOKEN", child)
        self.assertEqual(len(self.fixture.requests), 16)

    def test_stack_token_is_cleared_when_initial_clock_fails_before_owner_creation(self):
        primary = O.clocks.ClockError("SYNTHETIC_FIRST_CLOCK_FAILURE")
        self.choose("worker", "desktop-linux-x64")
        try:
            with patch.object(O.clocks, "observe", side_effect=primary):
                N._prepare_and_readmit_worker(self.cancelled)
        except O.clocks.ClockError as error:
            self.assertIs(error, primary)
            trace = error.__traceback__
            checked = []
            while trace:
                if trace.tb_frame.f_code.co_name in ("_prepare_and_readmit_worker", "_prepare_with_token"):
                    self.assertIsNone(trace.tb_frame.f_locals["token"])
                    checked.append(trace.tb_frame.f_code.co_name)
                trace = trace.tb_next
            self.assertEqual(len(checked), 2)
        else:
            self.fail("missing original clock failure")
        self.assertNotIn(O.wire.TOKEN_ENV, F.os.environ)
        self.assertFalse(N._PREPARED_RETURNS)


if __name__ == "__main__":
    unittest.main()
