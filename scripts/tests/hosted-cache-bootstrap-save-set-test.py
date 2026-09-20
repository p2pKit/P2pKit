#!/usr/bin/env python3
"""Pre/post save-set controls using memory-backed files, never native I/O.

The changed shared driver, new leaf and shared read/hash/roster definitions run.
Original admission/predecessor/source/native/copy suppliers remain explicit
models. Imported export classes cover the changed driver, not a hosted rerun.
Post checks use an explicit NEW memory owner and supplied before-save records;
there is no original-call after-save parent or provider execution in this fixture.
"""
import ast
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
import unittest


ROOT = Path(__file__).resolve().parents[1]
old = runpy.run_path(str(ROOT / "tests/hosted-cache-bootstrap-export-test.py"), run_name="export_models")
selected, require = old["selected"], old["require"]
Refusal, FalseyFailure = old["Refusal"], old["FalseyFailure"]
OriginalReturnModels, ExportModels = old["OriginalReturnModels"], old["ExportModels"]
SAVE = selected(ROOT / "hosted_cache_bootstrap_save_set.py",
    {"SaveSetEvidence", "_Window", "_AfterWindow", "before_save", "after_save", "_observe"})
READ = selected(ROOT / "hosted_cache_bootstrap_staging.py", {"_read"})
FILES = selected(ROOT / "hosted_dependency_seed_files.py", {"_info_binding", "_hash"})
ROSTER = selected(ROOT / "hosted_dependency_cache.py", {"_save_roster"})


def cells(function):
    return dict(zip(function.__code__.co_freevars, (cell.cell_contents for cell in function.__closure__)))


@dataclass(frozen=True)
class Info:
    identity: tuple
    size: int
    stamp: int

    def as_dict(self):
        return {"identity": list(self.identity), "size": self.size, "stamp": self.stamp}


class Node:
    def __init__(self, identity, data=None):
        self.identity, self.data, self.stamp, self.children = identity, data, 1, {}

    def info(self):
        return Info(self.identity, 0 if self.data is None else len(self.data), self.stamp)


