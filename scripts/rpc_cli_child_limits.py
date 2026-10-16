"""Child-only safety limits for the admitted synthetic CLI admission controls.

Never changes a parent/user/system limit, imports an app, or accepts an arbitrary
command. The original native executor remains the sole retirement authority.
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import resource
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def lowered(current, cap, hard_ceiling=None):
    soft, hard = current
    if type(cap) is not int or cap < 1:
        raise RuntimeError('Positive child limit required')
    if hard_ceiling is not None:
        if type(hard_ceiling) is not int or hard_ceiling < 1:
            raise RuntimeError('Positive kernel hard ceiling required')
        hard = hard_ceiling if hard == resource.RLIM_INFINITY else min(hard, hard_ceiling)
    new = cap if soft == resource.RLIM_INFINITY else min(soft, cap)
    if hard != resource.RLIM_INFINITY:
        new = min(new, hard)
    return new, hard


def darwin_process_ceiling():
    # Darwin clamps RLIMIT_NPROC's hard value to kern.maxprocperuid on
    # setrlimit, even when the inherited hard value is higher. Query that
    # read-only ceiling and request the exact stricter pair we will verify;
    # never accept an arbitrary readback mismatch or raise a child/host limit.
    if sys.platform != 'darwin':
        raise RuntimeError('The CLI child limit adapter requires Darwin')
    system = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    query = system.sysctlbyname
    query.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                     ctypes.c_void_p, ctypes.c_size_t]
    query.restype = ctypes.c_int
    value = ctypes.c_int()
    size = ctypes.c_size_t(ctypes.sizeof(value))
    if query(b'kern.maxprocperuid', ctypes.byref(value), ctypes.byref(size), None, 0) != 0 or \
            size.value != ctypes.sizeof(value) or value.value < 1:
        raise RuntimeError('Cannot verify the Darwin per-user process ceiling')
    return value.value


def apply_child_limits():
    rows = []
    for kind, cap, name in ((resource.RLIMIT_NOFILE, 256, 'openFiles'), (resource.RLIMIT_NPROC, 512, 'processes')):
        ceiling = darwin_process_ceiling() if kind == resource.RLIMIT_NPROC else None
        before = resource.getrlimit(kind)
        after = lowered(before, cap, ceiling)
        resource.setrlimit(kind, after)
        if resource.getrlimit(kind) != after:
            raise RuntimeError('Child safety limit was not applied')
        rows.append(dict(name=name, before=list(before), after=list(after),
                         kernelHardCeiling=ceiling, parentOrSystemChanged=False))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--home', required=True, type=Path)
    parser.add_argument('--app', required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()
    import rpc_cli_process_controls as cli
    files = cli.module('cli_limit_owned_context', 'run-rpc-capacity-lab.py')
    state, source = files.owned_context()
    base = state / 'work/cli-process-controls'
    cli.need(args.directory.parent == base and args.home.is_relative_to(base) and
             re.fullmatch('[A-Za-z0-9-]{1,72}', args.name) and
             re.fullmatch('p2pkit-cli-[a-f0-9]{20}', args.app), 'Only current synthetic child inputs are supported')
    for path in (args.directory, args.home, args.directory / 'tmp'):
        files.private_directory(path)
    manifest = json.loads(files.read_private(state / 'private/cli-runtime.json'))
    cli.need(manifest == cli.runtime_manifest(source), 'Child runtime differs from producer')
    rows = apply_child_limits()
    cli.private_write(args.directory / 'child-limits.json', dict(sourceSha=source, limits=rows,
        scope='CHILD_ONLY_SAFETY_CAPS_NOT_HOST_PRESSURE_OR_LIMIT_EXHAUSTION'))
    argv = cli.java_argv(manifest, args.home, args.directory / 'tmp') + cli.peer_options(
        args.name, args.app, args.directory)
    os.execv(argv[0], argv)


if __name__ == '__main__':
    raise SystemExit(main())
