#!/usr/bin/env python3
"""Offline finite-hint/file/caller models; never native closure or qualification."""
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
HINT_SOURCE = ROOT / "scripts/hosted_command_failure_hint.py"
CALLER_SOURCE = ROOT / "scripts/run-hosted-dependency-update.py"


def offline(event, _args):
    if event.startswith("socket.") or event in (
        "subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "ctypes.dlopen",
        "os.putenv", "os.unsetenv",
    ):
        raise AssertionError("offline hint controls attempted execution: " + event)


sys.addaudithook(offline)


def load(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


H = load("command_failure_hint_controls", HINT_SOURCE)
C = load("command_failure_caller_controls", CALLER_SOURCE)
INVOCATION, JOB = "a" * 32, "b" * 32
UNAVAILABLE = "UNAVAILABLE"
UPDATE_CODE = "PREREQUISITE_OWNER"
DRIVER_CODE = "JMDNS_ORIGINAL_OWNER"
# Independent reviewed guard roster, never derived from the production allowlist.
POLICY_DRIVER_CODES = frozenset({
    "JMDNS_POLICY_ARTIFACT_CHANGED",
    "JMDNS_POLICY_ARTIFACT_NOT_BOUND",
    "JMDNS_POLICY_CAPTURE_BOUND",
    "JMDNS_POLICY_COMPILER_IDENTITY",
    "JMDNS_POLICY_COMPILER_INPUT_CHANGED",
    "JMDNS_POLICY_COMPILER_OUTPUT_BOUND",
    "JMDNS_POLICY_FILE_CANONICAL",
    "JMDNS_POLICY_FILE_CHANGED",
    "JMDNS_POLICY_FILE_TYPE_OR_BOUND",
    "JMDNS_POLICY_HASH_TIMEOUT",
    "JMDNS_POLICY_JDK17_HEADERS",
    "JMDNS_POLICY_OUTPUT_ALREADY_EXISTS",
    "JMDNS_POLICY_OUTPUT_DIRECTORY",
    "JMDNS_POLICY_PREFLIGHT_BYPASSED",
    "JMDNS_POLICY_PREPARATION_TIMEOUT",
    "JMDNS_POLICY_RECHECK_TIMEOUT",
    "JMDNS_POLICY_RECORD_BOUND",
    "JMDNS_POLICY_RECORD_CHANGED",
    "JMDNS_POLICY_REQUEST_CHANGED",
    "JMDNS_POLICY_SELECTED_TOOLCHAIN",
    "JMDNS_POLICY_STREAM_COPY_CHANGED",
    "JMDNS_POLICY_TARGET_ONLY",
    "JMDNS_POLICY_TOOL_PATH",
    "JMDNS_POLICY_TRACKED_SOURCE",
})
# Independent eight-role/seven-predicate plan, not the production tables.
POLICY_FILE_ROLES = frozenset({
    "SOURCE", "CLANG", "JNI_HEADER", "JNI_PLATFORM_HEADER", "DNS_SD_HEADER",
    "LINKER_STUB", "JAVA_RELEASE", "DYLIB",
})
POLICY_FILE_PREDICATES = frozenset({
    "TYPE", "LINKS", "OWNER", "WRITE", "NONPOSITIVE", "STAT_LIMIT", "READ_LIMIT",
})
POLICY_FILE_CODES = frozenset(f"JMDNS_POLICY_FILE_{role}_{predicate}"
                              for role in POLICY_FILE_ROLES for predicate in POLICY_FILE_PREDICATES)
# Exactly two refusal-only additions; OWNER_LINKS never joins the predicate product.
POLICY_FILE_OWNER_LINK_CODES = frozenset({
    "JMDNS_POLICY_FILE_DNS_SD_HEADER_OWNER_LINKS",
    "JMDNS_POLICY_FILE_LINKER_STUB_OWNER_LINKS",
})
# Independent plan domains, not an oracle copied from the implementation.
LOCATION_ROLES = frozenset({
    "INIT", "JAVA_HASH", "COMMAND", "POLICY_FILE", "POLICY_DIR", "POLICY_PATH", "POLICY_PREP",
    "POLICY_CHECK", "JAVA_META", "RECORD", "TARGET", "TARGET_JOIN", "OBSERVER", "UNKNOWN",
})
LOCATION_FAMILIES = frozenset({
    "MISSING", "PERMISSION", "OS", "UNICODE", "KEY", "TYPE", "ATTRIBUTE", "VALUE", "TIMEOUT",
    "AUDIT", "OWNER", "DATA", "OTHER",
})
EXPECTED_LOCATION_CODES = frozenset("JMDNS_AT_" + role + "_" + family
                                    for role in LOCATION_ROLES for family in LOCATION_FAMILIES)
LOCATION_SAMPLES = (
    "JMDNS_AT_INIT_PERMISSION", "JMDNS_AT_POLICY_PREP_MISSING", "JMDNS_AT_COMMAND_AUDIT",
    "JMDNS_AT_OBSERVER_OWNER", "JMDNS_AT_UNKNOWN_OTHER",
)
PURPOSES = {
    "PREREQUISITES": "dependency-maintenance-prerequisites",
    "TARGET": "dependency-maintenance-jmdns-target",
    "OBSERVER": "dependency-maintenance-jmdns-observer",
    "GENERATOR": "dependency-maintenance-generator",
}
CHILDREN = {"PREREQUISITES": "_prerequisites", "TARGET": "_diagnostic-target", "OBSERVER": "_diagnostic-observer"}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("ascii")


def public_bytes(invocation=INVOCATION, phase="TARGET", code=DRIVER_CODE):
    return ("UNTRUSTED_V1 " + invocation + " " + phase + " " + code + "\n").encode("ascii")


def altered_stat(info, **changes):
    fields = {name: getattr(info, name) for name in dir(info) if name.startswith("st_")}
    fields.update(changes)
    return SimpleNamespace(**fields)


class HintFixture:
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.base = Path(self.stack.enter_context(tempfile.TemporaryDirectory(prefix="p2pkit-hint-model-"))).resolve()
        self.root = self.base / "controller"
        self.state = self.base / "operation/state"
        self.home = self.state / "gradle-home"
        self.directory = self.state / "evidence" / INVOCATION
        for directory in (self.root, self.state.parent, self.state, self.home,
                          self.directory.parent, self.directory):
            directory.mkdir(mode=0o700)
        self.path = self.directory / "public-failure-hint.txt"
        self.start_path = self.directory / "start.json"
        self.env = {
            "P2PKIT_AUDIT_JOB_ID": JOB,
            "P2PKIT_AUDIT_OWNERSHIP_CHAIN": INVOCATION,
            "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": json.dumps([
                {"id": INVOCATION, "job": JOB, "state": str(self.state), "home": str(self.home)}
            ], separators=(",", ":")),
            "P2PKIT_AUDIT_STATE_DIR": str(self.state),
            "GRADLE_USER_HOME": str(self.home),
        }

    def write(self, path, raw):
        with path.open("xb") as stream:
            stream.write(raw)
        path.chmod(0o600)

    def start(self, phase="TARGET", **changes):
        value = {
            "schema": 1, "id": INVOCATION, "purpose": PURPOSES[phase], "kind": "command",
            "requestedArgv": [str(Path(sys.executable).resolve()), "-I", "-B", "-S",
                              str(self.root / "scripts/run-hosted-dependency-update.py"), CHILDREN[phase]],
            "cwd": str(self.root), "wrapper": str(self.root / "gradlew"), "host": "macos-arm64",
            "jobId": JOB, "gradleHome": str(self.home), "startedUtc": "2026-09-28T00:00:00+00:00",
            "ancestorInvocationIds": [], "controllerPid": os.getppid(),
            "sourceBefore": None, "sourceAfter": None, "productExitCode": None, "stopExitCode": None,
            "finalExitCode": 125, "sourceUnchanged": False, "ownedSurvivors": [], "errors": [],
            "evidenceDirectory": str(self.directory),
        }
        value.update(changes)
        self.write(self.start_path, encoded(value))
        return value


class HintControls(HintFixture, unittest.TestCase):
    def test_fixed_public_format_and_purpose_mapping(self):
        self.assertEqual(H.BASENAME, "public-failure-hint.txt")
        self.assertEqual(H.MAX_BYTES, 128)
        self.assertEqual(H.DISCLAIMER, "HINT_NOT_CLOSURE_OR_ACCEPTANCE")
        for phase, purpose in PURPOSES.items():
            with self.subTest(phase=phase):
                self.assertEqual(H.phase_for_purpose(purpose), phase)
        for other in (None, 0, "", "TARGET", "dependency-maintenance-unknown"):
            with self.subTest(other=other):
                self.assertIsNone(H.phase_for_purpose(other))

    def test_projection_uses_exact_types_and_one_literal_argument_without_stringifying(self):
        class KnownUpdate(Exception):
            def __str__(self):
                raise AssertionError("exception must never be stringified")

        class KnownDriver(KnownUpdate):
            pass

        class UnknownSubtype(KnownUpdate):
            pass

        class UnsafeString(str):
            def __str__(self):
                raise AssertionError("argument must never be coerced")

        class UnsafeArgument:
            def __str__(self):
                raise AssertionError("private argument must never be stringified")

            def __repr__(self):
                raise AssertionError("private argument must never be represented")

        options = {"update_error_type": KnownUpdate, "driver_error_type": KnownDriver}
        self.assertIn(UPDATE_CODE, H.UPDATE_CODES)
        self.assertIn(DRIVER_CODE, H.DRIVER_CODES)
        for kind, codes in ((KnownUpdate, H.UPDATE_CODES), (KnownDriver, H.DRIVER_CODES)):
            for code in codes:
                self.assertEqual(H.failure_code(kind(code), **options), code)
        for error in (KnownUpdate(), KnownUpdate(UPDATE_CODE, "extra"),
                      KnownUpdate("PRIVATE_MODEL_TEXT_NOT_FOR_PUBLIC_OUTPUT"),
                      KnownUpdate(UnsafeString(UPDATE_CODE)), KnownUpdate(UnsafeArgument()),
                      KnownUpdate(DRIVER_CODE), KnownDriver(UPDATE_CODE), UnknownSubtype(UPDATE_CODE),
                      ValueError(UPDATE_CODE), KeyboardInterrupt()):
            self.assertEqual(H.failure_code(error, **options), "PRIVATE_FAILURE")
        self.assertEqual(H.failure_code(KnownUpdate(UPDATE_CODE)), "PRIVATE_FAILURE")

    def test_policy_guard_roster_matches_source_and_fixed_hint_allowlist(self):
        self.assertEqual(len(POLICY_DRIVER_CODES), 24)
        # Inspect bounded source text only; do not import or execute the driver.
        with (ROOT / "scripts/hosted_jmdns_driver.py").open("rb") as stream:
            raw = stream.read(256 * 1024 + 1)
        self.assertLessEqual(len(raw), 256 * 1024)
        literals = re.findall(rb"""["'](JMDNS_POLICY_[A-Z0-9_]+)["']""", raw)
        self.assertEqual({code.decode("ascii") for code in literals}, POLICY_DRIVER_CODES)
        # Prefix filtering is a coverage assertion, never an admission rule.
        for allowed in (H.DRIVER_CODES, H.CODES):
            self.assertEqual({code for code in allowed if code.startswith("JMDNS_POLICY_")},
                             POLICY_DRIVER_CODES | POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES)
        self.assertTrue((POLICY_DRIVER_CODES | POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES)
                        .isdisjoint(H.UPDATE_CODES))

    def test_policy_file_role_predicate_vocabulary_is_exact_and_bounded(self):
        self.assertEqual((len(POLICY_FILE_ROLES), len(POLICY_FILE_PREDICATES), len(POLICY_FILE_CODES)), (8, 7, 56))
        for actual, expected in ((H.POLICY_FILE_ROLES, POLICY_FILE_ROLES),
                                 (H.POLICY_FILE_PREDICATES, POLICY_FILE_PREDICATES),
                                 (H.POLICY_FILE_CODES, POLICY_FILE_CODES),
                                 (H.POLICY_FILE_OWNER_LINK_CODES, POLICY_FILE_OWNER_LINK_CODES)):
            self.assertIs(type(actual), frozenset)
            self.assertEqual(actual, expected)
        self.assertTrue(POLICY_FILE_CODES.isdisjoint(POLICY_DRIVER_CODES | H.UPDATE_CODES | H.LOCATION_CODES))
        self.assertEqual(len(POLICY_FILE_OWNER_LINK_CODES), 2)
        self.assertTrue(POLICY_FILE_OWNER_LINK_CODES.isdisjoint(
            POLICY_FILE_CODES | POLICY_DRIVER_CODES | H.UPDATE_CODES | H.LOCATION_CODES))
        self.assertEqual(len(POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES), 58)
        self.assertTrue(POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES <= H.DRIVER_CODES <= H.CODES)
        self.assertEqual(H.MAX_BYTES, 128)
        for code in sorted(POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES):
            for phase in PURPOSES:
                with self.subTest(code=code, phase=phase):
                    raw = public_bytes(phase=phase, code=code)
                    self.assertEqual(H._canonical(INVOCATION, phase, code), raw)
                    self.assertLessEqual(len(raw), 128)

    def test_policy_file_lookalikes_and_spoof_values_stay_unavailable(self):
        self.start()
        code = "JMDNS_POLICY_FILE_JNI_PLATFORM_HEADER_STAT_LIMIT"
        hooks = []

        def forbidden_hook(_value, *_args):
            hooks.append("hook")
            raise AssertionError("private hint values must not invoke hooks")

        class DriverError(RuntimeError):
            __str__ = forbidden_hook
            __repr__ = forbidden_hook

        class UnsafeString(str):
            __str__ = forbidden_hook
            __repr__ = forbidden_hook
            __hash__ = forbidden_hook
            __eq__ = forbidden_hook

        class UnsafeArgument:
            __str__ = forbidden_hook
            __repr__ = forbidden_hook
            __hash__ = forbidden_hook
            __eq__ = forbidden_hook

        lookalikes = (
            "JMDNS_POLICY_FILE_NEW_TYPE", "JMDNS_POLICY_FILE_SOURCE_NEW",
            "JMDNS_POLICY_FILE_PRE_SOURCE_TYPE", "JMDNS_POLICY_FILE_SOURCE_POST_TYPE",
            "JMDNS_POLICY_FILE_DYLIB_VERIFY_TYPE", code + "_EXTRA", code + "\n", code + "\0",
            " " + code, code.lower(), code + " PRIVATE_MODEL_TEXT",
        )
        lookalikes += tuple("JMDNS_POLICY_FILE_" + role + "_OWNER_LINKS"
                            for role in sorted(POLICY_FILE_ROLES - {"DNS_SD_HEADER", "LINKER_STUB"}))
        lookalikes += tuple(value for code in sorted(POLICY_FILE_OWNER_LINK_CODES)
                            for value in (code + "_EXTRA", code + "\n", code + "\0", " " + code,
                                          code.lower(), code + " PRIVATE_MODEL_TEXT"))
        for number, value in enumerate(lookalikes):
            with self.subTest(case=number):
                self.assertNotIn(value, H.CODES)
                self.assertEqual(H.failure_code(DriverError(value), driver_error_type=DriverError), "PRIVATE_FAILURE")
                with self.assertRaises(ValueError):
                    H._canonical(INVOCATION, "TARGET", value)
                self.assertIs(H.publish_child(self.root, self.env, "TARGET", value), False)
                self.assertFalse(self.path.exists())
                raw = public_bytes(code=value)
                self.write(self.path, raw)
                self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
                self.assertEqual(self.path.read_bytes(), raw)
                self.path.unlink()
        nonliterals = (None, 0, True, code.encode("ascii"), UnsafeString(code), UnsafeArgument())
        nonliterals += tuple(value for code in sorted(POLICY_FILE_OWNER_LINK_CODES)
                             for value in (code.encode("ascii"), UnsafeString(code)))
        for number, value in enumerate(nonliterals):
            with self.subTest(nonliteral=number):
                self.assertEqual(H.failure_code(DriverError(value), driver_error_type=DriverError), "PRIVATE_FAILURE")
                with self.assertRaises(ValueError):
                    H._canonical(INVOCATION, "TARGET", value)
                self.assertIs(H.publish_child(self.root, self.env, "TARGET", value), False)
                self.assertFalse(self.path.exists())
        self.assertEqual(hooks, [])

    def test_policy_projection_requires_exact_driver_type_and_builtin_literal_without_rendering(self):
        render_calls = []

        def forbidden_render(_value):
            render_calls.append("render")
            raise AssertionError("private errors and arguments must never be rendered")

        class PrivateError(RuntimeError):
            __str__ = forbidden_render
            __repr__ = forbidden_render

        class DriverError(PrivateError):
            pass

        class DriverSubtype(DriverError):
            pass

        class UpdateError(PrivateError):
            pass

        class UnsafeString(str):
            __str__ = forbidden_render
            __repr__ = forbidden_render

        class UnsafeArgument:
            __str__ = forbidden_render
            __repr__ = forbidden_render

        options = {"update_error_type": UpdateError, "driver_error_type": DriverError}
        for code in sorted(POLICY_DRIVER_CODES | POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES):
            with self.subTest(code=code):
                self.assertIs(type(code), str)
                self.assertEqual(H.failure_code(DriverError(code), **options), code)
                self.assertEqual(H.failure_code(DriverError(code)), "PRIVATE_FAILURE")
                errors = (
                    PrivateError(code), UpdateError(code), DriverSubtype(code),
                    DriverError(), DriverError(code, "extra"), DriverError(UnsafeString(code)),
                    DriverError(UnsafeArgument()), DriverError(code.encode("ascii")), DriverError(None),
                    DriverError("PRIVATE_MODEL_TEXT_NOT_FOR_PUBLIC_OUTPUT"),
                    DriverError("JMDNS_POLICY_UNREVIEWED_GUARD"),
                    DriverError(code + "_UNREVIEWED"), DriverError(code + "\n"),
                )
                for number, error in enumerate(errors):
                    with self.subTest(case=number):
                        self.assertEqual(H.failure_code(error, **options), "PRIVATE_FAILURE")
        # Catch attempted rendering even if failure_code swallowed its exception.
        self.assertEqual(render_calls, [])

    def test_all_policy_hints_round_trip_within_unchanged_128_byte_bound(self):
        self.assertEqual(H.MAX_BYTES, 128)
        self.start()
        before = set(self.base.rglob("*"))
        for code in sorted(POLICY_DRIVER_CODES | POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES):
            with self.subTest(code=code):
                raw = public_bytes(code=code)
                self.assertLessEqual(len(raw), 128)
                self.assertIs(H.publish_child(self.root, self.env, "TARGET", code), True)
                self.assertEqual(set(self.base.rglob("*")), before | {self.path})
                self.assertEqual(self.path.read_bytes(), raw)
                info = self.path.stat()
                self.assertEqual(info.st_size, len(raw))
                self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
                self.assertEqual(info.st_uid, os.getuid())
                self.assertEqual(info.st_nlink, 1)
                self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), code)
                self.assertFalse((self.directory / "receipt.json").exists())
                self.path.unlink()

    def test_location_vocabulary_and_both_phase_frames_are_closed_and_bounded(self):
        self.assertEqual((len(LOCATION_ROLES), len(LOCATION_FAMILIES), len(EXPECTED_LOCATION_CODES)), (14, 13, 182))
        for actual, expected in ((H.LOCATION_ROLES, LOCATION_ROLES), (H.LOCATION_FAMILIES, LOCATION_FAMILIES),
                                 (H.LOCATION_CODES, EXPECTED_LOCATION_CODES)):
            self.assertIs(type(actual), frozenset)
            self.assertEqual(actual, expected)
        self.assertTrue(H.LOCATION_CODES.isdisjoint(H.DRIVER_CODES | H.UPDATE_CODES))
        self.assertEqual(H.CODES, H.DRIVER_CODES | H.UPDATE_CODES | EXPECTED_LOCATION_CODES | {"PRIVATE_FAILURE"})
        self.assertEqual(H.MAX_BYTES, 128)

        class DriverError(RuntimeError):
            pass

        for code in sorted(EXPECTED_LOCATION_CODES):
            with self.subTest(code=code):
                # A location-looking exception argument must not bypass the mapper.
                self.assertEqual(H.failure_code(DriverError(code), driver_error_type=DriverError), "PRIVATE_FAILURE")
                for phase in ("TARGET", "OBSERVER"):
                    raw = public_bytes(phase=phase, code=code)
                    self.assertEqual(H._canonical(INVOCATION, phase, code), raw)
                    self.assertLessEqual(len(raw), 128)

    def test_location_lookalikes_and_nonbuiltin_strings_remain_unavailable(self):
        self.start()
        code = "JMDNS_AT_POLICY_PREP_MISSING"
        samples = ("JMDNS_AT_NEW_MISSING", "JMDNS_AT_POLICY_PREP_NEW", code + "_EXTRA", code + "\n",
                   code + "\0", " " + code, code.lower(), code + " PRIVATE_MODEL_TEXT")
        for number, value in enumerate(samples):
            with self.subTest(case=number):
                self.assertNotIn(value, H.CODES)
                with self.assertRaises(ValueError):
                    H._canonical(INVOCATION, "TARGET", value)
                self.assertIs(H.publish_child(self.root, self.env, "TARGET", value), False)
                self.assertFalse(self.path.exists())
                raw = public_bytes(code=value)
                self.write(self.path, raw)
                self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
                self.assertEqual(self.path.read_bytes(), raw)
                self.path.unlink()

        render_calls = []

        def forbidden_render(_value):
            render_calls.append("render")
            raise AssertionError("private hint arguments must never be rendered")

        class UnsafeString(str):
            __str__ = forbidden_render
            __repr__ = forbidden_render

        class UnsafeArgument:
            __str__ = forbidden_render
            __repr__ = forbidden_render

        for number, value in enumerate((None, 0, True, code.encode("ascii"), UnsafeString(code), UnsafeArgument())):
            with self.subTest(nonstring=number):
                with self.assertRaises(ValueError):
                    H._canonical(INVOCATION, "TARGET", value)
                self.assertIs(H.publish_child(self.root, self.env, "TARGET", value), False)
                self.assertFalse(self.path.exists())
        self.assertEqual(render_calls, [])

    def test_location_hints_round_trip_only_with_the_owned_child_binding(self):
        for phase in ("TARGET", "OBSERVER"):
            other = "OBSERVER" if phase == "TARGET" else "TARGET"
            self.start(phase)
            before = set(self.base.rglob("*"))
            for code in LOCATION_SAMPLES:
                with self.subTest(phase=phase, code=code):
                    self.assertIs(H.publish_child(self.root, self.env, other, code), False)
                    self.assertFalse(self.path.exists())
                    self.assertIs(H.publish_child(self.root, self.env, phase, code), True)
                    self.assertEqual(set(self.base.rglob("*")), before | {self.path})
                    raw, info = public_bytes(phase=phase, code=code), self.path.stat()
                    self.assertEqual(self.path.read_bytes(), raw)
                    self.assertEqual(info.st_size, len(raw))
                    self.assertLessEqual(info.st_size, 128)
                    self.assertEqual(stat.S_IMODE(info.st_mode), 0o600)
                    self.assertEqual(info.st_uid, os.getuid())
                    self.assertEqual(info.st_nlink, 1)
                    self.assertEqual(H.read_hint(self.state, INVOCATION, phase), code)
                    self.assertEqual(H.read_hint(self.state, INVOCATION, other), UNAVAILABLE)
                    self.assertEqual(H.read_hint(self.state, "c" * 32, phase), UNAVAILABLE)
                    self.assertEqual(self.path.read_bytes(), raw)
                    self.assertFalse((self.directory / "receipt.json").exists())
                    self.path.unlink()
            self.start_path.unlink()

    def test_exact_public_bytes_are_only_an_untrusted_hint(self):
        self.write(self.path, public_bytes())
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)
        self.assertEqual(self.path.read_bytes(), public_bytes())
        self.assertFalse((self.directory / "receipt.json").exists())

    def test_missing_malformed_partial_foreign_or_oversized_hint_is_unavailable(self):
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        samples = (
            b"", b"UNTRUSTED_V1 ", public_bytes()[:-1], public_bytes() + b"\n", public_bytes() + b"extra",
            public_bytes(invocation="c" * 32), public_bytes(phase="OBSERVER"),
            public_bytes(code="NON_ALLOWLISTED_PRIVATE_MODEL_TEXT"),
            public_bytes().replace(b"UNTRUSTED_V1", b"UNTRUSTED_V2"),
            public_bytes().replace(b" ", b"  ", 1), b"\xff", b"x" * 129,
        )
        for number, raw in enumerate(samples):
            with self.subTest(case=number):
                self.write(self.path, raw)
                self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
                self.assertEqual(self.path.read_bytes(), raw)
                self.path.unlink()

    def test_parent_selectors_cannot_redirect_hint_reads(self):
        self.write(self.path, public_bytes())
        for invocation, phase in (("../" + INVOCATION, "TARGET"), (INVOCATION.upper(), "TARGET"),
                                  (INVOCATION, "../TARGET"), (INVOCATION, "UNKNOWN"), (None, "TARGET")):
            with self.subTest(invocation=invocation, phase=phase):
                self.assertEqual(H.read_hint(self.state, invocation, phase), UNAVAILABLE)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)

    def test_symlink_and_hardlink_hints_are_unavailable(self):
        original = self.base / "foreign-public-hint"
        self.write(original, public_bytes())
        self.path.symlink_to(original)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.path.unlink()
        os.link(original, self.path)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertEqual(original.read_bytes(), public_bytes())

    def test_symlinked_ancestor_is_not_followed(self):
        self.write(self.path, public_bytes())
        alias = self.base / "state-alias"
        alias.symlink_to(self.state, target_is_directory=True)
        self.assertEqual(H.read_hint(alias, INVOCATION, "TARGET"), UNAVAILABLE)
        evidence_alias = self.state / "evidence-alias"
        self.directory.rename(evidence_alias)
        self.directory.symlink_to(evidence_alias, target_is_directory=True)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)

    def test_read_open_is_nonblocking_nofollow_and_fifo_cannot_block(self):
        real_open = os.open
        seen = []

        def checked_open(path, flags, *args, **kwargs):
            if Path(path).name == self.path.name:
                self.assertTrue(flags & os.O_NONBLOCK)
                self.assertTrue(flags & os.O_NOFOLLOW)
                seen.append(flags)
            return real_open(path, flags, *args, **kwargs)

        self.write(self.path, public_bytes())
        with patch.object(H.os, "open", side_effect=checked_open):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)
            self.assertTrue(seen)
            self.path.unlink()
            os.mkfifo(self.path, 0o600)
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)

    def test_wrong_owner_or_nonprivate_modes_are_unavailable(self):
        self.write(self.path, public_bytes())
        with patch.object(H.os, "getuid", return_value=os.getuid() + 1):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        inode, real_fstat = self.path.stat().st_ino, os.fstat

        def foreign_file(descriptor):
            info = real_fstat(descriptor)
            return altered_stat(info, st_uid=info.st_uid + 1) if info.st_ino == inode else info

        with patch.object(H.os, "fstat", side_effect=foreign_file):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        for mode in (0o644, 0o660, 0o666):
            with self.subTest(mode=mode):
                self.path.chmod(mode)
                self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.path.chmod(0o600)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), DRIVER_CODE)

    def test_replaced_file_during_open_is_unavailable(self):
        self.write(self.path, public_bytes())
        original_inode = self.path.stat().st_ino
        real_fstat = os.fstat
        replaced = False

        def replace_after_open(descriptor):
            nonlocal replaced
            info = real_fstat(descriptor)
            if info.st_ino == original_inode and not replaced:
                replaced = True
                self.path.rename(self.base / "original-open-hint")
                self.write(self.path, public_bytes())
            return info

        with patch.object(H.os, "fstat", side_effect=replace_after_open):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertTrue(replaced)

    def test_unstable_open_file_metadata_is_unavailable(self):
        self.write(self.path, public_bytes())
        original_inode = self.path.stat().st_ino
        real_fstat = os.fstat
        reads = 0

        def unstable(descriptor):
            nonlocal reads
            info = real_fstat(descriptor)
            if info.st_ino == original_inode:
                reads += 1
                if reads > 1:
                    return altered_stat(info, st_mtime_ns=info.st_mtime_ns + 1)
            return info

        with patch.object(H.os, "fstat", side_effect=unstable):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertGreaterEqual(reads, 2)

    def test_writer_uses_fixed_child_original_and_only_creates_bounded_public_hint(self):
        for phase in CHILDREN:
            with self.subTest(phase=phase):
                self.start(phase)
                before = set(self.base.rglob("*"))
                code = UPDATE_CODE if phase == "PREREQUISITES" else DRIVER_CODE
                self.assertIs(H.publish_child(self.root, self.env, phase, code), True)
                self.assertEqual(set(self.base.rglob("*")), before | {self.path})
                self.assertEqual(self.path.read_bytes(), public_bytes(phase=phase, code=code))
                self.assertLessEqual(self.path.stat().st_size, 128)
                self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
                self.assertEqual(H.read_hint(self.state, INVOCATION, phase), code)
                self.path.unlink()
                self.start_path.unlink()

    def test_writer_requires_complete_single_original_domain(self):
        self.start()
        cases = [{key: value for key, value in self.env.items() if key != missing} for missing in self.env]
        cases += [
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_CHAIN": INVOCATION + ":" + "c" * 32},
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": "[]"},
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": "{"},
            {**self.env, "P2PKIT_AUDIT_OWNERSHIP_DOMAINS": self.env["P2PKIT_AUDIT_OWNERSHIP_DOMAINS"].replace(JOB, "c" * 32)},
            {**self.env, "GRADLE_USER_HOME": str(self.base / "foreign-home")},
        ]
        for number, env in enumerate(cases):
            with self.subTest(case=number):
                self.assertIs(H.publish_child(self.root, env, "TARGET", DRIVER_CODE), False)
                self.assertFalse(self.path.exists())

    def test_writer_rejects_missing_malformed_foreign_or_changed_original_start(self):
        self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        changes = (
            {"schema": True}, {"id": "c" * 32}, {"jobId": "c" * 32}, {"kind": "gradle"},
            {"purpose": PURPOSES["OBSERVER"]}, {"requestedArgv": ["help"]},
            {"cwd": str(self.base / "foreign")}, {"wrapper": str(self.base / "gradlew")},
            {"gradleHome": str(self.base / "foreign-home")}, {"controllerPid": os.getppid() + 1},
            {"controllerPid": True}, {"ancestorInvocationIds": ["c" * 32]},
        )
        for number, changed in enumerate(changes):
            with self.subTest(case=number):
                self.start(**changed)
                self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
                self.assertFalse(self.path.exists())
                self.start_path.unlink()
        raw = encoded(self.start())
        self.start_path.unlink()
        for data in (raw.replace(b'"schema":1', b'"schema":1,"schema":1'), b"{", b"x" * 65537):
            self.write(self.start_path, data)
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
            self.assertFalse(self.path.exists())
            self.start_path.unlink()

    def test_writer_does_not_read_terminal_receipt_or_publish_for_nonchild_phase(self):
        self.start()
        receipt = self.directory / "receipt.json"
        self.write(receipt, b"SYNTHETIC_PRIVATE_RECEIPT_MUST_NOT_BE_READ\n")
        real_open = os.open

        def no_receipt_read(path, flags, *args, **kwargs):
            self.assertNotEqual(Path(path).name, "receipt.json")
            return real_open(path, flags, *args, **kwargs)

        with patch.object(H.os, "open", side_effect=no_receipt_read):
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertFalse(self.path.exists())
        receipt.unlink()
        for phase, code in (("GENERATOR", DRIVER_CODE), ("UNKNOWN", DRIVER_CODE), ("TARGET", "UNKNOWN")):
            self.assertIs(H.publish_child(self.root, self.env, phase, code), False)
            self.assertFalse(self.path.exists())

    def test_writer_never_clobbers_or_repairs_preexisting_hint(self):
        self.start()
        raw = b"unfinished prior public hint"
        self.write(self.path, raw)
        self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(self.path.read_bytes(), raw)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)

    def test_short_write_is_unavailable_without_retry_or_rewrite(self):
        self.start()
        real_write = os.write
        writes = []

        def short_write(descriptor, raw):
            writes.append(raw)
            return real_write(descriptor, raw[:7])

        with patch.object(H.os, "write", side_effect=short_write):
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(writes, [public_bytes()])
        self.assertEqual(self.path.read_bytes(), public_bytes()[:7])
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(self.path.read_bytes(), public_bytes()[:7])

    def test_io_or_close_failure_is_unavailable_and_retirement_continues(self):
        self.start()
        self.write(self.path, public_bytes())
        real_close = os.close
        closed = []

        def close_then_fail(descriptor):
            real_close(descriptor)  # Do not leak fixture descriptors while modeling failed close.
            closed.append(descriptor)
            if len(closed) == 1:
                raise OSError("PRIVATE_MODEL_CLOSE_DETAIL")

        with patch.object(H.os, "close", side_effect=close_then_fail):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.assertGreater(len(closed), 1)
        with patch.object(H.os, "read", side_effect=OSError("PRIVATE_MODEL_READ_DETAIL")):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        with patch.object(H.os, "read", return_value=public_bytes()[:7]):
            self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)
        self.path.unlink()
        with patch.object(H.os, "write", side_effect=OSError("PRIVATE_MODEL_WRITE_DETAIL")):
            self.assertIs(H.publish_child(self.root, self.env, "TARGET", DRIVER_CODE), False)
        self.assertEqual(H.read_hint(self.state, INVOCATION, "TARGET"), UNAVAILABLE)


