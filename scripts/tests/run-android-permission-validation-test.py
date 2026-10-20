#!/usr/bin/env python3
"""Synthetic permission-controller admission tests, not API37 runtime proof."""
import importlib.util
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("permission_validation", Path(__file__).resolve().parents[1] /
                                            "run-android-permission-validation.py")
p = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(p)
TOKEN, SOURCE, TREE = "a" * 32, "b" * 40, "c" * 40


def output(mode="revocation", changes=None, ready=False):
    fields = {"p2pkitToken": TOKEN, "p2pkitCompleted": "1", "p2pkitOutcome": "PASS", "p2pkitCleanup": "PASS",
              "p2pkitManager": "PASS", "p2pkitRawPregrant": "DENIED", "p2pkitRawRoute": "DENIED_THEN_ADMITTED",
              "p2pkitTraffic": "PASS", "p2pkitRecreation": "PASS", "p2pkitRequestSettled": "true",
              "p2pkitSentBytes": "40", "p2pkitReceivedBytes": "36"}
    if mode == "revoked-reentry":
        fields.update(p2pkitReentry="DENIED_AFTER_ATTRIBUTABLE_PERMISSION_KILL",
                      p2pkitSameInstanceRevocation="OS_PERMISSION_KILL_NOT_SAME_INSTANCE")
        test = "deniedReentryAfterPermissionDrivenExit"
    else:
        fields.update(p2pkitReentry="DENIED_SAME_MANAGER_AND_PROCESS", p2pkitSameInstanceRevocation="PASS")
        test = "permissionRecreationPinnedTcpAndRevocation"
    if ready:
        fields.update(p2pkitSameInstanceRevocation="NOT_EXECUTED", p2pkitPhase="awaiting-host-os-revocation")
    fields.update(changes or {})
    status = {**fields, "class": p.RUNNER, "test": test}
    text = "".join(f"INSTRUMENTATION_STATUS: {key}={value}\n" for key, value in status.items())
    if ready:
        return (text + "INSTRUMENTATION_STATUS_CODE: 2\n").encode()
    text += "INSTRUMENTATION_STATUS_CODE: 0\n"
    text += "".join(f"INSTRUMENTATION_RESULT: {key}={value}\n" for key, value in fields.items())
    return (text + "INSTRUMENTATION_CODE: -1\n").encode()


