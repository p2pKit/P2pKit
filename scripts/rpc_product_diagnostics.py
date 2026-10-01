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

import rpc_apple_network_diagnostics

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
    'BOOT_FINISHED': r'(?m)^\s*Finished!\s*$|^\s*Boot status is:.*Booted',
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
    'INITIAL_PEER_DISCOVERY_TIMEOUT': r'APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=INITIAL_PEER\b',
    'INITIAL_PEER_SET_DISCOVERY_TIMEOUT': r'APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=INITIAL_PEER_SET\b',
    'PEER_REDISCOVERY_TIMEOUT': r'APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=REDISCOVERY\b',
    'UNEXPECTED_DIAGNOSTIC': r'Unexpected warn/error diagnostics recorded',
    'SETUP_AFTER_STOP': r'P2pKit stopped before the session could be committed',
    'TIMEOUT': r'TimeoutCancellationException|Timed out waiting',
    'ASSERTION': r'AssertionError|AssertionFailedError',
    **{'APPLE_LAN_' + name: r'APPLE_LAN_DISCOVERY_OBSERVED marker=' + name + r'\b' for name in (
        'ADVERTISING_STARTED', 'BROWSE_RESULT_CALLBACK', 'PEER_RECORD_REJECTED', 'PEER_ACCEPTED',
        'BROWSER_READY', 'BROWSER_WAITING', 'BROWSER_FAILED', 'BROWSER_ERROR_PRESENT',
        'BROWSER_CODE_MINUS_65570', 'BROWSER_CODE_MINUS_65563', 'LISTENER_READY', 'LISTENER_FAILED',
        'MISSING_LOCAL_NETWORK_USAGE', 'MISSING_BONJOUR_SERVICE')},
}
# KGP 2.4.10's Native parser drops suppressed message lines after the first
# frame, then KotlinTestFailure prints the flattened JVM frames into XML.
# These test-only constructors preserve the SAME closed labels on that path.
# LlvmDeclarations names non-exported constructors Class.<init>#internal,
# without a signature. KGP retains that suffix in the flattened method name.
FAILURE_FRAME_MARKERS = {
    'INITIAL_PEER_DISCOVERY_TIMEOUT': 'AppleLanInitialPeerTimeout',
    'INITIAL_PEER_SET_DISCOVERY_TIMEOUT': 'AppleLanInitialPeerSetTimeout',
    'PEER_REDISCOVERY_TIMEOUT': 'AppleLanRediscoveryTimeout',
    'APPLE_LAN_BROWSER_READY': 'AppleLanObservedBrowserReady',
    'APPLE_LAN_BROWSER_WAITING': 'AppleLanObservedBrowserWaiting',
    'APPLE_LAN_BROWSER_FAILED': 'AppleLanObservedBrowserFailed',
    'APPLE_LAN_BROWSER_ERROR_PRESENT': 'AppleLanObservedBrowserError',
    'APPLE_LAN_BROWSER_CODE_MINUS_65570': 'AppleLanObservedBrowser65570',
    'APPLE_LAN_BROWSER_CODE_MINUS_65563': 'AppleLanObservedBrowser65563',
    'APPLE_LAN_LISTENER_READY': 'AppleLanObservedListenerReady',
    'APPLE_LAN_LISTENER_FAILED': 'AppleLanObservedListenerFailed',
    'APPLE_LAN_MISSING_LOCAL_NETWORK_USAGE': 'AppleLanObservedMissingUsage',
    'APPLE_LAN_MISSING_BONJOUR_SERVICE': 'AppleLanObservedMissingService',
    'APPLE_LAN_ADVERTISING_STARTED': 'AppleLanObservedAdvertisingStarted',
    'APPLE_LAN_BROWSE_RESULT_CALLBACK': 'AppleLanObservedBrowseResult',
    'APPLE_LAN_PEER_RECORD_REJECTED': 'AppleLanObservedPeerRejected',
    'APPLE_LAN_PEER_ACCEPTED': 'AppleLanObservedPeerAccepted',
}
for label, name in FAILURE_FRAME_MARKERS.items():
    FAILURE_MARKERS[label] += (r'|(?m:^\s*at ' + re.escape('dev.p2pkit.transport.lan.' + name) +
                              r'(?:#<init>|\.<init>(?:#internal)?)\()')
