"""Bounded diagnostic observations, NEVER test/ownership admission.

Only source-known task/method identifiers, fixed marker enums, counts and hashes
may cross the hosted artifact boundary. Raw output, messages, endpoints, UUIDs,
environments, payloads and result bundles remain private.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

MAX_LOG = 256 * 1024 * 1024
MAX_XML = 16 * 1024 * 1024
MARKERS = {
    'TESTS_FAILED': r'There were failing tests|There are test failures',
    'BOOT_FAILED': r'Unable to boot|Failed to boot|could not be booted|Unable to shutdown',
    'BOOT_TIMEOUT': r'boot.*timed out|Timed out.*boot|Timed out waiting for Simulator',
    'SPAWN_FAILED': r'Failed to spawn|Unable to spawn|Failed to launch|Failed to execute test',
    'RUNTIME_UNAVAILABLE': r'runtime.*(?:unavailable|not available|not supported)|Runtime profile not found',
    'ARCHITECTURE_UNSUPPORTED': r'Bad CPU type|Incompatible architecture|Unsupported architecture|unsupported architecture',
    'WAIT_BACKBOARD': r'Waiting on BackBoard',
    'WAIT_MIGRATION': r'Waiting on Data Migration|Waiting for Data Migration',
    'WAIT_SYSTEM_APP': r'Waiting on System App|Waiting for System App',
    'ALREADY_BOOTED': r'Device already booted',
    'BOOT_FINISHED': r'Finished|Boot status is:.*Booted',
    'DEVICE_FINALIZED': r"property 'device' is final",
    'LINK_FAILED': r'linker command failed|linking failed',
    'COMPILATION_FAILED': r'Compilation failed|Compilation error',
    'NATIVE_CRASH': r'SIGSEGV|SIGABRT|Segmentation fault|Abort trap',
    'NETWORK_UNREACHABLE': r'NoRouteToHostException|Network is unreachable',
    'WARNING_MODE_FAILED': r'Warnings found and --warning-mode fail',
}
DOMAINS = ('NSPOSIXErrorDomain', 'com.apple.CoreSimulator.SimError', 'com.apple.CoreSimulator.SimErrorDomain',
           'com.apple.SimLaunchHostService.RequestError', 'FBSOpenApplicationServiceErrorDomain')
STATES = ('Shutdown', 'Booting', 'Booted', 'Shutting Down', 'Creating')
OUTCOMES = ('EXECUTED', 'FAILED', 'NO_SOURCE', 'SKIPPED', 'UP-TO-DATE', 'FROM-CACHE',
            'NOT_COMPLETED', 'NOT_REQUESTED')
FAILURE_MARKERS = {
    'UNEXPECTED_DIAGNOSTIC': r'Unexpected warn/error diagnostics recorded',
    'SETUP_AFTER_STOP': r'P2pKit stopped before the session could be committed',
    'TIMEOUT': r'TimeoutCancellationException|Timed out waiting',
    'ASSERTION': r'AssertionError|AssertionFailedError',
}


def need(condition):
    if not condition:
        raise ValueError('Invalid closed product diagnostic')


def known_tasks(root):
    policy = json.loads((root / 'gradle/platform-test-policy.json').read_bytes())
    return {task for model in policy['model'].values() for task in model['tests']}


def source_methods(root):
    methods = set()
    for container in ('library', 'samples'):
        for path in sorted((root / container).glob('*/src/*Test/kotlin/**/*.kt')):
            need(not path.is_symlink() and path.stat().st_size <= MAX_XML)
            text = path.read_text()
            package = re.search(r'^package ([a-zA-Z0-9_.]+)', text, re.M)
            if not package:
                continue
            classes = re.findall(r'\bclass\s+([A-Za-z_][A-Za-z_0-9]*)', text)
            functions = re.findall(r'\bfun\s+([A-Za-z_][A-Za-z_0-9]*)\s*\(', text)
            for cls in classes:
                for function in functions:
                    methods.add((package[1] + '.' + cls, function))
    return methods


def source_locations(root):
    files = {}
    for container in ('library', 'samples'):
        for path in sorted((root / container).glob('*/src/*/kotlin/**/*.kt')):
            need(not path.is_symlink() and path.stat().st_size <= MAX_XML)
            files.setdefault(path.name, []).append((path.relative_to(root).as_posix(), len(path.read_text().splitlines())))
    # A bare filename in a stack trace cannot disambiguate duplicate source names.
    return {name: rows[0] for name, rows in files.items() if len(rows) == 1}


def failure_locations(case, locations):
    raw = '\n'.join(''.join(node.itertext()) for node in case if node.tag in ('failure', 'error'))
    sites = []
    for name, line in re.findall(r'\b([A-Za-z_][A-Za-z_0-9]*\.kt):([0-9]{1,7})(?::[0-9]+)?', raw):
        known = locations.get(name)
        if known and 0 < int(line) <= known[1] and (known[0], int(line)) not in sites:
            sites.append((known[0], int(line)))
    return {'sourceLocations': [list(site) for site in sites[:16]],
            'markers': sorted(label for label, pattern in FAILURE_MARKERS.items() if re.search(pattern, raw))}


def source_method_identity(case, task, methods):
    """Resolve Gradle's exact Native task prefix, never an arbitrary class alias."""
    name = (case.get('name') or '').split('[')[0].split('(')[0]
    cls = case.get('classname') or ''
    identity = (cls, name)
    if identity in methods:
        return identity
    # KGP's real Native XML uses e.g. iosX64Test.package.Class, whereas
    # checked-in declarations have only package.Class. Bind the one removable
    # prefix to this XML's own task directory and still require source membership.
    prefix = task + '.'
    if task in ('iosX64Test', 'iosSimulatorArm64Test') and cls.startswith(prefix):
        identity = (cls[len(prefix):], name)
        if identity in methods:
            return identity
    return None


