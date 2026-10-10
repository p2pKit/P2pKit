#!/usr/bin/env python3
"""Focused history-predicate DATA controls, not a reader/owner qualification.

Only selected, source-validated pure functions are compiled. No project module,
old fixture, CLI, reader, owner constructor, native library or provider is
imported/executed. Record classes below are inert exact-type model shells, NOT
original returns or reconstructed owners. Paths, stamps and bytes are supplied
in memory; no modeled pathname is opened.

Normal invocation retains fifteen predicate controls and adds eight current
builder controls. Separately select --measure-baseline /absolute/public-source-bfc7.py
for ONE fixed AB,BA,AB,BA
measurement, 64 whole-bank passes per side/block, without tuning or retries.
Both sides use bfc7's unchanged checker; each builds its own original/compact
snapshot graphs. The older6006 checker remains only an untimed negative-control
reference, never the performance baseline for this repair.
The caller must impose CPU60/wall90 and bind the candidate commit/tree plus
this file's hash before execution. A >=10% aggregate CPU reduction is only a
model-cost decision, never a CI timing test or proof of hosted schedule fit.
"""
from __future__ import annotations

import argparse
import ast
import builtins
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import time
from types import SimpleNamespace
import unittest


BASELINE_SHA256 = "ac94a3b81825b7bdbc0743fe576d76b1f9989b7b14701e8aebe7c8369909dd33"
BFC7_SHA256 = "ac24be2d2010703ae934cf44769348f63374f61ad9f351b0ea97221806c2fda5"
BUILDER_SHA256 = "5c7ca21eef9fb974e249069e9d53fd843854eb2d3346f5e11f0527ad53e867a5"
OLD_CHECKER_SHA256 = "727a22e06964a9bd13995e444a4ee7c863e56912572f8644928cd4ef3784953f"
SOURCE_PINS = {
    # Failure-only owner-ledger dispatch preserves the predicate and aliases;
    # selected require/_snapshot_metadata bytes still match 38035f8d. Adopt the
    # whole supplier only after both reviews; strict equality is unchanged.
    "run-hosted-initial-recipient-custody.py":
        "e40f507b256cb062d411f0cb3295a775b9605683594f54a3eb763ded168d9580",
    "hosted_test_identity.py": "07faeecd034439ea82dd2b05bcfd2f9ce4d6a44117b959b855d2c39651d3b770",
    "hosted_test_query.py": "d3b6aa5c6dd95b9c05c829f5b15de40f35ddbfa763d93031cb25fe596b463ca7",
    "hosted_full_job_budget.py": "95fb79e994746e85439446d39a49017fefa782d2b7182523db4ad1f2b071b1a3",
}
MAIN_NAME = "run-hosted-initial-recipient.py"
CUSTODY_NAME = "run-hosted-initial-recipient-custody.py"
ORDERS = ("AB", "BA", "AB", "BA")
ITERATIONS = 64
MINIMUM_IMPROVEMENT_PERCENT = 10

# Exact independent6006 preimage, including its final newline. This is not
# produced by reversing the candidate's AST or by calling its implementation.
OLD_CHECKER = '''def _check_history(nodes):
    scalars = (type(None), bool, int, float, str, bytes)
    def same(value, saved):
        return value is saved or type(value) is type(saved) and type(saved) in scalars and value == saved
    for value, kind, mode, saved in nodes:
        require(type(value) is kind, "RECIPIENT_HISTORY_CHANGED")
        if mode == "record":
            valid = object.__getattribute__(value, "__dict__") is saved
        elif mode == "mapping":
            valid = len(value) == len(saved) and all(same(key, old_key) and same(item, old_item)
                for (key, item), (old_key, old_item) in zip(value.items(), saved))
        elif mode == "sequence":
            valid = len(value) == len(saved) and all(same(item, old) for item, old in zip(value, saved))
        elif mode == "path":
            valid = (str(value), value.parts, value.drive, value.root) == saved
        else:
            valid = mode == "opaque"
        require(valid, "RECIPIENT_HISTORY_CHANGED")
'''
OLD_SEQUENCE = "valid = len(value) == len(saved) and all(same(item, old) for item, old in zip(value, saved))"
NEW_SEQUENCE = ("valid = (kind is tuple and value is saved) or (len(value) == len(saved) and\n"
    "                all(same(item, old) for item, old in zip(value, saved)))")
# Independent original builder from reviewed bfc7, not reconstructed from the
# candidate. The unchanged visited-object bound includes every exact tuple.
OLD_BUILDER = '''def _history_graph(*roots):
    """Finite pins of the closed Stage1 records, not a live reader or object codec."""
    records = (_ReadmissionReturn, _ReadmissionBinding, _ReadmissionClaim, _PreparationBinding,
        _OriginalPreparation, _OriginalServiceJobAdmission, _EntryWindowBinding, _ReadmissionWindow, SourceReturn, native.Owner,
        native.OriginalPhase, O.Fence, O.clocks.Reading, O.clocks.ClockIdentity,
        initial_identity.InitialBootstrapIdentity, acquisition.stages.BootstrapMatch,
        _AuthorityReturn, _AuthorityState, _RecipientRoster, _RecipientNativeReturn, _RecipientValidationReturn,
        _RecipientState, _RecipientCryptoOriginals)
    scalars = (type(None), bool, int, float, str, bytes)
    pending, seen, nodes = list(roots), set(), []
    while pending:
        value = pending.pop()
        kind = type(value)
        if kind in scalars or id(value) in seen:
            continue
        seen.add(id(value))
        require(len(seen) <= 10000, "RECIPIENT_HISTORY_LIMIT")
        if kind is dict:
            saved, mode = tuple(value.items()), "mapping"
            require(all(type(key) in scalars for key, _ in saved), "RECIPIENT_HISTORY_KEY")
            pending.extend(item for pair in saved for item in pair)
        elif kind in (tuple, list):
            saved, mode = tuple(value), "sequence"
            pending.extend(saved)
        elif kind in records:
            saved, mode = object.__getattribute__(value, "__dict__"), "record"
            pending.append(saved)
        elif kind is type(ROOT):
            saved, mode = (str(value), value.parts, value.drive, value.root), "path"
        else:
            saved, mode = None, "opaque"  # Callbacks/retired resources: reference only, never invoked.
        nodes.append((value, kind, mode, saved))
    return tuple(nodes)
'''
OLD_BUILDER_SEQUENCE = '''        elif kind in (tuple, list):
            saved, mode = tuple(value), "sequence"
            pending.extend(saved)
'''
NEW_BUILDER_SEQUENCE = '''        elif kind is tuple:
            pending.extend(value)
            continue
        elif kind is list:
            saved, mode = tuple(value), "sequence"
            pending.extend(saved)
'''
PURE_BUILTINS = {name: getattr(builtins, name) for name in (
    "all", "bool", "bytes", "dict", "float", "hasattr", "id", "int", "len", "list",
    "object", "set", "sorted", "str", "tuple", "type", "zip")}


