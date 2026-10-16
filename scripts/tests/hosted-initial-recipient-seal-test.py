#!/usr/bin/env python3
"""Seal-only supplied controls: AUTHORED, not execution/retirement evidence.

The existing collect MODEL supplies tiny historical bytes and low-level Git
returns, not earlier test cases or successful old owner registries. This new
fixture supplies collect-close DATA, clock/host observations, HTTP transport
and a native process boundary. All new seal composition remains production
code. No actual process, HTTP, native library, GPG, provider or CI is invoked.
Host-shaped values exist only in module-local supplier namespaces, never the
real environment. Run only after independent source review, as a real nonroot
user in a frozen source copy; no monkeypatched uid or native acceptance.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from email.utils import format_datetime
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


_spec = importlib.util.spec_from_file_location("seal_supplied_lower_boundaries",
    Path(__file__).with_name("hosted_initial_collect_models.py"))
M = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = M
_spec.loader.exec_module(M)
D, NS, BOOT, TOKEN, wire, sha = M.D, M.NS, M.BOOT, M.TOKEN, M.wire, M.sha


def dispose_tail_unknown_captures(case, rig, scope, failure):
    """Only dispose two tiny fixture streams after all UNKNOWN assertions.

    No candidate owner/scope/sink close is called, no registry row is repaired,
    and no retirement claim results. This teardown is scoped to the two new
    tail-native refusal controls, not a general production cleanup fallback.
    """
    anchors = [anchor for anchor in D._CUSTODY_OWNERS.values()
        if any(resource is scope for _row, _label, resource, _attempted, _closed in anchor.rows)]
    case.assertEqual(len(anchors), 1)
    anchor = anchors[0]
    owner = anchor.owner
    case.assertIs(type(owner), D._CustodyOwner)
    case.assertIs(type(owner.fence), D._TailClock)
    case.assertIs(owner.__dict__, anchor.dictionary)
    case.assertIs(owner.original, failure)
    case.assertIs(anchor.failure, failure)
    case.assertIs(owner.unknown, True)
    case.assertIs(anchor.unknown, True)
    case.assertTrue(any(value is owner for value in D.native.QUARANTINE))
    rows, quarantine = anchor.rows, tuple(D.native.QUARANTINE)
    ledger = tuple((row, dict(row)) for row, *_rest in rows)
    flags = (owner.closed, anchor.closed, scope.close_calls, scope.closed, tuple(scope.drains))
    captures = [(row, label, sink, attempted, closed) for row, label, sink, attempted, closed in rows
        if label in ("stdout", "stderr")]
    case.assertEqual([label for _row, label, *_rest in captures], ["stdout", "stderr"])
    for row, label, sink, attempted, closed in captures:
        case.assertIs(type(sink), D.Q._PosixSink)
        case.assertIs(type(sink.stream), io.BufferedWriter)
        case.assertEqual(sink.path, rig.custody / "authority-seal/service" / (label + ".log"))
        case.assertIs(row["owner"], sink)
        case.assertIs(attempted, False)
        case.assertIs(closed, False)
        case.assertIs(sink.closed, False)
        case.assertIs(sink.stream.closed, False)
        opened, named = M.os.fstat(sink.stream.fileno()), sink.path.lstat()
        case.assertTrue(M.os.path.samestat(opened, named))
        case.assertEqual((opened.st_uid, opened.st_nlink), (M.os.geteuid(), 1))
    for _row, _label, sink, _attempted, _closed in captures:
        sink.stream.close()
        case.assertIs(sink.stream.closed, True)
        case.assertIs(sink.closed, False)
    case.assertIs(anchor.rows, rows)
    case.assertEqual(tuple(D.native.QUARANTINE), quarantine)
    case.assertEqual((owner.closed, anchor.closed, scope.close_calls, scope.closed, tuple(scope.drains)), flags)
    case.assertIs(owner.original, failure)
    case.assertIs(anchor.failure, failure)
    case.assertIs(owner.unknown, True)
    case.assertIs(anchor.unknown, True)
    for row, original in ledger:
        case.assertEqual(row, original)


class TailScope(M.Scope):
    """Only the new fixed child route; native.phase still owns its lifecycle."""
    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        M.ensure(cwd == str(M.ROOT) and environment.get(D.O.wire.TOKEN_ENV) == TOKEN and
            not any(name in environment for name in D._CREDENTIAL_NAMES if name != D.O.wire.TOKEN_ENV), "TAIL_FIXED_TOKEN")
        M.ensure(argv[5] == "_tail-authority" and argv[-2] == "--minimum-ns", "TAIL_FIXED_ROUTE")
        self.launches.append({"created": True, "requestedArgv": list(argv), "resolvedArgv": list(argv), "cwd": cwd,
            "pid": self.leader["pid"], "api": "subprocess.Popen", "shell": False,
            "executable": argv[0], "outputMode": "caller-owned-files"})
        self.identities.append(dict(self.leader))
        self.rig.events.append(("supplied-tail-spawn", environment[D.O.wire.TOKEN_ENV]))
        if self.rig.spawn_hook is not None:
            self.rig.spawn_hook(self)
        child_env = dict(environment)
        with self.rig.environment(child_env), patch.object(D.native, "sys", SimpleNamespace(
                **{**vars(sys), "stdout": SimpleNamespace(buffer=stdout.stream)})):
            D.native.guarded(lambda _signals: D._tail_authority_child(argv[7], int(argv[-1]), self.rig.clock.cancelled))
        M.ensure(D.O.wire.TOKEN_ENV not in child_env, "TAIL_CHILD_TOKEN_POPPED")
        return SimpleNamespace(pid=self.leader["pid"], stdout=None, stderr=None, poll=lambda: 0)


class TailRig(M.Rig):
    """No old collect/crypto/native successful return is manufactured or run."""
    def __enter__(self):
        super().__enter__()
        for name in ("_TAIL_ATTEMPTS", "_TAIL_INPUTS", "_TAIL_CLOCKS", "_TAIL_AUTHORITIES", "_TAIL_SEALS", "_TAIL_OUTPUTS"):
            self.stack.enter_context(patch.object(D, name, {}))
        (self.custody / "authority-2").mkdir(mode=0o700)
        frame = self.packets.transfer["originalWindow"]
        end = frame["readEndNs"]
        originals = {name: sha(("SUPPLIED-HISTORICAL-" + name).encode("ascii")) for name in D.N.ORIGINAL_KEYS}
        originals.update(event=sha(self.packets.raws["event"]), match=sha(self.packets.raws["original-match"]),
            candidate_policy_raw=sha(self.packets.raws["policy"]))
        phases = {name: sha(("SUPPLIED-HISTORICAL-PHASE-" + name).encode("ascii")) for name in D.native.PHASE_FILES}
        authority = {name: sha(("SUPPLIED-HISTORICAL-" + name).encode("ascii")) for name in
            ("contextSha256", "sourceBeforeSha256", "sourceAfterSha256", "querySessionSha256", "childSha256")}
        authority.update(expectedMatchSha256=originals["match"], freshMatchSha256=originals["match"],
            originalsSha256=originals, phaseSha256=phases, ackSha256=phases["stdout.log"], invocation="9" * 32,
            startedNs=end - 4 * NS, acquiredNs=end - 3 * NS, checkedNs=end - 2 * NS,
            closedNs=end - 2 * NS, workEndNs=end, finalEndNs=end)
        self.collected = {"schema": 1, "scope": D._COLLECT_SCOPE, "kind": self.kind, "edge": "POST_EXPORT",
            "predecessor": D._collect_predecessor(self.packets.raws, self.packets.transfer), "primary": self.packets.primary,
            "originalWindow": frame, "lastNs": end - NS, "lastLocal": 150.0, "authority": authority,
            "parentClose": {"schema": 1, "scope": "INITIAL_POST_EXPORT_AUTHORITY_PARENT_KNOWN_CLOSE_V1",
                "resources": [{"ordinal": 0, "label": "directory", "closeAttempted": True, "closed": True}],
                "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False},
            "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED", "testAcceptance": "NOT_PERFORMED",
            "productiveAuthority": False, "cacheAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        self.raws = {**self.packets.raws, "collect": wire(self.collected)}
        M.put(self.custody / "returned" / D._COLLECT_FILE, self.raws["collect"])
        self.env.update({D._TAIL_OUTCOME: "success", D._TAIL_HASH: sha(self.raws["collect"]),
            D._TAIL_EXPORT_HASH: sha(self.raws["manifest"])})
        self.clock.raw, self.clock.local = end + 5 * NS, 200.0
        self.original_local_end = self.clock.local + (frame["sealEndNs"] - self.clock.raw) / NS
        return self

    def replace_collect(self, change):
        change(self.collected)
        self.raws["collect"] = wire(self.collected)
        (self.custody / "returned" / D._COLLECT_FILE).write_bytes(self.raws["collect"])
        self.env[D._TAIL_HASH] = sha(self.raws["collect"])

    def request(self, path, token, invocation, fence, end):
        index = len(self.requests)
        M.ensure(index < 8 and token == TOKEN, "TAIL_ONE_HTTP_EPISODE")
        name, expected, body = self.packets.bodies[index]
        M.ensure(path == expected and type(fence) is D._TailClock and fence.side == "child" and end <= fence.work,
            "TAIL_HTTP_ROUTE_AND_CLIP")
        started = fence.now(limit=end)
        self.clock.advance(.002)
        finished = fence.now(limit=end)
        if self.http_hook is not None:
            body = self.http_hook(name, body)
        date = format_datetime(datetime.fromtimestamp(self.packets.use, timezone.utc), usegmt=True)
        headers = ("HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: private, no-store\r\n"
            "X-GitHub-Api-Version-Selected: 2022-11-28\r\nX-GitHub-Request-Id: SUPPLIED-SEAL\r\nDate: " + date +
            "\r\nContent-Length: " + str(len(body)) + "\r\n\r\n").encode("ascii")
        raw = wire({"schema": 1, "scope": D.O.RESPONSE_SCOPE, "origin": D.O.wire.ORIGIN, "method": "GET", "path": path,
            "invocation": invocation, "clock": D.O.clock_value(self.clock.identity), "startedNs": started, "finishedNs": finished,
            "status": 200, "headersBase64": base64.b64encode(headers).decode("ascii"),
            "bodyBase64": base64.b64encode(body).decode("ascii"), "complete": True, "retirement": "KNOWN", "error": None})
        self.requests.append((name, raw))
        return raw, None

    def scope(self, job, invocation, state, home):
        result = TailScope(self, job, invocation, state, home)
        self.scopes.append(result)
        return result

    def input(self):
        clock = D._TailClock(self.clock.reading(), self.clock.local, BOOT, self.clock.cancelled, side="parent")
        inputs = D._read_tail_input(clock, self.kind, D._tail_actual())
        expected = clock.bind_parent(inputs)
        return clock, inputs, expected

    def authority(self):
        self.env[D.O.wire.TOKEN_ENV] = TOKEN
        return D._tail_pre_metadata(self.kind, self.clock.cancelled)

    def closed(self):
        return D._retain_tail_seal(self.authority())

    def guarded_seal(self):
        self.env[D.O.wire.TOKEN_ENV] = TOKEN
        output = io.BytesIO()
        with patch.object(D.native, "sys", SimpleNamespace(**{**vars(sys), "stdout": SimpleNamespace(buffer=output)})):
            D.native.guarded(lambda _signals: D.seal(self.kind, self.clock.cancelled))
        return output.getvalue()


class PriorAndClockControls(unittest.TestCase):
    def test_gate_and_worker_historical_data_not_old_live_capabilities(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), TailRig(kind) as rig:
                parsed = D._tail_bundle(rig.raws)
                self.assertEqual(parsed[-1]["edge"], "POST_EXPORT")
                self.assertEqual(parsed[0]["originalWindow"], rig.collected["originalWindow"])
                self.assertEqual(D._COLLECT_CLOCKS, {})
                self.assertEqual(D._COLLECT_RETURNS, {})
                with self.assertRaisesRegex(Exception, "TAIL_NOT_ORIGINAL_INPUT"):
                    D._checked_tail_input(D._TailInput(tuple(rig.raws.items()), wire(M.close_record(("directory",)))))

    def test_canonical_roster_and_rehashed_prior_mutations_refuse(self):
        mutations = (
            lambda value: value.update(edge="SEAL"),
            lambda value: value.update(extra=True),
            lambda value: value.update(lastNs=value["originalWindow"]["readEndNs"]),
            lambda value: value.update(lastLocal=98.0),
            lambda value: value["authority"].update(freshMatchSha256="0" * 64),
            lambda value: value["authority"]["originalsSha256"].update(event="0" * 64),
            lambda value: value["parentClose"].update(retirement="UNKNOWN"),
            lambda value: value["parentClose"]["resources"][0].update(closed=False),
            lambda value: value.update(productiveAuthority=True),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation), TailRig() as rig:
                rig.replace_collect(mutation)
                with self.assertRaises(Exception):
                    D._tail_bundle(rig.raws)
        with TailRig() as rig:
            with self.assertRaises(Exception):
                D._tail_bundle({**rig.raws, "authority2-return": b"invented"})
            with self.assertRaises(Exception):
                D._tail_bundle({**rig.raws, "collect": rig.raws["collect"] + b" "})

    def test_rehashed_collect_split_caps_post_cap_close_last_and_exact_end_refuse(self):
        for kind in ("gate", "worker"):
            for changed in ("split-cap", "closed-after-cap", "last-after-cap", "last-equal-cap"):
                with self.subTest(kind=kind, changed=changed), TailRig(kind) as rig:
                    original_hash = rig.env[D._TAIL_HASH]
                    end = rig.collected["originalWindow"]["readEndNs"]
                    def invalid(value):
                        authority = value["authority"]
                        if changed == "split-cap":
                            # All samples precede both ends: refuse inequality,
                            # not an unrelated late-close/last observation.
                            authority["workEndNs"] = end - NS // 2
                        else:
                            cap = end - {"closed-after-cap": 5 * NS // 2,
                                "last-after-cap": 3 * NS // 2, "last-equal-cap": NS}[changed]
                            authority.update(workEndNs=cap, finalEndNs=cap)
                    rig.replace_collect(invalid)
                    self.assertNotEqual(rig.env[D._TAIL_HASH], original_hash)
                    self.assertEqual(rig.env[D._TAIL_HASH], sha(rig.raws["collect"]))
                    # The real input reader sees the rehashed successful Step
                    # DATA, then refuses its chronology before any live query.
                    with self.assertRaisesRegex(Exception, "TAIL_COLLECT_TIME"):
                        rig.input()
                    self.assertEqual(rig.queries, [])
                    self.assertEqual(rig.requests, [])

    def test_primary_crypto_collect_success_and_exact_hashes_required(self):
        for name, value in ((D.PRIMARY_OUTCOME, "failure"), (D._COLLECT_OUTCOME, "skipped"),
                (D._TAIL_OUTCOME, "failure"), (D._TAIL_HASH, "0" * 64), (D._TAIL_EXPORT_HASH, "0" * 64),
                (D._COLLECT_STEP_HASH, "0" * 64), (D.PRIMARY_HANDOFF, "0" * 64)):
            with self.subTest(name=name), TailRig() as rig:
                rig.env[name] = value
                with self.assertRaises(Exception):
                    rig.input()
                self.assertEqual(rig.queries, [])
                self.assertEqual(rig.requests, [])

    def test_original_read_may_expire_but_seal_is_not_renewed(self):
        with TailRig() as rig:
            first_raw, first_local = rig.clock.raw, rig.clock.local
            clock, inputs, _expected = rig.input()
            frame = rig.collected["originalWindow"]
            self.assertGreater(first_raw, frame["readEndNs"])
            self.assertEqual(clock.work, frame["sealEndNs"])
            self.assertLessEqual(clock.local_end, first_local + (frame["sealEndNs"] - first_raw) / NS)
            self.assertEqual(D._TAIL_INPUTS[id(inputs)][4].owner.local_end,
                D.O.wire._directed_deadline(first_local, 30, first_raw + 30 * NS, first_raw))
            self.assertNotEqual(clock.local_end, D._TAIL_INPUTS[id(inputs)][4].owner.local_end)
            self.assertEqual(D._COLLECT_CLOCKS, {})

    def test_parent_first30_remains_stricter_than_large_worker_seal_residue(self):
        with TailRig("worker") as rig:
            def earlier(value):
                value.update(lastNs=1185 * NS, lastLocal=150.0)
                value["authority"].update(startedNs=1180 * NS, acquiredNs=1181 * NS, checkedNs=1182 * NS,
                    closedNs=1183 * NS, workEndNs=1186 * NS, finalEndNs=1186 * NS)
            rig.replace_collect(earlier)
            rig.clock.raw = 1190 * NS
            clock, _inputs, _expected = rig.input()
            self.assertEqual(clock.work, 1220 * NS)
            self.assertLess(clock.work, rig.collected["originalWindow"]["sealEndNs"])

    def test_narrowing_precedes_other_reads_and_does_not_bind_authority(self):
        with TailRig() as rig:
            read = D._read_private
            seen = []
            def observed(owner, directory, name, maximum):
                clock = owner.owner.fence
                seen.append((name, clock._view().phase, clock.work))
                if name != D._EXPORT_STEP_FILE:
                    self.assertEqual(clock._view().phase, "NARROWED")
                    self.assertLessEqual(clock.work, rig.collected["originalWindow"]["sealEndNs"])
                return read(owner, directory, name, maximum)
            with patch.object(D, "_read_private", observed):
                clock, _inputs, _expected = rig.input()
            self.assertEqual(seen[0][0:2], (D._EXPORT_STEP_FILE, "METADATA"))
            self.assertEqual(clock._view().phase, "OPERATIVE")
            self.assertIsNone(clock._view().operative)
            self.assertEqual(rig.requests, [])

    def test_preliminary_expenditure_or_original_expiry_refuses_before_other_files(self):
        for expiry in ("raw", "local"):
            with self.subTest(expiry=expiry), TailRig() as rig:
                read = D._read_private
                calls = []
                def changed(owner, directory, name, maximum):
                    calls.append(name)
                    raw = read(owner, directory, name, maximum)
                    if name == D._EXPORT_STEP_FILE:
                        if expiry == "raw":
                            rig.clock.raw = rig.collected["originalWindow"]["sealEndNs"]
                        else:
                            rig.clock.local += 26
                    return raw
                with patch.object(D, "_read_private", changed), self.assertRaises(Exception):
                    rig.input()
                self.assertEqual(calls, [D._EXPORT_STEP_FILE])
                self.assertEqual(rig.queries, [])

    def test_clock_boot_local_raw_mutations_stay_failed_after_restoration(self):
        for changed in ("boot", "local", "raw", "binding", "frame"):
            with self.subTest(changed=changed), TailRig() as rig:
                clock, _inputs, _expected = rig.input()
                boot, local, raw, binding = rig.clock.boot, rig.clock.local, rig.clock.raw, clock._binding
                frame = clock.frame
                seal_end = frame["sealEndNs"]
                if changed == "boot":
                    rig.clock.boot = "0" * 64
                elif changed == "local":
                    rig.clock.local -= 1
                elif changed == "raw":
                    rig.clock.raw = clock.work
                elif changed == "binding":
                    clock._binding = tuple(list(binding))
                else:
                    frame["sealEndNs"] += NS
                with self.assertRaises(Exception) as first:
                    clock.now()
                rig.clock.boot, rig.clock.local, rig.clock.raw, clock._binding = boot, local, raw, binding
                frame["sealEndNs"] = seal_end
                with self.assertRaises(Exception) as second:
                    clock.now(final=True)
                self.assertIs(first.exception, second.exception)

    def test_collect_floors_and_equal_new_input_dictionary_cannot_be_rebound(self):
        for changed in ("raw", "local", "dictionary"):
            with self.subTest(changed=changed), TailRig() as rig:
                if changed != "dictionary":
                    if changed == "raw":
                        rig.clock.raw = rig.collected["lastNs"] - NS
                    else:
                        rig.clock.local = rig.collected["lastLocal"] - 1
                    # The historical packet remains valid; reject the new FIRST
                    # sample at binding, not a collect grammar mutation.
                    D._tail_bundle(rig.raws)
                    with self.assertRaisesRegex(Exception, "TAIL_BIND_COLLECT_FLOORS"):
                        rig.input()
                else:
                    clock, inputs, _expected = rig.input()
                    object.__setattr__(inputs, "__dict__", dict(inputs.__dict__))
                    with self.assertRaises(Exception):
                        clock.now()

    def test_reentry_narrowing_and_bind_reuse_are_terminal(self):
        for operation, code in (("narrow", "TAIL_NARROW_ONCE_BEFORE_BINDING"), ("bind", "TAIL_BIND_ONCE")):
            with self.subTest(operation=operation), TailRig() as rig:
                clock, inputs, _expected = rig.input()
                with self.assertRaisesRegex(Exception, code) as first:
                    if operation == "narrow":
                        clock.narrow_parent(rig.raws["step"])
                    else:
                        clock.bind_parent(inputs)
                with self.assertRaises(Exception) as second:
                    clock.now()
                self.assertIs(first.exception, second.exception)
        with TailRig() as rig:
            clock, _inputs, _expected = rig.input()
            def reenter():
                try:
                    clock.now()
                except Exception:
                    pass
            rig.clock.callback = reenter
            with self.assertRaisesRegex(Exception, "REENTRY"):
                clock.now()


class NewAuthorityControls(unittest.TestCase):
    def test_new_source12_acquisition24_http8_source12_and_known_return(self):
        with TailRig() as rig:
            result = rig.authority()
            clock, inputs, raw, _originals, _match, _captured = D._checked_tail_authority(result)
            self.assertEqual([len(query.queries) for query in rig.queries], [12, 24, 12])
            self.assertEqual(len(rig.requests), 8)
            self.assertEqual(len(rig.scopes), 1)
            self.assertTrue(rig.scopes[0].closed)
            self.assertEqual(rig.scopes[0].close_calls, 1)
            self.assertTrue(all(query.closed and query.close_calls == 1 for query in rig.queries))
            self.assertEqual(json.loads(raw)["edge"], "SEAL")
            self.assertEqual(clock.work, rig.collected["originalWindow"]["sealEndNs"])
            self.assertIs(result.input, inputs)
            self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)
            self.assertEqual(D._COLLECT_AUTHORITY_RETURNS, {})

    def test_new_authority_rehashed_split_short_caps_and_exact_close_end_refuse(self):
        for changed in ("split-cap", "shared-short-cap", "close-equal-end"):
            with self.subTest(changed=changed), TailRig() as rig:
                result = rig.authority()
                clock, _inputs, raw, _originals, _match, _captured = D._checked_tail_authority(result)
                first_ns, end_ns = clock.first, clock.work
                frame = rig.collected["originalWindow"]
                original = D._tail_authority_record(raw, frame, first_ns, end_ns)
                self.assertEqual(original["authority"]["workEndNs"], end_ns)
                self.assertEqual(original["authority"]["finalEndNs"], end_ns)
                value = json.loads(raw)
                if changed == "split-cap":
                    value["authority"]["workEndNs"] = end_ns - NS
                elif changed == "shared-short-cap":
                    value["authority"].update(workEndNs=end_ns - NS, finalEndNs=end_ns - NS)
                else:
                    value["closedNs"] = value["authority"]["closedNs"] = end_ns
                changed_raw = wire(value)
                self.assertNotEqual(sha(changed_raw), sha(raw))
                with self.assertRaisesRegex(Exception, "TAIL_AUTHORITY_RECORD_TIME"):
                    D._tail_authority_record(changed_raw, frame, first_ns, end_ns)
                # Re-encoding DATA neither replaces the actual registered
                # return nor grants authority to the changed record.
                self.assertEqual(D._checked_tail_authority(result)[2], raw)

    def test_separate_token_required_and_never_retained_in_seal_frame(self):
        with TailRig() as rig:
            with self.assertRaisesRegex(Exception, "TAIL_TOKEN"):
                D._tail_pre_metadata(rig.kind, rig.clock.cancelled)
            self.assertEqual(rig.queries, [])
        with TailRig() as rig:
            original = D._retain_tail_seal
            def retain(authority):
                frames, frame = [], sys._getframe(1)
                while frame is not None:
                    frames.append(frame)
                    frame = frame.f_back
                self.assertFalse(any(frame.f_code.co_name in ("_tail_pre_metadata", "_tail_authority") for frame in frames))
                self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)
                caller = next(frame for frame in frames if frame.f_code.co_name == "seal")
                self.assertNotIn("token", caller.f_locals)
                return original(authority)
            with patch.object(D, "_retain_tail_seal", retain):
                rig.guarded_seal()

    def test_wrong_job_source_policy_and_owner_do_not_become_new_authority(self):
        for changed in ("job", "owner", "source", "policy"):
            with self.subTest(changed=changed), TailRig() as rig:
                if changed in ("job", "owner"):
                    def http(name, body):
                        value = json.loads(body)
                        if name == "jobs" and changed == "job":
                            value["jobs"][0]["runner_id"] += 1
                        if name == "comment" and changed == "owner":
                            value["user"]["id"] += 1
                        return wire(value)
                    rig.http_hook = http
                else:
                    def query(supplier, index, raw):
                        if supplier.path.name == "source-after" and index == (1 if changed == "source" else 11):
                            return b" M source\n" if changed == "source" else raw + b" "
                        return raw
                    rig.query_hook = query
                with self.assertRaises(Exception):
                    rig.authority()
                self.assertEqual(D._TAIL_AUTHORITIES, {})

    def test_fixed_scope_context_and_command_do_not_accept_upload_or_old_collect(self):
        with TailRig() as rig:
            rig.authority()
            path = rig.custody / "authority-seal/context.json"
            context = json.loads(path.read_bytes())
            self.assertEqual(D.native.phase_command(wire(context))[5], "_tail-authority")
            for name, value in (("edge", "PRE_UPLOAD"), ("scope", D.native.INITIAL_COLLECT_AUTHORITY_CONTEXT_SCOPE),
                    ("session", str(rig.custody / "authority-2")), ("continuationEndNs", context["continuationEndNs"] + NS)):
                changed = {**context, name: value}
                with self.assertRaises(Exception):
                    D._tail_context(wire(changed), rig.clock.identity)

    def test_equal_authority_dictionary_or_native_phase_tuple_cannot_grant_seal(self):
        for changed in ("dictionary", "phase"):
            with self.subTest(changed=changed), TailRig() as rig:
                result = rig.authority()
                if changed == "dictionary":
                    object.__setattr__(result, "__dict__", dict(result.__dict__))
                else:
                    owner = D._TAIL_AUTHORITIES[id(result)][6]
                    object.__setattr__(owner.phase_originals, "records", tuple(list(owner.phase_originals.records)))
                with self.assertRaises(Exception):
                    D._retain_tail_seal(result)
                self.assertFalse((rig.custody / "seal").exists())

    def test_query_unknown_keeps_falsey_first_failure_and_no_retry(self):
        with TailRig() as rig:
            failure = M.FalseyFailure("SUPPLIED_TAIL_QUERY_CLOSE_UNKNOWN")
            rig.query_close_error = failure
            with self.assertRaises(Exception) as caught:
                rig.authority()
            self.assertIs(caught.exception, failure)
            self.assertEqual(len(rig.queries), 1)
            self.assertEqual(rig.queries[0].close_calls, 1)
            self.assertEqual(D._TAIL_AUTHORITIES, {})
            self.assertEqual(rig.scopes, [])

    def test_tail_phase_setup_failure_cannot_leave_an_active_or_enlarged_phase(self):
        with TailRig() as rig:
            failure = M.FalseyFailure("SUPPLIED_TAIL_PHASE_SETUP_FAILURE")
            def refused(_context_raw, _minimum=None):
                raise failure
            with patch.object(D.native, "phase_command", refused), self.assertRaises(Exception) as caught:
                rig.authority()
            self.assertIs(caught.exception, failure)
            self.assertEqual(D._TAIL_AUTHORITIES, {})
            self.assertEqual(rig.scopes, [])
            self.assertEqual(len(D._CUSTODY_OWNERS), 1)
            anchor = next(iter(D._CUSTODY_OWNERS.values()))
            self.assertIs(anchor.failure, failure)
            self.assertFalse(anchor.phase_active)
            self.assertIsNone(anchor.owner.work_limit)
            self.assertIsNone(anchor.owner.final_limit)
            self.assertTrue(anchor.owner.closed)

    def test_unknown_native_close_and_post_allocation_failure_never_issue_seal(self):
        for changed in ("close", "post-allocation"):
            with self.subTest(changed=changed), TailRig() as rig:
                failure = M.FalseyFailure("SUPPLIED_TAIL_NATIVE_" + changed)
                if changed == "close":
                    rig.scope_close_error = failure
                else:
                    original = rig.scope
                    def allocate(*args):
                        scope = original(*args)
                        def cancelled():
                            raise failure
                        rig.clock.callback = cancelled
                        return scope
                    rig.stack.enter_context(patch.object(D.native.processes, "make_scope", allocate))
                with self.assertRaises(Exception) as caught:
                    rig.authority()
                self.assertIs(caught.exception, failure)
                self.assertEqual(D._TAIL_AUTHORITIES, {})
                self.assertNotIn(D.O.wire.TOKEN_ENV, rig.env)
                self.assertEqual(rig.output.read_bytes(), b"")
                self.assertEqual(len(rig.scopes), 1)
                scope = rig.scopes[0]
                self.assertTrue(scope.drains)
                self.assertLessEqual(scope.drains[0][2], rig.original_local_end)
                if changed == "close":
                    self.assertEqual(scope.close_calls, 1)
                dispose_tail_unknown_captures(self, rig, scope, failure)

    def test_initial_root_replay_and_extra_returned_member_refuse(self):
        for changed in ("authority-seal", "seal", "returned-extra"):
            with self.subTest(changed=changed), TailRig() as rig:
                if changed == "returned-extra":
                    M.put(rig.custody / "returned" / "seal.json", b"NOT_AN_ORIGINAL")
                else:
                    (rig.custody / changed).mkdir(mode=0o700)
                with self.assertRaises(Exception):
                    rig.authority()
                self.assertEqual(rig.queries, [])


class SealAndOutputControls(unittest.TestCase):
    def test_gate_and_worker_seal_only_full_composition_and_real_guarded_outputs(self):
        for kind in ("gate", "worker"):
            with self.subTest(kind=kind), TailRig(kind) as rig:
                public = json.loads(rig.guarded_seal())
                raw = (rig.custody / "seal/seal-pending.json").read_bytes()
                value = json.loads(raw)
                self.assertEqual(rig.output.read_bytes(), ("initialSealSha256=" + sha(raw) + "\n").encode("ascii"))
                self.assertEqual(public["initialSealSha256"], sha(raw))
                self.assertEqual(value["output"]["artifact"], json.loads(rig.raws["manifest"])["artifact"])
                self.assertEqual(value["decryption"], "NOT_PERFORMED")
                self.assertEqual(value["upload"], "NOT_PERFORMED")
                self.assertFalse(value["cacheAuthority"])
                self.assertFalse(value["productiveAuthority"])
                self.assertEqual(value["writerReturn"], "PENDING_OWNER_CLOSE")
                self.assertEqual(value["originalStepOutcome"], "NOT_OBSERVED")
                self.assertEqual([saved[2]["checks"] for saved in D._TAIL_OUTPUTS.values()], [2])
                self.assertEqual((rig.custody / "export-output" / D.native.posix.ARTIFACT).read_bytes(), b"XYZ")
                self.assertEqual((rig.custody / "export-output" / D.native.posix.MANIFEST).read_bytes(), rig.raws["manifest"])

    def test_output_pin_is_new_tail_observation_not_phantom_posix_history(self):
        with TailRig() as rig:
            self.assertIsNone(json.loads(rig.raws["context"])["directories"]["export-output"])
            result = rig.closed()
            value = json.loads(result.raw)
            self.assertEqual(value["output"]["scope"], "THIS_SEAL_FILE_OBSERVATION_NOT_HISTORICAL_POSIX_OUTPUT_PIN")
            before = D._TAIL_INPUTS[id(result.authority.input)][6][2][2]
            self.assertEqual(value["output"]["directoryIdentity"], list(before))
            self.assertNotIn("historicalOutputIdentity", value)

    def test_ciphertext_size_hash_extra_member_and_symlink_refuse(self):
        for changed in ("size", "hash", "extra", "symlink"):
            with self.subTest(changed=changed), TailRig() as rig:
                result = rig.authority()
                artifact = rig.custody / "export-output" / D.native.posix.ARTIFACT
                if changed in ("size", "hash"):
                    artifact.write_bytes(b"XY" if changed == "size" else b"XYQ")
                elif changed == "extra":
                    M.put(artifact.parent / "plaintext.txt", b"FORBIDDEN_EXTRA")
                else:
                    destination = rig.base / "external"
                    artifact.rename(destination)
                    artifact.symlink_to(destination)
                with self.assertRaises(Exception):
                    D._retain_tail_seal(result)
                self.assertEqual(rig.output.read_bytes(), b"")

    def test_input_output_directory_replacement_between_fresh_owners_refuses(self):
        with TailRig() as rig:
            authority = rig.authority()
            output = rig.custody / "export-output"
            output.rename(rig.base / "old-output")
            output.mkdir(mode=0o700)
            M.put(output / D.native.posix.MANIFEST, rig.raws["manifest"])
            M.put(output / D.native.posix.ARTIFACT, b"XYZ")
            with self.assertRaisesRegex(Exception, "INPUT_DIRECTORY_PINS"):
                D._retain_tail_seal(authority)

    def test_seal_files_cannot_attest_their_own_close_or_mint_registered_result(self):
        with TailRig() as rig:
            result = rig.closed()
            duplicate = D._TailSeal(result.authority, result.raw, result.metadata_close)
            with self.assertRaises(Exception):
                D._TailOutputFence(duplicate)
            metadata = D._TAIL_SEALS[id(result)][8]
            self.assertTrue(metadata.finished)
            self.assertTrue(metadata.owner.closed)
            self.assertTrue(all(a and c for _row, _label, _resource, a, c in metadata.rows))
            self.assertEqual(rig.output.read_bytes(), b"")

    def test_writer_and_close_errors_cannot_issue_seal_digest(self):
        for changed in ("write", "close"):
            with self.subTest(changed=changed), TailRig() as rig:
                authority = rig.authority()
                failure = M.FalseyFailure("SUPPLIED_SEAL_" + changed)
                original = D._tail_write if changed == "write" else D._PrimaryOwner.finish
                def rejected(*args):
                    if changed == "write":
                        raise failure
                    value = original(*args)
                    raise failure  # Actual tiny resources closed; ambiguous return remains FAILURE.
                target = D if changed == "write" else D._PrimaryOwner
                name = "_tail_write" if changed == "write" else "finish"
                with patch.object(target, name, rejected), self.assertRaises(Exception) as caught:
                    D._retain_tail_seal(authority)
                self.assertIs(caught.exception, failure)
                self.assertEqual(rig.output.read_bytes(), b"")
                self.assertEqual(D._TAIL_SEALS, {})

    def test_one_output_append_only_and_two_late_checks_only(self):
        with TailRig() as rig:
            result = rig.closed()
            fence = D._TailOutputFence(result)
            value, actual, limit = fence.append()
            self.assertIs(actual, fence)
            self.assertEqual(set(value) - {"schema", "scope", "testAcceptance", "exportSaveAuthority"}, {"initialSealSha256"})
            fence.now(final=True, limit=limit)
            fence.now(final=True, limit=limit)
            with self.assertRaisesRegex(Exception, "EXACT_LATE_CHECK"):
                fence.now(final=True, limit=limit)
            with self.assertRaises(Exception):
                D._TailOutputFence(result)
            with self.assertRaises(Exception):
                fence.append()

    def test_output_early_wrong_limit_equal_binding_or_expiry_cannot_recover(self):
        for changed in ("early", "limit", "binding", "expiry"):
            with self.subTest(changed=changed), TailRig() as rig:
                result = rig.closed()
                fence = D._TailOutputFence(result)
                limit = D._TAIL_SEALS[id(result)][7].work
                if changed != "early":
                    fence.append()
                original = fence._binding
                original_raw = rig.clock.raw
                if changed == "binding":
                    fence._binding = tuple(list(original))
                if changed == "expiry":
                    rig.clock.raw = limit
                with self.assertRaises(Exception) as first:
                    fence.now(final=True, limit=limit + (1 if changed == "limit" else 0))
                fence._binding = original
                rig.clock.raw = original_raw
                with self.assertRaises(Exception) as second:
                    fence.now(final=True, limit=limit)
                self.assertIs(first.exception, second.exception)

    def test_partial_append_fsync_readback_or_ambiguous_close_never_success(self):
        for changed in ("write", "fsync", "read", "close"):
            with self.subTest(changed=changed), TailRig() as rig:
                result = rig.closed()
                fence = D._TailOutputFence(result)
                failure = M.FalseyFailure("SUPPLIED_SEAL_OUTPUT_" + changed)
                original = getattr(D.C.os, changed)
                if changed == "write":
                    replacement = lambda descriptor, raw: original(descriptor, raw[:-1])
                elif changed == "read":
                    replacement = lambda descriptor, count: original(descriptor, count) + b"X"
                elif changed == "close":
                    def replacement(descriptor):
                        original(descriptor)
                        raise failure
                else:
                    def replacement(_descriptor):
                        raise failure
                with patch.object(D.C.os, changed, replacement), self.assertRaises(Exception):
                    fence.append()
                self.assertEqual(fence._original()[2]["checks"], 0)
                with self.assertRaises(Exception):
                    fence.now(final=True, limit=fence._binding[4])

    def test_second_late_currency_callback_cannot_replace_seal_dictionary(self):
        with TailRig() as rig:
            result = rig.closed()
            fence = D._TailOutputFence(result)
            _value, _fence, limit = fence.append()
            fence.now(final=True, limit=limit)
            original = D._tail_authority_currency
            def changed(authority):
                value = original(authority)
                object.__setattr__(result, "__dict__", dict(result.__dict__))
                return value
            with patch.object(D, "_tail_authority_currency", changed), self.assertRaises(Exception):
                fence.now(final=True, limit=limit)

    def test_cancellation_after_partial_output_still_fails_original_guard(self):
        with TailRig() as rig:
            result = rig.closed()
            fence = D._TailOutputFence(result)
            _value, _fence, limit = fence.append()
            failure = M.FalseyFailure("SUPPLIED_SEAL_LATE_CANCEL")
            def cancel():
                raise failure
            rig.clock.callback = cancel
            with self.assertRaises(Exception) as caught:
                fence.now(final=True, limit=limit)
            self.assertIs(caught.exception, failure)
            self.assertNotEqual(rig.output.read_bytes(), b"")
            self.assertEqual(fence._original()[2]["phase"], "OUTPUT")

    def test_output_whitelist_does_not_admit_future_upload_or_paths(self):
        with TailRig():
            for values in ({"initialUploadWindowSha256": "0" * 64}, {"initialSealSha256": "path/private"},
                    {"initialSealSha256": "0" * 64, "initialExporterReturnSha256": "1" * 64}):
                with self.assertRaises(Exception):
                    D.C.append_outputs(values, lambda: None)


if __name__ == "__main__":
    unittest.main()
