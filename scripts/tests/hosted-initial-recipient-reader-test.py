#!/usr/bin/env python3
"""Small borrowed-owner reader controls, not hosted/authority/crypto execution.

The three files and their POSIX directory are real, tiny and ordinary-UID.
Historical returns and current elapsed-clock readings are synthetic. No source,
HTTP, native process, provider, key or full recipient chain is acquired here.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes  # Stdlib initialization only, before the project-import guard.
import importlib.util
import inspect
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("initial_recipient_reader_subject",
    ROOT / "scripts/run-hosted-initial-recipient.py")
N = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = N
spec.loader.exec_module(N)
S, O, I, Q = N.native, N.O, N.I, N.Q
NS = O.NS


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class ReaderModels(unittest.TestCase):
    def setUp(self):
        self.assertNotEqual(os.geteuid(), 0, "tiny POSIX controls require an ordinary UID")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = tempfile.TemporaryDirectory(prefix="initial-reader-model-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.stack.enter_context(patch.dict(os.environ, {
            "GITHUB_JOB": "populate", "GITHUB_RUN_ID": "301", "GITHUB_RUN_ATTEMPT": "1",
            "RUNNER_TEMP": str(self.base)}, clear=True))
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.LINUX_DOMAIN, NS)
        self.first = O.clocks.Reading(self.clock, 500 * NS)
        self.cancel_calls = 0
        self.cancel_hook = self.deadline_hook = self.read_hook = lambda: None
        self.reads = []
        self.cancel_error = None
        case = self

        class Fence:
            clock = case.clock

            def deadline(self, maximum, *, final=False, limit=None):
                case.deadline_hook()
                return case.local_end

            def now(self, *, final=False, minimum=0, limit=None):
                return max(case.first.nanoseconds, minimum)

        self.fence = Fence()
        self.local_end = time.monotonic() + 20
        self.owner = S.Owner(self.local_end, self.fence, first=self.first, cancelled=self.cancel)
        # A borrower is not restricted to a brand-new owner with an empty roster.
        self.prefix_path = self.base / "already-owned"
        self.prefix_path.mkdir(mode=0o700)
        self.prefix = self.owner.open(self.prefix_path)
        self.path = self.base / "p2pkit-initial-recipient-301-1-worker-recipient-output"
        self.path.mkdir(mode=0o700)
        self.directory = self.owner.open(self.path)
        self.original_directory = self.directory
        self.ledger = self.owner.resources
        self.addCleanup(self.retire_fixture)
        self.entry, self.recipient = self.records()
        self.manifest = self.index()
        self.write_package()
        read = S.Owner.read

        def read_file(owner, directory, name, *args, **kwargs):
            self.reads.append((directory.path, name))
            raw = read(owner, directory, name, *args, **kwargs)
            self.read_hook()
            return raw

        self.stack.enter_context(patch.object(S.Owner, "read", new=read_file))

    def cancel(self):
        self.cancel_calls += 1
        self.cancel_hook()
        if self.cancel_error is not None:
            raise self.cancel_error

    def retire_fixture(self):
        # These are solely real tiny fixture directories (no native handles on
        # POSIX). Never apply this model-only recovery to a hosted UNKNOWN.
        self.cancel_hook = self.deadline_hook = self.read_hook = lambda: None
        for resource in (self.original_directory, self.prefix):
            resource.close()
        S.QUARANTINE.clear()
        Q.QUARANTINE.clear()
        S.diagnostics._QUARANTINE.clear()

    def records(self):
        clock = O.clock_value(self.clock)
        entry_window = {"schema": 1, "scope": N.ENTRY_WINDOW_SCOPE, "clock": clock,
            "firstNs": 100 * NS, "previousNs": 90 * NS, "workEndNs": 175 * NS, "finalEndNs": 220 * NS,
            "firstUseAt": 1000, "originalProductiveEntryEndNs": 400 * NS, "originalProposedJobEndNs": 900 * NS,
            "originalPreparationSha256": "1" * 64, "workerIdentitySha256": "2" * 64,
            "originalProposalSha256": "3" * 64, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        entry = {"schema": 1, "scope": N.READMISSION_SCOPE,
            "originalPreparationSha256": "1" * 64, "workerIdentitySha256": "2" * 64,
            "pendingSha256": "4" * 64, "serviceTimeBasisSha256": "5" * 64, "allocationProposalSha256": "3" * 64,
            "window": entry_window, "firstUseAt": 1000, "preCloseNs": 160 * NS, "closedNs": 170 * NS,
            "resourceCount": 3, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED",
            "workerAdmission": "NOT_PERFORMED", "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False}
        recipient_window = {"schema": 1, "scope": N.RECIPIENT_WINDOW_SCOPE, "clock": clock,
            "firstNs": 180 * NS, "previousNs": entry["closedNs"], "workEndNs": 420 * NS,
            "finalEndNs": 465 * NS, "readEndNs": 495 * NS, "firstUseAt": 1000,
            "originalReadmissionSha256": O.digest(O.encoded(entry)), "workerIdentitySha256": "2" * 64,
            "originalProposalSha256": "3" * 64, "originalFencesNs": {
                "recipient-validation": 700 * NS, "recipient-final": 750 * NS, "recipient-read": 800 * NS},
            "originalProposedJobEndNs": 900 * NS, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        recipient = {"schema": 1, "scope": N.RECIPIENT_RETURN_SCOPE, "window": recipient_window,
            "originalReadmissionSha256": O.digest(O.encoded(entry)), "workerIdentitySha256": "2" * 64,
            "authoritySha256": "6" * 64, "pendingSha256": "7" * 64, "preCloseNs": 440 * NS,
            "closedNs": 445 * NS, "resourceCount": 4, "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
            "liveRecipient": "NOT_TRANSFERRED", "currentRemoteAuthority": "NOT_GRANTED_BY_HISTORY",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        return entry, recipient

    def index(self):
        return {"schema": 1, "scope": N.RECIPIENT_SENDER_SCOPE, "directory": str(self.path),
            "directoryIdentity": list(self.directory.identity), "records": {}, "originalReferences": {
                "recipientSession": str(self.path.with_name(self.path.name.removesuffix("-output"))),
                "readmissionSession": str(self.base / "p2pkit-initial-recipient-301-1-worker-entry"),
                "scope": "PINNED_CONTEXT_REFERENCES_NOT_CURRENT_FILESYSTEM_OBSERVATIONS",
                "workerIdentitySha256": "2" * 64, "serviceTimeBasisSha256": "5" * 64,
                "originalProposalSha256": "3" * 64},
            "readWindow": {"clock": O.clock_value(self.clock), "previousNs": self.recipient["closedNs"],
                "previousLocal": 10.0, "readEndNs": 475 * NS, "readLocalCeiling": 30.0, "retainedNs": 450 * NS},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "originalStepOutcome": "NOT_OBSERVED",
            "completeOriginals": "NOT_ESTABLISHED_BY_THIS_BUNDLE", "liveRecipient": "NOT_TRANSFERRED",
            "currentRemoteAuthority": "NOT_GRANTED_BY_HISTORY", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}

    def write_package(self, *, relink=True):
        self.entry_raw = O.encoded(self.entry)
        if relink:
            self.recipient["originalReadmissionSha256"] = O.digest(self.entry_raw)
            self.recipient["window"]["originalReadmissionSha256"] = O.digest(self.entry_raw)
        self.recipient_raw = O.encoded(self.recipient)
        for name, raw in (("readmission-return.json", self.entry_raw), ("recipient-return.json", self.recipient_raw)):
            (self.path / name).write_bytes(raw)
            (self.path / name).chmod(0o600)
            self.manifest["records"][name] = {"bytes": len(raw), "sha256": O.digest(raw)}
        self.write_index()

    def write_index(self):
        self.manifest_raw = O.encoded(self.manifest)
        (self.path / "sender-pending.json").write_bytes(self.manifest_raw)
        (self.path / "sender-pending.json").chmod(0o600)
        self.sha = O.digest(self.manifest_raw)

    def read(self, **overrides):
        options = {"recipient_outcome": "success", "expected_sha256": self.sha, **overrides}
        return N._read_recipient_sender(self.owner, self.directory, **options)

    def refuse(self, pattern="INITIAL_NATIVE_RECIPIENT_READ"):
        with self.assertRaisesRegex(ValueError, pattern):
            self.read()

    def test_reader_entry_is_nonproductive_and_not_a_cli(self):
        reader = getattr(N, "_read_recipient_sender", None)
        self.assertTrue(callable(reader), "borrowed-owner sender reader is absent")
        self.assertEqual(tuple(inspect.signature(reader).parameters),
            ("owner", "directory", "recipient_outcome", "expected_sha256"))
        self.assertNotIn("_read_recipient_sender", inspect.getsource(N.main))

    def test_three_file_result_is_bytes_only_and_enclosing_owner_remains_live(self):
        before = tuple((row, dict(row)) for row in self.ledger)
        result = self.read()
        self.assertEqual(result, (self.manifest_raw, (
            ("readmission-return.json", self.entry_raw), ("recipient-return.json", self.recipient_raw))))
        self.assertIs(type(result), tuple)
        self.assertTrue(all(type(raw) is bytes for _name, raw in result[1]))
        self.assertFalse(self.owner.closed)
        self.assertIsNone(self.owner.original)
        self.assertFalse(self.owner.unknown)
        self.assertEqual(self.owner.local_end, self.local_end)
        self.assertTrue(all(self.ledger[i] is row and row == values for i, (row, values) in enumerate(before)))
        self.assertGreater(self.cancel_calls, 0)
        self.assertEqual(set(self.reads), {(self.path, name) for name in self.manifest["records"]} |
            {(self.path, "sender-pending.json")})

    def test_non_success_or_conclusion_shaped_outcomes_refuse_before_file_io(self):
        for value in (None, True, "Success", "success\n", "failure", "cancelled", "skipped", {"conclusion": "success"}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "RECIPIENT_READ_STEP_OUTCOME"):
                self.read(recipient_outcome=value)
        self.assertEqual(self.reads, [])

    def test_external_digest_is_required_and_never_taken_from_the_package(self):
        for value in (None, True, "", "a" * 63, "A" * 64, b"a" * 64):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "RECIPIENT_READ_ORIGINAL_HASH"):
                self.read(expected_sha256=value)
        self.assertEqual(self.reads, [])
        with self.assertRaisesRegex(ValueError, "RECIPIENT_READ_HASH_CHANGED"):
            self.read(expected_sha256="0" * 64)

    def test_gate_is_not_the_fixed_sender_location(self):
        os.environ["GITHUB_JOB"] = "initial-recipient-gate"
        self.refuse("RECIPIENT_WORKER_ONLY")
        self.assertEqual(self.reads, [])

    def test_different_run_cannot_reuse_the_registered_sender(self):
        os.environ["GITHUB_RUN_ID"] = "302"
        self.refuse("RECIPIENT_READ_LAYOUT")
        self.assertEqual(self.reads, [])

    def test_other_registered_directory_cannot_substitute_for_sender(self):
        self.directory = self.prefix
        self.refuse("RECIPIENT_READ_LAYOUT")
        self.assertEqual(self.reads, [])

    def test_unregistered_sender_directory_refuses_before_file_io(self):
        self.ledger.pop()
        self.refuse("DIRECTORY_NOT_OWNED")
        self.assertEqual(self.reads, [])

    def test_manifest_must_be_exact_canonical_json(self):
        raw = self.manifest_raw + b"\n"
        (self.path / "sender-pending.json").write_bytes(raw)
        self.sha = O.digest(raw)
        self.refuse("RECIPIENT_READ_INDEX")

    def test_unknown_manifest_member_is_not_ignored(self):
        self.manifest["approved"] = True
        self.write_index()
        self.refuse("RECIPIENT_READ_INDEX")

    def test_manifest_cannot_self_assert_step_success_or_authority(self):
        self.manifest["originalStepOutcome"] = "success"
        self.write_index()
        self.refuse("RECIPIENT_READ_INDEX")

    def test_original_reference_paths_are_fixed_not_traversed(self):
        self.manifest["originalReferences"]["recipientSession"] = str(self.base / "other")
        self.write_index()
        self.refuse("RECIPIENT_READ_REFERENCES")

    def test_current_directory_identity_must_match_manifest(self):
        self.manifest["directoryIdentity"][1] += 1
        self.write_index()
        self.refuse("RECIPIENT_READ_DIRECTORY")

    def test_extra_directory_member_refuses_even_when_not_referenced(self):
        (self.path / "extra").write_bytes(b"synthetic")
        self.refuse("RECIPIENT_READ_ROSTER")

    def test_missing_directory_member_refuses(self):
        (self.path / "recipient-return.json").unlink()
        self.refuse("RECIPIENT_READ_ROSTER")

    def test_blob_size_and_digest_are_not_recomputed_from_untrusted_bytes(self):
        self.manifest["records"]["recipient-return.json"]["sha256"] = "8" * 64
        self.write_index()
        self.refuse("RECIPIENT_READ_RECORD_CHANGED")

    def test_boolean_blob_length_is_not_integer_one(self):
        self.manifest["records"]["recipient-return.json"]["bytes"] = True
        self.write_index()
        self.refuse("RECIPIENT_READ_RECORD_BINDING")

    def test_return_hash_link_is_checked_even_with_coherent_manifest(self):
        self.recipient["originalReadmissionSha256"] = "8" * 64
        self.write_package(relink=False)
        self.refuse("RECIPIENT_READ_BINDING")

    def test_original_proposal_links_must_agree(self):
        self.recipient["window"]["originalProposalSha256"] = "8" * 64
        self.write_package()
        self.refuse("RECIPIENT_READ_BINDING")

    def test_first_use_is_not_reset_by_the_recipient_window(self):
        self.recipient["window"]["firstUseAt"] += 1
        self.write_package()
        self.refuse("RECIPIENT_READ_BINDING")

    def test_recipient_previous_floor_is_the_exact_closed_readmission(self):
        self.recipient["window"]["previousNs"] += 1
        self.write_package()
        self.refuse("RECIPIENT_READ_BINDING")

    def test_read_end_cannot_exceed_original_nominal_recipient_limit(self):
        self.manifest["readWindow"]["readEndNs"] = 496 * NS
        self.write_index()
        self.refuse("RECIPIENT_READ_CHRONOLOGY")

    def test_sender_retention_is_strictly_before_actual_read_end(self):
        self.manifest["readWindow"]["retainedNs"] = self.manifest["readWindow"]["readEndNs"]
        self.write_index()
        self.refuse("RECIPIENT_READ_CHRONOLOGY")

    def test_historical_local_values_are_not_current_process_deadlines(self):
        # A completely different LOCAL epoch is data, not authority/fresh time.
        self.manifest["readWindow"].update(previousLocal=1e30, readLocalCeiling=1e30 + 1e20)
        self.write_index()
        self.read()
        self.assertEqual(self.owner.local_end, self.local_end)

    def test_historical_local_window_must_be_finite_and_ordered(self):
        self.manifest["readWindow"].update(previousLocal=30.0)
        self.write_index()
        self.refuse("RECIPIENT_READ_LOCAL_RECORD")

    def test_readback_detects_postread_record_change(self):
        def change():
            if len(self.reads) == 3:
                (self.path / "readmission-return.json").write_bytes(self.entry_raw.replace(b"1000", b"1001"))
        self.read_hook = change
        self.refuse("RECIPIENT_READ_REREAD_CHANGED")

    def test_readback_detects_late_extra_member(self):
        def change():
            if len(self.reads) == 6:
                (self.path / "extra").write_bytes(b"synthetic")
        self.read_hook = change
        self.refuse("RECIPIENT_READ_ROSTER")

    def test_owner_callback_cannot_replace_cancellation(self):
        self.deadline_hook = lambda: setattr(self.owner, "cancelled", lambda: None)
        self.refuse("RECIPIENT_READ_OWNER_CHANGED")

    def test_owner_callback_cannot_extend_local_ceiling(self):
        self.deadline_hook = lambda: setattr(self.owner, "local_end", self.local_end + 1)
        self.refuse("RECIPIENT_READ_OWNER_CHANGED")

    def test_owner_callback_cannot_replace_resource_ledger(self):
        self.deadline_hook = lambda: setattr(self.owner, "resources", list(self.ledger))
        self.refuse("RECIPIENT_READ_OWNER_CHANGED")

    def test_owner_callback_cannot_drop_a_preexisting_resource(self):
        def change():
            self.deadline_hook = lambda: None
            self.ledger.pop(0)
        self.deadline_hook = change
        self.refuse("RECIPIENT_READ_ROSTER_CHANGED")

    def test_cancellation_is_explicit_even_with_deadline_only_fence(self):
        error = FalseyFailure("ORIGINAL_CANCELLATION")
        self.cancel_error = error
        with self.assertRaises(FalseyFailure) as raised:
            self.read()
        self.assertIs(raised.exception, error)
        self.assertIs(self.owner.original, error)
        self.assertEqual(self.reads, [])
        self.cancel_error = None
        with self.assertRaises(FalseyFailure) as retried:
            self.read()
        self.assertIs(retried.exception, error)

    def test_cancel_callback_mutation_cannot_pass_final_boundary(self):
        def change():
            if len(self.reads) >= 6:
                self.owner.work_limit = 999 * NS
        self.cancel_hook = change
        self.refuse("RECIPIENT_READ_OWNER_CHANGED")

    def on_final_cancellation(self, callback):
        # Arm at final directory verification, after all six original file reads.
        # Count only the two following checks' explicit cancellation callbacks.
        state = {"armed": False, "calls": 0, "ran": False}
        original = S._new_entry_owned
        def owned(*args, **kwargs):
            result = original(*args, **kwargs)
            if len(self.reads) == 6:
                state["armed"] = True
            return result
        def cancel():
            if state["armed"]:
                state["calls"] += 1
                if state["calls"] == 4:
                    state["ran"] = True
                    callback()
        self.cancel_hook = cancel
        self.stack.enter_context(patch.object(S, "_new_entry_owned", new=owned))
        return state

    def test_final_cancel_callback_cannot_spend_remaining_original_local_time(self):
        clock = [self.local_end - 1]
        state = self.on_final_cancellation(lambda: clock.__setitem__(0, self.local_end))
        with patch.object(time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(S.posix.EvidenceError, "exceeded its deadline") as failed:
                self.read()
        self.assertTrue(state["ran"])
        self.assertIs(self.owner.original, failed.exception)
        self.assertEqual(self.owner.local_end, self.local_end)

    def test_final_cancel_callback_cannot_spend_remaining_borrowed_raw_time(self):
        exhausted = []
        error = O.OriginError("SYNTHETIC_BORROWED_RAW_EXPIRED")
        state = self.on_final_cancellation(lambda: exhausted.append(True))
        def raw_fence():
            if exhausted:
                raise error
        self.deadline_hook = raw_fence
        with self.assertRaises(O.OriginError) as failed:
            self.read()
        self.assertTrue(state["ran"])
        self.assertIs(failed.exception, error)
        self.assertIs(self.owner.original, error)
        self.assertEqual(self.owner.local_end, self.local_end)

    def test_existing_falsey_error_remains_primary(self):
        error = FalseyFailure("EARLIER_ORIGINAL")
        self.owner.error("synthetic-earlier", error)
        with self.assertRaises(FalseyFailure) as raised:
            self.read()
        self.assertIs(raised.exception, error)

    def test_prior_unknown_refuses_and_is_not_cleared(self):
        self.owner.unknown = True
        self.refuse("RECIPIENT_READ_OWNER_NOT_LIVE")
        self.assertTrue(self.owner.unknown)
        self.assertEqual(self.reads, [])

    def test_reader_never_initializes_or_acquires_authority_or_reconstructs_registry(self):
        trap = AssertionError("NO_ACQUISITION_OR_AUTHORITY")
        registries = (N._RECIPIENT_RETURNS, N._READMISSION_RETURNS, N._RECIPIENT_WINDOWS, N._AUTHORITY_RETURNS)
        saved = tuple(dict(value) for value in registries)
        with patch.object(S.Owner, "__init__", side_effect=trap), patch.object(S.Owner, "open", side_effect=trap), \
                patch.object(S.Owner, "write", side_effect=trap), patch.object(S.Owner, "close", side_effect=trap), \
                patch.object(O.clocks, "observe", side_effect=trap), patch.object(N, "_recipient_authority", side_effect=trap), \
                patch.object(N, "source_queries", side_effect=trap), patch.object(N, "_recipient_claim", side_effect=trap), \
                patch.object(N, "check_recipient_validation_return", side_effect=trap), \
                patch.object(S._InitializerParent, "__init__", side_effect=trap):
            self.read()
        self.assertEqual(tuple(dict(value) for value in registries), saved)
        self.assertEqual(sorted(p.name for p in self.base.iterdir()), [self.prefix_path.name, self.path.name])


class ComposedReaderModel(unittest.TestCase):
    def test_sender_bytes_and_digest_reach_the_borrowed_reader_without_authority_transfer(self):
        # New sender->reader seam coverage, not a replay of accepted sender tests.
        # All upstream native/Git/HTTP/GPG suppliers still are explicit models.
        import io
        from types import SimpleNamespace
        spec = importlib.util.spec_from_file_location("reader_composed_recipient_models",
            Path(__file__).with_name("hosted-initial-recipient-validation-test.py"))
        fixture = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = fixture
        spec.loader.exec_module(fixture)
        case = fixture.RecipientModels("runTest")
        case.setUp()
        self.addCleanup(case.doCleanups)
        n, s, o = fixture.N, fixture.S, fixture.O
        returned = case.worker()
        prepared = n._retain_recipient_validation(returned)
        output = io.BytesIO()
        with patch.object(s.sys, "stdout", SimpleNamespace(buffer=output)):
            s.guarded(lambda _cancelled: prepared)
        emitted = o.parse(output.getvalue())
        self.assertEqual(emitted["scope"], n.RECIPIENT_OUTPUT_SCOPE)
        recipient_path = n._recipient_path()
        path = recipient_path.with_name(recipient_path.name + "-output")
        first = o.clocks.Reading(case.fixture.clock, case.fixture.ns)
        local_end = time.monotonic() + 15  # Synthetic borrower, not a production receiving window.

        class Fence:
            clock = first.clock

            def deadline(self, maximum, *, final=False, limit=None):
                return local_end

            def now(self, *, final=False, minimum=0, limit=None):
                return max(first.nanoseconds, minimum)

        owner = s.Owner(local_end, Fence(), first=first, cancelled=lambda: s.cancellation(case.cancelled))
        try:
            directory = owner.open(path)
            requests, queries = len(case.fixture.requests), len(case.queries)
            original_registry = dict(n._RECIPIENT_RETURNS)
            data = n._read_recipient_sender(owner, directory, recipient_outcome="success",
                expected_sha256=emitted["recipientSenderSha256"])
            self.assertEqual(o.digest(data[0]), emitted["recipientSenderSha256"])
            self.assertEqual(dict(data[1])["recipient-return.json"], returned.raw)
            self.assertFalse(owner.closed)
            self.assertEqual((len(case.fixture.requests), len(case.queries)), (requests, queries))
            self.assertEqual(n._RECIPIENT_RETURNS, original_registry)
        finally:
            owner.close()
        self.assertIsNone(owner.original)
        self.assertFalse(owner.unknown)


if __name__ == "__main__":
    unittest.main()
