#!/usr/bin/env python3
"""Offline original handoff/adoption controls, not genuine Actions execution.

Native process/query/clock/HTTP boundaries are explicit models. Only tiny POSIX
private files and regular-file capture descriptors run under an ordinary UID.
No application, native process provider, network, key, cache or SDK operation.
"""
from __future__ import annotations

from contextlib import contextmanager
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
import importlib.util

spec = importlib.util.spec_from_file_location("bootstrap_handoff_original_models",
    Path(__file__).with_name("hosted-cache-bootstrap-origin-test.py"))
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
S, O = M.S, M.O


class HandoffModels(M.ControllerTests):
    def prepare_handoff(self):
        output = io.BytesIO()
        with patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)):
            S.guarded(S.prepare_originals)
        raw = output.getvalue()
        path = self.admissions[0].parent
        return path, raw, O.parse(raw), O.parse((path / "origin-result.json").read_bytes())

    def test_prepare_ack_is_distinct_from_the_provisional_parent_receipt(self):
        path, raw, ack, result = self.prepare_handoff()
        handoff_raw = (path / "prepare-handoff.json").read_bytes()
        handoff = O.parse(handoff_raw)
        self.assertEqual(ack["scope"], "BOOTSTRAP_PREPARE_HANDOFF_PENDING_STEP_RETURN_V1")
        self.assertEqual(handoff["scope"], "BOOTSTRAP_PREPARE_POST_CLOSE_HANDOFF_V1")
        self.assertEqual(result["scope"], "BOOTSTRAP_ORIGINALS_PENDING_CALLER_RETURN_V2")
        self.assertEqual(ack["handoffSha256"], O.digest(handoff_raw))
        self.assertEqual(handoff["originSha256"], O.digest((path / "origin-result.json").read_bytes()))
        self.assertEqual(handoff["contextSha256"], O.digest((path / "context.json").read_bytes()))
        self.assertEqual(raw, O.encoded(ack))
        self.assertIs(ack["exportSaveAuthority"], False)
        self.assertEqual(ack["budgetAcceptance"], "NOT_ADMITTED")

    def test_prepare_binds_original_native_directory_identities(self):
        path, _, _, result = self.prepare_handoff()
        self.assertIsInstance(result.get("directories"), dict)
        self.assertEqual(set(result["directories"]), {"admission", "control-home", "final-admission", "service", "temporary"})
        self.assertEqual(result["sessionIdentity"], [path.stat().st_dev, path.stat().st_ino])
        for name, identity in result["directories"].items():
            self.assertEqual(identity, [(path / name).stat().st_dev, (path / name).stat().st_ino])

    def test_prepare_binds_native_lifetime_not_pid_alone(self):
        path, _, _, result = self.prepare_handoff()
        self.assertIsInstance(result.get("processIdentity"), dict)
        self.assertEqual(result["processIdentity"], {"pid": os.getpid(), "startTicks": 9012})
        phase = O.parse((path / "service/result.json").read_bytes())
        birth = O.parse((path / "service/native-start.json").read_bytes())
        self.assertEqual(result["processIdentity"], phase["preparerIdentity"])
        self.assertEqual(result["processIdentity"], birth["preparerIdentity"])
        self.assertEqual(result["processIdentity"], O.parse((path / "prepare-handoff.json").read_bytes())["processIdentity"])

    def test_prepare_ack_retains_a_real_post_close_predecessor_floor(self):
        observed, original = [], S.Owner.close
        def close(owner):
            original(owner)
            if owner.phase_originals is not None:
                observed.append(self.nanoseconds)
        with patch.object(S.Owner, "close", close):
            path, _, _, result = self.prepare_handoff()
        handoff = O.parse((path / "prepare-handoff.json").read_bytes())
        self.assertEqual(len(observed), 1)
        self.assertLessEqual(result["retainedNs"], observed[0])
        self.assertLessEqual(observed[0], handoff["closedNs"])
        self.assertLessEqual(handoff["closedNs"], handoff["recordedNs"])
        self.assertLessEqual(handoff["recordedNs"], self.nanoseconds)
        self.assertEqual(handoff["clock"], O.clock_value(self.clock))
        self.assertLess(handoff["recordedNs"], 1120 * O.NS)

    def test_public_prepare_output_contains_only_hash_and_closed_non_authority_fields(self):
        path, raw, ack, _ = self.prepare_handoff()
        self.assertEqual(set(ack), {"scope", "handoffSha256", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"})
        self.assertEqual(ack["testAcceptance"], "NOT_PERFORMED")
        for private in (str(path), M.TOKEN, M.RUNNER, "processIdentity", "startTicks", "clock", "closedNs", "recordedNs"):
            self.assertNotIn(private.encode(), raw)

    def capture_prepare_failure(self):
        output = io.BytesIO()
        with patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)), self.assertRaises(BaseException) as caught:
            S.guarded(S.prepare_originals)
        self.assertEqual(output.getvalue(), b"")
        return self.admissions[0].parent, caught.exception

    def test_failed_original_owner_close_prevents_handoff_even_with_parent_receipt(self):
        original, failure = S.Owner.close, OSError("SYNTHETIC_PREPARE_CLOSE")
        def close(owner):
            original(owner)
            if owner.phase_originals is not None:
                raise failure
        with patch.object(S.Owner, "close", close):
            path, error = self.capture_prepare_failure()
        self.assertIs(error, failure)
        self.assertTrue((path / "origin-result.json").is_file())
        self.assertFalse((path / "prepare-handoff.json").exists())

    def test_late_original_close_cannot_use_a_new_handoff_allowance(self):
        original = S.Owner.close
        def close(owner):
            original(owner)
            if owner.phase_originals is not None:
                self.nanoseconds = owner.fence.final
        with patch.object(S.Owner, "close", close):
            path, error = self.capture_prepare_failure()
        self.assertIsInstance(error, O.OriginError)
        self.assertFalse((path / "prepare-handoff.json").exists())

    def test_handoff_writer_close_failure_keeps_its_bytes_provisional(self):
        original, failure = S.Owner.close, OSError("SYNTHETIC_HANDOFF_CLOSE")
        def close(owner):
            original(owner)
            if owner.first is None and owner.phase_originals is None:
                raise failure
        with patch.object(S.Owner, "close", close):
            path, error = self.capture_prepare_failure()
        self.assertIs(error, failure)
        self.assertTrue((path / "prepare-handoff.json").is_file())

    def test_handoff_local_45_fence_is_not_the_remaining_120_second_prelude(self):
        original = S.Owner.close
        def close(owner):
            if owner.first is None and owner.phase_originals is None:
                self.nanoseconds = int(owner.local_end * O.NS) + 1
                self.assertLess(self.nanoseconds, owner.fence.final)
            original(owner)
        with patch.object(S.Owner, "close", close):
            path, error = self.capture_prepare_failure()
        self.assertIsInstance(error, S.posix.EvidenceError)
        self.assertTrue((path / "prepare-handoff.json").is_file())

    def test_handoff_write_is_exclusive_and_never_overwrites_a_prior_file(self):
        original, retained = S.prepare_handoff, b"SYNTHETIC_EXISTING_HANDOFF"
        def handoff(path, *args):
            target = path / "prepare-handoff.json"
            target.write_bytes(retained)
            target.chmod(0o600)
            return original(path, *args)
        with patch.object(S, "prepare_handoff", side_effect=handoff):
            path, error = self.capture_prepare_failure()
        self.assertIsInstance(error, FileExistsError)
        self.assertEqual((path / "prepare-handoff.json").read_bytes(), retained)

    def test_public_flush_failure_is_not_hidden_by_a_complete_private_handoff(self):
        output, failure = io.BytesIO(), OSError("SYNTHETIC_PUBLIC_FLUSH")
        def flush(): raise failure
        stream = SimpleNamespace(write=output.write, flush=flush)
        with patch.object(S.sys, "stdout", SimpleNamespace(buffer=stream)), self.assertRaises(OSError) as caught:
            S.guarded(S.prepare_originals)
        self.assertIs(caught.exception, failure)
        self.assertEqual(O.parse(output.getvalue())["scope"], S.HANDOFF_OUTPUT_SCOPE)
        self.assertTrue((self.admissions[0].parent / "prepare-handoff.json").is_file())

    def test_preparer_lifetimes_have_closed_native_shapes_and_typed_values(self):
        values = {"linux-x64": {"pid": 91, "startTicks": 123},
            "windows-x64": {"pid": 91, "creationFileTime": 123},
            "macos-arm64": {"pid": 91, "uniqueId": 12, "startSeconds": 13, "startMicroseconds": 0, "pidVersion": 0}}
        values["macos-x64"] = dict(values["macos-arm64"])
        for role, valid in values.items():
            self.assertEqual(S.closed_lifetime(valid, role), valid)
            cases = [{**valid, "extra": 1}, {"pid": 91}, {**valid, "pid": True}, {**valid, "pid": 0}]
            cases.extend({**valid, name: True} for name in valid)
            if role.startswith("macos-"):
                cases.append({**valid, "startMicroseconds": 1_000_000})
            for changed in cases:
                with self.subTest(role=role, changed=changed), self.assertRaises(O.OriginError):
                    S.closed_lifetime(changed, role)

    def test_preparer_reader_uses_existing_scope_and_nonowning_windows_pseudo_handle(self):
        calls = []
        def windows(handle, pid):
            calls.append((handle.value, pid))
            return {"pid": pid, "creationFileTime": 99}
        scope = SimpleNamespace(name=S.BACKENDS["windows-x64"], api=SimpleNamespace(identity=windows))
        self.assertEqual(S.preparer_identity(scope, "windows-x64"), {"pid": os.getpid(), "creationFileTime": 99})
        self.assertEqual(calls, [(S.processes.PTR(-1).value, os.getpid())])
        def darwin(pid, *, required):
            self.assertIs(required, True)
            return {"pid": pid, "uniqueId": 1, "startSeconds": 1, "startMicroseconds": 0, "pidVersion": 0, "live": True}
        scope = SimpleNamespace(name=S.BACKENDS["macos-arm64"], _identity=darwin)
        self.assertEqual(S.preparer_identity(scope, "macos-arm64")["pidVersion"], 0)
        with self.assertRaises(O.OriginError):
            S.preparer_identity(scope, "linux-x64")

    def test_preparer_identity_change_at_native_drain_cannot_publish_handoff(self):
        original, calls = S.preparer_identity, []
        def identity(scope, role):
            result = original(scope, role)
            calls.append(result)
            return result if len(calls) == 1 else {**result, "startTicks": result["startTicks"] + 1}
        with patch.object(S, "preparer_identity", side_effect=identity):
            path, _ = self.capture_prepare_failure()
        self.assertEqual(len(calls), 2)
        self.assertFalse((path / "prepare-handoff.json").exists())
        self.assertTrue(S.QUARANTINE)

    @contextmanager
    def adopter(self, ack, *, outcome="success", same_pid=False):
        # Explicit MODEL of a distinct process, never a native/admitted caller.
        env = {S.PREPARE_OUTCOME_ENV: outcome, S.PREPARE_HASH_ENV: ack["handoffSha256"]}
        with patch.dict(os.environ, env), patch.object(S.os, "getpid", return_value=os.getpid() + (0 if same_pid else 1)):
            yield

    def public_adoption(self):
        output = io.BytesIO()
        with patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)):
            S.guarded(S.adopt_originals)
        return output.getvalue(), O.parse(output.getvalue())

    def test_read_only_adoption_rebinds_originals_and_actual_admission_without_a_second_get(self):
        path, _, ack, _ = self.prepare_handoff()
        files = {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
        original, seen = self.fake_admit, []
        def admit(owner, fence, directory, *, expected):
            self.assertIsNone(owner.phase_originals)
            self.assertEqual(owner.admissions, {})
            self.assertEqual(expected, self.admitted)
            self.assertEqual(owner.work_limit, fence.work)
            self.assertEqual(owner.final_limit, fence.final)
            self.assertLessEqual(owner.local_end, fence.work / O.NS)
            seen.append(fence.raw)
            return original(owner, fence, directory, expected=expected)
        with self.adopter(ack), patch.object(S, "admit", side_effect=admit):
            raw, result = self.public_adoption()
        self.assertEqual(result["scope"], "BOOTSTRAP_READ_ONLY_ADOPTION_PENDING_RETURN_V1")
        self.assertEqual(set(result), {"scope", "adoptionSha256", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"})
        self.assertEqual(result["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(result["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(result["exportSaveAuthority"], False)
        target = path.with_name(path.name + "-adoption")
        receipt_raw = (target / "adoption-result.json").read_bytes()
        receipt = O.parse(receipt_raw)
        self.assertEqual(O.digest(receipt_raw), result["adoptionSha256"])
        self.assertEqual(receipt["originals"]["handoffSha256"], ack["handoffSha256"])
        self.assertEqual(receipt["retirement"], "PENDING_OWNER_CLOSE")
        self.assertEqual(seen, [(path / "prelude.json").read_bytes()])
        self.assertLessEqual(receipt["beganNs"], receipt["metadataLastNs"])
        self.assertLessEqual(receipt["metadataLastNs"], receipt["readmissionReturnedNs"])
        self.assertLessEqual(receipt["readmissionReturnedNs"], receipt["retainedNs"])
        self.assertLess(receipt["retainedNs"], receipt["prelude"]["workEndNs"])
        self.assertEqual(files, {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()})
        self.assertEqual((len(self.requests), len(self.scopes), len(self.admissions)), (2, 1, 3))
        self.assertNotIn(str(path).encode(), raw)
        self.assertNotIn(b"clock", raw)

    def test_only_literal_original_success_allows_even_read_only_adoption(self):
        _, _, ack, _ = self.prepare_handoff()
        for outcome in ("failure", "cancelled", "skipped", "neutral", "timed_out", "", "SUCCESS", "true"):
            with self.subTest(outcome=outcome), self.adopter(ack, outcome=outcome), self.assertRaisesRegex(
                    O.OriginError, "PREPARE_ORIGINAL_OUTCOME"):
                S.adopt_originals([])
        with self.adopter(ack):
            del os.environ[S.PREPARE_OUTCOME_ENV]
            os.environ["P2PKIT_BOOTSTRAP_PREPARE_CONCLUSION"] = "success"
            with self.assertRaisesRegex(O.OriginError, "PREPARE_ORIGINAL_OUTCOME"):
                S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_parent_receipt_or_changed_hash_cannot_replace_original_handoff_hash(self):
        path, _, ack, _ = self.prepare_handoff()
        for value in (O.digest((path / "origin-result.json").read_bytes()), "f" * 64, "", "A" * 64, "a" * 64 + "\n"):
            with self.subTest(hash=value), self.adopter({**ack, "handoffSha256": value}), self.assertRaisesRegex(
                    O.OriginError, "PREPARE_ORIGINAL_HASH"):
                S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_actions_read_token_is_forbidden_even_if_it_is_empty(self):
        _, _, ack, _ = self.prepare_handoff()
        for token in ("", M.TOKEN):
            with self.adopter(ack), patch.dict(os.environ, {O.wire.TOKEN_ENV: token}), self.assertRaisesRegex(
                    O.OriginError, "ADOPTION_TOKEN_FORBIDDEN"):
                S.adopt_originals([])
        self.assertEqual(len(self.requests), 2)

    def test_same_pid_is_conservatively_refused_not_promoted_to_liveness_proof(self):
        _, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack, same_pid=True), self.assertRaisesRegex(O.OriginError, "ADOPTER_SAME_PROCESS"):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_first_adopter_read_before_handoff_cannot_be_rehabilitated_by_later_clocks(self):
        path, _, ack, _ = self.prepare_handoff()
        handoff = O.parse((path / "prepare-handoff.json").read_bytes())
        original, first = self.observe, []
        def observe():
            if not first:
                first.append(True)
                return O.clocks.Reading(self.clock, handoff["recordedNs"] - 1)
            return original()
        with self.adopter(ack), patch.object(O.clocks, "observe", side_effect=observe), self.assertRaisesRegex(
                O.OriginError, "ADOPTER_PRECEDES_HANDOFF"):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_metadata_highwater_cannot_be_discarded_at_frame_binding(self):
        _, _, ack, _ = self.prepare_handoff()
        original = S.Owner.bind
        def bind(owner, *args, **kwargs):
            self.assertGreater(owner.early_last, owner.first.nanoseconds)
            self.nanoseconds = owner.early_last - 2000
            return original(owner, *args, **kwargs)
        with self.adopter(ack), patch.object(S.Owner, "bind", bind), self.assertRaises(O.clocks.ClockError):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_loading_frame_cannot_renew_initial_metadata_45_second_fence(self):
        _, _, ack, _ = self.prepare_handoff()
        original = S.Owner.read
        def read(owner, directory, name, *args, **kwargs):
            raw = original(owner, directory, name, *args, **kwargs)
            if name == "context.json" and owner.first is not None:
                self.nanoseconds += 45 * O.NS
            return raw
        with self.adopter(ack), patch.object(S.Owner, "read", read), self.assertRaises(S.posix.EvidenceError):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_original_75_second_work_cutoff_is_not_the_120_second_finalizer(self):
        path, _, ack, _ = self.prepare_handoff()
        frame = O.parse((path / "prelude.json").read_bytes())
        self.nanoseconds = frame["workEndNs"]
        self.assertLess(self.nanoseconds, frame["finalEndNs"])
        with self.adopter(ack), self.assertRaises(O.OriginError):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)
        self.assertFalse(path.with_name(path.name + "-adoption").exists())

    def test_same_path_and_bytes_do_not_substitute_for_original_root_identity(self):
        path, _, ack, _ = self.prepare_handoff()
        preserved = path.with_name(path.name + "-synthetic-original")
        path.rename(preserved)
        shutil.copytree(preserved, path)
        with self.adopter(ack), self.assertRaisesRegex(O.OriginError, "ADOPTION_DIRECTORIES_CHANGED"):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_every_original_child_directory_identity_is_required(self):
        path, _, ack, _ = self.prepare_handoff()
        for name in S.DIRECTORIES:
            target, saved = path / name, path.parent / ("synthetic-original-" + name)
            target.rename(saved)
            shutil.copytree(saved, target)
            try:
                with self.subTest(directory=name), self.adopter(ack), self.assertRaisesRegex(
                        O.OriginError, "ADOPTION_DIRECTORIES_CHANGED"):
                    S.adopt_originals([])
            finally:
                shutil.rmtree(target)
                saved.rename(target)
        self.assertEqual(len(self.admissions), 2)

    def test_admission_baseline_child_native_http_and_final_originals_are_all_hash_bound(self):
        path, _, ack, _ = self.prepare_handoff()
        names = ("prelude.json", "context.json", "admission-return.json", "final-admission-return.json",
            "admission/admission.json", "admission/original-event.json", "admission/original-policy.json",
            "admission/recipient-public.asc", "admission/session-result.json", "final-admission/admission.json",
            "final-admission/session-result.json", "service/start.json", "service/baseline.json",
            "service/native-start.json", "service/result.json", "service/stdout.log", "service/stderr.log",
            "service/child-result.json", "service/attempt.json", "service/jobs.json", "origin-result.json")
        for name in names:
            file = path / name
            raw = file.read_bytes()
            file.write_bytes(raw + b" ")
            try:
                with self.subTest(original=name), self.adopter(ack), self.assertRaises(ValueError):
                    S.adopt_originals([])
            finally:
                file.write_bytes(raw)
        self.assertEqual(len(self.admissions), 2)

    def test_coherent_parent_rehash_does_not_authorize_malformed_or_productive_records(self):
        path, _, ack, _ = self.prepare_handoff()
        parent, handoff = path / "origin-result.json", path / "prepare-handoff.json"
        original, handoff_raw = parent.read_bytes(), handoff.read_bytes()
        cases = [("schema", True), ("scope", "COMPLETE"), ("budgetAcceptance", "ADMITTED"),
            ("testAcceptance", "PASSED"), ("exportSaveAuthority", True), ("directories", {}),
            ("sessionIdentity", [True, path.stat().st_ino]), ("processIdentity", {"pid": os.getpid()}),
            ("retainedNs", 1), ("retainedNs", 1120 * O.NS), ("originalChain", {}), ("finalAdmissionOriginals", {})]
        for field, value in cases:
            changed = O.parse(original)
            changed[field] = value
            parent.write_bytes(O.encoded(changed))
            link = O.parse(handoff_raw)
            link["originSha256"] = O.digest(parent.read_bytes())
            handoff.write_bytes(O.encoded(link))
            try:
                with self.subTest(field=field), self.adopter({**ack, "handoffSha256": O.digest(handoff.read_bytes())}), \
                        self.assertRaises(ValueError):
                    S.adopt_originals([])
            finally:
                parent.write_bytes(original)
                handoff.write_bytes(handoff_raw)
        self.assertEqual(len(self.admissions), 2)

    def test_current_runner_event_and_ancestor_context_must_match_the_originals(self):
        _, _, ack, _ = self.prepare_handoff()
        for change in ({"RUNNER_NAME": "SYNTHETIC_OTHER_RUNNER"}, {"GRADLE_USER_HOME": "/SYNTHETIC/OTHER_HOME"},
                       {"RUNNER_ARCH": "ARM64"}, {"PYTHONPATH": "/SYNTHETIC/OVERRIDE"}):
            with self.subTest(fields=tuple(change)), self.adopter(ack), patch.dict(os.environ, change), self.assertRaises(ValueError):
                S.adopt_originals([])
        event = O.parse(self.admitted.original_event)
        event["inputs"]["expected_sha"] = "f" * 40
        self.event_path.write_bytes(O.encoded(event))
        with self.adopter(ack), self.assertRaisesRegex(O.OriginError, "ADOPTION_HOST_INPUTS_CHANGED"):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 2)

    def test_changed_attempt_cannot_open_or_recreate_the_original_episode(self):
        path, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack), patch.dict(os.environ, {"GITHUB_RUN_ATTEMPT": "2"}), self.assertRaises(FileNotFoundError):
            S.adopt_originals([])
        self.assertTrue(S.QUARANTINE)  # Existing conservative constructor policy, not reusable ownership.
        self.assertFalse(path.with_name(path.name.replace("-123-1-", "-123-2-")).exists())
        self.assertEqual(len(self.admissions), 2)

    def test_closed_handoff_shape_does_not_admit_coherent_rehashed_claims(self):
        path, _, ack, _ = self.prepare_handoff()
        file = path / "prepare-handoff.json"
        original = file.read_bytes()
        cases = [("schema", True), ("scope", "SUCCESS"), ("budgetAcceptance", "ADMITTED"),
            ("testAcceptance", "PASSED"), ("exportSaveAuthority", 1), ("processIdentity", {"pid": 91}),
            ("clock", {}), ("closedNs", 1120 * O.NS), ("recordedNs", True), ("unrecognized", "extra")]
        for name, value in cases:
            changed = O.parse(original)
            changed[name] = value
            file.write_bytes(O.encoded(changed))
            try:
                with self.subTest(field=name), self.adopter({**ack, "handoffSha256": O.digest(file.read_bytes())}), \
                        self.assertRaises(ValueError):
                    S.adopt_originals([])
            finally:
                file.write_bytes(original)
        for changed in (original + b" ", original + original):
            file.write_bytes(changed)
            try:
                with self.adopter({**ack, "handoffSha256": O.digest(changed)}), self.assertRaises(ValueError):
                    S.adopt_originals([])
            finally:
                file.write_bytes(original)
        self.assertEqual(len(self.admissions), 2)

    def test_prepare_inputs_are_not_forwarded_to_any_child_environment(self):
        path, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack):
            env = S.child_environment(path)
        self.assertNotIn(S.PREPARE_OUTCOME_ENV, env)
        self.assertNotIn(S.PREPARE_HASH_ENV, env)
        self.assertNotIn(O.wire.TOKEN_ENV, env)
        self.assertNotIn("GITHUB_TOKEN", env)

    def test_actual_readmission_failure_preserves_originals_and_cannot_be_digest_only(self):
        path, _, ack, _ = self.prepare_handoff()
        original = {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()}
        failure = S.I.AdmissionError("SYNTHETIC_SOURCE_OR_POLICY_CHANGED")
        with self.adopter(ack), patch.object(S, "admit", side_effect=failure), self.assertRaises(S.I.AdmissionError) as caught:
            S.adopt_originals([])
        self.assertIs(caught.exception, failure)
        self.assertEqual(original, {p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()})
        target = path.with_name(path.name + "-adoption")
        self.assertTrue((target / "adoption-failure.json").is_file())
        self.assertFalse((target / "adoption-result.json").exists())

    def test_late_readmission_is_work_and_cannot_publish_success_in_final_interval(self):
        path, _, ack, _ = self.prepare_handoff()
        original = self.fake_admit
        def admit(owner, fence, directory, **kwargs):
            result = original(owner, fence, directory, **kwargs)
            self.nanoseconds = fence.work
            return result
        # Enter near the work cutoff so it, not initial IO45, is the first fence.
        self.nanoseconds = O.parse((path / "prelude.json").read_bytes())["workEndNs"] - 10 * O.NS
        with self.adopter(ack), patch.object(S, "admit", side_effect=admit), self.assertRaises(O.OriginError):
            S.adopt_originals([])
        target = path.with_name(path.name + "-adoption")
        self.assertTrue((target / "adoption-failure.json").is_file())
        self.assertFalse((target / "adoption-result.json").exists())

    def test_original_change_during_actual_readmission_is_rechecked(self):
        path, _, ack, _ = self.prepare_handoff()
        original = self.fake_admit
        def admit(owner, fence, directory, **kwargs):
            result = original(owner, fence, directory, **kwargs)
            (path / "service/attempt.json").write_bytes(b"{}\n")
            return result
        with self.adopter(ack), patch.object(S, "admit", side_effect=admit), self.assertRaises(ValueError):
            S.adopt_originals([])
        self.assertEqual(len(self.admissions), 3)
        self.assertFalse((path.with_name(path.name + "-adoption") / "adoption-result.json").exists())

    def test_adopter_close_failure_keeps_receipt_provisional_and_stdout_empty(self):
        path, _, ack, _ = self.prepare_handoff()
        original, failure = S.Owner.close, OSError("SYNTHETIC_ADOPTER_CLOSE")
        def close(owner):
            original(owner)
            if owner.first is not None:
                raise failure
        output = io.BytesIO()
        with self.adopter(ack), patch.object(S.Owner, "close", close), \
                patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)), self.assertRaises(OSError) as caught:
            S.guarded(S.adopt_originals)
        self.assertIs(caught.exception, failure)
        self.assertEqual(output.getvalue(), b"")
        self.assertTrue((path.with_name(path.name + "-adoption") / "adoption-result.json").is_file())

    def test_public_adopter_flush_crossing_original_final_fence_fails_after_output(self):
        path, _, ack, _ = self.prepare_handoff()
        final = O.parse((path / "prelude.json").read_bytes())["finalEndNs"]
        output = io.BytesIO()
        def flush(): self.nanoseconds = final
        stream = SimpleNamespace(write=output.write, flush=flush)
        with self.adopter(ack), patch.object(S.sys, "stdout", SimpleNamespace(buffer=stream)), self.assertRaises(O.OriginError):
            S.guarded(S.adopt_originals)
        self.assertEqual(O.parse(output.getvalue())["scope"], S.ADOPTION_SCOPE)

    def test_adopter_cancellation_after_receipt_never_becomes_success(self):
        path, _, ack, _ = self.prepare_handoff()
        cancelled, original = [], S.Owner.write
        def write(owner, directory, name, *args, **kwargs):
            raw = original(owner, directory, name, *args, **kwargs)
            if name == "adoption-result.json":
                cancelled.append(S.signal.SIGTERM)
            return raw
        with self.adopter(ack), patch.object(S.Owner, "write", write), self.assertRaises(KeyboardInterrupt):
            S.adopt_originals(cancelled)
        self.assertTrue((path.with_name(path.name + "-adoption") / "adoption-result.json").is_file())

    def test_failed_handler_restoration_cannot_emit_success_after_adoption(self):
        _, _, ack, _ = self.prepare_handoff()
        failure, output, calls = OSError("SYNTHETIC_HANDLER_RESTORE"), io.BytesIO(), []
        def handler(number, value):
            calls.append(number)
            if value is None:
                raise failure
        with self.adopter(ack), patch.object(S.signal, "signal", side_effect=handler), \
                patch.object(S.sys, "stdout", SimpleNamespace(buffer=output)), self.assertRaises(OSError) as caught:
            S.guarded(S.adopt_originals)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(calls), 4)
        self.assertEqual(output.getvalue(), b"")

    def test_a_second_adoption_cannot_overwrite_its_original_readmission_episode(self):
        path, _, ack, _ = self.prepare_handoff()
        with self.adopter(ack):
            S.adopt_originals([])
            target = path.with_name(path.name + "-adoption")
            receipt = (target / "adoption-result.json").read_bytes()
            with self.assertRaises(FileExistsError):
                S.adopt_originals([])
            self.assertEqual((target / "adoption-result.json").read_bytes(), receipt)
        self.assertEqual(len(self.admissions), 3)


def load_tests(loader, _standard, _pattern):
    # Reuse the explicit fixture, not all inherited accepted tests as new cases.
    return unittest.TestSuite(HandoffModels(name) for name in sorted(HandoffModels.__dict__)
                              if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
