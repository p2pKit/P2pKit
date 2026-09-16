#!/usr/bin/env python3
"""Pure, adversarial controller controls; NEVER hosted/native/product evidence.

Only disposable synthetic files, in-memory children and native/API mocks are used.
No subprocess, GPG, socket, JVM, simulator, compiler, dependency acquisition or CI
is allowed. Encryption is covered by its separate suite: fake bytes here exercise
controller routing/manifest policy, not cryptographic validity or real retirement.
"""
from __future__ import annotations

import copy
import ctypes
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "run-hosted-lock-candidate.py"
SPEC = importlib.util.spec_from_file_location("hosted_lock_candidate_controls", SOURCE)
app = importlib.util.module_from_spec(SPEC)
with mock.patch.object(ctypes, "CDLL", side_effect=AssertionError("No native loader in pure tests")), \
        mock.patch.object(subprocess, "Popen", side_effect=AssertionError("No subprocess in pure tests")):
    SPEC.loader.exec_module(app)

SHA, TREE, FINGERPRINT, ENCRYPTION_FINGERPRINT = "a" * 40, "b" * 40, "C" * 40, "D" * 40
JOB, PRODUCT_ID, STOP_ID = "d" * 32, "e" * 32, "f" * 32
PUBLIC_KEY = "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\nSYNTHETIC-NOT-A-KEY\n-----END PGP PUBLIC KEY BLOCK-----\n"


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    path.chmod(0o600)


class FakeTee:
    def __init__(self, stream, path, unused, errors):
        path.write_bytes(stream.read())
        path.chmod(0o600)

    def finish(self):
        pass


class ModelScope:
    """An in-memory ownership model, not a native process or retirement receipt."""
    def __init__(self, fixture, job, invocation, state, home):
        self.fixture, self.job, self.invocation = fixture, job, invocation
        self.state, self.home = state, home
        # Parser fixtures only. The real native admission and lifetime algorithm
        # are separately tested; this in-memory model does not execute either.
        self.name, self.baseline = "darwin-libproc-audit-token", set()
        self.leaders, self.drains, self.closed = [], [], False

    def spawn(self, argv, cwd, env):
        self.argv, self.cwd, self.env = list(argv), cwd, dict(env)
        child = SimpleNamespace(stdout=io.BytesIO(b"synthetic stdout\n"), stderr=io.BytesIO(b"synthetic stderr\n"),
                                poll=lambda: 0)
        self.leaders.append(child)
        self.fixture.events.append(("spawn", self.invocation))
        if self.fixture.partial_launch == self.invocation:
            raise OSError("synthetic failure after leader registration")
        return child

    def discover(self):
        self.fixture.events.append(("discover", self.invocation))
        return []

    def drain(self, **kwargs):
        self.drains.append(kwargs)
        self.fixture.events.append(("drain", self.invocation))
        if self.fixture.drain_failure == self.invocation:
            raise OSError("synthetic drain unavailable")
        return []

    def description(self):
        return {"syntheticOnly": True, "invocation": self.invocation, "discoveryErrors": []}

    def close(self):
        self.closed = True
        self.fixture.events.append(("close", self.invocation))


class ProcessWorld:
    """Synthetic native observations for the REAL PosixScope discovery algorithm."""
    def __init__(self, state, home):
        self.state, self.home = str(state), str(home)
        self.identities, self.environments, self.signalled, self.released = {}, {}, [], []

    def add(self, pid, *, marked=False, generation=1, state=None, home=None):
        self.identities[pid] = {"pid": pid, "uid": os.getuid(), "live": True,
                                "uniqueId": pid + generation, "startSeconds": 100 + generation,
                                "startMicroseconds": pid % 1000000, "pidVersion": 1}
        environment = app.processes.ownership_environment({}, JOB, PRODUCT_ID, state or self.state,
                                                          home or self.home) if marked else {}
        self.environments[pid] = {os.fsencode(key): os.fsencode(value) for key, value in environment.items()}


