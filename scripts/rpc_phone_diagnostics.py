"""Closed phone-tool observations, never XCTest, ownership or capacity admission.

Failed controller output stays private. Only fixed stages/categories, numeric
observations and hashes cross the handoff boundary; no argv, runtime/device IDs,
exception text, application data or result bundles are exported.
"""
from datetime import datetime
import re

import rpc_product_diagnostics as product

SCOPE = 'PHONE_TOOL_OBSERVATIONS_NOT_TEST_OR_OWNERSHIP_ADMISSION'
COMMANDS = (
    'macos-version', 'xcode-version', 'xcodegen-version', 'runtimes', 'project-generation',
    'project-reference-inspection', 'framework-producer', 'create-simulator', 'simulator-initial',
    'boot-simulator', 'boot-readiness', 'simulator-ready', 'phone-unit-ui', 'xcresult-actions',
    *(f'xcresult-tests-{i}' for i in range(8)), 'unsigned-device-app', 'device-architectures',
    'device-minimum-os', 'simulator-before-shutdown', 'shutdown-simulator', 'simulator-final',
    'delete-simulator', 'simulator-deleted',
)
BOUNDS = {name: {'framework-producer': 3900, 'phone-unit-ui': 7200, 'unsigned-device-app': 7200}.get(name, 120)
          for name in COMMANDS}
FLAGS = ('simulatorTestsPassed', 'unsignedDeviceAppBuilt', 'simulatorShutdown', 'simulatorDeleted')
CATEGORIES = ('COMMAND_FAILED', 'COMMAND_DEADLINE', 'SIMULATOR_CLEANUP', 'FINAL_VERIFICATION', 'UNCLASSIFIED')
UTC = r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?\+00:00'


def need(condition):
    if not condition:
        raise RuntimeError('Malformed/private phone diagnostic observation')


def interval(row):
    values = {}
    for name in ('startedUtc', 'endedUtc'):
        if name in row:
            need(type(row[name]) is str and re.fullmatch(UTC, row[name]))
            try:
                values[name] = datetime.fromisoformat(row[name])
            except ValueError:
                need(False)
    # Wall-clock reversal is visible, never coerced into a passing deadline.
    return round((values['endedUtc'] - values['startedUtc']).total_seconds() * 1000) if len(values) == 2 else None


def error_category(text):
    need(type(text) is str and len(text) <= 65536)
    for category, prefix in (('COMMAND_FAILED', 'RuntimeError: Command failed: '),
                             ('COMMAND_DEADLINE', 'RuntimeError: Command deadline; native owner must drain: ')):
        if text.startswith(prefix) and text[len(prefix):] in COMMANDS:
            return dict(category=category, command=text[len(prefix):])
    for category, prefix in (('SIMULATOR_CLEANUP', 'Simulator cleanup: '),
                             ('FINAL_VERIFICATION', 'Final verification: ')):
        if text.startswith(prefix):
            return dict(category=category, command=None)
    return dict(category='UNCLASSIFIED', command=None)


def observe(private, logs, root):
    result = dict(schema=1, scope=SCOPE, executionAdmitted=False, resultAvailable=private is not None,
                  reportedStatus=None, reportedFlags={name: None for name in FLAGS}, commands=[], errors=[], logs={})
    if private is not None:
        need(type(private) is dict and type(private.get('commands')) is list and
             len(private['commands']) <= len(COMMANDS) and type(private.get('errors')) is list and
             len(private['errors']) <= 64)
        result.update(reportedStatus=private.get('status'), reportedFlags={name: private.get(name) for name in FLAGS},
                      errors=[error_category(text) for text in private['errors']])
        for row in private['commands']:
            need(type(row) is dict)
            result['commands'].append(dict(label=row.get('label'), timeoutSeconds=row.get('timeoutSeconds'),
                                           exitCode=row.get('exitCode'), elapsedMillis=interval(row)))
    need(type(logs) is dict and set(logs) <= {*COMMANDS, 'phone-controls'})
    for streams in logs.values():
        need(type(streams) is dict and set(streams) == {'stdout', 'stderr'})
    result['logs'] = {'logs': {name: {stream: product.log_observation(raw) for stream, raw in streams.items()}
                              for name, streams in logs.items()}}
    return validate(result, root)


def validate(value, root):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'executionAdmitted', 'resultAvailable',
         'reportedStatus', 'reportedFlags', 'commands', 'errors', 'logs'} and
         type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE and
         value['executionAdmitted'] is False and type(value['resultAvailable']) is bool)
    flags = value['reportedFlags']
    need(type(flags) is dict and set(flags) == set(FLAGS))
    if value['resultAvailable']:
        need(value['reportedStatus'] in ('FAIL', 'PASS_REQUIRES_OUTER_FINALIZATION') and
             all(type(v) is bool for v in flags.values()))
    else:
        need(value['reportedStatus'] is None and all(v is None for v in flags.values()) and
             value['commands'] == [] and value['errors'] == [])
    rows = value['commands']
    need(type(rows) is list and len(rows) <= len(COMMANDS))
    labels = []
    for row in rows:
        need(type(row) is dict and set(row) == {'label', 'timeoutSeconds', 'exitCode', 'elapsedMillis'} and
             type(row['label']) is str and row['label'] in COMMANDS and type(row['timeoutSeconds']) is int and
             row['timeoutSeconds'] == BOUNDS[row['label']] and
             (row['exitCode'] is None or type(row['exitCode']) is int and -255 <= row['exitCode'] <= 255) and
             (row['elapsedMillis'] is None or type(row['elapsedMillis']) is int and -172800000 <= row['elapsedMillis'] <= 172800000))
        labels.append(row['label'])
    need(len(labels) == len(set(labels)))
    need(type(value['errors']) is list and len(value['errors']) <= 64)
    for row in value['errors']:
        need(type(row) is dict and set(row) == {'category', 'command'} and row['category'] in CATEGORIES and
             (row['command'] in COMMANDS if row['category'] in ('COMMAND_FAILED', 'COMMAND_DEADLINE') else row['command'] is None))
    need(type(value['logs']) is dict and set(value['logs']) == {'logs'} and
         type(value['logs']['logs']) is dict and set(value['logs']['logs']) <= {*labels, 'phone-controls'})
    product.validate(value['logs'], root, (*COMMANDS, 'phone-controls'))
    return value
