"""Closed observations from the owned Apple OS probe; never product admission."""
from __future__ import annotations

import hashlib
import json
import re

NETWORK_MODES = ('network', 'network-late', 'network-txt', 'network-default-domain', 'network-legacy',
                 'network-production-shape', 'network-publish-txt', 'network-query-empty-txt',
                 'network-txt-tcp-parameters', 'network-separate-txt')
MODES = ('bsd', 'multicast-path', 'dns-any', 'dns-local', 'dns-resolve-txt', *NETWORK_MODES)
CONTEXTS = ('host', 'simulator')
LIMIT = 16384
COMMON = {'schema', 'mode', 'simulator', 'unprivileged', 'elapsedMillis', 'probeExit'}
MULTICAST_PATH_BOOLS = {'hasIpv4', 'connectionCreated', 'ready', 'waiting', 'failed', 'pathObserved',
                       'localNetworkDenied', 'cleanupComplete'}
MULTICAST_PATH_COUNTS = {'stateCallbacks', 'errorDomain', 'errorCode', 'pathStatus', 'pathReason'}
DNS_FIELDS = {'registrationStart', 'browseStart', 'registrationCallbacks', 'registrationCode',
              'browseCallbacks', 'browseCode', 'targetAdds', 'pollErrno', 'processingCode', 'referencesDeallocated',
              'localOnlyAdds', 'otherInterfaceAdds'}
RESOLVE_BOOLS = {'queriesStarted', 'resolvedTxtMatches', 'queriedTxtMatches', 'resolvedPortMatches', 'localTarget',
                 'referencesDeallocated'}
RESOLVE_OBSERVATION_BOOLS = {'localOnlyResolution', 'localOnlyQuery'}
RESOLVE_COUNTS = {'registrationCallbacks', 'resolveCallbacks', 'queryCallbacks', 'pollErrno'}
RESOLVE_CODES = {'registrationStart', 'registrationCode', 'resolveStart', 'resolveCode', 'queryStart', 'queryCode',
                 'processingCode'}
TARGET_KINDS = ('EMPTY', 'OVERSIZE', 'LOCAL_ABSOLUTE', 'LOCAL_RELATIVE', 'LOCALHOST', 'OTHER_ABSOLUTE', 'OTHER_RELATIVE')
NETWORK_BOOLS = {'hasIpv4', 'listenerReady', 'browserReady', 'connectionReady', 'cleanupComplete'}
NETWORK_OBSERVATION_BOOLS = {'txtLocalOnly', 'connectionLoopback'}
TXT_NETWORK_BOOLS = {'bonjourEndpoint', 'txtMatches', 'txtDeallocated'}
TXT_NETWORK_CODES = {'txtQueryStart', 'txtQueueCode', 'txtQueryCode'}
NETWORK_NUMBERS = {'listenerDomain', 'listenerCode', 'browserDomain', 'browserCode', 'connectionDomain',
                   'connectionCode', 'registrationAdds', 'browseCallbacks', 'targetAdds', 'acceptedConnections',
                   'pathStatus', 'pathReason', 'connectionPathReason', 'txtQueryCallbacks', 'resultInterfaces',
                   'resultLoopbackInterfaces', *TXT_NETWORK_CODES}
COMPILER_CATEGORIES = {
    'NULLABILITY': r'non-null|nonnull',
    'UNDECLARED_IDENTIFIER': r'undeclared identifier', 'IMPLICIT_FUNCTION': r'undeclared function|implicit declaration',
    'INCOMPATIBLE_POINTER': r'incompatible.*(?:pointer|type)', 'INVALID_MEMBER': r'no member named',
    'UNAVAILABLE_API': r'unavailable|deployment target', 'INVALID_ARGUMENT_COUNT': r'too (?:few|many) arguments',
    'UNUSED': r'unused', 'MISSING_INCLUDE': r'file not found', 'FORMAT': r'format specifies|format string',
    'SYNTAX': r'expected |extraneous |cannot initialize|read-only variable is not assignable',
}


