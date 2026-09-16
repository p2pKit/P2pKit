#!/usr/bin/env python3
"""Offline/synthetic submission controls; never starts Java, Gradle, SDK or native ownership."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("dependency_prerequisites",
    Path(__file__).resolve().parents[1] / "dependency-submission-prerequisites.py")
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)
SHA, TREE = "a" * 40, "b" * 40
ENV = {
    "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "RUNNER_ENVIRONMENT": "github-hosted",
    "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64", "GITHUB_SHA": SHA, "GITHUB_REF": "refs/heads/work/test",
    "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
    "GITHUB_WORKFLOW": "Dependency submission", "GITHUB_JOB": "submit", "GITHUB_WORKFLOW_SHA": SHA,
    "GITHUB_WORKFLOW_REF": app.WORKFLOW + "refs/heads/work/test",
}
EXPECTED = ["org.jetbrains.kotlin:kotlin-stdlib:2.4.10", "org.jetbrains.kotlinx:kotlinx-coroutines-core-jvm:1.11.0",
            "org.slf4j:slf4j-api:2.0.7"]


def graph(location="settings.gradle.kts", suffix=""):
    return {"version": 0, "sha": SHA, "ref": ENV["GITHUB_REF"],
        "job": {"id": "123", "correlator": "dependency_submission-submit" + suffix},
        "manifests": {"p2pkit": {"name": "p2pkit", "file": {"source_location": location},
            "resolved": {coordinate: {"package_url": "pkg:maven/" + coordinate.replace(":", "/", 1).replace(":", "@")}
                         for coordinate in EXPECTED}}}}


def graph_file(value=None):
    value = graph() if value is None else value
    return value["job"]["correlator"] + ".json", json.dumps(value).encode()


class PureContracts(unittest.TestCase):
    def test_current_lock_representatives_bind_real_source_without_running_gradle(self):
        self.assertEqual(app.expected_components(Path(__file__).resolve().parents[2]), EXPECTED)

    def test_strict_owned_properties_override_project_parallelism_without_cli_override(self):
        raw = app.properties(["/native/jdk17", "/native/jdk21"])
        for line in (
            "org.gradle.workers.max=2", "org.gradle.parallel=false", "org.gradle.caching=false",
            "org.gradle.configuration-cache=false", "org.gradle.daemon=false",
            "kotlin.compiler.execution.strategy=in-process", "org.gradle.java.installations.auto-download=false",
            "org.gradle.java.installations.auto-detect=false", "org.gradle.java.installations.paths=/native/jdk17,/native/jdk21",
            "org.gradle.jvmargs=-Xmx2g -XX:MaxMetaspaceSize=768m -XX:+UseParallelGC -Dfile.encoding=UTF-8",
        ):
            self.assertIn(line.encode() + b"\n", raw)
        self.assertNotIn(b"dependency.verification=off", raw)

    def test_invalid_java_paths_cannot_inject_gradle_properties(self):
        for paths in (["/17", "/17"], ["relative", "/21"], ["/17\norg.gradle.parallel=true", "/21"],
                      ["/17,other", "/21"], ["/17\\escape", "/21"], ["/17=other", "/21"], ["/17"]):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                app.properties(paths)

    def test_ambient_policy_graph_identity_and_filters_fail_closed(self):
        names = ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
                 "GRADLE_USER_HOME", "GRADLE_HOME", "KONAN_DATA_DIR", "ORG_GRADLE_PROJECT_org.gradle.parallel",
                 "GITHUB_DEPENDENCY_GRAPH_SHA", "GITHUB_DEPENDENCY_GRAPH_JOB_ID", "GITHUB_DEPENDENCY_GRAPH_ENABLED",
                 "DEPENDENCY_GRAPH_REPORT_DIR", "DEPENDENCY_GRAPH_INCLUDE_PROJECTS", "DEPENDENCY_GRAPH_RUNTIME_EXCLUDE_PROJECTS",
                 "DEPENDENCY_GRAPH_PLUGIN_VERSION", "GRADLE_PLUGIN_REPOSITORY_URL", "GRADLE_BUILD_ACTION_SETUP_COMPLETED",
                 "GRADLE_ACTION_ID", "INPUT_ADDITIONAL-ARGUMENTS", "BASH_ENV", "P2PKIT_AUDIT_JOB_ID")
        for name in names:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, "override"):
                app.reject_overrides({name: "override"})
        for name in ("GITHUB_DEPENDENCY_GRAPH_SHA", "DEPENDENCY_GRAPH_INCLUDE_CONFIGURATIONS", "INPUT_GITHUB-TOKEN"):
            with self.subTest(empty=name), self.assertRaises(ValueError):
                app.reject_overrides({name: ""})

    def test_act_presence_rejected_even_if_empty_and_unrelated_environment_not_dumped(self):
        for value in ("", "false", "true"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                app.reject_overrides({"ACT": value})
        app.reject_overrides({"JAVA_OPTS": "", "JAVA_HOME": "/toolcache/java", "UNRELATED_TOKEN": "not-inspected"})

    def test_original_hosted_identity_no_pr_or_synthetic_aliases(self):
        binding = app.hosted_identity(ENV)
        self.assertEqual(binding["correlator"], "dependency_submission-submit")
        self.assertEqual(binding["runAttempt"], "2")
        for key, bad in (("GITHUB_REPOSITORY", "elsewhere/repo"), ("RUNNER_OS", "Linux"), ("RUNNER_ARCH", "ARM"),
                         ("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_ACTIONS", "false"),
                         ("GITHUB_EVENT_NAME", "pull_request"), ("GITHUB_JOB", "other"),
                         ("GITHUB_WORKFLOW_SHA", TREE), ("GITHUB_WORKFLOW", "other"),
                         ("GITHUB_WORKFLOW_REF", app.WORKFLOW + "refs/heads/main"),
                         ("GITHUB_SHA", "short"), ("GITHUB_REF", "refs/tags/test"), ("GITHUB_RUN_ATTEMPT", "0")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                app.hosted_identity({**ENV, key: bad})

    def test_push_requires_main_and_real_workflow_identity(self):
        env = {**ENV, "GITHUB_EVENT_NAME": "push"}
        with self.assertRaises(ValueError):
            app.hosted_identity(env)
        env.update(GITHUB_REF="refs/heads/main", GITHUB_WORKFLOW_REF=app.WORKFLOW + "refs/heads/main")
        app.hosted_identity(env)

    def test_nonempty_graph_identity_and_current_components(self):
        result = app.inspect_graphs([graph_file()], app.hosted_identity(ENV), EXPECTED)
        self.assertEqual(result["distinctCoordinates"], 3)
        self.assertEqual(result["graphs"][0]["sha256"], app.digest(graph_file()[1]))

    def test_root_manifest_not_one_manifest_per_project_and_extra_graph_allowed(self):
        root, buildsrc = graph(), graph("buildSrc/build.gradle.kts", "-1")
        result = app.inspect_graphs([graph_file(root), graph_file(buildsrc)], app.hosted_identity(ENV), EXPECTED)
        self.assertEqual(len(result["graphs"]), 2)
        with self.assertRaisesRegex(ValueError, "root settings"):
            app.inspect_graphs([graph_file(buildsrc)], app.hosted_identity(ENV), EXPECTED)

    def test_empty_missing_wrong_source_ref_run_and_correlator_rejected(self):
        binding = app.hosted_identity(ENV)
        for files in ([], [graph_file()] * 101):
            with self.subTest(size=len(files)), self.assertRaises(ValueError):
                app.inspect_graphs(files, binding, EXPECTED)
        for section, key, bad in ((None, "sha", TREE), (None, "ref", "refs/heads/main"),
                                  ("job", "id", "124"), ("job", "id", 123),
                                  ("job", "correlator", "other"), ("job", "correlator", "dependency_submission-submit-100"),
                                  (None, "manifests", {})):
            value = graph()
            (value if section is None else value[section])[key] = bad
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                app.inspect_graphs([graph_file(value)], binding, EXPECTED)
        with self.assertRaises(ValueError):
            app.inspect_graphs([("wrong.json", graph_file()[1])], binding, EXPECTED)

    def test_duplicate_json_and_duplicate_correlators_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            app.parse(b'{"sha": "first", "sha": "second"}')
        with self.assertRaises(ValueError):
            app.inspect_graphs([graph_file(), graph_file()], app.hosted_identity(ENV), EXPECTED)

    def test_stale_external_jmdns_and_encoded_namespace_rejected(self):
        for purl in ("pkg:maven/org.jmdns/jmdns@3.6.3", "pkg:maven/org%2Ejmdns/jmdns@3.6.3"):
            value = graph()
            value["manifests"]["p2pkit"]["resolved"]["old"] = {"package_url": purl}
            with self.subTest(purl=purl), self.assertRaisesRegex(ValueError, "stale external"):
                app.inspect_graphs([graph_file(value)], app.hosted_identity(ENV), EXPECTED)

    def test_missing_representative_empty_or_unsafe_manifest_rejected(self):
        for mutate in (lambda m: m.update(resolved={}), lambda m: m.update(file=None),
                       lambda m: m["file"].update(source_location="../settings.gradle.kts"),
                       lambda m: m["file"].update(source_location="/settings.gradle.kts"),
                       lambda m: m["resolved"].pop(EXPECTED[0])):
            value = graph()
            mutate(value["manifests"]["p2pkit"])
            with self.assertRaises(ValueError):
                app.inspect_graphs([graph_file(value)], app.hosted_identity(ENV), EXPECTED)


class FilesystemModels(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-dependency-model-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root, self.sdk = self.base / "source", self.base / "sdk"
        self.root.mkdir(); self.sdk.mkdir()
        self.env = {**ENV, "ANDROID_HOME": str(self.sdk), "ANDROID_SDK_ROOT": str(self.sdk),
                    "RUNNER_TEMP": str(self.base)}

    def platform(self, folder, level):
        directory = self.sdk / "platforms" / folder
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "source.properties").write_text("AndroidVersion.ApiLevel=" + level + "\n")

    def test_missing_platform_plan_is_empty_without_sdkmanager_when_both_present(self):
        self.assertEqual(app.missing_platforms(self.sdk), ["platforms;android-36", "platforms;android-37.0"])
        self.platform("android-36", "36")
        self.assertEqual(app.missing_platforms(self.sdk), ["platforms;android-37.0"])
        self.platform("android-37.0", "37.0")
        self.assertEqual(app.missing_platforms(self.sdk), [])

    def test_existing_wrong_literal_missing_metadata_and_duplicates_fail_before_install(self):
        for raw in ("AndroidVersion.ApiLevel=37\n", "AndroidVersion.ApiLevel=37.0\nAndroidVersion.ApiLevel=37.0\n",
                    "AndroidVersion.ApiLevel =37.0\n", "AndroidVersion.ApiLevel=37.0 \n"):
            self.platform("android-37.0", "37.0")
            (self.sdk / "platforms/android-37.0/source.properties").write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                app.missing_platforms(self.sdk)
        (self.sdk / "platforms/android-37.0/source.properties").unlink()
        with self.assertRaises(OSError):
            app.missing_platforms(self.sdk)

    def test_sdk_alias_and_local_configuration_must_agree(self):
        self.assertEqual(app.sdk_directory(self.env, self.root), self.sdk)
        with self.assertRaises(ValueError):
            app.sdk_directory({**self.env, "ANDROID_SDK_ROOT": str(self.root)}, self.root)
        local = self.root / "local.properties"
        local.write_text("# SDK fixture\nsdk.dir=" + str(self.sdk) + "\n")
        self.assertEqual(app.sdk_directory(self.env, self.root), self.sdk)
        for raw in ("sdk.dir=" + str(self.root), "sdk.dir=" + str(self.sdk) + "\nsdk.dir=" + str(self.sdk),
                    "sdk\\u002edir=" + str(self.root), "sdk.dir relative", "sdk.dir=relative"):
            local.write_text(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                app.sdk_directory(self.env, self.root)

    def test_symlinks_hardlinks_and_repeated_output_not_admitted(self):
        original = self.base / "original"
        original.write_bytes(b"test")
        alias = self.base / "alias"
        alias.symlink_to(original)
        with self.assertRaises(ValueError):
            app.read(alias)
        alias.unlink(); os.link(original, alias)
        with self.assertRaises(ValueError):
            app.read(original)
        with self.assertRaises(OSError):
            app.write_new(original, b"replacement")
        self.assertEqual(original.read_bytes(), b"test")

    def test_java_real_path_and_observed_native_identity_not_merely_version_name(self):
        for major in (17, 21):
            home = self.base / ("jdk" + str(major))
            (home / "bin").mkdir(parents=True)
            for tool in ("java", "javac"):
                (home / "bin" / tool).write_text("not executed")
            self.env["JAVA_HOME_" + str(major) + "_ARM64"] = str(home)
        self.env["JAVA_HOME"] = self.env["JAVA_HOME_17_ARM64"]
        homes = app.java_homes(self.env)
        raw = "    java.specification.version = 17\n    java.home = " + homes[0] + "\n    os.arch = aarch64\n"
        app.java_settings(raw, 17, homes[0], "ARM64")
        for changed in (raw.replace("17\n", "21\n"), raw.replace("aarch64", "x86_64"),
                        raw.replace(homes[0], homes[1]), raw + "os.arch = aarch64\n"):
            with self.assertRaises(ValueError):
                app.java_settings(changed, 17, homes[0], "ARM64")
        with self.assertRaises(ValueError):
            app.java_homes({**self.env, "JAVA_HOME": homes[1]})
        for key in ("JAVA_HOME", "JAVA_HOME_17_ARM64", "JAVA_HOME_21_ARM64"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                app.java_homes({**self.env, key: ""})

    def prepare_fixture(self):
        """Synthetic source/event/tool files only; no program is executable here."""
        for path in ("gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties",
                     ".github/workflows/dependency-submission.yml", "scripts/dependency-submission-prerequisites.py",
                     "scripts/audit_processes.py", "gradle.properties", "gradle/verification-metadata.xml",
                     "gradle/libs.versions.toml", "gradle/gradle-daemon-jvm.properties"):
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("source fixture, not executed\n")
        (self.root / "settings.gradle.kts").write_text("".join('include(":project' + str(i) + '")\n' for i in range(10)))
        for directory, rows in (
            ("library/p2p-core", [EXPECTED[0] + "=jvmRuntimeClasspath", EXPECTED[1] + "=jvmRuntimeClasspath"]),
            ("library/p2p-transport-lan", [EXPECTED[2] + "=embeddedJmdnsCompileClasspath"]),
        ):
            target = self.root / directory; target.mkdir(parents=True)
            (target / "gradle.lockfile").write_text("\n".join(rows) + "\n")
        for major in (17, 21):
            home = self.base / ("jdk" + str(major)); (home / "bin").mkdir(parents=True)
            for tool in ("java", "javac"):
                (home / "bin" / tool).write_text("not executed")
            self.env["JAVA_HOME_" + str(major) + "_ARM64"] = str(home)
        self.env["JAVA_HOME"] = self.env["JAVA_HOME_17_ARM64"]
        event = self.base / "event.json"
        event.write_text(json.dumps({"repository": {"full_name": "p2pKit/P2pKit"}, "ref": "work/test", "inputs": {}}))
        self.env.update(GITHUB_WORKSPACE=str(self.root), GITHUB_EVENT_PATH=str(event),
                        GITHUB_ENV=str(self.base / "environment"), GITHUB_OUTPUT=str(self.base / "output"))
        return self.base / "p2pkit-dependency-submission-123-2"

    def mocked_prepare(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(app.sys, "platform", "darwin"))
        stack.enter_context(patch.object(app.audit_processes, "host_role", return_value="macos-arm64"))
        stack.enter_context(patch.object(app, "source_identity", return_value=TREE))
        # Not a native Java query: text is produced by the synthetic fixture.
        def java_query(argv, *_args, **_kwargs):
            self.assertEqual(argv[1:], ["-XshowSettings:properties", "-version"])
            home = str(Path(argv[0]).parents[1])
            major = 17 if home == self.env["JAVA_HOME_17_ARM64"] else 21
            return "", "java.specification.version = " + str(major) + "\njava.home = " + home + "\nos.arch = aarch64\n"
        stack.enter_context(patch.object(app, "query", side_effect=java_query))
        stack.enter_context(patch.object(app.subprocess, "run", side_effect=AssertionError("no native children permitted")))
        stack.enter_context(redirect_stdout(io.StringIO()))
        return stack

    def test_prepare_exports_only_fresh_exact_home_and_binds_source_models(self):
        state = self.prepare_fixture()
        with self.mocked_prepare():
            app.prepare(self.env, self.root)
        row = app.parse((state / "receipt/admission.json").read_bytes())
        self.assertEqual(row["binding"]["tree"], TREE)
        self.assertEqual(len(row["requiredResolverTasks"]), 11)
        self.assertEqual(row["missingPlatforms"], ["platforms;android-36", "platforms;android-37.0"])
        self.assertEqual(row["sourceInputs"]["gradlew"], app.digest((self.root / "gradlew").read_bytes()))
        self.assertEqual(row["propertiesSha256"], app.digest((state / "gradle-home/gradle.properties").read_bytes()))
        self.assertEqual(Path(self.env["GITHUB_ENV"]).read_text(), "GRADLE_USER_HOME=" + str(state / "gradle-home") + "\n")
        self.assertIn("state=" + str(state) + "\n", Path(self.env["GITHUB_OUTPUT"]).read_text())

    def test_prepare_rejects_preexisting_state_and_graph_without_reuse(self):
        state = self.prepare_fixture(); state.mkdir()
        with self.mocked_prepare(), self.assertRaisesRegex(ValueError, "fresh exclusive"):
            app.prepare(self.env, self.root)
        self.assertFalse((state / "receipt").exists())
        state.rmdir(); (self.root / app.GRAPH_DIRECTORY).mkdir()
        with self.mocked_prepare(), self.assertRaisesRegex(ValueError, "old dependency graphs"):
            app.prepare(self.env, self.root)
        self.assertFalse(state.exists())

    def test_prepare_rejects_event_mismatch_without_private_allocation(self):
        state = self.prepare_fixture()
        event = Path(self.env["GITHUB_EVENT_PATH"])
        for payload in ({"repository": {"full_name": "wrong/repo"}, "ref": "work/test", "inputs": {}},
                        {"repository": {"full_name": "p2pKit/P2pKit"}, "ref": "main", "inputs": {}},
                        {"repository": {"full_name": "p2pKit/P2pKit"}, "ref": "work/test", "inputs": {"task": "partial"}}):
            event.write_text(json.dumps(payload))
            with self.mocked_prepare(), self.assertRaises(ValueError):
                app.prepare(self.env, self.root)
            self.assertFalse(state.exists())

    def context(self):
        state = self.base / "p2pkit-dependency-submission-123-2"
        (state / "receipt").mkdir(parents=True)
        home = state / "gradle-home"; home.mkdir()
        policy = app.properties(["/jdk17", "/jdk21"])
        (home / "gradle.properties").write_bytes(policy)
        binding = {**app.hosted_identity(self.env), "tree": TREE}
        admission = {"schema": 1, "binding": binding, "sdk": str(self.sdk), "gradleHome": str(home),
                     "properties": policy.decode(), "expectedComponents": EXPECTED, "sourceInputs": {}}
        app.record(state / "receipt/admission.json", admission)
        self.env.update(P2PKIT_DEPENDENCY_STATE=str(state), GRADLE_USER_HOME=str(home),
                        P2PKIT_DEPENDENCY_ACTION_OUTCOME="success", P2PKIT_DEPENDENCY_STOP_OUTCOME="success",
                        P2PKIT_DEPENDENCY_STOP_EXIT_CODE="0")
        self.platform("android-36", "36"); self.platform("android-37.0", "37.0")
        directory = self.root / app.GRAPH_DIRECTORY; directory.mkdir()
        name, raw = graph_file(); (directory / name).write_bytes(raw)
        return state, admission

    def test_sdkmanager_not_called_for_qualified_existing_platforms(self):
        state, _ = self.context()
        with patch.object(app.subprocess, "run", side_effect=AssertionError("unexpected child/download")), redirect_stdout(io.StringIO()):
            app.install_sdk(self.env, self.root)
        receipt = app.parse((state / "receipt/sdk.json").read_bytes())
        self.assertEqual(receipt["validation"], "PASS")
        self.assertEqual(receipt["requestedMissingOnly"], [])
        self.assertIsNone(receipt["sdkManagerExitCode"])

    def test_sdkmanager_receives_only_missing_literal_package_and_no_license_override(self):
        state, _ = self.context()
        properties = self.sdk / "platforms/android-37.0/source.properties"
        properties.unlink(); properties.parent.rmdir()
        calls = []
        def install(argv, **options):
            calls.append((argv, options))
            self.platform("android-37.0", "37.0")
            return subprocess.CompletedProcess(argv, 0)
        with patch.object(app.subprocess, "run", side_effect=install), redirect_stdout(io.StringIO()):
            app.install_sdk(self.env, self.root)
        self.assertEqual(calls[0][0], [str(self.sdk / "cmdline-tools/latest/bin/sdkmanager"),
                                      "--sdk_root=" + str(self.sdk), "platforms;android-37.0"])
        self.assertEqual(calls[0][1]["stdin"], subprocess.DEVNULL)
        self.assertEqual(calls[0][1]["timeout"], 720)
        self.assertEqual(app.parse((state / "receipt/sdk.json").read_bytes())["sdkManagerExitCode"], 0)

    def test_sdk_install_failure_retains_original_code_without_accepting_partial_platform(self):
        state, _ = self.context()
        path = self.sdk / "platforms/android-37.0/source.properties"; path.unlink(); path.parent.rmdir()
        with patch.object(app.subprocess, "run", return_value=subprocess.CompletedProcess([], 7)), self.assertRaises(ValueError):
            app.install_sdk(self.env, self.root)
        receipt = app.parse((state / "receipt/sdk.json").read_bytes())
        self.assertEqual(receipt["sdkManagerExitCode"], 7)
        self.assertEqual(receipt["validation"], "FAIL")

    def test_receipt_pass_is_only_post_main_not_final_post_api_or_worker_acceptance(self):
        state, _ = self.context()
        with patch.object(app, "source_identity", return_value=TREE), redirect_stdout(io.StringIO()):
            app.verify(self.env, self.root)
        row = app.parse((state / "receipt/post-main.json").read_bytes())
        self.assertEqual(row["verification"], "PASS_POST_MAIN_SCOPE_ONLY")
        self.assertEqual(row["postActionAndApiReadback"], "POST_PENDING_EXTERNAL_READBACK")
        self.assertEqual(row["allWorkerRetirement"], "NOT_ESTABLISHED_BY_THIS_RECEIPT")
        self.assertEqual(row["fullResolverCoverage"], "NOT_INSPECTED")
        self.assertEqual(row["apiSubmission"], "NOT_INFERRED_FROM_THIS_RECEIPT")

    def test_skipped_action_is_not_reported_as_submission_attempt(self):
        state, _ = self.context()
        self.env.update(P2PKIT_DEPENDENCY_ACTION_OUTCOME="skipped", P2PKIT_DEPENDENCY_STOP_OUTCOME="skipped",
                        P2PKIT_DEPENDENCY_STOP_EXIT_CODE="")
        with patch.object(app, "source_identity", return_value=TREE), self.assertRaises(ValueError):
            app.verify(self.env, self.root)
        row = app.parse((state / "receipt/post-main.json").read_bytes())
        self.assertFalse(row["actionMainAttempted"])
        self.assertEqual(row["verification"], "FAIL")
        self.assertEqual(row["apiSubmission"], "NOT_INFERRED_FROM_THIS_RECEIPT")

    def test_pretty_graph_cannot_hide_failed_original_action(self):
        state, _ = self.context()
        self.env["P2PKIT_DEPENDENCY_ACTION_OUTCOME"] = "failure"
        with patch.object(app, "source_identity", return_value=TREE), self.assertRaises(ValueError):
            app.verify(self.env, self.root)
        row = app.parse((state / "receipt/post-main.json").read_bytes())
        self.assertEqual(row["verification"], "FAIL")
        self.assertEqual(row["actionMainOutcome"], "failure")
        self.assertEqual(len(row["graphs"]), 1)

    def test_successful_action_cannot_hide_stop_failure(self):
        state, _ = self.context()
        self.env.update(P2PKIT_DEPENDENCY_STOP_OUTCOME="failure", P2PKIT_DEPENDENCY_STOP_EXIT_CODE="9")
        with patch.object(app, "source_identity", return_value=TREE), self.assertRaises(ValueError):
            app.verify(self.env, self.root)
        row = app.parse((state / "receipt/post-main.json").read_bytes())
        self.assertEqual((row["stopOutcome"], row["stopExitCode"]), ("failure", "9"))

    def test_original_run_home_and_state_identity_fail_closed(self):
        self.context()
        for key, value in (("GRADLE_USER_HOME", str(self.base)), ("GITHUB_RUN_ATTEMPT", "3"),
                           ("GITHUB_SHA", TREE)):
            with self.subTest(key=key), self.assertRaises((ValueError, FileNotFoundError)):
                app.load_admission({**self.env, key: value})

    def test_source_change_and_resource_policy_change_are_failure_receipts(self):
        state, _ = self.context()
        with patch.object(app, "source_identity", return_value="c" * 40), self.assertRaises(ValueError):
            app.verify(self.env, self.root)
        self.assertEqual(app.parse((state / "receipt/post-main.json").read_bytes())["verification"], "FAIL")
        (state / "receipt/post-main.json").unlink()
        with (state / "gradle-home/gradle.properties").open("ab") as stream:
            stream.write(b"org.gradle.parallel=true\n")
        with patch.object(app, "source_identity", return_value=TREE), self.assertRaises(ValueError):
            app.verify(self.env, self.root)

    def test_only_documented_pinned_action_debug_prepend_can_change_owned_property_file(self):
        state, _ = self.context()
        props = state / "gradle-home/gradle.properties"
        props.write_bytes(b"org.gradle.logging.level=info\norg.gradle.logging.stacktrace=all\n\n" + props.read_bytes())
        with patch.object(app, "source_identity", return_value=TREE), redirect_stdout(io.StringIO()):
            app.verify(self.env, self.root)


if __name__ == "__main__":
    unittest.main(verbosity=2)