class AlgorithmScope(app.processes.PosixScope):
    """Actual PosixScope logic; only OS census/handle/signal primitives are fakes."""
    name = "darwin-libproc-audit-token"

    def __init__(self, world, *args):
        self.world = world
        super().__init__(*args)

    def _admit(self):
        pass  # No native admission claim. Tests never call DarwinScope._admit.

    def _pids(self):
        return sorted(self.world.identities)

    def _identity(self, pid):
        value = self.world.identities.get(pid)
        return dict(value) if value is not None else None

    def _key(self, identity):
        return app.processes.DarwinScope._key(self, identity)

    def _environment(self, pid):
        return self.world.environments[pid]

    def _acquire(self, identity):
        current = self._identity(identity["pid"])
        if current is None or self._key(current) != self._key(identity):
            raise ProcessLookupError(identity["pid"])
        return "SYNTHETIC_HANDLE", self._key(identity)

    def _send(self, identity, handle, signum):
        current = self._identity(identity["pid"])
        if current is None or self._key(current) != self._key(identity):
            raise ProcessLookupError(identity["pid"])
        if handle != ("SYNTHETIC_HANDLE", self._key(current)):
            raise AssertionError("Model handle/lifetime mismatch")
        self.world.signalled.append((identity["pid"], self._key(identity), signum))
        self.world.identities.pop(identity["pid"])

    def _release(self, handle):
        self.world.released.append(handle)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-hosted-lock-pure-", dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.root, self.state = self.base / "source", self.base / "state"
        self.root.mkdir(mode=0o700)
        self.state.mkdir(mode=0o700)
        for name in ("evidence", "evidence/commands", "evidence/task-maps", "gradle-home", "gradle-home/init.d",
                     "tmp", "tmp/native", "tmp/java", "empty-config", "work", "fixtures", "fixtures/native-tmp"):
            (self.state / name).mkdir(mode=0o700)
        self.runner_temp, self.home, self.sdk = self.base / "runner", self.base / "home", self.base / "sdk"
        for path in (self.runner_temp, self.home, self.sdk):
            path.mkdir(mode=0o700)
        self.event_path = self.base / "event.json"
        self.env = {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_EVENT_NAME": "workflow_dispatch",
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
            "P2PKIT_OPERATION": app.OPERATION, "GITHUB_JOB": app.OPERATION, "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1", "P2PKIT_EXPECTED_SHA": SHA, "P2PKIT_EXPECTED_TREE": TREE,
            "GITHUB_SHA": SHA, "GITHUB_WORKFLOW_SHA": SHA, "P2PKIT_REVIEWED_BASE": SHA,
            "GITHUB_REF": "refs/heads/work/synthetic", "GITHUB_WORKFLOW_REF": app.WORKFLOW + "refs/heads/work/synthetic",
            "GITHUB_WORKSPACE": str(self.root), "GITHUB_EVENT_PATH": str(self.event_path),
            "P2PKIT_EVIDENCE_PUBLIC_KEY": PUBLIC_KEY, "P2PKIT_EVIDENCE_FINGERPRINT": FINGERPRINT,
            "HOME": str(self.home), "ANDROID_HOME": str(self.sdk), "DEVELOPER_DIR": app.XCODE,
            "RUNNER_TEMP": str(self.runner_temp), "GITHUB_OUTPUT": str(self.base / "github-output"),
        }
        self.event = {"inputs": {name: self.env[variable] for name, variable in app.INPUTS.items()},
                      "ref": "work/synthetic", "repository": {"full_name": "p2pKit/P2pKit"}}
        write_json(self.event_path, self.event)
        self.binding = {"commit": SHA, "tree": TREE, "base": SHA, "ref": self.env["GITHUB_REF"],
                        "runId": "123", "runAttempt": "1", "recipientFingerprint": FINGERPRINT, "operation": app.OPERATION}
        self.before = {"commit": SHA, "tree": TREE, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()}
        self.events, self.scopes, self.results = [], [], {}
        self.partial_launch = self.drain_failure = None
        self.api = SimpleNamespace(Tee=FakeTee, wait_process=self.model_wait,
                                   output_roots=lambda root: [root / "build"], retain_reports=mock.Mock())
        for target, name in ((subprocess, "Popen"), (subprocess, "run"), (ctypes, "CDLL"), (socket, "socket"),
                             (app.processes, "host_role"), (app.processes, "make_scope")):
            self.use_patch(mock.patch.object(target, name, side_effect=AssertionError("Unexpected native/process/network call")))
        self.use_patch(mock.patch.object(app, "load_api", return_value=self.api))
        self.use_patch(mock.patch.dict(os.environ, self.env, clear=True))
        self.rt = app.Runtime(self.root, self.state, self.binding, self.env.copy(), job=JOB)
        self.rt.jvm = "-Xmx2048m -XX:ActiveProcessorCount=2"
        self.rt.report["sourceBefore"] = self.before
        self.rt.custody_request = {"source": copy.deepcopy(self.before),
            "command": ["scripts/prepare-dependency-update.sh", SHA], "ownerState": str(self.state),
            "owner": {"job": JOB, "productInvocation": PRODUCT_ID, "stopInvocation": STOP_ID}}

    def use_patch(self, patch):
        value = patch.start()
        self.addCleanup(patch.stop)
        return value

    def model_scope(self, *args):
        scope = ModelScope(self, *args)
        self.scopes.append(scope)
        return scope

    def model_wait(self, scope, child, seconds, cancelled, check, *, stop):
        self.events.append(("wait", scope.invocation, stop))
        check()
        outcome = self.results.get(scope.invocation, 0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    def model_product(self):
        with mock.patch.object(app.processes, "make_scope", side_effect=self.model_scope):
            self.rt.product()

    def neutral_finalizers(self):
        for name in ("collect_custody", "retire_simulator", "retain", "finish_resource"):
            self.use_patch(mock.patch.object(self.rt, name))

    def command_result(self, label):
        return app.parse(app.read(self.rt.commands / label / "command.json"))

    def manifest(self, output):
        # Use the encryption module's actual public shape, but never invoke GPG.
        result = app.hosted_evidence._manifest_identity(SHA, TREE, "123", "1")
        artifact = b"SYNTHETIC CIPHERTEXT FOR ROUTING ONLY: NOT ENCRYPTED"
        (output / "evidence.tar.gz.gpg").write_bytes(artifact)
        (output / "evidence.tar.gz.gpg").chmod(0o600)
        result["artifact"] = {"name": "evidence.tar.gz.gpg", "sha256": hashlib.sha256(artifact).hexdigest(), "size": len(artifact)}
        write_json(output / "manifest.json", result)
        return result

    def public_fixture(self):
        state, output = app.paths(self.binding)
        state.mkdir(mode=0o700)
        output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        output.mkdir(mode=0o700)
        manifest = self.manifest(output)
        self.seal_receipt(output, manifest)
        return output, manifest

    def seal_receipt(self, output, manifest):
        state, _ = app.paths(self.binding)
        write_json(state / "sealed.json", {"binding": self.binding, "recipientFingerprint": FINGERPRINT,
                   "encryptionFingerprint": ENCRYPTION_FINGERPRINT, "manifestSha256": app.digest(output / "manifest.json"),
                   "artifact": manifest.get("artifact"), "scope": "ENCRYPTED_CUSTODY_NOT_ACCEPTANCE"})


class DispatchTests(Fixture):
    def test_exact_six_original_inputs_and_reviewed_source_are_accepted(self):
        self.assertEqual(app.dispatch(self.env, self.root), self.binding)
        self.assertEqual(len(self.event["inputs"]), 6)
        self.assertEqual(self.env["P2PKIT_REVIEWED_BASE"], SHA)

    def test_original_event_accepts_short_or_fully_qualified_same_branch_only(self):
        for ref in ("work/synthetic", "refs/heads/work/synthetic"):
            event = dict(self.event, ref=ref)
            write_json(self.event_path, event)
            with self.subTest(ref=ref):
                self.assertEqual(app.dispatch(self.env, self.root), self.binding)

    def test_missing_extra_or_changed_event_input_rejected(self):
        for name in app.INPUTS:
            for action in ("delete", "change"):
                event = copy.deepcopy(self.event)
                if action == "delete":
                    del event["inputs"][name]
                else:
                    event["inputs"][name] += "mismatch"
                write_json(self.event_path, event)
                with self.subTest(name=name, action=action), self.assertRaises(ValueError):
                    app.dispatch(self.env, self.root)
        for name, value in (("extra", ""), ("skip_tests", "true")):
            event = copy.deepcopy(self.event)
            event["inputs"][name] = value
            write_json(self.event_path, event)
            with self.subTest(extra=name), self.assertRaises(ValueError):
                app.dispatch(self.env, self.root)

    def test_wrong_platform_operation_workflow_and_identity_rejected(self):
        cases = {"GITHUB_ACTIONS": "false", "GITHUB_REPOSITORY": "other/P2pKit", "GITHUB_EVENT_NAME": "push",
                 "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
                 "GITHUB_JOB": "verify", "P2PKIT_OPERATION": "sample-preview", "GITHUB_RUN_ID": "0",
                 "GITHUB_RUN_ATTEMPT": "01", "GITHUB_SHA": "c" * 40, "GITHUB_WORKFLOW_SHA": "c" * 40,
                 "P2PKIT_EXPECTED_SHA": "a" * 39, "P2PKIT_EXPECTED_TREE": "B" * 40,
                 "P2PKIT_REVIEWED_BASE": "c" * 40, "GITHUB_WORKFLOW_REF": "different/workflow@refs/heads/work/synthetic",
                 "GITHUB_REF": "refs/tags/forbidden", "GITHUB_WORKSPACE": str(self.base),
                 "P2PKIT_EVIDENCE_FINGERPRINT": "C" * 16, "GITHUB_SERVER_URL": "https://elsewhere.invalid",
                 "GITHUB_API_URL": "https://elsewhere.invalid"}
        for key, value in cases.items():
            with self.subTest(key=key), self.assertRaises((ValueError, KeyError)):
                app.dispatch(dict(self.env, **{key: value}), self.root)

    def test_original_event_ref_and_repository_must_match(self):
        for field, replacement in (("ref", "main"), ("repository", {"full_name": "other/P2pKit"})):
            event = copy.deepcopy(self.event)
            event[field] = replacement
            write_json(self.event_path, event)
            with self.subTest(field=field), self.assertRaises(ValueError):
                app.dispatch(self.env, self.root)

    def test_dispatch_json_duplicate_keys_and_nonfinite_numbers_rejected(self):
        for raw in (b'{"inputs":{},"inputs":{}}', b'{"inputs":NaN}', b'{"inputs":Infinity}'):
            self.event_path.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                app.dispatch(self.env, self.root)

    def test_private_or_empty_recipient_rejected_before_any_native_call(self):
        for key in ("", PUBLIC_KEY + "PRIVATE KEY", "-----BEGIN PGP PRIVATE KEY BLOCK-----", "\N{SNOWMAN}"):
            env = dict(self.env, P2PKIT_EVIDENCE_PUBLIC_KEY=key)
            event = copy.deepcopy(self.event)
            event["inputs"]["evidence_public_key"] = key
            write_json(self.event_path, event)
            with self.subTest(key=key), self.assertRaises((ValueError, UnicodeError)):
                app.dispatch(env, self.root)


class EnvironmentTests(Fixture):
    def child(self, env=None):
        with mock.patch.object(app.os, "getuid", return_value=os.getuid()), \
                mock.patch.object(app.os, "geteuid", return_value=os.getuid()):
            return app.credential_free_environment(env or self.env, self.state, self.root)

    def test_credentials_and_agent_hooks_never_inherited_parent_unchanged(self):
        ambient = dict(self.env, SSH_AUTH_SOCK="/synthetic/never-open-socket", SSH_AGENT_PID="999999",
                       GH_TOKEN="synthetic-only", GITHUB_TOKEN="synthetic-only", ACTIONS_RUNTIME_TOKEN="synthetic-only",
                       AWS_ACCESS_KEY_ID="synthetic-only", GOOGLE_APPLICATION_CREDENTIALS="/synthetic/no-read",
                       PATH="/synthetic/ambient-bin", PERSONAL_SECRET="synthetic-only")
        before = copy.deepcopy(ambient)
        with mock.patch.dict(os.environ, ambient, clear=True):
            process_before = dict(os.environ)
            child = self.child(ambient)
            self.assertEqual(dict(os.environ), process_before)
        self.assertEqual(ambient, before)
        for key in ("SSH_AUTH_SOCK", "SSH_AGENT_PID", "GH_TOKEN", "GITHUB_TOKEN", "ACTIONS_RUNTIME_TOKEN",
                    "AWS_ACCESS_KEY_ID", "GOOGLE_APPLICATION_CREDENTIALS", "PERSONAL_SECRET"):
            self.assertNotIn(key, child)
        self.assertEqual(child["HOME"], str(self.home))
        self.assertNotEqual(child["PATH"], ambient["PATH"])
        for key in app.IDENTITY_ENV:
            if key in ambient:
                self.assertEqual(child[key], ambient[key])

    def test_execution_overrides_must_fail_not_silently_disappear(self):
        names = ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS",
                 "GRADLE_HOME", "GRADLE_USER_HOME", "KONAN_DATA_DIR", "KONAN_HOME", "KOTLIN_HOME", "KOTLIN_OPTS",
                 "KONAN_OPTS", "KONAN_JVM_ARGS", "KOTLIN_NATIVE_HOME", "ANDROID_USER_HOME", "P2PKIT_GRADLE_EXECUTOR",
                 "P2PKIT_ROOT_OVERRIDE", "GNUPGHOME", "SDKROOT", "TOOLCHAINS", "XCODE_XCCONFIG_FILE", "BASH_ENV", "ENV",
                 "ZDOTDIR", "PYTHONPATH", "PYTHONHOME", "PYTHONSTARTUP", "PYTHONINSPECT", "SUDO_USER", "SUDO_UID",
                 "SUDO_GID", "SUDO_COMMAND", "DYLD_INSERT_LIBRARIES", "LD_PRELOAD", "ORG_GRADLE_PROJECT_secret",
                 "BASH_FUNC_synthetic%%", "GIT_SSH", "GIT_CONFIG_COUNT", "P2PKIT_AUDIT_STATE_DIR")
        for name in names:
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.child(dict(self.env, **{name: "synthetic-nonempty"}))

    def test_fixed_owned_temporary_and_empty_credential_configuration(self):
        child = self.child()
        for key in ("TMPDIR", "TEMP", "TMP"):
            self.assertEqual(child[key], str(self.state / "tmp/native"))
        self.assertEqual(child["JDK_JAVA_OPTIONS"], "-Djava.io.tmpdir=" + str(self.state / "tmp/java"))
        for key, suffix in (("GH_CONFIG_DIR", "gh"), ("CURL_HOME", "curl"), ("GNUPGHOME", "gpg"), ("XDG_CONFIG_HOME", "xdg")):
            self.assertEqual(child[key], str(self.state / "empty-config" / suffix))
        self.assertEqual(child["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(child["GIT_CONFIG_SYSTEM"], "/dev/null")

    def test_sdk_aliases_may_agree_but_may_not_diverge(self):
        child = self.child(dict(self.env, ANDROID_SDK_ROOT=str(self.sdk)))
        self.assertEqual(child["ANDROID_HOME"], str(self.sdk))
        self.assertNotIn("ANDROID_SDK_ROOT", child)
        with self.assertRaises(ValueError):
            self.child(dict(self.env, ANDROID_SDK_ROOT=str(self.home)))

    def test_unadmitted_xcode_or_elevation_rejected(self):
        with self.assertRaises(ValueError):
            self.child(dict(self.env, DEVELOPER_DIR="/Applications/Other.app/Contents/Developer"))
        with mock.patch.object(app.os, "geteuid", return_value=0), self.assertRaises(ValueError):
            app.credential_free_environment(self.env, self.state, self.root)

    def test_bounded_native_jdk_policy_disables_download_and_parallel_work(self):
        raw, jvm = app.policy("/synthetic/jdk17", "/synthetic/jdk21", self.state / "tmp/java")
        lines = raw.decode().splitlines()
        for required in ("org.gradle.workers.max=2", "org.gradle.parallel=false", "org.gradle.daemon=false",
                         "org.gradle.java.installations.auto-download=false", "kotlin.compiler.execution.strategy=in-process",
                         "org.gradle.caching=false", "org.gradle.configuration-cache=false"):
            self.assertIn(required, lines)
        self.assertIn("-Xmx2048m", jvm)
        self.assertIn("-XX:ActiveProcessorCount=2", jvm)
        for bad in ("relative", "/synthetic/jdk,other", "/synthetic/jdk\\other", "/synthetic/jdk other", "/synthetic/jdk=other"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                app.policy(bad, "/synthetic/jdk21", self.state / "tmp/java")
        with self.assertRaises(ValueError):
            app.policy("/synthetic/same", "/synthetic/same", self.state / "tmp/java")


class NativeProfileTests(Fixture):
    INTEL = "dependency-lock-candidate-x64"
    INTEL_XCODE = "/Applications/Xcode_26.3.app/Contents/Developer"

    def intel_environment(self):
        return dict(self.env, P2PKIT_OPERATION=self.INTEL, RUNNER_ARCH="X64", DEVELOPER_DIR=self.INTEL_XCODE)

    def event_for(self, env):
        write_json(self.event_path, dict(self.event, inputs={key: env[name] for key, name in app.INPUTS.items()}))

    def test_intel_dispatch_binds_operation_without_creating_another_job_or_input(self):
        env = self.intel_environment()
        self.event_for(env)
        result = app.dispatch(env, self.root)
        self.assertEqual(result, dict(self.binding, operation=self.INTEL))
        self.assertEqual(env["GITHUB_JOB"], "dependency-lock-candidate")
        self.assertEqual(len(app.INPUTS), 6)

    def test_operation_runner_and_original_event_must_agree(self):
        for operation, arch in ((app.OPERATION, "X64"), (self.INTEL, "ARM64"), ("shell", "X64")):
            env = dict(self.env, P2PKIT_OPERATION=operation, RUNNER_ARCH=arch)
            self.event_for(env)
            with self.subTest(operation=operation, arch=arch), self.assertRaises(ValueError):
                app.dispatch(env, self.root)
        env = self.intel_environment()
        self.event_for(self.env)
        with self.assertRaises(ValueError):
            app.dispatch(env, self.root)

    def test_intel_child_uses_only_its_pinned_xcode_and_keeps_credentials_out(self):
        env = dict(self.intel_environment(), GH_TOKEN="synthetic-never-used", SSH_AUTH_SOCK="/synthetic/agent")
        child = app.credential_free_environment(env, self.state, self.root)
        self.assertEqual(child["DEVELOPER_DIR"], self.INTEL_XCODE)
        self.assertEqual(child["RUNNER_ARCH"], "X64")
        self.assertNotIn("GH_TOKEN", child)
        self.assertNotIn("SSH_AUTH_SOCK", child)
        for original, wrong in ((env, app.XCODE), (self.env, self.INTEL_XCODE)):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                app.credential_free_environment(dict(original, DEVELOPER_DIR=wrong), self.state, self.root)

    def model_admission(self, *, intel, wrong=None):
        """Run the real admission with fake command bytes; no tool or native call."""
        env = self.intel_environment() if intel else self.env.copy()
        env["PATH"] = "/synthetic/never-executed"
        operation = self.INTEL if intel else app.OPERATION
        role, version, java_arch = ("macos-x64", "15.7.9", "amd64") if intel else ("macos-arm64", "26.6.2", "aarch64")
        xcode = "Xcode 26.3\nBuild version 17C529\n" if intel else "Xcode 26.5\nBuild version 17F42\n"
        runtime_version = "26.2" if intel else "26.5"
        runtime = "com.apple.CoreSimulator.SimRuntime.iOS-" + runtime_version.replace(".", "-")
        if wrong:
            role, version, java_arch, xcode, runtime_version = (
                wrong.get("role", role), wrong.get("version", version), wrong.get("java_arch", java_arch),
                wrong.get("xcode", xcode), wrong.get("runtime_version", runtime_version))
        state = Path(tempfile.mkdtemp(prefix="admit-", dir=self.base))
        for name in ("evidence", "evidence/commands", "evidence/task-maps", "gradle-home", "gradle-home/init.d", "tmp", "tmp/java"):
            (state / name).mkdir(mode=0o700)
        rt = app.Runtime(self.root, state, dict(self.binding, operation=operation), env, job=JOB)
        for folder, level in (("android-36", "36"), ("android-37.0", "37.0")):
            path = self.sdk / "platforms" / folder
            path.mkdir(parents=True, exist_ok=True)
            (path / "source.properties").write_text("AndroidVersion.ApiLevel=" + level + "\n")
        (self.root / app.INIT).parent.mkdir(exist_ok=True)
        (self.root / app.INIT).write_text("// synthetic initializer bytes\n")
        homes = {}
        for major in (17, 21):
            home = state / ("jdk" + str(major))
            (home / "bin").mkdir(parents=True)
            (home / "bin/javac").write_bytes(b"synthetic, never executed")
            homes[major] = home
        calls = []

        def command(label, argv, *args, **kwargs):
            calls.append((label, list(argv)))
            rt.command_index += 1
            directory = rt.commands / (f"{rt.command_index:03d}-" + label)
            directory.mkdir()
            outputs = {"macos-version": version + "\n", "physical-memory": str(8 * app.GIB) + "\n",
                       "xcode-version": xcode, "xcode-first-launch": "", "native-controls": "",
                       "simulator-runtimes": json.dumps({"runtimes": [
                           {"identifier": runtime, "version": runtime_version, "isAvailable": True}]}),
                       "simulator-devices": json.dumps({"devices": {runtime: [
                           {"name": "iPhone 17", "state": "Shutdown", "isAvailable": True,
                            "udid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"}]}})}
            for major, home in homes.items():
                outputs["java-home-" + str(major)] = str(home) + "\n"
                outputs["java-" + str(major)] = ""
            raw = outputs[label]
            (directory / "stdout.log").write_text(raw)
            if label in ("java-17", "java-21"):
                major = label.removeprefix("java-")
                (directory / "stderr.log").write_text(
                    f"    java.version = {major}.0.1\n    os.arch = {java_arch}\n"
                    f"    java.io.tmpdir = {state / 'tmp/java'}\n")
            return SimpleNamespace(text=lambda: raw, directory=directory)

        config = state / "config"
        config.mkdir()
        (config / "stdout.log").write_bytes(b"")
        git_outputs = {"shallow": "false\n", "base-ancestry": "", "local-config-names": "",
                       "lock-map": "\n".join(f"synthetic{i}/gradle.lockfile" for i in range(12)) + "\n"}
        def git(label, *args, **kwargs):
            return SimpleNamespace(text=lambda: git_outputs[label], directory=config)

        with mock.patch.object(rt, "source", return_value=self.before), mock.patch.object(rt, "git", side_effect=git), \
                mock.patch.object(rt, "command", side_effect=command), mock.patch.object(rt, "copy_candidates"), \
                mock.patch.object(app.processes, "host_role", return_value=role), \
                mock.patch.object(rt, "multicast") as multicast:
            try:
                rt.admit()
            except ValueError:
                multicast.assert_not_called()
                self.assertNotIn("native-controls", [label for label, _ in calls])
                raise
            multicast.assert_called_once_with()
        self.assertIn(("native-controls", [sys.executable, "-I", "-B", "-S",
            str(app.SCRIPTS / "tests/run-audit-command-test.py"), "--expected-host", role,
            "--evidence-dir", str(rt.evidence / "native-controls"), "--fixture-parent", str(state / "fixtures/native-tmp")]), calls)
        self.assertEqual(rt.env["P2PKIT_WRITER_SIMULATOR"], "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")

    def test_both_profiles_execute_actual_admission_with_their_own_pins(self):
        for intel in (False, True):
            with self.subTest(intel=intel):
                self.model_admission(intel=intel)

    def test_cross_profile_native_tool_and_runtime_values_fail_before_native_controls(self):
        for wrong in ({"role": "macos-arm64"}, {"version": "26.6.2"}, {"java_arch": "aarch64"},
                      {"xcode": "Xcode 26.5\nBuild version 17F42\n"}, {"runtime_version": "26.3"}):
            with self.subTest(wrong=wrong), self.assertRaises(ValueError):
                self.model_admission(intel=True, wrong=wrong)

    def test_resource_helper_receives_exact_selected_native_role(self):
        for operation, role in ((app.OPERATION, "macos-arm64"), (self.INTEL, "macos-x64")):
            rt = app.Runtime(self.root, self.state, dict(self.binding, operation=operation), self.env, job=JOB)
            fake = SimpleNamespace(start=lambda: setattr(rt, "resource_ready", True))
            with mock.patch.object(app, "Command", return_value=fake) as command:
                rt.start_resource()
            argv = command.call_args.args[2]
            self.assertEqual(argv[-2:], ["--expected-host", role])

    def test_selected_simulator_runtime_retirement_never_touches_other_devices(self):
        owned = {"udid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE", "isAvailable": True, "state": "Shutdown"}
        other = dict(owned, udid="11111111-2222-3333-4444-555555555555", state="Booted")
        for operation in (app.OPERATION, self.INTEL):
            for initial in ("Shutdown", "Booted"):
                with self.subTest(operation=operation, initial=initial):
                    rt = app.Runtime(self.root, self.state, dict(self.binding, operation=operation), self.env, job=JOB)
                    rt.simulator = owned
                    rt.report["writer"] = {"launchAttempted": True}
                    calls, queries = [], []
                    def command(label, argv, **kwargs):
                        self.assertEqual(kwargs, {"finalizing": True})
                        calls.append((label, argv))
                        if label == "simulator-shutdown":
                            return None
                        self.assertEqual(label, "simulator-retire-query")
                        state = initial if not queries else "Shutdown"
                        queries.append(state)
                        document = {"devices": {rt.profile["runtime"]: [dict(owned, state=state), other],
                                                "unrelated-runtime": [other]}}
                        return SimpleNamespace(text=lambda: json.dumps(document))
                    with mock.patch.object(rt, "command", side_effect=command):
                        rt.retire_simulator()
                    self.assertEqual(queries, [initial, "Shutdown"])
                    shutdowns = [argv for label, argv in calls if label == "simulator-shutdown"]
                    self.assertEqual(shutdowns, [] if initial == "Shutdown" else
                                     [["/usr/bin/xcrun", "simctl", "shutdown", owned["udid"]]])
                    self.assertEqual(rt.report["simulatorRetirement"]["status"], "KNOWN_SHUTDOWN")

    def test_intel_simulator_in_wrong_runtime_or_externally_booted_is_not_retired(self):
        owned = {"udid": "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE", "isAvailable": True, "state": "Shutdown"}
        for wrong_bucket in (True, False):
            with self.subTest(wrong_bucket=wrong_bucket):
                rt = app.Runtime(self.root, self.state, dict(self.binding, operation=self.INTEL), self.env, job=JOB)
                rt.simulator = owned
                runtime = app.PROFILES[app.OPERATION]["runtime"] if wrong_bucket else rt.profile["runtime"]
                document = {"devices": {runtime: [dict(owned, state="Booted")]}}
                with mock.patch.object(rt, "command", return_value=SimpleNamespace(text=lambda: json.dumps(document))) as command:
                    with self.assertRaises(ValueError):
                        rt.retire_simulator()
                command.assert_called_once()
                self.assertEqual(command.call_args.args[0], "simulator-retire-query")
                self.assertNotIn("simulatorRetirement", rt.report)


class FileAndAdmissionTests(Fixture):
    def test_private_exclusive_write_refuses_existing_symlink_or_hardlinked_input(self):
        target = self.base / "data"
        app.write(target, b"original")
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            app.write(target, b"replacement")
        self.assertEqual(target.read_bytes(), b"original")
        link = self.base / "link"
        link.symlink_to(target)
        with self.assertRaises(ValueError):
            app.read(link)
        hardlink = self.base / "alias"
        os.link(target, hardlink)
        with self.assertRaises(ValueError):
            app.read(target)

    def test_bounded_reads_reject_directory_and_oversized_file(self):
        with self.assertRaises(ValueError):
            app.read(self.root)
        target = self.base / "bounded"
        target.write_bytes(b"12345")
        with self.assertRaises(ValueError):
            app.read(target, 4)

    def test_state_is_fresh_and_not_reused(self):
        with mock.patch.object(app, "paths", return_value=(self.state, self.base / "export")), \
                mock.patch.object(app.hosted_evidence, "validate_recipient") as recipient:
            with self.assertRaises(FileExistsError):
                app.run(self.root, self.binding)
            recipient.assert_not_called()
        self.assertTrue(self.state.is_dir())

    def test_state_inside_source_rejected_before_creation(self):
        nested = self.root / "candidate-state"
        with mock.patch.object(app, "paths", return_value=(nested, self.base / "export")), self.assertRaises(ValueError):
            app.run(self.root, self.binding)
        self.assertFalse(nested.exists())

    def test_existing_generated_output_fails_before_native_or_candidate_copy(self):
        (self.root / "build").mkdir()
        locknames = ["module" + str(index) + "/gradle.lockfile" for index in range(12)]
        config_dir = self.base / "empty-git-config"
        config_dir.mkdir()
        (config_dir / "stdout.log").write_bytes(b"")
        def git(label, *args, **kwargs):
            if label == "shallow":
                return SimpleNamespace(text=lambda: "false\n")
            if label == "lock-map":
                return SimpleNamespace(text=lambda: "\n".join(locknames) + "\n")
            return SimpleNamespace(directory=config_dir)
        with mock.patch.object(self.rt, "source", return_value=self.before), \
                mock.patch.object(self.rt, "git", side_effect=git), mock.patch.object(self.rt, "command") as command, \
                mock.patch.object(self.rt, "copy_candidates") as copy_candidates, self.assertRaises(ValueError):
            self.rt.admit()
        command.assert_not_called()
        copy_candidates.assert_not_called()
        self.assertTrue((self.root / "build").is_dir())

    def test_source_must_be_exact_clean_reviewed_revision_before_host_probe(self):
        for field, value in (("commit", "c" * 40), ("tree", "c" * 40), ("status", " M file\n"),
                             ("diffSha256", hashlib.sha256(b"changed").hexdigest())):
            changed = dict(self.before, **{field: value})
            with self.subTest(field=field), mock.patch.object(self.rt, "source", return_value=changed), \
                    mock.patch.object(self.rt, "git") as git, mock.patch.object(self.rt, "command") as command, \
                    self.assertRaises(ValueError):
                self.rt.admit()
            git.assert_not_called()
            command.assert_not_called()

    def test_invalid_recipient_stops_before_resource_native_or_writer(self):
        fresh = self.base / "fresh-state"
        with mock.patch.object(app, "paths", return_value=(fresh, self.base / "export")), \
                mock.patch.object(app.hosted_evidence, "validate_recipient", side_effect=ValueError("synthetic invalid recipient")), \
                mock.patch.object(app.Runtime, "start_resource") as resource, mock.patch.object(app.Runtime, "admit") as admit, \
                mock.patch.object(app.Runtime, "product") as product:
            self.assertEqual(app.run(self.root, self.binding), 125)
        resource.assert_not_called()
        admit.assert_not_called()
        product.assert_not_called()
        self.assertTrue((fresh / "context.json").is_file())
        self.assertTrue((fresh / "evidence/bootstrap-failure.json").is_file())


class MulticastInterpreterTests(Fixture):
    """Exercise real argv construction; every compiler/network/child is fake."""
    def setUp(self):
        super().setUp()
        vendor = self.root / "library/p2p-transport-lan/vendor/jmdns/src/main"
        (vendor / "java").mkdir(parents=True)
        for number in range(60):
            (vendor / "java" / ("Synthetic%d.java" % number)).write_text("synthetic, never compiled\n")
        resource = vendor / "resources/dev/p2pkit/transport/lan/internal/jmdns/version.properties"
        resource.parent.mkdir(parents=True)
        resource.write_text("synthetic=only\n")
        fixture = self.root / ("library/p2p-transport-lan/src/jvmTest/java/dev/p2pkit/transport/lan/internal/"
                               "jmdns/impl/JmdnsCloseLifecycleFixture.java")
        fixture.parent.mkdir(parents=True)
        fixture.write_text("synthetic fixture, never compiled\n")
        self.pin = "5d6298b93a1905c32cda6478808ac14c2d4a47e91535e53c41f7feeb85d946f4"
        metadata = self.root / "gradle/verification-metadata.xml"
        metadata.parent.mkdir()
        metadata.write_text('<verification-metadata xmlns="https://schema.gradle.org/dependency-verification">'
                            '<components><component group="org.slf4j" name="slf4j-api" version="2.0.7">'
                            '<artifact name="slf4j-api-2.0.7.jar"><sha256 value="' + self.pin + '"/>'
                            '</artifact></component></components></verification-metadata>')
        self.python = self.base / "interpreter" / "python3"
        self.python.parent.mkdir()
        self.python.write_text("synthetic executable, never launched\n")
        self.python.chmod(0o700)
        self.rt.env["JAVA_HOME"] = str(self.base / "synthetic-jdk")
        self.calls = []
        real_digest = app.digest
        self.use_patch(mock.patch.object(app, "digest", side_effect=lambda p:
            self.pin if Path(p).name == "slf4j-api-2.0.7.jar" else real_digest(p)))
        self.command = self.use_patch(mock.patch.object(self.rt, "command", side_effect=self.fake_command))

    def fake_command(self, label, argv, *unused, **kwargs):
        self.calls.append((label, argv))
        directory = self.rt.commands / label
        directory.mkdir()
        (directory / "stdout.log").write_bytes(b"PASS mode=control\n" if label == "multicast-control" else b"")
        (directory / "stderr.log").write_bytes(b"")
        if label == "multicast-dependency":
            Path(argv[argv.index("--output") + 1]).write_bytes(b"SYNTHETIC, NOT A JAR")
        return SimpleNamespace(directory=directory)

    def assert_interpreter(self, supplied):
        with mock.patch.object(app.sys, "executable", str(supplied)):
            self.rt.multicast()
        controls = [argv for label, argv in self.calls if label == "multicast-control"]
        self.assertEqual(len(controls), 1)
        properties = [arg for arg in controls[0] if arg.startswith("-Dp2pkit.audit.pythonExecutable=")]
        self.assertEqual(properties, ["-Dp2pkit.audit.pythonExecutable=" + str(self.python)])
        self.assertEqual([label for label, _ in self.calls], ["multicast-dependency", "multicast-vendor-compile",
                                                           "multicast-fixture-compile", "multicast-control"])

    def assert_rejected_before_acquisition(self, supplied):
        with mock.patch.object(app.sys, "executable", str(supplied)), self.assertRaises((ValueError, OSError, RuntimeError)):
            self.rt.multicast()
        self.command.assert_not_called()
        self.assertFalse((self.state / "work/jmdns").exists())

    def test_canonical_interpreter_is_preserved_in_actual_probe_argv(self):
        self.assert_interpreter(self.python)

    def test_launcher_symlink_is_canonicalized_in_actual_probe_argv(self):
        alias = self.base / "python-launcher"
        alias.symlink_to(self.python)
        self.assert_interpreter(alias)

    def test_ancestor_symlink_is_canonicalized_in_actual_probe_argv(self):
        alias = self.base / "toolchain-alias"
        alias.symlink_to(self.python.parent, target_is_directory=True)
        self.assert_interpreter(alias / self.python.name)

    def test_missing_interpreter_fails_before_probe_acquisition(self):
        self.assert_rejected_before_acquisition(self.base / "missing-python")

    def test_relative_interpreter_fails_before_probe_acquisition(self):
        self.assert_rejected_before_acquisition("relative-python")

    def test_nonexecutable_interpreter_fails_before_probe_acquisition(self):
        self.python.chmod(0o600)
        self.assert_rejected_before_acquisition(self.python)

    def test_directory_interpreter_fails_before_probe_acquisition(self):
        self.assert_rejected_before_acquisition(self.python.parent)

    def test_broken_launcher_symlink_fails_before_probe_acquisition(self):
        alias = self.base / "broken-launcher"
        alias.symlink_to(self.base / "absent-python")
        self.assert_rejected_before_acquisition(alias)


class SharedResourceClockTests(Fixture):
    """Real controller checks, synthetic JSONL and clocks; no native calls."""
    NOW = 30_000_000_000
    DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"

    def setUp(self):
        super().setUp()
        self.directory = self.state / "synthetic-resource-clock"
        self.directory.mkdir()
        self.rt.resource = SimpleNamespace(directory=self.directory, child=None, row={"errors": []})
        self.local = self.use_patch(mock.patch.object(app.time, "monotonic", return_value=1.0))
        self.raw = self.use_patch(mock.patch.object(app.time, "clock_gettime_ns", return_value=self.NOW, create=True))
        self.use_patch(mock.patch.object(app.time, "CLOCK_MONOTONIC_RAW", 4, create=True))
        self.use_patch(mock.patch.object(app.sys, "platform", "darwin"))
        self.samples = {lane: {"schema": 2, "kind": "resource-sample", "lane": lane,
            "clockDomain": self.DOMAIN, "observedRawNs": self.NOW,
            "startedLocalMonotonic": 1.0, "observedLocalMonotonic": 1.0,
            # Deliberately retain a legacy field to expose old epoch subtraction.
            "observedMonotonic": 1.0} for lane in ("fast", "network")}

    def emit(self):
        rows = [*self.samples.values(), {"schema": 2, "kind": "resource-ready"}]
        (self.directory / "stdout.log").write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.rt.resource_cursor, self.rt.resource_buffer, self.rt.resource_samples = 0, b"", {}
        self.rt.resource_ready = False

    def test_fresh_shared_time_does_not_depend_on_parent_process_epoch(self):
        self.local.return_value = 100.0
        self.emit()
        self.rt.check()
        self.raw.assert_called_once_with(4)
        self.local.assert_not_called()

    def test_five_and_eight_second_freshness_limits_remain_inclusive(self):
        self.samples["fast"]["observedRawNs"] -= 5_000_000_000
        self.samples["network"]["observedRawNs"] -= 8_000_000_000
        self.emit()
        self.rt.check()

    def test_each_lane_rejects_one_nanosecond_beyond_its_limit(self):
        for lane, limit in (("fast", 5_000_000_000), ("network", 8_000_000_000)):
            with self.subTest(lane=lane):
                self.samples[lane]["observedRawNs"] = self.NOW - limit - 1
                self.emit()
                with self.assertRaises(ValueError):
                    self.rt.check()
                self.samples[lane]["observedRawNs"] = self.NOW

    def test_negative_legacy_age_cannot_hide_stale_raw_sample(self):
        self.samples["fast"].update(observedMonotonic=100.0, observedRawNs=self.NOW - 6_000_000_000)
        self.emit()
        with self.assertRaises(ValueError):
            self.rt.check()

    def test_each_lane_rejects_future_sample(self):
        for lane in self.samples:
            with self.subTest(lane=lane):
                self.samples[lane]["observedRawNs"] = self.NOW + 1
                self.emit()
                with self.assertRaises(ValueError):
                    self.rt.check()
                self.samples[lane]["observedRawNs"] = self.NOW

    def test_old_missing_or_wrong_clock_contract_is_not_reinterpreted(self):
        good = copy.deepcopy(self.samples["fast"])
        for field, value in (("schema", 1), ("schema", True), ("schema", 2.0),
                             ("clockDomain", "time.monotonic"), ("clockDomain", None),
                             ("observedRawNs", None)):
            with self.subTest(field=field, value=value):
                self.samples["fast"] = {**good, field: value}
                if value is None:
                    self.samples["fast"].pop(field)
                self.emit()
                with self.assertRaises(ValueError):
                    self.rt.check()

    def test_sample_timestamp_requires_nonnegative_integer_nanoseconds(self):
        for value in (True, "30000000000", 30_000_000_000.0, -1, 1 << 64):
            with self.subTest(value=value):
                self.samples["fast"]["observedRawNs"] = value
                self.emit()
                with self.assertRaises(ValueError):
                    self.rt.check()

    def test_unavailable_native_clock_fails_without_local_clock_fallback(self):
        self.emit()
        with mock.patch.object(app.sys, "platform", "linux"), self.assertRaises(ValueError):
            self.rt.check()
        self.raw.assert_not_called()
        self.local.assert_not_called()

    def test_invalid_native_clock_value_fails_closed(self):
        for value in (True, -1, 0.5, "30000000000", 1 << 64):
            with self.subTest(value=value):
                self.raw.return_value = value
                self.emit()
                with self.assertRaises(ValueError):
                    self.rt.check()

    def test_stale_sample_cannot_suppress_same_home_stop_or_owned_drains(self):
        self.samples["fast"]["observedRawNs"] -= 6_000_000_000
        self.emit()
        resource, original_wait = self.rt.resource, self.api.wait_process
        self.rt.resource = None
        def wait(scope, child, seconds, cancelled, check, *, stop):
            # A pre-launch rejection correctly needs no Gradle stop. Inject the
            # stale observation only after the modeled writer actually launches.
            if scope.invocation == PRODUCT_ID:
                self.rt.resource = resource
            return original_wait(scope, child, seconds, cancelled, check, stop=stop)
        self.api.wait_process = wait
        self.model_product()
        self.assertIsNone(self.rt.report["writer"]["waitExitCode"])
        self.assertEqual(self.rt.report["stop"]["waitExitCode"], 0)
        self.assertTrue(any(row["stage"] == "writer" and row["message"] == "LANE_STALE" for row in self.rt.errors))
        self.assertTrue(all(scope.closed and scope.drains for scope in self.scopes))

    def test_finalization_does_not_consult_failed_resource_clock(self):
        self.raw.side_effect = AssertionError("Cleanup must not consult clock")
        self.emit()
        self.rt.check(finalizing=True)
        self.raw.assert_not_called()


class BoundedStreamTests(unittest.TestCase):
    def test_exact_stream_limit_is_complete_not_truncated(self):
        source, result, errors = io.BytesIO(b"12345678"), {}, []
        budget = app.StreamBudget(8)
        reader = app.BoundedReader(source, budget, result, errors, limit=8)
        self.assertEqual(reader.read(8), b"12345678")
        self.assertEqual(reader.read(8), b"")
        self.assertEqual(result, {"observedBytes": 8, "retainedBytes": 8, "truncated": False, "limitBytes": 8})
        self.assertFalse(errors)
        self.assertEqual(budget.remaining, 0)
        reader.close()
        self.assertTrue(source.closed)

    def test_overflow_retains_only_prefix_and_latches_incomplete_transcript(self):
        source, result, errors = io.BytesIO(b"123456"), {}, []
        reader = app.BoundedReader(source, app.StreamBudget(20), result, errors, limit=4)
        self.assertEqual(reader.read(20), b"1234")
        self.assertEqual(reader.read(20), b"")
        self.assertEqual(result["observedBytes"], 6)
        self.assertEqual(result["retainedBytes"], 4)
        self.assertTrue(result["truncated"])
        self.assertEqual(len(errors), 1)
        self.assertIn("NOT complete execution evidence", errors[0])

    def test_shared_budget_caps_aggregate_across_separate_streams(self):
        budget = app.StreamBudget(5)
        first, second, first_errors, second_errors = {}, {}, [], []
        left = app.BoundedReader(io.BytesIO(b"abc"), budget, first, first_errors, limit=4)
        right = app.BoundedReader(io.BytesIO(b"def"), budget, second, second_errors, limit=4)
        self.assertEqual(left.read(), b"abc")
        self.assertEqual(right.read(), b"de")
        self.assertEqual(first["retainedBytes"] + second["retainedBytes"], 5)
        self.assertEqual(budget.remaining, 0)
        self.assertFalse(first["truncated"])
        self.assertTrue(second["truncated"])
        self.assertFalse(first_errors)
        self.assertEqual(len(second_errors), 1)

    def test_read_request_is_chunk_bounded_without_truncating_exact_total(self):
        source, result, errors = io.BytesIO(b"x" * 65537), {}, []
        reader = app.BoundedReader(source, app.StreamBudget(65537), result, errors, limit=65537)
        self.assertEqual(len(reader.read(10 ** 9)), 65536)
        self.assertEqual(reader.read(), b"x")
        self.assertEqual(reader.read(), b"")
        self.assertEqual(result["retainedBytes"], 65537)
        self.assertFalse(result["truncated"])
        self.assertFalse(errors)


class ProductCustodyTests(Fixture):
    def assert_original_product_and_stop(self, expected_product):
        writer, stop = self.command_result("writer"), self.command_result("stop")
        self.assertEqual(writer, self.rt.report["writer"])
        self.assertEqual(stop, self.rt.report["stop"])
        self.assertEqual(writer["invocation"], PRODUCT_ID)
        self.assertEqual(stop["invocation"], STOP_ID)
        self.assertEqual(writer["waitExitCode"], expected_product)
        self.assertEqual(writer["argv"], ["scripts/prepare-dependency-update.sh", SHA])
        self.assertEqual(stop["argv"][0:3], [str(self.root / "gradlew"), "--stop", "--console=plain"])
        self.assertEqual(writer["timeoutSeconds"], 7200)
        self.assertEqual(stop["timeoutSeconds"], 120)
        self.assertIn("product-final", [row["stage"] for row in writer["drains"]])
        self.assertIn("stop-final", [row["stage"] for row in stop["drains"]])
        self.assertEqual([scope.invocation for scope in self.scopes], [PRODUCT_ID, STOP_ID])
        for scope in self.scopes:
            self.assertEqual(scope.job, JOB)
            self.assertEqual(scope.home, str(self.rt.home))
            self.assertEqual(scope.state, str(self.state))
            self.assertEqual(scope.env["GRADLE_USER_HOME"], str(self.rt.home))
            self.assertEqual(scope.env["P2PKIT_AUDIT_STATE_DIR"], str(self.state))
            self.assertEqual(scope.env["P2PKIT_AUDIT_OWNERSHIP_CHAIN"], scope.invocation)
            self.assertTrue(scope.closed)
        self.assertIn(("wait", STOP_ID, True), self.events)
        self.assertFalse(self.rt.report["candidateAccepted"])

    def test_success_uses_reserved_ids_same_home_and_original_records(self):
        self.model_product()
        self.assert_original_product_and_stop(0)
        self.assertFalse(self.rt.errors)

    def test_nonzero_writer_never_laundered_by_successful_stop(self):
        self.results[PRODUCT_ID] = 19
        self.model_product()
        self.assert_original_product_and_stop(19)
        self.assertEqual(self.rt.report["stop"]["waitExitCode"], 0)
        self.assertTrue(any(row["stage"] == "writer" for row in self.rt.errors))
        self.neutral_finalizers()
        self.rt.finalize()
        self.assertEqual(self.rt.report["finalExitCode"], 125)
        self.assertEqual(self.rt.report["candidateStatus"], "HOLD")

    def test_writer_timeout_still_stops_and_retains_original_absent_exit(self):
        self.results[PRODUCT_ID] = TimeoutError("synthetic timeout")
        self.model_product()
        self.assert_original_product_and_stop(None)
        self.assertTrue(self.rt.report["writer"]["launchAttempted"])
        self.assertEqual(self.rt.report["stop"]["waitExitCode"], 0)

    def test_partial_launch_uses_registered_leader_and_always_stops(self):
        self.partial_launch = PRODUCT_ID
        self.model_product()
        self.assert_original_product_and_stop(None)
        self.assertTrue(self.rt.report["writer"]["launchAttempted"])
        self.assertEqual((self.rt.commands / "writer/stdout.log").read_bytes(), b"synthetic stdout\n")
        self.assertFalse(any(event[0:2] == ("wait", PRODUCT_ID) for event in self.events))

    def test_prelaunch_cancellation_does_not_fabricate_product_or_stop_execution(self):
        self.rt.cancelled.append(15)
        self.model_product()
        writer = self.command_result("writer")
        self.assertFalse(writer["launchAttempted"])
        self.assertIsNone(writer["waitExitCode"])
        self.assertIsNone(self.rt.report["stop"])
        self.assertFalse(self.scopes)
        self.assertIn("product-final", [row["stage"] for row in writer["drains"]])

    def test_failed_stop_is_original_failure_not_skipped_or_relabelled(self):
        self.results[STOP_ID] = 7
        self.model_product()
        self.assert_original_product_and_stop(0)
        self.assertEqual(self.rt.report["stop"]["waitExitCode"], 7)
        self.assertTrue(any(row["stage"] == "stop" for row in self.rt.errors))
        self.neutral_finalizers()
        self.rt.finalize()
        self.assertEqual(self.rt.report["candidateStatus"], "HOLD")

    def test_drain_failure_does_not_prevent_stop_or_terminal_product_record(self):
        self.drain_failure = PRODUCT_ID
        self.model_product()
        self.assert_original_product_and_stop(0)
        self.assertTrue(self.rt.report["writer"]["errors"])
        self.assertTrue(self.rt.errors)
        self.assertTrue(any(row["error"] for row in self.rt.report["writer"]["drains"]))

    def test_stop_constructor_failure_still_finalizes_product_and_latches_hold(self):
        (self.rt.commands / "stop").mkdir()
        # Reserved stop path collision is not permission to overwrite another record.
        marker = self.rt.commands / "stop/other-owner"
        marker.write_bytes(b"untouched")
        self.model_product()
        writer = self.command_result("writer")
        self.assertIn("product-final", [row["stage"] for row in writer["drains"]])
        self.assertEqual(marker.read_bytes(), b"untouched")
        self.assertTrue(self.scopes[0].closed)
        self.assertTrue(self.rt.errors)
        self.assertIsNone(self.rt.report["stop"])

    def test_failed_observer_does_not_veto_same_home_stop(self):
        original_wait = self.api.wait_process
        def wait(scope, child, seconds, cancelled, check, *, stop):
            if scope.invocation == PRODUCT_ID:
                directory = self.state / "observer-error"
                directory.mkdir()
                (directory / "stdout.log").write_bytes(b'{"kind":"resource-error","code":"SYNTHETIC"}\n')
                self.rt.resource = SimpleNamespace(directory=directory, child=None, row={"errors": []})
                check()
            return original_wait(scope, child, seconds, cancelled, check, stop=stop)
        self.api.wait_process = wait
        self.model_product()
        self.assert_original_product_and_stop(None)
        self.assertEqual(self.rt.report["stop"]["waitExitCode"], 0)

    def test_product_stream_exhaustion_cannot_consume_stop_transcript_reserve(self):
        self.assertEqual(self.rt.stream_budget.remaining, 64 * app.MIB)
        self.assertEqual(self.rt.final_stream_budget.remaining, 8 * app.MIB)
        self.rt.stream_budget = app.StreamBudget(1)
        self.model_product()
        self.assert_original_product_and_stop(None)
        self.assertTrue(self.rt.report["writer"]["streams"]["stdout"]["truncated"])
        self.assertTrue(self.rt.report["writer"]["errors"])
        self.assertEqual(self.rt.report["stop"]["waitExitCode"], 0)
        self.assertFalse(self.rt.report["stop"]["streams"]["stdout"]["truncated"])
        self.assertFalse(self.rt.report["stop"]["errors"])

    def test_replaced_home_blocks_stop_spawn_but_not_original_native_drains(self):
        original_wait = self.api.wait_process
        def replace_after_product(scope, child, seconds, cancelled, check, *, stop):
            code = original_wait(scope, child, seconds, cancelled, check, stop=stop)
            if scope.invocation == PRODUCT_ID:
                self.rt.home.rename(self.state / "original-gradle-home")
                self.rt.home.mkdir(mode=0o700)
            return code
        self.api.wait_process = replace_after_product
        self.model_product()
        self.assertEqual([scope.invocation for scope in self.scopes], [PRODUCT_ID])
        self.assertTrue(self.scopes[0].closed)
        self.assertGreaterEqual(len(self.scopes[0].drains), 2)
        writer, stop = self.command_result("writer"), self.command_result("stop")
        self.assertEqual(writer["waitExitCode"], 0)
        self.assertIn("product-final", [row["stage"] for row in writer["drains"]])
        self.assertFalse(stop["launchAttempted"])
        self.assertIsNone(stop["waitExitCode"])
        self.assertIn("stop-final", [row["stage"] for row in stop["drains"]])
        self.assertTrue(self.rt.errors)
        self.assertTrue((self.state / "original-gradle-home").is_dir())

    def test_prepare_consumes_actual_helper_reservation_and_full_writer_contract(self):
        request = copy.deepcopy(self.rt.custody_request)
        def prepare(label, argv, **kwargs):
            self.assertEqual(label, "custody-prepare")
            self.assertIn("--scope", argv)
            self.assertEqual(argv[argv.index("--scope") + 1], "both")
            self.assertEqual(argv[argv.index("--owner-kind") + 1], "writer")
            self.assertEqual(argv[argv.index("--writer-job") + 1], JOB)
            self.assertEqual(argv[argv.index("--home") + 1], str(self.rt.home))
            self.assertEqual(argv[argv.index("--") + 1:], request["command"])
            custody = self.state / "custody"
            custody.mkdir()
            write_json(custody / "request.json", request)
        self.rt.custody_request = None
        with mock.patch.object(self.rt, "command", side_effect=prepare):
            self.rt.prepare_custody()
        self.assertEqual(self.rt.custody_request, request)
        self.model_product()
        self.assert_original_product_and_stop(0)

    def test_custody_snapshot_preserves_original_writer_stop_and_mutable_scope(self):
        self.model_product()
        self.rt.custody_attempted = True
        (self.state / "custody").mkdir()
        calls = []
        def command(label, argv, **kwargs):
            calls.append((label, argv, kwargs))
            if label == "custody-collect":
                write_json(self.state / "custody/result.json", {"result": "RETAINED", "retirement": "KNOWN"})
        with mock.patch.object(self.rt, "command", side_effect=command):
            self.rt.collect_custody()
        snapshot = app.parse(app.read(self.state / "custody-owner-snapshot.json"))
        self.assertEqual(snapshot["scope"], "MUTABLE_FULL_WRITER_NOT_AUDIT_LEAF")
        self.assertEqual(snapshot["state"], str(self.state))
        self.assertEqual(snapshot["sourceBefore"], self.before)
        self.assertEqual(snapshot["writer"], self.command_result("writer"))
        self.assertEqual(snapshot["stop"], self.command_result("stop"))
        self.assertEqual([row[0] for row in calls], ["custody-collect", "custody-uninstall"])
        self.assertTrue(all(row[2]["finalizing"] for row in calls))

    def test_custody_hold_does_not_uninstall_unknown_retirement_or_claim_success(self):
        self.rt.custody_attempted = True
        (self.state / "custody").mkdir()
        calls = []
        def command(label, argv, **kwargs):
            calls.append(label)
            write_json(self.state / "custody/result.json", {"result": "HOLD", "retirement": "UNKNOWN"})
        with mock.patch.object(self.rt, "command", side_effect=command), self.assertRaises(ValueError):
            self.rt.collect_custody()
        self.assertEqual(calls, ["custody-collect"])
        self.assertEqual(self.rt.report["transcriptCustody"], {"result": "HOLD", "retirement": "UNKNOWN"})
        self.assertFalse(self.rt.report["candidateAccepted"])


class FinalizationAndRetentionTests(Fixture):
    def complete_retention_fixture(self):
        """Twelve tiny synthetic locks plus model report/generated/custody bytes."""
        self.rt.lockfiles = ["module" + str(index) + "/gradle.lockfile" for index in range(12)]
        originals = {}
        for name in [*self.rt.lockfiles, "gradle/verification-metadata.xml"]:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            originals[name] = ("synthetic candidate only: " + name + "\n").encode()
            path.write_bytes(originals[name])
        generated = self.root / "build/generated.api"
        generated.parent.mkdir()
        generated.write_bytes(b"synthetic generated output, not an actual ABI dump\n")
        write_json(self.rt.evidence / "task-maps/original.jsonl", {"event": "graph",
                   "task": {"path": ":model:abiDump", "outputs": [str(generated)]}})
        self.api.regular_report_files = lambda directory, unused: sorted(path for path in directory.rglob("*") if path.is_file())
        def reports(root, state, commands, report, evidence):
            app.write(evidence / "report-model-marker", b"synthetic report retention completed\n")
        self.api.retain_reports.side_effect = reports
        custody = self.state / "custody"
        custody.mkdir()
        (custody / "original.log").write_bytes(b"synthetic private original custody\n")
        write_json(self.state / "custody-owner-snapshot.json", {"scope": "MUTABLE_FULL_WRITER_NOT_AUDIT_LEAF",
                   "writer": {}, "stop": {}, "sourceBefore": self.before, "state": str(self.state)})
        return originals

    def assert_retained_failure_artifacts(self, originals, *, missing=()):
        for name, raw in originals.items():
            if name in missing:
                continue
            self.assertEqual((self.rt.evidence / "candidate/after" / name).read_bytes(), raw)
            self.assertEqual((self.root / name).read_bytes(), raw)
        self.api.retain_reports.assert_called_once()
        self.assertEqual((self.rt.evidence / "report-model-marker").read_bytes(), b"synthetic report retention completed\n")
        self.assertEqual((self.rt.evidence / "generated/build/generated.api").read_bytes(),
                         b"synthetic generated output, not an actual ABI dump\n")
        self.assertEqual((self.rt.evidence / "custody/original.log").read_bytes(), b"synthetic private original custody\n")
        self.assertEqual((self.rt.evidence / "custody-owner-snapshot.json").read_bytes(),
                         (self.state / "custody-owner-snapshot.json").read_bytes())
        self.assertTrue(self.rt.errors)
        self.assertFalse(self.rt.report["candidateAccepted"])

    def test_noncandidate_delta_retains_all_failure_evidence(self):
        originals = self.complete_retention_fixture()
        after = dict(self.before, status=" M library/noncandidate.kt\n")
        with mock.patch.object(self.rt, "source", return_value=after), \
                mock.patch.object(self.rt, "git", return_value=SimpleNamespace(text=lambda: "library/noncandidate.kt\n")):
            self.rt.retain()
        self.assert_retained_failure_artifacts(originals)
        self.assertEqual(self.rt.report["sourceAfter"], after)

    def test_changed_commit_retains_all_failure_evidence(self):
        originals = self.complete_retention_fixture()
        after = dict(self.before, commit="c" * 40)
        with mock.patch.object(self.rt, "source", return_value=after), \
                mock.patch.object(self.rt, "git", return_value=SimpleNamespace(text=lambda: "")):
            self.rt.retain()
        self.assert_retained_failure_artifacts(originals)
        self.assertEqual(self.rt.report["sourceAfter"], after)

    def test_candidate_copy_failure_still_attempts_remaining_locks_and_retention(self):
        originals = self.complete_retention_fixture()
        missing = self.rt.lockfiles[0]
        (self.root / missing).unlink()
        watched = {self.root / name: name for name in originals}
        attempted = []
        original_read = app.read
        def observe(path, *args, **kwargs):
            if Path(path) in watched:
                attempted.append(watched[Path(path)])
            return original_read(path, *args, **kwargs)
        with mock.patch.object(app, "read", side_effect=observe), \
                mock.patch.object(self.rt, "source", return_value=self.before), \
                mock.patch.object(self.rt, "git", return_value=SimpleNamespace(text=lambda: "")):
            self.rt.retain()
        self.assertEqual(set(attempted), set(originals))
        self.assertEqual(len(attempted), 13)
        self.assert_retained_failure_artifacts(originals, missing=(missing,))

    def test_no_writer_can_never_become_generated_candidate(self):
        self.neutral_finalizers()
        self.rt.finalize()
        self.assertEqual(self.rt.report["finalExitCode"], 125)
        self.assertEqual(self.rt.report["candidateStatus"], "HOLD")
        self.assertIsNone(self.rt.report["writer"])
        self.assertEqual(app.parse(app.read(self.rt.evidence / "result.json")), self.rt.report)

    def test_every_finalizer_still_called_after_prior_finalizer_errors(self):
        names = ("collect_custody", "retire_simulator", "retain", "finish_resource")
        order = []
        for name in names:
            def fail(name=name):
                order.append(name)
                raise ValueError("synthetic " + name + " failure")
            self.use_patch(mock.patch.object(self.rt, name, side_effect=fail))
        self.rt.report["writer"] = {"launchAttempted": True, "waitExitCode": 0}
        self.rt.finalize()
        self.assertEqual(order, list(names))
        self.assertEqual(len(self.rt.errors), len(names))
        self.assertEqual(self.rt.report["candidateStatus"], "HOLD")

    def test_finalizing_ignores_broken_observer_but_normal_work_refuses(self):
        directory = self.state / "observer-error"
        directory.mkdir()
        (directory / "stdout.log").write_bytes(b'not even json\n')
        self.rt.resource = SimpleNamespace(directory=directory, child=None, row={"errors": []})
        self.rt.cancelled.append(15)
        self.rt.check(finalizing=True)
        with self.assertRaises(ValueError):
            self.rt.check()

    def test_success_status_remains_requires_review_never_acceptance(self):
        self.model_product()
        self.neutral_finalizers()
        self.rt.finalize()
        self.assertEqual(self.rt.report["candidateStatus"], "GENERATED_REQUIRES_INDEPENDENT_REVIEW")
        self.assertFalse(self.rt.report["candidateAccepted"])
        self.assertFalse(self.rt.report["releaseGateExecuted"])
        self.assertFalse(self.rt.report["physicalDeviceEvidence"])

    def test_partial_resource_launch_is_retained_for_owned_finalization(self):
        def start(command, finalizing=False):
            command.row["launchAttempted"] = True
            raise OSError("synthetic resource partial launch")
        with mock.patch.object(app.Command, "start", start), self.assertRaises(OSError):
            self.rt.start_resource()
        self.assertIsNotNone(self.rt.resource)
        self.assertTrue(self.rt.resource.row["launchAttempted"])

    def test_resource_stop_file_failure_still_drains_closes_and_retains_original_row(self):
        resource = app.Command(self.rt, "resource-model", ["synthetic-resource-only"])
        with mock.patch.object(app.processes, "make_scope", side_effect=self.model_scope):
            resource.start()
        self.rt.resource = resource
        stop_file = self.state / "resource-stop"
        stop_file.write_bytes(b"existing file must not be overwritten")
        with self.assertRaises(FileExistsError):
            self.rt.finish_resource()
        self.assertTrue(self.scopes[0].closed)
        self.assertTrue(self.scopes[0].drains)
        self.assertIsNone(resource.row["waitExitCode"])
        self.assertIn("resource-final", [row["stage"] for row in resource.row["drains"]])
        self.assertEqual(self.rt.report["resourceRetirement"], self.command_result("resource-model"))
        self.assertEqual(stop_file.read_bytes(), b"existing file must not be overwritten")

    def test_unlaunched_resource_finalization_cannot_start_observer(self):
        resource = app.Command(self.rt, "resource-model", ["synthetic-resource-only"])
        self.rt.resource = resource
        self.rt.finish_resource()
        self.assertFalse(self.scopes)
        self.assertFalse(resource.row["launchAttempted"])
        self.assertIsNone(resource.row["waitExitCode"])
        self.assertEqual(self.rt.report["resourceRetirement"], self.command_result("resource-model"))
        self.assertFalse((self.state / "resource-stop").exists())

    def test_generated_output_map_cannot_escape_fresh_owned_build_roots(self):
        outside = self.base / "outside.api"
        outside.write_bytes(b"not allowed")
        # Use an ABI-named mapped task, not a filename-only approximation.
        write_json(self.rt.evidence / "task-maps/map.jsonl", {"event": "graph", "task": {"path": ":module:abiDump",
                   "outputs": [str(outside)]}})
        with self.assertRaises(ValueError):
            self.rt.retain_generated()
        self.assertEqual(outside.read_bytes(), b"not allowed")
        self.assertFalse((self.rt.evidence / "generated-manifest.json").exists())

    def test_report_retention_error_is_latched_even_if_source_and_generated_copy_succeed(self):
        self.api.retain_reports.side_effect = ValueError("synthetic report-copy failure")
        with mock.patch.object(self.rt, "copy_candidates"), mock.patch.object(self.rt, "source", return_value=self.before), \
                mock.patch.object(self.rt, "git", return_value=SimpleNamespace(text=lambda: "")), \
                mock.patch.object(self.rt, "retain_generated"):
            self.rt.retain()
        self.assertTrue(any(row["stage"] == "report-retention" for row in self.rt.errors))
        self.rt.report["writer"] = {"launchAttempted": True, "waitExitCode": 0}
        self.neutral_finalizers()
        self.rt.finalize()
        self.assertEqual(self.rt.report["candidateStatus"], "HOLD")

    def test_copy_tree_preserves_originals_and_fails_for_links_overflow_or_existing_target(self):
        source = self.base / "copy-source"
        source.mkdir()
        (source / "raw").write_bytes(b"original synthetic bytes")
        target = self.base / "copy-target"
        app.copy_tree(source, target, 128)
        self.assertEqual((source / "raw").read_bytes(), (target / "raw").read_bytes())
        with self.assertRaises(ValueError):
            app.copy_tree(source, target, 128)
        with self.assertRaises(ValueError):
            app.copy_tree(source, self.base / "too-small", 1)
        (source / "link").symlink_to(source / "raw")
        with self.assertRaises(ValueError):
            app.copy_tree(source, self.base / "contains-link", 128)
        self.assertEqual((source / "raw").read_bytes(), b"original synthetic bytes")


class NativeDiscoveryAlgorithmTests(Fixture):
    FOREIGN, OWNED, LATER, WRONG_DOMAIN, REUSED = 2000000001, 2000000002, 2000000003, 2000000004, 2000000005

    def original_baseline_fixture(self):
        context = {"job": JOB, "root": str(self.root), "binding": self.binding,
                   "stateIdentity": app.identity(self.state), "gradleHomeIdentity": app.identity(self.rt.home)}
        write_json(self.state / "context.json", context)
        directory = self.rt.commands / "writer"
        directory.mkdir()
        start = {"job": JOB, "invocation": PRODUCT_ID, "state": str(self.state), "home": str(self.rt.home),
                 "cwd": str(self.root), "argv": ["scripts/prepare-dependency-update.sh", SHA]}
        write_json(directory / "start.json", start)
        world = ProcessWorld(self.state, self.rt.home)
        world.add(self.FOREIGN)
        world.add(self.REUSED)
        original = AlgorithmScope(world, JOB, PRODUCT_ID, str(self.state), str(self.rt.home))
        app.save_baseline(original, directory, start)
        write_json(directory / "launch-attempt.json", {"job": JOB, "invocation": PRODUCT_ID,
                   "argv": start["argv"], "baselineSha256": app.digest(directory / "baseline.json")})
        original.close()
        return context, directory, start, world

    def instant_clock(self):
        ticks = iter(range(100000))
        self.use_patch(mock.patch.object(app.processes.time, "monotonic", side_effect=lambda: next(ticks) / 10))
        self.use_patch(mock.patch.object(app.processes.time, "sleep"))

    def test_original_baseline_recovers_owned_orphan_that_fresh_census_excludes(self):
        context, directory, start, world = self.original_baseline_fixture()
        world.add(self.OWNED, marked=True)
        world.add(self.LATER)  # Not in original baseline, but never owned.
        world.add(self.WRONG_DOMAIN, marked=True, state=str(self.state / "foreign-state"))
        # A foreign PID from the original baseline may now name another lifetime.
        world.add(self.REUSED, generation=2)
        fresh = AlgorithmScope(world, JOB, PRODUCT_ID, str(self.state), str(self.rt.home))
        self.assertEqual(fresh.discover(), [])  # Negative control: later census hides the orphan.
        fresh.close()
        self.instant_clock()
        with mock.patch.object(app.processes, "make_scope", side_effect=lambda *args: AlgorithmScope(world, *args)):
            self.assertTrue(app.quiesce(self.state, context))
        self.assertEqual([pid for pid, key, sig in world.signalled], [self.OWNED])
        self.assertNotIn(self.OWNED, world.identities)
        self.assertEqual(set(world.identities), {self.FOREIGN, self.REUSED, self.LATER, self.WRONG_DOMAIN})
        self.assertTrue(world.released)
        result = app.parse(app.read(self.state / "evidence/seal-quiescence.json"))
        self.assertTrue(result["recoveredUnexpectedWorkers"])
        self.assertTrue(result["candidateHold"])
        self.assertEqual(result["commands"][0]["survivors"], [])

    def test_known_owned_pid_reused_by_unmarked_lifetime_is_never_signalled(self):
        context, directory, start, world = self.original_baseline_fixture()
        world.add(self.OWNED, marked=True)
        self.instant_clock()
        with mock.patch.object(app.processes, "make_scope", side_effect=lambda *args: AlgorithmScope(world, *args)):
            recovered = app.recover_scope(directory, start)
        try:
            self.assertEqual([row["pid"] for row in recovered.discover()], [self.OWNED])
            world.add(self.OWNED, marked=False, generation=2)
            self.assertEqual(recovered.drain(grace=5, kill_wait=5), [])
            self.assertFalse(world.signalled)
            self.assertIn(self.OWNED, world.identities)
            self.assertEqual(world.identities[self.OWNED]["startSeconds"], 102)
        finally:
            recovered.close()
        self.assertTrue(world.released)

    def test_missing_original_baseline_after_launch_blocks_encryption(self):
        context, directory, start, world = self.original_baseline_fixture()
        (directory / "baseline.json").unlink()
        with mock.patch.object(app, "paths", return_value=(self.state, self.base / "upload/encrypted")), \
                mock.patch.object(app.processes, "make_scope") as native, \
                mock.patch.object(app.hosted_evidence, "export_encrypted") as encrypt, self.assertRaises(FileNotFoundError):
            app.seal(self.root, self.binding)
        native.assert_not_called()
        encrypt.assert_not_called()
        self.assertFalse((self.state / "sealed.json").exists())

    def test_valid_lifetime_tamper_of_original_baseline_blocks_encryption(self):
        context, directory, start, world = self.original_baseline_fixture()
        world.add(self.OWNED, marked=True)
        saved = app.parse(app.read(directory / "baseline.json"))
        # Structurally valid, same domain: silently adding this lifetime would
        # hide the orphan unless the durable launch binds original baseline bytes.
        saved["lifetimes"].append(list(app.processes.DarwinScope._key(None, world.identities[self.OWNED])))
        write_json(directory / "baseline.json", saved)
        with mock.patch.object(app, "paths", return_value=(self.state, self.base / "upload/encrypted")), \
                mock.patch.object(app.processes, "make_scope") as native, \
                mock.patch.object(app.hosted_evidence, "export_encrypted") as encrypt, self.assertRaises(ValueError):
            app.seal(self.root, self.binding)
        native.assert_not_called()
        encrypt.assert_not_called()
        self.assertIn(self.OWNED, world.identities)
        self.assertFalse(world.signalled)
        self.assertFalse((self.state / "sealed.json").exists())


class ProducerRetentionTests(Fixture):
    RELATIVE = Path("library/p2p-transport-lan/build/embedded-jmdns/p2pkit-internal-jmdns.jar")
    COMPONENT = "p2pkit:private:synthetic-embedded-jmdns"

    def producer_fixture(self):
        # Arbitrary tiny fixture bytes: source-bound hash retention, not JAR
        # format, compilation, real producer or SBOM generation acceptance.
        self.producer_raw = b"synthetic private producer bytes -- not a compiled JAR\n"
        source = self.root / self.RELATIVE
        source.parent.mkdir(parents=True)
        source.write_bytes(self.producer_raw)
        self.producer_hash = hashlib.sha256(self.producer_raw).hexdigest()
        vendor = "library/p2p-transport-lan/vendor/jmdns"
        self.input_names = ["build.gradle.kts", "library/p2p-transport-lan/build.gradle.kts",
                            vendor + "/PROVENANCE.json", vendor + "/src/main/java/Synthetic.java"]
        for name in self.input_names:
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("// synthetic inventory input only\n")
        write_json(self.root / vendor / "PROVENANCE.json", {"component": {"bomRef": self.COMPONENT}})
        (self.root / "build/reports/cyclonedx").mkdir(parents=True)
        for suffix in ("json", "xml"):
            self.write_sbom(suffix)
        self.rt.report["writer"] = {"waitExitCode": 0}
        self.input_inventory = self.use_patch(mock.patch.object(self.rt, "git", return_value=
                                             SimpleNamespace(text=lambda: "\n".join(self.input_names) + "\n")))
        return source

    def write_sbom(self, suffix, *, count=1, hashes=None):
        hashes = [self.producer_hash] if hashes is None else hashes
        path = self.root / ("build/reports/cyclonedx/bom." + suffix)
        if suffix == "json":
            write_json(path, {"components": [{"bom-ref": self.COMPONENT,
                       "hashes": [{"alg": "SHA-256", "content": value} for value in hashes]} for _ in range(count)]})
        else:
            values = "".join('<hash alg="SHA-256">' + value + "</hash>" for value in hashes)
            component = '<component bom-ref="' + self.COMPONENT + '"><hashes>' + values + "</hashes></component>"
            path.write_text('<bom xmlns="http://cyclonedx.org/schema/bom/1.6"><components>' +
                            component * count + "</components></bom>")

    def case_evidence(self, name):
        self.rt.evidence = self.state / ("producer-case-" + name)
        self.rt.evidence.mkdir(mode=0o700)

    def assert_producer_rejected(self):
        before = len(self.rt.errors)
        self.rt.safely("embedded-jmdns", self.rt.retain_embedded_jmdns)
        self.assertEqual(len(self.rt.errors), before + 1)
        self.assertFalse(self.rt.report["candidateAccepted"])
        self.assertTrue((self.rt.evidence / "embedded-jmdns-manifest.json").is_file())

    def test_exact_producer_bytes_and_both_sbom_hash_matches_are_retained(self):
        source = self.producer_fixture()
        self.rt.retain_embedded_jmdns()
        self.assertEqual((self.rt.evidence / "generated" / self.RELATIVE).read_bytes(), self.producer_raw)
        self.assertEqual(source.read_bytes(), self.producer_raw)
        result = app.parse(app.read(self.rt.evidence / "embedded-jmdns-manifest.json"))
        self.assertEqual(result["status"], "RETAINED")
        self.assertEqual(result["sha256"], self.producer_hash)
        self.assertEqual(result["bytes"], len(self.producer_raw))
        self.assertEqual(result["inputs"], {name: app.digest(self.root / name) for name in self.input_names})
        self.assertEqual([row["status"] for row in result["sbom"]], ["HASH_MATCH", "HASH_MATCH"])
        self.assertEqual([row["sha256"] for row in result["sbom"]],
                         [app.digest(self.root / ("build/reports/cyclonedx/bom." + suffix)) for suffix in ("json", "xml")])
        self.assertFalse(self.rt.report["candidateAccepted"])

    def test_successful_writer_missing_producer_is_failure_not_not_generated_pass(self):
        source = self.producer_fixture()
        source.unlink()
        self.assert_producer_rejected()
        result = app.parse(app.read(self.rt.evidence / "embedded-jmdns-manifest.json"))
        self.assertEqual(result["status"], "NOT_GENERATED")
        self.assertFalse((self.rt.evidence / "generated" / self.RELATIVE).exists())

    def test_failed_writer_missing_producer_is_explicit_not_generated_not_acceptance(self):
        source = self.producer_fixture()
        source.unlink()
        self.rt.report["writer"] = {"waitExitCode": 19}
        self.rt.retain_embedded_jmdns()
        result = app.parse(app.read(self.rt.evidence / "embedded-jmdns-manifest.json"))
        self.assertEqual(result["status"], "NOT_GENERATED")
        self.assertFalse(self.rt.report["candidateAccepted"])

    def test_successful_writer_requires_both_json_and_xml_sboms(self):
        self.producer_fixture()
        for suffix in ("json", "xml"):
            with self.subTest(suffix=suffix):
                self.case_evidence("missing-" + suffix)
                (self.root / ("build/reports/cyclonedx/bom." + suffix)).unlink()
                self.assert_producer_rejected()
                self.assertEqual((self.rt.evidence / "generated" / self.RELATIVE).read_bytes(), self.producer_raw)
                result = app.parse(app.read(self.rt.evidence / "embedded-jmdns-manifest.json"))
                self.assertEqual(result["sbom"][-1]["status"], "NOT_GENERATED")
                self.write_sbom(suffix)

    def test_each_sbom_requires_one_component_and_one_exact_sha256(self):
        self.producer_fixture()
        cases = (("missing-component", 0, [None]), ("duplicate-component", 2, [None]),
                 ("wrong-hash", 1, ["0" * 64]), ("duplicate-hash", 1, [None, None]))
        for suffix in ("json", "xml"):
            for name, count, hashes in cases:
                with self.subTest(suffix=suffix, case=name):
                    self.case_evidence(suffix + "-" + name)
                    self.write_sbom(suffix, count=count, hashes=[self.producer_hash if value is None else value for value in hashes])
                    self.assert_producer_rejected()
                    self.assertEqual((self.rt.evidence / "generated" / self.RELATIVE).read_bytes(), self.producer_raw)
                    self.write_sbom(suffix)

    def test_sbom_xml_declarations_are_rejected_without_acceptance(self):
        self.producer_fixture()
        path = self.root / "build/reports/cyclonedx/bom.xml"
        path.write_bytes(b'<!DOCTYPE bom [<!ENTITY hidden "synthetic">]>' + path.read_bytes())
        self.assert_producer_rejected()
        self.assertEqual((self.rt.evidence / "generated" / self.RELATIVE).read_bytes(), self.producer_raw)


class PublicExportTests(Fixture):
    def setUp(self):
        super().setUp()
        # This suite does not assert fake bytes are encrypted. It exercises the
        # controller calling the real separately-tested ciphertext validator.
        self.shape = self.use_patch(mock.patch.object(app.hosted_evidence, "_ciphertext_shape"))

    def test_accepts_actual_nested_manifest_shape_and_ciphertext_only_directory(self):
        output, manifest = self.public_fixture()
        self.assertEqual(set(manifest), {"schema", "scope", "source", "github", "artifact"})
        self.assertEqual(app.validate_public(self.binding), 0)
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_text(), "artifacts_ready=true\n")
        self.assertEqual({p.name for p in output.iterdir()}, {"manifest.json", "evidence.tar.gz.gpg"})
        self.shape.assert_called_once_with(output / "evidence.tar.gz.gpg", ENCRYPTION_FINGERPRINT)

    def test_no_public_ready_for_wrong_nested_source_run_hash_size_or_shape(self):
        output, original = self.public_fixture()
        cases = (("source", "commit", "c" * 40), ("source", "tree", "c" * 40),
                 ("github", "repository", "other/P2pKit"), ("github", "runId", "456"),
                 ("github", "runAttempt", "2"), ("artifact", "sha256", "0" * 64),
                 ("artifact", "size", 0), ("artifact", "name", "raw.log"))
        for section, key, value in cases:
            manifest = copy.deepcopy(original)
            manifest[section][key] = value
            write_json(output / "manifest.json", manifest)
            self.seal_receipt(output, manifest)
            with self.subTest(section=section, key=key), self.assertRaises(ValueError):
                app.validate_public(self.binding)
            self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())
        manifest = copy.deepcopy(original)
        manifest["privateRawLog"] = "must-not-publish"
        write_json(output / "manifest.json", manifest)
        self.seal_receipt(output, manifest)
        with self.assertRaises(ValueError):
            app.validate_public(self.binding)

    def test_flat_old_schema_is_not_treated_as_the_encryption_contract(self):
        output, _ = self.public_fixture()
        manifest = {"sourceCommit": SHA, "sourceTree": TREE, "runId": "123", "runAttempt": "1",
                    "ciphertextSha256": app.digest(output / "evidence.tar.gz.gpg")}
        write_json(output / "manifest.json", manifest)
        self.seal_receipt(output, manifest)
        with self.assertRaises(ValueError):
            app.validate_public(self.binding)
        self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())

    def test_raw_file_private_key_or_extra_directory_blocks_public_ready(self):
        output, _ = self.public_fixture()
        for name in ("stdout.log", "recipient-private.asc", "evidence.tar.gz"):
            extra = output / name
            extra.write_bytes(b"synthetic never publish")
            with self.subTest(name=name), self.assertRaises(ValueError):
                app.validate_public(self.binding)
            self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())
            extra.unlink()
        (output / "private").mkdir()
        with self.assertRaises(ValueError):
            app.validate_public(self.binding)

    def test_export_parent_and_output_paths_are_private_and_disjoint(self):
        state, output = app.paths(self.binding)
        self.assertEqual(state.parent, self.runner_temp)
        self.assertNotEqual(state, output)
        self.assertNotIn(state, output.parents)
        self.assertNotIn(output, state.parents)
        # hosted_evidence requires a caller-owned private parent, not RUNNER_TEMP.
        self.assertNotEqual(output.parent, self.runner_temp)

    def test_output_permissions_and_ciphertext_links_are_rejected(self):
        output, _ = self.public_fixture()
        output.chmod(0o755)
        with self.assertRaises(ValueError):
            app.validate_public(self.binding)
        output.chmod(0o700)
        artifact = output / "evidence.tar.gz.gpg"
        saved = self.base / "saved-artifact"
        artifact.rename(saved)
        artifact.symlink_to(saved)
        with self.assertRaises(ValueError):
            app.validate_public(self.binding)
        self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())

    def test_missing_or_wrong_private_seal_receipt_never_sets_public_ready(self):
        output, manifest = self.public_fixture()
        state, _ = app.paths(self.binding)
        (state / "sealed.json").unlink()
        with self.assertRaises(FileNotFoundError):
            app.validate_public(self.binding)
        self.seal_receipt(output, manifest)
        original = app.parse(app.read(state / "sealed.json"))
        for field, value in (("recipientFingerprint", "E" * 40), ("manifestSha256", "0" * 64),
                             ("binding", dict(self.binding, runAttempt="2")),
                             ("binding", dict(self.binding, operation=app.INTEL_OPERATION))):
            write_json(state / "sealed.json", dict(original, **{field: value}))
            with self.subTest(field=field), self.assertRaises(ValueError):
                app.validate_public(self.binding)
        self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())
        self.shape.assert_not_called()

    def test_ciphertext_shape_failure_is_not_promoted_by_matching_hash(self):
        self.public_fixture()
        self.shape.side_effect = app.hosted_evidence.EvidenceError("synthetic packet mismatch")
        with self.assertRaises(app.hosted_evidence.EvidenceError):
            app.validate_public(self.binding)
        self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())

    def seal_fixture(self):
        state, output = app.paths(self.binding)
        state.mkdir(mode=0o700)
        (state / "evidence").mkdir(mode=0o700)
        (state / "evidence/commands").mkdir(mode=0o700)
        (state / "gradle-home").mkdir(mode=0o700)
        (state / "recipient.asc").write_text(PUBLIC_KEY)
        write_json(state / "context.json", {"schema": 1, "binding": self.binding, "job": JOB, "root": str(self.root),
                   "stateIdentity": app.identity(state), "gradleHomeIdentity": app.identity(state / "gradle-home")})
        write_json(state / "evidence/result.json", {"candidateStatus": "HOLD", "finalExitCode": 125})
        (state / "evidence/raw.log").write_bytes(b"synthetic private transcript")
        return state, output

    def test_seal_only_calls_encryptor_with_private_evidence_and_exact_identity(self):
        state, output = self.seal_fixture()
        recipient = SimpleNamespace(fingerprint=FINGERPRINT, encryption_fingerprint=ENCRYPTION_FINGERPRINT)
        def export(source, destination, selected, **identities):
            self.assertEqual(source, state / "evidence")
            self.assertEqual(destination, output)
            self.assertIs(selected, recipient)
            self.assertEqual(identities, {"source_commit": SHA, "source_tree": TREE, "run_id": "123", "run_attempt": "1"})
            self.assertFalse(output.exists())
            self.assertEqual(stat.S_IMODE(output.parent.stat().st_mode), 0o700)
            output.mkdir(mode=0o700)
            return self.manifest(output)
        with mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=recipient), \
                mock.patch.object(app.hosted_evidence, "export_encrypted", side_effect=export) as encrypt:
            self.assertEqual(app.seal(self.root, self.binding), 0)
        encrypt.assert_called_once()
        self.assertEqual({p.name for p in output.iterdir()}, {"manifest.json", "evidence.tar.gz.gpg"})
        self.assertEqual((state / "evidence/raw.log").read_bytes(), b"synthetic private transcript")
        self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())

    def test_failed_encryption_never_relabels_evidence_or_sets_public_ready(self):
        state, output = self.seal_fixture()
        with mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=object()), \
                mock.patch.object(app.hosted_evidence, "export_encrypted", side_effect=ValueError("synthetic encryption failure")):
            with self.assertRaises(ValueError):
                app.seal(self.root, self.binding)
        self.assertFalse(output.exists())
        self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())
        self.assertEqual((state / "evidence/raw.log").read_bytes(), b"synthetic private transcript")

    def test_export_cleanup_failure_leaves_no_seal_or_upload_authorization(self):
        state, output = self.seal_fixture()
        recipient = SimpleNamespace(fingerprint=FINGERPRINT, encryption_fingerprint=ENCRYPTION_FINGERPRINT)
        def export_then_cleanup_failure(evidence, destination, selected, **identities):
            destination.mkdir(mode=0o700)
            self.manifest(destination)
            raise OSError("synthetic private archive cleanup failed after output creation")
        with mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=recipient), \
                mock.patch.object(app.hosted_evidence, "export_encrypted", side_effect=export_then_cleanup_failure), \
                self.assertRaises(OSError):
            app.seal(self.root, self.binding)
        self.assertEqual({path.name for path in output.iterdir()}, {"manifest.json", "evidence.tar.gz.gpg"})
        self.assertFalse((state / "sealed.json").exists())
        with self.assertRaises(FileNotFoundError):
            app.validate_public(self.binding)
        self.shape.assert_not_called()
        self.assertFalse(Path(self.env["GITHUB_OUTPUT"]).exists())
        self.assertEqual((state / "evidence/raw.log").read_bytes(), b"synthetic private transcript")

    def test_seal_never_overwrites_existing_owned_export(self):
        state, output = self.seal_fixture()
        output.parent.mkdir(mode=0o700)
        marker = output.parent / "existing-owner"
        marker.write_bytes(b"must remain")
        recipient = SimpleNamespace(fingerprint=FINGERPRINT, encryption_fingerprint=ENCRYPTION_FINGERPRINT)
        with mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=recipient), \
                mock.patch.object(app.hosted_evidence, "export_encrypted") as encrypt, self.assertRaises(FileExistsError):
            app.seal(self.root, self.binding)
        encrypt.assert_not_called()
        self.assertEqual(marker.read_bytes(), b"must remain")
        self.assertEqual((state / "evidence/raw.log").read_bytes(), b"synthetic private transcript")