def compiler_observation(raw, source):
    """Locations and source-declared symbols, never raw compiler messages/paths."""
    need(type(raw) is bytes and len(raw) <= 1048576)
    code = source.read_text()
    symbols = set(re.findall(r'\b[A-Za-z_][A-Za-z_0-9]*\b', code))
    rows = []
    pattern = re.compile(re.escape(str(source)) + r':([0-9]+):([0-9]+): (fatal error|error|warning|note): ([^\n]+)')
    for match in pattern.finditer(raw.decode(errors='replace')):
        message = match[4]
        category = next((key for key, pattern in COMPILER_CATEGORIES.items() if re.search(pattern, message)), 'OTHER')
        names = sorted(set(re.findall(r"'([A-Za-z_][A-Za-z_0-9]*)'", message)) & symbols)
        rows.append({'line': int(match[1]), 'column': int(match[2]), 'severity': match[3],
                     'category': category, 'symbols': names})
    result = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'diagnostics': rows}
    validate_compiler(result, source)
    return result


def validate_compiler(value, source):
    need(type(value) is dict and set(value) == {'sha256', 'bytes', 'diagnostics'} and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']) and
         type(value['bytes']) is int and 0 <= value['bytes'] <= 1048576 and
         type(value['diagnostics']) is list and len(value['diagnostics']) <= 64)
    code = source.read_text()
    symbols = set(re.findall(r'\b[A-Za-z_][A-Za-z_0-9]*\b', code))
    lines = code.splitlines()
    for row in value['diagnostics']:
        need(type(row) is dict and set(row) == {'line', 'column', 'severity', 'category', 'symbols'})
        integer(row['line'], 1, len(lines))
        integer(row['column'], 1, len(lines[row['line'] - 1]) + 1)
        need(row['severity'] in ('fatal error', 'error', 'warning', 'note') and
             row['category'] in (*COMPILER_CATEGORIES, 'OTHER') and type(row['symbols']) is list and
             len(row['symbols']) <= 16 and all(type(s) is str and s in symbols for s in row['symbols']))
    return value


def need(condition):
    if not condition:
        raise ValueError('Invalid closed Apple network diagnostic')


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result)
        result[key] = value
    return result


def integer(value, minimum=0, maximum=1000000):
    need(type(value) is int and minimum <= value <= maximum)


