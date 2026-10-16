#!/usr/bin/env python3
"""Read-only hosted Intel Bonjour observations, never product/permission qualification.

No preference, service, audit session, process privilege, or security policy is changed.
Only the fixed Git queries and a service-registration read are executed. Raw output,
account/process identifiers, unrelated preferences and environment values are not exported.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import re
import selectors
import stat
import subprocess
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_bonjour_environment as bonjour
from audit_processes import host_role

SCOPE = 'READ_ONLY_INTEL_BONJOUR_ENVIRONMENT_NOT_QUALIFICATION'
OUTPUT = 'rpc-intel-bonjour-diagnostic.json'
LIMIT = 128 * 1024
COMMANDS = {
    'status': ['/usr/bin/git', '--no-optional-locks', 'status', '--porcelain=v1'],
    'commit': ['/usr/bin/git', '--no-optional-locks', 'rev-parse', 'HEAD'],
    'tree': ['/usr/bin/git', '--no-optional-locks', 'rev-parse', 'HEAD^{tree}'],
    'service': ['/bin/launchctl', 'print', bonjour.SERVICE],
}
ERRORS = {'ADMISSION', 'SOURCE_QUERY', 'SOURCE_DIRTY', 'SOURCE_MISMATCH', 'SOURCE_CHANGED',
          'COMMAND_BOUNDS', 'SYSTEM_OBSERVATION', 'OUTPUT_POLICY'}


class Refusal(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise Refusal(code)


def oid(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{40}', value) is not None and set(value) != {'0'}


def capture(label, deadline):
    """Bound reads and lifetime of one directly owned read-only command, not a product supervisor."""
    require(label in COMMANDS and time.monotonic() < deadline, 'COMMAND_BOUNDS')
    end = min(deadline, time.monotonic() + 10)
    env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'C', 'LC_ALL': 'C',
           'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_OPTIONAL_LOCKS': '0'}
    with subprocess.Popen(COMMANDS[label], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL) as child:
        try:
            data = bytearray()
            with selectors.DefaultSelector() as selector:
                selector.register(child.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    require(time.monotonic() < end, 'COMMAND_BOUNDS')
                    for key, _ in selector.select(min(0.1, max(0, end - time.monotonic()))):
                        chunk = os.read(key.fd, min(8192, LIMIT + 1 - len(data)))
                        data.extend(chunk)
                        require(len(data) <= LIMIT, 'COMMAND_BOUNDS')
                        if not chunk:
                            selector.unregister(key.fd)
            code = child.wait(timeout=max(0.001, end - time.monotonic()))
            require(time.monotonic() <= end, 'COMMAND_BOUNDS')
            return code, bytes(data)
        except subprocess.TimeoutExpired:
            raise Refusal('COMMAND_BOUNDS') from None
        finally:
            if child.poll() is None:
                child.kill()  # Retained, unreaped direct child only; never a discovered PID/service.
                child.wait(timeout=5)


def source_snapshot(deadline):
    values = {}
    for name in ('status', 'commit', 'tree'):
        code, raw = capture(name, deadline)
        require(code == 0, 'SOURCE_QUERY')
        try:
            values[name] = raw.decode('ascii').strip()
        except UnicodeError:
            raise Refusal('SOURCE_QUERY') from None
    require(values.pop('status') == '', 'SOURCE_DIRTY')
    require(all(oid(value) for value in values.values()), 'SOURCE_QUERY')
    return values


def admit(env):
    expected = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
                'GITHUB_REPOSITORY': 'p2pKit/P2pKit', 'GITHUB_EVENT_NAME': 'workflow_dispatch',
                'GITHUB_WORKFLOW': 'Intel iOS simulator tests', 'GITHUB_JOB': 'intel-environment-diagnostics',
                'RUNNER_OS': 'macOS', 'RUNNER_ARCH': 'X64'}
    require(all(env.get(key) == value for key, value in expected.items()), 'ADMISSION')
    require(re.fullmatch(r'refs/heads/work/rpc-[a-zA-Z0-9_-]+', env.get('GITHUB_REF', '')) is not None,
            'ADMISSION')
    require(oid(env.get('GITHUB_SHA')), 'ADMISSION')
    require(all(re.fullmatch('[1-9][0-9]{0,17}', env.get(key, '')) is not None
                for key in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')), 'ADMISSION')
    require(platform.system() == 'Darwin' and platform.machine() == 'x86_64' and
            host_role() == 'macos-x64', 'ADMISSION')
    require(os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() != 0, 'ADMISSION')
    require(Path(env.get('GITHUB_WORKSPACE', '')).resolve(strict=True) == ROOT, 'ADMISSION')
    return {'id': int(env['GITHUB_RUN_ID']), 'attempt': int(env['GITHUB_RUN_ATTEMPT'])}


def empty_report():
    return dict(schema=1, scope=SCOPE, status='REFUSED', source=None, run=None, context=None, bonjour=None,
                error=None, productExecuted=False, testsExecuted=0, configurationChanged=False,
                privilegesChanged=False, qualification='NOT_PERFORMED')


def collect(env):
    result = empty_report()
    deadline = time.monotonic() + 60
    try:
        result['run'] = admit(env)
        result['source'] = source_snapshot(deadline)
        require(result['source']['commit'] == env['GITHUB_SHA'], 'SOURCE_MISMATCH')
        console = Path('/dev/console').stat()
        require(stat.S_ISCHR(console.st_mode), 'SYSTEM_OBSERVATION')
        result['context'] = dict(nativeIntel=True, nonroot=True, consoleUserMatches=console.st_uid == os.getuid())
        # Reuse reviewed protected-file/reparse/owner/type checks, NOT its mutating preparation class.
        before_service = bonjour.read_service_configuration()
        try:
            values, policy, before = bonjour.read_preference()
        except bonjour.PreparationFailure as error:
            require(error.category == 'PREFERENCE_MISSING', 'SYSTEM_OBSERVATION')
            before = bonjour.absent_domain_observation()
            require(before == bonjour.absent_domain_observation(), 'SYSTEM_OBSERVATION')
            preference = 'DOMAIN_ABSENT'
        else:
            preference = 'TRUE' if values[bonjour.KEY] else 'FALSE'
            values_after, policy_after, after = bonjour.read_preference()
            require(before == after and policy == policy_after and values == values_after, 'SYSTEM_OBSERVATION')
        code, _ = capture('service', deadline)
        require(before_service == bonjour.read_service_configuration(), 'SYSTEM_OBSERVATION')
        result['bonjour'] = dict(preference=preference, protectedServiceConfigurationVerified=True,
                                 registration='PRESENT' if code == 0 else 'READ_UNAVAILABLE')
        require(source_snapshot(deadline) == result['source'], 'SOURCE_CHANGED')
        result['status'] = 'OBSERVED'
    except Refusal as error:
        result['error'] = str(error) if str(error) in ERRORS else 'SYSTEM_OBSERVATION'
    except Exception:
        result['error'] = 'SYSTEM_OBSERVATION'
    validate_report(result)
    return result


def validate_report(value):
    require(type(value) is dict and set(value) == set(empty_report()), 'OUTPUT_POLICY')
    require(type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE and
            value['status'] in ('OBSERVED', 'REFUSED') and value['qualification'] == 'NOT_PERFORMED' and
            value['productExecuted'] is False and type(value['testsExecuted']) is int and value['testsExecuted'] == 0 and
            value['configurationChanged'] is False and value['privilegesChanged'] is False, 'OUTPUT_POLICY')
    source, run = value['source'], value['run']
    require(source is None or type(source) is dict and set(source) == {'commit', 'tree'} and
            all(oid(item) for item in source.values()), 'OUTPUT_POLICY')
    require(run is None or type(run) is dict and set(run) == {'id', 'attempt'} and
            all(type(item) is int and 0 < item < 10**18 for item in run.values()), 'OUTPUT_POLICY')
    context, observed = value['context'], value['bonjour']
    require(context is None or type(context) is dict and
            set(context) == {'nativeIntel', 'nonroot', 'consoleUserMatches'} and
            context['nativeIntel'] is True and context['nonroot'] is True and
            type(context['consoleUserMatches']) is bool, 'OUTPUT_POLICY')
    require(observed is None or type(observed) is dict and
            set(observed) == {'preference', 'protectedServiceConfigurationVerified', 'registration'} and
            observed['preference'] in ('TRUE', 'FALSE', 'DOMAIN_ABSENT') and
            observed['protectedServiceConfigurationVerified'] is True and
            observed['registration'] in ('PRESENT', 'READ_UNAVAILABLE'), 'OUTPUT_POLICY')
    if value['status'] == 'OBSERVED':
        require(all(item is not None for item in (source, run, context, observed)) and value['error'] is None,
                'OUTPUT_POLICY')
    else:
        require(value['error'] in ERRORS, 'OUTPUT_POLICY')


def write_report(value, env):
    validate_report(value)
    parent = Path(env['RUNNER_TEMP'])
    bonjour.private.physical(parent)
    require(parent.is_dir() and parent.stat().st_uid == os.getuid(), 'OUTPUT_POLICY')
    path = parent / OUTPUT
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('ascii')
    require(len(raw) <= LIMIT, 'OUTPUT_POLICY')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)


def main():
    result = collect(os.environ)
    try:
        write_report(result, os.environ)
    except Exception:
        result.update(status='REFUSED', error='OUTPUT_POLICY')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'OBSERVED' else 1


if __name__ == '__main__':
    raise SystemExit(main())
