#!/usr/bin/env python3
"""No payload/native execution. Fixed adapter, byte/refusal and original-owner retirement controls."""
from pathlib import Path
import hashlib
import importlib.util
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("native_payload", ROOT / "scripts/windows_native_smoke_payload.py")
N = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(N)


class Controls(unittest.TestCase):
    def arguments(self, root, **changes):
        return types.SimpleNamespace(operation="native-custody", native_directory=str(root),
                                     native_sha256="a" * 64, **changes)

    def test_only_exact_modes_accept_the_required_external_digest_and_directory(self):
        with tempfile.TemporaryDirectory() as root:
            args = self.arguments(root)
            self.assertEqual(N.executable(args), Path(root) / N.FILE_NAME)
            self.assertEqual(N.extra_arguments(args), ["--native-directory", root, "--native-sha256", "a" * 64])
            for field, value in (("native_directory", None), ("native_directory", "relative"),
                                 ("native_sha256", None), ("native_sha256", "A" * 64),
                                 ("native_sha256", "a" * 63), ("operation", "admission"),
                                 ("operation", "native-custody;exit")):
                changed = vars(args) | {field: value}
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    N.validate_arguments(types.SimpleNamespace(**changed))
        self.assertEqual(N.extra_arguments(types.SimpleNamespace(operation="admission")), [])

    def test_native_stdout_cannot_substitute_an_installed_result_or_hide_a_failure(self):
        for operation in N.OPERATIONS:
            scope = (b"SCOPE real-native-custody-smoke-only; NOT transactions/JNI/loader/MSI qualification"
                     if operation == "native-custody" else
                     b"SCOPE cold-composite-write-session-reopen-only; NOT crash/encrypted-profile/JNI/loader/MSI qualification")
            raw = scope + b"\nPASS original-owner\nRESULT code=0; canonical-fixtures-retained; exit-zero-required\n"
            self.assertTrue(N.matches(raw, operation))
            self.assertFalse(N.matches(raw, next(item for item in N.OPERATIONS if item != operation)))
            for altered in (raw.replace(b"PASS", b"FAIL"), raw.replace(b"code=0", b"code=8"),
                            raw + b"unexpected\n", b"{}\n", raw + b"x" * 65536):
                self.assertFalse(N.matches(altered, operation))

    def run_owner_case(self, mode):
        events = []
        data = bytearray(512)
        data[:2] = b"MZ"; data[60:64] = (64).to_bytes(4, "little")
        data[64:68] = b"PE\0\0"; data[68:70] = (0x8664).to_bytes(2, "little")
        data[86:88] = (2).to_bytes(2, "little"); data[88:90] = (0x20b).to_bytes(2, "little")
        class File:
            path = ROOT / N.FILE_NAME
            def read(self): events.append("read"); return data
            def verify(self):
                events.append("file-verify")
                return 1 if mode != "changed" or events.count("file-verify") == 1 else 2
            def close(self):
                events.append("file-close")
                if mode == "close": raise OSError("inert close failure")
        class Directory:
            path = ROOT
            def open_file(self, name, **options):
                self_case.assertEqual(name, N.FILE_NAME); events.append("file-open"); return File()
            def verify(self): events.append("directory-verify")
            def close(self): events.append("directory-close")
        self_case = self
        def command(argv, **options):
            events.append("command")
            self.assertNotIn("file-close", events)
            self.assertEqual(argv, [str(ROOT / N.FILE_NAME), "--disposable-custody-smoke"])
            self.assertEqual((options["timeout"], options["cleanup_seconds"]), (15, 5))
            if mode == "command": raise RuntimeError("inert command failure")
            return {"result": "observed"}
        args = self.arguments(ROOT)
        args.native_sha256 = hashlib.sha256(data).hexdigest() if mode != "hash" else "0" * 64
        F = types.SimpleNamespace(open_private_directory=lambda path: Directory())
        E = types.SimpleNamespace(run_command=command)
        deadline = types.SimpleNamespace(monotonic_end=lambda reserve: 999, check=lambda reserve: 9,
                                         worker_budgets=lambda: (15, 5))
        if mode == "normal":
            self.assertEqual(N.run(args, deadline, E, F, ROOT / "command"), {"result": "observed"})
        else:
            with self.assertRaises(Exception): N.run(args, deadline, E, F, ROOT / "command")
        self.assertEqual(events[-2:], ["file-close", "directory-close"])
        self.assertEqual(events.count("file-close"), 1)
        self.assertEqual(events.count("directory-close"), 1)
        self.assertEqual("command" in events, mode != "hash")

    def test_hash_is_compared_before_execution_and_original_file_survives_until_observed_exit(self):
        for mode in ("normal", "hash", "changed", "command", "close"):
            with self.subTest(mode=mode): self.run_owner_case(mode)


if __name__ == "__main__":
    unittest.main()
