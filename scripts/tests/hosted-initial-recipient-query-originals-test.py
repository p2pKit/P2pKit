#!/usr/bin/env python3
"""Fixed Stage1 query-original controls: tiny POSIX files, modeled native/Git.

No subprocess, actual Git/native/GPG/HTTP/provider supplier or hosted identity
is executed. The real query writer only captures bytes from the explicit model
below. Reader ownership and file operations run under an ordinary fixture UID.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes  # Stdlib initialization before the pre-project guard.
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise RuntimeError("OFFLINE_PROCESS_NETWORK_NATIVE_FORBIDDEN")


sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("initial_query_originals_subject", ROOT / "scripts/run-hosted-initial-recipient.py")
N = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = N
spec.loader.exec_module(N)
S, Q, O, I = N.native, N.Q, N.O, N.I


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class ModeledScope:
    """No native calls: supplied process records plus tiny borrowed POSIX fds."""
    def __init__(self, case, job, invocation, state, home):
        self.case, self.job, self.invocation = case, job, invocation
        self.baseline, self.launches, self.closed = {(11, 22)}, [], False
        self.leader = {"pid": 2000 + len(case.scopes), "startTicks": 321}
        case.scopes.append(self)

    def spawn(self, argv, cwd, environment, *, stdout, stderr):
        self.launches.append({"api": "subprocess.Popen", "created": True, "requestedArgv": argv,
            "resolvedArgv": argv, "cwd": cwd, "pid": self.leader["pid"], "shell": False,
            "executable": argv[0], "outputMode": "caller-owned-files"})
        os.write(stdout.fileno(), self.case.output(tuple(argv[7:])))
        return SimpleNamespace(stdout=None, stderr=None, poll=lambda: 0)

    def discover(self):
        return []

    def drain(self, *, grace, kill_wait, deadline=None):
        return []

    def description(self):
        return {"backend": S.BACKENDS["linux-x64"], "scope": "controlled-marker-inheriting-descendants",
            "invocation": self.invocation, "job": self.job, "launches": self.launches,
            "startedIdentities": [self.leader], "discoveryReconciliations": [], "discoveryErrors": []}

    def close(self):
        self.closed = True


class QueryOriginalModels(unittest.TestCase):
    def setUp(self):
        self.assertNotEqual(os.geteuid(), 0, "actual tiny POSIX files require an ordinary UID")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.temp = tempfile.TemporaryDirectory(prefix="initial-query-originals-model-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.root.mkdir(mode=0o700)
        self.runner_temp = self.base / "runner-temp"
        self.runner_temp.mkdir(mode=0o700)
        self.stack.enter_context(patch.object(N, "ROOT", self.root))
        self.stack.enter_context(patch.dict(os.environ, {"GITHUB_JOB": "populate", "GITHUB_RUN_ID": "301",
            "GITHUB_RUN_ATTEMPT": "1", "RUNNER_TEMP": str(self.runner_temp)}, clear=True))
        self.scopes, self.suppliers, self.held, self.reads = [], [], [], []
        self.stack.enter_context(patch.object(Q.processes, "host_role", return_value="linux-x64"))
        self.stack.enter_context(patch.object(Q.processes, "make_scope", side_effect=lambda *args: ModeledScope(self, *args)))
        self.stack.enter_context(patch.object(Q.shutil, "which", return_value="/usr/bin/git"))
        self.stack.enter_context(patch.object(Q.processes.subprocess, "Popen", side_effect=AssertionError("NO_REAL_PROCESS")))
        self.addCleanup(self.cleanup_files)
        self.source, self.tree = "1" * 40, "2" * 40
        # Deliberately not a policy/key: the query-only reader binds blob bytes,
        # while higher identity/crypto/authority validation remains outstanding.
        self.policy = b"MODEL_ONLY_NOT_A_RECIPIENT_POLICY\n"
        self.blob = hashlib.sha1(b"blob " + str(len(self.policy)).encode("ascii") + b"\0" + self.policy).hexdigest()
        self.entry = b"100644 blob " + self.blob.encode("ascii") + b"\t" + I.POLICY_PATH.encode("ascii") + b"\x00"
        self.bins = {"base_policy_entry": b"", "ancestry_raw": N.acquisition.stages.BASE["commit"].encode("ascii") + b"\n",
            "candidate_policy_entry": self.entry, "candidate_policy_raw": self.policy}
        self.cancel_hook = self.deadline_hook = self.read_hook = lambda: None
        self.cancel_calls, self.cancel_error = 0, None
        self.clock = O.clocks.ClockIdentity("linux-x64", O.clocks.LINUX_DOMAIN, O.NS)
        self.first = O.clocks.Reading(self.clock, 500 * O.NS)
        self.local_end = time.monotonic() + 20
        case = self

        class Fence:
            clock = case.clock

            def deadline(self, maximum, *, final=False, limit=None):
                case.deadline_hook()
                return case.local_end

        self.fence = Fence()
        self.owner = S.Owner(self.local_end, self.fence, first=self.first, cancelled=self.cancel)
        self.prefix_path = self.base / "existing-borrowed-prefix"
        self.prefix_path.mkdir(mode=0o700)
        self.prefix = self.owner.open(self.prefix_path)
        self.prefix_rows = tuple(self.owner.resources)
        self.read_method = S.Owner.read

        def read(owner, directory, name, *args, **kwargs):
            raw = self.read_method(owner, directory, name, *args, **kwargs)
            self.reads.append((directory.path, name))
            self.read_hook()
            return raw

        self.stack.enter_context(patch.object(S.Owner, "read", new=read))

    def cancel(self):
        self.cancel_calls += 1
        self.cancel_hook()
        if self.cancel_error is not None:
            raise self.cancel_error

    def cleanup_files(self):
        # No real native worker/Windows handle exists. Retire fixture POSIX
        # objects only, including the explicit mutation/UNKNOWN controls.
        for supplier in self.suppliers:
            for row in supplier.resources:
                resource = row["owner"]
                if type(resource) in (Q._PosixDirectory, Q._PosixSink):
                    resource.close()
        for row in self.owner.resources:
            if type(row) is dict and type(row.get("owner")) is Q._PosixDirectory:
                row["owner"].close()
        for resource in self.held:
            if type(resource) is Q._PosixDirectory:
                resource.close()
        self.prefix.close()
        S.QUARANTINE.clear()
        Q.QUARANTINE.clear()
        S.diagnostics._QUARANTINE.clear()

    def output(self, suffix):
        base = N.acquisition.stages.BASE
        outputs = {("rev-parse", "--show-toplevel"): os.fsencode(self.root) + b"\n",
            ("status", "--porcelain=v1", "--untracked-files=all"): b"",
            ("rev-parse", "--verify", "HEAD^{commit}"): self.source.encode("ascii") + b"\n",
            ("rev-parse", "--verify", self.source + "^{tree}"): self.tree.encode("ascii") + b"\n",
            ("rev-parse", "--is-shallow-repository"): b"false\n",
            ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"): base["commit"].encode("ascii") + b"\n",
            ("rev-parse", "--verify", base["commit"] + "^{tree}"): base["tree"].encode("ascii") + b"\n",
            ("ls-tree", "-z", base["commit"], "--", I.POLICY_PATH): b"",
            ("merge-base", base["commit"], self.source): self.bins["ancestry_raw"],
            ("ls-tree", "-z", self.source, "--", I.POLICY_PATH): self.entry,
            ("cat-file", "-s", self.blob): str(len(self.policy)).encode("ascii") + b"\n",
            ("cat-file", "blob", self.blob): self.policy}
        return outputs[suffix]

    def fixture(self, *, acquisition=False, location=None):
        preparation = self.runner_temp / "p2pkit-initial-recipient-301-1-worker"
        self.path = location or preparation / ("acquisition-queries" if acquisition else "source-before")
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        supplier = Q.NativeGitQueries(self.root, self.path, check_cancel=lambda: None)
        self.suppliers.append(supplier)
        git = I.GitView(self.root, dict(os.environ), supplier)
        context = {"source": {"commit": self.source, "tree": self.tree}}
        if acquisition:
            supplier._write(supplier.private, "event.bin", b"MODEL_EVENT")
        self.assertEqual(N.acquisition._source(git, context, lambda: None), self.bins)
        for name in N.SOURCE_KEYS:
            supplier._write(supplier.private, name + ".bin", self.bins[name])
        if acquisition:
            for name in N.HTTP_KEYS:
                supplier._write(supplier.private, name + ".bin", ("MODEL_HTTP_" + name).encode("ascii"))
            self.assertEqual(N.acquisition._source(git, context, lambda: None), self.bins)
            for name in ("observation", "match"):
                supplier._write(supplier.private, name + ".bin", ("MODEL_" + name).encode("ascii"))
        supplier.close()
        self.session_raw = (self.path / "session-result.json").read_bytes()
        self.session = O.parse(self.session_raw)
        self.sha = O.digest(self.session_raw)
        self.sidecar = None
        if not acquisition:
            self.side = {"schema": 1, "scope": N.SOURCE_SCOPE,
                "originalsSha256": {name: O.digest(raw) for name, raw in self.bins.items()},
                "sessionSha256": self.sha, "clock": O.clock_value(self.clock), "returnedNs": 400 * O.NS}
            self.sidecar = O.encoded(self.side)
            self.write("source-return.json", self.sidecar)
        self.directory = self.owner.open(self.path)
        self.held.append(self.directory)
        self.original_rows = tuple(self.owner.resources)
        self.reads.clear()
        return supplier

    def write(self, name, raw):
        path = self.path / name
        path.write_bytes(raw)
        path.chmod(0o600)

    def link_session(self):
        self.session_raw = Q.encoded(self.session)
        self.sha = O.digest(self.session_raw)
        self.write("session-result.json", self.session_raw)
        if self.sidecar is not None:
            self.side["sessionSha256"] = self.sha
            self.sidecar = O.encoded(self.side)
            self.write("source-return.json", self.sidecar)

    def rebind_original(self, name, raw):
        """Synthetic coherent graph mutation, never a repair of real originals."""
        self.write(name, raw)
        path = self.path / name
        row = next(row for row in self.session["readbacks"] if (row["parent"], row["name"]) == (str(path.parent), path.name))
        row.update(bytes=len(raw), sha256=O.digest(raw))
        if not name.endswith(".log"):
            row["maximum"] = max(1, len(raw))
        self.link_session()

    def read(self, **overrides):
        return N._read_initial_query_originals(self.owner, self.directory,
            **{"expected_session_sha256": self.sha, "expected_source_return_raw": self.sidecar, **overrides})

    def refuse(self, pattern="QUERY_ORIGINAL", **overrides):
        with self.assertRaisesRegex((ValueError, RuntimeError), pattern):
            self.read(**overrides)

    def test_entry_is_dormant_and_not_a_command(self):
        self.assertTrue(callable(getattr(N, "_read_initial_query_originals", None)))
        import inspect
        self.assertNotIn("_read_initial_query_originals", inspect.getsource(N.main))

    def test_complete_source12_retains65_rows_and_separate_sidecar(self):
        self.fixture()
        self.assertNotIn("end", self.owner.__dict__)
        raw, records, side = self.read()
        self.assertNotIn("end", self.owner.__dict__)
        self.assertEqual((len(self.session["queries"]), len(records), len(list(self.path.iterdir()))), (12, 65, 20))
        self.assertEqual((raw, side), (self.session_raw, self.sidecar))
        self.assertEqual(dict(records)["base_policy_entry.bin"], b"")
        self.assertNotIn("source-return.json", dict(records))
        self.assertNotIn("session-result.json", dict(records))
        self.assertEqual(len(self.owner.resources), len(self.original_rows) + 13)
        self.assertTrue(all(now is old for now, old in zip(self.owner.resources, self.original_rows)))
        self.assertFalse(self.owner.closed)
        self.assertTrue(all(not row["closed"] for row in self.owner.resources))
        self.owner.close()
        self.assertTrue(all(row["closed"] for row in self.owner.resources))

    def test_complete_acquisition24_has_real42_member_roster(self):
        self.fixture(acquisition=True)
        raw, records, side = self.read()
        self.assertEqual((len(self.session["queries"]), len(records), len(list(self.path.iterdir()))), (24, 136, 42))
        self.assertIsNone(side)
        self.assertEqual(raw, self.session_raw)
        self.assertEqual(len(self.owner.resources), len(self.original_rows) + 25)
        self.assertEqual([name for name, _raw in records][0:2], ["owner.json", "event.bin"])
        self.assertTrue(all(scope.closed for scope in self.scopes))  # Model objects, not native evidence.

    def test_all12_source_owned_locations_select_the_fixed_family(self):
        preparation = self.runner_temp / "p2pkit-initial-recipient-301-1-worker"
        recipient = preparation.with_name(preparation.name + "-recipient")
        choices = [(parent / name, name == "acquisition-queries") for parent in
            (preparation, preparation.with_name(preparation.name + "-entry"), recipient / "authority")
            for name in ("source-before", "acquisition-queries", "source-after")]
        choices.extend((recipient / "recipient-validation" / name, False) for name in ("source-before", "source-after"))
        choices.append((recipient / "source-final", False))
        for location, acquisition in choices:
            with self.subTest(location=location.relative_to(self.base)):
                self.fixture(acquisition=acquisition, location=location)
                self.assertEqual(len(self.read()[1]), 136 if acquisition else 65)

    def test_each_metadata_capture_and_bin_byte_change_refuses(self):
        self.fixture()
        query = "query-" + self.session["queries"][0]["id"]
        for name in ("owner.json", "candidate_policy_raw.bin", *(query + "/" + part for part in
                ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"))):
            with self.subTest(name=name):
                original = (self.path / name).read_bytes()
                self.write(name, original[:-1] + b" " if original else b" ")
                self.refuse("BYTES_CHANGED|QUERY_CAPTURE_CHANGED")
                self.write(name, original)
                self.reset_model_failure()

    def reset_model_failure(self):
        # Model-only reuse after a deliberately failed offline control; no
        # production registry/capability is reset by this test helper.
        self.cancel_error = None
        self.owner.original = None
        self.owner.unknown = False
        self.owner.errors.clear()
        S.QUARANTINE.clear()
        Q.QUARANTINE.clear()
        S.diagnostics._QUARANTINE.clear()

    def test_missing_hash_is_not_a_legacy_fallback(self):
        self.fixture()
        self.session["readbacks"][0].pop("sha256")
        self.link_session()
        self.refuse("READBACK")
        self.assertEqual(self.owner.resources, list(self.original_rows))

    def test_malformed_hash_boolean_count_and_extra_fields_refuse(self):
        self.fixture()
        original = dict(self.session["readbacks"][0])
        for change in ({"sha256": "A" * 64}, {"sha256": "f" * 64 + "\n"}, {"bytes": True},
                {"maximum": True}, {"bytes": -1}, {"digest": "f" * 64}):
            with self.subTest(change=change):
                self.session["readbacks"][0] = {**original, **change}
                self.link_session()
                self.refuse("READBACK")
                self.reset_model_failure()

    def test_duplicate_id_and_readback_reordering_refuse(self):
        self.fixture(acquisition=True)
        original = self.session["queries"][1]["id"]
        self.session["queries"][1]["id"] = self.session["queries"][0]["id"]
        self.link_session()
        self.refuse("IDS")
        self.reset_model_failure()
        self.session["queries"][1]["id"] = original
        self.session["readbacks"][1], self.session["readbacks"][2] = self.session["readbacks"][2], self.session["readbacks"][1]
        self.link_session()
        self.refuse("READBACK")

    def test_wrong_owner_job_is_not_a_supplied_current_identity(self):
        self.fixture()
        value = O.parse((self.path / "owner.json").read_bytes())
        value["job"] = "9" * 32
        self.rebind_original("owner.json", Q.encoded(value))
        self.refuse("OWNER_RECORD")

    def test_coherent_but_nonfixed_allowed_git_command_refuses(self):
        self.fixture()
        row = self.session["queries"][0]
        parent = "query-" + row["id"]
        start = O.parse((self.path / parent / "start.json").read_bytes())
        argv = row["argv"][:7] + ["rev-parse", "--is-shallow-repository"]
        row["argv"] = start["argv"] = argv
        row["ownership"]["launches"][0].update(requestedArgv=argv, resolvedArgv=argv)
        self.rebind_original(parent + "/start.json", Q.encoded(start))
        self.rebind_original(parent + "/result.json", Q.encoded(row))
        self.refuse("FIXED_SEQUENCE")

    def test_boolean_exit_is_not_known_zero(self):
        self.fixture()
        row = self.session["queries"][0]
        row["waitExitCode"] = False
        self.rebind_original("query-" + row["id"] + "/result.json", Q.encoded(row))
        self.refuse("QUERY_ORIGINAL_RESULT")

    def test_baseline_translation_preserves_strict_integer_grammar(self):
        self.fixture()
        name = "query-" + self.session["queries"][0]["id"] + "/baseline.json"
        value = O.parse((self.path / name).read_bytes())
        value["baseline"] = [[True, 22]]
        self.rebind_original(name, Q.encoded(value))
        self.refuse("BASELINE")

    def test_native_leader_must_be_unique_original_identity(self):
        self.fixture()
        row = self.session["queries"][0]
        row["ownership"]["startedIdentities"] *= 2
        self.rebind_original("query-" + row["id"] + "/result.json", Q.encoded(row))
        self.refuse("NATIVE_LEADER")

    def test_native_leader_cannot_preexist_in_original_baseline(self):
        self.fixture()
        row = self.session["queries"][0]
        name = "query-" + row["id"] + "/baseline.json"
        value = O.parse((self.path / name).read_bytes())
        value["baseline"] = [list(S.lifetime(row["ownership"]["startedIdentities"][0], "linux-x64"))]
        self.rebind_original(name, Q.encoded(value))
        self.refuse("PREEXISTING_LEADER")

    def test_empty_claimed_ancestor_context_is_not_no_context(self):
        self.fixture()
        value = O.parse((self.path / "owner.json").read_bytes())
        value["ancestorContext"] = {name: "" for name in Q._CONTEXT}
        self.rebind_original("owner.json", Q.encoded(value))
        self.refuse("ANCESTOR_CONTEXT")

    def ancestor_fixture(self):
        ancestors = Q.processes.ownership_environment({}, "a" * 32, "b" * 32,
            str(self.base / "model-ancestor-state"), str(self.base / "model-ancestor-home"))
        self.stack.enter_context(patch.dict(os.environ, ancestors))
        self.fixture()
        return ancestors

    def test_complete_source_preserves_bound_ancestor_context(self):
        ancestors = self.ancestor_fixture()
        _raw, records, _side = self.read()
        self.assertEqual(O.parse(dict(records)["owner.json"])["ancestorContext"], ancestors)

    def test_full_ancestor_context_requires_ascii_and_matching_last_domain(self):
        self.ancestor_fixture()
        original = O.parse((self.path / "owner.json").read_bytes())
        for field, changed in ((Q.processes.DOMAINS_ENV, original["ancestorContext"][Q.processes.DOMAINS_ENV] + "\u00a0"),
                (Q.processes.JOB_ENV, "c" * 32), (Q.processes.STATE_ENV, "MODEL_WRONG_STATE"),
                ("GRADLE_USER_HOME", "MODEL_WRONG_HOME")):
            with self.subTest(field=field):
                value = {**original, "ancestorContext": {**original["ancestorContext"], field: changed}}
                self.rebind_original("owner.json", Q.encoded(value))
                self.refuse("ANCESTOR_CONTEXT")
                self.reset_model_failure()

    def windows_record_model(self):
        self.fixture()
        row = self.session["queries"][0]
        parent = self.path / ("query-" + row["id"])
        contents = {name: (parent / name).read_bytes() for name in
            ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json")}
        value = O.parse((self.path / "owner.json").read_bytes())
        value["nativeRole"] = "windows-x64"
        start = O.parse(contents["start.json"])
        start["environment"]["SYSTEMROOT"] = "MODEL_ONLY_WINDOWS_ROOT"
        contents["start.json"] = Q.encoded(start)
        contents["baseline.json"] = Q.encoded({"nativeRole": "windows-x64", "baseline": None, "kernelJob": True})
        ownership = row["ownership"]
        ownership.pop("discoveryReconciliations")
        ownership.update(backend=S.BACKENDS["windows-x64"], scope="kernel-job-no-breakaway-kill-on-close")
        leader = ownership["startedIdentities"][0]
        ownership["startedIdentities"] = [{"pid": leader["pid"], "creationFileTime": 123,
            "jobAssignedBeforeResume": True}]
        launch = ownership["launches"][0]
        launch.update(api="CreateProcessW", batch=False, applicationName=row["argv"][0],
            commandLine=S.subprocess.list2cmdline(row["argv"]), resumed=True, jobAssignedBeforeResume=True,
            outputMode="caller-owned-native-files", resourceCleanup=[{"phase": "launch-temporary",
                "resource": name, "status": "RETIRED"} for name in
                ("startup-attributes", "launch-handle-0", "launch-handle-1", "launch-handle-2", "primary-thread")])
        for name, capture in row["outputs"].items():
            row["outputs"][name] = {"identity": [17, "1" * 32], "is_directory": False, "size": capture["size"],
                "links": 1, "attributes": 0, "creation_100ns": 123, "modified_100ns": 124, "change_100ns": 125,
                "owner_sid": "S-1-5-21-1-2-3-1001", "protected_dacl": True,
                "bytes": capture["bytes"], "sha256": capture["sha256"]}
        contents["result.json"] = Q.encoded(row)
        return row, contents, value

    def test_windows_record_model_requires_native_launch_and_private_file_metadata(self):
        row, contents, value = self.windows_record_model()
        N._initial_query_record(row, contents, value)  # Pure supplied grammar; no Windows API.
        row["outputs"]["stdout"]["is_directory"] = True
        contents["result.json"] = Q.encoded(row)
        with self.assertRaisesRegex(ValueError, "CAPTURE_METADATA"):
            N._initial_query_record(row, contents, value)

    def test_windows_record_model_missing_temporary_retirement_refuses(self):
        row, contents, value = self.windows_record_model()
        row["ownership"]["launches"][0]["resourceCleanup"].pop()
        contents["result.json"] = Q.encoded(row)
        with self.assertRaisesRegex(ValueError, "WINDOWS_TEMPORARIES"):
            N._initial_query_record(row, contents, value)

    def test_source_sidecar_is_mandatory_and_exact_not_a_session_row(self):
        self.fixture()
        self.refuse("SIDECAR_INPUT", expected_source_return_raw=None)
        self.reset_model_failure()
        self.refuse("SIDECAR_BYTES|BYTES_CHANGED", expected_source_return_raw=self.sidecar.replace(b"400000000000", b"399000000000"))
        self.reset_model_failure()
        self.session["readbacks"].append({"parent": str(self.path), "name": "source-return.json", "maximum": len(self.sidecar),
            "bytes": len(self.sidecar), "sha256": O.digest(self.sidecar), "retirement": "KNOWN", "result": "RETAINED"})
        self.link_session()
        self.refuse("READBACK_ROSTER")

    def test_acquisition_forbids_caller_supplied_sidecar(self):
        self.fixture(acquisition=True)
        self.refuse("SIDECAR_INPUT", expected_source_return_raw=b"{}\n")
        self.assertEqual(self.reads, [])

    def test_sidecar_hash_edges_are_not_self_authorization(self):
        self.fixture()
        self.side["originalsSha256"]["base_policy_entry"] = "0" * 64
        self.sidecar = O.encoded(self.side)
        self.write("source-return.json", self.sidecar)
        self.refuse("SIDECAR")

    def test_wrong_external_session_hash_refuses_before_suboriginals(self):
        self.fixture()
        self.refuse("SESSION_HASH", expected_session_sha256="f" * 64)
        self.assertEqual([name for _parent, name in self.reads], ["session-result.json"])

    def test_serialized_traversal_does_not_choose_a_file(self):
        self.fixture()
        self.session["readbacks"][0]["parent"] = str(self.path / ".." / "private-not-allowed")
        self.link_session()
        self.refuse("READBACK")
        self.assertEqual([name for _parent, name in self.reads], ["session-result.json"])

    def test_foreign_run_and_nonfixed_source_path_refuse(self):
        foreign = self.runner_temp / "p2pkit-initial-recipient-302-1-worker/source-before"
        self.fixture(location=foreign)
        self.refuse("LAYOUT")
        self.assertEqual(self.reads, [])

    def test_missing_extra_and_case_alias_rosters_refuse(self):
        self.fixture()
        for name in ("unexpected", "OWNER.JSON"):
            self.write(name, b"MODEL_EXTRA")
            self.refuse("DIRECTORY_LIMIT|DIRECTORY_ROSTER")
            (self.path / name).unlink()
            self.reset_model_failure()
        (self.path / "query-home").rmdir()
        self.refuse("DIRECTORY_ROSTER")

    def test_query_home_must_be_empty(self):
        self.fixture()
        self.write("query-home/unexpected", b"MODEL_EXTRA")
        self.refuse("DIRECTORY_ROSTER")

    def test_nested_query_roster_is_exactly_five(self):
        self.fixture()
        self.write("query-" + self.session["queries"][0]["id"] + "/extra", b"MODEL_EXTRA")
        self.refuse("DIRECTORY_LIMIT|DIRECTORY_ROSTER")

    def test_registered_root_directory_replacement_refuses(self):
        self.fixture()
        self.path.rename(self.path.with_name("displaced-model-root"))
        self.path.mkdir(mode=0o700)
        self.refuse("QUERY_DIRECTORY_REPLACED")
        self.assertEqual(self.reads, [])

    def test_symlink_and_hardlink_originals_are_not_plain_private_files(self):
        self.fixture()
        target = self.path / "candidate_policy_raw.bin"
        raw = target.read_bytes()
        target.unlink()
        origin = self.base / "model-original"
        origin.write_bytes(raw)
        origin.chmod(0o600)
        target.symlink_to(origin)
        with self.assertRaises(OSError):
            self.read()
        target.unlink()
        self.reset_model_failure()
        os.link(origin, target)
        self.refuse("QUERY_PRIVATE_FILE_CHANGED")

    def test_declared_total_excess_refuses_before_child_opens(self):
        self.fixture(acquisition=True)
        for row in self.session["readbacks"]:
            row["bytes"] = row["maximum"] = Q.MAX_RECEIPT_BYTES
        for row in self.session["queries"]:
            row["stdoutLimit"] = row["stderrLimit"] = Q.MAX_RECEIPT_BYTES
        self.link_session()
        self.refuse("SESSION_LIMIT")
        self.assertEqual(self.owner.resources, list(self.original_rows))
        self.assertEqual([name for _parent, name in self.reads], ["session-result.json"])

    def test_owner_fence_and_borrowed_prefix_replacements_refuse(self):
        self.fixture()
        def change():
            self.owner.fence = object()
        self.cancel_hook = change
        self.refuse("OWNER_CHANGED")

    def test_identical_borrowed_prefix_row_copy_is_not_the_original(self):
        self.fixture()
        def change():
            self.owner.resources[0] = dict(self.owner.resources[0])
        self.cancel_hook = change
        self.refuse("ROSTER_CHANGED")
        self.assertTrue(self.owner.unknown)

    def test_falsey_original_failure_is_retained(self):
        self.fixture()
        original = FalseyFailure("MODELED_FALSEY_FIRST")
        self.owner.error("model-before-reader", original)
        with self.assertRaises(FalseyFailure) as raised:
            self.read()
        self.assertIs(raised.exception, original)
        self.assertEqual(self.reads, [])

    def test_hash_time_local_expiry_cannot_return_success(self):
        self.fixture()
        digest = O.digest
        def late(raw):
            result = digest(raw)
            if raw == self.policy:
                self.local_end = time.monotonic() - 1
            return result
        with patch.object(O, "digest", side_effect=late), self.assertRaises((ValueError, RuntimeError)):
            self.read()
        self.assertIsNotNone(self.owner.original)

    def test_final_callback_expiry_spends_the_original_interval(self):
        self.fixture()
        def expire():
            if sum(name == "session-result.json" for _parent, name in self.reads) == 2:
                self.local_end = time.monotonic() - 1
        self.cancel_hook = expire
        with self.assertRaises((ValueError, RuntimeError)):
            self.read()
        self.assertFalse(self.owner.closed)

    def test_postallocation_erasure_keeps_the_actual_raw_resource(self):
        self.fixture()
        self.assertNotIn("end", self.owner.__dict__)
        original = FalseyFailure("MODELED_POSTALLOCATION")
        saved = []
        def erase():
            if len(self.owner.resources) > len(self.original_rows):
                saved.append(self.owner.resources[-1]["owner"])
                self.owner.resources.pop()
                raise original
        self.deadline_hook = erase
        with self.assertRaises(FalseyFailure) as raised:
            self.read()
        self.assertIs(raised.exception, original)
        self.assertEqual(len(saved), 1)
        self.assertNotIn("end", self.owner.__dict__)
        self.assertTrue(self.owner.unknown)
        self.assertTrue(any(type(item) is tuple and any(resource is saved[0] for resource in item[2]) for item in S.QUARANTINE))
        self.held.extend(saved)

    def test_allocation_restores_original_instance_end_slot(self):
        self.fixture()
        original = self.owner.end
        self.owner.end = original
        self.read()
        self.assertIs(self.owner.__dict__["end"], original)

    def test_postallocation_replaced_end_is_not_silently_restored(self):
        self.fixture()
        replacement = lambda **_kwargs: self.local_end
        def change():
            if len(self.owner.resources) > len(self.original_rows):
                self.owner.end = replacement
        self.deadline_hook = change
        self.refuse("END_CHANGED")
        self.assertIs(self.owner.__dict__["end"], replacement)
        self.assertTrue(self.owner.unknown)
        self.assertTrue(S.QUARANTINE)

    def test_postallocation_replaced_end_preserves_falsey_first_error(self):
        self.fixture()
        original = FalseyFailure("MODELED_END_REPLACEMENT_FIRST_ERROR")
        replacement = lambda **_kwargs: self.local_end
        def change():
            if len(self.owner.resources) > len(self.original_rows):
                self.owner.end = replacement
                raise original
        self.deadline_hook = change
        with self.assertRaises(FalseyFailure) as raised:
            self.read()
        self.assertIs(raised.exception, original)
        self.assertIs(self.owner.__dict__["end"], replacement)
        self.assertTrue(self.owner.unknown)
        self.assertTrue(S.QUARANTINE)

    def test_postallocation_equal_row_copy_is_not_the_original(self):
        self.fixture()
        saved = []
        def replace_row():
            if not saved and len(self.owner.resources) > len(self.original_rows):
                saved.append(self.owner.resources[-1])
                self.owner.resources[-1] = dict(saved[0])
        self.deadline_hook = replace_row
        self.refuse("ROSTER_CHANGED")
        self.assertEqual(len(saved), 1)
        self.assertTrue(self.owner.unknown)
        self.assertIsNot(self.owner.resources[-1], saved[0])
        self.assertTrue(any(type(item) is tuple and any(resource is saved[0]["owner"] for resource in item[2])
            for item in S.QUARANTINE))

    def test_inplace_root_path_alias_is_not_an_immutable_pin(self):
        self.fixture()
        path = self.directory.path
        original = str(path)
        changed = False
        def change_after_session_reread():
            nonlocal changed
            if not changed and sum(name == "session-result.json" for _parent, name in self.reads) == 2:
                # Same actual directory, but the original Path text has changed;
                # comparing two aliases of this object cannot witness that.
                path._str = original + "/."
                changed = True
        self.read_hook = change_after_session_reread
        try:
            self.refuse("HISTORY_CHANGED|DIRECTORY_CHANGED")
            self.assertTrue(changed)
        finally:
            path._str = original  # Fixture cleanup only, never a production recovery.

    def test_equal_replacement_path_cannot_disconnect_original_history_pin(self):
        self.fixture()
        original = self.directory.path
        changed = False
        def change_after_session_reread():
            nonlocal changed
            if not changed and sum(name == "session-result.json" for _parent, name in self.reads) == 2:
                replacement = Path(str(original))
                self.assertIsNot(replacement, original)
                self.assertEqual(replacement, original)
                replacement._str = str(original) + "/."
                self.directory.path = replacement
                changed = True
        self.read_hook = change_after_session_reread
        try:
            self.refuse("HISTORY_CHANGED|DIRECTORY_CHANGED")
            self.assertTrue(changed)
        finally:
            self.directory.path = original  # Fixture cleanup only.

    def test_delegated_reader_close_unknown_keeps_original_and_resources(self):
        self.fixture()
        original = FalseyFailure("MODELED_READER_CLOSE_UNKNOWN")
        read = Q._PosixDirectory.read_bytes
        def fail(directory, name, **kwargs):
            if name == "owner.json":
                raise original
            return read(directory, name, **kwargs)
        with patch.object(Q._PosixDirectory, "read_bytes", new=fail), self.assertRaises(FalseyFailure) as raised:
            self.read()
        self.assertIs(raised.exception, original)
        self.assertTrue(self.owner.unknown)
        self.assertEqual(len(self.owner.resources), len(self.original_rows) + 13)
        self.assertTrue(S.QUARANTINE)

    def test_reread_changed_bytes_refuse(self):
        self.fixture()
        changed = False
        def mutate():
            nonlocal changed
            if not changed and self.reads and self.reads[-1][1] == "source-return.json":
                self.write("candidate_policy_raw.bin", b"X" * len(self.policy))
                changed = True
        self.read_hook = mutate
        self.refuse("REREAD_CHANGED")


if __name__ == "__main__":
    unittest.main()
