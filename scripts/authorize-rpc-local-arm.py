#!/usr/bin/env python3
"""Request one macOS administrator dialog for one fresh prepared ARM qualification.

This launcher stays unprivileged. The unchanged audit-session bootstrap alone
allocates a fresh session and permanently drops privilege before any repository
import, product execution or evidence write. No sudo policy, stored password,
persistent helper, session reuse, automatic retry or system installation.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import platform
import shlex
import subprocess
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'ONE_SHOT_MACOS_AUTHORIZATION_TRANSPORT_NOT_QUALIFICATION'
# Only the Apple-event transport can wait this long. Every product, readiness,
# ownership and Gradle-stop deadline inside the unchanged executor still applies.
# Never put a password or an account name in AppleScript arguments.
APPLESCRIPT = '''on run arguments
    if (count of arguments) is not 1 then error "One prepared bootstrap required"
    with timeout of 28800 seconds
        return do shell script (item 1 of arguments) with administrator privileges with prompt "P2pKit: authorize one fresh audit session. Tests run as your normal account; no system settings are changed." without altering line endings
    end timeout
end run'''


def need(condition, message):
    if not condition:
        raise RuntimeError(message)


def gui_session(system, uid, euid, console):
    need(system == 'Darwin' and uid == euid == console and uid > 0,
         'The unprivileged logged-in Mac console account must request the administrator dialog')


def console_uid():
    return Path('/dev/console').stat().st_uid


def digest(path):
    with path.open('rb') as source:
        return hashlib.file_digest(source, 'sha256').hexdigest()


def dialog_argv(python, bootstrap, config, uid, gid):
    need(type(uid) is int and type(gid) is int and uid > 0 and gid > 0, 'Non-root invoking credentials required')
    need(all(path.is_absolute() and '\0' not in str(path) for path in (python, bootstrap, config)),
         'Explicit executable, bootstrap and prepared configuration paths required')
    # Standard Additions does not set sudo's invoker variables. Bind exactly the
    # already validated normal account; bootstrap still checks its primary group.
    # Start with an empty root environment and isolate Python from site hooks.
    command = 'exec ' + shlex.join(['/usr/bin/env', '-i', f'SUDO_UID={uid}', f'SUDO_GID={gid}',
        str(python), '-I', '-S', str(bootstrap), '--bootstrap', str(config)])
    return ['/usr/bin/osascript', '-e', APPLESCRIPT, command]


def preflight(parent, expected, local):
    uid, gid = os.getuid(), os.getgid()
    local.local_host(os.environ, platform.system(), platform.machine(), uid, os.geteuid())
    gui_session(platform.system(), uid, os.geteuid(), console_uid())
    local.private_parent(parent)
    for relative in ('state', 'local-session-admission.json', 'private-session/session-admission.json',
                     'gui-authorization-request.json'):
        path = parent / relative
        need(not path.exists() and not path.is_symlink(), 'Consumed or already-prompted request; no automatic retry')
    source = local.source_admission(expected)
    config_path = parent / 'private-session/session-config.json'
    config = local.bootstrap.read_config(config_path, uid)
    local.bootstrap.validate(config, uid, gid)
    prepared = local.runner.read_json(parent / 'prepared.json')
    need(all(type(prepared.get(key)) is bool for key in
             ('swiftRuntimeOnly', 'macGeneratorOnly', 'cliProcessOnly', 'cliRemainingOnly')),
         'Explicit prepared qualification selections required')
    only, clock_only, cli_only = prepared['swiftRuntimeOnly'], prepared['macGeneratorOnly'], prepared['cliProcessOnly']
    remaining_only = prepared['cliRemainingOnly']
    need('cliFirstCase' in prepared, 'An explicit nullable CLI suffix is required')
    first_case = prepared['cliFirstCase']
    plan = list(local.plan_for(only, clock_only, cli_only, remaining_only, first_case))
    need(config['cwd'] == str(local.ROOT) and
         config['argv'] == local.run_argv(parent, expected, only, clock_only, cli_only, remaining_only, first_case),
         'Only the exact prepared local ARM controller is authorized')
    need(type(prepared.get('schema')) is int and prepared['schema'] == 1 and
         prepared['scope'] == local.SCOPE and prepared['baseline'] == local.BASELINE and
         prepared['source'] == source and prepared['plan'] == plan and
         prepared['environment'] == config['environment'] and prepared['bootstrapExecuted'] is False and
         prepared['installationsRequested'] is False and prepared['priorResultsReusedAsNativeAdmission'] is False,
         'Prepared source, environment or authorization scope changed')
    local.distribution.admit_archive(local.ROOT, parent, prepared['gradleDistribution'])
    need(local.xcodegen_package.admit(prepared['xcodegenPackage']) / 'bin/xcodegen' == Path(prepared['xcodegen']),
         'Prepared XcodeGen package differs')
    need(not any(path.exists() or path.is_symlink() for path in local.runner.disposable_roots(local.ROOT)),
         'Existing generated outputs must be preserved outside the source before fresh qualification; no automatic cleanup')
    return dict(schema=1, scope=SCOPE, source=source, uid=uid, gid=gid, configPath=str(config_path),
        pythonPath=config['argv'][0],
        swiftRuntimeOnly=only, macGeneratorOnly=clock_only, cliProcessOnly=cli_only,
        cliRemainingOnly=remaining_only, cliFirstCase=first_case, requestedPlan=plan,
        configSha256=digest(config_path), preparedSha256=digest(parent / 'prepared.json'),
        bootstrapSha256=digest(local.ROOT / 'scripts/with-darwin-audit-session.py'),
        persistentPrivilege=False, passwordCollected=False, bootstrapAutomaticallyRetried=False)


def authorize(parent, expected, local):
    request = preflight(parent, expected, local)
    python = Path(sys.executable)
    prepared_python = Path(request['pythonPath'])
    need(python.is_absolute() and python.resolve(strict=True) == prepared_python,
         'Python interpreter changed after prepared-command admission')
    argv = dialog_argv(prepared_python, local.ROOT / 'scripts/with-darwin-audit-session.py',
                       Path(request['configPath']), request['uid'], request['gid'])
    local.bootstrap.write_new(parent / 'gui-authorization-request.json', request)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    with os.fdopen(os.open(parent / 'gui-authorization.stdout', flags, 0o600), 'wb') as output, \
            os.fdopen(os.open(parent / 'gui-authorization.stderr', flags, 0o600), 'wb') as errors:
        # No shell=True, password stdin, background root process or sudo cache.
        # The OS displays its own authentication UI; cancel is never retried.
        process = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=output, stderr=errors, check=False)
    result_path = parent / 'state/private/result.json'
    record = dict(schema=1, scope=SCOPE, authorizationTransportExitCode=process.returncode,
        nativeResult=None, nativeResultPath=None, nativeResultSha256=None,
        nativeResultIndependentlyVerified=False, bootstrapAutomaticallyRetried=False)
    if result_path.is_file() and not result_path.is_symlink():
        result = local.runner.read_json(result_path)
        need(result['source'] == request['source'] and result['scope'] == local.SCOPE and
             result.get('swiftRuntimeOnly') is request['swiftRuntimeOnly'] and
             result.get('macGeneratorOnly') is request['macGeneratorOnly'] and
             result.get('cliProcessOnly') is request['cliProcessOnly'] and
             result.get('cliRemainingOnly') is request['cliRemainingOnly'] and
             'cliFirstCase' in result and result['cliFirstCase'] == request['cliFirstCase'] and
             result.get('requestedPlan') == request['requestedPlan'],
             'Native result belongs to a different qualification request')
        record.update(nativeResult=result['result'], nativeResultPath=str(result_path),
                      nativeResultSha256=digest(result_path))
    local.bootstrap.write_new(parent / 'gui-authorization-result.json', record)
    print(record)
    # An OS dialog's exit alone is never a native qualification pass. The agent
    # must independently inspect the saved native receipts and product results.
    return process.returncode if process.returncode else 0 if record['nativeResult'] == 'PASS' else 125


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-authorized-arm27', action='store_true')
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true', help='Read-only preflight; never show a dialog or run bootstrap')
    args = parser.parse_args()
    need(args.owner_authorized_arm27, 'Explicit owner authorization required')
    spec = importlib.util.spec_from_file_location('gui_local_arm_controller', ROOT / 'scripts/run-rpc-local-arm-qualification.py')
    local = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(local)
    if args.check_only:
        print(preflight(args.parent, args.expected_commit, local))
        return 0
    return authorize(args.parent, args.expected_commit, local)


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('One-shot Mac authorization refused: ' + str(error), file=sys.stderr)
        raise SystemExit(125)
