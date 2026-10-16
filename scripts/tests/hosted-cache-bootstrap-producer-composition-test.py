#!/usr/bin/env python3
"""Fixed command/return-custody controls using selected source and memory files.

No full runner import, hosted identity, native process, real private file,
provider, Gradle or toolchain is executed. Adoption's external entry/admission
and close/readmission suppliers are models. The handoff fixture executes the
selected actual handoff/Owner/export/save code over its existing memory inputs.
"""
import argparse
from contextlib import redirect_stderr
from dataclasses import replace
import hashlib
import io
import json
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
prior = runpy.run_path(str(ROOT / "tests/hosted-cache-bootstrap-save-handoff-test.py"), run_name="handoff_models")
require, Refusal, FalseyFailure = (prior[name] for name in ("require", "Refusal", "FalseyFailure"))
encoded, SECOND = prior["encoded"], prior["SECOND"]
selected, cells = prior["old"]["selected"], prior["old"]["cells"]
CODE = selected(ROOT / "run-hosted-cache-bootstrap.py",
    {"_prepare_adoption", "adopt_originals", "produce_originals", "public_result", "guarded", "main"})


def throw(error):
    raise error


class AdoptionWorld:
    """Actual shared preparation/wrappers, with explicit entry/clock/I/O models."""
    def __init__(self):
        self.events, self.owners, self.hooks = [], [], {}
        self.barrier = False
        self.path = Path("/modeled-private/originals")
        self.private = NS(path=self.path)
        self.target = NS(path=self.path.with_name("originals-adoption"))
        self.clock = NS(role="linux-x64")
        self.first = NS(clock=self.clock, nanoseconds=1000 * SECOND)
        self.handoff_raw = encoded({"recordedNs": 999 * SECOND, "processIdentity": {"pid": 10}})
        self.env = {"P2PKIT_BOOTSTRAP_PREPARE_OUTCOME": "success",
            "P2PKIT_BOOTSTRAP_PREPARE_SHA256": hashlib.sha256(self.handoff_raw).hexdigest(), "RUNNER_NAME": "modeled"}
        self.admitted, self.entry = NS(original_event=b"modeled-event"), NS(raw=b"modeled-entry")
        self.closed, self.current = object(), object()
        self.new_fence = NS(now=lambda **_kwargs: self.hit("new-fence") or 2000 * SECOND)
        self.returned = NS(_complete=lambda value: self.complete(value))
        self.prepared = {"clock": "modeled"}
        world = self

        class Fence:
            def __init__(self, value, *, minimum, cancelled):
                self.clock, self.raw = world.clock, encoded(value)
                self.work, self.final, self.last = 1075 * SECOND, 1120 * SECOND, minimum
                self.cancelled = cancelled
                world.fence = self

            def now(self, **_kwargs):
                require(not world.barrier, "OLD_FENCE_AFTER_CLOSE_BARRIER")
                world.hit("old-fence")
                self.cancelled()
                self.last += 1
                return self.last

        class Owner:
            def __init__(self, local_end, *, first, cancelled):
                self.local_end, self.first, self.cancelled = local_end, first, cancelled
                self.closed, self.unknown, self.original, self.fence = False, False, None, None
                self.errors, self.files, self.closes = [], {}, 0
                world.owners.append(self)

            def end(self):
                require(not self.closed, "MODEL_OWNER_CLOSED")
                self.cancelled()
                world.hit("owner-end")

            def bind(self, fence, **kwargs):
                require(kwargs == {"work_limit": fence.work, "final_limit": fence.final}, "MODEL_ORIGINAL_LIMITS")
                self.fence = fence
                world.hit("bind")

            def open(self, path):
                require(path == world.path, "MODEL_PREPARATION_PATH")
                world.hit("open")
                return world.private

            def new(self, path):
                require(path == world.target.path, "MODEL_ADOPTION_PATH")
                world.hit("new")
                return world.target

            def read(self, _directory, name):
                world.hit("read:" + name)
                return {"prepare-handoff.json": world.handoff_raw, "context.json": b"modeled-context",
                        "prelude.json": encoded(world.prepared)}[name]

            def write(self, directory, name, value, **_kwargs):
                require(not self.closed and directory is world.target, "MODEL_WRITE_OWNER")
                world.hit("write:" + name)
                self.files[name] = encoded(value)
                return self.files[name]

            def error(self, stage, error):
                require(not world.barrier, "OLD_ERROR_AFTER_CLOSE_BARRIER")
                if self.original is None:
                    self.original = error
                self.errors.append({"stage": stage, "detail": {"modelType": type(error).__name__,
                                                           "retirementUnknown": False}})

            def close(self):
                require(not world.barrier, "OLD_CLOSE_AFTER_CLOSE_BARRIER")
                self.closes += 1
                self.closed = True
                world.hit("owner-close")

        self.namespace = {"__doc__": __doc__, "Owner": Owner, "require": require, "re": prior["re"],
            "time": NS(monotonic=lambda: 100.0), "QUARANTINE": [], "diagnostics": NS(_QUARANTINE=[]),
            "query": NS(QUARANTINE=[], _inherited_context=lambda: {}),
            "origin": NS(wire=NS(TOKEN_ENV="MODEL_READ_TOKEN"), Fence=Fence, parse=json.loads, encoded=encoded,
                digest=lambda raw: hashlib.sha256(raw).hexdigest(), clocks=NS(observe=lambda: self.first,
                    validate_reading=lambda value: value)),
            "os": NS(environ=self.env, getpid=lambda: 11),
            "cancellation": lambda flags: require(not flags, "MODEL_CANCELLED"),
            "PREPARE_OUTCOME_ENV": "P2PKIT_BOOTSTRAP_PREPARE_OUTCOME", "PREPARE_HASH_ENV": "P2PKIT_BOOTSTRAP_PREPARE_SHA256",
            "ADOPTION_SCOPE": "BOOTSTRAP_READ_ONLY_ADOPTION_PENDING_RETURN_V2",
            "host_inputs": lambda role: ("desktop-linux-x64", self.path, b"modeled-event"),
            "child_environment": lambda path: self.hit("environment"),
            "handoff_record": lambda raw, clock: json.loads(raw),
            "prepared_content": lambda *_args: (self.admitted, {"selection": "desktop-linux-x64",
                "runnerName": "modeled", "inheritedContext": {}}, {}),
            "admit": self.admit, "execution_entry": self.enter, "check_execution_entry": self.check_entry,
            "close_entry_transition": self.close_entry, "readmit_closed_entry": self.readmit,
            "save_handoff_after_entry": self.handoff,
            "posix": NS(_deadline=lambda value: self.hit("old-local")),
            "argparse": argparse, "sys": NS(flags=NS(isolated=1, no_site=1), dont_write_bytecode=True,
                stderr=io.StringIO())}
        exec(CODE, self.namespace)

    def hit(self, name):
        self.events.append(name)
        if name in self.hooks:
            self.hooks[name]()

    def admit(self, owner, fence, path, *, expected):
        require(owner is self.owners[0] and fence is self.fence and expected is self.admitted and
                path == self.target.path / "admission", "MODEL_ACTUAL_ADOPTION_ARGUMENTS")
        self.hit("admit")
        return self.admitted, {"returnedNs": 1000 * SECOND}

    def enter(self, owner, target, private, handoff, context, admitted, before, fence):
        require((owner, target, private, admitted, fence) ==
                (self.owners[0], self.target, self.private, self.admitted, self.fence), "MODEL_ENTRY_ARGUMENTS")
        self.hit("entry")
        return self.entry

    def check_entry(self, owner, target, entry, fence, *, retained):
        require(owner is self.owners[0] and target is self.target and entry is self.entry and
                fence is self.fence and retained is True and not owner.closed, "MODEL_LIVE_ENTRY")
        self.hit("entry-check")
        return {"window": {"clock": {}, "adopterFirstNs": self.first.nanoseconds,
                "metadataLastNs": self.first.nanoseconds, "readmissionReturnedNs": self.first.nanoseconds,
                "startedNs": self.first.nanoseconds, "workEndNs": fence.work},
            "preparation": {}, "prelude": self.prepared, "readmission": {}}

    def close_entry(self, owner, target, entry, fence):
        require(owner is self.owners[0] and target is self.target and entry is self.entry and fence is self.fence,
                "MODEL_EXACT_CLOSE_ARGUMENTS")
        self.hit("close-transition")
        owner.close()
        self.barrier = True
        return self.closed

    def readmit(self, value):
        require(value is self.closed and self.barrier, "MODEL_ORIGINAL_CLOSED_RETURN")
        self.hit("readmit")
        return self.current

    def handoff(self, value):
        require(value is self.current, "MODEL_ORIGINAL_NEW_RETURN")
        self.hit("handoff")
        return self.returned

    def complete(self, value):
        require(value is self.returned, "MODEL_ORIGINAL_HANDOFF_RETURN")
        self.hit("complete")
        return {"scope": "MODELED_COMMAND_RETURN"}, self.new_fence, 2200 * SECOND

    def run(self, name="produce_originals", cancelled=None):
        return self.namespace[name]([] if cancelled is None else cancelled)


