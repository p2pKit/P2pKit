#!/usr/bin/env python3
"""New bounded offline seam controls, never genuine native/hosted acceptance.

Model clocks, byte streams, owners, Git rows and comments below are synthetic.
An audit guard refuses processes, native loading and networking. No native
entry, download, key, product, existing test method or earlier suite is run.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import copy
import ctypes  # Stdlib initialization only, before the native-loader guard.
from email.utils import formatdate
import importlib.util
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


M = load("initial_ordinary_native_control_subject", ROOT / "scripts/run-hosted-initial-ordinary.py")
O, I, S, A = M.origin, M.I, M.S, M.acquisition
F = load("initial_ordinary_native_stage_fixture", Path(__file__).with_name("hosted-initial-recipient-stages-test.py"))
MODELS = load("initial_ordinary_native_original_fixture", Path(__file__).with_name("hosted-initial-ordinary-originals-test.py"))
COMPAT = load("initial_ordinary_native_compatibility_fixture", Path(__file__).with_name("hosted-cache-compatibility-test.py"))
NS, FIRST = O.NS, 1000 * O.NS


@contextmanager
def references_fixture():
    # Existing SETUP/builders only. No test_* method or inherited suite runs.
    builder = MODELS.OriginalModels(methodName="runTest")
    try:
        builder.setUp()
        yield builder
    finally:
        builder.doCleanups()


def query_fixture():
    declaration, _histories = F.stage2(F.stage1())
    source = {"source": declaration["firstPullRequest"]["merge"], "reviewed": declaration["reviewed"],
        "mergeParents": [S.BASE["commit"], F.H2]}
    originals = {"source_binding": I.encoded(source), "observation": I.encoded(F.observation2(declaration)),
        "candidate_policy_entry": F.ENTRY, "candidate_policy_raw": F.POLICY, "base_policy_entry": b"",
        "ancestry_raw": S.BASE["commit"].encode("ascii") + b"\n", "prior_ancestry_raw": F.H1.encode("ascii") + b"\n"}
    commands = (
        ("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
        ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--is-shallow-repository"),
        ("rev-parse", "--verify", F.MERGE + "^{tree}"), ("rev-parse", "--verify", F.H2 + "^{tree}"),
        ("show", "-s", "--format=%P", F.MERGE), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
        ("rev-parse", "--verify", S.BASE["commit"] + "^{tree}"),
        ("ls-tree", "-z", S.BASE["commit"], "--", I.POLICY_PATH),
        ("merge-base", S.BASE["commit"], F.H2), ("ls-tree", "-z", F.H2, "--", I.POLICY_PATH),
        ("cat-file", "-s", F.BLOB), ("cat-file", "blob", F.BLOB),
        ("rev-parse", "--verify", F.H1 + "^{tree}"), ("merge-base", F.H1, F.H2),
    )
    raw = (str(ROOT).encode("utf-8") + b"\n", b"", F.MERGE.encode("ascii") + b"\n", b"false\n",
        F.T2.encode("ascii") + b"\n", F.T2.encode("ascii") + b"\n",
        (S.BASE["commit"] + " " + F.H2).encode("ascii") + b"\n", S.BASE["commit"].encode("ascii") + b"\n",
        S.BASE["tree"].encode("ascii") + b"\n", b"", originals["ancestry_raw"], F.ENTRY,
        str(len(F.POLICY)).encode("ascii") + b"\n", F.POLICY, F.T1.encode("ascii") + b"\n", originals["prior_ancestry_raw"])
    rows = [{"argv": ["/model/git", "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false", "-C", str(ROOT), *args],
        "stdoutLimit": I.EVENT_LIMIT if index == 1 else I.POLICY_LIMIT if index == 13 else 4096}
        for index, args in enumerate(commands)]
    return rows + copy.deepcopy(rows), list(raw + raw), originals, {"reviewedCommit": F.H2, "sourceCommit": F.MERGE}, declaration


def native_query_fixture():
    path = Path("/model/query")
    owner = {"job": "a" * 32, "state": str(path), "home": str(path / "query-home"), "git": "/model/git",
        "nativeRole": "linux-x64"}
    argv = [owner["git"], "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false", "-C", str(ROOT),
        "rev-parse", "--show-toplevel"]
    row = {"schema": 1, "scope": "NATIVE_OWNED_ORDINARY_GIT_QUERY", "id": "b" * 32, **{name: owner[name] for name in
        ("job", "state", "home")}, "cwd": str(ROOT), "argv": argv, "stdoutLimit": 4096, "stderrLimit": 4096,
        "timeoutSeconds": 15, "launchAttempted": True, "scopeAttempted": True, "waitExitCode": 0,
        "retirement": "KNOWN", "result": "READY_FOR_CALLER_SEAL", "errors": [], "outputs": {}, "ownedSurvivors": [],
        "ownership": {"backend": "linux-proc-pidfd", "job": owner["job"], "invocation": "b" * 32,
            "discoveryErrors": [], "scope": "controlled-marker-inheriting-descendants", "discoveryReconciliations": [],
            "startedIdentities": [{"pid": 12345, "startTicks": 200}], "launches": [{"pid": 12345, "created": True,
                "requestedArgv": argv, "resolvedArgv": argv, "cwd": str(ROOT), "api": "subprocess.Popen", "shell": False,
                "executable": argv[0], "outputMode": "caller-owned-files"}]}}
    start = {name: copy.deepcopy(value) for name, value in row.items() if name not in ("ownedSurvivors", "ownership")}
    start.update(launchAttempted=False, scopeAttempted=False, waitExitCode=None, retirement="UNKNOWN", result="HOLD")
    start["environment"] = M.processes.ownership_environment(M.queries._git_environment(), row["job"], row["id"],
        row["state"], row["home"], allow_new_context=True)
    baseline = {"nativeRole": "linux-x64", "kernelJob": False, "baseline": [[11111, 100]]}
    return row, start, baseline, owner


def archive_header_fixture(status=302, count=0, **changes):
    fields = {"content-length": str(count), "date": formatdate(F.START, usegmt=True)}
    if status == 302:
        fields.update({"location": "https://unit.blob.core.windows.net/packet?sig=SYNTHETIC",
            "x-github-api-version-selected": "2022-11-28", "x-github-request-id": "SYNTHETIC-0001"})
    fields.update(changes)
    return ("HTTP/1.1 " + str(status) + " SYNTHETIC\r\n" + "".join(name + ": " + value + "\r\n"
        for name, value in fields.items()) + "\r\n").encode("ascii")


def packet_interval_fixture():
    clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
    window = M._window(O.clocks.Reading(clock, FIRST), FIRST + 75 * NS, FIRST + 120 * NS)
    packet = {"artifactId": 1001, "bytes": 1024, "sha256": "c" * 64}
    interval = {"schema": 1, "scope": "INITIAL_ORDINARY_ORIGINAL_PACKET_ACQUISITION_V1",
        "invocation": "d" * 32, "clock": window["clock"], "firstNs": FIRST + NS, "workEndNs": FIRST + 46 * NS,
        "completedNs": FIRST + 40 * NS, "packet": packet, "source": {"commit": F.H1, "tree": F.T1},
        "selection": "desktop-linux-x64", "archive": "ORIGINAL_DOWNLOAD"}
    return interval, packet, "d" * 32, window


class NativeSeamControls(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack(); self.addCleanup(self.stack.close)
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        self.raw, self.local = FIRST + 1, 1000.0
        self.stack.enter_context(patch.object(O.clocks, "checked_now", side_effect=self.now))
        self.stack.enter_context(patch.object(M.time, "monotonic", side_effect=lambda: self.local))
        self.stack.enter_context(patch.object(O.clocks, "observe", side_effect=AssertionError("NATIVE_CLOCK_FORBIDDEN")))
        self.stack.enter_context(patch.object(M.processes, "make_scope", side_effect=AssertionError("NATIVE_SCOPE_FORBIDDEN")))
        self.stack.enter_context(patch.object(M.files, "private_root", side_effect=AssertionError("NATIVE_FILES_FORBIDDEN")))
        self.stack.enter_context(patch.object(M.files, "public_root", side_effect=AssertionError("NATIVE_FILES_FORBIDDEN")))
        self.stack.enter_context(patch.object(M, "_launch", side_effect=AssertionError("NATIVE_LAUNCH_FORBIDDEN")))
        self.stack.enter_context(patch.object(O, "_request", side_effect=AssertionError("HTTP_FORBIDDEN")))
        self.addCleanup(M._QUARANTINE.clear)

    def now(self, clock, *, minimum_ns):
        self.assertEqual(clock, self.clock)
        if self.raw < minimum_ns:
            raise O.clocks.ClockError("SYNTHETIC_REVERSED_CLOCK")
        self.raw += 1
        return self.raw

    def fence(self, cancelled=lambda: None):
        first = O.clocks.Reading(self.clock, FIRST)
        value = M._window(first, FIRST + 75 * NS, FIRST + 120 * NS)
        return M._Fence(value, first, self.local, cancelled)

    def test_window_is_separate_unadmitted_and_cannot_widen_original_source_caps(self):
        first = O.clocks.Reading(self.clock, FIRST)
        value = M._window(first, FIRST + 60 * NS, FIRST + 90 * NS)
        self.assertEqual((value["budgetAcceptance"], value["ordinaryAcceptance"]), ("NOT_ADMITTED", "NOT_PERFORMED"))
        for work, final in ((FIRST, FIRST + NS), (FIRST + 76 * NS, FIRST + 120 * NS),
                (FIRST + 75 * NS, FIRST + 121 * NS), (FIRST + 70 * NS, FIRST + 60 * NS), (True, FIRST + NS)):
            with self.assertRaises((I.AdmissionError, O.OriginError)): M._window(first, work, final)

    def test_raw_local_and_cancellation_fences_are_distinct_and_final_never_renews(self):
        fence = self.fence()
        self.assertLess(fence.deadline(10000), 1075.001)
        self.raw = FIRST + 75 * NS
        with self.assertRaisesRegex(I.AdmissionError, "EXPIRED"): fence.now()
        self.raw = FIRST + 1; self.local = 1121.0
        with self.assertRaisesRegex(I.AdmissionError, "EXPIRED"): fence.now(final=True)
        self.local = 1000.0
        original = KeyboardInterrupt("SYNTHETIC_CANCEL")
        def cancelled(): raise original
        fence = self.fence(cancelled)
        with self.assertRaises(KeyboardInterrupt) as caught: fence.now()
        self.assertIs(caught.exception, original)
        fence.now(final=True)  # Cleanup only; does not make cancelled work pass.

    def test_model_file_owner_closes_original_resources_once_and_binds_its_return(self):
        owner = M._Owner(M._OWNER_KEY, self.fence())
        resource = SimpleNamespace(calls=0)
        def close(): resource.calls += 1
        resource.close = close
        owner.acquire("MODEL_NO_FILE", lambda: resource)
        returned = owner.close()
        self.assertIs(M._checked_close(returned), owner)
        self.assertEqual(resource.calls, 1)
        with self.assertRaises(I.AdmissionError): owner.close()
        with self.assertRaises(I.AdmissionError): M._checked_close(M._ClosedOwner(returned.raw))

    def test_original_close_failure_quarantines_and_never_retries_or_returns_success(self):
        owner = M._Owner(M._OWNER_KEY, self.fence())
        original = RuntimeError("SYNTHETIC_CLOSE_UNKNOWN")
        calls = []
        def close(): calls.append(True); raise original
        owner.acquire("MODEL_NO_FILE", lambda: SimpleNamespace(close=close))
        with self.assertRaises(RuntimeError) as caught: owner.close()
        self.assertIs(caught.exception, original)
        self.assertEqual(calls, [True])
        self.assertTrue(owner.unknown)
        self.assertIn(owner, M._QUARANTINE)

    def test_nested_source_reads_charge_each_actual_pass_and_keep_original_owner_close(self):
        tree, owner = COMPAT.ModelTree(), M._Owner(M._OWNER_KEY, self.fence())
        with patch.object(M.files, "PosixFile", COMPAT.ModelFile), \
                patch.object(M.files, "PosixSourceDirectory", COMPAT.ModelDirectory), \
                patch.object(M.files, "public_root", side_effect=lambda _root: COMPAT.ModelDirectory(tree, ())):
            first = M._source_inputs(owner)
            self.assertEqual(M._source_inputs(owner), first)
        self.assertEqual(owner.control_bytes, 2 * sum(len(raw) for raw in tree.raw.values()))
        self.assertEqual([row[0] for row in owner.resources], list(M.compatibility.source_read_labels()) * 2)
        self.assertEqual(len(owner.resources), 298)
        self.assertTrue(all(row[3] and row[1].close_calls == 1 for row in owner.resources))
        self.assertIs(M._checked_close(owner.close()), owner)
        self.assertEqual((M.CONTROL_LIMIT, M.FILE_COUNT, M.SOURCE_SECONDS, M.FINAL_SECONDS),
            (64 * 1024 * 1024, 1024, 75, 120))

    def test_source_quota_exhaustion_keeps_adopted_file_and_original_failure(self):
        tree, owner = COMPAT.ModelTree(), M._Owner(M._OWNER_KEY, self.fence())
        owner.control_bytes = M.CONTROL_LIMIT - 1  # Explicit pre-consumed model ledger.
        resource = COMPAT.ModelFile(tree, M.compatibility.PROVIDER_INPUTS[0])
        with patch.object(M.files, "PosixFile", COMPAT.ModelFile), \
                self.assertRaisesRegex(I.AdmissionError, "CONTROL_BYTES") as caught:
            owner.acquire("dependency-seed-input", lambda: resource)
        self.assertEqual(tree.reads, [])
        self.assertEqual(len(owner.resources), 1)
        self.assertFalse(owner.unknown or owner.resources[0][2])
        with self.assertRaises(I.AdmissionError) as closed: owner.close()
        self.assertIs(closed.exception, caught.exception)
        self.assertTrue(owner.resources[0][3])
        self.assertEqual(resource.close_calls, 1)

    def test_source_size_refusal_is_after_retention_before_read_and_cannot_fake_type(self):
        for malformed in ("oversize", "directory", "untyped"):
            tree, owner = COMPAT.ModelTree(), M._Owner(M._OWNER_KEY, self.fence())
            name = M.compatibility.PROVIDER_INPUTS[0]
            tree.sizes[name] = M.files.authority.MAX_XML_BYTES + 1 if malformed == "oversize" else 1
            resource = COMPAT.ModelFile(tree, name)
            if malformed == "directory":
                resource.initial_info = COMPAT.replace(resource.initial_info, is_directory=True)
            if malformed == "untyped":
                resource = SimpleNamespace(initial_info=resource.initial_info, close=lambda: None)
            with patch.object(M.files, "PosixFile", COMPAT.ModelFile), self.assertRaises(I.AdmissionError):
                owner.acquire("dependency-seed-input", lambda: resource)
            self.assertIs(owner.resources[0][1], resource)
            self.assertEqual((owner.control_bytes, tree.reads), (0, []))
            with self.assertRaises(I.AdmissionError): owner.close()
            self.assertTrue(owner.resources[0][3])

    def test_source_post_adoption_deadline_keeps_charge_and_never_refunds_or_retries(self):
        tree, owner = COMPAT.ModelTree(), M._Owner(M._OWNER_KEY, self.fence())
        resource = COMPAT.ModelFile(tree, M.compatibility.PROVIDER_INPUTS[0])
        def observed():
            self.raw = FIRST + 75 * NS
            return resource.initial_info
        resource.verify = observed
        with patch.object(M.files, "PosixFile", COMPAT.ModelFile), self.assertRaisesRegex(I.AdmissionError, "EXPIRED"):
            owner.acquire("dependency-seed-input", lambda: resource)
        self.assertEqual(owner.control_bytes, resource.initial_info.size)
        self.assertEqual(tree.reads, [])
        with self.assertRaises(I.AdmissionError): owner.close()
        self.assertTrue(owner.resources[0][3])
        self.assertEqual(resource.close_calls, 1)

    def test_supplied_data_cannot_construct_native_current_or_close_authority(self):
        for supplied in (M.InitialOrdinaryCurrent(), {}, b"{}", SimpleNamespace(record=b"{}")):
            with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_CURRENT_RETURN_REQUIRED"):
                M.checked_initial_ordinary(supplied)
        forged = M._NativeReturn(object(), object(), b"{}", b"{}", b"{}", b"{}", b"")
        with self.assertRaisesRegex(I.AdmissionError, "ORIGINAL_NATIVE_RETURN"): M._checked_native(forged, object())

    def test_single_owner_token_only_enters_fixed_child_not_argv_or_git_environment(self):
        token = "SYNTHETIC_TEST_TOKEN_NOT_A_CREDENTIAL"
        with patch.dict(os.environ, {"PATH": "/ambient/must/not/be/inherited", "HTTP_PROXY": "SYNTHETIC_FORBIDDEN"}, clear=True), \
                patch.object(M, "_installed_git", return_value="/model/git"):
            value = M._child_environment(Path("/model/private"), "a" * 32, "b" * 32, token, "/model/git")
            self.assertEqual(value["PATH"], "/model")
            self.assertEqual(value[O.wire.TOKEN_ENV], token)
            self.assertNotIn("HTTP_PROXY", value)
            self.assertNotIn(O.wire.TOKEN_ENV, M.queries._git_environment())
            self.assertNotIn(O.wire.TOKEN_ENV, os.environ)
            window = I.parse(self.fence().raw, M.SMALL_LIMIT)
            command = M._command("gate", "b" * 32, "c" * 64, FIRST + 1, window, "d" * 64)
            self.assertNotIn(token, command)
            self.assertEqual(command[1:4], ["-I", "-B", "-S"])

    def test_ambient_credentials_and_execution_overrides_fail_before_launch(self):
        for key in (*M.FORBIDDEN_SECRETS, O.wire.TOKEN_ENV, "PYTHONPATH", "LD_PRELOAD"):
            with self.subTest(key=key), patch.dict(os.environ, {key: "SYNTHETIC"}, clear=True), \
                    patch.object(M, "_installed_git", return_value="/model/git"), self.assertRaises(I.AdmissionError):
                M._child_environment(Path("/model/private"), "a" * 32, "b" * 32,
                    "SYNTHETIC_TEST_TOKEN_NOT_A_CREDENTIAL", "/model/git")

    def test_only_original_github_blob_https_locations_are_accepted(self):
        self.assertEqual(M._storage_location("https://unit.blob.core.windows.net/packet?sig=SYNTHETIC"),
            ("unit.blob.core.windows.net", "/packet?sig=SYNTHETIC"))
        for value in ("http://unit.blob.core.windows.net/packet", "https://api.github.com/packet",
            "https://unit.blob.core.windows.net.evil.invalid/packet", "https://u:p@unit.blob.core.windows.net/packet",
            "https://unit.blob.core.windows.net:444/packet", "https://unit.blob.core.windows.net/packet#fragment",
            "https://unit.blob.core.windows.net/packet\n", "https://unit.blob.core.windows.net\\evil/packet"):
            with self.subTest(value=value), self.assertRaises(I.AdmissionError): M._storage_location(value)

    def test_paginated_links_match_complete_fixed_paths_but_never_select_an_endpoint(self):
        path = lambda number: M.qualification.references.inventory_path("301", number)
        link = lambda number, relation: '<' + O.wire.ORIGIN + path(number) + '>; rel="' + relation + '"'
        M._page_links({"link": link(2, "next") + ", " + link(2, "last")}, 1, 101, path)
        M._page_links({"link": link(1, "prev") + ", " + link(1, "first")}, 2, 101, path)
        M._page_links({}, 1, 0, path)
        for headers, page in (({}, 1), ({"link": link(2, "next")}, 2),
            ({"link": link(2, "next") + ", " + link(2, "next")}, 1),
            ({"link": link(2, "next").replace("api.github.com", "example.invalid")}, 1),
            ({"link": link(2, "next").replace("per_page=100", "per_page=50")}, 1)):
            with self.assertRaises(I.AdmissionError): M._page_links(headers, page, 101, path)

    def test_binary_reader_keeps_bounded_reads_and_original_close_error(self):
        class Sock:
            def settimeout(self, value): self.timeout = value
        sock = Sock(); fence = self.fence()
        reader = M._ArchiveReader(io.BytesIO(b"HTTP/1.1 200 OK\r\n\r\nabc"), sock, fence, FIRST + 10 * NS, 3)
        self.assertEqual(reader.readline(), b"HTTP/1.1 200 OK\r\n")
        self.assertEqual(reader.readline(), b"\r\n")
        reader.in_headers = False
        self.assertEqual(reader.read(3), b"abc")
        self.assertLessEqual(sock.timeout, 5)
        with self.assertRaises(I.AdmissionError): reader.read(65537)
        reader.close(); reader.close()
        calls, original = [], RuntimeError("SYNTHETIC_STREAM_CLOSE_UNKNOWN")
        def fail(): calls.append(True); raise original
        failed = M._ArchiveReader(SimpleNamespace(close=fail), sock, fence, FIRST + 10 * NS, 3)
        for _ in range(2):
            with self.assertRaises(RuntimeError) as caught: failed.close()
            self.assertIs(caught.exception, original)
        self.assertEqual(calls, [True])

    def test_live_and_retained_archive_headers_have_one_exact_original_grammar(self):
        fields, date = M._archive_headers(archive_header_fixture(), 302, 0)
        self.assertEqual(date, F.START)
        self.assertEqual(M._storage_location(fields["location"])[0], "unit.blob.core.windows.net")
        M._archive_headers(archive_header_fixture(200, 33), 200, 33)
        for changes in ({"content-length": "01"}, {"content-range": "bytes 0-32/33"},
                {"transfer-encoding": "chunked"}, {"content-encoding": "gzip"}, {"age": "1"},
                {"via": "SYNTHETIC"}, {"x-github-api-version-selected": "wrong"},
                {"location": "https://example.invalid/packet"}):
            with self.subTest(changes=changes), self.assertRaises(I.AdmissionError):
                M._archive_headers(archive_header_fixture(**changes), 302, 0)
        with self.assertRaisesRegex(I.AdmissionError, "SECOND_REDIRECT"):
            M._archive_headers(archive_header_fixture(200, 33, location="https://unit.blob.core.windows.net/again"), 200, 33)

    def test_original_packet_interval_cannot_renew_forty_five_or_change_packet_clock(self):
        value, packet, invocation, window = packet_interval_fixture()
        self.assertEqual(M._packet_interval(I.encoded(value), packet, invocation, window), value)
        for change in (lambda row: row.update(workEndNs=row["workEndNs"] + 1),
            lambda row: row.update(completedNs=row["workEndNs"]), lambda row: row.update(invocation="e" * 32),
            lambda row: row["packet"].update(artifactId=1002), lambda row: row["clock"].update(role="windows-x64")):
            changed = copy.deepcopy(value); change(changed)
            with self.assertRaises(I.AdmissionError): M._packet_interval(I.encoded(changed), packet, invocation, window)

    def test_packet_original_responses_keep_order_complete_interval_and_service_dates(self):
        value, _packet, _invocation, _window = packet_interval_fixture()
        first = {"startedNs": FIRST + 2 * NS, "finishedNs": FIRST + 3 * NS}
        later = {"startedNs": FIRST + 4 * NS, "finishedNs": FIRST + 5 * NS}
        audit = M._PacketAudit(value)
        audit.accept(first, F.START); audit.accept(later, F.START + 2)
        for response, date in ((first, F.START), (later, F.START - 1),
            ({"startedNs": FIRST + 41 * NS, "finishedNs": FIRST + 42 * NS}, F.START + 40),
            (later, F.START + O.wire.CACHE_SECONDS + 10)):
            audit = M._PacketAudit(value); audit.accept(first, F.START)
            with self.assertRaises(I.AdmissionError): audit.accept(response, date)

    def test_complete_two_source_query_sequences_bind_h1_h2_merge_and_policy(self):
        M._query_source_sequence(*query_fixture())

    def test_query_sequence_rejects_dropped_reordered_or_substituted_outputs(self):
        for change in (lambda rows, raws: rows.pop(), lambda rows, raws: raws.__setitem__(8, b"0" * 40 + b"\n"),
            lambda rows, raws: rows.reverse(), lambda rows, raws: raws.__setitem__(9, b"POLICY_ALREADY_PRESENT"),
            lambda rows, raws: raws.__setitem__(19, b"true\n")):
            rows, raws, originals, context, declaration = query_fixture(); change(rows, raws)
            with self.assertRaises(I.AdmissionError): M._query_source_sequence(rows, raws, originals, context, declaration)

    def test_query_native_records_bind_original_start_environment_lifetime_and_baseline(self):
        with patch.dict(os.environ, {}, clear=True):
            row, start, baseline, owner = native_query_fixture()
            M._query_native_record(row, I.encoded(start), I.encoded(baseline), owner, {})
            changed = copy.deepcopy(start); changed["environment"]["SYNTHETIC_TOKEN"] = "NOT_A_REAL_SECRET"
            with self.assertRaisesRegex(I.AdmissionError, "CREDENTIAL_OR_DOMAIN"):
                M._query_native_record(row, I.encoded(changed), I.encoded(baseline), owner, {})
            baseline["baseline"].append([12345, 200])
            with self.assertRaisesRegex(I.AdmissionError, "LIFETIME"):
                M._query_native_record(row, I.encoded(start), I.encoded(baseline), owner, {})

    def test_query_native_return_cannot_change_command_scope_or_claim_success_before_launch(self):
        with patch.dict(os.environ, {}, clear=True):
            for mutate in (lambda row: row["ownership"]["launches"][0].update(created=False),
                lambda row: row["ownership"].update(invocation="c" * 32),
                lambda row: row.update(launchAttempted=False), lambda row: row.update(timeoutSeconds=60)):
                row, start, baseline, owner = native_query_fixture(); mutate(row)
                with self.assertRaises(I.AdmissionError): M._query_native_record(row, I.encoded(start), I.encoded(baseline), owner, {})

    def test_naturally_short_posix_leader_is_not_an_invented_observed_lifetime(self):
        with patch.dict(os.environ, {}, clear=True):
            row, start, baseline, owner = native_query_fixture()
            row["ownership"]["startedIdentities"] = []
            M._query_native_record(row, I.encoded(start), I.encoded(baseline), owner, {})
            self.assertEqual(row["ownership"]["startedIdentities"], [])
            for mutate in (lambda value: value.update(waitExitCode=None),
                lambda value: value.update(ownedSurvivors=[{"pid": 12345}]),
                lambda value: value.update(retirement="UNKNOWN"),
                lambda value: value["ownership"]["launches"][0].update(created=False),
                lambda value: value["ownership"].update(discoveryErrors=["SYNTHETIC_UNKNOWN"])):
                changed = copy.deepcopy(row); mutate(changed)
                with self.assertRaises(I.AdmissionError):
                    M._query_native_record(changed, I.encoded(start), I.encoded(baseline), owner, {})

    def test_windows_still_requires_original_pre_resume_lifetime_identity(self):
        with patch.dict(os.environ, {}, clear=True):
            row, start, baseline, owner = native_query_fixture()
            owner["nativeRole"] = "windows-x64"
            baseline.update(nativeRole="windows-x64", baseline=None, kernelJob=True)
            row["ownership"].update(backend=M.processes.WindowsScope.name,
                scope="kernel-job-no-breakaway-kill-on-close", startedIdentities=[])
            with self.assertRaisesRegex(I.AdmissionError, "QUERY_NATIVE_LEADER"):
                M._query_native_record(row, I.encoded(start), I.encoded(baseline), owner, {})

    def test_current_claim_is_one_shot_and_wrong_role_poisoning_is_sticky(self):
        current = M.InitialOrdinaryCurrent()
        state = SimpleNamespace(context_raw=I.encoded({"observed": {"kind": "worker"}}),
            lineage={"claims": {}, "failed": False})
        with patch.object(M, "checked_initial_ordinary", return_value=current), patch.object(M, "_history", return_value=state):
            self.assertIs(M.claim_initial_ordinary(current, "provider"), current)
            with self.assertRaisesRegex(I.AdmissionError, "USE_ONCE"): M.claim_initial_ordinary(current, "seed")
            self.assertTrue(state.lineage["failed"])
            state.lineage = {"claims": {}, "failed": False}
            with self.assertRaisesRegex(I.AdmissionError, "GATE_CANNOT"): M.claim_initial_ordinary(current, "gate")
            self.assertTrue(state.lineage["failed"])


class CurrentReferenceControls(unittest.TestCase):
    def test_first_current_pass_selects_references_without_creating_history_or_admission(self):
        with references_fixture() as model:
            result, originals = model.acquire(histories=(), expected=None, current_references=True)
            self.assertIs(type(result), A.CurrentReferences)
            self.assertEqual(len(model.requests), 9)
            self.assertEqual(set(dict(originals)), set(M.CURRENT_KEYS))
            record = I.parse(result.record, M.SMALL_LIMIT)
            self.assertEqual(record["scope"], "INITIAL_ORDINARY_CURRENT_REFERENCES_ONLY_V1")
            self.assertEqual(record["qualificationAcceptance"], "NOT_ESTABLISHED")
            self.assertNotIsInstance(result, I.Admission)

    def test_first_pass_cannot_accept_arbitrary_histories_or_an_expected_ordinary_result(self):
        with references_fixture() as model:
            with self.assertRaisesRegex(I.AdmissionError, "OWNER_CALLBACKS_OR_HISTORY"):
                model.acquire(current_references=True)
            with self.assertRaisesRegex(I.AdmissionError, "OWNER_CALLBACKS_OR_HISTORY"):
                model.acquire(histories=(), expected=object(), current_references=True)
            self.assertEqual(model.requests, [])


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
