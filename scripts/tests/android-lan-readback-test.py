#!/usr/bin/env python3
"""Pure declared-input controls. No Android/SDK, command, file or runtime claim."""

from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict, replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest


SPEC = importlib.util.spec_from_file_location(
    "android_lan_readback", Path(__file__).resolve().parents[1] / "android_lan_readback.py")
readback = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = readback
SPEC.loader.exec_module(readback)


def binding():
    return {
        "token": "1" * 32, "sourceCommit": "2" * 40, "sourceTree": "3" * 40,
        "appApkSha256": "4" * 64, "testApkSha256": "5" * 64, "profileSha256": "6" * 64,
        "installId": "7" * 32, "packageName": readback.APP_PACKAGE, "user": 0, "uid": 10123,
        "pid": 321, "processStartElapsedMillis": 1000, "installEpochMillis": 1_790_000_000_000,
        "sdkInt": 37, "targetSdk": 37, "codename": "REL", "previewSdkInt": 0, "buildDirty": False,
    }


def packet(values=(True, True)):
    result = {
        "schema": readback.SCHEMA, "mode": readback.MODE, "binding": binding(),
        "readerClass": readback.READER_CLASS, "flagPackage": readback.FLAG_PACKAGE,
        "flagName": readback.FLAG_NAME, "events": [],
    }
    for index in range(3):
        elapsed = 1100 + index * 10
        event = {
            "phase": "load" if index == 0 else "read", "binding": binding(), "readerId": "8" * 32,
            "start": {"epochMillis": binding()["installEpochMillis"] + elapsed, "elapsedMillis": elapsed},
            "end": {"epochMillis": binding()["installEpochMillis"] + elapsed + 1, "elapsedMillis": elapsed + 1},
            "outcome": {"kind": "LOADED"},
        }
        if index:
            event["default"] = index == 2
            event["outcome"] = {"kind": "RETURNED", "value": values[index - 1]}
        result["events"].append(event)
    return result


def encoded(value):
    return json.dumps(value, separators=(",", ":"), ensure_ascii=True).encode("ascii")


def checked(value, expected=None):
    return readback.validate_readback(encoded(value), binding() if expected is None else expected)


