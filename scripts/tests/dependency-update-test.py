#!/usr/bin/env python3
"""Tiny real Git checkouts + modeled generator; no Gradle/network/private key."""
import copy
import contextlib
import io
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import sys
import unittest
from unittest.mock import Mock, patch

SPEC = importlib.util.spec_from_file_location("dependency_update", Path(__file__).resolve().parents[1] / "dependency_update.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)


def xml(extra=False):
    component = lambda name: ('<component group="org.example" name="' + name + '" version="1">'
                              '<artifact name="' + name + '.jar"><sha256 value="' + 'a' * 64 + '"/></artifact></component>')
    return ('<verification-metadata xmlns="https://schema.gradle.org/dependency-verification">'
            '<configuration><verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures></configuration>'
            '<components>' + component('old') + (component('new') if extra else '') + '</components></verification-metadata>').encode()


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dependency-update-model-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        self.controller, self.candidate = self.parent / "controller", self.parent / "candidate"
        self.controller.mkdir()
        self.command(self.controller, "init", "--quiet")
        for name in (*D.HELPERS, D.XML, "gradle.lockfile", "product.txt", ".gitignore"):
            path = self.controller / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(xml() if name == D.XML else b"build/\n" if name == ".gitignore" else b"original\n")
        self.command(self.controller, "add", ".")
        self.command(self.controller, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                     "commit", "--quiet", "-m", "Synthetic initial source")
        self.command(self.parent, "clone", "--quiet", "--no-hardlinks", str(self.controller), str(self.candidate))
        commit = D.git(self.controller, "rev-parse", "HEAD").decode().strip()
        tree = D.git(self.controller, "rev-parse", "HEAD^{tree}").decode().strip()
        self.request = {"controller_sha": commit, "controller_tree": tree, "candidate_sha": commit,
                        "candidate_tree": tree, "dependency_base_sha": commit}
        self.output = self.parent / "public"
        self.calls = []
        self.reports = Mock()

    @staticmethod
    def command(root, *arguments):
        return subprocess.run(["git", "-C", str(root), *arguments], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def generator(self, argv, **options):
        self.calls.append((argv, options))
        if argv[-1] != "--stop":
            (self.candidate / D.XML).write_bytes(xml(True))
            (self.candidate / "gradle.lockfile").write_text("new lock\n")
        return Mock(returncode=0)

    def execute(self, **options):
        return D.execute(self.controller, self.candidate, self.request, self.output,
                         run=options.get("run", self.generator), reports=self.reports)

    def test_actual_git_delta_invokes_unchanged_generator_and_is_not_qualification(self):
        result = self.execute()
        self.assertEqual("DEPENDENCY_UPDATE_CANDIDATE_NOT_QUALIFICATION", result["scope"])
        self.assertFalse(result["releaseQualified"])
        self.assertTrue(result["requiresReviewBeforeApply"])
        self.assertEqual(1, result["addedVerifiedArtifacts"])
        self.assertEqual("UPDATED_VERIFICATION", result["outcome"])
        self.assertEqual(["gradle.lockfile", D.XML], [row["path"] for row in result["changes"]])
        self.assertEqual([str(self.candidate / "scripts/prepare-dependency-update.sh"), self.request["dependency_base_sha"]], self.calls[0][0])
        self.assertEqual("1", self.calls[0][1]["env"]["P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED"])
        self.assertEqual("1", self.calls[0][1]["env"]["P2PKIT_DEPENDENCY_TERMINAL_GENERATE"])
        self.assertNotIn("env", self.calls[1][1])
        self.assertEqual(([str(self.candidate / "gradlew"), "--stop"], 90), (self.calls[1][0], self.calls[1][1]["timeout"]))
        self.assertEqual({"generated-dependencies.patch", "generated-dependencies.json"}, {p.name for p in self.output.iterdir()})
        self.assertEqual(result, json.loads((self.output / "generated-dependencies.json").read_text()))
        self.assertEqual(b"", D.git(self.controller, "status", "--porcelain=v1"))

    def test_real_invocation_sequence_can_report_unchanged_without_inventing_delta(self):
        def unchanged(argv, **kwargs):
            self.calls.append((argv, kwargs))
            return Mock(returncode=0)
        before_environment = dict(os.environ)
        result = self.execute(run=unchanged)
        self.assertEqual("UNCHANGED", result["outcome"])
        self.assertEqual([], result["changes"])
        self.assertEqual(0, result["addedVerifiedArtifacts"])
        self.assertEqual({"sha256": hashlib.sha256(b"").hexdigest(), "bytes": 0}, result["patch"])
        self.assertEqual(b"", (self.output / "generated-dependencies.patch").read_bytes())
        self.assertFalse(result["releaseQualified"])
        self.assertEqual(2, len(self.calls))  # modeled real generator, then original bounded stop
        self.assertEqual("1", self.calls[0][1]["env"]["P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED"])
        self.assertEqual("1", self.calls[0][1]["env"]["P2PKIT_DEPENDENCY_TERMINAL_GENERATE"])
        self.assertNotIn("env", self.calls[1][1])
        self.assertEqual(before_environment, dict(os.environ))
        self.reports.assert_called_once()

    def test_lock_only_delta_requires_unchanged_complete_verification(self):
        def lock_only(argv, **kwargs):
            if argv[-1] != "--stop":
                (self.candidate / "gradle.lockfile").write_text("regenerated lock graph\n")
            return Mock(returncode=0)
        result = self.execute(run=lock_only)
        self.assertEqual("LOCK_ONLY", result["outcome"])
        self.assertEqual(["gradle.lockfile"], [row["path"] for row in result["changes"]])
        self.assertEqual(0, result["addedVerifiedArtifacts"])
        self.assertGreater(result["patch"]["bytes"], 0)

    def test_equal_checksum_set_does_not_allow_xml_rewrite_or_failed_noop(self):
        for change in ("format", "annotation", "generator", "stop"):
            self.command(self.candidate, "reset", "--hard", "HEAD")
            def modeled(argv, **kwargs):
                if argv[-1] != "--stop":
                    if change == "format":
                        (self.candidate / D.XML).write_bytes(xml() + b"\n")
                    elif change == "annotation":
                        (self.candidate / D.XML).write_bytes(xml().replace(b'<sha256 value=', b'<sha256 reason="changed" value='))
                    return Mock(returncode=7 if change == "generator" else 0)
                return Mock(returncode=7 if change == "stop" else 0)
            expected = "GENERATION_OR_GRADLE_STOP_FAILED" if change in ("generator", "stop") else "UNCHANGED_VERIFICATION_BYTES_DIFFER"
            with self.subTest(change=change), self.assertRaisesRegex(D.UpdateError, expected):
                self.execute(run=modeled)
            self.assertFalse(self.output.exists())

    def test_stale_source_or_base_never_executes_generator(self):
        for key in self.request:
            with self.subTest(key=key):
                request = {**self.request, key: "0" * 40}
                with self.assertRaises(D.UpdateError):
                    D.execute(self.controller, self.candidate, request, self.output, run=self.generator)
        self.assertFalse(self.calls)

    def test_changed_or_dirty_maintained_helper_refuses(self):
        (self.candidate / D.HELPERS[0]).write_text("changed wrapper")
        with self.assertRaisesRegex(D.UpdateError, "SOURCE_DIRTY"):
            self.execute()
        self.assertFalse(self.calls)

    def test_committed_helper_difference_and_malformed_request_refuse(self):
        for request in (None, [], {**self.request, "extra": "a" * 40}, {**self.request, "candidate_sha": True}):
            with self.subTest(request=request), self.assertRaisesRegex(D.UpdateError, "REQUEST_IDENTITY"):
                D.execute(self.controller, self.candidate, request, self.output, run=self.generator)
        (self.candidate / D.HELPERS[0]).write_text("different committed wrapper")
        self.command(self.candidate, "add", D.HELPERS[0])
        self.command(self.candidate, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                     "commit", "--quiet", "-m", "Different generator")
        self.request.update(candidate_sha=D.git(self.candidate, "rev-parse", "HEAD").decode().strip(),
                            candidate_tree=D.git(self.candidate, "rev-parse", "HEAD^{tree}").decode().strip())
        with self.assertRaisesRegex(D.UpdateError, "MAINTAINED_GENERATOR_CHANGED"):
            self.execute()
        self.assertFalse(self.calls)

    def test_current_public_verification_schema_and_nested_policy_refusal(self):
        _, entries = D.verification((Path(__file__).resolve().parents[2] / D.XML).read_bytes())
        self.assertGreater(len(entries), 0)
        for raw in (xml().replace(b'<components>', b'<components trust="all">'),
                    xml().replace(b'/></artifact>', b'><trusted/></sha256></artifact>'),
                    xml().replace(b'</components>', b'not-checksums</components>')):
            with self.subTest(raw=raw[:30]), self.assertRaises(D.UpdateError):
                D.verification(raw)

    def test_non_dependency_or_untracked_or_staged_changes_refuse(self):
        for change in ("product", "untracked", "staged", "mode", "link"):
            with self.subTest(change=change):
                self.command(self.candidate, "reset", "--hard", "HEAD")
                self.command(self.candidate, "clean", "-fd")
                def altered(argv, **kwargs):
                    result = self.generator(argv, **kwargs)
                    if argv[-1] != "--stop":
                        if change == "product":
                            (self.candidate / "product.txt").write_text("bad change")
                        elif change == "untracked":
                            (self.candidate / "unknown.lockfile").write_text("unapproved new path")
                        elif change == "staged":
                            self.command(self.candidate, "add", "gradle.lockfile")
                        elif change == "mode":
                            (self.candidate / "gradle.lockfile").chmod(0o755)
                        else:
                            path = self.candidate / "gradle.lockfile"
                            path.unlink(); path.symlink_to(self.controller / "gradle.lockfile")
                    return result
                with self.assertRaises(D.UpdateError):
                    self.execute(run=altered)
                self.assertFalse(self.output.exists())

    def test_removed_hash_or_changed_trust_is_not_an_update(self):
        for raw in (xml(True).replace(b'name="old"', b'name="replaced"'),
                    xml(True).replace(b'<verify-metadata>true', b'<verify-metadata>false')):
            with self.subTest(raw=raw[:25]):
                self.command(self.candidate, "reset", "--hard", "HEAD")
                def altered(argv, **kwargs):
                    result = self.generator(argv, **kwargs)
                    if argv[-1] != "--stop":
                        (self.candidate / D.XML).write_bytes(raw)
                    return result
                with self.assertRaises(D.UpdateError):
                    self.execute(run=altered)
                self.assertFalse(self.output.exists())

    def test_diagnostic_exits_are_actual_original_returns_and_do_not_change_failure(self):
        for codes in ((9, 0), (0, 7), (9, 7)):
            with self.subTest(codes=codes):
                self.command(self.candidate, "reset", "--hard", "HEAD")
                returns = iter(codes)
                def failed(argv, **kwargs):
                    self.generator(argv, **kwargs)
                    return Mock(returncode=next(returns))
                diagnostic = io.StringIO()
                with contextlib.redirect_stdout(diagnostic), self.assertRaisesRegex(D.UpdateError, "GENERATION_OR_GRADLE_STOP_FAILED"):
                    self.execute(run=failed)
                self.assertEqual(diagnostic.getvalue(),
                    f"DEPENDENCY_UPDATE_STEP GENERATOR EXIT {codes[0]}\nDEPENDENCY_UPDATE_STEP GRADLE_STOP EXIT {codes[1]}\n")
                self.assertFalse(self.output.exists())
                self.assertEqual(self.calls[-1][0][-1], "--stop")
                self.assertEqual(self.calls[-1][1]["timeout"], 90)
        self.assertEqual(self.reports.call_count, 3)

    def test_diagnostic_no_invented_exit_on_launch_or_report_error(self):
        for failing in ("generator", "stop", "reports"):
            with self.subTest(failing=failing):
                original = OSError("PRIVATE_UNAVAILABLE_PATH")
                self.reports.reset_mock()
                self.reports.side_effect = original if failing == "reports" else None
                calls = []
                def invoke(argv, **kwargs):
                    step = "stop" if argv[-1] == "--stop" else "generator"
                    calls.append(step)
                    if step == failing:
                        raise original
                    return Mock(returncode=7 if step == "generator" else 0)
                diagnostic = io.StringIO()
                with contextlib.redirect_stdout(diagnostic), self.assertRaises(OSError) as caught:
                    self.execute(run=invoke)
                self.assertIs(caught.exception, original)
                expected = ("" if failing == "generator" else "DEPENDENCY_UPDATE_STEP GENERATOR EXIT 7\n")
                expected += "" if failing == "stop" else "DEPENDENCY_UPDATE_STEP GRADLE_STOP EXIT 0\n"
                self.assertEqual(diagnostic.getvalue(), expected)
                self.assertEqual(calls, ["generator", "stop"])
                self.reports.assert_called_once()
                self.assertFalse(self.output.exists())

    def test_diagnostic_step_output_is_typed_bounded_and_closed(self):
        diagnostic = io.StringIO()
        with contextlib.redirect_stdout(diagnostic):
            for value in (True, "PRIVATE", None, -(2**31)-1, 2**32):
                D.step_exit_diagnostic("GENERATOR", value)
            D.step_exit_diagnostic("PRIVATE", 0)
        self.assertEqual(diagnostic.getvalue(), "")
        with contextlib.redirect_stdout(diagnostic):
            D.step_exit_diagnostic("GENERATOR", -(2**31))
            D.step_exit_diagnostic("GRADLE_STOP", 2**32-1)
        self.assertEqual(diagnostic.getvalue(),
                         "DEPENDENCY_UPDATE_STEP GENERATOR EXIT -2147483648\nDEPENDENCY_UPDATE_STEP GRADLE_STOP EXIT 4294967295\n")

    def test_generator_failure_and_stop_failure_never_publish_candidate(self):
        for codes in ((9, 0), (0, 7)):
            with self.subTest(codes=codes):
                self.command(self.candidate, "reset", "--hard", "HEAD")
                returns = iter(codes)
                def failed(argv, **kwargs):
                    self.generator(argv, **kwargs)
                    return Mock(returncode=next(returns))
                with self.assertRaisesRegex(D.UpdateError, "GENERATION_OR_GRADLE_STOP_FAILED"):
                    self.execute(run=failed)
                self.assertFalse(self.output.exists())
                self.assertEqual("--stop", self.calls[-1][0][-1])
        self.assertEqual(2, self.reports.call_count)

    def test_failed_generator_retains_actual_android_originals_but_no_candidate(self):
        with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
            import ci_evidence
        expected = {}
        for module in ("p2p-core", "p2p-transport-lan", "p2p-rpc", "p2p-network-provisioning-android"):
            for directory in ("abi/android", "androidAbi"):
                relative = f"library/{module}/build/kotlin/{directory}/{module}.api"
                expected[relative] = (relative + " synthetic original\n").encode()
                path = self.candidate / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(expected[relative])

        def failed(argv, **options):
            self.generator(argv, **options)
            return Mock(returncode=0 if argv[-1] == "--stop" else 9)

        diagnostic = io.StringIO()
        with patch.object(sys, "path", list(sys.path)), contextlib.redirect_stdout(diagnostic):
            with self.assertRaisesRegex(D.UpdateError, "GENERATION_OR_GRADLE_STOP_FAILED"):
                D.execute(self.controller, self.candidate, self.request, self.output, run=failed)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.calls[-1][0][-1], "--stop")
        self.assertEqual(diagnostic.getvalue(),
                         "DEPENDENCY_UPDATE_STEP GENERATOR EXIT 9\nDEPENDENCY_UPDATE_STEP GRADLE_STOP EXIT 0\n")
        destination = self.controller / "build/reports/dependency-update"
        self.assertEqual({p.relative_to(destination).as_posix(): p.read_bytes()
                          for p in destination.rglob("*") if p.is_file()}, expected)

    def test_spawn_failure_still_attempts_original_gradle_stop(self):
        calls = []
        def failed(argv, **kwargs):
            calls.append(argv)
            if argv[-1] != "--stop":
                raise OSError("modeled spawn failure")
            return Mock(returncode=0)
        with self.assertRaises(OSError):
            self.execute(run=failed)
        self.assertEqual("--stop", calls[-1][-1])
        self.reports.assert_called_once()
        self.assertFalse(self.output.exists())

    def test_immutable_controller_changes_block_output(self):
        def changed(argv, **kwargs):
            result = self.generator(argv, **kwargs)
            (self.controller / "product.txt").write_text("changed controller")
            return result
        with self.assertRaisesRegex(D.UpdateError, "SOURCE_DIRTY"):
            self.execute(run=changed)
        self.assertFalse(self.output.exists())

    def test_existing_internal_and_linked_outputs_refuse_before_execution(self):
        existing = self.parent / "existing"
        existing.mkdir()
        linked = self.parent / "link"
        linked.symlink_to(self.controller, target_is_directory=True)
        for output in (existing, self.controller / "output", self.candidate / "output", linked / "output"):
            with self.subTest(output=output), self.assertRaises(D.UpdateError):
                D.execute(self.controller, self.candidate, self.request, output, run=self.generator)
        self.assertFalse(self.calls)

    def test_xml_dtd_duplicate_and_weak_checksums_refuse(self):
        for raw in (b'<!DOCTYPE verification-metadata []>' + xml(), xml().replace(b"sha256", b"sha1"),
                    xml().replace(b'</components>', xml().split(b'<components>')[1].split(b'</components>')[0] + b'</components>')):
            with self.subTest(raw=raw[:20]), self.assertRaises(D.UpdateError):
                D.verification(raw)


class WorkflowRetentionTests(unittest.TestCase):
    def test_plugin_provenance_tracks_active_catalog_not_historical_versions(self):
        root = Path(__file__).resolve().parents[2]
        version = re.findall(r'^cyclonedx = "([^"]+)"$',
                             (root / "gradle/libs.versions.toml").read_text(), re.MULTILINE)
        self.assertEqual(len(version), 1)
        policies = [line.split("|") for line in (root / "gradle/plugin-provenance-policy.txt").read_text().splitlines()
                    if line.startswith("org.cyclonedx|cyclonedx-gradle-plugin|")]
        self.assertEqual([row[2] for row in policies], version)

    def test_submission_plugin_is_resolved_by_writer_without_applying_or_submitting(self):
        root = Path(__file__).resolve().parents[2]
        helper = "gradle/dependency-submission-verification.init.gradle"
        self.assertIn(helper, D.HELPERS)
        source = "\n".join(line for line in (root / helper).read_text().splitlines()
                           if not line.lstrip().startswith("//"))
        self.assertEqual(re.findall(r"classpath '([^']+)'", source),
                         ["org.gradle:github-dependency-graph-gradle-plugin:1.5.0"])
        self.assertIn("mavenCentral()", source)
        self.assertIn("gradlePluginPortal", source)
        self.assertIn("includeModule('org.gradle', 'github-dependency-graph-gradle-plugin')", source)
        self.assertNotRegex(source, r"\b(?:apply|allprojects|settingsEvaluated|System|exec)\b")
        workflow = (root / ".github/workflows/dependency-submission.yml").read_text()
        self.assertIn("gradle/actions/dependency-submission@3f5f9adaf7d9fecd50b5935e54106014257a94e6", workflow)
        self.assertIn("additional-arguments: --dependency-verification strict", workflow)

    def test_failed_generation_retains_only_explicit_safe_evidence_files(self):
        workflow = (Path(__file__).resolve().parents[2] /
                    ".github/workflows/dependency-update-candidate.yml").read_text()

        def check(source):
            blocks = [block for block in source.split("      - name: ")
                      if block.startswith("Retain encrypted diagnostics including failed generation\n")]
            self.assertEqual(len(blocks), 1)
            block = blocks[0]
            self.assertIn("        if: ${{ always() && steps.generate.outcome != 'skipped' }}\n", block)
            self.assertIn("        uses: actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9\n", block)
            paths = re.findall(r"^          path: \|\n((?:            [^\n]+\n)+)", block, re.MULTILINE)
            self.assertEqual(len(paths), 1)
            self.assertEqual(paths[0].splitlines(), [
                "            ${{ runner.temp }}/dependency-evidence/" + name
                for name in ("manifest.json", "evidence.tar.gz.gpg", "failure.json")])
            for setting in ("if-no-files-found: error", "retention-days: 14", "overwrite: false"):
                self.assertIn("          " + setting + "\n", block)

        check(workflow)
        fallback = "            ${{ runner.temp }}/dependency-evidence/failure.json\n"
        for changed in (workflow.replace(fallback, ""),
                        workflow.replace(fallback, fallback.replace("failure.json", "*")),
                        workflow.replace(fallback, fallback.replace("failure.json", "stderr.log")),
                        workflow.replace("always() && steps.generate.outcome != 'skipped'", "success()")):
            with self.subTest(mutation=changed != workflow), self.assertRaises(AssertionError):
                check(changed)


class DependencyCIPolicyTests(unittest.TestCase):
    """Actual modular component model; subprocesses/Gradle/tool probes mocked."""

    def setUp(self):
        path = Path(__file__).resolve().parents[1] / "ci_component.py"
        spec = importlib.util.spec_from_file_location("dependency_ci_component", path)
        self.component = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.component)

    def expected(self):
        c = self.component
        return [
            ("integrity-policy", ["bash", "scripts/check-dependency-verification.sh"]),
            ("lock-coverage", ["bash", "scripts/tests/check-osv-lockfile-coverage.sh"]),
            ("lock-writer-policy", ["bash", "scripts/tests/check-lock-write-policy-test.sh"]),
            *[(name, [sys.executable, "-B", "scripts/tests/" + name, "-v"])
              for name in ("check-freemarker-floor-test.py", "check-jackson-floor-test.py", "check-guava-floor-test.py")],
            ("build-plugin-floors", [str(c.ROOT / "gradlew.bat") if os.name == "nt" else "./gradlew",
                "--no-daemon", "--no-build-cache", "--no-configuration-cache",
                "--dependency-verification", "strict", "--max-workers=2", "--no-parallel", "--console=plain",
                ":verifyBuildPluginSecurityFloors", ":checkPublicConstantAbiPolicy"]),
        ]

    def test_required_modular_integrity_lock_and_strict_floor_commands(self):
        c = self.component
        self.assertEqual(c.commands("dependencies"), self.expected())
        self.assertIn("dependencies", [row["component"] for row in c.matrix("all")["include"]])
        source = dict(c.commands("source"))
        self.assertEqual(source["dependency-update-test.py"],
                         [sys.executable, "-B", "scripts/tests/dependency-update-test.py", "-v"])
        self.assertEqual(source["workflow-contract"], ["ruby", "scripts/check-modular-ci-policy.rb"])

    def test_missing_reordered_or_lenient_dependency_commands_are_not_equivalent(self):
        actual = self.component.commands("dependencies")
        lenient = copy.deepcopy(actual)
        lenient[-1][1][lenient[-1][1].index("strict")] = "lenient"
        for changed in (actual[1:], [*actual[1:], actual[0]], lenient):
            with self.subTest(changed=changed), self.assertRaises(AssertionError):
                self.assertEqual(changed, self.expected())

    def test_actual_component_preserves_first_failure_and_bounded_stop(self):
        c = self.component
        for failed in (None, *range(len(self.expected()))):
            for stop_code in (0, 9):
                with self.subTest(failed=failed, stop_code=stop_code), tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    with patch.object(c, "ROOT", root), patch.object(c, "record_tools"), \
                            patch.object(c.subprocess, "run") as run:
                        commands = self.expected()
                        count = len(commands) if failed is None else failed + 1
                        failure_code = 0 if failed is None else 37 + failed
                        codes = [0] * count
                        if failed is not None:
                            codes[-1] = failure_code
                        run.side_effect = [Mock(returncode=code) for code in (*codes, stop_code)]
                        code = c.execute("dependencies")
                    expected_code = failure_code or stop_code
                    self.assertEqual(code, expected_code)  # Failure must never become PASS.
                    stop = [str(root / "gradlew.bat") if os.name == "nt" else "./gradlew", "--stop"]
                    self.assertEqual([call.args[0] for call in run.call_args_list],
                                     [argv for _, argv in commands[:count]] + [stop])
                    self.assertEqual(run.call_args.kwargs, {"cwd": root, "check": False, "timeout": 90})
                    report = json.loads((root / "build/reports/ci-component/dependencies.json").read_text())
                    self.assertEqual(report["exitCode"], expected_code)
                    self.assertEqual(report["tasks"], [
                        {"task": name, "exitCode": value}
                        for (name, _), value in zip(commands[:count], codes)
                    ] + [{"task": "gradle-stop", "exitCode": stop_code}])


