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
    def result(self, selection='all', first_case=None):
        selected = m.case_inventory(selection, first_case)
        return dict(schema=3, scope=m.SCOPE, sourceSha=SOURCE, result='PASS', fullCampaignQualified=False,
            caseSelection=selection, firstCase=first_case,
            unselectedCases=[name for name in m.case_inventory() if name not in selected], incompleteCases=[],
            physicalNetworkTested=False, headfulTested=False, liveChildCount=0,
            cases=[dict(case=name, passed=True) for name in selected])

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

    def test_every_continuation_is_an_exact_ordered_suffix_without_inherited_passes(self):
        names = m.case_inventory('post-options')
        for index, name in enumerate(names):
            with self.subTest(first_case=name):
                selected = m.case_inventory('post-options', name)
                self.assertEqual(selected, names[index:])
                result = self.result('post-options', name)
                self.assertEqual(m.assess_result(result, SOURCE, 'post-options', name), result)
                self.assertEqual(result['unselectedCases'], m.case_inventory()[:29 + index])
                with self.assertRaises(RuntimeError):
                    m.assess_result(result, SOURCE, 'post-options')
        self.assertEqual(len(m.case_inventory('post-options', 'admission-pressure-0')), 54)

    def test_invalid_suffix_or_full_inventory_continuation_fails_before_native_work(self):
        for selection, first in [('all', 'command-contract'), ('all', 'option-0')] + [
                ('post-options', name) for name in (True, 1, [], '', 'option-28', 'admission-pressure-3',
                                                   'admission-pressure-0,transfer-storage-0')]:
            with self.subTest(selection=selection, first=first), self.assertRaises(RuntimeError):
                m.Campaign(None, None, selection, first)

    def test_result_cannot_substitute_or_omit_suffix_or_promote_an_old_schema(self):
        result = self.result('post-options', 'admission-pressure-0')
        for change in ({'firstCase': None}, {'firstCase': 'admission-pressure-1'}, {'firstCase': True},
                       {'schema': 2}, {'unselectedCases': m.case_inventory()[:29]},
                       {'cases': self.result('post-options')['cases']}, {'cases': result['cases'][1:]}):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.assess_result(result | change, SOURCE, 'post-options', 'admission-pressure-0')
        for value, first in ((self.result(), None), (result, 'admission-pressure-0')):
            del value['firstCase']
            with self.assertRaises(RuntimeError):
                m.assess_result(value, SOURCE, value['caseSelection'], first)

    def test_remaining_selection_cannot_record_a_passed_option_or_skip_failed_first_case(self):
        campaign = m.Campaign.__new__(m.Campaign)
        campaign.selection, campaign.rows = 'post-options', []
        campaign.selected = m.case_inventory(campaign.selection)
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
        for selection, first in (('all', None), ('post-options', None), ('post-options', 'admission-pressure-0'),
                                 ('post-options', 'transfer-storage-1'), ('post-options', 'idle-kill-1')):
            with self.subTest(selection=selection, first=first), tempfile.TemporaryDirectory() as tmp:
                campaign = m.Campaign.__new__(m.Campaign)
                campaign.selection, campaign.source, campaign.directory = selection, SOURCE, Path(tmp)
                campaign.first_case, campaign.selected = first, m.case_inventory(selection, first)
                campaign.rows, campaign.children, campaign.peers, campaign.manifest = [], [], [], {'OFFLINE': True}
                campaign.relay, campaign.started, campaign.scope = None, time.monotonic(), Mock()
                groups = dict(options=m.case_inventory()[:29], commands=['command-contract'],
                    multi_peer_contract=['multi-peer-contract'],
                    admission_pressure=[f'admission-pressure-{n}' for n in range(3)],
                    transfers_and_storage=[f'transfer-storage-{n}' for n in range(3)],
                    faults=m.case_inventory()[37:])
                for method, cases in groups.items():
                    setattr(campaign, method, Mock(side_effect=lambda names=cases:
                        campaign.rows.extend(dict(case=name, passed=True) for name in names if name in campaign.selected)))
                with patch.object(m, 'runtime_manifest', return_value=campaign.manifest), \
                        patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_bavail=8 * 1024**3, f_frsize=1)):
                    result = campaign.run()
                self.assertEqual(campaign.options.call_count, 1 if selection == 'all' else 0)
                self.assertEqual([r['case'] for r in result['cases']], m.case_inventory(selection, first))
                self.assertEqual(result['incompleteCases'], [])
                for method in ('commands', 'multi_peer_contract'):
                    self.assertEqual(getattr(campaign, method).call_count, int(groups[method][0] in campaign.selected))
                for method in ('admission_pressure', 'transfers_and_storage', 'faults'):
                    getattr(campaign, method).assert_called_once_with()
                campaign.scope.close.assert_called_once_with()
                self.assertEqual(result, m.assess_result(result, SOURCE, selection, first))

    def test_case_loops_do_not_launch_peers_for_a_previously_completed_prefix(self):
        for method, first, expected in (('admission_pressure', 'admission-pressure-1', 'admission-pressure-1-b'),
                ('admission_pressure', 'transfer-storage-0', None),
                ('transfers_and_storage', 'transfer-storage-2', 'transfer-storage-2-a'),
                ('transfers_and_storage', 'handshake-term-0', None),
                ('faults', 'idle-kill-1', 'idle-kill-1-a')):
            campaign = m.Campaign.__new__(m.Campaign)
            campaign.selected = m.case_inventory('post-options', first)
            with self.subTest(method=method, first=first), patch.object(m, 'Peer', side_effect=RuntimeError('OFFLINE peer')) as peer:
                if expected is None:
                    getattr(campaign, method)()
                    peer.assert_not_called()
                else:
                    with self.assertRaisesRegex(RuntimeError, 'OFFLINE peer'):
                        getattr(campaign, method)()
                    peer.assert_called_once()
                    self.assertEqual(peer.call_args.args[1], expected)

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
            campaign.first_case, campaign.selected = None, m.case_inventory()
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
            campaign.first_case, campaign.selected = None, m.case_inventory('post-options')
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

    def test_suffix_failure_retains_failed_and_unstarted_cases_without_replaying_contracts(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = m.Campaign.__new__(m.Campaign)
            campaign.source, campaign.directory, campaign.selection = SOURCE, Path(tmp), 'post-options'
            campaign.first_case = 'admission-pressure-0'
            campaign.selected = m.case_inventory(campaign.selection, campaign.first_case)
            campaign.rows, campaign.peers, campaign.children = [], [], []
            campaign.relay, campaign.started, campaign.scope = None, time.monotonic(), Mock()
            campaign.options, campaign.commands, campaign.multi_peer_contract = Mock(), Mock(), Mock()
            campaign.admission_pressure = Mock(side_effect=RuntimeError('OFFLINE child failure'))
            with patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_bavail=8 * 1024**3, f_frsize=1)), \
                    self.assertRaisesRegex(RuntimeError, 'OFFLINE child failure'):
                campaign.run()
            for method in ('options', 'commands', 'multi_peer_contract'):
                getattr(campaign, method).assert_not_called()
            campaign.admission_pressure.assert_called_once_with()
            campaign.scope.close.assert_called_once_with()
            value = json.loads((Path(tmp) / 'result.json').read_bytes())
            self.assertEqual(value['result'], 'FAIL')
            self.assertEqual(value['cases'], [])
            self.assertEqual(value['incompleteCases'], m.case_inventory()[31:])
            self.assertEqual(value['unselectedCases'], m.case_inventory()[:31])

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

    def test_darwin_ceiling_only_lowers_hard_limit_and_never_raises_either_limit(self):
        for before, ceiling, expected in (((2666, 4000), 2666, (512, 2666)),
                                         ((64, 128), 2666, (64, 128)),
                                         ((512, 1024), 256, (256, 256)),
                                         ((resource.RLIM_INFINITY, resource.RLIM_INFINITY), 2666, (512, 2666))):
            with self.subTest(before=before, ceiling=ceiling):
                self.assertEqual(limits.lowered(before, 512, ceiling), expected)
        for ceiling in (True, 0, -1, '2666'):
            with self.subTest(ceiling=ceiling), self.assertRaises(RuntimeError):
                limits.lowered((2666, 4000), 512, ceiling)

    def test_kernel_ceiling_query_is_fixed_read_only_and_validates_status_size_and_value(self):
        def query(_name, value, size, new, new_size):
            self.assertIsNone(new)
            self.assertEqual(new_size, 0)
            ctypes.cast(value, ctypes.POINTER(ctypes.c_int)).contents.value = supplied
            ctypes.cast(size, ctypes.POINTER(ctypes.c_size_t)).contents.value = returned_size
            return status
        for status, returned_size, supplied in ((0, ctypes.sizeof(ctypes.c_int), 2666), (-1, 4, 2666),
                                                (0, 8, 2666), (0, 4, 0), (0, 4, -1)):
            system = Mock(sysctlbyname=Mock(side_effect=query))
            with self.subTest(status=status, size=returned_size, value=supplied), \
                    patch.object(limits.sys, 'platform', 'darwin'), patch.object(limits.ctypes, 'CDLL', return_value=system) as library:
                if status == 0 and returned_size == ctypes.sizeof(ctypes.c_int) and supplied > 0:
                    self.assertEqual(limits.darwin_process_ceiling(), supplied)
                else:
                    with self.assertRaises(RuntimeError):
                        limits.darwin_process_ceiling()
                library.assert_called_once_with('/usr/lib/libSystem.B.dylib', use_errno=True)
                system.sysctlbyname.assert_called_once()
                self.assertEqual(system.sysctlbyname.call_args.args[0], b'kern.maxprocperuid')
        with patch.object(limits.sys, 'platform', 'linux'), patch.object(limits.ctypes, 'CDLL') as library, \
                self.assertRaises(RuntimeError):
            limits.darwin_process_ceiling()
        library.assert_not_called()

    def test_child_limit_application_records_exact_clamped_values_not_an_accepted_mismatch(self):
        state = {resource.RLIMIT_NOFILE: (1048575, resource.RLIM_INFINITY), resource.RLIMIT_NPROC: (2666, 4000)}
        def setter(kind, pair):
            state[kind] = pair
        with patch.object(limits, 'darwin_process_ceiling', return_value=2666) as ceiling, \
                patch.object(limits.resource, 'getrlimit', side_effect=lambda kind: state[kind]), \
                patch.object(limits.resource, 'setrlimit', side_effect=setter) as set_limit:
            rows = limits.apply_child_limits()
        ceiling.assert_called_once_with()
        self.assertEqual(set_limit.call_args_list[0].args, (resource.RLIMIT_NOFILE, (256, resource.RLIM_INFINITY)))
        self.assertEqual(set_limit.call_args_list[1].args, (resource.RLIMIT_NPROC, (512, 2666)))
        self.assertEqual(rows, [dict(name='openFiles', before=[1048575, resource.RLIM_INFINITY],
            after=[256, resource.RLIM_INFINITY], kernelHardCeiling=None, parentOrSystemChanged=False),
            dict(name='processes', before=[2666, 4000], after=[512, 2666], kernelHardCeiling=2666, parentOrSystemChanged=False)])

    def test_other_readback_mismatches_and_unavailable_kernel_ceiling_still_fail_closed(self):
        for observed in ((511, 2666), (512, 4000), (513, 2666), (512, 2665)):
            with self.subTest(observed=observed), patch.object(limits, 'darwin_process_ceiling', return_value=2666), \
                    patch.object(limits.resource, 'getrlimit', side_effect=[(1024, 2048), (256, 2048), (2666, 4000), observed]), \
                    patch.object(limits.resource, 'setrlimit'), self.assertRaisesRegex(RuntimeError, 'not applied'):
                limits.apply_child_limits()
        with patch.object(limits, 'darwin_process_ceiling', side_effect=RuntimeError('OFFLINE sysctl failed')), \
                patch.object(limits.resource, 'getrlimit', side_effect=[(1024, 2048), (256, 2048)]), \
                patch.object(limits.resource, 'setrlimit') as set_limit, self.assertRaisesRegex(RuntimeError, 'sysctl failed'):
            limits.apply_child_limits()
        set_limit.assert_called_once_with(resource.RLIMIT_NOFILE, (256, 2048))


