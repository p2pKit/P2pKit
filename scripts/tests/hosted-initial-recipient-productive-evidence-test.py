#!/usr/bin/env python3
"""Productive facade models, not native custody or production-key qualification.

The maintained public-policy fixture and DATA parsers are reused. PC admission
and backend operations are explicit, small in-memory models; no real child,
native owner, public-key operation, HTTP, filesystem effect or build executes.
"""
from __future__ import annotations

import ctypes
from contextlib import ExitStack
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import sys
from types import MappingProxyType, SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            GUARDED and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        raise AssertionError("PRODUCTIVE_EVIDENCE_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_evidence as E
import hosted_initial_recipient_productive as P
import hosted_initial_recipient_productive_custody as PC
import hosted_initial_recipient_productive_custody_data as CD

SPEC = importlib.util.spec_from_file_location("productive_evidence_stage_fixture",
    Path(__file__).with_name("hosted-initial-recipient-stages-test.py"))
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)  # Fixture constructors only; no old test method runs.
NS = P.O.NS


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n").encode("ascii")


class ProductiveFacadeModels(unittest.TestCase):
    def setUp(self):
        global GUARDED
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(self.unguard)
        self.clock = P.O.clocks.ClockIdentity("linux-x64", P.O.clocks.DOMAINS["linux-x64"], NS)
        self.raw, self.local, self.utc = 100 * NS, 1000.0, F.DONE1
        self.clock_calls, self.local_calls = 0, 0
        self.forbid_observation = False
        self.admission_action = self.live_action = self.backend_action = lambda: None
        self.backend_results, self.backend_calls = [], []
        self.retired = False
        self.model_os = SimpleNamespace(name="posix", environ={}, getpid=lambda: 71001)
        self.install(E, "os", self.model_os)
        self.install(E, "time", SimpleNamespace(time=lambda: self.utc, monotonic=self.local_now))
        self.install(P, "_credential_free", lambda: None)
        self.install(P.O.clocks, "observe", self.observe)
        for name in ("_PRODUCTIVE_ATTEMPTS", "_PRODUCTIVE_BINDINGS", "_PRODUCTIVE_RETURNS"):
            self.install(E, name, {})
        self.install(PC, "checked_child_validation", self.admit_validation)
        self.install(PC, "check_child_validation", self.live_validation)
        self.install(PC, "checked_retired_child_validation", self.retired_validation)
        self.install(PC, "checked_child_archive", self.admit_archive)
        self.install(PC, "check_child_archive", self.live_archive)
        self.install(PC, "archive_liveness", self.archive_liveness)
        self.install(PC, "check_retired_child_archive", self.retired_archive)
        self.install(E.posix, "_validate_initial_productive", self.backend_validation)
        self.install(E.posix, "_export_initial_productive", self.backend_export)
        self.install(E.posix, "_checked_productive_validation_return", self.checked_backend)
        self.install(E.posix, "_checked_productive_export_return", self.checked_backend)
        self.fresh()
        GUARDED = True

    @staticmethod
    def unguard():
        global GUARDED
        GUARDED = False

    def install(self, owner, name, value):
        return self.stack.enter_context(patch.object(owner, name, value))

    def local_now(self):
        if self.forbid_observation:
            raise AssertionError("PASSIVE_CHECK_MUST_NOT_OBSERVE_LOCAL")
        self.local_calls += 1
        return self.local

    def observe(self):
        if self.forbid_observation:
            raise AssertionError("PASSIVE_CHECK_MUST_NOT_OBSERVE_RAW")
        self.clock_calls += 1
        return P.O.clocks.Reading(self.clock, self.raw)

    def fresh(self):
        self.child, self.archive = object(), object()
        self.work = Path("/synthetic/productive-final/public-crypto")
        self.policy, self.key = E.I._policy(F.POLICY, self.utc)
        declaration = F.stage1()
        self.match_raw = F.check1(declaration, F.observation1(declaration)).record
        self.match = json.loads(self.match_raw)
        source = PC.ChildSourceBinding("a" * 32, b"{}\n", "e" * 64, "c" * 64, "d" * 64)
        first = P.O.clocks.Reading(self.clock, self.raw)
        caps = PC.ValidationCaps(self.clock, first, self.local, 160 * NS, 1060.0, 160 * NS, 1060.0, 0, 60 * NS)
        self.validation = PC.ValidationView(self.child, "linux-x64", self.work, self.key, F.POLICY,
            self.match_raw, source, caps)
        self.recipient = E.posix.Recipient(self.work, self.work / "gnupg", Path("/synthetic/gpg"),
            self.policy["recipient"]["fingerprint"], "B" * 40, self.policy["expiresAt"] + 1000,
            self.policy["recipient"]["sha256"], (1, 2))
        self.view = None

    def admit_validation(self, child):
        self.assertIs(child, self.child)
        self.admission_action()
        return self.validation

    def live_validation(self, view):
        self.assertIs(view, self.validation)
        if self.retired:
            raise RuntimeError("MODEL_CHILD_NOT_ACTIVE")
        self.live_action()
        return view

    def retired_validation(self, child):
        self.assertIs(child, self.child)
        if not self.retired:
            raise RuntimeError("MODEL_CHILD_NOT_RETIRED")
        return self.validation

    def admit_archive(self, child, archive, recipient):
        self.assertIs(child, self.child)
        self.assertIs(archive, self.archive)
        self.assertIs(recipient, self.recipient)
        return self.view

    def live_archive(self, view):
        self.assertIs(view, self.view)
        if self.retired:
            raise RuntimeError("MODEL_CHILD_NOT_ACTIVE")
        self.live_action()
        return view

    def archive_liveness(self, view):
        return self.live_archive(view).caps

    def retired_archive(self, view):
        self.assertIs(view, self.view)
        if not self.retired:
            raise RuntimeError("MODEL_CHILD_NOT_RETIRED")
        return view

    def checked_backend(self, result, binding):
        if not any(result is original for original in self.backend_results) or result.binding is not binding:
            raise RuntimeError("MODEL_BACKEND_UNREGISTERED_RESULT")
        return result

    def backend_validation(self, binding):
        self.backend_calls.append("validation")
        self.backend_action()
        self.assertIs(E._productive_work_guard(binding), self.validation.caps)
        result = E.posix._ProductiveValidationReturn(binding, object(), self.recipient, (object(),), object())
        self.backend_results.append(result)
        return result

    def backend_export(self, binding):
        self.backend_calls.append("export")
        self.backend_action()
        nodes = (self.view.payload_root, self.view.index, *(node for part in self.view.partitions
            for node in (part.root, *part.members, part.map)))
        E._productive_check_snapshot(binding, {node.relative: node.native[1:] for node in nodes})
        cap = E._productive_keyring_begin(binding)
        self.assertIs(E._productive_keyring_guard(binding, cap), cap)
        self.assertIs(E._productive_keyring_complete(binding, cap), cap)
        raw = E._productive_manifest(binding, "f" * 64, 100)
        artifact = E.posix._ProductiveArtifact(E.posix.ARTIFACT, "f" * 64, 100,
            ("posix", 1, 9999, stat.S_IFREG | 0o600, 1, 1, 100, 1, 1))
        result = E.posix._ProductiveExportReturn(binding, object(), raw, artifact, (object(),), object())
        self.backend_results.append(result)
        return result

    def archive_view(self):
        number = 1
        def node(name, raw=None):
            nonlocal number
            directory = raw is None
            result = PC.ExpectedNode(name, "directory" if directory else "file", None if directory else len(raw),
                None if directory else sha(raw), ("posix", 1, number, (stat.S_IFDIR | 0o700) if directory else
                    (stat.S_IFREG | 0o600), 1, 2 if directory else 1, 4096 if directory else len(raw), 1, 1), object())
            number += 1
            return result
        root = node("")
        parts = tuple(PC.PartitionView(index, name, node(name), (node(name + "/member-00000.bin", b"synthetic"),),
            node("map-" + name + ".json", b"{}\n")) for index, name in enumerate(CD.GROUPS, 1))
        index = node("copy-index.json", b"{}\n")
        inputs = {"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_MANIFEST_INPUTS_V1", "kind": "worker",
            "selection": self.match["github"]["selection"], "source": self.match["source"],
            "github": {**self.match["github"], "repository": E.I.REPOSITORY, "eventSha256": "e" * 64},
            "policy": {**self.match["policy"], "fingerprint": self.policy["recipient"]["fingerprint"],
                "keySha256": self.policy["recipient"]["sha256"], "expiresAt": self.policy["expiresAt"], "retentionDays": 14},
            "initialRecipient": {**{key: self.match[key] for key in
                ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt")},
                "matchSha256": sha(self.match_raw), "preExportReturnSha256": "a" * 64, "preExportIndexSha256": "b" * 64},
            "productive": {key: "success" if key.endswith("StepOutcome") else "c" * 64 for key in
                ("originalProposalSha256", "producerHandoffSha256", "producerReturnSha256", "producerStepOutcome",
                 "afterSaveSha256", "afterSaveStepOutcome", "probeSha256", "afterProbeStepOutcome", "prefixRetentionSha256",
                 "compatibilityInputsSha256")}}
        inputs["copy"] = {"scope": "INITIAL_RECIPIENT_PRODUCTIVE_FIXED30_ARCHIVE_BINDING_V1",
            "groups": [{"ordinal": part.ordinal, "group": part.group, "map": {"name": part.map.relative,
                "bytes": part.map.bytes, "sha256": part.map.sha256}, "dataFiles": 1, "dataBytes": 9} for part in parts],
            "index": {"name": index.relative, "bytes": index.bytes, "sha256": index.sha256}, "dataFiles": 30,
            "mapFiles": 30, "indexFiles": 1, "archiveFiles": 61, "archiveNativeNodes": 92,
            "plaintextBytes": 30 * (9 + 3) + 3}
        caps = PC.ArchiveCaps(self.clock, P.O.clocks.Reading(self.clock, self.raw), self.local,
            340 * NS, 1240.0, 340 * NS, 1240.0, 0, 240 * NS)
        self.view = PC.ArchiveView(self.child, self.archive, self.recipient, "linux-x64",
            Path("/synthetic/productive-final/payload"), Path("/synthetic/productive-final/export-output"), root,
            parts, index, object(), caps, canonical(inputs))
        return self.view

    def validate(self):
        return E.validate_initial_productive_recipient(self.child)

    def export(self):
        return E.export_initial_productive_encrypted(self.child, self.archive, self.recipient)

    def test_00_actual_facade_model_registers_validation_and_fixed30_export(self):
        validation = self.validate()
        self.assertIs(validation.recipient, self.recipient)
        view = self.archive_view()
        result = self.export()
        self.assertIs(result.view, view)
        self.assertIs(E.checked_productive_backend_return(result, view), result)
        manifest = json.loads(result.manifest_raw)
        self.assertEqual(manifest["copy"]["archiveNativeNodes"], 92)
        self.assertEqual(manifest["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(manifest["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(manifest["productive"]["compatibilityInputsSha256"], "c" * 64)
        self.assertLess(len(result.manifest_raw), CD.PUBLIC_LIMIT)
        self.assertIs(manifest["exportSaveAuthority"], False)
        self.assertEqual(self.backend_calls, ["validation", "export"])

    def test_unregistered_equal_validation_result_refuses(self):
        result = self.validate()
        with self.assertRaises(Exception):
            E.checked_productive_validation_return(dataclasses.replace(result), self.child)

    def test_equal_original_view_field_replacement_refuses(self):
        result = self.validate()
        object.__setattr__(self.validation, "caps", dataclasses.replace(self.validation.caps))
        with self.assertRaises(Exception):
            E.checked_productive_validation_return(result, self.child)

    def test_admission_callback_cannot_install_new_backend(self):
        self.admission_action = lambda: setattr(E.posix, "_validate_initial_productive", lambda _binding: None)
        with self.assertRaises(Exception):
            self.validate()
        self.assertFalse(self.backend_calls)

    def test_admission_callback_cannot_replace_shared_graph_engine(self):
        original, callbacks, replacements = E._graph_data, [], []

        def replacement(*args, **kwargs):
            replacements.append(True)
            return original(*args, **kwargs)

        def replace():
            callbacks.append(True)
            E._graph_data = replacement

        with patch.object(E, "_graph_data", original):
            self.admission_action = replace
            with self.assertRaisesRegex(E.posix.EvidenceError, "^INITIAL_EVIDENCE_PRODUCTIVE_ADMISSION_CHANGED$"):
                self.validate()
        self.assertEqual(callbacks, [True])
        self.assertEqual(replacements, [])
        self.assertEqual(self.backend_calls, [])

    def test_caught_admission_reentry_poisons_first_attempt(self):
        def reenter():
            try:
                self.validate()
            except Exception:
                pass
        self.admission_action = reenter
        with self.assertRaises(Exception):
            self.validate()
        self.admission_action = lambda: None
        with self.assertRaises(Exception):
            self.validate()
        self.assertFalse(self.backend_calls)

    def test_raw_work_expiry_refuses_before_backend_return(self):
        self.backend_action = lambda: setattr(self, "raw", 160 * NS)
        with self.assertRaises(Exception):
            self.validate()

    def test_local_work_expiry_refuses_even_with_early_raw(self):
        self.backend_action = lambda: setattr(self, "local", 1060.0)
        with self.assertRaises(Exception):
            self.validate()

    def test_operation_cannot_claim_more_than_original_sixty_seconds(self):
        object.__setattr__(self.validation, "caps", dataclasses.replace(self.validation.caps,
            workEndNs=161 * NS, operationFinishEndNs=161 * NS))
        with self.assertRaises(Exception):
            self.validate()
        self.assertFalse(self.backend_calls)

    def test_completed_validation_checks_original_fact_not_spent_subcap(self):
        result = self.validate()
        self.raw, self.local = 200 * NS, 1100.0
        self.assertIs(E.checked_productive_validation_return(result, self.child), result)

    def test_retired_result_never_observes_clock_or_uses_active_pc_route(self):
        result = self.validate()
        self.retired = True
        def no_effect(*_args):
            raise AssertionError("PASSIVE_CHECK_MUST_NOT_OBSERVE")
        # Preserve original callable pins: reject any invocation through model action.
        self.live_action = no_effect
        previous = self.clock_calls, self.local_calls
        self.forbid_observation = True
        self.raw, self.local = 10 ** 15, 10 ** 12
        self.assertIs(E.checked_retired_productive_validation_return(result, self.child), result)
        self.assertEqual((self.clock_calls, self.local_calls), previous)

    def test_live_child_cannot_be_relabelled_retired(self):
        result = self.validate()
        with self.assertRaisesRegex(RuntimeError, "MODEL_CHILD_NOT_RETIRED"):
            E.checked_retired_productive_validation_return(result, self.child)

    def test_completion_reading_mutation_is_rejected_passively(self):
        result = self.validate()
        self.retired = True
        completion = result.observations[1][0]
        object.__setattr__(completion, "nanoseconds", completion.nanoseconds + 1)
        with self.assertRaises(Exception):
            E.checked_retired_productive_validation_return(result, self.child)

    def test_export_requires_same_actually_returned_recipient(self):
        self.validate()
        self.archive_view()
        self.recipient = dataclasses.replace(self.recipient)
        with self.assertRaises(Exception):
            self.export()

    def test_native_alias_in_another_partition_refuses(self):
        self.validate()
        self.archive_view()
        object.__setattr__(self.view.partitions[1].members[0], "native", self.view.partitions[0].members[0].native)
        with self.assertRaises(Exception):
            self.export()
        self.assertEqual(self.backend_calls, ["validation"])

    def test_public_counts_are_reconciled_against_actual_view(self):
        self.validate()
        self.archive_view()
        value = json.loads(self.view.public_inputs)
        value["copy"]["archiveFiles"] += 1
        object.__setattr__(self.view, "public_inputs", canonical(value))
        with self.assertRaises(Exception):
            self.export()

    def test_actual_crypto_facade_rejects_missing_compatibility_digest_before_export(self):
        self.validate()
        self.archive_view()
        value = json.loads(self.view.public_inputs)
        del value["productive"]["compatibilityInputsSha256"]
        object.__setattr__(self.view, "public_inputs", canonical(value))
        with self.assertRaises(Exception):
            self.export()
        self.assertEqual(self.backend_calls, ["validation"])

    def test_duplicate_keyring_begin_poison_is_sticky(self):
        self.validate()
        self.archive_view()
        state = E._productive_start(self.child, "export")
        binding = E._productive_admit(state, self.archive, self.recipient)
        cap = E._productive_keyring_begin(binding)
        self.assertLessEqual(cap.workEndNs, self.raw + 30 * NS)
        self.assertLess(cap.workEndLocal, self.local + 30)
        with self.assertRaises(Exception):
            E._productive_keyring_begin(binding)
        with self.assertRaises(Exception):
            E._productive_keyring_guard(binding, cap)

    def test_changed_same_selected_node_is_not_accepted_per_block(self):
        self.validate()
        self.archive_view()
        state = E._productive_start(self.child, "export")
        binding = E._productive_admit(state, self.archive, self.recipient)
        node = self.view.partitions[0].members[0]
        self.assertIs(E._productive_expected_node(binding, node.relative), node)
        object.__setattr__(node, "sha256", "f" * 64)
        with self.assertRaises(Exception):
            E._productive_node_guard(binding, node)

    def test_artifact_native_vector_keeps_complete_shape_and_actual_size(self):
        native = ("posix", 1, 2, stat.S_IFREG | 0o600, 1, 1, 100, 1, 1)
        self.assertEqual(E._productive_native_shape(native, "linux-x64", "file"), 100)
        for bad in (native[:-1], list(native), (*native[:3], stat.S_IFDIR | 0o700, *native[4:]),
                (*native[:6], True, *native[7:])):
            with self.subTest(native=bad), self.assertRaises(Exception):
                E._productive_native_shape(bad, "linux-x64", "file")

    def snapshot_shape_model(self, role):
        # Only this facade's role/type/roster/native comparison is under test.
        # These tiny exact FileInfo/DATA objects do not claim a native snapshot.
        info = (E.windows.files.FileInfo((1, "a" * 32), True, 0, 1, 16, 1, 2, 3, "MODEL-SID", True)
            if role == "windows-x64" else (1, 2, stat.S_IFDIR | 0o700, 1, 2, 0, 1, 1))
        entries = {"": info}
        state = {"mode": "export", "status": "RUNNING", "failure": None, "busy": True,
            "nodes": {"": SimpleNamespace(native=E._productive_native(info, role))}}
        binding = SimpleNamespace(view=SimpleNamespace(role=role))
        self.install(E, "_productive_enter", lambda _binding: state)
        self.install(E, "_productive_current", lambda _state, **_kwargs: None)
        self.install(E, "_productive_time", lambda _state: None)
        self.install(E, "_productive_passive", lambda _state, **_kwargs: None)
        return binding, entries

    def test_snapshot_preserves_actual_exact_platform_mapping(self):
        for role in ("linux-x64", "macos-arm64", "windows-x64"):
            with self.subTest(role=role):
                binding, entries = self.snapshot_shape_model(role)
                original = MappingProxyType(entries) if role == "windows-x64" else entries
                self.assertIs(E._productive_check_snapshot(binding, original), original)

    def test_snapshot_rejects_wrong_role_mapping_and_nonexact_types(self):
        class DictionarySubclass(dict):
            pass
        for role in ("linux-x64", "windows-x64"):
            for kind in ("wrong-platform", "subclass", "list"):
                with self.subTest(role=role, kind=kind):
                    binding, entries = self.snapshot_shape_model(role)
                    wrong = (entries if role == "windows-x64" else MappingProxyType(entries))
                    if kind == "subclass":
                        wrong = DictionarySubclass(entries)
                    elif kind == "list":
                        wrong = list(entries.items())
                    with self.assertRaisesRegex(E.posix.EvidenceError, "PRODUCTIVE_SNAPSHOT_ROSTER"):
                        E._productive_check_snapshot(binding, wrong)


if __name__ == "__main__":
    unittest.main(failfast=True)
