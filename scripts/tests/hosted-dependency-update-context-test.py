#!/usr/bin/env python3
"""Focused offline bridge controls, not native or productive qualification.

Source, closed DATA and fake original observations only. No subprocess, Darwin
observation/control, network, hosted run, old accepted-reader suite or productive command is
executed. The four real qualifier cases remain a separate admission boundary.
"""
import __future__
import argparse
import ast
import contextlib
import copy
import ctypes
import errno
import grp
import hashlib
import importlib.util
import io
import ipaddress
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import pwd
import re
import select
import shlex
import shutil
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import types
import unittest
import uuid
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
BRIDGE_PATH = "scripts/hosted_dependency_update_context.py"
GENERATION_PATH = "scripts/run-hosted-dependency-update.py"
QUALIFIER_PATH = "scripts/run-hosted-dependency-context-qualification.py"
QUALIFIER_WORKFLOW = ".github/workflows/dependency-update-context-qualification.yml"
QUALIFIER_JOB_IF = "${{ github.repository == 'p2pKit/P2pKit' && github.event_name == 'workflow_dispatch' && " \
    "github.actor == 'Apdelrahman1911' && github.actor_id == '104788132' && github.triggering_actor == 'Apdelrahman1911' }}"
CLOCK_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
NS = 1_000_000_000
CASES = ("Q1", "Q2", "Q3", "Q4")
IDENTITY_KEYS = frozenset(("pid", "parentPid", "uniqueId", "parentUniqueId", "pidVersion", "startSeconds",
                           "startMicroseconds", "uid", "realUid", "gid", "realGid", "status"))
ACCOUNT = {"uid": 501, "euid": 501, "gid": 20, "egid": 20, "groups": [20, 80]}
GENERATION_REQUEST_KEYS = {"controller_sha", "controller_tree", "candidate_sha", "candidate_tree",
                           "dependency_base_sha"}
QUALIFIER_REQUEST_KEYS = {"source_sha", "source_tree"}
CANONICAL_PINS = {
    "scripts/run-audit-command.py": "04e921eb5ba1e715078d9b315e366cc8f970151c9c1e5e0a4e5dfae0f0ed1ccc",
    "scripts/audit_processes.py": "7ef1beb8a79ce3c8e062100849babee6ffa0ce3421d0f0fc56706c3e0ef7ed13",
}
DARWIN_METHODS = {
    "test_darwin_synthesizes_exact_real_uid_roman_us_cache_before_launch",
    "test_caller_cf_and_unapproved_inputs_are_not_read_inherited_or_mutated",
    "test_signed_exact_int_uid_guard_refuses_before_formatting_or_output",
    "test_non_darwin_keeps_prior_environment_without_any_uid_query",
}


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }:
        raise AssertionError("offline context control attempted an external operation: " + event)


# Preload the standard library, then fence every project import and control.
sys.addaudithook(offline)


