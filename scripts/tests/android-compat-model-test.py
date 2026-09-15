#!/usr/bin/env python3
"""Bounded pure candidate-source controls; no SDK, guest, collector or live proof."""

from dataclasses import FrozenInstanceError, asdict, replace
import importlib.util
from pathlib import Path
import sys
import unittest


SPEC = importlib.util.spec_from_file_location(
    "android_compat_model", Path(__file__).resolve().parents[1] / "android_compat_model.py")
model = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = model
SPEC.loader.exec_module(model)

ROW = b"ChangeId(365139289; name=RESTRICT_LOCAL_NETWORK; disabled)"
APP = model.PackageFacts("com.example.app", 10123, 0, 37)
OTHER = model.PackageFacts("com.example.other", 10123, 0, 36)
FACTS = model.DeclaredUidFacts(APP.uid, APP.user_id, (APP.package_name,), (APP,))
CLASSIFIER = model.Classifier("REL", 37, 0)
PROFILE = model.CANDIDATE_PROFILE_ID


def row_with(**changes):
    return replace(model.CANDIDATE_DEFINITION, **changes)


def resolve(row=model.CANDIDATE_DEFINITION, facts=FACTS, classifier=CLASSIFIER, profile=PROFILE):
    return model.resolve_candidate_uid(row, facts, classifier, profile)


class LimitsMixin:
    def assert_model_only(self, result):
        self.assertEqual(result.scope, "CANDIDATE_SOURCE_MODEL")
        self.assertEqual(result.evidence_level, "MODEL_ONLY")
        self.assertEqual(result.runtime_state, "COMPAT_STATE_UNPROVEN")
        self.assertEqual(result.change_kind, "LEGACY_DEVELOPER_OPT_IN")
        self.assertEqual(result.mandatory_system_flag, "UNKNOWN")
        self.assertEqual(result.permission_propagation, "UNKNOWN")
        self.assertEqual(asdict(result)["runtime_state"], "COMPAT_STATE_UNPROVEN")

    def assert_hold(self, result, reason=None):
        self.assert_model_only(result)
        self.assertIsInstance(result.hold_reason, model.HoldReason)
        if reason is not None:
            self.assertEqual(result.hold_reason, reason)
        if isinstance(result, model.ModelResult):
            self.assertIsNone(result.enabled)
            self.assertEqual(result.declared_package_values, ())


