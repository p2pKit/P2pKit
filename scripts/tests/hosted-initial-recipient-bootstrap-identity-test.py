#!/usr/bin/env python3
"""Guarded supplied-identity/cohort models; not admission or qualification.

Only the committed PUBLIC policy and synthetic source/run/authority records are
used. No key directory, native backend, provider, crypto, process or network.
The separate native enclosure suite covers the actual owning-call composition.
"""
from __future__ import annotations

import copy
import ctypes  # Stdlib initialization only, before every project import.
import dataclasses
import importlib.util
from pathlib import Path, PureWindowsPath
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_bootstrap_identity as H
import hosted_cache_bootstrap_origin as O
import hosted_dependency_cache as K
import hosted_dependency_seed_files as S
import hosted_test_evidence as E


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


F = load("initial_identity_stages_fixture", "hosted-initial-recipient-stages-test.py")
C = load("initial_identity_cohort_fixture", "hosted-cache-bootstrap-cohort-test.py")
I, B = H.I, H.B


class WorkerIdentityModels(unittest.TestCase):
    def setUp(self):
        self.declaration = F.stage1()
        self.select("desktop-linux-x64")

    def select(self, name):
        self.observed = F.observation1(self.declaration, name)
        self.match = F.check1(self.declaration, self.observed)
        self.event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"},
            "ref": H.stages.SOURCE_REF, "inputs": {"selection": name, "expected_sha": F.H1, "expected_tree": F.T1}}

    def bind(self, **options):
        values = dict(match=self.match, event_raw=I.encoded(self.event), policy_raw=F.POLICY, now=F.DONE1)
        values.update(options)
        return H.bind_worker_match(**values)

    def altered_match(self, mutate):
        value = I.parse(self.match.record, H.stages.LIMIT)
        mutate(value)
        return H.stages.BootstrapMatch(I.encoded(value))

    def refuse(self, **options):
        with self.assertRaises((I.AdmissionError, ValueError)):
            self.bind(**options)

    def test_six_worker_roles_keep_candidate_origin_and_original_authority(self):
        for name, profile, role, system, arch in B.SELECTIONS:
            with self.subTest(selection=name):
                self.select(name)
                bound = self.bind()
                value = I.parse(bound.record, I.EVENT_LIMIT)
                self.assertIs(type(bound), H.InitialBootstrapIdentity)
                self.assertNotIsInstance(bound, I.Admission)
                self.assertEqual(H.cache_cohort(bound.record), (profile, role))
                self.assertEqual(value["initialRecipient"], I.parse(self.match.record, H.stages.LIMIT))
                self.assertEqual(value["initialRecipient"]["originalBase"], H.stages.BASE)
                self.assertEqual(value["policy"]["origin"], "reviewed-head")
                self.assertEqual(value["policy"]["commit"], F.H1)
                self.assertEqual(value["github"]["eventBinding"]["originalMain"], H.stages.BASE["commit"])
                self.assertNotIn("policyMain", value["github"]["eventBinding"])
                self.assertEqual((value["github"]["runnerOS"], value["github"]["runnerArch"]), (system, arch))
                self.assertEqual(value["producerCommand"], list(B.COMMAND))
                self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
                self.assertNotIn("suites", value)

    def test_bound_bytes_are_immutable_and_not_in_the_representation(self):
        bound = self.bind()
        self.assertEqual(bound.original_event, I.encoded(self.event))
        self.assertEqual(bound.original_policy, F.POLICY)
        self.assertEqual(bound.public_key, I._policy(F.POLICY, F.DONE1)[1])
        self.assertNotIn("BEGIN PGP", repr(bound))
        with self.assertRaises(dataclasses.FrozenInstanceError): bound.record = b"replacement"

    def test_gate_ordinary_or_untyped_match_cannot_bind_worker_identity(self):
        for value in (H.stages.OrdinaryMatch(self.match.record), self.match.record, {}, None):
            with self.subTest(kind=type(value).__name__): self.refuse(match=value)

    def test_mutable_and_equality_overriding_originals_are_refused(self):
        class EqualBytes(bytes):
            def __eq__(self, other): return True
        for raw in (bytearray(self.match.record), memoryview(self.match.record), EqualBytes(self.match.record)):
            with self.subTest(kind=type(raw).__name__): self.refuse(match=H.stages.BootstrapMatch(raw))
        self.refuse(event_raw=bytearray(I.encoded(self.event)))
        self.refuse(policy_raw=memoryview(F.POLICY))

    def test_match_encoding_cannot_be_normalized(self):
        for raw in (self.match.record + b"\n", self.match.record + b"{}", b" " + self.match.record):
            with self.subTest(raw=raw[:1]): self.refuse(match=H.stages.BootstrapMatch(raw))

    def test_original_policy_bytes_and_blob_must_match(self):
        self.refuse(policy_raw=F.POLICY + b"\n")
        self.refuse(match=self.altered_match(lambda v: v["policy"].update(blob="f" * 40)))

    def test_original_policy_cannot_be_labelled_as_main(self):
        for mutate in (lambda v: v["policy"].update(origin="main"),
                       lambda v: v["policy"].update(commit=H.stages.BASE["commit"]),
                       lambda v: v["policy"].update(sha256="0" * 64)):
            self.refuse(match=self.altered_match(mutate))

    def test_wrong_stage_or_changed_reviewed_source_refuses(self):
        for mutate in (lambda v: v.update(scope=H.stages.STAGE2 + "_MATCH_ONLY_NOT_ADMISSION"),
                       lambda v: v["reviewed"].update(commit=F.H2),
                       lambda v: v.update(source=H.stages.BASE, reviewed=H.stages.BASE),
                       lambda v: v["originalBase"].update(tree=F.T2)):
            self.refuse(match=self.altered_match(mutate))

    def test_worker_host_job_source_and_selection_remain_closed(self):
        for name, value in (("job", "initial-recipient-gate"), ("profile", "full"), ("event", "pull_request"),
                            ("ref", "refs/heads/main"), ("workflowSha", F.H2), ("runnerOS", "Windows"),
                            ("selection", "full-linux-x64"), ("runAttempt", "0")):
            with self.subTest(name=name):
                self.refuse(match=self.altered_match(lambda v: v["github"].update({name: value})))

    def test_exact_authority_owner_fields_and_environment_are_preserved(self):
        for mutate in (lambda v: v["authority"].update(owner="OtherOwner"),
                       lambda v: v["authority"].update(ownerId=True),
                       lambda v: v["authority"].update(url="https://github.com/other"),
                       lambda v: v["authority"].update(bodySha256="not-a-hash"),
                       lambda v: v["environment"].update(name="sample-development-release"),
                       lambda v: v["environment"]["branchPolicies"].pop()):
            self.refuse(match=self.altered_match(mutate))

    def test_original_window_is_finite_and_not_restarted(self):
        self.assertEqual(self.bind(now=F.FIRST1).record, self.bind(now=self.declaration["expiresAt"] - 1).record)
        for now in (F.FIRST1 - 1, self.declaration["expiresAt"], F.END, True): self.refuse(now=now)
        for mutate in (lambda v: v.update(firstUseAt=F.START - 1),
                       lambda v: v.update(expiresAt=F.END + 1),
                       lambda v: v.update(notBefore=True),
                       lambda v: v["authority"].update(createdAt=F.utc(F.FIRST1 + 1))):
            self.refuse(match=self.altered_match(mutate))

    def test_dispatch_has_only_original_three_inputs(self):
        for mutate in (lambda v: v["inputs"].update(selection="desktop-windows-x64"),
                       lambda v: v["inputs"].update(expected_sha=F.H2),
                       lambda v: v["inputs"].update(expected_tree=F.T2),
                       lambda v: v["inputs"].update(public_key="not-an-input"),
                       lambda v: v["repository"].update(full_name="other/repository"),
                       lambda v: v.update(ref="refs/heads/main")):
            value = copy.deepcopy(self.event)
            mutate(value)
            self.refuse(event_raw=I.encoded(value))

    def test_extra_match_fields_are_not_an_open_identity_descriptor(self):
        self.refuse(match=self.altered_match(lambda v: v.update(approved=True)))
        self.refuse(match=self.altered_match(lambda v: v["authority"].update(approved=True)))

    def test_legacy_trusted_main_admission_and_export_still_refuse_initial_type(self):
        bound = self.bind()
        with self.assertRaises(I.AdmissionError): B.cache_cohort(bound.record)
        with self.assertRaises(O.OriginError): O.admitted_value(bound)
        def forbidden(**_args): raise AssertionError("MUST_REFUSE_BEFORE_QUERY_OR_CRYPTO")
        with self.assertRaisesRegex(E.hosted_evidence.EvidenceError, "original admission"):
            E._bound_bootstrap_manifest(SimpleNamespace(), root=ROOT, admission=bound, query_runner=forbidden)

    def test_initial_cohort_is_only_an_explicit_planning_route(self):
        bound = self.bind()
        self.assertEqual(S.validate_cohort(bound.record, "desktop", "linux-x64"), ("desktop", "linux-x64"))
        with self.assertRaisesRegex(S.SeedError, "COHORT_CHANGED"):
            S.validate_cohort(bound.record, "full", "macos-arm64")
        with self.assertRaisesRegex(S.SeedError, "EXECUTION_NOT_CONNECTED"):
            S.require_connected_execution(bound.record)

    def test_marker_relabelling_cannot_fall_through_to_ordinary_or_legacy_bootstrap(self):
        base = I.parse(self.bind().record, I.EVENT_LIMIT)
        for mutate in (lambda v: v.update(scope=B.SCOPE),
                       lambda v: v.update(scope="ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", profile="desktop"),
                       lambda v: v.pop("initialRecipient"),
                       lambda v: v.update(scope=B.SCOPE, profile="cache-bootstrap")):
            value = copy.deepcopy(base)
            mutate(value)
            with self.assertRaisesRegex(S.SeedError, "BOOTSTRAP_IDENTITY_CHANGED"):
                S.validate_cohort(I.encoded(value), "desktop", "linux-x64")

    def test_cohort_reader_rejects_disagreements_extra_fields_and_encoding_changes(self):
        base = I.parse(self.bind().record, I.EVENT_LIMIT)
        for mutate in (lambda v: v["cacheCohort"].update(profile="full"),
                       lambda v: v["github"]["eventBinding"].update(policyMain=F.H1),
                       lambda v: v["github"].update(runAttempt="2"),
                       lambda v: v.update(producerCommand=["check"]),
                       lambda v: v.update(testAcceptance="PASSED"),
                       lambda v: v["policy"].update(retentionDays=True),
                       lambda v: v.update(suites=["full"]),
                       lambda v: v["policy"].update(expiresAt=F.FIRST1)):
            value = copy.deepcopy(base)
            mutate(value)
            with self.assertRaises(I.AdmissionError): H.cache_cohort(I.encoded(value))
        with self.assertRaises(I.AdmissionError): H.cache_cohort(I.encoded(base) + b"\n")

    def test_ordinary_without_initial_markers_still_uses_legacy_reader(self):
        raw = I.encoded({"scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", "profile": "desktop"})
        self.assertIsNone(H.cache_cohort(raw))
        self.assertIsNone(S.validate_cohort(raw, "desktop", "linux-x64"))
        S.require_connected_execution(raw)

    def test_new_validation_suppliers_are_in_original_source_input_roster(self):
        for name in ("hosted_initial_recipient_bootstrap_identity.py", "hosted_initial_recipient_stages.py",
                     "hosted_initial_recipient_exception.py"):
            self.assertIn("scripts/" + name, S.INPUTS)

    def test_initial_plan_keeps_existing_literal_stage_and_key_but_not_execution_authority(self):
        fixture = C.BootstrapCohort("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        bound = self.bind()
        slot = self.observed["github"]
        session = fixture.runner_temp / ("p2pkit-cache-originals-" + slot["runId"] + "-" + slot["runAttempt"] +
            "-desktop-linux-x64-productive") / "initializer"
        path = S.stage_path(session, "desktop", "linux-x64", admitted_raw=bound.record)
        self.assertEqual(path, fixture.runner_temp / "p2pkit-dependency-seed-desktop-linux-x64")
        stage = S.stage_record(bound.record, "desktop", "linux-x64", path, fixture.info, fixture.source_info, fixture.inputs)
        plan = K.make_plan(bound.record, S.encoded(stage), fixture.compiled, fixture.inputs, session=session,
                           profile="desktop", role="linux-x64", mode="bootstrap")
        self.assertEqual(plan["path"], str(path.joinpath("restore-home", *S.PREFIX)))
        self.assertEqual(plan["key"], K.cache_key("desktop", "linux-x64", fixture.compiled.authority_sha256,
                                               fixture.inputs["files"][S.INPUTS[1]]))
        self.assertEqual(plan["admissionSha256"], S.digest(bound.record))
        self.assertEqual(plan["github"]["eventBinding"]["policyHead"], F.H1)
        with self.assertRaisesRegex(S.SeedError, "BOOTSTRAP_CANNOT_CONSUME"):
            K.make_plan(bound.record, S.encoded(stage), fixture.compiled, fixture.inputs, session=session,
                        profile="desktop", role="linux-x64", mode="consume")

    def test_windows_stage_spelling_is_explicitly_only_a_pure_path_model(self):
        self.select("desktop-windows-x64")
        bound = self.bind()
        slot = self.observed["github"]
        session = PureWindowsPath("D:/runner-temp") / ("p2pkit-cache-originals-" + slot["runId"] + "-1-" +
            "desktop-windows-x64-productive") / "initializer"
        with patch.object(S, "Path", PureWindowsPath):
            result = S.stage_path(session, "desktop", "windows-x64", admitted_raw=bound.record)
        self.assertEqual(result, PureWindowsPath("D:/runner-temp/p2pkit-dependency-seed-desktop-windows-x64"))


if __name__ == "__main__":
    unittest.main()
