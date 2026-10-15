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
        instance.ci_native_components = Mock()
        instance.invoke = Mock(side_effect=[{"count": count, "productExitCode": 0} for count in (49, 25, 28)])
        instance.output = lambda proof, **kwargs: f'Ran {proof["count"]} tests in 0.01s\nOK\n'.encode()
        instance.execute()
        controls.assert_called_once_with(instance)
        instance.ci_native_components.assert_called_once_with()
        multicast.assert_not_called()
        self.assertEqual(instance.result["result"], "PASS_COMPONENT_CONTROLS_ONLY")
        self.assertEqual(instance.result["fixture"], "NOT_RUN")
        self.assertEqual(instance.result["counts"], {"ci-source-admission": 49, "ci-metadata": 25,
                                                   "terminal-refusal": 28})
        self.assertTrue(all(call.args[2] == 90 for call in instance.invoke.call_args_list))

    def test_incomplete_component_inventory_cannot_receive_success(self):
        instance = module.Diagnostic.__new__(module.Diagnostic)
        instance.profile = "terminal-components"
        instance.result = {"counts": {}, "result": "FAIL"}
        instance.qualification = SimpleNamespace(Qualification=SimpleNamespace(native_controls=lambda _: None))
        instance.invoke = lambda *args, **kwargs: {"productExitCode": 0}
        instance.output = lambda *args, **kwargs: b"Ran 1 tests in 0.01s\nOK\n"
        with self.assertRaises(ValueError):
            instance.execute()
        self.assertEqual(instance.result["result"], "FAIL")

    def test_component_failure_projection_exposes_only_reviewed_test_names(self):
        raw = (b'FAIL: test_known (__main__.Tests)\nprivate machine path\n'
               b'ERROR: test_PRIVATE_PAYLOAD (__main__.Tests)\n')
        projected = module.component_failure_projection(raw, 'def test_known():\n    pass\n')
        self.assertEqual(projected["failedTests"], ["test_known"])
        self.assertEqual(projected["unknownFailureCount"], 1)
        self.assertNotIn("PRIVATE_PAYLOAD", json.dumps(projected))
        self.assertNotIn("private machine", json.dumps(projected))

    def test_component_failure_is_retained_before_refusing_nonzero_product(self):
        instance = module.Diagnostic.__new__(module.Diagnostic)
        instance.profile = "terminal-components"
        instance.result = {"counts": {}, "result": "FAIL"}
        instance.qualification = SimpleNamespace(Qualification=SimpleNamespace(native_controls=lambda _: None))
        instance.invoke = lambda *args, **kwargs: {"productExitCode": 1}
        instance.output = lambda *args, **kwargs: b"FAIL: test_exact_pr_synthetic_merge_admitted (__main__.Tests)\n"
        with self.assertRaises(ValueError):
            instance.execute()
        self.assertEqual(instance.result["result"], "FAIL")
        self.assertEqual(instance.result["componentDiagnostics"]["ci-source-admission"]["failedTests"],
                         ["test_exact_pr_synthetic_merge_admitted"])

    def test_no_repeated_command(self):
        instance = module.Diagnostic.__new__(module.Diagnostic)
        instance.result = {"commands": [{"purpose": "already-run"}]}
        with self.assertRaises(ValueError):
            instance.invoke("already-run", [], 45)


