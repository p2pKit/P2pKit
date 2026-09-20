#!/usr/bin/env python3
"""Focused AST/memory controls; no full controller, native I/O or provider.

The new export code, shared leaf/window and shared copy loop execute. Admission,
upstream returns, source reads, native files, copy/hash operations and inventory
bindings are explicit models. Model elapsed time is not scheduling evidence.
"""
import ast
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import threading
from types import SimpleNamespace as NS
import unittest


ROOT = Path(__file__).resolve().parents[1]


def selected(path, names):
    tree = ast.parse(path.read_text())
    nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    assert len(nodes) == len(names)
    return compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec", dont_inherit=True)


PARENT = selected(ROOT / "run-hosted-cache-bootstrap.py",
    {"BootstrapExportPrefix", "BootstrapSaveSetPrefix", "_bootstrap_export_controls"})
NO_LOADER = selected(ROOT / "run-hosted-cache-bootstrap.py", {"NoLoaderPrefix", "_no_loader_parent_controls"})
EXPORT = selected(ROOT / "hosted_cache_bootstrap_export.py", {"ExportEvidence", "_Window", "export_snapshot"})
SHARED = selected(ROOT / "hosted_cache_bootstrap_staging.py", {"_Window", "_Leaf"})
COPY = selected(ROOT / "hosted_dependency_seed_files.py", {"_copy_allowlisted", "_validate_inventory"})
HELPERS = selected(ROOT / "tests/hosted-cache-bootstrap-no-loader-parent-test.py",
    {"Refusal", "FalseyFailure", "require", "integer", "local", "encoded", "Home", "Evidence", "Transition", "World"})
NS_SECOND = 1_000_000_000
helper_namespace = {"__name__": "original_return_models", "dataclass": dataclass, "field": field,
    "hashlib": hashlib, "json": json, "threading": threading, "NS": NS, "CODE": NO_LOADER,
    "NS_PER_SECOND": NS_SECOND}
exec(HELPERS, helper_namespace)
OldWorld = helper_namespace["World"]
Refusal, FalseyFailure = helper_namespace["Refusal"], helper_namespace["FalseyFailure"]
require, integer, local, encoded = (helper_namespace[name] for name in ("require", "integer", "local", "encoded"))


class Transition:
    pass


