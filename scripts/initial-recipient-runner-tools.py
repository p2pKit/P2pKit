#!/usr/bin/env python3
"""Observe fixed native tool DATA; no admission, download or tool substitution."""
from __future__ import annotations

import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))
import hosted_initial_recipient_continuity as C

_WRITER = C._append_output_bytes
_FORBIDDEN = ("P2PKIT_ACTIONS_READ_TOKEN", "GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN")
_ATTRIBUTES = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns",
    "st_file_attributes")


def require(condition, code):
    C.require(condition, "RUNNER_TOOLS_" + code)


def _units(value):
    """Match JavaScript string.length, not Python's Unicode code-point count."""
    require(type(value) is str, "STRING")
    try:
        return len(value.encode("utf-16-le")) // 2
    except UnicodeError:
        raise C.ContinuityError("RUNNER_TOOLS_NON_NATIVE_STRING") from None


def _absolute(value, windows):
    """Recognize precisely native Node's absolute, already-normalized spelling.

    No path is normalized for emission. A single trailing separator is legal;
    double separators and . / .. components are not normalized spellings. UNC
    server/share is the root (not tail components) and needs its root separator.
    """
    require(type(windows) is bool and type(value) is str and 0 < _units(value) <= 4096 and
        not any(ord(char) < 32 or ord(char) == 127 for char in value), "ABSOLUTE_PATH")
    if not windows:
        require(value.startswith("/") and not value.startswith("//"), "POSIX_ROOT")
        tail, separator = value[1:], "/"
    else:
        require("/" not in value, "WINDOWS_NATIVE_SEPARATOR")
        separator = "\\"
        if value.startswith("\\\\"):
            root = value[2:].split("\\", 2)
            require(len(root) == 3 and root[0] and root[1], "WINDOWS_UNC_ROOT")
            tail = root[2]
        elif value.startswith("\\"):
            tail = value[1:]
        else:
            require(re.match(r"[A-Za-z]:\\", value) is not None, "WINDOWS_ABSOLUTE_DRIVE")
            tail = value[3:]
    if tail:
        components = tail.split(separator)
        if components[-1] == "":
            components = components[:-1]
        require(components and all(part not in ("", ".", "..") for part in components), "NORMALIZED_PATH")
    return value


def _values(executable, tool_path, windows):
    _absolute(executable, windows)
    basename = executable.rsplit("\\" if windows else "/", 1)[-1]
    require(re.fullmatch(r"python(?:3(?:\.[0-9]+)?)?(?:\.exe)?", basename) is not None, "PYTHON_BASENAME")
    require(type(tool_path) is str and 0 < _units(tool_path) <= 16384, "PATH_LENGTH")
    for entry in tool_path.split(";" if windows else ":"):
        _absolute(entry, windows)
    return (("python", executable), ("tool-path", tool_path))


def _encode(values):
    require(type(values) is tuple and len(values) == 2 and all(type(row) is tuple and len(row) == 2
        for row in values) and tuple(row[0] for row in values) == ("python", "tool-path"), "OUTPUT_FIELDS")
    _values(values[0][1], values[1][1], os.name == "nt")
    return "".join(name + "=" + value + "\n" for name, value in values).encode("utf-8")


def _metadata(executable):
    path = Path(executable)
    original = path.lstat()
    target = path.resolve(strict=True)
    current = target.stat()
    require(target.is_absolute() and stat.S_ISREG(current.st_mode) and os.access(target, os.X_OK), "ACTUAL_EXECUTABLE")
    return (str(target), tuple(getattr(original, name, None) for name in _ATTRIBUTES),
        tuple(getattr(current, name, None) for name in _ATTRIBUTES))


def observe():
    require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and
        sys.argv == [str(SCRIPTS / "initial-recipient-runner-tools.py")] and
        os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
        os.environ.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and
        (sys.platform, os.environ.get("RUNNER_OS")) in
            (("win32", "Windows"), ("linux", "Linux"), ("darwin", "macOS")), "ACTUAL_NATIVE_CALLER")
    executable, tool_path = sys.executable, os.environ.get("PATH")
    values = _values(executable, tool_path, os.name == "nt")
    metadata = _metadata(executable)  # May inspect a legitimate executable symlink; never emits its resolved spelling.

    def check():
        require(sys.executable == executable and os.environ.get("PATH") == tool_path and
            not any(name in os.environ for name in _FORBIDDEN) and C._append_output_bytes is _WRITER,
            "ACTUAL_TOOLS_OR_WRITER_CHANGED")
        require(_values(sys.executable, os.environ.get("PATH"), os.name == "nt") == values and
            _metadata(executable) == metadata, "ACTUAL_EXECUTABLE_CHANGED")

    check()
    _WRITER(_encode(values), check)
    check()


def main():
    try:
        observe()
        return 0
    except BaseException:
        # Never echo arbitrary environment, paths, rejected bytes or exception text.
        print("INITIAL_RECIPIENT_RUNNER_TOOLS_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
