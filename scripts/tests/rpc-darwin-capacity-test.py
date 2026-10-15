#!/usr/bin/env python3
"""Offline Mac clock/route/controller controls. Mock time and pages are not native or capacity evidence."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_darwin_capacity as m
spec = importlib.util.spec_from_file_location('ios_capacity_test', ROOT / 'scripts/run-rpc-ios-mobile-capacity.py')
mobile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mobile)
lab = mobile.base.module('ios_capacity_lab_test', 'run-rpc-capacity-lab.py')


def snapshot():
    return dict(memoryBytes=16 * 1024 ** 3, availableBytes=8 * 1024 ** 3, pageBytes=16384, logicalCpus=10,
                nativeMacModelObserved=True, hypervisorPresent=False, memorySource='vm-stat-free-inactive-speculative')


def clock():
    return dict(schema=1, scope=m.SCOPE, periodNanos=m.PERIOD, durationNanos=m.DURATION,
        kernelExpirations=12500, userspaceReads=12500, coalescedExpirations=0, maximumGapNanos=m.PERIOD,
        minimumAvailableBytes=8 * 1024 ** 3, samples=[dict(elapsedNanos=0, snapshot=snapshot()),
            dict(elapsedNanos=m.DURATION, snapshot=snapshot())], healthyForAttempt=True, capacityQualified=False)


class Clock(unittest.TestCase):
    def test_same_125_second_100ms_and_6gib_limits_without_linux_counter_fabrication(self):
        self.assertEqual(m.assess_clock(clock()), clock())
        for change in (dict(durationNanos=m.DURATION - 1), dict(kernelExpirations=12499), dict(periodNanos=20_000_000),
                       dict(scope='GENERATOR_CLOCK_PREFLIGHT_NOT_CAPACITY'), dict(capacityQualified=True),
                       dict(maximumGapNanos=100_000_000), dict(healthyForAttempt=1), dict(balloonInflateDelta=0)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.assess_clock(clock() | change)

    def test_unhealthy_run_is_retained_as_unhealthy_not_renamed_as_pass(self):
        slow = clock() | dict(maximumGapNanos=100_000_000, healthyForAttempt=False)
        self.assertFalse(m.assess_clock(slow)['healthyForAttempt'])
        low = clock()
        low['samples'][-1]['snapshot']['availableBytes'] = m.MIN_MEMORY - 1
        low.update(minimumAvailableBytes=m.MIN_MEMORY - 1, healthyForAttempt=False)
        self.assertFalse(m.assess_clock(low)['healthyForAttempt'])

    def test_full_actual_memory_and_clock_inventory_is_required(self):
        for change in (dict(hypervisorPresent=True), dict(nativeMacModelObserved=False), dict(availableBytes=True),
                       dict(availableBytes=17 * 1024 ** 3), dict(pageBytes=0), dict(memorySource='fake-linux')):
            value = clock()
            value['samples'][1]['snapshot'].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                m.assess_clock(value)
        for change in (dict(coalescedExpirations=1), dict(userspaceReads=0), dict(minimumAvailableBytes=1)):
            with self.assertRaises(ValueError):
                m.assess_clock(clock() | change)

    def test_missing_virtual_or_changed_native_hardware_cannot_be_admitted(self):
        values = {'hw.memsize': 16 * 1024 ** 3, 'hw.pagesize': 16384, 'hw.logicalcpu': 10,
                  'hw.model': 'Mac16,1', 'kern.hv_vmm_present': 0}
        self.assertFalse(m.native_hardware(values.__getitem__)['hypervisorPresent'])
        for key, value in (('hw.model', 'VirtualMac2,1'), ('kern.hv_vmm_present', 1),
                           ('kern.hv_vmm_present', False), ('hw.logicalcpu', True), ('hw.pagesize', 1)):
            with self.subTest(key=key), self.assertRaises(ValueError):
                m.native_hardware((values | {key: value}).__getitem__)

    def test_kernel_counted_expirations_and_timer_closure_are_preserved(self):
        moment = [0]
        source = Mock()
        source.__enter__ = Mock(return_value=source)
        source.__exit__ = Mock(return_value=False)
        def read(timeout):
            self.assertEqual(timeout, .5)
            moment[0] += m.PERIOD
            return 1
        source.read.side_effect = read
        result = m.clock(None, now=lambda: moment[0], timer=lambda: source, observe=lambda _: snapshot())
        self.assertEqual(result['kernelExpirations'], 12500)
        self.assertEqual(result['durationNanos'], m.DURATION)
        self.assertEqual(len(result['samples']), 126)
        source.__exit__.assert_called_once()

    def test_failed_page_observation_still_closes_the_owned_timer(self):
        source = Mock()
        source.__enter__ = Mock(return_value=source)
        source.__exit__ = Mock(return_value=False)
        source.read.return_value = 100
        observe = Mock(side_effect=[snapshot(), ValueError('synthetic pages failure')])
        with self.assertRaises(ValueError):
            m.clock(None, now=Mock(side_effect=[0, 1_000_000_000]), timer=lambda: source, observe=observe)
        source.__exit__.assert_called_once()

    def test_slow_last_page_observation_cannot_disappear_from_the_clock_gap(self):
        moment = [0]
        source = Mock()
        source.__enter__ = Mock(return_value=source)
        source.__exit__ = Mock(return_value=False)
        def read(_):
            moment[0] += m.PERIOD
            return 1
        def observe(_):
            if moment[0] >= m.DURATION:
                moment[0] += 100_000_000
            return snapshot()
        source.read.side_effect = read
        result = m.clock(None, now=lambda: moment[0], timer=lambda: source, observe=observe)
        self.assertEqual(result['maximumGapNanos'], 100_000_000)
        self.assertFalse(result['healthyForAttempt'])
        source.__exit__.assert_called_once()


class Route(unittest.TestCase):
    def fixture(self):
        route = b'   route to: 192.168.14.2\ndestination: 192.168.14.2\n  interface: en0\n      flags: <UP,HOST,DONE,LLINFO,IFSCOPE>\n'
        interface = b'en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500\n\tinet 192.168.14.3 netmask 0xffffff00 broadcast 192.168.14.255\n'
        config = dict(interface='en0', endpointAddress='192.168.14.2', localAddress='192.168.14.3')
        return route, interface, config

    def test_direct_selected_kernel_route_is_not_physical_lan_proof(self):
        result = m.direct_route(*self.fixture())
        self.assertTrue(result['selectedDirectRouteObserved'])
        self.assertFalse(result['physicalLanProven'])

    def test_gateway_tunnel_wrong_address_inactive_or_ambiguous_interface_fails(self):
        route, interface, config = self.fixture()
        for change in (route.replace(b'HOST,', b'HOST,GATEWAY,'), route.replace(b'en0', b'utun0'),
                       route + b'interface: en0\n', route.replace(b'DONE', b'REJECT')):
            with self.assertRaises(ValueError):
                m.direct_route(change, interface, config)
        for change in (interface.replace(b'RUNNING', b'INACTIVE'), interface.replace(b'192.168.14.3', b'192.168.14.4'),
                       interface + interface):
            with self.assertRaises(ValueError):
                m.direct_route(route, change, config)


class Coordinator(unittest.TestCase):
    def values(self):
        return dict(schema='1', sourceSha='2' * 40, hostArtifactSha256='3' * 64, endpointAddress='192.168.14.2',
            port='48123', subnets='192.168.14.0/24', interface='en0', localAddress='192.168.14.3', hostInterface='en0',
            iosDeviceIdentifier='11111111-2222-3333-4444-555555555555')

    def test_ios_configuration_cannot_admit_android_wireless_or_weakened_lan_inputs(self):
        result = mobile.settings(self.values(), '2' * 40, 'test-run', lab)
        self.assertEqual(result['role'], 'client')
        for key, value in (('iosDeviceIdentifier', 'wireless.local'), ('interface', 'utun0'), ('hostInterface', 'awdl0'),
                           ('hostArtifactSha256', 'bad'), ('endpointAddress', '8.8.8.8'), ('subnets', '0.0.0.0/0'),
                           ('sourceSha', '4' * 40), ('adb', '/NOT_EXECUTED')):
            with self.subTest(key=key), self.assertRaises((ValueError, RuntimeError)):
                mobile.settings(self.values() | {key: value}, '2' * 40, 'test-run', lab)

    def test_no_page_or_usb_subprocess_before_native_controls(self):
        run = mobile.Run.__new__(mobile.Run)
        self.assertIsNone(run.initial_generator_snapshot())
        run.result = {}
        run.policy = Mock(control_inventory=Mock(return_value=129))
        with patch.object(mobile.darwin, 'snapshot') as observe, self.assertRaises(ValueError):
            run.generator_snapshot()
        observe.assert_not_called()

    def test_android_keeps_its_existing_linux_source_and_receipt_contract(self):
        self.assertEqual(mobile.base.Run.native_host, 'linux-x64')
        self.assertEqual(mobile.base.Run.phone_platform, 'Android')
        self.assertEqual(mobile.Run.native_host, 'macos-arm64')
        self.assertEqual(mobile.Run.phone_platform, 'Ios')
        self.assertIs(mobile.Run.workload, mobile.base.Run.workload)
        self.assertIs(mobile.Run.stop_phone, mobile.base.Run.stop_phone)
        self.assertIs(mobile.Run.check_receipt, mobile.base.Run.check_receipt)


if __name__ == '__main__':
    unittest.main(verbosity=2)
