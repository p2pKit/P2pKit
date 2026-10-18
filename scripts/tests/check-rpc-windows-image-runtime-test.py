#!/usr/bin/env python3
"""Bounded offline models; no application, native provider or installer is executed."""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "check-rpc-windows-image-runtime.py"
SPEC = importlib.util.spec_from_file_location("rpc_windows_runtime", SCRIPT)
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)


def module_observation():
    return {"scope": "WINDOWS_RUNTIME_MODULE_RESOLUTION_ONLY_NOT_PROFILE_OR_RELEASE", "source": "a" * 40,
            "javaFeature": 21, "javaVersion": "21.0.12.1+1", "module": "jdk.unsupported",
            "options": ["NOSHARE_READ", "NOSHARE_WRITE", "NOSHARE_DELETE"],
            "nativeLoad": "NOT_PERFORMED", "profileAccess": "NOT_PERFORMED"}


def adapter_observation():
    return {"source": "a" * 40, "adapter": {
        "schema": 1, "scope": "JDK21_PREVIEW_MODULE_DIAGNOSTIC_NOT_DLL_OR_PROFILE", "javaFeature": 21,
        "javaVersion": "21.0.12.1+1", "module": "dev.p2pkit.rpc.windows.loader", "previewEnabled": True,
        "namedNativeAccess": True, "unnamedNativeAccess": False, "ffmFromJavaBase": True,
        "windowsX64Hint": True, "productionAvailable": False, "nativeLoad": "NOT_PERFORMED",
        "profileAccess": "NOT_PERFORMED", "javaVendor": "Eclipse Adoptium",
        "javaRuntimeVersion": "21.0.12.1+1-LTS", "javaVmVersion": "21.0.12.1+1-LTS"}}