class RecoveryTests(Fixture):
    def recovery_fixture(self, *, attempted=True):
        state, output = app.paths(self.binding)
        state.mkdir(mode=0o700)
        for name in ("evidence", "evidence/commands", "evidence/commands/writer", "gradle-home", "custody"):
            (state / name).mkdir(mode=0o700)
        (state / "recipient.asc").write_text(PUBLIC_KEY)
        write_json(state / "context.json", {"schema": 1, "binding": self.binding, "job": JOB, "root": str(self.root),
                   "stateIdentity": app.identity(state), "gradleHomeIdentity": app.identity(state / "gradle-home")})
        write_json(state / "evidence/commands/writer/start.json", {"job": JOB, "invocation": PRODUCT_ID,
                   "state": str(state), "home": str(state / "gradle-home"), "cwd": str(self.root),
                   "argv": ["scripts/prepare-dependency-update.sh", SHA], "launchAttempted": False,
                   "waitExitCode": None, "drains": [], "errors": []})
        if attempted:
            start = app.parse(app.read(state / "evidence/commands/writer/start.json"))
            write_json(state / "evidence/commands/writer/baseline.json", {"schema": 1,
                       "backend": "darwin-libproc-audit-token", "domain": app.scope_domain(start), "lifetimes": []})
            write_json(state / "evidence/commands/writer/launch-attempt.json", {"job": JOB, "invocation": PRODUCT_ID,
                       "argv": start["argv"], "baselineSha256": app.digest(state / "evidence/commands/writer/baseline.json")})
        write_json(state / "execution-environment.json", {"binding": self.binding, "job": JOB,
                   "environment": self.env.copy(), "jvmArguments": self.rt.jvm})
        write_json(state / "custody/result.json", {"result": "HOLD", "retirement": "UNKNOWN"})
        return state, output

    def export(self, evidence, output, recipient, **kwargs):
        output.mkdir(mode=0o700)
        return self.manifest(output)

    def complete_recovery_retention(self, stop_code, *, partial_collection=False):
        state, output = self.recovery_fixture()
        lockfiles = ["module" + str(index) + "/gradle.lockfile" for index in range(12)]
        originals = {}
        for name in [*lockfiles, "gradle/verification-metadata.xml"]:
            source = self.root / name
            source.parent.mkdir(parents=True, exist_ok=True)
            originals[name] = ("synthetic retained candidate: " + name + "\n").encode()
            source.write_bytes(originals[name])
        write_json(state / "evidence/before-candidate.json", {"files": [{"path": name, "bytes": len(raw),
                   "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in originals.items()]})
        generated = self.root / "build/generated.api"
        generated.parent.mkdir()
        generated.write_bytes(b"synthetic recovery ABI-shaped bytes, not generated native evidence\n")
        (state / "evidence/task-maps").mkdir()
        write_json(state / "evidence/task-maps/original.jsonl", {"event": "graph",
                   "task": {"path": ":model:abiDump", "outputs": [str(generated)]}})
        self.api.regular_report_files = lambda directory, unused: sorted(path for path in directory.rglob("*") if path.is_file())
        (state / "custody/result.json").unlink()
        (state / "custody/retained").mkdir()
        (state / "custody-attempted").write_bytes(b"attempted\n")
        request = copy.deepcopy(self.rt.custody_request)
        request.update(ownerState=str(state), home=str(state / "gradle-home"))
        write_json(state / "custody/request.json", request)
        custody_bytes = b"synthetic private child transcript preserved by recovery\n"
        (state / "custody/original.log").write_bytes(custody_bytes)
        if partial_collection:
            (state / "custody/retained/earlier-copy.log").write_bytes(b"synthetic one-shot partial original\n")
        original_writer = {"argv": request["command"], "invocation": PRODUCT_ID, "timeoutSeconds": 7200,
                           "launchAttempted": True, "waitExitCode": 143, "errors": ["synthetic interrupted original"],
                           "drains": [], "ownership": {"syntheticOnly": True}}
        write_json(state / "evidence/commands/writer/command.json", original_writer)
        original_writer_bytes = (state / "evidence/commands/writer/command.json").read_bytes()
        stages, snapshots, candidate_reads = [], [], []
        watched = {self.root / name: name for name in originals}
        original_read = app.read
        def read_observer(path, *args, **kwargs):
            if Path(path) in watched:
                candidate_reads.append(watched[Path(path)])
            return original_read(path, *args, **kwargs)
        def wait(scope, child, seconds, cancelled, check, *, stop):
            check()
            if "--stop" in scope.argv:
                stages.append("stop")
                self.assertTrue(stop)
                self.assertEqual(scope.env["GRADLE_USER_HOME"], str(state / "gradle-home"))
                self.assertNotIn(scope.invocation, (PRODUCT_ID, STOP_ID))
                return stop_code
            if "collect" in scope.argv and str(self.root / app.CUSTODY) in scope.argv:
                stages.append("collect")
                self.assertTrue(stop)
                snapshot_path = Path(scope.argv[scope.argv.index("--owner-result") + 1])
                snapshot = app.parse(app.read(snapshot_path))
                snapshots.append(snapshot)
                self.assertEqual(snapshot["writer"], original_writer)
                self.assertEqual(snapshot["stop"], {})
                self.assertEqual(snapshot["sourceBefore"], self.before)
                self.assertEqual(snapshot["scope"], "MUTABLE_FULL_WRITER_NOT_AUDIT_LEAF")
                if not partial_collection:
                    write_json(state / "custody/result.json", {"result": "HOLD", "retirement": "UNKNOWN"})
                return 125  # Model helper's one-shot/HOLD result, never runtime success.
            self.fail("Unexpected model command: " + repr(scope.argv))
        self.api.wait_process = wait
        def reports(root, supplied_state, commands, report, evidence):
            stages.append("reports")
            self.assertEqual(supplied_state, state)
            self.assertEqual(evidence, state / "evidence/recovery")
            app.write(evidence / "report-model-marker", b"synthetic recovered report bytes\n")
        self.api.retain_reports.side_effect = reports
        def git(runtime, label, *args, **kwargs):
            self.assertTrue(kwargs.get("finalizing"))
            self.assertIn(args[0], ("diff", "ls-files"))
            return SimpleNamespace(text=lambda: "")
        recipient = SimpleNamespace(fingerprint=FINGERPRINT, encryption_fingerprint=ENCRYPTION_FINGERPRINT)
        with mock.patch.object(app.processes, "make_scope", side_effect=self.model_scope), \
                mock.patch.object(app.Runtime, "source", return_value=self.before), \
                mock.patch.object(app.Runtime, "git", git), mock.patch.object(app, "read", side_effect=read_observer), \
                mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=recipient), \
                mock.patch.object(app.hosted_evidence, "export_encrypted", side_effect=self.export):
            self.assertEqual(app.seal(self.root, self.binding), 125)
        self.assertEqual(stages, ["stop", "collect", "reports"])
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(set(candidate_reads), set(originals))
        self.assertEqual(len(candidate_reads), 13)
        retained = state / "evidence/recovery"
        for name, raw in originals.items():
            self.assertEqual((retained / "candidate/after" / name).read_bytes(), raw)
            self.assertEqual((self.root / name).read_bytes(), raw)
        self.assertEqual((retained / "report-model-marker").read_bytes(), b"synthetic recovered report bytes\n")
        self.assertEqual((retained / "generated/build/generated.api").read_bytes(), generated.read_bytes())
        generated_manifest = app.parse(app.read(retained / "generated-manifest.json"))
        self.assertIn({"task": ":model:abiDump", "output": str(generated)}, generated_manifest["actualAbiTaskOutputMap"])
        self.assertEqual((retained / "custody/original.log").read_bytes(), custody_bytes)
        self.assertEqual((state / "custody/original.log").read_bytes(), custody_bytes)
        if partial_collection:
            self.assertEqual((retained / "custody/retained/earlier-copy.log").read_bytes(),
                             b"synthetic one-shot partial original\n")
            self.assertFalse((state / "custody/result.json").exists())
        else:
            self.assertEqual(app.parse(app.read(retained / "custody/result.json")), {"result": "HOLD", "retirement": "UNKNOWN"})
        self.assertEqual((state / "evidence/commands/writer/command.json").read_bytes(), original_writer_bytes)
        self.assertFalse((state / "evidence/commands/stop/command.json").exists())
        self.assertFalse((state / "evidence/result.json").exists())
        recovery = app.parse(app.read(state / "evidence/interrupted-owner.json"))
        self.assertEqual(recovery["candidateStatus"], "HOLD")
        self.assertEqual(recovery["finalExitCode"], 125)
        self.assertEqual(recovery["recoveryStop"]["waitExitCode"], stop_code)
        self.assertEqual(recovery["originalWriter"], original_writer)
        self.assertNotIn("originalStop", recovery)
        self.assertTrue(recovery["errors"])
        self.assertFalse(recovery.get("candidateAccepted", False))
        self.assertTrue((state / "evidence/recovery-final-quiescence.json").is_file())
        self.assertTrue((output / "manifest.json").is_file())
        self.assertTrue(all(scope.closed for scope in self.scopes))

    def test_interrupted_recovery_collects_original_custody_and_all_retention(self):
        self.complete_recovery_retention(0)

    def test_failed_recovery_stop_still_collects_original_custody_and_all_retention(self):
        self.complete_recovery_retention(7)

    def test_partial_one_shot_custody_failure_keeps_other_recovery_retention_running(self):
        self.complete_recovery_retention(7, partial_collection=True)

    def test_interrupted_writer_gets_new_same_home_stop_without_reconstructed_acceptance(self):
        state, output = self.recovery_fixture()
        start = (state / "evidence/commands/writer/start.json").read_bytes()
        original_custody = (state / "custody/result.json").read_bytes()
        recipient = SimpleNamespace(fingerprint=FINGERPRINT, encryption_fingerprint=ENCRYPTION_FINGERPRINT)
        with mock.patch.object(app.processes, "make_scope", side_effect=self.model_scope), \
                mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=recipient), \
                mock.patch.object(app.hosted_evidence, "export_encrypted", side_effect=self.export):
            self.assertEqual(app.seal(self.root, self.binding), 125)
        recovery = app.parse(app.read(state / "evidence/interrupted-owner.json"))
        self.assertEqual(recovery["candidateStatus"], "HOLD")
        self.assertEqual(recovery["scope"], "INTERRUPTED_OWNER_RECOVERY_NOT_ACCEPTANCE")
        self.assertEqual(recovery["recoveryStop"]["waitExitCode"], 0)
        self.assertNotIn(recovery["recoveryStop"]["invocation"], (PRODUCT_ID, STOP_ID))
        observed_originals = [scope for scope in self.scopes if scope.invocation == PRODUCT_ID]
        self.assertTrue(observed_originals)
        self.assertTrue(all(not hasattr(scope, "argv") for scope in observed_originals))
        stops = [scope for scope in self.scopes if hasattr(scope, "argv") and "--stop" in scope.argv]
        self.assertEqual(len(stops), 1)
        stop = stops[0]
        self.assertEqual(stop.argv[0:3], [str(self.root / "gradlew"), "--stop", "--console=plain"])
        self.assertEqual(stop.env["GRADLE_USER_HOME"], str(state / "gradle-home"))
        self.assertEqual(stop.env["P2PKIT_AUDIT_STATE_DIR"], str(state))
        self.assertTrue(all(scope.closed for scope in self.scopes))
        self.assertFalse((state / "evidence/result.json").exists())
        self.assertFalse((state / "evidence/commands/writer/command.json").exists())
        snapshot = app.parse(app.read(state / "custody-owner-snapshot.json"))
        self.assertEqual(snapshot["writer"], {})
        self.assertEqual(snapshot["stop"], {})
        self.assertEqual((state / "evidence/commands/writer/start.json").read_bytes(), start)
        self.assertEqual((state / "custody/result.json").read_bytes(), original_custody)
        self.assertEqual((state / "evidence/recovery/custody/result.json").read_bytes(), original_custody)
        self.assertTrue((output / "manifest.json").is_file())

    def test_interrupted_before_launch_does_not_invent_writer_or_stop(self):
        state, _ = self.recovery_fixture(attempted=False)
        recipient = SimpleNamespace(fingerprint=FINGERPRINT, encryption_fingerprint=ENCRYPTION_FINGERPRINT)
        with mock.patch.object(app.processes, "make_scope", side_effect=self.model_scope), \
                mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=recipient), \
                mock.patch.object(app.hosted_evidence, "export_encrypted", side_effect=self.export):
            self.assertEqual(app.seal(self.root, self.binding), 125)
        recovery = app.parse(app.read(state / "evidence/interrupted-owner.json"))
        self.assertNotIn("recoveryStop", recovery)
        self.assertEqual(recovery["candidateStatus"], "HOLD")
        self.assertFalse(any(hasattr(scope, "argv") and ("--stop" in scope.argv or
                             "scripts/prepare-dependency-update.sh" in scope.argv) for scope in self.scopes))
        self.assertFalse((state / "evidence/result.json").exists())

    def test_recovery_owner_mismatch_fails_before_native_ownership_or_export(self):
        state, _ = self.recovery_fixture()
        start_path = state / "evidence/commands/writer/start.json"
        start = app.parse(app.read(start_path))
        start["home"] = str(self.home)
        write_json(start_path, start)
        with mock.patch.object(app.processes, "make_scope") as scope, \
                mock.patch.object(app.hosted_evidence, "export_encrypted") as encrypt, self.assertRaises(ValueError):
            app.seal(self.root, self.binding)
        scope.assert_not_called()
        encrypt.assert_not_called()

    def test_changed_context_profile_blocks_seal_before_native_recovery_or_export(self):
        state, _ = self.recovery_fixture()
        context = app.parse(app.read(state / "context.json"))
        context["binding"]["operation"] = app.INTEL_OPERATION
        write_json(state / "context.json", context)
        with mock.patch.object(app, "quiesce") as quiesce, \
                mock.patch.object(app, "recover_interrupted") as recover, \
                mock.patch.object(app.hosted_evidence, "export_encrypted") as encrypt, self.assertRaises(ValueError):
            app.seal(self.root, self.binding)
        quiesce.assert_not_called()
        recover.assert_not_called()
        encrypt.assert_not_called()
        self.assertFalse((state / "sealed.json").exists())

    def test_changed_saved_profile_blocks_recovery_stop_but_preserves_finalization_hold(self):
        state, _ = self.recovery_fixture()
        path = state / "execution-environment.json"
        saved = app.parse(app.read(path))
        saved["binding"]["operation"] = app.INTEL_OPERATION
        write_json(path, saved)
        original = path.read_bytes()
        context = app.parse(app.read(state / "context.json"))
        lock_map = "\n".join(f"module{i}/gradle.lockfile" for i in range(12)) + "\n"
        with mock.patch.object(app.Runtime, "git", return_value=SimpleNamespace(text=lambda: lock_map)), \
                mock.patch.object(app.Runtime, "collect_custody") as collect, \
                mock.patch.object(app.Runtime, "retain") as retain, mock.patch.object(app, "Command") as command, \
                mock.patch.object(app, "quiesce") as quiesce:
            app.recover_interrupted(self.root, state, self.binding, context)
        command.assert_not_called()
        collect.assert_called_once_with()
        retain.assert_called_once_with()
        quiesce.assert_called_once_with(state, context, "recovery-final-quiescence")
        result = app.parse(app.read(state / "evidence/interrupted-owner.json"))
        self.assertEqual(result["candidateStatus"], "HOLD")
        self.assertEqual(result["finalExitCode"], 125)
        self.assertNotIn("recoveryStop", result)
        self.assertTrue(any(row["stage"] == "recovery-stop" and row["message"] == "recovery execution binding differs"
                            for row in result["errors"]))
        self.assertEqual(path.read_bytes(), original)

    def test_replaced_gradle_home_rejected_before_recovery_or_export(self):
        state, _ = self.recovery_fixture()
        # Retain the old inode rather than letting the filesystem reuse it.
        (state / "gradle-home").rename(state / "old-gradle-home")
        (state / "gradle-home").mkdir(mode=0o700)
        with mock.patch.object(app.processes, "make_scope") as scope, \
                mock.patch.object(app.hosted_evidence, "export_encrypted") as encrypt, self.assertRaises(ValueError):
            app.seal(self.root, self.binding)
        scope.assert_not_called()
        encrypt.assert_not_called()

    def test_quiescence_unknown_native_retirement_blocks_sealing(self):
        state, _ = self.recovery_fixture()
        context = app.parse(app.read(state / "context.json"))
        scope = ModelScope(self, JOB, PRODUCT_ID, str(state), str(state / "gradle-home"))
        scope.discover = lambda: ["synthetic-live-marker-owner"]
        scope.drain = lambda **kwargs: ["synthetic-still-live"]
        with mock.patch.object(app.processes, "make_scope", return_value=scope), self.assertRaises(ValueError):
            app.quiesce(state, context)
        self.assertTrue(scope.closed)
        self.assertFalse((state / "evidence/seal-quiescence.json").exists())

    def test_terminal_report_does_not_replace_fresh_native_quiescence(self):
        state, output = self.recovery_fixture()
        original = {"candidateStatus": "HOLD", "finalExitCode": 125, "writer": {"waitExitCode": None}}
        write_json(state / "evidence/result.json", original)
        raw = (state / "evidence/result.json").read_bytes()
        scope = ModelScope(self, JOB, PRODUCT_ID, str(state), str(state / "gradle-home"))
        scope.discover = lambda: ["synthetic-unexpected-worker"]
        recipient = SimpleNamespace(fingerprint=FINGERPRINT, encryption_fingerprint=ENCRYPTION_FINGERPRINT)
        with mock.patch.object(app.processes, "make_scope", return_value=scope), \
                mock.patch.object(app.hosted_evidence, "validate_recipient", return_value=recipient), \
                mock.patch.object(app.hosted_evidence, "export_encrypted", side_effect=self.export):
            self.assertEqual(app.seal(self.root, self.binding), 125)
        self.assertTrue(scope.closed)
        self.assertTrue(scope.drains)
        quiescence = app.parse(app.read(state / "evidence/seal-quiescence.json"))
        self.assertTrue(quiescence["candidateHold"])
        self.assertTrue(quiescence["recoveredUnexpectedWorkers"])
        self.assertEqual((state / "evidence/result.json").read_bytes(), raw)
        self.assertTrue((output / "manifest.json").is_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