def load_source(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Source:
    """Inspect these exact maintained sources; never compile/execute fragments."""

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
        found = [node for node in nodes if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
        if len(found) != 1:
            raise AssertionError("missing or duplicate source function: " + str(owner) + "." + name)
        return found[0]

    def segment(self, node):
        return ast.get_source_segment(self.text, node)

    @staticmethod
    def call_name(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = Source.call_name(node.value)
            return parent + "." + node.attr if parent else node.attr
        return ""

    @classmethod
    def calls(cls, node):
        return [(item.lineno, cls.call_name(item.func), item) for item in sorted(
            (item for item in ast.walk(node) if isinstance(item, ast.Call)), key=lambda item: (item.lineno, item.col_offset))]

    @staticmethod
    def strings(node):
        return {item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and type(item.value) is str}


def identity(pid=101, *, parent_pid=71, unique=1001, parent_unique=701, version=19):
    return {"pid": pid, "parentPid": parent_pid, "uniqueId": unique, "parentUniqueId": parent_unique,
            "pidVersion": version, "startSeconds": 123, "startMicroseconds": 456,
            "uid": 501, "realUid": 501, "gid": 20, "realGid": 20, "status": 2}


class UnreapedChild:
    def __init__(self, pid, returncode=None):
        self.pid, self.returncode = pid, returncode

    def poll(self):
        raise AssertionError("startup must not poll/reap the original child")

    wait = communicate = terminate = kill = poll


def setUpModule():
    global B, G, Q, BS, GS, QS
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise AssertionError("use the admitted isolated/no-site/no-bytecode control invocation")
    G = load_source("dependency_generation_context_controls", GENERATION_PATH)
    Q = load_source("dependency_qualifier_context_controls", QUALIFIER_PATH)
    # Use the qualifier's actual imported singleton/type objects, not a second
    # independently loaded ProductionRefusal class with the same spelling.
    B = Q.bridge
    BS, GS, QS = Source(BRIDGE_PATH), Source(GENERATION_PATH), Source(QUALIFIER_PATH)


class SourceBoundaryControls(unittest.TestCase):
    def test_fixed_api_has_no_supplied_executor_environment_or_clock_selector(self):
        signatures = {
            (None, "service"): ("profile", "directory"),
            (None, "producer"): ("profile", "fd"),
            ("Foreground", "__init__"): ("self", "profile", "operation", "allocation"),
            ("Foreground", "prepare_case"): ("self", "case"),
            ("Foreground", "run_case"): ("self", "case", "input_path"),
            ("Foreground", "production_result"): ("self", "outcome"),
            ("Foreground", "finish"): ("self",),
            ("Foreground", "abort"): ("self",),
        }
        for (owner, name), expected in signatures.items():
            with self.subTest(owner=owner, method=name):
                node = BS.definition(name, owner)
                self.assertEqual(tuple(arg.arg for arg in (*node.args.posonlyargs, *node.args.args)), expected)
                self.assertIsNone(node.args.vararg)
                self.assertIsNone(node.args.kwarg)
                self.assertEqual(tuple(arg.arg for arg in node.args.kwonlyargs),
                                 ("step_started_ns",) if name == "__init__" else ())
                self.assertEqual(node.args.defaults, [])
                self.assertTrue(all(value is None for value in node.args.kw_defaults))

    def test_canonical_native_sources_and_existing_darwin_controls_are_not_replaced(self):
        for relative, expected in CANONICAL_PINS.items():
            with self.subTest(path=relative):
                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)
        original = Source("scripts/tests/hosted-dependency-update-test.py")
        methods = [node.name for node in ast.walk(original.tree)
                   if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
        self.assertEqual(len(methods), len(set(methods)))
        self.assertEqual(len(methods), 48)
        self.assertEqual(hashlib.sha256(("\n".join(sorted(methods)) + "\n").encode("ascii")).hexdigest(),
                         "1b00e13585408cd00a1567eac332341f067fadf953cb6fea14f8a5f5d5a08e43")
        self.assertTrue(DARWIN_METHODS.issubset(methods))
        self.assertEqual({node.name for node in next(node for node in original.tree.body
            if isinstance(node, ast.ClassDef) and node.name == "DarwinStartupEnvironmentControls").body
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}, DARWIN_METHODS)

    def test_current_shared_module_is_not_a_diagnostic_runtime_import(self):
        forbidden = {"run-hosted-darwin-context-experiment.py", "run-audit-command-test.py",
                     "hosted-dependency-update-test.py", "run-hosted-context-diagnostic.py"}
        for source in (BS, GS, QS):
            for _line, name, call in source.calls(source.tree):
                if name.endswith(("load_module", "module", "spec_from_file_location", "compile", "exec", "run_path")):
                    self.assertFalse(forbidden & {Path(value).name for value in Source.strings(call)})
            for node in ast.walk(source.tree):
                if isinstance(node, ast.Import):
                    self.assertFalse(any("diagnostic" in alias.name or alias.name.startswith("test_") for alias in node.names))
                elif isinstance(node, ast.ImportFrom):
                    self.assertNotIn("diagnostic", node.module or "")


def request_fixture(profile):
    keys = GENERATION_REQUEST_KEYS if profile is B.GENERATION else QUALIFIER_REQUEST_KEYS
    request = {key: chr(ord("a") + index) * 40 for index, key in enumerate(sorted(keys))}
    source_key = "controller_sha" if profile is B.GENERATION else "source_sha"
    tree_key = "controller_tree" if profile is B.GENERATION else "source_tree"
    ref = "refs/heads/work/release-foundation-dependency-context-control"
    env = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_EVENT_NAME": "workflow_dispatch",
           "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
           "GITHUB_JOB": profile.job, "GITHUB_ACTOR": "Apdelrahman1911", "GITHUB_ACTOR_ID": "104788132",
           "GITHUB_TRIGGERING_ACTOR": "Apdelrahman1911", "GITHUB_REF": ref,
           "GITHUB_SHA": request[source_key], "GITHUB_WORKFLOW_SHA": request[source_key],
           "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/" + profile.workflow + "@" + ref,
           "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_EVENT_PATH": "/controlled/event.json",
           profile.request_env: B.encoded(request).decode("ascii")}
    github = {"repository": "p2pKit/P2pKit", "workflow": profile.workflow, "job": profile.job, "ref": ref,
              "source": request[source_key], "sourceTree": request[tree_key], "runId": "123", "runAttempt": "1",
              "actor": "Apdelrahman1911", "actorId": "104788132", "triggeringActor": "Apdelrahman1911"}
    return request, env, github


def allocation_fixture(profile):
    request, env, github = request_fixture(profile)
    allocation = {"schema": 2, "clockDomain": CLOCK_DOMAIN, "source": github["source"],
                  "sourceTree": github["sourceTree"], "runId": github["runId"], "runAttempt": github["runAttempt"],
                  "startedMonotonicNs": 1000 * NS, "startedEpochNs": (B.POLICY_EXPIRES - 20000) * NS}
    if profile is B.QUALIFICATION:
        allocation["scope"] = profile.scope
    return request, env, github, allocation


class ProfileAndClockControls(unittest.TestCase):
    def test_only_two_original_profiles_and_closed_public_request_rosters(self):
        self.assertIs(B.validate_profile(B.GENERATION), B.GENERATION)
        self.assertIs(B.validate_profile(B.QUALIFICATION), B.QUALIFICATION)
        for value in (None, "GENERATION", "QUALIFICATION", {}, copy.copy(B.GENERATION), copy.copy(B.QUALIFICATION)):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(B.ContextError):
                B.validate_profile(value)
        self.assertEqual(B.GENERATION.cases, ("GENERATION",))
        self.assertEqual(B.QUALIFICATION.cases, CASES)
        self.assertEqual(G.REQUEST_KEYS, GENERATION_REQUEST_KEYS)
        self.assertEqual(Q.REQUEST_KEYS, QUALIFIER_REQUEST_KEYS)
        self.assertEqual(Q.CASES, CASES)
        self.assertEqual(B.GENERATION.script, GENERATION_PATH)
        self.assertEqual(B.QUALIFICATION.script, QUALIFIER_PATH)
        self.assertEqual(B.QUALIFICATION.workflow, QUALIFIER_WORKFLOW)
        self.assertEqual(B.QUALIFICATION.job, "dependency_context_qualification")

    def check_original(self, profile, request, env, event_inputs):
        values = {**env, profile.request_env: B.encoded(request).decode("ascii")}
        with patch.object(B, "physical", side_effect=lambda value: Path(value)), \
                patch.object(B, "read_file", return_value=B.encoded({"inputs": event_inputs})):
            return B.validate_original_environment(profile, values)

    def test_shared_request_joins_actual_workflow_event_and_source_without_selectors(self):
        for profile in (B.GENERATION, B.QUALIFICATION):
            request, env, github = request_fixture(profile)
            with self.subTest(profile=profile.job):
                self.assertEqual(self.check_original(profile, request, env, request), github)
                for key in ("operation", "case", "command", "timeout", "profile"):
                    with self.subTest(extra=key), self.assertRaises(B.ContextError):
                        self.check_original(profile, {**request, key: "Q4"}, env, request)
                for key in request:
                    with self.subTest(missing=key), self.assertRaises(B.ContextError):
                        self.check_original(profile, {name: value for name, value in request.items() if name != key}, env, request)
                with self.assertRaises(B.ContextError):
                    self.check_original(profile, request, env, {**request, "case": "Q1"})
                for key, value in (("GITHUB_EVENT_NAME", "push"), ("GITHUB_JOB", "context_experiment"),
                                   ("GITHUB_WORKFLOW_SHA", "f" * 40), ("GITHUB_RUN_ID", "01"),
                                   ("GITHUB_WORKFLOW_REF", "p2pKit/P2pKit/" + QUALIFIER_WORKFLOW + "@refs/heads/main")):
                    with self.subTest(substitution=key), self.assertRaises(B.ContextError):
                        self.check_original(profile, request, {**env, key: value}, request)

    def test_qualifier_two_field_request_refuses_generation_or_diagnostic_identity(self):
        request, env, github = request_fixture(B.QUALIFICATION)
        self.assertEqual(Q.validate_request(request, env, request), github)
        mutations = [({**request, "case": "Q4"}, env, request),
                     ({**request, "source_sha": "A" * 40}, env, request),
                     (request, env, {**request, "source_tree": "f" * 40})]
        for key, value in (("GITHUB_JOB", "generate"), ("GITHUB_EVENT_NAME", "pull_request"),
                           ("GITHUB_REF", "refs/heads/main"), ("GITHUB_ACTOR_ID", "1"),
                           ("GITHUB_WORKFLOW_SHA", "f" * 40), ("GITHUB_RUN_ATTEMPT", "01"),
                           ("GITHUB_WORKFLOW_REF", "p2pKit/P2pKit/.github/workflows/darwin-native-context-experiment.yml@" + env["GITHUB_REF"])):
            mutations.append((request, {**env, key: value}, request))
        for index, values in enumerate(mutations):
            with self.subTest(mutation=index), self.assertRaises(Q.QualificationError):
                Q.validate_request(*values)

    def test_shared_raw_clock_has_one_guarded_builtin_call_and_no_fallback(self):
        for value in (0, 123456789, (1 << 64) - 1):
            clock = Mock(return_value=value)
            raw = types.SimpleNamespace(CLOCK_MONOTONIC_RAW=91, clock_gettime_ns=clock)
            with self.subTest(value=value), patch.object(B.sys, "platform", "darwin"), patch.object(B, "time", raw):
                self.assertEqual(B.shared_raw_ns(), value)
                clock.assert_called_once_with(91)
        for value in (True, False, -1, 1 << 64, 1.0, "1", None):
            raw = types.SimpleNamespace(CLOCK_MONOTONIC_RAW=91, clock_gettime_ns=Mock(return_value=value))
            with self.subTest(invalid_type=type(value).__name__), patch.object(B.sys, "platform", "darwin"), \
                    patch.object(B, "time", raw), self.assertRaises(B.ContextError):
                B.shared_raw_ns()
        clock = Mock(side_effect=AssertionError("unsupported clock must not be sampled"))
        for host, constant in (("linux", 91), ("darwin", True), ("darwin", None)):
            with self.subTest(host=host, constant=constant), patch.object(B.sys, "platform", host), \
                    patch.object(B, "time", types.SimpleNamespace(CLOCK_MONOTONIC_RAW=constant, clock_gettime_ns=clock)), \
                    self.assertRaises(B.ContextError):
                B.shared_raw_ns()
        clock.assert_not_called()
        self.assertEqual(B.CLOCK_SCHEMA, 2)
        self.assertEqual(B.CLOCK_DOMAIN, CLOCK_DOMAIN)
        for source in (BS, GS, QS):
            self.assertFalse(any(name in ("time.monotonic", "time.monotonic_ns", "time.perf_counter", "time.perf_counter_ns")
                                 for _line, name, _call in source.calls(source.tree)))

    def test_schema2_allocation_is_identical_across_original_shared_and_qualifier_clocks(self):
        for profile in (B.GENERATION, B.QUALIFICATION):
            request, _env, github, allocation = allocation_fixture(profile)
            now = allocation["startedMonotonicNs"] + 30 * NS
            wall = allocation["startedEpochNs"] + 30 * NS
            expected = allocation["startedMonotonicNs"] + profile.job_seconds * NS
            with self.subTest(profile=profile.job):
                self.assertEqual(B.validate_allocation(profile, allocation, github, now, wall), expected)
                if profile is B.QUALIFICATION:
                    self.assertEqual(Q.validate_allocation(allocation, request, github, now, wall), expected)
                mutations = [{**allocation, "schema": 1}, {**allocation, "schema": True},
                             {**allocation, "clockDomain": "time.monotonic_ns"},
                             {key: value for key, value in allocation.items() if key != "clockDomain"},
                             {**allocation, "sourceTree": "f" * 40}, {**allocation, "runAttempt": "2"},
                             {**allocation, "startedMonotonicNs": True}, {**allocation, "startedEpochNs": 0},
                             {**allocation, "deadline": now + 123}]
                mutations.append({**allocation, "scope": B.GENERATION.scope})
                for index, changed in enumerate(mutations):
                    with self.subTest(mutation=index), self.assertRaises(B.ContextError):
                        B.validate_allocation(profile, changed, github, now, wall)
                    if profile is B.QUALIFICATION:
                        with self.subTest(qualifier_mutation=index), self.assertRaises(Q.QualificationError):
                            Q.validate_allocation(changed, request, github, now, wall)

    def test_original_job_elapsed_and_wall_raw_drift_cannot_be_renewed(self):
        for profile in (B.GENERATION, B.QUALIFICATION):
            _request, _env, github, allocation = allocation_fixture(profile)
            start, wall_start = allocation["startedMonotonicNs"], allocation["startedEpochNs"]
            end = start + profile.job_seconds * NS
            for elapsed in (0, 30 * NS, profile.job_seconds * NS - 1):
                with self.subTest(profile=profile.job, elapsed=elapsed):
                    self.assertEqual(B.validate_allocation(profile, allocation, github,
                                                          start + elapsed, wall_start + elapsed), end)
            for now, wall in ((start - 1, wall_start), (end, wall_start + profile.job_seconds * NS),
                              (start + NS, wall_start + 61 * NS + 1), (True, wall_start), (start, False)):
                with self.subTest(profile=profile.job, now=now, wall=wall), self.assertRaises(B.ContextError):
                    B.validate_allocation(profile, allocation, github, now, wall)

    def test_production_reserves_and_distinct_qualifier_refusal_envelope_are_unchanged(self):
        values = {"JOB_SECONDS": 12600, "STEP_SECONDS": 9900, "PREREQUISITES_SECONDS": 900,
                  "PRODUCT_SECONDS": 7200, "STOP_SECONDS": 120, "NATIVE_HEADROOM": 180,
                  "FINALIZE_SECONDS": 300, "EXPORT_SECONDS": 120, "UPLOAD_SECONDS": 1320,
                  "WRITER_RESERVE": 9240, "ENTRY_RESERVE": 10440}
        for name, value in values.items():
            with self.subTest(generation=name):
                self.assertEqual(getattr(G, name), value)
        for name, value in {"JOB_SECONDS": 2460, "STEP_SECONDS": 1740, "SUITE_SECONDS": 1200,
                            "CASE_SECONDS": 300, "PRODUCT_SECONDS": 20, "STOP_SECONDS": 5,
                            "READY_SECONDS": 15, "ADMIN_SECONDS": 10, "ABORT_SECONDS": 120,
                            "FREEZE_SECONDS": 60, "EXPORT_SECONDS": 120, "UPLOAD_SECONDS": 420}.items():
            with self.subTest(qualifier=name):
                self.assertEqual(getattr(Q, name), value)
        self.assertEqual(Q.POLICY_EXPIRES, 1791158400)
        self.assertEqual(Q.LATEST_ENTRY, 1791145800)
        self.assertEqual((B.FRAME_BYTES, B.STREAM_BYTES), (16384, 65536))
        self.assertEqual((Q.EVIDENCE_BYTES, Q.EVIDENCE_MEMBERS, Q.CIPHERTEXT_BYTES),
                         (512 * 1024 * 1024, 10000, 576 * 1024 * 1024))


class StartupIdentityControls(unittest.TestCase):
    def setUp(self):
        self.parent = identity(71, parent_pid=1, unique=701, parent_unique=11)
        self.birth = identity()
        self.child = UnreapedChild(self.birth["pid"])

    def observe(self, birth, observed, process=None):
        native = types.SimpleNamespace(identity=Mock(return_value=observed))
        with patch.object(B.os, "getpid", return_value=self.parent["pid"]):
            result = B.observe_startup_child(native, process or self.child, birth, self.parent, ACCOUNT)
        native.identity.assert_called_once_with(self.child.pid)
        return result

    def test_birth_to_ready_query_preserves_ten_fields_and_actual_unmodified_versions(self):
        self.assertEqual(B.IDENTITY_KEYS, IDENTITY_KEYS)
        for version in (0, 1, self.birth["pidVersion"], 83):
            original, observed = copy.deepcopy(self.birth), {**self.birth, "pidVersion": version, "status": 3}
            with self.subTest(version=version):
                self.assertEqual(self.observe(self.birth, observed), observed)
                self.assertEqual(self.birth, original)
                self.assertEqual(observed["pidVersion"], version)
        calls = [name for _line, name, _call in BS.calls(BS.definition("observe_startup_child"))]
        self.assertEqual(calls.count("native.identity"), 1)
        self.assertFalse(any(name.endswith((".poll", ".wait", ".communicate")) for name in calls))

    def test_any_birth_parent_account_or_native_type_change_refuses_without_retry(self):
        for key in IDENTITY_KEYS - {"status", "pidVersion"}:
            changed = {**self.birth, key: self.birth[key] + 1}
            native = types.SimpleNamespace(identity=Mock(return_value=changed))
            with self.subTest(field=key), patch.object(B.os, "getpid", return_value=self.parent["pid"]), \
                    self.assertRaises(B.ContextError):
                B.observe_startup_child(native, self.child, self.birth, self.parent, ACCOUNT)
            native.identity.assert_called_once_with(self.child.pid)
        for changed in ({**self.birth, "pidVersion": True}, {**self.birth, "status": 0},
                        {**self.birth, "extra": 1}, {key: value for key, value in self.birth.items() if key != "startSeconds"}):
            with self.subTest(shape=tuple(changed)), self.assertRaises(B.ContextError):
                self.observe(self.birth, changed)
        native = types.SimpleNamespace(identity=Mock(side_effect=B.ContextError("IDENTITY", "RETURN_FAILED")))
        with patch.object(B.os, "getpid", return_value=self.parent["pid"]), self.assertRaises(B.ContextError):
            B.observe_startup_child(native, self.child, self.birth, self.parent, ACCOUNT)
        native.identity.assert_called_once_with(self.child.pid)

    def test_reaped_child_or_wrong_original_parent_never_reaches_startup_query(self):
        for process, birth in ((UnreapedChild(self.child.pid, 0), self.birth),
                               (UnreapedChild(True), self.birth),
                               (self.child, {**self.birth, "parentUniqueId": self.parent["uniqueId"] + 1}),
                               (self.child, {**self.birth, "uid": 0, "realUid": 0})):
            native = types.SimpleNamespace(identity=Mock(side_effect=AssertionError("no replacement startup query")))
            with self.subTest(pid=process.pid), patch.object(B.os, "getpid", return_value=self.parent["pid"]), \
                    self.assertRaises(B.ContextError):
                B.observe_startup_child(native, process, birth, self.parent, ACCOUNT)
            native.identity.assert_not_called()

    def test_full_ready_image_does_not_reuse_birth_tolerance_after_binding(self):
        full = {**self.birth, "pidVersion": 83}
        self.assertEqual(B.same_identity({**full, "status": 3}, full)["pidVersion"], 83)
        for key in IDENTITY_KEYS - {"status"}:
            with self.subTest(field=key), self.assertRaises(B.ContextError):
                B.same_identity({**full, key: full[key] + 1}, full)
        session = {"pid": full["pid"], "sessionId": full["pid"], "processGroupId": full["pid"]}
        for parent_pid, parent_unique in ((self.parent["pid"], self.parent["uniqueId"]), (1, self.parent["uniqueId"])):
            changed = {**full, "parentPid": parent_pid, "parentUniqueId": parent_unique}
            with self.subTest(parent=parent_pid):
                row = B.validate_orphan_identity(changed, full, self.parent, session, session, 100, 101)
                self.assertEqual(row["serviceExitObservedRawNs"], 100)
                self.assertEqual(row["currentParentUniqueId"], parent_unique)
        orphan = {**full, "parentPid": 1, "parentUniqueId": self.parent["uniqueId"]}
        for key in IDENTITY_KEYS - {"status", "parentPid", "parentUniqueId"}:
            with self.subTest(orphan_field=key), self.assertRaises(B.ContextError):
                B.validate_orphan_identity({**orphan, key: orphan[key] + 1}, full, self.parent, session, session, 100, 101)
        for changed, current, event, checked in (({**orphan, "parentUniqueId": 999}, session, 100, 101),
                                               (orphan, {**session, "sessionId": self.parent["pid"]}, 100, 101),
                                               (orphan, session, 0, 101), (orphan, session, 102, 101),
                                               (orphan, session, True, 101)):
            with self.subTest(event=event, checked=checked), self.assertRaises(B.ContextError):
                B.validate_orphan_identity(changed, full, self.parent, current, session, event, checked)

    def test_nonroot_account_and_child_environment_are_closed_data_not_inherited_authority(self):
        self.assertEqual(B.validate_account(ACCOUNT), ACCOUNT)
        for changed in ({**ACCOUNT, "uid": 0, "euid": 0}, {**ACCOUNT, "euid": 502},
                        {**ACCOUNT, "gid": True}, {**ACCOUNT, "groups": [80, 20]},
                        {**ACCOUNT, "groups": [20, 20]}, {**ACCOUNT, "groups": [True]},
                        {**ACCOUNT, "username": "caller"}):
            with self.subTest(shape=tuple(changed)), self.assertRaises(B.ContextError):
                B.validate_account(changed)
        operation = Path("/controlled/operation")
        tools = {"PATH": "/approved/bin", "JAVA_HOME": "/approved/jdk17", "P2PKIT_AUDIT_JDK21": "/approved/jdk21",
                 "DEVELOPER_DIR": "/Applications/Xcode_26.5.app/Contents/Developer", "ANDROID_HOME": "/approved/android"}
        with patch.object(B.os, "getuid", return_value=501):
            for profile, selected in ((B.GENERATION, tools), (B.QUALIFICATION, {})):
                result = B.child_environment(profile, operation, selected)
                self.assertEqual(result["__CF_USER_TEXT_ENCODING"], "0x1F5:0:0")
                self.assertFalse(set(result) & {"GITHUB_OUTPUT", "GITHUB_TOKEN", "GH_TOKEN", "GITHUB_ENV", *B.OWNER_ENV})
                self.assertFalse(any(name.startswith(("GITHUB_", "ACTIONS_", "DYLD_")) for name in result))
                for key in ("GITHUB_OUTPUT", "GH_TOKEN", "__CF_USER_TEXT_ENCODING", "BASH_ENV"):
                    with self.subTest(profile=profile.job, extra=key), self.assertRaises(B.ContextError):
                        B.child_environment(profile, operation, {**selected, key: "unapproved"})

    def test_literal_nonroot_service_plist_has_no_restart_or_environment_authority_selector(self):
        self.assertEqual(B.INTERPRETER, "/Library/Developer/CommandLineTools/usr/bin/python3")
        self.assertEqual(B.ROOT_TEMPLATE, "/private/var/db/p2pkit-context.XXXXXXXXXX")
        self.assertEqual(B.OS_PARENTS, ("/", "/private", "/private/var", "/private/var/db", "/usr", "/usr/bin", "/bin"))
        self.assertEqual(B.OS_TOOLS, ("/usr/bin/sudo", "/usr/bin/mktemp", "/usr/bin/stat", "/usr/bin/tee", "/bin/cat", "/bin/ls",
                                     "/bin/rm", "/bin/rmdir", "/bin/launchctl", "/usr/bin/git", "/usr/bin/sw_vers"))
        operation, directory = Path("/controlled/operation"), Path("/controlled/operation/bridge/cases/Q1")
        context = types.SimpleNamespace(profile=B.QUALIFICATION, interpreter={"path": B.INTERPRETER},
                                        username="runner", groupname="staff", operation=operation, tools={})
        with patch.object(B.os, "getuid", return_value=501):
            raw = B.service_plist(context, "p2pkit.context.r123.a1.q1.abcdef", directory)
            expected_environment = B.child_environment(B.QUALIFICATION, operation, {})
        self.assertLessEqual(len(raw), B.FRAME_BYTES)
        self.assertEqual(plistlib.loads(raw), {
            "Label": "p2pkit.context.r123.a1.q1.abcdef", "ProgramArguments": [B.INTERPRETER, "-I", "-B", "-S",
                str(ROOT / QUALIFIER_PATH), "_service", str(directory)],
            "UserName": "runner", "GroupName": "staff", "InitGroups": True, "RunAtLoad": True,
            "KeepAlive": False, "AbandonProcessGroup": False, "WorkingDirectory": str(ROOT),
            "EnvironmentVariables": expected_environment, "StandardInPath": "/dev/null",
            "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null"})


class ClosedDataControls(unittest.TestCase):
    def test_bounded_unique_json_refuses_partial_or_nonfinite_transport_data(self):
        self.assertEqual(B.encoded({"z": [1, True, None], "a": "x"}), b'{"a":"x","z":[1,true,null]}\n')
        for raw in (b'{"a":1,"a":2}\n', b'{"a":NaN}\n', b'{"a":Infinity}\n', b'{"a":', b"\xff", b" " * (B.FRAME_BYTES + 1)):
            with self.subTest(raw_size=len(raw)), self.assertRaises(B.ContextError):
                B.parsed(raw)
        deep = 0
        for _ in range(B.JSON_DEPTH + 1):
            deep = [deep]
        with self.assertRaises(B.ContextError):
            B.encoded(deep)
        self.assertEqual(B.CASE_INPUT_KEYS, frozenset(("schema", "scope", "case", "binding", "github",
            "allocationSha256", "repositorySource", "caseDirectoryIdentity", "foreground", "account",
            "caseStartNs", "caseEndNs")))
        self.assertEqual(B.PRODUCER_RESULT_KEYS, frozenset(("schema", "scope", "case", "binding", "caseInputSha256",
            "canonicalEntrySha256", "producerIdentity", "commands", "code", "disposition", "completedRawNs")))

    def test_producer_return_data_preserves_original_command_order_and_raw_return_anchor(self):
        entry = {"case": "GENERATION", "binding": "a" * 64, "producerIdentity": identity(), "enteredMonotonicNs": 10}
        first = {"invocationId": "1" * 32, "purpose": "dependency-maintenance-prerequisites",
                 "receiptSha256": "b" * 64, "code": 0, "returnedRawNs": 20}
        second = {"invocationId": "2" * 32, "purpose": "dependency-maintenance-generator",
                  "receiptSha256": "c" * 64, "code": 0, "returnedRawNs": 30}
        result = {"schema": 1, "scope": B.GENERATION.scope, "case": "GENERATION", "binding": entry["binding"],
                  "caseInputSha256": "d" * 64, "canonicalEntrySha256": "e" * 64, "producerIdentity": identity(),
                  "commands": [first, second], "code": 0, "disposition": "SUCCESS", "completedRawNs": 40}
        self.assertEqual(B.validate_producer_result(B.GENERATION, result, entry, "d" * 64), result)
        failed = {**result, "commands": [{**first, "code": 23}], "code": 23, "disposition": "CLOSED_FAILED_PRODUCT"}
        self.assertEqual(B.validate_producer_result(B.GENERATION, failed, entry, "d" * 64), failed)
        mutations = [{**result, "commands": [first]}, {**result, "commands": [second, first]},
                     {**result, "commands": [first, {**second, "invocationId": first["invocationId"]}]},
                     {**result, "commands": [first, {**second, "returnedRawNs": 19}]},
                     {**result, "commands": [{**first, "code": 23}, second]},
                     {**result, "commands": [first, {**second, "code": True}]},
                     {**result, "completedRawNs": 29}, {**result, "code": True},
                     {**result, "caseInputSha256": "f" * 64},
                     {**result, "producerIdentity": {**identity(), "pidVersion": 20}}]
        for code in (124, 125):
            mutations.append({**result, "commands": [first, {**second, "code": code}], "code": code,
                              "disposition": "CLOSED_FAILED_PRODUCT"})
        for index, changed in enumerate(mutations):
            with self.subTest(mutation=index), self.assertRaises(B.ContextError):
                B.validate_producer_result(B.GENERATION, changed, entry, "d" * 64)
        # A later result-creation timestamp cannot replace the original return.
        self.assertEqual(result["commands"][-1]["returnedRawNs"], 30)
        self.assertEqual(result["completedRawNs"], 40)

    def test_fixed_canonical_qualifier_codes_and_only_expected_cancellation_receipts(self):
        for case in CASES:
            code, receipt, context, entry = canonical_fixture(case)
            expected = "SUCCESS" if case == "Q1" else "CLOSED_FAILED_PRODUCT" if case == "Q2" else "INFRASTRUCTURE_REFUSAL"
            with self.subTest(case=case):
                self.assertEqual(Q.validate_canonical_result(code, receipt, context, entry, case), expected)
                changes = [{**receipt, "stopExitCode": 1}, {**receipt, "sourceUnchanged": False},
                           {**receipt, "sourceAfter": {**context["source"], "tree": "a" * 40}},
                           {**receipt, "ownedSurvivors": [{"pid": 999}]},
                           {**receipt, "ownership": {"discoveryErrors": ["unknown"]}},
                           {**receipt, "cancelRequested": True}, {**receipt, "productExitCode": True},
                           {**receipt, "id": "f" * 32}, {**receipt, "controllerPid": 999}]
                if case in ("Q3", "Q4"):
                    changes.extend(({**receipt, "errors": []}, {**receipt, "cancelledSignals": [15, 15]},
                                    {**receipt, "productExitCode": 125}, {**receipt, "finalExitCode": 0}))
                else:
                    changes.extend(({**receipt, "errors": list(Q.CANCELLATION_ERRORS)},
                                    {**receipt, "cancelledSignals": []}, {**receipt, "cancelRequested": False}))
                for index, changed in enumerate(changes):
                    with self.subTest(mutation=index), self.assertRaises(Q.QualificationError):
                        Q.validate_canonical_result(code, changed, context, entry, case)
                for changed_code in (True, 124, -15, 0 if code else 23):
                    with self.subTest(code=changed_code), self.assertRaises(Q.QualificationError):
                        Q.validate_canonical_result(changed_code, receipt, context, entry, case)


def canonical_fixture(case):
    """Fixed synthetic DATA; never creates a canonical context or executes it."""
    code = 0 if case == "Q1" else 23 if case == "Q2" else 125
    source = {"commit": "f" * 40, "tree": "e" * 40, "status": "", "diffSha256": B.digest(b"")}
    state = "/controlled/operation/states/" + case
    context = {"id": "a" * 32, "root": "/controlled/operation/fixture", "gradleHome": state + "/gradle-home",
               "source": source, "gradlePropertiesSha256": "d" * 64}
    entry = {"schema": 1, "scope": Q.SCOPE, "case": case, "binding": "b" * 64,
             "caseInputSha256": "c" * 64, "contextSha256": "d" * 64, "contextId": context["id"],
             "invocationId": "1" * 32, "fixtureSourceCommit": source["commit"], "fixtureSourceTree": source["tree"],
             "gradlePolicySha256": context["gradlePropertiesSha256"], "producerIdentity": identity(), "enteredMonotonicNs": 110}
    argv = [str(Path(sys.executable).resolve()), "-I", "-B", "-S", context["root"] + "/fixture.py", "--product", case]
    receipt = {"schema": 1, "id": entry["invocationId"], "jobId": context["id"], "kind": "command",
               "purpose": "dependency-context-" + case.lower(), "requestedArgv": argv, "executedArgv": list(argv),
               "controllerPid": entry["producerIdentity"]["pid"], "cwd": context["root"],
               "wrapper": context["root"] + "/gradlew", "host": "macos-arm64", "gradleHome": context["gradleHome"],
               "sourceBefore": copy.deepcopy(source), "sourceAfter": copy.deepcopy(source), "sourceUnchanged": True,
               "productPid": 121, "productExitCode": -15 if case in ("Q3", "Q4") else code,
               "stopExitCode": 0, "finalExitCode": code, "ownedSurvivors": [], "ownership": {"discoveryErrors": []},
               "stopArgv": [context["root"] + "/gradlew", "--stop", "--console=plain", "--no-parallel",
                            "--max-workers=2", "-Dorg.gradle.jvmargs=" + Q.JVM_ARGUMENTS],
               "errors": list(Q.CANCELLATION_ERRORS) if case in ("Q3", "Q4") else []}
    if case in ("Q3", "Q4"):
        receipt.update(cancelledSignals=[15], cancelRequested=False)
    return code, receipt, context, entry


def native_event(pid, code):
    return {"ident": pid, "filter": -5, "flags": 0, "fflags": 0x84000000,
            "data": code << 8 if code >= 0 else -code}


def terminal_fixture(identity, code, observed):
    event = native_event(identity["pid"], code)
    return {"event": event, "status": {"rawStatus": event["data"], "kind": "EXITED" if code >= 0 else "SIGNALED",
            "value": abs(code), "popenCode": code}, "observedRawNs": observed}


def registration_fixture(observer, identity, started):
    return {"observer": observer, "observation": {"identity": copy.deepcopy(identity),
        "startedMonotonicNs": started, "returnedMonotonicNs": started + 1, "recheckedMonotonicNs": started + 2,
        "requested": {"ident": identity["pid"], "filter": -5, "flags": 0x45, "fflags": 0x84000000},
        "receipts": [{"ident": identity["pid"], "filter": -5, "flags": 0x4000, "fflags": 0x84000000, "data": 0}]}}


def signal_fixture(signaler, identity, number, started, returned, orphan=None):
    return {"signaler": signaler, "observation": {"identity": copy.deepcopy(identity), "signal": number,
        "returnedCode": 0, "startedMonotonicNs": started, "returnedMonotonicNs": returned}, "orphan": orphan}


def qualifier_fixture(case):
    """Synthetic closed DATA for exactly Q1--Q4, never an owner or an observation."""
    code, receipt, context, entry = canonical_fixture(case)
    p = entry["producerIdentity"] = identity(version=83)
    d = identity(71, parent_pid=1, unique=701, parent_unique=11)
    f = identity(51, parent_pid=1, unique=501, parent_unique=11)
    k = identity(receipt["productPid"], parent_pid=p["pid"], unique=1201, parent_unique=p["uniqueId"])
    state = str(Path(context["gradleHome"]).parent)
    ready = {"schema": 1, "scope": Q.SCOPE, "case": case, "binding": entry["binding"], "contextId": context["id"],
        "invocationId": entry["invocationId"], "pid": k["pid"], "parentPid": p["pid"], "account": copy.deepcopy(ACCOUNT),
        "ownership": {"jobId": context["id"], "chain": entry["invocationId"], "domains": [{"id": entry["invocationId"],
            "job": context["id"], "state": state, "home": context["gradleHome"]}], "state": state, "home": context["gradleHome"]},
        "sourceSha256": B.digest(Q.FIXTURE.encode("ascii")), "sigtermDefault": True, "sigtermBlocked": False,
        "readyMonotonicNs": 120}
    start = {key: copy.deepcopy(receipt[key]) for key in ("schema", "id", "purpose", "kind", "requestedArgv", "cwd",
                                                        "wrapper", "host", "jobId", "gradleHome", "controllerPid")}
    start.update(sourceBefore=None, sourceAfter=None, productExitCode=None, stopExitCode=None)
    disposition = "SUCCESS" if case == "Q1" else "CLOSED_FAILED_PRODUCT" if case == "Q2" else "INFRASTRUCTURE_REFUSAL"
    producer = {"schema": 1, "scope": Q.SCOPE, "case": case, "binding": entry["binding"],
        "caseInputSha256": entry["caseInputSha256"], "canonicalEntrySha256": B.digest(B.encoded(entry)),
        "producerIdentity": copy.deepcopy(p), "commands": [{"invocationId": entry["invocationId"],
            "purpose": receipt["purpose"], "receiptSha256": B.digest(B.encoded(receipt)), "code": code, "returnedRawNs": 170}],
        "code": code, "disposition": disposition, "completedRawNs": 175}
    registrations = [registration_fixture("F", d, 102), registration_fixture("F", p, 113), registration_fixture("F", k, 121)]
    if case != "Q4":
        registrations += [registration_fixture("D", f, 101), registration_fixture("D", p, 112)]
    signals = []
    if case == "Q3":
        signals = [signal_fixture("D", p, 15, 141, 142)]
    elif case == "Q4":
        orphan = {"originalParentPid": d["pid"], "originalParentUniqueId": d["uniqueId"],
            "currentParentPid": 1, "currentParentUniqueId": d["uniqueId"], "serviceExitObservedRawNs": 145, "checkedRawNs": 150}
        signals = [signal_fixture("F", d, 9, 132, 134), signal_fixture("F", p, 15, 151, 152, orphan)]
    closure = {"producerWait": code, "producerPipeEof": True, "producerPipeCaptures": "CLOSED", "producerRecords": "CLOSED",
        "serviceFinalFrame": "RECEIVED", "serviceCaptures": "CLOSED", "producerNativeExit": True, "serviceNativeExit": True,
        "controlEof": True, "controlClosed": True, "registrationAbsent": True, "rootObjectsRemoved": True,
        "adminClosed": True, "soleWritersRetired": True, "nativeRetention": "HELD_UNTIL_SUITE_FINISH"}
    losses = {"producerWait": "ABSENT_D_DIED", "producerPipeEof": "ABSENT_D_DIED", "serviceFinalFrame": "ABSENT_D_DIED",
              "producerPipeCaptures": "INCOMPLETE_D_DIED", "serviceCaptures": "INCOMPLETE_D_DIED"} if case == "Q4" else {}
    closure.update(losses)
    native = {"foreground": f, "service": d, "producerBirth": {**p, "pidVersion": 19}, "producer": p, "product": k,
        "serviceSession": {"pid": d["pid"], "sessionId": 1, "processGroupId": d["pid"]},
        "producerSession": {"pid": p["pid"], "sessionId": p["pid"], "processGroupId": p["pid"]},
        "producerNative": terminal_fixture(p, code, 180),
        "serviceNative": terminal_fixture(d, -9 if case == "Q4" else code, 145 if case == "Q4" else 190),
        "productNative": terminal_fixture(k, -15 if case in ("Q3", "Q4") else code, 160),
        "registrations": registrations, "signalReturns": signals}
    record = {"schema": 1, "scope": Q.SCOPE, "case": case, "binding": entry["binding"],
        "caseInputSha256": entry["caseInputSha256"], "canonicalEntrySha256": producer["canonicalEntrySha256"],
        "producerResultSha256": B.digest(B.encoded(producer)), "native": native,
        "action": {"kind": "RELEASE" if case in ("Q1", "Q2") else "F_WRITE_EOF" if case == "Q3" else "D_SIGKILL",
            "canonicalEntrySha256": producer["canonicalEntrySha256"], "canonicalStartSha256": B.digest(B.encoded(start)),
            "productReadySha256": B.digest(B.encoded(ready)), "startedRawNs": 130, "returnedRawNs": 140,
            "returnedValue": 0 if case == "Q4" else None},
        "closure": closure, "lossAnnotations": losses, "caseStartNs": 100, "caseEndNs": 300, "closedMonotonicNs": 200}
    return record, entry, producer, receipt, context, start, ready


def service_final_fixture(case, record, producer):
    result = B.frame_value(7, record["binding"], {"case": case, "producerResultSha256": record["producerResultSha256"],
                           "producerCapturesSha256": "a" * 64, "code": producer["code"]})
    trace = [B.frame_record(B.frame_value(serial, record["binding"], {})) for serial in range(1, 7)]
    trace.append(B.frame_record(result))
    streams = lambda prefix, extra: [{"name": prefix + "." + suffix, "size": 0, "sha256": B.digest(b""),
                                     "closed": True, extra: True} for suffix in ("stdout", "stderr")]
    return B.frame_value(8, record["binding"], {"case": case, "producerCode": producer["code"],
        "producerStreams": streams("producer-pipe", "eof"), "serviceStreams": streams("service", "fsync"),
        "resultFrame": result, "tracePrefix": trace, "producerControlEof": True, "producerWait": True,
        "nativeClosed": True, "capturesClosed": True,
        "signalReturns": copy.deepcopy([row for row in record["native"]["signalReturns"] if row["signaler"] == "D"]),
        "registrations": copy.deepcopy([row for row in record["native"]["registrations"] if row["observer"] == "D"]),
        "producerNative": {**copy.deepcopy(record["native"]["producerNative"]), "observedRawNs": 179},
        "foregroundLoss": {"kind": "WRITE_EOF", "observedRawNs": 132} if case == "Q3" else None,
        "startForward": {"startedMonotonicNs": 114, "returnedMonotonicNs": 115}})


class QualifierOriginalDataControls(unittest.TestCase):
    def test_fixed_q1_q4_records_require_original_rosters_and_pre_spawn_start_not_final_receipt(self):
        for case in CASES:
            values = qualifier_fixture(case)
            record, entry, producer, receipt, context, start, ready = values
            with self.subTest(case=case):
                self.assertEqual(Q.validate_case_records(case, *values), producer["disposition"])
                self.assertNotEqual(record["native"]["producerBirth"]["pidVersion"], record["native"]["producer"]["pidVersion"])
                watches = {(row["observer"], row["observation"]["identity"]["pid"]) for row in record["native"]["registrations"]}
                expected = {("F", 71), ("F", 101), ("F", 121)} | (set() if case == "Q4" else {("D", 51), ("D", 101)})
                self.assertEqual(watches, expected)
                for changed in ({**start, "productPid": receipt["productPid"]}, {**start, "executedArgv": receipt["executedArgv"]},
                                {**start, "sourceBefore": context["source"]}, receipt):
                    with self.subTest(start_keys=tuple(changed)), self.assertRaises(Q.QualificationError):
                        Q.validate_case_records(case, record, entry, producer, receipt, context, changed, ready)
                for replacement in (record["native"]["registrations"][:-1],
                                    record["native"]["registrations"] + [record["native"]["registrations"][0]]):
                    changed = copy.deepcopy(record)
                    changed["native"]["registrations"] = replacement
                    with self.assertRaises(Q.QualificationError):
                        Q.validate_case_records(case, changed, *values[1:])
        # Exercise the actual fixed-Q1 readiness seam, with no native/file I/O.
        # K can be ready after F starts F5 but before F records send's return.
        for ready_ns, admitted in ((120, True), (114, False)):
            record, entry, _producer, _receipt, context, start, ready = qualifier_fixture("Q1")
            ready["readyMonotonicNs"] = ready_ns
            operation = Path("/controlled/operation")
            directory = operation / "bridge/cases/Q1"
            original_files = {directory / "product-ready.json": B.encoded(ready),
                operation / "fixture/fixture.py": Q.FIXTURE.encode("ascii"),
                operation / "states/Q1/evidence" / entry["invocationId"] / "start.json": B.encoded(start)}
            native = types.SimpleNamespace(same=Mock(), identity=Mock(return_value=record["native"]["product"]), watch=Mock())
            owner = object.__new__(B.Foreground)
            owner.profile, owner.native, owner.account, owner.operation = B.QUALIFICATION, native, ACCOUNT, operation
            owner.interpreter = {"path": str(Path(sys.executable).resolve())}
            state = {"directory": directory, "inputs": {}, "inputHash": entry["caseInputSha256"], "entry": entry,
                "entryHash": record["canonicalEntrySha256"], "service": record["native"]["service"],
                "producer": record["native"]["producer"], "end": 300, "startSentNs": 115, "startReturnedNs": 125,
                "actionDone": False}
            with self.subTest(ready_ns=ready_ns), patch.object(B.os.path, "lexists", return_value=True), \
                    patch.object(B, "read_file", side_effect=lambda path, *limits: original_files[path]), \
                    patch.object(B, "read_canonical_entry", return_value=(entry, record["canonicalEntrySha256"])), \
                    patch.object(B, "shared_raw_ns", return_value=130), patch.object(B, "write_new", return_value=None) as write:
                if admitted:
                    owner._qualifier_action(state)
                    self.assertEqual(state["action"]["kind"], "RELEASE")
                    self.assertTrue(state["actionDone"])
                    native.identity.assert_called_once_with(record["native"]["product"]["pid"])
                    native.watch.assert_called_once_with(record["native"]["product"])
                    write.assert_called_once()
                else:
                    with self.assertRaises(B.ContextError):
                        owner._qualifier_action(state)
                    self.assertFalse(state["actionDone"])
                    native.identity.assert_not_called()
                    native.watch.assert_not_called()
                    write.assert_not_called()

    def test_actual_f8_f7_native_and_q3_eof_records_cannot_be_replaced_by_optimistic_final_data(self):
        for case in ("Q1", "Q2", "Q3"):
            record, _entry, producer, *_rest = qualifier_fixture(case)
            frame = service_final_fixture(case, record, producer)
            self.assertEqual(Q.validate_service_final(case, frame, record, producer), frame["payload"])
            changes = []
            for key in ("producerControlEof", "producerWait", "nativeClosed", "capturesClosed"):
                changed = copy.deepcopy(frame)
                changed["payload"][key] = False
                changes.append(changed)
            for mutation in ("trace", "original-native", "original-registrations", "original-result"):
                changed = copy.deepcopy(frame)
                if mutation == "trace":
                    changed["payload"]["tracePrefix"][-1]["sha256"] = "f" * 64
                elif mutation == "original-native":
                    changed["payload"]["producerNative"]["observedRawNs"] = producer["completedRawNs"] - 1
                elif mutation == "original-registrations":
                    changed["payload"]["registrations"] = []
                else:
                    changed["payload"]["resultFrame"]["payload"]["producerResultSha256"] = "f" * 64
                changes.append(changed)
            if case == "Q3":
                for loss in (None, {"kind": "TERMINAL", "observedRawNs": 132},
                             {"kind": "WRITE_EOF", "observedRawNs": 129}, {"kind": "WRITE_EOF", "observedRawNs": 142}):
                    changed = copy.deepcopy(frame)
                    changed["payload"]["foregroundLoss"] = loss
                    changes.append(changed)
            for index, changed in enumerate(changes):
                with self.subTest(case=case, mutation=index), self.assertRaises(Q.QualificationError):
                    Q.validate_service_final(case, changed, record, producer)
        record, _entry, producer, *_rest = qualifier_fixture("Q4")
        with self.assertRaises(Q.QualificationError):
            Q.validate_service_final("Q4", service_final_fixture("Q4", record, producer), record, producer)

    def test_q4_actual_d_exit_precedes_orphan_signal_and_missing_d_closures_stay_missing(self):
        values = qualifier_fixture("Q4")
        record = values[0]
        self.assertEqual(record["lossAnnotations"], Q.Q4_LOSSES)
        changes = []
        for key in Q.Q4_LOSSES:
            changed = copy.deepcopy(record)
            changed["closure"][key] = "CLOSED"
            changes.append(changed)
        changed = copy.deepcopy(record)
        changed["lossAnnotations"] = {}
        changes.append(changed)
        for mutation in ("predicted-event", "early-check", "wrong-parent", "wrong-sender"):
            changed = copy.deepcopy(record)
            cancellation = changed["native"]["signalReturns"][1]
            if mutation == "predicted-event":
                cancellation["orphan"]["serviceExitObservedRawNs"] -= 1
            elif mutation == "early-check":
                cancellation["orphan"]["checkedRawNs"] = 144
            elif mutation == "wrong-parent":
                cancellation["orphan"]["currentParentUniqueId"] += 1
            else:
                cancellation["signaler"] = "D"
            changes.append(changed)
        for index, changed in enumerate(changes):
            with self.subTest(mutation=index), self.assertRaises(Q.QualificationError):
                Q.validate_case_records("Q4", changed, *values[1:])
        # Independent processes can return in either order. Preserve the actual
        # causal starts; do not invent a post-return happens-before relation.
        for case in ("Q3", "Q4"):
            values = qualifier_fixture(case)
            record = values[0]
            record["native"]["signalReturns"][-1]["observation"]["returnedMonotonicNs"] = 179
            if case == "Q3":
                record["action"]["returnedRawNs"] = 145  # D started its reaction at141.
            self.assertEqual(Q.validate_case_records(case, *values), "INFRASTRUCTURE_REFUSAL")

    def test_only_retained_original_outcome_reaches_strict_production_data_validator(self):
        record = qualifier_fixture("Q1")[0]
        owner = object.__new__(B.Foreground)
        owner.failed, owner._aborted = False, False
        original = B.CaseOutcome(owner, record)
        owner.outcomes = [original]
        copied = original.record
        copied["closure"]["producerWait"] = 23
        with patch.object(B, "validate_production_data", return_value=(0, "SUCCESS")) as validator:
            self.assertEqual(owner.production_result(original), (0, "SUCCESS"))
            validator.assert_called_once_with(record)
            for supplied in (record, B.CaseOutcome(owner, record), B.CaseOutcome(object(), record)):
                validator.reset_mock()
                with self.subTest(supplied_type=type(supplied).__name__), self.assertRaises(B.ContextError):
                    owner.production_result(supplied)
                validator.assert_not_called()
            for attribute in ("failed", "_aborted"):
                setattr(owner, attribute, True)
                validator.reset_mock()
                with self.subTest(state=attribute), self.assertRaises(B.ContextError):
                    owner.production_result(original)
                validator.assert_not_called()
                setattr(owner, attribute, False)

    def test_expected_negative_assessor_cannot_promote_data_or_unexpected_errors_to_production_success(self):
        for case in CASES:
            record = qualifier_fixture(case)[0]
            if case in ("Q1", "Q2"):
                self.assertEqual(B.validate_production_data(record),
                                 (0, "SUCCESS") if case == "Q1" else (23, "CLOSED_FAILED_PRODUCT"))
            else:
                with self.assertRaises(B.ProductionRefusal):
                    B.validate_production_data(record)
        q4 = qualifier_fixture("Q4")[0]
        q4["closure"], q4["lossAnnotations"] = qualifier_fixture("Q3")[0]["closure"], {}
        with self.assertRaises(B.ProductionRefusal):
            B.validate_production_data(q4)  # A forged closed-D label does not make canonical125 eligible.
        with patch.object(Q, "read_file", side_effect=AssertionError("no original-file read after a refused disposition")) as read:
            for case, result in (("Q1", (23, "CLOSED_FAILED_PRODUCT")), ("Q2", (0, "SUCCESS")),
                                 ("Q3", (0, "SUCCESS")), ("Q4", (0, "SUCCESS"))):
                owner = types.SimpleNamespace(production_result=Mock(return_value=result))
                outcome = object()
                with self.subTest(case=case), self.assertRaises(Q.QualificationError):
                    Q.assess_case(owner, outcome, case)
                owner.production_result.assert_called_once_with(outcome)
            for error in (B.ContextError("CLOSE", "RESOURCE_UNKNOWN"), RuntimeError("unexpected control failure")):
                owner = types.SimpleNamespace(production_result=Mock(side_effect=error))
                with self.subTest(error=type(error).__name__), self.assertRaises(type(error)) as raised:
                    Q.assess_case(owner, object(), "Q4")
                self.assertIs(raised.exception, error)
            read.assert_not_called()
        handlers = [node for node in ast.walk(QS.definition("assess_case")) if isinstance(node, ast.ExceptHandler)]
        self.assertEqual([Source.call_name(node.type) for node in handlers], ["bridge.ProductionRefusal"])


class FakeEventControls(unittest.TestCase):
    def test_original_native_event_decoder_and_observation_clock_do_not_adopt_predictions(self):
        for code in (0, 23, 125, -15, -9):
            event = native_event(101, code)
            expected = {"rawStatus": event["data"], "kind": "EXITED" if code >= 0 else "SIGNALED",
                        "value": abs(code), "popenCode": code}
            with self.subTest(code=code):
                self.assertEqual(B.decode_exit_event(event, 101), expected)
                native = object.__new__(B.Darwin)  # No Darwin constructor or real native backend.
                native.role, native.closed, native.watched, native.events = "F", False, {101: identity()}, {}
                fake_event = types.SimpleNamespace(**event, observedRawNs=999999)
                native.kqueue = types.SimpleNamespace(control=Mock(return_value=[fake_event]))
                with patch.object(B, "shared_raw_ns", return_value=211) as clock:
                    native.poll()
                self.assertEqual(native.events[101], {"event": event, "status": expected, "observedRawNs": 211})
                clock.assert_called_once_with()
                with self.assertRaises(B.ContextError):
                    native.poll()  # Duplicate native event is not a new observation.
        valid = native_event(101, 0)
        for changed in ({**valid, "ident": 102}, {**valid, "filter": 0}, {**valid, "flags": 0x4000},
                        {**valid, "fflags": 0x80000000}, {**valid, "data": True},
                        {**valid, "data": -1}, {**valid, "data": 0x7f}):
            with self.subTest(event=changed), self.assertRaises(B.ContextError):
                B.decode_exit_event(changed, 101)

    def test_one_shot_frame_reader_refuses_replay_partial_eof_and_wrong_bindings(self):
        binding, trace, channel = "a" * 64, [], object()
        frame = B.frame_value(5, binding, {"case": "GENERATION"})

        def reader(raw):
            chunks = bytearray(raw)

            def read(_channel, count):
                data = bytes(chunks[:min(count, 3)])
                del chunks[:len(data)]
                return data

            value = B.FrameReader(channel, 5, binding, trace)
            with patch.object(B.select, "select", return_value=([channel], [], [])), \
                    patch.object(B, "receive_bytes", side_effect=read):
                returned = value.poll()
            return value, returned

        raw = B.encoded(frame)
        value, returned = reader(struct.pack("!I", len(raw)) + raw)
        self.assertEqual(returned, frame)
        self.assertEqual(trace, [B.frame_record(frame)])
        with self.assertRaises(B.ContextError):
            value.poll()
        with self.assertRaises(B.ContextError):
            B.FrameReader(channel, 5, binding, trace)
        trace.clear()
        for bad in (b"\x00", struct.pack("!I", 0), struct.pack("!I", B.FRAME_BYTES + 1),
                    struct.pack("!I", len(raw)) + raw[:-1]):
            with self.subTest(bytes=len(bad)), self.assertRaises(B.ContextError):
                reader(bad)
            self.assertEqual(trace, [])
        for changed in ({**frame, "binding": "b" * 64}, {**frame, "serial": 6},
                        {**frame, "schema": True}, {**frame, "direction": "D>P"},
                        {**frame, "kind": "RESULT"}, {**frame, "extra": None}):
            data = B.encoded(changed)
            with self.subTest(keys=tuple(changed)), self.assertRaises(B.ContextError):
                reader(struct.pack("!I", len(data)) + data)
            self.assertEqual(trace, [])

    def test_shared_d_eof_reaction_pumps_pipes_and_signals_original_p_at_most_once(self):
        producer = identity()
        service = identity(71, parent_pid=1, unique=701, parent_unique=11)
        channel = object()
        for signal_failure in (False, True):
            native = types.SimpleNamespace(events={}, poll=Mock(), same=Mock(), signal=Mock())
            if signal_failure:
                native.signal.side_effect = B.ContextError("CLOSE", "RETURN_FAILED")
            state = {"pipes": types.SimpleNamespace(pump=Mock()), "captures": types.SimpleNamespace(check=Mock()),
                     "native": native, "producer": producer, "service": service,
                     "foreground": identity(51, parent_pid=1, unique=501, parent_unique=11), "channel": channel,
                     "foregroundLoss": None, "cancelAttempted": False, "end": 1000,
                     "producerSession": {"pid": 101, "sessionId": 101, "processGroupId": 101}}
            with self.subTest(signal_failure=signal_failure), patch.object(B.select, "select", return_value=([channel], [], [])), \
                    patch.object(B, "receive_bytes", return_value=b""), patch.object(B, "shared_raw_ns", return_value=100), \
                    patch.object(B, "session_record", return_value=state["producerSession"]):
                if signal_failure:
                    with self.assertRaises(B.ContextError):
                        B.service_pump(state)
                else:
                    B.service_pump(state)
                self.assertTrue(state["cancelAttempted"])
                self.assertEqual(state["foregroundLoss"], {"kind": "WRITE_EOF", "observedRawNs": 100})
                B.service_pump(state)
            native.signal.assert_called_once_with(producer, signal.SIGTERM, 1000)
            self.assertEqual(state["pipes"].pump.call_count, 2)
            self.assertEqual(state["captures"].check.call_count, 2)
            self.assertEqual(native.poll.call_count, 2)

    def test_f_orphan_signal_requires_its_original_d_event_and_held_full_image_token(self):
        service = identity(71, parent_pid=1, unique=701, parent_unique=11)
        producer = identity(version=83)
        session = {"pid": 101, "sessionId": 101, "processGroupId": 101}

        def owner():
            native = object.__new__(B.Darwin)
            native.role, native.watched = "F", {71: service, 101: producer}
            native.events, native._tokens = {71: {"observedRawNs": 300}}, {101: object()}
            native.identity = Mock(return_value={**producer, "parentPid": 1, "parentUniqueId": 701})
            native.token = Mock(side_effect=AssertionError("do not mint a replacement orphan token"))
            native._signal_return = Mock(return_value=0)
            return native

        native = owner()
        held = native._tokens[101]
        with patch.object(B, "shared_raw_ns", return_value=400), patch.object(B, "session_record", return_value=session):
            self.assertEqual(native.signal_orphan(producer, service, session, 1000), 0)
        native.identity.assert_called_once_with(101)
        native.token.assert_not_called()
        sent = native._signal_return.call_args.args
        self.assertEqual(sent[0], producer)
        self.assertIs(sent[1], held)
        self.assertEqual(sent[2:4], (signal.SIGTERM, 1000))
        self.assertEqual(sent[4]["serviceExitObservedRawNs"], 300)
        self.assertEqual(sent[4]["checkedRawNs"], 400)
        for change in ("no_terminal", "no_original_token", "wrong_observer"):
            native = owner()
            if change == "no_terminal":
                native.events.clear()
            elif change == "no_original_token":
                native._tokens.clear()
            else:
                native.role = "D"
            with self.subTest(change=change), self.assertRaises(B.ContextError):
                native.signal_orphan(producer, service, session, 1000)
            native.identity.assert_not_called()
            native.token.assert_not_called()
            native._signal_return.assert_not_called()

    def test_actual_f_pump_cancels_original_p_once_only_after_original_d_terminal(self):
        service = identity(71, parent_pid=1, unique=701, parent_unique=11)
        producer, foreground = identity(version=83), identity(51, parent_pid=1, unique=501, parent_unique=11)
        session = {"pid": 101, "sessionId": 101, "processGroupId": 101}
        for terminal, final, p_exited, failed_signal in ((False, None, False, False), (True, {}, False, False),
                (True, None, True, False), (True, None, False, False), (True, None, False, True)):
            native = types.SimpleNamespace(events={}, poll=Mock(), same=Mock(), signal_orphan=Mock())
            if terminal:
                native.events[service["pid"]] = {"observedRawNs": 90}
            if p_exited:
                native.events[producer["pid"]] = {"observedRawNs": 95}
            if failed_signal:
                native.signal_orphan.side_effect = B.ContextError("CLOSE", "RETURN_FAILED")
            owner = object.__new__(B.Foreground)  # No original environment/native constructor is executed.
            owner.profile, owner.native, owner.foreground_identity, owner.sentinel = B.GENERATION, native, foreground, None
            owner._qualifier_action = Mock(side_effect=AssertionError("productive liveness is not qualifier injection"))
            owner.current = {"started": True, "service": service, "producer": producer, "final": final,
                             "cancelAttempted": False, "producerSession": session, "end": 1000}
            with self.subTest(terminal=terminal, final=final, p_exited=p_exited, failed_signal=failed_signal), \
                    patch.object(B, "shared_raw_ns", return_value=100):
                if failed_signal:
                    with self.assertRaises(B.ContextError):
                        owner._pump_case()
                else:
                    owner._pump_case()
                owner._pump_case()
            should_signal = terminal and final is None and not p_exited
            self.assertEqual(owner.current["cancelAttempted"], should_signal)
            if should_signal:
                native.signal_orphan.assert_called_once_with(producer, service, session, 1000)
            else:
                native.signal_orphan.assert_not_called()
            self.assertEqual(native.poll.call_count, 2)
            self.assertEqual(native.same.call_args_list, [unittest.mock.call(foreground)] * 2)
            owner._qualifier_action.assert_not_called()


class OriginalReturnClockControls(unittest.TestCase):
    def test_genuine_owned_command_samples_raw_return_before_any_original_receipt_read(self):
        invocation, purpose = "1" * 32, "dependency-maintenance-prerequisites"
        parent = Path("/controlled/operation")
        argv = [G.PYTHON, "-I", "-B", "-S", str(ROOT / GENERATION_PATH), "_prerequisites"]
        for code, case in ((0, "Q1"), (23, "Q2")):
            _code, receipt, context, _entry = canonical_fixture(case)
            receipt.update(id=invocation, purpose=purpose, requestedArgv=argv)
            raw, trace, returns = G.encoded(receipt), [], []

            def execute(_args):
                trace.append("execute-return")
                return code

            def clock():
                trace.append("raw-return")
                return 7 * NS

            def original(path, limit):
                trace.append("original-receipt")
                self.assertEqual(path, parent / "state/evidence" / invocation / "receipt.json")
                self.assertEqual(limit, 4 * G.MIB)
                return raw, {}

            runner = types.SimpleNamespace(execute=Mock(side_effect=execute))
            with self.subTest(code=code), patch.object(G, "environment", return_value=contextlib.nullcontext()) as environment, \
                    patch.object(G, "os", types.SimpleNamespace(environ={})), \
                    patch.object(G.uuid, "uuid4", return_value=types.SimpleNamespace(hex=invocation)), \
                    patch.object(G, "shared_raw_ns", side_effect=clock), patch.object(G, "read_file", side_effect=original):
                if code:
                    with self.assertRaises(G.ClosedProductFailure) as raised:
                        G.owned_command(runner, parent, context, purpose, argv, G.PREREQUISITES_SECONDS, command_returns=returns)
                    self.assertEqual((raised.exception.code, raised.exception.receipt, raised.exception.receipt_hash),
                                     (code, receipt, G.digest(raw)))
                else:
                    self.assertEqual(G.owned_command(runner, parent, context, purpose, argv, G.PREREQUISITES_SECONDS,
                                                    command_returns=returns), (receipt, G.digest(raw)))
            self.assertEqual(trace, ["execute-return", "raw-return", "original-receipt"])
            environment.assert_called_once_with({"P2PKIT_AUDIT_STATE_DIR": str(parent / "state")})
            runner.execute.assert_called_once()
            arguments = runner.execute.call_args.args[0]
            self.assertEqual(vars(arguments), {"cwd": str(ROOT), "wrapper": str(ROOT / "gradlew"), "id": invocation,
                "purpose": purpose, "kind": "command", "argv": argv, "timeout": G.PREREQUISITES_SECONDS,
                "stop_timeout": G.STOP_SECONDS, "receipt": None})
            self.assertEqual(returns, [{"invocationId": invocation, "purpose": purpose, "receiptSha256": G.digest(raw),
                                       "code": code, "returnedRawNs": 7 * NS}])

    def test_original_step_and_last_genuine_return_keep_exact_nonrenewable_finalization_boundary(self):
        _request, _env, _github, allocation = allocation_fixture(B.GENERATION)
        step = allocation["startedMonotonicNs"] + NS
        boundary = step + (G.STEP_SECONDS - (G.FINAL_RESERVE - G.UPLOAD_SECONDS)) * NS
        with patch.object(G, "budget") as job_budget:
            with patch.object(G, "shared_raw_ns", return_value=boundary - 1):
                G.generation_budget(allocation, step, G.FINAL_RESERVE)
            with patch.object(G, "shared_raw_ns", return_value=boundary), self.assertRaises(G.UpdateError) as raised:
                G.generation_budget(allocation, step, G.FINAL_RESERVE)
            self.assertEqual(str(raised.exception), "GENERATOR_STEP_DEADLINE")
            self.assertEqual(job_budget.call_args_list, [unittest.mock.call(allocation, G.FINAL_RESERVE)] * 2)
        returned, reserve = step + 10 * NS, G.EXPORT_SECONDS + G.UPLOAD_SECONDS
        with patch.object(G, "budget") as job_budget:
            with patch.object(G, "shared_raw_ns", return_value=returned + 300 * NS - 1):
                G.generation_budget(allocation, step, reserve, returned_ns=returned)
            with patch.object(G, "shared_raw_ns", return_value=returned + 300 * NS), self.assertRaises(G.UpdateError) as raised:
                G.generation_budget(allocation, step, reserve, returned_ns=returned)
            self.assertEqual(str(raised.exception), "GENERATOR_FINALIZATION_DEADLINE")
            self.assertEqual(job_budget.call_args_list, [unittest.mock.call(allocation, reserve)] * 2)
        for changed in (True, 1.0, step - 1, returned + 1):
            with self.subTest(returned=changed), patch.object(G, "budget"), \
                    patch.object(G, "shared_raw_ns", return_value=returned), self.assertRaises(G.UpdateError):
                G.generation_budget(allocation, step, reserve, returned_ns=changed)
        for source, name in ((GS, "owned_command"), (QS, "produce")):
            node = source.definition(name)
            blocks = [item for item in ast.walk(node) if isinstance(item, ast.With) and
                      any(Source.call_name(call.func) == "runner.execute" for _line, _name, call in source.calls(item))]
            self.assertEqual(len(blocks), 1)
            body = blocks[0].body
            execution = next(index for index, item in enumerate(body) if isinstance(item, ast.Assign) and
                             isinstance(item.value, ast.Call) and Source.call_name(item.value.func) == "runner.execute")
            next_statement = body[execution + 1]
            self.assertIsInstance(next_statement, ast.Assign)
            self.assertEqual([Source.call_name(target) for target in next_statement.targets], ["returned_raw_ns"])
            self.assertEqual(Source.call_name(next_statement.value.func), "shared_raw_ns")


class OriginalCallGraphControls(unittest.TestCase):
    def named(self, source, node, name):
        return [call for _line, found, call in source.calls(node) if found == name]

    def one(self, source, node, name):
        calls = self.named(source, node, name)
        self.assertEqual(len(calls), 1, name)
        return calls[0]

    def ordered(self, *nodes):
        for first, second in zip(nodes, nodes[1:]):
            self.assertLess(first.lineno, second.lineno)

    def endpoint_write(self, source, node, attribute):
        calls = [call for call in self.named(source, node, "write_new")
                 if Source.call_name(call.args[0]) == "endpoint." + attribute]
        self.assertEqual(len(calls), 1, attribute)
        return calls[0]

    def test_only_original_p_initializes_context_before_ready_and_executes_after_start(self):
        for source in (GS, QS):
            functions = [node for node in source.tree.body if isinstance(node, ast.FunctionDef)]
            producer = source.definition("produce")
            for name in ("runner.initialize", "runner.context_at"):
                self.assertEqual([node.name for node in functions if self.named(source, node, name)], ["produce"])
            execute_owner = "owned_command" if source is GS else "produce"
            self.assertEqual([node.name for node in functions if self.named(source, node, "runner.execute")], [execute_owner])
            initialize = self.one(source, producer, "runner.initialize")
            context = self.one(source, producer, "runner.context_at")
            entry = self.endpoint_write(source, producer, "canonical_entry_path")
            ready = self.one(source, producer, "endpoint.ready")
            commands = self.named(source, producer, "owned_command" if source is GS else "runner.execute")
            self.assertEqual(len(commands), 2 if source is GS else 1)
            result = self.endpoint_write(source, producer, "producer_result_path")
            complete = self.one(source, producer, "endpoint.complete")
            self.ordered(initialize, context, entry, ready, *commands, result, complete)
            self.assertEqual(Source.call_name(ready.args[0]), "endpoint.canonical_entry_path")
            self.assertEqual(Source.call_name(complete.args[0]), "endpoint.producer_result_path")
        self.assertFalse(any(name.endswith((".initialize", ".context_at", ".execute"))
                             for _line, name, _call in BS.calls(BS.tree)))
        ready = BS.definition("ready", "Producer")
        frames = self.named(BS, ready, "read_frame")
        self.assertEqual([call.args[1].value for call in frames], [6])
        self.assertIn("self.started = True", BS.segment(ready))

    def test_productive_baseline_supported_generator_and_narrow_local_failure_catch_stay_in_p(self):
        producer, foreground = GS.definition("produce"), GS.definition("generate")
        commands = self.named(GS, producer, "owned_command")
        self.assertEqual([call.args[3].value for call in commands],
                         ["dependency-maintenance-prerequisites", "dependency-maintenance-generator"])
        self.assertEqual([Source.call_name(call.args[5]) for call in commands],
                         ["PREREQUISITES_SECONDS", "PRODUCT_SECONDS"])
        self.assertEqual([keyword.arg for keyword in commands[1].keywords], ["command_returns"])
        self.assertEqual(Source.call_name(commands[1].keywords[0].value), "command_returns")
        generator_argv = GS.segment(commands[1].args[4])
        self.assertEqual(generator_argv,
                         '[str(candidate / "scripts/prepare-dependency-update.sh"), request["dependency_base_sha"]]')
        baseline = self.one(GS, producer, "runner.report_snapshot")
        baseline_writes = [call for call in self.named(GS, producer, "write_new")
                           if "candidate-report-baseline.json" in Source.strings(call.args[0])]
        self.assertEqual(len(baseline_writes), 1)
        retained = self.named(GS, producer, "retain_candidate_reports")
        self.assertEqual(len(retained), 2)
        self.ordered(commands[0], baseline, baseline_writes[0], commands[1], retained[0])
        handlers = [node for node in ast.walk(producer) if isinstance(node, ast.ExceptHandler)]
        self.assertEqual([Source.call_name(node.type) for node in handlers], ["ClosedProductFailure"])
        self.assertEqual(handlers[0].name, "original")
        self.assertIn("failed = original", GS.segment(handlers[0]))
        self.assertIn("failed.receipt", GS.segment(handlers[0]))
        self.assertFalse(self.named(GS, foreground, "ClosedProductFailure"))
        self.assertFalse(any(Source.call_name(node.type) == "ClosedProductFailure"
                             for node in ast.walk(foreground) if isinstance(node, ast.ExceptHandler)))
        self.assertEqual(len(self.named(GS, GS.tree, "ClosedProductFailure")), 1)

    def test_original_f_recipient_prefix_closure_case_finish_and_actual_export_precede_outputs(self):
        foreground = GS.definition("generate")
        validation = self.one(GS, GS.tree, "exporter.validate_recipient")
        constructor = self.one(GS, foreground, "bridge.Foreground")
        capture = [node for node in ast.walk(foreground) if isinstance(node, ast.With) and
                   any(Source.call_name(item.context_expr.func) == "contextlib.redirect_stdout"
                       for item in node.items if isinstance(item.context_expr, ast.Call))]
        self.assertEqual(len(capture), 1)
        self.assertLess(validation.lineno, capture[0].end_lineno)
        self.assertLess(capture[0].end_lineno, constructor.lineno)
        export = self.one(GS, GS.tree, "exporter.export_encrypted")
        output = self.one(GS, foreground, "stream.write")
        self.ordered(constructor, self.one(GS, foreground, "owner.prepare_case"),
                     self.one(GS, foreground, "owner.run_case"), self.one(GS, foreground, "owner.production_result"),
                     self.one(GS, foreground, "owner.finish"), self.one(GS, foreground, "retain_bridge_files"), export, output)
        recipient = [node for node in ast.walk(foreground) if isinstance(node, ast.Assign) and
                     any(Source.call_name(target) == "recipient" for target in node.targets)]
        self.assertEqual(len(recipient), 1)
        self.assertIs(recipient[0].value, validation)
        self.assertEqual(Source.call_name(export.args[2]), "recipient")
        output_records = [call for call in self.named(GS, foreground, "write_new")
                          if "generator-success.json" in Source.strings(call.args[0])]
        self.assertEqual(len(output_records), 1)
        self.ordered(export, output_records[0], output)
        self.assertIn("successSha256=", Source.strings(output))
        self.assertIn("failedProductSha256=", Source.strings(output))

        prepare = QS.definition("prepare")
        validation = self.one(QS, QS.tree, "context.exporter.validate_recipient")
        constructor = self.one(QS, prepare, "bridge.Foreground")
        closed = [call for call in self.named(QS, prepare, "require")
                  if "FOREGROUND_PREFIX_CLOSE" in Source.strings(call)]
        self.assertEqual(len(closed), 1)
        self.ordered(validation, closed[0], constructor)
        qualify = QS.definition("qualify")
        self.ordered(self.one(QS, qualify, "prepare"), self.one(QS, qualify, "prepare_fixture"),
                     self.one(QS, qualify, "context.owner.prepare_case"), self.one(QS, qualify, "context.owner.run_case"),
                     self.one(QS, qualify, "assess_case"), self.one(QS, qualify, "context.owner.finish"),
                     self.one(QS, qualify, "finish_export"))
        loops = [node for node in ast.walk(qualify) if isinstance(node, ast.For)]
        self.assertEqual(len(loops), 1)
        self.assertEqual(Source.call_name(loops[0].iter), "CASES")
        finish = QS.definition("finish_export")
        exported = self.one(QS, QS.tree, "context.exporter.export_encrypted")
        self.assertEqual(Source.call_name(exported.args[2]), "context.recipient_original")
        self.assertIn("context.recipient is context.recipient_original", QS.segment(finish))
        self.ordered(self.one(QS, finish, "validate_finish"), self.one(QS, finish, "collect_evidence"),
                     self.one(QS, finish, "freeze_evidence"), exported, self.one(QS, finish, "output_snapshot"),
                     self.one(QS, finish, "context.output.emit"))
        self.assertLess(QS.segment(finish).index("context.export_called = True"),
                        QS.segment(finish).index("context.exporter.export_encrypted("))
        self.assertFalse(any(name.endswith((".validate_recipient", ".export_encrypted"))
                             for _line, name, _call in BS.calls(BS.tree)))

    def test_native_prepare_is_passive_and_d_binds_original_p_before_forwarding_start(self):
        constructor = BS.definition("__init__", "Foreground")
        prepare, run = BS.definition("prepare_case", "Foreground"), BS.definition("_run_current_case", "Foreground")
        forbidden = {"Darwin", "Admin", "capture_fixed", "subprocess.Popen", "self._start_sentinel"}
        self.assertFalse(forbidden & {name for _line, name, _call in BS.calls(constructor)})
        self.assertEqual(len(self.named(BS, prepare, "Darwin")), 1)
        self.assertFalse({"Admin", "subprocess.Popen", "self._start_sentinel", "admin.bootstrap"} &
                         {name for _line, name, _call in BS.calls(prepare)})
        self.assertIn("if self.native is None:", BS.segment(prepare))
        self.assertIn("self.native.same(self.foreground_identity)", BS.segment(prepare))
        self.ordered(self.one(BS, run, "Admin"), self.one(BS, run, "admin.create"), self.one(BS, run, "admin.bootstrap"))
        service = BS.definition("service")
        popen = self.one(BS, service, "subprocess.Popen")
        options = {keyword.arg: keyword.value for keyword in popen.keywords}
        self.assertIs(options["start_new_session"].value, True)
        self.assertIs(options["close_fds"].value, True)
        self.assertEqual([Source.call_name(node) for node in options["pass_fds"].elts], ["child_fd"])
        self.assertNotIn("preexec_fn", options)
        self.assertTrue({"-I", "-B", "-S", "_produce"} <= Source.strings(popen.args[0]))
        read = {call.args[1].value: call for call in self.named(BS, service, "read_frame")}
        sent = {call.args[1].value: call for call in self.named(BS, service, "send_frame")}
        self.assertEqual(set(read), {2, 3, 5, 7})
        self.assertEqual(set(sent), {1, 4, 6, 8})
        birth = [call for call in self.named(BS, service, "native.identity")
                 if Source.call_name(call.args[0]) == "process.pid"]
        self.assertEqual(len(birth), 1)
        observed = self.one(BS, BS.tree, "observe_startup_child")
        watch = [call for call in self.named(BS, service, "native.watch")
                 if Source.call_name(call.args[0]) == "producer_identity"]
        self.assertEqual(len(watch), 1)
        self.ordered(popen, birth[0], read[3], observed, self.one(BS, service, "validate_ready"),
                     watch[0], sent[4], read[5], sent[6], read[7])
        self.assertFalse(self.named(BS, run, "observe_startup_child"))

    def test_final_data_never_replaces_direct_wait_native_terminals_or_original_capture_close(self):
        service = BS.definition("service")
        final = [call for call in self.named(BS, service, "send_frame") if call.args[1].value == 8][0]
        waits = [call for call in self.named(BS, service, "pipes.finish") if call.lineno < final.lineno]
        native_close = [call for call in self.named(BS, service, "native.close") if call.lineno < final.lineno]
        capture_close = [call for call in self.named(BS, service, "captures.close") if call.lineno < final.lineno]
        self.assertEqual((len(waits), len(native_close), len(capture_close)), (1, 1, 1))
        self.ordered(self.one(BS, service, "wait_eof"), waits[0], self.one(BS, service, "native.wait"),
                     native_close[0], capture_close[0], final)
        pumped = [call for _line, name, call in BS.calls(service) if name in ("read_frame", "wait_eof", "pipes.finish") and
                  any("service_pump" in {called for _line, called, _node in BS.calls(arg)} for arg in call.args)]
        self.assertEqual([Source.call_name(call.func) for call in pumped], ["read_frame", "wait_eof", "pipes.finish"])
        complete = BS.definition("complete", "Producer")
        delivery = [call for call in self.named(BS, complete, "send_frame") if call.args[1].value == 7][0]
        self.ordered(self.one(BS, complete, "validate_producer_result"), self.one(BS, complete, "self.native.close"),
                     self.one(BS, complete, "self.captures.close"), delivery)
        run = BS.definition("_run_current_case", "Foreground")
        text = BS.segment(run)
        self.assertIn('all(value["pid"] in self.native.events for value in required)', text)
        self.assertIn("(reader.value is not None or reader.eof)", text)
        self.assertIn('state["final"] is not None or expected_loss', text)
        self.ordered(self.one(BS, run, "admin.retire"), self.one(BS, run, "admin.close"),
                     self.one(BS, run, "CaseOutcome"), self.one(BS, run, "self.outcomes.append"))
        self.assertIn('result["commands"][-1]["returnedRawNs"] + 300 * NS', text)
        self.assertNotIn('result["completedRawNs"] +', text)
        for node in (service, complete, run):
            self.assertIn('result["commands"][-1]["returnedRawNs"] + 300 * NS', BS.segment(node))
            self.assertNotIn('result["completedRawNs"] +', BS.segment(node))
        closed = BS.definition("_closed_files", "Foreground")
        self.assertFalse(any(name.endswith(".rglob") for _line, name, _call in BS.calls(closed)))
        self.assertIn('optional.update(SERVICE_FILES)', BS.segment(closed))
        self.assertIn('required.add("service-final.json")', BS.segment(closed))
        self.assertIn('"native-exit.json"', BS.segment(closed))
        self.assertIn('not os.path.lexists(directory / "service-final.json")', QS.segment(QS.definition("assess_case")))
        self.assertIn('"bridge/sentinel/native-exit.json"', QS.segment(QS.definition("validate_finish")))


def workflow_parts(relative):
    text = (ROOT / relative).read_text(encoding="utf-8")
    header, steps = text.split("    steps:\n")
    return header, re.split(r"(?m)^      - name: ", steps)[1:]


class QualifierWorkflowClockControls(unittest.TestCase):
    def test_only_exact_manual_qualifier_job_and_original_success_allow_encrypted_upload(self):
        header, steps = workflow_parts(QUALIFIER_WORKFLOW)
        header = "\n".join(line for line in header.splitlines() if line.strip() and not line.lstrip().startswith("#"))
        expected_header = """name: Dependency maintenance context qualification
on:
  push:
    branches: ['work/release-foundation-dependency-context-*']
    paths: [.github/workflows/dependency-update-context-qualification.yml]
  workflow_dispatch:
    inputs:
      source_sha:
        description: Exact independently reviewed controller and qualifier commit at this ref
        required: true
        type: string
      source_tree:
        description: Exact independently reviewed controller and qualifier tree
        required: true
        type: string
permissions:
  contents: read
env:
  PYTHONDONTWRITEBYTECODE: '1'
  PYTHONUNBUFFERED: '1'
  DEVELOPER_DIR: /Applications/Xcode_26.5.app/Contents/Developer
jobs:
  dependency_context_qualification:
    if: ORIGINAL_MANUAL_CONDITION
    concurrency:
      group: p2pkit-nonphysical-heavy
      queue: max
      cancel-in-progress: false
    runs-on: macos-26
    timeout-minutes: 41
    defaults:
      run:
        shell: bash""".replace("ORIGINAL_MANUAL_CONDITION", QUALIFIER_JOB_IF)
        self.assertEqual(header, expected_header)
        self.assertEqual(len(steps), 6)
        self.assertEqual([re.findall(r"(?m)^        timeout-minutes: (\d+)$", step) for step in steps],
                         [["1"], ["3"], ["29"], ["1"], ["5"], ["1"]])
        self.assertEqual([re.findall(r"(?m)^        ([a-z-]+):", step) for step in steps], [
            ["timeout-minutes", "shell", "env", "run"], ["timeout-minutes", "uses", "with"],
            ["id", "timeout-minutes", "env", "run"], ["id", "if", "timeout-minutes", "env", "run"],
            ["id", "if", "timeout-minutes", "uses", "with"], ["if", "timeout-minutes", "env", "run"]])
        self.assertEqual([re.findall(r"(?m)^        id: (.+)$", step) for step in steps],
                         [[], [], ["qualification"], ["before_upload"], ["encrypted"], []])
        self.assertEqual(re.findall(r"(?m)^        shell: (.+)$", steps[0]), [B.INTERPRETER + " -I -B -S {0}"])
        for index, command in ((2, "qualify"), (3, "before-upload"), (5, "after-upload")):
            self.assertEqual(re.findall(r"(?m)^        run: (.+)$", steps[index]),
                             [B.INTERPRETER + " -I -B -S controller/" + QUALIFIER_PATH + " " + command])
        checkout = dict(re.findall(r"(?m)^          ([a-z-]+): (.+)$", steps[1]))
        self.assertEqual(checkout, {"ref": "${{ github.sha }}", "path": "controller", "fetch-depth": "1",
                                    "fetch-tags": "false", "persist-credentials": "false"})
        uses = [re.findall(r"(?m)^        uses: ([^ #]+)", step) for step in steps]
        self.assertEqual(uses, [[], ["actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"], [], [],
                               ["actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"], []])
        base = "!cancelled() && steps.qualification.outcome == 'success'"
        joined = ("steps.before_upload.outputs.uploadAllowed != '' && "
                  "steps.before_upload.outputs.uploadAllowed == steps.qualification.outputs.qualificationSha256")
        expressions = [[], [], [], ["${{ " + base + " && steps.qualification.outputs.qualificationSha256 != '' }}"],
            ["${{ " + base + " && steps.before_upload.outcome == 'success' && " + joined + " }}"],
            ["${{ " + base + " && steps.before_upload.outcome == 'success' && steps.encrypted.outcome == 'success' && " + joined + " }}"]]
        self.assertEqual([re.findall(r"(?m)^        if: (.+)$", step) for step in steps], expressions)
        upload = dict(re.findall(r"(?m)^          ([a-z-]+): (.+)$", steps[4]))
        self.assertEqual(upload, {"name": "dependency-context-evidence-${{ github.run_id }}-${{ github.run_attempt }}",
            "path": "|", "if-no-files-found": "error", "retention-days": "14", "compression-level": "0",
            "overwrite": "false", "include-hidden-files": "false"})
        self.assertEqual(re.findall(r"(?m)^            (\$\{\{ env\..+)$", steps[4]),
            ["${{ env.P2PKIT_DEPENDENCY_CONTEXT_OPERATION }}/outputs/encrypted/" + name
             for name in ("evidence.tar.gz.gpg", "manifest.json")])
        request = {"P2PKIT_DEPENDENCY_CONTEXT_REQUEST": "${{ toJSON(inputs) }}"}
        original_return = {**request, "P2PKIT_DEPENDENCY_CONTEXT_STEP_OUTCOME": "${{ steps.qualification.outcome }}",
                           "P2PKIT_DEPENDENCY_CONTEXT_QUALIFICATION_SHA256": "${{ steps.qualification.outputs.qualificationSha256 }}"}
        after = {**original_return, "P2PKIT_DEPENDENCY_CONTEXT_UPLOAD_ALLOWED": "${{ steps.before_upload.outputs.uploadAllowed }}",
            "P2PKIT_DEPENDENCY_CONTEXT_UPLOAD_OUTCOME": "${{ steps.encrypted.outcome }}",
            "P2PKIT_DEPENDENCY_CONTEXT_ARTIFACT_ID": "${{ steps.encrypted.outputs.artifact-id }}",
            "P2PKIT_DEPENDENCY_CONTEXT_ARTIFACT_DIGEST": "${{ steps.encrypted.outputs.artifact-digest }}"}
        self.assertEqual([dict(re.findall(r"(?m)^          ([A-Z_0-9]+): (.+)$", step)) for step in steps],
                         [request, {}, request, original_return, {}, after])

    def test_both_original_allocations_use_schema2_raw_clock_and_never_refresh_original_fields(self):
        for relative in (".github/workflows/dependency-update-candidate.yml", QUALIFIER_WORKFLOW):
            _header, steps = workflow_parts(relative)
            raw = steps[0].split("        run: |\n", 1)[1]
            snippet = "\n".join(line[10:] if line.startswith(" " * 10) else line for line in raw.splitlines())
            tree = ast.parse(snippet, filename=relative + ":original-allocation")  # Source inspection, not execution.
            calls = Source.calls(tree)
            self.assertEqual(len([name for _line, name, _call in calls if name == "time.clock_gettime_ns"]), 1)
            self.assertFalse(any(name in ("time.monotonic", "time.monotonic_ns", "time.perf_counter", "time.perf_counter_ns")
                                 for _line, name, _call in calls))
            raw_call = next(call for _line, name, call in calls if name == "time.clock_gettime_ns")
            self.assertEqual([Source.call_name(arg) for arg in raw_call.args], ["time.CLOCK_MONOTONIC_RAW"])
            if relative == QUALIFIER_WORKFLOW:
                assignments = {node.targets[0].id: node.value for node in tree.body if isinstance(node, ast.Assign) and
                               len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)}
                self.assertEqual(ast.literal_eval(assignments["CLOCK_SCHEMA"]), 2)
                self.assertEqual(ast.literal_eval(assignments["CLOCK_DOMAIN"]), CLOCK_DOMAIN)
                self.assertEqual(ast.literal_eval(assignments["SCOPE"]), "MANUAL_DEPENDENCY_CONTEXT_QUALIFICATION_V1")
                allocations = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign) and
                               any(Source.call_name(target) == "allocation" for target in node.targets)]
                self.assertEqual(len(allocations), 1)
                self.assertEqual(Source.call_name(allocations[0].func), "dict")
                fields = {item.arg: ast.unparse(item.value) for item in allocations[0].keywords}
                self.assertEqual(fields, {"schema": "CLOCK_SCHEMA", "clockDomain": "CLOCK_DOMAIN", "scope": "SCOPE",
                    "source": "request['source_sha']", "sourceTree": "request['source_tree']", "runId": "env['GITHUB_RUN_ID']",
                    "runAttempt": "env['GITHUB_RUN_ATTEMPT']", "startedMonotonicNs": "started", "startedEpochNs": "wall"})
                for name in ("started", "wall"):
                    self.assertEqual(len([node for node in ast.walk(tree) if isinstance(node, ast.Name) and
                                          node.id == name and isinstance(node.ctx, ast.Store)]), 1)
                captured = [node for node in ast.walk(tree) if isinstance(node, ast.Assign) and
                            any(isinstance(target, ast.Tuple) and [Source.call_name(item) for item in target.elts] ==
                                ["started", "wall"] for target in node.targets)]
                self.assertEqual(len(captured), 1)
                self.assertEqual([Source.call_name(item.func) for item in captured[0].value.elts],
                                 ["shared_raw_ns", "time.time_ns"])
                self.assertLess(captured[0].lineno, allocations[0].lineno)
            else:
                allocations = [node.value for node in ast.walk(tree) if isinstance(node, ast.Assign) and
                               any(Source.call_name(target) == "record" for target in node.targets)]
                self.assertEqual(len(allocations), 1)
                fields = {key.value: value for key, value in zip(allocations[0].keys, allocations[0].values)}
                self.assertEqual(set(fields), {"schema", "clockDomain", "source", "sourceTree", "runId", "runAttempt",
                                                "startedMonotonicNs", "startedEpochNs"})
                self.assertEqual(ast.literal_eval(fields["schema"]), 2)
                self.assertEqual(ast.literal_eval(fields["clockDomain"]), CLOCK_DOMAIN)
                self.assertEqual(ast.unparse(fields["sourceTree"]), "request['controller_tree']")
                self.assertIs(fields["startedMonotonicNs"], raw_call)
                self.assertEqual(Source.call_name(fields["startedEpochNs"].func), "time.time_ns")
        foreground = BS.segment(BS.definition("__init__", "Foreground"))
        self.assertIn('allocation["startedMonotonicNs"] + POLICY_EXPIRES * NS - allocation["startedEpochNs"]', foreground)
        prepare = QS.segment(QS.definition("prepare"))
        self.assertIn('context.allocation["startedMonotonicNs"] + POLICY_EXPIRES * NS -', prepare)
        self.assertIn('context.allocation["startedEpochNs"]', prepare)
        self.assertNotIn("now + POLICY_EXPIRES", prepare)

    def test_heavy_queue_change_adds_only_fixed_qualifier_job_and_actor_bound_condition(self):
        raw = (ROOT / "scripts/check-heavy-job-queue-policy.rb").read_bytes()
        additions = [b'        "dependency-update-context-qualification.yml" => {"dependency_context_qualification" => nil},\n',
                     ('        ["dependency-update-context-qualification.yml", "dependency_context_qualification"] => "' +
                      QUALIFIER_JOB_IF + '",\n').encode("ascii")]
        for line in additions:
            self.assertEqual(raw.count(line), 1)
            raw = raw.replace(line, b"")
        # Preserve every pre-existing participant, supersession/routing rule and
        # generic nonparticipant-reserved-group refusal, not just selected lines.
        self.assertEqual(hashlib.sha256(raw).hexdigest(),
                         "d4f2c914cd8374bfe47e526d44bc5e07cc5d3f0f5980be199bbae6cafc56d38f")