def insist(value, code):
    if not value:
        raise AssertionError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def install_audit(paths):
    allowed = frozenset(os.path.abspath(os.fspath(path)) for path in paths)
    writes = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def audit(event, args):
        if event == "open":
            path, mode, flags = args
            if (not isinstance(path, (str, bytes)) or
                    os.path.abspath(os.fsdecode(path)) not in allowed or
                    flags & writes or mode is not None and mode not in ("r", "rb")):
                raise RuntimeError("HISTORY_MODEL_SOURCE_READS_ONLY")
        elif event == "import" or event.startswith(("subprocess.", "socket.")) or event in (
                "ctypes.dlopen", "ctypes.dlsym", "os.system", "os.exec", "os.posix_spawn",
                "os.fork", "os.forkpty", "pty.spawn", "os.listdir", "os.scandir", "os.chdir",
                "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink",
                "os.chmod", "os.chown", "os.truncate", "os.utime", "builtins.input"):
            raise RuntimeError("HISTORY_MODEL_IMPORT_PROCESS_NETWORK_FILESYSTEM_FORBIDDEN")

    sys.addaudithook(audit)


def read_public(path):
    # Explicit public source only; no path discovery, provider or model I/O.
    before = path.lstat()
    insist(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= 2 * 1024 * 1024,
        "PUBLIC_SOURCE_REGULAR_BOUNDED")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        opened = os.fstat(descriptor)
        insist((opened.st_dev, opened.st_ino, opened.st_size) ==
            (before.st_dev, before.st_ino, before.st_size), "PUBLIC_SOURCE_IDENTITY")
        pieces, remaining = [], before.st_size
        while remaining:
            piece = os.read(descriptor, min(remaining, 65536))
            insist(piece, "PUBLIC_SOURCE_SHORT_READ")
            pieces.append(piece)
            remaining -= len(piece)
        insist(os.read(descriptor, 1) == b"", "PUBLIC_SOURCE_EOF")
        after = os.fstat(descriptor)
        insist((after.st_size, after.st_mtime_ns, after.st_ctime_ns) ==
            (opened.st_size, opened.st_mtime_ns, opened.st_ctime_ns), "PUBLIC_SOURCE_CHANGED")
        return b"".join(pieces)
    finally:
        os.close(descriptor)


def selected(text, filename, name):
    tree = ast.parse(text, filename=filename)
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    insist(len(nodes) == 1, "ONE_SELECTED_PURE_FUNCTION")
    node = nodes[0]
    insist(not node.decorator_list and not node.args.defaults and not node.args.kw_defaults,
        "NO_SELECTED_DEFINITION_CALLBACK")
    insist(not any(isinstance(item, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal))
        for item in ast.walk(node)), "NO_SELECTED_IMPORT_OR_GLOBAL_WRITE")
    lines = text.splitlines(keepends=True)
    return node, "".join(lines[node.lineno - 1:node.end_lineno])


def compile_function(node, filename, environment):
    # The restricted namespace has no open, import, eval, exec, native or CLI.
    environment["__builtins__"] = PURE_BUILTINS
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, "exec", dont_inherit=True), environment)
    return environment[node.name]


class AdmissionError(ValueError):
    """Model error type used by the unchanged maintained require function."""


class QueryError(RuntimeError):
    pass


class BudgetError(ValueError):
    pass


class Sources:
    def __init__(self, root, own_path, baseline=None):
        self.paths = {name: root / "scripts" / name for name in (MAIN_NAME, *SOURCE_PINS)}
        self.raw = {name: read_public(path) for name, path in self.paths.items()}
        for name, expected in SOURCE_PINS.items():
            insist(sha(self.raw[name]) == expected, "UNCHANGED_PURE_DEPENDENCY:" + name)
        self.text = {name: raw.decode("utf-8") for name, raw in self.raw.items()}
        self.pins = {"candidate": sha(self.raw[MAIN_NAME]), "controls": sha(read_public(own_path)),
            "custody": sha(self.raw[CUSTODY_NAME]), "baseline": BFC7_SHA256,
            "historicalPredicateBaseline": BASELINE_SHA256,
            "pureDependencies": dict(SOURCE_PINS)}
        self.cache = {}
        self.old_node, old_fragment = selected(OLD_CHECKER, "<independent6006-history>", "_check_history")
        insist(sha(old_fragment.encode("utf-8")) == OLD_CHECKER_SHA256, "INDEPENDENT_OLD_PREDICATE_PIN")
        candidate, fragment = self.function(MAIN_NAME, "_check_history")
        expected, _ = selected(OLD_CHECKER.replace(OLD_SEQUENCE, NEW_SEQUENCE),
            "<approved-tuple-identity-predicate>", "_check_history")
        insist(ast.dump(candidate) == ast.dump(expected), "ONLY_APPROVED_PREDICATE_AST")
        original_builder, original_fragment = selected(OLD_BUILDER, "<independent-bfc7-builder>", "_history_graph")
        insist(sha(original_fragment.encode("utf-8")) == BUILDER_SHA256, "INDEPENDENT_BFC7_BUILDER_PIN")
        builder_node, builder = self.function(MAIN_NAME, "_history_graph")
        expected_builder, _ = selected(OLD_BUILDER.replace(OLD_BUILDER_SEQUENCE, NEW_BUILDER_SEQUENCE),
            "<reviewed-exact-tuple-elision>", "_history_graph")
        insist(ast.dump(builder_node) == ast.dump(expected_builder), "ONLY_APPROVED_BUILDER_AST")
        # Restore only this independently pinned builder. The whole-source pin
        # binds every other byte, including the exact unchanged bfc7 checker.
        lines = self.text[MAIN_NAME].splitlines(keepends=True)
        predecessor = "".join(lines[:builder_node.lineno - 1]) + OLD_BUILDER + "".join(lines[builder_node.end_lineno:])
        insist(sha(predecessor.encode("utf-8")) == BFC7_SHA256, "ALL_OTHER_MAIN_SOURCE_EXACT_BFC7")
        predecessor_node, predecessor_fragment = selected(predecessor, "<exact-bfc7-preimage>", "_check_history")
        insist(predecessor_fragment == fragment, "BFC7_CHECKER_BYTES_UNCHANGED")
        # Preserve the historical6006 admission too; no old result is relabelled
        # as execution of this new builder or as a hosted qualification.
        lines = predecessor.splitlines(keepends=True)
        inverse = "".join(lines[:predecessor_node.lineno - 1]) + OLD_CHECKER + "".join(lines[predecessor_node.end_lineno:])
        insist(sha(inverse.encode("utf-8")) == BASELINE_SHA256, "HISTORICAL_OTHER_SOURCE_EXACT6006")
        self.pins["oldChecker"] = OLD_CHECKER_SHA256
        self.pins["candidateChecker"] = sha(fragment.encode("utf-8"))
        self.pins["builder"] = BUILDER_SHA256
        self.pins["candidateBuilder"] = sha(builder.encode("utf-8"))
        self.baseline_node = self.old_node
        self.baseline_filename = "<independent6006-history>"
        self.original_builder_node = original_builder
        self.original_builder_filename = "<independent-bfc7-builder>"
        self.predecessor_node = predecessor_node
        self.predecessor_filename = "<exact-bfc7-preimage>"
        if baseline is not None:
            original = read_public(baseline)
            insist(sha(original) == BFC7_SHA256, "EXPLICIT_FULL_BASELINE_BFC7_PIN")
            source = original.decode("utf-8")
            node, actual = selected(source, str(baseline), "_check_history")
            insist(actual == predecessor_fragment, "ACTUAL_BFC7_CHECKER_BYTES")
            original_builder, actual_builder = selected(source, str(baseline), "_history_graph")
            insist(actual_builder == OLD_BUILDER, "ACTUAL_BFC7_BUILDER_EQUALS_INDEPENDENT_PREIMAGE")
            self.predecessor_node, self.predecessor_filename = node, str(baseline)
            self.original_builder_node, self.original_builder_filename = original_builder, str(baseline)

    def function(self, source, name):
        key = source, name
        if key not in self.cache:
            self.cache[key] = selected(self.text[source], str(self.paths[source]), name)
        return self.cache[key]

    def bind(self, source, name, environment):
        return compile_function(self.function(source, name)[0], str(self.paths[source]), environment)


