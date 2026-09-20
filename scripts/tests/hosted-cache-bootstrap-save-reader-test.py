#!/usr/bin/env python3
"""Borrowed-Owner save-package controls, not original-step/provider admission.

Only selected reader/Owner/directory, JSON/clock-data and plan-shape definitions
execute. Admission, elapsed-clock observations and private files are memory
models. Fixtures match the reader-visible record shapes; unselected originals
are deliberately opaque, not a replay of the accepted writer or its tests.
No full controller import, native operation, process or filesystem fixture.
"""
import ast
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
import math
from pathlib import Path
import re
from types import SimpleNamespace as NS
import unittest


ROOT = Path(__file__).resolve().parents[1]
SECOND, LIMIT = 1_000_000_000, 2 * 1024 * 1024
NAMES = (
    "before-parent.json", "before-leaf.json", "export-parent.json", "export-leaf.json",
    "no-loader-parent.json", "no-loader-leaf.json", "collection-parent.json", "collection-leaf.json",
    "collection-inventory.json", "producer-parent.json", "producer-request.json", "producer-observation.json",
    "producer-command.json", "producer-birth.json", "producer-leader.json", "producer-preparer.json",
    "producer-terminal.json", "producer-survivors.json", "custody-parent.json", "custody-leaf.json",
    "seed-parent.json", "stage-parent.json", "stage-leaf.json", "seed-leaf.json", "initializer-parent.json",
    "recipient-parent.json", "allocation-proposal.json", "entry-parent.json", "adoption-parent.json",
    "adoption-preparation.json", "entry-preparation.json",
)


def selected(filename, names):
    tree = ast.parse((ROOT / filename).read_text(), filename=filename)
    nodes, found = [], set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            offered = {node.name}
        elif isinstance(node, ast.Assign):
            offered = {item.id for target in node.targets for item in ast.walk(target) if isinstance(item, ast.Name)}
        else:
            continue
        if offered & names:
            assert offered <= names, (filename, offered)
            nodes.append(node)
            found |= offered
    assert found == names, (filename, names - found)
    return compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec")


RUNNER = selected("run-hosted-cache-bootstrap.py",
    {"Owner", "directory_identity", "_new_entry_owned", "_initializer_names", "_read_save_handoff"})
CLOCK = selected("hosted_job_clock.py", {"NS", "UINT64", "INT64", "DARWIN_DOMAIN", "LINUX_DOMAIN",
    "WINDOWS_DOMAIN", "DOMAINS", "ClockError", "require", "integer", "ClockIdentity", "Reading",
    "validate_identity", "validate_reading"})
JSON_PARSER = selected("hosted_test_identity.py", {"AdmissionError", "require", "parse"})
WIRE = selected("hosted_full_job_budget.py", {"encoded", "digest"})
INTEGER = selected("hosted_cache_bootstrap_origin.py", {"integer"})
CACHE = selected("hosted_dependency_cache.py", {"ACTION_PIN", "PLAN_SCOPE", "MODES", "PLAN_KEYS",
    "_sha", "_profile", "cache_key", "_provider", "_plan_shape"})
FILES = selected("hosted_dependency_seed_files.py", {"INPUTS", "stage_path"})
LOCAL = selected("hosted_cache_bootstrap_staging.py", {"_local"})


class Refusal(ValueError):
    pass


class FalseyFailure(BaseException):
    def __bool__(self):
        return False


def require(value, reason):
    if not value:
        raise Refusal(reason)


def noop(*_args):
    pass


wire = {"require": require, "json": json, "hashlib": hashlib, "RECORD_LIMIT": LIMIT}
exec(WIRE, wire)
encoded, digest = wire["encoded"], wire["digest"]
parser = {"json": json}
exec(JSON_PARSER, parser)


