"""Closed Stage1 evidence adapter, not acquisition, a launcher or admission.

The fixed caller owns actual primary Step success, original fresh HTTP/native
returns, the three-origin frozen copy, same-process PUBLIC Recipient provenance,
all original absolute fences and known retirement. Typed records/digests supplied
here do not establish those facts. No ordinary Admission, arbitrary manifest or
JSON-restored live Recipient is accepted. The terminal transport self-tail is
not declared inside the already-frozen evidence packet.

``read_manifest()`` must read only the fixed output/manifest.json through the
caller's bounded native owner and return after known file closure. ``check()``
is that owner's original guard, not a replacement HTTP acquisition. Neither
callback receives a caller-selected command, path, URL or manifest.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PosixPath, WindowsPath
import re
import stat
import sys
import time
from types import MappingProxyType

import hosted_evidence as posix
import hosted_windows_evidence as windows
import hosted_initial_recipient_originals as acquisition


ROOT = Path(__file__).resolve().parents[1]
I, G, S = acquisition.identity, acquisition.gate, acquisition.stages
SCOPE = "ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_EVIDENCE"
ORIGINS = ("PRIMARY", "AUTHORITY_PRE_EXPORT", "RECIPIENT_PRE_EXPORT")
MANIFEST_LIMIT = 64 * 1024
PRIMARY_FIELDS = {"step", "outcome", "resultSha256", "handoffSha256", "inventorySha256"}
COPY_FIELDS = {"mapSha256", "memberCount", "totalBytes", "origins"}
AUTHORITY_FIELDS = {"returnSha256", "matchSha256"}
COMMON_MATCH = {"schema", "scope", "authority", "originalBase", "reviewed", "source", "github", "policy",
                "environment", "firstUseAt", "notBefore", "expiresAt"}


def require(value, code):
    if not value:
        raise posix.EvidenceError("INITIAL_EVIDENCE_" + code)


def _fields(value, names):
    require(type(value) is dict and set(value) == names and all(type(key) is str for key in value), "FIELDS")


def _sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "DIGEST")
    return value


def _graph(value):
    """Finite exact builtin graph; capture before any fallible external supplier.

    References and independent immutable shapes are both retained. In particular,
    replacing a nested dict/list by an equal one cannot detach the saved graph.
    This is a cooperating-call contract, not a sandbox against replaced code.
    """
    rows, seen, count = [], set(), 0

    def visit(current, depth):
        nonlocal count
        count += 1
        require(depth <= 16 and count <= 2048, "GRAPH_LIMIT")
        kind = type(current)
        if kind in (dict, list):
            require(id(current) not in seen and len(current) <= 128, "GRAPH_ALIAS_OR_SIZE")
            seen.add(id(current))
            if kind is dict:
                items = tuple(dict.items(current))
                require(all(type(key) is str and len(key) <= 128 for key, _ in items), "GRAPH_KEY")
                children = tuple((key, visit(child, depth + 1)) for key, child in items)
                shape = (dict, tuple(sorted(children)))
                rows.append((current, dict, items))
            else:
                items = tuple(current)
                shape = (list, tuple(visit(child, depth + 1) for child in items))
                rows.append((current, list, items))
            return shape
        require(kind in (str, int, bool, type(None)), "GRAPH_TYPE")
        require(kind is not str or len(current) <= 4096, "GRAPH_STRING")
        require(kind is not int or 0 <= current < 2 ** 128, "GRAPH_INTEGER")
        return kind, current

    shape = visit(value, 0)
    return value, shape, tuple(rows)


def _graph_current(pin):
    for original, kind, items in pin[2]:
        require(type(original) is kind, "GRAPH_CHANGED")
        current = tuple(dict.items(original)) if kind is dict else tuple(original)
        require(len(current) == len(items), "GRAPH_CHANGED")
        for actual, saved in zip(current, items):
            if kind is dict:
                require(type(actual[0]) is str and actual[0] == saved[0], "GRAPH_CHANGED")
                actual, saved = actual[1], saved[1]
            require(type(actual) is type(saved) and
                    (actual is saved if type(saved) in (dict, list) else actual == saved), "GRAPH_CHANGED")


def _copy(value):
    # Only already-checked JSON builtins; never deepcopy a live object/owner.
    if type(value) is dict:
        return {key: _copy(child) for key, child in value.items()}
    if type(value) is list:
        return [_copy(child) for child in value]
    return value


def _canonical(value):
    # EXACT maintained POSIX export / Windows _manifest_bytes spelling.
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False) + "\n").encode("ascii")
    require(0 < len(raw) <= MANIFEST_LIMIT, "MANIFEST_LIMIT")
    return raw


# Productive final custody is separate from the legacy three-origin/schema4
# adapter above. Only the genuine, child-local PC graph can enter these APIs.
_PRODUCTIVE_ATTEMPTS, _PRODUCTIVE_BINDINGS, _PRODUCTIVE_RETURNS = {}, {}, {}
_VALIDATION_VIEW_FIELDS = tuple("child role work public_key_raw policy_raw original_match_raw source caps".split())
_ARCHIVE_VIEW_FIELDS = tuple("child archive recipient role payload output payload_root partitions index lineage caps public_inputs".split())
_CAP_FIELDS = tuple("clock first firstLocal workEndNs workEndLocal operationFinishEndNs operationFinishEndLocal finishReserveNs operationLimitNs".split())
_NODE_FIELDS = ("relative", "kind", "bytes", "sha256", "native", "provenance")
_SOURCE_FIELDS = ("job_id", "observed_raw", "event_sha256", "context_sha256", "start_sha256")
_PARTITION_FIELDS = ("ordinal", "group", "root", "members", "map")


@dataclass(frozen=True, repr=False)
class _ProductiveValidationBinding:
    view: object


@dataclass(frozen=True, repr=False)
class _ProductiveExportBinding:
    view: object


@dataclass(frozen=True, repr=False)
class _ProductiveKeyringCap:
    first: object
    firstLocal: float
    workEndNs: int
    workEndLocal: float
    limitNs: int


@dataclass(frozen=True, repr=False)
class ProductiveValidationReturn:
    view: object
    recipient: object
    backend: object
    observations: object
    known_close: object


@dataclass(frozen=True, repr=False)
class ProductiveBackendReturn:
    view: object
    backend: object
    manifest_raw: bytes
    artifact: object
    observations: object
    known_close: object


def _productive_modules():
    import hosted_initial_recipient_productive as P
    import hosted_initial_recipient_productive_custody as PC
    import hosted_initial_recipient_productive_custody_data as CD
    require(PC.P is P and PC.C is P.C and PC.N is P.N and PC.B is P.B and PC.O is P.O, "PRODUCTIVE_MODULE_GRAPH")
    return P, PC, CD


def _productive_pin(value, kind, names):
    require(type(value) is kind and type(value.__dict__) is dict and set(value.__dict__) == set(names),
        "PRODUCTIVE_OBJECT_FIELDS")
    return value, kind, value.__dict__, names, tuple(value.__dict__[name] for name in names)


def _productive_pin_current(pin):
    value, kind, dictionary, names, values = pin
    require(type(value) is kind and value.__dict__ is dictionary and set(dictionary) == set(names),
        "PRODUCTIVE_OBJECT_CHANGED")
    # ALL original field objects stay pinned, including immutable tuple slots.
    # No equality callback can stand in for original object/reference currency.
    require(all(dictionary[name] is original for name, original in zip(names, values)), "PRODUCTIVE_FIELD_CHANGED")


def _productive_fail(state, error):
    if state["failure"] is None:
        state["failure"] = error
    return state["failure"]


def _productive_start(child, mode):
    key = (mode, id(child))
    previous = _PRODUCTIVE_ATTEMPTS.get(key)
    if previous is not None:
        raise _productive_fail(previous, posix.EvidenceError("INITIAL_EVIDENCE_PRODUCTIVE_REENTRY"))
    state = {"child": child, "mode": mode, "key": key, "pid": os.getpid(), "busy": True,
        "failure": None, "status": "STARTED", "binding": None, "backend_result": None,
        "result": None, "keyring": None, "keyring_complete": None, "completion": None}
    _PRODUCTIVE_ATTEMPTS[key] = state
    return state


def _productive_original(binding):
    state = _PRODUCTIVE_BINDINGS.get(id(binding))
    require(type(state) is dict and state["binding"] is binding and
        _PRODUCTIVE_ATTEMPTS.get(state["key"]) is state and state["child"] is binding.view.child,
        "PRODUCTIVE_BINDING_NOT_ORIGINAL")
    if state["failure"] is not None:
        raise state["failure"]
    return state


def _productive_enter(binding):
    state = _productive_original(binding)
    try:
        require(not state["busy"], "PRODUCTIVE_GUARD_REENTRY")
        state["busy"] = True
        _productive_passive(state)
        return state
    except BaseException as error:
        raise _productive_fail(state, error)


def _productive_refs(state, *, whole=False):
    binding, P, PC, CD = state["binding"], state["P"], state["PC"], state["CD"]
    require(state["pid"] == os.getpid() and state["failure"] is None and state["busy"] and
        _PRODUCTIVE_ATTEMPTS.get(state["key"]) is state and _PRODUCTIVE_BINDINGS.get(id(binding)) is state,
        "PRODUCTIVE_REGISTRY_CHANGED")
    require(sys.modules.get(P.__name__) is P and sys.modules.get(PC.__name__) is PC and
        sys.modules.get(CD.__name__) is CD and PC.P is P and PC.C is P.C and PC.N is P.N and
        PC.B is P.B and PC.O is P.O and all(getattr(owner, name, None) is original
            for owner, name, original in state["methods"]), "PRODUCTIVE_SUPPLIER_CHANGED")
    for pin in state["pins"]:
        _productive_pin_current(pin)
    require(all(os.environ.get(name) == original for name, original in state["environment"]),
        "PRODUCTIVE_CONTEXT_CHANGED")
    _graph_current(state["policy_pin"])
    _graph_current(state["match_pin"])
    if state.get("recipient_pin") is not None:
        _productive_pin_current(state["recipient_pin"])
        _paths_current(state["recipient_paths"])
    if state["mode"] == "export":
        _graph_current(state["public_pin"])
        view, partitions = binding.view, state["partitions"]
        require(view.partitions is partitions and type(partitions) is tuple and len(partitions) == 30 and
            all(partitions[index] is row[0] for index, row in enumerate(state["partition_pins"])),
            "PRODUCTIVE_PARTITIONS_CHANGED")
        if whole:
            for pin in state["partition_pins"]:
                _productive_pin_current(pin)
            require(len(state["nodes"]) == len(state["node_rows"]), "PRODUCTIVE_NODE_ROSTER_CHANGED")
            for node, pin, _partition in state["node_rows"]:
                require(state["nodes"].get(node.relative) is node, "PRODUCTIVE_NODE_REFERENCE_CHANGED")
                _productive_pin_current(pin)
    if state["keyring"] is not None:
        _productive_pin_current(state["keyring_pin"])
    for name in ("keyring_complete", "completion"):
        if state[name] is not None:
            observation, first_pin, clock_pin = state[name + "_pin"]
            require(state[name] is observation, "PRODUCTIVE_COMPLETION_CHANGED")
            _productive_pin_current(first_pin)
            _productive_pin_current(clock_pin)


def _productive_passive(state, *, whole=False):
    _productive_refs(state, whole=whole)
    state["P"]._credential_free()
    _productive_refs(state, whole=whole)


def _productive_observation_pin(state, observation):
    first, local = observation
    require(type(observation) is tuple and len(observation) == 2 and type(local) is float and
        math.isfinite(local), "PRODUCTIVE_COMPLETION_TYPE")
    clocks = state["P"].O.clocks
    return (observation, _productive_pin(first, clocks.Reading, ("clock", "nanoseconds")),
        _productive_pin(first.clock, clocks.ClockIdentity, ("role", "domain", "ticks_per_second")))


def _productive_current(state, *, whole=False, retired=False):
    _productive_passive(state, whole=whole)
    PC, view = state["PC"], state["binding"].view
    if retired:
        returned = (PC.checked_retired_child_validation(view.child) if state["mode"] == "validation" else
            PC.check_retired_child_archive(view))
        require(returned is view, "PRODUCTIVE_OUTER_NOT_RETIRED")
    else:
        if state["mode"] == "validation":
            require(PC.check_child_validation(view) is view, "PRODUCTIVE_ACTIVE_VALIDATION")
        elif whole:
            require(PC.check_child_archive(view) is view, "PRODUCTIVE_ACTIVE_ARCHIVE")
        else:
            require(PC.archive_liveness(view) is view.caps, "PRODUCTIVE_ACTIVE_ARCHIVE_CAPS")
        now = int(time.time())
        policy, match = state["policy"], state["match"]
        require(policy["notBefore"] <= match["notBefore"] <= match["firstUseAt"] <= now <
            match["expiresAt"] <= policy["expiresAt"], "PRODUCTIVE_POLICY_EXPIRED")
        recipient = state.get("recipient")
        if recipient is not None:
            require(now < policy["expiresAt"] <= recipient.expires_at, "PRODUCTIVE_KEY_EXPIRED")
    _productive_passive(state, whole=whole)


def _productive_time(state, *, finish=False, keyring=None):
    P, caps = state["P"], state["binding"].view.caps
    local = time.monotonic()  # Actual LOCAL immediately before actual RAW; never a renewal.
    first = P.O.clocks.observe()
    require(P.O.clocks.validate_reading(first) is first, "PRODUCTIVE_ACTUAL_CLOCK_RETURN")
    end = caps.operationFinishEndNs if finish else caps.workEndNs
    local_end = caps.operationFinishEndLocal if finish else caps.workEndLocal
    if keyring is not None:
        require(state["keyring"] is keyring and state["keyring_complete"] is None, "PRODUCTIVE_KEYRING_ORIGINAL")
        end, local_end = min(end, keyring.workEndNs), min(local_end, keyring.workEndLocal)
    require(type(local) is float and math.isfinite(local) and state["last_local"] <= local < local_end and
        first.clock == caps.clock and state["last_ns"] <= first.nanoseconds < end, "PRODUCTIVE_OPERATION_EXPIRED")
    state["last_ns"], state["last_local"] = first.nanoseconds, local
    return first, local


def _productive_guard(binding, *, finish=False, whole=False):
    state = _productive_enter(binding)
    try:
        require(state["status"] == "RUNNING", "PRODUCTIVE_OPERATION_NOT_RUNNING")
        _productive_current(state, whole=whole)
        _productive_time(state, finish=finish)
        _productive_passive(state, whole=whole)
        return binding.view.caps
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _checked_productive_validation_binding(binding):
    require(type(binding) is _ProductiveValidationBinding, "PRODUCTIVE_VALIDATION_BINDING")
    _productive_finish_guard(binding)
    return binding.view


def _checked_productive_export_binding(binding):
    require(type(binding) is _ProductiveExportBinding, "PRODUCTIVE_EXPORT_BINDING")
    _productive_finish_guard(binding)
    return binding.view


def _productive_work_guard(binding):
    return _productive_guard(binding)


def _productive_finish_guard(binding):
    return _productive_guard(binding, finish=True)


def _productive_whole_guard(binding):
    return _productive_guard(binding, finish=True, whole=True)


def _productive_expected_node(binding, relative):
    state = _productive_enter(binding)
    try:
        require(state["mode"] == "export" and state["status"] == "RUNNING" and type(relative) is str and
            relative in state["nodes"], "PRODUCTIVE_EXPECTED_PATH")
        _productive_current(state)
        node = state["nodes"][relative]
        _productive_pin_current(state["node_pins"][id(node)][0])
        _productive_passive(state)
        return node
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _productive_node_guard(binding, node):
    state = _productive_enter(binding)
    try:
        require(state["mode"] == "export" and state["status"] == "RUNNING", "PRODUCTIVE_NODE_MODE")
        row = state["node_pins"].get(id(node))
        require(type(row) is tuple and row[0][0] is node and state["nodes"].get(node.relative) is node,
            "PRODUCTIVE_NODE_NOT_ORIGINAL")
        _productive_current(state)
        _productive_pin_current(row[0])
        if row[1] is not None:
            _productive_pin_current(row[1])
        _productive_time(state)
        _productive_passive(state)
        return node
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _productive_native(info, role):
    if role == "windows-x64":
        require(type(info) is windows.files.FileInfo, "PRODUCTIVE_WINDOWS_SNAPSHOT_TYPE")
        return ("windows", *info.identity, info.is_directory, info.size, info.links, info.attributes,
            info.creation_100ns, info.modified_100ns, info.change_100ns, info.owner_sid, info.protected_dacl)
    require(type(info) is tuple and len(info) == 8 and all(type(value) is int for value in info),
        "PRODUCTIVE_POSIX_SNAPSHOT_TYPE")
    return ("posix", *info)


def _productive_check_snapshot(binding, entries):
    state = _productive_enter(binding)
    try:
        expected_type = MappingProxyType if binding.view.role == "windows-x64" else dict
        require(state["mode"] == "export" and state["status"] == "RUNNING" and type(entries) is expected_type and
            all(type(name) is str for name in entries) and set(entries) == set(state["nodes"]),
            "PRODUCTIVE_SNAPSHOT_ROSTER")
        _productive_current(state, whole=True)
        for name, info in entries.items():
            actual = _productive_native(info, binding.view.role)
            expected = state["nodes"][name].native
            require(len(actual) == len(expected) and all(type(left) is type(right) and left == right
                for left, right in zip(actual, expected)), "PRODUCTIVE_SNAPSHOT_NATIVE")
        _productive_time(state)
        _productive_passive(state, whole=True)
        return entries  # DATA comparison only; never a snapshot owner/receipt.
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _productive_keyring_begin(binding):
    state = _productive_enter(binding)
    try:
        require(state["mode"] == "export" and state["status"] == "RUNNING" and state["keyring"] is None,
            "PRODUCTIVE_KEYRING_ONCE")
        _productive_current(state)
        first, local = _productive_time(state)
        P, caps = state["P"], binding.view.caps
        limit = 30 * P.O.NS
        end = min(P.O.integer(first.nanoseconds + limit), caps.workEndNs)
        # Move the saved earlier CHILD projection backwards, rounding only
        # earlier; an actual operation sample may further shorten it, never renew.
        remaining = math.nextafter((caps.workEndNs - end) / P.O.NS, math.inf)
        inherited = math.nextafter(caps.workEndLocal - remaining, -math.inf)
        local_end = min(inherited, P.O.wire._directed_deadline(local, 30, end, first.nanoseconds))
        require(local < local_end <= caps.workEndLocal, "PRODUCTIVE_KEYRING_LOCAL_CAP")
        cap = _ProductiveKeyringCap(first, local, end, local_end, limit)
        state["keyring"] = cap
        state["keyring_pin"] = _productive_pin(cap, _ProductiveKeyringCap,
            ("first", "firstLocal", "workEndNs", "workEndLocal", "limitNs"))
        state["pins"] += (_productive_pin(first, P.O.clocks.Reading, ("clock", "nanoseconds")),
            _productive_pin(first.clock, P.O.clocks.ClockIdentity, ("role", "domain", "ticks_per_second")))
        _productive_passive(state)
        return cap
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _productive_keyring_guard(binding, cap):
    state = _productive_enter(binding)
    try:
        require(state["mode"] == "export" and state["status"] == "RUNNING", "PRODUCTIVE_KEYRING_MODE")
        _productive_current(state)
        _productive_time(state, keyring=cap)
        _productive_passive(state)
        return cap
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _productive_keyring_complete(binding, cap):
    state = _productive_enter(binding)
    try:
        require(state["mode"] == "export" and state["status"] == "RUNNING", "PRODUCTIVE_KEYRING_MODE")
        _productive_current(state)
        observation = _productive_time(state, keyring=cap)
        state["keyring_complete_pin"] = _productive_observation_pin(state, observation)
        state["keyring_complete"] = observation
        _productive_passive(state)
        return cap
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _productive_recipient(state, recipient):
    native_windows = state["binding"].view.role == "windows-x64"
    names = (("work", "executable", "executable_sha256", "work_identity", "fingerprint",
        "encryption_fingerprint", "expires_at", "key_sha256", "job_id") if native_windows else
        ("work_dir", "home", "executable", "fingerprint", "encryption_fingerprint", "expires_at",
         "key_sha256", "work_identity"))
    kind = windows.Recipient if native_windows else posix.Recipient
    pin = _productive_pin(recipient, kind, names)
    declared = state["policy"]["recipient"]
    require(recipient.fingerprint == declared["fingerprint"] and recipient.key_sha256 == declared["sha256"] and
        type(recipient.encryption_fingerprint) is str and re.fullmatch(r"[0-9A-F]{40}", recipient.encryption_fingerprint) and
        type(recipient.expires_at) is int and recipient.expires_at >= state["policy"]["expiresAt"],
        "PRODUCTIVE_RECIPIENT_POLICY")
    validation = state["validation_view"]
    require(type(recipient.work_identity) is tuple and len(recipient.work_identity) == 2,
        "PRODUCTIVE_RECIPIENT_NATIVE_IDENTITY")
    if native_windows:
        require(recipient.work is validation.work and recipient.job_id == validation.source.job_id and
            recipient.work_identity == validation.work.identity, "PRODUCTIVE_RECIPIENT_WORK")
        _sha(recipient.executable_sha256)
        paths = (recipient.executable, recipient.work.path)
    else:
        require(recipient.work_dir is validation.work and recipient.home == validation.work / "gnupg",
            "PRODUCTIVE_RECIPIENT_WORK")
        paths = (recipient.work_dir, recipient.home, recipient.executable)
    state["recipient"], state["recipient_pin"], state["recipient_paths"] = recipient, pin, _paths_pin(paths)


def _productive_native_shape(native, role, kind):
    """Full tagged native vector, not a filename/hash standing in for custody."""
    if role == "windows-x64":
        require(type(native) is tuple and len(native) == 12 and native[0] == "windows" and
            type(native[1]) is int and 0 <= native[1] < 2 ** 64 and type(native[2]) is str and
            re.fullmatch(r"[0-9a-f]{32}", native[2]) and type(native[3]) is bool and
            native[3] is (kind == "directory") and all(type(value) is int and 0 <= value < 2 ** 64
                for value in native[4:10]) and (native[10] is None or type(native[10]) is str and
                re.fullmatch(r"S-[0-9]+(?:-[0-9]+)+", native[10])) and
            (native[11] is None or type(native[11]) is bool), "PRODUCTIVE_WINDOWS_NATIVE")
        return native[4]
    require(type(native) is tuple and len(native) == 9 and native[0] == "posix" and
        all(type(value) is int and 0 <= value < 2 ** 64 for value in native[1:]) and
        (stat.S_ISDIR(native[3]) if kind == "directory" else stat.S_ISREG(native[3])),
        "PRODUCTIVE_POSIX_NATIVE")
    return native[6]


def _productive_nodes(state):
    PC, CD, view = state["PC"], state["CD"], state["binding"].view
    require(type(view.partitions) is tuple and len(view.partitions) == 30 and type(CD.GROUPS) is tuple and
        len(CD.GROUPS) == len(set(CD.GROUPS)) == 30, "PRODUCTIVE_PARTITION_ROSTER")
    rows, by_name, by_node, partitions, native_ids = [], {}, {}, [], set()

    def add(node, relative, kind, partition):
        pin = _productive_pin(node, PC.ExpectedNode, _NODE_FIELDS)
        require(type(node.relative) is str and node.relative == relative and type(node.kind) is str and
            node.kind == kind and relative not in by_name and id(node) not in by_node, "PRODUCTIVE_NODE_PATH_KIND")
        native = node.native
        file_size = _productive_native_shape(native, view.role, kind)
        native_id = native[:3]
        require(native_id not in native_ids, "PRODUCTIVE_NATIVE_ALIAS")
        native_ids.add(native_id)
        if kind == "directory":
            require(node.bytes is None and node.sha256 is None, "PRODUCTIVE_DIRECTORY_SENTINELS")
        else:
            require(type(node.bytes) is int and 0 <= node.bytes <= posix.MAX_BYTES and node.bytes == file_size,
                "PRODUCTIVE_FILE_SIZE")
            _sha(node.sha256)
        by_name[relative], by_node[id(node)] = node, (pin, partition)
        rows.append((node, pin, partition))

    add(view.payload_root, "", "directory", None)
    for ordinal, (group, partition) in enumerate(zip(CD.GROUPS, view.partitions), 1):
        pin = _productive_pin(partition, PC.PartitionView, _PARTITION_FIELDS)
        require(type(partition.ordinal) is int and partition.ordinal == ordinal and type(partition.group) is str and
            partition.group == group and type(partition.members) is tuple and partition.members,
            "PRODUCTIVE_PARTITION_SHAPE")
        partitions.append(pin)
        add(partition.root, group, "directory", pin)
        for node in partition.members:
            require(type(node) is PC.ExpectedNode and type(node.relative) is str and
                re.fullmatch(re.escape(group) + r"/member-[0-9]{5}\.bin", node.relative), "PRODUCTIVE_MEMBER_NAME")
            add(node, node.relative, "file", pin)
        add(partition.map, "map-" + group + ".json", "file", pin)
    add(view.index, "copy-index.json", "file", None)
    require(len(rows) <= posix.MAX_MEMBERS and
        sum(node.bytes for node, _pin, _partition in rows if node.kind == "file") <= posix.MAX_BYTES,
        "PRODUCTIVE_CORPUS_LIMIT")
    state.update(partitions=view.partitions, partition_pins=tuple(partitions), node_rows=tuple(rows),
        nodes=by_name, node_pins=by_node)


def _productive_public_inputs(state):
    view, match, policy = state["binding"].view, state["match"], state["policy"]
    raw = view.public_inputs
    require(type(raw) is bytes and 0 < len(raw) <= MANIFEST_LIMIT, "PRODUCTIVE_PUBLIC_BYTES")
    value = I.parse(raw, MANIFEST_LIMIT)
    _fields(value, set("schema scope kind selection source github policy initialRecipient productive copy".split()))
    require(_canonical(value) == raw and type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == "INITIAL_RECIPIENT_PRODUCTIVE_MANIFEST_INPUTS_V1" and value["kind"] == "worker" and
        value["selection"] == match["github"]["selection"] and value["source"] == match["source"],
        "PRODUCTIVE_PUBLIC_IDENTITY")
    github = value["github"]
    _fields(github, set(match["github"]) | {"repository", "eventSha256"})
    _sha(github["eventSha256"])
    require(github == {**match["github"], "repository": I.REPOSITORY, "eventSha256": github["eventSha256"]},
        "PRODUCTIVE_PUBLIC_GITHUB")
    require(value["policy"] == {**match["policy"], "fingerprint": policy["recipient"]["fingerprint"],
        "keySha256": policy["recipient"]["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14},
        "PRODUCTIVE_PUBLIC_POLICY")
    initial = value["initialRecipient"]
    _fields(initial, set("authority environment originalBase reviewed firstUseAt notBefore expiresAt matchSha256 preExportReturnSha256 preExportIndexSha256".split()))
    for name in ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt"):
        require(type(initial[name]) is type(match[name]) and initial[name] == match[name], "PRODUCTIVE_PUBLIC_INITIAL")
    require(initial["matchSha256"] == hashlib.sha256(state["validation_view"].original_match_raw).hexdigest(),
        "PRODUCTIVE_PUBLIC_MATCH")
    for name in ("matchSha256", "preExportReturnSha256", "preExportIndexSha256"):
        _sha(initial[name])
    productive = value["productive"]
    _fields(productive, set("originalProposalSha256 producerHandoffSha256 producerReturnSha256 producerStepOutcome afterSaveSha256 afterSaveStepOutcome probeSha256 afterProbeStepOutcome prefixRetentionSha256".split()))
    for name, item in productive.items():
        if name.endswith("StepOutcome"):
            require(type(item) is str and item == "success", "PRODUCTIVE_PUBLIC_PREDECESSOR")
        else:
            _sha(item)
    copied = value["copy"]
    _fields(copied, set("scope groups index dataFiles mapFiles indexFiles archiveFiles archiveNativeNodes plaintextBytes".split()))
    require(copied["scope"] == "INITIAL_RECIPIENT_PRODUCTIVE_FIXED30_ARCHIVE_BINDING_V1" and
        type(copied["groups"]) is list and len(copied["groups"]) == 30, "PRODUCTIVE_PUBLIC_COPY")
    data_files, data_bytes, map_bytes = 0, 0, 0
    for ordinal, (group, partition) in enumerate(zip(copied["groups"], view.partitions), 1):
        _fields(group, {"ordinal", "group", "map", "dataFiles", "dataBytes"})
        expected_count = len(partition.members)
        expected_bytes = sum(node.bytes for node in partition.members)
        require(type(group["ordinal"]) is int and group["ordinal"] == ordinal and group["group"] == partition.group and
            type(group["dataFiles"]) is int and group["dataFiles"] == expected_count and
            type(group["dataBytes"]) is int and group["dataBytes"] == expected_bytes,
            "PRODUCTIVE_PUBLIC_GROUP")
        _fields(group["map"], {"name", "bytes", "sha256"})
        require(type(group["map"]["bytes"]) is int and group["map"] == {"name": partition.map.relative,
            "bytes": partition.map.bytes, "sha256": partition.map.sha256}, "PRODUCTIVE_PUBLIC_MAP")
        data_files += expected_count
        data_bytes += expected_bytes
        map_bytes += partition.map.bytes
    _fields(copied["index"], {"name", "bytes", "sha256"})
    require(type(copied["index"]["bytes"]) is int and copied["index"] == {"name": "copy-index.json",
        "bytes": view.index.bytes, "sha256": view.index.sha256}, "PRODUCTIVE_PUBLIC_INDEX")
    counts = {"dataFiles": data_files, "mapFiles": 30, "indexFiles": 1, "archiveFiles": data_files + 31,
        "archiveNativeNodes": data_files + 62, "plaintextBytes": data_bytes + map_bytes + view.index.bytes}
    require(all(type(copied[name]) is int and copied[name] == expected for name, expected in counts.items()) and
        copied["archiveNativeNodes"] == len(state["node_rows"]), "PRODUCTIVE_PUBLIC_COUNTS")
    state["public"], state["public_pin"] = value, _graph(value)


def _productive_manifest(binding, digest, size):
    state = _productive_enter(binding)
    try:
        require(state["mode"] == "export" and state["status"] == "RUNNING", "PRODUCTIVE_MANIFEST_MODE")
        _sha(digest)
        require(type(size) is int and 32 < size <= posix.MAX_CIPHERTEXT_BYTES, "PRODUCTIVE_CIPHERTEXT_SIZE")
        _productive_current(state, whole=True)
        _productive_time(state)
        recipient = state["recipient"]
        result = _copy(state["public"])
        result.update(scope="ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_PRODUCTIVE_EVIDENCE_V1",
            recipient={"fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
                "keySha256": recipient.key_sha256, "expiresAt": recipient.expires_at},
            artifact={"name": posix.ARTIFACT, "sha256": digest, "size": size}, testAcceptance="NOT_PERFORMED",
            productiveAuthority=False, cacheAuthority=False, exportSaveAuthority=False, budgetAcceptance="NOT_ADMITTED")
        raw = _canonical(result)
        _productive_passive(state, whole=True)
        return raw  # Formatting only; backend still owes native publication/readback/known close.
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _productive_admit(state, archive=None, recipient=None):
    P, PC, CD = _productive_modules()
    # Pin suppliers BEFORE the first fallible PC/checker/parser callback. A
    # callback cannot replace a method and have its replacement adopted later.
    backend = windows if os.name == "nt" else posix
    methods = tuple((owner, name, getattr(owner, name)) for owner, names in (
        (PC, ("P", "C", "N", "B", "O", "ValidationView", "ArchiveView", "ValidationCaps", "ArchiveCaps",
            "ChildSourceBinding", "PartitionView", "ExpectedNode", "checked_child_validation", "check_child_validation",
            "checked_child_archive", "check_child_archive", "archive_liveness", "checked_retired_child_validation",
            "check_retired_child_archive")),
        (CD, ("GROUPS",)), (P, ("_credential_free",)), (P.O, ("integer", "NS", "clocks", "wire")),
        (P.O.clocks, ("Reading", "ClockIdentity", "observe", "validate_reading", "validate_identity")),
        (P.O.wire, ("_directed_deadline",)), (P.N.initial_identity, ("_match",)),
        (backend, ("Recipient", "_ProductiveValidationReturn", "_ProductiveExportReturn", "_ProductiveArtifact",
            "_validate_initial_productive", "_export_initial_productive", "_finish_initial_productive",
            "_checked_productive_validation_return", "_checked_productive_export_return")),
        (time, ("time", "monotonic")), (I, ("_policy", "parse", "encoded")),
        (S, ("POLICY_SHA256", "joint")), (S.joint, ("OWNER_LOGIN",)),
        (sys.modules[__name__], ("MappingProxyType", "_ProductiveValidationBinding", "_ProductiveExportBinding", "_ProductiveKeyringCap",
            "ProductiveValidationReturn", "ProductiveBackendReturn", "_productive_pin", "_productive_pin_current",
            "_productive_start", "_productive_original", "_productive_enter", "_productive_admit", "_productive_fail",
            "_productive_refs", "_productive_passive", "_productive_current", "_productive_time",
            "_productive_guard", "_productive_observation_pin", "_productive_recipient", "_productive_native_shape", "_productive_nodes",
            "_productive_public_inputs", "_productive_finish_return", "_checked_productive_return",
            "_checked_productive_validation_binding", "_checked_productive_export_binding",
            "_productive_work_guard", "_productive_finish_guard", "_productive_whole_guard",
            "_productive_expected_node", "_productive_node_guard", "_productive_native", "_productive_check_snapshot",
            "_productive_keyring_begin", "_productive_keyring_guard", "_productive_keyring_complete",
            "_productive_manifest", "_graph", "_graph_current", "_canonical", "_paths_pin", "_paths_current")),
    ) for name in names)
    environment = tuple((name, os.environ.get(name)) for name in ("GITHUB_ACTIONS", "GITHUB_REPOSITORY",
        "GITHUB_SERVER_URL", "GITHUB_API_URL", "RUNNER_ENVIRONMENT", "GITHUB_EVENT_NAME", "GITHUB_REF",
        "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF", "GITHUB_JOB", "GITHUB_RUN_ID",
        "GITHUB_RUN_ATTEMPT", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME", "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH"))
    state.update(P=P, PC=PC, CD=CD, backend=backend, methods=methods, environment=environment)

    def original_suppliers():
        require(state["failure"] is None and state["busy"] and state["status"] == "STARTED" and
            all(getattr(owner, name, None) is original for owner, name, original in methods) and
            all(os.environ.get(name) == original for name, original in environment), "PRODUCTIVE_ADMISSION_CHANGED")

    mode, child = state["mode"], state["child"]
    if mode == "validation":
        view = PC.checked_child_validation(child)
        original_suppliers()
        view_pin = _productive_pin(view, PC.ValidationView, _VALIDATION_VIEW_FIELDS)
        validation = view
        binding = _ProductiveValidationBinding(view)
    else:
        prior = _PRODUCTIVE_ATTEMPTS.get(("validation", id(child)))
        require(type(prior) is dict and prior["child"] is child and prior["status"] == "RETURNED" and
            prior["recipient"] is recipient, "PRODUCTIVE_ORIGINAL_VALIDATION_REQUIRED")
        checked_productive_validation_return(prior["result"], child)
        original_suppliers()
        validation = prior["binding"].view
        view = PC.checked_child_archive(child, archive, recipient)
        original_suppliers()
        view_pin = _productive_pin(view, PC.ArchiveView, _ARCHIVE_VIEW_FIELDS)
        require(view.archive is archive and view.recipient is recipient, "PRODUCTIVE_ORIGINAL_ARCHIVE")
        binding = _ProductiveExportBinding(view)
    require(state["failure"] is None and state["busy"] and state["status"] == "STARTED" and view.child is child,
        "PRODUCTIVE_ADMISSION_REENTRY")
    caps = view.caps
    caps_pin = _productive_pin(caps, PC.ValidationCaps if mode == "validation" else PC.ArchiveCaps, _CAP_FIELDS)
    P.O.clocks.validate_reading(caps.first)
    require(caps.clock is caps.first.clock and caps.clock.role == view.role and
        view.role in P.O.clocks.DOMAINS and (os.name == "nt") is (view.role == "windows-x64"), "PRODUCTIVE_CAP_CLOCK")
    for name in ("workEndNs", "operationFinishEndNs", "finishReserveNs", "operationLimitNs"):
        P.O.integer(getattr(caps, name))
    require(caps.operationLimitNs == (60 if mode == "validation" else 240) * P.O.NS and
        caps.finishReserveNs == (30 * P.O.NS if view.role == "windows-x64" else 0) and
        caps.first.nanoseconds < caps.workEndNs <= caps.operationFinishEndNs - caps.finishReserveNs and
        caps.operationFinishEndNs <= caps.first.nanoseconds + caps.operationLimitNs and
        all(type(getattr(caps, name)) is float and math.isfinite(getattr(caps, name)) and getattr(caps, name) >= 0
            for name in ("firstLocal", "workEndLocal", "operationFinishEndLocal")) and
        caps.firstLocal < caps.workEndLocal <= caps.operationFinishEndLocal - caps.finishReserveNs / P.O.NS and
        caps.operationFinishEndLocal <= caps.firstLocal + caps.operationLimitNs / P.O.NS,
        "PRODUCTIVE_ORIGINAL_OPERATION_CAP")
    policy, public_key = I._policy(validation.policy_raw, int(time.time()))
    original_suppliers()
    require(type(validation.public_key_raw) is bytes and validation.public_key_raw == public_key and
        hashlib.sha256(validation.policy_raw).hexdigest() == S.POLICY_SHA256 and
        policy["retrievalOwner"] == S.joint.OWNER_LOGIN, "PRODUCTIVE_POLICY_KEY_BINDING")
    match = I.parse(validation.original_match_raw, S.LIMIT)
    original_suppliers()
    require(type(validation.original_match_raw) is bytes and I.encoded(match) == validation.original_match_raw,
        "PRODUCTIVE_MATCH_ENCODING")
    _profile, role = P.N.initial_identity._match(match)
    original_suppliers()
    blob = hashlib.sha1(b"blob " + str(len(validation.policy_raw)).encode("ascii") + b"\0" + validation.policy_raw).hexdigest()
    require(role == view.role and match["policy"]["blob"] == blob, "PRODUCTIVE_MATCH_POLICY")
    source_pin = _productive_pin(validation.source, PC.ChildSourceBinding, _SOURCE_FIELDS)
    require(type(validation.source.job_id) is str and re.fullmatch(r"[0-9a-f]{32}", validation.source.job_id),
        "PRODUCTIVE_SOURCE_JOB")
    native_windows = view.role == "windows-x64"
    if native_windows:
        require(type(validation.work) is windows.files.PrivateDirectory, "PRODUCTIVE_WORK_ROOT_TYPE")
        if mode == "export":
            require(type(view.payload) is windows.files.PrivateDirectory and type(view.output) is windows.files.PrivateDirectory,
                "PRODUCTIVE_ARCHIVE_ROOT_TYPE")
    else:
        require(type(validation.work) is PosixPath and validation.work.is_absolute(), "PRODUCTIVE_WORK_ROOT_TYPE")
        if mode == "export":
            require(type(view.payload) is PosixPath and type(view.output) is PosixPath and
                view.payload.is_absolute() and view.output.is_absolute(), "PRODUCTIVE_ARCHIVE_ROOT_TYPE")
    state.update(binding=binding, backend=backend, validation_view=validation, methods=methods,
        pins=(_productive_pin(binding, type(binding), ("view",)), view_pin, caps_pin, source_pin,
            _productive_pin(caps.first, P.O.clocks.Reading, ("clock", "nanoseconds")),
            _productive_pin(caps.clock, P.O.clocks.ClockIdentity, ("role", "domain", "ticks_per_second"))),
        policy=policy, policy_pin=_graph(policy), match=match, match_pin=_graph(match),
        recipient=None, recipient_pin=None, last_ns=caps.first.nanoseconds, last_local=caps.firstLocal)
    _PRODUCTIVE_BINDINGS[id(binding)] = state
    if mode == "export":
        _productive_recipient(state, recipient)
        _productive_nodes(state)
        _productive_public_inputs(state)
    _productive_current(state, whole=True)
    _productive_time(state)
    state["status"], state["busy"] = "RUNNING", False
    return binding


def _productive_finish_return(state, backend_result):
    binding, backend = state["binding"], state["backend"]
    _productive_enter(binding)
    try:
        require(state["status"] == "RUNNING" and state["backend_result"] is backend_result, "PRODUCTIVE_BACKEND_RETURN")
        validation = state["mode"] == "validation"
        names = (("binding", "session", "recipient", "observations", "known_close") if validation else
            ("binding", "session", "manifest_raw", "artifact", "observations", "known_close"))
        kind = backend._ProductiveValidationReturn if validation else backend._ProductiveExportReturn
        pin = _productive_pin(backend_result, kind, names)
        require(backend_result.binding is binding, "PRODUCTIVE_BACKEND_BINDING_CHANGED")
        checker = backend._checked_productive_validation_return if validation else backend._checked_productive_export_return
        require(checker(backend_result, binding) is backend_result, "PRODUCTIVE_BACKEND_NOT_KNOWN_CLOSED")
        _productive_pin_current(pin)
        state["backend_pin"] = pin
        if validation:
            _productive_recipient(state, backend_result.recipient)
        else:
            require(state["keyring"] is not None and state["keyring_complete"] is not None,
                "PRODUCTIVE_KEYRING_NOT_COMPLETED")
            artifact = backend_result.artifact
            artifact_pin = _productive_pin(artifact, backend._ProductiveArtifact, ("name", "sha256", "size", "native"))
            require(artifact.name == posix.ARTIFACT and type(artifact.size) is int and 32 < artifact.size <= posix.MAX_CIPHERTEXT_BYTES,
                "PRODUCTIVE_RETURN_ARTIFACT")
            require(_productive_native_shape(artifact.native, binding.view.role, "file") == artifact.size,
                "PRODUCTIVE_RETURN_ARTIFACT_NATIVE_SIZE")
            _sha(artifact.sha256)
            raw = backend_result.manifest_raw
            require(type(raw) is bytes and 0 < len(raw) <= MANIFEST_LIMIT, "PRODUCTIVE_RETURN_MANIFEST")
            manifest = I.parse(raw, MANIFEST_LIMIT)
            expected = _copy(state["public"])
            recipient = state["recipient"]
            expected.update(scope="ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_PRODUCTIVE_EVIDENCE_V1",
                recipient={"fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
                    "keySha256": recipient.key_sha256, "expiresAt": recipient.expires_at},
                artifact={"name": artifact.name, "sha256": artifact.sha256, "size": artifact.size},
                testAcceptance="NOT_PERFORMED", productiveAuthority=False, cacheAuthority=False,
                exportSaveAuthority=False, budgetAcceptance="NOT_ADMITTED")
            require(raw == _canonical(expected) == _canonical(manifest), "PRODUCTIVE_MANIFEST_RETURN_CHANGED")
            state["artifact_pin"] = artifact_pin
        _productive_current(state, whole=True)
        completion = _productive_time(state, finish=True)
        state["completion_pin"] = _productive_observation_pin(state, completion)
        state["completion"] = completion
        observations = (backend_result.observations, completion)
        result = (ProductiveValidationReturn(binding.view, state["recipient"], backend_result, observations,
            backend_result.known_close) if validation else ProductiveBackendReturn(binding.view, backend_result,
                backend_result.manifest_raw, backend_result.artifact, observations, backend_result.known_close))
        result_pin = _productive_pin(result, type(result), tuple(result.__dataclass_fields__))
        state.update(result=result, result_pin=result_pin, status="RETURNED")
        _PRODUCTIVE_RETURNS[id(result)] = state
        _productive_passive(state, whole=True)
        return result
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def _checked_productive_return(result, target, *, validation, retired):
    state = _PRODUCTIVE_RETURNS.get(id(result))
    kind = ProductiveValidationReturn if validation else ProductiveBackendReturn
    require(type(result) is kind and type(state) is dict and state["result"] is result and
        (result.view.child is target if validation else result.view is target), "PRODUCTIVE_RESULT_NOT_ORIGINAL")
    binding = state["binding"]
    _productive_enter(binding)
    try:
        require(state["status"] == "RETURNED" and state["completion"] is not None, "PRODUCTIVE_RESULT_INCOMPLETE")
        _productive_pin_current(state["result_pin"])
        _productive_pin_current(state["backend_pin"])
        if not validation:
            _productive_pin_current(state["artifact_pin"])
        backend = state["backend"]
        checker = backend._checked_productive_validation_return if validation else backend._checked_productive_export_return
        require(checker(state["backend_result"], binding) is state["backend_result"], "PRODUCTIVE_BACKEND_RETURN_CHANGED")
        # Completed suboperations retain their actual in-window observations.
        # Only CURRENT enclosing PC authority is checked here, never a restarted
        # or already-spent validation/keyring/export cap. Retired checks are passive.
        _productive_current(state, whole=True, retired=retired)
        _productive_pin_current(state["result_pin"])
        return result
    except BaseException as error:
        raise _productive_fail(state, error)
    finally:
        state["busy"] = False


def validate_initial_productive_recipient(child):
    state = _productive_start(child, "validation")
    try:
        binding = _productive_admit(state)
        returned = state["backend"]._validate_initial_productive(binding)
        state["backend_result"] = returned  # Retain ACTUAL result before any callback.
        result = _productive_finish_return(state, returned)
        return checked_productive_validation_return(result, child)
    except BaseException as error:
        raise _productive_fail(state, error)


def export_initial_productive_encrypted(child, archive, recipient):
    state = _productive_start(child, "export")
    try:
        binding = _productive_admit(state, archive, recipient)
        returned = state["backend"]._export_initial_productive(binding)
        state["backend_result"] = returned
        result = _productive_finish_return(state, returned)
        return checked_productive_backend_return(result, binding.view)
    except BaseException as error:
        raise _productive_fail(state, error)


def checked_productive_validation_return(result, child):
    return _checked_productive_return(result, child, validation=True, retired=False)


def checked_productive_backend_return(result, view):
    return _checked_productive_return(result, view, validation=False, retired=False)


def checked_retired_productive_validation_return(result, child):
    return _checked_productive_return(result, child, validation=True, retired=True)


def checked_retired_productive_backend_return(result, view):
    return _checked_productive_return(result, view, validation=False, retired=True)


def _match_pin(value, kind):
    expected = G.GateEligibility if kind == "gate" else S.BootstrapMatch
    require(type(value) is expected and type(value.__dict__) is dict and
            set(value.__dict__) == {"record"} and type(value.record) is bytes and
            0 < len(value.record) <= S.LIMIT, "MATCH_TYPE")
    return value, expected, value.__dict__, value.record


def _match_current(pin):
    value, kind, dictionary, raw = pin
    require(type(value) is kind and value.__dict__ is dictionary and set(dictionary) == {"record"} and
            type(value.record) is bytes and value.record == raw, "MATCH_CHANGED")


def _paths_pin(paths):
    result = []
    for path in paths:
        require(type(path) in (PosixPath, WindowsPath) and path.is_absolute() and ".." not in path.parts,
                "PATH_TYPE")
        result.append((path, type(path), str(path), tuple(path.parts)))
    return tuple(result)


def _paths_current(pins):
    for path, kind, text, parts in pins:
        require(type(path) is kind and str(path) == text and tuple(path.parts) == parts, "PATH_CHANGED")


def _recipient_pin(recipient, native_windows, evidence, output):
    kind = windows.Recipient if native_windows else posix.Recipient
    names = (("work", "executable", "executable_sha256", "work_identity", "fingerprint",
              "encryption_fingerprint", "expires_at", "key_sha256", "job_id") if native_windows else
             ("work_dir", "home", "executable", "fingerprint", "encryption_fingerprint",
              "expires_at", "key_sha256", "work_identity"))
    require(type(recipient) is kind and type(recipient.__dict__) is dict and
            set(recipient.__dict__) == set(names), "RECIPIENT_TYPE")
    values = tuple(recipient.__dict__[name] for name in names)
    require(all(type(getattr(recipient, name)) is str and re.fullmatch(r"[0-9A-F]{40}", getattr(recipient, name))
                for name in ("fingerprint", "encryption_fingerprint")) and
            type(recipient.expires_at) is int and recipient.expires_at > 0, "RECIPIENT_PUBLIC_FIELDS")
    _sha(recipient.key_sha256)
    identity = recipient.work_identity
    require(type(identity) is tuple and len(identity) == 2 and type(identity[0]) is int and
            0 <= identity[0] < 2 ** 64, "RECIPIENT_IDENTITY")
    directories = []
    if native_windows:
        _sha(recipient.executable_sha256)
        require(type(recipient.job_id) is str and re.fullmatch(r"[0-9a-f]{32}", recipient.job_id) and
                type(identity[1]) is str and re.fullmatch(r"[0-9a-f]{32}", identity[1]), "RECIPIENT_IDENTITY")
        for directory in (recipient.work, evidence, output):
            require(type(directory) is windows.files.PrivateDirectory and directory._closed is False and
                    type(directory.identity) is tuple, "WINDOWS_PINNED_DIRECTORY")
            directories.append((directory, directory.__dict__, directory.path, directory.identity))
        require(recipient.work.identity == identity, "RECIPIENT_IDENTITY")
        paths = (recipient.executable, *(row[2] for row in directories))
    else:
        require(type(identity[1]) is int and 0 < identity[1] < 2 ** 64, "RECIPIENT_IDENTITY")
        paths = (recipient.work_dir, recipient.home, recipient.executable, evidence, output)
    return recipient, kind, recipient.__dict__, names, values, _paths_pin(paths), tuple(directories)


def _recipient_current(pin):
    recipient, kind, dictionary, names, values, paths, directories = pin
    require(type(recipient) is kind and recipient.__dict__ is dictionary and set(dictionary) == set(names),
            "RECIPIENT_CHANGED")
    for name, saved in zip(names, values):
        actual = dictionary[name]
        require(type(actual) is type(saved) and
                (actual == saved if type(saved) in (str, int) else actual is saved), "RECIPIENT_CHANGED")
    for directory, dictionary, path, identity in directories:
        require(type(directory) is windows.files.PrivateDirectory and directory.__dict__ is dictionary and
                directory.path is path and directory.identity is identity and directory._closed is False,
                "WINDOWS_DIRECTORY_CHANGED")
    _paths_current(paths)


def _manifest(*, kind, selection, source_commit, source_tree, match_raw, event_raw, policy_raw,
              primary, copied, authority, recipient, native_windows):
    """Current local binding only: this does not acquire HTTP or query Git."""
    require(acquisition.origin.wire.TOKEN_ENV not in os.environ, "TOKEN_IN_CRYPTO")
    value = I.parse(match_raw, S.LIMIT)
    require(match_raw == I.encoded(value), "MATCH_ENCODING")
    extras = ({"stage", "selector", "workerAdmission", "qualificationAcceptance"} if kind == "gate" else set())
    _fields(value, COMMON_MATCH | extras)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
            ("NONPRODUCTIVE_ELIGIBILITY" if kind == "gate" else S.STAGE1 + "_MATCH_ONLY_NOT_ADMISSION"), "MATCH_SCOPE")
    source = {"commit": I.sha(source_commit), "tree": I.sha(source_tree)}
    require(S.joint.source(value["originalBase"]) == S.BASE and
            S.joint.source(value["source"]) == S.joint.source(value["reviewed"]) == source and
            source["commit"] != S.BASE["commit"] and source["tree"] != S.BASE["tree"], "MATCH_SOURCE")
    current = int(time.time())
    policy, _public_key = I._policy(policy_raw, current)
    start, first, expires = (value[key] for key in ("notBefore", "firstUseAt", "expiresAt"))
    require(all(type(x) is int for x in (start, first, expires)) and
            policy["notBefore"] <= start <= first <= current < expires <= policy["expiresAt"] and
            expires - start <= 14 * 24 * 60 * 60 and policy["retrievalOwner"] == S.joint.OWNER_LOGIN,
            "MATCH_WINDOW")
    blob = hashlib.sha1(b"blob " + str(len(policy_raw)).encode("ascii") + b"\0" + policy_raw).hexdigest()
    require(hashlib.sha256(policy_raw).hexdigest() == S.POLICY_SHA256 and value["policy"] == {
        "origin": "reviewed-head", "commit": source_commit, "blob": blob,
        "path": I.POLICY_PATH, "sha256": S.POLICY_SHA256}, "POLICY_ORIGIN")
    declared = policy["recipient"]
    require(recipient.fingerprint == declared["fingerprint"] and recipient.key_sha256 == declared["sha256"] and
            current < policy["expiresAt"] <= recipient.expires_at, "RECIPIENT_POLICY")
    author = value["authority"]
    _fields(author, {"id", "url", "bodySha256", "owner", "ownerId", "createdAt"})
    S.positive(author["id"])
    _sha(author["bodySha256"])
    require(author["owner"] == S.joint.OWNER_LOGIN and type(author["ownerId"]) is int and
            author["ownerId"] == S.joint.OWNER_ID and author["url"] ==
            "https://github.com/" + I.REPOSITORY + "/issues/437#issuecomment-" + str(author["id"]) and
            0 < S.joint.timestamp(author["createdAt"]) <= first, "AUTHORITY_IDENTITY")
    S.environment(value["environment"])
    env = dict(os.environ)
    require(ROOT == ROOT.resolve(strict=True) and env.get("GITHUB_WORKSPACE") == str(ROOT), "WORKSPACE")
    actual_event = I.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    require(type(actual_event) is bytes and actual_event == event_raw, "EVENT_CHANGED")
    observed = acquisition._context(env, event_raw, kind, first)
    require(observed["source"] == source and observed["inputs"]["selection"] == selection and
            native_windows is (observed["role"] == "windows-x64"), "ACTUAL_SELECTION")
    github = dict(observed["github"])
    if kind == "worker":
        github.update(profile=S.bootstrap.PROFILE, selection=selection)
    require(value["github"] == github, "MATCH_JOB")
    if kind == "gate":
        require(value["stage"] == "stage1" and value["workerAdmission"] == "NOT_PERFORMED" and
                value["qualificationAcceptance"] == "NOT_ESTABLISHED_BY_GATE", "GATE_ONLY")
        selected = {"schema": 1, "scope": "INITIAL_RECIPIENT_SELECTED_APPROVAL_ONLY", "stage": "stage1",
            "runId": github["runId"], "runAttempt": github["runAttempt"], "commentId": author["id"],
            "bodySha256": author["bodySha256"], "environmentId": value["environment"]["id"],
            "environmentName": S.ENVIRONMENT,
            "approvalLine": "AUTHORIZE_INITIAL_RECIPIENT stage1 " + github["runId"] + "/" +
                github["runAttempt"] + " " + str(author["id"]) + " " + author["bodySha256"],
            "owner": {"login": S.joint.OWNER_LOGIN, "id": S.joint.OWNER_ID}}
        require(_graph(value["selector"])[1] == _graph(selected)[1], "GATE_SELECTOR")
    return {"schema": 4, "scope": SCOPE, "kind": kind, "selection": selection, "source": source,
        "github": {**github, "repository": I.REPOSITORY, "eventSha256": hashlib.sha256(event_raw).hexdigest()},
        "policy": {**value["policy"], "fingerprint": declared["fingerprint"], "keySha256": declared["sha256"],
                   "expiresAt": policy["expiresAt"], "retentionDays": 14},
        "initialRecipient": {"authority": author, "environment": value["environment"],
            "originalBase": value["originalBase"], "reviewed": value["reviewed"], "firstUseAt": first,
            "notBefore": start, "expiresAt": expires, "matchSha256": authority["matchSha256"],
            "freshReturnSha256": authority["returnSha256"]},
        "primary": _copy(primary), "copy": _copy(copied),
        "recipient": {"fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
                      "keySha256": recipient.key_sha256, "expiresAt": recipient.expires_at},
        "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"}


def export_encrypted(evidence, output, recipient, *, kind, selection, source_commit, source_tree,
                     original_match, fresh_match, event_raw, policy_raw, primary, copied, authority,
                     check, read_manifest, timeout_seconds, max_bytes=posix.MAX_BYTES,
                     max_members=posix.MAX_MEMBERS) -> bytes:
    """Return canonical ORIGINAL manifest bytes, not success/custody/Step authority.

    primary: step/outcome/resultSha256/handoffSha256/inventorySha256.
    copied: mapSha256/memberCount/totalBytes/origins, where origins is exactly
    PRIMARY/AUTHORITY_PRE_EXPORT/RECIPIENT_PRE_EXPORT -> original map SHA256.
    authority: returnSha256/matchSha256 of the actual fresh acquisition binding.
    All mappings are closed supplied data, never arbitrary public manifests.

    POSIX output is an ABSENT path reserved by the backend. Native Windows
    output/evidence are already-pinned, new-empty/read-only private directories.
    The caller keeps its owners and the same-process Recipient alive through
    actual backend return/readback and subsequent original known retirement.
    """
    require(type(kind) is str and kind in ("gate", "worker") and type(selection) is str, "KIND")
    require(os.name in ("posix", "nt") and callable(check) and callable(read_manifest), "CALLER")
    platform_name = os.name
    native_windows = platform_name == "nt"
    require(type(event_raw) is bytes and 0 < len(event_raw) <= I.EVENT_LIMIT and
            type(policy_raw) is bytes and 0 < len(policy_raw) <= I.POLICY_LIMIT, "ORIGINAL_BYTES")
    original_pin, fresh_pin = _match_pin(original_match, kind), _match_pin(fresh_match, kind)
    require(original_pin[3] == fresh_pin[3], "FRESH_MATCH_DIFFERS")
    input_pins = tuple(_graph(value) for value in (primary, copied, authority))
    recipient_pin = _recipient_pin(recipient, native_windows, evidence, output)
    _fields(primary, PRIMARY_FIELDS)
    require(primary["step"] == ("initial-originals" if kind == "gate" else "canonical-initialization") and
            primary["outcome"] == "success", "PRIMARY_STEP")
    for key in ("resultSha256", "handoffSha256", "inventorySha256"):
        _sha(primary[key])
    _fields(copied, COPY_FIELDS)
    _fields(copied["origins"], set(ORIGINS))
    _sha(copied["mapSha256"])
    for digest in copied["origins"].values():
        _sha(digest)
    require(len(set(copied["origins"].values())) == 3, "COPY_ORIGINS")
    _fields(authority, AUTHORITY_FIELDS)
    for digest in authority.values():
        _sha(digest)
    require(authority["matchSha256"] == hashlib.sha256(fresh_pin[3]).hexdigest(), "FRESH_MATCH_HASH")
    for value, maximum in ((max_bytes, posix.MAX_BYTES), (max_members, posix.MAX_MEMBERS), (timeout_seconds, 240)):
        require(type(value) is int and 0 < value <= maximum, "BOUNDS")
    require(type(copied["memberCount"]) is int and 0 < copied["memberCount"] <= max_members and
            type(copied["totalBytes"]) is int and 0 < copied["totalBytes"] <= max_bytes, "COPY_BOUNDS")
    retained_env = tuple((name, os.environ.get(name)) for name in (
        "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_API_URL", "RUNNER_ENVIRONMENT",
        "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_SHA", "GITHUB_WORKFLOW_SHA", "GITHUB_WORKFLOW_REF",
        "GITHUB_JOB", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "RUNNER_OS", "RUNNER_ARCH", "RUNNER_NAME",
        "GITHUB_WORKSPACE", "GITHUB_EVENT_PATH"))

    def passive():
        require(os.name == platform_name and acquisition.origin.wire.TOKEN_ENV not in os.environ and
                all(os.environ.get(name) == value for name, value in retained_env), "CONTEXT_CHANGED")
        _match_current(original_pin)
        _match_current(fresh_pin)
        _recipient_current(recipient_pin)
        for pin in input_pins:
            _graph_current(pin)

    def manifest():
        passive()
        check()
        passive()
        result = _manifest(kind=kind, selection=selection, source_commit=source_commit, source_tree=source_tree,
            match_raw=original_pin[3], event_raw=event_raw, policy_raw=policy_raw, primary=primary,
            copied=copied, authority=authority, recipient=recipient, native_windows=native_windows)
        result_pin = _graph(result)
        passive()
        check()
        passive()
        # A successful final guard can still expose expiry or changed fields.
        # This local currency sample is NOT another remote acquisition.
        current = int(time.time())
        passive()
        _graph_current(result_pin)
        require(result["initialRecipient"]["firstUseAt"] <= current < result["initialRecipient"]["expiresAt"] <=
                result["policy"]["expiresAt"] <= result["recipient"]["expiresAt"], "FINAL_WINDOW")
        return result

    expected = manifest()
    expected_shape = _graph(expected)[1]

    def factory():
        result = manifest()
        require(_graph(result)[1] == expected_shape, "MANIFEST_IDENTITY_CHANGED")
        return result  # A NEW dict each call; Windows will add artifact only to the first.

    if native_windows:
        returned = windows._export(evidence, output, recipient, factory, max_bytes=max_bytes,
                                   max_members=max_members, timeout_seconds=timeout_seconds)
    else:
        returned = posix._export_bound_manifest(evidence, output, recipient, manifest=factory(),
            max_bytes=max_bytes, max_members=max_members, timeout_seconds=timeout_seconds)
    returned_pin = _graph(returned)  # FIRST action after actual backend return; no callback/reader/encoder.
    require(type(returned) is dict and set(returned) == set(expected) | {"artifact"}, "RETURN_FIELDS")
    require(_graph({key: value for key, value in returned.items() if key != "artifact"})[1] == expected_shape,
            "RETURN_IDENTITY")
    artifact = returned["artifact"]
    _fields(artifact, {"name", "sha256", "size"})
    require(artifact["name"] == posix.ARTIFACT and type(artifact["size"]) is int and
            0 < artifact["size"] <= posix.MAX_CIPHERTEXT_BYTES, "RETURN_ARTIFACT")
    _sha(artifact["sha256"])
    passive()
    raw = _canonical(returned)  # The actual return is canonical-encoded ONCE, before any file reread.
    _graph_current(returned_pin)
    require(_graph(manifest())[1] == expected_shape, "RETURN_CURRENT_IDENTITY")
    _graph_current(returned_pin)
    actual = read_manifest()
    _graph_current(returned_pin)
    passive()
    require(type(actual) is bytes and 0 < len(actual) <= MANIFEST_LIMIT and actual == raw, "MANIFEST_READBACK")
    require(_graph(manifest())[1] == expected_shape, "FINAL_CURRENT_IDENTITY")
    _graph_current(returned_pin)
    passive()
    return raw
