#!/usr/bin/env python3
"""Offline refusal controls, not multicast or native ownership evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("current_mdns", ROOT / "scripts/diagnose-current-macos-multicast.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AdmissionTest(unittest.TestCase):
    def setUp(self):
        self.env = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
                    "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_REF": module.REF,
                    "GITHUB_EVENT_NAME": "push", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
                    "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}

    def test_exact_context_admitted(self):
        module.admit(self.env, "Darwin", "arm64", 501, 501)

    def test_component_scope_is_explicit_and_cannot_relabel_multicast(self):
        component = {**self.env, "GITHUB_REF": module.COMPONENT_REF}
        module.admit(component, "Darwin", "arm64", 501, 501, "terminal-components")
        for env, profile in ((component, "multicast"), (self.env, "terminal-components"),
                             (component, "full"), (component, None)):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                module.admit(env, "Darwin", "arm64", 501, 501, profile)

    def test_wrong_or_missing_event_field_refused(self):
        for key in self.env:
            for wrong in (None, "", "incorrect"):
                with self.subTest(key=key, wrong=wrong):
                    changed = dict(self.env)
                    if wrong is None:
                        changed.pop(key)
                    else:
                        changed[key] = wrong
                    with self.assertRaises(ValueError):
                        module.admit(changed, "Darwin", "arm64", 501, 501)

    def test_privilege_translation_and_wrong_platform_refused(self):
        for system, machine, uid, euid in (("Linux", "arm64", 501, 501), ("Darwin", "x86_64", 501, 501),
                                          ("Darwin", "arm64", 0, 0), ("Darwin", "arm64", 501, 0)):
            with self.subTest(system=system, machine=machine, uid=uid, euid=euid):
                with self.assertRaises(ValueError):
                    module.admit(self.env, system, machine, uid, euid)

    def test_network_and_jvm_overrides_refused(self):
        for key in ("P2PKIT_JMDNS_FIXTURE_IPV4", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
                    "JAVA_OPTS", "GRADLE_OPTS"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.admit({**self.env, key: "override"}, "Darwin", "arm64", 501, 501)

    def test_zero_and_malformed_run_identity_refused(self):
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            for value in ("0", "-1", "01", "1\n", "9" * 21):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    module.admit({**self.env, key: value}, "Darwin", "arm64", 501, 501)

    def test_bootstrap_record_refuses_missing_or_weakened_boundaries(self):
        valid = {"schema": 1, "scope": "PROCESS_LOCAL_AUDIT_SESSION_NOT_OWNERSHIP_OR_PRODUCT_ADMISSION",
                 "previousSessionAssigned": True, "freshAssignedSession": True, "auditPolicyPreserved": True,
                 "invokingCredentialsRestored": True, "rootCannotBeRegained": True,
                 "privilegedObservationOrProductExecution": False}
        self.assertEqual(valid, module.validate_session(valid))
        for key in valid:
            with self.subTest(key=key):
                missing = dict(valid)
                missing.pop(key)
                with self.assertRaises(ValueError):
                    module.validate_session(missing)
                with self.assertRaises(ValueError):
                    module.validate_session({**valid, key: "true"})
        for key in ("freshAssignedSession", "auditPolicyPreserved", "invokingCredentialsRestored",
                    "rootCannotBeRegained", "privilegedObservationOrProductExecution"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.validate_session({**valid, key: not valid[key]})


class FinalResultTest(unittest.TestCase):
    def diagnostic(self, directory):
        instance = module.Diagnostic.__new__(module.Diagnostic)
        instance.profile = "multicast"
        instance.context = {"source": {"commit": "a" * 40, "tree": "b" * 40}}
        instance.result = {"scope": module.SCOPE, "result": "FAIL", "releaseCredit": False,
                           "completeGateCredit": False}
        instance.export = Path(directory)
        instance.runner = SimpleNamespace(source_snapshot=lambda root: instance.context["source"],
            write_new_json=lambda path, value: path.write_text(json.dumps(value)))
        return instance

    def test_product_failure_stays_failed_and_private_error_is_not_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.diagnostic(directory)
            with patch.object(instance, "execute", side_effect=ValueError("private-payload-address-path")):
                self.assertEqual(1, instance.run())
            raw = (Path(directory) / "summary.json").read_text()
            self.assertNotIn("private-payload", raw)
            self.assertEqual("ValueError", json.loads(raw)["failureClass"])

    def test_success_is_diagnostic_only(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.diagnostic(directory)
            with patch.object(instance, "execute", side_effect=lambda: instance.result.update(result="PASS_DIAGNOSTIC_ONLY")):
                self.assertEqual(0, instance.run())
            self.assertFalse(instance.result["releaseCredit"])
            self.assertFalse(instance.result["completeGateCredit"])

    def test_source_change_refuses_success(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.diagnostic(directory)
            instance.runner.source_snapshot = lambda root: {"commit": "c" * 40}
            with patch.object(instance, "execute", side_effect=lambda: instance.result.update(result="PASS_DIAGNOSTIC_ONLY")):
                self.assertEqual(1, instance.run())
            self.assertFalse(instance.result["sourceUnchanged"])

    def test_component_success_cannot_become_multicast_or_complete_gate_success(self):
        with tempfile.TemporaryDirectory() as directory:
            instance = self.diagnostic(directory)
            instance.profile = "terminal-components"
            instance.result["scope"] = module.COMPONENT_SCOPE
            with patch.object(instance, "execute", side_effect=lambda: instance.result.update(
                    result="PASS_COMPONENT_CONTROLS_ONLY")):
                self.assertEqual(0, instance.run())
            self.assertFalse(instance.result["releaseCredit"])
            self.assertFalse(instance.result["completeGateCredit"])
            instance.profile = "multicast"
            with patch.object(instance, "execute"):
                self.assertEqual(1, instance.run())

    def test_component_inventory_keeps_native_controls_but_does_not_run_multicast(self):
        instance = module.Diagnostic.__new__(module.Diagnostic)
        instance.profile = "terminal-components"
        instance.result = {"counts": {}, "fixture": "NOT_RUN", "result": "FAIL"}
        from unittest.mock import Mock
        controls = Mock()
        multicast = Mock(side_effect=AssertionError("Separate component scope cannot execute multicast"))
        instance.qualification = SimpleNamespace(Qualification=SimpleNamespace(
            native_controls=controls, multicast_admission=multicast))
        instance.invoke = Mock(side_effect=[{"count": count} for count in (49, 22, 28)])
        instance.output = lambda proof, **kwargs: f'Ran {proof["count"]} tests in 0.01s\nOK\n'.encode()
        instance.execute()
        controls.assert_called_once_with(instance)
        multicast.assert_not_called()
        self.assertEqual(instance.result["result"], "PASS_COMPONENT_CONTROLS_ONLY")
        self.assertEqual(instance.result["fixture"], "NOT_RUN")
        self.assertEqual(instance.result["counts"], {"ci-source-admission": 49, "ci-metadata": 22,
                                                   "terminal-refusal": 28})
        self.assertTrue(all(call.args[2] == 90 for call in instance.invoke.call_args_list))

    def test_incomplete_component_inventory_cannot_receive_success(self):
        instance = module.Diagnostic.__new__(module.Diagnostic)
        instance.profile = "terminal-components"
        instance.result = {"counts": {}, "result": "FAIL"}
        instance.qualification = SimpleNamespace(Qualification=SimpleNamespace(native_controls=lambda _: None))
        instance.invoke = lambda *args: {}
        instance.output = lambda *args, **kwargs: b"Ran 1 tests in 0.01s\nOK\n"
        with self.assertRaises(ValueError):
            instance.execute()
        self.assertEqual(instance.result["result"], "FAIL")

    def test_no_repeated_command(self):
        instance = module.Diagnostic.__new__(module.Diagnostic)
        instance.result = {"commands": [{"purpose": "already-run"}]}
        with self.assertRaises(ValueError):
            instance.invoke("already-run", [], 45)


class PrimitiveProjectionTest(unittest.TestCase):
    def test_exact_jdk_and_python_failure_records_retained(self):
        lines = [
            "startup primitivePair observation=POST_FAILURE scope=CAPTURED_IPV4_MDNS interpretation=KERNEL_ACCEPTANCE_ONLY",
            "startup primitive=JDK_MULTICAST reuseAddress=true reusePort=true",
            "startup primitive=JDK_MULTICAST stage=SEND result=FAIL failureClass=java.net.NoRouteToHostException errno=UNKNOWN sentBytes=0 socketClosed=true closeFailureClass=NONE",
            "startup primitive=PYTHON_IPV4 processCompleted=true exitZero=true",
            "startup primitive=PYTHON_IPV4 reportValid=true",
            "startup primitive=PYTHON_IPV4 stage=SEND result=FAIL failureClass=OSError errno=65 sentBytes=0 socketClosed=true closeFailureClass=NONE",
            "startup primitive=PYTHON_IPV4 processReaped=true",
        ]
        result = module.primitive_projection(("\n".join(lines) + "\n").encode())
        self.assertEqual(lines, result["markers"])
        self.assertEqual(0, result["unclassifiedPrimitiveLineCount"])

    def test_unknown_private_values_and_suffixes_not_exported(self):
        lines = ["startup primitive=PYTHON_IPV4 processReaped=true secret=PRIVATE",
                 "startup primitive=PYTHON_IPV4 stage=SEND result=FAIL failureClass=PRIVATE errno=65 sentBytes=0 socketClosed=true closeFailureClass=NONE",
                 "PRIVATE unrelated raw output",
                 "startup primitivePair attempted=false reason=PRIVATE"]
        result = module.primitive_projection("\n".join(lines).encode())
        self.assertEqual([], result["markers"])
        self.assertEqual(3, result["unclassifiedPrimitiveLineCount"])
        self.assertNotIn("PRIVATE", json.dumps(result))

    def test_success_is_kernel_acceptance_only(self):
        line = "startup primitive=PYTHON_IPV4 stage=SEND result=KERNEL_ACCEPTED failureClass=NONE errno=UNKNOWN sentBytes=42 socketClosed=true closeFailureClass=NONE"
        self.assertEqual([line], module.primitive_projection(line.encode())["markers"])

    def test_bounds_and_canonical_refusal_retained(self):
        line = "startup primitivePair attempted=false reason=CANONICAL_INTERPRETER_REQUIRED"
        self.assertEqual([line], module.primitive_projection(line.encode())["markers"])
        with self.assertRaises(ValueError):
            module.primitive_projection(((line + "\n") * 33).encode())
        with self.assertRaises(ValueError):
            module.primitive_projection(b"x" * (16 * 1024 * 1024 + 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