class World(old["World"]):
    def __init__(self, payload=b"abc"):
        super().__init__()
        self.payload = payload
        for item in self.compiled.artifacts:
            item.sha256 = hashlib.sha256(payload).hexdigest()
        self.start_candidate, self.finish_candidate = 89.0, 95.0
        self.phase, self.freeze_calls = "export", 0
        self.before_hook = self.before_return_hook = self.read_hook = self.verify_hook = self.names_hook = lambda *args: None
        self.nodes = {name: Node(identity) for name, identity in self.ids.items()}
        self.nodes["repo"].children["scripts"] = self.nodes["scripts"]
        self.nodes["container"].children["restore-home"] = self.nodes["restore-home"]
        self.next_identity = 1000
        world = self

        class Directory:
            def __init__(self, name):
                self.name = name if type(name) is str else "nested"
                self.node = world.nodes[name] if type(name) is str else name
                self.identity, self.closes = self.node.identity, 0
                world.opened.append(self)

            def open_directory(self, name, *, deadline):
                require(world.monotonic() < deadline, "MODEL_DEADLINE")
                node = self.node.children[name]
                require(node.data is None, "MODEL_NOT_DIRECTORY")
                return Directory(node)

            def open_file(self, name, *, max_bytes, deadline):
                require(world.monotonic() < deadline, "MODEL_DEADLINE")
                node = self.node.children[name]
                require(node.data is not None and len(node.data) <= max_bytes, "MODEL_NOT_FILE_OR_LIMIT")
                return File(node, name)

            def names(self, *, max_names, deadline):
                world.names_hook(self)
                require(world.monotonic() < deadline and len(self.node.children) <= max_names, "MODEL_NAMES_BOUND")
                return tuple(sorted(self.node.children))

            def verify(self):
                world.verify_hook(self)
                return self.node.info()

            def close(self):
                self.closes += 1
                world.close_hook(self)

        class File:
            def __init__(self, value, name="ephemeral"):
                self.name = value if type(value) is str else name
                self.node = world.node(b"") if type(value) is str else value
                self.identity, self.closes, self.offset = self.node.identity, 0, 0
                self.initial_info = self.node.info()
                world.opened.append(self)

            def read(self, size):
                world.read_hook(self)
                raw = self.node.data[self.offset:self.offset + size]
                self.offset += len(raw)
                return raw

            def verify(self):
                world.verify_hook(self)
                return self.node.info()

            def close(self):
                self.closes += 1
                world.close_hook(self)

        self.Directory, self.File = Directory, File
        self.files.PosixPrivateDirectory = self.files.PosixSourceDirectory = Directory
        self.files.PosixFile = File
        self.files.public_root = self.files.private_root = Directory
        self.files.BLOCK, self.files.NAMES_LIMIT = 65536, 10000
        self.namespace["windows"] = NS(PrivateDirectory=Directory, DependencySourceDirectory=Directory, NativeFile=File)
        helpers = {"require": require, "digest": self.origin.digest, "encoded": self.encode,
                   "hashlib": hashlib, "BLOCK": self.files.BLOCK}
        exec(FILES, helpers)
        self.files._hash, self.files._info_binding = helpers["_hash"], helpers["_info_binding"]
        helpers = {"require": require, "files": self.files}
        exec(READ, helpers)
        self.staging._read = helpers["_read"]
        helpers = {}
        exec(ROSTER, helpers)
        self.staging.cache._save_roster = helpers["_save_roster"]

        for name in ("hosted_cache_bootstrap_export.py", "hosted_cache_bootstrap_custody.py",
                     "hosted_dependency_cache.py", "hosted_cache_bootstrap_save_set.py"):
            self.nodes["scripts"].children[name] = self.node(name.encode())
        for directory, name, data in (("session", "initializer-context.json", b"initializer"),
                ("state", "context.json", b"canonical"), ("gradle-home", "gradle.properties", b"properties"),
                ("container", "staging.json", b"original-stage")):
            self.nodes[directory].children[name] = self.node(data)
        original_init = self.Inputs.__init__

        def inputs_init(value, *args):
            original_init(value, *args)
            value.proposal["phaseFencesNs"]["save-set-before"] = 850 * old["NS_SECOND"]
            value.proposal["phaseFencesNs"]["save-set-after"] = 880 * old["NS_SECOND"]
            value.stage["containerIdentity"] = list(world.ids["container"])
            for key, directory, name in (("initializer-context", "session", "initializer-context.json"),
                    ("canonical-context", "state", "context.json"), ("properties", "gradle-home", "gradle.properties"),
                    ("staging", "container", "staging.json")):
                value.seed_value["fileBindings"][key] = world.binding(world.nodes[directory].children[name])

        self.Inputs.__init__ = inputs_init
        # Bind the shared export loop's explicit candidate-copy model to memory
        # nodes with real hashlib digests. This is not a native copy operation.
        copy_namespace = cells(self.files._copy_allowlisted)["actual"].__globals__
        candidate = copy_namespace["_copy_candidate"]

        def copy_candidate(*args):
            status, row = candidate(*args)
            if row is not None:
                row["size"] = len(world.payload)
                row["sha1"] = hashlib.sha1(world.payload).hexdigest()
                parts = row["path"].split("/")
                parts[-2] = row["sha1"]
                row["path"] = "/".join(parts)
                args[6]["prehashBytes"] += len(world.payload) - 3
                args[6]["outputBytes"] += len(world.payload) - 3
                node = world.nodes["restore-home"]
                for name in parts[:-1]:
                    if name not in node.children:
                        node.children[name] = world.node()
                    node = node.children[name]
                node.children[parts[-1]] = world.node(world.payload)
                row["destination"] = world.binding(node.children[parts[-1]])
            return status, row

        copy_namespace["_copy_candidate"] = copy_candidate
        namespace = {"dataclass": dataclass, "field": field, "custody": self.custody, "staging": self.staging,
            "files": self.files, "origin": self.origin, "dependency_export": self.export,
            "SCOPE": "BOOTSTRAP_SAVE_SET_BEFORE_LEAF_V1", "STATUSES": ("KNOWN_FROZEN",),
            "AFTER_SCOPE": "BOOTSTRAP_SAVE_SET_AFTER_LEAF_V1", "AFTER_STATUS": "KNOWN_UNCHANGED"}
        exec(SAVE, namespace)
        self.save_namespace = namespace
        self.save = NS(**{name: namespace[name] for name in
            ("SaveSetEvidence", "_Window", "_AfterWindow", "after_save", "SCOPE", "STATUSES", "AFTER_SCOPE", "AFTER_STATUS")})
        actual = namespace["before_save"]

        def freeze(owner, inputs, window, raw):
            world.phase, world.freeze_calls = "before", world.freeze_calls + 1
            world.freeze_owner, world.freeze_window, world.freeze_inputs = owner, window, inputs
            world.export_raw = raw
            world.before_hook(owner, inputs, window)
            result = actual(owner, inputs, window, raw)
            world.before_return_hook(result)
            return result

        self.save.before_save = freeze
        self.namespace["dependency_save_set"] = self.save
        self.run, self.before = self.namespace["_bootstrap_export_controls"]()
        self.namespace.update(export_after_entry=self.run, before_save_after_entry=self.before)

    def node(self, data=None):
        self.next_identity += 1
        return Node((1, self.next_identity), data)

    def binding(self, node):
        return self.files._info_binding(node.info())

    def before_state(self):
        return cells(cells(self.before)["drive"])["before_calls"][id(self.transition)]

    def original_check(self):
        return cells(cells(self.before)["drive"])["closed_export_return"]

    def exported_file(self):
        row = json.loads(self.export_raw)["admitted"][0]
        node = self.nodes["restore-home"]
        for part in row["path"].split("/"):
            node = node.children[part]
        return node


