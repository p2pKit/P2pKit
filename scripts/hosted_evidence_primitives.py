"""Shared finite file/diagnostic primitives, never a custody or execution owner.

Importing this leaf performs no path setup, file operation or project import.
The custody backends reexport the same original objects and pin their supplier
slots before productive callbacks; consumers retain their own native owners.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import time


class EvidenceError(RuntimeError):
    """A public-safe failure; do not print raw exceptions or private GPG output."""


def _fail(message: str) -> None:
    raise EvidenceError(message)


def _deadline(end: float) -> None:
    if time.monotonic() >= end:
        _fail("Encrypted evidence operation exceeded its deadline")


def _path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        _fail("Evidence paths must be absolute and normalized")
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        try:
            info = current.lstat()
        except FileNotFoundError:
            if current != path:
                _fail("Evidence path parent is absent")
            break
        if stat.S_ISLNK(info.st_mode):
            _fail("Evidence paths cannot contain symbolic links")
    return path


def _private_directory(value: str | Path, *, empty: bool = False) -> Path:
    path = _path(value)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        _fail("Evidence directories must be exclusively owned mode-0700 directories")
    if empty and any(path.iterdir()):
        _fail("Evidence work directory must be new and empty")
    return path


def _identity(path: Path) -> tuple[int, int]:
    info = path.lstat()
    return info.st_dev, info.st_ino


def _exception_detail(error):
    """Finite, cycle/accessor-safe PRIVATE details; incomplete graphs mean UNKNOWN.

    Supplier notes and the process owner's explicit carrier are BOTH inspected.
    No assumption is made that ``str(error)`` includes notes or secondary errors.
    This is bounded diagnostic handling of cooperating code, not an execution
    sandbox for a malicious Python ``__str__``/property which never returns.
    """
    result = {"nodes": [], "incomplete": False, "retirementUnknown": False}
    remaining = 32 * 1024

    def incomplete():
        result["incomplete"] = result["retirementUnknown"] = True

    def text(value, limit=2048):
        nonlocal remaining
        if type(value) is not str:
            incomplete()
            return "<non-text diagnostic>"
        admitted = min(limit, remaining)
        if len(value) > admitted:
            incomplete()
        value = value[:admitted]
        remaining -= len(value)
        if "UNKNOWN" in value:
            result["retirementUnknown"] = True
        return value

    def attribute(value, name, default=None):
        try:
            return getattr(value, name, default)
        except BaseException:
            incomplete()
            return default

    pending, seen = [("original", error)], {}
    while pending:
        edge, current = pending.pop(0)
        if current is None:
            continue
        if not isinstance(current, BaseException):
            incomplete()
            continue
        if len(result["nodes"]) >= 64:
            incomplete()
            break
        if id(current) in seen:
            result["nodes"].append({"edge": edge, "reference": seen[id(current)]})
            continue
        index = len(result["nodes"])
        seen[id(current)] = index
        try:
            message = str(current)
        except BaseException:
            incomplete()
            message = "<exception message unavailable>"
        try:
            kind = type(current).__name__
        except BaseException:
            incomplete()
            kind = "<exception type unavailable>"
        row = {"edge": edge, "type": text(kind, 128), "message": text(message)}
        result["nodes"].append(row)
        notes = attribute(current, "__notes__", ())
        if type(notes) not in (list, tuple):
            incomplete()
        else:
            if len(notes) > 16:
                incomplete()
            row["notes"] = [text(note, 512) for note in notes[:16]]
        carrier = attribute(current, "_p2pkit_retirement")
        if carrier is not None:
            result["retirementUnknown"] = True
            if type(carrier) is not dict or len(carrier) != 3 or \
                    not all(type(key) is str for key in carrier) or \
                    set(carrier) != {"status", "resources", "omitted"} or \
                    carrier.get("status") != "UNKNOWN" or type(carrier.get("resources")) is not list or \
                    type(carrier.get("omitted")) is not int or carrier["omitted"] < 0:
                incomplete()
                row["retirement"] = "<uninspectable carrier>"
            else:
                resources = carrier["resources"]
                if len(resources) > 32 or carrier["omitted"]:
                    incomplete()
                row["retirement"] = []
                for resource in resources[:32]:
                    if type(resource) is not dict or len(resource) != 4 or \
                            not all(type(key) is str for key in resource) or \
                            set(resource) != {"phase", "resource", "status", "error"}:
                        incomplete()
                        row["retirement"].append({"error": "<uninspectable resource>"})
                    else:
                        row["retirement"].append({key: text(resource[key], 512)
                                                  for key in ("phase", "resource", "status", "error")})
        for name in ("__cause__", "__context__"):
            linked = attribute(current, name)
            if linked is not None:
                pending.append((f"{index}.{name}", linked))
        grouped = attribute(current, "exceptions", ())
        if type(grouped) not in (tuple, list):
            incomplete()
        else:
            if len(grouped) > 64:
                incomplete()
            pending.extend((f"{index}.group[{i}]", child) for i, child in enumerate(grouped[:64]))
        if len(pending) > 128:
            incomplete()
            pending = pending[:128]
    return result
