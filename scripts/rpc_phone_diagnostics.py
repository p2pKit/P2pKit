"""Closed phone-tool observations, never XCTest, ownership or capacity admission.

Failed controller output stays private. Only fixed stages/categories, numeric
observations and hashes cross the handoff boundary; no argv, runtime/device IDs,
exception text, application data or result bundles are exported.
"""
from datetime import datetime
import hashlib
import json
import re

import rpc_product_diagnostics as product
import rpc_apple_boot_diagnostics as boot

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
DEVICE_ID = r'[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}'
DEVICE_INVENTORIES = ('simulator-initial', 'simulator-ready', 'simulator-before-shutdown',
                      'simulator-final', 'simulator-deleted')
DEVICE_STATES = ('Shutdown', 'Booting', 'Booted', 'Shutting Down', 'Creating', 'Unknown')


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


def device_inventory(raw, selected):
    """Counts from an existing owned simctl read, never authority over other devices.

    The selected UUID and all names/paths stay private. A booted device count
    describes coexisting simulator state, not CPU attribution or a readiness
    result. No additional command, wait, service mutation or boot is introduced.
    """
    need(type(raw) is bytes and 0 < len(raw) <= 16 * 1024 * 1024 and
         type(selected) is str and re.fullmatch(DEVICE_ID, selected))
    def unique(pairs):
        value = {}
        for key, field in pairs:
            need(key not in value)
            value[key] = field
        return value
    value = json.loads(raw, object_pairs_hook=unique)
    need(type(value) is dict and type(value.get('devices')) is dict and len(value['devices']) <= 64)
    seen, owned_state = set(), None
    others = dict.fromkeys(DEVICE_STATES, 0)
    for group in value['devices'].values():
        need(type(group) is list and len(group) <= 256)
        for row in group:
            need(type(row) is dict and type(row.get('udid')) is str and re.fullmatch(DEVICE_ID, row['udid']))
            identifier = row['udid'].lower()
            need(identifier not in seen and len(seen) < 4096)
            seen.add(identifier)
            state = row.get('state')
            state = state if type(state) is str and state in DEVICE_STATES else 'Unknown'
            if identifier == selected.lower():
                owned_state = state
            else:
                others[state] += 1
    return dict(sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), ownedState=owned_state, otherStates=others)


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
            if 'processObservation' in row:
                need(row.get('label') == 'boot-readiness' and 'bootProcesses' not in result)
                result['bootProcesses'] = boot.validate(row['processObservation'])
    need(type(logs) is dict and set(logs) <= {*COMMANDS, 'phone-controls'})
    for streams in logs.values():
        need(type(streams) is dict and set(streams) == {'stdout', 'stderr'})
    result['logs'] = {'logs': {name: {stream: product.log_observation(raw) for stream, raw in streams.items()}
                              for name, streams in logs.items()}}
    create = next((row for row in result['commands'] if row['label'] == 'create-simulator'), None)
    if create is not None and create['exitCode'] == 0 and 'create-simulator' in logs:
        selected = logs['create-simulator']['stdout'].decode('ascii').strip()
        need(re.fullmatch(DEVICE_ID, selected))
        inventories = {}
        for row in result['commands']:
            name = row['label']
            if name in DEVICE_INVENTORIES and row['exitCode'] == 0 and name in logs:
                inventories[name] = device_inventory(logs[name]['stdout'], selected)
        if inventories:
            result['deviceInventories'] = inventories
    return validate(result, root)


def validate(value, root):
    required = {'schema', 'scope', 'executionAdmitted', 'resultAvailable',
                'reportedStatus', 'reportedFlags', 'commands', 'errors', 'logs'}
    need(type(value) is dict and required <= set(value) <= required | {'bootProcesses', 'deviceInventories'} and
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
    if 'bootProcesses' in value:
        need(value['resultAvailable'] and 'boot-readiness' in labels)
        boot.validate(value['bootProcesses'])
    need(type(value['errors']) is list and len(value['errors']) <= 64)
    for row in value['errors']:
        need(type(row) is dict and set(row) == {'category', 'command'} and row['category'] in CATEGORIES and
             (row['command'] in COMMANDS if row['category'] in ('COMMAND_FAILED', 'COMMAND_DEADLINE') else row['command'] is None))
    need(type(value['logs']) is dict and set(value['logs']) == {'logs'} and
         type(value['logs']['logs']) is dict and set(value['logs']['logs']) <= {*labels, 'phone-controls'})
    product.validate(value['logs'], root, (*COMMANDS, 'phone-controls'))
    if 'deviceInventories' in value:
        inventories = value['deviceInventories']
        need(value['resultAvailable'] and 'create-simulator' in labels and
             type(inventories) is dict and 0 < len(inventories) <= len(DEVICE_INVENTORIES) and
             set(inventories) <= set(DEVICE_INVENTORIES) & set(labels) & set(value['logs']['logs']))
        need('create-simulator' in value['logs']['logs'] and
             next(row for row in rows if row['label'] == 'create-simulator')['exitCode'] == 0)
        for name, item in inventories.items():
            need(type(item) is dict and set(item) == {'sha256', 'bytes', 'ownedState', 'otherStates'} and
                 (item['ownedState'] is None or type(item['ownedState']) is str and item['ownedState'] in DEVICE_STATES) and
                 type(item['otherStates']) is dict and set(item['otherStates']) == set(DEVICE_STATES) and
                 all(type(n) is int and 0 <= n <= 4096 for n in item['otherStates'].values()) and
                 sum(item['otherStates'].values()) + (item['ownedState'] is not None) <= 4096)
            source = value['logs']['logs'][name]['stdout']
            need(type(item['bytes']) is int and 0 < item['bytes'] <= 16 * 1024 * 1024 and
                 type(item['sha256']) is str and item['sha256'] == source['sha256'] and item['bytes'] == source['bytes'])
            need(next(row for row in rows if row['label'] == name)['exitCode'] == 0)
    return value
