#!/usr/bin/env python3
"""Closed observations of one bounded, read-only CoreSimulator log query.

Only the explicit Intel inventory experiment calls this helper. The original
native executor owns the log reader and all descendants within the SAME
120-second inventory deadline. Raw system records stay in private stderr;
no message, path, PID, device identifier or environment is exported.
This is not a readiness, permission, ownership or cleanup decision.
"""
from __future__ import annotations

import hashlib
import json
import re

BEGIN = 'RPC_INTEL_SERVICE_LOG_BEGIN'
END = 'RPC_INTEL_SERVICE_LOG_END_JSON:'
SCOPE = 'BOUNDED_CORESIMULATOR_LOG_OBSERVATION_NOT_ADMISSION'
MAX_BYTES = 4 * 1024 * 1024
QUERY_AFTER_NANOS = 60 * 10 ** 9
COMMAND = ('/usr/bin/log', 'show', '--style', 'ndjson', '--info', '--last', '120s', '--predicate',
           'process == "simctl" OR process == "com.apple.CoreSimulator.CoreSimulatorService" '
           'OR subsystem BEGINSWITH "com.apple.CoreSimulator"')
LEVELS = frozenset(('Default', 'Info', 'Debug', 'Error', 'Fault', 'Unknown'))
MARKERS = {
    'XPC_CONNECTION_INVALID': r'(?:CoreSimulatorService connection|Connection to CoreSimulatorService).*invalid|connection invalidated',
    'HELPER_COMMUNICATION_FAILED': r'could not communicate with a helper|couldn.t communicate with a helper',
    'XPC_CONNECTION_INTERRUPTED': r'connection interrupted|interrupted connection',
    'SERVICE_CONTEXT_INITIALIZATION': r'simserviceContextForDeveloperDir|initializ\w*.*SimServiceContext',
    'SERVICE_CONNECTION_FAILED': r'(?:Failed|Unable) to (?:connect|initialize).*CoreSimulator|CoreSimulator.*(?:connection refused|unavailable)',
    'SERVICE_VERSION_MISMATCH': r'CoreSimulatorService.*version.*(?:does not match|mismatch|incompatible)|'
                              r'(?:our|expected) version.*does not match.*(?:service|running)',
    'DEVICE_SET_INITIALIZATION_FAILED': r'(?:Failed|Unable) to (?:initialize|create|load|obtain).*(?:default )?device set',
    'BOOTSTRAP_LOOKUP_FAILED': r'bootstrap_look_up.*(?:failed|error)|(?:Failed|Unable) to look up.*(?:service|bootstrap)',
    'RUNTIME_MOUNT_FAILED': r'(?:Failed|Unable) to mount|disk image.*(?:invalid|unavailable|failed)',
    'RUNTIME_PROFILE_MISSING': r'Runtime profile not found|runtime.*(?:unavailable|not available|not supported)',
    'DYLD_CACHE_MENTIONED': r'dyld_shared_cache|dyld.*cache',
    'DYLD_CACHE_MISSING': r'(?:missing|no|not found).*dyld.*cache|dyld.*cache.*(?:missing|not found)',
    'PERMISSION_DENIED': r'Operation not permitted|Permission denied|not authori[sz]ed',
    'SERVICE_TIMED_OUT': r'timed out|timeout|deadline exceeded',
    'SERVICE_WAITING': r'waiting (?:for|on)|wait for',
    'SERVICE_CRASHED': r'crashed|crash report|unexpectedly exited',
    'FIRST_LAUNCH_REQUIRED': r'first launch.*(?:required|not complete)|runFirstLaunch',
    'DISK_SPACE_FAILED': r'No space left on device|insufficient disk space',
}


def need(value):
    if not value:
        raise ValueError('Invalid closed CoreSimulator log observation')


def unique(pairs):
    value = {}
    for key, item in pairs:
        need(key not in value)
        value[key] = item
    return value


def validate(value):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'executionAdmitted', 'bytes', 'sha256',
         'readerExitCode', 'records', 'unclassifiedRecords', 'levels', 'markers'} and
         type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE and
         value['executionAdmitted'] is False)
    need(type(value['bytes']) is int and 0 < value['bytes'] <= MAX_BYTES and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']))
    need(value['readerExitCode'] is None or type(value['readerExitCode']) is int and
         -255 <= value['readerExitCode'] <= 255)
    need(all(type(value[k]) is int and 0 <= value[k] <= 32768 for k in ('records', 'unclassifiedRecords')) and
         value['unclassifiedRecords'] <= value['records'])
    for key, allowed in (('levels', LEVELS), ('markers', MARKERS)):
        need(type(value[key]) is dict and set(value[key]) <= set(allowed) and
             all(type(n) is int and 0 < n <= value['records'] for n in value[key].values()))
    need(sum(value['levels'].values()) == value['records'])
    return value


def observation(raw):
    """Reread the actual private command log; arbitrary records never leave it."""
    need(type(raw) is bytes and len(raw) <= MAX_BYTES)
    started = False
    ended = False
    code = None
    records = unclassified = 0
    levels, markers = {}, {}
    for line in raw.decode('utf-8').splitlines():
        if line == BEGIN:
            need(not started)
            started = True
        elif line.startswith(END):
            need(started and not ended)
            row = json.loads(line[len(END):], object_pairs_hook=unique)
            need(type(row) is dict and set(row) == {'exitCode'} and type(row['exitCode']) is int and
                 -255 <= row['exitCode'] <= 255)
            code, ended = row['exitCode'], True
        elif started and not ended and line.startswith('{'):
            need(len(line) <= 1024 * 1024)
            row = json.loads(line, object_pairs_hook=unique)
            need(type(row) is dict)
            # Apple's ndjson includes a fixed header record as well as events.
            # Only eventMessage records contribute to diagnostic event counts.
            if 'eventMessage' not in row:
                continue
            message = row['eventMessage']
            need(type(message) is str and len(message) <= 1024 * 1024)
            records += 1
            need(records <= 32768)
            level = row.get('messageType')
            level = level if type(level) is str and level in LEVELS else 'Unknown'
            levels[level] = levels.get(level, 0) + 1
            found = [name for name, pattern in MARKERS.items() if re.search(pattern, message, re.IGNORECASE)]
            unclassified += not found
            for name in found:
                markers[name] = markers.get(name, 0) + 1
    if not started:
        return None  # A completed fast inventory does not need this observation.
    return validate(dict(schema=1, scope=SCOPE, executionAdmitted=False, bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(), readerExitCode=code, records=records,
        unclassifiedRecords=unclassified, levels=levels, markers=markers))
