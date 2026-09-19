#!/usr/bin/env python3
"""Pure supplied-report controls, not collection, native or workflow evidence.

Compose only the existing producer fixture SETUP and pure JSON/argv formatters;
no old test methods, canonical main/execute, source file collector or loader runs.
Large byte counts are declarations, never allocated payloads or observed files.
"""
import builtins
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_collection as C

spec = importlib.util.spec_from_file_location("collection_producer_fixtures", ROOT / "scripts/tests/hosted-cache-bootstrap-producer-test.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)


def encoded(value, *, pretty=True):
    options = {"indent": 2} if pretty else {"separators": (",", ":")}
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, **options) + "\n").encode("ascii")


def row(source="build/reports/problems/problems-report.html", *, changed=True, size=7):
    value = {"source": source, "sha256": C.producer.digest(b"" if size == 0 else b"example"), "bytes": size,
             "classification": "changed-since-admission" if changed else "preexisting-unchanged"}
    if changed:
        value["retained"] = "reports/" + source
    return value


class InventoryModels(unittest.TestCase):
    def setUp(self):
        self.fixture = F.ProducerModels()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def inputs(self, rows=(), *, pretty=True, manifest=None, receipt=None, **changes):
        original = copy.deepcopy(self.fixture.receipt if receipt is None else receipt)
        original["reports"] = copy.deepcopy(list(rows))
        document = {"schema": 1, "records": copy.deepcopy(list(rows)),
                    "limitation": "Changed bytes are not proof of test execution; use the unchanged product assessor."}
        values = {"request_raw": self.fixture.request_raw, "admitted_raw": self.fixture.admitted_raw,
                  "canonical_raw": self.fixture.canonical_raw, "start_raw": self.fixture.start_raw,
                  "receipt_raw": encoded(original, pretty=pretty),
                  "manifest_raw": encoded(document if manifest is None else manifest, pretty=pretty),
                  "original_exit_code": 0}
        values.update(changes)
        return values

    def value(self, rows=(), **changes):
        return json.loads(C.describe_inventory(**self.inputs(rows, **changes)))

    def refuse(self, values, reason=None):
        with self.assertRaisesRegex(C.CollectionError, reason or "^BOOTSTRAP_COLLECTION_"):
            C.describe_inventory(**values)

    def test_empty_reports_still_require_four_unread_logs_and_no_authority(self):
        value = self.value()
        self.assertEqual(value["schema"], 1)
        self.assertEqual(value["scope"], "BOOTSTRAP_CONFIGURATION_REPORT_INVENTORY_V1")
        self.assertEqual(value["counts"], {"reports": 0, "changedReports": 0, "preexistingReports": 0,
            "declaredReportBytes": 0, "declaredRetainedReportBytes": 0, "minimumDeclaredArchiveEntries": 0})
        self.assertEqual(value["requiredLogs"], [{"path": name, "maximumBytes": 67108864, "observation": "NOT_READ"}
            for name in ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log")])
        self.assertEqual(value["retainedReports"], [])
        self.assertEqual(value["payloadByteCeilingExcludingMetadata"], 268435456)
        self.assertEqual({key: value[key] for key in ("inputProvenance", "collectionState", "noLoaderObservation",
            "actualArchiveEntryCount", "enclosingNativeRetirement", "producerScope", "dependencyPopulation",
            "budgetAcceptance", "testAcceptance", "nextPhaseAuthority", "exportSaveAuthority")}, {
                "inputProvenance": "SUPPLIED_RECORDS_ONLY", "collectionState": "NOT_PERFORMED",
                "noLoaderObservation": "NOT_OBSERVED", "actualArchiveEntryCount": "NOT_OBSERVED",
                "enclosingNativeRetirement": "NOT_OBSERVED_HERE",
                "producerScope": "CONFIGURATION_ONLY_NOT_COMPLETE_DEPENDENCIES_OR_TESTS",
                "dependencyPopulation": "NOT_ATTESTED", "budgetAcceptance": "NOT_ADMITTED",
                "testAcceptance": "NOT_PERFORMED", "nextPhaseAuthority": False, "exportSaveAuthority": False})

    def test_mixed_inventory_preserves_classification_without_following_unchanged_sources(self):
        rows = [row("build/reports/a.txt", changed=False), row("build/reports/sub/b.html"),
                row("build/test-results/test/TEST-c.xml", size=0)]
        value = self.value(rows)
        self.assertEqual(value["declaredReports"], rows)
        self.assertEqual(value["counts"], {"reports": 3, "changedReports": 2, "preexistingReports": 1,
            "declaredReportBytes": 14, "declaredRetainedReportBytes": 7, "minimumDeclaredArchiveEntries": 7})
        self.assertEqual(value["retainedReports"], [{"path": item["retained"], "bytes": item["bytes"], "sha256": item["sha256"]}
                                                 for item in rows[1:]])

    def test_fixed_help_output_root_families_and_portable_report_names(self):
        sources = ("build/reports/.config.json", "buildSrc/build/test-results/test/TEST-A$Nested (1).xml",
            "library/p2p-core/build/reports/tests/Test_a+b.html", "samples/iosApp/build/reports/some-name.js")
        value = self.value([row(source) for source in sources])
        self.assertEqual(value["counts"]["reports"], 4)
        self.assertEqual([item["path"] for item in value["retainedReports"]], ["reports/" + source for source in sources])

    def test_six_modeled_cohorts_remain_separate_from_any_native_acceptance(self):
        for selection in F.I.SELECTIONS:
            with self.subTest(selection=selection[0]):
                self.fixture.configure(selection)
                value = self.value([row()])
                self.assertEqual(value["binding"]["requestSha256"], C.producer.digest(self.fixture.request_raw))
                self.assertEqual(value["enclosingNativeRetirement"], "NOT_OBSERVED_HERE")
                self.assertIs(value["exportSaveAuthority"], False)

    def test_exact_pretty_original_hashes_and_byte_counts_are_not_compact_rewrites(self):
        values = self.inputs([row()])
        value = json.loads(C.describe_inventory(**values))
        for name, key, binding in (("start.json", "start_raw", "startSha256"),
                ("receipt.json", "receipt_raw", "receiptSha256"), ("report-manifest.json", "manifest_raw", "manifestSha256")):
            self.assertNotEqual(values[key], encoded(json.loads(values[key]), pretty=False))
            self.assertEqual(value["binding"][binding], C.producer.digest(values[key]))
            self.assertIn({"path": name, "bytes": len(values[key]), "sha256": C.producer.digest(values[key])},
                          value["requiredMetadata"])
        observed = C.producer.observe_canonical(**{key: item for key, item in values.items() if key != "manifest_raw"})
        self.assertEqual(value["binding"]["canonicalObservationSha256"], C.producer.digest(C.producer.encoded(observed)))

    def test_equivalent_manifest_reserialization_cannot_validate_old_inventory(self):
        values = self.inputs([row()])
        raw = C.describe_inventory(**values)
        values["manifest_raw"] = encoded(json.loads(values["manifest_raw"]), pretty=False)
        replacement = C.describe_inventory(**values)
        self.assertNotEqual(raw, replacement)
        with self.assertRaisesRegex(C.CollectionError, "INVENTORY_CHANGED"):
            C.validate_inventory(raw, **values)

    def test_every_input_requires_exact_bounded_nonempty_bytes(self):
        class Subclass(bytes):
            pass
        for key in ("request_raw", "admitted_raw", "canonical_raw", "start_raw", "receipt_raw", "manifest_raw"):
            for raw in (None, "{}", bytearray(b"{}"), Subclass(b"{}"), b"", b" " * (4194304 + 1)):
                with self.subTest(key=key, kind=type(raw).__name__):
                    self.refuse(self.inputs(**{key: raw}), "METADATA_BYTES")

    def test_manifest_metadata_exact_limit_and_one_byte_over(self):
        values = self.inputs()
        values["manifest_raw"] += b" " * (4194304 - len(values["manifest_raw"]))
        self.assertEqual(json.loads(C.describe_inventory(**values))["requiredMetadata"][2]["bytes"], 4194304)
        values["manifest_raw"] += b" "
        self.refuse(values, "METADATA_BYTES")

    def test_manifest_top_level_shape_schema_and_limitation_are_closed(self):
        base = json.loads(self.inputs()["manifest_raw"])
        alternatives = ([], {**base, "schema": True}, {**base, "schema": 1.0}, {**base, "schema": 2},
                        {**base, "limitation": "tests passed"}, {**base, "authority": True}, {"schema": 1, "records": []})
        for value in alternatives:
            with self.subTest(value=value):
                self.refuse(self.inputs(manifest=value))

    def test_duplicate_fields_trailing_json_and_nonfinite_manifest_are_refused(self):
        values = self.inputs([row()])
        for raw in (values["manifest_raw"].replace(b'"schema": 1', b'"schema": 1,"schema": 1'),
                    values["manifest_raw"] + b"{}", values["manifest_raw"][:-4],
                    values["manifest_raw"].replace(b'"bytes": 7', b'"bytes": NaN'),
                    values["manifest_raw"].replace(b'"bytes": 7', b'"bytes": 7,"bytes": 7')):
            with self.subTest(raw=raw[:24]):
                self.refuse({**values, "manifest_raw": raw})

    def test_manifest_utf16_utf32_bom_and_invalid_utf8_are_not_reinterpreted(self):
        values = self.inputs()
        text = values["manifest_raw"].decode()
        for raw in (text.encode("utf-16"), text.encode("utf-16-le"), text.encode("utf-32"),
                    b"\xef\xbb\xbf" + values["manifest_raw"], values["manifest_raw"] + b"\xff", b"{\0}"):
            with self.subTest(raw=raw[:12]):
                self.refuse({**values, "manifest_raw": raw})

    def test_report_roster_requires_list_with_twenty_thousand_upper_bound(self):
        for records in (None, {}, True, "[]", [row()] * 20001):
            manifest = {"schema": 1, "records": records, "limitation": C.LIMITATION}
            with self.subTest(kind=type(records).__name__):
                values = self.inputs(manifest=manifest, pretty=False)
                # Use unchanged rows here to keep the adverse JSON below4MiB.
                if isinstance(records, list):
                    manifest["records"] = [row("build/reports/x", changed=False, size=0)] * 20001
                    values = self.inputs(manifest=manifest, pretty=False)
                self.assertLess(len(values["manifest_raw"]), 4194304)
                self.refuse(values, "REPORT_ROSTER")

    def test_report_rows_have_exact_classification_dependent_fields(self):
        for item in ([], None, {}, {**row(), "extra": True}, {**row(), "classification": "PASS"},
                     {**row(), "classification": True}, {**row(changed=False), "retained": "reports/build/reports/x"},
                     {key: value for key, value in row().items() if key != "retained"}):
            with self.subTest(item=item):
                self.refuse(self.inputs([item]))

    def test_report_sizes_are_exact_nonnegative_integers_bounded_per_file(self):
        for size in (True, False, "7", None, -1, 7.0, 536870913):
            with self.subTest(size=size):
                self.refuse(self.inputs([{**row(), "bytes": size}]), "REPORT_SIZE")

    def test_report_hashes_are_exact_lowercase_sha256_and_empty_digest_is_consistent(self):
        for sha in (None, True, 64, "a" * 63, "a" * 65, "A" * 64, "g" * 64, "a" * 64 + "\n"):
            with self.subTest(sha=sha):
                self.refuse(self.inputs([{**row(), "sha256": sha}]), "REPORT_SHA256")
        self.refuse(self.inputs([{**row(size=0), "sha256": "a" * 64}]), "EMPTY_REPORT_DIGEST")
        self.assertEqual(self.value([row(size=0)])["counts"]["declaredReportBytes"], 0)

    def test_aggregate_includes_unchanged_reports_at_original_512mib_limit(self):
        rows = [row("build/reports/a", changed=False, size=536870912), row("build/reports/b", size=0)]
        self.assertEqual(self.value(rows)["counts"]["declaredReportBytes"], 536870912)
        rows[1] = row("build/reports/b", size=1)
        self.refuse(self.inputs(rows), "REPORT_BYTES")

    def test_declared_maximum_payload_exceeds_snapshot_without_becoming_observed_bytes(self):
        value = self.value([row(size=536870912)])
        self.assertEqual(value["payloadByteCeilingExcludingMetadata"], 805306368)
        self.assertGreater(value["payloadByteCeilingExcludingMetadata"], 603979776)
        self.assertEqual(value["collectionState"], "NOT_PERFORMED")
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")

    def test_source_order_and_exact_duplicates_are_refused(self):
        for rows in ([row("build/reports/z"), row("build/reports/a")], [row(), row()]):
            self.refuse(self.inputs(rows), "REPORT_ORDER")

    def test_case_aliases_in_files_and_ancestors_are_refused(self):
        alternatives = (("build/reports/A", "build/reports/a"),
                        ("build/reports/Dir/a", "build/reports/dir/b"),
                        ("library/Core/build/reports/a", "library/core/build/reports/b"))
        for sources in alternatives:
            with self.subTest(sources=sources):
                self.refuse(self.inputs([row(source) for source in sorted(sources)]), "REPORT_ALIAS")

    def test_file_directory_prefix_conflicts_are_refused(self):
        self.refuse(self.inputs([row("build/reports/a"), row("build/reports/a/b")]), "REPORT_PREFIX")
        self.refuse(self.inputs([row("build/reports/a", changed=False), row("build/reports/a/b")]), "REPORT_PREFIX")

    def test_retained_paths_cannot_escape_or_relabel_original_source(self):
        for path in (None, True, "build/reports/problems/problems-report.html", "reports/../outside",
                     "reports/build/reports/other.html", "/reports/build/reports/problems/problems-report.html",
                     "reports\\build\\reports\\problems\\problems-report.html"):
            with self.subTest(path=path):
                self.refuse(self.inputs([{**row(), "retained": path}]), "RETAINED_PATH")

    def test_absolute_traversal_backslash_empty_and_drive_components_are_refused(self):
        sources = ("/build/reports/a", "build//reports/a", "build/reports/../a", "build/reports/./a",
            "build/reports/a/", "build\\reports\\a", "C:/build/reports/a", "//server/build/reports/a", "",
            "build/reports/a\0b", "build/reports/a\nb", "build/reports/a\x7fb", "build/reports/\u00e9.html")
        for source in sources:
            with self.subTest(source=source):
                self.refuse(self.inputs([row(source)]))

    def test_windows_device_names_punctuation_and_trailing_dots_spaces_are_refused(self):
        for name in ("CON", "con.xml", "LPT1", "COM9.txt", "CONIN$", "CONOUT$.txt", "CLOCK$",
                     "name.", "name ", "na:me", "na*me", "na?me", 'na"me', "na<me", "na>me", "na|me"):
            with self.subTest(name=name):
                self.refuse(self.inputs([row("build/reports/" + name)]))

    def test_reserved_device_stems_with_spaces_before_extensions_are_refused(self):
        for name in ("CON .txt", "nul  .xml", "AUX .log", "COM1  .xml", "lpt9 .html",
                     "CONIN$ .txt", "CONOUT$  .log", "CLOCK$ .json"):
            with self.subTest(name=name):
                self.refuse(self.inputs([row("build/reports/" + name)]), "REPORT_DEVICE")
        self.assertEqual(self.value([row("build/reports/COM10 .xml")])["counts"]["reports"], 1)

    def test_external_unknown_nested_and_nonreport_roots_are_refused(self):
        for source in ("external/fixture/build/reports/a", "gradle/reports/a", "build/a", "build/reports",
                       "buildSrc/reports/a", "library/build/reports/a", "library/x/nested/build/reports/a",
                       "samples/x/build/classes/a.class", "Build/reports/a"):
            with self.subTest(source=source):
                self.refuse(self.inputs([row(source)]), "REPORT_ROOT")

    def test_component_source_and_report_depth_boundaries(self):
        self.assertEqual(self.value([row("build/reports/" + "a" * 255)])["counts"]["reports"], 1)
        self.refuse(self.inputs([row("build/reports/" + "a" * 256)]), "REPORT_COMPONENT")
        source = "build/reports/" + "/".join(["a" * 255] * 15 + ["a" * 242])
        self.assertEqual(len(source), 4096)
        self.assertEqual(self.value([row(source)])["counts"]["reports"], 1)
        self.refuse(self.inputs([row(source + "a")]), "REPORT_SOURCE")
        self.assertEqual(self.value([row("build/reports/" + "d/" * 256 + "x")])["counts"]["minimumDeclaredArchiveEntries"], 258)
        self.refuse(self.inputs([row("build/reports/" + "d/" * 257 + "x")]), "REPORT_DEPTH")

    def test_minimum_archive_members_count_roots_and_shared_directories_not_source_ancestors(self):
        rows = [row("build/reports/sub/a"), row("build/reports/sub/b"),
                row("buildSrc/build/reports/x"), row("library/core/build/test-results/test/z.xml")]
        value = self.value(rows)
        self.assertEqual(value["counts"]["minimumDeclaredArchiveEntries"], 9)
        self.assertEqual(value["actualArchiveEntryCount"], "NOT_OBSERVED")

    def test_minimum_member_limit_is_inclusive_and_counts_the_report_root(self):
        rows = [row("build/reports/" + format(index, "05d"), changed=False, size=0) for index in range(19999)]
        values = self.inputs(rows, pretty=False)
        self.assertLess(len(values["manifest_raw"]), 4194304)
        value = json.loads(C.describe_inventory(**values))
        self.assertEqual(value["counts"]["minimumDeclaredArchiveEntries"], 20000)
        self.assertEqual(value["counts"]["reports"], 19999)
        rows.append(row("build/reports/19999", changed=False, size=0))
        self.refuse(self.inputs(rows, pretty=False), "REPORT_ENTRIES")

    def test_manifest_receipt_rows_match_typed_values_not_python_boolean_equality(self):
        values = self.inputs([row(size=1)])
        receipt = json.loads(values["receipt_raw"])
        for change in ({"bytes": True}, {"bytes": 1.0}, {"sha256": "e" * 64}, {"retained": "reports/build/reports/else"}):
            updated = copy.deepcopy(receipt)
            updated["reports"][0].update(change)
            with self.subTest(change=change):
                self.refuse({**values, "receipt_raw": encoded(updated)}, "RECEIPT_REPORTS_CHANGED")

    def test_manifest_receipt_list_order_missing_and_extra_rows_are_refused(self):
        values = self.inputs([row("build/reports/a"), row("build/reports/b")])
        receipt = json.loads(values["receipt_raw"])
        for reports in ([], receipt["reports"][:1], receipt["reports"][::-1], receipt["reports"] * 2):
            with self.subTest(count=len(reports)):
                self.refuse({**values, "receipt_raw": encoded({**receipt, "reports": reports})}, "RECEIPT_REPORTS_CHANGED")

    def test_original_request_and_source_binding_are_checked_before_inventory(self):
        request = copy.deepcopy(self.fixture.request)
        for change in ({"requestedArgv": ["check"]}, {"timeout": 5400}, {"testAcceptance": "PASS"}):
            with self.subTest(change=change), self.assertRaises(C.producer.ProducerError):
                C.describe_inventory(**self.inputs(request_raw=encoded({**request, **change}, pretty=False)))
        context = copy.deepcopy(self.fixture.context)
        context["source"]["commit"] = "f" * 40
        with self.assertRaises(C.producer.ProducerError):
            C.describe_inventory(**self.inputs(canonical_raw=encoded(context)))

    def test_supplied_exit_failure_and_reported_stop_failure_cannot_be_promoted(self):
        for code in (None, True, False, "0", 1, 125):
            with self.subTest(code=code), self.assertRaises(C.producer.ProducerError):
                C.describe_inventory(**self.inputs(original_exit_code=code))
        receipt = copy.deepcopy(self.fixture.receipt)
        receipt["stopExitCode"] = 1
        with self.assertRaises(C.producer.ProducerError):
            C.describe_inventory(**self.inputs(receipt=receipt))

    def test_inventory_validation_rederives_exact_bytes_and_refuses_authority_upgrade(self):
        values = self.inputs([row()])
        raw = C.describe_inventory(**values)
        self.assertIs(C.validate_inventory(raw, **values), raw)
        value = json.loads(raw)
        for change in ({"exportSaveAuthority": True}, {"collectionState": "RETAINED"},
                       {"budgetAcceptance": "ADMITTED"}, {"nextPhaseAuthority": True}, {"extra": False}):
            with self.subTest(change=change), self.assertRaisesRegex(C.CollectionError, "INVENTORY_CHANGED"):
                C.validate_inventory(encoded({**value, **change}, pretty=False), **values)
        for changed in (encoded(value), raw + b" "):
            with self.assertRaisesRegex(C.CollectionError, "INVENTORY_CHANGED"):
                C.validate_inventory(changed, **values)

    def test_inventory_validation_requires_exact_nonempty_bounded_bytes(self):
        class Subclass(bytes):
            pass
        values = self.inputs()
        for raw in (None, "{}", bytearray(b"{}"), Subclass(b"{}"), b"", b" " * (4194304 + 1)):
            with self.subTest(kind=type(raw).__name__), self.assertRaisesRegex(C.CollectionError, "METADATA_BYTES"):
                C.validate_inventory(raw, **values)

    def test_inventory_expansion_over_four_mib_refuses_bounded_original_inputs(self):
        rows = [row("build/reports/" + format(index, "05d") + "-" + "x" * 200, size=0) for index in range(5500)]
        values = self.inputs(rows, pretty=False)
        for name, raw in values.items():
            if name.endswith("_raw"):
                self.assertLess(len(raw), 4194304)
        self.refuse(values, "METADATA_(ENCODING|BYTES)")

    def test_deep_malformed_manifest_refuses_with_finite_error(self):
        # Unbalanced JSON, independent of an interpreter's recursion ceiling.
        raw = b'{"schema":1,"records":' + b"[" * 1200 + b"0" + b"]" * 1199 + b"}"
        self.refuse(self.inputs(manifest_raw=raw), "MANIFEST_JSON")

    def test_public_inventory_operations_need_no_file_clock_or_process_operation(self):
        values = self.inputs([row()])
        def forbidden(*_args, **_kwargs):
            raise AssertionError("UNEXPECTED_INVENTORY_IO")
        with patch.object(builtins, "open", forbidden), patch.object(os, "open", forbidden), \
             patch.object(os, "stat", forbidden), patch.object(os, "lstat", forbidden), \
             patch.object(os, "scandir", forbidden), patch.object(os, "listdir", forbidden), \
             patch.object(Path, "open", forbidden), patch.object(Path, "stat", forbidden), \
             patch.object(Path, "resolve", forbidden), patch.object(time, "monotonic", forbidden), \
             patch.object(time, "monotonic_ns", forbidden), patch.object(time, "time", forbidden), \
             patch.object(time, "time_ns", forbidden), patch.object(time, "perf_counter", forbidden), \
             patch.object(time, "perf_counter_ns", forbidden):
            raw = C.describe_inventory(**values)
            self.assertEqual(C.validate_inventory(raw, **values), raw)

    def test_inventory_errors_do_not_echo_private_input_and_output_has_no_log_hash_claim(self):
        sentinel = "private-inventory-sentinel"
        values = self.inputs([row("outside/" + sentinel)])
        try:
            C.describe_inventory(**values)
        except C.CollectionError as error:
            self.assertNotIn(sentinel, str(error))
            self.assertRegex(str(error), r"^BOOTSTRAP_COLLECTION_[A-Z_]+$")
        else:
            self.fail("unsafe source accepted")
        for log in self.value()["requiredLogs"]:
            self.assertEqual(set(log), {"path", "maximumBytes", "observation"})
        self.assertEqual((C.METADATA_BYTES, C.REPORT_BYTES, C.REPORT_ENTRIES, C.LOG_BYTES),
                         (4194304, 536870912, 20000, 67108864))


if __name__ == "__main__":
    unittest.main()
