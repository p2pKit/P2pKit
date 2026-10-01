#!/usr/bin/env python3
"""Offline controls only. No Java, SDK, subprocess workload, network or capacity claims."""

import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("capacity_lab", ROOT / "scripts/run-rpc-capacity-lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
SOURCE = "a" * 40


class LabControls(unittest.TestCase):
    def test_cpu_placement_is_explicit_and_cannot_change_the_workload_or_native_owner(self):
        import inspect
        self.assertEqual(inspect.signature(lab.execute).parameters['cpu_placement'].default, 'inherited')
        source = (ROOT / 'scripts/run-rpc-capacity-lab.py').read_text()
        selected = source.index('placement = cpu.begin(cpu_placement, role)')
        started = source.index('child = subprocess.Popen(argv', selected)
        sampled = source.index('cpu.observe_child(placement, child)', started)
        waited = source.index('child.wait(timeout=10)', sampled)
        finished = source.index('cpu.finish(placement)', waited)
        self.assertLess(selected, started)
        self.assertLess(sampled, waited)
        self.assertLess(waited, finished)
        for option in ('-Xms128m', '-Xmx2048m', 'time.monotonic() - started < 2450'):
            self.assertIn(option, source)
        for tuning in ('ActiveProcessorCount', 'kotlinx.coroutines.scheduler', 'os.nice(', 'sched_setscheduler('):
            self.assertNotIn(tuning, source)

    def test_profile_is_bounded_diagnostic_sampling_not_a_reduced_workload_or_gc_tuning(self):
        for mode in ('correctness', 'large'):
            self.assertEqual(lab.profile_options(self.root, mode), [])
        repository, option = lab.profile_options(self.root, 'steady')
        self.assertEqual(repository, '-XX:FlightRecorderOptions=repository=' + str(self.root / 'jfr-repository'))
        self.assertIn('delay=120s,duration=180s,maxsize=32m,disk=true,dumponexit=true', option)
        self.assertIn(str(self.root / 'runtime-profile.jfr'), option)
        self.assertNotIn('UseG1', option)
        self.assertNotIn('Xmx', option)
        with self.assertRaises(RuntimeError):
            lab.profile_options(self.root, 'short-capacity')
        with self.assertRaises(RuntimeError):
            lab.profile_options(self.root / 'injected,duration=1s', 'steady')
        events = ET.parse(ROOT / 'scripts/rpc-capacity-profile.jfc').getroot().findall('event')
        self.assertEqual({e.attrib['name'] for e in events},
                         {'jdk.ExecutionSample', 'jdk.NativeMethodSample', 'jdk.ThreadPark', 'jdk.JavaMonitorEnter', 'jdk.CPULoad'})
        self.assertEqual(len(events), 5)
        for event in events:
            settings = {s.attrib['name']: s.text for s in event.findall('setting')}
            self.assertEqual(settings['enabled'], 'true')
            if event.attrib['name'] == 'jdk.CPULoad':
                self.assertEqual(settings['period'], '1 s')
            elif event.attrib['name'].endswith('Sample'):
                self.assertEqual(settings['period'], '20 ms')
            else:
                self.assertEqual(settings['threshold'], '20 ms')
        for name in ('runtime-profile.jfr', 'runtime-profile.json', 'profile-analysis.log'):
            path = self.root / name
            path.write_bytes(b'existing evidence')
            with self.assertRaises(RuntimeError):
                lab.profile_options(self.root, 'steady')
            path.unlink()
        (self.root / 'jfr-repository').symlink_to(self.root / 'absent')
        with self.assertRaises(RuntimeError):
            lab.profile_options(self.root, 'steady')

    def test_correctness_requires_an_explicit_distinct_entrypoint_and_keeps_capacity_unchanged(self):
        for mode in ('steady', 'large'):
            self.assertEqual(lab.workload_entrypoint('client', mode),
                             ('dev.p2pkit.sample.rpc.RpcCapacityMainKt', ['--owner-authorized-capacity-run', '--' + mode]))
            self.assertEqual(lab.workload_entrypoint('host', mode),
                             ('dev.p2pkit.sample.rpc.lab.LabHostKt', ['--owner-authorized-capacity-host']))
        self.assertEqual(lab.workload_entrypoint('client', 'correctness'),
                         ('dev.p2pkit.sample.rpc.lab.LabRpcChecksKt', ['--owner-authorized-correctness-run']))
        self.assertEqual(lab.workload_entrypoint('host', 'correctness'),
                         ('dev.p2pkit.sample.rpc.lab.LabHostKt', ['--owner-authorized-correctness-host']))
        for role, mode in (('peer', 'correctness'), ('host', 'anything'), ('client', '--unsafe')):
            with self.assertRaises(RuntimeError):
                lab.workload_entrypoint(role, mode)

    def test_all_six_exact_real_socket_cases_are_required_not_just_exit_zero(self):
        result = dict(schema=1, mode='correctness', scope='REAL_SOCKET_CORRECTNESS_NOT_CAPACITY',
                      status='PENDING_RESOURCE_AND_NETWORK_REVIEW', capacityQualified=False,
                      expectedCases=6, passedCases=list(lab.CORRECTNESS_CASES))
        self.assertTrue(lab.correctness_result(result))
        for changes in ({'schema': True}, {'expectedCases': 5}, {'passedCases': list(lab.CORRECTNESS_CASES[:-1])},
                        {'passedCases': list(lab.CORRECTNESS_CASES) + ['skipped']}, {'private': 'must-not-be-accepted'},
                        {'mode': 'steady'}, {'capacityQualified': True}, {'capacityQualified': 0}, {'status': 'FAIL'}):
            self.assertFalse(lab.correctness_result({**result, **changes}))
        for missing in (None, {}, [], True):
            self.assertFalse(lab.correctness_result(missing))

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rpc-capacity-controls-")
        self.root = Path(self.temporary.name).resolve()
        self.root.chmod(0o700)

    def tearDown(self):
        self.temporary.cleanup()

    def settings(self):
        return dict(schema="1", role="client", runLabel="unit-test", sourceSha=SOURCE,
                    endpointAddress="10.25.0.2", port="48123", subnets="10.25.0.0/24",
                    interface="eth0", localAddress="10.25.0.3")

    def test_exact_source_and_explicit_private_configuration(self):
        expected = self.settings()
        self.assertEqual(expected, lab.configuration(lab.parse(lab.encode(expected)), SOURCE))
        with self.assertRaises(RuntimeError):
            lab.configuration(expected, "b" * 40)

    def test_refuse_public_loopback_dns_and_unapproved_destinations(self):
        for address in ("127.0.0.1", "8.8.8.8", "169.254.1.2", "example.test", "198.18.0.1", "10.26.0.2", "::1"):
            with self.subTest(address=address), self.assertRaises((RuntimeError, ValueError)):
                lab.configuration({**self.settings(), "endpointAddress": address}, SOURCE)

    def test_invalid_subnets_roles_ports_and_extra_fields_fail_closed(self):
        for changes in ({"role": "mesh"}, {"port": "22"}, {"port": "65536"}, {"port": "04812"},
                        {"subnets": "0.0.0.0/0"}, {"subnets": "10.25.0.1/24"}, {"extra": "unsafe"},
                        {"runLabel": "private-user@example"}, {"interface": "en0;command"}):
            with self.subTest(changes=changes), self.assertRaises((RuntimeError, ValueError)):
                lab.configuration({**self.settings(), **changes}, SOURCE)

    def test_control_parser_rejects_duplicate_fields_and_unbounded_inputs(self):
        for data in (b"x=1\nx=2\n", b"x=\n", b"x=value\r\n", b"x=\0secret\n", b"a" * (lab.LIMIT + 1)):
            with self.subTest(length=len(data)), self.assertRaises(RuntimeError):
                lab.parse(data)

    def test_private_file_round_trip_does_not_replace_without_permission(self):
        path = self.root / "control.txt"
        lab.write_private(path, b"x=1\n")
        self.assertEqual(b"x=1\n", lab.read_private(path))
        self.assertEqual(0o600, path.stat().st_mode & 0o777)
        with self.assertRaises(FileExistsError):
            lab.write_private(path, b"x=2\n")
        lab.write_private(path, b"x=3\n", replace=True)
        self.assertEqual(b"x=3\n", lab.read_private(path))

    def test_atomic_telemetry_publication_is_reobserved_without_consuming_changed_lifetime(self):
        path = self.root / "host-telemetry.txt"
        replacement = self.root / "next"
        lab.write_private(path, b"sequence=1\n")
        lab.write_private(replacement, b"sequence=2\n")
        original, opened = os.open, []

        def open_at_publication(name, *args, **kwargs):
            if name == path:
                if not opened:
                    os.replace(replacement, path)  # Exactly between lstat and open, as in the failed run.
                else:
                    with self.assertRaises(OSError):
                        os.fstat(opened[-1])  # The rejected observation did not leak its descriptor.
                descriptor = original(name, *args, **kwargs)
                opened.append(descriptor)
                return descriptor
            return original(name, *args, **kwargs)

        with patch.object(lab.os, "open", side_effect=open_at_publication):
            self.assertEqual(lab.read_telemetry(path), b"sequence=2\n")
        self.assertEqual(len(opened), 2)
        with self.assertRaises(OSError):
            os.fstat(opened[-1])

    def test_immutable_control_lifetime_changes_still_fail_without_reobservation(self):
        path, replacement = self.root / "client-pins.txt", self.root / "next"
        lab.write_private(path, b"original\n")
        lab.write_private(replacement, b"replacement\n")
        original, observed = os.open, []

        def replace_once(name, *args, **kwargs):
            if name == path:
                observed.append(True)
                os.replace(replacement, path)
            return original(name, *args, **kwargs)

        with patch.object(lab.os, "open", side_effect=replace_once), \
                self.assertRaisesRegex(lab.ControlFileLifetimeChanged, "Control file lifetime changed"):
            lab.read_private(path)
        self.assertEqual(observed, [True])
        with patch.object(lab, "read_private") as read:
            for name in ("client-pins.txt", "config.txt", "host-ready.txt", "stop.txt", "receipt.json"):
                with self.assertRaisesRegex(RuntimeError, "Only host telemetry"):
                    lab.read_telemetry(self.root / name)
            read.assert_not_called()

    def test_continuously_replaced_telemetry_still_fails_after_three_complete_observations(self):
        path = self.root / "host-telemetry.txt"
        lab.write_private(path, b"sequence=0\n")
        replacements = [self.root / str(n) for n in range(3)]
        for n, replacement in enumerate(replacements):
            lab.write_private(replacement, f"sequence={n + 1}\n".encode())
        original, observed = os.open, []

        def replace_each_time(name, *args, **kwargs):
            if name == path:
                os.replace(replacements[len(observed)], path)
                observed.append(True)
            return original(name, *args, **kwargs)

        with patch.object(lab.os, "open", side_effect=replace_each_time), \
                self.assertRaises(lab.ControlFileLifetimeChanged):
            lab.read_telemetry(path)
        self.assertEqual(len(observed), 3)

    def test_replacement_with_wrong_permissions_fails_immediately_before_reobservation(self):
        path, replacement = self.root / "host-telemetry.txt", self.root / "next"
        lab.write_private(path, b"sequence=1\n")
        lab.write_private(replacement, b"sequence=2\n")
        replacement.chmod(0o644)
        original, observed = os.open, []

        def replace_with_unprotected_file(name, *args, **kwargs):
            if name == path:
                os.replace(replacement, path)
                observed.append(True)
            return original(name, *args, **kwargs)

        with patch.object(lab.os, "open", side_effect=replace_with_unprotected_file), \
                self.assertRaisesRegex(RuntimeError, "Opened control file must be owned"):
            lab.read_telemetry(path)
        self.assertEqual(observed, [True])

    def test_symlink_or_fifo_replacement_is_not_followed_retried_or_allowed_to_block(self):
        path, target = self.root / "host-telemetry.txt", self.root / "other"
        lab.write_private(target, b"must-not-be-consumed\n")
        original = os.open
        for kind in ("symlink", "fifo"):
            with self.subTest(kind=kind):
                lab.write_private(path, b"sequence=1\n")
                observed = []

                def replace_with_nonfile(name, flags, *args, **kwargs):
                    if name == path:
                        self.assertTrue(flags & os.O_NOFOLLOW)
                        self.assertTrue(flags & os.O_NONBLOCK)
                        path.unlink()
                        path.symlink_to(target) if kind == "symlink" else os.mkfifo(path, 0o600)
                        observed.append(True)
                    return original(name, flags, *args, **kwargs)

                with patch.object(lab.os, "open", side_effect=replace_with_nonfile), \
                        self.assertRaises((OSError, RuntimeError)):
                    lab.read_telemetry(path)
                self.assertEqual(observed, [True])
                path.unlink()
        self.assertEqual(lab.read_private(target), b"must-not-be-consumed\n")

    def test_opened_descriptor_owner_is_checked_independently(self):
        path = self.root / "host-telemetry.txt"
        lab.write_private(path, b"sequence=1\n")
        original = os.fstat

        def foreign_owner(descriptor):
            from types import SimpleNamespace
            row = original(descriptor)
            return SimpleNamespace(st_mode=row.st_mode, st_uid=os.getuid() + 1)

        with patch.object(lab.os, "fstat", side_effect=foreign_owner) as observed, \
                self.assertRaisesRegex(RuntimeError, "Opened control file must be owned"):
            lab.read_telemetry(path)
        self.assertEqual(observed.call_count, 1)

    def test_in_place_mutation_is_not_a_retryable_atomic_publication(self):
        path = self.root / "host-telemetry.txt"
        lab.write_private(path, b"sequence=1\n")
        original, observed = os.fstat, []

        def mutate_after_first_descriptor_observation(descriptor):
            row = original(descriptor)
            if not observed:
                path.write_bytes(b"sequence=200\n")
            observed.append(True)
            return row

        with patch.object(lab.os, "fstat", side_effect=mutate_after_first_descriptor_observation), \
                self.assertRaisesRegex(RuntimeError, "Control file changed during read"):
            lab.read_telemetry(path)
        self.assertEqual(len(observed), 2)

    def test_atomic_replacement_after_descriptor_binding_returns_one_coherent_old_snapshot(self):
        path, replacement = self.root / "host-telemetry.txt", self.root / "next"
        lab.write_private(path, b"sequence=1\n")
        lab.write_private(replacement, b"sequence=2\n")
        original, observed = os.fstat, []

        def replace_after_binding(descriptor):
            row = original(descriptor)
            if not observed:
                os.replace(replacement, path)
            observed.append(True)
            return row

        with patch.object(lab.os, "fstat", side_effect=replace_after_binding):
            self.assertEqual(lab.read_telemetry(path), b"sequence=1\n")
        self.assertEqual(lab.read_telemetry(path), b"sequence=2\n")

    def test_telemetry_reobservation_does_not_relax_byte_or_directory_limits(self):
        path = self.root / "host-telemetry.txt"
        path.write_bytes(b"x" * (lab.LIMIT + 1))
        path.chmod(0o600)
        with self.assertRaisesRegex(RuntimeError, "Oversized control file"):
            lab.read_telemetry(path)
        self.root.chmod(0o755)
        with self.assertRaisesRegex(RuntimeError, "Directory must be owned"):
            lab.read_telemetry(path)

    def test_concurrent_create_has_one_winner_and_no_stale_temporary_files(self):
        path = self.root / "winner.txt"

        def attempt(number):
            data = f"winner={number}\n".encode()
            try:
                lab.write_private(path, data)
                return data
            except FileExistsError:
                return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            winners = [result for result in executor.map(attempt, range(32)) if result is not None]
        self.assertEqual(1, len(winners))
        self.assertEqual(winners[0], lab.read_private(path))
        self.assertEqual([path], list(self.root.iterdir()))

    def test_unprotected_or_symlinked_paths_are_never_adopted(self):
        path = self.root / "foreign"
        path.mkdir(mode=0o755)
        path.chmod(0o755)  # Do not let the invoking shell's restrictive umask repair this negative fixture.
        with self.assertRaises(RuntimeError):
            lab.private_directory(path)
        link = self.root / "link"
        link.symlink_to(path, target_is_directory=True)
        with self.assertRaises(RuntimeError):
            lab.private_directory(link)
        file = self.root / "control.txt"
        file.symlink_to(path / "absent")
        with self.assertRaises(RuntimeError):
            lab.write_private(file, b"x=1\n", replace=True)
        self.assertFalse((path / "absent").exists())

    def distribution(self):
        directory = self.root / "samples/p2p-sample-rpc/build/capacity-lab"
        directory.mkdir(parents=True)
        (directory / "lab.jar").write_bytes(b"unit-test-only-not-a-runtime")
        manifest = {"schema": 1, "sourceSha": SOURCE, "scope": "SYNTHETIC_LAB_NOT_PUBLICATION_OR_QUALIFICATION",
                    "entries": [{"name": "lab.jar", "sha256": hashlib.sha256((directory / "lab.jar").read_bytes()).hexdigest()}]}
        (directory / "manifest.json").write_text(json.dumps(manifest))
        return directory

    def test_distribution_is_bound_to_real_bytes_order_and_source(self):
        directory = self.distribution()
        with patch.object(lab, "ROOT", self.root):
            self.assertEqual(str(directory / "lab.jar"), lab.classpath(SOURCE))
            with self.assertRaises(RuntimeError):
                lab.classpath("b" * 40)
            (directory / "lab.jar").write_bytes(b"changed")
            with self.assertRaises(RuntimeError):
                lab.classpath(SOURCE)

    def test_distribution_cannot_add_ambient_classes_or_symlinks(self):
        directory = self.distribution()
        (directory / "ambient.jar").symlink_to(directory / "lab.jar")
        with patch.object(lab, "ROOT", self.root), self.assertRaises(RuntimeError):
            lab.classpath(SOURCE)

    def test_missing_native_ownership_or_owner_acknowledgement_refuses_execution(self):
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(RuntimeError):
            lab.owned_context()
        with patch.dict(os.environ, {"P2PKIT_AUDIT_OWNERSHIP_CHAIN": "not-sufficient"}, clear=True):
            with self.assertRaises(RuntimeError):
                lab.owned_context()


if __name__ == "__main__":
    unittest.main(verbosity=2)
