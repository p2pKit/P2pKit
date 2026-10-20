#!/usr/bin/env python3
"""Run selected unchanged modular CI commands in an ordinary Terminal descendant.

TN3179 permits this CLI context; it does not diagnose the earlier NoRoute cause.
The native helper retains its original application/shell lease. No privacy
setting, audit executor, qualification policy or product deadline is changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import hashlib
import math
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
APPLE_COMPONENT = 'apple-swift-jvm-transfer'
# Fixed existing component budgets only. No arbitrary command or duration.
PROFILES = {'jmdns-diagnostic': ('modular-jmdns', 1800), 'macos-shared': ('modular-shared', 7200),
            'consumers': ('modular-consumers', 7200),
            'published-consumers-diagnostic': ('modular-published-consumers', 7200),
            'dependency-generate': ('modular-dependency-generate', 10800),
            'release-consumers': ('modular-release-consumers', 7200),
            APPLE_COMPONENT: ('modular-apple-swift-jvm-transfer', 16200)}


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
APPLE_ENVIRONMENT = frozenset({'APPLE_ISSUE_PARENT', 'P2PKIT_AUDIT_JDK21'})


RELEASE_ENVIRONMENT = frozenset({'HOME', 'SDKROOT', 'P2PKIT_CONSUMER_REPOSITORY_URL', 'P2PKIT_CONSUMER_PROFILE',
    'P2PKIT_CONSUMER_WORK_DIR', 'P2PKIT_CI_COMMAND_DEADLINE_NS'})
RELEASE_SDK_ENVIRONMENT = frozenset({'PATH', 'JAVA_HOME', 'ANDROID_HOME', 'ANDROID_SDK_ROOT', 'DEVELOPER_DIR',
    'SDKROOT', 'HOME', 'TMPDIR', 'LANG', 'LC_ALL', 'CI', 'P2PKIT_CONSUMER_REPOSITORY_URL',
    'P2PKIT_CONSUMER_PROFILE', 'P2PKIT_CONSUMER_WORK_DIR'})


class ContextFailure(RuntimeError):
    pass


def require(condition, code):
    if not condition:
        raise ContextFailure(code)


def apple_parent(env):
    parent = Path(env.get('APPLE_ISSUE_PARENT', ''))
    private.private_parent(parent, os.getuid())
    require(parent.parent == Path(env['RUNNER_TEMP']).resolve(strict=True) and
            re.fullmatch(r'apple-issue-validation\.[A-Za-z0-9_-]+', parent.name) is not None, 'APPLE_STATE')
    return parent


def allowed_environment(component):
    return ENVIRONMENT | (DEPENDENCY_ENVIRONMENT if component == 'dependency-generate' else
        RELEASE_ENVIRONMENT if component == 'release-consumers' else
        APPLE_ENVIRONMENT if component == APPLE_COMPONENT else frozenset())


def dependency_request(env):
    try:
        request = json.loads(env.get('DEPENDENCY_UPDATE_REQUEST', ''))
    except (ValueError, TypeError):
        raise ContextFailure('DEPENDENCY_REQUEST') from None
    require(type(request) is dict and set(request) == {'controller_sha', 'controller_tree',
        'candidate_sha', 'candidate_tree', 'dependency_base_sha'} and
        all(type(value) is str and re.fullmatch('[0-9a-f]{40}', value) for value in request.values()), 'DEPENDENCY_REQUEST')
    return request


def command_deadline(env, maximum, code):
    value = env.get('P2PKIT_CI_COMMAND_DEADLINE_NS', '')
    require(type(value) is str and re.fullmatch('[1-9][0-9]{0,19}', value) is not None, code)
    deadline = int(value) / 1_000_000_000
    require(0 < deadline - time.monotonic() <= maximum, code)
    return deadline


def dependency_deadline(env):
    return command_deadline(env, 10800, 'DEPENDENCY_DEADLINE')


def release_context(env):
    workspace = Path(env.get('GITHUB_WORKSPACE', '')).resolve(strict=True)
    workflow, separator, ref = env.get('GITHUB_WORKFLOW_REF', '').partition('@')
    if workflow == 'p2pKit/P2pKit/.github/workflows/publish-maven-central.yml':
        require(separator == '@' and ref == env.get('GITHUB_REF') and ref.startswith('refs/tags/v') and
                env.get('GITHUB_EVENT_NAME') == 'push' and env.get('GITHUB_JOB') == 'publish-release' and
                ROOT == workspace, 'RELEASE_CONTEXT')
        return workspace, 9000
    require(workflow == 'p2pKit/P2pKit/.github/workflows/recover-maven-central.yml' and
            separator == '@' and ref == env.get('GITHUB_REF') == 'refs/heads/main' and
            env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch' and env.get('GITHUB_JOB') == 'verify-recovery' and
            ROOT == workspace / 'controller', 'RELEASE_CONTEXT')
    return workspace / 'original', 5400


def release_deadline(env):
    return command_deadline(env, release_context(env)[1], 'RELEASE_DEADLINE')


def release_source_check(released, env):
    require(type(released) is dict and set(released) == {'source', 'directory', 'script'}, 'RELEASE_INPUT')
    source = released['source']
    require(type(source) is dict and set(source) == {'commit', 'tree'} and
            all(type(value) is str and re.fullmatch('[0-9a-f]{40}', value) for value in source.values()), 'SOURCE_IDENTITY')
    original, _ = release_context(env)
    dependency.source(original, source['commit'], source['tree'])
    # Reuse canonical version parsing; this release-only import is not part of
    # dependency generation. Never run current-main fixtures for an old release.
    import application_release_version
    version = application_release_version.repository_version(original)['canonicalVersion']
    require(not version.endswith('-SNAPSHOT') and
            dependency.read(original / 'gradle.properties').decode().splitlines().count('GROUP=io.github.apdelrahman1911') == 1,
            'RELEASE_VERSION')
    if env['GITHUB_JOB'] == 'publish-release':
        require(source['commit'] == env['GITHUB_SHA'] and env['GITHUB_REF'] == 'refs/tags/v' + version, 'RELEASE_VERSION')
    raw = dependency.read(original / 'scripts/check-published-consumers.sh')
    require(released['script'] == {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'RELEASE_SCRIPT')
    directory = Path(released['directory'])
    private.private_parent(directory, os.getuid())
    require(Path(env['RUNNER_TEMP']).resolve(strict=True) in directory.parents and
            env.get('HOME') == str(directory / 'home') and env.get('TMPDIR') == str(directory / 'tmp') and
            env.get('P2PKIT_CONSUMER_WORK_DIR') == str(directory / 'consumer') and
            env.get('GRADLE_USER_HOME') == str(directory / 'consumer/gradle-home') and
            env.get('P2PKIT_CONSUMER_REPOSITORY_URL') == 'https://repo.maven.apache.org/maven2' and
            env.get('P2PKIT_CONSUMER_PROFILE') == 'complete', 'RELEASE_ENVIRONMENT')
    for name in ('home', 'tmp'):
        private.private_parent(directory / name, os.getuid())
    release_deadline(env)
    return directory


def release_outcome(directory):
    """Join only closed captures after independent native/source finalization."""
    captures = directory / 'capture'
    outcome = private.read_json(captures / 'result.json')
    require(evidence.public_outcome(outcome) is not None and outcome.get('cleanupKnown') is True and
            outcome.get('capturesClosed') is True, 'RELEASE_CLEANUP')
    paths = [captures / name for name in ('stdout.log', 'stderr.log')]
    for path in paths:
        private.physical(path)
        require(path.is_file(), 'RELEASE_LOG')
    require(sum(path.stat().st_size for path in paths) <= evidence.MAX_LOG_BYTES, 'RELEASE_LOG')
    with (directory / 'command.log').open('xb') as output:
        os.chmod(directory / 'command.log', 0o600)
        total = 0
        for path in paths:
            with path.open('rb') as stream:
                while block := stream.read(64 * 1024):
                    total += len(block)
                    require(total <= evidence.MAX_LOG_BYTES, 'RELEASE_LOG')
                    output.write(block)
    return outcome


def run_release_consumers(source_root, source_identity, environment, directory, deadline):
    """Closed in-process API; caller retains its exact approval/provider clock."""
    require(type(environment) is dict and set(environment) <= RELEASE_SDK_ENVIRONMENT and
            all(type(value) is str and '\0' not in value for value in environment.values()), 'RELEASE_ENVIRONMENT')
    require(type(deadline) in (int, float) and math.isfinite(deadline), 'RELEASE_DEADLINE')
    # Add only nonsecret hosted identity, never the caller's GH/Central/signing
    # credentials or ambient Gradle/JVM options. Fresh caller HOME/TMP stay exact.
    identity = {key: value for key, value in os.environ.items() if key in ENVIRONMENT and
                (key.startswith(('GITHUB_', 'RUNNER_')) or key == 'GITHUB_ACTIONS')}
    env = {**environment, **identity, 'P2PKIT_CI_COMMAND_DEADLINE_NS': str(int(deadline * 1_000_000_000)),
           'GRADLE_USER_HOME': str(Path(directory) / 'consumer/gradle-home')}
    environment_admit(env, 'release-consumers')
    original, _ = release_context(env)
    require(Path(source_root) == original, 'SOURCE_PATH')
    raw = dependency.read(original / 'scripts/check-published-consumers.sh')
    released = {'source': source_identity, 'directory': str(directory),
                'script': {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}}
    release_source_check(released, env)
    require(not (Path(directory) / 'consumer').exists() and not (Path(directory) / 'capture').exists(), 'CONSUMER_WORK')
    return run('release-consumers', released=released, environment=env)


def environment_admit(env, component=COMPONENT):
    require(component in PROFILES, 'COMPONENT')
    generating = component == 'dependency-generate'
    releasing = component == 'release-consumers'
    apple = component == APPLE_COMPONENT
    events = {'workflow_dispatch'} if component in {'jmdns-diagnostic', 'published-consumers-diagnostic',
                                                   'dependency-generate', APPLE_COMPONENT} else {'workflow_dispatch', 'push', 'pull_request', 'schedule'}
    workflow = 'dependency-update-candidate.yml' if generating else 'ci.yml'
    if releasing:
        release_context(env)
        workflow = 'publish-maven-central.yml' if env['GITHUB_JOB'] == 'publish-release' else 'recover-maven-central.yml'
        events = {'push'} if env['GITHUB_JOB'] == 'publish-release' else {'workflow_dispatch'}
    require(platform.system() == 'Darwin' and platform.machine() == ('arm64' if apple else 'x86_64') and
            env.get('RUNNER_OS') == 'macOS' and env.get('RUNNER_ARCH') == ('ARM64' if apple else 'X64') and
            env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
            env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_EVENT_NAME') in events and
            env.get('GITHUB_WORKFLOW_REF', '').startswith('p2pKit/P2pKit/.github/workflows/' + workflow + '@') and
            re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')) is not None and
            env.get('GITHUB_WORKFLOW_SHA') == env.get('GITHUB_SHA'), 'HOST_CONTEXT')
    workspace = Path(env.get('GITHUB_WORKSPACE', '')).resolve(strict=True)
    require(releasing or (workspace / 'candidate' if generating else workspace) == ROOT, 'SOURCE_PATH')
    require(re.fullmatch('[A-Za-z0-9_-]{1,200}', env.get('RUNNER_TRACKING_ID', '')) is not None,
            'RUNNER_TRACKING')
    if apple:
        require(platform.mac_ver()[0].split('.')[0] == '26' and env.get('GITHUB_JOB') == 'native' and
                env.get('GITHUB_WORKFLOW_REF') == 'p2pKit/P2pKit/.github/workflows/ci.yml@' + env.get('GITHUB_REF', '') and
                env.get('GITHUB_REF', '').startswith('refs/heads/'), 'APPLE_CONTEXT')
        apple_parent(env)
        require(bool(env.get('P2PKIT_AUDIT_JDK21')) and Path(env['P2PKIT_AUDIT_JDK21']).is_absolute(), 'APPLE_JDK')
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
        require({key for key in env if key.startswith('P2PKIT_AUDIT_')} ==
                ({'P2PKIT_AUDIT_JDK21'} if apple else set()), 'NESTED_DOMAIN')
        if releasing:
            release_deadline(env)


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
    if component == APPLE_COMPONENT:
        state = apple_parent(env) / 'state'
        require(not state.exists() and not state.is_symlink(), 'APPLE_STATE_EXISTS')
        return [str(Path(sys.executable).resolve()), '-B', str(ROOT / 'scripts/run-apple-issue-validation.py'),
                'run', '--state', str(state), '--operation', 'swift-jvm-transfer']
    if component == 'release-consumers':
        return ['bash', str(release_context(env)[0] / 'scripts/check-published-consumers.sh')]
    if component == 'dependency-generate':
        return [str(ROOT / 'gradlew'), 'resolveAndLockAll', '--write-locks', '--write-verification-metadata',
                'sha256', '--continue', '--no-configure-on-demand', '--no-daemon',
                '--max-workers=2', '--no-parallel', '--console=plain']
    python = str(Path(sys.executable).resolve())
    return [python, '-B', str(ROOT / 'scripts/ci_evidence.py'), '--component', component,
            '--timeout-seconds', str(budget['command']), '--source-root', str(ROOT), '--output-dir',
            str(Path(env['RUNNER_TEMP']) / ('ci-evidence-' + component)),
            '--report-glob', '**/build/test-results/**/*.xml', '--report-glob', 'build/reports/**/*',
            '--', python, '-B', str(ROOT / 'scripts/ci_component.py'), component]


def validate_config(config, directory):
    releasing = type(config) is dict and config.get('component') == 'release-consumers'
    require(type(config) is dict and set(config) == ({'uid', 'gid', 'groups', 'source', 'environment', 'component'} |
            ({'release'} if releasing else set())), 'CONFIG')
    require(type(config['uid']) is int and type(config['gid']) is int and
            os.getuid() == os.geteuid() == config['uid'] > 0 and
            os.getgid() == os.getegid() == config['gid'] > 0 and
            config['groups'] == sorted(set(os.getgroups())), 'CREDENTIALS')
    env = config['environment']
    require(type(env) is dict and set(env) <= allowed_environment(config['component']) and 'PATH' in env and
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
    if releasing:
        release_source_check(config['release'], env)


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
    releasing = config['component'] == 'release-consumers'
    env = {**config['environment'], 'HOME': config['environment']['HOME'] if releasing else account.pw_dir, 'USER': account.pw_name, 'LOGNAME': account.pw_name,
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
        if config['component'] == 'dependency-generate' or releasing:
            remaining = (release_deadline(env) if releasing else dependency_deadline(env)) - time.monotonic() - 450
            require(remaining > 0, 'RELEASE_DEADLINE' if releasing else 'DEPENDENCY_DEADLINE')
            if releasing:
                reports = Path(config['release']['directory']) / 'capture'
                cwd, _ = release_context(env)
                require(not (Path(config['release']['directory']) / 'consumer').exists(), 'CONSUMER_WORK')
                remaining = min(7200, remaining)
            else:
                reports, cwd = ROOT / 'build/reports/dependency-generation', ROOT
                reports.parent.mkdir(parents=True, exist_ok=True)
            options = {'create_gradle_home': False} if releasing else {}
            outcome = evidence.run_command(command(env, config['component']), cwd=cwd, environment=env,
                private=reports, timeout=remaining, cancelled=lambda: cancelled.is_set() or (directory / 'cancel').exists(), **options)
            private.write_json(reports / 'result.json', outcome)
            code = 0 if outcome['code'] == 'PASS' else 1
            require(outcome['cleanupKnown'] and outcome['capturesClosed'], 'RELEASE_CLEANUP' if releasing else 'GENERATION_CLEANUP')
        else:
            deadline = time.monotonic() + budget['child']
            process = subprocess.Popen(command(env, config['component']), cwd=ROOT, env=env, stdin=subprocess.DEVNULL)
            code = wait_evidence(process, directory, cancelled, deadline)
        finish_source(config['component'], source, before)
        if releasing:
            release_source_check(config['release'], env)
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
                if releasing:
                    release_source_check(config['release'], env)
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


def run(component=COMPONENT, *, released=None, environment=None):
    start = time.monotonic()
    budget = bounds(component)
    original_env = os.environ if environment is None else environment
    environment_admit(original_env, component)
    generating, releasing = component == 'dependency-generate', component == 'release-consumers'
    require(releasing == (released is not None), 'RELEASE_INPUT')
    allowed = allowed_environment(component)
    env = {key: value for key, value in original_env.items() if key in allowed}
    outer_end = dependency_deadline(env) if generating else release_deadline(env) if releasing else start + budget['wrapper']
    require(not (generating or releasing) or outer_end - start > 450, 'RELEASE_DEADLINE' if releasing else 'DEPENDENCY_DEADLINE')
    directory = Path(tempfile.mkdtemp(prefix='ci-terminal-', dir=Path(env['RUNNER_TEMP']).resolve(strict=True)))
    source, before = begin_source(component, env)
    config = dict(uid=os.getuid(), gid=os.getgid(), groups=sorted(set(os.getgroups())), source=source, environment=env, component=component)
    if releasing:
        config['release'] = released
    validate_config(config, directory)
    private.write_json(directory / 'config.json', config)
    if component == APPLE_COMPONENT:
        private.write_json(apple_parent(env) / 'terminal-context.json',
            {'schema': 1, 'component': component, 'source': source, 'directory': str(directory)})
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
            '-Werror', '-fobjc-arc', '-fblocks', '-arch', 'arm64' if component == APPLE_COMPONENT else 'x86_64',
            '-mmacosx-version-min=26.0' if component == APPLE_COMPONENT else '-mmacosx-version-min=15.0',
            '-DP2PKIT_MODULAR_CI', '-framework', 'AppKit', str(ROOT / 'scripts/diagnostics/apple-terminal-context.m'),
            '-o', str(binary)], cwd=ROOT, environment=env, private=directory / 'compile',
            timeout=90, cancelled=cancelled.is_set, **({'create_gradle_home': False} if releasing else {}))
        if component == APPLE_COMPONENT:
            private.write_json(directory / 'compile-result.json', compile_result)
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
            if releasing:
                release_source_check(released, env)
            require(time.monotonic() < outer_end - (30 if generating or releasing else 0), 'WRAPPER_DEADLINE')
            require(not cancelled.is_set(), 'CANCELLED')
        except BaseException as error:
            failed = failed or error
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    if failed is None:
        try:
            require(not command_path.is_symlink() and command_path.read_bytes() == script, 'COMMAND_CHANGED')
            command_path.unlink()
        except BaseException as error:
            failed = error
    if component == APPLE_COMPONENT:
        try:
            private.write_json(directory / 'wrapper-result.json', {'schema': 1, 'component': component,
                'source': source, 'finalExitCode': code if failed is None else 125,
                'finalized': failed is None, 'commandRemoved': not command_path.exists()})
        except BaseException as error:
            failed = failed or error
    if failed is not None:
        raise failed
    # This independent wrapper result is required by the Actions job. The inner
    # manifest cannot make a failed application/source finalization job succeed.
    if releasing:
        outcome = release_outcome(Path(released['directory']))
        require((0 if outcome['code'] == 'PASS' else 1) == code, 'RESULT_IDENTITY')
        return outcome
    print('CI_TERMINAL FINALIZED ' + ('PASS' if code == 0 else 'COMPONENT_FAILED'))
    return code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--child', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--component', choices=tuple(name for name in PROFILES if name != 'release-consumers'))
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