class RowTests(LimitsMixin, unittest.TestCase):
    def test_exact_row_with_or_without_one_lf_preserves_original(self):
        for original in (ROW, ROW + b"\n"):
            with self.subTest(original=original):
                result = model.parse_candidate_row(original)
                self.assertIs(result.original, original)
                self.assertIsNone(result.hold_reason)
                self.assertEqual(result.row, model.CANDIDATE_DEFINITION)
                self.assert_model_only(result)

    def test_evaluated_map_order_is_not_semantic(self):
        entries = (b"com.example.app=true, com.example.other=false",
                   b"com.example.other=false, com.example.app=true")
        facts = replace(FACTS, member_names=(APP.package_name, OTHER.package_name), packages=(APP, OTHER))
        results = []
        for entry in entries:
            original = ROW[:-1] + b"; packageOverrides={" + entry + b"})\n"
            parsed = model.parse_candidate_row(original)
            self.assertIsNone(parsed.hold_reason)
            self.assertEqual(parsed.original, original)
            results.append(resolve(parsed.row, facts))
        self.assertEqual(results[0], results[1])
        self.assertIs(results[0].enabled, False)

    def test_empty_or_nonbyte_capture_is_not_success(self):
        for original in (b"", b"\n", b"No compat overrides.\n", "", None, bytearray(ROW)):
            with self.subTest(original=original):
                result = model.parse_candidate_row(original)
                self.assert_hold(result)
                if type(original) is bytes:
                    self.assertIs(result.original, original)
                else:
                    self.assertIsNone(result.original)

    def test_every_truncated_prefix_of_candidate_row_holds(self):
        for end in range(len(ROW)):
            original = ROW[:end]
            with self.subTest(end=end):
                parsed = model.parse_candidate_row(original)
                self.assert_hold(parsed)
                self.assertIs(parsed.original, original)

    def test_whitespace_multiline_control_and_noncanonical_rows_hold(self):
        variants = (b" " + ROW, ROW + b" ", ROW + b"\r\n", ROW + b"\n\n", ROW + b"\n" + ROW,
                    ROW.replace(b"; ", b";", 1), ROW.replace(b"; ", b";  ", 1),
                    ROW.replace(b"365139289", b"0365139289"), ROW.replace(b"365139289", b"+365139289"),
                    ROW.replace(b"365139289", b"-0"), ROW.replace(b"365139289", b"9223372036854775808"),
                    ROW.replace(b"365139289", b"9" * 100), ROW + b"\x00", ROW + b"\xff")
        for original in variants:
            with self.subTest(original=original):
                result = model.parse_candidate_row(original)
                self.assert_hold(result)
                self.assertIs(result.original, original)

    def test_oversize_bytes_are_retained_not_truncated(self):
        at_limit = b"X" * model.MAX_ROW_BYTES
        self.assert_hold(model.parse_candidate_row(at_limit), model.HoldReason.ROW_SYNTAX)
        original = at_limit + b"X"
        result = model.parse_candidate_row(original)
        self.assert_hold(result, model.HoldReason.ROW_LIMIT)
        self.assertIs(result.original, original)

    def test_unknown_duplicate_out_of_order_or_valued_flag_fields_hold(self):
        variants = (
            (ROW[:-1] + b"; unknown=true)", model.HoldReason.UNKNOWN_FIELD),
            (ROW[:-1] + b"; disabled)", model.HoldReason.DUPLICATE_FIELD),
            (ROW.replace(b"; disabled", b"; name=RESTRICT_LOCAL_NETWORK; disabled"),
             model.HoldReason.DUPLICATE_FIELD),
            (b"ChangeId(365139289; disabled; name=RESTRICT_LOCAL_NETWORK)", model.HoldReason.FIELD_ORDER),
            (ROW.replace(b"disabled", b"disabled=true"), model.HoldReason.ROW_SYNTAX),
            (ROW.replace(b"disabled", b"disabled=false"), model.HoldReason.ROW_SYNTAX),
        )
        for original, reason in variants:
            with self.subTest(original=original):
                self.assert_hold(model.parse_candidate_row(original), reason)

    def test_known_optional_fields_preserved_but_unpinned_definitions_hold(self):
        original = (b"ChangeId(365139289; name=RESTRICT_LOCAL_NETWORK; enableSinceTargetSdk=37"
                    b"; disabled; loggingOnly; noLogging; overridable)")
        parsed = model.parse_candidate_row(original)
        self.assert_hold(parsed, model.HoldReason.UNSUPPORTED_DEFINITION)
        self.assertEqual(parsed.row.enable_since_target_sdk, 37)
        self.assertIs(parsed.row.logging_only, True)
        self.assertIs(parsed.row.no_logging, True)
        self.assertIs(parsed.row.overridable, True)
        self.assert_hold(resolve(parsed.row), model.HoldReason.UNSUPPORTED_DEFINITION)

    def test_name_id_disabled_and_threshold_must_match_candidate(self):
        variants = (ROW.replace(b"365139289", b"365139290"), ROW.replace(b"RESTRICT_LOCAL_NETWORK", b"OTHER"),
                    b"ChangeId(365139289; disabled)", b"ChangeId(365139289; name=RESTRICT_LOCAL_NETWORK)",
                    ROW.replace(b"; disabled", b"; enableSinceTargetSdk=37; disabled"))
        for original in variants:
            with self.subTest(original=original):
                parsed = model.parse_candidate_row(original)
                self.assert_hold(parsed, model.HoldReason.UNSUPPORTED_DEFINITION)
                self.assert_hold(resolve(parsed.row), model.HoldReason.UNSUPPORTED_DEFINITION)

    def test_threshold_sentinel_is_omitted_and_integer_syntax_is_canonical(self):
        for value in (b"-1", b"-2", b"-0", b"+37", b"037", b"2147483648", b"true", b""):
            with self.subTest(value=value):
                original = ROW.replace(b"; disabled", b"; enableSinceTargetSdk=" + value + b"; disabled")
                self.assert_hold(model.parse_candidate_row(original), model.HoldReason.ROW_SYNTAX)

    def test_evaluated_override_map_rejects_malformed_and_duplicate_entries(self):
        for value in (b"{}", b"com.example.app=true", b"{com.example.app=True}",
                      b"{com.example.app=1}", b"{com.example.app=null}", b"{com.example.app=true=bad}",
                      b"{com.example.app=true,com.example.other=false}", b"{com.example.app=true, }",
                      b"{com.example.app=true, com.example.app=true}",
                      b"{com.example.app=true, com.example.app=false}", b"{=true}", b"{com..app=true}"):
            with self.subTest(value=value):
                original = ROW[:-1] + b"; packageOverrides=" + value + b")"
                self.assert_hold(model.parse_candidate_row(original))

    def test_duplicate_evaluated_map_field_holds(self):
        field = b"; packageOverrides={com.example.app=true}"
        self.assert_hold(model.parse_candidate_row(ROW[:-1] + field + field + b")"),
                         model.HoldReason.DUPLICATE_FIELD)

    def test_override_count_is_bounded(self):
        entries = [f"com.example.p{number}=true".encode() for number in range(model.MAX_OVERRIDES + 1)]
        for count in (model.MAX_OVERRIDES, model.MAX_OVERRIDES + 1):
            original = ROW[:-1] + b"; packageOverrides={" + b", ".join(entries[:count]) + b"})"
            parsed = model.parse_candidate_row(original)
            if count == model.MAX_OVERRIDES:
                self.assertIsNone(parsed.hold_reason)
                self.assertEqual(len(parsed.row.evaluated_overrides), count)
            else:
                self.assert_hold(parsed, model.HoldReason.OVERRIDE_LIMIT)

    def test_any_raw_serialization_is_opaque_and_never_evaluated(self):
        for raw in (b"{}", b"{com.example.app=true}", b"{com.example.app=false}",
                    b"{com.example.app=PackageOverride@1234}", b"nonsense", b""):
            for prefix in (b"", b"; packageOverrides={com.example.app=true}"):
                with self.subTest(raw=raw, prefix=prefix):
                    original = ROW[:-1] + prefix + b"; rawOverrides=" + raw + b"; overridable)"
                    parsed = model.parse_candidate_row(original)
                    self.assert_hold(parsed, model.HoldReason.RAW_OVERRIDES_UNQUALIFIED)
                    self.assertIs(parsed.original, original)
                    self.assertIsNone(parsed.row)
                    self.assert_hold(resolve(parsed.row))


