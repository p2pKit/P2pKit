#!/usr/bin/env python3
"""New K DATA/refusal and AST topology controls, NOT native/runtime tests.

No B/Recipient/Admission/native or file owner is manufactured as valid. Positive
cases exercise only supplied cap/process/stamp DATA. Unregistered handles must
fail before I/O. AST assertions inspect this exact runner's call sites; they do
not prove any call executed, any native retirement, actual copy/freeze/export,
the enclosing Step, provider custody or scheduling qualification. No previous
fixture or accepted suite is imported or rerun.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import ctypes
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import unittest
from types import SimpleNamespace, TracebackType
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("TAIL_RUNNER_CONTROL_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
PATH = SCRIPTS / "run-hosted-initial-recipient-tail.py"
SOURCE = PATH.read_text(encoding="utf-8")
if len(SOURCE.encode("utf-8")) > 256 * 1024:
    raise AssertionError("TAIL_RUNNER_SOURCE_CONTROL_BOUND")
TREE = ast.parse(SOURCE, filename=str(PATH))
SPEC = importlib.util.spec_from_file_location("_tail_runner_controls", PATH)
K = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = K
SPEC.loader.exec_module(K)


NS = 1_000_000_000
DOMAINS = {"linux-x64": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-x64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-arm64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "windows-x64": "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns"}
SEED_FIELDS = {"initialSealSha256", "initialSealEndNs", "initialSealClockRole", "initialSealClockDomain",
    "initialSealClockTicksPerSecond", "initialSealBootSha256"}
PRIVATE_INPUTS = {"before-index.json", "before-readback.json", "before-writer-close.json", "before-match.json",
    "original-match.json", "event.json", "candidate-policy.json", "recipient-public.asc", "p0-manifest.json",
    "seal-pending.json", "crypto-step-pending.json", "custody-return.json", "p0-context.json", "collect-close.json"}


def wire(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False) + "\n").encode("ascii")


def seed(role="linux-x64", *, end=500):
    return {"initialSealSha256": "1" * 64, "initialSealEndNs": str(end * NS), "initialSealClockRole": role,
        "initialSealClockDomain": DOMAINS[role], "initialSealClockTicksPerSecond": str(7_000_003 if role == "windows-x64" else NS),
        "initialSealBootSha256": "2" * 64}


def process(value=None):
    if value is None:
        value = {"schema": 1, "waitExitCode": 0, "retired": True, "interruption": None}
    return (json.dumps(value, sort_keys=True, allow_nan=False) + "\n").encode("ascii")


def guarded(function, *args, **kwargs):
    global GUARDED
    previous, GUARDED = GUARDED, True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = previous


def node(name, cls=None):
    parent = TREE if cls is None else next(item for item in TREE.body if isinstance(item, ast.ClassDef) and item.name == cls)
    return next(item for item in parent.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name)


def calls(parent, name):
    return sorted((item for item in ast.walk(parent) if isinstance(item, ast.Call) and ast.unparse(item.func) == name),
        key=lambda item: (item.lineno, item.col_offset))


def text_of(parent):
    return ast.get_source_segment(SOURCE, parent)




# Exact reviewed first-catch delta; comparison bytes only, never runtime suppliers.
_FIRST_CATCH_CUSTODY_INVERSES = ((b'        clock.now()\n    except BaseException as error:\n        failure = error\n        if owner '
  b'is not None:\n            owner.error("before-authority-child", error)\n            failure = owne'
  b'r._anchor().failure\n',
  b'        clock.now()\n    except BaseException as error:\n        failure = error\n        try:\n    '
  b'        B._before_child_failure_remember(error)\n        except BaseException:\n            pass  '
  b'# First-catch DATA cannot replace the original error or cleanup.\n        if owner is not None:\n '
  b'           owner.error("before-authority-child", error)\n            failure = owner._anchor().fa'
  b'ilure\n'),
 (b'                child.add_argument(flag, required=True, dest=field)\n    args = parser.parse_args'
  b'()\n    try:\n        if args.operation == "collect-export":\n            native._custody_progress_'
  b'clear()\n        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_by'
  b'tecode,\n',
  b'                child.add_argument(flag, required=True, dest=field)\n    args = parser.parse_args'
  b'()\n    try:\n        if args.operation == "_before-authority":\n            try:\n                B'
  b'._before_child_failure_begin()\n            except BaseException:\n                pass  # Optiona'
  b'l observation cannot change CLI admission or outcome.\n        if args.operation == "collect-expo'
  b'rt":\n            native._custody_progress_clear()\n        require(sys.flags.isolated == 1 and sy'
  b's.flags.no_site == 1 and sys.dont_write_bytecode,\n'),
 (b'            except BaseException:\n                pass  # Private child DATA cannot replace the '
  b'generic refusal or exit125.\n        return 125\n\n\nif __name__ == "__main__":\n',
  b'            except BaseException:\n                pass  # Private child DATA cannot replace the '
  b'generic refusal or exit125.\n        return 125\n    finally:\n        if args.operation == "_befor'
  b'e-authority":\n            try:\n                B._before_child_failure_clear()\n            excep'
  b't BaseException:\n                pass  # Observation teardown cannot replace the original return'
  b' or error.\n\n\nif __name__ == "__main__":\n'))


# Exact reviewed immutable-input memo delta; comparison bytes only.
# Restore the complete72be supplier before every older custody inverse.
_IMMUTABLE_INPUT_CUSTODY_INVERSES = ((b'_BEFORE_ATTEMPTS, _BEFORE_INPUTS, _BEFORE_CLOCKS, _BEFORE_AUTHORITIES = {}, {}, {}, {}\n',
  b'_BEFORE_ATTEMPTS, _BEFORE_INPUTS, _BEFORE_CLOCKS, _BEFORE_AUTHORITIES = {}, {}, {}, {}\n# Immutable-work '
  b'memo only; never an owner, deadline or transferable authority.\n_BEFORE_INPUT_PROOFS = {}\n'),
 (b'def _checked_before_input(result):\n    saved = _BEFORE_INPUTS.get(id(result))\n',
  b'def _checked_before_input(result, *, _guard_only=False):\n    require(type(_guard_only) is bool, "BEFORE_'
  b'INPUT_GUARD_MODE")\n    saved = _BEFORE_INPUTS.get(id(result))\n'),
 (b'    value = _before_input_data(canonical(raw), metadata.owner.first.clock.role)\n    require(tuple((row["'
  b'key"], row["first"]["sha256"]) for row in value["files"]) ==\n        tuple((name, O.digest(data)) for na'
  b'me, data in originals), "BEFORE_INPUT_HASH_CHANGED")\n    return dict(originals), value, metadata\n',
  b'    role = metadata.owner.first.clock.role\n    if id(result) in _BEFORE_INPUT_PROOFS:\n        proof '
  b'= _BEFORE_INPUT_PROOFS[id(result)]\n        require(type(proof) is tuple and len(proof) == 2 and proof[0]'
  b' is saved and\n            type(proof[1]) is type(role) is str and proof[1] == role, "BEFORE_INPUT_PROOF_'
  b'CHANGED")\n        if _guard_only:\n            return None\n    else:\n        # Only exact immutable o'
  b'riginals can avoid repeating pure byte validation.\n        require(type(raw) is bytes and type(originals'
  b') is tuple and all(type(row) is tuple and len(row) == 2 and\n            type(row[0]) is str and type(row'
  b'[1]) is bytes for row in originals) and type(role) is str,\n            "BEFORE_INPUT_PROOF_IMMUTABLE'
  b'")\n    value = _before_input_data(canonical(raw), role)\n    require(tuple((row["key"], row["first"]['
  b'"sha256"]) for row in value["files"]) ==\n        tuple((name, O.digest(data)) for name, data in original'
  b's), "BEFORE_INPUT_HASH_CHANGED")\n    if id(result) not in _BEFORE_INPUT_PROOFS:\n        _BEFORE_INPU'
  b'T_PROOFS[id(result)] = (saved, role)\n    if _guard_only:\n        return None\n    # Consumers still r'
  b'eceive newly parsed mutable values on every full check.\n    return dict(originals), value, metadata\n'),
 (b'                _checked_before_input(anchor.bound[0])\n',
  b'                _checked_before_input(anchor.bound[0], _guard_only=True)\n'),
 (b'            _checked_before_input(inputs)\n            owner.check()\n',
  b'            _checked_before_input(inputs, _guard_only=True)\n            owner.check()\n'))


# Restore the exact6d authority relation before the retained input-proof inverse.
_AUTHORITY_PROOF_CUSTODY_INVERSES = ((b'_BEFORE_INPUT_PROOFS = {}\n', b'_BEFORE_INPUT_PROOFS = {}\n_BEFORE_AUTHORITY_PROOFS = {}\n'),
 (b'        N._check_worker_pins(original_pins, clock.clock.role, closed=True)\n        index = canon'
  b'ical(index_raw)\n        require(type(index["fileCount"]) is int and index["fileCount"] == len(or'
  b'iginals) == 280 and\n            index["requiredFiles"] == [name for name, _raw in originals] and'
  b' len(index["files"]) == 280 and\n            type(index["directoryCount"]) is int and index["dire'
  b'ctoryCount"] == len(index["directories"]) == 58 and\n            type(index["totalBytes"]) is int'
  b' and index["totalBytes"] == sum(len(data) for _name, data in originals) <= MAX_BYTES and\n       '
  b'     index["authorityCloseSha256"] == O.digest(raw), "BEFORE_AUTHORITY_EXHAUSTIVE_ROSTER_CHANGED'
  b'")\n        for (name, data), row in zip(originals, index["files"]):\n            require(row["rel'
  b'ative"] == name and type(row["bytes"]) is int and row["bytes"] == len(data) and\n                '
  b'row["sha256"] == O.digest(data), "BEFORE_AUTHORITY_ORIGINAL_BYTES_CHANGED")\n        require(dict'
  b'(originals)["authority-close.json"] == raw and\n            index["closeWriterReturn"] == canonic'
  b'al(writer_close) and index["capture"] == "NOT_K_CAPTURE",\n            "BEFORE_AUTHORITY_CLOSE_WR'
  b'ITER_CHANGED")\n        _before_entry_current(entry)\n',
  b'        role = clock.clock.role\n        N._check_worker_pins(original_pins, role, closed=True)\n '
  b'       if id(result) in _BEFORE_AUTHORITY_PROOFS:\n            proof = _BEFORE_AUTHORITY_PROOFS[i'
  b'd(result)]\n            require(type(proof) is tuple and len(proof) == 2 and proof[0] is saved an'
  b'd\n                type(proof[1]) is type(role) is str and proof[1] == role, "BEFORE_AUTHORITY_PR'
  b'OOF_CHANGED")\n        else:\n            proof = None\n            # Only immutable byte relations'
  b' are memoized; native/current checks above still run.\n            require(all(type(value) is byt'
  b'es for value in (raw, readback, writer_close, index_raw)) and\n                type(originals) is'
  b' tuple and all(type(row) is tuple and len(row) == 2 and\n                type(row[0]) is str and '
  b'type(row[1]) is bytes for row in originals) and type(role) is str,\n                "BEFORE_AUTHO'
  b'RITY_PROOF_IMMUTABLE")\n            index = canonical(index_raw)\n            require(type(index["'
  b'fileCount"]) is int and index["fileCount"] == len(originals) == 280 and\n                index["r'
  b'equiredFiles"] == [name for name, _raw in originals] and len(index["files"]) == 280 and\n        '
  b'        type(index["directoryCount"]) is int and index["directoryCount"] == len(index["directories"]'
  b') == 58 and\n                type(index["totalBytes"]) is int and index["totalBytes"] == sum(len('
  b'data) for _name, data in originals) <= MAX_BYTES and\n                index["authorityCloseSha256'
  b'"] == O.digest(raw), "BEFORE_AUTHORITY_EXHAUSTIVE_ROSTER_CHANGED")\n            for (name, data),'
  b' row in zip(originals, index["files"]):\n                require(row["relative"] == name and type'
  b'(row["bytes"]) is int and row["bytes"] == len(data) and\n                    row["sha256"] == O.d'
  b'igest(data), "BEFORE_AUTHORITY_ORIGINAL_BYTES_CHANGED")\n            require(dict(originals)["aut'
  b'hority-close.json"] == raw and\n                index["closeWriterReturn"] == canonical(writer_cl'
  b'ose) and index["capture"] == "NOT_K_CAPTURE",\n                "BEFORE_AUTHORITY_CLOSE_WRITER_CHA'
  b'NGED")\n        _before_entry_current(entry)\n        require(_BEFORE_AUTHORITIES.get(id(result)) '
  b'is saved and\n            ((id(result) not in _BEFORE_AUTHORITY_PROOFS) if proof is None else\n   '
  b'          _BEFORE_AUTHORITY_PROOFS.get(id(result)) is proof), "BEFORE_AUTHORITY_PROOF_CHANGED")\n'
  b'        if proof is None:\n            _BEFORE_AUTHORITY_PROOFS[id(result)] = (saved, role)\n'))


# Exact reviewed before-clock diagnostic delta; comparison bytes only.
_BEFORE_RAW_CUSTODY_INVERSES = ((b'class _BeforeClock:\n',
  b'def _before_raw_failure_diagnostic(anchor, final, limit, frontier, end, number, local):\n    '
  b'"""Optional refusal DATA from existing observations; never a clock/owner check."""\n    frame'
  b' = None\n    try:\n        if type(anchor) is not _BeforeClockAnchor or type(anchor.binding) i'
  b's not tuple or len(anchor.binding) != 10:\n            return\n        binding = anchor.bindin'
  b'g\n        if type(binding[8]) is not tuple or len(binding[8]) != 4 or type(final) is not boo'
  b'l or \\\n                type(number) is not int or number not in (0, 1) or type(anchor.busy) '
  b'is not bool or \\\n                type(binding[4]) is not str or binding[4] not in ("parent",'
  b' "child") or \\\n                type(anchor.phase) is not str or anchor.phase not in ("METADA'
  b'TA", "WINDOW_BOUND", "BINDING", "AUTHORITY"):\n            return\n        selected, local_end'
  b' = binding[8][1 if final else 0], binding[8][3 if final else 2]\n        if not all(type(valu'
  b'e) is int and 0 <= value <= (1 << 64) - 1 for value in (selected, frontier, end)) or \\\n     '
  b'           limit is not None and (type(limit) is not int or not 0 <= limit <= (1 << 64) - 1)'
  b' or \\\n                not all(type(value) in (int, float) and math.isfinite(value) and value'
  b' >= 0\n                    for value in (local, local_end)):\n            return\n        if en'
  b'd != (selected if limit is None else min(selected, limit)):\n            return\n        raw_b'
  b'efore_end, busy, failure_clear = frontier < end, anchor.busy, anchor.failure is None\n       '
  b' if raw_before_end and busy and failure_clear:\n            return\n        raw_ms = (end - fr'
  b'ontier) // 1_000_000\n        local_ms = (local_end - local) * 1000\n        if not math.isfin'
  b'ite(local_ms):\n            return\n        local_ms = math.floor(local_ms)\n        paths = {s'
  b'tr(SCRIPTS / name): token for name, token in (\n            ("run-hosted-initial-recipient-ta'
  b'il.py", "TAIL"),\n            ("run-hosted-initial-recipient-custody.py", "CUSTODY"),\n       '
  b'     ("run-hosted-initial-recipient.py", "PRIMARY"),\n            ("run-hosted-cache-bootstra'
  b'p.py", "NATIVE"),\n            ("hosted_test_query.py", "QUERY"), ("hosted_test_identity.py",'
  b' "IDENTITY"),\n            ("hosted_cache_bootstrap_origin.py", "ORIGIN"),\n            ("host'
  b'ed_cache_bootstrap_service_time.py", "SERVICE_TIME"),\n            ("hosted_initial_recipient'
  b'_originals.py", "ORIGINALS"), ("hosted_job_clock.py", "CLOCK"),\n            ("hosted_initial'
  b'_recipient_continuity.py", "CONTINUITY"),\n            ("hosted_initial_recipient_before.py",'
  b' "BEFORE"),\n            ("hosted_initial_recipient_tail_evidence.py", "TAIL_EVIDENCE"),\n    '
  b'        ("hosted_initial_recipient_tail_handoff.py", "TAIL_HANDOFF"),\n            ("hosted_i'
  b'nitial_recipient_tail_carrier.py", "TAIL_CARRIER"),\n            ("hosted_initial_recipient_e'
  b'vidence.py", "EVIDENCE"))}\n        sites, count, truncated = [], 0, False\n        frame = sy'
  b's._getframe(1)\n        while frame is not None and count < 32:\n            token, line = pat'
  b'hs.get(frame.f_code.co_filename), frame.f_lineno\n            if token is not None and type(l'
  b'ine) is int and 1 <= line <= 1_000_000:\n                if len(sites) == 12:\n               '
  b'     truncated = True\n                    break\n                sites.append({"module": toke'
  b'n, "line": line})\n            frame, count = frame.f_back, count + 1\n        truncated = tru'
  b'ncated or frame is not None\n        record = {"schema": 1, "scope": "INITIAL_RECIPIENT_BEFOR'
  b'E_RAW_FAILURE_V1", "decision": "REJECTED",\n            "side": binding[4], "phase": anchor.p'
  b'hase, "iteration": number, "final": final,\n            "limitRelation": "NONE" if limit is N'
  b'one else "CLIPPED" if limit < selected else\n                "EQUAL" if limit == selected els'
  b'e "UNCLIPPED",\n            "rawBeforeEnd": raw_before_end, "busy": busy, "failureClear": fai'
  b'lure_clear,\n            "rawRemainingMs": min(900000, max(-900000, raw_ms)),\n            "ra'
  b'wRemainingClamped": not -900000 <= raw_ms <= 900000,\n            "sampledLocalRemainingMs": '
  b'min(900000, max(-900000, local_ms)),\n            "sampledLocalRemainingClamped": not -900000'
  b' <= local_ms <= 900000,\n            "callerSites": sites, "callersTruncated": truncated}\n   '
  b'     raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allo'
  b'w_nan=False)\n        if len(raw) <= 2048:\n            print(raw, file=sys.stderr)\n    except'
  b' BaseException:\n        pass  # Optional diagnostics cannot replace the original refusal.\n  '
  b'  finally:\n        frame = None  # Never retain caller frames or their locals beyond the fai'
  b'ling call.\n\n\nclass _BeforeClock:\n'),
 (b'            require(frontier < end and anchor.busy and anchor.failure is None, "BEFORE_RAW_E'
  b'XPIRED_OR_CHANGED")\n',
  b'            try:\n                require(frontier < end and anchor.busy and anchor.failure i'
  b's None, "BEFORE_RAW_EXPIRED_OR_CHANGED")\n            except BaseException:\n                t'
  b'ry:\n                    _before_raw_failure_diagnostic(anchor, final, limit, frontier, end, '
  b'number, local)\n                except BaseException:\n                    pass  # A replaced '
  b'diagnostic callback cannot mask the original refusal.\n                raise\n'))




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
        raise AssertionError("BEFORE_CHILD_CUSTODY_IDLE_BYTES")
    if raw.count(_PARENT_IDLE_AFTER) != 1 or _PARENT_IDLE_BEFORE in raw:
        raise AssertionError("BEFORE_CHILD_CUSTODY_IDLE_EXACT_CONTEXT")
    original = raw.replace(_PARENT_IDLE_AFTER, _PARENT_IDLE_BEFORE, 1)
    if hashlib.sha256(original).hexdigest() != _PARENT_IDLE_BASE_SHA256:
        raise AssertionError("BEFORE_CHILD_CUSTODY_IDLE_WHOLE_962A_PREIMAGE")
    return original


def operational_budget_preimage(name, raw):
    name = name.removeprefix("scripts/")
    if name not in _OPERATIONAL_BASELINES:
        return raw
    if type(raw) is not bytes:
        raise AssertionError("BEFORE_CHILD_CUSTODY_OPERATIONAL_BYTES")
    raw = parent_idle_preimage(name, raw)
    for before, after, count in reversed(_OPERATIONAL_DELTAS[name]):
        if raw.count(after) != count or before in raw:
            raise AssertionError("BEFORE_CHILD_CUSTODY_OPERATIONAL_EXACT_CONTEXT")
        raw = raw.replace(after, before)
    if hashlib.sha256(raw).hexdigest() != _OPERATIONAL_BASELINES[name]:
        raise AssertionError("BEFORE_CHILD_CUSTODY_OPERATIONAL_WHOLE_FBC1_PREIMAGE")
    return raw

def currency_input_preimage(raw):
    raw = operational_budget_preimage("run-hosted-initial-recipient-custody.py", raw)
    # Exact guard-scheduling inverse; keep all historical supplier pins.
    guard_before, guard_after = b'        self._local(anchor, final)\n        self._current(anchor)\n        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "BEFORE_FRONTIER_CHANGED")\n', b'        self._local(anchor, final)\n        require(anchor.last == frontier and anchor.busy and anchor.failure is None, "BEFORE_FRONTIER_CHANGED")\n'
    if type(raw) is not bytes or raw.count(guard_after) != 1:
        raise AssertionError("GUARD_SCHEDULING_EXACT_CONTEXT")
    raw = raw.replace(guard_after, guard_before, 1)
    # Normalize only the reviewed original-job gate allocation, not live functions.
    old_schedule, new_schedule = b'    work = min(O.integer(start + 240 * O.NS), job_end - 180 * O.NS)\n', b'    work = (job_end - 180 * O.NS if kind == "gate" else\n        min(O.integer(start + 240 * O.NS), job_end - 180 * O.NS))\n'
    if type(raw) is not bytes or raw.count(new_schedule) != 1:
        raise AssertionError("BEFORE_CHILD_CUSTODY_GATE_ALLOCATION_EXACT_CONTEXT")
    raw = raw.replace(new_schedule, old_schedule, 1)
    # Restore only the reviewed currency input access; retain every historical pin.
    before, after = b'        raws, _input_metadata, _metadata = _checked_before_input(result.input)\n', b'        _checked_before_input(result.input, _guard_only=True)\n        raws = dict(result.input.originals)\n'
    if type(raw) is not bytes or raw.count(after) != 1:
        raise AssertionError("BEFORE_CHILD_CUSTODY_CURRENCY_INPUT_EXACT_CONTEXT")
    restored = raw.replace(after, before, 1)
    if hashlib.sha256(restored).hexdigest() != \
            "ada25c13de1e74659d074c8c19ce9fb18b7729d0bb978d061f5e44a69605a4e2":
        raise AssertionError("BEFORE_CHILD_CUSTODY_CURRENCY_INPUT_77_WHOLE_PREIMAGE")
    return restored

def before_raw_custody_preimage(raw):
    raw = currency_input_preimage(raw)
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise AssertionError("BEFORE_CHILD_CUSTODY_BEFORE_RAW_BOUNDED_BYTES")
    original = raw
    for before, after in reversed(_BEFORE_RAW_CUSTODY_INVERSES):
        if original.count(after) != 1:
            raise AssertionError("BEFORE_CHILD_CUSTODY_BEFORE_RAW_EXACT_CONTEXT")
        original = original.replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != "e1ff9b12703f73598584b63f88fdcb14e2ae0286e76815def7592a612ce63f25":
        raise AssertionError("BEFORE_CHILD_CUSTODY_BEFORE_RAW_555_WHOLE_PREIMAGE")
    return original


def authority_proof_custody_preimage(raw):
    raw = before_raw_custody_preimage(raw)
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise AssertionError("BEFORE_CHILD_CUSTODY_AUTHORITY_PROOF_BYTES")
    original = raw
    for before, after in reversed(_AUTHORITY_PROOF_CUSTODY_INVERSES):
        if original.count(after) != 1:
            raise AssertionError("BEFORE_CHILD_CUSTODY_AUTHORITY_PROOF_CONTEXT")
        original = original.replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != '74b13a3a663bf2c0848a3f501123db3915c6b72500b48478d8801e5bdc241098':
        raise AssertionError("BEFORE_CHILD_CUSTODY_AUTHORITY_PROOF_WHOLE_PREIMAGE")
    return original


def immutable_input_custody_preimage(raw):
    raw = authority_proof_custody_preimage(raw)
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise AssertionError("BEFORE_CHILD_CUSTODY_IMMUTABLE_INPUT_BYTES")
    original = raw
    for before, after in reversed(_IMMUTABLE_INPUT_CUSTODY_INVERSES):
        if original.count(after) != 1:
            raise AssertionError("BEFORE_CHILD_CUSTODY_IMMUTABLE_INPUT_EXACT_CONTEXT")
        original = original.replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != \
            "7dce9f3ca357518b6ee647fe3e5419ff383e8293f334ea790cab6e0657a9899b":
        raise AssertionError("BEFORE_CHILD_CUSTODY_IMMUTABLE_INPUT_72BE_WHOLE_PREIMAGE")
    return original


# Exact reviewed export-only source-token insertion, comparison bytes only.
_EXPORT_PROCESS_CUSTODY_ROW = b'        str(SCRIPTS / "audit_processes.py"): "AUDIT_PROCESS",\n'
_EXPORT_PROCESS_CUSTODY_CONTEXT = b'        str(SCRIPTS / "hosted_initial_recipient_continuity.py"): "CONTINUITY",\n        str(SCRIPTS / "audit_processes.py"): "AUDIT_PROCESS",\n    }\n    node = traceback_head'


def export_process_custody_preimage(raw):
    raw = immutable_input_custody_preimage(raw)
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024 or \
            raw.count(_EXPORT_PROCESS_CUSTODY_ROW) != 1 or raw.count(_EXPORT_PROCESS_CUSTODY_CONTEXT) != 1:
        raise AssertionError("BEFORE_CHILD_CUSTODY_EXPORT_PROCESS_EXACT_CONTEXT")
    original = raw.replace(_EXPORT_PROCESS_CUSTODY_ROW, b"", 1)
    if hashlib.sha256(original).hexdigest() != \
            "9b622f09dc28162aeba7d6af8513087a206b2894263b453f09271c8508f314e4":
        raise AssertionError("BEFORE_CHILD_CUSTODY_EXPORT_PROCESS_F63_PREIMAGE")
    return original


def first_catch_custody_preimage(raw):
    raw = export_process_custody_preimage(raw)
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise AssertionError("BEFORE_CHILD_CUSTODY_FIRST_CATCH_BOUNDED_BYTES")
    original = raw
    for before, after in reversed(_FIRST_CATCH_CUSTODY_INVERSES):
        if original.count(after) != 1:
            raise AssertionError("BEFORE_CHILD_CUSTODY_FIRST_CATCH_EXACT_CONTEXT")
        original = original.replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != \
            "21ab23cf36d94f4d1c01c75a4c80750a41c224441b6c5b52370880a512a72cc0":
        raise AssertionError("BEFORE_CHILD_CUSTODY_FIRST_CATCH_0DA3_WHOLE_PREIMAGE")
    return original


# Exact reviewed diagnostic insertion; only the comparison preimage is restored.
# Actual source bytes, imported suppliers and compiled functions are never replaced.
_BEFORE_CHILD_CUSTODY_ADDITION = (
    b'        elif args.operation == "_before-authority":\n'
    b'            try:\n'
    b'                diagnostic = B._before_child_failure_line(error)\n'
    b'                if type(diagnostic) is str and diagnostic.isascii() and len(diagnostic) <= 2048:\n'
    b'                    print(diagnostic, file=sys.stderr)\n'
    b'            except BaseException:\n'
    b'                pass  # Private child DATA cannot replace the generic refusal or exit125.\n'
)


def before_child_custody_preimage(raw):
    raw = first_catch_custody_preimage(raw)
    context = (b"                pass  # Failure-only data cannot change exit125 or authorize a retry.\n" +
        _BEFORE_CHILD_CUSTODY_ADDITION + b"        return 125\n")
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024 or \
            raw.count(_BEFORE_CHILD_CUSTODY_ADDITION) != 1 or raw.count(context) != 1:
        raise AssertionError("BEFORE_CHILD_CUSTODY_EXACT_CONTEXT")
    original = raw.replace(_BEFORE_CHILD_CUSTODY_ADDITION, b"", 1)
    if hashlib.sha256(original).hexdigest() != \
            "ac193b29531566368882de33f1b7a8f238b8afd23c4d43dd9c4d008d27bc38ef":
        raise AssertionError("BEFORE_CHILD_CUSTODY_WHOLE_PREIMAGE")
    return original



# Exact reviewed first-catch delta; comparison bytes only, never runtime suppliers.
_FIRST_CATCH_BEFORE_INVERSES = ((b'\n\n_BEFORE_CHILD_FAILURE_SCOPE = "INITIAL_RECIPIENT_BEFORE_AUTHORITY_CHILD_FAILURE_SITES_V1"\n'
  b'\n\ndef _before_child_failure_encode(value):\n    """Finite DATA only; no exception text, autho'
  b'rity or operational state."""\n    try:\n        fixed = {"schema": 1, "scope": _BEFORE_CHILD_'
  b'FAILURE_SCOPE, "operation": "_before-authority",\n            "kind": "UNAVAILABLE", "stage":'
  b' "UNAVAILABLE", "origin": "FINAL_CATCH"}\n        if type(value) is not dict or set(value) !='
  b' {*fixed, "sites", "truncated"} or \\\n                any(type(value[key]) is not type(expect'
  b'ed) or value[key] != expected\n                    for key, expected in fixed.items()) or typ'
  b'e(value["truncated"]) is not bool or \\\n                type(value["sites"]) is not list or l'
  b'en(value["sites"]) > 12:\n            return None\n        for row in value["sites"]:\n',
  b'\n\n_BEFORE_CHILD_FAILURE_SCOPE = "INITIAL_RECIPIENT_BEFORE_AUTHORITY_CHILD_FAILURE_SITES_V1"\n'
  b'_BEFORE_CHILD_FAILURE = None\n\n\ndef _before_child_failure_begin():\n    global _BEFORE_CHI'
  b'LD_FAILURE\n    try:\n        if _BEFORE_CHILD_FAILURE is not None:\n            _BEFORE_CHILD_'
  b'FAILURE = False  # Disabled until clear/consume, even across further reentry.\n            re'
  b'turn\n        _BEFORE_CHILD_FAILURE = {"selected": False, "error": None, "sites": None, "trun'
  b'cated": None}\n    except BaseException:\n        _BEFORE_CHILD_FAILURE = None\n\n\ndef _befo'
  b're_child_failure_remember(error):\n    """Copy first child-catch DATA before outer owner/meta'
  b'data cleanup reraises."""\n    try:\n        state = _BEFORE_CHILD_FAILURE\n        if type(sta'
  b'te) is not dict or state["selected"] is not False or not isinstance(error, BaseException):\n '
  b'           return\n        # Select before traversal; failed observation must not select a la'
  b'ter error.\n        state["selected"], state["error"] = True, error\n        sites, truncated '
  b'= _tail_failure_sites(BaseException.__traceback__.__get__(error))\n        state["sites"], st'
  b'ate["truncated"] = sites, truncated\n    except BaseException:\n        pass  # Optional DATA '
  b'cannot replace the original failure or its cleanup.\n\n\ndef _before_child_failure_clear():'
  b'\n    global _BEFORE_CHILD_FAILURE\n    _BEFORE_CHILD_FAILURE = None\n\n\ndef _before_child_f'
  b'ailure_encode(value):\n    """Finite DATA only; no exception text, authority or operational s'
  b'tate."""\n    try:\n        fixed = {"schema": 1, "scope": _BEFORE_CHILD_FAILURE_SCOPE, "opera'
  b'tion": "_before-authority",\n            "kind": "UNAVAILABLE", "stage": "UNAVAILABLE"}\n     '
  b'   if type(value) is not dict or set(value) != {*fixed, "origin", "sites", "truncated"} or \\'
  b'\n                any(type(value[key]) is not type(expected) or value[key] != expected\n      '
  b'              for key, expected in fixed.items()) or type(value["origin"]) is not str or \\\n '
  b'               value["origin"] not in ("FIRST_FAILURE", "FINAL_CATCH") or type(value["trunca'
  b'ted"]) is not bool or \\\n                type(value["sites"]) is not list or len(value["sites'
  b'"]) > 12:\n            return None\n        for row in value["sites"]:\n'),
 (b'\n\ndef _before_child_failure_line(error):\n    """Separate actual BEFORE-child final catch; ne'
  b'ver a first-failure claim."""\n    try:\n        if not isinstance(error, BaseException):\n    '
  b'        return None\n        sites, truncated = _tail_failure_sites(BaseException.__traceback'
  b'__.__get__(error))\n        return _before_child_failure_encode({"schema": 1, "scope": _BEFOR'
  b'E_CHILD_FAILURE_SCOPE,\n            "operation": "_before-authority", "kind": "UNAVAILABLE", '
  b'"stage": "UNAVAILABLE",\n',
  b'\n\ndef _before_child_failure_line(error):\n    """Consume first-catch DATA by identity, otherw'
  b'ise label the final-catch fallback."""\n    global _BEFORE_CHILD_FAILURE\n    state, _BEFORE_C'
  b'HILD_FAILURE = _BEFORE_CHILD_FAILURE, None\n    try:\n        if not isinstance(error, BaseExc'
  b'eption):\n            return None\n        if type(state) is dict and state.get("selected") is'
  b' True and state.get("error") is error:\n            # No fallback for an unavailable same-err'
  b'or memo: it must not relabel\n            # a later cleanup snapshot as the original first ca'
  b'tch.\n            return _before_child_failure_encode({"schema": 1, "scope": _BEFORE_CHILD_FA'
  b'ILURE_SCOPE,\n                "operation": "_before-authority", "kind": "UNAVAILABLE", "stage'
  b'": "UNAVAILABLE",\n                "origin": "FIRST_FAILURE", "sites": state["sites"], "trunc'
  b'ated": state["truncated"]})\n        sites, truncated = _tail_failure_sites(BaseException.__t'
  b'raceback__.__get__(error))\n        return _before_child_failure_encode({"schema": 1, "scope"'
  b': _BEFORE_CHILD_FAILURE_SCOPE,\n            "operation": "_before-authority", "kind": "UNAVAI'
  b'LABLE", "stage": "UNAVAILABLE",\n'))


