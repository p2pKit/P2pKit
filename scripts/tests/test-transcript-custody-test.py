#!/usr/bin/env python3
"""Offline custody controls. Synthetic XML/owners are NOT runtime evidence."""

import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("custody", ROOT / "scripts/test-transcript-custody.py")
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
SOURCE = {"commit": "1" * 40, "tree": "2" * 40, "status": "", "diffSha256": C.digest(b"")}


def native_trace(root, invocation="3" * 32):
    return {"backend": "darwin-libproc-audit-token", "scope": "controlled-marker-inheriting-descendants",
            "job": "4" * 32, "invocation": invocation, "discoveryErrors": [],
            "startedIdentities": [{"synthetic": True}], "launches": [{"cwd": str(root)}]}


class CustodyTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-custody-control-")
        self.base = Path(self.temporary.name).resolve()
        self.root, self.state = self.base / "source", self.base / "state"
        self.root.mkdir()
        self.state.mkdir()
        self.home = self.state / "gradle-home"
        self.home.mkdir()
        self.directory = self.state / "custody"
        (self.state / "context.json").write_bytes(C.encoded(
            {"id": "4" * 32, "source": SOURCE, "root": str(self.root), "gradleHome": str(self.home)}))
        for name in (C.INIT, "scripts/test-transcript-custody.py", *(suite["source"] for suite in C.SUITES.values())):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((ROOT / name).read_bytes())
        self.source_patch = patch.object(C, "source", return_value=copy.deepcopy(SOURCE))
        self.source_patch.start()
        self.command = [":p2p-sample-desktop:test", ":p2p-sample-diagnostics:test"]

    def tearDown(self):
        self.source_patch.stop()
        self.temporary.cleanup()  # Only this control's wholly synthetic data.

    def prepare(self, kind="audit", scopes=None):
        return C.prepare(self.root, self.directory, self.home, self.state, kind,
                         scopes or ["cli", "diagnostics"], self.command, "4" * 32 if kind == "writer" else None)

    def xml(self, scope):
        suite = C.SUITES[scope]
        xml = ET.Element("testsuite", name=suite["class"], tests=str(suite["count"]),
                         failures="0", errors="0", skipped="0")
        for name in C.methods(self.root, scope):
            ET.SubElement(xml, "testcase", name=name + "()", classname=suite["class"])
        data = b"synthetic\r\n\x00\xff"
        ET.SubElement(xml, "system-out").text = "\n".join(
            f"{suite['prefix']} {key} bytes={len(data)} base64={base64.b64encode(data).decode()}"
            for key in suite["records"])
        return xml

    def observations(self, request):
        request_hash = C.digest((self.directory / "request.json").read_bytes())
        for scope, entry in request["roots"].items():
            event = {"schema": 1, "token": request["token"], "requestSha256": request_hash,
                     "task": f":{C.SUITES[scope]['project']}:test", "temporary": entry["path"],
                     "ownerDomain": C.product_domain(request)}
            (self.directory / "events" / f"{scope}-start.json").write_bytes(C.encoded(event))
            (self.directory / "events" / f"{scope}-finish.json").write_bytes(
                C.encoded({**event, "executed": True, "failed": False}))
            report = C.report_path(self.root, C.SUITES[scope])
            report.parent.mkdir(parents=True)
            report.write_bytes(ET.tostring(self.xml(scope)))

    def owner(self, request=None):
        invocation = request["owner"]["productInvocation"] if request else "3" * 32
        evidence = self.state / "evidence" / invocation
        evidence.mkdir(parents=True)
        path = evidence / "receipt.json"
        owner = {"schema": 1, "id": invocation, "sourceBefore": SOURCE, "sourceAfter": SOURCE,
                 "sourceUnchanged": True, "cwd": str(self.root), "gradleHome": str(self.home),
                 "requestedArgv": self.command, "jobId": "4" * 32, "ownedSurvivors": [], "errors": [],
                 "ownership": native_trace(self.root, invocation), "productExitCode": 0, "stopExitCode": 0,
                 "finalExitCode": 0}
        path.write_bytes(C.encoded(owner))
        return path, owner

    def ready(self):
        request = self.prepare()
        self.observations(request)
        path, owner = self.owner(request)
        return request, path, owner

    def residual(self, scope="cli"):
        path = self.directory / "temp" / scope / "p2pkit-cli-shutdown-synthetic" / "child.log"
        path.parent.mkdir()
        path.write_bytes(b"unexported original\x00\xff\r\n")
        return path

    def test_prepare_is_nonexecuting_and_preserves_unrelated_initializers(self):
        (self.home / "init.d").mkdir()
        sentinel = self.home / "init.d" / "unrelated.gradle"
        sentinel.write_text("preserve")
        request = self.prepare()
        self.assertEqual("preserve", sentinel.read_text())
        self.assertEqual(SOURCE, request["source"])
        self.assertEqual(request, C.check_request(self.directory)[0])
        self.assertFalse((self.directory / "result.json").exists())

    def test_success_retains_six_original_exports_without_deleting_inputs(self):
        request, path, _ = self.ready()
        result = C.collect(self.directory, path)
        self.assertEqual("RETAINED", result["result"])
        exports = [item for item in result["files"] if "record" in item]
        self.assertEqual(6, len(exports))
        self.assertEqual("KNOWN", result["retirement"])
        self.assertTrue(path.exists())
        for entry in request["roots"].values():
            self.assertTrue(Path(entry["path"]).is_dir())

    def test_existing_root_is_not_overwritten(self):
        self.directory.mkdir()
        sentinel = self.directory / "sentinel"
        sentinel.write_text("keep")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertEqual("keep", sentinel.read_text())

    def test_existing_xml_is_not_admitted_as_fresh(self):
        report = C.report_path(self.root, C.SUITES["cli"])
        report.parent.mkdir(parents=True)
        report.write_bytes(b"old")
        with self.assertRaises(ValueError):
            self.prepare()
        self.assertFalse(self.directory.exists())

    def test_dirty_source_cannot_be_prepared(self):
        with patch.object(C, "source", return_value={**SOURCE, "status": " M file"}):
            with self.assertRaises(ValueError):
                self.prepare()

    def test_home_outside_owner_is_rejected(self):
        with self.assertRaises(ValueError):
            C.prepare(self.root, self.directory, self.home, self.root, "audit", ["cli"], self.command)

    def test_changed_initializer_source_or_token_is_rejected(self):
        request = self.prepare()
        paths = [self.home / "init.d" / C.LOADER, self.root / C.INIT,
                 Path(request["roots"]["cli"]["path"]) / "owner.token"]
        for path in paths:
            with self.subTest(path=path.name):
                original = path.read_bytes()
                path.write_bytes(original + b"changed")
                with self.assertRaises(ValueError):
                    C.check_request(self.directory)
                path.write_bytes(original)

    def test_replaced_temporary_directory_is_rejected(self):
        request = self.prepare()
        path = Path(request["roots"]["cli"]["path"])
        path.rename(path.with_name("original-cli"))
        path.mkdir()
        (path / "owner.token").write_text(request["token"] + "\n")
        with self.assertRaises(ValueError):
            C.check_request(self.directory)

    def test_symlink_and_hardlink_inputs_rejected(self):
        original = self.base / "original"
        original.write_text("private")
        link = self.base / "link"
        link.symlink_to(original)
        with self.assertRaises(ValueError):
            C.read_file(link)
        link.unlink()
        os.link(original, link)
        with self.assertRaises(ValueError):
            C.read_file(link)

    def test_duplicate_json_and_oversized_input_rejected(self):
        for raw in (b'{"schema":1,"schema":1}', b'{"schema":NaN}', b"x" * (C.JSON_LIMIT + 1)):
            with self.subTest(raw=raw[:32]):
                with self.assertRaises(ValueError):
                    C.parse_json(raw)

    def test_export_validation_rejects_missing_duplicate_malformed_and_wrong_length(self):
        original = self.xml("cli")
        text = original.find("system-out").text
        wrongs = ["", text + "\n" + text.splitlines()[0], text.replace("bytes=13", "bytes=12"),
                  text.replace("base64=", "base64=!"), text.replace("benignOption=false", "benignOption=other"),
                  "prefix " + text, text + "\nPROBE_EVIDENCE_HOLD: synthetic"]
        for wrong in wrongs:
            with self.subTest(wrong=wrong[:80]):
                xml = copy.deepcopy(original)
                xml.find("system-out").text = wrong
                with self.assertRaises(ValueError):
                    C.xml_exports(ET.tostring(xml), "cli", C.methods(self.root, "cli"))

    def test_wrong_suite_methods_and_failed_skipped_classes_reject(self):
        original = self.xml("diagnostics")
        for field, value in (("name", "wrong"), ("tests", "22"), ("failures", "1"), ("skipped", "1")):
            xml = copy.deepcopy(original)
            xml.set(field, value)
            with self.assertRaises(ValueError):
                C.xml_exports(ET.tostring(xml), "diagnostics", C.methods(self.root, "diagnostics"))
        original.find("testcase").set("name", "invented()")
        with self.assertRaises(ValueError):
            C.xml_exports(ET.tostring(original), "diagnostics", C.methods(self.root, "diagnostics"))

    def test_dtd_and_non_utf8_xml_do_not_expand_entities(self):
        for raw in (b'<!DOCTYPE testsuite [<!ENTITY x "expanded">]><testsuite/>',
                    '<testsuite/>'.encode("utf-16")):
            with self.assertRaises(ValueError):
                C.xml_exports(raw, "cli", C.methods(self.root, "cli"))

    def test_missing_event_still_retains_original_xml(self):
        _, path, _ = self.ready()
        (self.directory / "events/cli-start.json").unlink()
        result = C.collect(self.directory, path)
        self.assertEqual("HOLD", result["result"])
        self.assertTrue((self.directory / "retained/cli.xml").is_file())

    def test_missing_xml_still_retains_remaining_originals_after_retirement(self):
        _, path, _ = self.ready()
        C.report_path(self.root, C.SUITES["cli"]).unlink()
        log = self.residual()
        result = C.collect(self.directory, path)
        self.assertEqual("HOLD", result["result"])
        self.assertEqual(log.read_bytes(), (self.directory / "retained/cli-remaining-0.log").read_bytes())

    def test_failed_product_preserves_primary_status_and_all_originals(self):
        _, path, owner = self.ready()
        owner.update(productExitCode=7, finalExitCode=7)
        path.write_bytes(C.encoded(owner))
        log = self.residual()
        result = C.collect(self.directory, path)
        self.assertEqual(("HOLD", "KNOWN", 7),
                         (result["result"], result["retirement"], result["productExitCode"]))
        self.assertTrue(log.exists())
        self.assertTrue((self.directory / "retained/cli-remaining-0.log").exists())

    def test_unknown_retirement_keeps_raw_in_place_and_still_retains_reports(self):
        _, path, owner = self.ready()
        owner["ownedSurvivors"] = [{"status": "UNKNOWN"}]
        path.write_bytes(C.encoded(owner))
        log = self.residual()
        result = C.collect(self.directory, path)
        self.assertEqual(("HOLD", "UNKNOWN"), (result["result"], result["retirement"]))
        self.assertTrue(log.exists())
        self.assertFalse((self.directory / "retained/cli-remaining-0.log").exists())
        self.assertTrue((self.directory / "retained/cli.xml").exists())

    def test_failed_stop_cannot_pass(self):
        _, path, owner = self.ready()
        owner.update(stopExitCode=3, finalExitCode=125)
        path.write_bytes(C.encoded(owner))
        self.assertEqual("HOLD", C.collect(self.directory, path)["result"])

    def test_wrong_owner_command_and_noncanonical_receipt_reject(self):
        request, path, owner = self.ready()
        wrong = copy.deepcopy(owner)
        wrong["requestedArgv"] = ["help"]
        with self.assertRaises(ValueError):
            C.owner_outcome(request, wrong, path)
        alias = self.state / "alias.json"
        alias.write_bytes(C.encoded(wrong))
        with self.assertRaises(ValueError):
            C.owner_outcome(request, owner, alias)

    def test_failed_original_copy_does_not_delete_input_or_suppress_other_suite(self):
        _, path, _ = self.ready()
        log = self.residual()
        actual = C.write_new
        def fail(destination, data):
            if destination.name == "cli-remaining-0.log":
                raise OSError("synthetic full disk")
            return actual(destination, data)
        with patch.object(C, "write_new", side_effect=fail):
            result = C.collect(self.directory, path)
        self.assertEqual("HOLD", result["result"])
        self.assertTrue(log.exists())
        self.assertTrue((self.directory / "retained/diagnostics.xml").exists())

    def test_unknown_listing_cannot_mean_no_remaining_files(self):
        _, path, _ = self.ready()
        with patch.object(C, "remaining_logs", side_effect=OSError("synthetic listing failure")):
            self.assertEqual("HOLD", C.collect(self.directory, path)["result"])

    def test_collection_is_one_shot(self):
        _, path, _ = self.ready()
        C.collect(self.directory, path)
        with self.assertRaises(ValueError):
            C.collect(self.directory, path)

    def test_aggregate_limit_holds_without_deleting_originals(self):
        _, path, _ = self.ready()
        with patch.object(C, "TOTAL_LIMIT", 1):
            result = C.collect(self.directory, path)
        self.assertEqual("HOLD", result["result"])
        self.assertTrue(path.exists())

    def test_mutable_snapshot_requires_both_actual_drain_records(self):
        request = self.prepare(kind="writer")
        def row(stage, command, invocation):
            return {"argv": command, "launchAttempted": True, "errors": [], "waitExitCode": 0,
                    "drains": [{"stage": stage, "survivors": [], "error": None}],
                    "ownership": native_trace(self.root, invocation)}
        owner = {"scope": "MUTABLE_FULL_WRITER_NOT_AUDIT_LEAF", "state": str(self.state), "sourceBefore": SOURCE,
                 "writer": row("product-final", self.command, request["owner"]["productInvocation"]),
                 "stop": row("stop-final", [str(self.root / "gradlew"), "--stop"], request["owner"]["stopInvocation"])}
        self.assertEqual((0, 0, None), C.owner_outcome(request, owner, None))
        for command in ("writer", "stop"):
            wrong = copy.deepcopy(owner)
            wrong[command]["drains"][0]["survivors"] = [{"status": "UNKNOWN"}]
            with self.assertRaises(ValueError):
                C.owner_outcome(request, wrong, None)
        wrong = copy.deepcopy(owner)
        wrong["writer"]["ownership"]["backend"] = "process-group-only"
        with self.assertRaises(ValueError):
            C.owner_outcome(request, wrong, None)
        for stage in ("writer", "stop"):
            for key in ("job", "invocation"):
                wrong = copy.deepcopy(owner)
                wrong[stage]["ownership"][key] = "7" * 32
                with self.subTest(stage=stage, key=key), self.assertRaises(ValueError):
                    C.owner_outcome(request, wrong, None)

    def test_stale_canonical_receipt_cannot_prove_fresh_retirement(self):
        path, _ = self.owner()  # Finalized before prepare, same source/home/argv.
        request = self.prepare()
        self.assertNotEqual("3" * 32, request["owner"]["productInvocation"])
        self.observations(request)
        log = self.residual()
        result = C.collect(self.directory, path)
        self.assertEqual(("HOLD", "UNKNOWN"), (result["result"], result["retirement"]))
        self.assertTrue(log.exists())
        self.assertFalse((self.directory / "retained/cli-remaining-0.log").exists())
        self.assertTrue((self.directory / "retained/cli.xml").exists())

    def test_preexisting_or_duplicate_reserved_ids_reject_before_installation(self):
        self.owner()
        for identifier in ("3" * 32, "4" * 32):
            with patch.object(C.uuid, "uuid4", return_value=SimpleNamespace(hex=identifier)):
                with self.subTest(identifier=identifier), self.assertRaises(ValueError):
                    self.prepare()
        self.assertFalse(self.directory.exists())

    def test_audit_context_must_supply_actual_job_source_root_and_home(self):
        path = self.state / "context.json"
        original = C.parse_json(path.read_bytes())
        for key in ("id", "source", "root", "gradleHome"):
            path.write_bytes(C.encoded({**original, key: "wrong"}))
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.prepare()
        self.assertFalse(self.directory.exists())

    def test_missing_or_changed_event_domain_cannot_use_request_token_alone(self):
        request = self.prepare()
        self.observations(request)
        for suffix in ("start", "finish"):
            original = C.parse_json((self.directory / "events" / f"cli-{suffix}.json").read_bytes())
            for key in ("id", "job", "state", "home"):
                wrong = copy.deepcopy(original)
                wrong["ownerDomain"][key] = "wrong"
                with self.subTest(suffix=suffix, key=key), self.assertRaises(ValueError):
                    C.validate_event(wrong, request, original["requestSha256"], "cli", suffix)
            del original["ownerDomain"]
            with self.assertRaises(ValueError):
                C.validate_event(original, request, original["requestSha256"], "cli", suffix)

    def test_valid_receipt_cannot_accept_events_from_another_native_invocation(self):
        _, path, _ = self.ready()
        event_path = self.directory / "events/cli-start.json"
        event = C.parse_json(event_path.read_bytes())
        event["ownerDomain"]["id"] = "7" * 32
        event_path.write_bytes(C.encoded(event))
        self.assertEqual("HOLD", C.collect(self.directory, path)["result"])

    def test_writer_job_is_explicit_and_ids_are_distinct(self):
        with self.assertRaises(ValueError):
            C.prepare(self.root, self.directory, self.home, self.state, "writer", ["cli"], self.command)
        request = self.prepare(kind="writer")
        self.assertEqual(3, len(set(request["owner"].values())))
        self.assertEqual("4" * 32, request["owner"]["job"])

    def test_changed_current_source_is_not_old_source_evidence(self):
        _, path, _ = self.ready()
        with patch.object(C, "source", return_value={**SOURCE, "commit": "7" * 40}):
            self.assertEqual("HOLD", C.collect(self.directory, path)["result"])

    def test_reparse_attribute_is_not_an_ordinary_file(self):
        target = self.base / "synthetic-reparse"
        target.write_text("not followed")
        info = target.lstat()
        class Reparse:
            st_mode = info.st_mode
            st_file_attributes = 0x400
        with patch.object(Path, "lstat", return_value=Reparse()):
            with self.assertRaises(ValueError):
                C.no_links(target)

    def test_wrong_verified_copy_rejects_and_preserves_destination(self):
        path = self.base / "write-control"
        original = C.read_file
        def changed(target, limit=C.LIMIT):
            value = original(target, limit)
            return value + b"changed" if target == path else value
        with patch.object(C, "read_file", side_effect=changed):
            with self.assertRaises(ValueError):
                C.write_new(path, b"source-defined synthetic bytes")
        self.assertTrue(path.exists())

    def test_short_write_rejects_without_disposal(self):
        actual = C.os.fdopen
        class ShortWriter:
            def __init__(self, descriptor, mode):
                self.stream = actual(descriptor, mode)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def write(self, data):
                self.stream.write(data[:2])
                return 2
        destination = self.base / "short"
        with patch.object(C.os, "fdopen", side_effect=ShortWriter):
            with self.assertRaises(ValueError):
                C.write_new(destination, b"synthetic")
        self.assertEqual(b"sy", destination.read_bytes())

    def test_uninstall_removes_only_owned_loader_after_known_retirement(self):
        _, path, _ = self.ready()
        sentinel = self.home / "init.d" / "unrelated.gradle"
        sentinel.write_text("keep")
        C.collect(self.directory, path)
        C.uninstall(self.directory)
        self.assertFalse((self.home / "init.d" / C.LOADER).exists())
        self.assertEqual("keep", sentinel.read_text())
        self.assertTrue((self.directory / "retained/cli.xml").exists())
        self.assertFalse(json.loads((self.directory / "uninstalled.json").read_text())["originalsDeleted"])

    def test_unknown_retirement_cannot_uninstall_initializer(self):
        _, path, owner = self.ready()
        owner["errors"] = ["unknown retirement"]
        path.write_bytes(C.encoded(owner))
        C.collect(self.directory, path)
        with self.assertRaises(ValueError):
            C.uninstall(self.directory)
        self.assertTrue((self.home / "init.d" / C.LOADER).exists())


if __name__ == "__main__":
    unittest.main()
