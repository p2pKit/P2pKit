#!/usr/bin/env python3
"""One reversible configuration transaction for the ordinary hosted Intel test job.

No product is launched here. No audit/Terminal context or permission is created.
Private, create-only journals bind prepare/restore across workflow steps. An
incomplete/timeout command is uncertainty, NOT proof its privileged descendant
retired: refuse further mutation and do not claim restoration. The disposable
runner must then be retired. This is not a process supervisor or crash recovery.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import plistlib
import re
import stat
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_bonjour_environment as b
from audit_processes import host_role

NAME = 'rpc-intel-bonjour-advertising'
REPORT = NAME + '-result.json'
SCOPE = 'ORDINARY_INTEL_CONFIGURATION_TRANSACTION_NOT_PRODUCT_OR_PERMISSION_QUALIFICATION'
need = b.need


def admit(env):
    expected = {'GITHUB_ACTIONS': 'true', 'RUNNER_ENVIRONMENT': 'github-hosted',
                'GITHUB_REPOSITORY': 'p2pKit/P2pKit', 'GITHUB_JOB': 'run',
                'COMPONENT': 'apple-x64', 'RUNNER_OS': 'macOS', 'RUNNER_ARCH': 'X64'}
    need(all(env.get(k) == v for k, v in expected.items()), 'Wrong modular Intel component')
    ref, event = env.get('GITHUB_REF', ''), env.get('GITHUB_EVENT_NAME')
    callers = {'ci.yml': 'CI — modular qualification', 'ios-x64-tests.yml': 'Intel iOS simulator tests'}
    caller = next((name for name in callers if env.get('GITHUB_WORKFLOW_REF') ==
                   'p2pKit/P2pKit/.github/workflows/' + name + '@' + ref), None)
    need(caller is not None and env.get('GITHUB_WORKFLOW') == callers[caller], 'Exact workflow caller required')
    ordinary = ((event == 'workflow_dispatch' and re.fullmatch(r'refs/heads/[A-Za-z0-9_./-]+', ref)) or
                (event == 'schedule' and ref == 'refs/heads/main'))
    ci_event = caller == 'ci.yml' and ((event == 'push' and ref == 'refs/heads/main') or
                (event == 'pull_request' and re.fullmatch(r'refs/pull/[1-9][0-9]*/merge', ref)))
    need(ordinary or ci_event, 'Unadmitted event/ref')
    need(all(re.fullmatch('[1-9][0-9]{0,17}', env.get(k, '')) for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')) and
         re.fullmatch('[0-9a-f]{40}', env.get('GITHUB_SHA', '')) and
         env.get('GITHUB_WORKFLOW_SHA') == env['GITHUB_SHA'], 'Exact workflow/source/run required')
    need(not any(env.get(k) for k in ('RPC_APPLE_TERMINAL_CONTEXT', 'RPC_APPLE_AUDIT_CONTEXT',
                                    'RPC_APPLE_LAUNCHD_CONTEXT', 'RPC_QUALIFY_REQUESTED')),
         'No historical execution-context substitution')
    need(platform.system() == 'Darwin' and platform.machine() == 'x86_64' and host_role() == 'macos-x64',
         'Native Intel required')
    need(os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() != 0, 'Nonroot caller required')
    console = Path('/dev/console').stat()
    need(stat.S_ISCHR(console.st_mode) and console.st_uid == os.getuid(), 'Same ordinary console owner required')
    need(Path(env.get('GITHUB_WORKSPACE', '')).resolve(strict=True) == ROOT, 'Exact checkout required')
    parent = Path(env['RUNNER_TEMP'])
    b.private.physical(parent)
    need(parent.is_dir() and parent.stat().st_uid == os.getuid(), 'Owned runner temp required')
    return parent / NAME


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode('ascii')
    need(len(raw) <= b.LIMIT, 'Bounded private journal required')
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def read(path):
    info = path.lstat()
    need(info.st_nlink == 1, 'Hardlinked journal refused')
    return b.private.read_json(path)


def identity(path):
    info = path.lstat()
    return [info.st_dev, info.st_ino]


def binding(env, directory, source):
    return dict(schema=1, scope=SCOPE, source=source, uid=os.getuid(), gid=os.getgid(),
                run={k: env[k] for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_REF', 'GITHUB_JOB',
                                           'GITHUB_WORKFLOW_REF', 'GITHUB_WORKFLOW_SHA', 'COMPONENT')},
                directory=identity(directory), checkout=identity(ROOT))


class Transaction(b.AdvertisingPreparation):
    def __init__(self, env, parent, source):
        need(source == b.private.source_snapshot() and source['commit'] == env['GITHUB_SHA'], 'Unchanged source required')
        parent.mkdir(mode=0o700)
        b.private.private_parent(parent, os.getuid())
        self._initialize(parent, source, 'apple-x64')
        self.bound = binding(env, self.directory, source)
        write(self.directory / 'binding.json', self.bound)
        sync_directory(parent)

    def record(self):
        original = self.directory / 'original.plist'
        return dict(proof=self.proof, policy=list(self.policy) if self.policy is not None else None,
                    originalSha256=b.digest(b.private.read_private(original, os.getuid())) if original.exists() else None)

    def command(self, label):
        need(label in b.REPAIR_COMMANDS, 'Fixed repair command required')
        if label == 'apply':
            # Persist original bytes, typed policy and intent BEFORE sudo can write.
            with os.fdopen(os.open(self.directory / 'original.plist', os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
                os.fsync(stream.fileno())
        write(self.directory / ('intent-' + label + '.json'), self.record())
        try:
            super().command(label)
        finally:
            result = self.proof['commands'].get(label)
            # A timeout/reaped sudo does not establish descendant retirement.
            # No completion receipt means no automatic restoration/retry.
            if result is not None and not result['timedOut'] and result['exitCode'] >= 0:
                write(self.directory / ('complete-' + label + '.json'), result)

    def prepare(self):
        try:
            self.apply()
        finally:
            write(self.directory / 'prepared.json', self.record())

    def should_restore_reload(self):
        # Exact known success also covers a caught failure after command receipt
        # but before the caller set reloadSucceeded. Never retry denied reload.
        return self.proof['commands'].get('reload', {}).get('failure') == 'NONE'

    @classmethod
    def resume(cls, env, parent):
        b.private.private_parent(parent, os.getuid())
        directory = parent / 'bonjour-advertising'
        b.private.private_parent(directory, os.getuid())
        bound = read(directory / 'binding.json')
        need(type(bound) is dict and type(bound.get('source')) is dict and
             set(bound['source']) == {'commit', 'tree'} and
             all(type(v) is str and re.fullmatch('[0-9a-f]{40}', v) for v in bound['source'].values()) and
             bound['source']['commit'] == env['GITHUB_SHA'], 'Original exact source required')
        need(bound == binding(env, directory, bound['source']), 'Transaction owner/run/directory changed')
        record = read(directory / 'prepared.json')
        need(type(record) is dict and set(record) == {'proof', 'policy', 'originalSha256'}, 'Closed prepared record required')
        proof = b.validate(record['proof'], bound['source'], complete=False, expected_lane='apple-x64')
        need(proof['operation'] == 'EXPLICIT_TRUE_REPAIR' and not (directory / 'restore-started.json').exists(),
             'Single repair restoration only')
        intents = {p.name.removeprefix('intent-').removesuffix('.json') for p in directory.glob('intent-*.json')}
        completions = {p.name.removeprefix('complete-').removesuffix('.json') for p in directory.glob('complete-*.json')}
        need(intents == completions == set(proof['commands']) and intents <= {'inspect', 'apply', 'reload'},
             'Incomplete command: no closure or restoration claim')
        for label in intents:
            result = read(directory / ('complete-' + label + '.json'))
            need(result == proof['commands'][label] and not result['timedOut'] and result['exitCode'] >= 0,
                 'Unknown command completion')
            intent = read(directory / ('intent-' + label + '.json'))
            need(type(intent) is dict and set(intent) == set(record), 'Closed intent required')
            b.validate(intent['proof'], bound['source'], complete=False, expected_lane='apple-x64')
            if label == 'apply':
                need(intent['policy'] == record['policy'] and intent['originalSha256'] == record['originalSha256'] and
                     intent['proof']['observations'].get('before') == proof['observations'].get('before'),
                     'Original policy must precede mutation')
        instance = cls.__new__(cls)  # No constructor: never recreate, reset or overwrite existing state.
        instance.source, instance.directory, instance.bound, instance.proof = bound['source'], directory, bound, proof
        instance.before = instance.policy = None
        if proof['changeAttempted']:
            need(proof['originalRecorded'] and type(record['policy']) is list and len(record['policy']) == 3 and
                 all(type(v) is int for v in record['policy']) and record['policy'][0] == 0 and
                 0 <= record['policy'][2] <= 0o7777 and record['policy'][2] & 0o022 == 0, 'Original root-owned policy required')
            raw = b.private.read_private(directory / 'original.plist', os.getuid())
            need((directory / 'original.plist').lstat().st_nlink == 1 and b.digest(raw) == record['originalSha256'],
                 'Original preference bytes changed')
            instance.before, instance.policy = plistlib.loads(raw), tuple(record['policy'])
            need(type(instance.before) is dict and instance.before.get(b.KEY) is True and
                 b.summarize(instance.before) == proof['observations'].get('before'), 'Typed original snapshot required')
        write(directory / 'restore-started.json', dict(binding=bound, preparedSha256=b.digest(
            b.private.read_private(directory / 'prepared.json', os.getuid()))))
        return instance


def execute(mode, env):
    transaction = None
    parent = None
    failure_phase = 'ADMISSION'
    try:
        parent = admit(env)
        if mode == 'prepare':
            failure_phase = 'PREPARATION'
            transaction = Transaction(env, parent, b.private.source_snapshot())
            transaction.prepare()
        else:
            failure_phase = 'REHYDRATION_OR_COMMAND_COMPLETION'
            transaction = Transaction.resume(env, parent)
            failure_phase = 'RESTORATION'
            transaction.finish()
        success = True
        failure_phase = None
    except Exception:
        success = False  # Never print private paths, plist contents, account IDs or exception messages.
    if mode == 'restore' and parent is not None:
        report = dict(schema=1, scope=SCOPE, successfulConfigurationRoundTrip=success,
                      qualification='NOT_PERFORMED', failurePhase=failure_phase,
                      uncertainty='NONE' if success else 'NO_SUCCESSFUL_RESTORATION_CLAIM',
                      run={k: env[k] for k in ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT')},
                      proof=transaction.proof if transaction else None)
        try:
            # Only this closed proof enters the existing encrypted report archive.
            # Original plist, journals and privileged-command streams remain private
            # under RUNNER_TEMP; never copy/upload their directory.
            reports = ROOT / 'build/reports/ci-component'
            reports.mkdir(parents=True, exist_ok=True)
            write(reports / REPORT, report)
        except Exception:
            success = False
            failure_phase = 'REPORT'
    print(json.dumps(dict(scope=SCOPE, phase=mode, passed=success, failurePhase=failure_phase, qualification='NOT_PERFORMED'), sort_keys=True))
    return 0 if success else 1


if __name__ == '__main__':
    need(sys.argv[1:] in (['prepare'], ['restore']), 'Only prepare/restore admitted')
    raise SystemExit(execute(sys.argv[1], os.environ))
