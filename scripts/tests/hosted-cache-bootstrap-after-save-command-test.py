#!/usr/bin/env python3
"""After-save command/leaf composition over memory files, not hosted evidence.

Selected actual Owner, admission composition, descriptor/mapper, supplied-input
constructors, canonical-record checks, after-save traversal and private writers
execute. Native admission, original allocation, source allowlist acquisition,
elapsed clocks, Action receipts and files are explicit models. No full runner import or old
producer/prepare test execution, native files, provider, download or Gradle.
"""
import argparse
from copy import deepcopy
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import runpy
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
prior = runpy.run_path(str(ROOT / "tests/hosted-cache-bootstrap-prepare-save-test.py"), run_name="prepare_fixtures_only")
selected, require, Refusal, FalseyFailure = (prior[name] for name in ("selected", "require", "Refusal", "FalseyFailure"))
encoded, digest, SECOND, LIMIT, Info = (prior[name] for name in ("encoded", "digest", "SECOND", "LIMIT", "Info"))
CODE = selected("run-hosted-cache-bootstrap.py", {"_save_preparation_record", "_after_save_inputs", "after_save_originals"})
STAGING = selected("hosted_cache_bootstrap_staging.py", {"ROOT", "BOOTSTRAP_INPUTS", "DIRECTORIES", "COUNTERS", "EMPTY",
    "Originals", "PhaseStart", "LeafEvidence", "_capture", "_capture_phase", "_capture_evidence", "_clock", "_identity",
    "_bytes", "_Inputs", "_Window", "_Leaf", "_stage_evidence", "_sources"})
CUSTODY = selected("hosted_cache_bootstrap_custody.py", {"StagedEvidence", "_capture_staged", "_equal", "_leaf_window",
    "_parent_record", "_Inputs", "PARENT_SCOPE"})
SAVE = selected("hosted_cache_bootstrap_save_set.py", {"SCOPE", "STATUSES", "AFTER_SCOPE", "AFTER_STATUS",
    "SaveSetEvidence", "_Window", "_AfterWindow", "before_save", "after_save", "_observe"})
PROVIDER = selected("hosted_dependency_cache.py", {"OBSERVATION_SCOPE", "OUTCOMES", "RESTORE_OUTPUTS", "provider_observation"})
# Keep the pure helpers extracted from context_record in the selected namespace.
INITIALIZER = selected("hosted_cache_bootstrap_initialization.py",
    {"properties", "_context_values", "_context_fields", "context_record"})
PRODUCER = selected("hosted_cache_bootstrap_producer.py", {"ProducerError", "_path", "JVM_ARGUMENTS", "CONTEXT_FIELDS"})
HASH = selected("hosted_dependency_seed_files.py", {"_hash"})


