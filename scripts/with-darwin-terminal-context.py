#!/usr/bin/env python3
"""Explicit nonroot Terminal diagnostic context; never a permission override.

Apple TN3179 lists Terminal descendants as automatically allowed CLI contexts.
Open one fresh app using LaunchServices and retain its application lease. No
AppleScript, permission prompts/clicks, TCC edits, defaults or root execution.
Only the unchanged audit-session and native executor may run the OS probes.
Initially restricted to the Intel network diagnostic, not product qualification.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shlex
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('terminal_private_files', ROOT / 'scripts/with-darwin-launchd-context.py')
private = importlib.util.module_from_spec(spec)
spec.loader.exec_module(private)
need, write_json, read_json = private.need, private.write_json, private.read_json
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_network_diagnostics as diagnostics
SCOPE = 'DISPOSABLE_NONROOT_TERMINAL_CONTEXT_NOT_APP_PERMISSION_OR_PHYSICAL_LAN'
ENVIRONMENT = (private.ENVIRONMENT - {'RPC_APPLE_LAUNCHD_CONTEXT'}) | {'RPC_APPLE_TERMINAL_CONTEXT'}
FLAGS = {'consoleUser', 'noPreexistingTerminal', 'applicationCreated', 'originalApplicationIdentity',
         'nativeChildFinished', 'scriptChildReaped', 'applicationQuitRequested', 'applicationTerminated',
         'nonrootChild', 'terminalAncestorVerified', 'unrecoverableRootInChild', 'sourceUnchanged', 'commandRemoved'}
APPLICATION_FLAGS = FLAGS - {'nonrootChild', 'terminalAncestorVerified', 'unrecoverableRootInChild', 'sourceUnchanged', 'commandRemoved'}
STAGES = ('SETUP', 'COMPILE', 'OPEN', 'CHILD', 'QUIT', 'FINALIZED')
CHECKS = ('NONE', 'CONSOLE', 'PREEXISTING_APPLICATION', 'SYSTEM_APPLICATION', 'PRIVATE_COMMAND', 'APPLICATION_OPEN',
          'APPLICATION_IDENTITY', 'ADMISSION_WRITE', 'CHILD_REAP', 'CHILD_SOURCE', 'APPLICATION_IDENTITY_CHANGED',
          'QUIT_REQUEST', 'QUIT_COMPLETION')
OBSERVATIONS = {'failureCheck', 'openErrorDomain', 'openErrorCode'}
CHECK_CATEGORIES = (*private.CHECK_CATEGORIES, 'NATIVE_ANCESTRY', 'APPLICATION_RECEIPT')


def check_category(message):
    # Classify only fixed checks, never expose native identities or exception text.
    if any(word in message.lower() for word in ('ancestor', 'ancestry', 'native parent')):
        return 'NATIVE_ANCESTRY'
    if 'application' in message.lower() or 'terminal' in message.lower():
        return 'APPLICATION_RECEIPT'
    return private.check_category(message)


def log_metadata(raw):
    need(type(raw) is bytes and len(raw) <= private.LIMIT, 'Bounded context log required')
    checks = {line.removeprefix('CONTEXT_FAILURE ') for line in raw.decode('utf-8', errors='replace').splitlines()
              if line.startswith('CONTEXT_FAILURE ') and line.removeprefix('CONTEXT_FAILURE ') in CHECK_CATEGORIES}
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), failedChecks=sorted(checks))


def environment_admit(env):
    need(platform.system() == 'Darwin' and platform.machine() == 'x86_64' and
         env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
         env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_REF') == private.REF and
         env.get('GITHUB_EVENT_NAME') == 'push' and env.get('RPC_QUALIFY_REQUESTED') == 'true' and
         env.get('RPC_APPLE_TERMINAL_CONTEXT') == 'true' and re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')),
         'Explicit native Intel feature context required')
    need(Path(env['GITHUB_WORKSPACE']).resolve(strict=True) == ROOT, 'Wrong source checkout')


def config_validate(config, directory):
    need(type(config) is dict and set(config) == {'uid', 'gid', 'groups', 'source', 'argv', 'environment'},
         'Invalid Terminal configuration')
    uid, gid = config['uid'], config['gid']
    need(type(uid) is int and type(gid) is int and uid > 0 and gid > 0 and
         os.getuid() == os.geteuid() == uid and os.getgid() == os.getegid() == gid, 'Original nonroot credentials required')
    account = pwd.getpwuid(uid)
    need(account.pw_gid == gid and config['groups'] == sorted(set(os.getgrouplist(account.pw_name, gid))),
         'Original account policy required')
    env = config['environment']
    need(type(env) is dict and set(env) <= ENVIRONMENT and 'PATH' in env and
         all(type(v) is str and '\0' not in v for v in env.values()), 'Unadmitted environment')
    environment_admit(env)
    parent = Path(env['RPC_QUALIFICATION_PARENT'])
    need(directory == parent / 'terminal-context' and parent.is_relative_to(Path(env['RUNNER_TEMP']).resolve(strict=True)),
         'Task-private physical parent required')
    private.private_parent(parent, uid)
    private.private_parent(directory, uid)
    python = str(Path(sys.executable).resolve())
    need(config['argv'] == [python, str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', str(parent), '--',
         python, str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64',
         '--intel-investigation', 'network'], 'Only unchanged native Intel network diagnostic admitted')
    source = config['source']
    need(type(source) is dict and set(source) == {'commit', 'tree'} and
         all(type(v) is str and re.fullmatch('[0-9a-f]{40}', v) for v in source.values()) and
         source['commit'] == env['GITHUB_SHA'], 'Exact clean source binding required')


def command_bytes(directory):
    argv = [str(Path(sys.executable).resolve()), '-I', '-S', str(Path(__file__).resolve()),
            '--child', str(directory / 'config.json')]
    return ('#!/bin/bash\numask 077\n' + shlex.join(argv) + ' </dev/null >' + shlex.quote(str(directory / 'child.stdout.log')) +
            ' 2>' + shlex.quote(str(directory / 'child.stderr.log')) + '\nstatus=$?\n' +
            'printf \'%s\\n\' "$status" >' + shlex.quote(str(directory / 'shell-result.txt')) + '\nexit "$status"\n').encode()


def ancestor_matches(observe, own_pid, terminal, uid):
    need(type(terminal) is dict and set(terminal) == {'pid', 'uid', 'startSeconds', 'startMicroseconds'} and
         all(type(v) is int and v >= 0 for v in terminal.values()) and terminal['pid'] > 1 and terminal['uid'] == uid,
         'Exact application identity required')
    seen = set()
    cursor = own_pid
    previous = None
    for _ in range(32):
        need(cursor > 1 and cursor not in seen, 'Terminal ancestor not established')
        seen.add(cursor)
        row = observe(cursor)
        need(row['pid'] == cursor and row['uid'] == row['realUid'] == uid and row['live'], 'Wrong native ancestor identity')
        if previous is not None:
            need(previous['parentUniqueId'] == row['uniqueId'], 'Replaced native parent refused')
        if cursor == terminal['pid']:
            need(all(row[k] == terminal[k] for k in terminal), 'Application start identity changed')
            return
        previous, cursor = row, row['parentPid']
    need(False, 'Ancestry exceeded its bound')


def terminal_ancestor(directory):
    spec = importlib.util.spec_from_file_location('terminal_native_identity', ROOT / 'scripts/audit_processes.py')
    native = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = native
    spec.loader.exec_module(native)
    api = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    api.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
    api.proc_pidinfo.restype = ctypes.c_int
    def observe(pid):
        row = native.DarwinIdentity()
        need(api.proc_pidinfo(pid, 18, 1, ctypes.byref(row), ctypes.sizeof(row)) == ctypes.sizeof(row),
             'Exact native ancestor observation required')
        return dict(pid=row.bsd.pid, uid=row.bsd.uid, realUid=row.bsd.ruid, parentPid=row.bsd.ppid,
                    uniqueId=row.unique.uniqueid, parentUniqueId=row.unique.parentuniqueid,
                    startSeconds=row.bsd.startsec, startMicroseconds=row.bsd.startusec, live=row.bsd.status in (1, 2, 3, 4))
    path = directory / 'application-admission.json'
    deadline = time.monotonic() + 30
    while not path.exists():
        need(time.monotonic() < deadline, 'No exact Terminal application receipt')
        time.sleep(0.1)
    ancestor_matches(observe, os.getpid(), read_json(path), os.getuid())


def child(path):
    config = read_json(path)
    config_validate(config, path.parent)
    need(sorted(set(os.getgroups())) == config['groups'], 'Original nonroot groups required')
    need(private.source_snapshot() == config['source'], 'Source changed before Terminal child')
    terminal_ancestor(path.parent)
    try:
        os.setuid(0)
    except PermissionError:
        pass
    else:
        raise RuntimeError('Recoverable root refused')
    write_json(path.parent / 'child-admission.json', dict(source=config['source'], nonrootChild=True,
               terminalAncestorVerified=True, unrecoverableRootInChild=True))
    account = pwd.getpwuid(os.getuid())
    env = {**config['environment'], 'HOME': account.pw_dir, 'USER': account.pw_name, 'LOGNAME': account.pw_name,
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'}
    code = subprocess.call(config['argv'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    need(private.source_snapshot() == config['source'], 'Source changed during Terminal child')
    write_json(path.parent / 'child-result.json', dict(source=config['source'], exitCode=code))
    return code


def validate_proof(value, source, complete=True):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'source', 'exitCode', 'stage', 'logs',
                                             'compilerDiagnostics', *OBSERVATIONS, *FLAGS},
         'Closed Terminal proof required')
    need(type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE and value['source'] == source and
         type(value['exitCode']) is int and -255 <= value['exitCode'] <= 255 and value['stage'] in STAGES and
         all(type(value[k]) is bool for k in FLAGS), 'Invalid context proof')
    need(value['failureCheck'] in CHECKS and value['openErrorDomain'] in ('NONE', 'COCOA', 'OSSTATUS', 'POSIX', 'OTHER') and
         type(value['openErrorCode']) is int and -1000000 <= value['openErrorCode'] <= 1000000, 'Unknown application check')
    if value['compilerDiagnostics'] is not None:
        diagnostics.validate_compiler(value['compilerDiagnostics'], ROOT / 'scripts/diagnostics/apple-terminal-context.m')
    need(type(value['logs']) is dict and set(value['logs']) <= {'compile', 'application', 'child.stdout', 'child.stderr'},
         'Unknown log categories')
    for row in value['logs'].values():
        need(type(row) is dict and set(row) == {'bytes', 'sha256', 'failedChecks'} and type(row['bytes']) is int and
             0 <= row['bytes'] <= private.LIMIT and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}', row['sha256']),
             'Invalid log metadata')
        need(type(row['failedChecks']) is list and len(row['failedChecks']) <= len(CHECK_CATEGORIES) and
             all(type(item) is str and item in CHECK_CATEGORIES for item in row['failedChecks']) and
             row['failedChecks'] == sorted(set(row['failedChecks'])), 'Unknown/duplicate context checks')
    if complete:
        need(all(value[k] for k in FLAGS) and value['stage'] == 'FINALIZED' and value['exitCode'] in (0, 1),
             'Unproven Terminal context finalization')
        need(value['failureCheck'] == 'NONE' and value['openErrorDomain'] == 'NONE' and value['openErrorCode'] == 0 and
             value['compilerDiagnostics'] is not None, 'Failed/missing application or compiler proof')
        need(all(not row['failedChecks'] for row in value['logs'].values()), 'Failed child context cannot finalize')
    return value


def run(parent):
    environment_admit(os.environ)
    need(os.getuid() == os.geteuid() != 0, 'Nonroot controller required')
    private.private_parent(parent, os.getuid())
    directory = parent / 'terminal-context'
    directory.mkdir(mode=0o700)
    source = private.source_snapshot()
    python = str(Path(sys.executable).resolve())
    account = pwd.getpwuid(os.getuid())
    config = dict(uid=os.getuid(), gid=os.getgid(), groups=sorted(set(os.getgrouplist(account.pw_name, os.getgid()))),
        source=source, environment={k: v for k, v in os.environ.items() if k in ENVIRONMENT}, argv=[python,
        str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', str(parent), '--', python,
        str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64', '--intel-investigation', 'network'])
    config_validate(config, directory)
    write_json(directory / 'config.json', config)
    command = directory / 'native.command'
    script = command_bytes(directory)
    private.write_new(command, script)
    command.chmod(0o700)
    proof = dict(schema=1, scope=SCOPE, source=source, stage='SETUP', exitCode=125, logs={}, compilerDiagnostics=None,
                 failureCheck='NONE', openErrorDomain='NONE', openErrorCode=0, **dict.fromkeys(FLAGS, False))
    try:
        proof['stage'] = 'COMPILE'
        binary = directory / 'terminal-context'
        with (directory / 'compile.log').open('xb') as log:
            code = subprocess.call(['/usr/bin/xcrun', '--sdk', 'macosx', 'clang', '-Wall', '-Wextra', '-Werror',
                '-fobjc-arc', '-fblocks', '-mmacosx-version-min=15.0', '-framework', 'AppKit',
                str(ROOT / 'scripts/diagnostics/apple-terminal-context.m'), '-o', str(binary)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        proof['compilerDiagnostics'] = diagnostics.compiler_observation(
            private.read_private(directory / 'compile.log', os.getuid()), ROOT / 'scripts/diagnostics/apple-terminal-context.m')
        need(code == 0, 'Native context controller did not compile')
        with (directory / 'application.log').open('xb') as log:
            code = subprocess.call([str(binary), str(directory)], cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT)
        app = read_json(directory / 'application-result.json')
        need(type(app) is dict and set(app) == {'schema', 'stage', 'exitCode', *OBSERVATIONS, *APPLICATION_FLAGS} and
             type(app['schema']) is int and app['schema'] == 1 and app['stage'] in STAGES and
             type(app['exitCode']) is int and app['exitCode'] in (0, 1, 125) and
             all(type(app[k]) is bool for k in APPLICATION_FLAGS), 'Invalid application finalization')
        proof.update({k: v for k, v in app.items() if k != 'schema'})
        if (directory / 'child-admission.json').exists():
            admitted = read_json(directory / 'child-admission.json')
            need(admitted == dict(source=source, nonrootChild=True, terminalAncestorVerified=True,
                                  unrecoverableRootInChild=True), 'Missing native child context')
            proof.update({k: v for k, v in admitted.items() if k != 'source'})
        need(code == app['exitCode'] and code in (0, 1), 'Exact application/child result required')
        finished = read_json(directory / 'child-result.json')
        need(finished == dict(source=source, exitCode=code), 'Child result mismatch')
    finally:
        proof['sourceUnchanged'] = private.source_snapshot() == source
        for label in ('compile', 'application', 'child.stdout', 'child.stderr'):
            path = directory / (label + '.log')
            if path.exists():
                # Controller-created logs use ordinary open plus a local private umask.
                raw = private.read_private(path, os.getuid())
                proof['logs'][label] = log_metadata(raw)
        if proof['applicationTerminated'] and proof['scriptChildReaped']:
            need(command.read_bytes() == script and not command.is_symlink(), 'Do not remove a replaced command')
            command.unlink()
            proof['commandRemoved'] = True
        if all(proof[k] for k in FLAGS):
            proof['stage'] = 'FINALIZED'
        write_json(directory / 'result.json', proof)
    validate_proof(proof, source)
    return proof['exitCode']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--lane', choices=('apple-x64',))
    parser.add_argument('--intel-investigation', choices=('network',))
    args = parser.parse_args()
    os.umask(0o077)
    if args.child:
        need(args.parent is None and args.lane is None and args.intel_investigation is None, 'Exact child command required')
        return child(args.child)
    need(args.parent is not None and args.lane == 'apple-x64' and args.intel_investigation == 'network',
         'Only explicit Intel network investigation admitted')
    return run(args.parent)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        if isinstance(error, private.ContextFailure):
            print('CONTEXT_FAILURE ' + check_category(str(error)), file=sys.stderr)
        print('Nonroot Terminal context failed: ' + type(error).__name__ + '; no admission claim', file=sys.stderr)
        raise SystemExit(125)