RECORD_NAMES = (
    "_ReadmissionReturn", "_ReadmissionBinding", "_ReadmissionClaim", "_PreparationBinding",
    "_OriginalPreparation", "_OriginalServiceJobAdmission", "_EntryWindowBinding", "_ReadmissionWindow",
    "SourceReturn", "Owner", "OriginalPhase", "Fence", "Reading", "ClockIdentity",
    "InitialBootstrapIdentity", "BootstrapMatch", "_AuthorityReturn", "_AuthorityState", "_RecipientRoster",
    "_RecipientNativeReturn", "_RecipientValidationReturn", "_RecipientState", "_RecipientCryptoOriginals")


class Runtime:
    def __init__(self, sources, root=None, *, original_builder=False):
        self.records = {name: type(name, (), {}) for name in RECORD_NAMES}
        identity_require = sources.bind("hosted_test_identity.py", "require", {"AdmissionError": AdmissionError})
        identity = SimpleNamespace(require=identity_require)
        self.require = sources.bind(MAIN_NAME, "require", {"I": identity})
        query = {"QueryError": QueryError, "re": re}
        sources.bind("hosted_test_query.py", "require", query)
        component = sources.bind("hosted_test_query.py", "_component", query)
        wire = {"BudgetError": BudgetError, "json": json, "RECORD_LIMIT": 2 * 1024 * 1024}
        sources.bind("hosted_full_job_budget.py", "require", wire)
        self.encoded = sources.bind("hosted_full_job_budget.py", "encoded", wire)
        self.environment = dict(self.records, require=self.require, ROOT=Path("MODEL_ROOT") if root is None else root,
            native=SimpleNamespace(Owner=self.records["Owner"], OriginalPhase=self.records["OriginalPhase"]),
            O=SimpleNamespace(Fence=self.records["Fence"], clocks=SimpleNamespace(
                Reading=self.records["Reading"], ClockIdentity=self.records["ClockIdentity"])),
            initial_identity=SimpleNamespace(InitialBootstrapIdentity=self.records["InitialBootstrapIdentity"]),
            acquisition=SimpleNamespace(stages=SimpleNamespace(BootstrapMatch=self.records["BootstrapMatch"])))
        self.original_graph = compile_function(sources.original_builder_node,
            sources.original_builder_filename, dict(self.environment))
        self.current_graph = sources.bind(MAIN_NAME, "_history_graph", dict(self.environment))
        self.graph = self.original_graph if original_builder else self.current_graph
        self.candidate = sources.bind(MAIN_NAME, "_check_history", dict(self.environment))
        self.baseline = compile_function(sources.baseline_node, sources.baseline_filename, dict(self.environment))
        self.predecessor = compile_function(sources.predecessor_node, sources.predecessor_filename, dict(self.environment))
        custody = {"I": identity, "MAX_MEMBERS": 10000, "Q": SimpleNamespace(_component=component),
            "O": SimpleNamespace(encoded=self.encoded), "stat": stat}
        sources.bind(CUSTODY_NAME, "require", custody)
        # Only the POSIX gate's supplied eight-integer stamps are modeled.
        # Selecting Windows metadata without its genuine class must fail.
        custody["native"] = SimpleNamespace(windows=SimpleNamespace(FileInfo=type("UnusedWindowsFileInfo", (), {})))
        self.metadata = sources.bind(CUSTODY_NAME, "_snapshot_metadata", custody)

    def record(self, name, **fields):
        record = self.records[name]()
        record.__dict__.update(fields)
        return record


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class ModelPath:
    def __init__(self, name, events=None):
        self.name, self.events, self.hook = name, events, None
        self.values = {"str": name, "parts": (name,), "drive": "", "root": ""}

    def take(self, field):
        if self.events is not None:
            self.events.append(("path", self.name, field))
        if self.hook is not None:
            self.hook(field)
        return self.values[field]

    def __str__(self):
        return self.take("str")

    parts = property(lambda self: self.take("parts"))
    drive = property(lambda self: self.take("drive"))
    root = property(lambda self: self.take("root"))


def path_node(path):
    return path, type(path), "path", (path.name, (path.name,), "", "")


def observed(checker, nodes, events):
    original = checker.__globals__["require"]

    def require(value, code):
        events.append(("require", bool(value), code))
        return original(value, code)

    def visits():
        for ordinal, node in enumerate(nodes):
            events.append(("node", ordinal))
            yield node

    checker.__globals__["require"] = require
    try:
        result = checker(visits())
        return ("return", result), None
    except BaseException as error:
        return ("raise", type(error).__name__, error.args), error
    finally:
        checker.__globals__["require"] = original


def stamp(ordinal, directory=False, size=3, device=700):
    return (device, ordinal, (stat.S_IFDIR | 0o700) if directory else (stat.S_IFREG | 0o600),
        1, 1000, 0 if directory else size, 1700000000000000000 + ordinal, 1700000000000000000 + ordinal)


