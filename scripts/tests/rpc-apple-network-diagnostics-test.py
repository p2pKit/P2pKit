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
    if mode == 'multicast-path':
        return dict(common, **{k: False for k in d.MULTICAST_PATH_BOOLS},
                    **{k: 0 for k in d.MULTICAST_PATH_COUNTS})
    if mode in d.NETWORK_MODES:
        return dict(common, **{k: False for k in d.NETWORK_BOOLS | d.NETWORK_OBSERVATION_BOOLS}, **{k: 0 for k in d.NETWORK_NUMBERS},
                    bonjourEndpoint=mode == 'network-separate-txt', txtMatches=False, txtDeallocated=False)
    if mode == 'dns-resolve-txt':
        return dict(common, **{k: False for k in d.RESOLVE_BOOLS | d.RESOLVE_OBSERVATION_BOOLS},
                    **{k: 0 for k in d.RESOLVE_COUNTS | d.RESOLVE_CODES}, targetKind='EMPTY')
    return dict(common, **{k: 0 for k in d.DNS_FIELDS - {'referencesDeallocated'}}, referencesDeallocated=True)


class NetworkDiagnostics(unittest.TestCase):
    def test_multicast_path_policy_observation_is_not_delivery_or_product_admission(self):
        value = observation('multicast-path')
        value.update(hasIpv4=True, connectionCreated=True, waiting=True, pathObserved=True, localNetworkDenied=True,
                     stateCallbacks=2, errorDomain=1, errorCode=65, pathStatus=2, pathReason=3, cleanupComplete=True)
        row = d.observe(json.dumps(value).encode(), 'host', 'multicast-path', 1)
        self.assertTrue(row['observation']['localNetworkDenied'])
        self.assertFalse(row['executionAdmitted'])
        for change in (dict(probeExit=0), dict(pathObserved=False), dict(pathReason=0), dict(localNetworkDenied=1),
                       dict(stateCallbacks=True), dict(errorCode='private')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                d.validate_observation({**value, **change})
        ready = observation('multicast-path')
        ready.update(hasIpv4=True, connectionCreated=True, ready=True, pathObserved=True,
                     stateCallbacks=2, pathStatus=1, cleanupComplete=True, probeExit=0)
        self.assertFalse(d.observe(json.dumps(ready).encode(), 'simulator' if ready['simulator'] else 'host',
                                   'multicast-path', 0)['executionAdmitted'])
        for change in (dict(cleanupComplete=False), dict(pathObserved=False), dict(pathStatus=2),
                       dict(stateCallbacks=0), dict(failed=True), dict(errorCode=65)):
            with self.subTest(change=change), self.assertRaises(ValueError):
                d.validate_observation({**ready, **change})

    def test_multicast_path_uses_fixed_endpoint_and_original_nonroot_cancelled_lifetime(self):
        source = (ROOT / 'scripts/diagnostics/apple-bonjour-probe.c').read_text()
        body = source.split('static int multicast_path_probe(void) {', 1)[1].split('\nstruct dns_observation', 1)[0]
        for required in ('first_ipv4(&address)', 'nw_endpoint_create_host("224.0.0.251", "5353")',
                         'nw_parameters_set_local_endpoint(params, local)', 'nw_parameters_create_secure_udp',
                         'nw_path_unsatisfied_reason_local_network_denied', 'nw_connection_cancel(connection)',
                         'dispatch_group_wait', 'nw_connection_set_state_changed_handler(connection, NULL)'):
            self.assertIn(required, body)
        for forbidden in ('nw_connection_send', 'sendto(', 'system(', 'setuid(', 'setaudit_addr', 'tccutil'):
            self.assertNotIn(forbidden, body)
        self.assertLess(body.index('if (closing) return;'), body.index('nw_connection_copy_current_path(connection)'))

    def test_synthetic_service_names_do_not_leave_a_nul_before_the_random_suffix(self):
        source = (ROOT / 'scripts/diagnostics/apple-bonjour-probe.c').read_text()
        body = source.split('static void unique_name(char name[64]) {', 1)[1].split('\n}', 1)[0]
        self.assertIn('const size_t offset = sizeof(prefix) - 1;', body)
        self.assertIn('snprintf(name + offset + i * 2, 3, "%02x", random[i])', body)
        self.assertIn('sizeof(prefix) + 2 * sizeof(random) <= 64', body)
        self.assertIn('strlen(name) != offset + 2 * sizeof(random)', body)
        self.assertNotIn('name + 13', body)
        # A one-byte gap would hide the entropy; the original offset 13 was correct.
        prefix = b'p2pkit-probe-'
        self.assertEqual(len(prefix), 13)
        broken = prefix + b'\0' + b'ab' * 16 + b'\0'
        self.assertEqual(broken.split(b'\0')[0], prefix)
        self.assertEqual(len(prefix + b'ab' * 16), 45)

    def test_local_only_and_loopback_observations_are_not_coerced_into_lan_evidence(self):
        value = observation('dns-any')
        value.update(registrationCallbacks=1, browseCallbacks=1, targetAdds=1, localOnlyAdds=1, probeExit=0)
        row = d.observe(json.dumps(value).encode(), 'host', 'dns-any', 0)
        self.assertEqual(row['observation']['otherInterfaceAdds'], 0)
        self.assertFalse(row['executionAdmitted'])
        for patch in (dict(localOnlyAdds=0), dict(otherInterfaceAdds=1), dict(localOnlyAdds=True)):
            with self.assertRaises(ValueError):
                d.validate_observation({**value, **patch})
        value = observation('network-separate-txt')
        for patch in (dict(txtLocalOnly=1), dict(connectionLoopback='false'),
                      dict(resultInterfaces=0, resultLoopbackInterfaces=1)):
            with self.assertRaises(ValueError):
                d.validate_observation({**value, **patch})

    def test_network_differential_modes_are_closed_and_keep_all_failure_requirements(self):
        self.assertEqual(set(d.NETWORK_MODES), {'network', 'network-late', 'network-txt', 'network-default-domain',
                                             'network-legacy', 'network-production-shape', 'network-publish-txt',
                                             'network-query-empty-txt', 'network-txt-tcp-parameters', 'network-separate-txt'})
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

    def test_direct_dns_txt_resolution_cannot_pass_missing_data_wrong_port_or_failed_cleanup(self):
        value = observation('dns-resolve-txt')
        value.update({k: True for k in d.RESOLVE_BOOLS})
        value.update(probeExit=0, registrationCallbacks=1, resolveCallbacks=1, queryCallbacks=1,
                     targetKind='LOCAL_ABSOLUTE')
        d.observe(json.dumps(value).encode(), 'host', 'dns-resolve-txt', 0)
        for key in d.RESOLVE_BOOLS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate_observation({**value, key: False})
        for key in d.RESOLVE_CODES:
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate_observation({**value, key: -65570})
        for key in ('registrationCallbacks', 'resolveCallbacks', 'queryCallbacks'):
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate_observation({**value, key: 0})

    def test_dns_target_shape_is_closed_and_never_admits_a_nonlocal_target(self):
        value = observation('dns-resolve-txt')
        for kind in d.TARGET_KINDS:
            d.validate_observation({**value, 'targetKind': kind})
        for kind in ('private-host.example', '', True, 1, None):
            with self.assertRaises(ValueError):
                d.validate_observation({**value, 'targetKind': kind})
        with self.assertRaises(ValueError):
            d.validate_observation({**value, 'targetKind': 'OTHER_ABSOLUTE', 'localTarget': True})

    def test_separate_txt_control_requires_real_txt_bonjour_connection_and_queue_cleanup(self):
        value = observation('network-separate-txt')
        value.update({k: True for k in d.NETWORK_BOOLS | d.TXT_NETWORK_BOOLS})
        value.update(probeExit=0, registrationAdds=1, browseCallbacks=1, targetAdds=1, acceptedConnections=1,
                     txtQueryCallbacks=1)
        d.observe(json.dumps(value).encode(), 'host', 'network-separate-txt', 0)
        for key in d.NETWORK_BOOLS | d.TXT_NETWORK_BOOLS:
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate_observation({**value, key: False})
        for key in d.TXT_NETWORK_CODES:
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate_observation({**value, key: -65570})
        with self.assertRaises(ValueError):
            d.validate_observation({**value, 'txtQueryCallbacks': 0})
        source = (ROOT / 'scripts/diagnostics/apple-bonjour-probe.c').read_text()
        self.assertIn('DNSServiceSetDispatchQueue(value->txt_query, value->queue)', source)
        self.assertIn('DNSServiceRefDeallocate(value->txt_query)', source)
        self.assertIn('nw_endpoint_create_bonjour_service(name, type, "local.")', source)

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
        value.update(probeExit=0, registrationCallbacks=1, browseCallbacks=1, targetAdds=1, localOnlyAdds=1)
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