FAILURE_GROUPS = {
    "CANONICAL_RETURN": ("CASE_SUPPORTED", "RETURN_CODE_TYPE", "RECEIPT_TYPE"),
    "CANONICAL_RECEIPT": ("RETURN_CODE", "SCHEMA", "INVOCATION_ID", "JOB_ID", "COMMAND_KIND", "PURPOSE",
        "PRODUCT_ARGV", "CONTROLLER_PID", "CWD", "WRAPPER", "HOST", "GRADLE_HOME", "SOURCE_SNAPSHOTS",
        "SOURCE_UNCHANGED", "PRODUCT_PID", "PRODUCT_EXIT", "STOP_EXIT", "FINAL_EXIT", "OWNED_SURVIVORS",
        "OWNERSHIP_DISCOVERY"),
    "CANONICAL_STOP": ("STOP_ARGV",),
    "CANONICAL_CLOSED_PRODUCT": ("ERRORS_EMPTY", "CANCEL_SIGNALS_ABSENT", "CANCEL_REQUEST_ABSENT"),
    "CANONICAL_CANCELLATION": ("CANCELLATION_ERRORS", "CANCEL_SIGNALS", "CANCEL_REQUEST"),
}
FAILURE_KIND = "QUALIFICATION_FAILURE_DIAGNOSTIC"
FAILURE_FILES = {"P": "producer-failure.json", "D": "service-failure.json"}


