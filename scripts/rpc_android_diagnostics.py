"""Closed supplemental-AVD observations; never test or ownership admission.

Only source-known stages/sites, fixed error categories, counts and hashes leave
the private job. Tokens, device identifiers, argv, paths and exception messages
are not exported. The collector derives this again from the original files.
"""
from __future__ import annotations

import hashlib
import math
import re

from rpc_mobile_usb import ANDROID_SHELL_STAGES

SCOPE = 'ANDROID_TOOL_OBSERVATIONS_NOT_TEST_OR_OWNERSHIP_ADMISSION'
COMMANDS = (
    'test-apk-manifest', 'acceleration-observation', 'avd-create', 'initial-devices',
    'boot-state', 'avd-name', 'qemu', 'sdk', 'image-fingerprint', 'app-install',
    'test-install', 'rpc-controls', 'test-uninstall', 'app-uninstall',
    'owned-guest-failure-log', 'cleanup-avd-name', 'owned-emulator-stop', 'private-adb-stop',
    'control-shell-features', 'control-shell-prepare', 'control-shell-read-inbox',
    'control-shell-missing', 'control-shell-reprepare', 'control-shell-read-unchanged',
    'control-shell-stop', 'control-shell-restop', 'control-shell-read-stop',
    'stat-dereference-observation',
)
BOUNDS = {name: {'test-apk-manifest': 90, 'acceleration-observation': 30, 'avd-create': 90,
    'app-install': 120, 'test-install': 120, 'rpc-controls': 120, 'owned-guest-failure-log': 20,
    'cleanup-avd-name': 10, 'owned-emulator-stop': 20, 'private-adb-stop': 20}.get(name, 40) for name in COMMANDS}
STAGES = ('admission', 'keystore-round-trip', 'namespace-and-approval-validation', 'tampered-ciphertext',
    'purpose-substitution', 'client-runtime', 'invalid-phone-policy', 'actual-debug-activity',
    'mobile-private-control-files', 'mobile-self-process-resources', 'missing-keystore-key')
CLASSES = ('IllegalStateException', 'IllegalArgumentException', 'AssertionError', 'TimeoutCancellationException',
    'ErrnoException', 'SecurityException', 'IOException', 'NoSuchMethodError', 'NoClassDefFoundError',
    'LinkageError', 'AEADBadTagException', 'InvalidKeyException', 'KeyStoreException', 'RuntimeException', 'UNKNOWN')
CATEGORIES = ('COMMAND_FAILED', 'COMMAND_DEADLINE', 'BOOT_DEADLINE', 'EMULATOR_EXITED',
    'INSTRUMENTATION_TERMINAL', 'INSTRUMENTATION_RESULT', 'EMULATOR_CLEANUP', 'ADB_CLEANUP',
    'SHELL_V2_PREREQUISITE', 'SHELL_COMMAND_EXIT', 'SHELL_COMMAND_OUTPUT', 'DIAGNOSTIC_FAILED', 'UNCLASSIFIED') + tuple(
    'SHELL_STAGE_' + stage.replace('-', '_').upper() for stage in ANDROID_SHELL_STAGES)
FLAGS = ('booted', 'controlsPassed', 'naturalCleanup')
PREFIX = 'samples/p2p-sample-android/src/'
SITES = {'RpcLabRuntimeInstrumentation.kt': PREFIX + 'androidTest/java/dev/p2pkit/sample/android/rpclab/RpcLabRuntimeInstrumentation.kt',
    **{name + '.kt': PREFIX + 'debug/java/dev/p2pkit/sample/android/rpclab/' + name + '.kt'
       for name in ('AndroidRpcCapacityFiles', 'AndroidRpcLabTrustStore', 'RpcLabActivity')}}


def need(condition):
    if not condition:
        raise ValueError('Invalid/private Android diagnostic observation')


def metadata(raw):
    need(type(raw) is bytes and len(raw) <= 32 * 1024 * 1024)
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def source_site(root, name, line):
    if type(name) is not str or name not in SITES or type(line) is not str or not re.fullmatch('[1-9][0-9]{0,5}', line):
        return None
    path = root / SITES[name]
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 262144)
    return dict(file=name, line=int(line)) if int(line) <= len(path.read_text().splitlines()) else None


