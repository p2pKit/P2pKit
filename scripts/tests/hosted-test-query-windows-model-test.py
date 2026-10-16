#!/usr/bin/env python3
"""Offline actual-NativeFile caller models; NO native Windows API/process run.

The real pinned filesystem classes use the existing in-memory WinAPI model. The
actual query adapter calls a modeled scope with NativeFiles; fileno() must never
be used. Native host, ACL inheritance and process-handle acceptance remain NOT_RUN.
"""
from __future__ import annotations

from contextlib import ExitStack
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_test_query as Q

spec = importlib.util.spec_from_file_location("query_windows_file_model", ROOT / "scripts/tests/hosted-windows-files-test.py")
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)
F = model.files


class NativeSinkScopeModel:
    def __init__(self, case, job, invocation, state, home):
        self.case = case
        self.job, self.invocation = job, invocation
        self.launches = []

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        self.case.calls.append((stdout, stderr, env))
        self.case.assertIsInstance(stdout, F.NativeFile)
        self.case.assertIsInstance(stderr, F.NativeFile)
        self.case.assertNotEqual(stdout.native_handle, stderr.native_handle)
        self.case.events.append("spawn")
        self.case.api.write(stdout.native_handle, self.case.out)
        self.case.api.write(stderr.native_handle, self.case.err)
        self.launches.append({"cwd": cwd, "created": True, "outputMode": "MODELED_NATIVE_FILES"})
        return SimpleNamespace(stdout=None, stderr=None, poll=lambda: 0)

    def discover(self):
        return []

    def drain(self, *, grace, kill_wait):
        self.case.events.append("drain")
        self.case.assertEqual((grace, kill_wait), (0, 5))
        if self.case.drain_error:
            raise self.case.drain_error
        return []

    def description(self):
        return {"backend": "MODELED_WINDOWS_SCOPE_NOT_NATIVE", "job": self.job,
                "invocation": self.invocation, "launches": self.launches,
                "startedIdentities": [{"pid": 1}], "discoveryErrors": []}

    def close(self):
        self.case.events.append("scope-close")


