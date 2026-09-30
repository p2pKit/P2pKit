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
    if mode == 'network':
        return dict(common, **{k: False for k in d.NETWORK_BOOLS}, **{k: 0 for k in d.NETWORK_NUMBERS})
    return dict(common, **{k: 0 for k in d.DNS_FIELDS - {'referencesDeallocated'}}, referencesDeallocated=True)


class NetworkDiagnostics(unittest.TestCase):
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