class World:
    def __init__(self):
        self.seconds = self.local_extra = 0.0
        self.start_candidate, self.finish_candidate = 1.0, 2.0
        self.clock = NS(role="linux-x64", domain="modeled-raw", ticks_per_second=NS_SECOND)
        self.clock_hook = self.local_hook = self.callback_hook = self.copy_hook = self.close_hook = lambda *args: None
        self.input_hook = self.return_hook = self.encode_hook = self.signal_hook = lambda *args: None
        self.changed = self.stage_nonempty = self.bad_properties = False
        self.initial_failure = None
        self.opened, self.events, self.copy_starts = [], [], []
        self.original_calls, self.copy_calls = 0, 0
        self.transition = Transition()
        self.previous = NS(raw=b"original-no-loader", checked_ns=499 * NS_SECOND, checked_local=99.0)
        saved = NS(originals=object(), original_pin=object(), callbacks=(self.callback,))
        last = NS(staged=object(), staged_pin=object())
        self.bound = NS(pin=NS(frame=NS(predecessor=NS(frame=saved, phases=((None, last),))), graph=NS(nodes=[])))
        self.quarantine = []
        self.signals = {2: object(), 15: object()}
        self.original_signals = self.signals.copy()
        self.ids = {name: (1, index + 1) for index, name in enumerate(
            ("repo", "scripts", "session", "state", "gradle-home", "evidence", "cancellations", "container", "restore-home"))}
        self.file_serial = 100
        self.compiled = NS(artifacts=tuple(NS(group="group", module="module" + str(i), version="1",
            name="artifact.jar", sha256=hashlib.sha256(b"abc").hexdigest()) for i in range(2)))
        world = self

        class Directory:
            def __init__(self, name):
                self.name, self.identity, self.closes = name, world.ids[name], 0
                world.opened.append(self)

            def open_directory(self, name, *, deadline):
                require(world.monotonic() < deadline, "NATIVE_DEADLINE")
                return Directory(name)

            def verify(self):
                return NS(identity=self.identity)

            def close(self):
                self.closes += 1
                world.close_hook(self)

        class File:
            def __init__(self, name):
                world.file_serial += 1
                self.name, self.identity, self.closes = name, (1, world.file_serial), 0
                world.opened.append(self)
                world.events.append(("file", name, world.seconds, world.local_extra))

            def close(self):
                self.closes += 1
                world.close_hook(self)

        self.Directory, self.File = Directory, File

        class Inputs:
            def __init__(self, *args):
                require(args == (saved.originals, saved.original_pin, last.staged, last.staged_pin), "ORIGINAL_INPUTS")
                world.input_hook(self)
                self.clock, self.profile, self.role = world.clock, "desktop", world.clock.role
                self.proposal = {"phaseFencesNs": {"dependency-export": 800 * NS_SECOND},
                                 "proposedJobEndNs": 900 * NS_SECOND}
                self.proposal_raw = b"original-proposal"
                self.directories = {name: world.ids[name] for name in
                    ("session", "state", "gradle-home", "evidence", "cancellations")}
                self.home, self.restore, self.container, self.session, self.root = "H", "S", "container", "session", "repo"
                self.admitted, self.staging_raw = NS(record=b"bootstrap-admission"), b"original-stage"
                self.context_raw, self.canonical_raw, self.properties_raw = b"initializer", b"canonical", b"properties"
                bindings = {key: {"original": key} for key in
                    ("initializer-context", "canonical-context", "properties", "staging")}
                self.seed_value = {"fileBindings": bindings}
                self.stage_value = {"plan": {"key": "exact-key"}, "inputs": {"original": "inputs"},
                    "bootstrapInputs": {"original": "bootstrap"}, "fileBindings": bindings}
                self.stage = {"sourceIdentity": list(world.ids["restore-home"])}

            def unchanged(self):
                require(not world.changed, "ORIGINAL_CHANGED")

            def binding(self):
                return {"original": "bootstrap-inputs"}

            def predecessors(self):
                return {"original": "empty-seed"}

        self.Inputs = Inputs
        clocks = NS(observe=self.observe, validate_reading=lambda value: value)
        self.origin = NS(require=require, OriginError=Refusal, NS=NS_SECOND, integer=integer, encoded=self.encode,
            digest=lambda raw: hashlib.sha256(raw).hexdigest(), parse=json.loads, clocks=clocks,
            clock_value=lambda value: vars(value).copy(), wire=NS(_directed_deadline=lambda start, seconds, end, now:
                start + min(seconds, (end - now) / NS_SECOND)))
        files = NS(SeedError=Refusal, RECEIPT_LIMIT=4 * 1024 * 1024, MEMBER_LIMIT=10000, FILE_LIMIT=512 * 1024 * 1024,
            TOTAL_LIMIT=2 * 1024 * 1024 * 1024, encoded=self.encode, digest=self.origin.digest,
            policy=lambda: {"fixture": "bounded-file-policy"}, public_root=Directory, private_root=Directory,
            validate_stage=lambda *args: require(args[6].identity == world.ids["restore-home"], "STAGE_IDENTITY"),
            PosixPrivateDirectory=Directory, PosixSourceDirectory=Directory, PosixFile=File)
        self.files = files
        shared = {"__name__": "shared_memory", "require": require, "files": files, "origin": self.origin,
            "NS": NS_SECOND, "time": NS(monotonic=self.monotonic), "_local": local,
            "_clock": lambda c: (c.role, c.domain, c.ticks_per_second),
            "_capture_phase": lambda p: ((p.first.clock.role, p.first.clock.domain, p.first.clock.ticks_per_second),
                                         p.first.nanoseconds, local(p.local_started))}
        exec(SHARED, shared)
        self.staging = NS(_Window=shared["_Window"], _Leaf=shared["_Leaf"], files=files, _local=local,
            _capture_phase=shared["_capture_phase"], PhaseStart=lambda first, value: NS(first=first, local_started=value),
            COUNTERS=("prehashBytes", "outputBytes", "sourceNames", "destinationMembers", "sha256Rejected", "layoutRejected"),
            _sources=self.sources, _initialized=self.initialized, _read=self.read, _names=self.names,
            cache=NS(validate_plan=lambda *args, **kwargs: require(kwargs["mode"] == "bootstrap", "BOOTSTRAP_MODE")))
        self.custody = NS(staging=self.staging, files=files, origin=self.origin, _Inputs=Inputs,
            _equal=lambda a, b, reason: require(encoded(a) == encoded(b), reason), _stage_readback=self.stage_readback)
        export_namespace = {"__name__": "export_memory", "dataclass": dataclass, "field": field,
            "custody": self.custody, "staging": self.staging, "files": files, "origin": self.origin,
            "SCOPE": "BOOTSTRAP_DEPENDENCY_EXPORT_LEAF_V1", "STATUSES": ("KNOWN_EMPTY", "KNOWN_PARTIAL", "KNOWN_EXPORTED")}
        exec(EXPORT, export_namespace)
        self.export_namespace = export_namespace
        self.export = NS(**{key: export_namespace[key] for key in ("ExportEvidence", "_Window", "SCOPE", "STATUSES")})
        actual_copy = export_namespace["export_snapshot"]

        def copy(owner, inputs, window):
            world.copy_calls += 1
            world.owner, world.window = owner, window
            result = actual_copy(owner, inputs, window)
            world.copy_return = result
            world.return_hook(result)
            return result

        self.export.export_snapshot = copy
        self.install_copier()
        namespace = {"__name__": "export_parent_memory", "dataclass": dataclass, "field": field,
            "threading": threading, "require": require, "origin": self.origin, "staging": self.staging,
            "custody": self.custody, "dependency_export": self.export, "NewEntryTransition": Transition,
            "dependency_save_set": NS(before_save=None, _Window=None, SaveSetEvidence=None, SCOPE=None, STATUSES=None),
            "observe_no_loader_after_entry": self.original, "_checked_no_loader_parent_return": self.checked,
            "diagnostics": NS(_exception_detail=lambda failure: {"retirementUnknown": False}, _QUARANTINE=[]),
            "query": NS(QUARANTINE=[]), "QUARANTINE": self.quarantine, "time": NS(monotonic=self.monotonic),
            "signal": NS(SIGINT=2, SIGTERM=15, getsignal=lambda number: self.signals[number], signal=self.set_signal),
            "windows": NS(PrivateDirectory=Directory, DependencySourceDirectory=Directory, NativeFile=File),
            "cancellation": lambda flags: require(not flags, "CANCELLED")}
        exec(PARENT, namespace)
        self.namespace = namespace
        self.run, self.before, self.checked_before = namespace["_bootstrap_export_controls"]()
        namespace.update(export_after_entry=self.run, before_save_after_entry=self.before,
                         _checked_before_save_parent_return=self.checked_before)

    def encode(self, value):
        self.encode_hook(value)
        return encoded(value)

    def state(self):
        cells = dict(zip(self.run.__code__.co_freevars, self.run.__closure__))
        driver = cells["drive"].cell_contents
        cells = dict(zip(driver.__code__.co_freevars, driver.__closure__))
        return cells["calls"].cell_contents[id(self.transition)]

    def original(self, transition):
        self.original_calls += 1
        require(transition is self.transition, "TRANSITION")
        if self.initial_failure is not None:
            raise self.initial_failure
        return self.previous

    def checked(self, transition, returned):
        require(transition is self.transition and returned is self.previous and not self.changed, "ORIGINAL_RETURN")
        return self.bound

    def callback(self):
        self.callback_hook()

    def monotonic(self):
        self.local_hook()
        return 100.0 + self.seconds + self.local_extra

    def observe(self):
        self.clock_hook()
        return NS(clock=self.clock, nanoseconds=500 * NS_SECOND + int(self.seconds * NS_SECOND))

    def set_signal(self, number, handler):
        self.signals[number] = handler
        self.signal_hook(number, handler)

    def sources(self, leaf, inputs):
        leaf.check(new=True)
        return inputs.stage_value["inputs"], self.compiled, inputs.stage_value["bootstrapInputs"]

    def initialized(self, leaf, inputs):
        return {name: leaf.acquire(name, lambda name=name: self.Directory(name)) for name in inputs.directories}

    def read(self, leaf, directory, name, *, expected=None, binding=None):
        leaf.end(new=True)
        reader = leaf.acquire(name, lambda: self.File(name))
        require(not (self.bad_properties and name == "gradle.properties"), "PROPERTIES_CHANGED")
        leaf.close_one(reader)
        leaf.check()
        return (expected if expected is not None else name.encode()), binding

    def names(self, leaf, directory, names):
        leaf.end(new=True)
        leaf.check()

    def stage_readback(self, leaf, inputs, container, output):
        require(not self.stage_nonempty, "STAGE_NOT_EMPTY")
        require(output.identity == tuple(inputs.stage["sourceIdentity"]), "STAGE_CHANGED")
        leaf.check(new=True)

    def install_copier(self):
        world = self
        prefix = ("caches", "modules-2", "files-2.1")
        bucket = hashlib.sha1(b"abc").hexdigest()

        class Lookup:
            def __init__(self, *args):
                self.observed = set(range(8))

            def coordinate(self, path):
                return self

            def names(self, path, *args):
                return (bucket,) if len(path) == 6 else ("artifact.jar",)

            def directory(self, path):
                return path

        class Destination:
            def __init__(self, owner, output, end, check, *, empty):
                require(empty, "EMPTY_DESTINATION")
                self.owner, self.created = owner, 0

            def verify(self, accepted):
                for row in accepted:
                    handle = self.owner.acquire("final-readback", lambda: world.File("final-readback"))
                    self.owner.close_one(handle)

        def candidate(owner, directory, artifact, address, index, destination, counts, end, check, reserve):
            world.copy_starts.append(world.seconds)
            world.seconds = world.finish_candidate
            world.copy_hook(owner)
            for name in ("writer", "readback"):
                handle = owner.acquire(name, lambda name=name: world.File(name))
                owner.close_one(handle)
            check()
            path = "/".join((*prefix, artifact.group, artifact.module, artifact.version, address, artifact.name))
            require(reserve(index, path, 3), "RECEIPT_BUDGET")
            destination.created = len(path.split("/"))
            counts["prehashBytes"] += 3
            counts["outputBytes"] += 3
            return "ADMITTED", {"index": index, "path": path, "size": 3, "sha256": artifact.sha256, "sha1": address,
                "source": {"identity": [1, 500], "stampSha256": "1" * 64},
                "destination": {"identity": [1, 501], "stampSha256": "2" * 64}}

        namespace = {"__name__": "copy_memory", "require": require, "encoded": encoded, "PREFIX": prefix,
            "_SourceLookup": Lookup, "_Destination": Destination, "_copy_candidate": candidate,
            "VERSION_LIMIT": 64, "MEMBER_LIMIT": 10000, "FILE_LIMIT": self.files.FILE_LIMIT,
            "TOTAL_LIMIT": self.files.TOTAL_LIMIT, "KNOWN": ("KNOWN_MISS", "KNOWN_PARTIAL", "KNOWN_SEEDED"),
            "_file_binding": lambda row: type(row) is dict and set(row) == {"identity", "stampSha256"},
            "re": __import__("re")}
        exec(COPY, namespace)
        actual = namespace["_copy_allowlisted"]

        def copy(*args, **kwargs):
            world.seconds = world.start_candidate
            return actual(*args, **kwargs)

        self.files._copy_allowlisted = copy
        self.files._validate_inventory = namespace["_validate_inventory"]


