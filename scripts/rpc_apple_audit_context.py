"""One explicit Intel runtime experiment in the original nonroot audit context.

This does not grant local-network permission or native ownership. It avoids
creating a Terminal application while retaining the SAME audit bootstrap,
native controls, multicast, source, architecture and simulator deadlines.
All ordinary Apple/ARM lanes remain unchanged. No service or security setting
is changed here. Bonjour preparation is independently admitted and restored.
"""
from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import sys

import rpc_apple_runner_context as context

ROOT = Path(__file__).resolve().parents[1]
MARKER = '[rpc-intel-audit-context]'
SCOPE = 'EXPLICIT_INTEL_AUDIT_CONTEXT_NOT_OWNERSHIP_PERMISSION_OR_LAN'


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


private = module('audit_context_private_files', 'with-darwin-launchd-context.py')
session = module('audit_context_original_session', 'with-darwin-audit-session.py')
need = private.need
BOOTSTRAP = dict(schema=1, scope='PROCESS_LOCAL_AUDIT_SESSION_NOT_OWNERSHIP_OR_PRODUCT_ADMISSION',
    freshAssignedSession=True, auditPolicyPreserved=True, invokingCredentialsRestored=True,
    rootCannotBeRegained=True, privilegedObservationOrProductExecution=False)
FLAGS = ('freshAssignedSession', 'auditPolicyPreserved', 'invokingCredentialsRestored',
         'rootCannotBeRegained', 'nativeSessionObserved')
FAILURE_LABELS = {
    'Exact source working directory required': 'WORKING_DIRECTORY',
    'Exact original runtime arguments required': 'COMMAND_ARGUMENTS',
    'Exact original runtime interpreter required': 'COMMAND_INTERPRETER',
    'Original nonroot credentials required': 'NONROOT_CREDENTIALS',
    'Exact disposable feature workflow required': 'WORKFLOW',
    'Private task context required': 'TASK_CONTEXT',
    'Unchanged source required': 'SOURCE',
    'Bootstrap command/source context changed': 'BOOTSTRAP_CONTEXT',
    'Original unprivileged audit bootstrap did not admit this child': 'BOOTSTRAP_RECEIPT',
    'Original assigned session did not survive into the nonroot native controller': 'NATIVE_SESSION',
    **private.SOURCE_CHECKS,
}


def failure_label(error):
    """Closed diagnostic only. Never export exception text or award admission."""
    if type(error) is private.ContextFailure:
        return FAILURE_LABELS.get(str(error), 'OTHER_CONTEXT_CHECK')
    return 'UNCLASSIFIED_FAILURE'


def requested(env):
    flag = env.get('RPC_APPLE_AUDIT_CONTEXT')
    need(flag in (None, 'true', 'false'), 'Explicit Boolean audit-context request required')
    if flag != 'true':
        return False
    need(env.get('RPC_APPLE_LANE') == 'apple-x64' and env.get('RPC_INTEL_INVESTIGATION') == 'runtime' and
         env.get('RPC_ADMISSION_ONLY') == 'false' and env.get('RPC_APPLE_BONJOUR_ADVERTISING') == 'true' and
         all(env.get(key) == 'false' for key in
             ('RPC_APPLE_TERMINAL_CONTEXT', 'RPC_APPLE_SSH_CONTEXT', 'RPC_APPLE_LAUNCHD_CONTEXT')),
         'Only the explicit original Intel runtime inventory may select the audit-context experiment')
    return True


def validate(value, source):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'source', 'nativeLane', 'executionMode',
         'configSha256', 'bootstrapReceiptSha256', 'privilegedObservationOrProductExecution', *FLAGS} and
         type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE and
         value['source'] == source and value['nativeLane'] == 'apple-x64' and value['executionMode'] == 'runtime',
         'Closed exact-source Intel audit-context record required')
    need(all(value[k] is True for k in FLAGS) and value['privilegedObservationOrProductExecution'] is False and
         all(type(value[k]) is str and re.fullmatch('[0-9a-f]{64}', value[k])
             for k in ('configSha256', 'bootstrapReceiptSha256')), 'Incomplete native session preparation')
    return value


