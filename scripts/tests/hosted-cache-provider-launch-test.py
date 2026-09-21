#!/usr/bin/env python3
"""Actual fixed caller methods over modeled native/service suppliers, NOT admission."""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PureWindowsPath
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def fixture(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Fixture suppliers only: none of their earlier test methods is selected/run.
F = fixture("launch_lifecycle_fixtures", "hosted-cache-provider-lifecycle-test.py")
C = fixture("launch_contract_fixtures", "hosted-cache-provider-contract-test.py")
import hosted_cache_provider_launch as L
import hosted_cache_provider_worker as W

P, K, clocks, files = L.processes, L.cache, L.clocks, L.files.windows_files
assert files is F.files


class LaunchSites(unittest.TestCase):
    def setUp(self):
        self.model = F.ProviderLifecycleModels()
        self.model.setUp()
        self.addCleanup(self.model.tearDown)
        self.parents, self.workers, self.extra = [], [], []
        self.root = self.model.root
        self.home = self.root.create_directory("home", deadline=280.0)
        self.extra.append(self.home)
        self.tiny_bundle = b"MODEL_PINNED_BUNDLE_NOT_EXECUTED\n"
        writer = self.root.create_file("provider.cjs", max_bytes=len(self.tiny_bundle), deadline=280.0)
        writer.write(self.tiny_bundle)
        writer.close()
        self.plan_fixture = C.ProviderContract()
        self.plan_fixture.setUp()
        self.addCleanup(self.plan_fixture.doCleanups)
        c = self.plan_fixture.fixture
        c.runner_temp = PureWindowsPath(r"D:\a\_temp")
        c.configure(next(row for row in C.F.I.SELECTIONS if row[2] == "windows-x64"))
        self.patch(K, "Path", PureWindowsPath)
        self.patch(K.files, "Path", PureWindowsPath)
        self.plan = c.plan()
        self.contract_original = K.bootstrap_provider_contract
        self.patch(K, "bootstrap_provider_contract", self.contract)
        self.patch(L, "time", self.model.time)
        self.patch(L, "SCRIPTS", PureWindowsPath(r"C:\source\scripts"))
        self.patch(L.sys, "executable", r"C:\tools\python.exe")
        self.source_reads = self.patch(W, "read_source", Mock(side_effect=lambda _, name: ("# MODEL_SOURCE_" + name).encode()))
        self.patch(clocks, "observe", lambda: clocks.Reading(self.model.clock, self.model.raw))
        self.patch(files, "open_private_directory", lambda path: files._root(str(path), self.model.api, create=False))
        self.outer = self.scope("2" * 32, 92)
        self.inner = self.model.scope
        self.inner.invocation = "4" * 32
        self.inner.spawn = Mock(side_effect=lambda *args, **kw: self.spawn(self.inner, *args, **kw))
        # The cohort fixture intentionally replaces make_scope with an OFFLINE
        # guard. Install this new caller's explicit model AFTER both fixtures;
        # changing the earlier lifecycle Mock would leave that guard in place.
        self.scope_factory = self.patch(P, "make_scope", Mock(side_effect=self.make_scope))
        self.service = {"ACTIONS_RUNTIME_TOKEN": "MODEL_TOKEN_NEVER_REAL", "ACTIONS_RESULTS_URL": "https://model.invalid/",
                        "ACTIONS_CACHE_SERVICE_V2": "True"}
        self.ambient = {"SYSTEMROOT": r"C:\Windows", "NODE_OPTIONS": "MODEL_DO_NOT_INHERIT", "GH_TOKEN": "MODEL_DO_NOT_INHERIT",
                        "PATH": "MODEL_UNTRUSTED_PATH", **self.service}
        for identifier in ("a" * 32, "b" * 32):
            self.ambient = P.ownership_environment(self.ambient, "1" * 32, identifier, str(PureWindowsPath(r"C:\ancestor") / identifier),
                                                   str(self.home.path))
        self.environment_patch = patch.dict(os.environ, self.ambient, clear=True)
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)
        self.provider_code = self.worker_code = 0
        self.fail_outer = self.fail_inner = None
        self.command_bytes = b""

    def patch(self, obj, name, value):
        binding = patch.object(obj, name, value)
        result = binding.start()
        self.addCleanup(binding.stop)
        return result

    def contract(self, plan, phase):
        result = self.contract_original(plan, phase)
        result["bundle"] = {**result["bundle"], "bytes": len(self.tiny_bundle),
                            "sha256": hashlib.sha256(self.tiny_bundle).hexdigest()}
        return result

    def scope(self, invocation, handle):
        scope = object.__new__(P.WindowsScope)
        scope.job, scope.job_id, scope.invocation = handle, "1" * 32, invocation
        scope.api = SimpleNamespace(close=self.model.native_close)
        scope.leaders, scope.launches, scope.known, scope.discovery_errors = [], [], {}, set()
        scope.drain, scope.discover = Mock(return_value=[]), Mock(return_value=[])
        scope.spawn = Mock(side_effect=lambda *args, **kw: self.spawn(scope, *args, **kw))
        return scope

    def make_scope(self, job, invocation, state, home):
        self.assertEqual(home, str(self.home.path))
        if state == str(self.root.path):
            scope = self.outer
        else:
            self.assertEqual(state, str(PureWindowsPath(self.root.path) / "capture"))
            scope = self.inner
        # Model the constructor's actual input binding, including bad inherited
        # contexts which the real ownership_environment must then refuse.
        scope.job_id, scope.invocation = job, invocation
        return scope

    def spawn(self, scope, argv, cwd, env, *, stdout, stderr):
        self.model.events.append(("launch", scope, tuple(argv), cwd, dict(env), stdout, stderr))
        code = self.worker_code if scope is self.outer else self.provider_code
        child = P.WindowsProcess(scope.api, 77 if scope is self.outer else 78, 41 if scope is self.outer else 42, None, None)
        child.poll = Mock(return_value=code)
        scope.leaders.append(child)
        scope.launches.append({"api": "MODEL_ONLY_NO_PROCESS", "created": True, "pid": child.pid})
        scope.known[(child.pid, 7)] = {"pid": child.pid, "creationFileTime": 7, "live": True}
        if scope is self.inner:
            self.model.api.write(stdout.native_handle, b"MODEL_PRIVATE_STDOUT")
            self.model.api.write(stderr.native_handle, b"MODEL_PRIVATE_STDERR")
            if self.command_bytes:
                command = self.model.api.nodes[env["GITHUB_OUTPUT"]]
                handle = self.model.api.shared_open(command, 2, 7)
                try:
                    self.model.api.write(handle, self.command_bytes)
                finally:
                    self.model.api.close(handle)
            failure = self.fail_inner
        else:
            failure = self.fail_outer
        if failure is not None:
            raise failure
        return child

    def parent(self, **changes):
        parent = L.SupervisorLaunch()
        self.parents.append(parent)
        parent.take_directories(self.root, self.home)
        values = dict(issued_ns=100 * clocks.NS, hard_end_ns=280 * clocks.NS, worker_cutoff_ns=250 * clocks.NS,
            phase="save", job="1" * 32, invocation="2" * 32, inner_invocation="4" * 32, plan=self.plan,
            node=r"C:\tools\node.exe", tool_path=r"C:\tools;C:\Windows\System32", cancelled=lambda: None)
        values.update(changes)
        parent.start(clocks.Reading(self.model.clock, self.model.raw), **values)
        return parent

    def worker(self, parent, env=None, frame=None):
        worker = L._CaptureWorker(copy.deepcopy(parent.frame) if frame is None else frame)
        self.workers.append(worker)
        with patch.dict(os.environ, parent.worker_environment if env is None else env, clear=True):
            worker.run()
        return worker

    def tearDown(self):
        # Model disposal only, after assertions. NOT caller retirement or repair
        # of an UNKNOWN production owner. No real native handle/process exists.
        self.model.on_raw = None
        self.model.raw, self.model.local = 100 * clocks.NS, 100.0
        owners = []
        for worker in self.workers:
            if worker.capture is not None:
                owners += [slot.owner for slot in worker.capture._slots.values()]
            owners += [getattr(worker, name, None) for name in ("bundle", "capture_directory", "home", "directory")]
        for parent in self.parents:
            owners += [getattr(parent, name, None) for name in ("bundle", "stdout", "stderr", "capture_directory", "scope")]
            owners += list(getattr(parent, "_owners", {}).values())
        owners += self.extra
        done = set()
        for owner in owners:
            if owner is not None and id(owner) not in done and hasattr(owner, "close"):
                done.add(id(owner))
                try:
                    owner.close()
                except BaseException:
                    pass
        L.QUARANTINE.clear()
        L._WORKERS.clear()

    def test_constructor_and_root_transfer_are_inert(self):
        before = list(self.model.events)
        parent = L.SupervisorLaunch()
        parent.take_directories(self.root, self.home)
        self.assertEqual(before, self.model.events)
        self.scope_factory.assert_not_called()
        self.source_reads.assert_not_called()
        self.assertIs(parent.directory, self.root)
        self.assertFalse(parent.spawn_returned)

    def test_actual_two_spawn_sites_preserve_all_original_domains_and_sinks(self):
        original = dict(os.environ)
        parent = self.parent()
        worker = self.worker(parent)
        rows = [row for row in self.model.events if row[0] == "launch"]
        self.assertEqual(len(rows), 2)
        outer, inner = rows
        self.assertIs(outer[1], self.outer)
        self.assertIs(inner[1], self.inner)
        self.assertIs(outer[5], parent.stdout)
        self.assertIs(outer[6], parent.stderr)
        self.assertIs(inner[5], worker.capture._slots["stdout"].owner)
        self.assertIs(inner[6], worker.capture._slots["stderr"].owner)
        outer_domains = L._markers({n: outer[4][n] for n in L.MARKERS})[0]
        inner_domains = L._markers({n: inner[4][n] for n in L.MARKERS})[0]
        self.assertEqual([row[0] for row in outer_domains], ["a" * 32, "b" * 32, "2" * 32])
        self.assertEqual(inner_domains[:-1], outer_domains)
        self.assertEqual(inner_domains[-1], ("4" * 32, "1" * 32, str(worker.capture_directory.path), str(self.home.path)))
        self.assertEqual(inner[4]["GITHUB_OUTPUT"], str(worker.capture._slots["command"].owner.path))
        self.assertEqual(inner[2], (r"C:\tools\node.exe", r"C:\work\private\provider.cjs"))
        self.assertEqual(dict(os.environ), original)
        self.assertEqual(worker.capture_return.stdout, b"MODEL_PRIVATE_STDOUT")
        self.assertEqual(worker.capture_return.provider_acceptance, "NOT_ESTABLISHED")
        self.outer.drain.assert_not_called()  # Complete supervision is STILL missing.
        self.assertFalse(hasattr(parent, "result"))
        self.assertEqual(parent.scope.job, 92)

    def test_only_native_env_transports_service_values_and_closed_supplier_inputs(self):
        parent = self.parent()
        worker = self.worker(parent)
        for env in (parent.worker_environment, worker.provider_environment):
            for name, value in self.service.items():
                self.assertEqual(env[name], value)
            for name in ("NODE_OPTIONS", "NODE_PATH", "GH_TOKEN", "GITHUB_ENV", "GITHUB_STATE", "LD_PRELOAD"):
                self.assertNotIn(name, env)
        public = repr((parent.frame, parent.worker_argv, parent.source_originals, worker.provider_argv))
        for value in self.service.values():
            self.assertNotIn(value, public)
        self.assertEqual(worker.provider_environment["INPUT_KEY"], self.plan["key"])
        self.assertNotEqual(worker.provider_environment["GRADLE_USER_HOME"], self.plan["restoreHome"])

    def test_lookup_spawn_keeps_exact_lookup_only_inputs_and_original_output(self):
        delimiter = "ghadelimiter_12345678-1234-4234-8234-123456789abc"
        values = (("cache-primary-key", self.plan["key"]), ("cache-matched-key", self.plan["key"]), ("cache-hit", "true"))
        self.command_bytes = "".join(name + "<<" + delimiter + "\r\n" + value + "\r\n" + delimiter + "\r\n"
            for name, value in values).encode("ascii")
        parent = self.parent(phase="lookup")
        worker = self.worker(parent)
        self.assertEqual(worker.capture_return.command, self.command_bytes)
        self.assertEqual(dict(worker.capture_return.outputs), dict(values))
        self.assertEqual(worker.provider_environment["INPUT_LOOKUP-ONLY"], "true")
        self.assertEqual(worker.provider_environment["INPUT_FAIL-ON-CACHE-MISS"], "true")
        self.assertEqual(worker.provider_environment["INPUT_RESTORE-KEYS"], "")
        self.assertEqual(worker.capture_return.provider_acceptance, "NOT_ESTABLISHED")

    def test_json_reencoding_preserves_domain_values_not_encoded_prefix(self):
        real = P.ownership_environment
        def reencode(*args, **kw):
            self.assertNotIn("allow_new_context", kw)
            env = real(*args, **kw)
            env[P.DOMAINS_ENV] = json.dumps(json.loads(env[P.DOMAINS_ENV]), indent=2)
            return env
        with patch.object(P, "ownership_environment", side_effect=reencode):
            self.worker(self.parent())

    def test_empty_genuine_ancestor_chain_is_not_fabricated(self):
        with patch.dict(os.environ, {"SYSTEMROOT": r"C:\Windows", **self.service}, clear=True):
            parent = self.parent()
            self.assertEqual([row[0] for row in parent.frame["prefix"]], ["2" * 32])

    def test_partial_marker_roster_refuses_before_native_acquisition(self):
        for missing in L.MARKERS:
            with self.subTest(missing=missing), patch.dict(os.environ, {k: v for k, v in self.ambient.items() if k != missing}, clear=True):
                with self.assertRaises((L.ProviderLaunchError, P.OwnershipError)):
                    self.parent()
        self.scope_factory.assert_not_called()

    def test_malformed_and_duplicate_domain_fields_refuse(self):
        for encoded in ("{", '[{"id":"a","id":"b"}]', "[]"):
            with self.subTest(encoded=encoded), patch.dict(os.environ, {P.DOMAINS_ENV: encoded}):
                with self.assertRaises((L.ProviderLaunchError, P.OwnershipError)):
                    self.parent()
        self.outer.spawn.assert_not_called()

    def test_wrong_inherited_job_does_not_gain_allow_new_context(self):
        with self.assertRaises(P.OwnershipError):
            self.parent(job="9" * 32)
        self.outer.spawn.assert_not_called()

    def test_wrong_inherited_home_does_not_gain_allow_new_context(self):
        env = P.ownership_environment({}, "1" * 32, "a" * 32, r"C:\ancestor", r"C:\other-home")
        with patch.dict(os.environ, {"SYSTEMROOT": r"C:\Windows", **self.service, **env}, clear=True):
            with self.assertRaises(P.OwnershipError):
                self.parent()
        self.outer.spawn.assert_not_called()

    def test_duplicate_outer_invocation_refuses(self):
        with self.assertRaises(P.OwnershipError):
            self.parent(invocation="a" * 32)
        self.outer.spawn.assert_not_called()

    def test_existing_32_domain_limit_is_not_extended(self):
        env = {"SYSTEMROOT": r"C:\Windows", **self.service}
        for number in range(32):
            env = P.ownership_environment(env, "1" * 32, f"{number + 100:032x}", r"C:\ancestor", str(self.home.path))
        with patch.dict(os.environ, env, clear=True), self.assertRaises(P.OwnershipError):
            self.parent()
        self.outer.spawn.assert_not_called()

    def test_outer_helper_cannot_substitute_valid_inner_only_chain(self):
        real = P.ownership_environment
        def strip(base, *args, **kw):
            return real({k: v for k, v in base.items() if k not in L.MARKERS}, *args, **kw)
        with patch.object(P, "ownership_environment", side_effect=strip), self.assertRaisesRegex(L.ProviderLaunchError, "APPEND_ONLY"):
            self.parent()
        self.outer.spawn.assert_not_called()

    def test_worker_rejects_lost_reordered_or_substituted_prefix_before_service_read(self):
        parent = self.parent()
        domains = json.loads(parent.worker_environment[P.DOMAINS_ENV])
        variants = [domains[1:], [domains[1], domains[0], domains[2]], [{**domains[0], "state": r"C:\wrong"}, *domains[1:]]]
        for rows in variants:
            env = {**parent.worker_environment, P.CHAIN_ENV: ":".join(row["id"] for row in rows), P.DOMAINS_ENV: json.dumps(rows)}
            with self.subTest(variant=rows), patch.object(L, "_service", side_effect=AssertionError("MODEL_NO_SERVICE_BEFORE_PREFIX")):
                with self.assertRaisesRegex(L.ProviderLaunchError, "PREFIX_LOST"):
                    self.worker(parent, env=env)
        self.inner.spawn.assert_not_called()

    def test_inner_helper_cannot_drop_original_outer_owner(self):
        parent = self.parent()
        real = P.ownership_environment
        def strip(base, *args, **kw):
            return real({k: v for k, v in base.items() if k not in L.MARKERS}, *args, **kw)
        with patch.object(P, "ownership_environment", side_effect=strip), self.assertRaisesRegex(L.ProviderLaunchError, "APPEND_ONLY"):
            self.worker(parent)
        self.inner.spawn.assert_not_called()
        self.inner.drain.assert_called_once()

    def test_late_outer_loader_injection_refuses_before_spawn(self):
        def mutate():
            self.parents[-1].worker_environment["NODE_OPTIONS"] = "MODEL_INJECTED_LOADER"
        with self.assertRaises(L.ProviderLaunchError):
            self.parent(cancelled=mutate)
        self.outer.spawn.assert_not_called()

    def test_late_outer_argv_substitution_refuses_before_spawn(self):
        def mutate():
            self.parents[-1].worker_argv[0] = r"C:\unadmitted\python.exe"
        with self.assertRaises(L.ProviderLaunchError):
            self.parent(cancelled=mutate)
        self.outer.spawn.assert_not_called()

    def test_late_outer_sink_replacement_preserves_original_owner_and_refuses(self):
        saved = []
        def mutate():
            parent = self.parents[-1]
            saved.append(parent.stdout)
            parent.stdout = parent.stderr
        with self.assertRaises(L.ProviderLaunchError):
            self.parent(cancelled=mutate)
        self.outer.spawn.assert_not_called()
        self.assertIs(self.parents[-1]._owners["stdout"], saved[0])

    def test_caught_reentry_stays_failed_and_retains_original_scope(self):
        errors = []
        def reenter():
            parent = self.parents[-1]
            try:
                parent.start(None, issued_ns=0, hard_end_ns=0, worker_cutoff_ns=0, phase="save", job="", invocation="",
                    inner_invocation="", plan={}, node="", tool_path="", cancelled=lambda: None)
            except BaseException as error:
                errors.append(error)
        error = F.caught(lambda: self.parent(cancelled=reenter))
        self.assertIs(error, errors[0])
        self.assertIs(self.parents[-1].scope, self.outer)
        self.outer.spawn.assert_not_called()

    def test_original_source_change_during_final_readback_refuses(self):
        calls = {}
        def read(_, name):
            calls[name] = calls.get(name, 0) + 1
            return (name + str(calls[name])).encode()
        self.source_reads.side_effect = read
        with self.assertRaisesRegex(L.ProviderLaunchError, "SOURCE_CHANGED"):
            self.parent()
        self.outer.spawn.assert_not_called()

    def test_outer_spawn_failure_keeps_original_domain_even_without_child_return(self):
        self.fail_outer = F.FalseyCancellation("MODEL_PARTIAL_OUTER_LAUNCH")
        self.assertIs(F.caught(self.parent), self.fail_outer)
        parent = self.parents[-1]
        self.assertIs(parent.scope, self.outer)
        self.assertIsNone(parent.child)
        self.assertFalse(parent.spawn_returned)
        self.assertEqual(len(self.outer.leaders), 1)
        self.assertIn(parent, L.QUARANTINE)
        self.assertEqual(parent.scope.job, 92)
        self.outer.drain.assert_not_called()

    def test_post_return_failure_cannot_lose_original_worker_object(self):
        error = F.FalseyCancellation("MODEL_POST_RETURN_CLOCK")
        spawn = self.outer.spawn.side_effect
        def returned(*args, **kw):
            child = spawn(*args, **kw)
            self.model.on_raw = lambda: (_ for _ in ()).throw(error)
            return child
        self.outer.spawn.side_effect = returned
        self.assertIs(F.caught(self.parent), error)
        parent = self.parents[-1]
        self.assertIs(parent.child, self.outer.leaders[0])
        self.assertTrue(parent.spawn_returned)

    def test_late_inner_loader_injection_refuses_before_provider_spawn(self):
        parent = self.parent()
        def mutate():
            if self.workers and self.workers[-1].provider_environment is not None:
                self.workers[-1].provider_environment["NODE_OPTIONS"] = "MODEL_INJECTED_LOADER"
        self.model.on_raw = mutate
        with self.assertRaises(L.ProviderLaunchError):
            self.worker(parent)
        self.inner.spawn.assert_not_called()

    def test_late_inner_output_routing_change_refuses_before_provider_spawn(self):
        parent = self.parent()
        def mutate():
            if self.workers and self.workers[-1].provider_environment is not None:
                self.workers[-1].provider_environment["GITHUB_OUTPUT"] = r"C:\wrong-output"
        self.model.on_raw = mutate
        with self.assertRaises(L.ProviderLaunchError):
            self.worker(parent)
        self.inner.spawn.assert_not_called()

    def test_inner_partial_spawn_failure_retains_original_capture_and_outer_job(self):
        parent = self.parent()
        self.fail_inner = F.FalseyFailure("MODEL_INNER_FAILED_NATIVE_RETURN")
        self.assertIs(F.caught(lambda: self.worker(parent)), self.fail_inner)
        worker = self.workers[-1]
        self.assertIsNone(worker.child)
        self.assertIs(worker.capture._slots["scope"].owner, self.inner)
        self.inner.drain.assert_called_once()
        self.assertEqual(parent.scope.job, 92)
        self.assertIsNone(worker.capture_return)

    def test_nonzero_provider_keeps_original_failed_capture_without_success(self):
        parent = self.parent()
        self.provider_code = 9
        with self.assertRaises(L.lifecycle.ProviderLifecycleError):
            self.worker(parent)
        worker = self.workers[-1]
        self.assertEqual(worker.capture.failure_capture.exit_code, 9)
        self.assertEqual(worker.capture.failure_capture.stdout, b"MODEL_PRIVATE_STDOUT")
        self.assertIsNone(worker.capture_return)
        self.assertEqual(worker.closed, [])
        self.assertIn(worker, L.QUARANTINE)

    def test_worker_uses_shorter_local_cutoff_not_a_fresh180_or_second45(self):
        parent = self.parent()
        worker = self.worker(parent)
        self.assertEqual(parent.frame["hardEndNs"], str(280 * clocks.NS))
        self.assertEqual(worker.capture._raw_end, 280 * clocks.NS)
        self.assertLess(worker.window.local_end, 250.0)
        self.assertLessEqual(worker.capture._local_end, worker.window.local_end)
        self.assertEqual(worker.capture._work_local_end, worker.capture._local_end - 45)
        self.assertLess(self.inner.drain.call_args.kwargs["deadline"], 250.0)

    def test_expired_worker_cannot_renew_original_window(self):
        parent = self.parent()
        self.model.raw = 251 * clocks.NS
        with self.assertRaisesRegex(L.ProviderLaunchError, "RAW_EXPIRED"):
            self.worker(parent)
        self.inner.spawn.assert_not_called()

    def test_wire_keeps_raw_values_above_javascript_safe_integer_exact(self):
        issued = (1 << 53) + 139
        self.model.raw = issued
        parent = self.parent(issued_ns=issued, hard_end_ns=issued + 180 * clocks.NS,
                             worker_cutoff_ns=issued + 150 * clocks.NS)
        wire = json.loads(parent.worker_argv[-1])
        self.assertEqual(wire["issuedNs"], str(issued))
        self.assertIs(type(wire["hardEndNs"]), str)
        self.assertEqual(L._ns(wire["workerCutoffNs"]), issued + 150 * clocks.NS)

    def test_frame_rejects_float_boolean_renewed_and_noncanonical_raw_inputs(self):
        parent = self.parent()
        for name, value in (("issuedNs", 100.0), ("hardEndNs", True), ("issuedNs", "0100"),
                            ("workerCutoffNs", str(280 * clocks.NS)), ("hardEndNs", str(281 * clocks.NS))):
            frame = copy.deepcopy(parent.frame)
            frame[name] = value
            with self.subTest(name=name, value=value), self.assertRaises(L.ProviderLaunchError):
                self.worker(parent, frame=frame)
        self.inner.spawn.assert_not_called()


