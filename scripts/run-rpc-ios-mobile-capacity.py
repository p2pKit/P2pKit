#!/usr/bin/env python3
"""Opt-in native Mac generator / wired iPhone control / real organization-LAN RPC candidate.

Uses the existing JVM workload, protected identities, receipts, original timing,
retention and Stop barriers. A schema2 campaign can explicitly install a bound,
already signed development app, prepare its first slot and activate a sealed
run. It never signs, terminates an active app, grants permissions, fabricates
KVM/Linux observations or claims a physical capacity pass.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
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
    need(type(values) is dict and values.get('schema') in ('1', '2'))
    fields = SETTINGS | ({'clientCount'} if values['schema'] == '2' else set())
    if values['schema'] == '2' and 'iosControlTransport' in values:
        fields |= {'iosControlTransport'}
        need(values['iosControlTransport'] in ('wired', 'wireless'), 'Explicit wired or wireless iPhone control required')
    if values['schema'] == '2' and 'macGeneratorMinimumAvailableGiB' in values:
        fields |= {'macGeneratorMinimumAvailableGiB'}
        need(values['macGeneratorMinimumAvailableGiB'] in ('1', '6'), 'Explicit1GiB or6GiB Mac policy required')
    need(set(values) == fields and all(type(v) is str for v in values.values()) and
         values['sourceSha'] == source and re.fullmatch('[a-f0-9]{40}', source) and
         re.fullmatch('[a-f0-9]{64}', values['hostArtifactSha256']) and re.fullmatch('[a-z0-9-]{1,48}', label))
    if values['schema'] == '2':
        need(values['clientCount'] in ('128', '256'), 'Explicit128/256 profile required')
    need(re.fullmatch('[A-Fa-f0-9]{8}(?:-[A-Fa-f0-9]{4}){3}-[A-Fa-f0-9]{12}', values['iosDeviceIdentifier']) and
         re.fullmatch('en[0-9]{1,3}', values['interface']) and re.fullmatch('en[0-9]{1,3}', values['hostInterface']),
         'Explicit wired iPhone identity and selected LAN interfaces required')
    config = {k: values[k] for k in lab.FIELDS - {'role', 'runLabel'}} | dict(role='client', runLabel=label)
    if values['schema'] == '2':
        config['clientCount'] = values['clientCount']
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
        control_transport = self.values.get('iosControlTransport', 'wired')
        if control_transport == 'wireless':
            self.scope = 'IOS_WIRELESS_COREDEVICE_MAC_GENERATOR_REAL_RPC_CANDIDATE_PENDING_PHYSICAL_NETWORK_AND_RESOURCE_REVIEW'
        backend = ios.DevicectlFiles(self.commands, self.control / 'usb', self.values['iosDeviceIdentifier'], label,
                                    control_transport=control_transport)
        previous = getattr(self.args, 'previous_ios_run_label', None)
        previous_hash = getattr(self.args, 'previous_ios_inbox_sha256', None)
        need((previous is None) == (previous_hash is None), 'Previous iOS label and exact inbox hash must be supplied together')
        if previous is not None:
            self.previous_ios_prepare = (previous, previous_hash)
        return ios.IosUsb(backend, self.bound, owner_authorized=True)

    def generator_snapshot(self):
        need(self.result.get('nativeControlTests') == self.policy.control_inventory(self.native_host),
             'Do not launch a page observer after failed/missing native controls')
        return darwin.snapshot(self.commands)

    def initial_generator_snapshot(self):
        return None  # No subprocess, USB or clock observation before the complete native inventory passes.

    def prerequisites(self):
        self.result['iosControlTransport'] = self.values.get('iosControlTransport', 'wired')
        self.generator_prerequisites()
        self.begin_device_control()
        import time
        app = getattr(self.args, 'install_ios_app', None)
        prepare = getattr(self.args, 'prepare_ios_slot', False)
        need(not (getattr(self, 'previous_ios_prepare', None) is not None and (app is not None or prepare)),
             'Later iOS slots must use observed prior closure, never reinstall or relaunch an active app')
        if app is not None:
            self.result['installationAccepted'] = self.phone.backend.install_app(app, self.bound, time.monotonic() + 120)
        if prepare:
            self.phone.backend.launch_prepare(self.bound, time.monotonic() + 30)
            self.result['developmentSlotLaunchAccepted'] = True
        self.result['iosCoordinatorSha256'] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        self.result['devicectlSha256'] = self.phone.backend.tool_sha256
        self.result['coreDeviceVersion'] = self.phone.backend.tool_version
        self.result['coreDeviceMetadataSha256'] = self.phone.backend.metadata_sha256
        self.result['rawCopyIsAtomicPublication'] = False
        if getattr(self, 'previous_ios_prepare', None) is not None:
            label, digest = self.previous_ios_prepare
            self.phone.backend.prepare_next(self.bound, label, digest, time.monotonic() + 30)
            self.result['previousIosSlotPrepared'] = dict(runLabel=label, previousInboxSha256=digest,
                                                          priorRuntimeClosureVerified=True)
        print('Keep the selected signed app foreground/unlocked. Its NEW prepared USB slot must match this run; '
              'the RPC readiness timer has not started.', flush=True)
        self.phone.start()  # Validates the prepared development slot; never grants system trust or starts RPC.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner-authorized-mobile', required=True, action='store_true')
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--run-label', required=True)
    parser.add_argument('--mode', choices=('steady', 'large', 'correctness', 'churn'), required=True)
    parser.add_argument('--previous-ios-run-label')
    parser.add_argument('--previous-ios-inbox-sha256')
    parser.add_argument('--install-ios-app', type=Path,
                        help='First deployment only: exact signed development bundle through the selected native tool')
    parser.add_argument('--prepare-ios-slot', action='store_true',
                        help='Initial stopped development app only; prepares a slot without starting RPC')
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
