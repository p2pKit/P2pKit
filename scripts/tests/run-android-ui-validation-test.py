#!/usr/bin/env python3
"""Offline admission fixtures only; no Gradle, Android runtime, device or network."""
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import unittest

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("android_ui", Path(__file__).resolve().parents[1] /
                                            "run-android-ui-validation.py")
ui = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ui)
TOKEN = "a" * 32
SOURCE = "b" * 40
TREE = "c" * 40


def result(case="317", changes=None):
    fields = {"p2pkitToken": TOKEN, "p2pkitCompleted": "1", "p2pkitOutcome": ui.PASS,
              "p2pkitEvidence": f"no_backup/ui-{case}-{TOKEN}", "class": ui.CASES[case][0],
              "test": ui.CASES[case][1], "numtests": "1", "current": "1"}
    if case == "317":
        fields["p2pkitCleanup"] = "RETIRED_OWNED_OBSERVERS"
    fields.update(changes or {})
    status = "".join(f"INSTRUMENTATION_STATUS: {key}={value}\n" for key, value in fields.items())
    final = "".join(f"INSTRUMENTATION_RESULT: {key}={value}\n" for key, value in fields.items())
    return (status + "INSTRUMENTATION_STATUS_CODE: 0\n" + final + "INSTRUMENTATION_CODE: -1\n").encode()


def report(case="317", changes=None):
    value = {"case": case, "sourceCommit": SOURCE, "declaredSourceTree": TREE, "api": 35,
             "targetSdk": 37, "outcome": ui.PASS}
    if case == "317":
        value.update(token=TOKEN, cleanupFailures=[],
                     independentVisualAndMutationReview="REQUIRED_NOT_PERFORMED_BY_RUNNER")
    else:
        value.update(cleanup=[{"step": "fixture only", "outcome": "RETIRED"}], lifecycleViolation=False)
    value.update(changes or {})
    return json.dumps(value).encode()


def archive(entries):
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as target:
        for name, content, kind in entries:
            info = tarfile.TarInfo(name)
            info.type = kind
            info.size = len(content) if kind == tarfile.REGTYPE else 0
            info.linkname = "result.json" if kind == tarfile.SYMTYPE else ""
            target.addfile(info, io.BytesIO(content) if kind == tarfile.REGTYPE else None)
    return out.getvalue()