class WindowsQueryModels(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="query-win-model-", dir=ROOT.parent)
        self.root = Path(self.temp.name) / "source"
        self.root.mkdir(mode=0o700)
        self.target = Path(self.temp.name) / "private"
        self.api = model.ModelApi()
        self.owners, self.calls, self.events = [], [], []
        self.out, self.err = b"synthetic-native-output\x00\xff\n", b"synthetic-private-stderr\x00\n"
        self.drain_error = None
        self.patches = ExitStack()
        self.patches.enter_context(patch.dict(os.environ, {}, clear=True))
        self.patches.enter_context(patch.object(Q.processes, "host_role", return_value="windows-x64"))
        self.patches.enter_context(patch.object(Q.shutil, "which", return_value="/usr/bin/git"))
        self.patches.enter_context(patch.object(Q, "_new_private_directory", side_effect=self.new_root))
        self.patches.enter_context(patch.object(Q.processes, "make_scope", side_effect=
            lambda job, invocation, state, home: NativeSinkScopeModel(self, job, invocation, state, home)))
        self.patches.enter_context(patch.object(F.NativeFile, "fileno", side_effect=AssertionError("WIN32_IS_NOT_CRT")))
        self.patches.enter_context(patch.object(Q.processes.subprocess, "Popen", side_effect=AssertionError("NO_CHILD")))
        self.original_quarantine = list(Q.QUARANTINE)

    def new_root(self, path):
        self.assertEqual(path, self.target)
        return F._root(r"C:\work\query-private", self.api, create=True)

    def tearDown(self):
        # All handles here are integer model entries, not native handles. Reset
        # fault injection only to dispose test fixtures after UNKNOWN assertions.
        self.api.close_failure = None
        self.api.flush_failure = False
        self.api.inspect_failure = None
        for owner in self.owners:
            for resource in reversed(owner.resources):
                value = resource["owner"]
                if isinstance(value, (F.NativeFile, F.PrivateDirectory)):
                    try:
                        value.close()
                    except BaseException:
                        pass
        self.assertEqual(self.api.handles, {}, "Unaccounted OFFLINE model handles")
        Q.QUARANTINE[:] = self.original_quarantine
        self.patches.close()
        self.temp.cleanup()

    def owner(self):
        value = Q.NativeGitQueries(self.root, self.target, check_cancel=lambda: None)
        self.owners.append(value)
        return value

    def query(self, owner, **limits):
        return owner(argv=(owner.executable, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                           "-C", str(self.root), "rev-parse", "--show-toplevel"),
                     cwd=self.root, environment=dict(owner.git_environment), stdout_limit=limits.get("stdout", 4096),
                     stderr_limit=limits.get("stderr", 4096), timeout_seconds=15)

    def close_failed(self, owner):
        with self.assertRaises(Q.QueryError):
            owner.close()


    def actual_stream_query(self, *, post_drain_growth=False):
        queries = model.StreamQueryModel(self.api)
        original_spawn, original_close = NativeSinkScopeModel.spawn, NativeSinkScopeModel.close
        def spawn(scope, argv, cwd, env, *, stdout, stderr):
            child = original_spawn(scope, argv, cwd, env, stdout=stdout, stderr=stderr)
            queries.append_after_standard(stdout.native_handle, b"+stdout")
            queries.append_after_standard(stderr.native_handle, b"+stderr")
            return child
        def close(scope):
            original_close(scope)
            if post_drain_growth:
                queries.append_after_standard(self.calls[0][0].native_handle, b"late")
        self.patches.enter_context(patch.object(NativeSinkScopeModel, "spawn", spawn))
        self.patches.enter_context(patch.object(NativeSinkScopeModel, "close", close))
        return self.owner(), queries

    def test_real_inspector_live_growth_is_captured_by_actual_query_loop(self):
        owner, queries = self.actual_stream_query()
        self.assertEqual(self.query(owner), self.out + b"+stdout")
        self.assertEqual(owner.records[0]["waitExitCode"], 0)
        self.assertEqual(sum(maximum is not None for _, maximum in queries.observations), 2)
        self.assertTrue(all(stream.closed for stream in self.calls[0][:2]))
        owner.close()

    def test_actual_query_post_drain_verification_does_not_allow_live_growth(self):
        owner, queries = self.actual_stream_query(post_drain_growth=True)
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertEqual(owner.records[0]["waitExitCode"], 0)
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.assertIn("Alternate data streams are not admitted", json.dumps(owner.records[0]))
        self.assertEqual(sum(maximum is not None for _, maximum in queries.observations), 2)
        self.assertTrue(all(stream.closed for stream in self.calls[0][:2]))
        self.close_failed(owner)

    def test_actual_nativefile_objects_are_borrowed_without_crt_conversion(self):
        owner = self.owner()
        self.assertEqual(self.query(owner), self.out)
        self.assertEqual(self.events, ["spawn", "drain", "scope-close"])
        row = owner.records[0]
        self.assertEqual(row["outputs"]["stdout"]["sha256"], hashlib.sha256(self.out).hexdigest())
        prefix = r"C:\work\query-private\query-" + row["id"]
        self.assertEqual(self.api.nodes[prefix + r"\stdout.log"].content, self.out)
        self.assertEqual(self.api.nodes[prefix + r"\stderr.log"].content, self.err)
        self.assertEqual(json.loads(self.api.nodes[prefix + r"\result.json"].content)["retirement"], "KNOWN")
        owner.close()
        self.assertEqual(self.api.handles, {})

    def test_unknown_native_domain_keeps_native_sink_and_ancestor_pins(self):
        self.drain_error = OSError("model-native-drain-unknown")
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        out, err, _ = self.calls[0]
        self.assertIn(out.native_handle, self.api.handles)
        self.assertIn(err.native_handle, self.api.handles)
        self.assertTrue(owner.unknown)
        self.assertIn(owner, Q.QUARANTINE)
        for label in ("stdout", "stderr", "query-directory", "private-root", "query-home"):
            self.assertFalse(next(item for item in owner.resources if item["label"] == label)["closeAttempted"])
        self.close_failed(owner)
        self.assertIn(out.native_handle, self.api.handles)
        self.assertIn(err.native_handle, self.api.handles)

    def test_native_live_bound_is_not_bypassed_by_direct_child_handle_write(self):
        owner = self.owner()
        with self.assertRaises(Q.QueryError):
            self.query(owner, stdout=2)
        self.assertIn("drain", self.events)
        self.assertIsNone(owner.records[0]["waitExitCode"])
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.close_failed(owner)

    def test_native_root_privacy_loss_blocks_query_before_child_launch(self):
        owner = self.owner()
        self.api.nodes[r"C:\work\query-private"].bad_acl = True
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        self.assertFalse(self.calls)
        self.assertTrue(owner.unknown)
        self.api.nodes[r"C:\work\query-private"].bad_acl = False
        self.close_failed(owner)

    def test_native_output_close_failure_is_retained_and_never_retried(self):
        owner = self.owner()
        old_make_scope = self.patches.enter_context(patch.object(Q.processes, "make_scope"))
        def scope(job, invocation, state, home):
            inner = NativeSinkScopeModel(self, job, invocation, state, home)
            original_spawn = inner.spawn
            def spawn(*args, **kwargs):
                result = original_spawn(*args, **kwargs)
                self.api.close_failure = kwargs["stdout"].native_handle
                return result
            inner.spawn = spawn
            return inner
        old_make_scope.side_effect = scope
        with self.assertRaises(Q.QueryError):
            self.query(owner)
        failed = self.api.close_failure
        self.assertTrue(owner.unknown)
        self.close_failed(owner)
        self.assertEqual(sum(item[0] == "close" and item[1] == failed for item in self.api.events), 1)
        self.assertTrue(any("stdout-close" == item["phase"] for item in owner.errors))

    def _reader_close_failure(self, name):
        owner = self.owner()
        close = F.NativeFile.close
        failures = []
        def fail_reader_close(stream):
            if not stream._retired and not stream.closed and stream.readable() and str(stream.path).endswith(name):
                self.api.close_failure = stream.native_handle
                failures.append(stream.native_handle)
            return close(stream)
        with patch.object(F.NativeFile, "close", new=fail_reader_close):
            with self.assertRaises(Q.QueryError):
                self.query(owner)
        self.assertEqual(len(failures), 1)
        self.assertTrue(owner.unknown)
        self.assertEqual(owner.records[0]["retirement"], "UNKNOWN")
        self.assertEqual(owner.records[0]["result"], "HOLD")
        self.assertTrue(any(row["name"] == name and row["retirement"] == "UNKNOWN" for row in owner.readbacks))
        for label in ("query-directory", "private-root", "query-home"):
            self.assertFalse(next(row for row in owner.resources if row["label"] == label)["closeAttempted"])
        self.close_failed(owner)
        self.assertEqual(sum(item[0] == "close" and item[1] == failures[0] for item in self.api.events), 1)

    def test_native_capture_reader_close_unknown_quarantines_original_ancestor_pins(self):
        self._reader_close_failure("stdout.log")

    def test_native_receipt_reader_close_unknown_quarantines_original_ancestor_pins(self):
        self._reader_close_failure("result.json")

    def test_context_entry_cancel_retires_the_real_filesystem_models_native_pins(self):
        owner = self.owner()
        original = KeyboardInterrupt("MODELED_ENTRY_CANCEL_NO_CHILD")
        def cancelled():
            raise original
        owner.check_cancel = cancelled
        with self.assertRaises(KeyboardInterrupt) as caught:
            with owner:
                self.fail("Cancelled entry must not reach its body")
        self.assertIs(caught.exception, original)
        self.assertFalse(self.calls)
        self.assertTrue(owner.closed)
        self.assertTrue(owner.failed)
        self.assertFalse(owner.unknown)
        self.assertEqual(self.api.handles, {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
