#!/usr/bin/env python3
"""Source-only real-checker controls; no Kotlin build or source mutation."""
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('limits', ROOT / 'scripts/check-operational-limits.py')
limits = importlib.util.module_from_spec(spec)
spec.loader.exec_module(limits)


class LimitsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = (ROOT / limits.DOC).read_text()
        cls.rows = [line for line in cls.text.splitlines() if line.startswith('| `')]

    def test_current_source_values_and_all_citations(self):
        self.assertEqual((74, 19), limits.check())

    def test_each_changed_numeric_value_rejected(self):
        for row in self.rows:
            with self.subTest(row=row.split('|')[1]), self.assertRaisesRegex(ValueError, 'numeric value differs'):
                columns = row.split('|')
                number = re.search(r'`([0-9,]+)`', columns[2])[1]
                columns[2] = columns[2].replace(number, str(int(number.replace(',', '')) + 1), 1)
                limits.check(document=self.text.replace(row, '|'.join(columns)))

    def test_each_stale_declaration_fragment_rejected(self):
        for row in self.rows:
            with self.subTest(row=row.split('|')[1]), self.assertRaisesRegex(ValueError, 'stale declaration citation'):
                bad = re.sub(r'#L([0-9]+)(?:-L[0-9]+)?', lambda m: '#L' + str(int(m[1]) - 1), row, count=1)
                limits.check(document=self.text.replace(row, bad))

    def test_file_only_source_link_rejected(self):
        row = self.rows[0]
        with self.assertRaisesRegex(ValueError, 'requires exact line'):
            limits.check(document=self.text.replace(row, re.sub(r'#L[0-9]+', '', row)))

    def test_displayed_line_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, 'displayed citation differs'):
            limits.check(document=self.text.replace('[Config.kt:15]', '[Config.kt:16]', 1))

    def test_missing_and_duplicate_rows_rejected(self):
        with self.assertRaisesRegex(ValueError, 'inventory changed'):
            limits.check(document=self.text.replace(self.rows[0] + '\n', '', 1))
        with self.assertRaisesRegex(ValueError, 'duplicate operational setting'):
            limits.check(document=self.text + '\n' + self.rows[0])

    def test_actual_constant_change_rejected(self):
        def read(path):
            text = (ROOT / path).read_text()
            if path.name == 'Config.kt':
                text = text.replace('pingIntervalMillis: Long = 10_000', 'pingIntervalMillis: Long = 10_001')
            return text
        with self.assertRaisesRegex(ValueError, 'numeric value differs'):
            limits.check(reader=read)

    def test_supporting_excerpt_change_rejected(self):
        def read(path):
            text = (ROOT / path).read_text()
            if path.name == 'SessionProfile.kt':
                text = text.replace('maxEnrollmentSessions: Int = 4', 'maxEnrollmentSessions: Int = 3')
            return text
        with self.assertRaisesRegex(ValueError, 'supporting source excerpt changed'):
            limits.check(reader=read)

    def test_out_of_bounds_supporting_link_rejected(self):
        with self.assertRaisesRegex(ValueError, 'out of bounds'):
            limits.check(document=self.text.replace('SessionProfile.kt#L25-L49', 'SessionProfile.kt#L99999'))


if __name__ == '__main__':
    unittest.main()