DIAGNOSTIC_TEST_CLASSES = frozenset(('dev.p2pkit.transport.lan.AppleLanDiscoveryFailureTest',))
DIAGNOSTIC_TARGETS = frozenset(('iosX64Test', 'iosSimulatorArm64Test'))
INTEL_PROCESS_ROLES = frozenset((
    'DataMigrator', 'backboardd', 'SpringBoard', 'launchd_sim', 'Simulator', 'CoreSimulatorService',
    'com.apple.CoreSimulator.CoreSimulatorService',
    'simulatord', 'mds', 'mds_stores', 'mdworker_shared', 'PerfPowerServices', 'mDNSResponder',
    'installd', 'mobileassetd', 'runningboardd', 'logd',
))
INTEL_MEMORY_FIELDS = {
    'freePages': 'Pages free', 'activePages': 'Pages active', 'inactivePages': 'Pages inactive',
    'wiredPages': 'Pages wired down', 'speculativePages': 'Pages speculative',
    'purgeablePages': 'Pages purgeable', 'compressedPages': 'Pages stored in compressor',
    'compressorPages': 'Pages occupied by compressor', 'pageouts': 'Pageouts',
    'swapins': 'Swapins', 'swapouts': 'Swapouts',
}


def need(condition):
    if not condition:
        raise ValueError('Invalid closed product diagnostic')


def intel_environment_observation(kind, raw):
    """Read-only OS snapshots, not ownership, permission, peak-resource or test proof."""
    need(kind in ('hardware', 'memory', 'processes', 'host') and type(raw) is bytes and len(raw) <= MAX_XML)
    text = raw.decode(errors='replace')
    result = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    if kind == 'hardware':
        rows = text.splitlines()
        need(len(rows) == 2 and all(re.fullmatch(r'[0-9]{1,18}', row) for row in rows))
        result.update(memoryBytes=int(rows[0]), logicalCpus=int(rows[1]))
    elif kind == 'memory':
        page = re.search(r'page size of ([0-9]{1,6}) bytes', text)
        need(page is not None)
        fields = {}
        for name, label in INTEL_MEMORY_FIELDS.items():
            matches = re.findall(r'(?m)^' + re.escape(label) + r':\s+([0-9]{1,18})\.\s*$', text)
            need(len(matches) <= 1)
            if matches:
                fields[name] = int(matches[0])
        need({'freePages', 'activePages', 'inactivePages', 'wiredPages'} <= set(fields))
        result.update(pageSizeBytes=int(page[1]), fields=fields)
    elif kind == 'host':
        need(len(raw) <= 4096)
        def unique(pairs):
            value = {}
            for key, field in pairs:
                need(key not in value)
                value[key] = field
            return value
        value = json.loads(text, object_pairs_hook=unique)
        need(type(value) is dict and set(value) == {'loadMilli', 'psSetuid', 'psSetgid', 'psOwnedByRoot', 'unprivileged'})
        result.update(value)
    else:
        roles, observed = {}, 0
        for line in text.splitlines():
            row = re.fullmatch(r'\s*([0-9]{1,6})(?:\.([0-9]{1,3}))?\s+([0-9]{1,18})\s+(\S{1,8})\s+(.+)', line)
            need(row is not None)
            observed += 1
            need(observed <= 100000)
            role = row[5].rsplit('/', 1)[-1]
            if role not in INTEL_PROCESS_ROLES:
                continue
            item = roles.setdefault(role, {'count': 0, 'cpuMilliPercent': 0, 'residentKiB': 0,
                                          'running': 0, 'uninterruptible': 0, 'other': 0})
            item['count'] += 1
            item['cpuMilliPercent'] += int(row[1]) * 1000 + int((row[2] or '').ljust(3, '0'))
            item['residentKiB'] += int(row[3])
            item['running' if row[4].startswith('R') else 'uninterruptible' if row[4].startswith('U') else 'other'] += 1
        need(observed > 0)
        result.update(observedProcesses=observed, roles=roles)
    validate_intel_environment(kind, result)
    return result