class CallerControls(HintFixture, unittest.TestCase):
    @contextmanager
    def caller(self, returned=125, receipt_code=0, *, execute_error=None, read_error=None, receipt_changes=None,
               phase="TARGET"):
        """Real owned_command/validator; only executed owner return and receipt DATA are models."""
        source = {"commit": "c" * 40, "tree": "d" * 40, "status": "", "diffSha256": hashlib.sha256(b"").hexdigest()}
        context = {"id": JOB, "source": source}
        argv = [str(Path(sys.executable).resolve()), "-I", "-B", "-S",
                str(self.root / "scripts/run-hosted-dependency-update.py"), CHILDREN.get(phase, "_MODEL_generator")]
        purpose = PURPOSES[phase]
        receipt = {
            "schema": 1, "id": INVOCATION, "jobId": JOB, "kind": "command", "purpose": purpose,
            "requestedArgv": argv, "sourceBefore": source, "sourceAfter": source, "sourceUnchanged": True,
            "productExitCode": receipt_code, "stopExitCode": 0, "finalExitCode": receipt_code,
            "ownedSurvivors": [], "errors": [], "ownership": {"discoveryErrors": []},
            "cancelledSignals": [], "cancelRequested": False,
        }
        receipt.update(receipt_changes or {})
        raw = encoded(receipt)
        events = []

        def execute(args):
            events.append("execute")
            self.assertEqual(args.id, INVOCATION)
            self.assertEqual(args.kind, "command")
            self.assertEqual(args.purpose, purpose)
            self.assertEqual(args.argv, argv)
            self.assertEqual(args.cwd, str(self.root))
            self.assertEqual(args.wrapper, str(self.root / "gradlew"))
            self.assertEqual(args.stop_timeout, 120)
            self.assertEqual(os.environ["P2PKIT_AUDIT_STATE_DIR"], str(self.state))
            if execute_error is not None:
                raise execute_error
            return returned

        def original(path, limit):
            events.append("original-receipt")
            self.assertEqual(path, self.directory / "receipt.json", "raw streams/custody files must never be read")
            self.assertEqual(limit, 4 * C.MIB)
            if read_error is not None:
                raise read_error
            return raw, {}

        def module(name, relative):
            self.assertEqual((name, relative), ("hosted_command_failure_hint", "scripts/hosted_command_failure_hint.py"))
            return H  # Any exporter/native module load is a test failure.

        execute_mock = Mock(side_effect=execute)
        original_mock = Mock(side_effect=original)
        hint_read = H.read_hint

        def read_hint(*args):
            events.append("untrusted-hint")
            return hint_read(*args)

        with ExitStack() as stack:
            stack.enter_context(patch.object(C, "ROOT", self.root))
            stack.enter_context(patch.object(C.os, "environ", {}))
            stack.enter_context(patch.object(C.uuid, "uuid4", return_value=SimpleNamespace(hex=INVOCATION)))
            module_mock = stack.enter_context(patch.object(C, "module", side_effect=module))
            stack.enter_context(patch.object(C, "read_file", original_mock))
            hint_mock = stack.enter_context(patch.object(H, "read_hint", side_effect=read_hint))
            write_mock = stack.enter_context(patch.object(C, "write_new", side_effect=AssertionError("NO_RETURN_MARKERS")))
            custody_mock = stack.enter_context(patch.object(C, "retain_candidate_reports",
                                                         side_effect=AssertionError("NO_CUSTODY_ACCEPTANCE")))
            call = lambda: C.owned_command(SimpleNamespace(execute=execute_mock), self.state.parent, context,
                                          purpose, argv, 1200)
            yield SimpleNamespace(call=call, execute=execute_mock, original=original_mock, hints=hint_mock,
                                  modules=module_mock, write=write_mock, custody=custody_mock,
                                  receipt=receipt, raw=raw, events=events)

    def test_original_acceptance_predicate_bytes_are_unchanged(self):
        # Hash measured from the reviewed pre-repair 2dabecf3 source, not regenerated from this implementation.
        raw = CALLER_SOURCE.read_bytes()
        start = raw.index(b"def command_return_data(")
        end = raw.index(b"def owned_command(", start)
        self.assertEqual(hashlib.sha256(raw[start:end]).hexdigest(),
                         "783e36fa6772a55328001ef9cfff2153d1ee4dbd373b605de1f9fbc06b927f15")

    def test_actual_reserved125_cannot_be_replaced_by_optimistic_receipt_or_hint(self):
        self.write(self.path, public_bytes())
        with self.caller() as model:
            with self.assertRaises(C.OwnedCommandFailure) as failed:
                model.call()
            self.assertNotIsInstance(failed.exception, C.ClosedProductFailure)
            self.assertEqual(failed.exception.args, ("ORIGINAL_COMMAND_FAILED",))
            self.assertEqual(failed.exception.public_detail,
                "; phase=TARGET stage=VALIDATE_RETURN return=125 hint=JMDNS_ORIGINAL_OWNER HINT_NOT_CLOSURE_OR_ACCEPTANCE")
            self.assertEqual(model.events, ["execute", "original-receipt", "untrusted-hint"])
            model.execute.assert_called_once()
            model.original.assert_called_once()
            model.hints.assert_called_once_with(self.state, INVOCATION, "TARGET")
            model.modules.assert_called_once()
            model.write.assert_not_called()
            model.custody.assert_not_called()
            self.assertFalse((self.directory / "receipt.json").exists())  # Receipt DATA were modeled, never a real return.

    def test_all_policy_hints_keep_reserved125_refused_despite_optimistic_receipt(self):
        for code in sorted(POLICY_DRIVER_CODES | POLICY_FILE_CODES | POLICY_FILE_OWNER_LINK_CODES):
            with self.subTest(code=code):
                self.write(self.path, public_bytes(code=code))
                with self.caller(returned=125, receipt_code=0) as model:
                    with self.assertRaises(C.OwnedCommandFailure) as failed:
                        model.call()
                    self.assertIs(type(failed.exception), C.OwnedCommandFailure)
                    self.assertNotIsInstance(failed.exception, C.ClosedProductFailure)
                    self.assertEqual(failed.exception.args, ("ORIGINAL_COMMAND_FAILED",))
                    self.assertEqual(failed.exception.public_detail,
                        "; phase=TARGET stage=VALIDATE_RETURN return=125 hint=" + code +
                        " HINT_NOT_CLOSURE_OR_ACCEPTANCE")
                    self.assertEqual(model.receipt["productExitCode"], 0)
                    self.assertEqual(model.receipt["finalExitCode"], 0)
                    self.assertEqual(model.events, ["execute", "original-receipt", "untrusted-hint"])
                    model.execute.assert_called_once()
                    model.original.assert_called_once()
                    model.hints.assert_called_once_with(self.state, INVOCATION, "TARGET")
                    model.modules.assert_called_once_with("hosted_command_failure_hint",
                                                          "scripts/hosted_command_failure_hint.py")
                    model.write.assert_not_called()
                    model.custody.assert_not_called()
                    self.assertFalse((self.directory / "receipt.json").exists())
                self.assertEqual(self.path.read_bytes(), public_bytes(code=code))
                self.path.unlink()

    def test_location_hints_cannot_replace_reserved125_with_optimistic_receipt(self):
        for phase in ("TARGET", "OBSERVER"):
            for code in LOCATION_SAMPLES:
                with self.subTest(phase=phase, code=code), self.caller(returned=125, receipt_code=0, phase=phase) as model:
                    self.write(self.path, public_bytes(phase=phase, code=code))
                    with self.assertRaises(C.OwnedCommandFailure) as failed:
                        model.call()
                    self.assertIs(type(failed.exception), C.OwnedCommandFailure)
                    self.assertNotIsInstance(failed.exception, C.ClosedProductFailure)
                    self.assertEqual(failed.exception.args, ("ORIGINAL_COMMAND_FAILED",))
                    self.assertEqual(failed.exception.public_detail,
                        "; phase=" + phase + " stage=VALIDATE_RETURN return=125 hint=" + code +
                        " HINT_NOT_CLOSURE_OR_ACCEPTANCE")
                    self.assertEqual((model.receipt["productExitCode"], model.receipt["finalExitCode"]), (0, 0))
                    self.assertEqual(model.events, ["execute", "original-receipt", "untrusted-hint"])
                    model.execute.assert_called_once()
                    model.original.assert_called_once()
                    model.hints.assert_called_once_with(self.state, INVOCATION, phase)
                    model.modules.assert_called_once_with("hosted_command_failure_hint",
                                                          "scripts/hosted_command_failure_hint.py")
                    model.write.assert_not_called()
                    model.custody.assert_not_called()
                    self.assertFalse((self.directory / "receipt.json").exists())
                    self.assertEqual(self.path.read_bytes(), public_bytes(phase=phase, code=code))
                    self.path.unlink()

    def test_stage_and_actual_return_diagnostics_are_refusal_only(self):
        class PrivateFailure(Exception):
            def __str__(self):
                raise AssertionError("private failure must not be stringified")

        for options, stage, returned, events in (
            ({"execute_error": PrivateFailure()}, "EXECUTE", "NOT_RETURNED", ["execute", "untrusted-hint"]),
            ({"returned": 0, "read_error": PrivateFailure()}, "READ_ORIGINAL", "0",
             ["execute", "original-receipt", "untrusted-hint"]),
            ({"returned": 0, "receipt_changes": {"stopExitCode": 1}}, "VALIDATE_RETURN", "0",
             ["execute", "original-receipt", "untrusted-hint"]),
        ):
            with self.subTest(stage=stage), self.caller(**options) as model:
                with self.assertRaises(C.OwnedCommandFailure) as failed:
                    model.call()
                self.assertIn("stage=" + stage + " return=" + returned + " hint=UNAVAILABLE", failed.exception.public_detail)
                self.assertEqual(model.events, events)
                model.write.assert_not_called()
                model.custody.assert_not_called()

    def test_ordinary_success_and_failed_product_do_not_consult_hints(self):
        self.write(self.path, public_bytes())
        for code in (0, 1, 7, 123):
            with self.subTest(code=code), self.caller(returned=code, receipt_code=code) as model:
                if code == 0:
                    receipt, checksum = model.call()
                    self.assertEqual(receipt, model.receipt)
                    self.assertEqual(checksum, hashlib.sha256(model.raw).hexdigest())
                else:
                    with self.assertRaises(C.ClosedProductFailure) as failed:
                        model.call()
                    self.assertIs(type(failed.exception), C.ClosedProductFailure)
                    self.assertEqual(failed.exception.code, code)
                    self.assertEqual(failed.exception.receipt, model.receipt)
                    self.assertEqual(failed.exception.receipt_hash, hashlib.sha256(model.raw).hexdigest())
                model.hints.assert_not_called()
                self.assertEqual(model.events, ["execute", "original-receipt"])
                model.write.assert_not_called()

    def test_timeout_signal_and_noninteger_actual_returns_stay_refused(self):
        for code in (124, 125, 130, 255, -15, 256, True, "0", 0.0, None):
            with self.subTest(code=code), self.caller(returned=code) as model:
                with self.assertRaises(C.OwnedCommandFailure) as failed:
                    model.call()
                expected = str(code) if type(code) is int and 0 <= code <= 255 else (
                    "NOT_RETURNED" if code is None else "NONORDINARY")
                self.assertIn("stage=VALIDATE_RETURN return=" + expected + " ", failed.exception.public_detail)
                model.write.assert_not_called()
                model.custody.assert_not_called()

    def test_cancellation_baseexception_is_not_converted_or_followed_by_reads(self):
        cancellation = KeyboardInterrupt()
        with self.caller(execute_error=cancellation) as model:
            with self.assertRaises(KeyboardInterrupt) as failed:
                model.call()
            self.assertIs(failed.exception, cancellation)
            self.assertEqual(model.events, ["execute"])
            model.original.assert_not_called()
            model.hints.assert_not_called()
            model.write.assert_not_called()
            self.assertEqual(os.environ, {})

    def test_optional_hint_failure_cannot_mask_original_refusal(self):
        for hint_error in (OSError("PRIVATE_MODEL_HINT_READ_FAILURE"), KeyboardInterrupt()):
            with self.caller() as model:
                model.hints.side_effect = hint_error
                with self.assertRaises(C.OwnedCommandFailure) as failed:
                    model.call()
                self.assertIn("return=125 hint=UNAVAILABLE", failed.exception.public_detail)
                model.original.assert_called_once()
                model.write.assert_not_called()

    def test_outer_cli_renders_finite_diagnostic_and_still_returns125(self):
        refusal = C.OwnedCommandFailure(H, "TARGET", "VALIDATE_RETURN", 125, DRIVER_CODE)
        output = io.StringIO()
        with patch.object(C.sys, "argv", [str(CALLER_SOURCE), "generate"]), \
                patch.object(C, "generate", side_effect=refusal), patch.object(C.os, "umask"), \
                patch.object(C.sys, "stderr", output), patch.object(C, "module") as module:
            self.assertEqual(C.main(), 125)
        module.assert_not_called()
        self.assertEqual(output.getvalue(), "RESULT: FAIL — ORIGINAL_COMMAND_FAILED" + refusal.public_detail +
                         "; preserve private runner originals; no retry or partial acceptance\n")

    def test_fixed_child_preloads_typed_hint_helper_and_keeps_original_cli_failure(self):
        class FixedDriverError(Exception):
            def __str__(self):
                raise AssertionError("driver failure must never be stringified")

        for phase, child in CHILDREN.items():
            for hint_failure in (None, KeyboardInterrupt()):
                with self.subTest(phase=phase, hint_failure=hint_failure is not None), ExitStack() as stack:
                    events = []
                    code = UPDATE_CODE if phase == "PREREQUISITES" else DRIVER_CODE
                    error = C.UpdateError(code) if phase == "PREREQUISITES" else FixedDriverError(code)

                    def action(*_args):
                        events.append("action")
                        raise error

                    driver = SimpleNamespace(DriverError=FixedDriverError, target=action, observe=action)

                    def module(name, relative):
                        if (name, relative) == ("hosted_command_failure_hint", "scripts/hosted_command_failure_hint.py"):
                            events.append("hint-helper")
                            return H
                        self.assertEqual((name, relative), ("hosted_jmdns_driver", "scripts/hosted_jmdns_driver.py"))
                        events.append("driver")
                        return driver

                    def publish(*args):
                        events.append("finite-hint")
                        self.assertEqual(args, (self.root, self.env, phase, code))
                        if hint_failure is not None:
                            raise hint_failure
                        return True

                    output = io.StringIO()
                    stack.enter_context(patch.object(C, "ROOT", self.root))
                    stack.enter_context(patch.object(C.sys, "argv", [str(CALLER_SOURCE), child]))
                    stack.enter_context(patch.object(C.os, "environ", dict(self.env)))
                    stack.enter_context(patch.object(C.os, "umask"))
                    stack.enter_context(patch.object(C.sys, "stderr", output))
                    stack.enter_context(patch.object(C, "module", side_effect=module))
                    stack.enter_context(patch.object(C, "prerequisites", side_effect=action))
                    publisher = stack.enter_context(patch.object(H, "publish_child", side_effect=publish))
                    self.assertEqual(C.main(), 125)
                    publisher.assert_called_once()
                    self.assertEqual(events, ["hint-helper", *([] if phase == "PREREQUISITES" else ["driver"]),
                                              "action", "finite-hint"])
                    reason = UPDATE_CODE if phase == "PREREQUISITES" else "PRIVATE_FAILURE"
                    self.assertEqual(output.getvalue(), "RESULT: FAIL — " + reason +
                                     "; preserve private runner originals; no retry or partial acceptance\n")

    def test_child_location_fallback_is_generic_only_finite_and_optional(self):
        render_calls = []

        def forbidden_render(_value):
            render_calls.append("render")
            raise AssertionError("private errors and fallback values must never be rendered")

        class PrivateError(RuntimeError):
            __str__ = forbidden_render
            __repr__ = forbidden_render

        class FixedDriverError(PrivateError):
            pass

        class UnsafeString(str):
            __str__ = forbidden_render
            __repr__ = forbidden_render

        class UnsafeArgument:
            __str__ = forbidden_render
            __repr__ = forbidden_render

        location = "JMDNS_AT_POLICY_PREP_MISSING"
        # label, original error, fallback result/error, driver-load failure,
        # expected public code, and whether the fallback may be called.
        cases = [
            ("generic", PrivateError(UnsafeArgument()), location, None, False, location, True),
            ("private-driver", FixedDriverError("PRIVATE_MODEL_TEXT"), location, None, False, location, True),
            ("known-driver", FixedDriverError(DRIVER_CODE), location, None, False, DRIVER_CODE, False),
            ("known-policy", FixedDriverError("JMDNS_POLICY_FILE_CHANGED"), location, None, False,
             "JMDNS_POLICY_FILE_CHANGED", False),
            ("known-update", C.UpdateError(UPDATE_CODE), location, None, False, UPDATE_CODE, False),
            ("driver-load-failure", PrivateError(UnsafeArgument()), location, None, True, "PRIVATE_FAILURE", False),
        ]
        cases += [(code, FixedDriverError(code), location, None, False, code, False)
                  for code in sorted(POLICY_FILE_OWNER_LINK_CODES)]
        for label, result in (
            ("unknown-role", "JMDNS_AT_NEW_MISSING"), ("unknown-family", "JMDNS_AT_POLICY_PREP_NEW"),
            ("known-nonlocation", DRIVER_CODE), ("newline", location + "\n"), ("bytes", location.encode("ascii")),
            ("none", None), ("str-subclass", UnsafeString(location)), ("private-object", UnsafeArgument()),
        ):
            cases.append((label, PrivateError(UnsafeArgument()), result, None, False, "PRIVATE_FAILURE", True))
        for label, failure in (("raises", PrivateError(UnsafeArgument())), ("baseexception", KeyboardInterrupt())):
            cases.append((label, PrivateError(UnsafeArgument()), location, failure, False, "PRIVATE_FAILURE", True))
        models = [(phase, *case) for phase in ("TARGET", "OBSERVER") for case in cases]
        models += [
            ("PREREQUISITES", "no-driver", PrivateError(UnsafeArgument()), location, None, False, "PRIVATE_FAILURE", False),
            ("PREREQUISITES", "known-update", C.UpdateError(UPDATE_CODE), location, None, False, UPDATE_CODE, False),
        ]
        project = H.failure_code
        for phase, label, error, result, fallback_error, load_failed, expected, location_called in models:
            with self.subTest(phase=phase, case=label), ExitStack() as stack:
                events, original_args = [], error.args

                def action(*args):
                    events.append("action")
                    self.assertEqual(args, () if phase == "PREREQUISITES" else (C,))
                    raise error

                def fallback(caught):
                    events.append("location")
                    self.assertIs(caught, error)
                    if fallback_error is not None:
                        raise fallback_error
                    return result

                location_mock = Mock(side_effect=fallback)
                driver = SimpleNamespace(DriverError=FixedDriverError, target=action, observe=action,
                                         failure_hint=location_mock)

                def module(name, relative):
                    if (name, relative) == ("hosted_command_failure_hint", "scripts/hosted_command_failure_hint.py"):
                        events.append("hint-helper")
                        return H
                    self.assertEqual((name, relative), ("hosted_jmdns_driver", "scripts/hosted_jmdns_driver.py"))
                    events.append("driver")
                    if load_failed:
                        raise error
                    return driver

                def typed(caught, **types):
                    events.append("typed")
                    self.assertIs(caught, error)
                    return project(caught, **types)

                def publish(*args):
                    events.append("finite-hint")
                    self.assertEqual(args, (self.root, self.env, phase, expected))
                    return True

                output, stdout = io.StringIO(), io.StringIO()
                stack.enter_context(patch.object(C, "ROOT", self.root))
                stack.enter_context(patch.object(C.sys, "argv", [str(CALLER_SOURCE), CHILDREN[phase]]))
                stack.enter_context(patch.object(C.os, "environ", dict(self.env)))
                stack.enter_context(patch.object(C.os, "umask"))
                stack.enter_context(patch.object(C.sys, "stderr", output))
                stack.enter_context(patch.object(C.sys, "stdout", stdout))
                modules = stack.enter_context(patch.object(C, "module", side_effect=module))
                stack.enter_context(patch.object(C, "prerequisites", side_effect=action))
                projection = stack.enter_context(patch.object(H, "failure_code", side_effect=typed))
                publisher = stack.enter_context(patch.object(H, "publish_child", side_effect=publish))
                writes = stack.enter_context(patch.object(C, "write_new", side_effect=AssertionError("NO_RETURN_MARKERS")))
                custody = stack.enter_context(patch.object(C, "retain_candidate_reports",
                                                         side_effect=AssertionError("NO_CUSTODY_ACCEPTANCE")))
                self.assertEqual(C.main(), 125)
                expected_events = ["hint-helper"] + ([] if phase == "PREREQUISITES" else ["driver"])
                expected_events += ([] if load_failed else ["action"]) + ["typed"]
                expected_events += (["location"] if location_called else []) + ["finite-hint"]
                self.assertEqual(events, expected_events)
                self.assertEqual(modules.call_count, 1 if phase == "PREREQUISITES" else 2)
                registered = None if phase == "PREREQUISITES" or load_failed else FixedDriverError
                projection.assert_called_once_with(error, update_error_type=C.UpdateError, driver_error_type=registered)
                if location_called:
                    location_mock.assert_called_once()
                    self.assertIs(location_mock.call_args.args[0], error)
                else:
                    location_mock.assert_not_called()
                publisher.assert_called_once_with(self.root, self.env, phase, expected)
                writes.assert_not_called()
                custody.assert_not_called()
                self.assertIs(error.args, original_args)
                self.assertEqual(stdout.getvalue(), "")
                reason = UPDATE_CODE if type(error) is C.UpdateError else "PRIVATE_FAILURE"
                self.assertEqual(output.getvalue(), "RESULT: FAIL — " + reason +
                                 "; preserve private runner originals; no retry or partial acceptance\n")
        self.assertEqual(render_calls, [])


if __name__ == "__main__":
    unittest.main()
