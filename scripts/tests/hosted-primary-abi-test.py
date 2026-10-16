#!/usr/bin/env python3
"""Offline byte/task controls only. Public baselines are synthetic fixture inputs.

No generated production dump, native library, Gradle, Git child, network, GPG or
hosted execution is performed. These tests cannot qualify the actual FULL ABI.
"""
from __future__ import annotations

import ast
import copy
import io
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_primary_abi as A


class AbiBytesAndTasks(unittest.TestCase):
    def setUp(self):
        self.generated = {index: (ROOT / path).read_bytes() for index, path in enumerate(A.BASELINES)}
        self.references = {index: (A.blob(raw), raw) for index, raw in self.generated.items()}
        self.lines = [b"> Task " + name.encode("ascii") for name in A.FRESH_TASKS]
        self.log = self.observe()

    def observe(self, lines=None):
        raw = b"\n".join(self.lines if lines is None else lines) + b"\n"
        return A.observe_log(io.BytesIO(raw), len(raw), lambda: None)

    def assess(self, generated=None, references=None, log=None):
        return A.assess(self.generated if generated is None else generated,
                        self.references if references is None else references, self.log if log is None else log)

    def test_eight_separate_routes_and_six_generated_roots(self):
        self.assertEqual(len(A.ROUTES), 8)
        self.assertEqual(len(set(A.BASELINES)), 8)
        self.assertEqual(len(set(A.GENERATED)), 8)
        self.assertEqual(len(set(path.rsplit("/", 1)[0].removesuffix("/jvm") for path in A.GENERATED)), 6)
        result = self.assess()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["errors"], [])
        self.assertTrue(all(row["equal"] for row in result["routes"]))
        self.assertEqual(result["androidOnlyBuiltIn"]["classification"], "NO_SUPPORTED_DUMP")
        self.assertFalse(result["androidOnlyBuiltIn"]["replacesCustomAndroidChecks"])
        for row in result["routes"]:
            self.assertNotEqual(row["baseline"]["member"], row["generated"]["member"])

    def test_all_eight_omissions_remain_missing_despite_matching_references(self):
        for index in range(8):
            with self.subTest(index=index):
                generated = {**self.generated, index: None}
                result = self.assess(generated=generated)
                self.assertEqual(result["status"], "HOLD")
                self.assertIsNone(result["routes"][index]["generated"])
                self.assertFalse(result["routes"][index]["equal"])

    def test_all_eight_substitutions_or_same_size_mutations_fail(self):
        for index in range(8):
            for raw in (self.generated[(index + 1) % 8], b"!" + self.generated[index][1:]):
                with self.subTest(index=index, size=len(raw)):
                    self.assertEqual(self.assess(generated={**self.generated, index: raw})["status"], "HOLD")

    def test_role_addition_omission_or_alias_is_not_a_ninth_original(self):
        for change in ({**self.generated, 8: b"derived"}, {key: value for key, value in self.generated.items() if key != 7},
                       {str(key): value for key, value in self.generated.items()}):
            with self.subTest(keys=list(change)), self.assertRaisesRegex(A.AbiError, "ABI_ROLE_SET"):
                self.assess(generated=change)

    def test_reference_size_git_blob_and_generated_bounds_are_independent(self):
        for reference in (("a" * 40, self.generated[0]), ("a" * 40, b""), ("a" * 40, b"x" * (A.FILE_LIMIT + 1))):
            with self.subTest(size=len(reference[1])), self.assertRaises(A.AbiError):
                self.assess(references={**self.references, 0: reference})
        for raw in (b"", b"x" * (A.FILE_LIMIT + 1), bytearray(b"mutable"), True):
            with self.subTest(type=type(raw)), self.assertRaisesRegex(A.AbiError, "ABI_BYTE_BOUND"):
                self.assess(generated={**self.generated, 0: raw})

    def test_exact_32_fresh_roster_and_current_driver_flags(self):
        self.assertEqual(len(A.FRESH_TASKS), 32)
        self.assertEqual(len(set(A.FRESH_TASKS)), 32)
        self.assertEqual(A.FRESH_TASKS[-2:], (":p2p-network-provisioning-android:internalDumpKotlinAbi",
                                            ":p2p-network-provisioning-android:checkKotlinAbi"))
        parsed = ast.parse((ROOT / "scripts/run-platform-tests.py").read_bytes())
        values = {node.targets[0].id: ast.literal_eval(node.value) for node in parsed.body
                  if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and
                  node.targets[0].id in ("FLAGS", "PROFILES")}
        self.assertEqual(tuple(values["FLAGS"]), A.FLAGS)
        self.assertEqual(values["PROFILES"]["full"], ["check"])

    def test_each_of_32_missing_events_is_not_fresh(self):
        for index in range(32):
            with self.subTest(task=A.FRESH_TASKS[index]):
                result = self.assess(log=self.observe(self.lines[:index] + self.lines[index + 1:]))
                self.assertIn("ABI_TASK_NOT_FRESH:" + A.FRESH_TASKS[index], result["errors"])

    def test_each_of_32_duplicate_events_is_not_fresh(self):
        for line in self.lines:
            with self.subTest(task=line):
                self.assertEqual(self.assess(log=self.observe([*self.lines, line]))["status"], "HOLD")

    def test_each_of_32_suffixed_or_malformed_events_is_not_fresh(self):
        for index in range(32):
            for suffix in (b" FAILED", b" SKIPPED", b" NO-SOURCE", b" UP-TO-DATE", b" FROM-CACHE", b" "):
                with self.subTest(task=A.FRESH_TASKS[index], suffix=suffix):
                    lines = self.lines.copy()
                    lines[index] += suffix
                    self.assertEqual(self.assess(log=self.observe(lines))["status"], "HOLD")
            lines = self.lines.copy()
            lines[index] = b" " + lines[index]
            self.assertEqual(self.assess(log=self.observe(lines))["status"], "HOLD")

    def test_android_only_builtin_execution_cannot_replace_custom_checks(self):
        lines = [line for line in self.lines if not any(task in line for task in
                 (b":buildAndroidAbi", b":checkAndroidAbi", b":checkAndroidPublicConstants"))]
        result = self.assess(log=self.observe(lines))
        self.assertEqual(result["status"], "HOLD")
        self.assertEqual(len(result["errors"]), 9)

    def test_unrelated_tasks_do_not_invent_or_duplicate_a_required_event(self):
        lines = [b"log mentions :p2p-core:checkKotlinAbi", b"> Task :other:check", *self.lines,
                 b"> Task :p2p-core:checkKotlinAbiSibling", b"> Task :p2p-core:checkKotlinAbiAnother FROM-CACHE"]
        self.assertEqual(self.assess(log=self.observe(lines))["status"], "PASS")

    def test_crlf_framing_does_not_normalize_original_log_hash(self):
        raw = b"\r\n".join(self.lines) + b"\r\n"
        result = A.observe_log(io.BytesIO(raw), len(raw), lambda: None)
        self.assertEqual(result["sha256"], A.digest(raw))
        self.assertNotEqual(result["sha256"], self.log["sha256"])
        self.assertEqual(self.assess(log=result)["status"], "PASS")

    def test_each_final_task_event_requires_complete_lf_or_crlf_framing(self):
        for index in range(32):
            for ending in (b"", b"\r"):
                with self.subTest(task=A.FRESH_TASKS[index], ending=ending):
                    lines = self.lines[:index] + self.lines[index + 1:] + [self.lines[index]]
                    raw = b"\n".join(lines) + ending
                    log = A.observe_log(io.BytesIO(raw), len(raw), lambda: None)
                    result = self.assess(log=log)
                    self.assertEqual(result["status"], "HOLD")
                    self.assertEqual(result["errors"], ["ABI_TASK_NOT_FRESH:" + A.FRESH_TASKS[index]])

    def test_non_task_trailing_text_cannot_create_a_task_but_preserves_original_hash(self):
        raw = b"\n".join(self.lines) + b"\nordinary trailing output"
        result = A.observe_log(io.BytesIO(raw), len(raw), lambda: None)
        self.assertEqual(result["sha256"], A.digest(raw))
        self.assertEqual(self.assess(log=result)["status"], "PASS")

    def test_streaming_accepts_original_log_above_json_record_bound(self):
        raw = (b"quiet " * 500 + b"\n") * 1500 + b"\n".join(self.lines) + b"\n"
        self.assertGreater(len(raw), 4 * A.MIB)
        class BoundedReader(io.BytesIO):
            def read(self, size=-1):
                if not 0 < size <= 64 * 1024:
                    raise AssertionError("Log must remain streaming, not a read-all JSON record")
                return super().read(size)
        observed = A.observe_log(BoundedReader(raw), len(raw), lambda: None)
        self.assertEqual(observed["sha256"], A.digest(raw))
        self.assertEqual(self.assess(log=observed)["status"], "PASS")

    def test_log_growth_truncation_excess_line_or_event_count_fails(self):
        for raw, size in ((b"abc", 2), (b"abc", 4), (b"x" * (A.LINE_LIMIT + 1), A.LINE_LIMIT + 1),
                          ((self.lines[0] + b"\n") * 129, len(self.lines[0] + b"\n") * 129)):
            with self.subTest(size=size), self.assertRaises(A.AbiError):
                A.observe_log(io.BytesIO(raw), size, lambda: None)
        for size in (True, -1, A.LOG_LIMIT + 1):
            with self.assertRaisesRegex(A.AbiError, "ABI_LOG_BOUND"):
                A.observe_log(io.BytesIO(b""), size, lambda: None)

    def test_callback_failure_propagates_without_timeout_or_retry(self):
        error = KeyboardInterrupt("offline cancellation marker")
        def cancelled():
            raise error
        with self.assertRaises(KeyboardInterrupt) as seen:
            A.observe_log(io.BytesIO(b""), 0, cancelled)
        self.assertIs(seen.exception, error)

    def test_tampered_task_roster_or_boolean_outcome_cannot_label_a_pass(self):
        for change in (None, {}, [], True, [{"line": True, "outcome": "EXECUTED"}],
                       [{"line": 1, "outcome": True}], [{"line": 1, "outcome": "EXECUTED", "extra": True}]):
            value = copy.deepcopy(self.log)
            value["tasks"][0]["observations"] = change
            self.assertEqual(self.assess(log=value)["status"], "HOLD")
        value = copy.deepcopy(self.log)
        value["tasks"].pop()
        with self.assertRaisesRegex(A.AbiError, "ABI_TASK_SET"):
            self.assess(log=value)

    def test_exact_additive_generated_preimage_not_a_token_count(self):
        result = A.additive(self.generated[7])
        self.assertEqual(result, {"status": "PASS", "generatedBytes": 6176,
            "generatedSha256": "b65028bae83c1046bc4a145000ed1b0dae6aa9dd5d9a615ea03b60e5963579a0",
            "factoryLineSha256": "85dda4d27550c1503b061654f2f1907a4ffb1d62763e310249609e5b8694fea7",
            "completeLineOccurrences": 1,
            "preimageSha256": "4d849ded7bfa892236706c499b0692d8fde6f243e91469f4745b840d2692c77c"})

    def test_additive_missing_duplicate_whitespace_comment_or_unrelated_mutation_fails(self):
        raw, line = self.generated[7], A.FACTORY_LINE
        mutations = [None, raw.replace(line, b""), raw + line, raw.replace(line, b" " + line),
                     raw.replace(line, line.replace(b" // ", b" /// ")), raw.replace(line, line[:-1]),
                     raw[:-1], b"!" + raw[1:], raw.replace(line, line.replace(b"FlowCollector", b"FlowCollectar"))]
        for index, changed in enumerate(mutations):
            with self.subTest(index=index):
                self.assertEqual(A.additive(changed)["status"], "HOLD")

    def test_only_closed_private_member_names_are_produced(self):
        for index, role in ((True, "generated"), (-1, "generated"), (8, "baseline"), (0, "../baseline")):
            with self.assertRaisesRegex(A.AbiError, "ABI_CLOSED_ROLE"):
                A.member(index, role)


if __name__ == "__main__":
    unittest.main(verbosity=2)
