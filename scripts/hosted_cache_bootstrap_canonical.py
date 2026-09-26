"""Dormant source-bound canonical-init REQUEST; no initializer or phase caller.

This small adapter never imports the ordinary controller. It captures the pure
shared helper and canonical source bindings, then describes only the fixed init
argv for the current interpreter. Consistent returned bytes are NOT admission,
state ownership, a job allowance, recipient authority or successful execution.
A future live transaction must independently own and fence the actual operation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
# Separately reviewed source binding: never load this helper via a module cache,
# SourceFileLoader or ambient import path. It contains no non-stdlib imports.
_CANONICAL_HELPER_SHA256 = "432c06f0be8f98db286979b7adc58365d9eafde739c023ac13af1f227acaeba4"
_CANONICAL_HELPER_LIMIT = 32 * 1024


class CanonicalError(RuntimeError):
    """Finite source/request refusal, not native/provider or execution evidence."""


def require(value, code):
    if not value:
        raise CanonicalError(code)


def _canonical_source(name, maximum):
    """Read a closed source sibling, never cached bytecode or an ambient alias.

    This is bounded source-byte inspection, not native/source/host admission or
    an atomic filesystem snapshot. A failed close cannot publish helper code.
    """
    require(type(name) is str and name in ("hosted_canonical_python.py", "audit_processes.py", "run-audit-command.py") and
            type(maximum) is int and 0 < maximum <= 512 * 1024, "CANONICAL_HELPER_SOURCE")
    path = SCRIPTS / name
    require(path.is_absolute() and ".." not in path.parts, "CANONICAL_HELPER_SOURCE")
    ancestors = [(parent, parent.lstat()) for parent in path.parents]
    require(all(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
                for _, info in ancestors), "CANONICAL_HELPER_SOURCE")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            not getattr(before, "st_file_attributes", 0) & 0x400 and 0 < before.st_size <= maximum,
            "CANONICAL_HELPER_SOURCE")
    attributes = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns", "st_file_attributes")
    stamp = tuple(getattr(before, name, None) for name in attributes)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) |
                         getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    original, raw = None, b""
    try:
        opened = os.fstat(descriptor)
        require(tuple(getattr(opened, name, None) for name in attributes) == stamp, "CANONICAL_HELPER_SOURCE")
        while len(raw) <= maximum:
            block = os.read(descriptor, maximum + 1 - len(raw))
            if not block:
                break
            raw += block
        after = os.fstat(descriptor)
        require(tuple(getattr(after, name, None) for name in attributes) == stamp and
                len(raw) == before.st_size, "CANONICAL_HELPER_SOURCE")
    except BaseException as error:
        original = error
    try:
        os.close(descriptor)
    except BaseException as error:
        if original is not None:
            raise original from error
        raise
    if original is not None:
        raise original
    current = path.lstat()
    require(tuple(getattr(current, name, None) for name in attributes) == stamp, "CANONICAL_HELPER_SOURCE")
    for parent, previous in ancestors:
        current = parent.lstat()
        require(os.path.samestat(previous, current) and stat.S_ISDIR(current.st_mode) and
                not getattr(current, "st_file_attributes", 0) & 0x400, "CANONICAL_HELPER_SOURCE")
    return raw


def _load_canonical_helper():
    raw = _canonical_source("hosted_canonical_python.py", _CANONICAL_HELPER_LIMIT)
    require(hashlib.sha256(raw).hexdigest() == _CANONICAL_HELPER_SHA256, "CANONICAL_HELPER_SOURCE_BINDING")
    path = SCRIPTS / "hosted_canonical_python.py"
    namespace = {"__name__": "p2pkit_canonical_helpers", "__file__": str(path), "__package__": None}
    # Execute precisely the bounded bytes just compared to the caller's original
    # expected hash. No import cache, path mutation, loader hook or second read.
    exec(compile(raw, str(path), "exec", dont_inherit=True), namespace)
    return namespace


def _interpreter():
    require(type(sys.executable) is str and sys.executable, "BOOTSTRAP_CANONICAL_INTERPRETER")
    path = Path(sys.executable).resolve(strict=True)
    info = path.stat()
    require(path.is_absolute() and stat.S_ISREG(info.st_mode), "BOOTSTRAP_CANONICAL_INTERPRETER")
    return (sys.executable, str(path), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def init_request(*, state, expected_commit, role):
    """Return a private data-only descriptor; do not execute its argv here.

    Only the future source-owned caller may derive the original state path and
    admitted source/role. This function does not attest supplied inputs or that
    the proposed state is absent. It creates no directory, owner or process.
    """
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
            "BOOTSTRAP_CANONICAL_ISOLATION")
    require(type(expected_commit) is str and re.fullmatch(r"[0-9a-f]{40}", expected_commit) and
            type(role) is str and role in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64"),
            "BOOTSTRAP_CANONICAL_SOURCE_OR_ROLE")
    require(type(state) is str and 0 < len(state) <= 4096 and
            not any(ord(char) < 32 or ord(char) == 127 for char in state), "BOOTSTRAP_CANONICAL_STATE")
    target = Path(state)
    require(target.is_absolute() and ".." not in target.parts and str(target) == state and
            target != ROOT and target not in ROOT.parents and ROOT not in target.parents,
            "BOOTSTRAP_CANONICAL_STATE")
    interpreter = _interpreter()
    helper = _load_canonical_helper()
    originals = {name: _canonical_source(name, helper["CANONICAL_SOURCE_LIMIT"])
                 for name in helper["CANONICAL_NAMES"]}
    bindings = {name: hashlib.sha256(raw).hexdigest() for name, raw in originals.items()}
    bindings_json = json.dumps(bindings, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
    argv = helper["assemble"](interpreter[1], str(SCRIPTS), bindings_json,
                              "init", "--root", ROOT, "--state", target,
                              "--expected-commit", expected_commit, "--host", role)
    # Point-in-time rechecks, not a frozen filesystem or permission to execute.
    for name, raw in originals.items():
        require(_canonical_source(name, helper["CANONICAL_SOURCE_LIMIT"]) == raw,
                "BOOTSTRAP_CANONICAL_SOURCE_CHANGED")
    require(hashlib.sha256(_canonical_source("hosted_canonical_python.py", _CANONICAL_HELPER_LIMIT)).hexdigest() ==
            _CANONICAL_HELPER_SHA256 and _interpreter() == interpreter, "BOOTSTRAP_CANONICAL_BINDING_CHANGED")
    result = {"schema": 1, "scope": "BOOTSTRAP_CANONICAL_INIT_REQUEST_ONLY_V1", "root": str(ROOT),
              "state": state, "expectedCommit": expected_commit, "role": role, "python": interpreter[1],
              "helperSourceSha256": _CANONICAL_HELPER_SHA256, "canonicalSources": bindings, "argv": argv,
              "sourceAdmission": "NOT_ATTESTED_HERE", "stateOwnership": "NOT_ACQUIRED_OR_ATTESTED",
              "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
              "exportSaveAuthority": False}
    return (json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")
