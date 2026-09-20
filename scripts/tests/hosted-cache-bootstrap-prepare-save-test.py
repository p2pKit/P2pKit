#!/usr/bin/env python3
"""Selected-source save-transition controls, not a hosted or provider execution.

Owner, admission composition, package/sidecar checks, bound-file reader, plan,
stage and inventory validators execute. Native admission, source acquisition,
allocation rederivation, elapsed clocks and files are explicit memory models.
The reader's opaque upstream fixtures are not original producer evidence.
No full runner import, real private files, network, Gradle or provider is used.
"""
import argparse
from contextlib import redirect_stderr
from copy import deepcopy
import dataclasses
from dataclasses import dataclass, replace
import io
import json
import math
from pathlib import Path
import runpy
from types import SimpleNamespace as NS
from typing import NamedTuple, Tuple
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
prior = runpy.run_path(str(ROOT / "tests/hosted-cache-bootstrap-save-reader-test.py"), run_name="reader_models")
selected, require, Refusal, FalseyFailure = (prior[name] for name in ("selected", "require", "Refusal", "FalseyFailure"))
encoded, digest, SECOND, LIMIT = (prior[name] for name in ("encoded", "digest", "SECOND", "LIMIT"))
CODE = selected("run-hosted-cache-bootstrap.py", {"_producer_return_record", "_save_original_inventory",
    "prepare_save", "admit", "load_admission", "cancellation", "child_environment", "IDENTITY_ENV",
    "public_result", "guarded", "main"})
FILES = selected("hosted_dependency_seed_files.py", {"MIB", "FILE_LIMIT", "TOTAL_LIMIT", "BLOCK", "NAMES_LIMIT",
    "VERSION_LIMIT", "MEMBER_LIMIT", "RECEIPT_LIMIT", "HARD_SECONDS", "SOFT_SECONDS", "WRAPPER", "POLICY", "KNOWN",
    "_identity", "_file_binding", "_info_binding", "policy", "_validate_inventory", "stage_record", "validate_stage",
    "validate_retained_stage", "validate_cohort", "_bootstrap_cohort"})
PLAN = selected("hosted_dependency_cache.py", {"_inputs", "make_plan", "validate_plan", "_save_roster"})
BOUND_READER = selected("hosted_cache_bootstrap_staging.py", {"_read"})
DIRECTED = selected("hosted_full_job_budget.py", {"_directed_deadline"})
AUTHORITY = selected("hosted_dependency_seed.py", {"Artifact", "Allowlist"})
ADMISSION = selected("hosted_test_identity.py", {"Admission"})


def throw(error):
    raise error


@dataclass(frozen=True)
class Info:
    identity: tuple
    size: int = 0
    stamp: int = 1

    def as_dict(self):
        return {"identity": list(self.identity), "size": self.size, "modeledStamp": self.stamp}