class FixedSourceBootstrap(unittest.TestCase):
    def cold_roster(self, role):
        # Execute only the fixed original module bodies, then stop at the invalid
        # frame BEFORE clock/native acquisition. The unlisted sibling is poison,
        # not a supplier: no credential, provider or real key is used by this test.
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            bindings = {}
            for name in W.names(role):
                raw = (SCRIPTS / (name + ".py")).read_bytes()
                (root / (name + ".py")).write_bytes(raw)
                bindings[name] = hashlib.sha256(raw).hexdigest()
            (root / "uuid.py").write_text("raise AssertionError('MODEL_UNHASHED_SIBLING_IMPORTED')\n")
            argv = [str(root / "hosted_cache_provider_worker.py"), json.dumps(bindings), json.dumps({"role": role})]
            original_path, path_values = sys.path, tuple(sys.path)
            with patch.dict(sys.modules), patch.object(W, "__file__", argv[0]), patch.object(sys, "argv", argv), \
                    patch.object(sys, "path", list(path_values)):
                isolated_path = sys.path
                for name in (*W.NAMES, "uuid"):
                    sys.modules.pop(name, None)
                with self.assertRaisesRegex(RuntimeError, "^PROVIDER_LAUNCH_FRAME$"):
                    W.bootstrap()
                self.assertIs(sys.path, isolated_path)
                self.assertEqual(tuple(sys.path), path_values)
                for name in W.names(role):
                    self.assertEqual(Path(sys.modules[name].__file__).parent, root)
                self.assertNotEqual(Path(sys.modules["uuid"].__file__).parent, root)
            self.assertIs(sys.path, original_path)
            self.assertEqual(tuple(sys.path), path_values)

    def test_cold_linux_fixed_roster_cannot_import_unlisted_sibling(self):
        self.cold_roster("linux-x64")

    def test_cold_darwin_roster_cannot_widen_import_path(self):
        self.cold_roster("macos-arm64")  # Role-dependent source loading, NOT Darwin execution.

    def test_cold_windows_roster_excludes_unix_helper_without_path_widening(self):
        self.cold_roster("windows-x64")  # Import topology only, NOT Windows execution.

    def test_shared_suppliers_keep_direct_script_path_setup_only(self):
        for name in ("hosted_evidence", "hosted_lock_resources"):
            tree = ast.parse((SCRIPTS / (name + ".py")).read_bytes())
            prefix = []
            for node in tree.body:
                if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
                    break
                prefix.append(node)
            code = compile(ast.Module(body=prefix, type_ignores=[]), name, "exec")
            for entry in ("__main__", "loaded_supplier"):
                with self.subTest(name=name, entry=entry), patch.object(sys, "path", list(sys.path)):
                    before = tuple(sys.path)
                    exec(code, {"__file__": str(SCRIPTS / (name + ".py")), "__name__": entry})
                    self.assertEqual(tuple(sys.path), (str(SCRIPTS), *before) if entry == "__main__" else before)

    def test_direct_spec_fixtures_own_their_path_without_running_fixture_methods(self):
        for filename, supplier in (("encrypt-hosted-evidence-test.py", "H"), ("hosted-lock-resources-test.py", "R")):
            # Import definitions only: no TestCase, setUpClass, key generation,
            # crypto call or resource-observer execution is selected here.
            with self.subTest(filename=filename), patch.dict(sys.modules), \
                    patch.object(sys, "path", [part for part in sys.path if part != str(SCRIPTS)]):
                sys.modules.pop("audit_processes", None)
                sys.modules.pop("hosted_evidence", None)
                module = fixture("direct_spec_definitions_only", filename)
                loaded = getattr(module, supplier).audit_processes
                self.assertEqual(Path(loaded.__file__), SCRIPTS / "audit_processes.py")
                self.assertEqual(sys.path[0], str(SCRIPTS))

    def test_fixed_roster_covers_project_imports_without_controller_or_canonical_launcher(self):
        roster = set(W.NAMES)
        self.assertNotIn("run-hosted-initial-recipient", roster)
        self.assertNotIn("hosted_canonical_python", roster)
        self.assertNotIn("hosted_lock_resources", W.names("windows-x64"))
        self.assertIn("hosted_lock_resources", W.names("macos-arm64"))
        for name in roster:
            tree = ast.parse((SCRIPTS / (name + ".py")).read_bytes())
            for node in ast.walk(tree):
                imports = [alias.name for alias in node.names] if isinstance(node, ast.Import) else (
                    [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
                for imported in imports:
                    if (SCRIPTS / (imported + ".py")).is_file():
                        self.assertIn(imported, roster)

    def test_actual_tiny_source_read_and_changed_size_refusal(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            source = root / "audit_processes.py"
            source.write_bytes(b"# MODEL_SOURCE_NOT_EXECUTED\n")
            self.assertEqual(W.read_source(root, "audit_processes"), source.read_bytes())
            source.write_bytes(b"x" * (W.SOURCE_LIMIT + 1))
            with self.assertRaisesRegex(RuntimeError, "SOURCE_REFUSED"):
                W.read_source(root, "audit_processes")

    def test_source_symlink_hardlink_and_unknown_module_refuse(self):
        with tempfile.TemporaryDirectory() as path:
            root = Path(path)
            target = root / "target.py"
            target.write_bytes(b"# MODEL_SOURCE\n")
            source = root / "audit_processes.py"
            source.symlink_to(target)
            with self.assertRaises(RuntimeError):
                W.read_source(root, "audit_processes")
            source.unlink()
            os.link(target, source)
            with self.assertRaises(RuntimeError):
                W.read_source(root, "audit_processes")
            with self.assertRaises(RuntimeError):
                W.read_source(root, "unselected_module")

    def test_duplicate_fields_and_extra_source_roster_refuse_before_execution(self):
        with self.assertRaises(RuntimeError):
            W.record('{"role":"linux-x64","role":"windows-x64"}')
        with patch.object(sys, "argv", ["fixed.py", '{"extra":"' + "a" * 64 + '"}', '{"role":"linux-x64"}']), \
                patch.object(W, "read_source", side_effect=AssertionError("MODEL_NO_SOURCE_READ")), self.assertRaises(RuntimeError):
            W.bootstrap()

    def test_wrong_original_source_digest_refuses_before_any_project_execution(self):
        binding = {name: "a" * 64 for name in W.names("linux-x64")}
        with patch.object(sys, "argv", ["fixed.py", json.dumps(binding), '{"role":"linux-x64"}']), \
                patch.object(W, "read_source", return_value=b"raise AssertionError('MODEL_MUST_NOT_EXECUTE')"), \
                self.assertRaisesRegex(RuntimeError, "SOURCE_REFUSED"):
            W.bootstrap()


if __name__ == "__main__":
    unittest.main()