class BeforeSaveModels(unittest.TestCase):
    def test_original_export_then_complete_positive_partial_set(self):
        world = World()
        result = world.before(world.transition)
        value = json.loads(result.leaf.raw)
        self.assertEqual((world.original_calls, world.copy_calls, world.freeze_calls), (1, 1, 1))
        self.assertEqual(value["status"], "KNOWN_FROZEN")
        self.assertEqual(value["counts"], {"hashedBytes": 3, "verifiedFiles": 1, "members": 8})
        self.assertEqual(value["exportSha256"], hashlib.sha256(world.export_raw).hexdigest())
        self.assertFalse(value["atomicSnapshot"] or value["exportSaveAuthority"])
        self.assertTrue(all(item.closes == 1 for item in world.opened))
        self.assertEqual(world.signals, world.original_signals)
        self.assertIsNot(world.owner, world.freeze_owner)
        self.assertGreaterEqual(world.freeze_window.first, world.state()["result"].checked_ns)
        self.assertGreaterEqual(world.freeze_window.local_start, world.state()["result"].checked_local)

    def test_export_checker_is_passive_repeatable_original_only(self):
        world = World()
        result = world.run(world.transition)
        world.clock_hook = lambda: self.fail("closed checker sampled a clock")
        self.assertIs(world.original_check()(world.transition, result), world.bound)
        self.assertIs(world.original_check()(world.transition, result), world.bound)
        with self.assertRaises(Refusal):
            world.original_check()(world.transition, type(result)(result.raw, result.leaf, result.checked_ns, result.checked_local))

    def test_export_checker_refuses_replaced_public_dictionary(self):
        world = World()
        result = world.run(world.transition)
        object.__setattr__(result, "__dict__", vars(result).copy())
        with self.assertRaises(Refusal):
            world.original_check()(world.transition, result)

    def test_export_checker_refuses_mutated_leaf_and_late_cancel(self):
        world = World()
        result = world.run(world.transition)
        object.__setattr__(result.leaf, "checked_ns", result.leaf.checked_ns + 1)
        with self.assertRaises(Refusal):
            world.original_check()(world.transition, result)
        other = World()
        returned = other.run(other.transition)
        other.state()["cancelled"].append(2)
        with self.assertRaises(Refusal):
            other.original_check()(other.transition, returned)

    def test_separately_called_export_cannot_be_adopted(self):
        world = World()
        world.run(world.transition)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual((world.original_calls, world.copy_calls, world.freeze_calls), (1, 1, 0))

    def test_before_claim_precedes_original_and_reentry_does_not_deadlock(self):
        world = World()
        world.callback_hook = lambda: world.before(world.transition)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual(world.original_calls, 1)
        self.assertEqual(world.freeze_calls, 0)

    def test_replaced_public_export_operation_refuses_before_original(self):
        world = World()
        world.namespace["export_after_entry"] = lambda value: None
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual(world.original_calls, 0)

    def test_failed_export_never_starts_before_save_or_retries(self):
        world = World()
        failure = world.initial_failure = FalseyFailure()
        with self.assertRaises(FalseyFailure) as caught:
            world.before(world.transition)
        self.assertIs(caught.exception, failure)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual((world.original_calls, world.freeze_calls), (1, 0))

    def test_empty_export_cannot_freeze(self):
        world = World()
        world.start_candidate = 90.0
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertIsNone(world.before_state()["result"])

    def test_zero_byte_artifact_cannot_freeze(self):
        world = World(payload=b"")
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual(json.loads(world.state()["result"].leaf.raw)["counts"]["outputBytes"], 0)
        self.assertIsNone(world.before_state()["result"])

    def test_unexpected_empty_directory_cannot_be_ignored(self):
        world = World()
        world.before_hook = lambda *args: world.nodes["restore-home"].children.update(extra=world.node())
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_missing_exported_member_refuses(self):
        world = World()
        world.before_hook = lambda *args: world.nodes["restore-home"].children.clear()
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertIsNone(world.before_state()["result"])

    def test_changed_bytes_with_same_modeled_stamp_refuse_hash(self):
        world = World()
        world.before_hook = lambda *args: setattr(world.exported_file(), "data", b"bad")
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_replaced_exported_file_identity_refuses(self):
        world = World()
        world.before_hook = lambda *args: setattr(world.exported_file(), "identity", (1, 99999))
        with self.assertRaises(Refusal):
            world.before(world.transition)

    def test_alias_to_exported_file_cannot_be_an_ancestor(self):
        world = World()
        def alias(*args):
            world.nodes["restore-home"].children["caches"].identity = world.exported_file().identity
        world.before_hook = alias
        with self.assertRaises(Refusal):
            world.before(world.transition)

    def test_changed_staging_bytes_refuse(self):
        world = World()
        world.before_hook = lambda *args: setattr(world.nodes["container"].children["staging.json"], "data", b"changed")
        with self.assertRaises(Refusal):
            world.before(world.transition)

    def test_changed_export_source_refuses(self):
        world = World()
        world.before_hook = lambda *args: setattr(world.nodes["scripts"].children["hosted_cache_bootstrap_export.py"],
                                                "data", b"changed")
        with self.assertRaises(Refusal):
            world.before(world.transition)

    def test_final_membership_reenumeration_detects_added_directory(self):
        world = World()
        def change(reader):
            if world.phase == "before" and reader.name == "artifact.jar":
                world.nodes["restore-home"].children["late"] = world.node()
        world.read_hook = change
        with self.assertRaises(Refusal):
            world.before(world.transition)

    def test_exact_new_work90_cannot_publish_partial_roster(self):
        world = World()
        world.before_hook = lambda _owner, _inputs, window: setattr(world, "seconds", window.local_start - 100.0 + 90.0)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertIsNone(world.before_state()["result"])
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_hash_completion_after90_does_not_skip_remaining_roster(self):
        world = World()
        def begin(*args):
            world.seconds = 184.0
        world.before_hook = begin
        def late(reader):
            if world.phase == "before" and reader.name == "artifact.jar":
                world.seconds = 187.0
        world.read_hook = late
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertIsNone(world.before_state()["result"])

    def test_completed_reads_can_finish_serialization_before_hard120(self):
        world = World()
        def late(value):
            if type(value) is dict and value.get("scope") == world.save.SCOPE and value.get("completed") is True:
                world.seconds = 214.0
        world.encode_hook = late
        self.assertEqual(json.loads(world.before(world.transition).leaf.raw)["status"], "KNOWN_FROZEN")

    def test_exact_hard120_cannot_publish(self):
        world = World()
        def late(value):
            if type(value) is dict and value.get("scope") == world.save.SCOPE and value.get("completed") is True:
                world.seconds = 215.0
        world.encode_hook = late
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_mutated_original_window_fence_cannot_be_extended(self):
        world = World()
        def shorter(inputs):
            # The fixed window has already captured its original fence; any
            # mutation of the window itself must refuse, not renew it.
            world.before_state()["window"].hard += old["NS_SECOND"]
        world.before_hook = lambda _owner, inputs, _window: shorter(inputs)
        with self.assertRaises(Refusal):
            world.before(world.transition)

    def test_original_shorter_phase_fence_cannot_be_replaced_with120(self):
        world = World()
        original = world.Inputs.__init__
        def shorter(value, *args):
            original(value, *args)
            value.proposal["phaseFencesNs"]["save-set-before"] = 605 * old["NS_SECOND"]
        world.Inputs.__init__ = shorter
        world.before_hook = lambda *args: setattr(world, "seconds", 106.0)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual(world.freeze_window.hard, 605 * old["NS_SECOND"])
        self.assertIsNone(world.before_state()["result"])

    def test_local90_alone_refuses_new_freeze_work(self):
        world = World()
        world.before_hook = lambda *args: setattr(world, "local_extra", 90.0)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual(world.freeze_window.last, 595 * old["NS_SECOND"])
        self.assertIsNone(world.before_state()["result"])

    def test_export_owned_handle_is_not_borrowed_or_closed_again(self):
        world = World()
        saved = []
        def borrow(owner, *args):
            value = world.state()["returns"][0]
            saved.append(value)
            owner.acquire("borrowed", lambda: value)
        world.before_hook = borrow
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertEqual(saved[0].closes, 1)
        self.assertTrue(world.before_state()["unknown"])

    def test_falsey_read_failure_survives_annotation_and_cleanup(self):
        world = World()
        failure = FalseyFailure()
        def fail(reader):
            if world.phase == "before" and reader.name == "artifact.jar":
                raise failure
        world.read_hook = fail
        with self.assertRaises(FalseyFailure) as caught:
            world.before(world.transition)
        self.assertIs(caught.exception, failure)
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_unknown_close_stops_new_phase_operations(self):
        world = World()
        failure = Refusal("MODELED_CLOSE_UNKNOWN")
        def close(value):
            if world.phase == "before":
                raise failure
        world.close_hook = close
        with self.assertRaises(Refusal) as caught:
            world.before(world.transition)
        self.assertIs(caught.exception, failure)
        self.assertTrue(world.before_state()["unknown"])
        self.assertTrue(world.quarantine)
        self.assertTrue(all(item.closes <= 1 for item in world.opened))

    def test_final_parent_encoding_cancellation_refuses(self):
        world = World()
        def cancel(value):
            if type(value) is dict and value.get("scope") == "BOOTSTRAP_SAVE_SET_PARENT_CLOSED_OBSERVATIONS_V1":
                world.before_state()["cancelled"].append(2)
        world.encode_hook = cancel
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_changed_before_save_leaf_return_refuses(self):
        world = World()
        world.before_return_hook = lambda result: object.__setattr__(result, "checked_local", False)
        with self.assertRaises(Refusal):
            world.before(world.transition)
        self.assertIsNone(world.before_state()["result"])

    def test_no_ordinary_save_context_or_provider_is_available(self):
        world = World()
        world.before(world.transition)
        self.assertNotIn("save_set", vars(world.staging.cache))
        self.assertNotIn("provider_observation", vars(world.staging.cache))
        self.assertNotIn("dependencySeed", vars(world.freeze_inputs))
        self.assertNotIn("primaryAbiAccounting", vars(world.freeze_inputs))


