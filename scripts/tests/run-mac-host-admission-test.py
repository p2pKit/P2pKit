#!/usr/bin/env python3
"""Pure/model controls only: no genuine Mac/native/host admission is exercised.

Native calls are replaced with finite memory-only fakes. Filesystem controls use
only disposable synthetic fixtures, not a live checkout or native process owner.
A passing suite cannot establish any hosted run, runner capacity or terminal exit.
"""

import ast
import builtins
import copy
import ctypes
import errno
import hashlib
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
SOURCE = Path(__file__).resolve().parents[1] / "run-mac-host-admission.py"
SPEC = importlib.util.spec_from_file_location("mac_host_capacity", SOURCE)
app = importlib.util.module_from_spec(SPEC)
with mock.patch.object(ctypes, "CDLL", side_effect=AssertionError("No native load in pure controls")):
    SPEC.loader.exec_module(app)


def dispatch(operation="macos-arm64-admission"):
    selected = app.OPERATIONS[operation]
    env = {
        "P2PKIT_OPERATION": operation, "P2PKIT_EXPECTED_SHA": "a" * 40, "P2PKIT_EXPECTED_TREE": "b" * 40,
        "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1",
        "GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REPOSITORY": app.REPOSITORY,
        "GITHUB_REPOSITORY_OWNER": "p2pKit", "GITHUB_REPOSITORY_ID": "100", "GITHUB_REPOSITORY_OWNER_ID": "200",
        "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
        "GITHUB_JOB": app.JOB, "GITHUB_WORKFLOW": "Desktop cross-host", "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKFLOW_SHA": "a" * 40, "GITHUB_REF": "refs/heads/ci/capacity-test",
        "GITHUB_REF_TYPE": "branch", "GITHUB_REF_NAME": "ci/capacity-test",
        "GITHUB_WORKFLOW_REF": app.REPOSITORY + "/" + app.WORKFLOW + "@refs/heads/ci/capacity-test",
        "GITHUB_RUN_ID": "123456", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_RUN_NUMBER": "99",
        "GITHUB_ACTOR": "test-actor", "GITHUB_ACTOR_ID": "300", "GITHUB_TRIGGERING_ACTOR": "review-actor",
        "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "macOS", "RUNNER_ARCH": selected["arch"],
        "ImageOS": selected["images"][0], "ImageVersion": "20260901.0010",
    }
    event = {
        "ref": "ci/capacity-test", "inputs": {"operation": operation, "expected_sha": "a" * 40,
                                                  "expected_tree": "b" * 40},
        "repository": {"full_name": app.REPOSITORY, "name": "P2pKit", "id": 100, "fork": False,
                       "owner": {"login": "p2pKit", "id": 200},
                       "html_url": "https://github.com/" + app.REPOSITORY,
                       "url": "https://api.github.com/repos/" + app.REPOSITORY},
        "sender": {"login": "test-actor", "id": 300},
    }
    return env, event


def observations(operation="macos-arm64-admission"):
    selected = app.OPERATIONS[operation]
    return {
        "kernel": app.observed({"system": "Darwin", "release": selected["kernel_major"] + ".0.0",
                                "machine": selected["machine"]}),
        "product_version": app.observed(selected["product_major"] + ".0"),
        "build_version": app.observed(selected["kernel_major"] + "A123"),
        "ordinary_uid": app.observed(True), "pointer_bits": app.observed(64), "translation": app.observed(0),
        "physical_memory_bytes": app.observed(8 * app.GIB), "pressure": app.observed("NORMAL"),
        "disk": app.observed({"block_bytes": 4096, "total_bytes": 100 * app.GIB,
                              "available_bytes": app.INITIAL_DISK_BYTES}),
    }


def object_id(kind, body):
    return hashlib.sha1(kind + b" " + str(len(body)).encode("ascii") + b"\0" + body).digest()


def expected_tree(ordered_records):
    # Deliberately explicit ordering/modes, independent of the filesystem walker.
    body = b"".join(mode + b" " + name + b"\0" + oid for mode, name, oid in ordered_records)
    return object_id(b"tree", body).hex()


