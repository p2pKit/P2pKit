#!/usr/bin/env python3
"""Fixed Stage1 graph controls; tiny ordinary-UID files, modeled suppliers.

The positive fixture composes the actual retained-query writer with the existing
modeled sender/recipient controllers. No Git, native process, network, GPG,
provider or hosted execution occurs. Fault-injected decoded-leaf controls are
explicitly separate from on-disk mutations and actual file/ledger controls.
Select only this file's own methods, not inherited historical test suites.
"""
from __future__ import annotations

from collections import Counter
import copy
import importlib.util
import os
from pathlib import Path, PureWindowsPath
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("initial_graph_sender_fixtures",
    Path(__file__).with_name("hosted-initial-recipient-sender-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)  # Its pre-project process/network/native-loader guard remains active.
N, S, O, I, Q = F.N, F.S, F.O, F.I, F.V.Q
REAL_QUERIES = Q.NativeGitQueries
ACQ = F.V.F.F


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class ReaderPathHistoryModels(unittest.TestCase):
    def test_same_path_fields_order_duplicates_and_type_failure_as_shared_checker(self):
        seen = []
        class ModelPath:
            def __init__(self, name):
                self.name = name
            def __str__(self):
                seen.append((self.name, "str"))
                return self.name
            @property
            def parts(self):
                seen.append((self.name, "parts"))
                return (self.name,)
            @property
            def drive(self):
                seen.append((self.name, "drive"))
                return ""
            @property
            def root(self):
                seen.append((self.name, "root"))
                return ""
        a, b = ModelPath("a"), ModelPath("b")
        nodes = tuple((value, ModelPath, "path", (value.name, (value.name,), "", "")) for value in (a, b, a))
        expected = [(name, field) for name in ("a", "b", "a") for field in ("str", "parts", "drive", "root")]
        for checker in (N._check_history, N._check_reader_path_history):
            seen.clear()
            checker(nodes)
            self.assertEqual(seen, expected)
            seen.clear()
            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                checker(((a, str, "path", nodes[0][3]),))
            self.assertEqual(seen, [])
            for index in range(4):
                saved = list(nodes[0][3])
                saved[index] = None
                with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                    checker(((a, ModelPath, "path", tuple(saved)),))
        left, right = Path("MODEL_EQUAL_PATH"), Path("MODEL_EQUAL_PATH")
        self.assertEqual(left, right)
        self.assertIsNot(left, right)
        paths = (*N._history_graph(left), *N._history_graph(right), *N._history_graph(left))
        self.assertEqual([node[0] is left for node in paths], [True, False, True])
        N._check_history(paths)
        N._check_reader_path_history(paths)

    def test_nonpath_history_is_delegated_without_skipping_mutations(self):
        values = {"sequence": [1, False]}
        opaque = object()
        record = O.clocks.Reading(O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], O.NS), 1)
        nodes = N._history_graph(Path("MODEL_PATH_ONLY"), values, opaque, record)
        with patch.object(N, "_check_history", wraps=N._check_history) as shared:
            N._check_reader_path_history(nodes)
        self.assertEqual([call.args[0] for call in shared.call_args_list],
            [(node,) for node in nodes if node[2] != "path"])
        self.assertTrue({"record", "mapping", "sequence", "opaque", "path"}.issubset({node[2] for node in nodes}))
        values["sequence"][1] = 0
        for checker in (N._check_history, N._check_reader_path_history):
            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                checker(nodes)
        values["sequence"][1] = False
        object.__setattr__(record, "nanoseconds", True)
        for checker in (N._check_history, N._check_reader_path_history):
            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                checker(nodes)
            with self.assertRaisesRegex(I.AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                checker(((opaque, object, "INVALID_MODE", None),))


class MatchTimeModels(unittest.TestCase):
    def setUp(self):
        self.fixture = ACQ.OriginalModels("runTest")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.choose("worker", "desktop-linux-x64")
        self.match, self.originals = self.fixture.acquire()
        self.raw = dict(self.originals)
        self.context = {"observed": self.fixture.context}
        self.args = (self.context, self.raw, ACQ.INVOCATION, self.fixture.clock, 1000 * O.NS, 1045 * O.NS)
        self.first = self.fixture.context["firstUseAt"]
        self.end = O.parse(self.match.record)["expiresAt"]

    def test_first_use_interpretation_is_data_only_and_never_observes_wall_time(self):
        with patch.object(N.time, "time", side_effect=AssertionError("NO_HISTORICAL_WALL_CLOCK")):
            inputs = N._retained_match_inputs(*self.args)
            matched, service = N._retained_match_at(inputs, now=self.first)
            later, same_service = N._retained_match_at(inputs, now=self.first + 1)
        self.assertEqual(matched.record, self.match.record)
        self.assertEqual((matched.record, service), (later.record, same_service))
        self.assertEqual(service["numericJobId"], 901)
        self.assertEqual(service["budgetAcceptance"], "NOT_ADMITTED")
        self.assertFalse(service["exportSaveAuthority"])

    def test_live_match_samples_time_after_original_interpretation(self):
        original = N._retained_match_inputs
        observed = []
        def interpreted(*args):
            result = original(*args)
            observed.append("interpreted")
            return result
        def now():
            self.assertEqual(observed, ["interpreted"])
            observed.append("late-now")
            return self.end
        with patch.object(N, "_retained_match_inputs", side_effect=interpreted), patch.object(N.time, "time", side_effect=now):
            with self.assertRaises(I.AdmissionError):
                N.retained_match(*self.args)
        self.assertEqual(observed, ["interpreted", "late-now"])

    def test_live_worker_bind_has_its_own_later_expiry_check(self):
        identity = N.initial_identity.bind_worker_match(self.match, event_raw=self.raw["event"],
            policy_raw=self.raw["candidate_policy_raw"], now=self.first)
        captured = (O.encoded(self.context), self.originals, ACQ.INVOCATION, 1000 * O.NS, 1045 * O.NS)
        with patch.object(N.time, "time", side_effect=[self.first, self.end]) as now:
            with self.assertRaises(I.AdmissionError):
                N._worker_time_records(identity, captured, self.fixture.clock)
        self.assertEqual(now.call_count, 2)

    def test_supplied_time_does_not_bypass_expiry_or_accept_a_gate_as_worker(self):
        inputs = N._retained_match_inputs(*self.args)
        with self.assertRaises(I.AdmissionError):
            N._retained_match_at(inputs, now=self.end)
        with self.assertRaisesRegex(I.AdmissionError, "RETAINED_MATCH_KIND"):
            N._retained_match_at(("other", inputs[1], inputs[2]), now=self.first)


class QueryScope:
    """Supplied Linux lifetime/retirement records; never spawns a process."""
    def __init__(self, case, job, invocation, state, home):
        self.case, self.job, self.invocation = case, job, invocation
        self.baseline, self.launches, self.closed = {(11, 22)}, [], False
        self.leader = {"pid": 3000 + len(case.query_scopes), "startTicks": 123}
        case.query_scopes.append(self)

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        self.launches.append({"api": "subprocess.Popen", "created": True, "requestedArgv": argv, "resolvedArgv": argv,
            "cwd": cwd, "pid": self.leader["pid"], "shell": False, "executable": argv[0], "outputMode": "caller-owned-files"})
        os.write(stdout.fileno(), self.case.query_output(tuple(argv[7:])))
        return SimpleNamespace(stdout=None, stderr=None, poll=lambda: 0)

    def description(self):
        return {"backend": S.BACKENDS["linux-x64"], "scope": "controlled-marker-inheriting-descendants",
            "invocation": self.invocation, "job": self.job, "launches": self.launches, "startedIdentities": [self.leader],
            "discoveryReconciliations": [], "discoveryErrors": []}

    def discover(self):
        return []

    def drain(self, *, grace, kill_wait, deadline=None):
        return []

    def close(self):
        self.closed = True


class OriginalGraphModels(F.SenderModels):
    def setUp(self):
        super().setUp()
        self.query_scopes, self.complete_queries, self.tiny_directories, self.read_owners = [], [], [], []
        self.stack.enter_context(patch.object(Q, "NativeGitQueries", side_effect=self.complete_query))
        self.stack.enter_context(patch.object(Q.processes, "host_role", return_value="linux-x64"))
        self.stack.enter_context(patch.object(Q.shutil, "which", return_value="/usr/bin/git"))
        self.stack.enter_context(patch.object(Q.processes.subprocess, "Popen", side_effect=AssertionError("NO_REAL_PROCESS")))
        initialize = Q._PosixDirectory.__init__
        def directory(raw, *args, **kwargs):
            initialize(raw, *args, **kwargs)
            self.tiny_directories.append(raw)
        self.stack.enter_context(patch.object(Q._PosixDirectory, "__init__", new=directory))
        self.addCleanup(self.clean_graph)

    def complete_query(self, root, path, *, check_cancel, owner_deadlines):
        result = REAL_QUERIES(root, path, check_cancel=check_cancel, owner_deadlines=owner_deadlines)
        self.complete_queries.append(result)
        return result

    def make_scope(self, job, invocation, state, home):
        if Path(state).name in ("source-before", "source-after", "source-final", "acquisition-queries"):
            return QueryScope(self, job, invocation, state, home)
        return super().make_scope(job, invocation, state, home)

    def query_output(self, suffix):
        git = self.fixture.git
        if suffix == ("rev-parse", "--show-toplevel"):
            return os.fsencode(N.ROOT) + b"\n"
        if suffix == ("status", "--porcelain=v1", "--untracked-files=all"):
            return b""
        if suffix[:2] == ("rev-parse", "--verify"):
            ref = suffix[2]
            value = (git.head if ref == "HEAD^{commit}" else git.main if ref == "refs/remotes/origin/main^{commit}" else
                git.main_tree if ref == N.acquisition.stages.BASE["commit"] + "^{tree}" else git.tree_value)
            return value.encode("ascii") + b"\n"
        return git.query(*suffix, limit=I.POLICY_LIMIT if suffix[:2] == ("cat-file", "blob") else 4096)

    def clean_graph(self):
        # Exclusively tiny synthetic fixtures. This is not hosted UNKNOWN recovery.
        for resource in self.tiny_directories:
            if type(resource) is Q._PosixDirectory:
                resource.close()
        for supplier in self.complete_queries:
            for row in supplier.resources:
                resource = row["owner"]
                if type(resource) is Q._PosixSink:
                    resource.close()
        S.QUARANTINE[:] = [item for item in S.QUARANTINE
            if type(item) is not tuple and not any(item is owner for owner in self.read_owners)]
        Q.QUARANTINE.clear()

    def graph(self):
        result = self.worker()
        prepared = N._retain_recipient_validation(result)
        emitted = O.parse(self.emit(prepared))
        self.sender_path = self.output_path(result)
        self.recipient_path = self.sender_path.with_name(self.sender_path.name.removesuffix("-output"))
        self.preparation_path = self.recipient_path.with_name(self.recipient_path.name.removesuffix("-recipient"))
        self.entry_path = self.preparation_path.with_name(self.preparation_path.name + "-entry")
        self.sha = emitted["recipientSenderSha256"]
        self.assertEqual(len(self.complete_queries), 12)
        self.assertEqual(len(self.query_scopes), 180)
        self.assertTrue(all(query.closed and not query.unknown for query in self.complete_queries))
        self.assertTrue(all(scope.closed for scope in self.query_scopes))
        self.start_reader()

    def start_reader(self):
        self.cancel_hook = self.deadline_hook = lambda: None
        self.read_hook = lambda owner, parent, name, contents: None
        self.reads = []
        self.first = self.fixture.observe()
        self.local_end = self.fixture.ns / O.NS + 120
        case = self
        class Fence:
            clock = case.first.clock
            def deadline(self, maximum, *, final=False, limit=None):
                case.deadline_hook()
                return case.local_end
            def now(self, *, final=False, minimum=0, limit=None):
                return max(case.first.nanoseconds, minimum)
        self.reader = S.Owner(self.local_end, Fence(), first=self.first, cancelled=lambda: self.cancel_hook())
        self.read_owners.append(self.reader)
        prefix_path = self.base / ("reader-prefix-" + str(len(self.read_owners)))
        prefix_path.mkdir(mode=0o700)
        self.prefix = self.reader.open(prefix_path)
        self.directory = self.reader.open(self.sender_path)
        self.prefix_rows = tuple(self.reader.resources)
        read = S.Owner.read
        def reading(owner, parent, name, *args, **kwargs):
            contents = read(owner, parent, name, *args, **kwargs)
            if owner is self.reader:
                self.reads.append((parent.path, name, len(contents)))
                self.read_hook(owner, parent, name, contents)
            return contents
        self.stack.enter_context(patch.object(S.Owner, "read", new=reading))

    def read_graph(self):
        return N._read_initial_recipient_originals(self.reader, self.directory,
            recipient_outcome="success", expected_sha256=self.sha)

    def refuse(self, code):
        with self.assertRaisesRegex((I.AdmissionError, O.OriginError, O.wire.BudgetError, Q.QueryError, RuntimeError), code):
            self.read_graph()
        self.assertIsNotNone(self.reader.original)

    def change(self, path, mutate):
        old = path.read_bytes()
        value = O.parse(old)
        mutate(value)
        path.write_bytes(O.encoded(value))
        return old

    def test_complete_1066_original_graph_has_no_authority_and_bounded_rereads(self):
        self.graph()
        registry_names = ("_PREPARED_RETURNS", "_READMISSION_RETURNS", "_AUTHORITY_RETURNS", "_RECIPIENT_RETURNS", "_RECIPIENT_SENDERS")
        registries = {name: tuple(getattr(N, name).items()) for name in registry_names}
        crypto = self.recipient_path / "crypto"
        (crypto / "unbound-fixture-only").write_bytes(b"DO_NOT_READ_THIS_MODEL_FILE")
        scandir = os.scandir
        def listing(path):
            self.assertNotEqual(Path(path), crypto, "crypto internals are not authenticated by this graph")
            return scandir(path)
        with patch.object(N.time, "time", side_effect=AssertionError("NO_HISTORICAL_WALL_TIME")), \
                patch.object(os, "scandir", side_effect=listing):
            result = self.read_graph()
        self.assertIs(type(result), tuple)
        self.assertEqual(len(result), 1066)
        self.assertEqual(len(dict(result)), 1066)
        self.assertTrue(all(type(name) is str and type(contents) is bytes for name, contents in result))
        self.assertEqual(len(self.reader.resources), len(self.prefix_rows) + 221)
        self.assertFalse(self.reader.closed)
        self.assertFalse(self.reader.unknown)
        self.assertIsNone(self.reader.original)
        self.assertTrue(all(tuple(getattr(N, name).items()) == saved for name, saved in registries.items()))
        counts = Counter((path, name) for path, name, _ in self.reads)
        self.assertEqual(len(counts), 1066)
        self.assertLessEqual(max(counts.values()), 4)
        retained_bytes = sum(len(contents) for _, contents in result)
        self.assertLessEqual(retained_bytes, Q.MAX_SESSION_BYTES)
        self.assertLessEqual(sum(size for _, _, size in self.reads), 4 * retained_bytes)
        self.assertFalse(any(path == crypto for path, _, _ in self.reads))
        self.reader.close()
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.reader.resources))

    def test_extra_or_missing_wrapper_names_refuse_before_reading_unlisted_bytes(self):
        self.graph()
        extra = self.preparation_path / "unexpected"
        extra.write_bytes(b"MODEL_EXTRA")
        self.refuse("GRAPH_DIRECTORY_(LIMIT|ROSTER)")
        self.assertFalse(any(name == "unexpected" for _, name, _ in self.reads))
        extra.unlink()
        self.start_reader()
        missing = self.entry_path / "entry-pending.json"
        missing.unlink()
        self.refuse("GRAPH_DIRECTORY_ROSTER")

    def test_whole_graph_cap_refuses_before_any_query_leaf_allocation(self):
        self.graph()
        session_path = self.preparation_path / "source-before/session-result.json"
        raw = session_path.read_bytes()
        session = O.parse(raw)
        # The full fixed declarations must reserve bytes before the trusted leaf
        # can allocate. No oversized file is created for this negative control.
        for item in session["readbacks"]:
            item["bytes"] = item["maximum"] = Q.MAX_RECEIPT_BYTES
        session_path.write_bytes(O.encoded(session))
        side_path = session_path.with_name("source-return.json")
        self.change(side_path, lambda value: value.update(sessionSha256=O.digest(session_path.read_bytes())))
        self.change(self.preparation_path / "context.json", lambda value: value.update(sourceReturnSha256=O.digest(side_path.read_bytes())))
        with patch.object(N, "_read_initial_query_originals", side_effect=AssertionError("NO_LEAF_ALLOCATION")):
            self.refuse("GRAPH_BYTE_LIMIT")
        self.assertEqual(len(self.reader.resources), len(self.prefix_rows) + 29)

    def test_real_query_leaf_tail_is_pinned_before_next_cancellation_callback(self):
        self.graph()
        original = N._read_initial_query_originals
        finished = []
        def leaf(*args, **kwargs):
            result = original(*args, **kwargs)
            finished.append(True)
            return result
        changed = []
        def cancel():
            if finished and not changed:
                row = self.reader.resources[-1]
                changed.append(row)
                self.reader.resources[-1] = dict(row)
        self.cancel_hook = cancel
        with patch.object(N, "_read_initial_query_originals", side_effect=leaf):
            self.refuse("GRAPH_ROSTER_CHANGED")
        self.assertEqual(len(finished), 1)
        self.assertTrue(self.reader.unknown)
        self.assertTrue(changed)

    def test_failed_leaf_additions_preserve_falsey_primary_without_invented_unknown(self):
        self.graph()
        failure = FalseyFailure("MODEL_LEAF_READ_CANCELLED")
        def changed(owner, parent, name, contents):
            if parent.path == self.preparation_path / "source-before" and name == "owner.json":
                raise failure
        self.read_hook = changed
        with self.assertRaises(FalseyFailure) as caught:
            self.read_graph()
        self.assertIs(caught.exception, failure)
        self.assertIs(self.reader.original, failure)
        self.assertFalse(self.reader.unknown)
        self.assertEqual(len(self.reader.resources), len(self.prefix_rows) + 29 + 13)
        self.read_hook = lambda *_: None
        self.reader.close()
        self.assertTrue(all(row["attempted"] and row["closed"] for row in self.reader.resources))

    def test_wrapper_raw_row_is_pinned_before_postallocation_callback(self):
        self.graph()
        changed = []
        def deadline():
            if len(self.reader.resources) == len(self.prefix_rows) + 1 and not changed:
                changed.append(self.reader.resources[-1])
                self.reader.resources[-1] = dict(self.reader.resources[-1])
        self.deadline_hook = deadline
        self.refuse("GRAPH_(END|ROSTER)_CHANGED")
        self.assertTrue(self.reader.unknown)
        self.assertEqual(len(changed), 1)
        self.assertTrue(any(type(item) is tuple and changed[0]["owner"] in item[2] for item in S.QUARANTINE))

    def test_equal_prefix_path_replacement_does_not_become_a_new_baseline(self):
        self.graph()
        changed = []
        def read_hook(owner, parent, name, contents):
            if name == "sender-pending.json" and not changed:
                changed.append(self.prefix.path)
                self.prefix.path = Path(str(self.prefix.path))
        self.read_hook = read_hook
        self.refuse("GRAPH_PREFIX_PATH_CHANGED")
        self.assertTrue(self.reader.unknown)

    def test_earlier_query_original_is_reread_after_later_leaf_traversal(self):
        self.graph()
        original = N._read_initial_query_originals
        changed = []
        def leaf(owner, directory, **kwargs):
            result = original(owner, directory, **kwargs)
            if directory.path == self.recipient_path / "source-final":
                path = self.preparation_path / "source-before/owner.json"
                changed.append(path)
                self.change(path, lambda value: value.update(job="f" * 32))
            return result
        with patch.object(N, "_read_initial_query_originals", side_effect=leaf):
            self.refuse("GRAPH_REREAD_CHANGED")
        self.assertEqual(len(changed), 1)

    def test_decoded_leaf_source_must_equal_enclosing_observed_source(self):
        self.graph()
        original = N._read_initial_query_originals
        def leaf(*args, **kwargs):
            session, pairs, side = original(*args, **kwargs)
            query = O.parse(session)["queries"][2]["id"]
            name = "query-" + query + "/stdout.log"
            return session, tuple((key, b"f" * 40 + b"\n" if key == name else contents) for key, contents in pairs), side
        # Explicit decoded-return fault injection, not a native/Git claim.
        with patch.object(N, "_read_initial_query_originals", side_effect=leaf):
            self.refuse("GRAPH_QUERY_SOURCE")

    def test_decoded_leaf_ancestor_must_equal_enclosing_native_context(self):
        self.graph()
        original = N._read_initial_query_originals
        changed = []
        def leaf(owner, directory, **kwargs):
            session, pairs, side = original(owner, directory, **kwargs)
            if directory.path != self.preparation_path / "acquisition-queries":
                return session, pairs, side
            result = []
            for key, contents in pairs:
                if key == "owner.json":
                    value = O.parse(contents)
                    home = value["ancestorContext"]["GRADLE_USER_HOME"]
                    value["ancestorContext"]["GRADLE_USER_HOME"] = home[:-1] + ("x" if home[-1] != "x" else "y")
                    replacement = O.encoded(value)
                    self.assertEqual(len(replacement), len(contents))
                    self.assertNotEqual(replacement, contents)
                    changed.append(True)
                    contents = replacement
                result.append((key, contents))
            # Explicit decoded-return injection, equal length: reach the outer
            # ancestor binding, not an earlier declared-size/hash refusal.
            return session, tuple(result), side
        with patch.object(N, "_read_initial_query_originals", side_effect=leaf):
            self.refuse("GRAPH_BINDING")
        self.assertEqual(changed, [True])

    def test_windows_native_relative_names_use_fixed_graph_keys(self):
        self.graph()
        original, path = N._read_initial_query_originals, N.Path
        leaves = []
        stop = RuntimeError("MODEL_FIRST_SOURCE_VALIDATED")
        def leaf(*args, **kwargs):
            session, pairs, side = original(*args, **kwargs)
            leaves.append(True)
            return session, tuple((str(PureWindowsPath(key)), contents) for key, contents in pairs), side
        def relative(value):
            # Only the native relative-name seam is Windows. Real fixture paths
            # remain POSIX; setting a role flag alone would miss this defect.
            return PureWindowsPath(value) if value == "" or value.startswith("query-") else path(value)
        with patch.object(N, "Path", new=relative), patch.object(N, "_read_initial_query_originals", side_effect=leaf), \
                patch.object(N, "_initial_graph_native", side_effect=stop):
            with self.assertRaises(RuntimeError) as caught:
                self.read_graph()
        self.assertIs(caught.exception, stop)
        self.assertEqual(leaves, [True])
        self.assertIs(self.reader.original, stop)
        self.assertFalse(self.reader.unknown)
        self.reader.close()

    def test_windows_native_relative_name_does_not_accept_posix_alias(self):
        self.graph()
        original, path = N._read_initial_query_originals, N.Path
        changed = []
        def leaf(*args, **kwargs):
            session, pairs, side = original(*args, **kwargs)
            result = []
            for key, contents in pairs:
                native = str(PureWindowsPath(key))
                if not changed and "\\" in native:
                    native = native.replace("\\", "/")
                    changed.append(True)
                result.append((native, contents))
            return session, tuple(result), side
        def relative(value):
            return PureWindowsPath(value) if value == "" or value.startswith("query-") else path(value)
        with patch.object(N, "Path", new=relative), patch.object(N, "_read_initial_query_originals", side_effect=leaf):
            self.refuse("GRAPH_QUERY_RETURN")
        self.assertEqual(changed, [True])

    def test_decoded_recipient_identity_requires_exact_scalar_types(self):
        self.graph()
        native, require = N._initial_graph_native, N.require
        changed = []
        def phase(*args):
            start, row, birth, child, ack = native(*args)
            if args[-1] == "R":
                child = copy.deepcopy(child)
                identity = child["recipient"]["work_identity"]
                duplicate = [float(identity[0]), identity[1]]
                self.assertEqual(duplicate, identity)
                self.assertNotEqual(O.encoded(duplicate), O.encoded(identity))
                child["recipient"]["work_identity"] = duplicate
                changed.append(True)
            return start, row, birth, child, ack
        def boundary(value, reason):
            # Explicit decoded-native fault. If the supplier predicate misses
            # it, fail here rather than spending another complete graph reread.
            if reason == "GRAPH_RECIPIENT_CHRONOLOGY":
                raise RuntimeError("MODEL_INVALID_SUPPLIER_WAS_ACCEPTED")
            return require(value, reason)
        with patch.object(N, "_initial_graph_native", new=phase), patch.object(N, "require", new=boundary):
            self.refuse("GRAPH_SUPPLIER_RECORD")
        self.assertEqual(changed, [True])