# Admit only the reviewed GitHub pending/unstarted compatibility delta before
# comparing historical diagnostic source. Runtime imports keep the new source.
_PENDING_STEP_BEFORE_INVERSES = ((b'            status in ("queued", "in_progress", "completed"), "STEP_NAME_NUMBER_STATUS")\n',
  b'            status in ("queued", "pending", "in_progress", "completed"), "STEP_NAME_NUMBER_STATUS")\n'),
 (b'        if status == "queued":\n            require(conclusion is None and started is None and comple'
  b'ted is None, "STEP_QUEUED")\n',
  b'        if status in ("queued", "pending"):\n            require(conclusion is None and started is No'
  b'ne and completed is None, "STEP_QUEUED")\n'),
 (b'    require(all(row["status"] == ("completed" if row["number"] < current else "queued")\n        for '
  b'row in rows if row["number"] != current), "STEP_UNIQUE_CURRENT_FRONTIER")\n',
  b'    require(all(row["status"] in (("completed",) if row["number"] < current else ("queued", "pending'
  b'"))\n        for row in rows if row["number"] != current), "STEP_UNIQUE_CURRENT_FRONTIER")\n'))


def pending_step_before_preimage(raw):
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise AssertionError("BEFORE_CHILD_CODEC_PENDING_BOUNDED_BYTES")
    original = raw
    for before, after in reversed(_PENDING_STEP_BEFORE_INVERSES):
        if original.count(after) != 1:
            raise AssertionError("BEFORE_CHILD_CODEC_PENDING_EXACT_CONTEXT")
        original = original.replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != \
            "7e453819e519251d65daeaf5b2b957bb5208edc7cddadf7bbc79b0a66122fc71":
        raise AssertionError("BEFORE_CHILD_CODEC_PENDING_75CF_WHOLE_PREIMAGE")
    return original


def first_catch_before_preimage(raw):
    raw = pending_step_before_preimage(raw)
    if type(raw) is not bytes or not 0 < len(raw) <= 2 * 1024 * 1024:
        raise AssertionError("BEFORE_CHILD_CODEC_FIRST_CATCH_BOUNDED_BYTES")
    original = raw
    for before, after in reversed(_FIRST_CATCH_BEFORE_INVERSES):
        if original.count(after) != 1:
            raise AssertionError("BEFORE_CHILD_CODEC_FIRST_CATCH_EXACT_CONTEXT")
        original = original.replace(after, before, 1)
    if hashlib.sha256(original).hexdigest() != \
            "81cf980a9baf65290522754363a1c1d175cf6c0baf58af4ce8a9d9b5eeeec3fe":
        raise AssertionError("BEFORE_CHILD_CODEC_FIRST_CATCH_0DA3_WHOLE_PREIMAGE")
    return original


# Exact K-only diagnostic inverse; operational imports/AST above remain current.
_K_FAILURE_BASELINES = {'hosted_initial_recipient_before.py': '600e156921a806dc7880bf7e6ccefb08929b551c5e72463480aabc250e021688',
 'run-hosted-initial-recipient-tail.py': '8be3680dc2226e38b95d849cd87f3a2af309c6f443bb823b5570bfba595072cc'}