def fake_stat(original, **changes):
    fields = ("st_dev", "st_ino", "st_mode", "st_uid", "st_gid", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
    values = {field: getattr(original, field) for field in fields}
    values.update(changes)
    return SimpleNamespace(**values)


class FakeSysctl:
    def __init__(self, raw=b"", result=0, error=0, size=None):
        self.raw, self.result, self.error, self.size, self.calls = raw, result, error, size, []

    def __call__(self, name, output, size_pointer, new_value, new_length):
        size = ctypes.cast(size_pointer, ctypes.POINTER(ctypes.c_size_t)).contents
        self.calls.append((name, size.value, new_value, new_length))
        if new_value is not None or new_length != 0:
            raise AssertionError("Writable sysctl request")
        ctypes.memmove(output, self.raw, min(size.value, len(self.raw)))
        size.value = len(self.raw) if self.size is None else self.size
        ctypes.set_errno(self.error)
        return self.result


class ContextAndSchemaTests(unittest.TestCase):
    def test_exact_operations_and_complete_dispatch_identity(self):
        for operation in app.OPERATIONS:
            env, event = dispatch(operation)
            identity = app.dispatch_identity(env, event)
            self.assertEqual(identity["operation"], operation)
            self.assertEqual(identity["actor_id"], "300")
            self.assertEqual(identity["triggering_actor"], "review-actor")
            self.assertEqual(identity["selected_runner_label"], app.OPERATIONS[operation]["label"])
            for key, value in (("extra", ""), ("runner", "macos-26")):
                invalid = copy.deepcopy(event)
                invalid["inputs"][key] = value
                with self.assertRaises(app.Failure):
                    app.dispatch_identity(env, invalid)

    def test_wrong_forged_or_retired_context_rejected(self):
        env, event = dispatch()
        changes = {
            "GITHUB_EVENT_NAME": "pull_request", "RUNNER_ENVIRONMENT": "self-hosted", "RUNNER_OS": "Linux",
            "RUNNER_ARCH": "X64", "GITHUB_REPOSITORY": "elsewhere/P2pKit", "GITHUB_JOB": "verify",
            "GITHUB_API_URL": "https://invalid.example", "GITHUB_SERVER_URL": "https://invalid.example",
            "GITHUB_SHA": "c" * 40, "GITHUB_WORKFLOW_SHA": "c" * 40, "GITHUB_WORKFLOW_REF": "wrong",
            "GITHUB_RUN_ID": "0", "GITHUB_RUN_ATTEMPT": "01", "GITHUB_RUN_NUMBER": "-1",
            "GITHUB_ACTOR_ID": "301", "GITHUB_TRIGGERING_ACTOR": "private\nvalue",
            "GITHUB_REF": "refs/heads/audit/complete-2026-09-04", "GITHUB_REF_TYPE": "tag",
            "P2PKIT_EXPECTED_TREE": "B" * 40, "P2PKIT_OPERATION": "arbitrary-command",
            "ImageOS": "macos15", "ImageVersion": "/private/host-path",
        }
        for key, value in changes.items():
            with self.subTest(key=key), self.assertRaises(app.Failure):
                app.dispatch_identity(dict(env, **{key: value}), event)
        for section, key, value in (("sender", "id", True), ("sender", "login", "other-actor"),
                                    ("repository", "id", "100"), ("repository", "fork", True)):
            invalid = copy.deepcopy(event)
            invalid[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(app.Failure):
                app.dispatch_identity(env, invalid)
        for ref in ("refs/heads/x/../y", "refs/heads/x.lock/y", "refs/heads/x//y", "refs/heads/x\n"):
            self.assertFalse(app.branch_ref(ref))

    def test_ambient_hooks_rejected_without_normalization(self):
        env, _ = dispatch()
        app.check_environment(env)
        groups = {
            "ENVIRONMENT_PYTHON_HOOK": ("PYTHONPATH", "PYTHONHOME", "PYTHON_PRIVATE\nNAME"),
            "ENVIRONMENT_LOADER_HOOK": ("DYLD_INSERT_LIBRARIES", "LD_PRELOAD", "DYLD_PRIVATE", "LD_PRIVATE"),
            "ENVIRONMENT_GIT_HOOK": ("GIT_CONFIG_COUNT", "GIT_PAGER", "GIT_PRIVATE\nNAME"),
            "ENVIRONMENT_SHELL_HOOK": ("BASH_ENV", "ENV", "ZDOTDIR", "CDPATH"),
            "ENVIRONMENT_JVM_HOOK": ("JAVA_OPTS", "GRADLE_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS"),
            "ENVIRONMENT_BUILD_HOME": ("GRADLE_USER_HOME",),
            "ENVIRONMENT_CREDENTIAL_HOOK": ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN",
                                             "SSH_ASKPASS", "SSH_AUTH_SOCK", "GPG_AGENT_INFO"),
            "ENVIRONMENT_ELEVATION": ("SUDO_UID", "SUDO_GID", "SUDO_USER", "SUDO_COMMAND"),
            "ENVIRONMENT_CAMPAIGN_HOOK": ("P2PKIT_EXTRA_OPTION", "P2PKIT_PRIVATE\nNAME"),
        }
        for code, keys in groups.items():
            for key in keys:
                for content in ("", "private/value\n::notice::never-print"):
                    value = dict(env, **{key: content})
                    original = dict(value)
                    with self.subTest(key=key, empty=not content), self.assertRaises(app.Failure) as failure:
                        app.check_environment(value)
                    self.assertEqual(failure.exception.code, code)
                    self.assertEqual(str(failure.exception), code)
                    self.assertEqual(value, original)

    def test_environment_pinned_values_bounds_and_required_controls(self):
        env, _ = dispatch()
        # Optional Git prompt stays optional; ordinary hosted installations remain allowed.
        allowed = dict(env, PATH="/private/path", HOME="/private/home", JAVA_HOME="/private/jdk",
                       GIT_TERMINAL_PROMPT="0")
        app.check_environment(allowed)
        for key, expected in (("PYTHONDONTWRITEBYTECODE", "1"), ("PYTHONUNBUFFERED", "1"),
                              ("GIT_TERMINAL_PROMPT", "0")):
            for content in ("", expected + "\n", "private-value"):
                value = dict(env, **{key: content})
                original = dict(value)
                with self.subTest(key=key), self.assertRaises(app.Failure) as failure:
                    app.check_environment(value)
                self.assertEqual(failure.exception.code, "ENVIRONMENT_PINNED_VALUE")
                self.assertEqual(value, original)
        for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED"):
            value = dict(env)
            del value[key]
            with self.subTest(key=key), self.assertRaises(app.Failure) as failure:
                app.check_environment(value)
            self.assertEqual(failure.exception.code, "ENVIRONMENT_REQUIRED")
        for key in (123, "x" * 257):
            value = dict(env)
            value[key] = "private-value"
            with self.subTest(key=key), self.assertRaises(app.Failure) as failure:
                app.check_environment(value)
            self.assertEqual(failure.exception.code, "ENVIRONMENT_KEY")
        app.check_environment(dict(env, **{"x" * 256: "private-value"}))
        maximum = {"UNRELATED_" + str(i): "" for i in range(4096 - len(env))}
        maximum.update(env)
        app.check_environment(maximum)
        with self.assertRaises(app.Failure) as failure:
            app.check_environment(dict(maximum, extra="private-value"))
        self.assertEqual(failure.exception.code, "ENVIRONMENT_COUNT")

    def test_environment_cli_categories_stop_before_identity_source_or_observation(self):
        env, _ = dispatch()
        cases = (
            (dict(env, GIT_PRIVATE_NAME="private\nvalue"), "ENVIRONMENT_GIT_HOOK"),
            (dict(env, GH_TOKEN="private-token"), "ENVIRONMENT_CREDENTIAL_HOOK"),
            (dict(env, PYTHONUNBUFFERED="private"), "ENVIRONMENT_PINNED_VALUE"),
        )
        for operation in ("run", "validate-public"):
            for value, code in cases:
                original = dict(value)
                output = []
                with self.subTest(operation=operation, code=code), \
                        mock.patch.object(app.os, "environ", value), \
                        mock.patch.object(app, "runtime_identity", return_value={}), \
                        mock.patch.object(app, "read_external") as event, \
                        mock.patch.object(app, "dispatch_identity") as identity, \
                        mock.patch.object(app, "checked_source") as source, \
                        mock.patch.object(app, "collect_host") as observe, \
                        mock.patch.object(app, "retain_public") as retain, \
                        mock.patch.object(app, "append_ready") as ready, \
                        mock.patch.object(app.os, "write", side_effect=lambda fd, raw: output.append(raw) or len(raw)):
                    self.assertEqual(app.main([operation]), 2)
                self.assertEqual(output, [("MAC_HOST_CAPACITY_ERROR:" + code + "\n").encode("ascii")])
                for dependent in (event, identity, source, observe, retain, ready):
                    dependent.assert_not_called()
                self.assertEqual(value, original)

    def test_environment_reports_only_first_failed_predicate_in_existing_order(self):
        env, _ = dispatch()
        for values, code in (({"GH_TOKEN": "private", "GIT_PRIVATE": "private"}, "ENVIRONMENT_CREDENTIAL_HOOK"),
                             ({"GIT_PRIVATE": "private", "GH_TOKEN": "private"}, "ENVIRONMENT_GIT_HOOK")):
            with self.assertRaises(app.Failure) as failure:
                app.check_environment(dict(env, **values))
            self.assertEqual(failure.exception.code, code)

    def test_bounded_duplicate_free_json(self):
        _, event = dispatch()
        self.assertEqual(app.parse_json(app.json_bytes(event), app.MAX_EVENT_BYTES), event)
        bad = (b'{"inputs":{"a":1,"a":2}}', b'{"n":NaN}', b'{"n":Infinity}', b'{"n":1.5}',
               b'{"n":' + b"9" * 100 + b"}", b"[]", b'{"a":' * 34 + b"1" + b"}" * 34,
               b'\xff', b'{"unfinished":')
        for raw in bad:
            with self.subTest(raw=raw[:20]), self.assertRaises(app.Failure):
                app.parse_json(raw, app.MAX_EVENT_BYTES)
        with self.assertRaises(app.Failure):
            app.parse_json(b"{}", 1)

    def test_physical_path_spelling_not_silently_resolved(self):
        for path in ("relative", "/", "/tmp//x", "/tmp/./x", "/tmp/../x", "/tmp/x/", "/tmp/x\n", None):
            with self.subTest(path=path), self.assertRaises(app.Failure):
                app.physical_parts(path)
        self.assertEqual(app.physical_parts("/Users/runner/work/checkout"), ["Users", "runner", "work", "checkout"])

    def test_runtime_and_cooperative_budget_are_fixed(self):
        flags = SimpleNamespace(isolated=1, ignore_environment=1, no_user_site=1, no_site=1)
        with mock.patch.object(app.sys, "platform", "darwin"), mock.patch.object(app.os, "name", "posix"), \
                mock.patch.object(app.sys, "version_info", (3, 9, 0)), mock.patch.object(app.sys, "flags", flags):
            self.assertEqual(app.runtime_identity()["version"], [3, 9, 0])
            self.assertIs(app.runtime_identity()["no_site"], True)
            with mock.patch.object(flags, "no_site", 0), self.assertRaises(app.Failure):
                app.runtime_identity()
            with mock.patch.object(app.sys, "version_info", (3, 8, 0)), self.assertRaises(app.Failure):
                app.runtime_identity()
            with mock.patch.object(app.sys, "platform", "linux"), self.assertRaises(app.Failure):
                app.runtime_identity()
        with mock.patch.object(app.time, "monotonic", side_effect=[100.0, 129.999, 130.0, 99.0]):
            budget = app.Budget()
            self.assertLess(budget.check(), 30000)
            for _ in range(2):
                with self.assertRaises(app.Failure):
                    budget.check()

    def test_main_errors_and_cli_arguments_are_finite(self):
        for error, expected in ((OSError("private/path username hostname"), b"FILESYSTEM"),
                                (RuntimeError("private-value"), b"INTERNAL"),
                                (KeyboardInterrupt(), b"INTERRUPTED"),
                                (app.Failure("private-value"), b"INTERNAL")):
            output = []
            with mock.patch.object(app, "run", side_effect=error), \
                    mock.patch.object(app.os, "write", side_effect=lambda fd, raw: output.append(raw) or len(raw)):
                self.assertEqual(app.main(["run"]), 2)
            self.assertEqual(output, [b"MAC_HOST_CAPACITY_ERROR:" + expected + b"\n"])
        with mock.patch.object(app, "run") as run, mock.patch.object(app.os, "write") as write:
            self.assertEqual(app.main(["run", "/private/argument"]), 2)
            run.assert_not_called()
            write.assert_called_once_with(2, b"MAC_HOST_CAPACITY_ERROR:ARGUMENTS\n")

    def test_startup_import_failure_is_finite(self):
        original_import = builtins.__import__

        def refuse_hashlib(name, *args, **kwargs):
            if name == "hashlib":
                raise ImportError("private/interpreter/path")
            return original_import(name, *args, **kwargs)

        module = importlib.util.module_from_spec(SPEC)
        output = io.StringIO()
        with mock.patch.object(builtins, "__import__", side_effect=refuse_hashlib), \
                mock.patch.object(sys, "stderr", output), self.assertRaises(SystemExit) as stopped:
            SPEC.loader.exec_module(module)
        self.assertEqual(stopped.exception.code, 2)
        self.assertEqual(output.getvalue(), "MAC_HOST_CAPACITY_ERROR:STARTUP\n")

    def test_reviewed_import_and_call_boundary_has_no_spawn(self):
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 9))
        imports = {name.name for node in ast.walk(tree) if isinstance(node, ast.Import) for name in node.names}
        self.assertEqual(imports, {"sys", "ctypes", "errno", "hashlib", "json", "os", "re", "stat", "time", "unicodedata"})
        self.assertFalse(any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree)))
        forbidden = {"system", "popen", "Popen", "fork", "posix_spawn", "posix_spawnp", "spawnv", "spawnve",
                     "execv", "execve", "kill", "killpg", "waitpid", "find_library", "Thread", "Process"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    self.assertNotIn(node.func.attr, forbidden)
                if isinstance(node.func, ast.Name):
                    self.assertNotIn(node.func.id, {"exec", "eval", "compile", "__import__"})
        loads = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and
                 isinstance(node.func, ast.Attribute) and node.func.attr == "CDLL"]
        self.assertEqual(len(loads), 1)
        self.assertEqual(ast.literal_eval(loads[0].args[0]), "/usr/lib/libSystem.B.dylib")
        with mock.patch.object(ctypes, "CDLL") as native, mock.patch.object(os, "uname") as uname:
            SPEC.loader.exec_module(importlib.util.module_from_spec(SPEC))
            native.assert_not_called()
            uname.assert_not_called()