class AfterWorld(World):
    """Supplied-record leaf model; deliberately not the future provider parent."""
    def __init__(self):
        super().__init__()
        self.frozen = self.before(self.transition)
        self.frozen_raw, self.previous_raw = self.frozen.leaf.raw, self.frozen.raw
        self.phase, self.seconds = "after", self.seconds + 1.0
        self.after_hook = lambda *args: None
        self.after_cancelled = False
        world = self

        class MemoryOwner:
            def __init__(self):
                self.resources, self.original = [], None
                self.closed = self.unknown = False
                self.cancelled = lambda: require(not world.after_cancelled, "MODELED_AFTER_CANCELLED")

            def error(self, stage, failure, *, unknown=False):
                if self.original is None:
                    self.original = failure
                self.unknown |= unknown

            def end(self):
                require(not self.closed and not self.unknown, "MODELED_AFTER_NOT_LIVE")
                self.cancelled()
                return world.after_window.local_hard

            def acquire(self, label, factory):
                self.end()
                value = factory()
                self.resources.append({"owner": value, "attempted": False, "closed": False})
                return value

            def close_one(self, value):
                row = next(row for row in self.resources if row["owner"] is value)
                if row["attempted"]:
                    return
                require(not self.unknown, "MODELED_AFTER_UNKNOWN")
                row["attempted"] = True
                try:
                    value.close()
                    row["closed"] = True
                except BaseException as failure:
                    self.error("close", failure, unknown=True)
                    raise

        self.after_owner = MemoryOwner()

    def change_frozen(self, change, *, rebind=True):
        value = json.loads(self.frozen_raw)
        change(value)
        self.frozen_raw = self.encode(value)
        if rebind:
            # Deliberately coherent supplied records reach semantic guards.
            # This is not a claim that the original-call parent would adopt them.
            previous = json.loads(self.previous_raw)
            previous["leafSha256"] = self.origin.digest(self.frozen_raw)
            self.previous_raw = self.encode(previous)

    def recheck(self):
        phase = self.staging.PhaseStart(self.observe(), self.monotonic())
        self.after_window = self.save._AfterWindow(self.freeze_inputs, phase,
            (self.previous_raw, self.frozen.checked_ns, self.frozen.checked_local))
        self.after_hook(self.after_window)
        return self.save.after_save(self.after_owner, self.freeze_inputs, self.after_window,
                                    self.export_raw, self.frozen_raw)


