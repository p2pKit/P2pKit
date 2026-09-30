#!/usr/bin/env python3
"""Offline schema/privacy and fail-closed controls; not native/Bonjour execution."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_apple_network_diagnostics as d


def observation(mode, simulator=False):
    common = dict(schema=1, mode=mode, simulator=simulator, unprivileged=True, elapsedMillis=10000, probeExit=1)
    if mode == 'bsd':
        return dict(common, interfaces=[dict(privateIpv4=True, pointToPoint=False, setupErrno=0,
                                            sendErrno=65, closeErrno=0, sendReturned=False)])
    if mode in d.NETWORK_MODES:
        return dict(common, **{k: False for k in d.NETWORK_BOOLS}, **{k: 0 for k in d.NETWORK_NUMBERS})
    return dict(common, **{k: 0 for k in d.DNS_FIELDS - {'referencesDeallocated'}}, referencesDeallocated=True)


class NetworkDiagnostics(unittest.TestCase):
    def test_network_differential_modes_are_closed_and_keep_all_failure_requirements(self):
        self.assertEqual(set(d.NETWORK_MODES), {'network', 'network-late', 'network-txt', 'network-default-domain',
                                             'network-legacy', 'network-production-shape'})
        source = (ROOT / 'scripts/diagnostics/apple-bonjour-probe.c').read_text()
        for mode in d.NETWORK_MODES:
            self.assertIn('"' + mode + '"', source)
            value = observation(mode)
            d.observe(json.dumps(value).encode(), 'host', mode, 1)
            with self.assertRaises(ValueError):
                d.observe(json.dumps({**value, 'probeExit': 0}).encode(), 'host', mode, 0)
        for function in ('nw_txt_record_set_key', 'nw_advertise_descriptor_set_txt_record_object',
                         'nw_browse_descriptor_set_include_txt_record'):
            self.assertIn(function, source)
        self.assertNotIn('network-any-config', d.MODES)

    def test_cancelled_path_monitor_uses_its_nonnullable_callback_contract(self):
        source = (ROOT / 'scripts/diagnostics/apple-bonjour-probe.c').read_text()
        self.assertNotIn('nw_path_monitor_set_update_handler(monitor, NULL)', source)
        self.assertIn('nw_path_monitor_set_update_handler(monitor, ^(nw_path_t unused) { (void)unused; });', source)
        self.assertLess(source.index('nw_path_monitor_cancel(monitor)'),
                        source.index('nw_path_monitor_set_update_handler(monitor, ^(nw_path_t unused)'))
        raw = (str(ROOT / 'scripts/diagnostics/apple-bonjour-probe.c') +
               ':299:1: error: null passed to a callee that requires a non-null argument [-Werror,-Wnonnull]\n').encode()
        row = d.compiler_observation(raw, ROOT / 'scripts/diagnostics/apple-bonjour-probe.c')
        self.assertEqual(row['diagnostics'][0]['category'], 'NULLABILITY')

    def test_compiler_failures_export_only_real_source_locations_and_source_symbols(self):
        source = ROOT / 'scripts/diagnostics/apple-bonjour-probe.c'
        raw = (str(source) + ":50:1: error: incompatible pointer types 'DNSServiceRef' private-value\n" +
               "/private/other.c:12:1: error: private diagnostic\n").encode()
        value = d.compiler_observation(raw, source)
        self.assertEqual(value['diagnostics'], [dict(line=50, column=1, severity='error',
                         category='INCOMPATIBLE_POINTER', symbols=['DNSServiceRef'])])
        self.assertNotIn('private', json.dumps(value))
        for field, bad in (('line', 0), ('line', 99999), ('column', 99999), ('severity', 'private'),
                           ('category', 'private'), ('symbols', ['private-key']), ('symbols', 'private')):
            changed = copy.deepcopy(value)
            changed['diagnostics'][0][field] = bad
            with self.assertRaises(ValueError):
                d.validate_compiler(changed, source)

    def test_compiler_missing_raw_output_and_unknown_messages_never_become_a_pass(self):
        source = ROOT / 'scripts/diagnostics/apple-bonjour-probe.c'
        value = d.compiler_observation(b'', source)
        self.assertEqual(value['diagnostics'], [])
        self.assertNotIn('PASS', json.dumps(value))
        raw = (str(source) + ':50:1: error: private-value\n').encode()
        value = d.compiler_observation(raw, source)
        self.assertEqual(value['diagnostics'][0]['category'], 'OTHER')
        self.assertEqual(value['diagnostics'][0]['symbols'], [])

    def test_native_and_simulator_observations_remain_distinct_and_unadmitted(self):
        for context in d.CONTEXTS:
            for mode in d.MODES:
                raw = json.dumps(observation(mode, context == 'simulator')).encode()
                row = d.observe(raw, context, mode, 1)
                self.assertFalse(row['executionAdmitted'])
                d.validate({context + '-' + mode: row})
                with self.assertRaises(ValueError):
                    d.observe(raw, 'host' if context == 'simulator' else 'simulator', mode, 1)

    def test_no_arbitrary_fields_names_addresses_or_payloads_can_leave_probe(self):
        for mode in d.MODES:
            for key in ('address', 'name', 'interface', 'message', 'payload', 'identity', 'secret'):
                value = observation(mode)
                value[key] = 'private'
                with self.assertRaises(ValueError):
                    d.observe(json.dumps(value).encode(), 'host', mode, 1)
        value = observation('bsd')
        value['interfaces'][0]['name'] = 'private'
        with self.assertRaises(ValueError):
            d.validate_observation(value)

    def test_types_bounds_and_privilege_are_not_coerced(self):
        for key, bad in (('schema', True), ('schema', 2), ('mode', 'unknown'), ('simulator', 0),
                         ('unprivileged', False), ('unprivileged', 1), ('elapsedMillis', -1),
                         ('elapsedMillis', 60001), ('elapsedMillis', True), ('probeExit', 4)):
            with self.subTest(key=key, bad=bad), self.assertRaises(ValueError):
                d.validate_observation({**observation('network'), key: bad})

    def test_duplicate_keys_and_excessive_raw_data_are_rejected(self):
        raw = json.dumps(observation('bsd')).encode()
        for data in (raw.replace(b'{', b'{"schema":1,', 1), raw + b' ' * d.LIMIT, b'', b'not json'):
            with self.assertRaises(ValueError):
                d.observe(data, 'host', 'bsd', 1)

    def test_native_exit_and_compiled_platform_must_match_receipt_context(self):
        raw = json.dumps(observation('dns-any')).encode()
        for context, mode, code in (('simulator', 'dns-any', 1), ('host', 'dns-local', 1),
                                    ('host', 'dns-any', 0), ('host', 'dns-any', True)):
            with self.assertRaises(ValueError):
                d.observe(raw, context, mode, code)

    def test_false_zero_exit_cannot_claim_missing_multicast_or_bonjour_success(self):
        for mode in d.MODES:
            value = observation(mode)
            value['probeExit'] = 0
            with self.assertRaises(ValueError):
                d.validate_observation(value)
        value = observation('bsd')
        value.update(probeExit=0, interfaces=[])
        with self.assertRaises(ValueError):
            d.validate_observation(value)

    def test_actual_policy_denial_is_retained_not_converted_to_a_product_verdict(self):
        value = observation('dns-any')
        value.update(registrationCallbacks=1, registrationCode=-65570)
        row = d.observe(json.dumps(value).encode(), 'host', 'dns-any', 1)
        self.assertEqual(row['observation']['registrationCode'], -65570)
        self.assertEqual(row['observation']['probeExit'], 1)
        self.assertFalse(row['executionAdmitted'])
        value = observation('network')
        value.update(hasIpv4=True, listenerReady=True, browserReady=True, cleanupComplete=True,
                     connectionPathReason=3, connectionDomain=1, connectionCode=65)
        d.observe(json.dumps(value).encode(), 'host', 'network', 1)

    def test_local_only_control_cannot_be_relabelled_as_network_discovery(self):
        value = observation('dns-local')
        value.update(probeExit=0, registrationCallbacks=1, browseCallbacks=1, targetAdds=1)
        row = d.observe(json.dumps(value).encode(), 'host', 'dns-local', 0)
        d.validate({'host-dns-local': row})
        for label in ('host-dns-any', 'host-network', 'simulator-dns-local', 'product-pass'):
            with self.assertRaises(ValueError):
                d.validate({label: row})
        self.assertFalse(row['executionAdmitted'])

    def test_outer_observations_reject_private_metadata_and_admission_flags(self):
        row = d.observe(json.dumps(observation('bsd')).encode(), 'host', 'bsd', 1)
        for change in (dict(executionAdmitted=True), dict(sha256='private'), dict(bytes=True), dict(secret='private')):
            with self.assertRaises(ValueError):
                d.validate({'host-bsd': {**row, **change}})
        for bad in (None, [], {'private': row}):
            with self.assertRaises(ValueError):
                d.validate(bad)

    def test_failed_or_incomplete_cleanup_cannot_be_a_successful_native_control(self):
        value = observation('network')
        value.update({k: True for k in d.NETWORK_BOOLS})
        value.update(probeExit=0, registrationAdds=1, browseCallbacks=1, targetAdds=1, acceptedConnections=1)
        d.validate_observation(value)
        value['cleanupComplete'] = False
        with self.assertRaises(ValueError):
            d.validate_observation(value)
        value = observation('dns-local')
        value.update(probeExit=0, registrationCallbacks=1, targetAdds=1, referencesDeallocated=False)
        with self.assertRaises(ValueError):
            d.validate_observation(value)

    def test_interface_enumeration_never_allows_unbounded_or_inconsistent_results(self):
        value = observation('bsd')
        for patch in (dict(sendReturned=True), dict(sendErrno=-1), dict(closeErrno=256), dict(privateIpv4=1)):
            changed = copy.deepcopy(value)
            changed['interfaces'][0].update(patch)
            with self.assertRaises(ValueError):
                d.validate_observation(changed)
        value['interfaces'] *= 65
        with self.assertRaises(ValueError):
            d.validate_observation(value)

    def test_probe_source_does_not_grant_permissions_or_mutate_interfaces(self):
        source = (ROOT / 'scripts/diagnostics/apple-bonjour-probe.c').read_text()
        for required in ('getuid() == 0', 'getuid() != geteuid()', 'getgid() != getegid()',
                         'IP_MULTICAST_IF', 'kDNSServiceInterfaceIndexLocalOnly', 'kDNSServiceInterfaceIndexAny',
                         'DNSServiceProcessResult', 'DNSServiceRefDeallocate', 'nw_path_get_unsatisfied_reason',
                         'nw_listener_set_advertised_endpoint_changed_handler', 'nw_browser_cancel',
                         'nw_connection_cancel', 'dispatch_group_wait', 'nw_path_monitor_cancel'):
            self.assertIn(required, source)
        for forbidden in ('setuid(', 'setgid(', 'setaudit_addr', 'system(', 'exec(', 'popen(', 'ioctl(',
                          'tccutil', 'osascript', 'csrutil', 'launchctl', 'sudo'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