class AndroidUiAdmissionTests(unittest.TestCase):
    def test_both_explicit_synthetic_completed_bundles(self):
        for case in ui.CASES:
            self.assertEqual(ui.instrumentation_result(result(case), case, TOKEN)["p2pkitOutcome"], ui.PASS)

    def test_crash_partial_duplicate_wrong_token_and_scope_fail_closed(self):
        raw = result()
        invalid = [b"INSTRUMENTATION_CODE: 0\n", raw.rsplit(b"INSTRUMENTATION_CODE:", 1)[0],
                   raw.replace(b"INSTRUMENTATION_STATUS_CODE: 0", b"INSTRUMENTATION_STATUS_CODE: -2"),
                   raw + b"INSTRUMENTATION_CODE: -1\n", raw + b"INSTRUMENTATION_RESULT: p2pkitCompleted=1\n",
                   raw + b"INSTRUMENTATION_FAILED: crashed\n",
                   raw.replace(b"INSTRUMENTATION_RESULT: p2pkitCompleted=1", b"INSTRUMENTATION_RESULT: p2pkitCompleted=0")]
        invalid += [result(changes=change) for change in (
            {"p2pkitToken": "d" * 32}, {"p2pkitCompleted": "0"}, {"p2pkitOutcome": "PASS"},
            {"p2pkitCleanup": "FAIL"}, {"p2pkitEvidence": "no_backup/unowned"},
            {"class": "some.OtherRunner"}, {"p2pkitRetention": "FAIL"}, {"p2pkitFailureStage": "render"})]
        for malformed in invalid:
            with self.subTest(raw=malformed[-100:]), self.assertRaises(ValueError):
                ui.instrumentation_result(malformed, "317", TOKEN)

    def test_retained_reports_match_exact_source_and_do_not_promote_review(self):
        for case in ui.CASES:
            self.assertEqual(ui.validate_report(report(case), case, TOKEN, SOURCE, TREE)["outcome"], ui.PASS)
            for change in ({"case": "372"}, {"sourceCommit": "e" * 40}, {"declaredSourceTree": "f" * 40},
                           {"api": 37}, {"targetSdk": 36}, {"outcome": "PASS"}, {"outcome": "FAIL"}):
                with self.subTest(case=case, change=change), self.assertRaises(ValueError):
                    ui.validate_report(report(case, change), case, TOKEN, SOURCE, TREE)
        for change in ({"token": "d" * 32}, {"cleanupFailures": ["failed"]},
                       {"independentVisualAndMutationReview": "PASS"}):
            with self.assertRaises(ValueError):
                ui.validate_report(report(changes=change), "317", TOKEN, SOURCE, TREE)
        for change in ({"cleanup": []}, {"cleanup": [{"outcome": "FAIL"}]}, {"lifecycleViolation": True}):
            with self.assertRaises(ValueError):
                ui.validate_report(report("324", change), "324", TOKEN, SOURCE, TREE)

    def test_json_duplicate_cannot_override_fail(self):
        with self.assertRaises(ValueError):
            ui.decode_json(b'{"outcome":"FAIL","outcome":"HARNESS_PASS_PENDING_REVIEW"}')

    def test_only_flat_bounded_synthetic_evidence_files(self):
        raw = archive([("./", b"", tarfile.DIRTYPE), ("./result.json", report(), tarfile.REGTYPE),
                       ("./after.png", b"fixture, not an image", tarfile.REGTYPE)])
        self.assertEqual(set(ui.evidence_members(raw)), {"result.json", "after.png"})

    def test_traversal_symlink_duplicate_directory_or_missing_result_rejected(self):
        baseline = [("./result.json", report(), tarfile.REGTYPE)]
        for name, kind in (("../private", tarfile.REGTYPE), ("/private", tarfile.REGTYPE),
                           ("nested/private", tarfile.REGTYPE), ("private", tarfile.SYMTYPE),
                           ("private", tarfile.DIRTYPE), ("result.json", tarfile.REGTYPE)):
            with self.subTest(name=name, kind=kind), self.assertRaises(ValueError):
                ui.evidence_members(archive(baseline + [(name, b"fixture", kind)]))
        with self.assertRaises(ValueError):
            ui.evidence_members(archive([]))

    def test_archive_expansion_member_size_is_bounded_before_read(self):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode="w") as target:
            info = tarfile.TarInfo("huge.png")
            info.size = 16 * 1024 * 1024 + 1
            # Header-only malicious declaration, not a large allocation fixture.
            target.fileobj.write(info.tobuf())
        with self.assertRaises(ValueError):
            ui.evidence_members(out.getvalue())

    def test_modeled_credential_storage_stays_outside_flat_export(self):
        # Source-integration tripwire, not a Compose/device result: nested fixture
        # storage would always make the intentional flat-only tar admission fail.
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        source = (path / "CredentialUiInstrumentation.kt").read_text()
        self.assertIn('File(app.cacheDir.canonicalFile, "ui-324-fixture-$token")', source)
        self.assertNotIn('File(directory, "fixture")', source)
        self.assertIn("check(!it.exists() && it.mkdir() && it.canonicalFile == it)", source)

    def test_setup_failure_retains_observation_without_extending_deadlines(self):
        # Source integration guard only; the encrypted owned-guest image is not
        # available to this host fixture and must still be reviewed after ART.
        path = ui.ROOT / "samples/p2p-sample-android/src/androidTest/java/dev/p2pkit/sample/android/runtime"
        source = (path / "UiAcceptanceInstrumentation.kt").read_text()
        self.assertIn('stage = "setup-diagnostics-entry"', source)
        self.assertIn('await(5_000) { currentAppTree()?.text("Diagnostics") != null }', source)
        self.assertIn('withTimeout(25_000)', source)
        self.assertIn('val deadline = injection.end + 5_000_000_000L', source)
        self.assertIn('retainFailureObservation()', source)
        self.assertIn('newFile("failure-context.png")', source)
        self.assertIn('currentAppTree()?.let { write("failure-context-tree.json"', source)
        failure = source[source.index('private fun retainFailureObservation()'):source.index('private fun screenshot(')]
        for forbidden in ('performAction(', 'invalidate(', 'requestLayout(', 'startActivity(', 'sendStatus('):
            self.assertNotIn(forbidden, failure)

    def test_shared_manifest_consumer_does_not_change_default_runner(self):
        source = (ui.ROOT / "scripts/run-android-art-smoke.py").read_text()
        self.assertIn('INSTRUMENTATION = PACKAGE + ".runtime.LanPermissionRuntimeInstrumentation"', source)
        self.assertNotIn("372", ui.CASES)


if __name__ == "__main__":
    unittest.main()
