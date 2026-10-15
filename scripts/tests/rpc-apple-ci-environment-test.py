#!/usr/bin/env python3
"""Pure environment controls; no subprocess, filesystem mutation, build or native work."""
import copy
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rpc_apple_ci_environment as environment


COOKIE = "github_01234567-89ab-cdef-0123-456789abcdef"


def fixture():
    return {
        "PATH": "/private/setup/xcodegen/bin:/private/setup/java/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        "HOME": "/Users/runner", "USER": "runner", "LOGNAME": "runner", "TMPDIR": "/private/tmp/ci/",
        "JAVA_HOME": "/private/setup/java/Contents/Home", "P2PKIT_AUDIT_JDK21": "/private/setup/jdk21",
        "ANDROID_HOME": "/Users/runner/Library/Android/sdk", "ANDROID_SDK_ROOT": "/Users/runner/Library/Android/sdk",
        "DEVELOPER_DIR": "/Applications/Xcode.app/Contents/Developer", "RUNNER_TRACKING_ID": COOKIE,
        "GITHUB_WORKSPACE": "/private/ci/source", "GITHUB_ACTIONS": "true", "CI": "true",
        "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_REF": "refs/pull/463/merge",
        "GITHUB_SHA": "a" * 40, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "2",
        "RUNNER_TEMP": "/private/tmp/runner", "RUNNER_TOOL_CACHE": "/private/toolcache", "LANG": "en_US.UTF-8",
    }


def admit(values=None, profile="consumers-complete", cookie=COOKIE):
    return environment.admit_environment(profile, fixture() if values is None else values,
                                         expected_tracking_id=cookie)


