#!/usr/bin/env python3
"""Bootstrap policy controls. These do not count as native Apple ownership admission."""
import copy
import ctypes
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("private_session", ROOT / "scripts/with-darwin-audit-session.py")
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)


class SessionTests(unittest.TestCase):
    def config(self):
        return {"uid": 501, "gid": 20, "cwd": "/fixture", "argv": ["/fixture/python", "test.py"],
                "environment": {"PATH": "/usr/bin:/bin", "GITHUB_SHA": "a" * 40}}

    def system(self, mutate=lambda _: None, fail=None):
        value = s.AuditInfo()
        value.auid, value.asid, value.type = 501, 42, 4
        value.success, value.failure, value.flags = 9, 17, 16
        library = Mock()

        def get(pointer, size):
            self.assertEqual(size, 48)
            ctypes.memmove(pointer, ctypes.byref(value), size)
            return 0

        def set_info(pointer, size):
            requested = ctypes.cast(pointer, ctypes.POINTER(s.AuditInfo)).contents
            self.assertEqual(requested.asid, -1)
            saved = s.AuditInfo.from_buffer_copy(bytes(requested))
            saved.asid = 42
            self.assertEqual(bytes(saved), bytes(value), "Only ASID may change in the request")
            value.asid = 43
            mutate(value)
            return 0
        library.getaudit_addr.side_effect = get
        library.setaudit_addr.side_effect = set_info
        if fail:
            getattr(library, fail).side_effect = lambda *_: -1
        return library

    def test_fresh_session_preserves_every_audit_policy_byte(self):
        self.assertEqual(s.new_session(self.system()), (43, True))

    def test_same_unassigned_or_missing_session_fails_closed(self):
        for asid in (0, -1, 42):
            with self.subTest(asid=asid), self.assertRaisesRegex(RuntimeError, "fresh assigned"):
                s.new_session(self.system(lambda value: setattr(value, "asid", asid)))

    def test_policy_mutation_is_never_accepted(self):
        for field in ("auid", "success", "failure", "port", "type", "flags"):
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, "policy changed"):
                s.new_session(self.system(lambda value: setattr(value, field, getattr(value, field) + 1)))
        with self.assertRaisesRegex(RuntimeError, "policy changed"):
            s.new_session(self.system(lambda value: value.address.__setitem__(0, 5)))

    def test_native_api_failure_is_not_a_session(self):
        for function in ("getaudit_addr", "setaudit_addr"):
            with self.subTest(function=function), self.assertRaises(RuntimeError):
                s.new_session(self.system(fail=function))

    def test_only_original_nonroot_account_is_admitted(self):
        s.validate(self.config(), 501, 20)
        for uid, gid in ((0, 20), (501, 0), (502, 20), (501, 21), (True, 20)):
            with self.subTest(uid=uid, gid=gid), self.assertRaises(RuntimeError):
                s.validate(self.config(), uid, gid)

    def test_secrets_interpreter_hooks_and_ownership_override_are_not_forwarded(self):
        for key in ("GITHUB_TOKEN", "GH_TOKEN", "PYTHONPATH", "LD_PRELOAD", "DYLD_INSERT_LIBRARIES",
                    "P2PKIT_AUDIT_STATE_DIR", "P2PKIT_AUDIT_OWNERSHIP_CHAIN", "SUDO_UID", "SECURITYSESSIONID"):
            config = self.config()
            config["environment"][key] = "untrusted"
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                s.validate(config, 501, 20)

    def test_ambiguous_or_unbounded_commands_rejected(self):
        for argv in ([], ["relative"], ["/python", "a\0b"], ["/python"] * 129, "not-a-list"):
            config = self.config()
            config["argv"] = argv
            with self.subTest(argv=repr(argv)[:50]), self.assertRaises(RuntimeError):
                s.validate(config, 501, 20)

    def test_private_config_bytes_identity_and_no_follow(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            path = parent / "config.json"
            s.write_new(path, self.config())
            self.assertEqual(s.read_config(path, os.getuid()), self.config())
            with self.assertRaises(FileExistsError):
                s.write_new(path, self.config())
            path.chmod(0o644)
            with self.assertRaises(RuntimeError):
                s.read_config(path, os.getuid())
            path.chmod(0o600)
            link = parent / "link.json"
            link.symlink_to(path)
            with self.assertRaises(RuntimeError):
                s.read_config(link, os.getuid())
            path.write_text('{"uid":1,"uid":2}')
            with self.assertRaisesRegex(RuntimeError, "Duplicate"):
                s.read_config(path, os.getuid())

    def test_permanent_drop_checks_all_credentials_and_no_root_recovery(self):
        with patch.object(s.os, "getgrouplist", return_value=[20, 80]), \
             patch.object(s.os, "initgroups") as groups, patch.object(s.os, "setgid") as gid, \
             patch.object(s.os, "setuid", side_effect=[None, PermissionError()]) as uid, \
             patch.object(s.os, "getuid", return_value=501), patch.object(s.os, "geteuid", return_value=501), \
             patch.object(s.os, "getgid", return_value=20), patch.object(s.os, "getegid", return_value=20), \
             patch.object(s.os, "getgroups", return_value=[20, 80]):
            s.drop_privileges(501, 20, "fixture")
            groups.assert_called_once_with("fixture", 20)
            gid.assert_called_once_with(20)
            self.assertEqual([call.args for call in uid.call_args_list], [(501,), (0,)])
            uid.side_effect = None
            with self.assertRaisesRegex(RuntimeError, "recoverable root"):
                s.drop_privileges(501, 20, "fixture")

    def test_failed_drop_cannot_reach_evidence_write_or_exec(self):
        config = self.config()
        with patch.object(s.platform, "system", return_value="Darwin"), \
             patch.object(s.os, "getuid", return_value=0), patch.object(s.os, "geteuid", return_value=0), \
             patch.dict(s.os.environ, {"SUDO_UID": "501", "SUDO_GID": "20"}), \
             patch.object(s, "read_config", return_value=config), \
             patch.object(s.pwd, "getpwuid", return_value=Mock(pw_gid=20, pw_name="fixture")), \
             patch.object(s.ctypes, "CDLL", return_value=Mock()), \
             patch.object(s, "new_session", return_value=(43, True)), \
             patch.object(s, "drop_privileges", side_effect=RuntimeError("denied")), \
             patch.object(s, "write_new") as write, patch.object(s.os, "execvpe") as execute:
            with self.assertRaisesRegex(RuntimeError, "denied"):
                s.bootstrap(Path("/fixture/config"))
            write.assert_not_called()
            execute.assert_not_called()

    def test_observer_and_production_policy_are_not_in_the_privileged_bootstrap(self):
        source = (ROOT / "scripts/with-darwin-audit-session.py").read_text()
        for forbidden in ("import audit_processes", "make_scope(", "os.kill(", "killpg(", "setfacl", "spctl",
                          "csrutil", "shell=True"):
            self.assertNotIn(forbidden, source)
        bootstrap = source.split("def bootstrap(path):", 1)[1].split("def main():", 1)[0]
        self.assertLess(bootstrap.index("drop_privileges("), bootstrap.index("write_new("))
        self.assertLess(bootstrap.index("drop_privileges("), bootstrap.index("os.execvpe("))
        self.assertIn('"-I", "-S"', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