class OriginalReturnModels(unittest.TestCase):
    def test_original_return_is_readable_without_reexecution(self):
        world = OldWorld()
        result = world.run(world.transition)
        self.assertIs(world.closed_return(world.transition, result), world.bound)
        self.assertIs(world.closed_return(world.transition, result), world.bound)
        self.assertEqual((world.begin_calls, world.leaf_calls), (1, 1))

    def test_first_consumer_cannot_adopt_a_copied_return(self):
        world = OldWorld()
        result = world.run(world.transition)
        with self.assertRaises(Refusal):
            world.closed_return(world.transition, type(result)(result.raw, result.leaf, result.checked_ns, result.checked_local))

    def test_original_public_dictionary_replacement_refuses(self):
        world = OldWorld()
        result = world.run(world.transition)
        object.__setattr__(result, "__dict__", vars(result).copy())
        with self.assertRaises(Refusal):
            world.closed_return(world.transition, result)

    def test_mutated_return_clock_is_not_recaptured(self):
        world = OldWorld()
        result = world.run(world.transition)
        object.__setattr__(result, "checked_ns", result.checked_ns + 1)
        with self.assertRaises(Refusal):
            world.closed_return(world.transition, result)

    def test_mutated_leaf_is_not_adopted(self):
        world = OldWorld()
        result = world.run(world.transition)
        object.__setattr__(result.leaf, "raw", b"replacement")
        with self.assertRaises(Refusal):
            world.closed_return(world.transition, result)

    def test_failed_original_does_not_publish_a_return(self):
        world = OldWorld()
        world.begin_failure = FalseyFailure()
        with self.assertRaises(FalseyFailure):
            world.run(world.transition)
        with self.assertRaises(Refusal):
            world.closed_return(world.transition, None)

    def test_changed_closed_resource_row_refuses(self):
        world = OldWorld()
        result = world.run(world.transition)
        world.state()["resources"][0]["closed"] = False
        with self.assertRaises(Refusal):
            world.closed_return(world.transition, result)

    def test_late_cancellation_refuses_closed_adoption(self):
        world = OldWorld()
        result = world.run(world.transition)
        world.state()["cancelled"].append(2)
        with self.assertRaises(Refusal):
            world.closed_return(world.transition, result)


