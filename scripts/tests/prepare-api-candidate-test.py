#!/usr/bin/env python3
"""Real tiny Git worktrees and modeled generation; no Gradle, network or credentials."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("api_candidate", ROOT / "scripts/prepare-api-candidate.py")
A = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(A)


def api(native=False, changed=False):
    if native:
        return ("// Klib ABI Dump\n// Targets: [iosArm64, iosSimulatorArm64, iosX64]\n"
                "final class dev.p2pkit.core/Fixture { // dev.p2pkit.core/Fixture|null[0]\n"
                "    constructor <init>() // <init>(){}[0]\n" +
                ("    final fun addition(): kotlin/Unit // addition(){}[0]\n" if changed else "") + "}\n").encode()
    return ("public final class dev/p2pkit/core/Fixture {\n\tpublic fun <init> ()V\n" +
            ("\tpublic fun addition ()V\n" if changed else "") + "}\n").encode()


def request_environment(sha):
    return {"GITHUB_SHA": sha, "GITHUB_WORKFLOW_SHA": sha, "GITHUB_REPOSITORY": "p2pKit/P2pKit",
            "GITHUB_ACTIONS": "true", "GITHUB_JOB": "generate",
            "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/" + A.WORKFLOW + "@refs/heads/reviewed-api",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "RUNNER_ENVIRONMENT": "github-hosted",
            "RUNNER_OS": "macOS", "RUNNER_ARCH": "X64"}


class CandidateTests(unittest.TestCase):
    def setUp(self):
        owned = tempfile.TemporaryDirectory(prefix="api-candidate-test-")
        self.addCleanup(owned.cleanup)
        parent = Path(owned.name).resolve()
        self.controller, self.temporary = parent / "controller", parent / "runner-temp"
        self.controller.mkdir()
        self.temporary.mkdir()
        self.output = self.temporary / "review"
        self.command(self.controller, "-c", "init.defaultBranch=main", "init", "--quiet", "--template=")
        self.command(self.controller, "config", "core.autocrlf", "false")
        self.command(self.controller, "config", "core.filemode", "true")
        self.command(self.controller, "config", "user.name", "Synthetic fixture")
        self.command(self.controller, "config", "user.email", "fixture@example.invalid")
        self.original_api = {name: api(name.endswith(".klib.api")) for name in A.API_FILES}
        self.generated_api = {name: api(name.endswith(".klib.api"), True) for name in A.API_FILES}
        files = {**self.original_api, ".gitignore": b"build/\n.gradle/\nlocal.properties\n",
                 "product.txt": b"unchanged product\n", "gradle.lockfile": b"existing lock\n",
                 "gradle/verification-metadata.xml": b"existing reviewed checksums\n",
                 "library/p2p-core/gradle.lockfile": b"existing core lock\n",
                 "library/other/api/other.api": b"other module API\n",
                 A.WORKFLOW: b"synthetic reviewed workflow\n",
                 "scripts/prepare-api-candidate.py": b"synthetic reviewed helper\n",
                 # These fail loudly if a test accidentally stops modeling execution.
                 "gradlew": b"#!/bin/sh\nexit 97\n",
                 "scripts/check-gradle-wrapper.sh": b"#!/bin/sh\nexit 98\n",
                 "scripts/check-dependency-verification.sh": b"#!/bin/sh\nexit 98\n"}
        for name, raw in files.items():
            path = self.controller / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        (self.controller / "gradlew").chmod(0o755)
        self.command(self.controller, "add", ".")
        self.command(self.controller, "commit", "--quiet", "-m", "Synthetic reviewed source")
        self.command(self.controller, "tag", "historical-fixture")
        self.sha = A.git(self.controller, "rev-parse", "HEAD").decode().strip()
        self.tree = A.git(self.controller, "rev-parse", "HEAD^{tree}").decode().strip()
        self.original_snapshot = A.snapshot(self.controller)
        self.original_refs = A.git(self.controller, "show-ref")
        self.original_worktrees = A.git(self.controller, "worktree", "list", "--porcelain")
        self.calls = []
        self.log = io.StringIO()

    @staticmethod
    def command(root, *arguments, **options):
        return subprocess.run(["git", "-C", str(root), *arguments], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)

    def model(self, *, mutate=None, generation=0, stop=0, prerequisite=0, unchanged=False):
        def invoke(argv, **options):
            self.calls.append((argv, options))
            candidate = Path(options["cwd"])
            self.assertNotEqual(self.controller, candidate)
            self.assertEqual(self.temporary, candidate.parent.parent)
            self.assertEqual("source", candidate.name)
            self.assertEqual(subprocess.DEVNULL, options["stdin"])
            self.assertFalse(options["check"])
            if argv[0] == "bash":
                return subprocess.CompletedProcess(argv, prerequisite)
            if argv[-1] == "--stop":
                return subprocess.CompletedProcess(argv, stop)
            self.assertEqual(self.sha, A.git(candidate, "rev-parse", "HEAD").decode().strip())
            detached = subprocess.run(["git", "-C", str(candidate), "symbolic-ref", "-q", "HEAD"],
                                      capture_output=True, check=False)
            self.assertEqual(1, detached.returncode)
            actual = A.snapshot(candidate)
            self.assertEqual(self.original_snapshot.keys(), actual.keys())
            for name, original in self.original_snapshot.items():
                self.assertEqual(original[:2], actual[name][:2])
                self.assertEqual(original[3], actual[name][3])
            if not unchanged:
                for name, raw in self.generated_api.items():
                    (candidate / name).write_bytes(raw)
            ignored = candidate / "library/p2p-core/build/ignored.txt"
            ignored.parent.mkdir(parents=True)
            ignored.write_text("synthetic ignored build output\n")
            if mutate:
                mutate(candidate)
            return subprocess.CompletedProcess(argv, generation)
        return invoke

    def execute(self, **options):
        with contextlib.redirect_stdout(self.log):
            return A.execute(self.controller, self.sha, self.output, self.temporary, run=self.model(**options))

    def assert_retired(self, *, controller_unchanged=True):
        self.assertFalse(list(self.temporary.glob("core-api-worktree-*")))
        self.assertEqual(self.original_worktrees, A.git(self.controller, "worktree", "list", "--porcelain"))
        self.assertEqual(self.original_refs, A.git(self.controller, "show-ref"))
        if controller_unchanged:
            self.assertEqual(b"", A.git(self.controller, "status", "--porcelain=v1"))
            self.assertEqual(self.original_snapshot, A.snapshot(self.controller))

    def test_exact_detached_generation_emits_only_applicable_review_patch_and_bound_manifest(self):
        previous_umask = os.umask(0o077)
        try:
            result = self.execute()
        finally:
            os.umask(previous_umask)
        candidate = Path(self.calls[0][1]["cwd"])
        self.assertEqual([
            ["bash", str(candidate / "scripts/check-gradle-wrapper.sh")],
            ["bash", str(candidate / "scripts/check-dependency-verification.sh")],
            [str(candidate / "gradlew"), "--no-daemon", "--console=plain", "--no-build-cache",
             "--no-configuration-cache", "--dependency-verification", "strict", "--max-workers=2", "--no-parallel",
             ":p2p-core:updateKotlinAbi", ":p2p-core:updateAndroidAbi"],
            [str(candidate / "gradlew"), "--stop"],
        ], [argv for argv, _ in self.calls])
        self.assertEqual(90, self.calls[-1][1]["timeout"])
        self.assertTrue(all("shell" not in options and "env" not in options for _, options in self.calls))
        self.assertEqual({"core-api-candidate.patch", "core-api-candidate.json"},
                         {path.name for path in self.output.iterdir()})
        patch_bytes = (self.output / "core-api-candidate.patch").read_bytes()
        raw_manifest = (self.output / "core-api-candidate.json").read_bytes()
        self.assertEqual(result, json.loads(raw_manifest))
        self.assertEqual("CORE_API_CANDIDATE_REVIEW_ONLY", result["scope"])
        self.assertEqual({"commit": self.sha, "tree": self.tree}, result["source"])
        self.assertEqual({"path": A.WORKFLOW, "commit": self.sha}, result["workflow"])
        self.assertEqual(list(A.TASKS), result["tasks"])
        self.assertEqual("strict", result["dependencyVerification"])
        self.assertFalse(result["dependencyWritesAllowed"])
        self.assertFalse(result["releaseQualified"])
        self.assertTrue(result["requiresReviewBeforeApply"])
        self.assertEqual("CHANGED", result["outcome"])
        self.assertEqual(list(A.API_FILES), result["changedFiles"])
        self.assertEqual([
            {"path": name, "beforeSha256": hashlib.sha256(self.original_api[name]).hexdigest(),
             "afterSha256": hashlib.sha256(self.generated_api[name]).hexdigest(),
             "beforeBytes": len(self.original_api[name]), "afterBytes": len(self.generated_api[name])}
            for name in A.API_FILES], result["files"])
        self.assertEqual({"path": "core-api-candidate.patch", "bytes": len(patch_bytes),
                          "sha256": hashlib.sha256(patch_bytes).hexdigest()}, result["patch"])
        self.assertEqual("API_CANDIDATE REVIEW_ONLY manifest-sha256=" +
                         hashlib.sha256(raw_manifest).hexdigest() + "\n", self.log.getvalue())
        self.assertLess(len(raw_manifest), 8192)
        self.assertEqual(["+++ b/" + name for name in A.API_FILES],
                         [line for line in patch_bytes.decode().splitlines() if line.startswith("+++ ")])
        self.command(self.controller, "apply", "--check", "-", input=patch_bytes)
        self.assertNotIn(b"synthetic ignored build output", raw_manifest + patch_bytes)
        self.assert_retired()

    def test_rpc_candidate_changes_only_rpc_baselines_and_uses_rpc_tasks(self):
        files = A.api_files("p2p-rpc")
        for name in files:
            path = self.controller / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(api(name.endswith(".klib.api")).replace(b"p2pkit.core", b"p2pkit.rpc")
                             .replace(b"p2pkit/core", b"p2pkit/rpc"))
        self.command(self.controller, "add", ".")
        self.command(self.controller, "commit", "--quiet", "-m", "Synthetic RPC baseline")
        self.sha = A.git(self.controller, "rev-parse", "HEAD").decode().strip()
        original = A.snapshot(self.controller, "p2p-rpc")
        calls = []
        def generation(argv, **options):
            calls.append(argv)
            if argv[-1] != "--stop" and argv[0] != "bash":
                self.assertEqual([":p2p-rpc:updateKotlinAbi", ":p2p-rpc:updateAndroidAbi"], argv[-2:])
                for name in files:
                    (Path(options["cwd"]) / name).write_bytes(
                        api(name.endswith(".klib.api"), True).replace(b"p2pkit.core", b"p2pkit.rpc")
                        .replace(b"p2pkit/core", b"p2pkit/rpc"))
            return subprocess.CompletedProcess(argv, 0)
        with contextlib.redirect_stdout(self.log):
            result = A.execute(self.controller, self.sha, self.output, self.temporary,
                               module="p2p-rpc", run=generation)
        self.assertEqual("RPC_API_CANDIDATE_REVIEW_ONLY", result["scope"])
        self.assertEqual("p2p-rpc", result["module"])
        self.assertEqual(list(files), result["changedFiles"])
        self.assertEqual("rpc-api-candidate.patch", result["patch"]["path"])
        self.assertEqual({"rpc-api-candidate.patch", "rpc-api-candidate.json"},
                         {path.name for path in self.output.iterdir()})
        self.command(self.controller, "apply", "--check", "-",
                     input=(self.output / "rpc-api-candidate.patch").read_bytes())
        self.assertEqual(original, A.snapshot(self.controller, "p2p-rpc"))
        self.assertFalse(list(self.temporary.glob("rpc-api-worktree-*")))
        self.assertEqual(4, len(calls))

    def test_unsupported_module_refuses_before_git_or_execution(self):
        for module in ("other", "../p2p-core", "p2p-rpc; echo wrong", "p2p-rpc\n"):
            with self.subTest(module=module), self.assertRaisesRegex(A.CandidateError, "MODULE"):
                A.execute(self.controller, self.sha, self.output, self.temporary,
                          module=module, run=self.model())
        self.assertFalse(self.calls)
        self.assertFalse(self.output.exists())

    def test_successful_unchanged_generation_does_not_invent_an_api_delta(self):
        result = self.execute(unchanged=True)
        self.assertEqual("UNCHANGED", result["outcome"])
        self.assertEqual([], result["changedFiles"])
        self.assertEqual(b"", (self.output / "core-api-candidate.patch").read_bytes())
        self.assertEqual(hashlib.sha256(b"").hexdigest(), result["patch"]["sha256"])
        self.assertEqual(4, len(self.calls))
        self.assert_retired()

    def test_wrong_or_abbreviated_sha_refuses_before_any_execution(self):
        for sha in ("0" * 40, self.sha[:12], self.sha.upper(), "main", self.sha + "\n"):
            with self.subTest(sha=sha), self.assertRaisesRegex(A.CandidateError, "SOURCE_SHA"):
                A.execute(self.controller, sha, self.output, self.temporary, run=self.model())
        self.assertEqual([], self.calls)
        self.assertFalse(self.output.exists())
        self.assert_retired()

    def test_dirty_staged_and_untracked_controller_refuse_before_execution(self):
        for change in ("tracked", "staged", "untracked"):
            with self.subTest(change=change):
                target = self.controller / ("new.txt" if change == "untracked" else "product.txt")
                target.write_text("not the reviewed input\n")
                if change == "staged":
                    self.command(self.controller, "add", "product.txt")
                with self.assertRaises(A.CandidateError):
                    self.execute()
                self.assertFalse(self.output.exists())
                self.assertEqual([], self.calls)
                self.command(self.controller, "reset", "--hard", "HEAD")
                self.command(self.controller, "clean", "-fd")
        self.assert_retired()

    def test_existing_nested_or_controller_output_is_not_used(self):
        existing = self.temporary / "existing"
        existing.mkdir()
        (existing / "retain.txt").write_text("retain\n")
        for output in (existing, existing / "nested", self.controller / "candidate"):
            with self.subTest(output=output), self.assertRaisesRegex(A.CandidateError, "OUTPUT_PATH"):
                A.execute(self.controller, self.sha, output, self.temporary, run=self.model())
        self.assertEqual("retain\n", (existing / "retain.txt").read_text())
        self.assertEqual([], self.calls)
        self.assert_retired()

    def test_non_api_source_lock_checksum_and_other_module_api_writes_refuse(self):
        for name in ("product.txt", "gradle.lockfile", "library/p2p-core/gradle.lockfile",
                     "gradle/verification-metadata.xml", "library/other/api/other.api"):
            with self.subTest(name=name), self.assertRaisesRegex(A.CandidateError, "NON_API_SOURCE_CHANGED"):
                self.execute(mutate=lambda candidate: (candidate / name).write_text("forbidden write\n"))
            self.assertFalse(self.output.exists())
            self.assert_retired()

    def test_assume_unchanged_cannot_hide_non_api_writes(self):
        def mutate(candidate):
            self.command(candidate, "update-index", "--assume-unchanged", "product.txt")
            (candidate / "product.txt").write_text("hidden write\n")
        with self.assertRaisesRegex(A.CandidateError, "NON_API_SOURCE_CHANGED"):
            self.execute(mutate=mutate)
        self.assertFalse(self.output.exists())
        self.assert_retired()

    def test_staged_untracked_removed_mode_changed_and_linked_output_refuse(self):
        for change in ("staged", "untracked", "removed", "mode", "permissions", "symlink", "hardlink", "directory"):
            self.calls.clear()
            def mutate(candidate):
                target = candidate / A.API_FILES[0]
                if change == "staged":
                    self.command(candidate, "add", A.API_FILES[0])
                elif change == "untracked":
                    (candidate / "unexpected.txt").write_text("unapproved new source\n")
                elif change == "mode":
                    target.chmod(0o755)
                elif change == "permissions":
                    target.chmod(target.stat().st_mode ^ 0o040)
                else:
                    target.unlink()
                    if change == "symlink":
                        target.symlink_to(self.controller / A.API_FILES[0])
                    elif change == "hardlink":
                        os.link(self.controller / A.API_FILES[0], target)
                    elif change == "directory":
                        target.mkdir()
            with self.subTest(change=change), self.assertRaises((A.CandidateError, OSError)):
                self.execute(mutate=mutate)
            self.assertEqual(4, len(self.calls))
            self.assertFalse(self.output.exists())
            self.assert_retired()

    def test_generation_cannot_change_source_revision(self):
        def mutate(candidate):
            self.command(candidate, "commit", "--quiet", "--allow-empty", "-m", "Wrong detached revision")
        with self.assertRaisesRegex(A.CandidateError, "SOURCE_SHA"):
            self.execute(mutate=mutate)
        self.assertFalse(self.output.exists())
        self.assert_retired()

    def test_failed_generation_or_stop_cannot_export_even_valid_written_apis(self):
        for generation, stop in ((7, 0), (0, 9), (7, 9)):
            with self.subTest(generation=generation, stop=stop):
                self.calls.clear()
                with self.assertRaisesRegex(A.CandidateError, "GENERATION_OR_STOP_FAILED"):
                    self.execute(generation=generation, stop=stop)
                self.assertEqual(4, len(self.calls))
                self.assertEqual("--stop", self.calls[-1][0][-1])
                self.assertFalse(self.output.exists())
                self.assertEqual("", self.log.getvalue())
                self.assert_retired()

    def test_prerequisite_failure_never_executes_gradle(self):
        with self.assertRaisesRegex(A.CandidateError, "PREREQUISITE_FAILED"):
            self.execute(prerequisite=5)
        self.assertEqual(1, len(self.calls))
        self.assertEqual("bash", self.calls[0][0][0])
        self.assertFalse(self.output.exists())
        self.assert_retired()

    def test_launch_or_timeout_exception_still_stops_and_refuses(self):
        for error in (OSError("synthetic private detail"), subprocess.TimeoutExpired("fixture", 1)):
            def mutate(_candidate):
                raise error
            with self.subTest(error=type(error).__name__), self.assertRaises(type(error)):
                self.execute(mutate=mutate)
            self.assertEqual("--stop", self.calls[-1][0][-1])
            self.assertFalse(self.output.exists())
            self.assert_retired()

    def test_each_api_file_must_be_nonempty_utf8_lf_and_have_dump_structure(self):
        for name in A.API_FILES:
            for raw in (b"", b"\xff\n", b"not an API dump\n", self.generated_api[name] + b"\0\n",
                        self.generated_api[name].replace(b"\n", b"\r\n"), self.generated_api[name].rstrip(b"\n"),
                        self.generated_api[name].replace(b"}\n", b"")):
                self.calls.clear()
                with self.subTest(name=name, raw=raw[:20]), self.assertRaises((A.CandidateError, UnicodeError)):
                    self.execute(mutate=lambda candidate: (candidate / name).write_bytes(raw))
                self.assertEqual(4, len(self.calls))
                self.assertFalse(self.output.exists())
                self.assert_retired()

    def test_native_dump_requires_all_three_targets_and_a_real_core_declaration(self):
        raw = self.generated_api[A.API_FILES[0]]
        for invalid in (raw.replace(b"iosX64", b"macosX64"),
                        raw.replace(b"dev.p2pkit.core/", b"other.package/"),
                        b"// Klib ABI Dump\n// Targets: [iosArm64, iosSimulatorArm64, iosX64]\n// dev.p2pkit.core/\n"):
            self.calls.clear()
            with self.subTest(invalid=invalid[:60]), self.assertRaisesRegex(A.CandidateError, "INVALID_NATIVE_API"):
                self.execute(mutate=lambda candidate: (candidate / A.API_FILES[0]).write_bytes(invalid))
            self.assertEqual(4, len(self.calls))
            self.assertFalse(self.output.exists())
            self.assert_retired()

    def test_api_and_review_patch_limits_refuse_before_export(self):
        with patch.object(A, "MAX_API_BYTES", 8), self.assertRaisesRegex(A.CandidateError, "SOURCE_FILE"):
            self.execute()
        self.assertEqual([], self.calls)
        self.assertFalse(self.output.exists())
        self.assert_retired()
        with patch.object(A, "MAX_PATCH_BYTES", 1), self.assertRaisesRegex(A.CandidateError, "PATCH_LIMIT"):
            self.execute()
        self.assertEqual(4, len(self.calls))
        self.assertFalse(self.output.exists())
        self.assert_retired()

    def test_controller_bytes_must_still_match_even_when_git_status_hides_change(self):
        def mutate(_candidate):
            self.command(self.controller, "update-index", "--assume-unchanged", "product.txt")
            (self.controller / "product.txt").write_text("external controller change\n")
        with self.assertRaisesRegex(A.CandidateError, "CONTROLLER_CHANGED"):
            self.execute(mutate=mutate)
        self.assertFalse(self.output.exists())
        self.assert_retired(controller_unchanged=False)
        # A failed operation reports interference, never resets someone else's source.
        self.assertEqual("external controller change\n", (self.controller / "product.txt").read_text())


class RequestAndWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parsed = subprocess.run(["ruby", "-ryaml", "-rjson", "-e",
                                 "print JSON.generate(YAML.safe_load(File.read(ARGV.fetch(0)), aliases: false))",
                                 str(ROOT / A.WORKFLOW)], capture_output=True, check=True)
        cls.workflow = json.loads(parsed.stdout)
        cls.job = cls.workflow["jobs"]["generate"]

    def test_matching_full_sha_host_repository_event_and_workflow_are_required(self):
        sha = "abcdef0123456789" * 2 + "abcdef01"
        environment = request_environment(sha)
        A.validate_request(sha, environment)
        for key, wrong in (("GITHUB_SHA", "0" * 40), ("GITHUB_WORKFLOW_SHA", "0" * 40),
                           ("GITHUB_ACTIONS", "false"), ("GITHUB_JOB", "register"),
                           ("GITHUB_REPOSITORY", "fork/P2pKit"), ("GITHUB_EVENT_NAME", "push"),
                           ("GITHUB_WORKFLOW_REF", "p2pKit/P2pKit/.github/workflows/ci.yml@refs/heads/main"),
                           ("RUNNER_ENVIRONMENT", "self-hosted"), ("RUNNER_OS", "Linux"),
                           ("RUNNER_ARCH", "ARM64")):
            for value in (wrong, ""):
                with self.subTest(key=key, value=value), self.assertRaises(A.CandidateError):
                    A.validate_request(sha, {**environment, key: value})
        for wrong in (sha[:12], sha.upper(), "main", sha + "\n"):
            with self.subTest(wrong=wrong), self.assertRaisesRegex(A.CandidateError, "REQUEST_SHA"):
                A.validate_request(wrong, {**environment, "GITHUB_SHA": wrong, "GITHUB_WORKFLOW_SHA": wrong})

    def test_main_redacts_unexpected_errors_and_offers_no_arbitrary_task_argument(self):
        sha = "a" * 40
        with patch.dict(os.environ, {**request_environment(sha), "RUNNER_TEMP": "/unused"}, clear=True), \
                patch.object(A, "execute", side_effect=OSError("synthetic private path or log")) as execute, \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            self.assertEqual(1, A.main(["--source-sha", sha, "--output", "/unused/review"]))
            self.assertEqual("API_CANDIDATE FAIL OSError\n", stderr.getvalue())
            execute.assert_called_once()
        with patch.object(A, "execute") as execute, contextlib.redirect_stderr(io.StringIO()), \
                self.assertRaises(SystemExit) as failure:
            A.main(["--source-sha", sha, "--output", "/unused/review", "--task", "publish"])
        self.assertEqual(2, failure.exception.code)
        execute.assert_not_called()

    def test_workflow_has_exact_source_and_bounded_module_inputs_and_only_read_permissions(self):
        workflow, job = self.workflow, self.job
        events = workflow.get("on", workflow.get("true"))
        self.assertEqual(["push", "workflow_dispatch"], list(events))
        inputs = events["workflow_dispatch"]["inputs"]
        self.assertEqual(["source_sha", "module"], list(inputs))
        self.assertEqual("choice", inputs["module"]["type"])
        self.assertEqual("p2p-core", inputs["module"]["default"])
        self.assertEqual(["p2p-core", "p2p-rpc"], inputs["module"]["options"])
        self.assertEqual("string", inputs["source_sha"]["type"])
        self.assertIs(True, inputs["source_sha"]["required"])
        self.assertNotIn("default", inputs["source_sha"])
        self.assertEqual({"contents": "read", "actions": "read"}, workflow["permissions"])
        self.assertEqual({"group": "prepare-api-candidate-${{ github.ref }}-${{ inputs.module || 'p2p-core' }}",
                          "cancel-in-progress": False}, workflow["concurrency"])
        self.assertEqual(["register", "generate"], list(workflow["jobs"]))
        self.assertEqual("${{ github.repository == 'p2pKit/P2pKit' && github.event_name == 'workflow_dispatch' }}", job["if"])
        self.assertEqual("macos-15-intel", job["runs-on"])
        self.assertEqual(120, job["timeout-minutes"])
        self.assertNotIn("environment", job)
        self.assertNotIn("secrets", job)
        for step in job["steps"]:
            self.assertNotIn("continue-on-error", step)
            if "uses" in step:
                self.assertRegex(step["uses"], r"@[0-9a-f]{40}$")
        raw = json.dumps(workflow)
        for forbidden in ("secrets.", "github.token", "write-locks", "write-verification-metadata",
                          "run-hosted", "initial-recipient", "qualification_selection"):
            self.assertNotIn(forbidden, raw)

    def test_registration_push_is_one_exact_branch_and_file_with_no_checkout_or_build(self):
        events = self.workflow.get("on", self.workflow.get("true"))
        self.assertEqual({"branches": ["work/readiness-source-20261024-khnosw"],
                          "paths": [A.WORKFLOW]}, events["push"])
        registration = self.workflow["jobs"]["register"]
        self.assertEqual({
            "name": "Register the maintenance workflow without building",
            "if": "${{ github.repository == 'p2pKit/P2pKit' && github.event_name == 'push' && "
                  "github.ref == 'refs/heads/work/readiness-source-20261024-khnosw' }}",
            "runs-on": "ubuntu-24.04", "timeout-minutes": 2,
            "steps": [{"run": "echo 'Registration only. Explicitly dispatch the reviewed source SHA "
                      "to generate an API candidate.'"}],
        }, registration)

    def test_precheckout_guard_is_executable_and_rejects_a_different_source(self):
        guard = self.job["steps"][0]
        self.assertEqual("python3 {0}", guard["shell"])
        code = compile(guard["run"], "workflow-sha-guard", "exec")
        sha = "a" * 40
        with tempfile.TemporaryDirectory(prefix="api-candidate-guard-") as owned:
            env_file = Path(owned) / "job-env"
            environment = {**request_environment(sha), "API_CANDIDATE_SOURCE_SHA": sha,
                           "RUNNER_TEMP": owned, "GITHUB_ENV": str(env_file)}
            for key in ("API_CANDIDATE_SOURCE_SHA", "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "RUNNER_ENVIRONMENT"):
                with self.subTest(key=key), patch.dict(os.environ, {**environment, key: "wrong"}, clear=True), \
                        self.assertRaises(SystemExit):
                    exec(code, {})
                self.assertFalse(env_file.exists())
            with patch.dict(os.environ, environment, clear=True):
                exec(code, {})
            self.assertEqual(["GRADLE_USER_HOME=" + owned + "/api-candidate-gradle-home",
                              "KONAN_DATA_DIR=" + owned + "/api-candidate-konan"], env_file.read_text().splitlines())

    def test_workflow_has_credential_free_checkout_standard_tools_and_read_only_cache(self):
        steps = self.job["steps"]
        checkout = [step for step in steps if step.get("uses", "").startswith("actions/checkout@")]
        self.assertEqual(1, len(checkout))
        self.assertEqual({"ref": "${{ github.sha }}", "fetch-depth": 0, "persist-credentials": False}, checkout[0]["with"])
        java = [step for step in steps if step.get("uses", "").startswith("actions/setup-java@")]
        self.assertEqual(["21", "17"], [step["with"]["java-version"] for step in java])
        self.assertTrue(all(step["with"]["distribution"] == "temurin" for step in java))
        caches = [step for step in steps if step.get("uses", "").startswith("gradle/actions/setup-gradle@")]
        self.assertEqual(1, len(caches))
        self.assertIs(True, caches[0]["with"]["cache-read-only"])
        self.assertEqual(["caches/build-cache-1", "caches/*/kotlin-dsl", "caches/*/scripts", "caches/*/groovy-dsl"],
                         caches[0]["with"]["gradle-home-cache-excludes"].splitlines())
        setup = next(i for i, step in enumerate(steps) if step.get("run") == "bash scripts/setup-ci-component.sh consumers")
        generation = next(i for i, step in enumerate(steps) if step.get("id") == "generation")
        self.assertLess(setup, generation)
        self.assertEqual("python3 -B scripts/ci_evidence.py --component api-candidate --timeout-seconds 5400 "
                         '--output-dir "$RUNNER_TEMP/api-candidate-evidence" -- python3 -B scripts/prepare-api-candidate.py '
                         '--source-sha "$API_CANDIDATE_SOURCE_SHA" --module "$API_CANDIDATE_MODULE" '
                         '--output "$RUNNER_TEMP/$API_CANDIDATE_PREFIX-api-candidate"\n',
                         steps[generation]["run"])
        for suffix in ("SHA256", "FINGERPRINT"):
            self.assertEqual("${{ vars.CI_EVIDENCE_RECIPIENT_" + suffix + " }}",
                             self.job["env"]["CI_EVIDENCE_RECIPIENT_" + suffix])

    def test_only_encrypted_diagnostics_survive_failure_and_review_upload_requires_success(self):
        uploads = [step for step in self.job["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
        self.assertEqual(2, len(uploads))
        evidence, review = uploads
        self.assertEqual("${{ always() && steps.generation.outcome != 'skipped' }}", evidence["if"])
        self.assertEqual("${{ success() }}", review["if"])
        self.assertEqual(["${{ runner.temp }}/api-candidate-evidence/" + name for name in
                          ("manifest.json", "evidence.tar.gz.gpg", "failure.json")], evidence["with"]["path"].splitlines())
        self.assertEqual(["${{ runner.temp }}/${{ env.API_CANDIDATE_PREFIX }}-api-candidate/" + name for name in
                          ("${{ env.API_CANDIDATE_PREFIX }}-api-candidate.patch",
                           "${{ env.API_CANDIDATE_PREFIX }}-api-candidate.json")], review["with"]["path"].splitlines())
        for upload in uploads:
            self.assertEqual(14, upload["with"]["retention-days"])
            self.assertEqual("error", upload["with"]["if-no-files-found"])
            self.assertIs(False, upload["with"]["overwrite"])
            self.assertNotIn("**", upload["with"]["path"])

    def test_existing_four_real_baselines_pass_dump_shape_without_a_build(self):
        baselines = A.api_bytes(ROOT)
        self.assertEqual(set(A.API_FILES), set(baselines))
        self.assertTrue(all(baselines.values()))

    def test_source_ci_runs_fixture_controls_once_without_adding_a_generation_component(self):
        spec = importlib.util.spec_from_file_location("api_candidate_ci", ROOT / "scripts/ci_component.py")
        component = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(component)
        name = "prepare-api-candidate-test.py"
        commands = component.commands("source")
        self.assertEqual([[component.sys.executable, "-B", "scripts/tests/" + name, "-v"]],
                         [argv for task, argv in commands if task == name])
        self.assertNotIn("api-candidate", component.COMPONENTS)
        self.assertNotIn("api-candidate", component.DIAGNOSTICS)
        with self.assertRaises(ValueError):
            component.matrix("api-candidate")


if __name__ == "__main__":
    unittest.main()