class ResolverTests(LimitsMixin, unittest.TestCase):
    def test_disabled_legacy_default_is_not_mandatory_lnp_state(self):
        result = resolve()
        self.assertIs(result.enabled, False)
        self.assertIsNone(result.hold_reason)
        self.assertEqual(result.declared_package_values, ((APP.package_name, False),))
        self.assert_model_only(result)

    def test_explicit_true_and_false_evaluated_overrides_take_precedence(self):
        for enabled in (True, False):
            row = row_with(evaluated_overrides=(model.EvaluatedOverride(APP.package_name, enabled),))
            result = resolve(row)
            self.assertIs(result.enabled, enabled)
            self.assertIsNone(result.hold_reason)
            self.assert_model_only(result)

    def test_uid_and_uses_every_declared_package_and_is_order_independent(self):
        row = row_with(evaluated_overrides=(model.EvaluatedOverride(APP.package_name, True),))
        facts = replace(FACTS, member_names=(APP.package_name, OTHER.package_name), packages=(APP, OTHER))
        first = resolve(row, facts)
        second = resolve(row, replace(facts, member_names=tuple(reversed(facts.member_names)),
                                      packages=tuple(reversed(facts.packages))))
        self.assertEqual(first, second)
        self.assertIs(first.enabled, False)
        all_true = replace(row, evaluated_overrides=(model.EvaluatedOverride(OTHER.package_name, True),
                                                     model.EvaluatedOverride(APP.package_name, True)))
        self.assertIs(resolve(all_true, facts).enabled, True)
        self.assertEqual(first.declared_package_values, ((APP.package_name, True), (OTHER.package_name, False)))

    def test_unrelated_override_does_not_change_uid_value(self):
        self.assertIs(resolve(row_with(evaluated_overrides=(model.EvaluatedOverride(OTHER.package_name, True),)))
                      .enabled, False)

    def test_synthetic_kernel_covers_disabled_threshold_sentinel_and_platform_clamp(self):
        # Valid synthetic definitions test arithmetic only; never public candidate admission.
        controls = (
            (True, -1, 37, 37, False), (True, 1, 37, 37, False),
            (False, -1, 1, 37, True), (False, 0, 1, 37, True),
            (False, 37, 36, 37, False), (False, 37, 37, 37, True),
            (False, 37, 38, 37, True), (False, 38, 38, 37, False),
            (False, 37, 37, 36, False), (False, 2147483647, 2147483647, 37, False),
            (False, 2147483647, 2147483647, 2147483647, True),
        )
        for disabled, threshold, target, platform, expected in controls:
            with self.subTest(control=(disabled, threshold, target, platform)):
                row = row_with(disabled=disabled, enable_since_target_sdk=threshold)
                self.assertIs(model._enabled_for_package(row, replace(APP, target_sdk=target), platform), expected)
                if row != model.CANDIDATE_DEFINITION:
                    self.assert_hold(resolve(row), model.HoldReason.UNSUPPORTED_DEFINITION)

    def test_false_override_precedes_enabled_synthetic_default_and_true_precedes_disabled(self):
        for disabled, enabled in ((False, False), (True, True)):
            row = row_with(disabled=disabled, enable_since_target_sdk=37,
                           evaluated_overrides=(model.EvaluatedOverride(APP.package_name, enabled),))
            self.assertIs(model._enabled_for_package(row, APP, 37), enabled)
            self.assert_hold(resolve(row), model.HoldReason.UNSUPPORTED_DEFINITION)

    def test_wrong_profile_and_unqualified_classifier_hold(self):
        for profile in (None, True, "", PROFILE + "-stale", "REL/37"):
            self.assert_hold(resolve(profile=profile), model.HoldReason.UNSUPPORTED_PROFILE)
        classifiers = (None, {}, replace(CLASSIFIER, codename="Baklava"), replace(CLASSIFIER, codename="rel"),
                       replace(CLASSIFIER, sdk_int=36), replace(CLASSIFIER, sdk_int=38),
                       replace(CLASSIFIER, sdk_int=True), replace(CLASSIFIER, sdk_int="37"),
                       replace(CLASSIFIER, preview_sdk_int=1), replace(CLASSIFIER, preview_sdk_int=False),
                       replace(CLASSIFIER, preview_sdk_int=-1), replace(CLASSIFIER, sdk_int=2147483648))
        for classifier in classifiers:
            with self.subTest(classifier=classifier):
                self.assert_hold(resolve(classifier=classifier), model.HoldReason.UNSUPPORTED_CLASSIFIER)

    def test_wrong_definition_flags_boolean_as_integer_and_bounds_hold(self):
        changes = ({"change_id": True}, {"change_id": 365139290}, {"change_id": 1 << 63},
                   {"change_id": -(1 << 63) - 1}, {"name": None}, {"name": "OTHER"},
                   {"enable_since_target_sdk": True}, {"enable_since_target_sdk": -2},
                   {"enable_since_target_sdk": 1 << 31}, {"enable_since_target_sdk": 37},
                   {"disabled": 1}, {"disabled": False}, {"logging_only": 0}, {"logging_only": True},
                   {"no_logging": 0}, {"no_logging": True}, {"overridable": 0}, {"overridable": True})
        for change in changes:
            with self.subTest(change=change):
                self.assert_hold(resolve(row_with(**change)), model.HoldReason.UNSUPPORTED_DEFINITION)
        self.assert_hold(resolve(None), model.HoldReason.INPUT_TYPE)

    def test_manually_constructed_overrides_are_validated_not_trusted(self):
        variants = ([model.EvaluatedOverride(APP.package_name, True)], (None,), ((APP.package_name, True),),
                    (model.EvaluatedOverride(APP.package_name, 1),),
                    (model.EvaluatedOverride(APP.package_name, "false"),),
                    (model.EvaluatedOverride(None, True),), (model.EvaluatedOverride("bad name", True),),
                    (model.EvaluatedOverride(APP.package_name, True), model.EvaluatedOverride(APP.package_name, False)))
        for overrides in variants:
            with self.subTest(overrides=overrides):
                self.assert_hold(resolve(row_with(evaluated_overrides=overrides)))
        oversized = tuple(model.EvaluatedOverride(f"com.example.p{i}", True)
                          for i in range(model.MAX_OVERRIDES + 1))
        self.assert_hold(resolve(row_with(evaluated_overrides=oversized)), model.HoldReason.OVERRIDE_LIMIT)
        self.assert_hold(resolve(row_with(raw_overrides="{com.example.app=true}")),
                         model.HoldReason.RAW_OVERRIDES_UNQUALIFIED)

    def test_empty_missing_extra_duplicate_or_conflicting_uid_members_hold(self):
        variants = (None, {}, replace(FACTS, member_names=()), replace(FACTS, packages=()),
                    replace(FACTS, member_names=[APP.package_name]), replace(FACTS, packages=[APP]),
                    replace(FACTS, member_names=(APP.package_name, APP.package_name)),
                    replace(FACTS, member_names=(APP.package_name, OTHER.package_name)),
                    replace(FACTS, member_names=(OTHER.package_name,)),
                    replace(FACTS, packages=(APP, OTHER)), replace(FACTS, packages=(APP, APP)),
                    replace(FACTS, packages=(APP, replace(APP, target_sdk=36))),
                    replace(FACTS, member_names=(None,)), replace(FACTS, packages=(None,)))
        for facts in variants:
            with self.subTest(facts=facts):
                self.assert_hold(resolve(facts=facts))

    def test_system_shell_sandbox_multiuser_and_out_of_bounds_uid_hold(self):
        for uid in (True, 0, 1000, 2000, 9999, 20000, 99000, 110123, -1, 1 << 31, "10123"):
            with self.subTest(uid=uid):
                self.assert_hold(resolve(facts=replace(FACTS, uid=uid)), model.HoldReason.UID_SCOPE)
        for user_id in (True, 1, -1, 1 << 31, "0"):
            self.assert_hold(resolve(facts=replace(FACTS, user_id=user_id)), model.HoldReason.UID_SCOPE)
        for uid in (10000, 19999):
            app = replace(APP, uid=uid)
            self.assertIsNone(resolve(facts=replace(FACTS, uid=uid, packages=(app,))).hold_reason)

    def test_package_uid_user_target_type_bounds_and_identity_mismatch_hold(self):
        variants = ({"uid": 10124}, {"uid": True}, {"uid": 1 << 31}, {"user_id": 1},
                    {"user_id": False}, {"target_sdk": True}, {"target_sdk": "37"},
                    {"target_sdk": 0}, {"target_sdk": -1}, {"target_sdk": 1 << 31},
                    {"package_name": "com..app"}, {"package_name": "a." + "x" * 254})
        for change in variants:
            with self.subTest(change=change):
                facts = replace(FACTS, packages=(replace(APP, **change),))
                self.assert_hold(resolve(facts=facts), model.HoldReason.UID_FACTS)
        for target in (1, 36, 37, 2147483647):
            self.assertIsNone(resolve(facts=replace(FACTS, packages=(replace(APP, target_sdk=target),))).hold_reason)

    def test_uid_member_count_is_bounded(self):
        for count in (model.MAX_UID_PACKAGES, model.MAX_UID_PACKAGES + 1):
            packages = tuple(replace(APP, package_name=f"com.example.p{i}") for i in range(count))
            facts = replace(FACTS, member_names=tuple(package.package_name for package in packages), packages=packages)
            result = resolve(facts=facts)
            if count == model.MAX_UID_PACKAGES:
                self.assertIsNone(result.hold_reason)
                self.assertEqual(len(result.declared_package_values), count)
            else:
                self.assert_hold(result, model.HoldReason.UID_FACTS)

    def test_complete_looking_fixture_and_model_boolean_cannot_upgrade_proof(self):
        parsed = model.parse_candidate_row(ROW[:-1] + b"; packageOverrides={com.example.app=true})\n")
        resolved = resolve(parsed.row)
        self.assertIs(resolved.enabled, True)
        for result in (parsed, resolved, model.parse_candidate_row(b"broken"), resolve(facts=None)):
            self.assert_model_only(result)
            with self.assertRaises(FrozenInstanceError):
                result.runtime_state = "RESOLVED_FROM_LIVE_PLATFORM_COMPAT_DUMP"
            with self.assertRaises(ValueError):
                replace(result, runtime_state="RESOLVED_FROM_LIVE_PLATFORM_COMPAT_DUMP")
        with self.assertRaises(TypeError):
            model.resolve_candidate_uid(parsed.row, FACTS, CLASSIFIER, PROFILE, trusted=True)
        with self.assertRaises(TypeError):
            model.parse_candidate_row(ROW, complete=True)


if __name__ == "__main__":
    unittest.main()