def instrumentation(raw, root):
    need(type(raw) is bytes and len(raw) <= 262144)
    text = raw.decode(errors='replace')
    pairs = re.findall(r'^INSTRUMENTATION_RESULT: ([A-Za-z0-9]+)=(.*)$', text, re.M)
    need(len(pairs) == len({k for k, _ in pairs}))
    fields = dict(pairs)
    terminals = re.findall(r'^INSTRUMENTATION_CODE: (-?[0-9]{1,3})$', text, re.M)
    need(len(terminals) <= 4 and all(-255 <= int(n) <= 255 for n in terminals))
    result = dict(log=metadata(raw), terminalCodes=[int(n) for n in terminals],
        reportedOutcome=fields.get('rpcOutcome') if fields.get('rpcOutcome') in ('PASS', 'FAIL') else None,
        reportedCleanup=fields.get('rpcCleanup') if fields.get('rpcCleanup') in ('PASS', 'FAIL') else None,
        reportedCompleted=int(fields['rpcCompleted']) if fields.get('rpcCompleted') in tuple(map(str, range(11))) else None,
        failureStage=fields.get('rpcFailureStage') if fields.get('rpcFailureStage') in STAGES else
            ('UNKNOWN' if 'rpcFailureStage' in fields else None), failureClass=None, cleanupFailureClass=None,
        failureSite=source_site(root, fields.get('rpcFailureFile'), fields.get('rpcFailureLine')),
        failureErrno=None)
    for key, source in (('failureClass', 'rpcFailureClass'), ('cleanupFailureClass', 'rpcCleanupFailureClass')):
        if source in fields:
            result[key] = fields[source] if fields[source] in CLASSES else 'UNKNOWN'
    errno = fields.get('rpcFailureErrno', '')
    if re.fullmatch('[0-9]{1,4}', errno) and int(errno) <= 4095:
        result['failureErrno'] = int(errno)
    return result


def error_category(text):
    need(type(text) is str and len(text) <= 65536)
    prefix = 'Android shell stage: '
    if text.startswith(prefix) and text[len(prefix):] in ANDROID_SHELL_STAGES:
        return dict(category='SHELL_STAGE_' + text[len(prefix):].replace('-', '_').upper(), command=None)
    for category, prefix in (('COMMAND_FAILED', 'RuntimeError: Command failed: '),
                             ('COMMAND_DEADLINE', 'RuntimeError: Command deadline: '),
                             ('SHELL_COMMAND_EXIT', 'RuntimeError: Android shell control exit/type mismatch: '),
                             ('SHELL_COMMAND_OUTPUT', 'RuntimeError: Android shell control output mismatch: ')):
        if text.startswith(prefix) and text[len(prefix):] in COMMANDS:
            return dict(category=category, command=text[len(prefix):])
    fixed = {'RuntimeError: Software emulator boot deadline': 'BOOT_DEADLINE',
        'RuntimeError: Emulator exited before boot': 'EMULATOR_EXITED',
        'RuntimeError: Actual Android shell-v2 support is required': 'SHELL_V2_PREREQUISITE',
        'RuntimeError: Instrumentation did not finish successfully': 'INSTRUMENTATION_TERMINAL',
        'RuntimeError: Incomplete, wrong-device, mismatched-token or failed RPC controls': 'INSTRUMENTATION_RESULT'}
    if text in fixed:
        return dict(category=fixed[text], command=None)
    for prefix, category in (('Emulator cleanup: ', 'EMULATOR_CLEANUP'),
                             ('Private adb cleanup: ', 'ADB_CLEANUP'), ('Diagnostic failure: ', 'DIAGNOSTIC_FAILED')):
        if text.startswith(prefix):
            return dict(category=category, command=None)
    return dict(category='UNCLASSIFIED', command=None)


def observe(private, raw_result, raw_instrumentation, driver_logs, root):
    value = dict(schema=1, scope=SCOPE, executionAdmitted=False, resultAvailable=private is not None,
        resultLog=metadata(raw_result) if raw_result is not None else None, reportedStatus=None,
        reportedFlags={k: None for k in FLAGS}, reportedBootMillis=None, commands=[], errors=[],
        instrumentation=None, driverLogs={k: metadata(v) for k, v in driver_logs.items()})
    if private is not None:
        need(type(private) is dict and type(private.get('commands')) is list and len(private['commands']) <= 512 and
             type(private.get('errors')) is list and len(private['errors']) <= 64 and raw_result is not None)
        value.update(reportedStatus=private.get('status'), reportedFlags={k: private.get(k) for k in FLAGS},
            errors=[error_category(error) for error in private['errors']])
        seconds = private.get('bootSeconds')
        if seconds is not None:
            need(type(seconds) in (int, float) and math.isfinite(seconds) and 0 <= seconds <= 1800)
            value['reportedBootMillis'] = round(seconds * 1000)
        for row in private['commands']:
            need(type(row) is dict)
            value['commands'].append(dict(label=row.get('label'), timeoutSeconds=row.get('timeoutSeconds'),
                exitCode=row.get('exitCode'), elapsedMillis=row.get('elapsedMillis')))
    if raw_instrumentation is not None:
        value['instrumentation'] = instrumentation(raw_instrumentation, root)
    return validate(value, root)


