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
    def test_failed_generation_retains_only_explicit_safe_evidence_files(self):
        workflow = (Path(__file__).resolve().parents[2] /
                    ".github/workflows/dependency-update-candidate.yml").read_text()

        def check(source):
            blocks = [block for block in source.split("      - name: ")
                      if block.startswith("Retain encrypted diagnostics including failed generation\n")]
            self.assertEqual(len(blocks), 1)
            block = blocks[0]
            self.assertIn("        if: ${{ always() && steps.generate.outcome != 'skipped' }}\n", block)
            self.assertIn("        uses: actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a\n", block)
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
                              "sha256", "--continue", "--no-configure-on-demand", "--no-daemon", "--console=plain"]),
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
                    "with open(os.environ['TRACE'],'a') as stream: stream.write(json.dumps([phase,sys.argv[1:]])+'\\n')\n"
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
                result = subprocess.run(["bash", str(script), "synthetic-base"], env=environment,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
                with self.subTest(terminal=terminal, failed=failed):
                    self.assertEqual(result.returncode, code)
                    self.assertEqual([json.loads(line) for line in trace.read_text().splitlines()],
                                     [[phase, argv[1:]] for phase, argv in current[:count]])
                    self.assertEqual(result.stderr.decode().splitlines(),
                                     [f"DEPENDENCY_GENERATOR_PHASE {phase} EXIT {code if i == failed else 0}"
                                      for i, (phase, _) in enumerate(current[:count])])
                    self.assertEqual(b"RESULT: PASS" in result.stdout, failed is None)


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
  *" --write-locks "*) echo writer >> "$TRACE" ;;
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
        for name in ("P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED", "FAIL_STAGE"):
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