def failure_fixture(case="Q1"):
    """Synthetic DATA, not a validate_prepared admission or a native owner."""
    record, entry, _producer, _receipt, _context, _start, _ready = qualifier_fixture(case)
    prepared = dict.fromkeys(B.PREPARED_KEYS)
    prepared.update(schema=1, scope=B.QUALIFICATION.scope, case=case, binding=entry["binding"],
        caseInputSha256=entry["caseInputSha256"], caseEndNs=300, directoryIdentity=[17, 29],
        source={"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": B.digest(b""),
                "files": {BRIDGE_PATH: "c" * 64, QUALIFIER_PATH: "d" * 64}})
    state = {"directory": Path("/controlled/operation/bridge/cases") / case, "prepared": prepared,
        "inputs": {"case": case, "binding": prepared["binding"]}, "inputHash": prepared["caseInputSha256"],
        "end": prepared["caseEndNs"], "action": copy.deepcopy(record["action"]), "final": None,
        "service": record["native"]["service"], "producer": record["native"]["producer"],
        "product": record["native"]["product"]}
    events = {state[role]["pid"]: copy.deepcopy(record["native"][role + "Native"])
              for role in ("service", "producer", "product")}
    return prepared, state, events


def failure_marker(prepared, role):
    return {"schema": 1, "kind": FAILURE_KIND, "scope": B.QUALIFICATION.scope, "case": prepared["case"],
        "role": role, "binding": prepared["binding"], "caseInputSha256": prepared["caseInputSha256"],
        "sourceSha256": B.digest(B.encoded(prepared["source"])), "sites": [{"module": "BRIDGE", "line": 123}],
        "truncated": False, "predicates": []}