_K_FAILURE_DELTAS = {'hosted_initial_recipient_before.py': [(b'\n\n_ENTRY_LATCHES = {}\n\n',
                                         b'\n\ndef _tail_child_failure_projection(raw):\n    """One exact '
                                         b'K-child refusal packet to finite DATA; never reader/close proof.'
                                         b'"""\n    try:\n        if type(raw) is not bytes or not 0 < len(ra'
                                         b'w) <= 65536:\n            return None\n        lines = raw.split(b'
                                         b'"\\n")\n        if len(lines) != 3 or lines[0] != b"INITIAL_RECIPI'
                                         b'ENT_K_TAIL_NOT_ACCEPTED" or \\\n                lines[2] != b"" or'
                                         b' not 0 < len(lines[1]) <= 2048:\n            return None\n        '
                                         b'line = lines[1].decode("ascii")\n\n        def pairs(items):\n '
                                         b'           result = {}\n            for key, value in items:\n    '
                                         b'            if key in result:\n                    raise ValueErr'
                                         b'or("TAIL_CHILD_DUPLICATE_FIELD")\n                result[key] = v'
                                         b'alue\n            return result\n\n        def nonfinite(_value'
                                         b'):\n            raise ValueError("TAIL_CHILD_NONFINITE_JSON")'
                                         b'\n\n        value = json.loads(line, object_pairs_hook=pairs, pars'
                                         b'e_constant=nonfinite)\n        fixed = {"schema": 1, "scope": "IN'
                                         b'ITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",\n            "operation":'
                                         b' "_tail-child", "kind": "UNAVAILABLE"}\n        if type(value) is'
                                         b' not dict or set(value) != {*fixed, "stage", "origin", "sites", '
                                         b'"truncated"} or \\\n                any(type(value[key]) is not ty'
                                         b'pe(expected) or value[key] != expected for key, expected in fixe'
                                         b'd.items()) or \\\n                type(value["origin"]) is not str'
                                         b' or value["origin"] not in ("FIRST_FAILURE", "FINAL_CATCH") or \\'
                                         b'\n                type(value["stage"]) is not str or not (value["'
                                         b'stage"] in ("CHILD_ENTRY", "CHILD_WORK") or\n                    '
                                         b'value["stage"] == "UNAVAILABLE" and value["origin"] == "FINAL_CA'
                                         b'TCH") or \\\n                type(value["truncated"]) is not bool '
                                         b'or type(value["sites"]) is not list or len(value["sites"]) > 12:'
                                         b'\n            return None\n        for row in value["sites"]:\n'
                                         b'            if type(row) is not dict or set(row) != {"module", "'
                                         b'line"} or type(row["module"]) is not str or \\\n                  '
                                         b'  row["module"] not in _TAIL_FAILURE_PATHS.values() or type(row['
                                         b'"line"]) is not int or \\\n                    not 1 <= row["line"'
                                         b'] <= 1_000_000:\n                return None\n        encoded = js'
                                         b'on.dumps(value, sort_keys=True, separators=(",", ":"), ensure_as'
                                         b'cii=True, allow_nan=False)\n        return encoded if encoded == '
                                         b'line else None\n    except BaseException:\n        return None'
                                         b'\n\n\n_ENTRY_LATCHES = {}\n\n')],
 'run-hosted-initial-recipient-tail.py': [(b'\n\ndef _native_tail(parent):\n    """NEW genuine C native owne'
                                           b'r; no old clock attachment or phase widening."""\n',
                                           b'\n\n@dataclass(eq=False, repr=False)\nclass _TailChildDiagnosti'
                                           b'c:\n    """Optional K-only reader state; never a live authori'
                                           b'ty or native close."""\n    binding: tuple\n    child: object '
                                           b'= None\n    consumed: bool = False\n    fd: object = None\n    '
                                           b'close_attempted: bool = False\n    closed: bool = False\n    u'
                                           b'nknown: bool = False\n    fault: object = None\n\n\n@dataclass(f'
                                           b'rozen=True, repr=False)\nclass _TailDiagnosticFd:\n    descrip'
                                           b'tor: int\n\n    def fileno(self):\n        return self.descript'
                                           b'or\n\n\n# Ambiguous descriptors remain terminal holdings: never'
                                           b' probe/reclose a number.\n_TAIL_CHILD_DIAGNOSTIC_HOLDS = []\n\n'
                                           b'\ndef _tail_child_diagnostic_binding(context, role, directory'
                                           b', writer, scope, end, preparer, anchor, row):\n    try:\n     '
                                           b'   if not (context.get("scope") == CONTEXT_SCOPE and context.get'
                                           b'("kind") == "gate" and\n                role == "linux-x64" a'
                                           b'nd os.name == "posix" and os.getuid() != 0):\n            ret'
                                           b'urn None\n        require(type(directory) is Q._PosixDirector'
                                           b'y and type(writer) is Q._PosixSink and\n            type(scop'
                                           b'e) is native.processes.LinuxScope and type(anchor) is C._Custody'
                                           b'OwnerAnchor and\n            anchor.unknown is False and type'
                                           b'(row) is dict and row["launchAttempted"] is False and\n      '
                                           b'      writer.parent is directory and writer.path == directory.pa'
                                           b'th / "stderr.log" and\n            writer.maximum == native.S'
                                           b'TDERR_LIMIT and type(end) in (int, float) and math.isfinite(end)'
                                           b' and\n            end == writer.deadline and type(preparer) i'
                                           b's dict, "K_DIAGNOSTIC_BINDING")\n        scope_row = next(val'
                                           b'ue for value in anchor.rows if value[1] == "native-scope" and va'
                                           b'lue[2] is scope)\n        stderr_row = next(value for value i'
                                           b'n anchor.rows if value[1] == "stderr" and value[2] is writer'
                                           b')\n        require(scope_row[3:] == stderr_row[3:] == (False,'
                                           b' False), "K_DIAGNOSTIC_ORIGINAL_ROWS")\n        native.posix.'
                                           b'_deadline(end)\n        directory.verify()\n        writer.ver'
                                           b'ify()\n        return _TailChildDiagnostic((directory, writer'
                                           b', scope, directory.path, tuple(directory.identity),\n        '
                                           b'    (writer.original.st_dev, writer.original.st_ino), end, tuple'
                                           b'(sorted(preparer.items())),\n            anchor, scope_row[0]'
                                           b', stderr_row[0], row))\n    except BaseException:\n        ret'
                                           b'urn None\n\n\ndef _tail_child_diagnostic_launched(state, child)'
                                           b':\n    try:\n        if type(state) is not _TailChildDiagnosti'
                                           b'c or state.consumed:\n            return\n        require(stat'
                                           b'e.child is None and type(child) is native.processes.PosixProcess'
                                           b' and\n            type(child.process) is native.processes.sub'
                                           b'process.Popen and\n            state.binding[2].leaders == [c'
                                           b'hild], "K_DIAGNOSTIC_ORIGINAL_LEADER")\n        state.child ='
                                           b' (child, child.process)\n    except BaseException:\n        if'
                                           b' type(state) is _TailChildDiagnostic:\n            state.cons'
                                           b'umed = True\n\n\ndef _tail_child_diagnostic_retired(state):\n   '
                                           b' directory, writer, scope, _path, _pin, _writer_pin, end, prepar'
                                           b'er, anchor, scope_row, stderr_row, row = state.binding\n    r'
                                           b'equire(type(state.child) is tuple and len(state.child) == 2, "K_'
                                           b'DIAGNOSTIC_LAUNCH_MISSING")\n    child, process = state.child'
                                           b'\n    require(type(child) is native.processes.PosixProcess an'
                                           b'd child.process is process and\n        type(process) is nati'
                                           b've.processes.subprocess.Popen and type(process.returncode) is in'
                                           b't and\n        process.returncode == 125, "K_DIAGNOSTIC_POST_'
                                           b'DRAIN_CODE")\n    require(C._CUSTODY_OWNERS.get(id(anchor.own'
                                           b'er)) is anchor and anchor.owner.__dict__ is anchor.dictionary an'
                                           b'd\n        anchor.unknown is False and anchor.failure is not '
                                           b'None and row["launchAttempted"] is True and\n        row["sur'
                                           b'vivors"] == [] and row["ownership"]["discoveryErrors"] == [] and'
                                           b'\n        tuple(sorted(row["preparerIdentity"].items())) == p'
                                           b'reparer and\n        row["scopeCloseAttempted"] is True and r'
                                           b'ow["scopeClosed"] is True and\n        scope._closed is True '
                                           b'and scope._retirement_error is None and scope.leaders == [] and '
                                           b'scope.handles == {} and\n        scope.discovery_errors == se'
                                           b't(), "K_DIAGNOSTIC_RETIREMENT_UNKNOWN")\n    require(any(save'
                                           b'd is scope_row and label == "native-scope" and resource is scope'
                                           b' and attempted is True and closed is True\n        for saved,'
                                           b' label, resource, attempted, closed in anchor.rows) and\n    '
                                           b'    any(saved is stderr_row and label == "stderr" and resource i'
                                           b's writer and attempted is False and closed is False\n        '
                                           b'for saved, label, resource, attempted, closed in anchor.rows), "'
                                           b'K_DIAGNOSTIC_ORIGINAL_CLOSE_ROWS")\n    require(row["captureO'
                                           b'utcomes"]["stderr"]["synced"] is True and\n        row["captu'
                                           b'reOutcomes"]["stderr"]["verified"] is True, "K_DIAGNOSTIC_SINK_N'
                                           b'OT_VERIFIED")\n    native.posix._deadline(end)\n\n\ndef _tail_ch'
                                           b'ild_diagnostic_files(state, reader=None, expected=None):\n   '
                                           b' directory, writer, _scope, path, pin, writer_pin, end, *_rest ='
                                           b' state.binding\n    native.posix._deadline(end)\n    require(t'
                                           b'ype(directory) is Q._PosixDirectory and type(writer) is Q._Posix'
                                           b'Sink and directory.path == path and\n        tuple(directory.'
                                           b'identity) == pin and writer.parent is directory and writer.path '
                                           b'== path / "stderr.log" and\n        (writer.original.st_dev, '
                                           b'writer.original.st_ino) == writer_pin and writer.deadline == end'
                                           b' and\n        writer.maximum == native.STDERR_LIMIT and not w'
                                           b'riter.closed, "K_DIAGNOSTIC_FILE_BINDING")\n    directory.ver'
                                           b'ify()\n    info = writer.verify()\n    for stream in (writer,)'
                                           b' if reader is None else (writer, reader):\n        named, ope'
                                           b'ned = writer.path.lstat(), os.fstat(stream.fileno())\n       '
                                           b' require(all(stat.S_ISREG(value.st_mode) and stat.S_IMODE(value.'
                                           b'st_mode) == 0o600 and\n            value.st_uid == os.getuid('
                                           b') and value.st_nlink == 1 for value in (named, opened)) and\n'
                                           b'            os.path.samestat(named, opened), "K_DIAGNOSTIC_PRIVA'
                                           b'TE_FILE")\n        require(Q._file_info(writer.path, stream, '
                                           b'native.STDERR_LIMIT) == info, "K_DIAGNOSTIC_READER_PIN")\n   '
                                           b' require((info.device, info.inode) == writer_pin and (expected i'
                                           b's None or info == expected), "K_DIAGNOSTIC_STAMP")\n    nativ'
                                           b'e.posix._deadline(end)\n    return info\n\n\ndef _tail_child_dia'
                                           b'gnostic(state):\n    """Once, after real scope close, before '
                                           b'original sink close; no owner/fence."""\n    if type(state) i'
                                           b's not _TailChildDiagnostic or state.consumed:\n        return'
                                           b' None\n    state.consumed = True\n    raw, before, hold = None'
                                           b', None, None\n    try:\n        _tail_child_diagnostic_retired'
                                           b'(state)\n        before = _tail_child_diagnostic_files(state)'
                                           b'\n        hold = _TAIL_CHILD_DIAGNOSTIC_HOLDS\n        hold.ap'
                                           b'pend(state)  # BEFORE open: no returned descriptor can be orphan'
                                           b'ed.\n        state.fd = os.open(state.binding[1].path, os.O_R'
                                           b'DONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)\n      '
                                           b'  require(type(state.fd) is int and 0 <= state.fd <= 2147483647,'
                                           b' "K_DIAGNOSTIC_DESCRIPTOR")\n        reader = _TailDiagnostic'
                                           b'Fd(state.fd)\n        _tail_child_diagnostic_files(state, rea'
                                           b'der, before)\n        raw = os.read(state.fd, native.STDERR_L'
                                           b'IMIT + 1)\n        require(type(raw) is bytes and len(raw) =='
                                           b' before.size <= native.STDERR_LIMIT, "K_DIAGNOSTIC_SIZE")\n  '
                                           b'      _tail_child_diagnostic_files(state, reader, before)\n  '
                                           b'      require(os.read(state.fd, 1) == b"", "K_DIAGNOSTIC_EOF'
                                           b'")\n        _tail_child_diagnostic_files(state, reader, befor'
                                           b'e)\n    except BaseException as error:\n        state.fault = '
                                           b'error\n    finally:\n        if state.fd is not None:\n        '
                                           b'    try:\n                native.posix._deadline(state.bindin'
                                           b'g[6])\n            except BaseException as error:\n           '
                                           b'     if state.fault is None:\n                    state.fault'
                                           b' = error\n            state.close_attempted = True\n          '
                                           b'  try:\n                require(type(state.fd) is int and 0 <'
                                           b'= state.fd <= 2147483647, "K_DIAGNOSTIC_UNKNOWN_DESCRIPTOR")'
                                           b'\n                os.close(state.fd)\n                state.cl'
                                           b'osed, state.fd = True, None\n            except BaseException'
                                           b' as error:\n                state.unknown, state.fault = True'
                                           b', error\n        if hold is not None and state.fd is None and'
                                           b' not state.unknown:\n            if any(value is state for va'
                                           b'lue in hold):\n                hold.remove(state)\n    if stat'
                                           b'e.fault is not None or not state.closed:\n        return None'
                                           b'\n    try:\n        _tail_child_diagnostic_retired(state)\n    '
                                           b'    _tail_child_diagnostic_files(state, expected=before)\n   '
                                           b'     line = B._tail_child_failure_projection(raw)\n        na'
                                           b'tive.posix._deadline(state.binding[6])\n        return line\n '
                                           b'   except BaseException:\n        return None\n\n\ndef _tail_cos'
                                           b't_begin():\n    """Optional poll-loop cost only; never suppli'
                                           b'es a deadline or acceptance."""\n    try:\n        wall, cpu ='
                                           b' time.monotonic_ns(), time.process_time_ns()\n        if type'
                                           b'(wall) is not int or type(cpu) is not int or min(wall, cpu) < 0:'
                                           b'\n            return None\n        return {"first": (wall, cpu'
                                           b'), "last": (wall, cpu), "currency_start": None,\n            '
                                           b'"currency": [0, 0], "loops": 0, "currencies": 0, "polls": 0, "po'
                                           b'll_code": None,\n            "phase": "LOOP_ENTRY", "failed":'
                                           b' False, "disabled": False, "snapshot": None}\n    except Base'
                                           b'Exception:\n        return None\n\n\ndef _tail_cost_event(state,'
                                           b' phase, code=None):\n    try:\n        if type(state) is not d'
                                           b'ict or state["disabled"] or state["failed"]:\n            ret'
                                           b'urn\n        require(phase in ("CURRENCY", "PRE_POLL_CLOCK", '
                                           b'"POST_POLL_CLOCK", "DISCOVER_SLEEP", "FAILURE"), "K_COST_PHASE")'
                                           b'\n        wall, cpu = time.monotonic_ns(), time.process_time_'
                                           b'ns()\n        require(type(wall) is int and type(cpu) is int '
                                           b'and wall >= state["last"][0] and cpu >= state["last"][1],\n  '
                                           b'          "K_COST_BACKWARDS")\n        state["last"] = (wall,'
                                           b' cpu)\n        if phase == "CURRENCY":\n            require(st'
                                           b'ate["currency_start"] is None, "K_COST_CURRENCY_REENTRY")\n  '
                                           b'          state["loops"] += 1\n            state["currency_st'
                                           b'art"] = (wall, cpu)\n        elif phase == "PRE_POLL_CLOCK":\n'
                                           b'            require(state["currency_start"] is not None, "K_COST'
                                           b'_CURRENCY_RETURN")\n            for index, value in enumerate'
                                           b'((wall, cpu)):\n                state["currency"][index] += v'
                                           b'alue - state["currency_start"][index]\n            state["cur'
                                           b'rency_start"] = None\n            state["currencies"] += 1\n  '
                                           b'      elif phase == "POST_POLL_CLOCK":\n            require(c'
                                           b'ode is None or type(code) is int and -255 <= code <= 255, "K_COS'
                                           b'T_POLL_CODE")\n            state["polls"] += 1\n            st'
                                           b'ate["poll_code"] = code\n        elif phase == "FAILURE":\n   '
                                           b'         state["failed"] = True  # Freeze FIRST observation befo'
                                           b're cleanup.\n            values = {"loopWallMs": (wall - stat'
                                           b'e["first"][0]) // 1_000_000,\n                "loopCpuMs": (c'
                                           b'pu - state["first"][1]) // 1_000_000,\n                "compl'
                                           b'etedCurrencyWallMs": state["currency"][0] // 1_000_000,\n    '
                                           b'            "completedCurrencyCpuMs": state["currency"][1] // 1_'
                                           b'000_000}\n            state["snapshot"] = {"schema": 1, "scop'
                                           b'e": "INITIAL_RECIPIENT_K_PARENT_LOOP_COST_V1",\n             '
                                           b'   "decision": "REJECTED", "phase": state["phase"], "loops": min'
                                           b'(1_000_000, state["loops"]),\n                "completedCurre'
                                           b'ncies": min(1_000_000, state["currencies"]), "polls": min(1_000_'
                                           b'000, state["polls"]),\n                "countsClamped": max(s'
                                           b'tate["loops"], state["currencies"], state["polls"]) > 1_000_000,'
                                           b'\n                **{name: min(900000, value) for name, value'
                                           b' in values.items()},\n                "timesClamped": any(val'
                                           b'ue > 900000 for value in values.values()),\n                "'
                                           b'lastObservedPollCode": state["poll_code"], "childCause": "UNKNOW'
                                           b'N"}\n            return\n        state["phase"] = phase\n    ex'
                                           b'cept BaseException:\n        if type(state) is dict:\n        '
                                           b'    state["disabled"] = True\n\n\ndef _tail_cost_line(state, di'
                                           b'agnostic=None):\n    try:\n        if type(state) is not dict '
                                           b'or state["disabled"] or not state["failed"] or type(state["snaps'
                                           b'hot"]) is not dict:\n            return None\n        value = '
                                           b'state["snapshot"]\n        fixed = {"schema": 1, "scope": "IN'
                                           b'ITIAL_RECIPIENT_K_PARENT_LOOP_COST_V1", "decision": "REJECTE'
                                           b'D",\n            "childCause": "UNKNOWN"}\n        counts = ("'
                                           b'loops", "completedCurrencies", "polls")\n        times = ("lo'
                                           b'opWallMs", "loopCpuMs", "completedCurrencyWallMs", "completedCur'
                                           b'rencyCpuMs")\n        require(set(value) == {*fixed, *counts,'
                                           b' *times, "phase", "countsClamped", "timesClamped", "lastObserved'
                                           b'PollCode"} and\n            all(type(value[key]) is type(expe'
                                           b'cted) and value[key] == expected for key, expected in fixed.item'
                                           b's()) and\n            type(value["phase"]) is str and value["'
                                           b'phase"] in\n                ("LOOP_ENTRY", "CURRENCY", "PRE_P'
                                           b'OLL_CLOCK", "POST_POLL_CLOCK", "DISCOVER_SLEEP") and\n       '
                                           b'     all(type(value[key]) is int and 0 <= value[key] <= 1_000_00'
                                           b'0 for key in counts) and\n            all(type(value[key]) is'
                                           b' int and 0 <= value[key] <= 900000 for key in times) and\n   '
                                           b'         all(type(value[key]) is bool for key in ("countsClamped'
                                           b'", "timesClamped")) and\n            (value["lastObservedPoll'
                                           b'Code"] is None or type(value["lastObservedPollCode"]) is int and'
                                           b'\n                -255 <= value["lastObservedPollCode"] <= 25'
                                           b'5), "K_COST_FINITE_FIELDS")\n        post_code = None\n       '
                                           b' if type(diagnostic) is _TailChildDiagnostic and type(diagnostic'
                                           b'.child) is tuple and len(diagnostic.child) == 2:\n           '
                                           b' child, process = diagnostic.child\n            scope = diagn'
                                           b'ostic.binding[2]\n            anchor, scope_row, _stderr_row,'
                                           b' row = diagnostic.binding[8:]\n            if type(child) is '
                                           b'native.processes.PosixProcess and child.process is process a'
                                           b'nd \\\n                    type(process) is native.processes.s'
                                           b'ubprocess.Popen and scope._closed is True and \\\n            '
                                           b'        scope._retirement_error is None and row["scopeCloseAttem'
                                           b'pted"] is True and row["scopeClosed"] is True and \\\n        '
                                           b'            any(saved is scope_row and label == "native-scope" a'
                                           b'nd resource is scope and attempted is True and closed is Tru'
                                           b'e\n                        for saved, label, resource, attemp'
                                           b'ted, closed in anchor.rows) and \\\n                    type(p'
                                           b'rocess.returncode) is int and -255 <= process.returncode <= 255:'
                                           b'\n                post_code = process.returncode  # Cached or'
                                           b'iginal Popen field, NOT an extra poll.\n        raw = json.du'
                                           b'mps({**value, "postScopeCloseCode": post_code}, sort_keys=True, '
                                           b'separators=(",", ":"),\n            ensure_ascii=True, allow_'
                                           b'nan=False)\n        return raw if len(raw) <= 2048 else None\n'
                                           b'    except BaseException:\n        return None\n\n\ndef _native_'
                                           b'tail(parent):\n    """NEW genuine C native owner; no old cloc'
                                           b'k attachment or phase widening."""\n'),
                                          (b'    row = None\n    native_known = False\n    try:\n        own'
                                           b'er = C._CustodyOwner(min(clock.local_end, clock.deadline(900, fi'
                                           b'nal=True, limit=caps[2])), clock,\n',
                                           b'    row = None\n    native_known = False\n    diagnostic = cos'
                                           b't = None\n    try:\n        owner = C._CustodyOwner(min(clock.'
                                           b'local_end, clock.deadline(900, final=True, limit=caps[2])), cloc'
                                           b'k,\n'),
                                          (b'                "kernelJob": clock.clock.role == "windows-x64"})'
                                           b'\n            row["baselineSha256"] = O.digest(baseline_raw)\n'
                                           b'            _prelaunch_budget(parent, caps)\n            N._c'
                                           b'heck_history(original_inputs)\n',
                                           b'                "kernelJob": clock.clock.role == "windows-x64"})'
                                           b'\n            row["baselineSha256"] = O.digest(baseline_raw)\n'
                                           b'            try:\n                diagnostic = _tail_child_di'
                                           b'agnostic_binding(context, context["observed"]["role"], service, '
                                           b'err,\n                    scope, capture_end, row["preparerId'
                                           b'entity"], owner_anchor, row)\n            except BaseExceptio'
                                           b'n:\n                diagnostic = None  # Optional observation'
                                           b' never changes launch admission.\n            _prelaunch_budg'
                                           b'et(parent, caps)\n            N._check_history(original_input'
                                           b's)\n'),
                                          (b'            require(len(leaders) == 1, "NATIVE_ACTUAL_BIRTH"'
                                           b')\n            row["leader"] = dict(leaders[0])\n            n'
                                           b'ative.lifetime(row["leader"], clock.clock.role)\n            '
                                           b'birth_raw = owner.write(service, "native-start.json", {"ownershi'
                                           b'p": birth, "leader": row["leader"],\n',
                                           b'            require(len(leaders) == 1, "NATIVE_ACTUAL_BIRTH"'
                                           b')\n            row["leader"] = dict(leaders[0])\n            t'
                                           b'ry:\n                _tail_child_diagnostic_launched(diagnost'
                                           b'ic, child)\n            except BaseException:\n               '
                                           b' diagnostic = None\n            native.lifetime(row["leader"]'
                                           b', clock.clock.role)\n            birth_raw = owner.write(serv'
                                           b'ice, "native-start.json", {"ownership": birth, "leader": row["le'
                                           b'ader"],\n'),
                                          (b'            row["nativeStartSha256"] = O.digest(birth_raw)\n '
                                           b'           N._check_history(birth_graph)\n            while T'
                                           b'rue:\n                parent.currency()\n                paren'
                                           b't.now(limit=caps[1])\n                N._check_history(origin'
                                           b'al_inputs)\n',
                                           b'            row["nativeStartSha256"] = O.digest(birth_raw)\n '
                                           b'           N._check_history(birth_graph)\n            try:\n  '
                                           b'              cost = _tail_cost_begin() if context["kind"] == "g'
                                           b'ate" else None\n            except BaseException:\n           '
                                           b'     cost = None\n            while True:\n                try'
                                           b':\n                    _tail_cost_event(cost, "CURRENCY")\n   '
                                           b'             except BaseException:\n                    cost '
                                           b'= None\n                parent.currency()\n                try'
                                           b':\n                    _tail_cost_event(cost, "PRE_POLL_CLOCK'
                                           b'")\n                except BaseException:\n                   '
                                           b' cost = None\n                parent.now(limit=caps[1])\n     '
                                           b'           N._check_history(original_inputs)\n'),
                                          (b'                    stream.observe_live_output() if clock.clock.'
                                           b'role == "windows-x64" else stream.verify()\n                c'
                                           b'ode = child.poll()\n                if code is not None:\n    '
                                           b'                row["exitCode"] = code\n',
                                           b'                    stream.observe_live_output() if clock.clock.'
                                           b'role == "windows-x64" else stream.verify()\n                c'
                                           b'ode = child.poll()\n                try:\n                    '
                                           b'_tail_cost_event(cost, "POST_POLL_CLOCK", code)\n            '
                                           b'    except BaseException:\n                    cost = None\n  '
                                           b'              if code is not None:\n                    row["'
                                           b'exitCode"] = code\n'),
                                          (b'                    require(type(code) is int and code == 0 and '
                                           b'not scope.discover(), "NATIVE_CHILD_OR_DESCENDANT_FAILED")\n '
                                           b'                   break\n                scope.discover()\n  '
                                           b'              native.time.sleep(.025)\n        except BaseExc'
                                           b'eption as error:\n            owner.error("k-native", error)\n'
                                           b'        finally:\n',
                                           b'                    require(type(code) is int and code == 0 and '
                                           b'not scope.discover(), "NATIVE_CHILD_OR_DESCENDANT_FAILED")\n '
                                           b'                   break\n                try:\n              '
                                           b'      _tail_cost_event(cost, "DISCOVER_SLEEP")\n             '
                                           b'   except BaseException:\n                    cost = None\n   '
                                           b'             scope.discover()\n                native.time.sl'
                                           b'eep(.025)\n        except BaseException as error:\n           '
                                           b' try:\n                _tail_cost_event(cost, "FAILURE")\n    '
                                           b'        except BaseException:\n                cost = None\n  '
                                           b'          owner.error("k-native", error)\n        finally:\n'),
                                          (b'                        stream.verify()\n                    '
                                           b'    outcome["verified"] = True\n                    except Ba'
                                           b'seException as error:\n                        owner.error("k'
                                           b'-native-capture", error)\n',
                                           b'                        stream.verify()\n                    '
                                           b'    outcome["verified"] = True\n                        if na'
                                           b'me == "stderr" and owner_anchor.failure is not None:\n       '
                                           b'                     try:\n                                li'
                                           b'ne = _tail_child_diagnostic(diagnostic)\n                    '
                                           b'            if line is not None:\n                           '
                                           b'         print(line, file=sys.stderr)\n                      '
                                           b'      except BaseException:\n                                '
                                           b'pass  # No diagnostic fault skips original sink close or failure'
                                           b'.\n                    except BaseException as error:\n       '
                                           b'                 owner.error("k-native-capture", error)\n'),
                                          (b'                    original = next(resource for resource, _labe'
                                           b'l, actual, _a, _c in owner_anchor.rows if actual is stream)\n'
                                           b'                    outcome.update(closeAttempted=original["atte'
                                           b'mpted"], closed=original["closed"])\n            if row["laun'
                                           b'chAttempted"] and owner_anchor.failure is not None:\n        '
                                           b'        owner.error("k-native-child-return", owner_anchor.failur'
                                           b'e, unknown=True)\n',
                                           b'                    original = next(resource for resource, _labe'
                                           b'l, actual, _a, _c in owner_anchor.rows if actual is stream)\n'
                                           b'                    outcome.update(closeAttempted=original["atte'
                                           b'mpted"], closed=original["closed"])\n            try:\n       '
                                           b'         line = _tail_cost_line(cost, diagnostic)\n          '
                                           b'      if line is not None:\n                    print(line, f'
                                           b'ile=sys.stderr)\n            except BaseException:\n          '
                                           b'      pass  # First-failure cost DATA cannot replace native clea'
                                           b'nup/refusal.\n            if row["launchAttempted"] and owner'
                                           b'_anchor.failure is not None:\n                owner.error("k-'
                                           b'native-child-return", owner_anchor.failure, unknown=True)\n')]}


