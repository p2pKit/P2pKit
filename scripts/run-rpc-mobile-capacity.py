#!/usr/bin/env python3
"""Opt-in Android USB control / real organization-LAN RPC capacity coordinator.

Candidate tooling: physical USB/device execution is still required. This is not
an emulator mode, a data tunnel, an iPhone coordinator or a qualification verdict.
Run only inside the existing admitted native executor, on a clean Linux-x64
checkout with its source-matched prepared capacity distribution. No build,
installation, permission change, global ADB access or network reconfiguration.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = ROOT
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_capacity_evidence as evidence
import rpc_mobile_capacity as protocol
import rpc_mobile_usb as usb

SCOPE = 'ANDROID_USB_CONTROL_REAL_RPC_CANDIDATE_PENDING_PHYSICAL_NETWORK_AND_RESOURCE_REVIEW'
SETTINGS = {'schema', 'sourceSha', 'hostArtifactSha256', 'endpointAddress', 'port', 'subnets',
            'interface', 'localAddress', 'hostInterface', 'androidUsbSerial', 'adb'}
BOUNDS = {'mobile-native-controls': 1800, 'mobile-jdk17': 45, 'mobile-clock': 150, 'mobile-client': 2500}
need = protocol.need


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


def settings(value, source, label, lab):
    need(type(value) is dict and set(value) == SETTINGS and all(type(v) is str for v in value.values()))
    need(value['schema'] == '1' and value['sourceSha'] == source and re.fullmatch('[a-f0-9]{40}', source) and
         re.fullmatch('[a-f0-9]{64}', value['hostArtifactSha256']) and re.fullmatch('[a-z0-9-]{1,48}', label))
    need(re.fullmatch('[A-Za-z0-9_.:-]{1,32}', value['hostInterface']) and
         re.fullmatch('[A-Za-z0-9_-]{1,128}', value['androidUsbSerial']) and
         not value['androidUsbSerial'].startswith('emulator-'))
    adb = Path(value['adb'])
    need(adb.is_absolute() and '..' not in adb.parts and adb.name == 'adb', 'Select the installed ADB explicitly')
    config = {k: value[k] for k in lab.FIELDS - {'role', 'runLabel'}} | dict(role='client', runLabel=label)
    lab.configuration(config, source)  # The real library still performs all of its own interface/path admission.
    return config


def direct_route(raw, config):
    """A diagnostic prerequisite, NOT proof that a provider's virtual NIC is a physical LAN."""
    need(type(raw) is bytes and len(raw) <= 65536)
    rows = json.loads(raw, object_pairs_hook=evidence.unique)
    need(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict)
    row = rows[0]
    need(row.get('dst') == config['endpointAddress'] and row.get('dev') == config['interface'] and
         row.get('from', row.get('prefsrc')) == config['localAddress'] and
         not any(k in row for k in ('gateway', 'via', 'encap', 'multipath')) and
         row.get('type', 'unicast') == 'unicast', 'No gateway/tunnel substitution for the selected direct test path')
    return dict(selectedDirectRouteObserved=True, physicalLanProven=False,
                rawSha256=hashlib.sha256(raw).hexdigest())


def safe_environment(original):
    value = dict(original)
    for key in list(value):
        if key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN') or \
                key.upper().startswith(('SIGNING_', 'ORG_GRADLE_PROJECT_SIGNING', 'MAVEN_CENTRAL_', 'SONATYPE_')):
            value.pop(key)
    value.update(RPC_CAPACITY_LAB_AUTHORIZED='synthetic-private-network-only',
                 RPC_CAPACITY_MOBILE_AUTHORIZED=protocol.AUTHORIZATION, PYTHONDONTWRITEBYTECODE='1')
    return value


def bind_sources(runner, context):
    harness = runner.source_snapshot(HARNESS_ROOT)
    need(context['host'] == 'linux-x64' and context['root'] == str(ROOT) and
         context['source'] == runner.source_snapshot(ROOT) and
         context['source']['status'] == harness['status'] == '',
         'Both product and coordinator must be clean, independently source-bound checkouts')
    return harness