class ReadbackContentTests(unittest.TestCase):
    def assert_unqualified(self, result):
        self.assertEqual(result.evidence_level, "RECORDED_INPUT_ONLY")
        self.assertEqual(result.runtime_state, "COMPAT_STATE_UNPROVEN")
        self.assertEqual(result.qualification, "HOLD_UNQUALIFIED_RUNTIME_SEMANTICS")
        self.assertEqual(result.permission_enforcement, "NOT_PROVEN")
        self.assertEqual(result.same_instance_revocation, "NOT_EXECUTED")
        self.assertEqual(asdict(result)["qualification"], "HOLD_UNQUALIFIED_RUNTIME_SEMANTICS")

    def assert_hold(self, result, reason=None):
        self.assert_unqualified(result)
        self.assertIsNone(result.declared_value)
        self.assertEqual(result.classification, "CONTENT_HOLD")
        self.assertIsInstance(result.content_hold, readback.Hold)
        if reason is not None:
            self.assertEqual(result.content_hold, reason)

    def test_four_pairs_have_only_declared_content_meaning(self):
        for values in ((True, True), (False, False), (False, True), (True, False)):
            with self.subTest(values=values):
                result = checked(packet(values))
                self.assert_unqualified(result)
                if values[0] is values[1]:
                    self.assertIs(result.declared_value, values[0])
                    self.assertIsNone(result.content_hold)
                    self.assertEqual(result.classification, "MATCHING_DECLARED_" + str(values[0]).upper())
                else:
                    self.assert_hold(result, readback.Hold.LOOKUP_UNRESOLVED_OR_DRIFT if values[1]
                                     else readback.Hold.INCONSISTENT_OR_DRIFT)

    def test_originals_are_retained_without_mutating_or_printing_bindings(self):
        data, expected = packet(), binding()
        before = deepcopy((data, expected))
        raw = encoded(data)
        result = readback.validate_readback(raw, expected)
        self.assertIs(result.original, raw)
        self.assertEqual((data, expected), before)
        self.assertNotIn(expected["sourceCommit"], repr(result))
        with self.assertRaises(FrozenInstanceError):
            result.runtime_state = "QUALIFIED"
        with self.assertRaises(ValueError):
            replace(result, qualification="PASS")
        with self.assertRaises(TypeError):
            readback.validate_readback(raw, expected, trusted=True)

    def test_nonbytes_and_empty_or_nonobject_json_hold(self):
        for raw in (None, "{}", bytearray(b"{}"), b"", b"null", b"[]", b"true", b"37", b'"record"'):
            with self.subTest(raw=raw):
                result = readback.validate_readback(raw, binding())
                self.assert_hold(result)
                self.assertIs(result.original, raw if type(raw) is bytes else None)

    def test_every_truncated_record_prefix_holds(self):
        raw = encoded(packet())
        for length in range(len(raw)):
            with self.subTest(length=length):
                self.assert_hold(readback.validate_readback(raw[:length], binding()))

    def test_duplicate_keys_at_all_levels_and_escaped_duplicates_hold(self):
        raw = encoded(packet())
        cases = (
            raw.replace(b'"mode":', b'"mode":"profile-readback","mode":', 1),
            raw.replace(b'"uid":10123', b'"uid":10123,"uid":10123', 1),
            raw.replace(b'"phase":"read"', b'"phase":"read","phase":"read"', 1),
            raw.replace(b'"value":true', b'"value":true,"value":true', 1),
            raw.replace(b'"mode":', b'"m\\u006fde":"profile-readback","mode":', 1),
        )
        for original in cases:
            with self.subTest(original=original[:90]):
                self.assert_hold(readback.validate_readback(original, binding()), readback.Hold.DUPLICATE_FIELD)

    def test_invalid_encoding_trailing_data_and_deep_input_hold(self):
        raw = encoded(packet())
        for original in (b"\xff", b"\xef\xbb\xbf" + raw, raw + raw, raw + b"\x00", b"[" * 2000 + b"]" * 2000):
            with self.subTest(size=len(original)):
                self.assert_hold(readback.validate_readback(original, binding()), readback.Hold.JSON_SYNTAX)

    def test_numeric_aliases_nonfinite_values_and_giant_integers_hold(self):
        raw = encoded(packet())
        for token in (b"0.0", b"1e0", b"NaN", b"Infinity", b"-Infinity", b"-0", b"9" * 128):
            with self.subTest(token=token):
                bad = raw.replace(b'"user":0', b'"user":' + token, 1)
                self.assert_hold(readback.validate_readback(bad, binding()), readback.Hold.NUMBER_FORMAT)

    def test_oversize_record_preserves_exact_bytes_without_parsing(self):
        raw = b"x" * (readback.MAX_RECORD_BYTES + 1)
        result = readback.validate_readback(raw, binding())
        self.assert_hold(result, readback.Hold.RECORD_LIMIT)
        self.assertIs(result.original, raw)
        self.assert_hold(readback.validate_readback(raw[:-1], binding()), readback.Hold.JSON_SYNTAX)

    def test_closed_schema_rejects_authority_and_old_terminal_substitution(self):
        for extra in ({"trusted": True}, {"semanticsQualified": True}, {"p2pkitOutcome": "PASS"},
                      {"p2pkitSameInstanceRevocation": "PASS"}, {"adoptedShellIdentity": False}):
            data = packet(); data.update(extra)
            self.assert_hold(checked(data), readback.Hold.SCHEMA)
        for field, value in (("schema", 1), ("mode", "peer"), ("readerClass", "hidden.PlatformAconfigPackage"),
                             ("flagPackage", "other.flags"), ("flagName", "new_storage_public_api")):
            data = packet(); data[field] = value
            self.assert_hold(checked(data), readback.Hold.SCHEMA)

    def test_expected_binding_is_mandatory_and_type_checked(self):
        for expected in ({}, [], None, {**binding(), "trusted": True}, {**binding(), "user": False},
                         {**binding(), "profileSha256": "short"}):
            self.assert_hold(readback.validate_readback(encoded(packet()), expected), readback.Hold.EXPECTED_BINDING)

    def test_each_binding_field_is_checked_against_separate_expectation(self):
        for key, length in (("token", 32), ("sourceCommit", 40), ("sourceTree", 40),
                            ("appApkSha256", 64), ("testApkSha256", 64), ("profileSha256", 64), ("installId", 32)):
            for position in (None, 0, 1, 2):
                with self.subTest(key=key, position=position):
                    data = packet()
                    target = data["binding"] if position is None else data["events"][position]["binding"]
                    target[key] = "a" * length
                    self.assert_hold(checked(data), readback.Hold.BINDING_DRIFT)
        for key, value in (("uid", 10124), ("pid", 322), ("processStartElapsedMillis", 1001),
                           ("installEpochMillis", binding()["installEpochMillis"] - 1)):
            data = packet(); data["events"][2]["binding"][key] = value
            self.assert_hold(checked(data), readback.Hold.BINDING_DRIFT)

    def test_scope_and_boolean_integer_aliases_are_not_accepted(self):
        for key, value in (("user", False), ("user", 1), ("uid", 0), ("uid", 2000), ("uid", 9999),
                           ("uid", 20000), ("uid", 110123), ("pid", 0), ("pid", True),
                           ("sdkInt", 36), ("targetSdk", 36), ("previewSdkInt", 1), ("previewSdkInt", False),
                           ("buildDirty", 0), ("buildDirty", True), ("codename", "PREVIEW"),
                           ("packageName", readback.APP_PACKAGE + ".test"), ("sourceCommit", "Z" * 40)):
            with self.subTest(key=key, value=value):
                data = packet(); data["events"][1]["binding"][key] = value
                self.assert_hold(checked(data), readback.Hold.BINDING)

    def test_reader_label_must_match_load_without_claiming_object_identity(self):
        for value in (None, True, "", "8" * 31, "9" * 32):
            data = packet(); data["events"][2]["readerId"] = value
            self.assert_hold(checked(data), readback.Hold.READER_IDENTITY)
        self.assert_unqualified(checked(packet()))

    def test_default_order_and_types_cannot_be_reordered_or_repeated(self):
        for index, value in ((1, True), (2, False), (1, 0), (2, 1), (1, None), (2, "true")):
            data = packet(); data["events"][index]["default"] = value
            self.assert_hold(checked(data), readback.Hold.DEFAULT_ORDER)
        for index in range(3):
            data = packet(); data["events"][index]["phase"] = "read" if index == 0 else "load"
            self.assert_hold(checked(data), readback.Hold.EVENT_ORDER)

    def test_returned_value_is_boolean_only_and_no_status_fields_are_ignored(self):
        for value in (0, 1, "true", None, [], {}):
            data = packet(); data["events"][1]["outcome"]["value"] = value
            self.assert_hold(checked(data), readback.Hold.OUTCOME)
        for outcome in (None, {"kind": "PASS", "value": True}, {"kind": "RETURNED", "value": True, "error": None}):
            data = packet(); data["events"][1]["outcome"] = outcome
            self.assert_hold(checked(data), readback.Hold.OUTCOME)

    def test_all_public_storage_error_codes_hold_at_load_or_either_read(self):
        for index in range(3):
            for code in range(5):
                with self.subTest(index=index, code=code):
                    data = packet(); data["events"] = data["events"][:index + 1]
                    event = data["events"][index]
                    event["outcome"] = {"kind": "ERROR", "errorType": readback.STORAGE_ERROR, "errorCode": code}
                    if index == 0:
                        event["readerId"] = None
                    self.assert_hold(checked(data), readback.Hold.LOAD_ERROR if index == 0 else readback.Hold.READ_ERROR)

    def test_unknown_error_codes_types_and_success_after_error_hold(self):
        for name, code in ((readback.STORAGE_ERROR, True), (readback.STORAGE_ERROR, -1),
                           (readback.STORAGE_ERROR, 5), (readback.STORAGE_ERROR, None),
                           ("java.lang.SecurityException", 0), ("bad error text", None)):
            data = packet(); data["events"][2]["outcome"] = {"kind": "ERROR", "errorType": name, "errorCode": code}
            self.assert_hold(checked(data), readback.Hold.ERROR_RECORD)
        data = packet()
        data["events"][1]["outcome"] = {"kind": "ERROR", "errorType": readback.STORAGE_ERROR, "errorCode": 0}
        self.assert_hold(checked(data), readback.Hold.EVENT_ORDER)

    def test_unsupported_public_surface_and_access_errors_never_become_false(self):
        for name in ("java.lang.NoSuchMethodError", "java.lang.NoClassDefFoundError", "java.lang.SecurityException"):
            data = packet(); data["events"] = data["events"][:1]
            data["events"][0].update(readerId=None,
                                    outcome={"kind": "ERROR", "errorType": name, "errorCode": None})
            self.assert_hold(checked(data), readback.Hold.LOAD_ERROR)

    def test_missing_extra_or_nonarray_events_hold(self):
        for events in ([], packet()["events"][:1], packet()["events"][:2], packet()["events"] * 2, {}, None):
            data = packet(); data["events"] = events
            self.assert_hold(checked(data), readback.Hold.INCOMPLETE)

    def test_clocks_must_be_typed_ordered_and_inside_declared_install_and_lifetime(self):
        for index, edge, clock, value in ((0, "start", "elapsedMillis", 999),
                                         (0, "start", "epochMillis", binding()["installEpochMillis"] - 1),
                                         (1, "end", "elapsedMillis", 1109),
                                         (2, "start", "elapsedMillis", 1110),
                                         (2, "start", "epochMillis", binding()["installEpochMillis"] + 1110),
                                         (1, "end", "epochMillis", binding()["installEpochMillis"] + 1109),
                                         (0, "start", "elapsedMillis", True),
                                         (0, "start", "epochMillis", readback.LONG_MAX + 1)):
            with self.subTest(index=index, edge=edge, clock=clock):
                data = packet(); data["events"][index][edge][clock] = value
                self.assert_hold(checked(data), readback.Hold.CLOCK_RECORD)
        data = packet(); data["events"][0]["start"]["timezone"] = "UTC"
        self.assert_hold(checked(data), readback.Hold.CLOCK_RECORD)

    def test_consistent_fabricated_input_still_cannot_qualify_actual_profile(self):
        data = packet(); expected = binding()
        expected["profileSha256"] = "a" * 64
        data["binding"] = deepcopy(expected)
        for event in data["events"]:
            event["binding"] = deepcopy(expected)
        result = checked(data, expected)
        self.assertEqual(result.classification, "MATCHING_DECLARED_TRUE")
        self.assert_unqualified(result)
        # A syntactically matching hash/token is a reference, not verification.
        self.assertFalse(hasattr(result, "accepted"))


if __name__ == "__main__":
    unittest.main()
