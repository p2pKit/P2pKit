"""Fixed credential-free post-provider-close RAW observer; dormant, not admission.

The original Node bridge must observe the provider child's actual close before
starting this helper. Its sample precedes its OWN close: it cannot establish a
post-last-owner/Node-return/runner observation. No file retirement, provider
acceptance, new deadline, service authority or workflow activation is granted.
Matching source hashes do not authenticate this interpreter's earlier startup.
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


LIMIT = 512 * 1024
NAME = "hosted_cache_provider_clock"
ROLES = ("linux-x64", "windows-x64", "macos-arm64", "macos-x64")
STAMP = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns", "st_file_attributes")


def require(value):
    if not value:
        raise RuntimeError("PROVIDER_POST_CLOSE_CLOCK_REFUSED")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def record(raw):
    require(type(raw) is str and 0 < len(raw) <= 16 * 1024 and raw.isascii())
    def unique(pairs):
        value = {}
        for key, item in pairs:
            require(key not in value)
            value[key] = item
        return value
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: require(False))
    require(type(value) is dict and encoded(value) == raw)
    return value


def decimal(value, maximum):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value) is not None)
    number = int(value)
    require(number <= maximum)
    return number


def roster(role):
    require(type(role) is str and role in ROLES)
    return ("audit_processes", *(("hosted_lock_resources",) if role.startswith("macos-") else ()),
            "hosted_job_clock", NAME)


def read_source(directory, name):
    """Fixed small source reads only; no workspace import or provider-file read."""
    require(name in ("audit_processes", "hosted_lock_resources", "hosted_job_clock", NAME))
    path = directory / (name + ".py")
    require(path.is_absolute() and ".." not in path.parts)
    ancestors = [(parent, parent.lstat()) for parent in path.parents]
    require(all(stat.S_ISDIR(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400
                for _, info in ancestors))
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
            not getattr(before, "st_file_attributes", 0) & 0x400 and 0 < before.st_size <= LIMIT)
    stamp = tuple(getattr(before, key, None) for key in STAMP)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) |
                         getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    original, raw = None, b""
    try:
        opened = os.fstat(descriptor)
        require(tuple(getattr(opened, key, None) for key in STAMP) == stamp)
        while len(raw) <= LIMIT:
            part = os.read(descriptor, LIMIT + 1 - len(raw))
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


def load_clock(bindings, role):
    names = roster(role)
    require(set(bindings) == set(names) and all(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value)
                                               for value in bindings.values()))
    directory = Path(__file__).absolute().parent
    sources = {name: read_source(directory, name) for name in names}
    require(all(hashlib.sha256(raw).hexdigest() == bindings[name] for name, raw in sources.items()))
    dependencies = names[:-1]
    require(not any(name in sys.modules for name in dependencies))
    code = {name: compile(sources[name], str(directory / (name + ".py")), "exec", dont_inherit=True)
            for name in dependencies}
    original_path, original_argv = sys.path, sys.argv
    path_values, argv_values = tuple(sys.path), tuple(sys.argv)
    for name in dependencies:
        module = types.ModuleType(name)
        module.__file__ = str(directory / (name + ".py"))
        module.__package__, module.__spec__, module.__cached__ = None, None, None
        sys.modules[name] = module
        exec(code[name], module.__dict__)
        require(sys.path is original_path and tuple(sys.path) == path_values and
                sys.argv is original_argv and tuple(sys.argv) == argv_values)
    return sys.modules["hosted_job_clock"]


def run(bindings_raw, request_raw):
    request = record(request_raw)
    require(set(request) == {"schema", "invocationSha256", "role", "frequency", "minimumNs", "hardEndNs"} and
            request["schema"] == "P2PKIT_PROVIDER_POST_CLOSE_CLOCK_REQUEST_V1" and
            type(request["invocationSha256"]) is str and
            re.fullmatch(r"[0-9a-f]{64}", request["invocationSha256"]) is not None)
    role = request["role"]
    roster(role)
    frequency = decimal(request["frequency"], (1 << 63) - 1)
    minimum = decimal(request["minimumNs"], (1 << 64) - 1)
    end = decimal(request["hardEndNs"], (1 << 64) - 1)
    require(frequency > 0 and minimum < end and end - minimum <= 180_000_000_000 and
            (role == "windows-x64" or frequency == 1_000_000_000))
    clock = load_clock(record(bindings_raw), role)
    expected = clock.validate_identity(clock.ClockIdentity(role, clock.DOMAINS[role], frequency))
    observed = clock.checked_now(expected, minimum_ns=minimum)
    require(observed < end)
    payload = (encoded({**request, "schema": "P2PKIT_PROVIDER_POST_CLOSE_CLOCK_OBSERVATION_V1",
                        "domain": expected.domain, "observedNs": str(observed)}) + "\n").encode("ascii")
    require(len(payload) <= 1024)
    stream, output = sys.stdout, sys.stdout.buffer
    count = output.write(payload)
    require(type(count) is int and count == len(payload))
    output.flush()
    require(sys.stdout is stream and stream.buffer is output)
    # A provisional sample on stdout cannot pass if retention/return ran late.
    # This still precedes this helper's process close; the enclosing Node must
    # observe original exit/EOF/close and its own unchanged local fence.
    require(clock.checked_now(expected, minimum_ns=observed) < end)


def main():
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode and
                len(sys.argv) == 3)
        run(sys.argv[1], sys.argv[2])
        return 0
    except BaseException:
        return 66  # No original exception, environment or output bytes in logs.


if __name__ == "__main__":
    raise SystemExit(main())
