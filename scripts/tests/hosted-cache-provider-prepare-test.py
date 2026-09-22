#!/usr/bin/env python3
"""Tiny real POSIX materialization controls; no provider/hosted qualification.

Only Owner+LIMIT are selected from the maintained controller. Plans, clocks,
step outcomes and bundle metadata are explicit models. No accepted suite runs,
no dependency is downloaded and no provider or native child is started.
"""
from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError
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
import hosted_cache_provider_prepare as P

L, O = P.L, P.O
spec = importlib.util.spec_from_file_location("preparation_plan_models",
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
    "origin": NS(clocks=L.clocks, OriginError=L.ProviderLaunchError),
    "diagnostics": NS(_exception_detail=lambda error: {"retirementUnknown": False, "model": type(error).__name__})}
exec(compile(ast.Module(body=selected, type_ignores=[]), "selected-Owner", "exec"), owner_globals)
Owner = owner_globals["Owner"]
CONTRACT = L.cache.bootstrap_provider_contract


class Fixture:
    def __init__(self, case, phase="save"):
        self.case, self.phase = case, phase
        self.plan_case = C.ProviderContract()
        self.plan_case.setUp()
        case.addCleanup(self.plan_case.doCleanups)
        self.plan = self.plan_case.plan
        self.tmp = tempfile.TemporaryDirectory(prefix="provider-preparation-model-")
        case.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.path.chmod(0o700)
        self.clock = L.clocks.ClockIdentity("linux-x64", L.clocks.DOMAINS["linux-x64"], L.clocks.NS)
        self.raw, self.cut = 160 * L.clocks.NS, 200 * L.clocks.NS
        self.local_end = time.monotonic() + 20
        first = L.clocks.Reading(self.clock, self.raw)
        self.fence = NS(clock=self.clock, now=lambda **kw: self.raw,
                        deadline=lambda *args, **kw: self.local_end)
        self.owner = Owner(self.local_end, self.fence, first=first)
        case.addCleanup(self.close)
        self.directory = self.owner.open(self.path)
        self.bundle = b"MODEL_PROVIDER_BYTES_NOT_EXECUTABLE\n"
        self.prepared = {"scope": "BOOTSTRAP_" + ("SAVE" if phase == "save" else "PROBE") +
            "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1", "source": deepcopy(self.plan["source"]),
            "github": deepcopy(self.plan["github"]), "plan": deepcopy(self.plan),
            "planSha256": hashlib.sha256(L.files.encoded(self.plan)).hexdigest(),
            "providerRequest": CONTRACT(self.plan, phase)["request"],
            "directory": str(self.path), "directoryIdentity": list(self.directory.identity),
            "clock": {"role": self.clock.role, "domain": self.clock.domain,
                      "ticksPerSecond": self.clock.ticks_per_second},
            "providerWindow": {"issuedNs": 100 * L.clocks.NS, "hardEndNs": 280 * L.clocks.NS,
                               "actualProviderStart": "NOT_OBSERVED"},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        self.node, self.tool_path, self.outcome = "/modeled-tools/node", "/modeled-tools:/usr/bin", "success"

    def close(self):
        # Dispose only this fixture's tiny files, never recover candidate UNKNOWN.
        self.raw = 160 * L.clocks.NS
        try:
            self.owner.close()
        except L.ProviderLaunchError:
            if not self.owner.unknown:
                raise
        for row in reversed(self.owner.resources):
            if not row["closed"]:
                row["owner"].close()
        owner_globals["QUARANTINE"].clear()

    def contract(self, plan, phase):
        result = CONTRACT(plan, phase)  # Real closed plan/request checks still run.
        result["bundle"] = {**result["bundle"], "bytes": len(self.bundle),
                            "sha256": hashlib.sha256(self.bundle).hexdigest()}
        return result

    def run(self, *, raw=None, digest=None, bundle=None, contract=True):
        raw = L.files.encoded(self.prepared) if raw is None else raw
        digest = hashlib.sha256(raw).hexdigest() if digest is None else digest
        with patch.object(L.clocks, "observe", lambda: L.clocks.Reading(self.clock, self.raw)), \
                patch.object(L.cache, "bootstrap_provider_contract", self.contract if contract else CONTRACT):
            return P.materialize(self.owner, self.directory, raw, digest, self.outcome,
                phase=self.phase, plan=self.plan, bundle_raw=self.bundle if bundle is None else bundle,
                node=self.node, tool_path=self.tool_path, worker_cutoff_ns=self.cut)


class PreparationControls(unittest.TestCase):
    def setUp(self):
        self.model = Fixture(self)

    def test_save_materializes_actual_private_files_and_exact_request(self):
        model = self.model
        result = model.run()
        request, digest = O._context(result.request)
        self.assertEqual(request["phase"], "save")
        self.assertEqual(request["plan"], model.plan)
        self.assertEqual(request["issuedNs"], str(100 * L.clocks.NS))
        self.assertEqual(request["hardEndNs"], str(280 * L.clocks.NS))
        self.assertEqual(request["workerCutoffNs"], str(model.cut))
        self.assertEqual(request["firstNs"], str(model.owner.first.nanoseconds))
        self.assertEqual(request["frequency"], model.clock.ticks_per_second)
        self.assertEqual(digest, hashlib.sha256(result.request).hexdigest())
        self.assertEqual(result.preparation_sha256, hashlib.sha256(L.files.encoded(model.prepared)).hexdigest())
        self.assertEqual(result.checked_ns, model.raw)
        self.assertEqual({p.name for p in model.path.iterdir()}, {"provider", "provider-home"})
        for name in ("directory", "home"):
            path = Path(request[name])
            info = path.stat()
            self.assertEqual(request[name + "Identity"], [info.st_dev, info.st_ino])
            self.assertEqual(info.st_mode & 0o777, 0o700)
        bundle = Path(request["directory"]) / "provider.cjs"
        self.assertEqual(bundle.read_bytes(), model.bundle)
        self.assertEqual(bundle.stat().st_mode & 0o777, 0o600)
        self.assertEqual(len({request[name] for name in ("job", "outerId", "innerId")}), 3)
        self.assertFalse(model.owner.closed)
        self.assertTrue(all(row["closed"] for row in model.owner.resources if "bundle" in row["label"]))
        self.assertEqual((result.enclosing_owner_close, result.provider_execution, result.provider_acceptance),
                         ("NOT_OBSERVED", "NOT_PERFORMED", "NOT_ESTABLISHED"))
        self.assertNotIn(str(model.path), repr(result))
        with self.assertRaises(FrozenInstanceError):
            result.checked_ns = 1

    def test_lookup_uses_distinct_request_without_restoring_or_running(self):
        model = Fixture(self, "lookup")
        result = model.run()
        request, _ = O._context(result.request)
        self.assertEqual(request["phase"], "lookup")
        self.assertEqual(model.prepared["providerRequest"]["lookupOnly"], True)
        self.assertEqual(model.prepared["providerRequest"]["restoreKeys"], [])
        self.assertEqual(result.provider_execution, "NOT_PERFORMED")

    def test_retained_bindings_are_hashes_of_actual_separate_source_rosters(self):
        result = self.model.run()
        for bindings, names, reader in ((result.bindings, L.worker_source.outer_names("linux-x64"),
                L.worker_source.read_source), (result.clock_bindings, P.clock_source.roster("linux-x64"),
                P.clock_source.read_source)):
            self.assertEqual(tuple(name for name, _ in bindings), names)
            for name, digest in bindings:
                self.assertEqual(digest, hashlib.sha256(reader(SCRIPTS, name)).hexdigest())

    def test_missing_failed_or_boolean_original_outcome_refuses_before_creation(self):
        for value in (None, True, "failure", "cancelled", "skipped", "Success"):
            self.model.outcome = value
            with self.subTest(value=value), self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_STEP"):
                self.model.run()
        self.assertEqual(list(self.model.path.iterdir()), [])

    def test_changed_digest_or_nonbyte_original_refuses_before_creation(self):
        for kwargs in ({"digest": "0" * 64}, {"digest": "A" * 64}, {"raw": "not-bytes", "digest": "0" * 64}):
            with self.subTest(keys=tuple(kwargs)), self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_STEP"):
                self.model.run(**kwargs)
        self.assertEqual(list(self.model.path.iterdir()), [])

    def test_noncanonical_or_wrong_phase_descriptor_refuses(self):
        raw = json.dumps(self.model.prepared).encode()
        with self.assertRaisesRegex(L.ProviderLaunchError, "DESCRIPTOR"):
            self.model.run(raw=raw)
        self.model.phase = "lookup"
        with self.assertRaisesRegex(L.ProviderLaunchError, "DESCRIPTOR"):
            self.model.run()

    def test_authority_or_execution_claim_cannot_be_inserted(self):
        for name, value in (("exportSaveAuthority", True), ("writerReturn", "success"),
                            ("providerExecution", "PERFORMED")):
            with self.subTest(name=name), patch.dict(self.model.prepared, {name: value}), \
                    self.assertRaisesRegex(L.ProviderLaunchError, "DESCRIPTOR"):
                self.model.run()

    def test_plan_request_and_source_links_are_required(self):
        for name, value in (("planSha256", "0" * 64), ("plan", {}), ("providerRequest", {}),
                            ("source", {}), ("github", {})):
            with self.subTest(name=name), patch.dict(self.model.prepared, {name: value}), \
                    self.assertRaisesRegex(L.ProviderLaunchError, "PLAN"):
                self.model.run()

    def test_real_pinned_metadata_refuses_synthetic_bundle_without_download(self):
        with self.assertRaisesRegex(L.ProviderLaunchError, "BUNDLE"):
            self.model.run(contract=False)
        self.assertEqual(list(self.model.path.iterdir()), [])

    def test_short_long_and_same_size_changed_bundle_refuse(self):
        for raw in (self.model.bundle[:-1], self.model.bundle + b"x", b"X" + self.model.bundle[1:]):
            with self.subTest(size=len(raw)), self.assertRaisesRegex(L.ProviderLaunchError, "BUNDLE"):
                self.model.run(bundle=raw)

    def test_directory_path_and_identity_must_match_retained_original(self):
        for name, value in (("directory", str(self.model.path / "elsewhere")), ("directoryIdentity", [1, 2])):
            with self.subTest(name=name), patch.dict(self.model.prepared, {name: value}), \
                    self.assertRaisesRegex(L.ProviderLaunchError, "DIRECTORY"):
                self.model.run()

    def test_clock_uses_maintained_ticks_per_second_not_supervisor_frequency_key(self):
        original = self.model.prepared["clock"]
        for changed in ({**original, "domain": "other"}, {**original, "ticksPerSecond": 1},
                        {"role": original["role"], "domain": original["domain"], "frequency": L.clocks.NS}):
            with self.subTest(clock=changed), patch.dict(self.model.prepared, {"clock": changed}), \
                    self.assertRaisesRegex(L.ProviderLaunchError, "CLOCK"):
                self.model.run()

    def test_invalid_window_and_exhausted_initial_worker_cutoff_refuse_before_creation(self):
        for cut in (145, 159, 160, 280, 281):
            self.model.cut = cut * L.clocks.NS
            with self.subTest(cut=cut), self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
                self.model.run()
        self.model.cut = 200 * L.clocks.NS
        self.model.prepared["providerWindow"]["hardEndNs"] = 281 * L.clocks.NS
        with self.assertRaisesRegex(L.ProviderLaunchError, "ORIGINAL_END"):
            self.model.run()
        self.assertEqual(list(self.model.path.iterdir()), [])

    def test_current_worker_cutoff_crossed_during_bundle_sync_cannot_return_success(self):
        original = L.files._PosixSink.sync
        def sync(writer):
            original(writer)
            self.model.raw = self.model.cut  # Still earlier than end minus final45.
        with patch.object(L.files._PosixSink, "sync", sync), \
                self.assertRaisesRegex(L.ProviderLaunchError, "EXPIRED"):
            self.model.run()
        self.assertIsNotNone(self.model.owner.original)
        self.assertTrue(next(row for row in self.model.owner.resources if row["label"] == "provider-bundle-writer")["closed"])

    def test_shared_final45_is_reserved_even_when_worker_cutoff_is_later(self):
        self.model.cut = 250 * L.clocks.NS
        original = L.files._PosixSink.sync
        def sync(writer):
            original(writer)
            self.model.raw = 235 * L.clocks.NS
        with patch.object(L.files._PosixSink, "sync", sync), \
                self.assertRaisesRegex(L.ProviderLaunchError, "EXPIRED"):
            self.model.run()

    def test_final_owner_end_crossing_leaf_cutoff_is_postchecked(self):
        model, armed, calls = self.model, False, 0
        seen = {}
        read = P.clock_source.read_source
        last = P.clock_source.roster(model.clock.role)[-1]
        def source(directory, name):
            nonlocal armed
            raw = read(directory, name)
            seen[name] = seen.get(name, 0) + 1
            if name == last and seen[name] == 2:
                armed = True
            return raw
        end = model.owner.end
        def owner_end(*, final=False):
            nonlocal calls
            value = end(final=final)
            if armed and not final:
                calls += 1
                if calls == 2:
                    model.raw = model.cut
            return value
        with patch.object(P.clock_source, "read_source", source), patch.object(model.owner, "end", owner_end), \
                self.assertRaisesRegex(L.ProviderLaunchError, "EXPIRED"):
            model.run()
        self.assertTrue(armed)
        self.assertEqual(calls, 2)

    def test_local_expiration_is_not_rescued_by_unchanged_raw(self):
        original = L.files._PosixSink.sync
        def sync(writer):
            original(writer)
            self.model.local_end = time.monotonic() - 1
        with patch.object(L.files._PosixSink, "sync", sync), self.assertRaises(L.files.posix_files.EvidenceError):
            self.model.run()

    def test_relative_wrong_node_and_empty_path_member_refuse(self):
        for node, path in (("node", "/usr/bin"), ("/tools/python", "/usr/bin"),
                           ("/tools/node", "/usr/bin:"), ("/tools/node", "relative")):
            self.model.node, self.model.tool_path = node, path
            with self.subTest(node=node, path=path), self.assertRaises(L.ProviderLaunchError):
                self.model.run()
        self.assertEqual(list(self.model.path.iterdir()), [])

    def test_existing_fixed_child_is_not_overwritten(self):
        path = self.model.path / "provider"
        path.mkdir(mode=0o700)
        original = path.stat()
        with self.assertRaises(FileExistsError):
            self.model.run()
        self.assertEqual(path.stat().st_ino, original.st_ino)
        self.assertTrue(self.model.owner.unknown)

    def test_short_write_records_failure_and_closes_returned_writer(self):
        with patch.object(L.files._PosixSink, "write", lambda writer, raw: len(raw) - 1), \
                self.assertRaisesRegex(L.ProviderLaunchError, "SHORT_WRITE"):
            self.model.run()
        self.assertTrue(next(row for row in self.model.owner.resources if row["label"] == "provider-bundle-writer")["closed"])

    def test_same_bytes_replaced_between_writer_and_reader_are_refused(self):
        original = self.model.owner.close_one
        def close(value):
            original(value)
            if isinstance(value, L.files._PosixSink):
                value.path.rename(value.path.with_suffix(".original"))
                value.path.write_bytes(self.model.bundle)
                value.path.chmod(0o600)
        with patch.object(self.model.owner, "close_one", close), \
                self.assertRaisesRegex(L.ProviderLaunchError, "BUNDLE_REPLACED"):
            self.model.run()

    def test_ambiguous_close_retains_unknown_and_never_returns_preparation(self):
        close = L.files._PosixSink.close
        def failed_close(writer):
            close(writer)
            raise OSError("MODEL_CLOSE_AMBIGUOUS")
        with patch.object(L.files._PosixSink, "close", failed_close), \
                self.assertRaisesRegex(L.ProviderLaunchError, "INPUT_CHANGED"):
            self.model.run()
        self.assertTrue(self.model.owner.unknown)
        self.assertIsInstance(self.model.owner.original, OSError)

    def test_overlapping_clock_source_must_equal_worker_source(self):
        read = P.clock_source.read_source
        def changed(directory, name):
            raw = read(directory, name)
            return raw + b"\n# MODEL_DELTA\n" if name == "audit_processes" else raw
        with patch.object(P.clock_source, "read_source", changed), \
                self.assertRaisesRegex(L.ProviderLaunchError, "SOURCE_CHANGED"):
            self.model.run()

    def test_changed_source_on_final_reread_is_refused(self):
        read, seen = L.worker_source.read_source, {}
        def changed(directory, name):
            raw = read(directory, name)
            seen[name] = seen.get(name, 0) + 1
            return raw + b"\n# MODEL_DELTA\n" if seen[name] == 2 else raw
        with patch.object(L.worker_source, "read_source", changed), \
                self.assertRaisesRegex(L.ProviderLaunchError, "SOURCE_CHANGED"):
            self.model.run()

    def test_cancellation_and_input_replacement_do_not_start_file_work(self):
        def cancelled():
            raise RuntimeError("MODEL_CANCELLED")
        self.model.owner.cancelled = cancelled
        with self.assertRaisesRegex(RuntimeError, "MODEL_CANCELLED"):
            self.model.run()
        self.assertEqual(list(self.model.path.iterdir()), [])
        other = Fixture(self)
        def replace():
            other.owner.local_end += 1
        other.owner.cancelled = replace
        with self.assertRaisesRegex(L.ProviderLaunchError, "INPUT_CHANGED"):
            other.run()
        self.assertEqual(list(other.path.iterdir()), [])

    def test_unknown_or_closed_owner_cannot_become_a_preparation(self):
        self.model.owner.unknown = True
        with self.assertRaisesRegex(L.ProviderLaunchError, "INPUT_CHANGED"):
            self.model.run()
        other = Fixture(self)
        other.owner.close()
        with self.assertRaisesRegex(L.ProviderLaunchError, "INPUT_CHANGED"):
            other.run()


if __name__ == "__main__":
    unittest.main()