class ObservationTests(unittest.TestCase):
    def query(self, name, fake):
        return app.Sysctl(fake).read(name, app.Budget())

    def test_all_five_fixed_read_only_abi_queries(self):
        cases = (("physical_memory_bytes", b"hw.memsize", (8 * app.GIB).to_bytes(8, "little"), 8 * app.GIB, 8),
                 ("pressure", b"kern.memorystatus_vm_pressure_level", (1).to_bytes(4, "little"), "NORMAL", 4),
                 ("translation", b"sysctl.proc_translated", bytes(4), 0, 4),
                 ("product_version", b"kern.osproductversion", b"26.0\0", "26.0", 64),
                 ("build_version", b"kern.osversion", b"25A123\0", "25A123", 64))
        for name, key, raw, expected, length in cases:
            fake = FakeSysctl(raw)
            self.assertEqual(self.query(name, fake), app.observed(expected))
            self.assertEqual(fake.calls, [(key, length, None, 0)])
            self.assertIs(fake.restype, ctypes.c_int)
            self.assertEqual(fake.argtypes, [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                                             ctypes.c_void_p, ctypes.c_size_t])
        with self.assertRaises(app.Failure):
            self.query("arbitrary-key", FakeSysctl())

    def test_sysctl_short_long_invalid_and_error_results_are_missing(self):
        cases = (("physical_memory_bytes", FakeSysctl(bytes(8), size=4), "SYSCTL_SIZE_INVALID"),
                 ("physical_memory_bytes", FakeSysctl(bytes(8), size=9), "SYSCTL_SIZE_INVALID"),
                 ("physical_memory_bytes", FakeSysctl(bytes(8)), "SYSCTL_VALUE_INVALID"),
                 ("pressure", FakeSysctl((3).to_bytes(4, "little")), "SYSCTL_VALUE_INVALID"),
                 ("pressure", FakeSysctl(result=-1, error=errno.EPERM), "SYSCTL_ERROR"),
                 ("translation", FakeSysctl((2).to_bytes(4, "little")), "SYSCTL_VALUE_INVALID"),
                 ("translation", FakeSysctl(result=1, error=errno.ENOENT), "SYSCTL_ERROR"))
        for name, fake, reason in cases:
            self.assertEqual(self.query(name, fake), app.missing(reason))

    def test_enoent_translation_exception_does_not_mask_capacity_error(self):
        translation = self.query("translation", FakeSysctl(result=-1, error=errno.ENOENT))
        self.assertEqual(translation, app.missing("TRANSLATION_KEY_ABSENT"))
        values = observations()
        values["translation"] = translation
        self.assertEqual(app.native_role(values), "macos-arm64")
        values["physical_memory_bytes"] = self.query("physical_memory_bytes", FakeSysctl(result=-1, error=errno.ENOENT))
        self.assertEqual(values["physical_memory_bytes"], app.missing("SYSCTL_ERROR"))
        self.assertIn("PHYSICAL_MEMORY_BYTES_NOT_OBSERVED", app.assess(values, "macos-arm64-admission")["failures"])

    def test_bounded_os_strings_never_emit_raw_data(self):
        for raw, length in ((b"\0", 1), (b"26.0", 4), (b"26\x00.0\0", 6), (b"\xff\0", 2),
                            (b"/private/username\0", 18), (b"26.0\0", 65)):
            result = self.query("product_version", FakeSysctl(raw, size=length))
            self.assertEqual(result["status"], "NOT_OBSERVED")
            self.assertIsNone(result["value"])
            self.assertNotIn(b"private", app.json_bytes(result))

    def test_disk_uses_user_available_blocks_and_exact_initial_predicate(self):
        value = SimpleNamespace(f_frsize=4096, f_blocks=100 * app.GIB // 4096,
                                f_bavail=15 * app.GIB // 4096, f_bfree=90 * app.GIB // 4096)
        with mock.patch.object(app.os, "statvfs", return_value=value) as getter:
            result = app.read_disk(123, app.Budget())
        getter.assert_called_once_with(123)
        self.assertEqual(result["value"]["available_bytes"], 15 * app.GIB)
        values = observations()
        values["disk"] = result
        self.assertIn("INITIAL_DISK_BELOW_16_GIB", app.assess(values, "macos-arm64-admission")["failures"])
        self.assertEqual(app.assess(observations(), "macos-arm64-admission")["failures"], [])
        for change in ({"f_frsize": 0}, {"f_bavail": -1}, {"f_bavail": value.f_blocks + 1},
                       {"f_blocks": app.MAX_U64}):
            invalid = SimpleNamespace(**dict(vars(value), **change))
            with mock.patch.object(app.os, "statvfs", return_value=invalid):
                self.assertEqual(app.read_disk(123, app.Budget()), app.missing("INVALID_VALUE"))
        with mock.patch.object(app.os, "statvfs", side_effect=OSError("private/path")):
            self.assertEqual(app.read_disk(123, app.Budget()), app.missing("READ_FAILED"))

    def test_missing_warn_pressure_and_physical_not_available_ram(self):
        for pressure, failure in ((app.missing("SYSCTL_ERROR"), "PRESSURE_NOT_OBSERVED"),
                                  (app.observed("WARN"), "PRESSURE_NOT_NORMAL"),
                                  (app.observed("CRITICAL"), "PRESSURE_NOT_NORMAL")):
            values = observations()
            values["pressure"] = pressure
            self.assertIn(failure, app.assess(values, "macos-arm64-admission")["failures"])
        values = observations()
        values["physical_memory_bytes"] = app.observed(app.GIB)
        self.assertEqual(app.assess(values, "macos-arm64-admission")["failures"], [])
        self.assertEqual(app.LIMITATIONS["available_memory"], "NOT_OBSERVED")
        self.assertEqual(app.LIMITATIONS["prior_warn_hold"], "NOT_RELEASED")
        self.assertEqual(app.LIMITATIONS["writer_admission"], "NOT_GRANTED")
        self.assertEqual(app.LIMITATIONS["windows_witness"], "NOT_EXECUTED")

    def test_role_requires_kernel_pointer_and_native_translation(self):
        for operation in app.OPERATIONS:
            self.assertEqual(app.native_role(observations(operation)), app.OPERATIONS[operation]["role"])
        for name, value in (("pointer_bits", app.observed(32)), ("translation", app.observed(1)),
                            ("translation", app.missing("SYSCTL_ERROR")), ("kernel", app.missing("READ_FAILED"))):
            values = observations()
            values[name] = value
            self.assertEqual(app.native_role(values), "NOT_CONFIRMED")
        values = observations()
        values["ordinary_uid"] = app.observed(False)
        values["product_version"] = app.observed("15.0")
        failures = app.assess(values, "macos-arm64-admission")["failures"]
        self.assertIn("ORDINARY_UID_NOT_CONFIRMED", failures)
        self.assertIn("OS_IMAGE_ROLE_MISMATCH", failures)

    def test_collection_missing_native_library_retains_only_finite_fields(self):
        kernel = SimpleNamespace(sysname="Darwin", release="25.0.0", machine="arm64",
                                 nodename="NEVER_PUBLIC_HOST", version="NEVER_PUBLIC_BUILDER_PATH")
        disk = SimpleNamespace(f_frsize=4096, f_blocks=100 * app.GIB // 4096, f_bavail=20 * app.GIB // 4096)
        with mock.patch.object(app.sys, "platform", "darwin"), mock.patch.object(app.os, "name", "posix"), \
                mock.patch.object(app.os, "uname", return_value=kernel), mock.patch.object(app.os, "getuid", return_value=501), \
                mock.patch.object(app.os, "geteuid", return_value=501), mock.patch.object(app.os, "statvfs", return_value=disk), \
                mock.patch.object(app.Sysctl, "native", side_effect=OSError("NEVER_PUBLIC_LOADER_PATH")):
            result = app.collect_host(123, app.Budget())
        self.assertEqual(set(result), app.OBSERVATION_NAMES)
        for name in app.Sysctl.SPECS:
            self.assertEqual(result[name], app.missing("SYSCTL_UNAVAILABLE"))
        self.assertNotIn(b"NEVER_PUBLIC", app.json_bytes(result))


class FilesystemAndPublicTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-mac-model-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()  # Fixture setup only; production rejects aliases.
        self.root, self.temp = self.base / "checkout", self.base / "runner-temp"
        self.root.mkdir()
        self.temp.mkdir()
        (self.root / ".git").mkdir()
        self.write("base.txt", b"base\n")
        self.env, event = dispatch()
        self.env["GITHUB_OUTPUT"] = str(self.base / "output")
        Path(self.env["GITHUB_OUTPUT"]).write_bytes(b"")
        self.identity = app.dispatch_identity(self.env, event)
        self.runtime = {"implementation": "cpython", "version": [3, 9, 0], "platform": "darwin", "os_name": "posix",
                        "isolated": True, "no_site": True, "bytecode_disabled": True}

    def write(self, name, raw, mode=0o644):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(mode)
        return path

    def snapshot(self):
        budget = app.Budget()
        with app.Anchor(str(self.root), budget) as anchor:
            return app.source_tree(anchor, budget)

    def metadata(self):
        snapshot = self.snapshot()
        self.identity["source_tree"] = snapshot["tree"]
        values = observations()
        return {"schema": 1, "scope": app.SCOPE, "identity": copy.deepcopy(self.identity), "runtime": self.runtime,
                "source": {"method": "COMPLETE_FILESYSTEM_GIT_SHA1_TREE", "before": snapshot, "after": dict(snapshot)},
                "observations": values, "assessment": app.assess(values, self.identity["operation"]),
                "limitations": dict(app.LIMITATIONS), "observation_elapsed_ms": 1}

    def retained(self, metadata=None):
        metadata = self.metadata() if metadata is None else metadata
        budget = app.Budget()
        with app.Anchor(str(self.temp), budget) as temp:
            app.retain_public(temp, self.identity, self.runtime, metadata, budget)
        return Path(app.public_directory(str(self.temp), self.identity))

    def validate(self):
        budget = app.Budget()
        with app.Anchor(app.public_directory(str(self.temp), self.identity), budget) as public:
            return app.public_tree(public, self.identity, self.runtime, budget)

    def model_context(self):
        return mock.patch.object(app, "context", return_value=(self.runtime, self.identity, str(self.root), str(self.temp)))

    def replace_public(self, path, metadata):
        raw = app.json_bytes(metadata)
        (path / "metadata.json").write_bytes(raw)
        (path / "manifest.json").write_bytes(app.json_bytes(app.manifest_for(raw, self.identity)))

    def test_canonical_blobs_tree_modes_and_directory_slash_order(self):
        self.write("base.txt", b"hello\n")
        self.write("foo.bar", b"dot\n")
        self.write("foo/x", b"nested\n")
        child = bytes.fromhex(expected_tree([(b"100644", b"x", object_id(b"blob", b"nested\n"))]))
        expected = expected_tree([(b"100644", b"base.txt", object_id(b"blob", b"hello\n")),
                                  (b"100644", b"foo.bar", object_id(b"blob", b"dot\n")),
                                  (b"40000", b"foo", child)])
        snapshot = self.snapshot()
        self.assertEqual(snapshot, {"tree": expected, "entries": 4, "files": 3, "directories": 1, "bytes": 17})
        self.assertEqual(object_id(b"blob", b"").hex(), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_owner_execute_not_group_execute_controls_git_mode(self):
        for mode, git_mode in ((0o654, b"100644"), (0o744, b"100755")):
            self.write("base.txt", b"base\n", mode)
            self.assertEqual(self.snapshot()["tree"], expected_tree([(git_mode, b"base.txt", object_id(b"blob", b"base\n"))]))

    def test_hidden_extra_and_nested_git_are_not_skipped(self):
        initial = self.snapshot()["tree"]
        self.write(".git/private-ignored-control", b"excluded only at physical root")
        self.assertEqual(self.snapshot()["tree"], initial)
        self.write(".gitignore", b".gradle\n")
        self.write(".gradle/cache", b"extra")
        self.write("nested/.git/config", b"ordinary nested file")
        after = self.snapshot()
        self.assertNotEqual(after["tree"], initial)
        self.assertEqual(after["files"], 4)
        with app.Anchor(str(self.root), app.Budget()) as anchor, self.assertRaises(app.Failure):
            app.checked_source(anchor, initial, app.Budget())

    def test_raw_nonascii_names_are_not_normalized_in_git_records(self):
        self.write("é.txt", b"unicode\n")
        raw = next(os.fsencode(name) for name in os.listdir(self.root) if name not in (".git", "base.txt"))
        records = [(b"100644", b"base.txt", object_id(b"blob", b"base\n")),
                   (b"100644", raw, object_id(b"blob", b"unicode\n"))]
        self.assertEqual(self.snapshot()["tree"], expected_tree(sorted(records, key=lambda row: row[1])))
        self.assertEqual(app.entry_name("é".encode()), app.entry_name("e\u0301".encode()))
        for raw in (b"\xff", b"a/b", b"a\\b", b"a:b", b"a\n", b".."):
            with self.assertRaises(app.Failure):
                app.entry_name(raw)

    def test_case_and_unicode_aliases_rejected_before_reading(self):
        original = (self.root / "base.txt").stat()
        for names in (("Name", "name"), ("é", "e\u0301")):
            stream = mock.MagicMock()
            stream.__enter__.return_value = iter(SimpleNamespace(name=name) for name in names)
            with mock.patch.object(app.os, "scandir", return_value=stream), \
                    mock.patch.object(app.os, "stat", return_value=original), self.assertRaises(app.Failure):
                app.scan_directory(123, app.Budget())

    def test_root_git_and_ancestor_directory_links_are_rejected(self):
        (self.root / ".git").rmdir()
        target = self.base / "git-target"
        target.mkdir()
        (self.root / ".git").symlink_to(target, target_is_directory=True)
        with self.assertRaises(app.Failure):
            self.snapshot()
        alias = self.base / "checkout-alias"
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(app.Failure):
            app.Anchor(str(alias), app.Budget())

    def test_all_stability_dimensions_are_checked_after_read(self):
        original = (self.root / "base.txt").stat()
        for field in ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns"):
            changed = fake_stat(original, **{field: getattr(original, field) + 1})
            with self.subTest(field=field), mock.patch.object(app.os, "fstat", return_value=changed), \
                    mock.patch.object(app.os, "stat", return_value=original), self.assertRaises(app.Failure):
                app.finish_read(123, b"base.txt", 124, original, app.Budget())

    def test_empty_directories_and_gitfile_root_are_rejected(self):
        empty = self.root / "empty-submodule"
        empty.mkdir()
        with self.assertRaises(app.Failure):
            self.snapshot()
        empty.rmdir()
        (self.root / ".git").rmdir()
        self.write(".git", b"gitdir: elsewhere\n")
        with self.assertRaises(app.Failure):
            self.snapshot()

    def test_populated_gitlink_cannot_equal_ordinary_directory_tree(self):
        self.write("submodule/file", b"contents")
        expected = expected_tree([(b"100644", b"base.txt", object_id(b"blob", b"base\n")),
                                  (b"160000", b"submodule", bytes.fromhex("c" * 40))])
        with app.Anchor(str(self.root), app.Budget()) as anchor, self.assertRaises(app.Failure):
            app.checked_source(anchor, expected, app.Budget())

    def test_symlinks_hardlinks_special_and_unreadable_files_rejected(self):
        link = self.root / "link"
        link.symlink_to("base.txt")
        with self.assertRaises(app.Failure):
            self.snapshot()
        link.unlink()
        os.link(self.root / "base.txt", link)
        with self.assertRaises(app.Failure):
            self.snapshot()
        original = (self.root / "base.txt").stat()
        for changes in ({"st_mode": stat.S_IFIFO | 0o600, "st_nlink": 1},
                        {"st_mode": stat.S_IFREG, "st_nlink": 1}, {"st_nlink": 2}):
            with self.assertRaises(app.Failure):
                app.regular_stat(fake_stat(original, **changes), app.MAX_FILE_BYTES)
        state = app.TreeState(original.st_dev)
        state.remember(original)
        with self.assertRaises(app.Failure):
            state.remember(original)
        with self.assertRaises(app.Failure):
            app.TreeState(original.st_dev + 1).remember(original)

    def test_source_bounds_on_files_bytes_entries_names_and_depth(self):
        for constant, limit in (("MAX_FILE_BYTES", 4), ("MAX_SOURCE_BYTES", 4), ("MAX_ENTRIES", 0),
                                ("MAX_NAMES_BYTES", 1), ("MAX_NAME_BYTES", 3)):
            with self.subTest(constant=constant), mock.patch.object(app, constant, limit), self.assertRaises(app.Failure):
                self.snapshot()
        self.write("deep/file", b"x")
        with mock.patch.object(app, "MAX_DEPTH", 0), self.assertRaises(app.Failure):
            # Depth is rejected before descriptor use, not by absolute-path validation.
            app.tree_hash(123, (self.root / "deep").stat(), app.TreeState(self.root.stat().st_dev), app.Budget(), depth=1)

    def test_short_extra_and_changing_blob_reads_rejected(self):
        original_read = os.read
        for replacement in (lambda fd, count: b"", lambda fd, count: b"x" if count == 1 else original_read(fd, count)):
            with mock.patch.object(app.os, "read", side_effect=replacement), self.assertRaises(app.Failure):
                self.snapshot()
        changed = False

        def mutate(fd, count):
            nonlocal changed
            result = original_read(fd, count)
            if not changed:
                changed = True
                self.write("base.txt", b"different-longer\n")
            return result

        with mock.patch.object(app.os, "read", side_effect=mutate), self.assertRaises(app.Failure):
            self.snapshot()

    def test_membership_and_root_replacement_detected(self):
        original_scan, count = app.scan_directory, 0

        def mutate(fd, budget):
            nonlocal count
            count += 1
            if count == 2:
                self.write("late.txt", b"added")
            return original_scan(fd, budget)

        with mock.patch.object(app, "scan_directory", side_effect=mutate), self.assertRaises(app.Failure):
            self.snapshot()
        with app.Anchor(str(self.root), app.Budget()) as anchor:
            self.root.rename(self.base / "moved-checkout")
            self.root.mkdir()
            with self.assertRaises(app.Failure):
                app.source_tree(anchor, app.Budget())

    def test_closed_metadata_and_exact_types_include_no_native_receipt(self):
        original = self.metadata()
        app.validate_metadata(original, self.identity, self.runtime)
        mutations = [lambda value: value.update(hostname="private"),
                     lambda value: value["limitations"].update(children_launched=False),
                     lambda value: value["limitations"].update(ownedSurvivors=[]),
                     lambda value: value["source"]["before"].update(files=True),
                     lambda value: value["observations"].update(available_memory=app.observed(100)),
                     lambda value: value["observations"]["pressure"].update(value="UNKNOWN"),
                     lambda value: value["observations"]["disk"].update(status="NOT_OBSERVED", value=None, reason="PATH"),
                     lambda value: value["assessment"].update(status="NATIVE_PASS")]
        for mutate in mutations:
            invalid = copy.deepcopy(original)
            mutate(invalid)
            with self.assertRaises(app.Failure):
                app.validate_metadata(invalid, self.identity, self.runtime)

    def test_public_only_two_physical_unaliased_members(self):
        path = self.retained()
        self.assertEqual({p.name for p in path.iterdir()}, {"metadata.json", "manifest.json"})
        self.validate()
        extra = path / "private.json"
        extra.write_bytes(b"never retained")
        with self.assertRaises(app.Failure):
            self.validate()
        extra.unlink()
        os.link(path / "metadata.json", self.base / "alias")
        with self.assertRaises(app.Failure):
            self.validate()
        (self.base / "alias").unlink()
        (path / "manifest.json").unlink()
        (path / "manifest.json").symlink_to(self.root / "base.txt")
        with self.assertRaises(app.Failure):
            self.validate()

    def test_public_hash_schema_and_run_identity_tampering_rejected(self):
        metadata = self.metadata()
        path = self.retained(metadata)
        (path / "metadata.json").write_bytes(app.json_bytes(metadata) + b" ")
        with self.assertRaises(app.Failure):
            self.validate()
        for mutate in (lambda value: value.update(private_path="never public"),
                       lambda value: value["identity"].update(run_attempt="1"),
                       lambda value: value["source"]["after"].update(tree="d" * 40),
                       lambda value: value["observations"]["pressure"].update(value="WARN")):
            invalid = copy.deepcopy(metadata)
            mutate(invalid)
            self.replace_public(path, invalid)
            with self.assertRaises(app.Failure):
                self.validate()

    def test_run_failure_retains_measurement_but_is_not_admission(self):
        self.identity["source_tree"] = self.snapshot()["tree"]
        values = observations()
        values["pressure"] = app.observed("WARN")
        with self.model_context(), mock.patch.object(app, "collect_host", return_value=values):
            self.assertEqual(app.run(self.env, app.Budget()), 1)
        metadata = self.validate()[2]
        self.assertEqual(metadata["observations"]["pressure"], app.observed("WARN"))
        self.assertEqual(metadata["assessment"]["status"], "SNAPSHOT_PREDICATES_NOT_MET")
        self.assertEqual(metadata["limitations"]["terminal_outcome"], "REQUIRES_GENUINE_RUNNER_RECORD")
        with self.model_context():
            self.assertEqual(app.validate_public(self.env, app.Budget()), 0)
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"artifacts_ready=true\n")

    def test_source_change_between_observation_passes_prevents_retention(self):
        self.identity["source_tree"] = self.snapshot()["tree"]

        def mutate(fd, budget):
            self.write("base.txt", b"changed during collection")
            return observations()

        with self.model_context(), mock.patch.object(app, "collect_host", side_effect=mutate), self.assertRaises(app.Failure):
            app.run(self.env, app.Budget())
        self.assertEqual(list(self.temp.iterdir()), [])
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"")

    def test_missing_incomplete_or_cancelled_observation_never_sets_ready(self):
        self.identity["source_tree"] = self.snapshot()["tree"]
        with self.model_context(), self.assertRaises(OSError):
            app.validate_public(self.env, app.Budget())
        with self.model_context(), mock.patch.object(app, "collect_host", side_effect=KeyboardInterrupt()), \
                self.assertRaises(KeyboardInterrupt):
            app.run(self.env, app.Budget())
        path = Path(app.public_directory(str(self.temp), self.identity))
        path.mkdir(mode=0o700)
        (path / "metadata.json").write_bytes(b"{}\n")
        with self.model_context(), self.assertRaises(app.Failure):
            app.validate_public(self.env, app.Budget())
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"")

    def test_fresh_validation_checks_source_counts_and_never_reuses_output(self):
        metadata = self.metadata()
        path = self.retained(metadata)
        invalid = copy.deepcopy(metadata)
        for side in ("before", "after"):
            invalid["source"][side]["bytes"] += 1
        self.replace_public(path, invalid)
        with self.model_context(), self.assertRaises(app.Failure):
            app.validate_public(self.env, app.Budget())
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"")
        self.replace_public(path, metadata)
        with self.model_context():
            self.assertEqual(app.validate_public(self.env, app.Budget()), 0)
            with self.assertRaises(app.Failure):
                app.validate_public(self.env, app.Budget())
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), app.READINESS)
        with self.assertRaises(app.Failure):
            self.retained(metadata)

    def test_tamper_during_final_source_pass_prevents_readiness(self):
        metadata = self.metadata()
        path = self.retained(metadata)
        original, count = app.checked_source, 0

        def tamper(anchor, expected, budget):
            nonlocal count
            count += 1
            result = original(anchor, expected, budget)
            if count == 2:
                (path / "metadata.json").write_bytes(b"not metadata")
            return result

        with self.model_context(), mock.patch.object(app, "checked_source", side_effect=tamper), self.assertRaises(app.Failure):
            app.validate_public(self.env, app.Budget())
        self.assertEqual(Path(self.env["GITHUB_OUTPUT"]).read_bytes(), b"")

    def test_changed_source_or_symlink_output_cannot_be_marked_ready(self):
        self.retained()
        self.write("base.txt", b"changed source")
        with self.model_context(), self.assertRaises(app.Failure):
            app.validate_public(self.env, app.Budget())
        self.write("base.txt", b"base\n")
        output = Path(self.env["GITHUB_OUTPUT"])
        output.unlink()
        target = self.base / "unmodified-target"
        target.write_bytes(b"")
        output.symlink_to(target)
        with self.model_context(), self.assertRaises(app.Failure):
            app.validate_public(self.env, app.Budget())
        self.assertEqual(target.read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()
