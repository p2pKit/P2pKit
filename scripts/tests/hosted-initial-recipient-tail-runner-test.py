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


def seed(role="linux-x64"):
    return {"initialSealSha256": "1" * 64, "initialSealEndNs": str(500 * NS), "initialSealClockRole": role,
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
TAIL_DIAGNOSTIC_SOURCES = {name: (SCRIPTS.parent / name).read_text(encoding="utf-8")
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
        full, clipped = (100 * NS, 310 * NS, 355 * NS), (400 * NS, 455 * NS, 500 * NS)
        for role in DOMAINS:
            self.assertIs(guarded(K._caps, seed(role), full), full)
            self.assertIs(guarded(K._caps, seed(role), clipped), clipped)

    def test_caps_have_no_clock_boot_file_or_native_side_effect(self):
        with ExitStack() as stack:
            for module, names in ((K.O.clocks, ("observe", "checked_now")),
                    (K.continuity, ("boot_digest",)), (K.time, ("time", "monotonic"))):
                for name in names:
                    stack.enter_context(patch.object(module, name, side_effect=AssertionError("NO_CLOCK_SUPPLIER")))
            self.assertEqual(guarded(K._caps, seed(), (100 * NS, 310 * NS, 355 * NS)),
                (100 * NS, 310 * NS, 355 * NS))

    def test_caps_reject_list_boolean_float_zero_overflow_and_wrong_arity(self):
        for bad in ([100 * NS, 310 * NS, 355 * NS], (True, 310 * NS, 355 * NS),
                (100.0 * NS, 310 * NS, 355 * NS), (0, 210 * NS, 255 * NS),
                (2 ** 64, 2 ** 64 + NS, 2 ** 64 + 2 * NS), (100 * NS, 310 * NS)):
            self.reject(K._caps, seed(), bad)

    def test_caps_cannot_refresh_child_first_or_borrow_retirement_time(self):
        for bad in ((100 * NS, 311 * NS, 356 * NS), (100 * NS, 310 * NS, 356 * NS),
                (400 * NS, 456 * NS, 501 * NS), (455 * NS, 455 * NS, 500 * NS),
                (100 * NS, 300 * NS, 345 * NS)):
            self.reject(K._caps, seed(), bad)

    def test_caps_reject_noncanonical_or_mismatched_seed(self):
        for field, bad in (("initialSealEndNs", 500 * NS), ("initialSealEndNs", "0500000000000"),
                ("initialSealClockDomain", DOMAINS["macos-x64"]), ("initialSealBootSha256", "G" * 64),
                ("extra", "1")):
            supplied = seed()
            supplied[field] = bad
            self.reject(K._caps, supplied, (100 * NS, 310 * NS, 355 * NS))

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
            for (_name, flag), value in zip(K.CAP_FIELDS, (100 * NS, 310 * NS, 355 * NS)):
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

    def test_unchanged_operational_ast_inverse_and_success_has_no_output(self):
        for name, replacements in TAIL_DIAGNOSTIC_INVERSES.items():
            source = TAIL_DIAGNOSTIC_SOURCES[name]
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
            source = TAIL_DIAGNOSTIC_SOURCES[name]
            for before, after in reversed(replacements):
                self.assertEqual(source.count(after), 1, name)
                source = source.replace(after, before, 1)
            self.assertEqual(hashlib.sha256(source.encode("utf-8")).hexdigest(), TAIL_FINAL_CATCH_BASELINES[name])
            original = ast.parse(source)
            current = ast.parse(TAIL_DIAGNOSTIC_SOURCES[name])
            if name.endswith("before.py"):
                old_functions = {n.name: ast.dump(n, include_attributes=False) for n in original.body if isinstance(n, ast.FunctionDef)}
                new_functions = {n.name: ast.dump(n, include_attributes=False) for n in current.body if isinstance(n, ast.FunctionDef)}
                self.assertEqual(set(new_functions) - set(old_functions), {"_tail_failure_final_catch"})
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