# Invert only the later reviewed cleanup-role layer; preserve all older suppliers.
_RETIREMENT_BASE_SHA256 = '9deae813fa1b7c4a853935ddb3e769692c8c6b80d7397a8f0ce20691c3eca8a7'
_RETIREMENT_INVERSES = [(b'    clock = parent.clock\n    retirement_role = clock.clock.role  # Original admitted role; cleanup must not reacquire a failed clock view.\n    inputs = _input_values(parent)\n', b'    clock = parent.clock\n    inputs = _input_values(parent)\n'), (b'native.preparer_identity(scope, retirement_role) ==\n                        row["preparerIdentity"], "NATIVE_DRAIN_IDENTITY")', b'native.preparer_identity(scope, clock.clock.role) ==\n                        row["preparerIdentity"], "NATIVE_DRAIN_IDENTITY")')]


def retirement_preimage(name, raw):
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
    if name == "run-hosted-initial-recipient-tail.py":
        raw = operational_budget_preimage(name, raw)
    for before, after in reversed(_SELECTED_FAILURE_DELTAS[name]):
        if raw.count(after) != 1:
            raise AssertionError("SELECTED_FAILURE_EXACT_CONTEXT")
        raw = raw.replace(after, before, 1)
    if hashlib.sha256(raw).hexdigest() != _SELECTED_FAILURE_BASELINES[name]:
        raise AssertionError("SELECTED_FAILURE_WHOLE_3CEA_PREIMAGE")
    return raw


def k_failure_preimage(name, raw):
    name = name.removeprefix("scripts/")
    if name not in _K_FAILURE_BASELINES:
        return raw
    if type(raw) is not bytes:
        raise AssertionError("K_FAILURE_PREIMAGE_BYTES")
    if hashlib.sha256(raw).hexdigest() == _K_FAILURE_BASELINES[name]:
        return raw  # Exact prior layer supplied by another historical inverse.
    raw = selected_failure_preimage(name, raw)
    raw = retirement_preimage(name, raw)
    # Exact reviewed guard-scheduling layer precedes this older diagnostic inverse.
    guard_deltas = {'run-hosted-initial-recipient-tail.py': [(b'        self._local(anchor, final)\n        self.current()\n        require(anchor.busy and anchor.failure is None and anchor.last == frontier, "CHILD_CLOCK_CHANGED")\n', b'        self._local(anchor, final)\n        require(anchor.busy and anchor.failure is None and anchor.last == frontier, "CHILD_CLOCK_CHANGED")\n'), (b'            clock.current()\n            owner.structural()\n            require(owner.owner.fence is clock and owner.failure is None and not owner.owner.unknown and owner.errors == [] and\n', b'            require(type(clock) is _ChildClock and type(owner) is C._PrimaryOwner, "CAPTURE_ORIGINAL_CLOCK_AND_OWNER")\n            clock_anchor = clock.current()\n            require(type(clock_anchor) is _ChildAnchor and clock_anchor.handle is clock and\n                _CHILD_CLOCKS.get(id(clock)) is clock_anchor, "CAPTURE_ORIGINAL_CLOCK_RETURN")\n            owner_anchor = owner._anchor()\n            owners = clock_anchor.owners\n            require(type(owners) is tuple and any(type(pair) is tuple and len(pair) == 2 and\n                pair[0] is owner and pair[1] is owner_anchor for pair in owners), "CAPTURE_OWNER_NOT_ATTACHED")\n            require(owner.owner.fence is clock and owner.failure is None and not owner.owner.unknown and owner.errors == [] and\n')]}
    if name in guard_deltas:
        for before, after in reversed(guard_deltas[name]):
            if raw.count(after) != 1:
                raise AssertionError("GUARD_SCHEDULING_EXACT_CONTEXT")
            raw = raw.replace(after, before, 1)
    for before, after in reversed(_K_FAILURE_DELTAS[name]):
        if raw.count(after) != 1:
            raise AssertionError("K_FAILURE_EXACT_DIAGNOSTIC_DELTA")
        raw = raw.replace(after, before, 1)
    if hashlib.sha256(raw).hexdigest() != _K_FAILURE_BASELINES[name]:
        raise AssertionError("K_FAILURE_WHOLE_3EAC_PREIMAGE")
    return raw


# Exact reviewed budget diagnostic inverse; actual imported code remains current.
_PRELAUNCH_BUDGET_BEFORE = 'def _prelaunch_budget(parent, caps):\n    parent.currency()\n    local = C.local_value(time.monotonic())\n    observed = parent.now(limit=caps[1])\n    remaining = min(parent.clock.local_end - local, (caps[1] - observed) / NS)\n    require(remaining > 60 + (30 if parent.clock.clock.role == "windows-x64" else 0),\n        "NATIVE_VALIDATION_FINISH_CANNOT_FIT")\n\n\n'
_PRELAUNCH_BUDGET_AFTER = 'def _prelaunch_budget_diagnostic(local_remaining, work_remaining, required):\n    """Failure-only relative DATA; cannot grant time or replace the refusal."""\n    try:\n        if type(required) is not int or required not in (60, 90) or not all(\n                type(value) in (int, float) and math.isfinite(value) and -900 <= value <= 900\n                for value in (local_remaining, work_remaining)):\n            return\n        record = {"schema": 1, "scope": "INITIAL_RECIPIENT_K_PRELAUNCH_BUDGET_V1",\n            "decision": "REJECTED", "localRemainingMs": math.floor(local_remaining * 1000),\n            "workRemainingMs": math.floor(work_remaining * 1000), "requiredSeconds": required}\n        raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)\n        if len(raw) <= 512:\n            print(raw, file=sys.stderr)\n    except BaseException:\n        pass  # No diagnostic error may replace the actual admission failure.\n\n\ndef _prelaunch_budget(parent, caps):\n    parent.currency()\n    local = C.local_value(time.monotonic())\n    observed = parent.now(limit=caps[1])\n    local_remaining = parent.clock.local_end - local\n    work_remaining = (caps[1] - observed) / NS\n    remaining = min(local_remaining, work_remaining)\n    required = 60 + (30 if parent.clock.clock.role == "windows-x64" else 0)\n    try:\n        require(remaining > required, "NATIVE_VALIDATION_FINISH_CANNOT_FIT")\n    except BaseException:\n        try:\n            _prelaunch_budget_diagnostic(local_remaining, work_remaining, required)\n        except BaseException:\n            pass  # Even a replaced diagnostic callback cannot mask the refusal.\n        raise\n\n\n'


def prelaunch_budget_preimage(source):
    source = k_failure_preimage("run-hosted-initial-recipient-tail.py", source.encode("utf-8")).decode("utf-8")
    if type(source) is not str or source.count(_PRELAUNCH_BUDGET_AFTER) != 1:
        raise AssertionError("PRELAUNCH_DIAGNOSTIC_EXACT_CONTEXT")
    restored = source.replace(_PRELAUNCH_BUDGET_AFTER, _PRELAUNCH_BUDGET_BEFORE, 1)
    if hashlib.sha256(restored.encode("utf-8")).hexdigest() != '3bace28dd4f714d21d6a95c04a2ee5f50a3e0465f72aeb46eb2c2b390bc5fd3b':
        raise AssertionError("PRELAUNCH_DIAGNOSTIC_WHOLE_PREIMAGE")
    return restored


def before_child_diagnostic_preimage(name, source):
    if type(source) is not str:
        raise AssertionError("BEFORE_CHILD_SOURCE_TEXT")
    if name == "scripts/run-hosted-initial-recipient-custody.py":
        return before_child_custody_preimage(source.encode("utf-8")).decode("utf-8")
    if name == "scripts/run-hosted-initial-recipient-tail.py":
        return prelaunch_budget_preimage(source)
    if name != "scripts/hosted_initial_recipient_before.py":
        raise AssertionError("BEFORE_CHILD_EXACT_SUPPLIER")
    source = first_catch_before_preimage(source.encode("utf-8")).decode("utf-8")
    begin = '_BEFORE_CHILD_FAILURE_SCOPE = "INITIAL_RECIPIENT_BEFORE_AUTHORITY_CHILD_FAILURE_SITES_V1"\n'
    end = "_ENTRY_LATCHES = {}\n"
    preceding = "def _tail_failure_clear():\n    global _TAIL_FAILURE\n    _TAIL_FAILURE = None\n\n\n"
    imports = "from __future__ import annotations\n\nimport json\nimport re\n"
    if source.count(begin) != 1 or source.count(end) != 1 or source.count(imports) != 1 or \
            source.count("import json\n") != 1:
        raise AssertionError("BEFORE_CHILD_CODEC_EXACT_CONTEXT")
    start, stop = source.index(begin), source.index(end)
    if not start < stop or source[max(0, start - len(preceding)):start] != preceding:
        raise AssertionError("BEFORE_CHILD_CODEC_ORIGINAL_POSITION")
    block = source[start:stop].encode("utf-8")
    if len(block) != 3214 or hashlib.sha256(block).hexdigest() != \
            "7f688e2df6ad6b5683f58a620468801111a11e0a8d6ce6a8cd8f82aea8acdde9":
        raise AssertionError("BEFORE_CHILD_CODEC_EXACT_ADDITION")
    original = (source[:start] + source[stop:]).replace(imports, imports.replace("import json\n", ""), 1)
    if hashlib.sha256(original.encode("utf-8")).hexdigest() != \
            "fe65346a83bd898b01b517c129ced41581152983c50858dd904587a1fd9a3afd":
        raise AssertionError("BEFORE_CHILD_CODEC_WHOLE_PREIMAGE")
    return original


# Exact reviewed failure-only insertions, not regenerated historical expectations.
TAIL_DIAGNOSTIC_INVERSES = {'scripts/hosted_initial_recipient_before.py': [['import re\n',
                                                 'import re\n'
                                                 'from pathlib import Path\n'
                                                 'from types import TracebackType\n'],
                                                ['_ENTRY_LATCHES = {}\n',
                                                 '# Failure DATA only; inactive outside the actual TAIL CLI '
                                                 'lifetime. No clock,\n'
                                                 '# owner, capability or traceback frame is retained in this '
                                                 'optional state.\n'
                                                 '_TAIL_FAILURE = None\n'
                                                 '_TAIL_FAILURE_PATHS = {\n'
                                                 '    str(Path(__file__).parent / name): token for name, token in '
                                                 '(\n'
                                                 '        ("run-hosted-initial-recipient-tail.py", "TAIL"),\n'
                                                 '        ("run-hosted-initial-recipient-custody.py", '
                                                 '"CUSTODY"),\n'
                                                 '        ("run-hosted-initial-recipient.py", "PRIMARY"),\n'
                                                 '        ("run-hosted-cache-bootstrap.py", "NATIVE"),\n'
                                                 '        ("hosted_test_query.py", "QUERY"),\n'
                                                 '        ("hosted_test_identity.py", "IDENTITY"),\n'
                                                 '        ("hosted_cache_bootstrap_origin.py", "ORIGIN"),\n'
                                                 '        ("hosted_cache_bootstrap_service_time.py", '
                                                 '"SERVICE_TIME"),\n'
                                                 '        ("hosted_initial_recipient_originals.py", '
                                                 '"ORIGINALS"),\n'
                                                 '        ("hosted_job_clock.py", "CLOCK"),\n'
                                                 '        ("hosted_initial_recipient_continuity.py", '
                                                 '"CONTINUITY"),\n'
                                                 '        ("hosted_initial_recipient_before.py", "BEFORE"),\n'
                                                 '        ("hosted_initial_recipient_tail_evidence.py", '
                                                 '"TAIL_EVIDENCE"),\n'
                                                 '        ("hosted_initial_recipient_tail_handoff.py", '
                                                 '"TAIL_HANDOFF"),\n'
                                                 '        ("hosted_initial_recipient_tail_carrier.py", '
                                                 '"TAIL_CARRIER"),\n'
                                                 '        ("hosted_initial_recipient_evidence.py", "EVIDENCE"))}\n'
                                                 '_TAIL_FAILURE_STAGES = ("ENTRY", "BEFORE_AUTHORITY", '
                                                 '"K_PARENT", "K_NATIVE", "K_CARRIER",\n'
                                                 '    "K_PENDING", "K_OUTPUT", "CHILD_ENTRY", "CHILD_WORK")\n'
                                                 '\n'
                                                 '\n'
                                                 'def _tail_failure_begin(operation, kind):\n'
                                                 '    global _TAIL_FAILURE\n'
                                                 '    try:\n'
                                                 '        if _TAIL_FAILURE is not None:\n'
                                                 '            _TAIL_FAILURE = None  # Reentry disables '
                                                 'observation, never resets authority.\n'
                                                 '            return\n'
                                                 '        if type(operation) is not str or type(kind) is not str '
                                                 'or not (\n'
                                                 '                operation == "before-and-tail" and kind in '
                                                 '("gate", "worker") or\n'
                                                 '                operation == "_tail-child" and kind == '
                                                 '"UNAVAILABLE"):\n'
                                                 '            return\n'
                                                 '        _TAIL_FAILURE = {"operation": operation, "kind": kind,\n'
                                                 '            "stage": "ENTRY" if operation == "before-and-tail" '
                                                 'else "CHILD_ENTRY",\n'
                                                 '            "selected": False, "error": None, "origin": None, '
                                                 '"sites": None, "truncated": None}\n'
                                                 '    except BaseException:\n'
                                                 '        _TAIL_FAILURE = None\n'
                                                 '\n'
                                                 '\n'
                                                 'def _tail_failure_stage(stage):\n'
                                                 '    try:\n'
                                                 '        state = _TAIL_FAILURE\n'
                                                 '        if type(state) is dict and state["selected"] is False '
                                                 'and type(stage) is str and \\\n'
                                                 '                stage in _TAIL_FAILURE_STAGES and (\n'
                                                 '                    state["operation"] == "before-and-tail" and '
                                                 'stage not in ("CHILD_ENTRY", "CHILD_WORK") or\n'
                                                 '                    state["operation"] == "_tail-child" and '
                                                 'stage in ("CHILD_ENTRY", "CHILD_WORK")):\n'
                                                 '            state["stage"] = stage\n'
                                                 '    except BaseException:\n'
                                                 '        pass\n'
                                                 '\n'
                                                 '\n'
                                                 'def _tail_failure_sites(head):\n'
                                                 '    sites, count, truncated = [], 0, False\n'
                                                 '    node = head if type(head) is TracebackType else None\n'
                                                 '    while node is not None and count < 32:\n'
                                                 '        filename, line = node.tb_frame.f_code.co_filename, '
                                                 'node.tb_lineno\n'
                                                 '        token = _TAIL_FAILURE_PATHS.get(filename)\n'
                                                 '        if token is not None and type(line) is int and 1 <= '
                                                 'line <= 1_000_000:\n'
                                                 '            if len(sites) == 12:\n'
                                                 '                del sites[0]\n'
                                                 '                truncated = True\n'
                                                 '            sites.append({"module": token, "line": line})\n'
                                                 '        node, count = node.tb_next, count + 1\n'
                                                 '    return sites, truncated or node is not None\n'
                                                 '\n'
                                                 '\n'
                                                 'def _tail_failure_remember(error, *, origin="FIRST_FAILURE"):\n'
                                                 '    try:\n'
                                                 '        state = _TAIL_FAILURE\n'
                                                 '        if type(state) is not dict or state["selected"] is not '
                                                 'False or not isinstance(error, BaseException) or \\\n'
                                                 '                type(origin) is not str or origin not in '
                                                 '("FIRST_FAILURE", "FINAL_CATCH"):\n'
                                                 '            return\n'
                                                 '        # Select FIRST, before descriptor/traversal can fail. '
                                                 'Cleanup must not\n'
                                                 '        # relabel a later error or stage as the original after '
                                                 'a diagnostic fault.\n'
                                                 '        state["selected"], state["error"], state["origin"] = '
                                                 'True, error, origin\n'
                                                 '        head = BaseException.__traceback__.__get__(error)\n'
                                                 '        sites, truncated = _tail_failure_sites(head)\n'
                                                 '        state["sites"], state["truncated"] = sites, truncated\n'
                                                 '    except BaseException:\n'
                                                 '        pass  # Optional observation cannot replace the chosen '
                                                 'product failure.\n'
                                                 '\n'
                                                 '\n'
                                                 'def _tail_failure_record(error, operation, kind):\n'
                                                 '    global _TAIL_FAILURE\n'
                                                 '    state, _TAIL_FAILURE = _TAIL_FAILURE, None\n'
                                                 '    try:\n'
                                                 '        if type(state) is not dict or state["selected"] is not '
                                                 'True or state["error"] is not error or \\\n'
                                                 '                type(operation) is not str or type(kind) is not '
                                                 'str or \\\n'
                                                 '                (state["operation"], state["kind"]) != '
                                                 '(operation, kind) or not (\n'
                                                 '                    operation == "before-and-tail" and kind in '
                                                 '("gate", "worker") or\n'
                                                 '                    operation == "_tail-child" and kind == '
                                                 '"UNAVAILABLE"):\n'
                                                 '            return None\n'
                                                 '        stage, origin, sites, truncated = (state[name] for name '
                                                 'in ("stage", "origin", "sites", "truncated"))\n'
                                                 '        if type(stage) is not str or stage not in '
                                                 '_TAIL_FAILURE_STAGES or \\\n'
                                                 '                (stage in ("CHILD_ENTRY", "CHILD_WORK")) != '
                                                 '(operation == "_tail-child") or \\\n'
                                                 '                type(origin) is not str or origin not in '
                                                 '("FIRST_FAILURE", "FINAL_CATCH") or \\\n'
                                                 '                type(sites) is not list or len(sites) > 12 or '
                                                 'type(truncated) is not bool:\n'
                                                 '            return None\n'
                                                 '        for row in sites:\n'
                                                 '            if type(row) is not dict or set(row) != {"module", '
                                                 '"line"} or \\\n'
                                                 '                    type(row["module"]) is not str or '
                                                 'row["module"] not in _TAIL_FAILURE_PATHS.values() or \\\n'
                                                 '                    type(row["line"]) is not int or not 1 <= '
                                                 'row["line"] <= 1_000_000:\n'
                                                 '                return None\n'
                                                 '        return {"schema": 1, "scope": '
                                                 '"INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",\n'
                                                 '            "operation": operation, "kind": kind, "stage": '
                                                 'stage, "origin": origin,\n'
                                                 '            "sites": sites, "truncated": truncated}\n'
                                                 '    except BaseException:\n'
                                                 '        return None\n'
                                                 '\n'
                                                 '\n'
                                                 'def _tail_failure_clear():\n'
                                                 '    global _TAIL_FAILURE\n'
                                                 '    _TAIL_FAILURE = None\n'
                                                 '\n'
                                                 '\n'
                                                 '_ENTRY_LATCHES = {}\n'],
                                                ['        failure = saved[4] if saved[4] is not None else error\n',
                                                 '        failure = saved[4] if saved[4] is not None else error\n'
                                                 '        try:\n'
                                                 '            _tail_failure_remember(failure)\n'
                                                 '        except BaseException:\n'
                                                 '            pass  # Failure DATA cannot alter the original '
                                                 'latch transition.\n']],
 'scripts/run-hosted-initial-recipient-custody.py': [['            anchor.failure = owner.original if '
                                                      'owner.original is not None else error\n',
                                                      '            anchor.failure = owner.original if '
                                                      'owner.original is not None else error\n'
                                                      '            try:\n'
                                                      '                B._tail_failure_remember(anchor.failure)\n'
                                                      '            except BaseException:\n'
                                                      '                pass  # TAIL failure DATA cannot replace '
                                                      'the original error.\n'],
                                                     ['            anchor.failure = error  # Only this actual '
                                                      'error callback establishes the first failure.\n',
                                                      '            anchor.failure = error  # Only this actual '
                                                      'error callback establishes the first failure.\n'
                                                      '            try:\n'
                                                      '                B._tail_failure_remember(anchor.failure)\n'
                                                      '            except BaseException:\n'
                                                      '                pass  # TAIL failure DATA precedes native '
                                                      'error/cleanup rethrows.\n']],
 'scripts/run-hosted-initial-recipient-tail.py': [['    def fail(self, error):\n'
                                                   '        anchor = self._anchor()\n'
                                                   '        if anchor.failure is None:\n'
                                                   '            anchor.failure = error\n'
                                                   '        return anchor.failure\n',
                                                   '    def fail(self, error):\n'
                                                   '        anchor = self._anchor()\n'
                                                   '        if anchor.failure is None:\n'
                                                   '            anchor.failure = error\n'
                                                   '            try:\n'
                                                   '                B._tail_failure_remember(anchor.failure)\n'
                                                   '            except BaseException:\n'
                                                   '                pass  # Preserve the original child clock '
                                                   'error and caps.\n'
                                                   '        return anchor.failure\n'],
                                                  ['        before = C.before_authority(kind, cancelled)\n',
                                                   '        try:\n'
                                                   '            B._tail_failure_stage("BEFORE_AUTHORITY")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Last-entered DATA only; no call or '
                                                   'success is inferred.\n'
                                                   '        before = C.before_authority(kind, cancelled)\n'],
                                                  ['        parent = _Parent(before, attempt, original)\n',
                                                   '        try:\n'
                                                   '            B._tail_failure_stage("K_PARENT")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Last-entered DATA only; no call or '
                                                   'success is inferred.\n'
                                                   '        parent = _Parent(before, attempt, original)\n'],
                                                  ['        returned = _native_tail(parent)\n',
                                                   '        try:\n'
                                                   '            B._tail_failure_stage("K_NATIVE")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Last-entered DATA only; no call or '
                                                   'success is inferred.\n'
                                                   '        returned = _native_tail(parent)\n'],
                                                  ['        carrier = _copy_carrier(parent, returned)\n',
                                                   '        try:\n'
                                                   '            B._tail_failure_stage("K_CARRIER")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Last-entered DATA only; no call or '
                                                   'success is inferred.\n'
                                                   '        carrier = _copy_carrier(parent, returned)\n'],
                                                  ['        pending = _retain_pending(carrier)\n',
                                                   '        try:\n'
                                                   '            B._tail_failure_stage("K_PENDING")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Last-entered DATA only; no call or '
                                                   'success is inferred.\n'
                                                   '        pending = _retain_pending(carrier)\n'],
                                                  ['        return _OutputFence(pending).append()\n',
                                                   '        try:\n'
                                                   '            B._tail_failure_stage("K_OUTPUT")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Last-entered DATA only; no call or '
                                                   'success is inferred.\n'
                                                   '        return _OutputFence(pending).append()\n'],
                                                  ['        return _child_work(clock, context_raw, start_raw, '
                                                   'raws, minimum, metadata_close, metadata_last)\n',
                                                   '        try:\n'
                                                   '            B._tail_failure_stage("CHILD_WORK")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Last-entered DATA only; no call or '
                                                   'success is inferred.\n'
                                                   '        return _child_work(clock, context_raw, start_raw, '
                                                   'raws, minimum, metadata_close, metadata_last)\n'],
                                                  ['    args = parser.parse_args()\n    try:\n',
                                                   '    args = parser.parse_args()\n'
                                                   '    try:\n'
                                                   '        try:\n'
                                                   '            B._tail_failure_begin(args.operation, args.kind '
                                                   'if args.operation == "before-and-tail" else "UNAVAILABLE")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # No diagnostic failure may change the '
                                                   'operational CLI.\n'],
                                                  ['    except BaseException:\n'
                                                   '        print("INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED", '
                                                   'file=sys.stderr)\n'
                                                   '        return 125\n',
                                                   '    except BaseException as error:\n'
                                                   '        print("INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED", '
                                                   'file=sys.stderr)\n'
                                                   '        try:\n'
                                                   '            B._tail_failure_remember(error, '
                                                   'origin="FINAL_CATCH")\n'
                                                   '            diagnostic = B._tail_failure_record(error, '
                                                   'args.operation,\n'
                                                   '                args.kind if args.operation == '
                                                   '"before-and-tail" else "UNAVAILABLE")\n'
                                                   '            if diagnostic is not None:\n'
                                                   '                raw = json.dumps(diagnostic, sort_keys=True, '
                                                   'separators=(",", ":"), ensure_ascii=True, allow_nan=False)\n'
                                                   '                if len(raw) <= 2048:\n'
                                                   '                    print(raw, file=sys.stderr)\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # Generic refusal/exit125 remains '
                                                   'authoritative if DATA is unavailable.\n'
                                                   '        return 125\n'
                                                   '    finally:\n'
                                                   '        try:\n'
                                                   '            B._tail_failure_clear()\n'
                                                   '        except BaseException:\n'
                                                   '            pass\n']]}
