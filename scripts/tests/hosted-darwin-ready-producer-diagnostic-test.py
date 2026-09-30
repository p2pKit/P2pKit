#!/usr/bin/env python3
"""Three offline READY-producer diagnostic controls, not ownership/cause proof.

Only the current runtime executes. Historical source is inert text/AST DATA.
The pinned startup module supplies bounded memory endpoints, not its test run.
Invoke only: python3 -I -B -S scripts/tests/hosted-darwin-ready-producer-diagnostic-test.py
"""
import ast
import contextlib
import copy
import hashlib
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
STARTUP_PATH = ROOT / "scripts/tests/hosted-darwin-context-startup-diagnostic-test.py"
STARTUP_SHA256 = "4f0c69284f92a30f45c0f170bae18520b824b14443139af5f1ebdd1b8944c784"
PREIMAGE = "db90735880ff020f027a91c695221963bbebce07a3ee7e7e624622692931c852"
INVERSE_PREIMAGE = "d2e9583eb57e2b85e5e1faa5ec9d50d10c093a8d70ecba198080b86431fb27a3"
METHODS = (
    "test_01_real_ready_predicates_original_exception_and_nonentry",
    "test_02_schema_capsule_and_actual_terminal_gate",
    "test_03_exact_inverse_preservation_and_mutations",
)
FIELD_PAIRS = (
    ("pid", "PID"), ("parentPid", "PARENT_PID"), ("uniqueId", "UNIQUE_ID"),
    ("parentUniqueId", "PARENT_UNIQUE_ID"), ("pidVersion", "PID_VERSION"),
    ("startSeconds", "START_SECONDS"), ("startMicroseconds", "START_MICROSECONDS"),
    ("uid", "UID"), ("realUid", "REAL_UID"), ("gid", "GID"), ("realGid", "REAL_GID"), ("status", "STATUS"),
)
TOKENS = tuple(token for _key, token in FIELD_PAIRS)
DETAIL_PREFIX = "P2PKIT_CONTEXT_SERVICE_READY_PRODUCER|"
READY_PRIMARY = b"P2PKIT_CONTEXT_FAILURE|IDENTITY|IDENTITY_CHANGED|NONE\n"
ABSENT = object()

if len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_site or not sys.dont_write_bytecode:
    raise SystemExit("FIXED_OFFLINE_READY_PRODUCER_INVOCATION_REQUIRED")
if hashlib.sha256(STARTUP_PATH.read_bytes()).hexdigest() != STARTUP_SHA256:
    raise SystemExit("EXACT_ADAPTED_STARTUP_HELPER_REQUIRED")
spec = importlib.util.spec_from_file_location("darwin_context_startup_suite_for_ready", STARTUP_PATH)
STARTUP = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = STARTUP
spec.loader.exec_module(STARTUP)  # Installs the persistent no-process/network/write/native fence.
M, CLOCK = STARTUP.M, STARTUP.CLOCK
BINDING, CANARY = STARTUP.BINDING, STARTUP.CANARY


def detail(operand, predicate, *fields):
    return {"operand": operand, "predicate": predicate, "fields": list(fields)}


def ready_error(value=ABSENT):
    error = M.ExperimentError("IDENTITY", "IDENTITY_CHANGED")
    error.ready_site, error.args = "READY_PRODUCER", (CANARY,)
    if value is not ABSENT:
        error.ready_producer = value
    return error


def capsule(value=ABSENT, *, case="N1", producer=False):
    result = STARTUP.capsule_fixture(case=case, failure=["IDENTITY", "IDENTITY_CHANGED", "NONE"],
        site="CHILD_READY_VALIDATE", ready="READY_PRODUCER", producer=producer)
    if value is not ABSENT:
        result.update(schema=2, readyProducer=copy.deepcopy(value))
    return result


def expected_lines(value=ABSENT, *, case="N1", producer=False):
    result = (STARTUP.SERVICE_PREFIX + case + "|CHILD_READY_VALIDATE|READY_PRODUCER|IDENTITY|IDENTITY_CHANGED|NONE",)
    if value is not ABSENT:
        result += (DETAIL_PREFIX + "|".join((case, value["operand"], value["predicate"],
                                            ",".join(value["fields"]) or "NONE")),)
    if producer:
        result += (STARTUP.REPORTED_PREFIX + case + "|IDENTITY|IDENTITY_CHANGED|NONE",)
    return result


def finite_details():
    # Exhaust the finite detail grammar once; cases/P-presence cycle separately.
    for operand in ("REPORTED", "OBSERVED"):
        for predicate in ("TYPE", "KEYS"):
            yield detail(operand, predicate)
        for predicate in ("PID", "UNIQUE_ID", "STATUS"):
            yield detail(operand, predicate, predicate)
        for mask in range(1, 1 << 12):
            yield detail(operand, "VALUES", *(token for index, token in enumerate(TOKENS) if mask & (1 << index)))
    for mask in range(1, 1 << 11):
        yield detail("PAIR", "EQUALITY", *(token for index, token in enumerate(TOKENS[:-1]) if mask & (1 << index)))


class ArmedKey(str):
    """Construct a dict normally, then forbid inspecting an untrusted key."""
    armed = False

    def __hash__(self):
        if self.armed:
            raise AssertionError("READY_KEY_HASH_FORBIDDEN")
        return str.__hash__(self)

    def __eq__(self, other):
        if self.armed:
            raise AssertionError("READY_KEY_EQUALITY_FORBIDDEN")
        return str.__eq__(self, other)

    def __str__(self):
        raise AssertionError("READY_KEY_STRINGIFICATION_FORBIDDEN")

    __repr__ = __str__


