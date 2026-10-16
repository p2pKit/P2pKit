#!/usr/bin/env python3
"""Own temporary witnesses and injected context facts; no real audit qualification."""
import contextlib
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rpc_apple_ci_setup as setup
from rpc_apple_ci_environment import admit_environment


class SetupControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-setup-controls-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / "source"
        self.runner = self.base / "runner"
        for path in (self.root, self.runner, self.base / "home", self.base / "jdk17", self.base / "jdk21"):
            path.mkdir()
        self.workflow = self.root / ".github/workflows/ci.yml"
        self.workflow.parent.mkdir(parents=True)
        self.workflow.write_text("fixture workflow\nuses: " + setup.ACTION + "\n")
        self.old = self.base / "actual-java-user-home" / ".gradle"
        self.old.mkdir(parents=True)
        self.env = {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_SHA": "a" * 40,
            "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_JOB": "platform-checks",
            "GITHUB_REF": "refs/pull/463/merge", "GITHUB_EVENT_NAME": "pull_request",
            "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/.github/workflows/ci.yml@refs/pull/463/merge",
            "GITHUB_WORKFLOW_SHA": "b" * 40, "GITHUB_WORKSPACE": str(self.root), "RUNNER_TEMP": str(self.runner),
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
            "HOME": str(self.base / "home"), "JAVA_HOME": str(self.base / "jdk17"),
            "P2PKIT_AUDIT_JDK21": str(self.base / "jdk21"), "RUNNER_TRACKING_ID": "fixture-tracking-only",
            "PATH": "/usr/bin:/bin", "USER": "fixture", "LOGNAME": "fixture", "TMPDIR": str(self.runner),
            "ANDROID_HOME": str(self.base / "android-sdk"), "SECRET_FIXTURE": "must-not-project",
        }

    def directory(self):
        return setup.witness_directory(setup._binding(self.env))

    def post_environment(self):
        return {**self.env, "GRADLE_USER_HOME": str(self.old), setup.MARKER: "true",
                setup.OUTCOME: "success", setup.CONCLUSION: "success"}

    def capture(self):
        setup.before(self.env)
        environment = self.post_environment()
        setup.after(environment)
        return environment

    def context_facts(self):
        """Fixture ONLY: not canonical initialize/context_at or authenticated CI."""
        state = self.base / "canonical-state"
        state.mkdir(mode=0o700)
        home = state / "gradle-home"
        home.mkdir(mode=0o700)
        policy = home / "gradle.properties"
        policy.write_bytes(b"fixture-policy-not-runtime-qualification\n")
        source = {"commit": self.env["GITHUB_SHA"], "tree": "c" * 40}
        admitted = dict.fromkeys(setup.BINDING_KEYS)
        admitted.update(schema=1, scope=setup.ADMISSION_SCOPE, repository="p2pKit/P2pKit", event="pull_request",
                        ref=self.env["GITHUB_REF"], runId=123, runAttempt=2, root=str(self.root), source=source,
                        profile=setup.PROFILES[self.env["GITHUB_JOB"]], ciScope={"full": True, "head": source["commit"]})
        context = {"schema": 1, "id": "d" * 32, "host": "macos-arm64", "root": str(self.root),
                   "gradleHome": str(home), "expectedCommit": source["commit"], "tree": source["tree"],
                   "source": {**source, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()},
                   "javaHomes": [self.env["JAVA_HOME"], self.env["P2PKIT_AUDIT_JDK21"]],
                   "gradlePropertiesSha256": hashlib.sha256(policy.read_bytes()).hexdigest()}
        return state, context, admitted

    def transition(self, environment, state, context, admitted, **changes):
        arguments = dict(admitted_context=admitted, state=str(state), context_at=Mock(return_value=(state, context)),
                         expected_tracking_id=self.env["RUNNER_TRACKING_ID"])
        arguments.update(changes)
        return setup.transition_environment(environment, **arguments)

    def test_before_requires_home_marker_and_outcome_keys_absent_not_empty(self):
        for key in ("GRADLE_USER_HOME", setup.MARKER, setup.OUTCOME, setup.CONCLUSION):
            for value in ("", "true", str(self.old)):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    setup.before({**self.env, key: value})
        self.assertEqual(list(self.runner.iterdir()), [])

    def test_inherited_audit_state_and_wrapper_presence_are_refused_even_empty(self):
        for key in ("P2PKIT_AUDIT_STATE_DIR", "P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN",
                    "P2PKIT_AUDIT_OWNERSHIP_DOMAINS", "P2PKIT_AUDIT_DARWIN_PIPES", "P2PKIT_AUDIT_FUTURE",
                    "DYLD_INSERT_LIBRARIES"):
            for value in ("", "fixture"):
                with self.subTest(key=key), self.assertRaises(ValueError):
                    setup.before({**self.env, key: value})

    def test_closed_fixed_identity_requires_nonempty_tool_and_tracking_fields(self):
        for key in setup.IDENTITY_KEYS:
            for value in (None, ""):
                candidate = dict(self.env)
                if value is None:
                    candidate.pop(key)
                else:
                    candidate[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    setup.before(candidate)

    def test_unadmitted_job_source_attempt_and_workflow_are_refused(self):
        for key, value in (("GITHUB_JOB", "repository-checks"), ("GITHUB_SHA", "HEAD"),
                           ("GITHUB_SHA", "0" * 40), ("GITHUB_RUN_ID", "00123"),
                           ("GITHUB_RUN_ATTEMPT", str(2**31)), ("GITHUB_WORKFLOW_SHA", "c" * 39),
                           ("GITHUB_WORKFLOW_REF", "other/workflow.yml"), ("RUNNER_OS", "Linux")):
            with self.subTest(key=key), self.assertRaises(ValueError):
                setup.before({**self.env, key: value})

    def test_private_exclusive_records_capture_actual_export_not_home_inference(self):
        environment = self.capture()
        directory = self.directory()
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        for name in ("before.json", "after.json"):
            self.assertEqual(stat.S_IMODE((directory / name).stat().st_mode), 0o600)
        pre = json.loads((directory / "before.json").read_text())
        post = json.loads((directory / "after.json").read_text())
        self.assertEqual(post["oldGradleHome"], environment["GRADLE_USER_HOME"])
        self.assertNotEqual(post["oldGradleHome"], str(Path(self.env["HOME"]) / ".gradle"))
        self.assertEqual(post["beforeSha256"], hashlib.sha256((directory / "before.json").read_bytes()).hexdigest())
        self.assertEqual(pre["workflowSha256"], hashlib.sha256(self.workflow.read_bytes()).hexdigest())
        self.assertEqual(pre["action"], setup.ACTION)
        self.assertNotIn("PATH", pre["binding"])
        self.assertNotIn("SECRET_FIXTURE", pre["binding"])

    def test_pre_and_post_are_single_use_without_overwrite(self):
        environment = self.capture()
        before = (self.directory() / "before.json").read_bytes()
        after = (self.directory() / "after.json").read_bytes()
        with self.assertRaises(FileExistsError):
            setup.before(self.env)
        with self.assertRaises(FileExistsError):
            setup.after(environment)
        self.assertEqual((self.directory() / "before.json").read_bytes(), before)
        self.assertEqual((self.directory() / "after.json").read_bytes(), after)

    def test_post_needs_both_actual_success_fields_and_completion_marker(self):
        setup.before(self.env)
        for key in (setup.OUTCOME, setup.CONCLUSION, setup.MARKER):
            for value in ("", "failure", "skipped", "cancelled", "SUCCESS", "True"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    setup.after({**self.post_environment(), key: value})
        self.assertFalse((self.directory() / "after.json").exists())

    def test_post_does_not_fallback_when_actual_export_is_absent_or_relative(self):
        setup.before(self.env)
        for value in ("", "relative", "/", "../gradle", "/tmp/../gradle"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                setup.after({**self.post_environment(), "GRADLE_USER_HOME": value})

    def test_changed_fixed_identity_or_workflow_rejects_post_capture(self):
        setup.before(self.env)
        for key, value in (("GITHUB_SHA", "c" * 40), ("GITHUB_RUN_ID", "124"), ("GITHUB_RUN_ATTEMPT", "3"),
                           ("GITHUB_JOB", "artifact-checks"), ("JAVA_HOME", str(self.base / "jdk21")),
                           ("P2PKIT_AUDIT_JDK21", str(self.base / "jdk17")), ("RUNNER_TRACKING_ID", "changed"),
                           ("USER", "changed"), ("LOGNAME", "changed"), ("USER", ""), ("LOGNAME", "")):
            with self.subTest(key=key), self.assertRaises((ValueError, OSError)):
                setup.after({**self.post_environment(), key: value})
        self.workflow.write_text("changed bytes\n")
        with self.assertRaises(ValueError):
            setup.after(self.post_environment())

    def test_wrong_private_modes_hardlinks_and_symlinks_are_refused(self):
        setup.before(self.env)
        directory = self.directory()
        record = directory / "before.json"
        record.chmod(0o644)
        with self.assertRaises(ValueError):
            setup.after(self.post_environment())
        record.chmod(0o600)
        os.link(record, directory / "duplicate")
        with self.assertRaises(ValueError):
            setup.after(self.post_environment())
        (directory / "duplicate").unlink()
        record.rename(directory / "saved.json")
        record.symlink_to(directory / "saved.json")
        with self.assertRaises(ValueError):
            setup.after(self.post_environment())

    def test_private_directory_must_not_be_world_readable_or_a_symlink(self):
        setup.before(self.env)
        directory = self.directory()
        directory.chmod(0o755)
        with self.assertRaises(ValueError):
            setup.after(self.post_environment())
        directory.chmod(0o700)
        other = directory.with_name("saved")
        directory.rename(other)
        directory.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError):
            setup.after(self.post_environment())

    def test_witness_parent_cannot_overlap_checkout(self):
        for value in (str(self.root), str(self.base)):
            with self.assertRaises(ValueError):
                setup.before({**self.env, "RUNNER_TEMP": value})

    def test_closed_witness_keys_phase_pin_and_duplicate_json_are_checked(self):
        setup.before(self.env)
        record = self.directory() / "before.json"
        original = json.loads(record.read_text())
        for key, value in (("schema", True), ("phase", "AFTER"), ("action", "unpinned"), ("extra", True)):
            record.write_text(json.dumps({**original, key: value}))
            with self.assertRaises(ValueError):
                setup.after(self.post_environment())
        record.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError):
            setup.after(self.post_environment())

    def test_transition_calls_validator_and_only_overlays_actual_home_and_selector(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        callback = Mock(return_value=(state, context))
        ambient_before, global_before = copy.deepcopy(environment), dict(os.environ)
        result = self.transition(environment, state, context, admitted, context_at=callback)
        callback.assert_called_once_with(str(state))
        projected = result["environment"]
        self.assertEqual(projected["GRADLE_USER_HOME"], context["gradleHome"])
        self.assertEqual(projected[setup.STATE_SELECTOR], str(state))
        self.assertEqual(projected["RUNNER_TRACKING_ID"], environment["RUNNER_TRACKING_ID"])
        self.assertNotIn("SECRET_FIXTURE", projected)
        self.assertEqual({key for key in projected if key.startswith("P2PKIT_AUDIT_")},
                         {"P2PKIT_AUDIT_JDK21", setup.STATE_SELECTOR})
        self.assertFalse(result["nativeExecutionAuthorized"])
        self.assertFalse(result["cleanupVerified"])
        self.assertEqual(environment, ambient_before)
        self.assertEqual(dict(os.environ), global_before)
        transition = json.loads((self.directory() / "transition.json").read_text())
        self.assertEqual(transition["contextId"], context["id"])
        self.assertEqual(transition["state"], str(state))
        self.assertEqual(transition["source"], admitted["source"])
        self.assertEqual(stat.S_IMODE((self.directory() / "transition.json").stat().st_mode), 0o600)

    def test_current_tool_path_can_include_later_authorized_xcodegen(self):
        environment = self.capture()
        environment["PATH"] = str(self.base / "xcodegen/bin") + ":" + environment["PATH"]
        state, context, admitted = self.context_facts()
        result = self.transition(environment, state, context, admitted)
        self.assertEqual(result["environment"]["PATH"], environment["PATH"])

    def test_default_environment_guard_still_refuses_old_home(self):
        environment = self.capture()
        with self.assertRaises(ValueError):
            admit_environment("platform-full", environment, expected_tracking_id=environment["RUNNER_TRACKING_ID"])

    def test_unknown_old_home_or_inherited_state_refused_before_validator(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        for changes in ({"GRADLE_USER_HOME": str(self.base / "different")}, {setup.MARKER: ""},
                        {"P2PKIT_AUDIT_JOB_ID": ""}, {setup.STATE_SELECTOR: str(state)},
                        {"USER": "different"}, {"LOGNAME": "different"}):
            callback = Mock(return_value=(state, context))
            with self.assertRaises(ValueError):
                self.transition({**environment, **changes}, state, context, admitted, context_at=callback)
            callback.assert_not_called()

    def test_admitted_source_tree_run_and_profile_must_match(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        for changes in ({"source": {"commit": "e" * 40, "tree": "c" * 40}},
                        {"source": {"commit": "a" * 40, "tree": "e" * 40}},
                        {"runAttempt": 3}, {"runId": True}, {"profile": "consumers-complete"}, {"root": str(self.base)},
                        {"ciScope": {"full": False, "head": "a" * 40}}, {"ciScope": {"full": 1, "head": "a" * 40}}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.transition(environment, state, context, {**admitted, **changes})

    def test_canonical_context_source_selector_jdks_and_policy_must_match(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        for changes in ({"expectedCommit": "e" * 40}, {"tree": "e" * 40}, {"source": {}},
                        {"root": str(self.base)}, {"javaHomes": [self.env["JAVA_HOME"]]},
                        {"javaHomes": list(reversed(context["javaHomes"]))}, {"gradlePropertiesSha256": "0" * 64},
                        {"id": "0" * 32}, {"id": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.transition(environment, state, {**context, **changes}, admitted)
        with self.assertRaises(ValueError):
            self.transition(environment, state, context, admitted, context_at=Mock(return_value=(self.base, context)))
        with self.assertRaises(ValueError):
            self.transition(environment, state, context, admitted, context_at=None)

    def test_new_home_must_be_inside_selected_state_and_disjoint_from_old_and_source(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        for home in (self.old, self.root, self.base):
            with self.subTest(home=str(home)), self.assertRaises(ValueError):
                self.transition(environment, state, {**context, "gradleHome": str(home)}, admitted)
        selected = self.old / "state"
        selected.mkdir()
        (selected / "gradle-home").mkdir()
        with self.assertRaises(ValueError):
            self.transition(environment, selected, {**context, "gradleHome": str(selected / "gradle-home")}, admitted)

    def test_changed_policy_workflow_or_witness_link_does_not_get_projected(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        policy = Path(context["gradleHome"]) / "gradle.properties"
        original_policy = policy.read_bytes()
        policy.write_text("changed policy")
        with self.assertRaises(ValueError):
            self.transition(environment, state, context, admitted)
        policy.write_bytes(original_policy)
        post_file = self.directory() / "after.json"
        original_post = post_file.read_bytes()
        post = json.loads(original_post)
        post_file.write_text(json.dumps({**post, "beforeSha256": "0" * 64}))
        with self.assertRaises(ValueError):
            self.transition(environment, state, context, admitted)
        post_file.write_bytes(original_post)
        self.workflow.write_text("changed workflow")
        with self.assertRaises(ValueError):
            self.transition(environment, state, context, admitted)

    def test_raw_state_and_fresh_home_aliases_cannot_be_hidden_by_canonicalization(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        alias = self.base / "state-alias"
        alias.symlink_to(state, target_is_directory=True)
        callback = Mock(return_value=(state, context))
        with self.assertRaises(ValueError):
            self.transition(environment, alias, context, admitted, context_at=callback)
        callback.assert_not_called()
        home = Path(context["gradleHome"])
        moved = self.base / "moved-home"
        home.rename(moved)
        home.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.transition(environment, state, context, admitted)

    def test_successful_transition_is_one_use_even_for_another_validated_fresh_state(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        self.transition(environment, state, context, admitted)
        first = (self.directory() / "transition.json").read_bytes()
        with self.assertRaises(FileExistsError):
            self.transition(environment, state, context, admitted)
        second = self.base / "second-state"
        second.mkdir()
        (second / "gradle-home").mkdir()
        (second / "gradle-home/gradle.properties").write_bytes((state / "gradle-home/gradle.properties").read_bytes())
        changed = {**context, "id": "e" * 32, "gradleHome": str(second / "gradle-home")}
        with self.assertRaises(FileExistsError):
            self.transition(environment, second, changed, admitted)
        self.assertEqual((self.directory() / "transition.json").read_bytes(), first)

    def test_uncertain_transition_write_remains_refusal_without_removal_or_retry(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        with patch.object(setup.os, "fsync", side_effect=OSError("fixture uncertain flush")):
            with self.assertRaises(OSError):
                self.transition(environment, state, context, admitted)
        self.assertTrue((self.directory() / "transition.json").exists())
        with self.assertRaises(FileExistsError):
            self.transition(environment, state, context, admitted)

    def test_short_record_write_is_refused_and_left_consumed(self):
        real_fdopen = os.fdopen
        class ShortWriter:
            def __init__(self, fd, mode):
                self.stream = real_fdopen(fd, mode)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return self.stream.__exit__(*args)
            def fileno(self):
                return self.stream.fileno()
            def write(self, raw):
                return self.stream.write(raw[:-1])
        with patch.object(setup.os, "fdopen", side_effect=lambda fd, mode:
                          ShortWriter(fd, mode) if mode == "wb" else real_fdopen(fd, mode)):
            with self.assertRaisesRegex(ValueError, "Incomplete witness write"):
                setup.before(self.env)
        self.assertTrue((self.directory() / "before.json").exists())
        with self.assertRaises(FileExistsError):
            setup.before(self.env)

    def test_projector_preserves_guard_refusals_and_independent_tracking_binding(self):
        environment = self.capture()
        state, context, admitted = self.context_facts()
        for key in ("JAVA_TOOL_OPTIONS", "BASH_ENV", "P2PKIT_GRADLE_EXECUTOR", "PYTHONPATH"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.transition({**environment, key: "unadmitted"}, state, context, admitted)
        with self.assertRaises(ValueError):
            self.transition(environment, state, context, admitted, expected_tracking_id="different")

    def test_consumer_job_gets_only_complete_source_local_consumer_projection(self):
        self.env["GITHUB_JOB"] = "artifact-checks"
        environment = self.capture()
        state, context, admitted = self.context_facts()
        result = self.transition(environment, state, context, admitted)
        self.assertEqual(result["environment"]["P2PKIT_CONSUMER_PROFILE"], "complete")
        self.assertEqual(result["environment"]["P2PKIT_KEEP_CONSUMER_ARTIFACTS"], "0")

    def test_cli_prints_only_fixed_status_without_private_values(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            self.assertEqual(setup.main(["before"], self.env), 0)
            self.assertEqual(setup.main(["after"], self.post_environment()), 0)
            self.assertEqual(setup.main(["before"], self.env), 125)
            self.assertEqual(setup.main(["other"], self.env), 125)
        for value in (str(self.base), self.env["RUNNER_TRACKING_ID"], self.env["GITHUB_SHA"], "SECRET_FIXTURE"):
            self.assertNotIn(value, output.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
