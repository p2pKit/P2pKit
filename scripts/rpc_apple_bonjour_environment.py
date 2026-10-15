"""Reversible Bonjour advertising preparation on an explicitly admitted disposable runner.

This is system-service configuration, NOT native product ownership or permission
admission. Only one documented Boolean is changed, with ordinary fixed defaults
and launchctl commands. Products/observers stay nonroot. A protected-service
refusal is a failure, never permission to disable SIP or try PID-based signaling.
An actually absent domain on the native ARM image is observed without changing
anything; only subsequent real multicast/product gates establish functionality.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import platform
import plistlib
import re
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_runner_context as apple_context
import rpc_apple_audit_context as audit_context
spec = importlib.util.spec_from_file_location('bonjour_private_files', ROOT / 'scripts/with-darwin-launchd-context.py')
private = importlib.util.module_from_spec(spec)
spec.loader.exec_module(private)
need = private.need
DOMAIN = '/Library/Preferences/com.apple.mDNSResponder'
PREFERENCE = Path(DOMAIN + '.plist')
KEY = 'NoMulticastAdvertisements'
SERVICE_CONFIGURATION = Path('/System/Library/LaunchDaemons/com.apple.mDNSResponder.plist')
# The configuration filename is NOT the modern launchd Label. Validate the
# installed Apple configuration and actual registration before writing a key.
SERVICE = 'system/com.apple.mDNSResponder.reloaded'
SCOPE = 'DISPOSABLE_BONJOUR_ADVERTISING_CONFIGURATION_NOT_PERMISSION_OR_OWNERSHIP'
LIMIT = 128 * 1024
STAGES = ('INITIAL', 'SERVICE', 'SNAPSHOT', 'APPLY', 'RELOAD', 'ACTIVE', 'RESTORE', 'RESTORE_RELOAD', 'VERIFY_UNCHANGED', 'FINALIZED')
FAILURES = ('NONE', 'PREREQUISITE', 'PREFERENCE_CHANGED', 'PRIVILEGE_UNAVAILABLE', 'PROTECTED_SERVICE',
            'OPERATION_NOT_PERMITTED', 'SERVICE_UNAVAILABLE', 'COMMAND_FAILED', 'COMMAND_TIMEOUT', 'RESTORATION',
            'PREFERENCE_MISSING', 'PREFERENCE_UNREADABLE', 'PREFERENCE_POLICY_OR_RACE', 'PREFERENCE_FORMAT',
            'PREFERENCE_KEY_MISSING', 'PREFERENCE_KEY_TYPE', 'PREFERENCE_ALREADY_ENABLED')
FLAGS = {'serviceRegistered', 'originalRecorded', 'changeAttempted', 'applied', 'otherPreferencesUnchanged', 'filePolicyUnchanged',
         'reloadSucceeded', 'restored', 'restoreReloadSucceeded', 'sourceUnchanged'}
COMMANDS = {
    'inspect': ['/bin/launchctl', 'print', SERVICE],  # Nonroot read-only registration check.
    'inspect-unchanged': ['/bin/launchctl', 'print', SERVICE],
    'apply': ['/usr/bin/sudo', '-n', '/usr/bin/defaults', 'write', DOMAIN, KEY, '-bool', 'false'],
    'reload': ['/usr/bin/sudo', '-n', '/bin/launchctl', 'kickstart', '-k', SERVICE],
    'restore': ['/usr/bin/sudo', '-n', '/usr/bin/defaults', 'write', DOMAIN, KEY, '-bool', 'true'],
    'restore-reload': ['/usr/bin/sudo', '-n', '/bin/launchctl', 'kickstart', '-k', SERVICE],
}
REPAIR_COMMANDS = COMMANDS.keys() - {'inspect-unchanged'}
OPERATIONS = ('EXPLICIT_TRUE_REPAIR', 'ARM_ABSENT_DOMAIN_NO_CHANGE')


class PreparationFailure(RuntimeError):
    def __init__(self, category):
        need(category in FAILURES and category != 'NONE', 'Unknown preparation failure')
        self.category = category
        super().__init__(category)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def admit(env, parent, source):
    lane = apple_context.native_lane(env)
    audit = audit_context.requested(env)
    need(os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() != 0,
         'Only native nonroot Apple preparation admitted')
    need(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
         env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_REF') == private.REF and
         env.get('GITHUB_EVENT_NAME') == 'push' and env.get('RPC_QUALIFY_REQUESTED') == 'true' and
         env.get('RPC_APPLE_BONJOUR_ADVERTISING') == 'true' and
         (env.get('RPC_APPLE_TERMINAL_CONTEXT') == 'true' or audit),
         'Explicit disposable feature-only advertising preparation required')
    need(Path(env['GITHUB_WORKSPACE']).resolve(strict=True) == ROOT and
         Path(env['RPC_QUALIFICATION_PARENT']) == parent and
         parent.is_relative_to(Path(env['RUNNER_TEMP']).resolve(strict=True)), 'Task-private source and state required')
    private.private_parent(parent, os.getuid())
    need(type(source) is dict and set(source) == {'commit', 'tree'} and all(type(v) is str and
         re.fullmatch('[0-9a-f]{40}', v) for v in source.values()) and source['commit'] == env.get('GITHUB_SHA') and
         private.source_snapshot() == source, 'Exact unchanged feature source required')
    if audit:
        audit_context.recheck(env, parent, source)
    return lane


def read_system_file(path):
    """Used only with the two fixed system paths, never a caller-supplied filename."""
    private.physical(path)
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_uid == 0 and info.st_nlink == 1 and
         stat.S_IMODE(info.st_mode) & 0o022 == 0 and info.st_size <= LIMIT, 'System preference ownership required')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        actual = os.fstat(stream.fileno())
        need((actual.st_dev, actual.st_ino) == (info.st_dev, info.st_ino), 'Replaced system preference refused')
        raw = stream.read(LIMIT + 1)
        after = os.fstat(stream.fileno())
    need(len(raw) <= LIMIT and (actual.st_size, actual.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
         'Changing system preference refused')
    return raw, (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))


def read_service_configuration():
    raw, _ = read_system_file(SERVICE_CONFIGURATION)
    value = plistlib.loads(raw)
    need(type(value) is dict and value.get('Label') == SERVICE.removeprefix('system/'),
         'Exact installed Apple mDNS service label required')
    argv = value.get('ProgramArguments')
    need(type(argv) is list and 1 <= len(argv) <= 32 and
         all(type(v) is str and '\0' not in v for v in argv) and argv[0] == '/usr/sbin/mDNSResponder' and
         value.get('Program', argv[0]) == '/usr/sbin/mDNSResponder', 'Exact installed Apple mDNS program required')
    need('-NoMulticastAdvertisements' not in argv, 'Command-line advertising suppression cannot be overridden')
    return digest(raw)


def read_preference():
    """Read only the fixed system domain; never publish its arbitrary keys/values."""
    try:
        raw, policy = read_system_file(PREFERENCE)
    except FileNotFoundError:
        raise PreparationFailure('PREFERENCE_MISSING') from None
    except OSError:
        raise PreparationFailure('PREFERENCE_UNREADABLE') from None
    except private.ContextFailure:
        raise PreparationFailure('PREFERENCE_POLICY_OR_RACE') from None
    try:
        value = plistlib.loads(raw)
    except Exception:
        raise PreparationFailure('PREFERENCE_FORMAT') from None
    if type(value) is not dict:
        raise PreparationFailure('PREFERENCE_FORMAT')
    if KEY not in value:
        raise PreparationFailure('PREFERENCE_KEY_MISSING')
    if type(value[KEY]) is not bool:
        raise PreparationFailure('PREFERENCE_KEY_TYPE')
    return value, policy, raw


def absent_domain_observation():
    """Attest only absence and protected parent identity, not multicast behavior.

    Missing/read-denied/unsafe files are not interchangeable. Never create a
    preference, guess its contents, or delete a domain which appeared later.
    """
    private.physical(PREFERENCE)
    parent = PREFERENCE.parent
    info = parent.lstat()
    need(stat.S_ISDIR(info.st_mode) and info.st_uid == 0 and stat.S_IMODE(info.st_mode) & 0o022 == 0,
         'Protected system preference parent required')
    def identity(value):
        return value.st_dev, value.st_ino, value.st_uid, value.st_gid, value.st_mode
    try:
        PREFERENCE.lstat()
    except FileNotFoundError:
        pass
    else:
        raise PreparationFailure('PREFERENCE_CHANGED')
    need(identity(info) == identity(parent.lstat()), 'Preference parent changed during absence check')
    return digest(repr(identity(info)).encode('ascii'))


def summarize(value):
    others = {key: item for key, item in value.items() if key != KEY}
    return {'preferenceKind': 'TRUE' if value[KEY] else 'FALSE',
            'domainSha256': digest(plistlib.dumps(value, sort_keys=True)),
            'otherPreferencesSha256': digest(plistlib.dumps(others, sort_keys=True)), 'otherKeyCount': len(others)}


def equal_preferences(left, right):
    # Ordinary Python equality equates a Boolean and integer. Plist types are
    # part of the setting contract and must survive the round trip too.
    return plistlib.dumps(left, sort_keys=True) == plistlib.dumps(right, sort_keys=True)


def command_failure(raw, code, timeout):
    if timeout:
        return 'COMMAND_TIMEOUT'
    if code == 0:
        return 'NONE'
    if b'System Integrity Protection' in raw or b'protected service' in raw.lower():
        return 'PROTECTED_SERVICE'
    if b'a password is required' in raw or b'not allowed to execute' in raw:
        return 'PRIVILEGE_UNAVAILABLE'
    if b'Operation not permitted' in raw:
        return 'OPERATION_NOT_PERMITTED'
    if b'Could not find service' in raw:
        return 'SERVICE_UNAVAILABLE'
    return 'COMMAND_FAILED'


def validate(value, source, complete=True, *, expected_lane=None):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'source', 'stage', 'failure', 'restoreFailure',
         'observations', 'commands', 'serviceConfigurationSha256', 'nativeLane', 'operation', 'absence', *FLAGS} and type(value['schema']) is int and value['schema'] == 3 and
         value['scope'] == SCOPE and value['source'] == source and value['stage'] in STAGES and
         value['failure'] in FAILURES and value['restoreFailure'] in FAILURES and
         all(type(value[k]) is bool for k in FLAGS), 'Closed preparation proof required')
    apple_context.proof_lane(value['nativeLane'], expected_lane)
    need(value['operation'] in OPERATIONS, 'Unknown preparation operation')
    no_change = value['operation'] == 'ARM_ABSENT_DOMAIN_NO_CHANGE'
    if no_change:
        need(value['nativeLane'] == 'apple-arm64' and type(value['absence']) is dict and
             set(value['absence']) == {'before', 'after'} and all(item is None or
             type(item) is str and re.fullmatch('[0-9a-f]{64}', item) for item in value['absence'].values()),
             'Exact native ARM absence observations required')
    else:
        need(value['absence'] is None, 'Repair cannot claim an absence no-op')
    service_hash = value['serviceConfigurationSha256']
    need(service_hash is None or (type(service_hash) is str and re.fullmatch('[0-9a-f]{64}', service_hash)),
         'Invalid service configuration digest')
    observations = value['observations']
    need(type(observations) is dict and set(observations) <= {'before', 'active', 'restored'}, 'Closed preference observations required')
    for row in observations.values():
        need(type(row) is dict and set(row) == {'preferenceKind', 'domainSha256', 'otherPreferencesSha256', 'otherKeyCount'} and
             row['preferenceKind'] in ('TRUE', 'FALSE') and type(row['otherKeyCount']) is int and
             0 <= row['otherKeyCount'] <= 1024 and all(type(row[k]) is str and re.fullmatch('[0-9a-f]{64}', row[k])
             for k in ('domainSha256', 'otherPreferencesSha256')), 'Private preference data refused')
    need(type(value['commands']) is dict and set(value['commands']) <= COMMANDS.keys(), 'Unknown system command')
    for row in value['commands'].values():
        need(type(row) is dict and set(row) == {'exitCode', 'timedOut', 'failure', 'bytes', 'sha256'} and
             type(row['exitCode']) is int and -255 <= row['exitCode'] <= 255 and type(row['timedOut']) is bool and
             type(row['bytes']) is int and 0 <= row['bytes'] <= LIMIT and type(row['sha256']) is str and
             re.fullmatch('[0-9a-f]{64}', row['sha256']) and row['failure'] in FAILURES and
             (row['failure'] == 'NONE') is (row['exitCode'] == 0 and not row['timedOut']), 'Invalid command observation')
    if complete:
        need(value['stage'] == 'FINALIZED' and value['failure'] == value['restoreFailure'] == 'NONE' and
             service_hash is not None and all(row['failure'] == 'NONE' for row in value['commands'].values()),
             'Unproven configuration finalization')
        if no_change:
            need(value['serviceRegistered'] and value['sourceUnchanged'] and
                 all(not value[k] for k in FLAGS - {'serviceRegistered', 'sourceUnchanged'}) and observations == {} and
                 set(value['commands']) == {'inspect', 'inspect-unchanged'} and value['absence']['before'] is not None and
                 value['absence']['before'] == value['absence']['after'], 'Unproven no-change environment observation')
        else:
            need(all(value[k] for k in FLAGS) and set(observations) == {'before', 'active', 'restored'} and
                 observations['before'] == observations['restored'] and
                 observations['before']['preferenceKind'] == 'TRUE' and observations['active']['preferenceKind'] == 'FALSE' and
                 observations['before']['otherPreferencesSha256'] == observations['active']['otherPreferencesSha256'] and
                 observations['before']['otherKeyCount'] == observations['active']['otherKeyCount'] and
                 set(value['commands']) == REPAIR_COMMANDS, 'Unproven configuration restoration')
    return value


class AdvertisingPreparation:
    def __init__(self, parent, source):
        lane = admit(os.environ, parent, source)
        self.source = source
        self.directory = parent / 'bonjour-advertising'
        self.directory.mkdir(mode=0o700)
        self.before = self.policy = None
        self.proof = dict(schema=3, scope=SCOPE, source=source, nativeLane=lane, operation='EXPLICIT_TRUE_REPAIR', absence=None,
                          stage='INITIAL', failure='NONE', restoreFailure='NONE',
                          observations={}, commands={}, serviceConfigurationSha256=None, **dict.fromkeys(FLAGS, False))

    def command(self, label):
        need(label in COMMANDS and label not in self.proof['commands'], 'One fixed command attempt only')
        need((self.proof['operation'] == 'ARM_ABSENT_DOMAIN_NO_CHANGE' and label == 'inspect-unchanged') or
             (self.proof['operation'] == 'EXPLICIT_TRUE_REPAIR' and label in REPAIR_COMMANDS),
             'No-change observation cannot execute a mutation command')
        if label in ('inspect', 'inspect-unchanged', 'reload', 'restore-reload'):
            need(self.proof['serviceConfigurationSha256'] == read_service_configuration(),
                 'Installed service configuration changed; no service operation admitted')
        path = self.directory / (label + '.log')
        timed_out = False
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as log:
            try:
                code = subprocess.run(COMMANDS[label], cwd=ROOT, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                    env={'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'LANG': 'C', 'LC_ALL': 'C'}, timeout=30).returncode
            except subprocess.TimeoutExpired:
                code, timed_out = 125, True
        raw = private.read_private(path, os.getuid())
        category = command_failure(raw, code, timed_out)
        self.proof['commands'][label] = dict(exitCode=code, timedOut=timed_out, failure=category, bytes=len(raw), sha256=digest(raw))
        if category != 'NONE':
            raise PreparationFailure(category)

    def apply(self):
        try:
            self.proof['stage'] = 'SERVICE'
            self.proof['serviceConfigurationSha256'] = read_service_configuration()
            self.command('inspect')  # Fail BEFORE a preference write if launchd has no exact service.
            self.proof['serviceRegistered'] = True
            self.proof['stage'] = 'SNAPSHOT'
            try:
                self.before, self.policy, raw = read_preference()
            except PreparationFailure as error:
                if error.category != 'PREFERENCE_MISSING' or self.proof['nativeLane'] != 'apple-arm64':
                    raise
                before = absent_domain_observation()
                self.proof.update(operation='ARM_ABSENT_DOMAIN_NO_CHANGE', absence=dict(before=before, after=None), stage='ACTIVE')
                return  # No write/reload, no claim that multicast actually works.
            if self.before[KEY] is not True:
                # Distinguish a wrong preparation assumption from a permission
                # failure. This is still a refusal, not a no-op success.
                raise PreparationFailure('PREFERENCE_ALREADY_ENABLED')
            private.write_new(self.directory / 'original.plist', raw)
            self.proof['observations']['before'] = summarize(self.before)
            self.proof['originalRecorded'] = True
            self.proof['stage'] = 'APPLY'
            self.proof['changeAttempted'] = True  # Restore even if a command writes but returns a failure.
            self.command('apply')
            active, policy, _ = read_preference()
            self.proof['observations']['active'] = summarize(active)
            self.proof['otherPreferencesUnchanged'] = equal_preferences({**active, KEY: True}, self.before)
            self.proof['filePolicyUnchanged'] = policy == self.policy
            need(active[KEY] is False and self.proof['otherPreferencesUnchanged'] and self.proof['filePolicyUnchanged'],
                 'Only the exact advertising Boolean may change')
            self.proof['applied'] = True
            self.proof['stage'] = 'RELOAD'
            self.command('reload')  # Normal service-manager operation; do NOT fall back to raw PID signals.
            self.proof['reloadSucceeded'] = True
            self.proof['stage'] = 'ACTIVE'
        except Exception as error:
            self.proof['failure'] = error.category if isinstance(error, PreparationFailure) else 'PREREQUISITE'
            raise

    def finish(self):
        try:
            if self.proof['operation'] == 'ARM_ABSENT_DOMAIN_NO_CHANGE':
                self.proof['stage'] = 'VERIFY_UNCHANGED'
                self.proof['absence']['after'] = absent_domain_observation()
                need(self.proof['absence']['before'] == self.proof['absence']['after'], 'Preference parent identity changed')
                self.command('inspect-unchanged')  # Rechecks the same installed service configuration too.
            elif self.proof['changeAttempted']:
                self.proof['stage'] = 'RESTORE'
                current, policy, _ = read_preference()
                # Never overwrite another preference. Restore our ONE key even
                # when a separate key/metadata drift must keep the result failed.
                drift = not equal_preferences({**current, KEY: True}, self.before) or policy != self.policy
                self.command('restore')
                restored, policy, _ = read_preference()
                self.proof['observations']['restored'] = summarize(restored)
                self.proof['restored'] = equal_preferences(restored, self.before) and policy == self.policy and not drift
                if self.proof['reloadSucceeded']:
                    self.proof['stage'] = 'RESTORE_RELOAD'
                    self.command('restore-reload')
                    self.proof['restoreReloadSucceeded'] = True
                # A denied reload is not retried/bypassed. The disk preference is
                # restored, but a failed preparation can never qualify execution.
                need(self.proof['restored'], 'Original preference restoration failed')
        except Exception as error:
            self.proof['restoreFailure'] = error.category if isinstance(error, PreparationFailure) else 'RESTORATION'
        finally:
            try:
                self.proof['sourceUnchanged'] = private.source_snapshot() == self.source
            except Exception:
                self.proof['sourceUnchanged'] = False
            no_change = (self.proof['operation'] == 'ARM_ABSENT_DOMAIN_NO_CHANGE' and self.proof['sourceUnchanged'] and
                         self.proof['absence']['before'] == self.proof['absence']['after'])
            if (all(self.proof[k] for k in FLAGS) or no_change) and self.proof['failure'] == self.proof['restoreFailure'] == 'NONE':
                self.proof['stage'] = 'FINALIZED'
            private.write_json(self.directory / 'result.json', validate(self.proof, self.source, complete=False))
        validate(self.proof, self.source)