class World(prior["World"]):
    def __init__(self):
        super().__init__()
        self.raw_ns = 1020 * SECOND
        self.first = self.clocks.Reading(self.clock, self.raw_ns)
        self.after_path = self.original_path.with_name(self.original_path.name + "-after-save")
        self.leaf_calls = 0
        self.proposal["phaseFencesNs"].update({"canonical-init": 820 * SECOND, "canonical-init-final": 865 * SECOND,
            "canonical-init-read": 895 * SECOND, "dependency-stage": 880 * SECOND, "empty-seed": 900 * SECOND,
            "save-readmission": 1250 * SECOND, "save-set-after": 1400 * SECOND,
            "save-observation": 1430 * SECOND, "save-owner-return": 1475 * SECOND})
        self.proposal.update(proposedJobEndNs=1500 * SECOND, serviceTimeBasis={"service": {"lastNs": 690 * SECOND}})
        self.binding["invocation"] = "7" * 32
        self.origin.NS = SECOND
        self.origin.bootstrap = self.namespace["bootstrap"]
        self.origin.bootstrap.ordinary = self.namespace["I"]
        self.files.authority.MAX_XML_BYTES = LIMIT
        self.files.__dict__["hashlib"] = hashlib
        exec(HASH, self.files.__dict__)
        exec(PROVIDER, self.staging.cache.__dict__)
        producer = {"__name__": __name__, "require": require, "PurePosixPath": PurePosixPath,
            "PureWindowsPath": PureWindowsPath, "re": prior["prior"]["re"],
            "parse": self.origin.parse, "digest": digest, "bootstrap": self.origin.bootstrap}
        exec(PRODUCER, producer)
        initializer = {"require": require, "producer": NS(**producer), "re": prior["prior"]["re"],
            "datetime": datetime, "timezone": timezone}
        exec(INITIALIZER, initializer)
        self.staging.__dict__.update(__file__="/modeled-source/scripts/hosted_cache_bootstrap_staging.py",
            __name__=__name__, dataclass=dataclass, field=field, Path=Path, require=require, origin=self.origin,
            initialization=NS(**initializer), allocation=self.namespace["allocation"], re=prior["prior"]["re"],
            time=self.namespace["time"])
        exec(STAGING, self.staging.__dict__)
        custody = {"__name__": __name__, "dataclass": dataclass, "field": field, "staging": self.staging,
            "origin": self.origin, "files": self.files, "require": require, "ROOT": self.namespace["ROOT"], "Path": Path}
        exec(CUSTODY, custody)
        self.custody = NS(**custody)
        save = {"__name__": __name__, "dataclass": dataclass, "field": field, "staging": self.staging,
            "origin": self.origin, "files": self.files, "custody": self.custody,
            "dependency_export": self.namespace["dependency_export"]}
        exec(SAVE, save)
        self.save = NS(**save)
        actual_after = self.save.after_save

        def after(*args):
            self.leaf_calls += 1
            self.hit("leaf-call")
            result = actual_after(*args)
            self.hit("leaf-return")
            return result

        self.save.after_save = after
        self.namespace.update(custody=self.custody, dependency_save_set=self.save)
        exec(CODE, self.namespace)
        self.files.private_root = self.files.public_root = lambda path: self.open_directory(Path(path))
        directory = self.Directory
        world = self

        def names(handle, *, max_names, deadline):
            world.hit("names:" + handle.path.name)
            found = set(handle.node["files"]) | {path.name for path in world.data if path.parent == handle.path}
            require(world.local < deadline and len(found) <= max_names, "MODEL_NAMES_BOUNDARY")
            return tuple(sorted(found))

        def verify(handle):
            world.hit("verify:" + handle.path.name)
            require(handle.closes == 0 and handle.identity == handle.node["identity"], "MODEL_DIRECTORY_CHANGED")
            return Info(handle.identity, 0, handle.node.get("stamp", 1))

        directory.names, directory.verify = names, verify
        self.add_directory(self.save_path, 30)
        self.add_directory(self.namespace["ROOT"], 300)
        self.add_directory(self.namespace["ROOT"] / "scripts", 301)
        for number, name in enumerate(sorted(set((*self.staging.BOOTSTRAP_INPUTS,
                "scripts/hosted_cache_bootstrap_export.py", "scripts/hosted_cache_bootstrap_custody.py",
                "scripts/hosted_dependency_cache.py", "scripts/hosted_cache_bootstrap_save_set.py")))):
            self.add_file(self.namespace["ROOT"] / name, ("MODELED SOURCE ONLY " + name).encode(), 310 + number)
        self.bootstrap_inputs = {name: digest(self.data[self.namespace["ROOT"] / "scripts"]["files"][Path(name).name])
                                 for name in self.staging.BOOTSTRAP_INPUTS}
        self.properties = initializer["properties"](("/modeled/jdk17",))
        clock = self.origin.clock_value(self.clock)
        self.context = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PARENT_CONTEXT_V1", "job": "b" * 32,
            "previousSha256": "c" * 64, "requestSha256": "d" * 64, "admissionSha256": digest(self.admitted.record),
            "clock": clock, "directories": {name: list(self.ids(number)) for name, number in
                (("session", 10), ("canonical-init", 14), ("control-home", 15), ("temporary", 16))},
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        source = {**self.admission["source"], "status": "", "diffSha256": digest(b"")}
        self.canonical = {"schema": 1, "root": str(self.namespace["ROOT"]), "expectedCommit": source["commit"],
            "tree": source["tree"], "source": source, "host": "linux-x64", "gradleHome": str(self.session / "state/gradle-home"),
            "createdUtc": "2026-09-20T00:00:00+00:00", "id": "a" * 32, "gradlePropertiesSha256": digest(self.properties),
            "javaHomes": ["/modeled/jdk17"], "preexistingOutputPaths": []}
        self.context_raw = encoded(self.context)
        self.canonical_raw = (json.dumps(self.canonical, sort_keys=True, indent=2) + "\n").encode()
        self.add_directory(self.session / "state", 24)
        self.add_directory(self.session / "state/gradle-home", 23)
        self.actuals = {"initializer-context": self.context_raw, "canonical-context": self.canonical_raw,
                       "properties": self.properties, "staging": self.stage_raw}
        for number, (key, location, name) in enumerate((("initializer-context", self.session, "initializer-context.json"),
                ("canonical-context", self.session / "state", "context.json"),
                ("properties", self.session / "state/gradle-home", "gradle.properties"))):
            raw = self.actuals[key]
            info = self.add_file(location / name, raw, 400 + number)
            self.reference("initializer-actual/" + key, location, name, raw, self.files._info_binding(info))
        self.closed = {"schema": 1, "scope": "BOOTSTRAP_INITIALIZER_PREFIX_CLOSED_NO_EXECUTION_V1",
            "recipientClosedSha256": "c" * 64, "pendingSha256": "f" * 64,
            "window": {"clock": clock, "firstNs": 700 * SECOND, "workEndNs": 820 * SECOND,
                "nativeEndNs": 865 * SECOND, "prefixEndNs": 895 * SECOND, "finalStartedNs": 705 * SECOND,
                "finalEndNs": 750 * SECOND, "readStartedNs": 710 * SECOND, "readEndNs": 740 * SECOND,
                "budgetAcceptance": "NOT_ADMITTED"}, "closedNs": 712 * SECOND, "resourceCount": 17,
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "childReturn": "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False}
        self.blobs["initializer-parent.json"] = encoded(self.closed)
        self.value["chain"]["returns"].update({"initializer": {"checkedNs": 715 * SECOND, "checkedLocal": 5000.0},
            "dependency-stage": {"leaf": {"checkedNs": 772 * SECOND, "localStarted": 5001.0, "checkedLocal": 5002.0},
                "parent": {"checkedNs": 775 * SECOND, "checkedLocal": 5002.1}},
            "empty-seed": {"leaf": {"checkedNs": 792 * SECOND, "localStarted": 5003.0, "checkedLocal": 5004.0},
                "parent": {"checkedNs": 795 * SECOND, "checkedLocal": 5004.1}}})
        self.value["chain"]["returns"]["before"]["checkedLocal"] = 5008.0
        self.returned["handoffReturnedLocal"], self.returned["observedAfterReturnLocal"] = 5009.0, 5010.0
        directories = {name: list(self.ids(number)) for name, number in
            (("session", 10), ("state", 24), ("gradle-home", 23), ("evidence", 25), ("cancellations", 26))}
        original = self.staging.Originals(self.admitted, self.responses, self.binding["invocation"], self.clock,
            self.env["RUNNER_NAME"], encoded(self.proposal), str(self.original_path), self.context_raw, self.canonical_raw,
            self.properties, directories, self.blobs["initializer-parent.json"], 715 * SECOND, 5000.0)
        inputs = self.staging._Inputs(original, self.staging._capture(original))
        self.binding = self.value["binding"] = inputs.binding()
        self.blobs["allocation-proposal.json"] = encoded(self.proposal)
        bindings = {name: deepcopy(self.value["references"]["initializer-actual/" + name]["fileBinding"])
                    for name in ("initializer-context", "canonical-context", "properties")}
        bindings["staging"] = self.stage_binding
        stage_value = {"schema": 1, "scope": self.staging.STAGE_SCOPE, "binding": self.binding, "inputs": self.inputs,
            "bootstrapInputs": self.bootstrap_inputs, "stagingSha256": digest(self.stage_raw), "plan": self.plan,
            "seedIntent": {"modeled": "unused-seed-intent"}, "fileBindings": bindings,
            "window": self.window_record("dependency-stage", 760, self.blobs["initializer-parent.json"], 715 * SECOND),
            "status": self.staging.EMPTY, "completed": True, "leafHandleClose": "KNOWN",
            "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "nextPhaseAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        stage_leaf = self.staging.LeafEvidence(encoded(stage_value), self.stage_raw, 772 * SECOND, 5001.0, 5002.0)
        seed_value = {**stage_value, "scope": self.staging.SEED_SCOPE,
            "window": self.window_record("empty-seed", 780, stage_leaf.raw, stage_leaf.checked_ns),
            "stageEvidenceSha256": digest(stage_leaf.raw), "stageReturnBindingSha256": digest(encoded({
                "rawSha256": digest(stage_leaf.raw), "checkedNs": stage_leaf.checked_ns,
                "localStarted": stage_leaf.local_started, "localChecked": stage_leaf.checked_local})),
            "counts": {name: 0 for name in self.staging.COUNTERS}, "admitted": [],
            "misses": [{"index": i, "reason": "ABSENT", "rejected": 0} for i in range(2)],
            "sourceIdentity": self.stage["sourceIdentity"], "homeIdentity": directories["gradle-home"],
            "byteScope": "DEPENDENCY_BYTES_ONLY_METADATA_IO_OCCURRED"}
        seed_leaf = self.staging.LeafEvidence(encoded(seed_value), self.stage_raw, 792 * SECOND, 5003.0, 5004.0)
        stage_parent = self.parent_record(stage_leaf, self.blobs["initializer-parent.json"], 715 * SECOND)
        seed_parent = self.parent_record(seed_leaf, stage_parent, 775 * SECOND)
        self.blobs.update({"stage-leaf.json": stage_leaf.raw, "seed-leaf.json": seed_leaf.raw,
                           "stage-parent.json": stage_parent, "seed-parent.json": seed_parent})
        mapped = self.map_inputs()
        self.payload = b"abc"
        self.compiled = replace(self.compiled, artifacts=tuple(row._replace(sha256=digest(self.payload))
                                                               for row in self.compiled.artifacts))
        exported = json.loads(self.blobs["export-leaf.json"])
        exported.update(binding=self.binding, predecessors=mapped.predecessors(), propertiesSha256=digest(self.properties),
            exportInputs={"scripts/" + name: digest(self.data[self.namespace["ROOT"] / "scripts"]["files"][name])
                for name in ("hosted_cache_bootstrap_export.py", "hosted_cache_bootstrap_custody.py", "hosted_dependency_cache.py")})
        member = exported["admitted"][0]
        member["sha1"], member["sha256"] = hashlib.sha1(self.payload).hexdigest(), digest(self.payload)
        parts = member["path"].split("/")
        parts[-2] = member["sha1"]
        member["path"] = "/".join(parts)
        directories, _ = self.staging.cache._save_roster(exported)
        for number, parts in enumerate(sorted(directories)):
            location = self.container_path / "restore-home" / "/".join(parts)
            if location not in self.data:
                self.add_directory(location, 40 + number)
        self.add_file(self.container_path / "restore-home" / member["path"], self.payload, 81)
        frozen = json.loads(self.blobs["before-leaf.json"])
        frozen.update(binding=self.binding, predecessors=mapped.predecessors(), exportSha256=digest(encoded(exported)),
            files=[member["path"]], directories=[{"path": "/".join(parts), "names": list(names),
                "binding": self.files._info_binding(Info(self.data[self.container_path / "restore-home" / "/".join(parts)]["identity"]))}
                for parts, names in sorted(directories.items())],
            saveSetInputs={**exported["exportInputs"], "scripts/hosted_cache_bootstrap_save_set.py":
                digest(self.data[self.namespace["ROOT"] / "scripts"]["files"]["hosted_cache_bootstrap_save_set.py"])})
        frozen["window"]["proposalSha256"] = digest(encoded(self.proposal))
        self.blobs["export-leaf.json"], self.blobs["before-leaf.json"] = encoded(exported), encoded(frozen)
        self.relink()
        self.prepared = {"schema": 1, "scope": "BOOTSTRAP_SAVE_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1",
            **{name: self.admission[name] for name in ("source", "github", "selection", "cacheCohort")},
            "directory": str(self.save_path), "directoryIdentity": list(self.ids(30)),
            "handoffSha256": self.expected, "producerReturnSha256": digest(encoded(self.returned)),
            "producerOriginalOutcome": "success", "admissionSha256": digest(self.admitted.record),
            "admissionReturn": {"admissionSha256": digest(self.admitted.record), "sessionSha256": "e" * 64,
                "clock": clock, "returnedNs": 1002 * SECOND},
            "finalAdmissionReturn": {"admissionSha256": digest(self.admitted.record), "sessionSha256": "f" * 64,
                "clock": clock, "returnedNs": 1004 * SECOND}, "proposalSha256": digest(encoded(self.proposal)),
            "plan": self.plan, "planSha256": digest(encoded(self.plan)), "clock": clock,
            "firstNs": 1000 * SECOND, "hardEndNs": 1030 * SECOND, "producerObservedAfterReturnNs": 998 * SECOND,
            "providerWindow": {"issuedNs": 1005 * SECOND, "hardEndNs": 1185 * SECOND, "actualProviderStart": "NOT_OBSERVED"},
            "providerRequest": {"action": self.plan["provider"]["save"], "path": self.plan["path"], "key": self.plan["key"],
                "enableCrossOsArchive": False, "scope": "PRIVATE_DESCRIPTOR_NOT_EXECUTION"},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        self.env.update(P2PKIT_BOOTSTRAP_SAVE_PREPARE_OUTCOME="success", P2PKIT_BOOTSTRAP_SAVE_OUTCOME="success")
        self.preparation_bytes()
        self.action_calls = []
        self.namespace["provider_readback"] = NS(ACTION_FILES=("provider-prepared.json", "provider-readback.json"),
                                                validate_action_return=self.action_return)
        self.add_action_originals(self.save_path, "SAVE")

    def add_action_originals(self, path, prefix):
        # Only the new caller seam is modeled here; the pure validator has its
        # own focused controls. These are not real native/Action originals.
        for name in self.namespace["provider_readback"].ACTION_FILES:
            self.data[path]["files"][name] = encoded({"MODEL_ACTION_METADATA": name, "phase": prefix})
        self.env["P2PKIT_BOOTSTRAP_" + prefix + "_READBACK_SHA256"] = digest(
            self.data[path]["files"]["provider-readback.json"])

    def action_return(self, originals, descriptor, claims, first, **options):
        self.action_calls.append((dict(originals), descriptor, dict(claims), first, options))
        self.hit("action-receipt:" + options["phase"])

    def add_file(self, path, raw, number):
        info = Info(self.ids(number), len(raw))
        self.data[path.parent]["files"][path.name] = raw
        self.data[path.parent]["infos"][path.name] = info
        return info

    def new_directory(self, path):
        self.hit("new-dir:" + path.name)
        require(path == self.after_path, "MODEL_FIXED_AFTER_SAVE_TARGET")
        self.add_directory(path, 500)
        return self.open_directory(path)

    def source_inputs(self, owner, root, end, checked):
        return super().source_inputs(owner, Path(root), end, checked)

    def map_inputs(self, **changes):
        args = dict(admitted=self.admitted, index=self.value, blobs=self.blobs, responses=self.responses,
                    original_path=self.original_path, clock=self.clock, actuals=self.actuals)
        args.update(changes)
        return self.namespace["_after_save_inputs"](**args)

    def window_record(self, name, first, previous, checked):
        return {"phase": name, "clock": self.origin.clock_value(self.clock), "firstNs": first * SECOND,
            "hardEndNs": (first + 120) * SECOND, "softEndNs": (first + (90 if name == "empty-seed" else 120)) * SECOND,
            "lastNewWorkNs": (first + 5) * SECOND, "finishedNs": (first + 10) * SECOND,
            "predecessorSha256": digest(previous), "predecessorCheckedNs": checked,
            "proposalSha256": digest(encoded(self.proposal))}

    def parent_record(self, leaf, previous, checked):
        value = json.loads(leaf.raw)["window"]
        return encoded({"schema": 1, "scope": self.custody.PARENT_SCOPE, "phase": value["phase"],
            "window": {**{key: value[key] for key in ("phase", "clock", "firstNs", "softEndNs", "hardEndNs")},
                "budgetAcceptance": "NOT_ADMITTED"}, "pendingSha256": "e" * 64,
            "predecessorSha256": digest(previous), "predecessorCheckedNs": checked, "leafSha256": digest(leaf.raw),
            "leafCheckedNs": leaf.checked_ns, "closedNs": leaf.checked_ns + 2 * SECOND, "resourceCount": 5,
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "nextPhaseAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})

    def preparation_bytes(self):
        self.data[self.save_path]["files"]["save-preparation.json"] = encoded(self.prepared)
        self.env["P2PKIT_BOOTSTRAP_SAVE_PREPARATION_SHA256"] = digest(encoded(self.prepared))

    def rebind_proposal(self):
        old = digest(self.blobs["allocation-proposal.json"])
        new = digest(encoded(self.proposal))
        # Test-only supplied-data mutation, not original producer execution.
        self.blobs["allocation-proposal.json"] = encoded(self.proposal)
        self.binding["proposalSha256"] = new
        for name in ("stage-leaf.json", "seed-leaf.json", "export-leaf.json", "before-leaf.json"):
            raw = self.blobs[name].replace(old.encode(), new.encode())
            value = json.loads(raw)
            value["binding"] = self.binding
            self.blobs[name] = encoded(value)
        self.relink()
        self.prepared.update(proposalSha256=new, handoffSha256=self.expected,
                             producerReturnSha256=digest(encoded(self.returned)))
        self.preparation_bytes()

    def validate_descriptor(self, raw=None, expected=None):
        raw = encoded(self.prepared) if raw is None else raw
        return self.namespace["_save_preparation_record"](raw, digest(raw) if expected is None else expected,
            self.admitted, self.blobs["save-handoff.json"], encoded(self.returned), self.proposal,
            self.clocks.Reading(self.clock, self.raw_ns), NS(path=self.save_path, identity=self.ids(30)))

    def run(self, *, guarded=False, cancelled=None):
        return (self.namespace["guarded"](self.namespace["after_save_originals"]) if guarded else
                self.namespace["after_save_originals"]([] if cancelled is None else cancelled))

    def retained(self, name):
        return json.loads(self.data[self.after_path]["files"][name])


class CommandModels(unittest.TestCase):
    def fail(self, world, reason=None, kind=BaseException):
        with (self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)) as caught:
            world.run()
        self.assertNotIn("after-save-return.json", world.data.get(world.after_path, {}).get("files", {}))
        return caught.exception

    def test_actual_mapper_leaf_owner_provider_observation_and_three_phase_writers(self):
        w = World()
        raw, fence, hard = w.run()
        self.assertEqual(w.leaf_calls, 1)
        self.assertEqual(len(w.owners), 4)
        self.assertEqual(len(w.native_pairs), 2)
        self.assertTrue(all(owner.closed and owner.original is None and not owner.unknown for owner in w.owners))
        self.assertTrue(all(row["attempted"] and row["closed"] for owner in w.owners for row in owner.resources))
        self.assertTrue(all(handle.closes == 1 for handle in w.handles))
        self.assertEqual(w.retained("after-leaf.json")["counts"]["hashedBytes"], 3)
        self.assertEqual(w.retained("provider-save.json")["status"], "SAVE_SUCCEEDED_STORAGE_UNPROVEN")
        self.assertEqual(w.retained("provider-save.json")["outputs"], {})
        self.assertEqual(w.retained("after-save-return.json")["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(w.retained("save-observations.json")["providerRetirement"], "NOT_OBSERVED")
        self.assertEqual(w.retained("save-observations.json")["providerDeadlineEnforcement"], "NOT_ESTABLISHED")
        self.assertEqual(hard, fence.hard_end)
        self.assertIn("afterSaveSha256", raw)
        self.assertEqual(w.retained("after-parent-close.json")["historicalBeforeCheckedLocal"], 5008.0)
        self.assertLess(w.retained("after-parent-close.json")["localStarted"], 5008.0)

    def test_each_original_outcome_must_be_literal_success_before_ownership(self):
        for name in ("PRODUCER_OUTCOME", "SAVE_PREPARE_OUTCOME", "SAVE_OUTCOME"):
            for value in (None, "", "failure", "cancelled", "skipped", "SUCCESS", True):
                with self.subTest(name=name, value=value):
                    w = World()
                    w.env["P2PKIT_BOOTSTRAP_" + name] = value
                    self.fail(w, "ORIGINAL_OUTCOMES")
                    self.assertEqual(w.owners, [])

    def test_hashes_are_independent_original_lowercase_inputs(self):
        for name in ("HANDOFF_SHA256", "PRODUCER_RETURN_SHA256", "SAVE_PREPARATION_SHA256"):
            for value in (None, "A" * 64, "", True, "a" * 63):
                with self.subTest(name=name, value=value):
                    w = World()
                    w.env["P2PKIT_BOOTSTRAP_" + name] = value
                    self.fail(w, "ORIGINAL_HASHES")
                    self.assertEqual(w.owners, [])

    def test_token_and_ambient_execution_overrides_do_not_reach_native(self):
        for key in ("P2PKIT_JOB_TIME_TOKEN", "GRADLE_OPTS", "GIT_CONFIG_COUNT"):
            with self.subTest(key=key):
                w = World()
                w.env[key] = "modeled-denied-value"
                self.fail(w)
                self.assertEqual(w.native_pairs, [])

    def test_late_post_action_bound_is_denied_before_native_even_on_success(self):
        w = World()
        w.raw_ns = w.prepared["providerWindow"]["hardEndNs"]
        self.fail(w, "PROVIDER_RETURN_BOUND")
        self.assertEqual(w.native_pairs, [])
        self.assertEqual(w.leaf_calls, 0)

    def test_readmission_can_finish_after_provider_end_when_initial_bound_is_timely(self):
        w = World()
        original_inputs = w.map_inputs()
        # This cap change is modeled as an original supplied proposal. Recreate
        # the complete fixture rather than repairing stale nested hashes.
        w.proposal["phaseFencesNs"]["provider-save"] = 1040 * SECOND
        w.rebind_proposal()
        # Only exercise deadline handling here; source/data mapping has its own
        # actual-constructor cases and is explicitly replaced by the old data.
        w.namespace["_after_save_inputs"] = lambda *args: original_inputs
        w.prepared["providerWindow"]["hardEndNs"] = 1040 * SECOND
        w.preparation_bytes()
        w.hooks["native-admit:2"] = lambda: setattr(w, "raw_ns", 1045 * SECOND)
        # The complete leaf is modeled only in this timing-specific control.
        def leaf(owner, inputs, window, exported, frozen):
            w.leaf_calls += 1
            window.sample()
            value = {"scope": w.save.AFTER_SCOPE, "status": "KNOWN_UNCHANGED", "completed": True,
                "retirement": "KNOWN", "errors": [], "beforeSaveSha256": digest(frozen), "exportSha256": digest(exported),
                "nextPhaseAuthority": False, "exportSaveAuthority": False, "testAcceptance": "NOT_PERFORMED",
                "budgetAcceptance": "NOT_ADMITTED"}
            return w.save.SaveSetEvidence(encoded(value), window.last, window.local_start, window.local_last)
        w.save.after_save = leaf
        w.run()
        self.assertEqual(w.retained("save-observations.json")["firstPostProviderNs"], 1020 * SECOND)
        self.assertGreater(w.retained("readmission-close.json")["closedNs"], 1040 * SECOND)

    def test_recorded_readmission_cap_only_denies_before_native(self):
        w = World()
        w.proposal["phaseFencesNs"]["save-readmission"] = 1020 * SECOND
        w.rebind_proposal()
        self.fail(w, "JOB_TIME_LOCAL_DEADLINE")
        self.assertEqual(w.native_pairs, [])

    def test_original_metadata_cannot_get_a_fresh120_after_delay(self):
        w = World()
        w.hooks["host-inputs"] = lambda: setattr(w, "local", 221.0)
        self.fail(w)
        self.assertEqual(w.native_pairs, [])

    def test_fixed_reference_paths_hashes_and_file_identity_are_required(self):
        for field, value in (("directory", "/must/not/read"), ("name", "../replacement"), ("sha256", "0" * 64),
                             ("fileBinding", None)):
            with self.subTest(field=field):
                w = World()
                w.value["references"]["initializer-actual/properties"][field] = value
                w.relink()
                w.prepared.update(handoffSha256=w.expected, producerReturnSha256=digest(encoded(w.returned)))
                w.preparation_bytes()
                self.fail(w, "REFERENCE")
                self.assertEqual(w.leaf_calls, 0)

    def test_same_byte_replacement_during_final_admission_is_not_adopted(self):
        w = World()
        path = w.session / "state/gradle-home"
        w.hooks["native-admit:2"] = lambda: w.data[path]["infos"].update(
            {"gradle.properties": Info(w.ids(999), len(w.properties))})
        self.fail(w, "FILE_REPLACED")
        self.assertEqual(w.leaf_calls, 0)

    def test_source_change_between_readmission_and_leaf_is_rejected(self):
        w = World()
        w.hooks["leaf-call"] = lambda: w.data[w.namespace["ROOT"] / "scripts"]["files"].update(
            {"hosted_cache_bootstrap_export.py": b"changed-source"})
        self.fail(w)
        self.assertEqual(w.leaf_calls, 1)

    def test_changed_dependency_bytes_and_extra_directory_do_not_become_new_baseline(self):
        for mutate in ("bytes", "directory"):
            with self.subTest(mutate=mutate):
                w = World()
                member = json.loads(w.blobs["export-leaf.json"])["admitted"][0]["path"]
                path = w.container_path / "restore-home" / member
                if mutate == "bytes":
                    w.data[path.parent]["files"][path.name] = b"xyz"
                else:
                    w.add_directory(w.container_path / "restore-home/extra", 999)
                self.fail(w)
                self.assertEqual(w.leaf_calls, 1)

    def test_readmission_close_error_does_not_start_leaf(self):
        w = World()
        error = FalseyFailure("known-close-clock")
        def fail_close():
            raise error
        w.hooks["close-dir:final-admission"] = fail_close
        self.assertIs(self.fail(w), error)
        self.assertEqual(w.leaf_calls, 0)

    def test_known_expired_readmission_close_cannot_be_inferred_successful_from_closed(self):
        w = World()
        w.hooks["close-dir:final-admission"] = lambda: setattr(w, "local", 221.0)
        self.fail(w, "PHASE_EXPIRED")
        self.assertEqual(w.leaf_calls, 0)
        self.assertTrue(w.owners[0].closed)
        self.assertIsNotNone(w.owners[0].original)
        self.assertFalse(w.owners[0].unknown)
        self.assertTrue(all(handle.closes == 1 for handle in w.handles))

    def test_falsey_leaf_read_failure_remains_original_and_closes_known_handles_once(self):
        w = World()
        error = FalseyFailure("first-leaf-read")
        w.hooks["file-read:alpha.jar"] = lambda: prior["throw"](error)
        self.assertIs(self.fail(w), error)
        self.assertTrue(all(handle.closes == 1 for handle in w.handles))
        self.assertEqual(len(w.owners), 2)

    def test_unknown_leaf_read_quarantines_without_next_owner_or_more_closes(self):
        w = World()
        error = FalseyFailure("unknown-leaf-read")
        error.retirement_unknown = True
        w.hooks["file-read:alpha.jar"] = lambda: prior["throw"](error)
        self.assertIs(self.fail(w), error)
        self.assertEqual(len(w.owners), 2)
        self.assertTrue(w.owners[-1].unknown)
        self.assertIn(w.owners[-1], w.namespace["QUARANTINE"])
        self.assertTrue(any(handle.closes == 0 for handle in w.handles))

    def test_leaf_expiry_is_not_rescued_by_observation_phase(self):
        w = World()
        w.hooks["file-read:alpha.jar"] = lambda: setattr(w, "local", 221.0)
        self.fail(w)
        self.assertEqual(len(w.owners), 2)

    def test_provider_classification_spends_original_observation30(self):
        w = World()
        actual = w.staging.cache.provider_observation
        def delayed(*args, **kwargs):
            value = actual(*args, **kwargs)
            w.local += 31
            return value
        w.staging.cache.provider_observation = delayed
        self.fail(w, "PHASE_EXPIRED")
        self.assertEqual(len(w.owners), 3)

    def test_observation_write_failure_cannot_start_return_owner(self):
        w = World()
        error = FalseyFailure("observation-write")
        w.hooks["file-write:save-observations.json"] = lambda: prior["throw"](error)
        self.assertIs(self.fail(w), error)
        self.assertEqual(len(w.owners), 3)

    def test_last_writer_close_failure_leaves_only_pending_file_and_no_digest(self):
        w = World()
        error = FalseyFailure("last-writer-close")
        w.hooks["close-file:after-save-return.json"] = lambda: prior["throw"](error)
        with self.assertRaises(BaseException) as caught:
            w.run(guarded=True)
        self.assertIs(caught.exception, error)
        self.assertEqual(len(w.owners), 4)
        self.assertTrue(w.owners[-1].unknown)
        self.assertEqual(w.namespace["sys"].stdout.buffer.getvalue(), b"")
        self.assertEqual(w.retained("after-save-return.json")["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")

    def test_changed_retained_parent_directory_is_not_new_observation_authority(self):
        w = World()
        visits = []
        def changed():
            visits.append(True)
            if len(visits) == 2:
                w.data[w.after_path]["identity"] = w.ids(999)
        w.hooks["open-dir:" + w.after_path.name] = changed
        self.fail(w, "DIRECTORY_CHANGED")
        self.assertEqual(w.leaf_calls, 1)
        self.assertEqual(len(w.owners), 3)

    def test_backward_raw_during_leaf_does_not_reset_current_phase(self):
        w = World()
        w.hooks["leaf-call"] = lambda: setattr(w, "raw_ns", w.raw_ns - 1)
        self.fail(w)
        self.assertEqual(w.leaf_calls, 1)
        self.assertEqual(len(w.owners), 2)

    def test_replay_uses_no_old_owner_or_second_after_walk(self):
        w = World()
        w.run()
        with self.assertRaisesRegex(Refusal, "EXCLUSIVE_DIRECTORY"):
            w.run()
        self.assertEqual(w.leaf_calls, 1)

    def test_cancellation_and_environment_change_cannot_start_next_phase(self):
        for kind in ("cancelled", "changed"):
            with self.subTest(kind=kind):
                w = World()
                cancellation = []
                w.hooks["native-admit:2"] = (lambda: cancellation.append(15)) if kind == "cancelled" else (
                    lambda: w.env.update(P2PKIT_BOOTSTRAP_SAVE_OUTCOME="failure"))
                with self.assertRaises(BaseException):
                    w.run(cancelled=cancellation)
                self.assertEqual(w.leaf_calls, 0)

    def test_guarded_digest_has_no_paths_keys_or_provider_acceptance(self):
        w = World()
        w.run(guarded=True)
        result = json.loads(w.namespace["sys"].stdout.buffer.getvalue())
        self.assertEqual(set(result), {"scope", "afterSaveSha256", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"})
        self.assertEqual(result["budgetAcceptance"], "NOT_ADMITTED")
        self.assertIs(result["exportSaveAuthority"], False)
        self.assertNotIn("GITHUB_OUTPUT", w.env)

    def test_late_final_flush_cannot_turn_provisional_digest_into_success(self):
        w = World()
        class Output(io.BytesIO):
            def flush(self):
                w.local += 46
        w.namespace["sys"].stdout.buffer = Output()
        with self.assertRaisesRegex(Refusal, "PHASE_EXPIRED"):
            w.run(guarded=True)
        self.assertIn(b"afterSaveSha256", w.namespace["sys"].stdout.buffer.getvalue())
        self.assertTrue(all(owner.closed for owner in w.owners))


class DescriptorModels(unittest.TestCase):
    def test_exact_preparation_is_supplied_data_not_provider_start(self):
        w = World()
        self.assertEqual(w.validate_descriptor(), w.prepared)
        self.assertEqual(w.prepared["providerWindow"]["actualProviderStart"], "NOT_OBSERVED")

    def test_original_hash_canonical_encoding_and_closed_fields(self):
        w = World()
        for raw, expected in ((encoded(w.prepared), "0" * 64),
                (json.dumps(w.prepared, indent=2).encode(), None),
                (encoded({**w.prepared, "claim": "trusted"}), None)):
            with self.subTest(raw=raw[:30]), self.assertRaises(Refusal):
                w.validate_descriptor(raw, expected)

    def test_changed_source_run_selection_directory_or_plan_does_not_validate(self):
        mutations = (lambda v: v["source"].update(commit="0" * 40), lambda v: v["github"].update(runAttempt="2"),
            lambda v: v.update(selection="full-macos-x64"), lambda v: v.update(directoryIdentity=[1, 99]),
            lambda v: v["plan"].update(key="substitute"), lambda v: v.update(handoffSha256="0" * 64))
        for change in mutations:
            with self.subTest(change=change):
                w = World()
                value = deepcopy(w.prepared)
                change(value)
                with self.assertRaises(Refusal):
                    w.validate_descriptor(encoded(value))

    def test_provider_pin_path_key_cross_os_and_no_self_attestation(self):
        for key, value in (("action", "untrusted/save@main"), ("path", "/other"), ("key", "other"),
                           ("enableCrossOsArchive", True), ("scope", "EXECUTION")):
            with self.subTest(key=key):
                w = World()
                w.prepared["providerRequest"][key] = value
                with self.assertRaisesRegex(Refusal, "PROVIDER_REQUEST"):
                    w.validate_descriptor()

    def test_original_end_cannot_be_renewed_from_post_guard_start(self):
        w = World()
        w.prepared["providerWindow"]["hardEndNs"] = w.raw_ns + 180 * SECOND
        with self.assertRaisesRegex(Refusal, "PROVIDER_RETURN_BOUND"):
            w.validate_descriptor()

    def test_clock_order_and_original_admission_returns_are_required(self):
        for change in (lambda v: v["clock"].update(domain="different"),
                lambda v: v["finalAdmissionReturn"].update(returnedNs=1001 * SECOND),
                lambda v: v.update(producerObservedAfterReturnNs=999 * SECOND),
                lambda v: v["providerWindow"].update(issuedNs=1003 * SECOND)):
            with self.subTest(change=change):
                w = World()
                change(w.prepared)
                with self.assertRaises(Refusal):
                    w.validate_descriptor()


class MappingAndWindowModels(unittest.TestCase):
    def test_actual_supplied_constructors_keep_original_bytes_and_old_local(self):
        w = World()
        result = w.map_inputs()
        self.assertEqual(result.canonical_raw, w.canonical_raw)
        self.assertNotEqual(w.canonical_raw, encoded(w.canonical))
        self.assertEqual(result.previous_local, 5000.0)
        self.assertEqual(result.staged.checked_local, 5004.1)
        self.assertEqual(result.binding(), w.binding)
        self.assertEqual(w.owners, [])
        self.assertEqual(w.leaf_calls, 0)

    def test_corrupt_original_context_properties_and_parent_cannot_be_hydrated(self):
        for name in ("initializer-context", "canonical-context", "properties"):
            with self.subTest(name=name):
                w = World()
                actuals = dict(w.actuals, **{name: b"{}"})
                with self.assertRaises((ValueError, KeyError)):
                    w.map_inputs(actuals=actuals)
        w = World()
        w.blobs["seed-parent.json"] = encoded({"claim": "closed"})
        with self.assertRaises((ValueError, KeyError)):
            w.map_inputs()

    def test_original_staged_return_scalars_and_mapping_roster_are_not_filled_in(self):
        for change in (lambda w: w.value["chain"]["returns"]["empty-seed"]["leaf"].update(checkedLocal=1.0),
                lambda w: w.value["chain"]["returns"]["initializer"].update(checkedNs=1),
                lambda w: w.actuals.update(extra=b"not-an-original")):
            with self.subTest(change=change):
                w = World()
                change(w)
                with self.assertRaises((ValueError, KeyError)):
                    w.map_inputs()

    def test_new_process_local_is_not_compared_with_historical_before_local(self):
        w = World()
        inputs = w.map_inputs()
        phase = w.staging.PhaseStart(w.first, w.local)
        previous = (w.blobs["before-parent.json"], 985 * SECOND, 5008.0)
        window = w.save._AfterWindow(inputs, phase, previous, current_process_floor=phase)
        window.sample()
        self.assertEqual(window.previous_local, 5008.0)
        self.assertEqual(window.previous_ns, 985 * SECOND)
        self.assertEqual(window.local_start, 100.0)
        with self.assertRaisesRegex(Refusal, "PREDECESSOR_CLOCK"):
            w.save._AfterWindow(inputs, phase, previous)

    def test_default_same_process_window_retains_original_clock_contract(self):
        w = World()
        w.local = 5011.0
        phase = w.staging.PhaseStart(w.first, w.local)
        window = w.save._AfterWindow(w.map_inputs(), phase, (w.blobs["before-parent.json"], 985 * SECOND, 5008.0))
        window.sample()
        self.assertIsNone(window.current_process_floor)
        self.assertEqual(window.previous_local, 5008.0)
        w.local -= 1
        with self.assertRaisesRegex(Refusal, "LOCAL_BACKWARDS"):
            window.sample()

    def test_new_floor_must_follow_old_raw_and_new_phase_must_follow_both_clocks(self):
        w = World()
        for ns, local in ((984 * SECOND, 100.0), (1021 * SECOND, 100.0), (1020 * SECOND, 101.0)):
            with self.subTest(ns=ns, local=local), self.assertRaises(Refusal):
                w.save._AfterWindow(w.map_inputs(), w.staging.PhaseStart(w.first, 100.0),
                    (w.blobs["before-parent.json"], 985 * SECOND, 5008.0),
                    current_process_floor=w.staging.PhaseStart(w.clocks.Reading(w.clock, ns), local))

    def test_changed_current_floor_and_expired_original_after_cap_refuse(self):
        w = World()
        phase = w.staging.PhaseStart(w.first, 100.0)
        floor = w.staging.PhaseStart(w.first, 100.0)
        inputs = w.map_inputs()
        window = w.save._AfterWindow(inputs, phase, (w.blobs["before-parent.json"], 985 * SECOND, 5008.0),
                                    current_process_floor=floor)
        object.__setattr__(floor, "local_started", 99.0)
        with self.assertRaisesRegex(Refusal, "NEW_PROCESS_CHANGED"):
            window.sample()
        inputs.proposal["phaseFencesNs"]["save-set-after"] = 1020 * SECOND
        with self.assertRaises(Refusal):
            w.save._AfterWindow(inputs, phase, (w.blobs["before-parent.json"], 985 * SECOND, 5008.0),
                                current_process_floor=phase)

    def test_fixed_cli_has_no_path_key_command_duration_or_output_override(self):
        w = World()
        calls = []
        w.namespace["guarded"] = lambda operation: calls.append(operation)
        with patch("sys.argv", ["run-hosted-cache-bootstrap.py", "after-save"]):
            self.assertEqual(w.namespace["main"](), 0)
        self.assertEqual(calls, [w.namespace["after_save_originals"]])
        for option in ("--path", "--key", "--command", "--duration", "--outcome"):
            with self.subTest(option=option), patch("sys.argv", ["run-hosted-cache-bootstrap.py", "after-save", option, "x"]),\
                    patch("sys.stderr", io.StringIO()), self.assertRaises(SystemExit):
                w.namespace["main"]()


if __name__ == "__main__":
    unittest.main()
