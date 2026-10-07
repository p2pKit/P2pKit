#!/usr/bin/env python3
"""Offline rejection controls for the isolated diagnostic, not native acceptance."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("lan_host_diagnostic", ROOT / "scripts/diagnostics/intel-lan-host/run.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)
TOKEN = "a" * 32


def fixture(arm="CLI", discovered=False):
    peer = {key: 0 for key in D.COUNTERS}
    peer.update({key: False for key in D.PEER_BOOLS})
    peer.update(listenerReady=1, browserReady=1, listenerCancelled=True, browserCancelled=True,
                listenerLastState="ready", browserLastState="ready",
                listenerError={"domain": "none", "code": 0}, browserError={"domain": "none", "code": 0})
    if discovered:
        peer.update(expectedPeerObserved=True, resultCallbacks=1, maximumResultCount=1,
                    ownRegistrationObserved=True, registrationAdded=1)
    return {"schema": 1, "diagnosticOnly": True, "mode": arm.lower(),
            "outcome": "discovered" if discovered else "notDiscovered", "windowMilliseconds": 30000,
            "observationElapsedMilliseconds": 30001, "cleanupElapsedMilliseconds": 10,
            "isSimulatorBuild": True, "isX86_64Build": True, "counterOverflow": False,
            "packaging": {key: arm == "APP" for key in D.PACKAGE_KEYS},
            "peers": [copy.deepcopy(peer), copy.deepcopy(peer)],
            "cleanup": {"listenersCreated": 2, "listenersCancelled": 2, "browsersCreated": 2,
                        "browsersCancelled": 2, "complete": True}}


def streams(probe=None, arm="CLI", token=TOKEN, **extra):
    value = {"schema": 1, "token": token, "probe": fixture(arm) if probe is None else probe}
    if arm == "APP":
        value.update(permission="notObserved", appNotRunning=True)
    value.update(extra)
    marker = "P2PKIT_LAN_HOST_V1 " if arm == "CLI" else "P2PKIT_LAN_APP_V1 "
    return {"stdout": (marker + json.dumps(value) + "\n").encode(), "stderr": b""}


class DiagnosticControls(unittest.TestCase):
    def test_negative_cli_is_data_not_discovery_success(self):
        result = D.probe_result(streams(), "CLI", TOKEN)
        self.assertEqual("notDiscovered", result["probe"]["outcome"])
        self.assertNotIn(TOKEN, json.dumps(result))
        self.assertEqual(64, len(result["originals"]["stdoutSha256"]))

    def test_app_requires_real_package_and_retired_state(self):
        value = D.probe_result(streams(arm="APP"), "APP", TOKEN)
        self.assertEqual("notObserved", value["permission"])
        for key in D.PACKAGE_KEYS:
            bad = fixture("APP")
            bad["packaging"][key] = False
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.probe_result(streams(bad, "APP"), "APP", TOKEN)
        with self.assertRaises(ValueError):
            D.probe_result(streams(arm="APP", appNotRunning=False), "APP", TOKEN)

    def test_success_requires_both_owned_other_peers(self):
        good = fixture("APP", True)
        self.assertEqual("discovered", D.validate_probe(good, "APP")["outcome"])
        good["peers"][1]["expectedPeerObserved"] = False
        with self.assertRaises(ValueError):
            D.validate_probe(good, "APP")

    def test_listener_ready_does_not_claim_registration(self):
        good = fixture()
        D.validate_probe(good, "CLI")
        self.assertFalse(good["peers"][0]["ownRegistrationObserved"])
        good["peers"][0]["ownRegistrationObserved"] = True
        with self.assertRaises(ValueError):
            D.validate_probe(good, "CLI")

    def test_stale_duplicate_missing_or_unbounded_result_is_rejected(self):
        with self.assertRaises(ValueError):
            D.probe_result(streams(token="b" * 32), "CLI", TOKEN)
        for stdout in (b"", streams()["stdout"] * 2, b"P2PKIT_LAN_HOST_V1 " + b"x" * 8193):
            with self.subTest(length=len(stdout)), self.assertRaises(ValueError):
                D.probe_result({"stdout": stdout, "stderr": b""}, "CLI", TOKEN)

    def test_duplicate_json_and_unapproved_text_fields_are_rejected(self):
        bad = streams()["stdout"].replace(b'"schema": 1', b'"schema": 1, "schema": 1', 1)
        with self.assertRaises(ValueError):
            D.probe_result({"stdout": bad, "stderr": b""}, "CLI", TOKEN)
        with self.assertRaises(ValueError):
            D.probe_result(streams(address="private.invalid"), "CLI", TOKEN)
        bad = fixture()
        bad["peers"][0]["endpoint"] = "not-for-projection"
        with self.assertRaises(ValueError):
            D.validate_probe(bad, "CLI")

    def test_no_unsafe_cleanup_or_overflow_progression(self):
        for outcome in ("cleanupUnconfirmed", "counterOverflow", "timingInvalid"):
            bad = fixture()
            bad["outcome"] = outcome
            with self.subTest(outcome=outcome), self.assertRaises(ValueError):
                D.validate_probe(bad, "CLI")
        for key, value in (("complete", False), ("listenersCancelled", 1), ("browsersCreated", 1)):
            bad = fixture()
            bad["cleanup"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "CLI")

    def test_wrong_arch_mode_and_boolean_counts_rejected(self):
        for key, value in (("isSimulatorBuild", False), ("isX86_64Build", False), ("mode", "app"),
                           ("schema", True), ("windowMilliseconds", 60000), ("observationElapsedMilliseconds", 29999),
                           ("cleanupElapsedMilliseconds", 5001)):
            bad = fixture()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                D.validate_probe(bad, "CLI")
        bad = fixture()
        bad["peers"][0]["listenerReady"] = True
        with self.assertRaises(ValueError):
            D.validate_probe(bad, "CLI")

    def test_error_domains_and_numeric_bounds_closed(self):
        for domain, code in (("arbitrary-error", 0), ("none", 1), ("posix", 2 ** 31), ("dns", True)):
            bad = fixture()
            bad["peers"][0]["browserError"] = {"domain": domain, "code": code}
            with self.subTest(domain=domain, code=code), self.assertRaises(ValueError):
                D.validate_probe(bad, "CLI")

    def test_summary_is_bounded_and_token_free(self):
        import io
        from contextlib import redirect_stdout
        output = io.StringIO()
        with redirect_stdout(output):
            D.emit("CLI", D.probe_result(streams(), "CLI", TOKEN), {"commit": "b" * 40, "tree": "c" * 40},
                   {"GITHUB_RUN_ID": "1", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_JOB": "ios-x64"})
        self.assertLessEqual(len(output.getvalue()), 8192 + 27)
        self.assertNotIn(TOKEN, output.getvalue())
        self.assertIn('"qualification":false', output.getvalue())

    def test_late_command_fails_before_spawn_and_startup_supplier_unchanged(self):
        with mock.patch.object(D, "EXECUTION_END", 139), mock.patch.object(D.time, "monotonic", return_value=0), \
                mock.patch.object(D.GATE, "_intel_capture_phase") as capture:
            with self.assertRaises(ValueError):
                D.command(Path("/unused"), "compile-cli", ["/unused"])
            capture.assert_not_called()
        self.assertEqual(300, D.GATE.INTEL_BOOTSTATUS_SECONDS)
        self.assertEqual(120, D.GATE.simulator.SECONDS)
        self.assertEqual((15, 5), (D.GATE.TERMINATION_GRACE_SECONDS, D.GATE.TERMINATION_KILL_SECONDS))

    def test_source_has_no_product_build_or_privacy_bypass(self):
        source = (ROOT / "scripts/diagnostics/intel-lan-host/run.py").read_text()
        self.assertNotIn("gradlew", source)
        self.assertNotIn("TCC.db", source)
        self.assertNotIn('"privacy"', source)
        self.assertIn('"test-without-building"', source)
        self.assertIn('"-test-iterations", "1"', source)
        self.assertIn("owner.prepare()", source)
        self.assertIn("owner.retire()", source)


if __name__ == "__main__":
    unittest.main(failfast=True)