def validate_intel_environment(kind, value):
    need(type(value) is dict and type(value.get('sha256')) is str and re.fullmatch(r'[a-f0-9]{64}', value['sha256']))
    need(type(value.get('bytes')) is int and 0 <= value['bytes'] <= MAX_XML)
    common = {'sha256', 'bytes'}
    if kind == 'hardware':
        need(set(value) == common | {'memoryBytes', 'logicalCpus'} and
             type(value['memoryBytes']) is int and 0 < value['memoryBytes'] < 2 ** 60 and
             type(value['logicalCpus']) is int and 0 < value['logicalCpus'] <= 65536)
    elif kind == 'memory':
        need(set(value) == common | {'pageSizeBytes', 'fields'} and
             type(value['pageSizeBytes']) is int and value['pageSizeBytes'] in (4096, 16384) and
             type(value['fields']) is dict and set(value['fields']) <= INTEL_MEMORY_FIELDS.keys() and
             {'freePages', 'activePages', 'inactivePages', 'wiredPages'} <= set(value['fields']))
        need(all(type(n) is int and 0 <= n < 2 ** 60 for n in value['fields'].values()))
    elif kind == 'host':
        need(set(value) == common | {'loadMilli', 'psSetuid', 'psSetgid', 'psOwnedByRoot', 'unprivileged'} and
             type(value['loadMilli']) is list and len(value['loadMilli']) == 3 and
             all(type(n) is int and 0 <= n <= 100000000 for n in value['loadMilli']) and
             all(type(value[k]) is bool for k in ('psSetuid', 'psSetgid', 'psOwnedByRoot', 'unprivileged')) and
             value['unprivileged'] is True)
    else:
        need(kind == 'processes' and set(value) == common | {'observedProcesses', 'roles'} and
             type(value['observedProcesses']) is int and 0 < value['observedProcesses'] <= 100000 and
             type(value['roles']) is dict and set(value['roles']) <= INTEL_PROCESS_ROLES)
        for row in value['roles'].values():
            need(type(row) is dict and set(row) == {'count', 'cpuMilliPercent', 'residentKiB', 'running', 'uninterruptible', 'other'})
            need(all(type(n) is int and 0 <= n < 2 ** 60 for n in row.values()) and
                 0 < row['count'] <= value['observedProcesses'] and
                 row['running'] + row['uninterruptible'] + row['other'] == row['count'])
        need(sum(row['count'] for row in value['roles'].values()) <= value['observedProcesses'])


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


def native_observation(root, report, family='native'):
    """Attempted XML, separated by runtime family; never execution admission."""
    need(family in ('native', 'androidHost'))
    tasks = known_tasks(root)
    methods = source_methods(root)
    locations = source_locations(root)
    observed = {}
    for name, row in (report or {}).get('tests', {}).items():
        need(name in tasks and type(row) is dict)
        need(row.get('outcome') in OUTCOMES)
        observed[name] = {key: row[key] for key in ('outcome', 'enabled', 'inGraph', 'passed', 'failed', 'skipped')}
    failures, unmapped, files = set(), 0, 0
    details, diagnostic_cases = [], []
    counts = dict(passed=0, failed=0, errors=0, skipped=0)
    # Files are fresh in the admitted context; these are attempted observations,
    # not admission. The unchanged assessor and per-invocation XML checks follow.
    pattern = 'ios*Test' if family == 'native' else 'testAndroidHostTest'
    for container in ('library', 'samples'):
        for path in sorted((root / container).glob('*/build/test-results/' + pattern + '/**/TEST-*.xml')):
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
                identity = source_method_identity(case, task, methods)
                if identity is not None and identity[0] in DIAGNOSTIC_TEST_CLASSES:
                    need(task in DIAGNOSTIC_TARGETS and len(diagnostic_cases) < 128)
                    diagnostic_cases.append({'method': list(identity), 'target': task, 'outcome': label})
                if failure:
                    if identity is not None:
                        failures.add(identity)
                        need(len(details) < 10000)
                        details.append({'method': list(identity), **failure_locations(case, locations)})
                    else:
                        unmapped += 1
    return {'buildFailed': (report or {}).get('buildFailed'), 'tasks': observed, 'xmlFiles': files,
            'attemptCounts': counts, 'failedMethods': [list(pair) for pair in sorted(failures)],
            'unmappedFailedMethods': unmapped, 'executionAdmitted': False, 'failureDetails': details,
            'diagnosticCases': diagnostic_cases}