class CompositionModels(unittest.TestCase):
    def test_read_only_adoption_keeps_original_output_close_and_fence(self):
        world = AdoptionWorld()
        value, fence, cap = world.run("adopt_originals")
        self.assertEqual(value["scope"], "BOOTSTRAP_READ_ONLY_ADOPTION_PENDING_RETURN_V2")
        self.assertEqual(value["adoptionSha256"], hashlib.sha256(world.owners[0].files["adoption-result.json"]).hexdigest())
        self.assertIs(fence, world.fence)
        self.assertEqual(cap, world.fence.final)
        self.assertEqual(world.owners[0].closes, 1)
        self.assertEqual(world.events[-3:], ["owner-close", "old-local", "old-fence"])
        self.assertNotIn("close-transition", world.events)
        self.assertNotIn("handoff", world.events)

    def test_producer_composes_exact_returns_and_never_old_completion_tail(self):
        world = AdoptionWorld()
        _value, fence, cap = world.run()
        self.assertIs(fence, world.new_fence)
        self.assertEqual(cap, 2200 * SECOND)
        self.assertEqual(world.events[-5:], ["close-transition", "owner-close", "readmit", "handoff", "complete"])
        self.assertEqual(world.owners[0].closes, 1)
        self.assertEqual(world.owners[0].errors, [])
        self.assertNotIn("adoption-failure.json", world.owners[0].files)

    def test_preparation_failure_keeps_first_error_retention_and_close(self):
        for command in ("adopt_originals", "produce_originals"):
            with self.subTest(command=command):
                world, failure = AdoptionWorld(), FalseyFailure()
                world.hooks["admit"] = lambda: throw(failure)
                world.hooks["owner-close"] = lambda: throw(Refusal("SECONDARY_CLOSE"))
                with self.assertRaises(FalseyFailure) as caught:
                    world.run(command)
                self.assertIs(caught.exception, failure)
                self.assertEqual(world.owners[0].closes, 1)
                self.assertIn("adoption-failure.json", world.owners[0].files)
                self.assertNotIn("readmit", world.events)

    def test_original_prepare_outcome_hash_token_and_first_clock_stay_required(self):
        mutations = (lambda w: w.env.update(P2PKIT_BOOTSTRAP_PREPARE_OUTCOME="failure"),
            lambda w: (w.env.pop("P2PKIT_BOOTSTRAP_PREPARE_OUTCOME"), w.env.update(P2PKIT_BOOTSTRAP_PREPARE_CONCLUSION="success")),
            lambda w: w.env.update(P2PKIT_BOOTSTRAP_PREPARE_SHA256="f" * 64),
            lambda w: w.env.update(MODEL_READ_TOKEN=""),
            lambda w: setattr(w.first, "nanoseconds", 998 * SECOND))
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                world = AdoptionWorld()
                mutate(world)
                with self.assertRaises(Refusal):
                    world.run()
                self.assertEqual(world.owners[0].closes, 1)
                self.assertNotIn("admit", world.events)
                self.assertNotIn("close-transition", world.events)

    def test_cancelled_preparation_closes_without_running_successors(self):
        world = AdoptionWorld()
        with self.assertRaisesRegex(Refusal, "CANCELLED"):
            world.run(cancelled=[2])
        self.assertEqual(world.owners[0].closes, 1)
        self.assertNotIn("open", world.events)

    def test_rejected_preclaim_close_is_cleaned_once_without_losing_falsey_failure(self):
        world, failure = AdoptionWorld(), FalseyFailure()
        world.hooks["close-transition"] = lambda: throw(failure)
        world.hooks["owner-close"] = lambda: throw(Refusal("SECONDARY_CLOSE"))
        with self.assertRaises(FalseyFailure) as caught:
            world.run()
        self.assertIs(caught.exception, failure)
        self.assertEqual(world.owners[0].closes, 1)
        self.assertNotIn("readmit", world.events)

    def test_already_closed_transition_failure_cannot_reopen_or_annotate_old_owner(self):
        world, failure = AdoptionWorld(), FalseyFailure()
        def close(*_args):
            world.owners[0].close()
            world.barrier = True
            throw(failure)
        world.namespace["close_entry_transition"] = close
        with self.assertRaises(FalseyFailure) as caught:
            world.run()
        self.assertIs(caught.exception, failure)
        self.assertEqual(world.owners[0].closes, 1)
        self.assertEqual(world.owners[0].errors, [])

    def test_each_downstream_failure_leaves_closed_adoption_graph_untouched(self):
        for phase in ("readmit", "handoff", "complete"):
            with self.subTest(phase=phase):
                world, failure = AdoptionWorld(), FalseyFailure()
                world.hooks[phase] = lambda: throw(failure)
                with self.assertRaises(FalseyFailure) as caught:
                    world.run()
                self.assertIs(caught.exception, failure)
                self.assertEqual(world.owners[0].closes, 1)
                self.assertEqual(world.owners[0].errors, [])
                self.assertNotIn("adoption-failure.json", world.owners[0].files)

    def test_cli_has_only_fixed_producer_command_no_command_key_or_duration_override(self):
        world, calls = AdoptionWorld(), []
        world.namespace["guarded"] = calls.append
        with patch.object(sys, "argv", ["bootstrap", "produce-originals"]):
            self.assertEqual(world.namespace["main"](), 0)
        self.assertEqual(calls, [world.namespace["produce_originals"]])
        for option in ("--timeout", "--key", "--command", "--state"):
            with self.subTest(option=option), patch.object(sys, "argv", ["bootstrap", "produce-originals", option, "x"]), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                world.namespace["main"]()
        self.assertEqual(len(calls), 1)
        self.assertEqual(world.owners, [])

    def test_cli_failure_remains_finite_and_does_not_publish_private_exception(self):
        world = AdoptionWorld()
        world.namespace["guarded"] = lambda _operation: throw(FalseyFailure("PRIVATE_SENTINEL"))
        with patch.object(sys, "argv", ["bootstrap", "produce-originals"]):
            self.assertEqual(world.namespace["main"](), 125)
        self.assertEqual(world.namespace["sys"].stderr.getvalue(), "CACHE_BOOTSTRAP_ORIGINALS_NOT_ACCEPTED\n")


