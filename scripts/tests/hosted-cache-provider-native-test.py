#!/usr/bin/env python3
"""Bounded native-helper composition controls, not native/hosted admission.

Only Owner+LIMIT are AST-selected from the maintained controller. The complete
controller/initial-recipient receiver is never imported. Tiny private POSIX
files and the materializer are real; original host/admission/graph/clock/bundle
inputs and the successful provider reader are explicit models. No child starts.
"""
from __future__ import annotations

import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import hosted_cache_provider_native as N

L = N.L
spec = importlib.util.spec_from_file_location("native_provider_plan_models",
    SCRIPTS / "tests/hosted-cache-provider-contract-test.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)
tree = ast.parse((SCRIPTS / "run-hosted-cache-bootstrap.py").read_text())
selected = [node for node in tree.body if (isinstance(node, ast.ClassDef) and node.name == "Owner") or
            (isinstance(node, ast.Assign) and len(node.targets) == 1 and
             isinstance(node.targets[0], ast.Name) and node.targets[0].id == "LIMIT")]
assert len(selected) == 2
owner_globals = {"require": L.require, "math": math, "time": time, "os": os, "query": L.files,
    "posix": L.files.posix_files, "windows": L.files.windows_files, "QUARANTINE": [],
    "origin": NS(clocks=L.clocks, OriginError=L.ProviderLaunchError, encoded=L.files.encoded),
    "diagnostics": NS(_exception_detail=lambda error: {"retirementUnknown": False, "model": type(error).__name__})}
exec(compile(ast.Module(body=selected, type_ignores=[]), "selected-Owner", "exec"), owner_globals)
Owner = owner_globals["Owner"]
CONTRACT = L.cache.bootstrap_provider_contract
NS_SECOND = L.clocks.NS


class FenceControls(unittest.TestCase):
    def setUp(self):
        self.clock = L.clocks.ClockIdentity("linux-x64", L.clocks.DOMAINS["linux-x64"], NS_SECOND)
        self.raw, self.local, self.calls = 200 * NS_SECOND, 1000.0, 0
        self.addCleanup(patch.stopall)
        patch.object(L.clocks, "observe", lambda: L.clocks.Reading(self.clock, self.raw)).start()
        patch.object(time, "monotonic", lambda: self.local).start()

    def callback(self):
        self.calls += 1

    def fence(self, *, readback=False):
        return N._Fence(L.clocks.Reading(self.clock, self.raw), 100 * NS_SECOND, 280 * NS_SECOND,
                        self.callback, readback_only=readback)

    def test_preparation_stops_at_original_final45(self):
        fence = self.fence()
        self.assertEqual(fence.now(), self.raw)
        self.raw = 235 * NS_SECOND
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
            fence.now()

    def test_readback_owner_ordinary_bind_and_end_work_inside_final45(self):
        self.raw = 240 * NS_SECOND
        first = L.clocks.Reading(self.clock, self.raw)
        owner = Owner(self.local + 45, first=first, cancelled=self.callback)
        fence = self.fence(readback=True)
        owner.bind(fence, work_limit=280 * NS_SECOND, final_limit=280 * NS_SECOND)
        self.assertLess(owner.end(), 1040)
        self.assertGreater(self.calls, 0)
        owner.close()
        self.assertTrue(owner.closed)
        self.assertIsNone(owner.original)

    def test_readback_original_end_is_exclusive(self):
        fence = self.fence(readback=True)
        self.raw = 280 * NS_SECOND
        with self.assertRaisesRegex(L.ProviderLaunchError, "EXPIRED"):
            fence.now()

    def test_readback_still_checks_cancellation(self):
        def cancelled():
            raise KeyboardInterrupt("MODELED_CANCELLATION")
        fence = N._Fence(L.clocks.Reading(self.clock, self.raw), 100 * NS_SECOND, 280 * NS_SECOND,
                         cancelled, readback_only=True)
        with self.assertRaises(KeyboardInterrupt):
            fence.now()

    def test_callback_crossing_work_end_is_postchecked(self):
        def crossing():
            self.calls += 1
            if self.calls == 2:
                self.raw = 235 * NS_SECOND
        fence = N._Fence(L.clocks.Reading(self.clock, self.raw), 100 * NS_SECOND, 280 * NS_SECOND, crossing)
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
            fence.now()
        self.assertEqual(self.calls, 2)

    def test_local_end_is_not_renewed_when_raw_stalls(self):
        fence = self.fence(readback=True)
        end = fence.local_end
        self.local = end
        with self.assertRaisesRegex(L.ProviderLaunchError, "EXPIRED"):
            fence.now()

    def test_raw_regression_is_rejected(self):
        fence = self.fence(readback=True)
        self.raw -= 1
        with self.assertRaisesRegex(L.clocks.ClockError, "JOB_CLOCK_BACKWARDS"):
            fence.now()

    def test_smaller_caller_limit_is_preserved(self):
        fence = self.fence(readback=True)
        self.assertLessEqual(fence.deadline(45, limit=210 * NS_SECOND), self.local + 10)
        self.raw = 210 * NS_SECOND
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
            fence.now(limit=self.raw)

    def test_bound_work_cap_cannot_be_changed(self):
        fence = self.fence()
        fence.work_end = fence.hard_end
        with self.assertRaisesRegex(L.ProviderLaunchError, "FENCE_CHANGED"):
            fence.now()

    def test_readback_does_not_ignore_retained_owner_failure(self):
        first = L.clocks.Reading(self.clock, self.raw)
        owner = Owner(self.local + 45, first=first)
        fence = self.fence(readback=True)
        owner.bind(fence, work_limit=280 * NS_SECOND, final_limit=280 * NS_SECOND)
        original = OSError("MODELED_ORIGINAL")
        owner.error("model", original)
        with self.assertRaisesRegex(L.ProviderLaunchError, "OWNER_FAILED"):
            owner.end()
        owner.close()
        self.assertIs(owner.original, original)


class Fixture:
    def __init__(self, case, phase="save"):
        self.case, self.phase = case, phase
        self.plan_case = C.ProviderContract()
        self.plan_case.setUp()
        case.addCleanup(self.plan_case.doCleanups)
        self.plan = self.plan_case.plan
        self.tmp = tempfile.TemporaryDirectory(prefix="provider-native-model-")
        case.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.path.chmod(0o700)
        self.original_path = self.path / "originals"
        self.prepared_path = self.path / ("originals-save" if phase == "save" else "originals-probe")
        self.prepared_path.mkdir(mode=0o700)
        self.identity = [self.prepared_path.stat().st_dev, self.prepared_path.stat().st_ino]
        self.clock = L.clocks.ClockIdentity("linux-x64", L.clocks.DOMAINS["linux-x64"], NS_SECOND)
        self.raw = 160 * NS_SECOND
        self.bundle = b"MODEL_PUBLIC_BUNDLE_NOT_EXECUTABLE\n"
        self.prepared = {"scope": "BOOTSTRAP_" + ("SAVE" if phase == "save" else "PROBE") +
            "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1", "source": deepcopy(self.plan["source"]),
            "github": deepcopy(self.plan["github"]), "plan": deepcopy(self.plan),
            "planSha256": hashlib.sha256(L.files.encoded(self.plan)).hexdigest(),
            "providerRequest": CONTRACT(self.plan, phase)["request"], "directory": str(self.prepared_path),
            "directoryIdentity": self.identity,
            "clock": {"role": self.clock.role, "domain": self.clock.domain, "ticksPerSecond": NS_SECOND},
            "providerWindow": {"issuedNs": 100 * NS_SECOND, "hardEndNs": 280 * NS_SECOND,
                               "actualProviderStart": "NOT_OBSERVED"},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        self.name = "save-preparation.json" if phase == "save" else "probe-preparation.json"
        self.claims = {name: "success" if name.endswith("OUTCOME") else "1" * 64
                      for name in N._BASE_CLAIMS + (N._LOOKUP_CLAIMS if phase == "lookup" else ())}
        self.digest = None
        self.write_preparation()
        self.node, self.tool_path = "/modeled-tools/node", "/modeled-tools:/usr/bin"
        self.owners, self.events = [], []
        self.bootstrap = NS(Owner=self.owner, QUARANTINE=owner_globals["QUARANTINE"],
            query=NS(QUARANTINE=[]), diagnostics=NS(_QUARANTINE=[]),
            origin=NS(wire=NS(TOKEN_ENV="P2PKIT_ACTIONS_READ_TOKEN"), encoded=L.files.encoded,
                      parse=lambda raw: json.loads(raw), clock_value=lambda clock: {
                          "role": clock.role, "domain": clock.domain, "ticksPerSecond": clock.ticks_per_second}),
            host_inputs=lambda role: ("EXPLICIT_OFFLINE_MODEL", self.original_path, b"MODEL_EVENT"),
            child_environment=lambda path: self.events.append("environment"), cancellation=self.cancel)
        case.addCleanup(self.close)

    def write_preparation(self):
        raw = L.files.encoded(self.prepared)
        target = self.prepared_path / self.name
        target.write_bytes(raw)
        target.chmod(0o600)
        self.digest = hashlib.sha256(raw).hexdigest()
        self.claims[("SAVE" if self.phase == "save" else "PROBE") + "_PREPARATION_SHA256"] = self.digest
        return raw

    def owner(self, *args, **kwargs):
        result = Owner(*args, **kwargs)
        self.owners.append(result)
        return result

    def cancel(self, cancelled):
        if cancelled:
            raise KeyboardInterrupt("MODELED_CANCELLATION")

    def close(self):
        # Dispose only these tiny fixture files; never reinterpret UNKNOWN as
        # candidate recovery, native retirement or permission to reuse bytes.
        with patch.object(L.clocks, "observe", lambda: L.clocks.Reading(self.clock, self.raw)):
            for owner in self.owners:
                try:
                    owner.close()
                except BaseException:
                    pass
                for row in reversed(owner.resources):
                    if not row["closed"]:
                        row["owner"].close()
        owner_globals["QUARANTINE"].clear()

    def contract(self, plan, phase):
        result = CONTRACT(plan, phase)
        result["bundle"] = {**result["bundle"], "bytes": len(self.bundle),
                            "sha256": hashlib.sha256(self.bundle).hexdigest()}
        return result

    def graph(self, *args):
        self.case.assertEqual(args[2:4], (self.phase, self.claims))
        self.events.append("modeled-native-admission-and-graph")
        return self.plan, lambda: self.events.append("modeled-final-readmission-and-originals")

    def run(self, operation, *, environment=None, graph=None, **kwargs):
        env = {"RUNNER_NAME": "OFFLINE_MODEL_NOT_HOSTED", **{
            "P2PKIT_BOOTSTRAP_" + key: value for key, value in self.claims.items()}}
        env.update(environment or {})
        with patch.dict(os.environ, env, clear=True), patch.object(N, "B", self.bootstrap), \
                patch.object(N, "_graph", self.graph if graph is None else graph), \
                patch.object(L.clocks, "observe", lambda: L.clocks.Reading(self.clock, self.raw)), \
                patch.object(L.cache, "bootstrap_provider_contract", self.contract):
            return N.operate(operation, self.phase, [], **kwargs)

    def prepare(self):
        path = self.prepared_path / N.SOURCE_NAME
        path.write_bytes(self.bundle)
        path.chmod(0o600)
        return self.run("prepare", node=self.node, tool_path=self.tool_path)[0]


class NativeControls(unittest.TestCase):
    def setUp(self):
        self.model = Fixture(self)

    def test_window_reads_old_issuance_and_closes_without_admission(self):
        result, fence, cap = self.model.run("window")
        self.assertEqual(result["providerAdmission"], "NOT_ESTABLISHED")
        self.assertEqual(result["originalHelperReturn"], "PENDING")
        self.assertEqual(result["ownerClose"], "KNOWN_RESOURCE_CLOSE_ONLY")
        self.assertEqual(result["issuedNs"], str(100 * NS_SECOND))
        self.assertEqual(result["hardEndNs"], str(280 * NS_SECOND))
        self.assertEqual(cap, 235 * NS_SECOND)
        self.assertNotIn("modeled-native-admission-and-graph", self.model.events)
        self.assertTrue(all(owner.closed and not owner.unknown for owner in self.model.owners))
        self.assertFalse((self.model.prepared_path / N.PREPARED_NAME).exists())
        self.assertEqual(fence.hard_end, 280 * NS_SECOND)

    def test_window_wrong_preparation_hash_refuses_and_closes(self):
        self.model.claims["SAVE_PREPARATION_SHA256"] = "2" * 64
        with self.assertRaisesRegex(L.ProviderLaunchError, "PREPARATION_HASH"):
            self.model.run("window")
        self.assertTrue(self.model.owners[-1].closed)

    def test_window_cannot_renew_expired_original_interval(self):
        self.model.raw = 280 * NS_SECOND
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
            self.model.run("window")

    def test_descriptor_binds_native_directory_and_clock(self):
        for name, value in (("directoryIdentity", [0, 1]), ("directory", "/different"),
                            ("clock", {**self.model.prepared["clock"], "ticksPerSecond": 1})):
            with self.subTest(field=name):
                old = self.model.prepared[name]
                self.model.prepared[name] = value
                self.model.write_preparation()
                with self.assertRaisesRegex(L.ProviderLaunchError, "DESCRIPTOR"):
                    self.model.run("window")
                self.model.prepared[name] = old

    def test_descriptor_rejects_extended_provider180(self):
        self.model.prepared["providerWindow"]["hardEndNs"] += 1
        self.model.write_preparation()
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
            self.model.run("window")

    def test_descriptor_keeps_full_width_qpc_frequency(self):
        # Data-only Windows descriptor validation, not Windows files or a clock
        # observation. In particular this integer never traverses float/Number.
        frequency = 2 ** 63 - 1
        first = L.clocks.Reading(L.clocks.ClockIdentity("windows-x64", L.clocks.DOMAINS["windows-x64"], frequency),
                                 self.model.raw)
        value = deepcopy(self.model.prepared)
        value["clock"] = {"role": first.clock.role, "domain": first.clock.domain, "ticksPerSecond": frequency}
        value["plan"]["role"] = first.clock.role
        raw = L.files.encoded(value)
        # Only contract return is modeled: closed plan shape/native role checks
        # are independently covered by the maintained provider-contract suite.
        with patch.object(L.cache, "bootstrap_provider_contract", lambda *_: {"request": value["providerRequest"]}):
            result, _, _, _ = N._descriptor(raw, hashlib.sha256(raw).hexdigest(), "save", first,
                                           NS(path=self.model.prepared_path, identity=self.model.identity))
        self.assertEqual(result["clock"]["ticksPerSecond"], frequency)

    def test_failed_predecessor_refuses_before_owner_allocation(self):
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_CLAIMS"):
            self.model.run("window", environment={"P2PKIT_BOOTSTRAP_PRODUCER_OUTCOME": "failure"})
        self.assertEqual(self.model.owners, [])

    def test_runtime_credentials_are_refused_before_allocation(self):
        for name in (*L.environment.SERVICE_FIELDS, "GH_TOKEN", "GITHUB_TOKEN", "P2PKIT_ACTIONS_READ_TOKEN"):
            with self.subTest(field=name), self.assertRaisesRegex(L.ProviderLaunchError, "CREDENTIAL_FREE"):
                self.model.run("window", environment={name: "EXPLICIT_MODEL_NOT_A_CREDENTIAL"})
        self.assertEqual(self.model.owners, [])

    def test_prepare_real_tiny_materialization_is_private_and_pending(self):
        result = self.model.prepare()
        self.assertEqual((self.model.prepared_path / "provider/provider.cjs").read_bytes(), self.model.bundle)
        self.assertEqual(result["providerExecution"], "NOT_PERFORMED")
        self.assertEqual(result["enclosingActionReturn"], "NOT_OBSERVED")
        self.assertEqual(result["ownerClose"], "KNOWN_RESOURCE_CLOSE_ONLY")
        self.assertLess(len(L.files.encoded(result)), 16384)
        retained = (self.model.prepared_path / N.PREPARED_NAME).read_bytes()
        self.assertEqual(hashlib.sha256(retained).hexdigest(), result["preparedSha256"])
        self.assertEqual(self.model.events.count("modeled-native-admission-and-graph"), 1)
        self.assertEqual(self.model.events.count("modeled-final-readmission-and-originals"), 1)
        context, _ = N.readback.outer._context(result["request"].encode("ascii"))
        self.assertEqual(int(context["workerCutoffNs"]), 250 * NS_SECOND)
        self.assertEqual(int(context["hardEndNs"]), 280 * NS_SECOND)

    def test_prepare_cannot_skip_native_admission_failure(self):
        original = OSError("MODELED_ADMISSION_DENIAL")
        def denied(*_args):
            raise original
        with self.assertRaises(OSError) as raised:
            self.model.run("prepare", graph=denied, node=self.model.node, tool_path=self.model.tool_path)
        self.assertIs(raised.exception, original)
        self.assertFalse((self.model.prepared_path / "provider").exists())
        self.assertTrue(self.model.owners[-1].closed)

    def test_retained_original_error_precedes_secondary_failure(self):
        original = OSError("MODELED_ORIGINAL_CLOSE_FAILURE")
        def denied(owner, *_args):
            owner.error("modeled-first", original, unknown=True)
            raise RuntimeError("MODELED_SECONDARY")
        with self.assertRaises(OSError) as raised:
            self.model.run("prepare", graph=denied, node=self.model.node, tool_path=self.model.tool_path)
        self.assertIs(raised.exception, original)
        self.assertIs(self.model.owners[-1].original, original)
        self.assertTrue(self.model.owners[-1].unknown)
        self.assertTrue(any(value is self.model.owners[-1] for value in owner_globals["QUARANTINE"]))

    def test_known_close_error_prevents_helper_success(self):
        factory = self.model.bootstrap.Owner
        original = OSError("MODELED_CLOSE_FAILURE")
        def owner(*args, **kwargs):
            result = factory(*args, **kwargs)
            close = result.close
            def failed_close():
                close()
                result.error("modeled-close", original)
            result.close = failed_close
            return result
        self.model.bootstrap.Owner = owner
        with self.assertRaises(OSError) as raised:
            self.model.run("window")
        self.assertIs(raised.exception, original)

    def test_final_preparation_readback_detects_change(self):
        def graph(*_args):
            return self.model.plan, lambda: (self.model.prepared_path / self.model.name).write_bytes(b"{}")
        self.model.graph = graph
        with self.assertRaisesRegex(L.ProviderLaunchError, "FINAL_PREPARATION_CHANGED"):
            self.model.prepare()

    def test_changed_original_claims_during_preparation_refuse(self):
        def graph(*args):
            result = self.model.graph(*args)
            os.environ["P2PKIT_BOOTSTRAP_HANDOFF_SHA256"] = "9" * 64
            return result
        with self.assertRaisesRegex(L.ProviderLaunchError, "CREDENTIAL_FREE_CONTEXT"):
            self.model.run("prepare", graph=graph, node=self.model.node, tool_path=self.model.tool_path)

    def test_readback_runs_in_final45_and_preserves_python_spelling(self):
        result = self.model.prepare()
        self.model.raw = 240 * NS_SECOND
        python = "/modeled-tools/python3"  # No such executable is opened/run.
        calls = []
        def reader(owner, directory, request, acknowledgement, code, **kwargs):
            calls.append((owner, directory, request, acknowledgement, code, kwargs))
            owner.end()
            return NS(worker_request=b"MODEL_WORKER_REQUEST", provider=NS(outputs={}), checked_ns=self.model.raw)
        with patch.object(N.readback, "read_success", reader), patch.object(sys, "executable", python):
            output, _, cap = self.model.run("readback", prepared_sha256=result["preparedSha256"],
                acknowledgement=b"MODEL_ORIGINAL_ACK", minimum_ns=239 * NS_SECOND)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][-1]["python"], python)
        self.assertEqual(calls[0][4], 0)
        self.assertEqual(cap, 280 * NS_SECOND)
        self.assertEqual(output["providerAcceptance"], "NOT_ESTABLISHED")
        self.assertEqual(output["ownerClose"], "KNOWN_RESOURCE_CLOSE_ONLY")
        self.assertTrue((self.model.prepared_path / N.READBACK_NAME).is_file())
        retained = (self.model.prepared_path / N.READBACK_NAME).read_bytes()
        receipt = json.loads(retained)
        self.assertEqual(receipt["acknowledgement"].encode("ascii"), b"MODEL_ORIGINAL_ACK")
        self.assertEqual(receipt["acknowledgementSha256"], hashlib.sha256(b"MODEL_ORIGINAL_ACK").hexdigest())
        self.assertEqual(receipt["python"], python)
        self.assertEqual(hashlib.sha256(retained).hexdigest(), output["readbackSha256"])
        self.assertNotIn("acknowledgement", output)
        self.assertNotIn("python", output)

    def test_readback_rejects_changed_prepared_hash_before_provider_read(self):
        self.model.prepare()
        self.model.raw = 240 * NS_SECOND
        with patch.object(N.readback, "read_success") as reader:
            with self.assertRaisesRegex(L.ProviderLaunchError, "PREPARED_HASH"):
                self.model.run("readback", prepared_sha256="a" * 64,
                               acknowledgement=b"MODEL_ACK", minimum_ns=239 * NS_SECOND)
            reader.assert_not_called()

    def test_readback_rejects_high_water_below_original_request(self):
        result = self.model.prepare()
        self.model.raw = 240 * NS_SECOND
        with patch.object(N.readback, "read_success") as reader:
            with self.assertRaisesRegex(L.ProviderLaunchError, "READBACK_CONTEXT"):
                self.model.run("readback", prepared_sha256=result["preparedSha256"],
                               acknowledgement=b"MODEL_ACK", minimum_ns=159 * NS_SECOND)
            reader.assert_not_called()

    def test_readback_failed_reader_does_not_create_success_record(self):
        result = self.model.prepare()
        self.model.raw = 240 * NS_SECOND
        with patch.object(N.readback, "read_success", side_effect=OSError("MODELED_READER_DENIAL")):
            with self.assertRaises(OSError):
                self.model.run("readback", prepared_sha256=result["preparedSha256"],
                               acknowledgement=b"MODEL_FAILED_ACK", minimum_ns=239 * NS_SECOND)
        self.assertFalse((self.model.prepared_path / N.READBACK_NAME).exists())

    def test_lookup_uses_probe_preparation_and_requires_save_originals(self):
        model = Fixture(self, "lookup")
        result = model.prepare()
        request, _ = N.readback.outer._context(result["request"].encode("ascii"))
        self.assertEqual(request["phase"], "lookup")
        self.assertEqual(result["originalClaims"]["SAVE_OUTCOME"], "success")
        self.assertEqual(result["originalClaims"]["SAVE_READBACK_SHA256"], model.claims["SAVE_READBACK_SHA256"])
        self.assertEqual(result["originalClaims"]["AFTER_SAVE_SHA256"], model.claims["AFTER_SAVE_SHA256"])
        self.assertTrue(model.prepared["providerRequest"]["lookupOnly"])
        model.claims["SAVE_OUTCOME"] = "failure"
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_CLAIMS"):
            model.run("window")

    def test_main_refuses_this_nonhosted_process_before_bootstrap_import(self):
        import io
        with patch.dict(os.environ, {}, clear=True), patch.object(N, "_bootstrap") as bootstrap, \
                patch.object(sys, "stderr", io.StringIO()) as error:
            self.assertEqual(N.main(), 125)
            self.assertEqual(error.getvalue(), "CACHE_PROVIDER_NATIVE_NOT_ACCEPTED\n")
            bootstrap.assert_not_called()


if __name__ == "__main__":
    unittest.main()
