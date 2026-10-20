#!/usr/bin/env python3
"""Offline result-admission controls; these are not network or latency measurements."""
import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / 'run-tcp-nodelay-latency.py'
spec = importlib.util.spec_from_file_location('latency', path)
latency = importlib.util.module_from_spec(spec)
spec.loader.exec_module(latency)


def envelope():
    return {'schema': 1, 'scope': 'loopback-transport-only', 'warmup': 8, 'samplesPerBlock': 32,
        'blocks': [{'block': n, 'noDelay': (False, True, True, False)[n % 4],
            'acceptedNoDelay': (False, True, True, False)[n % 4],
            'writeShape': 'coalesced-40' if n < 4 else 'split-4-36',
            'nanoseconds': list(range(1, 33))} for n in range(8)]}


class ResultAdmission(unittest.TestCase):
    def test_full_interleaved_measured_inventory_is_required(self):
        rows = latency.summary(envelope())
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row['count'] == 64 and row['medianNanoseconds'] == 16.5 for row in rows))

    def test_missing_block_is_rejected(self):
        value = envelope(); value['blocks'].pop()
        with self.assertRaises(ValueError): latency.summary(value)

    def test_failed_remote_option_readback_is_rejected(self):
        value = envelope(); value['blocks'][0]['acceptedNoDelay'] = True
        with self.assertRaises(ValueError): latency.summary(value)

    def test_option_order_cannot_be_relabelled(self):
        value = envelope(); value['blocks'][0], value['blocks'][1] = value['blocks'][1], value['blocks'][0]
        with self.assertRaises(ValueError): latency.summary(value)

    def test_unknown_fields_are_rejected(self):
        for location in ('envelope', 'block'):
            value = envelope()
            (value if location == 'envelope' else value['blocks'][0])['extra'] = 1
            with self.assertRaises(ValueError): latency.summary(value)

    def test_invalid_clock_or_sample_count_is_rejected(self):
        for bad in (0, -1, True, 2_000_000_000, 1.5):
            value = envelope(); value['blocks'][0]['nanoseconds'][0] = bad
            with self.assertRaises(ValueError): latency.summary(value)
        value = envelope(); value['blocks'][0]['nanoseconds'].pop()
        with self.assertRaises(ValueError): latency.summary(value)

    def test_no_speedup_is_required_or_invented(self):
        value = envelope()
        for block in value['blocks']:
            block['nanoseconds'] = [1000 if block['noDelay'] else 100] * 32
        rows = latency.summary(value)
        self.assertEqual(rows[1]['medianNanoseconds'], 1000)
        self.assertEqual(rows[0]['medianNanoseconds'], 100)


if __name__ == '__main__':
    unittest.main()