class CompletionWorld(prior["World"]):
    def __init__(self):
        super().__init__()
        exec(CODE, self.namespace)
        self.namespace["query"]._component = lambda name: require(name == "dependency-save-handoff", "MODEL_FIXED_CHILD")
        self.namespace.update(ACK_SCOPE="service-ack", RECIPIENT_ACK_SCOPE="recipient-ack",
            sys=NS(stdout=NS(buffer=io.BytesIO())))
        self.returned = self.run_handoff()
        self.original_owner = self.meta_owner
        self.original_resources = tuple(self.metadata_opened)

    def complete(self):
        return self.returned._complete(self.returned)

    def record(self):
        return self.nodes["session"].children["producer-function-return.json"].data

    def cancel_handoff(self):
        cells(self.original_owner.cancelled)["cancelled"].append(2)


class CompletionModels(unittest.TestCase):
    def test_original_function_return_record_is_paired_with_command_digest_and_same_fence(self):
        world = CompletionWorld()
        world.seconds += 1
        output, fence, hard = world.complete()
        record, index = json.loads(world.record()), json.loads(world.returned.raw)
        self.assertIs(fence, world.original_owner.fence)
        self.assertIs(fence, world.meta_owner.fence)
        self.assertIsNot(world.meta_owner, world.original_owner)
        self.assertLessEqual(world.meta_owner.local_end, world.original_owner.local_end)
        self.assertEqual(hard, index["window"]["hardEndNs"])
        self.assertEqual((record["handoffReturnedNs"], record["handoffReturnedLocal"]),
                         (world.returned.checked_ns, world.returned.checked_local))
        self.assertGreater(record["observedAfterReturnNs"], record["handoffReturnedNs"])
        self.assertGreater(record["observedAfterReturnLocal"], record["handoffReturnedLocal"])
        self.assertEqual(record["handoffSha256"], output["handoffSha256"])
        self.assertEqual(output["producerReturnSha256"], hashlib.sha256(world.record()).hexdigest())
        self.assertEqual(record["recordWriterReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(record["producerStepOutcome"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(record["observationScope"], "HANDOFF_FUNCTION_RETURN_ONLY")
        self.assertEqual(len(world.stored()), 32)
        self.assertEqual(world.stored()["save-handoff.json"], world.returned.raw)
        self.assertEqual(set(world.nodes["container"].children), {"restore-home", "staging.json"})
        self.assertEqual(set(world.nodes["gradle-home"].children), {"gradle.properties"})
        self.assertTrue(all(value.closes == 1 for value in world.metadata_opened))

    def test_public_result_contains_only_two_original_digests_and_nonacceptance(self):
        world = CompletionWorld()
        output, _fence, _hard = world.complete()
        self.assertEqual(set(output), {"scope", "handoffSha256", "producerReturnSha256", "budgetAcceptance",
            "testAcceptance", "exportSaveAuthority"})
        self.assertEqual(output["budgetAcceptance"], "NOT_ADMITTED")
        self.assertEqual(output["testAcceptance"], "NOT_PERFORMED")
        self.assertIs(output["exportSaveAuthority"], False)
        for private in (b"session", b"clock", b"checked", b"producerCaptures", b"model-public-key"):
            self.assertNotIn(private, encoded(output))

    def test_copied_return_and_repeated_completion_cannot_allocate(self):
        world = CompletionWorld()
        with self.assertRaisesRegex(Refusal, "NOT_ORIGINAL"):
            world.returned._complete(replace(world.returned))
        self.assertEqual(tuple(world.metadata_opened), world.original_resources)
        world.complete()
        after = tuple(world.metadata_opened)
        with self.assertRaisesRegex(Refusal, "ALREADY_CLAIMED"):
            world.complete()
        self.assertEqual(tuple(world.metadata_opened), after)

    def test_changed_return_fields_refuse_before_new_owner(self):
        for name, value in (("raw", b"changed"), ("checked_ns", 1), ("checked_local", 1), ("_complete", None)):
            with self.subTest(name=name):
                world = CompletionWorld()
                complete = world.returned._complete
                object.__setattr__(world.returned, name, value)
                with self.assertRaises(Refusal):
                    complete(world.returned)
                self.assertEqual(tuple(world.metadata_opened), world.original_resources)

    def test_raw_or_local_expiry_after_handoff_cannot_start_another_45(self):
        for name in ("seconds", "local_extra"):
            with self.subTest(clock=name):
                world = CompletionWorld()
                setattr(world, name, getattr(world, name) + 45)
                with self.assertRaises(Refusal):
                    world.complete()
                self.assertEqual(tuple(world.metadata_opened), world.original_resources)

    def test_backwards_or_changed_clock_after_return_refuses(self):
        for mutate in (lambda w: setattr(w, "seconds", w.seconds - 1),
                       lambda w: setattr(w, "local_extra", -1),
                       lambda w: setattr(w, "clock", NS(role="linux-x64", domain="different", ticks_per_second=SECOND))):
            with self.subTest(mutation=mutate):
                world = CompletionWorld()
                mutate(world)
                with self.assertRaises(Refusal):
                    world.complete()
                self.assertEqual(tuple(world.metadata_opened), world.original_resources)

    def test_expiry_during_return_record_write_preserves_provisional_bytes_not_success(self):
        world = CompletionWorld()
        world.writer_hook = lambda *_args: setattr(world, "seconds", world.seconds + 45)
        with self.assertRaises(Refusal):
            world.complete()
        self.assertEqual(json.loads(world.record())["producerStepOutcome"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertTrue(all(value.closes == 1 for value in world.metadata_opened))
        self.assertEqual(world.original_owner.errors, [])

    def test_original_index_and_directory_identities_cannot_be_substituted(self):
        mutations = (lambda w: setattr(w.metadata[Path("session/dependency-save-handoff")].children["save-handoff.json"], "data", b"changed"),
            lambda w: setattr(w.nodes["session"], "identity", (1, 99999)),
            lambda w: setattr(w.metadata[Path("session/dependency-save-handoff")], "identity", (1, 99998)))
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                world = CompletionWorld()
                mutate(world)
                with self.assertRaises(Refusal):
                    world.complete()
                self.assertNotIn("producer-function-return.json", world.nodes["session"].children)

    def test_existing_return_record_is_not_overwritten(self):
        world = CompletionWorld()
        world.nodes["session"].children["producer-function-return.json"] = world.node(b"old-original")
        with self.assertRaises(Refusal):
            world.complete()
        self.assertEqual(world.record(), b"old-original")

    def test_falsey_writer_error_survives_later_unknown_close(self):
        world, failure = CompletionWorld(), FalseyFailure()
        world.writer_hook = lambda *_args: throw(failure)
        world.metadata_close_hook = lambda *_args: throw(Refusal("SECONDARY_CLOSE"))
        with self.assertRaises(FalseyFailure) as caught:
            world.complete()
        self.assertIs(caught.exception, failure)
        self.assertTrue(world.meta_owner.unknown)
        self.assertIn(world.meta_owner, world.quarantine)
        self.assertEqual(world.original_owner.errors, [])
        self.assertTrue(all(value.closes == 1 for value in world.original_resources))

    def test_close_failure_cannot_promote_the_retained_return_record(self):
        world, failure = CompletionWorld(), FalseyFailure()
        world.metadata_close_hook = lambda value: throw(failure) if value is not world.original_resources[0] else None
        with self.assertRaises(FalseyFailure) as caught:
            world.complete()
        self.assertIs(caught.exception, failure)
        self.assertEqual(json.loads(world.record())["recordWriterReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(world.original_owner.errors, [])

    def test_cancellation_before_and_during_completion_never_becomes_success(self):
        for during in (False, True):
            with self.subTest(during=during):
                world = CompletionWorld()
                if during:
                    world.metadata_close_hook = lambda *_args: world.cancel_handoff()
                else:
                    world.cancel_handoff()
                with self.assertRaises(Refusal):
                    world.complete()
                self.assertEqual(world.original_owner.errors, [])

    def test_guarded_uses_original_completion_fence_and_late_flush_cannot_renew_it(self):
        world = CompletionWorld()
        class LateOutput(io.BytesIO):
            def flush(self):
                world.seconds += 45
        output = LateOutput()
        world.namespace["sys"].stdout.buffer = output
        with self.assertRaises(Refusal):
            world.namespace["guarded"](lambda _cancelled: world.complete())
        escaped = json.loads(output.getvalue())
        self.assertEqual(escaped["producerReturnSha256"], hashlib.sha256(world.record()).hexdigest())
        self.assertEqual(json.loads(world.record())["producerStepOutcome"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")

    def test_guarded_handler_restore_failure_keeps_original_error_and_emits_nothing(self):
        world, failure = CompletionWorld(), FalseyFailure()
        actual = world.set_signal
        def changed(number, handler):
            if handler is world.original_signals[number]:
                throw(failure)
            actual(number, handler)
        world.namespace["signal"].signal = changed
        with self.assertRaises(FalseyFailure) as caught:
            world.namespace["guarded"](lambda _cancelled: world.complete())
        self.assertIs(caught.exception, failure)
        self.assertEqual(world.namespace["sys"].stdout.buffer.getvalue(), b"")

    def test_complete_command_glue_executes_with_real_new_handoff_custody_over_modeled_predecessors(self):
        adoption, handoff = AdoptionWorld(), prior["World"]()
        exec(CODE, handoff.namespace)
        handoff.namespace["query"]._component = lambda name: require(name == "dependency-save-handoff", "MODEL_FIXED_CHILD")
        def original_handoff(current):
            require(current is adoption.current and adoption.barrier, "MODEL_COMPOSED_ENTRY")
            return handoff.run_handoff()
        adoption.namespace["save_handoff_after_entry"] = original_handoff
        value, fence, hard = adoption.run()
        self.assertEqual(value["scope"], "BOOTSTRAP_PRODUCER_PENDING_ORIGINAL_STEP_RETURN_V1")
        self.assertIs(fence, handoff.meta_owner.fence)
        self.assertEqual(hard, json.loads(handoff.stored()["save-handoff.json"])["window"]["hardEndNs"])
        self.assertEqual(adoption.owners[0].closes, 1)
        self.assertEqual(adoption.owners[0].errors, [])


if __name__ == "__main__":
    unittest.main()
