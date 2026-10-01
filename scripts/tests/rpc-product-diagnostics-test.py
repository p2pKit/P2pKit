#!/usr/bin/env python3
"""Offline closed diagnostics; no product or Apple execution."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import rpc_product_diagnostics as d


class Diagnostics(unittest.TestCase):
    def test_jdk_accept_failures_keep_closed_causes_without_exporting_exception_messages(self):
        messages = {
            'JAVA_SOCKET_CLOSED': 'Socket closed', 'JAVA_INVALID_ARGUMENT': 'Invalid argument',
            'JAVA_BAD_DESCRIPTOR': 'Bad file descriptor', 'JAVA_NOT_A_SOCKET': 'Socket operation on non-socket',
            'JAVA_ACCEPT_ABORTED': 'Software caused connection abort', 'JAVA_CONNECTION_RESET': 'Connection reset',
            'JAVA_RESOURCE_UNAVAILABLE': 'Resource temporarily unavailable',
            'JAVA_FILE_DESCRIPTOR_LIMIT': 'Too many open files', 'JAVA_SOCKET_PERMISSION_DENIED': 'Permission denied',
        }
        for marker, message in messages.items():
            case = ET.fromstring('<testcase><failure>java.net.SocketException: ' + message +
                                 '\nPRIVATE_SECRET /private/endpoint</failure></testcase>')
            row = d.failure_locations(case, {})
            self.assertEqual(row['markers'], sorted([marker, 'JAVA_SOCKET_EXCEPTION']))
            self.assertNotIn('PRIVATE_SECRET', str(row))
            self.assertNotIn(message, str(row))
            case.find('failure').text = 'PRIVATE_SECRET ' + message
            self.assertEqual(d.failure_locations(case, {})['markers'], [])
        case = ET.fromstring('<testcase><failure>java.net.SocketException: PRIVATE_SECRET</failure></testcase>')
        self.assertEqual(d.failure_locations(case, {})['markers'], ['JAVA_SOCKET_EXCEPTION'])
        for cls, marker in (('java.net.SocketTimeoutException', 'JAVA_SOCKET_TIMEOUT'),
                            ('java.io.InterruptedIOException', 'JAVA_INTERRUPTED_IO')):
            case.find('failure').text = cls + ': PRIVATE_SECRET'
            self.assertEqual(d.failure_locations(case, {})['markers'], [marker])

    def test_compiler_diagnostics_export_only_known_locations_and_closed_categories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            source = root / 'samples/x/src/jvmMain/kotlin/Fixture.kt'
            source.parent.mkdir(parents=True)
            source.write_text('package sample\nclass Fixture {\n fun call() {}\n}\n')
            raw = (b'e: file:///private/Fixture.kt:3:7 Unresolved reference: PRIVATE_SECRET\n'
                   b'w: /private/Fixture.kt:4:1: Argument type mismatch: PRIVATE_SECRET\n'
                   b'e: Fixture.kt:1:1 Cannot infer PRIVATE_SECRET\n'
                   b'> Task :p2p-sample-rpc:compileKotlinJvm FAILED\n'
                   b'> Task :PRIVATE_SECRET:compileKotlinJvm FAILED\n'
                   b'> Task :p2p-sample-rpc:PRIVATE_SECRET FAILED\n'
                   b'Compilation error PRIVATE_SECRET\n')
            row = d.build_observation(root, raw)
            self.assertEqual(row['failedTasks'], [':p2p-sample-rpc:compileKotlinJvm'])
            self.assertEqual(row['compilerSites'], [dict(source=source.relative_to(root).as_posix(), line=line,
                column=column, severity=severity, markers=[marker]) for line, column, severity, marker in (
                    (3, 7, 'ERROR', 'UNRESOLVED_REFERENCE'), (4, 1, 'WARNING', 'TYPE_MISMATCH'),
                    (1, 1, 'ERROR', 'TYPE_INFERENCE'))])
            self.assertEqual(row['markers'], ['COMPILATION_FAILED'])
            self.assertFalse(row['executionAdmitted'])
            self.assertNotIn('PRIVATE_SECRET', json.dumps(row))
            self.assertNotIn('/private/', json.dumps(row))
            value = {'build': {'jvm-regression': {'stdout': row, 'stderr': d.build_observation(root, b'')}}}
            self.assertEqual(d.validate(value, root, {'jvm-regression'}), value)
            for prefix in ('e: /private/OtherFixture.kt:3:7', 'e: Fixture.kt:99:1', 'e: Fixture.kt:0:1',
                           'e: Fixture.kt:1:0', 'e: Fixture.kt:1:1000001', 'e: Unknown.kt:1:1',
                           'private e: Fixture.kt:3:7'):
                self.assertEqual(d.build_observation(root, (prefix + ' Unresolved reference PRIVATE_SECRET').encode())[
                    'compilerSites'], [])
            duplicate = root / 'library/x/src/commonMain/kotlin/Fixture.kt'
            duplicate.parent.mkdir(parents=True)
            duplicate.write_text(source.read_text())
            self.assertEqual(d.build_observation(root, raw)['compilerSites'], [])

    def test_compiler_public_schema_rejects_private_fields_unknown_scopes_and_forged_admission(self):
        row = d.build_observation(ROOT, b'e: file:///private/CapacityInitialization.kt:19:1 Syntax error PRIVATE_SECRET')
        self.assertEqual(len(row['compilerSites']), 1)
        original = {'build': {'jvm-regression': {'stdout': row, 'stderr': d.build_observation(ROOT, b'')}}}
        for key, bad in (('raw', 'PRIVATE_SECRET'), ('bytes', True), ('sha256', 'PRIVATE_SECRET'),
                         ('executionAdmitted', True), ('failedTasks', [':private:jvmTest']),
                         ('markers', ['PRIVATE_SECRET']), ('compilerSites', [True])):
            value = copy.deepcopy(original)
            value['build']['jvm-regression']['stdout'][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate(value, ROOT, {'jvm-regression'})
        for key, bad in (('source', '/PRIVATE_SECRET'), ('line', 9999999), ('line', True), ('column', 0),
                         ('column', True), ('severity', 'PRIVATE_SECRET'), ('markers', ['PRIVATE_SECRET']),
                         ('message', 'PRIVATE_SECRET')):
            value = copy.deepcopy(original)
            value['build']['jvm-regression']['stdout']['compilerSites'][0][key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                d.validate(value, ROOT, {'jvm-regression'})
        for value, purposes in ((original, set()), ({'build': []}, set()),
                                ({'build': {'full-platform': original['build']['jvm-regression']}}, {'full-platform'})):
            with self.assertRaises(ValueError):
                d.validate(value, ROOT, purposes)

    def test_jvm_xml_is_separate_from_native_and_android_and_never_admits_failed_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            source = root / 'samples/x/src/jvmTest/kotlin/Fixture.kt'
            source.parent.mkdir(parents=True)
            source.write_text('package sample\nclass Fixture {\n fun fails() {}\n}\n')
            for task in ('jvmTest', 'iosX64Test', 'testAndroidHostTest'):
                xml = root / 'samples/x/build/test-results' / task / 'TEST-fixture.xml'
                xml.parent.mkdir(parents=True)
                xml.write_text('<testsuite><testcase classname="sample.Fixture" name="fails">'
                               '<failure>AssertionError at Fixture.kt:3 PRIVATE_SECRET</failure></testcase></testsuite>')
            row = d.native_observation(root, {'buildFailed': True}, 'jvm')
            self.assertEqual(row['attemptCounts'], dict(passed=0, failed=1, errors=0, skipped=0))
            self.assertEqual(row['xmlFiles'], 1)
            self.assertEqual(row['failedMethods'], [['sample.Fixture', 'fails']])
            self.assertEqual(row['failureDetails'][0]['sourceLocations'], [[source.relative_to(root).as_posix(), 3]])
            self.assertFalse(row['executionAdmitted'])
            self.assertNotIn('PRIVATE_SECRET', json.dumps(row))
            for label in ('jvm-regression', 'full-platform'):
                self.assertEqual(d.validate({'jvm': {label: row}}, root, {label}), {'jvm': {label: row}})
                with self.assertRaises(ValueError):
                    d.validate({'jvm': {label: row}}, root, set())
            for family, label in (('jvm', 'scoped-native'), ('native', 'jvm-regression'), ('androidHost', 'jvm-regression')):
                with self.assertRaises(ValueError):
                    d.validate({family: {label: row}}, root, {label})

    def test_android_host_failure_is_not_lost_or_counted_as_native_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            source = root / 'library/x/src/androidHostTest/kotlin/HostFixture.kt'
            source.parent.mkdir(parents=True)
            source.write_text('package sample\nclass HostFixture {\n fun fails() {}\n}\n')
            base = root / 'library/x/build/test-results'
            for task, body in (('iosX64Test', '<testcase classname="private" name="not-exported"/>'),
                               ('testAndroidHostTest', '<testcase classname="sample.HostFixture" name="fails">'
                                '<failure>AssertionError at HostFixture.kt:3 private-token</failure></testcase>')):
                path = base / task / 'TEST-fixture.xml'
                path.parent.mkdir(parents=True)
                path.write_text('<testsuite>' + body + '</testsuite>')
            native = d.native_observation(root, None)
            host = d.native_observation(root, {'buildFailed': True}, 'androidHost')
            self.assertEqual(native['attemptCounts'], dict(passed=1, failed=0, errors=0, skipped=0))
            self.assertEqual(host['attemptCounts'], dict(passed=0, failed=1, errors=0, skipped=0))
            self.assertEqual(host['failedMethods'], [['sample.HostFixture', 'fails']])
            self.assertEqual(host['failureDetails'], [{'method': ['sample.HostFixture', 'fails'],
                'sourceLocations': [[source.relative_to(root).as_posix(), 3]], 'markers': ['ASSERTION']}])
            self.assertFalse(host['executionAdmitted'])
            for label in ('full-platform', 'intel-host-tests'):
                self.assertEqual(d.validate({'androidHost': {label: host}}, root, {label}),
                                 {'androidHost': {label: host}})
            self.assertNotIn('private', str(host))
            with self.assertRaises(ValueError):
                d.validate({'native': {'intel-host-tests': host}}, root, {'intel-host-tests'})
            with self.assertRaises(ValueError):
                d.validate({'androidHost': {'scoped-native': host}}, root, {'scoped-native'})

    def test_android_host_xml_retains_entity_symlink_unknown_family_and_private_name_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            path = root / 'samples/x/build/test-results/testAndroidHostTest/TEST-fixture.xml'
            path.parent.mkdir(parents=True)
            path.write_text('<testsuite><testcase classname="private" name="private-token">'
                            '<failure>private</failure></testcase></testsuite>')
            observed = d.native_observation(root, None, 'androidHost')
            self.assertEqual(observed['unmappedFailedMethods'], 1)
            self.assertEqual(observed['failedMethods'], [])
            self.assertNotIn('private', str(observed))
            with self.assertRaises(ValueError):
                d.native_observation(root, None, 'arbitrary')
            path.write_text('<!DOCTYPE testsuite [<!ENTITY private SYSTEM "file:///no-read">]><testsuite/>')
            with self.assertRaises(ValueError):
                d.native_observation(root, None, 'androidHost')
            path.unlink()
            path.symlink_to(root / 'gradle/platform-test-policy.json')
            with self.assertRaises(ValueError):
                d.native_observation(root, None, 'androidHost')

    def test_flattened_native_constructor_frames_preserve_only_closed_diagnostic_labels(self):
        import re
        source = (ROOT / 'library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/'
                  'AppleLanDiscoveryFailure.kt').read_text()
        declared = set(re.findall(r'private class (AppleLan[A-Za-z0-9]+) : AssertionError', source))
        self.assertEqual(declared, set(d.FAILURE_FRAME_MARKERS.values()))
        for marker, name in d.FAILURE_FRAME_MARKERS.items():
            # KGP's parser keeps only the first message, discards later
            # Suppressed lines and flattens their remaining Native frames.
            for constructor in ('#<init>', '.<init>', '.<init>#internal'):
                with self.subTest(marker=marker, constructor=constructor):
                    failure = ET.SubElement(case := ET.Element('testcase'), 'failure')
                    failure.text = ('TimeoutCancellationException: synthetic timeout\n'
                                    f'\tat dev.p2pkit.transport.lan.{name}{constructor}(AppleLanDiscoveryFailure.kt:40)\n'
                                    '\tat private.frame(private-file.kt:22)')
                    row = d.failure_locations(case, {})
                    self.assertEqual(row, {'sourceLocations': [], 'markers': sorted([marker, 'TIMEOUT'])})
                    self.assertNotIn('private', str(row))
                    self.assertNotIn('synthetic', str(row))
        for raw in ('at private.AppleLanInitialPeerTimeout#<init>(private.kt:1)',
                    'at dev.p2pkit.transport.lan.AppleLanInitialPeerTimeoutExtra#<init>(private.kt:1)',
                    'at dev.p2pkit.transport.lan.AppleLanInitialPeerTimeout#other(private.kt:1)',
                    'at dev.p2pkit.transport.lan.AppleLanInitialPeerTimeout.<init>#internalExtra(private.kt:1)',
                    'at dev.p2pkit.transport.lan.AppleLanInitialPeerTimeout.<init>#private(private.kt:1)',
                    'at dev.p2pkit.transport.lan.AppleLanInitialPeerTimeout#other#internal(private.kt:1)',
                    'at private.dev.p2pkit.transport.lan.AppleLanInitialPeerTimeout.<init>#internal(private.kt:1)',
                    'payload dev.p2pkit.transport.lan.AppleLanInitialPeerTimeout.<init>#internal(private.kt:1)',
                    'payload dev.p2pkit.transport.lan.AppleLanInitialPeerTimeout#<init>(private.kt:1)'):
            failure = ET.SubElement(case := ET.Element('testcase'), 'failure')
            failure.text = raw
            self.assertEqual(d.failure_locations(case, {})['markers'], [])

    def test_signatureless_private_native_constructor_keeps_suffix_through_pinned_frame_conversion(self):
        # KGP 2.4.10 removes kfun:, splits before the last opening parenthesis,
        # then splits at the last dot. A private symbol has NO signature to
        # remove: <init>#internal becomes the entire JVM method name.
        for marker, name in d.FAILURE_FRAME_MARKERS.items():
            native_symbol = f'kfun:dev.p2pkit.transport.lan.{name}.<init>#internal'
            class_and_method = native_symbol.removeprefix('kfun:').split('(')[0]
            cls, method = class_and_method.rsplit('.', 1)
            self.assertEqual(method, '<init>#internal')
            failure = ET.SubElement(case := ET.Element('testcase'), 'failure')
            failure.text = f'\tat {cls}.{method}(Unknown Source)'
            self.assertEqual(d.failure_locations(case, {}), {'sourceLocations': [], 'markers': [marker]})

    def test_helper_case_inventory_keeps_actual_source_bound_outcomes_without_admitting_execution(self):
        cls = 'dev.p2pkit.transport.lan.AppleLanDiscoveryFailureTest'
        helper = ROOT / 'library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/AppleLanDiscoveryFailureTest.kt'
        method = 'allStageContextsRetainOwnNativeConstructorFrames'
        for task in d.DIAGNOSTIC_TARGETS:
            with self.subTest(task=task), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'gradle').mkdir()
                (root / 'gradle/platform-test-policy.json').write_bytes(
                    (ROOT / 'gradle/platform-test-policy.json').read_bytes())
                source = root / helper.relative_to(ROOT)
                source.parent.mkdir(parents=True)
                source.write_bytes(helper.read_bytes())
                xml = root / 'library/p2p-transport-lan/build/test-results' / task / 'TEST-fixture.xml'
                xml.parent.mkdir(parents=True)
                xml.write_text(f'<testsuite><testcase classname="{task}.{cls}" name="{method}"/>'
                               '<testcase classname="private" name="private-secret"/></testsuite>')
                row = d.native_observation(root, {'buildFailed': True})
                self.assertEqual(row['diagnosticCases'], [{'method': [cls, method], 'target': task, 'outcome': 'passed'}])
                self.assertFalse(row['executionAdmitted'])
                d.validate({'native': {'scoped-native': row}}, root, {'scoped-native'})
                self.assertNotIn('private', str(row))
                for change in (dict(method=[cls, 'private-secret']), dict(method=['private', method]),
                               dict(target='jvmTest'), dict(outcome='PASS'), dict(outcome=True), dict(target=[])):
                    changed = copy.deepcopy(row)
                    changed['diagnosticCases'][0].update(change)
                    with self.assertRaises(ValueError):
                        d.validate({'native': {'scoped-native': changed}}, root, {'scoped-native'})
                changed = copy.deepcopy(row)
                changed['diagnosticCases'] *= 2
                with self.assertRaises(ValueError):
                    d.validate({'native': {'scoped-native': changed}}, root, {'scoped-native'})
                changed = copy.deepcopy(row)
                changed['diagnosticCases'][0]['outcome'] = 'skipped'
                with self.assertRaises(ValueError):
                    d.validate({'native': {'scoped-native': changed}}, root, {'scoped-native'})

    def test_discovery_wait_stages_remain_closed_not_payload_text_or_new_verdicts(self):
        for stage, marker in (('INITIAL_PEER', 'INITIAL_PEER_DISCOVERY_TIMEOUT'),
                              ('INITIAL_PEER_SET', 'INITIAL_PEER_SET_DISCOVERY_TIMEOUT'),
                              ('REDISCOVERY', 'PEER_REDISCOVERY_TIMEOUT')):
            case = ET.fromstring('<testcase><failure>TimeoutCancellationException private message\n'
                                 'Suppressed: AssertionError: APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=' + stage +
                                 '\n</failure></testcase>')
            row = d.failure_locations(case, {})
            self.assertEqual(row, {'sourceLocations': [], 'markers': ['ASSERTION', marker, 'TIMEOUT']})
            self.assertNotIn('private', str(row))
        case = ET.fromstring('<testcase><failure>APPLE_LAN_DISCOVERY_WAIT_TIMEOUT stage=INITIAL_PEER_SECRET'
                             '</failure></testcase>')
        self.assertEqual(d.failure_locations(case, {})['markers'], [])

    def test_browser_diagnostic_allowlist_matches_test_source_enums_and_never_exports_unknown_text(self):
        import re
        source = (ROOT / 'library/p2p-transport-lan/src/appleTest/kotlin/dev/p2pkit/transport/lan/'
                  'AppleLanDiscoveryFailure.kt').read_text()
        enums = re.search(r'enum class AppleLanDiscoveryMarker \{([^}]+)}', source)[1]
        names = re.findall(r'\b[A-Z][A-Z_0-9]+\b', enums)
        self.assertEqual({'APPLE_LAN_' + name for name in names},
                         {key for key in d.FAILURE_MARKERS if key.startswith('APPLE_LAN_')})
        for name in names:
            case = ET.fromstring('<testcase><failure>Suppressed: APPLE_LAN_DISCOVERY_OBSERVED marker=' + name +
                                 '\nprivate-payload</failure></testcase>')
            self.assertEqual(d.failure_locations(case, {})['markers'], ['APPLE_LAN_' + name])
        for unknown in ('BROWSER_PRIVATE', 'private-key', 'BROWSER_READY_PRIVATE'):
            case = ET.fromstring('<testcase><failure>APPLE_LAN_DISCOVERY_OBSERVED marker=' + unknown +
                                 '</failure></testcase>')
            self.assertEqual(d.failure_locations(case, {})['markers'], [])

    def test_failure_sites_are_only_unambiguous_existing_source_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'library/x/src/commonTest/kotlin/Fixture.kt'
            path.parent.mkdir(parents=True)
            path.write_text('package sample\nclass Fixture {\n fun test() {}\n}\n')
            case = ET.fromstring('<testcase><failure>private payload\n'
                                 'Unexpected warn/error diagnostics recorded\n'
                                 'P2pKit stopped before the session could be committed\n'
                                 'at /private/path/Fixture.kt:3:9\n'
                                 'at Fixture.kt:999\n'
                                 'at Unchecked.kt:1\n'
                                 '</failure></testcase>')
            row = d.failure_locations(case, d.source_locations(root))
            self.assertEqual(row['sourceLocations'], [['library/x/src/commonTest/kotlin/Fixture.kt', 3]])
            self.assertEqual(row['markers'], ['SETUP_AFTER_STOP', 'UNEXPECTED_DIAGNOSTIC'])
            self.assertNotIn('private', str(row))
            duplicate = root / 'samples/x/src/jvmTest/kotlin/Fixture.kt'
            duplicate.parent.mkdir(parents=True)
            duplicate.write_text(path.read_text())
            self.assertEqual(d.failure_locations(case, d.source_locations(root))['sourceLocations'], [])

    def test_only_closed_markers_and_numeric_boot_states_leave_raw_logs(self):
        raw = b'private-token /private/path\nWaiting on Data Migration\nStatus=2, isTerminal=NO, Elapsed=01:59.\nNSPOSIXErrorDomain Code=60 private-message'
        row = d.log_observation(raw)
        self.assertEqual(row['markers'], ['WAIT_MIGRATION'])
        self.assertEqual(row['domains'], [{'domain': 'NSPOSIXErrorDomain', 'code': 60}])
        self.assertEqual(row['lastBootStatuses'], [{'status': 2, 'terminal': False, 'elapsedSeconds': 119}])
        value = {'logs': {'swift-simulator-readiness': {'stdout': row, 'stderr': d.log_observation(b'')}}}
        d.validate(value, ROOT, {'swift-simulator-readiness'})
        self.assertNotIn('private', str(value))
        for key, bad in [('markers', ['private-token']), ('sha256', 'private-value'), ('bytes', True)]:
            changed = copy.deepcopy(value)
            changed['logs']['swift-simulator-readiness']['stdout'][key] = bad
            with self.assertRaises(ValueError):
                d.validate(changed, ROOT, {'swift-simulator-readiness'})

    def test_arbitrary_finished_test_stack_is_not_simulator_boot_completion(self):
        self.assertNotIn('BOOT_FINISHED', d.log_observation(b'at private.testFinished(Fixture.kt:3)')['markers'])
        self.assertIn('BOOT_FINISHED', d.log_observation(b'\nFinished!\n')['markers'])

    def test_failed_test_names_are_bound_to_checked_in_source_not_messages(self):
        cls, method = next(iter(d.source_methods(ROOT)))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'gradle').mkdir()
            (root / 'gradle/platform-test-policy.json').write_bytes((ROOT / 'gradle/platform-test-policy.json').read_bytes())
            p = root / 'library/x/src/commonTest/kotlin'
            p.mkdir(parents=True)
            package, name = cls.rsplit('.', 1)
            (p / 'Fixture.kt').write_text(f'package {package}\nclass {name} {{ fun {method}() {{}} }}')
            xml = root / 'library/x/build/test-results/iosX64Test'
            xml.mkdir(parents=True)
            (xml / 'TEST-fixture.xml').write_text(f'<testsuite><testcase classname="{cls}" name="{method}[iosX64]"><failure>secret payload</failure></testcase><testcase classname="private" name="secret"><error>secret</error></testcase></testsuite>')
            row = d.native_observation(root, {'buildFailed': True})
            self.assertEqual(row['failedMethods'], [[cls, method]])
            self.assertEqual(row['unmappedFailedMethods'], 1)
            self.assertEqual(row['attemptCounts'], dict(passed=0, failed=1, errors=1, skipped=0))
            self.assertFalse(row['executionAdmitted'])
            value = {'native': {'scoped-native': row}}
            d.validate(value, root, {'scoped-native'})
            self.assertNotIn('secret', str(value))
            row['failedMethods'].append(['private', 'secret'])
            with self.assertRaises(ValueError):
                d.validate(value, root, {'scoped-native'})

    def test_real_native_task_prefix_is_source_bound_on_both_architectures(self):
        for task, target in (('iosX64Test', 'iosX64'), ('iosSimulatorArm64Test', 'iosSimulatorArm64')):
            with self.subTest(task=task), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'gradle').mkdir()
                (root / 'gradle/platform-test-policy.json').write_bytes(
                    (ROOT / 'gradle/platform-test-policy.json').read_bytes())
                source = root / 'library/x/src/appleTest/kotlin/Fixture.kt'
                source.parent.mkdir(parents=True)
                source.write_text('package sample\nclass Fixture {\n fun test() {}\n}\n')
                xml = root / 'library/x/build/test-results' / task / 'TEST-fixture.xml'
                xml.parent.mkdir(parents=True)
                xml.write_text(f'<testsuite><testcase classname="{task}.sample.Fixture" '
                               f'name="test[{target}]"><failure>AssertionError at Fixture.kt:3 '
                               'private payload</failure></testcase></testsuite>')
                row = d.native_observation(root, {'buildFailed': True})
                self.assertEqual(row['failedMethods'], [['sample.Fixture', 'test']])
                self.assertEqual(row['unmappedFailedMethods'], 0)
                self.assertEqual(row['attemptCounts']['failed'], 1)
                self.assertEqual(row['failureDetails'], [{
                    'method': ['sample.Fixture', 'test'],
                    'sourceLocations': [['library/x/src/appleTest/kotlin/Fixture.kt', 3]],
                    'markers': ['ASSERTION'],
                }])
                self.assertFalse(row['executionAdmitted'])
                d.validate({'native': {'scoped-native': row}}, root, {'scoped-native'})
                self.assertNotIn('private', str(row))

    def test_wrong_task_or_recursive_prefix_does_not_become_a_source_identity(self):
        methods = {('sample.Fixture', 'test')}
        for cls in ('iosSimulatorArm64Test.sample.Fixture',
                    'iosX64Test.iosX64Test.sample.Fixture',
                    'untrusted.sample.Fixture', 'iosX64Test.private.Secret'):
            with self.subTest(cls=cls):
                case = ET.fromstring(f'<testcase classname="{cls}" name="test[iosX64]"/>')
                self.assertIsNone(d.source_method_identity(case, 'iosX64Test', methods))

    def test_no_entity_expansion_or_diagnostic_admission(self):
        value = {'native': {'scoped-native': d.native_observation(ROOT, None)}}
        value['native']['scoped-native']['executionAdmitted'] = True
        with self.assertRaises(ValueError):
            d.validate(value, ROOT, {'scoped-native'})
        with self.assertRaises(ValueError):
            d.validate({'simulator': {'states': {'known': 'private'}}}, ROOT, {'known'})
        with self.assertRaises(ValueError):
            d.validate({'simulator': {'version': 'secret', 'architectures': ['arm64']}}, ROOT, set())
        with self.assertRaises(ValueError):
            d.validate({'private': 'secret'}, ROOT, set())

    def test_failed_tasks_remain_observations_not_admitted_counts(self):
        task = ':p2p-core:iosX64Test'
        report = {'buildFailed': True, 'tests': {task: dict(outcome='FAILED', enabled=True, inGraph=True,
                                                         passed=30, failed=1, skipped=0)}}
        row = d.native_observation(ROOT, report)
        self.assertEqual(row['tasks'][task]['failed'], 1)
        self.assertFalse(row['executionAdmitted'])
        d.validate({'native': {'scoped-native': row}}, ROOT, {'scoped-native'})


class IntelEnvironment(unittest.TestCase):
    MEMORY = (b'Mach Virtual Memory Statistics: (page size of 4096 bytes)\n'
              b'Pages free:                              200.\n'
              b'Pages active:                            100.\n'
              b'Pages inactive:                          300.\n'
              b'Pages wired down:                        400.\n'
              b'Pages occupied by compressor:              5.\n'
              b'Swapins:                                  20.\n'
              b'Swapouts:                                 30.\n')

    def observations(self):
        return {kind: d.intel_environment_observation(kind, raw) for kind, raw in (
            ('hardware', b'17179869184\n4\n'), ('memory', self.MEMORY),
            ('processes', b'0.0 2048 S /private/path/DataMigrator\n'))}

    def test_hardware_and_vm_snapshots_keep_only_closed_numeric_observations(self):
        rows = self.observations()
        self.assertEqual(rows['hardware']['memoryBytes'], 17179869184)
        self.assertEqual(rows['hardware']['logicalCpus'], 4)
        self.assertEqual(rows['memory']['pageSizeBytes'], 4096)
        self.assertEqual(rows['memory']['fields'], {'freePages': 200, 'activePages': 100, 'inactivePages': 300,
            'wiredPages': 400, 'compressorPages': 5, 'swapins': 20, 'swapouts': 30})
        value = {'intelEnvironment': {'before': rows, 'after': copy.deepcopy(rows)}}
        self.assertEqual(d.validate(value, ROOT, set()), value)
        self.assertNotIn('private', str(value))

    def test_load_and_tool_flags_are_metadata_not_process_or_ownership_proof(self):
        raw = dict(loadMilli=[2500, 1250, 3750], psSetuid=True, psSetgid=False,
                   psOwnedByRoot=True, unprivileged=True)
        row = d.intel_environment_observation('host', json.dumps(raw).encode())
        self.assertEqual({k: row[k] for k in raw}, raw)
        partial = {'intelEnvironment': {'before': {'host': row}}}
        self.assertEqual(d.validate(partial, ROOT, set()), partial)
        self.assertNotIn('executionAdmitted', str(partial))
        self.assertNotIn('processes', str(partial))
        for change in (dict(path='/private'), dict(loadMilli=[True, 0, 0]), dict(loadMilli=[1, 2]),
                       dict(psSetuid=1), dict(unprivileged=False), dict(psOwnedByRoot='private')):
            with self.assertRaises(ValueError):
                d.intel_environment_observation('host', json.dumps({**raw, **change}).encode())
        with self.assertRaises(ValueError):
            d.intel_environment_observation('host', b'{"psSetuid":true,"psSetuid":false}')

    def test_known_process_aggregates_discard_all_paths_arguments_unknown_names_and_ids(self):
        row = d.intel_environment_observation('processes',
            b' 101.1 120 R /private/path/DataMigrator\n'
            b' 0.01 40 U /another/path/DataMigrator\n'
            b' 0 50 S+ /private/path/com.apple.CoreSimulator.CoreSimulatorService\n'
            b' 99.9 999 R /private/secret-process\n'
            b' 0.0 99 S /private/DataMigrator --secret argument\n')
        self.assertEqual(row['observedProcesses'], 5)
        self.assertEqual(row['roles']['DataMigrator'], dict(count=2, cpuMilliPercent=101110,
                                                          residentKiB=160, running=1, uninterruptible=1, other=0))
        self.assertEqual(set(row['roles']), {'DataMigrator', 'com.apple.CoreSimulator.CoreSimulatorService'})
        for forbidden in ('private', 'secret', 'argument', '999', 'pid', '/path/'):
            self.assertNotIn(forbidden, str(row['roles']))

    def test_malformed_missing_excessive_or_duplicate_snapshots_fail_closed(self):
        cases = [('hardware', b''), ('hardware', b'1\n4\nextra\n'), ('hardware', b'1\n0\n'),
                 ('hardware', b'-1\n4\n'), ('memory', b''),
                 ('memory', self.MEMORY.replace(b'Pages free:', b'Missing:')),
                 ('memory', self.MEMORY.replace(b'4096 bytes', b'1234 bytes')),
                 ('memory', self.MEMORY + b'Pages active: 100.\n'),
                 ('processes', b''), ('processes', b'PID private-text\n'),
                 ('processes', b'0.0 -1 S DataMigrator\n'), ('unknown', b'0\n')]
        for kind, raw in cases:
            with self.subTest(kind=kind, raw=raw[:40]), self.assertRaises(ValueError):
                d.intel_environment_observation(kind, raw)
        with self.assertRaises(ValueError):
            d.intel_environment_observation('processes', '0 1 S DataMigrator')
        with self.assertRaises(ValueError):
            d.intel_environment_observation('processes', b'x' * (d.MAX_XML + 1))

    def test_public_schema_rejects_unknown_keys_names_boolean_counts_and_inconsistent_totals(self):
        original = {'intelEnvironment': {'before': self.observations()}}
        for mutate in (
                lambda v: v['intelEnvironment'].update(secret={}),
                lambda v: v['intelEnvironment']['before'].update(secret={}),
                lambda v: v['intelEnvironment']['before']['hardware'].update(path='/private/path'),
                lambda v: v['intelEnvironment']['before']['hardware'].update(logicalCpus=True),
                lambda v: v['intelEnvironment']['before']['memory']['fields'].update(secret=1),
                lambda v: v['intelEnvironment']['before']['processes']['roles'].update(secret={}),
                lambda v: v['intelEnvironment']['before']['processes'].update(observedProcesses=0),
                lambda v: v['intelEnvironment']['before']['processes']['roles']['DataMigrator'].update(count=2),
                lambda v: v['intelEnvironment']['before']['processes']['roles']['DataMigrator'].update(other=True),
                lambda v: v['intelEnvironment']['before']['processes'].update(sha256='private')):
            value = copy.deepcopy(original)
            mutate(value)
            with self.assertRaises(ValueError):
                d.validate(value, ROOT, set())


if __name__ == '__main__':
    unittest.main(verbosity=2)
