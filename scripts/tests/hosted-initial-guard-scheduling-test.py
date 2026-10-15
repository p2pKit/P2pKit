#!/usr/bin/env python3
"""Exact guard scheduling controls, not native/hosted timing qualification.

Only selected public-source ASTs execute. Native owners, clocks, recipient and
entry seams below are explicitly synthetic; no native constructor, file reader,
process, real time, credentials or previous test suite is invoked.
"""
from __future__ import annotations

import __future__
import ast
from collections import Counter
from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest


ROOT = Path(__file__).resolve().parents[2]
BASELINES = {'run-hosted-initial-recipient-custody.py': '25c999787aa37f7c92dfd00ed513e11d1d251e1402288e2566cf374d533160c9', 'run-hosted-initial-recipient-tail.py': '9062bdc6d72a915d279c9f8ecce29096cded4028a0cff36f0d0734bd30256266'}
DELTAS = {'run-hosted-initial-recipient-custody.py': [(b'        self._local(anchor, final)\n        self._current(anchor)\n        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "BEFORE_FRONTIER_CHANGED")\n', b'        self._local(anchor, final)\n        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "BEFORE_FRONTIER_CHANGED")\n')], 'run-hosted-initial-recipient-tail.py': [(b'        self._local(anchor, final)\n        self.current()\n        require(anchor.busy and anchor.failure is None and anchor.last == frontier, "CHILD_CLOCK_CHANGED")\n', b'        self._local(anchor, final)\n        require(anchor.busy and anchor.failure is None and anchor.last == frontier, "CHILD_CLOCK_CHANGED")\n'), (b'            clock.current()\n            owner.structural()\n            require(owner.owner.fence is clock and owner.failure is None and not owner.owner.unknown and owner.errors == [] and\n', b'            require(type(clock) is _ChildClock and type(owner) is C._PrimaryOwner, "CAPTURE_ORIGINAL_CLOCK_AND_OWNER")\n            clock_anchor = clock.current()\n            require(type(clock_anchor) is _ChildAnchor and clock_anchor.handle is clock and\n                _CHILD_CLOCKS.get(id(clock)) is clock_anchor, "CAPTURE_ORIGINAL_CLOCK_RETURN")\n            owner_anchor = owner._anchor()\n            owners = clock_anchor.owners\n            require(type(owners) is tuple and any(type(pair) is tuple and len(pair) == 2 and\n                pair[0] is owner and pair[1] is owner_anchor for pair in owners), "CAPTURE_OWNER_NOT_ATTACHED")\n            require(owner.owner.fence is clock and owner.failure is None and not owner.owner.unknown and owner.errors == [] and\n')]}
SOURCES = {name: (ROOT / "scripts" / name).read_bytes() for name in BASELINES}
# Exact guarded-require scheduling inverse; never repin historical whole suppliers.
_HISTORY_REQUIRE_BASELINE = "3463f825e5d3864d867d5cb92cfee6d111344da0c7a97ea70b7df3dac5711b22"
_HISTORY_REQUIRE_CHANGES = [(b'        require(type(value) is kind, "RECIPIENT_HISTORY_CHANGED")\n', b'        if not (type(value) is kind):\n            require(False, "RECIPIENT_HISTORY_CHANGED")\n'), (b'        require(valid, "RECIPIENT_HISTORY_CHANGED")\n', b'        if not valid:\n            require(False, "RECIPIENT_HISTORY_CHANGED")\n')]


def guarded_require_preimage(raw):
    if type(raw) is not bytes:
        raise AssertionError("HISTORY_MAPPING_GUARDED_REQUIRE_BYTES")
    for before, after in reversed(_HISTORY_REQUIRE_CHANGES):
        if raw.count(after) != 1 or before in raw:
            raise AssertionError("HISTORY_MAPPING_GUARDED_REQUIRE_EXACT_CONTEXT")
        raw = raw.replace(after, before, 1)
    if hashlib.sha256(raw).hexdigest() != _HISTORY_REQUIRE_BASELINE:
        raise AssertionError("HISTORY_MAPPING_GUARDED_REQUIRE_WHOLE_52A_PREIMAGE")
    return raw


# Exact reviewed mapping-identity layer; preserve the historical whole supplier pin.
_HISTORY_MAPPING_BEFORE = b'            valid = len(value) == len(saved) and all(same(key, old_key) and same(item, old_item)\n                for (key, item), (old_key, old_item) in zip(value.items(), saved))\n'
_HISTORY_MAPPING_AFTER = b'            valid = len(value) == len(saved) and all((key is old_key and item is old_item) or\n                (same(key, old_key) and same(item, old_item))\n                for (key, item), (old_key, old_item) in zip(value.items(), saved))\n'


def history_source_preimage(raw):
    raw = guarded_require_preimage(raw)
    if type(raw) is not bytes or raw.count(_HISTORY_MAPPING_AFTER) != 1:
        raise AssertionError("HISTORY_MAPPING_EXACT_CONTEXT")
    original = raw.replace(_HISTORY_MAPPING_AFTER, _HISTORY_MAPPING_BEFORE, 1)
    if hashlib.sha256(original).hexdigest() != "fc305aaf82b26d3175a69ee02aa4bc9376ce820f9f6217bd243e13b54e49dcfc":
        raise AssertionError("HISTORY_MAPPING_WHOLE_E4_PREIMAGE")
    return original


PRIMARY = (ROOT / "scripts/run-hosted-initial-recipient.py").read_bytes()
if hashlib.sha256(history_source_preimage(PRIMARY)).hexdigest() != "fc305aaf82b26d3175a69ee02aa4bc9376ce820f9f6217bd243e13b54e49dcfc":
    raise AssertionError("UNCHANGED_HISTORY_SUPPLIER")