class AfterSaveModels(unittest.TestCase):
    def test_complete_positive_subset_matches_original_before_bytes(self):
        world = AfterWorld()
        result = world.recheck()
        value, before = json.loads(result.raw), json.loads(world.frozen_raw)
        self.assertEqual((value["scope"], value["status"], value["phase"]),
                         (world.save.AFTER_SCOPE, "KNOWN_UNCHANGED", "after-save"))
        self.assertEqual(value["beforeSaveSha256"], world.origin.digest(world.frozen_raw))
        for name in ("container", "stagingFile", "directories", "files", "counts", "saveSetInputs"):
            self.assertEqual(value[name], before[name])
        self.assertFalse(value["atomicSnapshot"] or value["exportSaveAuthority"] or value["nextPhaseAuthority"])
        self.assertEqual((value["budgetAcceptance"], value["testAcceptance"]), ("NOT_ADMITTED", "NOT_PERFORMED"))
        self.assertIsNot(world.freeze_owner, world.after_owner)
        self.assertGreater(world.after_window.first, world.frozen.checked_ns)
        self.assertGreater(world.after_window.local_start, world.frozen.checked_local)
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_after_cannot_reuse_before_window(self):
        world = AfterWorld()
        with self.assertRaises(Refusal):
            world.save.after_save(world.after_owner, world.freeze_inputs, world.freeze_window,
                                  world.export_raw, world.frozen_raw)
        self.assertEqual(world.after_owner.resources, [])

    def test_before_cannot_accept_after_window(self):
        world = AfterWorld()
        def refuse(window):
            with self.assertRaises(Refusal):
                world.save_namespace["before_save"](world.after_owner, world.freeze_inputs, window, world.export_raw)
        world.after_hook = refuse
        world.recheck()

    def test_original_before_bytes_are_required(self):
        for raw in (None, b"", {}, bytearray(b"{}")):
            with self.subTest(kind=type(raw).__name__):
                world = AfterWorld()
                world.frozen_raw = raw
                with self.assertRaises(Refusal):
                    world.recheck()
                self.assertEqual(world.after_owner.resources, [])

    def test_changed_before_bytes_cannot_replace_original_digest(self):
        world = AfterWorld()
        world.change_frozen(lambda value: value.update(extra=True), rebind=False)
        with self.assertRaisesRegex(Refusal, "BOOTSTRAP_SAVE_EXPORT_PREDECESSOR"):
            world.recheck()
        self.assertEqual(world.after_owner.resources, [])

    def test_failed_or_wrong_phase_before_record_cannot_qualify(self):
        for field, value in (("status", "FAILED"), ("completed", False), ("retirement", "UNKNOWN"),
                ("errors", ["failure"]), ("phase", "after-save"), ("beforeSaveSha256", "f" * 64)):
            with self.subTest(field=field):
                world = AfterWorld()
                world.change_frozen(lambda record: record.update({field: value}))
                with self.assertRaises(Refusal):
                    world.recheck()
                self.assertEqual(world.after_owner.resources, [])

    def test_coherent_supplied_before_cannot_change_input_or_authority(self):
        for field, value in (("binding", {}), ("plan", {}), ("exportSha256", "f" * 64),
                ("schema", True), ("exportSaveAuthority", True), ("budgetAcceptance", "ADMITTED")):
            with self.subTest(field=field):
                world = AfterWorld()
                world.change_frozen(lambda record: record.update({field: value}))
                with self.assertRaises(Refusal):
                    world.recheck()
                self.assertEqual(world.after_owner.resources, [])

    def test_coherent_supplied_before_cannot_change_complete_roster(self):
        for field, value in (("directories", []), ("files", []), ("counts", {}), ("saveSetInputs", {})):
            with self.subTest(field=field):
                world = AfterWorld()
                world.change_frozen(lambda record: record.update({field: value}))
                with self.assertRaisesRegex(Refusal, "BOOTSTRAP_SAVE_FROZEN_SET_CHANGED"):
                    world.recheck()
                self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_before_window_scope_clock_fence_and_types_are_rederived(self):
        for field, value in (("phase", "save-set-after"), ("clock", {}), ("proposalSha256", "f" * 64),
                ("predecessorSha256", "f" * 64), ("firstNs", True), ("hardEndNs", 999 * old["NS_SECOND"]),
                ("softEndNs", 999 * old["NS_SECOND"]), ("finishedNs", 999 * old["NS_SECOND"]),
                ("lastNewWorkNs", 999 * old["NS_SECOND"]), ("predecessorCheckedNs", 999 * old["NS_SECOND"])):
            with self.subTest(field=field):
                world = AfterWorld()
                world.change_frozen(lambda record: record["window"].update({field: value}))
                with self.assertRaises(Refusal):
                    world.recheck()
                self.assertEqual(world.after_owner.resources, [])

    def test_before_parent_must_match_its_original_fences_and_close(self):
        for field, value in (("scope", "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1"),
                ("closedNs", 999 * old["NS_SECOND"]), ("softEndNs", 999 * old["NS_SECOND"])):
            with self.subTest(field=field):
                world = AfterWorld()
                previous = json.loads(world.previous_raw)
                previous[field] = value
                world.previous_raw = world.encode(previous)
                with self.assertRaises(Refusal):
                    world.recheck()

    def test_same_identity_ancestor_stamp_change_cannot_be_new_baseline(self):
        world = AfterWorld()
        world.nodes["restore-home"].children["caches"].stamp += 1
        with self.assertRaisesRegex(Refusal, "BOOTSTRAP_SAVE_FROZEN_SET_CHANGED"):
            world.recheck()

    def test_extra_empty_directory_cannot_be_ignored(self):
        world = AfterWorld()
        world.nodes["restore-home"].children["extra"] = world.node()
        with self.assertRaises(Refusal):
            world.recheck()

    def test_missing_member_cannot_be_a_partial_after_check(self):
        world = AfterWorld()
        world.nodes["restore-home"].children.clear()
        with self.assertRaises(Refusal):
            world.recheck()

    def test_changed_bytes_with_unchanged_model_stamp_fail_hash(self):
        world = AfterWorld()
        world.exported_file().data = b"bad"
        with self.assertRaisesRegex(Refusal, "BOOTSTRAP_SAVE_BYTES_CHANGED"):
            world.recheck()

    def test_replaced_file_identity_or_staging_stamp_refuses(self):
        for target in ("file", "staging"):
            with self.subTest(target=target):
                world = AfterWorld()
                if target == "file":
                    world.exported_file().identity = (1, 99999)
                else:
                    world.nodes["container"].children["staging.json"].stamp += 1
                with self.assertRaises(Refusal):
                    world.recheck()

    def test_changed_save_checker_source_cannot_replace_original_source(self):
        world = AfterWorld()
        world.nodes["scripts"].children["hosted_cache_bootstrap_save_set.py"].data = b"changed"
        with self.assertRaisesRegex(Refusal, "BOOTSTRAP_SAVE_FROZEN_SET_CHANGED"):
            world.recheck()

    def test_late_extra_member_is_caught_by_complete_reenumeration(self):
        world = AfterWorld()
        def late(reader):
            if reader.name == "artifact.jar":
                world.nodes["restore-home"].children["late"] = world.node()
        world.read_hook = late
        with self.assertRaises(Refusal):
            world.recheck()

    def test_raw90_refuses_new_work_without_partial_success(self):
        world = AfterWorld()
        world.after_hook = lambda window: setattr(world, "seconds", world.seconds + 90.0)
        with self.assertRaises(Refusal):
            world.recheck()
        self.assertEqual(world.after_owner.resources, [])

    def test_local90_alone_refuses_new_work(self):
        world = AfterWorld()
        world.after_hook = lambda window: setattr(world, "local_extra", 90.0)
        with self.assertRaises(Refusal):
            world.recheck()
        self.assertEqual(world.after_window.last, world.after_window.first)

    def test_hard120_in_final_serialization_cannot_publish(self):
        world = AfterWorld()
        def late(value):
            if type(value) is dict and value.get("scope") == world.save.AFTER_SCOPE and value.get("completed") is True:
                world.seconds = world.after_window.local_start - 100.0 + 120.0
        world.encode_hook = late
        with self.assertRaises(Refusal):
            world.recheck()
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_original_shorter_after_fence_is_not_replaced_by120(self):
        world = AfterWorld()
        world.freeze_inputs.proposal["phaseFencesNs"]["save-set-after"] = 600 * old["NS_SECOND"]
        world.after_hook = lambda window: setattr(world, "seconds", 100.0)
        with self.assertRaises(Refusal):
            world.recheck()
        self.assertEqual(world.after_window.hard, 600 * old["NS_SECOND"])

    def test_falsey_first_read_failure_survives_known_cleanup(self):
        world = AfterWorld()
        failure = FalseyFailure()
        def fail(reader):
            if reader.name == "artifact.jar":
                raise failure
        world.read_hook = fail
        with self.assertRaises(FalseyFailure) as caught:
            world.recheck()
        self.assertIs(caught.exception, failure)
        self.assertTrue(all(item.closes == 1 for item in world.opened))

    def test_unknown_close_stops_following_owner_operations(self):
        world = AfterWorld()
        failure = Refusal("MODELED_AFTER_CLOSE_UNKNOWN")
        world.close_hook = lambda value: (_ for _ in ()).throw(failure)
        with self.assertRaises(Refusal) as caught:
            world.recheck()
        self.assertIs(caught.exception, failure)
        self.assertTrue(world.after_owner.unknown)
        self.assertTrue(all(item.closes <= 1 for item in world.opened))

    def test_final_cancellation_cannot_publish(self):
        world = AfterWorld()
        def cancel(value):
            if type(value) is dict and value.get("scope") == world.save.AFTER_SCOPE and value.get("completed") is True:
                world.after_cancelled = True
        world.encode_hook = cancel
        with self.assertRaises(Refusal):
            world.recheck()

    def test_observation_has_no_provider_or_ordinary_context(self):
        world = AfterWorld()
        world.recheck()
        self.assertNotIn("provider_observation", vars(world.staging.cache))
        self.assertNotIn("save_set", vars(world.staging.cache))
        self.assertNotIn("primaryAbiAccounting", vars(world.freeze_inputs))
        self.assertFalse(world.after_owner.closed)  # Leaf close is not enclosing-owner retirement.


if __name__ == "__main__":
    unittest.main()
