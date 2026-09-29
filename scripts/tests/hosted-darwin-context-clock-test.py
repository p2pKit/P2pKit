#!/usr/bin/env python3
"""Six offline clock controls, not installed-interpreter/native qualification.

All clocks, identities and upload files below are synthetic DATA. Only current
runtime functions and selected current inline clock/data AST nodes execute.
No reconstructed preimage, complete workflow, process, socket, native library,
privileged operation, recipient, encryption or remote upload may execute.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-context-clock-test.py
"""
import ast
import contextlib
import copy
import ctypes  # Load the standard module before forbidding native acquisition.
import hashlib
import importlib.util
import io
from pathlib import Path
import socket
import subprocess
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/run-hosted-darwin-context-experiment.py"
WORKFLOW = ROOT / ".github/workflows/darwin-native-context-experiment.yml"
NS, UINT64 = 1_000_000_000, (1 << 64) - 1
DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
SHA, TREE, BINDING = "a" * 40, "b" * 40, "c" * 64
EPOCH, RAW_KIND = 1790000000 * NS, 17  # Fake provider selector, not an installed Darwin constant.
CANARY, SOURCE_BYTES = "SYNTHETIC_CLOCK_CANARY", b"SYNTHETIC_SOURCE_NOT_EXECUTABLE"


def offline(event, _args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups", "os.chown",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }:
        raise AssertionError("OFFLINE_CLOCK_CONTROL_FORBIDDEN_OPERATION")


if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_CLOCK_INVOCATION_REQUIRED")
sys.addaudithook(offline)
spec = importlib.util.spec_from_file_location("darwin_context_clock_controls", SOURCE)
M = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = M
spec.loader.exec_module(M)
clock_spec = importlib.util.spec_from_file_location("darwin_context_clock_inverse", ROOT / "scripts/tests/hosted_darwin_context_clock_inverse.py")
CLOCK = importlib.util.module_from_spec(clock_spec)
clock_spec.loader.exec_module(CLOCK)


def allocation_fixture():
    return dict(schema=2, clockDomain=DOMAIN, source=SHA, sourceTree=TREE, runId="123", runAttempt="1",
                startedMonotonicNs=100 * NS, startedEpochNs=EPOCH)


def github_fixture():
    # Forwarded source-owned DATA only; this fixture does not attest a hosted run.
    return dict(repository=M.REPOSITORY, workflow=M.WORKFLOW, job="context_experiment",
                source=SHA, sourceTree=TREE, runId="123", runAttempt="1")


def account_fixture():
    return dict(uid=501, euid=501, gid=20, egid=20, groups=[12, 20, 61])


def prepared_fixture():
    return dict(schema=1, binding=BINDING, case="N1", github=github_fixture(), allocation=allocation_fixture(),
                source={"commit": SHA, "tree": TREE, "files": {M.SCRIPT: M.digest(SOURCE_BYTES)}},
                account=account_fixture(), foreground={}, boot="SYNTHETIC_BOOT",
                interpreter={"path": "/synthetic/python"}, directoryIdentity=[11, 12], operationIdentity=[11, 12],
                socketIdentity=[13, 14], caseEndNs=160 * NS, stepEndNs=840 * NS, jobEndNs=1540 * NS)


def inline_tree():
    source = WORKFLOW.read_text(encoding="utf-8").split("        run: |\n", 1)[1].split("\n      - name:", 1)[0]
    source = "\n".join(line[10:] if line.startswith(" " * 10) else line for line in source.splitlines())
    return ast.parse(source, filename="CURRENT_INLINE_CLOCK_SOURCE_ONLY", feature_version=(3, 9))


def inline_reader(time_data, platform_name="darwin"):
    """Only five current clock definitions, never imports or allocation I/O."""
    nodes, names = [], []
    for node in inline_tree().body:
        name = node.name if isinstance(node, ast.FunctionDef) else (
            node.targets[0].id if isinstance(node, ast.Assign) and len(node.targets) == 1 and
            isinstance(node.targets[0], ast.Name) else None)
        if name in {"UINT64", "CLOCK_SCHEMA", "CLOCK_DOMAIN", "require", "shared_raw_ns"}:
            nodes.append(node)
            names.append(name)
    if names != ["UINT64", "CLOCK_SCHEMA", "CLOCK_DOMAIN", "require", "shared_raw_ns"]:
        raise AssertionError("EXACT_INLINE_CLOCK_DEFINITIONS_REQUIRED")
    namespace = {"time": time_data, "sys": types.SimpleNamespace(platform=platform_name),
                 "__builtins__": {"type": type, "int": int, "callable": callable, "getattr": getattr, "ValueError": ValueError}}
    module = ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[]))
    exec(compile(module, "CURRENT_INLINE_CLOCK_DEFINITIONS_ONLY", "exec"), namespace)
    return namespace


