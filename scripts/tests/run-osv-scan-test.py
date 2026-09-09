#!/usr/bin/env python3
"""Controller/workflow regression controls; these do not execute an OSV scan."""

import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("osv_scan", ROOT / "scripts/run-osv-scan.py")
SCAN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCAN)
ARGUMENTS = "--config=./osv-scanner.toml\n--lockfile=gradle.lockfile:./buildscript-gradle.lockfile"
CLEAN_SARIF = json.dumps({"version": "2.1.0", "runs": [{
    "tool": {"driver": {"name": "osv-scanner"}}, "results": [],
}]}).encode()


class OsvScanTest(unittest.TestCase):
    def controlled_scan(self, root, returncode, payload):
        report_dir = root / "reports"
        outputs = root / "outputs"

        def original_scanner(command, *, stdout, stderr, check):
            self.assertEqual(command[:5], ["admitted-scanner", "scan", "source", "--all-vulns", "--format=sarif"])
            self.assertEqual(command[5], f"--output-file={report_dir / 'results.sarif'}")
            self.assertEqual(command[6:], ARGUMENTS.splitlines())
            self.assertEqual(stderr, subprocess.STDOUT)
            self.assertFalse(check)
            stdout.write(b"controlled original scanner log\n")
            if payload is not None:
                (report_dir / "results.sarif").write_bytes(payload)
            return subprocess.CompletedProcess(command, returncode)

        with mock.patch.object(SCAN.subprocess, "run", side_effect=original_scanner), \
                mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(outputs)}, clear=True), \
                io.TextIOWrapper(io.BytesIO()) as log, mock.patch.object(sys, "stdout", log), \
                mock.patch.object(sys, "stderr", io.StringIO()):
            result = SCAN.scan("admitted-scanner", report_dir, ARGUMENTS)
        return result, report_dir, outputs.read_text()

    def test_original_exit_cannot_be_replaced_by_a_successful_report(self):
        # Genuine clean/vulnerable evaluations may be uploaded; every operational
        # failure stays failing even when a structurally valid report exists.
        for code in (0, 1, 127, 128, 129, 130, -15):
            with self.subTest(scanner_exit=code), tempfile.TemporaryDirectory() as directory:
                result, reports, outputs = self.controlled_scan(Path(directory), code, CLEAN_SARIF)
                expected = code if code >= 0 else 128 - code
                self.assertEqual(result, expected)
                self.assertEqual((reports / "scanner-exit-code.txt").read_text(), f"{expected}\n")
                self.assertEqual("sarif_ready=true\n" in outputs, code in (0, 1))
                self.assertIn("controlled original scanner", (reports / "scanner.log").read_text())

    def test_missing_empty_or_malformed_report_cannot_pass(self):
        for payload in (None, b"", b"{", b"{}"):
            with self.subTest(payload=payload), tempfile.TemporaryDirectory() as directory:
                result, reports, outputs = self.controlled_scan(Path(directory), 0, payload)
                self.assertNotEqual(result, 0)
                self.assertEqual((reports / "scanner-exit-code.txt").read_text(), "0\n")
                self.assertNotIn("sarif_ready=true", outputs)

    def test_existing_report_is_not_reused(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(SCAN.subprocess, "run") as run:
            reports = Path(directory) / "reports"
            reports.mkdir()
            (reports / "results.sarif").write_bytes(CLEAN_SARIF)
            with self.assertRaises(FileExistsError):
                SCAN.scan("admitted-scanner", reports, ARGUMENTS)
            run.assert_not_called()
            self.assertEqual((reports / "results.sarif").read_bytes(), CLEAN_SARIF)

    def test_caller_cannot_override_strict_scanning(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(SCAN.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                SCAN.scan("admitted-scanner", Path(directory) / "reports", ARGUMENTS + "\n--allow-no-lockfiles")
            run.assert_not_called()

    def test_local_workflow_reference_is_same_revision_and_cannot_escape(self):
        text = (ROOT / "scripts/tests/release-workflow-test.sh").read_text()
        helper = re.search(r"(?m)^is_local_workflow_reference\(\) \{\n[\s\S]*?^\}\n", text)
        self.assertIsNotNone(helper)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            workflows = root / ".github/workflows"
            workflows.mkdir(parents=True)
            (workflows / "accepted.yml").write_text("on: workflow_call\n")
            (workflows / "untracked.yml").write_text("on: workflow_call\n")
            outside = Path(directory) / "outside.yml"
            outside.write_text("on: workflow_call\n")
            (workflows / "escaped.yml").symlink_to(outside)
            subprocess.run(["git", "init", "--quiet", str(root)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "add", ".github/workflows/accepted.yml",
                            ".github/workflows/escaped.yml"], check=True, capture_output=True)
            control = helper[0] + '''
root="$1"; shift
is_local_workflow_reference "$root" "$1"; shift
for reference in "$@"; do
    if is_local_workflow_reference "$root" "$reference"; then
        echo "Unsafe local workflow reference accepted: $reference" >&2
        exit 1
    fi
done
'''
            rejected = ["missing.yml", "untracked.yml", "escaped.yml", "../workflows/accepted.yml",
                        "/accepted.yml", "accepted.yml@main", "accepted.yml@" + "a" * 40]
            subprocess.run(["bash", "-euc", control, "pin-control", str(root),
                            "./.github/workflows/accepted.yml",
                            *("./.github/workflows/" + name for name in rejected),
                            "../.github/workflows/accepted.yml", "actions/checkout@main"],
                           check=True, capture_output=True)
            relocated = Path(directory) / "relocated-workflows"
            workflows.rename(relocated)
            workflows.symlink_to(relocated, target_is_directory=True)
            reject_parent_symlink = helper[0] + '\n! is_local_workflow_reference "$1" "$2"\n'
            subprocess.run(["bash", "-euc", reject_parent_symlink, "pin-control", str(root),
                            "./.github/workflows/accepted.yml"], check=True, capture_output=True)

    def test_workflow_preserves_the_blocking_scan_and_required_context(self):
        def workflow(name):
            raw = subprocess.check_output([
                "ruby", "-rjson", "-ryaml", "-e",
                "puts JSON.generate(YAML.safe_load(File.read(ARGV.fetch(0)), aliases: true))",
                str(ROOT / ".github/workflows" / name),
            ])
            return json.loads(raw)

        caller = workflow("osv-scanner.yml")
        leaf = workflow("osv-scanner-reusable.yml")
        self.assertEqual(set(caller["jobs"]), {"scan"})
        self.assertEqual(caller["jobs"]["scan"]["uses"], "./.github/workflows/osv-scanner-reusable.yml")
        self.assertEqual(set(leaf["jobs"]), {"osv-scan"})
        job = leaf["jobs"]["osv-scan"]
        self.assertNotIn("continue-on-error", caller["jobs"]["scan"])
        self.assertNotIn("continue-on-error", job)
        self.assertNotIn("if", job)
        steps = {step.get("id"): step for step in job["steps"]}
        scan = steps["scan"]
        self.assertNotIn("continue-on-error", scan)
        self.assertNotIn("if", scan)
        self.assertEqual(scan["env"]["OSV_SCAN_ARGS"], "${{ inputs.scan-args }}")
        self.assertEqual(scan["run"], 'export TMPDIR="$OSV_DIR/tmp" XDG_CACHE_HOME="$OSV_DIR/cache"\n'
                         'python3 scripts/run-osv-scan.py "$OSV_DIR/osv-scanner" "$OSV_DIR/reports"\n')
        uploads = [step for step in job["steps"] if step.get("uses", "").startswith("github/codeql-action/upload-sarif@")]
        self.assertEqual(len(uploads), 1)
        self.assertEqual(uploads[0]["if"], "${{ !cancelled() && steps.scan.outputs.sarif_ready == 'true' }}")
        self.assertNotIn("continue-on-error", uploads[0])
        self.assertTrue(any(step.get("run") == "scripts/tests/check-osv-lockfile-coverage.sh" for step in job["steps"]))


if __name__ == "__main__":
    unittest.main()