class FailureProvenanceControls(unittest.TestCase):
    def attach_hint(self, prepared, state, events, raws=None, *, mode=0o600, metadata=None, path_metadata=None, read_error=None):
        if raws is None:
            raws = {name: B.encoded(failure_marker(prepared, role)) for role, name in FAILURE_FILES.items()}
        streams, stamps, active = {}, {}, []
        self.marker_reads, self.marker_closed = {}, []
        control = self

        class MarkerStream(io.BytesIO):
            def __init__(self, name, raw):
                super().__init__(raw)
                self.name = name

            def read(self, limit=-1):
                control.assertEqual(limit, 4097)
                control.marker_reads[self.name].append(limit)
                if read_error is not None:
                    raise read_error
                return super().read(limit)

        def open_marker(path, flags):
            self.assertEqual(flags, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            self.assertEqual(path.parent, state["directory"])
            self.assertIn(path.name, FAILURE_FILES.values())
            value = raws[path.name]
            if isinstance(value, BaseException):
                raise value
            fd = 81 + len(streams)
            streams[fd] = MarkerStream(path.name, value)
            self.marker_reads[path.name] = []
            stamps[fd] = dict(st_dev=17, st_ino=fd, st_mode=stat.S_IFREG | mode, st_uid=501, st_gid=20,
                             st_nlink=1, st_size=len(value), st_mtime_ns=10, st_ctime_ns=11)
            stamps[fd].update(metadata or {})
            active[:] = [fd]
            return fd

        def fdopen(fd, mode, *, closefd):
            self.assertEqual((mode, closefd), ("rb", False))
            return streams[fd]

        def close(fd):
            self.marker_closed.append(streams[fd].name)
            streams[fd].close()

        def path_stat():
            if isinstance(path_metadata, BaseException):
                raise path_metadata
            return types.SimpleNamespace(**{**stamps[active[0]], **(path_metadata or {})})

        error = B.ContextError("CLOSE", "FINAL_FRAME_MISSING", private="not-for-output")
        with patch.object(B, "shared_raw_ns", return_value=100), \
                patch.object(B, "private_directory", return_value=prepared["directoryIdentity"]), \
                patch.object(B, "physical", side_effect=lambda path: Path(path)), \
                patch.object(B.os, "getuid", return_value=501), patch.object(B.os, "open", side_effect=open_marker), \
                patch.object(B.os, "fdopen", side_effect=fdopen), patch.object(B.os, "close", side_effect=close), \
                patch.object(B.os, "fstat", side_effect=lambda fd: types.SimpleNamespace(**stamps[fd])), \
                patch.object(Path, "lstat", side_effect=path_stat):
            B.attach_failure_hint(B.QUALIFICATION, state, events, error)
        self.assertEqual(sorted(self.marker_closed), sorted(self.marker_reads))
        self.assertTrue(all(stream.closed for stream in streams.values()))
        return error

    def test_original_traceback_sites_are_finite_exact_source_tokens_without_private_text(self):
        class UnprintableError(RuntimeError):
            def __str__(self):
                raise AssertionError("diagnostics must not format exceptions")

            __repr__ = __str__

        caught = None
        try:
            B.require(False, "CLOSE", "FINAL_FRAME_MISSING")
        except B.ContextError as original:
            caught = original
        observed = B.failure_sites(caught, B.QUALIFICATION)
        leaf = caught.__traceback__
        while leaf.tb_next is not None:
            leaf = leaf.tb_next
        self.assertEqual(observed, {"sites": [{"module": "BRIDGE", "line": leaf.tb_lineno}], "truncated": False})
        self.assertEqual(leaf.tb_frame.f_code.co_filename, str(ROOT / BRIDGE_PATH))
        with patch.object(B, "ROOT", Path("/different/source/root")):
            self.assertEqual(B.failure_sites(caught, B.QUALIFICATION), {"sites": [], "truncated": False})
        try:
            Q.require(False, "not-for-output")
        except Q.QualificationError as original:
            caller = B.failure_sites(original, B.QUALIFICATION)
        self.assertEqual([row["module"] for row in caller["sites"]], ["CALLER"])
        try:
            raise UnprintableError("private message, path and locals must stay absent")
        except UnprintableError as original:
            self.assertEqual(B.failure_sites(original, B.QUALIFICATION), {"sites": [], "truncated": False})

        # Synthetic traceback links borrow an original BRIDGE code/frame, not
        # compiled fragments; exact line DATA exercises both independent bounds.
        for count, expected, truncated in ((12, range(1, 13), False), (16, range(5, 17), True),
                                            (35, range(21, 33), True)):
            head = None
            for line in range(count, 0, -1):
                head = types.TracebackType(head, leaf.tb_frame, leaf.tb_lasti, line)
            error = UnprintableError("not-for-output").with_traceback(head)
            with self.subTest(walked=count):
                self.assertEqual(B.failure_sites(error, B.QUALIFICATION), {
                    "sites": [{"module": "BRIDGE", "line": line} for line in expected], "truncated": truncated})
        for line in (0, 1_000_001):
            error = UnprintableError().with_traceback(types.TracebackType(None, leaf.tb_frame, leaf.tb_lasti, line))
            with self.subTest(invalid_line=line):
                self.assertEqual(B.failure_sites(error, B.QUALIFICATION), {"sites": [], "truncated": False})
        self.assertEqual(B.FAILURE_MODULES, {"BRIDGE", "CALLER", "CANONICAL", "OWNERSHIP"})
        source = BS.segment(BS.definition("failure_sites"))
        self.assertIn("paths.get(node.tb_frame.f_code.co_filename)", source)
        self.assertTrue({"scripts/run-audit-command.py", "scripts/audit_processes.py"} <=
                        Source.strings(BS.definition("failure_sites")))
        for forbidden in ("f_locals", "f_globals", "co_name", "co_names", "error.args", "error.details", "str(error)", "repr(error)"):
            self.assertNotIn(forbidden, source)

    def test_failure_markers_use_original_bindings_private_exclusive_writes_and_deadline(self):
        prepared, state, _events = failure_fixture()
        original_prepared = copy.deepcopy(prepared)
        error = Q.QualificationError("not-for-output")
        error._qualification_failure_predicates = ("STOP_ARGV",)
        self.assertEqual((B.FAILURE_BYTES, B.FAILURE_HINT_BYTES), (4096, 12288))
        self.assertEqual(B.FAILURE_FILES, FAILURE_FILES)
        self.assertEqual(B.FAILURE_KIND, FAILURE_KIND)
        self.assertEqual(B.FAILURE_PREDICATES, {label for labels in FAILURE_GROUPS.values() for label in labels})
        for role, name in FAILURE_FILES.items():
            with self.subTest(role=role), patch.object(B, "shared_raw_ns", return_value=100) as clock, \
                    patch.object(B, "private_directory", return_value=prepared["directoryIdentity"]) as directory, \
                    patch.object(B, "write_new") as write:
                B.record_failure(B.QUALIFICATION, state["directory"], prepared, role, error)
                directory.assert_called_once_with(state["directory"])
                self.assertEqual(clock.call_count, 3)
                write.assert_called_once()
                path, raw = write.call_args.args
                self.assertEqual(path, state["directory"] / name)
                self.assertIs(type(raw), bytes)
                self.assertLessEqual(len(raw), 4096)
                expected = failure_marker(prepared, role)
                expected.update(sites=[], predicates=["STOP_ARGV"])
                self.assertEqual(B.parsed(raw), expected)
                self.assertEqual(raw, B.encoded(expected))
                self.assertNotIn(b"not-for-output", raw)
        self.assertEqual(prepared, original_prepared)
        # The retained helper delegates to the maintained no-follow exclusive
        # writer, not stdout/stderr (which may already be redirected to null).
        writes = [call for _line, name, call in BS.calls(BS.definition("record_failure")) if name == "write_new"]
        self.assertEqual(len(writes), 1)
        opens = [call for _line, name, call in BS.calls(BS.definition("write_new")) if name == "os.open"]
        self.assertEqual(len(opens), 1)
        expected_flags = ast.parse("os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW", mode="eval").body
        self.assertEqual(ast.dump(opens[0].args[1]), ast.dump(expected_flags))
        self.assertEqual(opens[0].args[2].value, 0o600)
        for text in ("sys.stdout", "sys.stderr", "captures", "print("):
            self.assertNotIn(text, BS.segment(BS.definition("record_failure")))
        for profile in (B.GENERATION, copy.copy(B.QUALIFICATION), None):
            with self.subTest(profile_type=type(profile).__name__), patch.object(B, "write_new") as write, \
                    patch.object(B, "private_directory") as directory, patch.object(B, "shared_raw_ns") as clock:
                B.record_failure(profile, state["directory"], prepared, "P", error)
                write.assert_not_called()
                directory.assert_not_called()
                clock.assert_not_called()
        mutations = [None, {**prepared, "schema": True}, {**prepared, "scope": B.GENERATION.scope},
                     {**prepared, "case": ""}, {**prepared, "binding": "f" * 63},
                     {**prepared, "caseInputSha256": "F" * 64}, {**prepared, "source": []},
                     {**prepared, "caseEndNs": True}, {**prepared, "extra": "not-for-output"}]
        for index, changed in enumerate(mutations):
            with self.subTest(prepared=index), patch.object(B, "shared_raw_ns", return_value=100), \
                    patch.object(B, "private_directory", return_value=prepared["directoryIdentity"]), \
                    patch.object(B, "write_new") as write:
                B.record_failure(B.QUALIFICATION, state["directory"], changed, "P", error)
                write.assert_not_called()
        for now, directory_identity, role in ((300, prepared["directoryIdentity"], "P"), (100, [17, 30], "P"),
                                               (100, prepared["directoryIdentity"], "F")):
            with self.subTest(now=now, identity=directory_identity, role=role), \
                    patch.object(B, "shared_raw_ns", return_value=now), \
                    patch.object(B, "private_directory", return_value=directory_identity), patch.object(B, "write_new") as write:
                B.record_failure(B.QUALIFICATION, state["directory"], prepared, role, error)
                write.assert_not_called()

    def test_absent_foreign_malformed_and_oversized_markers_never_supply_closure(self):
        prepared, state, events = failure_fixture()
        marker = failure_marker(prepared, "P")
        changed = [
            {**marker, "schema": True}, {**marker, "scope": B.GENERATION.scope}, {**marker, "kind": "OTHER"},
            {**marker, "case": "Q2"}, {**marker, "role": "D"}, {**marker, "binding": "f" * 64},
            {**marker, "caseInputSha256": "f" * 64}, {**marker, "sourceSha256": "f" * 64},
            {**marker, "truncated": 0}, {**marker, "predicates": ["not-for-output"]},
            {**marker, "predicates": ["STOP_ARGV", "STOP_ARGV"]}, {**marker, "predicates": ["STOP_ARGV"] * 33},
            {**marker, "sites": marker["sites"] * 13}, {**marker, "sites": [{"module": "BRIDGE", "line": True}]},
            {**marker, "sites": [{"module": "BRIDGE", "line": 0}]},
            {**marker, "sites": [{"module": "BRIDGE", "line": 1_000_001}]},
            {**marker, "sites": [{"module": "/private/not-for-output", "line": 1}]},
            {**marker, "sites": [{"module": "BRIDGE", "line": 1, "path": "/private/not-for-output"}]},
            {**marker, "message": "not-for-output"}, {key: value for key, value in marker.items() if key != "sites"},
        ]
        invalid = [B.encoded(value) for value in changed]
        invalid += [b"{", b" " * 4097, b'{"schema":1,"schema":1}\n', b'{"schema":NaN}\n',
                    b" " + B.encoded(marker), OSError(errno.EACCES, "not-for-output")]
        service_raw = B.encoded(failure_marker(prepared, "D"))
        for index, raw in enumerate(invalid):
            with self.subTest(marker=index):
                error = self.attach_hint(prepared, state, events, {FAILURE_FILES["P"]: raw, FAILURE_FILES["D"]: service_raw})
                hint = json.loads(B.public_failure_hint(error))
                self.assertEqual(hint["failures"]["P"], {"status": "INVALID"})
                self.assertEqual(hint["failures"]["D"]["status"], "AVAILABLE")
                self.assertIsNone(state["final"])
                self.assertEqual(error.reason, "FINAL_FRAME_MISSING")
                self.assertNotIn("not-for-output", B.public_failure_hint(error))
        missing = {name: FileNotFoundError(errno.ENOENT, "not-for-output") for name in FAILURE_FILES.values()}
        hint = json.loads(B.public_failure_hint(self.attach_hint(prepared, state, events, missing)))
        self.assertEqual(hint["failures"], {"D": {"status": "MISSING"}, "P": {"status": "MISSING"}})
        hint = json.loads(B.public_failure_hint(self.attach_hint(prepared, state, events, mode=0o640)))
        self.assertEqual(hint["failures"], {"D": {"status": "INVALID"}, "P": {"status": "INVALID"}})
        # A FIFO/type/permission/size refusal is made from a nonblocking fake
        # descriptor before read; no real FIFO, file or descriptor is opened.
        for metadata in ({"st_mode": stat.S_IFIFO | 0o600}, {"st_mode": stat.S_IFDIR | 0o600},
                         {"st_nlink": 2}, {"st_uid": 502}, {"st_size": 4097}):
            with self.subTest(before_read=metadata):
                hint = json.loads(B.public_failure_hint(self.attach_hint(prepared, state, events, metadata=metadata)))
                self.assertEqual(hint["failures"], {"D": {"status": "INVALID"}, "P": {"status": "INVALID"}})
                self.assertTrue(all(reads == [] for reads in self.marker_reads.values()))
        for changed_stamp in ({"st_ino": 999}, {"st_mtime_ns": 12}, FileNotFoundError(errno.ENOENT, "not-for-output")):
            with self.subTest(after_open_type=type(changed_stamp).__name__):
                hint = json.loads(B.public_failure_hint(self.attach_hint(prepared, state, events, path_metadata=changed_stamp)))
                self.assertEqual(hint["failures"], {"D": {"status": "INVALID"}, "P": {"status": "INVALID"}})
                self.assertTrue(all(reads == [4097] for reads in self.marker_reads.values()))
        hint = json.loads(B.public_failure_hint(self.attach_hint(prepared, state, events,
                         read_error=OSError(errno.EIO, "not-for-output"))))
        self.assertEqual(hint["failures"], {"D": {"status": "INVALID"}, "P": {"status": "INVALID"}})
        self.assertEqual(set(hint), {"schema", "kind", "scope", "case", "binding", "caseInputSha256", "sourceSha256",
                                     "action", "codes", "failures"})
        self.assertFalse({"closure", "final", "result", "seal", "native", "pid"} & set(hint))

    def test_original_terminal_codes_are_frozen_before_abort_without_new_observations(self):
        prepared, state, events = failure_fixture()
        state["common"] = {"case": "Q1"}
        owner = object.__new__(B.Foreground)
        owner.finished = owner.failed = owner._aborted = False
        owner.current, owner.profile = state, B.QUALIFICATION
        original = []

        def failed_case():
            error = self.attach_hint(prepared, state, events)
            original.append(error)
            raise error

        def abort():
            state["action"]["kind"] = "D_SIGKILL"
            prepared["binding"] = "f" * 64
            for row in events.values():
                row["status"]["popenCode"] = -9
            owner._aborted = True

        owner._run_current_case, owner.abort = Mock(side_effect=failed_case), Mock(side_effect=abort)
        with self.assertRaises(B.ContextError) as caught:
            owner.run_case("Q1", state["directory"] / "case-input.json")
        self.assertIs(caught.exception, original[0])
        owner.abort.assert_called_once_with()
        self.assertTrue(owner.failed)
        self.assertIs(type(original[0]._qualification_failure_hint_raw), bytes)
        hint = json.loads(B.public_failure_hint(original[0]))
        self.assertEqual(hint["codes"], {"D": 0, "P": 0, "K": 0})
        self.assertEqual(hint["action"], "RELEASE")
        self.assertEqual(hint["binding"], "b" * 64)
        self.assertIsNone(state["final"])
        prepared, state, events = failure_fixture()
        state["product"] = None
        events.pop(state["producer"]["pid"])
        hint = json.loads(B.public_failure_hint(self.attach_hint(prepared, state, events)))
        self.assertEqual(hint["codes"], {"D": 0, "P": "NOT_OBSERVED", "K": "NOT_OBSERVED"})
        pid = state["service"]["pid"]
        for code in (-127, 255, True, False, -128, 256, "0", None):
            events[pid]["status"]["popenCode"] = code
            with self.subTest(original_code=code):
                hint = json.loads(B.public_failure_hint(self.attach_hint(prepared, state, events)))
                self.assertEqual(hint["codes"]["D"], code if type(code) is int and -127 <= code <= 255 else "INVALID")
        observer_calls = {name for _line, name, _call in BS.calls(BS.definition("attach_failure_hint"))}
        self.assertFalse(any(name.endswith((".poll", ".wait", ".watch", ".identity", ".signal", ".same"))
                             for name in observer_calls))
        run = BS.definition("_run_current_case", "Foreground")
        guards = [call for _line, name, call in BS.calls(run)
                  if name == "require" and "FINAL_FRAME_MISSING" in Source.strings(call)]
        attached = [call for _line, name, call in BS.calls(run) if name == "attach_failure_hint"]
        self.assertEqual((len(guards), len(attached)), (1, 1))
        guarded = [node for node in ast.walk(run) if isinstance(node, ast.Try) and
                   any(isinstance(item, ast.Expr) and item.value is guards[0] for item in node.body)]
        self.assertEqual(len(guarded), 1)
        self.assertEqual(len(guarded[0].body), 1)
        self.assertEqual(len(guarded[0].handlers), 1)
        handler = guarded[0].handlers[0]
        self.assertEqual(Source.call_name(handler.type), "ContextError")
        self.assertIn(attached[0], list(ast.walk(handler)))
        suppressed = [node for node in ast.walk(handler) if isinstance(node, ast.With) and any(
            isinstance(item.context_expr, ast.Call) and Source.call_name(item.context_expr.func) == "contextlib.suppress" and
            [Source.call_name(arg) for arg in item.context_expr.args] == ["BaseException"] for item in node.items)]
        self.assertEqual(len(suppressed), 1)
        self.assertIn(attached[0], list(ast.walk(suppressed[0])))
        self.assertIsInstance(handler.body[-1], ast.Raise)
        self.assertIsNone(handler.body[-1].exc)

    def test_original_p_d_hooks_keep_primary_errors_retained_context_and_cleanup_order(self):
        prepared, state, _events = failure_fixture()
        endpoint = types.SimpleNamespace(deadline_ns=300, directory=state["directory"], prepared=prepared,
                                         captures=types.SimpleNamespace(closed=True))
        retained = B.record_failure
        for fault in (None, "write", "hook"):
            original = B.ContextError("CLOSE", "RESOURCE_UNKNOWN")
            with self.subTest(producer_fault=fault), patch.object(B, "producer", return_value=endpoint) as acquire, \
                    patch.object(B, "checked_interpreter", side_effect=original), \
                    patch.object(B, "shared_raw_ns", return_value=100), \
                    patch.object(B, "private_directory", return_value=prepared["directoryIdentity"]), \
                    patch.object(B, "write_new", side_effect=OSError(errno.EIO, "not-for-output") if fault == "write" else None), \
                    patch.object(B, "record_failure", wraps=retained,
                        side_effect=RuntimeError("not-for-output") if fault == "hook" else None) as hook:
                with self.assertRaises(B.ContextError) as caught:
                    Q.produce(17)
                self.assertIs(caught.exception, original)
                acquire.assert_called_once_with(B.QUALIFICATION, 17)
                hook.assert_called_once_with(B.QUALIFICATION, endpoint.directory, endpoint.prepared, "P", original)
                self.assertTrue(endpoint.captures.closed)
        original = B.ContextError("START", "REFUSED")
        with patch.object(B, "producer", side_effect=original), patch.object(B, "record_failure") as hook:
            with self.assertRaises(B.ContextError) as caught:
                Q.produce(17)
            self.assertIs(caught.exception, original)
            hook.assert_not_called()  # No invented endpoint after acquisition failed.

        for validated, already_closed, fault in ((True, False, None), (True, True, "write"),
                                                  (False, False, None), (True, False, "hook")):
            original = B.ContextError("SOURCE", "REFUSED")
            order, seen = [], []
            native, captures = types.SimpleNamespace(closed=False), types.SimpleNamespace(closed=already_closed)

            def close_native():
                order.append("NATIVE")
                native.closed = True

            def close_captures():
                order.append("CAPTURES")
                captures.closed = True

            def validate(_profile, original_prepared, _directory, _native, _interpreter):
                seen.append(original_prepared)
                if not validated:
                    raise original

            def write_marker(path, raw):
                self.assertEqual(path, state["directory"] / FAILURE_FILES["D"])
                self.assertLessEqual(len(raw), 4096)
                order.append("MARKER")
                if fault == "write":
                    raise OSError(errno.EIO, "not-for-output")

            native.close, captures.close = close_native, close_captures
            with self.subTest(service_validated=validated, closed=already_closed, fault=fault), \
                    patch.object(B.sys, "argv", [str(ROOT / QUALIFIER_PATH)]), \
                    patch.object(B, "physical", side_effect=lambda path: Path(path)), \
                    patch.object(B, "private_directory", return_value=prepared["directoryIdentity"]), \
                    patch.object(B, "account", return_value=ACCOUNT), patch.object(B, "Captures", return_value=captures), \
                    patch.object(B, "Darwin", return_value=native), patch.object(B, "read_file", return_value=B.encoded(prepared)), \
                    patch.object(B, "checked_interpreter", return_value={}), \
                    patch.object(B, "validate_prepared", side_effect=validate), \
                    patch.object(B, "child_environment", side_effect=original), \
                    patch.object(B, "shared_raw_ns", return_value=100), patch.object(B, "write_new", side_effect=write_marker), \
                    patch.object(B, "record_failure", wraps=retained,
                        side_effect=RuntimeError("not-for-output") if fault == "hook" else None) as hook:
                with self.assertRaises(B.ContextError) as caught:
                    B.service(B.QUALIFICATION, state["directory"])
                self.assertIs(caught.exception, original)
                hook.assert_called_once()
                self.assertIs(hook.call_args.args[2], seen[0] if validated else None)
                self.assertIs(hook.call_args.args[4], original)
                expected = (["MARKER"] if validated and fault != "hook" else []) + ["NATIVE"]
                self.assertEqual(order, expected + ([] if already_closed else ["CAPTURES"]))
                self.assertTrue(native.closed and captures.closed)
        service = BS.definition("service")
        hooks = [call for _line, name, call in BS.calls(service) if name == "record_failure"]
        handlers = [node for node in ast.walk(service) if isinstance(node, ast.ExceptHandler) and node.name == "error"]
        self.assertEqual((len(hooks), len(handlers)), (1, 1))
        cleanup = [node for node in handlers[0].body if isinstance(node, ast.Assign) and
                   any(Source.call_name(target) == "cleanup_identity" for target in node.targets)]
        self.assertEqual(len(cleanup), 1)
        self.assertLess(hooks[0].lineno, cleanup[0].lineno)
        self.assertIsInstance(handlers[0].body[-1], ast.Raise)
        self.assertIsNone(handlers[0].body[-1].exc)
        producer = QS.definition("produce")
        blocks = [node for node in producer.body if isinstance(node, ast.Try)]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(Source.call_name(producer.body[0].value.func), "bridge.producer")
        self.assertEqual(Source.call_name(blocks[0].body[-1].value.func), "endpoint.complete")
        self.assertIsInstance(blocks[0].handlers[0].body[-1], ast.Raise)
        self.assertIsNone(blocks[0].handlers[0].body[-1].exc)

    def test_public_hint_revalidation_and_diagnostic_output_faults_preserve_primary_125(self):
        prepared, state, events = failure_fixture()
        error = self.attach_hint(prepared, state, events)
        raw = error._qualification_failure_hint_raw
        public = B.public_failure_hint(error)
        value = json.loads(public)
        self.assertEqual(public.encode("ascii") + b"\n", raw)
        self.assertLessEqual(len(raw), 12288)
        self.assertNotIn("not-for-output", public)
        mutations = [{**value, "schema": True}, {**value, "kind": "OTHER"}, {**value, "scope": B.GENERATION.scope},
                     {**value, "case": ""}, {**value, "binding": "F" * 64}, {**value, "caseInputSha256": "a" * 63},
                     {**value, "sourceSha256": []}, {**value, "action": "not-for-output"},
                     {**value, "codes": {**value["codes"], "K": True}},
                     {**value, "codes": {**value["codes"], "K": 256}},
                     {**value, "codes": {"D": 0, "P": 0}}, {**value, "message": "not-for-output"},
                     {**value, "failures": {**value["failures"], "P": {"status": "SUCCESS"}}},
                     {**value, "failures": {**value["failures"], "P": {"status": "MISSING", "sites": []}}},
                     {**value, "failures": {**value["failures"], "P": {"status": "AVAILABLE", "sites": [],
                        "truncated": False, "predicates": ["not-for-output"]}}}]
        invalid = [B.encoded(item) for item in mutations]
        invalid += [b" " + raw, b" " * 12289, b'{"schema":1,"schema":1}\n', bytearray(raw), public, None]
        for index, changed in enumerate(invalid):
            error._qualification_failure_hint_raw = changed
            with self.subTest(public_hint=index):
                self.assertIsNone(B.public_failure_hint(error))
                self.assertEqual((error.stage, error.reason, error.errno_name), ("CLOSE", "FINAL_FRAME_MISSING", "NONE"))
        error._qualification_failure_hint_raw = raw
        for other in (B.ContextError("START", "FINAL_FRAME_MISSING"), B.ContextError("CLOSE", "OTHER"),
                      B.ContextError("CLOSE", "FINAL_FRAME_MISSING", "EPIPE"),
                      B.ProductionRefusal("CLOSE", "FINAL_FRAME_MISSING"), RuntimeError("not-for-output")):
            other._qualification_failure_hint_raw = raw
            self.assertIsNone(B.public_failure_hint(other))
        with patch.object(B, "parsed", side_effect=RuntimeError("not-for-output")):
            self.assertIsNone(B.public_failure_hint(error))
        unavailable = B.ContextError("CLOSE", "FINAL_FRAME_MISSING")
        with patch.object(B, "shared_raw_ns", return_value=100), \
                patch.object(B, "private_directory", side_effect=OSError(errno.EACCES, "not-for-output")), \
                patch.object(B.os, "open") as opened:
            B.attach_failure_hint(B.QUALIFICATION, state, events, unavailable)
            opened.assert_not_called()
        self.assertIsNone(B.public_failure_hint(unavailable))
        self.assertFalse(hasattr(unavailable, "_qualification_failure_hint_raw"))
        primary = ("P2PKIT_DEPENDENCY_CONTEXT_FAILURE|DEPENDENCY_CONTEXT/CLOSE/FINAL_FRAME_MISSING/NONE; "
                   "no seal, retry, or qualification\n")
        output = io.StringIO()
        with patch.object(Q.sys, "argv", [str(ROOT / QUALIFIER_PATH), "qualify"]), \
                patch.object(Q.os, "umask"), patch.object(Q, "qualify", side_effect=error), \
                patch.object(Q.sys, "stderr", output):
            self.assertEqual(Q.main(), 125)
        self.assertEqual(output.getvalue(), primary + "P2PKIT_DEPENDENCY_CONTEXT_DIAGNOSTIC|" + public + "\n")

        class FailedDiagnosticOutput(io.StringIO):
            def write(self, text):
                if text.startswith("P2PKIT_DEPENDENCY_CONTEXT_DIAGNOSTIC|"):
                    raise OSError(errno.EIO, "not-for-output")
                return super().write(text)

        output = FailedDiagnosticOutput()
        with patch.object(Q.sys, "argv", [str(ROOT / QUALIFIER_PATH), "qualify"]), \
                patch.object(Q.os, "umask"), patch.object(Q, "qualify", side_effect=error), \
                patch.object(Q.sys, "stderr", output):
            self.assertEqual(Q.main(), 125)
        self.assertEqual(output.getvalue(), primary)
        output = io.StringIO()
        with patch.object(Q.sys, "argv", [str(ROOT / QUALIFIER_PATH), "qualify"]), \
                patch.object(Q.os, "umask"), patch.object(Q, "qualify", side_effect=error), \
                patch.object(Q.sys, "stderr", output), \
                patch.object(B, "public_failure_hint", side_effect=RuntimeError("not-for-output")):
            self.assertEqual(Q.main(), 125)
        self.assertEqual(output.getvalue(), primary)

    def test_diagnostics_cannot_change_f8_q4_success_rosters_or_export_authority(self):
        self.assertEqual(B.FRAME_ROSTER, ((1, "D>F", "HELLO"), (2, "F>D", "PREPARE"), (3, "P>D", "CHILD_READY"),
            (4, "D>F", "CHILD_READY"), (5, "F>D", "START"), (6, "D>P", "START"), (7, "P>D", "RESULT"),
            (8, "D>F", "CHILD_RESULT_AND_EXIT_READY")))
        self.assertFalse(set(FAILURE_FILES.values()) & (B.CASE_FILES | B.SERVICE_FILES))
        run = BS.definition("_run_current_case", "Foreground")
        expected_loss = [node.value for node in ast.walk(run) if isinstance(node, ast.Assign) and
                         any(Source.call_name(target) == "expected_loss" for target in node.targets)]
        self.assertEqual(len(expected_loss), 1)
        original_loss = ast.parse('self.profile is QUALIFICATION and inputs["case"] == "Q4" and '
                                  'state["action"]["kind"] == "D_SIGKILL"', mode="eval").body
        self.assertEqual(ast.dump(expected_loss[0]), ast.dump(original_loss))
        guard = [call for _line, name, call in BS.calls(run)
                 if name == "require" and "FINAL_FRAME_MISSING" in Source.strings(call)]
        self.assertEqual(len(guard), 1)
        self.assertEqual(ast.dump(guard[0].args[0]),
                         ast.dump(ast.parse('state["final"] is not None or expected_loss', mode="eval").body))
        self.assertEqual([arg.value for arg in guard[0].args[1:]], ["CLOSE", "FINAL_FRAME_MISSING"])
        self.assertEqual(Q.Q4_LOSSES, {"producerWait": "ABSENT_D_DIED", "producerPipeEof": "ABSENT_D_DIED",
            "serviceFinalFrame": "ABSENT_D_DIED", "producerPipeCaptures": "INCOMPLETE_D_DIED",
            "serviceCaptures": "INCOMPLETE_D_DIED"})
        complete = BS.segment(BS.definition("complete", "Producer"))
        self.assertIn('self.profile is QUALIFICATION and self.case == "Q4" and result["code"] == 125 and', complete)
        self.assertIn('error.errno_name in ("EPIPE", "ECONNRESET")', complete)
        diagnostic_calls = {"record_failure", "attach_failure_hint", "public_failure_hint"}
        for source, node in ((BS, BS.definition("_closed_files", "Foreground")),
                             (BS, BS.definition("validate_production_data")),
                             (BS, BS.definition("complete", "Producer")),
                             (QS, QS.definition("finish_export")), (QS, QS.definition("collect_evidence")),
                             (GS, GS.tree)):
            self.assertFalse(diagnostic_calls & {name.rsplit(".", 1)[-1] for _line, name, _call in source.calls(node)})
        prepared, state, events = failure_fixture()
        error = B.ContextError("CLOSE", "FINAL_FRAME_MISSING")
        with patch.object(B, "_failure_binding") as binding:
            B.attach_failure_hint(B.GENERATION, state, events, error)
            binding.assert_not_called()
        self.assertFalse(hasattr(error, "_qualification_failure_hint_raw"))

        # Exercise the actual finite success roster with fake directory entries.
        # Neither normal Q1 nor Q4's optional/incomplete D streams admit markers.
        owner = object.__new__(B.Foreground)
        owner.operation, owner.profile = Path("/controlled/operation"), B.QUALIFICATION
        bridge = owner.operation / "bridge"
        for case in ("Q1", "Q4"):
            for failure in FAILURE_FILES.values():
                rows = {bridge: [bridge / name for name in ("foreground.json", "source-after.json", "suite-closed.json", "cases", "sentinel")],
                        bridge / "cases": [bridge / "cases" / name for name in CASES],
                        bridge / "sentinel": [bridge / "sentinel" / name for name in ("sentinel.stdout", "sentinel.stderr", "native-exit.json")]}
                for current in CASES:
                    names = set(B.CASE_FILES) | {"product-ready.json", "case-result.json"}
                    if current in ("Q1", "Q2"):
                        names.add("product-release.json")
                    if current != "Q4":
                        names.update(B.SERVICE_FILES | {"service-final.json"})
                    directory = bridge / "cases" / current
                    rows[directory] = [directory / name for name in sorted(names)]
                bad = bridge / "cases" / case / failure
                rows[bad.parent].insert(0, bad)
                with self.subTest(case=case, forbidden=failure), patch.object(B, "private_directory"), \
                        patch.object(B, "physical", side_effect=lambda path: Path(path)), \
                        patch.object(Path, "iterdir", lambda path: iter(rows[path])), \
                        patch.object(Path, "lstat", return_value=types.SimpleNamespace(st_mode=stat.S_IFREG | 0o600)), \
                        patch.object(B, "read_file", return_value=b"{}\n") as read:
                    with self.assertRaises(B.ContextError) as caught:
                        owner._closed_files()
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("FREEZE", "UNKNOWN_BRIDGE_MEMBER"))
                    self.assertFalse(any(call.args[0] == bad for call in read.call_args_list))

    def test_canonical_failure_labels_preserve_original_predicates_and_first_failure(self):
        # These are the original 7deeb646 acceptance expressions. Parse DATA for
        # comparison only; never compile or execute copied project fragments.
        original = {
            "CANONICAL_RETURN": "case in CASES and type(code) is int and type(receipt) is dict",
            "CANONICAL_RECEIPT": """code == expected_code and type(receipt.get("schema")) is int and receipt["schema"] == 1 and
                receipt.get("id") == invocation and receipt.get("jobId") == context["id"] and
                receipt.get("kind") == "command" and receipt.get("purpose") == "dependency-context-" + case.lower() and
                receipt.get("requestedArgv") == receipt.get("executedArgv") == argv and
                receipt.get("controllerPid") == entry["producerIdentity"]["pid"] and
                receipt.get("cwd") == context["root"] and receipt.get("wrapper") == str(Path(context["root"]) / "gradlew") and
                receipt.get("host") == "macos-arm64" and receipt.get("gradleHome") == context["gradleHome"] and
                receipt.get("sourceBefore") == receipt.get("sourceAfter") == context["source"] and
                receipt.get("sourceUnchanged") is True and
                all(type(receipt.get(key)) is int for key in ("productPid", "productExitCode", "stopExitCode", "finalExitCode")) and
                receipt["productPid"] > 0 and receipt["productExitCode"] == product_code and receipt["stopExitCode"] == 0 and
                receipt["finalExitCode"] == code and receipt.get("ownedSurvivors") == [] and
                type(receipt.get("ownership")) is dict and receipt["ownership"].get("discoveryErrors") == []""",
            "CANONICAL_STOP": """receipt.get("stopArgv") == [str(Path(context["root"]) / "gradlew"), "--stop", "--console=plain",
                "--no-parallel", "--max-workers=2", "-Dorg.gradle.jvmargs=" + JVM_ARGUMENTS]""",
            "CANONICAL_CLOSED_PRODUCT": """receipt.get("errors") == [] and "cancelledSignals" not in receipt and
                "cancelRequested" not in receipt""",
            "CANONICAL_CANCELLATION": """receipt.get("errors") == CANCELLATION_ERRORS and receipt.get("cancelledSignals") == [15] and
                receipt.get("cancelRequested") is False""",
        }
        validator = QS.definition("validate_canonical_result")
        guards = [call for _line, name, call in QS.calls(validator) if name == "require"]
        self.assertEqual([call.args[1].value for call in guards], list(original))
        for call in guards:
            with self.subTest(original_guard=call.args[1].value):
                expected = ast.parse("(" + original[call.args[1].value] + ")", mode="eval").body
                self.assertEqual(ast.dump(call.args[0]), ast.dump(expected))
                self.assertEqual(len(call.args), 2)
                self.assertEqual(call.keywords, [])

        label_group = {label: group for group, labels in FAILURE_GROUPS.items() for label in labels}
        self.assertEqual(len(label_group), 30)
        mutations = [
            ("RETURN_CODE", "Q1", {"finalExitCode": 1}, {"code": 1}),
            ("SCHEMA", "Q1", {"schema": True}, {}),
            ("INVOCATION_ID", "Q1", {"id": "f" * 32}, {}),
            ("JOB_ID", "Q1", {"jobId": "f" * 32}, {}),
            ("COMMAND_KIND", "Q1", {"kind": "not-a-command"}, {}),
            ("PURPOSE", "Q1", {"purpose": "not-a-qualifier"}, {}),
            ("PRODUCT_ARGV", "Q1", {"requestedArgv": ["/private/not-for-output"]}, {}),
            ("CONTROLLER_PID", "Q1", {"controllerPid": 999}, {}),
            ("CWD", "Q1", {"cwd": "/private/not-for-output"}, {}),
            ("WRAPPER", "Q1", {"wrapper": "/private/not-for-output"}, {}),
            ("HOST", "Q1", {"host": "not-a-host"}, {}),
            ("GRADLE_HOME", "Q1", {"gradleHome": "/private/not-for-output"}, {}),
            ("SOURCE_SNAPSHOTS", "Q1", {"sourceAfter": {}}, {}),
            ("SOURCE_UNCHANGED", "Q1", {"sourceUnchanged": False}, {}),
            ("PRODUCT_PID", "Q1", {"productPid": 0}, {}),
            ("PRODUCT_EXIT", "Q1", {"productExitCode": 23}, {}),
            ("STOP_EXIT", "Q1", {"stopExitCode": 1}, {}),
            ("FINAL_EXIT", "Q1", {"finalExitCode": 1}, {}),
            ("OWNED_SURVIVORS", "Q1", {"ownedSurvivors": ["not-for-output"]}, {}),
            ("OWNERSHIP_DISCOVERY", "Q1", {"ownership": {"discoveryErrors": ["not-for-output"]}}, {}),
            ("STOP_ARGV", "Q1", {"stopArgv": []}, {}),
            ("ERRORS_EMPTY", "Q1", {"errors": ["not-for-output"]}, {}),
            ("CANCEL_SIGNALS_ABSENT", "Q1", {"cancelledSignals": []}, {}),
            ("CANCEL_REQUEST_ABSENT", "Q1", {"cancelRequested": False}, {}),
            ("CANCELLATION_ERRORS", "Q3", {"errors": []}, {}),
            ("CANCEL_SIGNALS", "Q3", {"cancelledSignals": [9]}, {}),
            ("CANCEL_REQUEST", "Q3", {"cancelRequested": True}, {}),
            ("CASE_SUPPORTED", "Q1", {}, {"case": ""}),
            ("RETURN_CODE_TYPE", "Q1", {}, {"code": True}),
            ("RECEIPT_TYPE", "Q1", {}, {"receipt": []}),
        ]
        self.assertEqual({label for label, _case, _changes, _args in mutations}, set(label_group))
        for label, case, changes, replacements in mutations:
            code, receipt, context, entry = canonical_fixture(case)
            receipt.update(changes)
            args = {"code": code, "receipt": receipt, "context": context, "entry": entry, "case": case}
            args.update(replacements)
            before = copy.deepcopy(args)
            with self.subTest(label=label), self.assertRaises(Q.QualificationError) as caught:
                Q.validate_canonical_result(**args)
            self.assertEqual(str(caught.exception), label_group[label])
            self.assertEqual(caught.exception._qualification_failure_predicates, (label,))
            self.assertEqual(args, before)

        for field in ("productPid", "productExitCode", "stopExitCode", "finalExitCode"):
            code, receipt, context, entry = canonical_fixture("Q1")
            receipt[field] = False
            expected = dict(productPid="PRODUCT_PID", productExitCode="PRODUCT_EXIT",
                            stopExitCode="STOP_EXIT", finalExitCode="FINAL_EXIT")[field]
            with self.subTest(exact_int=field), self.assertRaises(Q.QualificationError) as caught:
                Q.validate_canonical_result(code, receipt, context, entry, "Q1")
            self.assertEqual(caught.exception._qualification_failure_predicates, (expected,))

        code, receipt, context, entry = canonical_fixture("Q1")
        receipt.update(sourceUnchanged=False, ownedSurvivors=["not-for-output"], stopArgv=[], errors=["not-for-output"])
        with self.assertRaises(Q.QualificationError) as caught:
            Q.validate_canonical_result(code, receipt, context, entry, "Q1")
        self.assertEqual(str(caught.exception), "CANONICAL_RECEIPT")
        self.assertEqual(caught.exception._qualification_failure_predicates, ("SOURCE_UNCHANGED", "OWNED_SURVIVORS"))
        # Classifier faults neither replace the first original reason nor turn
        # absent labels into acceptance. It is never called for successful DATA.
        with patch.object(Q, "canonical_failure_predicates", side_effect=RuntimeError("not-for-output")) as classifier:
            with self.assertRaises(Q.QualificationError) as caught:
                Q.validate_canonical_result(code, receipt, context, entry, "Q1")
            self.assertEqual(str(caught.exception), "CANONICAL_RECEIPT")
            self.assertFalse(hasattr(caught.exception, "_qualification_failure_predicates"))
            classifier.assert_called_once()
        for case, expected in zip(CASES, ("SUCCESS", "CLOSED_FAILED_PRODUCT", "INFRASTRUCTURE_REFUSAL", "INFRASTRUCTURE_REFUSAL")):
            code, receipt, context, entry = canonical_fixture(case)
            with self.subTest(success_data=case), patch.object(Q, "canonical_failure_predicates") as classifier:
                self.assertEqual(Q.validate_canonical_result(code, receipt, context, entry, case), expected)
                classifier.assert_not_called()


