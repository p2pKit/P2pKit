#!/usr/bin/env python3
"""Offline readback regression controls; no Windows runtime, workflow or network activity."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("rpc_windows_environment_evidence",
                                            ROOT / "scripts/rpc_windows_environment_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = evidence
SPEC.loader.exec_module(evidence)
NATIVE = ROOT / "samples/p2p-sample-rpc/native/windows-profile/tests/windows"


def wrapper(count=32, snapshot=True):
    return (b"PASS " + str(count).encode() + evidence.CONTROL_SUFFIX + b"\n$result.hiveObserverPhases = $phases\n" +
            (b"$result.hiveObserverSnapshot = $null" if snapshot else b"") +
            (b"\n" + evidence.DIAGNOSTIC_RETIRE_MARKER if count == 42 else b""))


def passing_handles():
    return dict(knownHandleAuditScope=evidence.HANDLE_SCOPE, knownHandleAuditPassed=True, knownHandleChecked=3,
                knownHandleAbsent=2, knownHandleReused=1, knownHandleLeaked=0, knownHandleError=0,
                knownHandleHelperControlsPassed=6)


class JsonEvidence(unittest.TestCase):
    def test_unambiguous_json_and_key_order(self):
        one = evidence.load_json('{"ready":true,"counts":[0,1]}')
        other = evidence.load_json('{"counts":[0,1],"ready":true}')
        evidence.require_same_json(one, other)

    def test_nested_boolean_integer_and_float_coercion_refused(self):
        for actual, claimed in ((True, 1), (False, 0), (1, 1.0), ({"retired": 1}, {"retired": True}),
                                ([{"error": False}], [{"error": 0}]), ([1], [1, 2]),
                                ({"a": 1}, {"b": 1})):
            with self.subTest(actual=actual, claimed=claimed), self.assertRaises(ValueError):
                evidence.require_same_json(actual, claimed)

    def test_duplicate_fields_and_non_json_numbers_refused(self):
        for raw in ('{"ready":false,"ready":true}', '{"nested":{"n":0,"n":1}}',
                    '{"n":NaN}', '{"n":Infinity}', '{"n":-Infinity}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                evidence.load_json(raw)


class Contracts(unittest.TestCase):
    def test_real_wrappers_are_understood(self):
        self.assertEqual(evidence.profile_contract((NATIVE / "check-hosted-profile-initialization.ps1").read_bytes())
                      .observer_controls, 42)
        self.assertTrue(evidence.known_handles_required(
            (NATIVE / "check-hosted-job-inheritance-environment.ps1").read_bytes()))

    def test_observer_inventory_follows_exact_source_not_candidate(self):
        for count in (18, 32, 33, 42):
            contract = evidence.profile_contract(wrapper(count))
            evidence.validate_observer_controls(b"PASS " + str(count).encode() + evidence.CONTROL_SUFFIX + b"\n",
                                                b"", contract)
            for wrong in set((18, 32, 33, 42)) - {count}:
                with self.subTest(count=count, wrong=wrong), self.assertRaises(ValueError):
                    evidence.validate_observer_controls(b"PASS " + str(wrong).encode() + evidence.CONTROL_SUFFIX + b"\n",
                                                        b"", contract)

    def test_unreviewed_or_ambiguous_counts_rejected(self):
        for raw in (wrapper(17), wrapper(0), wrapper() + wrapper()):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                evidence.profile_contract(raw)

    def test_diagnostic_contract_cannot_be_omitted_or_inserted_in_historical_wrapper(self):
        for raw in (wrapper(42).replace(evidence.DIAGNOSTIC_RETIRE_MARKER, b""),
                    wrapper(33) + evidence.DIAGNOSTIC_RETIRE_MARKER,
                    wrapper(42) + evidence.DIAGNOSTIC_RETIRE_MARKER, wrapper(42, False)):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                evidence.profile_contract(raw)

    def test_partial_handle_contract_rejected(self):
        self.assertFalse(evidence.known_handles_required(b"historical wrapper"))
        with self.assertRaises(ValueError):
            evidence.known_handles_required(b"knownHandleAuditScope")

    def test_control_output_requires_exact_single_line_and_empty_stderr(self):
        contract = evidence.profile_contract(wrapper())
        valid = b"PASS 32" + evidence.CONTROL_SUFFIX
        for stdout, stderr in ((valid, b""), (valid + b"\n\n", b""), (valid + b"\n", b"warning")):
            with self.subTest(stdout=stdout, stderr=stderr), self.assertRaises(ValueError):
                evidence.validate_observer_controls(stdout, stderr, contract)
        evidence.validate_observer_controls(valid + b"\r\n", b"", contract)


class Diagnostics(unittest.TestCase):
    def test_present_absent_and_error_are_observations_only(self):
        for state, status in ((1, 0), (2, 259), (3, 1018), (3, 0xffffffff)):
            text = f"P2PKIT_HIVE_PHASE 3\nP2PKIT_HIVE_SNAPSHOT {state} {status}\n".encode()
            receipt = {"result": "NOT_COMPLETED", "hiveObserverPhases": [3], "hiveObserverSnapshot":
                       {"state": state, "status": status, "scope": evidence.SNAPSHOT_SCOPE}}
            checked = evidence.validate_profile_diagnostics(receipt, text, evidence.profile_contract(wrapper()))
            self.assertEqual(checked["snapshot"]["state"], state)
            self.assertNotIn("passed", checked)

    def test_null_snapshot_and_legacy_phase_only(self):
        evidence.validate_profile_diagnostics({"hiveObserverPhases": [], "hiveObserverSnapshot": None}, b"",
                                              evidence.profile_contract(wrapper()))
        evidence.validate_profile_diagnostics({"hiveObserverPhases": [1, 2, 3]},
                                              b"P2PKIT_HIVE_PHASE 1\nP2PKIT_HIVE_PHASE 2\nP2PKIT_HIVE_PHASE 3\n",
                                              evidence.profile_contract(wrapper(18, False)))
        evidence.validate_profile_diagnostics({}, b"", evidence.profile_contract(b"historical wrapper"))

    def test_missing_snapshot_field_cannot_downgrade_new_source(self):
        with self.assertRaises(ValueError):
            evidence.validate_profile_diagnostics({"hiveObserverPhases": []}, b"", evidence.profile_contract(wrapper()))

    def test_legacy_source_cannot_claim_new_snapshot(self):
        with self.assertRaises(ValueError):
            evidence.validate_profile_diagnostics({"hiveObserverPhases": [], "hiveObserverSnapshot": None}, b"",
                                                  evidence.profile_contract(wrapper(18, False)))

    def test_bad_wire_diagnostics_rejected(self):
        for line in (b"P2PKIT_HIVE_SNAPSHOT 1 259\n", b"P2PKIT_HIVE_SNAPSHOT 2 0\n",
                     b"P2PKIT_HIVE_SNAPSHOT 3 0\n", b"P2PKIT_HIVE_SNAPSHOT 3 259\n",
                     b"P2PKIT_HIVE_SNAPSHOT 3 4294967296\n", b"P2PKIT_HIVE_PHASE 9\n",
                     b"P2PKIT_HIVE_PHASE 1", b"private value\n", b"x" * 257,
                     b"P2PKIT_HIVE_PHASE 1\n" * 2, b"P2PKIT_HIVE_SNAPSHOT 1 0\n" * 2):
            with self.subTest(line=line), self.assertRaises(ValueError):
                evidence.parse_hive_diagnostics(line)

    def test_snapshot_receipt_mismatch_and_type_confusion_rejected(self):
        text = b"P2PKIT_HIVE_PHASE 1\nP2PKIT_HIVE_SNAPSHOT 1 0\n"
        valid = {"hiveObserverPhases": [1], "hiveObserverSnapshot":
                 {"state": 1, "status": 0, "scope": evidence.SNAPSHOT_SCOPE}}
        mutations = (("state", True), ("status", False), ("status", 259), ("scope", "ACCEPTED"))
        for field, value in mutations:
            bad = copy.deepcopy(valid); bad["hiveObserverSnapshot"][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                evidence.validate_profile_diagnostics(bad, text, evidence.profile_contract(wrapper()))
        for value in ([True], [2], None):
            bad = copy.deepcopy(valid); bad["hiveObserverPhases"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                evidence.validate_profile_diagnostics(bad, text, evidence.profile_contract(wrapper()))

    def test_diagnostic_miss_cannot_be_relabelled_pass_but_historical_wait_can_complete(self):
        receipt = {"result": "PASS", "hiveObserverPhases": [], "hiveObserverSnapshot":
                   {"state": 2, "status": 259, "scope": evidence.SNAPSHOT_SCOPE}}
        text = b"P2PKIT_HIVE_SNAPSHOT 2 259\n"
        with self.assertRaises(ValueError):
            evidence.validate_profile_diagnostics(receipt, text, evidence.profile_contract(wrapper(42)))
        for count in (32, 33):
            evidence.validate_profile_diagnostics(receipt, text, evidence.profile_contract(wrapper(count)))
        for result in ("NOT_COMPLETED", "FAIL"):
            receipt["result"] = result
            checked = evidence.validate_profile_diagnostics(receipt, text, evidence.profile_contract(wrapper(42)))
            self.assertEqual(checked["snapshot"]["state"], 2)
            self.assertNotIn("passed", checked)

    def test_snapshot_error_not_relabelled_pass(self):
        receipt = {"result": "PASS", "hiveObserverPhases": [], "hiveObserverSnapshot":
                   {"state": 3, "status": 1018, "scope": evidence.SNAPSHOT_SCOPE}}
        with self.assertRaises(ValueError):
            evidence.validate_profile_diagnostics(receipt, b"P2PKIT_HIVE_SNAPSHOT 3 1018\n",
                                                  evidence.profile_contract(wrapper()))


class ProfileCompletion(unittest.TestCase):
    def setUp(self):
        self.contract = evidence.profile_contract(wrapper())
        self.receipt = {"result": "PASS", "controlExecutable": {"sha256": "a" * 64, "bytes": 100},
                        "controlExecution": {"passed": True, "exitCode": 0, "elapsedMs": 1,
                                             "processExitObserved": True, "finalizationCompleted": True,
                                             "timedOut": False, "outputExceeded": False}}
        self.observation = dict(namespaceAbsenceObserved=True, namespaceRetired=True, namespaceOpenStatus=0,
                                namespaceEnumerationStatus=259, namespaceNotificationStatus=0,
                                namespaceCloseStatus=0, namespaceSystemError=0, namespaceScans=1,
                                hiveQueryError=0, hiveCloseError=0)

    def test_complete_current_source_and_partial_failure(self):
        evidence.validate_profile_completion(self.receipt, self.observation, self.contract)
        evidence.validate_profile_completion({"result": "NOT_COMPLETED"}, None, self.contract)
        evidence.validate_profile_completion({"result": "PASS"}, {}, evidence.profile_contract(b"pre-observer"))

    def test_required_control_fields_cannot_be_omitted(self):
        for field in ("controlExecutable", "controlExecution"):
            bad = copy.deepcopy(self.receipt); del bad[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.validate_profile_completion(bad, self.observation, self.contract)
        for field in self.receipt["controlExecution"]:
            bad = copy.deepcopy(self.receipt); del bad["controlExecution"][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.validate_profile_completion(bad, self.observation, self.contract)

    def test_control_metadata_and_execution_type_confusion_rejected(self):
        for block, field, values in (("controlExecutable", "sha256", ("a" * 63, 123)),
                                     ("controlExecutable", "bytes", (0, True, 32 * 1024 * 1024 + 1)),
                                     ("controlExecution", "passed", (1, False)),
                                     ("controlExecution", "exitCode", (False, 1)),
                                     ("controlExecution", "elapsedMs", (-1, 10000, False)),
                                     ("controlExecution", "processExitObserved", (1, False)),
                                     ("controlExecution", "finalizationCompleted", (1, False)),
                                     ("controlExecution", "timedOut", (0, True)),
                                     ("controlExecution", "outputExceeded", (0, True))):
            for value in values:
                bad = copy.deepcopy(self.receipt); bad[block][field] = value
                with self.subTest(block=block, field=field, value=value), self.assertRaises(ValueError):
                    evidence.validate_profile_completion(bad, self.observation, self.contract)

    def test_all_namespace_fields_required(self):
        for field in self.observation:
            bad = self.observation.copy(); del bad[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.validate_profile_completion(self.receipt, bad, self.contract)

    def test_namespace_strict_types_and_failed_retirement(self):
        for field, original in self.observation.items():
            wrong_values = (1, False) if type(original) is bool else (False, -1, original + 1)
            if field == "namespaceScans":
                wrong_values = (True, 0, -1, 65537)
            for value in wrong_values:
                bad = self.observation.copy(); bad[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    evidence.validate_profile_completion(self.receipt, bad, self.contract)


class KnownHandles(unittest.TestCase):
    def test_exact_audit_and_legacy(self):
        self.assertEqual(evidence.validate_known_handles(passing_handles(), True, True), passing_handles())
        self.assertIsNone(evidence.validate_known_handles({}, False, True))

    def test_missing_fields_cannot_downgrade(self):
        for field in evidence.HANDLE_KEYS:
            bad = passing_handles(); del bad[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                evidence.validate_known_handles(bad, True, True)
        with self.assertRaises(ValueError):
            evidence.validate_known_handles(passing_handles(), False, True)

    def test_leaks_errors_wrong_counts_and_types_refused(self):
        for field, values in {
            "knownHandleAuditScope": ["EXHAUSTIVE"], "knownHandleAuditPassed": [False, 1],
            "knownHandleChecked": [2, 4, True], "knownHandleAbsent": [-1, 3, 2.0],
            "knownHandleReused": [0, 2], "knownHandleLeaked": [1], "knownHandleError": [5, 0x100000000],
            "knownHandleHelperControlsPassed": [5, 7],
        }.items():
            for value in values:
                bad = passing_handles(); bad[field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    evidence.validate_known_handles(bad, True, True)

    def test_partial_failure_preserved_not_promoted(self):
        failure = passing_handles()
        failure.update(knownHandleAuditPassed=False, knownHandleChecked=1, knownHandleAbsent=1,
                       knownHandleReused=0, knownHandleError=5)
        evidence.validate_known_handles(failure, True, False)
        with self.assertRaises(ValueError):
            evidence.validate_known_handles(failure, True, True)

    def test_claimed_pass_still_requires_all_controls_in_failed_run(self):
        bad = passing_handles(); bad["knownHandleError"] = 6
        with self.assertRaises(ValueError):
            evidence.validate_known_handles(bad, True, False)


if __name__ == "__main__":
    unittest.main()
