"""Two bounded OFFLINE MODEL phases; no production authority or clock restoration."""
import hashlib
import json
import os
from pathlib import Path
import stat
import time


def install(module, work, source):
    metadata = work / 'retained-synthetic-graph.json'
    script = source / 'scripts/run-hosted-initial-recipient.py'
    tests = source / 'scripts/tests/hosted-initial-recipient-original-graph-test.py'
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()
    def inventory(root):
        result = {}
        for path in sorted([root, *root.rglob('*')]):
            info = path.lstat()
            assert not stat.S_ISLNK(info.st_mode)
            name = str(path.relative_to(root))
            result[name] = {'identity': [info.st_dev, info.st_ino], 'mode': stat.S_IMODE(info.st_mode),
                'sha256': digest(path) if stat.S_ISREG(info.st_mode) else None,
                'size': info.st_size if stat.S_ISREG(info.st_mode) else None}
        return result

    class FixturePrepareModels(module.OriginalGraphModels):
        def test_prepare_and_close_synthetic_graph(self):
            self.assertFalse(metadata.exists(), 'never overwrite a retained fixture declaration')
            before = time.process_time()
            self.graph()
            self.reader.close()
            self.assertTrue(self.reader.closed)
            self.assertFalse(self.reader.unknown)
            self.assertTrue(all(row['attempted'] and row['closed'] for row in self.reader.resources))
            self.assertTrue(all(query.closed and not query.unknown for query in self.complete_queries))
            self.assertTrue(all(scope.closed for scope in self.query_scopes))
            (self.recipient_path / 'crypto/unbound-fixture-only').write_bytes(b'DO_NOT_READ_THIS_MODEL_FILE')
            contents = {'scope': 'SYNTHETIC_TEST_FIXTURE_ONLY_NOT_AUTHORITY', 'base': str(self.base),
                'sourceRoot': str(module.N.ROOT), 'scriptSha256': digest(script), 'testsSha256': digest(tests),
                'senderSha256': self.sha, 'modeledNs': self.fixture.ns, 'inventory': inventory(self.base)}
            with metadata.open('x') as output:
                json.dump(contents, output, sort_keys=True, separators=(',', ':'))
            metadata.chmod(0o600)
            # Retain only the owned tiny model tree. All normal resource/model
            # cleanup still runs; there is no actual native worker or capability.
            original_cleanup = self.temp.cleanup
            self._cleanups[:] = [entry for entry in self._cleanups if entry[0] != original_cleanup]
            self.temp._finalizer.detach()
            print('SYNTHETIC_FIXTURE_PREPARED_CLOSED CPU_SECONDS=%.6f FILES=%d DECLARATION_SHA256=%s' %
                (time.process_time() - before, sum(value['sha256'] is not None for value in contents['inventory'].values()), digest(metadata)), flush=True)

    class FixtureReaderModels(module.OriginalGraphModels):
        def graph(self):
            contents = json.loads(metadata.read_text())
            self.assertEqual(contents['scope'], 'SYNTHETIC_TEST_FIXTURE_ONLY_NOT_AUTHORITY')
            self.assertEqual(contents['sourceRoot'], str(module.N.ROOT))
            self.assertEqual(contents['scriptSha256'], digest(script))
            self.assertEqual(contents['testsSha256'], digest(tests))
            root = Path(contents['base'])
            self.assertEqual(root.parent, work)
            self.assertEqual(inventory(root), contents['inventory'])
            self.choose('worker', 'desktop-linux-x64')
            os.environ['RUNNER_TEMP'] = str(root)
            os.environ.pop(module.O.wire.TOKEN_ENV, None)
            self.fixture.ns = contents['modeledNs']
            self.recipient_path = module.N._recipient_path()
            self.sender_path = self.recipient_path.with_name(self.recipient_path.name + '-output')
            self.preparation_path = self.recipient_path.with_name(self.recipient_path.name.removesuffix('-recipient'))
            self.entry_path = self.preparation_path.with_name(self.preparation_path.name + '-entry')
            self.sha = contents['senderSha256']
            self.assertEqual(digest(self.sender_path / 'sender-pending.json'), self.sha)
            self.assertFalse(any(getattr(module.N, name) for name in
                ('_PREPARED_RETURNS', '_READMISSION_RETURNS', '_AUTHORITY_RETURNS', '_RECIPIENT_RETURNS', '_RECIPIENT_SENDERS')))
            self.start_reader()  # Fresh MODEL owner only, never reconstructed originals/authority.
            self.prepared_contents = contents

        def test_complete_fixed_graph_from_closed_synthetic_fixture(self):
            before = time.process_time()
            module.OriginalGraphModels.test_complete_1066_original_graph_has_no_authority_and_bounded_rereads(self)
            self.assertEqual(inventory(Path(self.prepared_contents['base'])), self.prepared_contents['inventory'])
            print('SYNTHETIC_READER_ONLY_COMPLETE CPU_SECONDS=%.6f ORIGINALS=1066 AUTHORITY=NONE' %
                (time.process_time() - before), flush=True)

        def test_decoded_recipient_identity_requires_exact_scalar_types(self):
            module.OriginalGraphModels.test_decoded_recipient_identity_requires_exact_scalar_types(self)
            self.assertEqual(inventory(Path(self.prepared_contents['base'])), self.prepared_contents['inventory'])

        def test_earlier_query_original_is_reread_after_later_leaf_traversal(self):
            module.OriginalGraphModels.test_earlier_query_original_is_reread_after_later_leaf_traversal(self)
            root = Path(self.prepared_contents['base'])
            before, after = self.prepared_contents['inventory'], inventory(root)
            changed = str((self.preparation_path / 'source-before/owner.json').relative_to(root))
            self.assertEqual(set(after), set(before))
            self.assertEqual({name for name in before if before[name] != after[name]}, {changed})
            self.assertEqual(after[changed]['identity'], before[changed]['identity'])
            self.assertEqual(after[changed]['mode'], before[changed]['mode'])
            self.assertNotEqual(after[changed]['sha256'], before[changed]['sha256'])

    module.FixturePrepareModels = FixturePrepareModels
    module.FixtureReaderModels = FixtureReaderModels