class NativeRecordModels(F.SenderModels):
    """Pure phase grammar needs only the existing modeled query supplier.

    Full query-file generation is reserved for wrapper/file controls; repeating
    it here would add setup cost without testing another graph traversal.
    """
    def graph(self):
        result = self.worker()
        prepared = N._retain_recipient_validation(result)
        self.emit(prepared)
        self.sender_path = self.output_path(result)
        self.recipient_path = self.sender_path.with_name(self.sender_path.name.removesuffix("-output"))
        self.preparation_path = self.recipient_path.with_name(self.recipient_path.name.removesuffix("-recipient"))
        self.entry_path = self.preparation_path.with_name(self.preparation_path.name + "-entry")
        self.first = self.fixture.observe()

    def phase_inputs(self, key):
        path = {"P": self.preparation_path, "E": self.entry_path, "A": self.recipient_path / "authority", "R": self.recipient_path}[key]
        context = (path / ("recipient-context.json" if key == "R" else "context.json")).read_bytes()
        if key == "P":
            past = S.history.HistoricalPrelude((path / "prelude.json").read_bytes())
            first, work, final = past.first, past.work, past.final
        elif key == "E":
            _, _, first, work, final = N._entry_frame((path / "entry-window.json").read_bytes())
        elif key == "A":
            _, _, first, work, final = N._authority_frame((path / "authority-window.json").read_bytes())
        else:
            _, _, first, ends = N._recipient_frame((path / "recipient-window.json").read_bytes())
            work, final = ends[:2]
        phase = path / ("recipient-validation" if key == "R" else "service")
        records = {name: (phase / name).read_bytes() for name in S.PHASE_FILES}
        return context, path, self.first.clock, first, work, final, records, (phase / "child-result.json").read_bytes(), key

    def native_role_inputs(self, role):
        """Supplied native grammar only; no Windows/macOS filesystem or host."""
        inputs = list(self.phase_inputs("P"))
        clock = O.clocks.ClockIdentity(role, O.clocks.DOMAINS[role], O.NS)
        inputs[2] = clock
        records = inputs[6]
        start, row, birth = (O.parse(records[name]) for name in ("start.json", "result.json", "native-start.json"))
        start["role"] = row["role"] = role
        records["start.json"] = O.encoded(start)
        pid, preparer_pid = row["leader"]["pid"], row["preparerIdentity"]["pid"]
        if role == "windows-x64":
            leader = {"pid": pid, "creationFileTime": 123, "jobAssignedBeforeResume": True}
            preparer = {"pid": preparer_pid, "creationFileTime": 456}
            baseline = None
        else:
            leader = {"pid": pid, "uniqueId": 123, "startSeconds": 456, "startMicroseconds": 0, "pidVersion": 0}
            preparer = dict(leader, pid=preparer_pid, uniqueId=789)
            baseline = [[11, 22, 33, 0]]
        for record in (row, birth):
            record["leader"], record["preparerIdentity"] = copy.deepcopy(leader), copy.deepcopy(preparer)
            ownership = record["ownership"]
            ownership.update(backend=S.BACKENDS[role], scope="kernel-job-no-breakaway-kill-on-close" if role == "windows-x64"
                else "controlled-marker-inheriting-descendants", startedIdentities=[copy.deepcopy(leader)])
            if role == "windows-x64":
                launch = ownership["launches"][0]
                launch.update(api="CreateProcessW", batch=False, applicationName=row["launchArgv"][0],
                    commandLine=S.subprocess.list2cmdline(row["launchArgv"]), resumed=True, jobAssignedBeforeResume=True,
                    outputMode="caller-owned-native-files", resourceCleanup=[{"phase": "launch-temporary",
                        "resource": name, "status": "RETIRED"} for name in
                        ("startup-attributes", "launch-handle-0", "launch-handle-1", "launch-handle-2", "primary-thread")])
            else:
                ownership.update(observationReconciliations=[], drainReconciliations=[{"outcome": "retired", "signalReconciliations": []}])
        records["baseline.json"] = O.encoded({"role": role, "baseline": baseline, "kernelJob": role == "windows-x64"})
        records["native-start.json"] = O.encoded(birth)
        child = O.parse(inputs[7])
        child.update(clock=O.clock_value(clock), startSha256=O.digest(records["start.json"]))
        inputs[7] = O.encoded(child)
        ack = O.parse(records["stdout.log"])
        ack.update(clock=O.clock_value(clock), terminalSha256=O.digest(inputs[7]))
        records["stdout.log"] = O.encoded(ack)
        row.update(baselineSha256=O.digest(records["baseline.json"]), nativeStartSha256=O.digest(records["native-start.json"]))
        row["captures"]["stdout"] = {"bytes": len(records["stdout.log"]), "sha256": O.digest(records["stdout.log"])}
        records["result.json"] = O.encoded(row)
        return inputs

    def test_native_birth_leader_requires_exact_duplicate_scalar_types(self):
        self.graph()
        for role, field, replacement in (("windows-x64", "jobAssignedBeforeResume", 1), ("macos-arm64", "pidVersion", False)):
            with self.subTest(role=role):
                inputs = self.native_role_inputs(role)
                N._initial_graph_native(*inputs)
                records = inputs[6]
                birth = O.parse(records["native-start.json"])
                birth["leader"][field] = replacement
                records["native-start.json"] = O.encoded(birth)
                row = O.parse(records["result.json"])
                self.assertEqual(row["leader"], birth["leader"])
                self.assertNotEqual(O.encoded(row["leader"]), O.encoded(birth["leader"]))
                row["nativeStartSha256"] = O.digest(records["native-start.json"])
                records["result.json"] = O.encoded(row)
                with self.assertRaisesRegex(I.AdmissionError, "GRAPH_NATIVE_RETIREMENT"):
                    N._initial_graph_native(*inputs)

    def test_native_birth_launches_require_exact_duplicate_scalar_types(self):
        self.graph()
        inputs = self.native_role_inputs("windows-x64")
        records = inputs[6]
        row, birth = (O.parse(records[name]) for name in ("result.json", "native-start.json"))
        # The shared supplied grammar admits additional native fields. A
        # synthetic additional scalar must still have an exact birth copy.
        for record in (row, birth):
            record["ownership"]["launches"][0]["MODEL_ONLY_DUPLICATE"] = True
        records["native-start.json"] = O.encoded(birth)
        row["nativeStartSha256"] = O.digest(records["native-start.json"])
        records["result.json"] = O.encoded(row)
        N._initial_graph_native(*inputs)
        birth["ownership"]["launches"][0]["MODEL_ONLY_DUPLICATE"] = 1
        records["native-start.json"] = O.encoded(birth)
        row["nativeStartSha256"] = O.digest(records["native-start.json"])
        records["result.json"] = O.encoded(row)
        with self.assertRaisesRegex(I.AdmissionError, "GRAPH_NATIVE_BIRTH"):
            N._initial_graph_native(*inputs)

    def test_native_ack_and_child_clocks_require_exact_duplicate_numeric_types(self):
        self.graph()
        for phase in ("P", "E", "A", "R"):
            inputs = self.phase_inputs(phase)
            N._initial_graph_native(*inputs)
            for target, reason in (("ack", "GRAPH_NATIVE_ACK"), ("child", "GRAPH_NATIVE_CHILD")):
                with self.subTest(phase=phase, target=target):
                    records = copy.deepcopy(inputs[6])
                    child_raw = inputs[7]
                    ack = O.parse(records["stdout.log"])
                    value = ack if target == "ack" else O.parse(child_raw)
                    original = copy.deepcopy(value["clock"])
                    value["clock"]["ticksPerSecond"] = float(value["clock"]["ticksPerSecond"])
                    self.assertEqual(value["clock"], original)
                    self.assertNotEqual(O.encoded(value["clock"]), O.encoded(original))
                    if target == "child":
                        child_raw = O.encoded(value)
                        ack["terminalSha256"] = O.digest(child_raw)
                    records["stdout.log"] = O.encoded(ack)
                    row = O.parse(records["result.json"])
                    row["captures"]["stdout"] = {"bytes": len(records["stdout.log"]), "sha256": O.digest(records["stdout.log"])}
                    records["result.json"] = O.encoded(row)
                    with self.assertRaisesRegex(I.AdmissionError, reason):
                        N._initial_graph_native(*inputs[:6], records, child_raw, inputs[-1])

    def test_pure_native_grammar_rejects_extra_fields_and_bool_schema_in_each_phase(self):
        self.graph()
        for key in ("P", "E", "A", "R"):
            inputs = self.phase_inputs(key)
            N._initial_graph_native(*inputs)
            for change in (lambda value: value.update(extra=True), lambda value: value.update(schema=True)):
                with self.subTest(phase=key, change=change):
                    altered = copy.deepcopy(inputs[6])
                    start = O.parse(altered["start.json"])
                    change(start)
                    altered["start.json"] = O.encoded(start)
                    with self.assertRaisesRegex(I.AdmissionError, "GRAPH_RECORD"):
                        N._initial_graph_native(*inputs[:6], altered, *inputs[7:])

    def test_pure_native_grammar_preserves_original_argv_birth_and_retirement(self):
        self.graph()
        inputs = self.phase_inputs("P")
        for field, value in (("launchArgv", ["MODEL_WRONG_COMMAND"]), ("scopeClosed", False),
                ("retirement", "UNKNOWN"), ("survivors", [321]), ("errors", ["MODEL_ERROR"]), ("preparerIdentity", {"pid": 1234, "startTicks": 5678})):
            altered = copy.deepcopy(inputs[6])
            row = O.parse(altered["result.json"])
            row[field] = value
            altered["result.json"] = O.encoded(row)
            with self.subTest(field=field), self.assertRaises(I.AdmissionError):
                N._initial_graph_native(*inputs[:6], altered, *inputs[7:])

    def test_pure_native_capture_metadata_is_not_bool_integer_aliasable(self):
        self.graph()
        inputs = self.phase_inputs("R")
        for group, name, field, value in (("captureOutcomes", "stdout", "closed", 1),
                ("captures", "stderr", "bytes", False)):
            altered = copy.deepcopy(inputs[6])
            row = O.parse(altered["result.json"])
            row[group][name][field] = value
            altered["result.json"] = O.encoded(row)
            with self.subTest(field=field), self.assertRaisesRegex(I.AdmissionError, "GRAPH_NATIVE_CAPTURES"):
                N._initial_graph_native(*inputs[:6], altered, *inputs[7:])


if __name__ == "__main__":
    suite = unittest.TestSuite(cls(name) for cls in (ReaderPathHistoryModels, MatchTimeModels, OriginalGraphModels, NativeRecordModels)
        for name in sorted(cls.__dict__) if name.startswith("test_"))
    raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
