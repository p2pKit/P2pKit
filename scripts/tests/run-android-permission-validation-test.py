#!/usr/bin/env python3
"""Synthetic permission-controller admission tests, not API37 runtime proof."""
import importlib.util
from pathlib import Path
import sys
import unittest

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
