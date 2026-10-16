"""Closed, read-only hosted runner observations for the same-source image comparison.

No benchmark tuning, hardware reservation, physical-core claim, ownership grant,
permission changes or capacity verdict. Model/topology and kernel observations
make unlike allocations visible; identical metadata does not prove equivalent
physical machines. Never export hostname, serials, environment or cpuinfo text.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import platform
import re

import rpc_capacity_cpu as cpu

IMAGES = {'ubuntu-22.04': ('ubuntu22', '22.04'), 'ubuntu-24.04': ('ubuntu24', '24.04')}
BASELINE_MARKER = '[rpc-capacity]'
COMPARISON_MARKER = '[rpc-capacity-compare]'
UBUNTU22_MARKER = '[rpc-capacity-ubuntu22]'
MARKERS = {'baseline': BASELINE_MARKER, 'image-comparison': COMPARISON_MARKER,
           'ubuntu22-follow-through': UBUNTU22_MARKER}
SCOPE = 'GUEST_RUNNER_OBSERVATION_NOT_PHYSICAL_ALLOCATION_OR_CAPACITY'
CPU_FIELDS = {'cpu family': 'family', 'model': 'model', 'stepping': 'stepping',
              'physical id': 'package', 'core id': 'core', 'cpu cores': 'cores', 'siblings': 'siblings'}


def need(condition):
    if not condition:
        raise ValueError('Incomplete or mismatched closed capacity runner observation')


def request(env, message=None):
    image, mode = env.get('RPC_CAPACITY_RUNNER'), env.get('RPC_CAPACITY_EXPERIMENT')
    need(type(image) is str and image in IMAGES and type(mode) is str and mode in MARKERS and
         env.get('ImageOS') == IMAGES[image][0])
    need(mode == 'image-comparison' or
         mode == 'baseline' and image == 'ubuntu-24.04' or
         mode == 'ubuntu22-follow-through' and image == 'ubuntu-22.04')
    if message is not None:
        need(type(message) is str and len(message) <= 65536)
        need(MARKERS[mode] in message and all(marker not in message
                                            for key, marker in MARKERS.items() if key != mode))
    return dict(runner=image, experiment=mode, imageOS=IMAGES[image][0])


def bounded(path):
    with path.open('r', encoding='ascii') as stream:
        raw = stream.read(1024 * 1024 + 1)
    need(0 < len(raw) <= 1024 * 1024)
    return raw


def distribution(raw, image):
    need(type(raw) is str and image in IMAGES and len(raw) <= 65536)
    result = {}
    for line in raw.splitlines():
        if line.startswith(('ID=', 'VERSION_ID=')):
            key, value = line.split('=', 1)
            need(key not in result)
            result[key] = value[1:-1] if value.startswith('"') and value.endswith('"') else value
    need(result == {'ID': 'ubuntu', 'VERSION_ID': IMAGES[image][1]})
    return list(map(int, IMAGES[image][1].split('.')))


def kernel(raw):
    need(type(raw) is str and 0 < len(raw) <= 128)
    match = re.fullmatch(r'([0-9]{1,4})\.([0-9]{1,4})\.([0-9]{1,4})(?:-([0-9]{1,6}))?'
                         r'(?:-([A-Za-z0-9._-]{1,64}))?', raw)
    need(match is not None)
    return dict(version=[int(n) for n in match.group(1, 2, 3)],
                abi=None if match[4] is None else int(match[4]),
                flavor={'azure': 'AZURE', 'generic': 'GENERIC'}.get(match[5], 'OTHER'))


def identification(raw, available):
    need(type(raw) is str and 0 < len(raw) <= 1024 * 1024)
    cpu.cpus(available)
    rows, seen = [], set()
    for entry in re.split(r'\n\s*\n', raw.strip()):
        fields = {}
        for line in entry.splitlines():
            key, sep, value = line.partition(':')
            key, value = key.strip(), value.strip()
            if sep and key in {'processor', 'vendor_id', *CPU_FIELDS}:
                need(key not in fields)
                fields[key] = value
        need(re.fullmatch(r'[0-9]{1,4}', fields.get('processor', '')) is not None)
        n = int(fields['processor'])
        need(n not in seen)
        seen.add(n)
        if n not in available:
            continue
        need(set(fields) == {'processor', 'vendor_id', *CPU_FIELDS})
        row = dict(cpu=n, vendor={'GenuineIntel': 'INTEL', 'AuthenticAMD': 'AMD'}.get(fields['vendor_id'], 'OTHER'))
        for key, output in CPU_FIELDS.items():
            need(re.fullmatch(r'[0-9]{1,4}', fields[key]) is not None)
            row[output] = int(fields[key])
        rows.append(row)
    need(sorted(row['cpu'] for row in rows) == available)
    return sorted(rows, key=lambda row: row['cpu'])


def validate(value):
    need(type(value) is dict and set(value) == {'schema', 'scope', 'request', 'osVersion', 'kernel',
                                              'availableCpus', 'topology', 'cpuIdentification'})
    need(type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE)
    r = value['request']
    need(type(r) is dict and set(r) == {'runner', 'experiment', 'imageOS'})
    need(request(dict(RPC_CAPACITY_RUNNER=r['runner'], RPC_CAPACITY_EXPERIMENT=r['experiment'], ImageOS=r['imageOS'])) == r)
    version = value['osVersion']
    need(type(version) is list and all(type(n) is int for n in version) and
         version == list(map(int, IMAGES[r['runner']][1].split('.'))))
    k = value['kernel']
    need(type(k) is dict and set(k) == {'version', 'abi', 'flavor'} and
         type(k['version']) is list and len(k['version']) == 3 and
         all(type(n) is int and 0 <= n <= 9999 for n in k['version']) and
         (k['abi'] is None or type(k['abi']) is int and 0 <= k['abi'] <= 999999) and
         k['flavor'] in ('AZURE', 'GENERIC', 'OTHER'))
    p = cpu.plan(value['availableCpus'], value['topology'])
    rows = value['cpuIdentification']
    need(type(rows) is list and len(rows) == len(p['availableCpus']))
    for index, row in enumerate(rows):
        need(type(row) is dict and set(row) == {'cpu', 'vendor', *CPU_FIELDS.values()} and
             row['vendor'] in ('INTEL', 'AMD', 'OTHER') and
             all(type(row[key]) is int and 0 <= row[key] <= 9999 for key in {'cpu', *CPU_FIELDS.values()}) and
             row['cpu'] == p['availableCpus'][index] and 1 <= row['cores'] <= row['siblings'])
        group = next(g for g in p['topology']['guestCores'] if row['cpu'] in g['cpus'])
        need((row['package'], row['core']) == (group['package'], group['core']))
    return copy.deepcopy(value)


def observe(env, os_release=Path('/etc/os-release'), cpuinfo=Path('/proc/cpuinfo')):
    r = request(env)
    need(platform.system() == 'Linux' and platform.machine() == 'x86_64')
    available = sorted(os.sched_getaffinity(0))
    value = dict(schema=1, scope=SCOPE, request=r, osVersion=distribution(bounded(os_release), r['runner']),
                 kernel=kernel(platform.release()), availableCpus=available, topology=cpu.topology(available),
                 cpuIdentification=identification(bounded(cpuinfo), available))
    need(sorted(os.sched_getaffinity(0)) == available)
    return validate(value)
