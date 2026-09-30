#!/usr/bin/env python3
"""Offline hosted-capacity admission/evidence controls. No products, timers or namespaces."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('capacity_job', ROOT / 'scripts/run-rpc-capacity-qualification.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def environment():
    return dict(PATH='/usr/bin:/bin', GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
                GITHUB_REPOSITORY='p2pKit/P2pKit', GITHUB_REF=c.REF, GITHUB_EVENT_NAME='push',
                GITHUB_SHA='a' * 40, GITHUB_WORKSPACE=str(ROOT), RPC_CAPACITY_REQUESTED='true')


def result():
    return dict(schema=1, scope=c.SCOPE, source={'commit': 'a' * 40, 'tree': 'b' * 40}, result='FAIL',
                commands=[], phases={}, workloads={}, foundationStatus='NOT_READY', physicalQualification=False,
                mobileCapacityQualification=False, rpcCapacityQualification=False, sourceUnchanged=True)


class HostedCapacity(unittest.TestCase):
    def test_only_the_native_nonroot_feature_runner_is_admitted(self):
        with patch.object(c.platform, 'system', return_value='Linux'), patch.object(c.platform, 'machine', return_value='x86_64'), \
             patch.object(c.os, 'getuid', return_value=1001), patch.object(c.os, 'geteuid', return_value=1001):
            c.admit(environment())
            for key, value in (('GITHUB_REF', 'refs/heads/main'), ('RUNNER_ENVIRONMENT', 'self-hosted'),
                               ('RPC_CAPACITY_REQUESTED', 'false'), ('GITHUB_REPOSITORY', 'fork/repo'),
                               ('GITHUB_EVENT_NAME', 'workflow_dispatch'), ('GITHUB_SHA', 'HEAD')):
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    c.admit({**environment(), key: value})
            for key in ('getuid', 'geteuid'):
                with patch.object(c.os, key, return_value=0), self.assertRaises(RuntimeError):
                    c.admit(environment())
            with patch.object(c.platform, 'machine', return_value='aarch64'), self.assertRaises(RuntimeError):
                c.admit(environment())

    def test_namespace_setup_does_not_change_host_security_or_reassign_source_ownership(self):
        env = {**environment(), 'JAVA_HOME': '/jdk', 'GH_TOKEN': 'private', 'PYTHONPATH': '/untrusted',
               'P2PKIT_AUDIT_OWNERSHIP_CHAIN': 'not-inherited', 'LD_PRELOAD': '/untrusted'}
        command = c.namespace_command(env, Path('/fixture'), 'steady', 1001, 1001, '/python')
        self.assertEqual(command[:4], ['/usr/bin/sudo', '-n', '/usr/bin/env', '-i'])
        self.assertIn('SUDO_UID=1001', command)
        self.assertIn('SUDO_GID=1001', command)
        self.assertIn('JAVA_HOME=/jdk', command)
        for item in command:
            if item != 'private':  # mount propagation is explicitly private
                self.assertNotIn('private', item)
            self.assertNotIn('untrusted', item)
            self.assertNotIn('not-inherited', item)
        for forbidden in ('--user', '--map-root-user', '--map-users', 'chown', 'sysctl', 'iptables', 'setfacl', 'nsenter'):
            self.assertFalse(any(forbidden in item for item in command))
        self.assertIn('--mount-proc', command)
        self.assertIn('--pid', command)
        self.assertIn('--net', command)
        self.assertIn('--owner-authorized-same-host', command)
        for uid, gid, mode in ((0, 1001, 'steady'), (1001, 0, 'steady'), (True, 1001, 'steady'), (1001, 1001, 'short')):
            with self.assertRaises(RuntimeError):
                c.namespace_command(env, Path('/fixture'), mode, uid, gid, '/python')

    def test_regression_requires_actual_model_and_all_four_fresh_jvm_executions(self):
        policy = json.loads((ROOT / 'gradle/platform-test-policy.json').read_text())
        tasks = {t for m in policy['model'].values() for t in m['tests']}
        records = {t: dict(enabled=True, inGraph=False, outcome='NOT_REQUESTED', passed=0, failed=0, skipped=0) for t in tasks}
        for name in c.MODULES:
            records[':' + name + ':jvmTest'].update(inGraph=True, outcome='EXECUTED', passed=3)
        report = dict(schema=1, token='a' * 32, dryRun=False, buildFailed=False, model=policy['model'],
                      host={'os': 'Linux', 'arch': 'amd64'}, tests=records)
        self.assertEqual(len(c.jvm_execution(report, policy, 'a' * 32)), 4)
        for key, value in (('token', 'b' * 32), ('dryRun', True), ('buildFailed', True), ('schema', True),
                           ('host', {'os': 'Mac OS X', 'arch': 'x86_64'}), ('model', {})):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.jvm_execution({**report, key: value}, policy, 'a' * 32)
        for key, value in (('passed', 0), ('passed', True), ('failed', 1), ('skipped', 1), ('inGraph', False),
                           ('outcome', 'UP-TO-DATE'), ('outcome', 'FROM-CACHE'), ('enabled', False)):
            changed = copy.deepcopy(report)
            changed['tests'][':p2p-rpc:jvmTest'][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.jvm_execution(changed, policy, 'a' * 32)

    def test_failed_and_partial_results_cannot_award_capacity_or_release_qualification(self):
        r = result()
        public = c.public_result(r, [], {}, False)
        self.assertEqual(public['result'], 'FAIL')
        self.assertFalse(public['rpcCapacityQualification'])
        self.assertEqual(public['foundationStatus'], 'NOT_READY')
        for key, value in (('scope', 'PHYSICAL'), ('foundationStatus', 'READY'), ('physicalQualification', True),
                           ('schema', True), ('source', {'commit': 'private', 'tree': 'b' * 40}),
                           ('mobileCapacityQualification', True), ('rpcCapacityQualification', True), ('secret', 'never-export'),
                           ('phases', {'private-label': 'PASS'}), ('nativeControlTests', 120),
                           ('result', 'MECHANICAL_AND_CLEANUP_PASS_PENDING_RESOURCE_REVIEW')):
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                c.public_result({**r, key: value}, [], {}, False)

    def test_public_hashes_and_environment_cannot_contain_arbitrary_data(self):
        for key in ('jvmExecutionSha256', 'distributionManifestSha256'):
            for value in (True, 'not-a-hash', 'a' * 63):
                with self.assertRaises(RuntimeError):
                    c.public_result({**result(), key: value}, [], {}, False)
        with self.assertRaises(RuntimeError):
            c.public_result({**result(), 'environment': {'raw': 'private'}}, [], {}, False)

    def test_native_failure_observations_do_not_become_admitted_counts_or_leak_text(self):
        value = {**result(), 'nativeAttempt': {'reportedTests': 121, 'status': 'FAIL_OUTPUT_ONLY', 'executionAdmitted': False},
                 'controlFailures': [], 'controlDiagnostics': []}
        public = c.public_result(value, [], {}, False)
        self.assertEqual(public['nativeAttempt'], value['nativeAttempt'])
        self.assertNotIn('nativeControlTests', public)
        for field, bad in (('controlFailures', [{'raw': 'private'}]), ('controlDiagnostics', [{'secret': 'private'}]),
                           ('nativeAttempt', {**value['nativeAttempt'], 'executionAdmitted': True})):
            with self.assertRaises(RuntimeError):
                c.public_result({**value, field: bad}, [], {}, False)

    def test_missing_attempt_measurement_stays_unadmitted_not_zero_or_passing(self):
        with tempfile.TemporaryDirectory() as name:
            state = Path(name)
            value = c.failed_attempt(state, 'steady', 1)
            self.assertEqual(value['result'], 'FAIL')
            self.assertIsNone(value['measurement'])
            self.assertEqual(value['sourceSites'], [])
            self.assertIn('UNADMITTED', value['scope'])

    def test_workflow_has_one_opt_in_runner_and_only_the_sanitized_output(self):
        workflow = (ROOT / '.github/workflows/rpc-capacity.yml').read_text()
        for value in ('contents: read', 'cancel-in-progress: false', 'runs-on: ubuntu-24.04',
                      'persist-credentials: false', 'fetch-tags: false', 'git fetch --no-tags --unshallow',
                      "contains(github.event.head_commit.message, '[rpc-capacity]')",
                      'path: ${{ env.RPC_CAPACITY_PARENT }}/public/summary.json',
                      'scripts/run-rpc-capacity-qualification.py run', 'scripts/run-rpc-capacity-qualification.py collect'):
            self.assertIn(value, workflow)
        for forbidden in ('secrets.', 'actions/cache', 'setfacl', 'sysctl', '/evidence/**', 'cancel-in-progress: true',
                          'pull_request:', 'workflow_dispatch:', 'continue-on-error:'):
            self.assertNotIn(forbidden, workflow)
        for line in workflow.splitlines():
            if 'uses:' in line:
                self.assertRegex(line, r'uses: [A-Za-z0-9/-]+@[0-9a-f]{40} #')

    def test_all_products_use_original_native_owner_and_original_full_workloads(self):
        source = (ROOT / 'scripts/run-rpc-capacity-qualification.py').read_text()
        self.assertIn('self.checker.validate(proof, code, purpose', source)
        self.assertIn('proof[\'ancestorInvocationIds\'] == []', source)
        self.assertIn("q.control_inventory('linux-x64')", source)
        self.assertIn("same.retention_admission(raw['postRetention']['before']", source)
        self.assertIn("checker.validate(proof, code, purpose", source)
        for forbidden in ('killpg(', 'os.kill(', '.terminate(', 'RpcTestLink', '--duration', '--calls-per-second'):
            self.assertNotIn(forbidden, source)


if __name__ == '__main__':
    unittest.main()
