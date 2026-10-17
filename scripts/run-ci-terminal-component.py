#!/usr/bin/env python3
"""Run selected unchanged modular CI commands in an ordinary Terminal descendant.

TN3179 permits this CLI context; it does not diagnose the earlier NoRoute cause.
The native helper retains its original application/shell lease. No privacy
setting, audit executor, qualification policy or product deadline is changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import pwd
import re
import shlex
import signal
import subprocess
import sys
import tempfile
import threading
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import ci_evidence as evidence
import dependency_update as dependency

spec = importlib.util.spec_from_file_location('ci_terminal_helpers', ROOT / 'scripts/with-darwin-terminal-context.py')
terminal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(terminal)
private = terminal.private
COMPONENT = 'jmdns-diagnostic'
# Fixed existing component budgets only. No arbitrary command or duration.
PROFILES = {'jmdns-diagnostic': ('modular-jmdns', 1800), 'macos-shared': ('modular-shared', 7200),
            'consumers': ('modular-consumers', 7200),
            'published-consumers-diagnostic': ('modular-published-consumers', 7200),
            'dependency-generate': ('modular-dependency-generate', 10800)}


def bounds(component):
    require(component in PROFILES, 'COMPONENT')
    mode, seconds = PROFILES[component]
    return dict(mode=mode, command=seconds, child=seconds + 180, native=seconds + 240,
                controller=seconds + 300, wrapper=seconds + 450)


ENVIRONMENT = frozenset('''PATH LANG LC_ALL TMPDIR JAVA_HOME JAVA_HOME_17_X64 JAVA_HOME_21_X64
ANDROID_HOME ANDROID_SDK_ROOT DEVELOPER_DIR GRADLE_USER_HOME CI GITHUB_ACTIONS
RUNNER_ENVIRONMENT RUNNER_OS RUNNER_ARCH RUNNER_TEMP RUNNER_TRACKING_ID
GITHUB_REPOSITORY GITHUB_REF GITHUB_EVENT_NAME GITHUB_SHA GITHUB_WORKSPACE
GITHUB_WORKFLOW_REF GITHUB_WORKFLOW_SHA GITHUB_RUN_ID GITHUB_RUN_ATTEMPT GITHUB_JOB
CI_EVIDENCE_RECIPIENT_SHA256 CI_EVIDENCE_RECIPIENT_FINGERPRINT'''.split())
DEPENDENCY_ENVIRONMENT = frozenset({'DEPENDENCY_UPDATE_REQUEST', 'P2PKIT_CI_COMMAND_DEADLINE_NS',
    evidence.audit_processes.JOB_ENV, evidence.audit_processes.CHAIN_ENV, evidence.audit_processes.DOMAINS_ENV,
    evidence.audit_processes.STATE_ENV, evidence.audit_processes.PIPE_ENV})


class ContextFailure(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise ContextFailure(code)


def dependency_request(env):
    try:
        request = json.loads(env.get('DEPENDENCY_UPDATE_REQUEST', ''))
    except (ValueError, TypeError):
        raise ContextFailure('DEPENDENCY_REQUEST') from None
    require(type(request) is dict and set(request) == {'controller_sha', 'controller_tree',
        'candidate_sha', 'candidate_tree', 'dependency_base_sha'} and
        all(type(value) is str and re.fullmatch('[0-9a-f]{40}', value) for value in request.values()), 'DEPENDENCY_REQUEST')
    return request


def dependency_deadline(env):
    value = env.get('P2PKIT_CI_COMMAND_DEADLINE_NS', '')
    require(type(value) is str and re.fullmatch('[1-9][0-9]{0,19}', value) is not None, 'DEPENDENCY_DEADLINE')
    deadline = int(value) / 1_000_000_000
    require(0 < deadline - time.monotonic() <= 10800, 'DEPENDENCY_DEADLINE')
    return deadline


def environment_admit(env, component=COMPONENT):
    require(component in PROFILES, 'COMPONENT')
    generating = component == 'dependency-generate'
    events = {'workflow_dispatch'} if component in {'jmdns-diagnostic', 'published-consumers-diagnostic',
                                                   'dependency-generate'} else {'workflow_dispatch', 'push', 'pull_request', 'schedule'}
    workflow = 'dependency-update-candidate.yml' if generating else 'ci.yml'
    require(platform.system() == 'Darwin' and platform.machine() == 'x86_64' and
            env.get('RUNNER_OS') == 'macOS' and env.get('RUNNER_ARCH') == 'X64' and
            env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
            env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_EVENT_NAME') in events and
            env.get('GITHUB_WORKFLOW_REF', '').startswith('p2pKit/P2pKit/.github/workflows/' + workflow + '@') and
            re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')) is not None and
            env.get('GITHUB_WORKFLOW_SHA') == env.get('GITHUB_SHA'), 'HOST_CONTEXT')
    workspace = Path(env.get('GITHUB_WORKSPACE', '')).resolve(strict=True)
    require((workspace / 'candidate' if generating else workspace) == ROOT, 'SOURCE_PATH')
    require(re.fullmatch('[A-Za-z0-9_-]{1,200}', env.get('RUNNER_TRACKING_ID', '')) is not None,
            'RUNNER_TRACKING')
    if generating:
        request = dependency_request(env)
        require(env.get('GITHUB_JOB') == 'generate' and env['GITHUB_SHA'] == request['controller_sha'], 'DEPENDENCY_REQUEST')
        audit = evidence.audit_processes
        domains = audit.ownership_domains(env.get(audit.CHAIN_ENV, ''), env.get(audit.DOMAINS_ENV, ''))
        require(bool(domains) and env.get(audit.JOB_ENV) == domains[-1]['job'] and
            env.get(audit.STATE_ENV) == domains[-1]['state'] and env.get('GRADLE_USER_HOME') == domains[-1]['home'] and
            {key for key in env if key.startswith('P2PKIT_AUDIT_')} ==
            {audit.JOB_ENV, audit.CHAIN_ENV, audit.DOMAINS_ENV, audit.STATE_ENV, audit.PIPE_ENV}, 'NESTED_DOMAIN')
        dependency_deadline(env)
    else:
        require(not any(key.startswith('P2PKIT_AUDIT_') for key in env), 'NESTED_DOMAIN')


def begin_source(component, env):
    if component != 'dependency-generate':
        return private.source_snapshot(), None
    request = dependency_request(env)
    source = {'commit': request['candidate_sha'], 'tree': request['candidate_tree']}
    dependency.source(ROOT, source['commit'], source['tree'])
    return source, dependency.snapshot(ROOT)


def finish_source(component, source, before):
    if component != 'dependency-generate':
        require(private.source_snapshot() == source, 'SOURCE_CHANGED')
        return
    dependency.source(ROOT, source['commit'], source['tree'], clean=False)
    dependency.changes(before, dependency.snapshot(ROOT), dependency.git(ROOT, 'diff', '--cached', '--binary'),
                       dependency.git(ROOT, 'ls-files', '--others', '--exclude-standard', '-z'))


def command(env, component=COMPONENT):
    budget = bounds(component)
    if component == 'dependency-generate':
        return [str(ROOT / 'gradlew'), 'resolveAndLockAll', '--write-locks', '--write-verification-metadata',
                'sha256', '--continue', '--no-configure-on-demand', '--no-daemon', '--console=plain']
    python = str(Path(sys.executable).resolve())
    return [python, '-B', str(ROOT / 'scripts/ci_evidence.py'), '--component', component,
            '--timeout-seconds', str(budget['command']), '--source-root', str(ROOT), '--output-dir',
            str(Path(env['RUNNER_TEMP']) / ('ci-evidence-' + component)),
            '--report-glob', '**/build/test-results/**/*.xml', '--report-glob', 'build/reports/**/*',
            '--', python, '-B', str(ROOT / 'scripts/ci_component.py'), component]


def validate_config(config, directory):
    require(type(config) is dict and set(config) == {'uid', 'gid', 'groups', 'source', 'environment', 'component'}, 'CONFIG')
    require(type(config['uid']) is int and type(config['gid']) is int and
            os.getuid() == os.geteuid() == config['uid'] > 0 and
            os.getgid() == os.getegid() == config['gid'] > 0 and
            config['groups'] == sorted(set(os.getgroups())), 'CREDENTIALS')
    env = config['environment']
    require(type(env) is dict and set(env) <= (ENVIRONMENT | (DEPENDENCY_ENVIRONMENT if config['component'] == 'dependency-generate' else frozenset())) and 'PATH' in env and
            all(type(v) is str and '\0' not in v and len(v) <= 32768 for v in env.values()), 'ENVIRONMENT')
    environment_admit(env, config['component'])
    require(os.environ.get('RUNNER_TRACKING_ID') == env['RUNNER_TRACKING_ID'], 'RUNNER_TRACKING')
    require(directory.parent == Path(env['RUNNER_TEMP']).resolve(strict=True) and
            directory.name.startswith('ci-terminal-'), 'PRIVATE_DIRECTORY')
    private.private_parent(directory, os.getuid())
    source = config['source']
    require(type(source) is dict and set(source) == {'commit', 'tree'} and
            all(type(v) is str and re.fullmatch('[0-9a-f]{40}', v) for v in source.values()) and
            source['commit'] == (dependency_request(env)['candidate_sha'] if config['component'] == 'dependency-generate'
                                 else env['GITHUB_SHA']), 'SOURCE_IDENTITY')


def command_bytes(directory):
    argv = [str(Path(sys.executable).resolve()), '-I', '-B', '-S', str(Path(__file__).resolve()),
            '--child', str(directory / 'config.json')]
    return ('#!/bin/bash\numask 077\n' + shlex.join(argv) + ' </dev/null >' +
            shlex.quote(str(directory / 'child.stdout.log')) + ' 2>' +
            shlex.quote(str(directory / 'child.stderr.log')) + '\nstatus=$?\n' +
            'printf \'%s\\n\' "$status" >' + shlex.quote(str(directory / 'shell-result.txt')) +
            '\nexit "$status"\n').encode()


def cancel_file(directory):
    path = directory / 'cancel'
    if not path.exists():
        private.write_new(path, b'cancel\n')


def wait_evidence(process, directory, cancelled, deadline):
    """Only the retained, unreaped direct child is signalled; never a PID lookup."""
    requested = False
    stop_at = deadline
    while True:
        code = process.poll()
        now = time.monotonic()
        stopping = cancelled.is_set() or (directory / 'cancel').exists() or now >= deadline
        if code is not None:
            require(not stopping and not requested, 'CANCELLED')
            require(code in (0, 1), 'CHILD_EXIT')
            return code
        if stopping and not requested:
            requested = True
            process.send_signal(signal.SIGTERM)
            stop_at = min(deadline + 60, now + 60)
        if requested and now >= stop_at:
            # Unknown retirement is failure. Do not kill the collector beneath
            # its owned Gradle cleanup or claim its descendants have exited.
            raise ContextFailure('CHILD_RETIREMENT_UNKNOWN')
        time.sleep(0.1)


def child(path):
    directory = path.parent
    config = private.read_json(path)
    validate_config(config, directory)
    source = config['source']
    budget = bounds(config['component'])
    observed, before = begin_source(config['component'], config['environment'])
    require(observed == source, 'SOURCE_CHANGED')
    ancestry = terminal.terminal_ancestor(directory, source)
    private.write_json(directory / 'child-admission.json', {'source': source, 'ancestry': ancestry})
    account = pwd.getpwuid(os.getuid())
    env = {**config['environment'], 'HOME': account.pw_dir, 'USER': account.pw_name, 'LOGNAME': account.pw_name,
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUNBUFFERED': '1'}
    if config['component'] == 'published-consumers-diagnostic':
        # Match the immutable remote script's own future Gradle home BEFORE
        # the collector creates its domain; keep borrowed work new/empty.
        for name in ('home', 'tmp'):
            (directory / name).mkdir(mode=0o700)
        work = directory / 'consumer'
        require(not work.exists(), 'CONSUMER_WORK')
        env.update(HOME=str(directory / 'home'), TMPDIR=str(directory / 'tmp'),
                   P2PKIT_CONSUMER_WORK_DIR=str(work), GRADLE_USER_HOME=str(work / 'gradle-home'))
    cancelled = threading.Event()
    previous = {sig: signal.signal(sig, lambda _s, _f: cancelled.set()) for sig in (signal.SIGINT, signal.SIGTERM)}
    process, code, source_checked = None, 125, False
    try:
        require(not (directory / 'cancel').exists(), 'CANCELLED')
        if config['component'] == 'dependency-generate':
            remaining = dependency_deadline(env) - time.monotonic() - 450
            require(remaining > 0, 'DEPENDENCY_DEADLINE')
            reports = ROOT / 'build/reports/dependency-generation'
            reports.parent.mkdir(parents=True, exist_ok=True)
            outcome = evidence.run_command(command(env, config['component']), cwd=ROOT, environment=env,
                private=reports, timeout=remaining, cancelled=lambda: cancelled.is_set() or (directory / 'cancel').exists())
            private.write_json(reports / 'result.json', outcome)
            code = 0 if outcome['code'] == 'PASS' else 1
            require(outcome['cleanupKnown'] and outcome['capturesClosed'], 'GENERATION_CLEANUP')
        else:
            deadline = time.monotonic() + budget['child']
            process = subprocess.Popen(command(env, config['component']), cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
            code = wait_evidence(process, directory, cancelled, deadline)
        finish_source(config['component'], source, before)
        source_checked = True
        require(not cancelled.is_set() and not (directory / 'cancel').exists(), 'CANCELLED')
    except BaseException:
        code = 125
        raise
    finally:
        # On observation/validation exceptions still request original collector
        # finalization, without overriding the first failure or guessing PIDs.
        if process is not None and process.poll() is None:
            cancelled.set()
            try:
                wait_evidence(process, directory, cancelled, time.monotonic() + 60)
            except Exception:
                code = 125
        try:
            if not source_checked:
                finish_source(config['component'], source, before)
        except BaseException:
            code = 125
        for sig, handler in previous.items():
            signal.signal(sig, handler)
        private.write_json(directory / 'child-result.json', {'source': source, 'exitCode': code})
    return code


def wait_controller(process, directory, cancelled, deadline):
    requested = False
    while process.poll() is None:
        if cancelled.is_set() and not requested:
            cancel_file(directory)
            requested = True
        require(time.monotonic() < deadline, 'CONTROLLER_RETIREMENT_UNKNOWN')
        time.sleep(0.1)
    require(time.monotonic() < deadline, 'CONTROLLER_RETIREMENT_UNKNOWN')
    return process.returncode


def validate_result(app, admission, finished, source, code, component=COMPONENT):
    require(type(app) is dict and set(app) == {'schema', 'executionMode', 'stage', 'exitCode',
            *terminal.OBSERVATIONS, *terminal.APPLICATION_FLAGS} and type(app.get('schema')) is int and
            app['schema'] == 3 and app.get('executionMode') == bounds(component)['mode'] and
            app.get('stage') == 'FINALIZED' and app.get('failureCheck') == 'NONE' and
            app.get('openErrorDomain') == 'NONE' and app.get('openErrorCode') == 0 and
            all(app.get(key) is True for key in terminal.APPLICATION_FLAGS), 'APPLICATION_FINALIZATION')
    require(type(code) is int and code in (0, 1) and type(app.get('exitCode')) is int and app['exitCode'] == code and
            finished == {'source': source, 'exitCode': code}, 'RESULT_IDENTITY')
    require(type(admission) is dict and set(admission) == {'source', 'ancestry'} and admission['source'] == source,
            'CHILD_ADMISSION')
    terminal.validate_ancestry(admission['ancestry'])


def run(component=COMPONENT):
    start = time.monotonic()
    budget = bounds(component)
    environment_admit(os.environ, component)
    generating = component == 'dependency-generate'
    allowed = ENVIRONMENT | (DEPENDENCY_ENVIRONMENT if generating else frozenset())
    env = {key: value for key, value in os.environ.items() if key in allowed}
    outer_end = dependency_deadline(env) if generating else start + budget['wrapper']
    require(not generating or outer_end - start > 450, 'DEPENDENCY_DEADLINE')
    directory = Path(tempfile.mkdtemp(prefix='ci-terminal-', dir=Path(env['RUNNER_TEMP']).resolve(strict=True)))
    source, before = begin_source(component, env)
    config = dict(uid=os.getuid(), gid=os.getgid(), groups=sorted(set(os.getgroups())), source=source, environment=env, component=component)
    validate_config(config, directory)
    private.write_json(directory / 'config.json', config)
    script = command_bytes(directory)
    command_path = directory / 'native.command'
    private.write_new(command_path, script)
    command_path.chmod(0o700)
    cancelled = threading.Event()
    previous = {sig: signal.signal(sig, lambda _s, _f: cancelled.set()) for sig in (signal.SIGINT, signal.SIGTERM)}
    process, code, failed = None, 125, None
    try:
        binary = directory / 'terminal-context'
        compile_result = evidence.run_command(['/usr/bin/xcrun', '--sdk', 'macosx', 'clang', '-Wall', '-Wextra',
            '-Werror', '-fobjc-arc', '-fblocks', '-arch', 'x86_64', '-mmacosx-version-min=15.0',
            '-DP2PKIT_MODULAR_CI', '-framework', 'AppKit', str(ROOT / 'scripts/diagnostics/apple-terminal-context.m'),
            '-o', str(binary)], cwd=ROOT, environment=env, private=directory / 'compile',
            timeout=90, cancelled=cancelled.is_set)
        require(compile_result['code'] == 'PASS' and compile_result['cleanupKnown'] and
                compile_result['capturesClosed'], 'COMPILE_FAILED')
        require(not cancelled.is_set(), 'CANCELLED')
        with (directory / 'application.log').open('xb') as log:
            process = subprocess.Popen([str(binary), str(directory), budget['mode']], cwd=ROOT, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
            code = wait_controller(process, directory, cancelled, min(outer_end - 60, time.monotonic() + budget['controller']))
        validate_result(private.read_json(directory / 'application-result.json'),
                        private.read_json(directory / 'child-admission.json'),
                        private.read_json(directory / 'child-result.json'), source, code, component)
    except BaseException as error:
        failed = error
    finally:
        try:
            if process is not None and process.poll() is None:
                # Preserve the native retained lease long enough to attempt
                # ordinary finalization; never signal a reconstructed PID.
                cancel_file(directory)
                wait_controller(process, directory, cancelled, outer_end - 45)
        except BaseException as error:
            failed = failed or error
        try:
            finish_source(component, source, before)
            require(time.monotonic() < outer_end - (30 if generating else 0), 'WRAPPER_DEADLINE')
            require(not cancelled.is_set(), 'CANCELLED')
        except BaseException as error:
            failed = failed or error
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if failed is not None:
        raise failed
    require(not command_path.is_symlink() and command_path.read_bytes() == script, 'COMMAND_CHANGED')
    command_path.unlink()
    # This independent wrapper result is required by the Actions job. The inner
    # manifest cannot make a failed application/source finalization job succeed.
    print('CI_TERMINAL FINALIZED ' + ('PASS' if code == 0 else 'COMPONENT_FAILED'))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--component', choices=tuple(PROFILES))
    args = parser.parse_args()
    os.umask(0o077)
    try:
        require(not args.child or args.component is None, 'COMPONENT')
        return child(args.child) if args.child else run(args.component or COMPONENT)
    except BaseException as error:
        # Only our finite labels are public; imported native/private exceptions
        # never expose a path, environment value, address or private log.
        print('CI_TERMINAL FAIL ' + (str(error) if type(error) is ContextFailure else 'CONTEXT_FAILURE'), file=sys.stderr)
        return 125


if __name__ == '__main__':
    raise SystemExit(main())