ACTIVE = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn",
            "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv", "os.kill", "os.killpg") or \
            ACTIVE and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        raise AssertionError("GUARD_CONTROL_REAL_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)


# Invert only the later reviewed cleanup-role layer; preserve all older suppliers.
_RETIREMENT_BASE_SHA256 = '9deae813fa1b7c4a853935ddb3e769692c8c6b80d7397a8f0ce20691c3eca8a7'
_RETIREMENT_INVERSES = [(b'    clock = parent.clock\n    retirement_role = clock.clock.role  # Original admitted role; cleanup must not reacquire a failed clock view.\n    inputs = _input_values(parent)\n', b'    clock = parent.clock\n    inputs = _input_values(parent)\n'), (b'native.preparer_identity(scope, retirement_role) ==\n                        row["preparerIdentity"], "NATIVE_DRAIN_IDENTITY")', b'native.preparer_identity(scope, clock.clock.role) ==\n                        row["preparerIdentity"], "NATIVE_DRAIN_IDENTITY")')]


# Exact selected-fatal-catch diagnostic inverse; all historical supplier pins remain unchanged.
_SELECTED_FAILURE_BASELINES = {'hosted_initial_recipient_before.py': '47a2a51ff38f101704111152dcb8ea1c53e2f768bdb2230ff45a4770ef903fa0', 'run-hosted-initial-recipient-tail.py': 'ea13cc5fae9c1d23eeb60a563d21e5eb3aa2becff283dca684828193d46512be'}
_SELECTED_FAILURE_DELTAS = {'hosted_initial_recipient_before.py': [(b'def _tail_failure_clear():\n', b'def _tail_child_selected_failure(error, stage):\n    """Snapshot one fatal catch\'s chosen error before its following cleanup."""\n    try:\n        state = _TAIL_FAILURE\n        if type(state) is not dict or type(state.get("operation")) is not str or \\\n                type(state.get("kind")) is not str or state.get("operation") != "_tail-child" or \\\n                state.get("kind") != "UNAVAILABLE" or "childPreCleanup" in state or \\\n                type(stage) is not str or stage not in ("CHILD_ENTRY", "CHILD_WORK"):\n            return\n        state["childPreCleanup"] = None  # First attempt wins even if observation fails.\n        if not isinstance(error, BaseException):\n            return\n        sites, truncated = _tail_failure_sites(BaseException.__traceback__.__get__(error))\n        value = {"schema": 1, "scope": "INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",\n            "operation": "_tail-child", "kind": "UNAVAILABLE", "stage": stage,\n            "origin": "PRE_CLEANUP_SELECTED", "sites": sites, "truncated": truncated}\n        line = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)\n        state["childPreCleanup"] = _tail_child_failure_projection(\n            b"INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\\n" + line.encode("ascii") + b"\\n")\n    except BaseException:\n        pass  # Optional DATA cannot alter the selected error or following cleanup.\n\n\ndef _tail_child_selected_failure_line():\n    """Validate saved DATA before the existing final-catch path consumes state."""\n    try:\n        state = _TAIL_FAILURE\n        if type(state) is not dict or type(state.get("operation")) is not str or \\\n                type(state.get("kind")) is not str or state.get("operation") != "_tail-child" or \\\n                state.get("kind") != "UNAVAILABLE":\n            return None\n        line = state.get("childPreCleanup")\n        if type(line) is not str or not 0 < len(line) <= 2048:\n            return None\n        value = _tail_child_failure_projection(\n            b"INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\\n" + line.encode("ascii") + b"\\n")\n        if value is not None and json.loads(value)["origin"] == "PRE_CLEANUP_SELECTED":\n            return value\n    except BaseException:\n        pass\n    return None\n\n\ndef _tail_failure_clear():\n'), (b'value["origin"] not in ("FIRST_FAILURE", "FINAL_CATCH")', b'value["origin"] not in ("FIRST_FAILURE", "FINAL_CATCH", "PRE_CLEANUP_SELECTED")')], 'run-hosted-initial-recipient-tail.py': [(b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n    finally:\n', b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n        try:\n            B._tail_child_selected_failure(failure, "CHILD_WORK")\n        except BaseException:\n            pass  # Snapshot failure cannot change the chosen error or cleanup.\n    finally:\n'), (b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n    finally:\n', b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n        try:\n            B._tail_child_selected_failure(failure, "CHILD_ENTRY")\n        except BaseException:\n            pass  # Snapshot failure cannot change the chosen error or cleanup.\n    finally:\n'), (b'        diagnostic = None\n        try:\n            B._tail_failure_remember(error, origin="FINAL_CATCH")\n', b'        diagnostic = selected = None\n        try:\n            if args.operation == "_tail-child":\n                selected = B._tail_child_selected_failure_line()\n        except BaseException:\n            pass  # Retrieval cannot alter the final exception or exit125.\n        try:\n            B._tail_failure_remember(error, origin="FINAL_CATCH")\n'), (b'        except BaseException:\n            pass  # An unavailable memo cannot prevent separate actual-catch DATA.\n        try:\n            if diagnostic is None:\n', b'        except BaseException:\n            pass  # An unavailable memo cannot prevent separate actual-catch DATA.\n        try:\n            if selected is not None and (diagnostic is None or diagnostic["origin"] != "FIRST_FAILURE"):\n                diagnostic = json.loads(selected)\n        except BaseException:\n            pass  # Keep the existing final-catch fallback when selected DATA fails.\n        try:\n            if diagnostic is None:\n')]}


def selected_failure_preimage(name, raw):
    name = name.removeprefix("scripts/")
    if name not in _SELECTED_FAILURE_BASELINES:
        return raw
    if type(raw) is not bytes:
        raise AssertionError("SELECTED_FAILURE_SOURCE_BYTES")
    if hashlib.sha256(raw).hexdigest() == _SELECTED_FAILURE_BASELINES[name]:
        return raw  # An exact original supplied by another inverse is not a new layer.
    for before, after in reversed(_SELECTED_FAILURE_DELTAS[name]):
        if raw.count(after) != 1:
            raise AssertionError("SELECTED_FAILURE_EXACT_CONTEXT")
        raw = raw.replace(after, before, 1)
    if hashlib.sha256(raw).hexdigest() != _SELECTED_FAILURE_BASELINES[name]:
        raise AssertionError("SELECTED_FAILURE_WHOLE_3CEA_PREIMAGE")
    return raw




# Exact owner-authorized operational layer; no historical supplier hash changes.
_OPERATIONAL_BASELINES = {'run-hosted-initial-recipient-custody.py': '54f9549629fd8ea5eea8ae4df4a66aed1bd8a3ff230ab817b45bb60dc1348093', 'run-hosted-initial-recipient-tail.py': '82fdd2a179c57728e1a204f04aaffae26bcb2035e788156ab027cffa1fe7e6d2'}
_OPERATIONAL_DELTAS = {'run-hosted-initial-recipient-custody.py': [(b'basis + 600 * O.NS', b'basis + 1200 * O.NS', 1)], 'run-hosted-initial-recipient-tail.py': [(b'started + 210 * NS', b'started + 600 * NS', 3), (b'Separate token-free K210 subcap', b'Separate token-free K600 subcap', 1)]}

# Exact bounded-idle scheduling inverse; original962a and older suppliers stay pinned.
_PARENT_IDLE_BASE_SHA256 = 'dd6eafd5f1bd0490463912800f7e68e3b5e1d4d16c7141179c3570b957dbde60'
_PARENT_IDLE_BEFORE = b'                scope.discover()\n                native.time.sleep(.025)\n'
_PARENT_IDLE_AFTER = b'                scope.discover()\n                wait_end = clock.deadline(.5, limit=caps[1])\n                native.time.sleep(max(0, min(.5, wait_end - native.time.monotonic())))\n'


def parent_idle_preimage(name, raw):
    if name.removeprefix("scripts/") != "run-hosted-initial-recipient-tail.py":
        return raw
    if type(raw) is not bytes:
        raise AssertionError("PARENT_IDLE_BYTES")
    raw = capacity_preimage(name, raw)
    if raw.count(_PARENT_IDLE_AFTER) != 1 or _PARENT_IDLE_BEFORE in raw:
        raise AssertionError("PARENT_IDLE_EXACT_CONTEXT")
    original = raw.replace(_PARENT_IDLE_AFTER, _PARENT_IDLE_BEFORE, 1)
    if hashlib.sha256(original).hexdigest() != _PARENT_IDLE_BASE_SHA256:
        raise AssertionError("PARENT_IDLE_WHOLE_962A_PREIMAGE")
    return original




# Exact final capacity layer restores416 source before every historical inverse.
_CAPACITY_BASELINES = {'run-hosted-initial-recipient-custody.py': '58f757b25c57f2c34e6d79748776e60d9ba5f71e76a0680219134f2a7f150e84', 'run-hosted-initial-recipient-tail.py': 'dfe41b926cb7cdb80f4626710904a46614507be64f714f0067512eb32e329ae5'}
_CAPACITY_DELTAS = {'run-hosted-initial-recipient-custody.py': [(b'basis + 1200 * O.NS', b'basis + 1800 * O.NS', 1), (b'0 < maximum <= 900, "BEFORE_MECHANISM_MAXIMUM")', b'0 < maximum <= (1245 if final is True else 900), "BEFORE_MECHANISM_MAXIMUM")', 1)], 'run-hosted-initial-recipient-tail.py': [(b'started + 600 * NS', b'started + 1200 * NS', 3), (b'Separate token-free K600 subcap', b'Separate token-free K1200 subcap', 1), (b'clock.deadline(900, final=True, limit=caps[2])', b'clock.deadline(1245, final=True, limit=caps[2])', 2)]}

# Exact owner-authorized headroom layer; preserve6f9 and every older whole supplier.
_HEADROOM_BASELINES = {'run-hosted-initial-recipient-custody.py': 'ce007ad8a64b02c1194d5b2db27495250364a93effea97bc48d807d9b0c1e13c', 'run-hosted-initial-recipient-tail.py': '73b2875b140765809a736cede4beeefca0c1dab3ab702b501017a4680b2e278d'}
_HEADROOM_DELTAS = {'run-hosted-initial-recipient-custody.py': [(b'basis + 1800 * O.NS', b'basis + 3600 * O.NS', 1), (b'(1245 if final is True else 900)', b'(2445 if final is True else 900)', 1)], 'run-hosted-initial-recipient-tail.py': [(b'started + 1200 * NS', b'started + 2400 * NS', 3), (b'Separate token-free K1200 subcap', b'Separate token-free K2400 subcap', 1), (b'clock.deadline(1245, final=True, limit=caps[2])', b'clock.deadline(2445, final=True, limit=caps[2])', 2)]}


def headroom_preimage(name, raw):
    name = name.removeprefix("scripts/")
    if name not in _HEADROOM_BASELINES:
        return raw
    if type(raw) is not bytes:
        raise AssertionError("OPERATIONAL_CAPACITY_HEADROOM_BYTES")
    if hashlib.sha256(raw).hexdigest() == _HEADROOM_BASELINES[name]:
        return raw  # Exact6f9 input can already have been normalized by another consumer.
    for before, after, count in reversed(_HEADROOM_DELTAS[name]):
        if raw.count(after) != count:
            raise AssertionError("OPERATIONAL_CAPACITY_HEADROOM_EXACT_CONTEXT")
        raw = raw.replace(after, before)
    if hashlib.sha256(raw).hexdigest() != _HEADROOM_BASELINES[name]:
        raise AssertionError("OPERATIONAL_CAPACITY_HEADROOM_WHOLE_6F9_PREIMAGE")
    return raw


def capacity_preimage(name, raw):
    name = name.removeprefix("scripts/")
    if name not in _CAPACITY_BASELINES:
        return raw
    if type(raw) is not bytes:
        raise AssertionError("OPERATIONAL_CAPACITY_BYTES")
    if hashlib.sha256(raw).hexdigest() == _CAPACITY_BASELINES[name]:
        return raw  # Exact416 input can already have been normalized by another consumer.
    raw = headroom_preimage(name, raw)
    for before, after, count in reversed(_CAPACITY_DELTAS[name]):
        if raw.count(after) != count:
            raise AssertionError("OPERATIONAL_CAPACITY_EXACT_CONTEXT")
        raw = raw.replace(after, before)
    if hashlib.sha256(raw).hexdigest() != _CAPACITY_BASELINES[name]:
        raise AssertionError("OPERATIONAL_CAPACITY_WHOLE_416_PREIMAGE")
    return raw

def operational_budget_preimage(name, raw):
    name = name.removeprefix("scripts/")
    if name not in _OPERATIONAL_BASELINES:
        return raw
    if type(raw) is not bytes:
        raise AssertionError("OPERATIONAL_BYTES")
    if name == "run-hosted-initial-recipient-custody.py":
        raw = capacity_preimage(name, raw)
    raw = parent_idle_preimage(name, raw)
    for before, after, count in reversed(_OPERATIONAL_DELTAS[name]):
        if raw.count(after) != count or before in raw:
            raise AssertionError("OPERATIONAL_EXACT_CONTEXT")
        raw = raw.replace(after, before)
    if hashlib.sha256(raw).hexdigest() != _OPERATIONAL_BASELINES[name]:
        raise AssertionError("OPERATIONAL_WHOLE_FBC1_PREIMAGE")
    return raw

def retirement_preimage(name, raw):
    raw = operational_budget_preimage(name, raw)
    raw = selected_failure_preimage(name, raw)
    if name != "run-hosted-initial-recipient-tail.py":
        return raw
    if type(raw) is not bytes:
        raise AssertionError("RETIREMENT_SOURCE_BYTES")
    for after, before in reversed(_RETIREMENT_INVERSES):
        if raw.count(after) != 1:
            raise AssertionError("RETIREMENT_EXACT_CONTEXT")
        raw = raw.replace(after, before, 1)
    if hashlib.sha256(raw).hexdigest() != _RETIREMENT_BASE_SHA256:
        raise AssertionError("RETIREMENT_WHOLE_86B_PREIMAGE")
    return raw


def preimage(name, raw):
    if type(raw) is not bytes:
        raise AssertionError("GUARD_SOURCE_BYTES")
    raw = retirement_preimage(name, raw)
    for before, after in reversed(DELTAS[name]):
        if raw.count(after) != 1:
            raise AssertionError("GUARD_EXACT_CONTEXT")
        raw = raw.replace(after, before, 1)
    if hashlib.sha256(raw).hexdigest() != BASELINES[name]:
        raise AssertionError("GUARD_WHOLE_E050_PREIMAGE")
    return raw


BASE = {name: preimage(name, raw) for name, raw in SOURCES.items()}


def selected(raw, names):
    nodes = [node for node in ast.parse(raw).body
             if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names]
    if {node.name for node in nodes} != set(names):
        raise AssertionError("EXACT_AST_SELECTION")
    return compile(ast.Module(body=nodes, type_ignores=[]), "<exact-public-guard-functions>", "exec",
                   flags=__future__.annotations.compiler_flag, dont_inherit=True)


DIRECTED_SOURCE = (ROOT / "scripts/hosted_full_job_budget.py").read_bytes()
if hashlib.sha256(DIRECTED_SOURCE).hexdigest() != "95fb79e994746e85439446d39a49017fefa782d2b7182523db4ad1f2b071b1a3":
    raise AssertionError("CAPACITY_UNCHANGED_DIRECTED_SUPPLIER")
DIRECTED_CODE = selected(DIRECTED_SOURCE, ("_directed_deadline",))


CODES = {}
for variant, sources in (("old", BASE), ("new", SOURCES)):
    CODES[variant] = (
        selected(PRIMARY, ("_check_history",)),
        selected(sources["run-hosted-initial-recipient-custody.py"],
                 ("_PrimaryOwnerAnchor", "_PrimaryOwner", "_BeforeClockAnchor", "_BeforeClock", "local_value")),
        selected(sources["run-hosted-initial-recipient-tail.py"],
                 ("_ChildAnchor", "_ChildClock", "_CaptureAnchor", "_Capture")),
    )


class Refusal(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise Refusal(reason)


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= (1 << 64) - 1, "MODEL_INTEGER")
    return value


def graph(value):
    # Exact mutable mapping pins consumed by the real _check_history function.
    return ((value, dict, "mapping", tuple(value.items())),)


class NativeOwnerModel:
    """Declared in-memory fields only, NOT a production native Owner."""
    def error(self, _stage, error, *, unknown=False):
        if self.original is None:
            self.original = error
        self.unknown |= unknown
        self.errors.append(error)


class EntryModel:
    def __init__(self):
        self.failure = None

    def fail(self, error):
        if self.failure is None:
            self.failure = error
        return self.failure


class Rig:
    """Real guard code with finite synthetic samples and owner/recipient seams."""
    def __init__(self, variant="new", kind="child", parent=False):
        self.events, self.counts, self.hooks = [], Counter(), {}
        self.local_values, self.raw_values = [2.0, 3.0, 4.0], [20, 21]
        self.boot_values = ["boot", "boot"]
        self.entry = EntryModel()
        space = {"__name__": __name__, "dataclass": dataclass, "require": require, "math": math,
                 "MAX_MEMBERS": 2000, "_PRIMARY_OWNERS": {}, "_PRIMARY_QUARANTINE": [],
                 "_BEFORE_CLOCKS": {}, "_CHILD_CLOCKS": {}, "_CAPTURES": {}}
        history = {"require": require}
        exec(CODES[variant][0], history)
        space["N"] = NS(_check_history=history["_check_history"])
        space["B"] = NS(_tail_failure_remember=lambda *_: None)
        space["native"] = NS(Owner=NativeOwnerModel, QUARANTINE=[],
                             diagnostics=NS(_QUARANTINE=[]), _custody_progress_failure=lambda *_: None)
        space["Q"] = NS(QUARANTINE=[])
        space["T"] = NS(CREDENTIAL_NAMES=(), windows=NS(_QUARANTINE=[]),
                         original=NS(_recipient_current=lambda _pin: self.event("recipient")))
        space["os"] = NS(environ={})
        space["time"] = NS(monotonic=self.local)
        space["O"] = NS(integer=integer, clocks=NS(checked_now=self.raw))
        space["continuity"] = NS(QUARANTINE=[], boot_digest=self.boot)
        space["C"] = NS(QUARANTINE=[], boot_digest=self.boot)
        space["_CREDENTIAL_NAMES"] = ()
        space["_before_entry_current"] = lambda _entry: None
        space["_before_actual"] = lambda _actual: ((), {})
        space["_same"] = lambda a, b, reason: require(a == b, reason)
        space["_before_raw_failure_diagnostic"] = lambda *_: self.events.append("diagnostic")
        exec(CODES[variant][1], space)
        space["C"]._PrimaryOwner = space["_PrimaryOwner"]
        space["C"].local_value = space["local_value"]
        space["C"]._crypto_recipient_closed = lambda _pin: self.event("closed-recipient")
        exec(CODES[variant][2], space)
        self.ns, self.kind = space, kind
        clock_type = space["_BeforeClock" if kind == "before" else "_ChildClock"]
        self.clock = object.__new__(clock_type)
        first = NS(clock=NS(role="linux-x64"), nanoseconds=10)
        self.first = first
        if kind == "before":
            binding = (first, 1.0, "boot", self.cancel, "parent" if parent else "child", {}, (), None,
                       (100, 145, 10.0, 14.5), (self.entry, object()) if parent else None)
            anchor_type, registry = space["_BeforeClockAnchor"], space["_BEFORE_CLOCKS"]
        else:
            binding = (first, 1.0, "boot", self.cancel, {}, (10, 100, 145), 10.0, 14.5)
            anchor_type, registry = space["_ChildAnchor"], space["_CHILD_CLOCKS"]
        self.clock._binding = binding
        self.anchor = anchor_type(self.clock, binding, (), 10, 1.0)
        registry[id(self.clock)] = self.anchor
        self.metadata = self.owner("metadata")
        self.active_owner = self.owner("active")
        if kind == "before":
            self.anchor.metadata = self.metadata
            self.anchor.file_owners = (("readback", self.active_owner, self.active_owner._anchor()),)
        else:
            self.anchor.owners = ((self.metadata, self.metadata._anchor()),
                                  (self.active_owner, self.active_owner._anchor()))
        method = "_current" if kind == "before" else "current"
        original = getattr(clock_type, method)
        def current(handle, *args, **kwargs):
            self.counts["current"] += 1
            return original(handle, *args, **kwargs)
        setattr(clock_type, method, current)  # Observation only: actual body is unchanged.
        original_structural = space["_PrimaryOwner"].structural
        def structural(handle):
            self.counts["structural:" + self.owner_names[id(handle)]] += 1
            return original_structural(handle)
        space["_PrimaryOwner"].structural = structural

    def owner(self, name):
        if not hasattr(self, "owner_names"):
            self.owner_names, self.owner_states = {}, {}
        native = NativeOwnerModel()
        native.first, native.fence, native.cancelled = self.first, self.clock, self.cancel
        native.local_end, native.work_limit, native.final_limit = 14.5, None, None
        native.closed, native.unknown, native.original = False, False, None
        resource = object()
        row = {"label": "reader", "owner": resource, "attempted": True, "closed": True}
        native.resources, native.errors = [row], []
        original_row = (row, "reader", resource, True, True)
        snapshot = {"original": name}
        owner = object.__new__(self.ns["_PrimaryOwner"])
        binding = (native, native.__dict__, native.resources, native.errors,
                   (native.first, native.fence, native.cancelled, native.local_end, None, None),
                   (), [original_row], [resource], [snapshot])
        owner._bound = binding
        anchor = self.ns["_PrimaryOwnerAnchor"](owner, binding, rows=(original_row,), returned=(resource,),
                                                 snapshots=((snapshot, graph(snapshot)),))
        self.ns["_PRIMARY_OWNERS"][id(owner)] = anchor
        self.owner_names[id(owner)] = name
        self.owner_states[name] = NS(native=native, row=row, snapshot=snapshot, anchor=anchor)
        return owner

    def event(self, name):
        self.events.append(name)
        hook = self.hooks.get(name)
        if hook is not None:
            hook()

    def local(self):
        self.counts["local"] += 1
        number = self.counts["local"]
        self.event("local" + str(number))
        return self.local_values[number - 1]

    def raw(self, clock, *, minimum_ns):
        require(clock is self.first.clock, "MODEL_ORIGINAL_RAW_CLOCK")
        self.counts["raw"] += 1
        number = self.counts["raw"]
        self.event("raw" + str(number))
        return integer(self.raw_values[number - 1], minimum_ns)

    def boot(self, role):
        require(role == "linux-x64", "MODEL_BOOT_ROLE")
        self.counts["boot"] += 1
        number = self.counts["boot"]
        self.event("boot" + str(number))
        return self.boot_values[number - 1]

    def cancel(self):
        self.event("cancel")

    def now(self, **kwargs):
        return self.clock.now(**kwargs)

    def capture(self):
        require(self.kind == "child", "MODEL_CAPTURE_CHILD_ONLY")
        work = NS(path=Path("/SYNTHETIC/work"), identity=(1, 2))
        destination = NS(path=Path("/SYNTHETIC/destination"), identity=(3, 4))
        context = {"kind": "gate", "directories": {"tail-public-crypto": (1, 2),
                                                   "tail-copied-evidence": (3, 4)}}
        paths = {"tail-public-crypto": work.path, "tail-copied-evidence": destination.path}
        self.ns["_paths"] = lambda _kind: paths
        capture = object.__new__(self.ns["_Capture"])
        binding = (self.clock, self.active_owner, b"context", b"start", {}, object(), work, destination, None, context)
        capture._binding = binding
        anchor = self.ns["_CaptureAnchor"](capture, binding, ())
        self.ns["_CAPTURES"][id(capture)] = anchor
        self.capture_handle, self.capture_anchor = capture, anchor
        self.work, self.destination = work, destination
        return capture


class GuardSchedulingControls(unittest.TestCase):
    def test_history_mapping_layer_preserves_exact_old_supplier_and_current_checker(self):
        original = history_source_preimage(PRIMARY)
        self.assertNotEqual(original, PRIMARY)
        self.assertIn(_HISTORY_MAPPING_AFTER, PRIMARY)
        for changed in (original, PRIMARY + b"\n", PRIMARY + _HISTORY_MAPPING_AFTER,
                        PRIMARY.replace(_HISTORY_MAPPING_AFTER, b"", 1),
                        PRIMARY.replace(b"key is old_key", b"key == old_key", 1)):
            with self.subTest(bytes=len(changed)):
                with self.assertRaises(AssertionError):
                    history_source_preimage(changed)

    def setUp(self):
        global ACTIVE
        ACTIVE = True

    def tearDown(self):
        global ACTIVE
        ACTIVE = False

    def raised(self, function, expected=Refusal):
        with self.assertRaises(expected) as caught:
            function()
        return caught.exception

    def compare_failure(self, kind, setup, *, kwargs=None, expected=Refusal):
        outcomes = []
        for variant in ("old", "new"):
            rig = Rig(variant, kind)
            setup(rig)
            error = self.raised(lambda: rig.now(**(kwargs or {})), expected)
            outcomes.append((type(error), str(error), rig.events))
            self.assertIs(rig.anchor.failure, error)
            self.assertIs(rig.anchor.busy, False)
            self.assertIs(self.raised(rig.now, type(error)), error)
        self.assertEqual(outcomes[0], outcomes[1])

    def test_only_three_function_asts_change(self):
        for name in SOURCES:
            def nodes(raw):
                tree = ast.parse(raw)
                return {(node.name, child.name): ast.dump(child, include_attributes=False)
                        for node in tree.body if isinstance(node, ast.ClassDef)
                        for child in node.body if isinstance(child, ast.FunctionDef)}
            before, after = nodes(BASE[name]), nodes(retirement_preimage(name, SOURCES[name]))
            self.assertEqual(before.keys(), after.keys())
            expected = {("_BeforeClock", "_observe")} if "custody" in name else {
                ("_ChildClock", "_observe"), ("_Capture", "current")}
            self.assertEqual({key for key in before if before[key] != after[key]}, expected)

    def test_complete_inverse_rejects_missing_duplicate_moved_partial_and_outside_edits(self):
        for name, raw in SOURCES.items():
            self.assertEqual(hashlib.sha256(preimage(name, raw)).hexdigest(), BASELINES[name])
            for before, after in DELTAS[name]:
                removed = raw.replace(after, b"", 1)
                for bad in (removed, raw.replace(after, after * 2, 1), removed + after,
                            raw.replace(after, before, 1), raw + b"\n"):
                    self.raised(lambda: preimage(name, bad), AssertionError)
            if name == "run-hosted-initial-recipient-tail.py":
                for after, before in _RETIREMENT_INVERSES:
                    removed = raw.replace(after, b"", 1)
                    for bad in (removed, raw.replace(after, after * 2, 1), removed + after,
                                raw.replace(after, before, 1), raw + b"\n"):
                        self.raised(lambda: preimage(name, bad), AssertionError)

    def test_normal_observations_keep_callbacks_and_reduce_only_one_current(self):
        for kind in ("before", "child"):
            for final in (False, True):
                for parent in (False, True) if kind == "before" else (False,):
                    results = []
                    for variant, count in (("old", 10), ("new", 9)):
                        rig = Rig(variant, kind, parent)
                        results.append((rig.now(final=final), rig.events))
                        self.assertEqual(rig.counts["current"], count)
                        self.assertEqual(rig.counts["structural:metadata"], count)
                        self.assertEqual(rig.counts["structural:active"], count)
                    self.assertEqual(results[0], results[1])
                    self.assertEqual(results[0], (21, ["local1", "raw1", "boot1", "cancel",
                                                      "local2", "raw2", "boot2", "local3"]))

    def test_original_raw_work_final_and_clipped_endpoints_remain_strict(self):
        for kind in ("before", "child"):
            for final, limit, end in ((False, None, 100), (True, None, 145), (False, 80, 80),
                                      (True, 80, 80), (False, 200, 100)):
                for value in (end - 1, end, end + 1):
                    outcomes = []
                    for variant in ("old", "new"):
                        rig = Rig(variant, kind)
                        rig.raw_values = [value, value]
                        if value < end:
                            outcomes.append(rig.now(final=final, limit=limit))
                        else:
                            outcomes.append(str(self.raised(lambda: rig.now(final=final, limit=limit))))
                    self.assertEqual(outcomes[0], outcomes[1])

    def test_local_backwards_equal_late_and_failure_at_each_sample(self):
        for kind in ("before", "child"):
            for index in range(3):
                for value in (0.5, 10.0, 10.1):
                    self.compare_failure(kind, lambda r, i=index, v=value: r.local_values.__setitem__(i, v))
                def fail(r, i=index):
                    def action():
                        raise OSError("synthetic-local")
                    r.hooks["local" + str(i + 1)] = action
                self.compare_failure(kind, fail, expected=OSError)
            for variant in ("old", "new"):
                rig = Rig(variant, kind)
                rig.local_values = [1.0, 1.0, 1.0]
                self.assertEqual(rig.now(), 21)  # Nondecreasing, not strictly increasing.

    def test_raw_backwards_late_and_callback_failure_at_both_samples(self):
        for kind in ("before", "child"):
            for index in range(2):
                for value in (9, 100, 101):
                    self.compare_failure(kind, lambda r, i=index, v=value: r.raw_values.__setitem__(i, v))
                def fail(r, i=index):
                    def action():
                        raise OSError("synthetic-raw")
                    r.hooks["raw" + str(i + 1)] = action
                self.compare_failure(kind, fail, expected=OSError)

    def test_boot_change_failure_and_state_mutation_at_both_callbacks(self):
        for kind in ("before", "child"):
            for index in range(2):
                self.compare_failure(kind, lambda r, i=index: r.boot_values.__setitem__(i, "changed"))
                def setup(r, i=index):
                    r.hooks["boot" + str(i + 1)] = lambda: r.owner_states["active"].row.__setitem__("closed", False)
                self.compare_failure(kind, setup)
                def fail(r, i=index):
                    def action():
                        raise OSError("synthetic-boot")
                    r.hooks["boot" + str(i + 1)] = action
                self.compare_failure(kind, fail, expected=OSError)

    def test_cancellation_failure_and_mutation_keep_immediate_guard(self):
        mutations = (
            lambda r: setattr(r.anchor, "busy", False),
            lambda r: setattr(r.anchor, "last", 19),
            lambda r: setattr(r.anchor, "local_last", 1.5),
            lambda r: r.owner_states["active"].row.__setitem__("closed", False),
            lambda r: r.owner_states["metadata"].snapshot.__setitem__("original", "changed"),
        )
        for kind in ("before", "child"):
            for mutation in mutations:
                self.compare_failure(kind, lambda r, m=mutation: r.hooks.__setitem__("cancel", lambda: m(r)))
            def setup(r):
                def fail():
                    raise KeyboardInterrupt("synthetic-cancel")
                r.hooks["cancel"] = fail
            self.compare_failure(kind, setup, expected=KeyboardInterrupt)

    def test_reentry_and_falsey_first_failure_remain_sticky(self):
        class Falsey(Refusal):
            def __bool__(self):
                raise AssertionError("must not ask exception truth")
        for kind in ("before", "child"):
            for variant in ("old", "new"):
                rig = Rig(variant, kind)
                rig.hooks["cancel"] = rig.now
                error = self.raised(rig.now)
                self.assertIs(rig.anchor.failure, error)
                self.assertIs(self.raised(rig.now), error)
                rig = Rig(variant, kind)
                original = Falsey("synthetic-first")
                def fail():
                    raise original
                rig.hooks["cancel"] = fail
                self.assertIs(self.raised(rig.now, Falsey), original)
                self.assertIs(self.raised(rig.now, Falsey), original)

    def test_final_local_mutation_is_caught_by_retained_local_current(self):
        for kind in ("before", "child"):
            for owner in ("metadata", "active"):
                def setup(r, selected=owner):
                    r.hooks["local3"] = lambda: r.owner_states[selected].snapshot.__setitem__("original", "changed")
                self.compare_failure(kind, setup)

    def test_capture_exact_owner_is_scanned_once_and_metadata_still_scanned(self):
        for recipient in (False, True):
            outcomes = []
            for variant, scans in (("old", 2), ("new", 1)):
                rig = Rig(variant)
                capture = rig.capture()
                self.assertIs(capture.current(recipient=recipient), rig.capture_anchor)
                self.assertEqual(rig.counts["structural:active"], scans)
                self.assertEqual(rig.counts["structural:metadata"], 1)
                outcomes.append(rig.events)
            self.assertEqual(outcomes[0], outcomes[1])

    def test_capture_forged_clock_owner_anchor_or_roster_refuses(self):
        # Mutate both callback-facing and private binding slots: constructor checks alone are insufficient.
        for role in ("clock", "owner"):
            rig = Rig()
            capture = rig.capture()
            touched = []
            forged = NS(current=lambda: touched.append("forged"), remember=lambda e: e)
            binding = list(rig.capture_anchor.binding)
            binding[0 if role == "clock" else 1] = forged
            capture._binding = rig.capture_anchor.binding = tuple(binding)
            self.raised(capture.current)
            self.assertEqual(touched, [])
        for mutation in ("absent", "other", "wrong-anchor", "registry", "non-tuple-roster", "non-tuple-pair"):
            rig = Rig()
            capture = rig.capture()
            owner, anchor = rig.active_owner, rig.active_owner._anchor()
            if mutation == "absent":
                rig.anchor.owners = ((rig.metadata, rig.metadata._anchor()),)
            elif mutation == "other":
                rig.anchor.owners = ((rig.metadata, rig.metadata._anchor()), (rig.metadata, rig.metadata._anchor()))
            elif mutation == "wrong-anchor":
                rig.anchor.owners = ((owner, object()),)
            elif mutation == "registry":
                rig.ns["_PRIMARY_OWNERS"][id(owner)] = rig.metadata._anchor()
            elif mutation == "non-tuple-roster":
                rig.anchor.owners = [(owner, anchor)]
            else:
                rig.anchor.owners = ([owner, anchor],)
            self.raised(capture.current)
            self.assertNotIn("recipient", rig.events)

        # Deliberately invalid return seams exercise the defensive join; they are
        # NOT admitted clock callbacks and never replace an actual successful guard.
        class Hostile:
            def __iter__(self):
                raise AssertionError("custom roster iteration")
            def __eq__(self, other):
                raise AssertionError("custom equality")
        for change in ("return-type", "handle", "clock-registry", "hostile-roster", "hostile-pair", "equal-anchor"):
            rig = Rig()
            capture = rig.capture()
            clock_type = rig.ns["_ChildClock"]
            actual_current = clock_type.current
            def invalid_return(handle, which=change):
                anchor = actual_current(handle)
                if which == "return-type":
                    return NS(owners=Hostile())
                if which == "handle":
                    anchor.handle = object()
                elif which == "clock-registry":
                    rig.ns["_CHILD_CLOCKS"][id(handle)] = object()
                elif which == "hostile-roster":
                    anchor.owners = Hostile()
                elif which == "hostile-pair":
                    anchor.owners = (Hostile(),)
                else:
                    anchor.owners = ((rig.active_owner, Hostile()),)
                return anchor
            clock_type.current = invalid_return
            self.raised(capture.current)
            self.assertNotIn("recipient", rig.events)

    def test_capture_original_metadata_and_active_mutations_still_refuse(self):
        for variant in ("old", "new"):
            for name in ("metadata", "active"):
                for mutation in ("ledger", "snapshot", "binding", "failure"):
                    rig = Rig(variant)
                    capture = rig.capture()
                    state = rig.owner_states[name]
                    if mutation == "ledger":
                        state.row["closed"] = False
                    elif mutation == "snapshot":
                        state.snapshot["original"] = "changed"
                    elif mutation == "binding":
                        state.native.resources = []
                    else:
                        state.anchor.failure = Refusal("synthetic-original-owner")
                    self.raised(capture.current)
                    self.assertNotIn("recipient", rig.events)

    def test_capture_structural_failure_is_sticky_and_poisoned_original_owner(self):
        for variant in ("old", "new"):
            rig = Rig(variant)
            capture = rig.capture()
            rig.owner_states["active"].row["closed"] = False
            original = self.raised(capture.current)
            self.assertIs(self.raised(capture.current), original)
            self.assertIs(rig.capture_anchor.failure, original)
            self.assertIs(rig.active_owner.failure, original)
            self.assertIs(rig.owner_states["active"].native.original, original)

    def test_recipient_failures_and_existing_next_guard_boundaries_match(self):
        for action in ("raise", "root", "owner"):
            outcomes = []
            for variant in ("old", "new"):
                rig = Rig(variant)
                capture = rig.capture()
                if action == "raise":
                    def fail():
                        raise OSError("synthetic-recipient")
                    rig.hooks["recipient"] = fail
                    result = str(self.raised(capture.current, OSError))
                elif action == "root":
                    rig.hooks["recipient"] = lambda: setattr(rig.work, "identity", (7, 8))
                    result = str(self.raised(capture.current))
                else:
                    rig.hooks["recipient"] = lambda: rig.owner_states["active"].row.__setitem__("closed", False)
                    self.assertIs(capture.current(), rig.capture_anchor)
                    # Existing code checks this mutation at the next original current boundary.
                    result = str(self.raised(capture.current))
                outcomes.append((result, rig.events))
            self.assertEqual(outcomes[0], outcomes[1])

    def capacity_clock(self, *, raw_work=3000_000_000_000, raw_final=3045_000_000_000,
                       local_work=3000.0, local_final=3045.0):
        # Actual current BeforeClock/deadline/observe/current plus existing finite owner seams.
        rig = Rig("new", "before")
        binding = list(rig.clock._binding)
        binding[8] = (raw_work, raw_final, local_work, local_final)
        rig.clock._binding = rig.anchor.binding = tuple(binding)
        rig.local_values = [2.0, 3.0, 4.0, 5.0]
        direct = {"math": math, "NS": 1_000_000_000, "require": require}
        exec(DIRECTED_CODE, direct)
        rig.ns["O"].wire = NS(_directed_deadline=direct["_directed_deadline"])
        return rig

    def test_capacity_final_only_ceiling_and_existing_900_are_actual(self):
        for maximum, final in ((900, False), (900, True), (1245, True), (2445, True)):
            rig = self.capacity_clock()
            native_ends = [rig.owner_states[name].native.local_end for name in ("active", "metadata")]
            result = rig.clock.deadline(maximum, final=final)
            self.assertEqual(result, math.nextafter(2.0 + maximum, -math.inf))
            self.assertEqual((rig.counts["raw"], rig.counts["boot"], rig.counts["local"]), (2, 2, 4))
            self.assertIn("cancel", rig.events)
            self.assertIsNone(rig.anchor.failure)
            self.assertIs(rig.anchor.busy, False)
            self.assertEqual(native_ends, [rig.owner_states[name].native.local_end for name in ("active", "metadata")])
        for maximum, final in ((1245, False), (2445, False), (math.nextafter(2445.0, math.inf), True),
                               (math.nextafter(900.0, math.inf), False)):
            rig = self.capacity_clock()
            error = self.raised(lambda: rig.clock.deadline(maximum, final=final))
            self.assertEqual(str(error), "BEFORE_MECHANISM_MAXIMUM")
            self.assertEqual(rig.events, [])
            self.assertIs(rig.anchor.failure, error)
            self.assertIs(self.raised(lambda: rig.clock.deadline(1)), error)

    def test_capacity_final_type_refuses_without_truthiness_or_samples(self):
        class Hostile:
            def __bool__(self):
                raise AssertionError("final truthiness must not run")
        for final in (Hostile(), 1, 0, None, "true"):
            rig = self.capacity_clock()
            error = self.raised(lambda: rig.clock.deadline(2445, final=final))
            self.assertEqual(str(error), "BEFORE_MECHANISM_MAXIMUM")
            self.assertEqual(rig.events, [])
            self.assertIs(rig.anchor.busy, False)

    def test_capacity_original_residual_and_expiry_still_bound_final(self):
        for raw_end, local_end, limit in ((12_000_000_000, 2045.0, None),
                (2045_000_000_000, 7.0, None), (2045_000_000_000, 2045.0, 8_000_000_000)):
            rig = self.capacity_clock(raw_final=raw_end, local_final=local_end)
            result = rig.clock.deadline(2445, final=True, limit=limit)
            selected_end = raw_end if limit is None else min(raw_end, limit)
            expected = min(local_end, math.nextafter(2.0 + min(2445,
                math.nextafter((selected_end - 21) / 1_000_000_000, 0.0)), -math.inf))
            self.assertEqual(result, expected)
            self.assertLess(result, 2447)
        for kwargs, reason in (({"local_final": 2.0}, "BEFORE_LOCAL_EXPIRED"),
                ({"raw_final": 20}, "BEFORE_RAW_EXPIRED_OR_CHANGED")):
            rig = self.capacity_clock(**kwargs)
            error = self.raised(lambda: rig.clock.deadline(2445, final=True))
            self.assertEqual(str(error), reason)
            self.assertIs(rig.anchor.failure, error)
            self.assertIs(self.raised(lambda: rig.clock.deadline(2445, final=True)), error)

    def test_capacity_exact_layer_and_original_parent_container_calls(self):
        for name, raw in SOURCES.items():
            prior = headroom_preimage(name, raw)
            self.assertEqual(hashlib.sha256(prior).hexdigest(), _HEADROOM_BASELINES[name])
            self.assertEqual(headroom_preimage(name, prior), prior)
            for before, after, count in _HEADROOM_DELTAS[name]:
                self.assertEqual(raw.count(after), count)
                removed = raw.replace(after, b"", 1)
                for changed in (removed, raw.replace(after, after * 2, 1), removed + after,
                                raw.replace(after, before, 1), raw.replace(after, after + b" ", 1), raw + b"\n"):
                    self.assertNotEqual(changed, raw)
                    with self.assertRaisesRegex(AssertionError, "OPERATIONAL_CAPACITY_HEADROOM_"):
                        headroom_preimage(name, changed)
            original = capacity_preimage(name, raw)
            self.assertEqual(hashlib.sha256(original).hexdigest(), _CAPACITY_BASELINES[name])
            self.assertEqual(capacity_preimage(name, original), original)
            raw = prior  # The old capacity controls retain their original complete6f9 supplier.
            for before, after, count in _CAPACITY_DELTAS[name]:
                self.assertEqual(raw.count(after), count)
                removed = raw.replace(after, b"", 1)
                for changed in (removed, raw.replace(after, after * 2, 1), removed + after,
                                raw.replace(after, before, 1), raw.replace(after, after + b" ", 1), raw + b"\n"):
                    self.assertNotEqual(changed, raw)
                    with self.assertRaisesRegex(AssertionError, "OPERATIONAL_CAPACITY_"):
                        capacity_preimage(name, changed)
        tail = SOURCES["run-hosted-initial-recipient-tail.py"].decode()
        parent = next(node for node in ast.parse(tail).body
                      if isinstance(node, ast.FunctionDef) and node.name == "_native_tail")
        calls = [node for node in ast.walk(parent) if isinstance(node, ast.Call)
                 and ast.unparse(node.func) == "clock.deadline" and node.args
                 and isinstance(node.args[0], ast.Constant) and node.args[0].value == 2445]
        self.assertEqual(len(calls), 2)
        for call in calls:
            self.assertEqual({item.arg: ast.unparse(item.value) for item in call.keywords},
                             {"final": "True", "limit": "caps[2]"})
        self.assertIn("work == min(started + 2400 * NS, seal_end - 45 * NS)", tail)
        self.assertIn("final == work + 45 * NS <= seal_end", tail)
        self.assertIn("min(clock.local_end, clock.deadline(2445, final=True, limit=caps[2]))", tail)

    def test_poll_reader_caps_cleanup_and_callbacks_are_byte_exact(self):
        # Prove the new capacity-only layer before any historical normalization.
        for name, raw in SOURCES.items():
            raw = capacity_preimage(name, raw)  # The following controls concern the older operational layer.
            self.assertEqual(hashlib.sha256(operational_budget_preimage(name, raw)).hexdigest(),
                             _OPERATIONAL_BASELINES[name])
            for before, after, count in _OPERATIONAL_DELTAS[name]:
                removed = raw.replace(after, b"", 1)
                for changed in (removed, raw.replace(after, after * 2, 1), removed + after,
                                raw.replace(after, before, 1), raw.replace(after, after + b" ", 1), raw + b"\n"):
                    self.assertNotEqual(changed, raw)
                    with self.assertRaises(AssertionError):
                        operational_budget_preimage(name, changed)
        for name in SOURCES:
            normalized = retirement_preimage(name, SOURCES[name])
            original, candidate = ast.parse(BASE[name]), ast.parse(normalized)
            excluded = {"_BeforeClock", "_ChildClock", "_Capture"}
            # One byte-line split per source, not a repeated whole-file text scan.
            def declarations(raw, tree):
                lines = raw.splitlines(keepends=True)
                return {node.name: b"".join(lines[node.lineno - 1:node.end_lineno])
                        for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                        and node.name not in excluded}
            before = declarations(BASE[name], original)
            after = declarations(normalized, candidate)
            self.assertEqual(before, after)
        # This assertion describes the proven historical guard-scheduling supplier, not current idle cadence.
        tail = parent_idle_preimage("run-hosted-initial-recipient-tail.py",
                                   SOURCES["run-hosted-initial-recipient-tail.py"]).decode()
        self.assertIn("native.time.sleep(.025)", tail)
        self.assertIn("work == min(started + 600 * NS, seal_end - 45 * NS)", tail)
        self.assertIn("final == work + 45 * NS <= seal_end", tail)


if __name__ == "__main__":
    unittest.main(failfast=True)
