#!/usr/bin/env python3
"""Explicit nonroot native Apple Terminal test context; never a permission override.

Apple TN3179 lists Terminal descendants as automatically allowed CLI contexts.
Open one fresh app using LaunchServices and retain its application lease. No
AppleScript, permission prompts/clicks, TCC edits, defaults or root execution.
Only the unchanged audit-session and native executor may run the fixed native
probe, original Intel LAN-test profile, narrow host-test/readiness diagnostic,
or the full original inventory for its exact native Apple architecture.
All product modes require the separately verified reversible advertising setup.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
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
import rpc_apple_runner_context as apple_context
SCOPE = 'DISPOSABLE_NONROOT_TERMINAL_CONTEXT_NOT_APP_PERMISSION_OR_PHYSICAL_LAN'
ENVIRONMENT = (private.ENVIRONMENT - {'RPC_APPLE_LAUNCHD_CONTEXT'}) | {
    'RPC_APPLE_TERMINAL_CONTEXT', 'RPC_APPLE_BONJOUR_ADVERTISING', 'RPC_INTEL_INVESTIGATION', 'RPC_APPLE_LANE'}
EXECUTION_MODES = ('network', 'native', 'runtime', 'qualification')
FLAGS = {'consoleUser', 'noPreexistingTerminal', 'applicationCreated', 'originalApplicationIdentity',
         'nativeChildFinished', 'scriptChildReaped', 'applicationQuitRequested', 'applicationTerminated',
         'nonrootChild', 'terminalAncestorVerified', 'unrecoverableRootInChild', 'sourceUnchanged', 'commandRemoved'}
APPLICATION_FLAGS = FLAGS - {'nonrootChild', 'terminalAncestorVerified', 'unrecoverableRootInChild', 'sourceUnchanged', 'commandRemoved'}
STAGES = ('SETUP', 'COMPILE', 'OPEN', 'CHILD', 'QUIT', 'FINALIZED')
CHECKS = ('NONE', 'CONSOLE', 'PREEXISTING_APPLICATION', 'SYSTEM_APPLICATION', 'PRIVATE_COMMAND', 'APPLICATION_OPEN',
          'APPLICATION_IDENTITY', 'ADMISSION_WRITE', 'CHILD_REAP', 'CHILD_SOURCE', 'APPLICATION_IDENTITY_CHANGED',
          'QUIT_REQUEST', 'QUIT_COMPLETION')
OBSERVATIONS = {'failureCheck', 'openErrorDomain', 'openErrorCode'}
ANCESTRY_METHOD = 'NONPRIVILEGED_SHORT_UNIQUE_BRACKETED'
ANCESTRY_CHECKS = {
    'Native ancestor observation failed': 'ANCESTOR_OBSERVATION',
    'Native ancestor PID differs': 'ANCESTOR_PID',
    'Native ancestor is not live': 'ANCESTOR_LIVENESS',
    'Native ancestor is privileged system login': 'ANCESTOR_SYSTEM_LOGIN',
    'Native ancestor credentials differ': 'ANCESTOR_CREDENTIALS',
    'Replaced native parent refused': 'ANCESTOR_PARENT_IDENTITY',
    'Terminal ancestor not established': 'ANCESTOR_CHAIN',
    'Application start identity changed': 'ANCESTOR_START_IDENTITY',
    'Ancestry exceeded its bound': 'ANCESTOR_BOUND',
    **{f'Native ancestor {name} {outcome}': f'ANCESTOR_{label}_{code}'
       for name, label in (('unique', 'UNIQUE'), ('limited BSD', 'LIMITED'), ('full start', 'FULL'))
       for outcome, code in (('permission denied', 'PERMISSION'), ('read failed', 'READ'))},
}
CHECK_CATEGORIES = (*private.CHECK_CATEGORIES, 'NATIVE_ANCESTRY', 'APPLICATION_RECEIPT', *ANCESTRY_CHECKS.values())


def check_category(message):
    # Classify only fixed checks, never expose native identities or exception text.
    if message in ANCESTRY_CHECKS:
        return ANCESTRY_CHECKS[message]
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
    apple_context.native_lane(env)
    need(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
         env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_REF') == private.REF and
         env.get('GITHUB_EVENT_NAME') == 'push' and env.get('RPC_QUALIFY_REQUESTED') == 'true' and
         env.get('RPC_APPLE_TERMINAL_CONTEXT') == 'true' and re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')),
         'Explicit native Apple feature context required')
    need(Path(env['GITHUB_WORKSPACE']).resolve(strict=True) == ROOT, 'Wrong source checkout')


def execution_mode(env):
    lane = apple_context.selected_lane(env)
    investigation = env.get('RPC_INTEL_INVESTIGATION')
    need(investigation in ('', 'native', 'network', 'runtime') and env.get('RPC_ADMISSION_ONLY') == 'false',
         'Exact non-admission Apple execution mode required')
    need(lane == 'apple-x64' or investigation == '', 'Intel diagnostics cannot substitute for native ARM qualification')
    mode = investigation or 'qualification'
    need(mode == 'network' or env.get('RPC_APPLE_BONJOUR_ADVERTISING') == 'true',
         'Original Apple product tests require the verified advertising preparation')
    return mode


def qualification_argv(parent, env):
    mode = execution_mode(env)
    advertising = env.get('RPC_APPLE_BONJOUR_ADVERTISING')
    need(advertising in (None, 'true', 'false'), 'Explicit Boolean advertising request required')
    python = str(Path(sys.executable).resolve())
    argv = [python, str(ROOT / 'scripts/with-darwin-audit-session.py'), '--parent', str(parent), '--',
            python, str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', apple_context.selected_lane(env)]
    if mode != 'qualification':
        argv += ['--intel-investigation', mode]
    # The request also crosses the nested session in argv. If a future context
    # filter drops the environment opt-in, fail BEFORE native work, not after
    # an accidental replay of the unchanged diagnostic.
    if advertising == 'true':
        argv.append('--require-bonjour-advertising')
    return argv


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
    need(config['argv'] == qualification_argv(parent, env), 'Only the exact original native Apple command is admitted')
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


class DarwinShortInfo(ctypes.Structure):
    # proc_bsdshortinfo: the kernel intentionally permits this limited view
    # across UIDs. Full BSDINFO/combined flavor 18 requires matching UIDs.
    _fields_ = [(key, ctypes.c_uint32) for key in ('pid', 'ppid', 'pgid', 'status')] + [
        ('comm', ctypes.c_char * 16)] + [(key, ctypes.c_uint32) for key in (
            'flags', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid', 'reserved')]


def observe_ancestor(api, native, pid):
    """Read-only origin proof, NOT product ownership or a signaling capability.

    Terminal's login parent retains privilege for PAM cleanup. Observe its
    limited BSD fields/path between *matching kernel unique-ID/exec-version*
    reads; never escalate to inspect it or manufacture a combined identity.
    Same-UID processes additionally retain the original full start-identity
    check, including the exact returned Terminal application.
    """
    need((ctypes.sizeof(DarwinShortInfo), ctypes.sizeof(native.DarwinUniqueInfo),
          ctypes.sizeof(native.DarwinIdentity)) == (64, 56, 192), 'Unsupported native ancestor ABI')

    def read(flavor, kind):
        value = kind()
        ctypes.set_errno(0)
        count = api.proc_pidinfo(pid, flavor, 1, ctypes.byref(value), ctypes.sizeof(value))
        name = {17: 'unique', 13: 'limited BSD', 18: 'full start'}[flavor]
        reason = 'permission denied' if count == 0 and ctypes.get_errno() in (errno.EPERM, errno.EACCES) else 'read failed'
        need(count == ctypes.sizeof(value), f'Native ancestor {name} {reason}')
        return value

    before = read(17, native.DarwinUniqueInfo)
    short = read(13, DarwinShortInfo)
    full = read(18, native.DarwinIdentity) if short.uid == os.geteuid() else None
    path = ctypes.create_string_buffer(4096)
    length = api.proc_pidpath(pid, path, len(path))
    system_login = 0 < length < len(path) and path.value == b'/usr/bin/login'
    restricted_denied = False
    if short.uid == 0 and system_login:
        # Retain the original API's actual result as a negative control. Failure
        # is not converted into ownership: the origin proof uses the separately
        # permitted limited identity and never acquires a signal capability.
        original = native.DarwinIdentity()
        ctypes.set_errno(0)
        count = api.proc_pidinfo(pid, 18, 1, ctypes.byref(original), ctypes.sizeof(original))
        restricted_denied = count == 0 and ctypes.get_errno() in (errno.EPERM, errno.EACCES)
        need(restricted_denied or (count == ctypes.sizeof(original) and bytes(original.unique) == bytes(before) and
             original.bsd.pid == pid and original.bsd.uid == short.uid), 'Unexpected restricted ancestor observation')
    after_short = read(13, DarwinShortInfo)
    after = read(17, native.DarwinUniqueInfo)
    keys = ('pid', 'ppid', 'pgid', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid')
    need(bytes(before) == bytes(after) and before.uniqueid > 0 and
         all(getattr(short, key) == getattr(after_short, key) for key in keys) and
         short.pid == pid and short.status in (1, 2, 3, 4) and after_short.status in (1, 2, 3, 4),
         'Native ancestor changed during bracketed observation')
    if full is not None:
        need(bytes(full.unique) == bytes(before) and all(getattr(full.bsd, key) == getattr(short, key) for key in keys) and
             full.bsd.status in (1, 2, 3, 4), 'Native ancestor full identity changed during observation')
    return dict(pid=short.pid, uid=short.uid, realUid=short.ruid, parentPid=short.ppid,
                uniqueId=before.uniqueid, parentUniqueId=before.parentuniqueid,
                startSeconds=full.bsd.startsec if full is not None else None,
                startMicroseconds=full.bsd.startusec if full is not None else None,
                live=True, systemLogin=system_login, restrictedCombinedDenied=restricted_denied)


def validate_ancestry(value):
    need(type(value) is dict and set(value) == {'method', 'depth', 'systemLoginAncestors', 'restrictedCombinedDenials'} and
         value['method'] == ANCESTRY_METHOD and type(value['depth']) is int and 2 <= value['depth'] <= 32 and
         type(value['systemLoginAncestors']) is int and 0 <= value['systemLoginAncestors'] <= 1 and
         type(value['restrictedCombinedDenials']) is int and
         0 <= value['restrictedCombinedDenials'] <= value['systemLoginAncestors'],
         'Closed native ancestry counts required')
    return value


def ancestor_matches(observe, own_pid, terminal, uid):
    need(type(terminal) is dict and set(terminal) == {'pid', 'uid', 'startSeconds', 'startMicroseconds'} and
         all(type(v) is int and v >= 0 for v in terminal.values()) and terminal['pid'] > 1 and terminal['uid'] == uid,
         'Exact application identity required')
    seen = set()
    cursor = own_pid
    previous = None
    system_login_ancestors = 0
    restricted_denials = 0
    for _ in range(32):
        need(cursor > 1 and cursor not in seen, 'Terminal ancestor not established')
        seen.add(cursor)
        row = observe(cursor)
        need(row['pid'] == cursor, 'Native ancestor PID differs')
        need(row['live'], 'Native ancestor is not live')
        # This one OS-owned intermediary is NOT a test-owned product process.
        # Require its real system image, direct parent to the exact Terminal,
        # and the same kernel parent-unique-ID chain as every other ancestor.
        # It is never signaled, adopted by the executor, or run by us as root.
        login = (cursor not in (own_pid, terminal['pid']) and row.get('systemLogin') is True and
                 row['uid'] == 0 and row['realUid'] in (0, uid) and row['parentPid'] == terminal['pid'] and
                 system_login_ancestors == 0)
        need(row['uid'] == row['realUid'] == uid or login,
             'Native ancestor is privileged system login' if row.get('systemLogin') and
             (row['uid'] == 0 or row['realUid'] == 0) else 'Native ancestor credentials differ')
        system_login_ancestors += int(login)
        restricted_denials += int(login and row.get('restrictedCombinedDenied') is True)
        if previous is not None:
            need(previous['parentUniqueId'] == row['uniqueId'], 'Replaced native parent refused')
        if cursor == terminal['pid']:
            need(all(row[k] == terminal[k] for k in terminal), 'Application start identity changed')
            return validate_ancestry(dict(method=ANCESTRY_METHOD, depth=len(seen),
                                         systemLoginAncestors=system_login_ancestors,
                                         restrictedCombinedDenials=restricted_denials))
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
    api.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    api.proc_pidpath.restype = ctypes.c_int
    path = directory / 'application-admission.json'
    deadline = time.monotonic() + 30
    while not path.exists():
        need(time.monotonic() < deadline, 'No exact Terminal application receipt')
        time.sleep(0.1)
    return ancestor_matches(lambda pid: observe_ancestor(api, native, pid), os.getpid(), read_json(path), os.getuid())


def child(path):
    config = read_json(path)
    config_validate(config, path.parent)
    need(sorted(set(os.getgroups())) == config['groups'], 'Original nonroot groups required')
    need(private.source_snapshot() == config['source'], 'Source changed before Terminal child')
    ancestry = terminal_ancestor(path.parent)
    try:
        os.setuid(0)
    except PermissionError:
        pass
    else:
        raise RuntimeError('Recoverable root refused')
    write_json(path.parent / 'child-admission.json', dict(source=config['source'], nonrootChild=True,
               terminalAncestorVerified=True, unrecoverableRootInChild=True, ancestry=ancestry))
    account = pwd.getpwuid(os.getuid())
    env = {**config['environment'], 'HOME': account.pw_dir, 'USER': account.pw_name, 'LOGNAME': account.pw_name,
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'}
    code = subprocess.call(config['argv'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
    need(private.source_snapshot() == config['source'], 'Source changed during Terminal child')
    write_json(path.parent / 'child-result.json', dict(source=config['source'], exitCode=code))
    return code


def validate_proof(value, source, complete=True, *, expected_lane=None):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'source', 'exitCode', 'stage', 'logs',
                                             'compilerDiagnostics', 'ancestry', 'executionMode', 'nativeLane', *OBSERVATIONS, *FLAGS},
         'Closed Terminal proof required')
    lane = apple_context.proof_lane(value['nativeLane'], expected_lane)
    need(lane == 'apple-x64' or value['executionMode'] == 'qualification', 'ARM proof requires the full original inventory')
    need(type(value['schema']) is int and value['schema'] == 3 and value['executionMode'] in EXECUTION_MODES and value['scope'] == SCOPE and value['source'] == source and
         type(value['exitCode']) is int and -255 <= value['exitCode'] <= 255 and value['stage'] in STAGES and
         all(type(value[k]) is bool for k in FLAGS), 'Invalid context proof')
    need(value['failureCheck'] in CHECKS and value['openErrorDomain'] in ('NONE', 'COCOA', 'OSSTATUS', 'POSIX', 'OTHER') and
         type(value['openErrorCode']) is int and -1000000 <= value['openErrorCode'] <= 1000000, 'Unknown application check')
    if value['compilerDiagnostics'] is not None:
        diagnostics.validate_compiler(value['compilerDiagnostics'], ROOT / 'scripts/diagnostics/apple-terminal-context.m')
    if value['ancestry'] is not None:
        validate_ancestry(value['ancestry'])
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
        need(value['ancestry'] is not None, 'Native ancestry was not observed')
    return value


def run(parent):
    environment_admit(os.environ)
    need(os.getuid() == os.geteuid() != 0, 'Nonroot controller required')
    private.private_parent(parent, os.getuid())
    directory = parent / 'terminal-context'
    directory.mkdir(mode=0o700)
    source = private.source_snapshot()
    account = pwd.getpwuid(os.getuid())
    env = {k: v for k, v in os.environ.items() if k in ENVIRONMENT}
    config = dict(uid=os.getuid(), gid=os.getgid(), groups=sorted(set(os.getgrouplist(account.pw_name, os.getgid()))),
        source=source, environment=env, argv=qualification_argv(parent, env))
    config_validate(config, directory)
    write_json(directory / 'config.json', config)
    command = directory / 'native.command'
    script = command_bytes(directory)
    private.write_new(command, script)
    command.chmod(0o700)
    proof = dict(schema=3, scope=SCOPE, source=source, nativeLane=apple_context.native_lane(env), executionMode=execution_mode(env), stage='SETUP', exitCode=125, logs={}, compilerDiagnostics=None, ancestry=None,
                 failureCheck='NONE', openErrorDomain='NONE', openErrorCode=0, **dict.fromkeys(FLAGS, False))
    try:
        proof['stage'] = 'COMPILE'
        binary = directory / 'terminal-context'
        with (directory / 'compile.log').open('xb') as log:
            code = subprocess.call(['/usr/bin/xcrun', '--sdk', 'macosx', 'clang', '-Wall', '-Wextra', '-Werror',
                '-fobjc-arc', '-fblocks', '-arch', apple_context.HOSTS[proof['nativeLane']][0],
                '-mmacosx-version-min=15.0', '-framework', 'AppKit',
                str(ROOT / 'scripts/diagnostics/apple-terminal-context.m'), '-o', str(binary)],
                cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        proof['compilerDiagnostics'] = diagnostics.compiler_observation(
            private.read_private(directory / 'compile.log', os.getuid()), ROOT / 'scripts/diagnostics/apple-terminal-context.m')
        need(code == 0, 'Native context controller did not compile')
        with (directory / 'application.log').open('xb') as log:
            code = subprocess.call([str(binary), str(directory), execution_mode(env)], cwd=ROOT, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT)
        app = read_json(directory / 'application-result.json')
        need(type(app) is dict and set(app) == {'schema', 'stage', 'exitCode', 'executionMode', *OBSERVATIONS, *APPLICATION_FLAGS} and
             type(app['schema']) is int and app['schema'] == 2 and app['executionMode'] == execution_mode(env) and app['stage'] in STAGES and
             type(app['exitCode']) is int and app['exitCode'] in (0, 1, 125) and
             all(type(app[k]) is bool for k in APPLICATION_FLAGS), 'Invalid application finalization')
        proof.update({k: v for k, v in app.items() if k != 'schema'})
        if (directory / 'child-admission.json').exists():
            admitted = read_json(directory / 'child-admission.json')
            ancestry = validate_ancestry(admitted.get('ancestry'))
            need(admitted == dict(source=source, nonrootChild=True, terminalAncestorVerified=True,
                                  unrecoverableRootInChild=True, ancestry=ancestry), 'Missing native child context')
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
    validate_proof(proof, source, expected_lane=apple_context.selected_lane(env))
    return proof['exitCode']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--parent', type=Path)
    parser.add_argument('--lane', choices=tuple(apple_context.HOSTS))
    parser.add_argument('--intel-investigation', choices=('network', 'native', 'runtime'))
    args = parser.parse_args()
    os.umask(0o077)
    if args.child:
        need(args.parent is None and args.lane is None and args.intel_investigation is None, 'Exact child command required')
        return child(args.child)
    need(args.parent is not None and args.lane == apple_context.selected_lane(os.environ) and
         (args.intel_investigation or '') == os.environ.get('RPC_INTEL_INVESTIGATION'),
         'Only the explicitly requested native Apple execution mode is admitted')
    return run(args.parent)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        if isinstance(error, private.ContextFailure):
            print('CONTEXT_FAILURE ' + check_category(str(error)), file=sys.stderr)
        print('Nonroot Terminal context failed: ' + type(error).__name__ + '; no admission claim', file=sys.stderr)
        raise SystemExit(125)