class World:
    def __init__(self, profile="desktop", role="linux-x64"):
        self.local, self.raw_ns = 100.0, 1000 * SECOND
        self.reads, self.cancellations = [], 0
        self.read_hook = self.verify_hook = self.names_hook = self.clock_hook = self.cancel_hook = noop
        clock_ns = {"dataclass": dataclass, "__name__": __name__}
        exec(CLOCK, clock_ns)
        self.clocks = NS(**clock_ns)
        self.clock = self.clocks.ClockIdentity(role, self.clocks.DOMAINS[role], SECOND)
        self.first = self.clocks.Reading(self.clock, self.raw_ns)
        self.selection = profile + "-" + role
        session = Path("/model/private") / ("p2pkit-cache-originals-123-1-" + self.selection + "-productive") / "initializer"
        self.session, self.path = session, session / "dependency-save-handoff"
        self.admission = {"source": {"commit": "a" * 40, "tree": "b" * 40},
            "github": {"repository": "p2pKit/P2pKit", "runId": "123", "runAttempt": "1"},
            "selection": self.selection, "cacheCohort": {"profile": profile, "role": role}}
        self.admitted = NS(record=encoded(self.admission))
        self.origin = NS(require=require, OriginError=Refusal, encoded=encoded, digest=digest,
            parse=lambda raw: parser["parse"](raw, LIMIT), clocks=self.clocks,
            clock_value=lambda value: {"role": self.clocks.validate_identity(value).role,
                "domain": value.domain, "ticksPerSecond": value.ticks_per_second})
        self.origin.admitted_value = lambda value: deepcopy(self.admission) if value is self.admitted else None
        integer = {"require": require, "clocks": self.clocks}
        exec(INTEGER, integer)
        self.origin.integer = integer["integer"]
        files = {"require": require, "Path": Path}
        exec(FILES, files)
        self.files = NS(**files, PREFIX=("caches", "modules-2", "files-2.1"), encoded=encoded)
        cache = {"require": require, "re": re, "files": self.files}
        exec(CACHE, cache)
        local = {"require": require, "math": math}
        exec(LOCAL, local)
        self.staging = NS(files=self.files, cache=NS(**cache), _local=local["_local"], NS=SECOND,
            STAGE_SCOPE="BOOTSTRAP_EMPTY_STAGING_LEAF_V1", SEED_SCOPE="BOOTSTRAP_KNOWN_EMPTY_SEED_LEAF_V1")
        self.proposal_scope = "BOOTSTRAP_ALLOCATION_SOURCE_PROPOSAL_V1"
        self.leaf_scopes = {"before-leaf.json": "BOOTSTRAP_SAVE_SET_BEFORE_LEAF_V1",
            "export-leaf.json": "BOOTSTRAP_DEPENDENCY_EXPORT_LEAF_V1", "stage-leaf.json": self.staging.STAGE_SCOPE,
            "seed-leaf.json": self.staging.SEED_SCOPE}
        world = self

        class Fence:
            # Deliberately deadline-only: the reader must forward Owner.cancelled.
            def __init__(self):
                self.clock, self.last, self.hard = world.clock, world.raw_ns, 1040 * SECOND

            def deadline(self, maximum, *, final=False, limit=None):
                world.clock_hook()
                require(world.raw_ns >= self.last, "MODEL_RAW_BACKWARDS")
                self.last = world.raw_ns
                require(self.last < min(self.hard, self.hard if limit is None else limit), "MODEL_RAW_EXPIRED")
                return min(140.0, world.local + maximum)

            def now(self, **kwargs):
                self.deadline(45, **kwargs)
                return self.last

        class Directory:
            def __init__(self, path, identity):
                self.path, self.identity, self.original_identity = path, identity, identity
                self.closes = 0

            def verify(self):
                world.verify_hook(self)
                require(self.closes == 0 and self.identity == self.original_identity, "MODEL_DIRECTORY_CHANGED")

            def read_bytes(self, name, *, max_bytes, deadline):
                self.verify()
                world.reads.append((self.path, name, max_bytes))
                world.read_hook(self, name)
                require(self is world.directory and world.local < deadline, "MODEL_READ_BOUNDARY")
                raw = world.blobs[name]
                require(len(raw) <= max_bytes, "MODEL_READ_LIMIT")
                return raw

            def names(self, *, max_names, deadline):
                world.names_hook(self)
                require(world.local < deadline and len(world.blobs) <= max_names, "MODEL_NAMES_LIMIT")
                return tuple(world.blobs)

            def close(self):
                self.closes += 1

        class Listing:
            def __init__(self, path):
                require(path == world.path, "MODEL_NO_REFERENCE_TRAVERSAL")

            def __enter__(self):
                world.names_hook(world.directory)
                return iter(NS(name=name) for name in world.blobs)

            def __exit__(self, *_args):
                pass

        self.namespace = {"require": require, "origin": self.origin, "math": math, "re": re, "LIMIT": LIMIT,
            "time": NS(monotonic=lambda: self.local), "os": NS(scandir=Listing),
            "posix": NS(_deadline=lambda end: require(self.local < end, "MODEL_LOCAL_EXPIRED")),
            "query": NS(QUARANTINE=[]), "QUARANTINE": [],
            "diagnostics": NS(_QUARANTINE=[], _exception_detail=lambda error: {"retirementUnknown": False}),
            "staging": self.staging, "allocation": NS(SCOPE=self.proposal_scope),
            "bootstrap": NS(cache_cohort=lambda raw: (profile, role)),
            "dependency_save_set": NS(SCOPE=self.leaf_scopes["before-leaf.json"]),
            "dependency_export": NS(SCOPE=self.leaf_scopes["export-leaf.json"])}
        exec(RUNNER, self.namespace)
        self.fence = Fence()

        def cancel():
            self.cancellations += 1
            self.cancel_hook()

        self.owner = self.namespace["Owner"](140.0, self.fence, first=self.first, cancelled=cancel)
        identity = lambda i: (1, format(i, "032x") if role == "windows-x64" else i)
        self.initializer, self.directory = Directory(session, identity(10)), Directory(self.path, identity(11))
        for directory in (self.initializer, self.directory):
            self.owner.resources.append({"label": "directory", "owner": directory, "attempted": False, "closed": False})
        container = self.files.stage_path(session, profile, role)
        clock = self.origin.clock_value(self.clock)
        self.proposal = {**deepcopy(self.admission), "schema": 1, "scope": self.proposal_scope, "clock": clock,
            "phaseFencesNs": {"producer-owner-return": 1050 * SECOND}, "proposedJobEndNs": 1100 * SECOND,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        self.plan = {"schema": 1, "scope": "DEPENDENCY_CACHE_PLAN_V1", "mode": "bootstrap", "profile": profile,
            "role": role, "source": self.admission["source"], "github": self.admission["github"],
            "admissionSha256": digest(self.admitted.record), "stagingSha256": "c" * 64,
            "session": str(session), "restoreHome": str(container / "restore-home"),
            "path": str(container / "restore-home/caches/modules-2/files-2.1"),
            "inputs": {"allowlistSha256": "d" * 64, "files": {name: "e" * 64 for name in self.files.INPUTS}},
            "key": "p2pkit-dependency-files-v1-" + profile + "-" + role + "-" + "d" * 64 + "-" + "e" * 64,
            "provider": {"restore": "actions/cache/restore@caa296126883cff596d87d8935842f9db880ef25",
                "save": "actions/cache/save@caa296126883cff596d87d8935842f9db880ef25",
                "restoreKeys": [], "enableCrossOsArchive": False}}
        self.binding = {"admissionSha256": digest(self.admitted.record), "proposalSha256": digest(encoded(self.proposal)),
            "session": str(session), "state": str(session / "state"), "home": str(session / "state/gradle-home"),
            "container": str(container), "restoreHome": self.plan["restoreHome"], "clock": clock,
            "initializerDirectories": {"session": list(self.initializer.identity)}}
        self.blobs = {name: encoded({"opaqueModeledOriginal": name}) for name in NAMES}
        self.blobs["allocation-proposal.json"] = encoded(self.proposal)
        for name, scope in self.leaf_scopes.items():
            self.blobs[name] = encoded({"scope": scope, "binding": self.binding, "plan": self.plan})
        before_leaf = json.loads(self.blobs["before-leaf.json"])
        before_leaf["exportSha256"] = digest(self.blobs["export-leaf.json"])
        self.blobs["before-leaf.json"] = encoded(before_leaf)
        for name, scope, leaf in (("export-parent.json", "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1", "export-leaf.json"),
                ("before-parent.json", "BOOTSTRAP_SAVE_SET_PARENT_CLOSED_OBSERVATIONS_V1", "before-leaf.json")):
            value = {"scope": scope, "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "clock": clock,
                "leafSha256": digest(self.blobs[leaf]), "firstNs": 900 * SECOND, "closedNs": 980 * SECOND,
                "hardEndNs": 1020 * SECOND, "nextPhaseAuthority": False, "exportSaveAuthority": False,
                "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED"}
            if name == "before-parent.json":
                value["exportParentSha256"] = digest(self.blobs["export-parent.json"])
            self.blobs[name] = encoded(value)
        self.value = {"schema": 1, "scope": "BOOTSTRAP_SAVE_HANDOFF_PENDING_ORIGINAL_STEP_RETURN_V1",
            **deepcopy(self.admission), "binding": self.binding, "plan": self.plan, "planSha256": digest(encoded(self.plan)),
            "directory": str(self.path), "directoryIdentity": list(self.directory.identity),
            "blobs": {}, "references": {"opaque": {"directory": "/must/not/read", "name": "../private"}},
            "chain": {"returns": {"before": {"checkedNs": 985 * SECOND, "checkedLocal": 80.0}}},
            "window": {"phase": "producer-owner-return", "clock": clock, "firstNs": 990 * SECOND,
                "hardEndNs": 1035 * SECOND, "predecessorCheckedNs": 985 * SECOND,
                "predecessorSha256": digest(self.blobs["before-parent.json"])},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
            "nextPhaseAuthority": False, "exportSaveAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED"}
        self.refresh()

    def refresh(self):
        self.value["blobs"] = {name: {"bytes": len(self.blobs[name]), "sha256": digest(self.blobs[name])} for name in NAMES}
        self.reindex()

    def reindex(self):
        self.blobs["save-handoff.json"] = encoded(self.value)
        self.expected = digest(self.blobs["save-handoff.json"])

    def change_blob(self, name, change):
        value = json.loads(self.blobs[name])
        change(value)
        self.blobs[name] = encoded(value)
        self.refresh()

    def run(self, **kwargs):
        return self.namespace["_read_save_handoff"](self.owner, self.initializer, self.directory, self.admitted,
            producer_outcome=kwargs.pop("producer_outcome", "success"),
            expected_sha256=kwargs.pop("expected_sha256", self.expected), **kwargs)


class ReaderModels(unittest.TestCase):
    def test_valid_selected_shapes_return_exact_bytes_without_new_owner_or_close(self):
        world = World()
        ledger, first, fence = tuple(world.owner.resources), world.owner.first, world.owner.fence
        raw, blobs = world.run()
        self.assertEqual(raw, world.blobs["save-handoff.json"])
        self.assertEqual(blobs, tuple((name, world.blobs[name]) for name in NAMES))
        self.assertEqual(len(world.reads), 64)
        self.assertEqual(tuple(world.owner.resources), ledger)
        self.assertIs(world.owner.first, first)
        self.assertIs(world.owner.fence, fence)
        self.assertEqual(world.owner.local_end, 140.0)
        self.assertFalse(world.owner.closed or world.owner.unknown)
        self.assertEqual((world.initializer.closes, world.directory.closes), (0, 0))
        self.assertTrue(all(path == world.path for path, _name, _limit in world.reads))

    def test_windows_and_full_macos_are_data_models_not_platform_execution(self):
        for profile, role in (("desktop", "windows-x64"), ("full", "macos-arm64"), ("full", "macos-x64")):
            with self.subTest(profile=profile, role=role):
                world = World(profile, role)
                self.assertEqual(len(world.run()[1]), 31)

    def test_unsuccessful_outcomes_refuse_before_any_read(self):
        for outcome in ("", "failure", "cancelled", "skipped", "neutral", "Success", None, True, {"conclusion": "success"}):
            world = World()
            with self.subTest(outcome=outcome), self.assertRaisesRegex(Refusal, "PRODUCER_OUTCOME"):
                world.run(producer_outcome=outcome)
            self.assertEqual(world.reads, [])

    def test_missing_malformed_or_uppercase_hash_refuses_before_reads(self):
        for sha in (None, "", "a" * 63, "A" * 64, "g" * 64, True):
            world = World()
            with self.subTest(sha=sha), self.assertRaisesRegex(Refusal, "ORIGINAL_HASH"):
                world.run(expected_sha256=sha)
            self.assertEqual(world.reads, [])

    def test_digest_is_separate_input_not_read_back_from_the_package(self):
        world = World()
        with self.assertRaisesRegex(Refusal, "HASH_CHANGED"):
            world.run(expected_sha256="0" * 64)
        self.assertEqual(len(world.reads), 1)

    def test_index_is_closed_canonical_and_cannot_claim_authority(self):
        changes = {"extra": True, "schema": True, "scope": "accepted", "writerReturn": "SUCCESS",
            "providerExecution": "PERFORMED", "nextPhaseAuthority": True, "exportSaveAuthority": 0,
            "budgetAcceptance": "ADMITTED", "testAcceptance": "PASSED", "references": [], "chain": []}
        for key, value in changes.items():
            world = World()
            world.value[key] = value
            world.reindex()
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, "READ_INDEX"):
                world.run()

    def test_noncanonical_or_duplicate_index_keys_refuse(self):
        for mutate in (lambda raw: b" " + raw, lambda raw: raw.replace(b'"schema":1', b'"schema":1,"schema":1')):
            world = World()
            world.blobs["save-handoff.json"] = mutate(world.blobs["save-handoff.json"])
            with self.subTest(mutate=mutate), self.assertRaises((Refusal, parser["AdmissionError"])):
                world.run(expected_sha256=digest(world.blobs["save-handoff.json"]))

    def test_source_run_attempt_selection_cohort_must_match_supplied_admission(self):
        for key, change in (("source", {"commit": "c" * 40, "tree": "b" * 40}),
                ("github", {"runId": "124", "runAttempt": "1"}),
                ("github", {"repository": "p2pKit/P2pKit", "runId": "123", "runAttempt": "2"}),
                ("selection", "full-macos-arm64"), ("cacheCohort", {"profile": "full", "role": "macos-arm64"})):
            world = World()
            world.value[key] = change
            world.reindex()
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, "READ_BINDING"):
                world.run()

    def test_plan_mode_path_source_run_and_admission_hash_are_checked(self):
        for key, value in (("mode", "consume"), ("source", {"commit": "c" * 40, "tree": "b" * 40}),
                ("github", {}), ("admissionSha256", "f" * 64), ("session", "/other"),
                ("restoreHome", "/other"), ("path", "/other")):
            world = World()
            world.plan[key] = value
            world.value["planSha256"] = digest(encoded(world.plan))
            world.reindex()
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, "READ_BINDING"):
                world.run()

    def test_existing_plan_shape_guard_keeps_provider_key_and_cohort_policy(self):
        for change in (lambda plan: plan.update(key="other"),
                       lambda plan: plan["provider"].update(enableCrossOsArchive=True),
                       lambda plan: plan["provider"].update(restoreKeys=["fallback"]),
                       lambda plan: plan.update(profile="full", role="linux-x64")):
            world = World()
            change(world.plan)
            world.reindex()
            with self.assertRaisesRegex(Refusal, "CACHE_"):
                world.run()

    def test_plan_digest_and_binding_paths_are_not_sufficient_when_changed(self):
        for key in ("planSha256", "session", "state", "home", "container", "restoreHome", "admissionSha256"):
            world = World()
            (world.value if key == "planSha256" else world.binding)[key] = "f" * 64
            world.reindex()
            with self.subTest(key=key), self.assertRaisesRegex(Refusal, "READ_BINDING"):
                world.run()

    def test_each_repeated_leaf_plan_binding_and_scope_is_compared(self):
        for name in ("stage-leaf.json", "seed-leaf.json", "export-leaf.json", "before-leaf.json"):
            for field, value in (("scope", "other"), ("binding", {}), ("plan", {})):
                world = World()
                world.change_blob(name, lambda leaf: leaf.update({field: value}))
                with self.subTest(name=name, field=field), self.assertRaisesRegex(Refusal, "READ_(BINDING|LEAF_SCOPE)"):
                    world.run()

    def test_parent_close_flags_leaf_links_and_export_parent_link_are_checked(self):
        for name, field, value in (("before-parent.json", "parentResourceClose", "UNKNOWN"),
                ("export-parent.json", "exportSaveAuthority", True),
                ("before-parent.json", "leafSha256", "0" * 64),
                ("export-parent.json", "leafSha256", "0" * 64),
                ("before-parent.json", "exportParentSha256", "0" * 64),
                ("before-leaf.json", "exportSha256", "0" * 64)):
            world = World()
            world.change_blob(name, lambda leaf: leaf.update({field: value}))
            with self.subTest(name=name, field=field), self.assertRaisesRegex(Refusal, "READ_(BINDING|PARENT)"):
                world.run()

    def test_proposal_hash_source_and_non_authority_are_checked(self):
        for change in (lambda value: value.update(scope="other"), lambda value: value.update(exportSaveAuthority=True),
                       lambda value: value.update(source={"commit": "f" * 40, "tree": "b" * 40})):
            world = World()
            world.change_blob("allocation-proposal.json", change)
            world.binding["proposalSha256"] = digest(world.blobs["allocation-proposal.json"])
            world.reindex()
            with self.assertRaisesRegex(Refusal, "READ_(PROPOSAL|BINDING)"):
                world.run()
        world = World()
        world.change_blob("allocation-proposal.json", lambda value: value.update(opaqueExtra=1))
        with self.assertRaisesRegex(Refusal, "READ_BINDING"):
            world.run()

    def test_declared_blob_roster_is_exact_not_json_selected(self):
        for add in (True, False):
            world = World()
            if add:
                world.value["blobs"]["../outside"] = world.value["blobs"][NAMES[0]]
            else:
                del world.value["blobs"][NAMES[0]]
            world.reindex()
            with self.assertRaisesRegex(Refusal, "BLOB_ROSTER"):
                world.run()

    def test_live_missing_extra_or_case_aliased_members_refuse(self):
        for operation in ("missing", "extra", "alias"):
            world = World()
            if operation == "missing":
                del world.blobs[NAMES[0]]
            else:
                if operation == "alias":
                    del world.blobs[NAMES[-1]]  # Keep32 names so casefold, not the count, refuses.
                world.blobs[NAMES[0].upper() if operation == "alias" else "extra"] = b"extra"
            with self.subTest(operation=operation), self.assertRaisesRegex(Refusal, "(DIRECTORY_ROSTER|DIRECTORY_LIMIT|ALIASES)"):
                world.run()

    def test_declared_sizes_types_hashes_and_extra_blob_fields_refuse(self):
        for field, value in (("bytes", True), ("bytes", 0), ("bytes", LIMIT + 1), ("sha256", "A" * 64), ("extra", 0)):
            world = World()
            world.value["blobs"][NAMES[0]][field] = value
            world.reindex()
            with self.subTest(field=field, value=value), self.assertRaisesRegex(Refusal, "BLOB_BINDING"):
                world.run()

    def test_changed_blob_bytes_refuse_even_when_size_matches(self):
        world = World()
        raw = world.blobs["producer-command.json"]
        world.blobs["producer-command.json"] = raw.replace(b"producer", b"modified")
        with self.assertRaisesRegex(Refusal, "BLOB_CHANGED"):
            world.run()

    def test_changed_or_short_blob_size_refuses(self):
        world = World()
        world.blobs["producer-command.json"] = b"{}"
        with self.assertRaisesRegex(Refusal, "BLOB_CHANGED"):
            world.run()

    def test_reread_detects_late_member_and_index_changes(self):
        for selected_name in ("producer-command.json", "save-handoff.json"):
            world = World()
            seen = []

            def mutate(_directory, name):
                seen.append(name)
                if name == selected_name and seen.count(name) == 2:
                    world.blobs[name] = b"{}"

            world.read_hook = mutate
            with self.subTest(name=selected_name), self.assertRaisesRegex(Refusal, "(REREAD_CHANGED|INDEX_CHANGED)"):
                world.run()

    def test_final_listing_detects_members_added_after_initial_enumeration(self):
        world = World()
        world.read_hook = lambda _directory, name: world.blobs.update(extra=b"extra") if name == NAMES[-1] else None
        with self.assertRaisesRegex(Refusal, "DIRECTORY_LIMIT"):
            world.run()

    def test_only_registered_unclosed_borrowed_directories_are_accepted(self):
        for field, value in (("label", "other"), ("attempted", True), ("closed", True)):
            world = World()
            world.owner.resources[1][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(Refusal, "NOT_OWNED"):
                world.run()
            self.assertEqual(world.reads, [])

    def test_directory_layout_and_recorded_identities_must_match(self):
        for change in (lambda world: setattr(world.directory, "path", world.session / "other"),
                       lambda world: world.value.update(directory="/other"),
                       lambda world: world.value.update(directoryIdentity=[1, 900]),
                       lambda world: world.binding["initializerDirectories"].update(session=[1, 900])):
            world = World()
            change(world)
            world.reindex()
            with self.assertRaisesRegex(Refusal, "READ_(LAYOUT|BINDING)"):
                world.run()

    def test_live_directory_replacement_during_reads_refuses(self):
        for kind in ("initializer", "directory"):
            world = World()
            world.read_hook = lambda _directory, _name: setattr(getattr(world, kind), "identity", (1, 900))
            with self.subTest(kind=kind), self.assertRaisesRegex(Refusal, "DIRECTORY_CHANGED"):
                world.run()

    def test_aliased_parent_and_handoff_refuse(self):
        world = World()
        world.directory.identity = world.initializer.identity
        with self.assertRaisesRegex(Refusal, "DIRECTORY_ALIAS"):
            world.run()

    def test_bound_owner_cancellation_is_not_delegated_to_deadline_only_fence(self):
        world = World()
        failure = KeyboardInterrupt("modeled cancellation")
        world.cancel_hook = lambda: (_ for _ in ()).throw(failure)
        with self.assertRaises(KeyboardInterrupt) as caught:
            world.run()
        self.assertIs(caught.exception, failure)
        self.assertIs(world.owner.original, failure)
        self.assertEqual(world.reads, [])
        self.assertEqual(world.cancellations, 1)

    def test_late_cancellation_during_final_checks_does_not_return_bytes(self):
        world = World()
        failure = KeyboardInterrupt("modeled late cancellation")

        def cancel():
            if len(world.reads) == 64:
                raise failure

        world.cancel_hook = cancel
        with self.assertRaises(KeyboardInterrupt) as caught:
            world.run()
        self.assertIs(caught.exception, failure)
        self.assertFalse(world.owner.closed)

    def test_reader_does_not_replace_or_extend_borrowed_owner_pins(self):
        for name, change in (("first", lambda world: replace(world.owner.first)),
                ("fence", lambda world: NS(clock=world.clock, deadline=world.fence.deadline)),
                ("resources", lambda world: list(world.owner.resources)),
                ("local_end", lambda world: 141.0), ("work_limit", lambda world: 1100 * SECOND),
                ("cancelled", lambda world: noop)):
            world = World()
            world.read_hook = lambda _directory, _name: setattr(world.owner, name, change(world))
            with self.subTest(name=name), self.assertRaisesRegex(Refusal, "OWNER_CHANGED"):
                world.run()

    def test_expiry_backward_clock_and_original_limits_refuse(self):
        for change, reason in ((lambda world: setattr(world, "local", 140.0), "LOCAL_EXPIRED"),
                (lambda world: setattr(world, "raw_ns", 1040 * SECOND), "RAW_EXPIRED"),
                (lambda world: setattr(world, "raw_ns", 999 * SECOND), "RAW_BACKWARDS")):
            world = World()
            change(world)
            with self.subTest(reason=reason), self.assertRaisesRegex(Refusal, reason):
                world.run()
            self.assertFalse(world.owner.closed)

    def test_recorded_window_cannot_renew_or_rewrite_predecessor_floors(self):
        for field, value in (("phase", "save-readmission"), ("predecessorSha256", "0" * 64),
                ("predecessorCheckedNs", 980 * SECOND), ("firstNs", 984 * SECOND),
                ("hardEndNs", 1036 * SECOND)):
            world = World()
            world.value["window"][field] = value
            world.reindex()
            with self.subTest(field=field), self.assertRaisesRegex(Refusal, "READ_(WINDOW|BINDING|RECORDED_CHRONOLOGY)"):
                world.run()

    def test_reader_first_must_not_precede_recorded_writer_start(self):
        world = World()
        world.owner.first = replace(world.first, nanoseconds=989 * SECOND)
        with self.assertRaisesRegex(Refusal, "RECORDED_CHRONOLOGY"):
            world.run()

    def test_historical_local_floor_is_not_compared_across_processes(self):
        world = World()
        world.value["chain"]["returns"]["before"]["checkedLocal"] = 1_000_000.0
        world.reindex()
        self.assertEqual(world.run()[0], world.blobs["save-handoff.json"])

    def test_closed_failed_unknown_or_global_quarantined_owner_cannot_read(self):
        for state in ("closed", "unknown", "local-quarantine", "query-quarantine", "native-quarantine"):
            world = World()
            if state in ("closed", "unknown"):
                setattr(world.owner, state, True)
            elif state == "local-quarantine":
                world.namespace["QUARANTINE"].append(object())
            elif state == "query-quarantine":
                world.namespace["query"].QUARANTINE.append(object())
            else:
                world.namespace["diagnostics"]._QUARANTINE.append(object())
            with self.subTest(state=state), self.assertRaisesRegex(Refusal, "(NOT_LIVE|PRIOR_UNKNOWN)"):
                world.run()
            self.assertEqual(world.reads, [])

    def test_falsey_original_failure_is_not_replaced_by_reader_failure(self):
        world = World()
        failure = FalseyFailure()
        world.owner.original = failure
        with self.assertRaises(FalseyFailure) as caught:
            world.run()
        self.assertIs(caught.exception, failure)
        self.assertIs(world.owner.original, failure)

    def test_failed_private_read_is_unknown_and_caller_still_owns_cleanup(self):
        world = World()
        failure = OSError("modeled read uncertainty")
        world.read_hook = lambda *_args: (_ for _ in ()).throw(failure)
        with self.assertRaises(OSError) as caught:
            world.run()
        self.assertIs(caught.exception, failure)
        self.assertTrue(world.owner.unknown)
        self.assertFalse(world.owner.closed)
        self.assertEqual((world.initializer.closes, world.directory.closes), (0, 0))
        with self.assertRaisesRegex(Refusal, "RETIREMENT_UNKNOWN"):
            world.owner.close()
        self.assertIs(world.namespace["QUARANTINE"][0], world.owner)

    def test_successful_read_is_not_successful_enclosing_owner_close(self):
        world = World()
        world.run()
        failure = OSError("modeled close uncertainty")
        world.directory.close = lambda: (_ for _ in ()).throw(failure)
        with self.assertRaisesRegex(Refusal, "RETIREMENT_UNKNOWN"):
            world.owner.close()
        self.assertIs(world.owner.original, failure)
        self.assertTrue(world.owner.unknown)

    def test_consistent_supplied_package_does_not_gain_unrecorded_authority(self):
        world = World()
        value = json.loads(world.run()[0])
        self.assertEqual(value["references"], {"opaque": {"directory": "/must/not/read", "name": "../private"}})
        self.assertEqual(world.blobs["producer-parent.json"], encoded({"opaqueModeledOriginal": "producer-parent.json"}))
        self.assertEqual(value["writerReturn"], "PENDING_NOT_OBSERVABLE_BY_THIS_FILE")
        self.assertEqual(value["providerExecution"], "NOT_PERFORMED")
        self.assertFalse(value["nextPhaseAuthority"] or value["exportSaveAuthority"])
        self.assertNotIn("handoff", value["chain"]["returns"])
        self.assertFalse(world.owner.closed)


if __name__ == "__main__":
    unittest.main()
