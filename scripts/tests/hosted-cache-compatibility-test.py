#!/usr/bin/env python3
"""Authored offline source/ownership models, NOT hosted/provider qualification.

All source files, identities, owners and close records below are in-memory
models. No old test method, actual key, native file, subprocess or network is
selected. Passing these controls cannot establish a real H1/H2 source window.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import ctypes  # Stdlib initialization before refusing subsequent native loads.
from dataclasses import replace
import hashlib
from pathlib import Path, PurePosixPath
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            GUARDED and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        raise AssertionError("COMPATIBILITY_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_compatibility as C
import hosted_dependency_seed_files as F
import hosted_initial_recipient_productive_data as D


SOURCE = {"commit": "a" * 40, "tree": "b" * 40}


def inputs():
    return {"seed": {"files": {name: "1" * 64 for name in F.INPUTS}, "allowlistSha256": "2" * 64,
        "artifacts": 1, "components": 1, "policy": F.policy()},
        "provider": {name: "3" * 64 for name in C.PROVIDER_INPUTS}}


def metadata():
    return ('<?xml version="1.0" encoding="UTF-8"?><verification-metadata xmlns="' + F.authority.NAMESPACE +
        '" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="' + F.authority.SCHEMA_LOCATION +
        '"><configuration><verify-metadata>true</verify-metadata><verify-signatures>false</verify-signatures>' +
        '</configuration><components><component group="org.model" name="model" version="1">'
        '<artifact name="model.jar"><sha256 value="' + hashlib.sha256(b"MODEL_NOT_DEPENDENCY").hexdigest() +
        '"/></artifact></component></components></verification-metadata>').encode("ascii")


class ModelFile:
    def __init__(self, tree, relative):
        self.tree, self.relative = tree, relative
        self.raw, self.offset, self.closed, self.close_calls = tree.raw[relative], 0, False, 0
        self.identity = tree.identities[relative]
        self.initial_info = F.PosixInfo(self.identity, False, tree.sizes.get(relative, len(self.raw)),
            stat.S_IFREG | 0o644, 1000, 1, 1, 1)

    def verify(self):
        if self.closed:
            raise RuntimeError("MODEL_CLOSED_FILE")
        if self.offset and self.relative == self.tree.changed:
            return replace(self.initial_info, mtime_ns=2)
        return self.initial_info

    def read(self, size):
        self.tree.reads.append((self.relative, size))
        if self.relative == self.tree.failed:
            raise self.tree.read_error
        if self.relative == self.tree.short:
            return b""
        if self.offset == len(self.raw) and self.relative == self.tree.trailing:
            return b"X"
        raw = self.raw[self.offset:self.offset + size]
        self.offset += len(raw)
        return raw

    def close(self):
        self.close_calls += 1
        if self.relative == self.tree.close_failed:
            raise self.tree.close_error
        self.closed = True


class ModelDirectory:
    def __init__(self, tree, relative):
        self.tree, self.relative, self.closed, self.close_calls = tree, relative, False, 0
        self.path = PurePosixPath("/model/source", *relative)
        self.identity = tree.identities[relative]
        self.info = F.PosixInfo(self.identity, True, 0, stat.S_IFDIR | 0o755, 1000, 2, 1, 1)

    def verify(self):
        if self.closed:
            raise RuntimeError("MODEL_CLOSED_DIRECTORY")
        return self.info

    def open_directory(self, name, *, deadline):
        self.tree.ends.append(deadline)
        self.verify()
        return ModelDirectory(self.tree, (*self.relative, name))

    def open_file(self, name, *, max_bytes, deadline):
        self.tree.ends.append(deadline)
        self.verify()
        if max_bytes != F.authority.MAX_XML_BYTES:
            raise AssertionError("SOURCE_LIMIT_CHANGED")
        relative = "/".join((*self.relative, name))
        self.tree.opened.append(relative)
        if relative == self.tree.missing:
            raise FileNotFoundError("MODEL_MISSING_SOURCE")
        return ModelFile(self.tree, relative)

    def close(self):
        self.close_calls += 1
        self.closed = True


class ModelTree:
    def __init__(self):
        self.raw = {name: b"MODEL_PUBLIC_SOURCE " + name.encode("ascii") for name in (*F.INPUTS, *C.PROVIDER_INPUTS)}
        self.raw[F.INPUTS[0]] = metadata()
        directories = {()}
        for name in self.raw:
            parts = tuple(name.split("/"))
            directories.update(parts[:count] for count in range(1, len(parts)))
        self.identities = {name: (7, ordinal) for ordinal, name in
            enumerate((*sorted(directories), *sorted(self.raw)), 1)}
        self.reads, self.opened, self.ends, self.sizes = [], [], [], {}
        self.failed = self.short = self.trailing = self.changed = self.missing = self.close_failed = None
        self.read_error, self.close_error = RuntimeError("MODEL_READ_ERROR"), RuntimeError("MODEL_CLOSE_UNKNOWN")


class ModelOwner:
    def __init__(self):
        self.resources, self.errors, self.checks = [], [], 0
        self.unknown, self.original, self.refuse_at = False, None, None
        self.refusal = RuntimeError("MODEL_ORIGINAL_END")

    def check(self, *, new=False):
        self.checks += 1
        if self.refuse_at == self.checks:
            raise self.refusal

    def end(self, *, new=False):
        self.check(new=new)
        return 1000.0

    def acquire(self, label, factory):
        self.check()
        resource = factory()
        self.resources.append([label, resource, False, False])
        return resource

    def error(self, label, error, *, unknown=False):
        if self.original is None:
            self.original = error
        self.unknown |= unknown
        self.errors.append((label, error))

    def close_one(self, resource):
        row, = (row for row in self.resources if row[1] is resource)
        if row[2]:
            if not row[3]:
                raise self.original
            return
        row[2] = True
        try:
            resource.close()
            row[3] = True
        except BaseException as error:
            self.error("model-close", error, unknown=True)
            raise

    def close(self):
        for row in reversed(self.resources):
            if self.unknown:
                break
            self.close_one(row[1])


def writer_fixture():
    """Complete supplied close/return DATA; no real writer is asserted."""
    O, NS = D.O, D.O.NS
    clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
    handoff = {"directory": "/model/handoff", "window": {"firstNs": 100 * NS, "localStarted": 1000.0,
        "hardEndNs": 145 * NS, "clock": O.clock_value(clock), "originalBootDigest": "b" * 64},
        "references": {"prefixRetention": {"model": "NOT_NATIVE_CUSTODY"}},
        "blobs": {name: {"bytes": 0 if name.endswith(".bin") else 1} for name in D.BLOB_NAMES}}
    old = [*("directory",) * 8, *("reader",) * 12, "directory", "directory",
        *("writer", "reader", "reader") * 6, *("reader",) * 6, "directory", "directory"]
    for name in (*D.BLOB_NAMES, "save-handoff.json"):
        old.extend(("empty-original-writer" if name.endswith(".bin") else "writer", "reader"))
    old.extend(("reader",) * 32)
    labels = (*old[:46], *C.source_read_labels(), *old[46:], *C.source_read_labels())
    raw = O.encoded(handoff)
    close = {"schema": 1, "scope": D.PREFIX_WRITER_CLOSE_SCOPE, "phase": "producer-owner-return", "ownerOrdinal": 0,
        **{name: handoff["window"][name] for name in ("firstNs", "localStarted", "hardEndNs")},
        "handoffSha256": O.digest(raw), "prefixRetentionSha256": O.digest(O.encoded(handoff["references"]["prefixRetention"])),
        "resourceCount": 448, "resources": [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
            for number, label in enumerate(labels)], "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
        "observationScope": "PRIOR_FIRST_OWNER_ONLY"}
    returned = {"schema": 2, "scope": D.RETURN_SCOPE, "handoffSha256": O.digest(raw),
        "handoffDirectory": handoff["directory"], "handoffDirectoryIdentity": [7, 2], "initializerIdentity": [7, 1],
        "clock": O.clock_value(clock), "originalBootDigest": "b" * 64, "firstNs": 100 * NS, "hardEndNs": 145 * NS,
        "handoffReturnedNs": 102 * NS, "handoffReturnedLocal": 1002.0, "observedAfterReturnNs": 103 * NS,
        "observedAfterReturnLocal": 1003.0, "prefixRetention": handoff["references"]["prefixRetention"],
        "priorWriterClose": close, "observationScope": "HANDOFF_FUNCTION_RETURN_ONLY", "recordWriterReturn": D.PENDING,
        "producerStepOutcome": D.PENDING, "providerExecution": "NOT_PERFORMED", "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    return old, raw, close, returned, clock


class CompatibilityDataControls(unittest.TestCase):
    def test_closed_roster_scope_and_source_are_not_optional_or_extensible(self):
        value = C.envelope(SOURCE, inputs())
        self.assertEqual((len(F.INPUTS), len(C.PROVIDER_INPUTS)), (12, 123))
        self.assertEqual(C.PROVIDER_INPUTS[-2:], ("scripts/hosted_evidence_primitives.py", "scripts/hosted_jvm_library_custody.py"))
        # Preserved ordered121-input preimage from9eb42cc; only append the leaf.
        old_roster = ("\n".join(C.PROVIDER_INPUTS[:-2]) + "\n").encode("ascii")
        self.assertEqual(hashlib.sha256(old_roster).hexdigest(),
            "7df33468002c82252b19fe5d525b0a3289b67b32d9f6a91ad01082773ff9e56e")
        reviewed122 = ("\n".join(C.PROVIDER_INPUTS[:-1]) + "\n").encode("ascii")
        self.assertEqual(hashlib.sha256(reviewed122).hexdigest(),
            "b99f03bffcb46ae3599e64451f5708bd6917f0610197f1f6374c5af92a065549")
        self.assertFalse(set(F.INPUTS).intersection(C.PROVIDER_INPUTS))
        for mutation in (lambda v: v.pop("inputs"), lambda v: v.update(extra=True),
                lambda v: v.update(schema=True), lambda v: v.update(scope="OLD_OR_OPTIONAL"),
                lambda v: v["source"].update(commit="A" * 40),
                lambda v: v["inputs"]["provider"].pop(C.PROVIDER_INPUTS[-1]),
                lambda v: v["inputs"]["provider"].pop("scripts/run-hosted-recipient-routing.py"),
                lambda v: v["inputs"]["provider"].update({"scripts/../secret": "a" * 64}),
                lambda v: v["inputs"]["seed"].update(components=2049),
                lambda v: v["inputs"]["seed"].update(artifacts=True)):
            bad = copy.deepcopy(value); mutation(bad)
            with self.assertRaises(C.CompatibilityError): C.checked_envelope(bad)

    def test_exact_canonical_bytes_include_lf_and_bind_h1_not_h2(self):
        value = C.envelope(SOURCE, inputs())
        raw = C.encoded(value)
        self.assertEqual(len(raw), 15946)
        self.assertTrue(raw.endswith(b"\n") and not raw.endswith(b"\n\n"))
        self.assertEqual(C.envelope_digest(value), hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(C.envelope_digest(value), hashlib.sha256(raw[:-1]).hexdigest())
        other = copy.deepcopy(value); other["source"]["commit"] = "c" * 40
        self.assertNotEqual(C.envelope_digest(value), C.envelope_digest(other))

    def test_outer2_preserves_inner_binding_and_complete_serialized_limits(self):
        binding = {"scope": D.INPUT_SCOPE, "model": "NOT_AUTHORITY"}
        old = {"schema": 1, "scope": D.INPUT_SCOPE, "binding": binding, "initializerCheckedLocal": 1.0}
        value = {**old, "schema": 2, "scope": D.OUTER_INPUT_SCOPE, "compatibilityInputs": C.envelope(SOURCE, inputs())}
        raw = C.encoded(value)
        self.assertEqual(len(raw) - len(C.encoded(old)), 15980)
        self.assertEqual(D.initial_inputs_record(raw, SOURCE)["binding"], binding)
        with self.assertRaises((ValueError, RuntimeError)): D.initial_inputs_record(C.encoded(old), SOURCE)
        with self.assertRaises((ValueError, RuntimeError)): D.initial_inputs_record(raw, {**SOURCE, "tree": "c" * 40})
        value["binding"]["model"] = "X" * D.LIMIT
        with self.assertRaises(C.CompatibilityError): C.encoded(value)
        self.assertEqual((C.LIMIT, D.LIMIT, C.TOTAL_LIMIT), (2097152, 2097152, 67108864))

    def test_complete448_close_and_return_retain_every_original144_row(self):
        old, raw, close, returned, clock = writer_fixture()
        self.assertEqual(len(old), 144)
        labels = [row["label"] for row in close["resources"]]
        self.assertEqual((close["resourceCount"], len(labels)), (448, 448))
        self.assertEqual(labels[:46] + labels[198:296], old)
        self.assertEqual((len(labels[46:198]), len(labels[296:448])), (152, 152))
        self.assertEqual(labels[46:198], list(C.source_read_labels()))
        self.assertEqual(labels[296:448], list(C.source_read_labels()))
        # Added JVM source rows contribute 168 bytes (84 per pass).
        # Preserve the existing 42-byte allowance above the derived 36208-byte fixture.
        self.assertLessEqual(len(C.encoded(close)), 36250)
        self.assertIs(D.prefix_writer_close(close, raw), close)
        original = SimpleNamespace(role="linux-x64", directories={"session": (7, 1)})
        returned_raw = D.O.encoded(returned)
        self.assertEqual(D.producer_return_record(returned_raw, raw, original,
            D.O.clocks.Reading(clock, 104 * D.O.NS), D.O.digest(returned_raw), (7, 2)), returned)
        self.assertLess(len(returned_raw), D.LIMIT)
        returned["prefixRetention"] = {"model": "X" * D.LIMIT}
        with self.assertRaises((ValueError, RuntimeError)): D.raw_bytes(D.O.encoded(returned))

    def test_ledger_rejects_old_missing_extra_reordered_or_unclosed_resources(self):
        _old, raw, original, _returned, _clock = writer_fixture()
        mutations = (lambda v: v.update(resourceCount=144), lambda v: v.update(resourceCount=442),
            lambda v: v.update(resourceCount=444),
            lambda v: v["resources"].pop(),
            lambda v: v["resources"].append(copy.deepcopy(v["resources"][-1])),
            lambda v: v["resources"][46].update(label="reader"),
            lambda v: v["resources"][46].update(ordinal=47),
            lambda v: v["resources"][46].update(closeAttempted=False),
            lambda v: v["resources"][46].update(closed=False),
            lambda v: v.update(ownerOrdinal=1), lambda v: v.update(hardEndNs=146 * D.O.NS))
        for mutation in mutations:
            bad = copy.deepcopy(original); mutation(bad)
            with self.assertRaises((ValueError, RuntimeError)): D.prefix_writer_close(bad, raw)
        for count in (446, 447, 449, True, 448.0, "448"):
            bad = copy.deepcopy(original)
            bad["resourceCount"] = count
            with self.subTest(resourceCount=count), self.assertRaisesRegex(
                    (ValueError, RuntimeError), "PREFIX_PRIOR_WRITER_ROWS"):
                D.prefix_writer_close(bad, raw)
        # Supplied old grammar: remove exactly the new reader from each pass.
        bad = copy.deepcopy(original)
        del bad["resources"][447]
        del bad["resources"][197]
        for number, row in enumerate(bad["resources"]):
            row["ordinal"] = number
        bad["resourceCount"] = 446
        self.assertEqual(len(bad["resources"]), 446)
        with self.assertRaisesRegex((ValueError, RuntimeError), "PREFIX_PRIOR_WRITER_ROWS"):
            D.prefix_writer_close(bad, raw)
        for ordinal in (197, 447):
            for flag in ("closeAttempted", "closed"):
                bad = copy.deepcopy(original)
                bad["resources"][ordinal][flag] = False
                with self.subTest(ordinal=ordinal, flag=flag), self.assertRaisesRegex(
                        (ValueError, RuntimeError), "PREFIX_PRIOR_WRITER_LEDGER"):
                    D.prefix_writer_close(bad, raw)


class BorrowedSourceControls(unittest.TestCase):
    def setUp(self):
        self.tree, self.owner, self.stack = ModelTree(), ModelOwner(), ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(F, "PosixFile", ModelFile))
        self.stack.enter_context(patch.object(F, "PosixSourceDirectory", ModelDirectory))
        self.stack.enter_context(patch.object(F, "public_root", side_effect=self.root))

    def root(self, root):
        self.assertEqual(str(root), "/model/source")
        return ModelDirectory(self.tree, ())

    def read(self):
        global GUARDED
        prior, GUARDED = GUARDED, True
        try:
            return C.read_inputs(self.owner, "/model/source", 1000.0, self.owner.check)
        finally:
            GUARDED = prior

    def test_all135_originals_and152_owned_resources_close_once_in_exact_order(self):
        value = self.read()
        self.assertEqual(self.tree.opened, [*F.INPUTS, *C.PROVIDER_INPUTS])
        self.assertEqual([row[0] for row in self.owner.resources], list(C.source_read_labels()))
        self.assertEqual(len(self.owner.resources), 152)
        self.assertTrue(all(row[2] and row[3] and row[1].close_calls == 1 for row in self.owner.resources))
        self.assertEqual(set(self.tree.ends), {1000.0})
        self.assertEqual(value["provider"], {name: hashlib.sha256(self.tree.raw[name]).hexdigest() for name in C.PROVIDER_INPUTS})

    def test_second_pass_acquires_fresh_resources_and_observes_changed_source(self):
        first = self.read()
        old_resources = [row[1] for row in self.owner.resources]
        self.tree.raw[C.PROVIDER_INPUTS[0]] += b" CHANGED"
        second = self.read()
        self.assertNotEqual(first, second)
        self.assertEqual(len(self.owner.resources), 304)
        self.assertFalse(any(row[1] is old for row in self.owner.resources[152:] for old in old_resources))
        self.assertTrue(all(row[2] and row[3] and row[1].close_calls == 1 for row in self.owner.resources))

    def test_nested_action_workflow_paths_are_opened_without_discovery(self):
        self.read()
        directories = [row[1].relative for row in self.owner.resources if isinstance(row[1], ModelDirectory)]
        self.assertIn((".github", "actions", "initial-recipient-productive-upload"), directories)
        self.assertIn((".github", "workflows"), directories)
        self.assertEqual(sum(label != "dependency-seed-input" for label, *_rest in self.owner.resources), 17)

    def test_selected_file_alias_refuses_and_keeps_original_parent_ownership(self):
        self.tree.identities[C.PROVIDER_INPUTS[1]] = self.tree.identities[C.PROVIDER_INPUTS[0]]
        with self.assertRaisesRegex(C.CompatibilityError, "ALIAS"): self.read()
        self.owner.close()
        self.assertTrue(all(row[3] for row in self.owner.resources))

    def test_missing_original_refuses_without_placeholder_or_roster_fallback(self):
        self.tree.missing = C.PROVIDER_INPUTS[-1]
        with self.assertRaises(FileNotFoundError): self.read()
        self.assertIsInstance(self.owner.original, FileNotFoundError)

    def test_truncation_non_eof_and_metadata_change_refuse(self):
        for mode in ("short", "trailing", "changed"):
            self.tree, self.owner = ModelTree(), ModelOwner()
            setattr(self.tree, mode, C.PROVIDER_INPUTS[0])
            with self.subTest(mode=mode), self.assertRaises(F.SeedError): self.read()
            self.assertIsNotNone(self.owner.original)

    def test_real_size_overflow_after_adoption_preserves_resource_for_cleanup(self):
        self.tree.sizes[F.INPUTS[0]] = F.authority.MAX_XML_BYTES + 1
        with self.assertRaisesRegex(C.CompatibilityError, "SOURCE_SIZE"): self.read()
        file_row, = (row for row in self.owner.resources if row[0] == "dependency-seed-input")
        self.assertFalse(file_row[2])  # F._Owners did not receive the refused return.
        self.assertEqual(self.tree.reads, [])
        self.owner.close()
        self.assertTrue(file_row[3])

    def test_repeated_actual_size_reservations_share_the_same64mib_bound(self):
        borrowed = C.borrowed_sources(self.owner, self.owner.check)
        for number, name in enumerate(C.PROVIDER_INPUTS[:65]):
            self.tree.sizes[name] = F.authority.MAX_XML_BYTES
            if number < 64:
                borrowed.acquire("dependency-seed-input", lambda name=name: ModelFile(self.tree, name))
            else:
                with self.assertRaisesRegex(C.CompatibilityError, "SOURCE_TOTAL_BYTES"):
                    borrowed.acquire("dependency-seed-input", lambda: ModelFile(self.tree, name))
        self.assertEqual((borrowed.bytes, len(self.owner.resources), self.tree.reads), (C.TOTAL_LIMIT, 65, []))
        self.owner.close()
        self.assertTrue(all(row[3] for row in self.owner.resources))

    def test_original_read_error_wins_over_unknown_close_without_retry(self):
        self.tree.failed = self.tree.close_failed = C.PROVIDER_INPUTS[0]
        with self.assertRaises(RuntimeError) as caught: self.read()
        self.assertIs(caught.exception, self.tree.read_error)
        self.assertIs(self.owner.original, self.tree.read_error)
        self.assertTrue(self.owner.unknown)
        failed, = (row[1] for row in self.owner.resources if isinstance(row[1], ModelFile) and
            row[1].relative == self.tree.failed)
        self.assertEqual(failed.close_calls, 1)

    def test_original_end_refusal_is_not_a_new_window(self):
        self.owner.refuse_at = 2
        with self.assertRaises(RuntimeError) as caught: self.read()
        self.assertIs(caught.exception, self.owner.refusal)
        self.assertIs(self.owner.original, self.owner.refusal)
        self.owner.close()
        self.assertTrue(all(row[3] for row in self.owner.resources))


if __name__ == "__main__":
    unittest.main(failfast=True)
