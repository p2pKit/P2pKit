#!/usr/bin/env python3
"""Selected handoff/Owner code with memory originals, not a provider/native run.

No full controller import, process, environment identity or real private file is
used. Existing selected export/before code supplies its real in-process returns;
upstream source/admission/native/clock records and file suppliers remain models.
"""
import hashlib
import json
import math
from pathlib import Path
import re
import runpy
from types import SimpleNamespace as NS
import unittest


ROOT = Path(__file__).resolve().parents[1]
old = runpy.run_path(str(ROOT / "tests/hosted-cache-bootstrap-save-set-test.py"), run_name="save_models")
require, Refusal, FalseyFailure = old["require"], old["Refusal"], old["FalseyFailure"]
encoded = old["old"]["encoded"]
SECOND, LIMIT = 1_000_000_000, 2 * 1024 * 1024


class World(old["World"]):
    def __init__(self):
        super().__init__()
        self.meta_owner = None
        self.metadata_opened, self.writes = [], []
        self.writer_hook = self.metadata_read_hook = self.metadata_close_hook = lambda *args: None
        self.metadata_verify_hook = self.metadata_names_hook = self.handoff_inputs_hook = lambda *args: None
        self.metadata_allocate_hook = lambda *args: None
        self.metadata = {Path("session"): self.nodes["session"]}
        self.input_count = 0
        self.window_limit, self.job_limit = 895 * SECOND, 900 * SECOND
        self.origin_inputs = {}
        world = self
        self.staging.NS = SECOND
        self.previous.leaf = NS(raw=encoded({"record": "no-loader-leaf"}), local_started=98.0, checked_local=99.0)
        self.frame = self.bound.pin.frame
        self.saved = self.frame.predecessor.frame
        last = self.frame.predecessor.phases[-1][1]

        def raw(label):
            return encoded({"modeledOriginal": label})

        def result(label, ns=480, local=80.0):
            return NS(raw=raw(label), checked_ns=ns * SECOND, checked_local=local)

        def leaf(label, ns=480, local=80.0):
            return NS(**vars(result(label, ns, local)), local_started=local - 1.0)

        self.phases = tuple(NS(name=name, result=result(name), leaf=leaf(name + "-leaf"), files=())
                            for name in ("dependency-stage", "empty-seed")) + (last,)
        last.name, last.result, last.leaf, last.files = "custody-prepare", result("custody-parent"), leaf("custody-leaf"), ()
        last.leaf.request_raw = encoded({"fileBindings": {name: {"originalBinding": name} for name in
            ("initializer-context", "canonical-context", "properties")}})
        last.request_pin = NS(path="session/configuration-custody", directory=(1, 62), retained=(1, 63),
                              binding_raw=encoded({"originalBinding": "request"}))
        self.frame.predecessor.phases = tuple((object(), phase) for phase in self.phases)
        self.reservation = NS(**vars(last.result), custody_leaf=last.leaf)
        self.saved.paths = tuple(Path(p) for p in ("prepare", "adoption", "entry", "session"))
        # The actual recipient and initializer rosters share these seven keys.
        # Keep their distinct original directories, names, limits and bytes.
        phase_names = ("start.json", "baseline.json", "native-start.json", "stdout.log", "stderr.log", "result.json")
        self.recipient_files = (("context", "recipient", (1, 80), "recipient-context.json", LIMIT, raw("recipient-context")),) + tuple(
            (name, "recipient/recipient-validation", (1, 81), name,
             16384 if name == "stdout.log" else 65536 if name == "stderr.log" else LIMIT, raw("recipient-" + name))
            for name in phase_names) + (("pending", "recipient", (1, 80), "recipient-prefix-pending.json", LIMIT, raw("recipient-pending")),)
        self.initializer_files = (("context", "session", self.ids["session"], "initializer-context.json", LIMIT, b"initializer"),) + tuple(
            (name, "session/canonical-init", (1, 82), name,
             16384 if name == "stdout.log" else 65536 if name == "stderr.log" else LIMIT, raw("initializer-" + name))
            for name in phase_names) + (("initializer-pending", "session", self.ids["session"], "initializer-prefix-pending.json",
                                        LIMIT, raw("initializer-pending")),)
        self.saved.files = self.recipient_files + self.initializer_files
        recipient = NS(raw=raw("recipient"), files=self.recipient_files, checked_ns=470 * SECOND, local_last=70.0)
        self.saved.registries = (None,) * 6 + ((None,) * 4 + ((None,) * 4 + (recipient,),),)
        admission = NS(record=b"bootstrap-admission", original_event=b"original-event", original_policy=b"original-policy",
                       public_key=b"model-public-key-not-a-real-key")
        sha = hashlib.sha256(b"hash-only-original").hexdigest()
        prepared = {"sessionIdentity": [1, 50], "directories": {name: [1, i + 51] for i, name in
            enumerate(("service", "admission", "final-admission"))}, "originSha256": sha,
            "originalChain": {"phaseSha256": {name: sha for name in
                ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log")},
                "childTerminalSha256": sha, "admissionOriginals": {"returnSha256": sha, "sessionSha256": sha}},
            "finalAdmissionOriginals": {"returnSha256": sha, "sessionSha256": sha}}
        entry = NS(raw=encoded({"sessionIdentity": [1, 56]}), admitted=admission,
            handoff_original=raw("prepare-handoff"), context_original=raw("prepare-context"),
            preparation_original=encoded(prepared), session_original=raw("adoption-session"),
            return_original=raw("adoption-return"))
        previous = NS(transition=NS(raw=raw("adoption-closed"), pending_raw=raw("adoption-pending"),
            _entry=entry, _fence=NS(raw=raw("prelude")), _checked_ns=450 * SECOND), admitted=admission,
            target_identity=(1, 57), pending_raw=raw("entry-pending"), preparation=encoded(prepared),
            admission_originals=(admission, raw("entry-session"), raw("entry-return")))
        self.transition._attempt, self.transition.raw, self.transition._checked_ns = previous, raw("entry-closed"), 460 * SECOND
        self.produced = NS(**vars(result("producer-parent")), request_raw=encoded({"jobId": "modeled-job", "id": "modeled-invocation"}),
                           observation_raw=raw("producer-observation"))
        self.native = NS(**{name + "_raw": raw("native-" + name) for name in
            ("birth", "leader", "preparer", "terminal", "survivors")}, launch_minimum=471 * SECOND,
            completed_ns=472 * SECOND, finalized_ns=473 * SECOND, argv=("MODELED_CONFIGURATION_NOT_EXECUTED",),
            exit_code=0, retired=True)

        def file_row(label):
            return NS(key="same-key", path=Path("session") / label, identity=(1, 60 if label == "producer" else 61),
                name="retained.json", maximum=LIMIT, raw=raw(label), binding_raw=encoded({"originalBinding": label}))

        self.producer_frame = NS(predecessor=self.frame.predecessor, reservation=self.reservation, native=self.native,
            descriptor=raw("producer-command"), outer_invocation="modeled-outer", files=(file_row("producer"),),
            handles=(("phase", object(), Path("session/configuration-parent"), (1, 64)),
                     ("admission:adoption", object(), Path("adoption/admission"), (1, 65)),
                     ("admission:entry", object(), Path("entry/admission"), (1, 66))),
            captures=tuple(NS(name=name, identity=(1, i + 70), final_stamp=((1, i + 70), 3, 1, 2),
                readback=(3, hashlib.sha256(name.encode()).hexdigest(), 479 * SECOND)) for i, name in enumerate(("stdout", "stderr"))))
        self.collected = NS(**vars(result("collection-parent")), manifest_raw=raw("collection-manifest"),
            leaf=NS(raw=raw("collection-leaf"), inventory_raw=raw("collection-inventory"), local_started=90.0, checked_local=91.0))
        self.frame.bound = NS(producer_frame=self.producer_frame, returned=self.produced)
        self.frame.files, self.bound.returned = (file_row("collector"),), self.collected

        original_init = self.Inputs.__init__

        def inputs_init(value, *args):
            original_init(value, *args)
            world.input_count += 1
            if world.input_count != 3:
                return
            value.proposal["phaseFencesNs"]["producer-owner-return"] = world.window_limit
            value.proposal["proposedJobEndNs"] = world.job_limit
            value.session, value.state, value.home, value.container = map(Path, ("session", "state", "H", "container"))
            value.admission = {"source": {"commit": "a" * 40, "tree": "b" * 40},
                "github": {"runId": "123", "runAttempt": "1"}, "selection": "desktop-linux-x64"}
            stage, seed = world.phases[:2]
            capture = lambda item: (item.raw, b"original-stage", item.checked_ns, item.local_started, item.checked_local)
            value.staged_capture = (seed.result.raw, stage.result.raw, capture(stage.leaf), capture(seed.leaf),
                                    seed.result.checked_ns, seed.result.checked_local)
            value.closed_raw, value.previous_ns, value.previous_local = raw("initializer-closed"), 475 * SECOND, 75.0
            value.responses = {name: raw("service-" + name) for name in ("attempt", "jobs")}
            world.handoff_inputs = value
            world.handoff_inputs_hook(value)

        self.Inputs.__init__ = inputs_init

        class Directory:
            def __init__(self, path):
                self.path, self.node, self.closes = Path(path), world.metadata[Path(path)], 0
                self.identity = self.node.identity
                world.metadata_opened.append(self)

            def verify(self):
                world.metadata_verify_hook(self)
                require(self.closes == 0 and self.identity == self.node.identity, "MODEL_PRIVATE_DIRECTORY_CHANGED")

            def create_directory(self, name, *, deadline):
                self.verify()
                require(world.monotonic() < deadline and name not in self.node.children, "MODEL_EXCLUSIVE_DIRECTORY")
                node = world.node()
                self.node.children[name] = node
                world.metadata[self.path / name] = node
                value = Directory(self.path / name)
                world.metadata_allocate_hook(value)
                return value

            def create_file(self, name, *, max_bytes, deadline):
                self.verify()
                require(world.monotonic() < deadline and name not in self.node.children, "MODEL_EXCLUSIVE_FILE")
                self.node.children[name] = world.node(b"")
                value = Writer(self, name, max_bytes)
                world.metadata_allocate_hook(value)
                return value

            def read_bytes(self, name, *, max_bytes, deadline):
                self.verify()
                world.metadata_read_hook(self, name)
                data = self.node.children[name].data
                require(world.monotonic() < deadline and len(data) <= max_bytes, "MODEL_PRIVATE_READ_BOUND")
                return data

            def names(self, *, max_names, deadline):
                world.metadata_names_hook(self)
                require(world.monotonic() < deadline and len(self.node.children) <= max_names, "MODEL_PRIVATE_NAMES_BOUND")
                return tuple(self.node.children)

            def close(self):
                self.closes += 1
                world.metadata_close_hook(self)

        class Writer:
            def __init__(self, directory, name, maximum):
                self.directory, self.name, self.maximum, self.closes, self.synced = directory, name, maximum, 0, False
                world.metadata_opened.append(self)

            def write(self, blob):
                world.writer_hook(self, blob)
                require(self.closes == 0 and len(blob) <= self.maximum, "MODEL_PRIVATE_WRITE_BOUND")
                self.directory.node.children[self.name].data = blob
                world.writes.append((self.name, blob))
                return len(blob)

            def sync(self):
                self.synced = True

            def verify(self):
                return NS(size=len(self.directory.node.children[self.name].data))

            def close(self):
                self.closes += 1
                world.metadata_close_hook(self)

        class Listing:
            def __init__(self, path):
                self.node = world.metadata[Path(path)]

            def __enter__(self):
                directory = NS(path=Path("session/dependency-save-handoff"), node=self.node)
                world.metadata_names_hook(directory)
                return iter(NS(name=name) for name in self.node.children)

            def __exit__(self, *_args):
                pass

        self.namespace.update(math=math, re=re, os=NS(name="posix", scandir=Listing),
            posix=NS(_deadline=lambda end: require(self.monotonic() < end, "MODEL_LOCAL_DEADLINE")),
            directory_identity=lambda values, role: tuple(values), PRODUCER_STREAM_BYTES=64 * 1024 * 1024 + 65536,
            ACK_LIMIT=16384, STDERR_LIMIT=65536)
        self.namespace["query"]._PosixDirectory = Directory
        self.namespace["windows"].open_private_directory = Directory
        actual = self.namespace["Owner"].__init__

        def construct(value, *args, **kwargs):
            actual(value, *args, **kwargs)
            world.meta_owner = value

        self.namespace["Owner"].__init__ = construct

    def run_handoff(self):
        return self.handoff(self.transition)

    def stored(self):
        return {name: node.data for name, node in self.metadata[Path("session/dependency-save-handoff")].children.items()}


class HandoffModels(unittest.TestCase):
    def test_original_chain_is_written_with_actual_owner_and_return_remains_provisional(self):
        world = World()
        returned = world.run_handoff()
        value, stored = json.loads(returned.raw), world.stored()
        self.assertEqual((world.original_calls, world.copy_calls, world.freeze_calls), (1, 1, 1))
        self.assertEqual(len(stored), 32)
        self.assertEqual(stored["save-handoff.json"], returned.raw)
        self.assertEqual(len(value["blobs"]), 31)
        for name, binding in value["blobs"].items():
            self.assertEqual(binding, {"bytes": len(stored[name]), "sha256": hashlib.sha256(stored[name]).hexdigest()})
        self.assertEqual(value["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(value["providerExecution"], "NOT_PERFORMED")
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertFalse(value["nextPhaseAuthority"] or value["exportSaveAuthority"])
        self.assertTrue(world.meta_owner.closed)
        self.assertTrue(all(item.closes == 1 for item in world.metadata_opened))
        self.assertEqual(world.signals, world.original_signals)

    def test_exact_memory_only_bytes_and_return_highwaters_are_retained(self):
        world = World()
        result = world.run_handoff()
        files, value = world.stored(), json.loads(result.raw)
        for name, raw in (("producer-command.json", world.producer_frame.descriptor),
                ("producer-observation.json", world.produced.observation_raw),
                ("producer-terminal.json", world.native.terminal_raw), ("producer-survivors.json", world.native.survivors_raw),
                ("collection-inventory.json", world.collected.leaf.inventory_raw),
                ("before-parent.json", world.before_state()["result"].raw),
                ("export-parent.json", world.state()["result"].raw), ("adoption-parent.json", world.transition._attempt.transition.raw)):
            self.assertEqual(files[name], raw)
        self.assertEqual(value["chain"]["returns"]["before"]["checkedNs"], world.before_state()["result"].checked_ns)
        self.assertEqual(value["chain"]["returns"]["recipient"], {"checkedNs": 470 * SECOND, "checkedLocal": 70.0})
        self.assertEqual(value["chain"]["producerNative"]["executedArgv"], ["MODELED_CONFIGURATION_NOT_EXECUTED"])

    def test_existing_references_keep_namespaces_and_missing_file_bindings_honest(self):
        world = World()
        value = json.loads(world.run_handoff().raw)
        refs = value["references"]
        self.assertNotEqual(refs["producer/same-key"], refs["collector/same-key"])
        self.assertEqual(refs["producer/same-key"]["fileBinding"], {"originalBinding": "producer"})
        self.assertIsNone(refs["initializer/context"]["fileBinding"])
        self.assertIsNone(refs["preparation/origin-result.json"]["bytes"])
        self.assertIsNone(refs["preparation/origin-result.json"]["fileBinding"])
        self.assertEqual(refs["service/attempt"]["name"], "attempt.json")
        self.assertEqual(refs["adoption/admission/session-result.json"]["directoryIdentity"], [1, 65])
        self.assertEqual(refs["initializer-actual/properties"]["fileBinding"], {"originalBinding": "properties"})
        self.assertGreater(refs["producer-capture/stdout"]["maximumBytes"], LIMIT)
        self.assertNotIn("stdout.log", world.stored())

    def test_overlapping_original_recipient_initializer_keys_are_all_retained(self):
        world = World()
        refs = json.loads(world.run_handoff().raw)["references"]
        common = {row[0] for row in world.recipient_files} & {row[0] for row in world.initializer_files}
        self.assertEqual(common, {"context", "start.json", "baseline.json", "native-start.json", "stdout.log", "stderr.log", "result.json"})
        for group, rows in (("recipient", world.recipient_files), ("initializer", world.initializer_files)):
            for key, path, identity, name, maximum, blob in rows:
                ref = refs[group + "/" + key]
                self.assertEqual((ref["directory"], ref["directoryIdentity"], ref["name"], ref["maximumBytes"], ref["bytes"], ref["sha256"]),
                                 (path, list(identity), name, maximum, len(blob), hashlib.sha256(blob).hexdigest()))
                self.assertIsNone(ref["fileBinding"])
        for key in common:
            self.assertNotEqual(refs["recipient/" + key], refs["initializer/" + key])

    def test_handoff_is_outside_frozen_stage_home_and_canonical_evidence(self):
        world = World()
        value = json.loads(world.run_handoff().raw)
        self.assertEqual(value["directory"], "session/dependency-save-handoff")
        self.assertEqual(set(world.nodes["container"].children), {"restore-home", "staging.json"})
        self.assertEqual(set(world.nodes["gradle-home"].children), {"gradle.properties"})

    def test_one_claim_refuses_previously_separately_run_before_save(self):
        world = World()
        previous = world.before(world.transition)
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertIsNone(world.meta_owner)
        self.assertIs(world.before_state()["result"], previous)

    def test_second_handoff_cannot_adopt_or_rewrite_original(self):
        world = World()
        world.run_handoff()
        before = tuple(world.writes)
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertEqual(tuple(world.writes), before)

    def test_upstream_failure_opens_no_handoff_and_preserves_falsey_exception(self):
        world = World()
        world.initial_failure = FalseyFailure()
        with self.assertRaises(FalseyFailure) as caught:
            world.run_handoff()
        self.assertIs(caught.exception, world.initial_failure)
        self.assertIsNone(world.meta_owner)

    def test_replaced_operation_refuses_before_original_call(self):
        for name in ("save_handoff_after_entry", "Owner", "_initializer_names", "_checked_before_save_parent_return"):
            with self.subTest(name=name):
                world = World()
                world.namespace[name] = object()
                with self.assertRaises(Refusal):
                    world.run_handoff()
                self.assertEqual(world.original_calls, 0)

    def test_oversized_or_missing_blob_refuses_before_new_owner(self):
        for blob in (None, "not bytes", b"", b"x" * (LIMIT + 1)):
            with self.subTest(kind=type(blob).__name__, size=len(blob) if blob is not None else None):
                world = World()
                world.produced.observation_raw = blob
                with self.assertRaises(Refusal):
                    world.run_handoff()
                self.assertIsNone(world.meta_owner)

    def test_oversized_combined_index_opens_no_writer(self):
        world = World()
        world.handoff_inputs_hook = lambda value: value.stage_value["plan"].update(large="x" * LIMIT)
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertEqual(world.writes, [])
        self.assertTrue(all(item.closes == 1 for item in world.metadata_opened))

    def test_duplicate_reference_is_not_silently_overwritten(self):
        for group in ("recipient", "initializer"):
            with self.subTest(group=group):
                world = World()
                if group == "recipient":
                    recipient = world.saved.registries[6][4][4]
                    recipient.files += recipient.files[:1]
                    world.saved.files = recipient.files + world.initializer_files
                else:
                    world.saved.files += world.initializer_files[:1]
                with self.assertRaisesRegex(Refusal, "BOOTSTRAP_SAVE_HANDOFF_REFERENCE_CHANGED"):
                    world.run_handoff()
                self.assertIsNone(world.meta_owner)

    def test_changed_recipient_roster_prefix_cannot_relabel_an_original(self):
        world = World()
        first = world.saved.files[0]
        world.saved.files = ((*first[:-1], first[-1] + b"changed"), *world.saved.files[1:])
        with self.assertRaisesRegex(Refusal, "BOOTSTRAP_SAVE_HANDOFF_RECIPIENT_ROSTER_CHANGED"):
            world.run_handoff()
        self.assertIsNone(world.meta_owner)

    def test_missing_original_admission_directory_cannot_be_invented(self):
        world = World()
        world.producer_frame.handles = world.producer_frame.handles[:1]
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertIsNone(world.meta_owner)

    def test_fixed_45_interval_is_not_staging_120_or_renewed_prelude(self):
        world = World()
        result = world.run_handoff()
        window = json.loads(result.raw)["window"]
        self.assertEqual(window["hardEndNs"] - window["firstNs"], 45 * SECOND)
        self.assertEqual(world.meta_owner.local_end - 195.0, 45.0)

    def test_original_proposal_and_job_cutoffs_only_shorten(self):
        for name in ("window_limit", "job_limit"):
            with self.subTest(name=name):
                world = World()
                setattr(world, name, 610 * SECOND)
                value = json.loads(world.run_handoff().raw)
                self.assertEqual(value["window"]["hardEndNs"], 610 * SECOND)
                self.assertEqual(world.meta_owner.local_end, 210.0)

    def test_expired_proposal_refuses_before_any_owner(self):
        world = World()
        world.window_limit = 590 * SECOND
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertIsNone(world.meta_owner)

    def test_late_input_rederivation_cannot_start_fresh_45(self):
        world = World()
        world.handoff_inputs_hook = lambda value: setattr(world, "seconds", world.seconds + 46)
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertIsNone(world.meta_owner)

    def test_backwards_raw_and_local_after_first_are_refused(self):
        for name in ("seconds", "local_extra"):
            with self.subTest(name=name):
                world = World()
                world.handoff_inputs_hook = lambda value: setattr(world, name, getattr(world, name) - 1)
                with self.assertRaises(Refusal):
                    world.run_handoff()
                self.assertIsNone(world.meta_owner)

    def test_late_raw_supplier_preserves_local_highwater_and_fails(self):
        world = World()
        def late():
            if world.meta_owner is not None:
                world.local_extra = 46.0
        world.clock_hook = late
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertEqual(world.writes, [])

    def test_expiry_during_write_closes_known_resources_without_new_allowance(self):
        world = World()
        world.writer_hook = lambda *_: setattr(world, "seconds", world.seconds + 46)
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertTrue(all(item.closes == 1 for item in world.metadata_opened))
        self.assertNotIn("save-handoff.json", world.stored())

    def test_falsey_write_error_precedes_later_close_failure(self):
        world = World()
        original = FalseyFailure()
        world.writer_hook = lambda *_: (_ for _ in ()).throw(original)
        world.metadata_close_hook = lambda *_: (_ for _ in ()).throw(Refusal("SECONDARY_CLOSE"))
        with self.assertRaises(FalseyFailure) as caught:
            world.run_handoff()
        self.assertIs(caught.exception, original)
        self.assertTrue(world.meta_owner.unknown)
        self.assertIn(world.meta_owner, world.quarantine)

    def test_unknown_reader_stops_acquisition_and_does_not_retry_close(self):
        world = World()
        original = Refusal("MODEL_READ_UNKNOWN")
        world.metadata_read_hook = lambda *_: (_ for _ in ()).throw(original)
        with self.assertRaises(Refusal) as caught:
            world.run_handoff()
        self.assertIs(caught.exception, original)
        self.assertEqual(len(world.writes), 1)
        self.assertTrue(all(item.closes <= 1 for item in world.metadata_opened))
        self.assertTrue(world.meta_owner.unknown)

    def test_prior_unknown_opens_nothing(self):
        world = World()
        world.namespace["query"].QUARANTINE.append(object())
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertEqual(world.original_calls, 0)

    def test_changed_original_after_write_cannot_publish(self):
        world = World()
        world.writer_hook = lambda *_: setattr(world, "changed", True)
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertTrue(all(item.closes == 1 for item in world.metadata_opened))

    def test_directory_replacement_and_alias_are_refused(self):
        for alias in (False, True):
            with self.subTest(alias=alias):
                world = World()
                def change(value):
                    if hasattr(value, "path"):
                        if alias:
                            value.identity = world.ids["session"]
                        else:
                            value.node.identity = (1, 99999)
                world.metadata_allocate_hook = change
                with self.assertRaises(Refusal):
                    world.run_handoff()
                self.assertEqual(world.writes, [])

    def test_unexpected_33rd_name_cannot_use_a_truncated_roster(self):
        world = World()
        def extra(directory):
            if len(directory.node.children) == 32:
                directory.node.children["extra"] = world.node(b"unrelated")
        world.metadata_names_hook = extra
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertTrue(world.meta_owner.closed)

    def test_post_write_readback_drift_is_refused(self):
        world = World()
        def change(writer, _blob):
            if writer.name == "save-handoff.json":
                writer.directory.node.children["producer-command.json"].data += b" "
        world.writer_hook = change
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertTrue(world.meta_owner.closed)

    def test_late_cancellation_after_index_write_cannot_publish(self):
        world = World()
        def cancel(writer, _blob):
            if writer.name == "save-handoff.json":
                world.signals[2](2, None)
        world.writer_hook = cancel
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertEqual(world.signals, world.original_signals)
        self.assertTrue(all(item.closes == 1 for item in world.metadata_opened))

    def test_handler_restoration_failure_cannot_be_rehabilitated_from_index(self):
        world = World()
        def fail(number, handler):
            if world.meta_owner is not None and handler is world.original_signals[number]:
                raise Refusal("RESTORE_FAILED")
        world.signal_hook = fail
        with self.assertRaises(Refusal):
            world.run_handoff()
        self.assertIn("save-handoff.json", world.stored())

    def test_windows_layout_uses_same_32_name_and_45_bounds_without_snapshot(self):
        world = World()
        world.clock.role, world.namespace["os"].name = "windows-x64", "nt"
        for capture in world.producer_frame.captures:
            capture.final_stamp = (capture.identity, 3, encoded({"originalNativeInfo": capture.name}))
        value = json.loads(world.run_handoff().raw)
        self.assertEqual(len(value["blobs"]), 31)
        self.assertEqual(value["window"]["hardEndNs"] - value["window"]["firstNs"], 45 * SECOND)
        self.assertIn("nativeInfoBytes", value["chain"]["producerCaptures"]["stdout"]["nativeStamp"])
        self.assertNotIn("Snapshot", vars(world.namespace["windows"]))


if __name__ == "__main__":
    unittest.main()
