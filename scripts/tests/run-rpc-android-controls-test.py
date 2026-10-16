#!/usr/bin/env python3
"""Offline negative controls for supplemental Android result admission, not Android runtime tests."""
import importlib.util
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
path = Path(__file__).resolve().parents[1] / "run-rpc-android-controls.py"
spec = importlib.util.spec_from_file_location("rpc_art_controls", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0, str(path.parent))
import rpc_mobile_usb as usb
import rpc_mobile_shell_fixture as shell_fixture


class AdmissionTests(unittest.TestCase):
    def test_avd_sizes_only_new_userdata_and_selects_the_existing_image(self):
        original = "hw.ramSize=1536\nimage.sysdir.1=old/\ndisk.dataPartition.size=10G\nhw.cpu.ncore=1\n"
        image = Path("/owned-sdk/system-images/android-24/default/x86_64")
        expected = original.replace("image.sysdir.1=old/", "image.sysdir.1=" + str(image) + "/")
        expected = expected.replace("disk.dataPartition.size=10G", "disk.dataPartition.size=2G")
        self.assertEqual(module.configure_avd(original, image), expected)

    def test_avd_refuses_missing_or_duplicate_image_and_userdata_configuration(self):
        lines = ["image.sysdir.1=old/\n", "disk.dataPartition.size=10G\n"]
        for line in lines:
            for changed in ("".join(lines).replace(line, ""), "".join(lines) + line):
                with self.subTest(config=changed), self.assertRaises(RuntimeError):
                    module.configure_avd(changed, Path("/owned-sdk/image"))

    def result(self):
        fields = dict(rpcToken="a" * 32, rpcApi="24", rpcAbi="x86_64", rpcVm="Dalvik", rpcScope=module.SCOPE,
                      rpcOutcome="PASS", rpcCleanup="PASS", rpcCompleted=str(len(module.CONTROL_NAMES)))
        fields.update({f"rpcControl{i}": name for i, name in enumerate(module.CONTROL_NAMES, 1)})
        return fields

    def encode(self, values):
        return "".join(f"INSTRUMENTATION_RESULT: {k}={v}\n" for k, v in values.items()) + "INSTRUMENTATION_CODE: -1\n"

    def test_exact_complete_nonce_bound_result_is_accepted(self):
        values = self.result()
        self.assertEqual(values, module.assess_instrumentation(self.encode(values), "a" * 32))

    def test_each_missing_control_or_field_is_rejected(self):
        for key in self.result():
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                values = self.result()
                del values[key]
                module.assess_instrumentation(self.encode(values), "a" * 32)

    def test_failed_cleanup_wrong_device_runtime_and_nonce_are_rejected(self):
        for key, value in [("rpcOutcome", "FAIL"), ("rpcCleanup", "FAIL"), ("rpcToken", "b" * 32),
                           ("rpcApi", "37"), ("rpcVm", "OpenJDK"), ("rpcAbi", "arm64-v8a"), ("rpcCompleted", "0")]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                module.assess_instrumentation(self.encode({**self.result(), key: value}), "a" * 32)

    def test_duplicate_fields_terminals_and_oversized_output_are_rejected(self):
        raw = self.encode(self.result())
        for changed in (raw + "INSTRUMENTATION_RESULT: rpcOutcome=PASS\n", raw + "INSTRUMENTATION_CODE: -1\n",
                        raw.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: 0"),
                        raw.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: -10"),
                        raw.replace("INSTRUMENTATION_CODE: -1", "INSTRUMENTATION_CODE: -1truncated"),
                        raw + "INSTRUMENTATION_CODE: malformed\n",
                        raw + "INSTRUMENTATION_FAILED: refused\n", raw + "x" * 262145):
            with self.assertRaises(RuntimeError):
                module.assess_instrumentation(changed, "a" * 32)

    def test_free_form_diagnostics_do_not_silently_become_an_accepted_result(self):
        with self.assertRaises(RuntimeError):
            module.assess_instrumentation(self.encode({**self.result(), "rpcFailureClass": "Unexpected"}), "a" * 32)