class NativeClockProjectionTest(unittest.TestCase):
    def setUp(self):
        self.before = {"schema": 1, "clock": module.ci_clock.CLOCK,
                       "bootSession": "12345678-1234-1234-1234-123456789abc",
                       "monotonicNs": 100_000_000_000, "wallNs": 10000_000_000_000, "sampleSpanNs": 1_000_000}
        self.native = {**self.before, "monotonicNs": 101_000_000_000, "wallNs": 10001_000_000_000}
        self.after = {**self.before, "monotonicNs": 102_000_000_000, "wallNs": 10002_000_000_000}
        self.native.pop("schema")

    def raw(self, **changes):
        return json.dumps({**self.native, **changes}).encode()

    def test_comparison_exports_only_closed_scoped_booleans_and_hash(self):
        result = module.native_clock_projection(self.raw(), self.before, self.after)
        self.assertEqual(set(result), {"scope", "clock", "sameBoot", "withinParentBracket",
                                      "originalAnchorPreserved", "logSha256"})
        self.assertEqual(result["scope"], "SHARED_CLOCK_BRACKET_NOT_TERMINAL_OR_MULTICAST_QUALIFICATION")
        self.assertTrue(result["sameBoot"] and result["withinParentBracket"] and result["originalAnchorPreserved"])
        for private in (self.before["bootSession"], str(self.native["monotonicNs"]), str(self.native["wallNs"])):
            self.assertNotIn(private, json.dumps(result))

    def test_native_schema_and_unrecognized_keys_are_not_silently_overwritten(self):
        for changes in ({"schema": 1}, {"schema": False}, {"extra": "value"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                module.native_clock_projection(self.raw(**changes), self.before, self.after)
        for key in self.native:
            changed = dict(self.native)
            changed.pop(key)
            with self.subTest(key=key), self.assertRaises(ValueError):
                module.native_clock_projection(json.dumps(changed).encode(), self.before, self.after)

    def test_duplicate_keys_encoding_size_and_nonfinite_are_refused(self):
        raw = self.raw()
        for invalid in (raw[:-1] + b',"wallNs":10001000000000}', b"", b" " * 4097,
                        raw.decode().encode("utf-16"), b'{"wallNs": NaN}', b"[]", b"null"):
            with self.subTest(size=len(invalid)), self.assertRaises(ValueError):
                module.native_clock_projection(invalid, self.before, self.after)

    def test_changed_boot_clock_or_float_ns_is_refused(self):
        for changes in ({"bootSession": "22345678-1234-1234-1234-123456789abc"}, {"clock": "UPTIME"},
                        {"monotonicNs": float(self.native["monotonicNs"])}, {"sampleSpanNs": True}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                module.native_clock_projection(self.raw(**changes), self.before, self.after)

    def test_process_local_origin_and_sample_outside_actual_parent_bracket_are_refused(self):
        for mono, wall in ((1000, self.native["wallNs"]), (self.before["monotonicNs"], self.before["wallNs"]),
                           (self.after["monotonicNs"], self.after["wallNs"])):
            with self.subTest(mono=mono), self.assertRaises(ValueError):
                module.native_clock_projection(self.raw(monotonicNs=mono, wallNs=wall), self.before, self.after)

    def test_native_span_must_finish_before_parent_after_sample(self):
        native = self.raw(monotonicNs=self.after["monotonicNs"] - 1000, wallNs=self.after["wallNs"] - 1000)
        with self.assertRaises(ValueError):
            module.native_clock_projection(native, self.before, self.after)

    def test_pairwise_allowed_drift_cannot_replace_original_anchor(self):
        native = self.raw(wallNs=self.native["wallNs"] + 700_000_000)
        after = {**self.after, "wallNs": self.after["wallNs"] + 1400_000_000}
        with self.assertRaises(ValueError):
            module.native_clock_projection(native, self.before, after)

    def test_terminal_candidate_is_not_invoked_by_component_adapter(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            instance = module.Diagnostic.__new__(module.Diagnostic)
            instance.private = Path(directory) / "private"
            instance.private.mkdir()
            instance.state = Path(directory)
            instance.result = {"counts": {}, "observations": {}}
            instance.runner = SimpleNamespace(file_digest=lambda _: "a" * 64)
            instance.invoke = Mock(side_effect=lambda purpose, *args, **kwargs:
                                   {"purpose": purpose, "productExitCode": 0})
            outputs = {"ci-native-default-refusal":
                           b"PASS: default Terminal ci refusal exit=125; NO_APPLICATION_EXECUTION\n",
                       "ci-native-clock": self.raw(),
                       "ci-native-envelope-controls":
                           b"PASS: apple-ci-envelope/195 deterministic controls; NOT_NATIVE_OR_RELEASE_QUALIFICATION\n"}
            instance.output = lambda proof, *args, **kwargs: (
                b"" if kwargs.get("stream") == "stderr" else outputs[proof["purpose"]])
            with patch.object(module.ci_clock, "admit_runtime"), \
                    patch.object(module.ci_clock, "sample_clock", side_effect=[self.before, self.after]):
                instance.ci_native_components()
            calls = instance.invoke.call_args_list
            self.assertEqual([call.args[0] for call in calls], ["ci-native-compile-default", "ci-native-compile-candidate",
                "ci-native-compile-fixture", "ci-native-compile-disabled-control", "ci-native-default-refusal",
                "ci-native-envelope-controls", "ci-native-clock"])
            self.assertTrue(calls[4].args[1][0].endswith("ci-terminal-disabled-control"))
            self.assertFalse(any(call.kwargs.get("allow_failure") for call in calls))
            self.assertFalse(any(call.args[1][0].endswith(("ci-terminal-candidate", "ci-terminal-default")) for call in calls))
            self.assertEqual(instance.result["candidateExecution"], "NOT_RUN")

    def test_canonical_receipt_checker_still_refuses_raw_expected_red_125(self):
        checker = module.load("ci_refusal_receipt", "check-audit-receipt.py")
        with self.assertRaisesRegex(ValueError, "audit infrastructure failure is not a policy rejection"):
            checker.validate({"schema": 1}, 125, "ci-native-default-refusal", ROOT, ROOT / "gradlew", ["unused"])


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