def gate_entries():
    """281/58 names from the maintained gate grammar, without original bytes."""
    directories = {"", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"}
    files = {"prelude.json", "context.json", "initial-result.json", "service/child-result.json"}
    phase = ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log")
    files.update("service/" + name for name in phase)
    source_keys = ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")
    original_keys = ("event", *source_keys, "attempt", "jobs", "approvals", "comment", "environment", "branches",
        "main", "reviewed_ref", "observation", "match")
    for group, count in (("source-before", 12), ("acquisition-queries", 24), ("source-after", 12)):
        directories.add(group + "/query-home")
        files.update((group + "/owner.json", group + "/session-result.json"))
        if group != "acquisition-queries":
            files.add(group + "/source-return.json")
        for key in original_keys if group == "acquisition-queries" else source_keys:
            files.add(group + "/" + key + ".bin")
        for number in range(count):
            query = group + "/query-" + format(number + 1, "032x")
            directories.add(query)
            files.update(query + "/" + name for name in ("start.json", "baseline.json", "result.json", "stdout.log", "stderr.log"))
    insist(len(files) == 281 and len(directories) == 58 and not files.intersection(directories), "FIXED_GATE281_58")
    entries = {name: stamp(number + 1, name in directories, 0 if name.endswith(".log") else 3)
        for number, name in enumerate(sorted(files | directories))}
    return entries, tuple(sorted(files)), tuple(sorted(directories))


def model_bank(runtime):
    """Actual snapshot/graph compositions; no uniform all-tuples microbenchmark.

    Primary gate:281 files/58 directories, separate handoff, then282 copied
    members. Retain snapshot.__dict__ graphs exactly as retain_snapshot does,
    including the original graph-of-graph. A second independent282-member
    destination snapshot models the existing PRIMARY reread boundary. Mutable
    decoded copy-map rows and a closed Owner-shaped graph remain in the bank.
    Each graph is visited once per fixed modeled guard pass; this is NOT an
    inferred count/weight of actual hosted callbacks or resources.
    """
    entries, files, directories = gate_entries()
    snapshots, graphs = [], []

    def snapshot(name, values):
        path = Path("MODEL_CUSTODY") / name
        data = {"group": name, "path": path, "directory": object(), "pin": values[""][:2], "native": None,
            "original": values, "metadata": runtime.metadata(values, False),
            "graph": runtime.graph(values, path), "windows": False}
        snapshots.append(data)
        graphs.append((name, runtime.graph(data)))
        return data

    primary = snapshot("primary-source", entries)
    handoff = snapshot("primary-handoff", {"": stamp(1, True, device=701),
        "gate-originals.json": stamp(2, device=701)})
    copied_names = tuple("member-" + str(number).zfill(5) + ".bin" for number in range(282))
    copied = snapshot("copied-primary-original", {name: stamp(number + 1, not name, device=702)
        for number, name in enumerate(("", *copied_names))})
    snapshot("copied-primary-reread", {name: stamp(number + 1, not name, device=702)
        for number, name in enumerate(("", *copied_names))})
    file_rows = tuple(("P/" + name, 4096, entries[name][5], "0" * 64, "ORIGINAL_PRIMARY_DECLARATION") for name in files)
    directory_rows = tuple(("P" + ("/" + name if name else ""), entries[name][:2], "ORIGINAL_DECLARED_DIRECTORY")
        for name in directories)
    primary_fields = {"kind": "gate", "role": "linux-x64", "handoff_raw": b"SUPPLIED_HANDOFF_NOT_A_STEP",
        "inventory_raw": b"SUPPLIED_INDEX", "roots": (("P", primary["path"]),), "directories": directory_rows,
        "files": file_rows, "embedded": (), "result_sha256": "0" * 64}
    copy_map = {"members": [{"member": name, "bytes": 3, "sha256": "0" * 64, "origin": "PRIMARY",
        "destinationWriteMetadata": {"device": 702, "inode": number + 2, "size": 3,
            "mtime_ns": 1700000000000000000 + number + 2, "ctime_ns": 1700000000000000000 + number + 2}}
        for number, name in enumerate(copied_names)],
        "sourceMetadata": [[name, directory, list(identity), count, json.loads(raw)]
            for name, directory, identity, count, raw in primary["metadata"]],
        "handoffMetadata": [[name, directory, list(identity), count, json.loads(raw)]
            for name, directory, identity, count, raw in handoff["metadata"]],
        "destinationMetadata": [[name, directory, list(identity), count, json.loads(raw)]
            for name, directory, identity, count, raw in copied["metadata"]],
        "memberCount": 282, "exportSaveAuthority": False}
    graphs.append(("primary-record-and-decoded-copy-metadata", runtime.graph(primary_fields, copy_map)))
    clock = runtime.record("ClockIdentity", role="linux-x64", domain="MODEL_RAW", ticks_per_second=1000000000)
    first = runtime.record("Reading", clock=clock, nanoseconds=1000000000)
    cancelled = lambda: (_ for _ in ()).throw(AssertionError("CLOSED_CALLBACK_MUST_NOT_RUN"))
    fence = runtime.record("Fence", clock=clock, raw=b"SUPPLIED_CLOSED_FENCE", first=1000000000,
        work=2000000000, final=3000000000, last=1500000000, cancelled=cancelled)
    rows = [{"label": "directory", "owner": object(), "attempted": True, "closed": True} for _ in range(7)]
    sources = {group: runtime.record("SourceReturn", records=tuple((key, b"SUPPLIED") for key in
        ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")),
        session=b"SUPPLIED_QUERY_SESSION", raw=b"SUPPLIED_SOURCE_RETURN") for group in ("source-before", "source-after")}
    owner = runtime.record("Owner", local_end=3.0, fence=fence, work_limit=None, final_limit=None,
        first=first, early_last=first.nanoseconds, cancelled=cancelled, resources=rows, errors=[], original=None,
        unknown=False, closed=True, phase_originals=runtime.record("OriginalPhase", context=b"SUPPLIED_CONTEXT",
            records=tuple((name, b"SUPPLIED") for name in ("start.json", "baseline.json", "result.json",
                "native-start.json", "stdout.log", "stderr.log"))), admissions={}, entry_original=None,
        entry_close_attempted=False, entry_close_original=None, entry_close_snapshot=None, initial_sources=sources)
    graphs.append(("closed-owner-records", runtime.graph(owner)))
    return tuple(graphs), {"files": len(files), "directories": len(directories), "copiedPrimaryFiles": 282,
        "closedOwnerRows": 7, "role": "SUPPLIED_POSIX_GATE_MODEL", "snapshots": len(snapshots)}, rows


SOURCES = None


class HistoryIdentityControls(unittest.TestCase):
    def equivalent(self, factory, *, accepts, original_error=None):
        outcomes = []
        for label in ("baseline", "candidate"):
            runtime, events = Runtime(SOURCES), []
            nodes = factory(runtime, events)
            result, error = observed(getattr(runtime, label), nodes, events)
            self.assertEqual(result[0], "return" if accepts else "raise")
            if original_error is not None:
                self.assertIs(error, original_error)
            outcomes.append((result, events))
        self.assertEqual(outcomes[0], outcomes[1])
        return outcomes[0]

    def test_01_builder_tuple_identity_scalars_nan_and_opaque_no_hooks(self):
        def factory(runtime, events):
            class Opaque:
                def __eq__(self, other):
                    raise AssertionError("OPAQUE_EQUALITY_MUST_NOT_RUN")
                def __call__(self):
                    raise AssertionError("OPAQUE_CALLBACK_MUST_NOT_RUN")
            value = ((), None, False, 1, 1.0, "text", b"bytes", float("nan"), Opaque())
            original = runtime.original_graph(value)
            self.assertIs(original[0][0], value)
            for item, kind, mode, saved in original:
                if kind is tuple:
                    self.assertEqual(mode, "sequence")
                    self.assertIs(item, saved)
            nodes = runtime.graph(value)
            self.assertEqual(len(nodes), 1)
            self.assertIs(nodes[0][0], value[-1])
            self.assertEqual(nodes[0][2], "opaque")
            return nodes
        result, events = self.equivalent(factory, accepts=True)
        self.assertEqual(result, ("return", None))
        self.assertEqual(sum(event[0] == "require" for event in events),
            2 * sum(event[0] == "node" for event in events))

    def test_02_nonidentical_manual_tuple_old_fallback_success(self):
        def factory(runtime, events):
            opaque = object()
            value, saved = tuple([1000, "same", opaque]), tuple([int("1000"), "sa" + "me", opaque])
            self.assertIsNot(value, saved)
            return ((value, tuple, "sequence", saved), ((), tuple, "sequence", ()),
                ((1, 2), tuple, "sequence", [1, 2]))
        self.equivalent(factory, accepts=True)

    def test_03_manual_tuple_differences_type_nan_and_reference_refusals(self):
        for actual, saved in (([True], [1]), ([1], [1.0]), ([1], [2]), ([1], []),
                ([float("nan")], [float("nan")]), ([[]], [[]]), ([{}], [{}]), ([object()], [object()])):
            with self.subTest(actual_type=type(actual[0]).__name__, saved_length=len(saved)):
                self.equivalent(lambda runtime, events: ((tuple(actual), tuple, "sequence", tuple(saved)),), accepts=False)

    def test_04_mutable_list_length_order_equal_replacement_and_scalar_aliases(self):
        for change in ("append", "delete", "order", "reference", "bool", "float"):
            def factory(runtime, events):
                value = [1, 2, {"x": 1}]
                nodes = runtime.graph(value)
                if change == "append":
                    value.append(3)
                elif change == "delete":
                    value.pop()
                elif change == "order":
                    value[:2] = [2, 1]
                elif change == "reference":
                    value[2] = {"x": 1}
                else:
                    value[0] = True if change == "bool" else 1.0
                return nodes
            with self.subTest(change=change):
                self.equivalent(factory, accepts=False)

    def test_05_mapping_length_order_references_and_key_type_refusals(self):
        for change in ("append", "delete", "order", "reference", "keytype", "valuetype"):
            def factory(runtime, events):
                value = {1: [], "two": 2}
                nodes = runtime.graph(value)
                if change == "append":
                    value["three"] = 3
                elif change == "delete":
                    del value["two"]
                elif change == "order":
                    value[1] = value.pop(1)
                elif change == "reference":
                    value[1] = []
                elif change == "keytype":
                    first = value.pop(1)
                    value.clear()
                    value.update({True: first, "two": 2})
                else:
                    value["two"] = 2.0
                return nodes
            with self.subTest(change=change):
                self.equivalent(factory, accepts=False)

    def test_06_tuple_mutable_descendants_rechecked_on_every_call(self):
        for mutable in ("dict", "list"):
            def factory(runtime, events):
                descendant = {"value": 1} if mutable == "dict" else [1]
                nodes = runtime.graph(((descendant,),))
                runtime.baseline(nodes)
                runtime.candidate(nodes)
                descendant["value" if mutable == "dict" else 0] = True
                return nodes
            with self.subTest(mutable=mutable):
                self.equivalent(factory, accepts=False)

    def test_07_known_record_dictionary_identity_and_field_descendants(self):
        for change in ("dictionary", "scalar", "reference", "nested"):
            def factory(runtime, events):
                record = runtime.record("SourceReturn", records=[1], session=b"session", raw=b"raw")
                nodes = runtime.graph((record,))
                self.assertTrue(any(node[2] == "record" for node in nodes))
                if change == "dictionary":
                    record.__dict__ = dict(record.__dict__)
                elif change == "scalar":
                    record.raw = "raw"
                elif change == "reference":
                    record.records = [1]
                else:
                    record.records[0] = True
                return nodes
            with self.subTest(change=change):
                self.equivalent(factory, accepts=False)

    def test_08_path_descendants_all_fields_and_type_before_accessors(self):
        for field in (None, "str", "parts", "drive", "root", "type"):
            def factory(runtime, events):
                path = ModelPath("model", events)
                runtime.graph.__globals__["ROOT"] = ModelPath("root")
                nodes = runtime.graph((path,))
                events.clear()
                if field == "type":
                    nodes = ((path, str, "path", nodes[0][3]),)
                elif field is not None:
                    path.values[field] = ("changed",) if field == "parts" else "changed"
                return nodes
            with self.subTest(field=field):
                _, events = self.equivalent(factory, accepts=field is None)
                self.assertEqual([event[-1] for event in events if event[0] == "path"],
                    [] if field == "type" else ["str", "parts", "drive", "root"])

    def test_09_tuple_subclass_opaque_and_manual_custom_fallback_hooks(self):
        for manual in (False, True):
            def factory(runtime, events):
                class TupleSubclass(tuple):
                    def __len__(self):
                        events.append(("custom", "len"))
                        return super().__len__()
                    def __iter__(self):
                        events.append(("custom", "iter"))
                        return super().__iter__()
                value = TupleSubclass((1, 2))
                nodes = ((value, type(value), "sequence", value),) if manual else runtime.graph(value)
                self.assertEqual(events, [])
                return nodes
            with self.subTest(manual=manual):
                _, events = self.equivalent(factory, accepts=True)
                self.assertEqual([event[-1] for event in events if event[0] == "custom"],
                    ["len", "len", "iter", "iter"] if manual else [])

    def test_10_cycles_shared_references_node_order_and_manual_duplicates(self):
        def factory(runtime, events):
            shared = []
            root = (shared, shared)
            shared.append(root)
            nodes = runtime.graph(root)
            self.assertEqual(len(nodes), 1)
            self.assertIs(nodes[0][0], shared)
            left, right = ModelPath("left", events), ModelPath("right", events)
            return (*nodes, path_node(left), path_node(right), path_node(left))
        _, events = self.equivalent(factory, accepts=True)
        self.assertEqual([event[1] for event in events if event[0] == "node"], list(range(4)))
        self.assertEqual([event[1] for event in events if event[0] == "path"], ["left"] * 4 + ["right"] * 4 + ["left"] * 4)

    def test_11_earlier_boundary_mutation_of_later_tuple_descendant_not_skipped(self):
        def factory(runtime, events):
            descendant, path = [1], ModelPath("earlier", events)
            runtime.graph.__globals__["ROOT"] = ModelPath("root")
            nodes = runtime.graph((descendant, path))
            events.clear()
            path.hook = lambda field: descendant.__setitem__(0, True) if field == "str" else None
            return nodes
        _, events = self.equivalent(factory, accepts=False)
        self.assertEqual([event[1] for event in events if event[0] == "node"], [0, 1])
        self.assertEqual(events[-1], ("require", False, "RECIPIENT_HISTORY_CHANGED"))

    def test_12_invalid_modes_types_and_malformed_manual_nodes(self):
        cases = (
            ((object(), object, "INVALID", None),),
            (([], tuple, "sequence", ()),),
            (((), tuple, "sequence", None),),
            ((),),
            ((object(), object, "opaque", None, None),),
        )
        for nodes in cases:
            with self.subTest(shape=tuple(len(node) for node in nodes)):
                self.equivalent(lambda runtime, events: nodes, accepts=False)

    def test_13_falsey_original_accessor_and_sequence_exceptions_preserved(self):
        failure = FalseyFailure("SUPPLIED_FALSEY_ORIGINAL")
        for site in ("path", "length", "iteration"):
            def factory(runtime, events):
                def fail():
                    events.append(("original-failure", site))
                    raise failure
                if site == "path":
                    path = ModelPath("falsey", events)
                    path.hook = lambda field: fail()
                    return (path_node(path),)
                class Sequence:
                    def __len__(self):
                        return fail() if site == "length" else 1
                    def __iter__(self):
                        return fail()
                value = Sequence()
                return ((value, Sequence, "sequence", (1,)),)
            with self.subTest(site=site):
                self.equivalent(factory, accepts=False, original_error=failure)

    def test_14_builder_keys_exact_node_limit_and_node_schema(self):
        runtime = Runtime(SOURCES)
        with self.assertRaisesRegex(AdmissionError, "RECIPIENT_HISTORY_KEY"):
            runtime.graph({object(): 1})
        values = [[] for _ in range(9999)]
        nodes = runtime.graph(values)
        self.assertEqual(len(nodes), 10000)
        self.assertTrue(all(type(node) is tuple and len(node) == 4 and node[1] is list and
            node[2] == "sequence" and type(node[3]) is tuple for node in nodes))
        values.append([])
        with self.assertRaisesRegex(AdmissionError, "RECIPIENT_HISTORY_LIMIT"):
            runtime.graph(values)

    def test_15_maintained_metadata_model_shape_and_closed_mutable_negative(self):
        runtime = Runtime(SOURCES)
        bank, shape, rows = model_bank(runtime)
        self.assertEqual((shape["files"], shape["directories"], shape["copiedPrimaryFiles"]), (281, 58, 282))
        self.assertEqual(len(bank), 6)
        modes = {node[2] for _, nodes in bank for node in nodes}
        self.assertEqual(modes, {"mapping", "sequence", "record", "path", "opaque"})
        for _, nodes in bank:
            runtime.baseline(nodes)
            runtime.candidate(nodes)
        rows[-1]["closed"] = False
        for checker in (runtime.baseline, runtime.candidate):
            with self.assertRaisesRegex(AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                checker(bank[-1][1])
        good = {"": stamp(1, True), "file": stamp(2)}
        self.assertEqual(len(runtime.metadata(good, False)), 2)
        for entries, windows in ((good, 0), ({"": stamp(1, True), "file": stamp(1)}, False),
                ({"": stamp(1, True), "file": (700, 2, stat.S_IFREG, 1, 1000, True, 1, 1)}, False)):
            with self.assertRaises(AdmissionError):
                runtime.metadata(entries, windows)


class CurrentBuilderControls(unittest.TestCase):
    """Compare actual candidate graphs with the independently pinned bfc7 builder."""

    def pair(self, runtime, *roots):
        original = runtime.original_graph(*roots)
        current = runtime.current_graph(*roots)
        retained = tuple(node for node in original if node[1] is not tuple)
        self.assertEqual(len(current), len(retained))
        for actual, old in zip(current, retained):
            self.assertIs(actual[0], old[0])
            self.assertIs(actual[1], old[1])
            self.assertEqual(actual[2], old[2])
            mode, saved, previous = actual[2], actual[3], old[3]
            if mode == "mapping":
                self.assertEqual(len(saved), len(previous))
                for (key, value), (old_key, old_value) in zip(saved, previous):
                    self.assertIs(key, old_key)
                    self.assertIs(value, old_value)
            elif mode == "sequence":
                self.assertIs(actual[1], list)
                self.assertEqual(len(saved), len(previous))
                for value, old_value in zip(saved, previous):
                    self.assertIs(value, old_value)
            elif mode == "path":
                self.assertEqual(saved, previous)
            else:
                self.assertIs(saved, previous)
        self.assertTrue(all(node[1] is not tuple for node in current))
        return original, current

    def same_outcome(self, runtime, pair, *, accepts, events=None, original_error=None):
        events = [] if events is None else events
        outcomes, traces = [], []
        for checker, nodes in zip((runtime.predecessor, runtime.candidate), pair):
            events.clear()
            result, error = observed(checker, nodes, events)
            self.assertEqual(result[0], "return" if accepts else "raise")
            if original_error is not None:
                self.assertIs(error, original_error)
            outcomes.append(result)
            # Only the removed exact-tuple node's two tautological requires
            # disappear. Every other node/hook/require stays in the same order.
            normalized, omitted = [], False
            for event in events:
                if event[0] == "node":
                    node = nodes[event[1]]
                    omitted = node[1] is tuple
                    if not omitted:
                        normalized.append(("node", id(node[0]), node[1], node[2]))
                elif not omitted:
                    normalized.append(event)
                else:
                    self.assertEqual(event, ("require", True, "RECIPIENT_HISTORY_CHANGED"))
            traces.append(normalized)
        self.assertEqual(outcomes[0], outcomes[1])
        self.assertEqual(traces[0], traces[1])
        return traces[0]

    def test_16_scalar_only_tuple_elision_has_no_remaining_check_nodes(self):
        runtime = Runtime(SOURCES)
        values = (((), None, False, 1, 1.0, float("nan")), ("text", b"bytes"))
        original, current = self.pair(runtime, values)
        self.assertGreater(len(original), 0)
        self.assertEqual(current, ())
        self.same_outcome(runtime, (original, current), accepts=True)

    def test_17_nested_mutable_descendants_remain_live_on_every_check(self):
        for change in ("list", "mapping", "reference", "append"):
            with self.subTest(change=change):
                runtime = Runtime(SOURCES)
                values = {"row": [1]}
                pair = self.pair(runtime, (((values,),),))
                self.same_outcome(runtime, pair, accepts=True)
                if change == "list":
                    values["row"][0] = True
                elif change == "mapping":
                    values["new"] = None
                elif change == "reference":
                    values["row"] = [1]
                else:
                    values["row"].append(2)
                self.same_outcome(runtime, pair, accepts=False)

    def test_18_equal_distinct_tuple_replacement_in_every_mutable_parent_refuses(self):
        for kind in ("mapping", "list", "record"):
            with self.subTest(kind=kind):
                runtime = Runtime(SOURCES)
                saved = (1, {"nested": []})
                replacement = tuple(list(saved))
                self.assertIsNot(saved, replacement)
                self.assertEqual(saved, replacement)
                parent = ({"slot": saved} if kind == "mapping" else [saved] if kind == "list" else
                    runtime.record("SourceReturn", slot=saved))
                pair = self.pair(runtime, (parent,))
                self.same_outcome(runtime, pair, accepts=True)
                if kind == "record":
                    parent.slot = replacement
                else:
                    parent["slot" if kind == "mapping" else 0] = replacement
                self.same_outcome(runtime, pair, accepts=False)

    def test_19_record_dictionary_identity_and_nested_path_fields_remain_pinned(self):
        for change in ("dictionary", "field", "path-str", "path-parts", "path-drive", "path-root"):
            with self.subTest(change=change):
                runtime, events = Runtime(SOURCES), []
                path = ModelPath("nested", events)
                for builder in (runtime.original_graph, runtime.current_graph):
                    builder.__globals__["ROOT"] = ModelPath("root")
                record = runtime.record("SourceReturn", data=((path,),), value=1)
                pair = self.pair(runtime, (record,))
                self.same_outcome(runtime, pair, accepts=True, events=events)
                if change == "dictionary":
                    record.__dict__ = dict(record.__dict__)
                elif change == "field":
                    record.value = True
                else:
                    field = change.removeprefix("path-")
                    path.values[field] = ("changed",) if field == "parts" else "changed"
                self.same_outcome(runtime, pair, accepts=False, events=events)

    def test_20_non_tuple_hook_order_and_original_falsey_exception_are_unchanged(self):
        for mode in ("late-mutation", "original-error"):
            with self.subTest(mode=mode):
                runtime, events = Runtime(SOURCES), []
                for builder in (runtime.original_graph, runtime.current_graph):
                    builder.__globals__["ROOT"] = ModelPath("root")
                descendant, path = [1], ModelPath("earlier", events)
                pair = self.pair(runtime, ((descendant,), path))
                failure = FalseyFailure("SUPPLIED_ORIGINAL_PATH_FAILURE")
                def hook(field):
                    if field == "str":
                        if mode == "original-error":
                            raise failure
                        descendant[0] = True
                path.hook = hook
                trace = self.same_outcome(runtime, pair, accepts=False, events=events,
                    original_error=failure if mode == "original-error" else None)
                self.assertEqual([event[-1] for event in trace if event[0] == "path"],
                    ["str"] if mode == "original-error" else ["str", "parts", "drive", "root"])

    def test_21_cycles_shared_aliases_and_tuple_subclasses_preserve_original_behavior(self):
        runtime = Runtime(SOURCES)
        class TupleSubclass(tuple):
            def __len__(self):
                raise AssertionError("OPAQUE_TUPLE_SUBCLASS_LENGTH_MUST_NOT_RUN")
            def __iter__(self):
                raise AssertionError("OPAQUE_TUPLE_SUBCLASS_ITERATION_MUST_NOT_RUN")
        opaque = TupleSubclass((1, 2))
        shared = []
        root = (shared, shared, opaque)
        shared.append(root)
        pair = self.pair(runtime, root)
        self.assertEqual(len(pair[1]), 2)
        self.assertEqual([node[2] for node in pair[1]], ["opaque", "sequence"])
        self.same_outcome(runtime, pair, accepts=True)
        shared.append(None)
        self.same_outcome(runtime, pair, accepts=False)

    def test_22_visited10000_cap_includes_elided_tuples_cycles_and_invalid_keys(self):
        runtime = Runtime(SOURCES)
        values = [(number,) for number in range(9999)]
        original, current = self.pair(runtime, values)
        self.assertEqual((len(original), len(current)), (10000, 1))
        self.same_outcome(runtime, (original, current), accepts=True)
        values.append((9999,))
        for builder in (runtime.original_graph, runtime.current_graph):
            with self.assertRaisesRegex(AdmissionError, "RECIPIENT_HISTORY_LIMIT"):
                builder(values)
            with self.assertRaisesRegex(AdmissionError, "RECIPIENT_HISTORY_KEY"):
                builder({(1,): None})
        shared = (1,)
        original, current = self.pair(runtime, [shared] * 10001)
        self.assertEqual((len(original), len(current)), (2, 1))
        self.same_outcome(runtime, (original, current), accepts=True)
        nested = ()
        for _ in range(9999):
            nested = (nested,)
        original, current = self.pair(runtime, nested)
        self.assertEqual((len(original), len(current)), (10000, 0))
        for builder in (runtime.original_graph, runtime.current_graph):
            with self.assertRaisesRegex(AdmissionError, "RECIPIENT_HISTORY_LIMIT"):
                builder((nested,))

    def test_23_original_and_current_snapshot_banks_keep_rosters_and_closed_mutable_checks(self):
        descriptions = []
        for original_builder in (True, False):
            runtime = Runtime(SOURCES, original_builder=original_builder)
            bank, shape, rows = model_bank(runtime)
            self.assertEqual((shape["files"], shape["directories"], shape["copiedPrimaryFiles"]), (281, 58, 282))
            self.assertEqual(len(bank), 6)
            for _, graph in bank:
                self.assertIsNone(runtime.predecessor(graph))
                self.assertIsNone(runtime.candidate(graph))
            descriptions.append((shape, tuple(name for name, _graph in bank)))
            if not original_builder:
                self.assertTrue(all(node[1] is not tuple for _, graph in bank for node in graph))
            rows[-1]["closed"] = False
            for checker in (runtime.predecessor, runtime.candidate):
                with self.assertRaisesRegex(AdmissionError, "RECIPIENT_HISTORY_CHANGED"):
                    checker(bank[-1][1])
        self.assertEqual(descriptions[0], descriptions[1])


def bank_shape(bank, shape):
    descriptions = []
    for name, nodes in bank:
        descriptions.append({"name": name, "nodes": len(nodes), "modes": dict(sorted(Counter(node[2] for node in nodes).items())),
            "types": dict(sorted(Counter(node[1].__name__ for node in nodes).items())), "requiresPerPass": 2 * len(nodes)})
    return dict(shape, graphs=descriptions, nodesPerPass=sum(row["nodes"] for row in descriptions),
        requiresPerPass=sum(row["requiresPerPass"] for row in descriptions))


def validate_bank(checker, bank):
    for _, nodes in bank:
        events = []
        outcome, error = observed(checker, nodes, events)
        insist(outcome == ("return", None) and error is None, "MODEL_RESULT_AGREEMENT")
        insist(sum(event[0] == "node" for event in events) == len(nodes) and
            sum(event[0] == "require" for event in events) == 2 * len(nodes), "MODEL_ALL_NODES_TWO_REQUIRES")


def measure(sources):
    runtimes = {"baseline": Runtime(sources, original_builder=True), "candidate": Runtime(sources)}
    models = {name: model_bank(runtime) for name, runtime in runtimes.items()}
    banks = {name: model[0] for name, model in models.items()}
    descriptions = {name: bank_shape(model[0], model[1]) for name, model in models.items()}
    insist(models["baseline"][1] == models["candidate"][1] and
        tuple(name for name, _ in banks["baseline"]) == tuple(name for name, _ in banks["candidate"]),
        "MODEL_ORIGINAL_AND_CURRENT_ROSTERS_IDENTICAL")
    checkers = {"baseline": runtimes["baseline"].predecessor, "candidate": runtimes["candidate"].candidate}
    # Two disclosed untimed correctness/count passes per implementation (one
    # before, one after). No calibration, warmup loop, adaptive iteration count
    # or retry. Timed require is the actual unchanged N.require -> I.require;
    # old6006 checker is not called. Graph construction itself is not timed.
    for name in ("baseline", "candidate"):
        validate_bank(checkers[name], banks[name])
    blocks = []
    for ordinal, order in enumerate(ORDERS, 1):
        block = {"ordinal": ordinal, "order": order, "iterationsPerSide": ITERATIONS}
        for label in order:
            name = "baseline" if label == "A" else "candidate"
            checker = checkers[name]
            wall_start, cpu_start = time.monotonic_ns(), time.process_time_ns()
            for _ in range(ITERATIONS):
                for _, nodes in banks[name]:
                    insist(checker(nodes) is None, "MODEL_TIMED_RESULT_AGREEMENT")
            cpu_ns, wall_ns = time.process_time_ns() - cpu_start, time.monotonic_ns() - wall_start
            insist(cpu_ns > 0 and wall_ns > 0, "MODEL_POSITIVE_CLOCK_DIFFERENCES")
            block[name] = {"cpuNs": cpu_ns, "wallNs": wall_ns, "passes": ITERATIONS}
        blocks.append(block)
    for name in ("baseline", "candidate"):
        validate_bank(checkers[name], banks[name])
    totals = {name: {clock: sum(block[name][clock] for block in blocks) for clock in ("cpuNs", "wallNs")}
        for name in ("baseline", "candidate")}
    old_cpu, new_cpu = totals["baseline"]["cpuNs"], totals["candidate"]["cpuNs"]
    passed = 100 * new_cpu <= (100 - MINIMUM_IMPROVEMENT_PERCENT) * old_cpu
    result = {"schema": 2, "scope": "MODEL_HISTORY_GRAPH_COST_ONLY", "passed": passed,
        "decision": "MEANINGFUL_CPU_REDUCTION" if passed else "NO_MEANINGFUL_CPU_REDUCTION", "agreement": True,
        "minimumImprovementPercent": MINIMUM_IMPROVEMENT_PERCENT,
        "baselineCommit": "bfc7b60c0fc8fb894430108425552f8e69061c67", "graphConstruction": "NOT_TIMED",
        "aggregate": dict(totals, cpuRatio=new_cpu / old_cpu, cpuImprovementPercent=100 * (old_cpu - new_cpu) / old_cpu,
            wallRatio=totals["candidate"]["wallNs"] / totals["baseline"]["wallNs"]),
        "blocks": blocks, "shape": descriptions, "iterationsPerImplementation": len(ORDERS) * ITERATIONS,
        "sourcePins": sources.pins, "validation": {"before": True, "after": True, "allRetainedNodesChecked": True,
            "identicalOriginalModelRosters": True, "unchangedBfc7CheckerBothSides": True,
            "untimedPassesPerImplementation": 2, "warmupPasses": 0},
        "timedNodesPerImplementation": {name: description["nodesPerPass"] * len(ORDERS) * ITERATIONS
            for name, description in descriptions.items()},
        "timedRequiresPerImplementation": {name: description["requiresPerPass"] * len(ORDERS) * ITERATIONS
            for name, description in descriptions.items()},
        "acceptance": "MODEL_ONLY_NOT_HOSTED_CUSTODY_NATIVE_PROVIDER_OR_SCHEDULE_FIT"}
    print(json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if passed else 1


def main():
    global SOURCES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure-baseline", type=Path)
    options, remainder = parser.parse_known_args()
    if options.measure_baseline is not None:
        if remainder:
            parser.error("measurement accepts only --measure-baseline ABSOLUTE_PUBLIC_SOURCE")
        if not options.measure_baseline.is_absolute():
            parser.error("--measure-baseline must be an absolute public source path")
    own_path = Path(__file__).absolute()
    root = own_path.parents[2]
    paths = [own_path, *(root / "scripts" / name for name in (MAIN_NAME, *SOURCE_PINS))]
    if options.measure_baseline is not None:
        paths.append(options.measure_baseline)
    sys.dont_write_bytecode = True
    install_audit(paths)
    SOURCES = Sources(root, own_path, options.measure_baseline)
    if options.measure_baseline is not None:
        return measure(SOURCES)
    program = unittest.main(argv=[str(own_path), *remainder], exit=False)
    return 0 if program.result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
