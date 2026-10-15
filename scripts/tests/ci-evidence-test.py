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

    def test_public_failure_diagnostics_keep_identifiers_not_private_messages(self):
        command = self.root / "command"
        command.mkdir()
        (command / "stdout.log").write_text(
            "> Task :p2p-core:jvmTest FAILED\n"
            "> Task :p2p-private:secret FAILED\n"
            "> Task :p2p-core:secret FAILED\n"
            "host_not_announced private-payload-123\n"
            "PUBLICATION_EMBEDDED_CHECK_LINES 321,99,15\n"
            "PUBLICATION_EMBEDDED_CHECK_LINES private-secret\n"
            "Dependency verification failed credential-never-public\n" +
            "a" * 5000 + "private-long-line\n")
        (command / "stderr.log").write_text("private URL or environment must not appear\n")
        phase = self.root / "build/reports/platform-tests/token/intel-simulator/simulator-first-launch"
        phase.mkdir(parents=True)
        (phase / "result.json").write_text(json.dumps({"label": "simulator-first-launch", "exitCode": 1,
            "timedOut": False, "outputLimitExceeded": False, "ownedGroupDrained": True,
            "argv": ["private-path"], "cwd": "private-directory"}))
        result = E.failure_diagnostics(self.root, command)
        self.assertEqual(result["categories"], ["DEPENDENCY_INTEGRITY", "LAN_HOST_NOT_ANNOUNCED"])
        self.assertEqual(result["failedGradleTasks"], [":p2p-core:jvmTest"])
        self.assertEqual(result["embeddedPublicationCheckLines"], [321,99,15])
        self.assertEqual(result["simulatorPhases"], [{"label": "simulator-first-launch", "exitCode": 1,
            "timedOut": False, "outputLimitExceeded": False, "ownedGroupDrained": True}])
        self.assertNotIn("private", json.dumps(result))
        self.assertNotIn("credential", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))
        row = json.loads((phase / "result.json").read_text())
        row["label"] = "simulator-private-secret"
        (phase / "result.json").write_text(json.dumps(row))
        self.assertEqual(E.failure_diagnostics(self.root, command)["simulatorPhases"], [])
        row["label"] = "simulator-first-launch"
        row.pop("exitCode")
        (phase / "result.json").write_text(json.dumps(row))
        self.assertEqual(E.failure_diagnostics(self.root, command)["simulatorPhases"], [])
        row["exitCode"] = True
        (phase / "result.json").write_text(json.dumps(row))
        self.assertEqual(E.failure_diagnostics(self.root, command)["simulatorPhases"], [])

    def test_embedded_publication_emits_source_lines_without_changing_failure(self):
        import ast
        import struct
        import xml.etree.ElementTree as ET
        import zipfile
        shell = (SCRIPTS / "check-publish-artifacts.sh").read_text()
        script = shell.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
        tree = ast.parse(script)
        helper = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "require")
        guard = next(node for node in tree.body if isinstance(node, ast.Try))
        namespace = {"sys": sys, "ET": ET, "zipfile": zipfile, "struct": struct}
        exec(compile(ast.Module(body=[helper], type_ignores=[]), "<stdin>", "exec"), namespace)
        namespace["inspect"] = lambda: namespace["require"](False, "PRIVATE_TEST_INPUT")
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured), self.assertRaises(SystemExit) as caught:
            exec(compile(ast.Module(body=[guard], type_ignores=[]), "<stdin>", "exec"), namespace)
        self.assertEqual(caught.exception.code, 1)
        self.assertRegex(captured.getvalue(), r"PUBLICATION_EMBEDDED_CHECK_LINES [0-9]+,[0-9]+\n")
        public_line = captured.getvalue().splitlines()[0]
        self.assertNotIn("PRIVATE", public_line)

    def test_platform_failure_diagnostics_project_only_known_tasks_and_counts(self):
        command = self.root / "command"
        command.mkdir()
        (command / "stdout.log").write_text("> Task :p2p-transport-lan:allTests FAILED\nPLATFORM_CHECK_LINES 831,134,58\n"
                                           "PLATFORM_CHECK_LINES private-secret\n")
        directory = self.root / "build/reports/platform-tests/current"
        directory.mkdir(parents=True)
        valid = {"outcome": "FAILED", "passed": 3, "failed": 1, "skipped": 0, "failure": "private-secret"}
        report = {"buildFailed": True, "private": "private-secret", "tests": {
            ":p2p-transport-lan:iosSimulatorArm64Test": valid,
            ":private:secret": valid,
            ":p2p-core:jvmTest": {**valid, "failed": True},
            ":p2p-core:iosX64Test": {**valid, "outcome": "private-secret"}}}
        (directory / "execution.json").write_text(json.dumps(report))
        result = E.failure_diagnostics(self.root, command)
        self.assertEqual(result["platformTests"], [{"buildFailed": True, "tests": [{
            "task": ":p2p-transport-lan:iosSimulatorArm64Test", "outcome": "FAILED", "passed": 3, "failed": 1, "skipped": 0}]}])
        self.assertEqual(result["failedGradleTasks"], [":p2p-transport-lan:allTests"])
        self.assertEqual(result["platformCheckLines"], [831,134,58])
        self.assertNotIn("private", json.dumps(result))
        (directory / "execution.json").write_text('{"tests":[]}')
        self.assertEqual(E.failure_diagnostics(self.root, command)["platformTests"], [])

    def test_platform_actual_failure_locator_preserves_private_exception(self):
        spec = importlib.util.spec_from_file_location("platform_locator_test", SCRIPTS / "run-platform-tests.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()
        try:
            module.require(False, "PRIVATE_FAILURE")
        except ValueError as error:
            with contextlib.redirect_stderr(output):
                module.report_failure_location(error)
            self.assertEqual(str(error), "PRIVATE_FAILURE")
        else:
            self.fail("Original failure was not preserved")
        self.assertRegex(output.getvalue(), r"^PLATFORM_CHECK_LINES [0-9]+\n$")
        self.assertNotIn("PRIVATE", output.getvalue())

    def test_windows_autocrlf_checkout_preserves_exact_public_recipient_blob(self):
        # Actual Git checkout conversion, not a mocked newline transform. The
        # original public blob is unchanged; no private key or GPG invocation.
        original = subprocess.check_output([
            "git", "-C", str(SCRIPTS.parent), "show", "HEAD:.github/ci-evidence-recipient.asc"])
        attributes = (SCRIPTS.parent / ".gitattributes").read_bytes()
        rule = b".github/ci-evidence-recipient.asc text eol=lf\n"
        self.assertEqual(attributes.count(rule), 1)
        self.assertNotIn(b"\r", original)
        for protected in (False, True):
            with self.subTest(protected=protected):
                repo = self.root / ("protected" if protected else "old-autocrlf")
                repo.mkdir()
                def git(*args, raw=None):
                    return subprocess.check_output(["git", "-C", str(repo), *args],
                                                   input=raw, stderr=subprocess.PIPE)
                git("init", "--quiet")
                git("config", "core.autocrlf", "true")
                for name, raw in ((".gitattributes", attributes if protected else attributes.replace(rule, b"")),
                                  (".github/ci-evidence-recipient.asc", original)):
                    blob = git("hash-object", "-w", "--stdin", raw=raw).decode().strip()
                    git("update-index", "--add", "--cacheinfo", "100644", blob, name)
                git("checkout-index", "--all", "--force")
                actual = (repo / ".github/ci-evidence-recipient.asc").read_bytes()
                if protected:
                    self.assertEqual(actual, original)
                    self.assertEqual(hashlib.sha256(actual).digest(), hashlib.sha256(original).digest())
                else:
                    self.assertIn(b"\r\n", actual)
                    self.assertNotEqual(hashlib.sha256(actual).digest(), hashlib.sha256(original).digest())

    def test_gpg_uses_cwd_relative_paths_for_native_and_msys_interoperation(self):
        work = self.root / 'private work'; work.mkdir()
        source = self.root / 'input archive.tar.gz'; source.write_bytes(b'public fixture')
        output = self.root / 'public output' / 'evidence.tar.gz.gpg'; output.parent.mkdir()
        key = (SCRIPTS.parent / '.github/ci-evidence-recipient.asc').read_bytes()
        calls = []
        def invoke(argv, **kwargs):
            calls.append(argv)
            self.assertEqual(kwargs['cwd'], work)
            self.assertEqual(argv[argv.index('--homedir') + 1], 'gnupg')
            self.assertIn('--no-autostart', argv)
            self.assertIn('--no-auto-key-retrieve', argv)
            expected = {'--import': work / 'recipient.asc', '--output': output, '--encrypt': source}
            for flag, path in expected.items():
                if flag in argv:
                    argument = argv[argv.index(flag) + 1]
                    self.assertFalse(os.path.isabs(argument))
                    self.assertNotIn('\\', argument)
                    self.assertEqual((work / argument).resolve(), path.resolve())
            directory = kwargs['private']; directory.mkdir()
            (directory / 'stdout.log').write_bytes(b'public-key-listing-model')
            (directory / 'stderr.log').write_bytes(b'')
            if '--encrypt' in argv:
                output.write_bytes(b'public-ciphertext-model' * 4)
            return {'code': 'PASS', 'exitCode': 0, 'timedOut': False, 'cleanupKnown': True}
        with mock.patch.object(E, 'run_command', side_effect=invoke), \
                mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                mock.patch.object(E, '_key_identity', return_value=(PUBLIC_FINGERPRINT, 0)):
            E.encrypt_archive(source, output, key, hashlib.sha256(key).hexdigest(),
                              PUBLIC_FINGERPRINT, work, dict(os.environ))
        self.assertEqual(len(calls), 4)
        other = self.root / 'different-drive-model'; other.mkdir()
        with mock.patch.object(E.os.path, 'relpath', side_effect=ValueError('PRIVATE_DRIVE')), \
                mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                mock.patch.object(E, 'run_command') as unused:
            with self.assertRaises(E.EvidenceError) as caught:
                E.encrypt_archive(source, output, key, hashlib.sha256(key).hexdigest(),
                                  PUBLIC_FINGERPRINT, other, dict(os.environ))
        self.assertEqual(caught.exception.code, 'ENCRYPTION')
        unused.assert_not_called()

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
        self.assertEqual([path.name for path in output.iterdir()], ["failure.json"])
        failure = json.loads((output / "failure.json").read_text())
        self.assertEqual(failure["kind"], "CI_EVIDENCE_FAILURE")
        self.assertIsNone(failure["source"])
        self.assertNotIn("PRIVATE", json.dumps(failure))

    def test_gpg_failure_keeps_only_fixed_phase_outcome_and_closed_error_categories(self):
        key = (SCRIPTS.parent / '.github/ci-evidence-recipient.asc').read_bytes()
        for failed_phase in ('key-show', 'key-import', 'key-list', 'encrypt'):
            for cleanup in (True, False):
                with self.subTest(phase=failed_phase, cleanup=cleanup):
                    work = self.root / (failed_phase + str(cleanup)); work.mkdir()
                    calls = []
                    def invoke(argv, **kwargs):
                        directory = kwargs['private']; directory.mkdir()
                        calls.append(directory.name)
                        (directory / 'stdout.log').write_bytes(b'PRIVATE_LISTING')
                        (directory / 'stderr.log').write_bytes(b'gpg: Permission denied PRIVATE_PATH\n')
                        failed = directory.name == failed_phase
                        return {'code': 'COMMAND_FAILED' if failed else 'PASS', 'exitCode': 2 if failed else 0,
                                'cleanupKnown': cleanup if failed else True, 'timedOut': False}
                    with mock.patch.object(E, 'run_command', side_effect=invoke), \
                            mock.patch.object(E.shutil, 'which', return_value='/public/gpg'), \
                            mock.patch.object(E, '_key_identity', return_value=(PUBLIC_FINGERPRINT, 0)):
                        with self.assertRaises(E.EvidenceError) as caught:
                            E.encrypt_archive(work / 'archive', work / 'output', key,
                                hashlib.sha256(key).hexdigest(), PUBLIC_FINGERPRINT, work, dict(os.environ))
                    diagnostic = caught.exception.encryption_diagnostic
                    self.assertEqual(diagnostic['phase'], failed_phase)
                    self.assertEqual(calls[-1], failed_phase)
                    self.assertEqual(diagnostic['outcome'], {'code': 'COMMAND_FAILED', 'exitCode': 2,
                                                            'cleanupKnown': cleanup, 'timedOut': False})
                    self.assertEqual(diagnostic['categories'], ['ACCESS_DENIED'] if cleanup else [])
                    self.assertNotIn('PRIVATE', json.dumps(diagnostic))

    def test_native_spawn_error_diagnostic_exposes_only_fixed_operation_and_numbers(self):
        os_error = OSError(13, 'PRIVATE_OS_MESSAGE', 'PRIVATE_PATH')
        os_error.winerror = 5
        cases = [(os_error, 'OS', None, 13, 5),
            (E.audit_processes.OwnershipError('Windows CreateProcessW (atomic job assignment) failed: error 87'),
             'WIN32', 'CreateProcessW (atomic job assignment)', None, 87),
            (E.audit_processes.OwnershipError('Unsupported Windows Job Object ABI layout'),
             'OWNERSHIP', 'WINDOWS_ABI', None, None),
            (E.audit_processes.OwnershipError('Windows PRIVATE_OPERATION failed: error 87'),
             'UNKNOWN', None, None, None),
            (RuntimeError('PRIVATE_UNKNOWN_ERROR'), 'UNKNOWN', None, None, None)]
        for index, (error, kind, operation, errno, winerror) in enumerate(cases):
            with self.subTest(index=index), mock.patch.object(E.audit_processes, 'make_scope', side_effect=error):
                result = E.run_command(['no-command-executed'], cwd=self.root, environment=dict(os.environ),
                    private=self.root / ('spawn-' + str(index)), timeout=1)
            self.assertEqual(result['code'], 'SPAWN')
            self.assertEqual(result['nativeError'], {'kind': kind, 'operation': operation,
                                                   'errno': errno, 'winerror': winerror})
            self.assertEqual(E.public_outcome(result)['nativeError'], result['nativeError'])
            self.assertNotIn('PRIVATE', json.dumps(E.public_outcome(result)))

    def test_encryption_failure_public_record_is_not_qualification_and_keeps_unknown_writers(self):
        source = {'commit': 'a' * 40, 'tree': 'b' * 40, 'version': '0.7.0-SNAPSHOT'}
        for cleanup in (True, False):
            with self.subTest(cleanup=cleanup):
                root = self.root / ('repo-' + str(cleanup)); root.mkdir()
                (root / '.github').mkdir()
                (root / '.github/ci-evidence-recipient.asc').write_bytes(b'public-key-model')
                output = self.root / ('output-' + str(cleanup))
                private = self.root / ('private-' + str(cleanup)); private.mkdir()
                report = root / 'build/reports/ci-component'; report.mkdir(parents=True)
                (report / 'jvm-windows.json').write_text(json.dumps({'component': 'jvm-windows',
                    'tasks': [{'task': 'component-setup', 'exitCode': 125}], 'exitCode': 125}))
                def command(argv, **kwargs):
                    directory = kwargs['private']; directory.mkdir()
                    (directory / 'stdout.log').write_bytes(b'PRIVATE_BODY\n')
                    (directory / 'stderr.log').write_bytes(b'PRIVATE_ERROR\n')
                    return {'code': 'COMMAND_FAILED', 'exitCode': 125, 'timedOut': False, 'cleanupKnown': True}
                error = E.EvidenceError('ENCRYPTION')
                error.encryption_diagnostic = {'phase': 'key-show', 'categories': [], 'outcome':
                    {'code': 'SPAWN', 'exitCode': None, 'timedOut': False, 'cleanupKnown': cleanup}}
                captured = io.StringIO()
                with mock.patch.object(E, 'source_identity', return_value=source), \
                        mock.patch.object(E, 'github_identity', return_value={'runId': '123', 'runAttempt': '1'}), \
                        mock.patch.object(E, 'run_command', side_effect=command), \
                        mock.patch.object(E.tempfile, 'mkdtemp', return_value=str(private)), \
                        mock.patch.object(E, 'encrypt_archive', side_effect=error), contextlib.redirect_stderr(captured):
                    result = E.main(['--component', 'jvm-windows', '--timeout-seconds', '5',
                        '--output-dir', str(output), '--source-root', str(root), '--', 'model-command'])
                self.assertEqual(result, 1)
                self.assertEqual([p.name for p in output.iterdir()], ['failure.json'])
                failure = json.loads((output / 'failure.json').read_text())
                self.assertEqual(failure['kind'], 'CI_EVIDENCE_FAILURE')
                self.assertEqual(failure['source'], source)
                self.assertEqual(failure['taskResults'], [{'task': 'component-setup', 'exitCode': 125}])
                self.assertEqual(failure['encryptionDiagnostic'], error.encryption_diagnostic)
                self.assertNotIn('PRIVATE', json.dumps(failure))
                self.assertNotIn('PRIVATE', captured.getvalue())
                self.assertEqual(private.exists(), not cleanup)
                # Exercise the actual existing consumer: even a correctly hashed
                # immutable archive of this diagnostic cannot qualify a component.
                import ci_qualification as Q
                import zipfile
                archive = self.root / ('failure-' + str(cleanup) + '.zip')
                with zipfile.ZipFile(archive, 'x') as zipped:
                    zipped.write(output / 'failure.json', 'failure.json')
                artifact = {'size_in_bytes': archive.stat().st_size,
                            'digest': 'sha256:' + hashlib.sha256(archive.read_bytes()).hexdigest()}
                api = mock.Mock()
                api.download.side_effect = lambda _artifact, destination: destination.write_bytes(archive.read_bytes())
                with self.assertRaisesRegex(Q.AdmissionError, '^Unexpected record ZIP members$'):
                    Q.read_archive(api, artifact, evidence=True)

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
