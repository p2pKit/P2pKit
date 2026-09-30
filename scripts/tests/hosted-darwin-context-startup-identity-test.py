#!/usr/bin/env python3
"""Two offline direct-child startup-image controls, not native custody proof.

Only the current helper/service/identity/token functions execute, with bounded
memory endpoints. Import READY -> STARTUP -> current runtime/inverse exactly
once and retain STARTUP's no-process/network/write/native audit fence. Prior
source is inert text/AST DATA, never an alternate imported or executed runtime.
The separately frozen minimum packet selects these two and three affected old
methods; importing their modules does not run any historical test suite.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-startup-identity-test.py
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
READY_PATH = ROOT / "scripts/tests/hosted-darwin-ready-producer-diagnostic-test.py"
READY_SHA256 = "42fbfc5210316ee554ba3a5dbd6ad69bc78f0c2fd48a9146c1650bc92984d752"
PREIMAGE = "65fac8adb5041deeb4e1eb5425dd43dcb88a28302d3d5ed75881e670305368b7"
INVERSE_PREIMAGE = "16b66f373915449ce6784b37b75dcf4ba9a2d43d2471166620615df95bf4d5f6"
CURRENT_RUNTIME_SHA256 = "e7ee6a443987146c4019648c9c75ab32bb3300be16b8035fcba4321b0501add5"
METHODS = (
    "test_01_original_child_image_binding_and_strict_cleanup",
    "test_02_exact_inverse_and_unchanged_ownership_guards",
)
CONTINUITY = ("pid", "parentPid", "uniqueId", "parentUniqueId", "startSeconds", "startMicroseconds",
              "uid", "realUid", "gid", "realGid")
ABSENT = object()

if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_STARTUP_IDENTITY_INVOCATION_REQUIRED")
if hashlib.sha256(READY_PATH.read_bytes()).hexdigest() != READY_SHA256:
    raise SystemExit("EXACT_ADAPTED_READY_HELPER_REQUIRED")
spec = importlib.util.spec_from_file_location("darwin_context_ready_suite_for_startup_identity", READY_PATH)
READY = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = READY
spec.loader.exec_module(READY)
STARTUP, M, CLOCK = READY.STARTUP, READY.M, READY.CLOCK
NATIVE = M.Darwin  # Keep the real class; never instantiate or load native code.


class StartupIdentity(unittest.TestCase):
    # Reuse bounded endpoints only, not inheritance or any old test invocation.
    _service = STARTUP.StartupDiagnostic._service
    _no_io = READY.ReadyProducerDiagnostic._no_io

    def _observe(self, birth, observed, *, parent=None, expected_account=None, pid=303, returncode=None,
                 queries=1, succeeds=False, native_error=None, reason="IDENTITY_CHANGED"):
        parent = STARTUP.identity(202, 1) if parent is None else parent
        expected_account = STARTUP.account() if expected_account is None else expected_account
        original = copy.deepcopy((birth, observed, parent, expected_account))
        forbidden = lambda: Mock(side_effect=AssertionError("NO_STARTUP_HELPER_PROCESS_OPERATION"))
        process = types.SimpleNamespace(pid=pid, returncode=returncode, poll=forbidden(), wait=forbidden(),
                                        communicate=forbidden(), terminate=forbidden(), kill=forbidden(), send_signal=forbidden())
        query = Mock(return_value=observed, side_effect=native_error)
        native = types.SimpleNamespace(identity=query)
        with self._no_io(), patch.object(M.os, "getpid", return_value=202), \
                patch.object(M, "same_identity", wraps=M.same_identity) as same, \
                patch.object(M, "identity_account", wraps=M.identity_account) as account:
            if succeeds:
                result = M.observe_startup_child(native, process, birth, parent, expected_account)
                self.assertIs(result, observed, "RETAIN_THE_ACTUAL_NATIVE_RETURN_WITHOUT_COPY_OR_REWRITE")
                self.assertEqual(same.call_count, 2)
                for call, held in zip(same.call_args_list, (birth, observed)):
                    self.assertIs(call.args[0], held)
                    self.assertIs(call.args[1], held)
                self.assertEqual(account.call_count, 2)
                for call, held in zip(account.call_args_list, (birth, observed)):
                    self.assertIs(call.args[0], held)
                    self.assertIs(call.args[1], expected_account)
            else:
                with self.assertRaises(M.ExperimentError) as raised:
                    M.observe_startup_child(native, process, birth, parent, expected_account)
                if native_error is not None:
                    self.assertIs(raised.exception, native_error)
                else:
                    self.assertEqual((raised.exception.stage, raised.exception.reason, raised.exception.errno_name),
                                     ("IDENTITY", reason, "NONE"))
        self.assertEqual(query.call_count, queries)
        if queries:
            query.assert_called_once_with(303)
            self.assertIs(type(query.call_args.args[0]), int)
        self.assertEqual((birth, observed, parent, expected_account), original, "NEITHER_NATIVE_OPERAND_MAY_BE_MUTATED")
        self.assertEqual((process.pid, process.returncode), (pid, returncode))
        for name in ("poll", "wait", "communicate", "terminate", "kill", "send_signal"):
            getattr(process, name).assert_not_called()

    def _ready_packet(self, state):
        raw = STARTUP.canonical(state.fixture.ready)
        self.assertEqual(state.probe_channel.packets[0][0], 3)
        state.probe_channel.packets[0] = (3, struct.pack("!I", len(raw)) + raw)

    @contextlib.contextmanager
    def _image_service(self, birth_version=12, image_version=77, *, reported_version=ABSENT, fail=None):
        """Actual D/frames/helper/READY/same/token/signal, memory native endpoints.

        Binding queries are recorded separately from the existing full-image
        rechecks inside same/token. Token reads never grant a new bound image.
        No real Popen, file, socket, syscall, ctypes loader or signal is used.
        """
        observe, read_frame, validate_ready = M.observe_startup_child, M.read_frame, M.validate_ready
        with self._service(fail, normal=True) as state:
            state.birth = dict(state.fixture.producer, pidVersion=birth_version)
            state.image = dict(state.birth, pidVersion=image_version, status=3)
            state.live, state.mode, state.now = state.image, "service", M.NS
            state.bound, state.primary = None, None
            state.birth_error, state.image_error = None, None
            state.expire_in_query = False
            state.binding_calls, state.ready_calls, state.identity_pids = [], [], []
            state.queries = {key: [] for key in ("birth", "binding", "recheck", "token")}
            state.recheck_images, state.rechecks, state.read_returns = [state.image, state.image], [], {}
            state.signal_attempts, state.token_attempts, state.cleanup_errors = [], [], []
            state.token_images, state.task_name_code, state.signal_code = None, 0, 0
            state.opaque_tokens, state.signal_returns, state.port_releases = [], [], []
            state.fixture.ready["payload"]["producer"] = copy.deepcopy(state.image)
            if reported_version is not ABSENT:
                state.fixture.ready["payload"]["producer"]["pidVersion"] = reported_version
            self._ready_packet(state)

            def identity(pid):
                state.identity_pids.append(pid)
                self.assertIs(type(pid), int)
                self.assertLessEqual(len(state.identity_pids), 8, "BOUNDED_NATIVE_MEMORY_OBSERVATIONS")
                if pid == 202:
                    self.assertEqual(state.mode, "service")
                    return state.fixture.service
                if pid == 101:
                    self.assertEqual(state.mode, "foreground")
                    return state.fixture.foreground
                self.assertEqual(pid, 303, "NO_READY_SELECTED_OR_REPLACEMENT_PID_QUERY")
                if state.mode == "service":
                    state.queries["birth"].append(pid)
                    state.order.append("native-birth")
                    self.assertEqual(len(state.queries["birth"]), 1, "NO_UNCLASSIFIED_REFRESH_QUERY")
                    if state.birth_error is not None:
                        state.primary = state.birth_error
                        raise state.birth_error
                    return state.birth
                if state.mode == "binding":
                    state.queries["binding"].append(pid)
                    state.order.append("native-image")
                    self.assertEqual(len(state.queries["binding"]), 1, "ONE_BINDING_OBSERVATION_ONLY")
                    if state.image_error is not None:
                        raise state.image_error
                    if state.expire_in_query:
                        state.now = state.fixture.prepared["caseEndNs"]
                    return state.image
                if state.mode == "recheck":
                    state.queries["recheck"].append(pid)
                    self.assertLessEqual(len(state.queries["recheck"]), 2)
                    return state.live
                self.assertEqual(state.mode, "token", "NO_CLEANUP_CONTINUITY_QUERY_OR_REBINDING")
                index = len(state.queries["token"])
                state.queries["token"].append(pid)
                state.order.append("token-recheck")
                self.assertLess(index, 2)
                if state.token_images is not None:
                    self.assertLess(index, len(state.token_images))
                    return state.token_images[index]
                return state.live

            def same(expected):
                if state.mode == "token":
                    return NATIVE.same(state.native, expected)
                previous = state.mode
                try:
                    if expected is state.fixture.foreground:
                        state.mode = "foreground"
                    else:
                        state.rechecks.append(expected)
                        self.assertIs(expected, state.image, "LATER_CHECKS_RETAIN_THE_FULL_BOUND_IMAGE")
                        self.assertLessEqual(len(state.rechecks), 2)
                        state.live = state.recheck_images[len(state.rechecks) - 1]
                        state.mode = "recheck"
                        state.order.append("image-recheck" + str(len(state.rechecks)))
                    return NATIVE.same(state.native, expected)
                except BaseException as error:
                    state.primary = error
                    raise
                finally:
                    state.mode = previous

            def bind(native, process, birth, parent, expected_account):
                state.binding_calls.append((native, process, birth, parent, expected_account))
                state.order.append("bind-enter")
                self.assertEqual(len(state.binding_calls), 1)
                self.assertFalse(state.snapshots, "NO_HELPER_ENTRY_FROM_EXCEPTIONAL_CLEANUP")
                self.assertIs(native, state.native)
                self.assertIs(process, state.process)
                self.assertIs(birth, state.birth)
                self.assertIs(parent, state.fixture.service)
                self.assertEqual(expected_account, state.fixture.prepared["account"])
                self.assertIn(3, state.read_returns, "COMPLETE_F3_MUST_RETURN_BEFORE_BINDING")
                self.assertEqual(state.probe_channel.pending, b"")
                self.assertNotIn("cleanup-poll", state.order)
                self.assertEqual(state.signal_attempts, [])
                previous, state.mode = state.mode, "binding"
                try:
                    state.bound = observe(native, process, birth, parent, expected_account)
                    self.assertIs(state.bound, state.image)
                    state.order.append("image-bound")
                    return state.bound
                except BaseException as error:
                    state.primary = error
                    raise
                finally:
                    state.mode = previous

            def read(channel, serial, binding, trace, end_ns, pump=None):
                self.assertEqual(end_ns, state.fixture.prepared["caseEndNs"])
                try:
                    value = read_frame(channel, serial, binding, trace, end_ns, pump)
                except BaseException as error:
                    state.primary = error
                    raise
                state.read_returns[serial] = value
                state.order.append("complete" + str(serial))
                if serial == 3:
                    self.assertEqual([row["serial"] for row in trace], [1, 2, 3])
                return value

            def ready(frame, prepared, parent, observed):
                state.ready_calls.append((frame, prepared, parent, observed))
                state.order.append("ready-validate")
                self.assertIs(frame, state.read_returns[3])
                self.assertIs(observed, state.image)
                self.assertIsNot(frame["payload"]["producer"], observed)
                try:
                    result = validate_ready(frame, prepared, parent, observed)
                except BaseException as error:
                    state.primary = error
                    raise
                state.order.append("ready-accepted")
                return result

            def make_token():
                token = (M.ctypes.c_uint32 * 8)(*range(8))
                state.opaque_tokens.append(token)
                return token

            def task_name(self_port, pid, port):
                self.assertEqual((self_port, pid), (17, 303))
                state.order.append("token-name")
                if state.task_name_code == 0:
                    port._obj.value = 19
                return state.task_name_code

            def task_info(port, flavor, token, count):
                self.assertEqual((port.value, flavor, count._obj.value), (19, 15, 8))
                self.assertIs(token._obj, state.opaque_tokens[-1])
                state.order.append("token-acquired")
                return 0

            def deallocate(self_port, port):
                state.port_releases.append((self_port, port.value))
                self.assertEqual(state.port_releases[-1], (17, 19))
                return 0

            def token(expected):
                state.token_attempts.append(expected)
                previous, state.mode = state.mode, "token"
                try:
                    return NATIVE.token(state.native, expected)
                finally:
                    state.mode = previous

            def signal_return(token, signum):
                state.signal_returns.append((token._obj, signum))
                self.assertIs(token._obj, state.opaque_tokens[-1], "ONLY_THE_ORIGINAL_OPAQUE_TOKEN_IS_SIGNALED")
                return state.signal_code

            def signal_child(expected, signum, end_ns):
                state.signal_attempts.append((expected, signum, end_ns))
                state.order.append("cleanup-signal")
                try:
                    return NATIVE.signal(state.native, expected, signum, end_ns)
                except BaseException as error:
                    state.cleanup_errors.append(error)
                    raise

            poll = state.process.poll

            def process_poll():
                poll()
                return state.process.returncode

            state.process.poll = process_poll
            for name in ("wait", "communicate", "terminate", "kill", "send_signal"):
                setattr(state.process, name, Mock(side_effect=AssertionError("NO_EARLY_OR_PID_ONLY_PROCESS_OPERATION")))
            state.native.identity, state.native.same = identity, same
            state.native.token, state.native.signal, state.native.self_port = token, signal_child, 17
            state.native.abi = types.SimpleNamespace(U32=M.ctypes.c_uint32, AuditToken=make_token)
            state.native.system = types.SimpleNamespace(task_name_for_pid=task_name, task_info=task_info,
                                                        mach_port_deallocate=deallocate)
            state.native.proc = types.SimpleNamespace(proc_signal_with_audittoken=signal_return)
            with patch.object(M, "observe_startup_child", side_effect=bind), \
                    patch.object(M, "read_frame", side_effect=read), \
                    patch.object(M, "validate_ready", side_effect=ready), \
                    patch.object(M, "shared_raw_ns", side_effect=lambda: state.now):
                yield state

    def _service_refusal(self, state, *, site, bindings, queries, ready, cleanup=ABSENT, forwarded=False):
        held = copy.deepcopy((state.birth, state.image, state.fixture.ready))
        with self.assertRaises(M.ExperimentError) as raised:
            M.service(STARTUP.EVIDENCE / "N2")
        error = raised.exception
        if state.primary is not None:
            self.assertIs(error, state.primary, "THE_ORIGINAL_FAILURE_WINS_OVER_CLEANUP")
        self.assertEqual((state.birth, state.image, state.fixture.ready), held)
        self.assertEqual(len(state.binding_calls), bindings)
        self.assertEqual(len(state.queries["binding"]), queries)
        self.assertEqual(len(state.ready_calls), ready)
        self.assertEqual(state.queries["birth"], [303])
        self.assertEqual([row["serial"] for row in state.channel.sent], [1, 4] if forwarded else [1])
        self.assertEqual(state.probe_channel.sent, [], "NO_F6_START_AFTER_REFUSAL")
        self.assertNotIn(8, [row["serial"] for row in state.channel.sent])
        if site is None:
            self.assertEqual(state.snapshots, [])
            self.assertEqual(len(state.written), 1)
        else:
            self.assertEqual(len(state.snapshots), 1)
            self.assertIs(state.snapshots[0][0], error)
            self.assertEqual(state.snapshots[0][1:4], ("N2", STARTUP.BINDING, site))
            self.assertLess(state.order.index("snapshot"), state.order.index("cleanup-poll"))
            self.assertEqual(len(state.written), 2)
        self.assertEqual(state.written[0], (M.public_error(error) + "\n").encode("ascii"))
        self.assertEqual(state.order.count("cleanup-poll"), 1)
        for cleanup_error in state.cleanup_errors:
            self.assertIs(type(cleanup_error), M.ExperimentError, "A_MODEL_ASSERTION_IS_NOT_A_NATIVE_GUARD_REFUSAL")
        if cleanup is ABSENT:
            self.assertEqual(state.signal_attempts, [])
            self.assertEqual(state.token_attempts, [])
        else:
            self.assertEqual(len(state.signal_attempts), 1)
            actual, signum, end = state.signal_attempts[0]
            self.assertIs(actual, cleanup, "STRICT_HELD_IMAGE_ONLY_NOT_A_RESCUED_OR_REPORTED_IDENTITY")
            self.assertEqual((signum, end), (M.signal.SIGTERM, state.fixture.prepared["caseEndNs"]))
            for expected in state.token_attempts:
                self.assertIs(expected, cleanup)
            self.assertLessEqual(len(state.token_attempts), 1)
        if state.pipes is not None:
            self.assertTrue(state.pipes.closed)
            self.assertEqual(state.order.count("finish"), 1)
            if site is not None:
                self.assertLess(state.order.index("snapshot"), state.order.index("finish"))
        self.assertTrue(state.native.closed and state.captures.closed)
        self.assertEqual((state.channel.fileno(), state.probe_channel.fileno(), state.child_channel.fileno()), (-1, -1, -1))
        for name in ("wait", "communicate", "terminate", "kill", "send_signal"):
            getattr(state.process, name).assert_not_called()
        return error

    def test_01_original_child_image_binding_and_strict_cleanup(self):
        self.assertEqual(M.IDENTITY_KEYS - {"status", "pidVersion"}, frozenset(CONTINUITY))
        self.assertEqual(len(CONTINUITY), 10)
        birth = STARTUP.identity(303, 202)

        # No numerical delta, direction, +1, or exec-count rule is invented.
        for old, new in ((1, 1), (5, 83), (700, 9), ((1 << 32) - 1, 0), (0, (1 << 32) - 2)):
            with self.subTest(image_versions=(old, new)):
                self._observe(dict(birth, pidVersion=old), dict(birth, pidVersion=new), succeeds=True)
        for old in (1, 2, 3, 4):
            for new in (1, 2, 3, 4):
                with self.subTest(live_statuses=(old, new)):
                    self._observe(dict(birth, status=old), dict(birth, status=new, pidVersion=91), succeeds=True)
        for key in CONTINUITY:
            with self.subTest(continuity_field=key):
                observed = dict(birth, pidVersion=77)
                observed[key] += 1
                self._observe(copy.deepcopy(birth), observed)

        def invalid_identities():
            for index, value in enumerate((None, True, 1, [], "NOT_AN_IDENTITY", STARTUP.DictSubclass(birth))):
                yield "type" + str(index), value
            yield "extra_key", dict(birth, extra=0)
            for key in sorted(M.IDENTITY_KEYS):
                value = dict(birth)
                del value[key]
                yield "missing_" + key, value
                for index, bad in enumerate((True, -1, 1.5, "1", STARTUP.IntegerSubclass(1))):
                    value = dict(birth)
                    value[key] = bad
                    yield key + "_value" + str(index), value
            for key in ("pid", "uniqueId"):
                value = dict(birth)
                value[key] = 0
                yield key + "_zero", value
            for status in (0, 5, 99):
                yield "status" + str(status), dict(birth, status=status)

        # The existing exact schema, int/nonnegative/positive-id and allowed
        # status guards run independently on BOTH untouched observations.
        for operand in ("birth", "observed"):
            for label, bad in invalid_identities():
                with self.subTest(malformed_operand=operand, predicate=label):
                    self._observe(bad if operand == "birth" else dict(birth),
                                  bad if operand == "observed" else dict(birth),
                                  queries=0 if operand == "birth" else 1)
        for key in ("parentPid", "parentUniqueId", "uid", "realUid", "gid", "realGid"):
            changed = dict(birth)
            changed[key] += 1
            with self.subTest(original_birth_guard=key):
                self._observe(changed, copy.deepcopy(changed), queries=0)
        for pid in (304, 0, -1, True, "303", None, STARTUP.IntegerSubclass(303)):
            with self.subTest(retained_pid_type=type(pid).__name__, retained_pid=pid):
                self._observe(dict(birth), dict(birth), pid=pid, queries=0)
        for code in (0, 1, -15, False, "None"):
            with self.subTest(known_returncode=code):
                self._observe(dict(birth), dict(birth), returncode=code, queries=0)
        for parent in (dict(STARTUP.identity(202, 1), pid=203), dict(STARTUP.identity(202, 1), uniqueId=2021)):
            self._observe(dict(birth), dict(birth), parent=parent, queries=0)
        # Even an internally matching alternative parent is not os.getpid().
        self._observe(dict(birth, parentPid=203), dict(birth, parentPid=203),
                      parent=dict(STARTUP.identity(202, 1), pid=203), queries=0)
        self._observe(dict(birth), dict(birth), expected_account=dict(STARTUP.account(), uid=502, euid=502), queries=0)
        for bad in (True, -1, 1 << 32):
            self._observe(dict(birth), dict(birth), expected_account=dict(STARTUP.account(), uid=bad, euid=bad),
                          queries=0, reason="REFUSED")
        native_error = M.ExperimentError("IDENTITY", "UNSUPPORTED")
        self._observe(dict(birth), dict(birth), native_error=native_error)

        for old, new in ((1, 1), (9, 701), (700, 3), ((1 << 32) - 1, 0)):
            with self.subTest(service_versions=(old, new)), self._image_service(old, new) as state:
                held = copy.deepcopy((state.birth, state.image, state.fixture.ready))
                self.assertEqual(M.service(STARTUP.EVIDENCE / "N2"), 23)
                self.assertEqual((state.birth, state.image, state.fixture.ready), held)
                self.assertIs(state.bound, state.image)
                self.assertEqual((len(state.binding_calls), len(state.ready_calls)), (1, 1))
                self.assertEqual(state.queries, {"birth": [303], "binding": [303], "recheck": [303, 303], "token": []})
                self.assertEqual(state.signal_attempts, [])
                self.assertEqual(state.snapshots, [])
                self.assertEqual(state.written, [])
                self.assertNotIn("cleanup-poll", state.order)
                self.assertEqual([row["serial"] for row in state.channel.sent], [1, 4, 8])
                self.assertEqual([row["serial"] for row in state.probe_channel.sent], [6])
                order = ("native-birth", "read3", "complete3", "bind-enter", "native-image", "image-bound",
                         "ready-validate", "ready-accepted", "image-recheck1", "send4", "read5", "complete5",
                         "image-recheck2", "send6", "read7", "finish", "send8")
                for first, second in zip(order, order[1:]):
                    self.assertLess(state.order.index(first), state.order.index(second), first + "_BEFORE_" + second)
                self.assertTrue(state.native.closed and state.captures.closed and state.pipes.closed)
                self.assertIsNot(state.ready_calls[0][0]["payload"]["producer"], state.image)
                for name in ("wait", "communicate", "terminate", "kill", "send_signal"):
                    getattr(state.process, name).assert_not_called()
                # finish is a bounded endpoint model; real post-START wait/drain
                # is byte-preserved in test02, not an observed OS wait receipt.

        # A stale or fabricated READY version never supplies binding authority.
        # A successful native helper binds cleanup BEFORE READY acceptance.
        for reported in (12, 88):
            with self.subTest(reported_version=reported), self._image_service(reported_version=reported) as state:
                error = self._service_refusal(state, site="CHILD_READY_VALIDATE", bindings=1, queries=1,
                                              ready=1, cleanup=state.image)
                self.assertIs(state.bound, state.image)
                self.assertEqual(error.ready_site, "READY_PRODUCER")
                self.assertEqual(error.ready_producer, READY.detail("PAIR", "EQUALITY", "PID_VERSION"))
                lines = M.parse_startup_record(b"".join(state.written), "N2", STARTUP.BINDING)
                self.assertIn(READY.DETAIL_PREFIX + "N2|PAIR|EQUALITY|PID_VERSION", lines)
                self.assertEqual(len(state.signal_returns), 1)
                self.assertEqual(state.native.signals[0]["identity"], state.image)
                self.assertEqual(state.native.signals[0]["returnedCode"], 0)
                self.assertEqual(state.queries["token"], [303, 303])
                self.assertEqual(state.queries["recheck"], [])
                self.assertEqual(state.cleanup_errors, [])
        with self._image_service(reported_version=88) as state:
            state.fixture.ready["payload"]["producer"]["pid"] = 999
            self._ready_packet(state)
            error = self._service_refusal(state, site="CHILD_READY_VALIDATE", bindings=1, queries=1,
                                          ready=1, cleanup=state.image)
            self.assertEqual(error.ready_producer, READY.detail("PAIR", "EQUALITY", "PID", "PID_VERSION"))
            self.assertNotIn(999, state.identity_pids)

        # Actual missing F3: strictly the validated birth, not a newly observed
        # image. A stale birth's token refusal is failure, not rescue/retirement.
        for current in (12, 77):
            with self.subTest(prebinding_eof_image=current), self._image_service(12, current) as state:
                state.probe_channel.packets.clear()
                error = self._service_refusal(state, site="CHILD_READY_READ", bindings=0, queries=0,
                                              ready=0, cleanup=state.birth)
                self.assertEqual((error.stage, error.reason, error.protocol_eof), ("START", "STATUS_MISSING", (3, "HEADER", "EMPTY")))
                self.assertIsNone(state.bound)
                self.assertEqual(len(state.signal_returns), 1 if current == 12 else 0)
                self.assertEqual(len(state.cleanup_errors), 0 if current == 12 else 1)
                self.assertEqual(state.queries["token"], [303, 303] if current == 12 else [303])
                self.assertNotIn("native-image", state.order)
        with self._image_service(12, 12, fail="CHILD_PIPES") as state:
            error = self._service_refusal(state, site="CHILD_PIPES", bindings=0, queries=0, ready=0, cleanup=state.birth)
            self.assertIs(error, state.failure)
            self.assertEqual(len(state.signal_returns), 1)
            self.assertIsNone(state.pipes)

        # A provisional invalid return is not retained as cleanup authority.
        provisional = (
            None, dict(birth, pid=304), dict(birth, parentPid=203), dict(birth, parentUniqueId=2021),
            dict(birth, uniqueId=0), dict(birth, status=0), dict(birth, uid=502, realUid=502),
            dict(birth, pidVersion=True), dict(birth, realGid=-1), dict(birth, extra=0),
            {key: value for key, value in birth.items() if key != "pidVersion"},
        )
        for index, value in enumerate(provisional):
            with self.subTest(invalid_provisional_birth=index), self._image_service() as state:
                state.birth = copy.deepcopy(value)
                error = self._service_refusal(state, site="CHILD_IDENTITY", bindings=0, queries=0, ready=0)
                self.assertEqual((error.stage, error.reason), ("IDENTITY", "IDENTITY_CHANGED"))
                self.assertIsNone(state.pipes)
                self.assertIsNone(state.bound)
                self.assertEqual(state.signal_returns, [])
                self.assertNotIn(3, state.read_returns)
        with self._image_service() as state:
            state.birth_error = M.ExperimentError("IDENTITY", "UNSUPPORTED")
            error = self._service_refusal(state, site="CHILD_IDENTITY", bindings=0, queries=0, ready=0)
            self.assertIs(error, state.birth_error)
            self.assertIsNone(state.pipes)

        # No rejected/failed normal observation authorizes a cleanup retry.
        with self._image_service() as state:
            state.image["uniqueId"] += 1
            error = self._service_refusal(state, site="CHILD_READY_VALIDATE", bindings=1, queries=1,
                                          ready=0, cleanup=state.birth)
            self.assertEqual((error.stage, error.reason), ("IDENTITY", "IDENTITY_CHANGED"))
            self.assertIsNone(state.bound)
            self.assertEqual(state.signal_returns, [])
            self.assertEqual(state.queries["token"], [303])
        with self._image_service() as state:
            state.image_error = M.ExperimentError("IDENTITY", "UNSUPPORTED")
            error = self._service_refusal(state, site="CHILD_READY_VALIDATE", bindings=1, queries=1,
                                          ready=0, cleanup=state.birth)
            self.assertIs(error, state.image_error)
            self.assertIsNone(state.bound)
            self.assertEqual(state.signal_returns, [])
        with self._image_service() as state:
            state.process.returncode = 0
            self._service_refusal(state, site="CHILD_READY_VALIDATE", bindings=1, queries=0, ready=0)
            self.assertIsNone(state.bound)
            self.assertEqual(state.queries["token"], [])

        # Exec/image change after the native binding query, and again after F4
        # but before F6, fails unchanged full native.same. No later rebinding.
        for recheck in (1, 2):
            with self.subTest(later_image_change=recheck), self._image_service() as state:
                state.recheck_images[recheck - 1] = dict(state.image, pidVersion=3)
                error = self._service_refusal(state, site="CHILD_RECHECK" if recheck == 1 else None,
                    bindings=1, queries=1, ready=1, cleanup=state.image, forwarded=recheck == 2)
                self.assertEqual((error.stage, error.reason), ("IDENTITY", "IDENTITY_CHANGED"))
                self.assertIs(state.bound, state.image)
                self.assertEqual(len(state.rechecks), recheck)
                self.assertEqual(state.signal_returns, [])
                self.assertEqual(state.queries["token"], [303])

        # Original READY refusal remains primary through token acquisition
        # refusal, a race at its second full-image check, or a signal error.
        for cleanup_failure in ("TOKEN_PERMISSION", "TOKEN_IMAGE_CHANGE", "SIGNAL_RETURN"):
            with self.subTest(cleanup_error=cleanup_failure), self._image_service(reported_version=12) as state:
                if cleanup_failure == "TOKEN_PERMISSION":
                    state.task_name_code = 5
                elif cleanup_failure == "TOKEN_IMAGE_CHANGE":
                    state.token_images = [state.image, dict(state.image, pidVersion=78)]
                else:
                    state.signal_code = 5
                error = self._service_refusal(state, site="CHILD_READY_VALIDATE", bindings=1, queries=1,
                                              ready=1, cleanup=state.image)
                self.assertEqual(error.ready_producer, READY.detail("PAIR", "EQUALITY", "PID_VERSION"))
                self.assertEqual(len(state.cleanup_errors), 1)
                self.assertIsNot(error, state.cleanup_errors[0])
                cleanup = state.cleanup_errors[0]
                expected = {"TOKEN_PERMISSION": ("IDENTITY", "PERMISSION_DENIED", "UNKNOWN"),
                            "TOKEN_IMAGE_CHANGE": ("IDENTITY", "IDENTITY_CHANGED", "NONE"),
                            "SIGNAL_RETURN": ("CLOSE", "RETURN_FAILED", M.errno_name(5))}[cleanup_failure]
                self.assertEqual((cleanup.stage, cleanup.reason, cleanup.errno_name), expected)
                self.assertEqual(len(state.signal_returns), 1 if cleanup_failure == "SIGNAL_RETURN" else 0)
                self.assertEqual(len(state.queries["token"]), 1 if cleanup_failure == "TOKEN_PERMISSION" else 2)
                self.assertEqual(state.port_releases, [] if cleanup_failure == "TOKEN_PERMISSION" else [(17, 19)])
                self.assertIs(state.bound, state.image)

        # A query consuming the inherited deadline is not an excuse to refresh
        # any clock/budget. F4 is refused and cleanup gets that same expired end.
        with self._image_service() as state:
            state.expire_in_query = True
            error = self._service_refusal(state, site="CHILD_READY_FORWARD", bindings=1, queries=1,
                                          ready=1, cleanup=state.image)
            self.assertEqual((error.stage, error.reason), ("START", "TIMEOUT"))
            self.assertEqual(error.timeout_site, ("SEND_PRE", 4, "FRAME"))
            self.assertEqual(state.token_attempts, [])
            self.assertEqual(state.signal_returns, [])
            self.assertEqual(len(state.cleanup_errors), 1)

    def test_02_exact_inverse_and_unchanged_ownership_guards(self):
        source = STARTUP.SOURCE.read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(), CURRENT_RUNTIME_SHA256)
        self.assertEqual(CLOCK.CHILD_STARTUP_BASE_RUNTIME_SHA256, PREIMAGE)
        self.assertEqual(len(CLOCK.CHILD_STARTUP_PATCH), 5)
        prior = CLOCK.restore_child_startup_runtime(source)
        self.assertNotEqual(source, prior)
        self.assertEqual(hashlib.sha256(prior.encode("utf-8")).hexdigest(), PREIMAGE)
        restores = (CLOCK.restore_child_startup_runtime, CLOCK.restore_ready_producer_runtime,
                    CLOCK.restore_startup_diagnostic_runtime, CLOCK.restore_protocol_timeout_runtime,
                    CLOCK.restore_protocol_eof_runtime, CLOCK.restore_plist_name_runtime,
                    CLOCK.restore_admin_return_runtime, CLOCK.restore_runtime)
        hashes = (
            PREIMAGE,
            "db90735880ff020f027a91c695221963bbebce07a3ee7e7e624622692931c852",
            "fac1691819a7a201851fa4c6062f2f9d272d6ab7635c4b613746a88f58e50754",
            "17b7105e3dab4dcf865d8fda633f988b9ad78d1b286e0ecbb215da8d2828da47",
            "e92c291407c4b1f6f000a675c07190b34c340cd6b17648e5d73fd8a610e9acac",
            "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf",
            "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b",
            "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d",
        )
        for restore, expected in zip(restores, hashes):
            self.assertEqual(hashlib.sha256(restore(source).encode("utf-8")).hexdigest(), expected)
        for restore in restores[1:]:
            with patch.object(CLOCK, "restore_child_startup_runtime", wraps=restores[0]) as newest:
                restore(source)
                newest.assert_called_once_with(source)
        self.assertEqual((len(CLOCK.READY_PRODUCER_PATCH), len(CLOCK.STARTUP_DIAGNOSTIC_PATCH),
                          len(CLOCK.PROTOCOL_TIMEOUT_PATCH), len(CLOCK.PROTOCOL_EOF_PATCH), len(CLOCK.PLIST_NAME_PATCH),
                          len(CLOCK.ADMIN_RETURN_PATCH), len(CLOCK.RUNTIME_PATCH), len(CLOCK.WORKFLOW_PATCH),
                          len(CLOCK.EXPERIMENT_TEST_PATCH)), (5, 10, 13, 7, 3, 8, 8, 3, 3))

        # Preserve EVERY previous inverse byte and pin, not a broad AST erasure
        # or embedded preimage substitute. No historical inverse is executed.
        inverse = STARTUP.INVERSE.read_text(encoding="utf-8")
        start = inverse.index("# The original direct-child startup image seam")
        end = inverse.index("# The finite READY-producer diagnostic", start)
        old_inverse = inverse[:start] + inverse[end:]
        start = old_inverse.index("def restore_child_startup_runtime(source):\n")
        end = old_inverse.index("def restore_ready_producer_runtime(source):\n", start)
        old_inverse = old_inverse[:start] + old_inverse[end:]
        chaining = "    source = restore_child_startup_runtime(source)\n"
        self.assertEqual(old_inverse.count(chaining), 1)
        old_inverse = old_inverse.replace(chaining, "", 1)
        self.assertEqual(hashlib.sha256(old_inverse.encode("utf-8")).hexdigest(), INVERSE_PREIMAGE)
        for unchanged in ("RUNTIME_PATCH, 33,", "WORKFLOW_PATCH, 3,", "EXPERIMENT_TEST_PATCH, 6,"):
            self.assertIn(unchanged, old_inverse)

        def reject(changed):
            self.assertNotEqual(changed, source, "A_CURRENT_SOURCE_MUTATION_MUST_ACTUALLY_CHANGE_THE_INPUT")
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(changed)

        for index, (before, after) in enumerate(CLOCK.CHILD_STARTUP_PATCH):
            with self.subTest(child_hunk=index):
                self.assertIs(type(before), str)
                self.assertIs(type(after), str)
                self.assertNotEqual(before, after)
                self.assertEqual(source.count(after), 1)
                reject(source.replace(after, before, 1))
                reject(source + after)
                reject(source.replace(after, after + "\n# UNREVIEWED_CHILD_HUNK_TAIL\n", 1))
                changed = list(CLOCK.CHILD_STARTUP_PATCH)
                changed[index] = (before + "\n# WRONG_CHILD_PREIMAGE\n", after)
                with patch.object(CLOCK, "CHILD_STARTUP_PATCH", tuple(changed)):
                    for restore in restores:
                        with self.assertRaises(AssertionError):
                            restore(source)
        for changed in (CLOCK.CHILD_STARTUP_PATCH[:-1], CLOCK.CHILD_STARTUP_PATCH + CLOCK.CHILD_STARTUP_PATCH[:1]):
            with patch.object(CLOCK, "CHILD_STARTUP_PATCH", changed):
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(source)
        for bad in (None, b"", "", STARTUP.StringSubclass(source), prior, source + "\n# UNRELATED_CHILD_MUTATION\n"):
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(bad)

        mutations = (
            ('process.returncode is None and type(process.pid) is int and process.pid > 0', 'True'),
            ('type(process.pid) is int and process.pid > 0', 'process.pid > 0'),
            ('same_identity(birth, birth)', 'None'),
            ('birth["pid"] == process.pid', 'True'),
            ('birth["parentPid"] == parent["pid"] == os.getpid()', 'birth["parentPid"] == parent["pid"]'),
            ('birth["parentUniqueId"] == parent["uniqueId"]', 'True'),
            ('identity_account(birth, expected_account)', 'None'),
            ('observed = native.identity(process.pid)', 'observed = native.identity(ready["payload"]["producer"]["pid"])'),
            ('same_identity(observed, observed)', 'None'),
            ('identity_account(observed, expected_account)', 'None'),
            ('return observed\n', 'return dict(observed)\n'),
            ('producer_birth = birth\n', 'producer_birth = dict(birth)\n'),
            ('producer_identity = observe_startup_child(native, process, producer_birth, service_identity, prepared["account"])',
             'producer_identity = ready["payload"]["producer"]'),
            ('cleanup_identity = producer_identity if producer_identity is not None else producer_birth',
             'cleanup_identity = producer_identity if producer_identity is not None else birth'),
            ('cleanup_identity = producer_identity if producer_identity is not None else producer_birth',
             'cleanup_identity = observe_startup_child(native, process, producer_birth, service_identity, prepared["account"])'),
            ('native.signal(cleanup_identity, signal.SIGTERM, end_ns)', 'os.kill(process.pid, signal.SIGTERM)'),
            ('native.signal(cleanup_identity, signal.SIGTERM, end_ns)', 'native.signal(cleanup_identity, signal.SIGTERM, end_ns + NS)'),
            ('IDENTITY_KEYS - {"status"}', 'IDENTITY_KEYS - {"status", "pidVersion"}'),
            ('same_identity(payload["producer"], producer_identity)', 'same_identity(payload["producer"], payload["producer"])'),
            ('native.same(producer_identity)', 'native.same(ready["payload"]["producer"])'),
            ('        self.same(identity)\n', '        pass\n'),
            ('self.proc.proc_signal_with_audittoken(ctypes.byref(token), signum)', 'os.kill(identity["pid"], signum)'),
            ('context.native.watch(producer_identity)', 'context.native.same(producer_identity)'),
            ('state["producer"] is not None or not state["prepareSent"]', 'True'),
            ('not context.export_called and context.recipient is context.recipient_original', 'True'),
            ('not any(key in os.environ for key in OWNER_ENV)', 'True'),
            ('close_fds=True, pass_fds=(child_fd,), cwd=ROOT, env=environment', 'close_fds=False, cwd=ROOT, env=environment'),
            ('[interpreter["path"], "-I", "-B", "-S", str(ROOT / SCRIPT), "_probe", str(child_fd)]',
             '[interpreter["path"], str(ROOT / SCRIPT), "_probe", str(child_fd)]'),
            ('return left(end_ns, "START")', 'return left(end_ns + NS, "START")'),
            ('CASE_SECONDS = 120, 180, 40', 'CASE_SECONDS = 120, 180, 41'),
        )
        for index, (before, after) in enumerate(mutations):
            with self.subTest(current_guard=index):
                self.assertIn(before, source)
                reject(source.replace(before, after, 1))
        exempt = 'IDENTITY_KEYS - {"status", "pidVersion"}'
        self.assertEqual(source.count(exempt), 1, "ONE_NARROW_BIRTH_CONTINUITY_GATE_NOT_A_GENERIC_IDENTITY_MODE")
        for field in CONTINUITY:
            reject(source.replace(exempt, 'IDENTITY_KEYS - {"status", "pidVersion", "' + field + '"}', 1))
        # Independently alter initial service authority, not merely the helper's
        # analogous guard. Every negative is still the actual current source.
        initial_before, initial_after = CLOCK.CHILD_STARTUP_PATCH[2]
        for before, after in (('same_identity(birth, birth)', 'None'),
                              ('birth["pid"] == process.pid', 'True'),
                              ('birth["parentPid"] == os.getpid()', 'True'),
                              ('birth["parentUniqueId"] == service_identity["uniqueId"]', 'True'),
                              ('identity_account(birth, prepared["account"])', 'None')):
            self.assertIn(before, initial_after)
            changed_hunk = initial_after.replace(before, after, 1)
            reject(source.replace(initial_after, changed_hunk, 1))
        self.assertNotEqual(initial_before, initial_after)

        # AST here is source DATA only. Neither prior runtime nor prior inverse
        # is compiled to executable code, imported, or behaviorally exercised.
        tree, old_tree = ast.parse(source, feature_version=(3, 9)), ast.parse(prior, feature_version=(3, 9))
        current = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        original = {node.name: node for node in old_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(set(current) - set(original), {"observe_startup_child"})
        self.assertFalse(set(original) - set(current))

        def segment(text, node):
            start = min([node.lineno] + [item.lineno for item in node.decorator_list])
            return "".join(text.splitlines(keepends=True)[start - 1:node.end_lineno])

        for name, node in original.items():
            if name != "service":
                self.assertEqual(segment(source, current[name]), segment(prior, node), "UNCHANGED_COMPLETE_FUNCTION_BYTES_" + name)
        for name in ("same_identity", "identity_account", "validate_ready", "Darwin", "ProbePipes", "producer",
                     "perform_case", "abort_suite", "emit_startup_diagnostic", "Context", "child_environment"):
            self.assertIn(name, original)
            self.assertEqual(segment(source, current[name]), segment(prior, original[name]))
        self.assertEqual(tuple(ast.dump(node) for node in tree.body if node not in (current["service"], current["observe_startup_child"])),
                         tuple(ast.dump(node) for node in old_tree.body if node is not original["service"]),
                         "NO_OTHER_MODULE_IMPORT_GLOBAL_FUNCTION_SCHEMA_OR_POLICY_CHANGE")

        helper, service = current["observe_startup_child"], current["service"]
        self.assertIs(tree.body[tree.body.index(service) - 1], helper)
        self.assertEqual([arg.arg for arg in helper.args.args], ["native", "process", "birth", "parent", "expected_account"])
        self.assertFalse(helper.args.posonlyargs or helper.args.kwonlyargs or helper.args.defaults or
                         helper.args.kw_defaults or helper.args.vararg or helper.args.kwarg or helper.decorator_list)
        self.assertEqual(sorted(ast.unparse(node.func) for node in ast.walk(helper) if isinstance(node, ast.Call)),
                         sorted(["require"] * 3 + ["same_identity"] * 2 + ["identity_account"] * 2 +
                                ["type", "os.getpid", "native.identity", "all"]))
        self.assertEqual([ast.unparse(node) for node in ast.walk(helper) if isinstance(node, ast.Assign)],
                         ["observed = native.identity(process.pid)"])
        self.assertFalse(any(isinstance(node, (ast.For, ast.While, ast.Try, ast.With, ast.AugAssign, ast.Delete)) for node in ast.walk(helper)))
        self.assertFalse(any(isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) for node in ast.walk(helper)))
        self.assertIsInstance(helper.body[-1], ast.Return)
        self.assertEqual(ast.unparse(helper.body[-1].value), "observed")
        self.assertNotIn("ready", {node.id for node in ast.walk(helper) if isinstance(node, ast.Name)})
        generators = [node for node in ast.walk(helper) if isinstance(node, ast.GeneratorExp)]
        self.assertEqual(len(generators), 1)
        generator = generators[0]
        self.assertEqual(ast.dump(generator.elt), ast.dump(ast.parse("observed[key] == birth[key]", mode="eval").body))
        self.assertEqual(len(generator.generators), 1)
        iterator = generator.generators[0]
        self.assertEqual(ast.unparse(iterator.target), "key")
        self.assertFalse(iterator.ifs or iterator.is_async)
        self.assertIsInstance(iterator.iter, ast.BinOp)
        self.assertIsInstance(iterator.iter.op, ast.Sub)
        self.assertEqual(ast.unparse(iterator.iter.left), "IDENTITY_KEYS")
        self.assertEqual({node.value for node in iterator.iter.right.elts}, {"status", "pidVersion"})

        parents = {child: node for node in ast.walk(service) for child in ast.iter_child_nodes(node)}

        def assignments(name):
            return sorted((node for node in ast.walk(service) if isinstance(node, ast.Assign) and
                           any(isinstance(held, ast.Name) and held.id == name for target in node.targets
                               for held in ast.walk(target))), key=lambda node: node.lineno)

        def statements(text):
            return tuple(ast.dump(node) for node in ast.parse(text, feature_version=(3, 9)).body)

        birth_stores, image_stores = assignments("producer_birth"), assignments("producer_identity")
        self.assertEqual((len(birth_stores), len(image_stores), len(assignments("birth"))), (2, 2, 1))
        self.assertIsNone(birth_stores[0].value.value)
        self.assertEqual(ast.unparse(birth_stores[1].value), "birth")
        self.assertEqual(ast.unparse(image_stores[0].targets[0].elts[-1]), "producer_identity")
        self.assertIsNone(image_stores[0].value.elts[-1].value)
        birth_assignment = assignments("birth")[0]
        birth_block = parents[birth_assignment].body
        index = birth_block.index(birth_assignment)
        self.assertEqual(tuple(ast.dump(node) for node in birth_block[index:index + 5]), statements(
            'birth = native.identity(process.pid)\n'
            'same_identity(birth, birth)\n'
            'require(birth["pid"] == process.pid and birth["parentPid"] == os.getpid() and\n'
            '        birth["parentUniqueId"] == service_identity["uniqueId"], "IDENTITY", "IDENTITY_CHANGED")\n'
            'identity_account(birth, prepared["account"])\n'
            'producer_birth = birth\n'))
        invocations = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                       isinstance(node.func, ast.Name) and node.func.id == "observe_startup_child"]
        self.assertEqual(len(invocations), 1)
        self.assertIs(image_stores[1].value, invocations[0])
        binding_block = parents[image_stores[1]].body
        index = binding_block.index(image_stores[1])
        self.assertEqual(tuple(ast.dump(node) for node in binding_block[index - 3:index + 4]), statements(
            'startup_site = "CHILD_READY_READ"\n'
            'ready = read_frame(probe_channel, 3, binding, trace, end_ns, pipes.pump)\n'
            'startup_site = "CHILD_READY_VALIDATE"\n'
            'producer_identity = observe_startup_child(native, process, producer_birth, service_identity, prepared["account"])\n'
            'validate_ready(ready, prepared, service_identity, producer_identity)\n'
            'startup_site = "CHILD_RECHECK"\n'
            'native.same(producer_identity)\n'))
        native_queries = sorted((node for node in ast.walk(service) if isinstance(node, ast.Call) and
                                 ast.unparse(node.func) == "native.identity"), key=lambda node: node.lineno)
        self.assertEqual([ast.unparse(node) for node in native_queries],
                         ["native.identity(os.getpid())", "native.identity(process.pid)"])

        def calls(name):
            return sorted((node for node in ast.walk(service) if isinstance(node, ast.Call) and
                           ast.unparse(node.func) == name), key=lambda node: node.lineno)

        read3 = next(node for node in calls("read_frame") if node.args[1].value == 3)
        read5 = next(node for node in calls("read_frame") if node.args[1].value == 5)
        send4 = next(node for node in calls("send_frame") if node.args[1].value == 4)
        send6 = next(node for node in calls("send_frame") if node.args[1].value == 6)
        rechecks = [node for node in calls("native.same") if ast.unparse(node.args[0]) == "producer_identity"]
        self.assertEqual(len(rechecks), 2)
        ordered = (birth_assignment, read3, invocations[0], calls("validate_ready")[0], rechecks[0], send4, read5, rechecks[1], send6)
        self.assertEqual([node.lineno for node in ordered], sorted(node.lineno for node in ordered))
        self.assertFalse(any(node.lineno < invocations[0].lineno for name in
                             ("process.poll", "process.wait", "process.communicate", "process.terminate", "process.kill")
                             for node in calls(name)))

        outer = next(node for node in service.body if isinstance(node, ast.Try))
        old_outer = next(node for node in original["service"].body if isinstance(node, ast.Try))
        self.assertEqual((len(outer.handlers), len(old_outer.handlers)), (1, 1))
        handler, old_handler = outer.handlers[0], old_outer.handlers[0]
        self.assertEqual((len(handler.body), len(old_handler.body)), (7, 6))
        self.assertEqual(ast.dump(handler.type), ast.dump(old_handler.type))
        self.assertEqual(handler.name, old_handler.name)
        self.assertEqual(tuple(ast.dump(node) for node in handler.body[2:4]), statements(
            'cleanup_identity = producer_identity if producer_identity is not None else producer_birth\n'
            'if process is not None and process.poll() is None and native is not None and cleanup_identity is not None:\n'
            '    with contextlib.suppress(BaseException):\n'
            '        native.signal(cleanup_identity, signal.SIGTERM, end_ns)\n'))
        self.assertEqual(tuple(ast.dump(node) for node in handler.body[:2] + handler.body[4:]),
                         tuple(ast.dump(node) for node in old_handler.body[:2] + old_handler.body[3:]),
                         "ORIGINAL_EXCEPTION_SNAPSHOT_BOUNDED_FINISH_PRIMARY_AND_BARE_RETHROW")
        handler_calls = {ast.unparse(node.func) for node in ast.walk(handler) if isinstance(node, ast.Call)}
        self.assertFalse({"observe_startup_child", "native.identity", "process.wait", "process.communicate", "os.kill"} & handler_calls)
        self.assertIsInstance(handler.body[-1], ast.Raise)
        self.assertIsNone(handler.body[-1].exc)
        self.assertIsNone(handler.body[-1].cause)
        self.assertEqual(tuple(ast.dump(node) for node in outer.finalbody), tuple(ast.dump(node) for node in old_outer.finalbody))
        self.assertNotIn("SIGCHLD", segment(source, helper) + segment(source, service))

        inverse_tree = ast.parse(inverse, feature_version=(3, 9))
        self.assertEqual([ast.unparse(node) for node in inverse_tree.body if isinstance(node, (ast.Import, ast.ImportFrom))],
                         ["import hashlib"])
        inverse_function = next(node for node in inverse_tree.body if isinstance(node, ast.FunctionDef) and
                                node.name == "restore_child_startup_runtime")
        self.assertFalse(any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in ast.walk(inverse_function)))
        self.assertFalse({"open", "read_text", "read_bytes", "exec", "eval", "compile", "parse"} &
                         {node.func.id if isinstance(node.func, ast.Name) else node.func.attr
                          for node in ast.walk(inverse_function) if isinstance(node, ast.Call)})
        self.assertEqual((M.JOB_SECONDS, M.STEP_SECONDS, M.PREPARE_SECONDS, M.NATIVE_SECONDS, M.CASE_SECONDS,
                          M.ABORT_SECONDS, M.FREEZE_SECONDS, M.EXPORT_SECONDS, M.UPLOAD_SECONDS, M.ADMIN_SECONDS),
                         (1440, 720, 120, 180, 40, 120, 60, 120, 420, 10))
        self.assertEqual((len(M.FRAME_ROSTER), M.FRAME_BYTES, M.STREAM_BYTES, M.STARTUP_BYTES), (8, 16384, 65536, 2048))
        self.assertEqual(M.CASES, ("N1", "N2", "N3", "N4"))
        for relative, expected in (
            ("scripts/audit_processes.py", "7ef1beb8a79ce3c8e062100849babee6ffa0ce3421d0f0fc56706c3e0ef7ed13"),
            (".github/workflows/darwin-native-context-experiment.yml", "46dd83658e256ed4c14ebe376addaac7f73b4cd40552b13853515d9c1f5d5933"),
            (".github/test-evidence-recipient.json", "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"),
            ("AGENTS.md", "3ca3ef11f49ba90152754fb9d884ed353a5bc549b0ab648e182d889d4283d84b"),
            ("CLAUDE.md", "0fd0e8bdd297e16caabc40e87411c377f674769a40b73a35f43818bf9f97a71d"),
        ):
            self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)
        self.assertEqual(StartupIdentity.__bases__, (unittest.TestCase,))
        self.assertIs(M, STARTUP.M)
        self.assertIs(CLOCK, STARTUP.CLOCK)
        self.assertEqual(READY.STARTUP_SHA256, "492d9b402824e4b7491791ce05720d3469d693a73e51305ed04f32ee96c96e68")


if __name__ == "__main__":
    if tuple(unittest.defaultTestLoader.getTestCaseNames(StartupIdentity)) != METHODS:
        raise SystemExit("FIXED_TWO_STARTUP_IDENTITY_METHODS_REQUIRED")
    suite = unittest.TestSuite(StartupIdentity(name) for name in METHODS)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
