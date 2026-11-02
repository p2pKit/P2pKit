#!/usr/bin/env python3
"""Offline mailbox authorization/replay controls, not physical campaign evidence."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("test_center", Path(__file__).resolve().parents[1] / "rpc_test_center.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class Requests(unittest.TestCase):
    def test_only_predeclared_phone_profiles_and_fixed_workloads_are_admitted(self):
        value = dict(schema=1, sourceSha="a" * 40, id="b" * 32, platform="android", clients=128, mode="large", action="run")
        self.assertEqual(m.request(value, "a" * 40), value)
        for key, wrong in (("schema", True), ("schema", 2), ("sourceSha", "c" * 40), ("id", "../outside"),
                           ("platform", "mac"), ("clients", True), ("clients", 512), ("clients", 255),
                           ("mode", "shell"), ("mode", "socket-faults"), ("action", "install")):
            with self.subTest(key=key, wrong=wrong), self.assertRaises(ValueError):
                m.request(value | {key: wrong}, "a" * 40)
        for key in ("command", "settings", "deviceAddress", "identity", "arguments"):
            with self.subTest(extra=key), self.assertRaises(ValueError):
                m.request(value | {key: "/unapproved"}, "a" * 40)
        for key in value:
            edited = copy.copy(value); edited.pop(key)
            with self.subTest(missing=key), self.assertRaises(ValueError):
                m.request(edited, "a" * 40)

    def test_worker_reopen_preserves_outcomes_and_never_replays_a_started_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary).resolve()
            (state / "private").mkdir(mode=0o700)
            (state / "work").mkdir(mode=0o700)
            directory = state / "private/test-center"
            directory.mkdir(mode=0o700)
            for name in ("requests", "results", "cancel"):
                (directory / name).mkdir(mode=0o700)

            def new(path, value):
                with path.open("x") as stream:
                    json.dump(value, stream)
                path.chmod(0o600)

            def private_json(path):
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertFalse(path.is_symlink())
                return json.loads(path.read_text())

            def write(path, raw, replace=False):
                self.assertTrue(replace == path.exists())
                path.write_bytes(raw); path.chmod(0o600)

            calls = []
            def run(args):
                calls.append(args)
                output = state / "work" / ("mobile-control-" + args.run_label)
                output.mkdir(mode=0o700)
                new(output / "result.json", {"scope": "OFFLINE_NOT_PHYSICAL_EVIDENCE"})

            settings = state / "private/settings.properties"
            settings.write_bytes(b"OFFLINE_PROFILE"); settings.chmod(0o600)
            session = SimpleNamespace(state=state, source={"commit": "a" * 40}, run=run)
            campaign = SimpleNamespace(private=lambda p: None, private_json=private_json, new_json=new,
                artifact=lambda p: {"sha256": "c" * 64}, module=lambda *args: SimpleNamespace(write_private=write))
            profile = {("android", 128): (settings, {"sha256": "c" * 64})}
            value = dict(schema=1, sourceSha="a" * 40, id="b" * 32, platform="android", clients=128, mode="large", action="run")
            new(directory / "requests" / (value["id"] + ".json"), value)
            cleanup = dict(runtimeClosed=True, clientPinsRemoved=True, controlHealthy=True)

            def serve_once():
                clock = [0]
                def sleep(_): clock[0] += 2000
                with patch.object(m, "prepare_profiles", return_value=profile), \
                     patch.object(m, "safe_summary", return_value={"cleanup": cleanup}), \
                     patch.object(m.time, "monotonic", side_effect=lambda: clock[0]), \
                     patch.object(m.time, "sleep", side_effect=sleep):
                    m.serve(session, campaign, [settings], lifetime_seconds=1000)

            serve_once()
            outcome_path = directory / "results" / (value["id"] + ".json")
            original = outcome_path.read_bytes()
            self.assertEqual(private_json(outcome_path)["state"], "NeedsReview")
            self.assertEqual(len(calls), 1)
            serve_once()
            self.assertEqual(len(calls), 1)
            self.assertEqual(outcome_path.read_bytes(), original)
            interrupted = value | {"id": "d" * 32}
            new(directory / "requests" / (interrupted["id"] + ".json"), interrupted)
            new(directory / (interrupted["id"] + ".started.json"), interrupted)
            serve_once()
            self.assertEqual(len(calls), 1)
            self.assertEqual(private_json(directory / "results" / (interrupted["id"] + ".json"))["state"], "RecoveryRequired")


if __name__ == "__main__":
    unittest.main()
