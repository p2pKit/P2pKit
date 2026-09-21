#!/usr/bin/env python3
"""Offline recipient sender controls; no native/GPG/provider/hosted execution.

Only tiny ordinary-UID POSIX files are real. The retained recipient fixtures
model Git, HTTP, process/native and crypto suppliers. Inherited controls are
not new sender coverage; select only this class's own methods.
"""
from __future__ import annotations

import ast
import copy
import dataclasses
import importlib.util
import io
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("initial_sender_recipient_fixtures",
    Path(__file__).with_name("hosted-initial-recipient-validation-test.py"))
V = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = V
spec.loader.exec_module(V)  # The pre-project process/network/native-loader guard stays active.
N, S, O, I = V.N, V.S, V.O, V.I


class SenderModels(V.RecipientModels):
    def setUp(self):
        super().setUp()
        self.sender_owners = []
        self.sender_raw, self.sender_raw_closes = [], []
        initialize = S.Owner.__init__
        def tracked(owner, *args, **kwargs):
            initialize(owner, *args, **kwargs)
            if type(owner.fence).__name__ == "SenderFence":
                self.sender_owners.append((owner, owner.resources))
        self.stack.enter_context(patch.object(S.Owner, "__init__", new=tracked))
        new, create = N.Q._new_private_directory, N.Q._PosixDirectory.create_file
        directory_close, writer_close = N.Q._PosixDirectory.close, N.Q._PosixSink.close
        def new_directory(path):
            returned = new(path)
            if path.name.endswith("-recipient-output"):
                self.sender_raw.append(returned)
            return returned
        def new_writer(parent, *args, **kwargs):
            returned = create(parent, *args, **kwargs)
            if any(parent is value for value in self.sender_raw):
                self.sender_raw.append(returned)
            return returned
        def directory_closed(raw):
            if any(raw is value for value in self.sender_raw):
                self.sender_raw_closes.append(raw)
            return directory_close(raw)
        def writer_closed(raw):
            if any(raw is value for value in self.sender_raw):
                self.sender_raw_closes.append(raw)
            return writer_close(raw)
        self.stack.enter_context(patch.object(N.Q, "_new_private_directory", side_effect=new_directory))
        self.stack.enter_context(patch.object(N.Q._PosixDirectory, "create_file", new=new_writer))
        self.stack.enter_context(patch.object(N.Q._PosixDirectory, "close", new=directory_closed))
        self.stack.enter_context(patch.object(N.Q._PosixSink, "close", new=writer_closed))
        self.addCleanup(self.retire_tiny_sender_files)

    def retire_tiny_sender_files(self):
        # These are exclusively tiny offline file fixtures, not a procedure to
        # recover a genuine UNKNOWN native/provider execution.
        for raw in reversed(self.sender_raw):
            if type(raw) is N.Q._PosixSink:
                raw.stream.close()  # Independently tracked real tiny fixture descriptor only.
            else:
                self.assertIs(type(raw), N.Q._PosixDirectory)  # This fixture owns no native directory handle.
        # The inherited native-model cleanup must not call sender capabilities
        # directly. Their independent, exclusively synthetic resources are now
        # retired above; keep the failing rows/flags themselves unchanged.
        S.QUARANTINE[:] = [value for value in S.QUARANTINE
            if not any(value is owner for owner, _rows in self.sender_owners)]
        if hasattr(N, "_RECIPIENT_SENDERS"):
            N._RECIPIENT_SENDERS.clear()

    def output_path(self, result):
        context = O.parse(N._RECIPIENT_RETURNS[id(result)][6].context)
        path = Path(context["session"])
        return path.with_name(path.name + "-output")

    def emit(self, prepared, *, write=None, flush=None):
        output = io.BytesIO()
        stream = SimpleNamespace(buffer=SimpleNamespace(write=write or output.write, flush=flush or output.flush))
        with patch.object(S.sys, "stdout", stream):
            S.guarded(lambda _cancelled: prepared)
        return output.getvalue()

    def test_closed_state_caps_are_pinned_at_original_return_not_sender_entry(self):
        result = self.worker()
        saved = N._RECIPIENT_RETURNS[id(result)]
        state = saved[3]
        for name in ("read_end", "read_local", "read_start", "last", "local_last"):
            before = getattr(state, name)
            with self.subTest(field=name):
                object.__setattr__(state, name, before + 1)
                try:
                    with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                        N.check_recipient_validation_return(result)
                finally:
                    object.__setattr__(state, name, before)
        original_dict = state.__dict__
        object.__setattr__(state, "__dict__", dict(original_dict))
        try:
            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                N.check_recipient_validation_return(result)
        finally:
            object.__setattr__(state, "__dict__", original_dict)
        self.assertIs(N.check_recipient_validation_return(result), result)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_RECIPIENT_VALIDATION_RETURN"):
            N.check_recipient_validation_return(dataclasses.replace(result))

    def test_fixed_public_sender_entry_exists_without_productive_or_workflow_options(self):
        self.assertTrue(callable(getattr(N, "validate_recipient", None)), "fixed sender entry is absent")
        with patch.object(S, "guarded") as guarded, patch.object(sys, "argv", [str(N.__file__), "validate-recipient"]):
            self.assertEqual(N.main(), 0)
            guarded.assert_called_once_with(N.validate_recipient)
        for option in ("--path", "--budget", "--token", "--admission", "--reader"):
            with self.subTest(option=option), patch.object(S, "guarded") as guarded, \
                    patch.object(sys, "argv", [str(N.__file__), "validate-recipient", option, "not-an-input"]), \
                    patch.object(sys, "stderr", io.StringIO()), self.assertRaises(SystemExit):
                N.main()
            guarded.assert_not_called()

    def test_sender_retains_two_exact_returns_and_only_emits_a_provisional_digest(self):
        result = self.worker()
        original = N._RECIPIENT_RETURNS[id(result)]
        readmission = N._recipient_claim(original[3].claim)[0]
        requests, queries, suppliers = len(self.fixture.requests), len(self.queries), len(self.suppliers)
        prepared = N._retain_recipient_validation(result)
        value, fence, limit = prepared
        path = self.output_path(result)
        self.assertEqual(sorted(p.name for p in path.iterdir()),
            ["readmission-return.json", "recipient-return.json", "sender-pending.json"])
        self.assertEqual((path / "readmission-return.json").read_bytes(), readmission.raw)
        self.assertEqual((path / "recipient-return.json").read_bytes(), result.raw)
        manifest_raw = (path / "sender-pending.json").read_bytes()
        manifest = O.parse(manifest_raw)
        self.assertEqual(manifest["scope"], N.RECIPIENT_SENDER_SCOPE)
        self.assertEqual(manifest["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(manifest["originalStepOutcome"], "NOT_OBSERVED")
        self.assertEqual(manifest["completeOriginals"], "NOT_ESTABLISHED_BY_THIS_BUNDLE")
        self.assertEqual(manifest["readWindow"]["readEndNs"], original[3].read_end)
        self.assertEqual(manifest["readWindow"]["readLocalCeiling"], original[3].read_local)
        self.assertEqual(limit, original[3].read_end)
        self.assertEqual(fence.local_end, original[3].read_local)
        self.assertEqual(value, S.public_result(N.RECIPIENT_OUTPUT_SCOPE, "recipientSenderSha256", manifest_raw))
        self.assertEqual(self.emit(prepared), O.encoded(value))
        self.assertNotIn(str(path).encode(), O.encoded(value))
        self.assertNotIn(V.F.TOKEN.encode(), O.encoded(value))
        self.assertEqual((len(self.fixture.requests), len(self.queries), len(self.suppliers)), (requests, queries, suppliers))
        self.assertEqual(len(self.sender_owners), 1)
        owner, rows = self.sender_owners[0]
        self.assertTrue(owner.closed)
        self.assertIsNone(owner.original)
        self.assertFalse(owner.unknown)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in rows))
        self.assertEqual(len(self.sender_raw), 4)
        self.assertEqual(len(self.sender_raw_closes), 4)
        self.assertTrue(all(sum(value is raw for value in self.sender_raw_closes) == 1 for raw in self.sender_raw))
        self.assertIs(N.check_recipient_validation_return(result), result)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            fence.now(final=True)

    def test_sender_never_reopens_or_observes_predecessor_or_acquires_current_authority(self):
        result = self.worker()
        trap = AssertionError("NO_PREDECESSOR_OR_AUTHORITY_EXECUTION")
        with patch.object(N._RecipientUseWindow, "now", side_effect=trap), \
                patch.object(N._RecipientUseWindow, "deadline", side_effect=trap), \
                patch.object(S.Owner, "open", side_effect=trap), \
                patch.object(N.time, "time", side_effect=trap), \
                patch.object(N.initial_identity, "bind_worker_match", side_effect=trap), \
                patch.object(N, "_recipient_authority", side_effect=trap), \
                patch.object(S.posix, "validate_recipient", side_effect=trap):
            self.emit(N._retain_recipient_validation(result))

    def test_expired_actual_read_cap_refuses_before_allocation_despite_later_nominal_cap(self):
        result = self.worker()
        state = N._RECIPIENT_RETURNS[id(result)][3]
        self.assertLess(state.read_end, state.ends[2])
        self.fixture.ns = state.read_end
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_EXPIRED"):
            N._retain_recipient_validation(result)
        self.assertEqual(self.sender_owners, [])
        self.assertFalse(self.output_path(result).exists())
        self.fixture.ns = state.last
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_ALREADY_CLAIMED"):
            N._retain_recipient_validation(result)

    def test_original_local_read_cap_cannot_be_replaced_by_fresh45_or_later_raw_cap(self):
        result = self.worker()
        state = N._RECIPIENT_RETURNS[id(result)][3]
        with patch.object(N.time, "monotonic", return_value=state.read_local), \
                self.assertRaisesRegex(I.AdmissionError, "SENDER_EXPIRED"):
            N._retain_recipient_validation(result)
        self.assertEqual(self.sender_owners, [])
        self.assertFalse(self.output_path(result).exists())

    def test_original_directory_id_cannot_be_replaced_during_postallocation_observation(self):
        result = self.worker()
        path = self.output_path(result)
        pending = []
        create, monotonic = N.Q._new_private_directory, N.time.monotonic
        def created(name):
            directory = create(name)
            if name == path:
                pending.append(directory)
            return directory
        def observed():
            if pending:
                directory = pending.pop()
                # Tiny real directories, no fabricated native ID: replace the
                # path and cohere the returned object's fields during the gap.
                path.rename(path.with_name(path.name + "-original"))
                path.mkdir(mode=0o700)
                directory.identity = N.Q.posix_files._identity(path)
            return monotonic()
        with patch.object(N.Q, "_new_private_directory", side_effect=created), \
                patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex((I.AdmissionError, N.Q.QueryError), "DIRECTORY|RESOURCE"):
            self.emit(N._retain_recipient_validation(result))
        self.assertFalse((path / "sender-pending.json").exists())

    def test_closing_clock_cannot_forge_row_flags_and_skip_the_actual_directory_close(self):
        result = self.worker()
        active, changed = [], []
        close, monotonic = S.Owner.close, N.time.monotonic
        def closing(owner):
            if type(owner.fence).__name__ == "SenderFence":
                active.append(owner)
            return close(owner)
        def observed():
            if active and active[-1].closed and not changed:
                row = next(row for row in active[-1].resources if row["label"] == "directory")
                self.assertFalse(row["owner"].closed)
                row["attempted"] = row["closed"] = True
                changed.append(row)
            return monotonic()
        with patch.object(S.Owner, "close", new=closing), patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex((I.AdmissionError, O.OriginError), "RESOURCE|CLOSE|RETIREMENT"):
            self.emit(N._retain_recipient_validation(result))
        self.assertEqual(len(changed), 1)

    def test_postclose_roster_alias_failure_retains_unknown_owner_in_quarantine(self):
        result = self.worker()
        close = S.Owner.close
        def replaced(owner):
            returned = close(owner)
            if type(owner.fence).__name__ == "SenderFence":
                owner.resources = list(owner.resources)
            return returned
        with patch.object(S.Owner, "close", new=replaced), self.assertRaisesRegex(I.AdmissionError, "OWNER_CHANGED"):
            N._retain_recipient_validation(result)
        owner = self.sender_owners[0][0]
        self.assertTrue(owner.unknown)
        self.assertTrue(any(value is owner for value in S.QUARANTINE))

    def test_new_first_reading_cannot_be_coherently_changed_before_close(self):
        result = self.worker()
        close = S.Owner.close
        def changed(owner):
            if type(owner.fence).__name__ == "SenderFence":
                object.__setattr__(owner.first, "nanoseconds", owner.first.nanoseconds + 1)
                owner.early_last += 1
            return close(owner)
        with patch.object(S.Owner, "close", new=changed), self.assertRaisesRegex(I.AdmissionError, "HISTORY_CHANGED"):
            self.emit(N._retain_recipient_validation(result))

    def test_rejected_output_use_is_sticky_and_cannot_be_followed_by_success(self):
        result = self.worker()
        prepared = N._retain_recipient_validation(result)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_OUTPUT_ONLY"):
            prepared[1].now(final=False)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            self.emit(prepared)

    def test_equal_directory_path_alias_is_pinned_before_postallocation_callback(self):
        result = self.worker()
        monotonic, changed = N.time.monotonic, []
        def observed():
            if self.sender_raw and not changed:
                raw = self.sender_raw[0]
                previous = raw.path
                raw.path = Path(str(previous))
                self.assertIsNot(raw.path, previous)
                changed.append(raw)
            return monotonic()
        with patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex(I.AdmissionError, "SENDER_RESOURCE_CHANGED"):
            N._retain_recipient_validation(result)
        self.assertEqual(len(changed), 1)
        self.assertFalse((self.output_path(result) / "sender-pending.json").exists())

    def test_writer_path_alias_is_pinned_at_factory_return_before_callback(self):
        result = self.worker()
        monotonic, changed = N.time.monotonic, []
        def observed():
            if len(self.sender_raw) > 1 and not changed:
                raw = self.sender_raw[-1]
                self.assertIs(type(raw), N.Q._PosixSink)
                previous = raw.path
                raw.path = Path(str(previous))
                self.assertIsNot(raw.path, previous)
                changed.append(raw)
            return monotonic()
        with patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex(I.AdmissionError, "SENDER_RESOURCE_CHANGED"):
            N._retain_recipient_validation(result)
        self.assertEqual(len(changed), 1)
        self.assertTrue(self.sender_owners[0][0].unknown)

    def test_newly_registered_row_is_pinned_before_first_postallocation_clock(self):
        result = self.worker()
        monotonic, changed = N.time.monotonic, []
        def observed():
            if self.sender_owners and self.sender_owners[0][1] and not changed:
                rows = self.sender_owners[0][1]
                original = rows[0]
                rows[0] = dict(original)
                changed.append(original)
            return monotonic()
        with patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex(I.AdmissionError, "RESOURCE|OWNER_CHANGED"):
            N._retain_recipient_validation(result)
        self.assertEqual(len(changed), 1)

    def test_forged_writer_row_flags_cannot_skip_actual_close(self):
        result = self.worker()
        monotonic, changed = N.time.monotonic, []
        def observed():
            if self.sender_owners and not changed:
                rows = self.sender_owners[0][1]
                writers = [row for row in rows if row["label"] == "writer"]
                if writers:
                    row = writers[0]
                    self.assertFalse(row["owner"].closed)
                    row["attempted"] = row["closed"] = True
                    changed.append(row)
            return monotonic()
        with patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex(I.AdmissionError, "SENDER_RESOURCE_CLOSE_LEDGER"):
            N._retain_recipient_validation(result)
        self.assertEqual(len(changed), 1)
        self.assertTrue(self.sender_owners[0][0].unknown)

    def test_returning_without_actual_raw_writer_close_is_not_success(self):
        result = self.worker()
        close, skipped = N.Q._PosixSink.close, []
        def no_close(raw):
            if any(raw is value for value in self.sender_raw):
                skipped.append(raw)
                return None  # Intentionally faulty synthetic supplier return, no native execution.
            return close(raw)
        with patch.object(N.Q._PosixSink, "close", new=no_close), \
                self.assertRaisesRegex(I.AdmissionError, "RESOURCE_CLOSE_CHANGED"):
            N._retain_recipient_validation(result)
        self.assertEqual(len(skipped), 1)
        self.assertFalse(skipped[0].stream.closed)
        self.assertTrue(any(value is self.sender_owners[0][0] for value in S.QUARANTINE))

    def test_original_raw_close_error_survives_erased_mutable_owner_errors(self):
        result = self.worker()
        failure = RuntimeError("SYNTHETIC_ORIGINAL_RAW_CLOSE_FAILURE")
        close, close_one, calls = N.Q._PosixSink.close, S.Owner.close_one, []
        def broken(raw):
            if any(raw is value for value in self.sender_raw):
                calls.append(raw)
                raise failure
            return close(raw)
        def erased(owner, raw):
            returned = close_one(owner, raw)
            if type(owner.fence).__name__ == "SenderFence":
                owner.original, owner.unknown = None, False
                owner.errors.clear()  # An adversarial model, never a production cleanup procedure.
            return returned
        with patch.object(N.Q._PosixSink, "close", new=broken), patch.object(S.Owner, "close_one", new=erased), \
                self.assertRaises(RuntimeError) as caught:
            N._retain_recipient_validation(result)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.sender_owners[0][0].unknown)
        self.assertTrue(any(value is self.sender_owners[0][0] for value in S.QUARANTINE))

    def copy_resource(self, result, label):
        acquire, copies = S.Owner.acquire, []
        def acquired(owner, kind, factory, *, final=False):
            returned = acquire(owner, kind, factory, final=final)
            if type(owner.fence).__name__ == "SenderFence" and kind == label and not copies:
                copied = copy.copy(returned)
                self.assertIsNot(copied, returned)
                calls = len(self.sender_raw_closes)
                with self.assertRaisesRegex(I.AdmissionError, "RESOURCE_NOT_ORIGINAL"):
                    if label == "directory":
                        copied.close()
                    else:
                        copied.write(b"UNAUTHORIZED_SYNTHETIC_WRITE")
                self.assertEqual(len(self.sender_raw_closes), calls)
                copies.append(copied)
            return returned
        with patch.object(S.Owner, "acquire", new=acquired), \
                self.assertRaisesRegex(I.AdmissionError, "RESOURCE_NOT_ORIGINAL"):
            N._retain_recipient_validation(result)
        self.assertEqual(len(copies), 1)

    def test_copied_directory_cannot_close_the_original_raw_resource(self):
        self.copy_resource(self.worker(), "directory")

    def test_copied_writer_cannot_write_through_the_original_raw_resource(self):
        result = self.worker()
        self.copy_resource(result, "writer")
        self.assertEqual((self.output_path(result) / "readmission-return.json").read_bytes(), b"")

    def test_known_directory_is_actually_closed_after_allocation_return_clock_expiry(self):
        result = self.worker()
        cap = N._RECIPIENT_RETURNS[id(result)][3].read_end
        monotonic, changed = N.time.monotonic, []
        def observed():
            if self.sender_raw and not changed:
                self.fixture.ns = cap
                changed.append(True)
            return monotonic()
        with patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex(I.AdmissionError, "SENDER_EXPIRED"):
            N._retain_recipient_validation(result)
        owner, rows = self.sender_owners[0]
        self.assertEqual(len(rows), 1)
        self.assertTrue(owner.closed)
        self.assertFalse(owner.unknown)
        self.assertTrue(rows[0]["attempted"] and rows[0]["closed"])
        self.assertEqual(self.sender_raw_closes, self.sender_raw)
        self.assertEqual(S.QUARANTINE, [])

    def test_mutated_payload_during_handler_restoration_never_reaches_stdout(self):
        prepared = N._retain_recipient_validation(self.worker())
        install, calls, output = S.signal.signal, {}, io.BytesIO()
        def changed(number, handler):
            calls[number] = calls.get(number, 0) + 1
            if calls[number] == 2:
                prepared[0]["scope"] = "MUTATED_NOT_AUTHORITY"
            return install(number, handler)
        with patch.object(S.signal, "signal", side_effect=changed), \
                self.assertRaisesRegex(I.AdmissionError, "HISTORY_CHANGED"):
            self.emit(prepared, write=output.write)
        self.assertEqual(output.getvalue(), b"")

    def test_mutated_payload_during_flush_refuses_even_after_digest_bytes_escape(self):
        prepared, output = N._retain_recipient_validation(self.worker()), io.BytesIO()
        original = O.encoded(prepared[0])
        def flush():
            prepared[0]["scope"] = "MUTATED_NOT_AUTHORITY"
        with self.assertRaisesRegex(I.AdmissionError, "HISTORY_CHANGED"):
            self.emit(prepared, write=output.write, flush=flush)
        self.assertEqual(output.getvalue(), original)

    def test_actual_raw_cap_expiry_during_flush_prevents_success_after_output(self):
        result, output = self.worker(), io.BytesIO()
        prepared = N._retain_recipient_validation(result)
        original = O.encoded(prepared[0])
        def flush():
            self.fixture.ns = N._RECIPIENT_RETURNS[id(result)][3].read_end
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_EXPIRED"):
            self.emit(prepared, write=output.write, flush=flush)
        self.assertEqual(output.getvalue(), original)

    def test_actual_local_cap_expiry_during_flush_prevents_success_after_output(self):
        result, output = self.worker(), io.BytesIO()
        prepared = N._retain_recipient_validation(result)
        monotonic, expired = N.time.monotonic, []
        def observed():
            return N._RECIPIENT_RETURNS[id(result)][3].read_local if expired else monotonic()
        with patch.object(N.time, "monotonic", side_effect=observed), \
                self.assertRaisesRegex(I.AdmissionError, "SENDER_EXPIRED"):
            self.emit(prepared, write=output.write, flush=lambda: expired.append(True))
        self.assertEqual(output.getvalue(), O.encoded(prepared[0]))

    def test_original_cancellation_during_flush_prevents_success_after_output(self):
        prepared, output = N._retain_recipient_validation(self.worker()), io.BytesIO()
        # The closed-original graph pins this list before the explicit empty-
        # cancellation predicate. Its first rejection must not be relabelled.
        with self.assertRaisesRegex(I.AdmissionError, "^INITIAL_NATIVE_RECIPIENT_HISTORY_CHANGED$"):
            self.emit(prepared, write=output.write, flush=lambda: self.cancelled.append(S.signal.SIGTERM))
        self.assertEqual(self.cancelled, [S.signal.SIGTERM])
        self.assertEqual(output.getvalue(), O.encoded(prepared[0]))
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            self.emit(prepared)

    def test_short_output_write_is_failure_and_cannot_be_replayed_to_success(self):
        prepared = N._retain_recipient_validation(self.worker())
        with self.assertRaisesRegex(O.OriginError, "BOOTSTRAP_ACK_WRITE"):
            self.emit(prepared, write=lambda raw: len(raw) - 1)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            self.emit(prepared)

    def test_flush_error_is_failure_and_cannot_be_replayed_to_success(self):
        prepared, output = N._retain_recipient_validation(self.worker()), io.BytesIO()
        error = OSError("SYNTHETIC_STDOUT_FLUSH_FAILURE")
        def flush():
            raise error
        with self.assertRaises(OSError) as caught:
            self.emit(prepared, write=output.write, flush=flush)
        self.assertIs(caught.exception, error)
        self.assertEqual(output.getvalue(), O.encoded(prepared[0]))
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            self.emit(prepared)

    def test_copied_output_fence_cannot_emit_or_leave_the_original_reusable(self):
        prepared = N._retain_recipient_validation(self.worker())
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            copy.copy(prepared[1]).now(final=True)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            self.emit(prepared)

    def test_output_registry_replacement_is_refused_without_recapturing_it(self):
        prepared = N._retain_recipient_validation(self.worker())
        with patch.object(N, "_RECIPIENT_SENDERS", dict(N._RECIPIENT_SENDERS)), \
                self.assertRaisesRegex(I.AdmissionError, "SENDER_ORIGINAL_REGISTRY_CHANGED"):
            self.emit(prepared)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_NOT_LIVE"):
            self.emit(prepared)

    def test_existing_output_is_not_overwritten_and_failed_claim_cannot_retry(self):
        result = self.worker()
        path = self.output_path(result)
        path.mkdir(mode=0o700)
        original = b"PREEXISTING_SYNTHETIC_OUTPUT\n"
        (path / "sentinel").write_bytes(original)
        with self.assertRaises(FileExistsError):
            N._retain_recipient_validation(result)
        self.assertEqual((path / "sentinel").read_bytes(), original)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_ALREADY_CLAIMED"):
            N._retain_recipient_validation(result)

    def test_original_owner_short_write_error_is_not_replaced_by_later_fence_error(self):
        result = self.worker()
        write, record, errors = N.Q._PosixSink.write, S.Owner.error, []
        def short(raw, data):
            return write(raw, data[:-1] if any(raw is value for value in self.sender_raw) else data)
        def recorded(owner, stage, error, **kwargs):
            if type(owner.fence).__name__ == "SenderFence" and stage == "write":
                errors.append(error)
            return record(owner, stage, error, **kwargs)
        with patch.object(N.Q._PosixSink, "write", new=short), patch.object(S.Owner, "error", new=recorded), \
                self.assertRaises((I.AdmissionError, O.OriginError)) as caught:
            N._retain_recipient_validation(result)
        self.assertEqual(len(errors), 1)
        self.assertIn("BOOTSTRAP_SHORT_WRITE", str(errors[0]))
        self.assertIs(caught.exception, errors[0])

    def windows_wrapper(self, *, writer=False, parent=False):
        """Exact nested resource-helper unit, NOT outer history or Windows admission.

        Extract the maintained helper AST unchanged; supply only its surrounding
        lexical state. Actual PrivateDirectory/NativeFile/_Pin methods use a
        wholly synthetic API/handle. No DLL loader, syscall or native factory runs.
        """
        tree = ast.parse(Path(N.__file__).read_text())
        sender = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and
            node.name == "_retain_recipient_validation")
        helpers = [node for node in sender.body if isinstance(node, ast.FunctionDef) and
            node.name in ("windows_pin", "windows_pins", "retain")]
        self.assertEqual(sum(node.name == "retain" for node in helpers), 1)
        namespace = dict(N.__dict__, clock=SimpleNamespace(role="windows-x64"), held=[], windows_handles={},
            windows_rosters=[], phase="OWNER", failed=False, owner=SimpleNamespace(resources=[]))
        errors, closes = [], []
        def remember(error, *, unknown=False):
            namespace["failed"] = True
            errors.append((error, unknown))
        namespace["remember"] = remember
        exec(compile(ast.Module(body=helpers, type_ignores=[]), str(N.__file__), "exec"), namespace)
        W = S.windows
        info = W.FileInfo((17, "a" * 32), not writer, 0, 1, W.DIRECTORY if not writer else 0, 1, 1, 1)
        nodes = {17: info}
        api = SimpleNamespace(close=lambda handle: closes.append(handle), flush=lambda _handle: None,
            inspect=lambda handle, *_args, **_kwargs: nodes[handle])
        path = self.base / "SYNTHETIC_WINDOWS_RESOURCE_NO_NATIVE_FILE"
        pin = W._Pin(api, 17, str(path), info, private=True, writable=writer)
        pins = [pin]
        parent_pin = None
        if parent:
            parent_info = dataclasses.replace(info, identity=(17, "c" * 32), is_directory=True, attributes=W.DIRECTORY)
            nodes[16] = parent_info
            parent_pin = W._Pin(api, 16, str(path.parent), parent_info, private=True)
            pins.insert(0, parent_pin)
        raw = (W.NativeFile(api, pins, max_bytes=128, writable=True, deadline=N.time.monotonic() + 20)
            if writer else W.PrivateDirectory(api, pins))
        def cleanup():
            if writer:
                # Only this no-handle API model is affected. Do not use this
                # explicit synthetic teardown as a native UNKNOWN recovery path.
                raw._retired = True
                io.RawIOBase.close(raw)
        self.addCleanup(cleanup)
        label = "writer" if writer else "directory"
        wrapper = namespace["retain"](raw, label, path, N._history_graph(path))
        row = {"label": label, "owner": wrapper, "attempted": False, "closed": False}
        namespace["owner"].resources.append(row)
        namespace["held"][0][1]()
        return SimpleNamespace(raw=raw, wrapper=wrapper, row=row, pin=pin, pins=pins, closes=closes,
            parent=parent_pin, errors=errors, namespace=namespace, nodes=nodes, check=namespace["held"][0][1])

    def test_windows_within_close_substitution_cannot_release_a_different_parent_handle(self):
        model = self.windows_wrapper(parent=True)
        def close(handle):
            model.closes.append(handle)
            if handle == 17:
                model.parent.handle = 19  # An existing native boundary mutates data, not executable code.
        model.raw._api.close = close
        model.row["attempted"] = True
        with self.assertRaises(S.windows.FilesystemError):
            model.wrapper.close()
        self.assertEqual(model.closes, [17])
        self.assertEqual(model.parent.references, 1)
        self.assertTrue(any(unknown for _error, unknown in model.errors))

    def test_windows_original_pin_roster_cannot_be_replaced_before_close(self):
        model = self.windows_wrapper()
        model.raw._pins = []
        model.row["attempted"] = True
        with self.assertRaisesRegex(I.AdmissionError, "RESOURCE|PIN|HANDLE"):
            model.wrapper.close()
        self.assertEqual(model.closes, [])
        self.assertEqual(model.pin.references, 1)
        self.assertTrue(any(unknown for _error, unknown in model.errors))

    def test_windows_same_roster_edit_cannot_hide_original_native_handle(self):
        model = self.windows_wrapper()
        model.pins.clear()
        model.row["attempted"] = True
        with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
            model.wrapper.close()
        self.assertEqual(model.closes, [])
        self.assertEqual(model.pin.references, 1)

    def test_windows_writer_supplier_bounds_and_api_aliases_are_pinned(self):
        for name, replacement in (("_deadline", lambda old: old + 1), ("max_bytes", lambda old: old + 1),
                ("_api", lambda _old: SimpleNamespace()), ("_operation_lock", lambda _old: threading.RLock())):
            with self.subTest(field=name):
                model = self.windows_wrapper(writer=True)
                setattr(model.raw, name, replacement(getattr(model.raw, name)))
                with self.assertRaisesRegex(I.AdmissionError, "RESOURCE|PIN|HANDLE"):
                    model.check()

    def test_windows_shared_pins_retire_once_with_live_writer_and_temporary_clone(self):
        model = self.windows_wrapper()
        W, api = S.windows, model.raw._api
        clone = model.raw._clone()  # Temporary model reader/clone, not another sender owner.
        self.assertEqual(model.pin.references, 2)
        clone.close()
        model.check()  # Stable after-return count is again exactly one.
        path = model.raw.path / "synthetic-record.json"
        info = dataclasses.replace(model.pin.info, identity=(17, "b" * 32), is_directory=False, attributes=0)
        model.nodes[18] = info
        file_pin = W._Pin(api, 18, str(path), info, private=True, writable=True)
        raw = W.NativeFile(api, [model.pin.acquire(), file_pin], max_bytes=128, writable=True,
            deadline=N.time.monotonic() + 20)
        def cleanup():
            raw._retired = True
            io.RawIOBase.close(raw)
        self.addCleanup(cleanup)
        wrapper = model.namespace["retain"](raw, "writer", path, N._history_graph(path))
        row = {"label": "writer", "owner": wrapper, "attempted": False, "closed": False}
        model.namespace["owner"].resources.append(row)
        model.namespace["held"][1][1]()
        model.check()
        self.assertEqual(model.pin.references, 2)
        row["attempted"] = True
        wrapper.close()
        row["closed"] = True
        model.namespace["held"][1][1]()
        self.assertEqual((model.pin.references, file_pin.references), (1, 0))
        self.assertIsNone(file_pin.handle)
        model.check()
        model.row["attempted"] = True
        model.wrapper.close()
        model.row["closed"] = True
        model.check()
        model.namespace["held"][1][1]()
        self.assertEqual(model.pin.references, 0)
        self.assertIsNone(model.pin.handle)
        self.assertEqual(model.closes, [18, 17])
        self.assertEqual(model.errors, [])

    def test_windows_original_pin_fields_and_counters_cannot_be_recaptured(self):
        changes = (("api", lambda _old: SimpleNamespace()), ("handle", lambda old: old + 1),
            ("references", lambda old: old + 1), ("path", lambda old: old + "-changed"),
            ("info", lambda old: dataclasses.replace(old)), ("lock", lambda _old: threading.RLock()),
            *((name, lambda old: not old) for name in
                ("private", "inherited_allowed", "writable", "strict_streams", "immutable")),
            ("__dict__", lambda old: dict(old)))
        for name, change in changes:
            with self.subTest(field=name):
                model = self.windows_wrapper()
                setattr(model.pin, name, change(getattr(model.pin, name)))
                with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_(PIN_CHANGED|HANDLE_RETIREMENT)"):
                    model.check()
                self.assertEqual(model.closes, [])
                self.assertTrue(any(unknown for _error, unknown in model.errors))

    def test_windows_pin_info_dictionary_is_not_a_replaceable_same_value_alias(self):
        model = self.windows_wrapper()
        object.__setattr__(model.pin.info, "__dict__", dict(model.pin.info.__dict__))
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_PIN_CHANGED"):
            model.check()

    def test_windows_actual_closed_empty_list_cannot_be_replaced_later(self):
        model = self.windows_wrapper()
        model.row["attempted"] = True
        model.wrapper.close()
        model.row["closed"] = True
        model.check()
        model.raw._pins = []
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_RESOURCE_CHANGED"):
            model.check()
        self.assertEqual(model.closes, [17])

    def test_windows_actual_handle_error_is_retained_and_never_retried(self):
        model, calls = self.windows_wrapper(), []
        def broken(handle):
            calls.append(handle)
            raise RuntimeError("SYNTHETIC_NATIVE_HANDLE_CLOSE_FAILURE")
        model.raw._api.close = broken
        model.row["attempted"] = True
        with self.assertRaises(S.windows.FilesystemError) as caught:
            model.wrapper.close()
        with self.assertRaises(S.windows.FilesystemError) as again:
            model.check()
        self.assertIs(again.exception, caught.exception)
        with self.assertRaisesRegex(I.AdmissionError, "RESOURCE_CLOSE_REUSED"):
            model.wrapper.close()
        self.assertEqual(calls, [17])
        self.assertEqual(model.pin.references, 0)
        self.assertEqual(model.pin.handle, 17)  # Original ambiguous handle retained, not fabricated retirement.
        self.assertIs(model.namespace["windows_handles"][id(model.pin)][0], model.pin)
        self.assertTrue(any(unknown for _error, unknown in model.errors))

    def test_windows_guard_replacement_or_removal_stays_failed_after_public_restoration(self):
        for name in ("acquire", "release"):
            for remove in (False, True):
                with self.subTest(method=name, removal=remove):
                    model = self.windows_wrapper()
                    guard = getattr(model.pin, name)
                    if remove:
                        delattr(model.pin, name)
                    else:
                        setattr(model.pin, name, getattr(S.windows._Pin, name).__get__(model.pin))
                    with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_PIN_CHANGED") as caught:
                        model.check()
                    setattr(model.pin, name, guard)  # Synthetic public-field restoration is NOT recovery.
                    with self.assertRaises(I.AdmissionError) as retry:
                        model.pin.release()
                    self.assertIs(retry.exception, caught.exception)
                    self.assertEqual(model.closes, [])
                    self.assertEqual(model.pin.references, 1)

    def test_windows_new_pin_does_not_adopt_an_unwitnessed_count_or_instance_override(self):
        model = self.windows_wrapper()
        for changed in ("references", "acquire", "release"):
            with self.subTest(field=changed):
                pin = S.windows._Pin(model.raw._api, 20, str(model.raw.path), model.pin.info, private=True)
                if changed == "references":
                    pin.references = 2
                else:
                    setattr(pin, changed, getattr(S.windows._Pin, changed).__get__(pin))
                before = dict(pin.__dict__)
                with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_NEW_PIN_(REFERENCES|METHODS)"):
                    model.namespace["windows_pin"](pin)
                self.assertEqual(pin.__dict__, before)
        self.assertEqual(model.closes, [])

    def test_windows_original_method_return_shapes_are_witnessed_and_sticky(self):
        # Only the fake-API helper's original supplier is modeled. Its method
        # is fixed BEFORE guard installation, never replaced during a call.
        for name in ("acquire", "release"):
            with self.subTest(method=name):
                method = getattr(S.windows._Pin, name)
                def wrong_return(pin):
                    method(pin)
                    return object()
                with patch.object(S.windows._Pin, name, new=wrong_return):
                    model = self.windows_wrapper()
                with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_PIN_RETURN") as caught:
                    getattr(model.pin, name)()
                self.assertEqual(model.pin.references, 2 if name == "acquire" else 0)
                self.assertEqual(model.closes, [] if name == "acquire" else [17])
                # Fault model only: restored public fields cannot invent the
                # missing original return or justify retrying an ambiguous handle.
                model.pin.references, model.pin.handle = 1, 17
                with self.assertRaises(I.AdmissionError) as retry:
                    model.pin.release()
                self.assertIs(retry.exception, caught.exception)
                self.assertEqual(model.closes, [] if name == "acquire" else [17])

    def test_windows_failed_acquire_preserves_healthy_prefix_rollback_cleanup(self):
        model = self.windows_wrapper(parent=True)
        model.pin.handle = 19
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_HANDLE_RETIREMENT") as caught:
            S.windows._acquire(model.pins)
        self.assertEqual(model.parent.references, 1)  # Actual acquire2 then cleanup-release1.
        self.assertEqual(model.parent.handle, 16)
        self.assertEqual(model.closes, [])
        model.pin.handle = 17  # Synthetic restoration cannot clear the failed pin.
        with self.assertRaises(I.AdmissionError) as retry:
            model.pin.release()
        self.assertIs(retry.exception, caught.exception)
        model.parent.release()  # Global failure must not block THIS still-known healthy pin.
        self.assertEqual(model.closes, [16])
        self.assertIsNone(model.parent.handle)
        self.assertEqual((model.parent.references, model.pin.references), (0, 1))

    def test_windows_swallowed_release_reentry_cannot_return_success_or_retry(self):
        model, nested = self.windows_wrapper(), []
        def close(handle):
            model.closes.append(handle)
            try:
                model.pin.release()
            except I.AdmissionError as error:
                nested.append(error)  # Synthetic supplier swallows the nested failure.
        model.raw._api.close = close
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_PIN_REENTRY") as caught:
            model.pin.release()
        self.assertEqual(len(nested), 1)
        self.assertIs(caught.exception, nested[0])
        self.assertEqual(model.closes, [17])
        self.assertEqual(model.pin.references, 0)
        self.assertIsNone(model.pin.handle)
        with self.assertRaises(I.AdmissionError) as retry:
            model.pin.release()
        self.assertIs(retry.exception, caught.exception)
        self.assertEqual(model.closes, [17])

    def test_windows_bypassed_guard_cannot_advance_original_private_close_witness(self):
        model = self.windows_wrapper()
        S.windows._Pin.release(model.pin)  # Deliberate model bypass, not a supported caller.
        self.assertEqual(model.closes, [17])
        self.assertEqual(model.pin.references, 0)
        self.assertIsNone(model.pin.handle)
        model.row["attempted"] = True
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_HANDLE_RETIREMENT"):
            model.wrapper.close()
        self.assertEqual(model.closes, [17])
        self.assertTrue(any(unknown for _error, unknown in model.errors))

    def test_windows_copied_pin_cannot_call_a_guard_as_its_original_self(self):
        model = self.windows_wrapper()
        copied = copy.copy(model.pin)
        with self.assertRaisesRegex(I.AdmissionError, "SENDER_WINDOWS_PIN_NOT_ORIGINAL") as caught:
            model.pin.acquire.__func__(copied)
        with self.assertRaises(I.AdmissionError) as retry:
            model.pin.release()
        self.assertIs(retry.exception, caught.exception)
        self.assertEqual(model.closes, [])
        self.assertEqual(model.pin.references, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
