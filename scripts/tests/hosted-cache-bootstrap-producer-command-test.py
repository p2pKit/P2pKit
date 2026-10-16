#!/usr/bin/env python3
"""Data-only descriptor controls, NOT canonical, native or hosted execution.

Actual ordinary-UID tiny POSIX source reads and fixed-helper assembly; admission,
context and changed-supplier conditions are synthetic. No old suite is inherited.
The generated loader/command is inspected, never executed or given an environment.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack, contextmanager
import copy
import ctypes
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS.parent
NAMES = ("audit_processes.py", "run-audit-command.py")
HELPER = "hosted_canonical_python.py"
HELPER_SHA256 = "432c06f0be8f98db286979b7adc58365d9eafde739c023ac13af1f227acaeba4"
LOADER_SHA256 = "b6d6ec850d03fa6ecc5df4d096813df568514aa442c049520120dd9ea929045d"
COMMAND = ["help", "--console=plain", "--no-configure-on-demand"]


@contextmanager
def no_execution():
    with ExitStack() as stack:
        for module, names in (
            (subprocess, ("Popen", "run", "call", "check_call", "check_output")),
            (os, ("system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp",
                  "execl", "execle", "execlp", "execlpe", "execv", "execve", "execvp", "execvpe")),
            (ctypes, ("CDLL", "PyDLL", "WinDLL")),
            (socket, ("socket", "create_connection", "getaddrinfo")),
            (http.client, ("HTTPConnection", "HTTPSConnection")),
            (ssl, ("create_default_context",)),
            (time, ("time", "time_ns", "monotonic", "monotonic_ns", "perf_counter",
                    "perf_counter_ns", "clock_gettime", "clock_gettime_ns", "sleep")),
        ):
            for name in names:
                stack.enter_context(patch.object(module, name,
                    side_effect=AssertionError("PROCESS_NETWORK_NATIVE_OR_CLOCK_FORBIDDEN"), create=True))
        yield


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class CommandModels(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not hasattr(os, "geteuid") or os.geteuid() == 0:
            raise AssertionError("actual ordinary UID required for these POSIX controls")
        if (sys.flags.isolated, sys.flags.no_site, sys.dont_write_bytecode) != (1, 1, True):
            raise AssertionError("run isolated Python -I -B -S")
        sys.path.insert(0, str(SCRIPTS))
        with no_execution():
            cls.M = load("bootstrap_producer_command_models", SCRIPTS / "hosted_cache_bootstrap_producer_command.py")
            cls.I = load("bootstrap_command_identity_fixtures", SCRIPTS / "tests/hosted-cache-bootstrap-identity-test.py")
        cls.P, cls.C = cls.M.producer, cls.M.canonical
        forbidden = (str(SCRIPTS / "run-hosted-test-custody.py"), str(SCRIPTS / "run-audit-command.py"),
                     str(SCRIPTS / "run-hosted-cache-bootstrap.py"))
        if any(getattr(value, "__file__", None) in forbidden for value in sys.modules.values() if value is not None):
            raise AssertionError("a descriptor imported a controller or canonical executor")

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(no_execution())
        for name in ("host_role", "make_scope", "ownership_environment"):
            self.stack.enter_context(patch.object(self.I.Q.processes, name,
                side_effect=AssertionError("NATIVE_OR_DOMAIN_SYNTHESIS_FORBIDDEN")))
        self.stack.enter_context(patch.object(self.C, "init_request",
            side_effect=AssertionError("INITIALIZER_REQUEST_FORBIDDEN")))
        self.temp = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="p2pkit-command-model-")))
        self.ancestors = ["c" * 32]
        self.invocation = "b" * 32
        self.configure("desktop-linux-x64", "Linux", "X64", "linux-x64")

    def configure(self, selection, system, arch, role):
        # Reuse only pure builders, never an old test class, setUp or test result.
        env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit",
               "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
               "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": system, "RUNNER_ARCH": arch,
               "GITHUB_JOB": "populate", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
               "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/work/fixture",
               "GITHUB_SHA": self.I.SOURCE, "GITHUB_WORKFLOW_SHA": self.I.SOURCE,
               "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/.github/workflows/dependency-cache-bootstrap.yml@refs/heads/work/fixture"}
        event = {"repository": {"full_name": "p2pKit/P2pKit", "default_branch": "main"}, "ref": "work/fixture",
                 "inputs": {"selection": selection, "expected_sha": self.I.SOURCE, "expected_tree": self.I.TREE}}
        self.admitted = self.I.B._admit(env, self.I.H.encoded(event), self.I.ModelGit(), self.I.NOW).record
        self.context = {"schema": 1, "root": str(ROOT), "expectedCommit": self.I.SOURCE, "tree": self.I.TREE,
            "source": {"commit": self.I.SOURCE, "tree": self.I.TREE, "status": "", "diffSha256": self.P.digest(b"")},
            "host": role, "gradleHome": str(self.temp / "state/gradle-home"),
            "createdUtc": "2026-09-18T00:00:00+00:00", "id": "a" * 32,
            "gradlePropertiesSha256": "d" * 64, "javaHomes": [], "preexistingOutputPaths": []}

    def descriptor(self, **changes):
        args = {"admitted_raw": self.admitted, "canonical_raw": self.P.encoded(self.context),
                "invocation": self.invocation, "ancestor_invocations": self.ancestors}
        args.update(changes)
        return self.M.command_request(**args)

    @contextmanager
    def source_fixture(self):
        root = self.temp / "repository"
        scripts = root / "scripts"
        scripts.mkdir(parents=True)
        for name in (HELPER, *NAMES):
            (scripts / name).write_bytes((SCRIPTS / name).read_bytes())
        with patch.object(self.M, "ROOT", root), patch.object(self.M, "SCRIPTS", scripts), \
                patch.object(self.C, "ROOT", root), patch.object(self.C, "SCRIPTS", scripts), \
                patch.dict(self.context, root=str(root)):
            yield root, scripts

    def test_fixed_runtime_argv_and_exact_two_supplier_loader(self):
        raw = self.descriptor()
        result = json.loads(raw)
        self.assertIs(type(raw), bytes)
        self.assertEqual(self.P.encoded(result), raw)
        self.assertEqual(result["scope"], "BOOTSTRAP_CANONICAL_PRODUCER_COMMAND_REQUEST_ONLY_V1")
        self.assertEqual(result["python"], str(Path(sys.executable).resolve(strict=True)))
        argv = result["argv"]
        self.assertEqual(argv[:5], [result["python"], "-I", "-B", "-S", "-c"])
        self.assertEqual(hashlib.sha256(argv[5].encode()).hexdigest(), LOADER_SHA256)
        self.assertEqual(argv[6], str(SCRIPTS))
        self.assertEqual(json.loads(argv[7]), result["canonicalSources"])
        self.assertEqual(set(result["canonicalSources"]), set(NAMES))
        self.assertEqual(result["canonicalSources"], {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest()
                                                    for name in NAMES})
        self.assertEqual(result["helperSourceSha256"], HELPER_SHA256)
        self.assertEqual(argv[8:], ["--cwd", str(ROOT), "--wrapper", str(ROOT / "gradlew"),
            "--purpose", "cache-bootstrap-configuration", "--kind", "gradle", "--id", "b" * 32,
            "--timeout", "600", "--stop-timeout", "120", "--", *COMMAND])

    def test_runtime_suffix_matches_actual_passively_parsed_canonical_grammar(self):
        tree = ast.parse((SCRIPTS / "run-audit-command.py").read_bytes())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        calls = [n for n in ast.walk(main) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                 and n.func.attr == "add_argument"]
        self.assertEqual({ast.literal_eval(n.args[0]) for n in calls},
                         {"--cwd", "--wrapper", "--purpose", "--kind", "--receipt", "--id",
                          "--timeout", "--stop-timeout", "argv"})
        suffix = json.loads(self.descriptor())["argv"][8:]
        self.assertEqual(suffix[0], "--cwd")
        self.assertNotIn("--state", suffix)
        self.assertNotIn("--receipt", suffix)
        self.assertNotIn("init", suffix)
        self.assertNotIn("run", suffix)
        self.assertEqual(suffix[suffix.index("--") + 1:], COMMAND)
        self.assertFalse(set(self.P.ENFORCED).intersection(suffix))

    def test_request_is_existing_detached_producer_bytes_not_a_second_validator(self):
        context_raw = json.dumps(self.context, indent=2).encode("ascii")
        expected = self.P.encoded(self.P.make_request(self.admitted, context_raw,
            invocation=self.invocation, ancestor_invocations=self.ancestors))
        with patch.object(self.P, "make_request", wraps=self.P.make_request) as maker:
            result = json.loads(self.descriptor(canonical_raw=context_raw))
        self.assertEqual(maker.call_count, 1)
        self.assertIs(maker.call_args.kwargs["ancestor_invocations"], self.ancestors)
        self.assertEqual(result["requestBytes"].encode("ascii"), expected)
        self.assertEqual(result["requestSha256"], hashlib.sha256(expected).hexdigest())
        self.assertEqual(result["admissionSha256"], hashlib.sha256(self.admitted).hexdigest())
        self.assertEqual(result["canonicalContextSha256"], hashlib.sha256(context_raw).hexdigest())
        self.assertNotEqual(result["canonicalContextSha256"], hashlib.sha256(self.P.encoded(self.context)).hexdigest())

    def test_supplied_posix_role_labels_do_not_become_host_acceptance(self):
        for selection, system, arch, role in (
            ("desktop-linux-x64", "Linux", "X64", "linux-x64"),
            ("desktop-macos-arm64", "macOS", "ARM64", "macos-arm64"),
            ("desktop-macos-x64", "macOS", "X64", "macos-x64"),
            ("full-macos-arm64", "macOS", "ARM64", "macos-arm64"),
            ("full-macos-x64", "macOS", "X64", "macos-x64"),
        ):
            self.configure(selection, system, arch, role)
            result = json.loads(self.descriptor())
            with self.subTest(selection=selection):
                self.assertEqual(result["role"], role)
                self.assertEqual(result["hostAdmission"], "NOT_ATTESTED_HERE")
                self.assertEqual(json.loads(result["requestBytes"])["selection"], selection)
                self.assertEqual(result["argv"][-3:], COMMAND)

    def test_windows_context_cannot_be_relabelled_as_the_actual_posix_source_root(self):
        self.configure("desktop-windows-x64", "Windows", "X64", "windows-x64")
        self.context.update(root=r"D:\a\P2pKit\P2pKit", gradleHome=r"D:\a\_temp\state\gradle-home")
        with patch.object(self.C, "_interpreter") as supplier, \
                self.assertRaisesRegex(self.M.CommandError, "SOURCE_ROOT"):
            self.descriptor()
        supplier.assert_not_called()

    def test_no_environment_domains_recipient_or_execution_authority(self):
        values = {"GH_TOKEN": "synthetic-token-never-copy", "ACTIONS_RUNTIME_TOKEN": "synthetic-runtime-never-copy",
                  "JAVA_HOME": "synthetic-home-never-copy", "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": "synthetic-domain-never-copy"}
        with patch.dict(os.environ, values, clear=True):
            raw = self.descriptor()
        for value in values.values():
            self.assertNotIn(value.encode(), raw)
        self.assertNotIn(self.I.KEY, raw)
        result = json.loads(raw)
        expected = {"environment": "NOT_BUILT_OR_ADMITTED", "sourceAdmission": "NOT_ATTESTED_HERE",
            "hostAdmission": "NOT_ATTESTED_HERE", "stateOwnership": "NOT_ACQUIRED_OR_ATTESTED",
            "recipientAuthority": "NOT_ATTESTED_HERE", "originalDomainChain": "NOT_OBSERVED_HERE",
            "producerStopRetirement": "NOT_OBSERVED_HERE", "custodyAcceptance": "NOT_OBSERVED_HERE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED"}
        self.assertEqual({name: result[name] for name in expected}, expected)
        self.assertIs(result["nextPhaseAuthority"], False)
        self.assertIs(result["exportSaveAuthority"], False)
        self.assertEqual(result["interpreterObservation"],
                         "CURRENT_PATH_AND_METADATA_NOT_EXECUTABLE_BYTE_AUTHENTICATION")

    def test_repeated_bytes_are_repeatable_data_not_single_use_or_created_state(self):
        first, second = self.descriptor(), self.descriptor()
        self.assertEqual(first, second)
        result = json.loads(first)
        self.assertEqual(result["state"], str(self.temp / "state"))
        self.assertFalse((self.temp / "state").exists())
        self.assertFalse(result["nextPhaseAuthority"])

    def test_existing_state_is_not_read_modified_adopted_or_owned(self):
        state = self.temp / "state"
        state.mkdir()
        marker = state / "marker"
        marker.write_bytes(b"existing state must remain untouched")
        before = marker.stat()
        original_stat, original_open = Path.stat, os.open
        def stat_path(path, *args, **kwargs):
            if path == state or state in path.parents:
                raise AssertionError("STATE_READ_FORBIDDEN")
            return original_stat(path, *args, **kwargs)
        def open_path(path, *args, **kwargs):
            if Path(path) == state or state in Path(path).parents:
                raise AssertionError("STATE_OPEN_FORBIDDEN")
            return original_open(path, *args, **kwargs)
        with patch.object(Path, "stat", stat_path), patch.object(os, "open", open_path):
            result = json.loads(self.descriptor())
        self.assertEqual(marker.stat(), before)
        self.assertEqual(marker.read_bytes(), b"existing state must remain untouched")
        self.assertEqual(list(state.iterdir()), [marker])
        self.assertEqual(result["stateOwnership"], "NOT_ACQUIRED_OR_ATTESTED")

    def test_exact_bytes_reject_mutable_inputs_and_bytes_subclasses_before_suppliers(self):
        class Bytes(bytes):
            pass
        for name, original in (("admitted_raw", self.admitted), ("canonical_raw", self.P.encoded(self.context))):
            for value in (bytearray(original), memoryview(original), Bytes(original), original.decode("ascii"), None):
                with self.subTest(name=name, kind=type(value).__name__), patch.object(self.C, "_interpreter") as supplier, \
                        self.assertRaisesRegex(self.M.CommandError, "ORIGINAL_BYTES"):
                    self.descriptor(**{name: value})
                supplier.assert_not_called()

    def test_existing_request_refusals_precede_source_suppliers(self):
        changes = ({"host": "macos-arm64"}, {"expectedCommit": "f" * 40}, {"tree": "f" * 40},
                   {"source": {**self.context["source"], "status": " M changed"}},
                   {"gradleHome": str(ROOT / "state/gradle-home")}, {"gradleHome": "/relative/../gradle-home"},
                   {"root": str(self.temp / "other-source")})
        for change in changes:
            with self.subTest(change=change), patch.object(self.C, "_interpreter") as supplier, \
                    self.assertRaises((self.P.ProducerError, self.M.CommandError)):
                self.descriptor(canonical_raw=self.P.encoded({**self.context, **change}))
            supplier.assert_not_called()

    def test_ordinary_or_mislabelled_admission_never_selects_bootstrap(self):
        admitted = json.loads(self.admitted)
        for change in ({"profile": "desktop"}, {"profile": "full"}, {"producerCommand": ["check"]},
                       {"cacheCohort": {"profile": "full", "role": "macos-arm64"}},
                       {"testAcceptance": "PASS"}, {"scope": "ORDINARY"}):
            with self.subTest(change=change), patch.object(self.C, "_interpreter") as supplier, \
                    self.assertRaisesRegex(self.P.ProducerError, "ADMISSION"):
                self.descriptor(admitted_raw=self.P.encoded({**admitted, **change}))
            supplier.assert_not_called()

    def test_invalid_invocation_and_ancestors_are_not_coerced(self):
        class List(list):
            pass
        class Tuple(tuple):
            pass
        values = ([], ["c" * 32, "c" * 32], ["b" * 32], [None], ["A" * 32],
                  [format(i, "032x") for i in range(32)], List(self.ancestors), Tuple(self.ancestors),
                  iter(self.ancestors), set(self.ancestors), "c" * 32)
        for value in values:
            with self.subTest(kind=type(value).__name__), patch.object(self.C, "_interpreter") as supplier, \
                    self.assertRaises(self.P.ProducerError):
                self.descriptor(ancestor_invocations=value)
            supplier.assert_not_called()
        for value in (None, True, "b" * 31, "B" * 32):
            with self.subTest(invocation=value), self.assertRaises(self.P.ProducerError):
                self.descriptor(invocation=value)

    def test_exact_tuple_ancestors_remain_data_not_effective_domains(self):
        ancestors = ("c" * 32, "d" * 32)
        result = json.loads(self.descriptor(ancestor_invocations=ancestors))
        self.assertEqual(result["ancestorInvocationIds"], list(ancestors))
        self.assertEqual(json.loads(result["requestBytes"])["ancestorInvocationIds"], list(ancestors))
        self.assertEqual(result["originalDomainChain"], "NOT_OBSERVED_HERE")

    def test_ancestor_container_is_detached_before_first_source_supplier(self):
        original = self.C._interpreter
        calls = []
        def interpreter():
            calls.append(True)
            self.ancestors[:] = ["d" * 32]
            return original()
        with patch.object(self.C, "_interpreter", interpreter):
            result = json.loads(self.descriptor())
        self.assertEqual(calls, [True, True])
        self.assertEqual(self.ancestors, ["d" * 32])
        self.assertEqual(result["ancestorInvocationIds"], ["c" * 32])
        self.assertEqual(json.loads(result["requestBytes"])["ancestorInvocationIds"], ["c" * 32])

    def test_no_root_interpreter_command_profile_recipient_environment_or_timeout_override(self):
        for name in ("root", "scripts", "executable", "interpreter", "command", "argv", "profile", "selection",
                     "recipient", "environment", "env", "domains", "timeout", "stop_timeout", "receipt", "state",
                     "bindings", "budget", "job_end", "allocation"):
            with self.subTest(name=name), patch.object(self.C, "_interpreter") as supplier, self.assertRaises(TypeError):
                self.descriptor(**{name: "not-authority"})
            supplier.assert_not_called()

    def test_isolation_refusal_precedes_request_and_source_suppliers(self):
        for isolated, no_site, no_bytecode in ((0, 1, True), (1, 0, True), (1, 1, False)):
            with self.subTest(flags=(isolated, no_site, no_bytecode)), \
                    patch.object(sys, "flags", SimpleNamespace(isolated=isolated, no_site=no_site)), \
                    patch.object(sys, "dont_write_bytecode", no_bytecode), \
                    patch.object(self.P, "make_request") as maker, patch.object(self.C, "_interpreter") as supplier, \
                    self.assertRaisesRegex(self.M.CommandError, "ISOLATION"):
                self.descriptor()
            maker.assert_not_called()
            supplier.assert_not_called()

    def test_initial_root_scripts_disagreement_refuses_before_suppliers(self):
        for module, name, value in ((self.M, "ROOT", self.temp), (self.M, "SCRIPTS", self.temp),
                                    (self.C, "ROOT", self.temp), (self.C, "SCRIPTS", self.temp)):
            with self.subTest(module=module.__name__, name=name), patch.object(module, name, value), \
                    patch.object(self.C, "_interpreter") as supplier, \
                    self.assertRaisesRegex(self.M.CommandError, "LOCATION"):
                self.descriptor()
            supplier.assert_not_called()

    def test_location_rechecks_use_originals_captured_before_interpreter(self):
        with self.source_fixture():
            alternate = self.temp / "alternate/scripts"
            alternate.mkdir(parents=True)
            for name in (HELPER, *NAMES):
                (alternate / name).write_bytes((SCRIPTS / name).read_bytes())
            original = self.C._interpreter
            for module, name, value in ((self.M, "ROOT", alternate.parent), (self.M, "SCRIPTS", alternate),
                                        (self.C, "ROOT", alternate.parent), (self.C, "SCRIPTS", alternate)):
                old = getattr(module, name)
                def interpreter():
                    setattr(module, name, value)
                    return original()
                with self.subTest(module=module.__name__, name=name), patch.object(module, name, old), \
                        patch.object(self.C, "_interpreter", interpreter), \
                        self.assertRaisesRegex(self.M.CommandError, "LOCATION_CHANGED"):
                    self.descriptor()

    def test_first_interpreter_failure_identity_prevents_later_suppliers(self):
        class FalseError(RuntimeError):
            def __bool__(self):
                return False
        for first in (FalseError("synthetic-first"), KeyboardInterrupt("synthetic-cancel")):
            with self.subTest(error=type(first).__name__), patch.object(self.C, "_interpreter", side_effect=first), \
                    patch.object(self.C, "_load_canonical_helper") as helper, \
                    self.assertRaises(type(first)) as caught:
                self.descriptor()
            self.assertIs(caught.exception, first)
            helper.assert_not_called()

    def test_first_helper_or_child_supplier_failure_is_not_replaced_or_retried(self):
        original = self.C._canonical_source
        for selected in (HELPER, *NAMES):
            for first in (OSError("synthetic-read"), KeyboardInterrupt("synthetic-cancel")):
                calls = []
                def source(name, limit):
                    calls.append(name)
                    if name == selected:
                        raise first
                    return original(name, limit)
                with self.subTest(selected=selected, error=type(first).__name__), \
                        patch.object(self.C, "_canonical_source", source), \
                        self.assertRaises(type(first)) as caught:
                    self.descriptor()
                self.assertIs(caught.exception, first)
                self.assertEqual(calls, list((HELPER, *NAMES)[:(HELPER, *NAMES).index(selected) + 1]))

    def test_both_source_originals_are_rechecked_before_return(self):
        original = self.C._canonical_source
        for selected in NAMES:
            seen = []
            def source(name, limit):
                raw = original(name, limit)
                if name == selected:
                    seen.append(name)
                    if len(seen) == 2:
                        return raw + b"\n# modeled changed source\n"
                return raw
            with self.subTest(selected=selected), patch.object(self.C, "_canonical_source", source), \
                    self.assertRaisesRegex(self.M.CommandError, "SOURCE_CHANGED"):
                self.descriptor()
            self.assertEqual(seen, [selected, selected])

    def test_final_helper_hash_and_interpreter_metadata_changes_refuse(self):
        original = self.C._canonical_source
        seen = []
        def source(name, limit):
            raw = original(name, limit)
            if name == HELPER:
                seen.append(name)
                if len(seen) == 2:
                    return raw + b"\n# modeled changed helper\n"
            return raw
        with patch.object(self.C, "_canonical_source", source), \
                self.assertRaisesRegex(self.M.CommandError, "BINDING_CHANGED"):
            self.descriptor()
        before = self.C._interpreter()
        for index in range(len(before)):
            after = list(before)
            after[index] = str(after[index]) + "-changed" if isinstance(after[index], str) else after[index] + 1
            with self.subTest(index=index), patch.object(self.C, "_interpreter", side_effect=[before, tuple(after)]), \
                    self.assertRaisesRegex(self.M.CommandError, "BINDING_CHANGED"):
                self.descriptor()

    def test_real_changed_helper_bytes_refuse_without_executing_them(self):
        with self.source_fixture() as (_root, scripts):
            (scripts / HELPER).write_bytes(b'raise AssertionError("UNTRUSTED_HELPER_EXECUTED")\n')
            with self.assertRaisesRegex(self.C.CanonicalError, "SOURCE_BINDING"):
                self.descriptor()

    def test_real_missing_source_cannot_fall_back_to_an_ambient_module(self):
        with self.source_fixture() as (_root, scripts):
            (scripts / NAMES[0]).unlink()
            with patch.dict(sys.modules, {"audit_processes": SimpleNamespace()}), self.assertRaises(FileNotFoundError):
                self.descriptor()

    def test_real_source_symlink_and_hardlink_are_rejected_by_the_existing_reader(self):
        with self.source_fixture() as (_root, scripts):
            path = scripts / NAMES[0]
            raw = path.read_bytes()
            other = scripts / "other.py"
            other.write_bytes(raw)
            path.unlink()
            path.symlink_to(other)
            with self.assertRaisesRegex(self.C.CanonicalError, "HELPER_SOURCE"):
                self.descriptor()
            path.unlink()
            os.link(other, path)
            with self.assertRaisesRegex(self.C.CanonicalError, "HELPER_SOURCE"):
                self.descriptor()

    def test_proposed_bounds_keep_stop_inside_return_and_read_outside_capture(self):
        value = json.loads(self.descriptor())["timingProposal"]
        self.assertEqual(value["scope"], "FIXED_SOURCE_PROPOSAL_NOT_LIVE_DEADLINES")
        self.assertEqual(value["phases"], [{"name": name, "maximumSeconds": seconds} for name, seconds in
            (("producer-work", 600), ("producer-return", 225), ("producer-final", 45), ("producer-read", 30))])
        self.assertEqual(value["producerReturn"], {"seconds": 225, "sameHomeStopSeconds": 120,
            "sameHomeStopIncluded": True, "scope": "STOP_AND_CANONICAL_TAIL_SHARE_ORIGINAL_RETURN_CAP"})
        self.assertEqual(value["nativeCapture"], {"name": "producer",
            "phases": ["producer-work", "producer-return", "producer-final"], "maximumSeconds": 870})
        self.assertEqual(value["windowsNativeFileSeconds"], 900)
        self.assertEqual(value["proposedJobSeconds"], 5400)
        self.assertEqual(value["deadlineEnforcement"], "NOT_PERFORMED_HERE_OR_BY_FLAGS_ALONE")
        self.assertEqual(value["parentObligation"], "SHORTEN_AGAINST_ORIGINAL_SHARED_CLOCK_JOB_PHASE_AND_CAPTURE_FENCES")

    def test_changed_phase_caps_order_or_capture_membership_refuse_before_suppliers(self):
        original = self.M.allocation.policy()
        changes = []
        for name in ("producer-work", "producer-return", "producer-final", "producer-read"):
            value = copy.deepcopy(original)
            next(row for row in value["phases"] if row["name"] == name)["maximumSeconds"] += 1
            changes.append(value)
        for member in ("maximumSeconds", "phases"):
            value = copy.deepcopy(original)
            row = next(row for row in value["nativeCaptureSpans"] if row["name"] == "producer")
            row[member] = 990 if member == "maximumSeconds" else [*row[member], "producer-read"]
            changes.append(value)
        value = copy.deepcopy(original)
        start = next(i for i, row in enumerate(value["phases"]) if row["name"] == "producer-work")
        value["phases"][start], value["phases"][start + 1] = value["phases"][start + 1], value["phases"][start]
        changes.append(value)
        value = copy.deepcopy(original)
        value["phases"].insert(start + 1, {"name": "foreign-phase", "maximumSeconds": 1})
        changes.append(value)
        value = copy.deepcopy(original)
        value["phases"].append(copy.deepcopy(value["phases"][start]))
        changes.append(value)
        for index, value in enumerate(changes):
            with self.subTest(index=index), patch.object(self.M.allocation, "policy", return_value=value), \
                    patch.object(self.C, "_interpreter") as supplier, \
                    self.assertRaisesRegex(self.M.CommandError, "ALLOCATION_CHANGED"):
                self.descriptor()
            supplier.assert_not_called()

    def test_changed_stop_inclusion_native_lifetime_or_job_proposal_refuses(self):
        original = self.M.allocation.policy()
        changes = []
        for key, field in (("seconds", 345), ("sameHomeStopSeconds", 121),
                           ("sameHomeStopIncluded", False), ("sameHomeStopIncluded", 1), ("scope", "renewable")):
            value = copy.deepcopy(original)
            value["producerReturn"][key] = field
            changes.append(value)
        for key, field in (("windowsNativeFileSeconds", 901), ("windowsNativeFileSeconds", True),
                           ("proposedJobSeconds", 5401), ("nativeCaptureScope", "fresh-per-call")):
            value = copy.deepcopy(original)
            value[key] = field
            changes.append(value)
        for index, value in enumerate(changes):
            with self.subTest(index=index), patch.object(self.M.allocation, "policy", return_value=value), \
                    patch.object(self.C, "_interpreter") as supplier, \
                    self.assertRaisesRegex(self.M.CommandError, "ALLOCATION_CHANGED"):
                self.descriptor()
            supplier.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