class CanonicalCancellationReceiptControls(unittest.TestCase):
    def test_cancellation_receipt_errors_match_original_typed_formatter_and_exact_clean_list(self):
        # Independent expected DATA, not a copy of the qualifier constant. This
        # is the clean source path, not a reconstruction of any hosted receipt.
        expected = ["AuditError: Invocation cancellation requested",
                    "Invocation cancellation cannot be a successful product result"]
        canonical = Source("scripts/run-audit-command.py")
        ownership = Source("scripts/audit_processes.py")
        for relative, pinned in CANONICAL_PINS.items():
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), pinned)
        error_types = [node for node in canonical.tree.body if isinstance(node, ast.ClassDef) and node.name == "AuditError"]
        self.assertEqual(len(error_types), 1)
        self.assertEqual([Source.call_name(base) for base in error_types[0].bases], ["RuntimeError"])
        self.assertEqual(len(error_types[0].body), 1)
        self.assertIsInstance(error_types[0].body[0], ast.Pass)
        cancellation_guard = ast.parse("cancelled and not stop", mode="eval").body
        branches = [node for node in ast.walk(canonical.definition("wait_process")) if isinstance(node, ast.If) and
                    ast.dump(node.test) == ast.dump(cancellation_guard)]
        self.assertEqual(len(branches), 2)
        for branch in branches:
            self.assertEqual(len(branch.body), 1)
            self.assertIsInstance(branch.body[0], ast.Raise)
            raised = branch.body[0].exc
            self.assertEqual(Source.call_name(raised.func), "AuditError")
            self.assertEqual([argument.value for argument in raised.args], ["Invocation cancellation requested"])
            self.assertEqual(raised.keywords, [])
            self.assertEqual(Source.call_name(raised.func) + ": " + raised.args[0].value, expected[0])
        self.assertIn('message = str(error)[:2048]', ownership.segment(ownership.definition("_exception_text")))
        formatted_return = ownership.definition("_exception_text").body[-1]
        self.assertIsInstance(formatted_return, ast.Return)
        self.assertEqual(ast.dump(formatted_return.value),
                         ast.dump(ast.parse('f"{type(error).__name__}: {message}"', mode="eval").body))
        formatter = ownership.definition("format_ownership_error")
        text_assignments = [node for node in formatter.body if isinstance(node, ast.Assign) and
                            any(Source.call_name(target) == "text" for target in node.targets)]
        self.assertEqual(len(text_assignments), 1)
        self.assertEqual(Source.call_name(text_assignments[0].value.func), "_exception_text")
        self.assertEqual([Source.call_name(arg) for arg in text_assignments[0].value.args], ["error"])
        self.assertEqual(Source.call_name(formatter.body[-1].value), "text")
        self.assertTrue(any(isinstance(node, ast.ImportFrom) and node.module == "audit_processes" and
            any(alias.name == "format_ownership_error" and alias.asname is None for alias in node.names)
            for node in canonical.tree.body))

        execute = canonical.definition("execute")
        recorders = [node for node in execute.body if isinstance(node, ast.FunctionDef) and node.name == "record_error"]
        self.assertEqual(len(recorders), 1)
        appends = [call for _line, name, call in canonical.calls(recorders[0]) if name == "errors.append"]
        self.assertEqual(len(appends), 1)
        self.assertEqual(ast.dump(appends[0].args[0]),
                         ast.dump(ast.parse("prefix + format_ownership_error(error)", mode="eval").body))
        blocks = [node for node in execute.body if isinstance(node, ast.Try)]
        self.assertEqual(len(blocks), 1)
        product = blocks[0].body[-1]
        self.assertEqual(Source.call_name(product.value.func), "wait_process")
        self.assertEqual(product.targets[0].slice.value, "productExitCode")
        self.assertFalse(any(keyword.arg == "stop" for keyword in product.value.keywords))
        self.assertEqual(len(blocks[0].handlers), 1)
        handler = blocks[0].handlers[0]
        self.assertEqual((Source.call_name(handler.type), handler.name), ("BaseException", "error"))
        self.assertEqual(len(handler.body), 1)
        self.assertEqual(ast.dump(handler.body[0].value), ast.dump(ast.parse('record_error("", error)', mode="eval").body))
        terminal = [node for node in blocks[0].finalbody if isinstance(node, ast.If) and
                    Source.call_name(node.test) == "cancelled"]
        self.assertEqual(len(terminal), 1)
        appends = [call for _line, name, call in canonical.calls(terminal[0]) if name == "errors.append"]
        self.assertEqual(len(appends), 1)
        self.assertEqual([argument.value for argument in appends[0].args], [expected[1]])

        self.assertEqual(Q.CANCELLATION_ERRORS, expected)
        invalid = [[], expected[:1], expected[1:], expected[::-1],
                   ["Invocation cancellation requested", expected[1]],
                   ["RuntimeError: Invocation cancellation requested", expected[1]],
                   expected + [expected[1]], [expected[0], *expected],
                   expected + ["Wrapper stop/finalizer failed: AuditError: CONTROL_FINALIZER_FAILURE"],
                   [expected[0] + "; POSIX resource retirement UNKNOWN (posix-close/pipe): "
                    "OSError: CONTROL_RETIREMENT_FAILURE", expected[1]]]
        for case in ("Q3", "Q4"):
            code, receipt, context, entry = canonical_fixture(case)
            receipt["errors"] = list(expected)
            with self.subTest(clean_case=case):
                self.assertEqual(Q.validate_canonical_result(code, receipt, context, entry, case), "INFRASTRUCTURE_REFUSAL")
                self.assertEqual((code, receipt["productExitCode"], receipt["stopExitCode"]), (125, -15, 0))
                self.assertEqual(receipt["cancelledSignals"], [15])
                self.assertIs(receipt["cancelRequested"], False)
            for index, errors in enumerate(invalid):
                changed = {**receipt, "errors": list(errors)}
                with self.subTest(case=case, invalid_errors=index), self.assertRaises(Q.QualificationError) as caught:
                    Q.validate_canonical_result(code, changed, context, entry, case)
                self.assertEqual(str(caught.exception), "CANONICAL_CANCELLATION")
                self.assertEqual(caught.exception._qualification_failure_predicates, ("CANCELLATION_ERRORS",))


