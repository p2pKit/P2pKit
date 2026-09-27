#!/usr/bin/env python3
"""Offline controls for feature-only hosted generation; no Java/network/Gradle."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rpc_hosted", ROOT / "scripts/run-rpc-hosted-validation.py")
hosted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosted)


class HostedValidationTest(unittest.TestCase):
    def test_complete_writer_is_not_replaced_by_a_partial_graph(self):
        commands = hosted.generator_commands()
        self.assertEqual([row[0] for row in commands], ["apple-abi", "complete-lock-writer"])
        self.assertEqual(commands[1][1], ["resolveAndLockAll", "--write-locks",
                                        "--write-verification-metadata", "sha256"])
        self.assertIn("--no-configure-on-demand", hosted.FLAGS)
        self.assertIn("--rerun-tasks", hosted.FLAGS)
        self.assertEqual(hosted.FLAGS[hosted.FLAGS.index("--dependency-verification") + 1], "strict")
        self.assertNotIn("-x", hosted.FLAGS)
        self.assertTrue(all("publish" not in str(row).lower() for row in commands))

    def test_generated_allowlist_excludes_keys_source_and_binaries(self):
        for path in ("keys.json", "gradle.properties", "library/p2p-rpc/src/Test.kt",
                     "library/p2p-rpc/build/rpc.jar", "AGENTS.md", "CLAUDE.md", "RPC_MODULE_PLAN.md"):
            self.assertNotIn(path, hosted.GENERATED)
        self.assertIn("library/p2p-rpc/gradle.lockfile", hosted.GENERATED)
        self.assertIn("samples/p2p-sample-rpc/gradle.lockfile", hosted.GENERATED)
        self.assertEqual(len(hosted.LOCKS), 14)

    def test_no_offline_execution_can_be_mistaken_for_hosted_authorization(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(hosted.HostedValidationError, "authorized disposable"):
                hosted.paths()

    def test_unrelated_ref_is_rejected_before_any_build(self):
        with patch.object(hosted.platform, "system", return_value="Darwin"), patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_REF": "refs/heads/main",
        }):
            with self.assertRaisesRegex(hosted.HostedValidationError, "feature ref"):
                hosted.paths()

    def test_diagnostics_exclude_fixture_payloads_and_assertion_bodies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.log"
            path.write_text("e: file:///public/Example.kt:12:7 Unresolved reference 'example'.\n"
                            "> Task :p2p-rpc:compileKotlinIosArm64 FAILED\n"
                            "> Could not resolve org.example:public-library:1.0.\n"
                            "invitation=synthetic-private-value\n"
                            "Expected payload <synthetic-private-value>\n"
                            "> Could not resolve secret: synthetic-private-value\n"
                            "BUILD FAILED in 4s\n")
            output = hosted.safe_diagnostics(path)
            self.assertEqual(len(output), 4)
            self.assertNotIn("synthetic-private-value", "\n".join(output))

    def test_overlong_line_is_not_admitted_by_a_matching_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.log"
            path.write_text("x" * 8193 + "e: file:///public/Example.kt:12 synthetic-private-value\n"
                            "BUILD FAILED in 4s\n")
            self.assertEqual(hosted.safe_diagnostics(path), ["BUILD FAILED in 4s"])

    def test_test_report_redacts_output_messages_and_stacktraces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "library/example/build/test-results/iosTest/TEST-example.xml"
            path.parent.mkdir(parents=True)
            path.write_text('<testsuite tests="2" failures="1" errors="0" skipped="0">'
                            '<testcase classname="example.Test" name="failure">'
                            '<failure message="secret">private trace</failure>'
                            '<system-out>private payload</system-out></testcase>'
                            '<testcase name="pass"/><system-err>private stderr</system-err></testsuite>')
            result = hosted.test_summary(root)
            self.assertEqual(result[0]["tests"], 2)
            self.assertEqual(result[0]["failedCases"], [{"classname": "example.Test", "name": "failure"}])
            self.assertNotIn("private", json.dumps(result))
            self.assertNotIn("secret", json.dumps(result))

    def test_invalid_counts_and_xml_entities_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "samples/example/build/test-results/test/TEST-example.xml"
            path.parent.mkdir(parents=True)
            for xml in ('<testsuite tests="-1"/>', '<!DOCTYPE x><testsuite tests="1"/>'):
                path.write_text(xml)
                with self.assertRaises(hosted.HostedValidationError):
                    hosted.test_summary(root)

    def test_bounded_reader_rejects_oversized_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"12345")
            self.assertEqual(hosted.read_bounded(path, 5), b"12345")
            with self.assertRaises(hosted.HostedValidationError):
                hosted.read_bounded(path, 4)
            link = path.with_name("link")
            link.symlink_to(path)
            with self.assertRaises(hosted.HostedValidationError):
                hosted.read_bounded(link)

    def test_unexpected_source_changes_block_candidate_export(self):
        with patch.object(hosted, "git", return_value=b"library/p2p-rpc/src/Unexpected.kt\n"):
            with self.assertRaisesRegex(hosted.HostedValidationError, "Unexpected source"):
                hosted.collect_candidates(ROOT, False)

    def test_failed_writer_never_exports_acceptable_locks(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(hosted, "git", return_value=b""):
            root = Path(directory)
            for name in (*hosted.LOCKS, *(f"library/{n}/api/{n}.klib.api" for n in hosted.LIBRARIES)):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic fixture\n")
            self.assertEqual(hosted.collect_candidates(root, False)[0]["status"], "INCOMPLETE_DO_NOT_IMPORT")
            self.assertEqual(hosted.collect_candidates(root, True)[0]["status"], "REVIEW_REQUIRED")
            (root / "library/p2p-rpc/gradle.lockfile").unlink()
            self.assertEqual(hosted.collect_candidates(root, True)[0]["status"], "INCOMPLETE_DO_NOT_IMPORT")

    def test_python_fixture_exit_and_deadline_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            failed = hosted.execute(state, "failure", [sys.executable, "-c", "raise SystemExit(7)"], 5)
            self.assertEqual(failed["exitCode"], 7)
            self.assertTrue(failed["processGroupDrained"])
            timed = hosted.execute(state, "deadline", [sys.executable, "-c", "import time; time.sleep(10)"], 0.1)
            self.assertEqual(timed["exitCode"], 124)
            self.assertTrue(timed["processGroupDrained"])


if __name__ == "__main__":
    unittest.main()
