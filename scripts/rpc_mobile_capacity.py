"""Private USB test-control protocol. Never a transport, permission grant or capacity verdict."""
from __future__ import annotations

import ipaddress
import re

SCOPE = 'mobile-usb-capacity'
AUTHORIZATION = 'usb-provisioned-physical-phone-no-data-tunnel'
BINDINGS = {'schema', 'scope', 'runLabel', 'runNonce', 'hostPlatform', 'hostSourceSha', 'hostArtifactSha256'}
BINDINGS_V2 = BINDINGS | {'clientCount'}
ENVIRONMENT_FIELDS = {'batteryPercentMilli', 'batteryCurrentMicroamps', 'batteryTemperatureMilliC',
                      'batteryState', 'batterySource', 'thermalState', 'thermalSource'}
NUMBERS = ('sequence', 'uptimeMillis', 'cpuNanos', 'residentBytes', 'nativeThreads', 'connected', 'accepted',
           'completed', 'refused', 'duplicates', 'droppedNotifications', 'protocolFailures', 'connectionFailures',
           'running', 'queued', 'records', 'payloadBytes')
COUNTERS = ('accepted', 'completed', 'refused', 'duplicates', 'droppedNotifications', 'protocolFailures', 'connectionFailures')
FILES = frozenset(('inbox.txt', 'stop.txt', 'ready.txt', 'telemetry.txt', 'closed.txt', 'failed.txt'))
RESOURCE_KINDS = {
    'Android': dict(cpuSource='android-process-elapsed-cpu', cpuResolutionNanos='1000000',
                    residentSource='proc-self-status', threadSource='proc-self-status'),
    'Ios': dict(cpuSource='getrusage-self', cpuResolutionNanos='1000', residentSource='mach-task-basic-info',
                threadSource='mach-task-threads-retired-rights'),
}
ARTIFACT_KINDS = {'Android': 'android-installed-base-apk', 'Ios': 'ios-installed-executable'}
RECORD_LIMIT = 16_384


def need(value, message='Invalid private mobile control record; no qualification'):
    if not value:
        raise ValueError(message)


def parse(raw):
    need(type(raw) is bytes and 0 < len(raw) <= RECORD_LIMIT and
         all(n == 10 or 32 <= n <= 126 for n in raw))
    result = {}
    for line in raw.decode('ascii').splitlines():
        if not line:
            continue
        key, separator, value = line.partition('=')
        need(separator and re.fullmatch('[A-Za-z][A-Za-z0-9]{0,63}', key) and value and key not in result)
        result[key] = value
    need(result)
    return result


def encode(value):
    need(type(value) is dict and all(type(k) is str and type(v) is str for k, v in value.items()))
    raw = ''.join(k + '=' + v + '\n' for k, v in value.items()).encode('ascii')
    need(parse(raw) == value)
    return raw


def binding(value):
    fields = binding_fields(value)
    need(set(value) == fields and all(type(v) is str for v in value.values()))
    need(value['scope'] == SCOPE and value['hostPlatform'] in RESOURCE_KINDS)
    if value['schema'] == '2':
        need(value['clientCount'] in ('128', '256'), 'Only explicit 128/256 mobile profiles are supported')
    for field, pattern in (('runLabel', '[a-z0-9-]{1,64}'), ('runNonce', '[a-f0-9]{64}'),
                           ('hostSourceSha', '[a-f0-9]{40}'), ('hostArtifactSha256', '[a-f0-9]{64}')):
        need(re.fullmatch(pattern, value[field]))
    return dict(value)


def binding_fields(value):
    need(type(value) is dict and value.get('schema') in ('1', '2'), 'Unknown mobile schema')
    return BINDINGS if value['schema'] == '1' else BINDINGS_V2


def client_count(bound):
    checked = binding(bound)
    return 128 if checked['schema'] == '1' else int(checked['clientCount'])


def environment(row, platform):
    """Public sensor observations, not battery-drain estimates or exact processor temperatures."""
    need(set(row) == ENVIRONMENT_FIELDS and all(type(value) is str for value in row.values()))
    ranges = {'batteryPercentMilli': (0, 100000), 'batteryCurrentMicroamps': (-20000000, 20000000),
              'batteryTemperatureMilliC': (-40000, 100000)}
    result = dict(row)
    for name, (low, high) in ranges.items():
        if row[name] != 'unavailable':
            need(re.fullmatch(r'0|-?[1-9][0-9]{0,8}', row[name]) and low <= int(row[name]) <= high)
            result[name] = int(row[name])
    need(row['batteryState'] in ('unavailable', 'unknown', 'unplugged', 'charging', 'full') and
         row['thermalState'] in ('unavailable', 'nominal', 'fair', 'serious', 'critical'))
    battery_source = {'Android': 'android-battery-manager', 'Ios': 'ios-uidevice'}[platform]
    thermal_source = {'Android': 'android-power-manager', 'Ios': 'ios-process-info'}[platform]
    need(row['batterySource'] in ('unavailable', battery_source) and
         row['thermalSource'] in ('unavailable', thermal_source))
    if row['batterySource'] == 'unavailable':
        need(all(row[name] == 'unavailable' for name in set(ranges) | {'batteryState'}))
    need((row['thermalSource'] == 'unavailable') == (row['thermalState'] == 'unavailable'))
    if platform == 'Ios':
        need(row['batteryCurrentMicroamps'] == row['batteryTemperatureMilliC'] == 'unavailable',
             'iOS public APIs do not supply current or an exact temperature')
    return result


