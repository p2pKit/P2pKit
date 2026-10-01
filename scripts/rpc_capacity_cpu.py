"""Opt-in, test-only CPU placement of an owned launcher and its future children.

Never a production dispatcher override, affinity change to another process,
extra runner allocation, physical-core claim or capacity verdict. Linux guest
topology is not proof of the hypervisor's physical CPU placement. The default
launcher remains inherited/unmodified; the hosted experiment explicitly selects
two disjoint two-logical-CPU sets made from complete guest-reported core groups.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import sys

INHERITED = 'inherited'
SPLIT = 'split-guest-cores'
POLICIES = (INHERITED, SPLIT)
SCOPE = 'OWNED_LAUNCHER_AFFINITY_NOT_EXCLUSIVE_PHYSICAL_CPU_OR_CAPACITY'


def need(condition):
    if not condition:
        raise ValueError('CPU placement requires complete unchanged guest topology and owned inheritance')


def cpus(value):
    need(type(value) is list and 0 < len(value) <= 256 and
         all(type(n) is int and 0 <= n <= 4095 for n in value) and value == sorted(set(value)))
    return value


def parse_cpus(raw):
    need(type(raw) is str and 0 < len(raw) <= 4096 and
         re.fullmatch(r'(?:0|[1-9][0-9]{0,3})(?:-(?:0|[1-9][0-9]{0,3}))?'
                      r'(?:,(?:0|[1-9][0-9]{0,3})(?:-(?:0|[1-9][0-9]{0,3}))?)*\n?', raw))
    result = []
    for field in raw.strip().split(','):
        bounds = list(map(int, field.split('-')))
        first, last = bounds[0], bounds[-1]
        need(first <= last <= 4095 and last - first < 256)
        result.extend(range(first, last + 1))
    return cpus(result)


def text(path):
    # Read-only sysfs observation; no shell, sysctl, affinity of a foreign PID,
    # CPU hotplug, cpuset/cgroup modification or privileged operation.
    with path.open('r', encoding='ascii') as stream:
        result = stream.read(4097)
    need(len(result) <= 4096)
    return result


def topology(available, base=Path('/sys/devices/system/cpu')):
    cpus(available)
    need(len(available) == 4)
    online = parse_cpus(text(base / 'online'))
    need(set(available) <= set(online))
    rows = []
    for cpu in available:
        directory = base / ('cpu' + str(cpu)) / 'topology'
        values = []
        for name in ('physical_package_id', 'core_id'):
            raw = text(directory / name)
            need(re.fullmatch(r'(?:0|[1-9][0-9]{0,3})\n?', raw))
            values.append(int(raw))
        siblings = parse_cpus(text(directory / 'thread_siblings_list'))
        need(cpu in siblings and set(siblings) <= set(available))
        rows.append(dict(cpu=cpu, package=values[0], core=values[1], siblings=siblings))
    # Every member must independently report the same group. Never split an
    # incomplete/ambiguous sibling group to make a particular runner admissible.
    groups = []
    for row in rows:
        peers = [other for other in rows if (other['package'], other['core']) == (row['package'], row['core'])]
        need(all(other['siblings'] == row['siblings'] for other in peers) and
             [other['cpu'] for other in peers] == row['siblings'])
        if row['cpu'] == row['siblings'][0]:
            groups.append(dict(package=row['package'], core=row['core'], cpus=row['siblings']))
    need(parse_cpus(text(base / 'online')) == online)
    return dict(onlineCpus=online, guestCores=groups)


def plan(available, observed):
    cpus(available)
    need(len(available) == 4 and type(observed) is dict and set(observed) == {'onlineCpus', 'guestCores'})
    cpus(observed['onlineCpus'])
    need(set(available) <= set(observed['onlineCpus']))
    groups = observed['guestCores']
    need(type(groups) is list and len(groups) in (2, 3, 4))
    covered, identities, firsts = [], [], []
    for group in groups:
        need(type(group) is dict and set(group) == {'package', 'core', 'cpus'} and
             all(type(group[k]) is int and 0 <= group[k] <= 9999 for k in ('package', 'core')))
        cpus(group['cpus'])
        need(len(group['cpus']) <= 2)
        covered.extend(group['cpus'])
        identities.append((group['package'], group['core']))
        firsts.append(group['cpus'][0])
    need(sorted(covered) == available and len(set(identities)) == len(groups) and firsts == sorted(firsts))
    # Deterministic, topology-bound two-plus-two split, not adaptive tuning based
    # on measured latency or a retry of a failed workload.
    selected = []
    for group in groups:
        if len(selected) + len(group['cpus']) <= 2:
            selected.extend(group['cpus'])
    need(len(selected) == 2)
    return dict(policy=SPLIT, availableCpus=list(available), topology=copy.deepcopy(observed),
                hostCpus=sorted(selected), clientCpus=sorted(set(available) - set(selected)))


def validate(value, role):
    need(role in ('host', 'client') and type(value) is dict and set(value) == {
        'schema', 'scope', 'role', 'plan', 'launcherBefore', 'launcherStarted', 'launcherFinished',
        'childMainSamples', 'childMainCpus', 'topologyUnchanged', 'capacityQualified'})
    need(type(value['schema']) is int and value['schema'] == 1 and value['scope'] == SCOPE and
         value['role'] == role and value['capacityQualified'] is False and value['topologyUnchanged'] is True)
    p = value['plan']
    need(type(p) is dict and set(p) == {'policy', 'availableCpus', 'topology', 'hostCpus', 'clientCpus'})
    need(p == plan(p['availableCpus'], p['topology']))
    expected = p[role + 'Cpus']
    for key in ('launcherBefore', 'launcherStarted', 'launcherFinished', 'childMainCpus'):
        cpus(value[key])
    need(value['launcherBefore'] == p['availableCpus'] and
         value['launcherStarted'] == value['launcherFinished'] == value['childMainCpus'] == expected and
         type(value['childMainSamples']) is int and 0 < value['childMainSamples'] <= 5000)
    return copy.deepcopy(value)


def begin(policy, role):
    need(policy in POLICIES and role in ('host', 'client'))
    if policy == INHERITED:
        return None  # The existing per-machine launcher is not changed implicitly.
    need(sys.platform == 'linux' and os.getuid() == os.geteuid() != 0 and
         len(os.listdir('/proc/self/task')) == 1)
    before = sorted(os.sched_getaffinity(0))
    observed = topology(before)
    p = plan(before, observed)
    need(sorted(os.sched_getaffinity(0)) == before)
    # PID 0 changes only this single-threaded owned launcher. Future JVM/JFR
    # children inherit normally; the native owner/controller is not repinned.
    os.sched_setaffinity(0, p[role + 'Cpus'])
    started = sorted(os.sched_getaffinity(0))
    need(started == p[role + 'Cpus'])
    return dict(schema=1, scope=SCOPE, role=role, plan=p, launcherBefore=before,
                launcherStarted=started, launcherFinished=None, childMainSamples=0,
                childMainCpus=None, topologyUnchanged=False, capacityQualified=False)


def observe_child(proof, child):
    if proof is None:
        return
    # The caller passes its directly created, not-yet-reaped Popen child. That
    # lifetime cannot be reused before wait(). This is read-only observation,
    # never ownership discovery, signaling, attach or permission to touch a PID.
    need(child.returncode is None and type(child.pid) is int and child.pid > 0)
    observed = sorted(os.sched_getaffinity(child.pid))
    need(observed == proof['plan'][proof['role'] + 'Cpus'] and proof['childMainSamples'] < 5000)
    proof['childMainSamples'] += 1
    proof['childMainCpus'] = observed


def finish(proof):
    if proof is None:
        return
    proof['launcherFinished'] = sorted(os.sched_getaffinity(0))
    proof['topologyUnchanged'] = topology(proof['launcherBefore']) == proof['plan']['topology']
    validate(proof, proof['role'])