def expected(env, parent, source):
    """Reconcile both original private bootstrap records, before work and on collection."""
    need(requested(env) and context.native_lane(env) == 'apple-x64', 'Explicit native Intel experiment required')
    need(os.getuid() == os.geteuid() != 0 and os.getgid() == os.getegid() != 0,
         'Original nonroot credentials required')
    need(env.get('GITHUB_ACTIONS') == 'true' and env.get('RUNNER_ENVIRONMENT') == 'github-hosted' and
         env.get('GITHUB_REPOSITORY') == 'p2pKit/P2pKit' and env.get('GITHUB_REF') == private.REF and
         env.get('GITHUB_EVENT_NAME') == 'push' and env.get('RPC_QUALIFY_REQUESTED') == 'true' and
         env.get('DEVELOPER_DIR') == '/Applications/Xcode_26.3.app/Contents/Developer',
         'Exact disposable feature workflow required')
    need(Path(env['GITHUB_WORKSPACE']).resolve(strict=True) == ROOT and
         Path(env['RPC_QUALIFICATION_PARENT']) == parent and
         parent != Path(env['RUNNER_TEMP']).resolve(strict=True) and
         parent.is_relative_to(Path(env['RUNNER_TEMP']).resolve(strict=True)), 'Private task context required')
    private.private_parent(parent, os.getuid())
    need(source == private.source_snapshot() and source['commit'] == env['GITHUB_SHA'], 'Unchanged source required')
    config_path, receipt_path = parent / 'session-config.json', parent / 'session-admission.json'
    config, receipt = private.read_json(config_path), private.read_json(receipt_path)
    session.validate(config, os.getuid(), os.getgid())
    need(config['cwd'] == str(ROOT), 'Exact source working directory required')
    need(config['argv'][1:] == [str(ROOT / 'scripts/run-rpc-qualification.py'), 'run', '--lane', 'apple-x64',
        '--intel-investigation', 'runtime', '--require-bonjour-advertising'], 'Exact original runtime arguments required')
    need(config['argv'][0] == str(Path(sys.executable).absolute()), 'Exact original runtime interpreter required')
    original = config['environment']
    need(requested(original) and all(original.get(k) == env.get(k) for k in (
        'GITHUB_SHA', 'GITHUB_WORKSPACE', 'GITHUB_REPOSITORY', 'GITHUB_REF', 'GITHUB_EVENT_NAME',
        'GITHUB_ACTIONS', 'RUNNER_ENVIRONMENT', 'RPC_QUALIFICATION_PARENT', 'RUNNER_TEMP',
        'RPC_QUALIFY_REQUESTED', 'DEVELOPER_DIR')), 'Bootstrap command/source context changed')
    need(type(receipt) is dict and set(receipt) == {*BOOTSTRAP, 'previousSessionAssigned'} and
         type(receipt['previousSessionAssigned']) is bool and
         all(type(receipt[k]) is type(v) and receipt[k] == v for k, v in BOOTSTRAP.items()),
         'Original unprivileged audit bootstrap did not admit this child')
    return validate(dict(schema=1, scope=SCOPE, source=source, nativeLane='apple-x64', executionMode='runtime',
        configSha256=hashlib.sha256(private.read_private(config_path, os.getuid())).hexdigest(),
        bootstrapReceiptSha256=hashlib.sha256(private.read_private(receipt_path, os.getuid())).hexdigest(),
        privilegedObservationOrProductExecution=False, **dict.fromkeys(FLAGS, True)), source)


def admit(env, parent, source):
    proof = expected(env, parent, source)
    value = session.AuditInfo()
    native = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    native.getaudit_addr.argtypes = [ctypes.POINTER(session.AuditInfo), ctypes.c_int]
    native.getaudit_addr.restype = ctypes.c_int
    need(ctypes.sizeof(value) == 48 and native.getaudit_addr(ctypes.byref(value), 48) == 0 and
         value.asid not in (0, -1) and env.get('SECURITYSESSIONID') == format(value.asid, 'x'),
         'Original assigned session did not survive into the nonroot native controller')
    private.write_json(parent / 'audit-context.json', proof)
    return proof


def recheck(env, parent, source):
    proof = validate(private.read_json(parent / 'audit-context.json'), source)
    need(proof == expected(env, parent, source), 'Native session context differs from original private records')
    return proof