class ReadyProducerDiagnostic(unittest.TestCase):
    # Deliberately do not inherit any of the four existing test methods.
    _guard_error = STARTUP.StartupDiagnostic._guard_error
    _foreground = STARTUP.StartupDiagnostic._foreground
    _refused = STARTUP.StartupDiagnostic._refused

    @contextlib.contextmanager
    def _no_io(self):
        with contextlib.ExitStack() as stack:
            endpoints = [stack.enter_context(patch.object(owner, name, side_effect=AssertionError("NO_READY_DIAGNOSTIC_IO")))
                         for owner, name in ((M, "shared_raw_ns"), (M, "read_file"), (M, "read_frame"),
                             (M, "send_frame"), (M, "Darwin"), (M.os, "read"), (M.os, "open"), (M.os, "write"),
                             (M.subprocess, "Popen"), (M.socket, "socket"), (M.socket, "socketpair"),
                             (M.select, "select"), (M.ProbePipes, "pump"), (M.ProbePipes, "finish"))]
            yield
            for endpoint in endpoints:
                endpoint.assert_not_called()

    def _safe(self, lines):
        self.assertIs(type(lines), tuple)
        self.assertLessEqual(len(lines), 3)
        for line in lines:
            self.assertIs(type(line), str)
            self.assertTrue(line.isascii())
            self.assertLessEqual(len(line), 256)  # All12 finite field tokens, never raw values.
            for forbidden in ("\n", "\r", CANARY, BINDING, str(STARTUP.PARENT)):
                self.assertNotIn(forbidden, line)

    def _ready_error(self, fixture):
        original = copy.deepcopy(fixture.__dict__)
        same_identity, calls, failures = M.same_identity, [], []

        def observe(actual, expected):
            calls.append((actual, expected))
            try:
                return same_identity(actual, expected)
            except M.ExperimentError as error:
                failures.append(error)
                raise

        with patch.object(M, "same_identity", side_effect=observe):
            error = self._guard_error(lambda: M.validate_ready(fixture.ready, fixture.prepared,
                                      fixture.service, fixture.producer), "READY_PRODUCER")
        self.assertEqual(len(failures), 1)
        self.assertIs(error, failures[0], "BARE_RETHROW_MUST_PRESERVE_ORIGINAL_GUARD_OBJECT")
        self.assertIs(type(error), M.ExperimentError)
        self.assertEqual((error.stage, error.reason, error.errno_name), ("IDENTITY", "IDENTITY_CHANGED", "NONE"))
        self.assertEqual(len(calls), 2)
        for actual, expected in zip(calls, ((fixture.ready["payload"]["parent"], fixture.service),
                                           (fixture.ready["payload"]["producer"], fixture.producer))):
            self.assertIs(actual[0], expected[0])
            self.assertIs(actual[1], expected[1])
        self.assertEqual(fixture.__dict__, original, "DIAGNOSTIC_MUST_NOT_MUTATE_HELD_OPERANDS")
        return error

    def test_01_real_ready_predicates_original_exception_and_nonentry(self):
        self.assertEqual(M.READY_PRODUCER_FIELDS, FIELD_PAIRS)
        self.assertEqual(M.IDENTITY_KEYS, frozenset(key for key, _token in FIELD_PAIRS))
        classifier = M.classify_ready_producer

        def refused(fixture, wanted):
            with patch.object(M, "classify_ready_producer", wraps=classifier) as classified:
                error = self._ready_error(fixture)
            classified.assert_called_once()
            self.assertIs(classified.call_args.args[0], fixture.ready["payload"]["producer"])
            self.assertIs(classified.call_args.args[1], fixture.producer)
            self.assertEqual(error.ready_producer, wanted)
            self.assertIs(M._ready_producer_detail(error.ready_producer), True)
            error.args, error.private_context = (CANARY,), CANARY
            companion = M.startup_failure_record(error, "N1", BINDING, "CHILD_READY_VALIDATE", None)
            self.assertEqual(companion, STARTUP.RECORD_PREFIX + STARTUP.canonical(capsule(wanted)))
            lines = M.parse_startup_record(READY_PRIMARY + companion, "N1", BINDING)
            self.assertEqual(lines, expected_lines(wanted))
            self._safe(lines)

        def replace_operand(fixture, operand, value):
            if operand == "REPORTED":
                fixture.ready["payload"]["producer"] = value
            else:
                fixture.producer = value

        with self._no_io():
            for operand in ("REPORTED", "OBSERVED"):
                # Every reported example remains JSON-representable, so the
                # real frame/shape/account/parent guards precede READY_PRODUCER.
                for index, bad in enumerate((None, True, 7, 1.25, [], CANARY)):
                    with self.subTest(operand=operand, type_case=index):
                        fixture = STARTUP.prepared_fixture()
                        replace_operand(fixture, operand, bad)
                        refused(fixture, detail(operand, "TYPE"))
                for key, _token in FIELD_PAIRS:
                    fixture = STARTUP.prepared_fixture()
                    bad = copy.deepcopy(fixture.producer)
                    del bad[key]
                    replace_operand(fixture, operand, bad)
                    with self.subTest(operand=operand, missing=key):
                        refused(fixture, detail(operand, "KEYS"))
                fixture = STARTUP.prepared_fixture()
                bad = dict(fixture.producer, **{CANARY: -1})
                replace_operand(fixture, operand, bad)
                refused(fixture, detail(operand, "KEYS"))
                for key, token in FIELD_PAIRS:
                    for index, bad_value in enumerate((True, -1, 1.25, None, CANARY, [], {})):
                        fixture = STARTUP.prepared_fixture()
                        bad = copy.deepcopy(fixture.producer)
                        bad[key] = bad_value
                        replace_operand(fixture, operand, bad)
                        with self.subTest(operand=operand, field=token, invalid_value=index):
                            refused(fixture, detail(operand, "VALUES", token))
                for key, value, predicate in (("pid", 0, "PID"), ("uniqueId", 0, "UNIQUE_ID"),
                                               ("status", 0, "STATUS"), ("status", 5, "STATUS")):
                    fixture = STARTUP.prepared_fixture()
                    bad = dict(fixture.producer)
                    bad[key] = value
                    replace_operand(fixture, operand, bad)
                    refused(fixture, detail(operand, predicate, predicate))
                fixture = STARTUP.prepared_fixture()
                bad = dict(reversed(tuple(fixture.producer.items())))
                bad.update(pid=0, uniqueId=0, status=0, parentPid=-1, realGid=CANARY)
                replace_operand(fixture, operand, bad)
                refused(fixture, detail(operand, "VALUES", "PARENT_PID", "REAL_GID"))
                bad.update(parentPid=202, realGid=20)
                refused(fixture, detail(operand, "PID", "PID"))
                bad["pid"] = 303
                refused(fixture, detail(operand, "UNIQUE_ID", "UNIQUE_ID"))
                bad["uniqueId"] = 3030
                refused(fixture, detail(operand, "STATUS", "STATUS"))

            fixture = STARTUP.prepared_fixture()
            fixture.ready["payload"]["producer"]["status"], fixture.producer = 0, None
            refused(fixture, detail("REPORTED", "STATUS", "STATUS"))
            fixture = STARTUP.prepared_fixture()
            fixture.ready["payload"]["producer"]["pidVersion"] += 1
            fixture.producer["status"] = 0
            refused(fixture, detail("OBSERVED", "STATUS", "STATUS"))
            for key, token in FIELD_PAIRS[:-1]:
                fixture = STARTUP.prepared_fixture()
                fixture.ready["payload"]["producer"][key] += 1
                with self.subTest(equality_field=token):
                    refused(fixture, detail("PAIR", "EQUALITY", token))
            for changed in (("realGid", "startMicroseconds", "pidVersion", "pid"),
                            tuple(key for key, _token in reversed(FIELD_PAIRS[:-1]))):
                fixture = STARTUP.prepared_fixture()
                reported = fixture.ready["payload"]["producer"] = dict(reversed(tuple(fixture.producer.items())))
                for key in changed:
                    reported[key] += 1
                reported["status"] = 4
                refused(fixture, detail("PAIR", "EQUALITY", *(token for key, token in FIELD_PAIRS if key in changed)))

            for reported_status in (1, 2, 3, 4):
                for observed_status in (1, 2, 3, 4):
                    fixture = STARTUP.prepared_fixture()
                    fixture.ready["payload"]["producer"]["status"] = reported_status
                    fixture.producer["status"] = observed_status
                    fixture.ready["payload"]["parent"]["status"] = 4
                    original = copy.deepcopy(fixture.__dict__)
                    with patch.object(M, "classify_ready_producer", wraps=classifier) as classified:
                        self.assertIs(M.validate_ready(fixture.ready, fixture.prepared, fixture.service, fixture.producer),
                                      fixture.ready["payload"])
                    classified.assert_not_called()
                    self.assertIsNone(classifier(fixture.ready["payload"]["producer"], fixture.producer))
                    self.assertEqual(fixture.__dict__, original)

            def both_account(value):
                value.producer["realUid"] = value.ready["payload"]["producer"]["realUid"] = 502

            for site, mutate in (
                ("READY_SHAPE", lambda value: value.ready["payload"].update(sigtermDefault=False)),
                ("READY_ACCOUNT", lambda value: value.ready["payload"]["account"].update(groups=[20, 21])),
                ("READY_PARENT", lambda value: value.ready["payload"]["parent"].update(pidVersion=2)),
                ("READY_ACCOUNT", both_account),
                ("READY_BINDINGS", lambda value: value.ready["payload"].update(boot=CANARY)),
            ):
                fixture = STARTUP.prepared_fixture()
                mutate(fixture)
                original = copy.deepcopy(fixture.__dict__)
                with patch.object(M, "classify_ready_producer", wraps=classifier) as classified:
                    error = self._guard_error(lambda: M.validate_ready(fixture.ready, fixture.prepared,
                                              fixture.service, fixture.producer), site)
                classified.assert_not_called()
                self.assertFalse(hasattr(error, "ready_producer"))
                self.assertEqual(fixture.__dict__, original)

            # Inject only refusal objects at the unchanged producer call, to
            # establish exact-type/triple scope rather than claim guard causes.
            for injected in (M.ExperimentError("START", "IDENTITY_CHANGED"),
                             M.ExperimentError("IDENTITY", "REFUSED"),
                             M.ExperimentError("IDENTITY", "IDENTITY_CHANGED", "UNKNOWN"),
                             STARTUP.ErrorSubclass("IDENTITY", "IDENTITY_CHANGED")):
                fixture, same_identity = STARTUP.prepared_fixture(), M.same_identity
                injected.args = (CANARY,)

                def inject(actual, expected):
                    if expected is fixture.producer:
                        raise injected
                    return same_identity(actual, expected)

                with patch.object(M, "same_identity", side_effect=inject), \
                        patch.object(M, "classify_ready_producer", wraps=classifier) as classified:
                    with self.assertRaises(M.ExperimentError) as raised:
                        M.validate_ready(fixture.ready, fixture.prepared, fixture.service, fixture.producer)
                self.assertIs(raised.exception, injected)
                self.assertIsNone(injected.__context__)
                self.assertEqual(injected.ready_site, "READY_PRODUCER")
                self.assertFalse(hasattr(injected, "ready_producer"))
                classified.assert_not_called()

            for name, options in (
                ("classify_ready_producer", {"side_effect": RuntimeError(CANARY)}),
                ("classify_ready_producer", {"side_effect": SystemExit(CANARY)}),
                ("classify_ready_producer", {"return_value": STARTUP.Hostile()}),
                ("classify_ready_producer", {"return_value": None}),
                ("_ready_producer_detail", {"side_effect": SystemExit(CANARY)}),
                ("READY_PRODUCER_FIELDS", {"new": (("missing", "PID"),)}),
            ):
                fixture = STARTUP.prepared_fixture()
                fixture.ready["payload"]["producer"]["pidVersion"] += 1
                with patch.object(M, name, **options):
                    error = self._ready_error(fixture)
                self.assertFalse(hasattr(error, "ready_producer"))
                self.assertEqual(M.startup_failure_record(error, "N1", BINDING, "CHILD_READY_VALIDATE", None),
                                 STARTUP.RECORD_PREFIX + STARTUP.canonical(capsule()))

            # These unsupported Python objects are tested directly, not passed
            # off as having crossed the real JSON READY frame validator.
            good = STARTUP.identity(303, 202)
            for operand in ("REPORTED", "OBSERVED"):
                for bad in (STARTUP.Hostile(), STARTUP.DictSubclass(good)):
                    args = (bad, good) if operand == "REPORTED" else (good, bad)
                    self.assertEqual(classifier(*args), detail(operand, "TYPE"))
                bad = {key: STARTUP.Hostile() for key, _token in FIELD_PAIRS}
                args = (bad, good) if operand == "REPORTED" else (good, bad)
                self.assertEqual(classifier(*args), detail(operand, "VALUES", *TOKENS))
                key = ArmedKey(CANARY)
                bad = dict(good)
                del bad["status"]
                bad[key] = 1
                key.armed = True
                args = (bad, good) if operand == "REPORTED" else (good, bad)
                self.assertEqual(classifier(*args), detail(operand, "KEYS"))
                for private, token in FIELD_PAIRS:
                    bad = dict(good)
                    bad[private] = STARTUP.IntegerSubclass(1)
                    args = (bad, good) if operand == "REPORTED" else (good, bad)
                    self.assertEqual(classifier(*args), detail(operand, "VALUES", token))

    def test_02_schema_capsule_and_actual_terminal_gate(self):
        self.assertEqual((M.STARTUP_BYTES, M.STARTUP_PREFIX), (2048, STARTUP.RECORD_PREFIX))
        wanted = detail("PAIR", "EQUALITY", "PID_VERSION")
        legacy = STARTUP.RECORD_PREFIX + STARTUP.canonical(capsule())
        pipes = STARTUP.buffered(bytearray(READY_PRIMARY))
        counts, combinations, count = {}, set(), 0
        with self._no_io():
            for count, value in enumerate(finite_details(), 1):
                case, producer = ("N1", "N2", "N3", "N4")[(count - 1) % 4], bool(((count - 1) // 4) % 2)
                combinations.add((case, producer))
                counts[value["predicate"]] = counts.get(value["predicate"], 0) + 1
                self.assertIs(M._ready_producer_detail(value), True)
                original = copy.deepcopy(value)
                companion = M.startup_failure_record(ready_error(value), case, BINDING, "CHILD_READY_VALIDATE",
                                                     pipes if producer else None)
                self.assertEqual(companion, STARTUP.RECORD_PREFIX + STARTUP.canonical(capsule(value, case=case, producer=producer)))
                raw = READY_PRIMARY + companion
                self.assertLessEqual(len(raw), 2048)
                self.assertEqual(raw.count(b"\n"), 2)
                lines = M.parse_startup_record(raw, case, BINDING)
                self.assertEqual(lines, expected_lines(value, case=case, producer=producer))
                self._safe(lines)
                self.assertEqual(value, original)
            self.assertEqual(count, 10247)
            self.assertEqual(counts, {"TYPE": 2, "KEYS": 2, "PID": 2, "UNIQUE_ID": 2,
                                     "STATUS": 2, "VALUES": 8190, "EQUALITY": 2047})
            self.assertEqual(combinations, {(case, producer) for case in ("N1", "N2", "N3", "N4") for producer in (False, True)})
            for endpoint in (pipes.pump, pipes.finish, pipes.process.poll, pipes.process.wait):
                endpoint.assert_not_called()
            self.assertEqual(pipes.data["stdout"], bytearray(READY_PRIMARY))
            self.assertEqual(M.startup_failure_record(ready_error(), "N1", BINDING, "CHILD_READY_VALIDATE", None), legacy)
            self.assertEqual(M.parse_startup_record(READY_PRIMARY + legacy, "N1", BINDING), expected_lines())

            # Locally unusable classification preserves the exact schema1
            # refusal; remotely malformed schema2 rejects the entire record.
            invalid_wire = [
                None, True, 7, CANARY, [], {},
                *({key: item for key, item in wanted.items() if key != removed}
                  for removed in ("operand", "predicate", "fields")),
                dict(wanted, extra=CANARY), dict(wanted, operand=CANARY), dict(wanted, predicate=CANARY),
                detail("PAIR", "TYPE"), detail("PAIR", "KEYS"), detail("PAIR", "VALUES", "PID"),
                detail("PAIR", "PID", "PID"), detail("PAIR", "EQUALITY"),
                detail("PAIR", "EQUALITY", "STATUS"), detail("PAIR", "EQUALITY", "PID", "STATUS"),
                detail("REPORTED", "EQUALITY", "PID"), detail("OBSERVED", "EQUALITY", "PID"),
                detail("REPORTED", "TYPE", "PID"), detail("OBSERVED", "KEYS", "PID"),
                detail("REPORTED", "VALUES"), detail("OBSERVED", "VALUES"),
                detail("REPORTED", "PID", "UNIQUE_ID"), detail("OBSERVED", "UNIQUE_ID", "PID"),
                detail("REPORTED", "STATUS", "PID"), detail("OBSERVED", "STATUS"),
                detail("PAIR", "EQUALITY", "PID", "PID"), detail("PAIR", "EQUALITY", "PID_VERSION", "PID"),
                detail("REPORTED", "VALUES", *reversed(TOKENS)), detail("OBSERVED", "VALUES", *(["PID"] * 13)),
                detail("PAIR", "EQUALITY", CANARY), detail("PAIR", "EQUALITY", 1),
                detail("PAIR", "EQUALITY", True), detail("PAIR", "EQUALITY", None),
                detail("PAIR", "EQUALITY", []), detail("PAIR", "EQUALITY", {}),
            ]
            for key in ("operand", "predicate", "fields"):
                for bad in (None, True, 7, {}, []):
                    invalid_wire.append(dict(wanted, **{key: bad}))
            invalid_wire.append(dict(wanted, fields="PID_VERSION"))
            invalid_python = [
                STARTUP.Hostile(), STARTUP.DictSubclass(wanted),
                dict(wanted, operand=STARTUP.StringSubclass("PAIR")),
                dict(wanted, predicate=STARTUP.StringSubclass("EQUALITY")),
                dict(wanted, fields=STARTUP.ListSubclass(["PID_VERSION"])),
                dict(wanted, fields=(("PID_VERSION",))),
                detail("PAIR", "EQUALITY", STARTUP.StringSubclass("PID_VERSION")),
            ]
            for key in ("operand", "predicate", "fields"):
                invalid_python.append(dict(wanted, **{key: STARTUP.Hostile()}))
            key = ArmedKey(CANARY)
            bad = {"operand": "PAIR", "predicate": "EQUALITY", key: ["PID_VERSION"]}
            key.armed = True
            invalid_python.append(bad)
            for index, invalid in enumerate((*invalid_wire, *invalid_python)):
                with self.subTest(invalid_detail=index):
                    self.assertIs(M._ready_producer_detail(invalid), False)
                    self.assertEqual(M.startup_failure_record(ready_error(invalid), "N1", BINDING,
                                                             "CHILD_READY_VALIDATE", None), legacy)
            for index, invalid in enumerate(invalid_wire):
                with self.subTest(received_invalid_detail=index):
                    self.assertEqual(M.parse_startup_record(STARTUP.capsule_bytes(capsule(invalid)), "N1", BINDING), ())
            with patch.object(M, "_ready_producer_detail", side_effect=SystemExit(CANARY)) as unavailable:
                self.assertEqual(M.startup_failure_record(ready_error(wanted), "N1", BINDING,
                                                         "CHILD_READY_VALIDATE", None), legacy)
                unavailable.assert_called_once_with(wanted)

            # The local optional object is copied before schema2 replaces1.
            encoded, seen = M.encoded, []

            def observe(value):
                if type(value) is dict and value.get("schema") == 2 and "readyProducer" in value:
                    seen.append(value)
                return encoded(value)

            with patch.object(M, "encoded", side_effect=observe):
                companion = M.startup_failure_record(ready_error(wanted), "N1", BINDING, "CHILD_READY_VALIDATE", None)
            self.assertEqual(companion, STARTUP.RECORD_PREFIX + STARTUP.canonical(capsule(wanted)))
            self.assertGreaterEqual(len(seen), 2)
            self.assertIsNot(seen[0]["readyProducer"], wanted)
            self.assertIsNot(seen[0]["readyProducer"]["fields"], wanted["fields"])
            self.assertEqual(seen[0]["readyProducer"], wanted)

            scopes = [(site, "NONE", ["IDENTITY", "IDENTITY_CHANGED", "NONE"])
                      for site in STARTUP.SITES if site != "CHILD_READY_VALIDATE"]
            scopes += [("CHILD_READY_VALIDATE", ready, ["IDENTITY", "IDENTITY_CHANGED", "NONE"])
                       for ready in (*STARTUP.READY, "NONE") if ready != "READY_PRODUCER"]
            scopes += [("CHILD_READY_VALIDATE", "READY_PRODUCER", failure) for failure in (
                ["IDENTITY", "REFUSED", "NONE"], ["IDENTITY", "IDENTITY_CHANGED", "UNKNOWN"],
                ["START", "STATUS_MISSING", "NONE"])]
            for site, ready, failure in scopes:
                error = M.ExperimentError(*failure)
                error.ready_site, error.ready_producer = ready, wanted
                expected = STARTUP.capsule_fixture(failure=failure, site=site, ready=ready, producer=False)
                self.assertEqual(M.startup_failure_record(error, "N1", BINDING, site, None),
                                 STARTUP.RECORD_PREFIX + STARTUP.canonical(expected))

            raw = STARTUP.capsule_bytes(capsule(wanted))
            changes = (
                ("schema", 1), ("schema", True), ("schema", 2.0), ("schema", 3),
                ("case", "N2"), ("case", CANARY), ("binding", "b" * 64), ("binding", CANARY),
                ("site", "CHILD_READY_READ"), ("site", CANARY), ("ready", "NONE"), ("ready", "READY_PARENT"),
                ("failure", ["IDENTITY", "REFUSED", "NONE"]), ("failure", ["IDENTITY", "IDENTITY_CHANGED", "UNKNOWN"]),
                ("failure", ["START", "STATUS_MISSING", "NONE"]), ("failure", ["START", "TIMEOUT", "NONE"]),
                ("timeout", ["READ_WAIT", "F3", "BODY"]), ("eof", ["F3", "HEADER", "EMPTY"]),
                ("producerFailure", ["IDENTITY", CANARY, "NONE"]), ("extra", CANARY),
            )
            for key, changed in changes:
                value = capsule(wanted)
                value[key] = changed
                self.assertEqual(M.parse_startup_record(STARTUP.capsule_bytes(value), "N1", BINDING), ())
            for removed in capsule(wanted):
                value = capsule(wanted)
                del value[removed]
                self.assertEqual(M.parse_startup_record(READY_PRIMARY + STARTUP.RECORD_PREFIX + STARTUP.canonical(value),
                                                       "N1", BINDING), ())
            for before, after in (
                (b'"schema":2', b'"schema":2,"schema":2'),
                (b'"readyProducer":', b'"readyProducer":null,"readyProducer":'),
                (b'"operand":"PAIR"', b'"operand":"PAIR","operand":"PAIR"'),
                (b'"fields":', b'"fields":[],"fields":'),
                (b'"schema":2', b'"schema": 2'),
                (b'IDENTITY_CHANGED|NONE\n', b'REFUSED|NONE\n'),
            ):
                self.assertEqual(raw.count(before), 1)
                changed = raw.replace(before, after, 1)
                self.assertNotEqual(changed, raw)
                self.assertEqual(M.parse_startup_record(changed, "N1", BINDING), ())
            malformed = (
                raw[:-1], raw + b"\n", raw + raw, raw.replace(b"\n", b"\r\n"),
                raw + CANARY.encode("ascii"), raw + b"x" * (2048 - len(raw)), raw + b"x" * (2049 - len(raw)),
                raw.replace(b"IDENTITY_CHANGED|NONE\n", CANARY.encode("ascii") + b"|NONE\n", 1),
                b"\xff\n", b"", None, [], {}, STARTUP.Hostile(), bytearray(raw), STARTUP.BytesSubclass(raw),
            )
            for index, invalid in enumerate(malformed):
                with self.subTest(malformed_record=index):
                    self.assertEqual(M.parse_startup_record(invalid, "N1", BINDING), ())
            for invalid in (CANARY, "N5", True, STARTUP.StringSubclass("N1"), STARTUP.Hostile()):
                self.assertEqual(M.parse_startup_record(raw, invalid, BINDING), ())
            for invalid in (CANARY, "b" * 64, True, STARTUP.StringSubclass(BINDING), STARTUP.Hostile()):
                self.assertEqual(M.parse_startup_record(raw, "N1", invalid), ())

        # Actual F main -> abort -> terminal/file gate, only memory/native
        # endpoints modeled by the bound existing helper. Schema2 adds no IO.
        maximum = detail("PAIR", "EQUALITY", *TOKENS[:-1])
        record = M.startup_failure_record(ready_error(maximum), "N1", BINDING, "CHILD_READY_VALIDATE", pipes)
        raw = READY_PRIMARY + record
        summary = "\n".join(expected_lines(maximum, producer=True)) + "\n"
        primary = STARTUP.PRIMARY + "\nP2PKIT_CONTEXT_PROTOCOL_EOF|N1|F4|HEADER|EMPTY\n"
        with self._foreground(raw=raw) as state:
            retained_events = copy.deepcopy(state.native.events)
            self.assertEqual(M.main(), 2)
            result = self._refused(state)
            self.assertEqual(state.output.getvalue(), summary + primary)
            self.assertEqual((len(state.opens), state.reads), (1, [2049]))
            self.assertEqual(result["cleanupErrors"], [])
            self.assertEqual(state.native.events, retained_events)
            self.assertEqual((state.native.wait.call_count, state.native.signal.call_count), (1, 0))
            order = list(state.order)
        with self._foreground(raw=READY_PRIMARY + legacy) as state:
            self.assertEqual(M.main(), 2)
            self._refused(state)
            self.assertEqual(state.order, order, "SCHEMA2_MUST_NOT_ADD_NATIVE_POLL_WAIT_READ_OR_CLOCK")
            self.assertEqual(state.output.getvalue(), "\n".join(expected_lines()) + "\n" + primary)
            self.assertEqual((len(state.opens), state.reads), (1, [2049]))

        for name, mutation in (
            ("event-absent", lambda state: state.native.events.clear()),
            ("registration-copy", lambda state: setattr(state.native, "attach_attempts", copy.deepcopy(state.native.attach_attempts))),
            ("watch-version", lambda state: state.native.watched[202].update(pidVersion=2)),
            ("replaced-current", lambda state: setattr(state, "replace_current", True)),
        ):
            with self.subTest(schema2_gate=name), self._foreground(raw=raw, mutation=mutation) as state:
                self.assertEqual(M.main(), 2)
                self._refused(state)
                self.assertEqual(state.output.getvalue(), primary)
                self.assertEqual((state.opens, state.reads, state.stats), ([], [], {}))
                self.assertNotIn("no-symlink", state.order)
        for fault in ("symlink", "overread", "fd-changed"):
            with self.subTest(schema2_file=fault), self._foreground(raw=raw, file_fault=fault) as state:
                self.assertEqual(M.main(), 2)
                self.assertEqual(self._refused(state)["cleanupErrors"], [])
                self.assertEqual(state.output.getvalue(), primary)
                self.assertLessEqual(len(state.opens), 1)
                self.assertLessEqual(len(state.reads), 1)
        for invalid in (STARTUP.capsule_bytes(capsule(detail("PAIR", "EQUALITY", CANARY))), b"x" * 2049):
            with self._foreground(raw=invalid) as state:
                self.assertEqual(M.main(), 2)
                self.assertEqual(self._refused(state)["cleanupErrors"], [])
                self.assertEqual(state.output.getvalue(), primary)
                self.assertLessEqual(len(state.reads), 1)
        with self._foreground(raw=raw, diagnostic_error=True) as state:
            self.assertEqual(M.main(), 2)
            self.assertEqual(self._refused(state)["cleanupErrors"], [])
            self.assertEqual(state.output.getvalue(), primary)
            self.assertEqual(state.opens, [])
        different = M.ExperimentError("IDENTITY", "REFUSED", "UNKNOWN")
        with self._foreground(raw=raw, primary_error=different) as state:
            self.assertEqual(M.main(), 2)
            self._refused(state)
            self.assertEqual(state.output.getvalue(), summary + "P2PKIT_CONTEXT_FAILURE|IDENTITY|REFUSED|UNKNOWN\n")

    def test_03_exact_inverse_preservation_and_mutations(self):
        source = STARTUP.SOURCE.read_text(encoding="utf-8")
        self.assertEqual(CLOCK.READY_PRODUCER_BASE_RUNTIME_SHA256, PREIMAGE)
        self.assertEqual(len(CLOCK.READY_PRODUCER_PATCH), 5)
        prior = CLOCK.restore_ready_producer_runtime(source)
        self.assertNotEqual(source, prior)
        self.assertEqual(hashlib.sha256(prior.encode("utf-8")).hexdigest(), PREIMAGE)
        restores = (CLOCK.restore_ready_producer_runtime, CLOCK.restore_startup_diagnostic_runtime,
                    CLOCK.restore_protocol_timeout_runtime, CLOCK.restore_protocol_eof_runtime,
                    CLOCK.restore_plist_name_runtime, CLOCK.restore_admin_return_runtime, CLOCK.restore_runtime)
        hashes = (
            PREIMAGE,
            "fac1691819a7a201851fa4c6062f2f9d272d6ab7635c4b613746a88f58e50754",
            "17b7105e3dab4dcf865d8fda633f988b9ad78d1b286e0ecbb215da8d2828da47",
            "e92c291407c4b1f6f000a675c07190b34c340cd6b17648e5d73fd8a610e9acac",
            "c2726e3b3e43544f813f567f674473f52636fa165f70766a1f0f7cd1e18dc1bf",
            "5224a331a6570a913aa3c34ac1785d2ae744688fbfe9e4329ba587e36586ba1b",
            "a3904f34c48f85d1e0b93b8a6f24f61423e9533030c9328c61916862c46b623d",
        )
        for restore, expected in zip(restores, hashes):
            self.assertEqual(hashlib.sha256(restore(source).encode("utf-8")).hexdigest(), expected)
        for restore in restores[1:]:
            with patch.object(CLOCK, "restore_ready_producer_runtime", wraps=restores[0]) as newest:
                restore(source)
                newest.assert_called_once_with(source)
        self.assertEqual((len(CLOCK.STARTUP_DIAGNOSTIC_PATCH), len(CLOCK.PROTOCOL_TIMEOUT_PATCH),
                          len(CLOCK.PROTOCOL_EOF_PATCH), len(CLOCK.PLIST_NAME_PATCH), len(CLOCK.ADMIN_RETURN_PATCH),
                          len(CLOCK.RUNTIME_PATCH), len(CLOCK.WORKFLOW_PATCH), len(CLOCK.EXPERIMENT_TEST_PATCH)),
                         (10, 13, 7, 3, 8, 8, 3, 3))

        # Every byte of the older inverse, including its pins, hunk tuples and
        # exact33/3/6 substitution limits, remains independently recoverable.
        inverse = STARTUP.INVERSE.read_text(encoding="utf-8")
        start = inverse.index("# The finite READY-producer diagnostic")
        end = inverse.index("# The startup-only diagnostic", start)
        old_inverse = inverse[:start] + inverse[end:]
        start = old_inverse.index("def restore_ready_producer_runtime(source):\n")
        end = old_inverse.index("def restore_startup_diagnostic_runtime(source):\n", start)
        old_inverse = old_inverse[:start] + old_inverse[end:]
        chaining = "    source = restore_ready_producer_runtime(source)\n"
        self.assertEqual(old_inverse.count(chaining), 1)
        old_inverse = old_inverse.replace(chaining, "", 1)
        self.assertEqual(hashlib.sha256(old_inverse.encode("utf-8")).hexdigest(), INVERSE_PREIMAGE)

        def reject(changed):
            self.assertNotEqual(changed, source, "MUTATION_MUST_CHANGE_SUPPLIED_CURRENT_SOURCE")
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(changed)

        for index, (before, after) in enumerate(CLOCK.READY_PRODUCER_PATCH):
            with self.subTest(new_hunk=index):
                self.assertIs(type(before), str)
                self.assertIs(type(after), str)
                self.assertNotEqual(before, after)
                self.assertEqual(source.count(after), 1)
                reject(source.replace(after, before, 1))
                reject(source + after)
                reject(source.replace(after, after + "\n# UNREVIEWED_READY_HUNK_TAIL\n", 1))
                changed = list(CLOCK.READY_PRODUCER_PATCH)
                changed[index] = (before + "\n# WRONG_READY_PREIMAGE\n", after)
                with patch.object(CLOCK, "READY_PRODUCER_PATCH", tuple(changed)):
                    for restore in restores:
                        with self.assertRaises(AssertionError):
                            restore(source)
        for changed in (CLOCK.READY_PRODUCER_PATCH[:-1], CLOCK.READY_PRODUCER_PATCH + CLOCK.READY_PRODUCER_PATCH[:1]):
            with patch.object(CLOCK, "READY_PRODUCER_PATCH", changed):
                for restore in restores:
                    with self.assertRaises(AssertionError):
                        restore(source)
        for bad in (None, b"", "", STARTUP.StringSubclass(source), prior, source + "\n# UNRELATED_READY_MUTATION\n"):
            for restore in restores:
                with self.assertRaises(AssertionError):
                    restore(bad)

        # Each intended current-source violation is present and actually
        # changed. No missing-newest-hunk preimage input substitutes for this.
        mutations = (
            ('type(value) is not dict or len(value) != 3', 'False'),
            ('len(value) != len(IDENTITY_KEYS) or not all(type(key) is str for key in value)', 'False'),
            ('type(value[key]) is not int or value[key] < 0', 'value[key] < 0'),
            ('fields != [token for _key, token in READY_PRODUCER_FIELDS if token in fields]', 'False'),
            ('return predicate == "EQUALITY" and bool(fields) and "STATUS" not in fields', 'return True'),
            ('if key != "status" and reported[key] != observed[key]',
             'if key not in ("status", "pidVersion") and reported[key] != observed[key]'),
            ('("parentPid", "PARENT_PID")', '("parentPid", "PID")'),
            ('ready_site == "READY_PRODUCER" and type(error) is ExperimentError', 'True'),
            ('type(error.errno_name) is str and error.errno_name == "NONE" and type(payload) is dict', 'True'),
            ('detail = classify_ready_producer(payload["producer"], producer_identity)',
             'detail = classify_ready_producer(producer_identity, payload["producer"])'),
            ('                    error.ready_producer = detail\n        raise\n',
             '                    error.ready_producer = detail\n        return payload\n'),
            ('type(schema) is not int or schema not in (1, 2)', 'False'),
            ('set(value) != (STARTUP_KEYS if schema == 1 else STARTUP_KEYS | {"readyProducer"})', 'False'),
            ('body != encoded(value)', 'False'),
            ('failure != ["IDENTITY", "IDENTITY_CHANGED", "NONE"] or timeout is not None or eof is not None', 'False'),
            ('",".join(detail["fields"]) or "NONE"', 'str(detail)'),
            ('                if _ready_producer_detail(detail):\n                    # Build independently',
             '                if True:\n                    # Build independently'),
            ('value = {**value, "schema": 2, "readyProducer": {', 'value = {**value, "schema": 1, "readyProducer": {'),
            ('"fields": list(detail["fields"])', '"fields": detail["fields"]'),
            ('STARTUP_BYTES = 2048', 'STARTUP_BYTES = 65536'),
            ('if len(lines) != 3 or lines[-1] != b"" or not lines[1].startswith(STARTUP_PREFIX):', 'if False:'),
            ('IDENTITY_KEYS - {"status"}', 'IDENTITY_KEYS - {"status", "pidVersion"}'),
            ('same_identity(payload["producer"], producer_identity)', 'same_identity(payload["producer"], payload["producer"])'),
            ('identity_account(producer_identity, prepared["account"])', 'validate_account(prepared["account"])'),
            ('producer_identity["parentUniqueId"] == service_identity["uniqueId"]', 'True'),
            ('payload["sourceSha256"] == prepared["source"]["files"][SCRIPT]', 'True'),
            ('payload["interpreter"] == prepared["interpreter"]["path"]', 'True'),
            ('context.native.watch(producer_identity)', 'context.native.same(producer_identity)'),
            ('return left(end_ns, "START")', 'return left(end_ns + NS, "START")'),
            ('CASE_SECONDS = 120, 180, 40', 'CASE_SECONDS = 120, 180, 41'),
            ('ABORT_SECONDS, FREEZE_SECONDS, EXPORT_SECONDS = 120, 60, 120',
             'ABORT_SECONDS, FREEZE_SECONDS, EXPORT_SECONDS = 121, 60, 120'),
            ('JOB_SECONDS, STEP_SECONDS = 1440, 720', 'JOB_SECONDS, STEP_SECONDS = 1441, 721'),
            ('UPLOAD_SECONDS, ADMIN_SECONDS = 420, 10', 'UPLOAD_SECONDS, ADMIN_SECONDS = 421, 11'),
            ('FRAME_BYTES, STREAM_BYTES, EVIDENCE_BYTES, EVIDENCE_MEMBERS = 16384, 65536, 2 * 1024 * 1024, 128',
             'FRAME_BYTES, STREAM_BYTES, EVIDENCE_BYTES, EVIDENCE_MEMBERS = 16385, 65537, 3 * 1024 * 1024, 129'),
            ('require(not ancillary and flags == 0, stage, "REFUSED")', 'require(True, stage, "REFUSED")'),
            ('not any(key in os.environ for key in OWNER_ENV)', 'True'),
            ('[interpreter["path"], "-I", "-B", "-S", str(ROOT / SCRIPT), "_probe", str(child_fd)]',
             '[interpreter["path"], str(ROOT / SCRIPT), "_probe", str(child_fd)]'),
            ('close_fds=True, pass_fds=(child_fd,), cwd=ROOT, env=environment',
             'close_fds=False, pass_fds=(), cwd=ROOT, env=environment'),
            ('require(channel.fileno() == -1, "CLOSE", "RESOURCE_UNKNOWN")', 'require(True, "CLOSE", "RESOURCE_UNKNOWN")'),
            ('state["producer"] is not None or not state["prepareSent"]', 'True'),
            ('context.sentinel_closed and context.sentinel_pipes.closed and context.native.closed', 'True'),
            ('not context.export_called and context.recipient is context.recipient_original', 'True'),
            ('context.current is not state', 'False'),
            ('not any(item is registration for item in native.attach_attempts)', 'False'),
            ('decoded = decode_exit_event(terminal["event"], pid)', 'decoded = terminal["status"]'),
            ('stat.S_IMODE(before.st_mode) != 0o600', 'False'),
            ('raw = read_file(path, STARTUP_BYTES)', 'raw = read_file(path, STREAM_BYTES)'),
        )
        for index, (before, after) in enumerate(mutations):
            with self.subTest(current_guard=index):
                self.assertIn(before, source)
                reject(source.replace(before, after, 1))

        # Parsing is source-only: neither historical runtime nor historical
        # inverse is compiled, imported or behaviorally executed.
        tree, old_tree = ast.parse(source, feature_version=(3, 9)), ast.parse(prior, feature_version=(3, 9))
        current = {node.name: node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        original = {node.name: node for node in old_tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        self.assertEqual(set(current) - set(original), {"_ready_producer_detail", "classify_ready_producer"})
        self.assertFalse(set(original) - set(current))

        def segment(text, node):
            start = min([node.lineno] + [item.lineno for item in node.decorator_list])
            return "".join(text.splitlines(keepends=True)[start - 1:node.end_lineno])

        changed_functions = {"validate_ready", "parse_startup_record", "startup_failure_record"}
        for name, node in original.items():
            if name not in changed_functions:
                self.assertEqual(segment(source, current[name]), segment(prior, node), "UNCHANGED_BYTES_" + name)
        self.assertEqual(segment(source, current["same_identity"]), segment(prior, original["same_identity"]))
        self.assertEqual(segment(source, current["emit_startup_diagnostic"]),
                         segment(prior, original["emit_startup_diagnostic"]))
        self.assertEqual(len(current["validate_ready"].body), 2)
        self.assertEqual(len(original["validate_ready"].body), 2)
        self.assertEqual(ast.dump(current["validate_ready"].body[0]), ast.dump(original["validate_ready"].body[0]))
        ready, old_ready = current["validate_ready"].body[1], original["validate_ready"].body[1]
        self.assertIsInstance(ready, ast.Try)
        self.assertIsInstance(old_ready, ast.Try)
        for attr in ("body", "orelse", "finalbody"):
            self.assertEqual(tuple(ast.dump(node) for node in getattr(ready, attr)),
                             tuple(ast.dump(node) for node in getattr(old_ready, attr)), "ORIGINAL_READY_" + attr)
        self.assertEqual((len(ready.handlers), len(old_ready.handlers)), (1, 1))
        handler, old_handler = ready.handlers[0], old_ready.handlers[0]
        self.assertEqual(ast.dump(handler.type), ast.dump(old_handler.type))
        self.assertEqual(handler.name, old_handler.name)
        self.assertEqual((len(handler.body), len(old_handler.body)), (3, 2))
        self.assertEqual(ast.dump(handler.body[0]), ast.dump(old_handler.body[0]))
        self.assertEqual(ast.dump(handler.body[-1]), ast.dump(old_handler.body[-1]))
        self.assertIsInstance(handler.body[-1], ast.Raise)
        self.assertIsNone(handler.body[-1].exc)
        self.assertIsNone(handler.body[-1].cause)
        for name in ("_ready_producer_detail", "classify_ready_producer"):
            calls = {ast.unparse(node.func) for node in ast.walk(current[name]) if isinstance(node, ast.Call)}
            self.assertTrue(calls)
            self.assertLessEqual(calls, {"type", "len", "all", "set", "bool"}, "HELD_MEMORY_ONLY_" + name)


if __name__ == "__main__":
    if tuple(unittest.defaultTestLoader.getTestCaseNames(ReadyProducerDiagnostic)) != METHODS:
        raise SystemExit("FIXED_THREE_READY_PRODUCER_METHODS_REQUIRED")
    suite = unittest.TestSuite(ReadyProducerDiagnostic(name) for name in METHODS)
    result = unittest.TextTestRunner(verbosity=2, failfast=True).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