class GeneratorPhaseTests(unittest.TestCase):
    def test_actual_generator_phase_order_arguments_and_first_failure_are_preserved(self):
        maintained = Path(__file__).resolve().parents[1] / "prepare-dependency-update.sh"
        with tempfile.TemporaryDirectory(prefix="generator-phase-model-") as temporary:
            root = Path(temporary)
            (root / "scripts").mkdir()
            (root / "bin").mkdir()
            script = root / "scripts/prepare-dependency-update.sh"
            script.write_bytes(maintained.read_bytes())
            expected = [
                ("WRAPPER", ["scripts/check-gradle-wrapper.sh"]),
                ("GENERATE", ["./gradlew", "resolveAndLockAll", "--write-locks", "--write-verification-metadata",
                              "sha256", "--continue", "--no-configure-on-demand", "--no-daemon",
                              "--max-workers=2", "--no-parallel", "--console=plain",
                              "--init-script", "gradle/dependency-submission-verification.init.gradle"]),
                ("INTEGRITY", ["scripts/check-dependency-verification.sh"]),
                ("STRICT", ["./gradlew", "verifyBuildPluginSecurityFloors", "help",
                            "--dependency-verification=strict", "--no-daemon", "--console=plain"]),
                ("PROVENANCE", ["scripts/review-dependency-verification.sh", "synthetic-base"]),
                ("DIFF", ["git", "diff", "--check"]),
            ]
            fake = ("#!" + sys.executable + "\n" +
                    "import json,os,pathlib,sys\n"
                    "name=pathlib.Path(sys.argv[0]).name\n"
                    "phase={'check-gradle-wrapper.sh':'WRAPPER','check-dependency-verification.sh':'INTEGRITY',"
                    "'review-dependency-verification.sh':'PROVENANCE','git':'DIFF'}.get(name)\n"
                    "if name=='gradlew': phase='GENERATE' if sys.argv[1]=='resolveAndLockAll' else 'STRICT'\n"
                    "if name=='python3': phase='GENERATE'\n"
                    "with open(os.environ['TRACE'],'a') as stream: stream.write(json.dumps([phase,sys.argv[1:],"
                    "os.environ.get('P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED')])+'\\n')\n"
                    "sys.exit(int(os.environ['FAIL_CODE']) if phase==os.environ.get('FAIL_PHASE') else 0)\n")
            for name in ("scripts/check-gradle-wrapper.sh", "scripts/check-dependency-verification.sh",
                         "scripts/review-dependency-verification.sh", "gradlew", "bin/git", "bin/python3"):
                path = root / name
                path.write_text(fake); path.chmod(0o755)
            trace = root / "trace"
            for terminal, failed in ((terminal, failed) for terminal in (False, True) for failed in (None, *range(len(expected)))):
                current = list(expected)
                if terminal:
                    current[1] = ("GENERATE", ["python3", "-B", "scripts/run-ci-terminal-component.py", "--component", "dependency-generate"])
                trace.write_text("")
                count = len(expected) if failed is None else failed + 1
                code = 0 if failed is None else 37 + failed
                environment = {**os.environ, "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
                               "TRACE": str(trace), "FAIL_PHASE": "" if failed is None else expected[failed][0],
                               "FAIL_CODE": str(code), "P2PKIT_DEPENDENCY_TERMINAL_GENERATE": "1" if terminal else ""}
                environment.pop("P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED", None)
                result = subprocess.run(["bash", str(script), "synthetic-base"], env=environment,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
                with self.subTest(terminal=terminal, failed=failed):
                    self.assertEqual(result.returncode, code)
                    self.assertEqual([json.loads(line) for line in trace.read_text().splitlines()],
                                     [[phase, argv[1:], "1" if phase == "PROVENANCE" else None]
                                      for phase, argv in current[:count]])
                    self.assertEqual(result.stderr.decode().splitlines(),
                                     [f"DEPENDENCY_GENERATOR_PHASE {phase} EXIT {code if i == failed else 0}"
                                      for i, (phase, _) in enumerate(current[:count])])
                    self.assertEqual(b"RESULT: PASS" in result.stdout, failed is None)


class AndroidAbiReportTests(unittest.TestCase):
    """Actual bounded copying/inventory of tiny files; no Gradle, keys or network."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dependency-abi-reports-")
        self.addCleanup(self.temporary.cleanup)
        self.parent = Path(self.temporary.name)
        # Load the real collector; each controller below is an isolated data fixture.
        with patch.object(sys, "path", [str(Path(__file__).resolve().parents[1]), *sys.path]):
            import ci_evidence
        self.evidence = ci_evidence
        self.expected = {
            f"library/{module}/build/kotlin/{directory}/{module}.api":
            f"synthetic {module} {directory}\n".encode()
            for module in ("p2p-core", "p2p-transport-lan", "p2p-rpc", "p2p-network-provisioning-android")
            for directory in ("abi/android", "androidAbi")
        }

    def fixture(self, name):
        candidate, controller = (self.parent / name / role for role in ("candidate", "controller"))
        for relative, raw in self.expected.items():
            path = candidate / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        controller.mkdir(parents=True)
        return candidate, controller

    def retain(self, candidate, controller):
        with patch.object(sys, "path", list(sys.path)):
            D.retain_reports(candidate, controller)
        return controller / "build/reports/dependency-update"

    def test_exact_four_builtin_and_four_custom_originals_are_inventoried_without_extra_files(self):
        candidate, controller = self.fixture("complete")
        for relative in (
            "library/p2p-core/build/kotlin/abi/android/unrelated.api",
            "library/p2p-core/build/kotlin/abi/jvm/p2p-core.api",
            "library/p2p-core/build/kotlin/androidAbi/unrelated.class",
            "library/p2p-core/api/android/p2p-core.api",
            "library/unrelated/build/kotlin/abi/android/unrelated.api",
            "private.txt",
        ):
            path = candidate / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"not a selected Android ABI original\n")
        destination = self.retain(candidate, controller)
        self.assertEqual({p.relative_to(destination).as_posix(): p.read_bytes()
                          for p in destination.rglob("*") if p.is_file()}, self.expected)
        inventory = self.evidence.archive_private(destination, self.parent / "synthetic.tar.gz")
        self.assertEqual(inventory, [
            {"path": path, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for path, raw in sorted(self.expected.items())
        ])
        self.assertEqual(len(inventory), 8)

    def test_missing_original_is_absent_not_fabricated(self):
        candidate, controller = self.fixture("missing")
        absent = next(iter(self.expected))
        (candidate / absent).unlink()
        destination = self.retain(candidate, controller)
        inventory = self.evidence.archive_private(destination, self.parent / "synthetic.tar.gz")
        self.assertEqual({row["path"] for row in inventory}, set(self.expected) - {absent})

    def test_original_collection_preserves_finite_count_bytes_and_link_refusal(self):
        for kind in ("count", "bytes", "symlink", "parent-link", "hardlink"):
            with self.subTest(kind=kind):
                candidate, controller = self.fixture(kind)
                path = candidate / next(iter(self.expected))
                if kind in ("symlink", "hardlink"):
                    outside = self.parent / (kind + "-outside")
                    outside.write_bytes(b"unselected fixture\n")
                    path.unlink()
                    if kind == "symlink":
                        path.symlink_to(outside)
                    else:
                        os.link(outside, path)
                elif kind == "parent-link":
                    outside = path.parent.with_name("other-directory")
                    path.parent.rename(outside)
                    path.parent.symlink_to(outside, target_is_directory=True)
                limits = ({"MAX_REPORTS": 7} if kind == "count" else
                          {"MAX_BUNDLE_BYTES": sum(map(len, self.expected.values())) - 1} if kind == "bytes" else {})
                with patch.multiple(self.evidence, **limits) if limits else contextlib.nullcontext():
                    with self.assertRaisesRegex(self.evidence.EvidenceError, "REPORTS"):
                        self.retain(candidate, controller)


class UnchangedCuratorTests(unittest.TestCase):
    """Actual shell orchestration; Gradle/checker/tools are explicit offline models."""
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dependency-noop-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for name in ("scripts", "gradle", "bin", "work", "home"):
            (self.root / name).mkdir()
        maintained = Path(__file__).resolve().parents[1]
        for name in ("prepare-dependency-update.sh", "review-dependency-verification.sh"):
            self.write("scripts/" + name, (maintained / name).read_text())
        self.write("scripts/check-gradle-wrapper.sh", '#!/bin/sh\necho wrapper >> "$TRACE"\n')
        self.write("scripts/check-dependency-verification.sh",
                   '#!/bin/sh\necho policy >> "$TRACE"\n[ "${FAIL_STAGE:-}" != policy ]\n')
        self.write("gradlew", '''#!/bin/sh
case " $* " in
  *" --write-locks "*) echo writer >> "$TRACE"; [ "${FAIL_STAGE:-}" != writer ] || exit 6 ;;
  *) echo strict-floors >> "$TRACE"; [ "${FAIL_STAGE:-}" != strict ] || exit 7 ;;
esac
''')
        for name in ("curl", "gh", "gpg"):
            self.write("bin/" + name, '#!/bin/sh\necho ' + name + ' >> "$TRACE"\nexit 97\n')
        self.write("bin/gpgconf", '#!/bin/sh\necho cleanup >> "$TRACE"\nexit 0\n')
        self.metadata = self.root / D.XML
        self.original = xml().replace(b'><', b'>\n<') + b'\n'
        self.metadata.write_bytes(self.original)
        (self.root / "gradle/plugin-provenance-policy.txt").write_text("# No exceptions\n")
        self.trace = self.root / "trace"
        self.environment = {**os.environ, "PATH": str(self.root / "bin") + os.pathsep + os.environ["PATH"],
                            "HOME": str(self.root / "home"), "GIT_CONFIG_NOSYSTEM": "1",
                            "GIT_CONFIG_GLOBAL": os.devnull, "P2PKIT_PYTHON3": sys.executable,
                            "P2PKIT_GPG_TMPDIR": str(self.root / "work"), "TMPDIR": str(self.root / "work"),
                            "TRACE": str(self.trace)}
        for name in ("P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED", "P2PKIT_DEPENDENCY_TERMINAL_GENERATE", "FAIL_STAGE"):
            self.environment.pop(name, None)
        self.git("init", "--quiet")
        self.git("add", "scripts", "gradlew", "gradle")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic baseline")
        self.base = self.git("rev-parse", "HEAD").decode().strip()

    def write(self, name, text):
        path = self.root / name
        path.write_text(text)
        path.chmod(0o755)

    def git(self, *arguments):
        return subprocess.check_output(["git", "-C", str(self.root), *arguments],
                                       env=self.environment, stderr=subprocess.PIPE)

    def invoke(self, flag=None, *, generator=False, fail=None):
        self.trace.write_text("")
        environment = dict(self.environment)
        if flag is not None:
            environment["P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED"] = flag
        if fail:
            environment["FAIL_STAGE"] = fail
        script = "prepare-dependency-update.sh" if generator else "review-dependency-verification.sh"
        result = subprocess.run([str(self.root / "scripts" / script), self.base], cwd=self.root,
                                env=environment, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
        events = self.trace.read_text().splitlines()
        self.assertNotIn("gh", events)
        self.assertNotIn("gpg", events)
        return result, events

    def test_default_and_invalid_opt_in_still_refuse_no_additions(self):
        for flag in (None, "0", "", "true", "2"):
            with self.subTest(flag=flag):
                result, events = self.invoke(flag)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"RESULT: PASS", result.stdout)
                self.assertNotIn("curl", events)

    def test_actual_generator_orders_all_checks_before_exact_noop(self):
        result, events = self.invoke("1", generator=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(events, ["wrapper", "writer", "policy", "strict-floors", "cleanup"])
        self.assertIn(b"byte-identical", result.stdout)
        self.assertEqual(self.metadata.read_bytes(), self.original)
        for stage in ("policy", "strict"):
            with self.subTest(stage=stage):
                result, events = self.invoke("1", generator=True, fail=stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"byte-identical", result.stdout)
                self.assertNotIn("cleanup", events)  # Curator was never reached.

    def test_direct_preparer_accepts_lock_only_refresh_without_ambient_opt_in(self):
        lock = self.root / "gradle.lockfile"
        lock.write_text("org.example:old:1=runtimeClasspath\n")
        self.git("add", "gradle.lockfile")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic accepted lock")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        writer = self.root / "gradlew"
        writer.write_text(writer.read_text().replace('echo writer >> "$TRACE";',
            'echo writer >> "$TRACE"; printf "org.example:old:1=otherClasspath\\n" > gradle.lockfile;'))
        result, events = self.invoke(generator=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(events, ["wrapper", "writer", "policy", "strict-floors", "cleanup"])
        self.assertEqual(lock.read_text(), "org.example:old:1=otherClasspath\n")
        self.assertEqual(self.metadata.read_bytes(), self.original)
        self.assertIn(b"byte-identical", result.stdout)
        self.assertNotIn("P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED", self.environment)

    def test_direct_preparer_retains_explicit_refusal_and_all_earlier_failures(self):
        for flag in ("0", "", "true", "2"):
            with self.subTest(flag=flag):
                result, events = self.invoke(flag, generator=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"RESULT: PASS", result.stdout)
                self.assertNotIn("curl", events)
        for stage, code in (("writer", 6), ("policy", 1), ("strict", 7)):
            with self.subTest(stage=stage):
                result, events = self.invoke(generator=True, fail=stage)
                self.assertEqual(result.returncode, code)
                self.assertNotIn(b"RESULT: PASS", result.stdout)
                self.assertNotIn("cleanup", events)

    def test_unchanged_review_refuses_changed_or_missing_original_provenance_policy(self):
        policy = self.root / "gradle/plugin-provenance-policy.txt"
        policy.write_text("# Changed trust policy must be reviewed, even with identical XML\n")
        for generator in (False, True):
            with self.subTest(generator=generator):
                result, events = self.invoke("1" if not generator else None, generator=generator)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"RESULT: PASS", result.stdout)
                self.assertNotIn("curl", events)
        policy.write_text("# No exceptions\n")
        self.git("rm", "--cached", "gradle/plugin-provenance-policy.txt")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic missing base policy")
        self.base = self.git("rev-parse", "HEAD").decode().strip()
        result, events = self.invoke(generator=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b"RESULT: PASS", result.stdout)
        self.assertNotIn("curl", events)

    def test_direct_preparer_refuses_invalid_base_metadata_and_routes_new_artifacts_to_curator(self):
        original_base = self.base
        for base in ("missing-base", "0" * 40):
            self.base = base
            result, events = self.invoke(generator=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn(b"RESULT: PASS", result.stdout)
            self.assertNotIn("curl", events)
        self.base = original_base
        for raw in (self.original + b"\n", self.original.replace(b'true', b'false'),
                    self.original.replace(b'a' * 64, b'b' * 64), b'<verification-metadata/>\n'):
            with self.subTest(raw=raw[:30]):
                self.metadata.write_bytes(raw)
                result, events = self.invoke(generator=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"RESULT: PASS", result.stdout)
        self.metadata.unlink()
        result, events = self.invoke(generator=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(b"RESULT: PASS", result.stdout)
        self.metadata.write_bytes(xml(True).replace(b'><', b'>\n<') + b'\n')
        result, events = self.invoke(generator=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("curl", events)  # Real curator reaches deliberately refused fake transport.
        self.assertNotIn(b"byte-identical", result.stdout)

    def test_noop_requires_entire_xml_and_additions_still_require_remote_review(self):
        for raw in (self.original + b"\n", self.original.replace(b'true', b'false'),
                    self.original.replace(b'<sha256 value=', b'<sha256 reason="changed" value='),
                    b'<verification-metadata/>\n'):
            with self.subTest(raw=raw[:30]):
                self.metadata.write_bytes(raw)
                result, events = self.invoke("1")
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn(b"byte-identical", result.stdout)
                self.assertNotIn("curl", events)
        self.metadata.write_bytes(xml(True).replace(b'><', b'>\n<') + b'\n')
        result, events = self.invoke("1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("curl", events)  # Deliberately refused fixture transport, no network.
        self.assertNotIn(b"byte-identical", result.stdout)


if __name__ == "__main__":
    unittest.main(failfast=True)