def inbox(raw, bound):
    checked = binding(bound)
    fields = binding_fields(checked)
    row = parse(raw)
    need(set(row) == fields | {'hostAddress', 'hostPort', 'hostInterface', 'subnets', 'clientPins'} and
         {key: row[key] for key in fields} == checked, 'Exact source, artifact, run and capacity binding required')
    need(re.fullmatch('[A-Za-z0-9_.:-]{1,32}', row['hostInterface']) and
         re.fullmatch('[1-9][0-9]{3,4}', row['hostPort']) and 1024 <= int(row['hostPort']) <= 65535)
    address = ipaddress.IPv4Address(row['hostAddress'])
    private = [ipaddress.IPv4Network(network) for network in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')]
    subnets = row['subnets'].split(',')
    need(1 <= len(subnets) <= 16 and len(set(subnets)) == len(subnets))
    networks = [ipaddress.IPv4Network(network, strict=True) for network in subnets]
    need(all(any(network.subnet_of(allowed) for allowed in private) for network in networks) and
         any(address in network for network in networks), 'Explicit private LAN required; no path admission bypass')
    pins = row['clientPins'].split(',')
    need(len(pins) == len(set(pins)) == client_count(checked) and
         all(re.fullmatch('p2f1-[a-z2-7]{52}', pin) for pin in pins),
         'Exactly the selected profile\'s distinct public synthetic pins are required')
    return row


class Protocol:
    def __init__(self, bound, address, port):
        self.binding = binding(bound)
        self.binding_fields = binding_fields(bound)
        self.client_count = client_count(bound)
        self.address, self.port = address, str(port)
        self.resources = RESOURCE_KINDS[bound['hostPlatform']] | dict(clock='host-run-monotonic')
        self.previous = None

    def require_binding(self, row, extra):
        need(type(row) is dict and set(row) == self.binding_fields | set(extra) and
             all(type(v) is str for v in row.values()) and {k: row[k] for k in self.binding_fields} == self.binding)

    def ready(self, row):
        self.require_binding(row, ('fingerprint', 'address', 'port', 'compiledSourceMatched', 'artifactKind'))
        need(row['address'] == self.address and row['port'] == self.port and row['compiledSourceMatched'] == 'true' and
             row['artifactKind'] == ARTIFACT_KINDS[self.binding['hostPlatform']] and
             re.fullmatch('p2f1-[a-z2-7]{52}', row['fingerprint']))
        # The actual Kotlin peer parser and authenticated handshake still validate this complete pin.
        return row

    def telemetry(self, row):
        optional = ENVIRONMENT_FIELDS if self.binding['schema'] == '2' else set()
        self.require_binding(row, set(self.resources) | set(NUMBERS) | optional)
        need({k: row[k] for k in self.resources} == self.resources)
        need(all(type(row[k]) is str and re.fullmatch('0|[1-9][0-9]{0,18}', row[k]) for k in NUMBERS))
        values = {k: int(row[k]) for k in NUMBERS}
        need(all(0 <= n < 2 ** 63 for n in values.values()))
        need(0 <= values['sequence'] < 3000 and values['residentBytes'] > 0 and values['nativeThreads'] > 0 and
             values['connected'] <= self.client_count and values['running'] <= self.client_count and
             values['queued'] <= self.client_count * 2 and values['records'] <= self.client_count * 1024 and
             values['payloadBytes'] <= self.client_count * 512 * 1024 and
             values['cpuNanos'] % int(self.resources['cpuResolutionNanos']) == 0)
        if optional:
            values.update(environment({key: row[key] for key in optional}, self.binding['hostPlatform']))
        if self.previous is not None:
            before = self.previous
            if values == before:
                return None  # Same immutable slot, not a new host sample or a refreshed freshness clock.
            need(values['sequence'] > before['sequence'] and values['uptimeMillis'] > before['uptimeMillis'] and
                 values['cpuNanos'] >= before['cpuNanos'] and all(values[k] >= before[k] for k in COUNTERS))
        self.previous = values
        return dict(values)

    def stop(self):
        return self.binding | dict(action='stop')

    def closed(self, row):
        self.require_binding(row, ('runtimeClosed', 'clientPinsRemoved', 'controlHealthy'))
        need(all(row[k] == 'true' for k in ('runtimeClosed', 'clientPinsRemoved', 'controlHealthy')),
             'Mobile close was failed, interrupted or unproven')


def retention(before, after):
    for row in (before, after):
        need(type(row) is dict and set(row) in (set(NUMBERS), set(NUMBERS) | ENVIRONMENT_FIELDS) and
             all(type(row[key]) is int and 0 <= row[key] < 2 ** 63 for key in NUMBERS))
        need(row['residentBytes'] > 0 and row['nativeThreads'] > 0)
        if ENVIRONMENT_FIELDS <= set(row):
            values = {key: row[key] for key in ENVIRONMENT_FIELDS}
            need(all(type(value) in (str, int) for value in values.values()))
            platform = 'Ios' if any(value in ('ios-uidevice', 'ios-process-info') for value in values.values()) else 'Android'
            need(environment({key: str(value) for key, value in values.items()}, platform) == values)
    need(set(before) == set(after), 'Retention samples must use the same telemetry schema')
    need(after['sequence'] > before['sequence'] and after['uptimeMillis'] - before['uptimeMillis'] >= 65000 and
         after['cpuNanos'] >= before['cpuNanos'])
    need(all(before[k] == 0 for k in ('connected', 'running', 'queued')) and
         all(after[k] == 0 for k in ('connected', 'running', 'queued', 'records', 'payloadBytes')) and
         all(before[k] == after[k] for k in COUNTERS))
    return dict(status='PASS', scope='PHONE_IDLE_RETENTION_NOT_RSS_RESET_OR_PROCESS_EXIT', before=before, after=after,
                observedHostMillis=after['uptimeMillis'] - before['uptimeMillis'])


def android_usb_inventory(raw, selected):
    """An explicit wired device on our private ADB server, never emulator/tcpip/wireless auto-selection."""
    need(android_usb_state(raw, selected) == 'device',
         'Selected Android USB device is missing, unauthorized, wireless or ambiguous')


def android_usb_state(raw, selected):
    """Waiting observations do not admit a device or start the RPC readiness clock."""
    need(type(raw) is str and len(raw) <= 65536 and re.fullmatch('[A-Za-z0-9_-]{1,128}', selected) and
         not selected.startswith('emulator-'))
    rows = [line.split() for line in raw.splitlines() if line and not line.startswith('List of devices attached')]
    matches = [row for row in rows if row[0] == selected]
    if not matches:
        return 'missing'
    need(len(matches) == 1 and len(matches[0]) >= 3 and matches[0][1] in ('device', 'offline', 'unauthorized') and
         len([f for f in matches[0][2:] if re.fullmatch('usb:[A-Za-z0-9_.-]+', f)]) == 1,
         'Selected Android USB device is missing, unauthorized, wireless or ambiguous')
    return matches[0][1]


def ios_usb_details(value, selected):
    """Fail closed if Xcode's actual selected-device details do not prove paired wired iOS."""
    need(type(value) is dict and type(value.get('result')) is dict)
    result = value['result']
    # `devicectl list devices --json-output` is the documented inventory shape.
    # Do not infer the control transport from a tunnel address or hostname.
    need(type(result.get('devices')) is list and 0 < len(result['devices']) <= 256 and
         all(type(row) is dict and type(row.get('identifier')) is str for row in result['devices']))
    candidates = [row for row in result['devices'] if row['identifier'] == selected]
    need(len(candidates) == 1)
    device = candidates[0]
    need(type(device) is dict and device.get('identifier') == selected and
         type(device.get('connectionProperties')) is dict and type(device.get('hardwareProperties')) is dict)
    connection, hardware = device['connectionProperties'], device['hardwareProperties']
    need(connection.get('transportType') == 'wired' and connection.get('pairingState') == 'paired' and
         hardware.get('platform') == 'iOS', 'Selected iPhone must be explicitly paired and wired; unknown schema is not admission')


def parse_vm_stat(raw, total_bytes):
    """Conservative *generator* available-page estimate, not a phone RSS or physical-memory guarantee."""
    need(type(raw) is str and len(raw) <= 65536 and type(total_bytes) is int and total_bytes > 0)
    sizes = re.findall(r'page size of ([0-9]+) bytes', raw)
    need(len(sizes) == 1 and int(sizes[0]) in (4096, 16384))
    values = {}
    for line in raw.splitlines():
        match = re.fullmatch(r'(Pages free|Pages inactive|Pages speculative):\s+([0-9]+)\.', line)
        if match:
            need(match[1] not in values)
            values[match[1]] = int(match[2])
    need(len(values) == 3)
    available = sum(values.values()) * int(sizes[0])
    need(0 <= available <= total_bytes)
    return available
