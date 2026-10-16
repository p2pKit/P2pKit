#!/usr/bin/env python3
"""OFFLINE models of the ACTUAL native-query adapter and its admission caller.

All host_role/make_scope calls are replaced; no Git child, native ownership API,
GPG, network, Gradle or GitHub operation is executed. POSIX fixture file I/O is
real and private; modeled output bytes are not protocol/crypto/host evidence.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_test_query as Q

SPEC = importlib.util.spec_from_file_location("hosted_query_entrypoint", ROOT / "scripts/run-hosted-test-admission.py")
ENTRY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ENTRY)
SOURCE, TREE, BEFORE = (item * 40 for item in "123")
PUBLIC = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\nsynthetic-policy-only\n-----END PGP PUBLIC KEY BLOCK-----\n"


class Clock:
    def __init__(self):
        self.now = 100.0

    def monotonic(self):
        return self.now

    def sleep(self, value):
        self.now += value


class Scope:
    """No process/backend calls. Writes model bytes through borrowed POSIX fds."""

    def __init__(self, case, job, invocation, state, home):
        self.case, self.job, self.invocation = case, job, invocation
        self.state, self.home = state, home
        self.baseline = {(11, 22)}
        self.launches = []
        self.closed = False
        self.case.events.append(("scope", self))
        if self.case.constructor_error is not None:
            raise self.case.constructor_error

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        self.case.events.append(("spawn", self))
        self.case.calls.append({"argv": argv, "cwd": cwd, "environment": env, "stdout": stdout, "stderr": stderr})
        self.launches.append({"created": True, "cwd": cwd, "argv": argv, "outputMode": "model-supplied-files"})
        if self.case.spawn_error is not None:
            raise self.case.spawn_error
        out, err = self.case.outputs(argv)
        os.write(stdout.fileno(), out)
        os.write(stderr.fileno(), err)
        if self.case.after_write is not None:
            self.case.after_write(stdout, stderr)
        return SimpleNamespace(stdout=None, stderr=None, poll=self.poll)

    def poll(self):
        self.case.events.append(("poll", self))
        if self.case.poll_error is not None:
            raise self.case.poll_error
        if self.case.poll_callback is not None:
            return self.case.poll_callback()
        return self.case.exit_code

    def discover(self):
        self.case.events.append(("discover", self))
        if self.case.discovery_error is not None:
            raise self.case.discovery_error
        return self.case.live

    def drain(self, *, grace, kill_wait, deadline=None):
        self.drain_deadline = deadline
        self.case.events.append(("drain", self, grace, kill_wait))
        if self.case.drain_error is not None:
            raise self.case.drain_error
        return self.case.survivors

    def description(self):
        self.case.events.append(("description", self))
        if self.case.description_error is not None:
            raise self.case.description_error
        return {"backend": "OFFLINE_SCOPE_MODEL", "scope": "MODELED_NOT_NATIVE", "job": self.job,
                "invocation": self.invocation, "launches": self.launches,
                "startedIdentities": [{"pid": 99}], "discoveryErrors": self.case.discovery_errors}

    def close(self):
        self.case.events.append(("scope-close", self))
        if self.case.close_error is not None:
            raise self.case.close_error
        self.closed = True


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="query-offline-", dir=ROOT.parent)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir(mode=0o700)
        self.state = self.base / "private"
        self.events, self.calls, self.owners = [], [], []
        self.clock = Clock()
        self.constructor_error = self.spawn_error = self.poll_error = None
        self.discovery_error = self.drain_error = self.description_error = self.close_error = None
        self.poll_callback = self.after_write = None
        self.live, self.survivors, self.discovery_errors = [], [], []
        self.exit_code = 0
        self.out, self.err = b"model-output\x00\xff\r\n", b"model-private-stderr\x00\xff\n"
        self.output_callback = None
        self.cancel_error = None
        self.patches = ExitStack()
        self.patches.enter_context(patch.dict(os.environ, {}, clear=True))
        self.patches.enter_context(patch.object(Q.processes, "host_role", return_value="macos-arm64"))
        self.patches.enter_context(patch.object(Q.processes, "make_scope", side_effect=self.make_scope))
        self.patches.enter_context(patch.object(Q.shutil, "which", return_value="/usr/bin/git"))
        self.patches.enter_context(patch.object(Q.time, "monotonic", side_effect=self.clock.monotonic))
        self.patches.enter_context(patch.object(Q.time, "sleep", side_effect=self.clock.sleep))
        self.patches.enter_context(patch.object(Q.processes.subprocess, "Popen", side_effect=AssertionError("NO_REAL_CHILD")))
        self.patches.enter_context(patch.object(Q.signal, "getsignal", return_value="MODEL_HANDLER"))
        self.patches.enter_context(patch.object(Q.signal, "signal", return_value="MODEL_HANDLER"))
        self.original_quarantine = list(Q.QUARANTINE)

    def tearDown(self):
        # Synthetic unknown workers never existed. Retire only fixture-owned
        # files explicitly; this does not model a production UNKNOWN cleanup.
        for owner in self.owners:
            for resource in reversed(owner.resources):
                obj = resource["owner"]
                if isinstance(obj, (Q._PosixSink, Q._PosixDirectory)):
                    try:
                        obj.close()
                    except BaseException:
                        pass
        Q.QUARANTINE[:] = self.original_quarantine
        self.patches.close()
        self.temp.cleanup()

    def make_scope(self, job, invocation, state, home):
        return Scope(self, job, invocation, state, home)

    def outputs(self, argv):
        return (self.out, self.err) if self.output_callback is None else self.output_callback(argv)

    def cancellation(self):
        if self.cancel_error is not None:
            raise self.cancel_error

    def owner(self):
        value = Q.NativeGitQueries(self.root, self.state, check_cancel=self.cancellation)
        self.owners.append(value)
        return value

    def arguments(self, owner, *suffix):
        return (owner.executable, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                "-C", str(self.root), *suffix)

    def query(self, owner, *suffix, **overrides):
        args = {"argv": self.arguments(owner, *(suffix or ("rev-parse", "--show-toplevel"))),
                "cwd": self.root, "environment": dict(owner.git_environment),
                "stdout_limit": 4096, "stderr_limit": 4096, "timeout_seconds": 15}
        args.update(overrides)
        return owner(**args)

    def close_failed(self, owner):
        with self.assertRaises(BaseException):
            owner.close()

    def test_success_returns_original_bytes_only_after_drain_and_receipt(self):
        owner = self.owner()
        self.assertEqual(self.query(owner), self.out)
        self.assertTrue(self.calls)
        self.assertEqual([item[0] for item in self.events][-3:], ["drain", "description", "scope-close"])
        row = owner.records[0]
        private = self.state / ("query-" + row["id"])
        self.assertEqual((private / "stdout.log").read_bytes(), self.out)
        self.assertEqual((private / "stderr.log").read_bytes(), self.err)
        self.assertEqual(json.loads((private / "result.json").read_bytes())["retirement"], "KNOWN")
        self.assertEqual(row["outputs"]["stdout"]["sha256"], hashlib.sha256(self.out).hexdigest())
        owner.close()
        self.assertTrue(all(item["closed"] for item in owner.resources))

    def test_successful_readbacks_hash_exact_metadata_and_capture_bytes(self):
        owner = self.owner()
        self.assertEqual(self.query(owner), self.out)
        directory = self.state / ("query-" + owner.records[0]["id"])
        expected = [(self.state, "owner.json"), *((directory, name) for name in
            ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"))]
        self.assertEqual([(Path(row["parent"]), row["name"]) for row in owner.readbacks], expected)
        for row, (parent, name) in zip(owner.readbacks, expected):
            with self.subTest(name=name):
                raw = (parent / name).read_bytes()
                self.assertEqual(set(row), {"parent", "name", "maximum", "retirement", "result", "bytes", "sha256"})
                self.assertEqual((row["retirement"], row["result"]), ("KNOWN", "RETAINED"))
                self.assertEqual(row["bytes"], len(raw))
                self.assertEqual(row["maximum"], 4096 if name.endswith(".log") else max(1, len(raw)))
                self.assertEqual(row["sha256"], hashlib.sha256(raw).hexdigest())
        owner.close()

    def test_zero_byte_captures_retain_the_empty_digest_not_an_absent_hash(self):
        self.out = self.err = b""
        owner = self.owner()
        self.assertEqual(self.query(owner), b"")
        captures = [row for row in owner.readbacks if row["name"].endswith(".log")]
        self.assertEqual([row["name"] for row in captures], ["stdout.log", "stderr.log"])
        for row in captures:
            self.assertEqual((row["bytes"], row["maximum"]), (0, 4096))
            self.assertEqual(row["sha256"], hashlib.sha256(b"").hexdigest())
        owner.close()

    def test_session_encodes_prior_hashes_but_not_its_own_readback_tail(self):
        owner = self.owner()
        self.query(owner)
        prior = [dict(row) for row in owner.readbacks]
        owner.close()
        raw = (self.state / "session-result.json").read_bytes()
        session = json.loads(raw)
        self.assertEqual(session["readbacks"], prior)
        self.assertTrue(all("sha256" in row for row in session["readbacks"]))
        self.assertFalse(any(row["name"] == "session-result.json" for row in session["readbacks"]))
        self.assertEqual(owner.readbacks[:-1], prior)
        self.assertEqual(owner.readbacks[-1], {"parent": str(self.state), "name": "session-result.json",
            "maximum": len(raw), "retirement": "KNOWN", "result": "RETAINED", "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()})
        self.assertTrue(all(row["closed"] for row in owner.resources))

    def test_failed_delegated_reader_keeps_unknown_and_no_success_hash(self):
        owner = self.owner()
        read = Q._PosixDirectory.read_bytes
        original = OSError("MODELED_ORIGINAL_READBACK_FAILURE")
        original.__notes__ = ["MODELED_READER_RETIREMENT_UNKNOWN"]
        def fail_read(directory, name, **kwargs):
            if name == "stdout.log":
                raise original
            return read(directory, name, **kwargs)
        with patch.object(Q._PosixDirectory, "read_bytes", new=fail_read), self.assertRaises(Q.QueryError):
            self.query(owner)
        failed = [row for row in owner.readbacks if row["name"] == "stdout.log"]
        self.assertEqual(len(failed), 1)
        self.assertEqual((failed[0]["retirement"], failed[0]["result"]), ("UNKNOWN", "HOLD"))
        self.assertNotIn("sha256", failed[0])
        self.assertNotIn("bytes", failed[0])
        self.assertIn("MODELED_ORIGINAL_READBACK_FAILURE", failed[0]["error"])
        self.assertEqual(failed[0]["notes"], original.__notes__)
        self.assertIs(owner.first_error, original)
        self.assertTrue(owner.unknown)
        self.assertIn(owner, Q.QUARANTINE)
        self.close_failed(owner)

    def test_readback_digest_work_cannot_outlive_its_original_deadline(self):
        owner = self.owner()
        raw = (self.state / "owner.json").read_bytes()
        expected, end, calls = hashlib.sha256(raw).hexdigest(), owner.io_deadline, []
        sha256 = Q.hashlib.sha256
        def late_digest(value):
            self.assertEqual(value, raw)
            actual = sha256(value)
            def hexdigest():
                calls.append(self.clock.now)
                self.clock.now = end
                return actual.hexdigest()
            return SimpleNamespace(hexdigest=hexdigest)
        with patch.object(Q.hashlib, "sha256", side_effect=late_digest):
            with self.assertRaisesRegex(Q.posix_files.EvidenceError, "exceeded its deadline"):
                owner._readback(owner.private, "owner.json", len(raw), end)
        self.assertEqual(calls, [100.0])
        self.assertEqual(owner.io_deadline, end)
        self.assertEqual(self.clock.now, end)
        self.assertEqual(owner.readbacks[-1]["sha256"], expected)
        self.assertEqual(owner.readbacks[-1]["retirement"], "KNOWN")
        # Retained bytes are not timely success; this direct leaf test did not
        # enter an enclosing query. Its separate session-close phase is unchanged.
        owner.close()

    def test_final_receipt_hash_expiry_prevents_query_success(self):
        owner = self.owner()
        read, sha256 = Q._PosixDirectory.read_bytes, Q.hashlib.sha256
        target, hashed = [], []
        def observe_read(directory, name, **kwargs):
            raw = read(directory, name, **kwargs)
            if name == "result.json":
                target.append(raw)
            return raw
        def late_digest(raw):
            actual = sha256(raw)
            if target and raw == target[0]:
                hashed.append(raw)
                self.clock.now = owner.io_deadline
            return actual
        with patch.object(Q._PosixDirectory, "read_bytes", new=observe_read), \
                patch.object(Q.hashlib, "sha256", side_effect=late_digest), self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertEqual(len(hashed), 1)
        self.assertEqual((self.clock.now, owner.io_deadline), (160.0, 160.0))
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.assertFalse(owner.unknown)  # The actual reader did return and close.
        self.assertTrue(any(row["phase"] == "original-query-receipt" for row in owner.errors))
        self.close_failed(owner)

    def test_each_query_has_its_own_real_backend_domain_and_original_baseline(self):
        owner = self.owner()
        self.query(owner)
        self.query(owner, "rev-parse", "--verify", "HEAD^{commit}")
        self.assertEqual(len({row["id"] for row in owner.records}), 2)
        for row in owner.records:
            env = json.loads((self.state / ("query-" + row["id"]) / "start.json").read_bytes())["environment"]
            domains = Q.processes.ownership_domains(env[Q.processes.CHAIN_ENV], env[Q.processes.DOMAINS_ENV])
            self.assertEqual(domains[-1], {"id": row["id"], "job": owner.job,
                                           "state": str(owner.path), "home": str(owner.home.path)})
            baseline = json.loads((self.state / ("query-" + row["id"]) / "baseline.json").read_bytes())
            self.assertEqual(baseline["baseline"], [[11, 22]])
        owner.close()

    def test_complete_existing_parent_context_survives_sanitized_git_environment(self):
        parent = {"id": "a" * 32, "job": "b" * 32, "state": "/modeled-parent", "home": "/modeled-parent/home"}
        os.environ.update({Q.processes.JOB_ENV: parent["job"], Q.processes.CHAIN_ENV: parent["id"],
                           Q.processes.DOMAINS_ENV: json.dumps([parent]), Q.processes.STATE_ENV: parent["state"],
                           "GRADLE_USER_HOME": parent["home"], "TOKEN_SHOULD_NOT_PASS": "private-ambient-token"})
        owner = self.owner()
        self.query(owner)
        env = self.calls[0]["environment"]
        self.assertNotIn("TOKEN_SHOULD_NOT_PASS", env)
        self.assertEqual(Q.processes.ownership_domains(env[Q.processes.CHAIN_ENV], env[Q.processes.DOMAINS_ENV])[0], parent)
        owner.close()

    def test_partial_parent_context_rejected_before_private_allocation(self):
        os.environ[Q.processes.JOB_ENV] = "a" * 32
        with self.assertRaisesRegex(Q.QueryError, "PARTIAL_ANCESTOR"):
            self.owner()
        self.assertFalse(self.state.exists())
        self.assertFalse(self.events)

    def test_raw_nonascii_parent_domains_rejected_before_private_allocation(self):
        domain = {"id": "a" * 32, "job": "b" * 32, "state": "/p/é", "home": "/p/é/home"}
        os.environ.update({Q.processes.JOB_ENV: domain["job"], Q.processes.CHAIN_ENV: domain["id"],
                           Q.processes.DOMAINS_ENV: json.dumps([domain], ensure_ascii=False),
                           Q.processes.STATE_ENV: domain["state"], "GRADLE_USER_HOME": domain["home"]})
        with self.assertRaisesRegex(Q.QueryError, "NONASCII"):
            self.owner()
        self.assertFalse(self.state.exists())
        self.assertFalse(self.events)

    def test_ambient_home_is_not_forged_parent_ownership(self):
        os.environ["GRADLE_USER_HOME"] = "/ordinary-ambient-home"
        owner = self.owner()
        self.query(owner)
        env = self.calls[0]["environment"]
        self.assertEqual(len(Q.processes.ownership_domains(env[Q.processes.CHAIN_ENV], env[Q.processes.DOMAINS_ENV])), 1)
        self.assertEqual(env["GRADLE_USER_HOME"], str(owner.home.path))
        owner.close()

    def test_changed_parent_or_git_environment_rejects_before_launch(self):
        owner = self.owner()
        os.environ["GRADLE_USER_HOME"] = "/changed"
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertFalse(self.events)
        self.assertTrue(owner.failed)
        self.close_failed(owner)

    def test_write_fetch_shell_and_extra_git_options_are_not_callable(self):
        for suffix in (("fetch", "origin"), ("checkout", "main"), ("config", "x", "y"),
                       ("--exec-path=/bad", "status"), ("cat-file", "blob", "HEAD:private"),
                       ("rev-parse", "--verify", "main^{commit}")):
            with self.subTest(suffix=suffix):
                self.assertFalse(Q._allowed_suffix(suffix))
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner, "fetch", "origin")
        self.assertFalse(self.events)
        self.assertTrue(owner.failed)
        self.close_failed(owner)

    def test_caller_cannot_add_credentials_or_git_overrides(self):
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner, environment={**owner.git_environment, "GIT_CONFIG_COUNT": "1"})
        self.assertFalse(self.events)
        self.close_failed(owner)

    def test_all_identity_git_suffixes_are_admitted(self):
        suffixes = [("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
                    ("rev-parse", "--verify", "HEAD^{commit}"),
                    ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
                    ("rev-parse", "--verify", SOURCE + "^{commit}"),
                    ("rev-parse", "--verify", SOURCE + "^{tree}"),
                    ("show", "-s", "--format=%P", SOURCE),
                    ("show", "-s", "--format=%B", SOURCE),
                    ("ls-tree", "-z", SOURCE, "--", Q.identity.POLICY_PATH),
                    ("cat-file", "-s", SOURCE), ("cat-file", "blob", SOURCE)]
        owner = self.owner()
        for suffix in suffixes:
            with self.subTest(suffix=suffix):
                self.assertEqual(self.query(owner, *suffix), self.out)
        owner.close()

    def test_message_query_accepts_no_mutable_ref_format_or_extra_argument(self):
        for suffix in (("show", "-s", "--format=%B", "HEAD"),
                       ("show", "-s", "--format=%B", SOURCE[:12]),
                       ("show", "-s", "--format=%B", SOURCE, "--"),
                       ("show", "-s", "--format=%B%x00%N", SOURCE),
                       ("show", "--format=%B", SOURCE)):
            with self.subTest(suffix=suffix):
                self.assertFalse(Q._allowed_suffix(suffix))
        self.assertTrue(Q._allowed_suffix(("show", "-s", "--format=%B", SOURCE)))
        self.assertEqual(Q.FINALIZATION_SECONDS, 45)

    def test_only_the_eight_exact_abi_paths_extend_ls_tree_admission(self):
        for path in Q.identity.abi.BASELINES:
            with self.subTest(path=path):
                self.assertTrue(Q._allowed_suffix(("ls-tree", "-z", SOURCE, "--", path)))
                for ref in ("HEAD", "main", SOURCE + "~1", SOURCE[:12]):
                    self.assertFalse(Q._allowed_suffix(("ls-tree", "-z", ref, "--", path)))
                for wrong in (path + "/", path + ".extra", "/" + path, path.replace("/api/", "/api/../api/")):
                    self.assertFalse(Q._allowed_suffix(("ls-tree", "-z", SOURCE, "--", wrong)))
        for suffix in (("ls-tree", "-z", SOURCE, "--", "private.key"),
                       ("ls-tree", "-r", "-z", SOURCE, "--", Q.identity.abi.BASELINES[0]),
                       ("ls-tree", "-z", SOURCE, "--", *Q.identity.abi.BASELINES[:2])):
            self.assertFalse(Q._allowed_suffix(suffix))
        self.assertEqual(Q.MAX_QUERIES, 64)
        self.assertEqual(Q.MAX_SESSION_BYTES, 64 * 1024 * 1024)

    def test_empty_git_stdout_is_valid_and_stderr_is_still_retained(self):
        self.out = b""
        owner = self.owner()
        self.assertEqual(self.query(owner), b"")
        self.assertEqual(owner.records[0]["outputs"]["stdout"]["bytes"], 0)
        owner.close()

    def test_nonzero_git_exit_never_returns_stdout(self):
        self.exit_code = 1
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        row = owner.records[0]
        self.assertEqual(row["waitExitCode"], 1)
        self.assertEqual(row["retirement"], "KNOWN")
        self.assertEqual(row["result"], "HOLD")
        self.assertEqual((self.state / ("query-" + row["id"]) / "stdout.log").read_bytes(), self.out)
        self.close_failed(owner)

    def test_live_stdout_overflow_is_rejected_before_result(self):
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner, stdout_limit=2)
        self.assertTrue(any(event[0] == "drain" for event in self.events))
        self.assertEqual(owner.records[0]["waitExitCode"], None)
        self.close_failed(owner)

    def test_live_stderr_overflow_is_independently_rejected(self):
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner, stderr_limit=2)
        self.assertTrue(any(event[0] == "drain" for event in self.events))
        self.assertEqual(owner.records[0]["waitExitCode"], None)
        self.close_failed(owner)

    def test_deadline_has_no_success_even_when_final_drain_succeeds(self):
        self.exit_code = None
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner, timeout_seconds=0.05)
        self.assertEqual(owner.records[0]["retirement"], "KNOWN")
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.close_failed(owner)

    def test_expired_query_deadline_prevents_a_late_product_launch(self):
        def delayed_scope(job, invocation, state, home):
            result = Scope(self, job, invocation, state, home)
            self.clock.now += 16
            return result
        owner = self.owner()
        with patch.object(Q.processes, "make_scope", side_effect=delayed_scope):
            with self.assertRaises(Q.QueryError):
                self.query(owner)
        self.close_failed(owner)
        self.assertFalse(any(event[0] == "spawn" for event in self.events))
        self.assertFalse(owner.records[0]["launchAttempted"])

    def test_natural_descendant_completion_is_required_not_forced_drain_success(self):
        self.live = [{"pid": 42}]
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertEqual(owner.records[0]["waitExitCode"], 0)
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.assertFalse(owner.unknown)
        self.close_failed(owner)

    def test_constructor_failure_without_scope_is_sticky_unknown(self):
        self.constructor_error = OSError("private-constructor-failure")
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertTrue(owner.unknown)
        self.assertEqual(owner.records[0]["retirement"], "UNKNOWN")
        self.assertFalse(any(event[0] == "spawn" for event in self.events))
        self.assertIn(owner, Q.QUARANTINE)
        self.close_failed(owner)
        self.assertFalse(next(item for item in owner.resources if item["label"] == "private-root")["closeAttempted"])

    def test_spawn_failure_still_drains_original_scope(self):
        self.spawn_error = OSError("modeled-spawn-failure")
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertEqual([event[0] for event in self.events][-3:], ["drain", "description", "scope-close"])
        self.close_failed(owner)

    def test_failed_drain_quarantines_original_sinks_and_roots(self):
        self.drain_error = OSError("private-drain-failure")
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertTrue(owner.unknown)
        self.assertEqual(owner.records[0]["retirement"], "UNKNOWN")
        for label in ("stdout", "stderr", "query-directory", "private-root", "query-home"):
            self.assertFalse(next(item for item in owner.resources if item["label"] == label)["closeAttempted"])
        self.close_failed(owner)

    def test_survivors_are_unknown_and_cannot_be_reset_by_another_query(self):
        self.survivors = [{"pid": 42}]
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.survivors = []
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertEqual(len(owner.records), 1)
        self.assertTrue(owner.unknown)
        self.close_failed(owner)

    def test_discovery_error_prevents_success_despite_empty_drain(self):
        self.discovery_errors = ["modeled-unresolved-discovery"]
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertTrue(owner.unknown)
        self.close_failed(owner)

    def test_native_close_failure_is_unknown_and_never_retried(self):
        self.close_error = OSError("modeled-ambiguous-native-close")
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.close_failed(owner)
        self.close_failed(owner)
        self.assertEqual(sum(event[0] == "scope-close" for event in self.events), 1)
        self.assertTrue(owner.unknown)

    def test_primary_cancellation_survives_secondary_drain_failure(self):
        original = KeyboardInterrupt("modeled-original-cancellation")
        self.poll_error = original
        self.drain_error = OSError("modeled-secondary-drain")
        owner = self.owner()
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.query(owner)
        self.assertIs(caught.exception, original)
        self.assertIs(owner.first_error, original)
        self.assertGreaterEqual(len(owner.records[0]["errors"]), 2)
        self.assertTrue(owner.unknown)
        self.close_failed(owner)

    def test_owner_cancellation_before_scope_allocates_no_process(self):
        owner = self.owner()
        original = KeyboardInterrupt("modeled-before-query")
        self.cancel_error = original
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.query(owner)
        self.assertIs(caught.exception, original)
        self.assertFalse(self.events)
        self.close_failed(owner)

    def test_sink_replacement_is_rejected_and_originals_are_not_deleted(self):
        def replace(out, _):
            path = out.path
            path.rename(path.with_name("original-stdout.log"))
            path.write_bytes(b"replacement")
            path.chmod(0o600)
        self.after_write = replace
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        directory = self.state / ("query-" + owner.records[0]["id"])
        self.assertEqual((directory / "original-stdout.log").read_bytes(), self.out)
        self.close_failed(owner)

    def test_receipt_write_failure_cannot_return_captured_output(self):
        owner = self.owner()
        original_write = owner._write
        def fail_result(parent, name, value):
            if name == "result.json":
                raise OSError("modeled-result-disk-failure")
            return original_write(parent, name, value)
        with patch.object(owner, "_write", side_effect=fail_result):
            with self.assertRaises(Q.QueryError):
                self.query(owner)
        self.assertTrue(owner.failed)
        self.close_failed(owner)
        self.assertTrue(any(item["phase"] == "original-query-receipt" for item in owner.errors))

    def test_private_sink_creation_failure_is_unknown_not_clean_absence(self):
        owner = self.owner()
        original_create = Q._PosixDirectory.create_file
        def create(parent, name, **kwargs):
            if name == "stderr.log":
                raise OSError("modeled-partial-native-file-allocation")
            return original_create(parent, name, **kwargs)
        with patch.object(Q._PosixDirectory, "create_file", new=create):
            with self.assertRaises(Q.QueryError):
                self.query(owner)
        self.assertTrue(owner.unknown)
        self.assertFalse(self.events)
        self.close_failed(owner)

    def test_admission_cancel_after_allocation_has_unconditional_owner_finalizer(self):
        self.hosted(policy_present=True)
        allocate = Q.NativeGitQueries
        installed = {}
        def signal_handler(number, handler):
            installed[number] = handler
        def allocation(*args, **kwargs):
            owner = allocate(*args, **kwargs)
            self.owners.append(owner)
            installed[Q.signal.SIGTERM](Q.signal.SIGTERM, None)
            return owner
        with patch.object(Q.signal, "signal", side_effect=signal_handler), \
                patch.object(Q, "NativeGitQueries", side_effect=allocation):
            with self.assertRaises(KeyboardInterrupt):
                Q.admit_hosted("desktop", self.root, self.state)
        owner = self.owners[-1]
        self.assertFalse(self.events)
        self.assertTrue(owner.closed)
        self.assertTrue(owner.failed)
        self.assertFalse(owner.unknown)
        self.assertTrue(all(resource["closed"] for resource in owner.resources))
        self.assertEqual(json.loads((self.state / "session-result.json").read_bytes())["result"], "HOLD")

    def test_context_entry_cancellation_preserved_across_secondary_close_unknown(self):
        owner = self.owner()
        original = KeyboardInterrupt("MODELED_ENTRY_CANCELLATION")
        self.cancel_error = original
        close = Q._PosixDirectory.close
        def fail_home(directory):
            if directory is owner.home:
                raise OSError("MODELED_ENTRY_CLOSE_UNKNOWN")
            return close(directory)
        with patch.object(Q._PosixDirectory, "close", new=fail_home):
            with self.assertRaises(KeyboardInterrupt) as caught:
                with owner:
                    self.fail("Cancelled context entry must not reach its body")
        self.assertIs(caught.exception, original)
        self.assertTrue(owner.closed)
        self.assertTrue(owner.unknown)
        self.assertIn(owner, Q.QUARANTINE)
        self.assertFalse(self.events)
        root = next(row for row in owner.resources if row["label"] == "private-root")
        self.assertFalse(root["closeAttempted"])
        self.assertTrue(any(row["phase"] == "query-home-close" for row in owner.errors))

    def test_final_query_receipt_cannot_renew_absolute_finalization_budget(self):
        owner = self.owner()
        write = owner._write
        def slow_final(parent, name, value):
            if name == "result.json":
                self.clock.now += 61
            return write(parent, name, value)
        with patch.object(owner, "_write", side_effect=slow_final):
            with self.assertRaises(Q.QueryError):
                self.query(owner)
        self.assertEqual(self.clock.now, 161)
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.assertTrue(any(event[0] == "drain" for event in self.events))
        self.close_failed(owner)

    def test_receipt_reader_does_not_renew_its_writer_absolute_deadline(self):
        owner = self.owner()
        sync, read = Q._PosixSink.sync, Q._PosixDirectory.read_bytes
        def slow_sync(stream):
            if stream.path.name == "result.json":
                self.clock.now += 40
            return sync(stream)
        def slow_read(directory, name, **kwargs):
            if name == "result.json":
                self.clock.now += 21
            return read(directory, name, **kwargs)
        with patch.object(Q._PosixSink, "sync", new=slow_sync), \
                patch.object(Q._PosixDirectory, "read_bytes", new=slow_read):
            with self.assertRaises(Q.QueryError):
                self.query(owner)
        self.assertEqual(self.clock.now, 161)
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.close_failed(owner)

    def test_final_callback_rechecks_cancellation_after_each_finalization_boundary(self):
        for phase in ("native-drain", "receipt-readback", "directory-close"):
            with self.subTest(phase=phase):
                self.state = self.base / phase
                self.cancel_error = None
                owner = self.owner()
                original = KeyboardInterrupt("MODELED_LATE_CANCEL_" + phase)
                drain, read, close = Scope.drain, Q._PosixDirectory.read_bytes, Q._PosixDirectory.close
                def cancel_drain(scope, **kwargs):
                    if phase == "native-drain":
                        self.cancel_error = original
                    return drain(scope, **kwargs)
                def cancel_read(directory, name, **kwargs):
                    if phase == "receipt-readback" and name == "result.json":
                        self.cancel_error = original
                    return read(directory, name, **kwargs)
                def cancel_close(directory):
                    if phase == "directory-close" and directory.path.name.startswith("query-"):
                        self.cancel_error = original
                    return close(directory)
                with patch.object(Scope, "drain", new=cancel_drain), \
                        patch.object(Q._PosixDirectory, "read_bytes", new=cancel_read), \
                        patch.object(Q._PosixDirectory, "close", new=cancel_close):
                    with self.assertRaises(KeyboardInterrupt) as caught:
                        self.query(owner)
                self.assertIs(caught.exception, original)
                self.assertIs(owner.cancellation, original)
                self.assertEqual(owner.records[0]["result"], "HOLD")
                self.close_failed(owner)

    def test_posix_reader_fdopen_failure_retires_its_allocated_descriptor(self):
        owner = self.owner()
        read = Q._PosixDirectory.read_bytes
        allocated = []
        def refuse_adoption(descriptor, *args, **kwargs):
            allocated.append(descriptor)
            raise OSError("MODELED_FDOPEN_ADOPTION_FAILURE")
        def readback(directory, name, **kwargs):
            if name == "stdout.log":
                with patch.object(Q.os, "fdopen", side_effect=refuse_adoption):
                    return read(directory, name, **kwargs)
            return read(directory, name, **kwargs)
        try:
            with patch.object(Q._PosixDirectory, "read_bytes", new=readback):
                with self.assertRaises(Q.QueryError):
                    self.query(owner)
            self.assertEqual(len(allocated), 1)
            for descriptor in allocated:
                with self.assertRaises(OSError):
                    os.fstat(descriptor)
            self.assertTrue(owner.unknown)  # No inference from an opaque supplier failure.
            self.close_failed(owner)
        finally:
            for descriptor in allocated:
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def test_posix_adoption_retirement_failure_preserves_primary_and_quarantines(self):
        owner = self.owner()
        read = Q._PosixDirectory.read_bytes
        allocated, attempts = [], []
        original = OSError("MODELED_ORIGINAL_ADOPTION_FAILURE")
        def refuse_adoption(descriptor, *args, **kwargs):
            allocated.append(descriptor)
            raise original
        def fail_close(descriptor):
            attempts.append(descriptor)
            raise OSError("MODELED_SECONDARY_DESCRIPTOR_CLOSE")
        def readback(directory, name, **kwargs):
            if name == "stdout.log":
                with patch.object(Q.os, "fdopen", side_effect=refuse_adoption), \
                        patch.object(Q.os, "close", side_effect=fail_close):
                    return read(directory, name, **kwargs)
            return read(directory, name, **kwargs)
        try:
            with patch.object(Q._PosixDirectory, "read_bytes", new=readback):
                with self.assertRaises(Q.QueryError):
                    self.query(owner)
            self.assertEqual(attempts, allocated)
            self.assertEqual(len(attempts), 1)
            self.assertIs(owner.first_error, original)
            self.assertTrue(any("MODELED_SECONDARY_DESCRIPTOR_CLOSE" in note
                                for note in getattr(original, "__notes__", ())))
            self.assertTrue(owner.unknown)
            root = next(row for row in owner.resources if row["label"] == "query-directory")
            self.assertFalse(root["closeAttempted"])
            self.close_failed(owner)
        finally:
            for descriptor in allocated:
                os.close(descriptor)  # Exact fixture descriptor; no real process/UNKNOWN worker exists.

    def test_posix_reader_primary_cancellation_survives_secondary_reader_close(self):
        owner = self.owner()
        read, fdopen = Q._PosixDirectory.read_bytes, Q.os.fdopen
        original = KeyboardInterrupt("MODELED_ORIGINAL_READER_CANCEL")
        closed = []
        class Reader:
            def __init__(self, descriptor):
                self.stream = fdopen(descriptor, "rb")
            def __enter__(self):
                return self
            def __exit__(self, *_):
                self.close()
                return False
            def fileno(self):
                return self.stream.fileno()
            def read(self, _):
                raise original
            def close(self):
                self.stream.close()
                closed.append(True)
                raise OSError("MODELED_SECONDARY_READER_CLOSE")
        def readback(directory, name, **kwargs):
            if name == "stdout.log":
                with patch.object(Q.os, "fdopen", side_effect=lambda descriptor, *_: Reader(descriptor)):
                    return read(directory, name, **kwargs)
            return read(directory, name, **kwargs)
        with patch.object(Q._PosixDirectory, "read_bytes", new=readback):
            with self.assertRaises(KeyboardInterrupt) as caught:
                self.query(owner)
        self.assertIs(caught.exception, original)
        self.assertEqual(closed, [True])
        self.assertTrue(any("MODELED_SECONDARY_READER_CLOSE" in note
                            for note in getattr(original, "__notes__", ())))
        self.assertTrue(owner.unknown)
        self.close_failed(owner)

    def test_public_cli_never_prints_private_exception_or_transcript(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(Q, "admit_hosted", side_effect=OSError("PRIVATE-CANARY-DO-NOT-PRINT")), \
                patch.object(sys, "stdout", out), patch.object(sys, "stderr", err):
            code = ENTRY.main(["--profile", "desktop", "--root", str(self.root),
                               "--evidence-directory", str(self.state)])
        self.assertEqual(code, 125)
        self.assertNotIn("PRIVATE-CANARY", out.getvalue() + err.getvalue())
        self.assertIn("no products started", err.getvalue())

    def policy(self):
        now = int(Q.identity.time.time())
        return Q.identity.encoded({"schema": 1, "repository": Q.identity.REPOSITORY,
            "purpose": "P2PKIT_TEST_TRANSCRIPTS", "notBefore": now - 1, "expiresAt": now + 600,
            "retentionDays": 14, "retrievalOwner": "synthetic-custodian",
            "recipient": {"publicKey": PUBLIC.decode(), "fingerprint": "A" * 40,
                          "sha256": hashlib.sha256(PUBLIC).hexdigest()}})

    def hosted(self, *, policy_present):
        event = {"repository": {"full_name": Q.identity.REPOSITORY, "default_branch": "main"},
                 "ref": "refs/heads/main", "after": SOURCE, "before": BEFORE, "deleted": False}
        event_path = self.base / "event.json"
        event_path.write_bytes(Q.identity.encoded(event))
        os.environ.update({"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": Q.identity.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SOURCE,
            "GITHUB_WORKFLOW_SHA": SOURCE, "GITHUB_WORKFLOW_REF":
                Q.identity.REPOSITORY + "/.github/workflows/desktop-cross-host.yml@refs/heads/main",
            "GITHUB_JOB": "verify", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS", "RUNNER_ARCH": "ARM64",
            "GITHUB_WORKSPACE": str(self.root), "GITHUB_EVENT_PATH": str(event_path)})
        raw = self.policy()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        def outputs(argv):
            suffix = tuple(argv[7:])
            if suffix == ("rev-parse", "--show-toplevel"):
                return str(self.root).encode() + b"\n", b""
            if suffix == ("status", "--porcelain=v1", "--untracked-files=all"):
                return b"", b""
            if suffix == ("rev-parse", "--verify", "HEAD^{commit}"):
                return SOURCE.encode() + b"\n", b""
            if suffix == ("rev-parse", "--verify", SOURCE + "^{tree}"):
                return TREE.encode() + b"\n", b""
            if suffix == ("show", "-s", "--format=%B", SOURCE):
                return b"SYNTHETIC ordinary merge\n", b""
            if suffix == ("show", "-s", "--format=%P", SOURCE):
                return (BEFORE + " " + TREE + "\n").encode(), b""
            if suffix == ("ls-tree", "-z", SOURCE, "--", Q.identity.POLICY_PATH):
                return ((b"100644 blob " + blob.encode() + b"\t" + Q.identity.POLICY_PATH.encode() + b"\0")
                        if policy_present else b""), b""
            if suffix == ("cat-file", "-s", blob):
                return str(len(raw)).encode() + b"\n", b""
            if suffix == ("cat-file", "blob", blob):
                return raw, b""
            raise AssertionError("Unexpected modeled identity query: " + repr(suffix))
        self.output_callback = outputs
        return raw, event_path.read_bytes()

    def test_actual_identity_caller_uses_bound_queries_and_missing_policy_holds(self):
        self.hosted(policy_present=False)
        with self.assertRaisesRegex(Q.identity.AdmissionError, "MISSING_TRUSTED_RECIPIENT_POLICY"):
            Q.admit_hosted("desktop", self.root, self.state)
        self.assertGreater(len(self.calls), 0)
        self.assertTrue(all(call["argv"][0] == "/usr/bin/git" for call in self.calls))
        self.assertTrue(all(event[1].closed for event in self.events if event[0] == "scope-close"))
        self.assertEqual(json.loads((self.state / "session-result.json").read_bytes())["result"], "HOLD")
        self.assertFalse((self.state / "admission.json").exists())
        self.assertTrue((self.state / "admission-failure.json").exists())

    def test_actual_identity_caller_retains_exact_bytes_and_never_claims_crypto_or_test(self):
        raw, event = self.hosted(policy_present=True)
        result = Q.admit_hosted("desktop", self.root, self.state)
        self.assertIsInstance(result, Q.identity.Admission)
        self.assertEqual((self.state / "original-policy.json").read_bytes(), raw)
        self.assertEqual((self.state / "original-event.json").read_bytes(), event)
        self.assertEqual((self.state / "recipient-public.asc").read_bytes(), PUBLIC)
        self.assertEqual(json.loads((self.state / "admission-scope.json").read_bytes())["scope"],
                         "IDENTITY_ONLY_NO_CRYPTO_NO_PRODUCTS_NO_UPLOAD")
        self.assertTrue(all(event[1].closed for event in self.events if event[0] == "scope-close"))

    def test_actual_native_role_disagreement_stops_before_first_git_query(self):
        self.hosted(policy_present=True)
        os.environ["RUNNER_ARCH"] = "X64"
        with self.assertRaisesRegex(Q.QueryError, "NATIVE_HOST_DIFFERS"):
            Q.admit_hosted("desktop", self.root, self.state)
        self.assertFalse(self.events)

    def test_main_success_message_is_only_admission_not_workflow_acceptance(self):
        out = io.StringIO()
        output = self.base / "outputs"
        output.write_bytes(b"")
        os.environ["GITHUB_OUTPUT"] = str(output)
        for required in (False, True):
            value = Q.identity.Admission(Q.identity.encoded({"profile": "desktop", "samplePackagingRequired": required}),
                                         b"synthetic", b"synthetic", b"synthetic", "A" * 40, "b" * 64, 3000)
            with patch.object(Q, "admit_hosted", return_value=value), patch.object(sys, "stdout", out):
                self.assertEqual(ENTRY.main(["--profile", "desktop", "--root", str(self.root),
                                            "--evidence-directory", str(self.state)]), 0)
        self.assertIn("no crypto validation, tests, export or upload", out.getvalue())
        self.assertEqual(output.read_bytes(), b"sample_packaging_required=false\nsample_packaging_required=true\n")

    def test_cli_output_sync_failure_cannot_grant_step_success(self):
        value = Q.identity.Admission(Q.identity.encoded({"profile": "desktop", "samplePackagingRequired": True}),
                                     b"synthetic", b"synthetic", b"synthetic", "A" * 40, "b" * 64, 3000)
        output = self.base / "outputs"
        output.write_bytes(b"")
        os.environ["GITHUB_OUTPUT"] = str(output)
        with patch.object(Q, "admit_hosted", return_value=value), \
                patch.object(ENTRY.os, "fsync", side_effect=OSError("PRIVATE-OUTPUT-FAILURE")), \
                patch.object(sys, "stderr", io.StringIO()) as err:
            self.assertEqual(ENTRY.main(["--profile", "desktop", "--root", str(self.root),
                                        "--evidence-directory", str(self.state)]), 125)
        self.assertNotIn("PRIVATE-OUTPUT-FAILURE", err.getvalue())



if __name__ == "__main__":
    unittest.main(verbosity=2)
