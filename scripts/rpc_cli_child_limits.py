"""Child-only safety limits for the admitted synthetic CLI admission controls.

Never changes a parent/user/system limit, imports an app, or accepts an arbitrary
command. The original native executor remains the sole retirement authority.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import resource
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


def lowered(current, cap):
    soft, hard = current
    if type(cap) is not int or cap < 1:
        raise RuntimeError('Positive child limit required')
    new = cap if soft == resource.RLIM_INFINITY else min(soft, cap)
    if hard != resource.RLIM_INFINITY:
        new = min(new, hard)
    return new, hard


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
    rows = []
    for kind, cap, name in ((resource.RLIMIT_NOFILE, 256, 'openFiles'), (resource.RLIMIT_NPROC, 512, 'processes')):
        before = resource.getrlimit(kind)
        after = lowered(before, cap)
        resource.setrlimit(kind, after)
        cli.need(resource.getrlimit(kind) == after, 'Child safety limit was not applied')
        rows.append(dict(name=name, before=list(before), after=list(after), parentOrSystemChanged=False))
    cli.private_write(args.directory / 'child-limits.json', dict(sourceSha=source, limits=rows,
        scope='CHILD_ONLY_SAFETY_CAPS_NOT_HOST_PRESSURE_OR_LIMIT_EXHAUSTION'))
    argv = cli.java_argv(manifest, args.home, args.directory / 'tmp') + cli.peer_options(
        args.name, args.app, args.directory)
    os.execv(argv[0], argv)


if __name__ == '__main__':
    raise SystemExit(main())