class SlowAdvertisingDiagnostics(unittest.TestCase):
    def waiting_peer(self):
        peer = m.Peer.__new__(m.Peer)
        peer.child = Mock(poll=Mock(return_value=None))
        peer.campaign = Mock()
        peer.text = Mock(return_value='not ready')
        peer.thread_dump = Mock()
        return peer

    def test_no_observation_when_output_arrives_before_original_deadline(self):
        peer = self.waiting_peer()
        peer.text.return_value = 'advertising off'
        with patch.object(m.time, 'monotonic', return_value=0):
            self.assertEqual(peer.wait_text('advertising off'), 'advertising off')
        peer.thread_dump.assert_not_called()

    def test_two_observations_do_not_extend_or_satisfy_original_deadline(self):
        peer = self.waiting_peer()
        with patch.object(m.time, 'monotonic', side_effect=[0, 4.5, 5, 6.5, 7, 20]), \
                self.assertRaisesRegex(RuntimeError, 'Missing CLI output: advertising off'):
            peer.wait_text('advertising off')
        self.assertEqual([call.args for call in peer.thread_dump.call_args_list], [(4.5,), (6.5,)])
        self.assertEqual(peer.campaign.pump.call_count, 4)

    def test_expired_or_exited_child_is_not_observed(self):
        for ended in (False, True):
            peer = self.waiting_peer()
            peer.child.poll.return_value = 0 if ended else None
            with patch.object(m.time, 'monotonic', side_effect=[0, 20]), self.assertRaises(RuntimeError):
                peer.wait_text('advertising off')
            peer.thread_dump.assert_not_called()

    def test_other_commands_never_request_thread_dumps(self):
        peer = self.waiting_peer()
        with patch.object(m.time, 'monotonic', side_effect=[0, 5, 7, 20]), self.assertRaises(RuntimeError):
            peer.wait_text('unrelated output')
        peer.thread_dump.assert_not_called()

    def test_dump_uses_only_opaque_lifetime_token_and_private_evidence(self):
        peer, scope = FaultPolicy().peer()
        peer.stopped = False
        with tempfile.TemporaryDirectory() as tmp, patch.object(m.os, 'kill') as kill, patch.object(m.os, 'killpg') as group:
            peer.directory = Path(tmp)
            peer.thread_dump(4.5)
            peer.thread_dump(4.5)  # A later command gets a distinct, exclusive evidence file.
            paths = sorted(peer.directory.glob('thread-dump-*.json'))
            self.assertEqual(len(paths), 2)
            for path in paths:
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(json.loads(path.read_text())['kind'], 'diagnostic')
            self.assertEqual([call.args[1] for call in scope.proc.proc_signal_with_audittoken.call_args_list],
                             [signal.SIGQUIT, signal.SIGQUIT])
            kill.assert_not_called()
            group.assert_not_called()

    def test_unowned_changed_exec_or_stopped_target_never_receives_dump_signal(self):
        for change in ({'parentUniqueId': 21}, {'realUid': 0}, {'live': False}, {'pidVersion': 4}, {'stopped': True}):
            peer, scope = FaultPolicy().peer()
            peer.stopped = change.get('stopped', False)
            scope._observe.return_value = peer.identity | change
            with self.assertRaises(RuntimeError):
                peer.thread_dump(4.5)
            scope.proc.proc_signal_with_audittoken.assert_not_called()

    def test_invalid_observation_or_missing_token_never_signals(self):
        for point, token in ((0, True), (5, True), ('4.5', True), (4.5, False)):
            peer, scope = FaultPolicy().peer()
            peer.stopped = False
            if not token:
                peer.token = None
            with self.assertRaises(RuntimeError):
                peer.thread_dump(point)
            scope.proc.proc_signal_with_audittoken.assert_not_called()

    def test_diagnostic_signal_failure_is_not_hidden_or_retried_with_a_pid(self):
        peer, scope = FaultPolicy().peer()
        peer.stopped = False
        scope.proc.proc_signal_with_audittoken.return_value = 1
        with patch.object(m.os, 'kill') as kill, patch.object(m.os, 'killpg') as group, \
                self.assertRaisesRegex(RuntimeError, 'no PID fallback'):
            peer.thread_dump(6.5)
        self.assertEqual(peer.events, [])
        scope.proc.proc_signal_with_audittoken.assert_called_once()
        kill.assert_not_called()
        group.assert_not_called()


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


