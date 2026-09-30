"""Closed observations from the owned Apple OS probe; never product admission."""
from __future__ import annotations

import hashlib
import json
import re

MODES = ('bsd', 'dns-any', 'dns-local', 'network')
CONTEXTS = ('host', 'simulator')
LIMIT = 16384
COMMON = {'schema', 'mode', 'simulator', 'unprivileged', 'elapsedMillis', 'probeExit'}
DNS_FIELDS = {'registrationStart', 'browseStart', 'registrationCallbacks', 'registrationCode',
              'browseCallbacks', 'browseCode', 'targetAdds', 'pollErrno', 'processingCode', 'referencesDeallocated'}
NETWORK_BOOLS = {'hasIpv4', 'listenerReady', 'browserReady', 'connectionReady', 'cleanupComplete'}
NETWORK_NUMBERS = {'listenerDomain', 'listenerCode', 'browserDomain', 'browserCode', 'connectionDomain',
                   'connectionCode', 'registrationAdds', 'browseCallbacks', 'targetAdds', 'acceptedConnections',
                   'pathStatus', 'pathReason', 'connectionPathReason'}


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
    fields = {'interfaces'} if mode == 'bsd' else NETWORK_BOOLS | NETWORK_NUMBERS if mode == 'network' else DNS_FIELDS
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
    elif mode == 'network':
        need(all(type(value[k]) is bool for k in NETWORK_BOOLS))
        for key in NETWORK_NUMBERS:
            integer(value[key], minimum=-1000000)
        for key in ('registrationAdds', 'browseCallbacks', 'targetAdds', 'acceptedConnections'):
            integer(value[key])
        if value['probeExit'] == 0:
            need(all(value[k] for k in NETWORK_BOOLS) and value['registrationAdds'] > 0 and value['targetAdds'] > 0 and
                 value['acceptedConnections'] > 0)
    else:
        need(type(value['referencesDeallocated']) is bool)
        for key in DNS_FIELDS - {'referencesDeallocated'}:
            integer(value[key], minimum=-1000000)
        for key in ('registrationCallbacks', 'browseCallbacks', 'targetAdds', 'pollErrno'):
            integer(value[key])
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
