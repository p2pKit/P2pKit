#!/usr/bin/env python3
"""Offline orchestration controls; no Windows tool, installer or application execution."""

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "inspect-rpc-windows-package.py"
SPEC = importlib.util.spec_from_file_location("inspect_rpc_package", SCRIPT)
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


class PackageInspectionTests(unittest.TestCase):
    def test_path_mismatch_retains_prior_comparisons_and_nonzero_finite_output(self):
        # Real MSI-module raise frame, with only its already observed dictionaries modeled.
        pinned = [{"target": "app/fixed-component", "bytes": 1, "sha256": "a" * 64}]
        def mismatch(*_):
            with patch.object(V.M, "image_inventory", return_value={"app/fixed-component": {
                    "bytes": 1, "sha256": "a" * 64}, "app/PRIVATE-image": {}}), \
                    patch.object(V.M, "extracted_inventory", return_value={"app/fixed-component": {
                        "bytes": 1, "sha256": "a" * 64}, "app/PRIVATE-msi": {},
                        "app/.package": {"bytes": 13, "sha256": hashlib.sha256(b"P2pKit Sample").hexdigest()}}):
                V.M.full_payload([], None, None, pinned)
        public = io.StringIO()
        with patch.object(V.M, "inspect", side_effect=mismatch), patch.object(V, "ROOT", self.root), \
                patch.object(V.os, "environ", self.env), patch.object(V.sys, "argv", [str(SCRIPT)]), \
                contextlib.redirect_stderr(public):
            self.assertEqual(V.main(), 1)
        lines = public.getvalue().splitlines()
        self.assertEqual(lines[0], "RPC_WINDOWS_PACKAGE_FAILURE RPC_MSI_PAYLOAD_PATHS")
        self.assertTrue(lines[1].startswith("RPC_WINDOWS_PACKAGE_CHECK_LINES "))
        self.assertTrue(lines[2].startswith("RPC_WINDOWS_PACKAGE_PATHS "))
        self.assertEqual(lines[3], "RPC_WINDOWS_PACKAGE_INSPECTION_REFUSED")
        self.assertEqual(len(lines), 4)
        self.assertNotIn("PRIVATE", public.getvalue())
        receipt = json.loads((self.reports / "msi-payload-refusal.json").read_text())
        self.assertEqual(receipt["result"], "REFUSED")
        self.assertEqual(receipt["source"], self.source)
        self.assertEqual(receipt["msi"], V.P.file_hash(self.msi, 1024 ** 3))
        self.assertEqual(receipt["comparedFiles"], pinned)
        self.assertEqual(receipt["pathMismatch"], json.loads(lines[2].split(" ", 1)[1]))
        self.assertEqual(receipt["imageInspectionSha256"],
                         hashlib.sha256((self.reports / "app-image-inspection.json").read_bytes()).hexdigest())
        self.assertEqual(receipt["wxsSha256"],
                         hashlib.sha256((self.reports / "decompiled-product.wxs").read_bytes()).hexdigest())
        self.assertFalse((self.reports / "result.json").exists())
        self.assertFalse((self.reports / "msi-payload-inspection.json").exists())
        self.assertEqual(len(self.calls), 2)

    def test_invalid_typed_mismatch_metadata_cannot_escape_or_produce_failed_receipt(self):
        error = V.M.PayloadPathMismatch({"app/a": {}}, {"app/b": {}}, [])
        error.diagnostic["PRIVATE"] = "PRIVATE_INPUT"
        public = io.StringIO()
        with patch.object(V.M, "inspect", side_effect=error), contextlib.redirect_stderr(public), \
                self.assertRaises(V.M.PayloadPathMismatch) as raised:
            self.inspect()
        self.assertIs(raised.exception, error)
        self.assertEqual(public.getvalue(), "RPC_WINDOWS_PACKAGE_REFUSAL_RECORD_FAILED\n")
        self.assertFalse((self.reports / "msi-payload-refusal.json").exists())
        self.assertFalse((self.reports / "result.json").exists())

    def test_failed_supplemental_receipt_preserves_original_path_refusal_and_public_counts(self):
        def mismatch(*_):
            with patch.object(V.M, "image_inventory", return_value={"app/PRIVATE-a": {}}), \
                    patch.object(V.M, "extracted_inventory", return_value={"app/PRIVATE-b": {},
                        "app/.package": {"bytes": 13, "sha256": hashlib.sha256(b"P2pKit Sample").hexdigest()}}):
                V.M.full_payload([], None, None, [])
        original_write = V.write_json
        def fail_receipt(path, *args, **kwargs):
            if path.name == "msi-payload-refusal.json":
                raise OSError("PRIVATE_FILE_SYSTEM_FAILURE")
            return original_write(path, *args, **kwargs)
        public = io.StringIO()
        with patch.object(V.M, "inspect", side_effect=mismatch), patch.object(V, "ROOT", self.root), \
                patch.object(V.os, "environ", self.env), patch.object(V.sys, "argv", [str(SCRIPT)]), \
                patch.object(V, "write_json", side_effect=fail_receipt), contextlib.redirect_stderr(public):
            self.assertEqual(V.main(), 1)
        lines = public.getvalue().splitlines()
        self.assertEqual(lines[0], "RPC_WINDOWS_PACKAGE_REFUSAL_RECORD_FAILED")
        self.assertEqual(lines[1], "RPC_WINDOWS_PACKAGE_FAILURE RPC_MSI_PAYLOAD_PATHS")
        self.assertTrue(lines[2].startswith("RPC_WINDOWS_PACKAGE_CHECK_LINES "))
        self.assertTrue(lines[3].startswith("RPC_WINDOWS_PACKAGE_PATHS "))
        self.assertEqual(json.loads(lines[3].split(" ", 1)[1])["missingFiles"], 1)
        self.assertEqual(lines[4], "RPC_WINDOWS_PACKAGE_INSPECTION_REFUSED")
        self.assertEqual(len(lines), 5)
        self.assertNotIn("PRIVATE", public.getvalue())
        self.assertNotIn("PASS", public.getvalue())
        self.assertFalse((self.reports / "result.json").exists())

    def test_failure_diagnostic_uses_only_exact_source_errors_and_numeric_frames(self):
        source = Path(V.M.__file__).read_text()
        for message, category in V.E.RPC_PACKAGE_ERRORS.items():
            with self.subTest(category=category):
                self.assertIn('"' + message + '"', source)
                try:
                    V.M.require(False, message)
                except ValueError as error:
                    actual, lines = V.failure_diagnostic(error)
                self.assertEqual(actual, category)
                self.assertEqual(len(lines), 1)
                self.assertTrue(0 < lines[0] <= 99999)
                self.assertNotIn(str(self.directory), json.dumps([actual, lines]))

    def test_failure_diagnostic_does_not_promote_private_or_foreign_errors(self):
        for message in ("PRIVATE_PAYLOAD", "MSI application payload differs from completed image PRIVATE",
                        " MSI application payload differs from completed image", "MSI application payload differs from completed image\n"):
            try:
                V.M.require(False, message)
            except ValueError as error:
                category, lines = V.failure_diagnostic(error)
            self.assertIsNone(category)
            self.assertEqual(len(lines), 1)
        try:
            raise ValueError("MSI application payload differs from completed image")
        except ValueError as error:
            self.assertEqual(V.failure_diagnostic(error), (None, []))

    def test_main_retains_failure_with_safe_inspector_diagnostics(self):
        public = io.StringIO()
        def refuse(*_):
            V.M.require(False, "MSI application payload differs from completed image")
        with patch.object(V.sys, "argv", [str(SCRIPT)]), patch.object(V, "inspect_package", side_effect=refuse), \
                contextlib.redirect_stderr(public):
            self.assertEqual(V.main(), 1)
        lines = public.getvalue().splitlines()
        self.assertEqual(lines[0], "RPC_WINDOWS_PACKAGE_FAILURE RPC_MSI_PAYLOAD_BYTES")
        self.assertRegex(lines[1], r"^RPC_WINDOWS_PACKAGE_CHECK_LINES [1-9][0-9]{0,4}$")
        self.assertEqual(lines[2], "RPC_WINDOWS_PACKAGE_INSPECTION_REFUSED")
        self.assertEqual(len(lines), 3)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rpc-package-controls-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.root = self.directory / "checkout"
        self.root.mkdir()
        self.runner = self.directory / "runner"
        self.runner.mkdir()
        self.wix = self.directory / "wix"
        (self.wix / "bin").mkdir(parents=True)
        self.dark = self.wix / "bin/dark.exe"
        self.dark.write_bytes(b"synthetic dark; never executed")
        self.source = {"commit": "a" * 40, "tree": "b" * 40, "platform": "windows", "architecture": "x64",
                       "job": "run", "workflow_ref": "p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/main",
                       "workflow_sha": "a" * 40, "run_id": "123", "run_attempt": "1"}
        self.env = {"WIX": str(self.wix), "RUNNER_TEMP": str(self.runner), "COMPONENT": "desktop-windows",
                    "P2PKIT_CI_COMMAND_DEADLINE_NS": "180000000000", "GRADLE_USER_HOME": "original-home",
                    "ORIGINAL_OWNERSHIP_MARKER": "preserve"}
        self.base = self.root / V.P.INSTALLER_ROOT
        self.image = self.base / "app/P2pKit Sample"
        self.image.mkdir(parents=True)
        (self.base / "msi").mkdir()
        self.msi = self.base / "msi/P2pKit Sample-1.8.203.msi"
        self.msi.write_bytes(bytes.fromhex("d0cf11e0a1b11ae1") + b"synthetic MSI")
        self.compiler = self.root / ("samples/p2p-sample-desktop-ui/build/rpc-windows-profile/" + "a" * 40 +
                                     "/compiler/compiler.properties")
        self.compiler.parent.mkdir(parents=True)
        self.compiler.write_bytes(b"synthetic compiler receipt; actual inspector tested separately\n")
        self.reports = self.root / "build/reports/rpc-windows-package"
        self.work = self.runner / "p2pkit-rpc-msi-123-1"
        self.image_record = {"scope": V.A.SCOPE, "source": "a" * 40, "tree": "b" * 40, "result": "PASS"}
        self.payload = {"scope": V.M.SCOPE, "source": "a" * 40, "tree": "b" * 40,
                        "result": "PASS", "comparedFiles": [{"synthetic": i} for i in range(4)]}
        self.outcome = {"exitCode": 0, "code": "PASS", "timedOut": False, "cleanupKnown": True,
                        "capturesClosed": True, "stage": "COMMAND", "elapsedSeconds": 0.01}
        self.calls = []
        self.change_tool = False
        self.change_msi = False
        self.bad_version = False
        self.failed_phase = None
        self.failure = {}
        for target, name, settings in ((V.P, "context", {"side_effect": lambda *args: dict(self.source)}),
                                       (V.A, "inspect", {"return_value": self.image_record}),
                                       (V.M, "inspect", {"return_value": self.payload}),
                                       (V.E, "run_command", {"side_effect": self.run_tool}),
                                       (V.time, "monotonic", {"return_value": 100.0})):
            patcher = patch.object(target, name, **settings)
            mock = patcher.start()
            self.addCleanup(patcher.stop)
            if target is V.P:
                self.context_mock = mock

    def run_tool(self, argv, **kwargs):
        self.calls.append((list(argv), kwargs))
        private = kwargs["private"]
        private.mkdir()
        version = argv == [str(self.dark), "-?"]
        (private / "stdout.log").write_bytes(
            b"unexpected version\n" if self.bad_version else
            b"Windows Installer XML Toolset Decompiler version 3.14.1.8722\r\n" if version else b"decompiled\n")
        (private / "stderr.log").write_bytes(b"")
        if not version:
            self.assertEqual(argv, [str(self.dark), "-nologo", "-x", str(self.work / "payload"),
                                    str(self.msi), str(self.work / "product.wxs")])
            (self.work / "payload/File").mkdir(parents=True)
            (self.work / "payload/File/do-not-copy").write_bytes(b"synthetic extracted bytes")
            (self.work / "product.wxs").write_bytes(b"<Wix>Synthetic metadata, not real MSI proof</Wix>\n")
            if self.change_msi:
                self.msi.write_bytes(b"changed MSI")
        if self.change_tool:
            self.dark.write_bytes(b"changed tool")
        result = dict(self.outcome)
        if self.failed_phase == ("version" if version else "extraction"):
            result.update(self.failure)
        return result

    def inspect(self):
        return V.inspect_package(self.root, self.env)

    def test_exact_existing_inspectors_and_bounded_tool_commands_are_used(self):
        result = self.inspect()
        self.assertEqual(result["scope"], V.SCOPE)
        self.assertEqual(result["result"], "PASS")
        self.assertEqual(result["comparedPayloads"], 4)
        self.assertEqual(result["source"], self.source)
        self.assertEqual(result["tool"]["version"], "3.14.1.8722")
        self.assertEqual(result["tool"]["sha256"], hashlib.sha256(self.dark.read_bytes()).hexdigest())
        for name in ("installation", "runtimeReadback", "nativeProvider", "wholeLifetimeSupervision"):
            self.assertEqual(result[name], "NOT_PERFORMED")
        self.assertEqual(len(self.calls), 2)
        self.assertEqual([kwargs["timeout"] for _, kwargs in self.calls], [10, 60])
        for argv, kwargs in self.calls:
            self.assertEqual(argv[0], str(self.dark))
            self.assertEqual(kwargs["cwd"], self.root)
            self.assertEqual(kwargs["log_limit"], 1024 * 1024)
            self.assertEqual(kwargs["cleanup_seconds"], 15.0)
            self.assertEqual(kwargs["environment"]["WIX_TEMP"], str(self.work / "temp"))
            for key, value in self.env.items():
                self.assertEqual(kwargs["environment"][key], value)
        expected = (self.image, self.compiler, self.msi, "a" * 40, "b" * 40)
        self.assertEqual(V.A.inspect.call_count, 2)
        for call in V.A.inspect.call_args_list:
            self.assertEqual(call.args, expected)
            self.assertEqual(call.kwargs, {"preview_adapter": True})
        V.M.inspect.assert_called_once_with(self.work / "product.wxs", self.work / "payload", self.image,
                                             self.reports / "app-image-inspection.json", self.msi)
        self.assertEqual(self.context_mock.call_count, 2)
        self.assertEqual(json.loads((self.reports / "app-image-inspection.json").read_text()), self.image_record)
        self.assertEqual((self.reports / "decompiled-product.wxs").read_bytes(), (self.work / "product.wxs").read_bytes())
        self.assertFalse(any(path.name == "do-not-copy" for path in self.reports.rglob("*")))
        self.assertTrue((self.work / "payload/File/do-not-copy").is_file())

    def test_both_maintained_callers_accepted_and_other_contexts_refused_before_io(self):
        for workflow in V.WORKFLOWS:
            with self.subTest(workflow=workflow):
                self.source["workflow_ref"] = workflow + "@refs/heads/work/current-candidate"
                self.assertEqual(V.context(self.root, self.env), self.source)
        for key, value in (("platform", "linux"), ("architecture", "arm64"), ("job", "rpc-windows"),
                           ("workflow_sha", "c" * 40), ("workflow_ref", "p2pKit/P2pKit/.github/workflows/other.yml@refs/heads/main")):
            previous = self.source[key]
            with self.subTest(key=key):
                self.source[key] = value
                with self.assertRaises(ValueError):
                    self.inspect()
                self.source[key] = previous
        self.env["COMPONENT"] = "desktop-linux"
        with self.assertRaises(ValueError):
            self.inspect()
        self.assertFalse(self.reports.exists())
        self.assertEqual(self.calls, [])

    def test_dirty_or_unbound_source_refusal_from_maintained_context_is_preserved(self):
        self.context_mock.side_effect = ValueError("source refused")
        with self.assertRaisesRegex(ValueError, "source refused"):
            self.inspect()
        self.assertFalse(self.reports.exists())
        self.assertEqual(self.calls, [])

    def test_existing_reports_are_never_overwritten(self):
        self.reports.mkdir(parents=True)
        sentinel = self.reports / "result.json"
        sentinel.write_bytes(b"prior record")
        with self.assertRaises(FileExistsError):
            self.inspect()
        self.assertEqual(sentinel.read_bytes(), b"prior record")
        self.assertEqual(self.calls, [])

    def test_multiple_installers_and_linked_compiler_are_refused(self):
        extra = self.msi.with_name("extra.msi")
        extra.write_bytes(b"extra")
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.inspect()
        extra.unlink()
        self.compiler.unlink()
        self.compiler.symlink_to(self.dark)
        with self.assertRaises(ValueError):
            self.inspect()
        self.assertEqual(self.calls, [])

    def test_extraction_cannot_use_checkout_or_existing_work(self):
        self.env["RUNNER_TEMP"] = str(self.root)
        with self.assertRaisesRegex(ValueError, "outside"):
            self.inspect()
        self.env["RUNNER_TEMP"] = str(self.runner)
        self.work.mkdir()
        with self.assertRaises(FileExistsError):
            self.inspect()
        self.assertEqual(self.calls, [])

    def test_missing_or_relative_runner_temp_is_refused_before_output(self):
        for value in (None, "", ".", "relative-temp"):
            with self.subTest(value=value):
                if value is None:
                    self.env.pop("RUNNER_TEMP", None)
                else:
                    self.env["RUNNER_TEMP"] = value
                with self.assertRaises(ValueError):
                    self.inspect()
        self.assertFalse(self.reports.exists())
        self.assertFalse(self.work.exists())
        self.assertEqual(self.calls, [])

    def test_failed_image_check_stops_before_any_native_tool(self):
        V.A.inspect.side_effect = ValueError("image refused")
        with self.assertRaisesRegex(ValueError, "image refused"):
            self.inspect()
        self.assertEqual(self.calls, [])
        self.assertFalse((self.reports / "result.json").exists())

    def test_nonzero_timeout_or_unknown_cleanup_is_retained_and_never_passes(self):
        for failure in ({"exitCode": 1, "code": "COMMAND_FAILED"}, {"timedOut": True, "code": "TIMEOUT"},
                        {"cleanupKnown": False}, {"capturesClosed": False}):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(dir=self.directory) as directory:
                reports = Path(directory)
                self.failed_phase, self.failure = "version", failure
                with self.assertRaisesRegex(ValueError, "complete safely"):
                    V.run_tool([str(self.dark), "-?"], "version", self.root, reports, self.env, self.source, 10)
                observed = json.loads((reports / "version/outcome.json").read_text())["outcome"]
                for key, value in failure.items():
                    self.assertEqual(observed[key], value)

    def test_extraction_failure_leaves_original_outcome_without_payload_success(self):
        self.failed_phase = "extraction"
        self.failure = {"exitCode": 7, "code": "COMMAND_FAILED"}
        with self.assertRaises(ValueError):
            self.inspect()
        self.assertEqual(json.loads((self.reports / "dark-extraction/outcome.json").read_text())["outcome"]["exitCode"], 7)
        V.M.inspect.assert_not_called()
        self.assertFalse((self.reports / "result.json").exists())

    def test_deadline_is_required_and_clips_tool_without_reset(self):
        for value in ("", "invalid", "114000000000"):
            with self.subTest(value=value):
                self.env["P2PKIT_CI_COMMAND_DEADLINE_NS"] = value
                with self.assertRaises(ValueError):
                    V.run_tool([str(self.dark), "-?"], "version", self.root, self.runner, self.env, self.source, 10)
        self.assertEqual(self.calls, [])
        self.env["P2PKIT_CI_COMMAND_DEADLINE_NS"] = "119000000000"
        V.run_tool([str(self.dark), "-?"], "version", self.root, self.runner, self.env, self.source, 10)
        self.assertEqual(self.calls[-1][1]["timeout"], 4.0)

    def test_unrecognized_version_or_changed_tool_stops_before_decompilation(self):
        self.bad_version = True
        with self.assertRaisesRegex(ValueError, "version output"):
            self.inspect()
        self.assertEqual(len(self.calls), 1)
        V.M.inspect.assert_not_called()

    def test_original_tool_change_is_not_hidden_by_success_exit(self):
        self.change_tool = True
        with self.assertRaisesRegex(ValueError, "WiX tool changed"):
            self.inspect()
        self.assertEqual(len(self.calls), 1)
        V.M.inspect.assert_not_called()

    def test_post_tool_source_and_msi_changes_cannot_produce_final_success(self):
        self.change_msi = True
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.inspect()
        self.assertFalse((self.reports / "result.json").exists())

    def test_current_source_and_all_four_payloads_are_required(self):
        for field, value in (("source", "c" * 40), ("tree", "c" * 40), ("comparedFiles", [{}, {}, {}])):
            with self.subTest(field=field):
                original = self.payload[field]
                self.payload[field] = value
                # Separate fresh report/work directories for each independent input.
                with tempfile.TemporaryDirectory(dir=self.directory) as directory:
                    fresh_reports = Path(directory) / "reports"
                    fresh_reports.mkdir()
                    self.env["RUNNER_TEMP"] = directory
                    old_work = self.work
                    self.work = Path(directory) / "p2pkit-rpc-msi-123-1"
                    with patch.object(V, "new_reports", return_value=fresh_reports):
                        with self.assertRaisesRegex(ValueError, "Incomplete source-bound"):
                            self.inspect()
                    self.work = old_work
                self.payload[field] = original

    def test_source_changed_after_tools_is_refused(self):
        self.context_mock.side_effect = [dict(self.source), {**self.source, "tree": "c" * 40}]
        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.inspect()
        self.assertFalse((self.reports / "result.json").exists())

    def test_cli_has_no_path_context_or_command_override_and_no_raw_error_output(self):
        with patch.object(V.sys, "argv", [str(SCRIPT), "--image", "PRIVATE_PATH"]), \
                contextlib.redirect_stdout(io.StringIO()) as stdout, contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(V.main(), 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "RPC_WINDOWS_PACKAGE_INSPECTION_REFUSED\n")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