class PermissionValidationTests(unittest.TestCase):
    def test_graphics_option_requires_actual_supplier_declarations_and_positive_help(self):
        help_output = b"-feature: enable or disable individual feature overrides\n"
        defaults = b"GLDirectMem = off\nHasSharedSlotsHostMemoryAllocator = on\n"
        self.assertEqual(p.graphics_options(help_output, defaults), ("-feature", "GLDirectMem"))
        self.assertEqual(p.graphics_options(help_output, defaults.replace(b"off", b"on")),
                         ("-feature", "GLDirectMem"))
        self.assertEqual(p.graphics_options(help_output, defaults.replace(b"Allocator = on", b"Allocator = off")),
                         ("-feature", "GLDirectMem"))  # Default values are not effective capability proof.
        for invalid in (b"", defaults.replace(b"GLDirectMem", b"Other"), defaults + b"GLDirectMem=off\n",
                        defaults.replace(b"GLDirectMem = off", b"GLDirectMem = maybe"),
                        defaults + b"HasSharedSlotsHostMemoryAllocator=off\n"):
            with self.subTest(defaults=invalid), self.assertRaises(ValueError):
                p.graphics_options(help_output, invalid)
        for invalid in (b"", b"unrelated help text\n", b"unknown help topic: feature\n",
                        b"-feature: enable overrides\nWARNING: Unknown feature GLDirectMem\n"):
            with self.subTest(help=invalid), self.assertRaises(ValueError):
                p.graphics_options(invalid, defaults)

    def test_emulator_graphics_rejection_is_failure_even_with_successful_boot_text(self):
        p.Campaign.validate_emulator_boot(b"Graphics backend: gfxstream\nBoot completed\n")
        for warning in (b"Unknown feature: GLDirectMem", b"Feature name GLDirectMem is invalid",
                        b"unsupported option -feature", b"GLDirectMem unrecognized"):
            with self.subTest(warning=warning), self.assertRaises(ValueError):
                p.Campaign.validate_emulator_boot(warning + b"\nBoot completed\n")

    def test_graphics_preflight_records_supplier_bytes_and_never_runs_an_avd(self):
        help_output = b"-feature: enable or disable feature overrides\n"
        defaults = b"GLDirectMem=off\nHasSharedSlotsHostMemoryAllocator=on\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk, report = root / "sdk", root / "report"
            (sdk / "emulator/lib").mkdir(parents=True)
            report.mkdir()
            (sdk / "emulator/lib/advancedFeatures.ini").write_bytes(defaults)
            (sdk / "emulator/emulator").write_bytes(b"synthetic frontend identity, not executed")
            run = Mock(return_value=(0, help_output))
            self.assertEqual(p.Campaign.prepare_emulator(run=run, sdk=sdk, report=report), ("-feature", "GLDirectMem"))
            run.assert_called_once_with([sdk / "emulator/emulator", "-help-feature"], timeout=15)
            receipt = json.loads((report / "emulator-graphics-request.json").read_text())
            self.assertEqual(receipt["options"], ["-feature", "GLDirectMem"])
            self.assertEqual(receipt["supplierDefaultsSha256"], hashlib.sha256(defaults).hexdigest())
            self.assertEqual(receipt["helpSha256"], hashlib.sha256(help_output).hexdigest())
            self.assertEqual(receipt["effectiveGuestDmaSupport"], "NOT_ESTABLISHED_BY_PREFLIGHT")
            self.assertEqual((report / "emulator-feature-help.txt").read_bytes(), help_output)
            self.assertEqual((report / "emulator-feature-defaults.ini").read_bytes(), defaults)

    def test_graphics_override_is_campaign_only_without_backend_or_runtime_relaxation(self):
        source = (p.ROOT / "scripts/run-android-ui-validation.py").read_text()
        self.assertIn("campaign.prepare_emulator(run=run, sdk=sdk, report=report) if campaign is not None else ()", source)
        self.assertIn('"-gpu", "swiftshader", "-memory", "2048", "-cores", "2"', source)
        self.assertIn("*emulator_options]", source)
        self.assertIn('write_json(report / "emulator-request.json", {"argv": emulator_argv, "sourceCommit": source, "sourceTree": tree})', source)
        self.assertIn('campaign.validate_emulator_boot((report / "emulator.log").read_bytes())', source)
        self.assertNotIn("GLDirectMem", source)  # No default/API35 UI flag or user feature selector.

    def test_absent_completed_instrumentation_output_is_not_runner_or_root_cause_proof(self):
        for raw in (b"", b"Error type 2\nonError: commandError=true message=synthetic frontend failure\n"):
            self.assertEqual(p.completed_instrumentation_output(raw), "NO_INSTRUMENTATION_OUTPUT")
        for raw in (output(), b"INSTRUMENTATION_CODE: 0\n", b"INSTRUMENTATION_FAILED: crashed\n"):
            self.assertEqual(p.completed_instrumentation_output(raw), "INSTRUMENTATION_OUTPUT_PRESENT")
        with self.assertRaises(ValueError):
            p.terminal(b"INSTRUMENTATION_FAILED: crashed\n", TOKEN, "revocation")
        source = (p.ROOT / "scripts/run-android-permission-validation.py").read_text()
        self.assertLess(source.index('until(lambda: drained("revocation")'),
                        source.index('instrumentation_output["revocation"] = completed_instrumentation_output'))
        self.assertLess(source.index('until(lambda: drained("revoked-reentry")'),
                        source.index('instrumentation_output["revoked-reentry"] = completed_instrumentation_output'))

    def test_invalid_or_missing_remote_record_never_becomes_a_json_evidence_file(self):
        for raw in (b"cat: synthetic-record: No such file or directory\n", b"", b"[]", b"null",
                    b'{"outcome":"FAIL","outcome":"PASS"}'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                path = Path(directory)
                with self.assertRaises(ValueError):
                    p.store_retained_record(raw, path, "before-revocation.json")
                self.assertFalse(list(path.iterdir()))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.assertEqual(p.store_retained_record(b'{"fixture":true}', path, "before-revocation.json"),
                             {"fixture": True})
            self.assertEqual((path / "before-revocation.json").read_bytes(), b'{"fixture":true}')
            with self.assertRaises(ValueError):
                p.store_retained_record(b'{}', path, "../unowned.json")

    def test_failure_diagnostic_error_does_not_replace_original_failure_or_retry(self):
        for capture_error in (RuntimeError("synthetic retention failure"), SystemExit(2)):
            capture = Mock(side_effect=capture_error)
            original = ValueError("synthetic original no-output failure")
            receipt = None
            with self.assertRaises(ValueError) as caught:
                try:
                    raise original
                except BaseException:
                    receipt = p.attempt_failure_capture(capture)
                    raise
            self.assertIs(caught.exception, original)
            self.assertEqual(receipt, {"status": "ATTEMPTED", "failureType": type(capture_error).__name__})
            capture.assert_called_once_with()

    def test_survival_and_os_kill_have_distinct_success_claims(self):
        for mode in ("revocation", "revoked-reentry"):
            self.assertEqual(p.terminal(output(mode), TOKEN, mode)["p2pkitOutcome"], "PASS")
        with self.assertRaises(ValueError):
            p.terminal(output("revoked-reentry"), TOKEN, "revocation")

    def test_no_exit_zero_partial_duplicate_or_fabricated_old_scope_pass(self):
        bad = [b"INSTRUMENTATION_CODE: 0\n", output()[:-25],
               output() + b"INSTRUMENTATION_CODE: -1\n",
               output() + b"INSTRUMENTATION_RESULT: p2pkitOutcome=PASS\n",
               output().replace(b"permissionRecreationPinnedTcpAndRevocation", b"permissionRecreationAndPinnedTcp")]
        bad += [output(changes=change) for change in ({"p2pkitToken": "d" * 32}, {"p2pkitCompleted": "0"},
            {"p2pkitSameInstanceRevocation": "NOT_EXECUTED"}, {"p2pkitRawRoute": "PREGRANT_BYPASS"},
            {"p2pkitTraffic": "NOT_RUN"}, {"p2pkitCleanup": "FAIL"}, {"p2pkitFailureStage": "revoked"})]
        for raw in bad:
            with self.subTest(raw=raw[-80:]), self.assertRaises(ValueError):
                p.terminal(raw, TOKEN, "revocation")

    def test_host_revocation_requires_completed_source_uid_handoff(self):
        self.assertIsNone(p.ready_checkpoint(b"", TOKEN))
        self.assertEqual(p.ready_checkpoint(output(ready=True), TOKEN)["p2pkitTraffic"], "PASS")
        for change in ({"p2pkitTraffic": "NOT_RUN"}, {"p2pkitRawRoute": "PREGRANT_BYPASS"},
                       {"p2pkitToken": "d" * 32}, {"p2pkitRequestSettled": "false"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.ready_checkpoint(output(ready=True, changes=change), TOKEN)
        with self.assertRaises(ValueError):
            p.ready_checkpoint(output(ready=True) * 2, TOKEN)

    def test_live_handoff_accepts_every_byte_fragment_without_treating_it_as_eof(self):
        raw = "ⓘ synthetic non-record line\n".encode() + output(ready=True)
        for size in range(len(raw)):
            with self.subTest(size=size):
                self.assertIsNone(p.ready_checkpoint(raw[:size], TOKEN))
        self.assertIsNotNone(p.ready_checkpoint(raw, TOKEN))
        with self.assertRaises(ValueError):
            p.terminal(output()[:-1], TOKEN, "revocation")

    def test_live_peer_lines_allow_utf8_fragments_but_not_partial_receipts(self):
        receipt = "incoming from anon-" + "a" * 16 + ": <text 40B>"
        raw = ("[state] Starting → Running\n> " + receipt + "\n").encode()
        for size in range(len(raw)):
            with self.subTest(size=size):
                self.assertNotIn(receipt, p.live_lines(raw[:size]))
        self.assertIn(receipt, p.live_lines(raw))
        self.assertIn(receipt, p.final_peer_lines(raw + b"> "))
        for invalid in (raw[:-1], raw + b"unclosed diagnostic", raw + b"\xe2"):
            with self.assertRaises(ValueError):
                p.final_peer_lines(invalid)

    def test_peer_reply_uses_actual_maintained_cli_command(self):
        self.assertEqual(p.PEER_REPLY_PREFIX, "send jvm-")
        source = (p.ROOT / "samples/p2p-sample-desktop/src/main/kotlin/dev/p2pkit/sample/desktop/Main.kt").read_text()
        self.assertIn('"send" -> {', source)

    def test_actual_source_runtime_record_binding(self):
        base = {"token": TOKEN, "sourceCommit": SOURCE, "sourceTree": TREE, "sdk": 37, "targetSdk": 37}
        p.record_binding(base, TOKEN, SOURCE, TREE)
        for change in ({"sdk": 35}, {"targetSdk": 36}, {"token": "d" * 32}, {"sourceCommit": "e" * 40},
                       {"sourceTree": "f" * 40}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.record_binding({**base, **change}, TOKEN, SOURCE, TREE)

    def test_separate_entry_keeps_ui_selectors_closed_and_no_permission_grant_or_force_stop(self):
        self.assertEqual(set(p.owner.CASES), {"317", "324"})
        self.assertEqual(p.Campaign.API, 37)
        source = Path(p.__file__).read_text()
        self.assertIn('"pm", "revoke", PACKAGE, PERMISSION', source)
        self.assertNotIn('"pm", "grant"', source)
        self.assertNotIn('"force-stop"', source)
        instrumentation = (p.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime" /
                           "LanPermissionRevocation.kt").read_text()
        self.assertIn("ApplicationExitInfo.REASON_PERMISSION_CHANGE", instrumentation)
        self.assertNotIn("getTraceInputStream", instrumentation)


if __name__ == "__main__":
    unittest.main()
