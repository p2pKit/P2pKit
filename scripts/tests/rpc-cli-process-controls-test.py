#!/usr/bin/env python3
"""Offline parser/artifact/fault policy models; no sockets, JVM, signals or native receipts."""
import ctypes
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import signal
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / file)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


m = module('offline_cli_controls', 'rpc_cli_process_controls.py')
limits = module('offline_cli_limits', 'rpc_cli_child_limits.py')
SOURCE = 'a' * 40


class Inventory(unittest.TestCase):
    def result(self):
        return dict(schema=2, scope=m.SCOPE, sourceSha=SOURCE, result='PASS', fullCampaignQualified=False,
            caseSelection='all', unselectedCases=[], incompleteCases=[],
            physicalNetworkTested=False, headfulTested=False, liveChildCount=0,
            cases=[dict(case=name, passed=True) for name in m.case_inventory()])

    def test_closed_inventory_covers_each_fault_in_three_phases_three_times(self):
        names = m.case_inventory()
        self.assertEqual(len(names), 85)
        self.assertEqual(len(set(names)), len(names))
        self.assertEqual(len(m.launch_cases()), 29)
        for repeat in range(3):
            for phase in ('handshake', 'idle', 'transfer'):
                for fault in m.FAULTS:
                    self.assertIn(f'{phase}-{fault}-{repeat}', names)
            self.assertIn(f'transfer-sender-kill-{repeat}', names)
        self.assertEqual(m.assess_result(self.result(), SOURCE), self.result())

    def test_post_options_is_exactly_the_56_incomplete_cases_not_an_inherited_pass(self):
        selected = m.case_inventory('post-options')
        self.assertEqual(selected, m.case_inventory()[29:])
        self.assertEqual(len(selected), 56)
        self.assertEqual(selected[0], 'command-contract')
        value = self.result() | dict(caseSelection='post-options', unselectedCases=m.case_inventory()[:29],
            cases=[dict(case=name, passed=True) for name in selected])
        self.assertEqual(m.assess_result(value, SOURCE, 'post-options'), value)
        with self.assertRaises(RuntimeError):
            m.assess_result(value, SOURCE)  # A partial selection never satisfies the full default.
        for change in ({'caseSelection': 'all'}, {'unselectedCases': []}, {'cases': value['cases'][1:]},
                       {'cases': self.result()['cases']}, {'schema': 1}, {'incompleteCases': ['command-contract']}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.assess_result(value | change, SOURCE, 'post-options')

    def test_unrecognized_case_selection_fails_before_any_native_work(self):
        for selection in (None, True, 1, [], 'resume', 'post-options,all'):
            with self.subTest(selection=selection), self.assertRaises(RuntimeError):
                m.Campaign(None, None, selection)

    def test_remaining_selection_cannot_record_a_passed_option_or_skip_failed_first_case(self):
        campaign = m.Campaign.__new__(m.Campaign)
        campaign.selection, campaign.rows = 'post-options', []
        with patch.object(m, 'private_write') as write:
            for name in ('option-0', 'multi-peer-contract'):
                with self.subTest(name=name), self.assertRaises(RuntimeError):
                    campaign.passed(dict(case=name, passed=True))
            write.assert_not_called()

    def test_missing_duplicate_reordered_or_failed_cases_never_pass(self):
        for change in ('missing', 'duplicate', 'reordered', 'failed', 'integer'):
            result = self.result()
            if change == 'missing':
                result['cases'].pop()
            elif change == 'duplicate':
                result['cases'][-1] = result['cases'][0]
            elif change == 'reordered':
                result['cases'].reverse()
            else:
                result['cases'][0]['passed'] = False if change == 'failed' else 1
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.assess_result(result, SOURCE)

    def test_wrong_source_scope_or_overbroad_claim_is_not_qualification(self):
        for change in ({'sourceSha': 'b' * 40}, {'scope': 'FULL_CAMPAIGN'}, {'schema': True}, {'result': 'FAIL'},
                       {'fullCampaignQualified': True}, {'physicalNetworkTested': True}, {'headfulTested': True},
                       {'liveChildCount': 1}, {'liveChildCount': False}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.assess_result(self.result() | change, SOURCE)

    def test_oversized_option_does_not_contain_a_real_path_or_credential(self):
        rows = m.launch_cases()
        self.assertEqual(len(rows[-1][0][0]), 65537)
        self.assertTrue(rows[-1][1])
        self.assertTrue(all('/Users/' not in str(row) for row in rows))

    def test_java_classpath_memory_and_destination_are_explicit(self):
        with patch.dict(os.environ, JAVA_HOME='/OFFLINE/JDK'):
            argv = m.java_argv({'jars': [{'path': 'ONLY.jar'}]}, Path('/PRIVATE/home'), Path('/PRIVATE/tmp'))
        self.assertEqual(argv[0], '/OFFLINE/JDK/bin/java')
        self.assertIn('-Xmx256m', argv)
        self.assertIn('-XX:-MaxFDLimit', argv)
        self.assertEqual(argv[-1], m.MAIN)
        self.assertNotIn('shell', argv)


class Artifacts(unittest.TestCase):
    def test_selected_dispatch_keeps_all_non_option_cases_and_does_not_replay_options(self):
        for selection in m.SELECTIONS:
            with self.subTest(selection=selection), tempfile.TemporaryDirectory() as tmp:
                campaign = m.Campaign.__new__(m.Campaign)
                campaign.selection, campaign.source, campaign.directory = selection, SOURCE, Path(tmp)
                campaign.rows, campaign.children, campaign.peers, campaign.manifest = [], [], [], {'OFFLINE': True}
                campaign.relay, campaign.started, campaign.scope = None, time.monotonic(), Mock()
                groups = dict(options=m.case_inventory()[:29], commands=['command-contract'],
                    multi_peer_contract=['multi-peer-contract'],
                    admission_pressure=[f'admission-pressure-{n}' for n in range(3)],
                    transfers_and_storage=[f'transfer-storage-{n}' for n in range(3)],
                    faults=m.case_inventory()[37:])
                for method, cases in groups.items():
                    setattr(campaign, method, Mock(side_effect=lambda names=cases:
                        campaign.rows.extend(dict(case=name, passed=True) for name in names)))
                with patch.object(m, 'runtime_manifest', return_value=campaign.manifest), \
                        patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_bavail=8 * 1024**3, f_frsize=1)):
                    result = campaign.run()
                self.assertEqual(campaign.options.call_count, 1 if selection == 'all' else 0)
                self.assertEqual([r['case'] for r in result['cases']], m.case_inventory(selection))
                self.assertEqual(result['incompleteCases'], [])
                for method in groups.keys() - {'options'}:
                    getattr(campaign, method).assert_called_once_with()
                campaign.scope.close.assert_called_once_with()
                self.assertEqual(result, m.assess_result(result, SOURCE, selection))

    def test_focused_xml_requires_exact_source_methods_and_no_failure_or_extra_suite(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'ROOT', Path(tmp).resolve()):
            source = m.ROOT / 'samples/p2p-sample-desktop/src/test/kotlin/dev/p2pkit/sample/desktop'
            reports = m.ROOT / 'samples/p2p-sample-desktop/build/test-results/test'
            source.mkdir(parents=True)
            reports.mkdir(parents=True)
            for name in m.CLASSES:
                (source / (name + '.kt')).write_text('@Test\nfun one() {}\n')
                path = reports / ('TEST-dev.p2pkit.sample.desktop.' + name + '.xml')
                path.write_text('<testsuite name="dev.p2pkit.sample.desktop.' + name +
                    '" failures="0" errors="0" skipped="0"><testcase name="one()"/></testsuite>')
            self.assertEqual({k: v['passed'] for k, v in m.focused_tests().items()}, dict.fromkeys(m.CLASSES, 1))
            original = path.read_text()
            path.write_text(original.replace('<testcase name="one()"/>', '<testcase name="one()"><failure/></testcase>'))
            with self.assertRaises(RuntimeError):
                m.focused_tests()
            path.write_text(original)
            (reports / 'TEST-extra.xml').write_text('<testsuite/>')
            with self.assertRaises(RuntimeError):
                m.focused_tests()

    def test_campaign_failure_is_saved_and_observation_scope_is_closed_without_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = m.Campaign.__new__(m.Campaign)
            campaign.source, campaign.directory = SOURCE, Path(tmp)
            campaign.selection = 'all'
            campaign.rows, campaign.peers, campaign.children = [], [], []
            campaign.relay, campaign.started, campaign.scope = None, time.monotonic(), Mock()
            with patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_bavail=0, f_frsize=4096)), \
                    self.assertRaises(RuntimeError):
                campaign.run()
            campaign.scope.close.assert_called_once_with()
            value = json.loads((Path(tmp) / 'result.json').read_bytes())
            self.assertEqual(value['result'], 'FAIL')
            self.assertEqual(value['failure']['type'], 'RuntimeError')
            self.assertFalse(value['fullCampaignQualified'])
            self.assertEqual(value['cases'], [])
            self.assertEqual(value['unselectedCases'], [])
            self.assertEqual(value['incompleteCases'], m.case_inventory())
            self.assertFalse((Path(tmp) / 'synthetic-49m.bin').exists())

    def test_remaining_failure_retains_failed_first_case_and_all_55_unstarted_cases(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = m.Campaign.__new__(m.Campaign)
            campaign.source, campaign.directory, campaign.selection = SOURCE, Path(tmp), 'post-options'
            campaign.rows, campaign.peers, campaign.children = [], [], []
            campaign.relay, campaign.started, campaign.scope = None, time.monotonic(), Mock()
            campaign.options, campaign.commands = Mock(), Mock(side_effect=RuntimeError('OFFLINE startup failure'))
            with patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_bavail=8 * 1024**3, f_frsize=1)), \
                    self.assertRaisesRegex(RuntimeError, 'OFFLINE startup failure'):
                campaign.run()
            campaign.options.assert_not_called()
            campaign.commands.assert_called_once_with()
            campaign.scope.close.assert_called_once_with()
            value = json.loads((Path(tmp) / 'result.json').read_bytes())
            self.assertEqual(value['result'], 'FAIL')
            self.assertEqual(value['cases'], [])
            self.assertEqual(value['incompleteCases'], m.case_inventory()[29:])
            self.assertEqual(value['unselectedCases'], m.case_inventory()[:29])

    def make_export(self, path, *, summary_source=SOURCE, event_source=SOURCE, session='case', bad_checksum=False):
        summary = dict(gitCommitSha=summary_source, testSessionId=session, platform='jvm-cli',
                       protocolVersion='secure-v2', eventCount=1)
        event = dict(gitCommitSha=event_source, testSessionId='case', platform='jvm-cli', index=1,
                     eventName='application.shutdown')
        files = {'summary.json': json.dumps(summary).encode(), 'events.jsonl': json.dumps(event).encode() + b'\n',
                 'events.txt': b'OFFLINE\n', 'manual-evidence-required.txt': b'No native claim\n'}
        hashes = '\n'.join(hashlib.sha256(data).hexdigest() + '  ' + name for name, data in files.items()) + '\n'
        files['checksums.sha256'] = b'0' * 64 if bad_checksum else hashes.encode()
        with zipfile.ZipFile(path, 'x') as archive:
            for name, data in files.items():
                archive.writestr(name, data)

    def test_real_export_shape_has_summary_provenance_not_a_fabricated_environment_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'offline.zip'
            self.make_export(path)
            value = m.inspect_export(path, SOURCE, 'case')
            self.assertEqual(value['sha256'], m.digest(path))
            self.assertEqual(value['eventNames'], ['application.shutdown'])
            self.assertEqual(value['decodedEventCount'], 1)

    def test_crossed_source_session_and_checksums_fail_closed(self):
        for kwargs in ({'summary_source': 'b' * 40}, {'event_source': 'b' * 40}, {'session': 'other'}, {'bad_checksum': True}):
            with self.subTest(kwargs=kwargs), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'offline.zip'
                self.make_export(path, **kwargs)
                with self.assertRaises(RuntimeError):
                    m.inspect_export(path, SOURCE, 'case')

    def test_linked_export_is_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'offline.zip'
            self.make_export(path)
            link = Path(tmp) / 'link.zip'
            link.symlink_to(path)
            with self.assertRaises(RuntimeError):
                m.inspect_export(link, SOURCE, 'case')

    def test_unsafe_or_unbounded_zip_members_are_rejected_before_read(self):
        for name, size in (('../escape', 1), ('safe.json', 17 * 1024**2)):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / 'offline.zip'
                path.write_bytes(b'OFFLINE')
                member = zipfile.ZipInfo(name)
                member.file_size = size
                archive = Mock()
                archive.__enter__ = Mock(return_value=archive)
                archive.__exit__ = Mock(return_value=False)
                archive.infolist.return_value = [member]
                with patch.object(m.zipfile, 'ZipFile', return_value=archive), self.assertRaises(RuntimeError):
                    m.inspect_export(path, SOURCE, 'case')
                archive.read.assert_not_called()

    def test_runtime_manifest_binds_every_new_jar_and_rejects_links(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'ROOT', Path(tmp).resolve()):
            directory = m.ROOT / 'samples/p2p-sample-desktop/build/install/p2p-sample-desktop/lib'
            directory.mkdir(parents=True)
            jar = directory / 'sample.jar'
            jar.write_bytes(b'OFFLINE NOT AN APPLICATION')
            first = m.runtime_manifest(SOURCE)
            jar.write_bytes(b'CHANGED OFFLINE FIXTURE')
            self.assertNotEqual(first, m.runtime_manifest(SOURCE))
            (directory / 'alias.jar').symlink_to(jar)
            with self.assertRaises(RuntimeError):
                m.runtime_manifest(SOURCE)

    def test_runtime_rejects_linked_parent_and_empty_distribution(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(m, 'ROOT', Path(tmp).resolve()):
            directory = m.ROOT / 'samples/p2p-sample-desktop/build/install/p2p-sample-desktop/lib'
            directory.mkdir(parents=True)
            with self.assertRaises(RuntimeError):
                m.runtime_manifest(SOURCE)
            (directory / 'one.jar').write_bytes(b'OFFLINE')
            linked = m.ROOT / 'linked'
            linked.symlink_to(m.ROOT, target_is_directory=True)
            with patch.object(m, 'ROOT', linked), self.assertRaises(RuntimeError):
                m.runtime_manifest(SOURCE)

    def test_private_reports_never_replace_existing_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            m.private_write(path, {'first': True})
            before = path.read_bytes()
            with self.assertRaises(FileExistsError):
                m.private_write(path, {'second': True})
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


class FaultPolicy(unittest.TestCase):
    def identity(self):
        owner = dict(pid=10, uniqueId=20, uid=501)
        child = dict(pid=11, parentPid=10, parentUniqueId=20, uid=501, realUid=501, live=True, pidVersion=3)
        return owner, child

    def peer(self):
        owner, child = self.identity()
        peer = m.Peer.__new__(m.Peer)
        scope = SimpleNamespace(_observe=Mock(return_value=child), proc=SimpleNamespace(proc_signal_with_audittoken=Mock(return_value=0)))
        peer.campaign = SimpleNamespace(owner=owner, scope=scope)
        peer.identity, peer.token = child, (ctypes.c_uint * 8)()
        peer.events = []
        return peer, scope

    def test_only_direct_same_account_live_child_lifetime_can_be_faulted(self):
        owner, child = self.identity()
        m.direct_child(child, owner)
        for change in ({'parentPid': 12}, {'parentUniqueId': 99}, {'uid': 0}, {'realUid': 0}, {'live': False}, {'pid': 10}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.direct_child(child | change, owner)

    def test_only_kernel_opaque_token_is_used_for_each_allowed_fault(self):
        for name, number in (('term', signal.SIGTERM), ('kill', signal.SIGKILL), ('stop', signal.SIGSTOP),
                             ('cont', signal.SIGCONT), ('hup', signal.SIGHUP)):
            peer, scope = self.peer()
            peer.fault(name)
            self.assertEqual(scope.proc.proc_signal_with_audittoken.call_args.args[1], number)
            self.assertEqual(peer.events[0]['signal'], name)

    def test_unknown_fault_never_observes_or_signals_a_process(self):
        peer, scope = self.peer()
        with self.assertRaises(RuntimeError):
            peer.fault('killall')
        scope._observe.assert_not_called()
        scope.proc.proc_signal_with_audittoken.assert_not_called()

    def test_exec_changed_target_is_not_signaled_or_reacquired(self):
        peer, scope = self.peer()
        scope._observe.return_value = peer.identity | {'pidVersion': 4}
        with self.assertRaises(RuntimeError):
            peer.fault('term')
        scope.proc.proc_signal_with_audittoken.assert_not_called()

    def test_signal_failure_is_retained_and_has_no_pid_fallback(self):
        peer, scope = self.peer()
        scope.proc.proc_signal_with_audittoken.return_value = 1
        with patch.object(m.os, 'kill') as kill, patch.object(m.os, 'killpg') as group, self.assertRaises(RuntimeError):
            peer.fault('term')
        kill.assert_not_called()
        group.assert_not_called()
        scope.proc.proc_signal_with_audittoken.assert_called_once()

    def test_child_limits_only_lower_the_soft_value_and_preserve_hard_value(self):
        for before, cap, expected in (((1024, 2048), 256, (256, 2048)), ((64, 128), 256, (64, 128)),
                                      ((resource.RLIM_INFINITY, resource.RLIM_INFINITY), 512,
                                       (512, resource.RLIM_INFINITY))):
            self.assertEqual(limits.lowered(before, cap), expected)
        for cap in (0, -1, True, '256'):
            with self.assertRaises(RuntimeError):
                limits.lowered((1024, 2048), cap)


class RelayModel(unittest.TestCase):
    def fixture(self, data=b'unchanged-wire-bytes', limit=3):
        relay = m.Relay.__new__(m.Relay)
        relay.client, relay.server, relay.listener = Mock(), Mock(), Mock()
        relay.buffers = {relay.client: bytearray(), relay.server: bytearray(data)}
        relay.forwarded, relay.limit = [0, 0], limit
        relay.accepted, relay.closed = True, False
        relay.server.send.side_effect = len
        relay.client.send.side_effect = len
        return relay

    def test_phase_gate_forwards_exact_prefix_then_preserves_queued_bytes(self):
        relay = self.fixture()
        with patch.object(m.select, 'select', return_value=([], [relay.server], [])):
            relay.pump(0)
        relay.server.send.assert_called_once_with(b'unc')
        self.assertEqual(relay.forwarded, [3, 0])
        self.assertEqual(relay.buffers[relay.server], b'hanged-wire-bytes')

    def test_releasing_gate_forwards_remaining_original_bytes_without_rewriting(self):
        relay = self.fixture(limit=None)
        with patch.object(m.select, 'select', return_value=([], [relay.server], [])):
            relay.pump(0)
        relay.server.send.assert_called_once_with(b'unchanged-wire-bytes')
        self.assertEqual(relay.buffers[relay.server], b'')

    def test_reverse_bytes_are_never_held_by_client_phase_gate(self):
        relay = self.fixture(limit=0)
        relay.buffers[relay.client] = bytearray(b'response')
        with patch.object(m.select, 'select', return_value=([], [relay.client], [])):
            relay.pump(0)
        relay.client.send.assert_called_once_with(b'response')
        self.assertEqual(relay.forwarded, [0, 8])

    def test_relay_enforces_byte_budget(self):
        relay = self.fixture(limit=None)
        relay.forwarded = [64 * 1024**2, 0]
        with patch.object(m.select, 'select', return_value=([], [relay.server], [])), self.assertRaises(RuntimeError):
            relay.pump(0)

    def test_reset_closes_only_its_three_owned_sockets(self):
        relay = self.fixture()
        relay.server.send.side_effect = ConnectionResetError('OFFLINE')
        with patch.object(m.select, 'select', return_value=([], [relay.server], [])):
            relay.pump(0)
        self.assertTrue(relay.closed)
        for connection in (relay.client, relay.server, relay.listener):
            connection.close.assert_called_once()

    def test_invalid_observed_port_never_opens_a_socket(self):
        for port in (True, 0, 65536, '1234'):
            with patch.object(m.socket, 'socket') as create, self.assertRaises(RuntimeError):
                m.Relay(port)
            create.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