class Run:
    native_host = 'linux-x64'
    phone_platform = 'Android'
    scope = SCOPE

    def admit_environment(self, args):
        need(args.owner_authorized_mobile and platform.system() == 'Linux' and platform.machine() == 'x86_64',
             'Explicit owner-approved Linux-x64 generator and wired Android required; no alternate-platform claim')

    def bind_context(self):
        return bind_sources(self.runner, self.context)

    def configuration(self, source, label):
        return settings(self.values, source, label, self.lab)

    def new_phone(self, label):
        self.runner.reject_symlinks(Path(self.values['adb']))
        need(Path(self.values['adb']).is_file() and os.access(self.values['adb'], os.X_OK))
        return usb.AndroidUsb(self.commands, self.control / 'usb', Path(self.values['adb']),
                              self.values['androidUsbSerial'], label)

    def generator_snapshot(self):
        return evidence.clock_snapshot()

    def initial_generator_snapshot(self):
        return self.generator_snapshot()

    def __init__(self, args):
        self.admit_environment(args)
        self.lab = module('mobile_lab', 'run-rpc-capacity-lab.py')
        self.runner = module('mobile_native', 'run-audit-command.py')
        self.checker = module('mobile_receipts', 'check-audit-receipt.py')
        self.policy = module('mobile_inventory', 'run-rpc-qualification.py')
        self.state, source = self.lab.owned_context()
        _, self.context = self.runner.context_at(str(self.state))
        self.harness_source = self.bind_context()
        self.ancestry = os.environ['P2PKIT_AUDIT_OWNERSHIP_CHAIN'].split(':')
        raw = self.lab.read_private(args.settings)
        self.values = self.lab.parse(raw)
        self.config = self.configuration(source, args.run_label)
        self.lab.classpath(source)  # Verify every prepared JAR; never accept a caller-supplied classpath.
        self.control = self.lab.private_directory(self.state / 'work') / ('mobile-control-' + args.run_label)
        self.control.mkdir(mode=0o700)
        self.directory = self.state / 'work' / ('mobile-client-' + args.run_label)
        self.directory.mkdir(mode=0o700)
        for name in ('usb', 'commands'):
            (self.control / name).mkdir(mode=0o700)
        self.mode = args.mode
        self.bound = dict(schema='1', scope=protocol.SCOPE, runLabel=args.run_label,
            runNonce=os.urandom(32).hex(), hostPlatform=self.phone_platform, hostSourceSha=source,
            hostArtifactSha256=self.values['hostArtifactSha256'])
        self.protocol = protocol.Protocol(self.bound, self.config['endpointAddress'], int(self.config['port']))
        self.env = safe_environment(os.environ)
        # This executable's environment only, before any child/native command;
        # never alter the owner's shell or carry publishing credentials to tools.
        os.environ.clear()
        os.environ.update(self.env)
        self.commands = usb.Commands(self.control / 'commands', self.env, self.lab)
        self.phone = self.new_phone(args.run_label)
        self.client = self.client_log = None
        self.client_id = uuid.uuid4().hex
        self.client_proof = None
        self.phone_stopped = False
        self.stop_attempted = False
        self.samples = []
        self.last_sample = None
        self.started = None
        self.result = dict(schema=1, scope=self.scope, mode=self.mode, source=self.context['source'],
            harnessSource=self.harness_source, harnessSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            settingsSha256=hashlib.sha256(raw).hexdigest(), status='FAIL', foundationStatus='NOT_READY',
            physicalLanQualified=False, mobileCapacityQualified=False, nativeCommands={}, errors=[],
            generatorBefore=self.initial_generator_snapshot())

    def check_receipt(self, purpose, argv, code):
        path = self.control / (purpose + '.json')
        proof = self.runner.read_json(path)
        self.checker.validate(proof, code, purpose, ROOT, ROOT / 'gradlew', argv)
        need(proof['jobId'] == self.context['id'] and proof['host'] == self.native_host and proof['kind'] == 'command' and
             proof['gradleHome'] == self.context['gradleHome'] and
             proof['sourceBefore'] == proof['sourceAfter'] == self.context['source'] and
             proof['ancestorInvocationIds'] == self.ancestry and not proof['ownedSurvivors'] and
             not proof['errors'] and not proof['ownership']['discoveryErrors'] and proof['stopExitCode'] == 0 and
             proof == self.runner.read_json(self.state / 'evidence' / proof['id'] / 'receipt.json'),
             'Source-bound native finalization is unproven')
        self.result['nativeCommands'][purpose] = dict(exitCode=code, finalizationVerified=True,
                                                     receiptSha256=self.runner.file_digest(path))
        return proof

    def native(self, purpose, argv):
        need(purpose in BOUNDS and purpose != 'mobile-client')
        with (self.control / (purpose + '.driver.log')).open('x') as log, \
                contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            code = self.runner.main(['--cwd', str(ROOT), '--wrapper', str(ROOT / 'gradlew'), '--kind', 'command',
                '--purpose', purpose, '--timeout', str(BOUNDS[purpose]),
                '--receipt', str(self.control / (purpose + '.json')), '--', *map(str, argv)])
        proof = self.check_receipt(purpose, argv, code)
        need(code == 0, 'A required native prerequisite failed')
        return proof

    def output(self, proof, stream='stdout'):
        return evidence.bounded(self.state / 'evidence' / proof['id'] / ('product.' + stream + '.log'))

    def prerequisites(self):
        destination = self.state / 'evidence' / ('mobile-controls-' + self.config['runLabel'])
        proof = self.native('mobile-native-controls', [sys.executable, str(ROOT / 'scripts/tests/run-audit-command-test.py'),
            '--expected-host', 'linux-x64', '--evidence-dir', str(destination)])
        count = self.policy.unittest_count(self.output(proof, 'stderr').decode())
        need(count == self.policy.control_inventory('linux-x64'), 'Complete native control inventory is required')
        self.result['nativeControlTests'] = count
        java = str(Path(os.environ['JAVA_HOME']).resolve(strict=True) / 'bin/java')
        proof = self.native('mobile-jdk17', [java, '-XshowSettings:properties', '-version'])
        properties = self.output(proof, 'stderr')
        need(re.findall(rb'(?m)^\s*java\.specification\.version = ([0-9]+)\s*$', properties) == [b'17'] and
             re.findall(rb'(?m)^\s*os\.arch = (\S+)\s*$', properties) in ([b'amd64'], [b'x86_64']),
             'Actual native x64 JVM 17 required')
        # Keep the existing 125-second, <100ms-gap, >=6GiB, no-balloon preflight.
        proof = self.native('mobile-clock', [sys.executable, str(ROOT / 'scripts/run-rpc-capacity-qualification.py'), 'clock'])
        clock = evidence.clock_evidence(json.loads(self.output(proof), object_pairs_hook=evidence.unique))
        self.result['clockPreflight'] = clock
        need(clock['healthyForAttempt'], 'Generator is not healthy enough for an interpretable capacity attempt')
        _, raw = self.commands.run('selected-direct-route', ['ip', '-j', '-4', 'route', 'get',
            self.config['endpointAddress'], 'from', self.config['localAddress']], timeout=10)
        self.result['routeObservation'] = direct_route(raw, self.config)
        self.result['adbSha256'] = hashlib.sha256(evidence.bounded(Path(self.values['adb']), 64 * 1024 * 1024)).hexdigest()
        self.phone.start()
        print('Authorize the new private USB key on the selected test phone; no RPC readiness timer has started.', flush=True)
        self.phone.await_authorization()

    def launch(self):
        self.lab.write_private(self.directory / 'config.txt', self.lab.encode(self.config))
        self.lab.write_private(self.directory / 'mobile.txt', protocol.encode(self.bound | dict(
            hostInterface=self.values['hostInterface'])))
        self.client_argv = [sys.executable, str(ROOT / 'scripts/run-rpc-capacity-lab.py'), 'run',
            '--directory', str(self.directory), '--role', 'client', '--mode', self.mode]
        argv = [sys.executable, str(ROOT / 'scripts/run-audit-command.py'), '--id', self.client_id,
            '--cwd', str(ROOT), '--wrapper', str(ROOT / 'gradlew'), '--kind', 'command', '--purpose', 'mobile-client',
            '--timeout', str(BOUNDS['mobile-client']), '--receipt', str(self.control / 'mobile-client.json'),
            '--', *self.client_argv]
        self.client_log = (self.control / 'client.driver.log').open('xb')
        self.client = subprocess.Popen(argv, cwd=ROOT, env=self.env, stdin=subprocess.DEVNULL,
                                       stdout=self.client_log, stderr=subprocess.STDOUT)
        self.started = time.monotonic()
        while not (self.directory / 'mobile-inbox.txt').exists():
            self.live(120)
            time.sleep(.1)
        self.phone.provision(self.lab.read_private(self.directory / 'mobile-inbox.txt'))
        print('On the phone, import the explicitly selected run and approve its network/128 synthetic pins. '
              'The original 120-second RPC readiness bound is unchanged.', flush=True)
        while True:
            self.live(120)
            need(self.phone.read('failed.txt') is None, 'Phone control failed before readiness')
            row = self.phone.read('ready.txt')
            if row is not None:
                self.protocol.ready(row)
                self.lab.write_private(self.directory / 'host-ready.txt', protocol.encode(row))
                return
            time.sleep(.1)

    def live(self, bound=2400):
        need(self.client is not None and self.client.poll() is None and time.monotonic() - self.started < bound and
             self.client_log.tell() <= 1048576, 'Generator exited or exceeded its original bounded work phase')

    def sample(self):
        # Failure observation and telemetry share one budget, not two 4-second
        # commands plus retries. Neither a duplicate nor a late new row refreshes
        # the existing 4.5-second provider freshness requirement.
        deadline = time.monotonic() + 4
        def remaining():
            value = deadline - time.monotonic()
            need(value > 0, 'Shared mobile observation budget expired')
            return min(4, value)
        need(self.phone.read('failed.txt', timeout=remaining()) is None, 'Phone reported a failed control session')
        row = self.phone.read('telemetry.txt', timeout=remaining())
        need(time.monotonic() < deadline and
             (self.last_sample is None or time.monotonic() - self.last_sample < 4.5),
             'Phone observation exceeded its shared/freshness bound')
        if row is not None:
            observed = self.protocol.telemetry(row)
            if observed is not None:
                need(len(self.samples) < 3000)
                self.samples.append(observed)
                self.last_sample = time.monotonic()
                self.lab.write_private(self.directory / 'host-telemetry.txt', protocol.encode(row), replace=True)
                return observed
        need(self.last_sample is None or time.monotonic() - self.last_sample < 4.5,
             'No new phone telemetry inside the original provider freshness bound')
        return None

    def wait_fresh(self):
        deadline = time.monotonic() + 4.5
        while True:
            value = self.sample()
            need(time.monotonic() < deadline, 'Phone sample exceeded the original provider freshness bound')
            if value is not None:
                return value
            time.sleep(.1)

    def workload(self):
        self.last_sample = time.monotonic()
        while self.client.poll() is None:
            # Exiting between this loop's poll and another poll is normal, not
            # a lost generator. Collect its finalized result below instead of
            # racing a second liveness assertion against successful shutdown.
            need(time.monotonic() - self.started < 2400 and self.client_log.tell() <= 1048576,
                 'Generator exceeded its original bounded work phase')
            self.sample()
            time.sleep(.25)
        code = self.client.wait(timeout=1)
        self.client_proof = self.check_receipt('mobile-client', self.client_argv, code)
        raw = self.lab.read_private(self.directory / 'launcher-result.json')
        result = json.loads(raw, object_pairs_hook=evidence.unique)
        need(type(result) is dict and result.get('sourceSha') == self.context['source']['commit'] and
             result.get('runLabel') == self.config['runLabel'] and result.get('role') == 'client' and
             result.get('mode') == self.mode, 'Cannot attribute another source, run or role\'s measurement')
        measured = evidence.measurement(result.get('measurement'), self.mode)
        self.result['measurement'] = measured  # Preserve a valid failed measurement before requiring a pass.
        if self.mode == 'steady':
            self.result['initialization'] = evidence.initialization(result.get('initialization'))
        need(code == 0 and result.get('status') == 'PENDING_RESOURCE_AND_NETWORK_REVIEW' and
             measured['status'] == 'PENDING_RESOURCE_AND_NETWORK_REVIEW' and
             result.get('cleanup', {}).get('cleanupVerified') is True and
             result.get('cleanup', {}).get('mechanicalChecksPassed') is True and
             self.lab.parse(self.lab.read_private(self.directory / 'clients-closed.txt')) ==
             dict(closed='true', fixturesRemoved='true'), 'Full exact workload and client fixture retirement required')
        before = self.wait_fresh()  # Strictly after the client/launcher retired, not a stale connected sample.
        deadline = time.monotonic() + 75
        after = before
        while after['uptimeMillis'] - before['uptimeMillis'] < 65000:
            need(time.monotonic() < deadline, 'The original post-retention observation did not complete')
            after = self.wait_fresh()
        self.result['postRetention'] = protocol.retention(before, after)

    def stop_phone(self):
        if not self.phone.provisioned or self.stop_attempted:
            return
        self.stop_attempted = True
        self.phone.stop(protocol.encode(self.protocol.stop()))
        deadline = time.monotonic() + 30
        while True:
            row = self.phone.read('closed.txt')
            need(time.monotonic() < deadline, 'Phone close and pin retirement are unproven')
            if row is not None:
                self.protocol.closed(row)
                self.phone_stopped = True
                self.result['phoneCleanup'] = dict(runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True)
                return
            time.sleep(.2)

    def finish(self):
        errors = self.result['errors']
        if self.client is not None and self.client_proof is None:
            try:
                # Only this exact invocation ID in this admitted state. Never a
                # raw PID/group, global server or another session's CI process.
                if self.client.poll() is None:
                    self.runner.request_cancellation(self.state, self.context['id'], self.client_id)
                code = self.client.wait(timeout=150)
                self.client_proof = self.check_receipt('mobile-client', self.client_argv, code)
            except Exception as error:
                errors.append(dict(phase='client-retirement', error=type(error).__name__))
        # A control/transport failure can coincide with normal JVM completion.
        # Retain any fully valid measurement after native finalization, even
        # when an earlier failure prevented workload() from reading it. This
        # cannot remove errors, award a pass or admit a partial measurement.
        if self.client_proof is not None:
            try:
                path = self.directory / 'launcher-result.json'
                if path.exists():
                    value = json.loads(self.lab.read_private(path), object_pairs_hook=evidence.unique)
                    need(type(value) is dict and value.get('sourceSha') == self.context['source']['commit'] and
                         value.get('runLabel') == self.config['runLabel'] and value.get('mode') == self.mode and
                         value.get('role') == 'client')
                    if value.get('measurement') is not None:
                        measured = evidence.measurement(value['measurement'], self.mode)
                        need(self.result.get('measurement', measured) == measured)
                        self.result['measurement'] = measured
                    if self.mode == 'steady' and value.get('initialization') is not None:
                        self.result['initialization'] = evidence.initialization(value['initialization'])
            except Exception as error:
                errors.append(dict(phase='measurement-retention', error=type(error).__name__))
        try:
            self.stop_phone()
        except Exception as error:
            errors.append(dict(phase='phone-retirement', error=type(error).__name__))
        try:
            self.result['usbCleanup'] = self.phone.close()
        except Exception as error:
            errors.append(dict(phase='usb-retirement', error=type(error).__name__))
        if self.client_log is not None:
            self.client_log.close()
        self.result['phoneSamples'] = self.samples
        self.result['usbCommands'] = self.commands.rows
        try:
            self.result['generatorAfter'] = self.generator_snapshot()
        except Exception as error:
            self.result['generatorAfter'] = None
            errors.append(dict(phase='generator-final-observation', error=type(error).__name__))
        for field, root, expected in (('sourceUnchanged', ROOT, self.context['source']),
                                      ('harnessUnchanged', HARNESS_ROOT, self.harness_source)):
            self.result[field] = False
            try:
                self.result[field] = self.runner.source_snapshot(root) == expected
            except Exception as error:
                errors.append(dict(phase=field + '-observation', error=type(error).__name__))
        if errors or not self.result['sourceUnchanged'] or not self.result['harnessUnchanged'] or not self.phone_stopped:
            self.result['status'] = 'FAIL'
        need(len(json.dumps(self.result, allow_nan=False).encode()) <= 8 * 1024 * 1024,
             'Bounded full-duration evidence required')
        self.runner.write_new_json(self.control / 'result.json', self.result)

    def run(self):
        try:
            self.prerequisites()
            self.launch()
            self.workload()
            self.stop_phone()
            self.result['status'] = 'MECHANICAL_PASS_PENDING_NETWORK_AND_RESOURCE_REVIEW'
        except Exception as error:
            self.result['errors'].append(dict(phase='execution', error=type(error).__name__))
        finally:
            self.finish()
        print('MOBILE_CAPACITY: ' + self.result['status'] + '; not physical/mobile/release qualification')
        return 0 if self.result['status'].startswith('MECHANICAL_PASS_') else 1


def main():
    global ROOT
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-authorized-mobile', action='store_true', required=True)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--run-label', required=True)
    parser.add_argument('--mode', choices=('steady', 'large'), required=True)
    parser.add_argument('--source', type=Path, default=HARNESS_ROOT,
                        help='Exact clean product source matching the installed app and prepared JVM distribution')
    args = parser.parse_args()
    need(args.source.is_absolute() and args.source == args.source.resolve(strict=True),
         'Explicit absolute canonical product checkout required')
    ROOT = args.source
    return Run(args).run()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('MOBILE_CAPACITY_ABORTED: ' + type(error).__name__ + '; inspect private evidence, no qualification', file=sys.stderr)
        raise SystemExit(1)