class ControlShellTests(unittest.TestCase):
    """Actual bounded POSIX fixtures, fake features/run-as: explicitly NOT Android/ADB/USB runtime."""
    def invoke(self, root, changes=None):
        changes = changes or {}
        environment = shell_fixture.install(root)
        operations = {
            'control-shell-prepare': ('prepare', None),
            'control-shell-read-inbox': ('read', 'inbox.txt'),
            'control-shell-missing': ('read', 'ready.txt'),
            'control-shell-reprepare': ('prepare', None),
            'control-shell-read-unchanged': ('read', 'inbox.txt'),
            'control-shell-stop': ('stop', None),
            'control-shell-restop': ('stop', None),
            'control-shell-read-stop': ('read', 'stop.txt'),
        }
        def run(label, argv, data):
            if label == 'control-shell-features':
                # `adb features` prints one mutually supported feature per line,
                # unlike the comma-separated internal host:features protocol.
                result = (0, b'cmd\nshell_v2\nstat_v2\n')
            else:
                self.assertEqual(argv[:-1], ['shell', '-T', '-e', 'none'])
                operation, name = operations[label]
                self.assertEqual(argv, usb.android_shell('offline-fixture', operation, name))
                script = shell_fixture.script(usb.android_script('offline-fixture', operation, name), environment)
                result = subprocess.run(['/bin/sh', '-c', script], cwd=root, input=data, env=environment,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                result = result.returncode, result.stdout
            return changes.get(label, result)
        return run

    def test_real_posix_operations_and_complete_inventory_without_hardware_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'no_backup').mkdir(mode=0o700)
            value = module.control_shell_checks(self.invoke(root), usb, 'offline-fixture')
            self.assertEqual(value, dict(scope=module.SHELL_SCOPE, completed=list(module.SHELL_COMMANDS), passed=True))
            directory = root / 'no_backup/rpc-capacity/offline-fixture'
            self.assertEqual((directory / 'inbox.txt').read_bytes(), b'schema=1\nvalue=non-executable;fixture\n')
            self.assertEqual((directory / 'stop.txt').read_bytes(), b'action=stop\n')

    def test_stat_probe_distinguishes_missing_option_from_success_and_other_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            environment = shell_fixture.install(root)
            command = shlex.split(module.stat_dereference_probe()[-1])
            self.assertEqual(command[:-1], ['run-as', usb.ANDROID_PACKAGE, 'sh', '-c'])
            script = command[-1]
            absent = subprocess.run(['/bin/sh', '-c', script], env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            self.assertEqual((absent.returncode, absent.stdout, absent.stderr), (69, b'', b''))
            modern = root / 'modern'
            modern.mkdir(mode=0o700)
            modern_environment = shell_fixture.install(modern, supports_dereference=True)
            present = subprocess.run(['/bin/sh', '-c', script], env=modern_environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            self.assertEqual((present.returncode, present.stdout, present.stderr), (0, b'', b''))
            stat = root / 'fixture-tools/stat'
            stat.write_text('#!/bin/sh\nprintf "UNEXPLAINED_FAILURE\\n" >&2\nexit 1\n')
            failed = subprocess.run(['/bin/sh', '-c', script], env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
            self.assertEqual((failed.returncode, failed.stdout, failed.stderr), (70, b'', b''))

    def test_stat_probe_requires_known_help_terminal_error_exit_and_output_bound(self):
        help_text = b'usage: stat [-f] [-c FORMAT] FILE...\n\nDisplay status of files or filesystems.\n\n'
        terminal = b'stat: Unknown option Lc\n'
        cases = (
            (b"stat: Unknown option 'L'\n", 1, 69),
            (b'stat: Unknown option L\n', 1, 69),
            (terminal, 1, 69),
            (help_text + terminal, 1, 69),
            (b'21b6\n', 0, 0),
            (b'', 0, 70),
            (help_text + terminal, 0, 70),
            (help_text + terminal, 2, 70),
            (b'UNEXPLAINED\n' + terminal, 1, 70),
            (help_text + terminal + b'UNEXPLAINED\n', 1, 70),
            (help_text + b'stat: Permission denied\n', 1, 70),
            (b'stat: Unknown option Legacy\n', 1, 70),
            (b'0' * 16385, 0, 70),
            (help_text + b'X' * 16385 + b'\n' + terminal, 1, 70),
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            environment = shell_fixture.install(root)
            script = shlex.split(module.stat_dereference_probe()[-1])[-1]
            for raw, code, expected in cases:
                with self.subTest(code=code, expected=expected, bytes=len(raw)):
                    (root / 'fixture-tools/stat').write_text(
                        f'#!{sys.executable}\nimport sys\nsys.stdout.buffer.write({raw!r})\nraise SystemExit({code})\n')
                    result = subprocess.run(['/bin/sh', '-c', script], env=environment,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
                    self.assertEqual((result.returncode, result.stdout, result.stderr), (expected, b'', b''))

    def test_failed_remote_exit_corrupt_output_and_legacy_shell_are_rejected(self):
        for label, result in (
                ('control-shell-features', (0, b'cmd\n')), ('control-shell-prepare', (1, b'')),
                ('control-shell-read-inbox', (0, b'WRONG')), ('control-shell-missing', (0, b'')),
                ('control-shell-reprepare', (0, b'')), ('control-shell-read-unchanged', (0, b'changed')),
                ('control-shell-stop', (1, b'')), ('control-shell-restop', (0, b'')),
                ('control-shell-read-stop', (0, b'action=changed\n'))):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / 'no_backup').mkdir(mode=0o700)
                with self.assertRaises(RuntimeError):
                    module.control_shell_checks(self.invoke(root, {label: result}), usb, 'offline-fixture')

    def test_wire_format_or_partial_feature_names_never_start_a_shell_command(self):
        for raw in (b'cmd,shell_v2\n', b'not_shell_v2\n', b'shell_v20\n', b'shell_v2\nshell_v2\n'):
            calls = []
            def invoke(label, argv, data):
                calls.append(label)
                return 0, raw
            with self.subTest(raw=raw), self.assertRaises(RuntimeError):
                module.control_shell_checks(invoke, usb, 'offline-fixture')
            self.assertEqual(calls, ['control-shell-features'])

    def test_unknown_label_and_nonzero_or_oversized_feature_output_cannot_start_data_work(self):
        for label in ('../outside', 'A', 'x;echo', 'x' * 65):
            with self.assertRaises(RuntimeError):
                module.control_shell_checks(lambda *_: self.fail('No command should execute'), usb, label)
        for result in ((1, b'shell_v2'), (True, b'shell_v2'), (0, b'shell_v2,' + b'x' * 16384)):
            with self.assertRaises(RuntimeError):
                module.control_shell_checks(lambda *_: result, usb, 'offline-fixture')


if __name__ == "__main__":
    unittest.main(verbosity=2)