def validate_observation(value):
    need(type(value) is dict and type(value.get('mode')) is str and value['mode'] in MODES)
    mode = value['mode']
    fields = ({'interfaces'} if mode == 'bsd' else MULTICAST_PATH_BOOLS | MULTICAST_PATH_COUNTS if mode == 'multicast-path' else
              NETWORK_BOOLS | TXT_NETWORK_BOOLS | NETWORK_OBSERVATION_BOOLS | NETWORK_NUMBERS if mode in NETWORK_MODES else
              RESOLVE_BOOLS | RESOLVE_OBSERVATION_BOOLS | RESOLVE_COUNTS | RESOLVE_CODES | {'targetKind'} if mode == 'dns-resolve-txt' else DNS_FIELDS)
    need(set(value) == COMMON | fields and type(value['schema']) is int and value['schema'] == 1 and
         type(value['simulator']) is bool and value['unprivileged'] is True)
    integer(value['elapsedMillis'], maximum=60000)
    integer(value['probeExit'], maximum=3)
    if mode == 'bsd':
        need(type(value['interfaces']) is list and len(value['interfaces']) <= 64)
        for row in value['interfaces']:
            need(type(row) is dict and set(row) == {'privateIpv4', 'pointToPoint', 'setupErrno', 'sendErrno',
                                                   'closeErrno', 'sendReturned'})
            need(all(type(row[k]) is bool for k in ('privateIpv4', 'pointToPoint', 'sendReturned')))
            for key in ('setupErrno', 'sendErrno', 'closeErrno'):
                integer(row[key], maximum=255)
            need(not row['sendReturned'] or row['setupErrno'] == row['sendErrno'] == 0)
        if value['probeExit'] == 0:
            need(value['interfaces'] and all(row['sendReturned'] and row['closeErrno'] == 0 for row in value['interfaces']))
    elif mode == 'multicast-path':
        need(all(type(value[k]) is bool for k in MULTICAST_PATH_BOOLS))
        for key in MULTICAST_PATH_COUNTS:
            integer(value[key], minimum=-1000000 if key == 'errorCode' else 0)
        need(not value['localNetworkDenied'] or value['pathObserved'] and value['pathReason'] == 3)
        if value['probeExit'] == 0:
            need(all(value[k] for k in ('hasIpv4', 'connectionCreated', 'ready', 'pathObserved', 'cleanupComplete')) and
                 not value['localNetworkDenied'] and not value['failed'] and value['pathStatus'] == 1 and
                 value['errorDomain'] == value['errorCode'] == 0 and value['stateCallbacks'] > 0)
    elif mode in NETWORK_MODES:
        need(all(type(value[k]) is bool for k in NETWORK_BOOLS | TXT_NETWORK_BOOLS | NETWORK_OBSERVATION_BOOLS))
        need(value['bonjourEndpoint'] is (mode == 'network-separate-txt'))
        for key in NETWORK_NUMBERS:
            integer(value[key], minimum=-1000000)
        for key in ('registrationAdds', 'browseCallbacks', 'targetAdds', 'acceptedConnections', 'txtQueryCallbacks', 'resultInterfaces', 'resultLoopbackInterfaces'):
            integer(value[key])
        need(value['resultLoopbackInterfaces'] <= value['resultInterfaces'])
        if value['probeExit'] == 0:
            need(all(value[k] for k in NETWORK_BOOLS) and value['registrationAdds'] > 0 and value['targetAdds'] > 0 and
                  value['acceptedConnections'] > 0)
            if mode == 'network-separate-txt':
                need(all(value[k] for k in TXT_NETWORK_BOOLS) and value['txtQueryCallbacks'] > 0 and
                     all(value[k] == 0 for k in TXT_NETWORK_CODES))
    elif mode == 'dns-resolve-txt':
        need(type(value['targetKind']) is str and value['targetKind'] in TARGET_KINDS)
        need(not value['localTarget'] or value['targetKind'] == 'LOCAL_ABSOLUTE')
        need(all(type(value[k]) is bool for k in RESOLVE_BOOLS | RESOLVE_OBSERVATION_BOOLS))
        for key in RESOLVE_COUNTS:
            integer(value[key])
        for key in RESOLVE_CODES:
            integer(value[key], minimum=-1000000)
        if value['probeExit'] == 0:
            need(all(value[k] for k in RESOLVE_BOOLS) and value['pollErrno'] == 0 and
                 all(value[k] == 0 for k in RESOLVE_CODES) and
                 all(value[k] > 0 for k in ('registrationCallbacks', 'resolveCallbacks', 'queryCallbacks')))
    else:
        need(type(value['referencesDeallocated']) is bool)
        for key in DNS_FIELDS - {'referencesDeallocated'}:
            integer(value[key], minimum=-1000000)
        for key in ('registrationCallbacks', 'browseCallbacks', 'targetAdds', 'pollErrno', 'localOnlyAdds', 'otherInterfaceAdds'):
            integer(value[key])
        need(value['localOnlyAdds'] + value['otherInterfaceAdds'] == value['targetAdds'])
        if value['probeExit'] == 0:
            need(value['referencesDeallocated'] and value['registrationCallbacks'] > 0 and value['targetAdds'] > 0 and
                 all(value[k] == 0 for k in ('registrationStart', 'browseStart', 'registrationCode', 'browseCode',
                                           'pollErrno', 'processingCode')))
    return value


def observe(raw, context, mode, product_exit):
    need(type(raw) is bytes and 0 < len(raw) <= LIMIT and context in CONTEXTS and mode in MODES)
    value = validate_observation(json.loads(raw, object_pairs_hook=unique))
    need(value['mode'] == mode and value['simulator'] is (context == 'simulator') and
         type(product_exit) is int and value['probeExit'] == product_exit)
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'observation': value,
            'executionAdmitted': False}


def validate(value):
    need(type(value) is dict and set(value) <= {c + '-' + m for c in CONTEXTS for m in MODES})
    for label, entry in value.items():
        context, mode = label.split('-', 1)
        need(type(entry) is dict and set(entry) == {'sha256', 'bytes', 'observation', 'executionAdmitted'})
        need(type(entry['sha256']) is str and re.fullmatch('[0-9a-f]{64}', entry['sha256']) and
             type(entry['bytes']) is int and 0 < entry['bytes'] <= LIMIT and entry['executionAdmitted'] is False)
        observation = validate_observation(entry['observation'])
        need(observation['mode'] == mode and observation['simulator'] is (context == 'simulator'))
    return value
