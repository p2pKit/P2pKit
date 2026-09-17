#!/usr/bin/env python3
"""Pre-budget cache routing models, NOT producer/native/provider qualification.

Actual identity/plan/receipt code sees synthetic Git/event/identity/file records.
No files are allocated, no native owner is constructed and no product runs.
Unsupported bootstrap execution must refuse BEFORE any ownership acquisition,
even when supplied otherwise coherent ordinary Desktop/FULL receipt models.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_identity as B
import hosted_dependency_cache as K
import hosted_dependency_seed_files as S

SPEC = importlib.util.spec_from_file_location(
    "bootstrap_identity_fixtures", ROOT / "scripts/tests/hosted-cache-bootstrap-identity-test.py")
I = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(I)


class BootstrapCohort(I.OfflineCase):
    def setUp(self):
        super().setUp()
        self.session = ROOT.parent / "synthetic-no-directory" / "session"
        self.bytes = b"synthetic allowlisted bytes, not a dependency"
        self.xml = ('<?xml version="1.0" encoding="UTF-8"?><verification-metadata xmlns="' +
            S.authority.NAMESPACE + '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
            'xsi:schemaLocation="' + S.authority.SCHEMA_LOCATION + '"><configuration>'
            '<verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures>'
            '</configuration><components><component group="org.fixture" name="example" version="1.0">'
            '<artifact name="example.jar"><sha256 value="' + S.digest(self.bytes) + '"/></artifact>'
            '</component></components></verification-metadata>').encode()
        self.compiled = S.authority.parse_allowlist(self.xml)
        self.inputs = {"files": {name: S.digest(self.xml if index == 0 else name.encode())
                                 for index, name in enumerate(S.INPUTS)},
                       "allowlistSha256": self.compiled.authority_sha256,
                       "artifacts": 1, "components": 1, "policy": S.policy()}
        self.info = SimpleNamespace(identity=(1, 2))
        self.source_info = SimpleNamespace(identity=(1, 3))
        self.configure(I.SELECTIONS[0])

    def configure(self, row):
        name, self.profile, self.role, system, arch = row
        self.env.update(RUNNER_OS=system, RUNNER_ARCH=arch)
        self.event["inputs"]["selection"] = name
        self.raw = self.admit().record

    def stage(self, raw=None, profile=None, role=None):
        raw = self.raw if raw is None else raw
        profile, role = profile or self.profile, role or self.role
        path = S.stage_path(self.session, profile, role)
        # Independently shaped records let negative controls reach every real
        # validator without an earlier helper filtering out the bad input.
        value = S.record(raw)
        return {"schema": 1, "scope": "DEPENDENCY_SEED_STAGING_V1", "profile": profile, "role": role,
                "source": value["source"], "github": value["github"], "admissionSha256": S.digest(raw),
                "container": str(path), "restoreHome": str(path / "restore-home"),
                "containerIdentity": [1, 2], "sourceIdentity": [1, 3], "inputs": self.inputs,
                "retirement": "KNOWN", "completed": True}

    def intent(self, stage, raw=None):
        raw = self.raw if raw is None else raw
        return {"schema": 1, "policy": S.POLICY, "profile": stage["profile"], "role": stage["role"],
                "admissionSha256": S.digest(raw), "stagingSha256": S.digest(S.encoded(stage)),
                "container": stage["container"], "restoreHome": stage["restoreHome"], "inputs": self.inputs}

    def context(self, stage, raw=None):
        raw = self.raw if raw is None else raw
        context = {"session": str(self.session), "profile": stage["profile"], "role": stage["role"],
                   "source": S.record(raw)["source"], "dependencySeed": self.intent(stage, raw)}
        if stage["profile"] == "full":
            # This plausible MODEL is specifically NOT bootstrap authority.
            context.update(jobBudgetSha256="f" * 64, primaryAbiAccounting={
                "productiveCutoffRawNs": 120_000_000_001})
        return context

    def plan(self, stage=None, raw=None, mode="bootstrap"):
        raw = self.raw if raw is None else raw
        stage = self.stage(raw) if stage is None else stage
        return K.make_plan(raw, S.encoded(stage), self.compiled, self.inputs, session=self.session,
                           profile=stage["profile"], role=stage["role"], mode=mode)

    def validate_boundaries(self, raw, stage):
        profile, role, path = stage["profile"], stage["role"], Path(stage["container"])
        return (
            lambda: S.stage_record(raw, profile, role, path, self.info, self.source_info, self.inputs),
            lambda: S.validate_stage(stage, raw, profile, role, path, self.info, self.source_info, self.inputs),
            lambda: S.seed_intent(raw, profile, role, path, S.encoded(stage), self.inputs),
            lambda: S.validate_retained_stage(stage, raw, self.context(stage, raw), self.inputs),
            lambda: self.plan(stage, raw),
        )

    def assert_rejected_everywhere(self, raw, stage):
        for index, call in enumerate(self.validate_boundaries(raw, stage)):
            with self.subTest(boundary=index):
                with self.assertRaisesRegex(S.SeedError, "BOOTSTRAP"):
                    call()

    def seed_model(self, stage, context):
        canonical = {"gradleHome": str(self.session / "state/gradle-home"), "gradlePropertiesSha256": "a" * 64}
        canonical_raw, context_raw, staging_raw = map(S.encoded, (canonical, context, stage))
        intent = context["dependencySeed"]
        window = S.window(1, 120_000_000_001, 90_000_000_001, raw=self.profile == "full",
                          job_budget="f" * 64 if self.profile == "full" else None)
        window["finishedNs"] = 2
        value = {"schema": 1, "scope": "DEPENDENCY_SEED_FILE_CUSTODY_V1",
            "intentSha256": S.digest(S.encoded(intent)), "contextSha256": S.digest(context_raw),
            "canonicalContextSha256": S.digest(canonical_raw), "stagingSha256": S.digest(staging_raw),
            "source": context["source"], "github": S.record(self.raw)["github"], "role": self.role,
            "home": canonical["gradleHome"], "restoreHome": stage["restoreHome"], "inputs": self.inputs,
            "policy": S.policy(), "wrapper": S.WRAPPER, "status": "KNOWN_MISS", "completed": True,
            "retirement": "KNOWN", "errors": [], "window": window,
            "counts": {"prehashBytes": 0, "outputBytes": 0, "sourceNames": 0, "destinationMembers": 0,
                       "sha256Rejected": 0, "layoutRejected": 0}, "admitted": [],
            "misses": [{"index": 0, "reason": "ABSENT", "rejected": 0}], "sourceIdentity": [1, 3],
            "homeIdentity": [1, 4], "propertiesSha256": "a" * 64, "propertiesAfterSha256": "a" * 64}
        return value, canonical_raw, context_raw, staging_raw

    def test_all_six_bootstrap_cohorts_plan_without_budget_or_ordinary_test_context(self):
        for row in I.SELECTIONS:
            with self.subTest(selection=row[0]):
                self.configure(row)
                stage = self.stage()
                for call in self.validate_boundaries(self.raw, stage):
                    call()
                expected = K.cache_key(row[1], row[2], self.compiled.authority_sha256,
                                       self.inputs["files"][S.INPUTS[1]])
                plan = self.plan(stage)
                self.assertEqual((plan["profile"], plan["role"], plan["key"]), (row[1], row[2], expected))
                self.assertEqual(plan["admissionSha256"], S.digest(self.raw))
                self.assertEqual(S.record(self.raw)["profile"], "cache-bootstrap")
                self.assertNotIn("jobBudgetSha256", plan)
                self.assertNotIn("primaryAbiAccounting", plan)

    def test_cross_profile_and_role_rejected_at_every_pre_budget_boundary(self):
        for row in I.SELECTIONS:
            self.configure(row)
            for other in I.SELECTIONS:
                if row[1:3] != other[1:3]:
                    with self.subTest(selection=row[0], substituted=other[0]):
                        self.assert_rejected_everywhere(self.raw, self.stage(profile=other[1], role=other[2]))

    def test_bootstrap_cannot_select_consume_even_for_matching_cohort(self):
        for row in I.SELECTIONS:
            self.configure(row)
            with self.subTest(selection=row[0]), self.assertRaisesRegex(S.SeedError, "BOOTSTRAP"):
                self.plan(mode="consume")

    def test_selection_and_declared_cohort_must_agree(self):
        value = S.record(self.raw)
        for mutate in (lambda v: v.update(selection="full-macos-arm64"),
                       lambda v: v.update(selection=None), lambda v: v.update(selection="custom"),
                       lambda v: v.update(cacheCohort={"profile": "full", "role": "macos-arm64"}),
                       lambda v: v["cacheCohort"].update(extra=True), lambda v: v.update(cacheCohort=None)):
            changed = copy.deepcopy(value)
            mutate(changed)
            raw = S.encoded(changed)
            self.assert_rejected_everywhere(raw, self.stage(raw))

    def test_host_labels_workflow_and_job_remain_the_bootstrap_identity(self):
        for changes in ({"runnerOS": "macOS"}, {"runnerArch": "ARM64"},
                        {"workflow": ".github/workflows/ci.yml"}, {"job": "complete-gate"},
                        {"event": "push"}):
            changed = S.record(self.raw)
            changed["github"].update(changes)
            raw = S.encoded(changed)
            self.assert_rejected_everywhere(raw, self.stage(raw))

    def test_configuration_only_request_cannot_gain_test_or_command_authority(self):
        for changes in ({"producerCommand": ["check"]}, {"producerCommand": list(B.COMMAND) + ["--write-locks"]},
                        {"producerScope": "FULL"}, {"testAcceptance": "PASS"}, {"suites": ["cli"]}):
            raw = S.encoded({**S.record(self.raw), **changes})
            self.assert_rejected_everywhere(raw, self.stage(raw))

    def test_bootstrap_marker_omission_or_ordinary_relabelling_never_falls_through(self):
        for remove, changes in (("scope", {}), ("profile", {}),
                                (None, {"scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY"}),
                                (None, {"profile": "desktop"}),
                                (None, {"scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", "profile": "desktop"})):
            changed = S.record(self.raw)
            if remove:
                del changed[remove]
            changed.update(changes)
            raw = S.encoded(changed)
            self.assert_rejected_everywhere(raw, self.stage(raw))

    def test_bootstrap_schema_and_reserved_fields_are_closed(self):
        for changes in ({"schema": True}, {"schema": 2}, {"extra": "not ignored"}):
            raw = S.encoded({**S.record(self.raw), **changes})
            self.assert_rejected_everywhere(raw, self.stage(raw))
        for field in ("cacheCohort", "selection", "producerCommand", "producerScope", "testAcceptance"):
            changed = S.record(self.raw)
            del changed[field]
            raw = S.encoded(changed)
            self.assert_rejected_everywhere(raw, self.stage(raw))

    def test_nested_bootstrap_markers_cannot_be_hidden_by_stripping_flat_fields(self):
        for ordinary_labels in (False, True):
            for marker in ("workflow", "job", "selection", "expectedCommit", "expectedTree"):
                changed = S.record(self.raw)
                for field in ("scope", "profile", "cacheCohort", "selection", "producerCommand",
                              "producerScope", "testAcceptance"):
                    del changed[field]
                if ordinary_labels:
                    changed.update(scope="ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", profile="desktop")
                original = copy.deepcopy(changed["github"])
                changed["github"].update(workflow=".github/workflows/desktop-cross-host.yml",
                                          job="desktop", eventBinding={})
                if marker in ("workflow", "job"):
                    changed["github"][marker] = original[marker]
                else:
                    changed["github"]["eventBinding"][marker] = original["eventBinding"][marker]
                raw = S.encoded(changed)
                with self.subTest(ordinary_labels=ordinary_labels, marker=marker):
                    self.assert_rejected_everywhere(raw, self.stage(raw))

    def test_stripped_bootstrap_admission_cannot_validate_a_coherent_ordinary_seed(self):
        changed = S.record(self.raw)
        for field in ("cacheCohort", "selection", "producerCommand", "producerScope", "testAcceptance"):
            del changed[field]
        changed.update(scope="ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", profile="desktop")
        self.raw = S.encoded(changed)  # Original bootstrap workflow/job are still contradictory.
        stage = self.stage()
        context = self.context(stage)
        seed, canonical_raw, context_raw, staging_raw = self.seed_model(stage, context)
        with self.assertRaisesRegex(S.SeedError, "BOOTSTRAP"):
            S.validate_receipt(seed, context["dependencySeed"], staging_raw, context_raw,
                               canonical_raw, self.raw, self.compiled)

    def test_plan_return_cannot_mutate_original_admission_or_stage(self):
        stage = self.stage()
        original = S.encoded(stage)
        plan = self.plan(stage)
        plan["source"]["commit"] = "9" * 40
        plan["github"]["runAttempt"] = "2"
        self.assertEqual(S.encoded(stage), original)
        self.assertEqual(S.record(self.raw)["source"]["commit"], I.SOURCE)
        self.assertEqual(self.plan()["github"]["runAttempt"], "1")

    def test_ordinary_minimal_model_contract_and_cache_key_stay_separate(self):
        value = S.record(self.raw)
        ordinary = S.encoded({"source": value["source"], "github": {"runId": "123", "runAttempt": "1"}})
        stage = self.stage(ordinary)
        for call in self.validate_boundaries(ordinary, stage):
            call()
        consume = self.plan(stage, ordinary, mode="consume")
        bootstrap = self.plan()
        self.assertEqual(consume["key"], bootstrap["key"])
        self.assertNotEqual(consume["admissionSha256"], bootstrap["admissionSha256"])

    def test_ordinary_record_with_bootstrap_only_fields_is_not_legacy_fallback(self):
        value = S.record(self.raw)
        ordinary = {"schema": 1, "scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", "profile": "desktop",
                    "source": value["source"], "github": {"runId": "123", "runAttempt": "1"}}
        for field in ("cacheCohort", "selection", "producerCommand", "producerScope", "testAcceptance"):
            raw = S.encoded({**ordinary, field: value[field]})
            self.assert_rejected_everywhere(raw, self.stage(raw))

    def test_legacy_desktop_or_fabricated_full_seed_receipt_cannot_be_bootstrap_execution(self):
        for row in (I.SELECTIONS[0], I.SELECTIONS[4]):
            self.configure(row)
            stage = self.stage()
            context = self.context(stage)
            seed, canonical_raw, context_raw, staging_raw = self.seed_model(stage, context)
            with self.subTest(selection=row[0]), self.assertRaisesRegex(
                    S.SeedError, "BOOTSTRAP_EXECUTION_NOT_CONNECTED"):
                S.validate_receipt(seed, context["dependencySeed"], staging_raw, context_raw,
                                   canonical_raw, self.raw, self.compiled)

    def test_all_six_seed_execution_routes_refuse_before_any_owned_acquisition(self):
        for row in I.SELECTIONS:
            self.configure(row)
            stage = self.stage()
            context = self.context(stage)
            seed, canonical_raw, context_raw, _staging_raw = self.seed_model(stage, context)
            with self.subTest(selection=row[0]), patch.object(S, "_Owners", side_effect=AssertionError("NO_OWNER")):
                with self.assertRaisesRegex(S.SeedError, "BOOTSTRAP_EXECUTION_NOT_CONNECTED"):
                    S.seed_home(object(), Path(S.record(canonical_raw)["gradleHome"]), context["dependencySeed"],
                                stage, self.compiled, context_raw, canonical_raw, self.raw,
                                end=1, check=lambda: None, now=lambda: 1, interval=seed["window"])

    def test_export_and_save_entry_and_retained_receipts_refuse_bootstrap(self):
        for row in (I.SELECTIONS[0], I.SELECTIONS[4]):
            self.configure(row)
            stage, plan = self.stage(), self.plan()
            context = self.context(stage)
            seed, canonical_raw, context_raw, staging_raw = self.seed_model(stage, context)
            args = (plan, staging_raw, S.encoded(seed), context_raw, canonical_raw, self.raw, self.compiled)
            save_args = (plan, b"{}", staging_raw, S.encoded(seed), context_raw,
                         canonical_raw, self.raw, self.compiled)
            options = dict(end=1, check=lambda: None, now=lambda: 1, interval=seed["window"])
            calls = (lambda: K.export_snapshot(object(), *args, **options),
                     lambda: K.validate_export_receipt({}, *args),
                     lambda: K.save_set(object(), *save_args, **options),
                     lambda: K.save_set(object(), *save_args, **options, frozen_raw=b"{}"),
                     lambda: K.validate_save_set_receipt({}, *save_args),
                     lambda: K.validate_save_set_receipt({}, *save_args, frozen_raw=b"{}"))
            with patch.object(S, "_Owners", side_effect=AssertionError("NO_OWNER")):
                for index, call in enumerate(calls):
                    with self.subTest(selection=row[0], boundary=index), self.assertRaisesRegex(
                            S.SeedError, "BOOTSTRAP_EXECUTION_NOT_CONNECTED"):
                        call()

    def test_coherent_legacy_seed_fixture_is_valid_only_as_ordinary_model(self):
        value = S.record(self.raw)
        self.raw = S.encoded({"source": value["source"], "github": {"runId": "123", "runAttempt": "1"}})
        stage = self.stage()
        context = self.context(stage)
        seed, canonical_raw, context_raw, staging_raw = self.seed_model(stage, context)
        self.assertEqual(S.validate_receipt(seed, context["dependencySeed"], staging_raw, context_raw,
                                           canonical_raw, self.raw, self.compiled), seed)


if __name__ == "__main__":
    unittest.main()
