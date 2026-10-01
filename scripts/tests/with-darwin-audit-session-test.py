#!/usr/bin/env python3
"""Bootstrap policy controls. These do not count as native Apple ownership admission."""
import copy
import ctypes
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import venv

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

    def test_main_preserves_the_explicit_interpreter_without_substituting_its_path_launcher(self):
        interpreter = '/fixture/Python.framework/Versions/3.13/Python.app/Contents/MacOS/Python'
        arguments = ['session.py', '--parent', '/fixture/private', '--', interpreter, '/fixture/test.py']
        def which(command):
            return '/fixture/bin/python3' if command == 'python3' else command
        with patch.object(sys, 'argv', arguments), patch.object(s.sys, 'executable', interpreter), \
                patch.object(s.platform, 'system', return_value='Darwin'), \
                patch.object(s.os, 'getuid', return_value=501), patch.object(s.os, 'geteuid', return_value=501), \
                patch.object(s.os, 'getgid', return_value=20), patch.object(s.os, 'getcwd', return_value='/fixture'), \
                patch.object(s, 'physical'), patch.object(s.Path, 'lstat',
                    return_value=SimpleNamespace(st_mode=stat.S_IFDIR | 0o700, st_uid=501)), \
                patch.dict(s.os.environ, {'PATH': '/fixture/bin'}, clear=True), \
                patch.object(s.shutil, 'which', side_effect=which), patch.object(s, 'write_new') as write, \
                patch.object(s.subprocess, 'call', return_value=0) as invoke:
            self.assertEqual(s.main(), 0)
        path, config = write.call_args.args
        self.assertEqual(path, Path('/fixture/private/session-config.json'))
        self.assertEqual(config['argv'], [interpreter, '/fixture/test.py'])
        self.assertEqual(config['cwd'], '/fixture')
        self.assertEqual(config['environment'], {'PATH': '/fixture/bin'})
        self.assertEqual(invoke.call_args.args[0], ['/usr/bin/sudo', '-n', interpreter, '-I', '-S',
                         str(ROOT / 'scripts/with-darwin-audit-session.py'), '--bootstrap', str(path)])

    def test_real_python_site_startup_selection_matches_child_without_changing_privileged_bootstrap(self):
        # Reproduce the relevant Homebrew behavior with a disposable, pip-free
        # environment. No installed interpreter/site file is modified, downloaded
        # or used for a privileged bootstrap; that bootstrap is not invoked here.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            environment = root / 'python-environment'
            builder = venv.EnvBuilder(with_pip=False, symlinks=True)
            builder.create(environment)
            context = builder.ensure_directories(environment)
            interpreter = Path(context.env_exe)
            selected = interpreter.with_name('selected-python')
            selected.symlink_to(interpreter)
            library = environment / 'lib' / f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages'
            self.assertTrue(library.is_dir())
            # A .pth startup hook models the same normal-site assignment without
            # competing with the distro's own stdlib sitecustomize module.
            (library / 'fixture-interpreter.pth').write_text(
                'import sys; sys.executable = ' + repr(str(selected)) + '\n')
            child_env = {'PATH': '/usr/bin:/bin', 'HOME': str(root), 'PYTHONDONTWRITEBYTECODE': '1'}
            expression = 'import sys; from pathlib import Path; print(Path(sys.executable).absolute())'
            def query(executable, *flags):
                return subprocess.check_output([str(executable), *flags, '-c', expression],
                    cwd=root, env=child_env, timeout=10).decode().strip()
            old = query(interpreter, '-I', '-S')
            chosen = query(interpreter, '-I')
            actual = query(chosen)
            self.assertNotEqual(old, actual)
            self.assertEqual(chosen, actual)
            self.assertEqual(Path(old).resolve(strict=True), Path(actual).resolve(strict=True))
            source = (ROOT / 'scripts/with-darwin-audit-session.py').read_text()
            self.assertIn('"-I", "-S"', source)  # Privileged setup still excludes every site hook.


if __name__ == "__main__":
    unittest.main(verbosity=2)
