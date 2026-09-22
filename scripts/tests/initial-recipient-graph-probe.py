#!/usr/bin/env python3
"""Two fixed offline-model cases, not a production or native execution entry.

Port of the retained R9 isolated guard. The existing fixture adapter and complete
1066/owner-close test are unchanged. The outer launcher supplies the original
per-invocation resource envelope and a fresh, network-isolated filesystem.
"""
import ctypes  # Only stdlib Python-API loader initialization precedes the guard.
import os
import resource
import sys

BASE = "/tmp/p2pkit-initial-graph-hosted"
SOURCE, HARNESS, WORK = BASE + "/source", BASE + "/harness", BASE + "/work"
PYLIB = "/lib/python" + str(sys.version_info.major) + "." + str(sys.version_info.minor)
READ = (SOURCE, HARNESS, WORK, sys.base_prefix + PYLIB)
DENIED = []

if not (os.geteuid() == os.getegid() == 65534 and os.getgroups() == [] and
        sys.version_info[:2] == (3, 12) and sys.flags.isolated == 1 and
        sys.flags.no_site == 1 and sys.flags.optimize == 0 and sys.dont_write_bytecode):
    raise RuntimeError("PROBE_INTERPRETER_OR_UID")
if dict(os.environ) != {"PATH": "/usr/bin:/bin", "HOME": WORK, "TMPDIR": WORK,
        "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}:
    raise RuntimeError("PROBE_CLOSED_ENVIRONMENT")
for name, limit in (("CPU", 20), ("AS", 536870912), ("FSIZE", 33554432),
        ("NOFILE", 128), ("CORE", 0)):
    if resource.getrlimit(getattr(resource, "RLIMIT_" + name)) != (limit, limit):
        raise RuntimeError("PROBE_RESOURCE_ENVELOPE")
if len(sys.argv) != 2 or sys.argv[1] not in ("prepare", "read"):
    raise RuntimeError("PROBE_FIXED_CASE_ONLY")
PHASE = sys.argv[1]


def within(value, root):
    return value == root or value.startswith(root + "/")


def checked_path(value, write=False):
    if isinstance(value, int):
        return  # Descriptors originate in the confined files or captured output.
    if value is None:
        value = os.getcwd()
    path = os.fsdecode(value)
    path = os.path.normpath(path if os.path.isabs(path) else os.path.join(os.getcwd(), path))
    allowed = (WORK,) if write else READ
    if not any(within(path, root) for root in allowed):
        DENIED.append(("filesystem-write" if write else "filesystem-read", path))
        raise RuntimeError("AUTHOR_FILESYSTEM_BOUNDARY")


_ORIGINAL_OPEN, _READLINK = os.open, os.readlink
_OPEN_CONTEXT = []
_ANCESTORS = {"/", "/tmp", BASE}


def scoped_open(path, flags, mode=0o777, *, dir_fd=None):
    name = os.fsdecode(path)
    anchor = os.getcwd() if dir_fd is None else _READLINK("/proc/self/fd/" + str(dir_fd))
    absolute = os.path.normpath(name if os.path.isabs(name) else os.path.join(anchor, name))
    _OPEN_CONTEXT.append((path, flags, absolute))
    try:
        return _ORIGINAL_OPEN(path, flags, mode, dir_fd=dir_fd)
    finally:
        _OPEN_CONTEXT.pop()


os.open = scoped_open


def offline(event, args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn",
            "ctypes.dlopen", "ctypes.dlsym", "ctypes.dlsym/handle", "os.startfile", "os.startfile/2"):
        DENIED.append((event, "prohibited-operation"))
        raise RuntimeError("AUTHOR_PROCESS_NETWORK_NATIVE_PROHIBITED")
    if event == "open":
        value, mode, flags = args
        write = (isinstance(mode, str) and any(x in mode for x in "wax+")) or (
            isinstance(flags, int) and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
        if (_OPEN_CONTEXT and _OPEN_CONTEXT[-1][0] == value and
                _OPEN_CONTEXT[-1][1] | os.O_CLOEXEC == flags):
            absolute = _OPEN_CONTEXT[-1][2]
            if not write and flags & os.O_DIRECTORY and flags & os.O_NOFOLLOW and absolute in _ANCESTORS:
                return  # Ancestor metadata pins only, not directory enumeration.
            checked_path(absolute, write)
        else:
            checked_path(value, write)
    elif event in ("os.listdir", "os.scandir"):
        checked_path(_READLINK("/proc/self/fd/" + str(args[0])) if isinstance(args[0], int) else args[0])
    elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.chown", "os.utime", "os.truncate", "os.chdir"):
        checked_path(args[0], True)
    elif event in ("os.rename", "os.link", "os.symlink"):
        checked_path(args[0], True)
        checked_path(args[1], True)


sys.addaudithook(offline)
# These deliberately dispatch audit events; they never perform the operations.
for event in ("subprocess.Popen", "socket.__new__", "ctypes.dlopen"):
    try:
        sys.audit(event, "SYNTHETIC_GUARD_CONTROL")
    except RuntimeError as error:
        assert str(error) == "AUTHOR_PROCESS_NETWORK_NATIVE_PROHIBITED"
    else:
        raise AssertionError("Guard failed closed-operation control")
try:
    checked_path(SOURCE + "/SYNTHETIC_FORBIDDEN_WRITE", True)
except RuntimeError as error:
    assert str(error) == "AUTHOR_FILESYSTEM_BOUNDARY"
else:
    raise AssertionError("Guard failed source-write control")
assert len(DENIED) == 4
CONTROL_DENIALS = len(DENIED)

import gc
import importlib.util
from pathlib import Path
import tempfile
import unittest
import warnings

os.chdir(WORK)
tempfile.tempdir = WORK


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


with warnings.catch_warnings(record=True) as observed_warnings:
    warnings.simplefilter("always", ResourceWarning)
    module = load("guarded_query_digest_subject",
        SOURCE + "/scripts/tests/hosted-initial-recipient-original-graph-test.py")
    load("retained_synthetic_graph", HARNESS + "/retained-fixture.py").install(module, Path(WORK), Path(SOURCE))
    name = {"prepare": "FixturePrepareModels.test_prepare_and_close_synthetic_graph",
        "read": "FixtureReaderModels.test_complete_fixed_graph_from_closed_synthetic_fixture"}[PHASE]
    class_name, method = name.split(".")
    cls = getattr(module, class_name)
    assert issubclass(cls, unittest.TestCase) and method in cls.__dict__
    suite = unittest.TestSuite((cls(method),))
    print("PROBE_PHASE=" + PHASE + " UID=65534 METHODS=1 CASE=" + name, flush=True)
    print("PROBE_PYTHON=" + sys.version.replace("\n", " ") + " EXECUTABLE=" + sys.executable, flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    assert result.testsRun == 1 and not result.skipped, "fixed case must actually execute"
    gc.collect()
    resources = [str(item.message) for item in observed_warnings if issubclass(item.category, ResourceWarning)]
print("AUTHOR_GUARD_SYNTHETIC_CONTROLS=4 UNEXPECTED_DENIALS=" + str(len(DENIED) - CONTROL_DENIALS))
print("AUTHOR_RESOURCE_WARNINGS=" + str(len(resources)))
for warning in resources:
    print("AUTHOR_RESOURCE_WARNING=" + warning)
for event, path in DENIED[CONTROL_DENIALS:]:
    print("AUTHOR_UNEXPECTED_GUARD_DENIAL=" + event + ":" + path)
assert len(DENIED) == CONTROL_DENIALS, "unexpected prohibited operation attempted"
assert not resources, "tiny fixture resources not closed"
sys.exit(0 if result.wasSuccessful() else 1)