class World(prior["World"]):
    def __init__(self, profile="desktop", role="linux-x64"):
        super().__init__(profile, role)
        self.events, self.hooks, self.owners, self.handles, self.native_pairs = [], {}, [], [], []
        self.native_expected, self.source_calls, self.proposal_calls = [], [], []
        self.original_path = self.session.parent.with_name(self.session.parent.name.removesuffix("-productive"))
        self.save_path = self.original_path.with_name(self.original_path.name + "-save")
        self.container_path = self.files.stage_path(self.session, profile, role, admitted_raw=self.admitted.record)
        self.ids = lambda number: (1, format(number, "032x") if role == "windows-x64" else number)
        self.env = {"RUNNER_NAME": "modeled-runner", "P2PKIT_BOOTSTRAP_PRODUCER_OUTCOME": "success"}
        self.event = b"modeled-original-dispatch"
        self.admission["policy"] = {"fingerprint": "F" * 40, "keySha256": "1" * 64, "expiresAt": 1}
        admission_ns = {"dataclasses": dataclasses, "__name__": __name__}
        exec(ADMISSION, admission_ns)
        self.admitted = admission_ns["Admission"](encoded(self.admission), self.event,
            b"modeled-policy-not-authority", b"modeled-key-not-a-key", "F" * 40, "1" * 64, 1)
        self.origin.admitted_value = lambda value: deepcopy(self.admission) if value == self.admitted else None
        self.origin.WORK_SECONDS, self.origin.PRELUDE_SECONDS = 75, 120
        directed = {"require": require, "math": math, "NS": SECOND}
        exec(DIRECTED, directed)
        self.origin.wire = NS(TOKEN_ENV="P2PKIT_JOB_TIME_TOKEN", _directed_deadline=directed["_directed_deadline"])
        self.origin.clocks.observe = self.observe
        authority = {"dataclass": dataclass, "NamedTuple": NamedTuple, "Tuple": Tuple, "__name__": __name__}
        exec(AUTHORITY, authority)
        authority["FILESTORE_PREFIX"] = "caches/modules-2/files-2.1"
        self.compiled = authority["Allowlist"]((authority["Artifact"]("fixture", "alpha", "1", "alpha.jar", "a" * 64),
            authority["Artifact"]("fixture", "beta", "1", "beta.jar", "b" * 64)), "c" * 64, "d" * 64, 2, 10)
        file_ns = self.files.__dict__
        file_ns.update(authority=NS(**authority), re=prior["re"], digest=digest, record=self.origin.parse,
            bootstrap=NS(cache_cohort=lambda raw: (profile, role), ordinary=NS(AdmissionError=Refusal)), SeedError=Refusal)
        exec(FILES, file_ns)
        cache_ns = self.staging.cache.__dict__
        cache_ns.update(Path=Path)
        exec(PLAN, cache_ns)
        bound_ns = {"files": self.files, "require": require}
        exec(BOUND_READER, bound_ns)
        self.staging._read = bound_ns["_read"]
        self.inputs = {"files": {name: "e" * 64 for name in self.files.INPUTS},
            "allowlistSha256": self.compiled.authority_sha256, "artifacts": 2, "components": 2, "policy": self.files.policy()}
        self.inputs["files"][self.files.INPUTS[0]] = self.compiled.source_sha256
        self.stage = self.files.stage_record(self.admitted.record, profile, role, self.container_path,
                                             Info(self.ids(20)), Info(self.ids(21)), self.inputs)
        self.stage_raw = encoded(self.stage)
        self.stage_info = Info(self.ids(22), len(self.stage_raw))
        self.stage_binding = self.files._info_binding(self.stage_info)
        self.plan = self.staging.cache.make_plan(self.admitted.record, self.stage_raw, self.compiled, self.inputs,
            session=self.session, profile=profile, role=role, mode="bootstrap")
        self.proposal.update(phaseFencesNs={"producer-owner-return": 1050 * SECOND,
            "save-set-before": 1060 * SECOND, "save-transition": 1100 * SECOND, "provider-save": 1300 * SECOND},
            proposedJobEndNs=1400 * SECOND)
        self.binding.update(admissionSha256=digest(self.admitted.record), proposalSha256=digest(encoded(self.proposal)),
            invocation="7" * 64, runnerName=self.env["RUNNER_NAME"], propertiesSha256="9" * 64,
            initializerDirectories={"session": list(self.ids(10)), "gradle-home": list(self.ids(23))})
        self.responses = {name: encoded({"modeledOriginalService": name}) for name in ("attempt", "jobs")}
        clock = self.origin.clock_value(self.clock)
        common = {"schema": 1, "binding": self.binding, "plan": self.plan, "predecessors": {"modeled": "staged"},
            "completed": True, "retirement": "KNOWN", "errors": [], "nextPhaseAuthority": False,
            "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL"}
        path = "/".join((*self.files.PREFIX, "fixture", "alpha", "1", "f" * 40, "alpha.jar"))
        exported = {**common, "scope": self.leaf_scopes["export-leaf.json"], "status": "KNOWN_PARTIAL",
            "sourceIdentity": list(self.ids(23)), "destinationIdentity": list(self.ids(21)),
            "home": self.binding["home"], "restoreHome": self.plan["restoreHome"], "propertiesSha256": "9" * 64,
            "policy": self.files.policy(), "window": {"finishedNs": 920 * SECOND},
            "counts": {"prehashBytes": 3, "outputBytes": 3, "sourceNames": 8, "destinationMembers": 8,
                       "sha256Rejected": 0, "layoutRejected": 0},
            "admitted": [{"index": 0, "path": path, "size": 3, "sha256": "a" * 64, "sha1": "f" * 40,
                "source": self.files._info_binding(Info(self.ids(80), 3)),
                "destination": self.files._info_binding(Info(self.ids(81), 3))}],
            "misses": [{"index": 1, "reason": "ABSENT", "rejected": 0}],
            "exportInputs": {"modeled": "not-source-acquisition"}}
        # The number includes every prefix/file member, not the root directory.
        exported["counts"]["destinationMembers"] = len(path.split("/"))
        directories, chosen = self.staging.cache._save_roster(exported)
        frozen = {**common, "scope": self.leaf_scopes["before-leaf.json"], "phase": "before-save",
            "beforeSaveSha256": None, "status": "KNOWN_FROZEN", "atomicSnapshot": False,
            "exportSha256": digest(encoded(exported)), "stagingFile": self.stage_binding,
            "container": {"binding": self.files._info_binding(Info(self.ids(20))),
                          "names": ["restore-home", "staging.json"]},
            "files": [path], "directories": [{"path": "/".join(parts), "names": list(names),
                "binding": self.files._info_binding(Info(self.ids(21 if not parts else 40 + number)))}
                for number, (parts, names) in enumerate(sorted(directories.items()))],
            "counts": {"hashedBytes": 3, "verifiedFiles": len(chosen), "members": len(path.split("/"))},
            "saveSetInputs": {"modeled": "not-source-acquisition"},
            "window": {"phase": "save-set-before", "clock": clock, "firstNs": 940 * SECOND,
                "hardEndNs": 1060 * SECOND, "softEndNs": 1030 * SECOND, "lastNewWorkNs": 950 * SECOND,
                "finishedNs": 970 * SECOND, "predecessorCheckedNs": 935 * SECOND,
                "predecessorSha256": "0" * 64, "proposalSha256": digest(encoded(self.proposal))}}
        self.blobs.update({"allocation-proposal.json": encoded(self.proposal), "export-leaf.json": encoded(exported),
                           "before-leaf.json": encoded(frozen)})
        for name in ("stage-leaf.json", "seed-leaf.json"):
            self.blobs[name] = encoded({"scope": self.leaf_scopes[name], "binding": self.binding, "plan": self.plan})
        for name, first, closed, soft, hard in (("export-parent.json", 820, 930, 910, 940),
                                               ("before-parent.json", 940, 980, 1030, 1060)):
            value = json.loads(self.blobs[name])
            value.update(firstNs=first * SECOND, closedNs=closed * SECOND, softEndNs=soft * SECOND, hardEndNs=hard * SECOND)
            self.blobs[name] = encoded(value)
        self.value.update(plan=self.plan, planSha256=digest(encoded(self.plan)), binding=self.binding,
                          **{name: self.admission[name] for name in ("source", "github", "selection", "cacheCohort")})
        self.value["references"] = {}
        self.data = {}
        self.add_directory(self.session, 10)
        self.add_directory(self.path, 11)["files"] = self.blobs
        service = self.add_directory(self.original_path / "service", 12)
        service["files"] = {name + ".json": raw for name, raw in self.responses.items()}
        container = self.add_directory(self.container_path, 20)
        container["files"]["staging.json"] = self.stage_raw
        container["infos"]["staging.json"] = self.stage_info
        self.add_directory(self.container_path / "restore-home", 21)
        for name, raw in self.responses.items():
            self.reference("service/" + name, self.original_path / "service", name + ".json", raw)
        self.reference("staging/staging", self.container_path, "staging.json", self.stage_raw, self.stage_binding)
        self.returned = {"schema": 1, "scope": "BOOTSTRAP_HANDOFF_FUNCTION_RETURN_PENDING_COMMAND_V1",
            "handoffSha256": "0" * 64, "handoffDirectory": str(self.path), "handoffDirectoryIdentity": list(self.ids(11)),
            "initializerIdentity": list(self.ids(10)), "clock": clock, "firstNs": 990 * SECOND, "hardEndNs": 1035 * SECOND,
            "handoffReturnedNs": 995 * SECOND, "handoffReturnedLocal": 5000.0,
            "observedAfterReturnNs": 998 * SECOND, "observedAfterReturnLocal": 5001.0,
            "observationScope": "HANDOFF_FUNCTION_RETURN_ONLY", "recordWriterReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE",
            "producerStepOutcome": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        self.relink()
        world = self

        class Directory:
            def __init__(self, path):
                self.path, self.node, self.closes = path, world.data[path], 0
                self.identity = self.node["identity"]
                world.handles.append(self)

            def verify(self):
                world.hit("verify:" + self.path.name)
                require(self.closes == 0 and self.identity == self.node["identity"], "MODEL_DIRECTORY_CHANGED")
                return Info(self.identity)

            def read_bytes(self, name, *, max_bytes, deadline):
                self.verify()
                world.hit("read:" + self.path.name + "/" + name)
                world.reads.append((self.path, name, max_bytes))
                raw = self.node["files"][name]
                require(world.local < deadline and len(raw) <= max_bytes, "MODEL_READ_BOUNDARY")
                return raw

            def names(self, *, max_names, deadline):
                self.verify()
                require(world.local < deadline and len(self.node["files"]) <= max_names, "MODEL_NAMES_BOUNDARY")
                return tuple(sorted(self.node["files"]))

            def open_directory(self, name, *, deadline):
                require(world.local < deadline, "MODEL_OPEN_BOUNDARY")
                return world.open_directory(self.path / name)

            def open_file(self, name, *, max_bytes, deadline):
                self.verify()
                world.hit("open-file:" + name)
                require(world.local < deadline and len(self.node["files"][name]) <= max_bytes, "MODEL_FILE_BOUNDARY")
                return File(self, name, False)

            def create_file(self, name, *, max_bytes, deadline):
                self.verify()
                world.hit("create-file:" + name)
                require(name not in self.node["files"] and world.local < deadline, "MODEL_EXCLUSIVE_FILE")
                self.node["files"][name] = b""
                self.node["infos"][name] = Info(world.ids(200 + len(world.handles)))
                return File(self, name, True)

            def close(self):
                self.closes += 1
                world.hit("close-dir:" + self.path.name)

        class File:
            def __init__(self, parent, name, writer):
                self.parent, self.name, self.writer, self.position, self.closes = parent, name, writer, 0, 0
                self.initial_info = parent.node["infos"][name]
                world.handles.append(self)

            def read(self, count):
                world.hit("file-read:" + self.name)
                raw = self.parent.node["files"][self.name]
                value = raw[self.position:self.position + count]
                self.position += len(value)
                return value

            def write(self, raw):
                world.hit("file-write:" + self.name)
                self.parent.node["files"][self.name] += raw
                return len(raw)

            def sync(self):
                world.hit("file-sync:" + self.name)

            def verify(self):
                world.hit("file-verify:" + self.name)
                info = self.parent.node["infos"][self.name]
                return replace(info, size=len(self.parent.node["files"][self.name]))

            def close(self):
                self.closes += 1
                world.hit("close-file:" + self.name)

        class Listing:
            def __init__(self, path):
                self.path = path

            def __enter__(self):
                world.hit("list:" + self.path.name)
                return iter(NS(name=name) for name in world.data[self.path]["files"])

            def __exit__(self, *_args):
                pass

        class Supplier:
            def __init__(self, root, path, *, check_cancel, owner_deadlines):
                world.hit("native-create")
                require(root == world.namespace["ROOT"] and len(owner_deadlines) == 2 and
                        world.local < owner_deadlines[0] <= owner_deadlines[1], "MODEL_QUERY_OWNER_DEADLINES")
                self.path, self.unknown, self.check, self.closes = path, False, check_cancel, 0
                world.native_pairs.append(owner_deadlines)
                world.add_directory(path, 100 + len(world.native_pairs))

            def native_host_matches_actions(self):
                self.check()
                world.hit("native-host")

            def retain_admission(self, value):
                world.hit("native-retain")
                world.data[self.path]["files"].update({"admission.json": value.record,
                    "original-event.json": value.original_event, "original-policy.json": value.original_policy,
                    "recipient-public.asc": value.public_key, "session-result.json": encoded({"modeledSession": True})})

            def _finalize(self, error):
                self.closes += 1
                world.hit("native-close")

        self.Directory, self.Supplier = Directory, Supplier
        self.namespace.update(ROOT=Path("/modeled-source"), __doc__=__doc__, argparse=argparse,
            I=NS(Admission=admission_ns["Admission"]),
            os=NS(name="nt" if role == "windows-x64" else "posix", environ=self.env, defpath="/modeled/bin", scandir=Listing),
            windows=NS(open_private_directory=self.open_directory), host_inputs=self.host_inputs,
            allocation=NS(SCOPE=self.proposal_scope, validate_proposal=self.validate_proposal),
            signal=NS(SIGINT=2, SIGTERM=15, getsignal=lambda number: number, signal=self.signal),
            ACK_SCOPE="unused-service", RECIPIENT_ACK_SCOPE="unused-recipient", ACK_LIMIT=16384,
            sys=NS(stdout=NS(buffer=io.BytesIO()), stderr=io.StringIO(), flags=NS(isolated=1, no_site=1),
                   dont_write_bytecode=True))
        self.namespace["query"].__dict__.update(_PosixDirectory=self.open_directory,
            _new_private_directory=self.new_directory, NativeGitQueries=Supplier, _component=lambda name: None,
            _inherited_context=lambda: {})
        self.namespace["bootstrap"].admit = self.native_admit
        self.namespace["dependency_export"].STATUSES = ("KNOWN_EMPTY", "KNOWN_PARTIAL", "KNOWN_EXPORTED")
        self.namespace["diagnostics"]._exception_detail = lambda error: {
            "retirementUnknown": bool(getattr(error, "retirement_unknown", False)), "kind": type(error).__name__}
        self.files.source_inputs, self.files.private_root = self.source_inputs, self.open_directory
        self.namespace["time"] = NS(monotonic=self.monotonic)
        exec(CODE, self.namespace)
        owner_type = self.namespace["Owner"]
        original_init = owner_type.__init__

        def tracked_init(owner, *args, **kwargs):
            original_init(owner, *args, **kwargs)
            world.owners.append(owner)

        owner_type.__init__ = tracked_init

    def hit(self, name):
        self.events.append(name)
        if name in self.hooks:
            self.hooks[name]()

    def monotonic(self):
        self.hit("local")
        return self.local

    def observe(self):
        self.hit("raw")
        return self.clocks.Reading(self.clock, self.raw_ns)

    def add_directory(self, path, number):
        require(path not in self.data, "MODEL_EXCLUSIVE_DIRECTORY")
        node = {"identity": self.ids(number), "files": {}, "infos": {}}
        self.data[path] = node
        return node

    def open_directory(self, path):
        self.hit("open-dir:" + path.name)
        require(path in self.data, "MODEL_FIXED_DIRECTORY")
        return self.Directory(path)

    def new_directory(self, path):
        self.hit("new-dir:" + path.name)
        require(path == self.save_path, "MODEL_FIXED_SAVE_TARGET")
        self.add_directory(path, 30)
        return self.open_directory(path)

    def reference(self, label, path, name, raw, binding=None):
        self.value["references"][label] = {"directory": str(path), "directoryIdentity": list(self.data[path]["identity"]),
            "name": name, "maximumBytes": LIMIT, "bytes": len(raw), "sha256": digest(raw), "fileBinding": binding,
            "bindingScope": "ORIGINAL_FILE_BINDING" if binding is not None else
                            "ORIGINAL_DIRECTORY_AND_BYTES_OR_HASH_ONLY_NOT_FILE_IDENTITY"}

    def relink(self):
        parent = json.loads(self.blobs["export-parent.json"])
        parent["leafSha256"] = digest(self.blobs["export-leaf.json"])
        self.blobs["export-parent.json"] = encoded(parent)
        frozen = json.loads(self.blobs["before-leaf.json"])
        frozen["exportSha256"] = digest(self.blobs["export-leaf.json"])
        frozen["window"]["predecessorSha256"] = digest(self.blobs["export-parent.json"])
        self.blobs["before-leaf.json"] = encoded(frozen)
        parent = json.loads(self.blobs["before-parent.json"])
        parent.update(leafSha256=digest(self.blobs["before-leaf.json"]),
                      exportParentSha256=digest(self.blobs["export-parent.json"]))
        self.blobs["before-parent.json"] = encoded(parent)
        self.value["window"]["predecessorSha256"] = digest(self.blobs["before-parent.json"])
        self.refresh()
        self.returned["handoffSha256"] = self.expected
        self.return_bytes()
        self.env["P2PKIT_BOOTSTRAP_HANDOFF_SHA256"] = self.expected

    def return_bytes(self):
        self.data[self.session]["files"]["producer-function-return.json"] = encoded(self.returned)
        self.env["P2PKIT_BOOTSTRAP_PRODUCER_RETURN_SHA256"] = digest(encoded(self.returned))

    def proposal_bytes(self):
        self.blobs["allocation-proposal.json"] = encoded(self.proposal)
        self.binding["proposalSha256"] = digest(encoded(self.proposal))
        for name in ("export-leaf.json", "before-leaf.json", "stage-leaf.json", "seed-leaf.json"):
            value = json.loads(self.blobs[name])
            value["binding"] = self.binding
            if name == "before-leaf.json":
                value["window"]["proposalSha256"] = digest(encoded(self.proposal))
            self.blobs[name] = encoded(value)
        self.relink()

    def host_inputs(self, role):
        self.hit("host-inputs")
        require(role == self.clock.role, "MODEL_ACTUAL_ROLE")
        return self.selection, self.original_path, self.event

    def native_admit(self, root, *, query_runner, expected):
        self.native_expected.append(expected)
        self.hit("native-admit:" + str(len(self.native_expected)))
        require(root == self.namespace["ROOT"] and isinstance(query_runner, self.Supplier) and
                (expected is None or expected == self.admitted), "MODEL_NATIVE_ADMISSION_INPUTS")
        return self.admitted

    def source_inputs(self, owner, root, end, checked):
        self.source_calls.append((owner, root, end))
        self.hit("source-inputs")
        require(root == self.namespace["ROOT"] and self.local < end, "MODEL_SOURCE_INPUTS")
        checked()
        return self.inputs, self.compiled

    def validate_proposal(self, raw, admitted, responses, invocation, clock, runner):
        self.proposal_calls.append((raw, admitted, responses, invocation, clock, runner))
        self.hit("proposal")
        require(raw == encoded(self.proposal) and admitted == self.admitted and responses == self.responses and
                invocation == self.binding["invocation"] and clock == self.clock and runner == "modeled-runner",
                "MODEL_ORIGINAL_PROPOSAL_INPUTS")
        return deepcopy(self.proposal)

    def signal(self, number, value):
        self.hit("handler-install" if callable(value) else "handler-restore")

    def run(self, *, guarded=False, cancelled=None):
        return (self.namespace["guarded"](self.namespace["prepare_save"]) if guarded else
                self.namespace["prepare_save"]([] if cancelled is None else cancelled))

    def descriptor(self):
        return json.loads(self.data[self.save_path]["files"]["save-preparation.json"])

    def inventory(self):
        return self.namespace["_save_original_inventory"](self.value, self.blobs, self.compiled,
                                                          self.stage, self.stage_binding, self.proposal)


class PrepareModels(unittest.TestCase):
    def test_positive_runs_actual_owner_admission_reader_and_plan_composition(self):
        world = World()
        value, fence, cap = world.run()
        self.assertEqual(world.native_expected, [None, world.admitted])
        self.assertEqual(len(world.proposal_calls), 1)
        self.assertEqual(len(world.source_calls), 1)
        self.assertEqual(cap, 1030 * SECOND)
        self.assertEqual(value["savePreparationSha256"], digest(encoded(world.descriptor())))
        self.assertEqual(world.descriptor()["plan"], world.plan)
        self.assertEqual(world.descriptor()["providerWindow"], {"issuedNs": 1000 * SECOND,
            "hardEndNs": 1180 * SECOND, "actualProviderStart": "NOT_OBSERVED"})
        self.assertEqual(world.descriptor()["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertFalse(world.descriptor()["exportSaveAuthority"])
        self.assertTrue(all(handle.closes == 1 for handle in world.handles))
        self.assertTrue(all(owner.closed and not owner.unknown for owner in world.owners))
        self.assertTrue(all(a <= b < 130.0 for a, b in world.native_pairs))
        self.assertEqual(world.events.count("open-file:staging.json"), 2)
        self.assertTrue(all(row["label"] == "directory" for row in world.owners[0].resources
                            if getattr(row["owner"], "path", None) == world.container_path))
        self.assertIs(fence.clock, world.clock)

    def test_other_five_selections_are_data_models_not_platform_qualification(self):
        for profile, role in (("desktop", "windows-x64"), ("desktop", "macos-arm64"), ("desktop", "macos-x64"),
                              ("full", "macos-arm64"), ("full", "macos-x64")):
            with self.subTest(profile=profile, role=role):
                world = World(profile, role)
                self.assertEqual(world.run()[0]["scope"], "BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1")

    def test_original_outcome_and_token_are_denied_before_ownership_or_native(self):
        for outcome in (None, "", "failure", "cancelled", "skipped", "Success", {"conclusion": "success"}):
            world = World()
            world.env["P2PKIT_BOOTSTRAP_PRODUCER_OUTCOME"] = outcome
            with self.subTest(outcome=outcome), self.assertRaisesRegex(Refusal, "ORIGINAL_PRODUCER_OUTCOME"):
                world.run()
            self.assertEqual((world.owners, world.native_pairs), ([], []))
        world = World()
        world.env[world.origin.wire.TOKEN_ENV] = ""
        with self.assertRaisesRegex(Refusal, "ORIGINAL_PRODUCER_OUTCOME"):
            world.run()
        self.assertEqual(world.owners, [])

    def test_both_hashes_are_original_separate_lowercase_inputs(self):
        for name in ("P2PKIT_BOOTSTRAP_HANDOFF_SHA256", "P2PKIT_BOOTSTRAP_PRODUCER_RETURN_SHA256"):
            for value in (None, "", "a" * 63, "A" * 64, "g" * 64):
                world = World()
                world.env[name] = value
                with self.subTest(name=name, value=value), self.assertRaisesRegex(Refusal, "ORIGINAL_PRODUCER_HASHES"):
                    world.run()
                self.assertEqual(world.owners, [])
            world = World()
            world.env[name] = "0" * 64
            with self.assertRaisesRegex(Refusal, "(ORIGINAL_HANDOFF_HASH|PRODUCER_RETURN_HASH)"):
                world.run()
            self.assertEqual(world.native_pairs, [])

    def test_ambient_execution_and_git_overrides_are_still_refused(self):
        for key in ("JAVA_OPTS", "GRADLE_OPTS", "PYTHONPATH", "GIT_DIR", "LD_PRELOAD", "ORG_GRADLE_PROJECT_extra"):
            world = World()
            world.env[key] = "override"
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, "AMBIENT_"):
                world.run()
            self.assertEqual(world.owners, [])

    def test_initial_metadata_spends_the_same_first30(self):
        for clock in ("raw", "local"):
            world = World()
            world.hooks["host-inputs"] = lambda: setattr(world, "raw_ns" if clock == "raw" else "local",
                                                         1030 * SECOND if clock == "raw" else 130.0)
            with self.subTest(clock=clock), self.assertRaises(Refusal):
                world.run()
            self.assertEqual(world.native_pairs, [])

    def test_recorded_original_caps_deny_before_native_admission(self):
        for name in ("save-transition", "job"):
            world = World()
            value = deepcopy(world.proposal)
            if name == "job":
                value["proposedJobEndNs"] = 999 * SECOND
            else:
                value["phaseFencesNs"][name] = 1000 * SECOND
            world.blobs["allocation-proposal.json"] = encoded(value)
            world.relink()
            with self.subTest(name=name), self.assertRaisesRegex(Refusal, "TRANSITION_EXPIRED"):
                world.run()
            self.assertEqual(world.native_pairs, [])
            self.assertNotIn(world.save_path, world.data)

    def test_shorter_recorded_cap_never_renews_final_admission_or_return(self):
        world = World()
        world.proposal["phaseFencesNs"]["save-transition"] = 1010 * SECOND
        world.proposal_bytes()
        _value, _fence, cap = world.run()
        self.assertEqual(cap, 1010 * SECOND)
        self.assertTrue(all(a <= b < 110.0 for a, b in world.native_pairs))

    def test_late_final_native_return_cannot_obtain_new_allowance(self):
        world = World()
        world.hooks["native-admit:2"] = lambda: setattr(world, "raw_ns", 1030 * SECOND)
        with self.assertRaises(Refusal):
            world.run()
        self.assertNotIn("save-preparation.json", world.data[world.save_path]["files"])
        self.assertTrue(all(handle.closes == 1 for handle in world.handles))

    def test_missing_stale_or_selected_reference_paths_are_not_traversed(self):
        for field, value in (("directory", "/outside"), ("name", "../private"), ("directoryIdentity", [1, 900]),
                             ("sha256", "0" * 64), ("bytes", True), ("maximumBytes", LIMIT + 1)):
            world = World()
            world.value["references"]["service/attempt"][field] = value
            world.relink()
            with self.subTest(field=field), self.assertRaises(Refusal):
                world.run()
            self.assertTrue(all(str(path).startswith("/model/private/") for path, _name, _limit in world.reads))

    def test_service_bytes_and_proposal_rederivation_are_not_bypassed(self):
        for point in ("service", "proposal", "source"):
            world = World()
            if point == "service":
                world.data[world.original_path / "service"]["files"]["attempt.json"] = b"{}"
            else:
                world.hooks["proposal" if point == "proposal" else "source-inputs"] = lambda: throw(Refusal("ORIGINAL_REFUSAL"))
            with self.subTest(point=point), self.assertRaises(Refusal):
                world.run()
            self.assertNotIn("save-preparation.json", world.data[world.save_path]["files"])

    def test_rederived_current_allowlist_and_whole_plan_must_match(self):
        for change in (lambda world: world.inputs["files"].update({world.files.INPUTS[0]: "0" * 64}),
                       lambda world: setattr(world, "compiled", replace(world.compiled, source_sha256="0" * 64)),
                       lambda world: world.plan.update(stagingSha256="0" * 64)):
            world = World()
            change(world)
            world.value["planSha256"] = digest(encoded(world.plan))
            for name in ("export-leaf.json", "before-leaf.json", "stage-leaf.json", "seed-leaf.json"):
                value = json.loads(world.blobs[name])
                value["plan"] = world.plan
                world.blobs[name] = encoded(value)
            world.relink()
            with self.assertRaisesRegex(Refusal, "(STAGING_|CACHE_)"):
                world.run()

    def test_same_byte_staging_replacement_during_final_admission_refuses(self):
        world = World()
        def replace_file():
            world.data[world.container_path]["infos"]["staging.json"] = replace(world.stage_info, identity=world.ids(999))
        world.hooks["native-admit:2"] = replace_file
        with self.assertRaisesRegex(Refusal, "SEED_FILE_REPLACED"):
            world.run()
        self.assertTrue(all(handle.closes == 1 for handle in world.handles))

    def test_unknown_reader_quarantines_before_any_new_close(self):
        world = World()
        first = FalseyFailure()
        first.retirement_unknown = True
        world.hooks["file-read:staging.json"] = lambda: throw(first)
        with self.assertRaises(FalseyFailure) as caught:
            world.run()
        self.assertIs(caught.exception, first)
        reader = next(handle for handle in world.handles if getattr(handle, "name", None) == "staging.json")
        self.assertEqual(reader.closes, 0)
        self.assertTrue(world.owners[0].unknown)
        self.assertIn(world.owners[0], world.namespace["QUARANTINE"])

    def test_known_falsey_read_failure_preserves_cause_and_closes_once(self):
        world = World()
        first = FalseyFailure()
        world.hooks["file-read:staging.json"] = lambda: throw(first)
        with self.assertRaises(FalseyFailure) as caught:
            world.run()
        self.assertIs(caught.exception, first)
        self.assertTrue(all(handle.closes == 1 for handle in world.handles))
        self.assertFalse(world.owners[0].unknown)

    def test_expiry_during_known_reader_close_still_closes_all_known_owners(self):
        world = World()
        world.hooks["close-file:staging.json"] = lambda: setattr(world, "local", 130.0)
        with self.assertRaises(Refusal):
            world.run()
        self.assertTrue(all(handle.closes == 1 for handle in world.handles))
        self.assertFalse(world.owners[0].unknown)

    def test_exclusive_save_sibling_refuses_replay(self):
        world = World()
        world.run()
        before = len(world.native_pairs)
        with self.assertRaisesRegex(Refusal, "EXCLUSIVE_DIRECTORY"):
            world.run()
        self.assertEqual(len(world.native_pairs), before)

    def test_cancellation_and_prior_quarantine_cannot_start(self):
        world = World()
        with self.assertRaises(KeyboardInterrupt):
            world.run(cancelled=[2])
        self.assertEqual(world.owners, [])
        for name in ("owner", "query", "diagnostics"):
            world = World()
            queue = (world.namespace["QUARANTINE"] if name == "owner" else
                     world.namespace["query"].QUARANTINE if name == "query" else world.namespace["diagnostics"]._QUARANTINE)
            queue.append(object())
            with self.subTest(name=name), self.assertRaisesRegex(Refusal, "PRIOR_UNKNOWN"):
                world.run()
            self.assertEqual(world.owners, [])

    def test_mid_read_cancellation_is_forwarded_and_known_owners_close(self):
        world, cancelled = World(), []
        world.hooks["file-read:staging.json"] = lambda: cancelled.append(2)
        with self.assertRaises(KeyboardInterrupt):
            world.run(cancelled=cancelled)
        self.assertTrue(all(handle.closes == 1 for handle in world.handles))
        self.assertFalse(world.owners[0].unknown)

    def test_failed_final_directory_close_quarantines_without_a_success_return(self):
        world = World()
        first = FalseyFailure()
        world.hooks["close-dir:restore-home"] = lambda: throw(first)
        with self.assertRaises(FalseyFailure) as caught:
            world.run()
        self.assertIs(caught.exception, first)
        self.assertTrue(world.owners[0].unknown)
        self.assertIn(world.owners[0], world.namespace["QUARANTINE"])
        self.assertEqual(world.descriptor()["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertTrue(all(handle.closes <= 1 for handle in world.handles))

    def test_late_environment_change_and_clocks_backwards_refuse(self):
        for change in (lambda world: world.env.update(RUNNER_NAME="other"),
                       lambda world: world.env.update(P2PKIT_JOB_TIME_TOKEN="late"),
                       lambda world: setattr(world, "local", 99.0),
                       lambda world: setattr(world, "raw_ns", 999 * SECOND)):
            world = World()
            world.hooks["native-admit:2"] = lambda: change(world)
            with self.assertRaises(Refusal):
                world.run()

    def test_provider_descriptor_is_not_start_and_cannot_extend_original_cap(self):
        world = World()
        world.proposal["phaseFencesNs"]["provider-save"] = 1005 * SECOND
        world.proposal_bytes()
        world.run()
        self.assertEqual(world.descriptor()["providerWindow"], {"issuedNs": 1000 * SECOND,
            "hardEndNs": 1005 * SECOND, "actualProviderStart": "NOT_OBSERVED"})
        self.assertNotIn("timeoutMinutes", world.descriptor()["providerWindow"])

    def test_guarded_public_output_has_only_digest_and_nonacceptance(self):
        world = World()
        world.run(guarded=True)
        value = json.loads(world.namespace["sys"].stdout.buffer.getvalue())
        self.assertEqual(set(value), {"scope", "savePreparationSha256", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"})
        self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
        self.assertNotIn("GITHUB_OUTPUT", world.env)
        self.assertEqual(world.events.count("handler-restore"), 2)

    def test_late_output_flush_and_handler_restore_cannot_publish_success(self):
        for point in ("flush", "restore"):
            world = World()
            output = world.namespace["sys"].stdout.buffer
            if point == "flush":
                world.namespace["sys"].stdout.buffer = NS(write=output.write,
                    flush=lambda: setattr(world, "raw_ns", 1030 * SECOND))
            else:
                world.hooks["handler-restore"] = lambda: setattr(world, "local", 130.0)
            with self.subTest(point=point), self.assertRaises(Refusal):
                world.run(guarded=True)
            self.assertTrue(all(handle.closes == 1 for handle in world.handles))


class SuppliedDataModels(unittest.TestCase):
    def test_historical_local_is_only_ordered_within_its_original_process(self):
        world = World()
        self.assertGreater(world.returned["handoffReturnedLocal"], world.local)
        world.run()

    def test_sidecar_is_canonical_closed_and_cannot_claim_step_return_or_authority(self):
        for key, value in (("schema", True), ("extra", 1), ("recordWriterReturn", "success"),
                           ("producerStepOutcome", "success"), ("providerExecution", "PERFORMED"),
                           ("testAcceptance", "PASSED"), ("exportSaveAuthority", 0)):
            world = World()
            world.returned[key] = value
            world.return_bytes()
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, "PRODUCER_RETURN_RECORD"):
                world.run()
            self.assertEqual(world.native_pairs, [])

    def test_noncanonical_or_duplicate_sidecar_is_not_admitted_by_a_matching_digest(self):
        for mutate in (lambda raw: b" " + raw, lambda raw: raw.replace(b'"schema":1', b'"schema":1,"schema":1')):
            world = World()
            raw = mutate(encoded(world.returned))
            world.data[world.session]["files"]["producer-function-return.json"] = raw
            world.env["P2PKIT_BOOTSTRAP_PRODUCER_RETURN_SHA256"] = digest(raw)
            with self.assertRaises((Refusal, prior["parser"]["AdmissionError"])):
                world.run()
            self.assertEqual(world.native_pairs, [])

    def test_sidecar_exact_hash_paths_clock_and_raw_floor_are_checked(self):
        for key, value in (("handoffSha256", "0" * 64), ("handoffDirectory", "/other"),
                           ("initializerIdentity", [1, 999]), ("handoffDirectoryIdentity", [1, 998]),
                           ("clock", {}), ("firstNs", 989 * SECOND), ("hardEndNs", 1036 * SECOND),
                           ("observedAfterReturnNs", 1001 * SECOND), ("handoffReturnedNs", 999 * SECOND),
                           ("observedAfterReturnLocal", 4999.0), ("handoffReturnedLocal", -1.0)):
            world = World()
            world.returned[key] = value
            world.return_bytes()
            with self.subTest(key=key), self.assertRaises(Refusal):
                world.run()
            self.assertEqual(world.native_pairs, [])

    def test_before_counts_files_and_complete_directory_roster_are_checked(self):
        for change in (lambda value: value["counts"].update(verifiedFiles=0),
                       lambda value: value["counts"].update(members=True),
                       lambda value: value["counts"].update(hashedBytes=2),
                       lambda value: value.update(files=[]), lambda value: value["directories"].pop(),
                       lambda value: value["directories"][0].update(names=[]),
                       lambda value: value["directories"][1].update(path="../other")):
            world = World()
            world.change_blob("before-leaf.json", change)
            with self.assertRaisesRegex(Refusal, "(ROSTER|DIRECTORY_BINDING)"):
                world.inventory()

    def test_export_inventory_uses_actual_compiled_artifact_authority(self):
        for change in (lambda value: value["admitted"][0].update(sha256="0" * 64),
                       lambda value: value["admitted"][0].update(path="../outside"),
                       lambda value: value["counts"].update(outputBytes=4),
                       lambda value: value.update(misses=[]),
                       lambda value: value["admitted"][0].update(index=1)):
            world = World()
            world.change_blob("export-leaf.json", change)
            with self.assertRaisesRegex(Refusal, "SEED_"):
                world.inventory()

    def test_empty_unknown_incomplete_or_relabelled_export_freeze_refuses(self):
        for name in ("export-leaf.json", "before-leaf.json"):
            for key, value in (("completed", False), ("retirement", "UNKNOWN"), ("errors", ["failure"]),
                               ("exportSaveAuthority", True), ("status", "KNOWN_EMPTY")):
                world = World()
                world.change_blob(name, lambda leaf: leaf.update({key: value}))
                with self.subTest(name=name, key=key), self.assertRaises(Refusal):
                    world.inventory()

    def test_before_file_directory_container_aliases_and_original_stage_binding_refuse(self):
        for change in (lambda value: value["container"].update(names=[]),
                       lambda value: value["stagingFile"].update(stampSha256="0" * 64),
                       lambda value: value["directories"][0]["binding"].update(identity=[1, 999]),
                       lambda value: value["directories"][1].update(binding=value["directories"][0]["binding"]),
                       lambda value: value["directories"][1]["binding"].update(identity=[1, 81])):
            world = World()
            world.change_blob("before-leaf.json", change)
            with self.assertRaisesRegex(Refusal, "(CONTAINER_BINDING|DIRECTORY_BINDING|FILE_DIRECTORY_ALIAS)"):
                world.inventory()

    def test_original_before_window_must_link_export_parent_and_original_caps(self):
        for key, value in (("phase", "after-save"), ("clock", {}), ("proposalSha256", "0" * 64),
                           ("predecessorSha256", "0" * 64), ("hardEndNs", 1061 * SECOND),
                           ("softEndNs", 1031 * SECOND), ("finishedNs", 981 * SECOND),
                           ("predecessorCheckedNs", 919 * SECOND), ("lastNewWorkNs", True)):
            world = World()
            world.change_blob("before-leaf.json", lambda leaf: leaf["window"].update({key: value}))
            with self.subTest(key=key), self.assertRaises((Refusal, world.clocks.ClockError)):
                world.inventory()


class AdmissionAndCliModels(unittest.TestCase):
    def test_shared_admission_work_pair_only_shortens_to_later_final_sample(self):
        world = World()
        class Fence:
            clock = world.clock
            def now(self, **_kwargs):
                return world.raw_ns
            def deadline(self, maximum, **_kwargs):
                return 129.0 if maximum == 75 else 128.0
        fence = Fence()
        owner = world.namespace["Owner"](130.0, fence, first=world.first)
        world.namespace["admit"](owner, fence, world.save_path / "admission")
        owner.close()
        self.assertEqual(world.native_pairs, [(128.0, 128.0)])

    def test_fixed_cli_routes_only_prepare_save_without_caller_options(self):
        world = World()
        calls = []
        world.namespace["guarded"] = lambda operation: calls.append(operation)
        with patch("sys.argv", ["bootstrap", "prepare-save"]):
            self.assertEqual(world.namespace["main"](), 0)
        self.assertEqual(calls, [world.namespace["prepare_save"]])
        for option in ("--path", "--key", "--command", "--seconds", "--outcome", "--skip-admission"):
            with self.subTest(option=option), patch("sys.argv", ["bootstrap", "prepare-save", option, "value"]), \
                    redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                world.namespace["main"]()
            self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