TAIL_DIAGNOSTIC_BASELINES = {'scripts/hosted_initial_recipient_before.py': '5d20b363dc08029f3e4e6204426d533c4a90d368073571216f92a15ceed39826',
 'scripts/run-hosted-initial-recipient-custody.py': '880438c2aac9875177f0957a7103f74ef7fd12123757c0a59a3fc6bcb36847dc',
 'scripts/run-hosted-initial-recipient-tail.py': 'b81a62d8644a2dd18e3842be1052b47dc9d5b38591fc4668aae4058b010f1b0a'}
TAIL_DIAGNOSTIC_SOURCES = {name: k_failure_preimage(name, (SCRIPTS.parent / name).read_bytes()).decode("utf-8")
    for name in TAIL_DIAGNOSTIC_INVERSES}


# Exact new-layer inverse precedes, never replaces, the retained diagnostic inverse.
TAIL_FINAL_CATCH_INVERSES = {'scripts/hosted_initial_recipient_before.py': [['def _tail_failure_clear():\n',
                                                 'def _tail_failure_final_catch(error, operation, '
                                                 'kind):\n'
                                                 '    # Separate, stateless DATA for the exception '
                                                 'actually caught by this CLI.\n'
                                                 '    # It cannot recover a rejected first memo or '
                                                 'establish the original cause.\n'
                                                 '    try:\n'
                                                 '        if not isinstance(error, BaseException) '
                                                 'or type(operation) is not str or type(kind) is '
                                                 'not str or not (\n'
                                                 '                operation == "before-and-tail" '
                                                 'and kind in ("gate", "worker") or\n'
                                                 '                operation == "_tail-child" and '
                                                 'kind == "UNAVAILABLE"):\n'
                                                 '            return None\n'
                                                 '        sites, truncated = '
                                                 '_tail_failure_sites(BaseException.__traceback__.__get__(error))\n'
                                                 '        if type(sites) is not list or len(sites) '
                                                 '> 12 or type(truncated) is not bool:\n'
                                                 '            return None\n'
                                                 '        for row in sites:\n'
                                                 '            if type(row) is not dict or set(row) '
                                                 '!= {"module", "line"} or \\\n'
                                                 '                    type(row["module"]) is not '
                                                 'str or row["module"] not in '
                                                 '_TAIL_FAILURE_PATHS.values() or \\\n'
                                                 '                    type(row["line"]) is not int '
                                                 'or not 1 <= row["line"] <= 1_000_000:\n'
                                                 '                return None\n'
                                                 '        return {"schema": 1, "scope": '
                                                 '"INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",\n'
                                                 '            "operation": operation, "kind": '
                                                 'kind, "stage": "UNAVAILABLE", "origin": '
                                                 '"FINAL_CATCH",\n'
                                                 '            "sites": sites, "truncated": '
                                                 'truncated}\n'
                                                 '    except BaseException:\n'
                                                 '        return None\n'
                                                 '\n'
                                                 '\n'
                                                 'def _tail_failure_clear():\n']],
 'scripts/run-hosted-initial-recipient-tail.py': [['        try:\n'
                                                   '            B._tail_failure_remember(error, '
                                                   'origin="FINAL_CATCH")\n'
                                                   '            diagnostic = '
                                                   'B._tail_failure_record(error, args.operation,\n'
                                                   '                args.kind if args.operation == '
                                                   '"before-and-tail" else "UNAVAILABLE")\n'
                                                   '            if diagnostic is not None:\n',
                                                   '        diagnostic = None\n'
                                                   '        try:\n'
                                                   '            B._tail_failure_remember(error, '
                                                   'origin="FINAL_CATCH")\n'
                                                   '            diagnostic = '
                                                   'B._tail_failure_record(error, args.operation,\n'
                                                   '                args.kind if args.operation == '
                                                   '"before-and-tail" else "UNAVAILABLE")\n'
                                                   '        except BaseException:\n'
                                                   '            pass  # An unavailable memo cannot '
                                                   'prevent separate actual-catch DATA.\n'
                                                   '        try:\n'
                                                   '            if diagnostic is None:\n'
                                                   '                diagnostic = '
                                                   'B._tail_failure_final_catch(error, '
                                                   'args.operation,\n'
                                                   '                    args.kind if '
                                                   'args.operation == "before-and-tail" else '
                                                   '"UNAVAILABLE")\n'
                                                   '            if diagnostic is not None:\n']]}
TAIL_FINAL_CATCH_BASELINES = {'scripts/hosted_initial_recipient_before.py': '458b32071912d1f29f58bd9de517b1861b67f70c507f3afa4133915f9dfcb618',
 'scripts/run-hosted-initial-recipient-tail.py': '374b1ddcd067d2a69dbf2e72f47ba8d3e3c571698028db90458a858eb1e87e8b'}


class KFailureInsertionControls(unittest.TestCase):
    def test_exact_whole_preimage_preserves_every_old_supplier_pin(self):
        for name, checksum in _K_FAILURE_BASELINES.items():
            raw = (SCRIPTS / name).read_bytes()
            self.assertEqual(hashlib.sha256(k_failure_preimage(name, raw)).hexdigest(), checksum)
            for changed in (raw + b"# unrelated edit\n", raw.replace(b"def _tail_", b"def _changed_tail_", 1)):
                with self.assertRaises(AssertionError):
                    k_failure_preimage(name, changed)
            if name == "run-hosted-initial-recipient-tail.py":
                for after, before in _RETIREMENT_INVERSES:
                    removed = raw.replace(after, b"", 1)
                    for changed in (removed, raw.replace(after, after * 2, 1), removed + after,
                                    raw.replace(after, before, 1), raw + b"\n"):
                        with self.assertRaises(AssertionError):
                            k_failure_preimage(name, changed)


