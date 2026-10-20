#!/usr/bin/env python3
"""Synthetic result/clock/binding controls; not an executed protocol measurement."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("probe", Path(__file__).resolve().parents[1] /
                                            "summarize-protocol-ping-latency.py")
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
COMMIT, TREE = "a" * 40, "b" * 40


def fixture():
    records = [{"kind": "identity", "sourceCommit": COMMIT, "declaredSourceTree": TREE,
                "protocol": "authenticated-v2", "topology": "same-process-two-kits-ipv4-loopback",
                "warmup": 8, "retained": 32}]
    for block, mode in enumerate((False, True, True, False)):
        records.append({"kind": "block", "block": block, "tcpNoDelay": mode,
                        "dialReadback": mode, "acceptReadback": mode, "mutualPinsVerified": True})
        for sample in range(40):
            start = block * 1000000 + sample * 1000
            records.append({"kind": "sample", "block": block, "sample": sample, "warmup": sample < 8,
                            "timesNanos": [start, start + 1, start + 2, start + sample + 3], "rttNanos": sample + 3})
        records.append({"kind": "retirement", "block": block, "closed": True, "warningsOrErrors": 0})
    return records + [{"kind": "terminal", "outcome": "PASS", "blocks": 4}]


def raw(records):
    return ("\n".join(json.dumps(record) for record in records) + "\n").encode()


class ProtocolPingLatencyTests(unittest.TestCase):
    def test_actual_boundaries_warmup_exclusion_nearest_rank_and_abba(self):
        result = p.summarize(raw(fixture()), COMMIT, TREE)
        self.assertEqual([b["tcpNoDelay"] for b in result["blocks"]], [False, True, True, False])
        for condition in result["conditions"]:
            self.assertEqual(condition["count"], 64)
            self.assertEqual(condition["minimumNanos"], 11)
            self.assertEqual(condition["medianNanos"], 26.5)
            self.assertEqual(condition["p95NanosNearestRank"], 41)

    def test_binding_mode_retirement_and_terminal_cannot_be_substituted(self):
        for index, key, value in ((0, "sourceCommit", "c" * 40), (0, "protocol", "raw-synthetic"),
                                  (1, "acceptReadback", True), (1, "mutualPinsVerified", False),
                                  (42, "closed", False), (42, "warningsOrErrors", 1), (-1, "outcome", "FAIL")):
            records = fixture()
            records[index][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.summarize(raw(records), COMMIT, TREE)

    def test_boolean_integer_substitution_cannot_pass(self):
        for index, key, value in ((1, "block", False), (1, "tcpNoDelay", 0), (1, "mutualPinsVerified", 1),
                                  (42, "closed", 1), (42, "warningsOrErrors", False)):
            records = fixture()
            records[index][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.summarize(raw(records), COMMIT, TREE)

    def test_wrong_duration_clock_order_and_sample_count_cannot_pass(self):
        for key, value in (("rttNanos", 1), ("timesNanos", [0, 2, 1, 3]), ("sample", True),
                           ("timesNanos", [0, 1, 2]), ("warmup", False)):
            records = fixture()
            records[2][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.summarize(raw(records), COMMIT, TREE)
        with self.assertRaises((ValueError, IndexError)):
            p.summarize(raw(fixture()[:-2]), COMMIT, TREE)

    def test_duplicate_truncated_and_appended_terminal_fail(self):
        good = raw(fixture())
        for data in (good[:-1], good + b'{}\n', good.replace(b'"warmup": 8', b'"warmup": 8, "warmup": 8', 1)):
            with self.assertRaises(ValueError):
                p.summarize(data, COMMIT, TREE)


if __name__ == "__main__":
    unittest.main()
