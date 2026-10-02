#!/usr/bin/env python3
"""Offline data-only wrapper input controls; no Gradle, network or native receipt."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('gradle_distribution_test', ROOT / 'scripts/rpc_gradle_distribution.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Distribution(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.root = self.base / 'repo'
        (self.root / 'gradle/wrapper').mkdir(parents=True)
        self.properties = self.root / 'gradle/wrapper/gradle-wrapper.properties'
        self.payload = b'OFFLINE PINNED DATA, NEVER EXTRACTED OR EXECUTED\n'
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.properties.write_text((ROOT / 'gradle/wrapper/gradle-wrapper.properties').read_text().replace(
            '84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae', self.sha))
        self.source = self.base / 'input.zip'
        self.source.write_bytes(self.payload)
        self.source.chmod(0o600)
        self.parent = self.base / 'request'
        self.parent.mkdir(mode=0o700)
        self.state = self.parent / 'state'
        self.home = self.state / 'gradle-home'

    def context(self):
        self.state.mkdir(mode=0o700)
        self.home.mkdir(mode=0o700)
        policy = self.home / 'gradle.properties'
        policy.write_bytes(b'OFFLINE admitted home policy\n')
        policy.chmod(0o600)
        return dict(root=str(self.root), gradleHome=str(self.home),
                    gradlePropertiesSha256=hashlib.sha256(policy.read_bytes()).hexdigest())

    def prepared(self):
        return m.prepare_archive(self.root, self.source, self.parent)

    def test_actual_source_pin_and_wrapper_cache_key_match_failed_wrapper_observation(self):
        policy = m.wrapper_policy(ROOT)
        self.assertEqual(policy['sha256'], '84fbba45c7f4c64abc77460e1c00f541e9f960e3c7ed2538f1ede19eacd873ae')
        self.assertEqual(policy['url'], 'https://services.gradle.org/distributions/gradle-9.7.0-bin.zip')
        self.assertEqual(policy['zipRelative'],
            'wrapper/dists/gradle-9.7.0-bin/d4tj7w02tcgubx9zk9hbippn6/gradle-9.7.0-bin.zip')

    def test_closed_wrapper_properties_reject_missing_duplicate_extra_or_changed_layout(self):
        original = self.properties.read_text()
        alternatives = [original + 'unknown=true\n', original + 'networkTimeout=10000\n',
            original.replace('distributionSha256Sum=', 'missing='),
            original.replace('zipStorePath=wrapper/dists', 'zipStorePath=../shared'),
            original.replace('distributionBase=GRADLE_USER_HOME', 'distributionBase=PROJECT'),
            original.replace('validateDistributionUrl=true', 'validateDistributionUrl=false'),
            original.replace('networkTimeout=10000', 'networkTimeout=0')]
        for raw in alternatives:
            with self.subTest(raw=raw):
                self.properties.write_text(raw)
                with self.assertRaises(RuntimeError):
                    m.wrapper_policy(self.root)

    def test_url_and_checksum_cannot_add_redirect_credentials_queries_or_unsigned_inputs(self):
        original = self.properties.read_text()
        for old, new in [('https\\:', 'http\\:'), ('services.gradle.org', 'example.invalid'),
                         ('services.gradle.org', 'user@services.gradle.org'),
                         ('-bin.zip\n', '-bin.zip?other=yes\n'),
                         (self.sha, self.sha.upper()), (self.sha, 'none')]:
            with self.subTest(new=new):
                self.properties.write_text(original.replace(old, new))
                with self.assertRaises(RuntimeError):
                    m.wrapper_policy(self.root)

    def test_prepare_copies_only_complete_verified_data_without_children_or_extraction(self):
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('No child permitted')):
            record = self.prepared()
        self.assertEqual((self.parent / record['archive']).read_bytes(), self.payload)
        self.assertEqual(record['bytes'], len(self.payload))
        self.assertEqual(record['sha256'], self.sha)
        self.assertEqual(set(p.name for p in self.parent.iterdir()), {record['archive']})
        self.assertEqual((self.parent / record['archive']).stat().st_mode & 0o777, 0o600)
        self.assertFalse(self.state.exists())
        self.assertEqual(self.source.read_bytes(), self.payload)

    def test_corrupt_input_is_retained_but_never_admitted(self):
        self.source.write_bytes(b'WRONG PIN')
        with self.assertRaises(RuntimeError):
            self.prepared()
        self.assertEqual(self.source.read_bytes(), b'WRONG PIN')
        self.assertFalse((self.parent / 'prepared.json').exists())

    def test_input_and_destination_are_create_only_no_symlink_or_hardlink_adoption(self):
        linked = self.base / 'link.zip'
        linked.symlink_to(self.source)
        with self.assertRaises(RuntimeError):
            m.prepare_archive(self.root, linked, self.parent)
        linked.unlink()
        os.link(self.source, linked)
        with self.assertRaises(RuntimeError):
            self.prepared()
        linked.unlink()
        record = self.prepared()
        with self.assertRaises(FileExistsError):
            self.prepared()
        self.assertEqual((self.parent / record['archive']).read_bytes(), self.payload)

    def test_nonprivate_foreign_special_or_oversized_input_is_refused_before_copy(self):
        self.source.chmod(0o644)
        with self.assertRaises(RuntimeError):
            self.prepared()
        self.source.chmod(0o600)
        with patch.object(m, 'MAX_ARCHIVE', len(self.payload) - 1), self.assertRaises(RuntimeError):
            self.prepared()
        with patch.object(m.os, 'getuid', return_value=os.getuid() + 1), self.assertRaises(RuntimeError):
            self.prepared()
        self.source.unlink()
        os.mkfifo(self.source, 0o600)
        with self.assertRaises(RuntimeError):
            self.prepared()
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_symlinked_ancestor_and_shared_request_directory_are_refused(self):
        alias = self.base / 'alias'
        alias.symlink_to(self.base, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            m.prepare_archive(self.root, alias / 'input.zip', self.parent)
        self.parent.chmod(0o755)
        with self.assertRaises(RuntimeError):
            self.prepared()

    def test_replaced_input_path_during_read_is_not_a_valid_unchanged_archive(self):
        read = os.read
        original_inode = self.source.stat().st_ino
        replaced = False

        def replacing_read(fd, count):
            nonlocal replaced
            data = read(fd, count)
            if not replaced and os.fstat(fd).st_ino == original_inode:
                self.source.rename(self.base / 'original.zip')
                self.source.write_bytes(self.payload)
                self.source.chmod(0o600)
                replaced = True
            return data

        with patch.object(m.os, 'read', side_effect=replacing_read), self.assertRaises(RuntimeError):
            self.prepared()
        self.assertTrue(replaced)

    def test_copy_corruption_is_detected_by_actual_readback_not_source_hash_alone(self):
        write = os.write

        def corrupting_write(fd, data):
            return write(fd, b'!' * len(data))

        with patch.object(m.os, 'write', side_effect=corrupting_write), self.assertRaises(RuntimeError):
            self.prepared()
        self.assertEqual(self.source.read_bytes(), self.payload)
        copies = list(self.parent.iterdir())
        self.assertEqual(len(copies), 1)
        self.assertEqual(copies[0].read_bytes(), b'!' * len(self.payload))

    def test_partial_writes_are_completed_but_zero_progress_is_not_retried(self):
        write = os.write
        with patch.object(m.os, 'write', side_effect=lambda fd, data: write(fd, data[:3])):
            record = self.prepared()
        self.assertEqual((self.parent / record['archive']).read_bytes(), self.payload)
        another = self.base / 'failed-request'
        another.mkdir(mode=0o700)
        with patch.object(m.os, 'write', return_value=0) as stalled, self.assertRaises(RuntimeError):
            m.prepare_archive(self.root, self.source, another)
        stalled.assert_called_once()
        self.assertEqual(len(list(another.iterdir())), 1)

    def test_prepared_record_is_exact_and_rechecked_against_current_pin_and_bytes(self):
        record = self.prepared()
        self.assertEqual(m.admit_archive(self.root, self.parent, record), self.parent / record['archive'])
        for change in (dict(archive='../input.zip'), dict(bytes=True), dict(sha256='a' * 64),
                       dict(extra=True), dict(policy=record['policy'] | {'url': 'https://example.invalid'})):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.admit_archive(self.root, self.parent, record | change)
        (self.parent / record['archive']).write_bytes(b'CHANGED')
        with self.assertRaises(RuntimeError):
            m.admit_archive(self.root, self.parent, record)

    def test_changed_wrapper_properties_invalidate_prepared_input(self):
        record = self.prepared()
        self.properties.write_text(self.properties.read_text() + '\n')
        with self.assertRaises(RuntimeError):
            m.admit_archive(self.root, self.parent, record)

    def test_stage_only_a_zip_in_exact_empty_home_no_ok_marker_or_extracted_runtime(self):
        record = self.prepared()
        context = self.context()
        with patch.object(subprocess, 'Popen', side_effect=AssertionError('No child permitted')):
            staged = m.stage_archive(self.root, self.parent, record, self.state, context)
        target = self.home / record['policy']['zipRelative']
        self.assertEqual(target.read_bytes(), self.payload)
        self.assertEqual(staged['sha256'], self.sha)
        self.assertFalse(staged['extracted'])
        self.assertFalse(staged['nativeAdmission'])
        self.assertEqual({str(p.relative_to(self.home)) for p in self.home.rglob('*') if p.is_file()},
                         {'gradle.properties', record['policy']['zipRelative']})

    def test_existing_wrapper_state_is_preserved_and_never_reused_or_cleaned(self):
        record = self.prepared()
        context = self.context()
        old = self.home / 'wrapper'
        old.mkdir(mode=0o700)
        (old / 'old.part').write_bytes(b'OLD FAILURE')
        with self.assertRaises(RuntimeError):
            m.stage_archive(self.root, self.parent, record, self.state, context)
        self.assertEqual((old / 'old.part').read_bytes(), b'OLD FAILURE')
        self.assertEqual(list(old.iterdir()), [old / 'old.part'])

    def test_foreign_home_policy_and_alternate_root_are_rejected_without_staging(self):
        record = self.prepared()
        context = self.context()
        for change in (dict(gradleHome=str(self.base)), dict(root=str(self.base)),
                       dict(gradlePropertiesSha256='a' * 64)):
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                m.stage_archive(self.root, self.parent, record, self.state, context | change)
        self.assertFalse((self.home / 'wrapper').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
