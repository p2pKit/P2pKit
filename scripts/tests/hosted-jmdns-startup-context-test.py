#!/usr/bin/env python3
"""Offline controls for the fixed third bridge profile, not native acceptance.

Only the bridge module is imported. These controls do not import or rerun the
old context/reader suites, invoke a product, obtain native process authority,
or perform a hosted/network operation. Native objects and private files below
are explicitly synthetic observations; actual STARTUP qualification is separate.
"""
import __future__
import ast
import contextlib
import copy
import ctypes
import errno
import grp
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import pwd
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = "scripts/hosted_dependency_update_context.py"
STARTUP_PATH = "scripts/run-hosted-jmdns-startup.py"
STARTUP_WORKFLOW = ".github/workflows/audit-jmdns-startup-context.yml"
SCOPE = "DIRECT_JAVA_STARTUP_DIAGNOSTIC_V1"
REF = "refs/heads/work/release-foundation-dependency-context-startup-control"
OPERATION = Path("/controlled/p2pkit-jmdns-startup-operation")
CLOCK_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
NS = 1_000_000_000
ACCOUNT = {"uid": 501, "euid": 501, "gid": 20, "egid": 20, "groups": [20, 80]}
TOOLS = {"PATH": "/approved/bin", "JAVA_HOME": "/approved/jdk17",
         "P2PKIT_AUDIT_JDK21": "/approved/jdk21",
         "DEVELOPER_DIR": "/Applications/Xcode_26.5.app/Contents/Developer"}
PURPOSES = (
    "startup-prerequisites", "startup-slf4j-download", "startup-vendor-javac", "startup-fixture-javac",
    "startup-control", "startup-failed_recovery", "startup-shared_close", "startup-close_wins",
    "startup-recovery_wins", "startup-responder_close", "startup-callback_executor", "startup-cleanup_retry",
)
CASE_FILES = {
    "case-input.json", "prepared.json", "canonical-entry.json", "producer-result.json",
    "producer-captures.json", "producer-delivery.json", "producer-controller.stdout",
    "producer-controller.stderr", "admin.jsonl", "launch.plist", "native-observations.json",
    "action-observation.json", "bridge-protocol.json", "bridge-result.json",
    "launcher.c", "hosted_dependency_context_launcher_config.h", "launcher-dependencies.before.d",
    "launcher-dependencies.after.d", "launcher.bin", "launcher.json",
    "launcher-command-1.json", "launcher-command-2.json", "launcher-command-3.json",
}
SERVICE_FILES = {"service.stdout", "service.stderr", "producer-pipe.stdout", "producer-pipe.stderr"}
PINNED_READONLY = {
    "scripts/run-audit-command.py": "04e921eb5ba1e715078d9b315e366cc8f970151c9c1e5e0a4e5dfae0f0ed1ccc",
    "scripts/audit_processes.py": "7ef1beb8a79ce3c8e062100849babee6ffa0ce3421d0f0fc56706c3e0ef7ed13",
    # Reviewed shared-control adaptation: saved IDs, native-prelude contract and
    # bounded original-byte installation. Canonical/fixture pins stay unchanged.
    "scripts/tests/hosted-dependency-update-context-test.py":
        "166c79af4702246e5e301bc3ffeea151c21b3912e54ee73265d6704dbe2986f2",
    "AGENTS.md": "3ca3ef11f49ba90152754fb9d884ed353a5bc549b0ab648e182d889d4283d84b",
    "CLAUDE.md": "0fd0e8bdd297e16caabc40e87411c377f674769a40b73a35f43818bf9f97a71d",
    "library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/jmdns/impl/"
    "JmdnsCloseLifecycleFixture.java": "67ccfae9489718111a1abdd2a251541d4107575f6114e3e030d034e131659a4e",
    "library/p2p-transport-lan/src/jvmTest/kotlin/dev/p2pkit/transport/lan/JmdnsCloseLifecycleTest.kt":
        "1eee1f8352a615c5c4aa543aa63837d9112c050c336677d2e3015d237fe27ec7",
}


def offline(event, args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
        "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.chmod", "os.chown",
    }:
        raise AssertionError("offline STARTUP control attempted an external operation: " + event)
    if event == "open" and type(args[2]) is int and args[2] & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
        raise AssertionError("offline STARTUP control attempted a filesystem write")


# Preload the standard library before fencing the sole project import.
sys.addaudithook(offline)


class Source:
    def __init__(self, relative):
        self.text = (ROOT / relative).read_text(encoding="utf-8")
        self.tree = ast.parse(self.text, filename=relative)

    def definition(self, name, owner=None):
        nodes = self.tree.body
        if owner is not None:
            classes = [node for node in nodes if isinstance(node, ast.ClassDef) and node.name == owner]
            if len(classes) != 1:
                raise AssertionError("missing or duplicate source class: " + owner)
            nodes = classes[0].body
        found = [node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name]
        if len(found) != 1:
            raise AssertionError("missing or duplicate source function: " + name)
        return found[0]

    def segment(self, node):
        return ast.get_source_segment(self.text, node)

    @staticmethod
    def call_name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return Source.call_name(node.value) + "." + node.attr
        return ""


def setUpModule():
    global B, BS
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise AssertionError("use python3 -I -B -S for the offline STARTUP controls")
    spec = importlib.util.spec_from_file_location("jmdns_startup_bridge_controls", ROOT / BRIDGE_PATH)
    B = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = B
    spec.loader.exec_module(B)
    BS = Source(BRIDGE_PATH)


def identity(pid=101, parent_pid=71, unique=1001, parent_unique=701):
    return {"pid": pid, "parentPid": parent_pid, "uniqueId": unique, "parentUniqueId": parent_unique,
            "pidVersion": 19, "startSeconds": 123, "startMicroseconds": 456,
            "uid": 501, "realUid": 501, "savedUid": 501, "gid": 20, "realGid": 20, "savedGid": 20, "status": 2}


def request_fixture(profile):
    request = ({"controller_sha": "a" * 40, "controller_tree": "b" * 40,
                "candidate_sha": "c" * 40, "candidate_tree": "d" * 40, "dependency_base_sha": "e" * 40}
               if profile is B.GENERATION else {"source_sha": "a" * 40, "source_tree": "b" * 40})
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit",
           "GITHUB_EVENT_NAME": "workflow_dispatch", "RUNNER_ENVIRONMENT": "github-hosted",
           "GITHUB_JOB": profile.job, "GITHUB_ACTOR": "Apdelrahman1911", "GITHUB_ACTOR_ID": "104788132",
           "GITHUB_TRIGGERING_ACTOR": "Apdelrahman1911", "GITHUB_REF": REF,
           "GITHUB_SHA": "a" * 40, "GITHUB_WORKFLOW_SHA": "a" * 40,
           "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/" + profile.workflow + "@" + REF,
           "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_EVENT_PATH": "/controlled/event.json",
           profile.request_env: B.encoded(request).decode("ascii")}
    github = {"repository": "p2pKit/P2pKit", "workflow": profile.workflow, "job": profile.job, "ref": REF,
              "source": "a" * 40, "sourceTree": "b" * 40, "runId": "123", "runAttempt": "1",
              "actor": "Apdelrahman1911", "actorId": "104788132", "triggeringActor": "Apdelrahman1911"}
    return request, env, github