class EnvironmentControls(unittest.TestCase):
    def test_complete_consumers_are_explicitly_pinned_source_local(self):
        result = admit()
        self.assertEqual(result["profile"], "consumers-complete")
        self.assertEqual(result["scope"], environment.SCOPE)
        for key, value in environment.CONSUMER_DEFAULTS.items():
            self.assertEqual(result["environment"][key], value)
        self.assertFalse(result["nativeExecutionAuthorized"])
        self.assertFalse(result["cleanupVerified"])

    def test_platform_profile_keeps_full_argv_contract_separate_from_consumer_switches(self):
        result = admit(profile="platform-full")
        self.assertFalse(set(environment.CONSUMER_DEFAULTS) & set(result["environment"]))
        self.assertEqual(result["profile"], "platform-full")

    def test_original_build_tools_paths_and_tracking_are_preserved_exactly(self):
        original = fixture()
        result = admit(original)["environment"]
        for key, value in original.items():
            self.assertEqual(result[key], value, key)
        self.assertTrue(admit(original)["trackingValueMatched"])

    def test_audit_jdk21_is_a_tool_input_not_an_inherited_ownership_context(self):
        self.assertEqual(admit()["environment"]["P2PKIT_AUDIT_JDK21"], fixture()["P2PKIT_AUDIT_JDK21"])

    def test_complete_or_default_consumer_switches_are_accepted(self):
        for profile in environment.PROFILES:
            for candidate in ({}, environment.CONSUMER_DEFAULTS,
                              dict.fromkeys(environment.CONSUMER_DEFAULTS, "")):
                with self.subTest(profile=profile, candidate=candidate):
                    admit({**fixture(), **candidate}, profile=profile)

    def test_narrow_consumer_profiles_cannot_enter_either_complete_command(self):
        for profile in environment.PROFILES:
            for value in ("lan-jvm-android", "complete ", "full", "0"):
                with self.subTest(profile=profile, value=value), self.assertRaises(ValueError):
                    admit({**fixture(), "P2PKIT_CONSUMER_PROFILE": value}, profile=profile)

    def test_nondefault_retention_and_metadata_are_not_silently_cleared(self):
        for key in ("P2PKIT_KEEP_CONSUMER_ARTIFACTS", "P2PKIT_CONSUMER_AUDIT_METADATA"):
            for value in ("1", "false", "0 "):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    admit({**fixture(), key: value})

    def test_remote_repository_borrowed_directory_and_nested_executor_are_refused(self):
        for key in ("P2PKIT_CONSUMER_REPOSITORY_URL", "P2PKIT_CONSUMER_WORK_DIR", "P2PKIT_GRADLE_EXECUTOR"):
            for value in ("/private/another-run", "https://repo.invalid", " "):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    admit({**fixture(), key: value})

    def test_ambient_owned_state_and_future_consumer_overrides_are_refused(self):
        for key in ("P2PKIT_AUDIT_STATE_DIR", "P2PKIT_AUDIT_JOB_ID", "P2PKIT_AUDIT_OWNERSHIP_CHAIN",
                    "P2PKIT_AUDIT_OWNERSHIP_DOMAINS", "P2PKIT_AUDIT_DARWIN_PIPES", "P2PKIT_CONSUMER_FUTURE"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                admit({**fixture(), key: "unadmitted"})

    def test_gradle_home_needs_explicit_runtime_resolution_not_silent_replacement(self):
        for value in ("/Users/runner/.gradle", "/private/future-owned/home"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                admit({**fixture(), "GRADLE_USER_HOME": value})

    def test_all_known_nonempty_execution_overrides_are_refused_without_value_disclosure(self):
        for key in environment.FORBIDDEN_KEYS:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "^Ambient execution override refused$"):
                admit({**fixture(), key: "private-marker-never-echo"})

    def test_ambient_options_include_real_java_wrapper_injection_paths(self):
        for key in ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
                    "JDK_JAVAC_OPTIONS"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                admit({**fixture(), key: "-Dorg.gradle.java.home=/other -javaagent:/other.jar"})

    def test_exported_shell_functions_native_injection_and_project_properties_are_refused(self):
        for key in ("BASH_FUNC_python3%%", "DYLD_INSERT_LIBRARIES", "ORG_GRADLE_PROJECT_releasePublication",
                    "ORG_GRADLE_PROJECT_signingInMemoryKey", "SIMCTL_CHILD_JAVA_TOOL_OPTIONS"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                admit({**fixture(), key: "private-marker-never-echo"})

    def test_dyld_key_presence_cannot_silently_change_the_runner_wrapper(self):
        for value in ("", "/private/not-a-real-library.dylib", " "):
            with self.subTest(empty=value == ""), self.assertRaisesRegex(
                    ValueError, "^Wrapper-affecting environment presence refused$"):
                admit({**fixture(), "DYLD_INSERT_LIBRARIES": value})

    def test_empty_dangerous_values_are_default_not_propagated(self):
        original = {**fixture(), **dict.fromkeys(environment.FORBIDDEN_KEYS, "")}
        result = admit(original)["environment"]
        self.assertFalse(set(environment.FORBIDDEN_KEYS) & set(result))

    def test_unknown_or_credential_variables_are_not_forwarded(self):
        original = {**fixture(), "GITHUB_TOKEN": "private", "GH_TOKEN": "private", "SIGNING_KEY": "private",
                    "ARBITRARY_FUTURE_ENV": "private", "GITHUB_OUTPUT": "/private/control-channel"}
        result = admit(original)["environment"]
        self.assertFalse(set(original) - set(fixture()) & set(result))
        self.assertNotIn("private", result.values())

    def test_tracking_is_not_dropped_relabelled_or_accepted_from_expected_argument_alone(self):
        for changed in (None, "", "another-cookie", COOKIE + " "):
            original = fixture()
            if changed is None:
                original.pop("RUNNER_TRACKING_ID")
            else:
                original["RUNNER_TRACKING_ID"] = changed
            with self.subTest(changed=changed), self.assertRaisesRegex(ValueError, "^Runner tracking value"):
                admit(original)

    def test_invalid_expected_tracking_values_do_not_leak(self):
        for value in (None, True, "", "private value", "private\nvalue", "x" * 513):
            with self.subTest(value_type=type(value).__name__), self.assertRaisesRegex(
                    ValueError, "^Invalid independently observed tracking value$"):
                admit(cookie=value)

    def test_required_build_values_cannot_be_missing_or_empty(self):
        for key in environment.REQUIRED_KEYS:
            for missing in (True, False):
                original = fixture()
                if missing:
                    original.pop(key)
                else:
                    original[key] = ""
                with self.subTest(key=key, missing=missing), self.assertRaises(ValueError):
                    admit(original)

    def test_one_explicit_sdk_variable_is_sufficient_without_local_properties_fallback(self):
        for missing in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
            original = fixture()
            original.pop(missing)
            self.assertNotIn(missing, admit(original)["environment"])
        original.pop("ANDROID_HOME")
        with self.assertRaises(ValueError):
            admit(original)

    def test_path_values_remain_lexical_and_cannot_use_relative_or_parent_traversal(self):
        for key in environment.PATH_KEYS:
            for value in ("relative", "/", "/private/../tools", "/private//tools", "/private/tool\npath"):
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    admit({**fixture(), key: value})

    def test_search_path_preserves_setup_tools_spaces_trailing_slash_and_duplicates(self):
        value = "/private/Setup Tools/bin/:/usr/bin:/usr/bin:/bin"
        self.assertEqual(admit({**fixture(), "PATH": value})["environment"]["PATH"], value)

    def test_search_path_cannot_silently_search_cwd_or_relative_entries(self):
        for value in (":/bin", "/bin:", "/bin::/usr/bin", ".:/bin", "relative:/bin", "/bin:/tmp/../bin"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                admit({**fixture(), "PATH": value})

    def test_search_path_and_preserved_value_bounds(self):
        for key, value in (("PATH", ":".join(["/bin"] * 129)), ("LANG", "x" * 16385)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                admit({**fixture(), key: value})

    def test_python_output_policy_is_explicit_and_nondefault_request_is_refused(self):
        for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED"):
            self.assertEqual(admit()["environment"][key], "1")
            self.assertEqual(admit({**fixture(), key: "1"})["environment"][key], "1")
            with self.assertRaises(ValueError):
                admit({**fixture(), key: "0"})

    def test_unknown_partial_or_feature_profiles_cannot_be_admitted(self):
        for profile in ("full", "lan-jvm-android", "qualification", "", None, True):
            with self.subTest(profile=profile), self.assertRaises(ValueError):
                admit(profile=profile)

    def test_environment_mapping_is_typed_and_bounded(self):
        for original in (None, [], True, {"X": None}, {1: "x"}, {"X=Y": "z"}, {"X": "a\0b"},
                         {str(index): "value" for index in range(2049)}):
            with self.subTest(value_type=type(original).__name__), self.assertRaises(ValueError):
                environment.admit_environment("consumers-complete", original, expected_tracking_id=COOKIE)

    def test_input_is_not_modified_and_output_does_not_alias_input(self):
        original = fixture()
        before = copy.deepcopy(original)
        result = admit(original)
        self.assertEqual(before, original)
        result["environment"]["JAVA_HOME"] = "/private/changed"
        self.assertEqual(before, original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