class QualifierIdentityDiagnosticControls(unittest.TestCase):
    def test_exact_qualify_identity_sites_preserve_primary_without_side_effects(self):
        # Pin only the new main-handler branch. The unchanged failure_sites
        # control already covers both bounds, allowlisting and private-data refusal.
        prefix = "P2PKIT_DEPENDENCY_CONTEXT_IDENTITY_SITES|"
        branch = ('with contextlib.suppress(BaseException):\n'
                  '    if (sys.argv[1:] == ["qualify"] and type(error) is bridge.ContextError and\n'
                  '            (error.stage, error.reason, error.errno_name) == ("IDENTITY", "IDENTITY_CHANGED", "NONE")):\n'
                  '        print("P2PKIT_DEPENDENCY_CONTEXT_IDENTITY_SITES|" +\n'
                  '              encoded(bridge.failure_sites(error, bridge.QUALIFICATION)).decode("ascii").rstrip("\\n"),\n'
                  '              file=sys.stderr)')
        main = QS.definition("main")
        blocks = [node for node in main.body if isinstance(node, ast.Try)]
        self.assertEqual(len(blocks), 1)
        self.assertEqual(len(blocks[0].handlers), 1)
        handler = blocks[0].handlers[0]
        self.assertEqual((Source.call_name(handler.type), handler.name), ("BaseException", "error"))
        self.assertEqual(len(handler.body), 5)
        self.assertEqual(ast.dump(handler.body[2]), ast.dump(ast.parse(branch).body[0]))
        self.assertEqual(handler.body[2].end_lineno - handler.body[2].lineno + 1, 6)
        self.assertEqual(QS.segment(handler.body[1]),
                         'print("P2PKIT_DEPENDENCY_CONTEXT_FAILURE|" + reason + "; no seal, retry, or qualification", file=sys.stderr)')
        self.assertEqual(ast.dump(handler.body[3]), ast.dump(ast.parse(
            'with contextlib.suppress(BaseException):\n'
            '    hint = bridge.public_failure_hint(error)\n'
            '    if hint is not None:\n'
            '        print("P2PKIT_DEPENDENCY_CONTEXT_DIAGNOSTIC|" + hint, file=sys.stderr)').body[0]))
        self.assertIsInstance(handler.body[4], ast.Return)
        self.assertEqual(handler.body[4].value.value, 125)
        self.assertEqual(QS.text.count(prefix), 1)
        self.assertEqual([name for _line, name, _call in QS.calls(QS.tree) if name == "bridge.failure_sites"],
                         ["bridge.failure_sites"])
        caller_lines = [line for line, name, _call in QS.calls(main) if name == "qualify"]
        bridge_lines = [line for line, name, _call in BS.calls(BS.definition("require")) if name == "ContextError"]
        self.assertEqual((len(caller_lines), len(bridge_lines)), (1, 1))
        expected = {"sites": [{"module": "CALLER", "line": caller_lines[0]},
                              {"module": "BRIDGE", "line": bridge_lines[0]}], "truncated": False}
        primary = ("P2PKIT_DEPENDENCY_CONTEXT_FAILURE|DEPENDENCY_CONTEXT/IDENTITY/IDENTITY_CHANGED/NONE; "
                   "no seal, retry, or qualification\n")
        diagnostic = prefix + json.dumps(expected, sort_keys=True, separators=(",", ":")) + "\n"

        def identity_error():
            try:
                B.require(False, "IDENTITY", "IDENTITY_CHANGED", private="not-for-output")
            except B.ContextError as error:
                return error

        class FailedSitesOutput(io.StringIO):
            def write(self, text):
                if text.startswith(prefix):
                    raise OSError(errno.EIO, "not-for-output")
                return super().write(text)

        def observe(arguments, error, fault=None):
            stdout, stderr = io.StringIO(), FailedSitesOutput() if fault == "stderr" else io.StringIO()
            before = None if error is None else (copy.deepcopy(vars(error)), error.args)
            with contextlib.ExitStack() as stack:
                # Intercept every command entrypoint and the only pre-dispatch
                # filesystem/mutation calls; no real qualification is entered.
                for owner, name in ((Q, "qualify"), (Q, "upload_guard"), (B, "service"), (Q, "produce")):
                    stack.enter_context(patch.object(owner, name, return_value=0, side_effect=error))
                stack.enter_context(patch.object(Q, "physical", side_effect=lambda value: Path(value)))
                stack.enter_context(patch.object(Q.os, "umask"))
                stack.enter_context(patch.object(Q.sys, "argv", [str(ROOT / QUALIFIER_PATH), *arguments]))
                stack.enter_context(patch.object(Q.sys, "stdout", stdout))
                stack.enter_context(patch.object(Q.sys, "stderr", stderr))
                sites = stack.enter_context(patch.object(B, "failure_sites", wraps=B.failure_sites,
                    side_effect=KeyboardInterrupt("not-for-output") if fault == "sites" else None))
                codec = stack.enter_context(patch.object(Q, "encoded", wraps=Q.encoded,
                    side_effect=KeyboardInterrupt("not-for-output") if fault == "encoded" else None))
                hint = stack.enter_context(patch.object(B, "public_failure_hint", wraps=B.public_failure_hint,
                    side_effect=KeyboardInterrupt("not-for-output") if fault == "hint" else None))
                code = Q.main()
            self.assertEqual(stdout.getvalue(), "")
            self.assertNotIn("not-for-output", stderr.getvalue())
            if error is not None:
                self.assertEqual((vars(error), error.args), before)
            return code, stderr.getvalue(), sites, codec, hint

        error = identity_error()
        code, output, sites, codec, hint = observe(["qualify"], error)
        self.assertEqual((code, output), (125, primary + diagnostic))
        sites.assert_called_once_with(error, B.QUALIFICATION)
        codec.assert_called_once_with(expected)
        hint.assert_called_once_with(error)

        rejected = [(["qualify"], B.ContextError(*fields, private="not-for-output")) for fields in (
            ("PREPARE", "IDENTITY_CHANGED", "NONE"), ("IDENTITY", "REFUSED", "NONE"),
            ("IDENTITY", "IDENTITY_CHANGED", "ESRCH"))]
        rejected += [(["qualify"], error) for error in (
            B.ProductionRefusal("IDENTITY", "IDENTITY_CHANGED", private="not-for-output"),
            Q.QualificationError("IDENTITY_CHANGED"), RuntimeError("not-for-output"))]
        rejected += [(arguments, identity_error()) for arguments in (
            ["before-upload"], ["after-upload"], ["_service", "/offline"], ["_produce", "3"], ["qualify", "extra"])]
        for index, (arguments, error) in enumerate(rejected):
            with self.subTest(rejected=index):
                code, output, sites, codec, hint = observe(arguments, error)
                self.assertEqual(code, 125)
                self.assertEqual(len(output.splitlines()), 1)
                self.assertTrue(output.startswith("P2PKIT_DEPENDENCY_CONTEXT_FAILURE|"))
                self.assertTrue(output.endswith("; no seal, retry, or qualification\n"))
                sites.assert_not_called()
                codec.assert_not_called()
                hint.assert_called_once()
        code, output, sites, codec, hint = observe(["qualify"], None)
        self.assertEqual((code, output), (0, ""))
        for helper in (sites, codec, hint):
            helper.assert_not_called()

        for fault in ("sites", "encoded", "stderr", "hint"):
            error = identity_error()
            with self.subTest(diagnostic_fault=fault):
                code, output, sites, codec, hint = observe(["qualify"], error, fault)
                self.assertEqual((code, output), (125, primary + (diagnostic if fault == "hint" else "")))
                sites.assert_called_once_with(error, B.QUALIFICATION)
                hint.assert_called_once_with(error)
                if fault == "sites":
                    codec.assert_not_called()
                else:
                    codec.assert_called_once_with(expected)


