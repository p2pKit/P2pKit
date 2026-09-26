#!/usr/bin/env python3
"""Bounded offline Stage1 recipient connection; NO native/GPG/hosted execution.

The fixed driver and child really compose with tiny ordinary-UID POSIX files.
Git/HTTP/native/process/GPG suppliers and service clocks are explicit models.
Inherited historical tests are not new recipient controls.
"""
from __future__ import annotations

import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("initial_validation_native_fixtures",
    Path(__file__).with_name("hosted-initial-recipient-native-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)  # Its pre-project process/network/native-loader guard stays active.
N, S, O, I, Q = F.N, F.S, F.O, F.I, F.Q


class RecipientModels(F.NativeModels):
    def setUp(self):
        super().setUp()
        self.supplier_calls, self.suppliers, self.operations = [], [], []
        self.before_recipient = self.after_recipient = lambda: None
        self.supplier_change = lambda value: value
        self.native_change = lambda row: row
        self.after_crypto_drain = lambda: None
        self.crypto_descendants = []
        self.stack.enter_context(patch.object(S.posix, "validate_recipient", side_effect=self.validate))
        self.stack.enter_context(patch.object(S.diagnostics, "validate_recipient",
            side_effect=AssertionError("A Linux fixture must not execute the Windows supplier")))

    def reset_models(self):
        # Only synthetic native domains exist. Retained tiny fixture files can
        # be closed here; this is NOT a production UNKNOWN-recovery procedure.
        for state in list(N._RECIPIENT_WINDOWS.values()) + list(N._AUTHORITY_WINDOWS.values()):
            roster = state.roster
            if roster is not None:
                for row, label, resource, _a, _c in reversed(roster.seen):
                    if label != "native-scope" and type(row) is dict and not row.get("attempted"):
                        resource.close()
                        row["attempted"] = row["closed"] = True
        super().reset_models()
        for registry in (N._READMISSION_USES, N._RECIPIENT_ATTEMPTS, N._RECIPIENT_CLAIMS,
                         N._RECIPIENT_WINDOWS, N._AUTHORITY_WINDOWS, N._AUTHORITY_RETURNS,
                         N._RECIPIENT_NATIVE_RETURNS, N._RECIPIENT_RETURNS, N._RECIPIENT_CRYPTO_ORIGINALS):
            registry.clear()

    def validate(self, key_path, fingerprint, work_path):
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        self.assertNotIn("GITHUB_TOKEN", os.environ)
        self.assertEqual(key_path.read_bytes(), N._RECIPIENT_CLAIMS[next(iter(N._RECIPIENT_CLAIMS))][3].identity_fields[3])
        self.assertEqual(len(self.fixture.requests), 24)
        self.assertEqual(len(N._AUTHORITY_RETURNS), 1)
        for saved in N._AUTHORITY_RETURNS.values():
            self.assertTrue(saved[3].checked().terminal)
            self.assertTrue(saved[3].checked().roster.owner.closed)
        # Tiny explicit supplier OUTPUT models, never a GPG/key invocation.
        # The original successful parent now retains their shallow inventory.
        for name in ("gnupg", "tmp", "gpg-model001", "gpg-model002"):
            (work_path / name).mkdir(mode=0o700)
        files = {"recipient.asc": key_path.read_bytes(), "recipient.gpg": b"SYNTHETIC_PUBLIC_RING_NOT_A_KEY\n"}
        for operation in ("gpg-model001", "gpg-model002"):
            files.update({operation + "/stdout": b"SYNTHETIC_PUBLIC_LISTING\n", operation + "/stderr": b"",
                operation + "/status": b"", operation + "/process.json": b'{"synthetic":true}\n'})
        for name, raw in files.items():
            target = work_path / name
            with target.open("xb") as stream:
                stream.write(raw)
            target.chmod(0o600)
        info = work_path.stat()
        recipient = S.posix.Recipient(work_path, work_path / "gnupg", work_path / "SYNTHETIC_GPG_NEVER_EXECUTED",
            fingerprint, "E" * 40, 0, O.digest(key_path.read_bytes()), (info.st_dev, info.st_ino))
        self.supplier_calls.append((key_path, fingerprint, work_path))
        value = self.supplier_change(recipient)
        self.suppliers.append(value)
        return value

    def make_scope(self, job, invocation, state, home):
        path = Path(state)
        if path.name != "authority" and not path.name.endswith("-recipient"):
            return super().make_scope(job, invocation, state, home)
        case = self
        operation = "_service-authority" if path.name == "authority" else "_recipient"
        class Scope:
            name, baseline = "linux-proc-pidfd", set()
            def __init__(self):
                self.launches, self.closed, self.close_calls = [], False, 0
                self.operation = operation
            def _identity(self, pid): return {"pid": pid, "startTicks": 9012, "live": True}
            def spawn(self, argv, cwd, env, *, stdout, stderr):
                case.before_child()
                case.assertEqual(argv[4:6], [str(F.ROOT / "scripts/run-hosted-initial-recipient.py"), operation])
                case.operations.append(operation)
                case.child_envs.append(dict(env))
                if operation == "_service-authority":
                    case.assertEqual(env[O.wire.TOKEN_ENV], F.TOKEN)
                else:
                    case.assertNotIn(O.wire.TOKEN_ENV, env)
                    case.before_recipient()
                for name in ("GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL"):
                    case.assertNotIn(name, env)
                self.launches = [{"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv,
                    "cwd": cwd, "shell": False, "created": True, "executable": argv[0], "pid": 1234,
                    "outputMode": "caller-owned-files"}]
                def write(raw):
                    actual = case.ack_transform(raw) if case.ack_transform else raw
                    case.assertEqual(os.write(stdout.fileno(), actual), len(actual))
                    return len(raw)
                output = SimpleNamespace(buffer=SimpleNamespace(write=write, flush=stdout.sync))
                code = 0
                try:
                    with patch.dict(os.environ, env, clear=True), patch.object(S.sys, "stdout", output):
                        if operation == "_service-authority":
                            S.guarded(lambda cancelled: N.service_child(argv[-3], int(argv[-1]), cancelled, authority=True))
                        else:
                            S.guarded(lambda cancelled: N._recipient_child(argv[-3], int(argv[-1]), cancelled))
                except BaseException as error:
                    case.child_errors.append(error)
                    os.write(stderr.fileno(), b"SYNTHETIC_CHILD_FAILURE\n")
                    code = 125
                case.after_child()
                if operation == "_recipient":
                    case.after_recipient()
                return SimpleNamespace(pid=1234, stdout=None, stderr=None,
                    poll=lambda: code if case.child_exit is None else case.child_exit)
            def description(self):
                return case.native_change({"backend": self.name, "scope": "controlled-marker-inheriting-descendants",
                    "job": job, "invocation": invocation, "launches": self.launches,
                    "startedIdentities": ([{"pid": 1234, "startTicks": 5678, "uid": os.getuid(), "live": False}]
                        if self.launches else []),
                    "discoveryErrors": [], "discoveryReconciliations": []})
            def discover(self): return case.crypto_descendants if operation == "_recipient" else []
            def drain(self, *, grace, kill_wait, deadline):
                directory = "service" if operation == "_service-authority" else "recipient-validation"
                start = json.loads((path / directory / "start.json").read_bytes())
                case.assertLessEqual(deadline, start["finalEndNs"] / O.NS)
                case.assertLessEqual(grace + kill_wait, max(0, deadline - case.fixture.ns / O.NS))
                case.drains.append((grace, kill_wait, deadline))
                case.after_drain()
                if operation == "_recipient":
                    case.after_crypto_drain()
                return case.scope_survivors
            def close(self):
                self.closed = True
                self.close_calls += 1
                if case.scope_close_error is not None:
                    raise case.scope_close_error
        value = Scope()
        self.scopes.append(value)
        return value

    def worker(self):
        self.choose("worker", "desktop-linux-x64")
        return N._prepare_and_validate_recipient(self.cancelled)

    def readmission(self):
        self.choose("worker", "desktop-linux-x64")
        return N._prepare_and_readmit_worker(self.cancelled)

    def after_claim(self, change):
        claim = N._claim_recipient
        def claimed(result):
            self.recipient_claim = claim(result)
            change(self.recipient_claim)
            return self.recipient_claim
        self.stack.enter_context(patch.object(N, "_claim_recipient", side_effect=claimed))

    def refuse_worker(self, code, *, crypto=False):
        with self.assertRaisesRegex((I.AdmissionError, O.OriginError, O.wire.BudgetError,
                                   O.clocks.ClockError, RuntimeError), code):
            self.worker()
        self.assertFalse(N._RECIPIENT_RETURNS)
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        if not crypto:
            self.assertNotIn("_recipient", self.operations)
            self.assertEqual(self.supplier_calls, [])

    def window(self):
        claim = N._claim_recipient(self.readmission())
        local = self.fixture.ns / O.NS
        first = self.fixture.observe()
        return N._RecipientUseWindow(claim, local, first)

    def test_actual_three_acquisitions_then_credential_free_recipient_and_known_parent_close(self):
        result = self.worker()
        self.assertIs(type(result), N._RecipientValidationReturn)
        self.assertIs(N.check_recipient_validation_return(result), result)
        self.assertEqual(len(self.fixture.requests), 24)
        self.assertEqual(self.operations, ["_service-authority", "_recipient"])
        self.assertEqual(len(self.scopes), 4)
        self.assertTrue(all(scope.closed and scope.close_calls == 1 for scope in self.scopes))
        self.assertEqual(len(self.supplier_calls), 1)
        self.assertEqual(len(self.queries), 12)  # 3 per acquisition; child source pair; parent final source.
        self.assertTrue(all(query.closed and query.finalizations == 1 for query in self.queries))
        value = json.loads(result.raw)
        self.assertEqual(value["scope"], N.RECIPIENT_RETURN_SCOPE)
        self.assertEqual(value["liveRecipient"], "NOT_TRANSFERRED")
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertFalse(value["exportSaveAuthority"])
        self.assertEqual(value["currentRemoteAuthority"], "NOT_GRANTED_BY_HISTORY")
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
        self.assertFalse(self.child_errors)
        self.assertFalse(S.QUARANTINE)
        self.assertTrue(all(F.TOKEN.encode() not in path.read_bytes() for path in self.base.rglob("*") if path.is_file()))

    def test_gate_refuses_before_any_original_acquisition_or_native_allocation(self):
        with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_WORKER_ONLY"):
            N._prepare_and_validate_recipient(self.cancelled)
        self.assertEqual(self.queries, [])
        self.assertEqual(self.scopes, [])
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)

    def test_copied_readmission_and_claim_do_not_consume_or_replace_originals(self):
        result = self.readmission()
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_READMISSION_RETURN"):
            N._claim_recipient(dataclasses.replace(result))
        self.assertNotIn(id(result), N._RECIPIENT_ATTEMPTS)
        claim = N._claim_recipient(result)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_RECIPIENT_CLAIM"):
            N._recipient_claim(dataclasses.replace(claim))
        self.assertIs(N._recipient_claim(claim)[0].returned, result)

    def test_consumed_readmission_cannot_be_claimed_or_read_again(self):
        result = self.readmission()
        N._claim_recipient(result)
        for operation in (N._claim_recipient, N.check_readmission_return):
            with self.subTest(operation=operation.__name__), self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
                operation(result)
        self.assertFalse(N._READMISSION_USES)

    def test_failed_claim_is_irreversible_even_if_original_bytes_are_restored(self):
        result = self.readmission()
        raw = result.raw
        object.__setattr__(result, "raw", b"SYNTHETIC_MUTATION")
        with self.assertRaisesRegex(I.AdmissionError, "RETURN_BYTES_CHANGED"):
            N._claim_recipient(result)
        object.__setattr__(result, "raw", raw)
        with self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
            N._claim_recipient(result)
        self.assertFalse(N._READMISSION_USES)
        self.assertFalse(N._RECIPIENT_CLAIMS)

    def test_reentrant_claim_refuses_without_holding_lock_across_validation(self):
        result = self.readmission()
        check = N._readmission_content
        def checked(binding):
            self.assertTrue(N._RECIPIENT_USE_LOCK.acquire(blocking=False))
            N._RECIPIENT_USE_LOCK.release()
            with self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
                N._claim_recipient(binding.returned)
            return check(binding)
        with patch.object(N, "_readmission_content", side_effect=checked):
            claim = N._claim_recipient(result)
        self.assertIs(claim.original, result)

    def test_concurrent_historical_read_excludes_claim_but_not_registry_lock(self):
        result = self.readmission()
        entered, release = threading.Event(), threading.Event()
        check, values, errors = N._readmission_content, [], []
        def checked(binding):
            entered.set()
            self.assertTrue(release.wait(2), "synthetic reader coordination timeout")
            return check(binding)
        def reader():
            try:
                values.append(N.check_readmission_return(result))
            except BaseException as error:
                errors.append(error)
        with patch.object(N, "_readmission_content", side_effect=checked):
            thread = threading.Thread(target=reader)
            thread.start()
            try:
                self.assertTrue(entered.wait(2), "synthetic reader did not enter")
                self.assertTrue(N._RECIPIENT_USE_LOCK.acquire(blocking=False))
                N._RECIPIENT_USE_LOCK.release()
                with self.assertRaisesRegex(I.AdmissionError, "USE_IN_PROGRESS"):
                    N._claim_recipient(result)
                self.assertNotIn(id(result), N._RECIPIENT_ATTEMPTS)
            finally:
                release.set()
                thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(values, [result])
        self.assertIs(N._claim_recipient(result).original, result)

    def test_claim_pins_original_closed_identity_basis_clock_and_resource_graph(self):
        result = self.readmission()
        claim = N._claim_recipient(result)
        binding, original = N._recipient_claim(claim)
        changes = ((result, "raw", b"SYNTHETIC_RESULT"),
            (original, "service_time_raw", b"SYNTHETIC_BASIS"),
            (original, "proposal_raw", b"SYNTHETIC_PROPOSAL"),
            (original.identity, "record", b"SYNTHETIC_IDENTITY"),
            (original.match, "record", b"SYNTHETIC_MATCH"),
            (binding.claim, "service_job", (999, "changed", 999, "changed")),
            (binding.owner, "resources", list(binding.owner.resources)),
            (binding.owner, "local_end", binding.owner.local_end + 1),
            (original.fence, "last", original.fence.last - 1))
        for value, name, changed in changes:
            saved = getattr(value, name)
            with self.subTest(field=name):
                object.__setattr__(value, name, changed)
                try:
                    with self.assertRaisesRegex(I.AdmissionError, "HISTORY_CHANGED"):
                        N._recipient_claim(claim)
                finally:
                    object.__setattr__(value, name, saved)
        with patch.object(O, "parse", side_effect=AssertionError("history must not parse")), \
                patch.object(O.clocks, "observe", side_effect=AssertionError("history must not observe")):
            self.assertIs(N._recipient_claim(claim)[0], binding)

    def test_no_closed_preparation_or_readmission_observation_or_reopening(self):
        def protect(claim):
            binding, original = N._recipient_claim(claim)
            old_owners = (binding.owner, original.owner)
            open_ = S.Owner.open
            def open_new(owner, *args, **kwargs):
                self.assertFalse(any(owner is old for old in old_owners))
                return open_(owner, *args, **kwargs)
            self.stack.enter_context(patch.object(S.Owner, "open", open_new))
            for kind in (N._ReadmissionWindow, O.Fence):
                self.stack.enter_context(patch.object(kind, "now", side_effect=AssertionError("old fence was observed")))
                self.stack.enter_context(patch.object(kind, "__init__", side_effect=AssertionError("old fence was renewed")))
        self.after_claim(protect)
        result = self.worker()
        self.assertIs(N.check_recipient_validation_return(result), result)

    def test_third_acquisition_preserves_original_first_use_job_basis_and_proposal(self):
        acquire, expected = N.acquisition.acquire_bootstrap, []
        def checked(root, **kwargs):
            expected.append(kwargs["expected"])
            self.assertEqual(kwargs["first_use_at"], F.F.F.FIRST1)
            return acquire(root, **kwargs)
        def progress(_claim):
            self.fixture.service_date += 1
            self.fixture.bodies["jobs"]["jobs"][0]["steps"] = [{"name": "SYNTHETIC progress", "status": "in_progress"}]
        self.after_claim(progress)
        with patch.object(N.acquisition, "acquire_bootstrap", side_effect=checked):
            result = self.worker()
        self.assertEqual(len(expected), 3)
        self.assertIsNone(expected[0])
        binding, original = N._recipient_claim(self.recipient_claim)
        self.assertEqual([value.record for value in expected[1:]], [original.match_raw] * 2)
        authority = next(iter(N._AUTHORITY_RETURNS.values()))
        row = json.loads(authority[1])
        self.assertEqual(row["serviceTimeBasisSha256"], O.digest(original.service_time_raw))
        self.assertEqual(row["originalProposalSha256"], O.digest(original.proposal_raw))
        self.assertEqual(json.loads(result.raw)["window"]["firstUseAt"], F.F.F.FIRST1)
        self.assertEqual(binding.returned.proposal_raw, original.proposal_raw)

    def test_third_acquisition_rejects_changed_owner_authorization_comment(self):
        self.after_claim(lambda _: self.fixture.bodies["comment"].update(updated_at=F.F.F.utc(F.F.F.FIRST1)))
        self.refuse_worker("SERVICE_CHILD_FAILED")
        self.assertIn("COMMENT_EDITED", str(self.child_errors[-1]))

    def test_third_acquisition_rejects_removed_environment_approval(self):
        self.after_claim(lambda _: self.fixture.bodies.update(approvals=[]))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_third_acquisition_rejects_recreated_environment(self):
        self.after_claim(lambda _: self.fixture.bodies["environment"].update(id=999))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_third_acquisition_rejects_recreated_branch_policy(self):
        self.after_claim(lambda _: self.fixture.bodies["branches"]["branch_policies"][0].update(id=999))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_third_acquisition_rejects_live_main_ref_change(self):
        self.after_claim(lambda _: self.fixture.bodies["main"]["object"].update(sha="b" * 40))
        self.refuse_worker("SERVICE_CHILD_FAILED")

    def test_third_acquisition_rejects_changed_original_numeric_job(self):
        def change(_claim):
            job = self.fixture.bodies["jobs"]["jobs"][0]
            job.update(id=999, url=job["url"].rsplit("/", 1)[0] + "/999")
        self.after_claim(change)
        self.refuse_worker("AUTHORITY_JOB_OR_MATCH_CHANGED")
        self.assertFalse(self.child_errors)
        self.assertEqual(len(self.fixture.requests), 24)

    def test_third_acquisition_rejects_changed_original_numeric_runner(self):
        self.after_claim(lambda _: self.fixture.bodies["jobs"]["jobs"][0].update(runner_id=999))
        self.refuse_worker("AUTHORITY_JOB_OR_MATCH_CHANGED")

    def test_third_acquisition_rejects_changed_original_job_start(self):
        self.after_claim(lambda _: self.fixture.bodies["jobs"]["jobs"][0].update(started_at=F.F.F.utc(F.F.F.START + 1)))
        self.refuse_worker("AUTHORITY_JOB_OR_MATCH_CHANGED")

    def test_changed_source_fails_before_third_http_or_crypto(self):
        self.after_claim(lambda _: setattr(self.fixture.git, "clean_value", False))
        self.refuse_worker("SOURCE")
        self.assertEqual(len(self.fixture.requests), 16)
        self.assertEqual(len(self.scopes), 2)

    def test_changed_public_policy_fails_before_third_http_or_crypto(self):
        self.after_claim(lambda _: setattr(self.fixture.git, "policy_raw", b"SYNTHETIC_CHANGED_POLICY"))
        self.refuse_worker("POLICY_BLOB")
        self.assertEqual(len(self.fixture.requests), 16)

    def test_window_frames_clamp_to_original_fences_and_reject_modified_caps(self):
        window = self.window()
        frame = json.loads(window.raw)
        self.assertEqual([frame[name] - frame["firstNs"] for name in ("workEndNs", "finalEndNs", "readEndNs")],
                         [seconds * O.NS for seconds in (240, 285, 315)])
        for name in ("workEndNs", "finalEndNs", "readEndNs", "originalProposedJobEndNs"):
            changed = dict(frame)
            changed[name] = changed[name] + 1 if name != "originalProposedJobEndNs" else frame["firstNs"]
            with self.subTest(field=name), self.assertRaises(I.AdmissionError):
                N._recipient_frame(O.encoded(changed))
        shortened = dict(frame, originalProposedJobEndNs=frame["firstNs"] + 60 * O.NS)
        for name in ("workEndNs", "finalEndNs", "readEndNs"):
            shortened[name] = shortened["originalProposedJobEndNs"]
        self.assertEqual(N._recipient_frame(O.encoded(shortened))[-1], (shortened["originalProposedJobEndNs"],) * 3)
        authority = {"schema": 1, "scope": N.AUTHORITY_WINDOW_SCOPE, "recipientWindow": shortened,
                     "workEndNs": frame["firstNs"] + 15 * O.NS, "finalEndNs": shortened["workEndNs"]}
        self.assertEqual(N._authority_frame(O.encoded(authority))[-2:], (authority["workEndNs"], authority["finalEndNs"]))
        authority["workEndNs"] += 1
        with self.assertRaisesRegex(I.AdmissionError, "AUTHORITY_FRAME_FENCES"):
            N._authority_frame(O.encoded(authority))

    def test_window_work_equality_expires_without_renewing_original_start(self):
        window = self.window()
        first, work, raw = window.first, window.work, window.raw
        self.fixture.ns = work
        with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_WINDOW_EXPIRED"):
            window.now()
        self.assertEqual((window.first, window.work, window.raw), (first, work, raw))
        self.assertTrue(window.state().failed)
        with self.assertRaisesRegex(I.AdmissionError, "NOT_LIVE"):
            window.now()

    def test_window_final_failure_leaves_expired_once_only_sentinel(self):
        window = self.window()
        error = O.clocks.ClockError("SYNTHETIC_FINAL_FIRST_CLOCK_FAILURE")
        with patch.object(O.clocks, "observe", side_effect=error), self.assertRaises(O.clocks.ClockError) as caught:
            window.begin_final()
        self.assertIs(caught.exception, error)
        self.assertEqual(window.state().final_end, 0)
        with self.assertRaisesRegex(I.AdmissionError, "FINAL_REENTRY"):
            window.begin_final()
        with self.assertRaisesRegex(I.AdmissionError, "WINDOW_EXPIRED"):
            window.now(final=True)

    def test_window_final_is_actual_start45_clamped_to_original285(self):
        window = self.window()
        self.fixture.ns += 10 * O.NS
        window.begin_final()
        state = window.state()
        self.assertEqual(state.final_end, min(state.ends[1], state.final_start + 45 * O.NS))
        with self.assertRaisesRegex(I.AdmissionError, "FINAL_REENTRY"):
            window.begin_final()
        self.fixture.ns = state.final_end
        with self.assertRaisesRegex(I.AdmissionError, "WINDOW_EXPIRED"):
            window.now(final=True)

    def test_window_slow_local_clock_cannot_hide_behind_raw_time(self):
        window = self.window()
        values = iter((window.state().local_last, window.state().locals[0]))
        with patch.object(N.time, "monotonic", side_effect=lambda: next(values)), \
                self.assertRaisesRegex(I.AdmissionError, "WINDOW_EXPIRED"):
            window.now()
        self.assertGreaterEqual(window.state().local_last, window.state().locals[0])

    def test_window_backward_clock_refuses_and_retains_last_validated_highwater(self):
        window = self.window()
        old = window.last
        self.fixture.ns = old - 1001
        with patch.object(N.time, "monotonic", return_value=window.state().local_last), \
                self.assertRaises(O.clocks.ClockError):
            window.now()
        self.assertEqual(window.last, old)

    def test_window_backward_local_clock_refuses_before_new_raw_observation(self):
        window = self.window()
        old = window.last
        with patch.object(N.time, "monotonic", return_value=window.state().local_last - 1), \
                patch.object(O.clocks, "observe", side_effect=AssertionError("must reject LOCAL first")), \
                self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_LOCAL_CLOCK"):
            window.now()
        self.assertEqual(window.last, old)

    def test_http_phase_cannot_select_crypto_command_or_arbitrary_operation(self):
        for scope in (N.RECIPIENT_CONTEXT_SCOPE, "SYNTHETIC_CRYPTO", ""):
            with self.subTest(scope=scope), self.assertRaisesRegex(O.OriginError, "SERVICE_CONTEXT_SCOPE"):
                S.phase_command(O.encoded({"scope": scope}), 1)
        for scope, operation in ((S.CONTEXT_SCOPE, "_service"), (S.INITIAL_CONTEXT_SCOPE, "_service"),
            (S.INITIAL_ENTRY_CONTEXT_SCOPE, "_service-entry"), (S.INITIAL_AUTHORITY_CONTEXT_SCOPE, "_service-authority")):
            command = S.phase_command(O.encoded({"scope": scope}), 1)
            self.assertEqual(command[5], operation)
            self.assertEqual(command[-2:], ["--minimum-ns", "1"])

    def test_authority_work75_expiry_prevents_third_http_and_crypto(self):
        acquire = N._recipient_authority
        def late(window, token):
            self.fixture.ns = window.first + 75 * O.NS
            return acquire(window, token)
        with patch.object(N, "_recipient_authority", side_effect=late):
            self.refuse_worker("RECIPIENT_WINDOW_EXPIRED")
        self.assertEqual(len(self.fixture.requests), 16)

    def test_authority_close120_expiry_cannot_resume_outer_work(self):
        close, changed = S.Owner.close, []
        def late(owner):
            close(owner)
            if type(owner.fence) is N._RecipientAuthorityWindow and owner.fence.checked(cleanup=True).roster is not None:
                changed.append(owner)
                self.fixture.ns = owner.fence.final
        with patch.object(S.Owner, "close", late):
            self.refuse_worker("RECIPIENT_WINDOW_EXPIRED")
        self.assertEqual(len(changed), 1)
        self.assertFalse(N._AUTHORITY_RETURNS)
        self.assertEqual(len(self.fixture.requests), 24)

    def authority_close(self, change):
        close = S.Owner.close
        def after(owner):
            was_closed = owner.closed
            close(owner)
            if (type(owner.fence) is N._RecipientAuthorityWindow and not was_closed and
                    owner.fence.checked(cleanup=True).roster is not None):
                change(owner)
        return patch.object(S.Owner, "close", after)

    def test_authority_close_cannot_replace_original_phase_with_equal_copy(self):
        with self.authority_close(lambda owner: setattr(owner, "phase_originals", dataclasses.replace(owner.phase_originals))):
            self.refuse_worker("AUTHORITY_ORIGINAL_RETURN_CHANGED")
        self.assertFalse(N._AUTHORITY_RETURNS)

    def test_authority_close_cannot_replace_source_alias_in_original_registry(self):
        def changed(owner):
            key = next(key for key in owner.initial_sources if key.endswith("source-after"))
            owner.initial_sources[key] = dataclasses.replace(owner.initial_sources[key])
        with self.authority_close(changed):
            self.refuse_worker("RECIPIENT_HISTORY_CHANGED")
        self.assertFalse(N._AUTHORITY_RETURNS)

    def test_work240_expiry_before_crypto_does_not_reissue_recipient_episode(self):
        native = N._recipient_native
        def late(owner, private, context, window, authority):
            self.fixture.ns = window.work
            return native(owner, private, context, window, authority)
        with patch.object(N, "_recipient_native", side_effect=late):
            self.refuse_worker("RECIPIENT_WINDOW_EXPIRED")
        self.assertEqual(len(N._RECIPIENT_WINDOWS), 1)
        self.assertEqual(len(N._AUTHORITY_RETURNS), 1)

    def bad_supplier(self, name, value, reason="KEY_OR_POLICY_CHANGED"):
        self.supplier_change = lambda recipient: dataclasses.replace(recipient, **{name: value})
        self.refuse_worker("RECIPIENT_CHILD_FAILED", crypto=True)
        self.assertEqual(len(self.supplier_calls), 1)
        self.assertIn(reason, str(self.child_errors[-1]))

    def test_supplier_wrong_type_cannot_be_reconstructed_as_recipient(self):
        self.supplier_change = lambda recipient: SimpleNamespace(**vars(recipient))
        self.refuse_worker("RECIPIENT_CHILD_FAILED", crypto=True)
        self.assertIn("RECIPIENT_SUPPLIER_TYPE", str(self.child_errors[-1]))

    def test_supplier_wrong_primary_fingerprint_refuses(self):
        self.bad_supplier("fingerprint", "F" * 40)

    def test_supplier_wrong_exact_key_hash_refuses(self):
        self.bad_supplier("key_sha256", "f" * 64)

    def test_supplier_unusable_encryption_fingerprint_refuses(self):
        self.bad_supplier("encryption_fingerprint", "not-an-encryption-key")

    def test_supplier_expiry_before_policy_end_refuses(self):
        self.bad_supplier("expires_at", 1)

    def test_supplier_foreign_work_identity_refuses(self):
        self.bad_supplier("work_identity", (999, 999))

    def test_supplier_object_is_pinned_before_fallible_post_return_clock(self):
        changed = []
        def observe():
            reading = self.fixture.observe()
            if self.suppliers and not changed:
                changed.append(self.suppliers[0])
                object.__setattr__(self.suppliers[0], "executable", Path("/SYNTHETIC_CHANGED_EXECUTABLE"))
            return reading
        with patch.object(O.clocks, "observe", side_effect=observe):
            self.refuse_worker("RECIPIENT_CHILD_FAILED", crypto=True)
        self.assertEqual(len(changed), 1)
        self.assertIn("RECIPIENT_POST_SUPPLIER_CHANGED", str(self.child_errors[-1]))

    def test_failed_supplier_unknown_never_becomes_known_outer_close(self):
        def unknown(recipient):
            S.diagnostics._QUARANTINE.append(object())  # Explicit synthetic unknown domain, not a native handle.
            return recipient
        self.supplier_change = unknown
        self.refuse_worker("RECIPIENT_PRIOR_UNKNOWN", crypto=True)
        self.assertFalse(N._RECIPIENT_NATIVE_RETURNS)
        self.assertTrue(S.QUARANTINE)

    def test_nonzero_crypto_child_cannot_adopt_even_an_original_success_ack(self):
        self.before_recipient = lambda: setattr(self, "child_exit", 125)
        self.refuse_worker("RECIPIENT_CHILD_FAILED", crypto=True)
        self.assertFalse(N._RECIPIENT_NATIVE_RETURNS)
        self.assertTrue(next(iter(N._RECIPIENT_WINDOWS.values())).roster.owner.unknown)
        self.assertTrue(S.QUARANTINE)

    def test_crypto_descendants_prevent_success_and_have_one_drain_close(self):
        self.before_recipient = lambda: setattr(self, "crypto_descendants", [{"pid": 999, "startTicks": 1}])
        self.refuse_worker("RECIPIENT_LEFT_DESCENDANTS", crypto=True)
        self.assertEqual(self.scopes[-1].close_calls, 1)
        self.assertEqual(len(self.drains), 4)

    def test_crypto_native_birth_must_match_actual_child(self):
        def changed(row):
            row["startedIdentities"][0]["pid"] = 999
            return row
        self.before_recipient = lambda: setattr(self, "native_change", changed)
        self.refuse_worker("RECIPIENT_NATIVE_BIRTH", crypto=True)

    def test_crypto_leader_must_not_preexist_in_original_native_baseline(self):
        make = self.make_scope
        def scope(job, invocation, state, home):
            value = make(job, invocation, state, home)
            if Path(state).name.endswith("-recipient"):
                value.baseline = {(1234, 5678)}
            return value
        with patch.object(S.processes, "make_scope", side_effect=scope):
            self.refuse_worker("RECIPIENT_NATIVE_PREEXISTING_LEADER", crypto=True)

    def test_crypto_native_argv_cannot_change_after_launch(self):
        def changed(row):
            row = json.loads(json.dumps(row))
            row["launches"][0]["requestedArgv"][-1] = "1"
            return row
        self.before_recipient = lambda: setattr(self, "native_change", changed)
        self.refuse_worker("NATIVE_ORIGINAL_LIFETIME", crypto=True)

    def test_crypto_drain_expiry_is_unknown_and_never_reads_capture(self):
        def expire():
            self.fixture.ns = next(iter(N._RECIPIENT_WINDOWS.values())).final_end
        self.after_crypto_drain = expire
        reads, read = [], S.Owner.read
        def checked(owner, directory, name, *args, **kwargs):
            if type(owner.fence) is N._RecipientUseWindow and name in ("stdout.log", "stderr.log"):
                reads.append(name)
            return read(owner, directory, name, *args, **kwargs)
        with patch.object(S.Owner, "read", checked):
            self.refuse_worker("RECIPIENT_WINDOW_EXPIRED", crypto=True)
        self.assertEqual(reads, [])
        self.assertTrue(S.QUARANTINE)
        self.assertEqual(self.scopes[-1].close_calls, 1)

    def test_crypto_scope_close_failure_keeps_pins_without_capture_adoption(self):
        self.before_recipient = lambda: setattr(self, "scope_close_error", RuntimeError("SYNTHETIC_SCOPE_CLOSE_UNKNOWN"))
        self.refuse_worker("SYNTHETIC_SCOPE_CLOSE_UNKNOWN", crypto=True)
        self.assertTrue(S.QUARANTINE)
        self.assertEqual(self.scopes[-1].close_calls, 1)
        self.assertFalse(N._RECIPIENT_NATIVE_RETURNS)

    def test_capture_sync_failure_prevents_readback_and_preserves_original_error(self):
        primary = RuntimeError("SYNTHETIC_CAPTURE_SYNC_FAILURE")
        def fail():
            state = next(iter(N._RECIPIENT_WINDOWS.values()))
            resource = next(value for _row, label, value, _a, _c in state.roster.seen if label == "stdout")
            self.stack.enter_context(patch.object(resource, "sync", side_effect=primary))
        self.after_crypto_drain = fail
        with self.assertRaises(RuntimeError) as caught:
            self.worker()
        self.assertIs(caught.exception, primary)
        self.assertFalse(N._RECIPIENT_NATIVE_RETURNS)
        self.assertFalse(N._RECIPIENT_RETURNS)

    def test_post_retirement_read30_expiry_prevents_final_source_acquisition(self):
        query = N.source_queries
        attempted = []
        def expire(owner, window, context, path):
            if type(window) is N._RecipientUseWindow:
                attempted.append(path)
                self.assertEqual(window.state().phase, "READ")
                self.fixture.ns = window.state().read_end
            return query(owner, window, context, path)
        with patch.object(N, "source_queries", side_effect=expire):
            self.refuse_worker("RECIPIENT_WINDOW_EXPIRED", crypto=True)
        self.assertEqual(len(attempted), 1)
        self.assertEqual(len(self.queries), 11)

    def parent_close(self, change):
        close = S.Owner.close
        def after(owner):
            was_closed = owner.closed
            close(owner)
            if type(owner.fence) is N._RecipientUseWindow and not was_closed:
                change(owner)
        return patch.object(S.Owner, "close", after)

    def test_parent_close_cannot_replace_native_original_return(self):
        with self.parent_close(lambda owner: setattr(owner, "phase_originals", dataclasses.replace(owner.phase_originals))):
            self.refuse_worker("RECIPIENT_FINAL_ORIGINALS_CHANGED", crypto=True)

    def test_parent_close_cannot_mutate_final_source_bytes(self):
        def changed(owner):
            source = next(iter(owner.initial_sources.values()))
            object.__setattr__(source, "raw", b"SYNTHETIC_FINAL_SOURCE")
        with self.parent_close(changed):
            self.refuse_worker("RECIPIENT_HISTORY_CHANGED", crypto=True)

    def test_parent_close_cannot_replace_source_alias_with_equal_return(self):
        def changed(owner):
            key = next(iter(owner.initial_sources))
            owner.initial_sources[key] = dataclasses.replace(owner.initial_sources[key])
        with self.parent_close(changed):
            self.refuse_worker("RECIPIENT_HISTORY_CHANGED", crypto=True)

    def test_pending_writer_cannot_mutate_native_or_final_source_originals(self):
        write = S.Owner.write
        changed = []
        def mutation(owner, directory, name, *args, **kwargs):
            raw = write(owner, directory, name, *args, **kwargs)
            if name == "recipient-pending.json":
                changed.append(owner)
                object.__setattr__(owner.phase_originals, "child", b"SYNTHETIC_CHANGED_CHILD_RETURN")
                object.__setattr__(next(iter(owner.initial_sources.values())), "raw", b"SYNTHETIC_CHANGED_SOURCE_RETURN")
            return raw
        with patch.object(S.Owner, "write", mutation):
            self.refuse_worker("RECIPIENT_HISTORY_CHANGED", crypto=True)
        self.assertEqual(len(changed), 1)

    def test_parent_close_cannot_extend_original_local_deadline(self):
        with self.parent_close(lambda owner: setattr(owner, "local_end", owner.local_end + 1)):
            self.refuse_worker("RECIPIENT_OWNER_CHANGED", crypto=True)

    def test_policy_expiry_during_parent_close_prevents_final_return(self):
        def expired(_owner):
            self.stack.enter_context(patch.object(N.time, "time", return_value=F.F.F.END))
        with self.parent_close(expired):
            self.refuse_worker("RECIPIENT_POLICY_VALIDITY", crypto=True)

    def test_manual_handler_restoration_failure_cannot_emit_success(self):
        restored = []
        def signal(number, handler):
            if handler is None and N._RECIPIENT_NATIVE_RETURNS:
                restored.append(number)
                raise RuntimeError("SYNTHETIC_HANDLER_RESTORE_FAILURE")
        with patch.object(S.signal, "signal", side_effect=signal):
            self.refuse_worker("SYNTHETIC_HANDLER_RESTORE_FAILURE", crypto=True)
        self.assertTrue(restored)

    def test_actual_directory_return_is_retained_before_postallocation_clock_failure(self):
        primary = O.wire.BudgetError("SYNTHETIC_POSTALLOCATION_CLOCK_FAILURE")
        new, returned, pending = Q._new_private_directory, [], []
        def directory(path):
            value = new(path)
            if path.name.endswith("-recipient"):
                returned.append(value)
                pending.append(True)
            return value
        def local():
            if pending:
                pending.clear()
                raise primary
            return self.fixture.ns / O.NS
        with patch.object(Q, "_new_private_directory", side_effect=directory), \
                patch.object(N.time, "monotonic", side_effect=local), self.assertRaises(O.wire.BudgetError) as caught:
            self.worker()
        self.assertIs(caught.exception, primary)
        self.assertEqual(len(returned), 1)
        state = next(iter(N._RECIPIENT_WINDOWS.values()))
        self.assertTrue(any(resource is returned[0] and row["closed"] for row, _label, resource, _a, _c in state.roster.seen))
        self.assertEqual(self.supplier_calls, [])
        self.assertFalse(N._RECIPIENT_RETURNS)
        self.assertFalse(S.QUARANTINE)

    def test_actual_unlaunched_scope_return_retires_without_invented_preparer_observation(self):
        primary = O.wire.BudgetError("SYNTHETIC_SCOPE_POSTALLOCATION_CLOCK_FAILURE")
        make, returned, pending = self.make_scope, [], []
        def scope(job, invocation, state, home):
            value = make(job, invocation, state, home)
            if Path(state).name.endswith("-recipient"):
                returned.append(value)
                pending.append(True)
            return value
        def local():
            if pending:
                pending.clear()
                raise primary
            return self.fixture.ns / O.NS
        with patch.object(S.processes, "make_scope", side_effect=scope), \
                patch.object(N.time, "monotonic", side_effect=local), self.assertRaises(O.wire.BudgetError) as caught:
            self.worker()
        self.assertIs(caught.exception, primary)
        self.assertEqual(len(returned), 1)
        self.assertEqual(returned[0].launches, [])
        self.assertEqual(returned[0].close_calls, 1)
        state = next(iter(N._RECIPIENT_WINDOWS.values()))
        self.assertTrue(any(resource is returned[0] and row["closed"] for row, _label, resource, _a, _c in state.roster.seen))
        self.assertFalse(state.roster.owner.unknown)
        self.assertFalse(S.QUARANTINE)
        self.assertEqual(self.supplier_calls, [])

    def test_failed_first_recipient_clock_keeps_claim_consumed_and_stack_token_cleared(self):
        primary = O.clocks.ClockError("SYNTHETIC_FIRST_RECIPIENT_CLOCK_FAILURE")
        self.after_claim(lambda _: self.stack.enter_context(patch.object(O.clocks, "observe", side_effect=primary)))
        checked = {}
        try:
            self.worker()
        except O.clocks.ClockError as error:
            self.assertIs(error, primary)
            # Inspect only this synthetic token reference while its traceback
            # is live; unittest.assertRaises deliberately clears traceback.
            trace = error.__traceback__
            while trace is not None:
                if trace.tb_frame.f_code.co_name == "_prepare_and_validate_recipient":
                    checked[id(trace.tb_frame)] = trace.tb_frame.f_locals.get("token")
                trace = trace.tb_next
        else:
            self.fail("the original first-recipient clock failure was not raised")
        self.assertEqual(list(checked.values()), [None])
        self.assertFalse(N._RECIPIENT_WINDOWS)
        with self.assertRaisesRegex(I.AdmissionError, "ALREADY_CLAIMED"):
            N._claim_recipient(self.recipient_claim.original)
        self.assertEqual(len(self.fixture.requests), 16)
        self.assertNotIn(O.wire.TOKEN_ENV, os.environ)

    def test_late_synchronous_supplier_return_cannot_extend_outer_work_or_hide_unknown(self):
        def late(recipient):
            self.fixture.ns = next(iter(N._RECIPIENT_WINDOWS.values())).ends[0]
            return recipient
        self.supplier_change = late
        self.refuse_worker("RECIPIENT_WINDOW_EXPIRED", crypto=True)
        state = next(iter(N._RECIPIENT_WINDOWS.values()))
        self.assertTrue(state.roster.owner.unknown)
        self.assertTrue(S.QUARANTINE)
        self.assertEqual(len(self.supplier_calls), 1)
        self.assertEqual(state.ends[0], state.first + 240 * O.NS)

    def test_final_raw_observation_cannot_mutate_native_return_after_owner_close(self):
        closed, changed = [], []
        def observe():
            reading = self.fixture.observe()
            if closed and not changed:
                changed.append(closed[0])
                object.__setattr__(closed[0].phase_originals, "context", b"SYNTHETIC_POSTCLOSE_RAW_MUTATION")
            return reading
        with self.parent_close(closed.append), patch.object(O.clocks, "observe", side_effect=observe):
            self.refuse_worker("RECIPIENT_HISTORY_CHANGED", crypto=True)
        self.assertEqual(len(changed), 1)

    def test_final_cancellation_cannot_register_success_after_actual_owner_close(self):
        closed = []
        cancellation = S.cancellation
        def cancel(values):
            cancellation(values)
            if closed and not self.cancelled:
                self.cancelled.append("SYNTHETIC_FINAL_CANCELLATION")
        with self.parent_close(closed.append), patch.object(S, "cancellation", side_effect=cancel), \
                self.assertRaises(KeyboardInterrupt):
            self.worker()
        self.assertFalse(N._RECIPIENT_RETURNS)
        self.assertEqual(len(closed), 1)

    def test_closed_validation_checker_is_historical_no_clock_io_or_remote_authority(self):
        result = self.worker()
        denied = AssertionError("historical result must not observe, acquire or validate live policy")
        with patch.object(O.clocks, "observe", side_effect=denied), patch.object(N.time, "monotonic", side_effect=denied), \
                patch.object(N.time, "time", side_effect=denied), patch.object(S.Owner, "open", side_effect=denied), \
                patch.object(N.acquisition, "acquire_bootstrap", side_effect=denied), patch.object(O, "parse", side_effect=denied):
            self.assertIs(N.check_recipient_validation_return(result), result)
            with self.assertRaisesRegex(I.AdmissionError, "NOT_ORIGINAL_RECIPIENT_VALIDATION_RETURN"):
                N.check_recipient_validation_return(dataclasses.replace(result))
        with self.assertRaises(O.OriginError):
            O.admitted_value(result)
        state = next(iter(N._RECIPIENT_WINDOWS.values()))
        with self.assertRaisesRegex(I.AdmissionError, "NOT_LIVE"):
            state.window.now(final=True)


if __name__ == "__main__":
    unittest.main()