class RuntimeObservationTests(unittest.TestCase):
    def test_exact_module_and_disabled_adapter_observations(self):
        V.validate_observation(module_observation(), "a" * 40, "21.0.12.1+1", False)
        V.validate_observation(adapter_observation(), "a" * 40, "21.0.12.1+1", True)

    def test_module_source_schema_options_and_load_refusals(self):
        for key, value in (("source", "b" * 40), ("extra", True), ("javaFeature", True),
                           ("javaFeature", 17), ("javaFeature", 22), ("module", "java.base"), ("options", "NOSHARE_READ"),
                           ("options", ["NOSHARE_DELETE", "NOSHARE_WRITE", "NOSHARE_READ"]),
                           ("nativeLoad", "PERFORMED"), ("profileAccess", "PERFORMED"),
                           ("javaVersion", "21.0.11+1"), ("javaVersion", [21])):
            with self.subTest(key=key, value=value):
                observation = module_observation()
                observation[key] = value
                with self.assertRaises(ValueError):
                    V.validate_observation(observation, "a" * 40, "21.0.12.1+1", False)

    def test_preview_refuses_types_native_grants_and_unbounded_metadata(self):
        cases = [("schema", True), ("javaFeature", True), ("javaFeature", 17), ("extra", None),
                 ("nativeLoad", "LOADED"), ("profileAccess", "OPEN"), ("module", "ALL-UNNAMED"),
                 ("javaVendor", "PRIVATE\nVALUE"), ("javaVmVersion", "x" * 129),
                 ("javaRuntimeVersion", ""), ("javaVersion", "21.0.11+1")]
        for name in ("previewEnabled", "namedNativeAccess", "unnamedNativeAccess", "ffmFromJavaBase",
                     "windowsX64Hint", "productionAvailable"):
            expected = adapter_observation()["adapter"][name]
            cases.extend(((name, not expected), (name, int(expected)), (name, str(expected))))
        for key, value in cases:
            with self.subTest(key=key, value=value):
                observation = adapter_observation()
                observation["adapter"][key] = value
                with self.assertRaises(ValueError):
                    V.validate_observation(observation, "a" * 40, "21.0.12.1+1", True)
        for observation in ({"source": "b" * 40, "adapter": adapter_observation()["adapter"]},
                            {**adapter_observation(), "extra": False}):
            with self.assertRaises(ValueError):
                V.validate_observation(observation, "a" * 40, "21.0.12.1+1", True)

    def test_json_rejects_duplicate_nonfinite_and_malformed(self):
        for raw in (b'{"source":1,"source":2}', b'{"value":NaN}', b'{"value":Infinity}', b'{"bad"}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                V.parse_json(raw)


class RuntimeCallerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rpc-runtime-controls-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.image = self.root / V.P.INSTALLER_ROOT / "app/P2pKit Sample"
        for member in (*V.MEMBERS, "app/application.jar", "app/rpc.jar", "app/dependency.jar"):
            path = self.image / member
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(("synthetic; never executed: " + member).encode())
        (self.image / "runtime/release").write_bytes(b'JAVA_VERSION="21.0.12.1+1"\nMODULES="java.base jdk.unsupported"\n')
        self.source = {"commit": "a" * 40, "tree": "b" * 40, "platform": "windows", "architecture": "x64",
                       "job": "run", "workflow_ref": "p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/main",
                       "workflow_sha": "a" * 40, "run_id": "123", "run_attempt": "1"}
        self.environment = {"COMPONENT": "desktop-windows", "P2PKIT_CI_COMMAND_DEADLINE_NS": "180000000000",
                            "GRADLE_USER_HOME": "original-home", "ORIGINAL_OWNERSHIP_MARKER": "unchanged"}
        self.msi = self.root / V.P.INSTALLER_ROOT / "msi/P2pKit Sample.msi"
        self.msi.parent.mkdir()
        self.msi.write_bytes(b"synthetic MSI; never executed" * 4)
        self.inspection = self.root / "build/reports/rpc-windows-package/app-image-inspection.json"
        self.inspection.parent.mkdir(parents=True)
        self.reports = self.root / "build/reports/rpc-windows-runtime-readback"
        members = V.inventory(self.image, "application.jar")
        def jar(name):
            return {"file": name, "jarBytes": members["app/" + name]["bytes"],
                    "jarSha256": members["app/" + name]["sha256"]}
        self.record = {"source": "a" * 40, "tree": "b" * 40, "scope": V.A.SCOPE, "result": "PASS",
                       "applicationJar": "application.jar", "declaredUnsupportedModule": True,
                       "parentPin": jar("rpc.jar"), "requiredClassJars": [jar("rpc.jar"), jar("application.jar")],
                       "adapter": {"scope": V.A.ADAPTER_SCOPE, "file": V.A.ADAPTER_PATH,
                                   "module": V.A.ADAPTER_MODULE, "jarBytes": members[V.A.ADAPTER_PATH]["bytes"],
                                   "jarSha256": members[V.A.ADAPTER_PATH]["sha256"],
                                   "launcher": {"file": "app/P2pKit Sample.cfg",
                                                "sha256": members["app/P2pKit Sample.cfg"]["sha256"],
                                                "requiredOptions": list(V.A.ADAPTER_OPTIONS)}},
                       "msi": {"file": self.msi.name, **V.P.file_hash(self.msi, 1024 ** 3)}}
        self.save_inspection()
        self.calls = []
        self.outcome = {"code": "PASS", "exitCode": 0, "timedOut": False, "cleanupKnown": True,
                        "capturesClosed": True, "elapsedSeconds": 0.01}
        self.raw_override = None
        self.stderr = b""
        self.after_run = lambda: None
        self.context_patch = patch.object(V.P, "context", return_value=self.source)
        self.context_patch.start()
        self.addCleanup(self.context_patch.stop)
        self.run_patch = patch.object(V.E, "run_command", side_effect=self.fake_run)
        self.run_mock = self.run_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.clock = patch.object(V.time, "monotonic", return_value=100.0)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def save_inspection(self):
        self.inspection.write_text(json.dumps(self.record), encoding="utf-8")

    def fake_run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        self.assertEqual(argv, [str(self.image / "P2pKit Sample.exe"), V.PROBES[len(self.calls) - 1][1]])
        self.assertEqual(kwargs["environment"], self.environment)
        self.assertEqual(kwargs["cwd"], self.root)
        self.assertEqual(kwargs["cleanup_seconds"], 15.0)
        self.assertEqual(kwargs["log_limit"], 4096)
        private = kwargs["private"]
        private.mkdir()
        observation = module_observation() if len(self.calls) == 1 else adapter_observation()
        raw = self.raw_override if self.raw_override is not None else (json.dumps(observation) + "\n").encode()
        (private / "stdout.log").write_bytes(raw)
        (private / "stderr.log").write_bytes(self.stderr)
        self.after_run()
        return self.outcome

    def assert_no_success(self):
        self.assertFalse((self.reports / "result.json").exists())

    def test_two_fixed_commands_source_receipt_and_explicit_unqualified_scope(self):
        raw_hash = hashlib.sha256(self.inspection.read_bytes()).hexdigest()
        result = V.check_runtime(self.root, self.environment)
        self.assertEqual(len(self.calls), 2)
        self.assertTrue(all(kwargs["timeout"] == 15.0 for _, kwargs in self.calls))
        self.assertEqual(result["imageInspectionSha256"], raw_hash)
        self.assertEqual(result["source"], self.source)
        self.assertEqual(result["msi"], self.record["msi"])
        self.assertEqual(result["result"], "PASS")
        for name in ("installedRuntime", "nativeProvider", "wholeLifetimeSupervision"):
            self.assertEqual(result[name], "NOT_PERFORMED")
        self.assertEqual(json.loads((self.reports / "result.json").read_bytes()), result)
        self.assertIn("app/dependency.jar", result["inputs"])

    def test_context_and_ambient_overrides_refuse_before_execution(self):
        for name in V.OVERRIDES:
            with self.subTest(name=name), self.assertRaises(ValueError):
                V.check_runtime(self.root, {**self.environment, name: "PRIVATE_VALUE"})
        for key, value in (("platform", "linux"), ("architecture", "arm64"), ("job", "publisher"),
                           ("workflow_sha", "c" * 40),
                           ("workflow_ref", "p2pKit/P2pKit/.github/workflows/unknown.yml@refs/heads/main")):
            with self.subTest(key=key), patch.object(V.P, "context", return_value={**self.source, key: value}), \
                    self.assertRaises(ValueError):
                V.check_runtime(self.root, self.environment)
        with self.assertRaises(ValueError):
            V.check_runtime(self.root, {**self.environment, "COMPONENT": "jvm-windows"})
        self.run_mock.assert_not_called()

    def test_static_source_and_member_pin_mismatch_refuse(self):
        for key, value in (("source", "c" * 40), ("tree", "c" * 40), ("result", "FAIL"),
                           ("scope", "INSTALLED"), ("applicationJar", "../application.jar"),
                           ("declaredUnsupportedModule", False)):
            with self.subTest(key=key):
                original = copy.deepcopy(self.record)
                self.record[key] = value
                self.save_inspection()
                with self.assertRaises(ValueError):
                    V.check_runtime(self.root, self.environment)
                self.record = original
        original = copy.deepcopy(self.record)
        for field in ("parentPin", "adapter"):
            with self.subTest(field=field):
                self.record = copy.deepcopy(original)
                self.record[field]["jarSha256"] = "d" * 64
                self.save_inspection()
                with self.assertRaises(ValueError):
                    V.check_runtime(self.root, self.environment)
        self.run_mock.assert_not_called()

    def test_inventory_refuses_missing_nonregular_empty_and_oversized_members(self):
        member = self.image / "app/dependency.jar"
        member.unlink()
        member.mkdir()
        with self.assertRaises(ValueError):
            V.inventory(self.image, "application.jar")
        member.rmdir()
        member.write_bytes(b"")
        with self.assertRaises(ValueError):
            V.inventory(self.image, "application.jar")
        member.write_bytes(b"bounded size model")
        original_signature = V.P.signature
        def oversized(path):
            observed = original_signature(path)
            if path == member:
                observed[2] = 512 * 1024 ** 2 + 1
            return observed
        with patch.object(V.P, "signature", side_effect=oversized), self.assertRaises(ValueError):
            V.inventory(self.image, "application.jar")
        member.unlink()
        (self.image / "app/application.jar").unlink()
        with self.assertRaises(ValueError):
            V.inventory(self.image, "application.jar")

    def test_enclosing_deadline_clips_original_budget_and_exhaustion_refuses(self):
        for deadline in ("", "not-a-deadline", "115000000000"):
            with self.subTest(deadline=deadline), self.assertRaises(ValueError):
                V.probe(self.root, self.image, "probe", V.PROBES[0][1], self.inspection.parent,
                        {**self.environment, "P2PKIT_CI_COMMAND_DEADLINE_NS": deadline}, self.source,
                        "21.0.12.1+1", False)
        self.run_mock.assert_not_called()
        self.environment["P2PKIT_CI_COMMAND_DEADLINE_NS"] = "120000000000"
        V.check_runtime(self.root, self.environment)
        self.assertTrue(all(kwargs["timeout"] == 5.0 for _, kwargs in self.calls))

    def test_unknown_cleanup_nonzero_cancel_timeout_refuse_without_reading_captures(self):
        for index, (key, value) in enumerate((("code", "CANCELLED"), ("exitCode", 1), ("exitCode", False),
                                              ("timedOut", True), ("cleanupKnown", False),
                                              ("capturesClosed", False))):
            with self.subTest(key=key):
                self.outcome = {"code": "PASS", "exitCode": 0, "timedOut": False,
                                "cleanupKnown": True, "capturesClosed": True, key: value}
                self.calls.clear()
                private_name = "failure-" + str(index)
                with patch.object(V, "read", side_effect=AssertionError("Must not read uncertain captures")), \
                        self.assertRaises(ValueError):
                    V.probe(self.root, self.image, private_name, V.PROBES[0][1], self.inspection.parent,
                            self.environment, self.source, "21.0.12.1+1", False)
                self.assert_no_success()

    def test_output_framing_stderr_oversize_and_duplicate_key_refusals(self):
        valid = json.dumps(module_observation()).encode()
        cases = [(valid, b""), (valid + b"\nPRIVATE\n", b""), (b"[]\n", b""),
                 (valid + b"\n", b"PRIVATE"), (b'{"long":"' + b"x" * 2048 + b'"}\n', b""),
                 (b'{"source":1,"source":2}\n', b""), (valid.replace(b'21,', b'NaN,') + b"\n", b"")]
        for index, (raw, stderr) in enumerate(cases):
            with self.subTest(index=index):
                self.calls.clear()
                self.raw_override, self.stderr = raw, stderr
                with self.assertRaises(ValueError):
                    V.probe(self.root, self.image, "framing-" + str(index), V.PROBES[0][1], self.inspection.parent,
                            self.environment, self.source, "21.0.12.1+1", False)

    def test_missing_or_changed_msi_refuses_before_command(self):
        self.msi.unlink()
        with self.assertRaises(OSError):
            V.check_runtime(self.root, self.environment)
        self.msi.write_bytes(b"different MSI")
        with self.assertRaises(ValueError):
            V.check_runtime(self.root, self.environment)
        self.run_mock.assert_not_called()
        self.assert_no_success()

    def test_post_command_msi_change_refuses(self):
        self.after_run = lambda: self.msi.write_bytes(b"changed MSI")
        with self.assertRaises(ValueError):
            V.check_runtime(self.root, self.environment)
        self.assertEqual(len(self.calls), 1)
        self.assert_no_success()

    def test_post_command_source_change_refuses(self):
        self.after_run = lambda: self.source.update(tree="c" * 40)
        # A real context call produces a fresh value each time, never mutates the saved source.
        with patch.object(V.P, "context", side_effect=lambda *_: dict(self.source)), self.assertRaises(ValueError):
            V.check_runtime(self.root, self.environment)
        self.assertEqual(len(self.calls), 1)
        self.assert_no_success()

    def test_post_command_receipt_change_refuses(self):
        self.after_run = lambda: self.inspection.write_bytes(self.inspection.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            V.check_runtime(self.root, self.environment)
        self.assertEqual(len(self.calls), 1)
        self.assert_no_success()

    def test_post_command_unpinned_dependency_change_refuses(self):
        self.after_run = lambda: (self.image / "app/dependency.jar").write_bytes(b"changed")
        with self.assertRaises(ValueError):
            V.check_runtime(self.root, self.environment)
        self.assertEqual(len(self.calls), 1)
        self.assert_no_success()

    def test_post_command_new_classpath_member_refuses(self):
        self.after_run = lambda: (self.image / "app/added.jar").write_bytes(b"new")
        with self.assertRaises(ValueError):
            V.check_runtime(self.root, self.environment)
        self.assertEqual(len(self.calls), 1)
        self.assert_no_success()

    def test_evidence_must_be_fresh_and_cli_errors_are_finite(self):
        self.reports.mkdir()
        with self.assertRaises(FileExistsError):
            V.check_runtime(self.root, self.environment)
        self.run_mock.assert_not_called()
        output, error = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), "PRIVATE_OVERRIDE"]), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            self.assertEqual(V.main(), 1)
        self.assertEqual(output.getvalue(), "")
        self.assertEqual(error.getvalue(), "RPC_WINDOWS_IMAGE_RUNTIME_READBACK_REFUSED\n")


if __name__ == "__main__":
    unittest.main(failfast=True)