def inline_allocation(started, wall):
    nodes = [node for node in ast.walk(inline_tree()) if isinstance(node, ast.Assign) and len(node.targets) == 1 and
             isinstance(node.targets[0], ast.Name) and node.targets[0].id == "allocation"]
    if len(nodes) != 1:
        raise AssertionError("EXACT_INLINE_ALLOCATION_DATA_EXPRESSION_REQUIRED")
    expression = ast.fix_missing_locations(ast.Expression(body=nodes[0].value))
    return eval(compile(expression, "CURRENT_INLINE_ALLOCATION_DATA_ONLY", "eval"), {"__builtins__": {"dict": dict}},
                dict(CLOCK_SCHEMA=2, CLOCK_DOMAIN=DOMAIN, started=started, wall=wall,
                     request={"source_sha": SHA, "source_tree": TREE},
                     env={"GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1"}))


class ClockControls(unittest.TestCase):
    @contextlib.contextmanager
    def _raw(self, now):
        state = {"ns": now}
        read = Mock(side_effect=lambda _kind: state["ns"])
        fallback = Mock(side_effect=AssertionError("NO_PROCESS_LOCAL_OR_WALL_CLOCK_FALLBACK"))
        clock = types.SimpleNamespace(CLOCK_MONOTONIC_RAW=RAW_KIND, clock_gettime_ns=read,
            monotonic_ns=fallback, monotonic=fallback, perf_counter_ns=fallback,
            time_ns=lambda: EPOCH + state["ns"] - 100 * NS)
        with patch.object(M, "time", clock), patch.object(M.sys, "platform", "darwin"), patch.object(M.os, "environ", {}):
            yield state, clock, read
        fallback.assert_not_called()
        self.assertTrue(all(call.args == (RAW_KIND,) and not call.kwargs for call in read.call_args_list))

    def test_01_runtime_and_inline_fixed_raw_readers_fail_closed(self):
        class IntegerSubclass(int):
            pass

        for location in ("runtime", "allocation"):
            def invoke(platform_name, clock):
                if location == "allocation":
                    namespace = inline_reader(clock, platform_name)
                    self.assertEqual((namespace["CLOCK_SCHEMA"], namespace["CLOCK_DOMAIN"], namespace["UINT64"]),
                                     (2, DOMAIN, UINT64))
                    return namespace["shared_raw_ns"]()
                with patch.object(M, "time", clock), patch.object(M.sys, "platform", platform_name):
                    return M.shared_raw_ns()

            for value in (0, 1, NS, UINT64):
                read, fallback = Mock(return_value=value), Mock(side_effect=AssertionError("NO_CLOCK_FALLBACK"))
                clock = types.SimpleNamespace(CLOCK_MONOTONIC_RAW=RAW_KIND, clock_gettime_ns=read,
                                             monotonic_ns=fallback, monotonic=fallback, time_ns=fallback)
                self.assertEqual(invoke("darwin", clock), value)
                read.assert_called_once_with(RAW_KIND)
                fallback.assert_not_called()
            for key, value in (("platform", "linux"), ("platform", "win32"), ("clock_gettime_ns", None),
                               ("clock_gettime_ns", False), ("CLOCK_MONOTONIC_RAW", None),
                               ("CLOCK_MONOTONIC_RAW", True), ("CLOCK_MONOTONIC_RAW", 1.0),
                               ("CLOCK_MONOTONIC_RAW", IntegerSubclass(RAW_KIND))):
                read = Mock(return_value=NS)
                fields = dict(CLOCK_MONOTONIC_RAW=RAW_KIND, clock_gettime_ns=read)
                if key != "platform":
                    if value is None:
                        del fields[key]
                    else:
                        fields[key] = value
                with self.assertRaises((M.ExperimentError, ValueError)) as caught:
                    invoke(value if key == "platform" else "darwin", types.SimpleNamespace(**fields))
                read.assert_not_called()
                if location == "runtime":
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("PREPARE", "UNSUPPORTED"))
            for value in (None, True, False, -1, UINT64 + 1, 1.0, float("nan"), float("inf"), "1", IntegerSubclass(1)):
                read = Mock(return_value=value)
                with self.assertRaises((M.ExperimentError, ValueError)) as caught:
                    invoke("darwin", types.SimpleNamespace(CLOCK_MONOTONIC_RAW=RAW_KIND, clock_gettime_ns=read))
                read.assert_called_once_with(RAW_KIND)
                if location == "runtime":
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("PREPARE", "BOUND"))
            for error in (OSError(M.errno.EINVAL, CANARY), RuntimeError(CANARY)):
                read, fallback = Mock(side_effect=error), Mock(side_effect=AssertionError("NO_CLOCK_FALLBACK"))
                clock = types.SimpleNamespace(CLOCK_MONOTONIC_RAW=RAW_KIND, clock_gettime_ns=read,
                                             monotonic_ns=fallback, monotonic=fallback, time_ns=fallback)
                with self.assertRaises(type(error)) as caught:
                    invoke("darwin", clock)
                self.assertIs(caught.exception, error)
                read.assert_called_once_with(RAW_KIND)
                fallback.assert_not_called()

    def test_02_allocation_domain_schema_bindings_and_original_time_bounds(self):
        request, github = {"source_sha": SHA, "source_tree": TREE}, github_fixture()
        allocation = inline_allocation(100 * NS, EPOCH)
        self.assertEqual(allocation, allocation_fixture())
        original = copy.deepcopy(allocation)
        for elapsed in (0, 1, 100 * NS, 1440 * NS - 1):
            for skew in (-10 * NS, 0, 10 * NS):
                self.assertEqual(M.validate_allocation(allocation, request, github,
                                 100 * NS + elapsed, EPOCH + elapsed + skew), 1540 * NS)
        class IntegerSubclass(int):
            pass
        class StringSubclass(str):
            pass
        invalid = [None, {}, [], {**allocation, "extra": True}]
        invalid += [{key: value for key, value in allocation.items() if key != missing} for missing in allocation]
        invalid += [{**allocation, key: value} for key, value in (
            ("schema", 1), ("schema", True), ("schema", "2"), ("schema", IntegerSubclass(2)),
            ("clockDomain", None), ("clockDomain", "time.monotonic_ns"),
            ("clockDomain", DOMAIN + "_APPROX"), ("clockDomain", StringSubclass(DOMAIN)))]
        for changed in invalid:
            with self.assertRaises(M.ExperimentError) as caught:
                M.validate_allocation(changed, request, github, 120 * NS, EPOCH + 20 * NS)
            self.assertEqual((caught.exception.stage, caught.exception.reason), ("PREPARE", "IDENTITY_CHANGED"))
        for key, value in (("source", "d" * 40), ("sourceTree", "d" * 40), ("runId", "124"), ("runAttempt", "2")):
            with self.assertRaises(M.ExperimentError):
                M.validate_allocation({**allocation, key: value}, request, github, 120 * NS, EPOCH + 20 * NS)
        for now, wall in ((100 * NS - 1, EPOCH), (1540 * NS, EPOCH + 1440 * NS),
                          (120 * NS, EPOCH + 30 * NS + 1), (120 * NS, EPOCH + 10 * NS - 1)):
            with self.assertRaises(M.ExperimentError) as caught:
                M.validate_allocation(allocation, request, github, now, wall)
            self.assertEqual(caught.exception.reason, "TIMEOUT")
        for now, wall in ((True, EPOCH), (0, EPOCH), (120 * NS, True), (120 * NS, float("inf"))):
            with self.assertRaises(M.ExperimentError):
                M.validate_allocation(allocation, request, github, now, wall)
        self.assertEqual(allocation, original)

    def test_03_service_and_producer_contract_precedes_deadline_consumption(self):
        prepared, directory = prepared_fixture(), Path("/synthetic/evidence/N1")
        invalid = [None, {**prepared["allocation"], "schema": 1},
                   {key: value for key, value in prepared["allocation"].items() if key != "clockDomain"},
                   {**prepared["allocation"], "clockDomain": "time.monotonic_ns"}]
        for allocation in invalid:
            with patch.object(M, "account") as account, patch.object(M, "left") as left:
                with self.assertRaises(M.ExperimentError) as caught:
                    M.validate_prepared({**prepared, "allocation": allocation}, directory, None, None)
                self.assertEqual((caught.exception.stage, caught.exception.reason), ("START", "IDENTITY_CHANGED"))
                account.assert_not_called()
                left.assert_not_called()
        boundary = M.ExperimentError("IDENTITY", "REFUSED")
        for allocation in [*invalid, prepared["allocation"]]:
            native = types.SimpleNamespace(closed=False, close=Mock())
            with patch.object(M, "physical", return_value=directory), patch.object(M, "private_directory"), \
                    patch.object(M, "account", side_effect=account_fixture), \
                    patch.object(M, "ServiceCaptures", return_value=types.SimpleNamespace(closed=True)), \
                    patch.object(M, "Darwin", return_value=native), patch.object(M, "read_file", return_value=b"DATA"), \
                    patch.object(M, "parsed", return_value={**prepared, "allocation": allocation}), \
                    patch.object(M, "checked_interpreter", side_effect=boundary) as interpreter, \
                    patch.object(M, "left") as left, patch.object(M.socket, "socket") as channel, \
                    patch.object(M.subprocess, "Popen") as process:
                with self.assertRaises(M.ExperimentError) as caught:
                    M.service(directory)
                if allocation is prepared["allocation"]:
                    self.assertIs(caught.exception, boundary)
                    interpreter.assert_called_once_with(prepared["caseEndNs"])
                else:
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("START", "IDENTITY_CHANGED"))
                    interpreter.assert_not_called()
                left.assert_not_called()
                channel.assert_not_called()
                process.assert_not_called()
                native.close.assert_called_once_with()
        markers = {"P2PKIT_CONTEXT_CLOCK_SCHEMA": "2", "P2PKIT_CONTEXT_CLOCK_DOMAIN": DOMAIN}
        bad_markers = [{}, {"P2PKIT_CONTEXT_CLOCK_SCHEMA": "2"}, {"P2PKIT_CONTEXT_CLOCK_DOMAIN": DOMAIN},
                       {**markers, "P2PKIT_CONTEXT_CLOCK_SCHEMA": "1"}, {**markers, "P2PKIT_CONTEXT_CLOCK_SCHEMA": 2},
                       {**markers, "P2PKIT_CONTEXT_CLOCK_DOMAIN": "time.monotonic_ns"}]
        for env in [*bad_markers, markers]:
            with patch.object(M.os, "environ", env), patch.object(M.os, "fstat", side_effect=boundary) as fstat, \
                    patch.object(M, "account") as account, patch.object(M, "Darwin") as native, \
                    patch.object(M.socket, "socket") as channel, patch.object(M, "left") as left:
                with self.assertRaises(M.ExperimentError) as caught:
                    M.producer(11)
                if env is markers:
                    self.assertIs(caught.exception, boundary)
                    fstat.assert_called_once_with(11)
                else:
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("START", "IDENTITY_CHANGED"))
                    fstat.assert_not_called()
                for endpoint in (account, native, channel, left):
                    endpoint.assert_not_called()
        tree = ast.parse(SOURCE.read_text(), feature_version=(3, 9))
        service = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "service")
        updates = [node for node in ast.walk(service) if isinstance(node, ast.Call) and
                   isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and
                   node.func.value.id == "environment" and node.func.attr == "update"]
        self.assertEqual(len(updates), 1)
        self.assertEqual({item.arg: ast.dump(item.value, include_attributes=False) for item in updates[0].keywords},
            {key: ast.dump(ast.parse(value, mode="eval").body, include_attributes=False) for key, value in {
                "P2PKIT_CONTEXT_BINDING": "binding", "P2PKIT_CONTEXT_CASE_END_NS": "str(end_ns)",
                "P2PKIT_CONTEXT_CLOCK_SCHEMA": "str(CLOCK_SCHEMA)", "P2PKIT_CONTEXT_CLOCK_DOMAIN": "CLOCK_DOMAIN"}.items()})
        with self._raw(130 * NS), patch.object(M, "account", side_effect=account_fixture), \
                patch.object(M, "private_directory", return_value=[11, 12]), patch.object(M, "read_file", return_value=SOURCE_BYTES):
            native = types.SimpleNamespace(boot=Mock(return_value=prepared["boot"]))
            self.assertIs(M.validate_prepared(prepared, directory, native, prepared["interpreter"]), prepared)
            for key, changed in (("boot", "OTHER_BOOT"), ("interpreter", {"path": "/different/python"}),
                                 ("source", {**prepared["source"], "tree": "d" * 40})):
                with self.assertRaises(M.ExperimentError) as caught:
                    M.validate_prepared({**prepared, key: changed}, directory, native, prepared["interpreter"])
                self.assertEqual(caught.exception.stage, "SOURCE" if key == "source" else "IDENTITY")

    def test_04_shared_epochs_join_allocation_workers_and_both_upload_guards(self):
        request, github = {"source_sha": SHA, "source_tree": TREE}, github_fixture()
        with self._raw(100 * NS) as (clock, time_data, _read):
            allocation = inline_allocation(inline_reader(time_data)["shared_raw_ns"](), EPOCH)
            clock["ns"] = 120 * NS
            context = M.Context()
            context.job_end = M.validate_allocation(allocation, request, github, M.shared_raw_ns(), time_data.time_ns())
            context.step_end, context.policy_end = context.started + 720 * NS, 10000 * NS
            case_end = context.limit(40)
            self.assertEqual((context.started, case_end, context.job_end), (120 * NS, 160 * NS, 1540 * NS))
            clock["ns"] = 130 * NS  # Synthetic D; its process-local epoch is irrelevant.
            self.assertEqual(M.left(case_end, "START"), 30)
            clock["ns"] = 135 * NS  # Synthetic P, actual negative-probe timestamp code.
            observation = {}
            with patch.object(M.socket, "socket") as channel, patch.object(M, "interface_ipv4") as interface:
                probe = M.native_probe("N2", None, case_end, observation=observation)
                self.assertIs(M.validate_probe_observation(observation, probe, "N2", case_end), observation)
                channel.assert_not_called()
                interface.assert_not_called()
            self.assertEqual((observation["startedMonotonicNs"], observation["finishedMonotonicNs"]), (135 * NS, 135 * NS))
            # Counterfactual local epochs reproduce the arithmetic defect as DATA,
            # not a claim about the installed interpreter or failed hosted run.
            for local_epoch in (7 * NS, 999999 * NS):
                with self.assertRaises(M.ExperimentError):
                    M.validate_allocation(allocation, request, github, local_epoch, EPOCH + 35 * NS)
            parent, identity = Path("/synthetic/operation"), [11, 12]
            seal = dict(schema=1, scope=M.SCOPE, outcome="SUCCESS", github=github, source=prepared_fixture()["source"],
                        allocation=allocation, operationIdentity=identity, account=account_fixture(),
                        policySha256=M.POLICY_SHA256, policyExpires=M.POLICY_EXPIRES, evidenceSha256="d" * 64,
                        exportReturnedMonotonicNs=140 * NS, stepStartedMonotonicNs=context.started,
                        stepEndMonotonicNs=context.step_end, jobEndMonotonicNs=context.job_end,
                        uploadEndMonotonicNs=560 * NS, encrypted={"syntheticPin": "NO_CIPHERTEXT"})
            seal_hash = M.digest(M.encoded(seal))
            output_raw = ("outcome=SUCCESS\nsuccessSha256=" + seal_hash + "\n").encode("ascii")
            command = dict(path="/synthetic/original-command", stat=[0] * 6 + [len(output_raw), 0, 0],
                           sha256=M.digest(output_raw), closed=True)
            step = dict(schema=1, scope=M.SCOPE, sealSha256=seal_hash, commandFile=command,
                        outputCloseReturned=True, intendedExitCode=0, returnedMonotonicNs=140 * NS)
            memory = {parent / "allocation.json": M.encoded(allocation), parent / "export-return.json": M.encoded(seal),
                      parent / "step-return.json": M.encoded(step), ROOT / M.POLICY_PATH: b"SYNTHETIC_POLICY_DATA"}
            writes = []
            def write(path, raw):
                self.assertNotIn(path, memory)
                writes.append(path.name)
                memory[path] = raw
            env = dict(P2PKIT_CONTEXT_STEP_OUTCOME="success", P2PKIT_CONTEXT_SUCCESS_SHA256=seal_hash,
                       P2PKIT_CONTEXT_CLOSED_FAILURE_SHA256="")
            output = types.SimpleNamespace(emit=Mock(return_value={"closed": True}), close=Mock())
            with patch.object(M.os, "environ", env), patch.object(M, "original_request", return_value=(request, github)), \
                    patch.object(M, "operation_paths", return_value=(parent, identity)), \
                    patch.object(M, "read_file", side_effect=lambda path, *_args: memory[path]), \
                    patch.object(M, "account", side_effect=account_fixture), \
                    patch.object(M, "source_snapshot", return_value=seal["source"]), \
                    patch.object(M, "child_environment", return_value={}), patch.object(M, "validate_policy"), \
                    patch.object(M, "output_snapshot", return_value=seal["encrypted"]), \
                    patch.object(M, "CommandFile", return_value=output), patch.object(M, "write_new", side_effect=write), \
                    patch.object(M, "load_module") as loader, patch.object(M, "finish_export") as exporter:
                clock["ns"] = 150 * NS
                self.assertEqual(M.upload_guard(), 0)
                output.emit.assert_called_once_with({"uploadAllowed": seal_hash})
                output.close.assert_called_once_with()
                env.update(P2PKIT_CONTEXT_UPLOAD_ALLOWED=seal_hash, P2PKIT_CONTEXT_UPLOAD_OUTCOME="success",
                           P2PKIT_CONTEXT_ARTIFACT_ID="456", P2PKIT_CONTEXT_ARTIFACT_DIGEST="f" * 64)
                clock["ns"] = 160 * NS
                self.assertEqual(M.upload_guard(after=True), 0)
                loader.assert_not_called()
                exporter.assert_not_called()
            self.assertEqual(writes, ["before-upload.json", "after-upload.json"])
            self.assertEqual([M.parsed(memory[parent / name])["returnedMonotonicNs"] for name in writes], [150 * NS, 160 * NS])
            self.assertTrue(M.parsed(memory[parent / "after-upload.json"])["remoteReadbackRequired"])
            with self.assertRaises(M.ExperimentError):
                M.validate_seal(seal, github, allocation, identity, 560 * NS)
            clock["ns"] = 830 * NS
            self.assertEqual(context.limit(40), 840 * NS)  # Never renew the original step/job interval.
            clock["ns"] = 840 * NS
            with self.assertRaises(M.ExperimentError):
                M.left(context.step_end, "FREEZE")

    def test_05_exact_source_inverse_all_33_plus_3_calls_and_mutation_containment(self):
        source, workflow = SOURCE.read_text(encoding="utf-8"), WORKFLOW.read_text(encoding="utf-8")
        # Preimages are byte/AST evidence only. Never compile/execute them.
        self.assertEqual(hashlib.sha256(CLOCK.restore_runtime(source).encode()).hexdigest(), CLOCK.BASE_RUNTIME_SHA256)
        self.assertEqual(hashlib.sha256(CLOCK.restore_workflow(workflow).encode()).hexdigest(), CLOCK.BASE_WORKFLOW_SHA256)
        legacy = (ROOT / "scripts/tests/hosted-darwin-context-experiment-test.py").read_text(encoding="utf-8")
        self.assertEqual(hashlib.sha256(CLOCK.restore_experiment_test(legacy).encode()).hexdigest(), CLOCK.BASE_EXPERIMENT_TEST_SHA256)
        tree, roster = ast.parse(source, feature_version=(3, 9)), {}
        def inspect(node, owners=()):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                owners += (node.name,)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "shared_raw_ns":
                    self.assertFalse(node.args or node.keywords)
                    name = ".".join(owners)
                    roster[name] = roster.get(name, 0) + 1
                if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == "time":
                    self.assertNotIn(node.func.attr, {"monotonic", "monotonic_ns", "perf_counter", "perf_counter_ns"})
            for child in ast.iter_child_nodes(node):
                inspect(child, owners)
        inspect(tree)
        self.assertEqual(roster, {"left": 1, "capture_fixed": 1, "Darwin.watch": 3, "Darwin.signal": 2,
            "native_probe": 7, "Admin._run": 2, "service": 2, "Context.__init__": 1, "Context.limit": 1,
            "prepare": 2, "perform_case": 4, "close_sentinel": 1, "run_cases": 1, "finish_export": 2, "upload_guard": 3})
        roster.clear()
        inspect(inline_tree())
        self.assertEqual(roster, {"": 3})
        self.assertEqual((M.CLOCK_SCHEMA, M.CLOCK_DOMAIN, M.UINT64), (2, DOMAIN, UINT64))
        self.assertEqual((M.JOB_SECONDS, M.STEP_SECONDS, M.PREPARE_SECONDS, M.NATIVE_SECONDS, M.CASE_SECONDS,
                          M.ABORT_SECONDS, M.FREEZE_SECONDS, M.EXPORT_SECONDS, M.UPLOAD_SECONDS, M.ADMIN_SECONDS),
                         (1440, 720, 120, 180, 40, 120, 60, 120, 420, 10))
        mutations = (
            (source, CLOCK.restore_runtime, 'CLOCK_SCHEMA = 2', 'CLOCK_SCHEMA = 1'),
            (source, CLOCK.restore_runtime, DOMAIN, 'darwin.clock_gettime_ns(CLOCK_MONOTONIC)'),
            (source, CLOCK.restore_runtime, '(end_ns - shared_raw_ns())', '(end_ns - time.monotonic_ns())'),
            (source, CLOCK.restore_runtime, 'type(value) is int and 0 <= value <= UINT64', 'isinstance(value, int)'),
            (source, CLOCK.restore_runtime, 'validate_allocation_clock(prepared.get("allocation"), "START")', 'pass'),
            (source, CLOCK.restore_runtime, 'os.environ.get("P2PKIT_CONTEXT_CLOCK_SCHEMA") == str(CLOCK_SCHEMA)', 'True'),
            (source, CLOCK.restore_runtime, 'CASE_SECONDS = 120, 180, 40', 'CASE_SECONDS = 120, 180, 41'),
            (source, CLOCK.restore_runtime, 'native.boot() == value["boot"]', 'True'),
            (source, CLOCK.restore_runtime, 'context.recipient_original', 'context.changed_recipient_original'),
            (workflow, CLOCK.restore_workflow, DOMAIN, 'time.monotonic_ns'),
            (workflow, CLOCK.restore_workflow, 'shared_raw_ns() - started < 60', 'shared_raw_ns() - started < 61'),
            (workflow, CLOCK.restore_workflow, 'timeout-minutes: 24', 'timeout-minutes: 25'),
            (workflow, CLOCK.restore_workflow, 'contents: read', 'contents: write'),
            (legacy, CLOCK.restore_experiment_test, 'return_value=M.NS)', 'return_value=2 * M.NS)'),
            (legacy, CLOCK.restore_experiment_test, 'self.assertEqual(len(calls), 42)', 'self.assertEqual(len(calls), 41)'),
        )
        for text, inverse, before, after in mutations:
            changed = text.replace(before, after, 1)
            self.assertNotEqual(changed, text)
            with self.assertRaises(AssertionError):
                inverse(changed)

    def test_06_clock_refusal_cannot_reach_native_admin_export_or_upload_outputs(self):
        for command in ("experiment", "before-upload", "after-upload"):
            stage = "PREPARE" if command == "experiment" else "UPLOAD"
            cases = (("linux", NS, None, "PREPARE|UNSUPPORTED|NONE", 0),
                     ("darwin", True, None, "PREPARE|BOUND|NONE", 1),
                     ("darwin", NS, RuntimeError(CANARY), stage + "|REFUSED|UNKNOWN", 1),
                     ("darwin", NS, OSError(M.errno.EINVAL, CANARY), stage + "|RETURN_FAILED|EINVAL", 1))
            for platform_name, value, error, expected, calls in cases:
                read, fallback = Mock(return_value=value, side_effect=error), Mock(side_effect=AssertionError("NO_CLOCK_FALLBACK"))
                clock = types.SimpleNamespace(CLOCK_MONOTONIC_RAW=RAW_KIND, clock_gettime_ns=read,
                                             monotonic_ns=fallback, monotonic=fallback, time_ns=fallback)
                output = io.StringIO()
                with contextlib.ExitStack() as stack:
                    for manager in (patch.object(M, "time", clock), patch.object(M.sys, "platform", platform_name),
                                    patch.object(M.sys, "argv", ["SYNTHETIC_ENTRY", command]),
                                    patch.object(M.os, "environ", {}), patch.object(M.os, "umask"),
                                    contextlib.redirect_stdout(output)):
                        stack.enter_context(manager)
                    endpoints = [stack.enter_context(patch.object(M, name)) for name in (
                        "original_request", "operation_paths", "CommandFile", "Darwin", "Admin", "load_module",
                        "write_new", "finish_export", "run_cases", "source_snapshot", "checked_interpreter")]
                    self.assertEqual(M.main(), 2)
                    for endpoint in endpoints:
                        endpoint.assert_not_called()
                self.assertEqual(read.call_count, calls)
                fallback.assert_not_called()
                self.assertEqual(output.getvalue(), "P2PKIT_CONTEXT_FAILURE|" + expected + "\n")
                self.assertNotIn(CANARY, output.getvalue())
        class Parent:
            def iterdir(self):
                return [Path("allocation.json")]
            def __truediv__(self, name):
                return Path("/synthetic/operation") / name
        parent, request, github = Parent(), {"source_sha": SHA, "source_tree": TREE}, github_fixture()
        for allocation in ({**allocation_fixture(), "schema": 1}, {**allocation_fixture(), "clockDomain": "time.monotonic_ns"}):
            for operation in (M.prepare, M.upload_guard):
                with self._raw(120 * NS), contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(M, "original_request", return_value=(request, github)))
                    stack.enter_context(patch.object(M, "operation_paths", return_value=(parent, [11, 12])))
                    stack.enter_context(patch.object(M, "account", side_effect=account_fixture))
                    read = stack.enter_context(patch.object(M, "read_file", return_value=M.encoded(allocation)))
                    endpoints = [stack.enter_context(patch.object(M, name)) for name in (
                        "CommandFile", "Darwin", "Admin", "load_module", "write_new", "finish_export", "source_snapshot")]
                    with self.assertRaises(M.ExperimentError) as caught:
                        operation()
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("PREPARE", "IDENTITY_CHANGED"))
                    read.assert_called_once_with(parent / "allocation.json")
                    for endpoint in endpoints:
                        endpoint.assert_not_called()


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(ClockControls)
    if suite.countTestCases() != 6:
        raise SystemExit("FIXED_SIX_CLOCK_METHODS_REQUIRED")
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