def allocation_fixture(profile):
    github = request_fixture(profile)[2]
    value = {"schema": 2, "clockDomain": CLOCK_DOMAIN, "source": github["source"],
             "sourceTree": github["sourceTree"], "runId": "123", "runAttempt": "1",
             "startedMonotonicNs": 1000 * NS, "startedEpochNs": (B.POLICY_EXPIRES - 20000) * NS}
    if profile is not B.GENERATION:
        value["scope"] = profile.scope
    return value, github


def case_fixture(profile):
    case = profile.cases[0]
    directory = OPERATION / "bridge/cases" / case
    if profile is B.STARTUP:
        extra, name = "startupInputsSha256", "startup-inputs.json"
    elif profile is B.GENERATION:
        extra, name = "generationInputsSha256", "generation-inputs.json"
    else:
        extra, name = "fixtureSourceSha256", "fixture-source.json"
    original = b"fixed synthetic input bytes\n"
    inputs = {"schema": 1, "scope": profile.scope, "case": case, "binding": "a" * 64,
              "github": request_fixture(profile)[2], "allocationSha256": "b" * 64,
              "repositorySource": {"commit": "a" * 40, "tree": "b" * 40},
              "caseDirectoryIdentity": [7, 11], "foreground": identity(51, 1, 501, 1),
              "account": copy.deepcopy(ACCOUNT), "caseStartNs": 10 * NS, "caseEndNs": 1000 * NS,
              extra: B.digest(original)}
    files = {directory / "case-input.json": B.encoded(inputs), OPERATION / name: original}
    return directory, inputs, files