def validate(value, root, purposes):
    need(type(value) is dict and set(value) <= {'logs', 'native', 'androidHost', 'simulator', 'intelEnvironment', 'appleNetwork', 'appleNetworkBaseline',
                                             'appleNetworkCompiler'})
    rpc_apple_network_diagnostics.validate(value.get('appleNetwork', {}))
    baseline = rpc_apple_network_diagnostics.validate(value.get('appleNetworkBaseline', {}))
    need(set(baseline) <= {c + '-' + m for c in rpc_apple_network_diagnostics.CONTEXTS
                          for m in rpc_apple_network_diagnostics.BASELINE_MODES})
    compiler = value.get('appleNetworkCompiler', {})
    need(type(compiler) is dict and set(compiler) <= set(rpc_apple_network_diagnostics.COMPILER_CONTEXTS))
    for row in compiler.values():
        rpc_apple_network_diagnostics.validate_compiler(row, root / 'scripts/diagnostics/apple-bonjour-probe.c')
    environment = value.get('intelEnvironment', {})
    need(type(environment) is dict and set(environment) <= {'before', 'after'})
    for observation in environment.values():
        # A failed snapshot must not erase already finalized earlier snapshots.
        # Partial diagnostic data never establishes a phase/ownership verdict.
        need(type(observation) is dict and set(observation) <= {'hardware', 'memory', 'processes', 'host'})
        for kind, row in observation.items():
            validate_intel_environment(kind, row)
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
    observations = []
    for family in ('native', 'androidHost'):
        need(type(value.get(family, {})) is dict)
        for label, row in value.get(family, {}).items():
            need(label in (('scoped-native', 'full-platform') if family == 'native' else
                           ('intel-host-tests', 'full-platform')))
            observations.append(row)
    for row in observations:
        required = {'buildFailed', 'tasks', 'xmlFiles', 'attemptCounts', 'failedMethods',
                    'unmappedFailedMethods', 'executionAdmitted'}
        need(required <= set(row) <= required |
             {'failureDetails', 'diagnosticCases'})
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
        cases = row.get('diagnosticCases', [])
        need(type(cases) is list and len(cases) <= 128)
        seen = set()
        for case in cases:
            need(type(case) is dict and set(case) == {'method', 'target', 'outcome'} and
                 type(case['method']) is list and len(case['method']) == 2 and
                 all(type(item) is str for item in case['method']) and
                 case['method'][0] in DIAGNOSTIC_TEST_CLASSES and tuple(case['method']) in methods and
                 type(case['target']) is str and case['target'] in DIAGNOSTIC_TARGETS and
                 type(case['outcome']) is str and case['outcome'] in row['attemptCounts'])
            identity = (case['target'], *case['method'])
            need(identity not in seen)
            seen.add(identity)
        need(all(sum(case['outcome'] == outcome for case in cases) <= row['attemptCounts'][outcome]
                 for outcome in ('passed', 'failed', 'errors', 'skipped')))
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
