#!/usr/bin/env python3
"""Offline same-call old-owner close controls, not productive/native acceptance.

Only tiny actual ordinary-UID POSIX files close. Native query/process/service,
different-process identity and clocks are explicit models. No inherited tests
are included and no completed public adopter is resurrected into a live entry.
"""
from __future__ import annotations

from contextlib import contextmanager, ExitStack
import copy
from dataclasses import FrozenInstanceError, replace
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("bootstrap_close_entry_models",
    Path(__file__).with_name("hosted-cache-bootstrap-entry-test.py"))
E = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = E
spec.loader.exec_module(E)
S, O = E.S, E.O
import hosted_dependency_cache as cache


class CloseModels(E.EntryModels):
    @contextmanager
    def live(self):
        """Actual live owner/outer admit/entry, with explicit native models.

        This is a dedicated fixture, not a modified public adopter. Its finally
        retains its own cleanup responsibility if the close gate rejects input.
        """
        path, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack), self.actual_readmission_wrapper() as (calls, admitted):
            local_end = S.time.monotonic() + 45
            first = O.clocks.validate_reading(O.clocks.observe())
            cancel = lambda: S.cancellation(self.cancelled)
            owner = S.Owner(local_end, first=first, cancelled=cancel)
            try:
                selection, actual_path, event = S.host_inputs(first.clock.role)
                self.assertEqual(actual_path, path)
                inherited = S.query._inherited_context()
                S.child_environment(path)
                private = owner.open(path)
                handoff_raw = owner.read(private, "prepare-handoff.json")
                self.assertEqual(O.digest(handoff_raw), ack["handoffSha256"])
                context_raw = owner.read(private, "context.json")
                frame = owner.read(private, "prelude.json")
                fence = O.Fence(O.parse(frame), minimum=first.nanoseconds, cancelled=cancel)
                owner.bind(fence, work_limit=fence.work, final_limit=fence.final)
                prior, context, before = S.prepared_content(owner, private, handoff_raw, context_raw, fence)
                self.assertEqual((context["selection"], prior.original_event, context["inheritedContext"]),
                                 (selection, event, inherited))
                target = owner.new(path.with_name(path.name + "-adoption"))
                current, returned = S.admit(owner, fence, target.path / "admission", expected=prior)
                owner.write(target, "admission-return.json", returned)
                entry = S.execution_entry(owner, target, private, handoff_raw, context_raw, current, before, fence)
                self.assertIs(current, admitted)
                self.assertFalse(owner.closed)
                yield SimpleNamespace(owner=owner, fence=fence, target=target, private=private,
                    entry=entry, path=path, calls=calls, first=first)
            finally:
                if not owner.closed:
                    owner.close()

    def close(self, call):
        return S.close_entry_transition(call.owner, call.target, call.entry, call.fence)

    def reject_without_touch(self, call, **changes):
        args = dict(owner=call.owner, target=call.target, entry=call.entry, fence=call.fence)
        args.update(changes)
        with ExitStack() as guards:
            for name in ("read", "write", "acquire", "close", "open", "new"):
                guards.enter_context(patch.object(S.Owner, name, side_effect=AssertionError("NO_REJECTED_INPUT_IO")))
            with self.assertRaises(O.OriginError):
                S.close_entry_transition(**args)

    def change_during_retention(self, relative):
        with self.live() as call:
            original = S.Owner.write
            def write(owner, directory, name, *args, **kwargs):
                raw = original(owner, directory, name, *args, **kwargs)
                if owner is call.owner and name == "entry-close-pending.json":
                    file = call.path / relative
                    file.write_bytes(file.read_bytes() + b" ")
                return raw
            with patch.object(S.Owner, "write", write), self.assertRaises(ValueError):
                self.close(call)
            self.assertTrue(call.owner.closed)
            self.assertIsNone(call.owner.entry_close_original)
            self.assertTrue((call.target.path / "entry-close-pending.json").is_file())

    def bad_roster(self, mutate):
        with self.live() as call:
            original, calls = S.Owner.close, []
            def close(owner):
                original(owner)
                if owner is call.owner:
                    calls.append(True)
                    mutate(owner)
            with patch.object(S.Owner, "close", close), self.assertRaisesRegex(O.OriginError, "ENTRY_CLOSE_ROSTER"):
                self.close(call)
            self.assertEqual(calls, [True])
            self.assertTrue(call.owner.unknown)
            self.assertTrue(any(owner is call.owner for owner in S.QUARANTINE))
            self.assertIsNone(call.owner.entry_close_original)
            # Original row/object references survive even if resources was emptied.
            self.assertGreater(len(call.owner.entry_close_snapshot[1]), 2)

    def test_actual_live_entry_close_binds_originals_and_never_grants_productive_authority(self):
        with self.live() as call:
            before = {p.relative_to(call.path): p.read_bytes() for p in call.path.rglob("*") if p.is_file()}
            first_count = len(call.owner.resources)
            with patch.object(call.owner, "close", wraps=call.owner.close) as closed:
                result = self.close(call)
            closed.assert_called_once()
            self.assertEqual(call.calls, ["construct", "native-model", "identity-model", "retain", "finalize"])
            self.assertIs(call.owner.entry_close_original, result)
            self.assertIs(type(result), S.ClosedEntryTransition)
            value = S.check_closed_entry_transition(result)
            self.assertEqual(value["scope"], "BOOTSTRAP_READ_ONLY_OWNER_CLOSED_NO_PRODUCTIVE_AUTHORITY_V1")
            self.assertEqual(value["oldOwnerRetirement"], "KNOWN_RESOURCE_CLOSE_ONLY")
            self.assertEqual(value["productiveOwner"], "NOT_CREATED")
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
            self.assertIs(value["exportSaveAuthority"], False)
            self.assertGreater(value["resourceCount"], first_count)
            self.assertEqual(value["resourceCount"], len(call.owner.resources))
            self.assertTrue(all(row["attempted"] is True and row["closed"] is True for row in call.owner.resources))
            proposal = O.parse(result.proposal_raw)
            self.assertEqual(proposal["serviceTimeBasis"],
                O.parse(call.entry.raw)["preparation"]["originalChain"]["serviceTimeBasis"])
            self.assertEqual(dict(result.responses), {name: (call.path / "service" / (name + ".json")).read_bytes()
                                                     for name in ("attempt", "jobs")})
            self.assertEqual(before, {p.relative_to(call.path): p.read_bytes() for p in call.path.rglob("*") if p.is_file()})
            self.assertEqual((len(self.requests), len(self.scopes)), (2, 1))
            self.assertGreater(result._checked_ns, value["closedNs"])
            self.assertEqual(result._checked_ns, call.fence.last)

    def test_preclose_file_stays_provisional_and_does_not_claim_its_later_roster(self):
        with self.live() as call:
            result = self.close(call)
            pending = O.parse(result.pending_raw)
            self.assertEqual(result.pending_raw, (call.target.path / "entry-close-pending.json").read_bytes())
            self.assertEqual((call.target.path / "entry-close-pending.json").stat().st_mode & 0o777, 0o600)
            self.assertEqual(pending["oldOwnerRetirement"], "PENDING_CLOSE")
            self.assertNotIn("resourceCount", pending)
            self.assertNotIn("closedNs", pending)
            self.assertFalse((call.target.path / "entry-close-result.json").exists())
            self.assertEqual(repr(result), "ClosedEntryTransition()")
            with self.assertRaises(FrozenInstanceError):
                result.raw = b"{}"

    def test_already_closed_writer_rows_are_not_closed_again(self):
        with self.live() as call, ExitStack() as guards:
            prior = [row["owner"] for row in call.owner.resources if row["attempted"]]
            self.assertTrue(prior)
            for value in prior:
                guards.enter_context(patch.object(value, "close", side_effect=AssertionError("NO_SECOND_CLOSE")))
            self.close(call)

    def test_copied_entry_rejects_before_io_or_cleanup(self):
        with self.live() as call:
            self.reject_without_touch(call, entry=replace(call.entry))
            self.assertFalse(call.owner.entry_close_attempted)

    def test_copied_owner_rejects_without_closing_the_actual_owner(self):
        with self.live() as call:
            self.reject_without_touch(call, owner=copy.copy(call.owner))
            self.assertFalse(call.owner.closed)

    def test_copied_fence_cannot_renew_the_original_owner(self):
        with self.live() as call:
            self.reject_without_touch(call, fence=copy.copy(call.fence))

    def test_same_path_foreign_target_is_not_the_owned_object(self):
        with self.live() as call:
            foreign = S.query._PosixDirectory(call.target.path)
            try:
                self.reject_without_touch(call, target=foreign)
            finally:
                foreign.close()

    def test_copied_admission_registry_is_not_the_actual_return(self):
        with self.live() as call:
            key = str(call.target.path / "admission")
            original = call.owner.admissions[key]
            call.owner.admissions[key] = (replace(original[0]), *original[1:])
            try:
                self.reject_without_touch(call)
            finally:
                call.owner.admissions[key] = original

    def test_unregistered_preparation_handle_rejects_before_cleanup_claim(self):
        with self.live() as call:
            original, foreign = call.entry._private, S.query._PosixDirectory(call.private.path)
            object.__setattr__(call.entry, "_private", foreign)  # Explicit bad internal construction model.
            try:
                self.reject_without_touch(call)
                self.assertFalse(call.owner.entry_close_attempted)
            finally:
                object.__setattr__(call.entry, "_private", original)
                foreign.close()

    def test_reentrant_attempt_is_refused_before_another_supplier_call(self):
        with self.live() as call:
            original, calls = S._entry_close_proposal, []
            def proposal(entry, responses):
                self.reject_without_touch(call)
                calls.append(True)
                return original(entry, responses)
            with patch.object(S, "_entry_close_proposal", side_effect=proposal):
                self.close(call)
            self.assertEqual(len(calls), 2)

    def test_successful_transition_cannot_close_again_or_reuse_old_entry(self):
        with self.live() as call:
            self.close(call)
            self.reject_without_touch(call)
            with self.assertRaisesRegex(O.OriginError, "OWNER_NOT_LIVE"):
                S.check_execution_entry(call.owner, call.target, call.entry, call.fence, retained=True)

    def test_failed_retention_keeps_first_error_and_forbids_retry(self):
        with self.live() as call:
            failure, original = OSError("SYNTHETIC_PENDING_RETENTION"), S.Owner.write
            def write(owner, directory, name, *args, **kwargs):
                if owner is call.owner and name == "entry-close-pending.json":
                    raise failure
                return original(owner, directory, name, *args, **kwargs)
            with patch.object(S.Owner, "write", write), self.assertRaises(OSError) as caught:
                self.close(call)
            self.assertIs(caught.exception, failure)
            self.assertTrue(call.owner.closed)
            self.assertIsNone(call.owner.entry_close_original)
            self.assertTrue((call.target.path / "entry-close-failure.json").is_file())
            self.reject_without_touch(call)

    def test_changed_attempt_during_pending_retention_is_caught_by_final_reread(self):
        self.change_during_retention("service/attempt.json")

    def test_changed_jobs_during_pending_retention_is_caught_by_final_reread(self):
        self.change_during_retention("service/jobs.json")

    def test_changed_context_during_pending_retention_cannot_be_promoted(self):
        self.change_during_retention("context.json")

    def test_changed_handoff_during_pending_retention_cannot_be_promoted(self):
        self.change_during_retention("prepare-handoff.json")

    def test_changed_pending_readback_is_not_replaced_by_later_close(self):
        with self.live() as call:
            original = S.Owner.read
            def read(owner, directory, name, *args, **kwargs):
                raw = original(owner, directory, name, *args, **kwargs)
                return raw + b" " if owner is call.owner and name == "entry-close-pending.json" else raw
            with patch.object(S.Owner, "read", read), self.assertRaises(ValueError):
                self.close(call)
            self.assertIsNone(call.owner.entry_close_original)
            self.assertTrue((call.target.path / "entry-close-pending.json").is_file())

    def test_preexisting_pending_file_is_never_overwritten(self):
        with self.live() as call:
            path = call.target.path / "entry-close-pending.json"
            path.write_bytes(b"SYNTHETIC_EXISTING_ORIGINAL")
            path.chmod(0o600)
            with self.assertRaises(FileExistsError):
                self.close(call)
            self.assertEqual(path.read_bytes(), b"SYNTHETIC_EXISTING_ORIGINAL")
            self.assertIsNone(call.owner.entry_close_original)

    def test_empty_roster_after_close_is_not_vacuous_success(self):
        self.bad_roster(lambda owner: owner.resources.clear())

    def test_equal_replacement_resource_list_is_not_original_roster(self):
        self.bad_roster(lambda owner: setattr(owner, "resources", list(owner.resources)))

    def test_omitted_original_row_is_not_complete_close(self):
        self.bad_roster(lambda owner: owner.resources.pop())

    def test_reordered_original_rows_are_not_the_captured_roster(self):
        self.bad_roster(lambda owner: owner.resources.reverse())

    def test_equal_but_replaced_row_is_not_the_original_close_record(self):
        self.bad_roster(lambda owner: owner.resources.__setitem__(0, dict(owner.resources[0])))

    def test_foreign_resource_in_original_row_is_not_closed_original(self):
        self.bad_roster(lambda owner: owner.resources[0].update(owner=SimpleNamespace(close=lambda: None)))

    def test_nonboolean_close_status_cannot_be_promoted(self):
        self.bad_roster(lambda owner: owner.resources[0].update(closed=1))

    def test_returned_close_exception_is_not_hidden_by_closed_rows(self):
        with self.live() as call:
            original, failure = S.Owner.close, OSError("SYNTHETIC_OUTER_CLOSE_RETURN")
            def close(owner):
                original(owner)
                if owner is call.owner:
                    raise failure
            with patch.object(S.Owner, "close", close), self.assertRaises(OSError) as caught:
                self.close(call)
            self.assertIs(caught.exception, failure)
            self.assertIsNone(call.owner.entry_close_original)
            self.assertTrue(all(row["closed"] for row in call.owner.resources))

    def test_unknown_native_close_preserves_first_retention_failure(self):
        with self.live() as call:
            first, original_write, original_close = OSError("SYNTHETIC_FIRST_RETENTION"), S.Owner.write, call.target.close
            closed = []
            def write(owner, directory, name, *args, **kwargs):
                if owner is call.owner and name == "entry-close-pending.json":
                    raise first
                return original_write(owner, directory, name, *args, **kwargs)
            def close():
                original_close()
                closed.append(True)
                raise OSError("SYNTHETIC_LATER_CLOSE_UNKNOWN")
            with patch.object(S.Owner, "write", write), patch.object(call.target, "close", close), \
                    self.assertRaises(OSError) as caught:
                self.close(call)
            self.assertIs(caught.exception, first)
            self.assertEqual(closed, [True])
            self.assertTrue(call.owner.unknown)
            self.assertIsNone(call.owner.entry_close_original)

    def test_swallowed_close_fence_error_returning_normally_still_fails(self):
        with self.live() as call:
            original, failures = S.posix._deadline, []
            failure = S.posix.EvidenceError("SYNTHETIC_SINGLE_CLOSE_FENCE_FAILURE")
            def deadline(end):
                if call.owner.closed and not failures:
                    failures.append(True)
                    raise failure
                return original(end)
            # The actual close_fence catches this one failure and close returns
            # normally. Repeated expiry is a distinct error-saturation case below.
            with patch.object(S.posix, "_deadline", side_effect=deadline), \
                    self.assertRaises(S.posix.EvidenceError) as caught:
                self.close(call)
            self.assertIs(caught.exception, failure)
            self.assertEqual(failures, [True])
            self.assertFalse(call.owner.unknown)
            self.assertTrue(all(row["closed"] for row in call.owner.resources))
            self.assertIsNone(call.owner.entry_close_original)

    def test_repeated_close_fence_expiry_preserves_original_error_and_saturates_to_unknown(self):
        with self.live() as call:
            original = S.Owner.close
            def close(owner):
                if owner is call.owner:
                    self.nanoseconds = int(owner.local_end * O.NS)
                original(owner)
            with patch.object(S.Owner, "close", close), self.assertRaises(S.posix.EvidenceError) as caught:
                self.close(call)
            self.assertIs(caught.exception, call.owner.original)
            self.assertEqual(len(call.owner.errors), 64)
            self.assertTrue(call.owner.unknown)
            self.assertTrue(any(owner is call.owner for owner in S.QUARANTINE))
            self.assertIsNone(call.owner.entry_close_original)

    def test_original_local45_expiry_after_close_has_no_fresh_allowance(self):
        with self.live() as call:
            original = S.Owner.close
            def close(owner):
                original(owner)
                if owner is call.owner:
                    self.nanoseconds = int(owner.local_end * O.NS)
                    self.assertLess(self.nanoseconds, call.fence.final)
            with patch.object(S.Owner, "close", close), self.assertRaises(S.posix.EvidenceError):
                self.close(call)
            self.assertFalse(call.owner.unknown)
            self.assertIsNone(call.owner.entry_close_original)

    def test_original_final120_expiry_is_checked_even_with_earlier_local_clock(self):
        with self.live() as call:
            original = S.Owner.close
            def close(owner):
                original(owner)
                if owner is call.owner:
                    self.nanoseconds = owner.fence.final
            with patch.object(S.Owner, "close", close), \
                    patch.object(S.time, "monotonic", return_value=call.owner.local_end - 1), \
                    self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
                self.close(call)
            self.assertFalse(call.owner.unknown)
            self.assertIsNone(call.owner.entry_close_original)

    def test_work75_expiry_during_retention_is_not_final_time_for_more_work(self):
        with self.live() as call:
            original = S.Owner.write
            def write(owner, directory, name, *args, **kwargs):
                raw = original(owner, directory, name, *args, **kwargs)
                if owner is call.owner and name == "entry-close-pending.json":
                    self.nanoseconds = call.fence.work
                return raw
            with patch.object(S.Owner, "write", write), self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
                self.close(call)
            self.assertIsNone(call.owner.entry_close_original)
            self.assertTrue(call.owner.closed)

    def test_close_cannot_mutate_local_end_to_renew_it(self):
        with self.live() as call:
            original = S.Owner.close
            def close(owner):
                original(owner)
                if owner is call.owner:
                    owner.local_end += 45
            with patch.object(S.Owner, "close", close), self.assertRaisesRegex(O.OriginError, "LIMITS_CHANGED"):
                self.close(call)

    def test_close_cannot_mutate_original_shared_final_cutoff(self):
        with self.live() as call:
            original = S.Owner.close
            def close(owner):
                original(owner)
                if owner is call.owner:
                    owner.fence.final += 120 * O.NS
            with patch.object(S.Owner, "close", close), self.assertRaisesRegex(O.OriginError, "LIMITS_CHANGED"):
                self.close(call)

    def test_rejected_changed_limits_do_not_authorize_failure_file_acquisition(self):
        with self.live() as call:
            original, failures = S.Owner.write, []
            def write(owner, directory, name, *args, **kwargs):
                if owner is call.owner and name == "entry-close-failure.json":
                    failures.append(True)
                raw = original(owner, directory, name, *args, **kwargs)
                if owner is call.owner and name == "entry-close-pending.json":
                    owner.local_end += 45
                return raw
            with patch.object(S.Owner, "write", write), self.assertRaisesRegex(O.OriginError, "LIMITS_CHANGED"):
                self.close(call)
            self.assertEqual(failures, [], "a rejected frame cannot authorize even failure-retention I/O")
            self.assertTrue(call.owner.closed)
            self.assertIsNone(call.owner.entry_close_original)

    @contextmanager
    def after_content_callback(self, call, change):
        original_content, original_cancel = S._entry_close_content, S.cancellation
        validated, changed = [], []
        def content(transition):
            result = original_content(transition)
            validated.append(True)
            return result
        def cancel(cancelled):
            original_cancel(cancelled)
            if validated and not changed:
                change(call.owner)
                changed.append(True)
        with patch.object(S, "_entry_close_content", side_effect=content), \
                patch.object(S, "cancellation", side_effect=cancel):
            yield changed

    def test_postvalidation_nonraising_first_error_prevents_registration(self):
        with self.live() as call:
            failure = OSError("SYNTHETIC_LAST_CALLBACK_FAILURE")
            with self.after_content_callback(call, lambda owner: owner.error("last-callback", failure)) as changed, \
                    self.assertRaises(OSError) as caught:
                self.close(call)
            self.assertEqual(changed, [True])
            self.assertIs(caught.exception, failure)
            self.assertIsNone(call.owner.entry_close_original)

    def test_postvalidation_roster_uncertainty_is_quarantined_without_reclosing(self):
        with self.live() as call:
            with self.after_content_callback(call, lambda owner: owner.resources.clear()) as changed, \
                    patch.object(call.owner, "close", wraps=call.owner.close) as closed, \
                    self.assertRaisesRegex(O.OriginError, "ENTRY_CLOSE_ROSTER"):
                self.close(call)
            self.assertEqual(changed, [True])
            closed.assert_called_once()
            self.assertTrue(call.owner.unknown)
            self.assertTrue(any(owner is call.owner for owner in S.QUARANTINE))
            self.assertGreater(len(call.owner.entry_close_snapshot[1]), 2)
            self.assertIsNone(call.owner.entry_close_original)

    def test_first_backwards_postclose_read_cannot_recover_on_later_observation(self):
        with self.live() as call:
            original_close, original_observe, seen = S.Owner.close, O.clocks.observe, []
            def close(owner):
                original_close(owner)
                if owner is call.owner:
                    self.nanoseconds = call.fence.last - 2000
            def observe():
                if call.owner.closed:
                    seen.append(True)
                return original_observe()
            with patch.object(S.Owner, "close", close), patch.object(O.clocks, "observe", side_effect=observe), \
                    self.assertRaises(O.clocks.ClockError):
                self.close(call)
            self.assertIsNone(call.owner.entry_close_original)
            # Owner.close's own final observations also occur after closed=True;
            # the final one is the sole failing post-return observation.
            self.assertTrue(seen)

    def test_cancellation_during_retention_closes_known_resources_but_never_returns_token(self):
        with self.live() as call:
            original = S.Owner.write
            def write(owner, directory, name, *args, **kwargs):
                raw = original(owner, directory, name, *args, **kwargs)
                if owner is call.owner and name == "entry-close-pending.json":
                    self.cancelled.append(15)
                return raw
            with patch.object(S.Owner, "write", write), self.assertRaises(KeyboardInterrupt):
                self.close(call)
            self.assertTrue(call.owner.closed)
            self.assertFalse(call.owner.unknown)
            self.assertIsNone(call.owner.entry_close_original)

    def test_cancellation_after_actual_close_is_not_skipped_by_final_clock_mode(self):
        with self.live() as call:
            original = S.Owner.close
            def close(owner):
                original(owner)
                if owner is call.owner:
                    self.cancelled.append(15)
            with patch.object(S.Owner, "close", close), self.assertRaises(KeyboardInterrupt):
                self.close(call)
            self.assertIsNone(call.owner.entry_close_original)

    def test_no_postclose_file_or_new_owner_acquisition_on_success(self):
        with self.live() as call, ExitStack() as guards:
            for name in ("read", "write", "acquire", "open", "new", "child"):
                original = getattr(S.Owner, name)
                def guarded(owner, *args, _original=original, **kwargs):
                    self.assertFalse(owner.closed, "NO_POSTCLOSE_IO")
                    return _original(owner, *args, **kwargs)
                guards.enter_context(patch.object(S.Owner, name, guarded))
            guards.enter_context(patch.object(S.Owner, "__init__", side_effect=AssertionError("NO_NEW_OWNER")))
            guards.enter_context(patch.object(cache, "export_snapshot", side_effect=AssertionError("NO_EXPORT")))
            guards.enter_context(patch.object(cache, "save_set", side_effect=AssertionError("NO_SAVE_SET")))
            result = self.close(call)
            self.assertIs(result, call.owner.entry_close_original)

    def test_exact_return_validator_is_nonacquiring_and_copies_cannot_rehydrate_registry(self):
        with self.live() as call:
            result = self.close(call)
            expected = O.parse(result.raw)
            with ExitStack() as guards:
                for target, name in ((S.Owner, "read"), (S.Owner, "acquire"), (S.Owner, "__init__"),
                                     (O.clocks, "observe"), (S.time, "monotonic"), (Path, "read_bytes")):
                    guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_VALIDATOR_IO")))
                self.assertEqual(S.check_closed_entry_transition(result), expected)
                self.assertEqual(S.check_closed_entry_transition(result), expected)
                for copied in (replace(result), copy.copy(result), SimpleNamespace(raw=result.raw)):
                    with self.assertRaisesRegex(O.OriginError, "NOT_CURRENT_RETURN"):
                        S.check_closed_entry_transition(copied)

    def test_public_adopter_does_not_call_the_new_close_bridge(self):
        _, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack), patch.object(S, "close_entry_transition", side_effect=AssertionError("NO_NEW_CALLER")):
            _, result = self.public_adoption()
        self.assertEqual(result["scope"], "BOOTSTRAP_READ_ONLY_ADOPTION_PENDING_RETURN_V2")
        self.assertIs(result["exportSaveAuthority"], False)


def load_tests(loader, _tests, _pattern):
    return unittest.TestSuite(CloseModels(name) for name in sorted(CloseModels.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