class DeadlineAdmission(unittest.TestCase):
    """Scripted observation clocks and inert children; no JVM, sockets, signals or native qualification."""
    def peer(self):
        peer = m.Peer.__new__(m.Peer)
        peer.child = Mock(poll=Mock(return_value=None), returncode=0, args=['OFFLINE'])
        peer.campaign = Mock(source=SOURCE)
        peer.text = Mock(return_value='observed')
        peer.thread_dump = Mock()
        return peer

    def test_matching_text_first_observed_at_or_after_deadline_cannot_pass(self):
        for elapsed in (20, 20.01):
            for expected in ('advertising off', 'observed'):
                peer = self.peer()
                peer.text.return_value = expected
                with self.subTest(elapsed=elapsed, expected=expected), \
                        patch.object(m.time, 'monotonic', side_effect=[0, elapsed]), \
                        self.assertRaisesRegex(RuntimeError, 'Missing CLI output:'):
                    peer.wait_text(expected)
                peer.thread_dump.assert_not_called()
                peer.campaign.pump.assert_not_called()

    def test_matching_pattern_first_observed_at_or_after_deadline_cannot_pass(self):
        for elapsed in (40, 40.01):
            peer = self.peer()
            with self.subTest(elapsed=elapsed), patch.object(m.time, 'monotonic', side_effect=[0, elapsed]), \
                    self.assertRaisesRegex(RuntimeError, 'Missing CLI terminal observation:'):
                peer.wait_pattern('^observed$')
            peer.campaign.pump.assert_not_called()

    def test_timely_matching_text_and_pattern_remain_accepted(self):
        for method, expected, elapsed in (('wait_text', 'observed', 19.999),
                                         ('wait_pattern', '^observed$', 39.999)):
            peer = self.peer()
            with self.subTest(method=method), patch.object(m.time, 'monotonic', side_effect=[0, elapsed]):
                self.assertEqual(getattr(peer, method)(expected), 'observed')
            peer.thread_dump.assert_not_called()
            peer.campaign.pump.assert_not_called()

    def exiting_peer(self, directory, polls):
        peer = self.peer()
        peer.directory, peer.path = directory, directory / 'terminal.log'
        peer.app, peer.identity, peer.events, peer.stream = 'OFFLINE', {}, [], Mock()
        peer.child.poll.side_effect = polls
        (directory / 'exports').mkdir()
        (directory / 'exports/offline.zip').write_bytes(b'NOT AN APPLICATION OR VALID NATIVE EXPORT')
        return peer

    def test_late_exit_cannot_publish_success_or_close_evidence_as_timely(self):
        for clocks, polls in (([0, 35], [0]), ([0, 35.01], [0]), ([0, 34.9, 35], [None, 0])):
            with self.subTest(clocks=clocks), tempfile.TemporaryDirectory() as temporary:
                peer = self.exiting_peer(Path(temporary), polls)
                with patch.object(m.time, 'monotonic', side_effect=clocks), \
                        patch.object(m, 'digest', return_value='a' * 64), \
                        patch.object(m, 'inspect_export', return_value={}), patch.object(m, 'private_write') as write, \
                        self.assertRaisesRegex(RuntimeError, 'original shutdown budget'):
                    peer.wait_exit((0,))
                write.assert_not_called()
                peer.child.stdin.close.assert_not_called()
                peer.stream.close.assert_not_called()

    def test_timely_exit_keeps_returncode_and_export_checks(self):
        with tempfile.TemporaryDirectory() as temporary:
            peer = self.exiting_peer(Path(temporary), [0])
            with patch.object(m.time, 'monotonic', side_effect=[0, 34.999]), \
                    patch.object(m, 'digest', return_value='a' * 64), \
                    patch.object(m, 'inspect_export', return_value={'OFFLINE': True}) as inspect, \
                    patch.object(m, 'private_write') as write:
                peer.wait_exit((0,))
            self.assertEqual(write.call_count, 2)
            inspect.assert_called_once()
            peer.child.stdin.close.assert_called_once()
            peer.stream.close.assert_called_once()

    def option_case(self, directory, clocks, polls, *, output_limit=m.MAX_LOG):
        campaign = m.Campaign.__new__(m.Campaign)
        campaign.directory, campaign.children = directory, []
        campaign.java_argv, campaign.pump, campaign.passed = Mock(return_value=['OFFLINE']), Mock(), Mock()
        child = Mock(poll=Mock(side_effect=polls), returncode=0)
        def launch(*args, **kwargs):
            kwargs['stdout'].write(b'Usage:\n')
            return child
        with patch.object(m.time, 'monotonic', side_effect=clocks), patch.object(m, 'MAX_LOG', output_limit), \
                patch.object(m, 'launch_cases', return_value=[(['--help'], False)]), \
                patch.object(m.subprocess, 'Popen', side_effect=launch):
            campaign.options()
        return campaign

    def test_late_option_exit_cannot_record_a_passed_case(self):
        for clocks, polls in (([0, 15], [0]), ([0, 15.01], [0]), ([0, 14.9, 15], [None, 0])):
            with self.subTest(clocks=clocks), tempfile.TemporaryDirectory() as temporary, \
                    self.assertRaisesRegex(RuntimeError, 'CLI option deadline/output bound'):
                self.option_case(Path(temporary), clocks, polls)

    def test_finished_option_output_still_requires_original_byte_bound(self):
        with tempfile.TemporaryDirectory() as temporary, \
                self.assertRaisesRegex(RuntimeError, 'CLI option deadline/output bound'):
            self.option_case(Path(temporary), [0, 1], [0], output_limit=5)

    def test_timely_option_exit_keeps_the_original_case_assertions(self):
        with tempfile.TemporaryDirectory() as temporary:
            campaign = self.option_case(Path(temporary), [0, 14.999], [0])
            campaign.passed.assert_called_once()
            self.assertEqual(campaign.passed.call_args.args[0]['case'], 'option-0')

    def test_last_stdin_write_cannot_cross_original_deadline(self):
        peer = self.peer()
        with patch.object(m.time, 'monotonic', side_effect=[0, 9.9, 10]), \
                patch.object(m.os, 'write', return_value=1) as write, \
                self.assertRaisesRegex(RuntimeError, 'CLI stdin deadline/early exit'):
            peer.write('x')
        write.assert_called_once()

    def test_timely_stdin_write_does_not_extend_or_change_the_payload(self):
        peer = self.peer()
        with patch.object(m.time, 'monotonic', side_effect=[0, 9.9, 9.999]), \
                patch.object(m.os, 'write', return_value=1) as write:
            peer.write('x')
        self.assertEqual(write.call_args.args[1], b'x')

    def phase_boundary(self, phase, clocks):
        campaign = m.Campaign.__new__(m.Campaign)
        campaign.selected = [phase + '-term-0']
        campaign.connect, campaign.offer = Mock(), Mock(return_value='OFFLINE-OFFER')
        campaign.files = Mock(side_effect=RuntimeError('continued after phase admission'))
        alice, bob = self.peer(), self.peer()
        bob.port, bob.pin = 12345, 'OFFLINE-PIN'
        alice.write, bob.command = Mock(), Mock()
        alice.text.return_value = bob.text.return_value = ''
        relay = SimpleNamespace(forwarded=[0, 0], limit=1, port=23456)
        def pump(_):
            relay.forwarded[0] = relay.limit
        campaign.pump = pump
        with patch.object(m.time, 'monotonic', side_effect=clocks), \
                patch.object(m, 'Peer', side_effect=[alice, bob]), patch.object(m, 'Relay', return_value=relay):
            campaign.faults()

    def test_late_handshake_progress_cannot_authorize_a_phase_fault(self):
        with self.assertRaisesRegex(RuntimeError, 'Handshake phase not reached'):
            self.phase_boundary('handshake', [0, 9.9, 10])

    def test_late_transfer_progress_cannot_authorize_a_phase_fault(self):
        with self.assertRaisesRegex(RuntimeError, 'In-flight transfer phase not reached'):
            self.phase_boundary('transfer', [0, 19.9, 20])

    def test_timely_phase_progress_preserves_original_next_assertions(self):
        for phase, clocks in (('handshake', [0, 9.9, 9.999]), ('transfer', [0, 19.9, 19.999])):
            with self.subTest(phase=phase), self.assertRaisesRegex(RuntimeError, 'continued after phase admission'):
                self.phase_boundary(phase, clocks)

    def finished_campaign(self, directory):
        campaign = m.Campaign.__new__(m.Campaign)
        campaign.selection, campaign.first_case = 'post-options', None
        campaign.source, campaign.directory = SOURCE, directory
        campaign.selected = m.case_inventory(campaign.selection)
        campaign.rows, campaign.children, campaign.peers = [], [], []
        campaign.relay, campaign.started, campaign.scope = None, 0, Mock()
        campaign.manifest = {'OFFLINE': True}
        for name in ('options', 'commands', 'multi_peer_contract', 'admission_pressure', 'transfers_and_storage'):
            setattr(campaign, name, Mock())
        campaign.faults = Mock(side_effect=lambda: campaign.rows.extend(
            dict(case=name, passed=True) for name in campaign.selected))
        return campaign

    def test_final_campaign_success_cannot_escape_original_safety_deadline(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            campaign = self.finished_campaign(directory)
            with patch.object(m.time, 'monotonic', return_value=2700), \
                    patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_bavail=8 * 1024**3, f_frsize=1)), \
                    patch.object(m, 'runtime_manifest', return_value=campaign.manifest), \
                    patch.object(m, 'digest', return_value='a' * 64), \
                    patch.object(Path, 'open', unittest.mock.mock_open()), \
                    self.assertRaisesRegex(RuntimeError, 'Campaign safety deadline'):
                campaign.run()
            value = json.loads((directory / 'result.json').read_bytes())
            self.assertEqual(value['result'], 'FAIL')
            self.assertFalse(value['fullCampaignQualified'])
            campaign.scope.close.assert_called_once()

    def test_timely_final_campaign_keeps_closed_inventory_and_no_native_claim(self):
        with tempfile.TemporaryDirectory() as temporary:
            campaign = self.finished_campaign(Path(temporary))
            with patch.object(m.time, 'monotonic', return_value=2699.999), \
                    patch.object(m.os, 'statvfs', return_value=SimpleNamespace(f_bavail=8 * 1024**3, f_frsize=1)), \
                    patch.object(m, 'runtime_manifest', return_value=campaign.manifest), \
                    patch.object(m, 'digest', return_value='a' * 64), \
                    patch.object(Path, 'open', unittest.mock.mock_open()):
                result = campaign.run()
            self.assertEqual(result['result'], 'PASS')
            self.assertEqual([row['case'] for row in result['cases']], m.case_inventory('post-options'))
            self.assertFalse(result['fullCampaignQualified'])
            campaign.scope.close.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