def validate(value, root):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'executionAdmitted', 'resultAvailable',
         'resultLog', 'reportedStatus', 'reportedFlags', 'reportedBootMillis', 'commands', 'errors',
         'instrumentation', 'driverLogs'} and type(value['schema']) is int and value['schema'] == 1 and
         value['scope'] == SCOPE and value['executionAdmitted'] is False and type(value['resultAvailable']) is bool)
    need(type(value['reportedFlags']) is dict and set(value['reportedFlags']) == set(FLAGS))
    if value['resultAvailable']:
        need(value['reportedStatus'] in ('PASS', 'FAIL') and value['resultLog'] is not None and
             all(type(n) is bool for n in value['reportedFlags'].values()))
    else:
        need(value['reportedStatus'] is None and value['resultLog'] is None and
             all(n is None for n in value['reportedFlags'].values()) and value['reportedBootMillis'] is None and
             value['commands'] == value['errors'] == [] and value['instrumentation'] is None)
    millis = value['reportedBootMillis']
    need(millis is None or type(millis) is int and 0 <= millis <= 1800000)
    need(type(value['commands']) is list and len(value['commands']) <= 512)
    labels = []
    for row in value['commands']:
        need(type(row) is dict and set(row) == {'label', 'timeoutSeconds', 'exitCode', 'elapsedMillis'} and
             type(row['label']) is str and row['label'] in COMMANDS and type(row['timeoutSeconds']) is int and
             row['timeoutSeconds'] == BOUNDS[row['label']] and
             (row['exitCode'] is None or type(row['exitCode']) is int and -255 <= row['exitCode'] <= 255) and
             (row['elapsedMillis'] is None or type(row['elapsedMillis']) is int and 0 <= row['elapsedMillis'] <= 1800000))
        labels.append(row['label'])
    need(all(labels.count(n) <= 1 for n in set(labels) - {'boot-state'}))
    need(type(value['errors']) is list and len(value['errors']) <= 64)
    for row in value['errors']:
        need(type(row) is dict and set(row) == {'category', 'command'} and row['category'] in CATEGORIES and
             (row['command'] in COMMANDS if row['category'] in
              ('COMMAND_FAILED', 'COMMAND_DEADLINE', 'SHELL_COMMAND_EXIT', 'SHELL_COMMAND_OUTPUT')
              else row['command'] is None))
    need(type(value['driverLogs']) is dict and set(value['driverLogs']) == {'stdout', 'stderr'})
    logs = [*value['driverLogs'].values()]
    if value['resultLog'] is not None:
        logs.append(value['resultLog'])
    item = value['instrumentation']
    if item is not None:
        need('rpc-controls' in labels and type(item) is dict and set(item) == {'log', 'terminalCodes',
            'reportedOutcome', 'reportedCleanup', 'reportedCompleted', 'failureStage', 'failureClass',
            'cleanupFailureClass', 'failureSite', 'failureErrno'})
        need(type(item['terminalCodes']) is list and len(item['terminalCodes']) <= 4 and
             all(type(n) is int and -255 <= n <= 255 for n in item['terminalCodes']))
        need(all(item[k] is None or type(item[k]) is str and item[k] in ('PASS', 'FAIL') for k in ('reportedOutcome', 'reportedCleanup')))
        need(item['reportedCompleted'] is None or type(item['reportedCompleted']) is int and 0 <= item['reportedCompleted'] <= 10)
        need(item['failureStage'] is None or type(item['failureStage']) is str and item['failureStage'] in (*STAGES, 'UNKNOWN'))
        need(all(item[k] is None or type(item[k]) is str and item[k] in CLASSES for k in ('failureClass', 'cleanupFailureClass')))
        need(item['failureErrno'] is None or type(item['failureErrno']) is int and 0 <= item['failureErrno'] <= 4095)
        site = item['failureSite']
        if site is not None:
            need(type(site) is dict and set(site) == {'file', 'line'} and type(site['line']) is int and
                 source_site(root, site['file'], str(site['line'])) == site)
        logs.append(item['log'])
    for log in logs:
        need(type(log) is dict and set(log) == {'bytes', 'sha256'} and type(log['bytes']) is int and
             0 <= log['bytes'] <= 32 * 1024 * 1024 and type(log['sha256']) is str and re.fullmatch('[a-f0-9]{64}', log['sha256']))
    return value