def canonical_fixture(profile):
    directory, inputs, files = case_fixture(profile)
    state = OPERATION / "states" / inputs["case"] if profile is B.QUALIFICATION else OPERATION / "state"
    canonical = OPERATION / "fixture" if profile is B.QUALIFICATION else ROOT
    policy = b"fixed synthetic canonical policy\n"
    context = {"id": "a" * 32, "root": str(canonical), "gradleHome": str(state / "gradle-home"),
               "source": {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": B.digest(b"")}}
    context_raw = B.encoded(context)
    input_hash = B.digest(files[directory / "case-input.json"])
    entry = {"schema": 1, "scope": profile.scope, "case": inputs["case"], "binding": inputs["binding"],
             "caseInputSha256": input_hash, "contextSha256": B.digest(context_raw), "contextId": context["id"],
             "gradlePolicySha256": B.digest(policy), "producerIdentity": identity(), "enteredMonotonicNs": 10 * NS}
    if profile is B.QUALIFICATION:
        entry.update(fixtureSourceCommit="a" * 40, fixtureSourceTree="b" * 40, invocationId="1" * 32)
    else:
        entry.update(sourceCommit="a" * 40, sourceTree="b" * 40)
    files.update({directory / "canonical-entry.json": B.encoded(entry), state / "context.json": context_raw,
                  state / "gradle-home/gradle.properties": policy})
    return directory, inputs, input_hash, entry, context, files


def result_fixture(profile, *, count=None, code=0):
    entry = canonical_fixture(profile)[3]
    if profile is B.STARTUP:
        purposes = PURPOSES
    elif profile is B.GENERATION:
        purposes = ("dependency-maintenance-prerequisites", "dependency-maintenance-generator")
    else:
        purposes = ("dependency-context-q1",)
    count = len(purposes) if count is None else count
    rows = [{"invocationId": "1" * 32 if profile is B.QUALIFICATION else format(index + 1, "032x"),
             "purpose": purpose, "receiptSha256": B.digest(("receipt-" + str(index)).encode("ascii")),
             "code": code if index == count - 1 else 0, "returnedRawNs": (20 + index) * NS}
            for index, purpose in enumerate(purposes[:count])]
    value = {"schema": 1, "scope": profile.scope, "case": entry["case"], "binding": entry["binding"],
             "caseInputSha256": entry["caseInputSha256"], "canonicalEntrySha256": "e" * 64,
             "producerIdentity": identity(), "commands": rows, "code": code,
             "disposition": "SUCCESS" if code == 0 else "CLOSED_FAILED_PRODUCT" if 1 <= code <= 123
             else "INFRASTRUCTURE_REFUSAL", "completedRawNs": 50 * NS}
    return entry, value


class ProfileAndEnvironmentControls(unittest.TestCase):
    def test_only_three_original_singletons_are_profiles(self):
        self.assertEqual({name for name, value in vars(B).items() if type(value) is B._Profile},
                         {"GENERATION", "QUALIFICATION", "STARTUP"})
        for profile in (B.GENERATION, B.QUALIFICATION, B.STARTUP):
            self.assertIs(B.validate_profile(profile), profile)
            with self.subTest(copy=profile.job), self.assertRaises(B.ContextError):
                B.validate_profile(copy.copy(profile))
        for value in (None, "STARTUP", {}, types.SimpleNamespace(scope=SCOPE)):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(B.ContextError):
                B.validate_profile(value)
        names = ("script", "workflow", "job", "scope", "cases", "operation_env", "request_env",
                 "operation_prefix", "job_seconds", "step_seconds", "upload_seconds")
        expected = (
            (B.STARTUP, (STARTUP_PATH, STARTUP_WORKFLOW, "jmdns_startup", SCOPE, ("STARTUP",),
                         "P2PKIT_JMDNS_STARTUP_OPERATION", "P2PKIT_JMDNS_STARTUP_REQUEST", "p2pkit-jmdns-startup-",
                         12600, 9900, 1320)),
            (B.GENERATION, ("scripts/run-hosted-dependency-update.py", ".github/workflows/dependency-update-candidate.yml",
                            "generate", "MANUAL_DEPENDENCY_GENERATION_ONLY_V1", ("GENERATION",),
                            "P2PKIT_DEPENDENCY_OPERATION", "P2PKIT_MAINTENANCE_REQUEST", "p2pkit-dependency-update-",
                            12600, 9900, 1320)),
            (B.QUALIFICATION, ("scripts/run-hosted-dependency-context-qualification.py",
                               ".github/workflows/dependency-update-context-qualification.yml",
                               "dependency_context_qualification", "MANUAL_DEPENDENCY_CONTEXT_QUALIFICATION_V1",
                               ("Q1", "Q2", "Q3", "Q4"), "P2PKIT_DEPENDENCY_CONTEXT_OPERATION",
                               "P2PKIT_DEPENDENCY_CONTEXT_REQUEST", "p2pkit-dependency-context-", 2460, 1740, 420)),
        )
        for profile, values in expected:
            with self.subTest(profile=profile.job):
                self.assertEqual(tuple(getattr(profile, name) for name in names), values)

    def test_startup_ref_is_exact_and_does_not_admit_an_ordinary_or_qualifier_branch(self):
        self.assertIsNotNone(B.STARTUP.ref.fullmatch(REF))
        for ref in ("refs/heads/main", "refs/heads/work/release-foundation-dependency-context-control",
                    "refs/heads/work/release-foundation-dependency-context-startup-", REF + "/child", REF + "\n"):
            with self.subTest(ref=ref):
                self.assertIsNone(B.STARTUP.ref.fullmatch(ref))
        self.assertEqual(B.GENERATION.ref.pattern, r"refs/heads/(?:main|work/release-foundation-[A-Za-z0-9-]+)\Z")
        self.assertEqual(B.QUALIFICATION.ref.pattern,
                         r"refs/heads/work/release-foundation-dependency-context-[A-Za-z0-9-]+\Z")

    def check_request(self, profile, request, env, event_inputs):
        env = {**env, profile.request_env: B.encoded(request).decode("ascii")}
        with patch.object(B, "physical", side_effect=Path), \
                patch.object(B, "read_file", return_value=B.encoded({"inputs": event_inputs})):
            return B.validate_original_environment(profile, env)

    def test_original_request_event_and_profile_identity_cannot_be_substituted(self):
        for profile in (B.GENERATION, B.QUALIFICATION, B.STARTUP):
            request, env, github = request_fixture(profile)
            with self.subTest(profile=profile.job):
                self.assertEqual(self.check_request(profile, request, env, request), github)
        request, env, _github = request_fixture(B.STARTUP)
        for extra in ("profile", "case", "command", "timeout", "operation", "candidate_sha", "controller_sha"):
            with self.subTest(extra=extra), self.assertRaises(B.ContextError):
                self.check_request(B.STARTUP, {**request, extra: "a" * 40}, env, request)
        for key in request:
            with self.subTest(missing=key), self.assertRaises(B.ContextError):
                self.check_request(B.STARTUP, {name: value for name, value in request.items() if name != key}, env, request)
        mutations = {"GITHUB_EVENT_NAME": "push", "GITHUB_JOB": B.QUALIFICATION.job,
                     "RUNNER_ENVIRONMENT": "self-hosted", "GITHUB_ACTOR_ID": "1",
                     "GITHUB_TRIGGERING_ACTOR": "someone-else", "GITHUB_SHA": "f" * 40,
                     "GITHUB_WORKFLOW_SHA": "f" * 40, "GITHUB_RUN_ID": "01", "GITHUB_RUN_ATTEMPT": "0",
                     "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/" + B.GENERATION.workflow + "@" + REF}
        for key, value in mutations.items():
            with self.subTest(field=key), self.assertRaises(B.ContextError):
                self.check_request(B.STARTUP, request, {**env, key: value}, request)
        for key in B.OWNER_ENV:
            with self.subTest(enclosing_owner=key), self.assertRaises(B.ContextError):
                self.check_request(B.STARTUP, request, {**env, key: "foreign"}, request)
        for event in ({**request, "source_tree": "f" * 40}, {**request, "case": "STARTUP"}, {}):
            with self.subTest(event_keys=tuple(event)), self.assertRaises(B.ContextError):
                self.check_request(B.STARTUP, request, env, event)

    def test_startup_four_tool_environment_does_not_widen_generation_or_qualifier(self):
        self.assertEqual(B.STARTUP_TOOL_ENV, tuple(TOOLS))
        self.assertEqual(B.TOOL_ENV, (*TOOLS, "ANDROID_HOME"))
        generation_tools = {**TOOLS, "ANDROID_HOME": "/approved/android"}
        with patch.object(B.os, "getuid", return_value=501):
            startup = B.child_environment(B.STARTUP, OPERATION, dict(TOOLS))
            generation = B.child_environment(B.GENERATION, OPERATION, generation_tools)
            qualifier = B.child_environment(B.QUALIFICATION, OPERATION, {})
            self.assertEqual({key: startup[key] for key in TOOLS}, TOOLS)
            self.assertNotIn("ANDROID_HOME", startup)
            self.assertEqual(generation["ANDROID_HOME"], generation_tools["ANDROID_HOME"])
            self.assertNotIn("JAVA_HOME", qualifier)
            self.assertNotIn("P2PKIT_AUDIT_JDK21", qualifier)
            self.assertEqual({key: value for key, value in generation.items() if key != "ANDROID_HOME"}, startup)
            for result in (startup, generation, qualifier):
                self.assertEqual(result["__CF_USER_TEXT_ENCODING"], "0x1F5:0:0")
                self.assertFalse(set(result) & {*B.OWNER_ENV, "GH_TOKEN", "GITHUB_TOKEN", "GITHUB_OUTPUT"})
                self.assertFalse(any(key.startswith(("GITHUB_", "ACTIONS_", "DYLD_")) for key in result))
            for key in (*TOOLS,):
                with self.subTest(missing=key), self.assertRaises(B.ContextError):
                    B.child_environment(B.STARTUP, OPERATION, {name: value for name, value in TOOLS.items() if name != key})
            for key in ("ANDROID_HOME", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "BASH_ENV",
                        "DYLD_INSERT_LIBRARIES", "GITHUB_TOKEN", "__CF_USER_TEXT_ENCODING"):
                with self.subTest(extra=key), self.assertRaises(B.ContextError):
                    B.child_environment(B.STARTUP, OPERATION, {**TOOLS, key: "unapproved"})
            with self.assertRaises(B.ContextError):
                B.child_environment(B.GENERATION, OPERATION, dict(TOOLS))
            with self.assertRaises(B.ContextError):
                B.child_environment(B.QUALIFICATION, OPERATION, dict(TOOLS))
            for value in ("", "bad\npath", "bad\0path", 17, True):
                with self.subTest(tool_type=type(value).__name__), self.assertRaises(B.ContextError):
                    B.child_environment(B.STARTUP, OPERATION, {**TOOLS, "JAVA_HOME": value})
            with self.assertRaises(B.ContextError):
                B.child_environment(B.STARTUP, OPERATION, {**TOOLS, "DEVELOPER_DIR": "/another/Xcode"})

    def test_private_startup_environment_rechecks_owner_secret_and_tool_boundaries(self):
        with patch.object(B.os, "getuid", return_value=501):
            expected = B.child_environment(B.STARTUP, OPERATION, dict(TOOLS))
        with patch.object(B.os, "environ", dict(expected)):
            self.assertIsNone(B.validate_private_environment(expected))
        for key in (*B.OWNER_ENV, "GITHUB_RUN_ID", "ACTIONS_RUNTIME_TOKEN", "DYLD_INSERT_LIBRARIES",
                    "GH_TOKEN", "GITHUB_TOKEN", "PYTHONPATH", "PYTHONHOME", "BASH_ENV", "ENV", "JAVA_OPTS",
                    "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"):
            with self.subTest(extra=key), patch.object(B.os, "environ", {**expected, key: "foreign"}), \
                    self.assertRaises(B.ContextError):
                B.validate_private_environment(expected)
        for key in TOOLS:
            for simulated in ({name: value for name, value in expected.items() if name != key},
                              {**expected, key: expected[key] + "-changed"}):
                with self.subTest(tool=key, missing=key not in simulated), patch.object(B.os, "environ", simulated), \
                        self.assertRaises(B.ContextError):
                    B.validate_private_environment(expected)

    def test_startup_service_still_selects_nonroot_ids_before_project_entry(self):
        directory = OPERATION / "bridge/cases/STARTUP"
        launcher = "/private/var/db/p2pkit-context.abcdefghij/launcher"
        context = types.SimpleNamespace(profile=B.STARTUP, interpreter={"path": B.INTERPRETER},
                                        username="runner", groupname="staff", operation=OPERATION, tools=dict(TOOLS),
                                        os_env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"})
        raw = B.service_plist(context, "p2pkit.context.r123.a1.startup.abcdef", directory, launcher)
        self.assertEqual(plistlib.loads(raw), {
            "Label": "p2pkit.context.r123.a1.startup.abcdef", "ProgramArguments": [launcher], "RunAtLoad": True,
            "KeepAlive": False, "AbandonProcessGroup": False, "WorkingDirectory": "/",
            "EnvironmentVariables": {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"},
            "StandardInPath": "/dev/null",
            "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null"})
        self.assertLessEqual(len(raw), B.FRAME_BYTES)
        for account in ({**ACCOUNT, "uid": 0, "euid": 0}, {**ACCOUNT, "euid": 502},
                        {**ACCOUNT, "groups": [80, 20]}, {**ACCOUNT, "gid": True}):
            with self.subTest(account=account), self.assertRaises(B.ContextError):
                B.validate_account(account)


class CaseAndSourceControls(unittest.TestCase):
    def test_startup_uses_real_root_and_single_state_not_the_qualifier_fixture(self):
        for profile in (B.GENERATION, B.STARTUP):
            case = profile.cases[0]
            self.assertEqual(B.case_paths(profile, OPERATION, case),
                             (OPERATION / "bridge/cases" / case, OPERATION / "state", ROOT))
        self.assertEqual(B.case_paths(B.QUALIFICATION, OPERATION, "Q1"),
                         (OPERATION / "bridge/cases/Q1", OPERATION / "states/Q1", OPERATION / "fixture"))
        for case in ("GENERATION", "Q1", "startup", "../STARTUP"):
            with self.subTest(case=case), self.assertRaises(B.ContextError):
                B.case_paths(B.STARTUP, OPERATION, case)

    def test_each_case_consumes_its_own_exact_input_file_and_digest_key(self):
        for profile in (B.GENERATION, B.QUALIFICATION, B.STARTUP):
            directory, inputs, files = case_fixture(profile)
            with self.subTest(profile=profile.job), patch.object(B, "private_directory", return_value=[7, 11]), \
                    patch.object(B, "read_file", side_effect=lambda path, *_args: files[path]) as reader:
                self.assertEqual(B.case_input(profile, directory), (inputs, B.digest(files[directory / "case-input.json"])))
                self.assertEqual({call.args[0] for call in reader.call_args_list}, set(files))
        directory, inputs, files = case_fixture(B.STARTUP)
        for key in ("generationInputsSha256", "fixtureSourceSha256"):
            changed = {**inputs, key: inputs["startupInputsSha256"]}
            del changed["startupInputsSha256"]
            with self.subTest(foreign_key=key), patch.object(B, "private_directory", return_value=[7, 11]), \
                    patch.object(B, "read_file", return_value=B.encoded(changed)), self.assertRaises(B.ContextError):
                B.case_input(B.STARTUP, directory)
        for field, value in (("schema", True), ("scope", B.GENERATION.scope), ("case", "Q1"),
                             ("caseDirectoryIdentity", [7, 12]), ("startupInputsSha256", "f" * 64)):
            changed_files = {**files, directory / "case-input.json": B.encoded({**inputs, field: value})}
            with self.subTest(field=field), patch.object(B, "private_directory", return_value=[7, 11]), \
                    patch.object(B, "read_file", side_effect=lambda path, *_args: changed_files[path]), \
                    self.assertRaises(B.ContextError):
                B.case_input(B.STARTUP, directory)
        files[OPERATION / "startup-inputs.json"] += b"changed"
        with patch.object(B, "private_directory", return_value=[7, 11]), \
                patch.object(B, "read_file", side_effect=lambda path, *_args: files[path]), self.assertRaises(B.ContextError):
            B.case_input(B.STARTUP, directory)

    def test_canonical_entry_shape_preserves_generation_and_qualifier_distinction(self):
        for profile in (B.GENERATION, B.QUALIFICATION, B.STARTUP):
            directory, inputs, input_hash, entry, _context, files = canonical_fixture(profile)
            with self.subTest(profile=profile.job), patch.object(B, "read_file", side_effect=lambda path, *_args: files[path]):
                self.assertEqual(B.read_canonical_entry(profile, directory, inputs, input_hash),
                                 (entry, B.digest(files[directory / "canonical-entry.json"])))
        _directory, inputs, input_hash, entry, _context, _files = canonical_fixture(B.STARTUP)
        for key, value in (("fixtureSourceCommit", "a" * 40), ("fixtureSourceTree", "b" * 40),
                           ("invocationId", "1" * 32), ("sourceCommit", "A" * 40),
                           ("scope", B.QUALIFICATION.scope), ("caseInputSha256", "f" * 64),
                           ("enteredMonotonicNs", inputs["caseEndNs"]), ("enteredMonotonicNs", True)):
            with self.subTest(field=key), self.assertRaises(B.ContextError):
                B.validate_canonical_entry(B.STARTUP, {**entry, key: value}, inputs, input_hash)

    def test_entry_readback_cannot_relabel_other_source_or_qualifier_root_as_startup(self):
        for mutation in ("root", "home", "dirty", "diff", "source", "context_id", "policy", "context_bytes"):
            directory, inputs, input_hash, entry, context, files = canonical_fixture(B.STARTUP)
            state = OPERATION / "state"
            if mutation == "root":
                context["root"] = str(OPERATION / "fixture")
            elif mutation == "home":
                context["gradleHome"] = str(OPERATION / "states/STARTUP/gradle-home")
            elif mutation == "dirty":
                context["source"]["status"] = " M unexpected"
            elif mutation == "diff":
                context["source"]["diffSha256"] = "f" * 64
            elif mutation == "source":
                context["source"]["commit"] = entry["sourceCommit"] = "f" * 40
            elif mutation == "context_id":
                context["id"] = "f" * 32
            elif mutation == "policy":
                files[state / "gradle-home/gradle.properties"] += b"changed"
            files[state / "context.json"] = B.encoded(context)
            if mutation != "context_bytes":
                entry["contextSha256"] = B.digest(files[state / "context.json"])
            else:
                files[state / "context.json"] += b" "
            files[directory / "canonical-entry.json"] = B.encoded(entry)
            with self.subTest(mutation=mutation), patch.object(B, "read_file", side_effect=lambda path, *_args: files[path]), \
                    self.assertRaises(B.ContextError):
                B.read_canonical_entry(B.STARTUP, directory, inputs, input_hash)

    def test_source_rosters_bind_the_shared_launcher_and_startup_imported_helpers(self):
        for profile in (B.GENERATION, B.QUALIFICATION, B.STARTUP):
            expected = {BRIDGE_PATH, profile.script, profile.workflow, "scripts/audit_processes.py",
                        "scripts/run-audit-command.py", "scripts/hosted_dependency_context_launcher.c",
                        "AGENTS.md", "CLAUDE.md", B.POLICY_PATH}
            if profile is B.STARTUP:
                expected.update(("scripts/run-hosted-dependency-update.py", "scripts/hosted_evidence.py"))
            with self.subTest(profile=profile.job):
                names = B._source_names(profile)
                self.assertEqual(set(names), expected)
                self.assertEqual(len(names), len(expected))
        with self.assertRaises(B.ContextError):
            B._source_names(copy.copy(B.STARTUP))

    def test_changed_or_missing_startup_helper_and_policy_bytes_refuse(self):
        names = B._source_names(B.STARTUP)
        originals = {ROOT / name: ("synthetic source " + name).encode("ascii") for name in names}
        originals[ROOT / B.POLICY_PATH] = (ROOT / B.POLICY_PATH).read_bytes()
        source = {"commit": "a" * 40, "tree": "b" * 40,
                  "files": {name: B.digest(originals[ROOT / name]) for name in names}}
        with patch.object(B, "read_file", side_effect=lambda path, *_args: originals[path]):
            self.assertIsNone(B.check_source_files(B.STARTUP, source))
            for name in names:
                changed = copy.deepcopy(source)
                del changed["files"][name]
                with self.subTest(missing=name), self.assertRaises(B.ContextError):
                    B.check_source_files(B.STARTUP, changed)
            changed = copy.deepcopy(source)
            changed["files"]["scripts/run-hosted-context-diagnostic.py"] = "f" * 64
            with self.assertRaises(B.ContextError):
                B.check_source_files(B.STARTUP, changed)
        for name in names:
            drifted = {**originals, ROOT / name: originals[ROOT / name] + b"changed"}
            with self.subTest(changed=name), patch.object(B, "read_file", side_effect=lambda path, *_args: drifted[path]), \
                    self.assertRaises(B.ContextError):
                B.check_source_files(B.STARTUP, source)

    def test_first_increment_keeps_canonical_ownership_existing_tests_and_fixture_bytes(self):
        for relative, expected in PINNED_READONLY.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)


class OrderedResultControls(unittest.TestCase):
    def validate(self, entry, result, profile=None):
        return B.validate_producer_result(B.STARTUP if profile is None else profile, result, entry, entry["caseInputSha256"])

    def test_all_twelve_commands_are_required_for_success_and_old_profiles_keep_their_rosters(self):
        self.assertEqual(B.STARTUP_PURPOSES, PURPOSES)
        self.assertEqual(len(PURPOSES), 12)
        for profile, length in ((B.STARTUP, 12), (B.GENERATION, 2), (B.QUALIFICATION, 1)):
            entry, result = result_fixture(profile)
            with self.subTest(profile=profile.job):
                self.assertEqual(len(result["commands"]), length)
                self.assertEqual(self.validate(entry, result, profile), result)
        for length in range(1, 12):
            entry, result = result_fixture(B.STARTUP, count=length)
            with self.subTest(success_prefix=length), self.assertRaises(B.ContextError):
                self.validate(entry, result)
        entry, result = result_fixture(B.GENERATION, count=1)
        with self.assertRaises(B.ContextError):
            self.validate(entry, result, B.GENERATION)

    def test_every_first_failure_prefix_is_retained_without_synthesizing_not_run_rows(self):
        for length in range(1, 13):
            for code in (1, 23, 123, 124, 125):
                entry, result = result_fixture(B.STARTUP, count=length, code=code)
                before = copy.deepcopy(result)
                with self.subTest(length=length, code=code):
                    self.assertEqual(self.validate(entry, result), before)
                    self.assertEqual(result, before)
                    self.assertEqual(tuple(row["purpose"] for row in result["commands"]), PURPOSES[:length])
        for profile in (B.GENERATION, B.QUALIFICATION):
            entry, result = result_fixture(profile, count=1, code=23)
            with self.subTest(prior_profile=profile.job):
                self.assertEqual(self.validate(entry, result, profile), result)

    def test_order_holes_duplicates_additional_commands_and_continuation_after_failure_refuse(self):
        entry, baseline = result_fixture(B.STARTUP)
        variants = []
        for commands in ([], baseline["commands"][1:], baseline["commands"] + [baseline["commands"][-1]]):
            variants.append({**baseline, "commands": commands})
        for field, value in (("purpose", "startup-extra"), ("purpose", "dependency-maintenance-prerequisites"),
                             ("invocationId", baseline["commands"][0]["invocationId"]),
                             ("returnedRawNs", baseline["commands"][0]["returnedRawNs"] - 1),
                             ("code", 23), ("unexpected", True)):
            result = copy.deepcopy(baseline)
            result["commands"][1][field] = value
            variants.append(result)
        reordered = copy.deepcopy(baseline)
        reordered["commands"][0], reordered["commands"][1] = reordered["commands"][1], reordered["commands"][0]
        variants.append(reordered)
        for index, result in enumerate(variants):
            with self.subTest(mutation=index), self.assertRaises(B.ContextError):
                self.validate(entry, result)

    def test_negative_boolean_unbounded_and_mismatched_return_codes_never_become_closed_failure(self):
        for code in (-15, -1, True, False, 1.0, "23", None, 126, 255):
            entry, result = result_fixture(B.STARTUP, count=1, code=23)
            result["commands"][0]["code"] = result["code"] = code
            with self.subTest(code=code), self.assertRaises(B.ContextError):
                self.validate(entry, result)
        for code, wrong in ((0, "CLOSED_FAILED_PRODUCT"), (23, "SUCCESS"),
                            (124, "CLOSED_FAILED_PRODUCT"), (125, "CLOSED_FAILED_PRODUCT")):
            entry, result = result_fixture(B.STARTUP, code=code)
            result["disposition"] = wrong
            with self.subTest(code=code, wrong=wrong), self.assertRaises(B.ContextError):
                self.validate(entry, result)
        entry, result = result_fixture(B.STARTUP, count=1, code=23)
        result["code"] = 24
        with self.assertRaises(B.ContextError):
            self.validate(entry, result)

    def test_source_owner_hash_and_original_return_clock_remain_bound(self):
        entry, baseline = result_fixture(B.STARTUP)
        for field, value in (("schema", True), ("scope", B.GENERATION.scope), ("case", "Q1"),
                             ("binding", "f" * 64), ("caseInputSha256", "f" * 64),
                             ("canonicalEntrySha256", "not-a-hash"), ("code", True),
                             ("completedRawNs", baseline["commands"][-1]["returnedRawNs"] - 1),
                             ("completedRawNs", True), ("nativeClosed", True)):
            with self.subTest(field=field), self.assertRaises(B.ContextError):
                self.validate(entry, {**baseline, field: value})
        changed = copy.deepcopy(baseline)
        changed["producerIdentity"]["pidVersion"] += 1
        with self.assertRaises(B.ContextError):
            self.validate(entry, changed)
        for field in ("invocationId", "receiptSha256", "returnedRawNs"):
            changed = copy.deepcopy(baseline)
            changed["commands"][0][field] = True
            with self.subTest(row_field=field), self.assertRaises(B.ContextError):
                self.validate(entry, changed)
        changed = copy.deepcopy(baseline)
        changed["commands"][0]["returnedRawNs"] = entry["enteredMonotonicNs"] - 1
        with self.assertRaises(B.ContextError):
            self.validate(entry, changed)
        # Equal raw readings are permitted; result construction is not a new return.
        same_tick = copy.deepcopy(baseline)
        for row in same_tick["commands"]:
            row["returnedRawNs"] = entry["enteredMonotonicNs"]
        self.assertEqual(self.validate(entry, same_tick), same_tick)
        qualifier_entry, qualifier_result = result_fixture(B.QUALIFICATION)
        qualifier_result["commands"][0]["invocationId"] = "f" * 32
        with self.assertRaises(B.ContextError):
            self.validate(qualifier_entry, qualifier_result, B.QUALIFICATION)


def closed_record(profile, code):
    closure = {name: True for name in ("producerNativeExit", "serviceNativeExit", "controlEof", "controlClosed",
                                      "registrationAbsent", "rootObjectsRemoved", "adminClosed", "soleWritersRetired",
                                      "producerPipeEof")}
    closure.update(producerWait=code, producerPipeCaptures="CLOSED", serviceCaptures="CLOSED", producerRecords="CLOSED",
                   serviceFinalFrame="RECEIVED", nativeRetention="HELD_UNTIL_SUITE_FINISH")
    return {"schema": 1, "scope": profile.scope, "case": profile.cases[0], "closure": closure,
            "native": {"producerNative": {"status": {"popenCode": code}},
                       "serviceNative": {"status": {"popenCode": code}}}, "action": {"kind": "NONE"},
            "lossAnnotations": {}}


def file_roster(profile):
    bridge = OPERATION / "bridge"
    result = {bridge: {"foreground.json", "source-after.json", "suite-closed.json", "cases"},
              bridge / "cases": set(profile.cases)}
    for case in profile.cases:
        names = set(CASE_FILES)
        if profile is B.QUALIFICATION:
            names.update(("product-ready.json", "case-result.json"))
            if case in ("Q1", "Q2"):
                names.add("product-release.json")
        if profile is not B.QUALIFICATION or case != "Q4":
            names.update(SERVICE_FILES | {"service-final.json"})
        result[bridge / "cases" / case] = names
    if profile is B.QUALIFICATION:
        result[bridge].add("sentinel")
        result[bridge / "sentinel"] = {"sentinel.stdout", "sentinel.stderr", "native-exit.json"}
    return result


class ClosureAndRosterControls(unittest.TestCase):
    def test_genuine_closed_nonzero_product_is_failure_not_success_and_infrastructure_cannot_export(self):
        for profile in (B.STARTUP, B.GENERATION):
            for code in (0, 1, 23, 123):
                with self.subTest(profile=profile.job, code=code):
                    self.assertEqual(B.validate_production_data(closed_record(profile, code)),
                                     (code, "SUCCESS" if code == 0 else "CLOSED_FAILED_PRODUCT"))
            for code in (-15, True, 124, 125):
                with self.subTest(profile=profile.job, refused=code), self.assertRaises(B.ProductionRefusal):
                    B.validate_production_data(closed_record(profile, code))

    def test_no_retirement_stream_or_native_status_is_replaced_by_optimistic_closed_data(self):
        baseline = closed_record(B.STARTUP, 23)
        for name, original in baseline["closure"].items():
            if name == "producerWait":
                continue
            changed = copy.deepcopy(baseline)
            changed["closure"][name] = False if original is True else "ABSENT_D_DIED"
            with self.subTest(closure=name), self.assertRaises(B.ProductionRefusal):
                B.validate_production_data(changed)
        changed = copy.deepcopy(baseline)
        changed["lossAnnotations"] = {"serviceFinalFrame": "ABSENT_D_DIED"}
        with self.assertRaises(B.ProductionRefusal):
            B.validate_production_data(changed)
        for role in ("producerNative", "serviceNative"):
            changed = copy.deepcopy(baseline)
            changed["native"][role]["status"]["popenCode"] = 0
            with self.subTest(native=role), self.assertRaises(B.ContextError):
                B.validate_production_data(changed)
        for action in ("F_WRITE_EOF", "D_SIGKILL"):
            changed = {**baseline, "action": {"kind": action}}
            with self.subTest(action=action), self.assertRaises(B.ContextError):
                B.validate_production_data(changed)

    def test_only_the_held_original_outcome_can_reach_the_shared_result_gate(self):
        owner = object.__new__(B.Foreground)
        owner.profile, owner.failed, owner._aborted = B.STARTUP, False, False
        record = closed_record(B.STARTUP, 23)
        outcome = B.CaseOutcome(owner, record)
        owner.outcomes = [outcome]
        changed = outcome.record
        changed["closure"]["producerWait"] = 0
        self.assertEqual(owner.production_result(outcome), (23, "CLOSED_FAILED_PRODUCT"))
        for candidate in (record, B.CaseOutcome(owner, record), B.CaseOutcome(object(), record), copy.copy(outcome)):
            with self.subTest(candidate=type(candidate).__name__), self.assertRaises(B.ContextError):
                owner.production_result(candidate)
        for flag in ("failed", "_aborted"):
            setattr(owner, flag, True)
            with self.subTest(flag=flag), self.assertRaises(B.ContextError):
                owner.production_result(outcome)
            setattr(owner, flag, False)

    def read_roster(self, profile, roster):
        owner = object.__new__(B.Foreground)
        owner.profile, owner.operation = profile, OPERATION
        with patch.object(Path, "iterdir", new=lambda path: iter(path / name for name in sorted(roster[path]))), \
                patch.object(Path, "lstat", new=lambda _path: types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600)), \
                patch.object(B, "physical", side_effect=lambda path: path), \
                patch.object(B, "private_directory", return_value=[7, 11]), \
                patch.object(B, "read_file", return_value=b"closed synthetic data\n"):
            return owner._closed_files()

    def test_startup_and_generation_require_complete_rosters_without_qualifier_exceptions(self):
        self.assertEqual(set(B.CASE_FILES), CASE_FILES)
        self.assertEqual(set(B.SERVICE_FILES), SERVICE_FILES)
        for profile in (B.STARTUP, B.GENERATION, B.QUALIFICATION):
            with self.subTest(profile=profile.job):
                files = self.read_roster(profile, file_roster(profile))
                self.assertEqual(files, sorted(files, key=lambda row: row["path"]))
                if profile is not B.QUALIFICATION:
                    expected = {"bridge/" + name for name in ("foreground.json", "source-after.json", "suite-closed.json")}
                    expected.update("bridge/cases/" + profile.cases[0] + "/" + name
                                    for name in CASE_FILES | SERVICE_FILES | {"service-final.json"})
                    self.assertEqual({row["path"] for row in files}, expected)
        # Q4 alone still permits absent D-owned streams, not STARTUP.
        self.assertNotIn("service-final.json", file_roster(B.QUALIFICATION)[OPERATION / "bridge/cases/Q4"])

    def test_every_missing_startup_member_and_foreign_qualifier_file_refuses(self):
        original = file_roster(B.STARTUP)
        for directory, names in original.items():
            for name in names:
                changed = copy.deepcopy(original)
                changed[directory].remove(name)
                with self.subTest(missing=str(directory / name)), self.assertRaises(B.ContextError):
                    self.read_roster(B.STARTUP, changed)
        case = OPERATION / "bridge/cases/STARTUP"
        for name in ("product-ready.json", "product-release.json", "case-result.json", "service-failure.json",
                     "producer-failure.json", "unbounded-extra.log"):
            changed = copy.deepcopy(original)
            changed[case].add(name)
            with self.subTest(extra=name), self.assertRaises(B.ContextError):
                self.read_roster(B.STARTUP, changed)
        changed = copy.deepcopy(original)
        changed[OPERATION / "bridge"].add("sentinel")
        with self.assertRaises(B.ContextError):
            self.read_roster(B.STARTUP, changed)


class ClockAndOwnershipBoundaryControls(unittest.TestCase):
    def test_startup_allocation_scope_and_existing_job_clock_cannot_be_renewed(self):
        for profile in (B.STARTUP, B.GENERATION, B.QUALIFICATION):
            allocation, github = allocation_fixture(profile)
            start, wall = allocation["startedMonotonicNs"], allocation["startedEpochNs"]
            end = start + profile.job_seconds * NS
            with self.subTest(profile=profile.job):
                self.assertEqual(B.validate_allocation(profile, allocation, github, start + NS, wall + NS), end)
            for now, actual_wall in ((start - 1, wall), (end, wall + profile.job_seconds * NS),
                                     (start + NS, wall + 61 * NS + 1), (True, wall)):
                with self.subTest(profile=profile.job, now=now), self.assertRaises(B.ContextError):
                    B.validate_allocation(profile, allocation, github, now, actual_wall)
        allocation, github = allocation_fixture(B.STARTUP)
        for field, value in (("scope", B.GENERATION.scope), ("schema", True), ("clockDomain", "time.monotonic_ns"),
                             ("sourceTree", "f" * 40), ("runAttempt", "2"), ("deadline", 999),
                             ("startedMonotonicNs", True)):
            with self.subTest(field=field), self.assertRaises(B.ContextError):
                B.validate_allocation(B.STARTUP, {**allocation, field: value}, github,
                                      allocation["startedMonotonicNs"] + NS, allocation["startedEpochNs"] + NS)
        without_scope = {key: value for key, value in allocation.items() if key != "scope"}
        with self.assertRaises(B.ContextError):
            B.validate_allocation(B.STARTUP, without_scope, github,
                                  allocation["startedMonotonicNs"] + NS, allocation["startedEpochNs"] + NS)
        self.assertEqual(B.POLICY_EXPIRES, 1791158400)
        self.assertEqual((B.ADMIN_SECONDS, B.ABORT_SECONDS), (10, 120))

    def prepare_owner(self, profile):
        owner = object.__new__(B.Foreground)
        owner.profile, owner.operation = profile, OPERATION
        owner.finished, owner.failed, owner._aborted, owner.current = False, False, False, None
        owner.outcomes, owner._suite_end = [], None
        owner.step_end_ns, owner.job_end_ns, owner.policy_end_ns = 9900 * NS, 12600 * NS, 20000 * NS
        owner.native = types.SimpleNamespace(same=Mock(), attach_attempts=[], signals=[])
        owner.source, owner.foreground_identity = {}, identity(51, 1, 501, 1)
        owner.account, owner.github = copy.deepcopy(ACCOUNT), request_fixture(profile)[2]
        owner.repository_source, owner.allocation_hash = {"commit": "a" * 40, "tree": "b" * 40}, "b" * 64
        owner._original_data = Mock()
        return owner

    def test_prepare_uses_existing_reserves_not_qualifier_case_or_suite_timeouts(self):
        for profile in (B.STARTUP, B.GENERATION, B.QUALIFICATION):
            owner = self.prepare_owner(profile)
            with self.subTest(profile=profile.job), patch.object(B, "shared_raw_ns", return_value=100 * NS), \
                    patch.object(B.os, "urandom", return_value=b"x" * 32), patch.object(Path, "mkdir"), \
                    patch.object(B, "check_source_files"), patch.object(B, "private_directory", return_value=[7, 11]):
                value = owner.prepare_case(profile.cases[0])
                self.assertEqual(value["caseEndNs"], 400 * NS if profile is B.QUALIFICATION else 9780 * NS)
                self.assertEqual(owner._suite_end, 1300 * NS if profile is B.QUALIFICATION else 9780 * NS)
                with self.assertRaises(B.ContextError):
                    owner.prepare_case(profile.cases[0])
        for field in ("job_end_ns", "policy_end_ns"):
            owner = self.prepare_owner(B.STARTUP)
            setattr(owner, field, 2000 * NS)
            with self.subTest(limiting=field), patch.object(B, "shared_raw_ns", return_value=100 * NS), \
                    patch.object(B.os, "urandom", return_value=b"x" * 32), patch.object(Path, "mkdir"), \
                    patch.object(B, "check_source_files"), patch.object(B, "private_directory", return_value=[7, 11]):
                self.assertEqual(owner.prepare_case("STARTUP")["caseEndNs"], (2000 - 1320 - 120) * NS)

    def complete_producer(self, profile, *, code=0, now, deadline=1000 * NS,
                          changed_hash=False, changed_receipt=False):
        entry, result = result_fixture(profile, code=code)
        endpoint = object.__new__(B.Producer)
        endpoint.profile, endpoint.started, endpoint.completed = profile, True, False
        endpoint.case, endpoint.binding, endpoint.trace = entry["case"], entry["binding"], []
        endpoint.entry, endpoint.entry_hash = entry, "e" * 64
        endpoint.input_sha256, endpoint.deadline_ns = entry["caseInputSha256"], deadline
        endpoint.directory, endpoint.state, _root = B.case_paths(profile, OPERATION, entry["case"])
        endpoint.producer_result_path = endpoint.directory / "producer-result.json"
        endpoint.native = types.SimpleNamespace(closed=False)
        endpoint.native.close = Mock(side_effect=lambda: setattr(endpoint.native, "closed", True))
        endpoint.captures = types.SimpleNamespace(close=Mock(return_value=[]))
        endpoint.channel = types.SimpleNamespace(fileno=lambda: -1)
        files = {endpoint.producer_result_path: B.encoded(result)}
        for index, row in enumerate(result["commands"]):
            files[endpoint.state / "evidence" / row["invocationId"] / "receipt.json"] = ("receipt-" + str(index)).encode("ascii")
        if changed_receipt:
            files[endpoint.state / "evidence" / result["commands"][0]["invocationId"] / "receipt.json"] += b"changed"
        if changed_hash:
            result["canonicalEntrySha256"] = "f" * 64
            files[endpoint.producer_result_path] = B.encoded(result)
        with patch.object(B, "read_file", side_effect=lambda path, *_args: files[path]), \
                patch.object(B, "write_new", side_effect=lambda path, raw: files.__setitem__(path, raw)), \
                patch.object(B, "shared_raw_ns", return_value=now), patch.object(B, "close_socket"), \
                patch.object(B, "send_frame") as send:
            returned = endpoint.complete(endpoint.producer_result_path)
        return endpoint, returned, send, result

    def test_p_completion_uses_last_actual_return_plus_300_and_never_a_later_creation_clock(self):
        for profile in (B.STARTUP, B.GENERATION):
            for code in (0, 23, 123):
                _entry, result = result_fixture(profile, code=code)
                cutoff = result["commands"][-1]["returnedRawNs"] + 300 * NS
                with self.subTest(profile=profile.job, code=code):
                    endpoint, returned, send, _result = self.complete_producer(profile, code=code, now=cutoff - 1)
                    self.assertEqual(returned, code)
                    self.assertTrue(endpoint.completed)
                    endpoint.native.close.assert_called_once_with()
                    endpoint.captures.close.assert_called_once_with()
                    self.assertEqual(send.call_count, 1)
                    self.assertEqual(send.call_args.args[-1], cutoff)
                    with self.assertRaises(B.ContextError):
                        endpoint.complete(endpoint.producer_result_path)
                    with self.assertRaises(B.ContextError):
                        self.complete_producer(profile, code=code, now=cutoff)
        _endpoint, _returned, send, _result = self.complete_producer(B.QUALIFICATION, now=500 * NS)
        self.assertEqual(send.call_args.args[-1], 1000 * NS)
        _endpoint, _returned, send, _result = self.complete_producer(B.STARTUP, now=99 * NS, deadline=100 * NS)
        self.assertEqual(send.call_args.args[-1], 100 * NS)
        with self.assertRaises(B.ContextError):
            self.complete_producer(B.STARTUP, now=60 * NS, changed_hash=True)

    def test_receipt_drift_refuses_and_infrastructure_codes_keep_the_original_deadline(self):
        with self.assertRaises(B.ContextError) as refusal:
            self.complete_producer(B.STARTUP, now=60 * NS, changed_receipt=True)
        self.assertEqual((refusal.exception.stage, refusal.exception.reason), ("CLOSE", "RECEIPT_CHANGED"))
        for code in (124, 125):
            with self.subTest(code=code):
                _endpoint, returned, send, result = self.complete_producer(B.STARTUP, code=code, now=500 * NS)
                self.assertEqual(returned, code)
                self.assertEqual(result["disposition"], "INFRASTRUCTURE_REFUSAL")
                self.assertEqual(send.call_args.args[-1], 1000 * NS)
                with self.assertRaises(B.ContextError):
                    self.complete_producer(B.STARTUP, code=code, now=1000 * NS)

    def test_p_d_and_f_share_the_same_finalization_expression_and_exact_eligible_code_guard(self):
        for owner, name, profile_name in (("Producer", "complete", "self.profile"),
                                          (None, "service", "profile"),
                                          ("Foreground", "_run_current_case", "self.profile")):
            node = BS.definition(name, owner)
            expression = ast.parse('min(end_ns, result["commands"][-1]["returnedRawNs"] + 300 * NS)', mode="eval").body
            guard = ast.parse("(" + profile_name + " is GENERATION or " + profile_name +
                              ' is STARTUP) and 0 <= result["code"] <= 123', mode="eval").body
            matches = [item for item in ast.walk(node) if isinstance(item, ast.If) and
                       any(isinstance(statement, ast.Assign) and
                           ast.dump(statement.value) == ast.dump(expression) for statement in item.body)]
            with self.subTest(owner=owner, function=name):
                self.assertEqual(len(matches), 1)
                self.assertEqual(ast.dump(matches[0].test), ast.dump(guard))
                if owner != "Producer":
                    propagation = 'state["end"] = end_ns' if owner is None else 'state["end"], admin.end_ns = end_ns, end_ns'
                    expected = ast.parse(propagation).body[0]
                    self.assertTrue(any(ast.dump(statement) == ast.dump(expected) for statement in matches[0].body))

    def test_startup_cannot_acquire_qualifier_actions_and_keeps_original_native_loss_reaction(self):
        owner = object.__new__(B.Foreground)
        owner.profile, owner.sentinel = B.STARTUP, None
        with self.assertRaises(B.ContextError):
            owner._start_sentinel(1000 * NS)
        with self.assertRaises(B.ContextError):
            owner._qualifier_action({})
        service, producer, foreground = identity(71, 1, 701, 1), identity(), identity(51, 1, 501, 1)
        for profile in (B.STARTUP, B.GENERATION):
            native = types.SimpleNamespace(poll=Mock(), same=Mock(), signal_orphan=Mock(), events={71: {"terminal": True}})
            owner.profile, owner.native, owner.foreground_identity = profile, native, foreground
            owner.current = {"service": service, "producer": producer, "started": True, "final": None,
                             "cancelAttempted": False, "producerSession": {"pid": 101, "sessionId": 101, "processGroupId": 101},
                             "end": 1000 * NS, "actionDone": False}
            with self.subTest(profile=profile.job), patch.object(B, "shared_raw_ns", return_value=100 * NS):
                owner._pump_case()
                owner._pump_case()
                native.signal_orphan.assert_called_once_with(producer, service, owner.current["producerSession"], 1000 * NS)
                self.assertTrue(owner.current["cancelAttempted"])
        complete = BS.segment(BS.definition("complete", "Producer"))
        self.assertIn('self.profile is QUALIFICATION and self.case == "Q4" and result["code"] == 125', complete)
        service_source = BS.segment(BS.definition("service"))
        self.assertIn("start_new_session=True", service_source)
        self.assertIn('birth["parentUniqueId"] == service_identity["uniqueId"]', service_source)
        ready = BS.segment(BS.definition("validate_ready"))
        self.assertIn('producer_identity["parentUniqueId"] == service_identity["uniqueId"]', ready)
        self.assertIn('"sessionId": producer_identity["pid"]', ready)
        self.assertIn('"processGroupId": producer_identity["pid"]', ready)


if __name__ == "__main__":
    unittest.main()
