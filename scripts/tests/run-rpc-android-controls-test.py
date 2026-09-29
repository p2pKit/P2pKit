#!/usr/bin/env python3
"""Offline negative controls for supplemental Android result admission, not Android runtime tests."""
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
path = Path(__file__).resolve().parents[1] / "run-rpc-android-controls.py"
spec = importlib.util.spec_from_file_location("rpc_art_controls", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AdmissionTests(unittest.TestCase):
    def result(self):
        fields = dict(rpcToken="a" * 32, rpcApi="24", rpcAbi="x86_64", rpcVm="Dalvik", rpcScope=module.SCOPE,
                      rpcOutcome="PASS", rpcCleanup="PASS", rpcCompleted=str(len(module.CONTROL_NAMES)))
        fields.update({f"rpcControl{i}": name for i, name in enumerate(module.CONTROL_NAMES, 1)})
        return fields

    def encode(self, values):
        return "".join(f"INSTRUMENTATION_RESULT: {k}={v}\n" for k, v in values.items()) + "INSTRUMENTATION_CODE: -1\n"

    def test_exact_complete_nonce_bound_result_is_accepted(self):
        values = self.result()
        self.assertEqual(values, module.assess_instrumentation(self.encode(values), "a" * 32))

    def test_each_missing_control_or_field_is_rejected(self):
        for key in self.result():
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                values = self.result()
                del values[key]
                module.assess_instrumentation(self.encode(values), "a" * 32)

    def test_failed_cleanup_wrong_device_runtime_and_nonce_are_rejected(self):
        for key, value in [("rpcOutcome", "FAIL"), ("rpcCleanup", "FAIL"), ("rpcToken", "b" * 32),
                           ("rpcApi", "37"), ("rpcVm", "OpenJDK"), ("rpcAbi", "arm64-v8a"), ("rpcCompleted", "0")]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                module.assess_instrumentation(self.encode({**self.result(), key: value}), "a" * 32)

    def test_duplicate_fields_terminals_and_oversized_output_are_rejected(self):
        raw = self.encode(self.result())
        for changed in (raw + "INSTRUMENTATION_RESULT: rpcOutcome=PASS\n", raw + "INSTRUMENTATION_CODE: -1\n",
                        raw.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: 0"),
                        raw.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: -10"),
                        raw.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: -1truncated"),
                        raw + "INSTRUMENTATION_CODE: malformed\n",
                        raw + "INSTRUMENTATION_FAILED: refused\n", raw + "x" * 262145):
            with self.assertRaises(RuntimeError):
                module.assess_instrumentation(changed, "a" * 32)

    def test_free_form_diagnostics_do_not_silently_become_an_accepted_result(self):
        with self.assertRaises(RuntimeError):
            module.assess_instrumentation(self.encode({**self.result(), "rpcFailureClass": "Unexpected"}), "a" * 32)


if __name__ == "__main__":
    unittest.main(verbosity=2)