def log_observation(raw):
    need(type(raw) is bytes and len(raw) <= MAX_LOG)
    text = raw.decode(errors='replace')
    markers = [label for label, pattern in MARKERS.items() if re.search(pattern, text, re.I)]
    domains = []
    for domain in DOMAINS:
        codes = set(int(value) for value in re.findall(re.escape(domain) + r'[^\n]{0,40}?\b[Cc]ode[=: ]+(-?[0-9]{1,6})', text))
        domains.extend({'domain': domain, 'code': code} for code in sorted(codes))
    statuses = [{'status': int(status), 'terminal': terminal == 'YES', 'elapsedSeconds': int(minutes) * 60 + int(seconds)}
                for status, terminal, minutes, seconds in re.findall(
                    r'Status=([0-9]{1,3}), isTerminal=(YES|NO), Elapsed=([0-9]{1,4}):([0-5][0-9])', text)]
    return {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw), 'markers': sorted(markers),
            'domains': domains, 'bootStatusCount': len(statuses), 'lastBootStatuses': statuses[-8:]}


def native_observation(root, report):
    tasks = known_tasks(root)
    methods = source_methods(root)
    locations = source_locations(root)
    observed = {}
    for name, row in (report or {}).get('tests', {}).items():
        need(name in tasks and type(row) is dict)
        need(row.get('outcome') in OUTCOMES)
        observed[name] = {key: row[key] for key in ('outcome', 'enabled', 'inGraph', 'passed', 'failed', 'skipped')}
    failures, unmapped, files = set(), 0, 0
    details = []
    counts = dict(passed=0, failed=0, errors=0, skipped=0)
    # Files are fresh in the admitted context; these are attempted observations,
    # not admission. The unchanged assessor and per-invocation XML checks follow.
    for container in ('library', 'samples'):
        for path in sorted((root / container).glob('*/build/test-results/ios*Test/**/TEST-*.xml')):
            need(not path.is_symlink() and path.stat().st_size <= MAX_XML)
            files += 1
            need(files <= 4096)
            raw = path.read_bytes()
            need(b'<!DOCTYPE' not in raw.upper() and b'<!ENTITY' not in raw.upper())
            suite = ET.fromstring(raw)
            task = path.relative_to(root / container).parts[3]
            for case in suite.findall('testcase'):
                failure = case.find('failure') is not None or case.find('error') is not None
                label = ('errors' if case.find('error') is not None else 'failed') if failure else (
                    'skipped' if case.find('skipped') is not None else 'passed')
                counts[label] += 1
                if failure:
                    identity = source_method_identity(case, task, methods)
                    if identity is not None:
                        failures.add(identity)
                        need(len(details) < 10000)
                        details.append({'method': list(identity), **failure_locations(case, locations)})
                    else:
                        unmapped += 1
    return {'buildFailed': (report or {}).get('buildFailed'), 'tasks': observed, 'xmlFiles': files,
            'attemptCounts': counts, 'failedMethods': [list(pair) for pair in sorted(failures)],
            'unmappedFailedMethods': unmapped, 'executionAdmitted': False, 'failureDetails': details}


