#!/usr/bin/env python3
"""Offline isolation/admission controls, not a namespace, JVM, network or capacity test."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('same_host', ROOT / 'scripts/run-rpc-same-host-lab.py')
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


def topology(role='host'):
    return {
        'links': [{'ifname': 'lo'}, {'ifname': lab.INTERFACE, 'linkinfo': {'info_kind': 'veth'},
                                   'flags': ['UP', 'LOWER_UP', 'MULTICAST']}],
        'routes': [{'dst': lab.SUBNET, 'dev': lab.INTERFACE}],
        'addresses': [{'ifname': 'lo', 'addr_info': [{'local': '127.0.0.1', 'prefixlen': 8, 'family': 'inet'},
                                                    {'local': '::1', 'prefixlen': 128, 'family': 'inet6'}]},
                      {'ifname': lab.INTERFACE, 'addr_info': [
                          {'local': lab.ADDRESSES[role], 'prefixlen': 30, 'family': 'inet'},
                          {'local': 'fe80::1', 'prefixlen': 64, 'family': 'inet6'}]}],
        'role': role,
    }


class IsolationTests(unittest.TestCase):
    def test_attempts_have_distinct_bounded_create_only_paths(self):
        self.assertEqual(lab.mode_label(SimpleNamespace(mode='steady', attempt=1)), 'steady')
        self.assertEqual(lab.mode_label(SimpleNamespace(mode='steady', attempt=2)), 'steady-2')
        self.assertEqual(lab.mode_label(SimpleNamespace(mode='large', attempt=99)), 'large-99')
        for invalid in (0, -1, 100, True, '2'):
            with self.assertRaises(RuntimeError):
                lab.mode_label(SimpleNamespace(mode='steady', attempt=invalid))

    def test_full_idle_retention_checks_resources_not_a_forced_rss_reset(self):
        before = dict(sequence=20, uptimeMillis=1000, cpuNanos=2000, residentBytes=4096,
                      nativeThreads=10, jvmThreads=8, connected=0, accepted=128, completed=128,
                      refused=0, duplicates=0, droppedNotifications=0, protocolFailures=0,
                      connectionFailures=0, running=0, queued=0, records=128, payloadBytes=1024)
        after = {**before, 'sequence': 85, 'uptimeMillis': 66000, 'cpuNanos': 4000, 'residentBytes': 8192,
                 'records': 0, 'payloadBytes': 0}
        self.assertEqual(lab.retention_admission(before, after)['status'], 'PASS')
        for mutation in ({'uptimeMillis': 65999}, {'sequence': 20}, {'cpuNanos': 0}, {'residentBytes': 0},
                         {'accepted': 129}, {'completed': 129}, {'refused': 1}, {'duplicates': 1},
                         {'protocolFailures': 1}, {'connectionFailures': 1}, {'connected': 1},
                         {'running': 1}, {'queued': 1}, {'records': 1}, {'payloadBytes': 1},
                         {'cpuNanos': True}, {'jvmThreads': -1}, {'private': 'not-an-exported-field'}):
            with self.assertRaises(RuntimeError):
                lab.retention_admission(before, {**after, **mutation})
        for field in ('connected', 'running', 'queued'):
            with self.assertRaises(RuntimeError):
                lab.retention_admission({**before, field: 1}, after)

    def test_retention_failure_still_closes_host_and_cannot_complete(self):
        source = (ROOT / 'scripts/run-rpc-same-host-lab.py').read_text()
        begin = source.index('result["postRetention"] = review_retention()')
        failed = source.index('result["postRetention"] = {"status": "FAIL"', begin)
        stop = source.index('lab.write_private(directories["host"] / "stop.txt"', failed)
        check = source.index('need(result["postRetention"]["status"] == "PASS"', stop)
        complete = source.index('result["status"] = "COMPLETED_', check)
        self.assertLess(begin, failed)
        self.assertLess(failed, stop)
        self.assertLess(stop, check)
        self.assertLess(check, complete)

    def test_distinct_clean_harness_never_rebinds_admitted_product_source(self):
        product = {'commit': 'a' * 40, 'tree': 'b' * 40, 'diffSha256': 'c' * 64, 'status': ''}
        harness = {**product, 'commit': 'd' * 40, 'tree': 'e' * 40}
        context = {'root': str(lab.ROOT), 'source': product}
        lab.source_binding_admission(context, product, harness)
        for changed_context, changed_product, changed_harness in (
                ({**context, 'root': '/other-source'}, product, harness),
                (context, harness, harness),
                (context, {**product, 'status': ' M tracked.py'}, harness),
                (context, product, {**harness, 'status': '?? untracked.py'}),
                (context, {**product, 'diffSha256': 'f' * 64}, harness)):
            with self.assertRaises(RuntimeError):
                lab.source_binding_admission(changed_context, changed_product, changed_harness)

    def test_explicit_product_source_does_not_change_harness_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            product = Path(temporary).resolve()
            harness = lab.HARNESS_ROOT
            with patch.object(lab, 'ROOT', lab.ROOT), patch.object(lab, 'setup') as setup, \
                    patch.object(sys, 'argv', ['driver', '--owner-authorized-same-host', '--state', '/synthetic',
                                              '--mode', 'steady', '--source', str(product)]):
                self.assertEqual(lab.main(), 125)  # Real setup must exec; this is an offline argv check only.
                self.assertEqual(lab.ROOT, product)
                self.assertEqual(lab.HARNESS_ROOT, harness)
                self.assertEqual(setup.call_args.args[0].source, product)

    def test_noncanonical_or_symlinked_product_source_never_reaches_setup(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            link = base / 'linked-source'
            link.symlink_to(ROOT, target_is_directory=True)
            for source in ('relative', str(link), str(base / 'missing')):
                with patch.object(lab, 'setup') as setup, \
                        patch.object(sys, 'argv', ['driver', '--owner-authorized-same-host', '--state', '/synthetic',
                                                  '--mode', 'steady', '--source', source]), \
                        self.assertRaises((RuntimeError, FileNotFoundError)):
                    lab.main()
                setup.assert_not_called()

    def test_only_unaddressed_inactive_kernel_sit_fallback_is_tolerated(self):
        fallback = {'ifname': 'sit0', 'flags': ['NOARP'], 'link_type': 'sit', 'operstate': 'DOWN',
                    'linkinfo': {'info_kind': 'sit'}, 'address': '0.0.0.0'}
        value = topology()
        value['links'].append(fallback)
        value['addresses'].append({'ifname': 'sit0', 'addr_info': []})
        lab.topology_admission(**value)
        with patch.object(lab.sys, 'platform', 'linux'):
            lab.isolated_controller_admission(1, [{'ifname': 'lo'}, fallback], [])
        for mutation in ({'flags': ['NOARP', 'UP']}, {'operstate': 'UP'}, {'ifname': 'utun0'},
                         {'link_type': 'ether'}, {'address': '10.1.2.3'}):
            self.assertFalse(lab.inactive_kernel_fallback({**fallback, **mutation}))
        value['addresses'][-1]['addr_info'].append({'family': 'inet', 'local': '10.1.2.3', 'prefixlen': 24})
        with self.assertRaises(RuntimeError):
            lab.topology_admission(**value)

    def test_two_distinct_namespace_endpoints_and_explicit_virtual_scope(self):
        for role in ('host', 'client'):
            lab.topology_admission(**topology(role))
        self.assertNotEqual(lab.ADDRESSES['host'], lab.ADDRESSES['client'])
        self.assertIn('SAME_HOST_VIRTUAL_ETHERNET_NOT_PHYSICAL_LAN', lab.SCOPE)

    def test_foreign_duplicate_or_nonvirtual_links_are_rejected(self):
        for mutate in (lambda t: t['links'].append({'ifname': 'eth0'}),
                       lambda t: t['links'].append({'ifname': 'lo'}),
                       lambda t: t['links'][1].update(ifname='utun0'),
                       lambda t: t['links'][1]['linkinfo'].update(info_kind='bridge'),
                       lambda t: t['links'][1]['linkinfo'].clear(),
                       lambda t: t['links'][1].update(flags=['UP'])):
            value = topology()
            mutate(value)
            with self.assertRaises(RuntimeError):
                lab.topology_admission(**value)

    def test_default_gateway_foreign_subnet_or_wrong_interface_is_rejected(self):
        for mutate in (lambda t: t['routes'].append({'dst': 'default', 'gateway': '192.168.252.2'}),
                       lambda t: t['routes'][0].update(gateway='192.168.252.2'),
                       lambda t: t['routes'][0].update(dst='192.168.252.0/24'),
                       lambda t: t['routes'][0].update(dev='eth0'), lambda t: t['routes'].clear()):
            value = topology()
            mutate(value)
            with self.assertRaises(RuntimeError):
                lab.topology_admission(**value)

    def test_wrong_peer_alias_extra_address_or_global_ipv6_is_rejected(self):
        for mutate in (lambda t: t.update(role='client'),
                       lambda t: t['addresses'][1]['addr_info'][0].update(prefixlen=24),
                       lambda t: t['addresses'][1]['addr_info'].append(
                           {'local': '10.1.2.3', 'prefixlen': 24, 'family': 'inet'}),
                       lambda t: t['addresses'][1]['addr_info'][1].update(local='fd00::1'),
                       lambda t: t['addresses'][1]['addr_info'][1].update(local='2001:4860::1'),
                       lambda t: t['addresses'].append({'ifname': 'eth0', 'addr_info': []})):
            value = topology()
            mutate(value)
            with self.assertRaises(RuntimeError):
                lab.topology_admission(**value)

    def test_setup_requires_pid_one_and_no_existing_network(self):
        with patch.object(lab.sys, 'platform', 'linux'):
            lab.isolated_controller_admission(1, [{'ifname': 'lo'}], [])
            for pid, links, routes in ((2, [{'ifname': 'lo'}], []), (1, [{'ifname': 'eth0'}], []),
                                       (1, [{'ifname': 'lo'}], [{'dst': 'default'}])):
                with self.assertRaises(RuntimeError):
                    lab.isolated_controller_admission(pid, links, routes)
        with patch.object(lab.sys, 'platform', 'darwin'), self.assertRaises(RuntimeError):
            lab.isolated_controller_admission(1, [{'ifname': 'lo'}], [])

    def test_all_capability_sets_and_new_privilege_admission_are_closed(self):
        fields = {name: '0000000000000000' for name in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb')}
        fields['NoNewPrivs'] = '1'
        text = lambda value: '\n'.join(key + ':\t' + data for key, data in value.items())
        lab.capability_admission(text(fields))
        for name in fields:
            altered = {**fields, name: '0' if name == 'NoNewPrivs' else '0000000000000001'}
            with self.assertRaises(RuntimeError):
                lab.capability_admission(text(altered))

    def test_internal_stages_still_require_owner_acknowledgement(self):
        for stage in ([], ['--coordinate'], ['--worker', 'host']):
            with patch.object(sys, 'argv', ['driver', '--state', '/synthetic', '--mode', 'steady', *stage]), \
                    self.assertRaisesRegex(RuntimeError, 'authorization'):
                lab.main()

    def test_result_is_create_only_private_and_never_follows_a_symlink(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'result.json'
            lab.private_json(path, {'scope': lab.SCOPE})
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(path.read_text()), {'scope': lab.SCOPE})
            with self.assertRaises(FileExistsError):
                lab.private_json(path, {})
            link = Path(directory) / 'link.json'
            link.symlink_to(path)
            with self.assertRaises(FileExistsError):
                lab.private_json(link, {})

    def test_original_executor_and_full_inventory_precede_workload_gate_release(self):
        source = (ROOT / 'scripts/run-rpc-same-host-lab.py').read_text()
        self.assertIn('policy.control_inventory("linux-x64")', source)
        self.assertIn('runner.main([', source)
        self.assertIn('checker.validate(proof, code, purpose', source)
        self.assertLess(source.index('"Complete fresh native admission failed'), source.index('release("client")'))
        self.assertIn('lab.classpath(context["source"]["commit"])', source)
        self.assertIn('NoNewPrivs', source)
        self.assertIn('signal.pidfd_send_signal(worker["pidfd"], signal.SIGTERM)', source)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                self.assertNotIn(node.func.attr, ('kill', 'killpg', 'terminate', 'send_signal'))
        for forbidden in ('iptables', 'nftables', 'sysctl', 'StrictHostKeyChecking=no', 'LocalForward',
                          'isForbiddenLanInterface', 'organizationJvmTarget', 'RpcTestLink', 'mock'):
            # The docstring says "mock" to explicitly prohibit it; no executable references are allowed.
            literals = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
                        and isinstance(node.value, str) and node is not tree.body[0].value]
            with self.subTest(forbidden=forbidden):
                self.assertFalse(any(forbidden in literal for literal in literals))


if __name__ == '__main__':
    unittest.main(verbosity=2)
