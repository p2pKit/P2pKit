#!/usr/bin/env python3
"""Offline same-call init controls; NO actual native/Git/JDK/product execution.

The real parent and canonical initialize() run against tiny ordinary-UID files.
Canonical Git/native identity is modeled; no generated argv runs. Installed JDK
fixtures are nonfunctional tiny files, never executed. All process/network/GPG
suppliers are prohibited or explicitly modeled by the retained fixture builders.
Inherited historical test methods are NOT selected by this file's load_tests.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    import sys
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


P = load("bootstrap_initializer_parent_models", Path(__file__).with_name("hosted-cache-bootstrap-recipient-parent-test.py"))
S, O = P.S, P.O
A = load("bootstrap_canonical_initializer_model", ROOT / "scripts/run-audit-command.py")


class InitModels(P.ParentModels):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(S, "_INITIALIZER_ATTEMPTS", {}))
        self.stack.enter_context(patch.object(S, "_PARENT_CONTROLS", {}))
        self.init_scopes, self.init_events, self.init_errors = [], [], []
        self.before_init = self.after_init = self.init_drain = self.init_close = lambda: None
        self.init_constructed = self.before_init_poll = lambda: None
        self.init_stdout = lambda raw: raw
        self.init_exit = None
        for name in ("JAVA_HOME", "P2PKIT_AUDIT_JDK21"):
            home = self.base / name
            (home / "bin").mkdir(parents=True, mode=0o700)
            for binary in ("java", "javac"):
                target = home / "bin" / binary
                target.write_bytes(b"SYNTHETIC_NONFUNCTIONAL_TOOLCHAIN_FILE_NEVER_EXECUTE\n")
                target.chmod(0o700)
            os.environ[name] = str(home)

    def reset_models(self):
        for row in S._INITIALIZER_ATTEMPTS.values():
            if row[3] is not None:
                for pin in reversed(row[3].seen):
                    if pin.label != "native-scope":
                        pin.resource.close()
        super().reset_models()

    def initializer(self):
        return S._INITIALIZER_ATTEMPTS[id(self.parent())][1]

    def failed_init(self, reason=None, kind=Exception):
        assertion = self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)
        with assertion as caught:
            S.initialize_after_entry(self.current.new)
        self.assertIsNone(self.initializer().result)
        self.assertEqual(self.initializer().state, "FAILED")
        self.assertEqual(self.parent().state, "HANDED_OFF")
        self.unchanged_predecessors(self.current)
        return caught.exception

    def recipient_scope(self, job, invocation, state, home):
        if Path(state) == self.session:
            return super().recipient_scope(job, invocation, state, home)
        case = self
        path = self.session / "initializer"
        self.assertEqual(Path(state), path)
        self.assertEqual(Path(home), path / "control-home")
        self.init_events.append("construct")

        class Scope:
            name = "linux-proc-pidfd"
            baseline = set()

            def __init__(self):
                self.launches, self.closed, self.close_count = [], False, 0

            def _identity(self, pid):
                return {"pid": pid, "startTicks": 9901, "live": True}

            def spawn(self, argv, cwd, env, *, stdout, stderr):
                case.init_events.append("spawn")
                request = O.parse(case.initializer().init_inputs().request_raw)
                case.assertEqual(argv, request["argv"])
                case.assertNotIn("--minimum-ns", argv)
                case.assertEqual(cwd, str(ROOT))
                case.assertNotIn("GITHUB_TOKEN", env)
                case.assertNotIn(O.wire.TOKEN_ENV, env)
                case.assertNotIn("P2PKIT_GRADLE_EXECUTOR", env)
                case.assertEqual(env["JAVA_HOME"], str(case.base / "JAVA_HOME"))
                case.assertEqual(env["P2PKIT_AUDIT_JDK21"], str(case.base / "P2PKIT_AUDIT_JDK21"))
                case.assertFalse((path / "state").exists())
                self.launches = [{"api": "subprocess.Popen", "requestedArgv": argv, "resolvedArgv": argv,
                    "cwd": cwd, "shell": False, "created": True, "executable": argv[0], "pid": 54322,
                    "outputMode": "caller-owned-files"}]
                case.before_init()
                output, code = io.StringIO(), 0
                source = {**O.parse(case.admitted.record)["source"], "status": "", "diffSha256": O.digest(b"")}
                try:
                    with patch.dict(os.environ, env, clear=True), redirect_stdout(output), \
                            patch.object(A, "source_snapshot", return_value=source), \
                            patch.object(A, "host_role", return_value="linux-x64"), \
                            patch.object(A, "git", side_effect=AssertionError("NO_REAL_CANONICAL_GIT")):
                        code = A.initialize(SimpleNamespace(root=str(ROOT), state=str(path / "state"),
                            expected_commit=source["commit"], host="linux-x64"))
                    raw = case.init_stdout(output.getvalue().encode("utf-8"))
                    os.write(stdout.fileno(), raw)
                except BaseException as error:
                    case.init_errors.append(error)
                    os.write(stderr.fileno(), b"SYNTHETIC_CANONICAL_INITIALIZATION_FAILURE\n")
                    code = 125
                case.after_init()

                def poll():
                    case.init_events.append("poll")
                    case.before_init_poll()
                    return code if case.init_exit is None else case.init_exit

                return SimpleNamespace(pid=54322, stdout=None, stderr=None, poll=poll)

            def description(self):
                return {"backend": self.name, "scope": "controlled-marker-inheriting-descendants", "job": job,
                    "invocation": invocation, "launches": self.launches, "startedIdentities":
                    ([{"pid": 54322, "startTicks": 6789, "uid": os.getuid(), "live": False}] if self.launches else []),
                    "discoveryErrors": [], "discoveryReconciliations": []}

            def discover(self):
                return []

            def drain(self, *, grace, kill_wait):
                case.assertTrue(0 <= grace <= 5 and 0 <= kill_wait <= 5)
                case.init_events.append("drain")
                case.init_drain()
                return []

            def close(self):
                self.closed = True
                self.close_count += 1
                case.init_events.append("close")
                case.init_close()

        scope = Scope()
        self.init_scopes.append(scope)
        self.init_constructed()
        return scope

    def test_same_live_parent_initializes_only_after_recipient_closure(self):
        with self.prepared() as call:
            original, reads = S.Owner.read, []
            def read(owner, directory, name, *args, **kwargs):
                if type(owner.fence) is S._InitializerWindow and (name in ("stdout.log", "stderr.log", "context.json", "gradle.properties")):
                    if "initializer" in directory.path.parts:
                        self.assertTrue(self.init_scopes[-1].closed)
                        owner.fence.call.phase_writers_closed()
                        reads.append(name)
                return original(owner, directory, name, *args, **kwargs)
            def before():
                self.closed_parent()
                self.assertIsNot(self.parent().owner, self.initializer().owner)
                self.assertIsNot(self.parent().window, self.initializer().window)
                self.assertEqual(self.parent().window.phase, "READ")
            self.before_init = before
            with patch.object(S.Owner, "read", read):
                result = S.initialize_after_entry(call.new)
            self.assertEqual(self.init_errors, [])
            self.assertEqual(len(self.init_scopes), 1)
            self.assertEqual(self.init_scopes[0].close_count, 1)
            self.assertTrue({"stdout.log", "context.json", "gradle.properties"}.issubset(reads))
            self.assertEqual(call.new_calls.count("finalize"), 3)
            parent = self.initializer()
            self.assertIs(result, parent.result)
            self.assertTrue(parent.owner.closed)
            self.assertTrue(all(row["attempted"] and row["closed"] for row in parent.owner.resources))
            self.assertEqual(parent.window.work - parent.window.first, 120 * O.NS)
            self.assertEqual(parent.window.native_end - parent.window.first, 165 * O.NS)
            self.assertEqual(parent.window.prefix_end - parent.window.first, 195 * O.NS)
            self.assertFalse(O.parse(result.raw)["nextPhaseAuthority"])
            self.assertFalse(O.parse(result.raw)["exportSaveAuthority"])
            self.assertEqual(O.parse(result.raw)["testAcceptance"], "NOT_PERFORMED")
            self.unchanged_predecessors(call)

    def test_recipient_only_has_no_retroactive_initializer_authority(self):
        with self.prepared() as call:
            result = S.run_recipient_after_entry(call.new)
            self.assertEqual(self.init_scopes, [])
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_SECOND_FIRST")):
                with self.assertRaisesRegex(O.OriginError, "RECIPIENT_ALREADY_CLAIMED"):
                    S.initialize_after_entry(call.new)
                with self.assertRaisesRegex(O.OriginError, "NOT_ORIGINAL_HANDOFF"):
                    S._InitializerPredecessor.capture(self.parent(), result.raw, result.checked_ns)
            self.assertEqual(S._INITIALIZER_ATTEMPTS, {})

    def test_initializer_never_observes_or_reopens_old_recipient(self):
        with self.prepared() as call:
            original = S._initialize_claimed
            def enter(parent):
                old = self.parent()
                first = old.window.last
                # Inherited mechanics remain real for the exact initializer;
                # refuse only the old object, not the base method globally.
                real = S._RecipientParentWindow.now
                def now(window, *args, **kwargs):
                    self.assertIsNot(window, old.window)
                    return real(window, *args, **kwargs)
                opened = S.Owner.open
                def open_directory(owner, *args, **kwargs):
                    self.assertIsNot(owner, old.owner)
                    return opened(owner, *args, **kwargs)
                # Guard the receiver through the class, without adding an
                # attribute to the intentionally pinned closed Owner.__dict__.
                with patch.object(S._RecipientParentWindow, "now", now), \
                        patch.object(S.Owner, "open", open_directory):
                    result = original(parent)
                self.assertEqual(old.window.last, first)
                return result
            with patch.object(S, "_initialize_claimed", enter):
                S.initialize_after_entry(call.new)

    def test_init_first_clock_failure_consumes_claim_without_new_owner(self):
        with self.prepared():
            original = S._initialize_claimed
            error = P.FalseyFailure("SYNTHETIC_INITIALIZER_FIRST")
            def enter(parent):
                with patch.object(O.clocks, "observe", side_effect=error):
                    return original(parent)
            with patch.object(S, "_initialize_claimed", enter):
                self.assertIs(self.failed_init(kind=OSError), error)
            self.assertIsNone(self.initializer().owner)
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_RETRY_FIRST")), \
                    self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
                S._initialize_claimed(self.initializer())

    def test_foreign_parent_and_window_subclasses_do_not_select_engine(self):
        with self.prepared():
            class Foreign(S._RecipientParent):
                pass
            for candidate in (Foreign(None, ()), S._InitializerParent(None, ()), SimpleNamespace()):
                with self.assertRaisesRegex(O.OriginError, "NOT_CLAIMED"):
                    S._recipient_parent_registration(candidate)
            self.assertEqual(S._INITIALIZER_ATTEMPTS, {})

    def test_existing_state_refuses_without_replacing_original_bytes(self):
        with self.prepared():
            original = S._InitializerParent.admit
            saved = b"SYNTHETIC_EXISTING_STATE"
            def admit(parent):
                original(parent)
                self.put(self.session / "initializer/state", saved)
            with patch.object(S._InitializerParent, "admit", admit):
                self.failed_init("STATE_ALREADY_EXISTS")
            self.assertEqual((self.session / "initializer/state").read_bytes(), saved)
            self.assertEqual(self.init_scopes, [])

    def test_work120_expires_after_query_return_without_launch_or_new_allowance(self):
        with self.prepared():
            supplier = S.query.NativeGitQueries
            finalize = supplier._finalize
            def finish(value, error):
                finalize(value, error)
                if str(value.directory.path).endswith("/initializer/admission"):
                    self.nanoseconds = self.initializer().window.work
            with patch.object(supplier, "_finalize", finish):
                self.failed_init("PARENT_EXPIRED")
            self.assertEqual(self.init_scopes, [])

    def test_fresh_query_pair_never_spends_native_or_read_reserve(self):
        with self.prepared() as call:
            supplier, pairs = S.query.NativeGitQueries, []
            constructor = supplier.__init__
            def create(value, root, directory, **kwargs):
                if str(directory).endswith("/initializer/admission"):
                    pair = kwargs["owner_deadlines"]
                    self.assertLessEqual(pair[1], self.initializer().window.work_local)
                    pairs.append(pair)
                constructor(value, root, directory, **kwargs)
            with patch.object(supplier, "__init__", create):
                S.initialize_after_entry(call.new)
            self.assertEqual(len(pairs), 1)

    def test_source_request_change_before_launch_refuses(self):
        with self.prepared():
            original = S.canonical.init_request
            def request(**kwargs):
                raw = original(**kwargs)
                if self.init_scopes:
                    return raw + b" "
                return raw
            with patch.object(S.canonical, "init_request", request):
                self.failed_init("REQUEST_CHANGED")
            self.assertNotIn("spawn", self.init_events)

    def test_installed_environment_change_at_scope_return_refuses(self):
        with self.prepared():
            self.init_constructed = lambda: os.environ.__setitem__("JAVA_HOME", str(self.base / "P2PKIT_AUDIT_JDK21"))
            self.failed_init("JDK_CHANGED")
            self.assertNotIn("spawn", self.init_events)

    def test_bad_stdout_is_not_recipient_ack_or_product_receipt(self):
        with self.prepared():
            self.init_stdout = lambda raw: O.encoded({"scope": S.RECIPIENT_ACK_SCOPE})
            self.failed_init("STDOUT_CONTEXT_PATH")
            self.assertTrue(self.init_scopes[0].closed)
            self.assertTrue(self.initializer().unknown)

    def test_context_field_drift_refuses_after_native_and_capture_close(self):
        with self.prepared():
            def change():
                path = self.session / "initializer/state/context.json"
                value = O.parse(path.read_bytes())
                value["source"]["tree"] = "e" * 40
                self.put(path, O.encoded(value))
            self.after_init = change
            self.failed_init("CONTEXT_BINDING")
            self.assertTrue(self.init_scopes[0].closed)

    def test_extra_state_output_is_not_an_empty_initializer_result(self):
        with self.prepared():
            self.after_init = lambda: self.put(self.session / "initializer/state/evidence/invented.json", b"{}")
            self.failed_init("STATE_ROSTER_CHANGED")

    def test_original_recipient_bytes_are_reread_under_new_owner(self):
        with self.prepared():
            self.init_close = lambda: self.put(self.session / "recipient-prefix-pending.json", b"{}")
            self.failed_init("RECIPIENT_ORIGINAL_CHANGED")

    def test_final45_cannot_use_all_native165_after_early_exit(self):
        with self.prepared():
            self.init_drain = lambda: setattr(self, "nanoseconds", self.initializer().window.final)
            self.failed_init("PARENT_EXPIRED")
            self.assertEqual(self.initializer().window.phase, "FINAL")
            self.assertTrue(self.init_scopes[0].closed)

    def test_read30_equality_cannot_retain_successful_pending(self):
        with self.prepared():
            original = S._InitializerParent.initialized_state
            def read(parent, **kwargs):
                result = original(parent, **kwargs)
                self.nanoseconds = parent.window.read_end
                return result
            with patch.object(S._InitializerParent, "initialized_state", read):
                self.failed_init("PARENT_EXPIRED")
            self.assertFalse((self.session / "initializer/initializer-prefix-pending.json").exists())


class PureReadback(unittest.TestCase):
    def test_properties_match_canonical_escaping_without_executing_java(self):
        # Exercise the unchanged canonical formatter with only path checks
        # modeled. Neither code path runs any Java executable.
        homes = ("/synthetic/JDK 17:#é", "/synthetic/JDK21😀")
        with patch.dict(os.environ, dict(zip(("JAVA_HOME", "P2PKIT_AUDIT_JDK21"), homes)), clear=True), \
                patch.object(Path, "resolve", lambda p, **kwargs: p), patch.object(Path, "is_dir", return_value=True), \
                patch.object(Path, "is_file", return_value=True), patch.object(os, "access", return_value=True):
            policy, actual = A.java_policy()
        self.assertEqual(tuple(actual), homes)
        self.assertEqual(S.initialization.properties(homes), policy)
        self.assertIn(b"auto-download=false", policy)
        self.assertIn(b"auto-detect=false", policy)

    def test_empty_or_duplicate_toolchain_lists_are_not_policy_inputs(self):
        for homes in ((), [], ("/jdk", "/jdk"), ("/jdk,other",), (None,)):
            with self.subTest(homes=homes), self.assertRaises(ValueError):
                S.initialization.properties(homes)


class FirstOwnerModels(InitModels):
    """Real once-claim/first owner, intercepted before initialization I/O.

    This does not execute or fake a successful canonical phase. Tiny counter
    resources exercise only the real Owner's close and window machinery.
    """
    def at_first_host(self, operation, reason=None, kind=Exception):
        with self.prepared(), patch.object(S._InitializerParent, "host", operation):
            result = self.failed_init(reason, kind)
        self.assertEqual(self.init_scopes, [])
        return result

    def test_initializer_local_work120_expires_independently_of_raw(self):
        def operation(parent):
            self.assertLess(parent.window.last, parent.window.work)
            with patch.object(S.time, "monotonic", return_value=parent.window.work_local):
                parent.window.now()
        self.at_first_host(operation, "LOCAL_EXPIRED")

    def test_initializer_actual_final_local45_is_not_native165(self):
        def operation(parent):
            parent.window.begin_final()
            self.assertLess(parent.window.final_local, parent.window.native_local)
            with patch.object(S.time, "monotonic", return_value=parent.window.final_local):
                parent.window.now(final=True)
        self.at_first_host(operation, "LOCAL_EXPIRED")

    def test_initializer_local_read30_cannot_use_unused_native_time(self):
        def operation(parent):
            for name in ("native-scope", "stdout", "stderr"):
                resource = SimpleNamespace(close=lambda: None)
                parent.owner.acquire(name, lambda resource=resource: resource)
                parent.owner.close_one(resource)
            parent.native_retired = parent.captures_retired = True
            parent.window.begin_final()
            parent.window.begin_read()
            self.assertLess(parent.window.read_local, parent.window.local_end)
            with patch.object(S.time, "monotonic", return_value=parent.window.read_local):
                parent.window.now()
        self.at_first_host(operation, "LOCAL_EXPIRED")

    def test_returned_resource_survives_falsey_postreturn_clock_failure(self):
        failure, closes = P.FalseyFailure("SYNTHETIC_INIT_POSTRETURN_CLOCK"), []
        def operation(parent):
            resource = SimpleNamespace(close=lambda: closes.append("original"))
            acquire = lambda: resource
            checked = O.clocks.checked_now
            def now(*args, **kwargs):
                if any(row["owner"] is resource for row in parent.owner.resources):
                    raise failure
                return checked(*args, **kwargs)
            with patch.object(O.clocks, "checked_now", now):
                parent.owner.acquire("directory", acquire)
        self.assertIs(self.at_first_host(operation, kind=OSError), failure)
        self.assertEqual(closes, ["original"])
        owner = self.initializer().actual_owner()
        self.assertIs(owner.original, failure)
        self.assertFalse(owner.unknown)
        self.assertTrue(owner.closed)

    def test_direct_published_record_change_cannot_erase_original_cleanup(self):
        failure, closes, saved = P.FalseyFailure("SYNTHETIC_PUBLISHED_RECORD_CHANGE"), [], {}
        def operation(parent):
            owner = parent.owner
            saved.update(owner=owner, control=S._parent_control(parent))
            for index in range(72):
                resource = SimpleNamespace(close=lambda index=index: closes.append(index))
                owner.acquire("directory", lambda resource=resource: resource)
            control = saved["control"]
            record = control.record
            # Mutate the ORIGINAL published dataclass, not just its registry
            # alias. Frozen dataclass syntax does not prevent this operation.
            control.__dict__["record"] = (*record[:3], None, *record[4:])
            with patch.object(O.clocks, "checked_now", side_effect=AssertionError("NO_LIVE_CLOCK")):
                with self.assertRaisesRegex(O.OriginError, "CONTROL_CHANGED"):
                    owner.end(final=True)
            raise failure
        self.assertIs(self.at_first_host(operation, kind=OSError), failure)
        owner = saved["owner"]
        self.assertIs(self.initializer().actual_owner(), owner)
        self.assertIs(owner.original, failure)
        self.assertIsNone(saved["control"].record[3])  # Not written back as rehabilitation.
        self.assertEqual(sorted(closes), list(range(72)))
        self.assertTrue(owner.closed)
        self.assertFalse(owner.unknown)
        self.assertLess(len(owner.errors), 64)
        self.assertTrue(all(row["attempted"] and row["closed"] for row in owner.resources))

    def test_direct_published_handlers_change_cannot_skip_original_restoration(self):
        failure, saved = P.FalseyFailure("SYNTHETIC_PUBLISHED_HANDLERS_CHANGE"), {}
        def operation(parent):
            control = S._parent_control(parent)
            saved.update(control=control, handlers=control.handlers, owner=parent.owner)
            object.__setattr__(control, "handlers", ())
            with self.assertRaisesRegex(O.OriginError, "CONTROL_CHANGED"):
                parent.check()
            raise failure
        self.assertIs(self.at_first_host(operation, kind=OSError), failure)
        self.assertEqual(saved["control"].handlers, ())
        self.assertTrue(saved["owner"].closed)
        self.assertFalse(saved["owner"].unknown)
        self.assertEqual(S._recipient_parent_registration(self.initializer())[3].handler_restored,
                         list(saved["handlers"]))
        for number, handler in saved["handlers"]:
            self.assertEqual(S.signal.getsignal(number), handler)


class InputAndDirectoryModels(unittest.TestCase):
    """Tiny real paths and supplied bytes, not native/source admission."""
    def test_stdout_contract_is_ascii_with_only_native_line_ending(self):
        self.assertEqual(S.initialization.stdout_path("/tmp/state", "linux-x64"), b"/tmp/state/context.json\n")
        self.assertEqual(S.initialization.stdout_path("C:\\state", "windows-x64"), b"C:\\state\\context.json\r\n")
        for role, path in (("linux-x64", "/tmp/é"), ("windows-x64", "C:\\é")):
            with self.subTest(role=role), self.assertRaisesRegex(ValueError, "ASCII_PATH_REQUIRED"):
                S.initialization.stdout_path(path, role)

    def test_shared_ancestor_timestamp_churn_is_not_source_content_drift(self):
        with tempfile.TemporaryDirectory(prefix="bootstrap-init-output-model-") as temporary:
            base = Path(temporary)
            root = base / "checkout"
            for name in ("buildSrc", "library", "samples/iosApp"):
                (root / name).mkdir(parents=True)
            changed = []
            original = Path.lstat
            def lstat(path):
                result = original(path)
                if path == base and not changed:
                    (base / "unrelated-sibling").mkdir()
                    # Filesystems may coalesce rapid directory changes into
                    # one timestamp quantum. Drive and verify this exact pin.
                    os.utime(base, ns=(result.st_atime_ns, result.st_mtime_ns + 1000000000))
                    self.assertNotEqual(original(base).st_mtime_ns, result.st_mtime_ns)
                    changed.append(True)
                return result
            owner = SimpleNamespace(end=lambda: None, error=lambda *a, **k: self.fail("NO_ENUMERATION_ERROR"))
            with patch.object(S, "ROOT", root), patch.object(Path, "lstat", lstat):
                S._initializer_outputs_absent(owner)
            self.assertEqual(changed, [True])

    def test_source_directory_churn_remains_rejected(self):
        with tempfile.TemporaryDirectory(prefix="bootstrap-init-output-model-") as temporary:
            root = Path(temporary)
            for name in ("buildSrc", "library", "samples/iosApp"):
                (root / name).mkdir(parents=True)
            original, changed = Path.lstat, []
            def lstat(path):
                result = original(path)
                if path == root and not changed:
                    (root / "new-source-directory").mkdir()
                    os.utime(root, ns=(result.st_atime_ns, result.st_mtime_ns + 1000000000))
                    self.assertNotEqual(original(root).st_mtime_ns, result.st_mtime_ns)
                    changed.append(True)
                return result
            owner = SimpleNamespace(end=lambda: None, error=lambda *a, **k: self.fail("NO_ENUMERATION_ERROR"))
            with patch.object(S, "ROOT", root), patch.object(Path, "lstat", lstat), \
                    self.assertRaisesRegex(ValueError, "SOURCE_DIRECTORY_CHANGED"):
                S._initializer_outputs_absent(owner)
            self.assertEqual(changed, [True])


def load_tests(_loader, _tests, _pattern):
    return unittest.TestSuite(cls(name) for cls in (InitModels, PureReadback, FirstOwnerModels, InputAndDirectoryModels)
                              for name in sorted(cls.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
