"""Fixed, dormant provider-worker/outer bootstrap; NOT a hosted admission entry.

Only fixed internal parents may select this script. Its source/tool and
pre-Node admission are separate, still missing prerequisites. No admitted
workflow calls it today. No credential belongs in its arguments or source map.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import types


SOURCE_LIMIT = 512 * 1024
# Dependency order, not caller-selected modules or an ambient import directory.
NAMES = (
    "audit_processes", "hosted_primary_abi", "hosted_test_identity",
    "hosted_cache_bootstrap_identity", "hosted_dependency_seed",
    "hosted_initial_recipient_exception", "hosted_initial_recipient_stages",
    "hosted_initial_recipient_bootstrap_identity", "hosted_windows_files",
    "hosted_dependency_seed_files", "hosted_dependency_cache",
    "hosted_lock_resources", "hosted_job_clock", "hosted_evidence",
    "hosted_test_query", "hosted_test_evidence", "hosted_windows_evidence",
    "hosted_cache_provider_environment", "hosted_cache_provider_lifecycle", "hosted_cache_provider_return",
    "hosted_cache_provider_worker", "hosted_cache_provider_launch",
)
OUTER_NAMES = ("hosted_cache_provider_supervisor_return", "hosted_cache_provider_supervisor",
               "hosted_cache_provider_entry")
STAMP = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns", "st_file_attributes")


def require(value):
    if not value:
        raise RuntimeError("PROVIDER_WORKER_SOURCE_REFUSED")


def names(role):
    require(type(role) is str and role in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64"))
    # The RAW Darwin reader imports Unix-only resource modules. Never preload
    # it on Windows; the non-Darwin clock path cannot select it.
    return tuple(name for name in NAMES if name != "hosted_lock_resources" or role.startswith("macos-"))


def outer_names(role):
    return names(role) + OUTER_NAMES


def read_source(directory, name):
    """Bounded original byte read, not installed-source/runner authentication."""
    require(type(name) is str and name in NAMES + OUTER_NAMES and isinstance(directory, Path) and directory.is_absolute())
    path = directory / (name + ".py")
    require(".." not in path.parts)
    ancestors = [(parent, parent.lstat()) for parent in path.parents]
    require(all(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
                for _, info in ancestors))
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            not getattr(before, "st_file_attributes", 0) & 0x400 and 0 < before.st_size <= SOURCE_LIMIT)
    stamp = tuple(getattr(before, key, None) for key in STAMP)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) |
                         getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    original, raw = None, b""
    try:
        opened = os.fstat(descriptor)
        require(tuple(getattr(opened, key, None) for key in STAMP) == stamp)
        while len(raw) <= SOURCE_LIMIT:
            part = os.read(descriptor, SOURCE_LIMIT + 1 - len(raw))
            if not part:
                break
            raw += part
        after = os.fstat(descriptor)
        require(len(raw) == before.st_size and tuple(getattr(after, key, None) for key in STAMP) == stamp)
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
    require(tuple(getattr(current, key, None) for key in STAMP) == stamp)
    for parent, prior in ancestors:
        current = parent.lstat()
        require(stat.S_ISDIR(current.st_mode) and not getattr(current, "st_file_attributes", 0) & 0x400 and
                os.path.samestat(prior, current))
    return raw


def record(raw):
    require(type(raw) is str and 0 < len(raw.encode("ascii")) <= 16 * 1024)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result)
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False))
    require(type(value) is dict)
    return value


def bootstrap():
    original_argv, argv = sys.argv, tuple(sys.argv)
    outer = len(argv) == 4 and argv[1] == "--supervisor"
    require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode and
            (len(argv) == 3 or outer))
    bindings, frame = record(argv[-2]), record(argv[-1])
    roster = outer_names(frame.get("role")) if outer else names(frame.get("role"))
    require(set(bindings) == set(roster) and all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value)
                                               for value in bindings.values()))
    directory = Path(__file__).absolute().parent
    source = {name: read_source(directory, name) for name in roster}
    require(all(hashlib.sha256(raw).hexdigest() == bindings[name] for name, raw in source.items()))
    code = {name: compile(raw, str(directory / (name + ".py")), "exec", dont_inherit=True)
            for name, raw in source.items()}
    # No sys.path widening, cached bytecode, ambient sibling import or second
    # source read after hashing. This does not authenticate this script's own
    # earlier startup; its original parent/source admission is still required.
    require(not any(name in sys.modules for name in roster))
    original_path, path_values = sys.path, tuple(sys.path)
    for name in roster:
        module = types.ModuleType(name)
        module.__file__ = str(directory / (name + ".py"))
        module.__package__, module.__spec__, module.__cached__ = None, None, None
        sys.modules[name] = module
        exec(code[name], module.__dict__)
        require(sys.path is original_path and tuple(sys.path) == path_values and
                sys.argv is original_argv and tuple(sys.argv) == argv)
    # Return the actual new worker, not a replay selected from the diagnostic
    # roster. main() normalizes every incomplete exit, including SystemExit.
    if outer:
        return sys.modules["hosted_cache_provider_entry"]._SupervisorEntry(argv[-1].encode("ascii"))
    worker = sys.modules["hosted_cache_provider_launch"]._CaptureWorker(frame, argv[-1].encode("ascii"))
    sys.modules["hosted_cache_provider_launch"]._WORKERS.append(worker)
    return worker


def main():
    try:
        outer = len(sys.argv) == 4 and sys.argv[1] == "--supervisor"
        worker = bootstrap()
        expected = (sys.modules["hosted_cache_provider_entry"]._SupervisorEntry if outer else
                    sys.modules["hosted_cache_provider_launch"]._CaptureWorker)
        require(type(worker) is expected)
        try:
            result = worker.run()
        except BaseException as error:
            return worker.exit_code(None, error)
        return worker.exit_code(result, None)
    except BaseException:
        # Neither a bare return nor an exception's own code can mint0/65. Do
        # not print original exceptions, credentials or private capture bytes.
        return 66  # Fixed incomplete transport; provider-return.INCOMPLETE_EXIT.


if __name__ == "__main__":
    raise SystemExit(main())