class OrphanParentIdentityControls(unittest.TestCase):
    def test_reparent_keeps_original_image_parent_and_original_signal_authority(self):
        # Same-image synthetic DATA derived from the reviewed XNU semantics,
        # not reconstructed native values or permission to refresh an image.
        service = identity(71, parent_pid=1, unique=701, parent_unique=11)
        producer = identity(version=83)
        session = {"pid": 101, "sessionId": 101, "processGroupId": 101}
        self.assertEqual(producer["parentUniqueId"], service["uniqueId"])
        self.assertNotEqual(service["uniqueId"], service["parentUniqueId"])
        attached = {**producer, "status": 3}
        orphan = {**attached, "parentPid": 1}

        def owner(actual):
            native = object.__new__(B.Darwin)  # No native constructor or token acquisition.
            native.role, native.watched = "F", {71: dict(service), 101: dict(producer)}
            native.events, native._tokens = {71: terminal_fixture(service, -9, 300)}, {101: object()}
            native.identity = Mock(return_value=actual)
            native.token = Mock(side_effect=AssertionError("never replace the original opaque token"))
            native._signal_return = Mock(return_value=0)
            return native

        rejected = [{**orphan, key: orphan[key] + 1} for key in sorted(IDENTITY_KEYS - {"status", "parentPid"})]
        rejected += [{**orphan, "parentUniqueId": service["parentUniqueId"]},
                     {**orphan, "parentPid": 999}, {**orphan, "parentPid": True}]
        for index, actual in enumerate([attached, orphan, *rejected]):
            native = owner(actual)
            held = native._tokens[101]
            before = copy.deepcopy((native.watched, native.events, actual))
            with self.subTest(identity=index), patch.object(B, "shared_raw_ns", return_value=400), \
                    patch.object(B, "session_record", return_value=session) as observed_session:
                if index < 2:
                    self.assertEqual(native.signal_orphan(producer, service, session, 1000), 0)
                    expected = {"originalParentPid": 71, "originalParentUniqueId": 701,
                        "currentParentPid": actual["parentPid"], "currentParentUniqueId": 701,
                        "serviceExitObservedRawNs": 300, "checkedRawNs": 400}
                    native._signal_return.assert_called_once_with(producer, held, signal.SIGTERM, 1000, expected)
                else:
                    with self.assertRaises(B.ContextError) as raised:
                        native.signal_orphan(producer, service, session, 1000)
                    self.assertEqual((raised.exception.stage, raised.exception.reason, raised.exception.errno_name),
                                     ("IDENTITY", "IDENTITY_CHANGED", "NONE"))
                    native._signal_return.assert_not_called()
            native.identity.assert_called_once_with(101)
            observed_session.assert_called_once_with(producer)
            native.token.assert_not_called()
            self.assertIs(native._tokens[101], held)
            self.assertEqual((native.watched, native.events, actual), before)

        for change in ("wrong-observer", "unwatched-D", "unwatched-P", "foreign-D-event", "P-exited",
                       "missing-token", "changed-D-image", "changed-P-image"):
            native = owner(orphan)
            if change == "wrong-observer":
                native.role = "D"
            elif change == "unwatched-D":
                del native.watched[71]
            elif change == "unwatched-P":
                del native.watched[101]
            elif change == "foreign-D-event":
                native.events = {72: terminal_fixture(identity(72), -9, 300)}
            elif change == "P-exited":
                native.events[101] = terminal_fixture(producer, 125, 350)
            elif change == "missing-token":
                native._tokens.clear()
            elif change == "changed-D-image":
                native.watched[71]["uniqueId"] += 1
            else:
                native.watched[101]["pidVersion"] += 1
            with self.subTest(prerequisite=change), patch.object(B, "shared_raw_ns") as clock, \
                    patch.object(B, "session_record") as observed_session, self.assertRaises(B.ContextError):
                native.signal_orphan(producer, service, session, 1000)
            for operation in (native.identity, native.token, native._signal_return, clock, observed_session):
                operation.assert_not_called()

        parameters = {"actual": orphan, "original": producer, "service": service,
            "current_session": session, "original_session": session, "event_observed_ns": 300, "checked_ns": 400}
        bad_session = {**session, "sessionId": service["pid"]}
        changes = [{"original": {**producer, "parentPid": 72}},
                   {"original": {**producer, "parentUniqueId": 702}},
                   {"service": {**service, "parentPid": 2}},
                   {"current_session": {**session, "pid": 102}},
                   {"current_session": bad_session},
                   {"current_session": {**session, "processGroupId": 71}},
                   {"original_session": bad_session},
                   {"current_session": bad_session, "original_session": bad_session},
                   {"event_observed_ns": 0}, {"event_observed_ns": True},
                   {"event_observed_ns": 401}, {"checked_ns": True}]
        for index, changed in enumerate(changes):
            with self.subTest(original_data=index), self.assertRaises(B.ContextError) as raised:
                B.validate_orphan_identity(**{**parameters, **changed})
            reason = "EVENT_ORDER" if set(changed) & {"event_observed_ns", "checked_ns"} else "IDENTITY_CHANGED"
            self.assertEqual((raised.exception.stage, raised.exception.reason, raised.exception.errno_name),
                             ("IDENTITY", reason, "NONE"))

        values = qualifier_fixture("Q4")
        original = values[0]
        d, p = original["native"]["service"], original["native"]["producer"]
        self.assertEqual(p["parentUniqueId"], d["uniqueId"])
        for parent_pid in (d["pid"], 1):
            record = copy.deepcopy(original)
            current = record["native"]["signalReturns"][1]["orphan"]
            current["currentParentPid"] = parent_pid
            self.assertEqual(current["currentParentUniqueId"], p["parentUniqueId"])
            with self.subTest(q4_parent=parent_pid):
                self.assertEqual(Q.validate_case_records("Q4", record, *values[1:]), "INFRASTRUCTURE_REFUSAL")
                self.assertEqual(record["lossAnnotations"], Q.Q4_LOSSES)
                self.assertTrue(all(record["closure"][key] == value for key, value in Q.Q4_LOSSES.items()))
            for key, value in (("currentParentUniqueId", d["parentUniqueId"]),
                               ("currentParentUniqueId", d["uniqueId"] + 1), ("currentParentPid", d["pid"] + 1),
                               ("originalParentPid", d["pid"] + 1), ("originalParentUniqueId", d["uniqueId"] + 1)):
                changed = copy.deepcopy(record)
                changed["native"]["signalReturns"][1]["orphan"][key] = value
                with self.subTest(q4_parent=parent_pid, forged=key, value=value), \
                        self.assertRaises(Q.QualificationError) as raised:
                    Q.validate_case_records("Q4", changed, *values[1:])
                self.assertEqual(str(raised.exception), "ORIGINAL_ORPHAN_JOIN")


if __name__ == "__main__":
    unittest.main()
