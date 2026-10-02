"""Bounded source-built CLI controls on the admitted Mac, not a physical/headful campaign.

Only synthetic loopback peers, private profiles and kernel-identity-scoped faults.
No SDK hooks, security overrides, network/system settings or PID/name-based kills.
The enclosing original native executor owns finalization even after a failure.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCOPE = 'SOURCE_BUILT_MAC_CLI_PROCESS_CONTROLS_NOT_FULL_PS_T05_PS_T06_OR_RPC_CAPACITY'
MAIN = 'dev.p2pkit.sample.desktop.MainKt'
CLASSES = ('CliOptionsTest', 'CliLineReaderTest', 'CliShutdownTest')
MAX_LOG = 8 * 1024**2
FIXTURE_BYTES = 49 * 1024**2
FAULTS = ('term', 'kill', 'eof', 'stop-cont', 'hup')


def need(value, message='CLI process control failed'):
    if not value:
        raise RuntimeError(message)


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def private_write(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()
    need(len(raw) <= 4 * 1024**2, 'Bounded private JSON required')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


def runtime_manifest(source):
    directory = ROOT / 'samples/p2p-sample-desktop/build/install/p2p-sample-desktop/lib'
    need(re.fullmatch('[a-f0-9]{40}', source), 'Full source SHA required')
    need(all(not p.is_symlink() for p in (directory, *directory.parents)), 'No linked runtime ancestry')
    jars = sorted(directory.iterdir())
    need(1 <= len(jars) <= 64 and all(p.suffix == '.jar' and p.is_file() and not p.is_symlink() for p in jars),
         'Exact newly produced CLI installDist runtime required')
    need(sum(p.stat().st_size for p in jars) <= 256 * 1024**2, 'CLI runtime exceeds byte budget')
    return dict(schema=1, scope=SCOPE, source=source, jars=[
        dict(path=str(p.relative_to(ROOT)), bytes=p.stat().st_size, sha256=digest(p)) for p in jars])


def focused_tests():
    source = ROOT / 'samples/p2p-sample-desktop/src/test/kotlin/dev/p2pkit/sample/desktop'
    reports = ROOT / 'samples/p2p-sample-desktop/build/test-results/test'
    expected = {name: set(re.findall(r'@Test\s+fun (\w+)\(', (source / (name + '.kt')).read_text())) for name in CLASSES}
    paths = sorted(reports.glob('TEST-*.xml'))
    need({p.name for p in paths} == {'TEST-dev.p2pkit.sample.desktop.' + name + '.xml' for name in CLASSES},
         'Focused JVM test inventory differs')
    actual = {}
    for path in paths:
        need(path.is_file() and not path.is_symlink() and path.stat().st_size <= 4 * 1024**2, 'Bounded JVM XML required')
        tree = ET.fromstring(path.read_bytes())
        name = tree.attrib['name'].split('.')[-1]
        cases = tree.findall('testcase')
        need(tree.tag == 'testsuite' and all(tree.attrib.get(key) == '0' for key in ('failures', 'errors', 'skipped')),
             'Focused JVM suite did not pass')
        need(cases and all(not list(case) for case in cases), 'Failed/skipped focused JVM method')
        names = [case.attrib['name'].removesuffix('()') for case in cases]
        need(len(names) == len(set(names)) and set(names) == expected[name], 'Missing/duplicate JVM method')
        actual[name] = dict(passed=len(cases), reportSha256=digest(path), sourceSha256=digest(source / (name + '.kt')))
    return actual


def launch_cases():
    rows = [(['--help'], False), (['-h'], False), (['--unknown'], True), (['future=value'], True)]
    rows += [(['reconnect=' + value], True) for value in ('', 'bad', '0,1', '-1,1', '1,-1', '1,2,3', '2147483648,1')]
    rows += [([option, option], True) for option in ('reconnect=5,1000', 'trace=off', 'test=PS-T05',
        'session=case', 'role=both', 'evidence=/NOT_USED', 'log=/NOT_USED')]
    rows += [([option], True) for option in ('trace=', 'test=', 'session=', 'role=', 'evidence=', 'log=',
        'trace=invalid', 'test=x', 'session=unsafe session', 'role=invalid')]
    rows.append((['x' * 65537], True))
    return rows


def case_inventory():
    return ['option-' + str(n) for n in range(len(launch_cases()))] + ['command-contract', 'multi-peer-contract'] + [
        'admission-pressure-' + str(n) for n in range(3)] + [
        'transfer-storage-' + str(n) for n in range(3)] + [
        f'{phase}-{fault}-{repeat}' for repeat in range(3)
        for phase, fault in [(phase, fault) for phase in ('handshake', 'idle', 'transfer') for fault in FAULTS] + [('transfer', 'sender-kill')]]


def assess_result(value, source):
    need(type(value) is dict and type(value.get('schema')) is int and value.get('schema') == 1 and value.get('scope') == SCOPE and
         value.get('sourceSha') == source and value.get('result') == 'PASS' and
         value.get('fullCampaignQualified') is False and value.get('physicalNetworkTested') is False and
         value.get('headfulTested') is False and type(value.get('liveChildCount')) is int and
         value.get('liveChildCount') == 0, 'Invalid/overbroad CLI result')
    need([r['case'] for r in value['cases']] == case_inventory() and all(r.get('passed') is True for r in value['cases']),
         'Incomplete CLI process control inventory')
    return value


def inspect_export(path, source, session):
    """Bound and verify ZIP members without extraction; no invented environment sidecar."""
    need(path.is_file() and not path.is_symlink() and path.stat().st_size <= MAX_LOG, 'Bounded CLI export required')
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        names = [row.filename for row in members]
        need(len(names) == len(set(names)) <= 64 and
             all(re.fullmatch('[A-Za-z0-9._-]{1,96}', name) and name not in ('.', '..') for name in names) and
             all(not row.is_dir() and not stat.S_ISLNK(row.external_attr >> 16) for row in members) and
             sum(row.file_size for row in members) <= 16 * 1024**2, 'CLI export member bound')
        required = {'events.jsonl', 'events.txt', 'summary.json', 'manual-evidence-required.txt', 'checksums.sha256'}
        need(required <= set(names), 'Incomplete diagnostic export')
        raw = {name: archive.read(name) for name in names}
    checksums = raw['checksums.sha256'].decode('ascii').splitlines()
    expected = sorted(hashlib.sha256(data).hexdigest() + '  ' + name for name, data in raw.items()
                      if name != 'checksums.sha256')
    need(sorted(checksums) == expected, 'CLI export checksum mismatch')
    summary = json.loads(raw['summary.json'])
    events = [json.loads(line) for line in raw['events.jsonl'].splitlines()]
    need(summary['gitCommitSha'] == source and summary['testSessionId'] == session and
         summary['platform'] == 'jvm-cli' and summary['protocolVersion'] == 'secure-v2', 'CLI binary/export source mismatch')
    # The existing exporter samples summary then events while workers may log;
    # validate source/session membership, not an invented atomic-count contract.
    need(events and
         all(e['gitCommitSha'] == source and e['testSessionId'] == session and e['platform'] == 'jvm-cli' for e in events),
         'Crossed or missing diagnostic events')
    indices = [e['index'] for e in events]
    need(indices == sorted(set(indices)), 'Reordered/duplicate diagnostic events')
    return dict(file=path.name, bytes=path.stat().st_size, sha256=digest(path), summary=summary,
                decodedEventCount=len(events), eventNames=sorted({e['eventName'] for e in events}),
                terminalTransfers=[dict(event=e['eventName'], connectionId=e.get('connectionId'),
                    transferId=e.get('transferId'), state=e.get('currentState'), outcome=e.get('outcome'))
                    for e in events if e['eventName'] in ('transfer.completed', 'transfer.failed', 'transfer.cancelled',
                                                         'transfer.durable.committed', 'transfer.offer.rejected')])


def direct_child(identity, owner):
    need(identity is not None and identity['live'] is True and identity['parentPid'] == owner['pid'] and
         identity['parentUniqueId'] == owner['uniqueId'] and identity['uid'] == identity['realUid'] == owner['uid'] and
         identity['pid'] != owner['pid'], 'Fault target is not the directly launched ordinary-account lifetime')


def java_argv(manifest, home, temporary):
    classpath = os.pathsep.join(str(ROOT / r['path']) for r in manifest['jars'])
    return [str(Path(os.environ['JAVA_HOME']) / 'bin/java'), '-Xms32m', '-Xmx256m', '-XX:-MaxFDLimit',
            '-Duser.home=' + str(home), '-Djava.io.tmpdir=' + str(temporary), '-cp', classpath, MAIN]


def peer_options(name, app, directory):
    return [name, app, 'reconnect=5,1000', 'trace=frames', 'test=PS-T05', 'session=' + app,
            'role=both', 'evidence=' + str(directory / 'exports'), 'log=' + str(directory / 'events.jsonl')]


class Relay:
    """Opaque loopback byte gate for a reproducible phase; never alters protocol bytes."""
    def __init__(self, port, limit=None):
        need(type(port) is int and 1 <= port <= 65535, 'Only an observed synthetic peer port is supported')
        self.listener = socket.socket()
        self.listener.bind(('127.0.0.1', 0))
        self.listener.listen(1)
        self.listener.setblocking(False)
        self.port, self.target = self.listener.getsockname()[1], port
        self.client = self.server = None
        self.buffers, self.forwarded, self.limit = {}, [0, 0], limit
        self.accepted = self.closed = False

    def pump(self, seconds):
        if self.closed:
            time.sleep(seconds)
            return
        if self.client is None:
            ready, _, _ = select.select([self.listener], [], [], seconds)
            if ready:
                self.client, address = self.listener.accept()
                need(address[0] == '127.0.0.1', 'Loopback-only phase relay')
                self.server = socket.create_connection(('127.0.0.1', self.target), timeout=2)
                self.client.setblocking(False)
                self.server.setblocking(False)
                self.buffers = {self.client: bytearray(), self.server: bytearray()}
                self.accepted = True
            return
        sockets = (self.client, self.server)
        reads = [s for s in sockets if len(self.buffers[sockets[1 - sockets.index(s)]]) < 65536]
        writes = [s for s in sockets if self.buffers[s] and
                  (s is self.client or self.limit is None or self.forwarded[0] < self.limit)]
        ready, writable, _ = select.select(reads, writes, [], seconds)
        try:
            for source in ready:
                destination = sockets[1 - sockets.index(source)]
                data = source.recv(65536 - len(self.buffers[destination]))
                if not data:
                    self.close()
                    return
                self.buffers[destination].extend(data)
            for destination in writable:
                index = 0 if destination is self.server else 1
                count = len(self.buffers[destination])
                if index == 0 and self.limit is not None:
                    count = min(count, max(0, self.limit - self.forwarded[0]))
                if count:
                    need(sum(self.forwarded) + count <= 64 * 1024**2, 'Phase relay byte safety cutoff')
                    count = destination.send(bytes(self.buffers[destination][:count]))
                    del self.buffers[destination][:count]
                    self.forwarded[index] += count
        except (ConnectionResetError, BrokenPipeError):
            self.close()

    def close(self):
        for stream in (self.client, self.server, self.listener):
            if stream is not None:
                stream.close()
        self.closed = True

    def evidence(self):
        return dict(loopbackOnly=True, bytesUnmodified=True, accepted=self.accepted, closed=self.closed,
                    forwardedClientBytes=self.forwarded[0], forwardedServerBytes=self.forwarded[1], holdAfterClientBytes=self.limit)


class Peer:
    def __init__(self, campaign, label, app, *, home=None, name=None, limited=False):
        self.campaign, self.label, self.app = campaign, label, app
        self.directory = campaign.directory / label
        self.directory.mkdir(mode=0o700)
        self.home = self.directory / 'home' if home is None else home
        if home is None:
            self.home.mkdir(mode=0o700)
        need(self.home.is_relative_to(campaign.directory) and not self.home.is_symlink(), 'Private synthetic profile required')
        (self.directory / 'tmp').mkdir(mode=0o700)
        self.path = self.directory / 'terminal.log'
        self.stream = os.fdopen(os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb')
        argv = campaign.java_argv(self.home, self.directory / 'tmp') + peer_options(name or label, app, self.directory)
        if limited:
            argv = [sys.executable, '-B', str(ROOT / 'scripts/rpc_cli_child_limits.py'), '--directory',
                    str(self.directory), '--home', str(self.home), '--app', app, '--name', name or label]
        self.child = subprocess.Popen(argv, cwd=ROOT, env=os.environ, stdin=subprocess.PIPE,
            stdout=self.stream, stderr=subprocess.STDOUT, start_new_session=True, bufsize=0)
        campaign.children.append(self.child)
        os.set_blocking(self.child.stdin.fileno(), False)
        self.events, self.identity, self.token, self.stopped = [], None, None, False
        campaign.peers.append(self)
        self.wait_text('Ready. Type', timeout=30)
        identity = campaign.scope._identity(self.child.pid, required=True)
        direct_child(identity, campaign.owner)
        need(campaign.scope._ours(campaign.scope._inspect_environment(identity)), 'Native ownership domain mismatch')
        self.identity, self.token = identity, campaign.scope._acquire(identity)
        self.command('mesh off', 'auto-mesh off')
        self.command('disc off', 'discovery off')
        self.command('adv off', 'advertising off')
        info = self.command('info', 'manual port')
        self.peer_id = re.findall(r'(?m)^localPeerId\s+(\S+)', info)[-1]
        self.pin = re.findall(r'(?m)^fingerprint\s+(p2f1-[a-z2-7]{52})', info)[-1]
        self.qr = re.findall(r'(?m)^pairing QR\s+(\S+)', info)[-1]
        self.port = int(re.findall(r'(?m)^manual port\s+([0-9]+)', info)[-1])
        self.observe('ready')

    def text(self):
        need(self.path.stat().st_size <= MAX_LOG, 'CLI terminal log exceeds safety bound')
        return self.path.read_text(errors='replace')

    def write(self, text):
        raw, offset, deadline = text.encode(), 0, time.monotonic() + 10
        need(len(raw) <= 256 * 1024, 'Bounded synthetic stdin required')
        while offset < len(raw):
            need(time.monotonic() < deadline and self.child.poll() is None, 'CLI stdin deadline/early exit')
            try:
                offset += os.write(self.child.stdin.fileno(), raw[offset:])
            except BlockingIOError:
                self.campaign.pump(.01)

    def wait_text(self, expected, *, offset=0, timeout=20):
        deadline = time.monotonic() + timeout
        while True:
            value = self.text()[offset:]
            if expected in value:
                return value
            need(self.child.poll() is None and time.monotonic() < deadline, 'Missing CLI output: ' + expected)
            self.campaign.pump(.02)

    def wait_pattern(self, pattern, *, offset=0, timeout=40):
        deadline = time.monotonic() + timeout
        while True:
            value = self.text()[offset:]
            match = re.search(pattern, value, re.MULTILINE)
            if match:
                return match.group(0)
            need(self.child.poll() is None and time.monotonic() < deadline, 'Missing CLI terminal observation: ' + pattern)
            self.campaign.pump(.02)

    def command(self, text, expected, timeout=20):
        offset = len(self.text())
        self.events.append(dict(kind='stdin', command=text if len(text) < 1024 else '<oversized synthetic input>', utc=time.time_ns()))
        self.write(text + '\n')
        return self.wait_text(expected, offset=offset, timeout=timeout)

    def observe(self, label):
        before = self.campaign.scope._observe(self.identity, 'CLI resource observation', lambda row: row)
        row = self.campaign.native.task(self.child.pid)
        bsd = self.campaign.native.bsd(self.child.pid)
        after = self.campaign.scope._observe(self.identity, 'CLI resource observation', lambda row: row)
        need(self.campaign.scope._key(before) == self.campaign.scope._key(after) and row is not None and
             before['pidVersion'] == after['pidVersion'] == self.identity['pidVersion'] and
             bsd is not None and row.resident > 0, 'Unproven child resources')
        value = dict(kind='resource', label=label, utc=time.time_ns(), identity=after,
            residentBytes=row.resident, threads=row.threadCount, fileDescriptors=bsd.nfiles,
            cpuUser=row.totalUser, cpuSystem=row.totalSystem)
        need(row.resident < 1024**3 and row.threadCount < 512 and bsd.nfiles < 2048, 'Child resource safety cutoff')
        self.events.append(value)
        return value

    def snapshot_exports(self, label):
        self.command('diag export', 'evidence exported:')
        directory = self.directory / ('snapshot-' + label)
        directory.mkdir(mode=0o700)
        paths = sorted((self.directory / 'exports').glob('*.zip'))
        need(paths, 'Missing CLI diagnostic export')
        rows = []
        for path in paths:
            review = inspect_export(path, self.campaign.source, self.app)
            # The sample deliberately replaces the same active-session ZIP.
            # Preserve the exact pre-fault bytes before its later final export.
            fd = os.open(directory / path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(path.read_bytes())
            need(digest(directory / path.name) == review['sha256'], 'Export changed while preserving snapshot')
            rows.append(review)
        private_write(directory / 'review.json', dict(sourceSha=self.campaign.source, exports=rows))
        return rows

    def fault(self, name):
        need(name in ('term', 'kill', 'stop', 'cont', 'hup'), 'Closed fault allowlist required')
        current = self.campaign.scope._observe(self.identity, 'CLI fault identity', lambda row: row)
        direct_child(current, self.campaign.owner)
        need(current['pidVersion'] == self.identity['pidVersion'], 'Fault target exec changed; no token reacquisition')
        signum = dict(term=signal.SIGTERM, kill=signal.SIGKILL, stop=signal.SIGSTOP,
                     cont=signal.SIGCONT, hup=signal.SIGHUP)[name]
        self.events.append(dict(kind='fault', signal=name, utc=time.time_ns(), identity=current))
        status = self.campaign.scope.proc.proc_signal_with_audittoken(ctypes.byref(self.token), signum)
        need(status == 0, 'Identity-scoped CLI signal failed; no PID fallback')
        self.stopped = name == 'stop'

    def wait_exit(self, allowed):
        deadline = time.monotonic() + 35
        while self.child.poll() is None:
            need(time.monotonic() < deadline, 'CLI did not exit within original shutdown budget plus observation')
            self.campaign.pump(.02)
        need(self.child.returncode in allowed, 'Unexpected CLI exit status')
        self.child.stdin.close()
        self.stream.close()
        private_write(self.directory / 'process-evidence.json', dict(argv=self.child.args, events=self.events,
            identity=self.identity, exitCode=self.child.returncode, terminalSha256=digest(self.path)))
        exports = sorted((self.directory / 'exports').glob('*.zip'))
        need(exports, 'Missing CLI diagnostic export')
        self.exports = [inspect_export(path, self.campaign.source, self.app) for path in exports]
        private_write(self.directory / 'export-review.json', dict(sourceSha=self.campaign.source, exports=self.exports))

    def quit(self):
        if self.child.poll() is None:
            self.write('quit\n')
        self.wait_exit((0,))
        need(self.text().count('Stopping…') == 1, 'Graceful teardown did not execute exactly once')
        need(any('application.shutdown' in row['eventNames'] for row in self.exports), 'Missing final diagnostic shutdown')


class Campaign:
    def __init__(self, directory, manifest):
        import audit_processes as processes
        files = module('cli_private_files', 'run-rpc-capacity-lab.py')
        self.state, source = files.owned_context()
        need(processes.host_role() == 'macos-arm64' and directory == self.state / 'work/cli-process-controls',
             'Only the admitted Mac-owned work directory is supported')
        need(manifest == runtime_manifest(source), 'Source-built CLI runtime changed')
        self.source, self.manifest, self.directory = source, manifest, directory
        directory.mkdir(mode=0o700)
        self.peers, self.children, self.rows = [], [], []
        self.relay = None
        self.started = time.monotonic()
        self.last_safety_check = self.started
        context = json.loads(files.read_private(self.state / 'context.json'))
        domain = processes.ownership_domains(os.environ[processes.CHAIN_ENV], os.environ[processes.DOMAINS_ENV])[-1]
        self.scope = processes.DarwinScope(context['id'], domain['id'], str(self.state), context['gradleHome'])
        self.owner = self.scope._identity(os.getpid(), required=True)
        self.native = module('cli_readonly_resources', 'rpc_intel_process_diagnostics.py').NativeSnapshot(expected_role='macos-arm64')

    def java_argv(self, home, temporary):
        return java_argv(self.manifest, home, temporary)

    def passed(self, row):
        need(row['case'] == case_inventory()[len(self.rows)] and row['passed'] is True, 'Out-of-order CLI case result')
        private_write(self.directory / ('case-' + row['case'] + '.json'), row)
        self.rows.append(row)
        print('PASS ' + row['case'], file=sys.stderr, flush=True)

    def pump(self, seconds):
        need(time.monotonic() - self.started < 2700, 'Campaign safety deadline; native executor must drain')
        if time.monotonic() - self.last_safety_check >= 5:
            self.last_safety_check = time.monotonic()
            for peer in self.peers:
                if peer.child.poll() is None and peer.identity is not None:
                    try:
                        peer.observe('periodic-five-second-safety')
                    except ProcessLookupError:
                        need(peer.child.poll() is not None, 'Resource observation lost a still-running owned lifetime')
                    peer.text()  # Bound logs, including workers not currently receiving a command.
        if self.relay is None:
            time.sleep(seconds)
        else:
            self.relay.pump(seconds)

    def options(self):
        for index, (options, error) in enumerate(launch_cases()):
            path = self.directory / ('option-' + str(index))
            path.mkdir(mode=0o700)
            with (path / 'output.log').open('xb') as output:
                child = subprocess.Popen(self.java_argv(path / 'unused-home', path) + options, cwd=ROOT,
                    env=os.environ, stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
                self.children.append(child)
                # Do not use subprocess.run(timeout): its raw-PID kill is not our native finalizer.
                deadline = time.monotonic() + 15
                while child.poll() is None:
                    need(time.monotonic() < deadline and output.tell() <= MAX_LOG, 'CLI option deadline/output bound')
                    self.pump(.02)
            raw = (path / 'output.log').read_text()
            need(child.returncode == 0 and 'Usage:' in raw and ('[p2pkit ERROR]' in raw) is error
                 and '[P2pKit CLI]' not in raw and not (path / 'unused-home').exists(), 'Invalid option started the application')
            self.passed(dict(case='option-' + str(index), passed=True, exitCode=child.returncode, logSha256=digest(path / 'output.log')))

    def commands(self):
        peer = Peer(self, 'command-contract', 'p2pkit-cli-' + uuid.uuid4().hex[:20])
        commands = [('help', 'Commands:'), ('peers', '(no peers yet)'), ('sessions', '(no active sessions)'),
            ('pairing', 'fingerprint'), ('adv', 'usage:'), ('disc', 'usage:'), ('mesh', 'usage:'),
            ('adv on', 'advertising on'), ('adv off', 'advertising off'),
            ('disc on', 'discovery on'), ('disc off', 'discovery off'), ('mesh on', 'auto-mesh on'), ('mesh off', 'auto-mesh off'),
            ('connect', 'usage:'), ('connect missing', 'no peer matching'), ('connect-pinned', 'usage:'),
            ('manual', 'usage:'), ('send', 'usage:'),
            ('send synthetic', 'no active session'), ('to', 'usage:'), ('to missing synthetic', 'no active session'),
            ('sendfile', 'usage:'), ('offers', '(no pending file offers)'), ('accept', 'usage:'), ('reject', 'usage:'),
            ('accept missing', 'no pending file offer'), ('reject missing', 'no pending file offer'), ('close', 'usage:'),
            ('diag', 'diagnostics test='), ('diag status', 'diagnostics test='), ('diag invalid', 'diag ['),
            ('diag fault', 'usage:'), ('diag complete', 'usage:'), ('diag start x', 'diagnostics start failed:'),
            ('diag fault command-contract no-behavior-change', 'recorded external fault action:'),
            ('x' * 65537 + 'quit', 'command rejected: maximum 65536 characters'), ('info', 'manual port'),
            ('unknown\u001b[31mcommand', 'unknown command <input omitted>'),
            ('diag complete success controls-only', 'diagnostics completed: SUCCESS'), ('diag export', 'evidence exported:')]
        for text, expected in commands:
            peer.command(text, expected)
        peer.snapshot_exports('before-clear')
        peer.command('diag clear', 'cleared session history')
        peer.command('diag start PS-T05 ' + peer.app + ' both', 'diagnostics started:')
        peer.command('diag complete success after-clear', 'diagnostics completed: SUCCESS')
        peer.observe('after-command-matrix')
        peer.quit()
        self.passed(dict(case='command-contract', passed=True, commands=len(commands) + 4, oversizedTailNotExecuted=True))

    def multi_peer_contract(self):
        app = 'p2pkit-cli-' + uuid.uuid4().hex[:20]
        alice, bob, carol = [Peer(self, 'multi-peer-' + name, app) for name in ('a', 'b', 'c')]
        self.connect(alice, bob)
        self.connect(alice, carol)
        for command in ('to anon- synthetic', 'close anon-', 'sendfile anon- ' + str(self.fixture)):
            alice.command(command, 'ambiguous session')
        alice.command('connect anon-', 'ambiguous peer')
        alice.command('connect-pinned anon- ' + bob.qr, 'ambiguous peer')
        alice.command('connect-pinned ' + bob.peer_id + ' ' + bob.qr, 'connected to ')
        offsets = [len(peer.text()) for peer in (bob, carol)]
        alice.command('send synthetic-broadcast', 'to 2 peer(s)')
        for peer, offset in zip((bob, carol), offsets):
            peer.wait_text('incoming from ', offset=offset)
        offset = len(bob.text())
        alice.command('to ' + bob.peer_id + ' synthetic-targeted', 'to 1 peer(s)')
        bob.wait_text('incoming from ', offset=offset)
        alice.command('close ' + bob.peer_id, 'closed session with ')
        alice.command('to ' + bob.peer_id + ' after-close', 'no active session matching')
        alice.command('close ' + bob.peer_id, 'no active session matching')
        # A discovered/registered selector cannot turn a gone transport into a success.
        bob.quit()
        alice.command('connect ' + bob.peer_id, 'connect failed:', timeout=30)
        for peer in (alice, carol):
            peer.command('diag complete success multi-peer-controls', 'diagnostics completed: SUCCESS')
            peer.quit()
        self.passed(dict(case='multi-peer-contract', passed=True, ambiguousSelectionRejected=True,
            pinnedExistingSessionVerified=True, broadcastAndTargetedReceiveObserved=True,
            gonePeerDidNotReportSuccess=True, physicalDiscoveryClaimed=False))

    def admission_pressure(self):
        for repeat in range(3):
            label = 'admission-pressure-' + str(repeat)
            app = 'p2pkit-cli-' + uuid.uuid4().hex[:20]
            bob = Peer(self, label + '-b', app, limited=True)
            before = bob.observe('before-two-unfinished-handshakes')
            bob.command('diag fault per-source-admission two-unfinished-loopback-connections', 'recorded external fault action:')
            connections = []
            try:
                for _ in range(2):
                    connection = socket.create_connection(('127.0.0.1', bob.port), timeout=2)
                    connection.settimeout(.1)
                    connections.append(connection)
                    try:
                        data = connection.recv(1)
                    except socket.timeout:
                        data = None
                    need(data is None, 'An intended outstanding handshake was not retained')
                extra = socket.create_connection(('127.0.0.1', bob.port), timeout=2)
                connections.append(extra)
                extra.settimeout(2)
                try:
                    refused = extra.recv(1) == b''
                    refusal = 'EOF'
                except ConnectionResetError:
                    refused, refusal = True, 'RESET'
                need(refused, 'Third same-source pre-handshake connection was not refused')
                during = bob.observe('two-held-third-refused')
                need(during['fileDescriptors'] < 256, 'Child exceeded its selected descriptor safety cap')
                bob.command('diag status', 'diagnostics test=')
            finally:
                for connection in connections:
                    connection.close()
            alice = Peer(self, label + '-a', app)
            self.connect(alice, bob)
            offset = len(bob.text())
            alice.command('send recovered', 'to 1 peer(s)')
            bob.wait_text('incoming from ', offset=offset)
            for peer in (alice, bob):
                peer.command('diag complete recovered bounded-admission-pressure', 'diagnostics completed: RECOVERY')
                peer.quit()
            limits = json.loads((bob.directory / 'child-limits.json').read_bytes())
            need(limits['sourceSha'] == self.source and all(row['parentOrSystemChanged'] is False for row in limits['limits']),
                 'Child limit provenance differs')
            self.passed(dict(case=label, passed=True, repeat=repeat, perSourceHeld=2, excessRefused=1, refusal=refusal,
                authenticatedRecoveryObserved=True, childLimits=limits, resourcesBefore=before, resourcesDuring=during,
                heapMaximumBytes=256 * 1024**2, quotaExhaustionClaimed=False))

    def connect(self, alice, bob):
        port = bob.port if self.relay is None else self.relay.port
        alice.command('manual 127.0.0.1:' + str(port) + ' ' + bob.pin, 'connected manual peer', timeout=30)
        alice.command('sessions', 'Connected')
        bob.command('sessions', 'Connected')

    def offer(self, alice, bob):
        offset = len(bob.text())
        alice.command('sendfile ' + bob.peer_id + ' ' + str(self.fixture), 'sending <selected file>')
        bob.wait_text('offered <file>', offset=offset, timeout=20)
        text = bob.command('offers', 'selector=')
        matches = re.findall(r'selector=(\S+)', text)
        need(len(matches) == 1, 'Ambiguous synthetic offer')
        return matches[0]

    def files(self, peer):
        root = peer.home / '.p2pkit/incoming'
        paths = sorted(root.rglob('*')) if root.exists() else []
        need(len(paths) < 256 and all(not p.is_symlink() for p in paths), 'Unexpected receiver filesystem')
        rows = [dict(path=str(p.relative_to(root)), bytes=p.stat().st_size, sha256=digest(p)) for p in paths if p.is_file()]
        need(sum(row['bytes'] for row in rows) <= 3 * FIXTURE_BYTES, 'Receiver byte safety cutoff')
        for row in rows:
            if row['path'].endswith('.part'):
                row['kind'] = 'uncommitted-staging'
            elif row['bytes'] == 0:
                # uniqueSaveFile atomically claims an empty target before the
                # delegate opens staging. An intentional SIGKILL can retain it.
                row['kind'] = 'empty-reservation-not-publication'
            else:
                need(row['bytes'] == FIXTURE_BYTES and row['sha256'] == self.fixture_sha,
                     'Partial or corrupt published receiver target')
                row['kind'] = 'complete-fixture'
        return rows

    def faults(self):
        for repeat in range(3):
            for phase, fault in [(phase, fault) for phase in ('handshake', 'idle', 'transfer') for fault in FAULTS] + [('transfer', 'sender-kill')]:
                label = f'{phase}-{fault}-{repeat}'
                app = 'p2pkit-cli-' + uuid.uuid4().hex[:20]
                alice, bob = Peer(self, label + '-a', app), Peer(self, label + '-b', app)
                self.relay = Relay(bob.port, 1 if phase == 'handshake' else None)
                if phase == 'handshake':
                    alice.write('manual 127.0.0.1:' + str(self.relay.port) + ' ' + bob.pin + '\n')
                    deadline = time.monotonic() + 10
                    while self.relay.forwarded[0] < 1:
                        need(time.monotonic() < deadline, 'Handshake phase not reached')
                        self.pump(.01)
                    need('connected manual peer' not in alice.text(), 'Handshake gate was already bypassed')
                else:
                    self.connect(alice, bob)
                    if phase == 'transfer':
                        self.relay.limit = self.relay.forwarded[0] + 256 * 1024
                        selector = self.offer(alice, bob)
                        bob.command('accept ' + selector, 'accepting ')
                        deadline = time.monotonic() + 20
                        while self.relay.forwarded[0] < self.relay.limit:
                            need(time.monotonic() < deadline, 'In-flight transfer phase not reached')
                            self.pump(.01)
                        need('Completed' not in alice.text() and 'Completed' not in bob.text(), 'Transfer already completed before fault')
                before_files = self.files(bob)
                for peer in (alice, bob):
                    peer.command('diag fault ' + fault + ' peer-interruption', 'recorded external fault action:')
                    peer.snapshot_exports('before-fault')
                    peer.observe('before-fault')
                if fault == 'sender-kill':
                    alice.fault('kill')
                    alice.wait_exit((-signal.SIGKILL,))
                    self.relay.close()
                    terminal = bob.wait_pattern(r'^\[file ←.*\] (Failed\(.+\)|Cancelled)$')
                    bob.command('diag status', 'diagnostics test=')
                    bob.quit()
                elif fault == 'eof':
                    bob.events.append(dict(kind='fault', action='close-stdin', utc=time.time_ns()))
                    bob.child.stdin.close()
                    bob.wait_exit((0,))
                elif fault == 'stop-cont':
                    bob.fault('stop')
                    deadline = time.monotonic() + 35  # Longer than the unchanged 30-second keepalive timeout.
                    while time.monotonic() < deadline:
                        self.pump(.1)
                    bob.fault('cont')
                    self.relay.limit = None
                    bob.command('diag status', 'diagnostics test=')
                    bob.quit()
                else:
                    bob.fault(fault)
                    allowed = dict(term=(143, -signal.SIGTERM), kill=(-signal.SIGKILL,), hup=(129, -signal.SIGHUP))[fault]
                    bob.wait_exit(allowed)
                if fault != 'kill':
                    need(bob.text().count('Stopping…') == 1, 'Catchable termination did not run lexical cleanup once')
                else:
                    need('Stopping…' not in bob.text(), 'Intentional crash must not be reported as graceful shutdown')
                self.relay.close()
                relay = self.relay.evidence()
                self.relay = None
                after_files = self.files(bob)
                if fault != 'sender-kill':
                    if phase == 'handshake':
                        terminal = alice.wait_text('manual connect failed:', timeout=40)
                    else:
                        terminal = alice.wait_pattern(r'^\[state\].* → (Closed|Failed)$')
                    alice.command('diag status', 'diagnostics test=')
                    alice.observe('after-peer-fault')
                    alice.command('diag complete interrupted expected-peer-fault', 'diagnostics completed: INTERRUPTION')
                    alice.quit()
                if phase == 'transfer' and fault != 'stop-cont':
                    need(not any(row['kind'] == 'complete-fixture' for row in after_files),
                         'An interrupted partial transfer was published')
                if fault != 'kill':
                    need(all(row['kind'] == 'complete-fixture' for row in after_files),
                         'Catchable termination leaked staging or a destination reservation')
                # The sample deliberately uses process-local identities, even with the same home.
                same = Peer(self, label + '-same-profile', app, home=bob.home)
                need(same.peer_id != bob.peer_id and same.pin != bob.pin, 'Restart retained a process-local identity')
                same.quit()
                fresh = Peer(self, label + '-new-profile', app)
                need(fresh.peer_id not in (bob.peer_id, same.peer_id) and fresh.pin not in (bob.pin, same.pin), 'New profile reused identity')
                fresh.quit()
                self.passed(dict(case=label, passed=True, fault=fault, repeat=repeat,
                    phase=phase, peerExit=bob.child.returncode, crashNotGraceful=fault in ('kill', 'sender-kill'),
                    senderExit=alice.child.returncode, survivingPeerTerminal=terminal[-2048:],
                    receiverBefore=before_files, receiverAfter=after_files, phaseRelay=relay,
                    sameAndNewProfileIdentityReset=True,
                    crashStagingNotMisreportedAsGracefulCleanup=fault in ('kill', 'sender-kill')))

    def transfers_and_storage(self):
        for repeat in range(3):
            app = 'p2pkit-cli-' + uuid.uuid4().hex[:20]
            label = 'transfer-storage-' + str(repeat)
            alice, bob = Peer(self, label + '-a', app), Peer(self, label + '-b', app)
            self.connect(alice, bob)
            offer = self.offer(alice, bob)
            bob.command('reject ' + offer, 'rejected <file>')
            # Receiver-only filesystem permission fault, not disk exhaustion or host-wide pressure.
            target = bob.home / '.p2pkit/incoming'
            target.mkdir(mode=0o700, exist_ok=True)
            identity = (target.stat().st_dev, target.stat().st_ino)
            target.chmod(0o500)
            try:
                for peer in (alice, bob):
                    peer.command('diag fault storage-denied bounded-private-directory', 'recorded external fault action:')
                offer = self.offer(alice, bob)
                bob.command('accept ' + offer, 'cannot create <app-private directory>')
                need(self.files(bob) == [], 'Denied receiver storage published data')
            finally:
                need(identity == (target.stat().st_dev, target.stat().st_ino) and not target.is_symlink(), 'Owned storage directory replaced')
                target.chmod(0o700)
            offer = self.offer(alice, bob)
            bob.command('accept ' + offer, 'accepting ')
            alice.wait_text('Completed', timeout=120)
            bob.wait_text('Completed', timeout=120)
            bob.wait_text('durable sha256=' + self.fixture_sha, timeout=20)
            rows = self.files(bob)
            need(len(rows) == 1 and rows[0]['bytes'] == FIXTURE_BYTES and rows[0]['sha256'] == self.fixture_sha,
                 'Receiver did not publish the exact synthetic fixture or leaked staging')
            for peer in (alice, bob):
                peer.observe('after-storage-recovery')
                peer.command('diag complete recovered storage-recovery', 'diagnostics completed: RECOVERY')
                peer.quit()
            self.passed(dict(case=label, passed=True, byteCount=FIXTURE_BYTES, sha256=self.fixture_sha,
                rejectionAndStorageRecoveryVerified=True, receiver=rows))

    def run(self):
        result = dict(schema=1, scope=SCOPE, sourceSha=self.source, result='FAIL', cases=self.rows,
            fullCampaignQualified=False, physicalNetworkTested=False, headfulTested=False)
        try:
            free = os.statvfs(self.directory)
            need(free.f_bavail * free.f_frsize >= 6 * 1024**3, 'Insufficient disk headroom; never purge owner data')
            self.fixture = self.directory / 'synthetic-49m.bin'
            with self.fixture.open('xb') as stream:
                block = bytes(range(256)) * 4096
                for _ in range(49):
                    stream.write(block)
            self.fixture_sha = digest(self.fixture)
            self.options()
            self.commands()
            self.multi_peer_contract()
            self.admission_pressure()
            self.transfers_and_storage()
            self.faults()
            need(all(child.poll() is not None for child in self.children), 'A launched CLI is still running')
            need(runtime_manifest(self.source) == self.manifest, 'Prepared runtime changed during controls')
            result['result'] = 'PASS'
        except BaseException as error:
            result['failure'] = dict(type=type(error).__name__, message=str(error))
            raise
        finally:
            result['elapsedSeconds'] = time.monotonic() - self.started
            result['liveChildCount'] = sum(child.poll() is None for child in self.children)
            result['remainingCampaign'] = ['terminal-emulator UI closure and approved real-display automation',
                'physical multi-peer discovery', 'dedicated-filesystem quota and isolated multi-source network-lab pressure',
                'headful multi-OS campaign',
                'controlled hostile network and independent malformed secure-v2 harness']
            if self.relay is not None:
                self.relay.close()
            private_write(self.directory / 'result.json', result)
            self.scope.close()  # Observation capabilities only; enclosing native executor owns worker cleanup.
        assess_result(result, self.source)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-authorized-cli-controls', action='store_true')
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    args = parser.parse_args()
    need(args.owner_authorized_cli_controls, 'Explicit synthetic CLI authorization required')
    os.umask(0o077)
    files = module('cli_manifest_files', 'run-rpc-capacity-lab.py')
    state, _ = files.owned_context()
    need(args.manifest == state / 'private/cli-runtime.json', 'Only the current source producer manifest is admitted')
    value = Campaign(args.directory, json.loads(files.read_private(args.manifest))).run()
    print(json.dumps(value, sort_keys=True))
    return 0 if value['result'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