class PrelaunchBudgetDiagnosticControls(unittest.TestCase):
    """Real guard, synthetic clocks/parent; no native launch or timing qualification."""

    def invoke(self, function, role, local_left, work_left, *, stream=None):
        events = []
        clock = SimpleNamespace(local_end=100.0 + local_left, clock=SimpleNamespace(role=role))
        caps = (NS, 500 * NS, 545 * NS)

        class Parent:
            def currency(self):
                events.append("currency")

            def now(self, **kwargs):
                events.append("now")
                if kwargs != {"limit": caps[1]}:
                    raise AssertionError("WRONG_SYNTHETIC_CAP")
                return caps[1] - round(work_left * NS)

            @property
            def clock(self):
                events.append("clock")
                return clock

        def local():
            events.append("monotonic")
            return 100.0

        stream = io.StringIO() if stream is None else stream
        error = None
        with patch.object(K.time, "monotonic", local), patch.object(K.sys, "stderr", stream):
            try:
                guarded(function, Parent(), caps)
            except BaseException as caught:
                error = caught
        return events, error, stream

    def test_actual_guard_matches_previous_decisions_and_observation_order(self):
        namespace = dict(vars(K))
        exec(compile(_PRELAUNCH_BUDGET_BEFORE, "<retained-prelaunch-function>", "exec"), namespace)
        previous = namespace["_prelaunch_budget"]
        for role, minimum in (("linux-x64", 60), ("macos-arm64", 60), ("windows-x64", 90)):
            for local_left, work_left in ((minimum, minimum + 1), (minimum + 1, minimum),
                    (minimum - 1, minimum + 1), (minimum + 1, minimum - 1),
                    (minimum + .001, minimum + .001)):
                with self.subTest(role=role, local=local_left, work=work_left):
                    old_events, old_error, old_out = self.invoke(previous, role, local_left, work_left)
                    events, error, out = self.invoke(K._prelaunch_budget, role, local_left, work_left)
                    self.assertEqual(events, old_events)
                    self.assertEqual(events, ["currency", "monotonic", "now", "clock", "clock"])
                    self.assertEqual(type(error), type(old_error))
                    self.assertEqual(str(error), str(old_error))
                    self.assertEqual(old_out.getvalue(), "")
                    if error is None:
                        self.assertEqual(out.getvalue(), "")
                    else:
                        self.assertIn("NATIVE_VALIDATION_FINISH_CANNOT_FIT", str(error))
                        record = json.loads(out.getvalue())
                        self.assertEqual(record["requiredSeconds"], minimum)
                        self.assertEqual(record["decision"], "REJECTED")
                        self.assertEqual(record["workRemainingMs"], round(work_left * 1000))

    def test_one_closed_bounded_record_and_floor_not_rounding(self):
        output = io.StringIO()
        with patch.object(K.sys, "stderr", output):
            guarded(K._prelaunch_budget_diagnostic, -0.0001, 59.9999, 60)
        raw = output.getvalue()
        self.assertTrue(raw.isascii())
        self.assertLessEqual(len(raw.rstrip("\n")), 512)
        self.assertEqual(len(raw.splitlines()), 1)
        record = {"schema": 1, "scope": "INITIAL_RECIPIENT_K_PRELAUNCH_BUDGET_V1",
            "decision": "REJECTED", "localRemainingMs": -1, "workRemainingMs": 59999,
            "requiredSeconds": 60}
        self.assertEqual(raw, json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    def test_invalid_diagnostic_data_is_omitted_not_stringified(self):
        for value in (True, None, "PRIVATE_SENTINEL", object(), float("nan"), float("inf"),
                -float("inf"), 900.001, -900.001):
            for dimension in (0, 1):
                args = [50.0, 50.0, 60]
                args[dimension] = value
                output = io.StringIO()
                with self.subTest(value=type(value).__name__, dimension=dimension), patch.object(
                        K.sys, "stderr", output):
                    self.assertIsNone(guarded(K._prelaunch_budget_diagnostic, *args))
                    self.assertEqual(output.getvalue(), "")
        for required in (True, 60.0, 61, 91, "PRIVATE_SENTINEL"):
            output = io.StringIO()
            with self.subTest(required=required), patch.object(K.sys, "stderr", output):
                guarded(K._prelaunch_budget_diagnostic, 50.0, 50.0, required)
                self.assertEqual(output.getvalue(), "")

    def test_output_or_diagnostic_failure_preserves_original_exception(self):
        original = RuntimeError("PRIVATE_ORIGINAL_EXCEPTION")

        class BrokenStream:
            def write(self, _value):
                raise OSError("PRIVATE_WRITE_EXCEPTION")

        with patch.object(K, "require", side_effect=original):
            _events, error, _stream = self.invoke(K._prelaunch_budget, "linux-x64", 59, 61,
                stream=BrokenStream())
            self.assertIs(error, original)
            with patch.object(K, "_prelaunch_budget_diagnostic", side_effect=RuntimeError("PRIVATE_CALLBACK")):
                _events, error, stream = self.invoke(K._prelaunch_budget, "linux-x64", 59, 61)
                self.assertIs(error, original)
                self.assertEqual(stream.getvalue(), "")

    def test_exact_inverse_rejects_missing_duplicate_moved_and_outside_edits(self):
        restored = guarded(prelaunch_budget_preimage, SOURCE)
        self.assertIn(_PRELAUNCH_BUDGET_BEFORE, restored)
        removed = SOURCE.replace(_PRELAUNCH_BUDGET_AFTER, "", 1)
        for changed in (removed, SOURCE.replace(_PRELAUNCH_BUDGET_AFTER, _PRELAUNCH_BUDGET_AFTER * 2, 1),
                removed + _PRELAUNCH_BUDGET_AFTER, SOURCE + "\n",
                SOURCE.replace('required not in (60, 90)', 'required not in (59, 90)', 1)):
            with self.assertRaises(AssertionError):
                guarded(prelaunch_budget_preimage, changed)


class RunnerDataRefusalControls(unittest.TestCase):
    def reject(self, function, *args, **kwargs):
        with self.assertRaises((ValueError, RuntimeError)):
            guarded(function, *args, **kwargs)

    def test_one_maintained_import_lineage_and_no_authority_was_acquired(self):
        self.assertIs(K.N, K.C.N)
        self.assertIs(K.native, K.C.native)
        self.assertIs(K.T.original, K.C.E)
        self.assertIs(K.H.B, K.C.B)
        self.assertEqual(K._ATTEMPTS, {})
        self.assertEqual(K.C._BEFORE_ATTEMPTS, {})
        self.assertEqual((len(K._PARENTS), len(K._CHILD_CLOCKS), len(K._NATIVE), len(K._CARRIERS), len(K._PENDING)),
            (0, 0, 0, 0, 0))

    def test_caps_are_original_tuple_data_for_each_role(self):
        full, clipped = (100 * NS, 700 * NS, 745 * NS), (400 * NS, 455 * NS, 500 * NS)
        for role in DOMAINS:
            self.assertIs(guarded(K._caps, seed(role, end=1000), full), full)
            self.assertIs(guarded(K._caps, seed(role), clipped), clipped)

    def test_caps_have_no_clock_boot_file_or_native_side_effect(self):
        with ExitStack() as stack:
            for module, names in ((K.O.clocks, ("observe", "checked_now")),
                    (K.continuity, ("boot_digest",)), (K.time, ("time", "monotonic"))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_CLOCK_SUPPLIER")))
            self.assertEqual(guarded(K._caps, seed(), (100 * NS, 455 * NS, 500 * NS)),
                (100 * NS, 455 * NS, 500 * NS))

    def test_caps_reject_list_boolean_float_zero_overflow_and_wrong_arity(self):
        for bad in ([100 * NS, 455 * NS, 500 * NS], (True, 455 * NS, 500 * NS),
                (100.0 * NS, 455 * NS, 500 * NS), (0, 210 * NS, 255 * NS),
                (2 ** 64, 2 ** 64 + NS, 2 ** 64 + 2 * NS), (100 * NS, 455 * NS)):
            self.reject(K._caps, seed(), bad)

    def test_caps_cannot_refresh_child_first_or_borrow_retirement_time(self):
        self.reject(K._caps, seed(end=1000), (100 * NS, 701 * NS, 746 * NS))
        self.reject(K._caps, seed(end=1000), (100 * NS, 310 * NS, 355 * NS))
        for bad in ((100 * NS, 311 * NS, 356 * NS), (100 * NS, 455 * NS, 356 * NS),
                (400 * NS, 456 * NS, 501 * NS), (455 * NS, 455 * NS, 500 * NS),
                (100 * NS, 300 * NS, 345 * NS)):
            self.reject(K._caps, seed(), bad)

    def test_caps_reject_noncanonical_or_mismatched_seed(self):
        for field, bad in (("initialSealEndNs", 500 * NS), ("initialSealEndNs", "0500000000000"),
                ("initialSealClockDomain", DOMAINS["macos-x64"]), ("initialSealBootSha256", "G" * 64),
                ("extra", "1")):
            supplied = seed()
            supplied[field] = bad
            self.reject(K._caps, supplied, (100 * NS, 455 * NS, 500 * NS))

    def test_posix_process_spelling_is_actual_spaced_json_not_compact(self):
        value = {"schema": 1, "waitExitCode": 0, "retired": True, "interruption": None}
        self.assertEqual(guarded(K._process_record, process(value)), value)
        self.reject(K._process_record, wire(value))
        self.reject(K._process_record, process(value).rstrip())

    def test_process_record_requires_known_success_and_no_invented_argv(self):
        for field, bad in (("schema", True), ("waitExitCode", False), ("waitExitCode", 1), ("waitExitCode", None),
                ("retired", 1), ("retired", False), ("interruption", "operation-interrupted"), ("argv", [])):
            value = {"schema": 1, "waitExitCode": 0, "retired": True, "interruption": None}
            value[field] = bad
            self.reject(K._process_record, process(value))

    def test_process_duplicate_extra_trailing_or_oversized_bytes_refuse(self):
        raw = process()
        for bad in (b'{"schema":1,' + raw[1:], raw + b"\n", b"{}\n", b"x" * (K.native.LIMIT + 1)):
            self.reject(K._process_record, bad)

    def test_encryption_status_data_has_one_begin_one_end_and_no_error(self):
        raw = b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n[GNUPG:] END_ENCRYPTION\n"
        self.assertIsNone(guarded(K._encryption_status, raw))
        for bad in (b"", raw + b"[GNUPG:] END_ENCRYPTION\n", raw + b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n",
                raw + b"[GNUPG:] FAILURE encrypt 1\n", raw + b"[GNUPG:] ERROR encrypt 1\n",
                b"x" * (K.T.posix.MAX_DIAGNOSTIC_BYTES + 1)):
            self.reject(K._encryption_status, bad)

    def test_snapshot_stamp_comparison_is_supplied_posix_data_only(self):
        stamp = [1, 21, stat.S_IFREG | 0o600, 1000, 1, 7, 30, 40]
        row = ("member-00000.bin", False, (1, 21), 7, wire({"posixStamp": stamp}))
        expected = {"device": 1, "inode": 21, "size": 7, "mtime_ns": 30, "ctime_ns": 40}
        for role in ("linux-x64", "macos-x64", "macos-arm64"):
            self.assertEqual(guarded(K._snapshot_file_data, row, role), expected)

    def test_snapshot_stamp_rejects_wrong_identity_size_links_kind_and_writable_mode(self):
        for index, bad in ((0, 2), (1, 22), (2, stat.S_IFDIR | 0o700), (2, stat.S_IFREG | 0o622),
                (3, -1), (4, 2), (4, True), (5, 8), (6, True)):
            stamp = [1, 21, stat.S_IFREG | 0o600, 1000, 1, 7, 30, 40]
            stamp[index] = bad
            row = ("member-00000.bin", False, (1, 21), 7, wire({"posixStamp": stamp}))
            self.reject(K._snapshot_file_data, row, "linux-x64")

    def test_snapshot_row_name_kind_count_and_shape_are_exact(self):
        original = ("member-00000.bin", False, (1, 21), 7,
            wire({"posixStamp": [1, 21, stat.S_IFREG | 0o600, 1000, 1, 7, 30, 40]}))
        for index, bad in ((0, "../member-00000.bin"), (1, 0), (2, [1, 21]), (3, True)):
            row = list(original)
            row[index] = bad
            self.reject(K._snapshot_file_data, tuple(row), "linux-x64")
        self.reject(K._snapshot_file_data, list(original), "linux-x64")

    def test_windows_snapshot_stamp_uses_full_private_metadata(self):
        value = {"identity": [1, "1" * 32], "is_directory": False, "size": 7, "links": 1,
            "attributes": 0x80, "creation_100ns": 10, "modified_100ns": 20, "change_100ns": 30,
            "owner_sid": "S-1-5-21-1", "protected_dacl": True}
        row = ("member-00000.bin", False, (1, "1" * 32), 7, wire(value))
        self.assertEqual(guarded(K._snapshot_file_data, row, "windows-x64"), value)
        value["protected_dacl"] = False
        self.reject(K._snapshot_file_data, (*row[:4], wire(value)), "windows-x64")

    def test_unregistered_parent_clock_capture_terminal_and_output_handles_refuse(self):
        for kind, method in ((K._Parent, "current"), (K._ChildClock, "current"), (K._Capture, "current"),
                (K._TerminalRead, "current"), (K._OutputFence, "append")):
            # An allocated Python shape is deliberately NOT a valid capability.
            value = object.__new__(kind)
            self.reject(getattr(value, method))

    def test_unregistered_file_native_carrier_freeze_and_pending_returns_refuse(self):
        self.reject(K._file_current, object.__new__(K._File))
        self.reject(K._checked_native, object(), object.__new__(K._NativeReturn))
        self.reject(K._checked_carrier, object.__new__(K._Carrier))
        self.reject(K._freeze_current, object.__new__(K._Freeze))
        self.reject(K._checked_pending, object.__new__(K._Pending))

    def test_nonowners_refuse_before_file_or_budget_callbacks(self):
        self.reject(K._open_file, object(), object(), "manifest.json", 65536)
        self.reject(K._closed_files, object())
        self.reject(K._budget, object())

    def test_seven_outputs_reject_bad_fields_or_seed_before_guard_or_io(self):
        def no_guard():
            raise AssertionError("OUTPUT_GUARD_SHOULD_NOT_HAVE_RUN")
        for change in ("missing", "extra", "hash", "clock", "integer", "old-shape"):
            value = {"initialBeforeSha256": "3" * 64, **seed()}
            if change == "missing":
                del value["initialSealBootSha256"]
            elif change == "extra":
                value["initialTailSha256"] = "4" * 64
            elif change == "hash":
                value["initialBeforeSha256"] = "G" * 64
            elif change == "clock":
                value["initialSealClockTicksPerSecond"] = "01"
            elif change == "integer":
                value["initialSealEndNs"] = 500 * NS
            else:
                value = seed()
            self.reject(K._append_seven, value, no_guard)

    def test_fixed_inputs_private_closes_and_output_names(self):
        self.assertEqual(set(K.INPUT_LIMITS), PRIVATE_INPUTS)
        expected = PRIVATE_INPUTS | {"context.json", "tail-child-result.json", "control-home", "temporary", "service"}
        self.assertEqual(K.PRIVATE_INPUT_NAMES, tuple(sorted(expected)))
        self.assertEqual(K.PRIVATE_CLOSED_NAMES, tuple(sorted(expected | {"carrier-close.json", "before-upload-pending.json"})))
        self.assertEqual({name for name, _environment, _flag in K.B.SEED_FIELDS}, SEED_FIELDS)
        self.assertEqual((K.H.OUTPUT, K.H.HASH_ENV, K.H.OUTCOME_ENV),
            ("initialBeforeSha256", "P2PKIT_INITIAL_BEFORE_SHA256", "P2PKIT_INITIAL_BEFORE_OUTCOME"))

    def test_new_custody_rosters_are_finite_and_require_output_before_upload(self):
        before = guarded(K._custody_names, tail_output=False)
        exported = guarded(K._custody_names, tail_output=True)
        carrier = guarded(K._custody_names, tail_output=True, upload=True)
        self.assertEqual(set(before) - set(K.C._before_roster(created=True)),
            {"tail-returned", "tail-public-crypto", "tail-copied-evidence"})
        self.assertEqual(set(exported) - set(before), {"tail-export-output"})
        self.assertEqual(set(carrier) - set(exported), {"upload-output"})
        self.reject(K._custody_names, tail_output=False, upload=True)
        self.reject(K._custody_names, tail_output=1)


class RunnerSourceTopologyControls(unittest.TestCase):
    def line(self, parent, name):
        found = calls(parent, name)
        self.assertTrue(found, name)
        return found[0].lineno

    def test_ast_exact_single_c_loader_and_shared_lineage(self):
        loaders = calls(TREE, "importlib.util.spec_from_file_location")
        self.assertEqual(len(loaders), 1)
        self.assertIn('"run-hosted-initial-recipient-custody.py"', text_of(loaders[0]))
        self.assertEqual(len(calls(TREE, "_spec.loader.exec_module")), 1)
        self.assertEqual(len(calls(TREE, "C.before_authority")), 1)

    def test_ast_parent_order_is_real_b_native_carrier_pending_complete_outputs(self):
        parent = node("before_and_tail")
        order = [self.line(parent, name) for name in ("C.before_authority", "_Parent", "_native_tail", "_copy_carrier",
            "_retain_pending", "original.complete", "_checked_pending", "_OutputFence(pending).append")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(calls(parent, "original.begin")), 1)

    def test_ast_no_reconstructed_b_recipient_or_admission_and_no_phase_widening(self):
        forbidden = {"C._BeforeAuthority", "C._BeforeClock", "C._TailClock", "T.posix.Recipient", "T.windows.Recipient",
            "C.O.Admission", "owner.enter_custody_phase", "owner.enter_crypto_phase", "owner.enter_before_phase",
            "clock.attach_file_owner", "object.__new__", "cache.export_snapshot", "cache.save_set"}
        self.assertFalse(forbidden.intersection(ast.unparse(item.func) for item in ast.walk(TREE) if isinstance(item, ast.Call)))
        for item in ast.walk(TREE):
            if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else [item.target]
                for target in targets:
                    self.assertFalse(isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and
                        target.value.id in {"C", "N", "native", "B", "continuity"})

    def test_ast_parent_checks_registry_and_failures_poison_original_b_and_k(self):
        current, failed = text_of(node("current", "_Parent")), text_of(node("fail", "_Parent"))
        self.assertIn("C._BEFORE_AUTHORITIES.get(id(before)) is original", current)
        self.assertIn("self._binding is saved[1]", current)
        self.assertIn("saved[1][1][18][0].fail(error)", failed)
        self.assertIn("saved[1][11].fail(original)", failed)
        self.assertEqual(len(calls(node("currency", "_Parent"), "C._before_currency")), 1)

    def test_ast_child_first_local_raw_boot_precedes_any_metadata_owner_or_reader(self):
        child = node("tail_child")
        order = [self.line(child, name) for name in ("time.monotonic", "O.clocks.observe", "continuity.boot_digest",
            "_ChildClock", "C._PrimaryOwner", "C._private", "_small")]
        self.assertEqual(order, sorted(order))
        self.assertLess(self.line(child, "owner.finish"), self.line(child, "clock.bind"))
        self.assertLess(self.line(child, "clock.bind"), self.line(child, "_child_work"))

    def test_ast_child_has_two_sequential_real_owners_not_a_restored_clock(self):
        attach = text_of(node("attach", "_ChildClock"))
        self.assertIn("len(anchor.owners) < 2", attach)
        self.assertIn("anchor.owners[0][0].finished", attach)
        self.assertIn("owner.owner.first is anchor.binding[0]", attach)
        self.assertEqual(len(calls(node("_child_work"), "C._PrimaryOwner")), 1)
        self.assertEqual(len(calls(node("_child_work"), "clock.attach")), 1)

    def test_ast_native_parent_uses_actual_owner_spawn_drain_known_close(self):
        parent = node("_native_tail")
        order = [self.line(parent, name) for name in ("C._CustodyOwner", "native.processes.make_scope", "scope.spawn",
            "scope.drain", "owner.freeze", "owner.close", "owner.known", "_NativeReturn")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(calls(parent, "scope.spawn")), 1)
        self.assertIn("owner.phase_originals = result", text_of(parent))
        self.assertIn('parent.now(final=True, limit=caps[2])', text_of(parent))

    def test_ast_no_native_context_or_owner_label_allowlist_changes(self):
        source = text_of(node("_native_tail"))
        self.assertNotIn("enter_", source)
        self.assertIn("clock.deadline(900, final=True, limit=caps[2])", source)
        self.assertIn('native._initializer_names(owner, root)', source)
        self.assertIn('C._before_roster(created=True)', source)

    def test_ast_new_validation_precedes_complete_capture_freeze_and_export(self):
        child = node("_child_work")
        validation_lines = [self.line(child, name) for name in ("T.windows.validate_recipient", "T.posix.validate_recipient")]
        capture_line = self.line(child, "_Capture")
        self.assertLess(max(validation_lines), capture_line)
        order = [self.line(child, name) for name in ("_validation_sources", "_existing_declarations", "_p0_diagnostics",
            "_freeze_tail", "T.export_encrypted", "_terminal_check", "owner.finish")]
        self.assertEqual(order, sorted(order))
        self.assertEqual(len(calls(TREE, "T.export_encrypted")), 1)

    def test_ast_exact_old_and_new_original_groups_not_whole_crypto_snapshot(self):
        self.assertEqual(K.T.GROUPS, ("RETURNED", "CRYPTO_SERVICE", "POST_EXPORT_AUTHORITY", "SEAL_AUTHORITY", "SEAL",
            "P0_EXPORT_DIAGNOSTICS", "P0_VALIDATION_MAP_REFERENCE", "BEFORE_AUTHORITY", "NEW_RECIPIENT_VALIDATION"))
        declared = text_of(node("_existing_declarations"))
        self.assertIn("C._historical_tail_authority_indexes", declared)
        self.assertIn("B.member_grammar(*query_ids)", declared)
        snap = text_of(node("_destination_snapshot"))
        self.assertIn("destination.snapshot", snap)
        self.assertIn("not owner.snapshots", snap)
        self.assertNotIn("work.snapshot", SOURCE)

    def test_ast_map_reservation_precedes_copy_and_map_is_not_recursive(self):
        freeze = node("_freeze_tail")
        source = text_of(freeze)
        self.assertIn("anchor.charged_bytes + copy_bytes + T.MAP_LIMIT <= T.posix.MAX_BYTES", source)
        self.assertLess(source.index("PRECOPY_SHARED_AND_MAP_RESERVATION"), source.index("destination.create_file"))
        self.assertIn('"mapSelfReference": "EXCLUDED_FROM_OWN_HASH_AND_TOTALS"', source)
        self.assertLess(self.line(freeze, "_write_bytes"), self.line(freeze, "_destination_snapshot"))
        self.assertIn("C.canonical(reader.raw) == observed == snapshotted[name]", source)

    def test_ast_reader_owns_directory_and_uses_real_eof_and_bounded_chunks(self):
        opened, streamed = text_of(node("_open_file")), text_of(node("_stream"))
        self.assertIn('label == "directory" and resource is directory', opened)
        self.assertIn("owner.owner.fence.deadline(900)", opened)
        self.assertIn("C.COPY_CHUNK", streamed)
        self.assertIn("value.reader.read(1)", streamed)
        self.assertIn("_file_current(value)", streamed)
        self.assertIn("owner.close_one(resource)", streamed)
        self.assertEqual(K.C.COPY_CHUNK, 64 * 1024)

    def test_ast_exclusive_writer_close_precedes_independent_readback(self):
        function = node("_write_bytes")
        order = [self.line(function, name) for name in ("directory.create_file", "writer.sync", "writer.verify",
            "owner.close_one", "_open_file", "_stream", "R.write_close_metadata")]
        self.assertEqual(order, sorted(order))

    def test_ast_carrier_is_after_native_close_and_pending_after_actual_carrier_close(self):
        copied = node("_copy_carrier")
        self.assertLess(self.line(copied, "_checked_native"), self.line(copied, "C._PrimaryOwner"))
        self.assertLess(self.line(copied, "H.carrier_bytes"), self.line(copied, "_open_file"))
        self.assertLess(self.line(copied, "owner.finish"), self.line(copied, "R.encode_close"))
        pending = node("_retain_pending")
        writes = calls(pending, "_write_bytes")
        self.assertEqual(len(writes), 2)
        self.assertEqual(ast.unparse(writes[0].args[2]), "H.PRIVATE_CARRIER_CLOSE")
        self.assertEqual(ast.unparse(writes[1].args[2]), "H.FILE")
        self.assertLess(writes[1].lineno, self.line(pending, "owner.finish"))

    def test_ast_pending_writer_never_attests_own_original_step(self):
        self.assertEqual(guarded(K._nonacceptance), {"originalStepOutcome": "NOT_OBSERVED", "upload": "NOT_PERFORMED",
            "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
            "exportSaveAuthority": False, "budgetAcceptance": "NOT_ADMITTED"})
        self.assertIn('"writerReturn": "PENDING_OWNER_CLOSE"', text_of(node("_retain_pending")))
        self.assertIn('"writerReturn": "PENDING_SEPARATE_RECORD_WRITER_CLOSE"', text_of(node("_copy_carrier")))
        self.assertIn('"NOT_USED_AS_QUALIFICATION_ORIGINALS"', text_of(node("_child_data")))

    def test_ast_seven_output_writer_is_distinct_with_sync_readback_close(self):
        self.assertEqual(calls(TREE, "continuity.append_outputs"), [])
        appended = node("_append_seven")
        order = [self.line(appended, name) for name in ("os.open", "os.write", "os.fsync", "os.read", "os.close")]
        self.assertEqual(order, sorted(order))
        self.assertIn('parent / "_runner_file_commands"', text_of(appended))
        self.assertIn("before.st_size == 0", text_of(appended))
        self.assertIn("continuity.QUARANTINE.append(descriptor)", text_of(appended))

    def test_ast_output_fence_requires_exactly_two_late_checks_and_poison_on_failure(self):
        source = text_of(node("now", "_OutputFence"))
        # Retrieve the genuine registry lineage before checking the mutable
        # visible binding, so even a late replacement reaches original B/K.
        self.assertNotIn("self._binding", text_of(node("_anchor", "_OutputFence")))
        begun = text_of(node("_begin", "_OutputFence"))
        self.assertLess(begun.index("try:"), begun.index("self._binding is saved[1]"))
        self.assertIn("raise self._fail(saved, error)", begun)
        self.assertIn('0 <= saved[2]["checks"] < 2', source)
        self.assertIn('saved[2]["checks"] += 1', source)
        self.assertIn("final is True", source)
        self.assertIn("raise self._fail(saved, error)", source)
        self.assertEqual(len(calls(node("main"), "native.guarded")), 2)

    def test_ast_cli_is_fixed_isolated_and_has_no_activation_or_productive_entry(self):
        main = text_of(node("main"))
        self.assertIn('"before-and-tail"', main)
        self.assertIn('"_tail-child"', main)
        self.assertIn("allow_abbrev=False", main)
        self.assertIn("sys.flags.isolated == 1 and sys.flags.no_site == 1", main)
        self.assertIn("sys.argv[1:] == _command(args.context_sha256, seed, caps, minimum)[5:]", main)
        self.assertNotIn("workflow_dispatch", main)
        self.assertNotIn("prepare-save", main)


class TailFailureDiagnosticControls(unittest.TestCase):
    """Failure DATA only; supplied anchors/CLI work are NOT admitted B/K owners."""

    def setUp(self):
        K.B._tail_failure_clear()
        self.addCleanup(K.B._tail_failure_clear)

    def begin(self, operation="before-and-tail", kind="gate"):
        guarded(K.B._tail_failure_begin, operation, kind)

    def record(self, error, operation="before-and-tail", kind="gate"):
        return guarded(K.B._tail_failure_record, error, operation, kind)

    def original_error(self):
        try:
            guarded(K.require, False, "DIAGNOSTIC_CONTROL")
        except BaseException as error:
            return error
        self.fail("control must raise")

    def trace(self, filename, lines):
        # Actual Python traceback nodes, compiled with a supplied PUBLIC code
        # filename. No supplier file is opened or claimed to have executed.
        try:
            exec(compile("raise RuntimeError()\n", filename, "exec"), {})
        except RuntimeError as error:
            last = BaseException.__traceback__.__get__(error)
            while last.tb_next is not None:
                last = last.tb_next
        head = None
        for line in reversed(lines):
            head = TracebackType(head, last.tb_frame, last.tb_lasti, line)
        return head

    def cli(self, operation, action, kind="gate"):
        argv = [str(PATH), operation]
        command = None
        if operation == "before-and-tail":
            argv.extend(("--kind", kind))
        else:
            argv.extend(("--context-sha256", "3" * 64, "--minimum-ns", "100000000000"))
            value = seed()
            for name, _environment, flag in K.B.SEED_FIELDS:
                argv.extend((flag, value[name]))
            for (_name, flag), value in zip(K.CAP_FIELDS, (100 * NS, 455 * NS, 500 * NS)):
                argv.extend((flag, str(value)))
            # Supplied executable spelling only; real decimal/cap/argv
            # predicates still run, and no filesystem command lookup is made.
            command = ["supplied-python", "-I", "-B", "-S", str(PATH), *argv[1:]]
        stdout, stderr = io.StringIO(), io.StringIO()
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "argv", argv))
            stack.enter_context(patch.object(sys, "stdout", stdout))
            stack.enter_context(patch.object(sys, "stderr", stderr))
            stack.enter_context(patch.object(K.native, "guarded", action))
            if command is not None:
                stack.enter_context(patch.object(K, "_command", return_value=command))
            code = guarded(K.main)
        return code, stdout.getvalue(), stderr.getvalue()

    def refusal(self, error, stage=None, first=False):
        def supplied_work(_callback):
            if stage is not None:
                guarded(K.B._tail_failure_stage, stage)
            if first:
                guarded(K.B._tail_failure_remember, error)
            raise error
        return supplied_work

    def test_closed_schema_exact_public_paths_and_line_bounds(self):
        self.assertEqual(len(K.B._TAIL_FAILURE_PATHS), 16)
        for filename, token in K.B._TAIL_FAILURE_PATHS.items():
            with self.subTest(token=token):
                sites, truncated = guarded(K.B._tail_failure_sites, self.trace(filename, (1, 1_000_000)))
                self.assertEqual(sites, [{"module": token, "line": 1}, {"module": token, "line": 1_000_000}])
                self.assertFalse(truncated)
                self.assertEqual(guarded(K.B._tail_failure_sites, self.trace(filename, (0, 1_000_001))), ([], False))
                foreign = "/not-the-public-supplier/" + Path(filename).name
                self.assertEqual(guarded(K.B._tail_failure_sites, self.trace(foreign, (1,))), ([], False))
        error = self.original_error()
        self.begin()
        guarded(K.B._tail_failure_remember, error)
        value = self.record(error)
        self.assertEqual(set(value), {"schema", "scope", "operation", "kind", "stage", "origin", "sites", "truncated"})
        self.assertEqual((value["schema"], value["scope"], value["operation"], value["kind"], value["stage"], value["origin"]),
            (1, "INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1", "before-and-tail", "gate", "ENTRY", "FIRST_FAILURE"))
        self.assertIs(type(value["truncated"]), bool)
        self.assertTrue(value["sites"])
        self.assertLessEqual(len(wire(value)), 2048)
        self.assertNotIn(str(SCRIPTS), wire(value).decode("ascii"))
        self.assertIsNone(self.record(error))

    def test_32_frame_12_site_limits_and_truthful_truncation(self):
        filename = str(PATH)
        for count in (0, 1, 12, 13, 32, 33, 65):
            with self.subTest(count=count):
                value, truncated = guarded(K.B._tail_failure_sites, self.trace(filename, range(1, count + 1)))
                scanned = min(count, 32)
                self.assertEqual(value, [{"module": "TAIL", "line": line}
                    for line in range(max(1, scanned - 11), scanned + 1)])
                self.assertIs(truncated, count > 12)
        self.assertEqual(guarded(K.B._tail_failure_sites, self.trace("/private/foreign", range(1, 34))), ([], True))
        error = RuntimeError()
        BaseException.__traceback__.__set__(error, self.trace(filename, (1_000_000,) * 32))
        self.begin()
        guarded(K.B._tail_failure_remember, error)
        self.assertLessEqual(len(wire(self.record(error))), 2048)

    def test_private_exception_hooks_args_locals_and_chains_are_never_read(self):
        touched = []
        class Hostile(RuntimeError):
            def __getattribute__(self, name):
                if name in ("args", "__traceback__", "__cause__", "__context__", "__dict__"):
                    touched.append(name)
                    raise AssertionError("PRIVATE_HOOK")
                return super().__getattribute__(name)
            def __str__(self):
                touched.append("str")
                raise AssertionError("PRIVATE_HOOK")
            def __repr__(self):
                touched.append("repr")
                raise AssertionError("PRIVATE_HOOK")
            def __bool__(self):
                touched.append("bool")
                return False
        error = Hostile("private-secret-marker")
        error.__cause__ = RuntimeError("private-chain")
        BaseException.__traceback__.__set__(error, self.trace(str(PATH), (71,)))
        self.begin()
        guarded(K.B._tail_failure_remember, error)
        raw = wire(self.record(error))
        self.assertEqual(touched, [])
        for forbidden in (b"private", b"Hostile", b"args", b"cause", b"context", b"filename"):
            self.assertNotIn(forbidden, raw)

    def test_first_falsey_error_origin_survives_64_cleanup_rethrows(self):
        class Falsey(RuntimeError):
            def __bool__(self):
                return False
        original = self.original_error()
        error = Falsey()
        BaseException.__traceback__.__set__(error, BaseException.__traceback__.__get__(original))
        sites = guarded(K.B._tail_failure_sites, BaseException.__traceback__.__get__(error))[0]
        self.assertTrue(sites)
        with patch.object(K.B, "_ENTRY_LATCHES", {}):
            latch = K.B.EntryLatch({})
            self.begin()
            guarded(K.B._tail_failure_stage, "K_NATIVE")
            self.assertIs(guarded(latch.fail, error), error)
            for _ in range(64):
                try:
                    raise error
                except BaseException as caught:
                    self.assertIs(guarded(latch.fail, caught), error)
            guarded(K.B._tail_failure_stage, "K_OUTPUT")
            guarded(K.B._tail_failure_remember, error, origin="FINAL_CATCH")
            value = self.record(error)
        self.assertEqual(value["sites"], sites)
        self.assertEqual((value["stage"], value["origin"]), ("K_NATIVE", "FIRST_FAILURE"))
        self.assertFalse(value["truncated"])

    def test_later_cleanup_error_and_identity_mismatch_cannot_replace_origin(self):
        first, later = self.original_error(), RuntimeError()
        self.begin()
        guarded(K.B._tail_failure_stage, "BEFORE_AUTHORITY")
        guarded(K.B._tail_failure_remember, first)
        guarded(K.B._tail_failure_remember, later, origin="FINAL_CATCH")
        self.assertIs(K.B._TAIL_FAILURE["error"], first)
        self.assertIsNone(self.record(later))
        self.assertIsNone(self.record(first))
        for operation, kind in (("before-and-tail", "worker"), ("_tail-child", "UNAVAILABLE")):
            self.begin()
            guarded(K.B._tail_failure_remember, first)
            self.assertIsNone(self.record(first, operation, kind))
        self.begin()
        guarded(K.B._tail_failure_remember, first)
        guarded(K.B._tail_failure_remember, later)
        value = self.record(first)
        self.assertEqual(value["origin"], "FIRST_FAILURE")

    def test_four_original_error_recorders_preserve_first_error_and_call_order(self):
        # Deliberately supplied anchors: invoke REAL methods but do not claim
        # an owned resource, successful check/close or admission of a fake owner.
        for role in ("entry", "primary", "custody", "child"):
            with self.subTest(role=role), ExitStack() as stack:
                K.B._tail_failure_clear()
                first, later, events = self.original_error(), RuntimeError(), []
                remember = K.B._tail_failure_remember
                def capture(error, **kwargs):
                    events.append("diagnostic")
                    return remember(error, **kwargs)
                stack.enter_context(patch.object(K.B, "_tail_failure_remember", capture))
                stack.enter_context(patch.object(K.B, "_ENTRY_LATCHES", {}))
                stack.enter_context(patch.object(K.native, "_custody_progress_failure", lambda error: events.append("old-progress")))
                self.begin()
                if role == "entry":
                    handle = K.B.EntryLatch({})
                    call = handle.fail
                elif role == "primary":
                    owner = SimpleNamespace(original=None, unknown=False,
                        error=lambda *args, **kwargs: events.append("native-error"))
                    anchor = SimpleNamespace(binding=(owner,), failure=None)
                    handle = SimpleNamespace(_anchor=lambda: anchor)
                    call = lambda error: K.C._PrimaryOwner.remember(handle, error)
                elif role == "custody":
                    handle = SimpleNamespace(unknown=False)
                    anchor = SimpleNamespace(binding=(None,) * 5 + ([],), failure=None, unknown=False,
                        dictionary=handle.__dict__)
                    handle._anchor = lambda: anchor
                    stack.enter_context(patch.object(K.native.Owner, "error",
                        lambda *args, **kwargs: events.append("native-error")))
                    call = lambda error: K.C._CustodyOwner.error(handle, "control", error)
                else:
                    anchor = SimpleNamespace(failure=None)
                    handle = SimpleNamespace(_anchor=lambda: anchor)
                    call = lambda error: K._ChildClock.fail(handle, error)
                result = guarded(call, first)
                if role != "custody":
                    self.assertIs(result, first)
                self.assertEqual(events, {"entry": ["diagnostic"], "primary": ["diagnostic", "old-progress", "native-error"],
                    "custody": ["diagnostic", "native-error"], "child": ["diagnostic"]}[role])
                guarded(call, later)
                self.assertIs(K.B._TAIL_FAILURE["error"], first)
                if role != "entry":
                    self.assertIs(anchor.failure, first)
                self.assertEqual(self.record(first)["origin"], "FIRST_FAILURE")

    def test_inactive_success_and_completed_lifetimes_never_leak_records(self):
        error = self.original_error()
        guarded(K.B._tail_failure_stage, "K_NATIVE")
        guarded(K.B._tail_failure_remember, error)
        self.assertIsNone(K.B._TAIL_FAILURE)
        self.assertIsNone(self.record(error))
        for operation, kind in (("collect-export", "gate"), ("before-and-tail", "UNAVAILABLE"),
                ("_tail-child", "gate"), (None, "gate")):
            self.begin(operation, kind)
            self.assertIsNone(K.B._TAIL_FAILURE)
        self.begin()
        self.assertIsNone(self.record(error))  # no failure in this lifetime
        self.begin()
        guarded(K.B._tail_failure_remember, error)
        guarded(K.B._tail_failure_clear)
        self.assertIsNone(self.record(error))
        self.begin()
        self.begin()  # reentry disables the diagnostic, not a latch reset
        self.assertIsNone(K.B._TAIL_FAILURE)
        self.begin("_tail-child", "UNAVAILABLE")
        guarded(K.B._tail_failure_remember, error)
        value = self.record(error, "_tail-child", "UNAVAILABLE")
        self.assertEqual((value["kind"], value["stage"]), ("UNAVAILABLE", "CHILD_ENTRY"))
        self.assertIsNone(K.B._TAIL_FAILURE)

    def test_parent_child_stage_literals_freeze_at_first_failure(self):
        stages = ("ENTRY", "BEFORE_AUTHORITY", "K_PARENT", "K_NATIVE", "K_CARRIER", "K_PENDING", "K_OUTPUT", "CHILD_ENTRY", "CHILD_WORK")
        self.assertEqual(K.B._TAIL_FAILURE_STAGES, stages)
        error = self.original_error()
        for stage in stages:
            child = stage.startswith("CHILD_")
            operation, kind = ("_tail-child", "UNAVAILABLE") if child else ("before-and-tail", "worker")
            self.begin(operation, kind)
            guarded(K.B._tail_failure_stage, stage)
            guarded(K.B._tail_failure_stage, "K_NATIVE" if child else "CHILD_WORK")
            guarded(K.B._tail_failure_stage, "UNKNOWN")
            guarded(K.B._tail_failure_remember, error)
            guarded(K.B._tail_failure_stage, "CHILD_ENTRY" if child else "K_OUTPUT")
            value = self.record(error, operation, kind)
            self.assertEqual(value["stage"], stage)
            self.assertNotIn("nativeSuccess", value)

    def test_diagnostic_internal_failures_cannot_replace_original_refusal(self):
        first, later = self.original_error(), RuntimeError()
        self.begin()
        guarded(K.B._tail_failure_stage, "K_PARENT")
        with patch.object(K.B, "_tail_failure_sites", side_effect=RuntimeError("diagnostic")):
            guarded(K.B._tail_failure_remember, first)
        self.assertIs(K.B._TAIL_FAILURE["selected"], True)
        guarded(K.B._tail_failure_stage, "K_OUTPUT")
        guarded(K.B._tail_failure_remember, later, origin="FINAL_CATCH")
        self.assertIs(K.B._TAIL_FAILURE["error"], first)
        self.assertEqual((K.B._TAIL_FAILURE["stage"], K.B._TAIL_FAILURE["origin"]), ("K_PARENT", "FIRST_FAILURE"))
        self.assertIsNone(self.record(first))
        with patch.object(K.B, "_ENTRY_LATCHES", {}), patch.object(K.B, "_tail_failure_remember", side_effect=RuntimeError()):
            latch = K.B.EntryLatch({})
            self.assertIs(guarded(latch.fail, first), first)
            self.assertIs(guarded(latch.fail, later), first)
        for name in ("_tail_failure_begin", "_tail_failure_remember", "_tail_failure_record", "_tail_failure_clear"):
            K.B._tail_failure_clear()
            with patch.object(K.B, name, side_effect=RuntimeError("diagnostic")):
                code, out, err = self.cli("before-and-tail", self.refusal(first))
            self.assertEqual((code, out), (125, ""))
            self.assertEqual(err.splitlines()[0], "INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED")
        K.B._tail_failure_clear()
        with patch.object(K.json, "dumps", side_effect=RuntimeError("diagnostic")):
            self.assertEqual(self.cli("before-and-tail", self.refusal(first)),
                (125, "", "INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\n"))

    def test_parent_cli_keeps_generic_marker_exit125_and_one_safe_json(self):
        for kind in ("gate", "worker"):
            error = self.original_error()
            code, out, err = self.cli("before-and-tail", self.refusal(error, "K_NATIVE", True), kind)
            self.assertEqual((code, out), (125, ""))
            lines = err.splitlines()
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0], "INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED")
            value = json.loads(lines[1])
            self.assertEqual((value["kind"], value["stage"], value["origin"]), (kind, "K_NATIVE", "FIRST_FAILURE"))
            self.assertEqual(lines[1].encode("ascii") + b"\n", wire(value))
            self.assertLessEqual(len(lines[1]), 2048)
            self.assertIsNone(K.B._TAIL_FAILURE)
        for supplied in (None, {"oversize": "x" * 2049}):
            with patch.object(K.B, "_tail_failure_record", return_value=supplied), \
                    patch.object(K.B, "_tail_failure_final_catch", return_value=None):
                self.assertEqual(self.cli("before-and-tail", self.refusal(error)),
                    (125, "", "INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\n"))
        code, _out, err = self.cli("before-and-tail", self.refusal(error))
        self.assertEqual(code, 125)
        self.assertEqual(json.loads(err.splitlines()[1])["origin"], "FINAL_CATCH")

    def test_child_cli_is_distinct_and_does_not_claim_parent_or_native_success(self):
        error = self.original_error()
        code, out, err = self.cli("_tail-child", self.refusal(error, "CHILD_WORK", True))
        self.assertEqual((code, out), (125, ""))
        lines = err.splitlines()
        self.assertEqual(len(lines), 2)
        value = json.loads(lines[1])
        self.assertEqual((value["operation"], value["kind"], value["stage"], value["origin"]),
            ("_tail-child", "UNAVAILABLE", "CHILD_WORK", "FIRST_FAILURE"))
        self.assertEqual(set(value), {"schema", "scope", "operation", "kind", "stage", "origin", "sites", "truncated"})
        with patch.object(K.C, "digest", side_effect=error):
            code, out, err = self.cli("_tail-child", lambda _callback: self.fail("must not reach native boundary"))
        self.assertEqual((code, out), (125, ""))
        value = json.loads(err.splitlines()[1])
        self.assertEqual((value["stage"], value["kind"], value["origin"]), ("CHILD_ENTRY", "UNAVAILABLE", "FINAL_CATCH"))
        self.assertIsNone(K.B._TAIL_FAILURE)


    def test_first_catch_custody_inverse_preserves_0da3_and_rejects_unreviewed_changes(self):
        raw = TAIL_DIAGNOSTIC_SOURCES["scripts/run-hosted-initial-recipient-custody.py"].encode("utf-8")
        self.assertEqual(hashlib.sha256(guarded(before_raw_custody_preimage, raw)).hexdigest(),
            "e1ff9b12703f73598584b63f88fdcb14e2ae0286e76815def7592a612ce63f25")
        for before, after in _BEFORE_RAW_CUSTODY_INVERSES:
            removed = raw.replace(after, before, 1)
            invalid = (removed, raw.replace(after, after + after, 1), removed + after,
                raw.replace(after, after[:-1] + b" # changed exact context\n", 1),
                raw + b"# unrelated before-clock edit\n")
            for index, changed in enumerate(invalid):
                with self.subTest(beforeRawCase=index), self.assertRaises(AssertionError):
                    guarded(before_raw_custody_preimage, changed)
        restored_72be = guarded(immutable_input_custody_preimage, raw)
        self.assertEqual(hashlib.sha256(restored_72be).hexdigest(),
            "7dce9f3ca357518b6ee647fe3e5419ff383e8293f334ea790cab6e0657a9899b")
        self.assertNotEqual(raw, restored_72be)
        for before, after in _IMMUTABLE_INPUT_CUSTODY_INVERSES:
            removed = raw.replace(after, before, 1)
            invalid = (removed, raw.replace(after, after + after, 1), removed + after,
                raw.replace(after, after[:-1] + b" # changed exact context\n", 1),
                raw + b"# unrelated immutable-input edit\n")
            for index, changed in enumerate(invalid):
                with self.subTest(immutableInputCase=index), self.assertRaises(AssertionError):
                    guarded(immutable_input_custody_preimage, changed)
        for changed in (raw.replace(_EXPORT_PROCESS_CUSTODY_ROW, b"", 1),
                raw.replace(_EXPORT_PROCESS_CUSTODY_ROW, _EXPORT_PROCESS_CUSTODY_ROW * 2, 1),
                raw.replace(_EXPORT_PROCESS_CUSTODY_ROW, b"", 1) + _EXPORT_PROCESS_CUSTODY_ROW,
                raw.replace(b'"AUDIT_PROCESS"', b'"AUDIT_OTHER"', 1), raw + b"# unrelated\n"):
            with self.assertRaises(AssertionError):
                export_process_custody_preimage(changed)
        original = guarded(first_catch_custody_preimage, raw)
        self.assertEqual(hashlib.sha256(original).hexdigest(),
            "21ab23cf36d94f4d1c01c75a4c80750a41c224441b6c5b52370880a512a72cc0")
        self.assertNotEqual(raw, original)
        invalid = [raw + b"# unrelated source edit\n"]
        for before, after in _FIRST_CATCH_CUSTODY_INVERSES:
            removed = raw.replace(after, before, 1)
            invalid.extend((removed, raw.replace(after, after + after, 1), removed + after,
                raw.replace(after, after[:-1] + b" # mutated context\n", 1)))
        for index, changed in enumerate(invalid):
            with self.subTest(firstCatchCase=index), self.assertRaises(AssertionError):
                guarded(first_catch_custody_preimage, changed)

    def test_first_catch_before_inverse_preserves_0da3_and_rejects_unreviewed_changes(self):
        raw = TAIL_DIAGNOSTIC_SOURCES["scripts/hosted_initial_recipient_before.py"].encode("utf-8")
        restored = guarded(pending_step_before_preimage, raw)
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
            "7e453819e519251d65daeaf5b2b957bb5208edc7cddadf7bbc79b0a66122fc71")
        invalid_pending = [raw + b"# unrelated source edit\n"]
        for before, after in _PENDING_STEP_BEFORE_INVERSES:
            removed = raw.replace(after, before, 1)
            invalid_pending.extend((removed, raw.replace(after, after + after, 1), removed + after,
                raw.replace(after, after[:-1] + b" # mutated context\n", 1)))
        for index, changed in enumerate(invalid_pending):
            with self.subTest(pendingCase=index), self.assertRaises(AssertionError):
                guarded(pending_step_before_preimage, changed)
        original = guarded(first_catch_before_preimage, raw)
        self.assertEqual(hashlib.sha256(original).hexdigest(),
            "81cf980a9baf65290522754363a1c1d175cf6c0baf58af4ce8a9d9b5eeeec3fe")
        self.assertNotEqual(raw, original)
        invalid = [raw + b"# unrelated source edit\n"]
        for before, after in _FIRST_CATCH_BEFORE_INVERSES:
            removed = raw.replace(after, before, 1)
            invalid.extend((removed, raw.replace(after, after + after, 1), removed + after,
                raw.replace(after, after[:-1] + b" # mutated context\n", 1)))
        for index, changed in enumerate(invalid):
            with self.subTest(firstCatchCase=index), self.assertRaises(AssertionError):
                guarded(first_catch_before_preimage, changed)

    def test_before_child_outer_inverse_rejects_missing_moved_or_unrelated_edits(self):
        custody_name = "scripts/run-hosted-initial-recipient-custody.py"
        raw = TAIL_DIAGNOSTIC_SOURCES[custody_name].encode("utf-8")
        original = guarded(before_child_custody_preimage, raw)
        self.assertEqual(hashlib.sha256(original).hexdigest(),
            "ac193b29531566368882de33f1b7a8f238b8afd23c4d43dd9c4d008d27bc38ef")
        block = _BEFORE_CHILD_CUSTODY_ADDITION
        removed = raw.replace(block, b"", 1)
        invalid = (removed, raw.replace(block, block + block, 1), removed + block,
            raw.replace(block, block.replace(b"<= 2048", b"<= 2049"), 1), raw + b"\n")
        for index, changed in enumerate(invalid):
            with self.subTest(case=index), self.assertRaises(AssertionError) as caught:
                guarded(before_child_custody_preimage, changed)
            self.assertTrue(str(caught.exception).startswith("BEFORE_CHILD_CUSTODY_"))

        name = "scripts/hosted_initial_recipient_before.py"
        source = TAIL_DIAGNOSTIC_SOURCES[name]
        original = guarded(before_child_diagnostic_preimage, name, source)
        self.assertEqual(hashlib.sha256(original.encode("utf-8")).hexdigest(),
            "fe65346a83bd898b01b517c129ced41581152983c50858dd904587a1fd9a3afd")
        begin = source.index('_BEFORE_CHILD_FAILURE_SCOPE = ')
        end = source.index("_ENTRY_LATCHES = {}\n")
        block = source[begin:end]
        removed = source[:begin] + source[end:]
        invalid = (removed, source.replace(block, block + block, 1), removed + block,
            source.replace("BEFORE_CHILD_DUPLICATE_FIELD", "BEFORE_CHILD_CHANGED_FIELD", 1),
            source.replace("import json\n", "", 1), source.replace("import json\n", "import json\n" * 2, 1),
            source.replace("import json\n", "", 1) + "import json\n", source + "\n")
        for index, changed in enumerate(invalid):
            with self.subTest(codecCase=index), self.assertRaises(AssertionError) as caught:
                guarded(before_child_diagnostic_preimage, name, changed)
            self.assertTrue(str(caught.exception).startswith("BEFORE_CHILD_CODEC_"))
        self.assertIs(TAIL_DIAGNOSTIC_SOURCES[name], source)

    def test_unchanged_operational_ast_inverse_and_success_has_no_output(self):
        for name, replacements in TAIL_DIAGNOSTIC_INVERSES.items():
            source = before_child_diagnostic_preimage(name, TAIL_DIAGNOSTIC_SOURCES[name])
            if name == "scripts/run-hosted-initial-recipient-custody.py":
                # Undo only the reviewed first-error propagation before the
                # unchanged historical diagnostic source-preservation checks.
                original_clock = '            anchor.operative.check()\n            require(anchor.operative.original is None and not anchor.operative.unknown, "BEFORE_OPERATIVE_FAILED")\n'
                repaired_clock = '            anchor.operative.check()\n            if anchor.operative.original is not None:\n                raise anchor.operative.original\n            require(anchor.operative.original is None and not anchor.operative.unknown, "BEFORE_OPERATIVE_FAILED")\n'
                self.assertEqual(source.count(repaired_clock), 1)
                source = source.replace(repaired_clock, original_clock, 1)
                self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(),
                    "bcb0799c6621bfd7ec44160ac663313c69bd2797f96fe738699c458e8ed68796")
            for before, after in reversed(TAIL_FINAL_CATCH_INVERSES.get(name, ())):
                self.assertEqual(source.count(after), 1, name)
                source = source.replace(after, before, 1)
            for before, after in reversed(replacements):
                self.assertEqual(source.count(after), 1, name)
                source = source.replace(after, before, 1)
            self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(), TAIL_DIAGNOSTIC_BASELINES[name])
            ast.parse(source)  # syntax only; never import/execute the recovered original
        for operation in ("before-and-tail", "_tail-child"):
            self.assertEqual(self.cli(operation, lambda _callback: None), (0, "", ""))
            self.assertIsNone(K.B._TAIL_FAILURE)


    def test_final_catch_fallback_keeps_mismatched_first_memo_rejected(self):
        filename = str(SCRIPTS / "run-hosted-initial-recipient-tail.py")
        first, final = RuntimeError("first-not-output"), RuntimeError("final-not-output")
        BaseException.__traceback__.__set__(first, self.trace(filename, (11,)))
        BaseException.__traceback__.__set__(final, self.trace(filename, (22,)))
        self.begin()
        guarded(K.B._tail_failure_remember, first)
        self.assertIs(K.B._TAIL_FAILURE["error"], first)
        self.assertIsNone(self.record(final))  # Rejection/consumption must not be relaxed.
        self.assertIsNone(K.B._TAIL_FAILURE)
        selected = []
        def work(_callback):
            guarded(K.B._tail_failure_stage, "K_NATIVE")
            guarded(K.B._tail_failure_remember, first)
            selected.append(K.B._TAIL_FAILURE["error"])
            raise final
        code, out, err = self.cli("before-and-tail", work)
        self.assertEqual((code, out), (125, ""))
        self.assertEqual(selected, [first])
        self.assertEqual(err.splitlines()[0], "INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED")
        self.assertEqual(len(err.splitlines()), 2)
        value = json.loads(err.splitlines()[1])
        parent_calls = calls(node("main"), "native.guarded")
        self.assertEqual(len(parent_calls), 2)
        self.assertEqual((value["origin"], value["stage"], value["sites"]),
            ("FINAL_CATCH", "UNAVAILABLE", [
                {"module": "TAIL", "line": parent_calls[0].lineno}, {"module": "TAIL", "line": 22}]))
        self.assertNotIn({"module": "TAIL", "line": 11}, value["sites"])
        self.assertNotIn("not-output", err)
        self.assertIsNone(K.B._TAIL_FAILURE)
        # Even a sticky re-raise of the same error has no recovered-stage claim
        # when the actual memo accessor is unavailable.
        with patch.object(K.B, "_tail_failure_record", return_value=None):
            code, _, err = self.cli("before-and-tail", self.refusal(first, "K_NATIVE", True))
        self.assertEqual(code, 125)
        self.assertEqual((json.loads(err.splitlines()[1])["origin"], json.loads(err.splitlines()[1])["stage"]),
            ("FINAL_CATCH", "UNAVAILABLE"))

    def test_final_catch_fallback_survives_memo_diagnostic_faults(self):
        first = self.original_error()
        sites = K.B._tail_failure_sites
        calls_seen, selections = [], []
        def once_fault(head):
            calls_seen.append(head)
            if len(calls_seen) == 1:
                raise RuntimeError("optional-traversal")
            return sites(head)
        def work(_callback):
            guarded(K.B._tail_failure_stage, "K_PARENT")
            guarded(K.B._tail_failure_remember, first)
            guarded(K.B._tail_failure_stage, "K_OUTPUT")
            selections.append((K.B._TAIL_FAILURE["error"], K.B._TAIL_FAILURE["stage"],
                               K.B._TAIL_FAILURE["origin"], K.B._TAIL_FAILURE["selected"]))
            raise first
        with patch.object(K.B, "_tail_failure_sites", side_effect=once_fault):
            code, out, err = self.cli("before-and-tail", work)
        self.assertEqual(selections, [(first, "K_PARENT", "FIRST_FAILURE", True)])
        self.assertEqual(len(calls_seen), 2)
        self.assertEqual((code, out), (125, ""))
        self.assertEqual((json.loads(err.splitlines()[1])["stage"], json.loads(err.splitlines()[1])["origin"]),
            ("UNAVAILABLE", "FINAL_CATCH"))
        for name in ("_tail_failure_remember", "_tail_failure_record"):
            with self.subTest(helper=name), patch.object(K.B, name, side_effect=RuntimeError("memo-only")):
                code, out, err = self.cli("before-and-tail", self.refusal(first))
            self.assertEqual((code, out), (125, ""))
            self.assertEqual(len(err.splitlines()), 2)
            self.assertEqual(json.loads(err.splitlines()[1])["stage"], "UNAVAILABLE")
            self.assertIsNone(K.B._TAIL_FAILURE)

    def test_final_catch_fallback_preserves_valid_memo_precedence(self):
        for operation, kind, stage in (("before-and-tail", "gate", "K_NATIVE"),
                ("before-and-tail", "worker", "K_OUTPUT"), ("_tail-child", "UNAVAILABLE", "CHILD_WORK")):
            for remembered in (True, False):
                with self.subTest(operation=operation, kind=kind, remembered=remembered):
                    error = self.original_error()
                    with patch.object(K.B, "_tail_failure_final_catch", side_effect=AssertionError("must not call")) as fallback:
                        code, out, err = self.cli(operation, self.refusal(error, stage, remembered), kind)
                    fallback.assert_not_called()
                    value = json.loads(err.splitlines()[1])
                    self.assertEqual((code, out, len(err.splitlines())), (125, "", 2))
                    self.assertEqual((value["operation"], value["kind"], value["stage"], value["origin"]),
                        (operation, kind, stage, "FIRST_FAILURE" if remembered else "FINAL_CATCH"))
                    self.assertIsNone(K.B._TAIL_FAILURE)

    def test_final_catch_fallback_bounds_and_private_value_exclusion(self):
        class Hostile(RuntimeError):
            def __getattribute__(self, name):
                if name in ("__traceback__", "__cause__", "__context__", "args", "__class__"):
                    raise AssertionError("private attribute")
                return super().__getattribute__(name)
            def __str__(self):
                raise AssertionError("private str")
            def __repr__(self):
                raise AssertionError("private repr")
        error = Hostile("secret-not-output")
        self.begin()
        memo = K.B._TAIL_FAILURE
        for operation, kind in (("before-and-tail", "gate"), ("before-and-tail", "worker"), ("_tail-child", "UNAVAILABLE")):
            for filename, token in K.B._TAIL_FAILURE_PATHS.items():
                BaseException.__traceback__.__set__(error, self.trace(filename, (1, 1_000_000)))
                value = guarded(K.B._tail_failure_final_catch, error, operation, kind)
                self.assertEqual(value, {"schema": 1, "scope": "INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",
                    "operation": operation, "kind": kind, "stage": "UNAVAILABLE", "origin": "FINAL_CATCH",
                    "sites": [{"module": token, "line": 1}, {"module": token, "line": 1_000_000}], "truncated": False})
                self.assertLessEqual(len(wire(value).rstrip(b"\n")), 2048)
                self.assertTrue(wire(value).isascii())
                self.assertNotIn(b"secret", wire(value))
        for count, expected_lines, truncated in ((12, range(1, 13), False), (13, range(2, 14), True),
                (32, range(21, 33), True), (33, range(21, 33), True)):
            BaseException.__traceback__.__set__(error, self.trace(str(PATH), range(1, count + 1)))
            value = guarded(K.B._tail_failure_final_catch, error, "before-and-tail", "gate")
            self.assertEqual([r["line"] for r in value["sites"]], list(expected_lines))
            self.assertIs(value["truncated"], truncated)
        BaseException.__traceback__.__set__(error, self.trace("/private/foreign", (1,)))
        value = guarded(K.B._tail_failure_final_catch, error, "_tail-child", "UNAVAILABLE")
        self.assertEqual((value["sites"], value["truncated"]), ([], False))
        self.assertIs(K.B._TAIL_FAILURE, memo)
        self.assertIs(memo["selected"], False)
        for operation, kind in (("other", "gate"), ("before-and-tail", "UNAVAILABLE"), ("_tail-child", "gate"),
                (None, "gate"), ("before-and-tail", True)):
            self.assertIsNone(guarded(K.B._tail_failure_final_catch, error, operation, kind))
        self.assertIsNone(guarded(K.B._tail_failure_final_catch, object(), "before-and-tail", "gate"))
        for supplied in (((), False), ([], 0), ([{"module": "UNKNOWN", "line": 1}], False),
                ([{"module": "TAIL", "line": True}], False), ([{"module": "TAIL", "line": 0}], False),
                ([{"module": "TAIL", "line": 1_000_001}], False), ([{"module": "TAIL", "line": 1, "extra": 0}], False),
                ([{"module": "TAIL", "line": 1}] * 13, False)):
            with patch.object(K.B, "_tail_failure_sites", return_value=supplied):
                self.assertIsNone(guarded(K.B._tail_failure_final_catch, error, "before-and-tail", "gate"))

    def test_final_catch_fallback_faults_keep_generic_exit_and_cleanup(self):
        error = self.original_error()
        generic = (125, "", "INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\n")
        class FalseException:
            @property
            def __class__(self):
                return RuntimeError
        # Negative direct DATA call: isinstance may accept a supplied __class__,
        # but the real BaseException traceback descriptor rejects this receiver.
        self.assertIsNone(guarded(K.B._tail_failure_final_catch, FalseException(), "before-and-tail", "gate"))
        for mode in ("helper", "traversal", "serializer", "oversize"):
            with self.subTest(mode=mode), ExitStack() as stack:
                stack.enter_context(patch.object(K.B, "_tail_failure_record", return_value=None))
                if mode == "helper":
                    stack.enter_context(patch.object(K.B, "_tail_failure_final_catch", side_effect=RuntimeError()))
                elif mode == "traversal":
                    stack.enter_context(patch.object(K.B, "_tail_failure_sites", side_effect=RuntimeError()))
                elif mode == "serializer":
                    stack.enter_context(patch.object(K.json, "dumps", side_effect=RuntimeError()))
                else:
                    stack.enter_context(patch.object(K.B, "_tail_failure_final_catch", return_value={"oversize": "x" * 2049}))
                self.assertEqual(self.cli("before-and-tail", self.refusal(error)), generic)
            self.assertIsNone(K.B._TAIL_FAILURE)
        for operation in ("before-and-tail", "_tail-child"):
            with patch.object(K.B, "_tail_failure_final_catch", side_effect=AssertionError("success must not call")) as fallback:
                self.assertEqual(self.cli(operation, lambda _callback: None), (0, "", ""))
            fallback.assert_not_called()
            self.assertIsNone(K.B._TAIL_FAILURE)

    def test_final_catch_fallback_inverse_restores_exact_current_source(self):
        for name, replacements in TAIL_FINAL_CATCH_INVERSES.items():
            source = before_child_diagnostic_preimage(name, TAIL_DIAGNOSTIC_SOURCES[name])
            for before, after in reversed(replacements):
                self.assertEqual(source.count(after), 1, name)
                source = source.replace(after, before, 1)
            self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(), TAIL_FINAL_CATCH_BASELINES[name])
            original = ast.parse(source)
            comparison = TAIL_DIAGNOSTIC_SOURCES[name]
            if name.endswith("before.py"):
                comparison = guarded(pending_step_before_preimage, comparison.encode("utf-8")).decode("utf-8")
            current = ast.parse(comparison)
            if name.endswith("before.py"):
                old_functions = {n.name: ast.dump(n, include_attributes=False) for n in original.body if isinstance(n, ast.FunctionDef)}
                new_functions = {n.name: ast.dump(n, include_attributes=False) for n in current.body if isinstance(n, ast.FunctionDef)}
                self.assertEqual(set(new_functions) - set(old_functions), {"_tail_failure_final_catch",
                    "_before_child_failure_encode", "_before_child_failure_line", "_before_child_failure_projection",
                    "_before_child_failure_begin", "_before_child_failure_remember", "_before_child_failure_clear"})
                for function, body in old_functions.items():
                    self.assertEqual(new_functions[function], body)
        self.assertEqual(K.B._TAIL_FAILURE_STAGES,
            ("ENTRY", "BEFORE_AUTHORITY", "K_PARENT", "K_NATIVE", "K_CARRIER", "K_PENDING", "K_OUTPUT", "CHILD_ENTRY", "CHILD_WORK"))

    def operative_clock(self, original=None, *, unknown=False, parent=False, check_error=None):
        # Supplied DATA/anchors only: call the real _current/_view/_error, but
        # never construct or admit a native owner/clock, read time, or do I/O.
        # Upstream DATA and the operative check are supplied; their order and
        # later resources are observable. The real parent EntryLatch still runs.
        stack = ExitStack()
        self.addCleanup(stack.close)
        events, state = [], {"original": original}
        handle = SimpleNamespace()
        class SuppliedOperative:
            fence = handle
            def check(self):
                events.append("check")
                if check_error is not None:
                    raise check_error
            @property
            def original(self):
                events.append("original")
                return state["original"]
        owner = SuppliedOperative()
        owner.unknown = unknown
        entry = None
        if parent:
            stack.enter_context(patch.object(K.B, "_ENTRY_LATCHES", {}))
            attempts = {}
            latch = K.B.EntryLatch(attempts)
            attempt = guarded(latch.begin, attempts)
            entry = (latch, attempt)
            stack.enter_context(patch.object(K.C, "_BEFORE_ENTRY", latch))
            stack.enter_context(patch.object(K.C, "_BEFORE_ATTEMPTS", attempts))
            stack.enter_context(patch.object(K.C, "_before_actual", return_value=((), {})))
        binding = (None, None, None, None, "parent" if parent else "child", {}, (), None, None, entry)
        handle._binding = binding
        saved = object()
        later = SimpleNamespace(owner=SimpleNamespace(fence=handle, unknown=False), failure=None,
            _anchor=lambda: (events.append("file-anchor"), saved)[1],
            structural=lambda: events.append("file-structural"))
        anchor = SimpleNamespace(handle=handle, binding=binding, graph=(), frame_graph=(), bound_graph=(),
            metadata=None, bound=None, operative=owner, file_owners=(("supplied", later, saved),), failure=None)
        handle._anchor = lambda: anchor
        handle._current = lambda value: K.C._BeforeClock._current(handle, value)
        handle._error = K.C._BeforeClock._error
        stack.enter_context(patch.object(K.C, "_BEFORE_CLOCKS", {id(handle): anchor}))
        stack.enter_context(patch.object(K.C, "_CustodyOwner", SuppliedOperative))
        for module, name in ((K.C.native, "QUARANTINE"), (K.C.Q, "QUARANTINE"),
                (K.C.C, "QUARANTINE"), (K.C.native.diagnostics, "_QUARANTINE")):
            stack.enter_context(patch.object(module, name, False))
        return SimpleNamespace(handle=handle, anchor=anchor, owner=owner, events=events, state=state,
            entry=entry, current=lambda: guarded(K.C._BeforeClock._current, handle, anchor),
            view=lambda: guarded(K.C._BeforeClock._view, handle))

    def test_before_operative_healthy_check_precedes_original_and_remaining_resources(self):
        fixture = self.operative_clock()
        self.assertIsNone(fixture.current())
        self.assertEqual(fixture.events,
            ["check", "original", "original", "file-anchor", "file-structural"])
        self.assertIsNone(fixture.anchor.failure)
        self.assertIsNone(fixture.state["original"])
        self.assertIs(fixture.owner.unknown, False)

    def test_before_operative_ordinary_falsey_and_hostile_originals_keep_identity(self):
        hooks = []
        class Falsey(RuntimeError):
            def __bool__(self):
                hooks.append("falsey-bool")
                return False
        class Hostile(RuntimeError):
            def __bool__(self):
                hooks.append("hostile-bool")
                raise AssertionError("must not inspect bool")
            def __str__(self):
                hooks.append("str")
                raise AssertionError("must not inspect message")
            def __repr__(self):
                hooks.append("repr")
                raise AssertionError("must not inspect repr")
        for error in (RuntimeError(), Falsey(), Hostile()):
            with self.subTest(error_type=type(error).__name__):
                fixture = self.operative_clock(error)
                with self.assertRaises(type(error)) as caught:
                    fixture.current()
                self.assertIs(caught.exception, error)
                self.assertEqual(fixture.events, ["check", "original", "original"])
                self.assertIs(fixture.state["original"], error)
                self.assertIsNone(fixture.anchor.failure)  # _current itself does not latch/clear.
        self.assertEqual(hooks, [])

    def test_before_operative_parent_latch_preserves_first_and_prior_failure_precedence(self):
        for prior in (False, True):
            with self.subTest(prior=prior):
                K.B._tail_failure_clear()
                original, earlier, cleanup, acquisition = (RuntimeError() for _ in range(4))
                fixture = self.operative_clock(original, parent=True)
                latch, attempt = fixture.entry
                self.begin()
                guarded(K.B._tail_failure_stage, "K_NATIVE")
                if prior:
                    self.assertIs(guarded(latch.fail, earlier), earlier)
                with self.assertRaises(RuntimeError) as caught:
                    fixture.view()
                selected = earlier if prior else original
                self.assertIs(caught.exception, selected)
                self.assertIs(fixture.anchor.failure, selected)
                self.assertEqual(fixture.events, [] if prior else ["check", "original", "original"])
                self.assertIs(guarded(K.C._BeforeClock._error, fixture.anchor, cleanup), selected)
                self.assertIs(guarded(latch.fail, acquisition), selected)
                self.assertIs(attempt["failure"], selected)
                self.assertEqual(attempt["state"], "FAILED")
                self.assertIs(K.B._TAIL_FAILURE["error"], selected)
                value = self.record(selected)
                self.assertEqual((value["origin"], value["stage"]), ("FIRST_FAILURE", "K_NATIVE"))
                self.assertIsNone(self.record(cleanup))
                before = list(fixture.events)
                with self.assertRaises(RuntimeError) as repeated:
                    fixture.view()
                self.assertIs(repeated.exception, selected)
                self.assertEqual(fixture.events, before)

    def test_before_operative_unknown_without_original_still_refuses_unchanged(self):
        fixture = self.operative_clock(unknown=True)
        with self.assertRaisesRegex(Exception, "BEFORE_OPERATIVE_FAILED"):
            fixture.current()
        self.assertEqual(fixture.events, ["check", "original", "original"])
        self.assertIsNone(fixture.state["original"])
        self.assertIs(fixture.owner.unknown, True)
        self.assertIsNone(fixture.anchor.failure)

    def test_before_operative_earlier_binding_quarantine_and_check_failures_win(self):
        for mode in ("binding", "quarantine", "check"):
            with self.subTest(mode=mode):
                original, earlier = RuntimeError(), RuntimeError()
                fixture = self.operative_clock(original, check_error=earlier if mode == "check" else None)
                if mode == "binding":
                    fixture.handle._binding = ()
                    expected = "BEFORE_CLOCK_BINDING_CHANGED"
                elif mode == "quarantine":
                    expected = "BEFORE_CLOCK_UNKNOWN"
                with ExitStack() as stack:
                    if mode == "quarantine":
                        stack.enter_context(patch.object(K.C.native, "QUARANTINE", True))
                    if mode == "check":
                        with self.assertRaises(RuntimeError) as caught:
                            fixture.current()
                        self.assertIs(caught.exception, earlier)
                    else:
                        with self.assertRaisesRegex(Exception, expected):
                            fixture.current()
                self.assertEqual(fixture.events, ["check"] if mode == "check" else [])
                self.assertIs(fixture.state["original"], original)
                self.assertIsNone(fixture.anchor.failure)


if __name__ == "__main__":
    unittest.main()