def validate(value, root, purposes):
    need(type(value) is dict and set(value) <= {'logs', 'native', 'simulator'})
    methods, tasks = source_methods(root), known_tasks(root)
    for purpose, streams in value.get('logs', {}).items():
        need(purpose in purposes and type(streams) is dict and set(streams) == {'stdout', 'stderr'})
        for row in streams.values():
            need(type(row) is dict and set(row) == {'sha256', 'bytes', 'markers', 'domains', 'bootStatusCount', 'lastBootStatuses'})
            need(type(row['sha256']) is str and re.fullmatch(r'[a-f0-9]{64}', row['sha256']))
            need(type(row['bytes']) is int and 0 <= row['bytes'] <= MAX_LOG)
            need(type(row['markers']) is list and row['markers'] == sorted(set(row['markers'])) and set(row['markers']) <= MARKERS.keys())
            need(type(row['domains']) is list and len(row['domains']) <= 32)
            for domain in row['domains']:
                need(type(domain) is dict and set(domain) == {'domain', 'code'} and domain['domain'] in DOMAINS and
                     type(domain['code']) is int and -999999 <= domain['code'] <= 999999)
            need(type(row['bootStatusCount']) is int and 0 <= row['bootStatusCount'] <= 1000000)
            need(type(row['lastBootStatuses']) is list and len(row['lastBootStatuses']) <= min(8, row['bootStatusCount']))
            for status in row['lastBootStatuses']:
                need(set(status) == {'status', 'terminal', 'elapsedSeconds'} and type(status['terminal']) is bool and
                     type(status['status']) is int and 0 <= status['status'] <= 999 and
                     type(status['elapsedSeconds']) is int and 0 <= status['elapsedSeconds'] < 600000)
    for label, row in value.get('native', {}).items():
        required = {'buildFailed', 'tasks', 'xmlFiles', 'attemptCounts', 'failedMethods',
                    'unmappedFailedMethods', 'executionAdmitted'}
        need(label in ('scoped-native', 'full-platform') and required <= set(row) <= required | {'failureDetails'})
        need(row['executionAdmitted'] is False and (row['buildFailed'] is None or type(row['buildFailed']) is bool))
        need(set(row['tasks']) <= tasks)
        for item in row['tasks'].values():
            need(set(item) == {'outcome', 'enabled', 'inGraph', 'passed', 'failed', 'skipped'} and
                 item['outcome'] in OUTCOMES and type(item['enabled']) is bool and type(item['inGraph']) is bool)
            need(all(type(item[k]) is int and 0 <= item[k] <= 10000000 for k in ('passed', 'failed', 'skipped')))
        need(type(row['failedMethods']) is list and len(row['failedMethods']) <= 10000 and
             all(type(pair) is list and len(pair) == 2 and tuple(pair) in methods for pair in row['failedMethods']))
        locations = {path: lines for path, lines in source_locations(root).values()}
        need(type(row.get('failureDetails', [])) is list and len(row.get('failureDetails', [])) <= 10000)
        for detail in row.get('failureDetails', []):
            need(type(detail) is dict and set(detail) == {'method', 'sourceLocations', 'markers'} and
                 detail['method'] in row['failedMethods'])
            need(type(detail['sourceLocations']) is list and len(detail['sourceLocations']) <= 16)
            for site in detail['sourceLocations']:
                need(type(site) is list and len(site) == 2 and type(site[0]) is str and site[0] in locations and
                     type(site[1]) is int and 0 < site[1] <= locations[site[0]])
            need(type(detail['markers']) is list and detail['markers'] == sorted(set(detail['markers'])) and
                 set(detail['markers']) <= FAILURE_MARKERS.keys())
        need(set(row['attemptCounts']) == {'passed', 'failed', 'errors', 'skipped'})
        need(all(type(n) is int and 0 <= n <= 10000000 for n in
                 [*row['attemptCounts'].values(), row['xmlFiles'], row['unmappedFailedMethods']]))
    simulator = value.get('simulator', {})
    need(set(simulator) <= {'version', 'architectures', 'states'})
    if 'version' in simulator:
        need(type(simulator['version']) is str and re.fullmatch(r'[0-9]{1,3}(?:\.[0-9]{1,3}){0,3}', simulator['version']))
        need(type(simulator['architectures']) is list and set(simulator['architectures']) <= {'arm64', 'x86_64'})
    for label, state in simulator.get('states', {}).items():
        need(label in purposes and state in STATES)
    return value
