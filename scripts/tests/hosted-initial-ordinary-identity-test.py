#!/usr/bin/env python3
"""Offline Stage2 binding/cohort DATA models, not admission or qualification.

Only synthetic source/comment/run/event records and committed PUBLIC policy
are used. Prior fixture builders are reused, not earlier test methods/results.
No native owner, credential acquisition, private key, provider, crypto or CI.
"""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
from pathlib import Path
import sys
import unittest


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_ordinary_identity as H
import hosted_initial_recipient_gate as G

spec = importlib.util.spec_from_file_location("ordinary_identity_stages_fixture",
    Path(__file__).with_name("hosted-initial-recipient-stages-test.py"))
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
S, I = H.stages, H.I


class IdentityModels(unittest.TestCase):
    def setUp(self):
        self.declaration, self.histories = F.stage2(F.stage1())
        self.select()

    def select(self, profile="desktop", role="linux-x64"):
        self.observed = F.observation2(self.declaration, profile, role)
        self.comment = F.comment(self.declaration, 8002, F.START + 200)
        self.match = S.match_ordinary(comment_raw=I.encoded(self.comment), comment_id=8002,
            body_sha256=F.body_hash(self.comment), observation_raw=I.encoded(self.observed),
            now=F.NOW, histories=self.histories, prior_ancestry_raw=F.H1.encode() + b"\n", **F.policy_inputs())
        self.event = {"action": "synchronize", "number": 999,
            "repository": {"full_name": I.REPOSITORY, "default_branch": "main"},
            "pull_request": copy.deepcopy(self.observed["pullRequest"])}

    def bind(self, **options):
        args = dict(match=self.match, comment_raw=I.encoded(self.comment), event_raw=I.encoded(self.event),
                    policy_raw=F.POLICY, now=F.NOW)
        args.update(options)
        return H.bind_worker_match(**args)

    def altered_match(self, mutate):
        value = I.parse(self.match.record, S.LIMIT)
        mutate(value)
        return S.OrdinaryMatch(I.encoded(value))

    def refuse(self, code=".+", **options):
        with self.assertRaisesRegex(I.AdmissionError, code):
            self.bind(**options)

    def test_four_worker_cohorts_remain_ordinary_reference_bindings(self):
        for profile, role in (("desktop", "linux-x64"), ("desktop", "windows-x64"),
                              ("desktop", "macos-arm64"), ("full", "macos-arm64")):
            with self.subTest(profile=profile, role=role):
                self.select(profile, role)
                bound = self.bind()
                value = I.parse(bound.record, I.EVENT_LIMIT)
                self.assertIs(type(bound), H.InitialOrdinaryIdentity)
                self.assertNotIsInstance(bound, (I.Admission, S.BootstrapMatch, G.GateEligibility))
                self.assertEqual(H.cache_cohort(bound.record), (profile, role))
                self.assertEqual(value["source"], {"commit": F.MERGE, "tree": F.T2})
                self.assertEqual(value["policy"]["origin"], "reviewed-head")
                self.assertEqual(value["policy"]["commit"], F.H2)
                self.assertEqual(value["initialRecipient"]["stage1"]["reviewed"]["commit"], F.H1)
                self.assertEqual(value["initialRecipient"]["qualificationAcceptance"], "NOT_ESTABLISHED_BY_REFERENCE_MATCH")
                self.assertEqual(value["firstPullRequest"], self.declaration["firstPullRequest"])
                self.assertNotIn("cacheCohort", value)
                self.assertNotIn("producerCommand", value)
                if profile == "desktop":
                    self.assertIs(value["samplePackagingRequired"], False)
                    self.assertEqual(value["suites"], ["cli"])
                else:
                    self.assertNotIn("samplePackagingRequired", value)
                    self.assertEqual(value["suites"], ["cli", "diagnostics"])

    def test_bound_originals_are_immutable_without_visible_key_or_record_payload(self):
        bound = self.bind()
        self.assertEqual(bound.original_event, I.encoded(self.event))
        self.assertEqual(bound.original_policy, F.POLICY)
        self.assertEqual(bound.public_key, I._policy(F.POLICY, F.NOW)[1])
        self.assertNotIn("BEGIN PGP", repr(bound))
        self.assertNotIn("firstPullRequest", repr(bound))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            bound.record = b"changed"

    def test_gate_bootstrap_untyped_and_mutable_matches_cannot_bind(self):
        class EqualBytes(bytes):
            def __eq__(self, _other):
                raise AssertionError("original-byte subclass equality must not run")
        for match in (S.BootstrapMatch(self.match.record), G.GateEligibility(self.match.record),
                self.match.record, {}, None, S.OrdinaryMatch(bytearray(self.match.record)),
                S.OrdinaryMatch(EqualBytes(self.match.record))):
            with self.subTest(kind=type(match).__name__):
                self.refuse("ORIGINAL_TYPES", match=match)
        for name, value in (("comment_raw", bytearray(I.encoded(self.comment))),
                ("event_raw", memoryview(I.encoded(self.event))), ("policy_raw", EqualBytes(F.POLICY))):
            self.refuse("ORIGINAL_TYPES", **{name: value})

    def test_exact_match_encoding_is_not_normalized(self):
        for raw in (self.match.record + b"\n", b" " + self.match.record, self.match.record + b"{}"):
            with self.subTest(prefix=raw[:1]):
                self.refuse(match=S.OrdinaryMatch(raw))

    def test_original_c2_comment_and_its_complete_roster_are_required(self):
        for change in ({"id": 8003}, {"updated_at": F.utc(F.START + 201)}, {"body": self.comment["body"] + " "}):
            with self.subTest(change=tuple(change)):
                self.refuse(comment_raw=I.encoded({**self.comment, **change}))
        self.refuse("ORIGINAL_TYPES", comment_raw=None)
        changed = copy.deepcopy(self.declaration)
        changed["firstPullRequest"]["runs"][3]["runId"] = "403"
        self.refuse("COMMENT_DIGEST", comment_raw=I.encoded(F.comment(changed, 8002, F.START + 200)))

    def test_reference_or_roster_change_cannot_reuse_original_owner_statement_hash(self):
        match = self.altered_match(lambda v: v["qualifications"][0]["inventory"].update(sha256="f" * 64))
        self.refuse("OWNER_STATEMENT_BINDING", match=match)
        value = I.parse(self.bind().record, I.EVENT_LIMIT)
        value["firstPullRequest"]["runs"][3]["runId"] = "403"
        with self.assertRaisesRegex(I.AdmissionError, "OWNER_STATEMENT_BINDING"):
            H.cache_cohort(I.encoded(value))

    def test_policy_origin_exact_bytes_and_h2_binding_cannot_be_trusted_main(self):
        self.refuse("POLICY_BYTES", policy_raw=F.POLICY + b"\n")
        for change in ({"origin": "main"}, {"commit": S.BASE["commit"]}, {"commit": F.H1},
                {"commit": F.MERGE}, {"blob": "f" * 40}, {"sha256": "0" * 64}):
            with self.subTest(change=change):
                self.refuse(match=self.altered_match(lambda v: v["policy"].update(change)))

    def test_actual_event_keeps_repository_pr_merge_and_head_identities(self):
        for mutate in (lambda e: e.update(number=True), lambda e: e.update(action="closed"),
                lambda e: e["repository"].update(full_name="other/repo"),
                lambda e: e["pull_request"]["head"].update(sha=F.H1),
                lambda e: e["pull_request"].update(merge_commit_sha=F.H2),
                lambda e: e["pull_request"].update(auto_merge={})):
            event = copy.deepcopy(self.event)
            mutate(event)
            self.refuse(event_raw=I.encoded(event))

    def test_current_window_is_finite_and_does_not_renew_historical_h1(self):
        self.assertGreater(F.NOW, F.START + 150)
        self.assertEqual(self.bind(now=F.FIRST2).record, self.bind(now=F.END - 1).record)
        for now in (F.FIRST2 - 1, F.END, True):
            with self.subTest(now=now):
                self.refuse(now=now)
        for field, value in (("firstUseAt", True), ("expiresAt", F.END + 1), ("notBefore", 0)):
            self.refuse(match=self.altered_match(lambda v: v.update({field: value})))

    def test_partial_or_relabelled_stage2_markers_refuse_instead_of_falling_through(self):
        raw = self.bind().record
        for mutate in (lambda v: v.update(scope="ORDINARY"), lambda v: v.pop("scope"),
                lambda v: v.pop("firstPullRequest"), lambda v: v.pop("initialRecipient"),
                lambda v: v["initialRecipient"].update(scope=S.STAGE1 + "_MATCH_ONLY_NOT_ADMISSION"),
                lambda v: v["policy"].pop("origin"), lambda v: v.update(profile="cache-bootstrap"),
                lambda v: v.update(scope="ORDINARY", initialRecipient={}, firstPullRequest={})):
            value = I.parse(raw, I.EVENT_LIMIT)
            mutate(value)
            with self.assertRaises(I.AdmissionError):
                H.cache_cohort(I.encoded(value))
        self.assertIsNone(H.cache_cohort(I.encoded({"profile": "desktop", "policy": {}, "github": {}})))

    def test_numeric_type_substitutions_cannot_use_python_bool_int_equality(self):
        raw = self.bind().record
        for mutate in (lambda v: v.update(schema=True), lambda v: v.update(samplePackagingRequired=0),
                lambda v: v["policy"].update(retentionDays=14.0),
                lambda v: v["initialRecipient"].update(firstUseAt=float(F.FIRST2)),
                lambda v: v["firstPullRequest"].update(number=999.0),
                lambda v: v["github"]["eventBinding"].update(number=999.0)):
            value = I.parse(raw, I.EVENT_LIMIT)
            mutate(value)
            with self.assertRaises(I.AdmissionError):
                H.cache_cohort(I.encoded(value))

    def test_desktop_packaging_and_full_suites_are_not_bootstrap_or_publication(self):
        for profile, role in (("desktop", "linux-x64"), ("full", "macos-arm64")):
            self.select(profile, role)
            raw = self.bind().record
            for change in ({"suites": []}, {"samplePackagingRequired": True},
                    {"producerCommand": ["help"]}, {"cacheCohort": {"profile": profile, "role": role}},
                    {"qualificationAcceptance": "PASS"}):
                with self.subTest(profile=profile, change=tuple(change)):
                    value = I.parse(raw, I.EVENT_LIMIT)
                    value.update(change)
                    with self.assertRaises(I.AdmissionError):
                        H.cache_cohort(I.encoded(value))

    def test_gate_or_swapped_worker_and_service_source_cannot_be_relabelled(self):
        for field, bad in (("job", G.JOB), ("runAttempt", "2"), ("workflowSha", F.H2),
                ("event", "workflow_dispatch"), ("ref", S.SOURCE_REF), ("runnerArch", "ARM64")):
            with self.subTest(field=field):
                self.refuse(match=self.altered_match(lambda v: v["github"].update({field: bad})))
        self.refuse(match=self.altered_match(lambda v: v.update(qualificationAcceptance="PASS")))
        self.refuse(match=self.altered_match(lambda v: v["source"].update(commit=F.H2)))

    def test_cached_record_reconstruction_and_public_key_field_shapes_remain_closed(self):
        raw = self.bind().record
        for mutate in (lambda v: v["source"].update(commit=F.H2),
                lambda v: v["github"]["eventBinding"].update(head=F.H1),
                lambda v: v["policy"].update(origin="main"),
                lambda v: v["policy"].update(fingerprint="not-an-openpgp-fingerprint"),
                lambda v: v["policy"].update(keySha256="Z" * 64)):
            value = I.parse(raw, I.EVENT_LIMIT)
            mutate(value)
            with self.assertRaises(I.AdmissionError):
                H.cache_cohort(I.encoded(value))
        with self.assertRaisesRegex(I.AdmissionError, "RECORD_BYTES"):
            H.cache_cohort(bytearray(raw))


if __name__ == "__main__":
    unittest.main(failfast=True)
