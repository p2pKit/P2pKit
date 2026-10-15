#!/usr/bin/env python3
"""Focused genuine subprocess/public-key evidence tests; no Gradle or service."""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import ci_evidence as E

PUBLIC_FINGERPRINT = "0A996D2BC19518FB50071A95D3FDADA57CFB7E1F"


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-evidence-test-")
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def command(self, program, **options):
        return E.run_command([sys.executable, "-I", "-B", "-c", program], cwd=self.root,
            environment=dict(os.environ), private=self.root / "command", timeout=options.pop("timeout", 5),
            **options)

    def test_real_success_captures_both_private_streams_and_known_close(self):
        public = io.StringIO()
        with contextlib.redirect_stdout(public), contextlib.redirect_stderr(public):
            result = self.command("import sys; print('PRIVATE_OUTPUT'); print('PRIVATE_ERROR',file=sys.stderr)")
        self.assertEqual(result["code"], "PASS")
        self.assertEqual(result["exitCode"], 0)
        self.assertTrue(result["cleanupKnown"])
        self.assertFalse(result["timedOut"])
        self.assertEqual(public.getvalue(), "")
        self.assertEqual((self.root / "command/stdout.log").read_bytes(), b"PRIVATE_OUTPUT\n")
        self.assertEqual((self.root / "command/stderr.log").read_bytes(), b"PRIVATE_ERROR\n")

    def test_real_nonzero_is_preserved_and_not_relabelled_pass(self):
        result = self.command("import sys; print('original failure',file=sys.stderr); sys.exit(7)")
        self.assertEqual((result["code"], result["exitCode"]), ("COMMAND_FAILED", 7))
        self.assertTrue(result["cleanupKnown"])

    def test_real_timeout_retires_original_child(self):
        result = self.command("import time; time.sleep(30)", timeout=0.3)
        self.assertEqual(result["code"], "TIMEOUT")
        self.assertTrue(result["timedOut"])
        self.assertTrue(result["cleanupKnown"])
        self.assertIsNotNone(result["exitCode"])
        self.assertLess(result["elapsedSeconds"], 10)

    def test_real_leader_exit_does_not_leave_child_writing(self):
        # Descendant inherits the actual supervisor marker/Job Object and pipes.
        result = self.command("import subprocess,sys; subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])")
        self.assertEqual(result["exitCode"], 0)
        self.assertTrue(result["cleanupKnown"])
        self.assertEqual(result["code"], "PASS")
        self.assertLess(result["elapsedSeconds"], 10)

    def test_real_output_limit_is_enforced_during_capture(self):
        result = self.command("import sys,time; sys.stdout.buffer.write(b'x'*200000); sys.stdout.flush(); time.sleep(30)",
                              log_limit=1024)
        self.assertEqual(result["code"], "OUTPUT_LIMIT")
        self.assertLessEqual((self.root / "command/stdout.log").stat().st_size, 1024)
        self.assertTrue(result["cleanupKnown"])

    def test_actual_scope_failed_postspawn_still_closes_original_pipes(self):
        real = E.audit_processes.make_scope
        retained = []
        def supplier(*args):
            scope = real(*args)
            original = scope.spawn
            def failed(*args, **kwargs):
                child = original(*args, **kwargs)
                retained.extend((child.stdout, child.stderr))
                raise RuntimeError("PRIVATE_EXCEPTION")
            scope.spawn = failed
            return scope
        with mock.patch.object(E.audit_processes, "make_scope", supplier):
            result = self.command("import time; time.sleep(30)")
        self.assertEqual(result["code"], "SPAWN")
        self.assertTrue(result["cleanupKnown"])
        self.assertTrue(all(pipe.closed for pipe in retained))

    def test_real_cancellation_is_not_pass(self):
        result = self.command("import time; time.sleep(30)", cancelled=lambda: True)
        self.assertEqual(result["code"], "CANCELLED")
        self.assertTrue(result["cleanupKnown"])

    def test_reports_archive_hashes_and_rejects_links(self):
        source = self.root / "repo"
        source.mkdir()
        (source / "result.xml").write_bytes(b"<testsuite tests='1'/>\n")
        bundle = self.root / "bundle"
        bundle.mkdir()
        E.collect_reports(source, ["*.xml"], bundle / "reports")
        destination = self.root / "bundle.tar.gz"
        rows = E.archive_private(bundle, destination)
        self.assertEqual(rows, [{"path": "reports/result.xml", **E.digest_file(source / "result.xml")}])
        with tarfile.open(destination) as archive:
            self.assertEqual(archive.extractfile("reports/result.xml").read(), (source / "result.xml").read_bytes())
        # A real hard link is portable and must not silently include aliased data.
        os.link(source / "result.xml", source / "alias.xml")
        with self.assertRaises(E.EvidenceError):
            E.collect_reports(source, ["*.xml"], self.root / "rejected")

    def test_recipient_trusted_pin_checked_before_any_command(self):
        with mock.patch.object(E, "run_command", side_effect=AssertionError("must not launch")):
            with self.assertRaises(E.EvidenceError):
                E.encrypt_archive(self.root / "none", self.root / "cipher", b"NOT A KEY", "0" * 64,
                                  "1" * 40, self.root, dict(os.environ))

    def test_actual_public_key_encrypts_without_private_key_or_agent(self):
        key = (SCRIPTS.parent / ".github/ci-evidence-recipient.asc").read_bytes()
        source = self.root / "evidence.tar.gz"
        source.write_bytes(b"PUBLIC_SYNTHETIC_TEST_ONLY" * 100)
        result = E.encrypt_archive(source, self.root / "evidence.tar.gz.gpg", key,
            hashlib.sha256(key).hexdigest(), PUBLIC_FINGERPRINT, self.root, dict(os.environ))
        self.assertEqual(result["recipientFingerprint"], PUBLIC_FINGERPRINT)
        self.assertEqual(result["sha256"], E.digest_file(self.root / "evidence.tar.gz.gpg")["sha256"])
        self.assertGreater(result["bytes"], 32)
        secret_dir = self.root / "gnupg/private-keys-v1.d"
        self.assertFalse(list(secret_dir.iterdir()) if secret_dir.exists() else [])

    def test_actual_git_identity_detects_tracked_mutation(self):
        # Tiny synthetic repository, no project build/source mutation.
        subprocess.run(["git", "init", "-q", str(self.root / "repo")], check=True)
        repo = self.root / "repo"
        (repo / "gradle.properties").write_text("VERSION_NAME=0.8.0-rc1\n")
        subprocess.run(["git", "-C", str(repo), "add", "gradle.properties"], check=True)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Synthetic", "-c", "user.email=synthetic@example.invalid",
                        "commit", "-qm", "synthetic"], check=True)
        self.assertEqual(E.source_identity(repo)["version"], "0.8.0-rc1")
        (repo / "gradle.properties").write_text("VERSION_NAME=changed\n")
        with self.assertRaises(E.EvidenceError):
            E.source_identity(repo)

    def test_real_complete_runner_binds_source_and_encrypts_private_failure(self):
        repo = self.root / "repo"
        repo.mkdir()
        (repo / ".github").mkdir()
        (repo / "gradle.properties").write_text("VERSION_NAME=0.8.0-rc1\n")
        key_raw = (SCRIPTS.parent / ".github/ci-evidence-recipient.asc").read_bytes()
        (repo / ".github/ci-evidence-recipient.asc").write_bytes(key_raw)
        for args in (["init", "-q"], ["add", "."], ["-c", "user.name=Synthetic", "-c",
                     "user.email=synthetic@example.invalid", "commit", "-qm", "synthetic"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True)
        identity = E.source_identity(repo)
        environment = {"GITHUB_REPOSITORY": "example/project", "GITHUB_SHA": identity["commit"],
            "GITHUB_WORKFLOW_REF": "example/project/.github/workflows/ci.yml@refs/heads/main",
            "GITHUB_WORKFLOW_SHA": identity["commit"], "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_JOB": "test", "RUNNER_ENVIRONMENT": "github-hosted",
            "CI_EVIDENCE_RECIPIENT_SHA256": hashlib.sha256(key_raw).hexdigest(),
            "CI_EVIDENCE_RECIPIENT_FINGERPRINT": PUBLIC_FINGERPRINT}
        for exit_code in (0, 9):
            with self.subTest(exit_code=exit_code), mock.patch.dict(os.environ, environment):
                output = self.root / ("public-" + str(exit_code))
                public = io.StringIO()
                with contextlib.redirect_stdout(public), contextlib.redirect_stderr(public):
                    result = E.main(["--component", "source", "--timeout-seconds", "5", "--output-dir", str(output),
                        "--source-root", str(repo), "--", sys.executable, "-c",
                        "import sys; print('PRIVATE_FULL_COMPOSITION'); sys.exit(" + str(exit_code) + ")"])
                self.assertEqual(result, 0 if exit_code == 0 else 1)
                self.assertNotIn("PRIVATE_FULL_COMPOSITION", public.getvalue())
                self.assertEqual({p.name for p in output.iterdir()}, {"manifest.json", "evidence.tar.gz.gpg"})
                manifest = json.loads((output / "manifest.json").read_bytes())
                self.assertEqual(manifest["source"], identity)
                self.assertEqual(manifest["outcome"]["exitCode"], exit_code)
                self.assertTrue(manifest["outcome"]["cleanupKnown"])
                self.assertEqual(manifest["github"]["runAttempt"], "1")
                self.assertEqual(manifest["ciphertext"]["sha256"], E.digest_file(output / "evidence.tar.gz.gpg")["sha256"])
                self.assertNotIn(b"PRIVATE_FULL_COMPOSITION", (output / "manifest.json").read_bytes())

    def test_main_failure_never_echoes_exception_or_partial_artifact(self):
        with mock.patch.object(E, "source_identity", side_effect=RuntimeError("PRIVATE_FAILURE_DATA")):
            output = self.root / "public"
            diagnostic = io.StringIO()
            with contextlib.redirect_stderr(diagnostic):
                result = E.main(["--component", "source", "--timeout-seconds", "5", "--output-dir", str(output),
                                 "--source-root", str(self.root / "not-output"), "--", sys.executable, "-c", "pass"])
        self.assertEqual(result, 1)
        self.assertEqual(diagnostic.getvalue(), "CI_EVIDENCE FAIL SOURCE INPUT\n")
        self.assertEqual(list(output.iterdir()), [])

    def test_cleanup_exception_cannot_escape_finite_failure_diagnostic(self):
        diagnostic = io.StringIO()
        output = self.root / "public"
        with mock.patch.object(E, "source_identity", side_effect=RuntimeError("PRIVATE_SOURCE")), \
                mock.patch.object(Path, "unlink", side_effect=OSError("PRIVATE_CLEANUP_PATH")), \
                contextlib.redirect_stderr(diagnostic):
            result = E.main(["--component", "source", "--timeout-seconds", "5", "--output-dir", str(output),
                             "--source-root", str(self.root / "not-output"), "--", sys.executable, "-c", "pass"])
        self.assertEqual(result, 1)
        self.assertEqual(diagnostic.getvalue(), "CI_EVIDENCE FAIL SOURCE INPUT\nCI_EVIDENCE CLEANUP UNKNOWN\n")

    def test_task_diagnostic_admits_only_fixed_names_and_integral_exit_codes(self):
        directory = self.root / "build/reports/ci-component"
        directory.mkdir(parents=True)
        target = directory / "source.json"
        self.assertIsNone(E.component_tasks(self.root, "source"))
        record = {"component": "source", "tasks": [{"task": "wrapper", "exitCode": 7}], "exitCode": 7}
        target.write_text(json.dumps(record))
        self.assertEqual(E.component_tasks(self.root, "source"), [{"task": "wrapper", "exitCode": 7}])
        for row in ({"task": "PRIVATE_TEXT", "exitCode": 7}, {"task": "wrapper", "exitCode": True},
                    {"task": "wrapper", "exitCode": "PRIVATE_TEXT"}, {"task": "wrapper", "exitCode": 2**40},
                    {"task": "wrapper", "exitCode": 7, "private": "NEVER_PUBLIC"}):
            with self.subTest(row=row):
                target.write_text(json.dumps({**record, "tasks": [row]}))
                self.assertIsNone(E.component_tasks(self.root, "source"))
        target.write_text("PRIVATE_NOT_JSON")
        self.assertIsNone(E.component_tasks(self.root, "source"))

    def test_task_diagnostic_names_cover_every_actual_component_route(self):
        import ci_component
        observed = {name for component in ci_component.COMPONENTS
                    for name, _argv in ci_component.commands(component)}
        self.assertEqual(set(), observed - E.TASK_NAMES)
        self.assertTrue({"prepare-android", "prepare-desktop", "inspect-android", "inspect-desktop",
                         "component-setup", "gradle-stop"} <= E.TASK_NAMES)


if __name__ == "__main__":
    unittest.main(failfast=True)