class ExportModels(unittest.TestCase):
    def world(self):
        world = World()
        # One admitted file and one honest post-cutoff miss.
        world.start_candidate, world.finish_candidate = 89.0, 95.0
        return world

    def test_new_parent_uses_original_return_and_shared_copy_loop(self):
        world = self.world()
        result = world.run(world.transition)
        value = json.loads(result.leaf.raw)
        self.assertEqual((world.original_calls, world.copy_calls), (1, 1))
        self.assertEqual(value["status"], "KNOWN_PARTIAL")
        self.assertEqual(value["counts"]["outputBytes"], 3)
        self.assertFalse(value["exportSaveAuthority"])
        self.assertTrue(all(value.closes == 1 for value in world.opened))
        self.assertEqual(world.signals, world.original_signals)

    def test_candidate_before90_finishes_readback_after90_inside120(self):
        world = self.world()
        result = world.run(world.transition)
        self.assertEqual(world.copy_starts, [89.0])
        self.assertTrue(all(row[2] == 95.0 for row in world.events if row[1] in ("writer", "readback", "final-readback")))
        self.assertEqual(json.loads(result.leaf.raw)["misses"][0]["reason"], "BUDGET_NOT_STARTED")

    def test_exact_raw90_starts_no_candidate(self):
        world = self.world()
        world.start_candidate = 90.0
        result = world.run(world.transition)
        self.assertEqual(world.copy_starts, [])
        self.assertEqual(json.loads(result.leaf.raw)["status"], "KNOWN_EMPTY")

    def test_local90_shortens_raw_cutoff_without_fabricating_reading(self):
        world = self.world()
        world.start_candidate = 80.0
        world.callback_hook = lambda: setattr(world, "local_extra", 10.0) if world.seconds >= 80 else None
        result = world.run(world.transition)
        self.assertEqual(world.copy_starts, [])
        self.assertEqual(result.checked_ns, 580 * NS_SECOND)

    def test_exact120_cannot_finish_or_publish_success(self):
        world = self.world()
        world.finish_candidate = 120.0
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertIsNone(world.state()["result"])
        self.assertTrue(all(value.closes == 1 for value in world.opened))

    def test_original_allocation_fence_cannot_be_replaced_with120(self):
        world = self.world()
        original = world.Inputs.__init__
        def shorter(value, *args):
            original(value, *args)
            value.proposal["phaseFencesNs"]["dependency-export"] = 590 * NS_SECOND
        world.Inputs.__init__ = shorter
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertTrue(all(value.closes == 1 for value in world.opened))

    def test_original_failure_is_retained_without_copy_or_retry(self):
        world = self.world()
        failure = world.initial_failure = FalseyFailure()
        with self.assertRaises(FalseyFailure) as caught:
            world.run(world.transition)
        self.assertIs(caught.exception, failure)
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual((world.original_calls, world.copy_calls), (1, 0))

    def test_second_successful_call_refuses_before_original(self):
        world = self.world()
        world.run(world.transition)
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(world.original_calls, 1)

    def test_changed_original_operation_refuses_before_claim(self):
        world = self.world()
        world.namespace["observe_no_loader_after_entry"] = lambda value: world.previous
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(world.original_calls, 0)

    def test_nonempty_original_staging_refuses_copy(self):
        world = self.world()
        world.stage_nonempty = True
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(world.copy_starts, [])
        self.assertTrue(all(value.closes == 1 for value in world.opened))

    def test_changed_properties_refuse_copy_and_close_known_handles(self):
        world = self.world()
        world.bad_properties = True
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(world.copy_starts, [])
        self.assertTrue(all(value.closes == 1 for value in world.opened))

    def test_unknown_close_quarantines_without_retry(self):
        world = self.world()
        failure = Refusal("MODELED_CLOSE_UNKNOWN")
        world.close_hook = lambda _value: (_ for _ in ()).throw(failure)
        with self.assertRaises(Refusal) as caught:
            world.run(world.transition)
        self.assertIs(caught.exception, failure)
        self.assertTrue(world.state()["unknown"])
        self.assertTrue(world.quarantine)
        self.assertEqual(sum(value.closes for value in world.opened), 1)

    def test_expired_cleanup_closes_more_than64_known_obligations(self):
        world = self.world()
        def acquire_then_expire(leaf):
            for i in range(70):
                leaf.acquire("extra", lambda: world.File("extra"))
            world.seconds = 120.0
        world.copy_hook = acquire_then_expire
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertTrue(all(value.closes == 1 for value in world.opened))
        self.assertFalse(world.state()["unknown"])

    def test_post_return_clock_cannot_replace_leaf_before_pin(self):
        world = self.world()
        def arm(result):
            world.clock_hook = lambda: object.__setattr__(result, "raw", b"replacement")
        world.return_hook = arm
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertNotEqual(world.state()["leaf_pin"][1], b"replacement")

    def test_cancel_during_final_encoding_refuses_after_known_close(self):
        world = self.world()
        def cancel(value):
            if type(value) is dict and value.get("scope") == "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1":
                world.state()["cancelled"].append(2)
        world.encode_hook = cancel
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertTrue(all(value.closes == 1 for value in world.opened))

    def test_cancel_during_final_clock_refuses_after_known_close(self):
        world = self.world()
        def arm(value):
            if type(value) is dict and value.get("scope") == "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1":
                world.clock_hook = lambda: world.state()["cancelled"].append(2)
        world.encode_hook = arm
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertTrue(all(value.closes == 1 for value in world.opened))

    def test_clock_cannot_extend_original_window(self):
        world = self.world()
        world.copy_hook = lambda leaf: setattr(leaf.window, "hard", leaf.window.hard + NS_SECOND)
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertIsNone(world.state()["result"])

    def test_preclose_clock_row_change_quarantines_without_dispatch(self):
        world = self.world()
        held = []
        def alter(leaf):
            value = leaf.acquire("probe", lambda: world.File("probe"))
            held.append(value)
            def change():
                world.clock_hook = lambda: None
                leaf.parent.resources[-1]["label"] = "replacement"
            world.clock_hook = change
            leaf.parent.close_one(value)
        world.copy_hook = alter
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(held[0].closes, 0)
        self.assertTrue(world.state()["unknown"])

    def test_preclose_clock_global_unknown_stops_dispatch(self):
        world = self.world()
        held = []
        def alter(leaf):
            value = leaf.acquire("probe", lambda: world.File("probe"))
            held.append(value)
            def change():
                world.clock_hook = lambda: None
                world.namespace["query"].QUARANTINE.append(object())
            world.clock_hook = change
            leaf.parent.close_one(value)
        world.copy_hook = alter
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(held[0].closes, 0)

    def test_preclose_reentry_dispatches_original_close_only_once(self):
        world = self.world()
        held = []
        def alter(leaf):
            value = leaf.acquire("probe", lambda: world.File("probe"))
            held.append(value)
            def change():
                world.clock_hook = lambda: None
                leaf.parent.close_one(value)
            world.clock_hook = change
            leaf.parent.close_one(value)
        world.copy_hook = alter
        world.run(world.transition)
        self.assertEqual(held[0].closes, 1)

    def test_wrong_resource_kind_is_retained_but_never_closed(self):
        world = self.world()
        foreign = object()
        world.copy_hook = lambda leaf: leaf.acquire("foreign", lambda: foreign)
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertIn(foreign, world.state()["returns"])
        self.assertTrue(world.state()["unknown"])

    def test_borrowed_predecessor_handle_is_never_closed_by_export(self):
        world = self.world()
        borrowed = world.File("predecessor")
        world.bound.pin.graph.nodes.append((borrowed,))
        world.copy_hook = lambda leaf: leaf.acquire("borrowed", lambda: borrowed)
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertEqual(borrowed.closes, 0)

    def test_bool_leaf_time_is_not_an_original_clock(self):
        world = self.world()
        world.return_hook = lambda result: object.__setattr__(result, "checked_local", False)
        with self.assertRaises(Refusal):
            world.run(world.transition)
        self.assertIsNone(world.state()["result"])

    def test_no_provider_or_ordinary_context_is_called(self):
        world = self.world()
        world.run(world.transition)
        self.assertNotIn("export_snapshot", vars(world.staging.cache))
        self.assertNotIn("save_set", vars(world.staging.cache))
        self.assertNotIn("primaryAbiAccounting", vars(world.state()["inputs"]))


if __name__ == "__main__":
    unittest.main()
