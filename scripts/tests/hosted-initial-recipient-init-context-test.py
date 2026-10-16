#!/usr/bin/env python3
"""Offline Stage1 canonical-context grammar, not initializer/native execution.

Only the committed public policy and existing synthetic identity/event fixtures
are read. Paths/toolchain homes are lexical data; no state, process, key or
authority is acquired. These tests do not invoke the canonical initializer.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes  # Stdlib initialization only, before project imports/guards.
import importlib.util
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import time
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_initialization as C
import hosted_initial_recipient_bootstrap_identity as H


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(filename))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


F = load("initial_context_stage_models", "hosted-initial-recipient-stages-test.py")
L = load("initial_context_legacy_models", "hosted-cache-bootstrap-identity-test.py")
I, B = H.I, H.B


class InitialContextModels(L.OfflineCase):
    def setUp(self):
        super().setUp()
        self.declaration = F.stage1()
        self.select("desktop-linux-x64")

    def select(self, name):
        observed = F.observation1(self.declaration, name)
        match = F.check1(self.declaration, observed)
        event = {"repository": {"full_name": I.REPOSITORY, "default_branch": "main"},
            "ref": H.stages.SOURCE_REF, "inputs": {"selection": name,
                "expected_sha": F.H1, "expected_tree": F.T1}}
        self.worker = H.bind_worker_match(match, event_raw=I.encoded(event), policy_raw=F.POLICY, now=F.DONE1)
        self.role = B.selection(name)[1]
        path = PureWindowsPath if self.role == "windows-x64" else PurePosixPath
        root = path(r"D:\source\P2pKit" if self.role == "windows-x64" else "/source/P2pKit")
        state = path(r"D:\temporary\initial\state" if self.role == "windows-x64" else "/temporary/initial/state")
        homes = ((r"C:\jdks\17", r"C:\jdks\21") if self.role == "windows-x64" else ("/jdks/17", "/jdks/21"))
        policy = C.properties(homes)
        self.options = dict(worker_raw=self.worker.record, root=str(root), state=str(state), role=self.role,
            outer_job="8" * 32, homes=homes, policy_raw=policy)
        self.context = {"schema": 1, "root": str(root), "expectedCommit": F.H1, "tree": F.T1,
            "source": {"commit": F.H1, "tree": F.T1, "status": "", "diffSha256": C.producer.digest(b"")},
            "host": self.role, "gradleHome": str(state / "gradle-home"), "createdUtc": F.utc(F.DONE1),
            "id": "9" * 32, "gradlePropertiesSha256": C.producer.digest(policy),
            "javaHomes": list(homes), "preexistingOutputPaths": []}

    def check(self, context=None, **changed):
        options = {**self.options, **changed}
        raw = I.encoded(self.context if context is None else context)
        return C.initial_recipient_context_record(raw, **options)

    def refuse(self, context=None, **changed):
        with self.assertRaises(ValueError):
            self.check(context, **changed)

    def legacy(self, name):
        _profile, _role, system, arch = B.selection(name)
        self.env.update(RUNNER_OS=system, RUNNER_ARCH=arch)
        self.event["inputs"]["selection"] = name
        admitted = self.admit()
        context = copy.deepcopy(self.context)
        context.update(expectedCommit=L.SOURCE, tree=L.TREE)
        context["source"].update(commit=L.SOURCE, tree=L.TREE)
        options = {name: value for name, value in self.options.items() if name != "worker_raw"}
        return admitted, context, options

    def test_distinct_stage1_route_accepts_all_six_canonical_contexts(self):
        for name, _profile, _role, _system, _arch in B.SELECTIONS:
            with self.subTest(selection=name):
                self.select(name)
                before = self.worker.record
                self.assertEqual(self.check(), self.context)
                self.assertEqual(self.worker.record, before)
                self.assertEqual(I.parse(before, I.EVENT_LIMIT)["policy"]["origin"], "reviewed-head")
                self.assertNotIsInstance(self.worker, I.Admission)

    def test_existing_trusted_main_route_still_accepts_its_own_six_records(self):
        for name, _profile, _role, _system, _arch in B.SELECTIONS:
            with self.subTest(selection=name):
                self.select(name)
                admitted, context, options = self.legacy(name)
                self.assertEqual(C.context_record(I.encoded(context), admitted_raw=admitted.record, **options), context)
                self.refuse(context, worker_raw=admitted.record)

    def test_stage1_does_not_enter_legacy_context_or_cohort_routes(self):
        for name, _profile, _role, _system, _arch in B.SELECTIONS:
            with self.subTest(selection=name):
                self.select(name)
                options = {name: value for name, value in self.options.items() if name != "worker_raw"}
                with self.assertRaises(ValueError):
                    C.context_record(I.encoded(self.context), admitted_raw=self.worker.record, **options)
                with self.assertRaises(ValueError):
                    B.cache_cohort(self.worker.record)

    def test_non_stage1_and_relabelled_worker_records_cannot_select_new_route(self):
        self.refuse(worker_raw=I.encoded({"schema": 1, "scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY"}))
        for mutate in (lambda v: v.update(scope=B.SCOPE), lambda v: v.update(profile="full"),
                       lambda v: v.pop("initialRecipient"), lambda v: v.update(scope=H.stages.STAGE2),
                       lambda v: v["initialRecipient"].update(scope=H.stages.STAGE2 + "_MATCH_ONLY_NOT_ADMISSION")):
            value = I.parse(self.worker.record, I.EVENT_LIMIT)
            mutate(value)
            self.refuse(worker_raw=I.encoded(value))

    def test_worker_policy_authority_and_source_bindings_are_not_normalized(self):
        for mutate in (lambda v: v["policy"].update(origin="main"),
                       lambda v: v["policy"].update(commit=H.stages.BASE["commit"]),
                       lambda v: v["policy"].update(sha256="f" * 64),
                       lambda v: v["initialRecipient"]["authority"].update(owner="another-user"),
                       lambda v: v["initialRecipient"]["originalBase"].update(tree="f" * 40),
                       lambda v: v["source"].update(commit=F.H2),
                       lambda v: v["github"].update(job="initial-recipient-gate"),
                       lambda v: v["cacheCohort"].update(profile="full")):
            value = I.parse(self.worker.record, I.EVENT_LIMIT)
            mutate(value)
            self.refuse(worker_raw=I.encoded(value))
        self.refuse(worker_raw=self.worker.record + b"\n")

    def test_exact_input_bytes_reject_mutable_or_subclassed_records(self):
        class EqualBytes(bytes):
            def __eq__(self, _other):
                return True
        raw = I.encoded(self.context)
        for convert in (bytearray, memoryview, EqualBytes):
            with self.subTest(kind=convert.__name__):
                with self.assertRaises(ValueError):
                    C.initial_recipient_context_record(convert(raw), **self.options)
                self.refuse(worker_raw=convert(self.worker.record))

    def test_canonical_schema_is_exact_but_not_a_new_serialization_contract(self):
        raw = json.dumps(self.context, indent=2).encode("ascii")
        self.assertEqual(C.initial_recipient_context_record(raw, **self.options), self.context)
        for mutate in (lambda v: v.update(schema=True), lambda v: v.pop("id"),
                       lambda v: v.update(productiveAdmission=True), lambda v: v.update(originalOutcome="success")):
            value = copy.deepcopy(self.context)
            mutate(value)
            self.refuse(value)

    def test_exact_canonical_source_home_and_role_remain_required(self):
        for mutate in (lambda v: v["source"].update(commit=F.H2), lambda v: v["source"].update(tree=F.T2),
                       lambda v: v["source"].update(status=" M file"), lambda v: v["source"].update(diffSha256="f" * 64),
                       lambda v: v.update(expectedCommit=F.H2), lambda v: v.update(tree=F.T2),
                       lambda v: v.update(host="macos-arm64"), lambda v: v.update(root="/elsewhere"),
                       lambda v: v.update(gradleHome="/temporary/other/gradle-home")):
            value = copy.deepcopy(self.context)
            mutate(value)
            self.refuse(value)
        self.refuse(role="macos-arm64")
        self.refuse(root=Path(self.options["root"]))
        self.refuse(state=Path(self.options["state"]))

    def test_source_and_state_cannot_overlap_or_use_noncanonical_paths(self):
        for state in (self.options["root"], self.options["root"] + "/state", "/source", "relative/state",
                      "/temporary/../state"):
            self.refuse(state=state)
        self.select("desktop-windows-x64")
        self.refuse(state=r"\\server\share\state")
        self.refuse(state=r"D:\source\P2pKit\state")

    def test_initializer_job_must_be_distinct_and_well_formed(self):
        for value in (self.options["outer_job"], "9" * 31, "G" * 32, True, None):
            context = copy.deepcopy(self.context)
            context["id"] = value
            self.refuse(context)
        for value in (self.context["id"], "bad", True, None):
            self.refuse(outer_job=value)

    def test_properties_and_declared_installed_homes_must_match_exactly(self):
        for mutate in (lambda v: v.update(javaHomes=["/different-jdk"]),
                       lambda v: v.update(gradlePropertiesSha256="f" * 64),
                       lambda v: v.update(preexistingOutputPaths=["/source/P2pKit/build"]),
                       lambda v: v.update(preexistingOutputPaths=None)):
            value = copy.deepcopy(self.context)
            mutate(value)
            self.refuse(value)
        self.refuse(homes=list(self.options["homes"]))
        self.refuse(policy_raw=self.options["policy_raw"] + b"\n")
        self.refuse(policy_raw=bytearray(self.options["policy_raw"]))
        self.refuse(homes=())

    def test_utc_label_is_required_but_cannot_provide_a_live_window(self):
        for value in ("2026-09-21T12:00:00", "2026-09-21T12:00:00+01:00", "not-a-date", "", True):
            context = copy.deepcopy(self.context)
            context["createdUtc"] = value
            self.refuse(context)
        value = copy.deepcopy(self.context)
        value["createdUtc"] = "2000-01-01T00:00:00Z"
        self.assertEqual(self.check(value), value)  # Label grammar is not chronological authority.

    def test_reader_does_not_acquire_files_clocks_crypto_or_current_authority(self):
        raw = I.encoded(self.context)
        with ExitStack() as guards:
            for module, name in ((Path, "open"), (Path, "stat"), (Path, "lstat"),
                                 (time, "time"), (time, "monotonic"), (C, "installed_toolchains"),
                                 (H, "bind_worker_match"), (I, "_policy")):
                guards.enter_context(patch.object(module, name, side_effect=AssertionError("NO_NEW_AUTHORITY_OR_IO")))
            first = C.initial_recipient_context_record(raw, **self.options)
            second = C.initial_recipient_context_record(raw, **self.options)
        self.assertEqual(first, self.context)
        self.assertEqual(second, first)
        self.assertIsNot(second, first)
        self.assertNotIsInstance(first, I.Admission)
        self.assertEqual(set(first), C.producer.CONTEXT_FIELDS)

    def test_no_admission_budget_recipient_or_reader_override_argument(self):
        for name in ("admission", "recipient", "now", "timeout_seconds", "query_runner", "cohort_reader"):
            with self.subTest(argument=name), self.assertRaises(TypeError):
                self.check(**{name: None})


if __name__ == "__main__":
    unittest.main(verbosity=2)
