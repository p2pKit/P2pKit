#!/usr/bin/env python3
"""Opt-in native Mac generator / wired iPhone control / real organization-LAN RPC candidate.

Uses the existing JVM workload, protected identities, receipts, original timing,
retention and Stop barriers. It does not sign/install/start the app, fabricate KVM,
pretend that Mac page counts are Linux counters, or claim a physical capacity pass.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_darwin_capacity as darwin
import rpc_ios_usb as ios

spec = importlib.util.spec_from_file_location('ios_mobile_existing_coordinator', ROOT / 'scripts/run-rpc-mobile-capacity.py')
base = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = base
spec.loader.exec_module(base)
need = ios.need
SETTINGS = (base.SETTINGS - {'androidUsbSerial', 'adb'}) | {'iosDeviceIdentifier'}


def settings(values, source, label, lab):
    need(type(values) is dict and set(values) == SETTINGS and all(type(v) is str for v in values.values()) and
         values['schema'] == '1' and values['sourceSha'] == source and re.fullmatch('[a-f0-9]{40}', source) and
         re.fullmatch('[a-f0-9]{64}', values['hostArtifactSha256']) and re.fullmatch('[a-z0-9-]{1,48}', label))
    need(re.fullmatch('[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}', values['iosDeviceIdentifier']) and
         re.fullmatch('en[0-9]{1,3}', values['interface']) and re.fullmatch('en[0-9]{1,3}', values['hostInterface']),
         'Explicit wired iPhone identity and selected LAN interfaces required')
    config = {k: values[k] for k in lab.FIELDS - {'role', 'runLabel'}} | dict(role='client', runLabel=label)
    lab.configuration(config, source)  # Same production organization-LAN policy is applied again by the real JVM driver.
    return config


class Run(base.Run):
    native_host = 'macos-arm64'
    phone_platform = 'Ios'
    scope = 'IOS_USB_MAC_GENERATOR_REAL_RPC_CANDIDATE_PENDING_PHYSICAL_NETWORK_AND_RESOURCE_REVIEW'

    def admit_environment(self, args):
        from audit_processes import host_role
        need(args.owner_authorized_mobile and host_role() == self.native_host and os.getuid() == os.geteuid() != 0,
             'Explicit owner-approved native Mac ARM generator and wired iPhone required')

    def bind_context(self):
        harness = self.runner.source_snapshot(ROOT)
        need(self.context['host'] == self.native_host and self.context['root'] == str(ROOT) and
             self.context['source'] == harness and harness['status'] == '', 'Exact clean Mac product/coordinator source required')
        return harness

    def configuration(self, source, label):
        return settings(self.values, source, label, self.lab)

    def new_phone(self, label):
        backend = ios.DevicectlFiles(self.commands, self.control / 'usb', self.values['iosDeviceIdentifier'], label)
        return ios.IosUsb(backend, self.bound, owner_authorized=True)

    def generator_snapshot(self):
        need(self.result.get('nativeControlTests') == self.policy.control_inventory(self.native_host),
             'Do not launch a page observer after failed/missing native controls')
        return darwin.snapshot(self.commands)

    def initial_generator_snapshot(self):
        return None  # No subprocess, USB or clock observation before the complete native inventory passes.

    def prerequisites(self):
        destination = self.state / 'evidence' / ('mobile-controls-' + self.config['runLabel'])
        proof = self.native('mobile-native-controls', [sys.executable, str(ROOT / 'scripts/tests/run-audit-command-test.py'),
            '--expected-host', self.native_host, '--evidence-dir', str(destination)])
        count = self.policy.unittest_count(self.output(proof, 'stderr').decode())
        need(count == self.policy.control_inventory(self.native_host), 'Fresh complete native Mac controls required')
        self.result['nativeControlTests'] = count
        self.result['generatorBefore'] = self.generator_snapshot()
        java = str(Path(os.environ['JAVA_HOME']).resolve(strict=True) / 'bin/java')
        proof = self.native('mobile-jdk17', [java, '-XshowSettings:properties', '-version'])
        properties = self.output(proof, 'stderr')
        need(re.findall(rb'(?m)^\s*java\.specification\.version = ([0-9]+)\s*$', properties) == [b'17'] and
             re.findall(rb'(?m)^\s*os\.arch = (\S+)\s*$', properties) == [b'aarch64'], 'Actual native ARM JVM17 required')
        proof = self.native('mobile-clock', [sys.executable, str(ROOT / 'scripts/rpc_darwin_capacity.py'), '--directory',
            str(self.state / 'work' / ('mobile-clock-' + self.config['runLabel']))])
        clock = darwin.assess_clock(json.loads(self.output(proof), object_pairs_hook=ios.unique))
        self.result['clockPreflight'] = clock
        need(clock['healthyForAttempt'], 'Mac generator is not healthy for an interpretable capacity attempt')
        _, route = self.commands.run('selected-mac-route', ['/sbin/route', '-n', 'get', '-inet', self.config['endpointAddress']], timeout=10)
        _, interface = self.commands.run('selected-mac-interface', ['/sbin/ifconfig', self.config['interface']], timeout=10)
        self.result['routeObservation'] = darwin.direct_route(route, interface, self.config)
        self.result['iosCoordinatorSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.result['devicectlSha256'] = self.phone.backend.tool_sha256
        self.result['rawCopyIsAtomicPublication'] = False
        print('Keep the selected signed app foreground/unlocked. Its NEW prepared USB slot must match this run; '
              'the RPC readiness timer has not started.', flush=True)
        self.phone.start()  # Requires the owner's explicit on-phone preparation; never grants trust or starts a role.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-authorized-mobile', required=True, action='store_true')
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--run-label', required=True)
    parser.add_argument('--mode', choices=('steady', 'large'), required=True)
    args = parser.parse_args()
    os.umask(0o077)
    # An explicit opt-in selects only synthetic test execution, not native/device
    # admission. Existing native ownership and every actual source check remain mandatory.
    environment = base.safe_environment(os.environ)
    os.environ.clear()
    os.environ.update(environment)
    return Run(args).run()


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        print('IOS_MOBILE_CAPACITY_ABORTED: ' + type(error).__name__ + '; inspect private evidence, no qualification', file=sys.stderr)
        raise SystemExit(1)
